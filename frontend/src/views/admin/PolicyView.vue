<template>
  <div class="view-container">
    <header class="view-header">
      <h2>📋 政策中心</h2>
      <button v-if="!showUpload" @click="startNew" class="btn-primary btn-upload">+ 上传 PDF</button>
    </header>

    <!-- Policy list -->
    <div class="panel">
      <h3>政策列表</h3>
      <div v-if="policies.length > 0 && !loading" class="policy-list">
        <div v-for="p in policies" :key="p.id"
             :class="['policy-item', { active: p.id === selectedPolicyId }]"
             @click="selectPolicy(p.id)">
          <span class="policy-name">{{ p.name || 'Unnamed Policy' }}</span>
          <span :class="['status-badge', p.status]">{{ p.status }}</span>
        </div>
      </div>
      <div v-if="loading" class="panel-empty">加载中...</div>
      <div v-if="!loading && policies.length === 0" class="panel-empty">暂无政策</div>
    </div>

    <div v-if="errorMsg" class="error-bar">{{ errorMsg }}</div>

    <!-- Upload zone -->
    <div v-if="showUpload" class="panel upload-panel">
      <h3>上传政策 PDF</h3>
      <p class="upload-desc">上传公司报销政策文档，AI 将解析为结构化的费用规则并构建可搜索的知识库。</p>
      <div class="upload-row">
        <label class="btn-primary file-label">
          选择文件
          <input type="file" accept=".pdf,.docx,.txt" @change="handleUpload" hidden />
        </label>
        <input v-model="newPolicyName" placeholder="政策名称（可选）" class="input-dark" />
        <label class="checkbox-label auto-publish-check">
          <input v-model="autoPublish" type="checkbox" /> 自动发布
        </label>
      </div>
      <p v-if="uploading" class="upload-status">上传 & 解析中...</p>

      <!-- Upload summary -->
      <div v-if="uploadSummary" class="upload-summary">
        <div class="summary-row">
          <span class="summary-icon">✅</span>
          <span class="summary-label">KB Created
            <span class="summary-detail">ID: {{ uploadSummary.kb_id }}</span>
          </span>
        </div>
        <div class="summary-row">
          <span class="summary-icon">🤖</span>
          <span class="summary-label">AI Parsed
            <span class="summary-detail">{{ domainCount }} domains / {{ ruleCount }} rules</span>
          </span>
        </div>
      </div>
    </div>

    <!-- Editor area -->
    <div v-if="selectedPolicyId && !showUpload" class="editor-area">
      <!-- Version tabs -->
      <div class="version-tabs" v-if="versions.length > 0">
        <button v-for="v in versions" :key="v.id"
                :class="['tab', { active: v.id === selectedVersionId }]"
                @click="selectVersion(v.id)">
          v{{ v.version_number }}
          <span :class="['status-dot', v.status]" />
        </button>
        <!-- Review entry button for draft versions with parsed domains -->
        <button v-if="hasReviewableVersion" @click="goToReview" class="tab tab-review">
          🔍 审核
        </button>
      </div>

      <!-- AI parse failure notification + re-parse button -->
      <div v-if="showReparse" class="reparse-banner">
        <p>⚠️ AI 解析失败，未提取到费用规则。</p>
        <div v-if="versionDetail?.ai_draft?.warnings?.length" class="reparse-warnings">
          <div v-for="w in versionDetail.ai_draft.warnings" :key="w" class="warn-item">⚠️ {{ w }}</div>
        </div>
        <button @click="doReparse" :disabled="reparsing" class="btn-secondary btn-reparse">
          {{ reparsing ? '重新解析中...' : '🔄 重新 AI 解析' }}
        </button>
      </div>

      <!-- Warnings — always show even when domains are empty -->
      <div v-if="!showReparse && versionDetail?.ai_draft?.warnings?.length" class="warnings">
        <div v-for="w in versionDetail.ai_draft.warnings" :key="w" class="warn-item">⚠️ {{ w }}</div>
      </div>

      <!-- Draft editor — new format (domains → rules) -->
      <div v-if="usingNewFormat && versionDetail?.ai_draft?.policy_doc" class="draft-editor">
        <h3 class="section-title">政策域（{{ domains.length }}）</h3>
        <div v-if="domains.length === 0" class="panel-empty">未找到政策域</div>

        <div v-for="(domain, di) in domains" :key="domain.id || di" class="domain-card">
          <div class="domain-header">
            <span class="domain-name">{{ domain.name }}</span>
            <span class="domain-id">ID: {{ domain.id }}</span>
            <span class="domain-rule-count">{{ domain.rules.length }} 条规则</span>
          </div>

          <div v-for="(rule, ri) in domain.rules" :key="rule.id || ri" class="rule-card">
            <div class="rule-type-badge" :class="'rule-type-' + rule.type">{{ rule.type }}</div>
            <div class="rule-body">
              <div class="rule-title">{{ rule.title }}</div>
              <div class="rule-details">
                <span v-if="rule.value !== null && rule.value !== undefined" class="rule-detail">
                  值: <strong>{{ rule.value }} {{ rule.unit }}</strong>
                </span>
                <span v-if="rule.condition" class="rule-detail">
                  条件: {{ rule.condition }}
                </span>
                <span v-if="rule.scope?.role" class="rule-detail">
                  职级: {{ rule.scope.role }}
                </span>
                <span v-if="rule.scope?.region" class="rule-detail">
                  地区: {{ rule.scope.region }}
                </span>
                <span v-if="rule.scope?.amount_range" class="rule-detail">
                  金额范围: {{ rule.scope.amount_range }}
                </span>
              </div>
              <div class="rule-raw" v-if="rule.raw_text">
                <span class="raw-label">原文:</span> {{ rule.raw_text }}
              </div>
              <div class="rule-meta" v-if="rule.confidence !== undefined">
                <span :class="['rule-confidence', confColor(rule.confidence)]">
                  置信度: {{ (rule.confidence * 100).toFixed(0) }}%
                </span>
              </div>
            </div>

            <!-- Edit fields for each rule -->
            <div class="rule-edit-fields">
              <label class="field">值
                <input v-model.number="rule.value" type="number" class="input-dark field-input" />
              </label>
              <label class="field">条件
                <input v-model="rule.condition" class="input-dark field-input" />
              </label>
              <label class="field">单位
                <input v-model="rule.unit" class="input-dark field-input" />
              </label>
            </div>
          </div>
        </div>

        <div class="editor-actions">
          <button @click="saveDraft" class="btn-primary">保存草稿</button>
          <button @click="doNormalize" :disabled="normalizing" class="btn-secondary">
            {{ normalizing ? '规范化中...' : '规范化 → Policy JSON' }}
          </button>
        </div>
      </div>

      <!-- Draft editor — legacy format (expense_types) -->
      <div v-if="!usingNewFormat && versionDetail?.ai_draft?.expense_types" class="draft-editor">
        <div v-if="versionDetail.ai_draft.warnings?.length" class="warnings">
          <div v-for="w in versionDetail.ai_draft.warnings" :key="w" class="warn-item">⚠️ {{ w }}</div>
        </div>

        <h3 class="section-title">费用类型（{{ legacyExpenseTypes.length }}）</h3>
        <div v-if="legacyExpenseTypes.length === 0" class="panel-empty">未找到费用类型</div>

        <div v-for="(et, i) in legacyExpenseTypes" :key="et.code || i" class="expense-card">
          <div class="card-header">
            <span class="card-name">{{ et.name }} <code class="card-code">{{ et.code }}</code></span>
            <span :class="['confidence', confColor(et.confidence)]">{{ (et.confidence * 100).toFixed(0) }}%</span>
          </div>
          <div class="card-fields">
            <label class="field">报销比例
              <input v-model.number="et.reimbursement_ratio" type="number" min="0" max="1" step="0.05" class="input-dark field-input" />
            </label>
            <label class="field">最大金额
              <input v-model.number="et.max_amount" type="number" class="input-dark field-input" />
            </label>
            <label class="field">审批阈值
              <input v-model.number="et.approval_over" type="number" class="input-dark field-input" />
            </label>
            <label class="field checkbox-field">
              <input v-model="et.need_invoice" type="checkbox" /> 需要发票
            </label>
            <label class="field checkbox-field">
              <input v-model="et.need_guest" type="checkbox" /> 需客户名单
            </label>
            <label class="field checkbox-field">
              <input v-model="et.need_attachment" type="checkbox" /> 需附件
            </label>
            <label class="field checkbox-field">
              <input v-model="et.enabled" type="checkbox" /> 启用
            </label>
          </div>
          <div class="card-source" v-if="et.source_text">
            <span class="source-label">来源:</span> {{ et.source_text }}
          </div>
        </div>

        <div class="editor-actions">
          <button @click="saveDraft" class="btn-primary">保存草稿</button>
          <button @click="doNormalize" :disabled="normalizing" class="btn-secondary">
            {{ normalizing ? '规范化中...' : '规范化 → Policy JSON' }}
          </button>
        </div>
      </div>

      <div v-if="selectedVersionId && !versionDetail?.ai_draft && !errorMsg" class="panel-empty">
        选择一个版本以编辑草稿
      </div>

      <!-- Policy JSON preview -->
      <details v-if="versionDetail?.policy_json" class="json-preview">
        <summary>Policy JSON（已发布规则）</summary>
        <pre>{{ JSON.stringify(versionDetail.policy_json, null, 2) }}</pre>
      </details>

      <!-- Publish / Activate bar -->
      <div v-if="versionDetail?.policy_json && versionDetail.status !== 'published'" class="publish-bar">
        <p>版本已规范化，可发布</p>
        <button @click="doPublish" :disabled="publishing" class="btn-publish">
          {{ publishing ? '发布中...' : '发布' }}
        </button>
      </div>
      <div v-if="versionDetail?.status === 'published'" class="action-bar">
        <span class="published-badge">✅ 已发布于 {{ formatDate(versionDetail.published_at) }}</span>
      </div>

      <!-- Activate (for archived versions) -->
      <div v-if="versionDetail && versionDetail.status === 'archived'" class="action-bar">
        <button @click="doActivate" :disabled="activating" class="btn-publish btn-rollback">
          {{ activating ? '激活中...' : '激活此版本（回滚）' }}
        </button>
      </div>
      <!-- Activate (for draft versions with policy_json) -->
      <div v-if="versionDetail && versionDetail.status === 'draft' && versionDetail.policy_json" class="action-bar">
        <button @click="doActivate" :disabled="activating" class="btn-publish">
          {{ activating ? '发布中...' : '直接发布此草稿' }}
        </button>
      </div>
    </div>

    <!-- KB sidebar for current policy version -->
    <div v-if="currentKbInfo" class="panel kb-sidebar">
      <h3>📚 关联知识库: {{ currentKbInfo.name }}</h3>
      <div class="kb-meta-row">
        <span class="kb-meta-tag">ID: {{ currentKbInfo.id }}</span>
        <span :class="['kb-meta-tag', currentKbInfo.is_active ? 'tag-active' : 'tag-inactive']">
          {{ currentKbInfo.is_active ? 'active' : 'inactive' }}
        </span>
      </div>
      <div v-if="currentKbDocs.length > 0" class="kb-docs-list">
        <div v-for="doc in currentKbDocs" :key="doc.id" class="kb-doc-item">
          <div :class="['kb-doc-hdr', { open: expandedDocs.has(doc.id) }]"
               @click="toggleDocChunks(doc.id)">
            <span class="kb-doc-name">📄 {{ doc.filename }}</span>
            <span class="kb-doc-meta">{{ doc.chunk_count }} chunks</span>
          </div>
          <div v-if="expandedDocs.has(doc.id) && chunkDetails.get(doc.id)" class="kb-doc-chunks">
            <div v-for="c in (chunkDetails.get(doc.id) || [])" :key="c.index" class="kb-chunk-item">
              <span class="cidx">#{{ c.index }}</span>
              <span class="ctext">{{ c.text }}</span>
            </div>
          </div>
        </div>
      </div>
      <div class="kb-search-box">
        <h4>🔍 搜索测试</h4>
        <div class="kb-search-row">
          <input v-model="kbSearchQ" placeholder="搜索政策内容..." class="input-dark kb-search-input" @keyup.enter="doKbSearch" />
          <button @click="doKbSearch" :disabled="kbSearching" class="btn-sm">Go</button>
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
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { policyApi, type PolicyListItem, type PolicyVersionItem, type PolicyVersionDetail, type PolicyDraft, type DraftExpenseType, type PolicyDomain } from '../../api/policy'
import { kbApi } from '../../api/knowledge'

