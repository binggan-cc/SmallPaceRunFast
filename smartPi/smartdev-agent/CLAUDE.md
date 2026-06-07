# CLAUDE.md — SmartDev Agent 项目规则

本文件定义 Claude Code 在此项目中必须遵守的行为规则。
来源：`smartPi/docs/smartdev-agent-protocol.md` + `smartPi/docs/smartdev-agent-core-spec.md`。

---

## 项目概况

SmartDev Agent 是一个项目开发与仓库改进 AI Agent。
技术栈：Python 3.10+，零外部依赖。
架构：四层（Core Runtime → Workflow → Skill → Project Adapter）。

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
│   ├── context/       # 语义项目上下文（index_store, artifact_extractor, ...）
│   ├── detectors/     # 检测器（tech_stack, docs_status, entrypoints, ...）
│   ├── skills/        # Skill（repo.scan, code.search, code.impact, ...）
│   ├── adapters/      # 项目适配器（JSON）
│   ├── models.py      # 核心数据模型
│   └── cli.py         # CLI 入口
├── tests/             # 测试（386 tests）
├── docs/              # 开发进度、Phase 6 技术文档
├── pyproject.toml     # 项目配置
└── CHANGELOG.md       # 变更记录
```

---

## 当前阶段

Phase 6.3 — JS/TS Parser Provider v1（已完成，已冻结）

SmartDev 已具备基于 Node + Babel Parser 的 JS/TS/JSX/TSX 高置信度结构提取能力。
Node bridge 为 optional dependency — 有 Node 时自动启用（confidence=0.95），无 Node 时静默 fallback 到 regex（confidence=0.55）。
当前能力边界为 **module-level impact analysis**，不承诺完整符号级引用分析、函数调用图或多语言精确解析。

已完成：
- ✅ Phase 1-5：10 Skill + Workflow + Adapter
- ✅ Phase 6-MVP：SQLite 索引 + artifact 提取 + search + impact
- ✅ Phase 6.2：Code Intelligence v1（Python AST + import relations + project.map + graph.validate）
- ✅ Phase 6.3 Step 0：JS/TS Parser Provider 执行前设计
- ✅ Phase 6.3 Step 1：Node bridge 骨架（@babel/parser + JSONL 协议）
- ✅ Phase 6.3 Step 2：Python NodeBridgeExtractor 集成（子进程单例 + 三层 fallback）
- ✅ Phase 6.3 Step 3：JS/TS import relations + 全链路集成验证（7 种 ES module 模式）
- ✅ Phase 6.3 Step 4.1：排除 .d.ts 文件避免 artifact 膨胀
- ✅ Phase 6.3 Step 4.2：JS/TS import target 归一化（code:module:{path}）
- ✅ Phase 6.3 Step 5：tsconfig paths alias 解析（@/foo → src/foo）
- ✅ Phase 6.3 Step 3 补充：磁盘 fixture 全链路验证（tests/fixtures/js_ts_project/）

正在进行：

### Phase 7 Step 0 — Tree-sitter Multi-language Graph 设计确认
- 设计文档：[phase-7-design.md](docs/phase-7-design.md)
- Tree-sitter 作为 **optional multi-language Provider**，不替换 Python AST / NodeBridge
- 首批试点：Go（单语言），Python tree-sitter binding
- 复用现有 Provider 接口 + CodeSymbol / ImportRecord

### Phase 6.3B/C（后续可选）
- TypeScript Compiler API 增强（tsconfig 感知类型级别解析）
- Vue SFC / Svelte script 块抽取（Phase 6.3C）

---

## 参考文档

| 文档 | 路径 | 职责 |
|------|------|------|
| 执行协议 | `smartPi/docs/smartdev-agent-protocol.md` | 行为约束 |
| 核心规格 | `smartPi/docs/smartdev-agent-core-spec.md` | 能力定义 |
| 总览文档 | `smartPi/docs/smartdev-agent-v2.md` | 文档索引 |
| 测试用例 | `smartPi/docs/smartdev-test-cases.md` | 验收标准 |
| Phase 6 设计 | `smartPi/smartdev-agent/docs/next-phase-code-intelligence.md` | 技术设计 |
