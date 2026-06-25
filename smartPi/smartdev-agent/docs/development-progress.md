# SmartDev Agent 开发进度

> 最后更新：2026-06-10
> 当前阶段：Phase 11 已全部完成 — Standalone Hardened（1925 tests, 30 MCP 工具）

---

## 1. 项目定位

**SmartDev 是模型无关的 AI 编程协作控制层。**

它通过项目语义索引、影响分析、任务规划和安全 Patch，把代码仓库从"文件集合"变成 AI Agent 可查询、可判断、可安全修改的项目系统。它不绑定任何一个模型，而是把 Claude / Cursor / Kiro / Codex 等外部 Agent 都纳入同一套项目上下文、任务边界、风险控制和验收流程里。

```
SmartDev = 项目语义图谱 + Skill 执行层 + 风险控制 + 安全 Patch + MCP 工具出口
         = 模型无关的 AI 编程协作控制层
```

它不是"又一个写代码 Agent"，也不是聊天机器人，而是在人和 AI 编码工具之间增加一层**"项目理解 + 风险控制 + 安全执行"的本地智能层**。目标是给这些外部 Agent 提供可信的本地项目上下文，而不是替代它们。

### 分层架构（L1–L7）

```
L1  诊断层      repo.scan / tech_stack / docs_status / entrypoints
L2  规划层      task.plan / architecture.map / risk.check / qa.checklist
L3  语义层      code.index / code.search / code.impact / project.map / graph.validate
               多语言 Provider：Python(1.0) / JS-TS(0.95) / Go(0.98)
L3a Skill接入   risk.check ← impact / architecture.map ← index / task.plan ← impact
L4  执行层      code.patch(propose) → code.apply → code.rollback
L5  版本治理层  git.status / git.diff.explain / git.commit.plan / git.release.plan / git.merge.check（Phase 11A ✅）
               manifest / snapshot / doc.map / doc.consistency / doc.update.plan / doc.patch.propose（Phase 11C ✅）
               dev.guard / dependency.guard / security.review / change.budget / diff.explain / guard.runner（Phase 11B ✅）
L6  外部接入层  MCP Server → Claude / Kiro / Cursor / Codex（Phase 10 ✅，31 工具）
L7  模型协作层  handoff pack / scope gate（Phase 11D ✅）→ model registry / task router（Phase 12，可选）
```

完整 AI 编程闭环（各层覆盖范围）：

```
理解项目 → 判断影响 → 安全修改 → 测试验收 → 版本提交 → 发布治理
   L1-L3       L3          L4          L2       L5(11A)     L5(11A)
```

L7 是横向调度层，不替代任何现有层，而是决定：这个任务用哪个模型？需要哪些 SmartDev 工具？输出必须满足什么结构？是否允许进入 patch propose？

### Human-Controlled AI Coding Loop

AI 编程真正的风险是人失去理解权、判断权和验收权。SmartDev 通过六个门把每一次 AI 改动约束成可解释、可评估、可回滚、可交付的工程记录：

| 门 | 对应能力 | 覆盖阶段 |
|----|---------|---------|
| 理解门 | code.index / code.search / project.map / architecture.map | Phase 1–7 ✅ |
| 影响门 | code.impact / graph.validate | Phase 6–8 ✅ |
| 风险门 | risk.check（含 impact 增强）/ RiskController | Phase 8 ✅ |
| 权限门 | R0–R3 等级 / protected_paths / apply 显式确认 | Phase 9 ✅ |
| 测试门 | qa.checklist / patch propose 输出验证清单 | Phase 10 ✅（MCP 出口） |
| 回滚门 | code.rollback / .smartdev/patch_backups/ 备份 | Phase 9 ✅ |

这六个门共同构成 Human-Controlled AI Coding Loop 的核心。Phase 11 补上版本提交和发布治理，形成完整闭环。

### 路线图

```
Phase 10  MCP Server v0（能力分发）               ✅ 完成
    ↓
Phase 11  Human-Controlled AI Coding Layer           ✅ 全部完成
    ├── 11A: Git Governance v0（版本治理层 L5）     ✅ 完成
    ├── 11C: Documentation Governance v0           ✅ 完成
    ├── 11D: Collaboration Handoff v0              ✅ 完成
    └── 11B: Guard Skills（安全防护层 L5）          ✅ 完成
    ↓
Phase 12  Model Collaboration Layer（横向 L7，可选后续增强）
    ├── 12A: Policy 配置层（不调用真实 API）
    └── 12B: Router 真实路由（依赖 Phase 10 跑稳）
    ↓
Phase 13  Call Graph（函数级引用分析）
    ↓
Phase 14  FileWatcher / Incremental Sync
```

