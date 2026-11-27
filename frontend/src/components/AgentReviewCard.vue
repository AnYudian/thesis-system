<script setup lang="ts">
/**
 * 按环节的智能审阅卡片。
 *
 * 交互逻辑刻意做成"先预览、再提交"：对方串行处理，一次要 3-4 分钟，
 * 让老师看清楚会送哪几份、缺什么，比点完再等更省事。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { aiApi } from '@/api/ai'
import { STAGES } from '@/constants/stages'
import {
  AGENT_STATUS_LABEL,
  createAgentReview,
  getAgentReview,
  listAgentReviews,
  previewPackage,
  type AgentCheck,
  type AgentReview,
  type PackagePreview,
} from '@/api/agentReviews'

const props = defineProps<{
  studentId: number
  stage: string
  /** 只有学生当前所在环节才允许发起；历史/未来环节只读 */
  canInitiate?: boolean
}>()

const stageLabel = computed(() => STAGES.find((s) => s.code === props.stage)?.short ?? props.stage)

const preview = ref<PackagePreview | null>(null)
const review = ref<AgentReview | null>(null)
const loading = ref(false)
// 管理员在「参数配置」里关掉智能审阅时，按钮要禁用而不是让人白点
const aiEnabled = ref(true)
const submitting = ref(false)
const expanded = ref<number | null>(null)
let timer: number | undefined

const statusLabel = computed(() => (review.value ? AGENT_STATUS_LABEL[review.value.status] : ''))
const running = computed(() => review.value?.status === 'QUEUED' || review.value?.status === 'RUNNING')
const canSubmit = computed(
  () =>
    aiEnabled.value &&
    props.canInitiate !== false &&
    (preview.value?.total_files ?? 0) > 0 &&
    !running.value &&
    !submitting.value,
)
const result = computed(() => review.value?.result ?? null)
const checks = computed<AgentCheck[]>(() => (result.value?.checks as AgentCheck[]) ?? [])
const passedCount = computed(() => checks.value.filter((c) => statusType(c.status) === 'success').length)
const progressInfo = computed(() => (result.value?.project_progress as Record<string, unknown>) ?? null)
const findings = computed(
  () =>
    (result.value?.findings as {
      title?: string
      outcome?: string
      analysis?: string
      source_kind?: string
      evidence?: { quote?: string; name?: string; message_id?: string }[]
    }[]) ?? [],
)
const SOURCE_LABELS: Record<string, string> = {
  chat_analysis: '聊天分析',
  project_progress: '进度分析',
  document: '文档核查',
}
const searches = computed(
  () => ((result.value?.knowledge as { searches?: { query?: string; status?: string; note?: string }[] })?.searches ?? []),
)
const OUTCOME_LABELS: Record<string, string> = {
  no_new_evidence: '无新证据',
  unconfirmed: '待核验',
  improved: '有改善',
  still_present: '问题仍存在',
  new_progress: '新增进展',
}
// 对方返回但之前没展示的分析过程：材料识别、截图 OCR、聊天分析
const materialTypes = computed(
  () => (result.value?.material_types as Record<string, string>) ?? {},
)
const chatShots = computed(
  () =>
    (result.value?.chat_screenshots as {
      name?: string
      ocr_engine?: string
      width?: number
      height?: number
      messages?: {
        text?: string
        direction?: string
        confidence?: number
        categories?: string[]
        message_id?: string
        time_text?: string | null
        speaker_label?: string | null
      }[]
      unclassified_regions?: unknown[]
    }[]) ?? [],
)
const chatAnalysis = computed(() => (result.value?.chat_analysis as Record<string, unknown>) ?? null)
const showAllMsgs = ref(false)
// 卡片默认只留「材料 + 结论条 + 建议」，AI 的思考过程收起来，避免一屏全是细节
const showDetails = ref(false)

