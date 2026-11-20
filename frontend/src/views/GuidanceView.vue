<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadFile, type UploadUserFile } from 'element-plus'
import { Plus, Refresh, Search, UploadFilled } from '@element-plus/icons-vue'

import { METHOD_LABELS, guidanceApi, type GuidanceRecord, type GuidanceSummary } from '@/api/guidance'
import { studentsApi, type Student } from '@/api/students'
import { STAGES } from '@/constants/stages'
import { useConfigStore } from '@/stores/config'
import { formatTime } from '@/utils/format'

const configStore = useConfigStore()

const loading = ref(false)
const items = ref<GuidanceRecord[]>([])
const total = ref(0)
const students = ref<Student[]>([])
const summary = ref<GuidanceSummary | null>(null)

const query = reactive({
  page: 1,
  size: 10,
  studentId: undefined as number | undefined,
  stage: 'MIDTERM' as string,
})

const stageOptions = STAGES.map((s) => ({ value: s.code, label: s.label }))
const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code
const methodLabel = (method: string) => METHOD_LABELS[method as 'MEET' | 'ONLINE'] ?? method

// 中期进度只在选中具体学生时才有意义
const progress = computed(() => {
  if (!query.studentId || !summary.value) return null
  const done = summary.value.midterm_count
  const required = summary.value.midterm_required
  return {
    done,
    required,
    percent: Math.min(100, Math.round((done / required) * 100)),
    reached: done >= required,
  }
})

async function load() {
  loading.value = true
  try {
    const data = await guidanceApi.list({
      page: query.page,
      size: query.size,
      stage: query.stage || undefined,
      student_id: query.studentId,
    })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  summary.value = query.studentId ? await guidanceApi.summary(query.studentId) : null
}

function search() {
  query.page = 1
  load()
  loadSummary()
}

function reset() {
  query.studentId = undefined
  query.stage = 'MIDTERM'
  search()
}

// ---- 登记指导记录 ----
const dialogVisible = ref(false)
const saving = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  studentId: undefined as number | undefined,
  stage: 'MIDTERM',
  method: 'MEET' as 'MEET' | 'ONLINE',
  happenedAt: '',
  content: '',
})

const rules: FormRules = {
  studentId: [{ required: true, message: '请选择学生', trigger: 'change' }],
  happenedAt: [{ required: true, message: '请选择沟通时间', trigger: 'change' }],
  content: [
    { required: true, message: '请写清楚这次沟通了什么', trigger: 'blur' },
    { min: 2, max: 2000, message: '内容 2-2000 字', trigger: 'blur' },
  ],
}

