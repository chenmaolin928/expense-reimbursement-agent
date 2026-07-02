<template>
  <div class="view-container">
    <header class="view-header">
      <h2>📊 统计概览</h2>
    </header>

    <section class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon reports">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.total_reports || 0 }}</span>
          <span class="stat-label">总报销单</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon employees">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.total_employees || 0 }}</span>
          <span class="stat-label">员工数</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon amount">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">¥{{ (stats.total_reimbursed || 0).toLocaleString() }}</span>
          <span class="stat-label">已报销总额</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-icon users">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/></svg>
        </div>
        <div class="stat-body">
          <span class="stat-value">{{ stats.total_users || 0 }}</span>
          <span class="stat-label">用户数</span>
        </div>
      </div>
    </section>

    <section class="panel" v-if="stats.by_status">
      <h3>报销单状态分布</h3>
      <div class="status-bar">
        <div v-for="(count, key) in stats.by_status" :key="String(key)"
             :class="['status-seg', String(key)]"
             :style="{ flex: Math.max(Number(count), 1) }"
             :title="`${statusLabels[String(key)] || key}: ${count}`">
          <span v-if="count > 0" class="seg-label">{{ count }}</span>
        </div>
      </div>
      <div class="status-legend">
        <div v-for="(count, key) in stats.by_status" :key="String(key)" class="legend-item" v-show="count > 0">
          <span :class="['legend-dot', String(key)]" /> {{ statusLabels[String(key)] || key }} ({{ count }})
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import api from '../../api'

const stats = ref<any>({})

const statusLabels: Record<string, string> = {
  draft: 'Draft', submitted: 'Submitted', manager_approval: 'Manager Review',
  finance_approval: 'Finance Review', approved: 'Approved', paid: 'Paid', rejected: 'Rejected',
}

onMounted(async () => {
  try { const res = await api.get('/admin/stats'); stats.value = res.data } catch {}
})
</script>

<style scoped>
.view-container { padding: 24px 32px; }
.view-header { margin-bottom: 20px; }
.view-header h2 { font-size: 20px; font-weight: 700; color: #fff; margin: 0; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
@media (max-width: 900px) { .stats-grid { grid-template-columns: repeat(2, 1fr); } }
.stat-card {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 14px; padding: 20px; display: flex; align-items: center; gap: 16px;
}
.stat-icon {
  width: 48px; height: 48px; min-width: 48px;
  border-radius: 12px; display: flex; align-items: center; justify-content: center;
}
.stat-icon svg { width: 22px; height: 22px; }
.stat-icon.reports { background: rgba(99,102,241,0.12); color: #818cf8; }
.stat-icon.employees { background: rgba(52,211,153,0.12); color: #34d399; }
.stat-icon.amount { background: rgba(251,191,36,0.12); color: #fbbf24; }
.stat-icon.users { background: rgba(244,114,182,0.12); color: #f472b6; }
.stat-body { display: flex; flex-direction: column; }
.stat-value { font-size: 26px; font-weight: 700; color: #fff; letter-spacing: -0.5px; }
.stat-label { font-size: 12px; color: rgba(255,255,255,0.35); margin-top: 2px; }

.panel {
  background: #0f0f14; border: 1px solid rgba(255,255,255,0.04);
  border-radius: 14px; padding: 20px;
}
.panel h3 { font-size: 14px; font-weight: 600; color: #fff; margin: 0 0 12px 0; }

.status-bar { display: flex; height: 32px; border-radius: 8px; overflow: hidden; gap: 2px; }
.status-seg { display: flex; align-items: center; justify-content: center; transition: filter 0.2s; min-width: 20px; }
.status-seg:hover { filter: brightness(1.3); }
.status-seg.submitted { background: #6366f1; }
.status-seg.manager_approval { background: #8b5cf6; }
.status-seg.finance_approval { background: #a78bfa; }
.status-seg.approved { background: #34d399; }
.status-seg.paid { background: #10b981; }
.status-seg.rejected { background: #f87171; }
.status-seg.draft { background: rgba(255,255,255,0.08); }
.seg-label { font-size: 11px; font-weight: 600; color: #fff; }
.status-legend { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 10px; }
.legend-item { font-size: 12px; color: rgba(255,255,255,0.4); display: flex; align-items: center; gap: 6px; }
.legend-dot { width: 8px; height: 8px; border-radius: 50%; }
.legend-dot.submitted { background: #6366f1; }
.legend-dot.manager_approval { background: #8b5cf6; }
.legend-dot.finance_approval { background: #a78bfa; }
.legend-dot.approved { background: #34d399; }
.legend-dot.paid { background: #10b981; }
.legend-dot.rejected { background: #f87171; }
.legend-dot.draft { background: rgba(255,255,255,0.2); }
</style>
