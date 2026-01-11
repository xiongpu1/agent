
<template>
  <div class="page">
    <div class="page-header">
      <h1 class="title">基于产品知识库的内容生成系统</h1>
      <div class="toolbar">
        <el-button round :type="active === 'upload' ? 'primary' : ''" :plain="active !== 'upload'" :icon="Upload" @click="active = 'upload'">上传图片</el-button>
        <el-button round :type="active === 'kbSearch' ? 'primary' : ''" :plain="active !== 'kbSearch'" :icon="Search" @click="active = 'kbSearch'">产品知识库</el-button>
        <el-button round :type="active === 'manual' ? 'primary' : ''" :plain="active !== 'manual'" :icon="Notebook" @click="active = 'manual'">生成产品手册</el-button>
        <el-button round :type="active === 'export' ? 'primary' : ''" :plain="active !== 'export'" :icon="Download" @click="active = 'export'">导出编辑器</el-button>
      </div>
    </div>

    <div class="panel">
      <!-- 上传图片 -->
      <div v-if="active === 'upload'">
        <div class="img-mgr">
          <div class="img-mgr__left">
            <div class="card-header">上传图片</div>
            <div class="upload-form">
              <el-form :model="uploadForm" label-width="100px">
                <el-form-item label="产品名称">
                  <el-input v-model="uploadForm.name" placeholder="请输入产品名称后再选择图片" />
                </el-form-item>
                <el-form-item label="选择图片">
                  <el-upload
                    class="uploader"
                    drag
                    action="#"
                    :auto-upload="false"
                    :file-list="fileList"
                  >
                    <div class="el-upload__text">将文件拖到此处，或<em>点击选择</em></div>
                    <template #tip>
                      <div class="el-upload__tip">仅前端布局占位，未接入真实上传。</div>
                    </template>
                  </el-upload>
                </el-form-item>
                <div class="actions">
                  <el-button type="primary">上传</el-button>
                </div>
              </el-form>
            </div>

            <div class="divider" />

            <div class="card-header">查询图片</div>
            <div class="search-row">
              <el-input v-model="imageSearchName" placeholder="输入产品名称进行查询（仅布局）" clearable />
              <el-button type="primary">查询</el-button>
            </div>
          </div>

          <div class="img-mgr__right">
            <div class="list-toolbar">
              <div class="list-title">图片列表</div>
              <div class="list-actions">
                <el-button>查看所有图片</el-button>
              </div>
            </div>
            <el-table :data="imageList" border style="width: 100%">
              <el-table-column prop="name" label="产品名称" min-width="140" />
              <el-table-column label="缩略图" width="120">
                <template #default="scope">
                  <img :src="scope.row.url" class="thumb" alt="thumb" @error="onImgError" />
                </template>
              </el-table-column>
              <el-table-column prop="filename" label="文件名" min-width="180" />
              <el-table-column label="操作" width="160">
                <template #default>
                  <el-button link type="primary">修改</el-button>
                  <el-button link type="danger">删除</el-button>
                </template>
              </el-table-column>
            </el-table> 
          </div>
        </div>

      </div>
      <!-- 查询知识库 -->
      <div v-else-if="active === 'kbSearch'" class="section">
        <div class="card-header">产品知识库</div>
        <div class="product-panel">
          <div class="product-panel__header">所有物料编码</div>
          <el-input
            v-model="materialKeyword"
            placeholder="搜索物料编码"
            clearable
            class="product-panel__input"
          />
          <div v-if="loadingMaterials" class="loading">物料列表加载中...</div>
          <div v-else-if="materialsError" class="error">{{ materialsError }}</div>
          <div v-else-if="filteredMaterials.length" class="product-tags">
            <el-tag
              v-for="materialCode in filteredMaterials"
              :key="materialCode"
              class="product-tag"
              round
              effect="plain"
              @click="goToMaterialOverview(materialCode)"
            >
              {{ materialCode }}

            </el-tag>
          </div>
          <el-empty v-else :description="materials.length ? '未找到匹配的物料' : '暂无物料数据'" />
        </div>
        <div class="product-panel">
          <div class="product-panel__header">所有配件</div>
          <el-input
            v-model="accessoryKeyword"
            placeholder="搜索配件名称"
            clearable
            class="product-panel__input"
          />
          <div v-if="loadingAccessories" class="loading">配件列表加载中...</div>
          <div v-else-if="accessoriesError" class="error">{{ accessoriesError }}</div>
          <div v-else-if="accessoryTagsToShow.length" class="product-tags">
            <el-tag
              v-for="accessoryName in accessoryTagsToShow"
              :key="accessoryName"
              class="product-tag"
              round
              effect="plain"
            >
              {{ accessoryName }}
            </el-tag>
            <span
              v-if="accessoryHasMore"
              class="ellipsis-tag"
              role="button"
              tabindex="0"
              @click="showAllAccessoryTags"
              @keydown.enter.space.prevent="showAllAccessoryTags"
            >
              ...
            </span>
            <span
              v-else-if="showCollapseAccessoryTags"
              class="ellipsis-tag"
              role="button"
              tabindex="0"
              @click="collapseAccessoryTags"
              @keydown.enter.space.prevent="collapseAccessoryTags"
            >
              收起
            </span>
          </div>
          <el-empty v-else :description="hasAccessories ? '未找到匹配的配件' : '暂无配件数据'" />
        </div>

        <div class="prompt-optimizer-card" role="button" tabindex="0" @click="goToPromptPlaybook" @keydown.enter.space.prevent="goToPromptPlaybook">
          <div class="prompt-optimizer-card__header">
            <div>
              <div class="prompt-optimizer-card__title">提示词优化工作</div>
              <div class="prompt-optimizer-card__subtitle">
                面向规格页 / 说明书 / 海报的 ACE Prompt Playbook。
              </div>
            </div>
            <el-button type="primary" round>进入工作台</el-button>
          </div>
          <div class="prompt-optimizer-card__grid">
            <div v-for="highlight in promptPlaybookHighlights" :key="highlight.type" class="prompt-optimizer-card__item">
              <div class="item-label">
                {{ highlight.badge }} · {{ highlight.title }}
              </div>
              <div class="item-desc">{{ highlight.description }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 生成产品手册 -->
      <div v-else-if="active === 'manual'" class="section manual-section">
        <div class="card-header">生成产品手册</div>
        <el-form :model="manualForm" label-width="90px" class="manual-form">
          <el-form-item label="产品名称">
            <el-input v-model="manualForm.productName" placeholder="请输入产品名称" clearable />
          </el-form-item>
          <div class="bom-lookup-card">
            <div class="bom-card-header">
              <div>
                <div class="bom-card-title">BOM 编码快速解析</div>
                <div class="bom-card-sub">先选择产品类型，再输入 {{ bomLookupDigits }} 位编码即可查看配置</div>
              </div>
            </div>
            <div class="bom-card-controls">
              <div class="bom-type-tabs">
                <span class="control-label">产品类型</span>
                <el-radio-group v-model="bomLookupType" size="small" class="bom-type-switch">
                  <el-radio-button v-for="typeOption in BOM_TYPE_OPTIONS" :key="typeOption.value" :label="typeOption.value">
                    {{ typeOption.label }}
                  </el-radio-button>
                </el-radio-group>
              </div>
              <div class="bom-input-field">
                <span class="control-label">BOM 编码</span>
                <el-input
                  v-model="bomLookupCode"
                  :maxlength="bomLookupDigits"
                  placeholder="请输入完整 BOM 编号"
                  clearable
                  class="bom-code-input"
                />
              </div>
            </div>
            <div class="bom-card-meta">
              <span class="bom-counter">{{ bomLookupLength }} / {{ bomLookupDigits }} 位</span>
              <el-button text size="small" class="bom-toggle-btn" @click="toggleBomExpanded">
                {{ bomExpanded ? '收起配置段位' : '展开配置段位' }}
                <el-icon class="bom-toggle-icon" :class="{ rotated: bomExpanded }"><CaretBottom /></el-icon>
              </el-button>
            </div>
            <el-alert
              v-if="bomLookupError"
              :title="bomLookupError"
              type="warning"
              :closable="false"
              show-icon
              class="bom-lookup-alert"
            />
            <transition name="fade">
              <div v-show="bomExpanded" class="bom-detail-grid editable">
                <div v-for="segment in flatBomSegments" :key="segment.key" class="bom-detail-card editable">
                  <div class="detail-head">
                    {{ segment.label }}
                    <span class="detail-digits">{{ segment.digits }} 位</span>
                  </div>
                  <div class="detail-control">
                    <el-select
                      v-if="segment.options && Object.keys(segment.options).length"
                      v-model="bomSelections[segment.key]"
                      filterable
                      clearable
                      :allow-create="Boolean(segment.inputFallback)"
                      default-first-option
                      :placeholder="segment.placeholder || '请选择或输入编码'"
                      @change="(val) => updateSegmentValue(segment.key, val, segment.digits)"
                    >
                      <el-option
                        v-for="(label, code) in segment.options"
                        :key="code"
                        :label="`${code} · ${label}`"
                        :value="code"
                      />
                    </el-select>
                    <el-input
                      v-else
                      :model-value="bomSelections[segment.key]"
                      :maxlength="segment.digits"
                      :placeholder="segment.placeholder || `请输入 ${segment.digits} 位编码`"
                      @input="(val) => updateSegmentValue(segment.key, val, segment.digits)"
                    />
                  </div>
                  <div class="detail-meaning">{{ resolveSegmentMeaning(segment) }}</div>
                </div>
              </div>
            </transition>
          </div>
          <div class="manual-upload-grid">
            <div class="manual-upload-card">
              <div class="manual-upload-title">产品文件</div>
              <el-upload
                class="manual-uploader"
                drag
                action="#"
                :auto-upload="false"
                :file-list="manualProductFiles"
                multiple
                @change="handleManualProductFileChange"
              >
                <el-icon class="manual-upload-icon"><Upload /></el-icon>
                <div class="el-upload__text">拖拽或点击上传产品相关资料</div>
                <template #tip>
                  <div class="el-upload__tip">支持多文件上传功能，可上传产品相关的测试报告、操作工艺说明、产品图片等资料。</div>
                </template>
              </el-upload>
            </div>

            <div class="manual-upload-card">
              <div class="manual-upload-title">配件文件</div>
              <el-upload
                class="manual-uploader"
                drag
                action="#"
                :auto-upload="false"
                :file-list="manualAccessoryFiles"
                multiple
                @change="handleManualAccessoryFileChange"
              >
                <el-icon class="manual-upload-icon"><Upload /></el-icon>
                <div class="el-upload__text">拖拽或点击上传相关配件资料</div>
                <template #tip>
                  <div class="el-upload__tip">可选上传，用于辅助生成手册内容。</div>
                </template>
              </el-upload>
            </div>
          </div>
          <div class="manual-actions">
            <el-button
              :loading="manualGenerating"
              type="primary"
              :disabled="manualGenerating"
              @click="handleManualSubmit"
            >
              进行文件OCR
            </el-button>
            <el-button text @click="resetManualForm">重置</el-button>
          </div>
        </el-form>

        <div class="manual-history-bar">
          <div>
            <div class="history-title">历史记录</div>
            <div class="history-sub">展示最近 50 条 OCR 结果，可随时重新查看</div>
          </div>
          <el-button type="primary" text @click="openHistoryDialog">查看历史</el-button>
        </div>
      </div>

      <!-- 导出编辑器 -->
      <div v-else class="section">
        <div class="card-header">导出编辑器</div>
        <div v-if="loadingMaterials" class="loading">加载中...</div>
        <div v-else-if="materialsError" class="error">{{ materialsError }}</div>
        <div v-else>
          <div class="search-row product-search">
            <el-input
              v-model="exportMaterialKeyword"
              placeholder="输入物料编码进行查询..."
              clearable
            >
              <template #prefix>
                <el-icon class="product-search-icon">
                  <Search />
                </el-icon>
              </template>
            </el-input>
          </div>
          <div v-if="filteredExportMaterials.length" class="product-list">
            <el-card
              v-for="materialCode in filteredExportMaterials"
              :key="materialCode"
              class="product-card"
              shadow="hover"
              @click="goToExportMaterial(materialCode)"
            >
              <div class="product-row">
                <div class="product-name">{{ materialCode }}</div>
                <div class="arrow">›</div>
              </div>
            </el-card>
          </div>
          <div v-else class="loading">未找到匹配的物料</div>
        </div>
      </div>
    </div>
  </div>

  <el-dialog
    v-model="manualHistoryVisible"
    width="720px"
    class="manual-history-dialog"
    :close-on-click-modal="false"
    @close="closeHistoryDialog"
  >
    <template #header>
      <div class="dialog-header">
        <div>
          <div class="dialog-title">历史 OCR 记录</div>
          <div class="history-sub">展示最近 50 条 OCR 结果，可随时重新查看</div>
        </div>
        <el-button
          text
          :loading="historyLoading"
          @click="loadManualHistory(true)"
        >刷新</el-button>
        <el-button
          text
          type="danger"
          :loading="historyClearing"
          @click="handleClearManualHistory"
        >清空历史</el-button>
      </div>
    </template>

    <div class="history-dialog-content">
      <div v-if="historyError" class="history-error">{{ historyError }}</div>
      <el-skeleton v-else-if="historyLoading && !historyLoaded" rows="4" animated />
      <el-empty
        v-else-if="!manualHistory.length"
        description="暂无历史记录，赶快上传文件执行 OCR 吧"
      />
      <div v-else class="history-list">
        <el-card
          v-for="entry in manualHistory"
          :key="entry.session_id"
          class="history-item"
          :class="{ disabled: loadingHistorySessionId === entry.session_id }"
          shadow="hover"
          @click="openHistorySession(entry)"
        >
          <div class="history-item-header">
            <div class="history-name">{{ entry.product_name || '未命名产品' }}</div>
            <el-tag size="small" :type="historyStatusType(entry.status)">
              {{ formatHistoryStatus(entry.status) }}
            </el-tag>
          </div>
          <div class="history-meta">
            <span>{{ formatHistoryTime(entry.created_at) }}</span>
            <span>
              上传：产品 {{ entry.product_upload_count || 0 }} · 配件 {{ entry.accessory_upload_count || 0 }}
            </span>
            <span>
              OCR：产品 {{ entry.product_ocr_count || 0 }} · 配件 {{ entry.accessory_ocr_count || 0 }}
            </span>
            <span>
              BOM：{{ entry.bom_code || '未填写' }} · 类型：{{ formatHistoryBomType(entry.bom_type) }}
            </span>
          </div>
          <div class="history-actions-row">
            <el-button
              type="primary"
              text
              :loading="loadingHistorySessionId === entry.session_id"
            >查看详情</el-button>
            <el-button
              type="danger"
              text
              :loading="deletingSessionId === entry.session_id"
              @click.stop="handleDeleteSession(entry, $event)"
            >删除</el-button>
          </div>
        </el-card>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onMounted, watch, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Notebook, Search, Download, CaretBottom } from '@element-plus/icons-vue'
