<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'
import { STAGES } from '@/constants/stages'

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

function logout() {
  auth.logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <div class="page">
    <header class="topbar">
      <div class="brand">
        <span class="mark">论</span>
        <div class="brand-text">
          <h1>毕设论文审核系统</h1>
          <p>Thesis Review System</p>
        </div>
      </div>
      <div class="account">
        <span class="name">{{ auth.displayName }}</span>
        <el-tag effect="plain" size="small">{{ roleLabel }}</el-tag>
        <el-button text size="small" @click="logout">退出登录</el-button>
      </div>
    </header>

    <main class="stage">
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
      </section>

      <section class="cards">
        <article class="card card--done">
          <p class="card-label">本期进度</p>
          <h3>P1 · 登录与权限</h3>
          <p class="card-desc">三角色账号、JWT 登录、路由守卫与角色识别已接通。</p>
          <el-tag type="success" effect="light" size="small">已完成</el-tag>
        </article>

        <article class="card">
          <p class="card-label">下一期</p>
          <h3>P2 · 学生与课题建档</h3>
          <p class="card-desc">管理员创建学生与指导教师关系，教师查看所带学生，学生查看课题。</p>
          <el-tag type="info" effect="light" size="small">待开发</el-tag>
        </article>

        <article class="card">
          <p class="card-label">当前身份</p>
          <h3>{{ roleLabel }}</h3>
          <p class="card-desc">账号 {{ auth.user?.username }}。前端只做入口显隐，权限一律由后端校验。</p>
          <el-tag effect="plain" size="small">{{ auth.user?.role }}</el-tag>
        </article>
      </section>
    </main>

    <footer class="foot">
      <span>毕业论文（设计）全过程进度跟踪与智能审阅系统</span>
      <span class="version">V0.1 · 2026</span>
    </footer>
  </div>
</template>

<style scoped>
.page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  max-width: 1080px;
  margin: 0 auto;
  padding: 28px 32px 26px;
}

/* 双线分隔：学术文档的版式习惯，比单线更“正式” */
.topbar {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 18px;
  border-bottom: 2px solid var(--th-primary);
}

.topbar::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -6px;
  height: 1px;
  background: var(--th-border);
}

.brand {
  display: flex;
  align-items: center;
  gap: 13px;
}

.mark {
  display: grid;
  place-items: center;
  width: 42px;
  height: 42px;
  border-radius: 4px;
  background: var(--th-primary);
  color: #f7f1e3;
  font-family: var(--th-font-serif);
  font-size: 23px;
  box-shadow: inset 0 0 0 1px rgba(198, 168, 107, 0.45);
}

.brand-text h1 {
  font-size: 18px;
  color: var(--th-primary-deep);
}

.brand-text p {
  margin: 2px 0 0;
  font-size: 10px;
  letter-spacing: 0.2em;
  color: var(--th-text-muted);
}

.account {
  display: flex;
  align-items: center;
  gap: 12px;
}

.name {
  font-size: 14px;
  font-weight: 600;
}

.stage {
  flex: 1;
  padding: 34px 0 36px;
}

/* 深色题头压住整页重心，避免“一片浅色”发虚 */
.hero {
  position: relative;
  padding: 34px 38px 30px;
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
  left: 38px;
  right: 38px;
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
  font-size: 32px;
  line-height: 1.35;
  color: #fbf6ea;
}

.lede {
  max-width: 600px;
  margin: 12px 0 0;
  font-size: 14.5px;
  color: rgba(245, 239, 225, 0.78);
}

.workflow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 26px;
  padding-top: 20px;
  border-top: 1px solid rgba(245, 239, 225, 0.16);
}

.flow-label {
  margin-right: 4px;
  font-size: 11.5px;
  letter-spacing: 0.16em;
  color: rgba(245, 239, 225, 0.55);
}

.flow-node {
  padding: 3px 11px;
  font-size: 12.5px;
  letter-spacing: 0.04em;
  color: rgba(251, 246, 234, 0.92);
  border: 1px solid rgba(245, 239, 225, 0.24);
  border-radius: 3px;
}

.flow-arrow {
  font-size: 12px;
  color: var(--th-accent-soft);
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 18px;
  margin-top: 26px;
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
  font-size: 19px;
  color: var(--th-primary-deep);
}

.card-desc {
  margin: 0 0 16px;
  font-size: 13.5px;
  color: var(--th-text-muted);
}

.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 16px;
  border-top: 1px solid var(--th-border);
  font-size: 12px;
  color: var(--th-text-muted);
}

.version {
  letter-spacing: 0.1em;
}
</style>
