"""用户与部门存储模块(SQLite)。

为什么用 SQLite 而不是 JSON?
- 用户数据要按用户名精确查询、保证唯一性,SQLite 的 UNIQUE 约束天然支持
- 并发写入安全(JSON 多进程同时写会互相覆盖)
- Python 内置 sqlite3,零额外依赖,文件即数据库,轻量够用

密码安全(企业级优化):
- 使用 bcrypt 哈希(抗暴力破解,自动带盐)
- 老数据(sha256 格式)登录时自动迁移升级为 bcrypt——平滑过渡

表结构:
  users(id, username, password_hash, salt, department, role, created_at)
  - password_hash: bcrypt 哈希(老数据可能是 sha256,登录时自动迁移)
  - department: 所属部门(多租户隔离的键)
  - role: admin(管理员)/ user(普通用户)
"""
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime

import bcrypt

from .config import USERS_DB


@dataclass
class User:
    """用户对象:认证通过后携带的身份信息"""
    id: int
    username: str
    department: str
    role: str
    created_at: str = ""

    # 转成字典,方便返回给前端
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "department": self.department,
            "role": self.role,
            "created_at": self.created_at,
        }


class UserStore:
    """用户数据存取:注册、登录校验、查询"""

    def __init__(self, db_path=None) -> None:
        # 数据文件可注入:生产用默认路径,测试传临时路径
        self.db_path = db_path or USERS_DB
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """每次操作开新连接(避免多线程共用连接的问题)"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """建表(首次运行时自动创建)"""
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT COLLATE NOCASE UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    salt TEXT NOT NULL,
                    department TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user',
                    created_at TEXT NOT NULL
                )
                """
            )

    # ================= 密码安全(bcrypt) =================
    @staticmethod
    def _bcrypt_hash(password: str) -> str:
        """bcrypt 哈希:自动生成随机盐,输出形如 $2b$12$..."""
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def _is_bcrypt(hash_str: str) -> bool:
        """判断哈希是否为 bcrypt 格式($2 开头)"""
        return hash_str.startswith("$2")

    def _verify_and_upgrade(self, row, password: str) -> bool:
        """验证密码;老格式(sha256)验证通过后自动升级为 bcrypt。

        迁移策略(企业平滑升级常见做法):
        1. 新注册用户 → 直接 bcrypt
        2. 老用户登录 → 检测到 sha256 哈希 → 用老算法验证
           → 通过后立刻重写为 bcrypt,下次登录就是新格式
        """
        stored = row["password_hash"]
        if self._is_bcrypt(stored):
            return bcrypt.checkpw(password.encode(), stored.encode())

        # 老格式:sha256(盐 + 密码)
        import hashlib
        if hashlib.sha256((row["salt"] + password).encode()).hexdigest() == stored:
            # 升级:重写为 bcrypt
            with self._connect() as conn:
                conn.execute(
                    "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
                    (self._bcrypt_hash(password), "", row["id"]),
                )
            return True
        return False

    # ================= 核心操作 =================
    def create_user(self, username: str, password: str, department: str,
                    role: str = "user") -> User:
        """注册用户。用户名重复会抛 sqlite3.IntegrityError(由上层转成友好提示)"""
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, salt, department, role, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (username, self._bcrypt_hash(password), "", department, role, created),
            )
            uid = cur.lastrowid
        return User(id=uid, username=username, department=department,
                    role=role, created_at=created)

    def get_user(self, username: str) -> User | None:
        """按用户名查用户(不含密码字段)。

        COLLATE NOCASE:用户名不区分大小写(Orion2 / orion2 视为同一用户)
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone()
        if row is None:
            return None
        return User(id=row["id"], username=row["username"],
                    department=row["department"], role=row["role"],
                    created_at=row["created_at"])

    def verify_password(self, username: str, password: str) -> User | None:
        """登录校验:用户名存在 + 密码哈希匹配 → 返回 User,否则 None"""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone()
        if row is None:
            return None
        if not self._verify_and_upgrade(row, password):
            return None
        return User(id=row["id"], username=row["username"],
                    department=row["department"], role=row["role"],
                    created_at=row["created_at"])

    def list_users(self) -> list[dict]:
        """全部用户列表(管理员用)"""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM users ORDER BY id"
            ).fetchall()
        return [
            {"id": r["id"], "username": r["username"],
             "department": r["department"], "role": r["role"],
             "created_at": r["created_at"]}
            for r in rows
        ]

    def delete_user(self, username: str) -> bool:
        """删除用户(管理员用),返回是否删除了"""
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
        return cur.rowcount > 0

    def update_password(self, username: str, new_password: str) -> bool:
        """重置用户密码(bcrypt),返回是否成功"""
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
                (self._bcrypt_hash(new_password), "", username),
            )
        return cur.rowcount > 0


# 全局单例:所有模块共用一个存储实例
user_store = UserStore()
