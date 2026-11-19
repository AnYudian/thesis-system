<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Refresh, TrendCharts, User, UserFilled, Finished, FolderOpened } from '@element-plus/icons-vue'

import { statsApi, type Overview } from '@/api/stats'
import { STAGES } from '@/constants/stages'

const loading = ref(true)
const data = ref<Overview | null>(null)

const stages = computed(() => {
  const fromApi = data.value?.stages ?? []
  // 后端只回 9 条固定阶段；这里再对一次本地顺序，防止以后后端漏项导致条数不对
  return STAGES.map((meta) => {
    const hit = fromApi.find((s) => s.stage === meta.code)
    return {
      ...meta,
      label: hit?.label || meta.label,
      count: hit?.count ?? 0,
    }
  })
})

const maxCount = computed(() => Math.max(1, ...stages.value.map((s) => s.count)))
const total = computed(() => data.value?.students_total ?? 0)

const metrics = computed(() => [
  { label: '学生总数', value: data.value?.students_total ?? 0, unit: '人', note: '2026 届在库', icon: User, tone: 'navy' },
  { label: '指导教师', value: data.value?.teachers_total ?? 0, unit: '人', note: '在岗账号', icon: UserFilled, tone: 'gold' },
  { label: '进行中', value: data.value?.in_progress ?? 0, unit: '人', note: '尚未归档', icon: TrendCharts, tone: 'teal' },
  { label: '已归档', value: data.value?.archived ?? 0, unit: '人', note: '完成全流程', icon: Finished, tone: 'muted' },
  { label: '材料总数', value: data.value?.materials_total ?? 0, unit: '份', note: '含历史版本', icon: FolderOpened, tone: 'ink' },
])

const roleLabel: Record<string, string> = { ADMIN: '管理员', TEACHER: '教师', STUDENT: '学生' }

function barWidth(count: number) {
  if (!count) return '0%'
  // 最小的非零值也给一点宽度，否则 1 人在图上跟 0 人一样，看不出分布
  return `${Math.max(4, Math.round((count / maxCount.value) * 100))}%`
}

function share(count: number) {
  if (!total.value) return '0%'
  return `${Math.round((count / total.value) * 100)}%`
}

function fmt(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

async function load() {
  loading.value = true
  try {
    data.value = await statsApi.overview()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="overview">
    <section class="head">
      <div>
        <p class="eyebrow">OVERVIEW · 2026 届</p>
        <h2>全过程数据概览</h2>
        <p class="sub">按学生当前所处环节统计，数据取自学生档案的当前阶段。</p>
      </div>
      <el-button :icon="Refresh" size="small" plain @click="load">刷新数据</el-button>
    </section>

    <section class="metrics">
      <article v-for="m in metrics" :key="m.label" class="metric" :class="`tone-${m.tone}`">
        <div class="metric-head">
          <span class="metric-label">{{ m.label }}</span>
          <el-icon class="metric-icon"><component :is="m.icon" /></el-icon>
        </div>
        <p class="metric-value">
          {{ m.value }}<span class="unit">{{ m.unit }}</span>
        </p>
        <p class="metric-note">{{ m.note }}</p>
      </article>
    </section>

    <section class="grid">
      <article class="panel">
        <header class="panel-head">
          <div>
            <h3>九环节进度分布</h3>
            <p>节点上的数字是当前停留在该环节的学生人数</p>
          </div>
          <span class="legend"><i class="legend-dot" />后期接入智能体</span>
        </header>

        <div class="flow">
          <template v-for="(s, i) in stages" :key="s.code">
            <div class="flow-node" :class="{ 'is-ai': s.ai, 'is-empty': !s.count }">
              <span class="flow-count">{{ s.count }}</span>
              <span class="flow-name">{{ s.short }}</span>
              <i v-if="s.ai" class="ai-mark" />
            </div>
            <span v-if="i < stages.length - 1" class="flow-arrow">→</span>
          </template>
        </div>

        <div class="dist">
          <div v-for="(s, i) in stages" :key="s.code" class="dist-row" :class="{ 'is-empty': !s.count }">
            <span class="dist-idx">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="dist-name">
              {{ s.label }}
              <i v-if="s.ai" class="ai-mark ai-mark--inline" />
            </span>
            <div class="dist-bar">
              <div class="dist-fill" :class="{ 'is-ai': s.ai }" :style="{ width: barWidth(s.count) }" />
            </div>
            <span class="dist-count">{{ s.count }} 人</span>
            <span class="dist-share">{{ share(s.count) }}</span>
          </div>
        </div>
      </article>

      <div class="side-col">
        <article class="panel">
          <header class="panel-head">
            <div>
              <h3>最近登录</h3>
              <p>最近 6 次账号登录记录</p>
            </div>
          </header>

          <ul v-if="data?.recent_logins.length" class="logins">
            <li v-for="item in data.recent_logins" :key="item.id">
              <span class="login-avatar">{{ (item.real_name || item.username).slice(0, 1) }}</span>
              <div class="login-main">
                <strong>{{ item.real_name || item.username }}</strong>
                <span class="login-meta">{{ item.username }} · {{ roleLabel[item.role] || item.role }}</span>
              </div>
              <time>{{ fmt(item.created_at) }}</time>
            </li>
          </ul>
          <p v-else class="placeholder">暂无登录记录</p>
        </article>

        <article class="panel panel--plan">
          <header class="panel-head">
            <div>
              <h3>智能体待接入节点</h3>
              <p>先完成流程，再逐个接入审阅能力</p>
            </div>
          </header>
          <div class="plan-chips">
            <span v-for="s in stages.filter((x) => x.ai)" :key="s.code" class="chip">{{ s.short }}</span>
          </div>
          <p class="plan-note">
            当前所有节点均为人工流转；智能体只作为建议来源，是否放行仍由教师决定。
          </p>
        </article>
      </div>
    </section>
  </div>
</template>

<style scoped>
.overview {
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
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--th-text-muted);
}

.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
}

.metric {
  position: relative;
  padding: 16px 18px 14px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.05);
  overflow: hidden;
}

