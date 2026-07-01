"""Enterprise Data Sanitizer — 白名单过滤 + 令牌化。

设计原则：默认拒绝，显式允许。只有白名单中的字段才能进入 LLM 上下文。
所有真实敏感数据替换为不透明令牌，映射关系仅保存在 LocalContextStore。
"""

import re
import uuid
from typing import Any


def _gen_token(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:6]}"


class EnterpriseDataSanitizer:
    """基于白名单的数据过滤器。"""

    # ---- 白名单：仅允许这些字段进入 LLM ----

    ALLOWED_INVOICE_FIELDS = {
        'amount', 'currency', 'date', 'category', 'category_raw',
        'is_vat_invoice', 'tax_amount', 'file_path', 'line_items',
    }

    ALLOWED_POLICY_FIELDS = {
        'verdict', 'summary', 'policy_refs', 'breakdown', 'total_results',
        'results', 'chunk_id', 'snippet', 'kb_name', 'filename', 'score',
    }

    ALLOWED_WORKFLOW_FIELDS = {
        'report_number', 'status', 'total_amount', 'message',
        'approval_step', 'required_action', 'submitted_at', 'timeline',
    }

    # ---- PII 检测模式 ----
    # 中文姓名（2-4个常见姓+名组合）
    CN_NAME_PATTERN = re.compile(
        r'(?:[王李张刘陈杨黄赵周吴徐孙马胡朱郭何罗高林郑梁谢唐许冯宋韩]'
        r'[一-鿿]{1,2})'
    )
    # 手机号
    PHONE_PATTERN = re.compile(r'1[3-9]\d{9}')
    # 身份证
    ID_PATTERN = re.compile(r'\d{17}[\dXx]')
    # 统一社会信用代码
    USCC_PATTERN = re.compile(r'[0-9A-HJ-NPQRTUWXY]{2}\d{6}[0-9A-HJ-NPQRTUWXY]{10}')
    # 邮箱
    EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    # 银行账号
    BANK_PATTERN = re.compile(r'\d{16,19}')
    # 纳税人识别号
    TAX_ID_PATTERN = re.compile(r'[0-9A-Za-z]{15,20}')

    def __init__(self, token_store: dict):
        """token_store: 共享的令牌映射字典（通常来自 LocalContextStore._store['tokens']）"""
        self.tokens = token_store

    # ---- 自由文本清洗 ----

    def sanitize_text(self, text: str) -> str:
        """检测并令牌化自由文本中的企业敏感数据。

        返回清洗后的文本。令牌映射通过 self.tokens 获取。
        """
        if not text:
            return text

        clean = text

        # 手机号 → PHONE-xxx
        def _replace_phone(m: re.Match) -> str:
            return self.tokenize_entity(m.group(), 'phone')

        clean = self.PHONE_PATTERN.sub(_replace_phone, clean)

        # 身份证 → ID-xxx
        def _replace_id(m: re.Match) -> str:
            return self.tokenize_entity(m.group(), 'id_card')

        clean = self.ID_PATTERN.sub(_replace_id, clean)

        # 邮箱 → EMAIL-xxx
        def _replace_email(m: re.Match) -> str:
            return self.tokenize_entity(m.group(), 'email')

        clean = self.EMAIL_PATTERN.sub(_replace_email, clean)

        # 统一社会信用代码
        def _replace_uscc(m: re.Match) -> str:
            return self.tokenize_entity(m.group(), 'uscc')

        clean = self.USCC_PATTERN.sub(_replace_uscc, clean)

        # 纳税人识别号（在身份证和USCC之后，避免重复匹配）
        def _replace_tax(m: re.Match) -> str:
            # 不重复令牌化已有的令牌
            if m.group().startswith('ID-') or m.group().startswith('TAX-'):
                return m.group()
            return self.tokenize_entity(m.group(), 'tax_id')

        clean = self.TAX_ID_PATTERN.sub(_replace_tax, clean)

        # 中文姓名 → PERSON-xxx（最后处理，避免误伤其他模式）
        def _replace_name(m: re.Match) -> str:
            return self.tokenize_entity(m.group(), 'person')

        clean = self.CN_NAME_PATTERN.sub(_replace_name, clean)

        # 银行账号 → BANK-xxx（在去除其他数字模式后）
        def _replace_bank(m: re.Match) -> str:
            # 不重复令牌化已有的令牌
            if any(m.group().startswith(p) for p in ('PHONE-', 'ID-', 'TAX-', 'BANK-')):
                return m.group()
            return self.tokenize_entity(m.group(), 'bank_account')

        clean = self.BANK_PATTERN.sub(_replace_bank, clean)

        return clean

    # ---- 字典白名单过滤 ----

    def sanitize_dict(self, data: dict, allowed_keys: set) -> dict:
        """仅保留白名单 key，对值中的文本进行令牌化处理。"""
        if not data:
            return {}
        result = {}
        for key in allowed_keys:
            if key in data:
                value = data[key]
                if isinstance(value, str):
                    result[key] = self.sanitize_text(value)
                elif isinstance(value, dict):
                    # 嵌套 dict 不做 key 过滤，仅清洗文本值
                    result[key] = {k: self.sanitize_text(v) if isinstance(v, str) else v
                                   for k, v in value.items()}
                elif isinstance(value, list):
                    result[key] = [
                        self.sanitize_text(item) if isinstance(item, str) else item
                        for item in value
                    ]
                else:
                    result[key] = value
        return result

    # ---- 令牌化 ----

    def tokenize_entity(self, real_value: str, entity_type: str) -> str:
        """将真实值替换为不透明令牌。如已存在映射则复用。"""
        # 先查找是否已经令牌化过
        for token, (val, typ) in self.tokens.items():
            if val == real_value and typ == entity_type:
                return token

        token = _gen_token(entity_type.upper())
        self.tokens[token] = (real_value, entity_type)
        return token

    # ---- 令牌化供应商/组织名 ----

    def tokenize_vendor(self, vendor_name: str) -> str:
        """令牌化供应商/商户名 → VENDOR-xxx"""
        if not vendor_name or vendor_name == '未知商户':
            return vendor_name
        return self.tokenize_entity(vendor_name, 'vendor')

    def tokenize_organization(self, org_name: str) -> str:
        """令牌化组织/公司名 → ORG-xxx"""
        if not org_name:
            return org_name
        return self.tokenize_entity(org_name, 'organization')
