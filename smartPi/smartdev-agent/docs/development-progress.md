# SmartDev Agent 开发进度

> 最后更新：2026-06-07
> 当前阶段：Phase 7 Step 2 完成 — Go grammar 试点（TreeSitterProvider 激活）

---

## 1. 项目概述

SmartDev Agent 是一个项目开发与仓库改进 AI Agent，目标是将项目从"想法多、代码散"推进到"目标清、任务可执行、可持续迭代"。

**技术栈**：Python 3.10+，零外部依赖
**架构**：四层（Core Runtime → Workflow → Skill → Project Adapter）

---

## 2. 当前阶段

### Phase 1：只读诊断 Agent（进行中）

目标：不改代码，只读项目。实现 R0 只读类 Skill。

| 目标 | 状态 | 说明 |
|------|------|------|
| 项目骨架 | ✅ 完成 | models.py, skills/base.py |
| Risk Controller | ✅ 完成 | core/risk.py |
| Reporter 模板 | ✅ 完成 | core/reporter.py |
| repo.scan | ✅ 完成 | 技术栈/入口/文档/目录树 |
| task.plan | ✅ 完成 | 三档方案（保守/推荐/深度） |
| architecture.map | ✅ 完成 | 架构分析（ast 解析 + 循环依赖检测） |
| token.audit | ✅ 完成 | Token 审计（CSS 变量 + 硬编码颜色检测） |
| risk.check | ✅ 完成 | 风险检查（规则引擎 + 前置检查清单） |
| qa.checklist | ✅ 完成 | 验收清单（6 类模板） |
| CLI 入口 | ✅ 完成 | `smartdev scan/plan/list` |

**Phase 1 已完成。**

### Phase 2：项目适配器（进行中）

目标：让 Agent 能区分项目类型。

| 目标 | 状态 | 说明 |
|------|------|------|
| 适配器数据模型 | ✅ 完成 | core/adapter.py — ProjectAdapter |
| 适配器加载器 | ✅ 完成 | load_adapter() + find_adapter() |
| 项目类型检测 | ✅ 完成 | Chrome Extension/FastAPI/Python/Node.js |
| SmartFav 适配器 | ✅ 完成 | adapters/smartfav.json |
| Chrome Extension 适配器 | ✅ 完成 | adapters/chrome_extension.json |
| FastAPI 适配器 | ✅ 完成 | adapters/fastapi.json |
| diagnose 命令 | ✅ 完成 | CLI 集成适配器 + 扫描 |

### Phase 3：文档类 Skill（完成）

目标：生成 README、CONTRIBUTING、bug-notes。

| 目标 | 状态 | 说明 |
|------|------|------|
| doc.generate | ✅ 完成 | README/CONTRIBUTING/CHANGELOG 草案生成 |

**Phase 3 已完成。**

### Phase 4：Patch 类 Skill（完成）

目标：生成小范围代码修改。

| 目标 | 状态 | 说明 |
|------|------|------|
| core/patch.py | ✅ 完成 | Patch 数据模型 + diff 生成器 |
| code.patch | ✅ 完成 | 代码补丁生成（不直接应用） |

**Phase 4 已完成。**

### Phase 5：完整迭代闭环（完成）

目标：一次完成"小任务 → 修改 → 验证 → 总结 → 文档更新"。

| 目标 | 状态 | 说明 |
|------|------|------|
| core/workflow.py | ✅ 完成 | 工作流引擎（6 步默认流程） |
| CLI run 命令 | ✅ 完成 | 一键执行完整工作流 |
| 真实项目验证 | ✅ 完成 | ragflow/go-zero-demo/phpmyadmin |

**Phase 5 已完成。**

### Phase 6-MVP：Code Intelligence v0（完成）

目标：让 SmartDev 能知道项目里有哪些关键文件和工件，以及某个改动大概会影响哪里。

