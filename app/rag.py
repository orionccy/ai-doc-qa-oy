"""RAG(检索增强生成)核心模块:LangChain 组件封装,是整个应用的大脑。

RAG 是什么?
Retrieval-Augmented Generation = 先"检索"资料,再让大模型"生成"回答。
解决大模型不知道你私有文档内容的问题。

完整流程(建议按这个顺序理解代码):
  入库: 上传文档 → 解析成纯文本 → 切分成小块 → 每块向量化 → 存入向量库
  问答: 用户提问 → 问题向量化 → 向量库里检索最相关片段 → 拼进提示词 → 大模型流式回答

用到的 LangChain 组件(都在顶部 import):
  - RecursiveCharacterTextSplitter  文本切分器
  - OpenAIEmbeddings                文本→向量(走 OpenAI 兼容协议连阿里百炼)
  - ChatOpenAI                      对话大模型(走 OpenAI 兼容协议连 DeepSeek)
  - ChatPromptTemplate              提示词模板(系统角色 + 用户问题)
"""
import logging
from typing import Iterator, List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from .config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_CHAT_MODEL,
    EMBEDDING_MODEL,
    TOP_K,
)
from .parse import split_text
from .storage import store

# 业务日志:单独一个 logger,方便按模块过滤
logger = logging.getLogger("ai-doc-qa.rag")

# ================= 1. 初始化 LangChain 组件 =================

# embeddings:把"文本"变成"向量"的模型。
# 阿里百炼提供 OpenAI 兼容接口,所以用 OpenAIEmbeddings 换 base_url 即可。
# 注意:check_embedding_ctx_length=False 很重要!
# 新版 LangChain 默认开启"长度安全"处理,会把文本 tokenize 成 id 再发请求,
# 但 DashScope 兼容接口只接受原始文本,会报 contents 类型错误,所以必须关掉。
# max_retries=3:网络抖动/限流时自动重试,用户无感(企业级第二步)
embeddings = OpenAIEmbeddings(
    model=EMBEDDING_MODEL,
    api_key=DASHSCOPE_API_KEY,
    base_url=DASHSCOPE_BASE_URL,
    check_embedding_ctx_length=False,  # 直接发送原始文本,兼容阿里百炼
    max_retries=3,                     # 失败自动重试 3 次
)

# llm:对话大模型,同样通过 OpenAI 兼容协议连接 DeepSeek。
# timeout=60:单次请求超过 60 秒直接放弃,防止请求挂死拖垮服务
# max_retries=3:网络抖动自动重试
llm = ChatOpenAI(
    model=DEEPSEEK_CHAT_MODEL,
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    temperature=0.3,  # 低温度 → 回答更稳定、更忠于资料(不瞎编)
    streaming=True,   # 开启流式输出 → 前端有"打字机"效果
    timeout=60,       # 请求超时:60 秒
    max_retries=3,    # 失败自动重试 3 次
)

# splitter:文本切分逻辑已抽到 parse.py 模块(职责分离,便于复用和测试)

# prompt:提示词模板。{context} 和 {question} 是占位符,调用时填充。
prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """你是文档问答助手。请只根据下面的参考资料回答用户问题,引用时标注来源文档;如果资料中没有答案,直接说"资料中没有相关内容",不要编造。

参考资料:
{context}""",
        ),
        ("human", "{question}"),
    ]
)


# ================= 2. 入库流程 =================
# 阿里百炼 embedding 接口限制:单次请求最多 10 条文本
# 注意:LangChain 的 embed_documents 内部按 token 分批(不是按条数),
# 大文档时可能一批超过 10 条 → 报 400。所以必须自己控制按条数分批。
EMBED_BATCH = 10


def _embed_in_batches(texts: List[str]) -> List[List[float]]:
    """分批向量化:每批最多 EMBED_BATCH 条,兼容阿里百炼的限制。"""
    vectors: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        batch = texts[i : i + EMBED_BATCH]
        vectors.extend(embeddings.embed_documents(batch))
    return vectors


def ingest_document(doc_name: str, text: str) -> int:
    """把一个文档的全文切分、向量化、入库,返回入库的片段数。

    三步:
      1) splitter.split_text(text)         → 文本切分成若干小块
      2) embeddings.embed_documents(chunks)→ 每块调百炼 API 转成向量
      3) store.add_chunks(...)             → 文本+向量成对存进向量库
    """
    chunks = split_text(text)
    if not chunks:
        logger.warning("文档 %s 切分后为空,跳过", doc_name)
        return 0
    logger.info("文档 %s 切分为 %d 块,开始向量化", doc_name, len(chunks))
    vectors = _embed_in_batches(chunks)
    added = store.add_chunks(doc_name, chunks, vectors)
    logger.info("文档 %s 入库完成:新增 %d 块", doc_name, added)
    return added


# ================= 3. 问答流程(流式) =================
def ask_question(question: str) -> Iterator[str]:
    """RAG 问答:检索 → 组装 → 流式生成。返回逐段文本的迭代器。

    为什么是 Iterator(生成器)?
    生成器是"惰性"的——每次产出一点文本就交给 FastAPI 转发给前端,
    用户立刻看到第一个字,不用等全部生成完。
    """
    # 1) 问题向量化:把用户问题转成向量,才能和库里的块比相似度
    q_vector = embeddings.embed_query(question)

    # 2) 检索:从库里挑出与问题最相似的 TOP_K 个片段
    hits = store.search(q_vector, TOP_K)
    logger.info("检索命中 %d 块,开始生成回答", len(hits))

    # 健壮性:知识库为空/没命中时,直接友好提示,不白调一次大模型
    if not hits:
        yield "知识库中还没有相关内容,请先上传文档(txt/md/pdf/docx)再提问。"
        return

    # 3) 组装:把命中的片段拼成"参考资料",标注来源,防止模型编造
    context = "\n\n---\n\n".join(
        f"【来源:{c['doc_name']}】\n{c['text']}" for c in hits
    )

    # 4) 组成 LangChain 链:提示词模板 → 大模型
    #    (LangChain 用 | 管道符把组件串成链,像 Unix 管道一样)
    chain = prompt | llm

    # 5) 流式生成:chain.stream() 会逐 token 产出
    #    chunk.content 是当前这一小段的文本
    for chunk in chain.stream({"context": context, "question": question}):
        yield str(chunk.content)


# 下面这个变量仅作"链构建方式"的演示,方便你理解 | 管道语法
# 实际未使用;如果不用流式,可以直接 chain.invoke(...) 拿完整回答
_build_demo_chain = prompt | llm
