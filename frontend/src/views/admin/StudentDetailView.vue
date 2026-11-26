<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Download } from '@element-plus/icons-vue'

import ReviewDecisionDialog from '@/components/ReviewDecisionDialog.vue'
import AiReviewPanel from '@/components/AiReviewPanel.vue'
import AgentReviewCard from '@/components/AgentReviewCard.vue'
import { METHOD_LABELS, guidanceApi, type GuidanceRecord, type GuidanceSummary } from '@/api/guidance'
import { materialsApi, type Material } from '@/api/materials'
import { reviewsApi, type ReviewAction, type ReviewTarget, type StageReview } from '@/api/reviews'
import { studentsApi, type StudentDetail } from '@/api/students'
import { STAGES } from '@/constants/stages'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/format'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const studentId = Number(route.params.id)
const isTeacher = computed(() => auth.role === 'TEACHER')

// 同一个详情页有三种来路：教师从阶段审核进、管理员从阶段流转或学生列表进。
// 返回地址和文案必须跟来路一致，否则老师会莫名其妙回到别处。
const fromReviews = computed(() => route.query.from === 'reviews')
const backLabel = computed(() =>
  isTeacher.value ? '返回阶段审核' : fromReviews.value ? '返回阶段流转' : '返回学生与课题',
)

// 列表的筛选条件（环节 / 关键词 / 只看待审核 / 指导教师）跟着地址栏带过来，
// 返回时原样带回去，老师看完一个学生不用重新筛
function listQuery() {
  const q: Record<string, string> = {}
  for (const key of ['keyword', 'stage', 'teacher_id', 'todo']) {
    const value = route.query[key]
    if (typeof value === 'string' && value) q[key] = value
  }
  return q
}

function goBack() {
  if (isTeacher.value) {
    router.push({ path: '/reviews', query: listQuery() })
    return
  }
  if (fromReviews.value) {
    router.push({ path: '/admin/reviews', query: listQuery() })
    return
  }
  router.push('/admin/students')
}

const loading = ref(true)
const detail = ref<StudentDetail | null>(null)
const reviews = ref<StageReview[]>([])
const materials = ref<Material[]>([])
const guidance = ref<GuidanceRecord[]>([])
const summary = ref<GuidanceSummary | null>(null)

// 图片证据直接取 blob 做缩略图：管理员核对时不用每次点开新窗口再关掉。
// 地址是临时的，离开页面要统一回收，否则切几次学生就堆一堆内存。
const evidenceUrls = reactive<Record<number, string>>({})
const evidenceLoaded = ref(false)
const isImageEvidence = (type: string | null) => !!type && type.startsWith('image/')

async function loadEvidencePreviews(records: GuidanceRecord[]) {
  await Promise.all(
    records
      .filter((r) => r.evidence_name && isImageEvidence(r.evidence_type))
      .map(async (r) => {
        try {
          evidenceUrls[r.id] = await guidanceApi.evidenceUrl(r)
        } catch {
          // 单张取不到就退回「查看证据」按钮，不影响其它记录
        }
      }),
  )
  evidenceLoaded.value = true
}

onBeforeUnmount(() => {
  Object.values(evidenceUrls).forEach((url) => URL.revokeObjectURL(url))
})

const currentIndex = computed(() =>
  detail.value ? STAGES.findIndex((s) => s.code === detail.value?.current_stage) : -1,
)

const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code
const stageShort = (code: string) => STAGES.find((s) => s.code === code)?.short ?? code
const stageIndex = (code: string) => STAGES.findIndex((s) => s.code === code) + 1

const midtermProgress = computed(() => {
  if (!summary.value) return null
  const done = summary.value.midterm_count
  const required = summary.value.midterm_required
  return {
    done,
    required,
    percent: Math.min(100, Math.round((done / required) * 100)),
    reached: done >= required,
  }
})

