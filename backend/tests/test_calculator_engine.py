"""Unit tests for CalculatorEngine."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.policy_repository import PolicyRepository
from app.engines.policy_engine import PolicyEngine
from app.engines.calculator_engine import CalculatorEngine, CalculationResult


class TestCalculatorEngine:
    """CalculatorEngine unit tests."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Create CalculatorEngine with temp policy directory."""
        import json
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()
        policy = {
            "version": "1.0",
            "enterprise": "default",
            "expense_types": [
                {"code": "meals", "name": "餐饮", "reimbursement_ratio": 0.6, "cap": 500,
                 "approval_over": 0, "need_guest": False, "enabled": True},
                {"code": "travel", "name": "差旅", "reimbursement_ratio": 0.8, "cap": 500,
                 "approval_over": 0, "need_guest": False, "enabled": True},
                {"code": "entertainment", "name": "商务招待", "reimbursement_ratio": 0.8,
                 "cap": 1000, "approval_over": 1000, "need_guest": True, "enabled": True},
            ],
        }
        with open(policies_dir / "default.json", "w", encoding="utf-8") as f:
            json.dump(policy, f, ensure_ascii=False)
        repo = PolicyRepository(str(policies_dir))
        pe = PolicyEngine(repo)
        return CalculatorEngine(pe)

    def test_meals_over_cap_gets_capped(self, engine):
        """meals: 1000 * 0.6 = 600, cap=500 -> final=500, excess=100."""
        r = engine.calculate("meals", 1000)
        assert r.verdict == "in_scope"
        assert r.calculated_amount == 600.0
        assert r.final_amount == 500.0
        assert r.excess_amount == 100.0

    def test_meals_under_cap_no_excess(self, engine):
        """meals: 100 * 0.6 = 60, cap=500 -> final=60, excess=0."""
        r = engine.calculate("meals", 100)
        assert r.calculated_amount == 60.0
        assert r.final_amount == 60.0
        assert r.excess_amount == 0.0

    def test_unknown_type_out_of_scope(self, engine):
        """Unknown expense code -> verdict='out_of_scope'."""
        r = engine.calculate("unknown_type", 100)
        assert r.verdict == "out_of_scope"
        assert r.final_amount == 0.0

    def test_entertainment_large_amount_capped(self, engine):
        """entertainment: 2000 * 0.8 = 1600, cap=1000 -> final=1000."""
        r = engine.calculate("entertainment", 2000)
        assert r.calculated_amount == 1600.0
        assert r.final_amount == 1000.0
        assert r.excess_amount == 600.0

    def test_travel_exact_cap(self, engine):
        """travel: 625 * 0.8 = 500 exactly at cap -> final=500, excess=0."""
        r = engine.calculate("travel", 625)
        assert r.calculated_amount == 500.0
        assert r.final_amount == 500.0
        assert r.excess_amount == 0.0

    def test_result_is_dataclass(self, engine):
        """Result is a CalculationResult dataclass."""
        r = engine.calculate("meals", 200)
        assert isinstance(r, CalculationResult)
        assert r.expense_type_name == "餐饮"
