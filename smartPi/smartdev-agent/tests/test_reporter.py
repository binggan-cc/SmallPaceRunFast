"""
Reporter 测试

验证：
1. 执行前报告格式正确（协议 §6 的 6 段）
2. 执行后报告格式正确（协议 §7 的 6 段）
3. SkillResult 转换器正确
4. 风险等级提示正确
"""

from smartdev.core.reporter import (
    PreExecutionReport,
    PostExecutionReport,
    format_risk_notice,
    format_execution_header,
    skill_result_to_post_report,
)
from smartdev.models import RiskLevel, SkillResult


class TestPreExecutionReport:
    """执行前报告测试（协议 §6）"""

    def test_to_markdown_has_six_sections(self):
        """输出包含协议 §6 的 6 个段落"""
        report = PreExecutionReport(
            task="统一 design tokens",
            current_state="项目有 3 处重复 token 定义",
            scope=["tokens.css", "variables.css"],
            excluded_scope=["manifest.json"],
            risks=["可能影响暗色模式切换"],
            acceptance_criteria=["token 来源唯一", "覆盖率 >= 95%"],
        )
        md = report.to_markdown()

        assert "# 本轮任务" in md
        assert "# 当前状态" in md
        assert "# 修改范围" in md
        assert "# 不修改范围" in md
        assert "# 风险点" in md
        assert "# 验收标准" in md

    def test_to_markdown_content(self):
        """内容正确填充"""
        report = PreExecutionReport(
            task="修复 Side Panel 宽度",
            current_state="Side Panel 在 320px 下布局错位",
            scope=["sidepanel.css"],
            risks=["影响 400px/480px 布局"],
            acceptance_criteria=["320px 布局正常"],
        )
        md = report.to_markdown()

        assert "修复 Side Panel 宽度" in md
        assert "sidepanel.css" in md
        assert "320px 下布局错位" in md
        assert "- [ ] 320px 布局正常" in md

    def test_empty_fields(self):
        """空字段显示占位文本"""
        report = PreExecutionReport(
            task="测试任务",
            current_state="测试状态",
        )
        md = report.to_markdown()

        assert "（待定）" in md
        assert "无明显风险" in md
        assert "（待定义）" in md


class TestPostExecutionReport:
    """执行后报告测试（协议 §7）"""

    def test_to_markdown_has_six_sections(self):
        """输出包含协议 §7 的 6 个段落"""
        report = PostExecutionReport(
            completed=["完成 token 统一"],
            modified_files=["tokens.css"],
            key_changes=["移除了重复的 color 变量"],
            verification=["运行 pytest", "检查页面显示"],
            remaining_issues=["暗色模式未适配"],
            next_steps=["规划 Dark Mode"],
        )
        md = report.to_markdown()

        assert "# 本次完成" in md
        assert "# 修改文件" in md
        assert "# 关键变更" in md
        assert "# 验证方式" in md
        assert "# 遗留问题" in md
        assert "# 下一步建议" in md

    def test_empty_remaining_shows_none(self):
        """无遗留问题时显示「无」"""
        report = PostExecutionReport()
        md = report.to_markdown()
        assert "- 无" in md


class TestSkillResultConversion:
    """SkillResult → PostExecutionReport 转换测试"""

    def test_conversion(self):
        """转换结果正确"""
        result = SkillResult(
            success=True,
            summary="扫描完成",
            changed_files=["a.py"],
            risks=["发现 3 个问题"],
            validation=["运行测试"],
            next_steps=["继续诊断"],
        )
        report = skill_result_to_post_report(result)

        assert report.completed == ["扫描完成"]
        assert report.modified_files == ["a.py"]
        assert report.verification == ["运行测试"]
        assert report.next_steps == ["继续诊断"]


class TestRiskFormatting:
    """风险提示格式化测试"""

    def test_r0_notice(self):
        """R0 显示无风险"""
        notice = format_risk_notice(RiskLevel.R0)
        assert "R0" in notice
        assert "无风险" in notice

    def test_r3_notice(self):
        """R3 显示高风险"""
        notice = format_risk_notice(RiskLevel.R3)
        assert "R3" in notice
        assert "高风险" in notice
        assert "等待" in notice

    def test_execution_header(self):
        """执行头部包含 Skill 名称和风险等级"""
        header = format_execution_header("repo.scan", RiskLevel.R0)
        assert "repo.scan" in header
        assert "R0" in header
        assert "=" in header
