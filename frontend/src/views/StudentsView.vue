<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ElMessage,
  ElMessageBox,
  type FormInstance,
  type FormRules,
  type UploadFile,
  type UploadUserFile,
} from 'element-plus'
import { Plus, Refresh, Search, Upload, UploadFilled, UserFilled } from '@element-plus/icons-vue'

import {
  studentsApi,
  teachersApi,
  type ImportResult,
  type Student,
  type StudentForm,
} from '@/api/students'
import { STAGES } from '@/constants/stages'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const isAdmin = computed(() => auth.role === 'ADMIN')

const loading = ref(false)
const items = ref<Student[]>([])
const total = ref(0)

const query = reactive({
  page: 1,
  size: 10,
  keyword: '',
  stage: '',
  status: '',
  teacherId: undefined as number | undefined,
})

const teachers = ref<{ id: number; real_name: string | null; username: string }[]>([])

const stageOptions = STAGES.map((s) => ({ value: s.code, label: s.label }))

function stageLabel(code: string) {
  return STAGES.find((s) => s.code === code)?.label ?? code
}

function stageIndex(code: string) {
  return STAGES.findIndex((s) => s.code === code) + 1
}

// 管理员从名单点进详情页核实指导记录与审核历史；教师端不开放这个入口
function openDetail(row: Student) {
  router.push({ path: `/admin/students/${row.id}`, query: { from: 'students' } })
}

async function load() {
  loading.value = true
  try {
    const data = await studentsApi.list({
      page: query.page,
      size: query.size,
      keyword: query.keyword || undefined,
      stage: query.stage || undefined,
      status: query.status || undefined,
      teacher_id: query.teacherId,
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
  query.stage = ''
  query.status = ''
  query.teacherId = undefined
  search()
}

// ---- 新建 / 编辑学生 ----
const dialogVisible = ref(false)
const mode = ref<'create' | 'edit'>('create')
const editingId = ref<number | null>(null)
const saving = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  sno: '',
  name: '',
  major: '',
  class_name: '',
  grade: '2022',
  teacherId: 0,
  current_stage: 'TOPIC',
  create_account: true,
})

const rules: FormRules = {
  sno: [
    { required: true, message: '请输入学号', trigger: 'blur' },
    { pattern: /^[0-9A-Za-z_-]{4,30}$/, message: '学号由 4-30 位字母、数字、下划线或横线组成', trigger: 'blur' },
  ],
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  major: [{ required: true, message: '请输入专业', trigger: 'blur' }],
  class_name: [{ required: true, message: '请输入班级', trigger: 'blur' }],
  grade: [{ required: true, message: '请输入年级', trigger: 'blur' }],
  // 指导教师决定后续谁审核材料、谁能看到这名学生，所以建档时不允许留空；
  // 0 是下拉框的初始占位值，不能当成一个真实教师 ID 提交给后端。
  teacherId: [
    {
      validator: (_rule: unknown, value: number, callback: (error?: Error) => void) => {
        if (!value) callback(new Error('请选择指导教师'))
        else callback()
      },
      trigger: 'change',
    },
  ],
}

function openCreate() {
  mode.value = 'create'
  editingId.value = null
  Object.assign(form, {
    sno: '',
    name: '',
    major: '',
    class_name: '',
    grade: '2022',
    teacherId: 0,
    current_stage: 'TOPIC',
    create_account: true,
  })
  dialogVisible.value = true
}

function openEdit(row: Student) {
  mode.value = 'edit'
  editingId.value = row.id
  Object.assign(form, {
    sno: row.sno,
    name: row.name,
    major: row.major,
    class_name: row.class_name,
    grade: row.grade,
    teacherId: row.teacher_id ?? 0,
    current_stage: row.current_stage,
    create_account: false,
  })
  dialogVisible.value = true
}

async function submitStudent() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    if (mode.value === 'create') {
      const payload: StudentForm = {
        sno: form.sno.trim(),
        name: form.name.trim(),
        major: form.major.trim(),
        class_name: form.class_name.trim(),
        grade: form.grade.trim(),
        teacher_id: form.teacherId,
        current_stage: form.current_stage,
        create_account: form.create_account,
      }
      const res = await studentsApi.create(payload)
      dialogVisible.value = false
      if (res.initial_password) {
        // 初始密码只在创建时返回一次，这里必须让管理员看到
        await ElMessageBox.alert(
          `学号 ${res.student.sno}\n登录账号 ${res.student.username}\n初始密码 ${res.initial_password}\n\n请转告学生，登录后即可查看自己的课题与进度。`,
          '学生已建档，账号已开通',
          { confirmButtonText: '知道了', type: 'success' },
        )
      } else {
        ElMessage.success('学生已建档')
      }
    } else if (editingId.value) {
      await studentsApi.update(editingId.value, {
        name: form.name.trim(),
        major: form.major.trim(),
        class_name: form.class_name.trim(),
        grade: form.grade.trim(),
        current_stage: form.current_stage,
        teacher_id: form.teacherId,
      })
      dialogVisible.value = false
      ElMessage.success('已保存')
    }
    await load()
  } finally {
    saving.value = false
  }
}

