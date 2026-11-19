import { get, post } from './http'

export type ReviewAction = 'APPROVE' | 'RETURN'

export interface PendingItem {
  student_id: number
  sno: string
  name: string
  teacher_name: string | null
  stage: string
  material_count: number
  latest_material_at: string | null
  latest_version: number | null
  last_action: ReviewAction | null
  last_comment: string | null
  last_reviewed_at: string | null
  // 当前环节的指导记录数 / 要求次数（中期为 10，其余为 0）
  guidance_count: number
  guidance_required: number
  // 最近一次催交时间；没有催过为 null
  last_reminded_at: string | null
}

export interface StageReview {
  id: number
  student_id: number
  student_name: string
  sno: string
  teacher_name: string | null
  stage: string
  action: ReviewAction
  from_stage: string
  to_stage: string
  material_version: number | null
  comment: string | null
  reviewer_name: string | null
  created_at: string
}

export interface ReviewPage {
  items: StageReview[]
  total: number
  page: number
  size: number
}

export interface ReviewResult {
  review: StageReview
  current_stage: string
  status: string
}

export interface ReviewQuery {
  page?: number
  size?: number
  stage?: string
  keyword?: string
  action?: ReviewAction
  student_id?: number
  teacher_id?: number
}

/** 通过/退回弹窗需要的目标信息，列表和详情页共用 */
export interface ReviewTarget {
  student_id: number
  name: string
  sno: string
  stage: string
}

export interface PendingQuery {
  stage?: string
  keyword?: string
  teacher_id?: number
}

export const reviewsApi = {
  pending: (params?: PendingQuery) => get<PendingItem[]>('/reviews/pending', params as Record<string, unknown>),

  list: (params?: ReviewQuery) => get<ReviewPage>('/reviews', params as Record<string, unknown>),

  /** 通过 / 退回。退回时后端会再校验一次 comment 非空，前端校验只是少跑一趟网络 */
  decide: (studentId: number, action: ReviewAction, comment?: string) =>
    post<ReviewResult>(`/reviews/${studentId}`, { action, comment: comment?.trim() || null }),
}
