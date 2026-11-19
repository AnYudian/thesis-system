<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'

import {
  reviewsApi,
  type PendingItem,
  type ReviewAction,
  type StageReview,
} from '@/api/reviews'
import { teachersApi } from '@/api/students'
import { STAGES, STAGE_SHORT } from '@/constants/stages'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/format'

const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.role === 'ADMIN')

const loading = ref(false)
const items = ref<PendingItem[]>([])

// 中期检查先看指导次数：不够 10 次时把「通过」按钮直接禁掉，
// 后端也会再拦一次，这里只是让老师少点一次、提前知道差在哪
function canApprove(row: PendingItem) {
  return !row.guidance_required || row.guidance_count >= row.guidance_required
}

function openDetail(studentId: number) {
  router.push(`/admin/students/${studentId}`)
}

const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code
const stageIndex = (code: string) => STAGES.findIndex((s) => s.code === code) + 1

// ---- Tab ----
const tab = ref<'pending' | 'history'>('pending')

// ---- 流转记录 ----
// 待处理表只关心"现在停在哪"，历史表要回答"谁在什么时候放行/退回了谁"，
// 两者的筛选条件、分页都不同，所以拆成独立一套状态，首次切过去才请求。
const historyLoading = ref(false)
const historyItems = ref<StageReview[]>([])
const historyTotal = ref(0)
const historyLoaded = ref(false)
const historyQuery = reactive({
  page: 1,
  size: 10,
  keyword: '',
  stage: '',
  action: '' as '' | ReviewAction,
  teacherId: undefined as number | undefined,
})
const teachers = ref<{ id: number; real_name: string | null; username: string }[]>([])

async function loadHistory() {
  historyLoading.value = true
  try {
    const data = await reviewsApi.list({
      page: historyQuery.page,
      size: historyQuery.size,
      keyword: historyQuery.keyword || undefined,
      stage: historyQuery.stage || undefined,
      action: historyQuery.action || undefined,
      teacher_id: historyQuery.teacherId,
    })
    historyItems.value = data.items
    historyTotal.value = data.total
    historyLoaded.value = true
  } finally {
    historyLoading.value = false
  }
}

function searchHistory() {
  historyQuery.page = 1
  loadHistory()
}

function resetHistory() {
  historyQuery.keyword = ''
  historyQuery.stage = ''
  historyQuery.action = ''
  historyQuery.teacherId = undefined
  searchHistory()
}

function onTabChange(name: string | number) {
  if (name === 'history' && !historyLoaded.value) loadHistory()
}

// 通过：末尾环节的 to_stage 仍是本环节，光看代码会误以为没动，这里翻成人话
function toLabel(row: StageReview) {
  if (row.action === 'RETURN') return '留在本环节修改'
  return stageIndex(row.to_stage) === STAGES.length ? '归档' : stageLabel(row.to_stage)
}

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
    // 刚才的审核就是一条新历史，标记失效，下次切到历史 Tab 重新拉
    historyLoaded.value = false
  } catch {
    // 拦截器已经弹过具体原因（比如状态已变化），这里保持弹窗打开让老师重试
  } finally {
    dialog.submitting = false
  }
}

