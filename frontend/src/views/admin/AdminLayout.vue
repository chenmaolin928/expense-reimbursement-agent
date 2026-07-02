<template>
  <div class="admin-shell">
    <aside class="sidebar">
      <div class="brand">ExpenseFlow Admin</div>
      <nav>
        <router-link to="/admin/knowledge">📚 知识库</router-link>
        <router-link to="/admin/policy">📋 政策中心</router-link>
        <router-link to="/admin/analytics">📊 统计</router-link>
        <router-link v-if="showDebug" to="/admin/debug">🔧 调试</router-link>
      </nav>
      <div class="sidebar-footer">
        <router-link to="/chat">← 返回聊天</router-link>
        <a href="#" @click.prevent="handleLogout">退出登录</a>
      </div>
    </aside>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const showDebug = computed(() => {
  return import.meta.env.DEV || new URLSearchParams(window.location.search).has('dev')
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<style scoped>
* { box-sizing: border-box; margin: 0; padding: 0; }

.admin-shell {
  display: flex; height: 100vh;
  background: #0a0a0e;
  color: #e4e4e7;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.sidebar {
  width: 220px; min-width: 220px;
  background: #0f0f14;
  border-right: 1px solid rgba(255,255,255,0.04);
  display: flex; flex-direction: column;
  padding: 1.5rem 1rem;
}

.sidebar .brand {
  font-size: 14px; font-weight: 700; color: #fff;
  margin-bottom: 2rem; padding: 0 0.5rem;
  letter-spacing: -0.2px;
}

.sidebar nav { flex: 1; display: flex; flex-direction: column; gap: 2px; }

.sidebar nav a {
  color: rgba(255,255,255,0.4);
  text-decoration: none;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s;
}
.sidebar nav a:hover {
  background: rgba(255,255,255,0.03);
  color: rgba(255,255,255,0.7);
}
.sidebar nav a.router-link-exact-active {
  background: rgba(99,102,241,0.1);
  color: #a5b4fc;
  font-weight: 600;
}

.sidebar-footer {
  border-top: 1px solid rgba(255,255,255,0.04);
  padding-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.sidebar-footer a {
  color: rgba(255,255,255,0.25);
  text-decoration: none;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  transition: all 0.15s;
}
.sidebar-footer a:hover {
  color: rgba(255,255,255,0.5);
  background: rgba(255,255,255,0.02);
}

.content {
  flex: 1;
  overflow-y: auto;
  background: #0a0a0e;
}
</style>