**接入方式路线图：**

```
现在：   CLI（开发者本地使用）+ MCP Server（外部 AI Agent 调用）— Phase 10 ✅
后续：   IDE / Agent Workflow 集成（作为 AI 编程工具的项目语义与安全执行后端）
```

**技术栈**：Python 3.10+，core 零外部依赖，mcp 为 optional dependency

---

## 2. 当前阶段 — Phase 11 全部完成

> Phase 11A / 11B / 11C / 11D 已全部完成。SmartDev 当前为 standalone 工程协作工具。
> 测试基线：**1925 passed, 1 skipped**（完整环境含 mcp extra）。MCP 工具：**31 个**。
> Phase 12 为可选后续增强（Model Router），非完整性前提。
>
> ### Phase 11 Closeout Step 5：更新入口文档（✅ 完成）
>
> - **`README.md`**：更新为 Phase 11 完成状态（架构/MCP 31/Skill 27/CLI 26/standalone 示例）
> - **`CLAUDE.md`**：更新为 Closeout 后项目规则（分层/L5-L7/协作角色/Phase 12 可选）
>
> ### Phase 11 Closeout Step 4：Standalone 烟测（✅ 完成）
>
> - **`tests/test_standalone_workflow.py`**（新增）：22 tests 覆盖完整 standalone 闭环
> - 验证路径：run new → run report → handoff-* → context → guard run → scope-check
> - 零模型调用、零 MCP、零网络、零 git 依赖 — 纯本地 CLI/core API
>
> ### Phase 11 Closeout Step 3：协作产物契约测试（✅ 完成）
>
> - **`smartdev/core/handoff_review.py`**：新增 agent-output 消费（code-agent-result.md / changed-files.txt / test-report.txt），缺失时优雅降级
> - **`tests/test_handoff_doc.py`**：+2 contract tests — agent-output/code-agent-result.md 存在/缺失时的 doc pack 行为
> - **`tests/test_handoff_review.py`**：+4 contract tests — agent-output 三文件存在/缺失时的 review pack 行为
> - Handoff doc/review 现在能消费 Code Agent 已写回的 agent-output/ 产物，形成闭环
>
> ### Phase 11 Closeout Step 2：收口 MCP 工具数量事实源（✅ 完成）
>
> - **`smartdev/mcp/tools.py`**：新增 `_TOOL_REGISTRY` 集中注册表 + `get_available_tools()`，`handle_version` / `handle_list_tools` 均由此派生
> - **MCP 测试 ×8**：移除散落硬编码 `30`，改为 `len(get_available_tools())` 动态获取
> - 测试函数名去数字化，统一表达为“工具总数应与注册表一致”
> - 新增 MCP 工具时只需在 `_TOOL_REGISTRY` 追加一行；测试不再需要批量改数字
>
> ### Phase 11 Closeout Step 1：文档收口（✅ 完成，509f4ce）

### Phase 1：只读诊断 Agent（✅ 完成）

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

### Phase 2：项目适配器（✅ 完成）

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

### Phase 7：Tree-sitter Multi-language Graph Provider（✅ 完成）

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
1897 passed, 1 skipped — 0 failed
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
| test_mcp_server.py | 17 | MCP Server 骨架 + ping/version/list_tools（Phase 10 Step 1） |
| test_mcp_readonly_tools.py | 19 | 只读 Context 工具 + INDEX_NOT_FOUND 错误路径（Phase 10 Step 2） |
| test_mcp_skill_tools.py | 20 | Skill 工具 + Context 增强路径（Phase 10 Step 3） |
| test_mcp_patch_propose.py | 22 | code_index + patch_propose + change.budget（Phase 10 Step 4） |
| test_mcp_integration.py | 19 | 真实 JSON-RPC over stdio 协议集成测试（Phase 10 Step 5） |

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

### Phase 11A：Git Governance v0（✅ 完成）

目标：补齐 AI 编程闭环的后两步（版本提交 + 发布治理），覆盖交付记录层（L5）。

