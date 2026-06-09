# CLAUDE.md — SmartDev Agent 项目规则

本文件定义 Claude Code 在此项目中必须遵守的行为规则。
来源：`smartPi/docs/smartdev-agent-protocol.md` + `smartPi/docs/smartdev-agent-core-spec.md`。

---

## 项目概况

**SmartDev 是一个面向真实软件项目的本地开发智能层。**
它通过项目语义索引、影响分析、任务规划和安全 Patch，把代码仓库从"文件集合"变成 AI Agent 可查询、可判断、可安全修改的项目系统。

```
SmartDev = 项目语义图谱 + Skill 执行层 + 风险控制 + 安全 Patch + MCP 工具出口
```

它的目标不是替代 Claude、Codex、Kiro、Cursor，而是给这些 Agent 提供一个可信的本地项目上下文和安全执行能力。

当前协作模式：

```
DeepSeek      = Code Agent
Claude/Codex  = Doc Steward
SmartDev      = Handoff Pack + Gates
Human         = Apply / Commit / Release
```

当 Claude 或 Codex 处理本项目时，默认承担 **Doc Steward** 角色：审查文档与代码能力是否一致、维护 Phase 状态和测试基线、生成文档更新计划或 patch proposal。Doc Steward 不直接改核心源码，不执行 apply / commit / release，不扩大功能范围。

分层架构：

```
L1  诊断层      repo.scan / tech_stack / docs_status / entrypoints
L2  规划层      task.plan / architecture.map / risk.check / qa.checklist
L3  语义层      code.index / code.search / code.impact / project.map / graph.validate
               多语言 Provider：Python(1.0) / JS-TS(0.95) / Go(0.98)
L3a Skill接入   risk.check ← impact / architecture.map ← index / task.plan ← impact
L4  执行层      code.patch(propose) → code.apply → code.rollback
```

技术栈：Python 3.10+，core 零外部依赖（mcp 为 optional dependency）。

## 核心约束（必须遵守）

### 1. 每步提交 git（§3.6，最容易被忽略）

**每个可验证的小步骤完成后，必须立即 `git add + git commit`。**

```
不要累积多步再提交。不要跳过 commit。
每个 commit 对应一个可独立回溯的变更节点。
commit message 遵循 Conventional Commits 格式。
commit 前确认工作区干净（不混入无关文件）。
```

违反此规则 = 违反协议 §4 #16（禁止行为）。

### 2. 标准执行流程 13 步（§5）

每次处理任务必须按顺序执行：

```
1. 接收任务
2. 读取上下文（docs/、现有代码、测试）
3. 项目诊断
4. 问题归类
5. 方案分级（保守 / 推荐 / 深度）
6. 任务拆解
7. 执行前确认（输出 §6 模板）
8. 单步修改
9. 验证回归（python -m pytest tests/ -q）
10. Git 提交
11. 文档更新（CHANGELOG.md、development-progress.md）
12. 变更总结（输出 §7 模板）
13. 下一步建议
```

不允许跳过 7-10-11-12。

### 2a. 每步完成后的强制 Checklist（防止跳过提交）

每当测试全绿（步骤 9 通过）后，**必须在继续任何下一步之前**，逐项确认：

```
□ git add <本步相关文件>
□ git commit -m "<type>(<scope>): <subject>"
□ CHANGELOG.md 新增本步条目
□ development-progress.md 更新测试基线和状态
□ 输出 §7 变更总结
```

**触发条件**（满足任意一项即视为"一步完成"）：
- 一个 Skill 的 skill.py + skill.yaml + tests 全部写完且测试通过
- 一个 core 模块写完且测试通过
- 一个设计文档写完
- 一个 Phase 的某 Step 全部交付物就绪

**严禁行为**：测试通过后直接开始写下一步的代码，不先 commit。

### 3. 执行前必须输出（§6）

每次正式修改代码前，必须输出：

```md
当前任务：...
项目状态：...
修改范围：...
非修改范围：...
风险等级：R0/R1/R2/R3
验收标准：...
```

### 4. 执行后必须输出（§7）

每次完成修改后，必须输出：

```md
完成项：...
修改文件：...
关键变更：...
验证方式：...
遗留问题：...
下一步建议：...
```

### 5. 文档必须同步更新（§3.5）

以下情况必须更新文档：
- 新功能完成 → 更新 CHANGELOG.md + development-progress.md
- Bug 修复 → 记录根因和预防
- 架构调整 → 更新进度文档
- Phase 完成 → 更新版本号和测试计数

### 6. 边讲边做（§3.7）

开发过程中必须解释：
- 为什么选择这个方案（权衡）
- 遇到问题时的排查思路
- 关键代码段的意图和约束

不需要解释：显而易见的语法、框架固定用法。

### 7. 不扩大改动范围（§3.4）

只修改当前任务所需的文件。发现额外问题记录为后续任务，不擅自扩大范围。

---

## 禁止行为（§4）

1. 未诊断就改代码
2. 未说明影响就删文件
3. 未说明原因就替换技术栈
4. 未提供回滚方案就做跨模块重构
5. 一次性修改大量无关文件
6. "顺手优化"改动当前任务之外的逻辑
7. 完成修改后不说明验证方式
8. 修复 Bug 后不记录原因
9. 新增功能后不更新进度文档
10. 验证通过后不提交 git

---

## 开发规范

### 风险等级

