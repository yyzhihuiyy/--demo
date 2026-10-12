import { ref } from 'vue'
import { api, mutation, tokenStorage } from './api'
import type { LoginResponse, User } from './contracts'

const user = ref<User | null>(null)
let initialized = false
let pending: Promise<void> | null = null

window.addEventListener('auth-expired', () => { user.value = null; initialized = true })

export function useAuth() {
  async function restore() {
    if (initialized) return
    if (!pending) pending = (async () => {
      if (tokenStorage.get()) user.value = await api<User>('/auth/me')
      initialized = true
    })().finally(() => { pending = null })
    await pending
  }

  async function login(username: string, password: string) {
    const result = await mutation<LoginResponse>('/auth/login', { username, password })
    tokenStorage.set(result.token)
    user.value = result.user
    initialized = true
  }

  function logout() { tokenStorage.clear(); user.value = null; initialized = true }
  return { user, restore, login, logout }
}
