"""Unit tests for PolicyEngine."""

import os
import sys
import tempfile

import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.policy_repository import PolicyRepository
from app.engines.policy_engine import PolicyEngine


class TestPolicyEngine:
    """PolicyEngine unit tests."""

    @pytest.fixture
    def engine(self, tmp_path):
        """Create a PolicyEngine with a temp policies directory containing default.json."""
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()
        # Copy the real default.json
        import json, shutil
        src = os.path.join(os.path.dirname(__file__), "..", "policies", "default.json")
        if os.path.exists(src):
            shutil.copy(src, policies_dir / "default.json")
        else:
            # Fallback: write minimal policy
            policy = {
                "version": "1.0",
                "enterprise": "default",
                "expense_types": [
                    {"code": "meals", "name": "餐饮", "reimbursement_ratio": 0.6, "cap": 500,
                     "approval_over": 0, "need_guest": False, "need_invoice": True,
                     "need_attachment": False, "enabled": True},
                    {"code": "travel", "name": "差旅", "reimbursement_ratio": 0.8, "cap": 500,
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
        return PolicyEngine(repo)

    def test_get_expense_type_returns_full_rule(self, engine):
        """get_expense_type returns complete rule for known type."""
        meals = engine.get_expense_type("meals")
        assert meals["code"] == "meals"
        assert meals["reimbursement_ratio"] == 0.6
        assert meals["cap"] == 500

    def test_get_expense_type_unknown_returns_empty(self, engine):
        """get_expense_type returns {} for unsupported type."""
        assert engine.get_expense_type("nonexistent") == {}

    def test_is_expense_type_supported(self, engine):
        """is_expense_type_supported checks existence and enabled state."""
        assert engine.is_expense_type_supported("meals") is True
        assert engine.is_expense_type_supported("nonexistent") is False

    def test_get_all_expense_types_only_enabled(self, engine):
        """get_all_expense_types excludes disabled types."""
        all_types = engine.get_all_expense_types()
        codes = {et["code"] for et in all_types}
        assert "meals" in codes
        # Check no disabled type leaks through
        for et in all_types:
            assert et.get("enabled", True) is True
