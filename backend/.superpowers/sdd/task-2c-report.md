# Task 2C Report — PolicyPublisher + PolicyParser Extension

## Files Changed

### New: `backend/app/services/policy_publisher.py`
- `PolicyPublisher` class with `publish(version_id, repository)` and `rollback_publish(version_id)`
- `publish()` validates policy_json, archives old version, marks PUBLISHED, writes to backend
- `rollback_publish()` reverts to REVIEWING only if version is still current
- Lazy imports for `SessionLocal`, ORM models, enums — no top-level coupling

### Modified: `backend/app/services/policy_parser_service.py`
- Added `parse_for_draft(pdf_text)` method to existing `PolicyParserService` class
- Tries `parse_policy_document()` first; falls back to default 5 expense types if empty/error
- Enriches each expense type with `confidence`, `source_text`, `ai_reasoning`
- Returns ai_draft dict compatible with `PolicyVersion.ai_draft` JSONB column
- All 3 existing methods untouched

## Verification

| Check | Result |
|-------|--------|
| `python -c "from app.services.policy_publisher import PolicyPublisher; from app.services.policy_parser_service import PolicyParserService; print('OK')"` | OK |
| `pytest tests/` (full suite) | 57 passed (same as baseline) |
| `pytest tests/test_policy_engine.py tests/test_calculator_engine.py tests/test_rule_engine.py` | 15/15 passed |
| `parse_for_draft('')` smoke test | Returns 5 expense types with enriched fields (confidence, source_text, ai_reasoning) |
