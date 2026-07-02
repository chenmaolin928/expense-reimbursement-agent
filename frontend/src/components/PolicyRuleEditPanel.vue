<template>
  <div class="edit-panel">
    <div class="panel-header">
      <h3>✏️ 规则编辑</h3>
      <button v-if="rule" @click="$emit('close')" class="btn-close">✕</button>
    </div>

    <div v-if="!rule" class="empty-state">
      选择一条规则开始编辑
    </div>

    <div v-else class="edit-scroll">
      <!-- Type -->
      <label class="field-group">
        <span class="field-label">类型</span>
        <select v-model="localRule.type" @change="onFieldChange('type', localRule.type)" class="input-dark">
          <option value="limit">limit</option>
          <option value="ratio">ratio</option>
          <option value="approval">approval</option>
          <option value="requirement">requirement</option>
          <option value="restriction">restriction</option>
          <option value="other">other</option>
        </select>
      </label>

      <!-- Title -->
      <label class="field-group">
        <span class="field-label">标题</span>
        <input v-model="localRule.title" @change="onFieldChange('title', localRule.title)" class="input-dark" />
      </label>

      <!-- Scope -->
      <div class="field-group">
        <span class="field-label">适用范围</span>
        <div class="scope-fields">
          <input v-model="localScope.role" @change="onScopeChange('role', localScope.role)" placeholder="职级" class="input-dark scope-input" />
          <input v-model="localScope.region" @change="onScopeChange('region', localScope.region)" placeholder="地区" class="input-dark scope-input" />
          <input v-model="localScope.amount_range" @change="onScopeChange('amount_range', localScope.amount_range)" placeholder="金额范围" class="input-dark scope-input" />
        </div>
      </div>

      <!-- Condition -->
      <label class="field-group">
        <span class="field-label">条件</span>
        <input v-model="localRule.condition" @change="onFieldChange('condition', localRule.condition)" class="input-dark" />
      </label>

      <!-- Value + Unit -->
      <div class="field-row">
        <label class="field-group flex-1">
          <span class="field-label">值</span>
          <input v-model.number="localRule.value" type="number" @change="onFieldChange('value', localRule.value)" class="input-dark" />
        </label>
        <label class="field-group unit-field">
          <span class="field-label">单位</span>
          <select v-model="localRule.unit" @change="onFieldChange('unit', localRule.unit)" class="input-dark">
            <option value="yuan">yuan</option>
            <option value="percent">percent</option>
            <option value="days">days</option>
            <option value="times">times</option>
            <option value="">无</option>
          </select>
        </label>
      </div>

      <!-- Raw text (read-only) -->
      <div class="field-group">
        <span class="field-label">原文（只读）</span>
        <textarea :value="localRule.raw_text" class="input-dark raw-textarea" readonly rows="3"></textarea>
      </div>

      <!-- Review Status -->
      <div class="field-group">
        <span class="field-label">审核状态</span>
        <div class="status-toggle">
          <button :class="['status-btn', { active: localStatus === 'confirmed' }]"
                  @click="onStatusChange('confirmed')">
            ✔ 已确认
          </button>
          <button :class="['status-btn', { active: localStatus === 'pending_review' }]"
                  @click="onStatusChange('pending_review')">
            ⚠ 待审核
          </button>
          <button :class="['status-btn', { active: localStatus === 'invalid' }]"
                  @click="onStatusChange('invalid')">
            ❌ 错误
          </button>
        </div>
      </div>

      <!-- Review Notes -->
      <label class="field-group">
        <span class="field-label">审核备注</span>
        <textarea v-model="localNotes" @change="onNotesChange" class="input-dark raw-textarea" rows="2" placeholder="可选的审核说明"></textarea>
      </label>

      <!-- Actions -->
      <div class="edit-actions">
        <button @click="onSave" :disabled="!store.dirty" class="btn-primary btn-save">
          保存
        </button>
      </div>

      <!-- Danger Zone -->
      <div class="danger-zone">
        <button @click="onDelete" class="btn-danger">🗑️ 删除此规则</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import type { PolicyRule, PolicyRuleScope } from '../api/policy'
import { usePolicyReviewStore } from '../stores/policyReview'

const props = defineProps<{
  rule: PolicyRule | null
  domainId: string | null
  review: { status: string; notes?: string } | null
}>()

