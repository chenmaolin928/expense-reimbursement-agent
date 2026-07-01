<script setup lang="ts">
import { ref, computed } from 'vue'

const emit = defineEmits<{
  confirm: [data: any]
  correct: [data: any]
  cancel: []
}>()

const props = defineProps<{
  data: {
    fields: Record<string, { label: string; value: string | number }>
    desensitization: Record<string, { status: string; token: string }>
    invoice_path: string
  }
  readonly?: boolean  // When true, hides action buttons
}>()

const showDetail = ref(false)

function getFileUrl(filePath: string): string {
  const name = filePath.split('/').pop() || filePath.split('\\').pop() || filePath
  return `/api/v1/files/${name}`
}

function isImagePath(filePath: string): boolean {
  const ext = (filePath.split('.').pop() || '').toLowerCase()
  return ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].includes(ext)
}

function openImage(url: string) {
  window.open(url, '_blank')
}

interface FieldEntry { key: string; label: string; value: string | number }

const invoiceFields = computed<FieldEntry[]>(() => {
  return Object.entries(props.data.fields).map(([key, v]) => ({
    key,
    label: v.label,
    value: v.value,
  }))
})

const desensitizationEntries = computed(() => {
  return Object.entries(props.data.desensitization || {})
})

const hasDesensitization = computed(() => desensitizationEntries.value.length > 0)

function handleConfirm() {
  emit('confirm', { ...props.data })
}

function handleCorrect() {
  emit('correct', { ...props.data })
}
</script>

<template>
  <div class="invoice-card">
    <!-- Header -->
    <div class="card-header">
      <div class="header-left">
        <svg class="header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
        <span class="header-title">发票扫描结果</span>
      </div>
      <div class="header-right">
        <img
          v-if="data.invoice_path && isImagePath(data.invoice_path)"
          :src="getFileUrl(data.invoice_path)"
          class="invoice-thumb"
          @click="openImage(getFileUrl(data.invoice_path))"
        />
        <button class="detail-toggle" @click="showDetail = !showDetail">
          {{ showDetail ? '收起' : '查看详情' }}
        </button>
      </div>
    </div>

    <!-- Field Table -->
    <div class="card-body">
      <div class="field-grid">
        <div v-for="f in invoiceFields" :key="f.key" class="field-row">
          <span class="field-label">{{ f.label }}</span>
          <span class="field-value">{{ f.value }}</span>
        </div>
      </div>

      <!-- Desensitization badges -->
      <div v-if="hasDesensitization && showDetail" class="desensitization-section">
        <div class="desen-title">脱敏保护字段</div>
        <div class="desen-list">
          <div v-for="[entity, info] in desensitizationEntries" :key="entity" class="desen-item">
            <svg class="desen-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
            </svg>
            <span class="desen-entity">{{ entity }}</span>
            <span class="desen-token">{{ info.token }}</span>
            <span class="desen-status">{{ info.status === 'hidden' ? '已脱敏' : info.status }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Actions — only shown when not readonly -->
    <div v-if="!readonly" class="card-actions">
      <button class="btn btn-correct" @click="handleCorrect">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
          <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
        </svg>
        修正信息
      </button>
      <button class="btn btn-confirm" @click="handleConfirm">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <polyline points="20 6 9 17 4 12"/>
        </svg>
        确认无误，查询政策
      </button>
    </div>
  </div>
</template>

<style scoped>
.invoice-card {
  background: #18181b;
  border: 1px solid rgba(99, 102, 241, 0.25);
  border-radius: 14px;
  max-width: 480px;
  overflow: hidden;
  animation: cardIn 0.3s ease-out;
}

@keyframes cardIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Header */
.card-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px;
  background: rgba(99, 102, 241, 0.08);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-right { display: flex; align-items: center; gap: 8px; }
.header-icon { width: 20px; height: 20px; color: #818cf8; flex-shrink: 0; }
.header-title { font-size: 14px; font-weight: 600; color: #e4e4e7; }
.invoice-thumb {
  width: 48px; height: 34px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.12);
  cursor: pointer;
  transition: transform 0.15s;
}
.invoice-thumb:hover { transform: scale(1.1); }
.detail-toggle {
  background: none; border: none; color: #818cf8; font-size: 12px;
  cursor: pointer; padding: 4px 8px; border-radius: 6px;
  transition: background 0.15s;
}
.detail-toggle:hover { background: rgba(99, 102, 241, 0.12); }

/* Body */
.card-body { padding: 16px 18px; }

.field-grid {
  display: grid; grid-template-columns: 1fr 1fr; gap: 2px;
}
.field-row {
  display: flex; flex-direction: column; gap: 2px;
  padding: 10px 12px; background: rgba(255, 255, 255, 0.015);
  border-radius: 8px;
}
.field-label {
  font-size: 11px; color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.field-value {
  font-size: 15px; font-weight: 600; color: #e4e4e7;
}

/* Desensitization */
.desensitization-section {
  margin-top: 14px; padding-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}
.desen-title {
  font-size: 11px; color: rgba(255, 255, 255, 0.3);
  text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
}
.desen-list { display: flex; flex-direction: column; gap: 6px; }
.desen-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 10px; background: rgba(251, 191, 36, 0.05);
  border: 1px solid rgba(251, 191, 36, 0.1); border-radius: 8px;
  font-size: 12px;
}
.desen-icon { width: 14px; height: 14px; color: #fbbf24; flex-shrink: 0; }
.desen-entity { color: rgba(255, 255, 255, 0.4); min-width: 80px; }
.desen-token { color: #fbbf24; font-family: monospace; font-size: 11px; }
.desen-status {
  margin-left: auto; font-size: 10px; padding: 2px 8px;
  background: rgba(251, 191, 36, 0.12); color: #fbbf24; border-radius: 10px;
}

/* Actions */
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
.btn-confirm {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; border: none;
}
.btn-confirm:hover { box-shadow: 0 4px 16px rgba(99, 102, 241, 0.35); }
</style>
