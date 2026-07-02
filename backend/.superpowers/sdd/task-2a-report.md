# Task 2a Report — KnowledgeBuilder Service

## Status: Done

## File created

`backend/app/services/knowledge_builder.py`

## What it does

`KnowledgeBuilder` orchestrates KnowledgeBase lifecycle for PolicyVersion records:

- `build_for_version(version_id, pdf_text, created_by)` — creates KB, chunks+embeds text, links `kb_id` back to PolicyVersion
- `rebuild_for_version(version_id)` — deletes old KB and rebuilds from stored `pdf_content`
- `delete_for_version(version_id)` — removes KB and clears the link

## Method signature corrections

The task spec assumed `KnowledgeService.create_kb()` and `KnowledgeService.add_document()` return a KB with `.id`. Actual signatures:

| Assumed | Actual |
|---------|--------|
| `ks.create_kb(name=..., description=..., created_by=...)` | `ks.create_base(name, description, created_by)` returns `KnowledgeBase` |
| Returns KB with `.id` | `create_base` returns `KnowledgeBase` with `.id` -- same shape, different name |

`add_document(kb_id, filename, content)` matches the spec exactly.

## Verification

- Import check: `python -c "from app.services.knowledge_builder import KnowledgeBuilder; print('OK')"` passes
- Full test suite: **36 passed** (same as before this change). 2 pre-existing failures + 25 pre-existing errors are all SQLAlchemy `OperationalError` — test database/env issues, unrelated to this file.
