"""
test_handoff_code.py — Phase 11D Step 3 handoff code 聚焦测试

覆盖：
- generate_code_agent_pack 成功生成
- 输出路径在 .smartdev/runs/<run_id>/handoff/code-agent-pack.md
- pack 包含必要节
- run_id 不存在 → 错误
- task-card/scope 缺失 → 错误
- Scope Gate 结果集成
- 字符预算控制
- 相关文件收集
- existing patterns 发现

不覆盖：
- handoff doc / review（Step 4/5）
- MCP 工具（Step 6）
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from smartdev.core.handoff_code import (
    CODE_PACK_CHAR_BUDGET,
    HandoffCodeResult,
    _collect_files_by_pattern,
    _collect_relevant_files,
    _extract_section,
    _find_existing_patterns,
    _is_source_file,
    _read_task_card,
    _read_snippet,
    generate_code_agent_pack,
)
from smartdev.core.run_artifact import ScopeConfig, create_run_artifact


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def tmp_project():
    """临时项目目录。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def _setup_run(
    tmp_project: Path,
    run_id: str = "test-handoff",
    task: str = "",
    **scope_kwargs,
):
    """创建 run artifact 并返回项目路径。"""
    scope = ScopeConfig(**scope_kwargs) if scope_kwargs else ScopeConfig(
        allowed_paths=["smartdev/", "tests/"],
    )
    _, err = create_run_artifact(tmp_project, run_id, task=task, scope=scope, force=True)
    if err:
        raise RuntimeError(f"Failed to create run artifact: {err}")

    # 创建一些示例源文件以供代码片段收集
    (tmp_project / "smartdev" / "core").mkdir(parents=True, exist_ok=True)
    (tmp_project / "smartdev" / "core" / "example.py").write_text(
        '"""Example module."""\n\n\ndef hello():\n    return "world"\n'
    )
    (tmp_project / "tests").mkdir(parents=True, exist_ok=True)
    (tmp_project / "tests" / "test_example.py").write_text(
        '"""Test example."""\n\n\ndef test_hello():\n    assert True\n'
    )

    return tmp_project


# ── _extract_section ──────────────────────────────────────────


class TestExtractSection:
    def test_extracts_goal(self):
        md = "## 目标\n\n这是任务目标。\n\n## 范围\n\n范围内容"
        result = _extract_section(md, "目标")
        assert "这是任务目标" in result

    def test_empty_when_not_found(self):
        md = "## 其他\n内容"
        result = _extract_section(md, "不存在")
        assert result == ""

    def test_stops_at_next_section(self):
        md = "## 目标\n目标内容\n\n## 范围\n范围内容"
        result = _extract_section(md, "目标")
        assert "目标内容" in result
        assert "范围内容" not in result


# ── _read_task_card ──────────────────────────────────────────


class TestReadTaskCard:
    def test_reads_existing(self, tmp_project):
        _setup_run(tmp_project, "r1", task="修复登录Bug")
        run_dir = tmp_project / ".smartdev" / "runs" / "r1"
        content, err = _read_task_card(run_dir)
        assert err is None
        assert "修复登录Bug" in content

    def test_missing_returns_error(self, tmp_project):
        run_dir = tmp_project / ".smartdev" / "runs" / "no-task"
        run_dir.mkdir(parents=True)
        content, err = _read_task_card(run_dir)
        assert content == ""
        assert err is not None


# ── _collect_files_by_pattern ──────────────────────────────────


