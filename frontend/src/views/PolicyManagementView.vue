<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { policyApi, type PolicyListItem, type PolicyVersionItem, type PolicyVersionDetail, type DraftExpenseType, type PolicyDraft } from '../api/policy'

const router = useRouter()

// ── State ──────────────────────────────────────────
const policies = ref<PolicyListItem[]>([])
const selectedPolicyId = ref<number | null>(null)
const selectedVersionId = ref<number | null>(null)
const versionDetail = ref<PolicyVersionDetail | null>(null)
const versions = ref<PolicyVersionItem[]>([])
const uploading = ref(false)
const normalizing = ref(false)
const publishing = ref(false)
const draftExpenseTypes = reactive<DraftExpenseType[]>([])
const newPolicyName = ref('')
const errorMsg = ref('')
const showUpload = ref(true) // default: show upload until a policy is selected
const loading = ref(false)

onMounted(() => { loadPolicies() })

// ── Policy List ────────────────────────────────────
async function loadPolicies() {
  loading.value = true
  try { policies.value = await policyApi.list() } catch (e: any) { errorMsg.value = 'Failed to load policies' }
  finally { loading.value = false }
}

function startNew() {
  selectedPolicyId.value = null
  selectedVersionId.value = null
  versionDetail.value = null
  versions.value = []
  draftExpenseTypes.length = 0
  showUpload.value = true
  errorMsg.value = ''
}

async function selectPolicy(id: number) {
  selectedPolicyId.value = id
  selectedVersionId.value = null
  versionDetail.value = null
  draftExpenseTypes.length = 0
  showUpload.value = false
  errorMsg.value = ''
  try { versions.value = await policyApi.listVersions(id) } catch { versions.value = [] }
}

async function selectVersion(versionId: number) {
  if (!selectedPolicyId.value) return
  selectedVersionId.value = versionId
  errorMsg.value = ''
  try {
    versionDetail.value = await policyApi.getVersion(selectedPolicyId.value, versionId)
    // populate editable draft from ai_draft
    draftExpenseTypes.length = 0
    if (versionDetail.value.ai_draft?.expense_types) {
      for (const et of versionDetail.value.ai_draft.expense_types) {
        draftExpenseTypes.push({ ...et })
      }
    }
  } catch (e: any) {
    versionDetail.value = null
    errorMsg.value = 'Failed to load version'
  }
}

// ── Upload ─────────────────────────────────────────
async function handleUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  errorMsg.value = ''
  try {
    const res = await policyApi.uploadPdf(file, newPolicyName.value || undefined)
    await loadPolicies()
    selectedPolicyId.value = res.policy_id
    selectedVersionId.value = res.version_id
    showUpload.value = false
    newPolicyName.value = ''
    // load versions & detail
    versions.value = await policyApi.listVersions(res.policy_id)
    versionDetail.value = await policyApi.getVersion(res.policy_id, res.version_id)
    draftExpenseTypes.length = 0
    if (versionDetail.value.ai_draft?.expense_types) {
      for (const et of versionDetail.value.ai_draft.expense_types) {
        draftExpenseTypes.push({ ...et })
      }
    }
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || e.message || 'Upload failed'
  } finally {
    uploading.value = false
    input.value = ''
  }
}

// ── Draft Editor ───────────────────────────────────
function confColor(c: number): string {
  if (c >= 0.9) return 'high'
  if (c >= 0.7) return 'medium'
  return 'low'
}

async function saveDraft() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  errorMsg.value = ''
  try {
    const draft: PolicyDraft = {
      enterprise: 'default',
      description: '',
      expense_types: [...draftExpenseTypes],
      warnings: [],
      metadata: {},
    }
    await policyApi.updateDraft(selectedPolicyId.value, selectedVersionId.value, draft)
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Save failed'
  }
}

async function doNormalize() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  normalizing.value = true
  errorMsg.value = ''
  try {
    await policyApi.normalize(selectedPolicyId.value, selectedVersionId.value)
    // refresh version detail to get updated policy_json
    versionDetail.value = await policyApi.getVersion(selectedPolicyId.value, selectedVersionId.value)
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Normalize failed'
  } finally {
    normalizing.value = false
  }
}

// ── Publish ────────────────────────────────────────
async function doPublish() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  if (!confirm('Publish this policy version? It will become the active policy.')) return
  publishing.value = true
  errorMsg.value = ''
  try {
    await policyApi.publish(selectedPolicyId.value, selectedVersionId.value)
    // refresh
    versionDetail.value = await policyApi.getVersion(selectedPolicyId.value, selectedVersionId.value)
    await loadPolicies()
    versions.value = await policyApi.listVersions(selectedPolicyId.value)
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Publish failed'
  } finally {
    publishing.value = false
  }
}

  // no version count in list item yet — future API may include it
</script>

