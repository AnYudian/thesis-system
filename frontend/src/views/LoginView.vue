<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, FormRules } from 'element-plus'

import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await auth.login(form.username.trim(), form.password)
    // 管理员和管理员以外的角色落在不同入口，登录后不用再手动找路
    const fallback = auth.role === 'ADMIN' ? '/admin' : '/'
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : fallback
    await router.replace(redirect)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <div class="panel">
      <p class="kicker">2026 届 · 毕业论文（设计）全过程</p>

      <div class="brand">
        <span class="mark">论</span>
        <div>
          <h1>毕设论文审核系统</h1>
          <p>THESIS REVIEW SYSTEM</p>
        </div>
      </div>

      <p class="intro">使用学校分配的账号登录，按角色进入对应工作台。</p>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @submit.prevent="submit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
            autocomplete="current-password"
          />
        </el-form-item>
        <el-button class="submit" type="primary" :loading="loading" native-type="submit">登 录</el-button>
      </el-form>

      <div class="hint">
        <p class="hint-title">演示账号</p>
        <p>管理员 admin · 教师 teacher · 学生 student，密码均为 123456</p>
      </div>
    </div>

    <footer class="foot">毕业论文（设计）全过程进度跟踪与智能审阅系统 · V0.6</footer>
  </div>
</template>

<style scoped>
.page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 26px;
  padding: 40px 20px;
}

.panel {
  position: relative;
  width: 100%;
  max-width: 430px;
  padding: 34px 40px 30px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-top: 4px solid var(--th-accent);
  border-radius: 5px;
  box-shadow: 0 26px 60px rgba(16, 31, 51, 0.14);
}

.kicker {
  margin: 0 0 20px;
  font-size: 11.5px;
  letter-spacing: 0.16em;
  color: var(--th-accent);
}

.brand {
  display: flex;
  align-items: center;
  gap: 13px;
}

.mark {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 4px;
  background: var(--th-primary);
  color: #f7f1e3;
  font-family: var(--th-font-serif);
  font-size: 24px;
  box-shadow: inset 0 0 0 1px rgba(198, 168, 107, 0.45);
}

.brand h1 {
  font-size: 19px;
  color: var(--th-primary-deep);
}

.brand p {
  margin: 2px 0 0;
  font-size: 10px;
  letter-spacing: 0.18em;
  color: var(--th-text-muted);
}

.intro {
  margin: 22px 0 20px;
  font-size: 13.5px;
  color: var(--th-text-muted);
}

.submit {
  width: 100%;
  margin-top: 6px;
  letter-spacing: 0.34em;
  font-weight: 600;
}

.hint {
  margin-top: 24px;
  padding-top: 18px;
  border-top: 1px dashed var(--th-border);
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.hint p {
  margin: 0;
}

.hint-title {
  margin-bottom: 4px !important;
  letter-spacing: 0.12em;
  color: var(--th-accent);
}

.foot {
  font-size: 12px;
  color: var(--th-text-muted);
}
</style>
