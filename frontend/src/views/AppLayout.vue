<template>
  <div class="app-page">
    <div class="app-layout" :style="layoutStyle">
      <aside class="sidebar" :class="{ collapsed }">
        <div class="sidebar-top">
          <div class="brand" :title="collapsed ? '产品手册自动化设计生成系统' : ''">
            <button class="brand-mark" type="button" @click="collapsed = !collapsed">
              <img class="brand-logo" :src="homeLogo" alt="logo" />
            </button>
            <div class="brand-text">
              <div class="brand-title">产品手册自动化设计生成系统</div>
            </div>
          </div>
        </div>

        <nav class="nav">
          <button class="nav-item" :class="{ active: activeKey === 'kbChat' }" @click="goHomeTab('kbChat')">
            <el-icon class="nav-icon"><ChatDotRound /></el-icon>
            <span class="nav-label">知识库问答</span>
          </button>
          <button class="nav-item" :class="{ active: activeKey === 'export' }" @click="goHomeTab('export')">
            <el-icon class="nav-icon"><Download /></el-icon>
            <span class="nav-label">产品手册编辑导出</span>
          </button>
        </nav>

        <div class="sidebar-mid">
          <button
            class="tool-item"
            :class="{ active: imagePanelOpen }"
            type="button"
            @mouseenter="onImageToolEnter"
            @mouseleave="onImageToolLeave"
            @click="onImageToolClick"
          >
            <el-icon class="nav-icon"><Picture /></el-icon>
            <span class="nav-label">上传图片</span>
          </button>
        </div>

        <div class="sidebar-bottom" :class="{ collapsed }">
          <div class="admin-entry" :class="{ collapsed }">
            <button class="admin-entry__btn" type="button" @click="goAdmin()">{{ adminLabel }}</button>
          </div>

          <div class="auth" :class="{ collapsed }">
            <div class="auth__dot" :class="authDotClass" />
            <div v-if="!collapsed" class="auth__text">
              <div class="auth__title">钉钉登录</div>
              <button v-if="authState === 'error'" class="auth__retry" type="button" @click="runDingTalkLogin()">重试</button>
              <div v-else class="auth__subtitle">{{ authSubtitle }}</div>
            </div>
          </div>
        </div>
      </aside>

      <main class="main">
        <router-view />
      </main>

      <div
        v-show="imagePanelOpen"
        class="imgpanel-popover"
        :class="{ pinned: imagePanelPinned }"
        @mouseenter="onImagePanelEnter"
        @mouseleave="onImagePanelLeave"
      >
        <div class="imgpanel-popover__inner">
          <ImageLibraryPanel
            :logged-in="authState === 'ok'"
            :pinned="imagePanelPinned"
            :opened="imagePanelOpen"
            @retry-login="runDingTalkLogin()"
            @interact="onImagePanelInteract"
          />
        </div>
      </div>
    </div>

    <el-dialog v-model="diagVisible" title="钉钉登录诊断" width="560px" append-to-body>
      <div class="diag">
        <div class="diag__row"><span class="diag__label">状态</span><span class="diag__value">{{ authSubtitle }}</span></div>
        <div class="diag__row"><span class="diag__label">失败步骤</span><span class="diag__value">{{ diagStep || '-' }}</span></div>
        <div class="diag__row"><span class="diag__label">API</span><span class="diag__value">{{ diagApiName || '-' }}</span></div>
        <div class="diag__row"><span class="diag__label">URL</span><span class="diag__value">{{ diagUrl || '-' }}</span></div>
        <div class="diag__row"><span class="diag__label">UA</span><span class="diag__value">{{ diagUa || '-' }}</span></div>
        <div class="diag__row"><span class="diag__label">错误</span><span class="diag__value">{{ diagError || '-' }}</span></div>
        <div class="diag__row"><span class="diag__label">js_config</span><span class="diag__value">{{ diagJsConfig || '-' }}</span></div>
      </div>
      <template #footer>
        <el-button @click="copyDiagnostics">复制诊断信息</el-button>
        <el-button type="primary" @click="runDingTalkLogin()">重试登录</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Download, ChatDotRound, Picture } from '@element-plus/icons-vue'
