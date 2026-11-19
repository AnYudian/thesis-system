import { get } from './http'

export interface StageCount {
  stage: string
  label: string
  count: number
  ai_capable: boolean
}

export interface RecentLogin {
  id: number
  username: string
  real_name: string | null
  role: string
  created_at: string
}

export interface Overview {
  students_total: number
  teachers_total: number
  in_progress: number
  archived: number
  stages: StageCount[]
  recent_logins: RecentLogin[]
}

export const statsApi = {
  overview: () => get<Overview>('/stats/overview'),
}
