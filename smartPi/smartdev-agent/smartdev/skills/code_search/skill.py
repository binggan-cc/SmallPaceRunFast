"""
Skill: code.search — 代码搜索

功能：按名称、路径、类型搜索文件和工件。
风险：R0（只读，不修改任何文件）
类型：analyze

这是 Phase 6-MVP 的第 4 个交付物。基于 SQLite FTS5 或 LIKE 搜索。

搜索范围：
- files 表：按路径匹配
- artifacts 表：按名称、路径、类型匹配（FTS5 优先，LIKE fallback）

data 字段结构：
{
    "query": "搜索词",
    "files": [{"path": "...", "language": "...", "kind": "...", "size": ...}],
    "artifacts": [{"id": "...", "type": "...", "name": "...", "file_path": "..."}],
    "total_files": 5,
    "total_artifacts": 3
}

对应文档：
- next-phase-code-intelligence.md §8.3（code.search 设计）
- next-phase-code-intelligence.md §11（Task 4：code.search）
"""

from __future__ import annotations

from pathlib import Path

from smartdev.context.project_index import ProjectIndex
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


class CodeSearchSkill(Skill):
    """代码搜索 Skill

    在已建立索引的项目中搜索文件和工件。
    需要先运行 code.index 建立索引。

    使用示例：
        from smartdev.models import ProjectContext
        from smartdev.skills.base import Skill

        context = ProjectContext(project_path=Path("/path/to/project"))
        skill = Skill.create("code.search")
        result = skill.run(context, {"query": "token"})
    """

    name = "code.search"
    description = "按名称、路径、类型搜索文件和工件"
    risk_level = RiskLevel.R0
    task_type = TaskType.ANALYZE

    def can_run(self, context) -> bool:
        """前置条件：项目路径存在且已建立索引"""
        if not context.project_path.exists() or not context.project_path.is_dir():
            return False
        db_path = context.project_path / ".smartdev" / "index.sqlite"
        return db_path.exists()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行搜索

        参数：
            context: ProjectContext，必须包含 project_path
            inputs: 必须包含
                - query: str 搜索词
                - kind_filter: Optional[str] 按类型过滤
                - limit: int 最大返回数，默认 20

        返回：
            SkillResult，data 包含搜索结果
        """
        inputs = inputs or {}
        query = inputs.get("query", "")
        kind_filter = inputs.get("kind_filter")
        limit = inputs.get("limit", 20)

        if not query:
            return SkillResult(
                success=False,
                summary="错误：搜索词不能为空",
            )

        # 打开索引
        index = ProjectIndex(context.project_path)

        try:
            results = index.search(query, limit=limit)
        finally:
            index.close()

        # 按类型过滤 artifacts
        artifacts = results["artifacts"]
        if kind_filter:
            artifacts = [a for a in artifacts if a["type"] == kind_filter]

        # 组装结果
        total_files = results["total_files"]
        total_artifacts = len(artifacts)

        summary_parts = [
            f"搜索完成：'{query}'",
            f"匹配文件：{total_files} 个",
            f"匹配工件：{total_artifacts} 个",
        ]

        # 按类型统计工件
        if artifacts:
            type_counts: dict[str, int] = {}
            for a in artifacts:
                type_counts[a["type"]] = type_counts.get(a["type"], 0) + 1
            type_summary = ", ".join(f"{t}({c})" for t, c in sorted(type_counts.items()))
            summary_parts.append(f"工件类型：{type_summary}")

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "query": query,
                "files": results["files"],
                "artifacts": artifacts,
                "total_files": total_files,
                "total_artifacts": total_artifacts,
            },
        )