| 里程碑 | 交付物 | 状态 | 说明 |
|--------|--------|------|------|
| M1 | repo.scan 增强 | ✅ 完成 | Git-aware 扫描 + ignore 策略 + hash 变更检测 |
| M2 | .smartdev/index.sqlite | ✅ 完成 | SQLite 存储层（files/artifacts/relations/runs）+ FTS5 |
| M3 | Artifact 提取 | ✅ 完成 | 8 种工件类型提取（api_endpoint/manifest/design_token/document/model/config/server_file/extension_file） |
| M4 | code.search | ✅ 完成 | 基于 FTS5 的搜索 Skill + CLI search 命令 |
| M5 | code.impact | ✅ 完成 | 规则型影响分析 Skill + CLI impact 命令 |

**Phase 6-MVP 已完成。**

### Phase 6.2：Code Intelligence v1（已完成）

目标：从"知道项目有什么文件"升级到"知道代码里有什么符号，谁引用了谁"。

| Step | 交付物 | 状态 | 说明 |
|------|--------|------|------|
| Step 1 | 多语言结构提取 | ✅ 完成 | Provider 机制：PythonAstExtractor (1.0) + JsTsRegexFallbackExtractor (0.55) |
| Step 2A | Python import relations | ✅ 完成 | import → relations 表，module artifact，alias 保留 |
| Step 2A.1 | Import relation hardening | ✅ 完成 | source/target ID 对齐，DB 去重，相对 import 不重复 |
| Step 3 | ImpactAnalyzer 升级 | ✅ 完成 | 消费 import relations，reverse lookup 依赖方 |
| Step 4 | project.map 导出 | ✅ 完成 | JSON + Markdown 项目地图，hotspots / external deps |
| Step 5 | graph.validate v0 | ✅ 完成 | 6 类校验（orphan/duplicate/metadata/hotspot/unresolved） |

**Phase 6.2 — Code Intelligence v1 完成。**

能力边界：
- ✅ Python AST 结构提取（Provider 机制，confidence=1.0）
- ✅ JS/TS Babel Parser 结构提取（Node bridge，confidence=0.95）
- ✅ Module artifact + imports relation（Python + JS/TS import/export）
- ✅ ImpactAnalyzer 消费 imports relation（reverse lookup）
- ✅ symbol query fallback 到 module-level impact（relation_scope=module）
- ✅ project.map 导出（JSON + Markdown）
- ✅ graph.validate 校验（6 类检查 + JS/TS 专用 warning）
- ❌ 不支持精确符号级引用分析（需 Tree-sitter）
- ❌ 不支持函数调用图（需完整 call graph）
- ❌ 不支持 Vue/Svelte SFC script 抽取（Phase 6.3C，后续可选）

### Phase 6.3：JS/TS Parser Provider v1（已完成）

目标：为 JS/TS/JSX/TSX 提供高置信度解析路径（Node + Babel Parser），作为 optional dependency。

| Step | 交付物 | 状态 | 说明 |
|------|--------|------|------|
| Step 0 | 执行前设计 | ✅ 完成 | 5 个核心问题决策，provider 协议，Node bridge 协议 |
| Step 1 | Node bridge 骨架 | ✅ 完成 | `node_bridge/extract_structure.js`，JSONL 协议，`--batch` 模式 |
| Step 2 | Python 集成 | ✅ 完成 | `NodeBridgeProcess` (子进程单例) + `NodeBridgeExtractor` (Provider) |
| Step 3 | JS/TS import relations | ✅ 完成 | 7 种 ES module 导入模式 + 全链路集成测试 |
| Step 4.1 | 排除 .d.ts | ✅ 完成 | artifact 膨胀 -90%（756→78） |
| Step 4.2 | Import target 归一化 | ✅ 完成 | relative import → `code:module:{path}` |
| Step 5 | tsconfig paths alias | ✅ 完成 | `@/* → src/*` 解析 + `TsConfigResolver` |
| Step 3 补充 | 磁盘 fixture 验证 | ✅ 完成 | `tests/fixtures/js_ts_project/` + 16 fixture 测试 |