import homeLogo from '@/assets/logo.png'
import ImageLibraryPanel from '@/components/ImageLibraryPanel.vue'

const collapsed = ref(false)

const router = useRouter()
const route = useRoute()

const activeKey = computed(() => {
  const overrideKey = String(route.query?.moduleKey || '').trim()
  const metaKey = String(route.meta?.moduleKey || '').trim()
  const mk = overrideKey || metaKey
  if (mk === 'home') return String(route.query.tab || 'export')
  return mk
})

const goHomeTab = (tab) => {
  router.push({ path: '/', query: { tab } })
}

const goAdmin = () => {
  router.push({ path: '/admin' })
}

const adminLabel = computed(() => (collapsed.value ? '后台' : '产品后台管理'))

const layoutStyle = computed(() => ({
  '--sidebar-w': collapsed.value ? '72px' : '180px'
}))

const imagePanelOpen = ref(false)
const imagePanelPinned = ref(false)
const imageToolHover = ref(false)
const imagePanelHover = ref(false)
let imageCloseTimer = null

const isTouchDevice = () => {
  if (typeof window === 'undefined') return false
  const nav = window?.navigator
  const points = Number(nav?.maxTouchPoints || 0)
  return points > 0 || 'ontouchstart' in window
}

const cancelImageClose = () => {
  if (imageCloseTimer) {
    clearTimeout(imageCloseTimer)
    imageCloseTimer = null
  }
}

const scheduleImageClose = () => {
  if (imagePanelPinned.value) return
  cancelImageClose()
  imageCloseTimer = setTimeout(() => {
    if (!imageToolHover.value && !imagePanelHover.value && !imagePanelPinned.value) {
      imagePanelOpen.value = false
    }
  }, 200)
}

const onImageToolEnter = () => {
  if (isTouchDevice()) return
  imageToolHover.value = true
  cancelImageClose()
  imagePanelOpen.value = true
}

const onImageToolLeave = () => {
  if (isTouchDevice()) return
  imageToolHover.value = false
  scheduleImageClose()
}

const onImagePanelEnter = () => {
  if (isTouchDevice()) return
  imagePanelHover.value = true
  cancelImageClose()
}

const onImagePanelLeave = () => {
  if (isTouchDevice()) return
  imagePanelHover.value = false
  scheduleImageClose()
}

const onImageToolClick = () => {
  if (isTouchDevice()) {
    imagePanelPinned.value = false
    imagePanelOpen.value = !imagePanelOpen.value
    return
  }

  imagePanelPinned.value = !imagePanelPinned.value
  imagePanelOpen.value = true
  cancelImageClose()
}

const onImagePanelInteract = () => {
  if (!imagePanelOpen.value) imagePanelOpen.value = true
  if (!imagePanelPinned.value) imagePanelPinned.value = true
  cancelImageClose()
}

const authState = ref('idle')
const authUser = ref(null)
const authError = ref('')

const diagVisible = ref(false)
const diagStep = ref('')
const diagApiName = ref('')
const diagUrl = ref('')
const diagUa = ref('')
const diagError = ref('')
const diagJsConfig = ref('')

const authSubtitle = computed(() => {
  if (authState.value === 'ok') return authUser.value?.name || '已登录'
  if (authState.value === 'loading') return '登录中…'
  if (authState.value === 'unsupported') return '仅支持在钉钉内打开'
  if (authState.value === 'error') return authError.value || '登录失败'
  return '未登录'
})

const authDotClass = computed(() => {
  if (authState.value === 'ok') return 'ok'
  if (authState.value === 'loading') return 'loading'
  if (authState.value === 'error') return 'error'
  if (authState.value === 'unsupported') return 'muted'
  return 'muted'
})

const isInDingTalk = () => {
  const ua = String(navigator?.userAgent || '')
  return /DingTalk/i.test(ua)
}

const isMobileDingTalk = () => {
  const ua = String(navigator?.userAgent || '')
  if (!/DingTalk/i.test(ua)) return false
  return /Mobile|Android|iPhone|iPad|iPod|OpenHarmony|hmos/i.test(ua)
}

