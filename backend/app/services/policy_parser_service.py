"""Policy Parser Service — AI-powered natural language → structured JSON.

Calls the LLM to extract structured expense type rules from free-text policy documents.
"""

import json
import logging

from app.infrastructure.llm_client import get_model
from app.schemas.policy import PolicyDocument, PolicyExpenseType

logger = logging.getLogger(__name__)

POLICY_PARSE_SYSTEM_PROMPT = """你是一个企业报销政策解析器。你的任务是从给定的政策文本中提取结构化的报销规则。

请严格按照以下 JSON Schema 输出，不要输出任何其他内容：

```json
{
  "version": "1.0",
  "enterprise": "default",
  "description": "政策摘要",
  "expense_types": [
    {
      "code": "费用类型代码（英文）",
      "name": "费用类型名称（中文）",
      "reimbursement_ratio": 报销比例(0.0-1.0),
      "limit_per_person": 人均限额(null表示无),
      "cap": 单次报销金额上限(null表示无),
      "approval_over": 超过此金额需审批(0=不需要),
      "need_guest": 是否需要宾客名单(true/false),
      "need_invoice": 是否需要发票(true/false),
      "need_attachment": 是否需要附件(true/false),
      "enabled": 是否启用(true)
    }
  ]
}
```

**重要规则：**
1. 费用类型 code 必须使用英文：meals, travel, transportation, office_supplies, entertainment
2. 如果文本中提到两种以上费用类型，全部提取
3. 如果文本中没有明确的数字，使用合理默认值（餐饮60%，其他80%）
4. 商务招待(entertainment) 默认 need_guest=true, need_attachment=true, approval_over=1000
5. 如果某字段文本中未提及，根据费用类型常识填充

只输出 JSON，不要输出其他内容。"""


class PolicyParserService:
    """Parse natural-language policy text into structured PolicyDocument via LLM."""

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
            dict with keys: policy (PolicyDocument), warnings (list[str]),
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
            import re
            json_str = re.sub(r"^```\w*\n?", "", json_str)
            json_str = re.sub(r"\n?```$", "", json_str)

        warnings: list[str] = []
        policy: PolicyDocument | None = None

        try:
            data = json.loads(json_str)
            policy = self.validate_parsed_policy(data)
        except (json.JSONDecodeError, ValueError) as e:
            warnings.append(f"JSON 解析失败: {e}")
            # Fallback: return default policy
            policy = self._default_policy()
            warnings.append("已回退到默认政策")

        return {
            "policy": policy.model_dump() if policy else self._default_policy().model_dump(),
            "warnings": warnings,
            "raw_llm_output": raw_output,
        }

    def validate_parsed_policy(self, data: dict) -> PolicyDocument:
        """Validate and normalize parsed policy data into PolicyDocument."""
        result: list[str] = []

        expense_types = []
        for item in data.get("expense_types", []):
            # Ensure required fields have defaults
            item.setdefault("reimbursement_ratio", 0.8)
            item.setdefault("cap", None)
            item.setdefault("limit_per_person", None)
            item.setdefault("approval_over", 0)
            item.setdefault("need_guest", False)
            item.setdefault("need_invoice", True)
            item.setdefault("need_attachment", False)
            item.setdefault("enabled", True)

            # Validate ratio range
            ratio = item.get("reimbursement_ratio", 0.8)
            if not (0.0 <= ratio <= 1.0):
                result.append(f"{item.get('code')}: reimbursement_ratio {ratio} 超出范围，已调整")
                item["reimbursement_ratio"] = max(0.0, min(1.0, ratio))

            expense_types.append(PolicyExpenseType(**item))

        return PolicyDocument(
            version=data.get("version", "1.0"),
            enterprise=data.get("enterprise", "default"),
            description=data.get("description", ""),
            expense_types=expense_types,
        )

    @staticmethod
    def _default_policy() -> PolicyDocument:
        """Return a minimal default policy when parsing fails."""
        return PolicyDocument(
            version="1.0",
            enterprise="default",
            description="Default fallback policy",
            expense_types=[
                PolicyExpenseType(code="meals", name="餐饮", reimbursement_ratio=0.6, cap=500),
                PolicyExpenseType(code="travel", name="差旅", reimbursement_ratio=0.8, cap=500),
                PolicyExpenseType(code="transportation", name="交通", reimbursement_ratio=0.8, cap=200),
                PolicyExpenseType(code="office_supplies", name="办公用品", reimbursement_ratio=0.8, cap=500),
                PolicyExpenseType(code="entertainment", name="商务招待", reimbursement_ratio=0.8, cap=1000,
                                  approval_over=1000, need_guest=True, need_attachment=True),
            ],
        )
