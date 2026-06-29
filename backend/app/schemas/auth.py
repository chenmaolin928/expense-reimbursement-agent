"""Authentication DTOs — login, register, token responses."""

from pydantic import BaseModel, Field
from app.domain.enums import UserRole


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=4, max_length=100)
    role: UserRole = UserRole.EMPLOYEE
    employee_code: str | None = None  # optional; admin creates users without employee link


class AuthResponse(BaseModel):
    user_id: int
    username: str
    role: str
    token: str  # simulated JWT-like token


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    employee_id: int | None
    is_active: bool

    class Config:
        from_attributes = True
