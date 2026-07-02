"""Policy Center API — manage enterprise reimbursement policies.

Endpoints:
    POST /policy/parse      — AI parse policy text → structured JSON
    GET  /policy/current    — Get current policy
    PUT  /policy/current    — Save policy (admin only)
    GET  /policy/enterprises — List enterprises
    GET  /policy/{enterprise} — Get policy by enterprise
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import _parse_auth_header, require_admin
from app.schemas.policy import (
    PolicyParseRequest,
    PolicyParseResponse,
    PolicySaveRequest,
    PolicyDocument,
    PolicyUploadResponse,
    PolicyDraft,
    PolicyListItem,
    PolicyDetail,
    PolicyVersionItem,
    PolicyVersionDetail,
    UpdateDraftRequest,
    NormalizeResponse,
    PublishResponse,
)
from app.services.policy_parser_service import PolicyParserService
from app.services.policy_repository import PolicyRepository
from app.services.policy_service import PolicyService
from app.services.policy_lifecycle import PolicyLifecycleService
from app.domain.enums import InvalidPolicyTransitionError
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


# ============================================================================
# New Policy Center endpoints (Phase 3+4)
# ============================================================================

@router.post("/upload", response_model=PolicyUploadResponse, status_code=201)
async def upload_policy_pdf(
    file: UploadFile = File(...),
    name: str = Form(default=""),
    enterprise: str = Form(default="default"),
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Upload a PDF file -> extract text -> build KB -> AI parse -> return PolicyVersion."""
    require_admin(auth)
    try:
        pdf_bytes = await file.read()
        svc = PolicyService()
        result = svc.create_from_pdf(
            pdf_bytes=pdf_bytes,
            filename=file.filename or "policy.pdf",
            created_by=auth["user_id"],
            enterprise=enterprise,
            name=name,
        )
        return PolicyUploadResponse(**result)
    except Exception as e:
        logger.exception("Policy upload failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=list[PolicyListItem])
def list_policies(
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """List all policies."""
    svc = PolicyService()
    items = svc.list_policies()
    return [PolicyListItem(**p) for p in items]


@router.get("/{policy_id}", response_model=PolicyDetail)
def get_policy_detail(
    policy_id: int,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Get policy detail."""
    svc = PolicyService()
    p = svc.get_policy(policy_id)
    if not p:
        raise HTTPException(status_code=404, detail="Policy not found")
    return PolicyDetail(**p)


@router.get("/{policy_id}/versions", response_model=list[PolicyVersionItem])
def list_policy_versions(
    policy_id: int,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """List versions for a policy."""
    svc = PolicyService()
    versions = svc.get_versions(policy_id)
    return [PolicyVersionItem(**v) for v in versions]


@router.get("/{policy_id}/versions/{version_id}", response_model=PolicyVersionDetail)
def get_version_detail(
    policy_id: int,
    version_id: int,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Get full version detail with ai_draft and policy_json."""
    svc = PolicyService()
    v = svc.get_version_detail(version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return PolicyVersionDetail(**v)


@router.post("/{policy_id}/versions/{version_id}/parse")
def reparse_version(
    policy_id: int,
    version_id: int,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Re-run AI parsing on a version."""
    require_admin(auth)
    svc = PolicyService()
    draft = svc.trigger_ai_parse(version_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Version not found or has no PDF text")
    return PolicyDraft(**draft)


@router.put("/{policy_id}/versions/{version_id}/draft")
def update_draft(
    policy_id: int,
    version_id: int,
    req: UpdateDraftRequest,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Manually edit the AI draft."""
    require_admin(auth)
    svc = PolicyService()
    ok = svc.update_draft(version_id, req.draft.model_dump())
    if not ok:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"message": "Draft updated"}


@router.post("/{policy_id}/versions/{version_id}/normalize", response_model=NormalizeResponse)
def normalize_version(
    policy_id: int,
    version_id: int,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Normalize AI draft -> policy_json."""
    require_admin(auth)
    svc = PolicyService()
    result = svc.normalize_draft(version_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Version not found or has no draft")
    return NormalizeResponse(**result)


@router.post("/{policy_id}/versions/{version_id}/publish", response_model=PublishResponse)
def publish_version(
    policy_id: int,
    version_id: int,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Publish a policy version."""
    require_admin(auth)
    svc = PolicyService()
    result = svc.publish(version_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Publish failed"))
    return PublishResponse(**result)


@router.post("/{policy_id}/versions/{version_id}/archive")
def archive_version(
    policy_id: int,
    version_id: int,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Archive a policy version."""
    require_admin(auth)
    svc = PolicyService()
    ok = svc.archive(version_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"message": "Archived"}


@router.post("/{policy_id}/versions/{version_id}/activate")
def activate_policy_version(
    policy_id: int,
    version_id: int,
    auth: dict = Depends(_parse_auth_header),
    db: Session = Depends(get_db),
):
    """Activate a specific version (publish draft, rollback archived, or confirm active).

    - DRAFT with policy_json → PUBLISHED
    - ARCHIVED → PUBLISHED (rollback)
    - PUBLISHED → no-op (version is already active)

    Side effect: previous active version is automatically archived.
    """
    require_admin(auth)
    lifecycle = PolicyLifecycleService(db)
    try:
        result = lifecycle.activate_version(
            policy_id=policy_id,
            version_id=version_id,
            actor_id=auth["user_id"],
        )
        if not result.success:
            raise HTTPException(status_code=404, detail=result.message)
        return {
            "success": result.success,
            "message": result.message,
            "previous_active_version_id": result.previous_active_version_id,
            "transition_id": result.transition_id,
        }
    except InvalidPolicyTransitionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ponytail: placed after numeric {policy_id} routes so FastAPI matches integers first
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
