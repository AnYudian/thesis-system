import http, { del, get, patch, post, put } from './http'

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

export interface TeacherBrief {
  id: number
  username: string
  real_name: string | null
  college: string | null
  major: string | null
  phone: string | null
  email: string | null
}

export interface StudentDetail extends Student {
  topic: Topic | null
  teacher: TeacherBrief | null
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

export interface ImportIssue {
  line: number
  content: string
  reason: string
}

export interface ImportResult {
  created: number
  skipped: number
  errors: ImportIssue[]
  initial_password: string | null
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
  /** 批量导入：文本原样上传，后端按行校验；能建的先建，错误的行带原因返回 */
  importCsv: (text: string, createAccount: boolean) =>
    post<ImportResult>('/students/import', { text, create_account: createAccount }),

  /** Excel 导入：交给浏览器带 multipart 边界，后端用 openpyxl 解析 */
  async importFile(file: File, createAccount: boolean): Promise<ImportResult> {
    const body = new FormData()
    body.append('file', file)
    body.append('create_account', String(createAccount))
    const { data } = await http.post('/students/import/file', body)
    return data.data as ImportResult
  },

  assignTeacher: (studentIds: number[], teacherId: number) =>
    post<{ updated: number; teacher_name: string }>('/students/assign-teacher', {
      student_ids: studentIds,
      teacher_id: teacherId,
    }),
}

export const teachersApi = {
  list: () => get<TeacherBrief[]>('/users/teachers'),
}
