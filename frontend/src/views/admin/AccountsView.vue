<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus, Refresh, Search } from '@element-plus/icons-vue'

import { accountsApi, type Account, type AccountRole } from '@/api/accounts'
import { useAuthStore } from '@/stores/auth'
import { formatTime } from '@/utils/format'

const auth = useAuthStore()

const loading = ref(false)
const items = ref<Account[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  size: 10,
  keyword: '',
  role: '' as AccountRole | '',
  active: '' as '' | 'true' | 'false',
})

const roleLabels: Record<AccountRole, string> = {
  ADMIN: '管理员',
  TEACHER: '教师',
  STUDENT: '学生',
}

const roleTagType: Record<AccountRole, 'danger' | 'primary' | 'info'> = {
  ADMIN: 'danger',
  TEACHER: 'primary',
  STUDENT: 'info',
}

const activeCount = computed(() => items.value.filter((u) => u.is_active).length)

const roleLabel = (role: string) => roleLabels[role as AccountRole] ?? role
const roleTag = (role: string) => roleTagType[role as AccountRole] ?? 'info'

async function load() {
  loading.value = true
  try {
    const data = await accountsApi.list({
      page: query.page,
      size: query.size,
      keyword: query.keyword || undefined,
      role: query.role || undefined,
      is_active: query.active === '' ? undefined : query.active === 'true',
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function search() {
  query.page = 1
  load()
}

function reset() {
  query.keyword = ''
  query.role = ''
  query.active = ''
  search()
}

// ---- 新建账号 ----
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  username: '',
  real_name: '',
  role: 'TEACHER' as 'TEACHER' | 'ADMIN',
  password: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入登录账号', trigger: 'blur' },
    {
      pattern: /^[0-9A-Za-z_.-]{3,50}$/,
      message: '3-50 位字母、数字、下划线、点或横线',
      trigger: 'blur',
    },
  ],
  real_name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  password: [{ min: 6, max: 72, message: '密码 6-72 位', trigger: 'blur' }],
}

function openCreate() {
  Object.assign(form, { username: '', real_name: '', role: 'TEACHER', password: '' })
  dialogVisible.value = true
}

async function submitCreate() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const res = await accountsApi.create({
      username: form.username.trim(),
      real_name: form.real_name.trim(),
      role: form.role,
      password: form.password || null,
    })
    dialogVisible.value = false
    await ElMessageBox.alert(
      `账号 ${res.user.username}\n初始密码 ${res.initial_password}\n\n请转告本人，登录后即可使用。`,
      form.role === 'TEACHER' ? '教师账号已创建' : '管理员账号已创建',
      { confirmButtonText: '知道了', type: 'success' },
    )
    await load()
  } finally {
    saving.value = false
  }
}

