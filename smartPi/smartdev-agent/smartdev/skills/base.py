"""
Skill 抽象基类

设计原理：
─────────
Skill 是 SmartDev Agent 的最小可执行单元。每个 Skill 封装一个独立能力
（如扫描项目、审计 Token、生成文档），通过统一接口与 Core Runtime 交互。

为什么用 ABC + __init_subclass__ 而非协议（Protocol）？
─────────────────────────────────────────────────────
1. ABC 强制子类实现 run()，漏实现会报错；Protocol 只是结构化类型提示
2. __init_subclass__ 实现自动注册，子类定义即注册，无需手动维护列表
3. 类属性（risk_level, task_type）在类定义时就确定，Runtime 可静态获取

调用流程（对应 agent.md §5）：
────────────────────────────
  user input
    → IntentParser 判断 task_type
    → SkillRegistry.list_skills(task_type) 筛选可用 Skill
    → skill.can_run(context) 检查前置条件
    → risk_controller.check(skill.risk_level) 判断是否需要确认
    → skill.run(context, inputs) 执行
    → ResultReporter 处理 SkillResult

对应文档：
- smartPi/docs/smartdev-agent/agent.md §3（四层架构）、§8（Skill 接口）
- smartPi/docs/smartdev-agent-core-spec.md §11（风险等级）
- smartPi/docs/smartdev-agent-protocol.md §2（5 条核心原则）
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from smartdev.models import RiskLevel, SkillResult, TaskType


class Skill(ABC):
    """Skill 抽象基类

    所有 SmartDev Skill 必须继承此类并实现：
    - risk_level: 类属性，声明风险等级
    - task_type: 类属性，声明所属任务类型
    - name: 类属性，人类可读的 Skill 名称
    - description: 类属性，Skill 功能描述
    - can_run(): 检查前置条件
    - run(): 执行 Skill 逻辑

    使用示例：
        class RepoScanSkill(Skill):
            name = "repo.scan"
            description = "扫描项目目录，识别技术栈、入口文件和文档状态"
            risk_level = RiskLevel.R0
            task_type = TaskType.DIAGNOSE

            def can_run(self, context):
                return context.project_path.exists()

            def run(self, context, inputs=None):
                # ... 扫描逻辑
                return SkillResult(success=True, summary="扫描完成", data={...})
    """

    # ── 类属性（子类必须覆盖） ──────────────────────────────

    name: str = ""               # Skill 唯一标识，如 "repo.scan"
    description: str = ""        # 人类可读描述
    risk_level: RiskLevel = RiskLevel.R0   # 风险等级，决定 Runtime 的执行策略
    task_type: TaskType = TaskType.DIAGNOSE  # 所属任务类型，用于 Workflow 调度

    # ── 自动注册机制 ────────────────────────────────────────
    # 为什么用 __init_subclass__？
    #
    # 传统方式需要手动维护一个注册表：
    #   SKILL_REGISTRY = [RepoScanSkill, TokenAuditSkill, ...]
    #
    # __init_subclass__ 的优势：
    #   1. 子类定义即注册，不需要额外步骤
    #   2. 新增 Skill 只需创建文件，不需要修改任何注册表
    #   3. 避免"忘记注册"导致 Skill 不可用的 bug
    #
    # 工作原理：
    #   当 Python 执行 "class RepoScanSkill(Skill):" 时，
    #   会自动调用 Skill.__init_subclass__()，
    #   我们在这里把子类加入 _registry 字典。

    _registry: dict[str, type[Skill]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # 只注册有 name 的具体子类，跳过没有 name 的中间抽象类
        if cls.name:
            Skill._registry[cls.name] = cls

    @classmethod
    def get_registry(cls) -> dict[str, type[Skill]]:
        """获取所有已注册的 Skill 类

        返回：
            {skill_name: SkillClass} 字典

        使用场景：
            - Runtime 初始化时扫描所有可用 Skill
            - CLI 列出所有可用 Skill
            - Workflow 根据 task_type 筛选 Skill
        """
        return dict(cls._registry)

    @classmethod
    def get_skill(cls, name: str) -> type[Skill] | None:
        """按名称获取 Skill 类

        参数：
            name: Skill 名称，如 "repo.scan"

        返回：
            Skill 类，未找到返回 None
        """
        return cls._registry.get(name)

    @classmethod
    def create(cls, name: str) -> Skill:
        """按名称创建 Skill 实例

        参数：
            name: Skill 名称，如 "repo.scan"

        返回：
            Skill 实例

        异常：
            KeyError: 找不到名为 name 的 Skill
        """
        skill_cls = cls._registry.get(name)
        if skill_cls is None:
            available = ", ".join(sorted(cls._registry.keys()))
            raise KeyError(
                f"Skill '{name}' 未注册。可用 Skill: {available}"
            )
        return skill_cls()

    # ── 核心接口（子类必须实现） ─────────────────────────────

    @abstractmethod
    def can_run(self, context: Any) -> bool:
        """检查 Skill 是否可以在当前上下文中运行

        前置条件检查，对应 agent.md §5 的 preconditions。
        在 run() 之前调用，如果返回 False，Runtime 不应执行 run()。

        典型检查：
        - 项目路径是否存在
        - 适配器是否匹配
        - 必需文件是否存在
        - 用户约束是否满足

        参数：
            context: ProjectContext 实例

        返回：
            True 表示可以执行，False 表示前置条件不满足
        """
        ...

    @abstractmethod
    def run(self, context: Any, inputs: dict | None = None) -> SkillResult:
        """执行 Skill 逻辑

        核心执行方法，对应 agent.md §8 的 run(context, inputs) -> SkillResult。
        必须返回 SkillResult，不允许返回 None 或其他类型。

        约束（对应 protocol §1 的 5 条核心原则）：
        - R0 Skill：只读，不修改任何文件
        - R1 Skill：可修改，但必须在 changed_files 中列出
        - R2/R3 Skill：必须在 risks 中说明风险

        参数：
            context: ProjectContext 实例
            inputs: 可选的输入参数字典，不同 Skill 定义自己的 inputs 结构

        返回：
            SkillResult 实例
        """
        ...

    # ── 辅助方法（子类可选覆盖） ─────────────────────────────

    def describe(self) -> dict[str, Any]:
        """返回 Skill 的元数据描述

        用于 CLI --list 输出和 Runtime 的 Skill 发现。
        子类无需覆盖，自动从类属性生成。

        返回：
            包含 name, description, risk_level, task_type 的字典
        """
        return {
            "name": self.name,
            "description": self.description,
            "risk_level": self.risk_level.value,
            "task_type": self.task_type.value,
        }
