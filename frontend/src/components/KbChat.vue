<template>
  <div class="kbchat">
    <div class="kbchat__viewport" ref="viewportRef" @scroll="handleScroll">
      <div class="kbchat__container">
        <div v-if="!messages.length" class="kbchat__empty">
          <div class="kbchat__chips">
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
import { computed, nextTick, onMounted, ref } from 'vue'

const viewportRef = ref(null)
const textareaRef = ref(null)

const draft = ref('')
const messages = ref([])
const showScrollToBottom = ref(false)

const suggestedQuestions = [
  '这款产品支持哪些配件？',
  '请总结安装步骤',
  '给我一段产品亮点介绍',
  '有哪些注意事项？'
]

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

const handleSend = async () => {
  const text = draft.value.trim()
  if (!text) return

  const now = Date.now()
  messages.value.push({ id: `u-${now}`, role: 'user', content: text, status: 'done' })
  draft.value = ''
  await nextTick()
  autoResize()

  const typingId = `a-${now}`
  messages.value.push({ id: typingId, role: 'assistant', content: '正在思考…', status: 'typing' })
  await scrollToBottom()

  setTimeout(async () => {
    const idx = messages.value.findIndex((m) => m.id === typingId)
    if (idx !== -1) {
      messages.value[idx] = {
        id: typingId,
        role: 'assistant',
        status: 'done',
        content: '（UI 占位）我已收到你的问题。待接入知识库接口后，这里会返回基于资料的回答。'
      }
    }
    await scrollToBottom()
  }, 600)
}

onMounted(() => {
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
  line-height: 1.7;
  color: #111827;
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