// 中期检查的次数要求（管理员可配，默认 10 次）只在学生进入这一环节后才有意义：
// 前三个环节就摆一条"还差 N 次"，老师会误以为学生被卡住了
const midtermIndex = STAGES.findIndex((s) => s.code === 'MIDTERM')
const midtermPhase = computed<'BEFORE' | 'AT' | 'AFTER'>(() => {
  const d = detail.value
  if (!d) return 'BEFORE'
  if (d.status === 'ARCHIVED') return 'AFTER'
  if (currentIndex.value < 0) return 'BEFORE'
  if (currentIndex.value === midtermIndex) return 'AT'
  return currentIndex.value < midtermIndex ? 'BEFORE' : 'AFTER'
})

// 详情页拉的是该生全部材料，老师真正要处理的是"当前环节"这一批，
// 所以单独挑出来并排到表格最上面
const currentStageMaterials = computed(() => {
  const stage = detail.value?.current_stage
  return stage ? materials.value.filter((m) => m.stage === stage) : []
})

// 同一份材料可能交了 v1、v2，判断"要不要看"只认最新版
const currentStageLatest = computed(() => {
  const latest = new Map<string, Material>()
  for (const m of currentStageMaterials.value) {
    const old = latest.get(m.title)
    if (!old || m.version > old.version) latest.set(m.title, m)
  }
  return [...latest.values()]
})

// 本环节最近一次审核时间：这之后上传的才是"学生新交的、老师还没看过"
const currentStageReviewAt = computed<Date | null>(() => {
  const stage = detail.value?.current_stage
  if (!stage) return null
  const times = reviews.value
    .filter((r) => r.from_stage === stage)
    .map((r) => new Date(r.created_at).getTime())
  return times.length ? new Date(Math.max(...times)) : null
})

const isNewMaterial = (m: Material) => {
  if (!detail.value || m.stage !== detail.value.current_stage) return false
  return !currentStageReviewAt.value || new Date(m.created_at) > currentStageReviewAt.value
}

const newMaterials = computed(() => currentStageLatest.value.filter(isNewMaterial))
const newMaterialTitles = computed(() => newMaterials.value.map((m) => m.title).join('、'))
const newMaterialAt = computed(() => {
  if (!newMaterials.value.length) return ''
  const ts = Math.max(...newMaterials.value.map((m) => new Date(m.created_at).getTime()))
  return new Date(ts).toISOString()
})
const lastReviewedText = computed(() =>
  currentStageReviewAt.value ? formatTime(currentStageReviewAt.value.toISOString()) : '',
)

