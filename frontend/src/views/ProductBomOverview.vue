<template>
  <div class="page">
    <div class="topbar">
      <el-button link class="back-btn" @click="goBack">← 返回</el-button>
      <div class="title">{{ name }} · 产品概览</div>
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">BOM 编号</div>
          <div class="panel-sub">共 {{ boms.length }} 个</div>
        </div>
        <el-input
          v-model="bomKeyword"
          placeholder="搜索 BOM"
          clearable
          class="search-input"
        >
          <template #prefix>
            <el-icon class="search-icon">
              <Search />
            </el-icon>
          </template>
        </el-input>
      </div>
      <div v-if="loadingBoms" class="state">正在加载 BOM 列表...</div>
      <div v-else-if="bomsError" class="state error">{{ bomsError }}</div>
      <div v-else-if="filteredBoms.length" class="bom-tags">
        <el-tag
          v-for="bom in filteredBoms"
          :key="bom"
          class="bom-tag"
          :type="bom === selectedBom ? 'primary' : ''"
          @click="selectBom(bom)"
        >
          {{ bom }}
        </el-tag>
      </div>
      <el-empty v-else description="未找到匹配的 BOM" />
    </div>

    <div class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">关联配件</div>
          <div class="panel-sub" v-if="selectedBom">当前 BOM：{{ selectedBom }}</div>
        </div>
        <el-input
          v-if="selectedBom"
          v-model="accessoryKeyword"
          placeholder="搜索配件"
          clearable
          class="search-input"
        >
          <template #prefix>
            <el-icon class="search-icon">
              <Search />
            </el-icon>
          </template>
        </el-input>
      </div>
      <div v-if="!selectedBom" class="state">请选择上方 BOM 以查看配件与文件</div>
      <div v-else-if="loadingAccessories" class="state">正在加载配件...</div>
      <div v-else-if="accessoriesError" class="state error">{{ accessoriesError }}</div>
      <div v-else-if="filteredAccessories.length" class="product-tags">
        <el-tag
          v-for="item in filteredAccessories"
          :key="item"
          class="product-tag"
          :type="selectedAccessory === item ? 'primary' : 'info'"
          effect="plain"
          @click="toggleAccessory(item)"
        >
          {{ item }}
        </el-tag>
        <el-tag
          v-if="selectedAccessory"
          type="warning"
          effect="plain"
          class="product-tag"
          @click="clearAccessorySelection"
        >
          清除配件筛选
        </el-tag>
      </div>
      <el-empty v-else description="暂无关联配件" />
    </div>

    <div v-if="selectedBom" class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">产品配置</div>
          <div class="panel-sub">config_text_zh</div>
        </div>
        <div class="doc-toolbar">
          <el-button type="primary" plain size="small" :disabled="!selectedBom || !effectiveProductId" @click="openConfigEditDialog">
            编辑
          </el-button>
          <el-button type="primary" plain size="small" :disabled="!kbConfigText" @click="openConfigDialog">
            查看
          </el-button>
        </div>
      </div>
      <div v-if="loadingDocuments" class="state">正在加载配置...</div>
      <div v-else-if="documentsError" class="state error">{{ documentsError }}</div>
    </div>

    <el-dialog v-model="configDialogVisible" title="产品配置" width="840px" :style="{ maxWidth: '92vw' }" :close-on-click-modal="false">
      <div class="preview-dialog">
        <el-scrollbar class="preview-dialog__content config-dialog__content">
          <pre class="config-text">{{ kbConfigText || '暂无产品配置（待绑定）' }}</pre>
        </el-scrollbar>
      </div>
      <template #footer>
        <el-button :disabled="!kbConfigText" @click="copyConfig">复制</el-button>
        <el-button @click="configDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="configEditDialogVisible" title="编辑产品配置" width="840px" :style="{ maxWidth: '92vw' }" :close-on-click-modal="false">
      <div class="preview-dialog">
        <el-input
          v-model="configEditText"
          type="textarea"
          :rows="14"
          placeholder="请输入 config_text_zh（保存后会写入数据库）"
        />
      </div>
      <template #footer>
        <el-button @click="closeConfigEditDialog">取消</el-button>
        <el-button type="primary" :loading="configEditSaving" @click="saveConfigEdit">保存</el-button>
      </template>
    </el-dialog>

    <div v-if="showDocuments" class="panel">
      <div class="panel-header">
        <div>
          <div class="panel-title">{{ documentSectionTitle }}</div>
          <div class="panel-sub">
            <template v-if="selectedAccessory">配件：{{ selectedAccessory }}</template>
            <template v-else-if="selectedBom">BOM：{{ selectedBom }}</template>
            <template v-else>请选择 BOM</template>
          </div>
        </div>
        <div class="doc-toolbar">
          <el-select v-model="fileTypeFilter" class="type-select" placeholder="文件类型" size="small">
            <el-option label="全部" value="all" />
            <el-option label="文档" value="document" />
            <el-option label="图片" value="image" />
            <el-option label="文档图片" value="image_embedded" />
            <el-option label="规格页" value="specsheet" />
          </el-select>
          <el-input
            v-model="docKeyword"
            placeholder="输入文件名关键字"
            clearable
            class="search-input"
          >
            <template #prefix>
              <el-icon class="search-icon">
                <Search />
              </el-icon>
            </template>
          </el-input>
          <el-button type="primary" plain size="small" :disabled="!selectedBom" @click="openAttachDialog">
            增加文件
          </el-button>
        </div>
      </div>
      <div v-if="!selectedBom" class="state">请选择上方 BOM</div>
      <div v-else-if="loadingDocuments" class="state">正在加载文件...</div>
      <div v-else-if="documentsError" class="state error">{{ documentsError }}</div>
      <div v-else class="document-list">
        <el-card class="document-item" shadow="never">
          <div class="doc-name">产品手册</div>
          <div class="doc-summary">规格页 / 说明书 / 海报（来自 HAS_DOC role）</div>
          <div class="doc-actions">
            <el-button
              link
              type="primary"
              size="small"
              :disabled="!kbSpecialDocs.specsheet"
              @click="openFile(kbSpecialDocs.specsheet)"
            >规格页</el-button>
            <el-divider direction="vertical" />
            <el-button
              link
              type="primary"
              size="small"
              :disabled="!kbSpecialDocs.manual"
              @click="openFile(kbSpecialDocs.manual)"
            >说明书</el-button>
            <el-divider direction="vertical" />
            <el-button
              link
              type="primary"
              size="small"
              :disabled="!kbSpecialDocs.poster"
              @click="openFile(kbSpecialDocs.poster)"
            >海报</el-button>
          </div>
        </el-card>

        <el-collapse v-if="kbDatasets.length" class="manual-tree" accordion>
          <el-collapse-item v-for="ds in kbDatasets" :key="ds.dataset_id" :name="ds.dataset_id">
            <template #title>
              <div class="manual-tree-title">
                {{ ds.source === 'manual_uploads' ? '产品/配件文件集合' : `数据集 ${ds.dataset_id}` }}
                <span class="manual-tree-sub">（{{ ds.source || 'unknown' }}）</span>
              </div>
            </template>

            <div class="dataset-groups">
              <el-card class="document-item" shadow="hover">
                <div class="doc-name">产品文件（原始 + OCR）</div>
                <div class="group-note">OCR 将按原始文件页号归档</div>
                <div v-for="raw in getRawWithOcr(ds, 'product')" :key="raw.path" class="raw-block">
                  <div class="doc-row raw-row">
                    <div>
                      <div class="doc-name">{{ raw.name }}</div>
                      <div class="doc-metadata"><span class="doc-path">{{ raw.path }}</span></div>
                    </div>
                    <div class="doc-actions">
                      <el-button link type="primary" size="small" @click="openFile(raw)">打开</el-button>
                    </div>
                  </div>

                  <div v-if="!raw.pages.length" class="page-block">
                    <div class="page-title">暂无已归档 OCR 产物</div>
                  </div>

                  <div v-for="page in raw.pages" :key="page.page_number" class="page-block">
                    <div class="page-title">第 {{ page.page_number }} 页（{{ page.docs.length }}）</div>
                    <div v-for="doc in page.docs" :key="doc.path" class="doc-row ocr-row">
                      <div>
                        <div class="doc-name">{{ doc.name }}</div>
                        <div class="doc-metadata"><span class="doc-path">{{ doc.path }}</span></div>
                      </div>
                      <div class="doc-actions">
                        <el-button link type="primary" size="small" @click="openFile(doc)">打开</el-button>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="getOrphanOcr(ds, 'product').length" class="orphan-block">
                  <div class="page-title">未归档 OCR 文件（{{ getOrphanOcr(ds, 'product').length }}）</div>
                  <div v-for="doc in getOrphanOcr(ds, 'product')" :key="doc.path" class="doc-row ocr-row">
                    <div>
                      <div class="doc-name">{{ doc.name }}</div>
                      <div class="doc-metadata"><span class="doc-path">{{ doc.path }}</span></div>
                    </div>
                    <div class="doc-actions">
                      <el-button link type="primary" size="small" @click="openFile(doc)">打开</el-button>
                    </div>
                  </div>
                </div>
              </el-card>

              <el-card class="document-item" shadow="hover">
                <div class="doc-name">配件文件（原始 + OCR）</div>
                <div class="group-note">OCR 将按原始文件页号归档</div>
                <div v-for="raw in getRawWithOcr(ds, 'accessory')" :key="raw.path" class="raw-block">
                  <div class="doc-row raw-row">
                    <div>
                      <div class="doc-name">{{ raw.name }}</div>
                      <div class="doc-metadata"><span class="doc-path">{{ raw.path }}</span></div>
                    </div>
                    <div class="doc-actions">
                      <el-button link type="primary" size="small" @click="openFile(raw)">打开</el-button>
                    </div>
                  </div>

                  <div v-if="!raw.pages.length" class="page-block">
                    <div class="page-title">暂无已归档 OCR 产物</div>
                  </div>

                  <div v-for="page in raw.pages" :key="page.page_number" class="page-block">
                    <div class="page-title">第 {{ page.page_number }} 页（{{ page.docs.length }}）</div>
                    <div v-for="doc in page.docs" :key="doc.path" class="doc-row ocr-row">
                      <div>
                        <div class="doc-name">{{ doc.name }}</div>
                        <div class="doc-metadata"><span class="doc-path">{{ doc.path }}</span></div>
                      </div>
                      <div class="doc-actions">
                        <el-button link type="primary" size="small" @click="openFile(doc)">打开</el-button>
                      </div>
                    </div>
                  </div>
                </div>

                <div v-if="getOrphanOcr(ds, 'accessory').length" class="orphan-block">
                  <div class="page-title">未归档 OCR 文件（{{ getOrphanOcr(ds, 'accessory').length }}）</div>
                  <div v-for="doc in getOrphanOcr(ds, 'accessory')" :key="doc.path" class="doc-row ocr-row">
                    <div>
                      <div class="doc-name">{{ doc.name }}</div>
                      <div class="doc-metadata"><span class="doc-path">{{ doc.path }}</span></div>
                    </div>
                    <div class="doc-actions">
                      <el-button link type="primary" size="small" @click="openFile(doc)">打开</el-button>
                    </div>
                  </div>
                </div>
              </el-card>
            </div>
          </el-collapse-item>
        </el-collapse>

        <el-empty v-else description="暂无关联文件" />
      </div>
    </div>

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

    <el-dialog
      v-model="moveDialogVisible"
      title="移动文件"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form label-width="96px" :model="moveForm">
        <el-form-item label="文件">
          <div>
            <div class="doc-name">{{ moveDocInfo.name }}</div>
            <div class="doc-path">{{ moveDocInfo.path }}</div>
          </div>
        </el-form-item>
        <el-form-item label="目标类型">
          <el-radio-group v-model="moveForm.targetType">
            <el-radio label="product">产品</el-radio>
            <el-radio label="accessory">配件</el-radio>
          </el-radio-group>
        </el-form-item>
        <template v-if="moveForm.targetType === 'product'">
          <el-form-item label="目标产品">
            <el-select
              v-model="moveForm.productName"
              placeholder="请选择产品"
              filterable
              :loading="moveProductLoading"
              @visible-change="(val) => val && ensureProductOptions()"
            >
              <el-option
                v-for="item in moveProductOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="目标 BOM">
            <el-select
              v-model="moveForm.bomVersion"
              placeholder="请选择 BOM"
              :disabled="!moveForm.productName"
              filterable
              :loading="moveBomLoading"
            >
              <el-option
                v-for="item in moveBomOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-form-item>
        </template>
        <template v-else>
          <el-form-item label="目标配件">
            <el-select
              v-model="moveForm.accessoryName"
              placeholder="请选择配件"
              filterable
              :loading="moveAccessoryLoading"
              @visible-change="(val) => val && ensureAccessoryOptions()"
            >
              <el-option
                v-for="item in moveAccessoryOptions"
                :key="item"
                :label="item"
                :value="item"
              />
            </el-select>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="closeMoveDialog">取消</el-button>
        <el-button type="primary" :loading="moveLoading" @click="submitMove">确认移动</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="attachDialogVisible"
      title="增加文件"
      width="960px"
      :style="{ maxWidth: '92vw' }"
      :close-on-click-modal="false"
    >
      <div class="attach-dialog">
        <div class="attach-dialog__list">
          <div class="attach-dialog__list-header">
            <div class="panel-title">未匹配文件</div>
            <div class="attach-dialog__list-actions">
              <el-input
                v-model="unmatchedKeyword"
                placeholder="搜索未匹配文件"
                size="small"
                clearable
              >
                <template #prefix>
                  <el-icon class="search-icon">
                    <Search />
                  </el-icon>
                </template>
              </el-input>
              <el-button size="small" :loading="unmatchedLoading" @click="loadUnmatchedDocuments(true)">刷新</el-button>
            </div>
          </div>
          <el-table
            v-loading="unmatchedLoading"
            :data="filteredUnmatchedDocuments"
            height="320"
            highlight-current-row
            @current-change="handleSelectUnmatched"
          >
            <el-table-column type="index" width="60" label="#" />
            <el-table-column prop="name" label="文件名称" min-width="180" show-overflow-tooltip />
            <el-table-column prop="path" label="存储路径" min-width="260" show-overflow-tooltip />
          </el-table>
          <div v-if="!unmatchedLoading && !filteredUnmatchedDocuments.length" class="state">暂无未匹配文件</div>
        </div>
        <div class="attach-dialog__target">
          <el-form label-width="96px" :model="attachForm">
            <el-form-item label="已选文件">
              <div v-if="attachSelectedDoc">
                <div class="attach-dialog__selected">
                  <div class="doc-name">{{ attachSelectedDoc.name }}</div>
                  <div class="doc-path">{{ attachSelectedDoc.path }}</div>
                </div>
                <div class="attach-dialog__actions">
                  <el-button size="small" @click="handlePreviewUnmatched">查看内容</el-button>
                </div>
              </div>
              <div v-else class="state">请在左侧选择需要增加的文件</div>
            </el-form-item>
            <el-form-item label="目标类型">
              <el-radio-group v-model="attachForm.targetType">
                <el-radio label="product">产品</el-radio>
                <el-radio label="accessory">配件</el-radio>
              </el-radio-group>
            </el-form-item>
            <template v-if="attachForm.targetType === 'product'">
              <el-form-item label="目标产品">
                <el-select
                  v-model="attachForm.productName"
                  placeholder="请选择产品"
                  filterable
                  :loading="moveProductLoading"
                  @visible-change="(val) => val && ensureProductOptions()"
                >
                  <el-option
                    v-for="item in moveProductOptions"
                    :key="item"
                    :label="item"
                    :value="item"
                  />
                </el-select>
              </el-form-item>
              <el-form-item label="目标 BOM">
                <el-select
                  v-model="attachForm.bomVersion"
                  placeholder="请选择 BOM"
                  :disabled="!attachForm.productName"
                  filterable
                  :loading="attachBomLoading"
                >
                  <el-option
                    v-for="item in attachBomOptions"
                    :key="item"
                    :label="item"
                    :value="item"
                  />
                </el-select>
              </el-form-item>
            </template>
            <template v-else>
              <el-form-item label="目标配件">
                <el-select
                  v-model="attachForm.accessoryName"
                  placeholder="请选择配件"
                  filterable
                  :loading="moveAccessoryLoading"
                  @visible-change="(val) => val && ensureAccessoryOptions()"
                >
                  <el-option
                    v-for="item in moveAccessoryOptions"
                    :key="item"
                    :label="item"
                    :value="item"
                  />
                </el-select>
              </el-form-item>
            </template>
          </el-form>
        </div>
      </div>
      <template #footer>
        <el-button @click="closeAttachDialog">取消</el-button>
        <el-button type="primary" :loading="attachLoading" @click="submitAttach">确认增加</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="previewDialogVisible"
      title="未匹配文件内容"
      width="840px"
      :style="{ maxWidth: '92vw' }"
      :close-on-click-modal="false"
    >
      <div class="preview-dialog" v-loading="previewLoading">
        <div class="preview-dialog__meta">
          <div class="preview-dialog__name">{{ previewDoc.name || '未命名文件' }}</div>
          <div class="preview-dialog__path">{{ previewDoc.path || '—' }}</div>
          <div class="preview-dialog__dates">
            创建：{{ formatDate(previewDoc.created_at) }} · 更新：{{ formatDate(previewDoc.updated_at) }}
          </div>
        </div>
        <el-scrollbar class="preview-dialog__content">
          <pre>{{ previewDoc.content || '（文件内容为空）' }}</pre>
        </el-scrollbar>
      </div>
      <template #footer>
        <el-button @click="previewDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="imagePreview.visible" :title="imagePreview.title" width="720px" :close-on-click-modal="false">
      <div class="image-preview" v-loading="imagePreview.loading">
        <img v-if="imagePreview.src" :src="imagePreview.src" alt="preview" @load="onImageLoaded" @error="onImageError" />
        <div v-else class="state">暂无图片可显示</div>
      </div>
      <template #footer>
        <el-button @click="imagePreview.visible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="specsheetPreview.visible"
      title="规格页 JSON"
      width="720px"
      :close-on-click-modal="false"
    >
      <div class="specsheet-preview" v-loading="specsheetPreview.loading">
        <el-scrollbar class="specsheet-preview__scroll">
          <pre>{{ specsheetPreview.content }}</pre>
        </el-scrollbar>
      </div>
      <template #footer>
        <el-button @click="specsheetPreview.visible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, reactive, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const normalizeDocPath = (path = '') => {
  let p = String(path || '').trim()
  if (!p) return ''
  if (p.startsWith('http://') || p.startsWith('https://')) return p
  if (p.startsWith('/api/files/')) p = p.slice('/api/files/'.length)
  return p.replace(/^\/+/, '')
}

