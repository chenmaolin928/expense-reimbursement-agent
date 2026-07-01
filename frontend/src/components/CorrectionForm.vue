<script setup lang="ts">
import { ref, reactive, watch } from 'vue'

const emit = defineEmits<{
  submit: [fields: Record<string, string | number>]
  cancel: []
}>()

const props = defineProps<{
  fields: Record<string, { label: string; value: string | number }>
  invoicePath: string
}>()

const form = reactive<Record<string, string | number>>({})

// Init from props
watch(
  () => props.fields,
  (f) => {
    for (const [key, v] of Object.entries(f)) {
      form[key] = v.value
    }
  },
  { immediate: true, deep: true },
)

function handleSubmit() {
  // Only emit fields that changed
  const changed: Record<string, string | number> = {}
  for (const [key, v] of Object.entries(form)) {
    const original = props.fields[key]
    if (original && v !== original.value) {
      changed[key] = v
    }
  }
  emit('submit', changed)
}
</script>

<template>
  <div class="correction-form">
    <div class="form-header">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="form-icon">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
      </svg>
      <span>修正发票信息</span>
    </div>

    <div class="form-body">
      <div v-for="(v, key) in props.fields" :key="key" class="form-field">
        <label :for="'field-' + key">{{ v.label }}</label>
        <template v-if="key === 'category'">
          <select :id="'field-' + key" v-model="form[key]">
            <option value="meals">餐饮</option>
            <option value="travel">差旅</option>
            <option value="transportation">交通</option>
            <option value="office_supplies">办公用品</option>
            <option value="entertainment">商务招待</option>
            <option value="other">其他</option>
          </select>
        </template>
        <template v-else-if="key === 'date'">
          <input :id="'field-' + key" type="date" v-model="form[key]" />
        </template>
        <template v-else-if="key === 'amount'">
          <input
            :id="'field-' + key"
            type="number"
            step="0.01"
            v-model.number="form[key]"
            placeholder="输入金额"
          />
        </template>
        <template v-else>
          <input
            :id="'field-' + key"
            type="text"
            v-model="form[key]"
            placeholder="输入值"
          />
        </template>
      </div>
    </div>

    <div class="form-actions">
      <button class="btn btn-cancel" @click="$emit('cancel')">取消</button>
      <button class="btn btn-submit" @click="handleSubmit">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="btn-icon">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        重新搜索政策
      </button>
    </div>
  </div>
</template>

<style scoped>
.correction-form {
  background: #18181b;
  border: 1px solid rgba(251, 191, 36, 0.25);
  border-radius: 14px;
  max-width: 480px;
  overflow: hidden;
  animation: cardIn 0.2s ease-out;
}

@keyframes cardIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.form-header {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 18px;
  background: rgba(251, 191, 36, 0.06);
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  font-size: 13px; font-weight: 600; color: #fbbf24;
}
.form-icon { width: 16px; height: 16px; }

.form-body {
  padding: 14px 18px; display: flex; flex-direction: column; gap: 10px;
}
.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-field label {
  font-size: 11px; color: rgba(255, 255, 255, 0.35);
  text-transform: uppercase; letter-spacing: 0.5px;
}
.form-field input, .form-field select {
  padding: 8px 12px; background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px; color: #e4e4e7; font-size: 13px;
  font-family: inherit; outline: none; transition: border-color 0.15s;
}
.form-field input:focus, .form-field select:focus {
  border-color: rgba(99, 102, 241, 0.4);
}
.form-field select { cursor: pointer; }
.form-field select option { background: #18181b; color: #e4e4e7; }

.form-actions {
  display: flex; gap: 8px; padding: 12px 18px;
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  background: rgba(255, 255, 255, 0.01);
}
.btn {
  flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px;
  padding: 9px 16px; border-radius: 10px; font-size: 13px; font-weight: 500;
  cursor: pointer; transition: all 0.15s; border: 1px solid transparent;
}
.btn-icon { width: 14px; height: 14px; }
.btn-cancel {
  background: rgba(255, 255, 255, 0.04); border-color: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.4);
}
.btn-cancel:hover { background: rgba(255, 255, 255, 0.08); color: rgba(255, 255, 255, 0.6); }
.btn-submit {
  background: rgba(251, 191, 36, 0.12); border-color: rgba(251, 191, 36, 0.25);
  color: #fbbf24;
}
.btn-submit:hover { background: rgba(251, 191, 36, 0.2); }
</style>
