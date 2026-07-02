"""Domain enumerations — pure business logic, zero dependencies."""

from enum import Enum


class UserRole(str, Enum):
    EMPLOYEE = "employee"
    ADMIN = "admin"


class ReportStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    MANAGER_APPROVAL = "manager_approval"
    FINANCE_APPROVAL = "finance_approval"
    APPROVED = "approved"
    PAID = "paid"
    REJECTED = "rejected"


class ExpenseCategory(str, Enum):
    TRAVEL = "travel"
    MEALS = "meals"
    OFFICE_SUPPLIES = "office_supplies"
    TRANSPORTATION = "transportation"
    ENTERTAINMENT = "entertainment"
    OTHER = "other"


class DecisionStatus(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    ADJUSTED = "adjusted"
    REQUIRES_CLARIFICATION = "requires_clarification"


class ExecutionStatus(str, Enum):
    PENDING_OCR = "pending_ocr"
    OCR_DONE = "ocr_done"
    DESENSITIZED = "desensitized"
    CLOUD_DECIDED = "cloud_decided"
    FORM_FILLED = "form_filled"
    SUBMITTED = "submitted"
    PAID = "paid"
    REJECTED = "rejected"


class NotificationEvent(str, Enum):
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PAID = "paid"
    CLARIFICATION_NEEDED = "clarification_needed"


class PolicyStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# 内部子状态（不参与状态机迁移）
SUB_STATUS_DRAFTING = "drafting"
SUB_STATUS_PARSING = "parsing"
SUB_STATUS_REVIEWING = "reviewing"
SUB_STATUS_READY = "ready"

# 强制迁移规则
VALID_POLICY_TRANSITIONS: dict[PolicyStatus, set[PolicyStatus]] = {
    PolicyStatus.DRAFT: {PolicyStatus.PUBLISHED, PolicyStatus.ARCHIVED},
    PolicyStatus.PUBLISHED: {PolicyStatus.ARCHIVED},
    PolicyStatus.ARCHIVED: {PolicyStatus.PUBLISHED},  # 唯一回退路径
}


class InvalidPolicyTransitionError(ValueError):
    pass


def assert_transition_allowed(current: PolicyStatus, target: PolicyStatus) -> None:
    allowed = VALID_POLICY_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidPolicyTransitionError(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Allowed targets: {[s.value for s in allowed]}"
        )
