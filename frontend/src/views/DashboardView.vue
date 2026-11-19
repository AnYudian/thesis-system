<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import ReminderBanner from '@/components/ReminderBanner.vue'
import { reviewsApi, type PendingItem } from '@/api/reviews'
import { studentsApi, type Student } from '@/api/students'
import { STAGES } from '@/constants/stages'
import { teacherTypeLabel } from '@/constants/teachers'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const isTeacher = computed(() => auth.role === 'TEACHER')
// 就业老师目前没有任务可做：工作台单独给一页说明，不摆九张空卡片
const isReviewer = computed(() => isTeacher.value && auth.teacherType === 'REVIEWER')

const roleLabel = computed(() => {
  const map = { ADMIN: '管理员', TEACHER: '教师', STUDENT: '学生' } as const
  if (auth.role === 'TEACHER') return teacherTypeLabel(auth.teacherType)
  return auth.role ? map[auth.role] : ''
})

const roleIntro = computed(() => {
  if (isReviewer.value) {
    return '就业老师：不带学生，目前在本系统不承担任何审核任务，只保留身份与后续说明。'
  }
  const map = {
    ADMIN: '全局视角：维护账号与学生档案，查看全部材料、进度与统计。',
    TEACHER: '负责所带学生的阶段审核，决定是否放行进入下一阶段。',
    STUDENT: '按阶段提交材料，跟踪自己的进度与教师反馈。',
  } as const
  return auth.role ? map[auth.role] : ''
})

const primary = computed(() =>
  auth.role === 'TEACHER'
    ? { label: '查看我的学生', to: '/my-students' }
    : { label: '查看我的档案', to: '/profile' },
)

// ---- 教师工作台：九个环节的人数与待审核 ----
const loading = ref(false)
const pending = ref<PendingItem[]>([])
const students = ref<Student[]>([])

const stageIndex = (code: string) => STAGES.findIndex((s) => s.code === code) + 1

// “新提交”= 当前环节交过材料，且材料时间晚于最近一次审核（或根本没审过）。
// 退回后学生重新上传也会重新进待审，不会被当成“已处理”漏掉。
function isNewSubmission(row: PendingItem) {
  if (!row.material_count || !row.latest_material_at) return false
  if (!row.last_reviewed_at) return true
  return new Date(row.latest_material_at).getTime() > new Date(row.last_reviewed_at).getTime()
}

const stageCards = computed(() =>
  STAGES.map((stage) => {
    const rows = pending.value.filter((p) => p.stage === stage.code)
    return {
      ...stage,
      count: rows.length,
      todo: rows.filter(isNewSubmission).length,
    }
  }),
)

const maxCount = computed(() => Math.max(1, ...stageCards.value.map((s) => s.count)))
const todoTotal = computed(() => stageCards.value.reduce((n, s) => n + s.todo, 0))

const totalStudents = computed(() => students.value.length)
const archivedCount = computed(() => students.value.filter((s) => s.status === 'ARCHIVED').length)
const activeCount = computed(() => totalStudents.value - archivedCount.value)

// 完成度按“环节步数”算：停在选题算 0，停在任务书算完成 1 步，
// 归档按 9 步全完成；分母是 学生数 × 9，避免只看人数忽略进度深浅。
const completion = computed(() => {
  if (!totalStudents.value) return 0
  const done = students.value.reduce((sum, s) => {
    return sum + (s.status === 'ARCHIVED' ? STAGES.length : stageIndex(s.current_stage) - 1)
  }, 0)
  return Math.round((done / (totalStudents.value * STAGES.length)) * 100)
})

const RING_R = 54
const RING_C = 2 * Math.PI * RING_R
const ringDash = computed(() => `${(RING_C * completion.value) / 100} ${RING_C}`)

function barWidth(count: number) {
  return `${Math.round((count / maxCount.value) * 100)}%`
}

function openStage(code: string) {
  router.push({ name: 'teacher-reviews', query: { stage: code } })
}

