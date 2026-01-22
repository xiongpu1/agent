<template>
  <div class="kbchat">
    <div class="kbchat__viewport" ref="viewportRef" @scroll="handleScroll">
      <div class="kbchat__container">
        <div v-if="!messages.length" class="kbchat__empty">
          <div class="kbchat__chips">
            <button
              v-if="suggestionsFailed"
              class="kbchat__chip kbchat__chip--retry"
              type="button"
              @click="getSuggestions()"
            >
              点击重试推荐问题
            </button>
            <button
              v-for="q in suggestedQuestions"
              :key="q"
              class="kbchat__chip"
              type="button"
              @click="useSuggestion(q)"
            >
              {{ q }}
            </button>
          </div>
        </div>

        <div v-else class="kbchat__messages">
          <div v-for="m in messages" :key="m.id" class="kbchat__msg" :class="m.role">
            <div class="kbchat__avatar">{{ m.role === 'assistant' ? 'AI' : '你' }}</div>
            <div class="kbchat__content">
              <div class="kbchat__text" v-text="m.content" />
              <div v-if="m.status === 'typing'" class="kbchat__typing">
                <span class="dot" />
                <span class="dot" />
                <span class="dot" />
              </div>

              <div v-if="false" class="kbchat__citations" />
            </div>
          </div>
        </div>
      </div>

      <button
        v-if="showScrollToBottom"
        class="kbchat__scrollBottom"
        type="button"
        @click="scrollToBottom()"
      >
        回到底部
      </button>
    </div>

    <div class="kbchat__composer">
      <div class="kbchat__composerInner">
        <button class="kbchat__plus" type="button" :disabled="true" aria-label="attachment">
          +
        </button>

        <textarea
          ref="textareaRef"
          v-model="draft"
          class="kbchat__input"
          rows="1"
          placeholder="有问题，尽管问"
          @keydown.enter.exact.prevent="handleSend"
          @keydown.enter.shift.exact.stop
          @input="autoResize"
        />

        <button
          class="kbchat__send"
          type="button"
          :disabled="!canSend"
          @click="handleSend"
        >
          发送
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

const viewportRef = ref(null)
const textareaRef = ref(null)

const draft = ref('')
const messages = ref([])
const showScrollToBottom = ref(false)

const suggestedQuestions = ref([])
const suggestionsFailed = ref(false)

const sessionId = ref('')
const isStreaming = ref(false)
const streamAbortController = ref(null)
const eventSourceRef = ref(null)

const canSend = computed(() => draft.value.trim().length > 0)

const autoResize = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  const max = 200
  el.style.height = `${Math.min(el.scrollHeight, max)}px`
}

const scrollToBottom = async () => {
  await nextTick()
  const el = viewportRef.value
  if (!el) return
  el.scrollTop = el.scrollHeight
}

const handleScroll = () => {
  const el = viewportRef.value
  if (!el) return
  const threshold = 48
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < threshold
  showScrollToBottom.value = !atBottom
}

const useSuggestion = async (q) => {
  draft.value = q
  await nextTick()
  autoResize()
  textareaRef.value?.focus()
}

const resolveApiUrl = (path) => {
  const p = String(path || '')
  if (!p) return ''
  if (p.startsWith('http://') || p.startsWith('https://')) return p
  if (p.startsWith('/') && API_BASE_URL) return `${API_BASE_URL}${p}`
  return p
}

const getSuggestions = async () => {
  try {
    suggestionsFailed.value = false
    const url = resolveApiUrl('/api/kb/chat/suggestions')
    const resp = await fetch(url)
    if (!resp.ok) throw new Error(await resp.text())
    const data = await resp.json()
    const arr = Array.isArray(data?.suggestions) ? data.suggestions.filter((s) => typeof s === 'string' && s.trim()) : []
    suggestedQuestions.value = arr.length ? arr.slice(0, 6) : []
  } catch (e) {
    suggestionsFailed.value = true
    suggestedQuestions.value = []
  }
}

