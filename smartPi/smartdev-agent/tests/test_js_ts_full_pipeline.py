"""
Phase 6.3 Step 3 — JS/TS 全链路集成测试

验证 index → search → project.map → graph.validate 全链路
对 JS/TS 项目端到端闭合。

测试场景：
1. ES module imports（named / default / namespace）
2. Re-exports
3. External dependencies（npm packages）
4. function / class / arrow function / interface / type alias
5. 跨文件 import relations

注意：
- 真实 Node 集成测试用 skipif 保护
- 所有 fixture 在 tmp_path 内动态构建，不依赖外部项目
"""

import json
import shutil
from pathlib import Path

import pytest

from smartdev.context.graph_validator import validate_graph
from smartdev.context.node_bridge import is_node_available
from smartdev.context.project_index import ProjectIndex
from smartdev.context.project_map import generate_project_map


# ── Fixture Builder ─────────────────────────────────────────


def _build_js_ts_fixture(tmp_path: Path) -> Path:
    """构建小型 JS/TS fixture 项目

    目录结构：
        project/
        ├── package.json
        ├── types.ts              # interfaces + re-export
        ├── src/
        │   ├── index.ts          # 主入口，import 多个模块
        │   ├── models.ts         # interface + type alias
        │   ├── api.ts            # 使用 external dep（axios）
        │   └── utils/
        │       ├── helper.ts     # export function
        │       └── format.ts     # export const arrow function
        └── lib/
            └── validator.js      # CommonJS style

    覆盖的 import 模式：
    - named: import { X } from './module'
    - default: import X from './module'
    - namespace: import * as X from './module'
    - bare external: import X from 'axios'
    - re-export: export { X } from './module'
    """
    project = tmp_path / "js_ts_fixture"
    project.mkdir()

    # package.json
    (project / "package.json").write_text(json.dumps({
        "name": "test-fixture",
        "type": "module",
        "dependencies": {"axios": "^1.0.0"},
    }))

    # types.ts — interfaces + re-export
    (project / "types.ts").write_text("""\
export interface Config {
  appName: string;
  debug: boolean;
}

export interface User {
  id: string;
  name: string;
}

// Re-export: 从 models 导出（实际项目中可能跨文件）
export { UserProfile } from './src/models';
""")

    # src/
    src = project / "src"
    src.mkdir()

    # src/index.ts — 主入口
    (src / "index.ts").write_text("""\
import { helper } from './utils/helper';
import { format } from './utils/format';
import { Config } from '../types';
import { User, UserProfile } from './models';
import * as api from './api';

export class App {
  private config: Config;

  constructor(config: Config) {
    this.config = config;
  }

  async start(): Promise<void> {
    const msg = helper();
    const formatted = format(msg);
    console.log(format(`App starting: ${this.config.appName}`));

    const users = await api.fetchUsers();
    users.forEach((u: User) => {
      console.log(format(`User: ${u.name}`));
    });
  }
}

export function createApp(config: Config): App {
  return new App(config);
}
""")

    # src/models.ts — interface + type alias
    (src / "models.ts").write_text("""\
export interface User {
  id: string;
  name: string;
  email: string;
}

export interface UserProfile {
  userId: string;
  bio: string;
  avatar: string;
}

export type Status = 'active' | 'inactive' | 'pending';

export function validateUser(user: User): boolean {
  return user.id.length > 0 && user.name.length > 0;
}
""")

    # src/api.ts — 使用 external dep
    (src / "api.ts").write_text("""\
import axios from 'axios';
import { User } from './models';

const BASE_URL = 'https://api.example.com';

export async function fetchUsers(): Promise<User[]> {
  const response = await axios.get(`${BASE_URL}/users`);
  return response.data as User[];
}

export async function fetchUserById(id: string): Promise<User> {
  const response = await axios.get(`${BASE_URL}/users/${id}`);
  return response.data as User;
}
""")

    # src/utils/
    utils = src / "utils"
    utils.mkdir()

    # src/utils/helper.ts — export function
    (utils / "helper.ts").write_text("""\
export function helper(): string {
  return "Hello from helper!";
}

function internalHelper(): string {
  return "internal";  // not exported
}
""")

    # src/utils/format.ts — arrow functions
    (utils / "format.ts").write_text("""\
export const format = (s: string): string => {
  return `[Formatted] ${s}`;
};

export const truncate = (s: string, maxLen: number): string => {
  return s.length > maxLen ? s.slice(0, maxLen) + '...' : s;
};
""")

    # lib/validator.js — JavaScript with ES imports
    lib = project / "lib"
    lib.mkdir()
    (lib / "validator.js").write_text("""\
import { customAlphabet } from 'nanoid';

const nanoid = customAlphabet('1234567890abcdef', 10);

export function generateId() {
  return nanoid();
}

export function validateEmail(email) {
  return email.includes('@');
}

function internalCheck(value) {
  return value != null;  // not exported
}
""")

    return project


