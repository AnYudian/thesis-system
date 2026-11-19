<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  DataBoard,
  DocumentChecked,
  FolderOpened,
  Setting,
  Stamp,
  SwitchButton,
  User,
} from '@element-plus/icons-vue'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// 已建成的只有概览；其余按分期占位，避免做出“点了没反应”的假菜单
const menu = [
  { title: '数据概览', icon: DataBoard, to: '/admin', ready: true },
  { title: '学生与课题', icon: User, tag: 'P2', ready: false },
  { title: '材料中心', icon: FolderOpened, tag: 'P3', ready: false },
  { title: '阶段审核', icon: Stamp, tag: 'P4', ready: false },
  { title: '账号管理', icon: Setting, tag: 'P4', ready: false },
]

const pageTitle = computed(() => (route.meta.title as string | undefined) ?? '管理控制台')

function logout() {
  auth.logout()
  router.replace({ name: 'login' })
}
</script>

<template>
  <div class="shell">
    <aside class="side">
      <div class="brand">
        <span class="mark">论</span>
        <div class="brand-text">
          <h1>毕设论文审核</h1>
          <p>THESIS REVIEW</p>
        </div>
      </div>

      <p class="side-label">管理控制台</p>

      <nav class="nav">
        <template v-for="item in menu" :key="item.title">
          <router-link v-if="item.ready" :to="item.to!" class="nav-item" active-class="is-active">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
          </router-link>
          <span v-else class="nav-item is-locked" :title="`${item.tag} 阶段开放`">
            <el-icon><component :is="item.icon" /></el-icon>
            <span>{{ item.title }}</span>
            <em>{{ item.tag }}</em>
          </span>
        </template>
      </nav>

      <div class="side-foot">
        <p>V0.1 · 演示数据</p>
        <p class="side-tip">管理员视角：查看全局进度与材料</p>
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <div class="crumb">
          <span>管理控制台</span>
          <span class="sep">/</span>
          <strong>{{ pageTitle }}</strong>
        </div>

        <div class="account">
          <div class="who">
            <span class="avatar">{{ auth.displayName.slice(0, 1) }}</span>
            <div class="who-text">
              <strong>{{ auth.displayName }}</strong>
              <span>管理员</span>
            </div>
          </div>
          <el-button text size="small" @click="logout">
            <el-icon class="btn-icon"><SwitchButton /></el-icon>
            退出
          </el-button>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  min-height: 100vh;
}

/* 侧栏用最深的一档墨蓝，靠哑金细线与内容区分开，比浅色侧栏更有“院系系统”的分量 */
.side {
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  flex: 0 0 232px;
  height: 100vh;
  padding: 22px 14px 18px;
  color: rgba(245, 239, 225, 0.82);
  background:
    linear-gradient(180deg, rgba(198, 168, 107, 0.1) 0%, rgba(198, 168, 107, 0) 32%),
    linear-gradient(180deg, #172c46 0%, #101f33 100%);
  border-right: 1px solid rgba(198, 168, 107, 0.22);
}

.brand {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 2px 6px 20px;
}

.mark {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  border-radius: 4px;
  background: rgba(198, 168, 107, 0.16);
  color: #f0e3c6;
  font-family: var(--th-font-serif);
  font-size: 21px;
  box-shadow: inset 0 0 0 1px rgba(198, 168, 107, 0.45);
}

.brand-text h1 {
  font-size: 15.5px;
  color: #f7f1e3;
  letter-spacing: 0.02em;
}

.brand-text p {
  margin: 1px 0 0;
  font-size: 9px;
  letter-spacing: 0.2em;
  color: rgba(245, 239, 225, 0.45);
}

.side-label {
  margin: 4px 0 8px 8px;
  font-size: 10.5px;
  letter-spacing: 0.18em;
  color: rgba(198, 168, 107, 0.75);
}

.nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 4px;
  font-size: 13.5px;
  color: rgba(245, 239, 225, 0.78);
  text-decoration: none;
  transition: background 0.16s ease, color 0.16s ease;
}

.nav-item:hover {
  background: rgba(245, 239, 225, 0.07);
  color: #f7f1e3;
}

/* 选中态用左侧金条 + 淡金底，比整块高亮更克制 */
.nav-item.is-active {
  background: rgba(198, 168, 107, 0.15);
  color: #fbf6ea;
}

.nav-item.is-active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 2px;
  border-radius: 2px;
  background: var(--th-accent-soft);
}

.nav-item.is-locked {
  color: rgba(245, 239, 225, 0.38);
  cursor: not-allowed;
}

.nav-item em {
  margin-left: auto;
  padding: 0 5px;
  font-size: 10px;
  font-style: normal;
  letter-spacing: 0.06em;
  color: rgba(198, 168, 107, 0.9);
  border: 1px solid rgba(198, 168, 107, 0.4);
  border-radius: 3px;
}

.side-foot {
  margin-top: auto;
  padding: 14px 8px 0;
  border-top: 1px solid rgba(245, 239, 225, 0.12);
  font-size: 11.5px;
  color: rgba(245, 239, 225, 0.45);
}

.side-foot p {
  margin: 0;
}

.side-tip {
  margin-top: 4px !important;
  font-size: 11px;
  line-height: 1.6;
}

.main {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-width: 0;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 28px;
  background: rgba(255, 253, 247, 0.92);
  border-bottom: 1px solid var(--th-border);
  backdrop-filter: blur(6px);
}

.crumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.crumb strong {
  color: var(--th-primary-deep);
  font-weight: 600;
}

.sep {
  color: var(--th-border);
}

.account {
  display: flex;
  align-items: center;
  gap: 16px;
}

.who {
  display: flex;
  align-items: center;
  gap: 9px;
}

.avatar {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--th-primary);
  color: #f7f1e3;
  font-family: var(--th-font-serif);
  font-size: 14px;
}

.who-text {
  display: flex;
  flex-direction: column;
  line-height: 1.3;
}

.who-text strong {
  font-size: 13px;
  color: var(--th-primary-deep);
}

.who-text span {
  font-size: 11px;
  color: var(--th-text-muted);
}

.btn-icon {
  margin-right: 4px;
}

.content {
  flex: 1;
  padding: 24px 28px 34px;
}
</style>