import { setManualData } from '@/stores/manualStore'
import { createManualSession, runManualOcrSession } from '@/services/api'
import { BOM_TYPES, BOM_CONFIG, createDefaultBomSelections } from '@/constants/bomOptions'

const route = useRoute()
const AVAILABLE_TABS = ['upload', 'kbSearch', 'manual', 'export']
const active = ref(AVAILABLE_TABS.includes(route.query.tab) ? route.query.tab : 'export')

// 上传图片
const fileList = ref([])
const handleUploadChange = (file, files) => {
  fileList.value = files
}

// 图片管理（仅前端布局所需的占位数据）
const uploadForm = ref({ name: '' })
const imageSearchName = ref('')
const imageList = ref([])

const loadImages = async () => {
  try {
    const res = await fetch('/upload_image/images.json', { cache: 'no-cache' })
    if (!res.ok) {
      imageList.value = []
      return
    }
    const data = await res.json()
    imageList.value = Array.isArray(data) ? data : []
  } catch {
    imageList.value = []
  }
}

const openHistoryDialog = () => {
  manualHistoryVisible.value = true
  loadManualHistory()
}

const closeHistoryDialog = () => {
  manualHistoryVisible.value = false
}

onMounted(() => {
  if (active.value === 'upload') loadImages()
})

