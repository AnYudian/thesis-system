<script setup lang="ts">
/**
 * 统计报表：历史数据分析 + 导出。
 *
 * 与「数据概览」的分工：
 * - 概览 = 实时看板（今天谁在提交、谁刚登录、在途多少），只看当下；
 * - 报表 = 趋势与结构（环节分布、教师工作量、指导留痕、截止逾期），可导出交材料。
 * 所以这里全部用图表呈现，表格只作为明细补充。
 */
import { computed, nextTick, onMounted, ref } from 'vue'
import { Download, Document, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { EChartsOption } from 'echarts'

import EChart from '@/components/EChart.vue'
import { statsApi, type Report } from '@/api/stats'
import { STAGE_SHORT } from '@/constants/stages'
import { formatTime } from '@/utils/format'

const C = {
  primary: '#1d3354',
  soft: '#2c4a73',
  accent: '#9c7c46',
  accentSoft: '#c6a86b',
  muted: '#7a8fa6',
  red: '#a33c2a',
  green: '#3f7d5a',
}

const loading = ref(true)
const exporting = ref<'excel' | 'pdf' | null>(null)
const days = ref(14)
const data = ref<Report | null>(null)
const reportEl = ref<HTMLDivElement | null>(null)
const generatedAt = ref('')
const capturing = ref(false)

const summary = computed(() => data.value?.summary)
const stages = computed(() => data.value?.stages ?? [])
const teachers = computed(() => data.value?.teachers ?? [])
const activity = computed(() => data.value?.activity ?? [])
const deadlines = computed(() => data.value?.deadlines ?? [])
const guidance = computed(() => data.value?.guidance)
const overdueTotal = computed(() =>
  deadlines.value.reduce((sum, row) => sum + row.overdue, 0),
)

function pct(rate: number | null | undefined) {
  if (rate === null || rate === undefined) return '—'
  return `${Math.round(rate * 1000) / 10}%`
}

function hours(value: number | null | undefined) {
  if (value === null || value === undefined) return '—'
  if (value < 24) return `${value.toFixed(1)} 小时`
  return `${(value / 24).toFixed(1)} 天`
}

function shortDate(iso: string) {
  return iso.slice(5).replace('-', '/')
}

const stageShortNames = computed(() => stages.value.map((row) => STAGE_SHORT[row.stage] ?? row.label))

// ---------- 图表配置 ----------
const tooltipBase = {
  backgroundColor: 'rgba(255,255,255,0.96)',
  borderColor: '#d6cdb9',
  textStyle: { color: '#2c2a26', fontSize: 12 },
}

const stageBarOption = computed<EChartsOption>(() => ({
  animation: false,
  grid: { left: 8, right: 8, top: 28, bottom: 4, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipBase },
  xAxis: {
    type: 'category',
    data: stageShortNames.value,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#d6cdb9' } },
    axisLabel: { color: '#6b6355', fontSize: 11, interval: 0 },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    splitLine: { lineStyle: { color: '#efe9dc' } },
    axisLabel: { color: '#8a8375', fontSize: 11 },
  },
  series: [
    {
      name: '在环节学生',
      type: 'bar',
      data: stages.value.map((row) => row.students),
      barMaxWidth: 26,
      itemStyle: { color: C.primary, borderRadius: [2, 2, 0, 0] },
      label: { show: true, position: 'top', color: '#6b6355', fontSize: 11 },
    },
  ],
}))

const completionOption = computed<EChartsOption>(() => {
  const total = summary.value?.students_total ?? 0
  const archived = summary.value?.archived ?? 0
  const value = total ? Math.round((archived / total) * 1000) / 10 : 0
  return {
    animation: false,
    series: [
      {
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        min: 0,
        max: 100,
        radius: '92%',
        center: ['50%', '58%'],
        progress: { show: true, width: 14, itemStyle: { color: C.accent } },
        axisLine: { lineStyle: { width: 14, color: [[1, '#ece5d6']] } },
        axisTick: { show: false },
        splitNumber: 5,
        splitLine: { length: 8, lineStyle: { color: '#c9c1b1' } },
        axisLabel: { color: '#8a8375', fontSize: 10, distance: 12 },
        pointer: { show: false },
        anchor: { show: false },
        title: { offsetCenter: [0, '34%'], color: '#6b6355', fontSize: 12 },
        detail: {
          valueAnimation: false,
          offsetCenter: [0, '2%'],
          formatter: '{value}%',
          color: C.primary,
          fontSize: 26,
          fontWeight: 600,
        },
        data: [{ value, name: `已归档 ${archived} / ${total}` }],
      },
    ],
  }
})

const verdictOption = computed<EChartsOption>(() => {
  const approved = summary.value?.approved ?? 0
  const returned = summary.value?.returned ?? 0
  const total = approved + returned
  return {
    animation: false,
    tooltip: { trigger: 'item', formatter: '{b}：{c} 次（{d}%）', ...tooltipBase },
    legend: { bottom: 0, icon: 'rect', itemWidth: 9, itemHeight: 9, textStyle: { color: '#6b6355', fontSize: 12 } },
    graphic: total
      ? []
      : [{ type: 'text', left: 'center', top: 'middle', style: { text: '还没有审核记录', fill: '#a29a8b', fontSize: 12 } }],
    series: [
      {
        type: 'pie',
        radius: ['46%', '66%'],
        center: ['50%', '46%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}\n{c} 次', color: '#6b6355', fontSize: 11 },
        data: [
          { name: '通过', value: approved, itemStyle: { color: C.primary } },
          { name: '退回', value: returned, itemStyle: { color: C.red } },
        ],
      },
    ],
  }
})

const stageReviewOption = computed<EChartsOption>(() => ({
  animation: false,
  grid: { left: 8, right: 8, top: 34, bottom: 4, containLabel: true },
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipBase },
  legend: { top: 0, right: 0, icon: 'rect', itemWidth: 9, itemHeight: 9, textStyle: { color: '#6b6355', fontSize: 11 } },
  xAxis: {
    type: 'category',
    data: stageShortNames.value,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#d6cdb9' } },
    axisLabel: { color: '#6b6355', fontSize: 11, interval: 0 },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    splitLine: { lineStyle: { color: '#efe9dc' } },
    axisLabel: { color: '#8a8375', fontSize: 11 },
  },
  series: [
    {
      name: '通过',
      type: 'bar',
      stack: 'review',
      data: stages.value.map((row) => row.approved),
      barMaxWidth: 24,
      itemStyle: { color: C.green },
    },
    {
      name: '退回',
      type: 'bar',
      stack: 'review',
      data: stages.value.map((row) => row.returned),
      barMaxWidth: 24,
      itemStyle: { color: C.red },
    },
  ],
}))

