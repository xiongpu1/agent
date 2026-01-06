<template>
  <div class="page">
    <div class="topbar">
      <el-button class="back-btn" link @click="goBack">← 返回</el-button>
      <div class="title">BOM 资料预览</div>
      <div class="spacer" />
      <el-button text @click="handleRefresh" :loading="loading" :disabled="!canLoad">刷新</el-button>
      <el-button type="primary" @click="goGenerate" :disabled="!canGenerate">生成产品手册</el-button>
    </div>

    <div class="product-summary">
      <img class="thumb" :src="imgUrl" :alt="displayName" @error="onImgError" />
      <div class="meta">
        <div class="name">{{ displayName }}</div>
        <div class="sub">产品：{{ productName || '未知' }}</div>
        <div class="sub">BOM：{{ bom || '未选择' }}</div>
      </div>
    </div>

    <el-alert
      v-if="!canLoad"
      title="缺少产品名称或 BOM 版本，无法获取资料"
      type="warning"
      show-icon
      class="alert"
    />

    <el-alert
      v-else-if="error"
      :title="error"
      type="error"
      show-icon
      class="alert"
    />

    <div v-if="canLoad" class="files-board">
      <div class="file-row">
        <div class="file-panel">
          <div class="file-panel-header">
            <div>
              <div class="panel-title">产品原始文件</div>
              <div class="panel-sub">手工上传并入库的原文件</div>
            </div>
            <el-button link type="primary" size="small" @click="loadProductDocs">刷新</el-button>
          </div>
          <div class="panel-body">
            <div v-if="productDocsLoading" class="state condensed">正在加载原始文件...</div>
            <div v-else-if="productDocsError" class="state error condensed">{{ productDocsError }}</div>
            <div v-else-if="manualProductUploads.length" class="simple-doc-list scrollable">
              <div v-for="doc in manualProductUploads" :key="doc.path" class="simple-doc-item">
                <div class="doc-name-row">
                  <span class="doc-name">{{ doc.name }}</span>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    @click="handleOriginalFileClick(doc)"
                  >查看</el-button>
                </div>
                <div class="doc-subtle" v-if="doc.summary">{{ doc.summary }}</div>
              </div>
            </div>
            <el-empty v-else description="暂无原始文件" />
          </div>
        </div>

        <div class="file-panel">
          <div class="file-panel-header">
            <div>
              <div class="panel-title">产品 OCR 文件</div>
              <div class="panel-sub">OCR 后内容，可编辑 / 删除</div>
            </div>
            <el-button link type="primary" size="small" @click="loadProductDocs">刷新</el-button>
          </div>
          <div class="panel-body">
            <div v-if="productDocsLoading" class="state condensed">正在加载...</div>
            <div v-else-if="productDocsError" class="state error condensed">{{ productDocsError }}</div>
            <template v-else>
              <el-empty v-if="!productOcrGroups.length" description="暂无关联文件" />
              <div v-else class="ocr-summary-list scrollable">
                <div v-for="group in productOcrGroups" :key="group.id" class="ocr-summary-item">
                  <div>
                    <div class="group-title">{{ group.sourceName }}</div>
                    <div class="group-subtle">{{ group.sourceMime }}</div>
                  </div>
                  <div class="ocr-summary-meta">
                    <el-tag type="info" effect="plain">{{ group.pages.length }} 页</el-tag>
                    <el-button size="small" text type="primary" @click="openOcrModal('product', group)">查看详情</el-button>
                  </div>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <div class="file-row">
        <div class="file-panel">
          <div class="file-panel-header">
            <div>
              <div class="panel-title">配件原始文件</div>
              <div class="panel-sub">手工上传并入库的配件原文件</div>
            </div>
            <el-select
              v-model="selectedAccessory"
              placeholder="选择配件"
              size="small"
              class="accessory-select"
              :disabled="accessoriesLoading || !accessories.length"
            >
              <el-option v-for="item in accessories" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
          <div class="panel-body">
            <div v-if="accessoriesLoading" class="state condensed">正在加载配件...</div>
            <div v-else-if="!accessories.length" class="state condensed">暂无配件信息</div>
            <div v-else-if="accessoryDocsLoading" class="state condensed">正在加载配件原始文件...</div>
            <div v-else-if="accessoryDocsError" class="state error condensed">{{ accessoryDocsError }}</div>
            <div v-else-if="manualAccessoryUploads.length" class="simple-doc-list scrollable">
              <div v-for="doc in manualAccessoryUploads" :key="doc.path" class="simple-doc-item">
                <div class="doc-name-row">
                  <span class="doc-name">{{ doc.name }}</span>
                  <el-button
                    link
                    type="primary"
                    size="small"
                    @click="handleOriginalFileClick(doc)"
                  >查看</el-button>
                </div>
                <div class="doc-subtle" v-if="doc.summary">{{ doc.summary }}</div>
              </div>
            </div>
            <el-empty v-else :description="selectedAccessory ? '暂无原始文件' : '请选择配件'" />
          </div>
        </div>

        <div class="file-panel">
          <div class="file-panel-header">
            <div>
              <div class="panel-title">配件相关文件</div>
              <div class="panel-sub">OCR 结果，可编辑 / 删除</div>
            </div>
            <div class="panel-actions">
              <el-select
                v-model="selectedAccessory"
                placeholder="选择配件"
                size="small"
                class="accessory-select"
                :disabled="accessoriesLoading || !accessories.length"
              >
                <el-option v-for="item in accessories" :key="item" :label="item" :value="item" />
              </el-select>
              <el-button link type="primary" size="small" :disabled="!selectedAccessory" @click="refreshAccessoryDocs">刷新</el-button>
            </div>
          </div>
          <div class="panel-body">
            <div v-if="!selectedAccessory" class="state condensed">请选择配件后查看相关文件</div>
            <div v-else-if="accessoryDocsLoading" class="state condensed">正在加载配件文件...</div>
            <div v-else-if="accessoryDocsError" class="state error condensed">{{ accessoryDocsError }}</div>
            <template v-else>
              <el-empty v-if="!accessoryOcrGroups.length" description="该配件暂无关联文件" />
              <div v-else class="ocr-summary-list scrollable">
                <div v-for="group in accessoryOcrGroups" :key="group.id" class="ocr-summary-item">
                  <div>
                    <div class="group-title">{{ group.sourceName }}</div>
                    <div class="group-subtle">{{ group.sourceMime }}</div>
                  </div>
                  <div class="ocr-summary-meta">
                    <el-tag type="info" effect="plain">{{ group.pages.length }} 页</el-tag>
                    <el-button size="small" text type="primary" @click="openOcrModal('accessory', group)">查看详情</el-button>
                  </div>
                </div>
              </div>
            </template>
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
              {{ ocrModal.group.sourceMime }} · 共 {{ ocrModalPages.length }} 页
            </div>
          </div>
        </div>

        <div v-if="selectedPage" class="ocr-modal-body">
          <div class="page-meta">
            <div>
              <div class="page-title">第 {{ selectedPage.pageNumber ?? selectedPageIndex + 1 }} 页</div>
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
                  {{ formatKindLabel(selectedArtifact.kind) }}
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

    <el-dialog v-model="editDialogVisible" title="编辑文件" width="680px" :close-on-click-modal="false">
      <div v-if="editLoading" class="state">正在加载文件内容...</div>
      <template v-else>
        <el-form label-width="96px" :model="editForm">
          <el-form-item label="文件名称">
            <el-input v-model="editForm.name" placeholder="请输入文件名（含后缀）" />
          </el-form-item>
          <el-form-item label="文件路径">
            <el-input v-model="editForm.path" disabled />
          </el-form-item>
          <el-form-item label="文件内容">
            <el-input
              v-model="editForm.content"
              type="textarea"
              :rows="12"
              placeholder="请输入 Markdown 文本"
            />
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="closeEditDialog">取消</el-button>
        <el-button type="primary" :loading="editLoading" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const encodePath = (path = '') =>
  path
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/')