// ---- 课题 ----
const topicVisible = ref(false)
const topicSaving = ref(false)
const topicStudent = ref<Student | null>(null)
const topicRef = ref<FormInstance>()
const topicForm = reactive({
  title: '',
  summary: '',
  academic_year: '2026',
  existed: false,
})

const topicRules: FormRules = {
  title: [
    { required: true, message: '请输入课题题目', trigger: 'blur' },
    { min: 2, max: 200, message: '题目长度 2-200 字', trigger: 'blur' },
  ],
}

async function openTopic(row: Student) {
  topicStudent.value = row
  const detail = await studentsApi.detail(row.id)
  topicForm.title = detail.topic?.title ?? ''
  topicForm.summary = detail.topic?.summary ?? ''
  topicForm.academic_year = detail.topic?.academic_year ?? '2026'
  topicForm.existed = Boolean(detail.topic)
  topicVisible.value = true
}

async function submitTopic() {
  if (!topicRef.value || !topicStudent.value) return
  const valid = await topicRef.value.validate().catch(() => false)
  if (!valid) return

  topicSaving.value = true
  try {
    await studentsApi.setTopic(topicStudent.value.id, {
      title: topicForm.title.trim(),
      summary: topicForm.summary.trim() || null,
      academic_year: topicForm.academic_year,
    })
    ElMessage.success('课题已保存')
    topicVisible.value = false
    await load()
  } finally {
    topicSaving.value = false
  }
}

async function clearTopic() {
  if (!topicStudent.value) return
  await ElMessageBox.confirm('清除后该学生将回到「未选题」，确定吗？', '清除课题', {
    type: 'warning',
    confirmButtonText: '清除',
    cancelButtonText: '取消',
  })
  await studentsApi.clearTopic(topicStudent.value.id)
  ElMessage.success('课题已清除')
  topicVisible.value = false
  await load()
}

