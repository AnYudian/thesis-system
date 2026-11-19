<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Download, Refresh } from '@element-plus/icons-vue'

import { statsApi, type Report } from '@/api/stats'
import { formatTime } from '@/utils/format'

const loading = ref(true)
const data = ref<Report | null>(null)

const summary = computed(() => data.value?.summary)
const stages = computed(() => data.value?.stages ?? [])
const teachers = computed(() => data.value?.teachers ?? [])
const activity = computed(() => data.value?.activity ?? [])

const maxActivity = computed(() =>
  Math.max(1, ...activity.value.map((d) => d.materials + d.approvals + d.returns)),
)

const totalStudents = computed(() => summary.value?.students_total ?? 0)

function pct(rate: number | null | undefined) {
  if (rate === null || rate === undefined) return '—'
  return `${Math.round(rate * 1000) / 10}%`
}

function hours(hours: number | null | undefined) {
  if (hours === null || hours === undefined) return '—'
  if (hours < 24) return `${hours.toFixed(1)} 小时`
  return `${(hours / 24).toFixed(1)} 天`
}

function stageShare(count: number) {
  if (!totalStudents.value) return '0%'
  return `${Math.round((count / totalStudents.value) * 100)}%`
}

function barHeight(value: number) {
  return `${Math.max(value ? 4 : 0, Math.round((value / maxActivity.value) * 100))}%`
}

function shortDate(iso: string) {
  return iso.slice(5).replace('-', '/')
}

const allQuiet = computed(() =>
  activity.value.every((d) => !d.materials && !d.approvals && !d.returns),
)

async function load() {
  loading.value = true
  try {
    data.value = await statsApi.report(14)
  } finally {
    loading.value = false
  }
}

