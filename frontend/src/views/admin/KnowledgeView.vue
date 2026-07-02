<template>
  <div class="view-container">
    <header class="view-header">
      <h2>📚 知识库管理</h2>
    </header>

    <section class="panel">
      <h3>📦 所有知识库</h3>

      <div class="kb-create">
        <input v-model="kbName" placeholder="知识库名称" class="input-dark" />
        <div class="kb-create-row">
          <input v-model="kbDesc" placeholder="描述（可选）" class="input-dark" />
          <button @click="createKB" class="btn-primary btn-sm">创建</button>
        </div>
      </div>

      <div v-if="kbs.length === 0" class="panel-empty">暂无知识库</div>
      <div v-for="kb in kbs" :key="kb.id">
        <div class="kb-row" @click="toggleKb(kb.id)">
          <div class="kb-row-info">
            <span class="kb-row-name">{{ kb.name }}</span>
            <span class="kb-row-desc">{{ kb.description }}</span>
          </div>
          <div class="kb-row-meta">
            <span class="kb-count">{{ kb.document_count }} 文档</span>
            <label class="btn-sm btn-upload-kb" @click.stop>
              <input type="file" hidden @change="uploadDoc(kb.id, $event)" accept=".txt,.docx,.pdf" />
              {{ uploadingDoc === kb.id ? '...' : '+' }}
            </label>
            <button class="btn-sm btn-danger" @click.stop="deleteKB(kb.id)">×</button>
          </div>
        </div>
        <div v-if="expandedKb === kb.id" class="kb-expanded-docs">
          <div v-if="!kb._docs || kb._docs.length === 0" class="panel-empty">暂无文档</div>
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
    </section>

    <section class="panel" style="margin-top: 16px;">
      <h3>ChromaDB 集合信息</h3>
      <button @click="fetchChromaStats" class="btn-sm">获取 Stats</button>
      <pre v-if="chromaStatsData" class="raw-pre">{{ JSON.stringify(chromaStatsData, null, 2) }}</pre>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../../api'
import { kbApi } from '../../api/knowledge'

const kbs = ref<any[]>([])
const kbName = ref('')
const kbDesc = ref('')
const uploadingDoc = ref<number | null>(null)
const expandedKb = ref<number | null>(null)
const expandedDocs = ref<Set<number>>(new Set())
const chunkDetails = ref<Map<number, any[]>>(new Map())
const chromaStatsData = ref<any>(null)

onMounted(loadKBs)

async function loadKBs() {
  try { kbs.value = (await api.get('/knowledge/bases')).data } catch {}
}

async function createKB() {
  if (!kbName.value.trim()) return
  await api.post('/knowledge/bases', { name: kbName.value, description: kbDesc.value })
  kbName.value = ''; kbDesc.value = ''
  await loadKBs()
}

async function deleteKB(id: number) {
  try {
    await api.delete(`/knowledge/bases/${id}`)
    await loadKBs()
  } catch (e: any) {
    alert(e.response?.data?.detail?.message || e.message || '删除失败')
  }
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
  if (!chunkDetails.value.has(docId)) {
    try {
      const res = await kbApi.getChunks(docId)
      chunkDetails.value.set(docId, res.chunks)
    } catch { chunkDetails.value.set(docId, []) }
  }
}

async function fetchChromaStats() {
  try {
    const res = await api.get('/knowledge/chroma-stats')
    chromaStatsData.value = res.data
  } catch { alert('获取失败') }
}
</script>

<style scoped>
.view-container { padding: 24px 32px; }
.view-header { margin-bottom: 20px; }
.view-header h2 { font-size: 20px; font-weight: 700; color: #fff; margin: 0; }

.panel {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 14px; padding: 20px;
  display: flex; flex-direction: column; gap: 12px;
}
.panel h3 { font-size: 14px; font-weight: 600; color: #fff; margin: 0; }
.panel-empty {
  font-size: 12px; color: rgba(255,255,255,0.2); text-align: center; padding: 16px 0;
}

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

.kb-expanded-docs { margin-left: 10px; border-left: 1px solid rgba(255,255,255,0.05); padding-left: 14px; margin-bottom: 8px; }
.kb-exp-doc { margin-bottom: 4px; }
.kb-exp-doc-hdr { display: flex; align-items: center; gap: 8px; padding: 6px 10px; border-radius: 8px; cursor: pointer; transition: background 0.15s; }
.kb-exp-doc-hdr:hover { background: rgba(255,255,255,0.03); }
.kb-doc-name { font-size: 12px; color: rgba(255,255,255,0.55); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb-doc-meta { font-size: 10px; color: rgba(255,255,255,0.2); white-space: nowrap; }
.doc-expand-icon { font-size: 10px; color: rgba(255,255,255,0.25); width: 14px; text-align: center; }

.kb-doc-chunks { margin-left: 10px; padding-left: 10px; border-left: 1px solid rgba(99,102,241,0.1); display: flex; flex-direction: column; gap: 2px; }
.kb-chunk-item { display: flex; gap: 6px; font-size: 11px; padding: 3px 0; }
.cidx { color: rgba(99,102,241,0.4); font-weight: 600; min-width: 22px; flex-shrink: 0; }
.ctext { color: rgba(255,255,255,0.35); line-height: 1.4; word-break: break-all; }

.raw-pre {
  font-size: 11px; color: rgba(255,255,255,0.4); max-height: 350px; overflow: auto;
  font-family: 'Consolas', 'Courier New', monospace; white-space: pre-wrap;
  background: #18181b; border-radius: 8px; padding: 12px;
}

.btn-primary {
  padding: 9px 16px; background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer; transition: box-shadow 0.2s;
}
.btn-primary:hover { box-shadow: 0 4px 16px rgba(99,102,241,0.3); }
.btn-sm {
  padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 500;
  cursor: pointer; border: none; transition: all 0.15s;
  background: rgba(99,102,241,0.1); color: #a5b4fc; display: inline-flex; align-items: center;
}
.btn-sm:hover { background: rgba(99,102,241,0.2); }
.btn-danger { background: rgba(248,113,113,0.1); color: #fca5a5; }
.btn-danger:hover { background: rgba(248,113,113,0.2); }
.btn-upload-kb { font-size: 14px; padding: 4px 10px; }

.input-dark {
  padding: 9px 14px;
  background: #18181b; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; color: #fff; font-size: 13px; outline: none;
  transition: border-color 0.2s;
}
.input-dark:focus { border-color: rgba(99,102,241,0.4); }
.input-dark::placeholder { color: rgba(255,255,255,0.15); }
</style>