async function removeStudent(row: Student) {
  await ElMessageBox.confirm(
    `将删除学生 ${row.name}（${row.sno}）及其登录账号，操作不可恢复。`,
    '删除学生',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await studentsApi.remove(row.id)
  ElMessage.success('已删除')
  if (items.value.length === 1 && query.page > 1) query.page -= 1
  await load()
}

// ---- 批量导入 ----
const importVisible = ref(false)
const importing = ref(false)
const importMode = ref<'text' | 'excel'>('text')
const importText = ref('')
const importFile = ref<File | null>(null)
const importFileList = ref<UploadUserFile[]>([])
const importAccount = ref(true)
const importResult = ref<ImportResult | null>(null)

// 指导教师是必填列，示例里必须带上，否则照着示例粘贴也会被整行跳过
const IMPORT_SAMPLE =
  '20221201,张三,软件工程,软工2201,2022,teacher\n' +
  '20221202,李四,软件工程,软工2201,2022,teacher\n'

function openImport() {
  importMode.value = 'text'
  importText.value = ''
  importFile.value = null
  importFileList.value = []
  importAccount.value = true
  importResult.value = null
  importVisible.value = true
}

// el-upload 只负责交互，原始 File 要自己存下来，提交时才能真正发给后端
function onImportFileChange(file: UploadFile) {
  importFile.value = (file.raw as File) ?? null
}

async function submitImport() {
  if (importMode.value === 'excel') {
    if (!importFile.value) {
      ElMessage.warning('请先选择 .xlsx 文件')
      return
    }
  } else if (!importText.value.trim()) {
    ElMessage.warning('请先粘贴名单')
    return
  }

  importing.value = true
  try {
    importResult.value =
      importMode.value === 'excel'
        ? await studentsApi.importFile(importFile.value as File, importAccount.value)
        : await studentsApi.importCsv(importText.value, importAccount.value)
    const res = importResult.value
    if (res.created) {
      ElMessage.success(`已导入 ${res.created} 人${res.skipped ? `，跳过 ${res.skipped} 行` : ''}`)
      await load()
    } else {
      ElMessage.warning('没有导入任何学生，请检查下方错误原因')
    }
  } finally {
    importing.value = false
  }
}

// ---- 批量指派导师 ----
// 教师有变动时（接手别人的学生、离职交接）逐个改太慢，勾选后一次改派
const studentTable = ref<{ clearSelection: () => void } | null>(null)
const selectedIds = ref<number[]>([])
const assignVisible = ref(false)
const assignTeacherId = ref<number | undefined>(undefined)
const assigning = ref(false)

function onSelectionChange(rows: Student[]) {
  selectedIds.value = rows.map((r) => r.id)
}

function openAssign() {
  if (!selectedIds.value.length) return
  assignTeacherId.value = undefined
  assignVisible.value = true
}

async function submitAssign() {
  if (!assignTeacherId.value) {
    ElMessage.warning('请选择要指派的指导教师')
    return
  }
  assigning.value = true
  try {
    const res = await studentsApi.assignTeacher(selectedIds.value, assignTeacherId.value)
    ElMessage.success(`已将 ${res.updated} 名学生指派给 ${res.teacher_name}`)
    assignVisible.value = false
    selectedIds.value = []
    studentTable.value?.clearSelection()
    await load()
  } finally {
    assigning.value = false
  }
}

onMounted(async () => {
  await load()
  if (isAdmin.value) {
    teachers.value = await teachersApi.list().catch(() => [])
  }
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <p class="eyebrow">{{ isAdmin ? 'STUDENT & TOPIC' : 'MY STUDENTS' }}</p>
        <h2>{{ isAdmin ? '学生与课题建档' : '我的学生' }}</h2>
        <p class="sub">
          {{ isAdmin
            ? '建档时同步开通学生登录账号，初始密码统一为 123456；课题由管理员或指导教师录入。'
            : '这里只显示你名下的学生，课题由你或管理员录入。' }}
        </p>
      </div>
      <div v-if="isAdmin" class="head-actions">
        <el-button :icon="Upload" @click="openImport">批量导入</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">新建学生</el-button>
      </div>
    </header>

    <section class="toolbar">
      <el-input
        v-model="query.keyword"
        class="tool-input"
        placeholder="学号或姓名"
        clearable
        :prefix-icon="Search"
        @keyup.enter="search"
        @clear="search"
      />
      <el-select v-model="query.stage" class="tool-select" placeholder="全部环节" clearable @change="search">
        <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-select v-model="query.status" class="tool-select" placeholder="全部状态" clearable @change="search">
        <el-option label="进行中" value="ACTIVE" />
        <el-option label="已归档" value="ARCHIVED" />
      </el-select>
      <el-select
        v-if="isAdmin"
        v-model="query.teacherId"
        class="tool-select"
        placeholder="全部导师"
        clearable
        @change="search"
      >
        <el-option v-for="t in teachers" :key="t.id" :label="t.real_name || t.username" :value="t.id" />
      </el-select>
      <el-button :icon="Search" @click="search">查询</el-button>
      <el-button :icon="Refresh" plain @click="reset">重置</el-button>
      <el-button
        v-if="isAdmin && selectedIds.length"
        type="primary"
        plain
        :icon="UserFilled"
        @click="openAssign"
      >
        指派导师（{{ selectedIds.length }}）
      </el-button>
      <span class="count">共 <b>{{ total }}</b> 人</span>
    </section>

    <section class="table-wrap">
      <el-table
        ref="studentTable"
        v-loading="loading"
        :data="items"
        stripe
        row-key="id"
        @selection-change="onSelectionChange"
      >
        <el-table-column v-if="isAdmin" type="selection" width="42" />
        <el-table-column label="学号" width="128">
          <template #default="{ row }">
            <span class="cell-main">{{ row.sno }}</span>
            <span v-if="row.username" class="cell-sub">账号 {{ row.username }}</span>
            <span v-else class="cell-sub muted">未开通账号</span>
          </template>
        </el-table-column>
        <el-table-column label="姓名" width="86">
          <template #default="{ row }">
            <el-button v-if="isAdmin" link type="primary" class="name-link" @click="openDetail(row)">
              {{ row.name }}
            </el-button>
            <span v-else>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="专业 / 班级" min-width="176">
          <template #default="{ row }">
            <span class="cell-main">{{ row.major }}</span>
            <span class="cell-sub">{{ row.class_name }} · {{ row.grade }} 级</span>
          </template>
        </el-table-column>
        <el-table-column v-if="isAdmin" label="指导教师" width="92">
          <template #default="{ row }">
            <span v-if="row.teacher_name">{{ row.teacher_name }}</span>
            <span v-else class="muted">未指派</span>
          </template>
        </el-table-column>
        <el-table-column label="当前环节" width="160">
          <template #default="{ row }">
            <span class="stage-pill">
              <em>{{ String(stageIndex(row.current_stage)).padStart(2, '0') }}</em>
              {{ stageLabel(row.current_stage) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="课题" min-width="220">
          <template #default="{ row }">
            <span v-if="row.topic_title" class="topic" :title="row.topic_title">{{ row.topic_title }}</span>
            <span v-else class="muted">未选题</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="isAdmin ? 176 : 90" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openTopic(row)">课题</el-button>
            <template v-if="isAdmin">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button link type="danger" @click="removeStudent(row)">删除</el-button>
            </template>
          </template>
        </el-table-column>
        <template #empty>
          <p class="empty">没有匹配的学生。可以点右上角「新建学生」或「批量导入」。</p>
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

    <!-- 学生建档 / 编辑 -->
    <el-dialog
      v-model="dialogVisible"
      :title="mode === 'create' ? '新建学生' : '编辑学生'"
      width="560px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-form-item label="学号" prop="sno">
          <el-input v-model="form.sno" :disabled="mode === 'edit'" placeholder="如 20221234" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="学生姓名" />
        </el-form-item>
        <el-form-item label="专业" prop="major">
          <el-input v-model="form.major" placeholder="如 软件工程" />
        </el-form-item>
        <el-form-item label="班级" prop="class_name">
          <el-input v-model="form.class_name" placeholder="如 软工2201" />
        </el-form-item>
        <el-form-item label="年级" prop="grade">
          <el-input v-model="form.grade" placeholder="如 2022" />
        </el-form-item>
        <el-form-item label="指导教师" prop="teacherId">
          <el-select v-model="form.teacherId" placeholder="请选择指导教师" style="width: 100%">
            <el-option v-for="t in teachers" :key="t.id" :label="t.real_name || t.username" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="当前环节">
          <el-select v-model="form.current_stage" style="width: 100%">
            <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="mode === 'create'" label="登录账号">
          <el-checkbox v-model="form.create_account">同时开通学生账号（初始密码 123456）</el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitStudent">
          {{ mode === 'create' ? '建档' : '保存' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 指派导师 -->
    <el-dialog v-model="assignVisible" title="指派指导教师" width="480px" destroy-on-close>
      <p class="dialog-note">
        已选 <b>{{ selectedIds.length }}</b> 名学生，将统一改派给下方教师。
        只改归属关系，不影响已有材料与审核记录。
      </p>
      <el-form label-width="82px">
        <el-form-item label="指导教师" required>
          <el-select v-model="assignTeacherId" placeholder="请选择指导教师" style="width: 100%">
            <el-option
              v-for="t in teachers"
              :key="t.id"
              :label="`${t.real_name || '未命名'}（${t.username}）`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assigning" @click="submitAssign">确认指派</el-button>
      </template>
    </el-dialog>

    <!-- 批量导入 -->
    <el-dialog v-model="importVisible" title="批量导入学生" width="660px" destroy-on-close>
      <el-radio-group v-model="importMode" class="import-mode">
        <el-radio-button value="text">粘贴文本 / CSV</el-radio-button>
        <el-radio-button value="excel">上传 Excel</el-radio-button>
      </el-radio-group>

      <p class="import-tip">
        一行一个学生，列顺序固定为
        <b>学号, 姓名, 专业, 班级, 年级, 指导教师账号</b>。指导教师必填，填教师的登录账号；
        表头行可留可删。
      </p>

      <template v-if="importMode === 'text'">
        <el-input
          v-model="importText"
          type="textarea"
          :rows="8"
          :placeholder="IMPORT_SAMPLE"
          class="import-input"
        />
        <p class="import-hint">从 Excel 直接复制整块单元格粘贴进来也能识别（制表符分隔）。</p>
      </template>
      <template v-else>
        <el-upload
          v-model:file-list="importFileList"
          drag
          :auto-upload="false"
          :limit="1"
          accept=".xlsx"
          :on-change="onImportFileChange"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">把 .xlsx 拖到这里，或<em>点击选择</em></div>
          <template #tip>
            <div class="el-upload__tip">
              仅支持 .xlsx（.xls 请先另存为 .xlsx），单个文件不超过 5MB；第一行可为表头。
            </div>
          </template>
        </el-upload>
      </template>

      <el-checkbox v-model="importAccount" class="import-check">
        同时开通学生账号（账号=学号，初始密码 123456）
      </el-checkbox>

      <template v-if="importResult">
        <div class="import-summary" :class="{ 'has-error': importResult.skipped }">
          成功 <b>{{ importResult.created }}</b> 人
          <span v-if="importResult.skipped">，跳过 <b>{{ importResult.skipped }}</b> 行</span>
          <span v-if="importResult.initial_password"> · 初始密码 {{ importResult.initial_password }}</span>
        </div>
        <ul v-if="importResult.errors.length" class="issue-list">
          <li v-for="(e, i) in importResult.errors" :key="i" class="issue-item">
            <span class="issue-line">第 {{ e.line }} 行</span>
            <span class="issue-reason">{{ e.reason }}</span>
            <span class="issue-content" :title="e.content">{{ e.content }}</span>
          </li>
        </ul>
      </template>

      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
        <el-button type="primary" :loading="importing" @click="submitImport">开始导入</el-button>
      </template>
    </el-dialog>

    <!-- 课题 -->
    <el-dialog v-model="topicVisible" title="课题建档" width="600px" destroy-on-close>
      <p class="dialog-note">
        学生：<b>{{ topicStudent?.name }}</b>（{{ topicStudent?.sno }}） ·
        指导教师：{{ topicStudent?.teacher_name || '未指派' }}
      </p>
      <el-form ref="topicRef" :model="topicForm" :rules="topicRules" label-width="82px">
        <el-form-item label="课题题目" prop="title">
          <el-input v-model="topicForm.title" type="textarea" :rows="2" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item label="年度">
          <el-input v-model="topicForm.academic_year" style="width: 140px" />
        </el-form-item>
        <el-form-item label="课题简介">
          <el-input
            v-model="topicForm.summary"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="主要研究内容、技术路线、预期成果（可留空）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button v-if="topicForm.existed" type="danger" plain :loading="topicSaving" @click="clearTopic">
          清除课题
        </el-button>
        <el-button @click="topicVisible = false">取消</el-button>
        <el-button type="primary" :loading="topicSaving" @click="submitTopic">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.empty {
  margin: 0;
  padding: 16px 0;
  font-size: 13px;
  color: var(--th-text-muted);
}

.head-actions {
  display: flex;
  gap: 8px;
  white-space: nowrap;
}

.import-tip {
  margin: 0 0 10px;
  font-size: 12.5px;
  line-height: 1.8;
  color: var(--th-text-muted);
}

.import-tip b {
  color: var(--th-primary);
}

.import-mode {
  margin-bottom: 10px;
}

.import-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--th-text-muted);
}

:deep(.el-upload-dragger) {
  padding: 18px 10px;
}

.import-input :deep(textarea) {
  font-family: Consolas, "Courier New", monospace;
  font-size: 12.5px;
  line-height: 1.7;
}

.import-check {
  margin-top: 8px;
}

.import-summary {
  margin-top: 12px;
  padding: 10px 12px;
  font-size: 13px;
  color: #2f6b4f;
  background: rgba(47, 107, 79, 0.07);
  border-left: 3px solid #2f6b4f;
}

.import-summary.has-error {
  color: #8a6a1f;
  background: rgba(198, 168, 107, 0.12);
  border-left-color: var(--th-accent);
}

.issue-list {
  max-height: 200px;
  margin: 8px 0 0;
  padding: 0;
  overflow-y: auto;
  list-style: none;
}

.issue-item {
  display: flex;
  gap: 8px;
  padding: 6px 2px;
  font-size: 12px;
  border-bottom: 1px dashed var(--th-border-soft);
}

.issue-line {
  flex: none;
  color: #a29a8b;
}

.issue-reason {
  flex: none;
  color: #a33a2a;
}

.issue-content {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--th-text-muted);
}
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
  margin: 6px 0 0;
  font-size: 12.5px;
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
  width: 200px;
}

.tool-select {
  width: 150px;
}

.count {
  margin-left: auto;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.count b {
  font-family: var(--th-font-serif);
  font-size: 16px;
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

.name-link {
  padding: 0;
  font-size: 13px;
}

.cell-sub {
  display: block;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.muted {
  color: #9b958a;
  font-size: 12.5px;
}

.stage-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px 2px 6px;
  font-size: 12px;
  color: var(--th-primary);
  background: rgba(29, 51, 84, 0.06);
  border: 1px solid var(--th-border-soft);
  border-radius: 3px;
  white-space: nowrap;
}

.stage-pill em {
  font-style: normal;
  font-size: 10.5px;
  letter-spacing: 0.04em;
  color: var(--th-accent);
}

.topic {
  display: block;
  overflow: hidden;
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}

.dialog-note {
  margin: 0 0 14px;
  padding: 8px 12px;
  font-size: 12.5px;
  color: var(--th-text-muted);
  background: rgba(198, 168, 107, 0.1);
  border-left: 3px solid var(--th-accent);
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
