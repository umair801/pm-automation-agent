"""
Health check endpoint for deployment monitoring.
"""

from fastapi import APIRouter
from app.utils.config import settings

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check() -> dict:
    """Returns system health status. Used by Railway and monitoring tools."""
    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "version": "1.0.0",
        "project": "PM Automation Agent",
        "brand": "Datawebify",
    }