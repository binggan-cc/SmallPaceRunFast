"""
Handoff Doc — Phase 11D Step 4 核心交付物（R1，只写 .smartdev/runs/）

功能：
─────
读取 .smartdev/runs/<run_id>/ 下的 task-card.md + scope.json，
聚合 11C 的确定性产物（manifest / snapshot / doc_map / doc.consistency），
组装生成 doc-steward-pack.md 给 Doc Steward 使用。

Pack 包含（phase-11d-design.md §5.2）：
─────────
1. change_manifest
2. diff_summary
3. test_report
4. skill / cli / mcp snapshot（摘要）
5. doc_map（相关文档片段）
6. 当前 Phase 状态
7. doc.consistency issues
8. 需要检查的一致性问题（update focus）

设计约束：
─────────
- 零外部依赖（标准库 + 已有内部模块）
- 只写 .smartdev/runs/<run_id>/handoff/doc-steward-pack.md
- 不调用任何模型（纯确定性组装）
- Token 预算目标 ≤6k tokens（字符数近似控制在 ~24k 字符以内）
- 所有数据源均为可选——git 不可用 / 无索引 / Skill 异常 → 优雅跳过
- Doc Steward 输出固定为：docs_required / issues / update_plan / patch_propose_only

对应文档：
- docs/phase-11d-design.md §5.2（doc-steward-pack.md）
- docs/phase-11d-design.md §8 Step 4
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path


# ── 常量 ──────────────────────────────────────────────────────

# token 预算：~6k tokens，按 ~4 chars/token 估算 ≈ 24000 字符
DOC_PACK_CHAR_BUDGET = 22000


@dataclass
class HandoffDocResult:
    """handoff doc 生成结果。

    Attributes:
        output_path:  输出文件路径
        char_count:   生成内容的字符数
        sections:     各节标题列表
        skipped:      跳过的数据源列表（含原因）
        error:        错误消息（成功时为 None）
    """

    output_path: Path | None = None
    char_count: int = 0
    sections: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "output_path": str(self.output_path) if self.output_path else None,
            "char_count": self.char_count,
            "sections": self.sections,
            "skipped": self.skipped,
            "error": self.error,
        }


# ── 各数据源收集函数 ──────────────────────────────────────────


def _try_manifest(project_path: Path) -> tuple[str, bool]:
    """尝试生成 Change Manifest 摘要。"""
    try:
        from smartdev.core.manifest import manifest_from_git_diff
        m = manifest_from_git_diff(project_path)
        lines = [
            f"- changed_files: {len(m.changed_files)} 个",
            f"- change_type: {m.change_type}",
            f"- risk_level: {m.risk_level}",
            f"- public_surface_changed: {m.public_surface_changed}",
            f"- cli_changed: {m.cli_changed}",
            f"- skill_changed: {m.skill_changed}",
            f"- mcp_changed: {m.mcp_changed}",
            f"- docs_likely_needed: {m.docs_likely_needed}",
        ]
        if m.changed_files:
            lines.append(f"\n变更文件列表:\n" + "\n".join(f"  - {f}" for f in m.changed_files[:20]))
        return "\n".join(lines), True
    except Exception:
        return "（git 不可用，无法生成 Change Manifest）", False


def _try_diff_summary(project_path: Path) -> tuple[str, bool]:
    """尝试获取 git diff 摘要。"""
    try:
        from smartdev.core.git import GitService
        svc = GitService(project_path)
        if not svc.is_available():
            return "（git 不可用）", False
        diff = svc.diff(staged=False)
        lines = [
            f"- 文件数: {len(diff.files)}",
            f"- 新增行: {diff.insertions}",
            f"- 删除行: {diff.deletions}",
        ]
        if diff.files:
            lines.append("\n文件列表:")
            for f in diff.files[:15]:
                lines.append(f"  - {f.path} [{f.status}]")
        return "\n".join(lines), True
    except Exception:
        return "（git diff 摘要不可用）", False


def _try_test_report(project_path: Path) -> tuple[str, bool]:
    """尝试收集测试结果摘要。"""
    try:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        last_line = result.stdout.strip().split("\n")[-1] if result.stdout.strip() else ""
        return f"```\n{last_line}\n```", True
    except FileNotFoundError:
        return "（pytest 不可用）", False
    except Exception:
        return "（无法运行测试）", False


def _try_snapshots(project_path: Path) -> tuple[str, bool]:
    """生成 skill / cli / mcp 快照摘要。"""
    try:
        from smartdev.core.snapshot import (
            build_skill_snapshot,
            build_cli_snapshot,
            build_mcp_snapshot,
        )
        lines = []
        # Skill
        try:
            ss = build_skill_snapshot(project_path)
            lines.append(f"- Skill: {ss.skill_count} 个")
        except Exception:
            lines.append("- Skill: 不可用")
        # CLI
        try:
            cs = build_cli_snapshot()
            lines.append(f"- CLI 命令: {cs.command_count} 个")
        except Exception:
            lines.append("- CLI 命令: 不可用")
        # MCP
        try:
            ms = build_mcp_snapshot()
            if ms.available:
                lines.append(f"- MCP 工具: {ms.tool_count} 个")
            else:
                lines.append("- MCP: 未安装")
        except Exception:
            lines.append("- MCP: 不可用")
        return "\n".join(lines), True
    except Exception:
        return "（快照不可用）", False


def _try_doc_map(project_path: Path) -> tuple[str, bool]:
    """尝试运行 doc.map 获取文档片段。"""
    try:
        from smartdev.skills.doc_map.skill import DocMapSkill
        from smartdev.models import ProjectContext
        skill = DocMapSkill()
        ctx = ProjectContext(project_path=project_path)
        result = skill.run(ctx)
        if not result.success:
            return f"（doc.map 运行失败: {result.summary}）", False

        docs = result.data.get("docs", [])
        lines = []
        for d in docs[:10]:
            name = d.get("path", "")
            mentions = d.get("mentions", {})
            lines.append(f"- `{name}`")
            if mentions and isinstance(mentions, dict):
                mention_items = list(mentions.items())[:5]
                for key, values in mention_items:
                    val_str = ", ".join(values[:3]) if isinstance(values, list) else str(values)
                    lines.append(f"  {key}: {val_str}")
        return "\n".join(lines) if lines else "（未找到文档）", bool(lines)
    except Exception:
        return "（doc.map 不可用）", False


def _try_phase_status(project_path: Path) -> tuple[str, bool]:
    """提取当前 Phase 状态。"""
    lines: list[str] = []
    # 尝试读 CLAUDE.md
    claude_path = project_path / "CLAUDE.md"
    if claude_path.exists():
        try:
            content = claude_path.read_text(encoding="utf-8")
            # 提取 "当前阶段" 相关行
            in_section = False
            for line in content.split("\n"):
                if "当前阶段" in line or "当前阶段" in line:
                    in_section = True
                if in_section:
                    if line.strip().startswith("#") and "当前" not in line:
                        break
                    if line.strip():
                        lines.append(line)
                if len(lines) > 15:
                    break
        except Exception:
            pass

    # 尝试读 development-progress.md
    progress_path = project_path / "docs" / "development-progress.md"
    if progress_path.exists():
        try:
            content = progress_path.read_text(encoding="utf-8")
            # 提取测试基线
            for line in content.split("\n"):
                if "测试基线" in line or "passed" in line.lower():
                    stripped = line.strip()
                    if stripped:
                        lines.append(f"  {stripped}")
        except Exception:
            pass

    if lines:
        return "\n".join(lines), True
    return "（无法读取 Phase 状态）", False


def _try_doc_consistency(project_path: Path) -> tuple[str, bool]:
    """尝试运行 doc.consistency 获取 issues。"""
    try:
        from smartdev.skills.doc_consistency.skill import DocConsistencySkill
        from smartdev.models import ProjectContext
        skill = DocConsistencySkill()
        ctx = ProjectContext(project_path=project_path)
        result = skill.run(ctx)
        if not result.success:
            return f"（doc.consistency 运行失败: {result.summary}）", False

        issues = result.data.get("issues", [])
        if not issues:
            return "✅ 未发现文档一致性问题", True

        lines = [f"共 {len(issues)} 个问题:"]
        severity_order = {"high": 0, "medium": 1, "low": 2}
        sorted_issues = sorted(issues, key=lambda i: severity_order.get(i.get("severity", "low"), 99))
        for issue in sorted_issues[:15]:
            sev = issue.get("severity", "low").upper()
            sev_icon = {"HIGH": "❌", "MEDIUM": "⚠", "LOW": "ℹ"}.get(sev, "•")
            lines.append(
                f"  {sev_icon} [{issue.get('type', '?')}] {issue.get('message', '')[:120]}"
            )
        return "\n".join(lines), True
    except Exception:
        return "（doc.consistency 不可用）", False


def _try_update_focus(project_path: Path) -> tuple[str, bool]:
    """组装需要检查的一致性问题（update focus 清单）。"""
    try:
        from smartdev.skills.doc_update_plan.skill import DocUpdatePlanSkill
        from smartdev.skills.doc_consistency.skill import DocConsistencySkill
        from smartdev.models import ProjectContext

        # 先跑 doc.consistency 获取 issues
        cs_skill = DocConsistencySkill()
        ctx = ProjectContext(project_path=project_path)
        cs_result = cs_skill.run(ctx)
        if not cs_result.success or not cs_result.data.get("issues"):
            return "（无一致性 issues，无需更新）", True

        # 再跑 doc.update.plan
        up_skill = DocUpdatePlanSkill()
        up_result = up_skill.run(ctx, inputs={"consistency_issues": cs_result.data["issues"]})

        items = up_result.data.get("update_items", [])
        if not items:
            return "（无待更新项）", True

        lines = [f"共 {len(items)} 个待更新项:"]
        for item in items[:10]:
            kind = item.get("update_kind", "?")
            doc = item.get("doc_path", "?")
            priority = item.get("priority", "low")
            action = item.get("suggestion", "")[:100]
            lines.append(f"  - [{priority}] {doc} ({kind})")
            if action:
                lines.append(f"    → {action}")
        return "\n".join(lines), True
    except Exception:
        return "（update.plan 不可用）", False


# ── 核心逻辑 ──────────────────────────────────────────────────


def generate_doc_steward_pack(
    project_path: Path,
    run_id: str,
    run_test_report: bool = False,
) -> HandoffDocResult:
    """生成 doc-steward-pack.md。

    Args:
        project_path:      项目根目录
        run_id:            任务唯一标识
        run_test_report:   是否运行 `pytest` 收集测试结果（默认 False）

    Returns:
        HandoffDocResult
    """
    run_dir = project_path / ".smartdev" / "runs" / run_id

    # ── 1. 验证 run 目录存在 ───────────────────────────────────
    if not run_dir.exists():
        return HandoffDocResult(
            error=f"run 目录不存在: {run_dir}。请先运行 smartdev run new {run_id}"
        )

    # ── 2. 验证 scope.json 存在 ─────────────────────────────────
    scope_path = run_dir / "scope.json"
    if not scope_path.exists():
        return HandoffDocResult(
            error=f"scope.json 不存在: {scope_path}。请先运行 smartdev run new {run_id}"
        )

    skipped: list[str] = []
    sections: list[str] = []
    sec_num = 1
    created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # ── 文件头 ─────────────────────────────────────────────────
    pack = f"""# Doc Steward Pack — {run_id}

