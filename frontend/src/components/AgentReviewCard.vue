<script setup lang="ts">
/**
 * 按环节的智能审阅卡片。
 *
 * 交互逻辑刻意做成"先预览、再提交"：对方串行处理，一次要 3-4 分钟，
 * 让老师看清楚会送哪几份、缺什么，比点完再等更省事。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

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

const props = defineProps<{ studentId: number; stage: string }>()

const preview = ref<PackagePreview | null>(null)
const review = ref<AgentReview | null>(null)
const loading = ref(false)
const submitting = ref(false)
const expanded = ref<number | null>(null)
let timer: number | undefined

const statusLabel = computed(() => (review.value ? AGENT_STATUS_LABEL[review.value.status] : ''))
const running = computed(() => review.value?.status === 'QUEUED' || review.value?.status === 'RUNNING')
const canSubmit = computed(() => (preview.value?.total_files ?? 0) > 0 && !running.value && !submitting.value)
const result = computed(() => review.value?.result ?? null)
const checks = computed<AgentCheck[]>(() => (result.value?.checks as AgentCheck[]) ?? [])
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

onMounted(async () => {
  loading.value = true
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
    <header class="panel-head">
      <h3>
        智能审阅
        <el-tag v-if="review" :type="review.status === 'FAILED' ? 'danger' : review.status === 'DONE' ? 'success' : 'info'" size="small">
          {{ statusLabel }}
        </el-tag>
        <el-tag v-if="review?.simulation_only" type="warning" size="small" effect="plain">模拟结果</el-tag>
      </h3>
      <p>
        按「本环节 + 前置材料」打包送智能审阅服务；结论仅供参考，是否通过仍由老师决定。
      </p>
    </header>

    <div class="pkg">
      <div class="pkg-head">
        <span>本次将送 <strong>{{ preview?.total_files ?? 0 }}</strong> 份材料</span>
        <el-button type="primary" size="small" :loading="submitting" :disabled="!canSubmit" @click="submit">
          {{ running ? '审阅中…' : '发起智能审阅' }}
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

      <div v-if="suggestions.length" class="suggests">
        <h4>建议</h4>
        <p v-for="(s, i) in suggestions" :key="i">· {{ s }}</p>
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
.agent-panel :deep(.panel-head h3) {
  display: flex;
  align-items: center;
  gap: 8px;
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