onMounted(async () => {
  await load()
  if (isAdmin.value) {
    teachers.value = await teachersApi.list().catch(() => [])
  }
})
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
      <span class="count">
        {{ tab === 'pending' ? (isAdmin ? '进行中' : '待处理') : '流转记录' }}
        <b>{{ tab === 'pending' ? items.length : historyTotal }}</b>
        {{ tab === 'pending' ? '人' : '条' }}
      </span>
    </header>

    <el-tabs v-model="tab" class="stage-tabs" @tab-change="onTabChange">
      <el-tab-pane label="待处理" name="pending">
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
        <el-table-column label="指导记录" width="118">
          <template #default="{ row }">
            <template v-if="row.guidance_required">
              <span class="cell-main" :class="{ 'is-short': row.guidance_count < row.guidance_required }">
                {{ row.guidance_count }} / {{ row.guidance_required }} 次
              </span>
              <span class="cell-sub">
                {{ row.guidance_count >= row.guidance_required ? '已达标' : '不足，无法通过' }}
              </span>
            </template>
            <span v-else class="cell-sub">—</span>
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
            <el-tooltip
              :disabled="canApprove(row)"
              content="中期检查要求指导记录满 10 次，请先在「指导记录」补齐"
              placement="top"
            >
              <span>
                <el-button link type="primary" :disabled="!canApprove(row)" @click="open(row, 'APPROVE')">
                  通过
                </el-button>
              </span>
            </el-tooltip>
            <el-button link type="danger" @click="open(row, 'RETURN')">退回</el-button>
          </template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="操作" width="82" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.student_id)">详情</el-button>
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
      </el-tab-pane>

      <el-tab-pane label="流转记录" name="history">
        <section class="toolbar">
          <el-input
            v-model="historyQuery.keyword"
            class="tool-input"
            placeholder="学生姓名或学号"
            clearable
            :prefix-icon="Search"
            @keyup.enter="searchHistory"
            @clear="searchHistory"
          />
          <el-select
            v-model="historyQuery.stage"
            class="tool-select"
            placeholder="全部环节"
            clearable
            @change="searchHistory"
          >
            <el-option v-for="s in STAGES" :key="s.code" :label="s.label" :value="s.code" />
          </el-select>
          <el-select
            v-model="historyQuery.action"
            class="tool-select"
            placeholder="全部动作"
            clearable
            @change="searchHistory"
          >
            <el-option label="通过" value="APPROVE" />
            <el-option label="退回" value="RETURN" />
          </el-select>
          <el-select
            v-if="isAdmin"
            v-model="historyQuery.teacherId"
            class="tool-select"
            placeholder="全部指导教师"
            clearable
            @change="searchHistory"
          >
            <el-option v-for="t in teachers" :key="t.id" :label="t.real_name || t.username" :value="t.id" />
          </el-select>
          <el-button :icon="Search" @click="searchHistory">查询</el-button>
          <el-button :icon="Refresh" plain @click="resetHistory">重置</el-button>
        </section>

        <section class="table-wrap">
          <el-table v-loading="historyLoading" :data="historyItems" stripe row-key="id">
            <el-table-column label="时间" width="156">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="学生" width="110">
              <template #default="{ row }">
                <span class="cell-main">{{ row.student_name }}</span>
                <span class="cell-sub">{{ row.sno }}</span>
              </template>
            </el-table-column>
            <el-table-column v-if="isAdmin" label="指导教师" width="100">
              <template #default="{ row }">{{ row.teacher_name || '—' }}</template>
            </el-table-column>
            <el-table-column label="环节" width="140">
              <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
            </el-table-column>
            <el-table-column label="动作" width="76">
              <template #default="{ row }">
                <span class="opinion" :class="row.action === 'RETURN' ? 'is-return' : 'is-approve'">
                  {{ row.action === 'RETURN' ? '退回' : '通过' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="去向" width="130">
              <template #default="{ row }">{{ toLabel(row) }}</template>
            </el-table-column>
            <el-table-column label="意见" min-width="200">
              <template #default="{ row }">
                <span v-if="row.comment" class="opinion-text" :title="row.comment">{{ row.comment }}</span>
                <span v-else class="cell-sub">未填写意见</span>
              </template>
            </el-table-column>
            <el-table-column label="审核人" width="92">
              <template #default="{ row }">{{ row.reviewer_name || '—' }}</template>
            </el-table-column>
            <el-table-column v-if="isAdmin" label="操作" width="76">
              <template #default="{ row }">
                <el-button link type="primary" @click="openDetail(row.student_id)">详情</el-button>
              </template>
            </el-table-column>
            <template #empty>
              <p class="empty">还没有审核记录。学生材料通过或退回后，这里会留下完整流水。</p>
            </template>
          </el-table>

          <div class="pager">
            <el-pagination
              v-model:current-page="historyQuery.page"
              v-model:page-size="historyQuery.size"
              :total="historyTotal"
              :page-sizes="[10, 20, 50]"
              layout="sizes, prev, pager, next"
              background
              @current-change="loadHistory"
              @size-change="searchHistory"
            />
          </div>
        </section>
      </el-tab-pane>
    </el-tabs>

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

.stage-tabs :deep(.el-tabs__header) {
  margin-bottom: 12px;
}

.stage-tabs :deep(.el-tabs__item) {
  font-size: 14px;
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding: 12px 14px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
}

.tool-input {
  width: 200px;
}

.tool-select {
  width: 150px;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
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

.cell-main.is-short {
  color: #a33a2a;
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
