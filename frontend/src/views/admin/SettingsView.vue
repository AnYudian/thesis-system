<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { configApi } from '@/api/config'
import { STAGES } from '@/constants/stages'
import { useConfigStore } from '@/stores/config'
import { formatTime } from '@/utils/format'

const configStore = useConfigStore()

const loading = ref(false)
const saving = ref(false)
const meta = reactive<{ updated_at: string | null; updated_by_name: string | null }>({
  updated_at: null,
  updated_by_name: null,
})

const form = reactive<{ midterm: number; deadlines: Record<string, string | null> }>({
  midterm: 10,
  deadlines: {},
})

// 逾期只做提示，不参与拦截：截止日期是管理口径，放行权仍在指导老师手上
const today = new Date().toISOString().slice(0, 10)
const overdueStages = computed(() =>
  STAGES.filter((s) => {
    const day = form.deadlines[s.code]
    return day && day < today
  }).map((s) => s.short),
)

const configuredCount = computed(
  () => STAGES.filter((s) => form.deadlines[s.code]).length,
)

async function load() {
  loading.value = true
  try {
    const data = await configApi.get()
    form.midterm = data.midterm_min_guidance
    form.deadlines = Object.fromEntries(
      STAGES.map((s) => [s.code, data.stage_deadlines[s.code] ?? null]),
    )
    meta.updated_at = data.updated_at
    meta.updated_by_name = data.updated_by_name
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!Number.isInteger(form.midterm) || form.midterm < 1 || form.midterm > 50) {
    ElMessage.warning('中期最少沟通次数请填 1-50 之间的整数')
    return
  }
  saving.value = true
  try {
    const data = await configApi.update({
      midterm_min_guidance: form.midterm,
      stage_deadlines: form.deadlines,
    })
    meta.updated_at = data.updated_at
    meta.updated_by_name = data.updated_by_name
    // 教师端、学生端读的是同一个 store，保存后立刻刷新，切过去就是新口径
    await configStore.load(true)
    ElMessage.success('参数已保存，各端立刻按新口径显示')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page" v-loading="loading">
    <header class="head">
      <div>
        <p class="eyebrow">SYSTEM SETTINGS</p>
        <h2>参数配置</h2>
        <p class="sub">
          这里设定全系统统一的口径：中期检查要求的最少沟通次数，以及每个环节的截止日期。
          保存后教师端、学生端立刻按新口径显示；截止日期只做提醒，学生仍可补交，放行权在指导老师。
        </p>
      </div>
      <div class="head-right">
        <span v-if="meta.updated_at" class="meta">
          上次修改：{{ formatTime(meta.updated_at) }}
          <template v-if="meta.updated_by_name"> · {{ meta.updated_by_name }}</template>
        </span>
        <el-button type="primary" :loading="saving" @click="save">保存参数</el-button>
      </div>
    </header>

    <section class="card">
      <div class="card-head">
        <h3>审核口径</h3>
        <p>中期检查通过前，指导老师对该生的指导记录必须达到这个次数，否则后端直接拦下。</p>
      </div>
      <div class="field-row">
        <label class="field-label">中期检查最少沟通次数</label>
        <el-input-number v-model="form.midterm" :min="1" :max="50" :step="1" controls-position="right" />
        <span class="field-hint">
          默认 10 次。改小会让已通过的中期不受影响，只对之后的审核生效。
        </span>
      </div>
    </section>

    <section class="card">
      <div class="card-head">
        <h3>环节截止日期</h3>
        <p>
          已设置 {{ configuredCount }} / {{ STAGES.length }} 个环节。留空表示不设截止日期；
          教师端阶段审核、学生端材料页会显示对应日期，逾期只提示不拦截。
        </p>
      </div>

      <div class="deadline-grid">
        <div v-for="(stage, index) in STAGES" :key="stage.code" class="deadline-item">
          <div class="deadline-name">
            <span class="order">{{ String(index + 1).padStart(2, '0') }}</span>
            <span>{{ stage.label }}</span>
            <el-tag v-if="form.deadlines[stage.code] && form.deadlines[stage.code]! < today" size="small" type="danger" effect="plain">
              已过期
            </el-tag>
          </div>
          <div class="deadline-control">
            <el-date-picker
              v-model="form.deadlines[stage.code]"
              type="date"
              value-format="YYYY-MM-DD"
              placeholder="不设截止"
              :clearable="true"
              style="width: 100%"
            />
          </div>
        </div>
      </div>

      <p v-if="overdueStages.length" class="overdue-note">
        以下环节的截止日期已经过去：{{ overdueStages.join('、') }}。如果还在走流程，建议改成新的日期。
      </p>
    </section>

    <section class="card card--muted">
      <h3>口径说明</h3>
      <ul>
        <li>中期检查是唯一有硬门槛的环节：次数不足时「通过」按钮不可用，后端也会返回 422。</li>
        <li>环节截止日期用于提醒与统计，不改变审核流程；学生逾期提交不会自动退回。</li>
        <li>改动会写入操作日志（动作名「修改参数」），谁在什么时候改了什么都能追溯。</li>
      </ul>
    </section>
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
  max-width: 780px;
  margin: 6px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--th-text-muted);
}

.head-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.meta {
  font-size: 12px;
  color: var(--th-text-muted);
}

.card {
  padding: 18px 20px;
  background: var(--th-surface);
  border: 1px solid var(--th-border);
  border-radius: 6px;
}

.card--muted {
  background: rgba(245, 239, 225, 0.35);
}

.card-head h3 {
  margin: 0;
  font-size: 16px;
  color: var(--th-primary-deep);
}

.card-head p {
  margin: 5px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: var(--th-text-muted);
}

.field-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--th-border);
}

.field-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--th-text);
}

.field-hint {
  font-size: 12px;
  color: var(--th-text-muted);
}

.deadline-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 10px 14px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed var(--th-border);
}

.deadline-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border: 1px solid var(--th-border);
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.6);
}

.deadline-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--th-text);
}

.order {
  font-family: var(--th-font-serif);
  font-size: 12px;
  color: var(--th-accent);
}

.deadline-control {
  width: 100%;
}

.overdue-note {
  margin: 14px 0 0;
  padding: 10px 12px;
  font-size: 12.5px;
  color: #8a3b2e;
  background: rgba(138, 59, 46, 0.06);
  border-left: 3px solid #8a3b2e;
}

.card--muted ul {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 12.5px;
  line-height: 1.9;
  color: var(--th-text-muted);
}
</style>