const resolveFileUrl = (path) => {
  if (!path) return ''
  return `${API_BASE_URL}/api/files/${encodePath(path)}`
}

const route = useRoute()
const router = useRouter()

const id = computed(() => route.params.id)
const bom = computed(() => route.params.bom || route.query.bom || '')
const productName = computed(() => route.query.productName || '')
const displayName = computed(() => route.query.name || productName.value || `产品${id.value}`)
const image = computed(() => route.query.image || 'Alta.png')
const imgUrl = computed(() => `/product/${image.value}`)

const loading = ref(false)
const error = ref('')

const canLoad = computed(() => Boolean(productName.value && bom.value))
const canGenerate = computed(() => canLoad.value)

const onImgError = (e) => { e.target.src = '/favicon.ico' }

const productDocs = ref([])
const productDocsLoading = ref(false)
const productDocsError = ref('')
const accessories = ref([])
const accessoriesLoading = ref(false)
const selectedAccessory = ref('')
const accessoryDocs = ref([])
const accessoryDocsLoading = ref(false)
const accessoryDocsError = ref('')
const allAccessoryDocs = ref([])

const handleOriginalFileClick = (file) => {
  if (!file?.path) {
    ElMessage.warning('无法查看：缺少文件路径')
    return
  }
  const resolvedUrl = resolveFileUrl(file.path)
  if (!resolvedUrl) return
  window.open(resolvedUrl, '_blank', 'noopener')
}

