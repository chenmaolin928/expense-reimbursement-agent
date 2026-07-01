<script setup lang="ts">
import { ref, reactive } from 'vue'

const emit = defineEmits<{
  submit: [fields: Record<string, string | number>]
  cancel: []
}>()

const props = defineProps<{
  data: {
    title: string
    fields: Array<{
      field: string
      label: string
      type: 'text' | 'number' | 'select'
      required: boolean
      options?: Array<{ value: string; label: string }>
    }>
    hint: string
    invoice_path?: string
  }
}>()

const form = reactive<Record<string, string | number>>({})
const submitting = ref(false)

// Initialize form values
props.data.fields.forEach((f) => {
  form[f.field] = f.type === 'number' ? 0 : ''
})

function handleSubmit() {
  submitting.value = true
  emit('submit', { ...form })
}

function handleCancel() {
  emit('cancel')
}
</script>

<template>
  <div class="supplement-form-card">
    <!-- Header -->
    <div class="form-header">
      <div class="header-left">
        <svg class="header-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
          <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
        <span class="header-title">{{ data.title || '请补充信息' }}</span>
      </div>
      <span class="header-badge">本地处理</span>
    </div>

    <!-- Security notice -->
    <div class="security-notice">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="notice-icon">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
      </svg>
      <span>{{ data.hint || '此信息仅在本地处理，不会发送至云端' }}</span>
    </div>

    <!-- Form fields -->
    <div class="form-body">
      <div v-for="f in data.fields" :key="f.field" class="form-group">
        <label :for="'sf-' + f.field" class="form-label">
          {{ f.label }}
          <span v-if="f.required" class="required">*</span>
        </label>

        <select
          v-if="f.type === 'select'"
          :id="'sf-' + f.field"
          v-model="form[f.field]"
          class="form-input form-select"
        >
          <option value="" disabled>请选择...</option>
          <option v-for="opt in f.options" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>

        <input
          v-else
          :id="'sf-' + f.field"
          v-model="form[f.field]"
          :type="f.type"
          class="form-input"
          :placeholder="'请输入' + f.label"
        />
      </div>
    </div>

    <!-- Actions -->
    <div class="form-actions">
      <button class="btn btn-cancel" @click="handleCancel">
        取消
      </button>
      <button class="btn btn-submit" @click="handleSubmit" :disabled="submitting">
        <svg v-if="submitting" class="spinner" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-dasharray="31.4 31.4"/>
        </svg>
        提交
      </button>
    </div>
  </div>
</template>

<style scoped>
.supplement-form-card {
  background: #18181b;
  border: 1px solid rgba(52, 211, 153, 0.25);
  border-radius: 14px;
  max-width: 440px;
  overflow: hidden;
  animation: cardIn 0.3s ease-out;
}

@keyframes cardIn {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Header */
.form-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px;
  background: rgba(52, 211, 153, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.header-left { display: flex; align-items: center; gap: 10px; }
.header-icon { width: 20px; height: 20px; color: #34d399; flex-shrink: 0; }
.header-title { font-size: 14px; font-weight: 600; color: #e4e4e7; }
.header-badge {
  font-size: 10px; padding: 3px 10px;
  background: rgba(52, 211, 153, 0.12); color: #34d399;
  border-radius: 10px; font-weight: 500;
}

/* Security notice */
.security-notice {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 18px;
  background: rgba(52, 211, 153, 0.03);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 12px; color: rgba(255, 255, 255, 0.45);
}
.notice-icon { width: 14px; height: 14px; color: #34d399; flex-shrink: 0; }

/* Form body */
.form-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 12px; }
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-label {
  font-size: 12px; color: rgba(255, 255, 255, 0.55); font-weight: 500;
}
.required { color: #f87171; margin-left: 2px; }
.form-input {
  width: 100%; padding: 9px 12px;
  background: #0f0f14;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  color: #e4e4e7; font-size: 14px; font-family: inherit;
  outline: none; transition: border-color 0.15s;
  box-sizing: border-box;
}
.form-input:focus { border-color: rgba(52, 211, 153, 0.4); }
.form-input::placeholder { color: rgba(255, 255, 255, 0.15); }
.form-select {
  appearance: none; cursor: pointer;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.3)' stroke-width='2'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 12px center;
}

/* Actions */
.form-actions {
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
.btn-cancel {
  background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.5);
}
.btn-cancel:hover { background: rgba(255, 255, 255, 0.08); color: #e4e4e7; }
.btn-submit {
  background: linear-gradient(135deg, #34d399, #10b981);
  color: #fff; border: none;
}
.btn-submit:hover:not(:disabled) { box-shadow: 0 4px 16px rgba(52, 211, 153, 0.35); }
.btn-submit:disabled { opacity: 0.3; cursor: default; }
.spinner {
  width: 15px; height: 15px; animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
