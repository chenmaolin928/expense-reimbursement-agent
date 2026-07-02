"""Policy Center schemas — Pydantic DTOs for policy configuration."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Single expense type rule
# ---------------------------------------------------------------------------

class PolicyExpenseType(BaseModel):
    """Single expense category rule in the policy document."""
    code: str = Field(..., description="Expense type code: meals, travel, etc.")
    name: str = Field(..., description="Human-readable name: 餐饮, 差旅, etc.")
    reimbursement_ratio: float = Field(..., ge=0.0, le=1.0, description="Reimbursement ratio: 0.0–1.0")
    limit_per_person: Optional[float] = Field(None, description="Per-person limit, null if none")
    cap: Optional[float] = Field(None, description="Absolute cap amount per submission")
    approval_over: float = Field(default=0, description="Amount threshold for requiring approval; 0 = never")
    need_guest: bool = Field(default=False, description="Whether guest list is required")
    need_invoice: bool = Field(default=True, description="Whether invoice is required")
    need_attachment: bool = Field(default=False, description="Whether additional attachments are required")
    enabled: bool = Field(default=True, description="Whether this expense type is active")


# ---------------------------------------------------------------------------
# Full policy document
# ---------------------------------------------------------------------------

class PolicyDocument(BaseModel):
    """Complete enterprise reimbursement policy."""
    version: str = Field(default="1.0")
    enterprise: str = Field(default="default")
    description: str = Field(default="")
    expense_types: list[PolicyExpenseType] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Policy Parse (AI-powered)
# ---------------------------------------------------------------------------

class PolicyParseRequest(BaseModel):
    """Request to parse natural-language policy text into structured JSON."""
    text: str = Field(..., min_length=1, description="Natural language policy text")


class PolicyParseResponse(BaseModel):
    """Response containing AI-parsed policy document."""
    policy: PolicyDocument
    warnings: list[str] = Field(default_factory=list)
    raw_llm_output: Optional[str] = Field(None, description="Raw LLM output for debugging")


# ---------------------------------------------------------------------------
# Policy Save
# ---------------------------------------------------------------------------

class PolicySaveRequest(BaseModel):
    """Request to save a policy document."""
    enterprise: str = Field(default="default")
    policy: PolicyDocument
