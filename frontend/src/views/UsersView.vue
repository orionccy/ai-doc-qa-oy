<script setup lang="ts">
// ============ 用户管理页(仅管理员可见)============
import { ref, onMounted } from 'vue'
import { api, type UserInfo } from '../api'

const users = ref<UserInfo[]>([])
const msg = ref('')
const msgType = ref<'ok' | 'err'>('ok')
const resetTarget = ref('')
const newPassword = ref('')
const showResetDialog = ref(false)

async function loadUsers() {
  const res = await api.listUsers()
  users.value = res.users
}

async function removeUser(u: UserInfo) {
  if (!confirm(`确定删除用户「${u.username}」吗?其上传的文档也会被清理`)) return
  try {
    await api.deleteUser(u.username)
    showMsg(`✅ 已删除用户 ${u.username}`, 'ok')
    loadUsers()
  } catch (e: any) {
    showMsg(`❌ ${e.message}`, 'err')
  }
}

// 打开重置密码弹窗
function openReset(u: UserInfo) {
  resetTarget.value = u.username
  newPassword.value = ''
  showResetDialog.value = true
}

async function doReset() {
  if (newPassword.value.length < 6) {
    showMsg('❌ 新密码至少 6 位', 'err')
    return
  }
  try {
    await api.resetPassword(resetTarget.value, newPassword.value)
    showMsg(`✅ 已重置 ${resetTarget.value} 的密码`, 'ok')
    showResetDialog.value = false
  } catch (e: any) {
    showMsg(`❌ ${e.message}`, 'err')
  }
}

function showMsg(text: string, type: 'ok' | 'err') {
  msg.value = text
  msgType.value = type
  setTimeout(() => (msg.value = ''), 4000)
}

onMounted(loadUsers)
</script>

<template>
  <div class="users-page">
    <div class="head">
      <div>
        <h2>👥 用户管理</h2>
        <p class="sub">共 {{ users.length }} 个用户</p>
      </div>
    </div>

    <p v-if="msg" class="msg" :class="msgType">{{ msg }}</p>

    <div class="table">
      <div class="thead">
        <span>ID</span><span>用户名</span><span>部门</span><span>角色</span><span>注册时间</span><span>操作</span>
      </div>
      <div v-for="u in users" :key="u.id" class="trow">
        <span>{{ u.id }}</span>
        <span class="uname">{{ u.username }}</span>
        <span><span class="dept">{{ u.department }}</span></span>
        <span>
          <span class="role" :class="u.role">{{ u.role === 'admin' ? '管理员' : '用户' }}</span>
        </span>
        <span class="time">{{ u.created_at }}</span>
        <span class="ops">
          <button class="btn-reset" @click="openReset(u)">重置密码</button>
          <button class="btn-del" @click="removeUser(u)">删除</button>
        </span>
      </div>
    </div>

    <!-- 重置密码弹窗 -->
    <div v-if="showResetDialog" class="mask" @click.self="showResetDialog = false">
      <div class="dialog">
        <h3>重置密码:{{ resetTarget }}</h3>
        <input v-model="newPassword" type="text" placeholder="新密码(至少 6 位)" @keyup.enter="doReset" />
        <div class="btns">
          <button class="cancel" @click="showResetDialog = false">取消</button>
          <button class="ok" @click="doReset">确认重置</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.users-page { max-width: 900px; margin: 0 auto; }
.head { margin-bottom: 18px; }
h2 { margin: 0; font-size: 20px; color: #1e293b; }
.sub { margin: 4px 0 0; font-size: 13px; color: #64748b; }
.msg { padding: 10px 14px; border-radius: 10px; font-size: 14px; margin: 0 0 14px; }
.msg.ok { background: #dcfce7; color: #166534; }
.msg.err { background: #fee2e2; color: #991b1b; }
.table {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden;
}
.thead, .trow {
  display: grid; grid-template-columns: 50px 1.2fr 1fr 0.8fr 1.4fr 1.2fr;
  align-items: center; padding: 12px 16px; font-size: 13.5px;
}
.thead { background: #f8fafc; color: #64748b; font-weight: 600; border-bottom: 1px solid #e2e8f0; }
.trow { border-bottom: 1px solid #f1f5f9; color: #334155; }
.trow:last-child { border-bottom: none; }
.trow:hover { background: #f8fafc; }
.uname { font-weight: 600; }
.dept { background: #dbeafe; color: #1d4ed8; padding: 2px 10px; border-radius: 999px; font-size: 12px; }
.role { padding: 2px 10px; border-radius: 999px; font-size: 12px; }
.role.admin { background: #fef3c7; color: #92400e; }
.role.user { background: #f1f5f9; color: #475569; }
.time { color: #94a3b8; font-size: 12.5px; }
.ops { display: flex; gap: 6px; }
.btn-reset, .btn-del {
  padding: 4px 10px; border-radius: 7px; font-size: 12px; cursor: pointer; border: 1px solid;
}
.btn-reset { border-color: #bfdbfe; color: #1d4ed8; background: #fff; }
.btn-reset:hover { background: #eff6ff; }
.btn-del { border-color: #fecaca; color: #dc2626; background: #fff; }
.btn-del:hover { background: #fef2f2; }
.mask {
  position: fixed; inset: 0; background: rgba(0,0,0,0.4);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.dialog {
  background: #fff; border-radius: 14px; padding: 24px; width: 340px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.dialog h3 { margin: 0 0 14px; font-size: 16px; }
.dialog input {
  width: 100%; padding: 10px 12px; border: 1px solid #e2e8f0;
  border-radius: 8px; font-size: 14px; outline: none;
}
.dialog input:focus { border-color: #3b82f6; }
.btns { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.btns button { padding: 8px 18px; border-radius: 8px; font-size: 13px; cursor: pointer; border: none; }
.cancel { background: #f1f5f9; color: #475569; }
.ok { background: #2563eb; color: #fff; }
.ok:hover { background: #1d4ed8; }
</style>
