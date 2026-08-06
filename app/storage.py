"""向量存储模块:保存文档切片与向量,提供相似度检索。

本模块自己实现了一个最简单的"向量数据库":
- 数据存在内存列表 + 本地 JSON 文件(双保险:重启不丢)
- 检索用余弦相似度暴力比对(数据量小时完全够用)

生产环境可以换成真正的向量数据库(Chroma / pgvector / Milvus),
接口保持相似,业务代码几乎不用改——这就是"存储抽象"的意义。
"""
import json
import math
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List

from .config import DATA_DIR, CHUNKS_FILE


def cosine(a: List[float], b: List[float]) -> float:
    """余弦相似度:衡量两个向量"方向"有多接近,范围 [-1, 1],越大越相似。

    公式:cos(a,b) = (a·b) / (|a| * |b|)
    只关心方向不关心长度,所以适合比较文本语义(与文本长短无关)。
    设计为模块级纯函数:不依赖类状态,方便单元测试与复用。
    """
    dot = sum(x * y for x, y in zip(a, b))          # 点积
    na = math.sqrt(sum(x * x for x in a))           # 向量 a 的模长
    nb = math.sqrt(sum(x * x for x in b))           # 向量 b 的模长
    return dot / (na * nb) if na and nb else 0.0    # 除零保护


class VectorStore:
    """极简向量存储。chunks 结构:
    {
        "id": 唯一id,            # 用于定位/删除
        "doc_name": 来源文档名,   # 用于分组和删除
        "text": 文本内容,         # 供大模型阅读
        "embedding": [向量],      # 供相似度计算
    }
    """

    def __init__(self, data_file: Path | None = None) -> None:
        # 数据文件可注入:生产用默认路径,测试传临时路径(便于单测隔离)
        self.data_file = data_file or CHUNKS_FILE
        self.chunks: List[Dict[str, Any]] = []
        self._load()

    # ================= 持久化 =================
    def _load(self) -> None:
        """启动时从 JSON 文件加载历史数据(服务重启知识库不丢)。"""
        if self.data_file.exists():
            self.chunks = json.loads(self.data_file.read_text(encoding="utf-8"))

    def _save(self) -> None:
        """内存数据写回 JSON 文件。"""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.data_file.write_text(
            json.dumps(self.chunks, ensure_ascii=False), encoding="utf-8"
        )

    # ================= 写入 =================
    def add_chunks(
        self, doc_name: str, texts: List[str], embeddings: List[List[float]]
    ) -> int:
        """入库:把 (文本, 向量) 成对追加进存储,返回入库块数。

        doc_name:   来源文档名(用于前端展示与删除)
        texts:      切分后的文本块列表
        embeddings: 与 texts 一一对应的向量列表
        """
        now = time.time()
        for i, (text, emb) in enumerate(zip(texts, embeddings)):
            self.chunks.append(
                {
                    "id": f"{now}-{i}-{uuid.uuid4().hex[:6]}",  # 时间戳+随机,保证唯一
                    "doc_name": doc_name,
                    "text": text,
                    "embedding": emb,
                }
            )
        self._save()
        return len(texts)

    # ================= 检索 =================
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """检索:把问题向量和库里每个块向量算相似度,返回最相似的 top_k 块。

        query_embedding: 问题文本的向量(由 embedding 模型生成)
        """
        scored = [
            (cosine(query_embedding, c["embedding"]), c) for c in self.chunks
        ]
        scored.sort(key=lambda x: x[0], reverse=True)   # 相似度从高到低
        return [c for _, c in scored[:top_k]]

    # ================= 文档管理 =================
    def list_docs(self) -> List[Dict[str, Any]]:
        """按文档名聚合,返回每个文档的片段数(供前端列表展示)。"""
        counts: Dict[str, int] = {}
        for c in self.chunks:
            counts[c["doc_name"]] = counts.get(c["doc_name"], 0) + 1
        return [{"name": n, "chunk_count": cnt} for n, cnt in counts.items()]

    def delete_doc(self, name: str) -> int:
        """删除某个文档的所有片段,返回删除了多少块。"""
        before = len(self.chunks)
        self.chunks = [c for c in self.chunks if c["doc_name"] != name]
        self._save()
        return before - len(self.chunks)

    def total_chunks(self) -> int:
        """当前知识库总片段数。"""
        return len(self.chunks)


# 全局单例:整个应用共享同一个存储对象
# (FastAPI 每个请求是独立的,但模块级对象只初始化一次,大家共用)
store = VectorStore()