const getDingTalkApi = () => {
  const w = window
  if (isMobileDingTalk()) {
    return w?.dd || w?.DingTalkPC || null
  }
  return w?.DingTalkPC || w?.dd || null
}

const getDingTalkApiName = (dt) => {
  if (!dt) return ''
  const w = window
  if (w?.DingTalkPC && dt === w.DingTalkPC) return 'DingTalkPC'
  if (w?.dd && dt === w.dd) return 'dd'
  return 'unknown'
}

const fetchMe = async () => {
  const resp = await fetch('/api/auth/me', { credentials: 'include' })
  if (!resp.ok) return null
  const data = await resp.json()
  return data?.user || null
}

const withTimeout = (promise, ms, label) => {
  const timeoutMs = Number(ms || 0) > 0 ? Number(ms) : 10000
  return Promise.race([
    promise,
    new Promise((_, reject) => {
      const id = setTimeout(() => {
        clearTimeout(id)
        reject(new Error(`${label || 'operation'} timeout`))
      }, timeoutMs)
    }),
  ])
}

const stringifyErr = (e) => {
  try {
    if (!e) return ''
    if (typeof e === 'string') return e
    if (e?.message) return String(e.message)
    return JSON.stringify(e)
  } catch {
    return String(e)
  }
}

const openDiagnostics = (step, err, ctx = {}) => {
  diagStep.value = String(step || '')
  diagApiName.value = String(ctx.apiName || '')
  diagUrl.value = String(ctx.url || '')
  diagUa.value = String(navigator?.userAgent || '')
  diagError.value = stringifyErr(err)
  diagJsConfig.value = String(ctx.jsConfigSummary || '')
  diagVisible.value = true
}

const buildDiagnosticsText = () => {
  return [
    `status=${authState.value}`,
    `subtitle=${authSubtitle.value}`,
    `step=${diagStep.value}`,
    `api=${diagApiName.value}`,
    `url=${diagUrl.value}`,
    `ua=${diagUa.value}`,
    `error=${diagError.value}`,
    `js_config=${diagJsConfig.value}`,
  ].join('\n')
}

const copyDiagnostics = async () => {
  const text = buildDiagnosticsText()
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    try {
      const textarea = document.createElement('textarea')
      textarea.value = text
      textarea.style.position = 'fixed'
      textarea.style.top = '-1000px'
      document.body.appendChild(textarea)
      textarea.focus()
      textarea.select()
      document.execCommand('copy')
      document.body.removeChild(textarea)
    } catch {
      // ignore
    }
  }
}

const waitForConfig = (dt, config) =>
  new Promise((resolve, reject) => {
    try {
      dt.error((err) => reject(err))
      dt.ready(() => resolve(true))
      dt.config(config)
    } catch (e) {
      reject(e)
    }
  })

const requestAuthCode = (dt, corpId) =>
  new Promise((resolve, reject) => {
    try {
      dt.runtime.permission.requestAuthCode({
        corpId,
        onSuccess: (res) => resolve(res),
        onFail: (err) => reject(err),
      })
    } catch (e) {
      reject(e)
    }
  })

