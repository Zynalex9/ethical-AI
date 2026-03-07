"""
Scheduled validation tasks and notification triggers.

- ``run_scheduled_validations``: Celery beat periodic task that scans the
  ``scheduled_validations`` table and fires re-validations for due projects.
- ``check_metric_regression``: Compares the latest suite results to the
  previous suite and creates Notification records when metrics regress.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.celery_app import celery_app
from app.config import settings
from app.models.scheduled_validation import ScheduledValidation
from app.models.notification import Notification
from app.models.validation_suite import ValidationSuite
from app.models.validation import Validation, ValidationResult, ValidationStatus
from app.models.ml_model import MLModel

logger = logging.getLogger(__name__)

# Reuse engine from validation_tasks (or create a new one)
engine = create_async_engine(
    settings.database_url, echo=False, pool_pre_ping=True, pool_size=3, max_overflow=5
)
_async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def _next_run(frequency: str, from_dt: Optional[datetime] = None) -> datetime:
    base = from_dt or datetime.now(timezone.utc)
    if frequency == "daily":
        return base + timedelta(days=1)
    elif frequency == "monthly":
        return base + timedelta(days=30)
    return base + timedelta(weeks=1)


# ──────────────────────────────────────────────────────────────────
# Periodic task: scan schedules and fire validations
# ──────────────────────────────────────────────────────────────────

@celery_app.task(name="run_scheduled_validations")
def run_scheduled_validations() -> Dict[str, Any]:
    """Check all enabled schedules and fire validations for due ones."""
    import asyncio

    async def _scan():
        async with _async_session() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(ScheduledValidation).where(
                    ScheduledValidation.enabled == True,  # noqa: E712
                    ScheduledValidation.next_run_at <= now,
                )
            )
            due = result.scalars().all()
            triggered = 0

            for sched in due:
                config = sched.last_config
                if not config:
                    logger.warning("Schedule %s has no last_config — skipping", sched.id)
                    sched.next_run_at = _next_run(sched.frequency, now)
                    continue

                # Find latest model + dataset for the project
                model_q = await db.execute(
                    select(MLModel)
                    .where(MLModel.project_id == sched.project_id)
                    .order_by(MLModel.uploaded_at.desc())
                    .limit(1)
                )
                model = model_q.scalar_one_or_none()
                if not model:
                    logger.warning("No model found for project %s — skipping schedule", sched.project_id)
                    sched.next_run_at = _next_run(sched.frequency, now)
                    continue

                # Reuse model_id/dataset_id from config if present
                model_id = config.get("model_id", str(model.id))
                dataset_id = config.get("dataset_id")
                if not dataset_id:
                    logger.warning("No dataset_id in last_config for schedule %s — skipping", sched.id)
                    sched.next_run_at = _next_run(sched.frequency, now)
                    continue

                # Create a suite record tagged as scheduled
                suite = ValidationSuite(
                    model_id=UUID(model_id),
                    dataset_id=UUID(dataset_id),
                    status="pending",
                    created_by_id=sched.created_by_id,
                    started_at=now,
                )
                db.add(suite)
                await db.commit()
                await db.refresh(suite)

                # Queue the Celery task
                from app.tasks.validation_tasks import run_all_validations_task

                task = run_all_validations_task.delay(
                    suite_id=str(suite.id),
                    model_id=model_id,
                    dataset_id=dataset_id,
                    fairness_config=config.get("fairness_config", {}),
                    transparency_config=config.get("transparency_config", {}),
                    privacy_config=config.get("privacy_config", {}),
                    user_id=str(sched.created_by_id),
                    selected_validations=config.get("selected_validations", []),
                )

                suite.celery_task_id = task.id
                suite.status = "running"

                sched.last_run_at = now
                sched.next_run_at = _next_run(sched.frequency, now)
                await db.commit()

                triggered += 1
                logger.info(
                    "Scheduled validation fired: project=%s suite=%s task=%s",
                    sched.project_id, suite.id, task.id,
                )

            return {"due": len(due), "triggered": triggered}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_scan())
    finally:
        loop.close()


# ──────────────────────────────────────────────────────────────────
# Metric regression detection  (called after each suite completes)
# ──────────────────────────────────────────────────────────────────

@celery_app.task(name="check_metric_regression")
def check_metric_regression(suite_id: str) -> Dict[str, Any]:
    """
    Compare the just-completed suite to the previous suite on the same
    model. If any metric changed from PASS → FAIL, create Notification
    records for the suite owner.
    """
    import asyncio

    async def _check():
        async with _async_session() as db:
            current_suite_q = await db.execute(
                select(ValidationSuite).where(ValidationSuite.id == UUID(suite_id))
            )
            current_suite = current_suite_q.scalar_one_or_none()
            if not current_suite:
                return {"error": "suite not found"}

            # Find previous suite for same model (before this one)
            prev_q = await db.execute(
                select(ValidationSuite)
                .where(
                    ValidationSuite.model_id == current_suite.model_id,
                    ValidationSuite.id != current_suite.id,
                    ValidationSuite.status == "completed",
                )
                .order_by(ValidationSuite.completed_at.desc())
                .limit(1)
            )
            prev_suite = prev_q.scalar_one_or_none()
            if not prev_suite:
                return {"status": "no_previous_suite"}

            # Gather results for both suites
            async def _results_for(suite: ValidationSuite) -> Dict[str, bool]:
                """Return {metric_name: passed} for all validation results in a suite."""
                out = {}
                for vid in [suite.fairness_validation_id, suite.transparency_validation_id, suite.privacy_validation_id]:
                    if not vid:
                        continue
                    res = await db.execute(
                        select(ValidationResult).where(ValidationResult.validation_id == vid)
                    )
                    for r in res.scalars().all():
                        out[r.metric_name] = r.passed
                return out

            current_results = await _results_for(current_suite)
            prev_results = await _results_for(prev_suite)

            regressions = []
            for metric, passed in current_results.items():
                if not passed and prev_results.get(metric, False):
                    regressions.append(metric)

            if not regressions:
                return {"status": "no_regressions", "metrics_checked": len(current_results)}

            # Determine project ID from the model
            model_q = await db.execute(
                select(MLModel).where(MLModel.id == current_suite.model_id)
            )
            model_rec = model_q.scalar_one_or_none()
            project_id = model_rec.project_id if model_rec else None

            # Create notification
            msg = (
                f"Metric regression detected: {', '.join(regressions)} changed from PASS to FAIL "
                f"in suite {str(current_suite.id)[:8]}."
            )
            notif = Notification(
                user_id=current_suite.created_by_id,
                project_id=project_id,
                validation_suite_id=current_suite.id,
                message=msg,
                severity="error",
                link=f"/reports/validation/{current_suite.id}",
                details={"regressed_metrics": regressions, "suite_id": str(current_suite.id)},
            )
            db.add(notif)
            await db.commit()

            logger.warning("Metric regressions for suite %s: %s", suite_id, regressions)
            return {"status": "regressions_found", "metrics": regressions}

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_check())
    finally:
        loop.close()
