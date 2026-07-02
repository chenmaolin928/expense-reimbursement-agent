<template>
  <div class="rule-list-panel">
    <div class="panel-header">
      <h3>📋 规则结构</h3>
      <div class="header-actions">
        <span v-if="mergeMode" class="merge-info">已选 {{ selectedForMerge.length }} 条</span>
        <button v-if="mergeMode" @click="$emit('mergeRules', selectedForMerge)" :disabled="selectedForMerge.length < 2"
                class="btn-sm btn-merge">合并</button>
        <button v-if="mergeMode" @click="exitMergeMode" class="btn-sm btn-cancel">取消</button>
        <button v-else @click="enterMergeMode" class="btn-sm btn-outline">合并模式</button>
      </div>
    </div>

    <div v-if="domains.length === 0" class="empty-state">暂无规则</div>

    <div v-for="domain in domains" :key="domain.id" class="domain-section">
      <div class="domain-header" @click="toggleDomain(domain.id)">
        <div class="domain-info">
          <span class="domain-name">{{ domain.name }}</span>
          <span class="domain-meta">
            {{ domain.rules.length }} 条规则
            · {{ unreviewedCount(domain) }} 待审核
          </span>
        </div>
        <span :class="['collapse-arrow', { open: expandedDomains.has(domain.id) }]">▶</span>
      </div>

      <div v-if="expandedDomains.has(domain.id)" class="domain-rules">
        <div v-for="rule in domain.rules" :key="rule.id" class="rule-wrapper">
          <label v-if="mergeMode" class="merge-checkbox" @click.stop>
            <input type="checkbox" :value="`${domain.id}_${rule.id}`"
                   :checked="selectedForMerge.includes(`${domain.id}_${rule.id}`)"
                   @change="toggleMergeSelect(`${domain.id}_${rule.id}`)" />
          </label>
          <PolicyRuleCard
            :rule="rule"
            :domain-id="domain.id"
            :review-status="getReview(domain.id, rule.id)?.status || 'pending_review'"
            :selected="selectedRuleKey === `${domain.id}_${rule.id}`"
            @click="onSelectRule(domain.id, rule.id)"
          />
          <div class="rule-actions">
            <button class="btn-icon" title="拆分" @click="onSplit(domain.id, rule.id)">✂️</button>
            <button class="btn-icon" title="删除" @click="onDelete(domain.id, rule.id)">🗑️</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Split Modal -->
    <div v-if="splitModal" class="modal-overlay" @click.self="splitModal = null">
      <div class="modal-content">
        <h3>拆分规则</h3>
        <p class="modal-desc">将规则「{{ splitModal.rule.title }}」拆分为多条规则</p>
        <div v-for="(s, i) in splitTargets" :key="i" class="split-row">
          <div class="split-row-header">
            <span class="split-label">规则 {{ i + 1 }}</span>
            <button v-if="splitTargets.length > 1" @click="removeSplit(i)" class="btn-icon-sm">✕</button>
          </div>
          <div class="split-fields">
            <select v-model="s.type" class="input-dark split-input">
              <option value="limit">limit</option>
              <option value="ratio">ratio</option>
              <option value="approval">approval</option>
              <option value="requirement">requirement</option>
              <option value="restriction">restriction</option>
              <option value="other">other</option>
            </select>
            <input v-model="s.title" placeholder="标题" class="input-dark split-input" />
            <input v-model="s.condition" placeholder="条件" class="input-dark split-input" />
            <input v-model.number="s.value" type="number" placeholder="值" class="input-dark split-input thin" />
            <input v-model="s.unit" placeholder="单位" class="input-dark split-input thin" />
          </div>
          <div class="split-scope">
            <input v-model="s.scope.role" placeholder="职级" class="input-dark split-input" />
            <input v-model="s.scope.region" placeholder="地区" class="input-dark split-input" />
            <input v-model="s.scope.amount_range" placeholder="金额范围" class="input-dark split-input" />
          </div>
        </div>
        <div class="modal-actions">
          <button @click="addSplitTarget" class="btn-sm btn-outline">+ 添加拆分目标</button>
          <div class="modal-right">
            <button @click="splitModal = null" class="btn-sm btn-cancel">取消</button>
            <button @click="confirmSplit" class="btn-sm btn-primary">确认拆分</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import type { PolicyDomain, PolicyRule } from '../api/policy'
import PolicyRuleCard from './PolicyRuleCard.vue'
import { usePolicyReviewStore } from '../stores/policyReview'

const props = defineProps<{
  domains: PolicyDomain[]
  selectedRuleKey: string | null
}>()

const emit = defineEmits<{
  selectRule: [domainId: string, ruleId: string]
  splitRule: [domainId: string, ruleId: string, splits: any[]]
  deleteRule: [domainId: string, ruleId: string]
  mergeRules: [selected: string[]]
}>()

const store = usePolicyReviewStore()

const expandedDomains = ref<Set<string>>(new Set(props.domains.map(d => d.id)))
const mergeMode = ref(false)
const selectedForMerge = ref<string[]>([])
const splitModal = ref<{ domainId: string; rule: PolicyRule } | null>(null)
const splitTargets = reactive<any[]>([])