**Phase 6.3A 正式完成。**

新增模块：
- `context/node_bridge.py` — Python 适配层（`NodeBridgeProcess` + `NodeBridgeExtractor`）
- `context/node_bridge/` — Node 侧解析模块（`@babel/parser`）
- `context/tsconfig_resolver.py` — tsconfig/jsconfig paths alias 解析器

Provider 链（Phase 6.3 最终状态）：
```
PythonAstExtractor          → python (confidence=1.0)
NodeBridgeExtractor         → javascript, typescript (confidence=0.95)
JsTsRegexFallbackExtractor  → (JS/TS fallback, confidence=0.55)
NullStructureExtractor      → 不支持的语言
```

能力边界：
- ✅ JS/TS 结构提取（function, class, interface, type alias, import, export）
- ✅ ES Module import relations（named, default, namespace, side_effect, re_export, require, dynamic）
- ✅ Relative import 文件系统解析（ext + index 候选）
- ✅ tsconfig paths alias 解析（精确匹配 + 通配符）
- ✅ Node 自动检测 + 静默 fallback
- ❌ 不支持 Vue/Svelte SFC script 抽取（Phase 6.3C）
- ❌ 不支持 TypeScript Compiler API 类型级别解析（Phase 6.3B）
- ❌ 不支持 extends / references 多文件继承

### Phase 7：Tree-sitter Multi-language Graph Provider（进行中）

目标：为不支持的语言（首批 Go）提供高置信度解析，作为第三层 optional Provider。

| Step | 交付物 | 状态 | 说明 |
|------|--------|------|------|
| Step 0 | 执行前设计 | ✅ 完成 | 设计文档 phase-7-design.md — 6 问题决策 + 实施路线 |
| Step 1 | TreeSitterProvider 骨架 | ✅ 完成 | Provider 注册 + 依赖检测 + auto_detect + 接口合规测试 |
| Step 2 | Go grammar 试点 | ✅ 完成 | Go AST 映射 + import relations + test_go_extraction.py（27 tests） |
| Step 3 | Go fixture 全链路验证 | ✅ 完成 | tests/fixtures/go_project/ + 全链路 index→search→map→validate（26 tests） |
| Step 4 | 真实 Go 项目验证 | ✅ 完成 | gnet-examples（11 go 文件，0 error/warning）+ feishu-cli（1228 go 文件，0 error）只读验证 |

Provider 链（Phase 7 Step 2 状态）：
```
PythonAstExtractor      → python (confidence=1.0)
NodeBridgeExtractor     → javascript, typescript (confidence=0.95)
TreeSitterProvider      → go (confidence=0.98)  ← Step 2 激活
JsTsRegexFallbackExtractor → JS/TS fallback (confidence=0.55)
NullStructureExtractor  → 不支持的语言
```

Go 提取能力（Step 2）：
- ✅ function_declaration → function（exported detection）
- ✅ method_declaration → method（parent = receiver type）
- ✅ type_declaration → class（struct）/ interface
- ✅ import_declaration → import（单行 + block，alias/blank/dot）
- ✅ Go imports → external:go:{module}（import_kind 区分）
- ✅ 语法错误 → errors 列表，不崩溃
- ❌ go.mod module path resolution（Step 3 后续可选）
- ❌ struct 字段级解析（P2）
- ❌ interface 实现关系（P2）

---

## 3. 已完成模块

### 3.1 核心数据模型 (`models.py`)

| 类型 | 说明 |
|------|------|
| `RiskLevel` | R0-R3 风险等级枚举 |
| `TaskType` | 8 种任务类型 |
| `SkillResult` | Skill 统一输出格式 |
| `ProjectContext` | 项目上下文 |

### 3.2 Skill 基类 (`skills/base.py`)

- `__init_subclass__` 自动注册机制
- `can_run()` / `run()` 接口分离
- `describe()` 元数据输出

