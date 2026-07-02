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


# ---- New schemas for draft/upload flow ----

class DraftExpenseType(BaseModel):
    """Expense type with AI metadata fields for draft review."""
    code: str
    name: str
    reimbursement_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    max_amount: Optional[float] = None
    need_invoice: bool = True
    need_attachment: bool = False
    need_guest: bool = False
    approval_over: float = 0
    enabled: bool = True
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_text: str = ""
    ai_reasoning: str = ""


class PolicyDraft(BaseModel):
    """AI draft before normalization."""
    enterprise: str = "default"
    description: str = ""
    expense_types: list[DraftExpenseType] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class PolicyUploadResponse(BaseModel):
    """Response after PDF upload + AI parsing."""
    policy_id: int
    version_id: int
    version_number: int
    status: str
    pdf_filename: str
    kb_id: int | None = None
    message: str


class PolicyListItem(BaseModel):
    """Summary row in policy list."""
    id: int
    name: str
    description: str
    policy_type: str
    status: str
    current_version_number: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PolicyDetail(BaseModel):
    """Full policy detail with current version info."""
    id: int
    name: str
    description: str
    policy_type: str
    status: str
    enterprise: str
    current_version_id: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class PolicyVersionItem(BaseModel):
    """Single version row in history."""
    id: int
    version_number: int
    status: str
    pdf_filename: str | None = None
    kb_id: int | None = None
    published_at: str | None = None
    created_at: str | None = None


class PolicyVersionDetail(BaseModel):
    """Full version detail including draft and policy_json."""
    id: int
    version_number: int
    status: str
    pdf_filename: str | None = None
    kb_id: int | None = None
    ai_draft: dict | None = None
    policy_json: dict | None = None
    published_at: str | None = None
    created_at: str | None = None


class UpdateDraftRequest(BaseModel):
    """Manual draft edit request."""
    draft: PolicyDraft


class NormalizeResponse(BaseModel):
    """Result of draft -> policy_json normalization."""
    policy_json: dict
    warnings: list[str] = Field(default_factory=list)


class PublishResponse(BaseModel):
    """Result of publishing."""
    success: bool
    message: str
    policy_id: int
    version_id: int