/* 顶部色条区分四张卡的语义，但都用低饱和色，不抢数字 */
.metric::before {
  content: "";
  position: absolute;
  inset: 0 0 auto 0;
  height: 3px;
  background: var(--th-primary);
}

.tone-gold::before { background: var(--th-accent); }
.tone-teal::before { background: #3b6b63; }
.tone-muted::before { background: #9a9384; }
.tone-ink::before { background: #4a6173; }

.metric-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--th-text-muted);
}

.metric-label {
  font-size: 12.5px;
  letter-spacing: 0.06em;
}

.metric-icon {
  font-size: 16px;
  color: var(--th-border);
}

.metric-value {
  margin: 6px 0 0;
  font-family: var(--th-font-serif);
  font-size: 32px;
  font-weight: 700;
  line-height: 1.15;
  color: var(--th-primary-deep);
}

.unit {
  margin-left: 4px;
  font-family: var(--th-font-sans);
  font-size: 12px;
  font-weight: 400;
  color: var(--th-text-muted);
}

.metric-note {
  margin: 2px 0 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 16px;
  align-items: start;
}

@media (max-width: 1100px) {
  .grid {
    grid-template-columns: 1fr;
  }
}

.panel {
  padding: 18px 20px 20px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.05);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--th-border-soft);
}

.panel-head h3 {
  font-size: 16px;
  color: var(--th-primary-deep);
}

.panel-head p {
  margin: 3px 0 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.legend {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.legend-dot,
.ai-mark {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--th-accent);
}

.flow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 12px;
  margin-bottom: 18px;
  background: linear-gradient(180deg, rgba(29, 51, 84, 0.035), rgba(29, 51, 84, 0));
  border: 1px dashed var(--th-border);
  border-radius: 4px;
}

.flow-node {
  position: relative;
  display: flex;
  align-items: baseline;
  gap: 5px;
  padding: 5px 9px 5px 8px;
  background: #fff;
  border: 1px solid var(--th-border);
  border-radius: 3px;
}

.flow-node.is-ai {
  border-color: rgba(156, 124, 70, 0.55);
}

.flow-node.is-empty .flow-count {
  color: #a9a298;
}

.flow-count {
  font-family: var(--th-font-serif);
  font-size: 15px;
  font-weight: 700;
  color: var(--th-primary);
}

.flow-name {
  font-size: 12px;
  color: var(--th-text-muted);
}

.ai-mark {
  position: absolute;
  top: 3px;
  right: 3px;
}

.ai-mark--inline {
  position: static;
  margin-left: 5px;
  vertical-align: 2px;
}

.flow-arrow {
  font-size: 11px;
  color: var(--th-accent-soft);
}

.dist {
  display: flex;
  flex-direction: column;
}

.dist-row {
  display: grid;
  grid-template-columns: 26px minmax(120px, 190px) minmax(0, 1fr) 52px 42px;
  align-items: center;
  gap: 10px;
  padding: 7px 0;
  border-bottom: 1px dotted var(--th-border-soft);
}

.dist-row:last-child {
  border-bottom: none;
}

.dist-idx {
  font-size: 11px;
  letter-spacing: 0.06em;
  color: var(--th-accent);
}

.dist-name {
  font-size: 13px;
  color: var(--th-text);
}

.dist-row.is-empty .dist-name {
  color: #9b958a;
}

.dist-bar {
  height: 8px;
  background: #eee8da;
  border-radius: 4px;
  overflow: hidden;
}

.dist-fill {
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, var(--th-primary-soft), var(--th-primary));
  transition: width 0.5s ease;
}

.dist-fill.is-ai {
  background: linear-gradient(90deg, #b99b62, var(--th-accent));
}

.dist-count {
  font-size: 12.5px;
  font-weight: 600;
  text-align: right;
  color: var(--th-primary-deep);
}

.dist-share {
  font-size: 11.5px;
  text-align: right;
  color: var(--th-text-muted);
}

.side-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.logins {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.logins li {
  display: flex;
  align-items: center;
  gap: 10px;
}

.login-avatar {
  display: grid;
  place-items: center;
  flex: 0 0 30px;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: rgba(29, 51, 84, 0.08);
  color: var(--th-primary);
  font-family: var(--th-font-serif);
  font-size: 13px;
}

.login-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
  line-height: 1.35;
}

.login-main strong {
  font-size: 13px;
  font-weight: 600;
  color: var(--th-primary-deep);
}

.login-meta {
  font-size: 11px;
  color: var(--th-text-muted);
}

.logins time {
  font-size: 11px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.placeholder {
  margin: 0;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.panel--plan {
  background: linear-gradient(180deg, rgba(198, 168, 107, 0.09), rgba(255, 253, 247, 0.9));
}

.plan-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.chip {
  padding: 3px 10px;
  font-size: 12px;
  color: #6d5527;
  background: rgba(198, 168, 107, 0.16);
  border: 1px solid rgba(156, 124, 70, 0.38);
  border-radius: 12px;
}

.plan-note {
  margin: 12px 0 0;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--th-text-muted);
}
</style>
