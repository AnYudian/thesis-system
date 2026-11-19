/**
 * 教师的两类身份。
 *
 * 学校已确认是「指导老师」「就业老师」两种。中文文案只写在这里和后端
 * TEACHER_TYPE_LABELS：再改叫法时两处一起改，代码值（SUPERVISOR / REVIEWER）
 * 和数据库数据不用动。就业老师目前在本系统没有审核任务，只占身份位。
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
    label: '就业老师',
    hint: '不带学生，目前在本系统不承担审核任务',
  },
]

export const TEACHER_TYPE_LABEL: Record<TeacherType, string> = {
  SUPERVISOR: '指导教师',
  REVIEWER: '就业老师',
}

export function teacherTypeLabel(value: string | null | undefined): string {
  return (value && TEACHER_TYPE_LABEL[value as TeacherType]) || '教师'
}
