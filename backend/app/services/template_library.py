"""
Template Library Service – Phase 5
Provides helpers to query, customise, and apply domain-specific
ethical-requirement templates to projects.
"""

from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.template import Template, TemplateDomain
from app.models.requirement import Requirement, EthicalPrinciple, RequirementStatus


class TemplateLibrary:
    """Stateless helper – every public method receives its own ``AsyncSession``."""

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def get_all_templates(db: AsyncSession) -> List[Template]:
        """Return every active template."""
        result = await db.execute(
            select(Template)
            .where(Template.is_active == True)
            .order_by(Template.template_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_templates_by_domain(db: AsyncSession, domain: str) -> List[Template]:
        """Filter active templates by domain string."""
        result = await db.execute(
            select(Template)
            .where(Template.domain == domain, Template.is_active == True)
            .order_by(Template.template_id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_templates_by_principle(db: AsyncSession, principle: str) -> List[Template]:
        """Return templates whose rules reference a given principle."""
        all_templates = await TemplateLibrary.get_all_templates(db)
        matched: List[Template] = []
        for tpl in all_templates:
            rules = tpl.rules or {}
            principles = rules.get("principles", [])
            if principle in principles:
                matched.append(tpl)
        return matched

    # ------------------------------------------------------------------
    # Apply template → create requirements
    # ------------------------------------------------------------------

    @staticmethod
    async def apply_template_to_project(
        db: AsyncSession,
        project_id: UUID,
        template_id: UUID,
        user_id: Optional[UUID] = None,
        customizations: Optional[Dict[str, Any]] = None,
    ) -> List[Requirement]:
        """
        Load *template*, optionally overlay *customizations*, then create
        one ``Requirement`` row per rule-item and attach them to the project.
        Returns the list of newly-created requirements.
        """
        result = await db.execute(select(Template).where(Template.id == template_id))
        template = result.scalar_one_or_none()
        if template is None:
            raise ValueError("Template not found")

        rules: Dict[str, Any] = copy.deepcopy(template.rules or {})

        # Apply customizations (override thresholds / add / remove rules)
        if customizations:
            rules = TemplateLibrary._apply_customizations(rules, customizations)

        items: List[Dict[str, Any]] = rules.get("items", [])
        reference: str = rules.get("reference", "")
        template_display = template.template_id or template.name

        created: List[Requirement] = []
        for item in items:
            principle_str = item.get("principle", "fairness")
            try:
                principle = EthicalPrinciple(principle_str)
            except ValueError:
                principle = EthicalPrinciple.FAIRNESS

            req = Requirement(
                id=uuid.uuid4(),
                project_id=project_id,
                name=f"{item.get('metric', 'Unknown')} ({template_display})",
                description=(
                    f"{item.get('description', '')}. "
                    f"Source template: {template.name}. "
                    f"Reference: {reference}"
                ).strip(),
                principle=principle,
                specification={
                    "rules": [
                        {
                            "metric": item.get("metric", ""),
                            "operator": item.get("operator", ">="),
                            "value": item.get("value", 0),
                            "description": item.get("description", ""),
                        }
                    ]
                },
                based_on_template_id=template.id,
                status=RequirementStatus.ACTIVE,
                version=1,
                elicited_automatically=False,
                elicitation_reason=f"Applied from template: {template.name}",
                confidence_score=1.0,
                created_by_id=user_id,
            )
            db.add(req)
            created.append(req)

        await db.commit()
        for r in created:
            await db.refresh(r)
        return created

    # ------------------------------------------------------------------
    # Customise (clone + modify)
    # ------------------------------------------------------------------

    @staticmethod
    async def customize_template(
        db: AsyncSession,
        template_id: UUID,
        modifications: Dict[str, Any],
    ) -> Template:
        """
        Clone an existing template, apply *modifications*, and persist
        the clone as a new (user-level) template.
        """
        result = await db.execute(select(Template).where(Template.id == template_id))
        original = result.scalar_one_or_none()
        if original is None:
            raise ValueError("Template not found")

        new_rules = copy.deepcopy(original.rules or {})
        new_rules = TemplateLibrary._apply_customizations(new_rules, modifications)

        clone = Template(
            id=uuid.uuid4(),
            template_id=f"{original.template_id}-custom-{uuid.uuid4().hex[:6]}",
            name=modifications.get("name", f"{original.name} (Custom)"),
            description=modifications.get("description", original.description),
            domain=original.domain,
            rules=new_rules,
            version=1,
            is_active=True,
        )
        db.add(clone)
        await db.commit()
        await db.refresh(clone)
        return clone

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_customizations(
        rules: Dict[str, Any],
        customizations: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Merge *customizations* into *rules* dict.

        Supported keys in *customizations*:
        - ``rule_overrides``: list of ``{"index": int, "value": float, ...}``
        - ``add_rules``: list of new rule dicts to append
        - ``remove_indices``: list of int indices to remove
        """
        items: List[Dict[str, Any]] = rules.get("items", [])

        # 1. Override existing rule thresholds / fields
        for override in customizations.get("rule_overrides", []):
            idx = override.get("index")
            if idx is not None and 0 <= idx < len(items):
                for key in ("value", "operator", "metric", "description", "principle"):
                    if key in override:
                        items[idx][key] = override[key]

        # 2. Remove rules (reverse order to keep indices stable)
        for idx in sorted(customizations.get("remove_indices", []), reverse=True):
            if 0 <= idx < len(items):
                items.pop(idx)

        # 3. Append new rules
        for new_rule in customizations.get("add_rules", []):
            items.append(new_rule)

        rules["items"] = items
        return rules
