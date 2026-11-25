import { get, put } from './http'

/** 每个环节的截止日期：没设置就是 null */
export type StageDeadlines = Record<string, string | null>

export interface SystemConfig {
  midterm_min_guidance: number
  stage_deadlines: StageDeadlines
  ai_enabled: boolean
  /** 每日预审次数上限，0 表示不限 */
  ai_daily_limit: number
  updated_at: string | null
  updated_by_name: string | null
}

/** 两项都可选：只提交改过的那个，避免调次数时顺手改掉开关状态 */
export interface AiConfigForm {
  enabled?: boolean
  daily_limit?: number
}

export interface SystemConfigForm {
  midterm_min_guidance: number
  stage_deadlines: StageDeadlines
}

export const configApi = {
  get: () => get<SystemConfig>('/config'),
  update: (body: SystemConfigForm) => put<SystemConfig>('/config', body),
  // 单独的 AI 配置接口：参数表单保存时不会顺手改掉管理员刚关掉的 AI
  updateAi: (body: AiConfigForm) => put<SystemConfig>('/config/ai', body),
}
