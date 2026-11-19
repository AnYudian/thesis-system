<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { Refresh, Search } from '@element-plus/icons-vue'

import { logsApi, type AuditLog } from '@/api/logs'
import { ACTION_META, ACTIONS, DETAIL_LABELS } from '@/constants/actions'
import { STAGE_SHORT } from '@/constants/stages'
import { formatTime } from '@/utils/format'

const loading = ref(false)
const items = ref<AuditLog[]>([])
const total = ref(0)

const query = reactive({ page: 1, size: 20, action: '', keyword: '' })

const roleLabels: Record<string, string> = { ADMIN: '管理员', TEACHER: '教师', STUDENT: '学生' }

const targetLabels: Record<string, string> = {
  USER: '账号',
  STUDENT: '学生',
  MATERIAL: '材料',
}

function actionLabel(action: string) {
  return ACTION_META[action]?.label ?? action
}

function actionTone(action: string) {
  return `tone-${ACTION_META[action]?.tone ?? 'muted'}`
}

/** 把 JSONB 详情拼成一行中文；环节名走本地常量，日志里不存中文，改文案不影响历史 */
function detailText(log: AuditLog) {
  if (!log.detail) return '—'
  const parts = Object.entries(log.detail)
    .filter(([, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => {
      const label = DETAIL_LABELS[key] ?? key
      let text: string
      if (key === 'stage' || key === 'to_stage') {
        text = STAGE_SHORT[String(value)] ?? String(value)
      } else if (Array.isArray(value)) {
        text = value.join(' / ')
      } else if (typeof value === 'boolean') {
        text = value ? '是' : '否'
      } else {
        text = String(value)
      }
      return `${label} ${text}`
    })
  return parts.join(' · ') || '—'
}

async function load() {
  loading.value = true
  try {
    const data = await logsApi.list({
      page: query.page,
      size: query.size,
      action: query.action || undefined,
      keyword: query.keyword || undefined,
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
  query.action = ''
  query.keyword = ''
  search()
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <p class="eyebrow">AUDIT LOG</p>
        <h2>操作日志</h2>
        <p class="sub">
          登录、账号变更、学生建档、材料上传、阶段审核都会自动留痕。日志只增不改，用于事后追责与过程检查。
        </p>
      </div>
      <span class="count">共 <b>{{ total }}</b> 条</span>
    </header>

    <section class="toolbar">
      <el-select v-model="query.action" class="tool-select" placeholder="全部动作" clearable @change="search">
        <el-option v-for="a in ACTIONS" :key="a.value" :label="a.label" :value="a.value" />
      </el-select>
      <el-input
        v-model="query.keyword"
        class="tool-input"
        placeholder="操作人 / 学号 / 账号 / 详情关键词"
        clearable
        :prefix-icon="Search"
        @keyup.enter="search"
        @clear="search"
      />
      <el-button :icon="Search" @click="search">查询</el-button>
      <el-button :icon="Refresh" plain @click="reset">重置</el-button>
    </section>

    <section class="table-wrap">
      <el-table v-loading="loading" :data="items" stripe row-key="id">
        <el-table-column label="时间" width="142">
          <template #default="{ row }"><span class="time">{{ formatTime(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作人" width="146">
          <template #default="{ row }">
            <span class="cell-main">{{ row.real_name || row.username || '已删除账号' }}</span>
            <span v-if="row.username" class="cell-sub">{{ row.username }}</span>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="78">
          <template #default="{ row }">
            <span class="role">{{ row.role ? roleLabels[row.role] : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="动作" width="112">
          <template #default="{ row }">
            <span class="action" :class="actionTone(row.action)">{{ actionLabel(row.action) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="对象" width="110">
          <template #default="{ row }">
            <span v-if="row.target_type" class="target">
              {{ targetLabels[row.target_type] || row.target_type }}
              <em v-if="row.target_id">#{{ row.target_id }}</em>
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="300">
          <template #default="{ row }">
            <span class="detail" :title="detailText(row)">{{ detailText(row) }}</span>
          </template>
        </el-table-column>
        <template #empty>
          <p class="empty">还没有操作记录。登录、建档、上传、审核后会自动出现在这里。</p>
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          :total="total"
          :page-sizes="[20, 50, 100]"
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
  max-width: 760px;
  margin: 6px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
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

.tool-select {
  width: 150px;
}

.tool-input {
  width: 220px;
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

.time {
  font-size: 12px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.role {
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.action {
  display: inline-block;
  padding: 1px 7px;
  font-size: 11.5px;
  border-radius: 3px;
  white-space: nowrap;
}

.action.tone-ok {
  color: #2f6b4f;
  background: rgba(47, 107, 79, 0.08);
  border: 1px solid rgba(47, 107, 79, 0.22);
}

.action.tone-warn {
  color: #8a6a1f;
  background: rgba(198, 168, 107, 0.16);
  border: 1px solid rgba(198, 168, 107, 0.4);
}

.action.tone-bad {
  color: #a33a2a;
  background: rgba(163, 58, 42, 0.08);
  border: 1px solid rgba(163, 58, 42, 0.25);
}

.action.tone-muted {
  color: var(--th-text-muted);
  background: rgba(29, 51, 84, 0.05);
  border: 1px solid var(--th-border-soft);
}

.target {
  font-size: 12.5px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.target em {
  font-style: normal;
  font-size: 11px;
  color: #a29a8b;
}

.detail {
  display: block;
  font-size: 12px;
  color: var(--th-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.muted {
  color: #a29a8b;
}

.empty {
  margin: 0;
  padding: 16px 0;
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