function nowText() {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:00`
}

const fileList = ref<UploadUserFile[]>([])
const evidenceFile = ref<File | null>(null)

function onFileChange(file: UploadFile) {
  evidenceFile.value = (file.raw as File) ?? null
}

function openCreate() {
  form.studentId = query.studentId
  form.stage = query.stage || 'MIDTERM'
  form.method = 'MEET'
  form.happenedAt = nowText()
  form.content = ''
  evidenceFile.value = null
  fileList.value = []
  dialogVisible.value = true
}

async function submit() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid || !form.studentId) return

  saving.value = true
  try {
    await guidanceApi.create({
      student_id: form.studentId,
      stage: form.stage,
      method: form.method,
      happened_at: form.happenedAt,
      content: form.content.trim(),
      file: evidenceFile.value,
    })
    ElMessage.success('指导记录已登记')
    dialogVisible.value = false
    await load()
    await loadSummary()
  } finally {
    saving.value = false
  }
}

async function remove(row: GuidanceRecord) {
  await ElMessageBox.confirm(
    `删除 ${row.student_name} 在 ${formatTime(row.happened_at)} 的这条记录？删除后中期次数会减少。`,
    '删除指导记录',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await guidanceApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
  await loadSummary()
}

onMounted(async () => {
  const [, list] = await Promise.all([configStore.load(), studentsApi.list({ page: 1, size: 100 })])
  students.value = list.items
  await load()
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <p class="eyebrow">GUIDANCE LOG</p>
        <h2>指导记录</h2>
        <p class="sub">
          中期检查要求对每位学生指导不少于 {{ configStore.midtermMin }} 次，每次登记时间、方式、内容和证据。
          管理员可在「阶段流转 → 详情」里核对，次数不足时中期无法通过。
        </p>
      </div>
      <el-button type="primary" :icon="Plus" @click="openCreate">登记一次指导</el-button>
    </header>

    <section class="toolbar">
      <el-select
        v-model="query.studentId"
        class="tool-select-wide"
        placeholder="全部学生"
        clearable
        filterable
        @change="search"
      >
        <el-option
          v-for="s in students"
          :key="s.id"
          :label="`${s.name}（${s.sno}）`"
          :value="s.id"
        />
      </el-select>
      <el-select v-model="query.stage" class="tool-select" placeholder="全部环节" clearable @change="search">
        <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-button :icon="Search" @click="search">查询</el-button>
      <el-button :icon="Refresh" plain @click="reset">重置</el-button>
      <span class="count">共 <b>{{ total }}</b> 条</span>
    </section>

    <section v-if="progress" class="progress-card">
      <div class="progress-head">
        <span class="progress-title">中期检查指导进度</span>
        <span class="progress-num" :class="{ 'is-ok': progress.reached }">
          {{ progress.done }} / {{ progress.required }} 次
        </span>
      </div>
      <el-progress
        :percentage="progress.percent"
        :stroke-width="10"
        :status="progress.reached ? 'success' : undefined"
        :show-text="false"
      />
      <p class="progress-tip">
        <template v-if="progress.reached">已满足中期检查要求，可以放行到下一环节。</template>
        <template v-else>还差 {{ progress.required - progress.done }} 次；补满前「通过」会被系统拦下。</template>
      </p>
    </section>

    <section class="table-wrap">
      <el-table v-loading="loading" :data="items" stripe row-key="id">
        <el-table-column label="沟通时间" width="156">
          <template #default="{ row }"><span class="time">{{ formatTime(row.happened_at) }}</span></template>
        </el-table-column>
        <el-table-column label="学生" width="118">
          <template #default="{ row }">
            <span class="cell-main">{{ row.student_name }}</span>
            <span class="cell-sub">{{ row.sno }}</span>
          </template>
        </el-table-column>
        <el-table-column label="方式" width="76">
          <template #default="{ row }">
            <el-tag :type="row.method === 'MEET' ? 'primary' : 'success'" effect="plain" size="small">
              {{ methodLabel(row.method) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="环节" width="132">
          <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
        </el-table-column>
        <el-table-column label="沟通内容" min-width="240">
          <template #default="{ row }">
            <span class="content-text" :title="row.content">{{ row.content }}</span>
          </template>
        </el-table-column>
        <el-table-column label="证据" width="104">
          <template #default="{ row }">
            <el-button v-if="row.evidence_name" link type="primary" @click="guidanceApi.openEvidence(row)">
              查看截图
            </el-button>
            <span v-else class="cell-sub">未上传</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <p class="empty">还没有指导记录。点右上角「登记一次指导」开始记录。</p>
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

    <el-dialog v-model="dialogVisible" title="登记指导记录" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-form-item label="学生" prop="studentId">
          <el-select v-model="form.studentId" placeholder="选择你名下的学生" filterable style="width: 100%">
            <el-option
              v-for="s in students"
              :key="s.id"
              :label="`${s.name}（${s.sno}）`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="所属环节">
          <el-select v-model="form.stage" style="width: 100%">
            <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="沟通方式">
          <el-radio-group v-model="form.method">
            <el-radio value="MEET">面谈</el-radio>
            <el-radio value="ONLINE">线上（微信 / 电话 / 视频）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="沟通时间" prop="happenedAt">
          <el-date-picker
            v-model="form.happenedAt"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择实际沟通时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="沟通内容" prop="content">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="4"
            maxlength="2000"
            show-word-limit
            placeholder="例：讨论中期检查材料，实验数据还缺两组对比，约定下周三前补齐"
          />
        </el-form-item>
        <el-form-item label="证据">
          <el-upload
            v-model:file-list="fileList"
            :auto-upload="false"
            :limit="1"
            accept=".jpg,.jpeg,.png,.webp,.pdf"
            :on-change="onFileChange"
          >
            <el-button :icon="UploadFilled">选择截图 / PDF</el-button>
            <template #tip>
              <div class="upload-tip">可选；支持 jpg / png / webp / pdf，10MB 以内</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保存记录</el-button>
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
  max-width: 760px;
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

.tool-select-wide {
  width: 240px;
}

.tool-select {
  width: 160px;
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

.progress-card {
  padding: 14px 18px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-left: 3px solid var(--th-accent);
  border-radius: 5px;
}

.progress-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}

.progress-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--th-primary-deep);
}

.progress-num {
  font-family: var(--th-font-serif);
  font-size: 16px;
  color: #a33a2a;
}

.progress-num.is-ok {
  color: #2f6b4f;
}

.progress-tip {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--th-text-muted);
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

.time {
  font-size: 12px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.content-text {
  display: block;
  overflow: hidden;
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty {
  margin: 0;
  padding: 16px 0;
  font-size: 13px;
  color: var(--th-text-muted);
}

.pager {
  display: flex;
  justify-content: flex-end;
  padding-top: 14px;
}

.upload-tip {
  font-size: 11.5px;
  color: var(--th-text-muted);
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
