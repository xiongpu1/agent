<template>
  <div class="page">
    <div class="topbar">
      <el-button class="back-btn" link @click="goBack">← 返回</el-button>
      <div class="title">文件OCR结果</div>
      <div class="spacer" />
      <el-button text :disabled="!hasData" :loading="promptReverseLoading" @click="handlePromptReverse">图片提示词反推</el-button>
      <el-button text :disabled="!hasData" :loading="ocrLoading" @click="handleManualOcr">文件OCR</el-button>
      <el-button type="primary" :disabled="!hasData" @click="startOcr">生成产品手册</el-button>
    </div>

    <el-alert
      v-if="!hasData"
      title="请在首页上传产品与配件文件后再进入此页面"
      type="warning"
      show-icon
      class="alert"
    />
    <el-alert
      v-else-if="sessionError"
      :title="sessionError"
      type="error"
      show-icon
      class="alert"
      :closable="false"
    />

    <div v-else class="files-board">
      <div class="summary-card">
        <div class="summary-title">当前产品</div>
        <div class="summary-name">{{ manualData.productName }}</div>
        <div class="summary-bom" v-if="manualData.bomCode">
          <span class="summary-bom-label">BOM 号：</span>
          <span class="summary-bom-value">{{ manualData.bomCode }}</span>
        </div>
        <div class="summary-sub">共 {{ productFiles.length }} 个产品文件，{{ accessoryFiles.length }} 个配件文件</div>
      </div>
      <transition name="fade">
        <el-card v-if="ocrProgress.visible" shadow="hover" class="ocr-progress-card">
          <div class="progress-header">
            <div>
              <div class="progress-title">{{ ocrProgress.stage }}</div>
              <div class="progress-detail">{{ ocrProgress.detail }}</div>
            </div>
            <el-tag v-if="ocrProgress.currentFile" type="info" round>
              {{ ocrProgress.currentFile }}
            </el-tag>
          </div>
          <el-progress
            :percentage="ocrProgress.percent"
            :status="ocrProgress.status"
            :stroke-width="12"
            striped
            :striped-flow="ocrProgress.status === 'active'"
            color="#409EFF"
          />
        </el-card>
      </transition>
      <el-alert
        v-if="ocrError"
        type="error"
        show-icon
        class="ocr-alert"
        :closable="false"
        :title="ocrError"
      />

      <div class="paired-row">
        <div class="file-panel">
          <div class="file-panel-header">
            <div>
              <div class="panel-title">产品原始文件</div>
              <div class="panel-sub">来自上传的产品资料</div>
              <div class="panel-path">存储路径：{{ storagePaths.productOriginal }}</div>
            </div>
            <el-tag type="info" effect="plain">{{ productFiles.length }} 个文件</el-tag>
          </div>
          <div class="panel-body">
            <el-empty v-if="!productFiles.length" description="暂无关联文件" />
            <div v-else class="simple-doc-list scrollable">
              <div v-for="file in productFiles" :key="file.id" class="simple-doc-item">
                <div class="doc-name-row">
                  <span class="doc-name">{{ file.name }}</span>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    @click="handleOriginalFileClick(file)"
                  >查看</el-button>
                </div>
                <div class="doc-subtle">
                  {{ formatSize(file.size) }} · {{ file.type || '未知类型' }}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="file-panel ocr-panel">
          <div class="file-panel-header">
            <div>
              <div class="panel-title">产品 OCR 文件</div>
              <div class="panel-sub">OCR 结果，可编辑 / 导出</div>
              <div class="panel-path">存储路径：{{ storagePaths.productOcr }}</div>
            </div>
            <el-tag type="success" effect="plain">{{ productOcrCount }} 个文件</el-tag>
          </div>
          <div class="panel-body">
            <el-empty v-if="!productOcrGroups.length" description="暂无关联文件" />
            <div v-else class="ocr-summary-list scrollable">
              <div v-for="group in productOcrGroups" :key="group.id" class="ocr-summary-item">
                <div>
                  <div class="group-title">{{ group.sourceName }}</div>
                  <div class="group-subtle">{{ formatSize(group.sourceSize) }} · {{ group.sourceMime }}</div>
                </div>
                <div class="ocr-summary-meta">
                  <el-tag type="info" effect="plain">{{ group.pages.length }} 页</el-tag>
                  <el-button size="small" text type="primary" @click="openOcrModal('product', group)">查看详情</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="paired-row">
        <div class="file-panel">
          <div class="file-panel-header">
            <div>
              <div class="panel-title">配件原始文件</div>
              <div class="panel-sub">来自上传的配件资料</div>
              <div class="panel-path">存储路径：{{ storagePaths.accessoryOriginal }}</div>
            </div>
            <el-tag type="info" effect="plain">{{ accessoryFiles.length }} 个文件</el-tag>
          </div>
          <div class="panel-body">
            <el-empty v-if="!accessoryFiles.length" description="暂无关联文件" />
            <div v-else class="simple-doc-list scrollable">
              <div v-for="file in accessoryFiles" :key="file.id" class="simple-doc-item">
                <div class="doc-name-row">
                  <span class="doc-name">{{ file.name }}</span>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    @click="handleOriginalFileClick(file)"
                  >查看</el-button>
                </div>
                <div class="doc-subtle">
                  {{ formatSize(file.size) }} · {{ file.type || '未知类型' }}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="file-panel ocr-panel">
          <div class="file-panel-header">
            <div>
              <div class="panel-title">配件 OCR 文件</div>
              <div class="panel-sub">OCR 结果，可编辑 / 导出</div>
              <div class="panel-path">存储路径：{{ storagePaths.accessoryOcr }}</div>
            </div>
            <el-tag type="success" effect="plain">{{ accessoryOcrCount }} 个文件</el-tag>
          </div>
          <div class="panel-body">
            <el-empty v-if="!accessoryOcrGroups.length" description="暂无关联文件" />
            <div v-else class="ocr-summary-list scrollable">
              <div v-for="group in accessoryOcrGroups" :key="group.id" class="ocr-summary-item">
                <div>
                  <div class="group-title">{{ group.sourceName }}</div>
                  <div class="group-subtle">{{ formatSize(group.sourceSize) }} · {{ group.sourceMime }}</div>
                </div>
                <div class="ocr-summary-meta">
                  <el-tag type="info" effect="plain">{{ group.pages.length }} 页</el-tag>
                  <el-button size="small" text type="primary" @click="openOcrModal('accessory', group)">查看详情</el-button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="ocrModal.visible"
      :title="ocrModalTitle"
      width="860px"
      class="ocr-detail-dialog"
      @close="closeOcrModal"
    >
      <div v-if="ocrModal.group" class="ocr-modal-content">
        <div class="ocr-modal-header">
          <div>
            <div class="modal-group-name">{{ ocrModal.group.sourceName }}</div>
            <div class="modal-group-subtle">
              {{ formatSize(ocrModal.group.sourceSize) }} · {{ ocrModal.group.sourceMime }} · 共 {{ ocrModalPages.length }} 页
            </div>
          </div>
        </div>

        <div v-if="selectedPage" class="ocr-modal-body">
          <div class="page-meta">
            <div>
              <div class="page-title">第 {{ selectedPage.pageNumber ?? selectedPageIndex + 1 }} 页</div>
              <div v-if="selectedPage.imageStem" class="page-subtle">{{ selectedPage.imageStem }}</div>
            </div>
            <el-tag type="info" effect="plain">{{ selectedPage.artifacts.length }} 个文件</el-tag>
          </div>

          <div class="artifact-section" v-if="selectedPage.artifacts.length">
            <div class="artifact-selector">
              <span>选择该页文件：</span>
              <el-select
                v-model="selectedArtifactId"
                placeholder="请选择文件"
                size="small"
                class="artifact-select"
              >
                <el-option
                  v-for="artifact in selectedPage.artifacts"
                  :key="artifact.id"
                  :label="artifact.name || formatKindLabel(artifact.kind)"
                  :value="artifact.id"
                >
                  <div class="artifact-option">
                    <span>{{ formatKindLabel(artifact.kind) }}</span>
                    <strong>{{ artifact.name }}</strong>
                    <em>{{ formatSize(artifact.size) }}</em>
                  </div>
                </el-option>
              </el-select>
            </div>
          </div>
          <el-empty v-else description="该页没有生成文件" />

          <div v-if="selectedArtifact" class="artifact-preview-panel">
            <div class="artifact-preview-header">
              <div>
                <div class="preview-title">{{ selectedArtifact.name || '未命名文件' }}</div>
                <div class="preview-subtle">
                  {{ formatKindLabel(selectedArtifact.kind) }} · {{ formatSize(selectedArtifact.size) }}
                </div>
              </div>
              <div class="artifact-actions">
                <el-button
                  v-if="isSelectedArtifactText"
                  text
                  type="primary"
                  :loading="artifactActionLoading.editing"
                  @click="handleEditArtifact"
                >
                  编辑
                </el-button>
                <el-button
                  v-if="isSelectedArtifactText"
                  text
                  type="danger"
                  :loading="artifactActionLoading.deleting"
                  @click="handleDeleteArtifact"
                >
                  删除
                </el-button>
                <el-button v-if="selectedArtifact.url" text type="primary" @click="downloadSelectedArtifact">
                  下载
                </el-button>
              </div>
            </div>
            <div class="artifact-preview-body">
              <template v-if="isSelectedArtifactImage">
                <img :src="selectedArtifact.url" :alt="selectedArtifact.name || '预览'" />
              </template>
              <template v-else-if="isSelectedArtifactText">
                <div class="artifact-text-panel">
                  <div v-if="artifactContent.loading" class="artifact-preview-fallback">内容加载中...</div>
                  <div v-else-if="artifactContent.error" class="artifact-preview-fallback">{{ artifactContent.error }}</div>
                  <pre v-else class="artifact-text">{{ artifactContent.text }}</pre>
                </div>
              </template>
              <template v-else-if="selectedArtifact.url">
                <iframe :src="selectedArtifact.url" frameborder="0" />
              </template>
              <div v-else class="artifact-preview-fallback">暂无可预览内容</div>
            </div>
          </div>
          <el-empty v-else description="请选择要预览的文件" />
        </div>
        <el-empty v-else description="暂无页面数据" />

        <div v-if="ocrModalPages.length" class="ocr-page-pagination">
          <el-pagination
            small
            background
            layout="prev, pager, next"
            :page-size="1"
            :total="ocrModalPages.length"
            :current-page="selectedPageIndex + 1"
            @current-change="handlePageChange"
          />
          <div class="page-selector">
            <span>跳转至</span>
            <el-select v-model="pageSelectValue" size="small" @change="handlePageSelect">
              <el-option
                v-for="(page, idx) in ocrModalPages"
                :key="page.id"
                :label="`第 ${page.pageNumber ?? idx + 1} 页`"
                :value="idx"
              />
            </el-select>
            <span>页</span>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  useManualStore,
  clearManualData,
  setManualData,
  setManualOcrResults,
  setManualSession,
  setManualOcrProgress
} from '@/stores/manualStore'
import { runManualOcrSession, getManualOcrProgress, getManualSession, updateDocument, deleteDocument } from '@/services/api'
import { BOM_CONFIG } from '@/constants/bomOptions'

