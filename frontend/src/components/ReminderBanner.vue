<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { remindersApi, type Reminder } from '@/api/reminders'
import { STAGES } from '@/constants/stages'
import { formatTime } from '@/utils/format'

// 学生工作台和材料页共用：教师点了「催交」才会出现，点「我知道了」即已读。
// 每个页面各自拉一次未读，学生从哪个入口进来都能看到，不会只挂在一个页面。

const items = ref<Reminder[]>([])
const loading = ref(false)

const stageLabel = (code: string) => STAGES.find((s) => s.code === code)?.label ?? code

async function load() {
  loading.value = true
  try {
    const data = await remindersApi.mine(true)
    items.value = data.items
  } catch {
    // 提醒属于辅助信息，接口异常不打断学生提交材料
  } finally {
    loading.value = false
  }
}

async function dismiss(reminder: Reminder) {
  await remindersApi.read(reminder.id)
  items.value = items.value.filter((r) => r.id !== reminder.id)
  ElMessage.success('已标记为已读')
}

onMounted(load)
</script>

<template>
  <section v-if="items.length" class="reminder-box">
    <header class="reminder-head">
      <span class="reminder-title">教师催交</span>
      <span class="reminder-count">{{ items.length }} 条未读</span>
    </header>
    <ul class="reminder-list">
      <li v-for="r in items" :key="r.id" class="reminder-item">
        <div class="reminder-main">
          <p class="reminder-line">
            <b>{{ r.teacher_name || '指导教师' }}</b>
            提醒你提交「{{ stageLabel(r.stage) }}」环节材料
          </p>
          <p class="reminder-content">{{ r.content }}</p>
          <span class="reminder-time">{{ formatTime(r.created_at) }}</span>
        </div>
        <el-button size="small" plain @click="dismiss(r)">我知道了</el-button>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.reminder-box {
  padding: 14px 18px 16px;
  background: rgba(198, 168, 107, 0.1);
  border: 1px solid rgba(198, 168, 107, 0.4);
  border-left: 4px solid var(--th-accent);
  border-radius: 5px;
}

.reminder-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  padding-bottom: 8px;
  border-bottom: 1px dashed rgba(138, 106, 37, 0.3);
}

.reminder-title {
  font-family: var(--th-font-serif);
  font-size: 14px;
  color: #7a5d20;
}

.reminder-count {
  font-size: 12px;
  color: #8a6a25;
}

.reminder-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.reminder-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 0;
}

.reminder-item + .reminder-item {
  border-top: 1px dashed rgba(138, 106, 37, 0.2);
}

.reminder-main {
  flex: 1;
  min-width: 0;
}

.reminder-line {
  margin: 0;
  font-size: 13px;
  color: var(--th-primary-deep);
}

.reminder-content {
  margin: 4px 0 0;
  font-size: 12.5px;
  line-height: 1.7;
  color: #6d5a2e;
}

.reminder-time {
  display: block;
  margin-top: 2px;
  font-size: 11.5px;
  color: #a29a8b;
}
</style>