# ── 辅助函数 ─────────────────────────────────────────────────


def _all_artifact_types(index: ProjectIndex) -> set[str]:
    """获取索引中所有 artifact 类型"""
    conn = index.store.connect()
    rows = conn.execute("SELECT DISTINCT type FROM artifacts").fetchall()
    return {r[0] for r in rows}


def _artifacts_by_type(index: ProjectIndex, artifact_type: str) -> list[dict]:
    """按类型获取 artifact"""
    conn = index.store.connect()
    rows = conn.execute(
        "SELECT name, file_path, metadata_json FROM artifacts WHERE type = ?",
        (artifact_type,),
    ).fetchall()
    return [{"name": r["name"], "file_path": r["file_path"],
             "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {}}
            for r in rows]


def _relations_by_source(index: ProjectIndex, source_file: str) -> list[dict]:
    """获取某文件的 import relations"""
    conn = index.store.connect()
    rows = conn.execute(
        """SELECT r.source_id, r.target_id, r.type, r.metadata_json
           FROM relations r
           WHERE r.source_id = ?
           ORDER BY r.target_id""",
        (f"code:module:{source_file}",),
    ).fetchall()
    return [{"source_id": r["source_id"], "target_id": r["target_id"],
             "type": r["type"],
             "metadata": json.loads(r["metadata_json"]) if r["metadata_json"] else {}}
            for r in rows]


# ── 测试类（Node.js 必需）─────────────────────────────────────


@pytest.mark.skipif(
    shutil.which("node") is None,
    reason="Node.js not installed",
)
class TestJsTsFullPipeline:
    """Phase 6.3 Step 3 — JS/TS 全链路集成测试"""

    # ── 1. Index 阶段 ──

    def test_index_js_ts_files_detected(self, tmp_path: Path):
        """JS/TS 文件被正确识别语言并索引"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        stats = index.stats()
        # 应该有 JS/TS 文件
        langs = stats.get("languages", [])
        lang_names = [l["language"] for l in langs]
        assert "typescript" in lang_names or "javascript" in lang_names

        # 验证 code:module artifacts 标记了正确的语言
        conn = index.store.connect()
        rows = conn.execute(
            "SELECT name, metadata_json FROM artifacts WHERE type = 'code:module' AND file_path LIKE '%.ts'"
        ).fetchall()
        for row in rows:
            meta = json.loads(row["metadata_json"]) if row["metadata_json"] else {}
            assert meta.get("language") in ("typescript", "javascript")

        index.close()

    def test_index_creates_code_artifacts(self, tmp_path: Path):
        """索引后创建 code:* artifacts（function, class, import 等）"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        types = _all_artifact_types(index)
        # 应该有 code:* 类型的 artifact
        code_types = [t for t in types if t.startswith("code:")]
        assert len(code_types) >= 3  # module, function, import, class, etc.

        index.close()

    def test_js_ts_functions_extracted(self, tmp_path: Path):
        """function 和箭头函数被提取为 artifact"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        functions = _artifacts_by_type(index, "code:function")
        func_names = [f["name"] for f in functions]
        # 应包含普通函数和箭头函数
        assert "helper" in func_names
        assert "validateUser" in func_names
        assert "format" in func_names
        assert "truncate" in func_names
        assert "createApp" in func_names

        index.close()

    def test_js_ts_classes_extracted(self, tmp_path: Path):
        """class 被提取为 artifact"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        classes = _artifacts_by_type(index, "code:class")
        class_names = [c["name"] for c in classes]
        assert "App" in class_names

        # 验证 metadata 包含 signature
        app_class = [c for c in classes if c["name"] == "App"][0]
        assert "class App" in app_class["metadata"].get("signature", "")

        index.close()

    def test_js_ts_interfaces_and_types_extracted(self, tmp_path: Path):
        """interface 和 type alias 被提取为 artifact"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        interfaces = _artifacts_by_type(index, "code:interface")
        interface_names = [i["name"] for i in interfaces]
        assert "Config" in interface_names
        assert "User" in interface_names

        type_aliases = _artifacts_by_type(index, "code:type_alias")
        type_names = [t["name"] for t in type_aliases]
        assert "Status" in type_names

        index.close()

    # ── 2. Import Relations ──

    def test_js_ts_import_relations_created(self, tmp_path: Path):
        """JS/TS 模块间 import relations 正确创建"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        stats = index.stats()
        # 应该有 import relations
        assert stats["relations"] > 0

        # src/index.ts 应该 import 了多个模块
        index_relations = _relations_by_source(index, "src/index.ts")
        assert len(index_relations) >= 3  # helper, format, types, models, api

        # 检查 relation 的 metadata
        target_modules = []
        for rel in index_relations:
            meta = rel["metadata"]
            target_modules.append(meta.get("module", ""))

        # 应该包含内部模块（相对路径）
        assert any(m.startswith("./") for m in target_modules)

        index.close()

    def test_js_ts_internal_imports_resolved(self, tmp_path: Path):
        """相对 import 被解析为 project 内路径"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        # src/index.ts imports from ./utils/helper
        relations = _relations_by_source(index, "src/index.ts")
        target_ids = [r["target_id"] for r in relations]

        # 验证有 module: 类型的 target
        module_targets = [t for t in target_ids if t.startswith("module:")]
        assert len(module_targets) > 0

        # ./utils/helper 应该解析为 module:src/utils/helper
        assert any("helper" in t for t in module_targets)

        index.close()

    def test_js_ts_external_deps_tracked(self, tmp_path: Path):
        """外部 npm 依赖被识别为 external_module"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        # 检查 external_module artifacts
        externals = _artifacts_by_type(index, "external_module")
        external_names = [e["name"] for e in externals]

        # src/api.ts imports axios
        assert "axios" in external_names

        # lib/validator.js imports nanoid (external npm package)
        assert "nanoid" in external_names

        # 验证 external 类型的 relation
        conn = index.store.connect()
        rows = conn.execute(
            "SELECT target_id, metadata_json FROM relations WHERE type = 'imports'"
        ).fetchall()
        external_relations = []
        for r in rows:
            meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
            if meta.get("external"):
                external_relations.append(r["target_id"])

        assert len(external_relations) > 0
        assert any("axios" in t for t in external_relations)

        index.close()

    def test_js_file_import_relations_created(self, tmp_path: Path):
        """JavaScript 文件的 import relations 正确创建"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        # lib/validator.js 使用 ES import
        relations = _relations_by_source(index, "lib/validator.js")
        assert len(relations) > 0
        # 应该包含 nanoid 的 external import
        target_ids = [r["target_id"] for r in relations]
        assert any("nanoid" in t for t in target_ids)

        index.close()

    # ── 3. Search ──

    def test_search_finds_js_ts_artifacts(self, tmp_path: Path):
        """smartdev search 能搜索 JS/TS artifact"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        # 搜索函数名
        results = index.search("helper")
        assert results["total_artifacts"] >= 1
        artifact_names = [a["name"] for a in results["artifacts"]]
        assert "helper" in artifact_names

        # 搜索 class 名
        results = index.search("App")
        assert results["total_artifacts"] >= 1
        artifact_types = [a["type"] for a in results["artifacts"]]
        assert "code:class" in artifact_types

        # 搜索 external import
        results = index.search("axios")
        assert results["total_artifacts"] >= 1

        index.close()

    def test_search_finds_js_ts_files(self, tmp_path: Path):
        """smartdev search 能搜索 JS/TS 文件"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        results = index.search("types.ts")
        assert results["total_files"] >= 1
        paths = [f["path"] for f in results["files"]]
        assert any("types.ts" in p for p in paths)

        index.close()

    # ── 4. Project Map ──

    def test_project_map_includes_js_ts_modules(self, tmp_path: Path):
        """project.map 包含 JS/TS 模块"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        project_map = generate_project_map(index.store, "js-ts-fixture")
        index.close()

        # 应该有 modules
        assert len(project_map.modules) > 0

        # 验证 module 路径包含 JS/TS 文件
        module_paths = [m.file_path for m in project_map.modules]
        assert any("src/index.ts" in p for p in module_paths)
        assert any("src/models.ts" in p for p in module_paths)

        # 摘要应包含外部分类
        assert project_map.summary["modules"] > 0

    def test_project_map_has_external_deps(self, tmp_path: Path):
        """project.map 记录外部依赖"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        project_map = generate_project_map(index.store, "js-ts-fixture")
        index.close()

        # 应该有外部依赖（axios）
        ext_names = [e.name for e in project_map.external_dependencies]
        assert "axios" in ext_names

    def test_project_map_json_export(self, tmp_path: Path):
        """project.map 能导出 JSON"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        project_map = generate_project_map(index.store, "js-ts-fixture")
        index.close()

        json_str = project_map.to_json()
        data = json.loads(json_str)

        assert data["project"]["name"] == "js-ts-fixture"
        assert isinstance(data["modules"], list)
        assert isinstance(data["external_dependencies"], list)

    # ── 5. Graph Validate ──

    def test_graph_validate_clean(self, tmp_path: Path):
        """graph.validate 对 JS/TS 项目输出健康报告"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        result = validate_graph(index.store)
        index.close()

        # 应该没有 orphan source errors
        assert result.stats["orphan_sources"] == 0

        # 应该有关系统计
        assert result.stats["relations"] > 0

        # 应该有 external 统计
        assert result.stats["external"] > 0

        # 应该是健康的
        assert result.is_healthy

    def test_graph_validate_markdown_report(self, tmp_path: Path):
        """graph.validate 能生成 Markdown 报告"""
        project = _build_js_ts_fixture(tmp_path)
        index = ProjectIndex(project)
        index.index()

        result = validate_graph(index.store)
        index.close()

        md = result.to_markdown()
        assert "# Graph Validation Report" in md
        assert "## Summary" in md
        assert "Artifacts:" in md
        assert "Relations:" in md

    # ── 6. End-to-End ──

    def test_full_pipeline_end_to_end(self, tmp_path: Path):
        """全链路：index → search → project.map → graph.validate 串联验证"""
        project = _build_js_ts_fixture(tmp_path)

        # Step 1: Index
        index = ProjectIndex(project)
        result = index.index()
        assert result["files"] >= 7  # package.json + 7 source files
        assert result["relations"] > 0
        assert result["errors"] == 0

        # Step 2: Stats
        stats = index.stats()
        assert stats["artifacts"] > 10  # functions + classes + interfaces + imports + modules
        assert stats["relations"] > 0

        # Step 3: Search
        search_result = index.search("User")
        assert search_result["total_artifacts"] >= 2  # interface User + UserProfile

        # Step 4: Project Map
        project_map = generate_project_map(index.store, "e2e-test")
        assert project_map.summary["modules"] > 0
        assert project_map.summary["external_deps"] > 0

        # Step 5: Graph Validate
        validation = validate_graph(index.store)

        # 验证报告
        validation_md = validation.to_markdown()
        assert "Graph Validation Report" in validation_md
        assert "external" in validation.stats
        assert validation.stats["external"] > 0

        # 验证数据完整性
        assert validation.is_healthy

        # 验证 project map JSON 可序列化
        json_str = project_map.to_json()
        data = json.loads(json_str)
        assert data["project"]["name"] == "e2e-test"

        index.close()

    # ── 7. Safety ──

    def test_does_not_modify_source(self, tmp_path: Path):
        """索引和校验不修改被分析项目的源码"""
        project = _build_js_ts_fixture(tmp_path)

        # 记录原始内容
        original_contents = {}
        for f in project.rglob("*"):
            if f.is_file() and f.suffix in (".ts", ".js", ".json"):
                original_contents[str(f.relative_to(project))] = f.read_text()

        index = ProjectIndex(project)
        index.index()
        validate_graph(index.store)
        index.close()

        # 源码不变
        for rel, original in original_contents.items():
            current = (project / rel).read_text()
            assert current == original, f"File modified: {rel}"
