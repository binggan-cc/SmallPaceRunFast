"""
SmartDev Agent 核心数据模型

设计原则：
- 零外部依赖，只用标准库
- dataclass 而非 Pydantic（Phase 1 不需要复杂校验）
- Enum 而非字符串（类型安全，IDE 自动补全）

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md 第 11 节（风险等级）
- smartPi/docs/smartdev-agent-core-spec.md 第 10 节（任务类型）
- smartPi/docs/smartdev-agent/agent.md 第 8 节（Skill 接口）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


# ── 风险等级 ──────────────────────────────────────────────
# 对应 core-spec §11：R0 无风险 → R3 高风险
# 为什么用 Enum 而非字符串？
#   1. 类型安全：RiskLevel("R4") 会报错，字符串不会
#   2. IDE 补全：RiskLevel.R0 自动弹出
#   3. 和协议层的 risk_policy 映射关系明确

class RiskLevel(Enum):
    """任务风险等级，控制 Agent 的执行权限"""
    R0 = "R0"  # 无风险：只读分析、诊断、文档补充
    R1 = "R1"  # 低风险：小范围 CSS/文案修改、README 更新
    R2 = "R2"  # 中风险：多文件修改、API 调整、布局变更
    R3 = "R3"  # 高风险：数据模型、权限、技术栈、目录重构

    @property
    def can_auto_execute(self) -> bool:
        """该风险等级是否允许自动执行（无需用户确认）"""
        return self == RiskLevel.R0

    @property
    def requires_rollback_plan(self) -> bool:
        """该风险等级是否需要输出回滚方案"""
        return self in (RiskLevel.R2, RiskLevel.R3)


# ── 任务类型 ──────────────────────────────────────────────
# 对应 core-spec §10：8 种任务类型
# 为什么需要 TaskType？
#   1. Workflow 需要根据任务类型选择不同的 Skill 组合
#   2. Protocol 需要根据任务类型应用不同的约束规则
#   3. Reporter 需要根据任务类型选择不同的输出模板

class TaskType(Enum):
    """Agent 支持的任务类型"""
    DIAGNOSE = "diagnose"           # 项目诊断
    ANALYZE = "analyze"             # 架构分析
    PLAN = "plan"                   # 方案规划
    DOCUMENT = "document"           # 文档生成
    UI_GOVERNANCE = "ui_governance" # UI 规范治理
    BUGFIX = "bugfix"               # Bug 修复
    FEATURE = "feature"             # 新功能开发
    REFACTOR = "refactor"           # 重构


# ── Skill 执行结果 ────────────────────────────────────────
# 对应 agent.md 第 8 节：统一结果格式
# 为什么所有 Skill 输出同一个 SkillResult？
#   1. Core Runtime 不需要关心具体 Skill 的输出格式
#   2. Reporter 可以统一处理所有结果
#   3. Workflow 可以根据 success 字段决定下一步
#
# data 字段为什么是 dict 而非强类型？
#   不同 Skill 的结构化输出差异很大：
#   - repo.scan 输出 tech_stack: list[str]
#   - token.audit 输出 hardcoded_colors: list[dict]
#   - task.plan 输出 tasks: list[dict]
#   用 dict 保持灵活性，各 Skill 的文档说明自己的 data 结构。

@dataclass
class SkillResult:
    """Skill 统一执行结果

    所有 Skill 的 run() 方法必须返回此类型。
    Core Runtime 和 Workflow 层只依赖此接口，不感知具体 Skill 实现。
    """
    success: bool
    summary: str
    data: dict = field(default_factory=dict)
    changed_files: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    validation: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)


# ── 项目上下文 ────────────────────────────────────────────
# 对应 core-spec §4.3：Project Adapter Layer
# 为什么需要 ProjectContext？
#   1. Skill 需要知道项目路径、技术栈、适配器类型
#   2. 不同项目的 Skill 行为可能不同（Chrome Extension vs FastAPI）
#   3. 适配器的约束通过 context 传递给 Skill
#
# 为什么用 dataclass 而非 dict？
#   Phase 1 需要明确的字段定义，方便 IDE 提示和类型检查。
#   后续如果适配器需要动态字段，可以用扩展字段或迁移到 dict。

@dataclass
class ProjectContext:
    """项目上下文，传递给每个 Skill 的运行环境

    Attributes:
        project_path: 项目根目录的绝对路径
        adapter_name: 项目适配器名称（如 "smartfav", "chrome_extension"）
                      None 表示未识别到适配器，使用通用行为
        tech_stack: 识别到的技术栈（如 ["Chrome Extension MV3", "FastAPI"]）
        constraints: 用户指定的约束（如 ["不引入 React", "不做大规模重构"]）
        task_description: 用户的任务描述
    """
    project_path: Path
    adapter_name: str | None = None
    tech_stack: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    task_description: str = ""
