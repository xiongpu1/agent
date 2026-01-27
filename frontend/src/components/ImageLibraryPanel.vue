<template>
  <div class="imgpanel">
    <div class="imgpanel__top">
      <el-input
        v-model="keyword"
        placeholder="搜索名称 / 标签 / 备注 / 关联产品"
        clearable
        class="imgpanel__search"
        :disabled="!isUsable"
        @keyup.enter="onSearch"
      />
      <el-button
        class="imgpanel__searchBtn"
        :loading="loading"
        :disabled="!isUsable"
        @click="onSearch"
      >
        <el-icon><Search /></el-icon>
      </el-button>
    </div>

    <div v-if="!isUsable" class="imgpanel__empty">
      <el-empty :description="emptyDescription">
        <div class="imgpanel__emptyActions">
          <el-button type="primary" @click="retryLogin">重新登录</el-button>
        </div>
      </el-empty>
    </div>

    <template v-else>
      <div class="imgpanel__upload">
        <input
          ref="fileInput"
          class="imgpanel__fileInput"
          type="file"
          accept=".jpg,.jpeg,.png"
          multiple
          @change="onFilePicked"
        />
        <el-button class="imgpanel__uploadBtn" :loading="uploading" :disabled="!isUsable" @click="openFilePicker">
          上传文件
        </el-button>
      </div>

      <div v-if="selectedIds.size" class="imgpanel__bulkbar">
        <div class="imgpanel__bulkLeft">已选 {{ selectedIds.size }} 张</div>
        <div class="imgpanel__bulkRight">
          <el-button @click="clearSelection">取消</el-button>
          <el-button type="danger" :loading="bulkDeleting" @click="bulkDelete">删除</el-button>
        </div>
      </div>

      <div class="imgpanel__content">
        <div v-if="loading" class="imgpanel__loading">加载中…</div>
        <div v-else-if="error" class="imgpanel__error">{{ error }}</div>
        <el-empty v-else-if="!items.length" description="暂无图片" />

        <div v-else class="imgpanel__grid">
          <div v-for="it in items" :key="it.id" class="imgpanel__item" :class="{ selected: selectedIds.has(it.id) }">
            <button class="imgpanel__select" type="button" @click="toggleSelected(it.id)">
              <el-icon v-if="selectedIds.has(it.id)" class="imgpanel__check"><Check /></el-icon>
            </button>

            <el-image
              class="imgpanel__thumb"
              :src="resolveFileUrl(it.file_url)"
              fit="cover"
              :preview-src-list="[resolveFileUrl(it.file_url)]"
              preview-teleported
              @load="(e) => onThumbLoad(it.id, e)"
            />

            <div class="imgpanel__meta">
              <div class="imgpanel__metaTop">
                <div class="imgpanel__name" :title="it.original_filename">
                  {{ it.original_filename || '未命名图片' }}
                </div>
                <el-dropdown trigger="click" @command="(cmd) => onItemCommand(cmd, it)">
                  <button class="imgpanel__menu" type="button">⋯</button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">编辑信息</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>

              <div class="imgpanel__row" :title="formatMetaLine(it)">{{ formatMetaLine(it) }}</div>

              <div v-if="it.product_name" class="imgpanel__row" :title="it.product_name">关联：{{ it.product_name }}</div>
              <div v-if="it.remark" class="imgpanel__row" :title="it.remark">备注：{{ it.remark }}</div>
              <div v-if="Array.isArray(it.tags) && it.tags.length" class="imgpanel__tags">
                <el-tag v-for="t in it.tags" :key="t" size="small" effect="plain">{{ t }}</el-tag>
              </div>
            </div>
          </div>
        </div>
      </div>

      <el-dialog v-model="editVisible" title="编辑图片信息" width="520px" append-to-body>
        <el-form v-if="editItem" label-width="92px">
          <el-form-item label="名称">
            <el-input v-model="editForm.original_filename" placeholder="必填" />
          </el-form-item>
          <el-form-item label="尺寸/大小">
            <el-input :model-value="formatMetaLine(editItem)" disabled />
          </el-form-item>
          <el-form-item label="标签">
            <el-select
              v-model="editForm.tags"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="输入后回车"
              style="width: 100%"
            >
              <el-option v-for="t in editForm.tags" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="备注">
            <el-input v-model="editForm.remark" type="textarea" :rows="3" placeholder="可选" />
          </el-form-item>
          <el-form-item label="关联产品">
            <el-input v-model="editForm.product_name" placeholder="可选" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="editVisible = false">取消</el-button>
          <el-button type="primary" :loading="saving" @click="saveEdit">保存</el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, Search } from '@element-plus/icons-vue'
import { deleteImageAsset, listImageAssets, updateImageAsset, uploadImageAssets } from '@/services/api'

const props = defineProps({
  loggedIn: { type: Boolean, default: false },
  pinned: { type: Boolean, default: false },
  opened: { type: Boolean, default: false }
})