const route = useRoute()
const router = useRouter()
const manualData = useManualStore()

onMounted(async () => {
  // 兼容不同入口：store / query / params 都尝试获取 sessionId
  const initialSessionId =
    manualData.sessionId ||
    route.query.sessionId ||
    route.params.sessionId ||
    route.params.id ||
    route.query.id

  if (initialSessionId) {
    setManualSession(initialSessionId)
    if (!manualData.bomType && (route.query.bomType || route.params.bomType)) {
      manualData.bomType = route.query.bomType || route.params.bomType
    }
    await loadSession(initialSessionId)
    if (autoRunOcrAndPromptReverseOnEnter.value) {
      await runAutoOcrAndPromptReverse(initialSessionId)
    }
    return
  }

  // 没有会话且没有上传文件，直接返回首页并提示
  const hasLocalFiles =
    (manualData.productFiles && manualData.productFiles.length) ||
    (manualData.accessoryFiles && manualData.accessoryFiles.length)
  if (!hasLocalFiles) {
    ElMessage.warning('请在首页上传产品/配件文件并创建 OCR 会话后再进入此页')
    router.replace({ name: 'Home', query: { tab: 'manual' } })
  }
})

const computeTotalDigits = (sections = []) =>
  sections.reduce((sum, section) => {
    if (Array.isArray(section.children) && section.children.length) {
      return sum + section.children.reduce((childSum, child) => childSum + (child.digits || 0), 0)
    }
    return sum + (section.digits || 0)
  }, 0)