| Step | 交付物 | 状态 | 新增 tests | 累计 tests |
|------|--------|------|-----------|-----------|
| Step 0 | 设计文档 phase-11-design.md | ✅ 完成 | 0 | 637 |
| Step 1 | core/git.py（GitService + GitPolicy）| ✅ 完成 | 36 | 673 |
| Step 2 | git.status + git.diff.explain（R0）| ✅ 完成 | 57 | 730 |
| Step 3 | git.commit.plan + git.commit.message（R0）| ✅ 完成 | 59 | 789 |
| Step 4 | git.release.plan + git.merge.check（R0）| ✅ 完成 | 56 | 845 |
| Step 5 | git-policy.json 示例文件 + 文档补充 | ✅ 完成 | 0 | 845 |
| Step 6 | git commit / git tag CLI Command（R2）| ✅ 完成 | 28 | 873 |
| Step 7 | MCP 暴露只读 Git 工具（+5 工具，总数 19）| ✅ 完成 | 33 | 906 |

**Phase 11A（Git Governance v0）完成。** 7 步全部交付，906 tests，MCP 工具 14 → 19。

### Phase 11C：Documentation Governance v0（完成）

目标：SmartDev 提供文档一致性检查工具链，高阶模型担任 Doc Steward 角色。

| Step | 交付物 | 状态 | 新增 tests | 累计 tests |
|------|--------|------|-----------|-----------|
| Step 0 | 设计文档 phase-11c-design.md | ✅ 完成 | 0 | 906 |
| Step 1 | Change Manifest 生成 | ✅ 完成 | 54 | 960 |
| Step 2 | Capability Snapshot 导出（skill / cli / mcp）| ✅ 完成 | 53 | 1013 |
| Step 3 | doc.map Skill（R0 只读）| ✅ 完成 | 50 | 1063 |
| Step 4 | doc.consistency Skill（5 条规则）| ✅ 完成 | 39 | 1102 |
| Step 5 | doc.update.plan Skill | ✅ 完成 | 43 | 1145 |
| Step 6 | doc.patch.propose（不落盘）| ✅ 完成 | 40 | 1185 |
| Step 7 | MCP 暴露只读工具（19→21）| ✅ 完成 | 23 | 1208 |

设计文档：[phase-11c-design.md](phase-11c-design.md)

端到端验证：doc.consistency → doc.update.plan → 手动 code-agent-pack → Code Agent 起草 → 人工审阅 → apply。Rule 3 误报修复后，项目自检从 53 个 issue 降至 10 个，high 从 42 降至 0。测试基线：1210 passed, 1 skipped。

### Phase 11D：Collaboration Handoff v0（✅ 完成）

目标：基于 SmartDev run artifacts，把工程事实裁剪成角色化上下文包（code-agent / doc-steward / reviewer），让多模型协作不靠共享聊天记忆。

| Step | 交付物 | 状态 |
|------|--------|------|
| Step 0 | 设计文档 phase-11d-design.md | ✅ 完成 |
| Step 1 | Run Artifact 目录约定 + `smartdev run new` | ✅ 完成 |
| Step 2 | Scope Gate（11D 唯一新增核心）| ✅ 完成 |
| Step 3 | handoff code（≤8k）| ✅ 完成 |
| Step 4 | handoff doc（≤6k，依赖 11C）| ✅ 完成 |
| Step 5 | handoff review（≤10k）+ Role Activation Preamble + run context | ✅ 完成 |
| Step 6 | Agent Output & Review Artifact Protocol | ✅ 完成（6A + 6B）|
| Step 7 | MCP 暴露 handoff pack 工具（21→24）| ✅ 完成 |

边界：11C 生产事实，11D 组装事实给角色消费。先有事实层，再有协作层。
设计文档：[phase-11d-design.md](phase-11d-design.md)

Step 1 验证：`smartdev run new <id>` 可创建 `.smartdev/runs/<id>/task-card.md` 和 `scope.json`；重复 run_id 默认报错，`--force` 显式覆盖；CLI Snapshot 已同步 `smartdev run new`，CLI 命令数 17 → 18。测试基线：1263 passed, 1 skipped。

Step 2 验证：`smartdev run scope-check <id> --changed-files ...` 可读取 `scope.json` 并检查 max_files / denied_paths / protected_paths / outside_scope；CLI Snapshot 已同步 `smartdev run scope-check`，CLI 命令数 18 → 19。测试基线：1301 passed, 1 skipped。

