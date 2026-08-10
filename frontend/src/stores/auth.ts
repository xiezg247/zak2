import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getToken, setToken } from '../api/client'
import { authApi, type User } from '../api/screener'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const ready = ref(false)

  async function bootstrap() {
    if (!getToken()) {
      ready.value = true
      return
    }
    try {
      user.value = await authApi.me()
    } catch {
      setToken(null)
      user.value = null
    } finally {
      ready.value = true
    }
  }

  async function login(username: string, password: string) {
    const resp = await authApi.login(username, password)
    setToken(resp.access_token)
    user.value = resp.user
  }

  function logout() {
    setToken(null)
    user.value = null
  }

  return { user, ready, bootstrap, login, logout }
})
