<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search } from '@element-plus/icons-vue'

import ReviewDecisionDialog from '@/components/ReviewDecisionDialog.vue'
import { remindersApi } from '@/api/reminders'
import { reviewsApi, type PendingItem, type ReviewAction, type ReviewTarget } from '@/api/reviews'
import { teachersApi } from '@/api/students'
import { STAGES } from '@/constants/stages'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/format'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const isAdmin = computed(() => auth.role === 'ADMIN')

const loading = ref(false)
const items = ref<PendingItem[]>([])

// 一张表既是教师的待批清单，也是管理员的在途学生总览：
// 管理员看进度和详情，教师在同一行上直接放行/退回，不再拆成两个 Tab。
const query = reactive({
  keyword: '',
  stage: '',
  teacherId: undefined as number | undefined,
})

const teachers = ref<{ id: number; real_name: string | null; username: string }[]>([])

// “待审核”= 当前环节交过材料，且材料比最近一次审核新（或从来没审过）。
// 退回后学生重新上传也算新提交，不会因为“处理过一次”就被埋掉。
function isNewSubmission(row: PendingItem) {
  if (!row.material_count || !row.latest_material_at) return false
  if (!row.last_reviewed_at) return true
  return new Date(row.latest_material_at).getTime() > new Date(row.last_reviewed_at).getTime()
}

const todoCount = computed(() => items.value.filter(isNewSubmission).length)
const onlyTodo = ref(false)

// 教师的工作顺序：先处理有新提交的，再按流程顺序往下排，
// 这样打开页面第一屏就是该动手的人，不用逐条点开猜。
const displayItems = computed(() => {
  const rows = onlyTodo.value ? items.value.filter(isNewSubmission) : items.value
  return [...rows].sort((a, b) => {
    const an = isNewSubmission(a) ? 0 : 1
    const bn = isNewSubmission(b) ? 0 : 1
    if (an !== bn) return an - bn
    const order = stageIndex(a.stage) - stageIndex(b.stage)
    return order !== 0 ? order : a.sno.localeCompare(b.sno)
  })
})

// 中期检查先看指导次数：不够配置的次数时把「通过」按钮直接禁掉，
// 后端也会再拦一次，这里只是让老师少点一次、提前知道差在哪
function canApprove(row: PendingItem) {
  return !row.guidance_required || row.guidance_count >= row.guidance_required
}

function openDetail(studentId: number) {
  // 教师和学生详情在同一个路由族里，但从阶段审核点进去要能原路返回
  router.push(
    isAdmin.value
      ? { path: `/admin/students/${studentId}`, query: { from: 'reviews' } }
      : { path: `/students/${studentId}`, query: { from: 'reviews' } },
  )
}

// 需要催交的两种情况：本环节一份都没交，或者被退回后还没重交。
// 已经交了待审的人不催，避免老师催到正在等着被看的人头上。
function needsMaterial(row: PendingItem) {
  if (!row.material_count) return true
  if (row.last_action !== 'RETURN') return false
  if (!row.latest_material_at) return true
  return new Date(row.latest_material_at).getTime() <= new Date(row.last_reviewed_at ?? 0).getTime()
}

const needRemindRows = computed(() => displayItems.value.filter(needsMaterial))

async function remindOne(row: PendingItem) {
  const stage = stageLabel(row.stage)
  let content = ''
  try {
    const res = await ElMessageBox.prompt(`给 ${row.name}（${row.sno}）发一条催交提醒`, `催交材料 · ${stage}`, {
      inputValue: `请在「${stage}」环节尽快提交材料，有疑问随时联系我。`,
      inputType: 'textarea',
      inputPlaceholder: '学生下次登录工作台或材料页时能看到这条提醒',
      confirmButtonText: '发送提醒',
      cancelButtonText: '取消',
      inputValidator: (value: string) => (value && value.trim() ? true : '提醒内容不能为空'),
    })
    content = res.value
  } catch {
    return // 取消
  }
  await remindersApi.remind(row.student_id, content)
  ElMessage.success(`已提醒 ${row.name}`)
  await load()
}

