<script setup lang="ts">
// ============ 主布局:顶栏 + 导航 + 内容区 ============
import { onMounted } from 'vue'
import { useUserStore } from '../stores/user'
import { api } from '../api'

const userStore = useUserStore()

// 进入主界面时,用 token 向后端拉最新用户信息(防止刷新后显示空)
onMounted(async () => {
  if (!userStore.user) {
    try {
      userStore.user = await api.me()
    } catch { /* 401 已由 api 层处理跳转 */ }
  }
})

function logout() {
  userStore.logout()
  window.location.href = '/login'  // 整页跳转,干净退出
}
</script>

<template>
  <div class="layout">
    <!-- 顶部栏:品牌 + 用户信息 + 退出 -->
    <header class="topbar">
      <div class="brand">📄 AI 文档问答</div>
      <div class="right">
        <span class="dept-badge">{{ userStore.user?.department }}</span>
        <span class="username">{{ userStore.user?.username }}</span>
        <span v-if="userStore.user?.role === 'admin'" class="admin-badge">管理员</span>
        <button class="logout" @click="logout">退出</button>
      </div>
    </header>

    <div class="body">
      <!-- 侧边导航 -->
      <nav class="sidebar">
        <router-link to="/chat" class="nav-item">💬 智能问答</router-link>
        <router-link to="/docs" class="nav-item">📚 知识库文档</router-link>
        <!-- 管理员专属入口 -->
        <router-link v-if="userStore.user?.role === 'admin'" to="/users" class="nav-item">👥 用户管理</router-link>
      </nav>

      <!-- 内容区:子路由在这里渲染 -->
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout { min-height: 100vh; display: flex; flex-direction: column; background: #f8fafc; }
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e2e8f0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.brand { font-size: 17px; font-weight: 700; color: #1e293b; }
.right { display: flex; align-items: center; gap: 10px; }
.dept-badge {
  background: #dbeafe; color: #1d4ed8;
  padding: 3px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600;
}
.admin-badge {
  background: #fef3c7; color: #92400e;
  padding: 3px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600;
}
.username { font-size: 14px; color: #334155; }
.logout {
  padding: 6px 14px; border: 1px solid #e2e8f0;
  background: #fff; border-radius: 8px;
  cursor: pointer; font-size: 13px; color: #64748b;
}
.logout:hover { background: #f1f5f9; }
.body { display: flex; flex: 1; }
.sidebar {
  width: 180px; padding: 16px 12px;
  background: #fff; border-right: 1px solid #e2e8f0;
  display: flex; flex-direction: column; gap: 6px;
}
.nav-item {
  padding: 10px 14px; border-radius: 10px;
  text-decoration: none; color: #475569; font-size: 14px;
  transition: all 0.15s;
}
.nav-item:hover { background: #f1f5f9; }
.nav-item.router-link-active { background: #2563eb; color: #fff; font-weight: 600; }
.content { flex: 1; padding: 24px; overflow: auto; }
</style>
