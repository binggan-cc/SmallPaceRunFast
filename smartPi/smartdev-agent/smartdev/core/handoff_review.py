"""
Handoff Review — Phase 11D Step 5 核心交付物（R1，只写 .smartdev/runs/）

功能：
─────
读取 .smartdev/runs/<run_id>/ 下的 scope.json，
聚合 risk / impact / diff / dependency / security / test 事实，
组装生成 reviewer-pack.md 给 Reviewer 使用。

Pack 包含（phase-11d-design.md §5.3）：
─────────
1. risk + impact
2. changed_files
3. test_report
4. dependency changes
5. security checklist
6. git.diff.explain

设计约束：
─────────
- 零外部依赖（标准库 + 已有内部模块）
- 只写 .smartdev/runs/<run_id>/handoff/reviewer-pack.md
- 不调用任何模型（纯确定性组装）
- Token 预算目标 ≤10k tokens（字符数近似控制在 ~40k 字符以内）
- 所有数据源可选，git / index / pytest 不可用时优雅降级
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path


REVIEW_PACK_CHAR_BUDGET = 40000

DEPENDENCY_FILES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
}

SECURITY_PATTERNS = {
    "auth": "认证/授权相关变更",
    "token": "token / credential 相关变更",
    "secret": "secret 相关变更",
    "password": "password 相关变更",
    "security": "安全模块相关变更",
    "subprocess": "命令执行相关变更",
    "path": "路径处理相关变更",
    "upload": "上传入口相关变更",
}


@dataclass
class HandoffReviewResult:
    """handoff review 生成结果。"""

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


def _load_changed_files(project_path: Path, explicit: list[str] | None = None) -> list[str]:
    """优先使用显式 changed_files，否则从 git diff 推断。"""
    if explicit:
        return list(dict.fromkeys(explicit))
    try:
        from smartdev.core.git import GitService

        svc = GitService(project_path)
        if not svc.is_available():
            return []
        diff = svc.diff(staged=False)
        return [f.path for f in diff.files]
    except Exception:
        return []


def _try_risk_and_impact(project_path: Path, target: str, changed_files: list[str]) -> tuple[str, bool]:
    """生成 risk + impact 摘要。"""
    lines: list[str] = []

    try:
        from smartdev.core.manifest import manifest_from_git_diff

        m = manifest_from_git_diff(project_path)
        lines.extend([
            f"- risk_level: {m.risk_level}",
            f"- change_type: {m.change_type}",
            f"- public_surface_changed: {m.public_surface_changed}",
            f"- cli_changed: {m.cli_changed}",
            f"- skill_changed: {m.skill_changed}",
            f"- mcp_changed: {m.mcp_changed}",
        ])
    except Exception:
        risk = "R0" if not changed_files else ("R2" if len(changed_files) >= 5 else "R1")
        lines.append(f"- risk_level: {risk}（fallback based on changed_files）")

    if target:
        try:
            from smartdev.context.impact_analyzer import ImpactAnalyzer
            from smartdev.context.project_index import ProjectIndex

            db_path = project_path / ".smartdev" / "index.sqlite"
            if db_path.exists():
                index = ProjectIndex(project_path)
                analyzer = ImpactAnalyzer(index.store)
                impact = analyzer.analyze(target)
                lines.append("")
                lines.append("Impact:")
                lines.append(f"- target: {target}")
                lines.append(f"- summary: {impact.summary}")
                if impact.affected_files:
                    lines.append("- affected_files:")
                    lines.extend(f"  - {f}" for f in impact.affected_files[:15])
                index.close()
            else:
                lines.append(f"- impact: skipped（index 不存在，target={target}）")
        except Exception:
            lines.append(f"- impact: unavailable（target={target}）")
    else:
        lines.append("- impact: skipped（未提供 --target）")

    return "\n".join(lines), bool(lines)


def _try_diff_explain(project_path: Path) -> tuple[str, bool]:
    """尝试运行 git.diff.explain Skill。"""
    try:
        from smartdev.models import ProjectContext
        from smartdev.skills.git_diff_explain.skill import GitDiffExplainSkill

        result = GitDiffExplainSkill().run(ProjectContext(project_path=project_path))
        if result.success:
            return result.summary or "（无 diff 摘要）", True
        return f"（git.diff.explain 运行失败: {result.summary}）", False
    except Exception:
        return "（git.diff.explain 不可用）", False


def _try_test_report(project_path: Path) -> tuple[str, bool]:
    """运行 pytest 收集测试摘要。"""
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
        if not last_line:
            last_line = result.stderr.strip().split("\n")[-1] if result.stderr.strip() else ""
        return f"```\n{last_line}\n```", True
    except FileNotFoundError:
        return "（pytest 不可用）", False
    except Exception:
        return "（无法运行测试）", False


def _dependency_changes(changed_files: list[str]) -> str:
    """列出依赖文件变更。"""
    deps = [f for f in changed_files if Path(f).name in DEPENDENCY_FILES]
    if not deps:
        return "未检测到依赖清单或 lockfile 变更。"
    lines = ["检测到依赖相关变更:"]
    lines.extend(f"- `{f}`" for f in deps)
    lines.append("")
    lines.append("Reviewer 需检查：依赖来源、lockfile 是否同步、是否需要 audit。")
    return "\n".join(lines)


def _security_checklist(changed_files: list[str]) -> str:
    """根据路径关键词生成安全审查清单。"""
    lower_paths = " ".join(changed_files).lower()
    hits = [desc for key, desc in SECURITY_PATTERNS.items() if key in lower_paths]

    lines = [
        "- 输入校验是否完整",
        "- 路径拼接 / 文件写入是否限制在项目或 run artifact 边界内",
        "- subprocess / shell 调用是否使用列表参数且不拼接用户输入",
        "- 是否新增敏感信息、凭据、token、密钥或日志泄露风险",
        "- 是否修改认证、授权、网络、依赖或配置边界",
    ]
    if hits:
        lines.insert(0, "检测到需重点关注的路径信号：")
        lines[1:1] = [f"- {h}" for h in hits]
        lines.append("")
        lines.append("通用检查：")
    else:
        lines.insert(0, "未从文件路径检测到高敏安全信号。通用检查：")
    return "\n".join(lines)


def generate_reviewer_pack(
    project_path: Path,
    run_id: str,
    changed_files: list[str] | None = None,
    target: str = "",
    run_test_report: bool = False,
) -> HandoffReviewResult:
    """生成 reviewer-pack.md。"""
    run_dir = project_path / ".smartdev" / "runs" / run_id
    if not run_dir.exists():
        return HandoffReviewResult(
            error=f"run 目录不存在: {run_dir}。请先运行 smartdev run new {run_id}"
        )

    scope_path = run_dir / "scope.json"
    if not scope_path.exists():
        return HandoffReviewResult(
            error=f"scope.json 不存在: {scope_path}。请先运行 smartdev run new {run_id}"
        )

    changed = _load_changed_files(project_path, changed_files)
    sections: list[str] = []
    skipped: list[str] = []
    sec_num = 1
    created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    pack = f"""# Reviewer Pack — {run_id}

