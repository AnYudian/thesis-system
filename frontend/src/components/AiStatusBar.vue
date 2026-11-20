<script setup lang="ts">
/**
 * AI 可用状态条：教师端、学生端都能一眼看到"现在 AI 开没开、用的是哪个模型"。
 *
 * 只读，不提供开关——开关是管理员的事（参数配置页），这里只负责告知，
 * 避免学生或老师以为"没出意见 = 系统坏了"。
 */
import { onMounted, ref } from 'vue'

import { aiApi, type AiStatus } from '@/api/ai'

const status = ref<AiStatus | null>(null)

onMounted(async () => {
  status.value = await aiApi.status().catch(() => null)
})
</script>

<template>
  <div v-if="status" class="ai-status" :class="status.enabled ? 'is-on' : 'is-off'">
    <span class="dot" />
    <span v-if="status.enabled" class="text">
      AI 预审已开启
      <em v-if="status.mock">· 演示模式（不调用真实模型）</em>
      <em v-else>· 真实模型 {{ status.model }}</em>
      <template v-if="status.daily_limit"> · 今日 {{ status.used_today }} / {{ status.daily_limit }} 次</template>
    </span>
    <span v-else class="text">
      AI 预审已关闭 · 材料照常提交，由指导老师人工审阅
    </span>
  </div>
</template>

<style scoped>
.ai-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px;
  font-size: 11.5px;
  line-height: 1.6;
  border-radius: 3px;
}

.ai-status.is-on {
  color: var(--th-primary-soft);
  background: rgba(44, 74, 115, 0.05);
  border-left: 2px solid var(--th-primary-soft);
}

.ai-status.is-off {
  color: #8a6a2f;
  background: rgba(198, 168, 107, 0.12);
  border-left: 2px solid var(--th-accent);
}

.dot {
  flex: none;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.text em {
  font-style: normal;
  color: inherit;
  opacity: 0.85;
}
</style>
