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
    PARSING = "parsing"
    REVIEWING = "reviewing"
    PUBLISHED = "published"
    ARCHIVED = "archived"
