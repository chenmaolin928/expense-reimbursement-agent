"""OCR service — simulated invoice scanning with interface for future real OCR.

Currently MOCK: generates realistic extraction data based on file_path hash.
To switch to real OCR, implement the IOCRService interface from domain/interfaces.py
and swap the dependency in chat.py.
"""

from abc import ABC, abstractmethod


class IOCRService(ABC):
    """Interface for OCR services. Implement for PaddleOCR, Tesseract, etc."""

    @abstractmethod
    def scan(self, file_path: str) -> dict:
        ...


class MockOCRService(IOCRService):
    """Simulated OCR for demo/testing. Extracts fake but realistic invoice data."""

    def scan(self, file_path: str) -> dict:
        import hashlib
        hash_val = int(hashlib.md5(file_path.encode()).hexdigest()[:8], 16)

        categories = ["office_supplies", "meals", "travel", "transportation", "entertainment"]
        vendors = {
            "office_supplies": ["Office Depot", "Staples", "晨光文具"],
            "meals": ["海底捞", "星巴克", "麦当劳"],
            "travel": ["汉庭酒店", "如家", "锦江之星"],
            "transportation": ["滴滴出行", "曹操出行"],
            "entertainment": ["俏江南", "大董烤鸭"],
        }
        cat = categories[hash_val % len(categories)]
        vendor_list = vendors.get(cat, ["Unknown"])
        vendor = vendor_list[hash_val % len(vendor_list)]

        amounts = [45.00, 128.50, 234.50, 380.00, 520.00, 890.00]
        amount = amounts[hash_val % len(amounts)]

        return {
            "file_path": file_path,
            "vendor": vendor,
            "amount": amount,
            "currency": "CNY",
            "date": "2026-06-25",
            "category_raw": cat,
            "line_items": [{"description": f"{vendor} purchase", "total": amount}],
        }
