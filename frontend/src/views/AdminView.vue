<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'
import { policyApi, type PolicyListItem, type PolicyVersionItem, type PolicyVersionDetail, type DraftExpenseType, type PolicyDraft } from '../api/policy'
import { kbApi, type KbInfo, type KbDocument, type KbSearchResult } from '../api/knowledge'

const router = useRouter()
const auth = useAuthStore()

// ── Stats ──────────────────────────────────────────
const stats = ref<any>({})

// ── Policy Center ──────────────────────────────────
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
const showUpload = ref(true)
const loading = ref(false)
const uploadSummary = ref<{ kb_id: number | null; policy_name: string; version_number: number } | null>(null)

// ── Current KB (right panel) ───────────────────────
const currentKbInfo = ref<KbInfo | null>(null)
const currentKbDocs = ref<KbDocument[]>([])
const currentKbLoading = ref(false)

// ── KB Search (right panel) ────────────────────────
const kbSearchQ = ref('')
const kbSearchResults = ref<KbSearchResult[]>([])
const kbSearching = ref(false)

// ── All Knowledge Bases ────────────────────────────
const kbName = ref('')
const kbDesc = ref('')
const kbs = ref<any[]>([])
const uploadingDoc = ref<number | null>(null)
const expandedKb = ref<number | null>(null)

// ── Doc chunk expansion (shared) ───────────────────
const expandedDocs = ref<Set<number>>(new Set())
const chunkDetails = ref<Map<number, any[]>>(new Map())

// ── Search Debug ───────────────────────────────────
const searchQuery = ref('')
const searchTopK = ref(5)
const searchThreshold = ref(0)
const searchKbId = ref<number | null>(null)
const searchMode = ref<'normal' | 'raw'>('normal')
const searching = ref(false)
const searchResults = ref<any[]>([])
const searchMeta = ref<any>(null)
const sortField = ref<'score' | 'distance'>('score')
const sortDir = ref<-1 | 1>(-1)
const sortedResults = computed(() => {
  const arr = [...searchResults.value]
  arr.sort((a, b) => {
    const va = sortField.value === 'score' ? (a.score ?? a.cosine_similarity ?? 0) : (a.distance ?? 999)
    const vb = sortField.value === 'score' ? (b.score ?? b.cosine_similarity ?? 0) : (b.distance ?? 999)
    return (va - vb) * sortDir.value
  })
  return arr
})

// ── Lifecycle ──────────────────────────────────────
onMounted(async () => { await Promise.all([loadPolicies(), loadKBs(), loadStats()]) })

async function loadStats() {
  try { const res = await api.get('/admin/stats'); stats.value = res.data } catch {}
}

// ── Policy Center ──────────────────────────────────
async function loadPolicies() {
  loading.value = true
  try { policies.value = await policyApi.list() } catch { errorMsg.value = 'Failed to load policies' }
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
  uploadSummary.value = null
  clearCurrentKb()
}

async function selectPolicy(id: number) {
  selectedPolicyId.value = id
  selectedVersionId.value = null
  versionDetail.value = null
  draftExpenseTypes.length = 0
  showUpload.value = false
  errorMsg.value = ''
  uploadSummary.value = null
  clearCurrentKb()
  try { versions.value = await policyApi.listVersions(id) } catch { versions.value = [] }
}

async function selectVersion(versionId: number) {
  if (!selectedPolicyId.value) return
  selectedVersionId.value = versionId
  errorMsg.value = ''
  clearCurrentKb()
  try {
    versionDetail.value = await policyApi.getVersion(selectedPolicyId.value, versionId)
    draftExpenseTypes.length = 0
    if (versionDetail.value.ai_draft?.expense_types) {
      for (const et of versionDetail.value.ai_draft.expense_types) {
        draftExpenseTypes.push({ ...et })
      }
    }
    if (versionDetail.value.kb_id) await loadCurrentKb(versionDetail.value.kb_id)
  } catch {
    versionDetail.value = null
    errorMsg.value = 'Failed to load version'
  }
}

async function handleUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  errorMsg.value = ''
  try {
    const res = await policyApi.uploadPdf(file, newPolicyName.value || undefined)
    await loadPolicies()
    await loadKBs() // refresh KB list too
    selectedPolicyId.value = res.policy_id
    selectedVersionId.value = res.version_id
    showUpload.value = false
    newPolicyName.value = ''
    uploadSummary.value = { kb_id: res.kb_id, policy_name: res.message, version_number: res.version_number }
    versions.value = await policyApi.listVersions(res.policy_id)
    versionDetail.value = await policyApi.getVersion(res.policy_id, res.version_id)
    draftExpenseTypes.length = 0
    if (versionDetail.value.ai_draft?.expense_types) {
      for (const et of versionDetail.value.ai_draft.expense_types) {
        draftExpenseTypes.push({ ...et })
      }
    }
    if (res.kb_id) await loadCurrentKb(res.kb_id)
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || e.message || 'Upload failed'
  } finally {
    uploading.value = false
    input.value = ''
  }
}

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
      enterprise: 'default', description: '',
      expense_types: [...draftExpenseTypes], warnings: [], metadata: {},
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
    versionDetail.value = await policyApi.getVersion(selectedPolicyId.value, selectedVersionId.value)
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Normalize failed'
  } finally {
    normalizing.value = false
  }
}