// 置信度只用一行区间表示，逐条贴百分比对老师没有意义
const confidenceRange = computed(() => {
  const vals = chatShots.value
    .flatMap((s) => s.messages ?? [])
    .map((m) => m.confidence)
    .filter((v): v is number => typeof v === 'number')
  if (!vals.length) return ''
  const min = Math.min(...vals)
  const max = Math.max(...vals)
  const f = (v: number) => `${Math.round(v * 100)}%`
  return min === max ? f(min) : `${f(min)}–${f(max)}`
})

// 跨材料核验：同一结论引用了两份以上材料，才是"跨材料"的证据
const crossFindings = computed(() =>
  findings.value.filter(
    (f) =>
      f.outcome !== 'no_new_evidence' &&
      new Set((f.evidence ?? []).map((e) => e.name)).size >= 2,
  ),
)

function speakerOf(m: { direction?: string; speaker_label?: string | null }) {
  if (m.speaker_label) return m.speaker_label
  // 对方没给发言人，按气泡在截图中的左右位置推断：右侧是老师，左侧是学生
  if (m.direction === 'right') return '指导老师（右侧）'
  if (m.direction === 'left') return '学生（左侧）'
  return '发言人未确认'
}

function confType(c?: number) {
  if (c === undefined || c === null) return 'info'
  if (c >= 0.95) return 'success'
  if (c >= 0.85) return 'warning'
  return 'danger'
}
const TYPE_LABELS: Record<string, string> = {
  document: '文档',
  chat_screenshot: '聊天截图',
  code_archive: '代码包',
  other: '其他',
}
const CHAT_STATUS_LABELS: Record<string, string> = {
  analyzed: '已完成分析',
  insufficient_evidence: '证据不足',
  skipped: '未分析',
}
const suggestions = computed<string[]>(() => {
  const list = result.value?.suggestions ?? []
  return list.map((s) => (typeof s === 'string' ? s : String((s as { text?: string }).text ?? '')))
})

function statusType(status?: string) {
  if (status === '需修改' || status === '不通过') return 'danger'
  if (status === '待确认' || status === '待核验') return 'warning'
  return 'success'
}

