"""
SmartDev Agent 项目索引主入口

设计原理：
─────────
ProjectIndex 是 Semantic Project Context Layer 的门面类（Facade），
组合 IndexStore + ArtifactExtractor + ImpactAnalyzer，
提供统一的项目索引操作接口。

借鉴来源：
- CodeGraph 的 CodeGraph 类（src/index.ts）：组合 DatabaseConnection + ExtractionOrchestrator + ...
- 理念："不要让 LLM 读整个项目凭感觉分析，给它结构化上下文"

存储布局：
.smartdev/
  index.sqlite       ← 代码图谱数据库
  fingerprints.json  ← 文件指纹（增量检测）

对应文档：
- next-phase-code-intelligence.md §8.1（架构）
- next-phase-code-intelligence.md §11（实施路线）
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from smartdev.context.index_store import (
    ArtifactRecord,
    FileRecord,
    IndexStore,
    classify_file_kind,
    compute_file_hash,
    detect_language,
)


# ── 忽略策略 ──────────────────────────────────────────────
# 借鉴 CodeGraph 的默认忽略目录

_SKIP_DIRS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv",
    ".pytest_cache", ".mypy_cache", ".tox", "dist", "build",
    ".next", ".nuxt", ".cache", ".parcel-cache",
    "coverage", ".nyc_output", ".smartdev",
    "target", "vendor", ".gradle", ".idea", ".vscode",
    "eggs", "*.egg-info",
}

_SKIP_FILES = {
    "*.pyc", "*.pyo", "*.pyd", "*.so", "*.dylib",
    "*.o", "*.a", "*.lib",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock",
    ".DS_Store", "Thumbs.db",
}

MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB


def _should_skip_dir(dir_name: str) -> bool:
    """判断是否跳过目录"""
    if dir_name.startswith(".") and dir_name not in {".env.example"}:
        return True
    return dir_name in _SKIP_DIRS


def _should_skip_file(file_name: str) -> bool:
    """判断是否跳过文件"""
    return file_name in _SKIP_FILES


# ── Git-aware 文件扫描 ────────────────────────────────────

def _git_ls_files(project_path: Path) -> list[str] | None:
    """使用 git ls-files 获取 tracked 文件列表

    优先使用 git（更准确，自动尊重 .gitignore）。
    如果不是 git 仓库或 git 不可用，返回 None。
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def _walk_files(project_path: Path) -> list[str]:
    """使用 os.walk 扫描文件（fallback 方式）"""
    files = []
    for root, dirs, filenames in project_path.walk():
        # 过滤目录
        dirs[:] = [d for d in dirs if not _should_skip_dir(d)]
        for fname in filenames:
            if _should_skip_file(fname):
                continue
            rel_path = (root / fname).relative_to(project_path)
            files.append(str(rel_path))
    return sorted(files)


def scan_project_files(project_path: Path) -> list[FileRecord]:
    """扫描项目文件

    优先使用 git ls-files，fallback 到 os.walk。
    返回 FileRecord 列表，包含文件元信息。

    参数：
        project_path: 项目根目录

    返回：
        FileRecord 列表
    """
    # 优先 git-aware 扫描
    rel_paths = _git_ls_files(project_path)
    if rel_paths is None:
        rel_paths = _walk_files(project_path)

    records = []
    now = int(time.time())

    for rel_path in rel_paths:
        abs_path = project_path / rel_path

        # 跳过目录（git ls-files 有时会包含目录）
        if not abs_path.is_file():
            continue

        # 跳过过大文件
        try:
            size = abs_path.stat().st_size
        except OSError:
            continue
        if size > MAX_FILE_SIZE:
            continue

        # 计算 hash
        try:
            content_hash = compute_file_hash(abs_path)
        except OSError:
            continue

        # 检测语言和分类
        language = detect_language(abs_path)
        kind = classify_file_kind(abs_path)
        mtime = int(abs_path.stat().st_mtime)

        records.append(FileRecord(
            path=rel_path,
            content_hash=content_hash,
            language=language,
            kind=kind,
            size=size,
            modified_at=mtime,
            indexed_at=now,
        ))

    return records


