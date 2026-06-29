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
const uploadedFiles = ref<string[]>([])
const uploading = ref(false)

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
  uploadedFiles.value = []
  chat.currentSessionId = s.id
}

async function selectSession(sid: string) {
  chat.currentSessionId = sid
  streamingMessages.value = []
  uploadedFiles.value = []
  await chat.fetchMessages(sid)
  // Show persisted messages
  chat.messages.forEach((m) => {
    streamingMessages.value.push({
      role: m.role, content: m.content, tool_name: m.tool_name,
    })
  })
  scrollDown()
}

async function send() {
  const text = inputText.value.trim()
  if (!text || !chat.currentSessionId) return
  inputText.value = ''

  // Build full message with attachments
  let fullText = text
  if (uploadedFiles.value.length > 0) {
    fullText = `[已上传文件: ${uploadedFiles.value.join(', ')}]\n${text}`
  }
  const attachments = [...uploadedFiles.value]
  uploadedFiles.value = []

  // Add user bubble (show what user actually typed)
  streamingMessages.value.push({ role: 'user', content: text })

  // Add a single collapsible tool tracker
  const toolTracker: any = { role: 'agent-status', tools: [], done: false }
  streamingMessages.value.push(toolTracker)

  try {
    const res = await chat.sendMessage(chat.currentSessionId, fullText, attachments)
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
            toolTracker.done = true
            const last = streamingMessages.value[streamingMessages.value.length - 1]
            if (last?.role === 'assistant') {
              last.content += evt.content || ''
            } else {
              streamingMessages.value.push({ role: 'assistant', content: evt.content || '' })
            }
          } else if (evt.type === 'tool_call') {
            toolTracker.tools.push({ name: evt.tool, status: 'running' })
          } else if (evt.type === 'tool_result') {
            const t = toolTracker.tools.find((x: any) => x.name === evt.tool && x.status === 'running')
            if (t) t.status = 'done'
          }
        }
      }
      scrollDown()
    }
  } catch (e) {
    console.error('Chat error:', e)
  }

  // Reload persisted messages
  await chat.fetchMessages(chat.currentSessionId)
  await chat.fetchSessions()
  scrollDown()
}

