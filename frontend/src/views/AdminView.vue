<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import api from '../api'

const router = useRouter()
const auth = useAuthStore()

const kbName = ref('')
const kbDesc = ref('')
const kbs = ref<any[]>([])
const stats = ref<any>({})
const uploadingDoc = ref<number | null>(null)
const expandedKb = ref<number | null>(null)
const expandedDocs = ref<Set<number>>(new Set())
const chunkDetails = ref<Map<number, any[]>>(new Map())

const searchQuery = ref('')
const searchTopK = ref(5)
const searchThreshold = ref(0)
const searchKbId = ref<number | null>(null)
const searchMode = ref<'normal' | 'raw'>('normal')
const searching = ref(false)
const searchResults = ref<any[]>([])
const searchMeta = ref<any>(null)

onMounted(async () => { await loadKBs(); await loadStats() })

async function loadKBs() { const res = await api.get('/knowledge/bases'); kbs.value = res.data }
async function loadStats() { const res = await api.get('/admin/stats'); stats.value = res.data }

async function createKB() {
  if (!kbName.value.trim()) return
  await api.post('/knowledge/bases', { name: kbName.value, description: kbDesc.value })
  kbName.value = ''; kbDesc.value = ''
  await loadKBs()
}

async function deleteKB(id: number) { await api.delete(`/knowledge/bases/${id}`); await loadKBs() }

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

async function toggleKb(kbId: number) {
  if (expandedKb.value === kbId) { expandedKb.value = null; return }
  expandedKb.value = kbId
  await loadDocs(kbId)
}

async function toggleDocChunks(docId: number) {
  if (expandedDocs.value.has(docId)) {
    expandedDocs.value.delete(docId)
    return
  }
  expandedDocs.value.add(docId)
  const res = await api.get(`/knowledge/documents/${docId}/chunks`)
  chunkDetails.value.set(docId, res.data.chunks || [])
}

async function chromaStats() {
  const res = await api.get('/knowledge/chroma-stats')
  alert(JSON.stringify(res.data, null, 2))
}

// ---- Policy Center ----
const policyText = ref('')
const parsedPolicy = ref<any>(null)
const parseWarnings = ref<string[]>([])
const parsing = ref(false)
const saving = ref(false)
const currentPolicy = ref<any>(null)
const policyLoading = ref(false)

async function parsePolicy() {
  if (!policyText.value.trim()) return
  parsing.value = true
  parseWarnings.value = []
  try {
    const res = await api.post('/policy/parse', { text: policyText.value.trim() })
    parsedPolicy.value = res.data.policy
    parseWarnings.value = res.data.warnings || []
  } catch (e: any) {
    alert('Parse failed: ' + (e.response?.data?.detail || e.message))
  } finally {
    parsing.value = false
  }
}

async function loadCurrentPolicy() {
  policyLoading.value = true
  try {
    const res = await api.get('/policy/current')
    currentPolicy.value = res.data
  } catch {
    currentPolicy.value = null
  } finally {
    policyLoading.value = false
  }
}

async function savePolicy() {
  if (!parsedPolicy.value) return
  saving.value = true
  try {
    const res = await api.put('/policy/current', { enterprise: 'default', policy: parsedPolicy.value })
    currentPolicy.value = res.data
    alert('政策保存成功！')
  } catch (e: any) {
    alert('Save failed: ' + (e.response?.data?.detail || e.message))
  } finally {
    saving.value = false
  }
}

function policyJson(v: any) { return JSON.stringify(v, null, 2) }

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
      searchMeta.value = {
        total_results: res.data.total_results,
        top_k: res.data.top_k,
        threshold: res.data.threshold,
        kb_id_filter: res.data.kb_id_filter,
      }
    } else {
      params.top_k = searchTopK.value
      if (searchThreshold.value > 0) params.threshold = searchThreshold.value
      const res = await api.get('/knowledge/search', { params })
      searchResults.value = res.data
      searchMeta.value = {
        total_results: res.data.length,
        top_k: searchTopK.value,
        threshold: searchThreshold.value,
        kb_id_filter: searchKbId.value,
      }
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
  if (score >= 0.4) return '#f97316'
  return '#f87171'
}

type SortField = 'score' | 'distance'
const sortField = ref<SortField>('score')
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

function logout() { auth.logout(); router.push('/login') }

const statusLabels: Record<string, string> = {
  draft: 'Draft', submitted: 'Submitted', manager_approval: 'Manager Review',
  finance_approval: 'Finance Review', approved: 'Approved', paid: 'Paid', rejected: 'Rejected',
}

