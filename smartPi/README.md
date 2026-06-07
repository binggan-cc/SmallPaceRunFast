# SmartDev Agent

> **SmartDev 是一个面向真实软件项目的本地开发智能层。**
> 它通过项目语义索引、影响分析、任务规划和安全 Patch，把代码仓库从"文件集合"变成 AI Agent 可查询、可判断、可安全修改的项目系统。

---

## 这个项目是什么

SmartDev 不是"又一个写代码 Agent"，而是一个面向真实项目开发的**本地项目智能层**：

```
SmartDev = 项目语义图谱 + Skill 执行层 + 风险控制 + 安全 Patch + 版本治理 + 模型协作控制 + MCP 工具出口
```

它的目标不是替代 Claude、Codex、Kiro、Cursor，也不是绑定某一个模型，而是**把不同模型都纳入同一套项目上下文、任务边界、风险控制和验收流程里**。

更准确的定义：**模型无关的 AI 编程协作控制层。**

---

## 核心设计原则：Human-Controlled AI Coding Loop

AI 编程真正的风险，不是 AI 写不出代码，而是**人失去对代码的理解权、判断权和验收权**。

SmartDev 不是让 AI 写得更快，而是把 AI 编程约束成：

```
小步改动 → 可解释 → 可评估影响 → 可测试 → 可回滚 → 可审计 → 可交付
```

这通过六个门来保障：

| 门 | 对应能力 |
|----|---------|
| 理解门 | `code.index` / `code.search` / `project.map` / `architecture.map` |
| 影响门 | `code.impact` / `graph.validate` |
| 风险门 | `risk.check`（含 impact 增强）/ `RiskController` |
| 权限门 | R0–R3 风险等级 / `protected_paths` / `patch.apply` 显式确认 |
| 测试门 | `qa.checklist` / patch propose 输出验证清单 |
| 回滚门 | `code.rollback` / `.smartdev/patch_backups/` 备份 |

完整的 AI 编程闭环（SmartDev 已覆盖前四步，Git 治理层补上后两步）：

```
理解项目 → 判断影响 → 安全修改 → 测试验收 → 版本提交 → 发布治理
```

**模型无关原则**

SmartDev 不解决"哪个模型最聪明"，而是解决"不管用哪个模型，如何让它在可理解、可判断、可验证、可回滚的工程流程里工作"。不同模型能力参差不齐，SmartDev 的作用是把模型从"直接决定项目怎么改的人"，降级为"在 SmartDev 工程规则下工作的协作者"：

- 工具能确定性完成的（搜索 / 影响分析 / 路径安全），不交给模型
- 模型只处理解释、规划、生成候选方案和 review
- 所有模型输出必须经过同一套风险门和验收流程
- 任何模型都不能绕过 Patch Gate 直接修改源码

---

## 为什么做这个

最早不是为了做抽象平台，而是从真实开发痛点里长出来的：

- 项目想法很多、页面很多、代码逐渐变散
- 设计 token 不统一，Side Panel / Demo / Server / Docs 之间状态不一致
- 每次改动前不知道影响范围
- AI 能写代码，但人很难判断它改得是否安全
- 项目越做越散，没有可持续迭代机制

核心问题是：**如何在人和 AI 编码工具之间，增加一层"项目理解 + 风险控制 + 安全执行"的本地智能层。**

---

## 分层架构

```
L1  诊断层      repo.scan / tech_stack / docs_status / entrypoints
L2  规划层      task.plan / architecture.map / risk.check / qa.checklist
L3  语义层      code.index / code.search / code.impact / project.map / graph.validate
               多语言 Provider：Python(1.0) / JS-TS(0.95) / Go(0.98)
L3a Skill接入   risk.check ← impact
               architecture.map ← index
               task.plan ← impact
L4  执行层      code.patch(propose) → code.apply → code.rollback
L5  版本治理层  git.status / git.diff.explain / git.commit.plan / git.release.plan（Phase 11）
L6  外部接入层  MCP Server → Claude / Kiro / Cursor / Codex（Phase 10）
L7  模型协作层  model registry / task router / output contract / risk policy（Phase 12，横向）
```

L7 是横向调度层，不替代任何现有层，而是决定：这个任务用哪个模型？需要哪些 SmartDev 工具？输出必须满足什么结构？是否允许进入 patch propose？

内部结构：

```
用户输入 → Core Runtime → Workflow → Skill Registry → Skill → SkillResult
                          ↕
                    Project Adapter
                          ↕
               Context Layer（语义图谱 + 影响分析）
                          ↕
               Safe Patch（propose / apply / rollback）
                          ↕
               Git Governance（commit.plan / release.plan）（Phase 11）
```

---

## 当前能力（Phase 1–9 已完成，540 tests）

### Context Layer：项目语义层

把项目从"文件集合"变成可查询结构：

