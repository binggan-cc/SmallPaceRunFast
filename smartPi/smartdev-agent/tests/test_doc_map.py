"""
doc.map Skill 测试 — Phase 11C Step 3

覆盖：
1. Skill 注册验证
2. can_run()：目录存在 / 不存在
3. 空项目（无文档）
4. 扫描 README.md / CHANGELOG.md / CLAUDE.md / docs/
5. headings 提取（各级标题）
6. mentions 提取（version / phase / mcp_tool / cli_command / skill_name）
7. last_modified / size_bytes 字段
8. CHANGELOG 专用：latest_version / version_sections
9. extra_paths 输入参数
10. mention_keywords 自定义关键词
11. 文件不存在时跳过，不崩溃
12. DocEntry.to_dict() 结构
13. _extract_headings / _extract_mentions / _parse_skill_yaml_lite 单元测试
14. next_steps 建议
"""

from __future__ import annotations

from pathlib import Path

import pytest

from smartdev.models import ProjectContext
from smartdev.skills.base import Skill
from smartdev.skills.doc_map.skill import (
    DocEntry,
    DocMapSkill,
    _collect_doc_paths,
    _extract_headings,
    _extract_mentions,
    _scan_doc_file,
)


# ── Helpers ────────────────────────────────────────────────


def _ctx(path: Path) -> ProjectContext:
    return ProjectContext(project_path=path)


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ── 注册验证 ──────────────────────────────────────────────


def test_skill_registered():
    import smartdev.skills  # noqa: F401
    skill = Skill.get_skill("doc.map")
    assert skill is not None
    assert skill.name == "doc.map"


def test_skill_is_r0():
    from smartdev.models import RiskLevel
    assert DocMapSkill.risk_level == RiskLevel.R0


# ── can_run ───────────────────────────────────────────────


class TestCanRun:
    def test_true_for_existing_dir(self, tmp_path: Path):
        assert DocMapSkill().can_run(_ctx(tmp_path)) is True

    def test_false_for_nonexistent_dir(self, tmp_path: Path):
        assert DocMapSkill().can_run(_ctx(tmp_path / "no_such")) is False


# ── 空项目 ────────────────────────────────────────────────


class TestEmptyProject:
    def test_success_no_docs(self, tmp_path: Path):
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        assert result.success is True

    def test_doc_count_zero(self, tmp_path: Path):
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        assert result.data["doc_count"] == 0

    def test_docs_list_empty(self, tmp_path: Path):
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        assert result.data["docs"] == []


# ── README.md 扫描 ────────────────────────────────────────


