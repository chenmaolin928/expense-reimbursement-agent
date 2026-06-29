<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const username = ref('zhangwei')
const password = ref('zhang123')
const error = ref('')

async function handleLogin() {
  error.value = ''
  try {
    const user = await auth.login(username.value, password.value)
    if (user.role === 'admin') {
      router.push('/admin')
    } else {
      router.push('/chat')
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Login failed'
  }
}
</script>

<template>
  <div class="login-container">
    <div class="login-card">
      <h1>Expense Reimbursement AI</h1>
      <p class="subtitle">Enterprise AI Agent</p>
      <form @submit.prevent="handleLogin">
        <input v-model="username" placeholder="Username" type="text" />
        <input v-model="password" placeholder="Password" type="password" />
        <button type="submit">Login</button>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
      <div class="hint">
        <p>Demo: zhangwei / zhang123 (employee)</p>
        <p>Demo: admin / admin123 (admin)</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.login-container {
  display: flex; align-items: center; justify-content: center;
  min-height: 100vh; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  background: #fff; border-radius: 12px; padding: 40px; width: 380px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15); text-align: center;
}
.login-card h1 { font-size: 22px; color: #1a1a2e; margin-bottom: 4px; }
.subtitle { color: #888; font-size: 14px; margin-bottom: 28px; }
input {
  width: 100%; padding: 12px 16px; margin-bottom: 14px;
  border: 1px solid #ddd; border-radius: 8px; font-size: 15px;
}
input:focus { outline: none; border-color: #667eea; }
button {
  width: 100%; padding: 12px; background: #667eea; color: #fff;
  border: none; border-radius: 8px; font-size: 16px; cursor: pointer;
}
button:hover { background: #5a6fd6; }
.error { color: #e74c3c; margin-top: 10px; font-size: 14px; }
.hint { margin-top: 24px; font-size: 12px; color: #bbb; }
.hint p { margin-bottom: 4px; }
</style>
