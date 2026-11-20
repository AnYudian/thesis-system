/**
 * 审计动作名与中文口径。
 *
 * 后端存英文常量（LOGIN / STAGE_APPROVE…），翻译放前端：
 * 改文案不用动数据库里的历史记录。
 */
export type ActionTone = 'ok' | 'warn' | 'bad' | 'muted'

export interface ActionMeta {
  value: string
  label: string
  tone: ActionTone
}

export const ACTIONS: ActionMeta[] = [
  { value: 'LOGIN', label: '登录', tone: 'muted' },
  { value: 'ACCOUNT_CREATE', label: '新建账号', tone: 'ok' },
  { value: 'ACCOUNT_UPDATE', label: '修改账号', tone: 'warn' },
  { value: 'ACCOUNT_RESET_PASSWORD', label: '重置密码', tone: 'warn' },
  { value: 'ACCOUNT_SET_PASSWORD', label: '设置密码', tone: 'warn' },
  { value: 'PASSWORD_CHANGE', label: '修改密码', tone: 'warn' },
  { value: 'STUDENT_CREATE', label: '学生建档', tone: 'ok' },
  { value: 'STUDENT_IMPORT', label: '批量导入', tone: 'ok' },
  { value: 'STUDENT_UPDATE', label: '修改学生', tone: 'warn' },
  { value: 'STUDENT_ASSIGN_TEACHER', label: '指派导师', tone: 'warn' },
  { value: 'STUDENT_DELETE', label: '删除学生', tone: 'bad' },
  { value: 'TOPIC_UPDATE', label: '设置课题', tone: 'warn' },
  { value: 'TOPIC_DELETE', label: '清除课题', tone: 'bad' },
  { value: 'MATERIAL_UPLOAD', label: '上传材料', tone: 'ok' },
  { value: 'MATERIAL_DELETE', label: '删除材料', tone: 'bad' },
  { value: 'GUIDANCE_CREATE', label: '指导登记', tone: 'ok' },
  { value: 'GUIDANCE_DELETE', label: '删除指导', tone: 'bad' },
  { value: 'STAGE_APPROVE', label: '审核通过', tone: 'ok' },
  { value: 'STAGE_RETURN', label: '审核退回', tone: 'bad' },
  { value: 'REMIND', label: '催交材料', tone: 'warn' },
  { value: 'CONFIG_UPDATE', label: '修改参数', tone: 'warn' },
]

export const ACTION_META: Record<string, ActionMeta> = Object.fromEntries(
  ACTIONS.map((a) => [a.value, a]),
)

export const ACTION_LABEL: Record<string, string> = Object.fromEntries(
  ACTIONS.map((a) => [a.value, a.label]),
)

/** 详情里的英文键转中文，日志页直接读，不用一处一处写映射 */
export const DETAIL_LABELS: Record<string, string> = {
  sno: '学号',
  name: '姓名',
  title: '题目',
  stage: '环节',
  to_stage: '去向',
  comment: '意见',
  version: '版本',
  material_id: '材料',
  record_id: '记录',
  has_evidence: '附证据',
  method: '方式',
  username: '账号',
  is_active: '启用',
  was_active: '原状态',
  fields: '改动字段',
  created: '成功',
  skipped: '跳过',
  role: '角色',
  enabled: '启用',
  midterm_min_guidance: '中期最少指导次数',
  stage_deadlines: '环节截止日期',
}

/** 枚举值也要翻译，否则详情里会冒出 MEET / true 这种英文 */
export const DETAIL_VALUES: Record<string, Record<string, string>> = {
  method: { MEET: '面谈', ONLINE: '线上' },
}