const deriveBomTypeFromCode = (code = '') => {
  const normalized = String(code || '').replace(/\s+/g, '').toUpperCase()
  if (!normalized) return ''
  return Object.keys(BOM_CONFIG).find((type) => {
    const total = computeTotalDigits(BOM_CONFIG[type] || [])
    return total === normalized.length
  }) || ''
}

const productFiles = computed(() => manualData.productFiles || [])
const accessoryFiles = computed(() => manualData.accessoryFiles || [])
const productOcrFiles = computed(() => manualData.productOcrFiles || [])
const accessoryOcrFiles = computed(() => manualData.accessoryOcrFiles || [])
const productOcrGroups = computed(() => manualData.productOcrGroups || [])
const accessoryOcrGroups = computed(() => manualData.accessoryOcrGroups || [])
const countArtifacts = (groups = []) => {
  if (!Array.isArray(groups)) return 0
  return groups.reduce((sum, group) => {
    const pages = Array.isArray(group.pages) ? group.pages : []
    return sum + pages.reduce((pageSum, page) => pageSum + (page.artifacts?.length || 0), 0)
  }, 0)
}
const productOcrCount = computed(() => countArtifacts(productOcrGroups.value) || productOcrFiles.value.length)
const accessoryOcrCount = computed(() => countArtifacts(accessoryOcrGroups.value) || accessoryOcrFiles.value.length)
const storagePaths = computed(() => {
  const base = '/root/workspace/syp/agent/backend'
  if (!manualData.sessionId) {
    const waiting = '等待执行 OCR'
    return {
      productOriginal: waiting,
      accessoryOriginal: waiting,
      productOcr: waiting,
      accessoryOcr: waiting
    }
  }
  return {
    productOriginal: `${base}/manual_uploads/${manualData.sessionId}/products`,
    accessoryOriginal: `${base}/manual_uploads/${manualData.sessionId}/accessories`,
    productOcr: `${base}/manual_ocr_results/${manualData.sessionId}/products`,
    accessoryOcr: `${base}/manual_ocr_results/${manualData.sessionId}/accessories`
  }
})
const hasData = computed(() => Boolean(manualData.sessionId || (manualData.productName && productFiles.value.length)))
const ocrLoading = ref(false)
const ocrError = ref('')
const promptReverseLoading = ref(false)
const autoRunOcrAndPromptReverseOnEnter = ref(true)
const autoRunOcrAndPromptReverseKey = ref('')
const autoRunOcrAndPromptReverseRunning = ref(false)
const progressTimer = ref(null)
const progressHideTimer = ref(null)
const sessionLoading = ref(false)
const sessionError = ref('')
const rawProgress = computed(() => manualData.ocrProgress)
const ocrProgress = computed(() => {
  if (!rawProgress.value) {
    return {
      visible: false,
      stage: '',
      detail: '',
      percent: 0,
      status: 'active',
      currentFile: ''
    }
  }
  return {
    visible: true,
    stage: rawProgress.value.stage || '正在 OCR',
    detail: rawProgress.value.detail || '',
    percent: rawProgress.value.percent ?? 0,
    status: rawProgress.value.status || 'active',
    currentFile: rawProgress.value.current_file || rawProgress.value.currentFile || ''
  }
})

