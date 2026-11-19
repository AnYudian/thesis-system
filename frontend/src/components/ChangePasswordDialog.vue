<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'

import { authApi } from '@/api/auth'

// 用 defineModel 让父组件 v-model 控制显隐，组件内部只管表单
const visible = defineModel<boolean>({ required: true })

const formRef = ref<FormInstance>()
const saving = ref(false)
const form = reactive({ oldPassword: '', newPassword: '', confirm: '' })

const rules: FormRules = {
  oldPassword: [{ required: true, message: '请输入原密码', trigger: 'blur' }],
  newPassword: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, max: 72, message: '密码 6-72 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入新密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== form.newPassword) callback(new Error('两次输入的新密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

watch(visible, (open) => {
  if (open) {
    form.oldPassword = ''
    form.newPassword = ''
    form.confirm = ''
    formRef.value?.clearValidate()
  }
})

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    await authApi.changePassword(form.oldPassword, form.newPassword)
    ElMessage.success('密码已修改，下次登录请使用新密码')
    visible.value = false
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog v-model="visible" title="修改密码" width="440px" :close-on-click-modal="false">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="86px">
      <el-form-item label="原密码" prop="oldPassword">
        <el-input v-model="form.oldPassword" type="password" show-password autocomplete="current-password" />
      </el-form-item>
      <el-form-item label="新密码" prop="newPassword">
        <el-input v-model="form.newPassword" type="password" show-password autocomplete="new-password" />
      </el-form-item>
      <el-form-item label="确认新密码" prop="confirm">
        <el-input v-model="form.confirm" type="password" show-password autocomplete="new-password" />
      </el-form-item>
    </el-form>
    <p class="note">密码 6-72 位。修改后当前登录状态不变，下次登录使用新密码。</p>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="submit">确认修改</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.note {
  margin: 0;
  padding-left: 86px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--th-text-muted);
}
</style>