const runDingTalkLogin = async () => {
  if (authState.value === 'loading') return
  authError.value = ''
  authState.value = 'loading'

  try {
    diagStep.value = ''
    diagError.value = ''
    diagJsConfig.value = ''
    diagApiName.value = ''
    diagUrl.value = ''

    diagStep.value = 'me'
    const existing = await fetchMe()
    if (existing) {
      authUser.value = existing
      authState.value = 'ok'
      return
    }

    if (!isInDingTalk()) {
      authState.value = 'unsupported'
      return
    }

    const dt = getDingTalkApi()
    const apiName = getDingTalkApiName(dt)
    diagApiName.value = apiName
    if (!dt) {
      authState.value = 'error'
      authError.value = '未加载钉钉 JSAPI'
      openDiagnostics('init', authError.value, { apiName })
      return
    }

    const url = String(window.location.href || '').split('#')[0]
    diagUrl.value = url
    diagStep.value = 'js_config'
    const jsCfgResp = await fetch(`/api/auth/dingtalk/js_config?url=${encodeURIComponent(url)}`, {
      credentials: 'include',
    })
    if (!jsCfgResp.ok) {
      const txt = await jsCfgResp.text()
      throw new Error(txt || '获取 JSAPI 配置失败')
    }
    const jsCfg = await jsCfgResp.json()

    try {
      const jsCfgSummary = {
        corpId: jsCfg?.corpId,
        agentId: jsCfg?.agentId,
        timeStamp: jsCfg?.timeStamp,
        nonceStr: jsCfg?.nonceStr,
        signatureLen: String(jsCfg?.signature || '').length,
      }
      diagJsConfig.value = JSON.stringify(jsCfgSummary)
    } catch {
      diagJsConfig.value = ''
    }

    diagStep.value = 'dd.config'
    await withTimeout(
      waitForConfig(dt, {
        agentId: jsCfg.agentId,
        corpId: jsCfg.corpId,
        timeStamp: jsCfg.timeStamp,
        nonceStr: jsCfg.nonceStr,
        signature: jsCfg.signature,
        jsApiList: ['runtime.permission.requestAuthCode'],
      }),
      12000,
      'dd.config'
    )

    diagStep.value = 'requestAuthCode'
    const codeRes = await withTimeout(requestAuthCode(dt, jsCfg.corpId), 12000, 'requestAuthCode')
    const authCode = String(codeRes?.code || codeRes?.authCode || '').trim()
    if (!authCode) throw new Error('未获取到 authCode')

    diagStep.value = 'login'
    const loginResp = await fetch('/api/auth/dingtalk/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ authCode }),
    })
    if (!loginResp.ok) {
      const txt = await loginResp.text()
      throw new Error(txt || '登录失败')
    }

    diagStep.value = 'me'
    const me = await fetchMe()
    if (!me) throw new Error('登录成功但会话未生效')
    authUser.value = me
    authState.value = 'ok'
  } catch (e) {
    authState.value = 'error'
    authError.value = e?.message || String(e)
    openDiagnostics(diagStep.value || 'unknown', e, {
      apiName: diagApiName.value,
      url: diagUrl.value,
      jsConfigSummary: diagJsConfig.value,
    })
  }
}

onMounted(() => {
  runDingTalkLogin()
})
</script>

<style scoped>
.app-page {
  width: 100%;
  min-height: 100vh;
  padding: 0;
  background: #f6f7fb;
}

/* Hide scrollbars globally while keeping scroll behavior */
:global(html),
:global(body) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

:global(html::-webkit-scrollbar),
:global(body::-webkit-scrollbar) {
  width: 0;
  height: 0;
}

/* Element Plus dialog / scrollbar wrappers are teleported to body */
:global(.el-overlay *),
:global(.el-dialog__body *),
:global(.el-scrollbar__wrap) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

:global(.el-overlay *::-webkit-scrollbar),
:global(.el-dialog__body *::-webkit-scrollbar),
:global(.el-scrollbar__wrap::-webkit-scrollbar) {
  width: 0;
  height: 0;
  display: none;
}

.app-layout {
  display: flex;
  height: 100vh;
  position: relative;
}

.sidebar {
  width: 180px;
  flex: 0 0 180px;
  background: #ffffff;
  border-right: 1px solid var(--color-border);
  padding: 14px 12px;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  transition: width 160ms ease, flex-basis 160ms ease;
}

.auth {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border: 1px solid #eef2f7;
  border-radius: 12px;
  background: #fbfdff;
}

.auth.collapsed {
  justify-content: center;
  padding: 10px 0;
}

.auth__dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #9ca3af;
  flex: 0 0 auto;
}

.auth__dot.ok {
  background: #22c55e;
}

.auth__dot.loading {
  background: #f59e0b;
}

.auth__dot.error {
  background: #ef4444;
}

.auth__dot.muted {
  background: #9ca3af;
}

.auth__text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auth__title {
  font-size: 12px;
  font-weight: 700;
  color: #111827;
}

.auth__subtitle {
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 150px;
}

.auth__retry {
  appearance: none;
  border: 0;
  background: transparent;
  padding: 0;
  font-size: 12px;
  font-weight: 600;
  color: #2563eb;
  cursor: pointer;
  text-align: left;
}

