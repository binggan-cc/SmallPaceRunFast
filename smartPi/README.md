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
│   │   ├── cli.py                         ← CLI 入口（scan/plan/index/search/impact）
│   │   ├── core/                          ← 运行时（risk, reporter, adapter, workflow, patch）
│   │   ├── context/                       ← 语义上下文层（Phase 6 新增）
│   │   │   ├── index_store.py             ← SQLite + FTS5 存储层
│   │   │   ├── project_index.py           ← 项目索引门面类
│   │   │   ├── artifact_extractor.py      ← 8 种工件类型提取
│   │   │   ├── impact_analyzer.py         ← 变更影响分析 + import reverse lookup
│   │   │   ├── structure_extractor.py     ← 多语言结构提取（Provider 机制）
│   │   │   ├── project_map.py             ← 项目地图导出（JSON + Markdown）
│   │   │   └── graph_validator.py         ← 图谱健康校验（6 类检查）
│   │   ├── detectors/                     ← 项目检测器
│   │   │   ├── tech_stack.py              ← 技术栈检测（11 种技术）
│   │   │   ├── docs_status.py             ← 文档状态检测（10 种文档）
│   │   │   └── entrypoints.py             ← 入口文件检测
│   │   ├── skills/                        ← Skill（10 个）
│   │   │   ├── base.py                    ← Skill 抽象基类 + 自动注册
│   │   │   ├── repo_scan/                 ← 仓库扫描
│   │   │   ├── task_plan/                 ← 任务规划（三档方案）
│   │   │   ├── architecture_map/          ← 架构分析
│   │   │   ├── token_audit/               ← Token 审计
│   │   │   ├── risk_check/                ← 风险检查
│   │   │   ├── qa_checklist/              ← 验收清单
│   │   │   ├── doc_generate/              ← 文档生成
│   │   │   ├── code_patch/                ← 代码补丁
│   │   │   ├── code_search/               ← 代码搜索（FTS5）
│   │   │   └── code_impact/               ← 影响分析
│   │   └── adapters/                      ← 项目适配器（JSON）
│   ├── tests/                             ← 310 tests
│   └── docs/                              ← 开发文档
│       ├── development-progress.md        ← 开发进度
│       ├── next-phase-code-intelligence.md← Phase 6 设计
│       └── samples/                       ← 示例输出
│           ├── project-map-sample.json
│           ├── architecture-summary-sample.md
│           └── graph-validation-report-sample.md
│
├── docs/                                  ← 设计文档
│   ├── smartdev-agent-v2.md               ← 总览索引
│   ├── smartdev-agent-core-spec.md        ← 核心规格
│   ├── smartdev-agent-protocol.md         ← 执行协议
│   ├── agent.md                           ← 提取指南
│   └── smartdev-test-cases.md             ← 测试用例
│
└── reference/                             ← 参考资料
    ├── smartdev-adapter-smartfav.md
    └── 参考.md
```

## 快速开始

```bash
cd smartPi/smartdev-agent
python -m pytest tests/ -v     # 310 tests passed

# 对任意项目建立代码索引
python -m smartdev index -p /path/to/project

# 搜索文件和工件
python -m smartdev search "token" -p /path/to/project

# 分析变更影响范围
python -m smartdev impact "models.py" -p /path/to/project
```

## 架构概览

```
用户输入 → Core Runtime → Workflow → Skill Registry → Skill → SkillResult
                         ↕
                   Project Adapter
                         ↕
              Context Layer (Code Intelligence)
```

五层职责：
- **Core Runtime**：调度、状态、权限、风险控制
- **Workflow**：诊断 → 规划 → 执行 → 验证 → 总结
- **Skill**：可复用能力单元，通过 `__init_subclass__` 自动注册
- **Project Adapter**：项目差异隔离（目录、约束、验证清单）
- **Context Layer**：项目语义图谱（artifact 提取 + import 关系 + 影响分析）

## 当前进度

**Phase 6.2 — Code Intelligence v1（已完成，已冻结）**

SmartDev 已具备基于 Python AST 的轻量代码结构提取、模块级 import 关系图谱、反向依赖影响分析、项目地图导出和图谱健康校验能力。

| 阶段 | 状态 | 说明 |
|------|------|------|
| Phase 1-5 | ✅ | 10 Skill + Workflow + Adapter（8 类 Skill，完整迭代闭环） |
| Phase 6-MVP | ✅ | SQLite 索引 + artifact 提取 + code.search + code.impact |
| Phase 6.2 | ✅ | 结构提取 + import relations + ImpactAnalyzer 升级 + project.map + graph.validate |
| **总计** | | **310 tests passed** |

### Code Intelligence v1 能力边界

Phase 6.2 的目标是让 SmartDev 能从"搜索相关文件"升级为"基于项目语义关系判断影响范围"。
当前能力边界为 **module-level impact analysis**，不承诺：

- ❌ 完整符号级引用分析（需 Tree-sitter）
- ❌ 函数调用图（需完整 call graph）
- ❌ JS/TS 高置信度解析（当前为 regex fallback，confidence=0.55）

**该阶段已冻结，不再继续加功能。** 下一步：Phase 6.3 — JS/TS Parser Provider。

## 设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据模型 | dataclass | 零依赖，Phase 1 够用 |
| 风险等级 | Enum | 类型安全，IDE 补全 |
| Skill 注册 | `__init_subclass__` | 子类定义即注册，不需要手动维护列表 |
| 检测逻辑 | 独立 detector 层 | 单一职责，可独立测试，可跨 Skill 复用 |
| 技术检测 | 标记文件 | 快速、低开销，准确率够用于诊断场景 |
| 目录树 | 只扫 2 层 | 避免 node_modules 等大目录拖慢扫描 |

## 开发规范

本项目遵循 [执行协议](docs/smartdev-agent-protocol.md) 开发，每小步必须：

1. **边讲边做** — 解释原理和理由，不说黑盒执行器
2. **运行测试** — `python -m pytest tests/ -v`
3. **提交 git** — 验证通过后立即 commit，不累积
4. **执行前说明** — 范围、风险、验收标准
5. **执行后总结** — 变更文件、关键变更、下一步

commit message 格式：`<type>: <description>`

```
feat:     新功能
fix:      Bug 修复
docs:     文档变更
refactor: 重构（不改变功能）
test:     测试
chore:    构建/工具变更
```
