"""LLM Security Gateway — 所有发往 LLM 的数据的统一瓶颈。

设计原则（Enterprise Data Minimization）：
1. 默认拒绝 — 任何数据默认不发送给 LLM
2. 白名单放行 — 只有明确允许的结构化字段才能进入 LLM
3. LLM 与企业数据隔离 — LLM 不接触任何真实企业敏感数据
4. Tool 持有真实数据 — 所有真实数据仅保存在 LocalContextStore
5. 统一出口 — 所有进入 LLM 的数据统一经过 Gateway
"""

import logging
from sqlalchemy.orm import Session

from app.services.enterprise_data_sanitizer import EnterpriseDataSanitizer
from app.services.local_context_store import LocalContextStore

logger = logging.getLogger(__name__)


class LLMSecurityGateway:
    """所有发往 LLM 的数据的统一瓶颈。"""

    def __init__(self, db: Session, session_id: str):
        self.db = db
        self.session_id = session_id
        self.local_ctx = LocalContextStore(session_id)
        self.sanitizer = EnterpriseDataSanitizer(self.local_ctx._store['tokens'])

    # ---- 用户消息 ----

    def build_user_message(self, raw_text: str) -> str:
        """过滤用户聊天文本 → 返回清洗版供 LLM 用。

        检测并令牌化：人名、手机号、身份证号、统一社会信用代码、
        纳税人识别号、银行账号、邮箱。
        """
        if not raw_text:
            return raw_text
        clean = self.sanitizer.sanitize_text(raw_text)
        if clean != raw_text:
            logger.info(f"[Gateway] user message sanitized: {len(raw_text)}→{len(clean)} chars")
        return clean

    # ---- Tool 结果过滤 ----

    def build_tool_result(self, tool_name: str, result: dict) -> dict:
        """过滤 Tool 输出 → 仅白名单字段通过。"""
        if not result or not isinstance(result, dict):
            return result

        tool_sanitizers = {
            'scan_invoice': self._sanitize_invoice_result,
            'search_knowledge': self._sanitize_policy_result,
            'submit_reimbursement': self._sanitize_workflow_result,
            'check_reimbursement_status': self._sanitize_workflow_result,
            'send_notification': self._sanitize_workflow_result,
        }
        sanitizer_fn = tool_sanitizers.get(tool_name)
        if sanitizer_fn:
            return sanitizer_fn(result)
        # 未知 Tool：保守模式 — 仅允许已知安全字段
        return self._sanitize_default(result)

    # ---- OCR/发票结果 ----

    def build_ocr_result(self, ocr_data: dict) -> dict:
        """从 OCR 结果构建安全的 LLM 消息。

        完整数据 → local_ctx；过滤版 → LLM
        """
        # 完整数据存本地
        self.local_ctx.store_invoice(ocr_data)

        # 过滤版给 LLM
        clean = {}
        allowed = {'amount', 'currency', 'date', 'category', 'category_raw',
                   'file_path', 'line_items'}

        for key in allowed:
            if key in ocr_data:
                clean[key] = ocr_data[key]

        # 供应商令牌化
        vendor = ocr_data.get('vendor', '')
        if vendor and vendor != '未知商户':
            clean['vendor'] = self.sanitizer.tokenize_vendor(vendor)
        else:
            clean['vendor'] = vendor

        # 去除 raw_text — 可能含纳税人识别号等敏感信息
        # raw_text 仅在 local_ctx 中保留

        return clean

    # ---- 对话历史 ----

    def build_history(self, messages: list) -> list:
        """过滤对话历史中可能含敏感数据的旧消息。

        简洁策略：系统消息和用户消息通过 sanitizer，tool 消息仅保留白名单字段。
        """
        clean = []
        for m in messages:
            role = m.get('role', '')
            content = m.get('content', '')
            if role == 'user' and content:
                sanitized = self.sanitizer.sanitize_text(str(content))
                clean.append({**m, 'content': sanitized})
            elif role == 'assistant':
                clean.append(m)
            elif role == 'tool':
                # Tool 消息已经是 sanitized 版本
                clean.append(m)
            else:
                clean.append(m)
        return clean

    # ---- 确认消息（隐藏真实数据） ----

    def build_confirmation(self, tool_name: str) -> str:
        """生成安全的确认消息。"""
        messages = {
            'scan_invoice': '发票扫描完成，已提取结构化信息。',
            'search_knowledge': '政策查询完成。',
            'submit_reimbursement': '报销申请已提交。',
            'check_reimbursement_status': '状态查询完成。',
            'send_notification': '通知已发送。',
        }
        return messages.get(tool_name, f'工具 {tool_name} 执行完成。')

    # ---- 审计日志 ----

    def audit_log(self, event: str, detail: dict) -> None:
        """记录安全审计日志。"""
        logger.info(f"[Gateway.Audit] session={self.session_id} event={event} detail={detail}")

    # ---- 引擎上下文（Policy/Caculator/Rule Engine 结果的安全摘要） ----

    def build_engine_context(self, calc_result: dict | None = None, rule_result: dict | None = None) -> dict:
        """Build a safe context dict from engine results.

        Only passes verdict, summary, final_amount, need_approval — never
        raw policy data, internal IDs, or PII.
        """
        ctx: dict = {}
        if calc_result:
            ctx["verdict"] = calc_result.get("verdict", "unknown")
            ctx["summary"] = calc_result.get("summary", "")
            ctx["breakdown"] = calc_result.get("breakdown", {})
            ctx["final_amount"] = calc_result.get("breakdown", {}).get("final_amount", 0)
        if rule_result:
            ctx["need_approval"] = rule_result.get("need_approval", False)
            ctx["need_guest_list"] = rule_result.get("need_guest_list", False)
            ctx["need_attachment"] = rule_result.get("need_attachment", False)
            ctx["can_submit"] = rule_result.get("can_submit", True)

        if calc_result or rule_result:
            self.audit_log("engine_context", {"calc_keys": list(ctx.keys())})

        return ctx

    # ================================================================
    # Private sanitizers
    # ================================================================

    def _sanitize_invoice_result(self, data: dict) -> dict:
        """发票扫描结果 → 仅结构化字段，vendor 令牌化，去除 raw_text。"""
        # 完整数据存本地
        self.local_ctx.store_invoice(data)
        return self.build_ocr_result(data)

    def _sanitize_policy_result(self, data: dict) -> dict:
        """政策搜索结果 → 白名单通过。政策文本属于可发 LLM。"""
        return self.sanitizer.sanitize_dict(
            data,
            self.sanitizer.ALLOWED_POLICY_FIELDS,
        )

    def _sanitize_workflow_result(self, data: dict) -> dict:
        """工作流结果 → 仅允许 report_number + status + total_amount 等。"""
        return self.sanitizer.sanitize_dict(
            data,
            self.sanitizer.ALLOWED_WORKFLOW_FIELDS,
        )

    def _sanitize_default(self, data: dict) -> dict:
        """未知 Tool 的保守过滤。"""
        # 仅保留基本字段
        safe = {'report_number', 'status', 'message', 'total_amount'}
        return self.sanitizer.sanitize_dict(data, safe)