const emit = defineEmits<{
  close: []
  save: []
  delete: []
}>()

const store = usePolicyReviewStore()

const localRule = ref<{ type: string; title: string; condition: string; value: number | null; unit: string; raw_text: string }>({
  type: 'other', title: '', condition: '', value: null, unit: '', raw_text: '' })
const localScope = ref<{ role: string; region: string; amount_range: string }>({ role: '', region: '', amount_range: '' })
const localStatus = ref('pending_review')
const localNotes = ref('')

watch(() => props.rule, (r) => {
  if (r) {
    localRule.value = { type: r.type, title: r.title, condition: r.condition, value: r.value, unit: r.unit, raw_text: r.raw_text }
    localScope.value = {
      role: r.scope?.role || '',
      region: r.scope?.region || '',
      amount_range: r.scope?.amount_range || '',
    }
  }
  if (props.review) {
    localStatus.value = props.review.status || 'pending_review'
    localNotes.value = props.review.notes || ''
  }
}, { immediate: true })

function onFieldChange(field: string, value: any) {
  if (!props.domainId || !props.rule) return
  store.updateRuleField(props.domainId, props.rule.id, field, value)
}

function onScopeChange(field: string, value: string | null) {
  if (!props.domainId || !props.rule) return
  store.updateRuleScope(props.domainId, props.rule.id, field, value || null)
}

function onStatusChange(status: string) {
  localStatus.value = status
  if (!props.domainId || !props.rule) return
  store.setReviewStatus(props.domainId, props.rule.id, status, localNotes.value)
}

function onNotesChange() {
  if (!props.domainId || !props.rule) return
  store.setReviewStatus(props.domainId, props.rule.id, localStatus.value, localNotes.value)
}

function onSave() {
  emit('save')
}

function onDelete() {
  if (confirm('确定删除此规则？删除后不可撤销。')) {
    emit('delete')
  }
}
</script>

<style scoped>
.edit-panel {
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

.btn-close {
  background: none;
  border: none;
  color: #888;
  cursor: pointer;
  font-size: 16px;
  padding: 4px;
  border-radius: 4px;
}

.btn-close:hover {
  color: #e0e0e0;
  background: rgba(255,255,255,0.05);
}

.empty-state {
  color: #666;
  text-align: center;
  padding: 60px 20px;
  font-size: 14px;
}

.edit-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  font-size: 12px;
  font-weight: 500;
  color: #888;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.input-dark {
  padding: 8px 12px;
  background: #0f0f14;
  border: 1px solid #2a2a35;
  border-radius: 6px;
  color: #e0e0e0;
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s;
}

.input-dark:focus {
  border-color: #6366f1;
}

select.input-dark {
  cursor: pointer;
}

.scope-fields {
  display: flex;
  gap: 8px;
}

.scope-input {
  flex: 1;
}

.field-row {
  display: flex;
  gap: 12px;
}

.flex-1 {
  flex: 1;
}

.unit-field {
  width: 120px;
}

.raw-textarea {
  resize: vertical;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.5;
  color: #888;
}

.status-toggle {
  display: flex;
  gap: 8px;
}

.status-btn {
  flex: 1;
  padding: 8px 4px;
  border: 1px solid #2a2a35;
  border-radius: 6px;
  background: transparent;
  color: #888;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.status-btn.active {
  border-color: currentColor;
}

.status-btn:first-child.active { color: #22c55e; border-color: #22c55e; background: rgba(34,197,94,0.1); }
.status-btn:nth-child(2).active { color: #eab308; border-color: #eab308; background: rgba(234,179,8,0.1); }
.status-btn:last-child.active { color: #ef4444; border-color: #ef4444; background: rgba(239,68,68,0.1); }

.status-btn:hover {
  color: #e0e0e0;
}

.edit-actions {
  padding-top: 8px;
}

.btn-primary {
  padding: 8px 20px;
  background: #6366f1;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-save {
  width: 100%;
}

.danger-zone {
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid #2a2a35;
}

.btn-danger {
  width: 100%;
  padding: 8px;
  background: transparent;
  border: 1px solid #ef4444;
  border-radius: 6px;
  color: #ef4444;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-danger:hover {
  background: rgba(239,68,68,0.1);
}
</style>
