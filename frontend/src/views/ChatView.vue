<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import InvoiceCard from '../components/InvoiceCard.vue'
import PolicyCard from '../components/PolicyCard.vue'
import CorrectionForm from '../components/CorrectionForm.vue'

const router = useRouter()
const auth = useAuthStore()
const chat = useChatStore()

const inputText = ref('')
const chatBox = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const streamingMessages = ref<any[]>([])
const uploadedFiles = ref<string[]>([])
const uploading = ref(false)
const processing = ref(false)
const currentInvoiceData = ref<any>(null)
const currentPolicyData = ref<any>(null)
const showingCorrection = ref(false)

onMounted(async () => {
  await chat.fetchSessions()
  if (chat.sessions.length > 0) await selectSession(chat.sessions[0].id)
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
  chat.messages.forEach((m) => {
    streamingMessages.value.push({ role: m.role, content: m.content, tool_name: m.tool_name })
  })
  scrollDown()
}

async function send() {
  const text = inputText.value.trim()
  if (!text || !chat.currentSessionId || processing.value) return
  inputText.value = ''
  processing.value = true

  const attachments = [...uploadedFiles.value]
  uploadedFiles.value = []

  streamingMessages.value.push({ role: 'user', content: text })

  const toolTracker: any = { role: 'agent-status', tools: [], done: false, steps: [], plan: [] }
  streamingMessages.value.push(toolTracker)

  try {
    const res = await chat.sendMessage(chat.currentSessionId, text, attachments)
    const reader = res.body?.getReader()
    if (!reader) { processing.value = false; return }

    const decoder = new TextDecoder()
    let buf = ''
    let assistantStarted = false
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const evt = JSON.parse(line.slice(6))
          if (evt.type === 'plan') {
            // Execution plan from PAO agent
            toolTracker.plan = evt.steps || []
          } else if (evt.type === 'thinking') {
            // Real-time token streaming — show each token as it arrives
            const token = evt.content || ''
            if (assistantStarted) {
              const last = streamingMessages.value[streamingMessages.value.length - 1]
              if (last?.role === 'assistant') last.content += token
            } else {
              assistantStarted = true
              streamingMessages.value.push({ role: 'assistant', content: token })
            }
          } else if (evt.type === 'message' && evt.role === 'assistant') {
            toolTracker.done = true
            // If we already have a thinking-built assistant bubble, finalize it.
            // If no streaming happened (single-chunk response), create the bubble.
            if (assistantStarted) {
              const last = streamingMessages.value[streamingMessages.value.length - 1]
              if (last?.role === 'assistant' && last.content !== evt.content) {
                last.content = evt.content || ''
              }
            } else {
              assistantStarted = true
              streamingMessages.value.push({ role: 'assistant', content: evt.content || '' })
            }
          } else if (evt.type === 'tool_call') {
            toolTracker.tools.push({ name: evt.tool, status: 'running' })
            toolTracker.steps.push({ name: evt.tool, status: 'running' })
          } else if (evt.type === 'tool_result') {
            const t = toolTracker.tools.find((x: any) => x.name === evt.tool && x.status === 'running')
            if (t) t.status = 'done'
            const step = toolTracker.steps.find((x: any) => x.name === evt.tool && x.status === 'running')
            if (step) step.status = 'done'
          } else if (evt.type === 'done') {
            toolTracker.done = true
            toolTracker.tools.forEach((t: any) => {
              if (t.status === 'running') t.status = 'done'
            })
            toolTracker.steps.forEach((step: any) => {
              if (step.status === 'running') step.status = 'done'
            })
          } else if (evt.type === 'invoice_card') {
            // Invoice scan completed → show structured card
            currentInvoiceData.value = evt.data
            showingCorrection.value = false
            streamingMessages.value.push({
              role: 'invoice_card',
              data: evt.data,
              timestamp: Date.now(),
            })
          } else if (evt.type === 'policy_card') {
            // Policy match completed → show analysis card (reimbursement flow only)
            currentPolicyData.value = evt.data
            showingCorrection.value = false
            streamingMessages.value.push({
              role: 'policy_card',
              data: evt.data,
              timestamp: Date.now(),
            })
          } else if (evt.type === 'knowledge_refs') {
            // Pure consultation — AI already gave natural-language summary.
            // Show collapsible source citations only (no action buttons).
            streamingMessages.value.push({
              role: 'knowledge_refs',
              data: evt.data,
              timestamp: Date.now(),
            })
          } else if (evt.type === 'confirmation_request') {
            // Agent requests user confirmation — already handled by card buttons
          } else if (evt.type === 'error') {
            toolTracker.done = true
          }
        }
      }
      scrollDown()
    }
  } catch (e) {
    console.error('Chat error:', e)
  }

  processing.value = false
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
  } catch (e) { console.error('Upload failed:', e) }
  uploading.value = false
  input.value = ''
}

