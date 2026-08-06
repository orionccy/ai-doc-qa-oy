# 📄 AI 文档问答助手 (Python 版)

一个基于 **FastAPI + LangChain** 的 RAG(检索增强生成)文档问答应用:上传文档,自动解析、切分、向量化入库,然后基于文档内容进行流式问答。

## ✨ 功能特性

- 📤 **多格式文档上传**:支持 txt / md / pdf / docx,自动解析
- 🔍 **RAG 检索增强问答**:向量化检索 Top-K 相关片段,回答带来源标注
- ⚡ **流式输出**:打字机效果,边生成边显示
- 📚 **知识库管理**:文档列表、单文档删除、JSON 文件持久化(重启不丢)
- 🛡️ **企业级加固**:
  - 结构化日志(请求中间件 + 业务打点)
  - 全局异常处理 + 超时 + 自动重试
  - 上传大小限制(20MB)、扩展名白名单、文件名清洗、输入校验
- ✅ **CI 流水线**:GitHub Actions 自动跑语法检查 + 单元测试

## 🛠️ 技术栈

| 层 | 技术 |
|---|---|
| Web 框架 | FastAPI + Uvicorn |
| AI 框架 | LangChain (ChatOpenAI / OpenAIEmbeddings / RecursiveCharacterTextSplitter) |
| 对话模型 | DeepSeek (`deepseek-chat`) |
| 向量模型 | 阿里百炼 (`text-embedding-v3`) |
| 存储 | 本地 JSON 文件(极简向量存储,余弦相似度检索) |
| 前端 | 原生 HTML/JS(零框架依赖) |

## 🚀 快速开始

### 1. 环境准备

- Python 3.11+
- DeepSeek API Key(对话)
- 阿里百炼(DashScope)API Key(向量化)

### 2. 安装与配置

```bash
# 创建虚拟环境并安装依赖
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 配置密钥(复制 .env 模板并填入)
cp .env.example .env
# 编辑 .env:
#   DEEPSEEK_API_KEY=sk-xxx
#   DASHSCOPE_API_KEY=sk-xxx
```

### 3. 启动服务

```bash
.venv/bin/uvicorn app.main:app --reload
```

浏览器访问 <http://localhost:8000>

### 4. 使用

1. 上传文档(txt/md/pdf/docx,可多选)
2. 在聊天框提问,AI 基于文档内容回答并标注来源
3. 已入库文档可在列表区管理(删除)

## 📁 项目结构

```
ai-doc-qa-py/
├── app/
│   ├── main.py      # FastAPI 入口:路由、中间件、全局异常处理、安全关卡
│   ├── rag.py       # RAG 核心:向量化、检索、提示词组装、流式生成
│   ├── parse.py     # 文档解析与文本切分(职责分离)
│   ├── storage.py   # 极简向量存储:入库、余弦检索、删除、持久化
│   ├── config.py    # 配置:密钥、模型名、RAG 参数
│   └── static/      # 前端页面(index.html)
├── tests/           # 单元测试(余弦相似度/切分/存储增查删)
├── .github/workflows/ci.yml  # CI 流水线
└── requirements.txt
```

## 🔌 API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 前端页面 |
| POST | `/api/upload` | 上传文档入库(multipart,字段名 `files`) |
| POST | `/api/chat` | 流式问答(JSON: `{"messages":[{"role":"user","content":"问题"}]}`) |
| GET | `/api/docs` | 已入库文档列表 |
| DELETE | `/api/docs?name=xxx` | 删除指定文档 |

## 🧪 测试与 CI

```bash
python -m pytest tests/ -v
```

每次 push / 提 PR,GitHub Actions 自动执行:依赖安装 → 语法检查 → 单元测试。

## 🧠 设计要点

- **模块化**:路由(main)、业务(rag)、解析(parse)、存储(storage)、配置(config)五层分离
- **可测性**:余弦相似度抽为纯函数,存储支持注入文件路径(测试不污染真实数据)
- **安全**:前端限制只是体验,后端校验才是真正的安全边界
- **省钱**:空知识库直接提示,不白调大模型;embedding 按 10 条/批控制

## 📄 License

MIT
