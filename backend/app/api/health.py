"""Compatibility imports for existing health clients and overrides."""
from app.modules.health.router import router, get_health_service

__all__ = ["router", "get_health_service"]
