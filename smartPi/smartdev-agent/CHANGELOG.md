# Changelog

本文档记录 SmartDev Agent 的重要变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/)。

## [0.4.0] - 2026-06-07

### Added — Phase 8 Step 3: task.plan 接入 code.impact

- **`_extract_target()`**：确定 impact 目标——优先 inputs["target"]，否则从任务描述提取文件 token（.py/.js/.ts/.go/.css/.json/.md）
- **`_try_impact()`**：有 target + 索引时运行 `ImpactAnalyzer.analyze_import_impact()`，只读，R0 语义
- **推荐方案标注受影响文件**：把任务项的 `"（待分析）"` 占位符替换为真实受影响文件（前 10 个）
- **输出新增 `data["impact"]`**（仅当解析到影响）：target / affected_files / risk_level / validation
- **scope 标注 + next_steps 提示**受影响文件数
- **优雅降级**：无 target / 无索引 / 未解析 → 纯三档模板（零回归，无 impact 字段）
- **三档结构不变**：保守/推荐/深度结构和现有测试完全兼容
- **`test_task_plan.py` 扩展**：+6 tests（无索引 / inputs target / 描述提取 / 占位符替换 / 三档保留 / 未解析）

### Added — Phase 8 Step 2: architecture.map 接入 index relations

- **`_analyze_from_index()`**：从索引构建多语言依赖图
  - `code:module` artifacts → 模块节点（文件路径作节点标识，跨语言统一）
  - `imports` relations → 依赖边（internal `code:module:` / Python `module:{dotted}` 别名映射 / external）
  - 复用 `detectors.modules` 的 `ModuleInfo` + `_detect_circular_deps`，循环依赖算法与 AST 路径一致
- **数据源切换 + fallback**：有索引 → index（多语言）；无索引或无 module artifact → Python AST
- **can_run 放宽**：有索引时即使无 .py 也可分析（支持 Go/JS-TS 项目）
- **输出新增 `source` 字段**："index"（多语言）/ "ast"（Python）
- **`_safe_line_count()`**：语言无关的非空行计数（替代 Python 专属注释规则）
- **`test_architecture_map.py` 扩展**：+7 tests（fallback / index 源 / 依赖图 / 核心模块 / Go 多语言 / 循环依赖 / can_run）

### Added — Phase 8 Step 1: risk.check 接入 code.impact

- **`skills/_context_helper.py`**（新建）：Skill ↔ Context Layer 接入辅助
  - `get_index_if_available()`：检测 `.smartdev/index.sqlite`，存在则返回 ProjectIndex，否则 None（只读，不触发索引构建，异常安全）
  - `max_risk()`：多个 RiskLevel 取最高值（宁可保守，不可低估）
- **risk.check 可选接入 code.impact**：
  - inputs 提供 `target` 且项目已建索引 → 用 `ImpactAnalyzer.analyze_import_impact()` 增强
  - `final_risk = max(keyword_risk, impact_risk)`
  - 输出新增 `affected_files` / `impact_summary` / `impact_validation` / `risk_source`
  - 无 target / 无索引 / 解析失败 → 退回纯关键词匹配（零回归）
  - 保持 R0 只读语义（ImpactAnalyzer 只读索引）
- **已知问题 #1 缓解**：中文语序漏匹配问题，在有索引+target 时改用真实依赖分析判定风险
- **`test_risk_check.py` 扩展**：+6 tests（无 target / 无索引 / impact 增强 / max 风险 / 未解析 fallback / R0 只读）

### Changed

- risk.check 风险判断从"纯关键词"升级为"关键词 + 可选 impact 增强"

### Test

- **477 passed, 1 skipped** — 测试基线（458 → 477，+19：Step 1 +6, Step 2 +7, Step 3 +6）

---

## [0.3.0] - 2026-06-07

### Added — Phase 7 Step 1: TreeSitterProvider 骨架

- **TreeSitterProvider 骨架**：实现 `StructureExtractorProvider` 接口，依赖缺失时静默跳过
- **`_tree_sitter_available()`**：运行时检测 tree-sitter Python binding
- **`_try_create_tree_sitter_provider()`**：安全创建 Provider，异常不传播
- **auto_detect_treesitter**：`StructureExtractor.__init__` 新增自动注册入口
- **Step 1 不接真实 grammar**：此时 TreeSitterProvider 只注册接口，不提取任何代码结构
- **`test_tree_sitter_provider.py`**：20 tests（Provider 注册 + 接口合规 + 缺依赖跳过 + 不支持语言）
- 测试基线：405 passed, 1 skipped

