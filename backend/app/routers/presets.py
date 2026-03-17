# Validation Presets router — CRUD for saved validation configurations

from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..dependencies import get_current_user
from ..middleware.logging_config import get_logger
from ..models.project import Project
from ..models.user import User
from ..models.validation_preset import ValidationPreset

logger = get_logger("routers.presets")
router = APIRouter(prefix="/presets", tags=["presets"])


class ValidationPresetCreate(BaseModel):
    project_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    config: Dict[str, Any]


class ValidationPresetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    config: Dict[str, Any] | None = None


class ValidationPresetResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    config: Dict[str, Any]
    created_by_id: UUID
    created_at: str

    model_config = {"from_attributes": True}


async def _verify_project_access(db: AsyncSession, current_user: User, project_id: UUID) -> None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")


def _normalize_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="Preset name cannot be empty")
    return normalized


async def _ensure_unique_name(
    db: AsyncSession,
    *,
    project_id: UUID,
    created_by_id: UUID,
    name: str,
    exclude_id: UUID | None = None,
) -> None:
    query = select(ValidationPreset).where(
        ValidationPreset.project_id == project_id,
        ValidationPreset.created_by_id == created_by_id,
        ValidationPreset.name == name,
    )
    if exclude_id is not None:
        query = query.where(ValidationPreset.id != exclude_id)

    existing = (await db.execute(query)).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail=f"Preset '{name}' already exists")


@router.post("", response_model=ValidationPresetResponse, status_code=status.HTTP_201_CREATED)
async def create_preset(
    body: ValidationPresetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_project_access(db, current_user, body.project_id)
    preset_name = _normalize_name(body.name)
    await _ensure_unique_name(
        db,
        project_id=body.project_id,
        created_by_id=current_user.id,
        name=preset_name,
    )

    preset = ValidationPreset(
        project_id=body.project_id,
        name=preset_name,
        config=body.config,
        created_by_id=current_user.id,
    )
    db.add(preset)
    await db.commit()
    await db.refresh(preset)
    logger.info("Validation preset created: id=%s project=%s", preset.id, body.project_id)
    return ValidationPresetResponse(
        id=preset.id,
        project_id=preset.project_id,
        name=preset.name,
        config=preset.config,
        created_by_id=preset.created_by_id,
        created_at=preset.created_at.isoformat(),
    )


@router.get("", response_model=List[ValidationPresetResponse])
async def list_presets(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _verify_project_access(db, current_user, project_id)
    result = await db.execute(
        select(ValidationPreset)
        .where(
            ValidationPreset.project_id == project_id,
            ValidationPreset.created_by_id == current_user.id,
        )
        .order_by(ValidationPreset.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        ValidationPresetResponse(
            id=row.id,
            project_id=row.project_id,
            name=row.name,
            config=row.config,
            created_by_id=row.created_by_id,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]


@router.put("/{preset_id}", response_model=ValidationPresetResponse)
async def update_preset(
    preset_id: UUID,
    body: ValidationPresetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ValidationPreset).where(ValidationPreset.id == preset_id))
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    await _verify_project_access(db, current_user, preset.project_id)
    if preset.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Can only update your own presets")

    if body.name is not None:
        normalized_name = _normalize_name(body.name)
        await _ensure_unique_name(
            db,
            project_id=preset.project_id,
            created_by_id=current_user.id,
            name=normalized_name,
            exclude_id=preset.id,
        )
        preset.name = normalized_name
    if body.config is not None:
        preset.config = body.config

    await db.commit()
    await db.refresh(preset)
    logger.info("Validation preset updated: id=%s", preset.id)
    return ValidationPresetResponse(
        id=preset.id,
        project_id=preset.project_id,
        name=preset.name,
        config=preset.config,
        created_by_id=preset.created_by_id,
        created_at=preset.created_at.isoformat(),
    )


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_preset(
    preset_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(ValidationPreset).where(ValidationPreset.id == preset_id))
    preset = result.scalar_one_or_none()
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    await _verify_project_access(db, current_user, preset.project_id)
    if preset.created_by_id != current_user.id:
        raise HTTPException(status_code=403, detail="Can only delete your own presets")

    await db.delete(preset)
    await db.commit()
    logger.info("Validation preset deleted: id=%s", preset_id)