class TestCollectFilesByPattern:
    def test_directory_pattern(self, tmp_project):
        _setup_run(tmp_project, "p1")
        files = _collect_files_by_pattern(tmp_project, "smartdev/")
        paths = [str(f.relative_to(tmp_project)) for f in files]
        assert any("example.py" in p for p in paths)

    def test_glob_pattern(self, tmp_project):
        _setup_run(tmp_project, "p2")
        # 创建多个 .py 文件
        (tmp_project / "smartdev" / "core" / "a.py").write_text("# a")
        (tmp_project / "smartdev" / "core" / "b.py").write_text("# b")
        files = _collect_files_by_pattern(tmp_project, "smartdev/core/*.py")
        paths = [str(f.relative_to(tmp_project)) for f in files]
        assert len(paths) >= 2
        assert any("a.py" in p for p in paths)
        assert any("b.py" in p for p in paths)

    def test_non_existent_pattern(self, tmp_project):
        files = _collect_files_by_pattern(tmp_project, "nonexistent/")
        assert files == []

    def test_single_file_pattern(self, tmp_project):
        _setup_run(tmp_project, "p4")
        fpath = tmp_project / "smartdev" / "core" / "example.py"
        files = _collect_files_by_pattern(tmp_project, "smartdev/core/example.py")
        assert len(files) == 1
        assert files[0] == fpath

    def test_skips_non_source(self, tmp_project):
        _setup_run(tmp_project, "p5")
        (tmp_project / "smartdev" / "README.txt").write_text("not source")
        files = _collect_files_by_pattern(tmp_project, "smartdev/")
        paths = [str(f.relative_to(tmp_project)) for f in files]
        assert not any("README.txt" in p for p in paths)


# ── _is_source_file ───────────────────────────────────────────


class TestIsSourceFile:
    def test_py_is_source(self, tmp_project):
        assert _is_source_file(tmp_project / "foo.py") is True

    def test_txt_not_source(self, tmp_project):
        assert _is_source_file(tmp_project / "foo.txt") is False

    def test_pycache_skipped(self, tmp_project):
        assert _is_source_file(tmp_project / "__pycache__" / "foo.py") is False


# ── _collect_relevant_files ───────────────────────────────────


class TestCollectRelevantFiles:
    def test_collects_py_files(self, tmp_project):
        _setup_run(tmp_project, "c1")
        files = _collect_relevant_files(tmp_project, ["smartdev/", "tests/"])
        assert len(files) >= 2
        paths = [f[0] for f in files]
        assert any("example.py" in p for p in paths)
        assert any("test_example.py" in p for p in paths)

    def test_respects_max_files(self, tmp_project):
        _setup_run(tmp_project, "c2")
        files = _collect_relevant_files(tmp_project, ["smartdev/", "tests/"], max_files=1)
        assert len(files) == 1

    def test_non_existent_path_skipped(self, tmp_project):
        _setup_run(tmp_project, "c3")
        files = _collect_relevant_files(tmp_project, ["nonexistent/"])
        assert len(files) == 0

    def test_includes_snippets(self, tmp_project):
        _setup_run(tmp_project, "c4")
        files = _collect_relevant_files(tmp_project, ["smartdev/"])
        assert len(files) >= 1
        snippet = files[0][1]
        assert snippet is not None
        assert "hello" in snippet or "Example" in snippet

    def test_changed_files_appear_first(self, tmp_project):
        """changed_files 出现在相关文件列表最前面。"""
        _setup_run(tmp_project, "c5")
        # 创建 changed_files 指向的文件
        (tmp_project / "smartdev" / "core" / "changed_file.py").write_text(
            '"""This is the changed file."""\n\ndef new_func():\n    pass\n'
        )
        files = _collect_relevant_files(
            tmp_project, ["smartdev/", "tests/"],
            changed_files=["smartdev/core/changed_file.py"],
            max_files=10,
        )
        assert len(files) >= 1
        # changed_files 应在第一位
        assert files[0][0] == "smartdev/core/changed_file.py"

    def test_changed_files_deduped(self, tmp_project):
        """changed_files 不会在后续扫描中重复出现。"""
        _setup_run(tmp_project, "c6")
        files = _collect_relevant_files(
            tmp_project, ["smartdev/"],
            changed_files=["smartdev/core/example.py"],  # 这个文件也会被 allowed_paths 扫到
            max_files=10,
        )
        count = sum(1 for f in files if f[0] == "smartdev/core/example.py")
        assert count == 1  # 不应重复

    def test_changed_file_nonexistent_skipped(self, tmp_project):
        """不存在的 changed_file 静默跳过。"""
        _setup_run(tmp_project, "c7")
        files = _collect_relevant_files(
            tmp_project, ["smartdev/"],
            changed_files=["smartdev/core/nonexistent.py"],
            max_files=10,
        )
        assert not any(f[0] == "smartdev/core/nonexistent.py" for f in files)

    def test_glob_pattern_in_allowed_paths(self, tmp_project):
        """allowed_paths 中的 glob 模式工作正常。"""
        _setup_run(tmp_project, "c8")
        (tmp_project / "smartdev" / "core" / "x.py").write_text("# x")
        (tmp_project / "smartdev" / "core" / "y.py").write_text("# y")
        files = _collect_relevant_files(
            tmp_project, ["smartdev/core/*.py"],
        )
        paths = [f[0] for f in files]
        assert len(paths) >= 2


