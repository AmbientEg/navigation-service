import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


security = HTTPBearer(auto_error=True)


def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Simple Bearer token guard for admin CRUD routes."""
    expected = os.getenv("ADMIN_API_TOKEN")

    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API token is not configured",
        )

    if not secrets.compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )

    return True