> 生成时间：{created_at}
> 生成工具：smartdev run handoff-doc
> 目标模型：Doc Steward (Claude/Codex)
> Token 预算：≤ 6k tokens

---

## ══ 角色激活前言 ══

**你是 SmartDev 协作模式中的 Doc Steward。**

当前协作架构：
```
DeepSeek / coding model  = Code Agent
Claude / Codex           = Doc Steward  ← 你
SmartDev                 = Handoff Pack + Gates
Human                    = Apply / Commit / Release
```

**你的职责：**
- 审查文档与代码一致性
- 维护 Phase 状态和测试基线
- 生成文档更新计划或 patch proposal
- 检查能力边界、版本号、CLI/MCP/Skill 快照

**第一件事：**
先看"Doc Consistency Issues"；如有 issue，确认是否需要生成 doc.update.plan。

**你的输出必须是：**
```
docs_required: yes / no
issues:
  - 发现的问题列表
update_plan:
  - 建议的更新计划
patch_propose_only: true（Doc Steward 不直接 apply）
```

**你绝对不能：**
- 直接修改核心源码
- 执行 apply / commit / release
- 扩大功能范围
- 把聊天记录当作事实源（以本 pack 数据为准）

---

"""

    # ── 逐个组装数据源 ────────────────────────────────────────

    # 1. Change Manifest
    manifest_text, manifest_ok = _try_manifest(project_path)
    if manifest_ok:
        pack += f"""## {sec_num}. Change Manifest