function formatSize(bytes: number) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`
}

function formatTime(value?: string | null) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

async function loadPreview() {
  try {
    preview.value = await previewPackage(props.studentId, props.stage)
  } catch {
    preview.value = null
  }
}

async function loadLatest() {
  try {
    const page = await listAgentReviews({ student_id: props.studentId, stage: props.stage, page: 1, size: 1 })
    const first = page.items[0]
    // 列表接口不返回整份 result，必须再取一次详情，否则历史记录只能看到状态看不到结论
    review.value = first ? await getAgentReview(first.id) : null
  } catch {
    review.value = null
  }
}

function startPolling() {
  stopPolling()
  timer = window.setInterval(async () => {
    if (!review.value) return
    const data = await getAgentReview(review.value.id)
    review.value = data
    if (!running.value) {
      stopPolling()
      if (data.status === 'DONE') ElMessage.success('智能审阅完成')
      if (data.status === 'FAILED') ElMessage.error(data.error ?? '智能审阅失败')
    }
  }, 5000)
}

function stopPolling() {
  if (timer) window.clearInterval(timer)
  timer = undefined
}

async function submit() {
  submitting.value = true
  try {
    const created = await createAgentReview(props.studentId, props.stage)
    review.value = created
    ElMessage.success('已提交，正在排队（对方串行处理，约 3-5 分钟）')
    startPolling()
  } catch {
    // http 拦截器已提示
  } finally {
    submitting.value = false
  }
}

async function loadSwitch() {
  try {
    aiEnabled.value = (await aiApi.status()).enabled
  } catch {
    aiEnabled.value = true
  }
}

onMounted(async () => {
  loading.value = true
  await loadSwitch()
  await Promise.all([loadPreview(), loadLatest()])
  loading.value = false
  if (running.value) startPolling()
})

watch(
  () => [props.studentId, props.stage],
  async () => {
    stopPolling()
    loading.value = true
    await Promise.all([loadPreview(), loadLatest()])
    loading.value = false
    if (running.value) startPolling()
  },
)

onBeforeUnmount(stopPolling)
</script>

<template>
  <section v-loading="loading" class="panel agent-panel">
    <header class="ai-head">
      <div class="ai-title">
        <div class="ai-title-row">
          <span class="ai-seal" :class="{ 'has-issues': (review?.check_failed ?? 0) > 0 }">AI</span>
          <h3>智能审阅</h3>
          <el-tag
            v-if="review"
            :type="review.status === 'FAILED' ? 'danger' : review.status === 'DONE' ? 'success' : 'info'"
            size="small"
          >
            {{ statusLabel }}
          </el-tag>
          <el-tag v-if="review?.simulation_only" type="warning" size="small" effect="plain">模拟结果</el-tag>
        </div>
        <p>
          按「本环节 + 前置材料」打包送智能审阅服务；结论仅供参考，<b>是否通过仍由老师决定</b>。
        </p>
      </div>
      <span v-if="review?.model" class="ai-model">{{ review.model }}</span>
    </header>

    <div class="pkg">
      <div class="pkg-head">
        <span>本次将送 <strong>{{ preview?.total_files ?? 0 }}</strong> 份材料</span>
        <el-button type="primary" size="small" :loading="submitting" :disabled="!canSubmit" @click="submit">
          {{
            running
              ? '审阅中…'
              : !aiEnabled
                ? '管理员已关闭'
                : props.canInitiate === false
                  ? '仅查看'
                  : '发起智能审阅'
          }}
        </el-button>
      </div>
      <ul v-if="preview?.files.length" class="pkg-list">
        <li v-for="f in preview.files" :key="f.material_id">
          <el-tag size="small" :type="f.included ? 'success' : 'info'" effect="plain">
            {{ f.included ? '送审' : '跳过' }}
          </el-tag>
          <span class="name">{{ f.file_name }}</span>
          <span class="meta">v{{ f.material_version }} · {{ formatSize(f.file_size) }} · {{ f.role }}</span>
          <span v-if="f.skip_reason" class="skip">{{ f.skip_reason }}</span>
        </li>
      </ul>
      <p v-else class="empty">本环节还没有可送审的材料。</p>
      <p v-for="w in preview?.warnings ?? []" :key="w" class="warn">· {{ w }}</p>
      <p v-if="props.canInitiate === false" class="warn">
        · 当前查看的是{{ stageLabel }}，不是学生所在环节，只能查看历史结论，不能发起审阅
      </p>
    </div>

    <div v-if="review?.error" class="err">
      <strong>{{ review.error_code || '失败' }}：</strong>{{ review.error }}
    </div>

    <div v-if="result" class="result">
      <p class="summary">{{ result.summary || review?.summary }}</p>
      <div class="counts">
        <span>核查 {{ review?.check_total }} 条</span>
        <span class="bad">需修改 {{ review?.check_failed }}</span>
        <span class="warn-text">待确认 {{ review?.check_pending }}</span>
        <span v-if="review?.model" class="meta">{{ review.model }}</span>
      </div>

      <div v-if="checks.length" class="bar">
        <span class="bar-pass" :style="{ flex: passedCount || 0.001 }" :title="`通过 ${passedCount}`" />
        <span class="bar-fail" :style="{ flex: review?.check_failed || 0.001 }" :title="`需修改 ${review?.check_failed}`" />
        <span class="bar-pending" :style="{ flex: review?.check_pending || 0.001 }" :title="`待确认 ${review?.check_pending}`" />
      </div>

      <div v-if="suggestions.length" class="suggests">
        <h4>建议</h4>
        <p v-for="(s, i) in suggestions" :key="i">· {{ s }}</p>
      </div>

      <el-button class="detail-toggle" link type="primary" @click="showDetails = !showDetails">
        {{
          showDetails
            ? '收起分析过程'
            : `展开分析过程（核查 ${checks.length} 条 · 跨材料 ${crossFindings.length} 项 · 与上次对比 ${findings.length} 条）`
        }}
      </el-button>

      <div v-if="showDetails" class="details">
        <h4 class="details-title">核查明细</h4>
        <ul class="checks">
        <li v-for="(c, i) in checks" :key="i">
          <div class="check-head" @click="expanded = expanded === i ? null : i">
            <el-tag size="small" :type="statusType(c.status)">{{ c.status }}</el-tag>
            <span class="title">{{ c.title }}</span>
            <span class="toggle">{{ expanded === i ? '收起' : '展开' }}</span>
          </div>
          <div v-if="expanded === i" class="check-body">
            <p>{{ c.analysis }}</p>
            <blockquote v-for="(e, j) in c.evidence ?? []" :key="j">
              {{ e.quote }}
            </blockquote>
          </div>
        </li>
      </ul>

      <div v-if="Object.keys(materialTypes).length || chatShots.length || chatAnalysis" class="block">
        <h4>分析过程</h4>
        <p v-if="Object.keys(materialTypes).length" class="trace">
          材料识别：
          <span v-for="(t, k) in materialTypes" :key="k" class="trace-item">
            {{ k }} → {{ TYPE_LABELS[t] ?? t }}
          </span>
        </p>
        <p v-for="(s, i) in chatShots" :key="i" class="trace">
          截图解析：{{ s.name }}
          <span class="meta">
            · {{ s.ocr_engine }} · {{ s.width }}×{{ s.height }}
            · 识别消息 {{ (s.messages ?? []).length }} 条
            <template v-if="confidenceRange"> · 置信度 {{ confidenceRange }}</template>
            <template v-if="(s.unclassified_regions ?? []).length">
              · 未归类文本块 {{ (s.unclassified_regions ?? []).length }}
            </template>
          </span>
        </p>
        <div v-for="(s, i) in chatShots" :key="'m' + i" class="msgs">
          <div
            v-for="(m, j) in (s.messages ?? []).slice(0, showAllMsgs ? 50 : 3)"
            :key="j"
            class="msg"
          >
            <span class="msg-id">{{ m.message_id ?? `M${j + 1}` }}</span>
            <span class="msg-speaker">{{ speakerOf(m) }}</span>
            <span class="msg-text">{{ m.text }}</span>
          </div>
          <el-button
            v-if="(s.messages ?? []).length > 3"
            link
            type="primary"
            size="small"
            @click="showAllMsgs = !showAllMsgs"
          >
            {{ showAllMsgs ? '收起消息' : `展开全部 ${(s.messages ?? []).length} 条` }}
          </el-button>
        </div>
        <p v-if="chatAnalysis" class="trace">
          聊天分析：
          <el-tag size="small" effect="plain" :type="chatAnalysis.status === 'analyzed' ? 'success' : 'info'">
            {{ CHAT_STATUS_LABELS[String(chatAnalysis.status)] ?? chatAnalysis.status }}
          </el-tag>
          <span v-if="chatAnalysis.note" class="meta">{{ chatAnalysis.note }}</span>
        </p>
      </div>

      <div v-if="progressInfo" class="block">
        <h4>总体进度</h4>
        <p>
          状态：{{ progressInfo.status === 'analyzed' ? '已分析' : progressInfo.status }}
          · 历史事项 {{ progressInfo.finding_count ?? 0 }} 项
          · 交付物核验：{{ progressInfo.artifact_verification === 'not_verified' ? '未核验' : progressInfo.artifact_verification }}
        </p>
      </div>

      <div v-if="crossFindings.length" class="block cross">
        <h4>跨材料核验 <span class="cross-count">{{ crossFindings.length }} 项</span></h4>
        <p class="cross-hint">同一结论能同时引用两份及以上材料，说明它做了交叉比对。</p>
        <div v-for="(f, i) in crossFindings" :key="'c' + i" class="cross-item">
          <div class="cross-title">
            <strong>{{ f.title }}</strong>
            <span class="cross-link">
              {{ [...new Set((f.evidence ?? []).map((e) => e.name))].join(' ↔ ') }}
            </span>
          </div>
          <p class="cross-analysis">{{ f.analysis }}</p>
          <div
            v-for="(e, j) in (f.evidence ?? []).slice(0, 4)"
            :key="'ce' + j"
            class="cross-ev"
          >
            <span class="cross-doc">{{ e.name }}<template v-if="e.message_id"> · {{ e.message_id }}</template></span>
            <span class="cross-quote">{{ e.quote }}</span>
          </div>
        </div>
      </div>

      <div v-if="findings.length" class="block">
        <h4>与上次对比</h4>
        <p v-for="(f, i) in findings" :key="i" class="finding">
          <el-tag size="small" effect="plain" :type="f.outcome === 'improved' ? 'success' : f.outcome === 'still_present' ? 'danger' : 'info'">
            {{ OUTCOME_LABELS[f.outcome ?? ''] ?? f.outcome }}
          </el-tag>
          <el-tag v-if="f.source_kind" size="small" type="info" effect="plain">
            {{ SOURCE_LABELS[f.source_kind] ?? f.source_kind }}
          </el-tag>
          <span>{{ f.title }}</span>
          <em v-if="f.analysis">{{ f.analysis }}</em>
          <em v-for="(e, j) in (f.evidence ?? []).slice(0, 2)" :key="'e' + j" class="cite">
            证据：{{ e.quote }}<template v-if="e.name">（{{ e.name }}<template v-if="e.message_id"> {{ e.message_id }}</template>）</template>
          </em>
        </p>
      </div>

      <div class="block">
        <h4>规范检索</h4>
        <p v-if="!searches.length" class="empty-hint">
          规范库尚未接入，本项暂无依据；接入后这里会显示命中的条款与原文。
        </p>
        <p v-for="(s, i) in searches" :key="i" class="search">
          <el-tag size="small" :type="s.status === 'matched' ? 'success' : 'info'" effect="plain">
            {{ s.status === 'matched' ? '命中' : '未命中' }}
          </el-tag>
          <span>检索：{{ s.query }}</span>
          <em v-if="s.note">{{ s.note }}</em>
        </p>
      </div>

      </div>

      <p class="time">
        提交 {{ formatTime(review?.submitted_at) }}
        <template v-if="review?.started_at"> · 开始 {{ formatTime(review.started_at) }}</template>
        <template v-if="review?.finished_at"> · 结束 {{ formatTime(review.finished_at) }}</template>
      </p>
    </div>
  </section>
</template>

<style scoped>
.agent-panel {
  /* 用 inset 阴影做左侧强调条：父级 .panel 的 border 简写会覆盖 border-left，
     阴影不会被覆盖，视觉更稳 */
  box-shadow: inset 3px 0 0 var(--th-accent), 0 6px 16px rgba(16, 31, 51, 0.05);
}
.ai-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--th-border-soft);
}
.ai-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ai-title-row h3 {
  margin: 0;
  font-size: 16px;
}
.ai-title p {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.7;
  color: var(--th-text-muted);
}
.ai-title p b {
  color: var(--th-text);
}
.ai-seal {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  font-family: var(--th-font-serif);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: #d9c08a;
  background: linear-gradient(145deg, #24405f, #16283f);
  border: 1px solid rgba(198, 168, 107, 0.55);
  border-radius: 7px;
  box-shadow: 0 2px 6px rgba(16, 31, 51, 0.18);
}
.ai-seal.has-issues::after {
  content: '';
  position: absolute;
  top: -3px;
  right: -3px;
  width: 8px;
  height: 8px;
  background: #a33c2a;
  border: 1.5px solid var(--th-surface);
  border-radius: 50%;
}
.ai-model {
  font-size: 12px;
  color: var(--th-text-muted);
  white-space: nowrap;
  padding-top: 6px;
}
.pkg {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px 14px;
}
.pkg-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.pkg-list {
  margin: 10px 0 0;
  padding: 0;
  list-style: none;
}
.pkg-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
  font-size: 13px;
}
.pkg-list li:last-child {
  border-bottom: none;
}
.pkg-list .name {
  font-weight: 600;
}
.pkg-list .meta,
.time {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.pkg-list .skip {
  color: var(--el-color-warning);
  font-size: 12px;
}
.empty {
  margin: 10px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.warn {
  margin: 6px 0 0;
  color: var(--el-color-warning);
  font-size: 12px;
}
.err {
  margin-top: 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
  font-size: 13px;
}
.result {
  margin-top: 14px;
}
.summary {
  margin: 0 0 8px;
  line-height: 1.7;
}
.counts {
  display: flex;
  gap: 14px;
  font-size: 13px;
  margin-bottom: 10px;
}
.counts .bad {
  color: var(--el-color-danger);
}
.counts .warn-text {
  color: var(--el-color-warning);
}
.checks {
  margin: 0;
  padding: 0;
  list-style: none;
}
.checks li {
  border-top: 1px solid var(--el-border-color-lighter);
  padding: 8px 0;
}
.check-head {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}
.check-head .title {
  flex: 1;
  font-size: 14px;
}
.check-head .toggle {
  color: var(--el-color-primary);
  font-size: 12px;
}
.check-body p {
  margin: 8px 0 6px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
}
.check-body blockquote {
  margin: 6px 0;
  padding: 8px 10px;
  border-left: 3px solid var(--el-border-color);
  background: var(--el-fill-color-lighter);
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.detail-toggle {
  margin: 8px 0 2px;
  font-size: 13px;
}
.details {
  margin-top: 6px;
  padding-top: 8px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.details-title {
  margin: 4px 0 6px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.bar {
  display: flex;
  height: 6px;
  margin: 10px 0 4px;
  border-radius: 3px;
  overflow: hidden;
  background: var(--el-fill-color-lighter);
}
.bar-pass {
  background: #3f7d5a;
}
.bar-fail {
  background: #a33c2a;
}
.bar-pending {
  background: #c6a86b;
}
.block {
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.trace {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: baseline;
}
.msgs {
  margin: 6px 0 8px;
  padding-left: 4px;
  border-left: 2px solid var(--el-border-color-lighter);
}
.msg {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px;
  padding: 4px 0;
  font-size: 13px;
}
.msg-id {
  font-family: monospace;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}
.msg-speaker {
  font-weight: 600;
  color: var(--el-text-color-regular);
}
.msg-text {
  flex-basis: 100%;
  padding-left: 4px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
}
.cross {
  border: 1px solid var(--th-accent-soft);
  border-radius: 6px;
  padding: 10px 12px;
  background: rgba(198, 168, 107, 0.08);
}
.cross-count {
  font-size: 12px;
  color: var(--th-accent);
}
.cross-hint {
  margin: 2px 0 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.cross-item {
  padding: 8px 0;
  border-top: 1px dashed var(--el-border-color-lighter);
}
.cross-item:first-of-type {
  border-top: none;
}
.cross-title {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
}
.cross-link {
  font-size: 12px;
  color: var(--th-accent);
}
.cross-analysis {
  margin: 4px 0 6px;
  font-size: 13px;
  line-height: 1.6;
}
.cross-ev {
  display: flex;
  gap: 8px;
  padding: 3px 0;
  font-size: 12px;
}
.cross-doc {
  flex: 0 0 auto;
  color: var(--el-color-primary);
}
.cross-quote {
  color: var(--el-text-color-regular);
}
.cite {
  font-style: normal;
  font-size: 12px;
  color: var(--el-color-primary);
}
.trace-item {
  padding: 1px 6px;
  border-radius: 3px;
  background: var(--el-fill-color-lighter);
  font-size: 12px;
}
.block h4 {
  margin: 0 0 6px;
  font-size: 13px;
}
.block p {
  margin: 4px 0;
  font-size: 13px;
  line-height: 1.6;
}
.finding,
.search {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: baseline;
}
.finding em,
.search em {
  flex-basis: 100%;
  font-style: normal;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.suggests h4 {
  margin: 12px 0 6px;
  font-size: 13px;
}
.suggests p {
  margin: 4px 0;
  font-size: 13px;
  line-height: 1.6;
}
</style>
