import http, { del, get } from './http'

export interface Material {
  id: number
  student_id: number
  student_name: string
  sno: string
  stage: string
  title: string
  version: number
  file_name: string
  file_size: number
  content_type: string | null
  note: string | null
  uploader_name: string | null
  created_at: string
}

export interface MaterialPage {
  items: Material[]
  total: number
  page: number
  size: number
}

export interface MaterialQuery {
  page?: number
  size?: number
  stage?: string
  keyword?: string
  student_id?: number
  latest_only?: boolean
}

export interface UploadForm {
  stage: string
  title: string
  note?: string | null
  student_id?: number
}

export const materialsApi = {
  list: (params: MaterialQuery) => get<MaterialPage>('/materials', params as Record<string, unknown>),

  async upload(file: File, form: UploadForm): Promise<Material> {
    const body = new FormData()
    body.append('stage', form.stage)
    body.append('title', form.title)
    if (form.note) body.append('note', form.note)
    if (form.student_id) body.append('student_id', String(form.student_id))
    body.append('file', file)
    // 交给浏览器自动带 multipart boundary，手动设 Content-Type 反而会传坏
    const { data } = await http.post('/materials', body)
    return data.data as Material
  },

  remove: (id: number) => del<null>(`/materials/${id}`),

  /** 下载要走带 token 的请求，不能直接用 <a href>，所以取 blob 再触发保存 */
  async download(item: Material) {
    const res = await http.get(`/materials/${item.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data as Blob)
    const a = document.createElement('a')
    a.href = url
    a.download = item.file_name
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
}