const goBack = () => {
  router.push({ name: 'Home', query: { tab: 'manual' } })
}

const startOcr = () => {
  if (!manualData.sessionId) {
    ElMessage.warning('当前缺少 OCR 会话，请先返回首页重新上传')
    return
  }

  router.push({
    path: '/manual/manual-detail',
    query: {
      sessionId: manualData.sessionId,
      productName: manualData.productName,
      bomType: manualData.bomType || route.query.bomType || ''
    }
  })
}

const normalizeOcrFiles = (files = [], prefix = 'ocr-file') => {
  if (!Array.isArray(files)) return []
  return files.map((file, index) => ({
    id: file.id || `${prefix}-${index}`,
    name: file.name || `${prefix}-${index + 1}`,
    size: file.size || 0,
    type: file.type || 'document',
    url: file.url || (file.path ? `/api/files/${file.path}` : ''),
    path: file.path || file.relative_path || '',
    summary: file.summary || '',
    text: file.text || file.raw_text || '',
    mime_type: file.mime_type || file.type || 'application/octet-stream',
    source: file.source || ''
  }))
}

const normalizeOcrGroups = (groups = []) => {
  if (!Array.isArray(groups)) return []
  return groups.map((group, index) => ({
    id: `${group.source_name || 'group'}-${index}`,
    sourceName: group.source_name || '未命名文件',
    sourceMime: group.source_mime || 'application/octet-stream',
    sourceSize: group.source_size || 0,
    pages: Array.isArray(group.pages)
      ? group.pages
          .map((page, pageIdx) => ({
            id: `${group.source_name || 'group'}-page-${pageIdx}`,
            pageNumber: page?.page_number,
            imageStem: page?.image_stem,
            artifacts: Array.isArray(page?.artifacts)
              ? page.artifacts.map((artifact, artIdx) => ({
                  id: `${page?.image_stem || 'artifact'}-${artIdx}`,
                  name: artifact?.name,
                  url: artifact?.url,
                  path: artifact?.path || '',
                  kind: artifact?.kind || 'file',
                  size: artifact?.size || 0,
                  mime: artifact?.type || 'application/octet-stream',
                  summary: artifact?.caption || '',
                  text: artifact?.text || artifact?.raw_text || '',
                  image_base64: artifact?.image_base64 || '',
                  parentDir: artifact?.parent_dir,
                }))
              : [],
          }))
          .sort((a, b) => {
            const pageA = a.pageNumber ?? Number.MAX_SAFE_INTEGER
            const pageB = b.pageNumber ?? Number.MAX_SAFE_INTEGER
            if (pageA !== pageB) return pageA - pageB
            return (a.imageStem || '').localeCompare(b.imageStem || '')
          })
      : [],
  }))
}

const buildFileUrl = (path = '') => {
  if (!path) return ''
  const normalized = String(path).replace(/^\/+/, '')
  return normalized ? `/api/files/${normalized}` : ''
}

const normalizeOriginalFiles = (files = [], prefix = 'original') => {
  if (!Array.isArray(files)) return []
  return files.map((file, index) => {
    const rawPath = file.path || file.relative_path || ''
    const url = file.url || buildFileUrl(rawPath)
    return {
      id: file.id || `${prefix}-${index}`,
      name: file.name || file.original_name || `文件 ${index + 1}`,
      size: file.size || file.file_size || 0,
      type: file.mime_type || file.type || 'document',
      path: rawPath,
      url,
      previewUrl: url,
      lastModified: file.last_modified || Date.now()
    }
  })
}