### 3.3 检测器 (`detectors/`)

| 检测器 | 能力 | 检测项 |
|--------|------|--------|
| `tech_stack.py` | 技术栈检测 | 11 种技术（Python/Node/Chrome Extension/FastAPI/Vue/React/Tailwind/Docker/Vite/Git/TypeScript） |
| `docs_status.py` | 文档状态 | 10 种常见文档覆盖率 |
| `entrypoints.py` | 入口文件 | Python/Node.js/Chrome Extension 入口 |

### 3.4 核心运行时 (`core/`)

| 模块 | 说明 |
|------|------|
| `risk.py` | Risk Controller — 风险等级检查 + enforce 拦截 |
| `reporter.py` | 执行前/后输出模板（协议 §6 + §7） |

### 3.5 Skills

| Skill | 风险 | 说明 |
|-------|------|------|
| `repo.scan` | R0 | 仓库扫描：技术栈 + 入口 + 文档 + 目录树 |
| `task.plan` | R0 | 任务规划：三档方案（保守/推荐/深度） |
| `architecture.map` | R0 | 架构分析（AST 解析 + 循环依赖检测） |
| `token.audit` | R0 | Token 审计（CSS 变量 + 硬编码颜色） |
| `risk.check` | R0 | 风险检查（规则引擎 + 前置检查清单） |
| `qa.checklist` | R0 | 验收清单（6 类模板） |
| `doc.generate` | R1 | 文档生成（README/CONTRIBUTING/CHANGELOG） |
| `code.patch` | R1 | 代码补丁（占位符） |
| `code.search` | R0 | 代码搜索（FTS5 + LIKE，Phase 6-MVP） |
| `code.impact` | R0 | 影响分析（规则型，Phase 6-MVP） |

---

## 4. 版本历史

### v0.1.0（2026-06-03）— 项目初始化

| Commit | 类型 | 说明 |
|--------|------|------|
| `9c7d1b5` | docs | agent 开发前的文档 |
| `53b26da` | docs | 整理 smartPi 文档目录结构 |
| `6aad2fa` | feat | SmartDev Agent 项目骨架 + Skill 基类 |
| `d860aa1` | feat | 项目检测器（技术栈/文档状态/入口文件） |
| `b0b0f28` | feat | repo.scan Skill — 第一个只读诊断 Skill |
| `4fa91ed` | docs | 协议加入 git 提交规则 |
| `e217fdf` | feat | Risk Controller — 运行时风险检查 |
| `3912179` | feat | Reporter — 执行前/后输出模板 |
| `c16837a` | refactor | repo_scan 拆分为 skill.yaml + skill.py |
| `c1569ca` | feat | task.plan Skill — 方案分级 |
| `21ba715` | docs | 补齐进度文档和 CHANGELOG |
| `1f60924` | feat | CLI 入口 — smartdev scan/plan/list |
| `7f620aa` | docs | 协议加入「边讲边做」原则 |
| `d19a7b5` | feat | architecture.map Skill — 架构分析 |
| `47eef4c` | docs | 进度文档更新（architecture.map 完成） |
| `db295b3` | feat | token.audit Skill — Token 审计 |
| `a690808` | docs | 进度文档更新（token.audit 完成） |
| `1fff4bb` | feat | risk.check Skill — 风险检查 |
| `0f5a3d0` | docs | 进度文档更新（risk.check 完成） |
| `4b9e737` | feat | qa.checklist Skill — 验收清单（Phase 1 完成） |
| `c98714b` | docs | Phase 1 完成 — 进度文档更新 |
| `682b185` | feat | 项目适配器系统（Phase 2） |
| `d19f1c7` | feat | CLI 新增 diagnose 命令 |
| `151c1a6` | docs | 进度文档更新（Phase 2 适配器完成） |
| `db61eb8` | feat | doc.generate Skill — 文档生成（Phase 3） |
| `6d32345` | docs | 进度文档更新（Phase 3 完成） |
| `a7243e3` | feat | code.patch Skill — 代码补丁（Phase 4） |
| `d358ab2` | docs | 进度文档更新（Phase 4 完成） |
| `94d8c50` | docs | 验证报告 — Phase 1-4 合规审计 |
| `2ed58e5` | feat | Workflow Engine — 完整迭代闭环（Phase 5） |