const buildHistoryPayload = () =>
  messages.value
    .filter((m) => m.role === 'user' || m.role === 'assistant')
    .map((m) => ({ role: m.role, content: m.content }))
    .slice(-12)

const stopStreaming = () => {
  if (eventSourceRef.value) {
    try {
      eventSourceRef.value.close()
    } catch (e) {}
  }
  eventSourceRef.value = null
  if (streamAbortController.value) {
    try {
      streamAbortController.value.abort()
    } catch (e) {}
  }
  streamAbortController.value = null
  isStreaming.value = false
}

const fetchNonStreamAnswer = async (userText) => {
  const url = resolveApiUrl('/api/kb/chat')
  const payload = {
    sessionId: sessionId.value || undefined,
    message: userText,
    history: buildHistoryPayload(),
    context: { moduleKey: 'kbChat' }
  }
  const controller = new AbortController()
  const timeoutMs = 15000
  const t = setTimeout(() => controller.abort(), timeoutMs)
  let resp
  try {
    resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    })
  } catch (e) {
    if (e?.name === 'AbortError') {
      throw new Error('请求超时：后端未在 15 秒内响应，请检查 Neo4j/模型服务是否可用')
    }
    throw e
  } finally {
    clearTimeout(t)
  }

  const raw = await resp.text().catch(() => '')
  if (!resp.ok) throw new Error(raw || `HTTP ${resp.status}`)
  try {
    return JSON.parse(raw)
  } catch (e) {
    throw new Error(raw || '后端返回非 JSON 响应')
  }
}

const startStreamViaEventSource = (userText, assistantMsg) => {
  stopStreaming()
  isStreaming.value = true

  return new Promise((resolve) => {
    let gotAnyEvent = false
    let finalized = false
    const markGotEvent = () => {
      gotAnyEvent = true
    }

    const payloadObj = {
      sessionId: sessionId.value || '',
      message: userText,
      history: buildHistoryPayload(),
      context: { moduleKey: 'kbChat' }
    }
    const qs = new URLSearchParams({
      payload: JSON.stringify(payloadObj)
    })
    const url = resolveApiUrl(`/api/kb/chat/stream_get?${qs.toString()}`)
    const es = new EventSource(url)
    eventSourceRef.value = es

    es.onopen = () => {
      markGotEvent()
    }

    const finalize = () => {
      finalized = true
      clearTimeout(firstEventTimeout)
      try {
        es.close()
      } catch (e) {}
      eventSourceRef.value = null
      isStreaming.value = false
      if (assistantMsg.status === 'typing') assistantMsg.status = 'done'
      resolve(true)
    }

    const firstEventTimeout = setTimeout(() => {
      if (gotAnyEvent) return
      // SSE likely blocked/buffered by proxy; fallback to non-streaming.
      try {
        es.close()
      } catch (e) {}
      eventSourceRef.value = null
      isStreaming.value = false
      ;(async () => {
        try {
          const data = await fetchNonStreamAnswer(userText)
          console.log('[KbChat] response', data)
          if (data?.sessionId && !sessionId.value) sessionId.value = data.sessionId
          assistantMsg.status = 'done'
          assistantMsg.content = data?.content || '请求失败'
          assistantMsg.citations = Array.isArray(data?.citations) ? data.citations : []
        } catch (e) {
          console.log('[KbChat] request failed', e)
          assistantMsg.status = 'done'
          assistantMsg.content = e?.message || '连接超时，请稍后重试'
        } finally {
          resolve(true)
        }
      })()
    }, 15000)

    es.addEventListener('meta', (ev) => {
      markGotEvent()
      try {
        const data = JSON.parse(ev.data || '{}')
        if (data?.sessionId && !sessionId.value) sessionId.value = data.sessionId
      } catch (e) {}
    })

    es.addEventListener('clarify', (ev) => {
      markGotEvent()
      try {
        const data = JSON.parse(ev.data || '{}')
        assistantMsg.status = 'done'
        assistantMsg.content = data?.content || assistantMsg.content
      } catch (e) {}
      finalize()
    })

    es.addEventListener('answer_delta', (ev) => {
      markGotEvent()
      try {
        const data = JSON.parse(ev.data || '{}')
        const d = data?.delta || ''
        if (d) assistantMsg.content += d
        scrollToBottom()
      } catch (e) {}
    })

    es.addEventListener('citations', (ev) => {
      markGotEvent()
      try {
        const data = JSON.parse(ev.data || '{}')
        assistantMsg.citations = Array.isArray(data?.citations) ? data.citations : []
      } catch (e) {}
    })

    es.addEventListener('done', () => {
      markGotEvent()
      finalize()
    })

    es.addEventListener('error', () => {
      // Some browsers may emit an 'error' event when the server closes the connection
      // even after we've received the full answer and processed 'done'.
      if (finalized) return
      if (gotAnyEvent && assistantMsg.content) {
        finalize()
        return
      }
      clearTimeout(firstEventTimeout)
      try {
        es.close()
      } catch (e) {}
      eventSourceRef.value = null
      isStreaming.value = false
      ;(async () => {
        try {
          const data = await fetchNonStreamAnswer(userText)
          console.log('[KbChat] response', data)
          if (data?.sessionId && !sessionId.value) sessionId.value = data.sessionId
          assistantMsg.status = 'done'
          assistantMsg.content = data?.content || '请求失败'
          assistantMsg.citations = Array.isArray(data?.citations) ? data.citations : []
        } catch (e) {
          console.log('[KbChat] request failed', e)
          assistantMsg.status = 'done'
          assistantMsg.content = e?.message || '连接失败或被中断'
        } finally {
          resolve(true)
        }
      })()
    })
  })
}

