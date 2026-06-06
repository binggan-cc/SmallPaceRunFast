#!/usr/bin/env python3
"""
Phase 6.3 Step 4 — gateway 真实项目验证脚本 v2

收集 13 项指标 + 内部路径解析 / external 归类 / artifact 异常分析。
只读，不修改任何文件。
"""

import json
import time
from pathlib import Path

PROJECT_PATH = Path("/Volumes/elements/repos/ai-gateway/gateway")

from smartdev.context.project_index import ProjectIndex
from smartdev.context.project_map import generate_project_map
from smartdev.context.graph_validator import validate_graph
from smartdev.context.impact_analyzer import ImpactAnalyzer

t0 = time.time()

# ── 1. 加载索引 ──
index = ProjectIndex(PROJECT_PATH)
store = index.store
conn = store.connect()

# ── 2. 基本统计 ──
total_files = store.count_files()
total_artifacts = store.count_artifacts()
total_relations = store.count_relations()

# 按语言统计文件
lang_rows = conn.execute(
    "SELECT language, COUNT(*) as cnt FROM files GROUP BY language ORDER BY cnt DESC"
).fetchall()
lang_stats = {r["language"]: r["cnt"] for r in lang_rows}
js_ts_files = lang_stats.get("typescript", 0) + lang_stats.get("javascript", 0) + lang_stats.get("tsx", 0) + lang_stats.get("jsx", 0)

# 按类型统计 artifact
type_rows = conn.execute(
    "SELECT type, COUNT(*) as cnt FROM artifacts GROUP BY type ORDER BY cnt DESC"
).fetchall()
artifact_type_stats = {r["type"]: r["cnt"] for r in type_rows}

# ── 2a. Artifact 异常分析 — 检查 interface/type_alias 分布 ──
print("## Artifact 异常分析（interface/type_alias 文件分布）")
print()

# 每个 TS 文件的 interface 数量
iface_per_file = conn.execute("""
    SELECT file_path, COUNT(*) as cnt
    FROM artifacts
    WHERE type = 'code:interface'
    GROUP BY file_path
    ORDER BY cnt DESC
""").fetchall()
print("Interface 每文件分布:")
for r in iface_per_file:
    print(f"  {r['file_path']}: {r['cnt']}")

print()
# type_alias 分布
talias_per_file = conn.execute("""
    SELECT file_path, COUNT(*) as cnt
    FROM artifacts
    WHERE type = 'code:type_alias'
    GROUP BY file_path
    ORDER BY cnt DESC
""").fetchall()
print("Type Alias 每文件分布:")
for r in talias_per_file:
    print(f"  {r['file_path']}: {r['cnt']}")

print()
# class 分布
class_per_file = conn.execute("""
    SELECT file_path, COUNT(*) as cnt
    FROM artifacts
    WHERE type = 'code:class'
    GROUP BY file_path
    ORDER BY cnt DESC
""").fetchall()
print("Class 每文件分布:")
for r in class_per_file:
    print(f"  {r['file_path']}: {r['cnt']}")

print()
# 抽查：查看 interfaces 的 name（取前 20 个）
print("Sample interfaces (前 20):")
sample_ifaces = conn.execute(
    "SELECT name, file_path FROM artifacts WHERE type = 'code:interface' LIMIT 20"
).fetchall()
for r in sample_ifaces:
    print(f"  [{r['file_path']}] {r['name']}")

print()
# 检查 de-duplication: 同文件同 name 是否有重复？
dup_check = conn.execute("""
    SELECT file_path, name, COUNT(*) as cnt
    FROM artifacts
    WHERE type = 'code:interface'
    GROUP BY file_path, name
    HAVING cnt > 1
    ORDER BY cnt DESC
    LIMIT 20
""").fetchall()
if dup_check:
    print("⚠️ Interface duplicates (同文件同名):")
    for r in dup_check:
        print(f"  [{r['file_path']}] {r['name']} x{r['cnt']}")
else:
    print("✅ No duplicate interfaces (同文件同名)")

# 看看 name 的特征: 是否有很多单字母/短名称？
short_ifaces = conn.execute("""
    SELECT name, file_path, COUNT(*) as cnt
    FROM artifacts
    WHERE type = 'code:interface' AND length(name) <= 3
    GROUP BY name, file_path
    ORDER BY cnt DESC
    LIMIT 20
""").fetchall()
if short_ifaces:
    print(f"\nShort name interfaces (<4 chars): {sum(r['cnt'] for r in short_ifaces)} occurrences")
    for r in short_ifaces[:10]:
        print(f"  [{r['file_path']}] '{r['name']}' x{r['cnt']}")

print()
print("=" * 70)

