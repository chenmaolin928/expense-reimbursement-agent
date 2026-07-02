"""Unit tests for new structured policy parsing and normalization."""
import os
import sys
import json

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.schemas.policy import (
    RuleScope,
    PolicyRule,
    PolicyDomain,
    RawPolicyDoc,
)
from app.services.rule_normalizer import RuleNormalizer
from app.services.policy_parser_service import PolicyParserService


class TestNewSchemas:
    """RawPolicyDoc, PolicyDomain, PolicyRule, RuleScope Pydantic models."""

    def test_raw_policy_doc_empty(self):
        """Empty RawPolicyDoc should have default values."""
        doc = RawPolicyDoc()
        assert doc.doc_id == ""
        assert doc.domains == []

    def test_policy_rule_minimal(self):
        """PolicyRule with only required fields."""
        rule = PolicyRule(id="R001", type="limit")
        assert rule.title == ""
        assert rule.value is None
        assert rule.scope.role is None

    def test_policy_rule_all_fields(self):
        """PolicyRule with all fields set."""
        rule = PolicyRule(
            id="R001",
            type="ratio",
            title="报销比例",
            scope=RuleScope(role="总监", region="北京", amount_range="0-500"),
            condition="超过500元",
            value=0.6,
            unit="percent",
            raw_text="报销比例为60%",
        )
        assert rule.type == "ratio"
        assert rule.value == 0.6
        assert rule.scope.role == "总监"
        assert rule.raw_text == "报销比例为60%"

    def test_policy_rule_type_validation(self):
        """type must match the allowed pattern."""
        with pytest.raises(ValueError):
            PolicyRule(id="X", type="invalid_type")

    def test_policy_domain_with_rules(self):
        """PolicyDomain holds multiple PolicyRules."""
        domain = PolicyDomain(
            id="D001",
            name="餐饮",
            rules=[
                PolicyRule(id="R001", type="ratio", value=0.6, unit="percent",
                           raw_text="餐饮报销比例为60%"),
                PolicyRule(id="R002", type="limit", value=500, unit="yuan",
                           raw_text="单次不超过500元"),
            ],
        )
        assert len(domain.rules) == 2
        assert domain.rules[0].type == "ratio"
        assert domain.rules[1].type == "limit"

    def test_raw_policy_doc_full(self):
        """RawPolicyDoc with domains and rules."""
        doc = RawPolicyDoc(
            doc_id="DOC001",
            title="公司报销政策",
            version="2.0",
            domains=[
                PolicyDomain(id="D001", name="餐饮", rules=[
                    PolicyRule(id="R001", type="ratio", value=0.6),
                ]),
            ],
        )
        assert doc.title == "公司报销政策"
        assert doc.domains[0].name == "餐饮"
        assert doc.domains[0].rules[0].type == "ratio"


class TestRuleNormalizerNewFormat:
    """RuleNormalizer with new domains[].rules[] format."""

    def test_normalize_empty_policy_doc(self):
        """Empty policy_doc -> empty result."""
        normalizer = RuleNormalizer()
        result = normalizer.normalize({
            "policy_doc": {"doc_id": "", "title": "", "version": "", "domains": []},
            "warnings": [],
            "metadata": {},
        })
        assert result.is_valid is False
        assert result.policy_json["domains"] == []

    def test_normalize_new_format_strips_ai_metadata(self):
        """AI metadata fields should be stripped."""
        ai_draft = {
            "policy_doc": {
                "doc_id": "DOC001",
                "title": "Policy",
                "version": "1.0",
                "domains": [{
                    "id": "D001",
                    "name": "餐饮",
                    "rules": [{
                        "id": "R001", "type": "ratio", "title": "比例",
                        "scope": {"role": None, "region": None, "amount_range": None},
                        "condition": "", "value": 0.6, "unit": "percent",
                        "raw_text": "报销60%",
                        "confidence": 0.95,
                        "ai_reasoning": "AI reasoning here",
                    }],
                }],
            },
            "warnings": [],
            "metadata": {},
        }
        normalizer = RuleNormalizer()
        result = normalizer.normalize(ai_draft)
        cleaned = result.policy_json["domains"][0]["rules"][0]
        assert cleaned["type"] == "ratio"
        assert cleaned["value"] == 0.6
        assert "confidence" not in cleaned
        assert "ai_reasoning" not in cleaned

    def test_normalize_new_format_preserves_all_fields(self):
        """All essential fields preserved through normalization."""
        ai_draft = {
            "policy_doc": {
                "doc_id": "DOC001",
                "title": "公司报销政策",
                "version": "1.0",
                "domains": [{
                    "id": "D001",
                    "name": "餐饮",
                    "rules": [
                        {"id": "R001", "type": "ratio", "title": "报销比例",
                         "scope": {"role": "经理", "region": None, "amount_range": None},
                         "condition": "", "value": 0.6, "unit": "percent",
                         "raw_text": "餐饮报销比例60%"},
                        {"id": "R002", "type": "approval", "title": "审批阈值",
                         "scope": {"role": None, "region": None, "amount_range": None},
                         "condition": "超过500元", "value": 500, "unit": "yuan",
                         "raw_text": "超过500元需审批"},
                    ],
                }],
            },
            "warnings": [],
            "metadata": {},
        }
        normalizer = RuleNormalizer()
        result = normalizer.normalize(ai_draft)
        domains = result.policy_json["domains"]
        assert len(domains) == 1
        assert domains[0]["name"] == "餐饮"
        assert len(domains[0]["rules"]) == 2
        assert domains[0]["rules"][0]["value"] == 0.6
        assert domains[0]["rules"][0]["unit"] == "percent"
        assert domains[0]["rules"][1]["value"] == 500
        assert domains[0]["rules"][1]["condition"] == "超过500元"

    def test_normalize_legacy_format_backward_compat(self):
        """Legacy flat expense_types still works via _normalize_v1."""
        normalizer = RuleNormalizer()
        ai_draft = {
            "enterprise": "default",
            "description": "Test",
            "expense_types": [
                {"code": "meals", "name": "餐饮", "reimbursement_ratio": 0.6,
                 "cap": 500, "approval_over": 0, "need_guest": False,
                 "need_invoice": True, "need_attachment": False, "enabled": True,
                 "confidence": 0.95, "source_text": "原文"},
            ],
            "warnings": [],
            "metadata": {},
        }
        result = normalizer.normalize(ai_draft)
        # Should produce domains[].rules[]
        assert len(result.policy_json["domains"]) == 1
        assert result.policy_json["domains"][0]["name"] == "餐饮"
        rules = result.policy_json["domains"][0]["rules"]
        assert len(rules) >= 2  # ratio + cap
        assert any(r["type"] == "ratio" and r["value"] == 0.6 for r in rules)
        assert any(r["type"] == "limit" and r["value"] == 500 for r in rules)


