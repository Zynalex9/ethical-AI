# Templates router - Ethical requirement templates

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..models.template import Template
from ..models.audit_log import AuditLog, AuditAction, ResourceType

router = APIRouter(prefix="/templates", tags=["templates"])


# Pydantic schemas
class ThresholdRule(BaseModel):
    metric: str
    operator: str  # >=, <=, ==, >, <
    value: float
    description: Optional[str] = None


class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    principle: str  # fairness, transparency, privacy, accountability
    category: Optional[str] = None  # finance, healthcare, hiring, etc.
    rules: List[ThresholdRule]
    is_system: bool = False


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    principle: str
    category: Optional[str]
    rules: List[Dict[str, Any]]
    is_system: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[TemplateResponse])
async def list_templates(
    principle: Optional[str] = None,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all available templates, optionally filtered by principle or category."""
    query = select(Template)
    
    if principle:
        query = query.where(Template.principle == principle)
    if category:
        query = query.where(Template.category == category)
    
    query = query.order_by(Template.name)
    
    result = await db.execute(query)
    templates = result.scalars().all()
    
    return templates


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific template by ID."""
    result = await db.execute(
        select(Template).where(Template.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template


@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new template."""
    # Convert rules to dict list
    rules_dict = [r.model_dump() for r in template_data.rules]
    
    template = Template(
        name=template_data.name,
        description=template_data.description,
        principle=template_data.principle,
        category=template_data.category,
        rules=rules_dict,
        is_system=template_data.is_system,
        created_by_id=current_user.id
    )
    
    db.add(template)
    await db.commit()
    await db.refresh(template)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.TEMPLATE_CREATE,
        resource_type=ResourceType.TEMPLATE,
        resource_id=template.id,
        details={"template_name": template.name}
    )
    db.add(audit)
    await db.commit()
    
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a template (only non-system templates)."""
    result = await db.execute(
        select(Template).where(Template.id == template_id)
    )
    template = result.scalar_one_or_none()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    if template.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system templates")
    
    await db.delete(template)
    await db.commit()


@router.post("/seed-defaults", status_code=status.HTTP_201_CREATED)
async def seed_default_templates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Seed the database with default ethical requirement templates."""
    if current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Only admins can seed templates")
    
    default_templates = [
        {
            "name": "Fairness - Finance (80% Rule)",
            "description": "Standard fairness requirements for financial services following the 4/5ths rule",
            "principle": "fairness",
            "category": "finance",
            "is_system": True,
            "rules": [
                {"metric": "demographic_parity_ratio", "operator": ">=", "value": 0.8, "description": "80% rule for demographic parity"},
                {"metric": "equalized_odds_ratio", "operator": ">=", "value": 0.8, "description": "Equalized odds ratio threshold"},
                {"metric": "disparate_impact_ratio", "operator": ">=", "value": 0.8, "description": "Disparate impact ratio"},
            ]
        },
        {
            "name": "Fairness - Healthcare",
            "description": "Strict fairness requirements for healthcare AI systems",
            "principle": "fairness",
            "category": "healthcare",
            "is_system": True,
            "rules": [
                {"metric": "demographic_parity_ratio", "operator": ">=", "value": 0.9, "description": "Higher threshold for healthcare"},
                {"metric": "equalized_odds_ratio", "operator": ">=", "value": 0.9, "description": "Equal opportunity in healthcare"},
                {"metric": "equal_opportunity_difference", "operator": "<=", "value": 0.05, "description": "Minimal opportunity gap"},
            ]
        },
        {
            "name": "Transparency - General",
            "description": "General transparency requirements",
            "principle": "transparency",
            "category": "general",
            "is_system": True,
            "rules": [
                {"metric": "shap_coverage", "operator": ">=", "value": 1.0, "description": "Full SHAP coverage"},
            ]
        },
        {
            "name": "Privacy - PII Protection",
            "description": "Ensure no PII is leaked",
            "principle": "privacy",
            "category": "general",
            "is_system": True,
            "rules": [
                {"metric": "pii_count", "operator": "==", "value": 0, "description": "Zero PII allowed"},
            ]
        }
    ]
    
    created_count = 0
    for t_data in default_templates:
        # Check if exists
        exists = await db.scalar(select(Template).where(Template.name == t_data["name"]))
        if not exists:
            tpl = Template(
                name=t_data["name"],
                description=t_data["description"],
                principle=t_data["principle"],
                category=t_data["category"],
                rules=t_data["rules"],
                is_system=t_data["is_system"],
                created_by_id=current_user.id
            )
            db.add(tpl)
            created_count += 1
            
    await db.commit()
    return {"message": f"Seeded {created_count} templates"}