/** 导出在浏览器端拼 CSV：报表数据已经全量在手，不必再让后端写一遍 Excel */
function exportCsv() {
  if (!data.value) return
  const s = data.value.summary
  const rows: (string | number)[][] = [
    ['统计报表', new Date().toLocaleString('zh-CN')],
    [],
    ['指标', '数值'],
    ['学生总数', s.students_total],
    ['进行中', s.in_progress],
    ['已归档', s.archived],
    ['指导教师', s.teachers_total],
    ['材料版本数', s.materials_total],
    ['审核次数', s.reviews_total],
    ['通过次数', s.approved],
    ['退回次数', s.returned],
    ['通过率', pct(s.approve_rate)],
    ['平均审核时长', hours(s.avg_review_hours)],
    [],
    ['环节', '当前学生', '材料', '审核', '通过', '退回'],
    ...data.value.stages.map((r) => [r.label, r.students, r.materials, r.reviews, r.approved, r.returned]),
    [],
    ['指导教师', '学生', '进行中', '已归档', '材料', '审核', '通过率', '最近审核'],
    ...data.value.teachers.map((r) => [
      r.name,
      r.students,
      r.active,
      r.archived,
      r.materials,
      r.reviews,
      pct(r.approve_rate),
      r.last_reviewed_at ? formatTime(r.last_reviewed_at) : '—',
    ]),
  ]
  const csv = rows
    .map((row) => row.map((cell) => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\r\n')
  // 带 BOM：Excel 直接双击打开不会把中文变乱码
  const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `毕设统计-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="report">
    <header class="head">
      <div>
        <p class="eyebrow">ANALYTICS · 2026 届</p>
        <h2>统计报表</h2>
        <p class="sub">
          按环节、按指导教师汇总进度与审核质量；通过率 = 通过次数 / 审核总次数，平均审核时长按“交材料 → 教师处理”计算。
        </p>
      </div>
      <div class="head-actions">
        <el-button :icon="Download" size="small" plain @click="exportCsv">导出 CSV</el-button>
        <el-button :icon="Refresh" size="small" plain @click="load">刷新</el-button>
      </div>
    </header>

    <template v-if="summary">
      <section class="metrics">
        <article class="metric">
          <p class="metric-label">学生总数</p>
          <p class="metric-value">{{ summary.students_total }}</p>
          <p class="metric-note">进行中 {{ summary.in_progress }} · 已归档 {{ summary.archived }}</p>
        </article>
        <article class="metric">
          <p class="metric-label">材料版本</p>
          <p class="metric-value">{{ summary.materials_total }}</p>
          <p class="metric-note">同一环节多次提交分别计数</p>
        </article>
        <article class="metric">
          <p class="metric-label">审核次数</p>
          <p class="metric-value">{{ summary.reviews_total }}</p>
          <p class="metric-note">通过 {{ summary.approved }} · 退回 {{ summary.returned }}</p>
        </article>
        <article class="metric">
          <p class="metric-label">通过率</p>
          <p class="metric-value">{{ pct(summary.approve_rate) }}</p>
          <p class="metric-note">
            {{ summary.reviews_total ? `基于 ${summary.reviews_total} 次审核` : '还没有审核记录' }}
          </p>
        </article>
        <article class="metric">
          <p class="metric-label">平均审核时长</p>
          <p class="metric-value">{{ hours(summary.avg_review_hours) }}</p>
          <p class="metric-note">从提交材料到教师处理</p>
        </article>
      </section>

      <div class="grid">
        <article class="panel">
          <header class="panel-head">
            <div>
              <h3>环节维度</h3>
              <p>每个环节当前停留人数、材料与审核情况</p>
            </div>
            <span class="panel-tip">共 {{ stages.length }} 个环节</span>
          </header>

          <el-table :data="stages" size="small" row-key="stage">
            <el-table-column label="环节" min-width="150">
              <template #default="{ row }">
                <span class="cell-main">{{ row.label }}</span>
                <span class="cell-sub">占学生总数 {{ stageShare(row.students) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="当前学生" width="82" align="right">
              <template #default="{ row }"><b class="num">{{ row.students }}</b></template>
            </el-table-column>
            <el-table-column label="材料" width="64" align="right">
              <template #default="{ row }">{{ row.materials }}</template>
            </el-table-column>
            <el-table-column label="审核" width="64" align="right">
              <template #default="{ row }">{{ row.reviews }}</template>
            </el-table-column>
            <el-table-column label="通过 / 退回" width="104" align="right">
              <template #default="{ row }">
                <span class="ok">{{ row.approved }}</span>
                <span class="sep">/</span>
                <span class="bad">{{ row.returned }}</span>
              </template>
            </el-table-column>
          </el-table>
        </article>

        <article class="panel chart-panel">
          <header class="panel-head">
            <div>
              <h3>近 14 天动态</h3>
              <p>材料提交与审核动作，按本地日期归组</p>
            </div>
            <span class="legend">
              <i class="dot dot-material" />材料
              <i class="dot dot-ok" />通过
              <i class="dot dot-bad" />退回
            </span>
          </header>

          <div v-if="allQuiet" class="quiet">近 14 天没有材料提交和审核动作。</div>
          <div v-else class="chart">
            <div v-for="d in activity" :key="d.date" class="col">
              <div
                class="stack"
                :title="`${d.date}：材料 ${d.materials}，通过 ${d.approvals}，退回 ${d.returns}`"
              >
                <div class="seg seg-material" :style="{ height: barHeight(d.materials) }" />
                <div class="seg seg-ok" :style="{ height: barHeight(d.approvals) }" />
                <div class="seg seg-bad" :style="{ height: barHeight(d.returns) }" />
              </div>
              <span class="col-label">{{ shortDate(d.date) }}</span>
            </div>
          </div>
        </article>
      </div>

      <article class="panel">
        <header class="panel-head">
          <div>
            <h3>指导教师维度</h3>
            <p>名下学生数、材料与审核工作量；“未指派”是还没分导师的学生</p>
          </div>
          <span class="panel-tip">{{ teachers.length }} 组</span>
        </header>

        <el-table :data="teachers" size="small" row-key="name">
          <el-table-column label="指导教师" min-width="130">
            <template #default="{ row }">
              <span class="cell-main">{{ row.name }}</span>
              <span v-if="row.teacher_id === null" class="cell-sub">待管理员分配</span>
            </template>
          </el-table-column>
          <el-table-column label="学生" width="76" align="right">
            <template #default="{ row }"><b class="num">{{ row.students }}</b></template>
          </el-table-column>
          <el-table-column label="进行中 / 归档" width="120" align="right">
            <template #default="{ row }">{{ row.active }} / {{ row.archived }}</template>
          </el-table-column>
          <el-table-column label="材料" width="64" align="right">
            <template #default="{ row }">{{ row.materials }}</template>
          </el-table-column>
          <el-table-column label="审核" width="64" align="right">
            <template #default="{ row }">{{ row.reviews }}</template>
          </el-table-column>
          <el-table-column label="通过率" width="150">
            <template #default="{ row }">
              <div class="rate">
                <div class="rate-bar">
                  <div class="rate-fill" :style="{ width: `${(row.approve_rate ?? 0) * 100}%` }" />
                </div>
                <span class="rate-text">{{ pct(row.approve_rate) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="最近审核" width="140">
            <template #default="{ row }">
              <span class="time">{{ row.last_reviewed_at ? formatTime(row.last_reviewed_at) : '—' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </article>
    </template>
  </div>
</template>

<style scoped>
/* 右侧和左侧环节表同高：让图区吃掉剩余高度，避免下方一大片空白 */
.chart-panel {
  display: flex;
  flex-direction: column;
}

.report {
  display: flex;
  flex-direction: column;
  gap: 18px;
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

.head-actions {
  display: flex;
  gap: 8px;
  white-space: nowrap;
}

.metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 1100px) {
  .metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

.metric {
  padding: 14px 16px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-top: 2px solid var(--th-primary);
  border-radius: 4px;
}

.metric-label {
  margin: 0;
  font-size: 12px;
  color: var(--th-text-muted);
}

.metric-value {
  margin: 6px 0 2px;
  font-family: var(--th-font-serif);
  font-size: 26px;
  line-height: 1.1;
  color: var(--th-primary-deep);
}

.metric-note {
  margin: 0;
  font-size: 11.5px;
  color: #a29a8b;
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  gap: 14px;
}

@media (max-width: 1180px) {
  .grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

.panel {
  padding: 18px 20px 16px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.05);
}

.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  margin-bottom: 6px;
  border-bottom: 1px solid var(--th-border-soft);
}

.panel-head h3 {
  margin: 0;
  font-size: 15px;
  color: var(--th-primary-deep);
}

.panel-head p {
  margin: 3px 0 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.panel-tip {
  font-size: 11.5px;
  color: #a29a8b;
  white-space: nowrap;
}

.cell-main {
  display: block;
  font-size: 13px;
}

.cell-sub {
  display: block;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.num {
  font-family: var(--th-font-serif);
  font-size: 15px;
  color: var(--th-primary);
}

.ok {
  color: var(--th-primary);
}

.sep {
  margin: 0 4px;
  color: #c9c1b1;
}

.bad {
  color: #a33a2a;
}

.time {
  font-size: 12px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.legend {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 1px;
}

.dot-material {
  background: var(--th-accent);
}

.dot-ok {
  background: var(--th-primary);
}

.dot-bad {
  background: #a33a2a;
  margin-left: 6px;
}

.chart {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  flex: 1;
  min-height: 168px;
  padding-top: 10px;
}

.col {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  height: 100%;
  min-width: 0;
}

.stack {
  display: flex;
  flex: 1;
  flex-direction: column;
  justify-content: flex-end;
  width: 100%;
  max-width: 22px;
  background: rgba(29, 51, 84, 0.04);
  border-radius: 2px 2px 0 0;
}

.seg {
  width: 100%;
}

.seg-material {
  background: var(--th-accent);
}

.seg-ok {
  background: var(--th-primary);
}

.seg-bad {
  background: #a33a2a;
}

.col-label {
  font-size: 10px;
  color: #a29a8b;
  white-space: nowrap;
}

.quiet {
  display: grid;
  place-items: center;
  flex: 1;
  min-height: 168px;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.rate {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rate-bar {
  flex: 1;
  height: 6px;
  background: rgba(29, 51, 84, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.rate-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--th-primary), #3d6288);
}

.rate-text {
  flex: none;
  width: 44px;
  font-size: 12px;
  color: var(--th-text-muted);
  text-align: right;
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
