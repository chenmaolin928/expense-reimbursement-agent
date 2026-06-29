"""Notification service — simulated email sending.

Logs to notification_log table. In production, swap with SMTP/SendGrid/etc.
"""

from datetime import datetime
from sqlalchemy.orm import Session
from app.infrastructure.orm import NotificationLog


class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def send(
        self,
        recipient_email: str,
        event_type: str,
        subject: str,
        body: str,
        report_id: int | None = None,
    ) -> NotificationLog:
        log = NotificationLog(
            report_id=report_id,
            recipient_email=recipient_email,
            event_type=event_type,
            subject=subject,
            body=body,
            sent_at=datetime.utcnow(),
            is_sent=True,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_for_report(self, report_id: int):
        return (
            self.db.query(NotificationLog)
            .filter(NotificationLog.report_id == report_id)
            .order_by(NotificationLog.sent_at.desc())
            .all()
        )


def get_notification_service(db: Session) -> NotificationService:
    return NotificationService(db)