const router = useRouter()

const policies = ref<PolicyListItem[]>([])
const selectedPolicyId = ref<number | null>(null)
const selectedVersionId = ref<number | null>(null)
const versionDetail = ref<PolicyVersionDetail | null>(null)
const versions = ref<PolicyVersionItem[]>([])
const uploading = ref(false)
const normalizing = ref(false)
const publishing = ref(false)
const activating = ref(false)
const reparsing = ref(false)

// New format state
const domains = reactive<PolicyDomain[]>([])
// Legacy format state
const legacyExpenseTypes = reactive<DraftExpenseType[]>([])

const newPolicyName = ref('')
const errorMsg = ref('')
const showUpload = ref(true)
const loading = ref(false)
const uploadSummary = ref<{ kb_id: number | null; policy_name: string; version_number: number } | null>(null)
const autoPublish = ref(false)

const currentKbInfo = ref<any>(null)
const currentKbDocs = ref<any[]>([])
const kbSearchQ = ref('')
const kbSearchResults = ref<any[]>([])
const kbSearching = ref(false)
const expandedDocs = ref<Set<number>>(new Set())
const chunkDetails = ref<Map<number, any[]>>(new Map())

const usingNewFormat = computed(() => {
  return versionDetail.value?.ai_draft?.policy_doc?.domains?.length > 0
})

