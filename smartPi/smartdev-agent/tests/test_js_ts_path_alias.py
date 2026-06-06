"""
Phase 6.3 Step 5 — tsconfig paths alias 解析测试

验证 tsconfig/jsconfig compilerOptions.paths 的 alias 解析：
- 精确匹配: "@types": ["src/types.ts"]
- 通配符匹配: "@/*": ["src/*"]
- baseUrl 支持
- alias 文件不存在 → unresolved
- 无 tsconfig → alias 不启用
- external deps 不受影响
- relative import 不回退
"""

import json
import shutil
from pathlib import Path

import pytest

from smartdev.context.graph_validator import validate_graph
from smartdev.context.node_bridge import is_node_available
from smartdev.context.project_index import ProjectIndex
from smartdev.context.project_map import generate_project_map
from smartdev.context.tsconfig_resolver import TsConfigResolver


# ── Fixture Builders ─────────────────────────────────────────


def _build_alias_fixture(tmp_path: Path) -> Path:
    """构建含 tsconfig paths alias 的 fixture 项目

    目录：
        project/
        ├── tsconfig.json       ← baseUrl: ".", paths: { "@/*": ["src/*"], "@types": ["src/types.ts"] }
        ├── src/
        │   ├── index.ts         ← import { App } from '@/app'
        │   ├── app.ts           ← export class App { }
        │   ├── types.ts         ← export interface Config { }
        │   ├── lib/
        │   │   └── helper.ts    ← export function helper() { }
        │   └── utils/
        │       └── index.ts     ← export const VERSION = '1.0'
    """
    project = tmp_path / "alias_fixture"
    project.mkdir()

    # tsconfig with paths aliases
    (project / "tsconfig.json").write_text(json.dumps({
        "compilerOptions": {
            "baseUrl": ".",
            "paths": {
                "@/*": ["src/*"],
                "@types": ["src/types.ts"],
            },
        },
    }))

    # package.json
    (project / "package.json").write_text(json.dumps({
        "name": "alias-fixture",
        "type": "module",
    }))

    src = project / "src"
    src.mkdir()

    # src/index.ts — uses alias imports
    (src / "index.ts").write_text("""\
import { App } from '@/app';
import { Config } from '@types';
import { helper } from '@/lib/helper';
import { VERSION } from '@/utils';
import { Hono } from 'hono';
""")

    # src/app.ts
    (src / "app.ts").write_text("""\
export class App {
  start() {
    console.log('App started');
  }
}
""")

    # src/types.ts
    (src / "types.ts").write_text("""\
export interface Config {
  name: string;
}
""")

    # src/lib/helper.ts
    lib = src / "lib"
    lib.mkdir()
    (lib / "helper.ts").write_text("""\
export function helper(): string {
  return 'helper';
}
""")

    # src/utils/index.ts
    utils = src / "utils"
    utils.mkdir()
    (utils / "index.ts").write_text("""\
export const VERSION = '1.0';
""")

    return project


def _build_base_url_fixture(tmp_path: Path) -> Path:
    """构建 baseUrl != '.' 的 fixture"""
    project = tmp_path / "baseurl_fixture"
    project.mkdir()

    (project / "tsconfig.json").write_text(json.dumps({
        "compilerOptions": {
            "baseUrl": "src",
            "paths": {
                "@lib/*": ["lib/*"],
            },
        },
    }))

    (project / "package.json").write_text('{"name":"baseurl-fixture"}')

    src = project / "src"
    src.mkdir()
    lib = src / "lib"
    lib.mkdir()

    (lib / "util.ts").write_text("export const x = 1;\n")

    (src / "main.ts").write_text("""\
import { x } from '@lib/util';
""")

    return project


def _build_no_tsconfig_fixture(tmp_path: Path) -> Path:
    """构建无 tsconfig 的 fixture"""
    project = tmp_path / "no_tsconfig_fixture"
    project.mkdir()

    (project / "package.json").write_text('{"name":"no-tsconfig"}')

    src = project / "src"
    src.mkdir()
    (src / "main.ts").write_text("""\
import { x } from '@/lib/x';  // 应为 external (无 alias)
import { y } from 'hono';     // external
""")

    return project


