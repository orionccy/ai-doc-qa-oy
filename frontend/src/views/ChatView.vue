<script setup lang="ts">
// ============ 智能问答页:流式输出 + 打字机效果 + 历史记录 ============
import { ref, nextTick, onMounted } from 'vue'
import { api, getToken } from '../api'

interface Msg {
  role: 'user' | 'assistant'
  content: string
}

const messages = ref<Msg[]>([])
const input = ref('')
const loading = ref(false)
const msgList = ref<HTMLElement | null>(null)

// 进入页面时加载历史对话(持久化在 SQLite,刷新不丢)
onMounted(async () => {
  try {
    const res = await api.history()
    messages.value = res.messages
    scrollToBottom()
  } catch { /* 历史拉取失败不阻塞页面 */ }
})

// 流式提问:fetch 读流,逐段追加到最后一条助手消息
async function send() {
  const q = input.value.trim()
  if (!q || loading.value) return

  messages.value.push({ role: 'user', content: q })
  input.value = ''
  loading.value = true
  const msg: Msg = { role: 'assistant', content: '' }
  messages.value.push(msg)
  scrollToBottom()

  try {
    const resp = await fetch('/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${getToken()}`,
      },
      body: JSON.stringify({ messages: [{ role: 'user', content: q }] }),
    })
    if (!resp.ok) {
      const d = await resp.json().catch(() => ({}))
      throw new Error(d.error || `请求失败(${resp.status})`)
    }
    // 流式读取:ReadableStream 逐段解码
    const reader = resp.body!.getReader()
    const decoder = new TextDecoder()
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      msg.content += decoder.decode(value, { stream: true })
      scrollToBottom()
    }
  } catch (e: any) {
    msg.content = `❌ ${e.message || '连接失败,请确认后端服务已启动'}`
  } finally {
    loading.value = false
    scrollToBottom()
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (msgList.value) msgList.value.scrollTop = msgList.value.scrollHeight
  })
}
</script>

<template>
  <div class="chat-page">
    <!-- 消息区 -->
    <div ref="msgList" class="msgs">
      <div v-if="messages.length === 0" class="empty">
        <div class="empty-icon">🤖</div>
        <p>我是你的部门知识助手</p>
        <p class="sub">只回答本部门知识库里的内容,提问试试吧</p>
      </div>

      <div v-for="(m, i) in messages" :key="i" class="row" :class="m.role">
        <div class="avatar" :class="m.role">
          {{ m.role === 'user' ? '👤' : '🤖' }}
        </div>
        <div class="bubble">{{ m.content }}</div>
      </div>

      <div v-if="loading" class="typing">正在思考...</div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <textarea
        v-model="input"
        rows="2"
        placeholder="输入问题,Enter 发送,Shift+Enter 换行"
        @keydown.enter.exact.prevent="send"
      />
      <button class="send-btn" :disabled="loading || !input.trim()" @click="send">
        {{ loading ? '...' : '发送 ➤' }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.chat-page { display: flex; flex-direction: column; height: calc(100vh - 104px); }
.msgs {
  flex: 1; overflow-y: auto;
  background: #fff; border: 1px solid #e2e8f0;
  border-radius: 14px; padding: 20px;
}
.empty { text-align: center; margin-top: 15vh; color: #94a3b8; }
.empty-icon { font-size: 56px; }
.empty p { margin: 6px 0; }
.empty .sub { font-size: 13px; }
.row { display: flex; gap: 10px; margin: 14px 0; }
.row.user { flex-direction: row-reverse; }
.avatar {
  width: 34px; height: 34px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 17px; flex-shrink: 0;
  background: #f1f5f9;
}
.avatar.user { background: #dbeafe; }
.bubble {
  max-width: 75%; padding: 11px 16px; border-radius: 14px;
  line-height: 1.65; font-size: 14.5px; white-space: pre-wrap;
  word-break: break-word;
}
.row.assistant .bubble { background: #f8fafc; border: 1px solid #e2e8f0; }
.row.user .bubble { background: #2563eb; color: #fff; }
.typing { color: #94a3b8; font-size: 13px; padding: 8px 44px; }
.input-area { display: flex; gap: 10px; margin-top: 14px; }
.input-area textarea {
  flex: 1; padding: 12px 14px; border: 1px solid #e2e8f0;
  border-radius: 12px; font-size: 14.5px; resize: none; outline: none;
  font-family: inherit;
}
.input-area textarea:focus { border-color: #3b82f6; }
.send-btn {
  padding: 0 26px; background: #2563eb; color: #fff;
  border: none; border-radius: 12px; font-size: 15px;
  cursor: pointer; transition: background 0.15s;
}
.send-btn:hover:not(:disabled) { background: #1d4ed8; }
.send-btn:disabled { background: #93c5fd; cursor: not-allowed; }
</style>