const startStream = async (userText, assistantMsg) => {
  stopStreaming()
  isStreaming.value = true
  try {
    const data = await fetchNonStreamAnswer(userText)
    console.log('[KbChat] response', data)
    if (data?.sessionId && !sessionId.value) sessionId.value = data.sessionId
    assistantMsg.status = 'done'
    assistantMsg.content = data?.content || '请求失败'
    assistantMsg.citations = Array.isArray(data?.citations) ? data.citations : []
  } catch (e) {
    console.log('[KbChat] request failed', e)
    assistantMsg.status = 'done'
    assistantMsg.content = e?.message || '请求失败'
  } finally {
    isStreaming.value = false
  }
}

const handleSend = async () => {
  const text = draft.value.trim()
  if (!text || isStreaming.value) return

  const now = Date.now()
  const userId = `${now}-u`
  const aiId = `${now}-a`

  const userMsg = reactive({ id: userId, role: 'user', content: text })
  const assistantMsg = reactive({
    id: aiId,
    role: 'assistant',
    content: '',
    status: 'typing',
    citations: [],
    showCitations: false
  })

  messages.value.push(userMsg)
  messages.value.push(assistantMsg)

  draft.value = ''
  await nextTick()
  autoResize()
  await scrollToBottom()

  try {
    await startStreamViaEventSource(text, assistantMsg)
  } catch (e) {
    assistantMsg.status = 'done'
    assistantMsg.content = e?.message || '请求失败'
  } finally {
    if (assistantMsg.status === 'typing') {
      assistantMsg.status = 'done'
      if (!assistantMsg.content) assistantMsg.content = '请求结束但未收到内容'
    }
    console.log('[KbChat] final status', assistantMsg.status, assistantMsg.content)
    await nextTick()
    scrollToBottom()
  }
}

onMounted(async () => {
  await getSuggestions()
  autoResize()
  scrollToBottom()
})
</script>

