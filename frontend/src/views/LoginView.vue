<script setup lang="ts">
// ============ 登录/注册页 ============
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'
import { api } from '../api'

const router = useRouter()
const userStore = useUserStore()

// 模式切换:login(登录)/ register(注册)
const mode = ref<'login' | 'register'>('login')
const username = ref('')
const password = ref('')
const department = ref('研发部')
const departments = ref<string[]>(['研发部'])
const errorMsg = ref('')
const loading = ref(false)

onMounted(async () => {
  try {
    const res = await api.departments()
    departments.value = res.departments
    department.value = res.departments[0]
  } catch { /* 拉不到就用默认 */ }
})

async function submit() {
  errorMsg.value = ''
  if (!username.value.trim() || password.value.length < 6) {
    errorMsg.value = '请输入用户名,密码至少 6 位'
    return
  }
  loading.value = true
  try {
    if (mode.value === 'login') {
      await userStore.login(username.value.trim(), password.value)
      // 整页跳转:确保状态干净(SPA 内部 push 有时受路由状态影响)
      window.location.href = '/chat'
    } else {
      await userStore.register(username.value.trim(), password.value, department.value)
      errorMsg.value = '注册成功,请登录'
      mode.value = 'login'
      password.value = ''  // 清空密码,防止误用
    }
  } catch (e: any) {
    errorMsg.value = e.message || '操作失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="card">
      <div class="brand">
        <div class="logo">📄</div>
        <h1>AI 文档问答平台</h1>
        <p class="sub">企业级多租户 RAG 知识库</p>
      </div>

      <!-- 模式切换 -->
      <div class="tabs">
        <button :class="{ active: mode === 'login' }" @click="mode = 'login'">登录</button>
        <button :class="{ active: mode === 'register' }" @click="mode = 'register'">注册</button>
      </div>

      <div class="form">
        <!-- autocomplete:阻止浏览器自动填充上次输入(autofill) -->
        <input v-model="username" placeholder="用户名" autocomplete="off" @keyup.enter="submit" />
        <input v-model="password" type="password" placeholder="密码(至少 6 位)" autocomplete="new-password" @keyup.enter="submit" />
        <select v-if="mode === 'register'" v-model="department">
          <option v-for="d in departments" :key="d" :value="d">{{ d }}</option>
        </select>

        <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

        <button class="submit" :disabled="loading" @click="submit">
          {{ loading ? '处理中...' : mode === 'login' ? '登 录' : '注 册' }}
        </button>
      </div>

      <p class="tip">第一个注册的用户自动成为管理员</p>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  /* 渐变背景:企业级观感 */
  background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 50%, #60a5fa 100%);
  padding: 20px;
}
.card {
  width: 380px;
  background: #fff;
  border-radius: 16px;
  padding: 36px 32px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
}
.brand { text-align: center; margin-bottom: 24px; }
.logo { font-size: 42px; }
.brand h1 { font-size: 22px; margin: 8px 0 4px; color: #1e293b; }
.sub { font-size: 13px; color: #64748b; margin: 0; }
.tabs {
  display: flex;
  background: #f1f5f9;
  border-radius: 10px;
  padding: 4px;
  margin-bottom: 20px;
}
.tabs button {
  flex: 1;
  padding: 8px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #64748b;
}
.tabs button.active { background: #fff; color: #2563eb; font-weight: 600; box-shadow: 0 1px 4px rgba(0,0,0,0.1); }
.form { display: flex; flex-direction: column; gap: 12px; }
.form input, .form select {
  padding: 11px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 15px;
  outline: none;
  transition: border 0.2s;
}
.form input:focus, .form select:focus { border-color: #3b82f6; }
.error { color: #dc2626; font-size: 13px; margin: 0; }
.submit {
  padding: 12px;
  background: #2563eb;
  color: #fff;
  border: none;
  border-radius: 10px;
  font-size: 15px;
  cursor: pointer;
  transition: background 0.2s;
}
.submit:hover { background: #1d4ed8; }
.submit:disabled { background: #93c5fd; cursor: not-allowed; }
.tip { text-align: center; font-size: 12px; color: #94a3b8; margin: 16px 0 0; }
</style>
