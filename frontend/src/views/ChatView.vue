<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'

const router = useRouter()
const auth = useAuthStore()
const chat = useChatStore()

const inputText = ref('')
const chatBox = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const streamingMessages = ref<any[]>([])

onMounted(async () => {
  await chat.fetchSessions()
  if (chat.sessions.length > 0) {
    await selectSession(chat.sessions[0].id)
  }
})

async function newChat() {
  const s = await chat.createSession()
  chat.messages = []
  streamingMessages.value = []
  chat.currentSessionId = s.id
}

async function selectSession(sid: string) {
  chat.currentSessionId = sid
  streamingMessages.value = []
  await chat.fetchMessages(sid)
  scrollDown()
}

async function send() {
  const text = inputText.value.trim()
  if (!text || !chat.currentSessionId) return
  inputText.value = ''

  // Add user bubble locally
  streamingMessages.value.push({ role: 'user', content: text })

  try {
    const res = await chat.sendMessage(chat.currentSessionId, text)
    const reader = res.body?.getReader()
    if (!reader) return

    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const evt = JSON.parse(line.slice(6))
          if (evt.type === 'message' && evt.role === 'assistant') {
            const last = streamingMessages.value[streamingMessages.value.length - 1]
            if (last?.role === 'assistant') {
              last.content += evt.content || ''
            } else {
              streamingMessages.value.push({ role: 'assistant', content: evt.content || '' })
            }
          } else if (evt.type === 'tool_call') {
            streamingMessages.value.push({
              role: 'tool', tool_name: evt.tool, status: 'calling',
              content: `Calling ${evt.tool}...`,
            })
          } else if (evt.type === 'tool_result') {
            streamingMessages.value.push({
              role: 'tool', tool_name: evt.tool, status: 'done',
              content: `Done: ${evt.tool}`,
            })
          } else if (evt.type === 'thinking') {
            // Skip for now
          }
        }
      }
      scrollDown()
    }
  } catch (e) {
    console.error('Chat error:', e)
  }

  // Reload session to get persisted messages
  if (chat.currentSessionId) {
    await chat.fetchMessages(chat.currentSessionId)
    streamingMessages.value = []
    chat.messages.forEach((m) => {
      streamingMessages.value.push({
        role: m.role, content: m.content, tool_name: m.tool_name,
      })
    })
  }
  await chat.fetchSessions()
  scrollDown()
}

function handleFileUpload(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files?.length || !chat.currentSessionId) return
  chat.uploadFile(chat.currentSessionId, input.files[0])
  input.value = ''
}

function scrollDown() {
  nextTick(() => {
    if (chatBox.value) {
      chatBox.value.scrollTop = chatBox.value.scrollHeight
    }
  })
}

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="chat-layout">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <h3>Chats</h3>
        <button class="btn-new" @click="newChat">+ New</button>
      </div>
      <ul class="session-list">
        <li
          v-for="s in chat.sessions"
          :key="s.id"
          :class="{ active: s.id === chat.currentSessionId }"
          @click="selectSession(s.id)"
        >
          <span>{{ s.title || 'Chat' }}</span>
          <button class="btn-del" @click.stop="chat.deleteSession(s.id)">x</button>
        </li>
      </ul>
      <div class="sidebar-footer">
        <span class="user-role">{{ auth.role }}</span>
        <button class="btn-logout" @click="logout">Logout</button>
      </div>
    </aside>

    <!-- Main chat -->
    <main class="chat-main">
      <div class="chat-messages" ref="chatBox">
        <div v-if="!chat.currentSessionId" class="empty">
          <p>Create a new chat to start</p>
        </div>
        <div
          v-for="(m, i) in streamingMessages"
          :key="i"
          :class="['msg', m.role]"
        >
          <div v-if="m.role === 'tool'" class="tool-badge">
            [{{ m.tool_name }}]
          </div>
          <div v-else class="msg-bubble">
            {{ m.content }}
          </div>
        </div>
      </div>
      <div class="chat-input">
        <input type="file" ref="fileInput" @change="handleFileUpload" hidden />
        <button class="btn-attach" @click="fileInput?.click()">+</button>
        <input
          v-model="inputText"
          placeholder="Type a message... (e.g. 'help me reimburse this invoice')"
          @keydown.enter="send"
        />
        <button class="btn-send" @click="send" :disabled="!inputText.trim()">Send</button>
      </div>
    </main>
  </div>
</template>

<style scoped>
.chat-layout { display: flex; height: 100vh; }
.sidebar {
  width: 260px; background: #1a1a2e; color: #fff;
  display: flex; flex-direction: column; overflow: hidden;
}
.sidebar-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px; border-bottom: 1px solid #2a2a4e;
}
.sidebar-header h3 { font-size: 15px; }
.btn-new {
  padding: 4px 12px; background: #667eea; color: #fff;
  border: none; border-radius: 6px; cursor: pointer; font-size: 13px;
}
.session-list { flex: 1; overflow-y: auto; list-style: none; padding: 8px; }
.session-list li {
  padding: 10px 12px; border-radius: 8px; cursor: pointer;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 14px; margin-bottom: 2px;
}
.session-list li:hover { background: #2a2a4e; }
.session-list li.active { background: #667eea; }
.btn-del { background: none; border: none; color: #aaa; cursor: pointer; font-size: 12px; }
.sidebar-footer {
  padding: 12px 16px; border-top: 1px solid #2a2a4e;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 13px;
}
.btn-logout { padding: 4px 10px; background: #e74c3c; color: #fff; border: none; border-radius: 6px; cursor: pointer; }

.chat-main { flex: 1; display: flex; flex-direction: column; background: #f5f7fa; }
.chat-messages { flex: 1; overflow-y: auto; padding: 20px; }
.empty { text-align: center; color: #999; margin-top: 100px; }
.msg { margin-bottom: 12px; }
.msg.user .msg-bubble { background: #667eea; color: #fff; margin-left: auto; }
.msg.assistant .msg-bubble { background: #fff; color: #1a1a2e; }
.msg-bubble {
  max-width: 70%; padding: 10px 16px; border-radius: 12px;
  font-size: 14px; line-height: 1.5; white-space: pre-wrap;
  display: inline-block;
}
.msg.user { text-align: right; }
.tool-badge {
  display: inline-block; padding: 4px 10px; background: #eee;
  border-radius: 20px; font-size: 12px; color: #666;
}
.chat-input {
  display: flex; padding: 16px; background: #fff; border-top: 1px solid #eee;
  align-items: center; gap: 10px;
}
.chat-input input[type="text"] {
  flex: 1; padding: 10px 14px; border: 1px solid #ddd; border-radius: 8px;
  font-size: 14px;
}
.btn-attach, .btn-send {
  padding: 8px 16px; background: #667eea; color: #fff; border: none;
  border-radius: 8px; cursor: pointer; font-size: 14px;
}
.btn-send:disabled { opacity: 0.5; cursor: default; }
</style>