// 本环节材料置顶，其余按上传时间倒序，找历史版本时也不用来回翻
const sortedMaterials = computed(() => {
  const stage = detail.value?.current_stage
  return [...materials.value].sort((a, b) => {
    const aCurrent = a.stage === stage ? 0 : 1
    const bCurrent = b.stage === stage ? 0 : 1
    if (aCurrent !== bCurrent) return aCurrent - bCurrent
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
})

const materialRowClass = ({ row }: { row: Material }) => (isNewMaterial(row) ? 'row-new' : '')

// 管理员看的是"过程有没有真的发生"：面谈几次、线上几次、留了几张证据，
// 这些比一句"已完成指导"更能说明问题，所以放在明细表上方先给个汇总。
const guidanceStats = computed(() => {
  const meet = guidance.value.filter((g) => g.method === 'MEET').length
  const online = guidance.value.filter((g) => g.method === 'ONLINE').length
  const evidence = guidance.value.filter((g) => g.evidence_name).length
  return { total: guidance.value.length, meet, online, evidence }
})

function toLabel(row: StageReview) {
  if (row.action === 'RETURN') return '留在本环节'
  return stageIndex(row.to_stage) === STAGES.length ? '归档' : stageLabel(row.to_stage)
}

/** 退回时采纳的 AI 建议，悬停看清单；列表一行放不下，不展开占位 */
function aiAdoptedText(row: StageReview) {
  return (row.ai_adopted || []).map((issue, n) => `${n + 1}. ${issue.title}`).join('\n')
}

function fileSize(bytes: number | null) {
  if (!bytes) return '—'
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

// 教师在这个页面直接放行/退回，处理完要重新拉一遍：
// 环节、审核历史、指导次数都会变，不能只改本地状态
const decideVisible = ref(false)
const decideAction = ref<ReviewAction>('APPROVE')
const decideTarget = ref<ReviewTarget | null>(null)

// 中期检查没满要求次数时不允许通过；退回不拦，材料不合格时老师要能直接退
const approveBlocked = computed(() => {
  const d = detail.value
  if (!d || d.current_stage !== 'MIDTERM') return false
  return !!summary.value && summary.value.midterm_count < summary.value.midterm_required
})

function openDecide(action: ReviewAction) {
  const d = detail.value
  if (!d) return
  decideTarget.value = { student_id: d.id, name: d.name, sno: d.sno, stage: d.current_stage }
  decideAction.value = action
  decideVisible.value = true
}

function clearEvidenceUrls() {
  Object.values(evidenceUrls).forEach((url) => URL.revokeObjectURL(url))
  Object.keys(evidenceUrls).forEach((key) => delete evidenceUrls[Number(key)])
  evidenceLoaded.value = false
}

async function loadAll() {
  loading.value = true
  try {
    clearEvidenceUrls()
    detail.value = await studentsApi.detail(studentId)
    const [reviewPage, materialPage, guidancePage, guidanceSummary] = await Promise.all([
      reviewsApi.list({ student_id: studentId, size: 100 }),
      materialsApi.list({ student_id: studentId, size: 100 }),
      guidanceApi.list({ student_id: studentId, size: 100 }),
      guidanceApi.summary(studentId),
    ])
    reviews.value = reviewPage.items
    materials.value = materialPage.items
    guidance.value = guidancePage.items
    summary.value = guidanceSummary
    await loadEvidencePreviews(guidance.value)
  } finally {
    loading.value = false
  }
}

onMounted(loadAll)
</script>

<template>
  <div v-loading="loading" class="page">
    <div class="crumb">
      <el-button link :icon="ArrowLeft" @click="goBack">{{ backLabel }}</el-button>
      <span class="crumb-sep">/</span>
      <span>学生详情</span>
    </div>

    <template v-if="detail">
      <section class="profile">
        <div class="who">
          <span class="avatar">{{ detail.name.slice(0, 1) }}</span>
          <div>
            <p class="eyebrow">STUDENT DETAIL · 2026 届</p>
            <h2>{{ detail.name }}</h2>
            <p class="meta">
              {{ detail.sno }} · {{ detail.major }} · {{ detail.class_name }} · {{ detail.grade }} 级
            </p>
          </div>
        </div>
        <div class="side">
          <div class="side-item">
            <span class="side-label">当前环节</span>
            <strong>{{ stageLabel(detail.current_stage) }}</strong>
          </div>
          <div class="side-item">
            <span class="side-label">状态</span>
            <strong>{{ detail.status === 'ARCHIVED' ? '已归档' : '进行中' }}</strong>
          </div>
          <div class="side-item">
            <span class="side-label">课题</span>
            <strong class="side-topic" :title="detail.topic?.title || ''">
              {{ detail.topic?.title || '未选题' }}
            </strong>
          </div>
        </div>
      </section>

      <!-- 教师看自己的学生不需要再看到自己的联系方式；管理员核对指导记录时才需要 -->
      <section v-if="!isTeacher" class="panel teacher-panel">
        <header class="panel-head">
          <h3>指导教师</h3>
          <p>管理员核对指导记录时，需要能直接联系到导师</p>
        </header>
        <div v-if="detail.teacher" class="teacher-grid">
          <div>
            <span class="side-label">姓名 / 账号</span>
            <strong>{{ detail.teacher.real_name || '—' }} · {{ detail.teacher.username }}</strong>
          </div>
          <div>
            <span class="side-label">学院 / 专业</span>
            <strong>{{ detail.teacher.college || '未填' }} · {{ detail.teacher.major || '未填' }}</strong>
          </div>
          <div>
            <span class="side-label">手机号</span>
            <strong>{{ detail.teacher.phone || '未填' }}</strong>
          </div>
          <div>
            <span class="side-label">邮箱</span>
            <strong>{{ detail.teacher.email || '未填' }}</strong>
          </div>
        </div>
        <p v-else class="empty">该生还没有指派指导教师。</p>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>九环节进度</h3>
          <p>按流程顺序排列，当前环节高亮；已通过的打勾</p>
        </header>
        <ol class="steps">
          <li
            v-for="(s, i) in STAGES"
            :key="s.code"
            class="step"
            :class="{ 'is-done': i < currentIndex, 'is-current': i === currentIndex }"
          >
            <span class="step-no">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="step-name" :title="s.label">{{ s.short }}</span>
          </li>
        </ol>
      </section>

      <AiReviewPanel :student-id="studentId" :can-rerun="isTeacher || auth.role === 'ADMIN'" />

      <AgentReviewCard :student-id="studentId" :stage="detail.current_stage" />

      <section v-if="isTeacher && detail.status !== 'ARCHIVED'" class="panel action-panel">
        <header class="panel-head">
          <h3>本环节审核</h3>
          <p>
            当前：{{ stageLabel(detail.current_stage) }} · 本环节材料 {{ currentStageLatest.length }} 份 ·
            指导 {{ guidanceStats.total }} 次；看完下方材料与历史后再决定
          </p>
        </header>
        <div class="action-row">
          <div class="action-notes">
            <p v-if="approveBlocked" class="action-warn">
              中期检查要求指导记录满 {{ summary?.midterm_required ?? 10 }} 次，当前只有
              {{ summary?.midterm_count ?? 0 }} 次，先补齐再通过；也可以直接退回让学生完善。
            </p>
            <p v-if="newMaterials.length" class="action-new">
              学生在 {{ formatTime(newMaterialAt) }} 新提交了 {{ newMaterials.length }} 份材料（{{
                newMaterialTitles
              }}），表格里已标黄置顶，建议先下载核对再决定。
            </p>
            <p v-if="!approveBlocked && !newMaterials.length" class="action-hint">
              通过后学生进入下一环节；退回必须写明要改的地方。
            </p>
          </div>
          <div class="action-btns">
            <el-tooltip
              :disabled="!approveBlocked"
              :content="`中期检查要求指导记录满 ${summary?.midterm_required ?? 10} 次，请先在「指导记录」补齐`"
              placement="top"
            >
              <span>
                <el-button type="primary" :disabled="approveBlocked" @click="openDecide('APPROVE')">
                  通过本环节
                </el-button>
              </span>
            </el-tooltip>
            <el-button type="danger" plain @click="openDecide('RETURN')">退回修改</el-button>
          </div>
        </div>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>指导记录</h3>
          <p>
            <template v-if="midtermPhase === 'BEFORE'">
              学生还没进入中期检查；
            </template>
            <template v-else-if="midtermPhase === 'AT'">
              中期检查要求教师指导满 <b>{{ summary?.midterm_required ?? 10 }}</b> 次；
            </template>
            <template v-else>中期检查已通过；</template>
            共 {{ guidanceStats.total }} 条明细，
            面谈 {{ guidanceStats.meet }} 次、线上 {{ guidanceStats.online }} 次、附证据 {{ guidanceStats.evidence }} 条
          </p>
        </header>

        <div v-if="midtermPhase === 'BEFORE'" class="midterm-idle">
          <span class="midterm-idle-title">中期检查：未开始</span>
          <span class="midterm-idle-note">
            该环节要求指导满 {{ summary?.midterm_required ?? 10 }} 次，进入后才统计，当前不参与通过校验
          </span>
        </div>

        <div v-else-if="midtermPhase === 'AFTER'" class="midterm-idle is-done">
          <span class="midterm-idle-title">中期检查：已通过</span>
          <span class="midterm-idle-note">
            该环节共留痕 {{ midtermProgress?.done ?? 0 }} 条指导记录
          </span>
        </div>

        <div v-else-if="midtermProgress" class="midterm-bar">
          <div class="midterm-head">
            <span>中期检查：{{ midtermProgress.done }} / {{ midtermProgress.required }} 次</span>
            <span class="midterm-state" :class="{ 'is-ok': midtermProgress.reached }">
              {{ midtermProgress.reached ? '已达标' : `还差 ${midtermProgress.required - midtermProgress.done} 次` }}
            </span>
          </div>
          <el-progress
            :percentage="midtermProgress.percent"
            :stroke-width="10"
            :status="midtermProgress.reached ? 'success' : undefined"
            :show-text="false"
          />
        </div>

        <el-table :data="guidance" stripe row-key="id" class="inner-table">
          <el-table-column label="沟通时间" width="150">
            <template #default="{ row }"><span class="time">{{ formatTime(row.happened_at) }}</span></template>
          </el-table-column>
          <el-table-column label="环节" width="128">
            <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
          </el-table-column>
          <el-table-column label="方式" width="72">
            <template #default="{ row }">
              <el-tag :type="row.method === 'MEET' ? 'primary' : 'success'" effect="plain" size="small">
                {{ METHOD_LABELS[row.method as 'MEET' | 'ONLINE'] }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="沟通内容" min-width="260">
            <template #default="{ row }">
              <span class="content-text" :title="row.content">{{ row.content }}</span>
            </template>
          </el-table-column>
          <el-table-column label="证据" width="82">
            <template #default="{ row }">
              <template v-if="row.evidence_name">
                <el-image
                  v-if="isImageEvidence(row.evidence_type) && evidenceUrls[row.id]"
                  class="evidence-thumb"
                  :src="evidenceUrls[row.id]"
                  :preview-src-list="[evidenceUrls[row.id]]"
                  :preview-teleported="true"
                  fit="contain"
                  title="点击放大"
                />
                <el-button
                  v-else-if="isImageEvidence(row.evidence_type) && !evidenceLoaded"
                  link
                  class="muted-btn"
                >
                  加载中…
                </el-button>
                <el-button v-else link type="primary" @click="guidanceApi.openEvidence(row)">查看</el-button>
              </template>
              <span v-else class="muted">无</span>
            </template>
          </el-table-column>
          <el-table-column label="登记人" width="90">
            <template #default="{ row }">{{ row.teacher_name || '—' }}</template>
          </el-table-column>
          <template #empty>
            <p class="empty">还没有指导记录。教师在「指导记录」登记后，这里会列出每次沟通的时间、方式、内容与证据。</p>
          </template>
        </el-table>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>阶段材料</h3>
          <p>
            共 {{ materials.length }} 份（含历次版本）
            <template v-if="currentStageLatest.length">
              · 本环节（{{ stageShort(detail.current_stage) }}）{{ currentStageLatest.length }} 份，
              <b v-if="newMaterials.length" class="new-count">
                其中 {{ newMaterials.length }} 份学生新提交待核对
              </b>
              <template v-else-if="lastReviewedText">已于 {{ lastReviewedText }} 核对过</template>
              <template v-else>还没有审核记录</template>
            </template>
            <template v-else>· 本环节还没有材料</template>
          </p>
        </header>
        <el-table
          :data="sortedMaterials"
          stripe
          row-key="id"
          class="inner-table"
          :row-class-name="materialRowClass"
        >
          <el-table-column label="环节" width="164">
            <template #default="{ row }">
              <span>{{ stageShort(row.stage) }}</span>
              <el-tag v-if="row.stage === detail.current_stage" class="tag-current" size="small" effect="plain">
                本环节
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="材料" min-width="220">
            <template #default="{ row }">
              <span class="cell-main">
                {{ row.title }}
                <el-tag
                  v-if="isNewMaterial(row)"
                  class="tag-new"
                  size="small"
                  type="warning"
                  effect="plain"
                  title="按上传时间判定：晚于本环节最近一次通过 / 退回就算新提交。下载不会消除，审核或退回后才消失。"
                >
                  新提交
                </el-tag>
              </span>
              <span class="cell-sub">{{ row.file_name }} · {{ fileSize(row.file_size) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="版本" width="70">
            <template #default="{ row }">v{{ row.version }}</template>
          </el-table-column>
          <el-table-column label="上传时间" width="150">
            <template #default="{ row }"><span class="time">{{ formatTime(row.created_at) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="86">
            <template #default="{ row }">
              <el-button link type="primary" :icon="Download" @click="materialsApi.download(row)">下载</el-button>
            </template>
          </el-table-column>
          <template #empty>
            <p class="empty">该生还没有上传材料。</p>
          </template>
        </el-table>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>审核历史</h3>
          <p>共 {{ reviews.length }} 条，按时间倒序；通过 / 退回都会留痕</p>
        </header>
        <ul v-if="reviews.length" class="history">
          <li v-for="r in reviews" :key="r.id" class="history-item">
            <span class="history-time">{{ formatTime(r.created_at) }}</span>
            <span class="opinion" :class="r.action === 'RETURN' ? 'is-return' : 'is-approve'">
              {{ r.action === 'RETURN' ? '退回' : '通过' }}
            </span>
            <span class="history-stage">
              {{ stageLabel(r.stage) }}
              <em>→ {{ toLabel(r) }}</em>
            </span>
            <div class="history-main">
              <span class="history-comment" :title="r.comment || ''">{{ r.comment || '未填写意见' }}</span>
              <span v-if="r.ai_adopted?.length" class="history-ai" :title="aiAdoptedText(r)">
                AI 建议 {{ r.ai_adopted.length }} 条
              </span>
            </div>
            <span class="history-who">{{ r.reviewer_name || '—' }}</span>
          </li>
        </ul>
        <p v-else class="empty">还没有审核记录。</p>
      </section>
    </template>

    <ReviewDecisionDialog
      v-model="decideVisible"
      :action="decideAction"
      :target="decideTarget"
      @done="loadAll"
    />
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.crumb-sep {
  color: var(--th-border);
}

.profile {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 20px 22px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-top: 3px solid var(--th-primary);
  border-radius: 5px;
}

.who {
  display: flex;
  align-items: center;
  gap: 16px;
}

.avatar {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  font-family: var(--th-font-serif);
  font-size: 26px;
  color: #f7f1e3;
  background: var(--th-primary);
  border-radius: 4px;
}

.eyebrow {
  margin: 0 0 4px;
  font-size: 10.5px;
  letter-spacing: 0.16em;
  color: var(--th-accent);
}

.who h2 {
  margin: 0;
  font-size: 24px;
  color: var(--th-primary-deep);
}

.meta {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.side {
  display: flex;
  gap: 28px;
}

.side-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 220px;
}

.side-label {
  font-size: 11px;
  color: var(--th-text-muted);
}

.side-item strong {
  font-size: 13px;
  color: var(--th-primary-deep);
}

.side-topic {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.panel {
  padding: 16px 18px 18px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
}

.panel-head {
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--th-border-soft);
}

.panel-head h3 {
  margin: 0;
  font-size: 15px;
  color: var(--th-primary-deep);
}

.panel-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--th-text-muted);
}

.panel-head b {
  color: var(--th-primary);
}

/* 教师看完材料/记录后就在这里决定，不用返回列表再找同一行 */
.action-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.action-notes {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}

.action-hint {
  margin: 0;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

/* 新提交用金棕色，和流程条上的强调色一致，不刺眼但扫得到 */
.action-new {
  margin: 0;
  font-size: 12.5px;
  color: #8a6a25;
}

.action-warn {
  margin: 0;
  font-size: 12.5px;
  color: #a33a2a;
}

.action-btns {
  display: flex;
  flex: 0 0 auto;
  gap: 10px;
}

.teacher-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.teacher-grid > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.teacher-grid strong {
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--th-primary-deep);
}

.steps {
  display: grid;
  grid-template-columns: repeat(9, minmax(0, 1fr));
  gap: 6px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.step {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 6px;
  text-align: center;
  border: 1px solid var(--th-border-soft);
  border-radius: 3px;
  background: rgba(29, 51, 84, 0.02);
}

.step-no {
  font-size: 10px;
  letter-spacing: 0.08em;
  color: #a29a8b;
}

.step-name {
  overflow: hidden;
  font-size: 11.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--th-text-muted);
}

.step.is-done {
  background: rgba(47, 107, 79, 0.06);
  border-color: rgba(47, 107, 79, 0.2);
}

.step.is-done .step-name {
  color: #2f6b4f;
}

.step.is-current {
  background: rgba(29, 51, 84, 0.08);
  border-color: var(--th-primary);
}

.step.is-current .step-name {
  font-weight: 600;
  color: var(--th-primary-deep);
}

.midterm-bar {
  margin-bottom: 14px;
  padding: 12px 14px;
  background: rgba(198, 168, 107, 0.08);
  border-left: 3px solid var(--th-accent);
}

/* 未到中期检查时给一条中性说明，不制造"还差几次"的紧迫感 */
.midterm-idle {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 14px;
  padding: 12px 14px;
  font-size: 12.5px;
  color: var(--th-text-muted);
  background: rgba(29, 51, 84, 0.03);
  border-left: 3px solid var(--th-border);
}

.midterm-idle-title {
  font-family: var(--th-font-serif);
  color: var(--th-primary-deep);
}

.midterm-idle.is-done {
  background: rgba(47, 107, 79, 0.06);
  border-left-color: #2f6b4f;
}

.midterm-idle.is-done .midterm-idle-title {
  color: #2f6b4f;
}

.new-count {
  color: #8a6a25;
}

.tag-current,
.tag-new {
  margin-left: 6px;
}

.midterm-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 12.5px;
  color: var(--th-primary-deep);
}

.midterm-state {
  font-family: var(--th-font-serif);
  color: #a33a2a;
}

.midterm-state.is-ok {
  color: #2f6b4f;
}

.inner-table {
  width: 100%;
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

.time {
  font-size: 12px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.content-text {
  display: block;
  overflow: hidden;
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.muted {
  font-size: 12.5px;
  color: #9b958a;
}

.evidence-thumb {
  width: 46px;
  height: 46px;
  background: #fff;
  border: 1px solid var(--th-border);
  border-radius: 3px;
  cursor: zoom-in;
}

.muted-btn {
  padding: 0;
  font-size: 12px;
  color: #9b958a;
}

.empty {
  max-width: 560px;
  margin: 0 auto;
  padding: 12px 0;
  font-size: 13px;
  line-height: 1.8;
  text-align: center;
  color: var(--th-text-muted);
}

.history {
  margin: 0;
  padding: 0;
  list-style: none;
}

.history-item {
  display: grid;
  grid-template-columns: 142px 56px 190px minmax(0, 1fr) 76px;
  align-items: center;
  gap: 10px;
  padding: 9px 2px;
  font-size: 12.5px;
  border-bottom: 1px dashed var(--th-border-soft);
}

.history-time {
  font-size: 12px;
  color: var(--th-text-muted);
}

.history-stage {
  color: var(--th-primary-deep);
}

.history-stage em {
  font-style: normal;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.history-comment {
  overflow: hidden;
  color: var(--th-text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-main {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.history-main .history-comment {
  min-width: 0;
  flex: 1;
}

.history-who {
  font-size: 12px;
  color: var(--th-text-muted);
}

/* 采纳过 AI 建议的退回记录给个轻标识，悬停可看具体采纳了哪几条 */
.history-ai {
  flex: none;
  padding: 0 6px;
  font-size: 11px;
  line-height: 18px;
  color: #8a6a2f;
  background: rgba(198, 168, 107, 0.16);
  border: 1px solid rgba(198, 168, 107, 0.4);
  border-radius: 2px;
  cursor: help;
}

.opinion {
  display: inline-block;
  justify-self: start;
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

:deep(.el-table th.el-table__cell) {
  background: rgba(29, 51, 84, 0.04);
  color: var(--th-text-muted);
  font-weight: 600;
}

:deep(.el-table) {
  --el-table-border-color: var(--th-border-soft);
  --el-table-row-hover-bg-color: rgba(198, 168, 107, 0.08);
}

/* 学生新提交的材料整行淡金底，和列表页的"待审核"行保持同一套视觉语言 */
:deep(.el-table__row.row-new td.el-table__cell) {
  background: rgba(198, 168, 107, 0.16);
}

:deep(.el-table__row.row-new:hover td.el-table__cell) {
  background: rgba(198, 168, 107, 0.24);
}
</style>
