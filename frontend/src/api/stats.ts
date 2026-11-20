import http, { get } from './http'

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
  materials_total: number
  stages: StageCount[]
  recent_logins: RecentLogin[]
}

export interface ReportSummary {
  students_total: number
  in_progress: number
  archived: number
  teachers_total: number
  materials_total: number
  reviews_total: number
  approved: number
  returned: number
  approve_rate: number | null
  avg_review_hours: number | null
}

export interface StageReportRow {
  stage: string
  label: string
  students: number
  materials: number
  reviews: number
  approved: number
  returned: number
}

export interface TeacherReportRow {
  teacher_id: number | null
  name: string
  students: number
  active: number
  archived: number
  materials: number
  reviews: number
  approve_rate: number | null
  last_reviewed_at: string | null
}

export interface ActivityPoint {
  date: string
  materials: number
  approvals: number
  returns: number
}

export interface GuidanceStats {
  total: number
  meet: number
  online: number
  evidence: number
  students_with_guidance: number
  midterm_total: number
  midterm_required: number
  midterm_reached: number
}

export interface DistributionItem {
  name: string
  count: number
}

export interface DeadlineRow {
  stage: string
  label: string
  deadline: string | null
  students: number
  overdue: number
}

export interface Report {
  summary: ReportSummary
  stages: StageReportRow[]
  teachers: TeacherReportRow[]
  activity: ActivityPoint[]
  guidance: GuidanceStats
  majors: DistributionItem[]
  classes: DistributionItem[]
  grades: DistributionItem[]
  deadlines: DeadlineRow[]
}

export const statsApi = {
  overview: () => get<Overview>('/stats/overview'),
  report: (days = 14) => get<Report>('/stats/report', { days }),
  /** 导出 Excel：后端生成多 Sheet 工作簿，这里只负责把二进制流取回来 */
  async reportWorkbook(days: number): Promise<Blob> {
    const { data } = await http.get<Blob>('/stats/export.xlsx', {
      params: { days },
      responseType: 'blob',
    })
    return data
  },
}