// 批量只按当前列表（含筛选）来，老师筛出某个环节后一键催的就是这一环
async function remindAll() {
  const rows = needRemindRows.value
  if (!rows.length) return
  try {
    await ElMessageBox.confirm(
      `给 ${rows.length} 名未交（或退回后未重交）材料的学生各发一条提醒？提醒内容按各自环节自动生成。`,
      '批量催交',
      { confirmButtonText: '全部发送', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }

  let done = 0
  for (const row of rows) {
    try {
      await remindersApi.remind(row.student_id)
      done += 1
    } catch {
      // 单个失败（比如刚被归档）不打断其余学生，最后统一报数量
    }
  }
  ElMessage.success(`已提醒 ${done} 名学生`)
  await load()
}

const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code
const stageIndex = (code: string) => STAGES.findIndex((s) => s.code === code) + 1

async function load() {
  loading.value = true
  try {
    items.value = await reviewsApi.pending({
      keyword: query.keyword.trim() || undefined,
      stage: query.stage || undefined,
      teacher_id: query.teacherId,
    })
  } finally {
    loading.value = false
  }
}

function search() {
  load()
}

function reset() {
  query.keyword = ''
  query.stage = ''
  query.teacherId = undefined
  onlyTodo.value = false
  load()
}

// 通过/退回弹窗与详情页共用组件，这里只负责把行的信息递过去
const decideVisible = ref(false)
const decideAction = ref<ReviewAction>('APPROVE')
const decideTarget = ref<ReviewTarget | null>(null)

function open(row: PendingItem, action: ReviewAction) {
  decideTarget.value = {
    student_id: row.student_id,
    name: row.name,
    sno: row.sno,
    stage: row.stage,
  }
  decideAction.value = action
  decideVisible.value = true
}

function rowClass({ row }: { row: PendingItem }) {
  return isNewSubmission(row) ? 'row-todo' : ''
}

// 教师工作台的环节卡片会带 ?stage= 过来，落地时直接筛好这一环；
// 页面已打开时再点卡片也要跟着变，所以用 watch 而不是只在 onMounted 读一次
function applyStageFromQuery() {
  const stage = route.query.stage
  query.stage = typeof stage === 'string' ? stage : ''
}

onMounted(async () => {
  applyStageFromQuery()
  await load()
  if (isAdmin.value) {
    teachers.value = await teachersApi.list().catch(() => [])
  }
})

watch(
  () => route.query.stage,
  () => {
    applyStageFromQuery()
    load()
  },
)
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <p class="eyebrow">STAGE REVIEW</p>
        <h2>{{ isAdmin ? '阶段流转' : '阶段审核' }}</h2>
        <p class="sub">
          {{ isAdmin
            ? '全校在途学生的当前进度、材料、指导与上次流转都在这一页；点姓名或「详情」可追溯完整历史。放行由指导教师本人决定，管理员只读。'
            : '先处理标了「待审核」的学生：打开详情核对材料、指导记录和审核历史，再决定通过或退回。退回必须写明要改的地方。' }}
        </p>
      </div>
      <span class="count">
        {{ isAdmin ? '在途' : '待处理' }}
        <b>{{ items.length }}</b> 人
        <template v-if="!isAdmin"> · 待审核 <b class="count-todo">{{ todoCount }}</b> 份</template>
      </span>
    </header>

    <section class="toolbar">
      <el-input
        v-model="query.keyword"
        class="tool-input"
        placeholder="学生姓名或学号"
        clearable
        :prefix-icon="Search"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select v-model="query.stage" class="tool-select" placeholder="全部环节" clearable @change="search">
        <el-option v-for="s in STAGES" :key="s.code" :label="s.label" :value="s.code" />
      </el-select>
      <el-select
        v-if="isAdmin"
        v-model="query.teacherId"
        class="tool-select"
        placeholder="全部指导教师"
        clearable
        @change="search"
      >
        <el-option v-for="t in teachers" :key="t.id" :label="t.real_name || t.username" :value="t.id" />
      </el-select>
      <el-checkbox v-if="!isAdmin" v-model="onlyTodo" class="tool-check">只看待审核</el-checkbox>
      <el-button :icon="Search" @click="search">查询</el-button>
      <el-button :icon="Refresh" plain @click="reset">重置</el-button>
      <el-button
        v-if="!isAdmin"
        type="warning"
        plain
        :disabled="!needRemindRows.length"
        @click="remindAll"
      >
        催交未交材料<template v-if="needRemindRows.length">（{{ needRemindRows.length }}）</template>
      </el-button>
    </section>

    <section class="table-wrap">
      <el-table
        v-loading="loading"
        :data="displayItems"
        stripe
        row-key="student_id"
        :row-class-name="rowClass"
      >
        <el-table-column label="学生" width="132">
          <template #default="{ row }">
            <el-button link type="primary" class="name-link" @click="openDetail(row.student_id)">
              {{ row.name }}
            </el-button>
            <span class="cell-sub student-sub">
              {{ row.sno }}
              <em v-if="isNewSubmission(row)" class="todo-tag">待审核</em>
              <em v-else-if="!row.material_count" class="muted-tag">未交材料</em>
              <em v-else-if="row.last_action === 'RETURN' && needsMaterial(row)" class="muted-tag">待重交</em>
            </span>
          </template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="指导教师" width="100">
          <template #default="{ row }">{{ row.teacher_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="当前进度" width="182">
          <template #default="{ row }">
            <div class="stage-line">
              <span class="stage-pill">{{ stageLabel(row.stage) }}</span>
              <span class="stage-step">{{ stageIndex(row.stage) }} / {{ STAGES.length }}</span>
            </div>
            <div v-if="row.stage_deadline" class="deadline-line" :class="{ 'is-overdue': row.stage_overdue }">
              截止 {{ row.stage_deadline }}<template v-if="row.stage_overdue"> · 已逾期</template>
            </div>
            <div class="track" :title="`已完成 ${stageIndex(row.stage) - 1} 个环节`">
              <span
                v-for="(s, i) in STAGES"
                :key="s.code"
                class="track-seg"
                :class="{ 'is-done': i < stageIndex(row.stage) - 1, 'is-current': i === stageIndex(row.stage) - 1 }"
              />
            </div>
          </template>
        </el-table-column>
        <el-table-column label="材料" width="136">
          <template #default="{ row }">
            <template v-if="row.material_count">
              <span class="cell-main">{{ row.material_count }} 份 · v{{ row.latest_version }}</span>
              <span class="cell-sub">{{ formatTime(row.latest_material_at) }}</span>
            </template>
            <span v-else class="cell-sub">暂无材料</span>
            <span v-if="row.last_reminded_at" class="remind-note">
              已催交 {{ formatTime(row.last_reminded_at) }}
            </span>
            <el-button
              v-if="!isAdmin && needsMaterial(row)"
              link
              type="warning"
              size="small"
              class="remind-btn"
              @click="remindOne(row)"
            >
              {{ row.last_reminded_at ? '再催一次' : '催交' }}
            </el-button>
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
        <el-table-column label="上次流转" min-width="190">
          <template #default="{ row }">
            <template v-if="row.last_action">
              <span class="opinion" :class="row.last_action === 'RETURN' ? 'is-return' : 'is-approve'">
                {{ row.last_action === 'RETURN' ? '退回' : '通过' }}
              </span>
              <span class="cell-sub">{{ formatTime(row.last_reviewed_at) }}</span>
              <span class="opinion-text" :title="row.last_comment || ''">
                {{ row.last_comment || '未填写意见' }}
              </span>
            </template>
            <span v-else class="cell-sub">本环节还没有审核记录</span>
          </template>
        </el-table-column>
        <el-table-column v-if="!isAdmin" label="操作" width="168" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.student_id)">详情</el-button>
            <el-tooltip
              :disabled="canApprove(row)"
              :content="`中期检查要求指导记录满 ${row.guidance_required || 10} 次，请先在「指导记录」补齐`"
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
        <el-table-column v-if="isAdmin" label="操作" width="86" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.student_id)">详情</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <p class="empty">{{ onlyTodo ? '当前没有待审核的提交。' : '没有符合条件的学生。' }}</p>
        </template>
      </el-table>

      <div class="legend">
        <el-button :icon="Refresh" plain size="small" @click="load">刷新</el-button>
        <span class="legend-text">
          共 {{ STAGES.length }} 个环节，最后一环通过后自动归档；审核历史与指导明细在「详情」里。
        </span>
      </div>
    </section>

    <ReviewDecisionDialog
      v-model="decideVisible"
      :action="decideAction"
      :target="decideTarget"
      @done="load"
    />
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

