import { get } from './http'

export interface AuditLog {
  id: number
  user_id: number | null
  username: string | null
  real_name: string | null
  role: 'ADMIN' | 'TEACHER' | 'STUDENT' | null
  action: string
  target_type: string | null
  target_id: string | null
  detail: Record<string, unknown> | null
  created_at: string
}

export interface LogPage {
  items: AuditLog[]
  total: number
  page: number
  size: number
}

export interface LogQuery {
  page?: number
  size?: number
  action?: string
  keyword?: string
  target_type?: string
}

export const logsApi = {
  list: (params: LogQuery) => get<LogPage>('/logs', params as Record<string, unknown>),
}