const editDialogVisible = ref(false)
const editLoading = ref(false)
const originalDocName = ref('')
const editForm = reactive({
  path: '',
  name: '',
  content: '',
})

const formatDocType = (type) => {
  if (type === 'image') return '图片'
  if (type === 'image_embedded') return '文档图片'
  return '文件'
}
const goBack = () => router.back()

const manualProductBase = computed(() => productDocs.value.filter((doc) => String(doc.category || '').startsWith('manual_')))
const manualProductUploads = computed(() => manualProductBase.value.filter((doc) => doc.category === 'manual_upload'))
const manualProductOcrArtifacts = computed(() => manualProductBase.value.filter((doc) => doc.category === 'manual_ocr_artifact'))

const manualProductUploadNodes = computed(() => {
  const pageByParent = new Map()
  const uploadStemEntries = manualProductUploads.value
    .map((upload) => {
      const name = String(upload.name || '')
      const stem = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : name
      return {
        stem,
        stemLower: stem.toLowerCase(),
        path: upload.path,
      }
    })
    .filter((item) => item.stem)

  const inferParent = (artifact) => {
    const p = String(artifact?.path || '')
    if (!p) return ''
    const lower = p.toLowerCase()
    for (const item of uploadStemEntries) {
      if (lower.includes(`/products/${item.stemLower}/`)) return item.path
    }
    return ''
  }

  manualProductOcrArtifacts.value.forEach((doc) => {
    const parent = doc.parent_path || inferParent(doc) || ''
    const rawPage = doc.page_number
    const pageNumber = typeof rawPage === 'number' && Number.isFinite(rawPage) ? rawPage : null
    if (!pageByParent.has(parent)) pageByParent.set(parent, new Map())
    const pageMap = pageByParent.get(parent)
    const pageKey = pageNumber ?? 'unknown'
    if (!pageMap.has(pageKey)) pageMap.set(pageKey, [])
    pageMap.get(pageKey).push(doc)
  })

  return manualProductUploads.value.map((upload) => {
    const pagesMap = pageByParent.get(upload.path) || new Map()
    const sortedPages = Array.from(pagesMap.entries())
      .map(([key, docs]) => ({
        pageKey: key,
        page_number: typeof key === 'number' ? key : null,
        documents: (docs || []).slice().sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''))),
      }))
      .sort((a, b) => {
        const av = a.page_number
        const bv = b.page_number
        if (av == null && bv == null) return 0
        if (av == null) return 1
        if (bv == null) return -1
        return av - bv
      })
    return {
      ...upload,
      pages: sortedPages,
    }
  })
})

