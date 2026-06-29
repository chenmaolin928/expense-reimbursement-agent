"""Dependency injection for FastAPI routers.

Token-based simulated auth: tokens are of format "sim_{role}_{user_id}_{random}"
and are parsed from the Authorization header.
"""

from typing import Annotated
from fastapi import Depends, Header, HTTPException


def _parse_auth_header(authorization: Annotated[str | None, Header()] = None) -> dict:
    """Parse simulated token from Authorization header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录，请先登录")

    token = authorization.removeprefix("Bearer ").strip()
    if not token.startswith("sim_"):
        raise HTTPException(status_code=401, detail="无效的认证令牌")

    parts = token.split("_")
    if len(parts) < 3:
        raise HTTPException(status_code=401, detail="令牌格式无效")

    return {"role": parts[1], "user_id": int(parts[2])}


def get_current_user(auth: dict = Depends(_parse_auth_header)) -> dict:
    """FastAPI dependency: returns current user info from token."""
    return auth


def get_current_user_id(auth: dict = Depends(_parse_auth_header)) -> int:
    """FastAPI dependency: returns current user ID from token."""
    return auth["user_id"]


def get_current_user_role(auth: dict = Depends(_parse_auth_header)) -> str:
    """FastAPI dependency: returns current user role from token."""
    return auth["role"]


def require_admin(auth: dict = Depends(_parse_auth_header)) -> None:
    """FastAPI dependency: raises 403 if not admin."""
    if auth["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