> 生成时间：{created_at}
> 生成工具：smartdev run handoff-review
> 目标模型：Reviewer
> Token 预算：≤ 10k tokens

---

## ══ 角色激活前言 ══

**你是 SmartDev 协作模式中的 Reviewer。**

当前协作架构：
```
DeepSeek / coding model  = Code Agent
Claude / Codex           = Doc Steward
SmartDev                 = Handoff Pack + Gates
Reviewer                 = Risk / Architecture / Security  ← 你
Human                    = Apply / Commit / Release
```

**你的职责：**
- 审查风险等级和影响范围
- 审查架构决策和依赖变更
- 审查安全检查清单
- 判断是否需要人工介入或拒绝

**第一件事：**
先看"Risk + Impact"和"Security Checklist"；如有高风险信号，优先处理。

**你的输出必须是：**
```
risk_level: R0 / R1 / R2 / R3
issues:
  - 风险 / 架构 / 安全问题列表
required_checks:
  - 需要补跑或补充的验证
approval: approve / request_changes / block
patch_propose_only: true（Reviewer 不直接 apply）
```

**你绝对不能：**
- 直接修改代码
- 执行 apply / commit / release
- 扩大功能范围

---

"""

    risk_text, risk_ok = _try_risk_and_impact(project_path, target, changed)
    if risk_ok:
        pack += f"""## {sec_num}. Risk + Impact

{risk_text}

"""
        sections.append(f"{sec_num}. Risk + Impact")
        sec_num += 1
    else:
        skipped.append(f"Risk + Impact: {risk_text}")

    pack += f"""## {sec_num}. Changed Files