---

## 5. 测试覆盖

```
540 passed, 1 skipped — 0 failed
```

| 测试文件 | 数量 | 覆盖模块 |
|---------|------|---------|
| test_skill_base.py | 8 | Skill 基类 + 自动注册 |
| test_detectors.py | 14 | 五个检测器 |
| test_repo_scan.py | 9 | repo.scan Skill |
| test_risk_controller.py | 14 | Risk Controller |
| test_reporter.py | 9 | 执行前/后模板 |
| test_task_plan.py | 16 | task.plan Skill + code.impact 接入（Phase 8 Step 3，10+6） |
| test_skill_context_integration.py | 7 | Context Layer ↔ Skill workflow 端到端（Phase 8 Step 4） |
| test_cli.py | 7 | CLI 入口 |
| test_architecture_map.py | 18 | architecture.map Skill + index relations 接入（Phase 8 Step 2，11+7） |
| test_token_audit.py | 10 | token.audit Skill |
| test_qa_checklist.py | 11 | qa.checklist Skill |
| test_adapter.py | 14 | 项目适配器系统 |
| test_doc_generate.py | 11 | doc.generate Skill |
| test_patch.py | 39 | Patch 数据模型 + find-replace/序列化/路径安全/apply/rollback（Phase 9 Step 1A+1B，11+28） |
| test_code_patch.py | 18 | code.patch Skill + find-replace/impact 真实化（Phase 9 Step 2，9+9） |
| test_code_apply.py | 14 | code.apply Skill（写盘/权限门/R3确认/审计，Phase 9 Step 3） |
| test_code_rollback.py | 5 | code.rollback Skill（Phase 9 Step 3） |
| test_workflow.py | 6 | Workflow Engine |
| test_index_store.py | 26 | SQLite 存储层（Phase 6-MVP） |
| test_project_index.py | 7 | 项目索引门面类（Phase 6-MVP） |
| test_artifact_extractor.py | 15 | Artifact 提取器（Phase 6-MVP） |
| test_code_search.py | 7 | code.search Skill（Phase 6-MVP） |
| test_code_impact.py | 7 | code.impact Skill（Phase 6-MVP） |
| test_structure_extractor.py | 30 | 多语言结构提取 Provider（Phase 6.2 + 6.3） |
| test_import_relations.py | 19 | Import 关系构建（Phase 6.2） |
| test_impact_import_relations.py | 12 | ImpactAnalyzer import 分析（Phase 6.2） |
| test_project_map.py | 9 | 项目地图导出（Phase 6.2） |
| test_graph_validator.py | 15 | 图谱校验（Phase 6.2） |
| test_node_bridge_extractor.py | 20 | Node Bridge Python 适配（Phase 6.3） |
| test_js_ts_full_pipeline.py | 40 | JS/TS 全链路集成（Phase 6.3） |
| test_js_ts_path_alias.py | 15 | tsconfig paths alias（Phase 6.3） |
| test_tree_sitter_provider.py | 20 | TreeSitterProvider 骨架 + 接口（Phase 7 Step 1） |
| test_go_extraction.py | 27 | Go 结构提取 + import relations + 全链路（Phase 7 Step 2） |
| test_go_full_pipeline.py | 26 | Go fixture 磁盘项目全链路验证（Phase 7 Step 3） |
| test_risk_check.py | 17 | risk.check Skill + code.impact 接入（Phase 8 Step 1，11+6） |

---