.auth__retry:hover {
  text-decoration: underline;
}

.sidebar-bottom {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.admin-entry {
  padding: 0;
}

.admin-entry.collapsed {
  padding: 0;
}

.admin-entry__btn {
  width: 100%;
  border: 1px solid rgba(37, 99, 235, 0.35);
  background: rgba(37, 99, 235, 0.06);
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
  padding: 9px 10px;
  border-radius: 10px;
  cursor: pointer;
}

.admin-entry__btn:hover {
  background: rgba(37, 99, 235, 0.1);
}

.diag {
  display: grid;
  gap: 10px;
  padding: 4px 2px;
}

.diag__row {
  display: grid;
  grid-template-columns: 92px 1fr;
  gap: 10px;
  align-items: start;
}

.diag__label {
  font-size: 12px;
  color: #6b7280;
}

.diag__value {
  font-size: 12px;
  color: #111827;
  word-break: break-word;
  white-space: pre-wrap;
}

.sidebar.collapsed {
  width: 72px;
  flex-basis: 72px;
}

.sidebar-top {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.sidebar.collapsed .brand {
  gap: 0;
}

.brand-mark {
  appearance: none;
  border: 0;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  cursor: pointer;
}

.brand-logo {
  width: 32px;
  height: 32px;
  object-fit: contain;
  display: block;
}

.brand-mark:focus-visible {
  outline: 2px solid #93c5fd;
  outline-offset: 2px;
}

.brand-text {
  display: grid;
  gap: 2px;
  min-width: 0;
  overflow: hidden;
  transition: opacity 120ms ease, max-width 160ms ease;
  max-width: 220px;
  max-height: 44px;
  transition-property: opacity, max-width, max-height;
}

.brand-title {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
  line-height: 1.2;
}

.nav {
  display: grid;
  gap: 6px;
}

.sidebar-mid {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px 0;
}

.tool-item {
  appearance: none;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 12px;
  padding: 10px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  color: #111827;
}

.tool-item:hover {
  background: #f3f4f6;
}

.tool-item.active {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.imgpanel-popover {
  position: fixed;
  top: 14px;
  left: calc(var(--sidebar-w, 180px) + 12px);
  width: 320px;
  height: calc(100vh - 28px);
  z-index: 50;
}

.imgpanel-popover__inner {
  width: 100%;
  height: 100%;
  border-radius: 14px;
  border: 1px solid #e5e7eb;
  background: #ffffff;
  box-shadow: 0 18px 48px rgba(17, 24, 39, 0.14);
  overflow: hidden;
}

.nav-item {
  appearance: none;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 12px;
  padding: 10px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  text-align: left;
  width: 100%;
  color: #111827;
}

.nav-item:hover {
  background: #f3f4f6;
}

.nav-item.active {
  background: #eff6ff;
  border-color: #bfdbfe;
  color: #1d4ed8;
}

.nav-icon {
  font-size: 18px;
  flex: 0 0 auto;
}

.nav-label {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition: opacity 120ms ease, max-width 160ms ease;
  max-width: 160px;
}

.sidebar.collapsed .brand-text {
  opacity: 0;
  max-width: 0;
  max-height: 0;
  pointer-events: none;
}

.sidebar.collapsed .nav-label {
  opacity: 0;
  max-width: 0;
  pointer-events: none;
}

.sidebar:not(.collapsed) .brand-text,
.sidebar:not(.collapsed) .nav-label {
  transition-delay: 120ms;
}

.sidebar.collapsed .brand-text,
.sidebar.collapsed .nav-label {
  transition-delay: 0ms;
}

.main {
  flex: 1 1 auto;
  min-width: 0;
  height: 100vh;
  overflow: auto;
  padding: 18px 18px 24px;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.main::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}

/* Hide scrollbars for any scrollable descendants inside main */
.main :deep(*),
.main :deep(*::before),
.main :deep(*::after) {
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.main :deep(*::-webkit-scrollbar) {
  width: 0;
  height: 0;
  display: none;
}

@media (max-width: 1100px) {
  .sidebar {
    width: 72px;
    flex-basis: 72px;
  }
}
</style>
