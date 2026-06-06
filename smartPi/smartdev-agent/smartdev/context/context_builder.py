"""
SmartDev Agent 上下文构建器（占位）

Phase 6-MVP 中此模块为占位，Phase 6.2 再完善。

设计目标：
给定任务描述，自动搜索 + 遍历 + 提取代码块，
为 LLM 提供结构化上下文（而非让 LLM 读整个项目）。

借鉴来源：
- CodeGraph 的 buildContext() API
- "不要让 LLM 读整个项目凭感觉分析，给它结构化上下文"
"""

from __future__ import annotations

from pathlib import Path

from smartdev.context.index_store import IndexStore


class ContextBuilder:
    """上下文构建器（Phase 6.2 完善）"""

    def __init__(self, store: IndexStore) -> None:
        self.store = store

    def build(self, task_description: str, max_chars: int = 12000) -> dict:
        """为任务构建上下文

        Phase 6-MVP: 简单返回索引统计 + 相关文件。
        Phase 6.2: 加入搜索 + 遍历 + 代码块提取。

        参数：
            task_description: 任务描述
            max_chars: 最大输出字符数

        返回：
            上下文字典
        """
        stats = self.store.stats()

        return {
            "task": task_description,
            "project_stats": stats,
            "relevant_files": [],  # Phase 6.2: 基于搜索填充
            "relevant_artifacts": [],
            "context_hint": "使用 code.search 和 code.impact 获取详细信息",
        }
