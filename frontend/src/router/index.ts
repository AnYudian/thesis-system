import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

/** 各角色的默认落地页：管理员进后台，教师/学生进工作台 */
function homeOf(role: string | null | undefined): string {
  return role === 'ADMIN' ? '/admin' : '/'
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/',
      component: () => import('@/layouts/WorkLayout.vue'),
      children: [
        {
          path: '',
          name: 'dashboard',
          component: () => import('@/views/DashboardView.vue'),
          meta: { title: '工作台' },
        },
        {
          path: 'my-students',
          name: 'teacher-students',
          component: () => import('@/views/StudentsView.vue'),
          meta: { title: '我的学生', roles: ['TEACHER'] },
        },
        {
          path: 'profile',
          name: 'student-profile',
          component: () => import('@/views/StudentProfileView.vue'),
          meta: { title: '我的档案', roles: ['STUDENT'] },
        },
      ],
    },
    {
      path: '/admin',
      component: () => import('@/layouts/AdminLayout.vue'),
      meta: { roles: ['ADMIN'] },
      children: [
        {
          path: '',
          name: 'admin-overview',
          component: () => import('@/views/admin/OverviewView.vue'),
          meta: { title: '数据概览' },
        },
        {
          path: 'students',
          name: 'admin-students',
          component: () => import('@/views/StudentsView.vue'),
          meta: { title: '学生与课题' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (!auth.isLoggedIn) {
    if (to.meta.public) return true
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // 刷新页面后只有 token 没有用户信息，补一次 /me；
  // 失败说明 token 已失效，清掉再回登录页
  if (!auth.user) {
    try {
      await auth.loadMe()
    } catch {
      auth.logout()
      return to.meta.public ? true : { name: 'login', query: { redirect: to.fullPath } }
    }
  }

  // 已登录不必再看登录页，直接按角色落地
  if (to.name === 'login') return homeOf(auth.role)

  // 管理员有自己的后台，不进教师/学生工作台
  if (to.name === 'dashboard' && auth.role === 'ADMIN') return '/admin'

  // 前端只做入口显隐，真正的权限仍由后端校验
  const roles = to.meta.roles as string[] | undefined
  if (roles && !roles.includes(auth.role ?? '')) return homeOf(auth.role)

  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 毕设论文审核系统` : '毕设论文审核系统'
})

export default router
