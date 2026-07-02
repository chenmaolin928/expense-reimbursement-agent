# Phase 0 — Policy Center Data Model Report

## What was changed

- **`backend/app/domain/enums.py`**: Added `PolicyStatus` enum (5 values: DRAFT, PARSING, REVIEWING, PUBLISHED, ARCHIVED).
- **`backend/app/infrastructure/orm.py`**: Three changes:
  1. Imported `PolicyStatus` alongside existing enum imports.
  2. Added `policy_version_id` nullable FK column to `KnowledgeBase` model (before the `documents` relationship).
  3. Added `Policy` and `PolicyVersion` ORM models after the existing `StatusTransition` class.

## Test results

```
57 passed, 65 warnings in 103.90s (0:01:43)
```

All 57 tests pass. The one SAWarning about unresolvable FK dependency between `knowledge_bases` and `policy_versions` is expected — SQLite doesn't support ALTER for cycle resolution, and our cleanup uses `drop_all`. No functional impact.

## Concerns

- **Circular FK warning**: `policy_version_id` on `KnowledgeBase` points to `policy_versions`, while `kb_id` on `PolicyVersion` points to `knowledge_bases`. This creates a circular FK dependency. SQLite handles it fine at runtime (both are nullable), but the `drop_all` cleanup order warns. If this becomes a problem, adding `use_alter=True` on one of the FKs would resolve it. Not blocking for now.
