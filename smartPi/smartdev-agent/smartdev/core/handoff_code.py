"""
Handoff Code — Phase 11D Step 3 核心交付物（R1，只写 .smartdev/runs/）

功能：
─────
读取 .smartdev/runs/<run_id>/ 下的 task-card.md + scope.json，
可选消费 Scope Gate 结果 + 项目 index 的 impact 分析，
组装生成 code-agent-pack.md 给 Code Agent 使用。

Pack 包含（phase-11d-design.md §5.1）：
─────────
1. 当前任务（从 task-card.md 提取）
2. 修改范围（从 scope.json）
3. 相关文件列表 + 关键代码片段
4. impact / scope gate 结果摘要
5. existing patterns（参考同类实现）
6. 验收标准
7. 禁止项

设计约束：
─────────
- 零外部依赖（标准库）
- 只写 .smartdev/runs/<run_id>/handoff/code-agent-pack.md
- 不调用任何模型（纯确定性组装）
- Token 预算目标 ≤8k tokens（字符数近似控制在 ~30k 字符以内）
- run_id 不存在或 task-card/scope 缺失时有明确错误
- Code Agent 输出固定格式：改了哪些文件/为什么改/测试命令和结果/未完成项/是否需要文档更新

对应文档：
- docs/phase-11d-design.md §5.1（code-agent-pack.md）
- docs/phase-11d-design.md §8 Step 3
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


# ── 常量 ──────────────────────────────────────────────────────

# token 预算：~8k tokens，按 ~4 chars/token 估算 ≈ 32000 字符
CODE_PACK_CHAR_BUDGET = 30000

# 代码片段最大行数
MAX_SNIPPET_LINES = 50

# 相关文件最大数量
MAX_LISTED_FILES = 20

# 代码片段最大字符数（截断保护）
MAX_SNIPPET_CHARS = 3000

# 禁止项模板（Code Agent 通用约束，从 CLAUDE.md 提取）
DEFAULT_PROHIBITIONS = [
    "不修改 phase-*-design.md 历史设计文档",
    "不修改 CHANGELOG.md 历史记录",
    "不修改 docs/development-progress.md（除非在验收标准中明确要求）",
    "不执行 git commit / git tag / git push / release",
    "不执行 patch.apply（只生成 patch proposal）",
    "不扩大改动范围（发现额外问题记录为后续任务）",
    "不一次性修改大量无关文件",
    '不"顺手优化"改动当前任务之外的逻辑',
    "不暴露 MCP 工具（除非任务明确要求）",
    "不扩大到其他 Phase 范围",
]

# 文件扩展名 → 语言标注（用于代码块语法高亮）
_EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".jsx": "jsx",
    ".go": "go",
    ".md": "markdown",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".css": "css",
    ".html": "html",
    ".sh": "bash",
    ".sql": "sql",
}


def _lang_for(file_path: str) -> str:
    """根据文件扩展名推断语言标注。"""
    suffix = Path(file_path).suffix.lower()
    return _EXT_TO_LANG.get(suffix, "")


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class HandoffCodeResult:
    """handoff code 生成结果。

    Attributes:
        output_path: 输出文件路径
        char_count:  生成内容的字符数
        sections:    各节标题列表
        error:       错误消息（成功时为 None）
    """

    output_path: Path | None = None
    char_count: int = 0
    sections: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "output_path": str(self.output_path) if self.output_path else None,
            "char_count": self.char_count,
            "sections": self.sections,
            "error": self.error,
        }


# ── 核心逻辑 ──────────────────────────────────────────────────


def _read_task_card(run_dir: Path) -> tuple[str, str | None]:
    """读取 task-card.md，提取任务目标和验收标准。

    Returns:
        (task_content, error_message)
    """
    task_path = run_dir / "task-card.md"
    if not task_path.exists():
        return "", f"task-card.md 不存在: {task_path}。请先运行 smartdev run new <run_id>"
    try:
        return task_path.read_text(encoding="utf-8"), None
    except Exception as e:
        return "", f"无法读取 task-card.md: {e}"


def _extract_section(md_text: str, heading: str) -> str:
    """从 markdown 文本中提取指定标题下的内容。"""
    lines = md_text.split("\n")
    in_section = False
    content: list[str] = []
    for line in lines:
        if line.strip().startswith("## ") and heading in line:
            in_section = True
            continue
        if in_section and line.strip().startswith("## "):
            break
        if in_section:
            content.append(line)
    return "\n".join(content).strip()


def _collect_files_by_pattern(project_path: Path, pattern: str) -> list[Path]:
    """按单个 glob/目录模式收集文件。

    支持三种模式：
    - 目录前缀: "smartdev/" → 递归所有源码文件
    - 文件 glob: "smartdev/core/*.py" → 精确匹配
    - 简单文件名: "*.pyc" → 项目根 glob
    """
    results: list[Path] = []

    # 目录前缀模式（以 / 结尾）→ 递归扫描
    if pattern.endswith("/"):
        base_dir = project_path / pattern.rstrip("/")
        if base_dir.is_dir():
            for f in sorted(base_dir.rglob("*")):
                if f.is_file() and _is_source_file(f):
                    results.append(f)
        return results

    # 含 * ? [ 的 glob 模式
    if any(c in pattern for c in "*?["):
        try:
            for f in sorted(project_path.glob(pattern)):
                if f.is_file() and _is_source_file(f):
                    results.append(f)
        except Exception:
            pass
        return results

    # 不含通配符的路径 → 可能是文件或目录
    target = project_path / pattern
    if target.is_dir():
        for f in sorted(target.rglob("*")):
            if f.is_file() and _is_source_file(f):
                results.append(f)
    elif target.is_file() and _is_source_file(target):
        results.append(target)

    return results


def _is_source_file(file_path: Path) -> bool:
    """判断是否为源码文件（排除二进制/构建产物/隐藏文件）。"""
    if file_path.suffix not in _EXT_TO_LANG:
        return False
    parts = file_path.parts
    # 排除常见非源码目录
    skip_dirs = {"__pycache__", ".git", ".smartdev", "node_modules",
                 ".pytest_cache", "dist", "build", ".venv", "egg-info"}
    if any(p in skip_dirs for p in parts):
        return False
    return True


def _collect_relevant_files(
    project_path: Path,
    allowed_paths: list[str],
    changed_files: list[str] | None = None,
    max_files: int = MAX_LISTED_FILES,
) -> list[tuple[str, str | None]]:
    """收集相关文件列表，changed_files 优先。

    优先级：
    1. changed_files（如果有）— 这是 Code Agent 需要修改的文件
    2. allowed_paths 扫描结果 — 补充上下文文件

    Returns:
        list of (file_path, first_few_lines_or_None)
    """
    results: list[tuple[str, str | None]] = []
    seen: set[str] = set()

    def _add_file(file_path: Path) -> None:
        """添加文件到结果列表（去重）。"""
        try:
            rel = str(file_path.relative_to(project_path))
        except ValueError:
            return  # 不在项目内
        if rel in seen:
            return
        seen.add(rel)
        snippet = _read_snippet(file_path)
        results.append((rel, snippet))

    # 1. 优先收集 changed_files
    if changed_files:
        for cf in changed_files:
            fpath = project_path / cf
            if fpath.is_file() and _is_source_file(fpath):
                _add_file(fpath)

    # 2. 补充 allowed_paths 扫描结果
    if len(results) < max_files:
        for pattern in allowed_paths:
            for f in _collect_files_by_pattern(project_path, pattern):
                _add_file(f)
                if len(results) >= max_files:
                    break
            if len(results) >= max_files:
                break

    return results[:max_files]


def _read_snippet(file_path: Path, max_chars: int = MAX_SNIPPET_CHARS) -> str | None:
    """读取文件的代码片段（前 N 字符）。"""
    try:
        content = file_path.read_text(encoding="utf-8")
        if len(content) > max_chars:
            # 截断到最近的行边界
            truncated = content[:max_chars]
            last_nl = truncated.rfind("\n")
            if last_nl > max_chars // 2:
                truncated = truncated[:last_nl]
            return truncated + "\n# ... (truncated)"
        return content
    except Exception:
        return None


def _find_existing_patterns(
    project_path: Path, allowed_paths: list[str], limit: int = 5
) -> list[str]:
    """在允许路径下查找可参考的已有实现（同类文件模式）。

    返回同目录下结构相似的文件的简短描述列表。
    """
    patterns: list[str] = []
    seen_dirs = set()

    for ap in allowed_paths:
        base = ap.rstrip("/").rstrip("*")
        if not base:
            continue
        base_dir = project_path / base
        if not base_dir.exists() or not base_dir.is_dir():
            continue

        # 找到有多个同类文件的目录（暗示可参考的 pattern）
        for sub_dir in sorted(base_dir.rglob("*")):
            if sub_dir.is_dir() and sub_dir not in seen_dirs:
                py_files = sorted(sub_dir.glob("*.py"))
                if 2 <= len(py_files) <= 8:  # 2-8 个同类文件 → 可参考 pattern
                    seen_dirs.add(sub_dir)
                    rel = str(sub_dir.relative_to(project_path))
                    file_list = ", ".join(f.name for f in py_files[:5])
                    patterns.append(f"  - `{rel}/` ({len(py_files)} 文件: {file_list})")
                    if len(patterns) >= limit:
                        break
        if len(patterns) >= limit:
            break

    return patterns


def generate_code_agent_pack(
    project_path: Path,
    run_id: str,
    changed_files: list[str] | None = None,
    target: str = "",
) -> HandoffCodeResult:
    """生成 code-agent-pack.md。

    Args:
        project_path:   项目根目录
        run_id:         任务唯一标识
        changed_files:  变更文件列表（可选，用于 scope gate 检查）
        target:         变更目标（可选，用于 impact 分析）

    Returns:
        HandoffCodeResult
    """
    run_dir = project_path / ".smartdev" / "runs" / run_id

    # ── 1. 验证 run 目录存在 ───────────────────────────────────
    if not run_dir.exists():
        return HandoffCodeResult(
            error=f"run 目录不存在: {run_dir}。请先运行 smartdev run new {run_id}"
        )

    # ── 2. 加载 task-card ──────────────────────────────────────
    task_content, err = _read_task_card(run_dir)
    if err:
        return HandoffCodeResult(error=err)

    # ── 3. 加载 scope.json ─────────────────────────────────────
    from smartdev.core.scope_gate import load_scope_config

    scope_data, scope_err = load_scope_config(run_dir)
    if scope_err:
        return HandoffCodeResult(error=scope_err)

    allowed_paths: list[str] = scope_data["allowed_paths"]
    denied_paths: list[str] = scope_data["denied_paths"]
    max_files: int = scope_data["max_files"]
    protected_paths: list[str] = scope_data["protected_paths"]

    # ── 4. Scope Gate 检查（如果有 changed_files） ─────────────
    scope_result_summary = ""
    if changed_files:
        from smartdev.core.scope_gate import check_scope

        sg_result = check_scope(project_path, run_id, changed_files)
        scope_result_summary = sg_result.summary
        if sg_result.violations:
            scope_result_summary += "\n\n违规详情："
            for v in sg_result.violations:
                icon = "❌" if v.severity == "error" else "⚠"
                scope_result_summary += f"\n- {icon} [{v.rule}] {v.file}: {v.message}"

    # ── 5. Impact 分析（如果项目有索引且有 target）───────────────
    impact_summary = ""
    if target:
        try:
            from smartdev.context.impact_analyzer import ImpactAnalyzer
            from smartdev.context.project_index import ProjectIndex

            db_path = project_path / ".smartdev" / "index.sqlite"
            if db_path.exists():
                index = ProjectIndex(project_path)
                analyzer = ImpactAnalyzer(index.store)
                impact = analyzer.analyze(target)
                impact_summary = impact.summary
                if impact.affected_files:
                    impact_summary += (
                        f"\n- 受影响文件 ({len(impact.affected_files)}): "
                        + ", ".join(impact.affected_files[:10])
                    )
                index.close()
        except Exception:
            impact_summary = "（无法进行 impact 分析：索引不可用或 target 无效）"

    # ── 6. 收集相关文件（changed_files 优先）─────────────────────
    relevant_files = _collect_relevant_files(
        project_path, allowed_paths, changed_files=changed_files,
    )

    # ── 7. 找 existing patterns ────────────────────────────────
    patterns = _find_existing_patterns(project_path, allowed_paths)

    # ── 8. 提取任务信息 ────────────────────────────────────────
    task_goal = _extract_section(task_content, "目标") or "（从 task-card.md 提取）"
    task_acceptance = _extract_section(task_content, "验收标准") or "（从 task-card.md 提取）"

    # ── 9. 组装 pack ───────────────────────────────────────────
    sections: list[str] = []
    created_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

    # 文件头
    pack = f"""# Code Agent Pack — {run_id}

