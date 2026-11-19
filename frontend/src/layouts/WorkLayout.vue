<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ChangePasswordDialog from '@/components/ChangePasswordDialog.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const pwdVisible = ref(false)

const roleLabel = computed(() => {
  const map = { ADMIN: '管理员', TEACHER: '教师', STUDENT: '学生' } as const
  return auth.role ? map[auth.role] : ''
})

// 教师和学生共用同一个外壳，只是导航项不同；管理员的导航在 AdminLayout 里
const nav = computed(() => {
  if (auth.role === 'TEACHER') {
    return [
      { to: '/', title: '工作台', exact: true },
      { to: '/my-students', title: '我的学生' },
      { to: '/materials', title: '学生材料' },
      { to: '/guidance', title: '指导记录' },
      { to: '/reviews', title: '阶段审核' },
    ]
  }
  return [
    { to: '/', title: '工作台', exact: true },
    { to: '/profile', title: '我的档案' },
    { to: '/my-materials', title: '材料提交' },
  ]
})

function isActive(to: string, exact?: boolean) {
  return exact ? route.path === to : route.path.startsWith(to)
}

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

      <nav class="nav">
        <router-link
          v-for="item in nav"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ 'is-active': isActive(item.to, item.exact) }"
        >
          {{ item.title }}
        </router-link>
      </nav>

      <div class="account">
        <span class="name">{{ auth.displayName }}</span>
        <el-tag effect="plain" size="small">{{ roleLabel }}</el-tag>
        <el-button text size="small" @click="pwdVisible = true">修改密码</el-button>
        <el-button text size="small" @click="logout">退出登录</el-button>
      </div>
    </header>

    <main class="body">
      <router-view />
    </main>

    <ChangePasswordDialog v-model="pwdVisible" />

    <footer class="foot">
      <span>毕业论文（设计）全过程进度跟踪与智能审阅系统</span>
      <span class="version">V0.6 · 2026</span>
    </footer>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  max-width: 1120px;
  margin: 0 auto;
  padding: 24px 30px 22px;
}

/* 双线分隔：学术文档的版式习惯，比单线更“正式” */
.topbar {
  position: relative;
  display: flex;
  align-items: center;
  gap: 28px;
  padding-bottom: 16px;
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
  gap: 12px;
}

.mark {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 4px;
  background: var(--th-primary);
  color: #f7f1e3;
  font-family: var(--th-font-serif);
  font-size: 22px;
  box-shadow: inset 0 0 0 1px rgba(198, 168, 107, 0.45);
}

.brand-text h1 {
  font-size: 17px;
  color: var(--th-primary-deep);
}

.brand-text p {
  margin: 2px 0 0;
  font-size: 9.5px;
  letter-spacing: 0.2em;
  color: var(--th-text-muted);
}

.nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.nav-link {
  position: relative;
  padding: 6px 12px;
  font-size: 13.5px;
  color: var(--th-text-muted);
  text-decoration: none;
  border-radius: 3px;
}

.nav-link:hover {
  color: var(--th-primary);
  background: rgba(29, 51, 84, 0.05);
}

.nav-link.is-active {
  color: var(--th-primary-deep);
  font-weight: 600;
}

.nav-link.is-active::after {
  content: "";
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 0;
  height: 2px;
  background: var(--th-accent);
}

.account {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.name {
  font-size: 13.5px;
  font-weight: 600;
}

.body {
  flex: 1;
  padding: 28px 0 32px;
}

.foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 14px;
  border-top: 1px solid var(--th-border);
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.version {
  letter-spacing: 0.1em;
}
</style>