const loadSession = async (sessionId, { silent = false } = {}) => {
  if (!sessionId) return
  sessionLoading.value = true
  if (!silent) {
    sessionError.value = ''
  }
  try {
    const session = await getManualSession(sessionId)
    // 尝试同步最新进度；若后端无进度或已完成则清空前端残留
    let progressState = null
    try {
      progressState = await getManualOcrProgress(sessionId)
    } catch (e) {
      progressState = null
    }

    if (progressState && !['success', 'exception'].includes(progressState.status || '')) {
      setManualOcrProgress({ ...progressState, visible: true })
    } else {
      setManualOcrProgress(null)
      stopProgressPolling({ hide: true })
      ocrLoading.value = false
    }
    const normalizedProductFiles = normalizeOriginalFiles(session?.product_files, 'product-original')
    const normalizedAccessoryFiles = normalizeOriginalFiles(session?.accessory_files, 'accessory-original')
    const normalizedProductOcrFiles = normalizeOcrFiles(session?.product_ocr_files, 'product-ocr')
    const normalizedAccessoryOcrFiles = normalizeOcrFiles(session?.accessory_ocr_files, 'accessory-ocr')
    const normalizedProductOcrGroups = normalizeOcrGroups(session?.product_ocr_groups)
    const normalizedAccessoryOcrGroups = normalizeOcrGroups(session?.accessory_ocr_groups)

    setManualData({
      productName: session?.product_name || manualData.productName || '',
      bomCode: session?.bom_code || manualData.bomCode || '',
      bomType:
        session?.bom_type ||
        manualData.bomType ||
        route.query.bomType ||
        deriveBomTypeFromCode(session?.bom_code) ||
        '',
      productFiles: normalizedProductFiles,
      accessoryFiles: normalizedAccessoryFiles,
      productOcrFiles: normalizedProductOcrFiles,
      accessoryOcrFiles: normalizedAccessoryOcrFiles,
      productOcrGroups: normalizedProductOcrGroups,
      accessoryOcrGroups: normalizedAccessoryOcrGroups,
      sessionId: session?.session_id || sessionId,
      ocrProgress: manualData.ocrProgress
    })

    sessionError.value = ''
    if (!silent) {
      ElMessage.success('会话数据已加载')
    }
    // 只有在确实处于进行中时才轮询，否则会导致进度条残留
    if (progressState && !['success', 'exception'].includes(progressState.status || '')) {
      startProgressPolling()
    } else {
      stopProgressPolling({ hide: true })
      ocrLoading.value = false
    }
  } catch (error) {
    sessionError.value = error?.message || '加载 OCR 会话失败，请稍后重试'
    if (!silent) {
      ElMessage.error(sessionError.value)
    }
  } finally {
    sessionLoading.value = false
  }
}

const hasAnyOcrArtifacts = (groups = []) => {
  if (!Array.isArray(groups)) return false
  return groups.some((group) =>
    Array.isArray(group?.pages) &&
    group.pages.some((p) => Array.isArray(p?.artifacts) && p.artifacts.length)
  )
}

const hasAnyPromptReverseArtifacts = (groups = []) => {
  if (!Array.isArray(groups)) return false
  return groups.some((group) =>
    Array.isArray(group?.pages) &&
    group.pages.some((p) =>
      Array.isArray(p?.artifacts) &&
      p.artifacts.some((a) => String(a?.name || a?.path || '').toLowerCase().endsWith('.txt'))
    )
  )
}

const runAutoOcrAndPromptReverse = async (sessionId) => {
  if (!sessionId) return
  if (autoRunOcrAndPromptReverseRunning.value) return
  if (autoRunOcrAndPromptReverseKey.value === String(sessionId)) return

  autoRunOcrAndPromptReverseRunning.value = true
  try {
    let didRunOcr = false
    let didRunReverse = false

    const alreadyHasOcr =
      hasAnyOcrArtifacts(productOcrGroups.value) ||
      hasAnyOcrArtifacts(accessoryOcrGroups.value)

    if (!alreadyHasOcr) {
      ocrLoading.value = true
      ocrError.value = ''
      beginOcrProgressPlaceholder()
      startProgressPolling()
      await runManualOcrSession(String(sessionId))
      await loadSession(String(sessionId), { silent: true })
      didRunOcr = true
    }

    const alreadyHasReverse =
      hasAnyPromptReverseArtifacts(productOcrGroups.value) ||
      hasAnyPromptReverseArtifacts(accessoryOcrGroups.value)

    if (!alreadyHasReverse) {
      promptReverseLoading.value = true
      const { runPromptReverse, getManualSession } = await import('@/services/api')
      await runPromptReverse(String(sessionId))
      const updated = await getManualSession(String(sessionId))
      setManualOcrResults({
        productOcrGroups: normalizeOcrGroups(updated?.product_ocr_groups),
        accessoryOcrGroups: normalizeOcrGroups(updated?.accessory_ocr_groups),
        productOcrFiles: manualData.productOcrFiles,
        accessoryOcrFiles: manualData.accessoryOcrFiles
      })
      didRunReverse = true
    }

    autoRunOcrAndPromptReverseKey.value = String(sessionId)
    if (didRunOcr || didRunReverse) {
      await ElMessageBox.alert('OCR 与图片提示词反推已完成。', '处理成功', {
        type: 'success',
        confirmButtonText: '知道了',
        closeOnClickModal: false,
        closeOnPressEscape: false
      })
    }
  } catch (error) {
    console.error('Auto OCR / prompt reverse failed:', error)
    await ElMessageBox.alert(error?.message || '自动处理失败，请稍后重试', '处理失败', {
      type: 'error',
      confirmButtonText: '知道了',
      closeOnClickModal: false
    })
  } finally {
    autoRunOcrAndPromptReverseRunning.value = false
    ocrLoading.value = false
    promptReverseLoading.value = false
    stopProgressPolling({ hide: true })
  }
}

const clearProgressHideTimer = () => {
  if (progressHideTimer.value) {
    clearTimeout(progressHideTimer.value)
    progressHideTimer.value = null
  }
}

const stopProgressPolling = (options = { hide: false }) => {
  if (progressTimer.value) {
    clearInterval(progressTimer.value)
    progressTimer.value = null
  }
  if (options.hide) {
    clearProgressHideTimer()
  }
  if (options.hide) {
    setManualOcrProgress(null)
  }
}

