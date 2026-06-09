"""
Skill: doc.consistency — 文档一致性检查（R0 只读）

功能：基于 5 条确定性规则，检查代码能力与文档描述是否一致。
      输出 issues 列表，供 Doc Steward 高阶模型判断。

风险：R0（只读，不修改任何文件）

5 条规则（phase-11c-design.md §5）：
─────────────────────────────────
Rule 1  代码能力 vs 文档描述
        skill_snapshot.skill_count > doc_map 中 skill_name mentions 数量
        cli_snapshot.commands 中有 doc_map 未提及的命令
        → stale_capability

Rule 2  Phase 状态一致性
        CHANGELOG 最新版本 vs pyproject.toml version 不符
        progress.md mentions Phase N 完成 vs CLAUDE.md mentions Phase N
        → phase_status_mismatch

Rule 3  能力边界一致性
        设计文档写 "❌ 不做 X"，但其他文档 mentions 包含 X
        → capability_overpromise（severity: high）

Rule 4  测试基线一致性
        progress.md 中的测试基线数字 vs doc_map 中其他文档里的数字不一致
        → stale_test_baseline（severity: low）

Rule 5  公共接口变化后的文档检查
        change_manifest.public_surface_changed=True 但
        README / CHANGELOG / CLAUDE.md 的 last_modified 早于 manifest.timestamp
        → public_surface_changed_docs_not_updated

设计约束：
─────────
- 纯确定性，零 LLM，零外部依赖
- 每条规则独立执行，互不依赖，一条规则失败不阻断其他规则
- 输入快照不传时自动现场生成（方便 CLI 直接调用）
- doc_map 不传时调用 doc.map Skill 现场生成
- change_manifest 不传时跳过规则 5（不视为错误）
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 数据模型 ──────────────────────────────────────────────


@dataclass
class ConsistencyIssue:
    """单条一致性问题。

    Attributes:
        rule:        触发的规则编号（"rule1"–"rule5"）
        type:        问题类型标识（stale_capability / phase_status_mismatch 等）
        severity:    严重度（high / medium / low）
        doc:         涉及的文档路径
        code_fact:   代码侧的事实描述
        doc_claim:   文档侧的描述（可能已过时）
        suggestion:  建议行动（可选）
    """
    rule: str
    type: str
    severity: str       # high | medium | low
    doc: str
    code_fact: str
    doc_claim: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        d = {
            "rule": self.rule,
            "type": self.type,
            "severity": self.severity,
            "doc": self.doc,
            "code_fact": self.code_fact,
            "doc_claim": self.doc_claim,
        }
        if self.suggestion:
            d["suggestion"] = self.suggestion
        return d


# ── 辅助工具 ──────────────────────────────────────────────

# 测试基线行的正则：匹配 "906 passed" / "906 tests" 等
_TEST_BASELINE_RE = re.compile(r"\b(\d{3,})\s+(?:passed|tests?)\b", re.IGNORECASE)

# pyproject.toml version 行的正则
_PYPROJECT_VERSION_RE = re.compile(r'^version\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)

# 设计文档中"不做"声明的正则（❌ 开头的行）
_DONT_DO_RE = re.compile(r"^[ \t]*(?:❌|✗|×)\s+(.+)", re.MULTILINE)

# Phase 引用正则
_PHASE_RE = re.compile(r"\bPhase\s+(\d+[A-Za-z]?)\b")

# Changelog section 版本正则
_CHANGELOG_VER_RE = re.compile(r"^##\s+\[([^\]]+)\]", re.MULTILINE)

# Rule 3 通用术语停用词表
# 这些词在 SmartDev 文档里高频出现（描述 Skill/工具/架构时必然用到），
# 单独命中不构成"过度承诺"信号。只有过滤掉这些词后，
# 剩余的特异性关键词（如 rebase / force-push / multi-agent / Dashboard / watcher）
# 命中才说明文档真的承诺了设计排除的能力。
_RULE3_STOPWORDS = {
    # 项目高频术语
    "apply", "patch", "patches", "agent", "agents", "model", "models",
    "phase", "git", "mcp", "skill", "skills", "code", "doc", "docs",
    "tool", "tools", "server", "file", "files", "run", "runs", "test",
    "tests", "project", "command", "commands", "json", "api", "data",
    "smartdev", "steward", "handoff", "pack", "commit", "merge", "push",
    "diff", "llm", "router", "scope", "gate", "node", "tree", "sitter",
    "vite", "webpack", "alias", "transport", "stdio", "guard",
    # 英文虚词
    "the", "and", "for", "with", "not", "into", "from", "this", "that",
    "auto", "automatic", "automatically", "self",
}


def _get_doc(doc_map_data: dict, path_hint: str) -> dict | None:
    """从 doc_map.docs 列表中按路径后缀匹配找到文档条目。"""
    for doc in doc_map_data.get("docs", []):
        if doc.get("path", "").endswith(path_hint) or path_hint in doc.get("path", ""):
            return doc
    return None


def _all_skill_mentions(doc_map_data: dict) -> set[str]:
    """收集所有文档中 mentions.skill_name 的值集合。"""
    result: set[str] = set()
    for doc in doc_map_data.get("docs", []):
        for name in doc.get("mentions", {}).get("skill_name", []):
            result.add(name.strip())
    return result


def _all_cli_mentions(doc_map_data: dict) -> set[str]:
    """收集所有文档中 mentions.cli_command 的值集合（只取命令词）。"""
    result: set[str] = set()
    for doc in doc_map_data.get("docs", []):
        for cmd in doc.get("mentions", {}).get("cli_command", []):
            result.add(cmd.strip())
    return result


def _read_file_safe(project_path: Path, rel_path: str) -> str | None:
    """安全读取项目内文件，失败返回 None。"""
    try:
        p = project_path / rel_path
        if p.exists():
            return p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    return None


def _iso_to_ts(iso: str) -> float:
    """ISO 8601 UTC 字符串转 unix timestamp，解析失败返回 0.0。"""
    if not iso:
        return 0.0
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        return 0.0


# ── 规则实现 ──────────────────────────────────────────────


def _rule1_stale_capability(
    skill_snapshot: dict,
    cli_snapshot: dict,
    doc_map_data: dict,
) -> list[ConsistencyIssue]:
    """规则 1：代码能力 vs 文档描述。"""
    issues: list[ConsistencyIssue] = []

    # 1a. Skill 数量：skill_snapshot.skill_count vs doc_map 中 skill_name mentions
    skill_count = skill_snapshot.get("skill_count", 0)
    doc_skill_mentions = _all_skill_mentions(doc_map_data)
    # 容差：doc_map 中提到的 skill 名称数量（去重）
    # 只有当 skill_count 明显超过文档提及时才触发（超 3 个视为 stale）
    if skill_count > 0 and len(doc_skill_mentions) < skill_count - 3:
        issues.append(ConsistencyIssue(
            rule="rule1",
            type="stale_capability",
            severity="medium",
            doc="(all docs)",
            code_fact=f"Skill 注册表有 {skill_count} 个 Skill",
            doc_claim=f"文档中仅提及 {len(doc_skill_mentions)} 个 Skill 名称",
            suggestion="运行 doc.update.plan 生成文档更新建议",
        ))

    # 1b. CLI 命令：cli_snapshot.commands 中有 doc_map 未提及的命令
    cli_commands = {c.get("command", "") for c in cli_snapshot.get("commands", [])}
    doc_cli_mentions = _all_cli_mentions(doc_map_data)
    # 检查每个 CLI 命令是否在文档中被提及
    # 只检查"叶子命令"（有子命令的中间命令不计）
    undocumented: list[str] = []
    for cmd in sorted(cli_commands):
        if not cmd:
            continue
        # 将命令简化为最后两个词（如 "smartdev git commit" → "git commit"）
        parts = cmd.split()
        short = " ".join(parts[-2:]) if len(parts) >= 2 else parts[-1]
        # 检查是否被任何文档的 cli_command mention 或 headings 覆盖
        mentioned = any(
            short in m or cmd in m
            for m in doc_cli_mentions
        )
        if not mentioned:
            undocumented.append(cmd)

    if undocumented:
        issues.append(ConsistencyIssue(
            rule="rule1",
            type="stale_capability",
            severity="low",
            doc="README.md",
            code_fact=f"CLI 有 {len(cli_commands)} 条命令，其中 {len(undocumented)} 条未在文档中提及",
            doc_claim=f"未提及的命令：{', '.join(undocumented[:5])}{'...' if len(undocumented) > 5 else ''}",
            suggestion="在 README 或 docs/ 中补充这些命令的说明",
        ))

    return issues


def _rule2_phase_status(
    doc_map_data: dict,
    project_path: Path,
) -> list[ConsistencyIssue]:
    """规则 2：Phase 状态一致性。"""
    issues: list[ConsistencyIssue] = []

    # 2a. CHANGELOG 最新版本 vs pyproject.toml version
    changelog_doc = _get_doc(doc_map_data, "CHANGELOG.md")
    changelog_version = changelog_doc.get("latest_version", "") if changelog_doc else ""

    pyproject_text = _read_file_safe(project_path, "pyproject.toml")
    pyproject_version = ""
    if pyproject_text:
        m = _PYPROJECT_VERSION_RE.search(pyproject_text)
        if m:
            pyproject_version = m.group(1)

    if changelog_version and pyproject_version:
        # Unreleased 是正常状态，不触发
        if changelog_version.lower() != "unreleased":
            # 规范化：去掉 "v" 前缀后比较
            cv = changelog_version.lstrip("v")
            pv = pyproject_version.lstrip("v")
            if cv != pv:
                issues.append(ConsistencyIssue(
                    rule="rule2",
                    type="phase_status_mismatch",
                    severity="medium",
                    doc="CHANGELOG.md",
                    code_fact=f"pyproject.toml version = {pyproject_version}",
                    doc_claim=f"CHANGELOG.md 最新版本节 = [{changelog_version}]",
                    suggestion="同步 pyproject.toml 版本号与 CHANGELOG 的最新版本节",
                ))

    # 2b. progress.md 与 CLAUDE.md 之间的 Phase 数字差异
    progress_doc = _get_doc(doc_map_data, "progress.md")
    claude_doc = _get_doc(doc_map_data, "CLAUDE.md")

    if progress_doc and claude_doc:
        progress_phases = set(
            m.group(1) for m in _PHASE_RE.finditer(
                " ".join(progress_doc.get("mentions", {}).get("phase", []))
            )
        )
        claude_phases = set(
            m.group(1) for m in _PHASE_RE.finditer(
                " ".join(claude_doc.get("mentions", {}).get("phase", []))
            )
        )
        # 如果 progress 提到了某 Phase 但 CLAUDE.md 没有提到
        missing_in_claude = progress_phases - claude_phases
        if missing_in_claude:
            issues.append(ConsistencyIssue(
                rule="rule2",
                type="phase_status_mismatch",
                severity="low",
                doc="CLAUDE.md",
                code_fact=f"progress.md 提及 Phase: {sorted(progress_phases)}",
                doc_claim=f"CLAUDE.md 仅提及 Phase: {sorted(claude_phases)}，缺少 {sorted(missing_in_claude)}",
                suggestion="在 CLAUDE.md 中补充缺失的 Phase 状态描述",
            ))

    return issues


def _rule3_capability_overpromise(
    doc_map_data: dict,
    project_path: Path,
) -> list[ConsistencyIssue]:
    """规则 3：能力边界一致性（设计文档 ❌ 声明 vs 面向用户文档的描述）。

    只检查"面向用户承诺"的文档（README / CLAUDE.md），
    跳过历史记录文档（CHANGELOG / progress / 其他 design.md）。
    只使用最新 Phase 的设计文档（11c/11d）作为参考，
    避免旧 Phase 的"范围内不做"被误判为永久不做。
    """
    issues: list[ConsistencyIssue] = []

    # 只从最新设计文档里提取 ❌ 声明
    # 原则：只有"当前 Phase 设计文档"的 ❌ 才代表真实边界约束
    # 旧 Phase 的"不做"可能已被后续 Phase 实现
    _LATEST_DESIGN_PATTERNS = ("phase-11c-design", "phase-11d-design")
    design_docs = [
        doc for doc in doc_map_data.get("docs", [])
        if any(p in doc.get("path", "").lower() for p in _LATEST_DESIGN_PATTERNS)
        and doc.get("path", "").endswith(".md")
    ]

    if not design_docs:
        # 降级：找所有 design.md，但只取最新的（按文件名倒序取最后 2 个）
        all_design = sorted(
            [d for d in doc_map_data.get("docs", [])
             if "design" in d.get("path", "").lower() and d.get("path", "").endswith(".md")],
            key=lambda d: d.get("path", ""),
        )
        design_docs = all_design[-2:] if all_design else []

    # 只检查面向用户的承诺文档（README.md）
    # CLAUDE.md 是项目规则文档（内部工程约定），提到 apply/patch/Agent 是描述规则而非承诺
    # README.md 是面向外部用户的能力介绍，才需要检查是否过度承诺
    _USER_FACING_PATTERNS = ("README.md",)
    # 明确豁免的历史/规划文档
    _OVERPROMISE_EXEMPT_PATTERNS = (
        "-design.md",            # 所有设计文档（历史决策记录）
        "CHANGELOG",             # 变更日志（追加记录，不是能力承诺）
        "development-progress",  # 进度记录
        "progress.md",
        "chat.md",
        "references.md",
        "next-phase",            # 未来规划文档，提到未来功能是正常的
        "methodology",
        "software-delivery",
        "visual-",
        "prompt-knowledge",
    )

    for design_doc in design_docs:
        design_path = design_doc.get("path", "")
        text = _read_file_safe(project_path, design_path)
        if not text:
            continue

        # 提取 ❌ 不做 X 声明
        dont_do_items = _DONT_DO_RE.findall(text)
        if not dont_do_items:
            continue

        # 只检查面向用户的承诺文档
        other_docs = [
            d for d in doc_map_data.get("docs", [])
            if d.get("path") != design_path
            and any(uf in d.get("path", "") for uf in _USER_FACING_PATTERNS)
            and not any(p in d.get("path", "") for p in _OVERPROMISE_EXEMPT_PATTERNS)
        ]

        for item in dont_do_items:
            item_clean = item.strip()
            if not item_clean or len(item_clean) < 5:
                continue
            # 提取核心关键词（去掉标点和括号），过滤通用停用词
            raw_keywords = re.findall(r"[a-zA-Z][a-zA-Z_.-]{2,}", item_clean)
            keywords = [
                kw for kw in raw_keywords
                if kw.lower() not in _RULE3_STOPWORDS
            ]
            # 过滤后至少要有 2 个特异性关键词，否则该声明太通用，跳过
            if len(keywords) < 2:
                continue

            for other_doc in other_docs:
                other_path = other_doc.get("path", "")
                other_text = _read_file_safe(project_path, other_path)
                if not other_text:
                    continue
                matches = [kw for kw in keywords if re.search(rf"\b{re.escape(kw)}\b", other_text)]
                if len(matches) >= 2:  # 至少 2 个特异性关键词命中才触发
                    issues.append(ConsistencyIssue(
                        rule="rule3",
                        type="capability_overpromise",
                        severity="high",
                        doc=other_path,
                        code_fact=f"{design_path} 声明不做：{item_clean[:80]}",
                        doc_claim=f"{other_path} 中出现相关词汇：{matches[:3]}",
                        suggestion=f"检查 {other_path} 是否过度承诺了设计文档明确排除的能力",
                    ))
                    break  # 每条 ❌ 声明每个文档只报一次

    return issues


def _rule4_test_baseline(
    doc_map_data: dict,
) -> list[ConsistencyIssue]:
    """规则 4：测试基线一致性。"""
    issues: list[ConsistencyIssue] = []

    # 从 progress.md 提取测试基线数字
    progress_doc = _get_doc(doc_map_data, "progress.md")
    if not progress_doc:
        return issues

    progress_baselines = progress_doc.get("mentions", {}).get("test_baseline", [])
    if not progress_baselines:
        return issues

    # 取最大的测试数（通常是最新基线）
    progress_numbers: list[int] = []
    for b in progress_baselines:
        m = re.search(r"\b(\d+)\b", b)
        if m:
            progress_numbers.append(int(m.group(1)))
    if not progress_numbers:
        return issues
    progress_max = max(progress_numbers)

    # 检查其他文档中的测试基线数字是否与 progress.md 一致
    stale_docs: list[tuple[str, int]] = []
    for doc in doc_map_data.get("docs", []):
        doc_path = doc.get("path", "")
        if "progress" in doc_path.lower():
            continue
        baselines = doc.get("mentions", {}).get("test_baseline", [])
        for b in baselines:
            m = re.search(r"\b(\d+)\b", b)
            if m:
                n = int(m.group(1))
                # 只有明显落后（超 50 个）才触发，避免噪音
                if n < progress_max - 50:
                    stale_docs.append((doc_path, n))
                    break

    for doc_path, stale_n in stale_docs:
        issues.append(ConsistencyIssue(
            rule="rule4",
            type="stale_test_baseline",
            severity="low",
            doc=doc_path,
            code_fact=f"progress.md 测试基线：{progress_max} passed",
            doc_claim=f"{doc_path} 中记录的测试数：{stale_n}",
            suggestion=f"将 {doc_path} 中的测试基线更新为 {progress_max}",
        ))

    return issues


def _rule5_public_surface(
    doc_map_data: dict,
    change_manifest: dict,
) -> list[ConsistencyIssue]:
    """规则 5：公共接口变化后的文档检查。"""
    issues: list[ConsistencyIssue] = []

    if not change_manifest:
        return issues

    public_changed = change_manifest.get("public_surface_changed", False)
    if not public_changed:
        return issues

    manifest_ts_str = change_manifest.get("timestamp", "")
    manifest_ts = _iso_to_ts(manifest_ts_str)

    # 检查关键文档：README / CHANGELOG / CLAUDE.md 是否在 manifest 之后更新过
    key_docs = ["README.md", "CHANGELOG.md", "CLAUDE.md"]
    not_updated: list[str] = []

    for key in key_docs:
        doc = _get_doc(doc_map_data, key)
        if doc is None:
            continue
        doc_ts = _iso_to_ts(doc.get("last_modified", ""))
        # 如果文档修改时间比 manifest 早超过 60 秒，视为未更新
        if manifest_ts > 0 and doc_ts < manifest_ts - 60:
            not_updated.append(key)

    if not_updated:
        changed_files = change_manifest.get("changed_files", [])
        issues.append(ConsistencyIssue(
            rule="rule5",
            type="public_surface_changed_docs_not_updated",
            severity="medium",
            doc=", ".join(not_updated),
            code_fact=(
                f"公共接口文件已变更（{', '.join(changed_files[:3])}{'...' if len(changed_files) > 3 else ''}），"
                f"变更时间：{manifest_ts_str}"
            ),
            doc_claim=f"{', '.join(not_updated)} 的最后修改时间早于变更时间",
            suggestion=f"更新 {', '.join(not_updated)} 以反映公共接口变更",
        ))

    return issues


# ── Skill ─────────────────────────────────────────────────


class DocConsistencySkill(Skill):
    """文档一致性检查 Skill（R0 只读）

    消费 skill_snapshot / cli_snapshot / doc_map / change_manifest，
    执行 5 条确定性规则，输出 issues 列表。

    inputs 参数（均为可选，不传时自动现场生成）：
        skill_snapshot:   SkillSnapshot dict
        cli_snapshot:     CliSnapshot dict
        doc_map:          doc.map 输出 dict
        change_manifest:  ChangeManifest dict（不传则跳过规则 5）

    使用示例：
        # 最简调用（自动生成所有快照）
        result = Skill.create("doc.consistency").run(context)

        # 传入已有快照
        result = Skill.create("doc.consistency").run(context, {
            "skill_snapshot": snap.to_dict(),
            "doc_map": doc_map_result.data,
        })
    """

    name = "doc.consistency"
    description = "基于 5 条确定性规则检查文档与代码一致性，输出 issues 列表"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        return context.project_path.exists()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path

        # ── 准备各快照 ──────────────────────────────────────

        # skill_snapshot
        skill_snapshot: dict = inputs.get("skill_snapshot") or {}
        if not skill_snapshot:
            try:
                from smartdev.core.snapshot import build_skill_snapshot
                skill_snapshot = build_skill_snapshot(project).to_dict()
            except Exception:
                skill_snapshot = {"skill_count": 0, "skills": []}

        # cli_snapshot
        cli_snapshot: dict = inputs.get("cli_snapshot") or {}
        if not cli_snapshot:
            try:
                from smartdev.core.snapshot import build_cli_snapshot
                cli_snapshot = build_cli_snapshot().to_dict()
            except Exception:
                cli_snapshot = {"command_count": 0, "commands": []}

        # doc_map
        doc_map_data: dict = inputs.get("doc_map") or {}
        if not doc_map_data:
            try:
                doc_map_result = Skill.create("doc.map").run(context)
                doc_map_data = doc_map_result.data
            except Exception:
                doc_map_data = {"docs": [], "doc_count": 0}

        # change_manifest（可选，不传则跳过规则 5）
        change_manifest: dict = inputs.get("change_manifest") or {}

        # ── 执行 5 条规则 ────────────────────────────────────
        all_issues: list[ConsistencyIssue] = []

        try:
            all_issues.extend(_rule1_stale_capability(skill_snapshot, cli_snapshot, doc_map_data))
        except Exception as e:
            pass  # 单条规则失败不阻断其他规则

        try:
            all_issues.extend(_rule2_phase_status(doc_map_data, project))
        except Exception:
            pass

        try:
            all_issues.extend(_rule3_capability_overpromise(doc_map_data, project))
        except Exception:
            pass

        try:
            all_issues.extend(_rule4_test_baseline(doc_map_data))
        except Exception:
            pass

        try:
            if change_manifest:
                all_issues.extend(_rule5_public_surface(doc_map_data, change_manifest))
        except Exception:
            pass

        # ── 汇总 ────────────────────────────────────────────
        generated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        issue_count = len(all_issues)
        docs_required = issue_count > 0

        severity_summary = {"high": 0, "medium": 0, "low": 0}
        for issue in all_issues:
            severity_summary[issue.severity] = severity_summary.get(issue.severity, 0) + 1

        summary_lines = [f"文档一致性检查：发现 {issue_count} 个问题"]
        if severity_summary["high"]:
            summary_lines.append(f"  🔴 high: {severity_summary['high']}")
        if severity_summary["medium"]:
            summary_lines.append(f"  🟡 medium: {severity_summary['medium']}")
        if severity_summary["low"]:
            summary_lines.append(f"  🟢 low: {severity_summary['low']}")
        if issue_count == 0:
            summary_lines.append("  ✅ 文档与代码一致，无需更新")

        return SkillResult(
            success=True,
            summary="\n".join(summary_lines),
            data={
                "generated_at": generated_at,
                "issue_count": issue_count,
                "docs_required": docs_required,
                "severity_summary": severity_summary,
                "issues": [i.to_dict() for i in all_issues],
            },
            next_steps=_build_next_steps(all_issues),
        )


def _build_next_steps(issues: list[ConsistencyIssue]) -> list[str]:
    steps: list[str] = []
    if not issues:
        steps.append("文档与代码一致，可继续开发。")
        return steps
    high = [i for i in issues if i.severity == "high"]
    if high:
        steps.append(f"⚠️ {len(high)} 个 high 级问题需要优先处理（能力边界声明矛盾）。")
    steps.append("运行 doc.update.plan 生成文档更新方案。")
    return steps
