import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { authApi, type UserInfo } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') ?? '')
  const user = ref<UserInfo | null>(null)

  const isLoggedIn = computed(() => Boolean(token.value))
  const role = computed(() => user.value?.role ?? null)
  const displayName = computed(() => user.value?.real_name || user.value?.username || '')

  async function login(username: string, password: string) {
    const result = await authApi.login(username, password)
    token.value = result.access_token
    user.value = result.user
    localStorage.setItem('token', result.access_token)
  }

  async function loadMe() {
    if (!token.value) return
    user.value = await authApi.me()
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  return { token, user, isLoggedIn, role, displayName, login, loadMe, logout }
})