### Added — Phase 7 Step 2: Go grammar 试点

- **`_load_language("go")`**：tree-sitter-go grammar 加载适配层，隔离 API 差异
- **`_extract_go()`**：Go AST 节点 → CodeSymbol 映射
  - `function_declaration` → function（exported by 首字母大写）
  - `method_declaration` → method（parent = receiver type）
  - `type_declaration` → class（struct）/ interface
  - `import_declaration` → import（单行 + block，alias/blank/dot 三种形式）
  - 语法错误不崩溃，返回 errors 列表
- **Go import relations**（`artifact_extractor.py`）：
  - `.go` 文件语言映射
  - `_parse_go_imports()` / `_resolve_go_import_target()`
  - 所有 Go import → `external:go:{module}`
  - import_kind 区分：go_import / go_import_alias / go_import_blank / go_import_dot
  - Step 2 不做 go.mod module path resolution
- **`test_go_extraction.py`**：27 tests
  - 15 Go 结构提取测试（function/method/struct/interface/import）
  - 5 Go import relation 测试
  - 2 Go 文件检测测试
  - 3 Go 全链路测试（index → artifact → relation → search）
  - 2 Provider 隔离测试（Python/TS 不受影响）
  - grammar 相关测试用 `skipif(_go_grammar_available)` 保护

### Added — Phase 7 Step 3: Go fixture 全链路验证

- **`tests/fixtures/go_project/`**：4 个 Go 源文件的磁盘 fixture 项目
  - `go.mod` — 模块声明（`github.com/example/goproject`）
  - `main.go` — 入口，import stdlib + 内部包
  - `pkg/models/user.go` — struct + methods
  - `pkg/models/types.go` — interfaces（Stringer / Validator）
  - `internal/service/user_service.go` — struct + methods + import models
- **`test_go_full_pipeline.py`**：26 tests（6 个 TestClass）
  - `TestGoFixtureExists`（4）：fixture 文件存在 + 源码不可变性检查
  - `TestGoFixtureIndexing`（4）：索引完整性 + language=go + 无源文件修改
  - `TestGoFixtureArtifacts`（4）：function / struct(class) / interface / module language
  - `TestGoFixtureImportRelations`（3）：relations 创建 + stdlib external + 内部包 external
  - `TestGoFixtureSearch`（4）：函数/结构体/接口/文件路径搜索
  - `TestGoFixtureProjectMap`（4）：map 生成 + language 统计 + modules + JSON 导出
  - `TestGoFixtureGraphValidation`（3）：validate 运行 + 无 error + stats 填充

### Added — Phase 7 Step 4: 真实 Go 项目验证（只读）

- **gnet-examples**（11 Go 文件）：13 function / 28 method / 12 class / 23 external dep，graph.validate 0 error 0 warning
- **feishu-cli**（1228 Go 文件）：8677 function / 928 method / 777 class / 40 interface，21 秒完成索引，0 error / 43 hotspot warning
- 验证 `smartdev index / search / impact` + project.map / graph.validate 对真实 Go 项目的端到端表现
- method receiver type 正确提取为 parent；stdlib + 第三方包归类为 `external:go:{module}`
- 验证产生的 `.smartdev/` 已清理，不污染外部项目
- 无代码变更（纯只读验证）

**Phase 7（Tree-sitter Go Provider）完成。**

### Changed

- `tree-sitter` + `tree-sitter-go` 已安装（optional dependency）
- Provider 链新增第三层：`TreeSitterProvider → go (confidence=0.98)`

### Test

- **458 passed, 1 skipped** — 测试基线（432 → 458，+26）

---

## [0.2.0] - 2026-06-06

### Added — Phase 6-MVP: Code Intelligence v0

- **Semantic Project Context Layer**：新增 `smartdev/context/` 模块，把项目从"文件集合"变成"可查询的语义结构"
- **IndexStore**：SQLite 存储层，4 张表（files/artifacts/relations/runs）+ FTS5 全文搜索
- **ProjectIndex**：项目索引门面类，组合 IndexStore + ArtifactExtractor + ImpactAnalyzer
- **ArtifactExtractor**：8 种工件类型提取（api_endpoint/manifest/design_token/document/model/config/server_file/extension_file）
- **ImpactAnalyzer**：规则型变更影响分析（直接引用 + 间接影响 + 风险等级 + 验证项）
- **ContextBuilder**：上下文构建器占位（Phase 6.2 完善）
- **code.search Skill**：基于 SQLite FTS5 的搜索（R0 只读）
- **code.impact Skill**：文件级 + 工件级影响分析（R0 只读）
- **CLI 新增命令**：`smartdev index`、`smartdev search`、`smartdev impact`
- **Git-aware 文件扫描**：优先 `git ls-files`，fallback `os.walk`
- **增量索引**：SHA256 hash 比较，跳过未变化文件
- **62 个新测试**：IndexStore/ProjectIndex/ArtifactExtractor/code.search/code.impact