const inferArtifactKind = (doc) => {
  const name = String(doc?.name || '')
  const mime = String(doc?.mime_type || '')
  const type = String(doc?.type || '')
  const lower = name.toLowerCase()
  if (type === 'image' || mime.startsWith('image/')) return 'image'
  if (lower.endsWith('.md') || lower.endsWith('.markdown') || mime === 'text/markdown') return 'markdown'
  if (lower.endsWith('.json') || mime === 'application/json') return 'json'
  if (mime.startsWith('text/')) return 'text'
  return 'file'
}

const buildOcrGroupsFromNodes = (nodes = []) => {
  if (!Array.isArray(nodes)) return []
  return nodes
    .map((node) => {
      const pages = Array.isArray(node.pages) ? node.pages : []
      return {
        id: node.path,
        sourceName: node.name || '未命名文件',
        sourceMime: node.mime_type || node.type || '',
        pages: pages.map((page, pageIdx) => {
          const artifacts = Array.isArray(page.documents) ? page.documents : []
          return {
            id: `${node.path}-page-${pageIdx}`,
            pageNumber: page.page_number,
            imageStem: page.image_stem,
            artifacts: artifacts.map((doc, artIdx) => ({
              id: `${doc.path || doc.name || 'artifact'}-${artIdx}`,
              name: doc.name,
              url: resolveFileUrl(doc.path),
              path: doc.path || '',
              kind: inferArtifactKind(doc),
              size: doc.size || doc.file_size || 0,
              mime: doc.mime_type || doc.type || '',
              summary: doc.summary || '',
            })),
          }
        }),
      }
    })
    .filter((group) => group.id)
}

const productOcrGroups = computed(() => buildOcrGroupsFromNodes(manualProductUploadNodes.value))
const accessoryOcrGroups = computed(() => buildOcrGroupsFromNodes(manualAccessoryUploadNodes.value))

const ocrModal = reactive({
  visible: false,
  type: 'product',
  group: null,
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
  return selectedArtifact.value.kind === 'image' || selectedArtifact.value.mime?.startsWith?.('image/')
})

const isSelectedArtifactText = computed(() => {
  if (!selectedArtifact.value) return false
  return !isSelectedArtifactImage.value && isArtifactTextLike(selectedArtifact.value)
})

const artifactContent = reactive({
  loading: false,
  text: '',
  error: '',
})

