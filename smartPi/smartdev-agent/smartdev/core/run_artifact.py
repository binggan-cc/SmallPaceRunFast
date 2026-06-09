"""
Run Artifact 目录约定 — Phase 11D Step 1 核心交付物

功能：
─────
在 .smartdev/runs/<run_id>/ 下建立标准化运行产物目录，
包含 task-card.md（任务卡片）和 scope.json（修改范围约束）。

Scope Gate（Step 2）将消费 scope.json 对比 changed_files 做边界检查。
handoff code/doc/review（Step 3-5）将读取本目录作为事实源。

设计约束：
─────────
- 零外部依赖（标准库）
- 只写 .smartdev/runs/<run_id>/（不碰源码）
- run_id 验证：非空 / 字母数字短横下划线点 / 最长 64 字符
- 重复 run_id：默认报错；force=True 覆盖
- scope.json 字段为 Step 2 Scope Gate 预留消费接口

对应文档：
- docs/phase-11d-design.md §4（Run Artifact 目录约定）
- docs/phase-11d-design.md §6（Scope Gate）
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

# ── 常量 ──────────────────────────────────────────────────────

# run_id 命名规则：字母数字/短横/下划线/点，最长 64 字符
_RUN_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-_\.]{0,63}$")

# 默认 scope 值（Step 1 只建立结构，Step 2 消费）
DEFAULT_MAX_FILES = 10
DEFAULT_PROTECTED_PATHS = [
    "docs/phase-*-design.md",
    "CHANGELOG.md",
    "CLAUDE.md",
    "pyproject.toml",
    ".gitignore",
    ".smartdev/git-policy.json",
]
# 代码目录默认允许
DEFAULT_ALLOWED_PATHS = [
    "smartdev/",
    "tests/",
    "docs/",
]
# 默认拒绝路径（二进制/构建产物）
DEFAULT_DENIED_PATHS = [
    "__pycache__/",
    "*.pyc",
    ".pytest_cache/",
    "dist/",
    "build/",
    ".venv/",
    "node_modules/",
    ".git/",
]

# task-card.md 模板
TASK_CARD_TEMPLATE = """# {run_id}

> 状态：待开始
> 创建时间：{created_at}

## 目标

{task}

## 范围

<!-- 允许修改的文件/目录 -->

## 非范围

<!-- 禁止修改的文件/目录 -->

## 验收标准

<!-- 完成标准 -->

## 约束

<!-- 从 scope.json 自动生成 -->
- max_files: {max_files}
- allowed_paths: {allowed_paths}
- denied_paths: {denied_paths}
- protected_paths: {protected_paths}
"""


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class ScopeConfig:
    """修改范围约束，Phase 11D Step 2 Scope Gate 的消费接口。

    Attributes:
        allowed_paths:   允许修改的路径列表（glob 模式）
        denied_paths:    禁止修改的路径列表（glob 模式）
        max_files:       单次变更最大文件数（change.budget）
        protected_paths: 受保护路径（变更 → 触发 R3/rejection）
    """

    allowed_paths: list[str] = field(default_factory=lambda: DEFAULT_ALLOWED_PATHS.copy())
    denied_paths: list[str] = field(default_factory=lambda: DEFAULT_DENIED_PATHS.copy())
    max_files: int = DEFAULT_MAX_FILES
    protected_paths: list[str] = field(default_factory=lambda: DEFAULT_PROTECTED_PATHS.copy())

    def to_dict(self) -> dict:
        """序列化为 scope.json 格式。"""
        return {
            "allowed_paths": self.allowed_paths,
            "denied_paths": self.denied_paths,
            "max_files": self.max_files,
            "protected_paths": self.protected_paths,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ScopeConfig":
        """从 dict 反序列化。"""
        return cls(
            allowed_paths=d.get("allowed_paths", DEFAULT_ALLOWED_PATHS.copy()),
            denied_paths=d.get("denied_paths", DEFAULT_DENIED_PATHS.copy()),
            max_files=d.get("max_files", DEFAULT_MAX_FILES),
            protected_paths=d.get("protected_paths", DEFAULT_PROTECTED_PATHS.copy()),
        )

    def to_json(self, indent: int = 2) -> str:
        """序列化为 JSON 字符串。"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


# ── 核心逻辑 ──────────────────────────────────────────────────


def validate_run_id(run_id: str) -> str | None:
    """验证 run_id 格式。返回错误消息或 None（通过）。

    run_id 规则：
    - 非空
    - 以字母或数字开头
    - 只包含字母、数字、短横(-)、下划线(_)、点(.)
    - 最长 64 字符
    """
    if not run_id:
        return "run_id 不能为空"
    if not _RUN_ID_PATTERN.match(run_id):
        return (
            f"run_id '{run_id}' 格式无效。"
            f"必须以字母或数字开头，只包含字母/数字/短横/下划线/点，最长 64 字符"
        )
    return None


def create_run_artifact(
    project_path: Path,
    run_id: str,
    task: str = "",
    scope: ScopeConfig | None = None,
    force: bool = False,
) -> tuple[Path, str | None]:
    """创建 run artifact 目录并写入初始文件。

    Args:
        project_path: 项目根目录
        run_id:      任务唯一标识
        task:        任务描述（写入 task-card.md）
        scope:       修改范围约束（None 则用默认值）
        force:       是否覆盖已存在的 run 目录

    Returns:
        (run_dir, error_message)
        - 成功: (run_dir, None)
        - 失败: (Path("."), error_message)
    """
    # 1. 验证 run_id
    err = validate_run_id(run_id)
    if err:
        return Path("."), err

    # 2. 确定 run 目录路径
    runs_dir = project_path / ".smartdev" / "runs"
    run_dir = runs_dir / run_id

    # 3. 检查重复
    if run_dir.exists():
        if not force:
            return Path("."), (
                f"run_id '{run_id}' 已存在（{run_dir}）。"
                f"使用 --force 覆盖，或指定新的 run_id"
            )
        # force: 删除旧目录，重新创建
        import shutil
        shutil.rmtree(run_dir)

    # 4. 创建目录
    run_dir.mkdir(parents=True, exist_ok=True)

    # 5. 使用默认 scope（如果未提供）
    if scope is None:
        scope = ScopeConfig()

    # 6. 写入 scope.json
    scope_path = run_dir / "scope.json"
    scope_path.write_text(scope.to_json(), encoding="utf-8")

    # 7. 写入 task-card.md
    task_card_path = run_dir / "task-card.md"
    created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    task_card_content = TASK_CARD_TEMPLATE.format(
        run_id=run_id,
        created_at=created_at,
        task=task or "（待填写）",
        max_files=scope.max_files,
        allowed_paths=", ".join(scope.allowed_paths),
        denied_paths=", ".join(scope.denied_paths),
        protected_paths=", ".join(scope.protected_paths),
    )
    task_card_path.write_text(task_card_content, encoding="utf-8")

    return run_dir, None
