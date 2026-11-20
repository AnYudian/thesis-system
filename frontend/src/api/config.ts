import { get, put } from './http'

/** 每个环节的截止日期：没设置就是 null */
export type StageDeadlines = Record<string, string | null>

export interface SystemConfig {
  midterm_min_guidance: number
  stage_deadlines: StageDeadlines
  ai_enabled: boolean
  updated_at: string | null
  updated_by_name: string | null
}

export interface SystemConfigForm {
  midterm_min_guidance: number
  stage_deadlines: StageDeadlines
}

export const configApi = {
  get: () => get<SystemConfig>('/config'),
  update: (body: SystemConfigForm) => put<SystemConfig>('/config', body),
  // 单独一个开关接口：参数表单保存时不会顺手改掉管理员刚关掉的 AI
  toggleAi: (enabled: boolean) => put<SystemConfig>('/config/ai', { enabled }),
}