const encodePath = (path = '') =>
  String(path || '')
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/')

const resolveFileUrl = (path) => {
  const normalized = normalizeDocPath(path)
  if (!normalized) return ''
  if (normalized.startsWith('http://') || normalized.startsWith('https://')) return normalized
  return `${API_BASE_URL}/api/files/${encodePath(normalized)}`
}

const route = useRoute()
const router = useRouter()

const id = computed(() => route.params.id)
const materialCode = computed(() => route.query.materialCode || '')
const productId = computed(() => route.query.productId || '')
const productName = productId
const name = computed(() => {
  if (materialCode.value) return materialCode.value
  return route.query.label || productId.value || `产品 ${route.params.id}`
})

const boms = ref([])
const loadingBoms = ref(false)
const bomsError = ref('')
const bomKeyword = ref('')
const selectedBom = ref('')

const accessories = ref([])
const loadingAccessories = ref(false)
const accessoriesError = ref('')
const accessoryKeyword = ref('')
const selectedAccessory = ref('')

const showDocuments = ref(true)

const docKeyword = ref('')
const fileTypeFilter = ref('all')
const loadingDocuments = ref(false)
const documentsError = ref('')

const kbDatasets = ref([])
const kbSpecialDocs = reactive({ specsheet: null, manual: null, poster: null })
const kbConfigText = ref('')
const configDialogVisible = ref(false)