const emit = defineEmits(['retry-login', 'interact'])

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')

const resolveFileUrl = (path) => {
  const p = String(path || '')
  if (!p) return ''
  if (p.startsWith('http://') || p.startsWith('https://')) return p
  if (p.startsWith('/') && API_BASE_URL) return `${API_BASE_URL}${p}`
  return p
}

const items = ref([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')

const uploading = ref(false)
const fileInput = ref(null)

const selectedIds = ref(new Set())
const bulkDeleting = ref(false)

const editVisible = ref(false)
const editItem = ref(null)
const editForm = reactive({
  original_filename: '',
  tags: [],
  remark: '',
  product_name: ''
})
const saving = ref(false)

const imageDims = ref({})

const sessionExpired = ref(false)

const isUsable = computed(() => props.loggedIn && !sessionExpired.value)

const emptyDescription = computed(() => {
  if (props.loggedIn && sessionExpired.value) return '登录已失效，请重新登录'
  return '未登录，暂时无法使用图片库'
})

const isAuthError = (msg) => {
  const m = String(msg || '')
  if (!m) return false
  if (/not\s+logged\s+in/i.test(m)) return true
  if (/\b401\b/.test(m)) return true
  return false
}

const retryLogin = () => {
  sessionExpired.value = false
  emit('retry-login')
}

const markInteracted = () => {
  emit('interact')
}

const refresh = async () => {
  if (!isUsable.value) return
  loading.value = true
  error.value = ''
  try {
    const data = await listImageAssets({ keyword: keyword.value })
    items.value = Array.isArray(data?.items) ? data.items : []
    // Reset dims cache; it will be filled when thumbnails load.
    imageDims.value = {}
  } catch (e) {
    const msg = e?.message || String(e)
    if (isAuthError(msg)) {
      sessionExpired.value = true
      items.value = []
      return
    }
    error.value = msg
  } finally {
    loading.value = false
  }
}

const formatBytes = (bytes) => {
  const b = Number(bytes || 0)
  if (!Number.isFinite(b) || b <= 0) return ''
  if (b < 1024) return `${Math.round(b)}B`
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)}KB`
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1)}MB`
  return `${(b / (1024 * 1024 * 1024)).toFixed(1)}GB`
}

const onThumbLoad = (id, evt) => {
  try {
    const sid = String(id || '')
    if (!sid) return
    const img = evt?.target
    const w = Number(img?.naturalWidth || 0)
    const h = Number(img?.naturalHeight || 0)
    if (!w || !h) return
    imageDims.value = { ...imageDims.value, [sid]: { w, h } }
  } catch {
    // ignore
  }
}

const formatMetaLine = (it) => {
  const id = String(it?.id || '')
  const dims = id ? imageDims.value?.[id] : null
  const wh = dims?.w && dims?.h ? `${dims.w}×${dims.h}` : ''
  const size = formatBytes(it?.size_bytes)
  if (wh && size) return `${wh} · ${size}`
  return wh || size || ''
}

const onSearch = async () => {
  if (!isUsable.value) return
  markInteracted()
  await refresh()
}

const openFilePicker = () => {
  if (!isUsable.value) return
  markInteracted()
  fileInput.value?.click?.()
}

const onFilePicked = async (e) => {
  if (!isUsable.value) return
  const files = Array.from(e?.target?.files || []).filter(Boolean)
  if (!files.length) return

  markInteracted()
  uploading.value = true
  try {
    await uploadImageAssets(files)
    ElMessage.success('上传成功')
    await refresh()
  } catch (err) {
    const msg = err?.message || String(err)
    if (isAuthError(msg)) {
      sessionExpired.value = true
      return
    }
    ElMessage.error(msg)
  } finally {
    uploading.value = false
    try {
      if (fileInput.value) fileInput.value.value = ''
    } catch {
      // ignore
    }
  }
}

const toggleSelected = (id) => {
  const sid = String(id || '')
  if (!sid) return
  markInteracted()
  const next = new Set(selectedIds.value)
  if (next.has(sid)) next.delete(sid)
  else next.add(sid)
  selectedIds.value = next
}

const clearSelection = () => {
  selectedIds.value = new Set()
}