function scrollDown() {
  nextTick(() => { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight })
}

// ---- Card event handlers ----

function handleInvoiceConfirm(data: any) {
  // User confirmed invoice data → send confirmation message to agent
  const msg = '确认发票信息无误，请继续查询报销政策'
  streamingMessages.value.push({ role: 'user', content: msg })
  sendFollowUp(msg)
}

function handleInvoiceCorrect(data: any) {
  // Show correction form pre-filled with invoice fields
  currentInvoiceData.value = data
  showingCorrection.value = true
  streamingMessages.value.push({
    role: 'correction_form',
    data,
    timestamp: Date.now(),
  })
}

async function handleCorrectionSubmit(fields: Record<string, string | number>) {
  // User submitted corrected fields → re-search policy
  if (!chat.currentSessionId || !currentInvoiceData.value) return
  showingCorrection.value = false

  const changesStr = Object.entries(fields)
    .map(([k, v]) => `${k}: ${v}`)
    .join(', ')
  streamingMessages.value.push({
    role: 'user',
    content: `修正发票信息：${changesStr}`,
  })

  // Add agent-status chip
  const tracker: any = { role: 'agent-status', tools: [], done: false, steps: [], plan: [] }
  streamingMessages.value.push(tracker)

  try {
    const result = await chat.correctSearch(
      chat.currentSessionId,
      currentInvoiceData.value.invoice_path,
      fields,
    )
    tracker.done = true
    currentPolicyData.value = result
    streamingMessages.value.push({
      role: 'policy_card',
      data: result,
      timestamp: Date.now(),
    })
  } catch (e) {
    console.error('Correct search failed:', e)
    tracker.done = true
  }
  scrollDown()
}

function handleCorrectionCancel() {
  showingCorrection.value = false
  // Remove the correction form message
  const idx = streamingMessages.value.findIndex((m: any) => m.role === 'correction_form')
  if (idx >= 0) streamingMessages.value.splice(idx, 1)
}

function handlePolicyConfirm() {
  // User confirmed policy → send confirmation to agent
  if (!chat.currentSessionId) return
  const msg = '好的，确认无误，请帮我提交报销'
  streamingMessages.value.push({ role: 'user', content: msg })
  sendFollowUp(msg)
}

function handlePolicyCorrect(data: any) {
  // Out-of-scope or correction → show correction form
  const invoiceData = data?.invoice_fields
    ? { fields: data.invoice_fields, invoice_path: '' }
    : currentInvoiceData.value
  if (invoiceData) {
    currentInvoiceData.value = invoiceData
    showingCorrection.value = true
    streamingMessages.value.push({
      role: 'correction_form',
      data: invoiceData,
      timestamp: Date.now(),
    })
  }
}

async function sendFollowUp(message: string) {
  // Send a follow-up message to the agent (for confirm/correct actions)
  if (!chat.currentSessionId || processing.value) return
  processing.value = true

  const tracker: any = { role: 'agent-status', tools: [], done: false, steps: [], plan: [] }
  streamingMessages.value.push(tracker)

  try {
    const res = await chat.sendMessage(chat.currentSessionId, message, [])
    const reader = res.body?.getReader()
    if (!reader) { processing.value = false; return }

    const decoder = new TextDecoder()
    let buf = ''
    let assistantStarted = false
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() || ''
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const evt = JSON.parse(line.slice(6))
          if (evt.type === 'thinking') {
            const token = evt.content || ''
            if (assistantStarted) {
              const last = streamingMessages.value[streamingMessages.value.length - 1]
              if (last?.role === 'assistant') last.content += token
            } else {
              assistantStarted = true
              streamingMessages.value.push({ role: 'assistant', content: token })
            }
          } else if (evt.type === 'message' && evt.role === 'assistant') {
            tracker.done = true
            if (assistantStarted) {
              const last = streamingMessages.value[streamingMessages.value.length - 1]
              if (last?.role === 'assistant') last.content = evt.content || ''
            } else {
              streamingMessages.value.push({ role: 'assistant', content: evt.content || '' })
            }
          } else if (evt.type === 'tool_call') {
            tracker.tools.push({ name: evt.tool, status: 'running' })
          } else if (evt.type === 'tool_result') {
            const t = tracker.tools.find((x: any) => x.name === evt.tool && x.status === 'running')
            if (t) t.status = 'done'
          } else if (evt.type === 'done') {
            tracker.done = true
          } else if (evt.type === 'error') {
            tracker.done = true
          }
        }
      }
      scrollDown()
    }
  } catch (e) {
    console.error('Follow-up error:', e)
  }
  processing.value = false
  scrollDown()
}

