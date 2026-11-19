import { get, post } from './http'

export interface Reminder {
  id: number
  student_id: number
  sno: string
  student_name: string
  teacher_name: string | null
  stage: string
  content: string
  created_at: string
  read_at: string | null
}

export interface ReminderList {
  items: Reminder[]
  unread: number
}

export const remindersApi = {
  /** 教师催交；不传 content 时后端用默认话术（按当前环节生成） */
  remind: (studentId: number, content?: string) =>
    post<Reminder>(`/reminders/${studentId}`, { content: content?.trim() || null }),

  mine: (unreadOnly = true) => get<ReminderList>('/reminders/mine', { unread_only: unreadOnly }),

  read: (id: number) => post<null>(`/reminders/${id}/read`),
}