Step 3 验证：`smartdev run handoff-code <id>` 可生成 `.smartdev/runs/<id>/handoff/code-agent-pack.md`；pack 包含任务、scope、Scope Gate 摘要、相关文件、existing patterns、验收标准和禁止项；`changed_files` 优先进入相关文件列表；CLI Snapshot 已同步 `smartdev run handoff-code`，CLI 命令数 19 → 20。测试基线：1344 passed, 1 skipped。

Step 4 验证：`smartdev run handoff-doc <id>` 可生成 `.smartdev/runs/<id>/handoff/doc-steward-pack.md`；pack 聚合 Change Manifest、Diff Summary、Capability Snapshots、Doc Map、Phase Status、Doc Consistency 和 Update Focus；真实项目验证中 Diff Summary 与 Doc Map 均进入 pack；CLI Snapshot 已同步 `smartdev run handoff-doc`，CLI 命令数 20 → 21。测试基线：1361 passed, 1 skipped。

Step 5 验证：`smartdev run handoff-review <id>` 可生成 `.smartdev/runs/<id>/handoff/reviewer-pack.md`；pack 聚合 Risk + Impact、Changed Files、Test Report、Dependency Changes、Security Checklist 和 Git Diff Explain；支持 `--changed-files` / `--target` / `--run-tests`；CLI Snapshot 已同步 `smartdev run handoff-review`，CLI 命令数 21 → 22。测试基线：1375 passed, 1 skipped。

Role Activation 验证：三个 handoff pack（code-agent / doc-steward / reviewer）均在文件头加入角色激活前言（Role Activation Preamble），包含协作架构图、角色职责、第一步指引、输出格式和禁止项；`smartdev run context <id> --role` 可打印对应 pack 到 stdout；`--info` 模式打印元信息；CLI Snapshot 已同步 `smartdev run context`，CLI 命令数 22 → 23。测试基线：1394 passed, 1 skipped。

Step 6 设计：`phase-11d-design.md` 完成重大更新——固定输出回流协议。§4 Run Artifact 扩展加入 `agent-output/`（Code Agent 写回）和 `review/`（Doc Steward 写回）两层，三层职责划分（handoff=输入层 / agent-output=执行层 / review=审查层）；§7 协作流程重写，Human 全程不复制聊天内容，只看 `review/commit-readiness.md` 做决策；§14 新增 Code Agent 输出协议；§15 新增 Doc Steward 输出协议；§8 Step 6 重定义，MCP 工具暴露后移为 Step 7。测试基线：1394 passed, 1 skipped（纯文档）。

Step 6A 验证：`smartdev run new` 在创建 run artifact 时额外创建 `agent-output/` 和 `review/` 子目录，分别放入 `code-agent-result.template.md`（§14）和 `commit-readiness.template.md`（§15）模板文件；test_run_artifact.py 新增 `TestAgentOutputAndReviewDirectories`（6 tests）。CLI 命令数不变（23）。测试基线：1400 passed, 1 skipped。

Step 6B 验证：`smartdev run report <id>` 命令新增，支持 `--changed-files`（写 agent-output/changed-files.txt）/ `--auto-changed-files`（git diff 推断）/ `--tests <cmd>`（写 test-report.txt）/ `--status`（更新 code-agent-result.md Status）；`handoff doc` 扩展消费 `agent-output/code-agent-result.md`（若存在）加入 "Agent Output" 节；CLI Snapshot 同步，命令数 23 → 24。测试基线：1417 passed, 1 skipped。

Step 7 验证：MCP Server 暴露 `smartdev_handoff_code` / `smartdev_handoff_doc` / `smartdev_handoff_review` 三个 handoff pack 工具；三个工具复用已有 core handoff 生成器，只写 `.smartdev/runs/<run_id>/handoff/`，不调用模型、不修改源码；成功 payload 固定包含 `run_id` / `output_path` / `char_count` / `sections` / `skipped` / `note`；MCP 工具清单 21 → 24。测试基线：1436 passed, 1 skipped。

Step 6A 验证：`smartdev run new <id>` 新增强制创建 `agent-output/` 和 `review/` 子目录；`agent-output/code-agent-result.template.md` 遵循 §14 固定结构（Status / Implemented / Changed Files / Tests / Open Questions）；`review/commit-readiness.template.md` 遵循 §15 固定结构（Decision / Required Fixes / Gates / Documentation Status / Suggested Commits）；`--force` 覆盖时模板随 run 目录一起重建。测试基线：1400 passed, 1 skipped。

**当前协作模式：** DeepSeek = Code Agent；Claude/Codex = Doc Steward；SmartDev = Handoff Pack + Gates；Human = Apply / Commit / Release。