## 6. 已知问题

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | risk.check 关键词匹配是短语匹配，中文语序灵活导致漏匹配（如"重构目录"≠"目录重构"） | 中 | 已缓解（Phase 8 Step 1：有索引+target 时改用 impact 分析判定风险，关键词仅作 fallback） |
| 2 | code.patch 生成的是占位符补丁，非真实代码变更 | 低 | Phase 9 规划中（零 LLM → 确定性 find-replace 补丁 + 安全应用机制，设计见 phase-9-design.md） |
| 3 | 适配器用 JSON 格式，agent.md 设计的是 YAML | 低 | 可迁移 |

---

### Phase 7 Step 0：Tree-sitter 设计确认（✅ 完成）

- [x] 设计文档：[phase-7-design.md](phase-7-design.md) — 6 问题决策 + 实施路线
- 核心决策：
  - Tree-sitter 为 optional dependency（与 Node bridge 同级别）
  - Python tree-sitter binding 接入（非 Node/WASM）
  - 首批试点：Go（单语言）
  - 复用现有 Provider 接口 + CodeSymbol / ImportRecord
  - 不替换 Python AST / NodeBridge

### Phase 7 Step 1：TreeSitterProvider 骨架（✅ 完成）

- [x] `tree_sitter_provider.py` — Provider 骨架，接口合规
- [x] `structure_extractor.py` — auto_detect_treesitter 入口
- [x] `test_tree_sitter_provider.py` — 20 tests（骨架 + 接口 + 依赖检测）
- 测试基线：405 passed

### Phase 7 Step 2：Go grammar 试点（✅ 完成）

- [x] `tree_sitter_provider.py` 全面升级（_load_language("go") + Go AST 映射）
- [x] `artifact_extractor.py` Go import relation 分支
- [x] `test_go_extraction.py` — 27 tests（结构提取/import relations/全链路）
- 测试基线：432 passed, 1 skipped

### Phase 7 Step 3：Go fixture 全链路验证（✅ 完成）

- [x] `tests/fixtures/go_project/` 磁盘 fixture（4 个 Go 文件）
- [x] `test_go_full_pipeline.py` — 26 tests，全链路 index → search → project.map → graph.validate
- 测试基线：**458 passed, 1 skipped**

### Phase 7 Step 4：真实 Go 项目验证（✅ 完成）

只读验证，不改代码。验证 `smartdev index / search / impact` + project.map / graph.validate 对真实 Go 项目的表现。

| 项目 | Go 文件 | 提取结果 | graph.validate |
|------|--------|---------|----------------|
| gnet-examples | 11 | 13 function / 28 method / 12 class / 23 external dep | 0 error, 0 warning |
| feishu-cli | 1228 | 8677 function / 928 method / 777 class / 40 interface | 0 error, 43 hotspot warning |

- ✅ Go 结构提取（function/method/struct/interface）在真实项目准确
- ✅ method receiver type 正确提取为 parent
- ✅ stdlib + 第三方包归类为 external:go:{module}
- ✅ 大型项目（1228 文件）21 秒完成索引，无 error
- ✅ 验证产生的 `.smartdev/` 已清理，不污染外部项目

**Phase 7（Tree-sitter Go Provider）完成。**

### Phase 8：Context Layer ↔ Skill 接入打通（设计确认）

目标：把已建好的 Context Layer（索引/impact/relations）真正喂给 Skill 层，消除"眼睛和大脑两座孤岛"。
不新增解析能力，只做"接线"。

| Step | 交付物 | 状态 | 说明 |
|------|--------|------|------|
| Step 0 | 执行前设计 | ✅ 完成 | 设计文档 phase-8-design.md — 5 问题决策 + 优雅降级原则 |
| Step 1 | risk.check ← code.impact | ✅ 完成 | 关键词匹配升级为影响范围判断 + 优雅降级（6 tests） |
| Step 2 | architecture.map ← index | ✅ 完成 | 复用索引 relations，支持多语言依赖图（7 tests） |
| Step 3 | task.plan ← impact | ✅ 完成 | 推荐方案标注受影响文件 + target 自动提取（6 tests） |
| Step 4 | 端到端验证 | ✅ 完成 | workflow 注入 target 驱动 impact + 真实项目验证（7 tests） |