const domainCount = computed(() => domains.length)
const ruleCount = computed(() => domains.reduce((s: number, d: PolicyDomain) => s + d.rules.length, 0))

const hasReviewableVersion = computed(() => {
  return selectedVersionId.value && versionDetail.value?.ai_draft?.policy_doc?.domains?.length > 0
    && versionDetail.value?.status === 'draft'
})

const showReparse = computed(() => {
  return selectedVersionId.value && versionDetail.value?.status === 'draft'
    && (!versionDetail.value?.ai_draft?.policy_doc?.domains?.length
      || versionDetail.value.ai_draft.policy_doc.domains.every((d: PolicyDomain) => !d.rules?.length))
})

onMounted(loadPolicies)

function loadPolicies() {
  loading.value = true
  policyApi.list().then(r => policies.value = r).catch(() => errorMsg.value = 'Failed to load policies')
    .finally(() => loading.value = false)
}

function startNew() {
  selectedPolicyId.value = null
  selectedVersionId.value = null
  versionDetail.value = null
  versions.value = []
  domains.length = 0
  legacyExpenseTypes.length = 0
  showUpload.value = true
  errorMsg.value = ''
  uploadSummary.value = null
  clearCurrentKb()
}

function selectPolicy(id: number) {
  selectedPolicyId.value = id
  selectedVersionId.value = null
  versionDetail.value = null
  domains.length = 0
  legacyExpenseTypes.length = 0
  showUpload.value = false
  errorMsg.value = ''
  uploadSummary.value = null
  clearCurrentKb()
  policyApi.listVersions(id).then(r => versions.value = r).catch(() => versions.value = [])
}

