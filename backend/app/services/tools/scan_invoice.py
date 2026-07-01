"""Scan invoice tool — OCR-based invoice data extraction."""

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
        return ocr.scan(file_path)
