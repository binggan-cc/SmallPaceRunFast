"""
Skill: doc.patch.propose — 文档 Patch 生成（R1，不落盘）

功能：消费 doc.update.plan 的 update_items，对 status_sync 类型的更新
      生成确定性 find-replace patch，对 capability_boundary 类型只生成 hint。

风险：R1（只写 .smartdev/patches/，不修改任何文档源文件）

两类处理策略（phase-11c-design.md §7 Step 6）：
──────────────────────────────────────────────
1. status_sync → 确定性 find-replace patch
   - 从 issue 中提取 old value / new value
   - 复用 Phase 9 `build_find_replace_patch` + `save_patch`
   - 只针对涉及的文档文件（不是全项目 glob）
   - patch_id 持久化到 .smartdev/patches/，不自动 apply

2. capability_boundary / expression_alignment → hint（不生成 patch）
   - 需要人工或 Doc Steward 起草新内容
   - 输出 hint：涉及文档、更新方向、原因
   - 不生成 patch，不修改任何文件

apply 路径：
────────────
生成 patch 后，通过 CLI 显式 apply：
    smartdev apply --patch-id <id> --project <path>

设计约束：
─────────
- 不调用 LLM 生成内容
- 不自动 apply
- 不修改文档源文件
- find-replace 只在文档文件范围内执行（`*.md`, `*.rst`, `*.txt`）

对应文档：
- docs/phase-11c-design.md §7 Step 6
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class DocPatchProposal:
    """单个文档 patch 提案。

    Attributes:
        patch_id:    patch 唯一 ID（来自 save_patch）
        doc:         目标文档路径
        find:        查找字符串
        replace:     替换字符串
        summary:     变更摘要
        issue_type:  触发此 patch 的 issue type
        patch_path:  持久化路径（.smartdev/patches/<patch_id>.json）
    """
    patch_id: str
    doc: str
    find: str
    replace: str
    summary: str
    issue_type: str
    patch_path: str = ""

    def to_dict(self) -> dict:
        return {
            "patch_id": self.patch_id,
            "doc": self.doc,
            "find": self.find,
            "replace": self.replace,
            "summary": self.summary,
            "issue_type": self.issue_type,
            "patch_path": self.patch_path,
        }


@dataclass
class DocPatchHint:
    """不生成 patch 的文档更新 hint（需人工起草）。

    Attributes:
        doc:          目标文档路径
        update_kind:  更新性质
        direction:    更新方向描述
        reason:       为什么需要更新
        issue_types:  触发此 hint 的 issue types
    """
    doc: str
    update_kind: str
    direction: str
    reason: str
    issue_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "doc": self.doc,
            "update_kind": self.update_kind,
            "direction": self.direction,
            "reason": self.reason,
            "issue_types": self.issue_types,
        }


# ── find-replace 提取逻辑 ─────────────────────────────────

# 测试基线数字正则（匹配 "637 passed" / "637 tests" 等）
_BASELINE_RE = re.compile(r"\b(\d{3,})\s+(passed|tests?)\b", re.IGNORECASE)


def _extract_test_baseline_pair(issue: dict) -> tuple[str, str] | None:
    """从 stale_test_baseline issue 提取 (old_str, new_str)。

    例：code_fact="1145 passed"，doc_claim="637 passed"
    → find="637 passed", replace="1145 passed"
    """
    code_fact = issue.get("code_fact", "")
    doc_claim = issue.get("doc_claim", "")

    m_fact = _BASELINE_RE.search(code_fact)
    m_claim = _BASELINE_RE.search(doc_claim)

    if m_fact and m_claim:
        old_n = m_claim.group(1)
        old_unit = m_claim.group(2)
        new_n = m_fact.group(1)
        new_unit = m_fact.group(2)
        old_str = f"{old_n} {old_unit}"
        new_str = f"{new_n} {new_unit}"
        if old_str != new_str:
            return old_str, new_str
    return None


def _extract_version_pair(issue: dict) -> tuple[str, str] | None:
    """从 phase_status_mismatch issue（版本类）提取 (old_str, new_str)。

    例：code_fact="pyproject.toml version = 0.4.0"，doc_claim="CHANGELOG = v0.3.0"
    → find="0.3.0", replace="0.4.0"（只有 changelog 类型才做，通常不处理）
    """
    code_fact = issue.get("code_fact", "")
    doc_claim = issue.get("doc_claim", "")

    ver_re = re.compile(r"\bv?(\d+\.\d+\.\d+)\b")
    m_fact = ver_re.search(code_fact)
    m_claim = ver_re.search(doc_claim)

    if m_fact and m_claim:
        old_ver = m_claim.group(1)
        new_ver = m_fact.group(1)
        if old_ver != new_ver:
            # 只替换版本号（不含 v 前缀，避免误替换）
            return old_ver, new_ver
    return None


def _build_doc_glob(doc_path: str) -> str:
    """把文档路径转为 glob（只在该文件范围内搜索）。"""
    # 直接用路径作为 glob，但 build_find_replace_patch 的 glob 是相对项目根的
    return doc_path


# ── 核心生成逻辑 ──────────────────────────────────────────


def _process_status_sync_item(
    item: dict,
    issues: list[dict],
    project_path: Path,
    patches_dir: Path,
) -> list[DocPatchProposal]:
    """对 status_sync 类型的 update_item 生成 find-replace patch。"""
    from smartdev.core.patch import build_find_replace_patch, save_patch

    proposals: list[DocPatchProposal] = []
    doc_path = item.get("doc", "")
    issue_types = item.get("issues", [])

    # 找到和这个 doc 相关的所有 status_sync issues
    relevant_issues = [
        i for i in issues
        if i.get("type") in ("stale_test_baseline", "phase_status_mismatch")
        and (doc_path in i.get("doc", "") or i.get("doc", "") in doc_path)
    ]

    for issue in relevant_issues:
        issue_type = issue.get("type", "")
        pair: tuple[str, str] | None = None

        if issue_type == "stale_test_baseline":
            pair = _extract_test_baseline_pair(issue)
        elif issue_type == "phase_status_mismatch":
            # 只处理版本号类型（Phase 描述差异太复杂，留给 hint）
            code_fact = issue.get("code_fact", "")
            if "version" in code_fact.lower() or "pyproject" in code_fact.lower():
                pair = _extract_version_pair(issue)

        if pair is None:
            continue

        find_str, replace_str = pair
        if not find_str or not replace_str or find_str == replace_str:
            continue

        # 验证 find_str 在目标文档中是否存在
        doc_abs = project_path / doc_path
        if not doc_abs.exists():
            continue
        try:
            content = doc_abs.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if find_str not in content:
            continue

        # 生成 patch（只针对该文件）
        try:
            patch = build_find_replace_patch(
                project_path=project_path,
                find=find_str,
                replace=replace_str,
                include_glob=doc_path,
            )
        except Exception:
            continue

        if not patch.files:
            continue

        # 持久化
        try:
            patch_id = save_patch(patch, patches_dir)
            patch_file = str(patches_dir / f"{patch_id}.json")
        except Exception:
            patch_id = f"doc-{int(time.time())}"
            patch_file = ""

        summary = (
            f"{doc_path}：将 '{find_str}' 替换为 '{replace_str}'"
        )
        proposals.append(DocPatchProposal(
            patch_id=patch_id,
            doc=doc_path,
            find=find_str,
            replace=replace_str,
            summary=summary,
            issue_type=issue_type,
            patch_path=patch_file,
        ))

    return proposals


def _process_capability_item(item: dict) -> DocPatchHint:
    """对 capability_boundary / expression_alignment 类型生成 hint。"""
    doc = item.get("doc", "")
    update_kind = item.get("update_kind", "capability_boundary")
    reasons = item.get("reasons", [])
    suggestions = item.get("suggestions", [])
    issue_types = item.get("issues", [])

    # 生成方向描述
    if update_kind == "capability_boundary":
        direction = "新增或修正能力描述（需人工或 Doc Steward 起草内容后再 patch）"
    else:
        direction = "对齐多文档间的措辞表达（需人工确认后再 patch）"

    reason = "; ".join(r[:80] for r in reasons[:3]) if reasons else "参见 doc.consistency 输出"

    return DocPatchHint(
        doc=doc,
        update_kind=update_kind,
        direction=direction,
        reason=reason,
        issue_types=issue_types,
    )


# ── Skill ─────────────────────────────────────────────────


class DocPatchProposeSkill(Skill):
    """文档 Patch 生成 Skill（R1，只写 .smartdev/patches/）

    消费 doc.update.plan 的 update_items：
    - status_sync → 生成确定性 find-replace patch，持久化到 .smartdev/patches/
    - capability_boundary / expression_alignment → 生成 hint，不生成 patch

    不修改任何文档源文件。apply 需通过 CLI 显式执行。

    inputs 参数（均为可选）：
        update_items:       list[dict]  doc.update.plan 输出的 update_items
        consistency_issues: list[dict]  doc.consistency 输出的 issues
                            （不传 update_items 时自动运行 doc.update.plan）

    使用示例：
        # 最简调用（自动运行 doc.update.plan → doc.consistency）
        result = Skill.create("doc.patch.propose").run(context)

        # 传入 update_items
        plan = Skill.create("doc.update.plan").run(context)
        result = Skill.create("doc.patch.propose").run(context, {
            "update_items": plan.data["update_items"],
            "consistency_issues": consistency_result.data["issues"],
        })
    """

    name = "doc.patch.propose"
    description = "对 status_sync 类文档更新生成确定性 find-replace patch，持久化到 .smartdev/patches/"
    risk_level = RiskLevel.R1
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        return context.project_path.exists()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path
        patches_dir = project / ".smartdev" / "patches"

        # ── 获取 update_items ────────────────────────────────
        raw_items = inputs.get("update_items")
        raw_issues = inputs.get("consistency_issues")

        if raw_items is not None:
            update_items: list[dict] = list(raw_items)
            consistency_issues: list[dict] = list(raw_issues or [])
        else:
            # 自动运行 doc.update.plan
            try:
                plan_inputs: dict = {}
                if raw_issues is not None:
                    plan_inputs["consistency_issues"] = raw_issues
                plan_result = Skill.create("doc.update.plan").run(context, plan_inputs)
                update_items = plan_result.data.get("update_items", [])
                # 也从 plan 结果里拿到 issue_count，用于后续 patch 提取
            except Exception:
                update_items = []

            # 获取 consistency issues（用于 find-replace 提取）
            if raw_issues is not None:
                consistency_issues = list(raw_issues)
            else:
                try:
                    cons_result = Skill.create("doc.consistency").run(context)
                    consistency_issues = cons_result.data.get("issues", [])
                except Exception:
                    consistency_issues = []

        # ── 分类处理 ────────────────────────────────────────
        proposals: list[DocPatchProposal] = []
        hints: list[DocPatchHint] = []

        for item in update_items:
            update_kind = item.get("update_kind", "")
            if update_kind == "status_sync":
                new_proposals = _process_status_sync_item(
                    item, consistency_issues, project, patches_dir
                )
                proposals.extend(new_proposals)
            else:
                # capability_boundary / expression_alignment → hint
                hint = _process_capability_item(item)
                hints.append(hint)

        generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        patch_count = len(proposals)
        hint_count = len(hints)

        # ── 摘要 ─────────────────────────────────────────────
        if patch_count == 0 and hint_count == 0:
            summary = "无需生成文档 patch（无 update_items 或均无法自动化）。"
        else:
            lines = []
            if patch_count:
                lines.append(f"生成 {patch_count} 个文档 patch（status_sync 类型）")
            if hint_count:
                lines.append(f"{hint_count} 个文档需人工起草内容（capability_boundary 类型）")
            if patch_count:
                lines.append(f"patch 已持久化到 .smartdev/patches/，运行 apply 命令应用")
            summary = "；".join(lines)

        return SkillResult(
            success=True,
            summary=summary,
            data={
                "generated_at": generated_at,
                "patch_count": patch_count,
                "hint_count": hint_count,
                "patches": [p.to_dict() for p in proposals],
                "hints": [h.to_dict() for h in hints],
            },
            changed_files=[str(patches_dir / f"{p.patch_id}.json") for p in proposals],
            next_steps=_build_next_steps(proposals, hints),
        )


def _build_next_steps(
    proposals: list[DocPatchProposal],
    hints: list[DocPatchHint],
) -> list[str]:
    steps: list[str] = []
    if proposals:
        ids = [p.patch_id for p in proposals[:3]]
        steps.append(
            f"运行以下命令 apply 文档 patch："
            f"\n  " + "\n  ".join(f"smartdev apply --patch-id {pid} --project ." for pid in ids)
        )
    if hints:
        docs = list(dict.fromkeys(h.doc for h in hints))
        steps.append(
            f"以下 {len(hints)} 个文档需人工或 Doc Steward 起草内容后再 patch："
            f" {', '.join(docs[:3])}"
        )
    if not proposals and not hints:
        steps.append("文档与代码一致，无需 patch。")
    return steps
