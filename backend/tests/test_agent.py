"""Agent unit tests — verify ReAct loop, tools, mock LLM behavior."""

import pytest
from app.services.agent_service import build_agent_graph, AGENT_TOOLS, SYSTEM_PROMPT


class TestAgentGraph:
    """Verify the LangGraph ReAct agent structure."""

    def test_graph_builds(self):
        graph = build_agent_graph()
        assert graph is not None

    def test_graph_has_agent_and_tools(self):
        graph = build_agent_graph()
        nodes = list(graph.nodes.keys())
        assert "agent" in nodes
        assert "tools" in nodes

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


class TestMockLLM:
    """Verify the mock LLM generates correct tool call sequences."""

    def test_policy_question_no_tools(self):
        from app.infrastructure.llm_client import _MockChatModel
        from langchain_core.messages import HumanMessage

        model = _MockChatModel()
        model.bind_tools(AGENT_TOOLS)
        response = model.invoke([HumanMessage(content="公司餐补标准是多少？")])
        assert response.content is not None
        assert len(response.content) > 10
        # Should NOT request tool calls for a policy question without invoice
        assert not response.tool_calls

    def test_invoice_triggers_scan(self):
        from app.infrastructure.llm_client import _MockChatModel
        from langchain_core.messages import HumanMessage

        model = _MockChatModel()
        model.bind_tools(AGENT_TOOLS)
        response = model.invoke([HumanMessage(content="帮我报销这张发票 已上传文件: receipt.png")])
        assert response.tool_calls is not None
        assert any(tc["name"] == "scan_invoice" for tc in response.tool_calls)

    def test_confirm_triggers_submit(self):
        from app.infrastructure.llm_client import _MockChatModel
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

        model = _MockChatModel()
        model.bind_tools(AGENT_TOOLS)

        # Simulate a full conversation: scan done, knowledge checked, user confirms
        messages = [
            HumanMessage(content="帮我报销 已上传文件: test.png"),
            AIMessage(
                content="scanning...",
                tool_calls=[{"name": "scan_invoice", "args": {"file_path": "test.png"}, "id": "1"}],
            ),
            ToolMessage(content='{"vendor":"Test","amount":234.5}', name="scan_invoice", tool_call_id="1"),
            AIMessage(
                content="checking policy...",
                tool_calls=[{"name": "search_knowledge", "args": {"query": "test"}, "id": "2"}],
            ),
            ToolMessage(content='{"total_results":1}', name="search_knowledge", tool_call_id="2"),
            HumanMessage(content="确认，提交"),
        ]
        response = model.invoke(messages)
        assert response.tool_calls is not None, "Expected tool_calls, got None"
        assert any(tc["name"] == "submit_reimbursement" for tc in response.tool_calls), \
            f"No submit_reimbursement in {[tc['name'] for tc in response.tool_calls]}"


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
        set_tool_context(employee_id=1, user_email="test@test.cn")
        result = submit_reimbursement.invoke({
            "report_id": "REQ-test-001",
            "amount": 100.0,
            "category": "office_supplies",
            "vendor": "Test Corp",
            "note": "Test",
        })
        assert "report_number" in result
        assert result["status"] == "submitted"

    def test_send_notification(self):
        from app.services.tools import send_notification, set_tool_context
        set_tool_context(user_email="test@test.cn")
        result = send_notification.invoke({
            "subject": "Test",
            "body": "Test body",
        })
        assert result["sent"] is True
        assert result["recipient"] == "test@test.cn"
