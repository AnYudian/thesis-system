<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { reviewsApi, type StageReview } from '@/api/reviews'
import { studentsApi, type StudentDetail } from '@/api/students'
import { STAGES } from '@/constants/stages'
import { formatTime } from '@/utils/format'

const loading = ref(true)
const notFound = ref(false)
const detail = ref<StudentDetail | null>(null)
const reviews = ref<StageReview[]>([])

const currentIndex = computed(() =>
  detail.value ? STAGES.findIndex((s) => s.code === detail.value?.current_stage) : -1,
)

const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code

// 只认“当前环节”的退回意见：旧环节的退回学生已经改完了，再提醒会误导
const latestReturn = computed(() => {
  if (!detail.value) return null
  return reviews.value.find((r) => r.action === 'RETURN' && r.stage === detail.value?.current_stage) ?? null
})

onMounted(async () => {
  try {
    const data = await studentsApi.me()
    if (data) {
      detail.value = data
      const page = await reviewsApi.list({ page: 1, size: 5 })
      reviews.value = page.items
    } else notFound.value = true
  } catch {
    // 网络或服务异常：保持空状态，避免整页白屏
    notFound.value = true
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div v-loading="loading" class="page">
    <template v-if="detail">
      <section class="profile">
        <div class="who">
          <span class="avatar">{{ detail.name.slice(0, 1) }}</span>
          <div>
            <p class="eyebrow">STUDENT PROFILE · 2026 届</p>
            <h2>{{ detail.name }}</h2>
            <p class="meta">
              {{ detail.sno }} · {{ detail.major }} · {{ detail.class_name }} · {{ detail.grade }} 级
            </p>
          </div>
        </div>
        <div class="side">
          <div class="side-item">
            <span class="side-label">指导教师</span>
            <strong>{{ detail.teacher_name || '待指派' }}</strong>
          </div>
          <div class="side-item">
            <span class="side-label">登录账号</span>
            <strong>{{ detail.username || '—' }}</strong>
          </div>
          <div class="side-item">
            <span class="side-label">当前环节</span>
            <strong>{{ STAGES[currentIndex]?.label || '—' }}</strong>
          </div>
        </div>
      </section>

      <section v-if="latestReturn" class="return-banner">
        <span class="rb-label">退回修改</span>
        <div>
          <p class="rb-title">「{{ stageLabel(latestReturn.stage) }}」未通过</p>
          <p class="rb-text">{{ latestReturn.comment }}</p>
        </div>
        <span class="rb-meta">{{ latestReturn.reviewer_name || '指导教师' }} · {{ formatTime(latestReturn.created_at) }}</span>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>毕业设计进度</h3>
          <p>共九个环节，教师确认后进入下一环节；金色圆点表示后期可能由智能体先给出建议。</p>
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
            <i v-if="s.ai" class="ai-dot" title="后期可能接入智能体" />
          </li>
        </ol>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>我的课题</h3>
          <p v-if="detail.topic">年度 {{ detail.topic.academic_year }}</p>
          <p v-else>指导教师或管理员录入后显示在这里</p>
        </header>

        <div v-if="detail.topic" class="topic">
          <h4>{{ detail.topic.title }}</h4>
          <p class="topic-summary">{{ detail.topic.summary || '暂无课题简介。' }}</p>
        </div>
        <p v-else class="empty">还没选题。请联系指导教师或管理员完成课题建档。</p>
      </section>

      <section class="panel">
        <header class="panel-head">
          <h3>审核记录</h3>
          <p>教师对每个环节的通过 / 退回都会留痕，最近 5 条</p>
        </header>

        <ul v-if="reviews.length" class="review-list">
          <li v-for="r in reviews" :key="r.id" class="review-item">
            <span class="review-dot" :class="{ 'is-return': r.action === 'RETURN' }" />
            <div class="review-body">
              <p class="review-line">
                <span class="review-stage">{{ stageLabel(r.stage) }}</span>
                <span class="review-action" :class="r.action === 'RETURN' ? 'is-return' : 'is-approve'">
                  {{ r.action === 'RETURN' ? '退回' : '通过' }}
                </span>
                <span v-if="r.action === 'APPROVE'" class="review-to">
                  → {{ r.to_stage === r.stage ? '归档' : stageLabel(r.to_stage) }}
                </span>
              </p>
              <p class="review-comment">{{ r.comment || '未填写意见' }}</p>
              <p class="review-meta">
                {{ formatTime(r.created_at) }} · {{ r.reviewer_name || '—' }}
                <template v-if="r.material_version"> · 审阅时第 {{ r.material_version }} 版</template>
              </p>
            </div>
          </li>
        </ul>
        <p v-else class="empty">还没有审核记录。教师处理后会显示在这里。</p>
      </section>
    </template>

    <div v-else-if="!loading && notFound" class="empty-card">
      <h3>暂未查询到学生档案</h3>
      <p>你的账号已开通，但管理员还没有为这个账号建立学生档案。请联系教学秘书或管理员补录学号、专业与指导教师。</p>
    </div>
  </div>
</template>

<style scoped>
.return-banner {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  background: #fdf6ec;
  border: 1px solid rgba(163, 58, 42, 0.25);
  border-left: 4px solid #a33a2a;
  border-radius: 4px;
}

.rb-label {
  flex: none;
  padding: 2px 8px;
  font-size: 11.5px;
  color: #a33a2a;
  background: rgba(163, 58, 42, 0.08);
  border: 1px solid rgba(163, 58, 42, 0.25);
  border-radius: 3px;
  white-space: nowrap;
}

.rb-title {
  margin: 0;
  font-size: 13.5px;
  font-weight: 600;
  color: #8c3225;
}

.rb-text {
  margin: 3px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: #6b4a3f;
  white-space: pre-line;
}

.rb-meta {
  margin-left: auto;
  font-size: 11.5px;
  color: #a5867a;
  white-space: nowrap;
}

.review-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.review-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px dashed var(--th-border-soft);
}

.review-item:last-child {
  border-bottom: none;
  padding-bottom: 0;
}

.review-dot {
  flex: none;
  width: 8px;
  height: 8px;
  margin-top: 6px;
  border-radius: 50%;
  background: var(--th-primary);
  box-shadow: 0 0 0 3px rgba(29, 51, 84, 0.1);
}

.review-dot.is-return {
  background: #a33a2a;
  box-shadow: 0 0 0 3px rgba(163, 58, 42, 0.12);
}

.review-body {
  flex: 1;
  min-width: 0;
}

.review-line {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 0;
}

.review-stage {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--th-primary-deep);
}

.review-action {
  padding: 1px 6px;
  font-size: 11.5px;
  border-radius: 3px;
}

.review-action.is-approve {
  color: var(--th-primary);
  background: rgba(29, 51, 84, 0.06);
  border: 1px solid var(--th-border-soft);
}

.review-action.is-return {
  color: #a33a2a;
  background: rgba(163, 58, 42, 0.08);
  border: 1px solid rgba(163, 58, 42, 0.25);
}

.review-to {
  font-size: 12px;
  color: var(--th-text-muted);
}

.review-comment {
  margin: 4px 0 0;
  font-size: 13px;
  line-height: 1.7;
  color: var(--th-text-muted);
  white-space: pre-line;
}

.review-meta {
  margin: 4px 0 0;
  font-size: 11.5px;
  color: #a29a8b;
}

.page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 320px;
}

