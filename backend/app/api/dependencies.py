"""
Role-Based Access Control (RBAC) dependency for FastAPI.

Usage:
    - Clients send the `X-Role` header with one of: "ambulance", "hospital", "admin"
    - Each portal endpoint declares which role(s) are allowed
    - If the header is missing, access is DENIED (secure by default)
    - If the role doesn't match, a 403 Forbidden is returned

This is a lightweight, header-based RBAC suitable for internal/trusted
services. For production, replace with JWT/OAuth2 token-based auth.
"""

import logging
from typing import List

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

# Valid roles in the system
VALID_ROLES = {"ambulance", "hospital", "admin"}


def _check_role(x_role: str, allowed_roles: List[str]) -> str:
    """
    Core role validation logic.

    Args:
        x_role: The role claimed by the client via X-Role header
        allowed_roles: List of roles permitted to access this endpoint

    Returns:
        The validated role string (lowercase)

    Raises:
        HTTPException 401: If no role header is provided
        HTTPException 403: If the role is not in the allowed list
    """
    if not x_role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Role header. Provide one of: ambulance, hospital, admin"
        )

    role = x_role.strip().lower()

    if role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid role: '{x_role}'. Valid roles: {', '.join(sorted(VALID_ROLES))}"
        )

    if role not in allowed_roles:
        logger.warning(f"Access denied: role '{role}' tried to access endpoint restricted to {allowed_roles}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Role '{role}' is not authorized for this endpoint. Required: {', '.join(allowed_roles)}"
        )

    return role


def require_ambulance_role(x_role: str = Header(default="")) -> str:
    """
    Dependency: ensures the caller has the 'ambulance' or 'admin' role.
    Admin can access all portals.
    """
    return _check_role(x_role, ["ambulance", "admin"])


def require_hospital_role(x_role: str = Header(default="")) -> str:
    """
    Dependency: ensures the caller has the 'hospital' or 'admin' role.
    Admin can access all portals.
    """
    return _check_role(x_role, ["hospital", "admin"])


def require_admin_role(x_role: str = Header(default="")) -> str:
    """
    Dependency: ensures the caller has the 'admin' role.
    Only admins can create hospitals and manage system-level data.
    """
    return _check_role(x_role, ["admin"])
