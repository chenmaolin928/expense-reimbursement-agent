# Task 2b Report: RuleNormalizer Service

**Date**: 2026-07-02
**File**: `backend/app/services/rule_normalizer.py`

## Summary

Created `RuleNormalizer` — transforms AI-parsed draft policy data into clean, executable policy JSON by stripping metadata, validating schema, and filling defaults.

## File Created

| File | Purpose |
|------|---------|
| `backend/app/services/rule_normalizer.py` | AI draft normalization service |

## Classes

| Class | Purpose |
|-------|---------|
| `NormalizationResult` | Dataclass: `policy_json`, `warnings`, `excluded_count`, `is_valid` |
| `RuleNormalizer` | Normalizer with single `normalize(ai_draft: dict) -> NormalizationResult` method |

## What it does

1. **Strips AI metadata** — removes `confidence`, `source_text`, `ai_reasoning` from each expense type
2. **Excludes unknown codes** — expense types with codes not in `VALID_EXPENSE_CODES` are removed and counted in `excluded_count`
3. **Validates ratio** — clamps `reimbursement_ratio` to [0, 1] with warning
4. **Fills defaults** — `enabled`, `max_amount`, `reimbursement_ratio`, `requires_approval`, `approval_threshold`, `requires_guest_list`, `notes`
5. **Propagates warnings** — upstream AI draft warnings are carried forward
6. **Sets `is_valid`** — `False` if zero expense types survive normalization

## Verification

- Import and basic function: PASS
- Metadata stripping: PASS
- Unknown code exclusion: PASS
- Ratio clamping: PASS
- Default filling: PASS
- Empty draft handling: PASS
- Upstream warning propagation: PASS

Test suite: 34 passed, 26 errors (all 26 errors are pre-existing DB fixture issues in `conftest.py:clean_db`, unrelated to this file).