const artifactActionLoading = reactive({
  editing: false,
  deleting: false,
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

const normalizeDocPath = (raw = '') =>
  String(raw || '')
    .replace(/^https?:\/\/[^/]+\/(?:api\/)?files\//, '')
    .replace(new RegExp(`^${API_BASE_URL.replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')}\/api\/files\/`), '')
    .replace(/^\/api\/files\//, '')
    .replace(/^backend\//, '')
    .replace(/^\/+/, '')

const reloadCurrentOcrGroup = () => {
  const currentId = ocrModal.group?.id
  if (!currentId) return
  const candidates = ocrModal.type === 'accessory' ? accessoryOcrGroups.value : productOcrGroups.value
  const next = candidates.find((group) => group.id === currentId) || null
  ocrModal.group = next
  if (!next) {
    closeOcrModal()
    return
  }
  const nextPageIdx = Math.min(selectedPageIndex.value, Math.max(next.pages.length - 1, 0))
  selectedPageIndex.value = nextPageIdx
  pageSelectValue.value = nextPageIdx
  selectedArtifactId.value = next.pages?.[nextPageIdx]?.artifacts?.[0]?.id || ''
}

const reloadDocsForModal = async () => {
  if (ocrModal.type === 'accessory') {
    if (!selectedAccessory.value) return
    await loadAccessoryDocs(selectedAccessory.value, { forceReload: true })
    return
  }
  await loadProductDocs()
}

const handleEditArtifact = async () => {
  const artifact = selectedArtifact.value
  const docPath = normalizeDocPath(artifact?.path || '') || normalizeDocPath(artifact?.url || '')
  if (!docPath || artifactActionLoading.editing) return
  try {
    artifactActionLoading.editing = true
    let content = artifactContent.text
    if (!content && artifact?.url) {
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
      draggable: true,
      closeOnClickModal: false,
    })
    if (action !== 'confirm') return
    const { updateDocument } = await import('@/services/api')
    await updateDocument(docPath, { content: value })
    ElMessage.success('已保存')
    await reloadDocsForModal()
    reloadCurrentOcrGroup()
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
      closeOnClickModal: false,
    })
    artifactActionLoading.deleting = true
    const { deleteDocument } = await import('@/services/api')
    await deleteDocument(docPath)
    ElMessage.success('已删除')
    await reloadDocsForModal()
    selectedArtifactId.value = ''
    reloadCurrentOcrGroup()
  } catch (error) {
    if (error === 'cancel') return
    ElMessage.error(error?.message || '删除失败')
  } finally {
    artifactActionLoading.deleting = false
  }
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

const manualAccessoryBase = computed(() => accessoryDocs.value.filter((doc) => String(doc.category || '').startsWith('manual_')))
const manualAccessoryUploads = computed(() => manualAccessoryBase.value.filter((doc) => doc.category === 'manual_accessory_upload'))
const manualAccessoryOcrArtifacts = computed(() =>
  manualAccessoryBase.value.filter((doc) => doc.category === 'manual_accessory_ocr_artifact')
)

const manualAccessoryUploadNodes = computed(() => {
  const pageByParent = new Map()
  const uploadStemEntries = manualAccessoryUploads.value
    .map((upload) => {
      const name = String(upload.name || '')
      const stem = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : name
      return {
        stem,
        stemLower: stem.toLowerCase(),
        path: upload.path,
      }
    })
    .filter((item) => item.stem)

  const inferParent = (artifact) => {
    const p = String(artifact?.path || '')
    if (!p) return ''
    const lower = p.toLowerCase()
    for (const item of uploadStemEntries) {
      if (lower.includes(`/accessories/${item.stemLower}/`)) return item.path
    }
    return ''
  }

  manualAccessoryOcrArtifacts.value.forEach((doc) => {
    const parent = doc.parent_path || inferParent(doc) || ''
    const rawPage = doc.page_number
    const pageNumber = typeof rawPage === 'number' && Number.isFinite(rawPage) ? rawPage : null
    if (!pageByParent.has(parent)) pageByParent.set(parent, new Map())
    const pageMap = pageByParent.get(parent)
    const pageKey = pageNumber ?? 'unknown'
    if (!pageMap.has(pageKey)) pageMap.set(pageKey, [])
    pageMap.get(pageKey).push(doc)
  })

  return manualAccessoryUploads.value.map((upload) => {
    const pagesMap = pageByParent.get(upload.path) || new Map()
    const sortedPages = Array.from(pagesMap.entries())
      .map(([key, docs]) => ({
        pageKey: key,
        page_number: typeof key === 'number' ? key : null,
        documents: (docs || []).slice().sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''))),
      }))
      .sort((a, b) => {
        const av = a.page_number
        const bv = b.page_number
        if (av == null && bv == null) return 0
        if (av == null) return 1
        if (bv == null) return -1
        return av - bv
      })
    return {
      ...upload,
      pages: sortedPages,
    }
  })
})

const pickDocsForTransfer = (docs = []) =>
  (Array.isArray(docs) ? docs : []).map((doc) => ({
    name: doc?.name || '',
    path: doc?.path || '',
    type: doc?.type || '',
    summary: doc?.summary || '',
  }))

const stringifyDocsForQuery = (docs = []) => {
  try {
    return JSON.stringify(pickDocsForTransfer(docs))
  } catch (error) {
    console.warn('Failed to stringify docs', error)
    return '[]'
  }
}

