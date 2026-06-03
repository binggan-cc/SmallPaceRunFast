"""
Risk Controller 测试

验证：
1. 各风险等级的决策正确
2. enforce() 在 R2/R3 时抛出异常
3. 策略可自定义
4. describe_policy 输出正确
"""

import pytest

from smartdev.core.risk import (
    RiskController,
    RiskDecision,
    RiskViolation,
)
from smartdev.models import RiskLevel


class TestRiskController:
    """Risk Controller 基本功能测试"""

    def setup_method(self):
        self.controller = RiskController()

    def test_r0_allows_direct_execution(self):
        """R0 应该直接允许执行"""
        assert self.controller.check(RiskLevel.R0) == RiskDecision.ALLOW

    def test_r1_needs_explanation(self):
        """R1 需要说明范围"""
        assert self.controller.check(RiskLevel.R1) == RiskDecision.NEED_EXPLAIN

    def test_r2_needs_confirmation(self):
        """R2 需要用户确认"""
        assert self.controller.check(RiskLevel.R2) == RiskDecision.NEED_CONFIRM

    def test_r3_needs_confirmation(self):
        """R3 需要用户确认"""
        assert self.controller.check(RiskLevel.R3) == RiskDecision.NEED_CONFIRM

    def test_enforce_r0_passes(self):
        """R0 enforce 不抛异常"""
        self.controller.enforce(RiskLevel.R0)  # 不应该抛出

    def test_enforce_r1_passes(self):
        """R1 enforce 不抛异常（只需说明，不需确认）"""
        self.controller.enforce(RiskLevel.R1)

    def test_enforce_r2_raises(self):
        """R2 enforce 抛出 RiskViolation"""
        with pytest.raises(RiskViolation) as exc_info:
            self.controller.enforce(RiskLevel.R2)
        assert exc_info.value.risk_level == RiskLevel.R2

    def test_enforce_r3_raises(self):
        """R3 enforce 抛出 RiskViolation"""
        with pytest.raises(RiskViolation) as exc_info:
            self.controller.enforce(RiskLevel.R3)
        assert exc_info.value.risk_level == RiskLevel.R3

    def test_requires_explanation_r0(self):
        """R0 不需要说明"""
        assert self.controller.requires_explanation(RiskLevel.R0) is False

    def test_requires_explanation_r1(self):
        """R1 需要说明"""
        assert self.controller.requires_explanation(RiskLevel.R1) is True

    def test_requires_confirmation_r2(self):
        """R2 需要确认"""
        assert self.controller.requires_confirmation(RiskLevel.R2) is True

    def test_requires_confirmation_r1(self):
        """R1 不需要确认（只需说明）"""
        assert self.controller.requires_confirmation(RiskLevel.R1) is False


class TestRiskControllerCustomPolicy:
    """自定义策略测试"""

    def test_custom_policy(self):
        """可以传入自定义策略"""
        # 开发环境：R2 也直接允许
        dev_policy = {
            RiskLevel.R0: RiskDecision.ALLOW,
            RiskLevel.R1: RiskDecision.ALLOW,
            RiskLevel.R2: RiskDecision.ALLOW,
            RiskLevel.R3: RiskDecision.NEED_CONFIRM,
        }
        controller = RiskController(policy=dev_policy)

        assert controller.check(RiskLevel.R2) == RiskDecision.ALLOW
        assert controller.check(RiskLevel.R3) == RiskDecision.NEED_CONFIRM

    def test_describe_policy(self):
        """describe_policy 输出正确"""
        desc = self.controller.describe_policy()
        assert desc["R0"] == "allow"
        assert desc["R1"] == "explain"
        assert desc["R2"] == "confirm"
        assert desc["R3"] == "confirm"


# 需要在类方法中访问 self.controller
TestRiskControllerCustomPolicy.setup_method = TestRiskController.setup_method
