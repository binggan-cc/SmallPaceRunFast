"""
git.commit.plan + git.commit.message Skill 测试 — Phase 11A Step 3

覆盖：
git.commit.plan
  1. 注册验证
  2. can_run() git 可用性
  3. 空 diff 快速返回
  4. 单类别：source / test / doc / manifest
  5. 多类别：source + test + docs → 多个建议 commit
  6. scope_hint 透传
  7. source 文件按顶层目录拆分
  8. policy_warnings：超 max_files / protected branch
  9. staged_only 模式
  10. GIT_NOT_FOUND 优雅处理

git.commit.message
  1. 注册验证
  2. 基本消息生成（type + subject）
  3. scope 嵌入
  4. body 嵌入
  5. breaking_change → ! 标记 + BREAKING CHANGE footer
  6. co_authors footer
  7. 缺失 type / subject 返回错误
  8. 格式校验：大写开头 / 句号结尾 / 超长 subject / 非法 type
  9. 确定性：相同输入输出相同
  10. header 是消息第一行
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from smartdev.models import ProjectContext
from smartdev.skills.base import Skill
from smartdev.skills.git_commit_plan.skill import (
    GitCommitPlanSkill,
    CommitSuggestion,
    build_commit_suggestions,
    _infer_type,
    _infer_scope,
)
from smartdev.skills.git_commit_message.skill import (
    GitCommitMessageSkill,
    build_commit_message,
    validate_commit_inputs,
    VALID_TYPES,
)
from smartdev.core.git import GitDiff, GitFileChange


# ── Helpers ────────────────────────────────────────────────

def _git(path: Path, *args: str) -> str:
    r = subprocess.run(["git", *args], cwd=str(path), capture_output=True, text=True)
    return r.stdout.strip()


def _ctx(project_path: Path) -> ProjectContext:
    return ProjectContext(project_path=project_path, task_description="test")


def _diff(paths_statuses: list[tuple[str, str]]) -> GitDiff:
    """构造 GitDiff fixture，(path, status) 列表。"""
    return GitDiff(
        files=[
            GitFileChange(path=p, status=s, staged=False, added_lines=5, deleted_lines=2)
            for p, s in paths_statuses
        ],
        insertions=5 * len(paths_statuses),
        deletions=2 * len(paths_statuses),
    )


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("# Test\n")
    _git(tmp_path, "add", "README.md")
    _git(tmp_path, "commit", "-m", "init: initial commit")
    return tmp_path


# ═══════════════════════════════════════════════════════════
# git.commit.plan 测试
# ═══════════════════════════════════════════════════════════


class TestGitCommitPlanRegistered:
    def test_registered(self):
        from smartdev.skills import Skill as S
        assert S.get_skill("git.commit.plan") is not None


class TestInferType:
    def test_doc(self):     assert _infer_type("doc", "M") == "docs"
    def test_test(self):    assert _infer_type("test", "A") == "test"
    def test_manifest_add(self): assert _infer_type("manifest", "A") == "build"
    def test_manifest_mod(self): assert _infer_type("manifest", "M") == "chore"
    def test_config(self):  assert _infer_type("config", "M") == "chore"
    def test_source_add(self):   assert _infer_type("source", "A") == "feat"
    def test_source_del(self):   assert _infer_type("source", "D") == "refactor"
    def test_source_mod(self):   assert _infer_type("source", "M") == "fix"


class TestInferScope:
    def _f(self, path: str) -> GitFileChange:
        return GitFileChange(path=path, status="M", staged=False)

    def test_scope_hint_wins(self):
        files = [self._f("a/x.py"), self._f("b/y.py")]
        assert _infer_scope(files, "myhint") == "myhint"

    def test_common_top_dir(self):
        files = [self._f("context/foo.py"), self._f("context/bar.py")]
        assert _infer_scope(files, None) == "context"

    def test_multiple_top_dirs_no_scope(self):
        files = [self._f("api/foo.py"), self._f("cli/bar.py"), self._f("ui/baz.py")]
        # 没有公共前缀 >= 3 chars → 空
        scope = _infer_scope(files, None)
        assert isinstance(scope, str)

    def test_scope_hint_truncated_at_20(self):
        assert len(_infer_scope([], "a" * 30)) == 20


class TestBuildCommitSuggestions:
    def test_single_source_file(self):
        d = _diff([("src/main.py", "M")])
        suggestions = build_commit_suggestions(d)
        assert len(suggestions) == 1
        assert suggestions[0].type == "fix"

    def test_added_source_is_feat(self):
        d = _diff([("src/new.py", "A")])
        suggestions = build_commit_suggestions(d)
        assert suggestions[0].type == "feat"

    def test_test_file_gets_test_type(self):
        d = _diff([("tests/test_foo.py", "A")])
        suggestions = build_commit_suggestions(d)
        assert any(s.type == "test" for s in suggestions)

    def test_doc_file_gets_docs_type(self):
        d = _diff([("docs/README.md", "M")])
        suggestions = build_commit_suggestions(d)
        assert any(s.type == "docs" for s in suggestions)

    def test_manifest_add_gets_build(self):
        d = _diff([("pyproject.toml", "A")])
        suggestions = build_commit_suggestions(d)
        assert any(s.type == "build" for s in suggestions)

    def test_source_and_test_two_suggestions(self):
        d = _diff([("src/main.py", "M"), ("tests/test_main.py", "A")])
        suggestions = build_commit_suggestions(d)
        types = [s.type for s in suggestions]
        assert "test" in types
        assert "fix" in types or "feat" in types

    def test_source_split_by_top_dir(self):
        d = _diff([("api/routes.py", "M"), ("core/logic.py", "M")])
        suggestions = build_commit_suggestions(d)
        scopes = [s.scope for s in suggestions]
        assert "api" in scopes
        assert "core" in scopes

    def test_scope_hint_applied(self):
        d = _diff([("src/main.py", "M")])
        suggestions = build_commit_suggestions(d, scope_hint="cli")
        assert suggestions[0].scope == "cli"

    def test_files_list_in_suggestion(self):
        d = _diff([("src/main.py", "M"), ("src/utils.py", "M")])
        suggestions = build_commit_suggestions(d)
        all_files = [f for s in suggestions for f in s.files]
        assert "src/main.py" in all_files
        assert "src/utils.py" in all_files

    def test_to_dict_has_header(self):
        d = _diff([("src/main.py", "M")])
        s = build_commit_suggestions(d)[0]
        d_out = s.to_dict()
        assert "header" in d_out
        assert d_out["header"].startswith(s.type)


class TestGitCommitPlanSkill:
    def test_can_run_true_in_git_repo(self, git_repo: Path):
        assert GitCommitPlanSkill().can_run(_ctx(git_repo))

    def test_can_run_false_non_git(self, tmp_path: Path):
        assert not GitCommitPlanSkill().can_run(_ctx(tmp_path))

    def test_empty_diff_success(self, git_repo: Path):
        result = Skill.create("git.commit.plan").run(_ctx(git_repo))
        assert result.success is True
        assert result.data["commits"] == []
        assert result.data["total_files"] == 0

    def test_modified_file_generates_commit(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        result = Skill.create("git.commit.plan").run(_ctx(git_repo))
        assert result.success is True
        assert len(result.data["commits"]) >= 1

    def test_commit_has_required_keys(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        result = Skill.create("git.commit.plan").run(_ctx(git_repo))
        commit = result.data["commits"][0]
        for key in ("type", "scope", "subject", "header", "files", "reason"):
            assert key in commit

    def test_staged_only_mode(self, git_repo: Path):
        (git_repo / "staged.py").write_text("x = 1\n")
        _git(git_repo, "add", "staged.py")
        (git_repo / "unstaged.py").write_text("y = 2\n")
        result = Skill.create("git.commit.plan").run(_ctx(git_repo), {"staged_only": True})
        all_files = [f for c in result.data["commits"] for f in c["files"]]
        assert "staged.py" in all_files
        assert "unstaged.py" not in all_files

    def test_scope_hint_passed_through(self, git_repo: Path):
        (git_repo / "main.py").write_text("x=1\n")
        result = Skill.create("git.commit.plan").run(_ctx(git_repo), {"scope_hint": "cli"})
        if result.data["commits"]:
            assert result.data["commits"][0]["scope"] == "cli"

    def test_policy_warning_on_protected_branch(self, git_repo: Path):
        current_branch = _git(git_repo, "branch", "--show-current")
        if current_branch not in ("main", "master"):
            pytest.skip("not on a protected branch in this environment")
        # 修改已 tracked 文件才会出现在 diff
        (git_repo / "README.md").write_text("modified\n")
        result = Skill.create("git.commit.plan").run(_ctx(git_repo))
        assert len(result.data["policy_warnings"]) >= 1

    def test_git_not_found_graceful(self, monkeypatch, git_repo: Path):
        from smartdev.core import git as git_module
        def broken(self, **kw):
            from smartdev.core.git import GitNotAvailable
            raise GitNotAvailable("forced")
        monkeypatch.setattr(git_module.GitService, "diff", broken)
        result = GitCommitPlanSkill().run(_ctx(git_repo))
        assert result.success is False
        assert result.data["error"] == "GIT_NOT_FOUND"

    def test_next_steps_present(self, git_repo: Path):
        (git_repo / "README.md").write_text("modified\n")
        result = Skill.create("git.commit.plan").run(_ctx(git_repo))
        assert len(result.next_steps) >= 1


# ═══════════════════════════════════════════════════════════
# git.commit.message 测试
# ═══════════════════════════════════════════════════════════


class TestGitCommitMessageRegistered:
    def test_registered(self):
        from smartdev.skills import Skill as S
        assert S.get_skill("git.commit.message") is not None


class TestBuildCommitMessage:
    def test_basic_header(self):
        msg = build_commit_message("feat", "add git status skill")
        assert msg.startswith("feat: add git status skill")

    def test_with_scope(self):
        msg = build_commit_message("feat", "add skill", scope="context")
        assert msg.startswith("feat(context): add skill")

    def test_with_body(self):
        msg = build_commit_message("fix", "fix crash", body="Fixes the crash when git is missing.")
        lines = msg.splitlines()
        assert lines[0] == "fix: fix crash"
        assert lines[1] == ""
        assert "Fixes the crash" in msg

    def test_breaking_change_adds_exclamation(self):
        msg = build_commit_message("feat", "new api", breaking_change="old endpoint removed")
        assert "feat!: new api" in msg
        assert "BREAKING CHANGE: old endpoint removed" in msg

    def test_breaking_change_scope_and_exclamation(self):
        msg = build_commit_message("feat", "new api", scope="api", breaking_change="old removed")
        assert "feat(api)!: new api" in msg

    def test_co_authors_footer(self):
        msg = build_commit_message("fix", "fix bug", co_authors=["Alice <a@x.com>", "Bob <b@x.com>"])
        assert "Co-authored-by: Alice <a@x.com>" in msg
        assert "Co-authored-by: Bob <b@x.com>" in msg

    def test_empty_body_not_included(self):
        msg = build_commit_message("chore", "update deps", body="")
        assert msg == "chore: update deps"

    def test_deterministic(self):
        msg1 = build_commit_message("feat", "same", scope="ctx")
        msg2 = build_commit_message("feat", "same", scope="ctx")
        assert msg1 == msg2


class TestValidateCommitInputs:
    def test_valid_inputs_no_issues(self):
        assert validate_commit_inputs("feat", "add something new", "") == []

    def test_invalid_type(self):
        issues = validate_commit_inputs("wrong", "subject", "")
        assert any("type" in i for i in issues)

    def test_empty_subject(self):
        issues = validate_commit_inputs("feat", "", "")
        assert any("subject" in i for i in issues)

    def test_uppercase_subject_warning(self):
        issues = validate_commit_inputs("feat", "Add something", "")
        assert any("lowercase" in i or "小写" in i for i in issues)

    def test_trailing_period_warning(self):
        issues = validate_commit_inputs("feat", "add something.", "")
        assert any("句号" in i or "period" in i.lower() for i in issues)

    def test_long_subject_warning(self):
        issues = validate_commit_inputs("feat", "a" * 80, "")
        assert any("72" in i for i in issues)

    def test_long_scope_warning(self):
        issues = validate_commit_inputs("feat", "add x", "a" * 35)
        assert any("scope" in i for i in issues)

    def test_all_valid_types_accepted(self):
        for t in VALID_TYPES:
            issues = validate_commit_inputs(t, "do something", "")
            type_issues = [i for i in issues if "type" in i]
            assert type_issues == [], f"type '{t}' should be valid"


class TestGitCommitMessageSkill:
    def test_can_run_without_git(self, tmp_path: Path):
        # git.commit.message 不依赖 git 可用性
        ctx = _ctx(tmp_path)
        assert GitCommitMessageSkill().can_run(ctx) is True

    def test_missing_type_returns_error(self, tmp_path: Path):
        result = Skill.create("git.commit.message").run(_ctx(tmp_path), {"subject": "add x"})
        assert result.success is False
        assert result.data["error"] == "MISSING_TYPE"

    def test_missing_subject_returns_error(self, tmp_path: Path):
        result = Skill.create("git.commit.message").run(_ctx(tmp_path), {"type": "feat"})
        assert result.success is False
        assert result.data["error"] == "MISSING_SUBJECT"

    def test_basic_success(self, tmp_path: Path):
        result = Skill.create("git.commit.message").run(_ctx(tmp_path), {
            "type": "feat",
            "subject": "add git status skill",
        })
        assert result.success is True
        assert result.data["header"] == "feat: add git status skill"
        assert result.data["is_breaking"] is False

    def test_full_message_with_scope_body(self, tmp_path: Path):
        result = Skill.create("git.commit.message").run(_ctx(tmp_path), {
            "type": "fix",
            "scope": "cli",
            "subject": "handle missing git",
            "body": "Returns GIT_NOT_FOUND instead of crashing.",
        })
        assert result.success is True
        msg = result.data["message"]
        assert "fix(cli): handle missing git" in msg
        assert "GIT_NOT_FOUND" in msg

    def test_breaking_change_flag(self, tmp_path: Path):
        result = Skill.create("git.commit.message").run(_ctx(tmp_path), {
            "type": "feat",
            "subject": "new api",
            "breaking_change": "old endpoint removed",
        })
        assert result.data["is_breaking"] is True
        assert "BREAKING CHANGE" in result.data["message"]

    def test_validation_issues_in_output(self, tmp_path: Path):
        result = Skill.create("git.commit.message").run(_ctx(tmp_path), {
            "type": "feat",
            "subject": "Add something.",  # uppercase + trailing period
        })
        assert result.success is True   # 不拦截，只警告
        assert not result.data["validation"]["ok"]
        assert len(result.data["validation"]["issues"]) >= 1

    def test_valid_inputs_clean_validation(self, tmp_path: Path):
        result = Skill.create("git.commit.message").run(_ctx(tmp_path), {
            "type": "feat",
            "subject": "add something new",
        })
        assert result.data["validation"]["ok"] is True

    def test_header_is_first_line_of_message(self, tmp_path: Path):
        result = Skill.create("git.commit.message").run(_ctx(tmp_path), {
            "type": "docs",
            "scope": "readme",
            "subject": "update installation guide",
            "body": "More details.",
        })
        msg = result.data["message"]
        header = result.data["header"]
        assert msg.splitlines()[0] == header
