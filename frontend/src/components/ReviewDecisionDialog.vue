<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

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

watch(
  () => props.modelValue,
  (open) => {
    if (open) comment.value = ''
  },
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
    const result = await reviewsApi.decide(props.target.student_id, props.action, comment.value)
    ElMessage.success(
      result.status === 'ARCHIVED'
        ? '已通过，九个环节全部完成，学生进入归档'
        : `已通过，进入「${stageLabel(result.current_stage)}」`,
    )
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
    width="460px"
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
      <el-input
        v-model="comment"
        type="textarea"
        :rows="4"
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
</style>