**Phase 11 整体路线（全部完成）：** 11A ✅ → 11C ✅ → 11D ✅ → 11B ✅ → Standalone 闭环成立
（Phase 12 为可选后续增强，SmartDev 不依赖 Phase 12 即可作为完整的工程协作工具独立使用）

设计文档：[phase-11-design.md](phase-11-design.md)

目标：把 SmartDev 已有 L1–L4 能力暴露给外部 Agent（Claude / Kiro / Cursor 等），不继续新增底层分析能力。

| Step | 交付物 | 状态 | 新增 tests | 累计 tests |
|------|--------|------|-----------|-----------|
| Step 0 | 执行前设计 | ✅ 完成 | 0 | 540 |
| Step 1 | MCP Server 骨架（ping/version/list_tools）| ✅ 完成 | 17 | 557 |
| Step 2 | 只读 Context 工具（search/impact/map/validate）| ✅ 完成 | 19 | 576 |
| Step 3 | Skill 工具接入（repo_scan/risk_check/arch/plan/qa）| ✅ 完成 | 20 | 596 |
| Step 4 | code_index（CACHE_WRITE）+ patch_propose（PATCH_PROPOSE）| ✅ 完成 | 22 | 618 |
| Step 5 | 真实协议集成测试 + Kiro mcp.json 配置 | ✅ 完成 | 19 | 637 |

**Phase 10 完成。14 个工具全部实现，637 tests 通过，1 skipped。**

关键设计决策落地：

- `patch_propose` 新增 `diff_explain`（确定性摘要）+ `safety_note`（明确不落盘）+ `change.budget`（`max_files` 参数）
- 所有 Context 工具无索引时返回 `INDEX_NOT_FOUND` + `suggested_tool`，引导外部 Agent 先建索引
- 集成测试用 subprocess 走完整 JSON-RPC over stdio 协议，验证 MCP 行为与真实 Agent 一致
- Kiro 配置已写入 `~/.kiro/settings/mcp.json`，SmartDev 可直接在 Kiro 里调用

14 个工具权限分层：

| 权限层 | 数量 | 工具 |
|--------|------|------|
| READ | 11 | ping / version / list_tools / code_search / code_impact / project_map / graph_validate / repo_scan / risk_check / architecture_map / task_plan / qa_checklist |
| CACHE_WRITE | 1 | code_index（只写 .smartdev/，不改源码）|
| PATCH_PROPOSE | 1 | patch_propose（diff + patch_id，不落盘）|
| WRITE_CODE | 0 | patch_apply 暂不暴露（写盘确认机制待 Phase 11 重新设计）|

能力边界：
- ✅ stdio transport，single project per server instance
- ✅ 优雅降级：所有 Context 工具在无索引时返回 INDEX_NOT_FOUND + suggested_tool
- ✅ Kiro mcp.json 已配置（~/.kiro/settings/mcp.json），当前会话已验证可用
- ❌ WRITE_CODE（patch_apply）：v0 不暴露
- ❌ Git 执行工具：Phase 11 范围

设计文档：[phase-10-design.md](phase-10-design.md)

### Phase 6.3B/C（后续可选）

### 后续规划

**Phase 11：Human-Controlled AI Coding Layer（下一阶段）**

目标：把 AI 编程从"改完了"推进到"交付可审查"，覆盖完整闭环的后两步（版本提交 + 发布治理）。分为两个子阶段并行设计。

**Phase 11A：Git Governance v0（版本治理层 L5）**

| Skill / Command | 类型 | 说明 |
|----------------|------|------|
| `git.status` | R0 只读 Skill | 当前分支 / dirty files / staged files / 最近提交 |
| `git.diff.explain` | R0 只读 Skill | 解释 diff：每个文件改了什么 / 是否有无关改动 / 是否需要拆 commit |
| `git.commit.plan` | R0 只读 Skill | 把当前 diff 拆成建议 commit + Conventional Commit message |
| `git.release.plan` | R0 只读 Skill | 根据 CHANGELOG / commits / version 文件判断 semver bump |
| `git.merge.check` | R0 只读 Skill | 合并前检查：测试 / CHANGELOG / protected path / patch backup |
| `git.commit` | R1 执行 Command | 显式 `--apply` 才写 Git 历史，不自动执行 |
| `git.tag` | R1 执行 Command | 显式 `--apply` 才打 tag，不自动执行 |

