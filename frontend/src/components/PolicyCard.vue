<script setup lang="ts">
import { ref, computed } from 'vue'

defineEmits<{
  confirm: []
  correct: [data: any]
  cancel: []
}>()

const props = defineProps<{
  data: {
    verdict: string          // "in_scope" | "out_of_scope"
    summary: string
    policy_refs: Array<{
      source: string
      snippet: string
      kb_name: string
      score: number
    }>
    breakdown: {
      invoice_amount: number
      reimbursement_rate: number
      calculated_amount: number
      cap: number
      final_amount: number
    } | null
    total_results: number
    invoice_fields?: Record<string, any>
  }
  readonly?: boolean  // When true, hides action buttons (consultation mode)
}>()

const expandedRefs = ref<Set<number>>(new Set())
const isInScope = computed(() => props.readonly || props.data.verdict === 'in_scope')
const hasPolicyRefs = computed(() => props.data.policy_refs.length > 0)
const hasBreakdown = computed(() => props.data.breakdown !== null)

function toggleRef(index: number) {
  const s = new Set(expandedRefs.value)
  if (s.has(index)) s.delete(index)
  else s.add(index)
  expandedRefs.value = s
}

function formatAmount(v: number): string {
  return `¥${v.toFixed(2)}`
}

function formatRate(v: number): string {
  return `${Math.round(v * 100)}%`
}
</script>

<template>
  <div :class="['policy-card', isInScope ? 'in-scope' : 'out-of-scope']">
    <!-- Verdict Banner -->
    <div v-if="!readonly" class="verdict-banner">
      <div class="verdict-icon-wrap">
        <svg v-if="isInScope" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
        </svg>
      </div>
      <div class="verdict-text">
        <div class="verdict-title">{{ isInScope ? '在报销范围内' : '不在报销范围内' }}</div>
        <div class="verdict-summary">{{ data.summary }}</div>
      </div>
    </div>

    <!-- Readonly header (consultation / pure policy query) -->
    <div v-else class="readonly-header">
      <div class="readonly-icon-wrap">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
        </svg>
      </div>
      <div class="verdict-text">
        <div class="verdict-title readonly">来源引用</div>
        <div class="verdict-summary">以下为知识库中匹配的政策原文，展开可查看详情</div>
      </div>
    </div>

    <!-- Breakdown (in-scope only) -->
    <div v-if="hasBreakdown && isInScope" class="breakdown-section">
      <div class="breakdown-item">
        <span class="bd-label">发票金额</span>
        <span class="bd-value">{{ formatAmount(data.breakdown!.invoice_amount) }}</span>
      </div>
      <div class="breakdown-divider" />
      <div class="breakdown-item">
        <span class="bd-label">报销比例</span>
        <span class="bd-value rate">{{ formatRate(data.breakdown!.reimbursement_rate) }}</span>
      </div>
      <div class="breakdown-divider" />
      <div class="breakdown-item">
        <span class="bd-label">计算金额</span>
        <span class="bd-value">{{ formatAmount(data.breakdown!.calculated_amount) }}</span>
      </div>
      <div class="breakdown-divider" />
      <div class="breakdown-item">
        <span class="bd-label">单次上限</span>
        <span class="bd-value cap">{{ data.breakdown!.cap ? formatAmount(data.breakdown!.cap) : '无' }}</span>
      </div>
      <div class="breakdown-item total-row">
        <span class="bd-label">预计报销</span>
        <span class="bd-value final">{{ formatAmount(data.breakdown!.final_amount) }}</span>
      </div>
    </div>

    <!-- Policy Refs (expandable) -->
    <div v-if="hasPolicyRefs" class="policy-refs-section">
      <div class="refs-title">政策依据</div>
      <div v-for="(ref, i) in data.policy_refs" :key="i" class="ref-item">
        <button class="ref-toggle" @click="toggleRef(i)">
          <div class="ref-meta">
            <svg class="ref-doc-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
            <span class="ref-source">{{ ref.source }}</span>
            <span class="ref-badge">{{ ref.kb_name }}</span>
          </div>
          <svg :class="['chevron', { open: expandedRefs.has(i) }]" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
        <div v-if="expandedRefs.has(i)" class="ref-snippet">
          {{ ref.snippet }}
        </div>
      </div>
    </div>

    <!-- Actions — only shown when not readonly (consultation mode hides buttons) -->
    <div v-if="!readonly" class="card-actions">
      <template v-if="isInScope">
        <button class="btn btn-correct" @click="$emit('correct', {})">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          修正信息
        </button>
        <button class="btn btn-confirm" @click="$emit('confirm')">
          确认，开始报销
        </button>
      </template>
      <template v-else>
        <button class="btn btn-cancel" @click="$emit('cancel')">取消</button>
        <button class="btn btn-confirm" @click="$emit('correct', data.invoice_fields || {})">
          修正信息，重新查询
        </button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.policy-card {
  background: #18181b;
  border-radius: 14px;
  max-width: 480px;
  overflow: hidden;
  animation: cardIn 0.3s ease-out;
}
.policy-card.in-scope { border: 1px solid rgba(52, 211, 153, 0.3); }
.policy-card.out-of-scope { border: 1px solid rgba(248, 113, 113, 0.3); }

