import { get, patch, post } from './http'

export type AccountRole = 'ADMIN' | 'TEACHER' | 'STUDENT'
export type TeacherType = 'SUPERVISOR' | 'REVIEWER'

export interface Account {
  id: number
  username: string
  real_name: string | null
  role: AccountRole
  is_active: boolean
  created_at: string
  last_login_at: string | null
  teacher_type: TeacherType | null
  college: string | null
  major: string | null
  phone: string | null
  qq: string | null
}

export interface AccountPage {
  items: Account[]
  total: number
  page: number
  size: number
}

export interface AccountQuery {
  page?: number
  size?: number
  keyword?: string
  role?: AccountRole
  teacher_type?: TeacherType
  is_active?: boolean
}

export interface AccountForm {
  username: string
  real_name: string
  role: 'TEACHER' | 'ADMIN'
  teacher_type?: TeacherType
  password?: string | null
  college?: string | null
  major?: string | null
  phone?: string | null
  qq?: string | null
}

export const accountsApi = {
  list: (params: AccountQuery) => get<AccountPage>('/users', params as Record<string, unknown>),
  create: (body: AccountForm) =>
    post<{ user: Account; initial_password: string }>('/users', body),
  update: (
    id: number,
    body: {
      real_name?: string
      is_active?: boolean
      teacher_type?: TeacherType
      college?: string | null
      major?: string | null
      phone?: string | null
      qq?: string | null
    },
  ) => patch<Account>(`/users/${id}`, body),
  /** 重置为统一初始密码，返回值由页面弹窗告知管理员 */
  resetPassword: (id: number) => post<{ password: string }>(`/users/${id}/reset-password`),
  /** 管理员直接设置指定密码（教师忘了密码，或要发一个临时密码时用） */
  setPassword: (id: number, password: string) =>
    post<null>(`/users/${id}/set-password`, { password }),
}