永久禁止自动执行：`git push` / `git rebase` / `git reset` / `git merge`（高风险，留给人工）

Git Governance 核心设计原则：
- Skill 负责"判断和建议"，Command 负责"显式执行"
- `code.apply` 和 `git commit` 必须分开，apply 不自动 commit
- 支持 `.smartdev/git-policy.yaml` 配置保护分支 / commit 规范 / 危险操作禁止项

**Phase 11B：Guard Skills（安全防护层 L5，✅ 完成）**

设计文档：[phase-11b-design.md](phase-11b-design.md)

Step 0 验证：`docs/phase-11b-design.md` 已创建，明确 Guard Skills v0 定位、5 个确定性 Guard、Step 1–7 实施路线、统一输出结构、与 `scope_gate` / `git.diff.explain` / `doc.map` 的边界，以及“不接外部扫描器、不调用模型”的硬约束。测试基线：未运行（纯设计文档）。

Step 1 验证：`change.budget` Guard Skill 已实现；新增 `smartdev/core/guard_budget.py` 规则引擎、`smartdev/skills/change_budget/skill.py` + `skill.yaml`、`tests/test_guard_budget.py`，并在 `smartdev/skills/__init__.py` 注册。规则覆盖 file_count / line_count / schema_change / per_file_limit；支持显式输入运行，无 git 依赖，R0 只读。测试基线：1496 passed, 1 skipped。

Step 2 验证：`dev.guard` Guard Skill 已实现；新增 `smartdev/core/guard_dev.py` 规则引擎、`smartdev/skills/dev_guard/skill.py` + `skill.yaml`、`tests/test_guard_dev.py`，并在 `smartdev/skills/__init__.py` 注册。规则覆盖 mass_refactor / protected_path_hit / unrelated_change / test_deletion / config_in_code / forbidden_file_modification / large_commit；支持显式输入运行，无 git 依赖，R0 只读。测试基线：1584 passed, 1 skipped。

Step 3 验证：`dependency.guard` Guard Skill 已实现；新增 `smartdev/core/guard_dependency.py` 规则引擎、`smartdev/skills/dependency_guard/skill.py` + `skill.yaml` + `__init__.py`、`tests/test_guard_dependency.py`，并在 `smartdev/skills/__init__.py` 注册。规则覆盖 dependency_added / dependency_removed / dependency_version_changed / manifest_added / manifest_removed / lock_not_updated；支持 pyproject.toml（tomllib 优先 + 行解析降级）、package.json（json）、go.mod（行解析）、requirements.txt（行解析）4 种 manifest 格式；lock 文件同步检查支持 poetry.lock / uv.lock / package-lock.json / pnpm-lock.yaml / yarn.lock / go.sum；外部工具建议（pip-audit / npm audit / govulncheck / semgrep）只输出不执行。支持显式输入运行（changed_files / diff_content / manifest_before / manifest_after / lock_files_changed），无 git 依赖，R0 只读；unified diff 中 manifest 新增/删除（`/dev/null`）也会触发 manifest_added / manifest_removed。测试基线：1683 passed, 1 skipped。

Step 4 验证：`security.review` Guard Skill 已实现；新增 `smartdev/core/guard_security.py` 规则引擎、`smartdev/skills/security_review/skill.py` + `skill.yaml` + `__init__.py`、`tests/test_guard_security.py`，并在 `smartdev/skills/__init__.py` 注册。规则覆盖 input_validation / path_traversal / command_injection / sensitive_data / hardcoded_secrets / eval_exec 六类确定性安全检查；第一版只做文本/正则模式匹配（不做 AST/数据流分析）；支持显式输入运行（changed_files / diff_content / file_contents），无 git 依赖，R0 只读；敏感数据检测识 OpenAI/GitHub/Slack 等 token 前缀；外部工具建议（bandit / semgrep）只输出不执行。测试基线：1752 passed, 1 skipped。

Step 5 验证：`diff.explain` Guard Skill 已实现；新增 `smartdev/core/guard_diff_explain.py` 规则引擎、`smartdev/skills/diff_explain_patch/skill.py` + `skill.yaml` + `__init__.py`、`tests/test_guard_diff_explain.py`，并在 `smartdev/skills/__init__.py` 注册。规则覆盖逻辑分组 / 测试伴随 / 依赖匹配 / 跨模块检测 / 审查顺序建议；与 `git.diff.explain`（仓库级）互补，面向显式传入的 patch 文件列表和 diff 内容；支持 `base_signals` 合并外部既有信号；文件分类覆盖 source/test/doc/manifest/config/core/mcp/other；穿透项目根前缀（smartdev/src/app/lib）进行功能模块分组；risk_hints 覆盖 cross_module_change / dependency_manifest_changed_without_code / missing_related_tests 等 7 种风险信号；零外部依赖，R0 只读。测试基线：1838 passed, 1 skipped。

