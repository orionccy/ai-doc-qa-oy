// ============ 路由配置 ============
// 两个页面:登录页 + 主应用(问答/文档管理)
import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../api'

const routes = [
  { path: '/login', name: 'login', component: () => import('../views/LoginView.vue') },
  {
    path: '/',
    component: () => import('../views/HomeLayout.vue'),
    // 子路由:主应用内部的两个页面
    children: [
      { path: '', redirect: '/chat' },
      { path: 'chat', name: 'chat', component: () => import('../views/ChatView.vue') },
      { path: 'docs', name: 'docs', component: () => import('../views/DocsView.vue') },
      { path: 'users', name: 'users', component: () => import('../views/UsersView.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// ============ 路由守卫:未登录一律踢回登录页 ============
// 每次跳转前检查:没有 token 就拦截
router.beforeEach((to) => {
  const isLoggedIn = !!getToken()
  if (!isLoggedIn && to.name !== 'login') {
    return { name: 'login' }
  }
  if (isLoggedIn && to.name === 'login') {
    return { name: 'chat' }  // 已登录还去登录页?送回主界面
  }
  return true
})

export default router