const pickAccessoryGroupsForTransfer = (groups = []) =>
  (Array.isArray(groups) ? groups : [])
    .map((group) => ({
      accessory: group?.accessory || '',
      documents: pickDocsForTransfer(group?.documents || []),
    }))
    .filter((group) => group.accessory && group.documents.length)

const stringifyAccessoryGroupsForQuery = (groups = []) => {
  try {
    return JSON.stringify(pickAccessoryGroupsForTransfer(groups))
  } catch (error) {
    console.warn('Failed to stringify accessory docs', error)
    return '[]'
  }
}

const upsertAccessoryGroup = (accessoryName, docs = []) => {
  const next = allAccessoryDocs.value.slice()
  const idx = next.findIndex((item) => item.accessory === accessoryName)
  const entry = { accessory: accessoryName, documents: Array.isArray(docs) ? docs : [] }
  if (idx >= 0) {
    next[idx] = entry
  } else {
    next.push(entry)
  }
  allAccessoryDocs.value = next
}

const loadAllAccessoryDocs = async (names = []) => {
  if (!Array.isArray(names) || !names.length) {
    allAccessoryDocs.value = []
    return
  }
  try {
    const { getDocumentsByAccessory } = await import('@/services/api')
    const groups = await Promise.all(
      names.map(async (name) => {
        try {
          const docs = await getDocumentsByAccessory(name)
          return { accessory: name, documents: docs }
        } catch (error) {
          console.error(`Failed to load documents for accessory ${name}`, error)
          return { accessory: name, documents: [] }
        }
      })
    )
    allAccessoryDocs.value = groups
  } catch (error) {
    console.error('Failed to prefetch accessory documents', error)
    allAccessoryDocs.value = names.map((name) => ({ accessory: name, documents: [] }))
  }
}

const getCachedAccessoryDocs = (accessoryName) =>
  allAccessoryDocs.value.find((item) => item.accessory === accessoryName)

const ensureAllAccessoryDocsReady = async () => {
  if (!accessories.value.length) {
    allAccessoryDocs.value = []
    return
  }
  if (allAccessoryDocs.value.length === accessories.value.length) {
    return
  }
  await loadAllAccessoryDocs(accessories.value)
}

const goGenerate = async () => {
  if (!canLoad.value) return
  await ensureAllAccessoryDocsReady()
  router.push({
    name: 'ProductDetail',
    params: { id: String(id.value) },
    query: {
      productName: productName.value,
      name: displayName.value,
      image: image.value,
      bom: bom.value,
      productDocs: stringifyDocsForQuery(productDocs.value),
      accessoryDocs: stringifyAccessoryGroupsForQuery(allAccessoryDocs.value),
      accessoryName: selectedAccessory.value || '',
    },
  })
}

const loadProductDocs = async () => {
  if (!canLoad.value) return
  productDocsLoading.value = true
  productDocsError.value = ''
  try {
    const { getDocumentsByProductBom } = await import('@/services/api')
    const docs = await getDocumentsByProductBom(productName.value, bom.value)
    productDocs.value = docs
  } catch (error) {
    productDocsError.value = '加载产品文件失败'
    productDocs.value = []
    console.error(error)
  } finally {
    productDocsLoading.value = false
  }
}

const loadAccessories = async () => {
  if (!canLoad.value) {
    accessories.value = []
    selectedAccessory.value = ''
    allAccessoryDocs.value = []
    return
  }
  accessoriesLoading.value = true
  try {
    const { getAccessoriesByProductBom } = await import('@/services/api')
    const list = await getAccessoriesByProductBom(productName.value, bom.value)
    accessories.value = Array.isArray(list) ? list : []
    await loadAllAccessoryDocs(accessories.value)
    if (accessories.value.length && !selectedAccessory.value) {
      selectedAccessory.value = accessories.value[0]
    } else if (!accessories.value.length) {
      selectedAccessory.value = ''
    }
    if (selectedAccessory.value) {
      loadAccessoryDocs(selectedAccessory.value)
    }
  } catch (error) {
    accessories.value = []
    selectedAccessory.value = ''
    allAccessoryDocs.value = []
    console.error(error)
  } finally {
    accessoriesLoading.value = false
  }
}

