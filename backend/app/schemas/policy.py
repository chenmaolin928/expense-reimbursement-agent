"""Policy Center schemas — Pydantic DTOs for policy configuration."""

from __future__ import annotations

from enum import Enum
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
    policy_doc: RawPolicyDoc | None = None
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


# ===========================================================================
# New structured policy schemas (Phase 2 — domains[].rules[])
# ===========================================================================

class RuleScope(BaseModel):
    """Rule scope conditions — only filled if explicitly stated in text."""
    role: Optional[str] = Field(None, description="Employee role this rule applies to")
    region: Optional[str] = Field(None, description="Geographic region")
    amount_range: Optional[str] = Field(None, description="Amount range, e.g. '0-500'")


class PolicyRule(BaseModel):
    """Atomic rule unit — one condition, one effect.

    Rules MUST be atomic: '报销比例60%，超过500元需审批' → two PolicyRules.
    """
    id: str = Field(default="", description="Rule ID within the domain")
    type: str = Field(default="other", pattern=r"^(limit|ratio|approval|requirement|restriction|other)$")
    title: str = Field(default="", description="Short human-readable title")
    scope: RuleScope = Field(default_factory=RuleScope)
    condition: str = Field(default="", description="When this rule applies")
    value: Optional[float] = Field(None, description="Numeric value if applicable")
    unit: str = Field(default="", description="yuan / percent / days / times etc.")
    raw_text: str = Field(default="", description="Original text fragment this rule was extracted from")


class PolicyDomain(BaseModel):
    """Expense management domain — extracted from text, never predefined."""
    id: str = Field(default="", description="Domain ID, e.g. 'D001'")
    name: str = Field(default="", description="Domain name from原文")
    rules: list[PolicyRule] = Field(default_factory=list)


class RawPolicyDoc(BaseModel):
    """LLM-parsed structured policy document — top-level structure."""
    doc_id: str = Field(default="", description="Document identifier")
    title: str = Field(default="", description="Document title")
    version: str = Field(default="", description="Document version")
    domains: list[PolicyDomain] = Field(default_factory=list)


# ===========================================================================
# Rule Review / Audit schemas (Phase 6)
# ===========================================================================

class RuleReviewStatus(str, Enum):
    """Per-rule review status during human audit."""
    CONFIRMED = "confirmed"
    PENDING_REVIEW = "pending_review"
    INVALID = "invalid"


class RuleReview(BaseModel):
    """Per-rule review audit record stored in draft .reviews."""
    rule_id: str
    domain_id: str
    status: RuleReviewStatus = Field(default=RuleReviewStatus.PENDING_REVIEW)
    notes: str = ""
    updated_at: str = ""


class RuleUpdateRequest(BaseModel):
    """Update a single rule's fields + review status."""
    domain_id: str
    rule_id: str
    type: Optional[str] = Field(default=None, pattern=r"^(limit|ratio|approval|requirement|restriction|other)$")
    title: Optional[str] = None
    scope: Optional[RuleScope] = None
    condition: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    review_status: Optional[RuleReviewStatus] = None
    review_notes: Optional[str] = None


class SplitTarget(BaseModel):
    """One target rule when splitting a compound rule."""
    type: str = Field(..., pattern=r"^(limit|ratio|approval|requirement|restriction|other)$")
    title: str = ""
    scope: RuleScope = Field(default_factory=RuleScope)
    condition: str = ""
    value: Optional[float] = None
    unit: str = ""


class RuleSplitRequest(BaseModel):
    """Split a compound rule into multiple atomic rules."""
    domain_id: str
    source_rule_id: str
    splits: list[SplitTarget]


class RuleMergeRequest(BaseModel):
    """Merge multiple rules into one."""
    domain_id: str
    source_rule_ids: list[str]
    target_type: str = Field(..., pattern=r"^(limit|ratio|approval|requirement|restriction|other)$")
    target_title: str = ""
    target_condition: str = ""
    target_value: Optional[float] = None
    target_unit: str = ""


class BatchReviewUpdate(BaseModel):
    """Batch save all review changes at once."""
    reviews: dict[str, RuleReview] = Field(default_factory=dict)
    rule_updates: list[RuleUpdateRequest] = Field(default_factory=list)

