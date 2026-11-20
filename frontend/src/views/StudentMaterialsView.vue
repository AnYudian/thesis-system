<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, genFileId, type UploadFile, type UploadInstance, type UploadRawFile } from 'element-plus'
import { Download, UploadFilled } from '@element-plus/icons-vue'

import ReminderBanner from '@/components/ReminderBanner.vue'
import AiReviewPanel from '@/components/AiReviewPanel.vue'
import AiStatusBar from '@/components/AiStatusBar.vue'
import { materialsApi, type Material } from '@/api/materials'
import { studentsApi } from '@/api/students'
import { STAGES } from '@/constants/stages'
import { useConfigStore } from '@/stores/config'
import { formatSize, formatTime } from '@/utils/format'

const configStore = useConfigStore()

const loading = ref(false)
const uploading = ref(false)
const items = ref<Material[]>([])
const total = ref(0)

const uploadRef = ref<UploadInstance>()
const aiPanel = ref<InstanceType<typeof AiReviewPanel> | null>(null)
const pickedFile = ref<File | null>(null)
const pickedName = ref('')

const form = reactive({ stage: 'TOPIC', title: '', note: '' })

const stageOptions = STAGES.map((s) => ({ value: s.code, label: s.label }))
const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code

// 本环节截止日期由管理员在「参数配置」里设，没设就不显示提示条
const currentStage = ref<string | null>(null)
const stageDeadline = computed(() => configStore.deadlineOf(currentStage.value))
const stageDaysLeft = computed(() => configStore.daysLeft(currentStage.value))

// 九环节覆盖情况：哪一环还没有材料一眼就能看出来
const coverage = computed(() =>
  STAGES.map((s) => ({
    ...s,
    count: items.value.filter((i) => i.stage === s.code).length,
  })),
)