const pollProgressOnce = async () => {
  if (!manualData.sessionId) return
  try {
    const state = await getManualOcrProgress(manualData.sessionId)
    // 后端重启后 progress 可能丢失（返回 null），此时直接关闭进度并刷新 session 结果
    if (!state) {
      if (ocrLoading.value) return
      stopProgressPolling({ hide: true })
      setManualOcrProgress(null)
      ocrLoading.value = false
      await loadSession(manualData.sessionId, { silent: true })
      return
    }
    setManualOcrProgress({ ...state, visible: true })
    if (['success', 'exception'].includes(state.status)) {
      stopProgressPolling({ hide: true })
      setManualOcrProgress(null)
      ocrLoading.value = false
      await loadSession(manualData.sessionId, { silent: true })
    }
  } catch (error) {
    // Ignore not found errors before backend initializes
  }
}

const startProgressPolling = () => {
  if (!manualData.sessionId) return
  stopProgressPolling()
  pollProgressOnce()
  progressTimer.value = window.setInterval(pollProgressOnce, 2000)
}

const beginOcrProgressPlaceholder = () => {
  setManualOcrProgress({
    visible: true,
    stage: '正在 OCR',
    detail: '任务已提交，等待后端进度…',
    percent: 5,
    status: 'active',
    current_file: '',
    currentFile: ''
  })
}

const handleManualOcr = async () => {
  if (!manualData.sessionId || ocrLoading.value) return
  ocrLoading.value = true
  ocrError.value = ''
  beginOcrProgressPlaceholder()
  startProgressPolling()
  ElMessage.info('已触发 OCR，稍后自动刷新结果')
  try {
    await runManualOcrSession(manualData.sessionId)
    ElMessage.success('文件 OCR 已完成')
    stopProgressPolling({ hide: true })
    setManualOcrProgress(null)
    await loadSession(manualData.sessionId, { silent: true })
  } catch (error) {
    ocrError.value = error?.message || '文件 OCR 触发失败，请稍后重试'
    ElMessage.error(ocrError.value)
    stopProgressPolling({ hide: true })
  } finally {
    ocrLoading.value = false
  }
}

const handlePromptReverse = async () => {
  if (!manualData.sessionId) {
    ElMessage.warning('当前缺少 OCR 会话，请先返回首页重新上传')
    return
  }
  promptReverseLoading.value = true
  try {
    const { runPromptReverse, getManualSession } = await import('@/services/api')
    await runPromptReverse(manualData.sessionId)
    const updated = await getManualSession(manualData.sessionId)
    setManualOcrResults({
      productOcrGroups: normalizeOcrGroups(updated?.product_ocr_groups),
      accessoryOcrGroups: normalizeOcrGroups(updated?.accessory_ocr_groups),
      productOcrFiles: manualData.productOcrFiles,
      accessoryOcrFiles: manualData.accessoryOcrFiles
    })
    ElMessage.success('图片提示词反推完成')
  } catch (error) {
    console.error('Prompt reverse failed:', error)
    ElMessage.error(error?.message || '图片提示词反推失败，请稍后重试')
  } finally {
    promptReverseLoading.value = false
  }
}

const openOcrFile = (file) => {
  if (!file?.url) return
  window.open(file.url, '_blank')
}

const handleOriginalFileClick = (file) => {
  if (!file) return
  const resolvedUrl = file.url || file.previewUrl || (file.path ? `/api/files/${file.path}` : '')
  if (!resolvedUrl) return
  window.open(resolvedUrl, '_blank', 'noopener')
}

const formatSize = (size = 0) => {
  if (!size) return '未知大小'
  const units = ['B', 'KB', 'MB', 'GB']
  let idx = 0
  let val = size
  while (val >= 1024 && idx < units.length - 1) {
    val /= 1024
    idx++
  }
  return `${val.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`
}

const ocrModal = reactive({
  visible: false,
  type: 'product',
  group: null
})

const ocrModalPages = computed(() => (ocrModal.group?.pages ? [...ocrModal.group.pages] : []))
const selectedPageIndex = ref(0)
const selectedArtifactId = ref('')
const pageSelectValue = ref(0)

const ocrModalTitle = computed(() => {
  const prefix = ocrModal.type === 'accessory' ? '配件' : '产品'
  const name = ocrModal.group?.sourceName ? ` - ${ocrModal.group.sourceName}` : ''
  return `${prefix} OCR 详情${name}`
})

const selectedPage = computed(() => ocrModalPages.value[selectedPageIndex.value] || null)
const selectedArtifact = computed(() => {
  if (!selectedPage.value?.artifacts?.length) return null
  return selectedPage.value.artifacts.find((artifact) => artifact.id === selectedArtifactId.value) || null
})

const isArtifactTextLike = (artifact) => {
  if (!artifact) return false
  const kind = artifact.kind
  const mime = artifact.mime || ''
  const name = artifact.name || ''
  if (['markdown', 'diagram', 'json', 'text'].includes(kind)) return true
  if (mime.startsWith?.('text/')) return true
  if (['application/json', 'application/xml', 'application/vnd.mermaid+json'].includes(mime)) return true
  if (name.endsWith?.('.mmd') || name.endsWith?.('.md') || name.endsWith?.('.json')) return true
  return false
}

const isSelectedArtifactImage = computed(() => {
  if (!selectedArtifact.value) return false
  return (
    selectedArtifact.value.kind === 'image' ||
    selectedArtifact.value.mime?.startsWith?.('image/')
  )
})

