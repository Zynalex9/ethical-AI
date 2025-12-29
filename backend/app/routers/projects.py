# Projects router - CRUD operations for projects

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from ..database import get_db
from ..dependencies import get_current_user
from ..models.user import User
from ..models.project import Project
from ..models.ml_model import MLModel
from ..models.dataset import Dataset
from ..models.requirement import Requirement
from ..models.audit_log import AuditLog, AuditAction, ResourceType
from ..schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all projects for the current user.
    Admins can see all projects, regular users see only their own.
    """
    query = select(Project).where(Project.deleted_at.is_(None))
    
    # Non-admin users only see their own projects
    if current_user.role.value != "admin":
        query = query.where(Project.owner_id == current_user.id)
    
    query = query.offset(skip).limit(limit).order_by(Project.created_at.desc())
    
    result = await db.execute(query)
    projects = result.scalars().all()
    
    # Get counts for each project
    response = []
    for project in projects:
        # Count models
        model_count = await db.scalar(
            select(func.count(MLModel.id)).where(MLModel.project_id == project.id)
        )
        # Count datasets
        dataset_count = await db.scalar(
            select(func.count(Dataset.id)).where(Dataset.project_id == project.id)
        )
        # Count requirements
        req_count = await db.scalar(
            select(func.count(Requirement.id)).where(Requirement.project_id == project.id)
        )
        
        response.append(ProjectResponse(
            id=project.id,
            name=project.name,
            description=project.description,
            owner_id=project.owner_id,
            created_at=project.created_at,
            updated_at=project.updated_at,
            model_count=model_count or 0,
            dataset_count=dataset_count or 0,
            requirement_count=req_count or 0
        ))
    
    return response


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new project."""
    project = Project(
        name=project_data.name,
        description=project_data.description,
        owner_id=current_user.id
    )
    
    db.add(project)
    await db.commit()
    await db.refresh(project)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_CREATE,
        resource_type=ResourceType.PROJECT,
        resource_id=project.id,
        details={"project_name": project.name}
    )
    db.add(audit)
    await db.commit()
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        model_count=0,
        dataset_count=0,
        requirement_count=0
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific project by ID."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get counts
    model_count = await db.scalar(
        select(func.count(MLModel.id)).where(MLModel.project_id == project.id)
    )
    dataset_count = await db.scalar(
        select(func.count(Dataset.id)).where(Dataset.project_id == project.id)
    )
    req_count = await db.scalar(
        select(func.count(Requirement.id)).where(Requirement.project_id == project.id)
    )
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        model_count=model_count or 0,
        dataset_count=dataset_count or 0,
        requirement_count=req_count or 0
    )


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: UUID,
    project_data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Update fields
    if project_data.name is not None:
        project.name = project_data.name
    if project_data.description is not None:
        project.description = project_data.description
    
    project.updated_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(project)
    
    # Get counts
    model_count = await db.scalar(
        select(func.count(MLModel.id)).where(MLModel.project_id == project.id)
    )
    dataset_count = await db.scalar(
        select(func.count(Dataset.id)).where(Dataset.project_id == project.id)
    )
    req_count = await db.scalar(
        select(func.count(Requirement.id)).where(Requirement.project_id == project.id)
    )
    
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        owner_id=project.owner_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        model_count=model_count or 0,
        dataset_count=dataset_count or 0,
        requirement_count=req_count or 0
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Soft delete a project."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check access
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Soft delete
    project.deleted_at = datetime.now(timezone.utc)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.PROJECT_DELETE,
        resource_type=ResourceType.PROJECT,
        resource_id=project.id,
        details={"project_name": project.name}
    )
    db.add(audit)
    
    await db.commit()
