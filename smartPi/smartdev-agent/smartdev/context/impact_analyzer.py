"""
SmartDev Agent 影响分析器

设计原理：
─────────
第一版只做规则型影响分析，不做完整调用图。
通过 relations 表 + 文件路径分析来推断影响范围。

借鉴来源：
- CodeGraph 的 getImpactRadius()：BFS 遍历 incoming edges
- 但简化为规则型：同目录文件、import 关系、artifact 引用

分析策略：
1. 直接引用：relations 表中 source_id 或 target_id 匹配
2. 间接影响：同目录文件、同类型 artifact、文件名模式匹配
3. 风险等级：基于影响范围计算（单文件=R1，多文件+API=R2，数据模型=R3）
4. 验证项：根据影响的 artifact 类型自动生成

对应文档：
- next-phase-code-intelligence.md §8.3（code.impact 设计）
- next-phase-code-intelligence.md §9.4（Risk 计算）
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from smartdev.context.index_store import IndexStore


@dataclass
class ImpactResult:
    """影响分析结果"""
    target: str
    direct_references: list[str] = field(default_factory=list)
    indirect_impacts: list[str] = field(default_factory=list)
    risk_level: str = "R1"
    verification_items: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass
class ImportDependent:
    """Import 依赖方"""
    source_id: str       # 发起 import 的 module artifact id
    source_file: str     # 发起 import 的文件路径
    target_id: str       # 被 import 的 module artifact id
    import_kind: str     # "from_import" / "import"
    module: str          # 被 import 的模块名
    names: list[str] = field(default_factory=list)  # import 的具体符号
    aliases: dict = field(default_factory=dict)
    line: int = 0
    confidence: float = 1.0
    external: bool = False


@dataclass
class ImportImpactResult:
    """Import 影响分析结果"""
    query: str
    resolved_target: str = ""      # 解析后的 target artifact id
    relation_scope: str = "module" # 关系粒度（当前只有 module）
    direct_dependents: list[ImportDependent] = field(default_factory=list)
    affected_files: list[str] = field(default_factory=list)
    risk_level: str = "R1"
    validation_suggestions: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    summary: str = ""


# ── 风险等级计算 ──────────────────────────────────────────

def _compute_risk_level(
    direct_count: int,
    indirect_count: int,
    has_api: bool,
    has_model: bool,
    has_config: bool,
) -> str:
    """基于影响范围计算风险等级

    规则：
    - R0: 无影响或只读文档
    - R1: 单文件，无跨模块关系
    - R2: 多文件，有 API / UI / 数据影响
    - R3: 数据模型、权限、schema、核心协议影响
    """
    total = direct_count + indirect_count

    # R3: 涉及数据模型
    if has_model and total > 2:
        return "R3"

    # R2: 涉及 API 或多文件影响
    if has_api and total > 1:
        return "R2"
    if total > 3:
        return "R2"

    # R1: 有影响但范围有限
    if total > 0:
        return "R1"

    return "R0"


# ── 验证项生成 ────────────────────────────────────────────

def _generate_verification_items(
    direct_refs: list[str],
    indirect_impacts: list[str],
    artifact_types: set[str],
) -> list[str]:
    """根据影响范围自动生成验证项"""
    items = []

    if "api_endpoint" in artifact_types:
        items.append("API 接口测试")
    if "design_token" in artifact_types:
        items.append("视觉一致性检查")
    if "manifest" in artifact_types:
        items.append("扩展加载测试")
    if "model" in artifact_types:
        items.append("数据模型兼容性测试")
    if "server_file" in artifact_types:
        items.append("服务启动测试")
    if "extension_file" in artifact_types:
        items.append("扩展功能测试")

    # 通用验证项
    total = len(direct_refs) + len(indirect_impacts)
    if total > 3:
        items.append("回归测试")
    if total > 5:
        items.append("性能测试")

    return items


# ── 影响分析器 ────────────────────────────────────────────

class ImpactAnalyzer:
    """变更影响分析器

    分析修改某个文件或工件可能波及的范围。

    使用示例：
        analyzer = ImpactAnalyzer(index_store)
        result = analyzer.analyze("tokens.css")
        print(result.risk_level)
        print(result.direct_references)
    """

    def __init__(self, store: IndexStore) -> None:
        self.store = store

    def analyze(self, target: str, max_depth: int = 3) -> ImpactResult:
        """分析目标的影响范围

        参数：
            target: 文件路径或工件 ID/名称
            max_depth: 最大递归深度（BFS 层数）

        返回：
            ImpactResult 包含直接引用、间接影响、风险等级、验证项
        """
        direct_refs: list[str] = []
        indirect_impacts: list[str] = []
        artifact_types: set[str] = set()
        has_api = False
        has_model = False
        has_config = False

        # 1. 查找直接关系
        relations = self._find_relations(target)
        for rel in relations:
            other_id = rel["other_id"]
            ref_desc = f"{rel['type']}: {other_id}"
            direct_refs.append(ref_desc)

            # 追踪 artifact 类型
            artifact = self.store.get_artifact(other_id)
            if artifact:
                artifact_types.add(artifact.type)
                if artifact.type == "api_endpoint":
                    has_api = True
                elif artifact.type == "model":
                    has_model = True
                elif artifact.type == "config":
                    has_config = True

        # 2. 查找同目录文件（间接影响）
        same_dir_impacts = self._find_same_dir_files(target)
        indirect_impacts.extend(same_dir_impacts)

        # 3. 查找引用相同 artifact 的文件
        related_files = self._find_related_files(target)
        indirect_impacts.extend(related_files)

        # 4. 计算风险等级
        risk_level = _compute_risk_level(
            len(direct_refs), len(indirect_impacts),
            has_api, has_model, has_config,
        )

        # 5. 生成验证项
        verification_items = _generate_verification_items(
            direct_refs, indirect_impacts, artifact_types,
        )

        # 6. 生成摘要
        summary = self._build_summary(
            target, direct_refs, indirect_impacts,
            risk_level, verification_items,
        )

        return ImpactResult(
            target=target,
            direct_references=direct_refs,
            indirect_impacts=indirect_impacts,
            risk_level=risk_level,
            verification_items=verification_items,
            summary=summary,
        )

    # ── Import 关系分析（Phase 6.2 Step 3）─────────────────

    def analyze_import_impact(self, query: str) -> ImportImpactResult:
        """基于 imports relation 分析影响范围

        通过 relations 表做 reverse lookup，找到所有 import 了目标模块的文件。

        参数：
            query: 用户输入（模块名、文件路径、符号名、external placeholder）

        返回：
            ImportImpactResult

        target resolve 策略：
            1. 直接匹配 module:xxx 或 code:module:xxx artifact
            2. 文件路径 → code:module:{path} artifact
            3. 符号名 → 查找 code:class/function artifact → 获取所在 module → 再查
            4. external:python:xxx → 直接匹配
        """
        limitations = [
            "relation_scope = module（模块级关系，非符号级精确引用）",
        ]

        # 1. 解析 target
        resolved_targets = self._resolve_target(query)

        if not resolved_targets:
            return ImportImpactResult(
                query=query,
                limitations=limitations,
                summary=f"未找到目标：'{query}'\n\n建议：先运行 smartdev index 建立索引，或尝试搜索 smartdev search {query}",
            )

        # 2. 查询 incoming imports
        direct_dependents: list[ImportDependent] = []
        affected_files: set[str] = set()

        for target_id in resolved_targets:
            incoming = self.store.get_relations(target_id, direction="incoming")
            for rel in incoming:
                if rel["type"] != "imports":
                    continue

                meta = json.loads(rel["metadata_json"]) if rel["metadata_json"] else {}
                dep = ImportDependent(
                    source_id=rel["source_id"],
                    source_file=self._artifact_file_path(rel["source_id"]),
                    target_id=target_id,
                    import_kind=meta.get("import_kind", ""),
                    module=meta.get("module", ""),
                    names=meta.get("names", []),
                    aliases=meta.get("aliases", {}),
                    line=meta.get("line", 0),
                    confidence=meta.get("confidence", 1.0),
                    external=meta.get("external", False),
                )
                direct_dependents.append(dep)
                if dep.source_file:
                    affected_files.add(dep.source_file)

        # 3. 计算风险等级
        risk_level = _compute_risk_level(
            len(direct_dependents), 0,
            has_api=False, has_model=False, has_config=False,
        )

        # 4. 生成验证建议
        validation = self._generate_validation_suggestions(
            direct_dependents, list(affected_files),
        )

        # 5. 生成摘要
        summary = self._build_import_impact_summary(
            query, resolved_targets, direct_dependents,
            list(affected_files), risk_level, validation, limitations,
        )

        return ImportImpactResult(
            query=query,
            resolved_target=resolved_targets[0] if resolved_targets else "",
            direct_dependents=direct_dependents,
            affected_files=sorted(affected_files),
            risk_level=risk_level,
            validation_suggestions=validation,
            limitations=limitations,
            summary=summary,
        )

    def _resolve_target(self, query: str) -> list[str]:
        """解析用户输入为 target artifact ID 列表"""
        targets: list[str] = []

        # 1. 直接匹配 external placeholder
        if query.startswith("external:"):
            art = self.store.get_artifact(query)
            if art:
                return [query]

        # 2. 直接匹配 module:xxx
        art = self.store.get_artifact(f"module:{query}")
        if art:
            targets.append(art.id)

        # 3. 匹配 code:module:xxx（文件路径格式）
        if "/" in query or query.endswith(".py"):
            module_path = query.replace("/", ".")
            if module_path.endswith(".py"):
                module_path = module_path[:-3]
            art = self.store.get_artifact(f"code:module:{query}")
            if art:
                targets.append(art.id)
            # 也尝试 module: 格式
            art2 = self.store.get_artifact(f"module:{module_path}")
            if art2 and art2.id not in targets:
                targets.append(art2.id)

        # 4. 符号名 → 查找 class/function artifact → 获取所在 module
        if not targets:
            symbols = self.store.search_artifacts(query, limit=5)
            for sym in symbols:
                if sym.type.startswith("code:class") or sym.type.startswith("code:function"):
                    file_path = sym.file_path
                    if file_path:
                        # 从 file_path 推导 module 名
                        module_name = file_path.replace("/", ".").replace("\\", ".")
                        if module_name.endswith(".py"):
                            module_name = module_name[:-3]

                        # 两种格式都尝试（relations 表用 module:，artifact 用 code:module:）
                        code_module_id = f"code:module:{file_path}"
                        named_module_id = f"module:{module_name}"
                        for mid in [code_module_id, named_module_id]:
                            art = self.store.get_artifact(mid)
                            if art and art.id not in targets:
                                targets.append(art.id)

                        # 如果两种 artifact 都不存在，也尝试 module: 格式
                        # （relations 可能引用了还未索引到的 artifact）
                        module_id = f"module:{module_name}"
                        if module_id not in targets:
                            # 检查 relations 表是否有引用
                            rels = self.store.get_relations(module_id, direction="incoming")
                            if rels:
                                targets.append(module_id)

        return targets

    def _artifact_file_path(self, artifact_id: str) -> str:
        """获取 artifact 的文件路径"""
        art = self.store.get_artifact(artifact_id)
        if art:
            return art.file_path
        # 从 code:module:xxx 格式提取路径
        if artifact_id.startswith("code:module:"):
            return artifact_id[len("code:module:"):]
        return ""

    def _generate_validation_suggestions(
        self,
        dependents: list[ImportDependent],
        affected_files: list[str],
    ) -> list[str]:
        """根据依赖方生成验证建议"""
        suggestions: list[str] = []

        # 查找测试文件
        test_files = [
            f for f in affected_files
            if "test" in f or f.startswith("tests/")
        ]
        if test_files:
            suggestions.append(f"运行相关测试：{', '.join(test_files[:3])}")

        # 通用建议
        if len(affected_files) > 3:
            suggestions.append("运行全量回归测试：python -m pytest tests/ -q")

        # 按 import_kind 分类建议
        from_imports = [d for d in dependents if d.import_kind == "from_import"]
        if from_imports:
            symbols = set()
            for d in from_imports:
                symbols.update(d.names)
            if symbols:
                suggestions.append(f"检查 import 的符号是否仍然可用：{', '.join(sorted(symbols)[:5])}")

        if not suggestions:
            suggestions.append("验证受影响文件的功能正确性")

        return suggestions

    def _build_import_impact_summary(
        self,
        query: str,
        resolved_targets: list[str],
        dependents: list[ImportDependent],
        affected_files: list[str],
        risk_level: str,
        validation: list[str],
        limitations: list[str],
    ) -> str:
        """构建 import 影响分析摘要"""
        lines = [f"Import 影响分析：{query}", ""]

        # resolved target
        if resolved_targets:
            lines.append(f"解析目标：{resolved_targets[0]}")
        lines.append(f"关系粒度：module（模块级）")
        lines.append("")

        # direct dependents
        if dependents:
            lines.append(f"直接依赖方（{len(dependents)} 个文件 import 了此模块）：")
            for dep in dependents[:15]:
                file_info = dep.source_file or dep.source_id
                import_detail = f"import {dep.module}"
                if dep.names:
                    import_detail = f"from {dep.module} import {', '.join(dep.names[:3])}"
                lines.append(f"  - {file_info}  ({import_detail})")
        else:
            lines.append("直接依赖方：无")

        lines.append("")

        # affected files
        if affected_files:
            lines.append(f"受影响文件（{len(affected_files)} 个）：")
            for f in affected_files[:10]:
                lines.append(f"  - {f}")
        else:
            lines.append("受影响文件：无")

        lines.append("")
        lines.append(f"风险等级：{risk_level}")

        if validation:
            lines.append("")
            lines.append("验证建议：")
            for v in validation:
                lines.append(f"  - {v}")

        if limitations:
            lines.append("")
            lines.append("当前限制：")
            for lim in limitations:
                lines.append(f"  - {lim}")

        return "\n".join(lines)

    def _find_relations(self, target: str) -> list[dict]:
        """查找与目标相关的关系"""
        results = []

        # 先按 artifact 名称搜索
        artifacts = self.store.search_artifacts(target, limit=10)
        for artifact in artifacts:
            # 查找 outgoing 关系
            outgoing = self.store.get_relations(artifact.id, direction="outgoing")
            for rel in outgoing:
                results.append({
                    "type": rel["type"],
                    "source": artifact.id,
                    "target": rel["target_id"],
                    "other_id": rel["target_id"],
                })

            # 查找 incoming 关系
            incoming = self.store.get_relations(artifact.id, direction="incoming")
            for rel in incoming:
                results.append({
                    "type": rel["type"],
                    "source": rel["source_id"],
                    "target": artifact.id,
                    "other_id": rel["source_id"],
                })

        # 也按文件路径搜索
        file_artifacts = self.store.list_artifacts(file_path=target)
        for artifact in file_artifacts:
            outgoing = self.store.get_relations(artifact.id, direction="outgoing")
            for rel in outgoing:
                if not any(r["other_id"] == rel["target_id"] for r in results):
                    results.append({
                        "type": rel["type"],
                        "source": artifact.id,
                        "target": rel["target_id"],
                        "other_id": rel["target_id"],
                    })

        return results

    def _find_same_dir_files(self, target: str) -> list[str]:
        """查找同目录文件"""
        results = []
        target_path = Path(target)
        target_dir = target_path.parent

        # 查找同目录下的所有文件
        all_files = self.store.list_files()
        for f in all_files:
            if f.path == target:
                continue
            if Path(f.path).parent == target_dir:
                results.append(f"同目录: {f.path}")

        return results[:5]  # 限制数量

    def _find_related_files(self, target: str) -> list[str]:
        """查找引用相同 artifact 的文件"""
        results = []
        target_stem = Path(target).stem

        # 查找文件名相似的 artifact
        artifacts = self.store.search_artifacts(target_stem, limit=5)
        seen_files = set()
        for artifact in artifacts:
            if artifact.file_path != target and artifact.file_path not in seen_files:
                results.append(f"相关工件: {artifact.file_path} ({artifact.name})")
                seen_files.add(artifact.file_path)

        return results[:5]

    def _build_summary(
        self,
        target: str,
        direct_refs: list[str],
        indirect_impacts: list[str],
        risk_level: str,
        verification_items: list[str],
    ) -> str:
        """构建影响分析摘要"""
        lines = [f"影响分析：{target}", ""]

        if direct_refs:
            lines.append("直接影响：")
            for ref in direct_refs[:10]:
                lines.append(f"  - {ref}")
        else:
            lines.append("直接影响：无")

        lines.append("")

        if indirect_impacts:
            lines.append("间接影响：")
            for imp in indirect_impacts[:10]:
                lines.append(f"  - {imp}")
        else:
            lines.append("间接影响：无")

        lines.append("")
        lines.append(f"风险等级：{risk_level}")

        if verification_items:
            lines.append("")
            lines.append("验证项：")
            for item in verification_items:
                lines.append(f"  - {item}")

        return "\n".join(lines)
