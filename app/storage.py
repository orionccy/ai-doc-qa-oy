"""向量存储模块(Chroma 向量数据库版)。

从"自写 JSON 存储"升级为真正的向量数据库 Chroma:
- 数据持久化在 .data/chroma/ 目录
- 原生支持:向量检索(ANN 近似最近邻,数据量大时远快于暴力比对)、
  metadata 过滤(部门/文档/上传者——多租户隔离的载体)、批量删除
- 启动时自动把旧版 chunks.json 数据迁移进来(平滑升级)

对外接口与旧版保持一致:add_chunks / search / list_docs / delete_doc /
total_chunks / delete_doc_by_uploader——业务代码无需改动,这就是"存储抽象"的价值。
"""
import json
import math
import uuid
from pathlib import Path
from typing import Any, Dict, List

import chromadb

from .config import CHUNKS_FILE, DATA_DIR


def cosine(a: List[float], b: List[float]) -> float:
    """余弦相似度(保留纯函数,供测试与参考;实际检索由 Chroma 完成)。"""
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


class VectorStore:
    """Chroma 向量存储。chunk 结构(Chroma 的 document + metadata):
    - document: 文本内容(供大模型阅读)
    - metadata: {doc_name, department, uploader}(多租户隔离/审计)
    - embedding: 向量(供相似度检索)
    """

    def __init__(self, persist_dir: Path | None = None) -> None:
        # 持久化目录可注入:生产用默认路径,测试传临时目录(便于单测隔离)
        self.persist_dir = persist_dir or (DATA_DIR / "chroma")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        # hnsw:space=cosine:用余弦距离做检索(1-余弦相似度 = 距离)
        self.collection = self.client.get_or_create_collection(
            "chunks", metadata={"hnsw:space": "cosine"}
        )
        self._migrate_from_json()

    # ================= 旧数据迁移(一次性的平滑升级) =================
    def _migrate_from_json(self) -> None:
        """旧版 chunks.json → Chroma 自动导入。

        条件:JSON 存在、有数据、且 Chroma 还是空的(防止重复导入)。
        迁移成功后把 JSON 改名 .bak 备份,不再读取。
        """
        if not CHUNKS_FILE.exists() or self.collection.count() > 0:
            return
        try:
            old_chunks = json.loads(CHUNKS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return
        if not old_chunks:
            return
        ids = [c["id"] for c in old_chunks]
        embeddings = [c["embedding"] for c in old_chunks]
        documents = [c["text"] for c in old_chunks]
        metadatas = [
            {
                "doc_name": c.get("doc_name", "unknown"),
                "department": c.get("department", "default"),
                "uploader": c.get("uploader", ""),
            }
            for c in old_chunks
        ]
        self.collection.add(ids=ids, embeddings=embeddings,
                            documents=documents, metadatas=metadatas)
        CHUNKS_FILE.rename(CHUNKS_FILE.with_suffix(".json.bak"))
        print(f"[迁移] 旧 JSON 数据 {len(old_chunks)} 块已导入 Chroma,原文件已备份")

    # ================= 写入 =================
    def add_chunks(
        self, doc_name: str, texts: List[str], embeddings: List[List[float]],
        department: str = "default", uploader: str = "",
    ) -> int:
        """入库:文档切片 + 向量 + 元数据(部门/上传者)写入 Chroma。

        Chroma 要求:ids 唯一;embeddings/documents/metadatas 长度一致
        """
        ids = [f"{uuid.uuid4().hex}" for _ in texts]
        metadatas = [
            {"doc_name": doc_name, "department": department, "uploader": uploader}
            for _ in texts
        ]
        self.collection.add(
            ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas
        )
        return len(texts)

    # ================= 检索 =================
    def search(
        self, query_embedding: List[float], top_k: int = 5,
        department: str | None = None,
    ) -> List[Dict[str, Any]]:
        """检索:向量相似度 + 部门过滤(多租户隔离)。

        先隔离后检索:where 在数据库层过滤,不会把别的部门数据参与打分。
        score = 1 - cosine_distance(Chroma 返回距离,0=完全相同)。
        """
        where = {"department": department} if department else None
        res = self.collection.query(
            query_embeddings=[query_embedding], n_results=top_k, where=where
        )
        results: List[Dict[str, Any]] = []
        # Chroma 返回结构:ids/documents/metadatas/distances 都是 [[...]] 二维
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for i in range(len(ids)):
            m = metas[i] or {}
            results.append({
                "id": ids[i],
                "doc_name": m.get("doc_name", ""),
                "text": docs[i],
                "department": m.get("department", ""),
                "uploader": m.get("uploader", ""),
                "score": round(1 - dists[i], 4),  # 距离→相似度
            })
        return results

    # ================= 文档管理 =================
    def list_docs(self, department: str | None = None) -> List[Dict[str, Any]]:
        """按文档名聚合,返回每个文档的片段数(可按部门过滤)。

        返回带 department 字段:管理员视角需要区分文档属于哪个部门。
        """
        where = {"department": department} if department else None
        res = self.collection.get(where=where, include=["metadatas"])
        counts: Dict[str, Dict[str, Any]] = {}
        for m in res.get("metadatas", []):
            m = m or {}
            name = m.get("doc_name", "unknown")
            if name not in counts:
                counts[name] = {"chunk_count": 0, "department": m.get("department", "")}
            counts[name]["chunk_count"] += 1
        return [
            {"name": n, "chunk_count": v["chunk_count"], "department": v["department"]}
            for n, v in counts.items()
        ]

    def delete_doc(self, name: str, department: str | None = None) -> int:
        """删除某个文档的所有片段(可按部门限权),返回删除块数。"""
        where: Dict[str, str] = {"doc_name": name}
        if department:
            where["department"] = department
        res = self.collection.get(where=where)
        ids = res.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)

    def total_chunks(self, department: str | None = None) -> int:
        """总片段数(可按部门统计)。"""
        if department is None:
            return self.collection.count()
        return len(self.collection.get(where={"department": department}).get("ids", []))

    def delete_doc_by_uploader(self, uploader: str) -> int:
        """删除某上传者的全部文档(管理员删用户时调用),返回删除块数。"""
        res = self.collection.get(where={"uploader": uploader})
        ids = res.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)


# 全局单例:整个应用共享同一个存储对象
store = VectorStore()