# ── 3. JS/TS import relations 详细分析 ──
js_ts_relations = conn.execute(
    """SELECT r.source_id, r.target_id, r.metadata_json
       FROM relations r
       WHERE r.type = 'imports'
         AND r.source_id LIKE 'code:module:%'"""
).fetchall()

js_ts_import_count = 0
internal_count = 0
external_count = 0
unresolved_count = 0
external_deps: dict[str, list[str]] = {}
internal_targets: dict[str, list[str]] = {}
unresolved_targets: dict[str, list[str]] = {}

for rel in js_ts_relations:
    meta = json.loads(rel["metadata_json"]) if rel["metadata_json"] else {}
    source_id = rel["source_id"]
    target_id = rel["target_id"]
    module_name = meta.get("module", target_id)

    source_module = conn.execute(
        "SELECT metadata_json FROM artifacts WHERE id = ?", (source_id,)
    ).fetchone()
    source_lang = "unknown"
    if source_module:
        smeta = json.loads(source_module["metadata_json"]) if source_module["metadata_json"] else {}
        source_lang = smeta.get("language", "unknown")

    if source_lang in ("typescript", "javascript"):
        js_ts_import_count += 1
        if meta.get("external"):
            external_count += 1
            if module_name not in external_deps:
                external_deps[module_name] = []
            external_deps[module_name].append(source_id)
        elif target_id.startswith("unresolved:"):
            unresolved_count += 1
            if module_name not in unresolved_targets:
                unresolved_targets[module_name] = []
            unresolved_targets[module_name].append(source_id)
        else:
            internal_count += 1
            if module_name not in internal_targets:
                internal_targets[module_name] = []
            internal_targets[module_name].append(source_id)

# 检查 module: target 与 artifact 对应关系
module_targets = set()
for rel in js_ts_relations:
    tid = rel["target_id"]
    if tid.startswith("module:"):
        module_targets.add(tid)

orphan_module_targets = []
resolved_module_targets = []
for mt in module_targets:
    exists = conn.execute("SELECT COUNT(*) FROM artifacts WHERE id = ?", (mt,)).fetchone()[0]
    if exists == 0:
        orphan_module_targets.append(mt)
    else:
        resolved_module_targets.append(mt)

# ── 4. Extractor 统计 ──
node_bridge_hits = 0
python_ast_hits = 0
lang_extractor_rows = conn.execute(
    "SELECT metadata_json FROM artifacts WHERE type = 'code:module'"
).fetchall()
for r in lang_extractor_rows:
    meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
    lang = meta.get("language", "unknown")
    if lang in ("typescript", "javascript"):
        node_bridge_hits += 1
    elif lang == "python":
        python_ast_hits += 1

# 检查 code:import artifacts 的 metadata（看 confidence 来推断 extractor）
import_meta_rows = conn.execute(
    "SELECT file_path, name, metadata_json FROM artifacts WHERE type = 'code:import'"
).fetchall()
high_conf_imports = 0
low_conf_imports = 0
for r in import_meta_rows:
    meta = json.loads(r["metadata_json"]) if r["metadata_json"] else {}
    conf = meta.get("confidence", 0)
    if conf >= 0.9:
        high_conf_imports += 1
    else:
        low_conf_imports += 1

# ── 5. Graph Validate ──
validation = validate_graph(store)

# ── 6. Project Map ──
project_map = generate_project_map(store, "gateway")

# ── 7. Impact smoke test ──
analyzer = ImpactAnalyzer(store)
impact_result_src_index = analyzer.analyze("src/index.ts", max_depth=2)
impact_result_types = analyzer.analyze("src/types.ts", max_depth=2)

# ── 8. Search smoke ──
search_hono = index.search("Hono", limit=3)
search_app = index.search("App", limit=3)
search_gateway = index.search("gateway", limit=5)

# ── 9. 关闭连接 ──
# 注意：impact_analyzer 可能创建了自己的连接，安全起见先关闭 store
store.close()
elapsed = time.time() - t0

# ══════════════════════════════════════════════════════════════
# 输出报告
# ══════════════════════════════════════════════════════════════

print("=" * 70)
print("Phase 6.3 Step 4 — gateway 真实项目验证结果")
print("=" * 70)
print(f"项目: {PROJECT_PATH}")
print(f"耗时: {elapsed:.1f}s")
print()

print("## 项目规模")
print(f"- files: {total_files}")
print(f"- JS/TS/TSX files: {js_ts_files}")
print(f"- artifacts: {total_artifacts}")
print(f"- relations: {total_relations}")
print(f"- JS/TS import relations: {js_ts_import_count}")
print()

print("## 文件语言分布")
for lang, cnt in sorted(lang_stats.items(), key=lambda x: -x[1]):
    print(f"  {lang}: {cnt}")
print()