<template>
  <div class="policy-shell">
    <!-- Top bar -->
    <header class="policy-top">
      <div class="top-left">
        <div class="top-brand" />
        <button @click="router.push('/admin')" class="btn-back">← Admin</button>
        <span class="top-title">Policy Center</span>
      </div>
    </header>

    <div class="policy-body">
      <!-- Left: Policy List -->
      <aside class="policy-sidebar">
        <button @click="startNew" class="btn-new">+ New Policy</button>

        <div v-if="policies.length === 0 && !loading" class="sidebar-empty">
          No policies yet. Upload a PDF to get started.
        </div>

        <div v-for="p in policies" :key="p.id"
             :class="['policy-item', { active: p.id === selectedPolicyId }]"
             @click="selectPolicy(p.id)">
          <div class="policy-item-info">
            <span class="policy-name">{{ p.name || 'Unnamed Policy' }}</span>
          </div>
          <span :class="['status-badge', p.status]">{{ p.status }}</span>
        </div>
      </aside>

      <!-- Right: Content -->
      <main class="policy-content">
        <!-- Error -->
        <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>

        <!-- Upload area -->
        <div v-if="showUpload" class="upload-zone">
          <h3>Upload Policy PDF</h3>
          <p class="upload-desc">Upload a company reimbursement policy document (PDF). The AI will parse it into structured expense types.</p>
          <div class="upload-drop">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="upload-icon">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            <p>Drop PDF here or click to browse</p>
          </div>
          <div class="upload-row">
            <label class="btn-primary file-label">
              Choose PDF
              <input type="file" accept=".pdf" @change="handleUpload" hidden />
            </label>
            <input v-model="newPolicyName" placeholder="Policy name (optional)" class="input-dark" />
          </div>
          <p v-if="uploading" class="upload-status">Uploading & parsing...</p>
        </div>

        <!-- Version + editor area -->
        <div v-if="selectedPolicyId && !showUpload" class="version-area">
          <!-- Version tabs -->
          <div class="version-tabs" v-if="versions.length > 0">
            <button v-for="v in versions" :key="v.id"
                    :class="['tab', { active: v.id === selectedVersionId }]"
                    @click="selectVersion(v.id)">
              v{{ v.version_number }}
              <span :class="['status-dot', v.status]" />
            </button>
          </div>
          <div v-else class="panel-empty">No versions yet.</div>

          <!-- Draft editor -->
          <div v-if="versionDetail?.ai_draft" class="draft-editor">
            <div v-if="versionDetail.ai_draft.warnings?.length" class="warnings">
              <div v-for="w in versionDetail.ai_draft.warnings" :key="w" class="warn-item">⚠️ {{ w }}</div>
            </div>

            <h3 class="section-title">Expense Types ({{ draftExpenseTypes.length }})</h3>

            <div v-if="draftExpenseTypes.length === 0" class="panel-empty">No expense types found in draft.</div>

            <div v-for="(et, i) in draftExpenseTypes" :key="et.code || i" class="expense-card">
              <div class="card-header">
                <span class="card-name">{{ et.name }} <code class="card-code">{{ et.code }}</code></span>
                <span :class="['confidence', confColor(et.confidence)]">
                  {{ (et.confidence * 100).toFixed(0) }}%
                </span>
              </div>
              <div class="card-fields">
                <label class="field">Reimbursement Ratio
                  <input v-model.number="et.reimbursement_ratio" type="number" min="0" max="1" step="0.05" class="input-dark field-input" />
                </label>
                <label class="field">Max Amount
                  <input v-model.number="et.max_amount" type="number" class="input-dark field-input" />
                </label>
                <label class="field">Approval Over
                  <input v-model.number="et.approval_over" type="number" class="input-dark field-input" />
                </label>
                <label class="field checkbox-field">
                  <input v-model="et.need_invoice" type="checkbox" /> Need Invoice
                </label>
                <label class="field checkbox-field">
                  <input v-model="et.need_guest" type="checkbox" /> Need Guest List
                </label>
                <label class="field checkbox-field">
                  <input v-model="et.need_attachment" type="checkbox" /> Need Attachment
                </label>
                <label class="field checkbox-field">
                  <input v-model="et.enabled" type="checkbox" /> Enabled
                </label>
              </div>
              <div class="card-source" v-if="et.source_text">
                <span class="source-label">Source:</span> {{ et.source_text }}
              </div>
            </div>

            <div class="editor-actions">
              <button @click="saveDraft" class="btn-primary">Save Draft</button>
              <button @click="doNormalize" :disabled="normalizing" class="btn-secondary">
                {{ normalizing ? 'Normalizing...' : 'Normalize → Policy JSON' }}
              </button>
            </div>
          </div>

          <!-- No draft loaded -->
          <div v-if="selectedVersionId && !versionDetail?.ai_draft && !errorMsg" class="panel-empty">
            Select a version to edit its draft.
          </div>

          <!-- Policy JSON preview -->
          <details v-if="versionDetail?.policy_json" class="json-preview">
            <summary>Policy JSON (published rules)</summary>
            <pre>{{ JSON.stringify(versionDetail.policy_json, null, 2) }}</pre>
          </details>

          <!-- Publish bar -->
          <div v-if="versionDetail?.policy_json && versionDetail.status !== 'published'" class="publish-bar">
            <p>This version has been normalized and is ready to publish.</p>
            <button @click="doPublish" :disabled="publishing" class="btn-publish">
              {{ publishing ? 'Publishing...' : 'Publish' }}
            </button>
          </div>
          <div v-if="versionDetail?.status === 'published'" class="published-badge">
            Published on {{ versionDetail.published_at ? new Date(versionDetail.published_at).toLocaleDateString() : '—' }}
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
* { box-sizing: border-box; margin: 0; padding: 0; }