const activityOption = computed<EChartsOption>(() => ({
  animation: false,
  grid: { left: 8, right: 12, top: 34, bottom: 4, containLabel: true },
  tooltip: { trigger: 'axis', ...tooltipBase },
  legend: { top: 0, right: 0, icon: 'rect', itemWidth: 9, itemHeight: 9, textStyle: { color: '#6b6355', fontSize: 11 } },
  xAxis: {
    type: 'category',
    boundaryGap: false,
    data: activity.value.map((point) => shortDate(point.date)),
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#d6cdb9' } },
    axisLabel: { color: '#6b6355', fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    splitLine: { lineStyle: { color: '#efe9dc' } },
    axisLabel: { color: '#8a8375', fontSize: 11 },
  },
  series: [
    {
      name: '材料提交',
      type: 'line',
      smooth: true,
      symbolSize: 5,
      data: activity.value.map((point) => point.materials),
      itemStyle: { color: C.accent },
      lineStyle: { width: 2 },
      areaStyle: { color: 'rgba(156,124,70,0.10)' },
    },
    {
      name: '通过',
      type: 'line',
      smooth: true,
      symbolSize: 5,
      data: activity.value.map((point) => point.approvals),
      itemStyle: { color: C.primary },
      lineStyle: { width: 2 },
    },
    {
      name: '退回',
      type: 'line',
      smooth: true,
      symbolSize: 5,
      data: activity.value.map((point) => point.returns),
      itemStyle: { color: C.red },
      lineStyle: { width: 2 },
    },
  ],
}))

const guidanceOption = computed<EChartsOption>(() => {
  const meet = guidance.value?.meet ?? 0
  const online = guidance.value?.online ?? 0
  const total = meet + online
  return {
    animation: false,
    tooltip: { trigger: 'item', formatter: '{b}：{c} 次（{d}%）', ...tooltipBase },
    legend: { bottom: 0, icon: 'rect', itemWidth: 9, itemHeight: 9, textStyle: { color: '#6b6355', fontSize: 12 } },
    graphic: total
      ? []
      : [{ type: 'text', left: 'center', top: 'middle', style: { text: '还没有指导记录', fill: '#a29a8b', fontSize: 12 } }],
    series: [
      {
        type: 'pie',
        radius: ['46%', '66%'],
        center: ['50%', '46%'],
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}\n{c} 次', color: '#6b6355', fontSize: 11 },
        data: [
          { name: '面谈', value: meet, itemStyle: { color: C.soft } },
          { name: '线上', value: online, itemStyle: { color: C.accentSoft } },
        ],
      },
    ],
  }
})