.profile {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
  padding: 26px 30px;
  color: #f5efe1;
  background:
    linear-gradient(120deg, rgba(198, 168, 107, 0.16) 0%, rgba(198, 168, 107, 0) 45%),
    linear-gradient(160deg, #24405f 0%, var(--th-primary) 58%, var(--th-primary-deep) 100%);
  border-radius: 6px;
  box-shadow: 0 16px 34px rgba(16, 31, 51, 0.18);
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
  border-radius: 4px;
  background: rgba(198, 168, 107, 0.2);
  color: #f7f1e3;
  font-family: var(--th-font-serif);
  font-size: 27px;
  box-shadow: inset 0 0 0 1px rgba(198, 168, 107, 0.5);
}

.eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--th-accent-soft);
}

.profile h2 {
  font-size: 26px;
  color: #fbf6ea;
}

.meta {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: rgba(245, 239, 225, 0.75);
}

.side {
  display: flex;
  gap: 26px;
}

.side-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.side-label {
  font-size: 10.5px;
  letter-spacing: 0.12em;
  color: rgba(245, 239, 225, 0.55);
}

.side-item strong {
  font-size: 14px;
  font-weight: 600;
  color: #fbf6ea;
}

.panel {
  padding: 20px 22px 22px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.05);
}

.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--th-border-soft);
}

.panel-head h3 {
  font-size: 16px;
  color: var(--th-primary-deep);
}

.panel-head p {
  margin: 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.steps {
  display: grid;
  /* 九个环节排成一行，一眼看出全流程；窄屏再折行 */
  grid-template-columns: repeat(9, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

@media (max-width: 900px) {
  .steps {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.step {
  position: relative;
  padding: 10px 12px;
  background: #f7f3e9;
  border: 1px solid var(--th-border-soft);
  border-radius: 4px;
}

.step-no {
  display: block;
  font-size: 10.5px;
  letter-spacing: 0.08em;
  color: #a29a8b;
}

.step-name {
  display: block;
  font-size: 12.5px;
  line-height: 1.45;
  color: var(--th-text-muted);
}

.step.is-done {
  background: rgba(29, 51, 84, 0.05);
  border-color: rgba(29, 51, 84, 0.18);
}

.step.is-done .step-name {
  color: var(--th-primary);
}

.step.is-current {
  background: var(--th-primary);
  border-color: var(--th-primary);
}

.step.is-current .step-no,
.step.is-current .step-name {
  color: #f7f1e3;
}

.ai-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--th-accent);
}

.step.is-current .ai-dot {
  background: var(--th-accent-soft);
}

.topic h4 {
  margin: 0 0 8px;
  font-family: var(--th-font-serif);
  font-size: 17px;
  color: var(--th-primary-deep);
}

.topic-summary {
  margin: 0;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--th-text-muted);
  white-space: pre-line;
}

.empty {
  margin: 0;
  font-size: 13px;
  color: var(--th-text-muted);
}

.empty-card {
  padding: 36px 40px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-top: 3px solid var(--th-accent);
  border-radius: 5px;
}

.empty-card h3 {
  font-size: 19px;
  color: var(--th-primary-deep);
}

.empty-card p {
  margin: 10px 0 0;
  max-width: 560px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--th-text-muted);
}
</style>
