"""
Reporter — 执行前/后输出模板

设计原理：
─────────
Reporter 负责将 Skill 执行前后的信息格式化为协议要求的标准模板。
它不决定"做什么"，只负责"怎么呈现"。

为什么 Reporter 独立于 Skill？
─────────────────────────────
1. 所有 Skill 的输出格式应该统一，用户不需要适应不同 Skill 的输出风格
2. Reporter 可以独立演进（如后续支持 JSON/Markdown/HTML 输出）
3. Skill 只关心业务逻辑，不关心格式化

对应文档：
- smartPi/docs/smartdev-agent-protocol.md §6（执行前必须输出）
- smartPi/docs/smartdev-agent-protocol.md §7（执行后必须输出）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from smartdev.models import RiskLevel, SkillResult


# ── 执行前输出（协议 §6）──────────────────────────────────

@dataclass
class PreExecutionReport:
    """执行前报告，对应协议 §6 的 6 段内容

    Attributes:
        task: 本轮任务 — 要解决什么问题
        current_state: 当前状态 — 项目已什么，当前问题是什么
        scope: 修改范围 — 预计修改的文件或模块
        excluded_scope: 不修改范围 — 明确不会处理的内容
        risks: 风险点 — 可能影响的功能、样式、数据或接口
        acceptance_criteria: 验收标准 — 如何判断任务完成
    """
    task: str
    current_state: str
    scope: list[str] = field(default_factory=list)
    excluded_scope: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """格式化为协议 §6 要求的 Markdown 格式"""
        lines = [
            "# 本轮任务",
            "",
            self.task,
            "",
            "# 当前状态",
            "",
            self.current_state,
            "",
            "# 修改范围",
            "",
        ]
        for item in self.scope:
            lines.append(f"- {item}")
        if not self.scope:
            lines.append("- （待定）")

        lines.extend(["", "# 不修改范围", ""])
        for item in self.excluded_scope:
            lines.append(f"- {item}")
        if not self.excluded_scope:
            lines.append("- 无额外排除")

        lines.extend(["", "# 风险点", ""])
        for item in self.risks:
            lines.append(f"- {item}")
        if not self.risks:
            lines.append("- 无明显风险")

        lines.extend(["", "# 验收标准", ""])
        for item in self.acceptance_criteria:
            lines.append(f"- [ ] {item}")
        if not self.acceptance_criteria:
            lines.append("- （待定义）")

        return "\n".join(lines)


# ── 执行后输出（协议 §7）──────────────────────────────────

@dataclass
class PostExecutionReport:
    """执行后报告，对应协议 §7 的 6 段内容

    Attributes:
        completed: 本次完成 — 实际完成的修改
        modified_files: 修改文件 — 所有修改过的文件
        key_changes: 关键变更 — 每个重要修改的原因
        verification: 验证方式 — 如何运行、检查、测试
        remaining_issues: 遗留问题 — 发现但未处理的问题
        next_steps: 下一步建议 — 下一轮最适合处理的任务
    """
    completed: list[str] = field(default_factory=list)
    modified_files: list[str] = field(default_factory=list)
    key_changes: list[str] = field(default_factory=list)
    verification: list[str] = field(default_factory=list)
    remaining_issues: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        """格式化为协议 §7 要求的 Markdown 格式"""
        lines = [
            "# 本次完成",
            "",
        ]
        for item in self.completed:
            lines.append(f"- {item}")

        lines.extend(["", "# 修改文件", ""])
        for item in self.modified_files:
            lines.append(f"- `{item}`")

        lines.extend(["", "# 关键变更", ""])
        for item in self.key_changes:
            lines.append(f"- {item}")

        lines.extend(["", "# 验证方式", ""])
        for item in self.verification:
            lines.append(f"- {item}")

        lines.extend(["", "# 遗留问题", ""])
        for item in self.remaining_issues:
            lines.append(f"- {item}")
        if not self.remaining_issues:
            lines.append("- 无")

        lines.extend(["", "# 下一步建议", ""])
        for item in self.next_steps:
            lines.append(f"- {item}")

        return "\n".join(lines)


# ── SkillResult 转换器 ────────────────────────────────────
# 为什么需要转换器？
#   Skill 返回的是 SkillResult（结构化数据），
#   但用户需要看的是 Markdown 格式的报告。
#   转换器连接这两者。

def skill_result_to_post_report(result: SkillResult) -> PostExecutionReport:
    """将 SkillResult 转换为执行后报告

    参数：
        result: Skill 的执行结果

    返回：
        PostExecutionReport，可直接调用 to_markdown() 输出
    """
    return PostExecutionReport(
        completed=[result.summary],
        modified_files=result.changed_files,
        key_changes=result.risks,  # risks 在只读场景下可作为"关键发现"
        verification=result.validation,
        remaining_issues=[],
        next_steps=result.next_steps,
    )


# ── 风险等级输出 ──────────────────────────────────────────

def format_risk_notice(risk_level: RiskLevel) -> str:
    """根据风险等级输出对应的提示信息

    参数：
        risk_level: Skill 的风险等级

    返回：
        提示文本
    """
    notices = {
        RiskLevel.R0: "✅ R0 无风险，可直接执行。",
        RiskLevel.R1: "⚠️ R1 低风险，已说明修改范围。",
        RiskLevel.R2: "🔶 R2 中风险，需输出风险与回滚方案，等待确认。",
        RiskLevel.R3: "🔴 R3 高风险，必须先给方案并等待用户确认后才能执行。",
    }
    return notices.get(risk_level, f"❓ 未知风险等级: {risk_level.value}")


def format_execution_header(
    skill_name: str,
    risk_level: RiskLevel,
    timestamp: datetime | None = None,
) -> str:
    """格式化执行头部信息

    参数：
        skill_name: Skill 名称
        risk_level: 风险等级
        timestamp: 执行时间，默认当前时间

    返回：
        格式化的头部文本
    """
    ts = timestamp or datetime.now()
    risk_notice = format_risk_notice(risk_level)

    return (
        f"{'='*60}\n"
        f"SmartDev Agent — {skill_name}\n"
        f"时间: {ts.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"风险: {risk_notice}\n"
        f"{'='*60}"
    )