Step 6 验证：GuardRunner + CLI 入口已实现；新增 `smartdev/core/guard_runner.py` 组合执行层、`smartdev guard run` CLI 命令、`tests/test_guard_runner.py`（21 tests）；修改 `smartdev/cli.py`（新增 guard 命令组 + _cmd_guard_run 处理函数）、`smartdev/core/snapshot.py`（同步 _build_cli_parser）、`tests/test_cli.py`（新增 TestGuardCLI，11 tests）、`tests/test_snapshot.py`（新增 2 tests）。GuardRunner 按固定顺序运行 5 个 Guard，支持 `--select` 过滤、`--json` 输出、`--diff-file`、`--max-files`、`--max-lines`；单个 Guard 异常不崩溃；聚合 overall_passed / per-guard summary / duration_ms / risks / error_count / warning_count / suggested_actions；warning_count 只统计 warning/info 级 violations，不混入 error risks。CLI snapshot 已同步 `smartdev guard run`。测试基线：1871 passed, 1 skipped。

Step 7 验证：MCP Server 暴露 6 个 Guard 工具；新增 `smartdev/mcp/tools.py`（6 个 handler：handle_guard_run / handle_change_budget / handle_dev_guard / handle_dependency_guard / handle_security_review / handle_diff_explain）、`smartdev/mcp/server.py`（6 个 Tool schema + handler 路由注册）、`tests/test_mcp_guard_tools.py`（26 tests）；修改 `smartdev/mcp/tools.py`（handle_version / handle_list_tools 包含 6 个新工具）、8 个现有测试文件（工具总数 24 → 30）。smartdev_guard_run 支持 `--select` 过滤只运行指定 Guard；5 个单 Guard 工具接受和 Skill 一致的显式输入；所有 Guard 为 R0 只读，不依赖 git，不修改任何源文件；MCP 工具总数：24 → 30。测试基线：1897 passed, 1 skipped。

| Skill | 说明 |
|-------|------|
| `dev.guard` | 检查本轮任务是否违反 AI 编程硬规则（大规模重构 / 越过 protected_paths / 超过 max_files） |
| `dependency.guard` | 检测 package.json / pyproject.toml / go.mod 是否新增依赖，输出依赖审查报告 |
| `security.review` | 对 patch 或受影响文件做安全 checklist（输入校验 / 路径穿越 / 命令执行 / 敏感数据等） |
| `change.budget` | 作为 patch.propose / patch.apply 的参数约束（max_files / max_lines / allow_schema_change 等） |

第一版不接外部静态扫描工具，只做确定性 checklist。有工具（bandit / npm audit / semgrep）时调用，无工具时输出建议命令。

**Phase 11 完成后 MCP 扩展**

Phase 11 完成后，MCP 可扩展增加只读 Git 工具：
- `smartdev_git_status` / `smartdev_git_diff_explain` / `smartdev_git_commit_plan` / `smartdev_git_release_plan`
- 不暴露：`git.commit` / `git.push` / `git.merge`（执行类操作永远不进 MCP）

---

**Phase 12：Model Collaboration Layer（可选后续增强，非完整性前提）**

> SmartDev 当前已可作为 standalone 工程协作工具独立使用：本地 CLI、run artifact / handoff、GuardRunner、Doc Governance、MCP 工具（31 个）、Git 提交建议/治理。Phase 12 为可选增强——自动 Model Router 和 Policy 配置。

SmartDev 不绑定某一个模型，而是把不同模型都纳入同一套项目上下文、任务边界、风险控制和验收流程里。Phase 12 为可选增强，分两步实现。

**Phase 12A：Model Collaboration Policy（配置层，不调用真实 API）**

| 模块 | 说明 |
|------|------|
| Model Registry | 多模型配置（provider / role / strengths / weaknesses / max_risk） |
| Capability Profile | 模型能力画像（适合的任务类型 / 不适合的场景） |
| Task Router | 任务类型 → 推荐模型/模式的映射规则 |
| Output Contract | 统一输出结构约束（understanding / scope / affected_files / risk_level / patch_plan / validation / rollback） |
| Risk Policy | 模型可处理的最高风险等级 / 是否需要二次 review / 是否必须人确认 |