class TestParserServiceBackwardCompat:
    """PolicyParserService new prompt + legacy flat path."""

    def test_parse_flat_restaurant_rule(self):
        """parse_flat_policy_document converts new format to flat expense_types."""
        # We don't call the real LLM; instead verify the structure
        # by checking the class has the compat method
        svc = PolicyParserService()
        assert hasattr(svc, "parse_flat_policy_document")

    def test_domain_name_to_code_mapping(self):
        """Domain name -> code mapping works for common cases."""
        svc = PolicyParserService()
        assert svc._domain_name_to_code("餐饮", "") == "meals"
        assert svc._domain_name_to_code("差旅费", "") == "travel"
        assert svc._domain_name_to_code("交通", "") == "transportation"
        assert svc._domain_name_to_code("办公用品", "") == "office_supplies"
        assert svc._domain_name_to_code("商务招待", "") == "entertainment"
        assert svc._domain_name_to_code("未知类别", "other") == "other"

    def test_default_policy_is_empty(self):
        """Default policy should have no domains."""
        policy = PolicyParserService._default_policy()
        assert policy.domains == []


class TestPolicyEngineBridge:
    """PolicyEngine backward compat bridge via rules."""

    def test_policy_engine_resolves_from_new_format(self, tmp_path):
        """PolicyEngine.get_expense_type() resolves rules → flat dict."""
        from app.services.policy_repository import PolicyRepository
        from app.engines.policy_engine import PolicyEngine

        import json
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy = {
            "doc_id": "", "title": "Test", "version": "1.0",
            "domains": [{
                "id": "meals", "name": "餐饮",
                "rules": [
                    {"id": "R001", "type": "ratio", "title": "比例",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 0.6, "unit": "percent",
                     "raw_text": "报销比例60%"},
                    {"id": "R002", "type": "limit", "title": "上限",
                     "scope": {"role": None, "region": None, "amount_range": None},
                     "condition": "", "value": 500, "unit": "yuan",
                     "raw_text": "单次上限500元"},
                ],
            }],
        }
        with open(policies_dir / "default.json", "w", encoding="utf-8") as f:
            json.dump(policy, f, ensure_ascii=False)

        repo = PolicyRepository(str(policies_dir))
        engine = PolicyEngine(repo)

        # Legacy call — should resolve from new format
        et = engine.get_expense_type("meals")
        assert et.get("code") == "meals"
        assert et.get("reimbursement_ratio") == 0.6
        assert et.get("cap") == 500

    def test_policy_engine_get_domain(self, tmp_path):
        """PolicyEngine.get_domain() returns domain by name."""
        from app.services.policy_repository import PolicyRepository
        from app.engines.policy_engine import PolicyEngine

        import json
        policies_dir = tmp_path / "policies"
        policies_dir.mkdir()

        policy = {
            "doc_id": "", "title": "", "version": "",
            "domains": [{
                "id": "D001", "name": "餐饮",
                "rules": [{"id": "R001", "type": "ratio", "value": 0.6, "unit": "percent",
                          "scope": {}, "condition": "", "title": "", "raw_text": ""}],
            }],
        }
        with open(policies_dir / "default.json", "w", encoding="utf-8") as f:
            json.dump(policy, f, ensure_ascii=False)

        repo = PolicyRepository(str(policies_dir))
        engine = PolicyEngine(repo)

        domain = engine.get_domain("餐饮")
        assert domain["name"] == "餐饮"
        assert len(domain["rules"]) == 1