| 能力 | 说明 |
|------|------|
| `code.index` | SQLite + FTS5 语义索引 |
| Artifact 提取 | 文件 / 函数 / 类 / 模块 / import / endpoint / token / docs 等 8 种工件 |
| Import relations | 模块级 import 关系 + reverse lookup |
| `code.search` | 全文搜索 artifact / 文件 / 符号 |
| `code.impact` | 基于 imports relation 的影响范围分析（反向依赖） |
| `project.map` | JSON + Markdown 项目地图 |
| `graph.validate` | 图谱健康检查（6 类校验） |

### 多语言 Provider

| 语言 | Provider | Confidence |
|------|----------|-----------|
| Python | `PythonAstExtractor` | 1.0 |
| JavaScript / TypeScript | `NodeBridgeExtractor` (Babel) | 0.95 |
| Go | `TreeSitterProvider` | 0.98 |
| JS/TS fallback | `JsTsRegexFallbackExtractor` | 0.55 |

### Skill 层（Context 驱动）

Skill 不再是静态模板，而是由项目语义图谱驱动：

| Skill | 增强方式 |
|-------|---------|
| `risk.check` | 结合 impact 做影响范围判断，`final_risk = max(keyword, impact)` |
| `architecture.map` | 复用 index relations 构建多语言依赖图 |
| `task.plan` | 标注真实受影响文件，不只是模板方案 |
| `qa.checklist` | 结合受影响文件给验证建议 |

### Safe Patch 执行层

| 操作 | 风险 | 说明 |
|------|------|------|
| `code.patch`（propose） | R1 | 生成 find-replace diff + patch_id，不落盘 |
| `code.apply` | R2/R3 | 写盘，备份 + hash 校验 + 路径安全 + R3 强确认 |
| `code.rollback` | R1 | 从备份恢复 |

---

## 快速开始

```bash
cd smartPi/smartdev-agent

# 安装
pip install -e .

# 运行测试
python -m pytest tests/ -q         # 540 passed

# 对项目建立语义索引
python -m smartdev index -p /path/to/project

# 搜索文件和工件
python -m smartdev search "token" -p /path/to/project

# 分析变更影响范围
python -m smartdev impact "models.py" -p /path/to/project

# 运行完整工作流（诊断 → 规划 → 清单）
python -m smartdev run -p /path/to/project --task "统一设计 token"

# 生成 patch 提案（不落盘）
python -m smartdev patch -p /path/to/project --find "#22C55E" --replace "var(--color-accent)"
```

---

## 典型使用场景

### 1. 接手已有仓库

```bash
smartdev scan -p /path/to/project      # 技术栈 / 入口 / 文档状态
smartdev index -p /path/to/project     # 建立语义索引
smartdev map -p /path/to/project       # 导出项目地图
```

### 2. 改代码前做影响分析

```bash
smartdev impact "tokens.css" -p .      # 哪些文件依赖这个？
smartdev impact "service.py" -p .      # 改 service 会影响什么？
```

### 3. 安全做小步修改

```bash
# 生成 patch 提案，显示影响范围和风险
smartdev patch -p . --find "#22C55E" --replace "var(--color-accent)"

# 确认后应用（R2，需显式 --apply）
smartdev apply -p . --patch-id <id>

# 出问题可回滚
smartdev rollback -p . --patch-id <id>
```

### 4. 版本治理（Phase 11 Git Governance）

```bash
# 查看当前改动状态和是否有无关修改
smartdev git-status -p .

# 解释当前 diff，拆建议 commit
smartdev git-commit-plan -p .

# 生成 Conventional Commit message
smartdev git-commit-message -p .

# 检查是否适合合并
smartdev git-merge-check -p .

# 版本发布规划（CHANGELOG / semver bump）
smartdev git-release-plan -p .
```

Git 执行命令（`commit --apply` / `tag --apply`）始终需要显式确认，`push` / `rebase` / `reset` 不在自动化范围内。

### 5. 给 AI Agent 提供上下文（Phase 10 MCP）

```bash
# 启动 MCP Server，供外部 Agent（Claude / Kiro / Cursor）调用
smartdev mcp -p /path/to/project
```

外部 Agent 可查询：这个符号在哪里？这个模块被谁依赖？改这里风险多大？给我一个 patch 提案。
MCP v0 只开放 READ / CACHE_WRITE / PATCH_PROPOSE，不开放 apply 和 Git 执行类操作。

---

## 目录结构

