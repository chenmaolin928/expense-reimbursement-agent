<template>
  <div :class="['rule-card', { selected, 'status-confirmed': reviewStatus === 'confirmed', 'status-pending': reviewStatus === 'pending_review', 'status-invalid': reviewStatus === 'invalid' }]"
       @click="$emit('click')">
    <div class="card-top">
      <div class="card-left">
        <span class="rule-type-badge" :class="'rule-type-' + rule.type">{{ rule.type }}</span>
        <span class="rule-title">{{ rule.title }}</span>
      </div>
      <div class="card-right">
        <span :class="['status-badge', reviewStatus]">
          {{ statusLabel }}
        </span>
      </div>
    </div>

    <div class="card-body">
      <div v-if="rule.value !== null && rule.value !== undefined" class="detail-row">
        <span class="detail-label">值:</span>
        <span class="detail-value"><strong>{{ rule.value }} {{ rule.unit }}</strong></span>
      </div>
      <div v-if="rule.condition" class="detail-row">
        <span class="detail-label">条件:</span>
        <span class="detail-value">{{ rule.condition }}</span>
      </div>
      <div v-if="rule.scope?.role || rule.scope?.region || rule.scope?.amount_range" class="scope-chips">
        <span v-if="rule.scope.role" class="chip chip-role">{{ rule.scope.role }}</span>
        <span v-if="rule.scope.region" class="chip chip-region">{{ rule.scope.region }}</span>
        <span v-if="rule.scope.amount_range" class="chip chip-amount">{{ rule.scope.amount_range }}</span>
      </div>
    </div>

    <div v-if="rule.raw_text" class="card-raw">
      <span class="raw-label">📎 原文:</span>
      <span class="raw-text">{{ truncate(rule.raw_text, 80) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PolicyRule } from '../api/policy'

const props = defineProps<{
  rule: PolicyRule
  domainId: string
  reviewStatus: string
  selected: boolean
}>()

defineEmits<{
  click: []
}>()

const statusLabel = computed(() => {
  switch (props.reviewStatus) {
    case 'confirmed': return '✔ 已确认'
    case 'invalid': return '❌ 错误'
    default: return '⚠ 待审核'
  }
})

function truncate(s: string, max: number): string {
  return s.length > max ? s.slice(0, max) + '...' : s
}
</script>

<style scoped>
.rule-card {
  background: #1a1a24;
  border: 1px solid #2a2a35;
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.15s;
  position: relative;
}

.rule-card:hover {
  border-color: #3a3a50;
  background: #1e1e2a;
}

.rule-card.selected {
  border-color: #6366f1;
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.3);
  background: #1e1a2e;
}

.rule-card.status-confirmed {
  border-left: 3px solid #22c55e;
}

.rule-card.status-pending {
  border-left: 3px solid #eab308;
}

.rule-card.status-invalid {
  border-left: 3px solid #ef4444;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.card-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.rule-type-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.rule-type-limit { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
.rule-type-ratio { background: rgba(34, 197, 94, 0.2); color: #4ade80; }
.rule-type-approval { background: rgba(234, 179, 8, 0.2); color: #facc15; }
.rule-type-requirement { background: rgba(168, 85, 247, 0.2); color: #c084fc; }
.rule-type-restriction { background: rgba(239, 68, 68, 0.2); color: #f87171; }
.rule-type-other { background: rgba(148, 163, 184, 0.2); color: #94a3b8; }

.rule-title {
  font-size: 13px;
  font-weight: 500;
  color: #e0e0e0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-right {
  flex-shrink: 0;
}

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.status-badge.confirmed { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.status-badge.pending_review { background: rgba(234, 179, 8, 0.15); color: #facc15; }
.status-badge.invalid { background: rgba(239, 68, 68, 0.15); color: #f87171; }

.card-body {
  margin-bottom: 6px;
}

.detail-row {
  font-size: 12px;
  color: #a0a0b0;
  margin: 2px 0;
}

.detail-label {
  margin-right: 4px;
}

.detail-value {
  color: #d0d0e0;
}

.scope-chips {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 6px;
}

.chip {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
}

.chip-role { background: rgba(99, 102, 241, 0.15); color: #818cf8; }
.chip-region { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
.chip-amount { background: rgba(234, 179, 8, 0.15); color: #facc15; }

.card-raw {
  font-size: 11px;
  color: #666;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid #2a2a35;
  line-height: 1.5;
}

.raw-label {
  color: #888;
  margin-right: 4px;
}

.raw-text {
  color: #777;
}
</style>