async function doPublish() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  if (!confirm('Publish this policy version?')) return
  publishing.value = true
  errorMsg.value = ''
  try {
    await policyApi.publish(selectedPolicyId.value, selectedVersionId.value)
    versionDetail.value = await policyApi.getVersion(selectedPolicyId.value, selectedVersionId.value)
    await loadPolicies()
    versions.value = await policyApi.listVersions(selectedPolicyId.value)
  } catch (e: any) {
    errorMsg.value = e.response?.data?.detail || 'Publish failed'
  } finally {
    publishing.value = false
  }
}

// ── Current KB Panel ───────────────────────────────
async function loadCurrentKb(kbId: number) {
  currentKbLoading.value = true
  try {
    const [info, docs] = await Promise.all([
      kbApi.listBases().then(all => all.find(b => b.id === kbId) || null),
      kbApi.listDocuments(kbId),
    ])
    currentKbInfo.value = info
    currentKbDocs.value = docs
  } catch { /* non-critical */ }
  finally { currentKbLoading.value = false }
}

function clearCurrentKb() {
  currentKbInfo.value = null
  currentKbDocs.value = []
  currentKbLoading.value = false
  kbSearchQ.value = ''
  kbSearchResults.value = []
}

async function doKbSearch() {
  if (!kbSearchQ.value.trim() || !currentKbInfo.value?.id) return
  kbSearching.value = true
  try {
    kbSearchResults.value = await kbApi.search(kbSearchQ.value.trim(), currentKbInfo.value.id, 5)
  } catch { kbSearchResults.value = [] }
  finally { kbSearching.value = false }
}

// ── All Knowledge Bases ────────────────────────────
async function loadKBs() {
  try { const res = await api.get('/knowledge/bases'); kbs.value = res.data } catch {}
}

async function createKB() {
  if (!kbName.value.trim()) return
  await api.post('/knowledge/bases', { name: kbName.value, description: kbDesc.value })
  kbName.value = ''; kbDesc.value = ''
  await loadKBs()
}

async function deleteKB(id: number) {
  await api.delete(`/knowledge/bases/${id}`)
  await loadKBs()
}

async function uploadDoc(kbId: number, e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files?.length) return
  uploadingDoc.value = kbId
  const form = new FormData()
  form.append('file', input.files[0])
  await api.post(`/knowledge/bases/${kbId}/documents`, form)
  uploadingDoc.value = null; input.value = ''
  await loadKBs()
  if (expandedKb.value === kbId) await loadDocs(kbId)
}

async function loadDocs(kbId: number) {
  const res = await api.get(`/knowledge/bases/${kbId}/documents`)
  kbs.value = kbs.value.map(kb => kb.id === kbId ? { ...kb, _docs: res.data } : kb)
}

async function chromaStats() {
  try {
    const res = await api.get('/knowledge/chroma-stats')
    alert(JSON.stringify(res.data, null, 2))
  } catch {}
}

async function toggleKb(kbId: number) {
  if (expandedKb.value === kbId) { expandedKb.value = null; return }
  expandedKb.value = kbId
  await loadDocs(kbId)
}

// ── Doc chunk toggle (shared) ──────────────────────
async function toggleDocChunks(docId: number) {
  if (expandedDocs.value.has(docId)) {
    expandedDocs.value.delete(docId)
    return
  }
  expandedDocs.value.add(docId)
  if (!chunkDetails.value.has(docId)) {
    try {
      const res = await kbApi.getChunks(docId)
      chunkDetails.value.set(docId, res.chunks)
    } catch {
      chunkDetails.value.set(docId, [])
    }
  }
}

// ── Search Debug ───────────────────────────────────
async function doSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  try {
    const params: any = { q: searchQuery.value.trim() }
    if (searchKbId.value !== null) params.kb_id = searchKbId.value
    if (searchMode.value === 'raw') {
      params.top_k = searchTopK.value
      if (searchThreshold.value > 0) params.threshold = searchThreshold.value
      const res = await api.get('/knowledge/chroma-search-raw', { params })
      searchResults.value = res.data.results || []
      searchMeta.value = { total_results: res.data.total_results, top_k: res.data.top_k, threshold: res.data.threshold, kb_id_filter: res.data.kb_id_filter }
    } else {
      params.top_k = searchTopK.value
      if (searchThreshold.value > 0) params.threshold = searchThreshold.value
      const res = await api.get('/knowledge/search', { params })
      searchResults.value = res.data
      searchMeta.value = { total_results: res.data.length, top_k: searchTopK.value, threshold: searchThreshold.value, kb_id_filter: searchKbId.value }
    }
  } catch (e: any) {
    alert('Search failed: ' + (e.response?.data?.detail || e.message))
    searchResults.value = []
    searchMeta.value = null
  } finally {
    searching.value = false
  }
}

function scoreColor(score: number): string {
  if (score >= 0.8) return '#34d399'
  if (score >= 0.6) return '#fbbf24'
  return '#f87171'
}

// ── Misc ───────────────────────────────────────────
function logout() { auth.logout(); router.push('/login') }

const statusLabels: Record<string, string> = {
  draft: 'Draft', submitted: 'Submitted', manager_approval: 'Manager Review',
  finance_approval: 'Finance Review', approved: 'Approved', paid: 'Paid', rejected: 'Rejected',
}
function statusClassName(key: string | number): string { return String(key) }
</script>

