"""
Risk Controller — 风险控制器

设计原理：
─────────
Risk Controller 是 Core Runtime 的核心组件，负责在 Skill 执行前
检查风险等级，决定是否允许执行、是否需要用户确认。

为什么需要 Risk Controller？
──────────────────────────
1. Skill 自身声明 risk_level，但不决定是否能执行
2. 不同项目/场景的风险策略可能不同（开发环境 vs 生产环境）
3. R2/R3 操作必须有拦截机制，不能依赖 Skill 自觉

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §11（风险等级）
- smartPi/docs/smartdev-agent-core-spec.md §17（Agent 配置 — risk_policy）
- smartPi/docs/smartdev-agent-protocol.md §3.6（每步提交 git）
- smartPi/docs/smartdev-agent/agent.md §10（Skill 风险等级）
"""

from __future__ import annotations

from enum import Enum

from smartdev.models import RiskLevel


class RiskDecision(Enum):
    """风险检查决策

    ALLOW:          可以直接执行（R0）
    NEED_EXPLAIN:   需要说明范围后执行（R1）
    NEED_CONFIRM:   需要用户确认后执行（R2/R3）
    DENY:           拒绝执行（策略禁止）
    """

    ALLOW = "allow"
    NEED_EXPLAIN = "explain"
    NEED_CONFIRM = "confirm"
    DENY = "deny"


class RiskViolation(Exception):
    """风险违规异常

    当 Skill 尝试执行 R2/R3 操作但未获得用户确认时抛出。
    """

    def __init__(self, risk_level: RiskLevel, message: str = ""):
        self.risk_level = risk_level
        default_msg = (
            f"风险等级 {risk_level.value} 的操作需要用户确认后才能执行。"
            f"请先输出执行前说明（协议 §6），等待用户确认。"
        )
        super().__init__(message or default_msg)


# ── 默认风险策略 ──────────────────────────────────────────
# 对应 core-spec §17 的 risk_policy 配置
#
# 为什么用 dict 而非 Enum 映射？
#   Phase 1 只有默认策略，dict 足够清晰。
#   后续如果需要按项目/环境切换策略，可以升级为策略类。

DEFAULT_RISK_POLICY: dict[RiskLevel, RiskDecision] = {
    RiskLevel.R0: RiskDecision.ALLOW,
    RiskLevel.R1: RiskDecision.NEED_EXPLAIN,
    RiskLevel.R2: RiskDecision.NEED_CONFIRM,
    RiskLevel.R3: RiskDecision.NEED_CONFIRM,
}


class RiskController:
    """风险控制器

    在 Skill 执行前调用 check()，获取风险决策。
    根据决策决定是否需要输出执行前说明、是否需要用户确认。

    使用示例：
        from smartdev.core.risk import RiskController
        from smartdev.models import RiskLevel

        controller = RiskController()

        # R0 Skill — 直接执行
        decision = controller.check(RiskLevel.R0)
        assert decision == RiskDecision.ALLOW

        # R3 Skill — 需要确认
        decision = controller.check(RiskLevel.R3)
        assert decision == RiskDecision.NEED_CONFIRM

        # R3 Skill 未确认就执行 — 抛出异常
        controller.enforce(RiskLevel.R3)  # 抛出 RiskViolation
    """

    def __init__(self, policy: dict[RiskLevel, RiskDecision] | None = None):
        """初始化风险控制器

        参数：
            policy: 风险策略映射，None 使用默认策略
        """
        self._policy = policy or dict(DEFAULT_RISK_POLICY)

    def check(self, risk_level: RiskLevel) -> RiskDecision:
        """检查风险等级，返回决策

        参数：
            risk_level: Skill 的风险等级

        返回：
            RiskDecision，指示是否允许执行
        """
        return self._policy.get(risk_level, RiskDecision.DENY)

    def enforce(self, risk_level: RiskLevel) -> None:
        """强制执行风险检查，不满足则抛出异常

        参数：
            risk_level: Skill 的风险等级

        异常：
            RiskViolation: R2/R3 操作未获得确认时抛出

        使用场景：
            在 Skill 的 run() 入口调用，确保运行时也检查风险。
            即使上层 Workflow 漏掉了检查，Skill 自身也能拦截。
        """
        decision = self.check(risk_level)
        if decision == RiskDecision.NEED_CONFIRM:
            raise RiskViolation(risk_level)

    def requires_explanation(self, risk_level: RiskLevel) -> bool:
        """该风险等级是否需要输出执行前说明（协议 §6）"""
        decision = self.check(risk_level)
        return decision in (RiskDecision.NEED_EXPLAIN, RiskDecision.NEED_CONFIRM)

    def requires_confirmation(self, risk_level: RiskLevel) -> bool:
        """该风险等级是否需要用户确认"""
        return self.check(risk_level) == RiskDecision.NEED_CONFIRM

    def describe_policy(self) -> dict[str, str]:
        """输出当前策略的可读描述"""
        return {
            level.value: decision.value
            for level, decision in self._policy.items()
        }
