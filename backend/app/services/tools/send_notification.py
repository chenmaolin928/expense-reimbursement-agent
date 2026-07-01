"""Send notification tool — email notification for reimbursement outcomes."""

from pydantic import BaseModel, Field

from app.services.tools.base import BaseTool, get_tool_context


class SendNotificationInput(BaseModel):
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body content")


class SendNotificationTool(BaseTool):
    name = "send_notification"
    description = (
        "Send email notification to the current user about their reimbursement status. "
        "Use this at the end of processing to notify the user of the outcome. "
        "The system automatically determines the recipient email — DO NOT ask for it."
    )
    args_schema = SendNotificationInput

    def _run(self, subject: str, body: str) -> dict:
        from app.database import SessionLocal
        from app.infrastructure.orm import NotificationLog

        ctx = get_tool_context()
        recipient = ctx.user_email or "employee@company.cn"

        db = SessionLocal()
        try:
            log = NotificationLog(
                recipient_email=recipient,
                event_type="agent_notification",
                subject=subject,
                body=body,
            )
            db.add(log)
            db.commit()

            return {"sent": True, "recipient": recipient, "subject": subject}
        finally:
            db.close()
