<template>
  <div class="page">
    <div class="topbar">
      <el-button class="back-btn" link @click="goBack">← 返回</el-button>
      <div class="title">选择 BOM</div>
    </div>

    <div class="content">
      <div class="product-header">
        <img class="thumb" :src="imgUrl" :alt="name" @error="onImgError" />
        <div class="meta">
          <div class="name">{{ name }}</div>
          <div class="sub">ID：{{ id }}</div>
        </div>
      </div>

      <div class="panel">
        <div class="panel-title">请选择该产品的 BOM 号</div>
        <div class="filter-row" v-if="segmentList.length">
          <div class="filter-grid">
            <el-select
              v-for="segment in segmentList"
              :key="segment.key"
              v-model="filters[segment.key]"
              :placeholder="segment.label"
              clearable
              class="filter-select"
            >
              <el-option
                v-for="opt in segment.options"
                :key="`${segment.key}-${opt.code}`"
                :label="opt.label"
                :value="opt.code"
              />
            </el-select>
          </div>
          <div class="filter-controls">
            <el-button class="filter-reset" link :disabled="!hasActiveFilter" @click="resetFilters">
              重置筛选
            </el-button>
            <el-button class="filter-advanced" text @click="toggleAdvancedFilters">
              {{ showAdvancedFilters ? '收起高级筛选' : '展开高级筛选' }}
            </el-button>
          </div>
        </div>
        <div v-if="activeFilters.length" class="active-filter-tags">
          <div class="tags-label">当前筛选：</div>
          <el-tag
            v-for="tag in activeFilters"
            :key="tag.key"
            closable
            @close="clearFilter(tag.key)"
          >
            {{ tag.label }}：{{ tag.value }}
          </el-tag>
        </div>
        <div class="search-row bom-search">
          <el-input
            v-model="bomKeyword"
            placeholder="输入 BOM 编号进行查询..."
            clearable
          >
            <template #prefix>
              <el-icon class="bom-search-icon">
                <Search />
              </el-icon>
            </template>
          </el-input>
        </div>
        <div v-if="loadingBoms" class="loading">加载中...</div>
        <div v-else-if="bomsError" class="error">{{ bomsError }}</div>
        <div v-else-if="filteredBoms.length" class="bom-list">
          <el-card
            v-for="bom in filteredBoms"
            :key="bom"
            class="bom-item"
            shadow="hover"
            @click="goProductDetail(bom)"
          >
            <div class="bom-row">
              <div class="bom-code">{{ bom }}</div>
              <div class="arrow">›</div>
            </div>
          </el-card>
        </div>
        <div v-else class="loading">未找到匹配的 BOM</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import { BOM_CONFIG, createDefaultBomSelections } from '@/constants/bomOptions'

const route = useRoute()
const router = useRouter()

const id = computed(() => route.params.id)
const productId = computed(() => route.query.productId || '')
const materialCode = computed(() => route.query.materialCode || '')
const name = computed(() => route.query.label || productId.value || `产品${id.value}`)
const image = computed(() => route.query.image || 'Alta.png')
const imgUrl = computed(() => `/product/${image.value}`)

const onImgError = (e) => { e.target.src = '/favicon.ico' }

const bomList = ref([])
const loadingBoms = ref(false)
const bomsError = ref('')

const BOM_TYPE = 'outdoor'
const rawSegments = computed(() => BOM_CONFIG[BOM_TYPE] || [])

const segmentConfigs = computed(() =>
  rawSegments.value.map((seg) => {
    const entries = Object.entries(seg.options || {})
    return {
      key: seg.key,
      label: seg.label,
      length: seg.digits,
      options: entries.map(([code, meaning]) => ({
        code,
        label: `${code} · ${meaning}`,
      })),
      optionMap: seg.options || {},
    }
  })
)

const filters = reactive(createDefaultBomSelections(BOM_TYPE))
const showAdvancedFilters = ref(false)
const primarySegmentKeys = [
  'colorHole',
  'nozzle',
  'powerStandard',
  'controlSystem',
  'waterPump',
  'airPump',
  'sanitation',
  'multimedia',
  'lighting',
]

const segmentList = computed(() =>
  segmentConfigs.value.filter(
    (segment) => showAdvancedFilters.value || primarySegmentKeys.includes(segment.key)
  )
)

const hasActiveFilter = computed(() => segmentConfigs.value.some(({ key }) => filters[key]))

const findSegment = (key) => segmentConfigs.value.find((segment) => segment.key === key)

const getOptionLabel = (key, code) => {
  const segment = findSegment(key)
  if (!segment) return code
  const found = segment.options?.find((opt) => opt.code === code)
  if (found) return found.label
  const fallbackMeaning = segment.optionMap?.[code]
  return fallbackMeaning ? `${code} · ${fallbackMeaning}` : code
}

