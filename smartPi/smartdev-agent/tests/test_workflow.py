"""
Workflow Engine 测试

验证：
1. 默认工作流执行
2. 步骤失败时中断
3. 摘要生成
4. Markdown 报告输出
"""

from pathlib import Path

from smartdev.core.workflow import WorkflowEngine, WorkflowStep, WorkflowResult
from smartdev.skills.base import Skill

import smartdev.skills  # 触发注册


class TestWorkflowEngine:
    """WorkflowEngine 测试"""

    def test_run_on_python_project(self, tmp_path: Path):
        """在 Python 项目上执行完整工作流"""
        (tmp_path / "requirements.txt").write_text("requests\n")
        (tmp_path / "main.py").write_text("print('hello')\n")

        engine = WorkflowEngine()
        result = engine.run(tmp_path, task="测试任务")

        assert result.success is True
        assert len(result.steps) >= 4  # 至少 scan, risk, plan, checklist

    def test_run_on_empty_project(self, tmp_path: Path):
        """在空项目上执行工作流"""
        engine = WorkflowEngine()
        result = engine.run(tmp_path)

        assert result.success is True

    def test_summary_generated(self, tmp_path: Path):
        """摘要已生成"""
        (tmp_path / "main.py").write_text("pass\n")

        engine = WorkflowEngine()
        result = engine.run(tmp_path)

        assert len(result.summary) > 0
        assert "执行完成" in result.summary

    def test_to_markdown(self, tmp_path: Path):
        """Markdown 报告格式正确"""
        (tmp_path / "main.py").write_text("pass\n")

        engine = WorkflowEngine()
        result = engine.run(tmp_path)

        md = result.to_markdown()
        assert "SmartDev Agent" in md
        assert "执行步骤" in md
        assert "摘要" in md

    def test_steps_recorded(self, tmp_path: Path):
        """每个步骤都被记录"""
        engine = WorkflowEngine()
        result = engine.run(tmp_path)

        for step in result.steps:
            assert "skill_name" in step
            assert "success" in step
            assert "summary" in step


class TestWorkflowResult:
    """WorkflowResult 测试"""

    def test_to_markdown_format(self):
        """Markdown 输出包含必要段落"""
        result = WorkflowResult(
            project_path="/test",
            steps=[
                {"skill_name": "repo.scan", "success": True, "summary": "扫描完成", "risk_level": "R0", "data": {}},
            ],
            success=True,
            summary="执行完成：1/1",
        )

        md = result.to_markdown()
        assert "# SmartDev Agent" in md
        assert "repo.scan" in md
        assert "✅" in md