function logout() { auth.logout(); router.push('/login') }
</script>

<template>
  <div class="app-shell">
    <!-- Left Rail -->
    <nav class="nav-rail">
      <div class="rail-brand" @click="newChat">
        <div class="brand-mark" />
      </div>
      <div class="rail-actions">
        <button class="rail-btn" title="New Chat" @click="newChat">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>
      <div class="rail-sessions">
        <button
          v-for="s in chat.sessions.slice(0, 8)"
          :key="s.id"
          :class="['rail-session', { active: s.id === chat.currentSessionId }]"
          @click="selectSession(s.id)"
          :title="s.title"
        >
          {{ (s.title || 'C').charAt(0).toUpperCase() }}
        </button>
      </div>
      <div class="rail-footer">
        <div class="rail-avatar">{{ (auth.user?.username || 'U').charAt(0).toUpperCase() }}</div>
        <button class="rail-logout" @click="logout" title="Logout">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
        </button>
      </div>
    </nav>

    <!-- Session List Panel -->
    <aside class="session-panel">
      <div class="panel-header">
        <h2>Conversations</h2>
        <span class="panel-count" v-if="chat.sessions.length">{{ chat.sessions.length }}</span>
      </div>
      <div class="session-list">
        <div
          v-for="s in chat.sessions"
          :key="s.id"
          :class="['session-item', { active: s.id === chat.currentSessionId }]"
          @click="selectSession(s.id)"
        >
          <div class="session-meta">
            <span class="session-title">{{ s.title || 'New Chat' }}</span>
            <span class="session-time">{{ new Date(s.created_at).toLocaleDateString() }}</span>
          </div>
          <div class="session-info">
            <span class="session-msgs">{{ s.message_count || 0 }} msgs</span>
          </div>
        </div>
        <div v-if="chat.sessions.length === 0" class="session-empty">
          <p>No conversations yet</p>
          <span>Create one to get started</span>
        </div>
      </div>
    </aside>

    <!-- Chat Area -->
    <main class="chat-area">
      <!-- Empty State -->
      <div v-if="!chat.currentSessionId" class="chat-empty">
        <div class="empty-graphic">
          <div class="graphic-ring" />
          <div class="graphic-dot" />
        </div>
        <h3>Expense Reimbursement Agent</h3>
        <p>Upload an invoice or ask me about company reimbursement policy</p>
        <div class="quick-actions">
          <button @click="newChat(); inputText = 'What is the meal allowance policy?'">Meal policy</button>
          <button @click="newChat()">Upload invoice</button>
          <button @click="newChat(); inputText = 'Check status of my expense report'">Check status</button>
        </div>
      </div>

      <!-- Messages -->
      <div v-else class="chat-messages" ref="chatBox">
        <div v-for="(m, i) in streamingMessages" :key="i" :class="['msg-row', m.role]">
          <!-- Agent Status Chip -->
          <div v-if="m.role === 'agent-status'" class="agent-chip-row">
            <div v-if="!m.done && m.tools.length > 0" class="agent-chip running">
              <div class="chip-dots"><span /><span /><span /></div>
              Processing
              <span class="chip-count">{{ m.tools.filter((t:any) => t.status === 'done').length }}/{{ m.tools.length }}</span>
            </div>
            <div v-if="m.done && m.steps.length > 0" class="agent-chip done">
              <svg class="chip-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
              {{ m.steps.map((t: any) => t.name.replace('_',' ')).join('  >  ') }}
            </div>
          </div>

          <!-- User Bubble -->
          <div v-else-if="m.role === 'user'" class="msg-bubble user">
            <div class="bubble-content">{{ m.content }}</div>
          </div>

          <!-- Assistant Bubble -->
          <div v-else-if="m.role === 'assistant'" class="msg-bubble assistant">
            <div class="bubble-content">{{ m.content }}</div>
          </div>

          <!-- Tool from DB -->
          <div v-else-if="m.role === 'tool'" class="msg-tool-db">
            <code>{{ m.tool_name }}</code>
          </div>

          <!-- Invoice Card -->
          <div v-else-if="m.role === 'invoice_card'" class="msg-card-row">
            <InvoiceCard
              :data="m.data"
              @confirm="handleInvoiceConfirm"
              @correct="handleInvoiceCorrect"
            />
          </div>

          <!-- Policy Card -->
          <div v-else-if="m.role === 'policy_card'" class="msg-card-row">
            <PolicyCard
              :data="m.data"
              @confirm="handlePolicyConfirm"
              @correct="handlePolicyCorrect"
              @cancel="() => {}"
            />
          </div>

          <!-- Knowledge Refs (consultation mode — readonly, no action buttons) -->
          <div v-else-if="m.role === 'knowledge_refs'" class="msg-card-row">
            <PolicyCard
              :data="{
                verdict: 'in_scope',
                summary: '',
                policy_refs: m.data.references,
                total_results: m.data.references?.length ?? 0,
                breakdown: null,
              }"
              :readonly="true"
            />
          </div>

          <!-- Correction Form -->
          <div v-else-if="m.role === 'correction_form'" class="msg-card-row">
            <CorrectionForm
              :fields="m.data.fields"
              :invoice-path="m.data.invoice_path"
              @submit="handleCorrectionSubmit"
              @cancel="handleCorrectionCancel"
            />
          </div>
        </div>
      </div>

      <!-- Upload indicator -->
      <div v-if="uploadedFiles.length > 0" class="upload-bar">
        <div v-for="(f, i) in uploadedFiles" :key="i" class="upload-tag">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          {{ f.split('/').pop() || f.split('\\').pop() }}
          <button @click="uploadedFiles.splice(i, 1)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </div>

      <!-- Input Bar -->
      <div class="input-bar" v-if="chat.currentSessionId">
        <input type="file" ref="fileInput" @change="handleFileUpload" hidden accept="image/*,.pdf,.txt" />
        <button class="input-attach" @click="fileInput?.click()" :disabled="uploading">
          <svg v-if="!uploading" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
          <span v-else class="mini-spinner" />
        </button>
        <div class="input-wrap">
          <textarea
            v-model="inputText"
            placeholder="Describe your expense or upload an invoice..."
            @keydown.enter.exact.prevent="send"
            rows="1"
          />
        </div>
        <button class="input-send" @click="send" :disabled="!inputText.trim() || processing">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
        </button>
      </div>
    </main>
  </div>
