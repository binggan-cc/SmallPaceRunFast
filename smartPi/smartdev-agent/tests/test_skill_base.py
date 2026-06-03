"""
Skill 基类测试

验证：
1. 自动注册机制
2. 风险等级属性
3. can_run / run 接口契约
4. SkillResult 数据结构
5. describe() 元数据输出
"""

from pathlib import Path

from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 测试用的具体 Skill ──────────────────────────────────


class DummyReadOnlySkill(Skill):
    """一个最简的只读 Skill，用于测试基类机制"""

    name = "test.dummy_readonly"
    description = "测试用只读 Skill"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        return context.project_path.exists()

    def run(self, context, inputs=None):
        return SkillResult(
            success=True,
            summary="只读扫描完成",
            data={"files_found": 42},
        )


class DummyWriteSkill(Skill):
    """一个会修改文件的 Skill，测试 R1 风险等级"""

    name = "test.dummy_write"
    description = "测试用写入 Skill"
    risk_level = RiskLevel.R1
    task_type = TaskType.DOCUMENT

    def can_run(self, context) -> bool:
        return True

    def run(self, context, inputs=None):
        return SkillResult(
            success=True,
            summary="文档已生成",
            changed_files=["README.md"],
            risks=["修改了项目根目录文件"],
        )


# ── 测试用例 ────────────────────────────────────────────


def test_auto_registration():
    """测试 __init_subclass__ 自动注册"""
    registry = Skill.get_registry()
    assert "test.dummy_readonly" in registry
    assert "test.dummy_write" in registry
    assert registry["test.dummy_readonly"] is DummyReadOnlySkill
    assert registry["test.dummy_write"] is DummyWriteSkill


def test_get_skill():
    """测试按名称获取 Skill 类"""
    assert Skill.get_skill("test.dummy_readonly") is DummyReadOnlySkill
    assert Skill.get_skill("nonexistent") is None


def test_create_instance():
    """测试按名称创建 Skill 实例"""
    skill = Skill.create("test.dummy_readonly")
    assert isinstance(skill, DummyReadOnlySkill)
    assert skill.name == "test.dummy_readonly"


def test_create_nonexistent_raises():
    """测试创建不存在的 Skill 抛出 KeyError"""
    try:
        Skill.create("nonexistent")
        assert False, "应该抛出 KeyError"
    except KeyError as e:
        assert "nonexistent" in str(e)


def test_risk_level_properties():
    """测试风险等级的辅助属性"""
    assert RiskLevel.R0.can_auto_execute is True
    assert RiskLevel.R1.can_auto_execute is False
    assert RiskLevel.R2.can_auto_execute is False
    assert RiskLevel.R3.can_auto_execute is False

    assert RiskLevel.R0.requires_rollback_plan is False
    assert RiskLevel.R1.requires_rollback_plan is False
    assert RiskLevel.R2.requires_rollback_plan is True
    assert RiskLevel.R3.requires_rollback_plan is True


def test_can_run_check():
    """测试 can_run 前置条件检查"""
    from smartdev.models import ProjectContext

    # 项目路径存在时 can_run 返回 True
    context = ProjectContext(project_path=Path("/tmp"))
    skill = DummyReadOnlySkill()
    assert skill.can_run(context) is True

    # 项目路径不存在时 can_run 返回 False
    context = ProjectContext(project_path=Path("/nonexistent/path/abc123"))
    assert skill.can_run(context) is False


def test_run_returns_skill_result():
    """测试 run() 返回正确的 SkillResult"""
    from smartdev.models import ProjectContext

    context = ProjectContext(project_path=Path("/tmp"))

    # 只读 Skill
    readonly_skill = DummyReadOnlySkill()
    result = readonly_skill.run(context)
    assert isinstance(result, SkillResult)
    assert result.success is True
    assert result.data == {"files_found": 42}
    assert result.changed_files == []

    # 写入 Skill
    write_skill = DummyWriteSkill()
    result = write_skill.run(context)
    assert result.success is True
    assert result.changed_files == ["README.md"]
    assert len(result.risks) == 1


def test_describe_metadata():
    """测试 describe() 返回正确的元数据"""
    skill = DummyReadOnlySkill()
    desc = skill.describe()
    assert desc["name"] == "test.dummy_readonly"
    assert desc["description"] == "测试用只读 Skill"
    assert desc["risk_level"] == "R0"
    assert desc["task_type"] == "diagnose"
