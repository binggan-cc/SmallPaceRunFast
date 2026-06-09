"""
Run Report — Phase 11D Step 6B（R1，只写 .smartdev/runs/）

功能：
─────
Code Agent 完成任务后执行 `smartdev run report <run_id>`，
自动把 changed-files、test-report、code-agent-result.md 写入 agent-output/。

设计约束：
─────────
- 零外部依赖（标准库 + git.py）
- 只写 .smartdev/runs/<run_id>/agent-output/
- 不调用任何模型（纯确定性写入）
- git 不可用 / pytest 不可用时优雅降级

对应文档：
- docs/phase-11d-design.md §14（Code Agent 输出协议）
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RunReportResult:
    """run report 执行结果。"""

    output_dir: Path | None = None
    files_written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "output_dir": str(self.output_dir) if self.output_dir else None,
            "files_written": self.files_written,
            "skipped": self.skipped,
            "error": self.error,
        }


def _get_changed_from_git(project_path: Path) -> list[str]:
    """从 git diff HEAD 推断变更文件列表。"""
    try:
        from smartdev.core.git import GitService
        svc = GitService(project_path)
        if not svc.is_available():
            return []
        diff = svc.diff(staged=False)
        return [f.path for f in diff.files]
    except Exception:
        return []


def _ensure_result_md(
    agent_dir: Path, run_id: str, status: str
) -> bool:
    """若 code-agent-result.md 不存在，从模板生成。"""
    result_path = agent_dir / "code-agent-result.md"
    if result_path.exists():
        return False  # 已存在，不覆盖

    created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    content = f"""# Code Agent Result — {run_id}

> 生成时间：{created_at}
> 写入者：Code Agent
> 消费方：Doc Steward / Human

## Status
{status}

## Implemented
<!-- 简要说明实现了什么（每项一行） -->

## Changed Files
| 文件 | 操作 | 原因 |
|------|------|------|
| | | |

## Tests
Command:
```bash
# pytest 命令
```
Result:

## Open Questions
<!-- 如果没有，写"无" -->
"""
    result_path.write_text(content, encoding="utf-8")
    return True


def write_run_report(
    project_path: Path,
    run_id: str,
    changed_files: list[str] | None = None,
    auto_changed_files: bool = False,
    test_command: str | None = None,
    status: str = "completed",
) -> RunReportResult:
    """写入 Code Agent 运行报告到 agent-output/。

    Args:
        project_path:        项目根目录
        run_id:              任务唯一标识
        changed_files:       手动指定的变更文件列表
        auto_changed_files:  从 git diff HEAD 自动推断
        test_command:        要运行的测试命令（如 "python -m pytest tests/ -q"）
        status:              completed / blocked / partial

    Returns:
        RunReportResult
    """
    run_dir = project_path / ".smartdev" / "runs" / run_id
    if not run_dir.exists():
        return RunReportResult(
            error=f"run 目录不存在: {run_dir}。请先运行 smartdev run new {run_id}"
        )

    agent_dir = run_dir / "agent-output"
    agent_dir.mkdir(parents=True, exist_ok=True)

    files_written: list[str] = []
    skipped: list[str] = []

    # ── 1. changed-files.txt ───────────────────────────────────
    cf_path = agent_dir / "changed-files.txt"
    if changed_files:
        cf_path.write_text("\n".join(changed_files) + "\n", encoding="utf-8")
        files_written.append("changed-files.txt")
    elif auto_changed_files:
        auto_files = _get_changed_from_git(project_path)
        if auto_files:
            cf_path.write_text("\n".join(auto_files) + "\n", encoding="utf-8")
            files_written.append("changed-files.txt")
        else:
            skipped.append("changed-files.txt (git 不可用或无变更)")

    # ── 2. test-report.txt ────────────────────────────────────
    if test_command:
        try:
            result = subprocess.run(
                test_command, shell=True, cwd=str(project_path),
                capture_output=True, text=True, timeout=120,
            )
            report = result.stdout
            if result.stderr:
                report += "\n" + result.stderr
            (agent_dir / "test-report.txt").write_text(report, encoding="utf-8")
            files_written.append("test-report.txt")
        except FileNotFoundError:
            skipped.append(f"test-report.txt (命令不可用: {test_command})")
        except subprocess.TimeoutExpired:
            skipped.append("test-report.txt (超时)")
        except Exception as e:
            skipped.append(f"test-report.txt (错误: {e})")

    # ── 3. code-agent-result.md ───────────────────────────────
    created = _ensure_result_md(agent_dir, run_id, status)
    if created:
        files_written.append("code-agent-result.md (从模板生成)")
    else:
        # 已存在但需要更新 Status
        result_path = agent_dir / "code-agent-result.md"
        content = result_path.read_text(encoding="utf-8")
        if "## Status" in content:
            # 替换 Status 行
            import re
            content = re.sub(
                r"## Status\n.*",
                f"## Status\n{status}",
                content,
            )
            result_path.write_text(content, encoding="utf-8")

    return RunReportResult(
        output_dir=agent_dir,
        files_written=files_written,
        skipped=skipped,
    )