const configEditDialogVisible = ref(false)
const configEditText = ref('')
const configEditSaving = ref(false)

const openConfigDialog = () => {
  if (!kbConfigText.value) {
    ElMessage.info('暂无产品配置')
    return
  }
  configDialogVisible.value = true
}

const openConfigEditDialog = () => {
  if (!selectedBom.value || !effectiveProductId.value) {
    ElMessage.info('请选择 BOM 后再编辑')
    return
  }
  configEditText.value = kbConfigText.value || ''
  configEditDialogVisible.value = true
}

const closeConfigEditDialog = () => {
  configEditDialogVisible.value = false
  configEditText.value = ''
  configEditSaving.value = false
}

const saveConfigEdit = async () => {
  if (!effectiveProductId.value) return
  configEditSaving.value = true
  try {
    const { updateProductConfig, getKbOverview } = await import('@/services/api')
    await updateProductConfig(effectiveProductId.value, configEditText.value)
    ElMessage.success('已保存产品配置')
    configEditDialogVisible.value = false

    // refresh from backend to ensure UI is consistent with DB
    const data = await getKbOverview(effectiveProductId.value)
    kbConfigText.value = data?.product_config?.config_text_zh || ''
  } catch (error) {
    ElMessage.error(error?.message || '保存失败')
    console.error(error)
  } finally {
    configEditSaving.value = false
  }
}