const teacherOption = computed<EChartsOption>(() => {
  const rows = teachers.value.slice(0, 8).reverse()
  return {
    animation: false,
    grid: { left: 8, right: 24, top: 30, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipBase },
    legend: { top: 0, right: 0, icon: 'rect', itemWidth: 9, itemHeight: 9, textStyle: { color: '#6b6355', fontSize: 11 } },
    xAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: '#efe9dc' } },
      axisLabel: { color: '#8a8375', fontSize: 11 },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => row.name),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#d6cdb9' } },
      axisLabel: { color: '#6b6355', fontSize: 11 },
    },
    series: [
      {
        name: '学生数',
        type: 'bar',
        data: rows.map((row) => row.students),
        barMaxWidth: 12,
        itemStyle: { color: C.soft, borderRadius: [0, 2, 2, 0] },
      },
      {
        name: '审核次数',
        type: 'bar',
        data: rows.map((row) => row.reviews),
        barMaxWidth: 12,
        itemStyle: { color: C.accentSoft, borderRadius: [0, 2, 2, 0] },
      },
    ],
  }
})

const majorOption = computed<EChartsOption>(() => ({
  animation: false,
  tooltip: { trigger: 'item', formatter: '{b}：{c} 人（{d}%）', ...tooltipBase },
  legend: { bottom: 0, icon: 'rect', itemWidth: 9, itemHeight: 9, textStyle: { color: '#6b6355', fontSize: 11 } },
  series: [
    {
      type: 'pie',
      radius: ['40%', '65%'],
      center: ['50%', '44%'],
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { formatter: '{b}\n{c} 人', color: '#6b6355', fontSize: 11 },
      data: (data.value?.majors ?? []).map((item, index) => ({
        name: item.name,
        value: item.count,
        itemStyle: { color: [C.primary, C.accent, C.muted, C.accentSoft, C.soft, C.green][index % 6] },
      })),
    },
  ],
}))

const classOption = computed<EChartsOption>(() => {
  const rows = (data.value?.classes ?? []).slice(0, 10).reverse()
  return {
    animation: false,
    grid: { left: 8, right: 24, top: 16, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, ...tooltipBase },
    xAxis: {
      type: 'value',
      minInterval: 1,
      splitLine: { lineStyle: { color: '#efe9dc' } },
      axisLabel: { color: '#8a8375', fontSize: 11 },
    },
    yAxis: {
      type: 'category',
      data: rows.map((row) => row.name),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: '#d6cdb9' } },
      axisLabel: { color: '#6b6355', fontSize: 11 },
    },
    series: [
      {
        name: '人数',
        type: 'bar',
        data: rows.map((row) => row.count),
        barMaxWidth: 14,
        itemStyle: { color: C.primary, borderRadius: [0, 2, 2, 0] },
        label: { show: true, position: 'right', color: '#6b6355', fontSize: 11 },
      },
    ],
  }
})

