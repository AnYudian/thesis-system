import http, { del, get } from './http'

export type GuidanceMethod = 'MEET' | 'ONLINE'

export const METHOD_LABELS: Record<GuidanceMethod, string> = {
  MEET: '面谈',
  ONLINE: '线上',
}

export interface GuidanceRecord {
  id: number
  student_id: number
  student_name: string
  sno: string
  teacher_id: number | null
  teacher_name: string | null
  stage: string
  method: GuidanceMethod
  happened_at: string
  content: string
  evidence_name: string | null
  evidence_size: number | null
  evidence_type: string | null
  created_at: string
}

export interface GuidancePage {
  items: GuidanceRecord[]
  total: number
  page: number
  size: number
}

export interface GuidanceSummary {
  total: number
  by_stage: Record<string, number>
  midterm_count: number
  midterm_required: number
}

export interface GuidanceQuery {
  page?: number
  size?: number
  stage?: string
  student_id?: number
}

export interface GuidanceForm {
  student_id: number
  content: string
  stage: string
  method: GuidanceMethod
  happened_at?: string | null
  file?: File | null
}

export const guidanceApi = {
  list: (params: GuidanceQuery) => get<GuidancePage>('/guidance', params as Record<string, unknown>),

  summary: (studentId: number) =>
    get<GuidanceSummary>('/guidance/summary', { student_id: studentId }),

  /** 证据是可选文件，没有就只传文本；FormData 交给浏览器带 boundary */
  async create(form: GuidanceForm): Promise<GuidanceRecord> {
    const body = new FormData()
    body.append('student_id', String(form.student_id))
    body.append('content', form.content)
    body.append('stage', form.stage)
    body.append('method', form.method)
    if (form.happened_at) body.append('happened_at', form.happened_at)
    if (form.file) body.append('file', form.file)
    const { data } = await http.post('/guidance', body)
    return data.data as GuidanceRecord
  },

  remove: (id: number) => del<null>(`/guidance/${id}`),

  /** 证据接口要带 token，只能先取 blob 再转成浏览器能显示的临时地址 */
  async evidenceUrl(record: GuidanceRecord): Promise<string> {
    const res = await http.get(`/guidance/${record.id}/evidence`, { responseType: 'blob' })
    return URL.createObjectURL(res.data as Blob)
  },

  /** PDF 这类没法直接内嵌预览的，仍然新窗口打开 */
  async openEvidence(record: GuidanceRecord) {
    const url = await guidanceApi.evidenceUrl(record)
    window.open(url, '_blank')
    // 新窗口已经接管这张图，稍后回收即可，避免内存里堆 blob
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  },
}
