"""Authentication API routes — login, register."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.infrastructure.orm import User, Employee
from app.schemas.auth import LoginRequest, RegisterRequest, AuthResponse, UserResponse
from app.domain.enums import UserRole
from app.api.deps import get_current_user_id

import hashlib
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_password(password: str) -> str:
    """Simulated password hashing (SHA256 + salt). In production, use bcrypt."""
    salt = "expense-agent-salt-v1"
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


def _generate_token(user_id: int, username: str, role: str) -> str:
    """Simulated token generation. In production, use JWT with expiration."""
    return f"sim_{role}_{user_id}_{uuid.uuid4().hex[:8]}"


def _verify_token(token: str) -> dict | None:
    """Parse simulated token. Returns user info or None."""
    if not token.startswith("sim_"):
        return None
    parts = token.split("_")
    if len(parts) < 3:
        return None
    return {"role": parts[1], "user_id": int(parts[2])}


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if user.password_hash != _hash_password(req.password):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="账户已被禁用")

    token = _generate_token(user.id, user.username, user.role.value)

    return AuthResponse(
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        token=token,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    # Link employee if employee_code provided
    employee_id = None
    if req.employee_code:
        emp = db.query(Employee).filter(Employee.employee_code == req.employee_code).first()
        if emp:
            employee_id = emp.id

    user = User(
        username=req.username,
        password_hash=_hash_password(req.password),
        role=req.role,
        employee_id=employee_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = _generate_token(user.id, user.username, user.role.value)

    return AuthResponse(
        user_id=user.id,
        username=user.username,
        role=user.role.value,
        token=token,
    )


@router.get("/me", response_model=UserResponse)
def get_current_user(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Get current user info from simulated auth."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role.value,
        employee_id=user.employee_id,
        is_active=user.is_active,
    )
