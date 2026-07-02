<template>
  <div class="dev-debug-view">
    <header class="view-header" v-if="isDev">
      <h2>🔧 调试控制台</h2>
      <span class="dev-badge">DEV ONLY</span>
    </header>

    <template v-if="isDev">
      <section class="panel">
        <h3>ChromaDB 搜索</h3>
        <div class="search-controls">
          <div class="search-row">
            <input v-model="searchQuery" placeholder="输入搜索关键词..." class="input-dark" style="flex:1;" @keyup.enter="doSearch" />
            <button @click="doSearch" :disabled="searching" class="btn-primary">{{ searching ? '搜索中...' : '搜索' }}</button>
          </div>
          <div class="search-params">
            <label class="param-label">Top-K
              <select v-model.number="searchTopK" class="input-dark param-select">
                <option :value="1">1</option><option :value="3">3</option><option :value="5">5</option>
                <option :value="10">10</option><option :value="20">20</option><option :value="50">50</option>
              </select>
            </label>
            <label class="param-label">阈值
              <select v-model.number="searchThreshold" class="input-dark param-select">
                <option :value="0">None</option><option :value="0.3">0.3</option><option :value="0.5">0.5</option>
                <option :value="0.7">0.7</option><option :value="0.8">0.8</option><option :value="0.9">0.9</option>
              </select>
            </label>
            <label class="param-label">KB
              <input v-model.number="searchKbId" placeholder="KB ID" class="input-dark param-select" />
            </label>
            <label class="param-label">模式
              <select v-model="searchMode" class="input-dark param-select">
                <option value="normal">Normal</option><option value="raw">Raw (ChromaDB)</option>
              </select>
            </label>
          </div>
        </div>

        <div v-if="searchMeta" class="search-meta">
          {{ searchMeta.total_results }} 条结果 · top_k={{ searchMeta.top_k }}
          <span v-if="searchMeta.threshold"> · threshold={{ searchMeta.threshold }}</span>
          <span v-if="searchMeta.kb_id_filter"> · kb_id={{ searchMeta.kb_id_filter }}</span>
        </div>

        <div v-if="searchResults.length > 0" class="search-results">
          <div v-for="(r, idx) in searchResults" :key="idx" class="search-result-item">
            <div class="sr-header">
              <span class="sr-rank">#{{ idx + 1 }}</span>
              <span class="sr-file">{{ r.filename }}</span>
              <span class="sr-score" :style="{ color: scoreColor(r.score ?? r.cosine_similarity ?? 0) }">
                {{ ((r.score ?? r.cosine_similarity ?? 0) * 100).toFixed(1) }}%
              </span>
              <span v-if="r.distance !== undefined" class="sr-distance">d={{ r.distance }}</span>
            </div>
            <div class="sr-snippet">{{ r.snippet || r.text }}</div>
          </div>
        </div>
      </section>

      <section class="panel" style="margin-top: 16px;">
        <h3>ChromaDB 集合信息</h3>
        <button @click="fetchStats" class="btn-sm">获取 Stats</button>
        <pre v-if="chromaStats" class="raw-pre">{{ JSON.stringify(chromaStats, null, 2) }}</pre>
      </section>
    </template>

    <div v-else class="disabled-msg">
      <p>🔒 调试控制台仅在开发环境可用。</p>
      <p>在 URL 后添加 <code>?dev=true</code> 强制启用。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import api from '../../api'

const isDev = computed(() => import.meta.env.DEV || new URLSearchParams(window.location.search).has('dev'))

const searchQuery = ref('')
const searchTopK = ref(5)
const searchThreshold = ref(0)
const searchKbId = ref<number | undefined>()
const searchMode = ref<'normal' | 'raw'>('normal')
const searching = ref(false)
const searchResults = ref<any[]>([])
const searchMeta = ref<any>(null)
const chromaStats = ref<any>(null)

function scoreColor(score: number): string {
  if (score >= 0.6) return '#34d399'
  if (score >= 0.3) return '#fbbf24'
  return '#f87171'
}