function selectVersion(versionId: number) {
  if (!selectedPolicyId.value) return
  selectedVersionId.value = versionId
  errorMsg.value = ''
  clearCurrentKb()
  policyApi.getVersion(selectedPolicyId.value, versionId).then(v => {
    versionDetail.value = v
    domains.length = 0
    legacyExpenseTypes.length = 0
    if (v.ai_draft?.policy_doc?.domains) {
      for (const d of v.ai_draft.policy_doc.domains) {
        domains.push({ ...d })
      }
    } else if (v.ai_draft?.expense_types) {
      for (const et of v.ai_draft.expense_types) {
        legacyExpenseTypes.push({ ...et })
      }
    }
    if (v.kb_id) loadCurrentKb(v.kb_id)
  }).catch(() => {
    versionDetail.value = null
    errorMsg.value = 'Failed to load version'
  })
}

function handleUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploading.value = true
  errorMsg.value = ''
  policyApi.uploadPdf(file, newPolicyName.value || undefined, autoPublish.value)
    .then(async (res) => {
      await loadPolicies()
      selectedPolicyId.value = res.policy_id
      selectedVersionId.value = res.version_id
      showUpload.value = false
      newPolicyName.value = ''
      uploadSummary.value = { kb_id: res.kb_id, policy_name: res.message, version_number: res.version_number }
      versions.value = await policyApi.listVersions(res.policy_id)
      versionDetail.value = await policyApi.getVersion(res.policy_id, res.version_id)
      domains.length = 0
      legacyExpenseTypes.length = 0
      if (versionDetail.value.ai_draft?.policy_doc?.domains) {
        for (const d of versionDetail.value.ai_draft.policy_doc.domains) {
          domains.push({ ...d })
        }
      } else if (versionDetail.value.ai_draft?.expense_types) {
        for (const et of versionDetail.value.ai_draft.expense_types) {
          legacyExpenseTypes.push({ ...et })
        }
      }
      if (res.kb_id) await loadCurrentKb(res.kb_id)
    })
    .catch((e: any) => {
      errorMsg.value = e.response?.data?.detail || e.message || 'Upload failed'
    })
    .finally(() => { uploading.value = false; input.value = '' })
}