.count .count-todo {
  color: #8a5a1c;
}

.table-wrap {
  padding: 6px 14px 14px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.05);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
}

.tool-input {
  width: 220px;
}

.tool-select {
  width: 160px;
}

.tool-check {
  margin-right: 2px;
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

.student-sub {
  display: flex;
  align-items: center;
  gap: 6px;
}

.todo-tag,
.muted-tag {
  padding: 0 5px;
  font-size: 10px;
  font-style: normal;
  line-height: 16px;
  border-radius: 2px;
  white-space: nowrap;
}

.todo-tag {
  color: #8a5a1c;
  background: rgba(198, 168, 107, 0.18);
  border: 1px solid rgba(198, 168, 107, 0.5);
}

.muted-tag {
  color: #9b958a;
  background: rgba(29, 51, 84, 0.04);
  border: 1px solid var(--th-border-soft);
}

.cell-main.is-short {
  color: #a33a2a;
}

.name-link {
  height: auto;
  padding: 0;
  font-size: 13px;
  font-weight: 600;
}

.stage-line {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.stage-step {
  font-size: 11.5px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.stage-pill {
  display: inline-block;
  padding: 1px 6px;
  font-size: 11.5px;
  line-height: 18px;
  color: var(--th-primary);
  background: rgba(29, 51, 84, 0.06);
  border: 1px solid var(--th-border-soft);
  border-radius: 3px;
  white-space: nowrap;
}

.deadline-line {
  margin: 3px 0 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.deadline-line.is-overdue {
  color: #a33c2c;
}

.track {
  display: flex;
  gap: 3px;
  margin-top: 5px;
}

.track-seg {
  flex: 1;
  height: 4px;
  background: rgba(29, 51, 84, 0.1);
  border-radius: 2px;
}

.track-seg.is-done {
  background: rgba(47, 107, 79, 0.55);
}

.track-seg.is-current {
  background: var(--th-accent);
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
  color: #2f6b4f;
  background: rgba(47, 107, 79, 0.08);
  border: 1px solid rgba(47, 107, 79, 0.25);
}

.opinion-text {
  display: block;
  overflow: hidden;
  margin-top: 2px;
  font-size: 12px;
  color: var(--th-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 催交是辅助动作：字号小一号、金色，避免和「通过 / 退回」抢注意力 */
.remind-note {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: #a29a8b;
}

.remind-btn {
  padding: 0;
  margin-top: 2px;
  font-size: 12px;
  color: #8a6a25;
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

/* 有新提交的行轻轻铺一层暖色，横向扫视时能一眼挑出来 */
:deep(.el-table__body tr.row-todo > td.el-table__cell) {
  background: rgba(198, 168, 107, 0.08);
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