function toggleDomain(id: string) {
  const next = new Set(expandedDomains.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expandedDomains.value = next
}

function unreviewedCount(domain: PolicyDomain): number {
  return domain.rules.filter(r => {
    const rev = store.getReview(domain.id, r.id)
    return rev?.status === 'pending_review'
  }).length
}

function getReview(domainId: string, ruleId: string) {
  return store.getReview(domainId, ruleId)
}

function onSelectRule(domainId: string, ruleId: string) {
  if (mergeMode.value) return
  emit('selectRule', domainId, ruleId)
}

function enterMergeMode() {
  mergeMode.value = true
  selectedForMerge.value = []
}

function exitMergeMode() {
  mergeMode.value = false
  selectedForMerge.value = []
}

function toggleMergeSelect(key: string) {
  const i = selectedForMerge.value.indexOf(key)
  if (i >= 0) selectedForMerge.value.splice(i, 1)
  else selectedForMerge.value.push(key)
}

function onSplit(domainId: string, ruleId: string) {
  const d = props.domains.find(d => d.id === domainId)
  const r = d?.rules.find(r => r.id === ruleId)
  if (!r) return
  splitModal.value = { domainId, rule: r }
  splitTargets.splice(0, splitTargets.length, {
    type: r.type,
    title: r.title,
    condition: r.condition,
    value: r.value,
    unit: r.unit,
    scope: { ...(r.scope || { role: null, region: null, amount_range: null }) },
  })
}

function addSplitTarget() {
  const src = splitModal.value?.rule
  if (!src) return
  splitTargets.push({
    type: src.type,
    title: src.title,
    condition: '',
    value: src.value,
    unit: src.unit,
    scope: { role: null, region: null, amount_range: null },
  })
}

function removeSplit(i: number) {
  splitTargets.splice(i, 1)
}

function confirmSplit() {
  if (!splitModal.value || splitTargets.length < 2) return
  emit('splitRule', splitModal.value.domainId, splitModal.value.rule.id, [...splitTargets])
  splitModal.value = null
  splitTargets.splice(0, splitTargets.length)
}

function onDelete(domainId: string, ruleId: string) {
  if (confirm('确定删除此规则？')) {
    emit('deleteRule', domainId, ruleId)
  }
}
</script>

<style scoped>
.rule-list-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #14141a;
  border: 1px solid #2a2a35;
  border-radius: 8px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid #2a2a35;
  flex-shrink: 0;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  color: #e0e0e0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.merge-info {
  font-size: 12px;
  color: #facc15;
}

.empty-state {
  color: #666;
  text-align: center;
  padding: 40px;
  font-size: 14px;
}

.domain-section {
  border-bottom: 1px solid #1e1e2a;
}

.domain-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s;
  user-select: none;
}

.domain-header:hover {
  background: rgba(255, 255, 255, 0.03);
}

.domain-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.domain-name {
  font-size: 14px;
  font-weight: 600;
  color: #e0e0e0;
}

.domain-meta {
  font-size: 11px;
  color: #888;
}

.collapse-arrow {
  font-size: 10px;
  color: #666;
  transition: transform 0.2s;
}

.collapse-arrow.open {
  transform: rotate(90deg);
}

.domain-rules {
  padding: 4px 12px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  flex: 1;
}

.rule-wrapper {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  position: relative;
}

.merge-checkbox {
  padding-top: 14px;
  flex-shrink: 0;
}

.merge-checkbox input {
  width: 16px;
  height: 16px;
  accent-color: #6366f1;
  cursor: pointer;
}

.rule-actions {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-top: 8px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
}

.rule-wrapper:hover .rule-actions {
  opacity: 1;
}

.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 2px;
  border-radius: 4px;
  line-height: 1;
}

.btn-icon:hover {
  background: rgba(255, 255, 255, 0.05);
}

.btn-icon-sm {
  background: none;
  border: none;
  cursor: pointer;
  color: #ef4444;
  font-size: 14px;
  padding: 2px 6px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-content {
  background: #1a1a24;
  border: 1px solid #2a2a35;
  border-radius: 12px;
  padding: 24px;
  width: 640px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-content h3 {
  margin: 0 0 4px;
  font-size: 16px;
  color: #e0e0e0;
}

.modal-desc {
  font-size: 13px;
  color: #888;
  margin: 0 0 16px;
}

.split-row {
  background: #14141a;
  border: 1px solid #2a2a35;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 12px;
}

.split-row-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.split-label {
  font-size: 12px;
  font-weight: 600;
  color: #a0a0b0;
}

.split-fields {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.split-scope {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.split-input {
  padding: 6px 10px;
  font-size: 12px;
  border-radius: 4px;
  background: #0f0f14;
  border: 1px solid #2a2a35;
  color: #e0e0e0;
}

.split-input.thin {
  width: 80px;
}

.modal-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}

.modal-right {
  display: flex;
  gap: 8px;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary { background: #6366f1; color: white; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-outline { background: transparent; border: 1px solid #2a2a35; color: #a0a0b0; }
.btn-outline:hover { border-color: #3a3a50; color: #e0e0e0; }
.btn-cancel { background: transparent; color: #888; }
.btn-cancel:hover { color: #ccc; }
.btn-merge { background: #6366f1; color: white; }
.btn-merge:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
