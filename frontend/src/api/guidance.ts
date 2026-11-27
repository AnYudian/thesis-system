import http, { del, get, post } from './http'

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
    // timeout: 0 —— 视频/压缩包可能几十 MB，不能用全局 15 秒超时
    // 证据可能被重新登记，加时间戳避免拿到浏览器缓存的旧图
    const res = await http.get(`/guidance/${record.id}/evidence?v=${Date.now()}`, {
      responseType: 'blob',
      timeout: 0,
    })
    return URL.createObjectURL(res.data as Blob)
  },

  /** 压缩包 / 代码文件浏览器没法预览，直接按原文件名下载 */
  async downloadEvidence(record: GuidanceRecord) {
    const res = await http.get(`/guidance/${record.id}/evidence?v=${Date.now()}`, {
      responseType: 'blob',
      timeout: 0,
    })
    const url = URL.createObjectURL(res.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = record.evidence_name || `guidance-${record.id}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },

  /**
   * 视频 / PDF / 压缩包：让浏览器直接打开文件地址，由浏览器流式加载。
   *
   * 为什么不走 axios 下载成 blob：几十 MB 的视频要整份下完才能播，
   * 中途任何抖动都会变成"打不开"；直接打开地址可以边下边播、支持拖动进度条。
   * 浏览器新标签带不了 Authorization 头，所以先换一张 3 分钟有效、
   * 只能读这一个文件的票据放进 URL——登录令牌本身不进地址栏。
   */
  async openEvidence(record: GuidanceRecord) {
    // 必须在点击的同一帧里先开空白页：等 await 回来再 window.open，
    // 浏览器会当成"非用户操作"而拦截弹窗
    const win = window.open('about:blank', '_blank')
    try {
      const { ticket } = await post<{ ticket: string; expires_in: number }>(`/guidance/${record.id}/ticket`)
      const url = `/api/guidance/${record.id}/evidence?ticket=${encodeURIComponent(ticket)}&v=${Date.now()}`
      if (win) win.location.href = url
      else window.open(url, '_blank')
    } catch (err) {
      win?.close()
      throw err
    }
  },
}
