/**
 * 系统参数（中期最少沟通次数、各环节截止日期）。
 *
 * 教师端、学生端只读：多页面都要显示"中期要几次""本环节截止哪天"，
 * 放一个 store 里缓存一次，切页面不用反复请求；管理员保存后调 refresh() 更新。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { configApi, type StageDeadlines } from '@/api/config'

export const useConfigStore = defineStore('config', () => {
  const midtermMin = ref(10)
  const deadlines = ref<StageDeadlines>({})
  // AI 总开关：管理员在参数配置页改，教师端/学生端读同一份，用于提示"AI 是否可用"
  const aiEnabled = ref(false)
  const loaded = ref(false)
  const loading = ref(false)

  async function load(force = false) {
    if (loaded.value && !force) return
    if (loading.value) return
    loading.value = true
    try {
      const data = await configApi.get()
      midtermMin.value = data.midterm_min_guidance
      deadlines.value = data.stage_deadlines
      aiEnabled.value = data.ai_enabled
      loaded.value = true
    } finally {
      loading.value = false
    }
  }

  function deadlineOf(stage: string | null | undefined): string | null {
    if (!stage) return null
    return deadlines.value[stage] ?? null
  }

  /** 截止日期差几天：负数表示已过，0 表示就是今天 */
  function daysLeft(stage: string | null | undefined): number | null {
    const text = deadlineOf(stage)
    if (!text) return null
    const end = new Date(`${text}T23:59:59`)
    const diff = end.getTime() - Date.now()
    return Math.floor(diff / 86_400_000)
  }

  const today = computed(() => new Date().toISOString().slice(0, 10))

  return { midtermMin, deadlines, aiEnabled, loaded, load, deadlineOf, daysLeft, today }
})
