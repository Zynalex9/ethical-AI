"""
Traceability Service – Phase 3

Provides end-to-end traceability from ethical requirements to datasets,
models, and validation results.  Enables building a Requirement Traceability
Matrix (RTM) and performing root-cause analysis on failed validations.
"""

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.project import Project
from app.models.requirement import Requirement
from app.models.validation import Validation, ValidationResult, ValidationStatus
from app.models.validation_suite import ValidationSuite
from app.models.ml_model import MLModel
from app.models.dataset import Dataset

logger = logging.getLogger(__name__)


class TraceabilityService:
    """Build and query requirement traceability matrices."""

    # ------------------------------------------------------------------
    # 3.1.1  build_traceability_matrix
    # ------------------------------------------------------------------
    async def build_traceability_matrix(
        self, db: AsyncSession, project_id: UUID
    ) -> Dict[str, Any]:
        """
        Build a full traceability matrix for a project.

        For every requirement in the project, gather all linked validations
        (and their results), the dataset and model used, and return a
        structured list of *traces*.
        """

        # 1. Fetch all requirements for this project
        req_result = await db.execute(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.created_at)
        )
        requirements = req_result.scalars().all()

        # 2. Fetch all validation suites for this project (via model → project)
        suite_result = await db.execute(
            select(ValidationSuite)
            .join(MLModel, ValidationSuite.model_id == MLModel.id)
            .options(
                selectinload(ValidationSuite.model),
                selectinload(ValidationSuite.dataset),
            )
            .where(MLModel.project_id == project_id)
            .order_by(ValidationSuite.created_at.desc())
        )
        suites = suite_result.scalars().all()

        # 3. Fetch all validations belonging to those suites
        suite_validation_ids: List[UUID] = []
        for s in suites:
            for vid in [
                s.fairness_validation_id,
                s.transparency_validation_id,
                s.privacy_validation_id,
            ]:
                if vid:
                    suite_validation_ids.append(vid)

        # Also fetch validations that directly reference requirements (by requirement_id)
        req_ids = [r.id for r in requirements]

        # Fetch all validations for this project's models
        model_result = await db.execute(
            select(MLModel.id).where(MLModel.project_id == project_id)
        )
        model_ids = [row[0] for row in model_result.all()]

        dataset_result = await db.execute(
            select(Dataset.id).where(Dataset.project_id == project_id)
        )
        dataset_ids = [row[0] for row in dataset_result.all()]

        # Fetch all validations for this project
        val_result = await db.execute(
            select(Validation)
            .where(
                Validation.model_id.in_(model_ids) if model_ids else Validation.id.is_(None)
            )
            .order_by(Validation.created_at.desc())
        )
        all_validations = val_result.scalars().all()

        # For each validation fetch results
        validation_results_map: Dict[UUID, List[ValidationResult]] = {}
        for v in all_validations:
            vr_result = await db.execute(
                select(ValidationResult).where(
                    ValidationResult.validation_id == v.id
                )
            )
            validation_results_map[v.id] = list(vr_result.scalars().all())

        # Build model / dataset lookup
        model_lookup: Dict[UUID, MLModel] = {}
        for s in suites:
            if s.model:
                model_lookup[s.model.id] = s.model
        # Supplement with direct query
        if model_ids:
            m_result = await db.execute(
                select(MLModel).where(MLModel.id.in_(model_ids))
            )
            for m in m_result.scalars().all():
                model_lookup[m.id] = m

        dataset_lookup: Dict[UUID, Dataset] = {}
        for s in suites:
            if s.dataset:
                dataset_lookup[s.dataset.id] = s.dataset
        if dataset_ids:
            d_result = await db.execute(
                select(Dataset).where(Dataset.id.in_(dataset_ids))
            )
            for d in d_result.scalars().all():
                dataset_lookup[d.id] = d

        # Map suite → validation IDs for quick lookup
        suite_by_val: Dict[UUID, ValidationSuite] = {}
        for s in suites:
            for vid in [
                s.fairness_validation_id,
                s.transparency_validation_id,
                s.privacy_validation_id,
            ]:
                if vid:
                    suite_by_val[vid] = s

        # 4. Build traces
        traces: List[Dict[str, Any]] = []

        for req in requirements:
            # Find validations linked to this requirement
            linked_validations = [
                v for v in all_validations if v.requirement_id == req.id
            ]

            if linked_validations:
                for v in linked_validations:
                    results = validation_results_map.get(v.id, [])
                    overall_passed = all(r.passed for r in results) if results else None
                    suite = suite_by_val.get(v.id)

                    model_info = model_lookup.get(v.model_id)
                    dataset_info = dataset_lookup.get(v.dataset_id)

                    traces.append(self._build_trace(
                        requirement=req,
                        validation=v,
                        results=results,
                        overall_passed=overall_passed,
                        model=model_info,
                        dataset=dataset_info,
                        suite=suite,
                    ))
            else:
                # Requirement exists but no validation has been run for it yet
                traces.append({
                    "requirement": self._serialize_requirement(req),
                    "dataset": None,
                    "model": None,
                    "validation": None,
                    "status": "not_validated",
                })

        # Also capture unlinked validations (from suites without requirement links)
        linked_val_ids = {v.id for req in requirements for v in all_validations if v.requirement_id == req.id}
        for v in all_validations:
            if v.id not in linked_val_ids:
                results = validation_results_map.get(v.id, [])
                overall_passed = all(r.passed for r in results) if results else None
                model_info = model_lookup.get(v.model_id)
                dataset_info = dataset_lookup.get(v.dataset_id)
                suite = suite_by_val.get(v.id)

                # Determine the principle from results
                principle = None
                if results:
                    principles = set(r.principle for r in results)
                    principle = list(principles)[0] if len(principles) == 1 else "multiple"

                traces.append({
                    "requirement": None,
                    "dataset": self._serialize_dataset(dataset_info) if dataset_info else None,
                    "model": self._serialize_model(model_info) if model_info else None,
                    "validation": self._serialize_validation(v, results),
                    "status": "pass" if overall_passed else ("fail" if overall_passed is False else "unknown"),
                    "unlinked_principle": principle,
                })

        # Summary stats
        total_reqs = len(requirements)
        total_validations = len(all_validations)
        pass_count = sum(
            1 for t in traces if t["status"] == "pass"
        )
        fail_count = sum(
            1 for t in traces if t["status"] == "fail"
        )
        not_validated = sum(
            1 for t in traces if t["status"] == "not_validated"
        )

        return {
            "project_id": str(project_id),
            "summary": {
                "total_requirements": total_reqs,
                "total_validations": total_validations,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "not_validated_count": not_validated,
                "pass_rate": round(pass_count / max(pass_count + fail_count, 1) * 100, 1),
            },
            "traces": traces,
        }

    # ------------------------------------------------------------------
    # 3.1.2  trace_requirement_to_results
    # ------------------------------------------------------------------
    async def trace_requirement_to_results(
        self, db: AsyncSession, requirement_id: UUID
    ) -> List[Dict[str, Any]]:
        """Return compliance history for one requirement across all validations."""

        req_result = await db.execute(
            select(Requirement).where(Requirement.id == requirement_id)
        )
        requirement = req_result.scalar_one_or_none()
        if not requirement:
            return []

        val_result = await db.execute(
            select(Validation)
            .where(Validation.requirement_id == requirement_id)
            .order_by(Validation.created_at.desc())
        )
        validations = val_result.scalars().all()

        history: List[Dict[str, Any]] = []
        for v in validations:
            vr_result = await db.execute(
                select(ValidationResult).where(
                    ValidationResult.validation_id == v.id
                )
            )
            results = vr_result.scalars().all()
            overall_passed = all(r.passed for r in results) if results else None

            # Fetch model/dataset names
            model = await db.get(MLModel, v.model_id)
            dataset = await db.get(Dataset, v.dataset_id)

            history.append({
                "validation_id": str(v.id),
                "status": v.status if isinstance(v.status, str) else v.status.value,
                "overall_passed": overall_passed,
                "model_name": model.name if model else "Unknown",
                "dataset_name": dataset.name if dataset else "Unknown",
                "behavior_pattern": v.behavior_pattern,
                "affected_groups": v.affected_groups,
                "started_at": v.started_at.isoformat() if v.started_at else None,
                "completed_at": v.completed_at.isoformat() if v.completed_at else None,
                "created_at": v.created_at.isoformat(),
                "results": [
                    {
                        "metric_name": r.metric_name,
                        "metric_value": r.metric_value,
                        "threshold": r.threshold,
                        "passed": r.passed,
                        "principle": r.principle,
                    }
                    for r in results
                ],
            })

        return history

    # ------------------------------------------------------------------
    # 3.1.3  trace_dataset_to_requirements
    # ------------------------------------------------------------------
    async def trace_dataset_to_requirements(
        self, db: AsyncSession, dataset_id: UUID
    ) -> List[Dict[str, Any]]:
        """
        Given a dataset, show which requirements were elicited from it
        and which validations used this dataset.
        """
        dataset = await db.get(Dataset, dataset_id)
        if not dataset:
            return []

        # Find requirements for the same project
        req_result = await db.execute(
            select(Requirement).where(Requirement.project_id == dataset.project_id)
        )
        requirements = req_result.scalars().all()

        # Find validations that used this dataset
        val_result = await db.execute(
            select(Validation)
            .where(Validation.dataset_id == dataset_id)
            .order_by(Validation.created_at.desc())
        )
        validations = val_result.scalars().all()

        # Map requirement_id → validations
        req_val_map: Dict[Optional[UUID], List[Validation]] = {}
        for v in validations:
            req_val_map.setdefault(v.requirement_id, []).append(v)

        impact: List[Dict[str, Any]] = []
        for req in requirements:
            linked_vals = req_val_map.get(req.id, [])
            impact.append({
                "requirement": self._serialize_requirement(req),
                "validation_count": len(linked_vals),
                "latest_validation": (
                    {
                        "validation_id": str(linked_vals[0].id),
                        "status": linked_vals[0].status if isinstance(linked_vals[0].status, str) else linked_vals[0].status.value,
                        "completed_at": linked_vals[0].completed_at.isoformat() if linked_vals[0].completed_at else None,
                    }
                    if linked_vals
                    else None
                ),
            })

        # Unlinked validations for this dataset
        unlinked = req_val_map.get(None, [])

        return {
            "dataset": self._serialize_dataset(dataset),
            "requirements_impact": impact,
            "unlinked_validations_count": len(unlinked),
            "total_validations_using_dataset": len(validations),
        }

    # ------------------------------------------------------------------
    # 3.1.4  trace_validation_failure_to_root_cause
    # ------------------------------------------------------------------
    async def trace_validation_failure_to_root_cause(
        self, db: AsyncSession, validation_id: UUID
    ) -> Dict[str, Any]:
        """
        Perform root-cause analysis for a failed validation.

        Traces back to the requirement violated, the dataset features
        involved, and the model behavior pattern.
        """
        validation = await db.get(Validation, validation_id)
        if not validation:
            return {"error": "Validation not found"}

        # Get results
        vr_result = await db.execute(
            select(ValidationResult).where(
                ValidationResult.validation_id == validation_id
            )
        )
        results = vr_result.scalars().all()

        failed_results = [r for r in results if not r.passed]
        passed_results = [r for r in results if r.passed]

        # Get linked requirement
        requirement = None
        if validation.requirement_id:
            requirement = await db.get(Requirement, validation.requirement_id)

        # Get model and dataset
        model = await db.get(MLModel, validation.model_id) if validation.model_id else None
        dataset = await db.get(Dataset, validation.dataset_id) if validation.dataset_id else None

        # Build root cause analysis
        root_causes: List[Dict[str, Any]] = []
        recommendations: List[str] = []

        for fr in failed_results:
            cause = {
                "metric_name": fr.metric_name,
                "metric_value": fr.metric_value,
                "threshold": fr.threshold,
                "principle": fr.principle,
                "gap": None,
                "description": "",
                "affected_feature": None,
            }

            # Compute gap
            if fr.metric_value is not None and fr.threshold is not None:
                cause["gap"] = round(abs(fr.metric_value - fr.threshold), 4)

            # Generate description based on principle and metric
            cause["description"] = self._generate_root_cause_description(
                fr, validation, dataset
            )

            # Extract affected features from details
            if fr.details:
                cause["affected_feature"] = fr.details.get("affected_feature")
                cause["group_breakdown"] = fr.details.get("group_metrics")

            root_causes.append(cause)

            # Generate recommendation
            recommendations.append(
                self._generate_recommendation(fr, dataset)
            )

        # Overall behavior pattern
        behavior = validation.behavior_pattern or self.extract_model_behavior_pattern(
            {"results": [{"metric_name": r.metric_name, "metric_value": r.metric_value, "passed": r.passed, "details": r.details, "principle": r.principle} for r in results]}
        )

        return {
            "validation_id": str(validation_id),
            "status": validation.status if isinstance(validation.status, str) else validation.status.value,
            "requirement": self._serialize_requirement(requirement) if requirement else None,
            "model": self._serialize_model(model) if model else None,
            "dataset": self._serialize_dataset(dataset) if dataset else None,
            "overall_passed": all(r.passed for r in results) if results else None,
            "behavior_pattern": behavior,
            "affected_groups": validation.affected_groups or [],
            "total_metrics": len(results),
            "passed_metrics": len(passed_results),
            "failed_metrics": len(failed_results),
            "root_causes": root_causes,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # 3.1.5  extract_model_behavior_pattern
    # ------------------------------------------------------------------
    def extract_model_behavior_pattern(
        self, validation_result: Dict[str, Any]
    ) -> str:
        """
        Generate a plain-English description of what the model is doing,
        based on the validation results.
        """
        results = validation_result.get("results", [])
        if not results:
            return "No validation results available."

        patterns: List[str] = []

        for r in results:
            name = r.get("metric_name", "Unknown metric")
            value = r.get("metric_value")
            passed = r.get("passed")
            principle = r.get("principle", "")
            details = r.get("details", {}) or {}

            if value is None:
                continue

            if principle == "fairness":
                if "parity" in name.lower() or "impact" in name.lower():
                    if passed:
                        patterns.append(
                            f"{name}: {value:.3f} — model shows acceptable group parity."
                        )
                    else:
                        patterns.append(
                            f"{name}: {value:.3f} — model exhibits disparity between demographic groups."
                        )
                elif "opportunity" in name.lower() or "odds" in name.lower():
                    if passed:
                        patterns.append(
                            f"{name}: {value:.3f} — model errors are balanced across groups."
                        )
                    else:
                        patterns.append(
                            f"{name}: {value:.3f} — model error rates differ significantly across groups."
                        )
                else:
                    patterns.append(f"{name}: {value:.3f} — {'passed' if passed else 'failed'}.")
            elif principle == "privacy":
                if passed:
                    patterns.append(f"{name}: privacy check passed.")
                else:
                    patterns.append(f"{name}: privacy risk detected (value={value}).")
            elif principle == "transparency":
                patterns.append(f"{name}: explainability metric {value:.3f}.")
            else:
                patterns.append(f"{name}: {value} — {'passed' if passed else 'failed'}.")

        if not patterns:
            return "No measurable behavior patterns detected."

        return " ".join(patterns)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _build_trace(
        self,
        requirement: Requirement,
        validation: Validation,
        results: List[ValidationResult],
        overall_passed: Optional[bool],
        model: Optional[MLModel],
        dataset: Optional[Dataset],
        suite: Optional[ValidationSuite],
    ) -> Dict[str, Any]:
        return {
            "requirement": self._serialize_requirement(requirement),
            "dataset": self._serialize_dataset(dataset) if dataset else None,
            "model": self._serialize_model(model) if model else None,
            "validation": self._serialize_validation(validation, results),
            "suite_id": str(suite.id) if suite else None,
            "status": (
                "pass" if overall_passed
                else ("fail" if overall_passed is False else "unknown")
            ),
        }

    @staticmethod
    def _serialize_requirement(req: Requirement) -> Dict[str, Any]:
        return {
            "id": str(req.id),
            "name": req.name,
            "principle": req.principle if isinstance(req.principle, str) else req.principle.value,
            "description": req.description,
            "status": req.status if isinstance(req.status, str) else req.status.value,
            "specification": req.specification,
            "elicited_automatically": req.elicited_automatically,
            "confidence_score": req.confidence_score,
            "created_at": req.created_at.isoformat(),
        }

    @staticmethod
    def _serialize_model(model: MLModel) -> Dict[str, Any]:
        return {
            "id": str(model.id),
            "name": model.name,
            "model_type": model.model_type if isinstance(model.model_type, str) else model.model_type.value,
            "version": model.version,
        }

    @staticmethod
    def _serialize_dataset(dataset: Dataset) -> Dict[str, Any]:
        return {
            "id": str(dataset.id),
            "name": dataset.name,
            "row_count": dataset.row_count,
            "column_count": dataset.column_count,
            "sensitive_attributes": dataset.sensitive_attributes,
            "target_column": dataset.target_column,
        }

    @staticmethod
    def _serialize_validation(
        validation: Validation, results: List[ValidationResult]
    ) -> Dict[str, Any]:
        return {
            "id": str(validation.id),
            "status": validation.status if isinstance(validation.status, str) else validation.status.value,
            "behavior_pattern": validation.behavior_pattern,
            "affected_groups": validation.affected_groups,
            "started_at": validation.started_at.isoformat() if validation.started_at else None,
            "completed_at": validation.completed_at.isoformat() if validation.completed_at else None,
            "mlflow_run_id": validation.mlflow_run_id,
            "results": [
                {
                    "metric_name": r.metric_name,
                    "metric_value": r.metric_value,
                    "threshold": r.threshold,
                    "passed": r.passed,
                    "principle": r.principle,
                    "details": r.details,
                }
                for r in results
            ],
        }

    @staticmethod
    def _generate_root_cause_description(
        result: ValidationResult,
        validation: Validation,
        dataset: Optional[Dataset],
    ) -> str:
        """Generate a human-readable root-cause description for a failed metric."""
        name = result.metric_name
        value = result.metric_value
        threshold = result.threshold
        principle = result.principle

        if principle == "fairness":
            sensitive = (
                ", ".join(dataset.sensitive_attributes)
                if dataset and dataset.sensitive_attributes
                else "unknown attribute"
            )
            if "parity" in name.lower() or "impact" in name.lower():
                return (
                    f"The model's selection/approval rate differs across groups defined by "
                    f"'{sensitive}'. Metric {name} = {value:.3f} vs threshold {threshold:.3f}. "
                    f"This indicates unequal treatment of demographic groups."
                )
            elif "opportunity" in name.lower():
                return (
                    f"True positive rates differ across groups defined by '{sensitive}'. "
                    f"Metric {name} = {value:.3f} vs threshold {threshold:.3f}. "
                    f"The model is better at correctly identifying positive outcomes for some groups."
                )
            elif "odds" in name.lower():
                return (
                    f"Error rates (both false positives and false negatives) differ across groups "
                    f"defined by '{sensitive}'. Metric {name} = {value:.3f} vs threshold {threshold:.3f}."
                )
            return f"Fairness metric '{name}' failed: value {value} vs threshold {threshold}."

        elif principle == "privacy":
            if "pii" in name.lower():
                return "Personally Identifiable Information (PII) was detected in the dataset."
            elif "anonymity" in name.lower():
                return (
                    f"k-Anonymity check failed: some groups have fewer than {threshold} "
                    f"identical records, making individuals potentially identifiable."
                )
            elif "diversity" in name.lower():
                return (
                    f"l-Diversity check failed: some equivalence classes have fewer than "
                    f"{threshold} distinct sensitive values, risking attribute disclosure."
                )
            return f"Privacy metric '{name}' failed."

        elif principle == "transparency":
            return (
                f"Explainability metric '{name}' = {value}. "
                f"The model may not be sufficiently interpretable."
            )

        return f"Metric '{name}' failed: value {value} vs threshold {threshold}."

    @staticmethod
    def _generate_recommendation(
        result: ValidationResult, dataset: Optional[Dataset]
    ) -> str:
        """Generate an actionable recommendation for a failed metric."""
        name = result.metric_name
        principle = result.principle

        if principle == "fairness":
            sensitive = (
                ", ".join(dataset.sensitive_attributes)
                if dataset and dataset.sensitive_attributes
                else "the sensitive attribute"
            )
            if "parity" in name.lower() or "impact" in name.lower():
                return (
                    f"Consider applying fairness constraints (e.g., reweighing, "
                    f"threshold adjustment) targeting '{sensitive}' to achieve "
                    f"demographic parity."
                )
            elif "opportunity" in name.lower():
                return (
                    f"Retrain the model with equalized-opportunity constraints on "
                    f"'{sensitive}' to balance true positive rates across groups."
                )
            elif "odds" in name.lower():
                return (
                    f"Apply calibration or post-processing to equalize error rates "
                    f"across groups defined by '{sensitive}'."
                )
            return f"Review and address fairness for metric '{name}'."

        elif principle == "privacy":
            if "pii" in name.lower():
                return "Remove or anonymize columns containing PII before deploying the model."
            elif "anonymity" in name.lower():
                return "Generalize or suppress quasi-identifier columns to increase k-anonymity."
            elif "diversity" in name.lower():
                return "Apply data perturbation or generalization to improve l-diversity."
            return f"Address privacy concern for metric '{name}'."

        elif principle == "transparency":
            return (
                "Consider using a simpler, more interpretable model or adding "
                "SHAP/LIME explanation layers to improve transparency."
            )

        return f"Investigate and remediate the failure in metric '{name}'."
