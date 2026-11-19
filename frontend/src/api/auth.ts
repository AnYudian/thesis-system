import { get, post } from './http'

export type Role = 'ADMIN' | 'TEACHER' | 'STUDENT'

export interface UserInfo {
  id: number
  username: string
  real_name: string | null
  role: Role
}

export interface LoginResult {
  access_token: string
  token_type: string
  expires_in: number
  user: UserInfo
}

export const authApi = {
  login: (username: string, password: string) =>
    post<LoginResult>('/auth/login', { username, password }),
  me: () => get<UserInfo>('/auth/me'),
  /** 自助改密：必须带原密码，后端会再验一次 */
  changePassword: (oldPassword: string, newPassword: string) =>
    post<null>('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    }),
}
