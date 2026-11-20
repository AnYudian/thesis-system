<script setup lang="ts">
/**
 * AI 预审结果卡片（当前只覆盖开题报告）。
 *
 * 三个角色共用同一份组件，差异只在权限：
 * - 学生：只看自己，不能触发重跑；
 * - 教师：名下学生，可重跑；
 * - 管理员：同教师（后端再校验一次）。
 * 结论永远只作参考，卡片底部固定写明"由指导老师决定"。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { aiApi, type AiIssueLevel, type AiRun, type AiStatus } from '@/api/ai'
import { STAGES } from '@/constants/stages'
import { formatTime } from '@/utils/format'

const props = withDefaults(
  defineProps<{
    studentId?: number
    canRerun?: boolean
  }>(),
  { studentId: undefined, canRerun: false },
)

const enabled = ref(false)
const mock = ref(false)
const loading = ref(true)
const rerunning = ref(false)
const runs = ref<AiRun[]>([])
const stageLabel = STAGES.find((s) => s.code === 'PROPOSAL')?.label ?? '开题报告'

const latest = computed<AiRun | null>(() => runs.value[0] ?? null)
const history = computed(() => runs.value.slice(1))
const result = computed(() => latest.value?.result ?? null)
const majorIssues = computed(() => (result.value?.issues ?? []).filter((issue) => issue.level === 'MAJOR'))
const running = computed(
  () => latest.value?.status === 'QUEUED' || latest.value?.status === 'RUNNING',
)

const LEVELS: Record<AiIssueLevel, { label: string; tone: string }> = {
  MAJOR: { label: '必改', tone: 'major' },
  MINOR: { label: '建议', tone: 'minor' },
  INFO: { label: '提示', tone: 'info' },
}

// 同一条材料的多次重跑会并排出现，标清是谁触发的，老师才知道哪条是学生交完自动审的
function triggerLabel(row: AiRun) {
  if (row.trigger === 'UPLOAD') return '上传自动审'
  return row.triggered_by_name ? `${row.triggered_by_name}重跑` : '人工重跑'
}

function scoreTone(score: number | null | undefined) {
  if (score === null || score === undefined) return 'muted'
  if (score >= 80) return 'good'
  if (score >= 60) return 'warn'
  return 'bad'
}

function dimensionPercent(score: number, max: number) {
  if (!max) return '0%'
  return `${Math.min(100, Math.round((score / max) * 100))}%`
}

let timer: ReturnType<typeof setTimeout> | null = null
let attempts = 0

function stopPolling() {
  if (timer) clearTimeout(timer)
  timer = null
}

function schedulePoll() {
  stopPolling()
  if (!running.value || attempts >= 40) return
  attempts += 1
  timer = setTimeout(async () => {
    await loadRuns()
    schedulePoll()
  }, 3000)
}

async function loadRuns() {
  const data = await aiApi.runs({
    student_id: props.studentId,
    stage: 'PROPOSAL',
    size: 3,
  })
  runs.value = data.items
}

async function init() {
  loading.value = true
  try {
    const status: AiStatus = await aiApi.status()
    enabled.value = status.enabled
    mock.value = status.mock
    // 关闭后也要拉历史：开关只控制"是否自动审新提交"，不隐藏已有结论
    await loadRuns()
    schedulePoll()
  } finally {
    loading.value = false
  }
}

// 上传成功后由父组件调用：立刻查一次并把轮询次数清零，
// 否则学生刚交完材料，卡片还停在"没提交"的旧状态，看起来像没反应
async function refresh() {
  if (!enabled.value) return
  attempts = 0
  await loadRuns()
  schedulePoll()
}

defineExpose({ refresh })

async function rerun() {
  if (!latest.value) return
  rerunning.value = true
  try {
    await aiApi.rerun(latest.value.material_id)
    ElMessage.success('已重新提交预审，稍等几秒看结果')
    attempts = 0
    await loadRuns()
    schedulePoll()
  } finally {
    rerunning.value = false
  }
}

onMounted(init)
onBeforeUnmount(stopPolling)
</script>

<template>
  <section v-loading="loading" class="ai-panel" :class="{ 'ai-panel--off': !enabled }">
    <header class="ai-head">
      <div class="ai-title">
        <h3>{{ stageLabel }} · AI 预审</h3>
        <p v-if="enabled">
          模型按评分细则给出参考意见，不改变流程；<b>是否通过仍由指导老师决定</b>。
        </p>
        <p v-else>
          管理员在「参数配置」里关闭了 AI 预审，新材料不再自动送审；
          <b>已有记录与分数仍可查看</b>。
        </p>
      </div>
      <div class="ai-tools">
        <span v-if="!enabled" class="tag tag-off">已关闭</span>
        <span v-if="enabled && mock" class="tag tag-mock">演示模式</span>
        <span v-if="latest" class="ai-model">{{ latest.model }}</span>
        <el-button
          v-if="enabled && canRerun && latest && !running"
          :icon="Refresh"
          size="small"
          plain
          :loading="rerunning"
          @click="rerun"
        >
          重新预审
        </el-button>
      </div>
    </header>

    <p v-if="!enabled" class="ai-off-text">
      关闭期间材料照常提交、由指导老师人工审阅；重新开启后，新提交的开题报告会自动送审。
      以下是关闭前的记录，不会被删除。
    </p>

    <div v-if="!latest" class="ai-empty">
      <p v-if="!enabled">这段时间还没有 AI 预审记录。</p>
      <p v-else-if="canRerun">学生还没有提交开题报告的 PDF / DOCX，提交后会自动生成 AI 意见。</p>
      <p v-else>上传开题报告后，系统会自动生成 AI 修改建议，可先自行对照修改。</p>
    </div>

    <div v-else-if="running" class="ai-running">
      <span class="pulse" />
      <div>
        <p class="run-title">正在审阅第 {{ latest.material_version }} 版…</p>
        <p class="run-sub">通常需要 10-30 秒，结果出来后会自动刷新，不用手动刷新页面。</p>
      </div>
    </div>

    <div v-else-if="latest.status === 'FAILED' || latest.status === 'SKIPPED'" class="ai-blocked">
      <p class="blocked-title">{{ latest.status === 'FAILED' ? '这次预审没有完成' : '这次没有生成 AI 意见' }}</p>
      <p class="blocked-reason">{{ latest.error || '原因未知' }}</p>
      <p v-if="canRerun" class="blocked-hint">处理后可点右上角「重新预审」。</p>
      <p v-else class="blocked-hint">可联系指导老师处理，或换一份可复制文字的版本重新上传。</p>
    </div>

    <template v-else-if="result">
      <div v-if="majorIssues.length" class="ai-gate is-block">
        <p class="gate-title">AI 判定有 {{ majorIssues.length }} 条必改，已先退回学生修改</p>
        <p class="gate-sub">
          学生按下方清单改完后重新上传本环节材料，系统会自动再审；
          没有必改项后才进入指导老师审核。老师仍可人工优先处理。
        </p>
      </div>
      <div v-else-if="!running" class="ai-gate is-pass">
        <p class="gate-title">没有必改项，可以进入指导老师复核</p>
      </div>

      <div class="score-row">
        <div class="score-box" :class="scoreTone(result.score)">
          <span class="score-num">{{ Math.round(result.score) }}</span>
          <span class="score-unit">/ 100</span>
        </div>
        <div class="verdict">
          <p class="verdict-summary">{{ result.summary }}</p>
          <div class="completion">
            <span class="completion-label">完成度 {{ result.completion }}%</span>
            <div class="bar">
              <div class="bar-fill" :style="{ width: `${result.completion}%` }" />
            </div>
          </div>
          <p class="verdict-meta">
            第 {{ latest.material_version }} 版 · {{ formatTime(latest.finished_at || latest.created_at) }}
            · {{ triggerLabel(latest) }}
            <template v-if="latest.attempts > 1"> · 第 {{ latest.attempts }} 次尝试</template>
            <template v-if="latest.latency_ms"> · 用时 {{ Math.round(latest.latency_ms / 1000) }} 秒</template>
            <template v-if="latest.tokens_output"> · 输出 {{ latest.tokens_output }} tokens</template>
          </p>
        </div>
      </div>

      <div class="dims">
        <div v-for="dim in result.dimensions" :key="dim.key" class="dim">
          <div class="dim-top">
            <span class="dim-label">{{ dim.label }}</span>
            <span class="dim-score">{{ dim.score }} / {{ dim.max_score }}</span>
          </div>
          <div class="bar">
            <div class="bar-fill" :style="{ width: dimensionPercent(dim.score, dim.max_score) }" />
          </div>
          <p v-if="dim.comment" class="dim-comment">{{ dim.comment }}</p>
        </div>
      </div>

      <div v-if="result.issues.length" class="issues">
        <p class="section-label">需要修改的地方</p>
        <article v-for="(issue, index) in result.issues" :key="index" class="issue">
          <div class="issue-head">
            <span class="level" :class="LEVELS[issue.level].tone">{{ LEVELS[issue.level].label }}</span>
            <span class="issue-title">{{ issue.title }}</span>
          </div>
          <blockquote v-if="issue.quote" class="issue-quote">{{ issue.quote }}</blockquote>
          <p v-if="issue.suggestion" class="issue-suggestion">改法：{{ issue.suggestion }}</p>
        </article>
      </div>

      <div v-if="result.suggestions.length" class="suggestions">
        <p class="section-label">整体修改建议</p>
        <ol>
          <li v-for="(item, index) in result.suggestions" :key="index">{{ item }}</li>
        </ol>
      </div>
    </template>

    <div v-if="history.length" class="history">
      <p class="section-label">更早的预审记录</p>
      <div v-for="row in history" :key="row.id" class="history-row">
        <span class="history-ver">第 {{ row.material_version }} 版</span>
        <span class="history-status">{{ row.status_label }}</span>
        <span class="history-score">{{ row.score === null ? '—' : `${Math.round(row.score)} 分` }}</span>
        <span class="history-source">{{ triggerLabel(row) }}</span>
        <span class="history-time">{{ formatTime(row.created_at) }}</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ai-panel {
  padding: 18px 20px 16px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-left: 3px solid var(--th-accent);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.05);
}

/* 关闭态：保留一个安静的提示条，学生和老师都能知道"不是系统坏了" */
.ai-panel--off {
  border-left-color: var(--th-border);
  box-shadow: none;
}

