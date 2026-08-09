"""配置模块:负责读取 API 密钥、路径等全局配置。

为什么单独拆一个模块?
- 所有路径、密钥、模型名集中在这里,改配置不用翻代码
- 其他模块 `from config import xxx` 即可使用
"""
import os
from pathlib import Path

from pydantic import SecretStr

# ---------- 目录定义 ----------
# BASE_DIR:项目根目录(本文件在 app/ 下,往上一级就是根目录)
BASE_DIR = Path(__file__).resolve().parent.parent
# DATA_DIR:知识库数据目录(存放持久化文件)
DATA_DIR = BASE_DIR / ".data"
# CHUNKS_FILE:知识库数据文件(JSON 格式)
CHUNKS_FILE = DATA_DIR / "chunks.json"


def load_env(path: Path = BASE_DIR / ".env") -> None:
    """读取 .env 文件里的 KEY=VALUE 配置到环境变量(简单实现,零依赖)。

    为什么不直接用 python-dotenv?为了少装一个包,逻辑也很简单:
    逐行读取,跳过注释(#开头)和空行,按 = 拆成 key/value。
    """
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


load_env()

# ---------- API 密钥 ----------
DEEPSEEK_API_KEY = SecretStr(os.getenv("DEEPSEEK_API_KEY", ""))
DASHSCOPE_API_KEY = SecretStr(os.getenv("DASHSCOPE_API_KEY", ""))

# ---------- 模型配置 ----------
# DeepSeek 提供 OpenAI 兼容接口,base_url 指向它的标准端点
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_CHAT_MODEL = "deepseek-chat"  # 对话模型

# 阿里百炼也提供 OpenAI 兼容接口(compatible-mode),用于 embedding 向量化
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
EMBEDDING_MODEL = "text-embedding-v3"  # 向量化模型

# ---------- RAG 参数 ----------
CHUNK_SIZE = 600      # 每个文本块的最大字符数
CHUNK_OVERLAP = 80    # 相邻块之间的重叠字符数(避免关键句被切断丢失)
TOP_K = 5             # 提问时检索返回最相似的片段数
# 相关性阈值:检索结果相似度低于该值视为"不相关",不给模型直接提示没找到。
# 防幻觉关键(宁可不答,不要瞎答)。text-embedding-v3 的余弦分数:相关片段一般 >0.4
MIN_SCORE = 0.35

# ---------- 多租户与认证 ----------
# USERS_DB:用户/部门数据文件(SQLite 格式,Python 内置支持,零依赖)
USERS_DB = DATA_DIR / "users.db"
# JWT 密钥:优先从 .env 读(生产必须配置),否则用开发密钥并打警告
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET:
    JWT_SECRET = "dev-secret-change-me-in-production"
    import warnings
    warnings.warn("JWT_SECRET 未配置,正在使用开发密钥!生产环境请在 .env 中设置 JWT_SECRET")
# Token 有效期(分钟):过期后需要重新登录
TOKEN_EXPIRE_MINUTES = 60 * 12