function confColor(c: number): string {
  if (c >= 0.9) return 'high'
  if (c >= 0.7) return 'medium'
  return 'low'
}

function saveDraft() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  errorMsg.value = ''
  let payload: PolicyDraft
  if (usingNewFormat.value) {
    payload = {
      enterprise: 'default', description: '',
      expense_types: [],
      policy_doc: {
        doc_id: versionDetail.value?.ai_draft?.policy_doc?.doc_id || '',
        title: versionDetail.value?.ai_draft?.policy_doc?.title || '',
        version: versionDetail.value?.ai_draft?.policy_doc?.version || '',
        domains: [...domains],
      },
      warnings: versionDetail.value?.ai_draft?.warnings || [],
      metadata: versionDetail.value?.ai_draft?.metadata || {},
    } as any
  } else {
    payload = {
      enterprise: 'default', description: '',
      expense_types: [...legacyExpenseTypes], warnings: [], metadata: {},
    }
  }
  policyApi.updateDraft(selectedPolicyId.value, selectedVersionId.value, payload)
    .catch((e: any) => { errorMsg.value = e.response?.data?.detail || 'Save failed' })
}

function doNormalize() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  normalizing.value = true
  errorMsg.value = ''
  policyApi.normalize(selectedPolicyId.value, selectedVersionId.value)
    .then(() => policyApi.getVersion(selectedPolicyId.value!, selectedVersionId.value!))
    .then(v => versionDetail.value = v)
    .catch((e: any) => { errorMsg.value = e.response?.data?.detail || 'Normalize failed' })
    .finally(() => normalizing.value = false)
}

function doPublish() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  if (!confirm('发布此版本？')) return
  publishing.value = true
  errorMsg.value = ''
  policyApi.publish(selectedPolicyId.value, selectedVersionId.value)
    .then(() => Promise.all([
      policyApi.getVersion(selectedPolicyId.value!, selectedVersionId.value!),
    ]))
    .then(([v]) => { versionDetail.value = v; loadPolicies() })
    .catch((e: any) => { errorMsg.value = e.response?.data?.detail || 'Publish failed' })
    .finally(() => publishing.value = false)
}

function doActivate() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  activating.value = true
  errorMsg.value = ''
  import('../../api').then(m => m.default.post(`/policy/${selectedPolicyId.value}/versions/${selectedVersionId.value}/activate`))
    .then(() => Promise.all([
      policyApi.getVersion(selectedPolicyId.value!, selectedVersionId.value!),
      loadPolicies(),
    ]))
    .then(([v]) => { versionDetail.value = v })
    .catch((e: any) => { errorMsg.value = e.response?.data?.detail || 'Activate failed' })
    .finally(() => activating.value = false)
}

function doReparse() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  reparsing.value = true
  errorMsg.value = ''
  policyApi.reparse(selectedPolicyId.value, selectedVersionId.value)
    .then(() => policyApi.getVersion(selectedPolicyId.value!, selectedVersionId.value!))
    .then(v => {
      versionDetail.value = v
      domains.length = 0
      legacyExpenseTypes.length = 0
      if (v.ai_draft?.policy_doc?.domains) {
        for (const d of v.ai_draft.policy_doc.domains) {
          domains.push({ ...d })
        }
      } else if (v.ai_draft?.expense_types) {
        for (const et of v.ai_draft.expense_types) {
          legacyExpenseTypes.push({ ...et })
        }
      }
    })
    .catch((e: any) => { errorMsg.value = e.response?.data?.detail || '重新解析失败' })
    .finally(() => reparsing.value = false)
}

