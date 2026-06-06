"""SmartDev Agent 语义项目上下文层

提供项目索引、存储、artifact 提取和影响分析能力。
这一层把项目从"文件集合"变成"可查询的语义结构"。

模块：
- project_index: 项目索引主入口（门面类）
- index_store: SQLite 存储层
- artifact_extractor: 项目工件提取
- impact_analyzer: 变更影响分析
- context_builder: 上下文构建（Phase 6.2 完善）
"""

from smartdev.context.index_store import IndexStore
from smartdev.context.project_index import ProjectIndex

__all__ = ["IndexStore", "ProjectIndex"]
