import { del, get, patch, post, put } from './http'

export interface Student {
  id: number
  sno: string
  name: string
  major: string
  class_name: string
  grade: string
  teacher_id: number | null
  teacher_name: string | null
  current_stage: string
  status: string
  username: string | null
  topic_title: string | null
  created_at: string
}

export interface Topic {
  id: number
  title: string
  summary: string | null
  academic_year: string
  updated_at: string
}

export interface StudentDetail extends Student {
  topic: Topic | null
}

export interface StudentPage {
  items: Student[]
  total: number
  page: number
  size: number
}

export interface StudentForm {
  sno?: string
  name: string
  major: string
  class_name: string
  grade: string
  teacher_id: number | null
  current_stage?: string
  create_account?: boolean
}

export interface TopicForm {
  title: string
  summary: string | null
  academic_year: string
}

export interface StudentListQuery {
  page?: number
  size?: number
  keyword?: string
  stage?: string
  status?: string
  teacher_id?: number
}

export const studentsApi = {
  list: (params: StudentListQuery) => get<StudentPage>('/students', params as Record<string, unknown>),
  detail: (id: number) => get<StudentDetail>(`/students/${id}`),
  create: (body: StudentForm) =>
    post<{ student: Student; initial_password: string | null }>('/students', body),
  update: (id: number, body: Partial<StudentForm> & { clear_teacher?: boolean }) =>
    patch<StudentDetail>(`/students/${id}`, body),
  remove: (id: number) => del<null>(`/students/${id}`),
  setTopic: (id: number, body: TopicForm) => put<Topic>(`/students/${id}/topic`, body),
  clearTopic: (id: number) => del<null>(`/students/${id}/topic`),
  me: () => get<StudentDetail | null>('/students/me'),
}

export const teachersApi = {
  list: () => get<{ id: number; username: string; real_name: string | null }[]>('/users/teachers'),
}