> 生成时间：{created_at}
> 生成工具：smartdev run handoff-code
> 目标模型：Code Agent (DeepSeek / coding model)
> Token 预算：≤ 8k tokens

---

## ══ 角色激活前言 ══

**你是 SmartDev 协作模式中的 Code Agent。**

当前协作架构：
```
DeepSeek / coding model  = Code Agent  ← 你
Claude / Codex           = Doc Steward
SmartDev                 = Handoff Pack + Gates
Human                    = Apply / Commit / Release
```

**你的职责：**
- 小范围代码实现、补测试、修 bug
- 生成 patch proposal（不直接 apply）
- 只修改 `allowed_paths` 范围内的文件

**第一件事：**
阅读下方的"1. 当前任务"和"2. 修改范围"，确认你理解了任务目标和边界。

**你的输出必须是：**
```
完成项：...
修改文件：
| 文件 | 操作 | 原因 |
|------|------|------|
关键变更：...
验证方式：...
遗留问题：...
是否需要文档更新：...
```

**你绝对不能：**
- 修改 CHANGELOG.md / CLAUDE.md / phase-*-design.md
- 执行 git commit / git tag / git push / release
- 执行 patch.apply（只 propose）
- 扩大改动范围（发现额外问题记录为后续任务）
- 暴露 MCP 工具（除非任务明确要求）

