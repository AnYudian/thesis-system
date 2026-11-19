<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { STAGES } from '@/constants/stages'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const stages = STAGES.map((s) => s.short)

const roleLabel = computed(() => {
  const map = { ADMIN: '管理员', TEACHER: '教师', STUDENT: '学生' } as const
  return auth.role ? map[auth.role] : ''
})

const roleIntro = computed(() => {
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
</script>

<template>
  <div class="page">
    <section class="hero">
      <p class="eyebrow">2026 届 · 毕业论文（设计）全过程</p>
      <h2>{{ auth.displayName }}，欢迎回来</h2>
      <p class="lede">{{ roleIntro }}</p>

      <div class="workflow">
        <span class="flow-label">流程</span>
        <template v-for="(item, index) in stages" :key="item">
          <span class="flow-node">{{ item }}</span>
          <span v-if="index < stages.length - 1" class="flow-arrow">→</span>
        </template>
      </div>

      <el-button class="hero-btn" @click="router.push(primary.to)">{{ primary.label }}</el-button>
    </section>

    <section class="cards">
      <article class="card card--done">
        <p class="card-label">已完成</p>
        <h3>P1 · 登录与权限</h3>
        <p class="card-desc">三角色账号、JWT 登录、路由守卫与角色识别已接通。</p>
        <el-tag type="success" effect="light" size="small">已完成</el-tag>
      </article>

      <article class="card card--done">
        <p class="card-label">已完成</p>
        <h3>P2 · 学生与课题建档</h3>
        <p class="card-desc">管理员建档并开通学生账号，课题由管理员或指导教师录入。</p>
        <el-tag type="success" effect="light" size="small">已完成</el-tag>
      </article>

      <article class="card">
        <p class="card-label">下一期</p>
        <h3>P3 · 材料中心</h3>
        <p class="card-desc">按阶段上传任务书、开题报告、中期材料与论文稿件，保留版本记录。</p>
        <el-tag type="info" effect="light" size="small">待开发</el-tag>
      </article>
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

/* 深色题头压住整页重心，避免“一片浅色”发虚 */
.hero {
  position: relative;
  padding: 32px 36px 28px;
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
  max-width: 620px;
  margin: 10px 0 0;
  font-size: 14px;
  color: rgba(245, 239, 225, 0.78);
}

.workflow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px solid rgba(245, 239, 225, 0.16);
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

.hero-btn {
  margin-top: 22px;
  color: #f7f1e3;
  background: rgba(198, 168, 107, 0.18);
  border-color: rgba(198, 168, 107, 0.55);
}

.hero-btn:hover {
  color: #fff;
  background: rgba(198, 168, 107, 0.3);
  border-color: var(--th-accent-soft);
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 18px;
}

.card {
  padding: 22px 22px 20px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-top: 3px solid var(--th-primary);
  border-radius: 5px;
  box-shadow: 0 8px 20px rgba(16, 31, 51, 0.05);
}

.card--done {
  border-top-color: var(--th-accent);
}

.card-label {
  margin: 0 0 8px;
  font-size: 11.5px;
  letter-spacing: 0.14em;
  color: var(--th-accent);
}

.card h3 {
  margin-bottom: 8px;
  font-size: 18px;
  color: var(--th-primary-deep);
}

.card-desc {
  margin: 0 0 16px;
  font-size: 13.5px;
  color: var(--th-text-muted);
}

.note {
  margin: 0;
  font-size: 12px;
  color: var(--th-text-muted);
}
</style>