/** 教师名下学生一次取完：要算归档人数和完成度，只查在途列表不够 */
async function loadAllStudents() {
  const all: Student[] = []
  let page = 1
  for (;;) {
    const res = await studentsApi.list({ page, size: 100 })
    all.push(...res.items)
    if (all.length >= res.total || !res.items.length) break
    page += 1
  }
  students.value = all
}

onMounted(async () => {
  // 就业老师没有名下学生，跳过这两次请求，免得工作台空转
  if (!isTeacher.value || isReviewer.value) return
  loading.value = true
  try {
    const [pendingRows] = await Promise.all([reviewsApi.pending(), loadAllStudents()])
    pending.value = pendingRows
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <!-- 教师工作台：一进来先看九个环节各自积压了多少人、多少份待审 -->
  <div v-if="isTeacher && !isReviewer" v-loading="loading" class="page">
    <section class="hero">
      <div class="hero-copy">
        <p class="eyebrow">2026 届 · 毕业论文（设计）全过程</p>
        <h2>{{ auth.displayName }}，欢迎回来</h2>
        <p class="lede">{{ roleIntro }}</p>

        <div class="hero-actions">
          <el-button class="hero-btn" @click="router.push(primary.to)">{{ primary.label }}</el-button>
          <el-button class="hero-btn hero-btn--ghost" @click="router.push('/reviews')">
            阶段审核<template v-if="todoTotal">（{{ todoTotal }} 份待审）</template>
          </el-button>
        </div>
      </div>

      <div class="hero-chart">
        <svg class="ring" viewBox="0 0 140 140" aria-hidden="true">
          <circle class="ring-track" cx="70" cy="70" :r="RING_R" />
          <circle
            class="ring-fill"
            cx="70"
            cy="70"
            :r="RING_R"
            :stroke-dasharray="ringDash"
            transform="rotate(-90 70 70)"
          />
        </svg>
        <div class="ring-text">
          <strong>{{ completion }}%</strong>
          <span>总体完成度</span>
        </div>
        <p class="chart-note">
          学生 {{ totalStudents }} · 在途 {{ activeCount }} · 已归档 {{ archivedCount }}
        </p>
      </div>
    </section>

    <section class="stage-section">
      <header class="section-head">
        <div>
          <h3>九环节学生分布</h3>
          <p>数字是当前停留在该环节的学生数；「待审核」指已提交材料、尚未处理的</p>
        </div>
        <span class="section-total">待审核 {{ todoTotal }} 份</span>
      </header>

      <div class="stage-grid">
        <article
          v-for="(card, i) in stageCards"
          :key="card.code"
          class="stage-card"
          :class="{ 'is-empty': !card.count, 'has-todo': card.todo }"
          @click="openStage(card.code)"
        >
          <div class="stage-head">
            <span class="stage-idx">{{ String(i + 1).padStart(2, '0') }}</span>
            <span class="stage-name">{{ card.label }}</span>
            <i v-if="card.ai" class="ai-dot" title="后期可能接入智能体" />
          </div>

          <div class="stage-body">
            <span class="stage-count">{{ card.count }}<em>人</em></span>
            <span v-if="card.todo" class="stage-badge">{{ card.todo }} 份待审核</span>
            <span v-else class="stage-clear">暂无新提交</span>
          </div>

          <div class="stage-bar"><i :style="{ width: barWidth(card.count) }" /></div>
        </article>
      </div>
    </section>

    <p class="note">
      当前身份：{{ roleLabel }}（账号 {{ auth.user?.username }}）。点击环节卡片进入阶段审核，并自动筛好该环节。
    </p>
  </div>

  <!-- 就业老师：目前没有任务，先把身份和后续安排说清楚 -->
  <div v-else-if="isReviewer" class="page">
    <section class="hero hero--plain">
      <p class="eyebrow">就业老师 · 2026 届</p>
      <h2>{{ auth.displayName }}，欢迎回来</h2>
      <p class="lede">{{ roleIntro }}</p>

      <div class="workflow">
        <span class="flow-label">流程</span>
        <template v-for="(item, index) in STAGES" :key="item.code">
          <span class="flow-node">{{ item.short }}</span>
          <span v-if="index < STAGES.length - 1" class="flow-arrow">→</span>
        </template>
      </div>

      <div class="reviewer-box">
        <strong>目前没有分配给你的任务</strong>
        <p>
          本系统的阶段审核全部由指导教师完成。等学校明确就业老师在毕设流程里的职责、以及任务如何分配后，这里再开放对应入口。
        </p>
      </div>
    </section>

    <p class="note">
      当前身份：就业老师（账号 {{ auth.user?.username }}）。如果你实际需要带学生、做阶段审核，请联系管理员把身份改为指导教师。
    </p>
  </div>

  <!-- 学生工作台保持轻量：只说明流程和自己的入口 -->
  <div v-else class="page">
    <ReminderBanner />
    <section class="hero hero--plain">
      <p class="eyebrow">2026 届 · 毕业论文（设计）全过程</p>
      <h2>{{ auth.displayName }}，欢迎回来</h2>
      <p class="lede">{{ roleIntro }}</p>

      <div class="workflow">
        <span class="flow-label">流程</span>
        <template v-for="(item, index) in STAGES" :key="item.code">
          <span class="flow-node">{{ item.short }}</span>
          <span v-if="index < STAGES.length - 1" class="flow-arrow">→</span>
        </template>
      </div>

      <el-button class="hero-btn" @click="router.push(primary.to)">{{ primary.label }}</el-button>
    </section>

    <p class="note">
      当前身份：{{ roleLabel }}（账号 {{ auth.user?.username }}）。界面只做入口显隐，权限一律由后端校验。
    </p>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

/* 深色题头压住整页重心，右侧直接放完成度环，省掉原来那条用处不大的流程长条 */
.hero {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 36px;
  padding: 30px 36px;
  color: #f5efe1;
  background:
    linear-gradient(120deg, rgba(198, 168, 107, 0.16) 0%, rgba(198, 168, 107, 0) 42%),
    linear-gradient(160deg, #24405f 0%, var(--th-primary) 55%, var(--th-primary-deep) 100%);
  border-radius: 6px;
  box-shadow: 0 16px 34px rgba(16, 31, 51, 0.18);
}

.hero::before {
  content: "";
  position: absolute;
  left: 36px;
  right: 36px;
  top: 0;
  height: 2px;
  background: linear-gradient(90deg, var(--th-accent-soft), rgba(198, 168, 107, 0));
}

.hero-copy {
  min-width: 0;
}

.eyebrow {
  margin: 0 0 10px;
  font-size: 12px;
  letter-spacing: 0.18em;
  color: var(--th-accent-soft);
}

.hero h2 {
  font-size: 30px;
  line-height: 1.35;
  color: #fbf6ea;
}

.lede {
  max-width: 560px;
  margin: 10px 0 0;
  font-size: 14px;
  color: rgba(245, 239, 225, 0.78);
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 22px;
}

.hero-btn {
  color: #f7f1e3;
  background: rgba(198, 168, 107, 0.18);
  border-color: rgba(198, 168, 107, 0.55);
}

.hero-btn:hover {
  color: #fff;
  background: rgba(198, 168, 107, 0.3);
  border-color: var(--th-accent-soft);
}

.hero-btn--ghost {
  background: transparent;
  border-color: rgba(245, 239, 225, 0.28);
}

.hero-chart {
  position: relative;
  flex: 0 0 190px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.ring {
  width: 150px;
  height: 150px;
}

.ring-track {
  fill: none;
  stroke: rgba(245, 239, 225, 0.16);
  stroke-width: 11;
}

.ring-fill {
  fill: none;
  stroke: var(--th-accent-soft);
  stroke-width: 11;
  stroke-linecap: round;
  transition: stroke-dasharray 0.5s ease;
}

.ring-text {
  position: absolute;
  top: 46px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.ring-text strong {
  font-family: var(--th-font-serif);
  font-size: 30px;
  line-height: 1;
  color: #fbf6ea;
}

.ring-text span {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: rgba(245, 239, 225, 0.6);
}

.chart-note {
  margin: 0;
  font-size: 11.5px;
  color: rgba(245, 239, 225, 0.62);
  white-space: nowrap;
}

.stage-section {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--th-border);
}

.section-head h3 {
  margin: 0;
  font-size: 17px;
  color: var(--th-primary-deep);
}

.section-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--th-text-muted);
}

.section-total {
  font-size: 12.5px;
  color: var(--th-accent);
  white-space: nowrap;
}

.stage-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.stage-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 16px 16px 14px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-top: 3px solid var(--th-primary);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.04);
  cursor: pointer;
  transition: transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease;
}

.stage-card:hover {
  transform: translateY(-2px);
  border-color: var(--th-accent);
  box-shadow: 0 12px 24px rgba(16, 31, 51, 0.1);
}

.stage-card.is-empty {
  border-top-color: var(--th-border);
  background: rgba(255, 253, 247, 0.7);
}

.stage-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}

