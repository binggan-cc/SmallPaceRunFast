"""
Skill: git.diff.explain — 确定性 Diff 结构化解释（R0 只读）

功能：对当前 git diff 输出结构化分析：行数统计、文件分类、风险信号、
      拆分提交建议。不做自然语言总结，让外部 Agent 自行组织语言。
风险：R0（只读，不修改任何文件）

设计约束（phase-11-design.md §3 Q3）：
- 确定性输出，不用 LLM
- 外部 Agent 拿到结构化 diff 后自己组织自然语言
- 与 patch_propose 的 diff_explain 思路一致
- 信号覆盖：protected_path / dependency_manifest / test / docs / multi_module
"""

from __future__ import annotations

from pathlib import Path

from smartdev.core.git import GitDiff, GitFileChange, GitNotAvailable, GitService, load_git_policy
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill

# ── 文件分类规则 ──────────────────────────────────────────

# 测试文件特征
_TEST_PATTERNS = ("test_", "_test.", "/test/", "/tests/", "spec.", ".spec.")
# 文档文件扩展名
_DOC_EXTS = {".md", ".rst", ".txt", ".adoc"}
# 依赖 manifest 文件名
_MANIFEST_FILES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "Pipfile", "Pipfile.lock", "go.mod", "go.sum",
    "Cargo.toml", "Cargo.lock", "Gemfile", "Gemfile.lock",
    "build.gradle", "pom.xml",
}
# 配置文件扩展名
_CONFIG_EXTS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env"}
_CONFIG_NAMES = {
    ".gitignore", ".gitattributes", ".editorconfig", "Makefile",
    "Dockerfile", "docker-compose.yml", ".dockerignore",
}


def _classify_file(path: str) -> str:
    """将文件路径分类为：test / doc / manifest / config / source / other。"""
    p = Path(path)
    name = p.name
    name_lower = name.lower()
    path_lower = path.lower()

    if name_lower in _MANIFEST_FILES:
        return "manifest"
    if any(pat in path_lower for pat in _TEST_PATTERNS):
        return "test"
    if p.suffix in _DOC_EXTS:
        return "doc"
    if name_lower in _CONFIG_NAMES or p.suffix in _CONFIG_EXTS:
        return "config"
    if p.suffix in {".py", ".js", ".ts", ".jsx", ".tsx", ".go",
                    ".java", ".rs", ".cpp", ".c", ".cs", ".rb", ".php"}:
        return "source"
    return "other"


def _compute_signals(
    diff: GitDiff,
    protected_paths: list[str],
) -> dict:
    """从 diff 中提取确定性风险信号。"""
    protected_set = set(protected_paths)
    touches_tests = False
    touches_docs = False
    touches_manifest = False
    touches_protected = False
    protected_hits: list[str] = []

    for f in diff.files:
        cat = _classify_file(f.path)
        if cat == "test":
            touches_tests = True
        elif cat == "doc":
            touches_docs = True
        elif cat == "manifest":
            touches_manifest = True

        # protected path：路径的第一段（如 .git、.smartdev 等）
        first_part = Path(f.path).parts[0] if Path(f.path).parts else ""
        if first_part in protected_set or f.path in protected_set:
            touches_protected = True
            protected_hits.append(f.path)

    return {
        "touches_tests": touches_tests,
        "touches_docs": touches_docs,
        "touches_dependency_manifest": touches_manifest,
        "touches_protected_path": touches_protected,
        "protected_path_hits": protected_hits,
    }


def _compute_risk_hints(
    diff: GitDiff,
    signals: dict,
    max_files_per_commit: int,
) -> list[str]:
    """基于 diff 统计和信号生成风险提示列表。"""
    hints: list[str] = []
    n = len(diff.files)

    if n > max_files_per_commit:
        hints.append(f"large_changeset:{n}_files_exceeds_limit_{max_files_per_commit}")
    elif n > 5:
        hints.append(f"multi_file_change:{n}_files")

    if signals["touches_protected_path"]:
        hints.append("touches_protected_path")
    if signals["touches_dependency_manifest"]:
        hints.append("dependency_manifest_changed")

    # 检测多模块变更：source 文件跨多个顶层目录
    source_dirs = {
        Path(f.path).parts[0]
        for f in diff.files
        if _classify_file(f.path) == "source" and Path(f.path).parts
    }
    if len(source_dirs) > 2:
        hints.append(f"cross_module_change:{len(source_dirs)}_top_level_dirs")

    if diff.insertions + diff.deletions > 300:
        hints.append(f"large_diff:{diff.insertions + diff.deletions}_lines")

    return hints