# ── _find_existing_patterns ───────────────────────────────────


class TestFindExistingPatterns:
    def test_finds_directory_with_multiple_py_files(self, tmp_project):
        _setup_run(tmp_project, "p1")
        patterns = _find_existing_patterns(tmp_project, ["smartdev/"])
        # smartdev/core/ 有 example.py，再创建一个
        (tmp_project / "smartdev" / "core" / "other.py").write_text("# other")
        patterns2 = _find_existing_patterns(tmp_project, ["smartdev/"])
        assert len(patterns2) >= 1

    def test_returns_empty_for_no_patterns(self, tmp_project):
        _setup_run(tmp_project, "p2")
        patterns = _find_existing_patterns(tmp_project, ["nonexistent/"])
        assert patterns == []


# ── generate_code_agent_pack ──────────────────────────────────


class TestGenerateCodeAgentPack:
    def test_generates_pack_successfully(self, tmp_project):
        _setup_run(tmp_project, "h1", task="实现新功能X")
        result = generate_code_agent_pack(tmp_project, "h1")
        assert result.error is None
        assert result.output_path is not None
        assert result.output_path.exists()
        assert result.char_count > 0

    def test_output_path_is_under_handoff_dir(self, tmp_project):
        _setup_run(tmp_project, "h2")
        result = generate_code_agent_pack(tmp_project, "h2")
        assert result.error is None
        expected = (
            tmp_project / ".smartdev" / "runs" / "h2" / "handoff" / "code-agent-pack.md"
        )
        assert result.output_path == expected

    def test_pack_contains_required_sections(self, tmp_project):
        _setup_run(tmp_project, "h3", task="测试任务")
        result = generate_code_agent_pack(tmp_project, "h3")
        assert result.error is None
        content = result.output_path.read_text(encoding="utf-8")
        assert "当前任务" in content
        assert "修改范围" in content
        assert "相关文件" in content or "allowed_paths" in content
        assert "参考实现" in content or "existing patterns" in content
        assert "验收标准" in content
        assert "禁止项" in content
        assert "Code Agent 输出规范" in content

    def test_pack_contains_task(self, tmp_project):
        _setup_run(tmp_project, "h4", task="修复登录页面Bug")
        result = generate_code_agent_pack(tmp_project, "h4")
        content = result.output_path.read_text(encoding="utf-8")
        assert "修复登录页面Bug" in content

    def test_pack_contains_scope_info(self, tmp_project):
        _setup_run(
            tmp_project, "h5",
            allowed_paths=["src/only/"],
            max_files=3,
        )
        result = generate_code_agent_pack(tmp_project, "h5")
        content = result.output_path.read_text(encoding="utf-8")
        assert "src/only/" in content
        assert "max_files: 3" in content

    def test_pack_under_char_budget(self, tmp_project):
        _setup_run(tmp_project, "h6")
        result = generate_code_agent_pack(tmp_project, "h6")
        assert result.char_count <= CODE_PACK_CHAR_BUDGET * 1.5  # 允许一些余量

    def test_pack_includes_snippets(self, tmp_project):
        _setup_run(tmp_project, "h7")
        result = generate_code_agent_pack(tmp_project, "h7")
        content = result.output_path.read_text(encoding="utf-8")
        # 应有示例代码片段
        assert "```python" in content or "hello" in content.lower()

    def test_changed_files_in_pack(self, tmp_project):
        """--changed-files 指定的文件出现在 pack 中且排在前面。"""
        _setup_run(tmp_project, "h10")
        # 创建一个标记文件
        (tmp_project / "smartdev" / "core" / "my_feature.py").write_text(
            '"""My feature module."""\n\n\ndef do_work():\n    return 42\n'
        )
        result = generate_code_agent_pack(
            tmp_project, "h10",
            changed_files=["smartdev/core/my_feature.py"],
        )
        content = result.output_path.read_text(encoding="utf-8")
        # changed_file 应出现在相关文件列表中
        assert "my_feature.py" in content
        # 且应该出现在较前位置（在 adapter JSON 之前）
        my_pos = content.find("my_feature.py")
        adapter_pos = content.find("chrome_extension.json") if "chrome_extension.json" in content else 99999
        # changed_file 应该排在最前面（位置 < adapter 位置 或 adapter 不在 pack 中）
        if adapter_pos < 99999:
            assert my_pos < adapter_pos, (
                f"changed_file (pos={my_pos}) 应排在 adapter (pos={adapter_pos}) 之前"
            )

    def test_pack_with_scope_gate_results(self, tmp_project):
        _setup_run(tmp_project, "h8", max_files=1)
        result = generate_code_agent_pack(
            tmp_project, "h8",
            changed_files=["smartdev/a.py", "smartdev/b.py", "README.md"],
        )
        content = result.output_path.read_text(encoding="utf-8")
        assert "Scope Gate" in content
        # 超 max_files 应触发
        assert "超过上限" in content or "max_files" in content.lower()

    def test_pack_with_empty_changed_files(self, tmp_project):
        _setup_run(tmp_project, "h9")
        result = generate_code_agent_pack(
            tmp_project, "h9", changed_files=["smartdev/core/foo.py"],
        )
        content = result.output_path.read_text(encoding="utf-8")
        assert "Scope Gate" in content
        assert "通过" in content