def _build_jsconfig_fixture(tmp_path: Path) -> Path:
    """构建 jsconfig.json 的 fixture"""
    project = tmp_path / "jsconfig_fixture"
    project.mkdir()

    (project / "jsconfig.json").write_text(json.dumps({
        "compilerOptions": {
            "baseUrl": ".",
            "paths": {
                "~/*": ["./lib/*"],
            },
        },
    }))

    lib = project / "lib"
    lib.mkdir()
    (lib / "math.js").write_text("export const PI = 3.14;\n")

    (project / "index.js").write_text("""\
import { PI } from '~/math';
""")

    return project


# ── Helpers ───────────────────────────────────────────────────


def _relations_by_source(index: ProjectIndex, source_file: str) -> list[dict]:
    conn = index.store.connect()
    rows = conn.execute(
        "SELECT source_id, target_id, type, metadata_json FROM relations WHERE source_id = ?",
        (f"code:module:{source_file}",),
    ).fetchall()
    return [{"source_id": r["source_id"], "target_id": r["target_id"],
             "type": r["type"],
             "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {}}
            for r in rows]


# ── Tests ────────────────────────────────────────────────────


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node.js not installed",
)
class TestTsConfigPathAlias:
    """Phase 6.3 Step 5 — tsconfig paths alias 解析"""

    # ── TsConfigResolver 单元测试 ──

    def test_resolver_reads_tsconfig(self, tmp_path: Path):
        """TsConfigResolver 读取 tsconfig.json"""
        project = _build_alias_fixture(tmp_path)
        resolver = TsConfigResolver(project)
        assert resolver.paths.has_config
        assert resolver.paths.config_file == "tsconfig.json"
        assert resolver.paths.base_url == "."

    def test_exact_alias_match(self, tmp_path: Path):
        """精确 alias 匹配"""
        project = _build_alias_fixture(tmp_path)
        resolver = TsConfigResolver(project)
        result = resolver.resolve("@types")
        assert result is not None
        assert result["mapped_path"] == "src/types.ts"
        assert result["matched_alias"] == "@types"

    def test_wildcard_alias_match(self, tmp_path: Path):
        """通配符 alias 匹配"""
        project = _build_alias_fixture(tmp_path)
        resolver = TsConfigResolver(project)
        result = resolver.resolve("@/lib/helper")
        assert result is not None
        assert result["mapped_path"] == "src/lib/helper"
        assert result["matched_alias"] == "@/*"

    def test_no_match_returns_none(self, tmp_path: Path):
        """不匹配返回 None"""
        project = _build_alias_fixture(tmp_path)
        resolver = TsConfigResolver(project)
        result = resolver.resolve("hono")
        assert result is None

    def test_no_tsconfig_returns_none(self, tmp_path: Path):
        """无 tsconfig 时 resolve 返回 None"""
        project = _build_no_tsconfig_fixture(tmp_path)
        resolver = TsConfigResolver(project)
        assert not resolver.paths.has_config
        assert resolver.resolve("@/x") is None

    # ── 集成测试：index → relations ──

    def test_alias_resolved_to_code_module(self, tmp_path: Path):
        """alias import → code:module:{resolved_path}"""
        project = _build_alias_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        relations = _relations_by_source(index, "src/index.ts")
        target_ids = [r["target_id"] for r in relations]

        # @/app → code:module:src/app.ts
        assert "code:module:src/app.ts" in target_ids

        # @types → code:module:src/types.ts
        assert "code:module:src/types.ts" in target_ids

        # @/lib/helper → code:module:src/lib/helper.ts
        assert "code:module:src/lib/helper.ts" in target_ids

        # @/utils → code:module:src/utils/index.ts
        assert "code:module:src/utils/index.ts" in target_ids

        index.close()

    def test_alias_metadata_has_resolution_info(self, tmp_path: Path):
        """alias relation 的 metadata 包含 resolution_kind=tsconfig_paths"""
        project = _build_alias_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        relations = _relations_by_source(index, "src/index.ts")
        # 找 alias 的 relation
        alias_rels = [r for r in relations
                      if r["metadata"].get("resolution_kind") == "tsconfig_paths"
                      or r["metadata"].get("resolution_kind") == "tsconfig_paths_index"]
        assert len(alias_rels) > 0

        for rel in alias_rels:
            meta = rel["metadata"]
            assert meta["resolved"] is True
            assert "matched_alias" in meta
            assert meta["raw_specifier"].startswith("@")

        index.close()

    def test_base_url_alias(self, tmp_path: Path):
        """baseUrl 结合 alias 正确解析"""
        project = _build_base_url_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        relations = _relations_by_source(index, "src/main.ts")
        target_ids = [r["target_id"] for r in relations]

        # @lib/util + baseUrl=src → code:module:src/lib/util.ts
        assert "code:module:src/lib/util.ts" in target_ids

        index.close()

    def test_alias_file_not_found(self, tmp_path: Path):
        """alias 匹配但文件不存在 → unresolved:alias_file_not_found"""
        project = _build_alias_fixture(tmp_path)
        # 添加一个 alias import 指向不存在的文件
        (project / "src" / "broken.ts").write_text("""\
import { Missing } from '@/nonexistent';
""")

        index = ProjectIndex(project)
        index.index()

        relations = _relations_by_source(index, "src/broken.ts")
        target_ids = [r["target_id"] for r in relations]
        unresolved = [t for t in target_ids if t.startswith("unresolved:alias_file_not_found:")]
        assert len(unresolved) > 0

        for rel in relations:
            if rel["target_id"].startswith("unresolved:alias"):
                assert rel["metadata"]["resolved"] is False
                assert rel["metadata"]["resolution_kind"] == "tsconfig_paths_file_not_found"

        index.close()

    def test_no_tsconfig_alias_not_enabled(self, tmp_path: Path):
        """无 tsconfig 时 @/ 被视为 external"""
        project = _build_no_tsconfig_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        relations = _relations_by_source(index, "src/main.ts")
        target_ids = [r["target_id"] for r in relations]

        # @/lib/x → external (无 alias 配置)
        assert any(t.startswith("external:") and "@/lib/x" in t or "@" in t for t in target_ids)

        index.close()

    def test_external_deps_unaffected(self, tmp_path: Path):
        """external dep（如 hono）不受 alias 影响"""
        project = _build_alias_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        relations = _relations_by_source(index, "src/index.ts")
        target_ids = [r["target_id"] for r in relations]

        # hono → external
        assert any("hono" in t and t.startswith("external:") for t in target_ids)

        index.close()

    def test_relative_import_still_works(self, tmp_path: Path):
        """relative import 行为不受 alias 影响"""
        project = _build_alias_fixture(tmp_path)
        # 添加一个使用 relative import 的文件
        (project / "src" / "extra.ts").write_text("""\
import { App } from './app';
""")

        index = ProjectIndex(project)
        index.index()

        relations = _relations_by_source(index, "src/extra.ts")
        target_ids = [r["target_id"] for r in relations]

        # ./app → code:module:src/app.ts (relative, not alias)
        assert "code:module:src/app.ts" in target_ids

        index.close()

    def test_jsconfig_supported(self, tmp_path: Path):
        """jsconfig.json 同样生效"""
        project = _build_jsconfig_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        relations = _relations_by_source(index, "index.js")
        target_ids = [r["target_id"] for r in relations]

        # ~/math → code:module:lib/math.js
        assert "code:module:lib/math.js" in target_ids

        index.close()

    def test_graph_validate_alias_warning(self, tmp_path: Path):
        """graph.validate 对 alias unresolved 输出 warning"""
        project = _build_alias_fixture(tmp_path)
        (project / "src" / "broken.ts").write_text("""\
import { Missing } from '@/nonexistent';
""")

        index = ProjectIndex(project)
        index.index()

        result = validate_graph(index.store)
        index.close()

        alias_warnings = [w for w in result.warnings if w.category == "alias_target_not_found"]
        assert len(alias_warnings) >= 1
        assert "@/nonexistent" in alias_warnings[0].message
        assert result.stats.get("alias_target_not_found", 0) >= 1

    def test_project_map_with_alias(self, tmp_path: Path):
        """project.map 正确处理 alias import"""
        project = _build_alias_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        project_map = generate_project_map(index.store, "alias-test")
        index.close()

        # 应该有 modules
        assert len(project_map.modules) > 0

        # alias 解析的模块应该在 modules 中
        module_paths = [m.file_path for m in project_map.modules]
        assert any("src/app.ts" in p for p in module_paths)
        assert any("src/types.ts" in p for p in module_paths)