.ai-panel--off .ai-title h3 {
  color: var(--th-text-muted);
}

.ai-off-text {
  margin: 12px 0 2px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--th-text-muted);
}

/* 必改门禁：红 = 先改稿，绿 = 可以交老师 */
.ai-gate {
  margin-top: 14px;
  padding: 10px 14px;
  border-radius: 3px;
  border-left: 3px solid transparent;
}

.ai-gate.is-block {
  background: rgba(163, 60, 42, 0.06);
  border-left-color: #a33c2a;
}

.ai-gate.is-pass {
  background: rgba(47, 107, 79, 0.07);
  border-left-color: #3f7d5a;
}

.gate-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
}

.is-block .gate-title {
  color: #8c3222;
}

.is-pass .gate-title {
  color: #2f6b4f;
}

.gate-sub {
  margin: 4px 0 0;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--th-text-muted);
}

.ai-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--th-border-soft);
}

.ai-title h3 {
  margin: 0;
  font-size: 15px;
  color: var(--th-primary-deep);
}

.ai-title p {
  margin: 3px 0 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.ai-title b {
  color: var(--th-accent);
  font-weight: 600;
}

.ai-tools {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.ai-model {
  font-size: 11px;
  color: #a29a8b;
}

.tag {
  padding: 1px 7px;
  font-size: 11px;
  border-radius: 2px;
}

.tag-mock {
  color: #8a6a2f;
  background: rgba(198, 168, 107, 0.16);
  border: 1px solid rgba(198, 168, 107, 0.5);
}

.tag-off {
  color: var(--th-text-muted);
  background: rgba(29, 51, 84, 0.05);
  border: 1px solid var(--th-border);
}

.ai-empty {
  padding: 18px 2px 6px;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.ai-running {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 18px 2px 8px;
}

.pulse {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--th-accent);
  box-shadow: 0 0 0 0 rgba(156, 124, 70, 0.5);
  animation: pulse 1.4s infinite;
}

@keyframes pulse {
  70% {
    box-shadow: 0 0 0 10px rgba(156, 124, 70, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(156, 124, 70, 0);
  }
}

.run-title {
  margin: 0;
  font-size: 13px;
}

.run-sub {
  margin: 3px 0 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.ai-blocked {
  margin-top: 14px;
  padding: 12px 14px;
  background: rgba(163, 60, 42, 0.05);
  border-left: 2px solid #a33c2a;
  border-radius: 2px;
}

.blocked-title {
  margin: 0;
  font-size: 13px;
  color: #8c3222;
}

.blocked-reason {
  margin: 4px 0 0;
  font-size: 12px;
  color: #6b6355;
}

.blocked-hint {
  margin: 6px 0 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.score-row {
  display: flex;
  gap: 20px;
  padding: 16px 0 14px;
  border-bottom: 1px dashed var(--th-border-soft);
}

.score-box {
  display: flex;
  align-items: baseline;
  gap: 4px;
  min-width: 108px;
  padding: 8px 14px;
  border-radius: 4px;
  background: rgba(29, 51, 84, 0.04);
}

.score-num {
  font-family: var(--th-font-serif);
  font-size: 34px;
  line-height: 1;
  color: var(--th-primary);
}

.score-box.good .score-num {
  color: #3f7d5a;
}

.score-box.warn .score-num {
  color: var(--th-accent);
}

.score-box.bad .score-num {
  color: #a33c2a;
}

.score-unit {
  font-size: 12px;
  color: var(--th-text-muted);
}

.verdict {
  flex: 1;
  min-width: 0;
}

.verdict-summary {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.75;
  color: var(--th-text);
}

.completion {
  display: flex;
  align-items: center;
  gap: 10px;
}

.completion-label {
  flex: none;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.bar {
  flex: 1;
  height: 6px;
  background: rgba(29, 51, 84, 0.08);
  border-radius: 3px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--th-primary), #3d6288);
}

.verdict-meta {
  margin: 8px 0 0;
  font-size: 11px;
  color: #a29a8b;
}

.dims {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 22px;
  padding: 14px 0 4px;
}

@media (max-width: 900px) {
  .dims {
    grid-template-columns: minmax(0, 1fr);
  }
}

.dim-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.dim-label {
  font-size: 12.5px;
}

.dim-score {
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.dim .bar {
  margin-top: 5px;
}

.dim-comment {
  margin: 5px 0 0;
  font-size: 11.5px;
  line-height: 1.65;
  color: var(--th-text-muted);
}

.section-label {
  margin: 16px 0 8px;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: var(--th-accent);
}

.issue {
  padding: 9px 0;
  border-top: 1px solid var(--th-border-soft);
}

.issue-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.level {
  flex: none;
  padding: 0 6px;
  font-size: 11px;
  line-height: 18px;
  border-radius: 2px;
}

.level.major {
  color: #8c3222;
  background: rgba(163, 60, 42, 0.1);
}

.level.minor {
  color: #8a6a2f;
  background: rgba(198, 168, 107, 0.18);
}

.level.info {
  color: var(--th-primary-soft);
  background: rgba(44, 74, 115, 0.1);
}

.issue-title {
  font-size: 13px;
}

.issue-quote {
  margin: 6px 0 0 28px;
  padding: 4px 10px;
  font-size: 11.5px;
  line-height: 1.65;
  color: #6b6355;
  background: rgba(29, 51, 84, 0.03);
  border-left: 2px solid var(--th-border);
}

.issue-suggestion {
  margin: 6px 0 0 28px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--th-text-muted);
}

.suggestions ol {
  margin: 0;
  padding-left: 20px;
}

.suggestions li {
  margin-bottom: 5px;
  font-size: 12.5px;
  line-height: 1.7;
}

.history {
  margin-top: 6px;
}

.history-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 6px 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
  border-top: 1px dashed var(--th-border-soft);
}

.history-ver {
  color: var(--th-text);
}

.history-score {
  font-family: var(--th-font-serif);
  color: var(--th-primary);
}

.history-time {
  margin-left: auto;
}

.history-source {
  padding: 0 6px;
  font-size: 11px;
  line-height: 18px;
  color: #a29a8b;
  background: rgba(29, 51, 84, 0.04);
  border-radius: 2px;
}
</style>
