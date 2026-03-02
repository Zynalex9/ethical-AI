# Templates router - Ethical requirement templates (Phase 5 – Domain Adaptation)

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import uuid as _uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..models.template import Template, TemplateDomain
from ..models.audit_log import AuditLog, AuditAction, ResourceType
from ..services.template_library import TemplateLibrary

router = APIRouter(prefix="/templates", tags=["templates"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class RuleItem(BaseModel):
    metric: str
    operator: str  # >=, <=, ==, >, <
    value: float
    principle: Optional[str] = "fairness"
    description: Optional[str] = None


class TemplateCreate(BaseModel):
    template_id: str  # e.g. "ETH1", "CUSTOM-001"
    name: str
    description: Optional[str] = None
    domain: str = "general"
    rules: Dict[str, Any]  # {"principles": [...], "reference": "...", "items": [...]}


class TemplateResponse(BaseModel):
    id: UUID
    template_id: str
    name: str
    description: Optional[str]
    domain: str
    rules: Dict[str, Any]
    version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ApplyTemplateRequest(BaseModel):
    project_id: UUID
    template_id: UUID
    customizations: Optional[Dict[str, Any]] = None


class CustomizeTemplateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    rule_overrides: Optional[List[Dict[str, Any]]] = None
    add_rules: Optional[List[Dict[str, Any]]] = None
    remove_indices: Optional[List[int]] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    principle: Optional[str] = Query(None, description="Filter by principle present in rules"),
    search: Optional[str] = Query(None, description="Search by name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active templates with optional filters."""
    if domain:
        templates = await TemplateLibrary.get_templates_by_domain(db, domain)
    elif principle:
        templates = await TemplateLibrary.get_templates_by_principle(db, principle)
    else:
        templates = await TemplateLibrary.get_all_templates(db)

    if search:
        search_lower = search.lower()
        templates = [t for t in templates if search_lower in (t.name or "").lower()]

    return templates


@router.get("/{tpl_id}", response_model=TemplateResponse)
async def get_template(
    tpl_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single template by UUID."""
    result = await db.execute(select(Template).where(Template.id == tpl_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new template."""
    template = Template(
        id=_uuid.uuid4(),
        template_id=data.template_id,
        name=data.name,
        description=data.description,
        domain=data.domain,
        rules=data.rules,
        version=1,
        is_active=True,
    )
    db.add(template)

    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.TEMPLATE_CREATE,
        resource_type=ResourceType.TEMPLATE,
        resource_id=template.id,
        details={"template_name": template.name},
    )
    db.add(audit)

    await db.commit()
    await db.refresh(template)
    return template


@router.delete("/{tpl_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    tpl_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a template. System templates (ETH*) cannot be deleted unless admin."""
    result = await db.execute(select(Template).where(Template.id == tpl_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Protect system templates for non-admins
    if (template.template_id or "").startswith("ETH") and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Cannot delete system templates")

    await db.delete(template)
    await db.commit()


# ---------------------------------------------------------------------------
# Apply template to project (6.5)
# ---------------------------------------------------------------------------

@router.post("/apply-to-project")
async def apply_template_to_project(
    body: ApplyTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Apply a template (optionally customised) to a project, creating requirements."""
    try:
        created = await TemplateLibrary.apply_template_to_project(
            db=db,
            project_id=body.project_id,
            template_id=body.template_id,
            user_id=current_user.id,
            customizations=body.customizations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.TEMPLATE_CREATE,
        resource_type=ResourceType.TEMPLATE,
        resource_id=body.template_id,
        details={"action": "apply_to_project", "project_id": str(body.project_id), "requirements_created": len(created)},
    )
    db.add(audit)
    await db.commit()

    return {
        "message": f"Created {len(created)} requirements from template",
        "requirements": [
            {
                "id": str(r.id),
                "name": r.name,
                "principle": r.principle.value if hasattr(r.principle, "value") else r.principle,
                "description": r.description,
                "specification": r.specification,
            }
            for r in created
        ],
    }


# ---------------------------------------------------------------------------
# Customize template (6.4 backend)
# ---------------------------------------------------------------------------

@router.post("/{tpl_id}/customize", response_model=TemplateResponse)
async def customize_template(
    tpl_id: UUID,
    body: CustomizeTemplateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clone & customise a template, returning the new copy."""
    modifications: Dict[str, Any] = {}
    if body.name:
        modifications["name"] = body.name
    if body.description:
        modifications["description"] = body.description
    if body.rule_overrides:
        modifications["rule_overrides"] = body.rule_overrides
    if body.add_rules:
        modifications["add_rules"] = body.add_rules
    if body.remove_indices:
        modifications["remove_indices"] = body.remove_indices

    try:
        clone = await TemplateLibrary.customize_template(db, tpl_id, modifications)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    return clone


# ---------------------------------------------------------------------------
# Seed domain templates (6.2 + 6.8)
# ---------------------------------------------------------------------------

# Complete domain-template catalogue
DOMAIN_TEMPLATES: List[Dict[str, Any]] = [
    # ── General (legacy) ─────────────────────────────────────────────
    {
        "template_id": "GEN-FAIRNESS",
        "name": "Fairness - General",
        "description": "Baseline fairness requirements suitable for any domain.",
        "domain": "general",
        "rules": {
            "principles": ["fairness"],
            "reference": "General best practices",
            "items": [
                {"metric": "demographic_parity_ratio", "operator": ">=", "value": 0.80, "principle": "fairness", "description": "Demographic parity ratio"},
                {"metric": "equalized_odds_ratio", "operator": ">=", "value": 0.80, "principle": "fairness", "description": "Equalized odds ratio"},
            ],
        },
    },
    {
        "template_id": "GEN-TRANSPARENCY",
        "name": "Transparency - General",
        "description": "General model transparency requirements.",
        "domain": "general",
        "rules": {
            "principles": ["transparency"],
            "reference": "General best practices",
            "items": [
                {"metric": "shap_coverage", "operator": ">=", "value": 1.0, "principle": "transparency", "description": "Full SHAP coverage"},
            ],
        },
    },
    {
        "template_id": "GEN-PRIVACY",
        "name": "Privacy - PII Protection",
        "description": "Ensure no PII columns are present in the dataset.",
        "domain": "general",
        "rules": {
            "principles": ["privacy"],
            "reference": "General best practices",
            "items": [
                {"metric": "pii_count", "operator": "==", "value": 0, "principle": "privacy", "description": "Zero PII columns allowed"},
            ],
        },
    },
    # ── ETH1: Financial Services ─────────────────────────────────────
    {
        "template_id": "ETH1",
        "name": "ETH1: Financial Services (Lending & Credit)",
        "description": (
            "Fair lending requirements based on the 80 % rule from US fair lending laws. "
            "Covers demographic parity, disparate impact, and equal opportunity for credit "
            "scoring and loan-approval models."
        ),
        "domain": "finance",
        "rules": {
            "principles": ["fairness"],
            "reference": "Equal Credit Opportunity Act (ECOA), Fair Housing Act",
            "items": [
                {"metric": "demographic_parity_ratio", "operator": ">=", "value": 0.80, "principle": "fairness", "description": "80 % rule for demographic parity"},
                {"metric": "disparate_impact_ratio", "operator": ">=", "value": 0.80, "principle": "fairness", "description": "Disparate impact ratio ≥ 0.80"},
                {"metric": "equal_opportunity_difference", "operator": "<=", "value": 0.05, "principle": "fairness", "description": "Equal opportunity difference ≤ 0.05"},
            ],
        },
    },
    # ── ETH2: Healthcare ─────────────────────────────────────────────
    {
        "template_id": "ETH2",
        "name": "ETH2: Healthcare (Medical Diagnosis)",
        "description": (
            "Very strict fairness and full explainability requirements for medical AI. "
            "Every prediction must be explainable (100 % SHAP coverage) and a model card is required."
        ),
        "domain": "healthcare",
        "rules": {
            "principles": ["fairness", "transparency"],
            "reference": "HIPAA, FDA guidelines for AI/ML in medical devices",
            "items": [
                {"metric": "equal_opportunity_difference", "operator": "<=", "value": 0.03, "principle": "fairness", "description": "Very strict – healthcare critical"},
                {"metric": "shap_coverage", "operator": ">=", "value": 1.0, "principle": "transparency", "description": "100 % SHAP coverage – every prediction explainable"},
                {"metric": "model_card_completeness", "operator": ">=", "value": 1.0, "principle": "transparency", "description": "Model card required"},
            ],
        },
    },
    # ── ETH3: Criminal Justice ───────────────────────────────────────
    {
        "template_id": "ETH3",
        "name": "ETH3: Criminal Justice (Risk Assessment)",
        "description": (
            "Equalized-odds-focused requirements for recidivism and risk-assessment models. "
            "Equal TPR and FPR across races with calibration and audit trail."
        ),
        "domain": "criminal_justice",
        "rules": {
            "principles": ["fairness", "accountability"],
            "reference": "ProPublica COMPAS analysis standards",
            "items": [
                {"metric": "equalized_odds_ratio", "operator": ">=", "value": 0.85, "principle": "fairness", "description": "Equal TPR and FPR across races"},
                {"metric": "calibration_difference", "operator": "<=", "value": 0.05, "principle": "fairness", "description": "Calibration within ±5 % across groups"},
                {"metric": "audit_trail_required", "operator": "==", "value": 1.0, "principle": "accountability", "description": "Audit trail required"},
            ],
        },
    },
    # ── ETH4: Employment ─────────────────────────────────────────────
    {
        "template_id": "ETH4",
        "name": "ETH4: Employment (Hiring & Promotion)",
        "description": (
            "EEOC-compliant requirements for hiring and promotion AI. "
            "Enforces the four-fifths rule, demographic parity, and PII exclusion."
        ),
        "domain": "employment",
        "rules": {
            "principles": ["fairness"],
            "reference": "EEOC Uniform Guidelines on Employee Selection",
            "items": [
                {"metric": "demographic_parity_ratio", "operator": ">=", "value": 0.80, "principle": "fairness", "description": "Demographic parity ≥ 0.80"},
                {"metric": "four_fifths_rule", "operator": ">=", "value": 0.80, "principle": "fairness", "description": "Four-fifths rule compliance"},
                {"metric": "pii_in_features", "operator": "==", "value": 0, "principle": "fairness", "description": "No PII in features (except required by law)"},
            ],
        },
    },
    # ── ETH5: GDPR ───────────────────────────────────────────────────
    {
        "template_id": "ETH5",
        "name": "ETH5: GDPR Compliance (EU)",
        "description": (
            "Privacy and transparency requirements under GDPR Article 22. "
            "Requires right-to-explanation, no PII without consent, and k-anonymity."
        ),
        "domain": "general",
        "rules": {
            "principles": ["privacy", "transparency"],
            "reference": "GDPR Article 22 (automated decision-making)",
            "items": [
                {"metric": "pii_without_consent", "operator": "==", "value": 0, "principle": "privacy", "description": "No PII without consent"},
                {"metric": "shap_coverage", "operator": ">=", "value": 1.0, "principle": "transparency", "description": "Right to explanation (SHAP required)"},
                {"metric": "k_anonymity", "operator": ">=", "value": 5, "principle": "privacy", "description": "k-anonymity ≥ 5"},
            ],
        },
    },
    # ── ETH6: Education ──────────────────────────────────────────────
    {
        "template_id": "ETH6",
        "name": "ETH6: Education (Admissions)",
        "description": (
            "Fairness and transparency requirements for admissions and academic-placement AI. "
            "Explanation required for rejection decisions."
        ),
        "domain": "education",
        "rules": {
            "principles": ["fairness", "transparency"],
            "reference": "Title VI of Civil Rights Act",
            "items": [
                {"metric": "demographic_parity_ratio", "operator": ">=", "value": 0.75, "principle": "fairness", "description": "Demographic parity ≥ 0.75"},
                {"metric": "equal_opportunity_difference", "operator": "<=", "value": 0.10, "principle": "fairness", "description": "Equal opportunity difference ≤ 0.10"},
                {"metric": "explanation_required", "operator": "==", "value": 1.0, "principle": "transparency", "description": "Explanation required for rejections"},
            ],
        },
    },
]


@router.post("/seed-defaults", status_code=status.HTTP_201_CREATED)
async def seed_default_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Seed / upsert the full catalogue of domain templates (admin only)."""
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Only admins can seed templates")
    return await _seed_templates(db)


async def _seed_templates(db: AsyncSession) -> Dict[str, Any]:
    """Internal helper so we can call this from app startup too."""
    created_count = 0
    updated_count = 0

    for t_data in DOMAIN_TEMPLATES:
        result = await db.execute(
            select(Template).where(Template.template_id == t_data["template_id"])
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            tpl = Template(
                id=_uuid.uuid4(),
                template_id=t_data["template_id"],
                name=t_data["name"],
                description=t_data["description"],
                domain=t_data["domain"],
                rules=t_data["rules"],
                version=1,
                is_active=True,
            )
            db.add(tpl)
            created_count += 1
        else:
            # Update existing template if version changed
            if existing.rules != t_data["rules"] or existing.name != t_data["name"]:
                existing.name = t_data["name"]
                existing.description = t_data["description"]
                existing.domain = t_data["domain"]
                existing.rules = t_data["rules"]
                existing.version = (existing.version or 1) + 1
                updated_count += 1

    await db.commit()
    return {"message": f"Seeded {created_count} new, updated {updated_count} templates"}