<style scoped>
.kbchat {
  height: calc(100vh - 110px);
  min-height: 520px;
  display: flex;
  flex-direction: column;
  border-radius: 14px;
  overflow: hidden;
  background: #ffffff;
  border: 1px solid var(--color-border, #ebeef5);
}

.kbchat__viewport {
  position: relative;
  flex: 1 1 auto;
  overflow: auto;
}

.kbchat__container {
  max-width: 860px;
  margin: 0 auto;
  padding: 20px 18px 120px;
}

.kbchat__empty {
  padding: 56px 0 0;
  text-align: center;
}

.kbchat__chips {
  margin-top: 22px;
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
}

.kbchat__chip {
  width: 100%;
  text-align: left;
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 12px;
  padding: 14px 14px;
  cursor: pointer;
  color: #111827;
}

.kbchat__chip--retry {
  border-style: dashed;
  color: #334155;
}

.kbchat__chip:hover {
  border-color: #cbd5e1;
  background: #fafafa;
}

.kbchat__messages {
  display: grid;
  gap: 14px;
}

.kbchat__msg {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 12px;
  align-items: start;
}

.kbchat__avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 12px;
  color: #111827;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
}

.kbchat__msg.user .kbchat__avatar {
  background: #111827;
  color: #ffffff;
  border-color: #111827;
}

.kbchat__content {
  padding-top: 4px;
}

.kbchat__text {
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.7;
  color: #111827;
}

.kbchat__citations {
  margin-top: 10px;
}

.kbchat__citationsToggle {
  border: 1px solid #e5e7eb;
  background: #fff;
  color: #111827;
  border-radius: 10px;
  padding: 6px 10px;
  font-size: 12px;
  cursor: pointer;
}

.kbchat__citationsPanel {
  margin-top: 10px;
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 12px;
  padding: 10px;
}

.kbchat__citation {
  padding: 8px 6px;
  border-top: 1px solid #f3f4f6;
}

.kbchat__citation:first-child {
  border-top: none;
}

.kbchat__citationTitle {
  font-size: 13px;
  font-weight: 700;
  color: #111827;
}

.kbchat__citationSnippet {
  margin-top: 4px;
  color: #374151;
  font-size: 12px;
  line-height: 1.5;
}

.kbchat__citationMeta {
  margin-top: 4px;
  color: #9ca3af;
  font-size: 12px;
}

.kbchat__typing {
  margin-top: 8px;
  display: flex;
  gap: 6px;
  align-items: center;
}

.kbchat__typing .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #9ca3af;
  animation: kbchat-bounce 1s infinite ease-in-out;
}

.kbchat__typing .dot:nth-child(2) {
  animation-delay: 0.15s;
}

.kbchat__typing .dot:nth-child(3) {
  animation-delay: 0.3s;
}

@keyframes kbchat-bounce {
  0%,
  100% {
    transform: translateY(0);
    opacity: 0.55;
  }
  50% {
    transform: translateY(-3px);
    opacity: 1;
  }
}

.kbchat__scrollBottom {
  position: absolute;
  right: 16px;
  bottom: 90px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  border-radius: 999px;
  padding: 8px 12px;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.kbchat__scrollBottom:hover {
  background: #fafafa;
}

.kbchat__composer {
  position: sticky;
  bottom: 0;
  background: rgba(255, 255, 255, 0.96);
  border-top: 1px solid #e5e7eb;
  padding: 14px 14px 10px;
  backdrop-filter: blur(8px);
}

.kbchat__composerInner {
  max-width: 860px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 40px 1fr 64px;
  gap: 10px;
  align-items: end;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  padding: 10px;
  background: #fff;
}

.kbchat__plus {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  border: 1px solid #e5e7eb;
  background: #fff;
  cursor: not-allowed;
  color: #6b7280;
  font-size: 18px;
}

.kbchat__input {
  width: 100%;
  resize: none;
  border: 0;
  outline: none;
  font-size: 14px;
  line-height: 1.5;
  padding: 8px 2px;
  background: transparent;
  color: #111827;
}

.kbchat__send {
  height: 40px;
  border-radius: 999px;
  border: 0;
  background: #111827;
  color: #fff;
  cursor: pointer;
  font-weight: 700;
}

.kbchat__send:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .kbchat {
    height: calc(100vh - 96px);
    min-height: 420px;
  }

  .kbchat__container {
    padding-left: 14px;
    padding-right: 14px;
  }

  .kbchat__composerInner {
    grid-template-columns: 40px 1fr 56px;
  }
}
</style>