.policy-shell {
  min-height: 100vh;
  background: #0a0a0e;
  color: #e4e4e7;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Top bar — matches AdminView */
.policy-top {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 32px; height: 56px;
  background: #0f0f14; border-bottom: 1px solid rgba(255,255,255,0.04);
}
.top-left { display: flex; align-items: center; gap: 12px; }
.top-brand {
  width: 24px; height: 24px;
  background: linear-gradient(135deg, #6366f1, #a78bfa);
  border-radius: 6px;
}
.top-title { font-size: 14px; font-weight: 600; color: #fff; letter-spacing: -0.2px; }
.btn-back {
  background: rgba(99,102,241,0.1); color: #a5b4fc; border: none;
  padding: 6px 12px; border-radius: 8px; font-size: 12px; cursor: pointer;
  transition: background 0.15s;
}
.btn-back:hover { background: rgba(99,102,241,0.2); }

/* Body layout: sidebar + main */
.policy-body {
  display: flex; height: calc(100vh - 56px);
}

/* ── Sidebar ─────────────────────────────────── */
.policy-sidebar {
  width: 260px; min-width: 260px;
  background: #0f0f14; border-right: 1px solid rgba(255,255,255,0.04);
  padding: 16px; overflow-y: auto;
  display: flex; flex-direction: column; gap: 8px;
}
.btn-new {
  width: 100%; padding: 10px 14px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: box-shadow 0.2s;
}
.btn-new:hover { box-shadow: 0 4px 16px rgba(99,102,241,0.3); }

.policy-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px; border-radius: 10px; cursor: pointer;
  transition: background 0.15s; gap: 8px;
}
.policy-item:hover { background: rgba(255,255,255,0.03); }
.policy-item.active { background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.2); }
.policy-item-info { flex: 1; min-width: 0; }
.policy-name {
  font-size: 13px; font-weight: 500; color: #e4e4e7;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;
}
.status-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 6px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;
}
.status-badge.draft { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.35); }
.status-badge.published { background: rgba(52,211,153,0.12); color: #34d399; }
.status-badge.archived { background: rgba(248,113,113,0.1); color: #fca5a5; }
.status-badge.normalized { background: rgba(99,102,241,0.12); color: #a5b4fc; }

.sidebar-empty {
  font-size: 12px; color: rgba(255,255,255,0.2); text-align: center; padding: 20px 0;
}

/* ── Main content ────────────────────────────── */
.policy-content {
  flex: 1; overflow-y: auto; padding: 32px;
}

.error-bar {
  background: rgba(248,113,113,0.1); border: 1px solid rgba(248,113,113,0.2);
  border-radius: 10px; padding: 10px 16px; margin-bottom: 20px;
  font-size: 13px; color: #fca5a5;
}

/* Upload */
.upload-zone {
  max-width: 520px; margin: 0 auto; text-align: center;
}
.upload-zone h3 {
  font-size: 16px; font-weight: 600; color: #fff; margin-bottom: 8px;
}
.upload-desc {
  font-size: 13px; color: rgba(255,255,255,0.3); margin-bottom: 24px;
}
.upload-drop {
  border: 2px dashed rgba(255,255,255,0.08); border-radius: 14px;
  padding: 40px 20px; margin-bottom: 16px; cursor: pointer;
  transition: border-color 0.2s;
}
.upload-drop:hover { border-color: rgba(99,102,241,0.3); }
.upload-drop p { font-size: 13px; color: rgba(255,255,255,0.2); margin-top: 8px; }
.upload-icon { width: 32px; height: 32px; color: rgba(255,255,255,0.15); }
.upload-row {
  display: flex; gap: 10px; align-items: center; justify-content: center;
}
.file-label {
  cursor: pointer; display: inline-block; flex-shrink: 0;
}
.upload-status {
  margin-top: 12px; font-size: 13px; color: rgba(99,102,241,0.6);
}

/* Version tabs */
.version-area { display: flex; flex-direction: column; gap: 20px; }
.version-tabs { display: flex; gap: 6px; flex-wrap: wrap; }
.tab {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 14px; border-radius: 8px; font-size: 13px; cursor: pointer;
  border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.02);
  color: rgba(255,255,255,0.4); transition: all 0.15s;
}
.tab:hover { background: rgba(255,255,255,0.04); color: #e4e4e7; }
.tab.active {
  background: rgba(99,102,241,0.1); border-color: rgba(99,102,241,0.2);
  color: #a5b4fc;
}
.status-dot {
  width: 6px; height: 6px; border-radius: 50%; display: inline-block;
}
.status-dot.draft { background: rgba(255,255,255,0.3); }
.status-dot.published { background: #34d399; }
.status-dot.archived { background: #f87171; }
.status-dot.normalized { background: #6366f1; }

/* Draft editor */
.draft-editor { display: flex; flex-direction: column; gap: 16px; }
.section-title { font-size: 15px; font-weight: 600; color: #fff; }
.warnings { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
.warn-item {
  font-size: 12px; color: #fbbf24; padding: 6px 10px;
  background: rgba(251,191,36,0.08); border-radius: 8px;
}

/* Expense card */
.expense-card {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 12px; padding: 16px;
}
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 12px;
}
.card-name { font-size: 14px; font-weight: 600; color: #e4e4e7; }
.card-code { font-size: 12px; color: rgba(255,255,255,0.3); margin-left: 6px; }
.confidence {
  font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: 6px;
}
.confidence.high { background: rgba(52,211,153,0.12); color: #34d399; }
.confidence.medium { background: rgba(251,191,36,0.12); color: #fbbf24; }
.confidence.low { background: rgba(248,113,113,0.12); color: #fca5a5; }

.card-fields {
  display: flex; flex-wrap: wrap; gap: 12px;
}
.field {
  font-size: 12px; color: rgba(255,255,255,0.4);
  display: flex; flex-direction: column; gap: 4px;
}
.field-input { width: 140px; }
.checkbox-field {
  flex-direction: row; align-items: center; gap: 6px; cursor: pointer;
  color: rgba(255,255,255,0.5);
}
.checkbox-field input[type="checkbox"] {
  accent-color: #6366f1;
}

.card-source {
  margin-top: 10px; font-size: 12px; color: rgba(255,255,255,0.25);
}
.source-label { color: rgba(255,255,255,0.15); }

.editor-actions {
  display: flex; gap: 10px; margin-top: 8px;
}

/* Shared buttons */
.btn-primary {
  padding: 10px 16px; background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: box-shadow 0.2s;
}
.btn-primary:hover { box-shadow: 0 4px 16px rgba(99,102,241,0.3); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary {
  padding: 10px 16px; border-radius: 10px; font-size: 13px; font-weight: 500;
  cursor: pointer; border: 1px solid rgba(99,102,241,0.2);
  background: rgba(99,102,241,0.08); color: #a5b4fc; transition: all 0.15s;
}
.btn-secondary:hover { background: rgba(99,102,241,0.15); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-publish {
  padding: 10px 20px; background: linear-gradient(135deg, #34d399, #10b981);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: box-shadow 0.2s;
}
.btn-publish:hover { box-shadow: 0 4px 16px rgba(52,211,153,0.3); }
.btn-publish:disabled { opacity: 0.5; cursor: not-allowed; }

.input-dark {
  padding: 10px 14px;
  background: #18181b; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; color: #fff; font-size: 13px; outline: none;
  transition: border-color 0.2s;
}
.input-dark:focus { border-color: rgba(99,102,241,0.4); }
.input-dark::placeholder { color: rgba(255,255,255,0.15); }

/* JSON preview */
.json-preview {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 12px; padding: 16px;
}
.json-preview summary {
  font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.6); cursor: pointer;
  margin-bottom: 12px;
}
.json-preview pre {
  font-size: 12px; color: rgba(255,255,255,0.4); max-height: 400px; overflow: auto;
  font-family: 'Consolas', 'Courier New', monospace; white-space: pre-wrap;
  background: #18181b; border-radius: 8px; padding: 14px;
}

/* Publish bar */
.publish-bar {
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(52,211,153,0.06); border: 1px solid rgba(52,211,153,0.12);
  border-radius: 12px; padding: 16px 20px;
}
.publish-bar p { font-size: 13px; color: rgba(255,255,255,0.4); }
.published-badge {
  font-size: 13px; color: #34d399; padding: 12px 16px;
  background: rgba(52,211,153,0.06); border-radius: 10px;
}

.panel-empty {
  font-size: 13px; color: rgba(255,255,255,0.2); text-align: center; padding: 40px 0;
}
</style>
