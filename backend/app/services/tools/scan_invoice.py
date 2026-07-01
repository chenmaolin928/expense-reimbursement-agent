"""Scan invoice tool — OCR-based invoice data extraction.

Security: raw_text is stripped before returning to LLM.
Full OCR data is stored in LocalContextStore via the gateway.
"""

from pydantic import BaseModel, Field

from app.services.tools.base import BaseTool, get_tool_context


class ScanInvoiceInput(BaseModel):
    file_path: str = Field(..., description="Path to the uploaded invoice file")


class ScanInvoiceTool(BaseTool):
    name = "scan_invoice"
    description = (
        "OCR invoice/receipt image to extract structured data. "
        "Use this whenever a user uploads an invoice/receipt image or PDF. "
        "Returns vendor name, amount, date, category, and line items. "
        "Always call this FIRST before making any reimbursement decisions."
    )
    args_schema = ScanInvoiceInput

    def _run(self, file_path: str) -> dict:
        from app.services.ocr_service import get_ocr_service

        ocr = get_ocr_service()
        full_result = ocr.scan(file_path)

        # ---- Security Gateway: strip raw_text, tokenize vendor ----
        ctx = get_tool_context()
        gateway = ctx.security_gateway
        if gateway:
            return gateway.build_ocr_result(full_result)

        # Fallback: manual stripping when no gateway
        safe = {
            'amount': full_result.get('amount', 0),
            'currency': full_result.get('currency', 'CNY'),
            'date': full_result.get('date', ''),
            'category_raw': full_result.get('category_raw', 'other'),
            'file_path': full_result.get('file_path', file_path),
            'vendor': full_result.get('vendor', '未知商户'),
            'line_items': full_result.get('line_items', []),
        }
        return safe