---

## 1. 当前任务

{task_goal}

---

## 2. 修改范围

### 允许修改（allowed_paths）
{chr(10).join(f'- `{p}`' for p in allowed_paths)}

### 禁止修改（denied_paths）
{chr(10).join(f'- `{p}`' for p in denied_paths)}

### 受保护（protected_paths — 修改需 R3 确认）
{chr(10).join(f'- `{p}`' for p in protected_paths)}

### 变更预算
- max_files: {max_files}

"""
    sections.append("1. 当前任务")
    sections.append("2. 修改范围")

    # 动态节编号（从 3 开始）
    sec_num = 3

    # Scope Gate 结果
    if scope_result_summary:
        pack += f"""## {sec_num}. Scope Gate 结果

{scope_result_summary}

"""
        sections.append(f"{sec_num}. Scope Gate 结果")
        sec_num += 1

    # Impact 分析
    if impact_summary:
        pack += f"""## {sec_num}. Impact 分析

{impact_summary}

"""
        sections.append(f"{sec_num}. Impact 分析")
        sec_num += 1

    # 相关文件
    pack += f"""## {sec_num}. 相关文件

"""
    sections.append(f"{sec_num}. 相关文件")
    sec_num += 1

    if relevant_files:
        for i, (fpath, snippet) in enumerate(relevant_files, 1):
            lang = _lang_for(fpath)
            pack += f"### {i}. `{fpath}`\n\n"
            if snippet:
                pack += f"```{lang}\n{snippet}\n```\n\n"
            else:
                pack += "（无法读取文件内容）\n\n"

            # 预算检查：如果 pack 已接近预算上限，截断文件列表
            if len(pack) > CODE_PACK_CHAR_BUDGET * 0.7:
                remaining = len(relevant_files) - i
                if remaining > 0:
                    pack += (
                        f"> ⚠ 已达到字符预算限制，省略剩余 {remaining} 个文件。"
                        f"如需要，可单独读取这些文件。\n"
                    )
                break
    else:
        pack += "（allowed_paths 范围内未找到相关源文件）\n\n"

    # Existing patterns
    pack += f"""## {sec_num}. 参考实现（existing patterns）

