import { get, put } from './http'

/** 每个环节的截止日期：没设置就是 null */
export type StageDeadlines = Record<string, string | null>

export interface SystemConfig {
  midterm_min_guidance: number
  stage_deadlines: StageDeadlines
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
}
