"""Policy Parser Service — AI-powered natural language → structured JSON.

Calls the LLM to extract structured policy rules from free-text policy documents.
Output format: RawPolicyDoc (domains[].rules[]).
"""

import json
import logging
import re
import time

from app.infrastructure.llm_client import get_model
from app.schemas.policy import (
    PolicyDocument,
    PolicyExpenseType,
    RuleScope,
    PolicyRule,
    PolicyDomain,
    RawPolicyDoc,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# New LLM Prompt — structured extraction (domains → rules)
# ---------------------------------------------------------------------------

POLICY_PARSE_SYSTEM_PROMPT = """你是一个企业报销政策解析器。你的任务是将输入的企业报销制度文本转换为严格固定结构的 JSON 数据。

----------------------

强约束规则：
1. 不允许修改 JSON 结构
2. 不允许新增或删除字段
3. 不允许使用预定义费用分类
4. 所有分类（domains）必须从原文自动归纳
5. 不允许常识补全或猜测数据
6. 未明确字段必须填 null
7. 每条规则必须保留原文片段 raw_text
8. 规则必须拆分为最小原子单元，不允许合并

----------------------

输出结构必须严格如下：

{
  "doc_id": "",
  "title": "",
  "version": "",
  "domains": [
    {
      "id": "",
      "name": "",
      "rules": [
        {
          "id": "",
          "type": "limit | ratio | approval | requirement | restriction | other",
          "title": "",
          "scope": {
            "role": null,
            "region": null,
            "amount_range": null
          },
          "condition": "",
          "value": null,
          "unit": "",
          "raw_text": ""
        }
      ]
    }
  ]
}

----------------------

输出要求：
- 只输出 JSON
- 不要任何解释
- 不要任何额外文本
- 必须严格符合结构"""


class PolicyParserService:
    """Parse natural-language policy text into structured RawPolicyDoc via LLM."""

    def __init__(self):
        self._model = None

    @property
    def model(self):
        if self._model is None:
            self._model = get_model()
        return self._model

    def parse_policy_document(self, text: str) -> dict:
        """Call LLM to extract structured policy from free text.

        Returns:
            dict with keys: policy (RawPolicyDoc dict), warnings (list[str]),
            raw_llm_output (str|None)
        """
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = [
            SystemMessage(content=POLICY_PARSE_SYSTEM_PROMPT),
            HumanMessage(content=f"请解析以下企业报销政策文本：\n\n{text}"),
        ]

        response = self.model.invoke(messages)
        raw_output = str(response.content).strip()

        # Extract JSON from potential markdown fences
        json_str = raw_output
        if json_str.startswith("```"):
            json_str = re.sub(r"^```\w*\n?", "", json_str)
            json_str = re.sub(r"\n?```$", "", json_str)

        warnings: list[str] = []
        policy: RawPolicyDoc | None = None

        try:
            data = json.loads(json_str)
            policy = RawPolicyDoc(**data)
        except (json.JSONDecodeError, ValueError) as e:
            warnings.append(f"JSON 解析失败: {e}")
            policy = self._default_policy()
            warnings.append("已回退到默认政策")

        return {
            "policy": policy.model_dump() if policy else self._default_policy().model_dump(),
            "warnings": warnings,
            "raw_llm_output": raw_output,
        }

    @staticmethod
    def _default_policy() -> RawPolicyDoc:
        """Return a minimal default when parsing fails."""
        return RawPolicyDoc(
            doc_id="",
            title="Default policy",
            version="",
            domains=[],
        )

    # ------------------------------------------------------------------
    # New-format parse_for_draft — returns domains[].rules[]
    # ------------------------------------------------------------------

    def parse_for_draft(self, pdf_text: str) -> dict:
        """Parse PDF text and return a structured AI draft for PolicyVersion.ai_draft.

        Returns a dict matching the new ai_draft JSON schema:
        {
            "policy_doc": {
                "doc_id": "...",
                "title": "...",
                "version": "...",
                "domains": [{
                    "id": "...", "name": "...",
                    "rules": [{id, type, title, scope, condition, value, unit, raw_text,
                               confidence, ai_reasoning}, ...]
                }]
            },
            "warnings": [...],
            "metadata": {model, tokens_used, parse_time_ms}
        }
        """
        start = time.time()

        # Try the LLM parser
        try:
            result = self.parse_policy_document(pdf_text)
            policy = result.get("policy", {})
        except Exception:
            policy = {}
            result = {"warnings": ["LLM parsing failed"]}

        doc = policy if policy and policy.get("domains") else self._default_policy().model_dump()
        parse_time_ms = int((time.time() - start) * 1000)

        # Enrich each rule with AI metadata
        domains_data = []
        for domain in doc.get("domains", []):
            enriched_rules = []
            for rule in domain.get("rules", []):
                enriched_rules.append({
                    **rule,
                    "confidence": 0.8,
                    "ai_reasoning": "Extracted from policy document",
                })
            domains_data.append({**domain, "rules": enriched_rules})

        policy_doc = {
            "doc_id": doc.get("doc_id", ""),
            "title": doc.get("title", ""),
            "version": doc.get("version", ""),
            "domains": domains_data,
        }

        return {
            "policy_doc": policy_doc,
            "warnings": result.get("warnings", []),
            "metadata": {
                "model": "deepseek-chat",
                "tokens_used": 0,
                "parse_time_ms": parse_time_ms,
            },
        }

    # ------------------------------------------------------------------
    # Legacy: old flat expense_type parsing (keep for backward compat)
    # ------------------------------------------------------------------

    def parse_flat_policy_document(self, text: str) -> dict:
        """Same as parse_policy_document but returns old flat PolicyDocument format.

        Used by the /policy/parse endpoint for backward compatibility.
        """
        result = self.parse_policy_document(text)
        raw_doc = result.get("policy", {})

        # Convert new format → old flat expense_types
        expense_types = []
        for domain in raw_doc.get("domains", []):
            name = domain.get("name", "")
            code = self._domain_name_to_code(name, domain.get("id", ""))
            rules = domain.get("rules", [])

            ratio = 0.8
            cap = None
            approval_over = 0.0
            need_guest = False
            need_invoice = True
            need_attachment = False

            for rule in rules:
                rtype = rule.get("type", "")
                value = rule.get("value")
                raw = rule.get("raw_text", "")

                if rtype == "ratio" and value is not None:
                    ratio = value
                elif rtype == "limit" and value is not None:
                    cap = value
                elif rtype == "approval" and value is not None:
                    approval_over = value
                elif rtype == "requirement":
                    if "发票" in raw or "invoice" in raw.lower():
                        need_invoice = True
                    if "附件" in raw or "attachment" in raw.lower():
                        need_attachment = True
                    if "宾客" in raw or "guest" in raw.lower() or "客户" in raw:
                        need_guest = True

            expense_types.append({
                "code": code,
                "name": name,
                "reimbursement_ratio": ratio,
                "limit_per_person": None,
                "cap": cap,
                "approval_over": approval_over,
                "need_guest": need_guest,
                "need_invoice": need_invoice,
                "need_attachment": need_attachment,
                "enabled": True,
            })

        flat = {
            "version": raw_doc.get("version", "1.0"),
            "enterprise": "default",
            "description": raw_doc.get("title", ""),
            "expense_types": expense_types,
        }

        try:
            flat_doc = PolicyDocument(**flat)
        except Exception as e:
            warnings = result.get("warnings", []) + [f"Flat conversion warning: {e}"]
            flat_doc = PolicyDocument(
                version="1.0", enterprise="default", description="Parsing failed",
                expense_types=[],
            )
            return {
                "policy": flat_doc.model_dump(),
                "warnings": warnings,
                "raw_llm_output": result.get("raw_llm_output"),
            }

        return {
            "policy": flat_doc.model_dump(),
            "warnings": result.get("warnings", []),
            "raw_llm_output": result.get("raw_llm_output"),
        }

    @staticmethod
    def _domain_name_to_code(name: str, domain_id: str) -> str:
        """Map domain name to a code for backward-compatible flat conversion."""
        mapping = {
            "餐饮": "meals", "餐饮费": "meals", "餐费": "meals",
            "差旅": "travel", "差旅费": "travel", "出差": "travel",
            "交通": "transportation", "交通费": "transportation", "通勤": "transportation",
            "办公用品": "office_supplies", "办公": "office_supplies",
            "商务招待": "entertainment", "招待": "entertainment", "招待费": "entertainment",
        }
        for key, code in mapping.items():
            if key in name:
                return code
        return domain_id.lower().replace(" ", "_") if domain_id else "other"
