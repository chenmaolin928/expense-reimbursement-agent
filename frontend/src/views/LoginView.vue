<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const username = ref('zhangwei')
const password = ref('zhang123')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    const user = await auth.login(username.value, password.value)
    router.push(user.role === 'admin' ? '/admin' : '/chat')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Invalid credentials'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <!-- Decorative background -->
    <div class="bg-orb orb-1" />
    <div class="bg-orb orb-2" />
    <div class="bg-orb orb-3" />

    <div class="login-panel">
      <div class="login-visual">
        <div class="visual-logo">
          <div class="logo-hex" />
        </div>
        <h1>ExpenseFlow</h1>
        <p class="visual-desc">Enterprise AI Agent for intelligent reimbursement automation</p>
        <div class="visual-features">
          <div class="feature-dot" />
          <div class="feature-dot" />
          <div class="feature-dot" />
        </div>
      </div>

      <div class="login-form">
        <div class="form-header">
          <span class="form-badge">AI-Powered</span>
          <h2>Welcome back</h2>
          <p>Sign in to your account</p>
        </div>

        <form @submit.prevent="handleLogin">
          <div class="field">
            <label>Username</label>
            <div class="input-wrap">
              <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="12" cy="8" r="4"/><path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/>
              </svg>
              <input v-model="username" placeholder="Enter username" type="text" />
            </div>
          </div>

          <div class="field">
            <label>Password</label>
            <div class="input-wrap">
              <svg class="input-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
              <input v-model="password" placeholder="Enter password" type="password" />
            </div>
          </div>

          <button type="submit" :disabled="loading" class="btn-login">
            <span v-if="loading" class="spinner" />
            <span v-else>Sign In</span>
          </button>

          <p v-if="error" class="error-msg">{{ error }}</p>
        </form>

        <div class="demo-hints">
          <div class="demo-row">
            <span class="demo-role">Admin</span>
            <code>admin / admin123</code>
          </div>
          <div class="demo-row">
            <span class="demo-role">Employee</span>
            <code>zhangwei / zhang123</code>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #0f0f14;
  position: relative;
  overflow: hidden;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.bg-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  opacity: 0.15;
  pointer-events: none;
}
.orb-1 { width: 600px; height: 600px; background: #6366f1; top: -200px; right: -100px; }
.orb-2 { width: 400px; height: 400px; background: #8b5cf6; bottom: -150px; left: -80px; }
.orb-3 { width: 300px; height: 300px; background: #a78bfa; top: 40%; left: 50%; transform: translate(-50%, -50%); }

.login-panel {
  position: relative;
  z-index: 1;
  display: flex;
  background: rgba(24, 24, 33, 0.85);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 24px;
  overflow: hidden;
  width: 880px;
  max-width: 95vw;
  box-shadow:
    0 4px 6px rgba(0, 0, 0, 0.3),
    0 12px 40px rgba(0, 0, 0, 0.4),
    0 0 0 1px rgba(255, 255, 255, 0.03) inset;
}

.login-visual {
  flex: 0 0 400px;
  background: linear-gradient(160deg, rgba(99, 102, 241, 0.12) 0%, rgba(139, 92, 246, 0.06) 100%);
  padding: 64px 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  border-right: 1px solid rgba(255, 255, 255, 0.04);
}
.visual-logo {
  margin-bottom: 32px;
}
.logo-hex {
  width: 48px; height: 48px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  clip-path: polygon(50% 0%, 100% 25%, 100% 75%, 50% 100%, 0% 75%, 0% 25%);
}
.visual-desc {
  color: rgba(255, 255, 255, 0.4);
  font-size: 14px;
  line-height: 1.6;
  margin-top: 12px;
  max-width: 280px;
}
.visual-features {
  display: flex; gap: 8px; margin-top: auto;
}
.feature-dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
}
.feature-dot:first-child { background: rgba(99, 102, 241, 0.6); }

.login-form {
  flex: 1;
  padding: 64px 48px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

h1 { color: #fff; font-size: 24px; font-weight: 600; letter-spacing: -0.5px; margin: 0; }
h2 { color: #fff; font-size: 22px; font-weight: 600; margin: 0 0 4px; letter-spacing: -0.3px; }

.form-header { margin-bottom: 36px; }
.form-header p { color: rgba(255, 255, 255, 0.4); font-size: 14px; margin: 0; }
.form-badge {
  display: inline-block;
  padding: 3px 10px;
  background: rgba(99, 102, 241, 0.15);
  border: 1px solid rgba(99, 102, 241, 0.25);
  color: #818cf8;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  border-radius: 20px;
  margin-bottom: 16px;
}

.field { margin-bottom: 20px; }
.field label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255, 255, 255, 0.5);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}
.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.input-icon {
  position: absolute;
  left: 14px;
  width: 18px;
  height: 18px;
  color: rgba(255, 255, 255, 0.25);
  pointer-events: none;
}
.input-wrap input {
  width: 100%;
  padding: 12px 14px 12px 42px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  color: #fff;
  font-size: 14px;
  outline: none;
  transition: all 0.2s;
}
.input-wrap input:focus {
  border-color: rgba(99, 102, 241, 0.5);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
  background: rgba(255, 255, 255, 0.05);
}
.input-wrap input::placeholder { color: rgba(255, 255, 255, 0.2); }

.btn-login {
  width: 100%;
  padding: 13px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 8px;
  letter-spacing: -0.2px;
  transition: all 0.2s;
  position: relative;
}
.btn-login:hover:not(:disabled) {
  box-shadow: 0 4px 20px rgba(99, 102, 241, 0.35);
  transform: translateY(-1px);
}
.btn-login:disabled { opacity: 0.6; cursor: default; }

.spinner {
  display: inline-block;
  width: 18px; height: 18px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.error-msg {
  color: #f87171;
  font-size: 13px;
  margin-top: 12px;
  text-align: center;
}

.demo-hints {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
}
.demo-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
  font-size: 12px;
}
.demo-role { color: rgba(255, 255, 255, 0.3); }
.demo-row code {
  color: rgba(255, 255, 255, 0.5);
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 11px;
}

@media (max-width: 768px) {
  .login-panel { flex-direction: column; }
  .login-visual { flex: none; padding: 40px 32px; border-right: none; border-bottom: 1px solid rgba(255,255,255,0.04); }
  .login-form { padding: 40px 32px; }
  .visual-desc { max-width: 100%; }
}
</style>
