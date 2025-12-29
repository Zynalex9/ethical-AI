# Models router - ML model upload and management

import os
import shutil
from typing import List, Optional
from uuid import UUID
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..database import get_db
from ..dependencies import get_current_user
from ..config import settings
from ..models.user import User
from ..models.project import Project
from ..models.ml_model import MLModel, ModelType
from ..models.audit_log import AuditLog, AuditAction, ResourceType
from ..services.model_loader import UniversalModelLoader

router = APIRouter(prefix="/models", tags=["models"])


# Pydantic models for responses
from pydantic import BaseModel

class ModelResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: Optional[str]
    file_path: str
    file_size: int
    model_type: str
    model_metadata: dict
    version: str
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


def get_model_type_from_extension(filename: str) -> ModelType:
    """Determine model type from file extension."""
    ext = Path(filename).suffix.lower()
    mapping = {
        '.pkl': ModelType.SKLEARN,
        '.joblib': ModelType.SKLEARN,
        '.pickle': ModelType.SKLEARN,
        '.h5': ModelType.TENSORFLOW,
        '.keras': ModelType.TENSORFLOW,
        '.pt': ModelType.PYTORCH,
        '.pth': ModelType.PYTORCH,
        '.onnx': ModelType.ONNX,
    }
    return mapping.get(ext, ModelType.UNKNOWN)


@router.post("/upload", response_model=ModelResponse, status_code=status.HTTP_201_CREATED)
async def upload_model(
    file: UploadFile = File(...),
    name: str = Form(...),
    project_id: UUID = Form(...),
    description: Optional[str] = Form(None),
    version: str = Form("1.0.0"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload an ML model file.
    
    Supported formats:
    - scikit-learn: .pkl, .joblib, .pickle
    - TensorFlow/Keras: .h5, .keras
    - PyTorch: .pt, .pth
    - ONNX: .onnx
    """
    # Verify project exists and user has access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Validate file extension
    ext = Path(file.filename).suffix.lower()
    allowed_extensions = {'.pkl', '.joblib', '.pickle', '.h5', '.keras', '.pt', '.pth', '.onnx'}
    
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Create upload directory
    upload_dir = Path(settings.upload_dir) / "models" / str(project_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c for c in name if c.isalnum() or c in "._-")
    filename = f"{safe_name}_{timestamp}{ext}"
    file_path = upload_dir / filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Get file size
    file_size = os.path.getsize(file_path)
    
    # Try to load and extract metadata
    model_metadata = {}
    try:
        loaded_model = UniversalModelLoader.load(str(file_path))
        model_metadata = UniversalModelLoader.get_model_metadata(loaded_model)
    except Exception as e:
        model_metadata = {"load_warning": str(e)}
    
    # Create database record
    ml_model = MLModel(
        project_id=project_id,
        name=name,
        description=description,
        file_path=str(file_path),
        file_size=file_size,
        model_type=get_model_type_from_extension(file.filename),
        model_metadata=model_metadata,
        version=version,
        uploaded_by_id=current_user.id
    )
    
    db.add(ml_model)
    await db.commit()
    await db.refresh(ml_model)
    
    # Audit log
    audit = AuditLog(
        user_id=current_user.id,
        action=AuditAction.MODEL_UPLOAD,
        resource_type=ResourceType.MODEL,
        resource_id=ml_model.id,
        details={
            "model_name": name,
            "file_size": file_size,
            "model_type": ml_model.model_type.value
        }
    )
    db.add(audit)
    await db.commit()
    
    return ModelResponse(
        id=ml_model.id,
        project_id=ml_model.project_id,
        name=ml_model.name,
        description=ml_model.description,
        file_path=ml_model.file_path,
        file_size=ml_model.file_size,
        model_type=ml_model.model_type.value,
        model_metadata=ml_model.model_metadata or {},
        version=ml_model.version,
        uploaded_at=ml_model.uploaded_at
    )


@router.get("/project/{project_id}", response_model=List[ModelResponse])
async def list_models(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all models in a project."""
    # Verify project access
    result = await db.execute(
        select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get models
    result = await db.execute(
        select(MLModel).where(MLModel.project_id == project_id).order_by(MLModel.uploaded_at.desc())
    )
    models = result.scalars().all()
    
    return [
        ModelResponse(
            id=m.id,
            project_id=m.project_id,
            name=m.name,
            description=m.description,
            file_path=m.file_path,
            file_size=m.file_size,
            model_type=m.model_type.value,
            model_metadata=m.model_metadata or {},
            version=m.version,
            uploaded_at=m.uploaded_at
        )
        for m in models
    ]


@router.get("/{model_id}", response_model=ModelResponse)
async def get_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific model by ID."""
    result = await db.execute(
        select(MLModel).where(MLModel.id == model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check project access
    result = await db.execute(
        select(Project).where(Project.id == model.project_id)
    )
    project = result.scalar_one_or_none()
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return ModelResponse(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        description=model.description,
        file_path=model.file_path,
        file_size=model.file_size,
        model_type=model.model_type.value,
        model_metadata=model.model_metadata or {},
        version=model.version,
        uploaded_at=model.uploaded_at
    )


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(
    model_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a model."""
    result = await db.execute(
        select(MLModel).where(MLModel.id == model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    
    # Check project access
    result = await db.execute(
        select(Project).where(Project.id == model.project_id)
    )
    project = result.scalar_one_or_none()
    
    if current_user.role.value != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Delete file
    try:
        if os.path.exists(model.file_path):
            os.remove(model.file_path)
    except Exception:
        pass  # Continue even if file deletion fails
    
    # Delete record
    await db.delete(model)
    await db.commit()