const overdueOption = computed<EChartsOption>(() => ({
  animation: false,
  grid: { left: 8, right: 8, top: 34, bottom: 4, containLabel: true },
  tooltip: {
    trigger: 'axis',
    axisPointer: { type: 'shadow' },
    formatter: (params: unknown) => {
      const list = params as { dataIndex: number; seriesName: string; value: number; color: string }[]
      const row = deadlines.value[list[0]?.dataIndex ?? 0]
      if (!row) return ''
      const head = `${row.label}<br/>截止：${row.deadline ?? '未设置'}`
      return [head, ...list.map((item) => `${item.seriesName}：${item.value} 人`)].join('<br/>')
    },
    ...tooltipBase,
  },
  legend: { top: 0, right: 0, icon: 'rect', itemWidth: 9, itemHeight: 9, textStyle: { color: '#6b6355', fontSize: 11 } },
  xAxis: {
    type: 'category',
    data: stageShortNames.value,
    axisTick: { show: false },
    axisLine: { lineStyle: { color: '#d6cdb9' } },
    axisLabel: { color: '#6b6355', fontSize: 11, interval: 0 },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    splitLine: { lineStyle: { color: '#efe9dc' } },
    axisLabel: { color: '#8a8375', fontSize: 11 },
  },
  series: [
    {
      name: '在环节学生',
      type: 'bar',
      data: deadlines.value.map((row) => row.students),
      barMaxWidth: 24,
      itemStyle: { color: '#dcd4c4' },
    },
    {
      name: '已逾期',
      type: 'bar',
      data: deadlines.value.map((row) => row.overdue),
      barMaxWidth: 24,
      itemStyle: { color: C.red },
    },
  ],
}))

const gradeOption = computed<EChartsOption>(() => {
  const rows = data.value?.grades ?? []
  return {
    animation: false,
    tooltip: { trigger: 'item', formatter: '{b} 级：{c} 人（{d}%）', ...tooltipBase },
    legend: { bottom: 0, icon: 'rect', itemWidth: 9, itemHeight: 9, textStyle: { color: '#6b6355', fontSize: 11 } },
    series: [
      {
        type: 'pie',
        radius: ['46%', '66%'],
        center: ['50%', '45%'],
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b} 级\n{c} 人', color: '#6b6355', fontSize: 11 },
        data: rows.map((item, index) => ({
          name: item.name,
          value: item.count,
          itemStyle: { color: [C.soft, C.accentSoft, C.muted, C.accent][index % 4] },
        })),
      },
    ],
  }
})

// ---------- 数据与导出 ----------
async function load() {
  loading.value = true
  try {
    data.value = await statsApi.report(days.value)
  } finally {
    loading.value = false
  }
}

async function exportExcel() {
  exporting.value = 'excel'
  try {
    const blob = await statsApi.reportWorkbook(days.value)
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `统计报表-${new Date().toISOString().slice(0, 10)}.xlsx`
    anchor.click()
    URL.revokeObjectURL(url)
    ElMessage.success('Excel 已生成')
  } finally {
    exporting.value = null
  }
}

/**
 * PDF 走"截屏 → 分页贴图"：
 * 服务端生成 PDF 要额外处理中文字体，浏览器截屏所见即所得，图表也不会变形。
 * 图很高时按 A4 可用高度切片，避免整页被压扁看不清。
 */
