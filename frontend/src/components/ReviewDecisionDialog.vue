<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { aiApi, type AiIssue, type AiRun } from '@/api/ai'
import { reviewsApi, type ReviewAction, type ReviewTarget } from '@/api/reviews'
import { STAGES } from '@/constants/stages'

// 阶段审核页和学生详情页都要通过/退回，共用同一个弹窗：
// 校验、提示文案、跳转后的刷新都只维护一份。

const props = defineProps<{
  modelValue: boolean
  action: ReviewAction
  target: ReviewTarget | null
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  done: []
}>()

const comment = ref('')
const submitting = ref(false)

// ---- AI 建议（只在退回时出现，且只取当前环节最新一次成功的预审）----
const aiLoading = ref(false)
const aiRun = ref<AiRun | null>(null)
const aiChecked = ref<number[]>([])
// 上一次自动生成的草稿：输入框还等于它时才敢覆盖，避免冲掉老师手写的内容
const lastDraft = ref('')

type IssueRow = AiIssue & { idx: number }

const majorIssues = computed<IssueRow[]>(() => {
  const issues = aiRun.value?.result?.issues ?? []
  return issues
    .map((issue, idx) => ({ ...issue, idx }))
    .filter((issue) => issue.level === 'MAJOR')
})

const allChecked = computed(
  () => majorIssues.value.length > 0 && aiChecked.value.length === majorIssues.value.length,
)

const DRAFT_LIMIT = 500
const HEADER = '请按以下意见修改后重新提交：'

function issueLine(issue: IssueRow, n: number) {
  const title = issue.title.length > 36 ? `${issue.title.slice(0, 36)}…` : issue.title
  const suggestion = (issue.suggestion || '').replace(/\s+/g, ' ').trim()
  const tip = suggestion
    ? `（改法：${suggestion.length > 32 ? `${suggestion.slice(0, 32)}…` : suggestion}）`
    : ''
  return `${n}. ${title}${tip}`
}

const draftText = computed(() => {
  const picked = majorIssues.value.filter((issue) => aiChecked.value.includes(issue.idx))
  if (!picked.length) return ''
  // 退回理由后端限 500 字，7 条必改的完整"改法"塞不下：
  // 每条只留标题 + 截短的改法，放不下的条数折成一句，完整细节学生看 AI 卡片
  const lines: string[] = []
  let used = HEADER.length
  for (const issue of picked) {
    const line = issueLine(issue, lines.length + 1)
    if (used + line.length + 1 > DRAFT_LIMIT - 28) break
    lines.push(line)
    used += line.length + 1
  }
  const rest = picked.length - lines.length
  if (rest > 0) lines.push(`另有 ${rest} 条必改，详见 AI 预审卡片`)
  return [HEADER, ...lines].join('\n')
})

function syncDraft(force = false) {
  const next = draftText.value
  if (force || !comment.value.trim() || comment.value === lastDraft.value) {
    comment.value = next
  }
  lastDraft.value = next
}

watch(aiChecked, () => syncDraft())

async function loadAi() {
  if (!props.target) return
  aiLoading.value = true
  try {
    const page = await aiApi.runs({
      student_id: props.target.student_id,
      stage: props.target.stage,
      size: 1,
    })
    const run = page.items[0]
    // 失败 / 排队中 / 关闭 AI 时都不显示这块，退回照常手写
    if (!run || run.status !== 'DONE' || !run.result) return
    aiRun.value = run
    aiChecked.value = majorIssues.value.map((issue) => issue.idx)
    syncDraft(true)
  } catch {
    // AI 拉不到不影响人工退回，静默降级为纯手写
  } finally {
    aiLoading.value = false
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    comment.value = ''
    aiRun.value = null
    aiChecked.value = []
    lastDraft.value = ''
    if (props.action === 'RETURN') loadAi()
  },
)

function toggleAll() {
  aiChecked.value = allChecked.value ? [] : majorIssues.value.map((issue) => issue.idx)
}

const dialogWidth = computed(() =>
  props.action === 'RETURN' && (aiRun.value || aiLoading.value) ? '560px' : '460px',
)

const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code
const stageIndex = (code: string) => STAGES.findIndex((s) => s.code === code) + 1

// 最后一环通过即归档，直接写“归档”比显示同一个环节名更清楚
const nextLabel = computed(() => {
  if (!props.target || props.action === 'RETURN') return ''
  return stageIndex(props.target.stage) === STAGES.length
    ? '归档'
    : STAGES[stageIndex(props.target.stage)].short
})