const copyConfig = async () => {
  if (!kbConfigText.value) return
  try {
    await navigator.clipboard.writeText(kbConfigText.value)
    ElMessage.success('已复制产品配置')
  } catch (error) {
    ElMessage.error('复制失败')
    console.error(error)
  }
}

const effectiveProductId = computed(() => {
  if (materialCode.value && selectedBom.value) {
    return `${materialCode.value}_${selectedBom.value}`
  }
  return productId.value || ''
})

const loadDocuments = async () => {
  if (!selectedBom.value) return
  if (!effectiveProductId.value) return
  loadingDocuments.value = true
  documentsError.value = ''
  kbDatasets.value = []
  kbSpecialDocs.specsheet = null
  kbSpecialDocs.manual = null
  kbSpecialDocs.poster = null
  kbConfigText.value = ''
  configDialogVisible.value = false
  configEditDialogVisible.value = false
  try {
    const { getKbOverview } = await import('@/services/api')
    const data = await getKbOverview(effectiveProductId.value)
    kbDatasets.value = Array.isArray(data?.datasets) ? data.datasets : []
    const special = data?.special_docs || {}
    kbSpecialDocs.specsheet = special.specsheet || null
    kbSpecialDocs.manual = special.manual || null
    kbSpecialDocs.poster = special.poster || null
    kbConfigText.value = data?.product_config?.config_text_zh || ''
  } catch (error) {
    documentsError.value = error?.message || '加载文件失败'
    console.error(error)
  } finally {
    loadingDocuments.value = false
  }
}

const loadAccessoryDocuments = async (..._args) => {}

