"""Local Context Store — 每个 session 的安全上下文存储。

所有企业真实敏感数据仅存于此。LLM 永远不可见。
Tool 执行时从此读取真实数据。
"""

from typing import Any


class LocalContextStore:
    """Session-scoped secure context store. LLM never accesses this data."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._store: dict[str, Any] = {
            'employee': {},        # 员工信息
            'invoice': {},         # 完整 OCR 结果（含 raw_text）
            'invoice_list': [],    # 多发票场景
            'supplement': {},      # 用户填写的补充表单数据
            'vendors': {},         # token → 真实供应商名
            'organizations': {},   # token → 真实组织名
            'persons': {},         # token → 真实人名
            'tokens': {},          # 所有令牌映射 {token: (real_value, entity_type)}
        }

    # ---- 便捷访问 ----

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    # ---- 发票 ----

    def store_invoice(self, invoice_data: dict) -> str:
        """存储完整发票数据，返回索引键"""
        idx = len(self._store['invoice_list'])
        self._store['invoice_list'].append(invoice_data)
        self._store['invoice'] = invoice_data  # 最新一个
        return f"invoice_{idx}"

    def get_invoice(self, index: int = -1) -> dict | None:
        lst = self._store.get('invoice_list', [])
        if not lst:
            return None
        return lst[index]

    # ---- 令牌解析 ----

    def resolve_token(self, token: str) -> str | None:
        """解析令牌 → 真实值"""
        entry = self._store['tokens'].get(token)
        if entry:
            return entry[0]  # (real_value, entity_type)
        return None

    def get_real_vendor(self, token: str) -> str:
        """解析供应商令牌"""
        return self.resolve_token(token) or token

    # ---- 补充表单 ----

    def store_supplement(self, data: dict) -> None:
        self._store['supplement'] = data

    def get_supplement(self) -> dict:
        return self._store.get('supplement', {})

    # ---- 序列化（调试用，绝不发给 LLM） ----

    def to_debug(self) -> dict:
        return {
            'session_id': self.session_id,
            'keys': list(self._store.keys()),
            'token_count': len(self._store['tokens']),
            'invoice_count': len(self._store['invoice_list']),
        }