function statusClassName(key: string | number): string {
  return String(key)
}
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
      <!-- Stats grid -->
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
          <div
            v-for="(count, key) in stats.by_status"
            :key="key"
            class="status-seg"
            :class="statusClassName(key)"
            :style="{ flex: Math.max(count, 1) }"
            :title="`${statusLabels[key] || key}: ${count}`"
          >
            <span v-if="count > 0" class="seg-label">{{ count }}</span>
          </div>
        </div>
        <div class="status-legend">
          <div v-for="(count, key) in stats.by_status" :key="key" class="legend-item" v-show="count > 0">
            <span class="legend-dot" :class="statusClassName(key)" /> {{ statusLabels[key] || key }} ({{ count }})
          </div>
        </div>
      </section>

      <div class="content-grid">
        <!-- Create KB -->
        <section class="panel">
          <h3>New Knowledge Base</h3>
          <p class="panel-desc">Upload company reimbursement policy documents — supported formats: <strong>.txt</strong>, <strong>.docx</strong>, <strong>.pdf</strong></p>
          <div class="kb-create">
            <input v-model="kbName" placeholder="Knowledge base name" class="input-dark" />
            <input v-model="kbDesc" placeholder="Description (optional)" class="input-dark" />
            <button @click="createKB" class="btn-primary">Create</button>
          </div>
        </section>

        <!-- KB List -->
        <section class="panel" style="grid-column: span 2;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="margin:0;">Knowledge Bases</h3>
            <button class="btn-sm" @click="chromaStats">ChromaDB Stats</button>
          </div>
          <div v-if="kbs.length === 0" class="panel-empty">No knowledge bases yet. Create one above.</div>
          <div v-for="kb in kbs" :key="kb.id">
            <div class="kb-row" @click="toggleKb(kb.id)" style="cursor:pointer;">
              <div class="kb-info">
                <span class="kb-name">{{ kb.name }}</span>
                <span class="kb-desc">{{ kb.description }}</span>
              </div>
              <div class="kb-meta">
                <span class="kb-count">{{ kb.document_count }} docs</span>
              </div>
              <div class="kb-actions">
                <label :class="['btn-sm', { loading: uploadingDoc === kb.id }]">
                  <input type="file" hidden @change="uploadDoc(kb.id, $event)" @click.stop accept=".txt,.docx,.pdf" />
                  {{ uploadingDoc === kb.id ? 'Uploading...' : 'Upload Doc' }}
                </label>
                <button class="btn-sm btn-danger" @click.stop="deleteKB(kb.id)">Delete</button>
              </div>
            </div>
            <!-- Expanded: document list with chunks -->
            <div v-if="expandedKb === kb.id" class="kb-docs">
              <div v-if="!kb._docs || kb._docs.length === 0" class="panel-empty" style="padding:10px;">No documents yet.</div>
              <div v-for="doc in (kb._docs || [])" :key="doc.id" class="doc-item">
                <div class="doc-header" @click="toggleDocChunks(doc.id)">
                  <span class="doc-name">📄 {{ doc.filename }}</span>
                  <span class="doc-meta">{{ doc.chunk_count }} chunks · {{ new Date(doc.created_at).toLocaleDateString() }}</span>
                  <span class="doc-expand">{{ expandedDocs.has(doc.id) ? '▾' : '▸' }}</span>
                </div>
                <div v-if="expandedDocs.has(doc.id) && chunkDetails.has(doc.id)" class="doc-chunks">
                  <div v-for="c in (chunkDetails.get(doc.id) || [])" :key="c.index" class="chunk-item">
                    <span class="chunk-idx">#{{ c.index }}</span>
                    <span class="chunk-text">{{ c.text }}</span>
                    <span class="chunk-len">{{ c.char_count }}c</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Policy Center -->
        <section class="panel" style="margin-top: 24px;">
          <h3>⚙️ Policy Center</h3>
          <p class="panel-desc">Upload policy text → AI parses it into structured rules → review & save to repository.</p>

          <div style="margin-bottom:16px;">
            <textarea
              v-model="policyText"
              placeholder="Paste company reimbursement policy text here (Chinese)... e.g. &#10;餐饮费报销标准：按实际消费金额的60%报销，单次上限500元。&#10;差旅费报销标准：按实际消费金额的80%报销，单次上限500元。&#10;商务招待费报销标准：按实际消费金额的80%报销，单次上限1000元，超过1000元需审批，需提供宾客名单。"
              class="input-dark"
              style="height:120px; font-family:inherit; resize:vertical;"
            />
          </div>

          <div style="display:flex; gap:10px; margin-bottom:16px;">
            <button @click="parsePolicy" :disabled="parsing" class="btn-primary">
              {{ parsing ? 'Parsing...' : '🤖 AI Parse' }}
            </button>
            <button @click="loadCurrentPolicy" :disabled="policyLoading" class="btn-sm">
              {{ policyLoading ? 'Loading...' : '📋 Load Current' }}
            </button>
            <button
              v-if="parsedPolicy"
              @click="savePolicy"
              :disabled="saving"
              class="btn-sm"
              style="background: rgba(52,211,153,0.15); color: #34d399;"
            >
              {{ saving ? 'Saving...' : '💾 Save to Repository' }}
            </button>
          </div>

          <!-- Warnings -->
          <div v-if="parseWarnings.length > 0" style="margin-bottom:12px;">
            <div v-for="(w, i) in parseWarnings" :key="i" style="color:#fbbf24; font-size:12px; padding:4px 0;">⚠️ {{ w }}</div>
          </div>

          <!-- Parsed JSON editor -->
          <div v-if="parsedPolicy" style="margin-bottom:16px;">
            <label style="font-size:12px; color:rgba(255,255,255,0.4); margin-bottom:4px; display:block;">Parsed Policy (editable JSON)</label>
            <textarea
              :value="policyJson(parsedPolicy)"
              @input="(e: any) => { try { parsedPolicy = JSON.parse((e.target as HTMLTextAreaElement).value) } catch {} }"
              class="input-dark"
              style="height:300px; font-family:'Consolas','Courier New',monospace; font-size:12px; resize:vertical;"
            />
          </div>

          <!-- Current active policy (read-only) -->
          <div v-if="currentPolicy" style="margin-top:12px;">
            <label style="font-size:12px; color:rgba(255,255,255,0.4); margin-bottom:4px; display:block;">📦 Active Policy (read-only)</label>
            <pre style="
              background:#18181b; border:1px solid rgba(255,255,255,0.06); border-radius:10px;
              padding:14px; font-size:12px; color: rgba(255,255,255,0.5);
              max-height:200px; overflow:auto; white-space:pre-wrap;
            ">{{ policyJson(currentPolicy) }}</pre>
          </div>
        </section>
      </div>

      <!-- Search Debug Panel -->
      <section class="panel" style="margin-top: 24px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 16px;">
          <h3 style="margin:0;">🔍 Search Debug</h3>
          <span style="font-size:11px; color: rgba(255,255,255,0.3);">Test retrieval quality & tune parameters</span>
        </div>

        <!-- Controls -->
        <div class="search-controls">
          <div class="search-row">
            <input
              v-model="searchQuery"
              placeholder="Enter search query..."
              class="input-dark"
              style="flex:1;"
              @keyup.enter="doSearch"
            />
            <button @click="doSearch" :disabled="searching" class="btn-primary">
              {{ searching ? 'Searching...' : 'Search' }}
            </button>
          </div>
          <div class="search-params">
            <label class="param-label">
              Top-K
              <select v-model.number="searchTopK" class="input-dark param-select">
                <option :value="1">1</option>
                <option :value="3">3</option>
                <option :value="5">5</option>
                <option :value="10">10</option>
                <option :value="20">20</option>
                <option :value="50">50</option>
              </select>
            </label>
            <label class="param-label">
              Threshold
              <select v-model.number="searchThreshold" class="input-dark param-select">
                <option :value="0">None</option>
                <option :value="0.3">0.3</option>
                <option :value="0.5">0.5</option>
                <option :value="0.7">0.7</option>
                <option :value="0.8">0.8</option>
                <option :value="0.9">0.9</option>
              </select>
            </label>
            <label class="param-label">
              KB Filter
              <select v-model.number="searchKbId" class="input-dark param-select">
                <option :value="null">All</option>
                <option v-for="kb in kbs" :key="kb.id" :value="kb.id">{{ kb.name }}</option>
              </select>
            </label>
            <label class="param-label">
              Mode
              <select v-model="searchMode" class="input-dark param-select">
                <option value="normal">Normal (SearchResult)</option>
                <option value="raw">Raw (ChromaDB)</option>
              </select>
            </label>
            <label class="param-label" v-if="searchResults.length > 0">
              Sort
              <select v-model="sortField" class="input-dark param-select">
                <option value="score">Score ↓</option>
                <option value="distance">Distance ↑</option>
              </select>
            </label>
          </div>
        </div>

        <!-- Empty -->
        <div v-if="!searching && searchResults.length === 0 && !searchMeta" class="panel-empty" style="padding: 40px 0;">
          Enter a query and click Search to test retrieval quality.
        </div>

        <!-- Meta bar -->
        <div v-if="searchMeta" class="search-meta-bar">
          <span>{{ searchMeta.total_results }} results</span>
          <span>top_k={{ searchMeta.top_k }}</span>
          <span v-if="searchMeta.threshold">threshold={{ searchMeta.threshold }}</span>
          <span v-if="searchMeta.kb_id_filter">kb_id={{ searchMeta.kb_id_filter }}</span>
          <span class="meta-mode">{{ searchMode === 'raw' ? 'raw query' : 'normal' }}</span>
        </div>

        <!-- Results -->
        <div class="search-results" v-if="sortedResults.length > 0">
          <div v-for="(r, idx) in sortedResults" :key="idx" class="search-result-item">
            <div class="sr-header">
              <span class="sr-rank">#{{ idx + 1 }}</span>
              <span class="sr-file">{{ r.filename }}</span>
              <span v-if="r.kb_name" class="sr-kb">{{ r.kb_name }}</span>
              <span class="sr-score" :style="{color: scoreColor(r.score ?? r.cosine_similarity ?? 0)}">
                {{ ((r.score ?? r.cosine_similarity ?? 0) * 100).toFixed(1) }}%
              </span>
              <span v-if="r.distance !== undefined" class="sr-distance">d={{ r.distance }}</span>
            </div>
            <div class="sr-snippet">{{ r.snippet || r.text }}</div>
          </div>
        </div>

        <!-- No results -->
        <div v-if="!searching && searchMeta && sortedResults.length === 0" class="panel-empty" style="padding: 20px 0;">
          No results found. Try lowering the threshold or changing the query.
        </div>
      </section>
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

