"""对话历史存储模块(SQLite)。

需求:刷新页面后聊天记录不丢——每条问答都持久化,按用户维度读取。
与 user_store 同库(users.db)分表存储,方便统一管理。
"""
import sqlite3
from datetime import datetime

from .config import USERS_DB


class ChatStore:
    """消息存取:保存问答、按用户拉历史"""

    def __init__(self, db_path=None) -> None:
        self.db_path = db_path or USERS_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,      -- 谁发的(多用户隔离)
                    role TEXT NOT NULL,          -- user / assistant
                    content TEXT NOT NULL,       -- 消息内容
                    created_at TEXT NOT NULL
                )
                """
            )

    def add_message(self, username: str, role: str, content: str) -> None:
        """保存一条消息"""
        if not content.strip():
            return
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (username, role, content, created_at) VALUES (?, ?, ?, ?)",
                (username, role, content, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )

    def list_messages(self, username: str, limit: int = 100) -> list[dict]:
        """按用户拉最近 N 条消息(时间正序,方便前端直接渲染)"""
        with self._connect() as conn:
            # 子查询取最近 N 条,再正序返回
            rows = conn.execute(
                """
                SELECT * FROM (
                    SELECT * FROM messages WHERE username = ?
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
                """,
                (username, limit),
            ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "created_at": r["created_at"]}
            for r in rows
        ]

    def clear_history(self, username: str) -> int:
        """清空某用户的历史记录,返回删除条数"""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM messages WHERE username = ?", (username,))
        return cur.rowcount


# 全局单例
chat_store = ChatStore()
