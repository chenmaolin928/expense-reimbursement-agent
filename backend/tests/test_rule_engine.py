"""Unit tests for RuleEngine."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.policy_repository import PolicyRepository
from app.engines.policy_engine import PolicyEngine
from app.engines.rule_engine import RuleEngine, RuleResult


class TestRuleEngine:
    """RuleEngine unit tests."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Create RuleEngine with temp policy directory."""
        import json
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()
        policy = {
            "version": "1.0",
            "enterprise": "default",
            "expense_types": [
                {"code": "meals", "name": "餐饮", "reimbursement_ratio": 0.6, "cap": 500,
                 "approval_over": 0, "need_guest": False, "need_invoice": True,
                 "need_attachment": False, "enabled": True},
                {"code": "entertainment", "name": "商务招待", "reimbursement_ratio": 0.8,
                 "cap": 1000, "approval_over": 1000, "need_guest": True,
                 "need_invoice": True, "need_attachment": True, "enabled": True},
            ],
        }
        with open(policies_dir / "default.json", "w", encoding="utf-8") as f:
            json.dump(policy, f, ensure_ascii=False)
        repo = PolicyRepository(str(policies_dir))
        pe = PolicyEngine(repo)
        return RuleEngine(pe)

    def test_entertainment_over_approval_needs_approval(self, engine):
        """entertainment 1500 >= approval_over(1000) -> need_approval=true."""
        r = engine.evaluate("entertainment", 1500)
        assert r.can_submit is True
        assert r.need_approval is True
        assert r.need_guest_list is True
        assert r.need_attachment is True

    def test_meals_no_approval(self, engine):
        """meals: approval_over=0 -> need_approval=false regardless of amount."""
        r = engine.evaluate("meals", 9999)
        assert r.can_submit is True
        assert r.need_approval is False

    def test_unknown_category_cannot_submit(self, engine):
        """Unknown category -> can_submit=false."""
        r = engine.evaluate("nonexistent", 500)
        assert r.can_submit is False
        assert "不在公司报销范围内" in r.reason

    def test_entertainment_under_threshold_no_approval(self, engine):
        """entertainment 500 < approval_over(1000) -> need_approval=false."""
        r = engine.evaluate("entertainment", 500)
        assert r.can_submit is True
        assert r.need_approval is False

    def test_result_is_dataclass(self, engine):
        """Result is a RuleResult dataclass."""
        r = engine.evaluate("meals", 200)
        assert isinstance(r, RuleResult)