const activeFilters = computed(() =>
  segmentConfigs.value
    .filter(({ key }) => Boolean(filters[key]))
    .map(({ key, label }) => ({
      key,
      label,
      value: getOptionLabel(key, filters[key])
    }))
)

const resetFilters = () => {
  segmentConfigs.value.forEach(({ key }) => {
    filters[key] = ''
  })
}

const clearFilter = (key) => {
  if (filters[key] !== undefined) {
    filters[key] = ''
  }
}

const toggleAdvancedFilters = () => {
  showAdvancedFilters.value = !showAdvancedFilters.value
}

const decodeBom = (code = '') => {
  const normalized = String(code || '').trim().toUpperCase()
  let cursor = 0
  return Object.fromEntries(
    segmentConfigs.value.map(({ key, length }) => {
      const value = normalized.slice(cursor, cursor + length)
      cursor += length
      return [key, value]
    })
  )
}

const filterByRules = (code) => {
  const decoded = decodeBom(code)
  return segmentConfigs.value.every(({ key }) => {
    const filterVal = filters[key]
    if (!filterVal) return true
    return decoded[key] === filterVal
  })
}

// BOM 本地搜索关键字与过滤结果
const bomKeyword = ref('')
const filteredBoms = computed(() => {
  const kw = bomKeyword.value.trim().toLowerCase()
  return bomList.value.filter((code) => {
    if (!filterByRules(code)) return false
    if (!kw) return true
    return String(code).toLowerCase().includes(kw)
  })
})

// Load BOMs from API
const loadBoms = async () => {
  if (!productId.value && !materialCode.value) {
    bomsError.value = '缺少产品标识'
    return
  }

  loadingBoms.value = true
  bomsError.value = ''
  try {
    if (materialCode.value) {
      const { getBomsByMaterial } = await import('@/services/api')
      bomList.value = await getBomsByMaterial(materialCode.value)
    } else {
      const { getBomsByProduct } = await import('@/services/api')
      bomList.value = await getBomsByProduct(productId.value)
    }
    if (bomList.value.length === 0) {
      bomsError.value = '该产品暂无 BOM 信息'
    }
  } catch (error) {
    bomsError.value = '加载 BOM 列表失败，请稍后重试'
    console.error('Failed to load BOMs:', error)
  } finally {
    loadingBoms.value = false
  }
}

onMounted(() => {
  if (productId.value || materialCode.value) {
    loadBoms()
  }
})

const goBack = () => router.back()

const goProductDetail = async (bom) => {
  const bomCode = String(bom || '').trim().toUpperCase()
  if (!bomCode) return

  const initProductName = materialCode.value || productId.value || name.value
  try {
    const { initManualSession } = await import('@/services/api')
    const session = await initManualSession({
      productName: initProductName,
      bomCode,
      materialCode: materialCode.value || '',
      bomId: String(bom || '').trim(),
    })
    const sessionId = session?.session_id || session?.id
    if (!sessionId) {
      throw new Error('创建 OCR 会话失败，请稍后重试')
    }

    router.push({
      name: 'ManualReview',
      query: {
        sessionId,
      },
    })
  } catch (error) {
    console.error('Failed to init manual session:', error)
  }
}
</script>

<style scoped>
.page { width: 100%; padding: 24px; }
.topbar { display: flex; align-items: center; gap: 12px; margin-bottom: 16px; }
.title { font-weight: 700; font-size: 20px; }
.content { display: grid; gap: 16px; }
.product-header { display: flex; align-items: center; gap: 12px; }
.thumb { width: 88px; height: 88px; object-fit: contain; background: #fafafa; border-radius: 8px; }
.meta .name { font-weight: 700; }
.panel { background: #fff; padding: 16px; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.06); }
.panel-title { font-weight: 600; margin-bottom: 12px; }
.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}

.filter-select {
  min-width: 220px;
}

.filter-reset {
  align-self: center;
  color: #409eff;
}
.bom-list { display: grid; grid-template-columns: 1fr; gap: 12px; }
.bom-item { cursor: pointer; }
.bom-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 14px 8px; }
.bom-code { font-weight: 700; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace; word-break: break-all; }
.arrow { color: #999; font-size: 20px; line-height: 1; }
.bom-item:hover .arrow { color: #333; }

.loading, .error {
  text-align: center;
  padding: 40px;
  color: #666;
}

.error {
  color: #f56c6c;
}

/* BOM 搜索条样式 */
.bom-search {
  max-width: 520px;
  margin: 4px auto 16px;
}

.bom-search :deep(.el-input__wrapper) {
  border-radius: 999px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  padding-left: 10px;
}

.bom-search-icon {
  color: #c0c4cc;
}
</style>