```
smartPi/
├── README.md                              ← 你在这里
│
├── smartdev-agent/                        ← Python CLI + MCP Server 实现
│   ├── pyproject.toml                     ← 项目元数据（core 零外部依赖，mcp 为 optional）
│   ├── smartdev/
│   │   ├── models.py                      ← 核心数据模型（RiskLevel / SkillResult / ProjectContext）
│   │   ├── cli.py                         ← CLI 入口（scan/plan/index/search/impact/patch/apply/rollback/mcp）
│   │   ├── core/                          ← 运行时（risk / reporter / adapter / workflow / patch）
│   │   ├── context/                       ← 语义上下文层
│   │   │   ├── index_store.py             ← SQLite + FTS5 存储层
│   │   │   ├── project_index.py           ← 项目索引门面类
│   │   │   ├── artifact_extractor.py      ← 8 种工件类型提取
│   │   │   ├── impact_analyzer.py         ← 影响分析 + import reverse lookup
│   │   │   ├── structure_extractor.py     ← 多语言 Provider 机制
│   │   │   ├── node_bridge.py             ← JS/TS Node + Babel 适配层
│   │   │   ├── tree_sitter_provider.py    ← Go Tree-sitter Provider
│   │   │   ├── tsconfig_resolver.py       ← tsconfig paths alias 解析
│   │   │   ├── project_map.py             ← 项目地图导出（JSON + Markdown）
│   │   │   └── graph_validator.py         ← 图谱健康校验（6 类检查）
│   │   ├── detectors/                     ← 项目检测器（tech_stack / docs_status / entrypoints）
│   │   ├── skills/                        ← 12 个 Skill（含 code.apply / code.rollback）
│   │   ├── mcp/                           ← MCP Server（Phase 10，待实现）
│   │   └── adapters/                      ← 项目适配器（JSON）
│   ├── tests/                             ← 540 tests
│   └── docs/                              ← 开发进度 + Phase 设计文档
│
├── docs/                                  ← 设计文档
└── reference/                             ← 参考资料
```

---

## 开发进度

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1–5 | ✅ | 12 Skill + Workflow + Adapter + 完整迭代闭环 |
| Phase 6-MVP | ✅ | SQLite 索引 + artifact 提取 + search + impact |
| Phase 6.2 | ✅ | Python AST + import relations + project.map + graph.validate |
| Phase 6.3 | ✅ | JS/TS Node bridge + Babel + tsconfig alias（confidence=0.95） |
| Phase 7 | ✅ | Go Tree-sitter Provider（confidence=0.98，真实项目验证） |
| Phase 8 | ✅ | Context Layer ↔ Skill 接入（risk / architecture / plan 消费图谱） |
| Phase 9 | ✅ | Safe Patch（propose / apply / rollback + 备份 / hash校验 / R3确认） |
| **Phase 10** | 🔄 | **MCP Server v0**（设计确认完成，实现待开始） |
| **Phase 11** | 📋 | **Human-Controlled AI Coding Layer**（11A Git Governance + 11B Guard Skills） |
| **Phase 12** | 📋 | **Model Collaboration Layer**（12A Policy + 12B Router，模型无关协作控制） |
| **Phase 13** | 📋 | **Call Graph**（Python ast.Call + JS-TS CallExpression + Go Tree-sitter，函数级影响分析） |
| **Phase 14** | 📋 | **FileWatcher / Incremental Sync**（增量索引 + debounce + watcher 状态报告） |

**测试基线：540 passed, 1 skipped**

---

## 接入方式路线图

```
现在：    CLI（开发者本地使用）
           smartdev index / search / impact / patch / apply / rollback / git-*

Phase 10： MCP Server v0（外部 AI Agent 调用）
           smartdev mcp → Claude / Kiro / Cursor / Codex 直接查询
           只开放：READ / CACHE_WRITE / PATCH_PROPOSE
           模式 A：SmartDev 作为工具提供者，模型路由由外部 Agent 决定

Phase 11： Git Governance + Guard Skills（版本治理 + 安全防护层）

Phase 12： Model Collaboration Layer（横向模型协作控制层）
           12A Policy：model registry / capability profile / task router / output contract
           12B Router：select_model / validate_output_contract / handoff_to_patch
           模式 B：SmartDev 自己管理模型路由（依赖 Phase 10 MCP 跑稳）

后续：     Call Graph（Phase 13）→ FileWatcher（Phase 14）→ IDE 深度集成
```

---

## 开发规范

本项目遵循 [执行协议](docs/smartdev-agent-protocol.md) 开发：

- **边讲边做** — 解释原理和理由，不做黑盒执行
- **运行测试** — `python -m pytest tests/ -q`（540 passed 为基线）
- **提交 git** — 每个可验证步骤完成后立即 commit
- **执行前说明** — 范围 / 风险 / 验收标准
- **执行后总结** — 变更文件 / 关键变更 / 下一步

详细规则见 `smartdev-agent/CLAUDE.md`。

---

## 参考文档

| 文档 | 路径 |
|------|------|
| 执行协议 | `docs/smartdev-agent-protocol.md` |
| 核心规格 | `docs/smartdev-agent-core-spec.md` |
| 开发进度 | `smartdev-agent/docs/development-progress.md` |
| Phase 10 设计 | `smartdev-agent/docs/phase-10-design.md` |
| Code Intelligence 调研 | `smartdev-agent/docs/next-phase-code-intelligence.md` |