watch(active, (v) => {
  if (v === 'upload') loadImages()
})

const router = useRouter()
const materials = ref([])
const loadingMaterials = ref(false)
const materialsError = ref('')
const materialsLoaded = ref(false)

const products = ref([])
const loadingProducts = ref(false)
const productsError = ref('')
const productsLoaded = ref(false)
const accessories = ref([])
const loadingAccessories = ref(false)
const accessoriesError = ref('')
const accessoriesLoaded = ref(false)

// 生成产品手册
const manualForm = ref({
  productName: ''
})
const manualGenerating = ref(false)
const manualProductFiles = ref([])
const manualAccessoryFiles = ref([])
const manualValidationMessage = computed(() => {
  const trimmedName = manualForm.value.productName.trim()
  if (!trimmedName) return '请先填写产品名称'
  if (!isBomCodeComplete.value) return '请先输入完整的 BOM 编码'
  if (manualProductFiles.value.length === 0) return '请至少上传 1 个产品文件'
  return ''
})
const manualSubmitDisabled = computed(() => Boolean(manualValidationMessage.value))

const BOM_TYPE_OPTIONS = BOM_TYPES
const defaultBomType = BOM_TYPE_OPTIONS[0]?.value || 'outdoor'
const bomLookupType = ref(defaultBomType)
const bomLookupCode = ref('')
const bomLookupError = ref('')
const bomSelections = reactive(createDefaultBomSelections(defaultBomType))
const bomStateByType = reactive({})
const bomExpanded = ref(false)
const isBomCodeComplete = computed(() => {
  const total = bomLookupDigits.value
  if (!total) return false
  const normalized = String(bomLookupCode.value || '').trim().toUpperCase()
  return normalized.length === total && !normalized.includes('·')
})

