# Task 5b Report — PolicyManagementView.vue

**Status**: Complete

## What was built

Single-file Vue 3 component at `frontend/src/views/PolicyManagementView.vue` using `<script setup lang="ts">` with Composition API.

## Features implemented

1. **Policy List Sidebar** — loads all policies via `policyApi.list()`, click to select, active state highlighting, status badges (draft/published/archived/normalized), "New Policy" button opens upload area.

2. **PDF Upload Area** — drag-drop visual zone with file input, optional name field, calls `policyApi.uploadPdf()`, auto-selects new policy after upload.

3. **Draft Editor** — expense type cards with editable fields: reimbursement_ratio (0-1 number), max_amount, approval_over, checkboxes for need_invoice/need_guest/need_attachment/enabled. Each card shows confidence badge (green >=0.9, yellow >=0.7, red <0.7) and source text.

4. **Policy JSON Preview** — collapsible `<details>` showing `versionDetail.policy_json` as formatted JSON.

5. **Publish Bar** — shows when policy_json exists and status is not "published". Confirmation dialog before publish. Published badge with date shown when status is "published".

6. **Version Timeline** — tabs for each version with status dots, click to load version detail.

## Design decisions

- Uses `reactive()` for `draftExpenseTypes` so two-way binding with checkboxes works naturally (checkbox needs `.value` access pattern that `ref<array>` handles poorly with index access).
- Dark theme matches AdminView exactly: same colors (`#0a0a0e` background, `#0f0f14` cards, `#18181b` inputs, indigo/purple accent gradient).
- No external component imports — fully self-contained scoped component.
- `confColor()` returns CSS class string ('high'/'medium'/'low').

## File changed
- `frontend/src/views/PolicyManagementView.vue` — new file (created)

## Router
Route `/admin/policy` already configured in `frontend/src/router/index.ts` pointing to this component — no router changes needed.