### Changed

- CLI `main()` 修复重复 `parse_args()` 调用 bug
- 版本号升级至 0.2.0

### Test

- 227 个测试全部通过（165 原有 + 62 新增）

---

### Added — Phase 6.2: Code Intelligence v1（同日完成）

- **StructureExtractor（Provider 机制）**：PythonAstExtractor (confidence=1.0) + JsTsRegexFallbackExtractor (confidence=0.55) + NullStructureExtractor
- **Python import relations**：import → relations 表，module artifact，去重 upsert，alias 保留，external/unresolved placeholder
- **Import relation hardening**：source/target ID 对齐，DB 去重，相对 import 不重复，metadata line 信息修正
- **ImpactAnalyzer 升级**：消费 imports relation 做 reverse lookup，支持 module/file/symbol 三种 target resolve
- **project.map 导出**：JSON + Markdown 项目地图，hotspots / external deps / unresolved 统计
- **graph.validate v0**：6 类校验（orphan source/target、duplicate、missing metadata、hotspot、unresolved）
- **CLAUDE.md**：项目行为规则（7 条核心约束）

### Changed

- ProjectIndex 新增 `index()` 方法（一步完成 scan + extract + write）
- IndexStore 新增 `upsert_relation()` 去重方法

### Test

- 310 个测试全部通过（165 原有 + 145 新增）

### 能力边界

Phase 6.2 的目标是让 SmartDev 能从"搜索相关文件"升级为"基于项目语义关系判断影响范围"。
当前能力边界为 **module-level impact analysis**，不承诺：

- ❌ 完整符号级引用分析（需 Tree-sitter）
- ❌ 函数调用图（需完整 call graph）
- ❌ JS/TS 高置信度解析（当前为 regex fallback，confidence=0.55）

该阶段已冻结，不再继续加功能。下一步：Phase 6.3 — JS/TS Parser Provider。

---

### Added — Phase 6.3 Step 1: Node Bridge 骨架（同日）

- **node_bridge/ 模块**：独立 Node 解析实验模块（`smartdev/context/node_bridge/`）
- **package.json**：@babel/parser 依赖，零其他 npm 依赖
- **extract_structure.js**：JSONL 协议，`--batch` 模式，`errorRecovery: true`
- **test_extract_structure.js**：6 场景 Node 侧测试（import/export/function/class/arrow/type）
- **README.md**：安装说明 + 协议文档
- 边界：不碰 Python，不碰索引链路

### Added — Phase 6.3 Step 2: Python NodeBridgeExtractor 集成（同日）

- **NodeBridgeProcess**：长期 Node 子进程单例管理，JSONL 协议通信，自动重启恢复
- **NodeBridgeExtractor**：实现 StructureExtractorProvider 接口，confidence=0.95
- **auto_detect_node**：StructureExtractor 初始化时自动检测 Node.js，可用时自动注册
- **三层 fallback**：Node 未安装 → 不注册；启动失败 → 静默跳过；单文件超时 → 返回空
- 新增 2 文件 + 修改 2 文件，22 tests（含 skipif 保护的真实集成测试）

### Added — Phase 6.3 Step 3: JS/TS 全链路验证（同日）

- **JS/TS import relation 构建**：`artifact_extractor.py` 新增 ES module import 解析，支持 7 种导入模式（named/default/namespace/side_effect/re-export/require/dynamic）
- **语言感知 dispatch**：`_build_import_relations()` 根据文件后缀自动选择 Python/JS/TS import 解析器
- **相对路径解析**：`./foo` / `../bar` 解析为 project 内路径，bare specifier 归类为 external
- **JS/TS 全链路集成测试**：18 tests 覆盖 index → search → project.map → graph.validate 端到端
- 修改 1 文件 + 新增 1 文件，无 breaking changes

### Changed

- `code:module` artifact 的 metadata 中 `language` 字段从硬编码 `"python"` 改为动态检测（`python`/`typescript`/`javascript`）

### Test

- 350 个测试全部通过（332 原有 + 18 新增）

### Added — Phase 6.3 Step 4.1: 排除 .d.ts 避免 Artifact 膨胀（同日）