const loadAccessoryDocs = async (accessoryName, { forceReload = false } = {}) => {
  if (!accessoryName) {
    accessoryDocs.value = []
    return
  }
  if (!forceReload) {
    const cached = getCachedAccessoryDocs(accessoryName)
    if (cached) {
      accessoryDocs.value = cached.documents || []
      return
    }
  }
  accessoryDocsLoading.value = true
  accessoryDocsError.value = ''
  try {
    const { getDocumentsByAccessory } = await import('@/services/api')
    const docs = await getDocumentsByAccessory(accessoryName)
    accessoryDocs.value = docs
    upsertAccessoryGroup(accessoryName, docs)
  } catch (error) {
    accessoryDocsError.value = '加载配件文件失败'
    accessoryDocs.value = []
    console.error(error)
  } finally {
    accessoryDocsLoading.value = false
  }
}

const refreshAccessoryDocs = () => {
  if (selectedAccessory.value) {
    loadAccessoryDocs(selectedAccessory.value, { forceReload: true })
  }
}

const handleRefresh = () => {
  if (!canLoad.value) return
  loadProductDocs()
  loadAccessories()
  if (selectedAccessory.value) {
    refreshAccessoryDocs()
  }
}

watch(selectedAccessory, (value) => {
  if (value) {
    loadAccessoryDocs(value)
  } else {
    accessoryDocs.value = []
  }
})

const openEditDialog = async (doc) => {
  editDialogVisible.value = true
  editLoading.value = true
  editForm.path = doc.path
  editForm.name = doc.name
  editForm.content = ''
  originalDocName.value = doc.name
  try {
    const { getDocumentDetail } = await import('@/services/api')
    const detail = await getDocumentDetail(doc.path)
    editForm.name = detail.new_name || detail.name || doc.name
    originalDocName.value = editForm.name
    editForm.content = detail.content || ''
  } catch (error) {
    ElMessage.error('加载文件详情失败')
    console.error(error)
    editDialogVisible.value = false
  } finally {
    editLoading.value = false
  }
}

const closeEditDialog = () => {
  if (editLoading.value) return
  editDialogVisible.value = false
}

const submitEdit = async () => {
  if (!editForm.content.trim()) {
    ElMessage.warning('文件内容不能为空')
    return
  }
  editLoading.value = true
  try {
    const payload = { content: editForm.content }
    if (editForm.name && editForm.name !== originalDocName.value) {
      payload.new_name = editForm.name
    }
    const { updateDocument } = await import('@/services/api')
    await updateDocument(editForm.path, payload)
    ElMessage.success('文件已更新')
    editDialogVisible.value = false
    loadProductDocs()
    refreshAccessoryDocs()
  } catch (error) {
    ElMessage.error(error?.message || '文件更新失败')
    console.error(error)
  } finally {
    editLoading.value = false
  }
}

