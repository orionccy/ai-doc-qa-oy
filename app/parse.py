"""文档解析与切分模块:把二进制文件转成纯文本,再切分成小块。

职责单一:本模块只负责"文件 → 文本 → 小块的转换",不关心向量化、检索。
这样 main.py(路由)和 rag.py(RAG 流程)都能复用,也方便单独测试。
"""
import io
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

# 文本切分器:chunk_size=600 字符,overlap=80 字符。
# separators 定义"切分优先级":先按段落切,再按换行、句号……最后按字符硬切。
splitter = RecursiveCharacterTextSplitter(
    chunk_size=600,
    chunk_overlap=80,
    separators=["\n\n", "\n", "。", "!", "?", "；", " ", ""],
)


def extract_text(filename: str, data: bytes) -> str:
    """按扩展名把二进制文件解析成纯文本(支持 pdf / docx / txt / md)。

    这是"文件 → 文本"的转换层,后续交给 split_text 切块。
    """
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext == "pdf":
        # pypdf 解析 PDF:逐页提取文字
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if ext == "docx":
        # python-docx 解析 Word:逐段落提取
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)

    # 其余按纯文本处理(txt / md / csv / json ...)
    return data.decode("utf-8", errors="ignore")


def split_text(text: str) -> List[str]:
    """把全文切成小块(供向量化入库)。

    封装 LangChain 的 splitter,业务代码不需要知道切分细节。
    """
    return splitter.split_text(text)
