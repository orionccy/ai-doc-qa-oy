"""单元测试:只测纯逻辑,不调用任何外部 API(CI 里没有密钥也能跑)。

运行方式: python -m pytest tests/ -v
为什么要测试?企业级第四步:CI 里每次提交自动跑这些测试,
保证"改代码不弄坏旧功能"——这就是回归保护。
"""
import pytest

from app.storage import VectorStore, cosine
from app.parse import split_text


# ---------- 1. 余弦相似度(检索的核心算法) ----------
def test_cosine_same_vector():
    """相同向量相似度应接近 1"""
    a = [1.0, 2.0, 3.0]
    assert cosine(a, a) > 0.99


def test_cosine_orthogonal():
    """正交向量(完全不相关)相似度应接近 0"""
    assert cosine([1.0, 0.0], [0.0, 1.0]) < 0.01


def test_cosine_zero_vector():
    """零向量除零保护:不应报错"""
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


# ---------- 2. 文本切分 ----------
def test_split_long_text():
    """长文本应切成多块,且每块不超过上限"""
    text = "这是用于测试的文本内容。" * 300  # 约 3600 字
    chunks = split_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= 600 for c in chunks)


def test_split_short_text():
    """短文本应保持一块"""
    chunks = split_text("一句话")
    assert len(chunks) == 1


# ---------- 3. 向量存储(增/查/删,Chroma 版) ----------
def test_store_add_search_delete(tmp_path):
    """用临时目录测试存储(Chroma 持久化到 tmp_path),不污染真实知识库"""
    store = VectorStore(persist_dir=tmp_path / "chroma")

    # 入库 2 块(带部门标签)
    n = store.add_chunks(
        "测试文档",
        ["苹果是一种水果", "汽车是一种交通工具"],
        [[1.0, 0.0], [0.0, 1.0]],
        department="研发部",
        uploader="tester",
    )
    assert n == 2

    # 检索:查"水果"相关,应命中苹果那块(部门过滤生效)
    hits = store.search([0.9, 0.1], top_k=1, department="研发部")
    assert hits and "苹果" in hits[0]["text"]
    assert hits[0]["score"] > 0.5

    # 多租户隔离:查别的部门 → 无结果
    hits_other = store.search([0.9, 0.1], top_k=1, department="市场部")
    assert hits_other == []

    # 文档列表(带部门)
    docs = store.list_docs(department="研发部")
    assert docs[0]["name"] == "测试文档"
    assert docs[0]["chunk_count"] == 2
    assert docs[0]["department"] == "研发部"

    # 按上传者删除(管理员删用户时的清理路径)
    removed = store.delete_doc_by_uploader("tester")
    assert removed == 2
    assert store.total_chunks() == 0
