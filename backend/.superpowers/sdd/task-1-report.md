# Task 1 — Repository Storage Backend Abstraction

## Changes

1. **NEW: `backend/app/services/policy_storage_backends.py`**
   - `PolicyStorageBackend` (ABC) — abstract interface: `get_policy`, `save_policy`, `get_expense_type`, `list_enterprises`
   - `JsonFileBackend` (concrete) — existing JSON file logic, moved out of PolicyRepository
   - `DatabaseBackend` (concrete) — reads/writes via SQLAlchemy Session, queries `Policy` + `PolicyVersion` tables

2. **MODIFIED: `backend/app/services/policy_repository.py`**
   - `.__init__` now accepts either a directory path (`str`, backward-compatible) or a `PolicyStorageBackend` instance
   - All four original methods delegate to `self._backend`
   - Added three convenience methods for DB-only operations: `get_version_history`, `get_policy_draft`, `publish_policy`

3. **MODIFIED: `backend/app/config.py`**
   - `PolicySettings` gained `policy_storage_backend: str = Field(default="json")`

## Test Results

```
57 passed in 105.57s
```

All callers continue to work unchanged — `PolicyRepository(str(policies_dir))` still works via `JsonFileBackend`.

## Skipped

- No DI wiring for `DatabaseBackend` — add when an admin UI or policy management workflow needs DB-backed policy storage.
- `PolicyStorageBackend` ABC only has one `from app.services.policy_storage_backends import` site — no separate ABC module, YAGNI for now.