```
R0 = 只读/无代码影响 → 自动执行
R1 = 单文件/无跨模块 → 说明后执行
R2 = 多文件/API/UI/数据影响 → 说明风险+回滚方案
R3 = 数据模型/权限/schema/核心协议 → 必须确认后执行
```

### 任务粒度

```
推荐：单文件、单模块、单功能、单次可验证变更
谨慎：多文件重构、数据模型变更、接口结构变化（需先说明影响）
高风险：换技术栈、大规模目录重构、删除核心模块（必须先给方案）
```

### Git 提交格式

```
feat: 新功能
fix: Bug 修复
docs: 文档更新
refactor: 重构
test: 测试
chore: 杂务
```

---

## 测试规范

```bash
# 运行全部测试
cd smartPi/smartdev-agent && python -m pytest tests/ -q

# 运行单个测试文件
python -m pytest tests/test_xxx.py -v

# 验收标准：所有测试通过，无 regressions
```

---

## 项目目录结构

```
smartdev-agent/
├── smartdev/
│   ├── core/          # 运行时（risk, reporter, adapter, workflow, patch）
│   ├── context/       # 语义上下文层（index_store, artifact_extractor, structure_extractor,
│   │                  #   node_bridge, tree_sitter_provider, tsconfig_resolver,
│   │                  #   impact_analyzer, project_map, graph_validator）
│   ├── detectors/     # 检测器（tech_stack, docs_status, entrypoints）
│   ├── skills/        # 22 个 Skill（repo.scan / code.search / code.impact /
│   │                  #   code.patch / code.apply / code.rollback /
│   │                  #   doc.map / doc.consistency / doc.update.plan / doc.generate /
│   │                  #   doc.patch.propose / git.status / git.diff.explain /
│   │                  #   git.commit.plan / git.commit.message / git.release.plan /
│   │                  #   git.merge.check / task.plan / architecture.map /
│   │                  #   risk.check / qa.checklist / token.audit）
│   ├── mcp/           # MCP Server v0（Phase 10 ✅，21 工具，stdio transport）
│   ├── adapters/      # 项目适配器（JSON）
│   ├── models.py      # 核心数据模型
│   └── cli.py         # CLI 入口（18 条命令）
├── tests/             # 测试（1263 passed, 1 skipped）
├── docs/              # Phase 设计文档 + 开发进度
├── pyproject.toml     # 项目配置（core 零依赖，mcp optional）
└── CHANGELOG.md       # 变更记录
```

---

## 当前阶段

Phase 11D Step 1 完成 — Run Artifact 目录约定（21 MCP 工具，1263 tests）

SmartDev 的文档治理层 v0 已全部完成。doc.consistency（5 条规则）、doc.update.plan、doc.patch.propose 上线。MCP Server 21 个工具通过 stdio transport 暴露给外部 Agent（Claude / Kiro / Cursor / Codex）。

Phase 11C 端到端验证已完成：doc.consistency → doc.update.plan → code-agent-pack → Code Agent 起草 → 人工审阅 → apply。Rule 3 capability_overpromise 已按真实项目误报修复：只用最新设计文档的 ❌ 声明、只检查 README.md、使用 `_RULE3_STOPWORDS` 过滤通用词，宁可漏报不要误报。

已完成：
- ✅ Phase 1-5：12 Skill + Workflow + Adapter
- ✅ Phase 6-MVP / 6.2 / 6.3 / 7：多语言语义索引（Python/JS-TS/Go）
- ✅ Phase 8：Context Layer ↔ Skill 接入（risk / architecture / plan 消费图谱）
- ✅ Phase 9：Safe Patch（propose / apply / rollback + 备份 / hash校验 / R3确认）
- ✅ Phase 10：MCP Server v0（21 工具：READ×18 + CACHE_WRITE×1 + PATCH_PROPOSE×1）
- ✅ Phase 11A：Git Governance v0（git.status / diff.explain / commit.plan / release.plan / merge.check）
- ✅ Phase 11C：Documentation Governance v0（doc.map / doc.consistency / doc.update.plan / doc.patch.propose）
- ✅ Phase 11D Step 1：Run Artifact 目录约定（smartdev run new / task-card.md / scope.json）

**测试基线：1263 passed, 1 skipped**

进行中：

### Phase 11D — Collaboration Handoff v0（Step 1 完成，Step 2 待实现）
- Step 2：Scope Gate（下一步默认从这里开始）
- 11C 生产事实，11D 只组装事实为角色化 context pack
- Code Agent pack 给 DeepSeek；Doc Steward pack 给 Claude/Codex；SmartDev 负责 Handoff Pack + Gates

### Phase 11B — Guard Skills（待开始）
- change.budget / dev.guard / dependency.guard / security.review

### 后续规划
- Phase 12：Model Collaboration Layer（model registry + task router）
- Phase 13：Call Graph（函数级引用分析）
- Phase 14：FileWatcher（增量同步 + .smartdev/index 自动刷新）

---

## 参考文档

| 文档 | 路径 | 职责 |
|------|------|------|
| 执行协议 | `smartPi/docs/smartdev-agent-protocol.md` | 行为约束 |
| 核心规格 | `smartPi/docs/smartdev-agent-core-spec.md` | 能力定义 |
| 总览文档 | `smartPi/docs/smartdev-agent-v2.md` | 文档索引 |
| 测试用例 | `smartPi/docs/smartdev-test-cases.md` | 验收标准 |
| Phase 6 设计 | `smartPi/smartdev-agent/docs/next-phase-code-intelligence.md` | 技术设计 |