const computeTotalDigits = (sections = []) => {
  return sections.reduce((sum, section) => {
    if (Array.isArray(section.children) && section.children.length) {
      return (
        sum +
        section.children.reduce((childSum, child) => childSum + (child.digits || 0), 0)
      )
    }
    return sum + (section.digits || 0)
  }, 0)
}

const ensureTypeState = (type) => {
  if (!bomStateByType[type]) {
    bomStateByType[type] = {
      code: '',
      selections: createDefaultBomSelections(type)
    }
  }
  return bomStateByType[type]
}

const snapshotSelections = (source = bomSelections) => {
  return Object.fromEntries(Object.keys(source).map((key) => [key, source[key] || '']))
}

ensureTypeState(defaultBomType)

const currentBomSections = computed(() => BOM_CONFIG[bomLookupType.value] || [])
const flatBomSegments = computed(() => {
  const segments = []
  currentBomSections.value.forEach((section) => {
    if (Array.isArray(section.children) && section.children.length) {
      section.children.forEach((child) => segments.push(child))
    } else {
      segments.push(section)
    }
  })
  return segments
})
const bomLookupDigits = computed(() => computeTotalDigits(currentBomSections.value))
const bomLookupLength = computed(() =>
  (bomLookupCode.value || '').replace(/·/g, '').replace(/\s+/g, '').length
)

const overwriteSelections = (nextSelections = {}) => {
  Object.keys(bomSelections).forEach((key) => {
    if (!(key in nextSelections)) {
      delete bomSelections[key]
    }
  })
  Object.entries(nextSelections).forEach(([key, val]) => {
    bomSelections[key] = val || ''
  })
}

const buildCodeFromSelections = () => {
  return flatBomSegments.value.reduce((acc, segment) => {
    const digits = segment.digits || 0
    const raw = (bomSelections[segment.key] || '').toUpperCase().slice(0, digits)
    const padded = raw.padEnd(digits, '·')
    return acc + padded
  }, '')
}

let suppressCodeWatcher = false
let suppressSelectionWatcher = false

const syncSelectionsToCode = () => {
  const built = buildCodeFromSelections()
  suppressCodeWatcher = true
  bomLookupCode.value = built
  suppressCodeWatcher = false
  bomLookupError.value = built.includes('·') ? '请完善全部段位' : ''
}

const applyCodeToSelections = (rawCode = '') => {
  const normalized = String(rawCode || '').replace(/\s+/g, '').toUpperCase()
  if (!normalized.length) {
    overwriteSelections(createDefaultBomSelections(bomLookupType.value))
    bomLookupError.value = ''
    syncSelectionsToCode()
    return
  }
  const totalDigits = bomLookupDigits.value
  if (!totalDigits) {
    bomLookupError.value = '该产品类型暂未配置解析规则'
    return
  }
  if (normalized.length !== totalDigits) {
    bomLookupError.value = `当前输入 ${normalized.length} 位，需 ${totalDigits} 位`
    return
  }
  let cursor = 0
  const nextSelections = {}
  flatBomSegments.value.forEach((segment) => {
    const digits = segment.digits || 0
    nextSelections[segment.key] = normalized.slice(cursor, cursor + digits)
    cursor += digits
  })
  suppressSelectionWatcher = true
  overwriteSelections(nextSelections)
  suppressSelectionWatcher = false
  bomLookupError.value = ''
  syncSelectionsToCode()
}