{manifest_text}

"""
        sections.append(f"{sec_num}. Change Manifest")
        sec_num += 1
    else:
        skipped.append(f"Change Manifest: {manifest_text}")

    # 2. Diff Summary
    diff_text, diff_ok = _try_diff_summary(project_path)
    if diff_ok:
        pack += f"""## {sec_num}. Diff Summary

{diff_text}

"""
        sections.append(f"{sec_num}. Diff Summary")
        sec_num += 1
    else:
        skipped.append(f"Diff Summary: {diff_text}")

    # 3. Test Report
    if run_test_report:
        test_text, test_ok = _try_test_report(project_path)
        if test_ok and "no tests ran" not in test_text.lower():
            pack += f"""## {sec_num}. Test Report

{test_text}

"""
            sections.append(f"{sec_num}. Test Report")
            sec_num += 1
        else:
            skipped.append(f"Test Report: {test_text}")

    # 4. Snapshots（始终尝试）
    snap_text, snap_ok = _try_snapshots(project_path)
    if snap_ok:
        pack += f"""## {sec_num}. Capability Snapshots

{snap_text}

"""
        sections.append(f"{sec_num}. Capability Snapshots")
        sec_num += 1
    else:
        skipped.append(f"Snapshots: {snap_text}")

    # 5. Doc Map
    docmap_text, docmap_ok = _try_doc_map(project_path)
    if docmap_ok:
        pack += f"""## {sec_num}. Doc Map