</template>

<style scoped>
* { box-sizing: border-box; margin: 0; padding: 0; }

/* ---- Shell ---- */
.app-shell {
  display: flex;
  height: 100vh;
  width: 100vw;
  background: #0a0a0e;
  color: #e4e4e7;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  overflow: hidden;
}

/* ---- Nav Rail (48px) ---- */
.nav-rail {
  width: 56px; min-width: 56px;
  background: #0f0f14;
  border-right: 1px solid rgba(255,255,255,0.04);
  display: flex; flex-direction: column; align-items: center;
  padding: 16px 0;
}
.brand-mark {
  width: 28px; height: 28px;
  background: linear-gradient(135deg, #6366f1, #a78bfa);
  border-radius: 8px; cursor: pointer;
  transition: transform 0.2s;
}
.brand-mark:hover { transform: scale(1.1); }
.rail-actions { margin-top: 20px; }
.rail-btn {
  width: 36px; height: 36px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 10px; color: rgba(255,255,255,0.5); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.rail-btn svg { width: 18px; height: 18px; }
.rail-btn:hover { background: rgba(255,255,255,0.08); color: #fff; }

.rail-sessions { flex: 1; display: flex; flex-direction: column; gap: 4px; padding: 12px 0; overflow-y: auto; }
.rail-session {
  width: 32px; height: 32px; min-height: 32px;
  border-radius: 8px; border: none; background: rgba(255,255,255,0.03);
  color: rgba(255,255,255,0.4); font-size: 12px; font-weight: 600;
  cursor: pointer; transition: all 0.2s;
}
.rail-session:hover { background: rgba(255,255,255,0.08); color: #fff; }
.rail-session.active { background: rgba(99,102,241,0.2); color: #a5b4fc; }

.rail-footer { margin-top: auto; display: flex; flex-direction: column; align-items: center; gap: 10px; }
.rail-avatar {
  width: 30px; height: 30px; border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; font-size: 12px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}
.rail-logout {
  background: none; border: none; color: rgba(255,255,255,0.25); cursor: pointer; padding: 4px;
  transition: color 0.2s;
}
.rail-logout svg { width: 16px; height: 16px; }
.rail-logout:hover { color: #f87171; }

/* ---- Session Panel (260px) ---- */
.session-panel {
  width: 260px; min-width: 260px;
  background: #0f0f14;
  border-right: 1px solid rgba(255,255,255,0.04);
  display: flex; flex-direction: column;
}
.panel-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 20px 12px;
}
.panel-header h2 { font-size: 14px; font-weight: 600; color: rgba(255,255,255,0.7); letter-spacing: -0.2px; }
.panel-count {
  font-size: 11px; padding: 2px 8px; background: rgba(99,102,241,0.15); color: #a5b4fc;
  border-radius: 12px; font-weight: 600;
}
.session-list { flex: 1; overflow-y: auto; padding: 0 12px 12px; }
.session-item {
  padding: 10px 12px; border-radius: 10px; cursor: pointer;
  margin-bottom: 2px; transition: background 0.15s;
}
.session-item:hover { background: rgba(255,255,255,0.03); }
.session-item.active { background: rgba(99,102,241,0.1); }
.session-meta { display: flex; flex-direction: column; gap: 2px; }
.session-title { font-size: 13px; font-weight: 500; color: rgba(255,255,255,0.8); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-time { font-size: 11px; color: rgba(255,255,255,0.25); }
.session-info { margin-top: 4px; }
.session-msgs { font-size: 10px; color: rgba(255,255,255,0.2); }
.session-empty {
  text-align: center; padding: 40px 20px;
}
.session-empty p { font-size: 13px; color: rgba(255,255,255,0.3); margin-bottom: 4px; }
.session-empty span { font-size: 11px; color: rgba(255,255,255,0.15); }

/* ---- Chat Area ---- */
.chat-area {
  flex: 1; display: flex; flex-direction: column;
  background: #0a0a0e;
  min-width: 0;
}

/* Empty state */
.chat-empty {
  flex: 1; display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  text-align: center; padding: 60px;
}
.empty-graphic { position: relative; margin-bottom: 32px; }
.graphic-ring {
  width: 80px; height: 80px; border-radius: 50%;
  border: 3px solid rgba(99,102,241,0.15);
  animation: ringPulse 3s ease-in-out infinite;
}
.graphic-dot {
  position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);
  width: 12px; height: 12px; border-radius: 50%;
  background: #6366f1;
}
@keyframes ringPulse {
  0%, 100% { transform: scale(1); opacity: 0.5; }
  50% { transform: scale(1.2); opacity: 1; }
}
.chat-empty h3 { font-size: 20px; font-weight: 600; color: #fff; margin-bottom: 8px; letter-spacing: -0.3px; }
.chat-empty p { font-size: 14px; color: rgba(255,255,255,0.35); margin-bottom: 32px; max-width: 360px; }
.quick-actions { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; }
.quick-actions button {
  padding: 10px 18px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.08);
  background: rgba(255,255,255,0.03); color: rgba(255,255,255,0.6);
  font-size: 13px; cursor: pointer; transition: all 0.2s;
}
.quick-actions button:hover {
  background: rgba(99,102,241,0.1); border-color: rgba(99,102,241,0.25); color: #a5b4fc;
}

/* Messages */
.chat-messages {
  flex: 1; overflow-y: auto; padding: 32px 20%;
  scroll-behavior: smooth;
}
@media (max-width: 1200px) { .chat-messages { padding: 24px 8%; } }

.msg-row { margin-bottom: 20px; display: flex; flex-direction: column; }
.msg-row.user { align-items: flex-end; }
.msg-row.assistant { align-items: flex-start; }

.msg-bubble {
  max-width: 80%;
  padding: 14px 20px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg-bubble.user {
  background: #6366f1;
  color: #fff;
  border-bottom-right-radius: 6px;
}
.msg-bubble.assistant {
  background: #18181b;
  color: #e4e4e7;
  border: 1px solid rgba(255,255,255,0.05);
  border-bottom-left-radius: 6px;
}

/* Agent chip */
.agent-chip-row {
  display: flex; justify-content: center; margin-bottom: 0;
}
.agent-chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: 500;
}
.agent-chip.running {
  background: rgba(251, 191, 36, 0.08); border: 1px solid rgba(251, 191, 36, 0.15); color: #fbbf24;
}
.agent-chip.done {
  background: rgba(52, 211, 153, 0.08); border: 1px solid rgba(52, 211, 153, 0.15); color: #34d399;
}
.chip-dots { display: flex; gap: 3px; }
.chip-dots span {
  width: 4px; height: 4px; border-radius: 50%; background: #fbbf24;
  animation: dotBounce 1.2s infinite;
}
.chip-dots span:nth-child(2) { animation-delay: 0.2s; }
.chip-dots span:nth-child(3) { animation-delay: 0.4s; }
@keyframes dotBounce {
  0%, 60%, 100% { opacity: 0.3; }
  30% { opacity: 1; }
}
.chip-count {
  font-size: 10px; padding: 1px 6px; background: rgba(251,191,36,0.15); border-radius: 10px;
}
.chip-check { width: 14px; height: 14px; flex-shrink: 0; }

.msg-tool-db {
  text-align: center;
}
.msg-tool-db code {
  font-size: 11px; padding: 3px 10px; background: rgba(255,255,255,0.03); border-radius: 12px;
  color: rgba(255,255,255,0.25);
}

.msg-card-row {
  display: flex; justify-content: flex-start;
  margin-bottom: 4px;
}

/* Upload bar */
.upload-bar {
  display: flex; gap: 8px; padding: 10px 20%; flex-wrap: wrap;
  border-top: 1px solid rgba(255,255,255,0.03);
}
.upload-tag {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: rgba(99,102,241,0.08); border: 1px solid rgba(99,102,241,0.2);
  border-radius: 20px; font-size: 12px; color: #a5b4fc;
}
.upload-tag svg { width: 14px; height: 14px; opacity: 0.6; }
.upload-tag button {
  background: none; border: none; color: rgba(255,255,255,0.3); cursor: pointer; padding: 0;
  display: flex; align-items: center;
}
.upload-tag button svg { width: 12px; height: 12px; }
.upload-tag button:hover { color: #f87171; }

/* Input bar */
.input-bar {
  display: flex; align-items: flex-end; gap: 10px;
  padding: 16px 20%; border-top: 1px solid rgba(255,255,255,0.04);
  background: #0f0f14;
}
@media (max-width: 1200px) { .input-bar { padding: 14px 8%; } }

.input-attach {
  width: 40px; height: 40px; min-width: 40px;
  border-radius: 12px; border: 1px solid rgba(255,255,255,0.06);
  background: rgba(255,255,255,0.03); color: rgba(255,255,255,0.3);
  cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.input-attach svg { width: 18px; height: 18px; }
.input-attach:hover { background: rgba(255,255,255,0.06); color: #a5b4fc; border-color: rgba(99,102,241,0.3); }

.input-wrap { flex: 1; }
.input-wrap textarea {
  width: 100%; resize: none;
  padding: 11px 16px; background: #18181b;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px; color: #e4e4e7; font-size: 14px;
  font-family: inherit; line-height: 1.5;
  outline: none; transition: border-color 0.2s;
}
.input-wrap textarea:focus { border-color: rgba(99,102,241,0.4); }
.input-wrap textarea::placeholder { color: rgba(255,255,255,0.2); }

.input-send {
  width: 40px; height: 40px; min-width: 40px;
  border-radius: 12px; border: none;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; cursor: pointer; display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.input-send svg { width: 18px; height: 18px; }
.input-send:hover:not(:disabled) { box-shadow: 0 4px 16px rgba(99,102,241,0.35); }
.input-send:disabled { opacity: 0.3; cursor: default; }

.mini-spinner {
  width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.2);
  border-top-color: #fff; border-radius: 50%; animation: spin 0.6s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