watch(
  () => bomLookupType.value,
  (newType, oldType) => {
    if (oldType) {
      ensureTypeState(oldType)
      bomStateByType[oldType].code = bomLookupCode.value
      bomStateByType[oldType].selections = snapshotSelections(bomSelections)
    }
    ensureTypeState(newType)
    overwriteSelections(bomStateByType[newType].selections)
    bomLookupCode.value = bomStateByType[newType].code
    bomLookupError.value = ''
    syncSelectionsToCode()
  }
)

watch(
  bomSelections,
  () => {
    if (suppressSelectionWatcher) return
    syncSelectionsToCode()
  },
  { deep: true }
)

watch(
  bomLookupCode,
  (code) => {
    if (suppressCodeWatcher) return
    applyCodeToSelections(code)
  }
)

const manualHistory = ref([])
const historyLoading = ref(false)
const historyLoaded = ref(false)
const historyError = ref('')
const loadingHistorySessionId = ref('')
const manualHistoryVisible = ref(false)
const deletingSessionId = ref('')
const historyClearing = ref(false)

const resetManualForm = () => {
  manualForm.value = {
    productName: ''
  }
  manualProductFiles.value = []
  manualAccessoryFiles.value = []
}

const handleManualProductFileChange = (file, files) => {
  manualProductFiles.value = files
}

const handleManualAccessoryFileChange = (file, files) => {
  manualAccessoryFiles.value = files
}