.stage-idx {
  font-family: var(--th-font-serif);
  font-size: 11px;
  letter-spacing: 0.06em;
  color: #a29a8b;
}

.stage-name {
  overflow: hidden;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--th-primary-deep);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-dot {
  flex: 0 0 auto;
  width: 5px;
  height: 5px;
  margin-left: auto;
  border-radius: 50%;
  background: var(--th-accent);
}

.stage-body {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.stage-count {
  font-family: var(--th-font-serif);
  font-size: 28px;
  line-height: 1;
  color: var(--th-primary-deep);
}

.stage-count em {
  margin-left: 3px;
  font-family: var(--th-font-body, inherit);
  font-size: 12px;
  font-style: normal;
  color: var(--th-text-muted);
}

.stage-badge {
  padding: 1px 7px;
  font-size: 11.5px;
  color: #8a5a1c;
  background: rgba(198, 168, 107, 0.16);
  border: 1px solid rgba(198, 168, 107, 0.45);
  border-radius: 3px;
  white-space: nowrap;
}

.stage-clear {
  font-size: 11.5px;
  color: #a29a8b;
  white-space: nowrap;
}

.stage-bar {
  height: 4px;
  margin-top: 2px;
  background: rgba(29, 51, 84, 0.08);
  border-radius: 2px;
  overflow: hidden;
}

.stage-bar i {
  display: block;
  height: 100%;
  background: var(--th-primary);
  border-radius: 2px;
}

.stage-card.has-todo .stage-bar i {
  background: var(--th-accent);
}

.note {
  margin: 0;
  font-size: 12px;
  color: var(--th-text-muted);
}

/* ---- 学生版：保留流程条，不展示九宫格 ---- */
.hero--plain {
  flex-direction: column;
  align-items: flex-start;
  gap: 0;
}

/* 就业老师的说明块放在深色题头里，沿用左侧竖线的“提示条”样式 */
.reviewer-box {
  margin-top: 22px;
  padding: 13px 16px;
  background: rgba(245, 239, 225, 0.06);
  border-left: 3px solid var(--th-accent);
}

.reviewer-box strong {
  display: block;
  font-size: 13.5px;
  font-weight: 600;
  color: #f3e9d2;
}

.reviewer-box p {
  max-width: 620px;
  margin: 6px 0 0;
  font-size: 12.5px;
  line-height: 1.75;
  color: rgba(245, 239, 225, 0.72);
}

.workflow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid rgba(245, 239, 225, 0.16);
  align-self: stretch;
}

.flow-label {
  margin-right: 4px;
  font-size: 11.5px;
  letter-spacing: 0.16em;
  color: rgba(245, 239, 225, 0.55);
}

.flow-node {
  padding: 3px 10px;
  font-size: 12.5px;
  color: rgba(251, 246, 234, 0.92);
  border: 1px solid rgba(245, 239, 225, 0.24);
  border-radius: 3px;
}

.flow-arrow {
  font-size: 12px;
  color: var(--th-accent-soft);
}

@media (max-width: 1100px) {
  .stage-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .hero {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