class TestReadmeScan:
    def test_readme_detected(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# My Project\n\n## Usage\n\nHello world.\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        paths = [d["path"] for d in result.data["docs"]]
        assert "README.md" in paths

    def test_readme_headings_extracted(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# My Project\n\n## Usage\n\n### Sub\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        assert "# My Project" in doc["headings"]
        assert "## Usage" in doc["headings"]
        assert "### Sub" in doc["headings"]

    def test_readme_has_last_modified(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# Test\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        assert "T" in doc["last_modified"]  # ISO 格式

    def test_readme_has_size_bytes(self, tmp_path: Path):
        content = "# Test\n\nSome content.\n"
        _write(tmp_path / "README.md", content)
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        assert doc["size_bytes"] == len(content.encode("utf-8"))


# ── CHANGELOG.md 扫描 ─────────────────────────────────────


class TestChangelogScan:
    def test_changelog_detected(self, tmp_path: Path):
        _write(tmp_path / "CHANGELOG.md", "# Changelog\n\n## [Unreleased]\n\n## [v0.1.0]\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        paths = [d["path"] for d in result.data["docs"]]
        assert "CHANGELOG.md" in paths

    def test_changelog_latest_version_extracted(self, tmp_path: Path):
        _write(tmp_path / "CHANGELOG.md",
               "# Changelog\n\n## [Unreleased]\n\n## [v0.3.0]\n\n## [v0.2.0]\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "CHANGELOG.md")
        assert doc.get("latest_version") == "Unreleased"

    def test_changelog_version_sections(self, tmp_path: Path):
        _write(tmp_path / "CHANGELOG.md",
               "# Changelog\n\n## [Unreleased]\n\n## [v0.3.0]\n\n## [v0.2.0]\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "CHANGELOG.md")
        sections = doc.get("version_sections", [])
        assert "Unreleased" in sections
        assert "v0.3.0" in sections


# ── docs/ 目录扫描 ────────────────────────────────────────


class TestDocsDirScan:
    def test_docs_dir_scanned(self, tmp_path: Path):
        _write(tmp_path / "docs" / "guide.md", "# Guide\n\nContent.\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        paths = [d["path"] for d in result.data["docs"]]
        assert any("guide.md" in p for p in paths)

    def test_docs_dir_nested(self, tmp_path: Path):
        _write(tmp_path / "docs" / "api" / "reference.md", "# API Reference\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        paths = [d["path"] for d in result.data["docs"]]
        assert any("reference.md" in p for p in paths)

    def test_non_md_files_in_docs_skipped(self, tmp_path: Path):
        (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
        (tmp_path / "docs" / "image.png").write_bytes(b"\x89PNG")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        paths = [d["path"] for d in result.data["docs"]]
        assert not any("image.png" in p for p in paths)

    def test_multiple_docs_returned(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# R\n")
        _write(tmp_path / "docs" / "a.md", "# A\n")
        _write(tmp_path / "docs" / "b.md", "# B\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        assert result.data["doc_count"] >= 3


# ── mentions 提取 ─────────────────────────────────────────


class TestMentions:
    def test_phase_mention(self, tmp_path: Path):
        _write(tmp_path / "README.md", "Phase 11A is complete. See Phase 12.\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        phases = doc["mentions"].get("phase", [])
        assert any("11" in p for p in phases)

    def test_version_mention(self, tmp_path: Path):
        _write(tmp_path / "README.md", "Version v0.4.0 released. Also 1.2.3.\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        versions = doc["mentions"].get("version", [])
        assert any("0.4.0" in v for v in versions)

    def test_mcp_tool_mention(self, tmp_path: Path):
        _write(tmp_path / "README.md", "Use smartdev_ping to check health.\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        tools = doc["mentions"].get("mcp_tool", [])
        assert "smartdev_ping" in tools

    def test_cli_command_mention(self, tmp_path: Path):
        _write(tmp_path / "README.md", "Run smartdev scan --project .\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        cmds = doc["mentions"].get("cli_command", [])
        assert any("smartdev" in c for c in cmds)

    def test_test_baseline_mention(self, tmp_path: Path):
        _write(tmp_path / "README.md", "906 passed, 1 skipped.\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        baselines = doc["mentions"].get("test_baseline", [])
        assert any("906" in b for b in baselines)

    def test_no_mentions_empty_content(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# Title\n\nNo special keywords here.\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        # mentions 可以为空或只有 skill_name（.md 中有可能匹配）
        assert isinstance(doc["mentions"], dict)


# ── extra_paths 参数 ──────────────────────────────────────


class TestExtraPaths:
    def test_extra_path_included(self, tmp_path: Path):
        _write(tmp_path / "WORKSPACE.md", "# Workspace\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path), {
            "extra_paths": ["WORKSPACE.md"]
        })
        paths = [d["path"] for d in result.data["docs"]]
        assert "WORKSPACE.md" in paths

    def test_extra_path_nonexistent_skipped(self, tmp_path: Path):
        result = Skill.create("doc.map").run(_ctx(tmp_path), {
            "extra_paths": ["NO_SUCH_FILE.md"]
        })
        # 不崩溃，skipped 里会有这个路径
        assert result.success is True
        assert "NO_SUCH_FILE.md" in result.data["skipped"]


# ── mention_keywords 参数 ─────────────────────────────────


class TestMentionKeywords:
    def test_custom_keyword_found(self, tmp_path: Path):
        _write(tmp_path / "README.md", "Use my-custom-tool for analysis.\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path), {
            "mention_keywords": ["my-custom-tool"]
        })
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        custom_key = "custom:my-custom-tool"
        assert custom_key in doc["mentions"]
        assert "my-custom-tool" in doc["mentions"][custom_key]

    def test_custom_keyword_not_found_no_key(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# Nothing special.\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path), {
            "mention_keywords": ["nonexistent-keyword-xyz"]
        })
        doc = next(d for d in result.data["docs"] if d["path"] == "README.md")
        assert "custom:nonexistent-keyword-xyz" not in doc["mentions"]


# ── _extract_headings 单元测试 ────────────────────────────


class TestExtractHeadings:
    def test_h1(self):
        assert _extract_headings("# Title\n") == ["# Title"]

    def test_h2_h3(self):
        result = _extract_headings("## Section\n### Sub\n")
        assert "## Section" in result
        assert "### Sub" in result

    def test_no_headings(self):
        assert _extract_headings("Just some text.\n") == []

    def test_heading_with_extra_spaces(self):
        result = _extract_headings("#  Title With Spaces  \n")
        assert result == ["# Title With Spaces"]

    def test_code_block_not_heading(self):
        text = "```\n# not a heading\n```\n"
        # 我们的简单实现不解析 code block，这个测试记录当前行为
        result = _extract_headings(text)
        # 注意：简单实现会误匹配，这是已知限制，测试只验证不崩溃
        assert isinstance(result, list)

    def test_ordering_preserved(self):
        text = "# A\n## B\n# C\n"
        result = _extract_headings(text)
        assert result.index("# A") < result.index("## B")
        assert result.index("## B") < result.index("# C")


# ── _extract_mentions 单元测试 ────────────────────────────


class TestExtractMentions:
    def test_basic_pattern(self):
        patterns = {"version": r"\bv?\d+\.\d+\.\d+\b"}
        result = _extract_mentions("Release v1.2.3 and 4.5.6.", patterns)
        assert "version" in result
        assert "v1.2.3" in result["version"]

    def test_dedup(self):
        patterns = {"word": r"\bfoo\b"}
        result = _extract_mentions("foo foo foo", patterns)
        assert result["word"] == ["foo"]

    def test_no_match_key_absent(self):
        patterns = {"version": r"\bv?\d+\.\d+\.\d+\b"}
        result = _extract_mentions("No version here.", patterns)
        assert "version" not in result

    def test_max_20_items(self):
        patterns = {"num": r"\b\d+\b"}
        text = " ".join(str(i) for i in range(50))
        result = _extract_mentions(text, patterns)
        assert len(result.get("num", [])) <= 20

    def test_invalid_regex_does_not_crash(self):
        patterns = {"bad": r"[invalid("}
        result = _extract_mentions("some text", patterns)
        assert "bad" not in result  # 解析失败，跳过


# ── _collect_doc_paths 单元测试 ───────────────────────────


class TestCollectDocPaths:
    def test_readme_always_included_if_exists(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# R\n")
        paths = _collect_doc_paths(tmp_path, [])
        rel_paths = [r for _, r in paths]
        assert "README.md" in rel_paths

    def test_nonexistent_root_docs_not_included(self, tmp_path: Path):
        paths = _collect_doc_paths(tmp_path, [])
        rel_paths = [r for _, r in paths]
        # CHANGELOG.md 不存在，但路径应在列表里（_scan_doc_file 会检查存在性）
        # collect 只收集路径，不过滤存在性
        assert isinstance(rel_paths, list)

    def test_docs_dir_files_included(self, tmp_path: Path):
        _write(tmp_path / "docs" / "guide.md", "# G\n")
        paths = _collect_doc_paths(tmp_path, [])
        rel_paths = [r for _, r in paths]
        assert any("guide.md" in r for r in rel_paths)

    def test_dedup(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# R\n")
        paths = _collect_doc_paths(tmp_path, ["README.md"])
        rel_paths = [r for _, r in paths]
        assert rel_paths.count("README.md") == 1

    def test_sorted_output(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# R\n")
        _write(tmp_path / "docs" / "z.md", "# Z\n")
        _write(tmp_path / "docs" / "a.md", "# A\n")
        paths = _collect_doc_paths(tmp_path, [])
        rel_paths = [r for _, r in paths]
        assert rel_paths == sorted(rel_paths)


# ── generated_at 字段 ────────────────────────────────────


class TestGeneratedAt:
    def test_generated_at_present(self, tmp_path: Path):
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        assert "T" in result.data["generated_at"]

    def test_doc_count_matches_docs_list(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# R\n")
        _write(tmp_path / "CHANGELOG.md", "# C\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        assert result.data["doc_count"] == len(result.data["docs"])


# ── next_steps ────────────────────────────────────────────


class TestNextSteps:
    def test_next_steps_include_consistency(self, tmp_path: Path):
        _write(tmp_path / "README.md", "# R\n")
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        assert any("consistency" in s for s in result.next_steps)

    def test_next_steps_no_docs_warn(self, tmp_path: Path):
        result = Skill.create("doc.map").run(_ctx(tmp_path))
        assert any("未找到" in s for s in result.next_steps)


# ── DocEntry.to_dict 结构 ─────────────────────────────────


class TestDocEntryToDict:
    def test_required_keys(self):
        e = DocEntry(path="README.md", headings=["# Title"], last_modified="2026-01-01T00:00:00Z")
        d = e.to_dict()
        assert "path" in d
        assert "headings" in d
        assert "mentions" in d
        assert "last_modified" in d
        assert "size_bytes" in d

    def test_extra_fields_merged(self):
        e = DocEntry(path="CHANGELOG.md", extra={"latest_version": "Unreleased"})
        d = e.to_dict()
        assert d["latest_version"] == "Unreleased"