"""
    sections.append(f"{sec_num}. 参考实现（existing patterns）")
    sec_num += 1
    if patterns:
        pack += "\n".join(patterns) + "\n\n"
    else:
        pack += "（未找到可参考的同类实现 pattern）\n\n"

    # 验收标准
    pack += f"""## {sec_num}. 验收标准

{task_acceptance}

"""
    sections.append(f"{sec_num}. 验收标准")
    sec_num += 1

    # 禁止项
    pack += f"""## {sec_num}. 禁止项

"""
    sections.append(f"{sec_num}. 禁止项")
    for i, p in enumerate(DEFAULT_PROHIBITIONS, 1):
        pack += f"{i}. {p}\n"

    pack += f"""
> 以上禁止项来自 SmartDev 项目通用约束 + scope.json 保护路径。

---

## Code Agent 输出规范

你的回复必须包含以下结构：

```
完成项：...
修改文件：
| 文件 | 操作 | 原因 |
|------|------|------|

关键变更：...
验证方式：...
遗留问题：...
是否需要文档更新：...
```

不要输出：
- 与任务无关的文件修改
- 未经验证的 patch apply 声明
"""

    # ── 10. 写入文件 ───────────────────────────────────────────
    handoff_dir = run_dir / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    output_path = handoff_dir / "code-agent-pack.md"
    output_path.write_text(pack, encoding="utf-8")

    return HandoffCodeResult(
        output_path=output_path,
        char_count=len(pack),
        sections=sections,
    )