const confirmDelete = (doc) => {
  ElMessageBox.confirm(`确认删除文件「${doc.name}」？该操作不可撤销。`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
    .then(async () => {
      try {
        const { deleteDocument } = await import('@/services/api')
        await deleteDocument(doc.path)
        ElMessage.success('文件已删除')
        loadProductDocs()
        refreshAccessoryDocs()
      } catch (error) {
        ElMessage.error(error?.message || '删除失败')
        console.error(error)
      }
    })
    .catch(() => {})
}

watch(() => [productName.value, bom.value], () => {
  if (canLoad.value) {
    loadProductDocs()
    loadAccessories()
  }
})

onMounted(() => {
  if (canLoad.value) {
    loadProductDocs()
    loadAccessories()
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
.product-summary {
  display: flex;
  gap: 16px;
  align-items: center;
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}
.thumb {
  width: 96px;
  height: 96px;
  object-fit: contain;
  background: #fafafa;
  border-radius: 8px;
}
.meta .name {
  font-weight: 700;
  font-size: 18px;
  margin-bottom: 4px;
}
.meta .sub {
  color: #666;
  font-size: 14px;
}
.alert {
  width: 100%;
}
.files-board {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.file-row {
  display: flex;
  gap: 16px;
  align-items: stretch;
}
.file-panel {
  flex: 1;
  min-height: 360px;
  background: #fff;
  border-radius: 14px;
  padding: 18px;
  box-shadow: 0 6px 28px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.panel-body > .document-list,
.panel-body > .simple-doc-list {
  flex: 1;
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
.simple-doc-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.simple-doc-list.scrollable {
  flex: 1;
  max-height: 420px;
  overflow: auto;
}
.related-doc-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.related-doc-list.scrollable {
  flex: 1;
  max-height: 420px;
  overflow: auto;
}
.related-doc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border: 1px solid #f1f2f5;
  border-radius: 12px;
  background: #fafbfd;
}
.related-doc-main {
  flex: 1;
  min-width: 0;
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
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.simple-doc-item .doc-name {
  font-weight: 600;
}
.doc-subtle {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}
.state.condensed {
  padding: 12px;
  font-size: 13px;
}
.panel-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.accessory-select {
  min-width: 180px;
}
.document-list.compact {
  flex: 1;
  max-height: 420px;
  overflow: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.document-item {
  width: 100%;
}
.doc-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.doc-metadata {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.doc-summary {
  margin-top: 4px;
  font-size: 13px;
  color: #666;
}
.doc-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #bbb;
}
.image-preview {
  min-height: 200px;
  max-height: 70vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f9f9f9;
  border-radius: 8px;
  padding: 16px;
}

.image-preview img {
  max-width: 100%;
  max-height: 60vh;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.15);
}

 .manual-page-groups {
  display: grid;
  gap: 12px;
 }

 .manual-page-group {
  padding: 8px 10px;
  border: 1px solid #f0f0f0;
  border-radius: 10px;
  background: #fcfcfd;
  display: grid;
  gap: 10px;
 }

 .manual-page-title {
  font-weight: 600;
  font-size: 13px;
  color: #303133;
 }

 .manual-page-count {
  margin-left: 6px;
  font-weight: 500;
  color: #909399;
 }

.ocr-summary-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ocr-summary-list.scrollable {
  flex: 1;
  max-height: 420px;
  overflow: auto;
}

.ocr-summary-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #f1f2f5;
  border-radius: 12px;
  background: #fafbfd;
}

.group-title {
  font-weight: 600;
  color: #303133;
}

.group-subtle {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.ocr-summary-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ocr-detail-dialog :deep(.el-dialog__body) {
  padding-top: 8px;
}

.ocr-modal-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ocr-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.modal-group-name {
  font-weight: 700;
  font-size: 16px;
}

.modal-group-subtle {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.ocr-modal-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.page-meta {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.page-title {
  font-weight: 600;
}

.artifact-selector {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #606266;
}

.artifact-select {
  flex: 1;
  min-width: 360px;
}

.artifact-option {
  display: flex;
  align-items: center;
  gap: 8px;
}

.artifact-preview-panel {
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.artifact-preview-header {
  padding: 12px 14px;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid #f2f3f5;
  background: #fbfbfc;
}

.preview-title {
  font-weight: 600;
}

.preview-subtle {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}

.artifact-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.artifact-preview-body {
  padding: 12px 14px;
}

.artifact-preview-body img {
  max-width: 100%;
  max-height: 56vh;
  display: block;
  margin: 0 auto;
  border-radius: 8px;
}

.artifact-preview-body iframe {
  width: 100%;
  min-height: 56vh;
  border: none;
}

.artifact-text-panel {
  max-height: 56vh;
  overflow: auto;
  background: #0b1020;
  border-radius: 10px;
  padding: 12px;
}

.artifact-text {
  color: #e5e7eb;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
}

.artifact-preview-fallback {
  color: #909399;
  font-size: 13px;
}

.ocr-page-pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 4px;
}

.page-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #606266;
}
</style>