/* Top bar */
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

.admin-body { max-width: 1200px; margin: 0 auto; padding: 32px; }

/* Stats */
.stat-grid {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 32px;
}
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

/* Status bar */
.status-section { margin-bottom: 32px; }
.status-section h3 { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: rgba(255,255,255,0.6); }
.status-bar { display: flex; height: 32px; border-radius: 8px; overflow: hidden; gap: 2px; }
.status-seg {
  position: relative; display: flex; align-items: center; justify-content: center;
  transition: filter 0.2s; min-width: 20px;
}
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
.legend-dot {
  width: 8px; height: 8px; border-radius: 50%;
}
.legend-dot.submitted { background: #6366f1; }
.legend-dot.manager_approval { background: #8b5cf6; }
.legend-dot.finance_approval { background: #a78bfa; }
.legend-dot.approved { background: #34d399; }
.legend-dot.paid { background: #10b981; }
.legend-dot.rejected { background: #f87171; }
.legend-dot.draft { background: rgba(255,255,255,0.2); }

/* Content grid */
.content-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 24px; }
@media (max-width: 900px) { .content-grid { grid-template-columns: 1fr; } }

.panel {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 14px; padding: 24px;
}
.panel h3 { font-size: 15px; font-weight: 600; margin-bottom: 6px; color: #fff; }
.panel-desc { font-size: 12px; color: rgba(255,255,255,0.3); margin-bottom: 16px; }
.panel-empty { font-size: 13px; color: rgba(255,255,255,0.2); padding: 20px 0; text-align: center; }

.kb-create { display: flex; flex-direction: column; gap: 10px; }
.input-dark {
  width: 100%; padding: 10px 14px;
  background: #18181b; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; color: #fff; font-size: 13px; outline: none;
  transition: border-color 0.2s;
}
.input-dark:focus { border-color: rgba(99,102,241,0.4); }
.input-dark::placeholder { color: rgba(255,255,255,0.15); }
.btn-primary {
  padding: 10px 16px; background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: box-shadow 0.2s;
}
.btn-primary:hover { box-shadow: 0 4px 16px rgba(99,102,241,0.3); }

.kb-row {
  display: flex; align-items: center; gap: 16px;
  padding: 14px 0; border-bottom: 1px solid rgba(255,255,255,0.03);
}
.kb-row:last-child { border-bottom: none; }
.kb-info { flex: 1; display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.kb-name { font-size: 14px; font-weight: 500; color: #e4e4e7; }
.kb-desc { font-size: 12px; color: rgba(255,255,255,0.3); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.kb-meta { flex-shrink: 0; }
.kb-count {
  font-size: 11px; padding: 3px 10px; background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; color: rgba(255,255,255,0.3);
}
.kb-actions { display: flex; gap: 6px; flex-shrink: 0; }
.btn-sm {
  padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 500;
  cursor: pointer; border: none; transition: all 0.15s;
  background: rgba(99,102,241,0.1); color: #a5b4fc;
  display: inline-flex; align-items: center;
}
.btn-sm:hover { background: rgba(99,102,241,0.2); }
.btn-sm.loading { opacity: 0.5; }
.btn-danger { background: rgba(248,113,113,0.1); color: #fca5a5; }
.btn-danger:hover { background: rgba(248,113,113,0.2); }

/* Document list inside expanded KB */
.kb-docs {
  margin-left: 12px; border-left: 1px solid rgba(255,255,255,0.05); padding-left: 16px;
  margin-bottom: 12px;
}
.doc-item { margin-bottom: 6px; }
.doc-header {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 10px; border-radius: 8px; cursor: pointer; transition: background 0.15s;
}
.doc-header:hover { background: rgba(255,255,255,0.03); }
.doc-name { font-size: 13px; color: rgba(255,255,255,0.7); flex: 1; }
.doc-meta { font-size: 11px; color: rgba(255,255,255,0.25); }
.doc-expand { font-size: 11px; color: rgba(255,255,255,0.3); width: 16px; text-align: center; }

/* Chunk display */
.doc-chunks {
  margin-left: 20px; margin-top: 4px;
  border-left: 1px solid rgba(99,102,241,0.15); padding-left: 12px;
}
.chunk-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 6px 0; font-size: 12px;
}
.chunk-idx {
  color: rgba(99,102,241,0.6); font-weight: 600; min-width: 28px; flex-shrink: 0;
}
.chunk-text {
  color: rgba(255,255,255,0.5); flex: 1; word-break: break-all; line-height: 1.4;
}
.chunk-len {
  color: rgba(255,255,255,0.2); font-size: 10px; flex-shrink: 0; min-width: 30px; text-align: right;
}

/* Search Debug Panel */
.search-controls {
  display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px;
}
.search-row {
  display: flex; gap: 10px;
}
.search-params {
  display: flex; gap: 12px; flex-wrap: wrap;
}
.param-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: rgba(255,255,255,0.4);
}
.param-select {
  width: auto; padding: 6px 10px; font-size: 12px;
}
.search-meta-bar {
  display: flex; gap: 16px; flex-wrap: wrap;
  padding: 8px 12px; margin-bottom: 12px;
  background: rgba(255,255,255,0.02); border-radius: 8px;
  font-size: 12px; color: rgba(255,255,255,0.3);
}
.meta-mode {
  margin-left: auto; color: rgba(99,102,241,0.6); font-weight: 500;
}
.search-results {
  display: flex; flex-direction: column; gap: 8px;
}
.search-result-item {
  padding: 12px 14px;
  background: rgba(255,255,255,0.015); border: 1px solid rgba(255,255,255,0.04);
  border-radius: 10px; transition: background 0.15s;
}
.search-result-item:hover { background: rgba(255,255,255,0.03); }
.sr-header {
  display: flex; align-items: center; gap: 10px; margin-bottom: 6px;
}
.sr-rank {
  font-size: 11px; color: rgba(99,102,241,0.5); font-weight: 600; min-width: 24px;
}
.sr-file {
  font-size: 13px; color: #e4e4e7; font-weight: 500; flex: 1;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.sr-kb {
  font-size: 11px; color: rgba(255,255,255,0.25);
  padding: 2px 8px; background: rgba(255,255,255,0.03); border-radius: 6px;
}
.sr-score {
  font-size: 14px; font-weight: 700; min-width: 52px; text-align: right; font-variant-numeric: tabular-nums;
}
.sr-distance {
  font-size: 11px; color: rgba(255,255,255,0.2); min-width: 64px; text-align: right; font-variant-numeric: tabular-nums;
}
.sr-snippet {
  font-size: 12px; color: rgba(255,255,255,0.5); line-height: 1.5;
  padding-left: 24px; word-break: break-word;
}
</style>
