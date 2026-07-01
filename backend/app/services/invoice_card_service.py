"""Invoice card service — builds structured invoice data cards for the frontend.

Assembles OCR results + desensitization info into the invoice_card SSE event format.
"""

from typing import Any


def build_invoice_card(ocr_result: dict, desensitization: dict | None = None) -> dict:
    """Build an invoice_card event payload from OCR scan results.

    Args:
        ocr_result: Raw output from OCR service scan()
        desensitization: Optional desensitization mapping (entity_type -> token)

    Returns:
        Dict matching the invoice_card SSE event format
    """
    fields = {
        "vendor": {"label": "商家", "value": ocr_result.get("vendor", "未知")},
        "amount": {"label": "金额", "value": ocr_result.get("amount", 0)},
        "date": {"label": "日期", "value": ocr_result.get("date", "未知")},
        "category": {"label": "品类", "value": _category_label(ocr_result.get("category_raw", "other"))},
    }

    return {
        "type": "invoice_card",
        "data": {
            "fields": fields,
            "desensitization": desensitization or {},
            "invoice_path": ocr_result.get("file_path", ""),
        },
    }


_CATEGORY_LABELS: dict[str, str] = {
    "meals": "餐饮",
    "travel": "差旅",
    "transportation": "交通",
    "office_supplies": "办公用品",
    "entertainment": "商务招待",
    "other": "其他",
}


def _category_label(category_raw: str) -> str:
    return _CATEGORY_LABELS.get(category_raw, category_raw)