class TestGenerateCodeAgentPackErrors:
    def test_missing_run_dir(self, tmp_project):
        result = generate_code_agent_pack(tmp_project, "no-such-run")
        assert result.error is not None
        assert "不存在" in result.error

    def test_missing_task_card(self, tmp_project):
        run_dir = tmp_project / ".smartdev" / "runs" / "no-task"
        run_dir.mkdir(parents=True)
        # 写入 scope.json 但无 task-card
        from smartdev.core.run_artifact import ScopeConfig
        (run_dir / "scope.json").write_text(ScopeConfig().to_json())
        result = generate_code_agent_pack(tmp_project, "no-task")
        assert result.error is not None
        assert "task-card" in result.error

    def test_missing_scope_json(self, tmp_project):
        run_dir = tmp_project / ".smartdev" / "runs" / "no-scope"
        run_dir.mkdir(parents=True)
        (run_dir / "task-card.md").write_text("# test\n\n## 目标\n\n测试")
        result = generate_code_agent_pack(tmp_project, "no-scope")
        assert result.error is not None
        assert "scope" in result.error.lower()


# ── HandoffCodeResult 序列化 ──────────────────────────────────


class TestHandoffCodeResult:
    def test_to_dict(self):
        result = HandoffCodeResult(
            output_path=Path("/tmp/test/code-agent-pack.md"),
            char_count=5000,
            sections=["1. 当前任务", "2. 修改范围"],
        )
        d = result.to_dict()
        assert d["output_path"] == "/tmp/test/code-agent-pack.md"
        assert d["char_count"] == 5000
        assert len(d["sections"]) == 2
        assert d["error"] is None

    def test_to_dict_with_error(self):
        result = HandoffCodeResult(error="something went wrong")
        d = result.to_dict()
        assert d["output_path"] is None
        assert d["error"] == "something went wrong"


# ── 集成测试：不写源码外产物 ──────────────────────────────────


class TestHandoffCodeDoesNotModifySource:
    def test_only_writes_under_smartdev_runs(self, tmp_project):
        _setup_run(tmp_project, "safe-test")
        # 记录修改前的文件列表
        before = set()
        for f in tmp_project.rglob("*"):
            if f.is_file() and ".smartdev" not in str(f):
                before.add(str(f.relative_to(tmp_project)))

        result = generate_code_agent_pack(tmp_project, "safe-test")

        # 记录修改后的文件列表
        after = set()
        for f in tmp_project.rglob("*"):
            if f.is_file() and ".smartdev" not in str(f):
                after.add(str(f.relative_to(tmp_project)))

        assert result.error is None
        assert before == after  # 源码文件无变化
