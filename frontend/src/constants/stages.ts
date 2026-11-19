/**
 * 毕业设计全流程九节点。
 *
 * code 与后端 Stage 枚举一一对应；label 用后端口径，short 用于空间紧张的地方（流程条、表头）。
 * ai 标记“后期可能接入智能体”的节点：选题、开题、中期、查重、定稿，
 * 只作视觉标注，不影响当前任何业务逻辑。
 */
export interface StageMeta {
  code: string
  label: string
  short: string
  ai: boolean
}

export const STAGES: StageMeta[] = [
  { code: 'TOPIC', label: '选题/双向选择', short: '选题', ai: true },
  { code: 'TASK_BOOK', label: '任务书下达', short: '任务书', ai: false },
  { code: 'PROPOSAL', label: '开题报告/开题答辩', short: '开题', ai: true },
  { code: 'MIDTERM', label: '中期检查', short: '中期检查', ai: true },
  { code: 'PLAGIARISM', label: '查重检测', short: '查重', ai: true },
  { code: 'THESIS', label: '论文定稿', short: '定稿', ai: true },
  { code: 'REVIEW', label: '评阅', short: '评阅', ai: false },
  { code: 'DEFENSE', label: '答辩', short: '答辩', ai: false },
  { code: 'ARCHIVE', label: '归档/评优', short: '归档评优', ai: false },
]

export const STAGE_SHORT: Record<string, string> = Object.fromEntries(
  STAGES.map((s) => [s.code, s.short]),
)
