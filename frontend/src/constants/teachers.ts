/**
 * 教师的两类身份。
 *
 * 学校只说了有「指导老师」「另一个老师」两种，具体叫法还没确认，
 * 所以中文文案只写在这里和后端 TEACHER_TYPE_LABELS：确认后两处一起改，
 * 代码值（SUPERVISOR / REVIEWER）和数据库数据都不用动。
 */
export type TeacherType = 'SUPERVISOR' | 'REVIEWER'

export interface TeacherTypeMeta {
  value: TeacherType
  label: string
  hint: string
}

export const TEACHER_TYPES: TeacherTypeMeta[] = [
  {
    value: 'SUPERVISOR',
    label: '指导教师',
    hint: '带学生、做阶段审核、登记指导记录',
  },
  {
    value: 'REVIEWER',
    label: '评阅教师',
    hint: '不带学生，评阅任务等流程确定后开放',
  },
]

export const TEACHER_TYPE_LABEL: Record<TeacherType, string> = {
  SUPERVISOR: '指导教师',
  REVIEWER: '评阅教师',
}

export function teacherTypeLabel(value: string | null | undefined): string {
  return (value && TEACHER_TYPE_LABEL[value as TeacherType]) || '教师'
}
