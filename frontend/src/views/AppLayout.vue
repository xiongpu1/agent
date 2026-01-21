<template>
  <div class="app-page">
    <div class="app-layout">
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
          <button class="nav-item" :class="{ active: activeKey === 'upload' }" @click="goHomeTab('upload')">
            <el-icon class="nav-icon"><Upload /></el-icon>
            <span class="nav-label">上传图片</span>
          </button>
          <button class="nav-item" :class="{ active: activeKey === 'kbSearch' }" @click="goHomeTab('kbSearch')">
            <el-icon class="nav-icon"><Search /></el-icon>
            <span class="nav-label">产品知识库</span>
          </button>
          <button class="nav-item" :class="{ active: activeKey === 'kbChat' }" @click="goHomeTab('kbChat')">
            <el-icon class="nav-icon"><ChatDotRound /></el-icon>
            <span class="nav-label">知识库问答</span>
          </button>
          <button class="nav-item" :class="{ active: activeKey === 'manual' }" @click="goHomeTab('manual')">
            <el-icon class="nav-icon"><Notebook /></el-icon>
            <span class="nav-label">生成产品手册</span>
          </button>
          <button class="nav-item" :class="{ active: activeKey === 'export' }" @click="goHomeTab('export')">
            <el-icon class="nav-icon"><Download /></el-icon>
            <span class="nav-label">导出编辑器</span>
          </button>
        </nav>
      </aside>

      <main class="main">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Upload, Notebook, Search, Download, ChatDotRound } from '@element-plus/icons-vue'
import homeLogo from '@/assets/logo.png'

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