async function submit() {
  if (!props.target) return
  if (props.action === 'RETURN' && !comment.value.trim()) {
    ElMessage.warning('退回必须填写原因，学生要知道改什么')
    return
  }

  submitting.value = true
  try {
    const adopted =
      props.action === 'RETURN' && aiRun.value && aiChecked.value.length
        ? {
            runId: aiRun.value.id,
            adopted: majorIssues.value
              .filter((issue) => aiChecked.value.includes(issue.idx))
              .map((issue) => ({ level: issue.level, title: issue.title })),
          }
        : undefined
    const result = await reviewsApi.decide(
      props.target.student_id,
      props.action,
      comment.value,
      adopted,
    )
    // 退回和通过必须给不同的反馈：退回后学生还在原环节，
    // 之前一律写"已通过，进入下一环节"会让人以为点错了按钮
    if (props.action === 'RETURN') {
      ElMessage({
        type: 'warning',
        message: `已退回，${props.target.name} 仍停留在「${stageLabel(result.current_stage)}」，等学生修改后重新提交`,
      })
    } else {
      ElMessage.success(
        result.status === 'ARCHIVED'
          ? '已通过，九个环节全部完成，学生进入归档'
          : `已通过，进入「${stageLabel(result.current_stage)}」`,
      )
    }
    emit('update:modelValue', false)
    emit('done')
  } catch {
    // 拦截器已经弹过具体原因（比如状态已变化），保持弹窗打开让老师重试
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <el-dialog
    :model-value="modelValue"
    :title="action === 'APPROVE' ? '通过本环节' : '退回修改'"
    :width="dialogWidth"
    :close-on-click-modal="false"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template v-if="target">
      <p class="dlg-who">
        <b>{{ target.name }}</b>
        <span class="dlg-sno">{{ target.sno }}</span>
      </p>
      <p class="dlg-stage">
        {{ stageLabel(target.stage) }}
        <span v-if="action === 'APPROVE'" class="dlg-arrow">→ {{ nextLabel }}</span>
      </p>

      <!-- 退回时才出现：把 AI 的必改项带进理由，勾选=采纳，不勾=未采纳（只留痕） -->
      <section v-if="action === 'RETURN' && (aiLoading || aiRun)" class="ai-block">
        <header class="ai-head">
          <span class="ai-title">
            <b>AI 预审建议</b>
            <em v-if="aiRun">
              第 {{ aiRun.material_version }} 版 ·
              {{ aiRun.score === null ? '—' : `${Math.round(aiRun.score)} 分` }}
            </em>
          </span>
          <el-button v-if="majorIssues.length" link size="small" @click="toggleAll">
            {{ allChecked ? '全部不采纳' : '全部采纳' }}
          </el-button>
        </header>
        <p v-if="aiLoading" class="ai-loading">正在读取 AI 意见…</p>
        <el-checkbox-group v-else v-model="aiChecked" class="ai-list">
          <el-checkbox v-for="issue in majorIssues" :key="issue.idx" :value="issue.idx" class="ai-item">
            <span class="ai-item-title">{{ issue.title }}</span>
            <span v-if="issue.suggestion" class="ai-item-tip">改法：{{ issue.suggestion }}</span>
          </el-checkbox>
        </el-checkbox-group>
        <p v-if="!aiLoading && !majorIssues.length" class="ai-loading">
          这次预审没有必改项，可以只写人工意见。
        </p>
        <p v-else-if="!aiLoading" class="ai-foot">
          勾选的会写进退回理由；未勾选的记为「未采纳」，只做记录、不影响流程。
        </p>
      </section>

      <el-input
        v-model="comment"
        type="textarea"
        :rows="action === 'RETURN' && aiRun ? 6 : 4"
        maxlength="500"
        show-word-limit
        :placeholder="
          action === 'APPROVE'
            ? '可选：写一句给学生的确认意见（如“选题方向明确，可以进入任务书阶段”）'
            : '必填：写清楚哪里不通过、需要补什么，学生照着改'
        "
      />
    </template>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button
        :type="action === 'APPROVE' ? 'primary' : 'danger'"
        :loading="submitting"
        @click="submit"
      >
        {{ action === 'APPROVE' ? '确认通过' : '确认退回' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.dlg-who {
  margin: 0;
  font-size: 15px;
  color: var(--th-primary-deep);
}

.dlg-sno {
  margin-left: 8px;
  font-size: 12px;
  color: var(--th-text-muted);
}

.dlg-stage {
  margin: 6px 0 14px;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.dlg-arrow {
  color: var(--th-accent);
}

/* AI 建议区：和卡片里的"必改"同色系，但更紧凑，别把弹窗撑太大 */
.ai-block {
  margin-bottom: 12px;
  padding: 10px 12px;
  background: rgba(29, 51, 84, 0.03);
  border: 1px solid var(--th-border-soft);
  border-left: 3px solid var(--th-accent);
  border-radius: 4px;
}

.ai-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 6px;
  border-bottom: 1px dashed var(--th-border-soft);
}

.ai-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  font-size: 12.5px;
  color: var(--th-primary-deep);
}

.ai-title em {
  font-style: normal;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.ai-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 208px;
  padding: 8px 2px 4px;
  overflow-y: auto;
}

.ai-item {
  display: flex;
  align-items: flex-start;
  height: auto;
  margin: 0;
}

.ai-item :deep(.el-checkbox__label) {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-left: 8px;
  white-space: normal;
  line-height: 1.55;
}

.ai-item-title {
  font-size: 12.5px;
  color: var(--th-text);
}

.ai-item-tip {
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.ai-loading {
  margin: 8px 2px 2px;
  font-size: 12px;
  color: var(--th-text-muted);
}

.ai-foot {
  margin: 6px 2px 2px;
  font-size: 11px;
  color: var(--th-text-muted);
}
</style>
