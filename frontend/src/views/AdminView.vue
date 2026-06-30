<script setup lang="ts">
import { ref, onMounted } from 'vue'
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
  await api.post(`/knowledge/bases/${kbId}/documents`, form, { headers: { 'Content-Type': 'multipart/form-data' } })
  uploadingDoc.value = null; input.value = ''
  await loadKBs()
}

function logout() { auth.logout(); router.push('/login') }

const statusLabels: Record<string, string> = {
  draft: 'Draft', submitted: 'Submitted', manager_approval: 'Manager Review',
  finance_approval: 'Finance Review', approved: 'Approved', paid: 'Paid', rejected: 'Rejected',
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
            :class="key"
            :style="{ flex: Math.max(count, 1) }"
            :title="`${statusLabels[key] || key}: ${count}`"
          >
            <span v-if="count > 0" class="seg-label">{{ count }}</span>
          </div>
        </div>
        <div class="status-legend">
          <div v-for="(count, key) in stats.by_status" :key="key" class="legend-item" v-show="count > 0">
            <span class="legend-dot" :class="key" /> {{ statusLabels[key] || key }} ({{ count }})
          </div>
        </div>
      </section>

      <div class="content-grid">
        <!-- Create KB -->
        <section class="panel">
          <h3>New Knowledge Base</h3>
          <p class="panel-desc">Upload company reimbursement policy documents</p>
          <div class="kb-create">
            <input v-model="kbName" placeholder="Knowledge base name" class="input-dark" />
            <input v-model="kbDesc" placeholder="Description (optional)" class="input-dark" />
            <button @click="createKB" class="btn-primary">Create</button>
          </div>
        </section>

        <!-- KB List -->
        <section class="panel" style="grid-column: span 2;">
          <h3>Knowledge Bases</h3>
          <div v-if="kbs.length === 0" class="panel-empty">No knowledge bases yet. Create one above.</div>
          <div v-for="kb in kbs" :key="kb.id" class="kb-row">
            <div class="kb-info">
              <span class="kb-name">{{ kb.name }}</span>
              <span class="kb-desc">{{ kb.description }}</span>
            </div>
            <div class="kb-meta">
              <span class="kb-count">{{ kb.document_count }} docs</span>
            </div>
            <div class="kb-actions">
              <label :class="['btn-sm', { loading: uploadingDoc === kb.id }]">
                <input type="file" hidden @change="uploadDoc(kb.id, $event)" />
                {{ uploadingDoc === kb.id ? 'Uploading...' : 'Upload Doc' }}
              </label>
              <button class="btn-sm btn-danger" @click="deleteKB(kb.id)">Delete</button>
            </div>
          </div>
        </section>
      </div>
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
</style>
