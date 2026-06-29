"""LangGraph ReAct Agent — the brain of the expense reimbursement system.

Architecture:
    START → agent_node (LLM with tools) ↔ tool_node (local execution) → END

The LLM decides WHICH tool to call and WHEN. The graph just loops between
agent_node and tool_node until the LLM returns a final text response (no function_call).

This is a REAL ReAct agent, not a hardcoded DAG workflow.
Same /chat endpoint, different tool paths per conversation.
"""

from typing import Annotated, Literal
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage

from app.infrastructure.llm_client import get_model
from app.services.tools import (
    scan_invoice,
    search_knowledge,
    check_reimbursement_status,
    submit_reimbursement,
    send_notification,
    set_tool_context,
)
from app.config import settings

# ============================================================
# Agent tools (registered with LLM)
# ============================================================

AGENT_TOOLS = [
    scan_invoice,
    search_knowledge,
    check_reimbursement_status,
    submit_reimbursement,
    send_notification,
]

# ============================================================
# System Prompt — Defines the Agent's personality and rules
# ============================================================

SYSTEM_PROMPT = """你是公司内部的报销助手 AI Agent。你的名字叫"小报"。

你拥有以下工具能力:
1. **scan_invoice** — 扫描发票/收据，提取金额、类别、日期、商家
2. **search_knowledge** — 搜索公司报销政策和标准
3. **check_reimbursement_status** — 查询报销单审批进度
4. **submit_reimbursement** — 向公司内部系统提交报销申请
5. **send_notification** — 发送邮件通知员工报销进展

## 工作流程

当收到报销请求时，按以下原则自主决策:
1. **先扫描**: 有发票文件时，先调 scan_invoice 提取信息
2. **再查政策**: 根据发票类别，调 search_knowledge 查询对应报销标准
3. **比对待遇**: 对比发票金额和公司政策，做出判断
4. **确认用户**: 在提交前，必须先向用户确认报销金额和类别
5. **提交执行**: 用户确认后，调 submit_reimbursement 提交
6. **通知结果**: 提交完成后，调 send_notification 通知用户

## 决策原则

- 金额在标准范围内 → 可报销，向用户确认后提交
- 金额超出标准 → 解释原因，告知用户哪些部分可报哪些不可报，询问是否仍要提交
- 信息不足 → 向用户追问（不要编造信息）
- 无法判断 → 告知用户原因，建议人工处理
- 每次判断必须引用具体的政策条款

## 严格规则

- 不要编造政策规则 — 只依据 search_knowledge 返回的内容
- 报销金额不能超过发票金额
- 提交前必须获得用户确认
- 你是决策和执行引擎 — 可以改变系统状态，不只是回答问题
- 所有操作都有审计日志，请认真对待每笔报销

## 纯闲聊/非报销问题
如果用户不是问报销相关问题，直接用中文友好回复，不需要调用工具。
"""


# ============================================================
# Agent State
# ============================================================

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ============================================================
# Agent Node — calls LLM with tools
# ============================================================

def agent_node(state: AgentState) -> dict:
    """Call the LLM with the current message history + tools."""
    model = get_model()
    model_with_tools = model.bind_tools(AGENT_TOOLS)

    # Prepend system prompt if first message
    messages = list(state["messages"])
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = model_with_tools.invoke(messages)
    return {"messages": [response]}


# ============================================================
# Tool Node — executes tools locally
# ============================================================

tool_node = ToolNode(AGENT_TOOLS)


# ============================================================
# Router — should we call tools or end?
# ============================================================

def should_continue(state: AgentState) -> Literal["tools", "__end__"]:
    """Determine if the LLM wants to call a tool or is done."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "__end__"


# ============================================================
# Build the Graph
# ============================================================

def build_agent_graph() -> StateGraph:
    """Build the ReAct agent graph: agent ↔ tools loop."""
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "agent")  # Loop back to agent after tool execution

    return workflow.compile()


# ============================================================
# Singleton graph instance
# ============================================================

_agent_graph = None


def get_agent():
    """Get or create the compiled agent graph singleton."""
    global _agent_graph
    if _agent_graph is None:
        _agent_graph = build_agent_graph()
    return _agent_graph


# ============================================================
# Run Agent (called from Chat API)
# ============================================================

async def run_agent(
    session_id: str,
    user_message: str,
    user_id: int,
    employee_id: int | None,
    user_email: str | None,
    message_history: list[dict] | None = None,
) -> list[dict]:
    """Run the ReAct agent and return SSE events.

    Events are dicts with 'type': thinking, tool_call, tool_result, message, confirm, done
    """
    # Set tool execution context (PII stays local, never goes to LLM)
    set_tool_context(
        user_id=user_id,
        employee_id=employee_id,
        user_email=user_email,
    )

    agent = get_agent()

    # Build message history
    input_messages = []
    if message_history:
        for m in message_history:
            if m["role"] == "user":
                input_messages.append(HumanMessage(content=m["content"]))
            elif m["role"] == "assistant":
                input_messages.append(AIMessage(content=m["content"] or ""))

    # Add current message
    input_messages.append(HumanMessage(content=user_message))

    events = []
    config = {"configurable": {"thread_id": session_id}}

    # Stream the agent execution
    final_state = None
    async for event in agent.astream(
        {"messages": input_messages},
        config=config,
        stream_mode="values",
    ):
        final_state = event

    if final_state is None:
        return events

    # Convert messages to SSE events
    for msg in final_state["messages"]:
        if isinstance(msg, SystemMessage):
            continue

        if isinstance(msg, HumanMessage):
            # Only emit the last user message
            if msg.content == user_message:
                events.append({
                    "type": "message",
                    "role": "user",
                    "content": str(msg.content),
                })

        elif isinstance(msg, AIMessage):
            content = str(msg.content) if msg.content else ""
            if msg.tool_calls:
                events.append({
                    "type": "thinking",
                    "content": "正在分析..." if not content else content[:200],
                })
                for tc in msg.tool_calls:
                    events.append({
                        "type": "tool_call",
                        "tool": tc["name"],
                        "args": tc["args"],
                    })
            else:
                events.append({
                    "type": "message",
                    "role": "assistant",
                    "content": content,
                })

        elif isinstance(msg, ToolMessage):
            result = msg.content
            # Try to parse JSON tool results
            import json
            try:
                result = json.loads(msg.content) if isinstance(msg.content, str) else msg.content
            except (json.JSONDecodeError, TypeError):
                result = msg.content

            events.append({
                "type": "tool_result",
                "tool": msg.name,
                "result": result,
            })

    events.append({"type": "done"})
    return events
