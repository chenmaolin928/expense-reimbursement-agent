"""Policy Center API — manage enterprise reimbursement policies.

Endpoints:
    POST /policy/parse      — AI parse policy text → structured JSON
    GET  /policy/current    — Get current policy
    PUT  /policy/current    — Save policy (admin only)
    GET  /policy/enterprises — List enterprises
    GET  /policy/{enterprise} — Get policy by enterprise
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import _parse_auth_header, require_admin
from app.schemas.policy import (
    PolicyParseRequest,
    PolicyParseResponse,
    PolicySaveRequest,
    PolicyDocument,
)
from app.services.policy_parser_service import PolicyParserService
from app.services.policy_repository import PolicyRepository
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/policy", tags=["policy"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def _get_policy_repo() -> PolicyRepository:
    return PolicyRepository(settings.policy.policies_dir)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/parse", response_model=PolicyParseResponse)
def parse_policy(
    req: PolicyParseRequest,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """AI-powered: parse natural-language policy text into structured JSON."""
    require_admin(auth)
    parser = PolicyParserService()
    result = parser.parse_policy_document(req.text)
    return PolicyParseResponse(
        policy=PolicyDocument(**result["policy"]),
        warnings=result.get("warnings", []),
        raw_llm_output=result.get("raw_llm_output"),
    )


@router.get("/current", response_model=PolicyDocument)
def get_current_policy(
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Get the current active policy document."""
    repo = _get_policy_repo()
    data = repo.get_policy("default")
    if not data:
        raise HTTPException(status_code=404, detail="未找到默认政策文档")
    return PolicyDocument(**data)


@router.put("/current", response_model=PolicyDocument)
def save_current_policy(
    req: PolicySaveRequest,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Save/update the policy document (admin only)."""
    require_admin(auth)
    repo = _get_policy_repo()
    data = req.policy.model_dump()
    repo.save_policy(req.enterprise, data)
    logger.info(f"Policy saved for enterprise '{req.enterprise}'")
    return req.policy


@router.get("/enterprises", response_model=list[str])
def list_enterprises(
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """List all enterprises that have policy files."""
    repo = _get_policy_repo()
    return repo.list_enterprises()


@router.get("/{enterprise}", response_model=PolicyDocument)
def get_enterprise_policy(
    enterprise: str,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Get policy for a specific enterprise."""
    repo = _get_policy_repo()
    data = repo.get_policy(enterprise)
    if not data:
        raise HTTPException(status_code=404, detail=f"未找到企业 '{enterprise}' 的政策文档")
    return PolicyDocument(**data)