const isSelectedArtifactText = computed(() => {
  if (!selectedArtifact.value) return false
  return !isSelectedArtifactImage.value && isArtifactTextLike(selectedArtifact.value)
})

const artifactContent = reactive({
  loading: false,
  text: '',
  error: ''
})
const artifactActionLoading = reactive({
  editing: false,
  deleting: false
})

let artifactContentToken = 0
watch(selectedArtifact, async (artifact) => {
  artifactContentToken += 1
  const token = artifactContentToken
  artifactContent.text = ''
  artifactContent.error = ''
  artifactContent.loading = false

  if (!artifact || !artifact.url) return
  if (isSelectedArtifactImage.value || !isArtifactTextLike(artifact)) return

  artifactContent.loading = true
  try {
    const response = await fetch(artifact.url)
    if (!response.ok) throw new Error('内容加载失败')
    const text = await response.text()
    if (artifactContentToken !== token) return
    artifactContent.text = text
  } catch (error) {
    if (artifactContentToken !== token) return
    artifactContent.error = error?.message || '内容加载失败'
  } finally {
    if (artifactContentToken === token) {
      artifactContent.loading = false
    }
  }
})

const selectArtifact = (artifactId) => {
  selectedArtifactId.value = artifactId
}

const handlePageChange = (pageNumber) => {
  const newIndex = pageNumber - 1
  if (newIndex < 0 || newIndex >= ocrModalPages.value.length) return
  selectedPageIndex.value = newIndex
  pageSelectValue.value = newIndex
  selectedArtifactId.value = ocrModalPages.value[newIndex]?.artifacts?.[0]?.id || ''
}

const handlePageSelect = (idx) => {
  handlePageChange(idx + 1)
}

const downloadSelectedArtifact = () => {
  if (!selectedArtifact.value?.url) return
  const link = document.createElement('a')
  link.href = selectedArtifact.value.url
  link.download = selectedArtifact.value.name || 'ocr-file'
  link.target = '_blank'
  link.rel = 'noopener'
  link.click()
}

const reloadSessionSilently = async () => {
  if (!manualData.sessionId) return
  await loadSession(manualData.sessionId, { silent: true })
}

