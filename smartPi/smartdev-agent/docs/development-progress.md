# SmartDev Agent 开发进度

> 最后更新：2026-06-06
> 当前阶段：Phase 6-MVP — Code Intelligence v0

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

### Phase 6.2：Code Intelligence v1（进行中）

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
- ✅ Module artifact + imports relation（去重写入）
- ✅ ImpactAnalyzer 消费 imports relation（reverse lookup）
- ✅ symbol query fallback 到 module-level impact（relation_scope=module）
- ✅ project.map 导出（JSON + Markdown）
- ✅ graph.validate 校验（6 类检查）
- ❌ 不支持精确符号级引用分析（需 Tree-sitter）
- ❌ 不支持函数调用图（需完整 call graph）
- ❌ 不支持 JS/TS 高置信度解析（当前为 regex fallback，confidence=0.55）

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
310 passed — 0 failed
```

| 测试文件 | 数量 | 覆盖模块 |
|---------|------|---------|
| test_skill_base.py | 8 | Skill 基类 + 自动注册 |
| test_detectors.py | 14 | 五个检测器 |
| test_repo_scan.py | 9 | repo.scan Skill |
| test_risk_controller.py | 14 | Risk Controller |
| test_reporter.py | 9 | 执行前/后模板 |
| test_task_plan.py | 10 | task.plan Skill |
| test_cli.py | 7 | CLI 入口 |
| test_architecture_map.py | 11 | architecture.map Skill |
| test_token_audit.py | 10 | token.audit Skill |
| test_risk_check.py | 11 | risk.check Skill |
| test_qa_checklist.py | 11 | qa.checklist Skill |
| test_adapter.py | 14 | 项目适配器系统 |
| test_doc_generate.py | 11 | doc.generate Skill |
| test_patch.py | 11 | Patch 数据模型 |
| test_code_patch.py | 9 | code.patch Skill |
| test_workflow.py | 6 | Workflow Engine |
| test_index_store.py | 26 | SQLite 存储层（Phase 6-MVP） |
| test_project_index.py | 7 | 项目索引门面类（Phase 6-MVP） |
| test_artifact_extractor.py | 15 | Artifact 提取器（Phase 6-MVP） |
| test_code_search.py | 7 | code.search Skill（Phase 6-MVP） |
| test_code_impact.py | 7 | code.impact Skill（Phase 6-MVP） |
| test_structure_extractor.py | 28 | 多语言结构提取 Provider（Phase 6.2） |
| test_import_relations.py | 19 | Import 关系构建（Phase 6.2） |
| test_impact_import_relations.py | 12 | ImpactAnalyzer import 分析（Phase 6.2） |
| test_project_map.py | 9 | 项目地图导出（Phase 6.2） |
| test_graph_validator.py | 15 | 图谱校验（Phase 6.2） |

---

## 6. 已知问题

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | risk.check 关键词匹配是短语匹配，中文语序灵活导致漏匹配（如"重构目录"≠"目录重构"） | 中 | 待优化 |
| 2 | code.patch 生成的是占位符补丁，非真实代码变更 | 低 | 待 LLM 增强 |
| 3 | 适配器用 JSON 格式，agent.md 设计的是 YAML | 低 | 可迁移 |

---

## 7. 下一步

### Phase 6.2：Code Intelligence v1（后续）

- [ ] Tree-sitter 多语言解析（Python AST / TS parser）
- [ ] 完整调用图 / 引用解析
- [ ] `project.map` 导出
- [ ] `graph.validate` 校验
- [ ] CodeGraph 适配器（可选增强）
- [ ] ContextBuilder 完善（给 LLM 提供结构化上下文）

### Phase 7：Safe Patch Agent

- [ ] code.patch 真实实现（替换占位符）
- [ ] 影响分析驱动的风险评估
- [ ] 自动验证（测试 + lint）

### 优化项

- [ ] risk.check 关键词匹配优化（单词匹配 / 分词）
- [ ] 增加 FileWatcher / 增量同步

---

## 8. 协议合规状态

| 条款 | 状态 | 说明 |
|------|------|------|
| §3.1 先分析后修改 | ✅ | |
| §3.2 小步快跑 | ✅ | |
| §3.3 每步可验证 | ✅ | 227 个测试 |
| §3.4 不扩大范围 | ✅ | |
| §3.5 文档同步更新 | ✅ | 本文档即为证明 |
| §3.6 每步提交 git | ✅ | 11 个 commit |
| §3.7 边讲边做 | ✅ | 开发过程同步解释原理 |
| §4 禁止行为 #9 | ✅ | 本文档即为证明 |
| §6 执行前输出 | ✅ | reporter.py 已实现 |
| §7 执行后输出 | ✅ | reporter.py 已实现 |
| §11 风险等级 | ✅ | Risk Controller 已实现 |
| §12 方案分级 | ✅ | task.plan 已实现 |
