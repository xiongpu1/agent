<template>
  <div class="imglib">
    <div class="imglib__header">
      <div>
        <div class="imglib__title">上传图片</div>
        <div class="imglib__subtitle">你的图片素材库（按钉钉账号隔离存储）</div>
      </div>

      <div class="imglib__headerRight">
        <el-input
          v-model="keyword"
          placeholder="搜索标题 / 标签 / 备注 / 关联产品名称"
          clearable
          class="imglib__search"
          @keyup.enter="refresh()"
        />
        <el-button :loading="loading" @click="refresh()">刷新</el-button>
      </div>
    </div>

    <div v-if="selectedIds.size" class="imglib__bulkbar">
      <div class="imglib__bulkbarLeft">已选 {{ selectedIds.size }} 张</div>
      <div class="imglib__bulkbarRight">
        <el-button @click="clearSelection">取消选择</el-button>
        <el-button type="danger" :loading="bulkDeleting" @click="bulkDelete">删除</el-button>
      </div>
    </div>

    <div class="imglib__layout">
      <div class="imglib__left">
        <div class="imglib__card">
          <div class="imglib__cardTitle">上传图片</div>
          <div class="imglib__cardDesc">支持 jpg / png，单张最大 10MB。</div>

          <el-upload
            class="imglib__uploader"
            drag
            action="#"
            :auto-upload="false"
            multiple
            :file-list="uploadFiles"
            :on-change="onUploadChange"
            :on-remove="onUploadRemove"
            accept=".jpg,.jpeg,.png"
          >
            <div class="el-upload__text">将文件拖到此处，或<em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">上传后会进入右侧图片库。</div>
            </template>
          </el-upload>

          <div class="imglib__uploadActions">
            <el-button type="primary" :disabled="!uploadFiles.length" :loading="uploading" @click="doUpload">
              上传
            </el-button>
            <el-button :disabled="!uploadFiles.length || uploading" @click="clearUpload">清空</el-button>
          </div>
        </div>
      </div>

      <div class="imglib__right">
        <div v-if="loading" class="imglib__loading">加载中…</div>
        <div v-else-if="error" class="imglib__error">{{ error }}</div>
        <el-empty v-else-if="!items.length" description="暂无图片，先上传一张吧" />

        <div v-else class="imglib__grid">
          <div v-for="it in items" :key="it.id" class="imglib__item" :class="{ selected: selectedIds.has(it.id) }">
            <button class="imglib__select" type="button" @click="toggleSelected(it.id)">
              <el-icon v-if="selectedIds.has(it.id)" class="imglib__check"><Check /></el-icon>
            </button>

            <el-image
              class="imglib__thumb"
              :src="resolveFileUrl(it.file_url)"
              fit="cover"
              :preview-src-list="[resolveFileUrl(it.file_url)]"
              preview-teleported
            />

            <div class="imglib__meta">
              <div class="imglib__metaTop">
                <div class="imglib__name" :title="it.title || it.original_filename">
                  {{ it.title || it.original_filename || '未命名图片' }}
                </div>
                <el-dropdown trigger="click" @command="(cmd) => onItemCommand(cmd, it)">
                  <button class="imglib__menu" type="button">⋯</button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">编辑信息</el-dropdown-item>
                      <el-dropdown-item command="delete" divided>删除</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>

              <div v-if="it.product_name" class="imglib__row" :title="it.product_name">关联：{{ it.product_name }}</div>
              <div v-if="it.remark" class="imglib__row" :title="it.remark">备注：{{ it.remark }}</div>
              <div v-if="Array.isArray(it.tags) && it.tags.length" class="imglib__tags">
                <el-tag v-for="t in it.tags" :key="t" size="small" effect="plain">{{ t }}</el-tag>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="editVisible" title="编辑图片信息" width="520px" append-to-body>
      <el-form v-if="editItem" label-width="92px">
        <el-form-item label="标题">
          <el-input v-model="editForm.title" placeholder="可选" />
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="editForm.tags" multiple filterable allow-create default-first-option placeholder="输入后回车" style="width: 100%">
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
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check } from '@element-plus/icons-vue'
import { deleteImageAsset, listImageAssets, updateImageAsset, uploadImageAssets } from '@/services/api'

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

const uploadFiles = ref([])
const uploading = ref(false)

const selectedIds = ref(new Set())
const bulkDeleting = ref(false)

const editVisible = ref(false)
const editItem = ref(null)
const editForm = reactive({
  title: '',
  tags: [],
  remark: '',
  product_name: ''
})
const saving = ref(false)

