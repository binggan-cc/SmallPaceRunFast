"""
Skill ↔ Context Layer 接入辅助（Phase 8）

设计原理：
─────────
Phase 8 的核心是让 Skill 消费 Context Layer，但必须遵守"优雅降级"原则：
- 有索引（.smartdev/index.sqlite 存在）→ Skill 用 Context Layer 增强
- 无索引 → Skill 退回原逻辑（关键词 / 独立 AST），零回归

这个模块提供 Skill 层共享的索引可用性检测，避免每个 Skill 重复写检测逻辑。

为什么放在 skills/ 而不是 context/？
  这是 Skill 层的消费辅助，不是 Context Layer 的能力。
  context/ 只负责"提供索引"，不关心"谁来消费"。

对应文档：
- docs/phase-8-design.md §4.1（共享辅助：索引可用性检测）
"""

from __future__ import annotations

from pathlib import Path

from smartdev.models import RiskLevel


def get_index_if_available(project_path: Path):
    """如果项目已建立索引，返回 ProjectIndex，否则返回 None。

    用于 Skill 优雅降级：有索引则增强，无索引退回原逻辑。

    关键约束：
    - 只读，不触发索引构建（不调用 .index()）
    - 任何异常都返回 None，确保 Skill 永远不会因索引问题而崩溃
    - 调用方负责 close()

    参数：
        project_path: 项目根目录

    返回：
        ProjectIndex 实例（索引存在且可打开）或 None
    """
    db_path = project_path / ".smartdev" / "index.sqlite"
    if not db_path.exists():
        return None
    try:
        # 延迟导入，避免 skills 包加载时强依赖 context 层
        from smartdev.context.project_index import ProjectIndex

        return ProjectIndex(project_path)
    except Exception:
        # 索引损坏 / 打开失败 → 退回原逻辑，不中断 Skill
        return None


def max_risk(*levels: RiskLevel) -> RiskLevel:
    """返回多个风险等级中的最高值。

    RiskLevel.value 为 "R0".."R3"，字典序即风险高低序。
    用于合并关键词判断和 impact 判断的风险信号——宁可保守，不可低估。

    参数：
        levels: 一个或多个 RiskLevel

    返回：
        最高风险等级；无输入时返回 R0
    """
    if not levels:
        return RiskLevel.R0
    return max(levels, key=lambda r: r.value)
