# SmartDev Agent 开发进度

> 最后更新：2026-06-03
> 当前阶段：Phase 1 — 只读诊断 Agent（Python CLI MVP）

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

### Phase 4：Patch 类 Skill（待做）

目标：生成小范围代码修改。

### Phase 5：完整迭代闭环（待做）

目标：一次完成"小任务 → 修改 → 验证 → 总结 → 文档更新"。

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

---

## 5. 测试覆盖

```
139 passed — 0 failed
```

| 测试文件 | 数量 | 覆盖模块 |
|---------|------|---------|
| test_skill_base.py | 8 | Skill 基类 + 自动注册 |
| test_detectors.py | 14 | 三个检测器 |
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

---

## 6. 已知问题

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | Adapter 未转为 YAML 配置格式 | 低 | 待做 |
| 2 | risk.check 关键词匹配是短语匹配，中文语序灵活导致漏匹配（如"重构目录"≠"目录重构"） | 中 | 待优化 |
| 3 | Phase 1 剩余 1 个 Skill 未实现 | 低 | 待做 |

---

## 7. 下一步

### 优先级 1：完成 Phase 1

- [x] `architecture.map` — 架构分析
- [x] `token.audit` — Token 审计
- [x] `risk.check` — 风险检查
- [ ] `qa.checklist` — 验收清单

### 优先级 2：优化风险关键词匹配

- [ ] 将 risk.check 的短语匹配改为单词匹配
- [ ] 考虑引入分词库（如 jieba）提升中文匹配精度

### 优先级 3：开始 Phase 2

- [ ] 创建 SmartFav Adapter YAML
- [ ] 创建 Chrome Extension 通用 Adapter
- [ ] 创建 FastAPI 通用 Adapter

---

## 8. 协议合规状态

| 条款 | 状态 | 说明 |
|------|------|------|
| §3.1 先分析后修改 | ✅ | |
| §3.2 小步快跑 | ✅ | |
| §3.3 每步可验证 | ✅ | 71 个测试 |
| §3.4 不扩大范围 | ✅ | |
| §3.5 文档同步更新 | ✅ | 本文档即为证明 |
| §3.6 每步提交 git | ✅ | 11 个 commit |
| §3.7 边讲边做 | ✅ | 开发过程同步解释原理 |
| §4 禁止行为 #9 | ✅ | 本文档即为证明 |
| §6 执行前输出 | ✅ | reporter.py 已实现 |
| §7 执行后输出 | ✅ | reporter.py 已实现 |
| §11 风险等级 | ✅ | Risk Controller 已实现 |
| §12 方案分级 | ✅ | task.plan 已实现 |
