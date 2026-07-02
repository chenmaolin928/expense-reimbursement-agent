"""Agent unit tests — verify ReAct loop, tools, mock LLM behavior."""

import pytest
from app.services.agent_service import build_agent_graph, AGENT_TOOLS, SYSTEM_PROMPT, PLAN_PROMPT
from app.engines.rule_engine import RuleResult


class TestAgentGraph:
    """Verify the LangGraph ReAct agent structure."""

    def test_graph_builds(self):
        graph = build_agent_graph()
        assert graph is not None

    def test_graph_has_agent_and_tools(self):
        graph = build_agent_graph()
        nodes = list(graph.nodes.keys())
        # PAO graph: plan → act ↔ tools → observe
        assert "plan" in nodes
        assert "act" in nodes
        assert "tools" in nodes
        assert "observe" in nodes

    def test_tools_registered(self):
        assert len(AGENT_TOOLS) == 5
        tool_names = {t.name for t in AGENT_TOOLS}
        expected = {"scan_invoice", "search_knowledge", "check_reimbursement_status",
                     "submit_reimbursement", "send_notification"}
        assert tool_names == expected

    def test_system_prompt_contains_rules(self):
        assert "scan_invoice" in SYSTEM_PROMPT
        assert "search_knowledge" in SYSTEM_PROMPT
        assert "submit_reimbursement" in SYSTEM_PROMPT
        assert "send_notification" in SYSTEM_PROMPT

    def test_plan_prompt_contains_tools(self):
        assert "scan_invoice" in PLAN_PROMPT
        assert "search_knowledge" in PLAN_PROMPT


class TestTools:
    """Verify tool functions execute correctly."""

    def test_scan_invoice_returns_structure(self):
        from app.services.tools import scan_invoice
        result = scan_invoice.invoke({"file_path": "test.png"})
        assert "vendor" in result
        assert "amount" in result
        assert "category_raw" in result
        assert "date" in result

    def test_scan_invoice_deterministic(self):
        from app.services.tools import scan_invoice
        r1 = scan_invoice.invoke({"file_path": "a.png"})
        r2 = scan_invoice.invoke({"file_path": "a.png"})
        assert r1["vendor"] == r2["vendor"]
        assert r1["amount"] == r2["amount"]

    def test_scan_invoice_different_files(self):
        from app.services.tools import scan_invoice
        r1 = scan_invoice.invoke({"file_path": "a.png"})
        r2 = scan_invoice.invoke({"file_path": "b.png"})
        # Different files may produce different results due to hash
        assert "vendor" in r1 and "vendor" in r2

    def test_search_knowledge(self, db_session):
        """search_knowledge opens its own DB session, just verify it runs."""
        from app.services.tools import search_knowledge
        result = search_knowledge.invoke({"query": "test"})
        assert "total_results" in result
        assert isinstance(result["total_results"], int)

    def test_check_status_unknown_report(self):
        from app.services.tools import check_reimbursement_status
        result = check_reimbursement_status.invoke({"report_number": "EXP-NONEXISTENT"})
        assert "error" in result

    def test_submit_reimbursement_creates_report(self):
        from app.services.tools import submit_reimbursement, set_tool_context
        set_tool_context(employee_id=1, user_email="test@test.cn", rule_engine=None)
        result = submit_reimbursement.invoke({
            "report_id": "REQ-test-001",
            "amount": 100.0,
            "category": "office_supplies",
            "vendor": "Test Corp",
            "note": "Test",
        })
        assert "report_number" in result
        assert result["status"] == "submitted"

    def test_submit_reimbursement_enters_manager_approval_when_policy_requires_it(self):
        from app.services.tools import submit_reimbursement, set_tool_context

        class FakeRuleEngine:
            def evaluate(self, category: str, amount: float) -> RuleResult:
                return RuleResult(
                    can_submit=True,
                    reason="",
                    need_approval=True,
                    need_guest_list=False,
                    need_invoice=True,
                    need_attachment=False,
                    minimum_people=1,
                    expense_type_name="商务招待",
                )

        set_tool_context(
            employee_id=1,
            user_email="test@test.cn",
            rule_engine=FakeRuleEngine(),
        )
        result = submit_reimbursement.invoke({
            "report_id": "REQ-test-approval",
            "amount": 1500.0,
            "category": "entertainment",
            "vendor": "VIP Club",
            "note": "Approval path",
        })

        assert "report_number" in result
        assert result["status"] == "manager_approval"
        assert "等待主管审批" in result["message"]
        assert result["rule_check"]["need_approval"] is True

    def test_send_notification(self):
        from app.services.tools import send_notification, set_tool_context
        set_tool_context(user_email="test@test.cn")
        result = send_notification.invoke({
            "subject": "Test",
            "body": "Test body",
        })
        assert result["sent"] is True
        assert result["recipient"] == "test@test.cn"
