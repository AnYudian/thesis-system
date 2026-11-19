<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { reviewsApi, type PendingItem, type ReviewAction } from '@/api/reviews'
import { STAGES, STAGE_SHORT } from '@/constants/stages'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/format'

const auth = useAuthStore()
const isAdmin = computed(() => auth.role === 'ADMIN')

const loading = ref(false)
const items = ref<PendingItem[]>([])

const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code
const stageIndex = (code: string) => STAGES.findIndex((s) => s.code === code) + 1

async function load() {
  loading.value = true
  try {
    items.value = await reviewsApi.pending()
  } finally {
    loading.value = false
  }
}

// 一个弹窗复用“通过 / 退回”两种情况：字段一样，只是意见是否必填不同
const dialog = reactive({
  visible: false,
  action: 'APPROVE' as ReviewAction,
  row: null as PendingItem | null,
  comment: '',
  submitting: false,
})

function open(row: PendingItem, action: ReviewAction) {
  dialog.row = row
  dialog.action = action
  dialog.comment = ''
  dialog.visible = true
}

async function submit() {
  if (!dialog.row) return
  if (dialog.action === 'RETURN' && !dialog.comment.trim()) {
    ElMessage.warning('退回必须填写原因，学生要知道改什么')
    return
  }

  dialog.submitting = true
  try {
    const result = await reviewsApi.decide(dialog.row.student_id, dialog.action, dialog.comment)
    ElMessage.success(
      result.status === 'ARCHIVED'
        ? '已通过，九个环节全部完成，学生进入归档'
        : `已通过，进入「${stageLabel(result.current_stage)}」`,
    )
    dialog.visible = false
    await load()
  } catch {
    // 拦截器已经弹过具体原因（比如状态已变化），这里保持弹窗打开让老师重试
  } finally {
    dialog.submitting = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <p class="eyebrow">STAGE REVIEW</p>
        <h2>{{ isAdmin ? '阶段流转' : '阶段审核' }}</h2>
        <p class="sub">
          {{ isAdmin
            ? '全校学生当前停留在哪一环、交了几版材料。放行由指导教师本人决定，管理员只读。'
            : '学生完成当前环节后由你放行或退回。通过进入下一环节，退回必须写明要改的地方。' }}
        </p>
      </div>
      <span class="count">{{ isAdmin ? '进行中' : '待处理' }} <b>{{ items.length }}</b> 人</span>
    </header>

    <section class="table-wrap">
      <el-table v-loading="loading" :data="items" stripe row-key="student_id">
        <el-table-column label="学生" width="108">
          <template #default="{ row }">
            <span class="cell-main">{{ row.name }}</span>
            <span class="cell-sub">{{ row.sno }}</span>
          </template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="指导教师" width="96">
          <template #default="{ row }">{{ row.teacher_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="当前环节" width="150">
          <template #default="{ row }">
            <span class="stage-pill">{{ stageLabel(row.stage) }}</span>
            <span class="cell-sub">第 {{ stageIndex(row.stage) }} / {{ STAGES.length }} 步</span>
          </template>
        </el-table-column>
        <el-table-column label="材料" width="112">
          <template #default="{ row }">
            <template v-if="row.material_count">
              <span class="cell-main">{{ row.material_count }} 份 · v{{ row.latest_version }}</span>
              <span class="cell-sub">{{ formatTime(row.latest_material_at) }}</span>
            </template>
            <span v-else class="cell-sub">暂无材料</span>
          </template>
        </el-table-column>
        <el-table-column label="上次意见" min-width="180">
          <template #default="{ row }">
            <template v-if="row.last_action">
              <span class="opinion" :class="row.last_action === 'RETURN' ? 'is-return' : 'is-approve'">
                {{ row.last_action === 'RETURN' ? '退回' : '通过' }}
              </span>
              <span class="opinion-text" :title="row.last_comment || ''">
                {{ row.last_comment || '未填写意见' }}
              </span>
            </template>
            <span v-else class="cell-sub">本环节还没有审核记录</span>
          </template>
        </el-table-column>
        <el-table-column v-if="!isAdmin" label="操作" width="128" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="open(row, 'APPROVE')">通过</el-button>
            <el-button link type="danger" @click="open(row, 'RETURN')">退回</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <p class="empty">当前没有待处理的学生。</p>
        </template>
      </el-table>

      <div class="legend">
        <el-button :icon="Refresh" plain size="small" @click="load">刷新</el-button>
        <span class="legend-text">共 {{ STAGES.length }} 个环节，最后一环通过后自动归档。</span>
      </div>
    </section>

    <el-dialog
      v-model="dialog.visible"
      :title="dialog.action === 'APPROVE' ? '通过本环节' : '退回修改'"
      width="460px"
      :close-on-click-modal="false"
    >
      <template v-if="dialog.row">
        <p class="dlg-who">
          <b>{{ dialog.row.name }}</b>
          <span class="dlg-sno">{{ dialog.row.sno }}</span>
        </p>
        <p class="dlg-stage">
          {{ stageLabel(dialog.row.stage) }}
          <span v-if="dialog.action === 'APPROVE'" class="dlg-arrow">
            → {{ stageIndex(dialog.row.stage) === STAGES.length ? '归档' : STAGE_SHORT[STAGES[stageIndex(dialog.row.stage)].code] }}
          </span>
        </p>
        <el-input
          v-model="dialog.comment"
          type="textarea"
          :rows="4"
          maxlength="500"
          show-word-limit
          :placeholder="
            dialog.action === 'APPROVE'
              ? '可选：写一句给学生的确认意见（如“选题方向明确，可以进入任务书阶段”）'
              : '必填：写清楚哪里不通过、需要补什么，学生照着改'
          "
        />
      </template>
      <template #footer>
        <el-button @click="dialog.visible = false">取消</el-button>
        <el-button
          :type="dialog.action === 'APPROVE' ? 'primary' : 'danger'"
          :loading="dialog.submitting"
          @click="submit"
        >
          {{ dialog.action === 'APPROVE' ? '确认通过' : '确认退回' }}
        </el-button>
      </template>
    </el-dialog>
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

.opinion {
  display: inline-block;
  margin-right: 6px;
  padding: 1px 6px;
  font-size: 11.5px;
  border-radius: 3px;
  white-space: nowrap;
}

.opinion.is-return {
  color: #a33a2a;
  background: rgba(163, 58, 42, 0.08);
  border: 1px solid rgba(163, 58, 42, 0.25);
}

.opinion.is-approve {
  color: var(--th-primary);
  background: rgba(29, 51, 84, 0.06);
  border: 1px solid var(--th-border-soft);
}

.opinion-text {
  font-size: 12px;
  color: var(--th-text-muted);
}

.empty {
  margin: 0;
  padding: 18px 0;
  font-size: 13px;
  color: var(--th-text-muted);
}

.legend {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 12px;
}

.legend-text {
  font-size: 12px;
  color: var(--th-text-muted);
}

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
