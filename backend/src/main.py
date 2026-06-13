"""Main FastAPI application with middleware and exception handling."""

from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.events import EventBus, audit_event
from src.database import close_db, engine, init_db
from src.redis import redis_client


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler for startup/shutdown."""
    # Startup
    await init_db()
    await redis_client.connect()
    yield
    # Shutdown
    await redis_client.close()
    await close_db()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)


# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle validation errors with detailed messages."""
    errors = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error["loc"])
        errors.append(f"{loc}: {error['msg']}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": errors,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
        },
    )


# Health check endpoint
@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
    }


# Include routers
from src.api.admin import router as admin_router
from src.api.auth import router as auth_router
from src.api.coating import router as coating_router
from src.api.machines import router as machines_router
from src.api.packaging import router as packaging_router
from src.api.parts import router as parts_router
from src.api.price_accounts import router as price_accounts_router
from src.api.production import router as production_router
from src.api.quality import router as quality_router
from src.api.qr import router as qr_router
from src.api.quotes import router as quotes_router
from src.api.sampling_tasks import router as sampling_tasks_router
from src.api.toolings import router as toolings_router
from src.api.warehouse import router as warehouse_router

app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(coating_router, prefix=settings.API_V1_PREFIX)
app.include_router(machines_router, prefix=settings.API_V1_PREFIX)
app.include_router(packaging_router, prefix=settings.API_V1_PREFIX)
app.include_router(parts_router, prefix=settings.API_V1_PREFIX)
app.include_router(price_accounts_router, prefix=settings.API_V1_PREFIX)
app.include_router(production_router, prefix=settings.API_V1_PREFIX)
app.include_router(quality_router, prefix=settings.API_V1_PREFIX)
app.include_router(qr_router, prefix=settings.API_V1_PREFIX)
app.include_router(quotes_router, prefix=settings.API_V1_PREFIX)
app.include_router(sampling_tasks_router, prefix=settings.API_V1_PREFIX)
app.include_router(toolings_router, prefix=settings.API_V1_PREFIX)
app.include_router(warehouse_router, prefix=settings.API_V1_PREFIX)


# Root endpoint
@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs" if settings.DEBUG else "disabled",
    }
