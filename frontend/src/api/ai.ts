import { get, post } from './http'

export type AiIssueLevel = 'MAJOR' | 'MINOR' | 'INFO'

export interface AiDimension {
  key: string
  label: string
  score: number
  max_score: number
  comment: string | null
}

export interface AiIssue {
  level: AiIssueLevel
  title: string
  quote: string | null
  suggestion: string | null
}

export interface AiResult {
  score: number
  completion: number
  summary: string
  dimensions: AiDimension[]
  issues: AiIssue[]
  suggestions: string[]
}

export interface AiRun {
  id: number
  material_id: number
  student_id: number
  student_name: string | null
  sno: string | null
  stage: string
  material_version: number
  material_title: string | null
  file_name: string | null
  status: 'QUEUED' | 'RUNNING' | 'DONE' | 'FAILED' | 'SKIPPED'
  status_label: string
  provider: string
  model: string
  prompt_version: string
  score: number | null
  completion: number | null
  summary: string | null
  result: AiResult | null
  error: string | null
  tokens_input: number | null
  tokens_output: number | null
  latency_ms: number | null
  attempts: number
  trigger: 'UPLOAD' | 'MANUAL'
  triggered_by_name: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface AiStatus {
  enabled: boolean
  provider: string
  model: string
  mock: boolean
  has_key: boolean
  daily_limit: number
  used_today: number
  stages: string[]
}

export interface AiRunPage {
  items: AiRun[]
  total: number
  page: number
  size: number
}

export const aiApi = {
  status: () => get<AiStatus>('/ai/status'),
  // 学生不传 studentId：后端按登录身份收敛到本人，避免前端越权
  runs: (params: {
    page?: number
    size?: number
    student_id?: number
    material_id?: number
    stage?: string
    status?: string
  }) => get<AiRunPage>('/ai/runs', params),
  rerun: (materialId: number) => post<AiRun>('/ai/runs', { material_id: materialId }),
}