async function handleFileUpload(e: Event) {
  const input = e.target as HTMLInputElement
  if (!input.files?.length || !chat.currentSessionId) return
  uploading.value = true
  try {
    const path = await chat.uploadFile(chat.currentSessionId, input.files[0])
    uploadedFiles.value.push(path)
  } catch (e) {
    console.error('Upload failed:', e)
  }
  uploading.value = false
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
      </div>
      <button class="btn-new" @click="newChat">+ New Chat</button>
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
        <span class="user-role">{{ auth.role }} | {{ auth.user?.username }}</span>
        <button class="btn-logout" @click="logout">Logout</button>
      </div>
    </aside>

    <!-- Main chat -->
    <main class="chat-main">
      <div class="chat-messages" ref="chatBox">
        <div v-if="!chat.currentSessionId" class="empty">
          <div class="empty-icon">+</div>
          <p>Create a new chat to start</p>
          <p class="empty-hint">You can ask about reimbursement policy or upload invoices</p>
        </div>
        <div
          v-for="(m, i) in streamingMessages"
          :key="i"
          :class="['msg', m.role]"
        >
          <!-- Agent status: show what tools are running -->
          <div v-if="m.role === 'agent-status'" class="agent-status">
            <div v-if="!m.done && m.tools.length > 0" class="status-thinking">
              <span class="dot"></span> Processing... ({{ m.tools.filter((t:any) => t.status === 'running').length }} tools running, {{ m.tools.filter((t:any) => t.status === 'done').length }} done)
            </div>
            <div v-if="m.done" class="status-done">
              Used tools: {{ m.tools.map((t:any) => t.name).join(' > ') }}
            </div>
          </div>
          <!-- Tool message from DB -->
          <div v-else-if="m.role === 'tool'" class="tool-badge">
            [{{ m.tool_name }}]
          </div>
          <!-- Normal message bubbles -->
          <div v-else class="msg-bubble">{{ m.content }}</div>
        </div>
      </div>

      <!-- Uploaded files indicator -->
      <div v-if="uploadedFiles.length > 0" class="uploaded-files">
        <span v-for="(f, i) in uploadedFiles" :key="i" class="file-tag">
          {{ f.split('/').pop() || f.split('\\').pop() }}
          <button @click="uploadedFiles.splice(i, 1)">x</button>
        </span>
      </div>

      <div class="chat-input">
        <input type="file" ref="fileInput" @change="handleFileUpload" hidden accept="image/*,.pdf,.txt" />
        <button class="btn-attach" @click="fileInput?.click()" :disabled="uploading">
          {{ uploading ? 'Uploading...' : '+' }}
        </button>
        <input
          v-model="inputText"
          placeholder="Type a message... (upload an invoice, then ask me to process it)"
          @keydown.enter="send"
        />
        <button class="btn-send" @click="send" :disabled="!inputText.trim()">Send</button>
      </div>
    </main>
  </div>
</template>

<style scoped>
* { box-sizing: border-box; }

.chat-layout {
  display: flex;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

/* ---- Sidebar ---- */
.sidebar {
  width: 280px;
  min-width: 280px;
  background: #1a1a2e;
  color: #fff;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.sidebar-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 16px 12px;
}
.sidebar-header h3 { font-size: 16px; margin: 0; }
.btn-new {
  margin: 0 16px 12px;
  padding: 10px 16px;
  background: #667eea;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  width: calc(100% - 32px);
}
.btn-new:hover { background: #5a6fd6; }

.session-list {
  flex: 1;
  overflow-y: auto;
  list-style: none;
  padding: 0 8px;
  margin: 0;
}
.session-list li {
  padding: 12px 14px;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 14px;
  margin-bottom: 2px;
}
.session-list li:hover { background: #2a2a4e; }
.session-list li.active { background: #667eea; }
.btn-del {
  background: none;
  border: none;
  color: rgba(255,255,255,0.5);
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
}
.btn-del:hover { color: #e74c3c; }

.sidebar-footer {
  padding: 14px 16px;
  border-top: 1px solid #2a2a4e;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  gap: 8px;
}
.user-role { color: #888; }
.btn-logout {
  padding: 6px 14px;
  background: #e74c3c;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}

/* ---- Main Chat ---- */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  min-width: 0;
}
.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 32px 48px;
}
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #999;
}
.empty-icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 3px dashed #ccc;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #ccc;
  margin-bottom: 16px;
}
.empty p { font-size: 16px; margin: 0; }
.empty-hint { font-size: 13px !important; color: #bbb; margin-top: 8px !important; }

/* ---- Messages ---- */
.msg { margin-bottom: 16px; max-width: 75%; }
.msg.user { margin-left: auto; }
.msg.assistant { margin-right: auto; }

.msg-bubble {
  padding: 12px 18px;
  border-radius: 16px;
  font-size: 15px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg.user .msg-bubble {
  background: #667eea;
  color: #fff;
  border-bottom-right-radius: 4px;
}
.msg.assistant .msg-bubble {
  background: #fff;
  color: #1a1a2e;
  border-bottom-left-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* ---- Agent Status ---- */
.agent-status {
  margin: 0 auto 16px;
}
.status-thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 20px;
  font-size: 13px;
  color: #856404;
}
.status-thinking .dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: #ffc107;
  animation: pulse 1s infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.status-done {
  padding: 8px 16px;
  background: #d4edda;
  border: 1px solid #28a745;
  border-radius: 20px;
  font-size: 13px;
  color: #155724;
  text-align: center;
}

/* ---- Tool Badge (from DB) ---- */
.tool-badge {
  display: inline-block;
  padding: 3px 10px;
  background: #e8e8e8;
  border-radius: 12px;
  font-size: 12px;
  color: #888;
  margin: 0 auto 8px;
}

/* ---- Uploaded Files ---- */
.uploaded-files {
  display: flex;
  gap: 8px;
  padding: 8px 48px;
  background: #fff;
  border-top: 1px solid #eee;
  flex-wrap: wrap;
}
.file-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: #e8f0fe;
  border: 1px solid #667eea;
  border-radius: 20px;
  font-size: 13px;
  color: #667eea;
}
.file-tag button {
  background: none;
  border: none;
  color: #999;
  cursor: pointer;
  font-size: 14px;
  padding: 0 2px;
}

/* ---- Input ---- */
.chat-input {
  display: flex;
  padding: 16px 48px;
  background: #fff;
  border-top: 1px solid #eee;
  align-items: center;
  gap: 12px;
}
.chat-input > input[type="text"] {
  flex: 1;
  padding: 14px 18px;
  border: 2px solid #e0e0e0;
  border-radius: 12px;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}
.chat-input > input[type="text"]:focus { border-color: #667eea; }

.btn-attach {
  padding: 12px 18px;
  background: #e8e8e8;
  color: #333;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 18px;
  font-weight: 700;
  min-width: 48px;
}
.btn-attach:hover { background: #ddd; }
.btn-attach:disabled { opacity: 0.5; }

.btn-send {
  padding: 12px 28px;
  background: #667eea;
  color: #fff;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 600;
}
.btn-send:hover { background: #5a6fd6; }
.btn-send:disabled { opacity: 0.4; cursor: default; }

/* ---- Responsive ---- */
@media (max-width: 768px) {
  .sidebar { width: 200px; min-width: 200px; }
  .chat-messages { padding: 20px 16px; }
  .chat-input { padding: 12px 16px; }
  .msg { max-width: 90%; }
}
</style>
