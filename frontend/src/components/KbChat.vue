<template>
  <div class="kbchat">
    <div class="kbchat__sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="kbchat__sidebarHeader">
        <div v-if="!sidebarCollapsed" class="kbchat__sidebarTitle">对话</div>
        <div class="kbchat__sidebarActions">
          <button
            class="kbchat__collapse"
            type="button"
            :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
            :aria-label="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'"
            @click="toggleSidebar()"
          >
            <svg v-if="sidebarCollapsed" class="kbchat__icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M10 6L16 12L10 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg v-else class="kbchat__icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M14 6L8 12L14 18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
          <button
            class="kbchat__newChat"
            type="button"
            title="新建对话"
            aria-label="新建对话"
            @click="createConversation()"
          >
            <svg v-if="sidebarCollapsed" class="kbchat__icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 5V19" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
              <path d="M5 12H19" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
            <span v-else>新建</span>
          </button>
        </div>
      </div>
      <div v-if="!sidebarCollapsed" class="kbchat__convList">
        <div v-if="isInitializing" class="kbchat__convSkeleton">
          <div v-for="i in 6" :key="i" class="kbchat__convSkeletonItem">
            <div class="kbchat__skeleton kbchat__skeletonLine kbchat__convSkeletonTitle" />
            <div class="kbchat__skeleton kbchat__skeletonLine kbchat__convSkeletonMeta" />
          </div>
        </div>

        <button
          v-else
          v-for="c in conversations"
          :key="c.id"
          class="kbchat__convItem"
          :class="{ active: c.id === conversationId }"
          type="button"
          @click="selectConversation(c.id)"
        >
          <div class="kbchat__convTitle">{{ c.title }}</div>
          <div class="kbchat__convMeta">{{ formatTime(c.updated_at_ms || c.updated_at) }}</div>
        </button>
      </div>
    </div>

    <div class="kbchat__main">
      <div class="kbchat__viewport" ref="viewportRef" @scroll="handleScroll">
        <div class="kbchat__container">
        <div v-if="isInitializing" class="kbchat__msgSkeleton">
          <div v-for="i in 4" :key="i" class="kbchat__msgSkeletonRow">
            <div class="kbchat__skeleton kbchat__skeletonAvatar" />
            <div class="kbchat__msgSkeletonBubble">
              <div class="kbchat__skeleton kbchat__skeletonLine kbchat__msgSkeletonLine1" />
              <div class="kbchat__skeleton kbchat__skeletonLine kbchat__msgSkeletonLine2" />
            </div>
          </div>
        </div>

        <div v-else-if="!messages.length" class="kbchat__empty">
          <div class="kbchat__emptyBrand">
            <img class="kbchat__emptyLogo" src="../assets/logo.svg" alt="logo" />
          </div>
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
              <details v-if="m.role === 'assistant' && m.reasoning" class="kbchat__reasoning" open>
                <summary class="kbchat__reasoningTitle">思考过程</summary>
                <div class="kbchat__reasoningText" v-text="m.reasoning" />
              </details>
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
          :disabled="isInitializing"
          @keydown.enter.exact.prevent="handleSend"
          @keydown.enter.shift.exact.stop
          @input="autoResize"
        />

          <button
            class="kbchat__send"
            type="button"
            :disabled="!canSend || isInitializing"
            @click="handleSend"
          >
            发送
          </button>
        </div>
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
const conversationId = ref('')
const isStreaming = ref(false)
const streamAbortController = ref(null)
const eventSourceRef = ref(null)

const isInitializing = ref(true)

const sidebarCollapsed = ref(false)
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const canSend = computed(() => draft.value.trim().length > 0)

const conversations = ref([])

const authUser = ref(null)
const isLoggedIn = computed(() => Boolean(authUser.value?.userid))
const modeKey = computed(() => (isLoggedIn.value ? `u:${authUser.value.userid}` : 'anon'))

const localConvId = ref('')

let authPollTimer = null
const lastAuthUserid = ref('')

const formatTime = (v) => {
  const n = Number(v || 0)
  if (!n) return ''
  const d = new Date(n)
  return d.toLocaleString()
}

const fetchJson = async (path, options) => {
  const url = resolveApiUrl(path)
  const resp = await fetch(url, { credentials: 'include', ...(options || {}) })
  const raw = await resp.text().catch(() => '')
  if (!resp.ok) throw new Error(raw || `HTTP ${resp.status}`)
  try {
    return JSON.parse(raw)
  } catch (e) {
    throw new Error(raw || '后端返回非 JSON 响应')
  }
}

