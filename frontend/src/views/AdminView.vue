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
const uploadFileInput = ref<HTMLInputElement | null>(null)
const stats = ref<any>({})

onMounted(async () => {
  await loadKBs()
  await loadStats()
})

async function loadKBs() {
  const res = await api.get('/knowledge/bases')
  kbs.value = res.data
}
async function loadStats() {
  const res = await api.get('/admin/stats')
  stats.value = res.data
}

async function createKB() {
  await api.post('/knowledge/bases', { name: kbName.value, description: kbDesc.value })
  kbName.value = ''
  kbDesc.value = ''
  await loadKBs()
}

async function deleteKB(id: number) {
  await api.delete(`/knowledge/bases/${id}`)
  await loadKBs()
}

async function uploadDoc(kbId: number, e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files?.length) return
  const form = new FormData()
  form.append('file', input.files[0])
  await api.post(`/knowledge/bases/${kbId}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  input.value = ''
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="admin-layout">
    <header>
      <h2>Admin Panel</h2>
      <div>
        <span>{{ auth.role }}</span>
        <button @click="logout" class="btn-logout">Logout</button>
      </div>
    </header>

    <div class="admin-content">
      <!-- Stats -->
      <section class="card">
        <h3>Dashboard</h3>
        <div class="stats-grid">
          <div class="stat"><span>{{ stats.total_reports || 0 }}</span> Reports</div>
          <div class="stat"><span>{{ stats.total_employees || 0 }}</span> Employees</div>
          <div class="stat"><span>{{ stats.total_users || 0 }}</span> Users</div>
          <div class="stat"><span>{{ stats.total_reimbursed || 0 }}</span> Total CNY</div>
        </div>
      </section>

      <!-- KB Create -->
      <section class="card">
        <h3>New Knowledge Base</h3>
        <div class="kb-form">
          <input v-model="kbName" placeholder="Name" />
          <input v-model="kbDesc" placeholder="Description" />
          <button @click="createKB">Create</button>
        </div>
      </section>

      <!-- KB List -->
      <section class="card">
        <h3>Knowledge Bases</h3>
        <div v-for="kb in kbs" :key="kb.id" class="kb-item">
          <div>
            <strong>{{ kb.name }}</strong>
            <p>{{ kb.description }}</p>
            <small>{{ kb.document_count }} documents</small>
          </div>
          <div class="kb-actions">
            <button @click="uploadFileInput = $refs['upload-' + kb.id] as any">Upload Doc</button>
            <input
              :ref="(el) => { uploadFileInput = el as any }"
              type="file" hidden
              @change="uploadDoc(kb.id, $event)"
            />
            <button class="btn-danger" @click="deleteKB(kb.id)">Delete</button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.admin-layout { min-height: 100vh; background: #f5f7fa; }
header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 32px; background: #1a1a2e; color: #fff;
}
header h2 { font-size: 18px; }
.btn-logout { padding: 6px 14px; background: #e74c3c; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
.admin-content { max-width: 900px; margin: 0 auto; padding: 24px; }
.card { background: #fff; border-radius: 12px; padding: 24px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
.card h3 { margin-bottom: 16px; font-size: 16px; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat { text-align: center; padding: 16px; background: #f5f7fa; border-radius: 8px; font-size: 14px; }
.stat span { display: block; font-size: 28px; font-weight: 700; color: #667eea; }

.kb-form { display: flex; gap: 10px; }
.kb-form input { flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; }
.kb-form button { padding: 8px 16px; background: #667eea; color: #fff; border: none; border-radius: 6px; cursor: pointer; }

.kb-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 0; border-bottom: 1px solid #eee;
}
.kb-item p { font-size: 13px; color: #888; margin: 4px 0; }
.kb-actions { display: flex; gap: 8px; }
.kb-actions button { padding: 6px 12px; border: none; border-radius: 6px; font-size: 12px; cursor: pointer; background: #667eea; color: #fff; }
.kb-actions .btn-danger { background: #e74c3c; }
</style>
