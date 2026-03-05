"""
FastAPI application entry point with CORS, middleware, and router registration.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.database import init_db, close_db, create_engine_and_session
from app import database
from app.routers import auth, projects, models, datasets, validation, templates, audit, requirements, traceability, reports, admin, notifications, remediation
from app.middleware.logging_config import setup_logging, get_logger
from app.middleware.error_handler import (
    AppError,
    RequestIdMiddleware,
    app_error_handler,
    validation_exception_handler,
    general_exception_handler,
)
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware

# ---------- Initialise structured logging ----------
setup_logging(json_output=not settings.debug, level="DEBUG" if settings.debug else "INFO")
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    await init_db()
    logger.info("Database initialized")

    # Auto-seed domain templates (Phase 5 – 6.8)
    try:
        from app.routers.templates import _seed_templates
        create_engine_and_session()
        async with database.async_session_maker() as db:
            result = await _seed_templates(db)
            logger.info("Template seeding: %s", result.get("message", "done"))
    except Exception as exc:
        logger.warning("Template seeding skipped: %s", exc)
    
    yield
    
    # Shutdown
    await close_db()
    logger.info("Database connections closed")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A platform for operationalizing ethical principles in AI systems",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# ---------- Middleware (order matters: outermost first) ----------
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=100)
app.add_middleware(RequestIdMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# ---------- Exception handlers ----------
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, general_exception_handler)  # type: ignore[arg-type]


# Register routers
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(projects.router, prefix=settings.api_prefix)
app.include_router(models.router, prefix=settings.api_prefix)
app.include_router(datasets.router, prefix=settings.api_prefix)
app.include_router(validation.router, prefix=settings.api_prefix)
app.include_router(templates.router, prefix=settings.api_prefix)
app.include_router(audit.router, prefix=settings.api_prefix)
app.include_router(requirements.router, prefix=settings.api_prefix)
app.include_router(traceability.router, prefix=settings.api_prefix)
app.include_router(reports.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(notifications.router, prefix=settings.api_prefix)
app.include_router(remediation.router, prefix=settings.api_prefix)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """
    Health check endpoint for monitoring.
    
    Returns:
        Status information
    """
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version
    }


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> dict:
    """
    Root endpoint with API information.
    
    Returns:
        API information and available endpoints
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "documentation": "/docs",
        "health": "/health",
        "api_prefix": settings.api_prefix
    }