const refresh = async () => {
  loading.value = true
  error.value = ''
  try {
    const data = await listImageAssets({ keyword: keyword.value })
    items.value = Array.isArray(data?.items) ? data.items : []
  } catch (e) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

const clearUpload = () => {
  uploadFiles.value = []
}

const onUploadChange = (_file, fileList) => {
  uploadFiles.value = Array.isArray(fileList) ? fileList : []
}

const onUploadRemove = (_file, fileList) => {
  uploadFiles.value = Array.isArray(fileList) ? fileList : []
}

const doUpload = async () => {
  if (!uploadFiles.value.length) return
  uploading.value = true
  try {
    const rawFiles = uploadFiles.value
      .map((f) => f?.raw)
      .filter(Boolean)

    if (!rawFiles.length) {
      throw new Error('未选择文件')
    }

    await uploadImageAssets(rawFiles)
    ElMessage.success('上传成功')
    clearUpload()
    await refresh()
  } catch (e) {
    ElMessage.error(e?.message || String(e))
  } finally {
    uploading.value = false
  }
}

const toggleSelected = (id) => {
  const sid = String(id || '')
  if (!sid) return
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
    ElMessage.error(e?.message || String(e))
  } finally {
    bulkDeleting.value = false
  }
}

const openEdit = (it) => {
  editItem.value = it
  editForm.title = String(it?.title || '')
  editForm.tags = Array.isArray(it?.tags) ? [...it.tags] : []
  editForm.remark = String(it?.remark || '')
  editForm.product_name = String(it?.product_name || '')
  editVisible.value = true
}

const saveEdit = async () => {
  if (!editItem.value?.id) return
  saving.value = true
  try {
    const payload = {
      title: editForm.title,
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
    ElMessage.error(e?.message || String(e))
  } finally {
    saving.value = false
  }
}

const deleteOne = async (it) => {
  const id = String(it?.id || '')
  if (!id) return
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
    ElMessage.error(e?.message || String(e))
  }
}

const onItemCommand = (cmd, it) => {
  if (cmd === 'edit') {
    openEdit(it)
  } else if (cmd === 'delete') {
    deleteOne(it)
  }
}

onMounted(() => {
  refresh()
})
</script>

<style scoped>
.imglib {
  padding: 18px;
}

.imglib__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.imglib__title {
  font-size: 18px;
  font-weight: 800;
  color: #111827;
}

.imglib__subtitle {
  margin-top: 4px;
  font-size: 13px;
  color: #6b7280;
}

.imglib__headerRight {
  display: flex;
  gap: 10px;
  align-items: center;
}

.imglib__search {
  width: 360px;
}

.imglib__bulkbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #ffffff;
  margin-bottom: 12px;
}

.imglib__bulkbarLeft {
  font-size: 13px;
  font-weight: 600;
  color: #111827;
}

.imglib__layout {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 14px;
  align-items: start;
}

.imglib__card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 14px;
  display: grid;
  gap: 10px;
}

.imglib__cardTitle {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.imglib__cardDesc {
  font-size: 12px;
  color: #6b7280;
}

.imglib__uploader {
  width: 100%;
}

.imglib__uploadActions {
  display: flex;
  gap: 10px;
}

.imglib__right {
  min-width: 0;
}

.imglib__loading,
.imglib__error {
  text-align: center;
  padding: 40px;
  color: #6b7280;
}

.imglib__error {
  color: #ef4444;
}

.imglib__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}

.imglib__item {
  position: relative;
  border: 1px solid #e5e7eb;
  border-radius: 14px;
  overflow: hidden;
  background: #fff;
}

.imglib__item.selected {
  border-color: rgba(37, 99, 235, 0.7);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15);
}

.imglib__select {
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

.imglib__check {
  color: #2563eb;
}

.imglib__thumb {
  width: 100%;
  height: 160px;
  display: block;
}

.imglib__meta {
  padding: 10px 10px 12px;
  display: grid;
  gap: 6px;
}

.imglib__metaTop {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.imglib__name {
  font-size: 13px;
  font-weight: 700;
  color: #111827;
  min-width: 0;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.imglib__menu {
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 18px;
  line-height: 1;
  padding: 0 2px;
  color: #6b7280;
}

.imglib__row {
  font-size: 12px;
  color: #6b7280;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.imglib__tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

@media (max-width: 1000px) {
  .imglib__layout {
    grid-template-columns: 1fr;
  }

  .imglib__search {
    width: 220px;
  }
}
</style>
