import secrets

from fastapi import Header, HTTPException, status

from src.config.settings import get_settings


def require_admin(x_admin_key: str | None = Header(default=None)) -> None:
    """Protect document-management operations with a constant-time key check."""
    # Settings are cached for the lifetime of each server process.
    configured = get_settings().admin_api_key
    if not configured or configured == "change_this_admin_key":
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "La clave administrativa no está configurada")
    if not x_admin_key or not secrets.compare_digest(x_admin_key, configured):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credencial administrativa inválida")
