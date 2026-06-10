"""
SmartDev MCP Server — 主体

设计原理：
──────────
- stdio transport：外部 Agent 通过 JSON-RPC over stdio 调用
- single project per server instance：启动时绑定 project_path，运行时不切换
- mcp 是 optional dependency：未安装时给出明确提示

Phase 10 Step 1 只注册基础工具：
    smartdev_ping / smartdev_version / smartdev_list_tools

工具实现在 tools.py，server.py 只负责注册和启动。

对应文档：
    docs/phase-10-design.md §3.1 §3.2
"""

from __future__ import annotations

import asyncio
from pathlib import Path


def _require_mcp() -> None:
    """检查 mcp 包是否已安装，未安装时输出提示并退出"""
    try:
        import mcp  # noqa: F401
    except ImportError:
        import sys
        print(
            "错误: MCP Server 需要安装 mcp 包。\n"
            "请运行: pip install smartdev-agent[mcp]\n"
            "或直接: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)


def create_server(project_path: Path):
    """创建并返回配置好的 MCP Server 实例

    参数：
        project_path: 已验证存在的项目根目录

    返回：
        mcp.server.Server 实例，已注册所有工具
    """
    from mcp.server import Server
    from mcp.types import Tool

    from smartdev.mcp import tools as t

    server = Server("smartdev")

    # ── 工具 Schema 定义 ──────────────────────────────────────────

    _TOOLS: list[Tool] = [
        Tool(
            name="smartdev_ping",
            description=(
                "Health check. Confirms the SmartDev MCP Server is running "
                "and returns the bound project path."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_version",
            description=(
                "Returns SmartDev version and the full tool capability list "
                "(including tools not yet available in this step)."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_list_tools",
            description=(
                "Lists all currently available MCP tools with their "
                "permission levels and descriptions."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_code_search",
            description=(
                "Full-text search over indexed files and artifacts. "
                "Requires running smartdev_code_index first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (file name, function name, artifact type, etc.)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="smartdev_code_impact",
            description=(
                "Analyze the change impact of a file, module, or artifact via import reverse lookup. "
                "Returns affected files, risk level, and validation suggestions. "
                "Requires running smartdev_code_index first."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "Target to analyze (file path, module name, or artifact name)",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum depth for impact traversal (default: 3)",
                        "default": 3,
                    },
                },
                "required": ["target"],
            },
        ),
        Tool(
            name="smartdev_project_map",
            description=(
                "Export a project structure map including modules, hotspots, and external dependencies. "
                "Requires running smartdev_code_index first."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_graph_validate",
            description=(
                "Validate the health of the project graph: orphan nodes, duplicates, "
                "hotspots, and unresolved imports. "
                "Requires running smartdev_code_index first."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # ── Step 3: Skill 工具 ────────────────────────────────────
        Tool(
            name="smartdev_repo_scan",
            description=(
                "Scan the project: detect tech stack, entry points, documentation status, "
                "and directory structure."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum directory tree depth (default: 2)",
                        "default": 2,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="smartdev_risk_check",
            description=(
                "Check the risk level of a task. "
                "With an index, uses import-based impact analysis for more accurate results. "
                "Without an index, falls back to keyword matching."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task or change to evaluate",
                    },
                    "target": {
                        "type": "string",
                        "description": "(Optional) File path or module name to enhance impact analysis",
                    },
                },
                "required": ["task_description"],
            },
        ),
        Tool(
            name="smartdev_architecture_map",
            description=(
                "Analyze project architecture: dependency graph, circular dependencies, core modules. "
                "With an index, supports multi-language analysis (Python/JS/TS/Go). "
                "Without an index, falls back to Python AST only."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="smartdev_task_plan",
            description=(
                "Generate a three-tier task plan (conservative / recommended / deep) for a task. "
                "With an index, annotates the recommended plan with affected files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the development task",
                    },
                    "target": {
                        "type": "string",
                        "description": "(Optional) File path or module to scope impact analysis",
                    },
                },
                "required": ["task_description"],
            },
        ),
        Tool(
            name="smartdev_qa_checklist",
            description=(
                "Generate a structured acceptance checklist for a task, "
                "covering functionality, UI, API, performance, and security."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "Description of the task to generate a checklist for",
                    },
                },
                "required": ["task_description"],
            },
        ),
        # ── Step 4: CACHE_WRITE + PATCH_PROPOSE ──────────────────
        Tool(
            name="smartdev_code_index",
            description=(
                "Build the project semantic index (.smartdev/index.sqlite). "
                "WRITES ONLY to .smartdev/ cache — never modifies source files. "
                "Required before using code_search, code_impact, project_map, or graph_validate."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "force": {
                        "type": "boolean",
                        "description": "Force reindex all files, ignoring hash cache (default: false)",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="smartdev_patch_propose",
            description=(
                "Generate a find-replace patch proposal. "
                "Returns unified diff, affected files, risk level, diff_explain, and patch_id. "
                "DOES NOT modify any source files. "
                "To apply: use CLI `smartdev apply --patch-id <id>`."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "find": {
                        "type": "string",
                        "description": "Text or pattern to find across project files",
                    },
                    "replace": {
                        "type": "string",
                        "description": "Replacement text (can be empty string to delete matches)",
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Why this change is needed (required for audit trail)",
                    },
                    "glob": {
                        "type": "string",
                        "description": "File glob pattern to scope the search (default: **/*)",
                        "default": "**/*",
                    },
                    "regex": {
                        "type": "boolean",
                        "description": "Treat find as a regex pattern (default: false)",
                        "default": False,
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Max files to patch in one proposal (change.budget, default: 10)",
                        "default": 10,
                    },
                },
                "required": ["find", "replace", "task_description"],
            },
        ),
        # ── Phase 11A Step 7: 只读 Git 工具 ──────────────────────
        Tool(
            name="smartdev_git_status",
            description=(
                "Query current git status: branch, dirty files, staged/unstaged/untracked, "
                "recent commits, and policy hints (e.g. protected branch). Read-only."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "recent_commit_count": {
                        "type": "integer",
                        "description": "Number of recent commits to include (default: 10)",
                        "default": 10,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="smartdev_git_diff_explain",
            description=(
                "Deterministic structured diff explanation: line counts, file categories, "
                "risk signals (touches_tests/docs/manifest/protected_path), "
                "and suggested commit split. Does NOT generate natural language summaries."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "staged": {
                        "type": "boolean",
                        "description": "True to explain staged diff (--cached), False for worktree diff (default: false)",
                        "default": False,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="smartdev_git_commit_plan",
            description=(
                "Analyze current diff and generate Conventional Commit split suggestions. "
                "Does NOT execute commit. Groups files by category (source/test/doc/manifest) "
                "and suggests per-directory scope."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "staged_only": {
                        "type": "boolean",
                        "description": "Only analyze staged files (default: false, all diff)",
                        "default": False,
                    },
                    "scope_hint": {
                        "type": "string",
                        "description": "Optional scope hint to override inferred scope (e.g. 'context', 'cli')",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="smartdev_git_release_plan",
            description=(
                "Analyze commits, CHANGELOG, and version files to suggest semver bump "
                "(major/minor/patch/none) and generate a release checklist."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "since_tag": {
                        "type": "string",
                        "description": "Analyze commits since this tag (default: latest tag)",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="smartdev_git_merge_check",
            description=(
                "Pre-merge readiness check: working tree cleanliness, patch backups, "
                "branch direction, new commits, and semantic index availability. "
                "Returns blockers (must fix) and warnings (should fix)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_branch": {
                        "type": "string",
                        "description": "Target branch to merge into (default: first protected branch from policy)",
                    },
                },
                "required": [],
            },
        ),
        # ── Phase 11C Step 7: 只读 Doc Governance 工具 ───────────
        Tool(
            name="smartdev_doc_consistency",
            description=(
                "Check documentation consistency against code using 5 deterministic rules. "
                "Automatically generates skill/cli/mcp snapshots and doc map. "
                "Returns issues list with type, severity, code_fact, doc_claim. "
                "Read-only — does NOT modify any files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "change_manifest": {
                        "type": "object",
                        "description": "(Optional) ChangeManifest dict from smartdev manifest diff. "
                                       "Enables Rule 5 (public surface changed docs not updated).",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="smartdev_doc_update_plan",
            description=(
                "Generate structured documentation update plan from consistency issues. "
                "Outputs: update_items (what to change and why), "
                "no_change_items (docs that must not be modified). "
                "Classifies updates as status_sync / capability_boundary / expression_alignment. "
                "Read-only — does NOT modify any files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "consistency_issues": {
                        "type": "array",
                        "description": "(Optional) issues list from smartdev_doc_consistency. "
                                       "If omitted, runs doc.consistency automatically.",
                        "items": {"type": "object"},
                    },
                },
                "required": [],
            },
        ),
        # Phase 11B Step 7: 只读 Guard 工具
        Tool(
            name="smartdev_guard_run",
            description=(
                "Run all 5 Guard Skills (change.budget, dev.guard, dependency.guard, "
                "security.review, diff.explain) and return an aggregate report. "
                "Use --select to run only specific guards. "
                "All guards are R0 read-only — they never modify source files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "changed_files": {
                        "type": "array",
                        "description": "Changed file paths (list[str]). Required by most guards.",
                        "items": {"type": "string"},
                    },
                    "diff_content": {
                        "type": "string",
                        "description": "Unified diff text (optional, used by dependency/security/diff guards).",
                    },
                    "select": {
                        "type": "array",
                        "description": "Guard names to run (default: all 5). e.g. ['change.budget', 'dev.guard']",
                        "items": {"type": "string"},
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Task description (optional, used by dev.guard for unrelated change detection).",
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Maximum file count budget (default: 10, used by change.budget).",
                        "default": 10,
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum line count budget (optional, used by change.budget).",
                    },
                    "protected_paths": {
                        "type": "array",
                        "description": "Protected path glob patterns (optional, used by dev.guard).",
                        "items": {"type": "string"},
                    },
                    "denied_paths": {
                        "type": "array",
                        "description": "Denied path glob patterns (optional, used by dev.guard).",
                        "items": {"type": "string"},
                    },
                    "run_id": {
                        "type": "string",
                        "description": "Run identifier (optional, for report labeling).",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="smartdev_change_budget",
            description=(
                "Check whether a change exceeds budget limits: file count, line count, "
                "schema changes, per-file limits. Deterministic rule engine, R0 read-only."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "changed_files": {
                        "type": "array",
                        "description": "List of changed file paths (required).",
                        "items": {"type": "string"},
                    },
                    "max_files": {
                        "type": "integer",
                        "description": "Maximum file count (default: 10).",
                        "default": 10,
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": "Maximum total line count (optional, None=no limit).",
                    },
                    "allow_schema_change": {
                        "type": "boolean",
                        "description": "Whether data model changes are allowed (default: false).",
                        "default": False,
                    },
                    "per_file_limit": {
                        "type": "integer",
                        "description": "Maximum lines changed per file (default: 200).",
                        "default": 200,
                    },
                    "line_counts": {
                        "type": "object",
                        "description": "Per-file line counts dict, e.g. {\"src/a.py\": 15}.",
                    },
                },
                "required": ["changed_files"],
            },
        ),
        Tool(
            name="smartdev_dev_guard",
            description=(
                "AI coding rules guard: mass refactor detection, protected path hits, "
                "unrelated changes, test deletion, config mixing, forbidden file modifications, "
                "oversized commits. Deterministic rule engine, R0 read-only."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "changed_files": {
                        "type": "array",
                        "description": "List of changed file paths (required).",
                        "items": {"type": "string"},
                    },
                    "protected_paths": {
                        "type": "array",
                        "description": "Protected path glob patterns (optional).",
                        "items": {"type": "string"},
                    },
                    "denied_paths": {
                        "type": "array",
                        "description": "Denied path glob patterns (optional).",
                        "items": {"type": "string"},
                    },
                    "forbidden_paths": {
                        "type": "array",
                        "description": "Additional forbidden paths (optional).",
                        "items": {"type": "string"},
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Task description for unrelated change detection.",
                    },
                    "diff_content": {
                        "type": "string",
                        "description": "Unified diff content for precise test deletion detection.",
                    },
                    "max_files_per_commit": {
                        "type": "integer",
                        "description": "Maximum files per commit (default: 12).",
                        "default": 12,
                    },
                },
                "required": ["changed_files"],
            },
        ),
        Tool(
            name="smartdev_dependency_guard",
            description=(
                "Dependency manifest change review: detects added/removed/version-changed "
                "dependencies, manifest additions/removals, and lock file sync. "
                "Supports pyproject.toml, package.json, go.mod, requirements.txt. "
                "Deterministic rule engine, R0 read-only."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "changed_files": {
                        "type": "array",
                        "description": "List of changed file paths (required).",
                        "items": {"type": "string"},
                    },
                    "diff_content": {
                        "type": "string",
                        "description": "Unified diff text for manifest content analysis.",
                    },
                    "manifest_before": {
                        "type": "object",
                        "description": "Manifest contents before change (dict[str, str], optional).",
                    },
                    "manifest_after": {
                        "type": "object",
                        "description": "Manifest contents after change (dict[str, str], optional).",
                    },
                    "lock_files_changed": {
                        "type": "array",
                        "description": "List of changed lock files (optional).",
                        "items": {"type": "string"},
                    },
                },
                "required": ["changed_files"],
            },
        ),
        Tool(
            name="smartdev_security_review",
            description=(
                "Security review checklist: 6 categories — input validation, path traversal, "
                "command injection, sensitive data exposure, hardcoded secrets, dynamic code execution. "
                "Deterministic pattern matching, R0 read-only. "
                "Suggests external tools (bandit/semgrep) but never executes them."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "changed_files": {
                        "type": "array",
                        "description": "List of changed file paths (required).",
                        "items": {"type": "string"},
                    },
                    "diff_content": {
                        "type": "string",
                        "description": "Unified diff text for content-level security scanning.",
                    },
                    "file_contents": {
                        "type": "object",
                        "description": "File contents map (dict[str, str], optional) for deeper scanning.",
                    },
                },
                "required": ["changed_files"],
            },
        ),
        Tool(
            name="smartdev_diff_explain",
            description=(
                "Patch-level diff explanation: logical grouping, test coverage analysis, "
                "dependency matching, cross-module detection, file categorization, "
                "risk hints, and suggested review order. "
                "Deterministic rule engine, R0 read-only. "
                "Consumes base_signals from git.diff.explain for supplemental signals."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "patch_files": {
                        "type": "array",
                        "description": "List of changed file paths (required, same as changed_files).",
                        "items": {"type": "string"},
                    },
                    "diff_content": {
                        "type": "string",
                        "description": "Unified diff text for line count statistics.",
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Project root path (optional, defaults to bound project path).",
                    },
                    "base_signals": {
                        "type": "object",
                        "description": "External signals from git.diff.explain (optional, merged as supplement).",
                    },
                },
                "required": ["patch_files"],
            },
        ),
        # Phase 11D Step 7: Handoff Pack 工具
        Tool(
            name="smartdev_handoff_code",
            description=(
                "Generate code-agent-pack.md and write to .smartdev/runs/<run_id>/handoff/. "
                "Consumes task-card.md and scope.json. "
                "CACHE_WRITE — writes only to .smartdev/runs/, does NOT modify source files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Task run identifier (.smartdev/runs/<run_id>/)",
                    },
                    "changed_files": {
                        "type": "array",
                        "description": "(Optional) Changed file paths for Scope Gate integration.",
                        "items": {"type": "string"},
                    },
                    "target": {
                        "type": "string",
                        "description": "(Optional) Change target for impact analysis.",
                    },
                },
                "required": ["run_id"],
            },
        ),
        Tool(
            name="smartdev_handoff_doc",
            description=(
                "Generate doc-steward-pack.md and write to .smartdev/runs/<run_id>/handoff/. "
                "Aggregates manifest, diff, snapshots, doc_map, phase status, "
                "doc.consistency, and update focus. "
                "CACHE_WRITE — writes only to .smartdev/runs/, does NOT modify source files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Task run identifier (.smartdev/runs/<run_id>/)",
                    },
                    "run_tests": {
                        "type": "boolean",
                        "description": "(Optional) Run pytest to collect test results.",
                    },
                },
                "required": ["run_id"],
            },
        ),
        Tool(
            name="smartdev_handoff_review",
            description=(
                "Generate reviewer-pack.md and write to .smartdev/runs/<run_id>/handoff/. "
                "Aggregates risk+impact, changed files, dependency changes, "
                "security checklist, and git.diff.explain. "
                "CACHE_WRITE — writes only to .smartdev/runs/, does NOT modify source files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "run_id": {
                        "type": "string",
                        "description": "Task run identifier (.smartdev/runs/<run_id>/)",
                    },
                    "changed_files": {
                        "type": "array",
                        "description": "(Optional) Changed file paths.",
                        "items": {"type": "string"},
                    },
                    "target": {
                        "type": "string",
                        "description": "(Optional) Change target for impact analysis.",
                    },
                    "run_tests": {
                        "type": "boolean",
                        "description": "(Optional) Run pytest to collect test results.",
                    },
                },
                "required": ["run_id"],
            },
        ),
    ]

    # ── 工具路由表 ────────────────────────────────────────────────

    _HANDLERS = {
        "smartdev_ping":             t.handle_ping,
        "smartdev_version":          t.handle_version,
        "smartdev_list_tools":       t.handle_list_tools,
        "smartdev_code_search":      t.handle_code_search,
        "smartdev_code_impact":      t.handle_code_impact,
        "smartdev_project_map":      t.handle_project_map,
        "smartdev_graph_validate":   t.handle_graph_validate,
        "smartdev_repo_scan":        t.handle_repo_scan,
        "smartdev_risk_check":       t.handle_risk_check,
        "smartdev_architecture_map": t.handle_architecture_map,
        "smartdev_task_plan":        t.handle_task_plan,
        "smartdev_qa_checklist":     t.handle_qa_checklist,
        "smartdev_code_index":       t.handle_code_index,
        "smartdev_patch_propose":    t.handle_patch_propose,
        # Phase 11A Step 7: 只读 Git 工具
        "smartdev_git_status":       t.handle_git_status,
        "smartdev_git_diff_explain": t.handle_git_diff_explain,
        "smartdev_git_commit_plan":  t.handle_git_commit_plan,
        "smartdev_git_release_plan": t.handle_git_release_plan,
        "smartdev_git_merge_check":  t.handle_git_merge_check,
        # Phase 11C Step 7: 只读 Doc Governance 工具
        "smartdev_doc_consistency":  t.handle_doc_consistency,
        "smartdev_doc_update_plan":  t.handle_doc_update_plan,
        # Phase 11B Step 7: 只读 Guard 工具
        "smartdev_guard_run":        t.handle_guard_run,
        "smartdev_change_budget":   t.handle_change_budget,
        "smartdev_dev_guard":       t.handle_dev_guard,
        "smartdev_dependency_guard": t.handle_dependency_guard,
        "smartdev_security_review": t.handle_security_review,
        "smartdev_diff_explain":    t.handle_diff_explain,
        # Phase 11D Step 7: Handoff Pack 工具
        "smartdev_handoff_code":     t.handle_handoff_code,
        "smartdev_handoff_doc":      t.handle_handoff_doc,
        "smartdev_handoff_review":   t.handle_handoff_review,
    }

    # ── 注册 list_tools handler ────────────────────────────────────

    @server.list_tools()
    async def list_tools():
        return _TOOLS

    # ── 注册 call_tool handler ─────────────────────────────────────

    @server.call_tool()
    async def call_tool(name: str, arguments: dict):
        handler = _HANDLERS.get(name)
        if handler is None:
            from mcp.types import TextContent
            from smartdev.mcp import formatter
            return [TextContent(
                type="text",
                text=formatter.error(
                    name,
                    "UNKNOWN_TOOL",
                    f"Tool '{name}' is not registered in this MCP Server instance.",
                ),
            )]
        return await handler(arguments, project_path)

    return server


def run_mcp_server(project_path: Path) -> None:
    """启动 MCP Server（同步入口，供 CLI 调用）

    使用 stdio transport，阻塞直到连接关闭。
    """
    _require_mcp()

    from mcp.server.stdio import stdio_server

    server = create_server(project_path)

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_run())