function loadCurrentKb(kbId: number) {
  Promise.all([
    kbApi.listBases().then(all => all.find(b => b.id === kbId) || null),
    kbApi.listDocuments(kbId),
  ]).then(([info, docs]) => {
    currentKbInfo.value = info
    currentKbDocs.value = docs
  }).catch(() => { /* non-critical */ })
}

function clearCurrentKb() {
  currentKbInfo.value = null
  currentKbDocs.value = []
  kbSearchQ.value = ''
  kbSearchResults.value = []
}

function goToReview() {
  if (!selectedPolicyId.value || !selectedVersionId.value) return
  const { href } = router.resolve({ path: `/admin/policy/review/${selectedPolicyId.value}/${selectedVersionId.value}` })
  window.open(href, '_blank')
}

function doKbSearch() {
  if (!kbSearchQ.value.trim() || !currentKbInfo.value?.id) return
  kbSearching.value = true
  kbApi.search(kbSearchQ.value.trim(), currentKbInfo.value.id, 5)
    .then(r => kbSearchResults.value = r)
    .catch(() => kbSearchResults.value = [])
    .finally(() => kbSearching.value = false)
}

function toggleDocChunks(docId: number) {
  if (expandedDocs.value.has(docId)) { expandedDocs.value.delete(docId); return }
  expandedDocs.value.add(docId)
  if (!chunkDetails.value.has(docId)) {
    kbApi.getChunks(docId).then(r => chunkDetails.value.set(docId, r.chunks)).catch(() => chunkDetails.value.set(docId, []))
  }
}

function scoreColor(s: number): string {
  if (s >= 0.8) return '#34d399'
  if (s >= 0.6) return '#fbbf24'
  return '#f87171'
}

function formatDate(d: string | null): string {
  return d ? new Date(d).toLocaleDateString() : '—'
}
</script>

