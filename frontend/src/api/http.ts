import axios, { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

const http = axios.create({ baseURL: '/api', timeout: 15000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiEnvelope<unknown>>) => {
    const status = error.response?.status
    const message =
      error.response?.data?.message ??
      (error.response ? '后端服务暂时不可用，请确认它已启动（8000 端口）' : '无法连接服务器，请检查网络或后端是否已启动')

    if (status === 401) {
      localStorage.removeItem('token')
      // 用事件解耦：拦截器不认识 router，由 main.ts 统一处理跳转
      window.dispatchEvent(new CustomEvent('auth:expired'))
    }

    ElMessage.error(message)
    return Promise.reject(error)
  },
)

export async function get<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const { data } = await http.get<ApiEnvelope<T>>(url, { params })
  return data.data
}

export async function post<T>(url: string, body?: unknown): Promise<T> {
  const { data } = await http.post<ApiEnvelope<T>>(url, body)
  return data.data
}

export default http
