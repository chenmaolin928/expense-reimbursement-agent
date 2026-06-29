import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<any>(null)
  const role = ref('')

  async function login(username: string, password: string) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.data.token
    role.value = res.data.role
    user.value = res.data
    localStorage.setItem('token', token.value)
    return res.data
  }

  function logout() {
    token.value = ''
    role.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  return { token, user, role, login, logout }
})