const handleDeleteSession = async (entry, evt) => {
  evt?.stopPropagation?.()
  if (!entry?.session_id || deletingSessionId.value || historyClearing.value) return
  try {
    await ElMessageBox.confirm(`确定要删除「${entry.product_name || '未命名产品'}」的 OCR 记录吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  deletingSessionId.value = entry.session_id
  try {
    const { deleteManualSession } = await import('@/services/api')
    await deleteManualSession(entry.session_id)
    manualHistory.value = manualHistory.value.filter((item) => item.session_id !== entry.session_id)
    ElMessage.success('已删除该历史记录')
  } catch (error) {
    console.error('Failed to delete manual session:', error)
    ElMessage.error(error?.message || '删除失败，请稍后重试')
  } finally {
    deletingSessionId.value = ''
  }
}

const handleClearManualHistory = async () => {
  if (historyClearing.value || deletingSessionId.value) return
  try {
    await ElMessageBox.confirm('确定要清空所有 OCR 历史记录吗？该操作不可恢复。', '清空确认', {
      type: 'warning',
      confirmButtonText: '清空',
      cancelButtonText: '取消'
    })
  } catch {
    return
  }

  historyClearing.value = true
  try {
    const { clearManualHistory } = await import('@/services/api')
    await clearManualHistory()
    manualHistory.value = []
    historyLoaded.value = false
    ElMessage.success('已清空历史记录')
  } catch (error) {
    console.error('Failed to clear manual history:', error)
    ElMessage.error(error?.message || '清空历史失败，请稍后重试')
  } finally {
    historyClearing.value = false
  }
}

const prepareManualFiles = (files = []) =>
  (Array.isArray(files) ? files : []).map((file) => {
    const raw = file.raw || file
    const previewUrl = raw ? URL.createObjectURL(raw) : file.url || ''
    return {
      id: file.uid || `${file.name}-${raw?.lastModified || Date.now()}`,
      name: raw?.name || file.name || '未命名文件',
      size: raw?.size ?? file.size ?? 0,
      type: raw?.type ?? file.type ?? '',
      lastModified: raw?.lastModified ?? Date.now(),
      previewUrl,
      rawFile: raw
    }
  })

const generateManual = async () => {
  if (manualSubmitDisabled.value || manualGenerating.value) return
  manualGenerating.value = true
  try {
    const trimmedName = manualForm.value.productName.trim()
    const bomCode = bomLookupCode.value.trim().toUpperCase()
    const session = await createManualSession({
      productName: trimmedName,
      bomCode,
      bomType: bomLookupType.value,
      productFiles: manualProductFiles.value,
      accessoryFiles: manualAccessoryFiles.value
    })
    const sessionId = session?.session_id || session?.id
    if (!sessionId) {
      throw new Error('创建 OCR 会话失败，请稍后重试')
    }

    const preparedProductFiles = prepareManualFiles(manualProductFiles.value)
    const preparedAccessoryFiles = prepareManualFiles(manualAccessoryFiles.value)

    setManualData({
      productName: trimmedName,
      bomCode,
      bomType: bomLookupType.value,
      productFiles: preparedProductFiles,
      accessoryFiles: preparedAccessoryFiles,
      sessionId,
      ocrProgress: null
    })

    router.push({ name: 'ManualReview', query: { sessionId, bomType: bomLookupType.value } })
  } catch (error) {
    console.error('Failed to create manual session:', error)
    ElMessage.error(error?.message || '提交失败，请稍后重试')
  } finally {
    manualGenerating.value = false
  }
}

const handleManualSubmit = async () => {
  if (manualSubmitDisabled.value) {
    ElMessage.warning(manualValidationMessage.value || '请先完善必填信息')
    return
  }
  await generateManual()
}

const formatHistoryTime = (value) => {
  if (!value) return '未知时间'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

const formatHistoryStatus = (status) => {
  switch ((status || '').toLowerCase()) {
    case 'success':
      return '完成'
    case 'exception':
      return '失败'
    case 'active':
      return '进行中'
    default:
      return '未知'
  }
}

const bomTypeLabelMap = computed(() =>
  Object.fromEntries((BOM_TYPE_OPTIONS || []).map(({ value, label }) => [value, label || value]))
)
const formatHistoryBomType = (type) => bomTypeLabelMap.value[type] || type || '未标注'

const historyStatusType = (status) => {
  switch ((status || '').toLowerCase()) {
    case 'success':
      return 'success'
    case 'exception':
      return 'danger'
    case 'active':
      return 'warning'
    default:
      return 'info'
  }
}

const normalizeHistoryGroups = (groups = []) => {
  if (!Array.isArray(groups)) return []
  return groups.map((group, index) => ({
    id: `${group?.source_name || 'group'}-${index}`,
    sourceName: group?.source_name || '未命名文件',
    sourceMime: group?.source_mime || 'application/octet-stream',
    sourceSize: group?.source_size || 0,
    pages: Array.isArray(group?.pages)
      ? group.pages
          .map((page, pageIdx) => ({
            id: `${group?.source_name || 'group'}-page-${pageIdx}`,
            pageNumber: page?.page_number,
            imageStem: page?.image_stem,
            artifacts: Array.isArray(page?.artifacts)
              ? page.artifacts.map((artifact, artIdx) => ({
                  id: `${page?.image_stem || 'artifact'}-${artIdx}`,
                  name: artifact?.name,
                  url: artifact?.url,
                  kind: artifact?.kind || 'file',
                  size: artifact?.size || 0,
                  mime: artifact?.type || 'application/octet-stream',
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

const loadManualHistory = async (force = false) => {
  if (historyLoading.value || (historyLoaded.value && !force)) return
  historyLoading.value = true
  historyError.value = ''
  try {
    const { getManualHistory } = await import('@/services/api')
    manualHistory.value = await getManualHistory()
    historyLoaded.value = true
  } catch (error) {
    historyError.value = error?.message || '加载历史记录失败'
    console.error('Failed to load manual history:', error)
  } finally {
    historyLoading.value = false
  }
}

const openHistorySession = async (entry) => {
  if (!entry?.session_id || loadingHistorySessionId.value) return
  loadingHistorySessionId.value = entry.session_id
  try {
    const { getManualSession } = await import('@/services/api')
    const session = await getManualSession(entry.session_id)
    setManualData({
      productName: session.product_name || '未命名产品',
      bomCode: session.bom_code || '',
      bomType: session.bom_type || '',
      productFiles: session.product_files || [],
      accessoryFiles: session.accessory_files || [],
      productOcrGroups: normalizeHistoryGroups(session.product_ocr_groups),
      accessoryOcrGroups: normalizeHistoryGroups(session.accessory_ocr_groups),
      sessionId: session.session_id || '',
      ocrProgress: null
    })
    router.push({ name: 'ManualReview', query: { sessionId: session.session_id || '', bomType: session.bom_type || '' } })
  } catch (error) {
    console.error('Failed to open history session:', error)
    ElMessage.error(error?.message || '无法打开该历史记录')
  } finally {
    loadingHistorySessionId.value = ''
  }
}

// 导出编辑器 - 本地产品搜索关键字与过滤结果
const productKeyword = ref('')
const filteredProducts = computed(() => {
  if (!productKeyword.value.trim()) return products.value
  const kw = productKeyword.value.trim().toLowerCase()
  return products.value.filter((item) => {
    const hay = `${item?.label || ''} ${item?.product_id || ''}`.toLowerCase()
    return hay.includes(kw)
  })
})

const exportMaterialKeyword = ref('')
const filteredExportMaterials = computed(() => {
  const list = materials.value
  const kw = exportMaterialKeyword.value.trim().toLowerCase()
  if (!kw) return list
  return list.filter((code) => String(code).toLowerCase().includes(kw))
})

const materialKeyword = ref('')
const filteredMaterials = computed(() => {
  if (!materialKeyword.value.trim()) return materials.value
  const kw = materialKeyword.value.trim().toLowerCase()
  return materials.value.filter((code) => String(code).toLowerCase().includes(kw))
})

const accessoryKeyword = ref('')
const showAllAccessories = ref(false)
const filteredAccessories = computed(() => {
  if (!accessoryKeyword.value.trim()) return accessories.value
  const kw = accessoryKeyword.value.trim().toLowerCase()
  return accessories.value.filter((name) => String(name).toLowerCase().includes(kw))
})

const ACCESSORY_TAG_LIMIT = 80
const hasAccessories = computed(() => accessories.value.length > 0)
const accessoryTagsToShow = computed(() => {
  const list = filteredAccessories.value
  if (accessoryKeyword.value.trim() || showAllAccessories.value) {
    return list
  }
  return list.slice(0, ACCESSORY_TAG_LIMIT)
})
const accessoryHasMore = computed(() =>
  !accessoryKeyword.value.trim() && !showAllAccessories.value && filteredAccessories.value.length > ACCESSORY_TAG_LIMIT
)

const showAllAccessoryTags = () => {
  showAllAccessories.value = true
}

const showCollapseAccessoryTags = computed(() =>
  !accessoryKeyword.value.trim() && showAllAccessories.value && filteredAccessories.value.length > ACCESSORY_TAG_LIMIT
)

const collapseAccessoryTags = () => {
  showAllAccessories.value = false
}

const promptPlaybookHighlights = [
  {
    type: 'spec',
    badge: 'SPEC',
    title: '规格页 Playbook',
    // description: '聚焦技术参数、场景特征、对比卖点，适配结构化导出模板。',
    // example: '列出 5 个关键性能指标 + 注意单位一致'
  },
  {
    type: 'manual',
    badge: 'MANUAL',
    title: '说明书 Playbook',
    // description: '梳理步骤 / 注意事项 / 安全提醒，贴合 OCR 真值生成指引。',
    // example: '拆装步骤遵循「准备-执行-校验」三段式'
  },
  {
    type: 'poster',
    badge: 'POSTER',
    title: '海报 Playbook',
    // description: '总结视觉文案、 CTA、配色建议，支持多场景复用。',
    // example: '三段文案：场景开场 → 特性强化 → 购买号召'
  }
]

const goToPromptPlaybook = () => {
  router.push({ name: 'PromptPlaybook' })
}

const resolveSegmentMeaning = (segment) => {
  const value = (bomSelections[segment.key] || '').toUpperCase()
  if (!value) return '暂未配置说明'
  return segment.options?.[value] || '暂无配置说明'
}

const updateSegmentValue = (key, value, digits) => {
  bomSelections[key] = String(value || '').toUpperCase().slice(0, digits)
}

const toggleBomExpanded = () => {
  bomExpanded.value = !bomExpanded.value
}

const loadMaterials = async (force = false) => {
  if (materialsLoaded.value && !force) return
  loadingMaterials.value = true
  materialsError.value = ''
  try {
    const { getMaterials } = await import('@/services/api')
    const list = await getMaterials()
    materials.value = Array.isArray(list) ? list : []
    materialsLoaded.value = true
  } catch (error) {
    materialsError.value = '加载物料列表失败，请稍后重试'
    console.error('Failed to load materials:', error)
  } finally {
    loadingMaterials.value = false
  }
}

// Load products from API (used by export tab)
const loadProducts = async (force = false) => {
  if (productsLoaded.value && !force) return
  loadingProducts.value = true
  productsError.value = ''
  try {
    const { getProducts } = await import('@/services/api')
    const list = await getProducts()
    products.value = (Array.isArray(list) ? list : []).map((item) => {
      const display = item?.display_name_en || item?.display_name_zh || item?.material_code || item?.product_id || ''
      return {
        ...item,
        label: display,
      }
    })
    productsLoaded.value = true
  } catch (error) {
    productsError.value = '加载产品列表失败，请稍后重试'
    console.error('Failed to load products:', error)
  } finally {
    loadingProducts.value = false
  }
}

const loadAccessories = async (force = false) => {
  if (accessoriesLoaded.value && !force) return
  loadingAccessories.value = true
  accessoriesError.value = ''
  try {
    const { getAccessories } = await import('@/services/api')
    const list = await getAccessories()
    accessories.value = (Array.isArray(list) ? list : [])
      .map((item) => String(item?.name_zh || '').trim())
      .filter(Boolean)
    showAllAccessories.value = false
    accessoriesLoaded.value = true
  } catch (error) {
    accessoriesError.value = '加载配件列表失败，请稍后重试'
    console.error('Failed to load accessories:', error)
  } finally {
    loadingAccessories.value = false
  }
}

const goToMaterialOverview = (materialCode) => {
  const code = String(materialCode || '').trim()
  if (!code) return
  router.push({
    name: 'ProductBomOverview',
    params: { id: '0' },
    query: { materialCode: code }
  })
}

const goToBoms = (product) => {
  const pid = typeof product === 'string' ? product : (product?.product_id || '')
  const label = typeof product === 'string' ? product : (product?.label || '')
  router.push({
    name: 'ProductBoms',
    params: { id: '0' },
    query: { productId: pid, label }
  })
}

const goToExportMaterial = (materialCode) => {
  const code = String(materialCode || '').trim()
  if (!code) return
  router.push({
    name: 'ProductBoms',
    params: { id: '0' },
    query: { materialCode: code, label: code }
  })
}

onMounted(() => {
  if (active.value === 'upload') loadImages()
  loadProducts()
  loadMaterials()
  loadAccessories()
  if (active.value === 'manual' && manualHistoryVisible.value) loadManualHistory()
})

watch(active, (v) => {
  if (v === 'upload') {
    loadImages()
  } else if (['export', 'kbSearch', 'manual'].includes(v)) {
    if (!productsLoaded.value) {
      loadProducts()
    }
    if (!accessoriesLoaded.value) {
      loadAccessories()
    }
  }
  if (v === 'manual' && manualHistoryVisible.value) {
    loadManualHistory()
  }
})


watch(
  () => route.query.tab,
  (tab) => {
    if (typeof tab === 'string' && AVAILABLE_TABS.includes(tab)) {
      active.value = tab
    }
  }
)

watch(accessoryKeyword, (value) => {
  if (value.trim()) {
    showAllAccessories.value = true
  } else {
    showAllAccessories.value = false
  }
})
</script>

<style scoped>

.page {
  width: 100%;
  padding: 24px;
}

.page-header {
  display: grid;
  justify-items: center;
  gap: 30px;
  margin-bottom: 16px;
}

.title {
  font-size: 28px;
  font-weight: 700;
}

.toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.panel {
  background: #fff;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.06);
}

.uploader {
  width: 100%;
}

.section {
  display: grid;
  gap: 12px;
}

.card-header {
  font-size: 18px;
  font-weight: 600;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--color-border);
}

.search-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
}

.results {
  display: grid;
  gap: 12px;
  margin-top: 12px;
}

.result-card .title {
  font-weight: 600;
  margin-bottom: 4px;
}

.result-card .snippet {
  color: #666;
}

.product-panel {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
  margin-top: 12px;
  display: grid;
  gap: 12px;
}

.product-panel__header {
  font-weight: 600;
}

.product-panel__input :deep(.el-input__wrapper) {
  border-radius: 999px;
}

.product-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.product-tag {
  cursor: pointer;
}

.manual-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.bom-lookup-card {
  background: #fff;
  border-radius: 16px;
  padding: 22px 24px;
  box-shadow: 0 8px 26px rgba(15, 23, 42, 0.08);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.bom-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.bom-card-title {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
}

.bom-card-sub {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.bom-card-controls {
  display: grid;
  grid-template-columns: minmax(200px, 320px) minmax(260px, 1fr);
  gap: 18px;
  align-items: end;
}

.control-label {
  font-size: 13px;
  color: #606266;
  margin-bottom: 6px;
  display: inline-block;
}

.bom-type-tabs,
.bom-input-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bom-type-switch :deep(.el-radio-button__inner) {
  padding: 6px 18px;
}

.bom-code-input :deep(.el-input__wrapper) {
  padding: 10px 16px;
  font-size: 15px;
  border-radius: 12px;
}

.bom-card-meta {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #94a3b8;
}

.bom-counter {
  font-size: 13px;
  color: #94a3b8;
}

.bom-lookup-alert {
  margin-top: -4px;
}

.bom-detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.bom-detail-card {
  border-radius: 14px;
  border: 1px solid #eef2ff;
  background: #f9fafb;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bom-detail-card .detail-head {
  font-size: 13px;
  color: #94a3b8;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.bom-detail-card .detail-digits {
  font-size: 12px;
  color: #cbd5f5;
}

.bom-detail-card .detail-control :deep(.el-select),
.bom-detail-card .detail-control :deep(.el-input) {
  width: 100%;
}

.bom-detail-card .detail-meaning {
  font-size: 13px;
  color: #4b5563;
}

.manual-upload-grid {
  cursor: pointer;
}

.ellipsis-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 10px;
  color: #999;
  font-weight: 700;
  cursor: pointer;
}

.actions {
  text-align: right;
}

.product-list {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.product-card {
  cursor: pointer;
}

.product-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 8px;
}

.product-name {
  font-weight: 700;
  font-size: 16px;
}

.arrow {
  color: #999;
  font-size: 20px;
  line-height: 1;
}

.product-card:hover .arrow {
  color: #333;
}

.loading, .error {
  text-align: center;
  padding: 40px;
  color: #666;
}

.error {
  color: #f56c6c;
}

/* 图片管理布局 */
.img-mgr {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 20px;
  align-items: start;
}

.img-mgr__left {
  display: grid;
  gap: 12px;
  overflow: hidden;
}

.img-mgr__right {
  display: grid;
  gap: 12px;
  position: relative;
  z-index: 1;
}

.upload-form {
  background: #fafafa;
  border: 1px dashed var(--el-border-color, #dcdfe6);
  border-radius: 10px;
  padding: 12px;
  overflow: hidden;
}

/* 固定拖拽框高度，文件列表内部滚动，避免整体高度波动 */
.uploader :deep(.el-upload-dragger) {
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  box-sizing: border-box;
}

.uploader :deep(.el-upload-list) {
  max-height: 96px;
  overflow: auto;
  position: static;
}

.divider {
  height: 1px;
  background: var(--color-border, #ebeef5);
}

.list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.list-title {
  font-weight: 600;
}

.thumb {
  width: 64px;
  height: 64px;
  object-fit: contain;
  background: #fff;
  border: 1px solid var(--color-border, #ebeef5);
  border-radius: 6px;
}

/* 导出编辑器 - 产品搜索条样式 */
.product-search {
  max-width: 520px;
  margin: 4px auto 16px;
}

.product-search :deep(.el-input__wrapper) {
  border-radius: 999px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  padding-left: 10px;
}

.product-search-icon {
  color: #c0c4cc;
}
.prompt-optimizer-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  padding: 20px;
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  background: linear-gradient(135deg, #f7f9ff 0%, #ffffff 100%);
  cursor: pointer;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

.prompt-optimizer-card:focus-visible,
.prompt-optimizer-card:hover {
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.12);
  transform: translateY(-2px);
}

.prompt-optimizer-card__header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: center;
  flex-wrap: wrap;
}

.prompt-optimizer-card__title {
  font-size: 20px;
  font-weight: 700;
  color: #0f172a;
}

.prompt-optimizer-card__subtitle {
  margin-top: 4px;
  color: #4b5563;
  font-size: 14px;
}

.prompt-optimizer-card__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.prompt-optimizer-card__item {
  background: rgba(255, 255, 255, 0.8);
  border-radius: 14px;
  padding: 16px;
  border: 1px dashed rgba(148, 163, 184, 0.5);
}

.prompt-optimizer-card__item .item-label {
  font-size: 13px;
  font-weight: 600;
  color: #1d4ed8;
  margin-bottom: 8px;
}

.prompt-optimizer-card__item .item-desc {
  font-size: 14px;
  color: #374151;
  line-height: 1.5;
}

.prompt-optimizer-card__item .item-meta {
  margin-top: 10px;
  font-size: 12px;
  color: #64748b;
}
</style>