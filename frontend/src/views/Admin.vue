<template>
  <div class="admin">
    <div class="admin__header">
      <div>
        <div class="admin__title">产品后台管理</div>
        <div class="admin__subtitle">产品知识库、手册生成等管理入口</div>
      </div>
    </div>

    <div class="admin__grid">
      <el-card class="admin__card" shadow="hover">
        <div class="admin__cardTitle">产品知识库</div>
        <div class="admin__cardDesc">检索物料编码 / 配件名称，并查看对应资料入口。</div>
        <div class="admin__cardActions">
          <el-button type="primary" @click="goHomeTab('kbSearch')">进入</el-button>
        </div>
      </el-card>

      <el-card class="admin__card" shadow="hover">
        <div class="admin__cardTitle">生成产品手册</div>
        <div class="admin__cardDesc">上传产品/配件文件，完成 OCR 后进入说明书编辑页。</div>
        <div class="admin__cardActions">
          <el-button type="primary" @click="goHomeTab('manual')">进入</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const router = useRouter()

const goHomeTab = (tab) => {
  router.push({ path: '/', query: { tab } })
}
</script>

<style scoped>
.admin {
  padding: 18px;
}

.admin__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.admin__title {
  font-size: 18px;
  font-weight: 700;
  color: #111827;
  line-height: 1.2;
}

.admin__subtitle {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}

.admin__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.admin__card {
  border-radius: 12px;
}

.admin__cardTitle {
  font-size: 14px;
  font-weight: 700;
  color: #111827;
}

.admin__cardDesc {
  font-size: 12px;
  color: #6b7280;
  margin-top: 6px;
  line-height: 1.6;
}

.admin__cardActions {
  margin-top: 12px;
}

@media (max-width: 900px) {
  .admin__grid {
    grid-template-columns: 1fr;
  }
}
</style>
