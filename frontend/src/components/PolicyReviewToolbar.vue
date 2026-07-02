<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <span class="version-label">{{ policyName }} v{{ versionNumber }}</span>
      <span v-if="subStatus" class="sub-status">· {{ subStatus }}</span>
    </div>

    <div class="toolbar-center">
      <span class="progress-text">审核进度</span>
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: progress + '%' }"></div>
      </div>
      <span class="progress-count">{{ reviewedCount }}/{{ totalCount }}</span>
    </div>

    <div class="toolbar-right">
      <span v-if="dirty" class="unsaved-badge">未保存</span>
      <span v-else class="saved-badge">已保存</span>
      <button @click="$emit('saveAll')" :disabled="saving || !dirty" class="btn-primary btn-sm">
        {{ saving ? '保存中...' : '保存全部' }}
      </button>
      <button @click="$emit('normalize')" :disabled="saving || dirty" class="btn-secondary btn-sm">
        规范化
      </button>
      <button @click="$emit('exit')" class="btn-ghost btn-sm">← 返回</button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  policyName: string
  versionNumber: number
  subStatus: string
  dirty: boolean
  saving: boolean
  progress: number
  reviewedCount: number
  totalCount: number
}>()

defineEmits<{
  saveAll: []
  normalize: []
  exit: []
}>()
</script>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #14141a;
  border: 1px solid #2a2a35;
  border-radius: 8px;
  gap: 16px;
  flex-shrink: 0;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.version-label {
  font-size: 13px;
  font-weight: 600;
  color: #e0e0e0;
  white-space: nowrap;
}

.sub-status {
  font-size: 12px;
  color: #888;
}

.toolbar-center {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  justify-content: center;
}

.progress-text {
  font-size: 11px;
  color: #888;
  white-space: nowrap;
}

.progress-bar {
  width: 120px;
  height: 6px;
  background: #2a2a35;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #22c55e);
  border-radius: 3px;
  transition: width 0.3s;
}

.progress-count {
  font-size: 11px;
  color: #a0a0b0;
  white-space: nowrap;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.unsaved-badge {
  font-size: 11px;
  color: #eab308;
  padding: 2px 8px;
  background: rgba(234,179,8,0.1);
  border-radius: 10px;
}

.saved-badge {
  font-size: 11px;
  color: #22c55e;
  padding: 2px 8px;
  background: rgba(34,197,94,0.1);
  border-radius: 10px;
}

.btn-sm {
  padding: 6px 12px;
  font-size: 12px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  font-weight: 500;
  white-space: nowrap;
}

.btn-primary { background: #6366f1; color: white; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-secondary { background: transparent; border: 1px solid #2a2a35; color: #a0a0b0; }
.btn-secondary:hover { border-color: #3a3a50; color: #e0e0e0; }
.btn-secondary:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-ghost { background: transparent; color: #888; }
.btn-ghost:hover { color: #ccc; }
</style>