print("## Artifact 类型分布")
for atype, cnt in sorted(artifact_type_stats.items(), key=lambda x: -x[1]):
    print(f"  {atype}: {cnt}")
print()

print("## 解析情况")
print(f"- NodeBridgeExtractor 命中 (module artifacts): {node_bridge_hits}")
print(f"- PythonAstExtractor 命中 (module artifacts): {python_ast_hits}")
print(f"- 高置信度 imports (≥0.9): {high_conf_imports}")
print(f"- 低置信度 imports (<0.9): {low_conf_imports}")
print(f"- internal imports: {internal_count}")
print(f"- external imports: {external_count}")
print(f"- unresolved imports: {unresolved_count}")
print()

print("## 图谱健康")
print(f"- errors: {len(validation.errors)}")
print(f"- warnings: {len(validation.warnings)}")
print(f"- info: {len(validation.info)}")
for e in validation.errors:
    print(f"  [ERROR] [{e.category}] {e.message}")
for w in validation.warnings:
    print(f"  [WARN] [{w.category}] {w.message}")
for i in validation.info:
    print(f"  [INFO] [{i.category}] {i.message}")
print()

print("## 内部 import 路径解析")
print(f"- resolved module: targets 有对应 artifact: {len(resolved_module_targets)}")
print(f"- orphan module: targets 无对应 artifact: {len(orphan_module_targets)}")
if orphan_module_targets:
    for mt in orphan_module_targets[:10]:
        print(f"  - {mt}")
print()
print("  详情:")
for target, sources in sorted(internal_targets.items(), key=lambda x: -len(x[1]))[:15]:
    print(f"  {target} ← {len(sources)} files")
    for s in sources[:2]:
        print(f"    - {s}")
print()

print("## Top external deps")
for dep, sources in sorted(external_deps.items(), key=lambda x: -len(x[1])):
    print(f"  {dep} ← {len(sources)} files")
print()

print("## Unresolved imports")
if unresolved_targets:
    for target, sources in sorted(unresolved_targets.items(), key=lambda x: -len(x[1])):
        print(f"  {target} ← {len(sources)} files")
else:
    print("  (none)")
print()

print("## Top hotspots")
for h in project_map.hotspots[:10]:
    print(f"  {h.target} ({h.dependent_count} dependents, risk={h.risk})")
print()

print("## Impact smoke test")
print(f"- impact(src/index.ts):")
print(f"  {impact_result_src_index.summary[:300]}")
print(f"- impact(src/types.ts):")
print(f"  {impact_result_types.summary[:300]}")
print()

print("## Search smoke")
print(f"- search('Hono'): {search_hono['total_artifacts']} artifacts, {search_hono['total_files']} files")
print(f"- search('App'): {search_app['total_artifacts']} artifacts, {search_app['total_files']} files")
print(f"- search('gateway'): {search_gateway['total_artifacts']} artifacts, {search_gateway['total_files']} files")
print()

# ── 问题分级 ──
print("## 发现问题")
p0_issues = []
p1_issues = []
p2_issues = []

# P0
if not validation.is_healthy:
    p0_issues.append("graph.validate 有 errors")
if validation.stats.get("orphan_sources", 0) > 0:
    p0_issues.append(f"orphan_sources: {validation.stats['orphan_sources']}")

# P1: 内部路径对齐
if orphan_module_targets:
    p1_issues.append(f"module: target 无对应 artifact: {len(orphan_module_targets)} 个（path normalization 问题）")

# P1: artifact 膨胀
total_code_artifacts = artifact_type_stats.get("code:interface", 0) + artifact_type_stats.get("code:type_alias", 0) + artifact_type_stats.get("code:class", 0)
if total_code_artifacts / max(js_ts_files, 1) > 20:
    p1_issues.append(f"artifact 膨胀: {total_code_artifacts} code artifacts / {js_ts_files} TS files = {total_code_artifacts / js_ts_files:.0f}/file（异常高）")

# P2: export default naming, tsconfig alias
if unresolved_count > 0:
    p2_issues.append(f"unresolved imports: {unresolved_count} 个（检查是否 tsconfig alias）")

for issue in p0_issues:
    print(f"- P0: {issue}")
for issue in p1_issues:
    print(f"- P1: {issue}")
for issue in p2_issues:
    print(f"- P2: {issue}")
if not p0_issues and not p1_issues and not p2_issues:
    print("  (no issues detected)")
print()

print("## 结论")
if p0_issues:
    print("- ❌ 需先修 P0 问题再继续")
elif p1_issues:
    print("- ⚠️ 有 P1 问题，建议先修 artifact 膨胀 + path normalization 再进 tsconfig alias")
else:
    print("- ✅ JS/TS 链路基本可用，可以进入 tsconfig paths alias 解析")
print()
print("=" * 70)
