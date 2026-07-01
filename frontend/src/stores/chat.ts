import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api'

export interface Session {
  id: string
  title: string
  created_at: string
  message_count: number
}

export interface ChatMessage {
  id: number
  session_id: string
  role: string
  content: string | null
  tool_name: string | null
  attachments: string[] | null
  created_at: string
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref('')
  const messages = ref<ChatMessage[]>([])
  const loading = ref(false)

  async function fetchSessions() {
    const res = await api.get('/chat/sessions')
    sessions.value = res.data
  }

  async function createSession(title = 'New Chat') {
    const res = await api.post('/chat/sessions', { title })
    sessions.value.unshift(res.data)
    return res.data
  }

  async function fetchMessages(sessionId: string) {
    const res = await api.get(`/chat/sessions/${sessionId}`)
    messages.value = res.data.messages || []
  }

  async function sendMessage(sessionId: string, text: string, attachments: string[] = []) {
    const res = await fetch('/api/v1/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify({ session_id: sessionId, message: text, attachments }),
    })
    return res
  }

  async function uploadFile(sessionId: string, file: File) {
    const form = new FormData()
    form.append('file', file)
    const res = await api.post(`/chat/sessions/${sessionId}/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data.file_path
  }

  async function deleteSession(sessionId: string) {
    await api.delete(`/chat/sessions/${sessionId}`)
    sessions.value = sessions.value.filter((s) => s.id !== sessionId)
  }

  async function correctSearch(sessionId: string, invoicePath: string, correctedFields: Record<string, string | number>) {
    const res = await api.post(`/chat/sessions/${sessionId}/correct-search`, {
      invoice_path: invoicePath,
      corrected_fields: correctedFields,
    })
    return res.data
  }

  return {
    sessions, currentSessionId, messages, loading,
    fetchSessions, createSession, fetchMessages, sendMessage,
    uploadFile, deleteSession, correctSearch,
  }
})