**Phase 8（Context Layer ↔ Skill 接入打通）完成。** 三个核心 Skill 现在都能消费 Context Layer：
- risk.check：影响范围驱动风险判断（max(keyword, impact)）
- architecture.map：多语言依赖图 + 循环依赖（索引优先）
- task.plan：推荐方案标注真实受影响文件
- workflow：可选 target 注入，端到端驱动 impact

核心原则：
- 优雅降级——有索引则增强，无索引退回原逻辑，零回归
- 只改 skills/，不动 context/
- 风险信号取最大值（keyword vs impact）

不在本阶段：code.patch 真实化（→ Phase 9 Safe Patch Agent）、token.audit 接入、新增语言

### Phase 9：Safe Patch Agent（设计确认）

目标：把 code.patch 从占位符升级为"安全可控的代码执行能力"，完成 L3 诊断型 → L4 执行型跳跃。

| Step | 交付物 | 状态 | 说明 |
|------|--------|------|------|
| Step 0 | 执行前设计 | ✅ 完成 | 设计文档 phase-9-design.md — 5 问题决策 + 安全加固 P0-1~P0-4 |
| Step 1A | core/patch.py 可审查草案 | ✅ 完成 | find_replace_patch + 序列化(save/load) + hash 元数据 + 路径安全 + get_index schema 加固（17 tests） |
| Step 1B | core/patch.py apply/rollback | ✅ 完成 | apply_patch（hash 校验 + 路径安全 + 备份 + 原子性）+ rollback_patch（11 tests） |
| Step 2 | code.patch propose 真实化 | ✅ 完成 | find-replace 真实 diff + patch_id + impact 可选增强（9 tests） |
| Step 3 | code.apply Skill + 权限门 | ✅ 完成 | 写盘 + protected_path + R3 强确认 + 审计；code.rollback Skill（19 tests） |
| Step 4 | code.rollback + 端到端验证 | ✅ 完成 | propose→apply→rollback 闭环（含 Step 3 测试覆盖，540 tests） |

核心约束（诚实面对零 LLM）：
- 不做智能代码生成（破坏零依赖 + 确定性）
- 聚焦"安全执行机制"（生成/应用分离、impact 驱动、备份回滚、权限门）
- 旗舰场景：确定性 find-replace / token 替换（对应 SmartFav 硬编码颜色替换）
- 生成与应用分离：code.patch(propose, R1) / code.apply(R2/R3 确认) / code.rollback(R1)
- 默认安全：不加 --apply 绝不碰磁盘

### Phase 6.3B/C（后续可选）

### 优化项

- [ ] risk.check 关键词匹配优化（单词匹配 / 分词）
- [ ] 增加 FileWatcher / 增量同步
- [ ] ContextBuilder 完善（给 LLM 提供结构化上下文）

---

## 8. 协议合规状态

| 条款 | 状态 | 说明 |
|------|------|------|
| §3.1 先分析后修改 | ✅ | |
| §3.2 小步快跑 | ✅ | |
| §3.3 每步可验证 | ✅ | 540 个测试 |
| §3.4 不扩大范围 | ✅ | |
| §3.5 文档同步更新 | ✅ | 本文档即为证明 |
| §3.6 每步提交 git | ✅ | 25+ commits |
| §3.7 边讲边做 | ✅ | 开发过程同步解释原理 |
| §4 禁止行为 #9 | ✅ | 本文档即为证明 |
| §6 执行前输出 | ✅ | reporter.py 已实现 |
| §7 执行后输出 | ✅ | reporter.py 已实现 |
| §11 风险等级 | ✅ | Risk Controller 已实现 |
| §12 方案分级 | ✅ | task.plan 已实现 |
