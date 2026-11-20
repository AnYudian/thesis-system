<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, Refresh, Search } from '@element-plus/icons-vue'

import { materialsApi, type Material } from '@/api/materials'
import { STAGES } from '@/constants/stages'
import { useAuthStore } from '@/stores/auth'
import { formatSize, formatTime } from '@/utils/format'

const auth = useAuthStore()
const isAdmin = computed(() => auth.role === 'ADMIN')

const loading = ref(false)
const items = ref<Material[]>([])
const total = ref(0)

const query = reactive({ page: 1, size: 10, keyword: '', stage: '', latestOnly: false })

const stageOptions = STAGES.map((s) => ({ value: s.code, label: s.label }))
const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code

async function load() {
  loading.value = true
  try {
    const data = await materialsApi.list({
      page: query.page,
      size: query.size,
      keyword: query.keyword || undefined,
      stage: query.stage || undefined,
      latest_only: query.latestOnly || undefined,
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  load()
}

function reset() {
  query.keyword = ''
  query.stage = ''
  query.latestOnly = false
  search()
}

async function download(row: Material) {
  await materialsApi.download(row)
}

async function remove(row: Material) {
  await ElMessageBox.confirm(
    `将删除「${row.student_name} · ${row.title}」第 ${row.version} 版，文件不可恢复。`,
    '删除材料',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await materialsApi.remove(row.id)
  ElMessage.success('已删除')
  if (items.value.length === 1 && query.page > 1) query.page -= 1
  await load()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <p class="eyebrow">MATERIALS</p>
        <h2>{{ isAdmin ? '材料中心' : '学生材料' }}</h2>
        <p class="sub">
          {{ query.latestOnly
            ? (isAdmin
              ? '正在只看每个学生每个环节的最终版本；取消勾选可看全部历史版本。'
              : '只显示你名下学生每个环节的最终版本；取消勾选可看全部历史版本。')
            : (isAdmin
              ? '全部学生按环节提交的材料，同一环节多次提交会保留为不同版本。'
              : '只显示你名下学生提交的材料，可下载查看每一版。') }}
        </p>
      </div>
      <span class="count">
        共 <b>{{ total }}</b> 份{{ query.latestOnly ? '（各环节最终版）' : '' }}
      </span>
    </header>

    <section class="toolbar">
      <el-input
        v-model="query.keyword"
        class="tool-input"
        :placeholder="isAdmin ? '学生姓名 / 学号 / 材料名称' : '学号 / 材料名称'"
        clearable
        :prefix-icon="Search"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select v-model="query.stage" class="tool-select" placeholder="全部环节" clearable @change="search">
        <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-checkbox v-model="query.latestOnly" class="tool-check" @change="search">
        只看各环节最终版
      </el-checkbox>
      <el-button :icon="Search" @click="search">查询</el-button>
      <el-button :icon="Refresh" plain @click="reset">重置</el-button>
    </section>

    <section class="table-wrap">
      <el-table v-loading="loading" :data="items" stripe row-key="id">
        <el-table-column label="学生" width="104">
          <template #default="{ row }">
            <span class="cell-main">{{ row.student_name }}</span>
            <span class="cell-sub">{{ row.sno }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="环节" width="156">
          <template #default="{ row }">
            <span class="stage-pill">{{ stageLabel(row.stage) }}</span>
          </template>
        </el-table-column>
        <el-table-column v-else label="环节" width="148">
          <template #default="{ row }">
            <span class="stage-pill">{{ stageLabel(row.stage) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="材料名称" min-width="180">
          <template #default="{ row }">
            <span class="cell-main" :title="row.file_name">{{ row.title }}</span>
            <span class="cell-sub" :title="row.file_name">{{ row.file_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="66">
          <template #default="{ row }"><span class="ver">v{{ row.version }}</span></template>
        </el-table-column>
        <el-table-column label="大小" width="80">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="上传人" width="92">
          <template #default="{ row }">
            <span>{{ row.uploader_name || '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="上传时间" width="156">
          <template #default="{ row }"><span class="time">{{ formatTime(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" :width="isAdmin ? 124 : 78" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :icon="Download" @click="download(row)">下载</el-button>
            <el-button v-if="isAdmin" link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <p class="empty">还没有材料。学生提交后会自动出现在这里。</p>
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="sizes, prev, pager, next"
          background
          @current-change="load"
          @size-change="search"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--th-primary);
  position: relative;
}

.head::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -5px;
  height: 1px;
  background: var(--th-border);
}

.eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--th-accent);
}

.head h2 {
  font-size: 23px;
  color: var(--th-primary-deep);
}

.sub {
  margin: 6px 0 0;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.count {
  font-size: 12.5px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.count b {
  font-family: var(--th-font-serif);
  font-size: 17px;
  color: var(--th-primary);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
}

.tool-input {
  width: 240px;
}

.tool-select {
  width: 160px;
}

.tool-check {
  margin-left: 2px;
  font-size: 13px;
}

.table-wrap {
  padding: 6px 14px 14px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.05);
}

.cell-main {
  display: block;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-sub {
  display: block;
  font-size: 11.5px;
  color: var(--th-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-pill {
  display: inline-block;
  padding: 2px 8px;
  font-size: 12px;
  color: var(--th-primary);
  background: rgba(29, 51, 84, 0.06);
  border: 1px solid var(--th-border-soft);
  border-radius: 3px;
  white-space: nowrap;
}

.time {
  white-space: nowrap;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.ver {
  font-family: var(--th-font-serif);
  font-size: 13px;
  color: var(--th-accent);
}

.empty {
  margin: 0;
  padding: 18px 0;
  font-size: 13px;
  color: var(--th-text-muted);
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}

:deep(.el-table th.el-table__cell) {
  background: rgba(29, 51, 84, 0.04);
  color: var(--th-text-muted);
  font-weight: 600;
}

:deep(.el-table) {
  --el-table-border-color: var(--th-border-soft);
  --el-table-row-hover-bg-color: rgba(198, 168, 107, 0.08);
}
</style>