- **跳过 .d.ts 文件**：`artifact_extractor.py` 增加 `.d.ts` 过滤（如 wrangler types 生成的声明文件）
- **scripts/verify_gateway.py**：真实项目 13 项指标收集脚本
- 修复：artifacts 756→78（-90%），全链路健康

### Added — Phase 6.3 Step 4.2: JS/TS Import Target 归一化（同日）

- **`_resolve_js_ts_import_target()`**：relative import 文件系统解析（ext + index 候选）
- **归一化到 `code:module:{path}`**：`../types` / `./types` / `../../types` → 同一 `code:module:src/types.ts`
- **`unresolved:relative_file_not_found`**：文件不存在的 import 明确标记
- **project_map hotspot 聚合**：按 resolved target_id 聚合而非 raw specifier
- **graph_validator 新增**：`unresolved_relative_import` warning
- 355 tests

### Added — Phase 6.3 Step 5: tsconfig paths alias 解析（同日）

- **`tsconfig_resolver.py`**：读取 `tsconfig.json` / `jsconfig.json` 的 `compilerOptions.paths` + `baseUrl`
- **精确匹配**：`@types → src/types.ts`
- **通配符匹配**：`@/* → src/*` → `@/lib/x → src/lib/x`
- **懒加载 + 缓存**：`_get_tsconfig_resolver()` 同一批次只读一次配置
- **graph_validator 新增**：`alias_target_not_found` warning
- 新增 `test_js_ts_path_alias.py`（15 tests）
- 370 tests

### Added — Phase 6.3 Step 3 补充: 磁盘 Fixture 全链路验证

- **`tests/fixtures/js_ts_project/`**：独立于 inline fixture 的磁盘项目
  - 7 个文件：`package.json` + `tsconfig.json` + 5 个 TS/TSX 源文件
  - 覆盖：interface, type alias, class, function, arrow function, import, re-export, JSX component
- **`TestJsTsFixtureProject`**（16 tests）：基于磁盘 fixture 的全链路验证
  - index → search → project.map → graph.validate 端到端
  - Node bridge Provider 注册 + TSX 命中验证
  - 源码不可变性验证
- **`TestJsTsFixtureNoNodeFallback`**（1 test）：Node 不可用时的 regex fallback 路径
- 395 tests（原有 370 + 25 新增）

### Fixed — Phase 6.3.1: CLI 测试基线修复

- **`test_cli.py` 修复**：`subprocess.run` 调用注入 `PYTHONPATH`，解决本地包未安装时的 `No module named smartdev` 错误
- **`_run_cli()` 辅助函数**：统一管理 CLI subprocess 调用的环境变量
- 7/7 CLI tests 通过，不再需要 `--ignore=tests/test_cli.py`
- 386 passed, 1 skipped — 全量测试基线清洁

### Changed

- Phase 6.3A 正式冻结：Node bridge (Babel) JS/TS 高置信度解析链路闭合，全量 386 tests 清洁基线

### Test（最终）

- **395 tests passed**（370 → 386，+16 fixture 验证测试 + 7 CLI 测试全部修复）
- 1 skipped（Node 不可用 fallback 测试，Node 可用时自动跳过）
- Phase 6.3 功能链路完整，测试基线清洁，正式冻结

---

## [0.1.0] - 2026-06-03

### Added

- **项目骨架**：pyproject.toml，零外部依赖，Python >= 3.10
- **核心数据模型**：RiskLevel(R0-R3), TaskType(8种), SkillResult, ProjectContext
- **Skill 基类**：`__init_subclass__` 自动注册，can_run/run 接口分离
- **技术栈检测器**：11 种技术标记文件检测（Python/Node/Chrome Extension/FastAPI/Vue/React/Tailwind/Docker/Vite/Git/TypeScript）
- **文档状态检测器**：10 种常见文档覆盖率检测
- **入口文件检测器**：Python/Node.js/Chrome Extension 入口检测
- **repo.scan Skill**：仓库扫描（技术栈 + 入口 + 文档 + 目录树），R0 只读
- **Risk Controller**：运行时风险检查，R2/R3 enforce 拦截
- **Reporter**：执行前/后输出模板（协议 §6 + §7）
- **task.plan Skill**：三档方案（保守/推荐/深度），R0 只读
- **开发进度文档**：docs/development-progress.md
- **CLI 入口**：`smartdev scan/plan/list` 命令行工具

### Changed

- repo_scan 从单文件重构为 skill.yaml + skill.py 目录结构
- 协议加入 git 提交规则（§3.6 + §5 第 10 步 + §4 第 16 条）

### Test

- 71 个测试全部通过
- 覆盖：Skill 基类、三个检测器、repo.scan、Risk Controller、Reporter、task.plan、CLI
