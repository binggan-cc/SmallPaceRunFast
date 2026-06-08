"""
Skill: doc.update.plan — 文档更新计划（R0 只读）

功能：消费 doc.consistency 的 issues 列表，输出结构化文档更新计划。
      区分三类更新性质，明确"应该改什么"和"不应该改什么"。

风险：R0（只读，不修改任何文件）

三类更新性质（phase-11c-design.md §7 Step 5）：
─────────────────────────────────────────────
1. status_sync      状态同步
   来源：rule2（Phase 状态/版本号不一致）、rule4（测试基线过时）
   特征：有明确的新值，机械替换即可
   示例："把 CLAUDE.md 里的 637 改成 1102"

2. capability_boundary  能力边界
   来源：rule1（Skill/CLI 未文档化）、rule3（过度承诺）
   特征：需要新增或删除能力描述，不只是数字替换
   示例："在 README 新增 doc.map / doc.consistency 的说明"

3. expression_alignment  表达口径
   来源：多文档间表达不一致（rule2 Phase 状态跨文档）
   特征：意思对但措辞不统一，需要对齐
   示例："CHANGELOG 写 Phase 11A 完成，progress.md 写进行中"

不做：
──────
- 不生成实际文档内容（那是高阶模型 Doc Steward 的工作）
- 不自动 apply（那是 doc.patch.propose + 人确认的工作）
- 不修改任何文件
- 不删除历史文档节

对应文档：
- docs/phase-11c-design.md §7 Step 5
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 更新性质分类 ──────────────────────────────────────────

# issue type → update_kind 映射
_ISSUE_KIND_MAP: dict[str, str] = {
    "stale_capability":                          "capability_boundary",
    "phase_status_mismatch":                     "status_sync",
    "capability_overpromise":                    "capability_boundary",
    "stale_test_baseline":                       "status_sync",
    "public_surface_changed_docs_not_updated":   "capability_boundary",
}

# update_kind 的人类可读描述
_KIND_LABELS: dict[str, str] = {
    "status_sync":           "状态同步（有明确新值，机械替换）",
    "capability_boundary":   "能力边界（新增/修正能力描述）",
    "expression_alignment":  "表达口径（对齐多文档间的措辞）",
}

# 明确不应该改动的文档（设计文档和历史记录）
_NO_CHANGE_PATTERNS = [
    ("-design.md",    "设计文档记录决策历史，不应因代码变更而修改"),
    ("CHANGELOG.md",  "CHANGELOG 是追加记录，不应修改已有章节；只能在 Unreleased 节追加"),
    ("LICENSE",       "许可证文件不应修改"),
    (".gitignore",    "gitignore 由代码结构决定，不属于文档更新"),
]


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class UpdateItem:
    """单个文档的更新计划条目。

    Attributes:
        doc:          文档相对路径
        update_kind:  更新性质（status_sync / capability_boundary / expression_alignment）
        priority:     优先级（high / medium / low，来自触发 issue 的最高 severity）
        reasons:      触发更新的原因列表（来自 issues 的 code_fact + doc_claim）
        suggestions:  具体更新建议（确定性部分，如"把 N 改成 M"）
        issues:       关联的 issue type 列表
    """
    doc: str
    update_kind: str
    priority: str
    reasons: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "doc": self.doc,
            "update_kind": self.update_kind,
            "update_kind_label": _KIND_LABELS.get(self.update_kind, self.update_kind),
            "priority": self.priority,
            "reasons": self.reasons,
            "suggestions": self.suggestions,
            "issues": self.issues,
        }


@dataclass
class NoChangeItem:
    """明确不应改动的文档条目。

    Attributes:
        doc:    文档相对路径
        reason: 不应修改的理由
    """
    doc: str
    reason: str

    def to_dict(self) -> dict:
        return {"doc": self.doc, "reason": self.reason}


# ── 优先级映射 ────────────────────────────────────────────

_SEVERITY_PRIORITY = {"high": "high", "medium": "medium", "low": "low"}


def _max_priority(severities: list[str]) -> str:
    order = {"high": 0, "medium": 1, "low": 2}
    if not severities:
        return "low"
    return min(severities, key=lambda s: order.get(s, 2))


# ── 核心规划逻辑 ──────────────────────────────────────────


def _is_no_change_doc(doc_path: str) -> tuple[bool, str]:
    """判断文档是否属于"不应修改"类别，返回 (是否不改, 原因)。"""
    for pattern, reason in _NO_CHANGE_PATTERNS:
        if pattern in doc_path:
            # CHANGELOG 特殊：允许追加 Unreleased 节，但不修改历史节
            if pattern == "CHANGELOG.md":
                return True, reason
            return True, reason
    return False, ""


def _build_suggestion(issue: dict) -> str:
    """从单个 issue 生成确定性更新建议。"""
    issue_type = issue.get("type", "")
    code_fact = issue.get("code_fact", "")
    doc_claim = issue.get("doc_claim", "")

    if issue_type == "stale_test_baseline":
        # 从 code_fact 提取数字
        import re
        m_fact = re.search(r"\b(\d+)\b", code_fact)
        m_claim = re.search(r"\b(\d+)\b", doc_claim)
        if m_fact and m_claim:
            return f"将 '{m_claim.group(1)} passed' 替换为 '{m_fact.group(1)} passed'"
        return f"更新测试基线数字：{code_fact}"

    if issue_type == "phase_status_mismatch":
        import re
        # 版本号不符
        if "pyproject" in code_fact or "version" in code_fact.lower():
            m = re.search(r"\b\d+\.\d+\.\d+\b", code_fact)
            if m:
                return f"同步版本号至 {m.group(0)}"
        # Phase 状态缺失
        if "缺少" in doc_claim:
            phases = re.findall(r"Phase\s+\w+", doc_claim)
            if phases:
                return f"补充 {', '.join(phases)} 的状态描述"
        return f"对齐 Phase 状态描述：{doc_claim[:60]}"

    if issue_type == "stale_capability":
        if "CLI" in code_fact:
            return f"在文档中补充 CLI 命令说明：{doc_claim[:80]}"
        return f"补充能力描述：{code_fact[:80]}"

    if issue_type == "capability_overpromise":
        return f"检查并移除过度承诺的能力描述（参考设计文档的 ❌ 声明）"

    if issue_type == "public_surface_changed_docs_not_updated":
        return f"更新公共接口变更说明（{code_fact[:60]}）"

    return f"参考 issue：{issue_type}"


def build_update_plan(
    issues: list[dict],
    doc_map_data: dict | None = None,
) -> tuple[list[UpdateItem], list[NoChangeItem]]:
    """从 issues 列表构建文档更新计划。

    算法：
    1. 按 doc 分组 issues
    2. 对每个 doc：
       - 判断是否属于"不应修改"类别
       - 计算 update_kind（取优先级最高的 issue type 对应的 kind）
       - 计算 priority（取最高 severity）
       - 收集所有 reasons 和 suggestions
    3. 对所有涉及 doc 中属于"不应修改"的单独列出
    4. 按 priority 排序（high → medium → low）

    参数：
        issues:       doc.consistency 输出的 issues 列表
        doc_map_data: doc.map 输出（可选，用于补充文档元数据）

    返回：
        (update_items, no_change_items)
    """
    # 按 doc 分组
    doc_groups: dict[str, list[dict]] = {}
    for issue in issues:
        doc = issue.get("doc", "")
        # 一个 issue 可能涉及多个文档（逗号分隔）
        for d in [d.strip() for d in doc.split(",")]:
            if d and d != "(all docs)":
                doc_groups.setdefault(d, []).append(issue)
        if doc == "(all docs)":
            doc_groups.setdefault("README.md", []).append(issue)

    update_items: list[UpdateItem] = []
    no_change_items: list[NoChangeItem] = []
    seen_no_change: set[str] = set()

    # 处理每个受影响文档
    for doc_path, doc_issues in sorted(doc_groups.items()):
        is_no_change, no_change_reason = _is_no_change_doc(doc_path)

        if is_no_change:
            if doc_path not in seen_no_change:
                no_change_items.append(NoChangeItem(doc=doc_path, reason=no_change_reason))
                seen_no_change.add(doc_path)
            continue

        # 计算 update_kind（取最重要的 issue type 的 kind）
        # 优先级：capability_boundary > status_sync > expression_alignment
        kind_priority = {"capability_boundary": 0, "status_sync": 1, "expression_alignment": 2}
        kinds = [_ISSUE_KIND_MAP.get(i.get("type", ""), "expression_alignment") for i in doc_issues]
        update_kind = min(kinds, key=lambda k: kind_priority.get(k, 2)) if kinds else "status_sync"

        # 计算优先级
        severities = [i.get("severity", "low") for i in doc_issues]
        priority = _max_priority(severities)

        # 收集 reasons（去重）
        reasons: list[str] = []
        seen_reasons: set[str] = set()
        for issue in doc_issues:
            fact = issue.get("code_fact", "")
            claim = issue.get("doc_claim", "")
            reason_str = f"{fact} ← {claim}" if fact and claim else fact or claim
            if reason_str and reason_str not in seen_reasons:
                seen_reasons.add(reason_str)
                reasons.append(reason_str[:120])

        # 生成 suggestions
        suggestions: list[str] = []
        seen_sugg: set[str] = set()
        for issue in doc_issues:
            sugg = _build_suggestion(issue)
            if sugg not in seen_sugg:
                seen_sugg.add(sugg)
                suggestions.append(sugg)

        # 收集 issue types
        issue_types = list(dict.fromkeys(i.get("type", "") for i in doc_issues))

        update_items.append(UpdateItem(
            doc=doc_path,
            update_kind=update_kind,
            priority=priority,
            reasons=reasons,
            suggestions=suggestions,
            issues=issue_types,
        ))

    # 按 priority 排序
    priority_order = {"high": 0, "medium": 1, "low": 2}
    update_items.sort(key=lambda x: priority_order.get(x.priority, 2))

    return update_items, no_change_items


# ── Skill ─────────────────────────────────────────────────


class DocUpdatePlanSkill(Skill):
    """文档更新计划 Skill（R0 只读）

    消费 doc.consistency 的 issues，输出结构化更新计划：
    - update_items：需要更新的文档（按优先级排序）
    - no_change_items：不应修改的文档（含理由）

    inputs 参数（均为可选）：
        consistency_issues: list[dict]  doc.consistency 输出的 issues 列表
        doc_map:            dict        doc.map 输出（补充文档元数据，可选）

    如果不传 consistency_issues，自动运行 doc.consistency 获取。

    使用示例：
        # 最简调用（自动运行 doc.consistency）
        result = Skill.create("doc.update.plan").run(context)

        # 传入已有 issues
        consistency_result = Skill.create("doc.consistency").run(context)
        result = Skill.create("doc.update.plan").run(context, {
            "consistency_issues": consistency_result.data["issues"],
        })
    """

    name = "doc.update.plan"
    description = "消费 doc.consistency issues，输出结构化文档更新计划（哪些改/为什么/不该改哪些）"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        return context.project_path.exists()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path

        # ── 获取 consistency issues ──────────────────────────
        # 区分"明确传了空列表（已检查）"和"未传（需自动生成）"
        raw_issues = inputs.get("consistency_issues")
        if raw_issues is not None:
            # 调用方已提供（包括空列表），直接使用，不再自动运行
            issues: list[dict] = list(raw_issues)
        else:
            # 未传，自动运行 doc.consistency
            issues = []
            try:
                doc_map_input = inputs.get("doc_map") or {}
                consistency_result = Skill.create("doc.consistency").run(
                    context,
                    {"doc_map": doc_map_input} if doc_map_input else {},
                )
                issues = consistency_result.data.get("issues", [])
            except Exception:
                issues = []

        # ── 获取 doc_map（可选，补充元数据）──────────────────
        doc_map_data: dict = inputs.get("doc_map") or {}

        # ── 构建更新计划 ────────────────────────────────────
        update_items, no_change_items = build_update_plan(issues, doc_map_data)

        generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        update_count = len(update_items)

        # ── 生成摘要 ─────────────────────────────────────────
        if not issues:
            summary = "文档与代码一致，无需更新任何文档。"
        elif update_count == 0:
            summary = f"检查到 {len(issues)} 个 issue，但所有涉及文档均不应修改。"
        else:
            high_count = sum(1 for i in update_items if i.priority == "high")
            summary_lines = [f"文档更新计划：{update_count} 个文档需要更新"]
            if high_count:
                summary_lines.append(f"  ⚠️ 其中 {high_count} 个优先级 high（能力边界问题）")
            by_kind: dict[str, int] = {}
            for item in update_items:
                by_kind[item.update_kind] = by_kind.get(item.update_kind, 0) + 1
            for kind, count in sorted(by_kind.items()):
                label = _KIND_LABELS.get(kind, kind)
                summary_lines.append(f"  - {label}: {count} 个")
            if no_change_items:
                summary_lines.append(f"  🔒 {len(no_change_items)} 个文档不应修改")
            summary = "\n".join(summary_lines)

        return SkillResult(
            success=True,
            summary=summary,
            data={
                "generated_at": generated_at,
                "update_count": update_count,
                "update_items": [i.to_dict() for i in update_items],
                "no_change_items": [i.to_dict() for i in no_change_items],
                "issue_count_input": len(issues),
            },
            next_steps=_build_next_steps(update_items, no_change_items),
        )


def _build_next_steps(
    update_items: list[UpdateItem],
    no_change_items: list[NoChangeItem],
) -> list[str]:
    steps: list[str] = []
    if not update_items:
        steps.append("文档无需更新，可继续开发。")
        return steps

    high = [i for i in update_items if i.priority == "high"]
    if high:
        steps.append(
            f"优先处理 {len(high)} 个 high 优先级文档："
            f"{', '.join(i.doc for i in high[:3])}"
        )

    status_sync = [i for i in update_items if i.update_kind == "status_sync"]
    if status_sync:
        steps.append(
            f"{len(status_sync)} 个状态同步更新可由 doc.patch.propose 自动生成 patch。"
        )

    capability = [i for i in update_items if i.update_kind == "capability_boundary"]
    if capability:
        steps.append(
            f"{len(capability)} 个能力边界更新建议交给 Doc Steward 审阅后生成内容。"
        )

    steps.append("运行 doc.patch.propose 对 status_sync 类型生成可应用的文档 patch。")
    return steps