const getRawWithOcr = (dataset, scope) => {
  const folders = dataset?.folders || {}
  const rawDocs = scope === 'product' ? (folders.product_raw || []) : (folders.accessory_raw || [])
  const ocrDocs = scope === 'product' ? (folders.product_ocr || []) : (folders.accessory_ocr || [])

  const stemToRawPath = new Map()
  for (const raw of rawDocs) {
    const name = String(raw?.name || '')
    const stem = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : name
    const key = String(stem || '').trim().toLowerCase()
    if (key && raw?.path) stemToRawPath.set(key, raw.path)
  }

  const inferParentFromPath = (p) => {
    const lower = String(p || '').toLowerCase()
    if (!lower) return ''
    // manual_ocr_results/<sid>/products/<stem>/...
    const seg = scope === 'product' ? '/products/' : '/accessories/'
    const idx = lower.indexOf(seg)
    if (idx < 0) return ''
    const rest = lower.slice(idx + seg.length)
    const stem = rest.split('/')[0]
    if (!stem) return ''
    return stemToRawPath.get(stem) || ''
  }

  const inferPageNumberFromPath = (p) => {
    const m = String(p || '').match(/___page(\d{1,6})/i)
    if (!m) return 1
    const v = parseInt(m[1], 10)
    return Number.isFinite(v) && v > 0 ? v : 1
  }

  const byParent = new Map()
  for (const doc of ocrDocs) {
    const explicitParent = String(doc?.parent_raw_path || '').trim()
    const parent = explicitParent || inferParentFromPath(doc?.path)
    if (!parent) continue
    if (!byParent.has(parent)) byParent.set(parent, [])
    byParent.get(parent).push(doc)
  }

  return rawDocs.map((raw) => {
    const parentPath = raw.path
    const children = byParent.get(parentPath) || []
    const pagesMap = new Map()
    for (const d of children) {
      let pn = Number(d?.page_number || 0)
      if (!pn || pn < 1) pn = inferPageNumberFromPath(d?.path)
      if (!pagesMap.has(pn)) pagesMap.set(pn, [])
      pagesMap.get(pn).push(d)
    }
    const pages = Array.from(pagesMap.entries())
      .sort((a, b) => a[0] - b[0])
      .map(([page_number, docs]) => ({
        page_number,
        docs: docs.slice().sort((a, b) => String(a.name || '').localeCompare(String(b.name || '')))
      }))
    return { ...raw, pages }
  })
}

const getOrphanOcr = (dataset, scope) => {
  const folders = dataset?.folders || {}
  const ocrDocs = scope === 'product' ? (folders.product_ocr || []) : (folders.accessory_ocr || [])
  const rawDocs = scope === 'product' ? (folders.product_raw || []) : (folders.accessory_raw || [])
  const stems = new Set(
    rawDocs
      .map((raw) => {
        const name = String(raw?.name || '')
        const stem = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : name
        return String(stem || '').trim().toLowerCase()
      })
      .filter(Boolean)
  )

  const inferParentExists = (p) => {
    const lower = String(p || '').toLowerCase()
    if (!lower) return false
    const seg = scope === 'product' ? '/products/' : '/accessories/'
    const idx = lower.indexOf(seg)
    if (idx < 0) return false
    const rest = lower.slice(idx + seg.length)
    const stem = rest.split('/')[0]
    if (!stem) return false
    return stems.has(stem)
  }

  const orphans = ocrDocs.filter((doc) => {
    const explicit = String(doc?.parent_raw_path || '').trim()
    if (explicit) return false
    return !inferParentExists(doc?.path)
  })
  return orphans
    .slice()
    .sort((a, b) => String(a?.name || '').localeCompare(String(b?.name || '')))
}

const specsheetPreview = reactive({
  visible: false,
  loading: false,
  content: ''
})

const selectBom = (bom) => {
  selectedBom.value = bom
  selectedAccessory.value = ''
  loadAccessories()
  loadDocuments()
}

const showManualTree = computed(() => false)

const manualBaseDocs = computed(() => (showManualTree.value ? filteredDocuments.value : []))
const manualUploads = computed(() => manualBaseDocs.value.filter((doc) => doc.category === 'manual_upload'))
const manualTruthFiles = computed(() => manualBaseDocs.value.filter((doc) => doc.category === 'manual_truth'))
const manualOcrArtifacts = computed(() => manualBaseDocs.value.filter((doc) => doc.category === 'manual_ocr_artifact'))

const manualUploadNodes = computed(() => {
  const byParent = new Map()
  const pageByParent = new Map()
  const uploadStemEntries = manualUploads.value
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

  manualOcrArtifacts.value.forEach((doc) => {
    const parent = doc.parent_path || inferParent(doc) || ''
    if (!byParent.has(parent)) byParent.set(parent, [])
    byParent.get(parent).push(doc)

    const rawPage = doc.page_number
    const pageNumber = typeof rawPage === 'number' && Number.isFinite(rawPage) ? rawPage : null
    if (!pageByParent.has(parent)) pageByParent.set(parent, new Map())
    const pageMap = pageByParent.get(parent)
    const pageKey = pageNumber ?? 'unknown'
    if (!pageMap.has(pageKey)) pageMap.set(pageKey, [])
    pageMap.get(pageKey).push(doc)
  })

  return manualUploads.value.map((upload) => {
    const children = byParent.get(upload.path) || []
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
      children: children.slice().sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''))),
      pages: sortedPages,
    }
  })
})

const manualOrphanArtifacts = computed(() => {
  const uploadPaths = new Set(manualUploads.value.map((u) => u.path))
  return manualOcrArtifacts.value.filter((doc) => {
    const parent = doc.parent_path || ''
    if (parent && uploadPaths.has(parent)) return false
    const inferred = (() => {
      const p = String(doc?.path || '')
      if (!p) return ''
      const lower = p.toLowerCase()
      for (const upload of manualUploads.value) {
        const name = String(upload.name || '')
        const stem = name.includes('.') ? name.slice(0, name.lastIndexOf('.')) : name
        if (stem && lower.includes(`/products/${stem.toLowerCase()}/`)) return upload.path
      }
      return ''
    })()
    return !inferred
  })
})

const manualCollapseActive = ref(['uploads', 'truth'])
const manualUploadActive = ref([])

const filteredBoms = computed(() => {
  const kw = bomKeyword.value.trim().toLowerCase()
  if (!kw) return boms.value
  return boms.value.filter((code) => String(code).toLowerCase().includes(kw))
})

const filteredDocuments = computed(() => [])

const formatDocType = (type) => {
  if (type === 'image') return '图片'
  if (type === 'image_embedded') return '文档图片'
  if (type === 'specsheet') return '规格页'
  return '文件'
}

const openFile = (doc) => {
  const p = normalizeDocPath(doc?.path)
  if (!p) {
    ElMessage.warning('无法打开：缺少文件路径')
    return
  }
  window.open(resolveFileUrl(p), '_blank')
}

const filteredAccessories = computed(() => {
  if (!accessoryKeyword.value.trim()) return accessories.value
  const kw = accessoryKeyword.value.trim().toLowerCase()
  return accessories.value.filter((item) =>
    String(item).toLowerCase().includes(kw)
  )
})

const documentSectionTitle = computed(() =>
  selectedAccessory.value ? '配件关联文件' : '产品关联文件'
)