async function load() {
  loading.value = true
  try {
    const data = await materialsApi.list({ page: 1, size: 100 })
    items.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function onChange(file: UploadFile) {
  pickedFile.value = file.raw ?? null
  pickedName.value = file.name
}

function onExceed(files: File[]) {
  // 只允许一个文件：再选时直接替换掉旧的
  resetPicker()
  const file = files[0] as UploadRawFile
  file.uid = genFileId()
  uploadRef.value?.handleStart(file)
}

/** clearFiles 只清组件内部列表，原生 input 的值不清就会导致"再选同一个文件没反应" */
function resetPicker() {
  uploadRef.value?.clearFiles()
  const root = (uploadRef.value as unknown as { $el?: HTMLElement })?.$el
  const input = root?.querySelector('input[type="file"]') as HTMLInputElement | null
  if (input) input.value = ''
}

async function submit() {
  if (!pickedFile.value) {
    ElMessage.warning('请先选择要上传的文件')
    return
  }
  if (!form.title.trim()) {
    ElMessage.warning('请填写材料名称，例如「开题报告」')
    return
  }
  uploading.value = true
  const stage = form.stage
  try {
    const item = await materialsApi.upload(pickedFile.value, {
      stage: form.stage,
      title: form.title.trim(),
      note: form.note.trim() || null,
    })
    // 开题报告会被自动送去 AI 预审，明确告诉学生"交了、正在看"，
    // 否则上传成功的提示一闪而过，学生以为没交上去
    const aiPending = stage === 'PROPOSAL'
    ElMessage.success(
      aiPending
        ? `已上传第 ${item.version} 版，AI 正在预审开题报告，几秒后下方会出意见`
        : `上传成功，当前为第 ${item.version} 版`,
    )
    form.title = ''
    form.note = ''
    pickedFile.value = null
    pickedName.value = ''
    resetPicker()
    await load()
    if (aiPending) {
      await nextTick()
      aiPanel.value?.refresh()
      ;(aiPanel.value?.$el as HTMLElement | undefined)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  } finally {
    uploading.value = false
  }
}

async function download(row: Material) {
  await materialsApi.download(row)
}

async function remove(row: Material) {
  await ElMessageBox.confirm(
    `删除「${row.title}」第 ${row.version} 版后不可恢复，确定吗？`,
    '删除材料',
    { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
  )
  await materialsApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

onMounted(async () => {
  // 预选当前环节，学生多数时候就是交这一环的材料
  try {
    const me = await studentsApi.me()
    if (me) {
      form.stage = me.current_stage
      currentStage.value = me.current_stage
    }
  } catch {
    // 没有档案也不影响看历史材料
  }
  await Promise.all([load(), configStore.load()])
})
</script>

<template>
  <div class="page">
    <header class="head">
      <div>
        <p class="eyebrow">MY MATERIALS</p>
        <h2>材料提交</h2>
        <p class="sub">同一环节重复上传会保留为新版本，旧版本仍可下载，方便对照修改过程。</p>
      </div>
      <span class="count">已提交 <b>{{ total }}</b> 份</span>
    </header>

    <AiStatusBar />

    <ReminderBanner />

    <section
      v-if="stageDeadline"
      class="deadline-banner"
      :class="{ 'is-overdue': (stageDaysLeft ?? 0) < 0 }"
    >
      <div class="db-left">
        <span class="db-label">本环节截止</span>
        <strong class="db-date">{{ stageDeadline }}</strong>
        <span class="db-stage">{{ stageLabel(currentStage || '') }}</span>
      </div>
      <span class="db-right">
        <template v-if="stageDaysLeft === null"></template>
        <template v-else-if="stageDaysLeft < 0">已逾期 {{ -stageDaysLeft }} 天，请尽快提交并联系导师</template>
        <template v-else-if="stageDaysLeft === 0">今天截止</template>
        <template v-else>还剩 {{ stageDaysLeft }} 天</template>
      </span>
    </section>

    <section class="panel upload-panel">
      <div class="panel-title">
        <h3>上传材料</h3>
        <p>支持 PDF / Word / 压缩包 / 图片，单个文件不超过 20MB</p>
      </div>

      <div class="upload-body">
        <div class="form-col">
          <label class="field">
            <span>所属环节</span>
            <el-select v-model="form.stage" size="default">
              <el-option v-for="s in stageOptions" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </label>
          <label class="field">
            <span>材料名称</span>
            <el-input v-model="form.title" placeholder="如：开题报告、任务书、论文初稿" maxlength="120" />
          </label>
          <label class="field">
            <span>说明（可选）</span>
            <el-input v-model="form.note" placeholder="如：按导师意见修改了第三章" maxlength="500" />
          </label>
        </div>

        <el-upload
          ref="uploadRef"
          class="drop"
          drag
          :auto-upload="false"
          :limit="1"
          :on-change="onChange"
          :on-exceed="onExceed"
          accept=".pdf,.doc,.docx,.zip,.rar,.jpg,.jpeg,.png"
        >
          <el-icon class="drop-icon"><UploadFilled /></el-icon>
          <div class="drop-text">把文件拖到这里，或<em>点击选择</em></div>
          <template #tip>
            <p class="drop-tip">
              {{ pickedName ? `已选择：${pickedName}` : '支持 PDF / DOC / DOCX / ZIP / RAR / JPG / PNG' }}
            </p>
          </template>
        </el-upload>
      </div>

      <div class="upload-actions">
        <el-button type="primary" :loading="uploading" @click="submit">上传并存为最新版本</el-button>
      </div>
    </section>

    <AiReviewPanel ref="aiPanel" />

    <section class="panel">
      <div class="panel-title">
        <h3>九环节覆盖</h3>
        <p>数字是该环节已提交的版本数</p>
      </div>
      <div class="coverage">
        <div v-for="(s, i) in coverage" :key="s.code" class="cov" :class="{ 'is-empty': !s.count }">
          <span class="cov-no">{{ String(i + 1).padStart(2, '0') }}</span>
          <span class="cov-name" :title="s.label">{{ s.short }}</span>
          <span class="cov-count">{{ s.count }}</span>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-title">
        <h3>提交记录</h3>
        <p>最新的在前</p>
      </div>
      <el-table v-loading="loading" :data="items" stripe row-key="id">
        <el-table-column label="环节" width="168">
          <template #default="{ row }">
            <span class="stage-pill">{{ stageLabel(row.stage) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="材料名称" min-width="200">
          <template #default="{ row }">
            <span class="cell-main">{{ row.title }}</span>
            <span class="cell-sub" :title="row.file_name">{{ row.file_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="66">
          <template #default="{ row }"><span class="ver">v{{ row.version }}</span></template>
        </el-table-column>
        <el-table-column label="大小" width="80">
          <template #default="{ row }">{{ formatSize(row.file_size) }}</template>
        </el-table-column>
        <el-table-column label="上传时间" width="156">
          <template #default="{ row }"><span class="time">{{ formatTime(row.created_at) }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :icon="Download" @click="download(row)">下载</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <p class="empty">还没有提交过材料。先在上方选择环节并上传第一份文件。</p>
        </template>
      </el-table>
    </section>
  </div>
</template>

<style scoped>
.deadline-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  background: rgba(245, 239, 225, 0.6);
  border: 1px solid var(--th-border);
  border-left: 3px solid var(--th-accent);
  border-radius: 5px;
}

.deadline-banner.is-overdue {
  background: rgba(163, 60, 44, 0.05);
  border-left-color: #a33c2c;
}

.db-left {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.db-label {
  font-size: 12px;
  color: var(--th-text-muted);
}

.db-date {
  font-family: var(--th-font-serif);
  font-size: 16px;
  color: var(--th-primary-deep);
}

.db-stage {
  font-size: 12px;
  color: var(--th-accent);
}

.db-right {
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.is-overdue .db-right {
  color: #a33c2c;
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

.count {
  font-size: 12.5px;
  color: var(--th-text-muted);
  white-space: nowrap;
}

.count b {
  font-family: var(--th-font-serif);
  font-size: 17px;
  color: var(--th-primary);
}

.panel {
  padding: 18px 20px 20px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 5px;
  box-shadow: 0 6px 16px rgba(16, 31, 51, 0.05);
}

.panel-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 12px;
  margin-bottom: 16px;
  border-bottom: 1px solid var(--th-border-soft);
}

.panel-title h3 {
  font-size: 16px;
  color: var(--th-primary-deep);
}

.panel-title p {
  margin: 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.upload-body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 20px;
}

@media (max-width: 900px) {
  .upload-body {
    grid-template-columns: 1fr;
  }
}

.form-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field > span {
  font-size: 12px;
  color: var(--th-text-muted);
}

.drop {
  display: block;
}

.drop-icon {
  font-size: 30px;
  color: var(--th-accent);
}

.drop-text {
  font-size: 13px;
  color: var(--th-text-muted);
}

.drop-text em {
  font-style: normal;
  color: var(--th-primary);
}

.drop-tip {
  margin: 8px 0 0;
  font-size: 11.5px;
  color: var(--th-text-muted);
}

.upload-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.coverage {
  display: grid;
  grid-template-columns: repeat(9, minmax(0, 1fr));
  gap: 8px;
}

@media (max-width: 900px) {
  .coverage {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

.cov {
  padding: 9px 10px;
  background: rgba(29, 51, 84, 0.05);
  border: 1px solid rgba(29, 51, 84, 0.16);
  border-radius: 4px;
}

.cov.is-empty {
  background: #f7f3e9;
  border-color: var(--th-border-soft);
}

.cov-no {
  display: block;
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--th-accent);
}

.cov-name {
  display: block;
  font-size: 12px;
  color: var(--th-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.cov-count {
  display: block;
  margin-top: 2px;
  font-family: var(--th-font-serif);
  font-size: 16px;
  color: var(--th-primary);
}

.cov.is-empty .cov-count {
  color: #a8a196;
}

.cell-main {
  display: block;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-sub {
  display: block;
  font-size: 11.5px;
  color: var(--th-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-pill {
  display: inline-block;
  padding: 2px 8px;
  font-size: 12px;
  color: var(--th-primary);
  background: rgba(29, 51, 84, 0.06);
  border: 1px solid var(--th-border-soft);
  border-radius: 3px;
  white-space: nowrap;
}

.time {
  white-space: nowrap;
  font-size: 12.5px;
  color: var(--th-text-muted);
}

.ver {
  font-family: var(--th-font-serif);
  font-size: 13px;
  color: var(--th-accent);
}

.empty {
  margin: 0;
  padding: 18px 0;
  font-size: 13px;
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