"""
    if changed:
        pack += "\n".join(f"- `{f}`" for f in changed[:40]) + "\n\n"
        if len(changed) > 40:
            pack += f"> 已截断，剩余 {len(changed) - 40} 个文件未列出。\n\n"
    else:
        pack += "（未检测到 changed_files）\n\n"
    sections.append(f"{sec_num}. Changed Files")
    sec_num += 1

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

    # Agent Output（若 agent-output/ 下有产物，纳入上下文）
    agent_dir = run_dir / "agent-output"
    # 读取 code-agent-result.md 状态
    ca_path = agent_dir / "code-agent-result.md"
    if ca_path.exists():
        try:
            ca_content = ca_path.read_text(encoding="utf-8")
            status_line = ""
            for i, line in enumerate(ca_content.splitlines()):
                if line.startswith("## Status"):
                    if i + 1 < len(ca_content.splitlines()):
                        status_line = ca_content.splitlines()[i + 1].strip()
                    break
            if status_line:
                pack += f"""## {sec_num}. Code Agent Result

- Status: {status_line}
- 详见: `.smartdev/runs/{run_id}/agent-output/code-agent-result.md`

"""
                sections.append(f"{sec_num}. Code Agent Result")
                sec_num += 1
        except Exception:
            skipped.append("Code Agent Result: 读取失败")

    # 读取 changed-files.txt（补充或验证 Changed Files）
    cf_path = agent_dir / "changed-files.txt"
    if cf_path.exists():
        try:
            cf_content = cf_path.read_text(encoding="utf-8")
            cf_files = [f.strip() for f in cf_content.splitlines() if f.strip()]
            if cf_files:
                pack += f"""## {sec_num}. Agent Changed Files

Code Agent 记录的变更文件（`agent-output/changed-files.txt`）：
"""
                pack += "\n".join(f"- `{f}`" for f in cf_files[:40]) + "\n\n"
                if len(cf_files) > 40:
                    pack += f"> 已截断，剩余 {len(cf_files) - 40} 个文件未列出。\n\n"
                sections.append(f"{sec_num}. Agent Changed Files")
                sec_num += 1
        except Exception:
            skipped.append("Agent Changed Files: 读取失败")

    # 读取 test-report.txt（若未运行实时测试，纳入已有报告）
    tr_path = agent_dir / "test-report.txt"
    if tr_path.exists():
        try:
            tr_content = tr_path.read_text(encoding="utf-8")
            if tr_content.strip():
                pack += f"""## {sec_num}. Agent Test Report

Code Agent 记录的测试结果（`agent-output/test-report.txt`）：
```
{tr_content.strip()[:3000]}
```

"""
                sections.append(f"{sec_num}. Agent Test Report")
                sec_num += 1
        except Exception:
            skipped.append("Agent Test Report: 读取失败")

    pack += f"""## {sec_num}. Dependency Changes

{_dependency_changes(changed)}

"""
    sections.append(f"{sec_num}. Dependency Changes")
    sec_num += 1

    pack += f"""## {sec_num}. Security Checklist

{_security_checklist(changed)}

"""
    sections.append(f"{sec_num}. Security Checklist")
    sec_num += 1

    diff_text, diff_ok = _try_diff_explain(project_path)
    if diff_ok:
        pack += f"""## {sec_num}. Git Diff Explain

{diff_text}

"""
        sections.append(f"{sec_num}. Git Diff Explain")
        sec_num += 1
    else:
        skipped.append(f"Git Diff Explain: {diff_text}")

    pack += """---

## Reviewer 输出规范

作为 Reviewer，你的回复必须包含：

```
risk_level: R0 / R1 / R2 / R3
issues:
  - 风险 / 架构 / 安全问题列表

required_checks:
  - 需要补跑或补充的验证

approval: approve / request_changes / block
patch_propose_only: true（Reviewer 不直接 apply）
```

不要：
- 直接修改代码
- 执行 apply / commit / release
- 扩大功能范围
"""

    handoff_dir = run_dir / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    output_path = handoff_dir / "reviewer-pack.md"
    output_path.write_text(pack, encoding="utf-8")

    if len(pack) > REVIEW_PACK_CHAR_BUDGET:
        skipped.append(f"⚠ 字符数 {len(pack)} 超过预算 {REVIEW_PACK_CHAR_BUDGET}")

    return HandoffReviewResult(
        output_path=output_path,
        char_count=len(pack),
        sections=sections,
        skipped=skipped,
    )