const loadBoms = async () => {
  if (materialCode.value) {
    loadingBoms.value = true
    bomsError.value = ''
    try {
      const { getBomsByMaterial } = await import('@/services/api')
      boms.value = await getBomsByMaterial(materialCode.value)
      if (!boms.value.length) {
        bomsError.value = '该物料暂无 BOM 信息'
        selectedBom.value = ''
      } else {
        if (!selectedBom.value) {
          selectedBom.value = boms.value[0]
        }
      }
    } catch (error) {
      bomsError.value = '加载 BOM 列表失败，请稍后重试'
      console.error(error)
    } finally {
      loadingBoms.value = false
    }

    if (selectedBom.value) {
      await loadAccessories()
    }
    return
  }

  if (!productId.value) {
    bomsError.value = '缺少产品ID'
    return
  }
  loadingBoms.value = true
  bomsError.value = ''
  try {
    const { getBomsByProduct } = await import('@/services/api')
    boms.value = await getBomsByProduct(productId.value)
    if (!boms.value.length) {
      bomsError.value = '该产品暂无 BOM 信息'
      selectedBom.value = ''
    } else {
      if (!selectedBom.value) {
        selectedBom.value = boms.value[0]
      }
    }
  } catch (error) {
    bomsError.value = '加载 BOM 列表失败，请稍后重试'
    console.error(error)
  } finally {
    loadingBoms.value = false
  }

  if (selectedBom.value) {
    await loadAccessories()
  }
}

const loadAccessories = async () => {
  if (materialCode.value) {
    if (!materialCode.value || !selectedBom.value) return
    loadingAccessories.value = true
    accessoriesError.value = ''
    try {
      const { getAccessoriesZhByMaterialBom } = await import('@/services/api')
      accessories.value = await getAccessoriesZhByMaterialBom(materialCode.value, selectedBom.value)
      accessoryKeyword.value = ''
    } catch (error) {
      accessoriesError.value = '加载配件失败'
      accessories.value = []
      console.error(error)
    } finally {
      loadingAccessories.value = false
    }
    return
  }

  if (!productId.value || !selectedBom.value) return
  loadingAccessories.value = true
  accessoriesError.value = ''
  try {
    const { getAccessoriesByProductBom } = await import('@/services/api')
    accessories.value = await getAccessoriesByProductBom(productId.value, selectedBom.value)
    accessoryKeyword.value = ''
  } catch (error) {
    accessoriesError.value = '加载配件失败'
    accessories.value = []
    console.error(error)
  } finally {
    loadingAccessories.value = false
  }
}

const toggleAccessory = (name) => {
  if (selectedAccessory.value === name) {
    selectedAccessory.value = ''
    return
  }
  selectedAccessory.value = name
}

const clearAccessorySelection = () => {
  selectedAccessory.value = ''
}

const openSpecsheetPreview = async () => {
  if (!productName.value || !selectedBom.value) {
    ElMessage.warning('请选择 BOM 后再查看规格页')
    return
  }
  specsheetPreview.visible = true
  specsheetPreview.loading = true
  specsheetPreview.content = ''
  try {
    const { getSpecsheet } = await import('@/services/api')
    const specsheet = await getSpecsheet(productName.value, selectedBom.value)
    specsheetPreview.content = JSON.stringify(specsheet ?? {}, null, 2)
  } catch (error) {
    specsheetPreview.content = '加载规格页失败，请稍后重试'
    console.error(error)
  } finally {
    specsheetPreview.loading = false
  }
}

const editDialogVisible = ref(false)
const editLoading = ref(false)
const originalDocName = ref('')
const editForm = reactive({
  path: '',
  name: '',
  content: '',
})

const refreshDocuments = () => {
  if (selectedAccessory.value) {
    loadAccessoryDocuments(selectedAccessory.value, { preserveFilter: true })
  } else {
    loadDocuments({ preserveFilter: true })
  }
}

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
    const payload = {
      content: editForm.content,
    }
    if (editForm.name && editForm.name !== originalDocName.value) {
      payload.new_name = editForm.name
    }
    const { updateDocument } = await import('@/services/api')
    await updateDocument(editForm.path, payload)
    ElMessage.success('文件已更新')
    editDialogVisible.value = false
    refreshDocuments()
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
        refreshDocuments()
      } catch (error) {
        ElMessage.error(error?.message || '删除失败')
        console.error(error)
      }
    })
    .catch(() => {})
}

const moveDialogVisible = ref(false)
const moveLoading = ref(false)
const moveDocInfo = reactive({ path: '', name: '' })
const moveForm = reactive({
  targetType: 'product',
  productName: '',
  bomVersion: '',
  accessoryName: '',
})
const moveProductOptions = ref([])
const moveBomOptions = ref([])
const moveAccessoryOptions = ref([])
const moveProductLoading = ref(false)
const moveBomLoading = ref(false)
const moveAccessoryLoading = ref(false)

const resetMoveForm = () => {
  moveForm.targetType = 'product'
  moveForm.productName = productName.value || ''
  moveForm.bomVersion = selectedBom.value || ''
  moveForm.accessoryName = ''
}

const ensureProductOptions = async () => {
  if (moveProductOptions.value.length || moveProductLoading.value) return
  moveProductLoading.value = true
  try {
    const { getProducts } = await import('@/services/api')
    moveProductOptions.value = await getProducts()
  } catch (error) {
    ElMessage.error('加载产品列表失败')
    console.error(error)
  } finally {
    moveProductLoading.value = false
  }
}

const ensureAccessoryOptions = async () => {
  if (moveAccessoryOptions.value.length || moveAccessoryLoading.value) return
  moveAccessoryLoading.value = true
  try {
    const { getAccessories } = await import('@/services/api')
    moveAccessoryOptions.value = await getAccessories()
  } catch (error) {
    ElMessage.error('加载配件列表失败')
    console.error(error)
  } finally {
    moveAccessoryLoading.value = false
  }
}

