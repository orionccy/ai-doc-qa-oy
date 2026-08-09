<script setup lang="ts">
// ============ 知识库文档管理页:上传 / 列表 / 删除 ============
import { ref, onMounted } from 'vue'
import { api } from '../api'

interface DocItem { name: string; chunk_count: number }

const docs = ref<DocItem[]>([])
const totalChunks = ref(0)
const uploading = ref(false)
const msg = ref('')
const msgType = ref<'ok' | 'err'>('ok')

// 加载文档列表
async function loadDocs() {
  const res = await api.listDocs()
  docs.value = res.docs
  totalChunks.value = res.chunk_count
}

// 上传(支持多选)
async function onUpload(e: Event) {
  const files = (e.target as HTMLInputElement).files
  if (!files || files.length === 0) return
  uploading.value = true
  msg.value = ''
  try {
    const res = await api.upload(Array.from(files))
    showMsg(`✅ 成功入库 ${res.added} 个片段`, 'ok')
    loadDocs()
  } catch (err: any) {
    showMsg(`❌ ${err.message}`, 'err')
  } finally {
    uploading.value = false
    ;(e.target as HTMLInputElement).value = ''  // 清空 input,允许重复选同一文件
  }
}

// 删除
async function removeDoc(name: string) {
  if (!confirm(`确定删除「${name}」吗?`)) return
  try {
    await api.deleteDoc(name)
    showMsg(`🗑️ 已删除「${name}」`, 'ok')
    loadDocs()
  } catch (err: any) {
    showMsg(`❌ ${err.message}`, 'err')
  }
}

function showMsg(text: string, type: 'ok' | 'err') {
  msg.value = text
  msgType.value = type
  setTimeout(() => (msg.value = ''), 4000)
}

onMounted(loadDocs)
</script>

<template>
  <div class="docs-page">
    <div class="head">
      <div>
        <h2>📚 知识库文档</h2>
        <p class="sub">共 {{ docs.length }} 个文档 · {{ totalChunks }} 个片段(仅本部门可见)</p>
      </div>

      <!-- 上传按钮:隐藏原生 input,用美化按钮触发 -->
      <label class="upload-btn">
        {{ uploading ? '上传中...' : '⬆ 上传文档' }}
        <input type="file" multiple accept=".txt,.md,.pdf,.docx" hidden @change="onUpload" />
      </label>
    </div>

    <p v-if="msg" class="msg" :class="msgType">{{ msg }}</p>

    <!-- 文档列表 -->
    <div v-if="docs.length === 0" class="empty">
      还没有文档,点击右上角上传 📄
    </div>
    <div v-else class="grid">
      <div v-for="d in docs" :key="d.name" class="doc-card">
        <div class="doc-icon">📄</div>
        <div class="doc-info">
          <div class="doc-name" :title="d.name">{{ d.name }}</div>
          <div class="doc-meta">{{ d.chunk_count }} 个片段</div>
        </div>
        <button class="del-btn" @click="removeDoc(d.name)">删除</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.docs-page { max-width: 860px; margin: 0 auto; }
.head {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 20px;
}
h2 { margin: 0; font-size: 20px; color: #1e293b; }
.sub { margin: 4px 0 0; font-size: 13px; color: #64748b; }
.upload-btn {
  display: inline-block; padding: 10px 20px;
  background: #2563eb; color: #fff; border-radius: 10px;
  font-size: 14px; cursor: pointer; transition: background 0.15s;
}
.upload-btn:hover { background: #1d4ed8; }
.msg { padding: 10px 14px; border-radius: 10px; font-size: 14px; margin: 0 0 14px; }
.msg.ok { background: #dcfce7; color: #166534; }
.msg.err { background: #fee2e2; color: #991b1b; }
.empty {
  text-align: center; padding: 60px 0; color: #94a3b8;
  background: #fff; border-radius: 14px; border: 1px dashed #cbd5e1;
}
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; }
.doc-card {
  display: flex; align-items: center; gap: 12px;
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  padding: 14px 16px; transition: box-shadow 0.15s;
}
.doc-card:hover { box-shadow: 0 4px 14px rgba(0,0,0,0.08); }
.doc-icon { font-size: 26px; }
.doc-info { flex: 1; min-width: 0; }
.doc-name {
  font-size: 14px; color: #1e293b; font-weight: 500;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.doc-meta { font-size: 12px; color: #94a3b8; margin-top: 3px; }
.del-btn {
  padding: 5px 12px; border: 1px solid #fecaca; background: #fff;
  color: #dc2626; border-radius: 8px; font-size: 12px; cursor: pointer;
}
.del-btn:hover { background: #fef2f2; }
</style>
