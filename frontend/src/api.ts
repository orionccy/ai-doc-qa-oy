// ============ API 封装:所有后端请求都走这里 ============
// 统一处理:携带 token、错误提示、401 自动跳登录
import { useUserStore } from './stores/user'

// token 的存取:localStorage 持久化(刷新页面不丢登录态)
const TOKEN_KEY = 'qa_token'

export function getToken(): string {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY)
}

// 通用请求:自动带 token;已登录接口 401 时清理登录态并跳转登录页
async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`

  const resp = await fetch(url, { ...options, headers })
  const data = await resp.json().catch(() => ({}))
  const errMsg = (data as any).error || `请求失败(${resp.status})`

  if (resp.status === 401) {
    // 登录/注册接口的 401 = 密码错误/用户名不存在,直接抛给页面显示
    if (url.includes('/api/login') || url.includes('/api/register')) {
      throw new Error(errMsg)
    }
    // 其他接口的 401 = 登录已过期:清 token,跳登录页
    clearToken()
    window.location.href = '/login'
    throw new Error('登录已过期,请重新登录')
  }
  if (!resp.ok) {
    throw new Error(errMsg)
  }
  return data as T
}

// ============ 具体接口 ============
export interface UserInfo {
  id: number
  username: string
  department: string
  role: string
  created_at?: string
}

export const api = {
  // 认证
  login: (username: string, password: string) =>
    request<{ token: string; user: UserInfo }>('/api/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  register: (username: string, password: string, department: string) =>
    request<{ user: UserInfo }>('/api/register', {
      method: 'POST',
      body: JSON.stringify({ username, password, department }),
    }),
  me: () => request<UserInfo>('/api/me'),
  departments: () =>
    request<{ departments: string[] }>('/api/departments'),

  // 用户管理(管理员)
  listUsers: () => request<{ users: UserInfo[] }>('/api/users'),
  deleteUser: (username: string) =>
    request<{ ok: boolean }>(`/api/users/${encodeURIComponent(username)}`, { method: 'DELETE' }),
  resetPassword: (username: string, newPassword: string) =>
    request<{ ok: boolean }>(`/api/users/${encodeURIComponent(username)}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ new_password: newPassword }),
    }),

  // 文档
  listDocs: () => request<{ docs: { name: string; chunk_count: number }[]; chunk_count: number }>('/api/docs'),
  history: () => request<{ messages: { role: string; content: string }[] }>('/api/history'),
  upload: (files: File[]) => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    // 上传是 multipart,不能带 Content-Type(浏览器自动加 boundary)
    const headers: Record<string, string> = {}
    const token = getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
    return fetch('/api/upload', { method: 'POST', body: fd, headers }).then(async (r) => {
      const d = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error((d as any).error || `上传失败(${r.status})`)
      return d
    })
  },
  deleteDoc: (name: string) =>
    request<{ removed: number }>(`/api/docs?name=${encodeURIComponent(name)}`, { method: 'DELETE' }),
}