// ---- 启停 / 重置密码 ----
async function toggleActive(row: Account) {
  const next = !row.is_active
  if (!next) {
    await ElMessageBox.confirm(
      `停用后 ${row.real_name || row.username} 将无法登录，已有材料和审核记录都会保留。`,
      '停用账号',
      { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消' },
    )
  }
  await accountsApi.update(row.id, { is_active: next })
  ElMessage.success(next ? '已启用' : '已停用')
  await load()
}

async function resetPassword(row: Account) {
  await ElMessageBox.confirm(
    `将 ${row.real_name || row.username}（${row.username}）的密码重置为统一初始密码 123456。`,
    '重置密码',
    { type: 'warning', confirmButtonText: '重置', cancelButtonText: '取消' },
  )
  const res = await accountsApi.resetPassword(row.id)
  await ElMessageBox.alert(
    `账号 ${row.username}\n新密码 ${res.password}`,
    '密码已重置',
    { confirmButtonText: '知道了', type: 'success' },
  )
}

onMounted(load)
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <p class="eyebrow">ACCOUNTS</p>
        <h2>账号管理</h2>
        <p class="sub">
          教师与管理员账号在这里创建；学生账号随「学生与课题」建档自动开通。停用只禁止登录，历史记录全部保留。
        </p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">新建账号</el-button>
    </header>

    <section class="toolbar">
      <el-input
        v-model="query.keyword"
        class="tool-input"
        placeholder="账号或姓名"
        clearable
        :prefix-icon="Search"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select v-model="query.role" class="tool-select" placeholder="全部角色" clearable @change="search">
        <el-option label="管理员" value="ADMIN" />
        <el-option label="教师" value="TEACHER" />
        <el-option label="学生" value="STUDENT" />
      </el-select>
      <el-select v-model="query.active" class="tool-select" placeholder="全部状态" clearable @change="search">
        <el-option label="启用" value="true" />
        <el-option label="已停用" value="false" />
      </el-select>
      <el-button :icon="Search" @click="search">查询</el-button>
      <el-button :icon="Refresh" plain @click="reset">重置</el-button>
      <span class="count">共 <b>{{ total }}</b> 个 · 本页启用 {{ activeCount }}</span>
    </section>

    <section class="table-wrap">
      <el-table v-loading="loading" :data="items" stripe row-key="id">
        <el-table-column label="账号" min-width="150">
          <template #default="{ row }">
            <span class="cell-main">{{ row.username }}</span>
            <span class="cell-sub">{{ row.role === 'STUDENT' ? '学号即账号' : '后台登录账号' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="姓名" width="110">
          <template #default="{ row }">
            <span>{{ row.real_name || '—' }}</span>
            <span v-if="row.id === auth.user?.id" class="self">当前账号</span>
          </template>
        </el-table-column>
        <el-table-column label="角色" width="90">
          <template #default="{ row }">
            <el-tag :type="roleTag(row.role)" effect="plain" size="small">
              {{ roleLabel(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="82">
          <template #default="{ row }">
            <span class="status" :class="row.is_active ? 'is-on' : 'is-off'">
              {{ row.is_active ? '启用' : '停用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="最近登录" width="142">
          <template #default="{ row }">
            <span class="time">{{ row.last_login_at ? formatTime(row.last_login_at) : '从未登录' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="142">
          <template #default="{ row }"><span class="time">{{ formatTime(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="152" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="resetPassword(row)">重置密码</el-button>
            <el-button
              v-if="row.id !== auth.user?.id"
              link
              :type="row.is_active ? 'danger' : 'success'"
              @click="toggleActive(row)"
            >
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
          </template>
        </el-table-column>
        <template #empty>
          <p class="empty">没有匹配的账号。教师账号可在右上角「新建账号」里创建。</p>
        </template>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="query.page"
          v-model:page-size="query.size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="sizes, prev, pager, next"
          background
          @current-change="load"
          @size-change="search"
        />
      </div>
    </section>

    <el-dialog v-model="dialogVisible" title="新建账号" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="86px">
        <el-form-item label="登录账号" prop="username">
          <el-input v-model="form.username" placeholder="如 teacher_li" />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" placeholder="真实姓名" />
        </el-form-item>
        <el-form-item label="角色">
          <el-radio-group v-model="form.role">
            <el-radio value="TEACHER">教师</el-radio>
            <el-radio value="ADMIN">管理员</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input v-model="form.password" placeholder="留空则使用统一初始密码 123456" show-password />
        </el-form-item>
      </el-form>
      <p class="dialog-note">学生账号不在这里创建：在「学生与课题」建档时勾选开通，账号即学号。</p>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 2px solid var(--th-primary);
  position: relative;
}

.head::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: -5px;
  height: 1px;
  background: var(--th-border);
}

.eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  letter-spacing: 0.18em;
  color: var(--th-accent);
}

.head h2 {
  font-size: 23px;
  color: var(--th-primary-deep);
}

.sub {
  max-width: 720px;
  margin: 6px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--th-text-muted);
}

.toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
}

.tool-input {
  width: 220px;
}

.tool-select {
  width: 130px;
}

.count {
  margin-left: auto;
  font-size: 12px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.count b {
  font-family: var(--th-font-serif);
  font-size: 15px;
  color: var(--th-primary);
}

.table-wrap {
  padding: 6px 14px 14px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.05);
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

.self {
  margin-left: 6px;
  padding: 0 5px;
  font-size: 10.5px;
  color: var(--th-accent);
  background: rgba(198, 168, 107, 0.14);
  border-radius: 2px;
}

.status {
  font-size: 12.5px;
}

.status.is-on {
  color: #2f6b4f;
}

.status.is-off {
  color: #a33a2a;
}

.time {
  font-size: 12px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.empty {
  margin: 0;
  padding: 16px 0;
  font-size: 13px;
  color: var(--th-text-muted);
}

.dialog-note {
  margin: 4px 0 0;
  padding: 10px 12px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--th-text-muted);
  background: rgba(29, 51, 84, 0.04);
  border-left: 2px solid var(--th-accent);
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
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
</style>
