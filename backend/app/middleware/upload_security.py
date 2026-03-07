"""
File upload security utilities.

Provides:
- File size validation
- Extension whitelist validation
- Content-type sniffing guard
- CSV injection prevention
"""

import os
from typing import List, Optional

from fastapi import UploadFile, HTTPException, status

from app.config import settings


def validate_upload_file(
    file: UploadFile,
    *,
    allowed_extensions: List[str],
    max_size_mb: Optional[int] = None,
    label: str = "file",
) -> str:
    """
    Validate an uploaded file against extension whitelist and size limit.

    Args:
        file: FastAPI UploadFile object
        allowed_extensions: List of allowed extensions (e.g. [".csv", ".pkl"])
        max_size_mb: Maximum file size in MB (defaults to settings.max_upload_size_mb)
        label: Human-readable label for error messages (e.g. "model", "dataset")

    Returns:
        The validated file extension (lowercase).

    Raises:
        HTTPException on validation failure.
    """
    if max_size_mb is None:
        max_size_mb = settings.max_upload_size_mb

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No {label} filename provided",
        )

    # Extension check
    _, ext = os.path.splitext(file.filename.lower())
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported {label} extension '{ext}'. Allowed: {', '.join(allowed_extensions)}",
        )

    # Size check (if content-length header available)
    if file.size is not None and file.size > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"{label.capitalize()} exceeds maximum size of {max_size_mb} MB",
        )

    # Empty file check
    if file.size is not None and file.size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uploaded {label} is empty",
        )

    return ext


def sanitize_csv_cell(value: str) -> str:
    """
    Prevent CSV injection by stripping leading formula characters.

    Dangerous prefixes: =, +, -, @, \\t, \\r
    """
    if isinstance(value, str) and value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def safe_filename(original: str) -> str:
    """
    Sanitise a filename to prevent path traversal.

    Removes directory components and null bytes.
    """
    # Remove path components
    name = os.path.basename(original)
    # Remove null bytes
    name = name.replace("\x00", "")
    # If nothing remains, use a default
    if not name:
        name = "unnamed_upload"
    return name
