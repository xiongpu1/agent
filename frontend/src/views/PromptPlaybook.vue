<template>
  <div class="playbook-page">
    <div class="page-header">
      <div>
        <div class="breadcrumb" role="button" tabindex="0" @click="goBack" @keydown.enter.space.prevent="goBack">← 返回产品知识库</div>
        <h1 class="title">提示词优化工作台</h1>
        <p class="subtitle">同步规格页 / 说明书 / 海报 Playbook，支撑 ACE 技术快速生成与迭代。</p>
      </div>
      <el-button type="primary" :loading="loadingPlaybooks" @click="loadPlaybooks(true)">刷新数据</el-button>
    </div>

    <div class="workspace-grid">
      <div class="sidebar">
        <div class="sidebar-head">
          <div class="sidebar-title">Playbook Explorer</div>
          <div class="sidebar-sub">筛选产品并挑选样本构建 dataset，右侧可查看规则与历史</div>
        </div>
        <el-input v-model="productFilter" placeholder="输入产品名称（如 Massern）" clearable class="sidebar-search" />
        <el-scrollbar class="product-scroll">
          <el-checkbox-group v-model="selectedProducts">
            <el-checkbox
              v-for="product in filteredProducts"
              :key="product"
              :label="product"
            >
              {{ product }}
            </el-checkbox>
          </el-checkbox-group>
        </el-scrollbar>

        <el-card class="builder-card" shadow="never">
          <template #header>
            <div class="builder-header">
              <div>
                <div class="builder-title">待提交数据集</div>
                <div class="builder-sub">命名当前样本集，触发 ACE 时整体提交</div>
              </div>
              <el-button size="small" type="warning" text @click="clearDataset" :disabled="!builderSamples.length">清空</el-button>
            </div>
          </template>
          <el-form label-width="60px" size="small">
            <el-form-item label="名称">
              <el-input v-model="datasetName" placeholder="如 Massern_spec_v1" maxlength="60" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="datasetDescription" placeholder="选填，描述当前目标" maxlength="120" />
            </el-form-item>
          </el-form>
          <el-alert v-if="!builderSamples.length" title="请在下方 Playbook 中点击“加入数据集”" type="info" :closable="false" show-icon />
          <el-timeline v-else>
            <el-timeline-item
              v-for="sample in builderSamples"
              :key="sample.key"
              :timestamp="sample.product_name"
              type="primary"
            >
              <div class="builder-item">
                <div class="builder-item__preview">{{ sample.context_preview || sample.ground_truth_preview || '—' }}</div>
                <el-button link type="danger" size="small" @click="removeSample(sample.key)">移除</el-button>
              </div>
            </el-timeline-item>
          </el-timeline>
        </el-card>
      </div>

      <div class="main-panel">
        <el-card class="playbook-card">
          <template #header>
            <div class="panel-header">
              <div>
                <div class="panel-title">{{ activePlaybookLabel }} Playbook</div>
                <div class="panel-sub">切换标签查看数据库已有的规格页 / 说明书 / 海报文本</div>
              </div>
              <el-segmented v-model="activePlaybookType" :options="playbookOptions" />
            </div>
          </template>

          <div v-if="playbookError" class="error-state">{{ playbookError }}</div>
          <el-skeleton v-else-if="loadingPlaybooks" animated :rows="6" />
          <div v-else-if="!displayPlaybooks.length" class="empty-state">
            <el-empty description="选择产品后加载 Playbook" />
          </div>
          <div v-else class="playbook-content">
            <el-collapse v-model="expandedProduct" accordion>
              <el-collapse-item
                v-for="group in displayPlaybooks"
                :key="group.folder_name"
                :name="group.folder_name"
              >
                <template #title>
                  <div class="product-title">{{ group.product_name }}</div>
                </template>
                <div class="playbook-meta">
                  <el-tag size="small" type="info">{{ activePlaybookLabel }}</el-tag>
                  <div class="meta-spacer" />
                  <span v-if="!canSelectPlaybook(group)" class="meta-hint">缺少 Generate / Truth，无法加入 dataset</span>
                  <el-button
                    v-else
                    size="small"
                    type="primary"
                    link
                    @click.stop="appendSample(group)"
                  >加入数据集</el-button>
                </div>
                <div class="playbook-split">
                  <div class="playbook-block">
                    <div class="block-head">Generate</div>
                    <el-scrollbar class="text-area">
                      <pre>{{ extractPlaybookText(group, 'generate') || '暂无 generate 文本' }}</pre>
                    </el-scrollbar>
                  </div>
                  <div class="playbook-block">
                    <div class="block-head">Truth</div>
                    <el-scrollbar class="text-area">
                      <pre>{{ extractPlaybookText(group, 'truth') || '暂无 truth 文本' }}</pre>
                    </el-scrollbar>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
          </div>
        </el-card>

        <el-card class="dataset-card">
          <template #header>
            <div class="panel-header">
              <div>
                <div class="panel-title">样本池</div>
                <div class="panel-sub">可加入数据集的 Playbook</div>
              </div>
              <div class="pool-actions">
                <el-button size="small" type="primary" text @click="addSelectedSamples" :disabled="!selectedPoolKeys.length">加入所选</el-button>
                <el-button size="small" text @click="clearSelectedSamples" :disabled="!selectedPoolKeys.length">清空选择</el-button>
                <el-button size="small" text @click="addAllSamples" :disabled="!availableDatasetRows.length">全选加入</el-button>
                <el-button size="small" text @click="logsDialogVisible = true" :disabled="!hasAceLogs">查看运行日志</el-button>
                <el-button type="success" :loading="aceSubmitting" @click="handleAceSubmit" :disabled="!canSubmitDataset">触发 ACE</el-button>
              </div>
            </div>
          </template>
          <el-table
            :data="availableDatasetRows"
            row-key="key"
            style="width: 100%"
            border
            size="small"
            table-layout="fixed"
            empty-text="暂无可用样本"
            @selection-change="handlePoolSelectionChange"
            height="320"
          >
            <el-table-column type="selection" width="60" reserve-selection />
            <el-table-column prop="product_name" label="产品" width="200" show-overflow-tooltip class-name="clip-cell" />
            <el-table-column label="类型" width="100">
              <template #default="scope">
                <el-tag>{{ playbookLabelMap[scope.row.playbook_type] || scope.row.playbook_type }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="question_preview" label="系统提示词" show-overflow-tooltip class-name="clip-cell" />
            <el-table-column prop="context_preview" label="用户提示词" show-overflow-tooltip class-name="clip-cell" />
            <el-table-column prop="ground_truth_preview" label="Ground Truth" show-overflow-tooltip class-name="clip-cell" />
          </el-table>
        </el-card>

        <div class="insight-grid">
          <el-card class="history-card">
            <template #header>
              <div class="panel-header">
                <div>
                  <div class="panel-title">ACE Playbook 历史</div>
                  <div class="panel-sub">记录每次提交的 dataset，查看生成/真值摘要</div>
                </div>
                <el-button size="small" text @click="loadDatasets">刷新历史</el-button>
              </div>
            </template>
            <el-empty v-if="!datasetHistory.length" description="尚未提交 dataset" />
            <el-scrollbar v-else class="history-scroll">
              <el-timeline>
                <el-timeline-item
                  v-for="dataset in datasetHistory"
                  :key="datasetIdentifier(dataset)"
                  :timestamp="formatTimestamp(dataset.submitted_at)"
                  :color="playbookColor(dataset.playbook_type)"
                >
                  <div class="history-entry" @click="selectDatasetRules(dataset)" :class="{ 'history-entry--active': isDatasetSelected(dataset) }">
                    <div class="entry-header">
                      <strong>{{ dataset.dataset_name }}</strong>
                      <el-tag size="small">{{ playbookLabelMap[dataset.playbook_type] }}</el-tag>
                      <el-tag size="small" type="info">{{ dataset.sample_count }} 条样本</el-tag>
                      <el-button type="danger" link size="small" @click.stop="confirmDeleteDataset(dataset)">删除</el-button>
                    </div>
                    <div class="entry-products">位置：{{ dataset.file_path }}</div>
                    <div class="entry-products" v-if="dataset.description">备注：{{ dataset.description }}</div>
                    <el-collapse class="history-collapse">
                      <el-collapse-item title="查看样本详情">
                        <div v-for="sample in dataset.samples" :key="sample.product_name" class="history-sample">
                          <div class="history-sample__title">{{ sample.product_name }}</div>
                          <div class="history-sample__preview">
                            <span>Question：</span>{{ sample.question_preview || '—' }}
                          </div>
                          <div class="history-sample__preview">
                            <span>Context：</span>{{ sample.context_preview || '—' }}
                          </div>
                          <div class="history-sample__preview">
                            <span>Ground Truth：</span>{{ sample.ground_truth_preview || '—' }}
                          </div>
                        </div>
                      </el-collapse-item>
                    </el-collapse>
                  </div>
                </el-timeline-item>
              </el-timeline>
            </el-scrollbar>
          </el-card>

          <el-card class="rules-card">
            <template #header>
              <div class="panel-header">
                <div>
                  <div class="panel-title">Playbook 规则</div>
                  <div class="panel-sub">{{ activeRulesLabel }}</div>
                </div>
                <div class="rules-actions">
                  <el-button size="small" text @click="showGlobalRules" :disabled="activeRulesSource.type === 'global'">查看全局</el-button>
                  <el-button size="small" text @click="loadRules">刷新规则</el-button>
                </div>
              </div>
            </template>
            <div class="rules-body">
              <el-empty v-if="!displayedRules.length" :description="rulesEmptyDescription" />
              <el-scrollbar v-else class="rules-scroll" height="320">
                <div v-for="(rule, index) in displayedRules" :key="rule.id || index" class="rule-item">
                  <div class="rule-text" :title="rule.content">
                    <span class="rule-index">#{{ index + 1 }}</span>
                    <span class="rule-snippet">{{ rule.content }}</span>
                  </div>
                  <el-button
                    v-if="isGlobalRulesView && rule.id"
                    size="small"
                    type="danger"
                    link
                    :loading="deletingRuleId === rule.id"
                    @click="handleDeleteGlobalRule(rule)"
                  >
                    删除
                  </el-button>
                </div>
              </el-scrollbar>
            </div>
          </el-card>
        </div>
      </div>
    </div>
    <el-dialog
      v-model="logsDialogVisible"
      title="ACE 运行日志"
      width="80%"
      top="5vh"
    >
      <el-empty v-if="!aceRunLogs.length" description="暂无运行日志" />
      <el-scrollbar v-else class="logs-scroll" height="60vh">
        <div
          v-for="(log, index) in aceRunLogs"
          :key="log.sample?.key || index"
          class="log-entry"
        >
          <div class="log-entry__header">
            <div>
              <strong>样本 #{{ index + 1 }}</strong>
              <span class="log-entry__name"> · {{ log.sample?.product_name || '未知产品' }}</span>
            </div>
            <el-tag size="small">{{ playbookLabelMap[log.sample?.playbook_type] || log.sample?.playbook_type }}</el-tag>
          </div>
          <div class="log-section">
            <div class="log-section__label">Question</div>
            <pre class="text-block">{{ log.sample?.question || '—' }}</pre>
          </div>
          <div class="log-section">
            <div class="log-section__label">Context</div>
            <pre class="text-block">{{ log.sample?.context || '—' }}</pre>
          </div>
          <div class="log-section">
            <div class="log-section__label">Ground Truth</div>
            <pre class="text-block">{{ log.sample?.ground_truth || '—' }}</pre>
          </div>
          <div class="log-section" v-if="log.result?.generation">
            <div class="log-section__label">ACE 输出</div>
            <el-tabs class="log-tabs" type="border-card">
              <el-tab-pane label="Final Answer">
                <pre class="text-block">{{ formatJsonLikeText(log.result?.generation?.final_answer) }}</pre>
              </el-tab-pane>
              <el-tab-pane label="Reasoning">
                <pre class="text-block">{{ log.result?.generation?.reasoning || '—' }}</pre>
              </el-tab-pane>
              <el-tab-pane label="Raw Generation">
                <pre class="text-block">{{ JSON.stringify(log.result?.generation || {}, null, 2) }}</pre>
              </el-tab-pane>
              <el-tab-pane label="Reflection" v-if="log.result?.reflection">
                <pre class="text-block">{{ JSON.stringify(log.result?.reflection || {}, null, 2) }}</pre>
              </el-tab-pane>
            </el-tabs>
          </div>
        </div>
      </el-scrollbar>
      <template #footer>
        <el-button @click="logsDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getProducts, getPromptPlaybooks, runPromptPlaybookAce, getPromptPlaybookDatasets, getPromptPlaybookRulesByType, deletePromptPlaybookDataset, deletePromptPlaybookRuleByType } from '@/services/api'

const formatJsonLikeText = (value) => {
  if (value === null || value === undefined) return '—'
  if (typeof value !== 'string') {
    try {
      return JSON.stringify(value, null, 2)
    } catch {
      return String(value)
    }
  }
  const text = value.trim()
  if (!text) return '—'
  try {
    const parsed = JSON.parse(text)
    return JSON.stringify(parsed, null, 2)
  } catch {
    return value
  }
}

const router = useRouter()
const productFilter = ref('')
const allProducts = ref([])
const selectedProducts = ref([])
const activePlaybookType = ref('spec')
const playbookItems = ref([])
const loadingPlaybooks = ref(false)
const playbookError = ref('')
const aceSubmitting = ref(false)
const expandedProduct = ref('')
const datasetName = ref('')
const datasetDescription = ref('')
const builderSamples = ref([])
const datasetHistory = ref([])
const globalRules = ref([])
const activeRulesSource = ref({ type: 'global', datasetId: null })
const selectedPoolKeys = ref([])
const customRuleText = ref('')
const deletingRuleId = ref('')
const aceRunLogs = ref([])
const logsDialogVisible = ref(false)

const playbookOptions = [
  { label: '规格页', value: 'spec' },
  { label: '说明书', value: 'manual' },
  { label: '海报', value: 'poster' }
]

const playbookLabelMap = {
  spec: '规格页',
  manual: '说明书',
  poster: '海报'
}

const activePlaybookLabel = computed(() => playbookLabelMap[activePlaybookType.value] || 'Playbook')

const filteredProducts = computed(() => {
  if (!productFilter.value.trim()) return allProducts.value
  const keyword = productFilter.value.trim().toLowerCase()
  return allProducts.value.filter((name) => name.toLowerCase().includes(keyword))
})

const displayPlaybooks = computed(() => {
  if (!playbookItems.value.length) return []
  const activeSet = new Set(selectedProducts.value.map((name) => name.toLowerCase()))
  if (!activeSet.size) return playbookItems.value
  return playbookItems.value.filter((item) => {
    const itemName = item.product_name?.toLowerCase() || ''
    return Array.from(activeSet).some((name) => itemName.includes(name))
  })
})

const availableDatasetRows = computed(() =>
  playbookItems.value
    .map((item) => buildSampleFromPlaybook(item))
    .filter(Boolean)
)

const canSubmitDataset = computed(() => builderSamples.value.length > 0 && !aceSubmitting.value)
const hasAceLogs = computed(() => aceRunLogs.value.length > 0)

const datasetIdentifier = (dataset) => dataset?.file_path || dataset?.local_id || dataset?.dataset_name

const getDatasetById = (identifier) =>
  datasetHistory.value.find((item) => datasetIdentifier(item) === identifier)

const mergeRuleSets = (globalSet, customSet, fallback = []) => {
  const normalized = []
  if (Array.isArray(globalSet)) {
    normalized.push(...globalSet)
  }
  if (Array.isArray(customSet)) {
    normalized.push(...customSet)
  }
  if (normalized.length) return normalized
  return Array.isArray(fallback) ? fallback : []
}

const datasetRulesSnapshot = (dataset) => {
  if (!dataset) return []
  return mergeRuleSets(dataset.global_rules, dataset.custom_rules, dataset.rules)
}

const displayedRules = computed(() => {
  if (activeRulesSource.value.type === 'dataset') {
    const dataset = getDatasetById(activeRulesSource.value.datasetId)
    return datasetRulesSnapshot(dataset)
  }
  return globalRules.value
})

const isGlobalRulesView = computed(() => activeRulesSource.value.type === 'global')

const fallbackSystemPrompt = (type, productName) => {
  const label = playbookLabelMap[type] || 'Playbook'
  return `你现在是一名${label}优化助手，请结合提供的上下文为${productName || '目标产品'}生成结构化内容。`
}

const buildSampleFromPlaybook = (item) => {
  if (!item) return null
  const pb = item.playbooks?.[activePlaybookType.value]
  if (!pb) return null
  const truthText = pb.ground_truth || extractPlaybookText(item, 'truth')
  if (!truthText) return null
  const contextText = pb.context || extractPlaybookText(item, 'generate')
  const key = getPlaybookKey(item)
  const question = pb.question || fallbackSystemPrompt(activePlaybookType.value, item.product_name)
  return {
    key,
    folder_name: item.folder_name,
    product_name: item.product_name,
    playbook_type: activePlaybookType.value,
    question,
    context: contextText,
    ground_truth: truthText,
    question_preview: question.slice(0, 80),
    context_preview: (contextText || '').slice(0, 80),
    ground_truth_preview: (truthText || '').slice(0, 80),
  }
}

const activeRulesLabel = computed(() => {
  if (activeRulesSource.value.type === 'dataset') {
    const dataset = getDatasetById(activeRulesSource.value.datasetId)
    if (!dataset) return '数据集快照'
    return `${dataset.dataset_name}（${playbookLabelMap[dataset.playbook_type] || dataset.playbook_type}）`
  }
  return '全局最新'
})

const rulesEmptyDescription = computed(() => {
  if (activeRulesSource.value.type === 'dataset') {
    return '该数据集未保存规则快照，点击“查看全局”以返回最新规则'
  }
  return '暂无规则'
})

const isDatasetSelected = (dataset) =>
  activeRulesSource.value.type === 'dataset' && datasetIdentifier(dataset) === activeRulesSource.value.datasetId

const ensureRulesSourceValidity = () => {
  if (activeRulesSource.value.type === 'dataset') {
    const exists = getDatasetById(activeRulesSource.value.datasetId)
    if (!exists) {
      activeRulesSource.value = { type: 'global', datasetId: null }
    }
  }
}

const selectDatasetRules = (dataset) => {
  if (!datasetRulesSnapshot(dataset).length) {
    ElMessage.info('该数据集未保存规则快照，已显示全局最新')
    activeRulesSource.value = { type: 'global', datasetId: null }
    return
  }
  activeRulesSource.value = { type: 'dataset', datasetId: datasetIdentifier(dataset) }
}

const showGlobalRules = () => {
  activeRulesSource.value = { type: 'global', datasetId: null }
}

const loadProducts = async () => {
  try {
    allProducts.value = await getProducts()
  } catch (error) {
    console.error('Failed to load products', error)
  }
}

const loadPlaybooks = async () => {
  loadingPlaybooks.value = true
  playbookError.value = ''
  try {
    playbookItems.value = await getPromptPlaybooks({
      playbookType: activePlaybookType.value
    })
  } catch (error) {
    playbookError.value = error?.message || '加载 Playbook 失败'
  } finally {
    loadingPlaybooks.value = false
  }
}

const storeAceRunLogs = (aceResults = [], submittedSamples = []) => {
  aceRunLogs.value = submittedSamples.map((sample, index) => ({
    sample,
    result: aceResults[index] || null,
  }))
  if (aceRunLogs.value.length) {
    logsDialogVisible.value = true
  }
}

const handleAceSubmit = async () => {
  if (!builderSamples.value.length) return
  const submittedSamples = builderSamples.value.map((row) => ({ ...row }))
  const customRules = customRuleText.value
    .split(/\n+/)
    .map((rule) => rule.trim())
    .filter(Boolean)
  aceSubmitting.value = true
  try {
    const response = await runPromptPlaybookAce({
      playbook_type: activePlaybookType.value,
      dataset_name: datasetName.value.trim() || undefined,
      description: datasetDescription.value.trim() || undefined,
      custom_rules: customRules,
      samples: submittedSamples.map((row) => ({
        folder_name: row.folder_name,
        product_name: row.product_name,
        playbook_type: row.playbook_type,
        question: row.question,
        context: row.context,
        ground_truth: row.ground_truth,
      }))
    })
    ElMessage.success('ACE 触发成功，Playbook 会在后台持续优化')
    recordAceRun(response, submittedSamples)
    storeAceRunLogs(response?.ace_results || [], submittedSamples)
    builderSamples.value = []
    datasetName.value = ''
    datasetDescription.value = ''
    customRuleText.value = ''
    await loadDatasets()
    await loadRules()
  } catch (error) {
    ElMessage.error(error?.message || '触发 ACE 失败')
  } finally {
    aceSubmitting.value = false
  }
}

const getPlaybookKey = (item) => item?.folder_name || item?.product_name

const extractPlaybookText = (item, variant) => {
  const pb = item?.playbooks?.[activePlaybookType.value]
  if (!pb) return ''
  const list = pb[variant] || []
  return list.map((entry) => entry.content).join('\n\n').trim()
}

const canSelectPlaybook = (item) => {
  const pb = item?.playbooks?.[activePlaybookType.value]
  const truthText = pb?.ground_truth || extractPlaybookText(item, 'truth')
  return Boolean(truthText)
}

const appendSample = (item) => {
  let record = null

  if (item?.playbooks) {
    if (!canSelectPlaybook(item)) return
    record = buildSampleFromPlaybook(item)
  } else if (item?.key) {
    record = item
  }

  if (!record) return
  if (builderSamples.value.some((sample) => sample.key === record.key)) return
  builderSamples.value = [...builderSamples.value, record]
}

const removeSample = (key) => {
  builderSamples.value = builderSamples.value.filter((sample) => sample.key !== key)
}

const clearDataset = () => {
  builderSamples.value = []
  datasetName.value = ''
  datasetDescription.value = ''
}

const handlePoolSelectionChange = (rows) => {
  selectedPoolKeys.value = rows.map((row) => row.key)
}

const addSelectedSamples = () => {
  const keySet = new Set(selectedPoolKeys.value)
  availableDatasetRows.value.forEach((row) => {
    if (keySet.has(row.key)) {
      appendSample(row)
    }
  })
}

const addAllSamples = () => {
  availableDatasetRows.value.forEach((row) => appendSample(row))
}

const clearSelectedSamples = () => {
  selectedPoolKeys.value = []
}

const recordAceRun = (response, submittedSamples) => {
  const timestamp = new Date()
  const globalSnapshot = response?.global_rules || response?.rules || []
  const customSnapshot = response?.custom_rules || []
  const combinedRules = mergeRuleSets(globalSnapshot, customSnapshot)
  const entry = {
    dataset_name: datasetName.value || `dataset_${activePlaybookType.value}`,
    playbook_type: activePlaybookType.value,
    submitted_at: timestamp.toISOString(),
    file_path: response?.named_dataset || null,
    local_id: `local-${timestamp.getTime()}`,
    sample_count: submittedSamples.length,
    description: datasetDescription.value,
    samples: submittedSamples.map((row) => ({
      product_name: row.product_name,
      question_preview: row.question_preview,
      context_preview: row.context_preview,
      ground_truth_preview: row.ground_truth_preview,
    })),
    global_rules: globalSnapshot,
    custom_rules: customSnapshot,
    rules: combinedRules,
  }
  datasetHistory.value.unshift(entry)
  selectDatasetRules(entry)
}

const loadDatasets = async () => {
  const datasets = await getPromptPlaybookDatasets(20)
  datasetHistory.value = datasets.map((item) => ({
    ...item,
    rules: mergeRuleSets(item.global_rules, item.custom_rules, item.rules)
  }))
  ensureRulesSourceValidity()
}

const loadRules = async () => {
  globalRules.value = await getPromptPlaybookRulesByType(activePlaybookType.value, 200)
}

const handleDeleteGlobalRule = async (rule) => {
  if (!rule?.id) {
    ElMessage.warning('该规则缺少 ID，无法删除')
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除规则 ${rule.id} 吗？删除后不可恢复。`, '删除规则', {
      type: 'warning'
    })
  } catch {
    return
  }

  deletingRuleId.value = rule.id
  try {
    await deletePromptPlaybookRuleByType(rule.id, activePlaybookType.value)
    ElMessage.success('规则已删除')
    await loadRules()
  } catch (error) {
    ElMessage.error(error?.message || '删除规则失败')
  } finally {
    deletingRuleId.value = ''
  }
}

const confirmDeleteDataset = async (dataset) => {
  if (!dataset?.file_path) {
    ElMessage.warning('该数据集尚未持久化，无法删除')
    return
  }
  try {
    await ElMessageBox.confirm(`确认删除数据集 ${dataset.dataset_name} 吗？该操作不可恢复。`, '删除确认', {
      type: 'warning'
    })
  } catch {
    return
  }

  try {
    await deletePromptPlaybookDataset(dataset.file_path)
    ElMessage.success('删除成功')
    datasetHistory.value = datasetHistory.value.filter((item) => datasetIdentifier(item) !== datasetIdentifier(dataset))
    ensureRulesSourceValidity()
  } catch (error) {
    ElMessage.error(error?.message || '删除数据集失败')
  }
}

const formatTimestamp = (value) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

const playbookColor = (type) => {
  switch (type) {
    case 'spec':
      return '#3b82f6'
    case 'manual':
      return '#06b6d4'
    case 'poster':
      return '#f97316'
    default:
      return '#94a3b8'
  }
}

const goBack = () => {
  router.push({ name: 'Home', query: { tab: 'kbSearch' } })
}

onMounted(async () => {
  await loadProducts()
  await loadPlaybooks()
  await loadDatasets()
  await loadRules()
})

watch(activePlaybookType, () => {
  loadPlaybooks()
})
</script>

<style scoped>
.playbook-page {
  padding: 24px;
  width: 100%;
  max-width: 100vw;
  box-sizing: border-box;
  overflow-x: hidden;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 24px;
  margin-bottom: 20px;
}

.breadcrumb {
  color: #3b82f6;
  margin-bottom: 8px;
  cursor: pointer;
}

.title {
  font-size: 28px;
  margin: 0;
}

.subtitle {
  margin-top: 6px;
  color: #64748b;
}

.workspace-grid {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 20px;
  align-items: start;
}

.sidebar {
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 16px;
  background: #fff;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sidebar-head .sidebar-title {
  font-weight: 600;
}

.sidebar-sub {
  font-size: 13px;
  color: #94a3b8;
}

.sidebar-search :deep(.el-input__wrapper) {
  border-radius: 999px;
}

.product-scroll {
  max-height: 520px;
}

.main-panel {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.insight-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 20px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
}

.panel-title {
  font-size: 18px;
  font-weight: 600;
}

.panel-sub {
  color: #94a3b8;
  font-size: 13px;
}

.playbook-content {
  margin-top: 16px;
}

.playbook-split {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
  margin-top: 12px;
}

.playbook-block {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  background: #f9fafb;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.block-head {
  font-weight: 600;
  font-size: 14px;
}

.text-area {
  max-height: 320px;
  background: #fff;
  border-radius: 10px;
  padding: 10px;
  border: 1px dashed #cbd5f5;
}

.text-area pre {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.5;
  font-size: 13px;
}

.dataset-card {
  min-height: 260px;
}

.pool-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  align-items: center;
}

.clip-cell .cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dataset-card :deep(.el-table) {
  table-layout: fixed;
}

.history-card {
  min-height: 320px;
}

.history-scroll {
  max-height: 380px;
}

.rules-card {
  min-height: 320px;
}

.rules-body {
  max-height: 360px;
}

.rules-scroll {
  max-height: 360px;
}

.rule-item {
  padding: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.rule-text {
  display: flex;
  gap: 8px;
  font-size: 13px;
  color: #1f2937;
  line-height: 1.4;
}

.rule-snippet {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  line-clamp: 3;
  overflow: hidden;
  text-overflow: ellipsis;
}

.rule-index {
  font-weight: 600;
  color: #6366f1;
}

.playbook-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.meta-spacer {
  flex: 1;
}

.meta-hint {
  font-size: 12px;
  color: #f97316;
}

.history-entry {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.entry-header {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.entry-products {
  font-size: 13px;
  color: #4b5563;
}

.entry-preview {
  display: grid;
  gap: 4px;
  font-size: 12px;
  color: #475569;
}

.error-state {
  color: #f56c6c;
  padding: 40px;
  text-align: center;
}

.empty-state {
  padding: 40px 0;
}

.product-title {
  font-weight: 600;
}
</style>