const loadMoveBoms = async (product) => {
  if (!product) {
    moveBomOptions.value = []
    moveForm.bomVersion = ''
    return
  }
  moveBomLoading.value = true
  try {
    const { getBomsByProduct } = await import('@/services/api')
    moveBomOptions.value = await getBomsByProduct(product)
    if (!moveBomOptions.value.includes(moveForm.bomVersion)) {
      moveForm.bomVersion = ''
    }
  } catch (error) {
    ElMessage.error('加载产品 BOM 失败')
    console.error(error)
  } finally {
    moveBomLoading.value = false
  }
}

const openMoveDialog = async (doc) => {
  moveDocInfo.path = doc.path
  moveDocInfo.name = doc.name
  resetMoveForm()
  moveDialogVisible.value = true
  await ensureProductOptions()
  if (moveForm.productName) {
    loadMoveBoms(moveForm.productName)
  }
}

const closeMoveDialog = () => {
  if (moveLoading.value) return
  moveDialogVisible.value = false
}

const submitMove = async () => {
  const payload = { target_type: moveForm.targetType }
  if (moveForm.targetType === 'product') {
    if (!moveForm.productName) {
      ElMessage.warning('请选择目标产品')
      return
    }
    if (!moveForm.bomVersion) {
      ElMessage.warning('请选择目标 BOM')
      return
    }
    payload.product_name = moveForm.productName
    payload.bom_version = moveForm.bomVersion
  } else {
    if (!moveForm.accessoryName) {
      ElMessage.warning('请选择目标配件')
      return
    }
    payload.accessory_name = moveForm.accessoryName
  }

  moveLoading.value = true
  try {
    const { moveDocument } = await import('@/services/api')
    await moveDocument(moveDocInfo.path, payload)
    ElMessage.success('文件已移动')
    moveDialogVisible.value = false
    refreshDocuments()
  } catch (error) {
    ElMessage.error(error?.message || '移动文件失败')
    console.error(error)
  } finally {
    moveLoading.value = false
  }
}

const attachDialogVisible = ref(false)
const attachLoading = ref(false)
const unmatchedLoading = ref(false)
const unmatchedList = ref([])
const unmatchedKeyword = ref('')
const attachSelectedDoc = ref(null)
const attachForm = reactive({
  targetType: 'product',
  productName: '',
  bomVersion: '',
  accessoryName: '',
})
const attachBomOptions = ref([])
const attachBomLoading = ref(false)
const previewDialogVisible = ref(false)
const previewLoading = ref(false)
const previewDoc = reactive({
  name: '',
  path: '',
  content: '',
  created_at: '',
  updated_at: '',
})
const imagePreview = reactive({
  visible: false,
  title: '图片预览',
  src: '',
  loading: false,
})

const filteredUnmatchedDocuments = computed(() => {
  const kw = unmatchedKeyword.value.trim().toLowerCase()
  if (!kw) return unmatchedList.value
  return unmatchedList.value.filter((item) =>
    item.name?.toLowerCase().includes(kw) || item.path?.toLowerCase().includes(kw)
  )
})

const resetAttachForm = () => {
  attachForm.targetType = 'product'
  attachForm.productName = productName.value || ''
  attachForm.bomVersion = selectedBom.value || ''
  attachForm.accessoryName = ''
  attachSelectedDoc.value = null
  attachBomOptions.value = []
}

const loadUnmatchedDocuments = async (force = false) => {
  unmatchedLoading.value = true
  try {
    const { getUnmatchedDocuments } = await import('@/services/api')
    unmatchedList.value = await getUnmatchedDocuments()
    if (force) {
      ElMessage.success('未匹配文件已刷新')
    }
  } catch (error) {
    ElMessage.error('加载未匹配文件失败')
    console.error(error)
  } finally {
    unmatchedLoading.value = false
  }
}

const loadAttachBoms = async (product) => {
  if (!product) {
    attachBomOptions.value = []
    attachForm.bomVersion = ''
    return
  }
  attachBomLoading.value = true
  try {
    const { getBomsByProduct } = await import('@/services/api')
    attachBomOptions.value = await getBomsByProduct(product)
    if (!attachBomOptions.value.includes(attachForm.bomVersion)) {
      attachForm.bomVersion = ''
    }
  } catch (error) {
    ElMessage.error('加载产品 BOM 失败')
    console.error(error)
  } finally {
    attachBomLoading.value = false
  }
}

const openAttachDialog = async () => {
  if (!selectedBom.value) {
    ElMessage.warning('请先选择 BOM 再增加文件')
    return
  }
  attachDialogVisible.value = true
  resetAttachForm()
  await ensureProductOptions()
  if (!unmatchedList.value.length) {
    loadUnmatchedDocuments()
  }
  if (attachForm.productName) {
    loadAttachBoms(attachForm.productName)
  }
}

const closeAttachDialog = () => {
  if (attachLoading.value) return
  attachDialogVisible.value = false
}

const handleSelectUnmatched = (row) => {
  attachSelectedDoc.value = row || null
}

const handlePreviewUnmatched = async () => {
  if (!attachSelectedDoc.value) {
    ElMessage.info('请选择未匹配文件后再预览')
    return
  }
  previewDialogVisible.value = true
  previewLoading.value = true
  previewDoc.name = attachSelectedDoc.value.name
  previewDoc.path = attachSelectedDoc.value.path
  previewDoc.content = ''
  previewDoc.created_at = attachSelectedDoc.value.created_at
  previewDoc.updated_at = attachSelectedDoc.value.updated_at
  try {
    const { getUnmatchedDocumentDetail } = await import('@/services/api')
    const detail = await getUnmatchedDocumentDetail(attachSelectedDoc.value.path)
    previewDoc.name = detail.name || attachSelectedDoc.value.name
    previewDoc.path = detail.path
    previewDoc.content = detail.content || ''
    previewDoc.created_at = detail.created_at
    previewDoc.updated_at = detail.updated_at
  } catch (error) {
    previewDialogVisible.value = false
    ElMessage.error('加载未匹配文件内容失败')
    console.error(error)
  } finally {
    previewLoading.value = false
  }
}