<style scoped>
.view-container { padding: 24px 32px; max-width: 1200px; }
.view-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
.view-header h2 { font-size: 20px; font-weight: 700; color: #fff; margin: 0; }

.panel {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 14px; padding: 20px; margin-bottom: 16px;
}
.panel h3 { font-size: 14px; font-weight: 600; color: #fff; margin: 0 0 12px 0; }
.panel-empty {
  font-size: 12px; color: rgba(255,255,255,0.2); text-align: center; padding: 16px 0;
}

.policy-list { display: flex; flex-direction: column; gap: 4px; }
.policy-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 14px; border-radius: 10px; cursor: pointer;
  transition: background 0.15s;
}
.policy-item:hover { background: rgba(255,255,255,0.03); }
.policy-item.active { background: rgba(99,102,241,0.1); border: 1px solid rgba(99,102,241,0.2); }
.policy-name { font-size: 13px; font-weight: 500; color: #e4e4e7; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.status-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 6px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap;
}
.status-badge.draft { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.35); }
.status-badge.published { background: rgba(52,211,153,0.12); color: #34d399; }
.status-badge.archived { background: rgba(248,113,113,0.1); color: #fca5a5; }

.error-bar {
  background: rgba(248,113,113,0.1); border: 1px solid rgba(248,113,113,0.2);
  border-radius: 10px; padding: 10px 16px; font-size: 13px; color: #fca5a5; margin-bottom: 16px;
}

.upload-panel { text-align: center; }
.upload-desc { font-size: 13px; color: rgba(255,255,255,0.3); margin-bottom: 16px; }
.upload-row { display: flex; gap: 10px; align-items: center; justify-content: center; }
.file-label { cursor: pointer; display: inline-block; flex-shrink: 0; }
.upload-status { margin-top: 12px; font-size: 13px; color: rgba(99,102,241,0.6); }

.upload-summary {
  background: linear-gradient(135deg, rgba(99,102,241,0.06), rgba(139,92,246,0.04));
  border: 1px solid rgba(99,102,241,0.12); border-radius: 12px; padding: 14px 18px;
  display: flex; flex-direction: column; gap: 8px; margin-top: 16px;
}
.summary-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.summary-icon { font-size: 14px; }
.summary-label { font-size: 13px; font-weight: 600; color: #c4b5fd; }
.summary-detail { font-size: 12px; color: rgba(255,255,255,0.4); margin-left: 8px; }

.editor-area { display: flex; flex-direction: column; gap: 14px; }
.version-tabs { display: flex; gap: 6px; flex-wrap: wrap; }
.tab {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 12px; border-radius: 8px; font-size: 13px; cursor: pointer;
  border: 1px solid rgba(255,255,255,0.06); background: rgba(255,255,255,0.02);
  color: rgba(255,255,255,0.4); transition: all 0.15s;
}
.tab:hover { background: rgba(255,255,255,0.04); color: #e4e4e7; }
.tab.active { background: rgba(99,102,241,0.1); border-color: rgba(99,102,241,0.2); color: #a5b4fc; }
.tab-review { background: rgba(99,102,241,0.15); border-color: rgba(99,102,241,0.25); color: #818cf8; font-weight: 600; }
.tab-review:hover { background: rgba(99,102,241,0.25); color: #a5b4fc; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.status-dot.draft { background: rgba(255,255,255,0.3); }
.status-dot.published { background: #34d399; }
.status-dot.archived { background: #f87171; }

.draft-editor { display: flex; flex-direction: column; gap: 14px; }
.section-title { font-size: 15px; font-weight: 600; color: #fff; }
.warnings { display: flex; flex-direction: column; gap: 4px; }
.warn-item { font-size: 12px; color: #fbbf24; padding: 6px 10px; background: rgba(251,191,36,0.08); border-radius: 8px; }

/* Domain + Rule cards (new format) */
.domain-card {
  background: #0f0f14; border: 1px solid rgba(99,102,241,0.12);
  border-radius: 12px; padding: 14px; margin-bottom: 8px;
}
.domain-header {
  display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
}
.domain-name { font-size: 15px; font-weight: 700; color: #e4e4e7; }
.domain-id { font-size: 10px; color: rgba(255,255,255,0.2); background: rgba(255,255,255,0.04); padding: 2px 6px; border-radius: 4px; }
.domain-rule-count { font-size: 11px; color: rgba(255,255,255,0.3); margin-left: auto; }

.rule-card {
  display: flex; flex-direction: column; gap: 6px;
  padding: 10px 12px; margin-bottom: 6px;
  background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04);
  border-radius: 10px;
}

.rule-type-badge {
  font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 5px;
  text-transform: uppercase; letter-spacing: 0.3px; width: fit-content;
}
.rule-type-limit { background: rgba(52,211,153,0.12); color: #34d399; }
.rule-type-ratio { background: rgba(99,102,241,0.12); color: #a5b4fc; }
.rule-type-approval { background: rgba(251,191,36,0.12); color: #fbbf24; }
.rule-type-requirement { background: rgba(139,92,246,0.12); color: #c4b5fd; }
.rule-type-restriction { background: rgba(248,113,113,0.12); color: #fca5a5; }
.rule-type-other { background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.4); }

.rule-body { font-size: 13px; }
.rule-title { font-weight: 600; color: #e4e4e7; margin-bottom: 2px; }
.rule-details { display: flex; flex-wrap: wrap; gap: 8px; font-size: 11px; color: rgba(255,255,255,0.4); }
.rule-detail strong { color: rgba(255,255,255,0.6); }
.rule-raw { font-size: 11px; color: rgba(255,255,255,0.25); margin-top: 4px; }
.raw-label { color: rgba(255,255,255,0.15); }
.rule-meta { margin-top: 4px; }

.rule-edit-fields {
  display: flex; flex-wrap: wrap; gap: 8px; margin-top: 6px; padding-top: 6px;
  border-top: 1px solid rgba(255,255,255,0.04);
}

/* Legacy expense cards */
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

.json-preview {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 12px; padding: 14px;
}
.json-preview summary { font-size: 13px; font-weight: 600; color: rgba(255,255,255,0.5); cursor: pointer; margin-bottom: 10px; }
.json-preview pre {
  font-size: 11px; color: rgba(255,255,255,0.4); max-height: 350px; overflow: auto;
  font-family: 'Consolas', 'Courier New', monospace; white-space: pre-wrap;
  background: #18181b; border-radius: 8px; padding: 12px;
}

.publish-bar {
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(52,211,153,0.06); border: 1px solid rgba(52,211,153,0.12);
  border-radius: 12px; padding: 14px 18px;
}
.publish-bar p { font-size: 13px; color: rgba(255,255,255,0.4); }
.published-badge { font-size: 13px; color: #34d399; }
.action-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; border-radius: 12px;
  background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.04);
}

.kb-sidebar { margin-top: 16px; }
.kb-meta-row { display: flex; gap: 6px; margin-bottom: 8px; }
.kb-meta-tag { font-size: 10px; padding: 2px 8px; border-radius: 5px; font-weight: 500;
  background: rgba(255,255,255,0.03); color: rgba(255,255,255,0.3); }
.tag-active { background: rgba(52,211,153,0.1); color: #34d399; }
.tag-inactive { background: rgba(248,113,113,0.08); color: #fca5a5; }
.kb-docs-list { display: flex; flex-direction: column; gap: 4px; }
.kb-doc-hdr { display: flex; align-items: center; gap: 8px; padding: 7px 10px; border-radius: 8px; cursor: pointer; }
.kb-doc-hdr:hover { background: rgba(255,255,255,0.03); }
.kb-doc-hdr.open { background: rgba(99,102,241,0.06); }
.kb-doc-name { font-size: 12px; color: rgba(255,255,255,0.55); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kb-doc-meta { font-size: 10px; color: rgba(255,255,255,0.2); white-space: nowrap; }
.kb-doc-chunks { margin-left: 10px; padding-left: 10px; border-left: 1px solid rgba(99,102,241,0.1); display: flex; flex-direction: column; gap: 2px; }
.kb-chunk-item { display: flex; gap: 6px; font-size: 11px; padding: 3px 0; }
.cidx { color: rgba(99,102,241,0.4); font-weight: 600; min-width: 22px; }
.ctext { color: rgba(255,255,255,0.35); line-height: 1.4; word-break: break-all; }
.kb-search-box { margin-top: 12px; }
.kb-search-box h4 { font-size: 12px; font-weight: 600; color: rgba(255,255,255,0.4); margin-bottom: 8px; }
.kb-search-row { display: flex; gap: 6px; }
.kb-search-input { flex: 1; padding: 8px 12px; font-size: 12px; }
.kb-results { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.kb-result-item { padding: 9px 12px; background: rgba(255,255,255,0.015); border: 1px solid rgba(255,255,255,0.04); border-radius: 8px; }
.kb-result-hdr { display: flex; align-items: center; gap: 8px; margin-bottom: 3px; }
.result-rank { font-size: 10px; color: rgba(99,102,241,0.4); font-weight: 600; }
.result-file { font-size: 11px; color: rgba(255,255,255,0.3); flex: 1; }
.result-score { font-size: 12px; font-weight: 700; }
.result-snippet { font-size: 11px; color: rgba(255,255,255,0.45); line-height: 1.5; }

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
  background: rgba(99,102,241,0.08); color: #a5b4fc;
}
.btn-secondary:hover { background: rgba(99,102,241,0.15); }
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-publish {
  padding: 9px 20px; background: linear-gradient(135deg, #34d399, #10b981);
  color: #fff; border: none; border-radius: 10px; font-size: 13px; font-weight: 600;
  cursor: pointer;
}
.btn-publish:hover { box-shadow: 0 4px 16px rgba(52,211,153,0.3); }
.btn-publish:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-rollback { background: linear-gradient(135deg, #f59e0b, #d97706); }

.btn-sm {
  padding: 6px 12px; border-radius: 8px; font-size: 12px; font-weight: 500;
  cursor: pointer; border: none; background: rgba(99,102,241,0.1); color: #a5b4fc;
}
.btn-sm:hover { background: rgba(99,102,241,0.2); }

.input-dark {
  padding: 9px 14px;
  background: #18181b; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; color: #fff; font-size: 13px; outline: none;
  transition: border-color 0.2s;
}
.input-dark:focus { border-color: rgba(99,102,241,0.4); }
.input-dark::placeholder { color: rgba(255,255,255,0.15); }

.checkbox-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: rgba(255,255,255,0.4); cursor: pointer;
  white-space: nowrap;
}
.checkbox-label input[type="checkbox"] { accent-color: #6366f1; }
</style>