async function doSearch() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  try {
    const params: any = { q: searchQuery.value.trim(), top_k: searchTopK.value }
    if (searchKbId.value !== undefined && searchKbId.value !== null) params.kb_id = searchKbId.value
    if (searchThreshold.value > 0) params.threshold = searchThreshold.value

    if (searchMode.value === 'raw') {
      const res = await api.get('/knowledge/chroma-search-raw', { params })
      searchResults.value = res.data.results || []
      searchMeta.value = {
        total_results: res.data.total_results,
        top_k: res.data.top_k,
        threshold: res.data.threshold,
        kb_id_filter: res.data.kb_id_filter,
      }
    } else {
      const res = await api.get('/knowledge/search', { params })
      searchResults.value = res.data
      searchMeta.value = { total_results: res.data.length, top_k: params.top_k, threshold: params.threshold, kb_id_filter: params.kb_id }
    }
  } catch (e: any) {
    alert('搜索失败: ' + (e.response?.data?.detail || e.message))
    searchResults.value = []
    searchMeta.value = null
  } finally { searching.value = false }
}

async function fetchStats() {
  try {
    const res = await api.get('/knowledge/chroma-stats')
    chromaStats.value = res.data
  } catch { alert('获取失败') }
}
</script>

<style scoped>
.dev-debug-view { padding: 24px 32px; }
.view-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.view-header h2 { font-size: 20px; font-weight: 700; color: #fff; margin: 0; }
.dev-badge { background: #ff5722; color: white; font-size: 11px; padding: 3px 10px; border-radius: 99px; font-weight: 600; }
.disabled-msg {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; height: 60vh; color: rgba(255,255,255,0.3);
  gap: 8px; font-size: 14px;
}
.disabled-msg code { background: rgba(255,255,255,0.06); padding: 2px 8px; border-radius: 4px; }

.panel {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 14px; padding: 20px;
  display: flex; flex-direction: column; gap: 12px;
}
.panel h3 { font-size: 14px; font-weight: 600; color: #fff; margin: 0; }

.search-controls { display: flex; flex-direction: column; gap: 10px; }
.search-row { display: flex; gap: 10px; }
.search-params { display: flex; gap: 12px; flex-wrap: wrap; }
.param-label { display: flex; align-items: center; gap: 6px; font-size: 12px; color: rgba(255,255,255,0.4); }
.param-select { width: auto; padding: 6px 10px; font-size: 12px; }

.search-meta {
  padding: 8px 12px; background: rgba(255,255,255,0.02); border-radius: 8px;
  font-size: 12px; color: rgba(255,255,255,0.3);
}
.search-results { display: flex; flex-direction: column; gap: 8px; }
.search-result-item {
  padding: 12px 14px;
  background: rgba(255,255,255,0.015); border: 1px solid rgba(255,255,255,0.04);
  border-radius: 10px;
}
.sr-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.sr-rank { font-size: 11px; color: rgba(99,102,241,0.5); font-weight: 600; min-width: 24px; }
.sr-file { font-size: 13px; color: #e4e4e7; font-weight: 500; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sr-score { font-size: 14px; font-weight: 700; min-width: 52px; text-align: right; }
.sr-distance { font-size: 11px; color: rgba(255,255,255,0.2); min-width: 64px; text-align: right; }
.sr-snippet { font-size: 12px; color: rgba(255,255,255,0.5); line-height: 1.5; padding-left: 24px; word-break: break-word; }

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
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-sm {
  padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 500;
  cursor: pointer; border: none; background: rgba(99,102,241,0.1); color: #a5b4fc;
}
.btn-sm:hover { background: rgba(99,102,241,0.2); }
.input-dark {
  padding: 9px 14px;
  background: #18181b; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; color: #fff; font-size: 13px; outline: none;
}
.input-dark:focus { border-color: rgba(99,102,241,0.4); }
.input-dark::placeholder { color: rgba(255,255,255,0.15); }
</style>
