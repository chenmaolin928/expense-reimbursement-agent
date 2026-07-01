"""PII Desensitization Service — strips sensitive employee data before cloud requests.

CRITICAL: This is the security boundary. All data leaving for the cloud LLM
must pass through this service. Employee names, IDs, emails, departments,
and bank accounts are replaced with opaque tokens.

The mapping table (pii_mappings) stays in the local SQLite DB and NEVER
leaves the internal network.
"""

import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.infrastructure.orm import PiiMapping, Employee
from app.config import settings


# PII field definitions — which employee columns are sensitive
PII_FIELDS = [
    ("employee_name", "full_name"),
    ("employee_id", "employee_code"),
    ("department", "department"),
    ("email", "email"),
    ("bank_account", "bank_account"),
]


def _generate_batch_id() -> str:
    return f"BATCH-{uuid.uuid4().hex[:12]}"


def _generate_token() -> str:
    return f"ENT-{uuid.uuid4().hex[:8]}"


class DesensitizationService:
    """Strips PII from data and stores token mappings for later re-association."""

    def __init__(self, db: Session):
        self.db = db

    def desensitize_employee(self, employee_id: int) -> dict:
        """Create token mappings for an employee. Returns {batch_id, tokens}.

        The returned tokens are safe to include in cloud LLM context.
        Real employee data is stored in pii_mappings table (local only).
        """
        emp = self.db.query(Employee).filter(Employee.id == employee_id).first()
        if not emp:
            return {"batch_id": "", "tokens": {}, "error": "Employee not found"}

        batch_id = _generate_batch_id()
        tokens = {}
        expires_at = datetime.utcnow() + timedelta(days=settings.pii.mapping_retention_days)

        for entity_type, attr_name in PII_FIELDS:
            real_value = str(getattr(emp, attr_name, ""))
            token = _generate_token()
            tokens[entity_type] = token

            mapping = PiiMapping(
                batch_id=batch_id,
                entity_type=entity_type,
                real_value=real_value,
                token=token,
                expires_at=expires_at,
            )
            self.db.add(mapping)

        self.db.commit()
        return {"batch_id": batch_id, "tokens": tokens}

    def re_associate(self, batch_id: str) -> dict:
        """Look up real employee data from a batch of tokens.

        Used AFTER the cloud LLM returns a decision, to map tokens
        back to real employee records for internal system execution.
        """
        mappings = (
            self.db.query(PiiMapping)
            .filter(PiiMapping.batch_id == batch_id)
            .all()
        )
        if not mappings:
            return {"error": "Batch not found or expired"}

        result = {}
        for m in mappings:
            result[m.entity_type] = m.real_value

        return result

    def cleanup_expired(self) -> int:
        """Delete expired PII mappings. Returns count of deleted rows."""
        count = (
            self.db.query(PiiMapping)
            .filter(PiiMapping.expires_at < datetime.utcnow())
            .delete()
        )
        self.db.commit()
        return count

    def get_batch_info(self, batch_id: str) -> dict:
        """Get metadata about a token batch (without revealing real values)."""
        mappings = (
            self.db.query(PiiMapping)
            .filter(PiiMapping.batch_id == batch_id)
            .all()
        )
        if not mappings:
            return {"error": "Batch not found"}
        return {
            "batch_id": batch_id,
            "entity_count": len(mappings),
            "created_at": str(mappings[0].created_at),
            "expires_at": str(mappings[0].expires_at),
            "entity_types": [m.entity_type for m in mappings],
        }


def get_desensitization_service(db: Session) -> DesensitizationService:
    return DesensitizationService(db)
