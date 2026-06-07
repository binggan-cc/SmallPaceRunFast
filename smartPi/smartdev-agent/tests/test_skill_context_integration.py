"""
Phase 8 Step 4 — Context Layer ↔ Skill 端到端集成验证

验证 WorkflowEngine 在已索引项目上，能让 Skill 真正消费 Context Layer：
- architecture.map 自动用索引依赖图（source=index）
- 传入 target 时，risk.check / task.plan 触发 code.impact 影响分析

设计原则验证：
- 无索引项目：workflow 正常运行，Skill 退回原逻辑（零回归）
- 有索引项目：workflow 串起来消费索引

对应文档：docs/phase-8-design.md §4.5（端到端验证）
"""

from pathlib import Path

import pytest

from smartdev.context.project_index import ProjectIndex
from smartdev.core.workflow import WorkflowEngine


def _build_indexed_python_project(tmp_path: Path) -> Path:
    """建一个有 import 关系的 Python 项目并建立索引。"""
    project = tmp_path / "app"
    project.mkdir()
    (project / "models.py").write_text(
        "class User:\n    def __init__(self, name):\n        self.name = name\n"
    )
    (project / "service.py").write_text(
        "from models import User\n\ndef make(n):\n    return User(n)\n"
    )
    (project / "api.py").write_text(
        "from models import User\nfrom service import make\n\n"
        "def endpoint():\n    return make('x')\n"
    )
    index = ProjectIndex(project)
    index.index()
    index.close()
    return project


def _step(result, skill_name: str) -> dict | None:
    for s in result.steps:
        if s["skill_name"] == skill_name:
            return s
    return None


class TestWorkflowConsumesIndex:
    """workflow 在已索引项目上消费 Context Layer"""

    def test_architecture_map_uses_index_in_workflow(self, tmp_path: Path):
        """workflow 中 architecture.map 自动用索引依赖图（source=index）"""
        project = _build_indexed_python_project(tmp_path)
        engine = WorkflowEngine()
        result = engine.run(project, task="分析架构")

        arch = _step(result, "architecture.map")
        assert arch is not None
        assert arch["success"]
        assert arch["data"]["source"] == "index"

    def test_risk_check_uses_impact_with_target(self, tmp_path: Path):
        """传入 target → workflow 中 risk.check 用 impact 增强"""
        project = _build_indexed_python_project(tmp_path)
        engine = WorkflowEngine()
        result = engine.run(project, task="修改 User 模型", target="models.py")

        risk = _step(result, "risk.check")
        assert risk is not None
        assert risk["success"]
        # 有 target + 索引 → risk_source 应为 impact/both
        assert risk["data"]["risk_source"] in ("impact", "both")
        assert "affected_files" in risk["data"]

    def test_task_plan_annotates_affected_files_with_target(self, tmp_path: Path):
        """传入 target → workflow 中 task.plan 标注受影响文件"""
        project = _build_indexed_python_project(tmp_path)
        engine = WorkflowEngine()
        result = engine.run(project, task="重构用户模型", target="models.py")

        plan = _step(result, "task.plan")
        assert plan is not None
        assert plan["success"]
        assert "impact" in plan["data"]
        affected = plan["data"]["impact"]["affected_files"]
        assert any("service.py" in f for f in affected)
        assert any("api.py" in f for f in affected)

    def test_workflow_overall_success(self, tmp_path: Path):
        """完整 workflow 在已索引项目上成功"""
        project = _build_indexed_python_project(tmp_path)
        engine = WorkflowEngine()
        result = engine.run(project, task="修改 models.py", target="models.py")
        assert result.success


class TestWorkflowWithoutIndexNoRegression:
    """无索引项目：workflow 正常运行，Skill 退回原逻辑"""

    def test_no_index_workflow_still_runs(self, tmp_path: Path):
        """无索引项目 workflow 正常完成"""
        project = tmp_path / "plain"
        project.mkdir()
        (project / "main.py").write_text("import os\n\ndef f():\n    return os.getcwd()\n")

        engine = WorkflowEngine()
        result = engine.run(project, task="改进 main")
        assert result.success

    def test_no_index_architecture_uses_ast(self, tmp_path: Path):
        """无索引 → architecture.map 退回 Python AST"""
        project = tmp_path / "plain2"
        project.mkdir()
        (project / "main.py").write_text("import os\n\ndef f():\n    pass\n")

        engine = WorkflowEngine()
        result = engine.run(project, task="分析")

        arch = _step(result, "architecture.map")
        assert arch is not None
        if arch["success"]:
            assert arch["data"]["source"] == "ast"

    def test_no_target_risk_check_uses_keyword(self, tmp_path: Path):
        """无 target → risk.check 退回关键词匹配"""
        project = _build_indexed_python_project(tmp_path)
        engine = WorkflowEngine()
        # 不传 target
        result = engine.run(project, task="统一 CSS 颜色")

        risk = _step(result, "risk.check")
        assert risk is not None
        if risk["success"]:
            assert risk["data"]["risk_source"] == "keyword"
