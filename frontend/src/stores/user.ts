// ============ 用户状态(Pinia)============
// 全局共享:当前登录用户信息,任何组件都能读
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type UserInfo, setToken, clearToken } from '../api'

export const useUserStore = defineStore('user', () => {
  // 响应式状态:登录用户(初始从 localStorage 恢复,刷新不丢)
  const user = ref<UserInfo | null>(null)
  try {
    const saved = localStorage.getItem('qa_user')
    if (saved) user.value = JSON.parse(saved)
  } catch { /* 损坏的缓存忽略 */ }

  // 登录:存 token + 用户信息
  async function login(username: string, password: string) {
    const res = await api.login(username, password)
    setToken(res.token)
    user.value = res.user
    localStorage.setItem('qa_user', JSON.stringify(res.user))
  }

  // 注册
  async function register(username: string, password: string, department: string) {
    await api.register(username, password, department)
  }

  // 退出:清 token + 用户信息
  function logout() {
    clearToken()
    user.value = null
    localStorage.removeItem('qa_user')
  }

  return { user, login, register, logout }
})
