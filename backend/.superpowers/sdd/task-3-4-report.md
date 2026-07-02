# Task 3-4 Report: PolicyService + Schema Extension + API Endpoints

## Summary

Created PolicyService as lifecycle coordinator, extended schemas with 12 new DTOs, and added 11 new API endpoints for policy lifecycle management.

## Files Changed

### 1. `backend/app/schemas/policy.py` — Schema Extension
Appended 12 new Pydantic schemas (existing schemas untouched):
- `DraftExpenseType` — AI draft expense type with confidence/source fields
- `PolicyDraft` — AI draft container
- `PolicyUploadResponse` — PDF upload response
- `PolicyListItem` — Policy list summary row
- `PolicyDetail` — Full policy detail
- `PolicyVersionItem` — Version row in history
- `PolicyVersionDetail` — Full version with ai_draft/policy_json
- `UpdateDraftRequest` — Manual draft edit payload
- `NormalizeResponse` — Normalization result
- `PublishResponse` — Publish result

### 2. `backend/app/services/policy_service.py` — New File
Lifecycle coordinator orchestrating Policy + PolicyVersion through all phases:
- `create_from_pdf()` — Upload PDF, extract text, create Policy + Version, build KB, AI parse
- `trigger_ai_parse()` — Re-run AI parsing on existing version
- `update_draft()` — Manual draft edit
- `normalize_draft()` — Draft -> policy_json via RuleNormalizer
- `publish()` — Publish via PolicyPublisher
- `archive()` — Archive a version
- Query methods: `list_policies`, `get_policy`, `get_versions`, `get_version_detail`, `get_current_policy`

### 3. `backend/app/api/policy.py` — API Extension
Added 11 new endpoints (all existing endpoints preserved):
- `POST /policy/upload` — Multipart PDF upload (File + Form fields)
- `GET /policy/list` — List all policies
- `GET /policy/{policy_id}` — Policy detail (int path)
- `GET /policy/{policy_id}/versions` — Version history
- `GET /policy/{policy_id}/versions/{version_id}` — Full version detail
- `POST /policy/{policy_id}/versions/{version_id}/parse` — Re-parse version
- `PUT /policy/{policy_id}/versions/{version_id}/draft` — Edit draft
- `POST /policy/{policy_id}/versions/{version_id}/normalize` — Normalize draft
- `POST /policy/{policy_id}/versions/{version_id}/publish` — Publish version
- `POST /policy/{policy_id}/versions/{version_id}/archive` — Archive version

Route ordering: legacy `GET /policy/{enterprise}` (string catch-all) moved to end of file so numeric `{policy_id}` routes match first. Existing `GET /policy/enterprises` stays before it.

## Verification

- Import check: `python -c "from app.services.policy_service import PolicyService; from app.schemas.policy import PolicyDraft, PolicyUploadResponse; print('OK')"` — OK
- Tests: `python -m pytest tests/ -v --tb=short` — **57 passed**, 0 failed
