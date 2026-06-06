# Changelog

本文档记录 SmartDev Agent 的重要变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/)。

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
