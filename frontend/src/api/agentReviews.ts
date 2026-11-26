import { get, post } from './http'

export type AgentReviewStatus = 'QUEUED' | 'RUNNING' | 'DONE' | 'FAILED' | 'SKIPPED'

export interface AgentReviewItem {
  material_id: number | null
  stage: string
  material_version: number | null
  file_name: string
  file_size: number
  role: string
  included: boolean
  skip_reason: string | null
}

export interface AgentCheck {
  title?: string
  status?: string
  analysis?: string
  evidence?: { document_id?: string; quote?: string }[]
  rule_id?: string
}

export interface AgentResult {
  summary?: string
  checks?: AgentCheck[]
  problems?: { status?: string; title?: string; description?: string }[]
  suggestions?: { text?: string }[] | string[]
  findings?: { title?: string; outcome?: string; analysis?: string }[]
  knowledge?: { searches?: { query?: string; status?: string; note?: string }[] }
  review_mode?: string
  model?: string
  simulation_only?: boolean
  [key: string]: unknown
}

export interface AgentReview {
  id: number
  student_id: number
  stage: string
  project_id: string
  status: AgentReviewStatus
  external_id: string | null
  external_db_status: string | null
  review_mode: string | null
  model: string | null
  simulation_only: boolean | null
  summary: string | null
  check_total: number
  check_failed: number
  check_pending: number
  error: string | null
  error_code: string | null
  submitted_at: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  items: AgentReviewItem[]
  result?: AgentResult | null
}

export interface PackagePreview {
  student_id: number
  stage: string
  project_id: string
  total_files: number
  missing_stages: string[]
  warnings: string[]
  files: {
    material_id: number
    stage: string
    material_version: number
    file_name: string
    file_size: number
    role: string
    included: boolean
    skip_reason: string | null
  }[]
}

export interface AgentReviewPage {
  items: AgentReview[]
  total: number
  page: number
  size: number
}

export function previewPackage(studentId: number, stage: string) {
  return get<PackagePreview>('/ai/reviews/preview', { student_id: studentId, stage })
}

export function createAgentReview(studentId: number, stage: string) {
  return post<AgentReview>('/ai/reviews', { student_id: studentId, stage })
}

export function getAgentReview(id: number) {
  return get<AgentReview>(`/ai/reviews/${id}`)
}

export function listAgentReviews(params: Record<string, unknown>) {
  return get<AgentReviewPage>('/ai/reviews', params)
}

export const AGENT_STATUS_LABEL: Record<AgentReviewStatus, string> = {
  QUEUED: '排队中',
  RUNNING: '审阅中',
  DONE: '已完成',
  FAILED: '审阅失败',
  SKIPPED: '已跳过',
}