const bulkDelete = async () => {
  const ids = Array.from(selectedIds.value)
  if (!ids.length) return
  markInteracted()
  try {
    await ElMessageBox.confirm(`确定删除已选 ${ids.length} 张图片吗？`, '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  bulkDeleting.value = true
  try {
    for (const id of ids) {
      await deleteImageAsset(id)
    }
    ElMessage.success('删除成功')
    clearSelection()
    await refresh()
  } catch (e) {
    const msg = e?.message || String(e)
    if (isAuthError(msg)) {
      sessionExpired.value = true
      return
    }
    ElMessage.error(msg)
  } finally {
    bulkDeleting.value = false
  }
}

const openEdit = (it) => {
  markInteracted()
  editItem.value = it
  editForm.original_filename = String(it?.original_filename || '')
  editForm.tags = Array.isArray(it?.tags) ? [...it.tags] : []
  editForm.remark = String(it?.remark || '')
  editForm.product_name = String(it?.product_name || '')
  editVisible.value = true
}

const saveEdit = async () => {
  if (!editItem.value?.id) return
  markInteracted()
  saving.value = true
  try {
    const name = String(editForm.original_filename || '').trim()
    if (!name) throw new Error('名称不能为空')

    const payload = {
      original_filename: name,
      tags: editForm.tags,
      remark: editForm.remark,
      product_name: editForm.product_name
    }
    const res = await updateImageAsset(editItem.value.id, payload)
    const updated = res?.item
    items.value = items.value.map((x) => (x.id === updated?.id ? updated : x))
    ElMessage.success('已保存')
    editVisible.value = false
  } catch (e) {
    const msg = e?.message || String(e)
    if (isAuthError(msg)) {
      sessionExpired.value = true
      return
    }
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

const deleteOne = async (it) => {
  const id = String(it?.id || '')
  if (!id) return
  markInteracted()
  try {
    await ElMessageBox.confirm('确定删除该图片吗？', '删除确认', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }

  try {
    await deleteImageAsset(id)
    items.value = items.value.filter((x) => x.id !== id)
    const next = new Set(selectedIds.value)
    next.delete(id)
    selectedIds.value = next
    ElMessage.success('删除成功')
  } catch (e) {
    const msg = e?.message || String(e)
    if (isAuthError(msg)) {
      sessionExpired.value = true
      return
    }
    ElMessage.error(msg)
  }
}

const onItemCommand = (cmd, it) => {
  if (cmd === 'edit') openEdit(it)
  else if (cmd === 'delete') deleteOne(it)
}

watch(
  () => props.loggedIn,
  (v) => {
    if (v) sessionExpired.value = false
  }
)

watch(
  () => [props.opened, isUsable.value],
  ([opened, usable]) => {
    if (opened && usable) refresh()
  },
  { immediate: true }
)

onMounted(() => {
  if (props.opened && isUsable.value) refresh()
})
</script>

<style scoped>
.imgpanel {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 10px;
  gap: 12px;
}

.imgpanel__search {
  flex: 1 1 auto;
}

.imgpanel__top {
  display: flex;
  gap: 8px;
  align-items: center;
}

.imgpanel__searchBtn {
  width: 44px;
  height: 40px;
  padding: 0;
  border-radius: 12px;
}

.imgpanel__empty {
  flex: 1 1 auto;
  display: flex;
  align-items: center;
  justify-content: center;
}

.imgpanel__emptyActions {
  display: flex;
  justify-content: center;
  margin-top: 8px;
}

.imgpanel__upload {
  display: grid;
  gap: 8px;
}

.imgpanel__fileInput {
  display: none;
}

.imgpanel__uploadBtn {
  width: 100%;
  height: 44px;
  border-radius: 12px;
  font-weight: 800;
  background: #7c3aed;
  border-color: #7c3aed;
  color: #ffffff;
}

.imgpanel__uploadBtn:hover {
  background: #6d28d9;
  border-color: #6d28d9;
  color: #ffffff;
}

.imgpanel__uploadBtn:disabled {
  color: #ffffff;
}

.imgpanel__bulkbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  padding: 10px 12px;
}

.imgpanel__bulkLeft {
  font-size: 12px;
  font-weight: 700;
  color: #111827;
}

.imgpanel__content {
  flex: 1 1 auto;
  min-height: 0;
  overflow: auto;
  padding-right: 2px;
}

.imgpanel__loading,
.imgpanel__error {
  text-align: center;
  padding: 28px 12px;
  color: #6b7280;
}

.imgpanel__error {
  color: #ef4444;
}

.imgpanel__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.imgpanel__item {
  position: relative;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
}

.imgpanel__item.selected {
  border-color: rgba(37, 99, 235, 0.7);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.imgpanel__select {
  position: absolute;
  left: 10px;
  top: 10px;
  width: 22px;
  height: 22px;
  border-radius: 999px;
  border: 1px solid rgba(17, 24, 39, 0.25);
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 2;
}

.imgpanel__check {
  color: #2563eb;
}

.imgpanel__thumb {
  width: 100%;
  height: 96px;
  display: block;
}

.imgpanel__meta {
  padding: 10px 10px 12px;
  display: grid;
  gap: 6px;
}

.imgpanel__metaTop {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.imgpanel__name {
  font-size: 12px;
  font-weight: 800;
  color: #111827;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.imgpanel__menu {
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 0 2px;
  color: #6b7280;
}

.imgpanel__row {
  font-size: 12px;
  color: #6b7280;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.imgpanel__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>