const submitAttach = async () => {
  if (!attachSelectedDoc.value) {
    ElMessage.warning('请选择需要增加的文件')
    return
  }

  const payload = {
    doc_path: attachSelectedDoc.value.path,
    target_type: attachForm.targetType,
  }

  if (attachForm.targetType === 'product') {
    if (!attachForm.productName) {
      ElMessage.warning('请选择目标产品')
      return
    }
    if (!attachForm.bomVersion) {
      ElMessage.warning('请选择目标 BOM')
      return
    }
    payload.product_name = attachForm.productName
    payload.bom_version = attachForm.bomVersion
  } else {
    if (!attachForm.accessoryName) {
      ElMessage.warning('请选择目标配件')
      return
    }
    payload.accessory_name = attachForm.accessoryName
  }

  attachLoading.value = true
  try {
    const { attachDocument } = await import('@/services/api')
    await attachDocument(payload)
    ElMessage.success('文件已增加')
    attachDialogVisible.value = false
    refreshDocuments()
    loadUnmatchedDocuments()
  } catch (error) {
    ElMessage.error(error?.message || '增加文件失败')
    console.error(error)
  } finally {
    attachLoading.value = false
  }
}

const openImagePreview = (doc) => {
  if (!doc.path) {
    ElMessage.warning('无法预览：缺少文件路径')
    return
  }
  imagePreview.title = doc.name || '图片预览'
  imagePreview.src = resolveFileUrl(doc.path)
  imagePreview.visible = true
  imagePreview.loading = true
}

const onImageLoaded = () => {
  imagePreview.loading = false
}

const onImageError = () => {
  imagePreview.loading = false
  ElMessage.error('图片加载失败')
}

watch(
  () => moveForm.productName,
  (value) => {
    if (moveForm.targetType === 'product') {
      loadMoveBoms(value)
    }
  }
)

watch(
  () => moveForm.targetType,
  (value) => {
    if (value === 'product') {
      moveForm.accessoryName = ''
      if (moveForm.productName) loadMoveBoms(moveForm.productName)
    } else {
      moveForm.productName = ''
      moveForm.bomVersion = ''
      ensureAccessoryOptions()
    }
  }
)

watch(
  () => attachForm.productName,
  (value) => {
    if (attachForm.targetType === 'product') {
      loadAttachBoms(value)
    }
  }
)

watch(
  () => attachForm.targetType,
  (value) => {
    if (value === 'product') {
      attachForm.accessoryName = ''
      if (attachForm.productName) loadAttachBoms(attachForm.productName)
    } else {
      attachForm.productName = ''
      attachForm.bomVersion = ''
      ensureAccessoryOptions()
    }
  }
)

const goBack = () => {
  router.push({
    name: 'Home',
    query: { tab: 'kbSearch' }
  })
}

const formatDate = (value) => {
  if (!value) return '—'
  try {
    return new Date(value).toLocaleDateString()
  } catch {
    return value
  }
}

onMounted(() => {
  loadBoms()
})
</script>

<style scoped>
.page {
  width: 100%;
  padding: 24px;
  display: grid;
  gap: 16px;
}

.topbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.title {
  font-size: 20px;
  font-weight: 700;
}

.panel {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 4px 24px rgba(0,0,0,0.06);
  display: grid;
  gap: 12px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.panel-title {
  font-weight: 600;
}

.panel-sub {
  font-size: 12px;
  color: #999;
}

.search-input {
  max-width: 320px;
}

.search-icon {
  color: #c0c4cc;
}

.state {
  padding: 20px;
  text-align: center;
  color: #666;
}

.state.error {
  color: #f56c6c;
}

.bom-tags,
.product-tags,
.document-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.bom-tag,
.product-tag {
  cursor: pointer;
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

.doc-name {
  font-weight: 600;
}

.doc-path {
  font-size: 12px;
  color: #909399;
}

.doc-meta {
  font-size: 12px;
  color: #999;
  display: flex;
  align-items: center;
  gap: 16px;
}

.doc-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.doc-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.manual-file-row {
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(260px, 2fr) auto;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.manual-file-name {
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.manual-file-path {
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.manual-file-actions {
  display: flex;
  justify-content: flex-end;
}

.manual-tree-title {
  font-weight: 600;
}

.manual-tree {
  margin-top: 16px;
}

.manual-tree-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-weight: 600;
}

.manual-tree-sub {
  font-weight: 400;
  color: #909399;
  font-size: 12px;
}

.dataset-groups {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.group-note {
  font-size: 12px;
  color: #909399;
  margin: 6px 0 10px;
}

.raw-block {
  padding: 10px 0;
  border-top: 1px dashed #ebeef5;
}

.raw-block:first-of-type {
  border-top: none;
  padding-top: 0;
}

.raw-row {
  background: #fafbfd;
  border: 1px solid #f0f2f5;
  border-radius: 10px;
  padding: 10px 12px;
}

.page-block {
  margin: 10px 0 0 16px;
  padding-left: 12px;
  border-left: 2px solid #e5e7eb;
}

.page-title {
  font-size: 12px;
  color: #606266;
  margin-bottom: 6px;
}

.ocr-row {
  padding-left: 6px;
}

.orphan-block {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #ebeef5;
}

.manual-tree {
  width: 100%;
  flex: 1 1 100%;
}

.manual-tree-inner {
  width: 100%;
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

.attach-dialog {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 16px;
}

.attach-dialog__list {
  border-right: 1px solid #f0f0f0;
  padding-right: 16px;
}

.attach-dialog__list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.attach-dialog__list-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.attach-dialog__target {
  padding-left: 8px;
  max-height: 360px;
  overflow: auto;
}

.attach-dialog__selected {
  background: #f7f9fc;
  border: 1px solid #e6e8f0;
  border-radius: 8px;
  padding: 12px;
  display: grid;
  gap: 8px;
  max-height: 140px;
  overflow: auto;
  word-break: break-all;
}

.attach-dialog__selected .doc-name {
  font-size: 14px;
  font-weight: 600;
}

.attach-dialog__selected .doc-path {
  font-size: 12px;
  color: #909399;
  word-break: break-all;
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

 .config-dialog__content {
  height: 60vh;
 }

 .config-dialog__content :deep(.el-scrollbar__wrap) {
  height: 60vh;
 }

 .config-text {
  white-space: pre-wrap;
  word-break: break-word;
 }
</style>