const normalizeDocPath = (raw = '') =>
  raw
    .replace(/^https?:\/\/[^/]+\/api\/files\//, '')
    .replace(/^\/api\/files\//, '')
    .replace(/^backend\//, '')
    .replace(/^\/+/, '')

const handleEditArtifact = async () => {
  const artifact = selectedArtifact.value
  const docPath = normalizeDocPath(artifact?.path || '') || normalizeDocPath(artifact?.url || '')
  if (!docPath || artifactActionLoading.editing) return
  try {
    artifactActionLoading.editing = true
    // 确保有最新文本内容
    let content = artifactContent.text
    if (!content) {
      const resp = await fetch(artifact.url)
      content = await resp.text()
    }
    const { value, action } = await ElMessageBox.prompt('可编辑 OCR 文本内容：', '编辑文件', {
      inputType: 'textarea',
      inputValue: content,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputPlaceholder: '请输入新的文件内容',
      inputValidator: () => true,
      customClass: 'manual-edit-artifact-messagebox',
      draggable: true,
      closeOnClickModal: false
    })
    if (action !== 'confirm') return
    await updateDocument(docPath, { content: value })
    ElMessage.success('已保存')
    await reloadSessionSilently()
  } catch (error) {
    if (error?.action === 'cancel') return
    ElMessage.error(error?.message || '保存失败')
  } finally {
    artifactActionLoading.editing = false
  }
}

const handleDeleteArtifact = async () => {
  const artifact = selectedArtifact.value
  const docPath = normalizeDocPath(artifact?.path || '') || normalizeDocPath(artifact?.url || '')
  if (!docPath || artifactActionLoading.deleting) return
  try {
    await ElMessageBox.confirm(`确认删除文件「${artifact.name || artifact.path}」？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      closeOnClickModal: false
    })
    artifactActionLoading.deleting = true
    await deleteDocument(docPath)
    ElMessage.success('已删除')
    await reloadSessionSilently()
    selectedArtifactId.value = ''
  } catch (error) {
    if (error === 'cancel') return
    ElMessage.error(error?.message || '删除失败')
  } finally {
    artifactActionLoading.deleting = false
  }
}

const openOcrModal = (type, group) => {
  ocrModal.type = type
  ocrModal.group = group
  ocrModal.visible = true
  selectedPageIndex.value = 0
  pageSelectValue.value = 0
  selectedArtifactId.value = group?.pages?.[0]?.artifacts?.[0]?.id || ''
}

const closeOcrModal = () => {
  ocrModal.visible = false
  ocrModal.group = null
  selectedArtifactId.value = ''
  artifactContent.text = ''
  artifactContent.error = ''
  artifactContent.loading = false
}

const formatKindLabel = (kind) => {
  switch (kind) {
    case 'markdown':
      return 'Markdown'
    case 'diagram':
      return '结构图'
    case 'image':
      return '图片'
    case 'json':
      return 'JSON'
    default:
      return '文件'
  }
}

const handleBeforeLeave = () => {
  clearManualData()
  stopProgressPolling({ hide: true })
  clearProgressHideTimer()
}

onBeforeUnmount(() => {
  stopProgressPolling({ hide: true })
  clearProgressHideTimer()
})

const preserveManualReviewRoutes = new Set(['ProductManual'])

router.afterEach((to, from) => {
  if (from.name === 'ManualReview' && !preserveManualReviewRoutes.has(to.name)) {
    handleBeforeLeave()
  }
})

</script>

<style scoped>
.page {
  width: 100%;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title {
  font-weight: 700;
  font-size: 20px;
}
.spacer {
  flex: 1;
}
.alert {
  width: 100%;
}
.files-board {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.summary-card {
  background: #fff;
  border-radius: 12px;
  padding: 18px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
  display: grid;
  gap: 6px;
}
.ocr-progress-card {
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 6px 32px rgba(15, 23, 42, 0.12);
}
.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  gap: 12px;
}
.progress-title {
  font-weight: 600;
}
.progress-detail {
  font-size: 12px;
  color: #909399;
}
.summary-title {
  font-size: 14px;
  color: #888;
}
.summary-name {
  font-size: 20px;
  font-weight: 700;
}
.summary-bom {
  margin-top: 6px;
  display: flex;
  gap: 6px;
  font-size: 13px;
  color: #666;
}
.summary-bom-label {
  color: #999;
}
.summary-bom-value {
  font-weight: 600;
  color: #333;
}
.summary-sub {
  color: #666;
}
.paired-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(320px, 1fr));
  gap: 16px;
  align-items: stretch;
}
.file-panel {
  flex: 1;
  background: #fff;
  border-radius: 14px;
  padding: 18px;
  box-shadow: 0 6px 28px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.file-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.panel-title {
  font-weight: 600;
}
.panel-sub {
  font-size: 12px;
  color: #888;
}
.panel-path {
  font-size: 12px;
  color: #b1b6c2;
  margin-top: 4px;
  word-break: break-all;
}
.panel-body {
  flex: 1;
}
.simple-doc-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.simple-doc-list.scrollable {
  max-height: 420px;
  overflow: auto;
}
.simple-doc-item {
  padding: 12px;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  background: #fafbfd;
  display: grid;
  gap: 4px;
}
.doc-name-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.doc-name {
  font-weight: 600;
}
.doc-subtle {
  font-size: 12px;
  color: #909399;
}
.ocr-summary-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ocr-summary-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border: 1px solid #f0f2f5;
  border-radius: 12px;
  background: #fdfefe;
  gap: 16px;
}
.ocr-summary-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ocr-detail-dialog :deep(.el-dialog__body) {
  padding-top: 12px;
}
.ocr-modal-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 60vh;
}
.ocr-modal-header {
  border-bottom: 1px solid #f0f2f5;
  padding-bottom: 12px;
}
.modal-group-name {
  font-weight: 600;
  font-size: 16px;
}
.modal-group-subtle {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.ocr-modal-pages {
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ocr-modal-page {
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  padding: 12px 14px;
  background: #fff;
}
.ocr-detail-dialog :deep(.el-dialog__body) {
  padding-top: 12px;
}
.ocr-modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: 60vh;
  overflow: auto;
}
.page-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #eef2f7;
}
.page-title {
  font-weight: 600;
  font-size: 16px;
}
.page-subtle {
  font-size: 12px;
  color: #909399;
}
.artifact-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.artifact-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.artifact-select {
  min-width: 220px;
}
.artifact-list.selectable .artifact-item {
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease;
}
.artifact-list.selectable .artifact-item.active {
  border-color: #409eff;
  background: rgba(64, 158, 255, 0.08);
}
.artifact-preview-panel {
  border: 1px solid #eef2f7;
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: #fff;
  box-shadow: inset 0 1px 3px rgba(15, 23, 42, 0.04);
}
.artifact-preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.preview-title {
  font-weight: 600;
}
.preview-subtle {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.artifact-preview-panel .artifact-preview-body {
  min-height: 280px;
  border-radius: 12px;
  background: #f7f9fc;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.artifact-text-panel {
  width: 100%;
  height: 100%;
  overflow: auto;
  padding: 12px;
}
.artifact-text {
  white-space: pre-wrap;
  font-family: 'Fira Code', 'SFMono-Regular', Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #1f2937;
}
.artifact-preview-panel img {
  max-width: 100%;
  max-height: 50vh;
  object-fit: contain;
}
.artifact-preview-panel iframe {
  width: 100%;
  height: 50vh;
  background: #fff;
}
.artifact-preview-fallback {
  color: #909399;
}
.ocr-page-pagination {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.page-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.state {
  padding: 20px;
  text-align: center;
  color: #999;
}
.preview-body {
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.preview-body img {
  max-width: 100%;
  max-height: 60vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.15);
}
.preview-fallback {
  padding: 40px;
  text-align: center;
  color: #666;
}

:global(.manual-edit-artifact-messagebox) {
  width: min(1100px, 92vw) !important;
}

:global(.manual-edit-artifact-messagebox .el-textarea__inner) {
  min-height: 60vh!important;
}

:global(.manual-edit-artifact-messagebox .el-message-box__content) {
  max-height: 70vh;
  overflow: auto;
}

@media (max-width: 1024px) {
  .paired-row {
    grid-template-columns: 1fr;
  }
}
</style>