const fetchMe = async () => {
  try {
    const url = resolveApiUrl('/api/auth/me')
    const resp = await fetch(url, { credentials: 'include' })
    if (!resp.ok) return null
    const data = await resp.json()
    return data?.user || null
  } catch {
    return null
  }
}

const localKey = (suffix) => `kbchat_local_${suffix}_${modeKey.value}`

const loadLocalState = () => {
  try {
    const raw = localStorage.getItem(localKey('state')) || ''
    const st = raw ? JSON.parse(raw) : {}
    const convs = Array.isArray(st?.conversations) ? st.conversations : []
    const msgs = st?.messages && typeof st.messages === 'object' ? st.messages : {}
    const selected = String(st?.selectedId || '')
    return { conversations: convs, messages: msgs, selectedId: selected }
  } catch {
    return { conversations: [], messages: {}, selectedId: '' }
  }
}

const saveLocalState = (state) => {
  try {
    localStorage.setItem(localKey('state'), JSON.stringify(state || {}))
  } catch (e) {}
}

const ensureLocalConversation = () => {
  const st = loadLocalState()
  const convs = Array.isArray(st.conversations) ? st.conversations : []
  let cid = String(st.selectedId || '')
  if (!cid && convs.length) cid = String(convs[0]?.id || '')
  if (!cid) {
    const now = Date.now()
    cid = `local-${now}`
    convs.unshift({ id: cid, title: '新对话', updated_at_ms: now, created_at_ms: now })
  }
  const next = { conversations: convs, messages: st.messages || {}, selectedId: cid }
  saveLocalState(next)
  return cid
}

const loadConversations = async () => {
  if (!isLoggedIn.value) {
    const st = loadLocalState()
    conversations.value = Array.isArray(st.conversations) ? st.conversations : []
    return
  }
  const data = await fetchJson('/api/kb/conversations', { method: 'GET' })
  conversations.value = Array.isArray(data?.conversations) ? data.conversations : []
}

const loadMessages = async (cid) => {
  if (!isLoggedIn.value) {
    const st = loadLocalState()
    const arr = Array.isArray(st?.messages?.[cid]) ? st.messages[cid] : []
    messages.value = arr.map((m) =>
      reactive({
        id: m.id || `${m.ts || Date.now()}`,
        role: m.role,
        content: m.content || '',
        reasoning: m.reasoning || '',
        status: m.status || 'done',
        citations: Array.isArray(m.citations) ? m.citations : [],
        showCitations: false
      })
    )
    return
  }

  const data = await fetchJson(`/api/kb/conversations/${cid}/messages?limit=200`, { method: 'GET' })
  const arr = Array.isArray(data?.messages) ? data.messages : []
  messages.value = arr
    .filter((m) => m?.role === 'user' || m?.role === 'assistant')
    .map((m) =>
      reactive({
        id: m.id || `${m.seq || Date.now()}`,
        role: m.role,
        content: m.content || '',
        reasoning: m.reasoning || '',
        status: 'done',
        citations: Array.isArray(m.citations) ? m.citations : [],
        showCitations: false
      })
    )
}

const selectConversation = async (cid) => {
  stopStreaming()
  if (isLoggedIn.value) {
    conversationId.value = cid
  } else {
    localConvId.value = cid
  }
  try {
    localStorage.setItem(`kbchat_conversation_id_${modeKey.value}`, cid)
  } catch (e) {}
  await loadMessages(cid)
  await nextTick()
  scrollToBottom()
}

