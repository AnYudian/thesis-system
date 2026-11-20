<script setup lang="ts">
/**
 * ECharts 薄封装。
 *
 * 只按需注册用到的图表与组件：全量 import 会让打包体积翻倍，
 * 这个项目只需要柱图、折线、饼图和仪表盘。
 * 尺寸变化走 ResizeObserver，而不是监听 window.resize —— 侧栏收起、
 * 面板缩放都不会触发 window 事件，图表会停在旧宽度。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts/core'
import { BarChart, GaugeChart, LineChart, PieChart } from 'echarts/charts'
import {
  GraphicComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsOption } from 'echarts'

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  GaugeChart,
  GraphicComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  CanvasRenderer,
])

const props = withDefaults(defineProps<{ option: EChartsOption; height?: string }>(), {
  height: '240px',
})

const box = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let observer: ResizeObserver | null = null

onMounted(() => {
  if (!box.value) return
  chart = echarts.init(box.value)
  chart.setOption(props.option)
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(box.value)
})

watch(
  () => props.option,
  (option) => {
    // notMerge：筛选条件变化后旧的 series 可能变少，合并会把残留的柱子画出来
    chart?.setOption(option, true)
  },
  { deep: true },
)

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div ref="box" class="echart" :style="{ height }" />
</template>

<style scoped>
.echart {
  width: 100%;
}
</style>