<template>
  <div class="admin-shell">
    <!-- Top bar -->
    <header class="admin-top">
      <div class="top-left">
        <div class="top-brand" />
        <span class="top-title">ExpenseFlow Admin</span>
      </div>
      <div class="top-right">
        <span class="top-role">{{ auth.role }}</span>
        <button @click="logout" class="btn-logout">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>
    </header>

    <div class="admin-body">
      <!-- Stats -->
      <section class="stat-grid">
        <div class="stat-card">
          <div class="stat-icon reports">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <div class="stat-body">
            <span class="stat-value">{{ stats.total_reports || 0 }}</span>
            <span class="stat-label">Total Reports</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon employees">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
          <div class="stat-body">
            <span class="stat-value">{{ stats.total_employees || 0 }}</span>
            <span class="stat-label">Employees</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon amount">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
          </div>
          <div class="stat-body">
            <span class="stat-value">¥{{ (stats.total_reimbursed || 0).toLocaleString() }}</span>
            <span class="stat-label">Total Reimbursed</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon users">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/></svg>
          </div>
          <div class="stat-body">
            <span class="stat-value">{{ stats.total_users || 0 }}</span>
            <span class="stat-label">Users</span>
          </div>
        </div>
      </section>

      <!-- Status breakdown -->
      <section class="status-section" v-if="stats.by_status">
        <h3>Report Status Breakdown</h3>
        <div class="status-bar">
          <div v-for="(count, key) in stats.by_status" :key="key"
               class="status-seg" :class="statusClassName(key)"
               :style="{ flex: Math.max(count, 1) }"
               :title="`${statusLabels[key] || key}: ${count}`">
            <span v-if="count > 0" class="seg-label">{{ count }}</span>
          </div>
        </div>
        <div class="status-legend">
          <div v-for="(count, key) in stats.by_status" :key="key" class="legend-item" v-show="count > 0">
            <span class="legend-dot" :class="statusClassName(key)" /> {{ statusLabels[key] || key }} ({{ count }})
          </div>
        </div>
      </section>

      <!-- ── Main Two-Column Layout ─────────────────────── -->
      <div class="admin-main">
        <!-- ====== LEFT COLUMN: Policy Center ====== -->
        <div class="admin-left">
          <div class="left-section">
            <div class="left-section-header">
              <h2>Policy Center</h2>
              <button v-if="!showUpload" @click="startNew" class="btn-primary btn-upload">+ Upload PDF</button>
            </div>

            <!-- Policy list -->
            <div v-if="policies.length > 0 && !loading" class="policy-list">
              <div v-for="p in policies" :key="p.id"
                   :class="['policy-item', { active: p.id === selectedPolicyId }]"
                   @click="selectPolicy(p.id)">
                <span class="policy-name">{{ p.name || 'Unnamed Policy' }}</span>
                <span :class="['status-badge', p.status]">{{ p.status }}</span>
              </div>
            </div>
            <div v-if="loading" class="policy-loading">Loading policies...</div>
          </div>

          <!-- Error bar -->
          <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>

          <!-- ── Upload Zone ── -->
          <div v-if="showUpload" class="upload-zone">
            <h3>Upload Policy PDF</h3>
            <p class="upload-desc">Upload a company reimbursement policy document. The AI will parse it into structured expense rules and build a searchable knowledge base.</p>
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

          <!-- ── Editor Area (when policy selected) ── -->
          <div v-if="selectedPolicyId && !showUpload" class="version-area">
            <!-- Upload summary card -->
            <div v-if="uploadSummary" class="upload-summary">
              <div class="summary-row">
                <span class="summary-icon">✅</span>
                <span class="summary-label">KB Created</span>
                <span class="summary-detail" v-if="currentKbInfo">
                  "{{ currentKbInfo.name }}" · {{ currentKbInfo.document_count }} doc · <strong>{{ currentKbDocs.reduce((s, d) => s + d.chunk_count, 0) }}</strong> chunks indexed
                </span>
                <span class="summary-detail" v-else>KB ID: {{ uploadSummary.kb_id }}</span>
              </div>
              <div class="summary-row">
                <span class="summary-icon">🤖</span>
                <span class="summary-label">AI Parsed</span>
                <span class="summary-detail">
                  {{ draftExpenseTypes.length }} expense types
                  <template v-if="draftExpenseTypes.length">
                    · {{ draftExpenseTypes.filter(e => e.confidence >= 0.7).length }} high-confidence
                    <span v-if="draftExpenseTypes.filter(e => e.confidence < 0.7).length" class="warn-inline">
                      · {{ draftExpenseTypes.filter(e => e.confidence < 0.7).length }} need review
                    </span>
                  </template>
                </span>
              </div>
            </div>

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
                  <span :class="['confidence', confColor(et.confidence)]">{{ (et.confidence * 100).toFixed(0) }}%</span>
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

            <!-- No draft -->
            <div v-if="selectedVersionId && !versionDetail?.ai_draft && !errorMsg" class="panel-empty">
              Select a version to edit its draft.
            </div>

            <!-- Policy JSON preview -->
            <details v-if="versionDetail?.policy_json" class="json-preview">
              <summary>Policy JSON (published rules)</summary>
              <pre>{{ JSON.stringify(versionDetail.policy_json, null, 2) }}</pre>
            </details>

            <!-- Publish -->
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
        </div>

        <!-- ====== RIGHT COLUMN: Knowledge Base ====== -->
        <div class="admin-right">
          <!-- Current Policy KB -->
          <div v-if="currentKbInfo" class="panel">
            <h3>📚 {{ currentKbInfo.name }}</h3>
            <div class="kb-meta-row">
              <span class="kb-meta-tag">ID: {{ currentKbInfo.id }}</span>
              <span :class="['kb-meta-tag', currentKbInfo.is_active ? 'tag-active' : 'tag-inactive']">
                {{ currentKbInfo.is_active ? 'active' : 'inactive' }}
              </span>
            </div>
            <p v-if="currentKbInfo.description" class="kb-desc-text">{{ currentKbInfo.description }}</p>

            <!-- Documents -->
            <div v-if="currentKbDocs.length > 0" class="kb-docs-list">
              <div v-for="doc in currentKbDocs" :key="doc.id" class="kb-doc-item">
                <div :class="['kb-doc-hdr', { open: expandedDocs.has(doc.id) }]"
                     @click="toggleDocChunks(doc.id)">
                  <span class="kb-doc-name">📄 {{ doc.filename }}</span>
                  <span class="kb-doc-meta">{{ doc.chunk_count }} chunks</span>
                </div>
                <div v-if="expandedDocs.has(doc.id) && chunkDetails.has(doc.id)" class="kb-doc-chunks">
                  <div v-for="c in (chunkDetails.get(doc.id) || [])" :key="c.index" class="kb-chunk-item">
                    <span class="cidx">#{{ c.index }}</span>
                    <span class="ctext">{{ c.text }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- KB Search -->
            <div class="kb-search-box">
              <h4>🔍 Test Search</h4>
              <div class="kb-search-row">
                <input v-model="kbSearchQ" placeholder="Search policy content..." class="input-dark kb-search-input" @keyup.enter="doKbSearch" />
                <button @click="doKbSearch" :disabled="kbSearching" class="btn-sm">{{ kbSearching ? '...' : 'Go' }}</button>
              </div>
              <div v-if="kbSearchResults.length > 0" class="kb-results">
                <div v-for="(r, i) in kbSearchResults" :key="r.chunk_id" class="kb-result-item">
                  <div class="kb-result-hdr">
                    <span class="result-rank">#{{ i + 1 }}</span>
                    <span class="result-file">{{ r.filename }}</span>
                    <span class="result-score" :style="{ color: scoreColor(r.score) }">{{ (r.score * 100).toFixed(0) }}%</span>
                  </div>
                  <div class="result-snippet">{{ r.snippet }}</div>
                </div>
              </div>
              <div v-if="!kbSearching && kbSearchQ && kbSearchResults.length === 0" class="search-empty">No results.</div>
            </div>
          </div>

          <!-- All Knowledge Bases -->
          <div class="panel">
            <h3>📦 All Knowledge Bases</h3>

            <!-- Create KB -->
            <div class="kb-create">
              <input v-model="kbName" placeholder="Knowledge base name" class="input-dark" />
              <div class="kb-create-row">
                <input v-model="kbDesc" placeholder="Description (optional)" class="input-dark" />
                <button @click="createKB" class="btn-primary btn-sm">Create</button>
              </div>
            </div>

            <!-- KB List -->
            <div v-if="kbs.length === 0" class="panel-empty">No knowledge bases yet.</div>
            <div v-for="kb in kbs" :key="kb.id">
              <div class="kb-row" @click="toggleKb(kb.id)">
                <div class="kb-row-info">
                  <span class="kb-row-name">{{ kb.name }}</span>
                  <span class="kb-row-desc">{{ kb.description }}</span>
                </div>
                <div class="kb-row-meta">
                  <span class="kb-count">{{ kb.document_count }} docs</span>
                  <label class="btn-sm btn-upload-kb" @click.stop>
                    <input type="file" hidden @change="uploadDoc(kb.id, $event)" accept=".txt,.docx,.pdf" />
                    {{ uploadingDoc === kb.id ? '...' : '+' }}
                  </label>
                  <button class="btn-sm btn-danger" @click.stop="deleteKB(kb.id)">×</button>
                </div>
              </div>
              <!-- Expanded KB: documents + chunks -->
              <div v-if="expandedKb === kb.id" class="kb-expanded-docs">
                <div v-if="!kb._docs || kb._docs.length === 0" class="panel-empty">No documents yet.</div>
                <div v-for="doc in (kb._docs || [])" :key="doc.id" class="kb-exp-doc">
                  <div class="kb-exp-doc-hdr" @click="toggleDocChunks(doc.id)">
                    <span class="kb-doc-name">📄 {{ doc.filename }}</span>
                    <span class="kb-doc-meta">{{ doc.chunk_count }} chunks · {{ new Date(doc.created_at).toLocaleDateString() }}</span>
                    <span class="doc-expand-icon">{{ expandedDocs.has(doc.id) ? '▾' : '▸' }}</span>
                  </div>
                  <div v-if="expandedDocs.has(doc.id) && chunkDetails.has(doc.id)" class="kb-doc-chunks">
                    <div v-for="c in (chunkDetails.get(doc.id) || [])" :key="c.index" class="kb-chunk-item">
                      <span class="cidx">#{{ c.index }}</span>
                      <span class="ctext">{{ c.text }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- ChromaDB Stats -->
          <button @click="chromaStats" class="btn-sm btn-chroma">ChromaDB Stats</button>
        </div>
      </div>

      <!-- ── Search Debug (collapsible) ──────────────────── -->
      <details class="search-debug-panel">
        <summary>🔍 Search Debug <span class="debug-sub">Test retrieval quality &amp; tune parameters</span></summary>
        <div class="search-controls">
          <div class="search-row">
            <input v-model="searchQuery" placeholder="Enter search query..." class="input-dark" style="flex:1;" @keyup.enter="doSearch" />
            <button @click="doSearch" :disabled="searching" class="btn-primary">{{ searching ? 'Searching...' : 'Search' }}</button>
          </div>
          <div class="search-params">
            <label class="param-label">Top-K
              <select v-model.number="searchTopK" class="input-dark param-select">
                <option :value="1">1</option><option :value="3">3</option><option :value="5">5</option>
                <option :value="10">10</option><option :value="20">20</option><option :value="50">50</option>
              </select>
            </label>
            <label class="param-label">Threshold
              <select v-model.number="searchThreshold" class="input-dark param-select">
                <option :value="0">None</option><option :value="0.3">0.3</option><option :value="0.5">0.5</option>
                <option :value="0.7">0.7</option><option :value="0.8">0.8</option><option :value="0.9">0.9</option>
              </select>
            </label>
            <label class="param-label">KB Filter
              <select v-model.number="searchKbId" class="input-dark param-select">
                <option :value="null">All</option>
                <option v-for="kb in kbs" :key="kb.id" :value="kb.id">{{ kb.name }}</option>
              </select>
            </label>
            <label class="param-label">Mode
              <select v-model="searchMode" class="input-dark param-select">
                <option value="normal">Normal</option><option value="raw">Raw (ChromaDB)</option>
              </select>
            </label>
            <label class="param-label" v-if="searchResults.length > 0">Sort
              <select v-model="sortField" class="input-dark param-select">
                <option value="score">Score ↓</option><option value="distance">Distance ↑</option>
              </select>
            </label>
          </div>
        </div>

        <div v-if="!searching && searchResults.length === 0 && !searchMeta" class="panel-empty">Enter a query and click Search to test retrieval quality.</div>

        <div v-if="searchMeta" class="search-meta-bar">
          <span>{{ searchMeta.total_results }} results</span>
          <span>top_k={{ searchMeta.top_k }}</span>
          <span v-if="searchMeta.threshold">threshold={{ searchMeta.threshold }}</span>
          <span v-if="searchMeta.kb_id_filter">kb_id={{ searchMeta.kb_id_filter }}</span>
          <span class="meta-mode">{{ searchMode === 'raw' ? 'raw query' : 'normal' }}</span>
        </div>

        <div class="search-results" v-if="sortedResults.length > 0">
          <div v-for="(r, idx) in sortedResults" :key="idx" class="search-result-item">
            <div class="sr-header">
              <span class="sr-rank">#{{ idx + 1 }}</span>
              <span class="sr-file">{{ r.filename }}</span>
              <span v-if="r.kb_name" class="sr-kb">{{ r.kb_name }}</span>
              <span class="sr-score" :style="{ color: scoreColor(r.score ?? r.cosine_similarity ?? 0) }">
                {{ ((r.score ?? r.cosine_similarity ?? 0) * 100).toFixed(1) }}%
              </span>
              <span v-if="r.distance !== undefined" class="sr-distance">d={{ r.distance }}</span>
            </div>
            <div class="sr-snippet">{{ r.snippet || r.text }}</div>
          </div>
        </div>
        <div v-if="!searching && searchMeta && sortedResults.length === 0" class="panel-empty">No results found. Try lowering the threshold.</div>
      </details>
    </div>
  </div>
</template>

<style scoped>
* { box-sizing: border-box; margin: 0; padding: 0; }

.admin-shell {
  min-height: 100vh;
  background: #0a0a0e;
  color: #e4e4e7;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Top bar ───────────────────────────────────── */
.admin-top {
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
.top-right { display: flex; align-items: center; gap: 12px; }
.top-role {
  font-size: 11px; padding: 3px 10px; background: rgba(99,102,241,0.15); color: #a5b4fc;
  border-radius: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;
}
.btn-logout {
  background: none; border: none; color: rgba(255,255,255,0.3); cursor: pointer; padding: 4px;
}
.btn-logout svg { width: 18px; height: 18px; }
.btn-logout:hover { color: #f87171; }

/* ── Body ──────────────────────────────────────── */
.admin-body { max-width: 1440px; margin: 0 auto; padding: 24px 32px; }

/* ── Stats ─────────────────────────────────────── */
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
@media (max-width: 900px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } }
.stat-card {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 14px; padding: 20px; display: flex; align-items: center; gap: 16px;
}
.stat-icon {
  width: 48px; height: 48px; min-width: 48px;
  border-radius: 12px; display: flex; align-items: center; justify-content: center;
}
.stat-icon svg { width: 22px; height: 22px; }
.stat-icon.reports { background: rgba(99,102,241,0.12); color: #818cf8; }
.stat-icon.employees { background: rgba(52,211,153,0.12); color: #34d399; }
.stat-icon.amount { background: rgba(251,191,36,0.12); color: #fbbf24; }
.stat-icon.users { background: rgba(244,114,182,0.12); color: #f472b6; }
.stat-body { display: flex; flex-direction: column; }
.stat-value { font-size: 26px; font-weight: 700; color: #fff; letter-spacing: -0.5px; }
.stat-label { font-size: 12px; color: rgba(255,255,255,0.35); margin-top: 2px; }

/* ── Status breakdown ──────────────────────────── */
.status-section { margin-bottom: 24px; }
.status-section h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: rgba(255,255,255,0.6); }
.status-bar { display: flex; height: 32px; border-radius: 8px; overflow: hidden; gap: 2px; }
.status-seg { display: flex; align-items: center; justify-content: center; transition: filter 0.2s; min-width: 20px; }
.status-seg:hover { filter: brightness(1.3); }
.status-seg.submitted { background: #6366f1; }
.status-seg.manager_approval { background: #8b5cf6; }
.status-seg.finance_approval { background: #a78bfa; }
.status-seg.approved { background: #34d399; }
.status-seg.paid { background: #10b981; }
.status-seg.rejected { background: #f87171; }
.status-seg.draft { background: rgba(255,255,255,0.08); }
.seg-label { font-size: 11px; font-weight: 600; color: #fff; }
.status-legend { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; }
.legend-item { font-size: 12px; color: rgba(255,255,255,0.4); display: flex; align-items: center; gap: 6px; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; }
.legend-dot.submitted { background: #6366f1; }
.legend-dot.manager_approval { background: #8b5cf6; }
.legend-dot.finance_approval { background: #a78bfa; }
.legend-dot.approved { background: #34d399; }
.legend-dot.paid { background: #10b981; }
.legend-dot.rejected { background: #f87171; }
.legend-dot.draft { background: rgba(255,255,255,0.2); }

/* ── Main two-column layout ────────────────────── */
.admin-main {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}
.admin-left {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.admin-right {
  width: 370px;
  min-width: 370px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── Shared panel ──────────────────────────────── */
.panel {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 14px; padding: 20px;
  display: flex; flex-direction: column; gap: 12px;
}
.panel h3 { font-size: 14px; font-weight: 600; color: #fff; margin: 0; }
.panel h4 { font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.4); text-transform: uppercase; letter-spacing: 0.5px; }
.panel-empty {
  font-size: 12px; color: rgba(255,255,255,0.2); text-align: center; padding: 16px 0;
}

/* ── Left: Policy Center header ────────────────── */
.left-section-header {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;
}
.left-section-header h2 {
  font-size: 16px; font-weight: 600; color: #fff; margin: 0;
}

/* ── Policy List ───────────────────────────────── */
.policy-list { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.policy-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; border-radius: 10px; cursor: pointer;
  transition: background 0.15s;
}
.policy-item:hover { background: rgba(255,255,255,0.03); }
.policy-item.active { background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.2); }
.policy-name { font-size: 13px; font-weight: 500; color: #e4e4e7; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.policy-loading { font-size: 12px; color: rgba(255,255,255,0.2); padding: 12px 0; }

.status-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 6px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;
}
.status-badge.draft { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.35); }
.status-badge.published { background: rgba(52,211,153,0.12); color: #34d399; }
.status-badge.archived { background: rgba(248,113,113,0.1); color: #fca5a5; }
.status-badge.normalized { background: rgba(99,102,241,0.12); color: #a5b4fc; }
.status-badge.reviewing { background: rgba(251,191,36,0.12); color: #fbbf24; }
.status-badge.parsing { background: rgba(99,102,241,0.08); color: #a5b4fc; }

/* ── Error bar ─────────────────────────────────── */
.error-bar {
  background: rgba(248,113,113,0.1); border: 1px solid rgba(248,113,113,0.2);
  border-radius: 10px; padding: 10px 16px; font-size: 13px; color: #fca5a5;
}

/* ── Upload Zone ──────────────────────────────── */
.upload-zone { max-width: 480px; margin: 20px auto; text-align: center; }
.upload-zone h3 { font-size: 16px; font-weight: 600; color: #fff; margin-bottom: 8px; }
.upload-desc { font-size: 13px; color: rgba(255,255,255,0.3); margin-bottom: 20px; line-height: 1.6; }
.upload-drop {
  border: 2px dashed rgba(255,255,255,0.08); border-radius: 14px;
  padding: 40px 20px; margin-bottom: 16px; cursor: pointer; transition: border-color 0.2s;
}
.upload-drop:hover { border-color: rgba(99,102,241,0.3); }
.upload-drop p { font-size: 13px; color: rgba(255,255,255,0.2); margin-top: 8px; }
.upload-icon { width: 36px; height: 36px; color: rgba(255,255,255,0.15); }
.upload-row { display: flex; gap: 10px; align-items: center; justify-content: center; }
.file-label { cursor: pointer; display: inline-block; flex-shrink: 0; }
.upload-status { margin-top: 14px; font-size: 13px; color: rgba(99,102,241,0.6); }

/* ── Upload Summary ────────────────────────────── */
.upload-summary {
  background: linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04));
  border: 1px solid rgba(99,102,241,0.12); border-radius: 12px; padding: 14px 18px;
  display: flex; flex-direction: column; gap: 8px;
}
.summary-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.summary-icon { font-size: 14px; }
.summary-label { font-size: 13px; font-weight: 600; color: #c4b5fd; min-width: 80px; }
.summary-detail { font-size: 12px; color: rgba(255,255,255,0.4); }
.warn-inline { color: #fbbf24; }

/* ── Version tabs ──────────────────────────────── */
.version-area { display: flex; flex-direction: column; gap: 14px; }
.version-tabs { display: flex; gap: 6px; flex-wrap: wrap; }
.tab {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 12px; border-radius: 8px; font-size: 13px; cursor: pointer;
  border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.02);
  color: rgba(255,255,255,0.4); transition: all 0.15s;
}
.tab:hover { background: rgba(255,255,255,0.04); color: #e4e4e7; }
.tab.active { background: rgba(99,102,241,0.1); border-color: rgba(99,102,241,0.2); color: #a5b4fc; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.status-dot.draft { background: rgba(255,255,255,0.3); }
.status-dot.published { background: #34d399; }
.status-dot.archived { background: #f87171; }
.status-dot.normalized { background: #6366f1; }
.status-dot.reviewing { background: #fbbf24; }
.status-dot.parsing { background: rgba(255,255,255,0.2); }

/* ── Draft editor ──────────────────────────────── */
.draft-editor { display: flex; flex-direction: column; gap: 14px; }
.section-title { font-size: 15px; font-weight: 600; color: #fff; }
.warnings { display: flex; flex-direction: column; gap: 4px; }
.warn-item { font-size: 12px; color: #fbbf24; padding: 6px 10px; background: rgba(251,191,36,0.08); border-radius: 8px; }

.expense-card {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 12px; padding: 16px;
}
.card-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.card-name { font-size: 14px; font-weight: 600; color: #e4e4e7; }
.card-code { font-size: 12px; color: rgba(255,255,255,0.3); margin-left: 6px; }
.confidence { font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 6px; }
.confidence.high { background: rgba(52,211,153,0.12); color: #34d399; }
.confidence.medium { background: rgba(251,191,36,0.12); color: #fbbf24; }
.confidence.low { background: rgba(248,113,113,0.12); color: #fca5a5; }

.card-fields { display: flex; flex-wrap: wrap; gap: 10px; }
.field { font-size: 12px; color: rgba(255,255,255,0.4); display: flex; flex-direction: column; gap: 4px; }
.field-input { width: 130px; }
.checkbox-field { flex-direction: row; align-items: center; gap: 6px; cursor: pointer; color: rgba(255,255,255,0.5); }
.checkbox-field input[type="checkbox"] { accent-color: #6366f1; }
.card-source { margin-top: 8px; font-size: 11px; color: rgba(255,255,255,0.25); }
.source-label { color: rgba(255,255,255,0.15); }
.editor-actions { display: flex; gap: 10px; margin-top: 4px; }

/* ── Buttons & Inputs ──────────────────────────── */
.btn-primary {
  padding: 9px 16px; background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: box-shadow 0.2s;
}
.btn-primary:hover { box-shadow: 0 4px 16px rgba(99,102,241,0.3); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-upload { padding: 8px 14px; font-size: 12px; }

.btn-secondary {
  padding: 9px 16px; border-radius: 10px; font-size: 13px; font-weight: 500;
  cursor: pointer; border: 1px solid rgba(99,102,241,0.2);
  background: rgba(99,102,241,0.08); color: #a5b4fc; transition: all 0.15s;
}
.btn-secondary:hover { background: rgba(99,102,241,0.15); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-publish {
  padding: 9px 20px; background: linear-gradient(135deg, #34d399, #10b981);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: box-shadow 0.2s;
}
.btn-publish:hover { box-shadow: 0 4px 16px rgba(52,211,153,0.3); }
.btn-publish:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-sm {
  padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 500;
  cursor: pointer; border: none; transition: all 0.15s;
  background: rgba(99,102,241,0.1); color: #a5b4fc; display: inline-flex; align-items: center;
}
.btn-sm:hover { background: rgba(99,102,241,0.2); }

.btn-danger { background: rgba(248,113,113,0.1); color: #fca5a5; }
.btn-danger:hover { background: rgba(248,113,113,0.2); }
.btn-upload-kb { font-size: 14px; padding: 4px 10px; }
.btn-chroma { width: 100%; justify-content: center; }

.input-dark {
  padding: 9px 14px;
  background: #18181b; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; color: #fff; font-size: 13px; outline: none;
  transition: border-color 0.2s;
}
.input-dark:focus { border-color: rgba(99,102,241,0.4); }
.input-dark::placeholder { color: rgba(255,255,255,0.15); }

/* ── JSON preview ──────────────────────────────── */
.json-preview {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 12px; padding: 14px;
}
.json-preview summary {
  font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.5); cursor: pointer;
  margin-bottom: 10px;
}
.json-preview pre {
  font-size: 11px; color: rgba(255,255,255,0.4); max-height: 350px; overflow: auto;
  font-family: 'Consolas', 'Courier New', monospace; white-space: pre-wrap;
  background: #18181b; border-radius: 8px; padding: 12px;
}

/* ── Publish ───────────────────────────────────── */
.publish-bar {
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(52,211,153,0.06); border: 1px solid rgba(52,211,153,0.12);
  border-radius: 12px; padding: 14px 18px;
}
.publish-bar p { font-size: 13px; color: rgba(255,255,255,0.4); }
.published-badge {
  font-size: 13px; color: #34d399; padding: 10px 14px;
  background: rgba(52,211,153,0.06); border-radius: 10px;
}

/* ── Right: KB current ─────────────────────────── */
.kb-meta-row { display: flex; gap: 6px; }
.kb-meta-tag {
  font-size: 10px; padding: 2px 8px; border-radius: 5px; font-weight: 500;
  background: rgba(255,255,255,0.03); color: rgba(255,255,255,0.3);
}
.tag-active { background: rgba(52,211,153,0.1); color: #34d399; }
.tag-inactive { background: rgba(248,113,113,0.08); color: #fca5a5; }
.kb-desc-text { font-size: 12px; color: rgba(255,255,255,0.3); line-height: 1.5; }

.kb-docs-list { display: flex; flex-direction: column; gap: 4px; }
.kb-doc-item { }
.kb-doc-hdr {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; border-radius: 8px; cursor: pointer; transition: background 0.15s;
}
.kb-doc-hdr:hover { background: rgba(255,255,255,0.03); }
.kb-doc-hdr.open { background: rgba(99,102,241,0.06); }
.kb-doc-name { font-size: 12px; color: rgba(255,255,255,0.55); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb-doc-meta { font-size: 10px; color: rgba(255,255,255,0.2); white-space: nowrap; }

.kb-doc-chunks {
  margin-left: 10px; padding-left: 10px;
  border-left: 1px solid rgba(99,102,241,0.1);
  display: flex; flex-direction: column; gap: 2px;
}
.kb-chunk-item { display: flex; gap: 6px; font-size: 11px; padding: 3px 0; }
.cidx { color: rgba(99,102,241,0.4); font-weight: 600; min-width: 22px; flex-shrink: 0; }
.ctext { color: rgba(255,255,255,0.35); line-height: 1.4; word-break: break-all; }

/* KB Search */
.kb-search-box { display: flex; flex-direction: column; gap: 8px; }
.kb-search-row { display: flex; gap: 6px; }
.kb-search-input { flex: 1; padding: 8px 12px; font-size: 12px; }

.kb-results { display: flex; flex-direction: column; gap: 6px; }
.kb-result-item {
  padding: 9px 12px; background: rgba(255,255,255,0.015);
  border: 1px solid rgba(255,255,255,0.04); border-radius: 8px;
}
.kb-result-hdr { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
.result-rank { font-size: 10px; color: rgba(99,102,241,0.4); font-weight: 600; }
.result-file { font-size: 11px; color: rgba(255,255,255,0.3); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-score { font-size: 12px; font-weight: 700; font-variant-numeric: tabular-nums; }
.result-snippet { font-size: 11px; color: rgba(255,255,255,0.45); line-height: 1.5; }
.search-empty { font-size: 11px; color: rgba(255,255,255,0.15); text-align: center; padding: 8px 0; }

/* ── Right: All KBs ────────────────────────────── */
.kb-create { display: flex; flex-direction: column; gap: 8px; }
.kb-create-row { display: flex; gap: 8px; }
.kb-create-row .input-dark { flex: 1; }

.kb-row {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 0; border-bottom: 1px solid rgba(255,255,255,0.03); cursor: pointer;
}
.kb-row:last-child { border-bottom: none; }
.kb-row-info { flex: 1; min-width: 0; }
.kb-row-name { font-size: 13px; font-weight: 500; color: #e4e4e7; display: block; }
.kb-row-desc { font-size: 11px; color: rgba(255,255,255,0.25); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; }
.kb-row-meta { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.kb-count {
  font-size: 10px; padding: 2px 8px; background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; color: rgba(255,255,255,0.3);
}

/* Expanded KB docs */
.kb-expanded-docs {
  margin-left: 10px; border-left: 1px solid rgba(255,255,255,0.05); padding-left: 14px;
  margin-bottom: 8px;
}
.kb-exp-doc { margin-bottom: 4px; }
.kb-exp-doc-hdr {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px; border-radius: 8px; cursor: pointer; transition: background 0.15s;
}
.kb-exp-doc-hdr:hover { background: rgba(255,255,255,0.03); }
.doc-expand-icon { font-size: 10px; color: rgba(255,255,255,0.25); width: 14px; text-align: center; }

/* ── Search Debug (collapsible) ─────────────────── */
.search-debug-panel {
  margin-top: 24px;
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 14px; padding: 16px 20px;
}
.search-debug-panel summary {
  font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.4); cursor: pointer;
  outline: none;
}
.debug-sub { font-size: 11px; font-weight: 400; color: rgba(255,255,255,0.2); margin-left: 8px; }

.search-controls { display: flex; flex-direction: column; gap: 10px; margin-top: 12px; }
.search-row { display: flex; gap: 10px; }
.search-params { display: flex; gap: 12px; flex-wrap: wrap; }
.param-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: rgba(255,255,255,0.4);
}
.param-select { width: auto; padding: 6px 10px; font-size: 12px; }
.search-meta-bar {
  display: flex; gap: 16px; flex-wrap: wrap;
  padding: 8px 12px; margin-top: 8px;
  background: rgba(255,255,255,0.02); border-radius: 8px;
  font-size: 12px; color: rgba(255,255,255,0.3);
}
.meta-mode { margin-left: auto; color: rgba(99,102,241,0.6); font-weight: 500; }
.search-results { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
.search-result-item {
  padding: 12px 14px;
  background: rgba(255,255,255,0.015); border: 1px solid rgba(255,255,255,0.04);
  border-radius: 10px;
}
.sr-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.sr-rank { font-size: 11px; color: rgba(99,102,241,0.5); font-weight: 600; min-width: 24px; }
.sr-file { font-size: 13px; color: #e4e4e7; font-weight: 500; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sr-kb { font-size: 11px; color: rgba(255,255,255,0.25); padding: 2px 8px; background: rgba(255,255,255,0.03); border-radius: 6px; }
.sr-score { font-size: 14px; font-weight: 700; min-width: 52px; text-align: right; font-variant-numeric: tabular-nums; }
.sr-distance { font-size: 11px; color: rgba(255,255,255,0.2); min-width: 64px; text-align: right; font-variant-numeric: tabular-nums; }
.sr-snippet { font-size: 12px; color: rgba(255,255,255,0.5); line-height: 1.5; padding-left: 24px; word-break: break-word; }
</style>