核心原则：
- 工具能确定性完成的（搜索 / 影响分析 / 路径安全），不交给模型
- 模型只处理解释、规划、生成候选方案和 review
- 输出不符合 Output Contract，不能进入下一阶段，不能生成 patch
- 第一版是纯配置层，不调用真实模型 API

配置示例（`.smartdev/model-policy.yaml`）：
```yaml
models:
  claude-sonnet:
    role: reasoning
    strengths: [architecture, requirement_clarify, diff_explain, security_review]
    max_risk: R2
  local-small:
    role: cheap_worker
    strengths: [simple_patch_propose, test_stub, regex_replace]
    max_risk: R1

policy:
  R0: { model_review_required: false, human_confirm_required: false }
  R1: { model_review_required: false, human_confirm_required: true }
  R2: { model_review_required: true,  human_confirm_required: true }
  R3: { model_review_required: true,  human_confirm_required: true, apply_allowed: false }
```

**Phase 12B：Model Router（路由层，真实模型调用）**

依赖 Phase 12A 的规则层 + Phase 10 MCP 跑稳后实施。

| 能力 | 说明 |
|------|------|
| `select_model(task)` | 根据任务类型和风险选择模型 |
| `validate_output_contract(output)` | 校验模型输出是否符合契约 |
| `handoff_to_patch_propose()` | 契约通过后移交 SmartDev Patch Gate |
| `request_second_review()` | R2/R3 任务请求二次模型 review |

不做（Phase 12 范围内）：自动多模型辩论 / Planner-Coder-Reviewer 全自动流水线 / 模型自动 apply / 模型自动 commit / 跨模型长期记忆 / 复杂 agent swarm

---

**Phase 13：Call Graph（函数级引用分析）**

从 module-level impact 升级到 symbol-level impact。当前 SmartDev 知道"A 文件 import 了 B 模块"，但不知道"A.foo() 调用了 B.bar()"。

| Step | 任务 |
|------|------|
| Step 0 | 设计确认，限定首批语言和边界 |
| Step 1 | Python call graph 试点（`ast.Call`） |
| Step 2 | JS/TS call graph 试点（Babel `CallExpression`） |
| Step 3 | Go call graph 试点（Tree-sitter AST） |
| Step 4 | `relations` 表新增 `calls` 类型 |
| Step 5 | `ImpactAnalyzer` 支持 function-level reverse lookup |
| Step 6 | `project.map` / `graph.validate` 支持 call graph 摘要和校验 |
| Step 7 | 真实项目验证 |

不做：完整类型推断 / 跨语言调用解析 / 动态调用推断 / LSP 级重构 / 承诺 100% 精确

---

**Phase 14：FileWatcher / Incremental Sync（持续同步）**

让 SmartDev 从"手动 `smartdev index`"升级为"文件变化 → 自动增量更新索引"。

| Step | 任务 |
|------|------|
| Step 0 | 设计确认，决定 watchdog 还是平台原生方案，是否 optional dependency |
| Step 1 | 增量索引 API：单文件 reindex / delete / update |
| Step 2 | 文件变更检测（watchdog 或 FSEvents/inotify） |
| Step 3 | debounce：避免保存一次触发多次重建 |
| Step 4 | watcher 状态报告：last_indexed / changed_files / errors |
| Step 5 | `graph.validate` 增量校验 |
| Step 6 | MCP / CLI 暴露 watcher 状态 |
| Step 7 | 真实项目长时间运行验证 |

不做（Phase 13 范围内）：daemon 常驻进程 / 自动 apply / 自动修复 / 大型任务调度

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
| §3.3 每步可验证 | ✅ | 637 个测试 |
| §3.4 不扩大范围 | ✅ | |
| §3.5 文档同步更新 | ✅ | 本文档即为证明 |
| §3.6 每步提交 git | ✅ | 25+ commits |
| §3.7 边讲边做 | ✅ | 开发过程同步解释原理 |
| §4 禁止行为 #9 | ✅ | 本文档即为证明 |
| §6 执行前输出 | ✅ | reporter.py 已实现 |
| §7 执行后输出 | ✅ | reporter.py 已实现 |
| §11 风险等级 | ✅ | Risk Controller 已实现 |
| §12 方案分级 | ✅ | task.plan 已实现 |
