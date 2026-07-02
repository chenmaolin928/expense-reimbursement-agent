"""Rule Engine — deterministic workflow rule evaluation.

All process decisions (approval needed? attachment needed? can submit?)
live here. The LLM never decides approval workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.engines.policy_engine import PolicyEngine


@dataclass
class RuleResult:
    """Structured result of a workflow rule evaluation."""
    can_submit: bool
    reason: str
    need_approval: bool
    need_guest_list: bool
    need_invoice: bool
    need_attachment: bool
    minimum_people: int
    expense_type_name: str = ""


class RuleEngine:
    """Deterministic workflow rule evaluator.

    All process decisions MUST go through this engine.
    """

    def __init__(self, policy_engine: PolicyEngine):
        self._policy = policy_engine

    def evaluate(
        self,
        expense_code: str,
        invoice_amount: float,
        enterprise: str = "default",
    ) -> RuleResult:
        """Evaluate workflow rules for a reimbursement submission.

        Returns a RuleResult with all fields populated.
        """
        expense_type = self._policy.get_expense_type(expense_code, enterprise)

        if not expense_type:
            return RuleResult(
                can_submit=False,
                reason=f"费用类型 '{expense_code}' 不在公司报销范围内",
                need_approval=False,
                need_guest_list=False,
                need_invoice=False,
                need_attachment=False,
                minimum_people=1,
                expense_type_name=expense_code,
            )

        name = expense_type.get("name", expense_code)
        approval_over = expense_type.get("approval_over", 0)
        need_guest = expense_type.get("need_guest", False)
        need_invoice = expense_type.get("need_invoice", True)
        need_attachment = expense_type.get("need_attachment", False)

        # Approval rule: amount >= approval_over threshold, AND approval_over > 0
        need_approval = approval_over > 0 and invoice_amount >= approval_over

        return RuleResult(
            can_submit=True,
            reason="",
            need_approval=need_approval,
            need_guest_list=need_guest,
            need_invoice=need_invoice,
            need_attachment=need_attachment,
            minimum_people=1,
            expense_type_name=name,
        )