@keyframes cardIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Verdict Banner */
.verdict-banner {
  display: flex; gap: 12px;
  padding: 16px 18px;
}
.in-scope .verdict-banner { background: rgba(52, 211, 153, 0.06); }
.out-of-scope .verdict-banner { background: rgba(248, 113, 113, 0.06); }

.verdict-icon-wrap { width: 28px; height: 28px; flex-shrink: 0; }
.verdict-icon-wrap svg { width: 28px; height: 28px; }
.in-scope .verdict-icon-wrap svg { color: #34d399; }
.out-of-scope .verdict-icon-wrap svg { color: #f87171; }

.verdict-text { display: flex; flex-direction: column; gap: 4px; }
.verdict-title { font-size: 15px; font-weight: 600; }
.in-scope .verdict-title { color: #34d399; }
.out-of-scope .verdict-title { color: #f87171; }
.verdict-title.readonly { color: #818cf8; }
.verdict-summary { font-size: 13px; color: rgba(255, 255, 255, 0.55); line-height: 1.5; }

/* Readonly header (consultation mode) */
.readonly-header {
  display: flex; gap: 12px;
  padding: 16px 18px;
  background: rgba(99, 102, 241, 0.06);
  border-bottom: 1px solid rgba(99, 102, 241, 0.08);
}
.readonly-icon-wrap { width: 28px; height: 28px; flex-shrink: 0; }
.readonly-icon-wrap svg { width: 28px; height: 28px; color: #818cf8; }

/* Breakdown */
.breakdown-section {
  padding: 14px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  background: rgba(255, 255, 255, 0.01);
}
.breakdown-item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 0;
}
.bd-label { font-size: 13px; color: rgba(255, 255, 255, 0.45); }
.bd-value { font-size: 14px; font-weight: 600; color: #e4e4e7; }
.bd-value.rate { color: #818cf8; }
.bd-value.cap { color: rgba(255, 255, 255, 0.5); }
.bd-value.final { color: #34d399; font-size: 16px; }
.breakdown-divider {
  height: 1px; background: rgba(255, 255, 255, 0.03); margin: 2px 0;
}
.total-row {
  margin-top: 6px; padding-top: 8px;
  border-top: 1px solid rgba(52, 211, 153, 0.15);
}

/* Policy Refs */
.policy-refs-section {
  padding: 14px 18px; border-top: 1px solid rgba(255, 255, 255, 0.04);
}
.refs-title {
  font-size: 11px; color: rgba(255, 255, 255, 0.3);
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
}
.ref-item {
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 10px; margin-bottom: 6px;
}
.ref-toggle {
  width: 100%; display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px; background: none; border: none;
  color: rgba(255, 255, 255, 0.6); cursor: pointer; font-size: 13px;
  transition: background 0.15s; text-align: left;
}
.ref-toggle:hover { background: rgba(255, 255, 255, 0.02); }
.ref-meta { display: flex; align-items: center; gap: 8px; flex: 1; min-width: 0; }
.ref-doc-icon { width: 16px; height: 16px; color: rgba(255, 255, 255, 0.25); flex-shrink: 0; }
.ref-source { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ref-badge {
  font-size: 10px; padding: 1px 6px; background: rgba(99, 102, 241, 0.12);
  color: #818cf8; border-radius: 8px; flex-shrink: 0;
}
.chevron {
  width: 16px; height: 16px; color: rgba(255, 255, 255, 0.25); flex-shrink: 0;
  transition: transform 0.2s;
}
.chevron.open { transform: rotate(180deg); }
.ref-snippet {
  padding: 0 12px 12px 36px;
  font-size: 13px; color: rgba(255, 255, 255, 0.5); line-height: 1.7;
  white-space: pre-wrap; word-break: break-word;
}

/* Card Actions */
.card-actions {
  display: flex; gap: 8px;
  padding: 14px 18px; border-top: 1px solid rgba(255, 255, 255, 0.04);
  background: rgba(255, 255, 255, 0.01);
}
.btn {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 9px 16px; border-radius: 10px; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all 0.15s; border: 1px solid transparent;
}
.btn svg { width: 15px; height: 15px; }
.btn-correct {
  background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.6);
}
.btn-correct:hover { background: rgba(255, 255, 255, 0.08); color: #e4e4e7; }
.btn-cancel {
  background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.4);
}
.btn-cancel:hover { background: rgba(255, 255, 255, 0.08); color: rgba(255, 255, 255, 0.6); }
.btn-confirm {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border: none;
}
.btn-confirm:hover { box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35); }
</style>