async function exportPdf() {
  if (!reportEl.value) return
  exporting.value = 'pdf'
  try {
    const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
      import('html2canvas'),
      import('jspdf'),
    ])
    // 等一帧，确保 v-loading 蒙层已撤掉
    await new Promise((resolve) => requestAnimationFrame(() => resolve(null)))
    generatedAt.value = new Date().toLocaleString('zh-CN')
    capturing.value = true
    await nextTick()
    // 等标题块完成布局，否则量的边界和截图内容会差一个报头
    await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(null))))
    const canvas = await html2canvas(reportEl.value, {
      scale: 2,
      backgroundColor: '#ffffff',
      useCORS: true,
      // 必须按浏览器视口宽度克隆：传元素自身宽度时，克隆页里的侧栏仍会占位，
      // 主区域被压窄，图表 canvas 不重排就会被裁掉右半边
      windowWidth: window.innerWidth,
    })

    const pdf = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' })
    const pageWidth = pdf.internal.pageSize.getWidth()
    const pageHeight = pdf.internal.pageSize.getHeight()
    const margin = 8
    const imgWidth = pageWidth - margin * 2
    const usableHeight = pageHeight - margin * 2
    const sliceHeight = Math.floor((canvas.width * usableHeight) / imgWidth)

    // 面板边界（换算到 canvas 像素）：切页时优先在这些位置断开，
    // 否则一张图表会被拦腰截断到两页上，看着像出错
    const box = reportEl.value.getBoundingClientRect()
    const scale = canvas.width / box.width
    const boundaries = Array.from(
      reportEl.value.querySelectorAll<HTMLElement>('.metrics, .panel'),
    )
      .map((node) => (node.getBoundingClientRect().bottom - box.top) * scale)
      .sort((a, b) => a - b)

    const slices: { start: number; end: number }[] = []
    let start = 0
    while (start < canvas.height - 1) {
      let end = start + sliceHeight
      if (end >= canvas.height) {
        end = canvas.height
      } else {
        // 至少填满半页，才允许把断点往前挪到面板底部
        const candidate = boundaries.filter((b) => b > start + sliceHeight * 0.55 && b <= end).pop()
        if (candidate) end = candidate
      }
      slices.push({ start, end })
      start = end
    }

    slices.forEach((slice, index) => {
      if (index > 0) pdf.addPage()
      const height = slice.end - slice.start
      const piece = document.createElement('canvas')
      piece.width = canvas.width
      piece.height = height
      const ctx = piece.getContext('2d')
      if (!ctx) return
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, piece.width, piece.height)
      ctx.drawImage(canvas, 0, slice.start, canvas.width, height, 0, 0, canvas.width, height)
      pdf.addImage(
        piece.toDataURL('image/jpeg', 0.92),
        'JPEG',
        margin,
        margin,
        imgWidth,
        (height * imgWidth) / canvas.width,
      )
    })
    pdf.save(`统计报表-${new Date().toISOString().slice(0, 10)}.pdf`)
    ElMessage.success(`PDF 已生成（${slices.length} 页）`)
  } finally {
    // 报头只在截图期间存在，失败也要收掉，否则页面上会多出一条标题
    capturing.value = false
    exporting.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="report">
    <header class="head">
      <div>
        <p class="eyebrow">ANALYTICS · 2026 届</p>
        <h2>统计报表</h2>
        <p class="sub">
          全流程历史数据的横切分析：环节分布、审核结论、指导留痕、教师工作量与截止逾期。
          与「数据概览」的实时看板互补，这里的图表可直接导出为 Excel 或 PDF 交材料。
        </p>
      </div>
      <div class="head-actions">
        <el-radio-group v-model="days" size="small" @change="load">
          <el-radio-button :value="7">7 天</el-radio-button>
          <el-radio-button :value="14">14 天</el-radio-button>
          <el-radio-button :value="30">30 天</el-radio-button>
          <el-radio-button :value="90">90 天</el-radio-button>
        </el-radio-group>
        <el-button :icon="Download" size="small" plain :loading="exporting === 'excel'" @click="exportExcel">
          导出 Excel
        </el-button>
        <el-button :icon="Document" size="small" plain :loading="exporting === 'pdf'" @click="exportPdf">
          导出 PDF
        </el-button>
        <el-button :icon="Refresh" size="small" plain :loading="loading" @click="load">刷新</el-button>
      </div>
    </header>

    <div ref="reportEl" v-loading="loading" class="report-body">
      <div v-if="capturing" class="pdf-head">
        <div>
          <h1>毕业设计（论文）统计报表</h1>
          <p>2026 届 · 生成于 {{ generatedAt }} · 动态趋势统计近 {{ days }} 天</p>
        </div>
        <span class="pdf-brand">THESIS REVIEW SYSTEM</span>
      </div>
      <template v-if="data">
        <section class="metrics">
          <article class="metric">
            <p class="metric-label">学生总数</p>
            <p class="metric-value">{{ data.summary.students_total }}</p>
            <p class="metric-note">在途 {{ data.summary.in_progress }} · 归档 {{ data.summary.archived }}</p>
          </article>
          <article class="metric">
            <p class="metric-label">指导教师</p>
            <p class="metric-value">{{ data.summary.teachers_total }}</p>
            <p class="metric-note">启用状态的账号</p>
          </article>
          <article class="metric">
            <p class="metric-label">材料版本</p>
            <p class="metric-value">{{ data.summary.materials_total }}</p>
            <p class="metric-note">同一环节多次提交分别计数</p>
          </article>
          <article class="metric">
            <p class="metric-label">审核次数</p>
            <p class="metric-value">{{ data.summary.reviews_total }}</p>
            <p class="metric-note">通过 {{ data.summary.approved }} · 退回 {{ data.summary.returned }}</p>
          </article>
          <article class="metric">
            <p class="metric-label">通过率</p>
            <p class="metric-value">{{ pct(data.summary.approve_rate) }}</p>
            <p class="metric-note">
              {{ data.summary.reviews_total ? `基于 ${data.summary.reviews_total} 次审核` : '还没有审核记录' }}
            </p>
          </article>
          <article class="metric">
            <p class="metric-label">平均审核时长</p>
            <p class="metric-value">{{ hours(data.summary.avg_review_hours) }}</p>
            <p class="metric-note">从提交材料到教师处理</p>
          </article>
          <article class="metric">
            <p class="metric-label">指导记录</p>
            <p class="metric-value">{{ data.guidance.total }}</p>
            <p class="metric-note">
              面谈 {{ data.guidance.meet }} · 线上 {{ data.guidance.online }} · 证据 {{ data.guidance.evidence }}
            </p>
          </article>
          <article class="metric">
            <p class="metric-label">中期达标</p>
            <p class="metric-value">{{ data.guidance.midterm_reached }}</p>
            <p class="metric-note">要求 {{ data.guidance.midterm_required }} 次，共 {{ data.guidance.midterm_total }} 次沟通</p>
          </article>
          <article class="metric">
            <p class="metric-label">逾期学生</p>
            <p class="metric-value" :class="{ warn: overdueTotal > 0 }">{{ overdueTotal }}</p>
            <p class="metric-note">已过截止日期仍停在环节内</p>
          </article>
          <article class="metric">
            <p class="metric-label">有指导记录的学生</p>
            <p class="metric-value">{{ data.guidance.students_with_guidance }}</p>
            <p class="metric-note">占学生总数 {{ pct(data.summary.students_total ? data.guidance.students_with_guidance / data.summary.students_total : null) }}</p>
          </article>
        </section>

        <div class="charts">
          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>九环节在途人数</h3>
                <p>当前停在每个环节的学生数，堆在后面的环节说明流程被卡住</p>
              </div>
            </header>
            <EChart :option="stageBarOption" height="250px" />
          </article>

          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>总体完成度</h3>
                <p>已归档学生占全部学生的比例</p>
              </div>
            </header>
            <EChart :option="completionOption" height="250px" />
          </article>

          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>各环节通过 / 退回</h3>
                <p>退回集中在哪个环节，就是学生最需要指导的地方</p>
              </div>
            </header>
            <EChart :option="stageReviewOption" height="250px" />
          </article>

          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>审核结论占比</h3>
                <p>累计审核动作中通过与退回的比例</p>
              </div>
            </header>
            <EChart :option="verdictOption" height="250px" />
          </article>

          <article class="panel wide">
            <header class="panel-head">
              <div>
                <h3>近 {{ days }} 天动态</h3>
                <p>材料提交与审核动作按本地日期归组</p>
              </div>
            </header>
            <EChart :option="activityOption" height="240px" />
          </article>

          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>指导方式构成</h3>
                <p>中期检查要求留痕，面谈占比能反映线下指导投入</p>
              </div>
            </header>
            <EChart :option="guidanceOption" height="230px" />
          </article>

          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>专业分布</h3>
                <p>学生按所学专业的人数结构</p>
              </div>
            </header>
            <EChart :option="majorOption" height="230px" />
          </article>

          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>教师工作量</h3>
                <p>横向对比名下的学生数与处理过的审核次数</p>
              </div>
            </header>
            <EChart :option="teacherOption" height="230px" />
          </article>

          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>班级人数 Top 10</h3>
                <p>人数最多的十个班级</p>
              </div>
            </header>
            <EChart :option="classOption" height="230px" />
          </article>

          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>各环节截止与逾期</h3>
                <p>浅色是在环节人数，红色是已过截止日期的人数</p>
              </div>
            </header>
            <EChart :option="overdueOption" height="230px" />
          </article>

          <article class="panel">
            <header class="panel-head">
              <div>
                <h3>年级分布</h3>
                <p>按入学年份统计，答辩季通常集中在毕业年级</p>
              </div>
            </header>
            <EChart :option="gradeOption" height="230px" />
          </article>
        </div>

        <article class="panel">
          <header class="panel-head">
            <div>
              <h3>环节明细</h3>
              <p>上图对应的具体数字，便于逐项核对与截图汇报</p>
            </div>
            <span class="panel-tip">共 {{ stages.length }} 个环节</span>
          </header>

          <el-table :data="stages" size="small" row-key="stage">
            <el-table-column label="环节" min-width="170">
              <template #default="{ row }">
                <span class="cell-main">{{ row.label }}</span>
                <span class="cell-sub">
                  占学生总数 {{ pct(data.summary.students_total ? row.students / data.summary.students_total : null) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="当前学生" width="90" align="right">
              <template #default="{ row }"><b class="num">{{ row.students }}</b></template>
            </el-table-column>
            <el-table-column label="材料" width="70" align="right" prop="materials" />
            <el-table-column label="审核" width="70" align="right" prop="reviews" />
            <el-table-column label="通过" width="70" align="right">
              <template #default="{ row }"><span class="ok">{{ row.approved }}</span></template>
            </el-table-column>
            <el-table-column label="退回" width="70" align="right">
              <template #default="{ row }"><span class="bad">{{ row.returned }}</span></template>
            </el-table-column>
            <el-table-column label="通过率" width="90" align="right">
              <template #default="{ row }">
                {{ pct(row.reviews ? row.approved / row.reviews : null) }}
              </template>
            </el-table-column>
          </el-table>
        </article>

        <article class="panel">
          <header class="panel-head">
            <div>
              <h3>指导教师明细</h3>
              <p>名下学生、材料与审核工作量；“未指派”是还没分导师的学生</p>
            </div>
            <span class="panel-tip">{{ teachers.length }} 组</span>
          </header>

          <el-table :data="teachers" size="small" row-key="name">
            <el-table-column label="指导教师" min-width="140">
              <template #default="{ row }">
                <span class="cell-main">{{ row.name }}</span>
                <span v-if="row.teacher_id === null" class="cell-sub">待管理员分配</span>
              </template>
            </el-table-column>
            <el-table-column label="学生" width="76" align="right">
              <template #default="{ row }"><b class="num">{{ row.students }}</b></template>
            </el-table-column>
            <el-table-column label="在途 / 归档" width="120" align="right">
              <template #default="{ row }">{{ row.active }} / {{ row.archived }}</template>
            </el-table-column>
            <el-table-column label="材料" width="70" align="right" prop="materials" />
            <el-table-column label="审核" width="70" align="right" prop="reviews" />
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
            <el-table-column label="最近审核" width="150">
              <template #default="{ row }">
                <span class="time">{{ row.last_reviewed_at ? formatTime(row.last_reviewed_at) : '—' }}</span>
              </template>
            </el-table-column>
          </el-table>
        </article>
      </template>
    </div>
  </div>
</template>

<style scoped>
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
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.report-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 仅导出 PDF 时短暂渲染：带在报告正文里，截图后才移除 */
.pdf-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 2px solid var(--th-primary);
}

.pdf-head h1 {
  margin: 0;
  font-size: 22px;
  color: var(--th-primary-deep);
}

.pdf-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--th-text-muted);
}

.pdf-brand {
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--th-accent);
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

.metric-value.warn {
  color: #a33c2a;
}

.metric-note {
  margin: 0;
  font-size: 11.5px;
  color: #a29a8b;
}

.charts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

@media (max-width: 1180px) {
  .charts {
    grid-template-columns: minmax(0, 1fr);
  }
}

.wide {
  grid-column: span 2;
}

@media (max-width: 1180px) {
  .wide {
    grid-column: span 1;
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

.bad {
  color: #a33c2a;
}

.time {
  font-size: 12px;
  color: var(--th-text-muted);
  white-space: nowrap;
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
