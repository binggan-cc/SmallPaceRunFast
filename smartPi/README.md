# SmartDev Agent

> 项目开发与仓库改进 AI Agent — 将项目从"想法多、代码散"推进到"目标清、任务可执行、可持续迭代"。

## 目录结构

```
smartPi/
├── README.md                              ← 你在这里
│
├── smartdev-agent/                        ← Python CLI 实现
│   ├── pyproject.toml                     ← 项目元数据，零外部依赖
│   ├── smartdev/
│   │   ├── __init__.py
│   │   ├── models.py                      ← 核心数据模型
│   │   │   ├── RiskLevel (R0-R3)          ← 风险等级枚举
│   │   │   ├── TaskType                   ← 8 种任务类型
│   │   │   ├── SkillResult                ← Skill 统一输出
│   │   │   └── ProjectContext             ← 项目上下文
│   │   ├── detectors/                     ← 项目检测器（Skill 的底层能力）
│   │   │   ├── tech_stack.py              ← 技术栈检测（11 种技术）
│   │   │   ├── docs_status.py             ← 文档状态检测（10 种文档）
│   │   │   └── entrypoints.py             ← 入口文件检测（Python/Node/Extension）
│   │   └── skills/
│   │       ├── __init__.py                ← Skill 注册入口
│   │       ├── base.py                    ← Skill 抽象基类 + 自动注册
│   │       └── repo_scan.py               ← ✅ repo.scan（仓库扫描）
│   └── tests/
│       ├── test_skill_base.py             ← 8 个测试：基类机制
│       ├── test_detectors.py              ← 14 个测试：三个检测器
│       └── test_repo_scan.py              ← 9 个测试：repo.scan Skill
│
├── docs/                                  ← 设计文档
│   ├── smartdev-agent-v2.md               ← 总览索引（入口）
│   ├── smartdev-agent-core-spec.md        ← 核心规格（架构、状态机）
│   ├── smartdev-agent-protocol.md         ← 执行协议（行为约束）
│   ├── agent.md                           ← 提取指南（四层架构）
│   └── smartdev-test-cases.md             ← 测试用例（16 个 TC）
│
└── reference/                             ← 暂存：参考资料
    ├── smartdev-adapter-smartfav.md       ← SmartFav 适配器（已完成）
    └── 参考.md                            ← 外部 Agent 系统调研
```

## 快速开始

```bash
cd smartPi/smartdev-agent
python -m pytest tests/ -v     # 运行测试（31 个）
```

## 架构概览

```
用户输入 → Core Runtime → Workflow → Skill Registry → Skill → SkillResult
                         ↕
                   Project Adapter
```

四层职责：
- **Core Runtime**：调度、状态、权限、风险控制
- **Workflow**：诊断 → 规划 → 执行 → 验证 → 总结
- **Skill**：可复用能力单元，通过 `__init_subclass__` 自动注册
- **Project Adapter**：项目差异隔离（目录、约束、验证清单）

## 当前进度

**Phase 1：只读诊断 Agent（Python CLI MVP）**

| 模块 | 状态 | 测试 | 说明 |
|------|------|------|------|
| `models.py` | ✅ | 8 pass | RiskLevel, TaskType, SkillResult, ProjectContext |
| `skills/base.py` | ✅ | (含上) | Skill 抽象基类 + 自动注册 |
| `detectors/tech_stack.py` | ✅ | 6 pass | 11 种技术检测（Python/Node/Chrome/FastAPI/Vue/React...） |
| `detectors/docs_status.py` | ✅ | 4 pass | 10 种常见文档覆盖率检测 |
| `detectors/entrypoints.py` | ✅ | 4 pass | Python/Node/Chrome Extension 入口检测 |
| `skills/repo_scan.py` | ✅ | 9 pass | 仓库扫描：技术栈 + 入口 + 文档 + 目录树 |
| `skills/repo_diagnose` | 🔲 | — | 项目诊断报告 |
| `skills/architecture_map` | 🔲 | — | 架构分析 |
| `skills/token_audit` | 🔲 | — | Token 审计 |
| CLI 入口 | 🔲 | — | `smartdev diagnose / token-audit / plan` |

## 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据模型 | dataclass | 零依赖，Phase 1 够用 |
| 风险等级 | Enum | 类型安全，IDE 补全 |
| Skill 注册 | `__init_subclass__` | 子类定义即注册，不需要手动维护列表 |
| 检测逻辑 | 独立 detector 层 | 单一职责，可独立测试，可跨 Skill 复用 |
| 技术检测 | 标记文件 | 快速、低开销，准确率够用于诊断场景 |
| 目录树 | 只扫 2 层 | 避免 node_modules 等大目录拖慢扫描 |