{docmap_text}

"""
        sections.append(f"{sec_num}. Doc Map")
        sec_num += 1
    else:
        skipped.append(f"Doc Map: {docmap_text}")

    # 6. Phase Status
    phase_text, phase_ok = _try_phase_status(project_path)
    if phase_ok:
        pack += f"""## {sec_num}. Current Phase Status

{phase_text}

"""
        sections.append(f"{sec_num}. Current Phase Status")
        sec_num += 1
    else:
        skipped.append(f"Phase Status: {phase_text}")

    # 7. Doc Consistency
    consistency_text, consistency_ok = _try_doc_consistency(project_path)
    if consistency_ok:
        pack += f"""## {sec_num}. Doc Consistency Issues

{consistency_text}

"""
        sections.append(f"{sec_num}. Doc Consistency Issues")
        sec_num += 1
    else:
        skipped.append(f"Doc Consistency: {consistency_text}")

    # 8. Update Focus
    focus_text, focus_ok = _try_update_focus(project_path)
    if focus_ok:
        pack += f"""## {sec_num}. Update Focus

{focus_text}

"""
        sections.append(f"{sec_num}. Update Focus")
        sec_num += 1
    else:
        skipped.append(f"Update Focus: {focus_text}")

    # ── Doc Steward 输出规范 ───────────────────────────────────
    pack += f"""---

## Doc Steward 输出规范

作为 Doc Steward，你的回复必须包含：

```
docs_required: yes / no
issues:
  - 发现的问题列表

update_plan:
  - 建议的更新计划

patch_propose_only: true（Doc Steward 不直接 apply）
```

不要：
- 直接修改核心源码
- 执行 apply / commit / release
- 扩大功能范围
"""

    # ── 写入文件 ───────────────────────────────────────────────
    handoff_dir = run_dir / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    output_path = handoff_dir / "doc-steward-pack.md"
    output_path.write_text(pack, encoding="utf-8")

    # 预算警告
    if len(pack) > DOC_PACK_CHAR_BUDGET:
        skipped.append(
            f"⚠ 字符数 {len(pack)} 超过预算 {DOC_PACK_CHAR_BUDGET}"
        )

    return HandoffDocResult(
        output_path=output_path,
        char_count=len(pack),
        sections=sections,
        skipped=skipped,
    )