# ── 项目索引门面类 ────────────────────────────────────────

class ProjectIndex:
    """项目索引主入口

    组合 IndexStore 提供完整的项目索引能力：
    - 扫描文件（scan）
    - 建立索引（index）
    - 搜索（search）
    - 查询统计（stats）

    使用示例：
        index = ProjectIndex(Path("/path/to/project"))
        index.scan()
        index.index()
        results = index.search("token")
        print(index.stats())
    """

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path.resolve()
        self.smartdev_dir = self.project_path / ".smartdev"
        self.db_path = self.smartdev_dir / "index.sqlite"
        self._store: IndexStore | None = None

    @property
    def store(self) -> IndexStore:
        """获取 IndexStore 实例（懒加载）"""
        if self._store is None:
            self._store = IndexStore(self.db_path)
            self._store.create_tables()
        return self._store

    def close(self) -> None:
        """关闭索引"""
        if self._store:
            self._store.close()
            self._store = None

    def index(self, force: bool = False) -> dict:
        """完整索引：scan + extract artifacts + write relations

        一步完成所有索引工作。CLI 和测试都应调用此方法。

        参数：
            force: 强制重新索引所有文件

        返回：
            索引统计信息
        """
        from smartdev.context.artifact_extractor import ArtifactExtractor

        # 1. 扫描文件
        scan_result = self.scan(force=force)

        # 2. 提取 artifact + relations
        extractor = ArtifactExtractor()
        extraction = extractor.extract(self.project_path)

        # 3. 写入 artifact（去重 upsert）
        for artifact in extraction.artifacts:
            self.store.upsert_artifact(artifact)

        # 4. 写入 relation（去重 upsert）
        relations_added = 0
        for relation in extraction.relations:
            if self.store.upsert_relation(relation):
                relations_added += 1

        return {
            "files": scan_result["total"],
            "files_updated": scan_result["updated"],
            "files_skipped": scan_result["skipped"],
            "artifacts": len(extraction.artifacts),
            "relations": relations_added,
            "errors": len(extraction.errors),
        }

    def scan(self, force: bool = False) -> dict:
        """扫描项目文件并更新索引

        参数：
            force: 强制重新索引所有文件（忽略 hash 比较）

        返回：
            扫描统计信息
        """
        records = scan_project_files(self.project_path)

        updated = 0
        skipped = 0
        for record in records:
            if force:
                # 强制模式：总是更新
                self.store.upsert_file(record)
                updated += 1
            else:
                if self.store.upsert_file(record):
                    updated += 1
                else:
                    skipped += 1

        return {
            "total": len(records),
            "updated": updated,
            "skipped": skipped,
            "project_path": str(self.project_path),
        }

    def search(self, query: str, limit: int = 20) -> dict:
        """搜索文件和工件

        返回：
            包含 files 和 artifacts 的搜索结果
        """
        files = self.store.search_files(query, limit=limit)
        artifacts = self.store.search_artifacts(query, limit=limit)

        return {
            "query": query,
            "files": [
                {"path": f.path, "language": f.language, "kind": f.kind, "size": f.size}
                for f in files
            ],
            "artifacts": [
                {"id": a.id, "type": a.type, "name": a.name,
                 "file_path": a.file_path, "metadata": a.metadata_json}
                for a in artifacts
            ],
            "total_files": len(files),
            "total_artifacts": len(artifacts),
        }

    def stats(self) -> dict:
        """获取索引统计信息"""
        return self.store.stats()

    def file_count(self) -> int:
        """获取已索引文件数"""
        return self.store.count_files()

    def artifact_count(self) -> int:
        """获取已索引工件数"""
        return self.store.count_artifacts()