def _suggest_commit_split(diff: GitDiff) -> list[str]:
    """按文件类型建议 commit 拆分方案。

    规则：source / test / doc / manifest 各自可以是独立 commit。
    如果某类型文件很少（≤ 1 个），与 source commit 合并。
    """
    categories: dict[str, list[str]] = {}
    for f in diff.files:
        cat = _classify_file(f.path)
        categories.setdefault(cat, []).append(f.path)

    splits: list[str] = []
    # 主 source commit（含 config / other）
    main_cats = {"source", "config", "other"}
    main_files = sum(len(v) for k, v in categories.items() if k in main_cats)
    if main_files:
        splits.append(f"source/logic changes ({main_files} files)")

    # tests 单独（若有 2 个以上）
    tests = categories.get("test", [])
    if len(tests) >= 2:
        splits.append(f"test updates ({len(tests)} files)")
    elif tests:
        if splits:
            splits[-1] += f" + tests ({len(tests)} file)"
        else:
            splits.append(f"source + tests ({len(tests)} file)")

    # docs 单独（若有）
    docs = categories.get("doc", [])
    if docs:
        splits.append(f"docs ({len(docs)} files)")

    # manifest 单独（若有）
    manifests = categories.get("manifest", [])
    if manifests:
        splits.append(f"dependency manifest ({len(manifests)} files)")

    return splits if splits else ["single commit (small change)"]


class GitDiffExplainSkill(Skill):
    """确定性 Diff 结构化解释 Skill（R0 只读）

    输出结构化信号和拆分建议，不生成自然语言总结。
    外部 Agent（Claude / Kiro 等）拿到结构化输出后自行组织语言。

    inputs 参数：
        staged: bool  True=只看 staged diff，False=看 worktree diff（默认 False）

    使用示例：
        result = Skill.create("git.diff.explain").run(context)
        result = Skill.create("git.diff.explain").run(context, {"staged": True})
    """

    name = "git.diff.explain"
    description = "对 git diff 做确定性结构化解释：行数统计、文件分类、风险信号、拆分建议"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        if not context.project_path.exists():
            return False
        return GitService(context.project_path).is_available()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        inputs = inputs or {}
        project = context.project_path
        use_staged = bool(inputs.get("staged", False))

        svc = GitService(project)
        try:
            diff = svc.diff(staged=use_staged)
        except GitNotAvailable as e:
            return SkillResult(
                success=False,
                summary=f"git.diff.explain 失败：{e}",
                data={"error": "GIT_NOT_FOUND", "message": str(e)},
                risks=["git 不可用"],
            )

        if not diff.files:
            return SkillResult(
                success=True,
                summary="当前无 diff（工作区干净）",
                data={
                    "summary": {"files_changed": 0, "insertions": 0, "deletions": 0},
                    "signals": {
                        "touches_tests": False,
                        "touches_docs": False,
                        "touches_dependency_manifest": False,
                        "touches_protected_path": False,
                        "protected_path_hits": [],
                    },
                    "file_categories": {},
                    "risk_hints": [],
                    "suggested_commit_split": [],
                    "staged": use_staged,
                },
                next_steps=["工作区干净，无需处理。"],
            )

        # 加载 policy（protected paths 用于信号检测）
        policy = load_git_policy(project)
        protected_paths = list(policy.protected_branches)  # 分支名不是路径，但核心目录也要保护
        # 补充通用保护目录
        _CORE_PROTECTED = [".git", ".smartdev", "node_modules", "dist", "build"]
        protected_paths = list(set(protected_paths + _CORE_PROTECTED))

        # 计算各类别文件
        file_categories: dict[str, list[str]] = {}
        for f in diff.files:
            cat = _classify_file(f.path)
            file_categories.setdefault(cat, []).append(f.path)

        signals = _compute_signals(diff, protected_paths)
        risk_hints = _compute_risk_hints(diff, signals, policy.max_files_per_commit)
        split_suggestion = _suggest_commit_split(diff)

        n = len(diff.files)
        summary_str = (
            f"diff 分析：{n} 个文件，+{diff.insertions} -{diff.deletions} 行"
        )
        if risk_hints:
            summary_str += f"，{len(risk_hints)} 个风险信号"

        return SkillResult(
            success=True,
            summary=summary_str,
            data={
                "summary": {
                    "files_changed": n,
                    "insertions": diff.insertions,
                    "deletions": diff.deletions,
                },
                "signals": signals,
                "file_categories": file_categories,
                "risk_hints": risk_hints,
                "suggested_commit_split": split_suggestion,
                "staged": use_staged,
                "files": [
                    {
                        "path": f.path,
                        "status": f.status,
                        "added": f.added_lines,
                        "deleted": f.deleted_lines,
                        "category": _classify_file(f.path),
                    }
                    for f in diff.files
                ],
            },
            next_steps=_build_next_steps(diff, risk_hints, split_suggestion),
        )


def _build_next_steps(
    diff: GitDiff, risk_hints: list[str], split: list[str]
) -> list[str]:
    steps: list[str] = []
    if len(split) > 1:
        steps.append(
            f"建议拆成 {len(split)} 个 commit：{'; '.join(split)}。"
            "运行 git.commit.plan 生成详细提交方案。"
        )
    else:
        steps.append("运行 git.commit.plan 生成 Conventional Commit 提交建议。")
    if "touches_dependency_manifest" in " ".join(risk_hints):
        steps.append("检测到依赖 manifest 变更，建议运行 dependency.guard（Phase 11B）。")
    if "touches_protected_path" in " ".join(risk_hints):
        steps.append("⚠️ 变更命中 protected path，建议人工审查。")
    return steps
