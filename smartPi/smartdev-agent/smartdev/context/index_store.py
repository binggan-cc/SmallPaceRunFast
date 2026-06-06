"""
SmartDev Agent SQLite 索引存储层

设计原理：
─────────
基于 CodeGraph 的 SQLite + FTS5 方案，但大幅简化。
Phase 6-MVP 只做 4 张表：files, artifacts, relations, runs。

为什么选 SQLite？
─────────────────
1. Python 标准库内置，零外部依赖
2. FTS5 提供全文搜索，不需要向量数据库
3. 单文件数据库，便于项目内持久化
4. 支持事务和增量更新

存储位置：.smartdev/index.sqlite

隐私规则：
- 绝对路径不写入长期图谱（用相对路径或 ~ 替换）
- env/key/token 值不入图谱
- .smartdev/ 是缓存写入（CACHE_WRITE），不是源代码修改

对应文档：
- next-phase-code-intelligence.md §9.1（SQLite Schema）
- next-phase-code-intelligence.md §8.1（Semantic Project Context Layer）
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ──────────────────────────────────────────────

@dataclass
class FileRecord:
    """文件记录"""
    path: str
    content_hash: str
    language: str
    kind: str  # source / config / document / test / asset / other
    size: int
    modified_at: int  # Unix timestamp
    indexed_at: int   # Unix timestamp


@dataclass
class ArtifactRecord:
    """工件记录"""
    id: str
    type: str  # api_endpoint / manifest / design_token / document / ...
    name: str
    file_path: str
    start_line: int = 0
    end_line: int = 0
    metadata_json: str = "{}"


@dataclass
class RelationRecord:
    """关系记录"""
    source_id: str
    target_id: str
    type: str  # imports / calls / contains / references / ...
    confidence: float = 1.0
    metadata_json: str = "{}"


@dataclass
class RunRecord:
    """运行记录"""
    id: str
    task: str
    created_at: str
    summary_json: str = "{}"


# ── 文件哈希工具 ──────────────────────────────────────────

def compute_file_hash(file_path: Path) -> str:
    """计算文件内容的 SHA256 哈希

    用于增量检测：hash 变化 = 文件内容变化。
    跳过 > 1MB 的文件（避免生成文件、bundle 撑爆解析器）。
    """
    MAX_SIZE = 1 * 1024 * 1024  # 1MB
    if file_path.stat().st_size > MAX_SIZE:
        return " oversized"
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 语言检测 ──────────────────────────────────────────────

_LANG_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".jsx": "javascript", ".tsx": "typescript",
    ".css": "css", ".scss": "scss", ".less": "less",
    ".html": "html", ".htm": "html",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".md": "markdown", ".rst": "rst", ".txt": "text",
    ".go": "go", ".rs": "rust", ".java": "java",
    ".rb": "ruby", ".php": "php", ".c": "c", ".cpp": "cpp",
    ".h": "c", ".hpp": "cpp", ".swift": "swift", ".kt": "kotlin",
    ".sql": "sql", ".sh": "shell", ".bash": "shell",
    ".vue": "vue", ".svelte": "svelte",
    ".toml": "toml", ".ini": "ini", ".cfg": "config",
    ".xml": "xml", ".svg": "svg",
}

# 文件类型分类
_CONFIG_PATTERNS = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "package.json", "tsconfig.json", "vite.config.ts", "vite.config.js",
    "webpack.config.js", "babel.config.js", ".eslintrc.js", ".prettierrc",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".gitignore", ".env", "Makefile", "CMakeLists.txt",
    "manifest.json", "background.js", "content.js",
}

_DOC_EXTENSIONS = {".md", ".rst", ".txt"}
_TEST_PATTERNS = {"test_", "_test.", ".test.", ".spec.", "tests/", "__tests__/"}


def detect_language(file_path: Path) -> str:
    """检测文件语言"""
    return _LANG_MAP.get(file_path.suffix.lower(), "unknown")


def classify_file_kind(file_path: Path) -> str:
    """分类文件类型：source / config / document / test / asset / other"""
    name = file_path.name
    suffix = file_path.suffix.lower()
    parts = file_path.parts

    # 测试文件
    for pattern in _TEST_PATTERNS:
        if pattern in name or pattern in str(file_path):
            return "test"

    # 文档
    if suffix in _DOC_EXTENSIONS:
        return "document"

    # 配置文件
    if name in _CONFIG_PATTERNS:
        return "config"

    # 资源文件
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
                   ".woff", ".woff2", ".ttf", ".eot"}:
        return "asset"

    # 源代码
    if suffix in _LANG_MAP:
        return "source"

    return "other"


# ── SQLite 存储层 ─────────────────────────────────────────

class IndexStore:
    """SQLite 索引存储

    管理 .smartdev/index.sqlite 数据库。
    支持增量更新（通过 content_hash 比较）。

    使用示例：
        store = IndexStore(project_path / ".smartdev" / "index.sqlite")
        store.create_tables()
        store.upsert_file(FileRecord(...))
        results = store.search_files("token")
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> sqlite3.Connection:
        """建立数据库连接"""
        if self._conn is None:
            # 确保父目录存在
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            # 启用 WAL 模式（更好的并发性能）
            self._conn.execute("PRAGMA journal_mode=WAL")
            # 启用外键约束
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None

    def create_tables(self) -> None:
        """创建所有表和索引

        幂等操作：表已存在时不会报错。
        """
        conn = self.connect()

        # 文件表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS files (
                path TEXT PRIMARY KEY,
                content_hash TEXT NOT NULL,
                language TEXT NOT NULL,
                kind TEXT NOT NULL,
                size INTEGER NOT NULL,
                modified_at INTEGER NOT NULL,
                indexed_at INTEGER NOT NULL
            )
        """)

        # 工件表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                start_line INTEGER DEFAULT 0,
                end_line INTEGER DEFAULT 0,
                metadata_json TEXT DEFAULT '{}'
            )
        """)

        # 关系表（不设外键：source/target 可以指向还未索引的 artifact）
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                metadata_json TEXT DEFAULT '{}'
            )
        """)

        # 运行记录表
        conn.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                created_at TEXT NOT NULL,
                summary_json TEXT DEFAULT '{}'
            )
        """)

        # FTS5 全文搜索索引（搜索 artifacts）
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS artifacts_fts USING fts5(
                id, type, name, file_path,
                content='artifacts', content_rowid='rowid'
            )
        """)

        # FTS 同步触发器
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS artifacts_ai AFTER INSERT ON artifacts BEGIN
                INSERT INTO artifacts_fts(rowid, id, type, name, file_path)
                VALUES (NEW.rowid, NEW.id, NEW.type, NEW.name, NEW.file_path);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS artifacts_ad AFTER DELETE ON artifacts BEGIN
                INSERT INTO artifacts_fts(artifacts_fts, rowid, id, type, name, file_path)
                VALUES ('delete', OLD.rowid, OLD.id, OLD.type, OLD.name, OLD.file_path);
            END
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS artifacts_au AFTER UPDATE ON artifacts BEGIN
                INSERT INTO artifacts_fts(artifacts_fts, rowid, id, type, name, file_path)
                VALUES ('delete', OLD.rowid, OLD.id, OLD.type, OLD.name, OLD.file_path);
                INSERT INTO artifacts_fts(rowid, id, type, name, file_path)
                VALUES (NEW.rowid, NEW.id, NEW.type, NEW.name, NEW.file_path);
            END
        """)

        # 辅助索引
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_language ON files(language)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_files_kind ON files(kind)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_file ON artifacts(file_path)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id)")

        conn.commit()

    # ── 文件操作 ──────────────────────────────────────────

    def upsert_file(self, record: FileRecord) -> bool:
        """插入或更新文件记录

        增量策略：如果 path 已存在且 hash 相同，跳过（返回 False）。
        如果 hash 不同，更新记录（返回 True）。
        如果 path 不存在，插入新记录（返回 True）。

        返回：
            True 表示有更新，False 表示跳过
        """
        conn = self.connect()

        # 检查是否已存在
        existing = conn.execute(
            "SELECT content_hash FROM files WHERE path = ?",
            (record.path,)
        ).fetchone()

        if existing and existing["content_hash"] == record.content_hash:
            return False  # hash 相同，跳过

        # 插入或更新
        conn.execute("""
            INSERT OR REPLACE INTO files
            (path, content_hash, language, kind, size, modified_at, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record.path, record.content_hash, record.language,
            record.kind, record.size, record.modified_at, record.indexed_at,
        ))
        conn.commit()
        return True

    def get_file(self, path: str) -> FileRecord | None:
        """获取单个文件记录"""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM files WHERE path = ?", (path,)
        ).fetchone()
        if row is None:
            return None
        return FileRecord(
            path=row["path"],
            content_hash=row["content_hash"],
            language=row["language"],
            kind=row["kind"],
            size=row["size"],
            modified_at=row["modified_at"],
            indexed_at=row["indexed_at"],
        )

    def list_files(self, kind: str | None = None, language: str | None = None) -> list[FileRecord]:
        """列出文件记录

        参数：
            kind: 按类型过滤（source/config/document/test/asset/other）
            language: 按语言过滤（python/javascript/...）
        """
        conn = self.connect()
        query = "SELECT * FROM files WHERE 1=1"
        params: list = []
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        if language:
            query += " AND language = ?"
            params.append(language)
        query += " ORDER BY path"

        rows = conn.execute(query, params).fetchall()
        return [
            FileRecord(
                path=r["path"], content_hash=r["content_hash"],
                language=r["language"], kind=r["kind"],
                size=r["size"], modified_at=r["modified_at"],
                indexed_at=r["indexed_at"],
            )
            for r in rows
        ]

    def count_files(self) -> int:
        """统计文件总数"""
        conn = self.connect()
        return conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]

    # ── Artifact 操作 ─────────────────────────────────────

    def upsert_artifact(self, record: ArtifactRecord) -> bool:
        """插入或更新工件记录

        返回：
            True 表示有更新，False 表示跳过（已存在且相同）
        """
        conn = self.connect()

        existing = conn.execute(
            "SELECT file_path, start_line, end_line FROM artifacts WHERE id = ?",
            (record.id,)
        ).fetchone()

        if existing:
            # 检查是否有变化
            if (existing["file_path"] == record.file_path
                    and existing["start_line"] == record.start_line
                    and existing["end_line"] == record.end_line):
                return False

        conn.execute("""
            INSERT OR REPLACE INTO artifacts
            (id, type, name, file_path, start_line, end_line, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            record.id, record.type, record.name,
            record.file_path, record.start_line, record.end_line,
            record.metadata_json,
        ))
        conn.commit()
        return True

    def get_artifact(self, artifact_id: str) -> ArtifactRecord | None:
        """获取单个工件记录"""
        conn = self.connect()
        row = conn.execute(
            "SELECT * FROM artifacts WHERE id = ?", (artifact_id,)
        ).fetchone()
        if row is None:
            return None
        return ArtifactRecord(
            id=row["id"], type=row["type"], name=row["name"],
            file_path=row["file_path"], start_line=row["start_line"],
            end_line=row["end_line"], metadata_json=row["metadata_json"],
        )

    def list_artifacts(self, artifact_type: str | None = None,
                       file_path: str | None = None) -> list[ArtifactRecord]:
        """列出工件记录"""
        conn = self.connect()
        query = "SELECT * FROM artifacts WHERE 1=1"
        params: list = []
        if artifact_type:
            query += " AND type = ?"
            params.append(artifact_type)
        if file_path:
            query += " AND file_path = ?"
            params.append(file_path)
        query += " ORDER BY type, name"

        rows = conn.execute(query, params).fetchall()
        return [
            ArtifactRecord(
                id=r["id"], type=r["type"], name=r["name"],
                file_path=r["file_path"], start_line=r["start_line"],
                end_line=r["end_line"], metadata_json=r["metadata_json"],
            )
            for r in rows
        ]

    def count_artifacts(self) -> int:
        """统计工件总数"""
        conn = self.connect()
        return conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]

    # ── Relation 操作 ─────────────────────────────────────

    def add_relation(self, record: RelationRecord) -> int:
        """添加关系记录（不去重，直接插入）

        返回：
            新记录的 ID
        """
        conn = self.connect()
        cursor = conn.execute("""
            INSERT INTO relations (source_id, target_id, type, confidence, metadata_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            record.source_id, record.target_id, record.type,
            record.confidence, record.metadata_json,
        ))
        conn.commit()
        return cursor.lastrowid or 0

    def upsert_relation(self, record: RelationRecord) -> bool:
        """插入或更新关系记录（去重）

        去重键：source_id + target_id + type
        如果已存在相同关系，更新 confidence 和 metadata（取新值）。

        返回：
            True 表示有更新，False 表示跳过（已存在且相同）
        """
        conn = self.connect()

        existing = conn.execute("""
            SELECT confidence, metadata_json FROM relations
            WHERE source_id = ? AND target_id = ? AND type = ?
        """, (record.source_id, record.target_id, record.type)).fetchone()

        if existing:
            # 已存在：如果 confidence 或 metadata 变了则更新
            if (existing["confidence"] == record.confidence
                    and existing["metadata_json"] == record.metadata_json):
                return False  # 跳过
            conn.execute("""
                UPDATE relations SET confidence = ?, metadata_json = ?
                WHERE source_id = ? AND target_id = ? AND type = ?
            """, (
                record.confidence, record.metadata_json,
                record.source_id, record.target_id, record.type,
            ))
            conn.commit()
            return True

        # 不存在：插入
        conn.execute("""
            INSERT INTO relations (source_id, target_id, type, confidence, metadata_json)
            VALUES (?, ?, ?, ?, ?)
        """, (
            record.source_id, record.target_id, record.type,
            record.confidence, record.metadata_json,
        ))
        conn.commit()
        return True

    def get_relations(self, artifact_id: str,
                      direction: str = "both") -> list[dict]:
        """获取与指定工件相关的关系

        参数：
            artifact_id: 工件 ID
            direction: "outgoing" / "incoming" / "both"
        """
        conn = self.connect()
        results = []

        if direction in ("outgoing", "both"):
            rows = conn.execute(
                "SELECT * FROM relations WHERE source_id = ?",
                (artifact_id,)
            ).fetchall()
            results.extend([dict(r) for r in rows])

        if direction in ("incoming", "both"):
            rows = conn.execute(
                "SELECT * FROM relations WHERE target_id = ?",
                (artifact_id,)
            ).fetchall()
            results.extend([dict(r) for r in rows])

        return results

    def count_relations(self) -> int:
        """统计关系总数"""
        conn = self.connect()
        return conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

    # ── Run 操作 ──────────────────────────────────────────

    def record_run(self, record: RunRecord) -> None:
        """记录一次运行"""
        conn = self.connect()
        conn.execute("""
            INSERT OR REPLACE INTO runs (id, task, created_at, summary_json)
            VALUES (?, ?, ?, ?)
        """, (record.id, record.task, record.created_at, record.summary_json))
        conn.commit()

    # ── 搜索操作 ──────────────────────────────────────────

    def search_artifacts(self, query: str, limit: int = 20) -> list[ArtifactRecord]:
        """全文搜索工件

        优先使用 FTS5，fallback 到 LIKE。
        """
        conn = self.connect()

        # 尝试 FTS5 搜索
        try:
            rows = conn.execute("""
                SELECT a.* FROM artifacts a
                JOIN artifacts_fts f ON a.rowid = f.rowid
                WHERE artifacts_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit)).fetchall()
            if rows:
                return [
                    ArtifactRecord(
                        id=r["id"], type=r["type"], name=r["name"],
                        file_path=r["file_path"], start_line=r["start_line"],
                        end_line=r["end_line"], metadata_json=r["metadata_json"],
                    )
                    for r in rows
                ]
        except sqlite3.OperationalError:
            pass  # FTS 查询语法错误，fallback 到 LIKE

        # Fallback: LIKE 搜索
        like_pattern = f"%{query}%"
        rows = conn.execute("""
            SELECT * FROM artifacts
            WHERE name LIKE ? OR file_path LIKE ? OR type LIKE ?
            LIMIT ?
        """, (like_pattern, like_pattern, like_pattern, limit)).fetchall()

        return [
            ArtifactRecord(
                id=r["id"], type=r["type"], name=r["name"],
                file_path=r["file_path"], start_line=r["start_line"],
                end_line=r["end_line"], metadata_json=r["metadata_json"],
            )
            for r in rows
        ]

    def search_files(self, query: str, limit: int = 20) -> list[FileRecord]:
        """搜索文件（LIKE 匹配路径）"""
        conn = self.connect()
        like_pattern = f"%{query}%"
        rows = conn.execute("""
            SELECT * FROM files
            WHERE path LIKE ?
            ORDER BY path
            LIMIT ?
        """, (like_pattern, limit)).fetchall()

        return [
            FileRecord(
                path=r["path"], content_hash=r["content_hash"],
                language=r["language"], kind=r["kind"],
                size=r["size"], modified_at=r["modified_at"],
                indexed_at=r["indexed_at"],
            )
            for r in rows
        ]

    # ── 统计操作 ──────────────────────────────────────────

    def stats(self) -> dict:
        """返回索引统计信息"""
        conn = self.connect()
        return {
            "files": conn.execute("SELECT COUNT(*) FROM files").fetchone()[0],
            "artifacts": conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0],
            "relations": conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0],
            "runs": conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0],
            "languages": [
                dict(r) for r in conn.execute(
                    "SELECT language, COUNT(*) as count FROM files GROUP BY language ORDER BY count DESC"
                ).fetchall()
            ],
            "artifact_types": [
                dict(r) for r in conn.execute(
                    "SELECT type, COUNT(*) as count FROM artifacts GROUP BY type ORDER BY count DESC"
                ).fetchall()
            ],
        }
