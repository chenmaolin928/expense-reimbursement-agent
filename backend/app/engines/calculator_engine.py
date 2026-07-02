"""Calculator Engine — deterministic reimbursement math.

All financial calculations live here. The LLM never does math.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.engines.policy_engine import PolicyEngine


@dataclass
class CalculationResult:
    """Structured result of a reimbursement calculation."""
    verdict: str  # "in_scope" | "out_of_scope"
    invoice_amount: float
    reimbursement_ratio: float
    calculated_amount: float
    cap: float | None
    final_amount: float
    excess_amount: float
    per_person_limit: float | None
    people_count: int
    expense_type_name: str = ""


class CalculatorEngine:
    """Deterministic reimbursement calculator.

    All math MUST go through this engine — the LLM never computes amounts.
    """

    def __init__(self, policy_engine: PolicyEngine):
        self._policy = policy_engine

    def calculate(
        self,
        expense_code: str,
        invoice_amount: float,
        people_count: int = 1,
        enterprise: str = "default",
    ) -> CalculationResult:
        """Calculate reimbursement amount based on policy rules.

        Logic: invoice_amount × reimbursement_ratio → compare to cap → min → excess.
        """
        expense_type = self._policy.get_expense_type(expense_code, enterprise)

        if not expense_type:
            return CalculationResult(
                verdict="out_of_scope",
                invoice_amount=invoice_amount,
                reimbursement_ratio=0.0,
                calculated_amount=0.0,
                cap=None,
                final_amount=0.0,
                excess_amount=0.0,
                per_person_limit=None,
                people_count=people_count,
                expense_type_name="",
            )

        ratio = expense_type.get("reimbursement_ratio", 0.8)
        cap = expense_type.get("cap")
        per_person_limit = expense_type.get("limit_per_person")
        name = expense_type.get("name", expense_code)

        calculated = round(invoice_amount * ratio, 2)
        final_amount = min(calculated, cap) if cap is not None else calculated
        excess = round(calculated - final_amount, 2) if calculated > final_amount else 0.0

        return CalculationResult(
            verdict="in_scope",
            invoice_amount=invoice_amount,
            reimbursement_ratio=ratio,
            calculated_amount=calculated,
            cap=cap,
            final_amount=final_amount,
            excess_amount=max(excess, 0.0),
            per_person_limit=per_person_limit,
            people_count=people_count,
            expense_type_name=name,
        )