const createConversation = async () => {
  if (!isLoggedIn.value) {
    const now = Date.now()
    const cid = `local-${now}`
    const st = loadLocalState()
    const convs = Array.isArray(st.conversations) ? st.conversations : []
    convs.unshift({ id: cid, title: '新对话', updated_at_ms: now, created_at_ms: now })
    const next = { conversations: convs, messages: st.messages || {}, selectedId: cid }
    saveLocalState(next)
    await loadConversations()
    await selectConversation(cid)
    return
  }

  const data = await fetchJson('/api/kb/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  })
  const cid = data?.conversation?.id
  if (!cid) throw new Error('创建会话失败')
  await loadConversations()
  await selectConversation(cid)
}

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
  const local = !isLoggedIn.value
  const cid = local ? localConvId.value : conversationId.value
  const payload = local
    ? { local: true, conversationId: cid || 'local', message: userText, history: buildHistoryPayload(), context: { moduleKey: 'kbChat' } }
    : { conversationId: cid, message: userText, context: { moduleKey: 'kbChat' } }
  const controller = new AbortController()
  const timeoutMs = 15000
  const t = setTimeout(() => controller.abort(), timeoutMs)
  let resp
  try {
    resp = await fetch(url, {
      method: 'POST',
      credentials: 'include',
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

    const local = !isLoggedIn.value
    const cid = local ? localConvId.value : conversationId.value
    const payloadObj = local
      ? { local: true, conversationId: cid || 'local', message: userText, history: buildHistoryPayload(), context: { moduleKey: 'kbChat' } }
      : { conversationId: cid, message: userText, context: { moduleKey: 'kbChat' } }
    const qs = new URLSearchParams({
      payload: JSON.stringify(payloadObj)
    })
    const url = resolveApiUrl(`/api/kb/chat/stream_get?${qs.toString()}`)
    const es = new EventSource(url, { withCredentials: true })
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
          assistantMsg.reasoning = data?.reasoning || ''
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

    es.addEventListener('reasoning_delta', (ev) => {
      markGotEvent()
      try {
        const data = JSON.parse(ev.data || '{}')
        const d = data?.delta || ''
        if (d) assistantMsg.reasoning = (assistantMsg.reasoning || '') + d
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
          assistantMsg.reasoning = data?.reasoning || ''
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
    assistantMsg.reasoning = data?.reasoning || ''
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
    reasoning: '',
    status: 'typing',
    citations: [],
    showCitations: false
  })

  messages.value.push(userMsg)
  messages.value.push(assistantMsg)

  if (!isLoggedIn.value) {
    const cid = localConvId.value
    const st = loadLocalState()
    const msgsMap = st.messages && typeof st.messages === 'object' ? st.messages : {}
    const arr = Array.isArray(msgsMap[cid]) ? msgsMap[cid] : []
    arr.push({ id: userId, role: 'user', content: text, ts: now })
    arr.push({ id: aiId, role: 'assistant', content: '', reasoning: '', status: 'typing', ts: now })
    msgsMap[cid] = arr
    const convs = Array.isArray(st.conversations) ? st.conversations : []
    const idx = convs.findIndex((c) => c.id === cid)
    if (idx >= 0) convs[idx] = { ...convs[idx], updated_at_ms: now }
    saveLocalState({ conversations: convs, messages: msgsMap, selectedId: cid })
    await loadConversations()
  }

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

    if (!isLoggedIn.value) {
      try {
        const cid = localConvId.value
        const st = loadLocalState()
        const msgsMap = st.messages && typeof st.messages === 'object' ? st.messages : {}
        const arr = Array.isArray(msgsMap[cid]) ? msgsMap[cid] : []
        const i = arr.findIndex((m) => m.id === aiId)
        if (i >= 0) {
          arr[i] = {
            ...arr[i],
            content: assistantMsg.content,
            reasoning: assistantMsg.reasoning,
            status: 'done',
            citations: assistantMsg.citations
          }
        }
        msgsMap[cid] = arr
        saveLocalState({ conversations: st.conversations || [], messages: msgsMap, selectedId: cid })
      } catch (e) {}
    }

    console.log('[KbChat] final status', assistantMsg.status, assistantMsg.content)
    await nextTick()
    scrollToBottom()
  }
}

onMounted(async () => {
  const initChat = async (options = {}) => {
    const skipFetch = Boolean(options.skipFetchMe)
    stopStreaming()
    messages.value = []
    conversations.value = []
    conversationId.value = ''
    localConvId.value = ''
    sessionId.value = ''

    isInitializing.value = true
    try {
      await getSuggestions()

      if (!skipFetch) {
        authUser.value = await fetchMe()
      }
      lastAuthUserid.value = String(authUser.value?.userid || '')

      if (!isLoggedIn.value) {
        await loadConversations()
        const cid = ensureLocalConversation()
        localConvId.value = cid
        await selectConversation(cid)
        return
      }

      await loadConversations()
      let cid = ''
      try {
        cid = localStorage.getItem(`kbchat_conversation_id_${modeKey.value}`) || ''
      } catch (e) {}
      if (!cid && conversations.value.length) cid = conversations.value[0].id
      if (!cid) {
        await createConversation()
      } else {
        await selectConversation(cid)
      }
    } finally {
      isInitializing.value = false
      autoResize()
      scrollToBottom()
    }
  }

  const refreshAuthAndMaybeSwitch = async () => {
    const me = await fetchMe()
    const nextUid = String(me?.userid || '')
    const prevUid = String(authUser.value?.userid || '')
    if (nextUid !== prevUid) {
      authUser.value = me
      await initChat({ skipFetchMe: true })
    }
  }

  await initChat()

  const onFocus = () => refreshAuthAndMaybeSwitch()
  const onVis = () => {
    if (document.visibilityState === 'visible') refreshAuthAndMaybeSwitch()
  }

  window.addEventListener('focus', onFocus)
  document.addEventListener('visibilitychange', onVis)

  authPollTimer = setInterval(() => {
    refreshAuthAndMaybeSwitch()
  }, 8000)
})
</script>

<style scoped>
.kbchat {
  height: calc(100vh - 110px);
  min-height: 520px;
  position: relative;
  display: flex;
  flex-direction: row;
  border-radius: 14px;
  overflow: hidden;
  background: #ffffff;
  border: 1px solid var(--color-border, #ebeef5);
}

.kbchat__skeleton {
  background: linear-gradient(90deg, #f3f4f6 0%, #e5e7eb 45%, #f3f4f6 100%);
  background-size: 200% 100%;
  animation: kbchat-skeleton 1.1s ease-in-out infinite;
}

@keyframes kbchat-skeleton {
  0% {
    background-position: 0% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

.kbchat__skeletonLine {
  height: 10px;
  border-radius: 999px;
}

.kbchat__skeletonAvatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
}

.kbchat__convSkeleton {
  display: grid;
  gap: 10px;
}

.kbchat__convSkeletonItem {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 12px;
  padding: 10px;
}

.kbchat__convSkeletonTitle {
  width: 72%;
}

.kbchat__convSkeletonMeta {
  width: 46%;
  margin-top: 8px;
}

.kbchat__msgSkeleton {
  display: grid;
  gap: 14px;
  padding-top: 6px;
}

.kbchat__msgSkeletonRow {
  display: grid;
  grid-template-columns: 34px 1fr;
  gap: 12px;
  align-items: start;
}

.kbchat__msgSkeletonBubble {
  padding-top: 4px;
}

.kbchat__msgSkeletonLine1 {
  width: 68%;
}

.kbchat__msgSkeletonLine2 {
  width: 48%;
  margin-top: 10px;
}

.kbchat__sidebar {
  width: 260px;
  border-right: 1px solid #e5e7eb;
  background: #fcfcfd;
  display: flex;
  flex-direction: column;
}

.kbchat__sidebar.collapsed {
  width: 56px;
}

.kbchat__sidebarHeader {
  padding: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.kbchat__sidebar.collapsed .kbchat__sidebarHeader {
  padding: 10px 8px;
  justify-content: center;
}

.kbchat__sidebar.collapsed .kbchat__sidebarActions {
  flex-direction: column;
  gap: 8px;
}

.kbchat__sidebarActions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.kbchat__collapse {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 10px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
}

.kbchat__sidebar.collapsed .kbchat__collapse,
.kbchat__sidebar.collapsed .kbchat__newChat {
  width: 40px;
  padding: 6px 0;
  text-align: center;
}

.kbchat__icon {
  width: 18px;
  height: 18px;
  display: inline-block;
  vertical-align: middle;
}

.kbchat__sidebarTitle {
  font-weight: 800;
  color: #111827;
}

.kbchat__newChat {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 10px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
}

.kbchat__convList {
  padding: 8px;
  overflow: auto;
  display: grid;
  gap: 8px;
}

.kbchat__convItem {
  text-align: left;
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 12px;
  padding: 10px;
  cursor: pointer;
}

.kbchat__convItem.active {
  border-color: #111827;
}

.kbchat__convTitle {
  font-size: 13px;
  font-weight: 700;
  color: #111827;
}

.kbchat__convMeta {
  margin-top: 4px;
  font-size: 12px;
  color: #6b7280;
}

.kbchat__viewport {
  position: relative;
  flex: 1 1 auto;
  overflow: auto;
}

.kbchat__main {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.kbchat__viewport {
  flex: 1 1 auto;
}

.kbchat__composer {
  flex: 0 0 auto;
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

.kbchat__emptyBrand {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin: 34px 0 22px;
}

.kbchat__emptyLogo {
  width: 220px;
  max-width: 62vw;
  height: auto;
  opacity: 0.95;
}

.kbchat__empty .kbchat__chips {
  max-width: 680px;
  margin-left: auto;
  margin-right: auto;
}

.kbchat__empty .kbchat__chip {
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
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

.kbchat__reasoning {
  margin: 0 0 8px;
  padding: 10px 12px;
  border: 1px dashed #e5e7eb;
  border-radius: 10px;
  background: #fafafa;
}

.kbchat__reasoningTitle {
  cursor: pointer;
  color: #334155;
  font-size: 12px;
  user-select: none;
}

.kbchat__reasoningText {
  margin-top: 8px;
  white-space: pre-wrap;
  color: #0f172a;
  font-size: 12px;
  line-height: 1.5;
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
