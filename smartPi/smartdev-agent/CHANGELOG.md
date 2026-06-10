# Changelog

本文档记录 SmartDev Agent 的重要变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/)。

## [Unreleased] — Phase 11 Complete: Standalone Hardened

### Added — Phase 11 Closeout: 文档收口

- **`CHANGELOG.md`**（修改）：追加 Phase 11 Closeout 记录
- **`docs/development-progress.md`**（修改）：Phase 11 全部完成状态、测试基线 1897/MCP 30、Phase 12 标记为可选增强
- **`docs/phase-11-design.md`**（修改）：追加 Closeout 注记，更新路线图
- **`docs/phase-11c-design.md`**（修改）：明确 11C 工具链 standalone 可用
- **`docs/phase-11d-design.md`**（修改）：修正过期状态描述（暂不实现 → 已完成）
- **`docs/phase-11b-design.md`**：Step 0–7 全部完成，无需更改

Phase 11 Closeout 事实：
- Phase 11A Git Governance v0 ✅
- Phase 11B Guard Skills v0 ✅
- Phase 11C Documentation Governance v0 ✅
- Phase 11D Collaboration Handoff v0 ✅
- 测试基线：**1897 passed, 1 skipped**
- MCP 工具：**30 个**（READ×24 + CACHE_WRITE×5 + PATCH_PROPOSE×1）
- SmartDev 为 standalone 工程协作工具（本地 CLI · run artifact / handoff · GuardRunner · Doc Governance · MCP 工具 · Git 治理建议）。Phase 12 Model Router 为可选后续增强，非完整性前提。

### Added — Phase 11B Step 7: MCP 暴露只读 Guard 工具

- **`smartdev/mcp/tools.py`**（修改）：新增 6 个 MCP Guard handler
  - `handle_guard_run()` — 一键运行全部 5 个 Guard，返回聚合报告
  - `handle_change_budget()` — 变更预算检查（文件数/行数/schema）
  - `handle_dev_guard()` — AI 编程规则守卫
  - `handle_dependency_guard()` — 依赖变更审查
  - `handle_security_review()` — 安全审查清单（6 类检查）
  - `handle_diff_explain()` — Patch 级 diff 解释
  - 所有 Guard handler 遵循统一模式：Skill.create() → can_run() → run() → 结构化响应
  - 缺少 required 参数时返回 `INVALID_ARGUMENT`，异常时返回 `INTERNAL_ERROR`
- **`smartdev/mcp/server.py`**（修改）：注册 6 个 Tool schema + 路由 handler
- **`smartdev/mcp/tools.py`**（修改）：`handle_version` 和 `handle_list_tools` 包含 6 个新 Guard 工具
- **`tests/test_mcp_guard_tools.py`**（新增）：26 tests
  - `TestGuardToolsRegistered`：4 tests（version/list_tools/handlers/schemas 注册验证）
  - `TestGuardRunHandler`：6 tests（有效输入/select 过滤/无效名称/全量运行/空文件/diff_content）
  - `TestChangeBudgetHandler`：4 tests（缺失参数/空列表/有效输入/自定义 max_files）
  - `TestDevGuardHandler`：3 tests（缺失参数/有效输入/protected_paths）
  - `TestDependencyGuardHandler`：3 tests（缺失参数/有效输入/manifest diff）
  - `TestSecurityReviewHandler`：3 tests（缺失参数/有效输入/hardcoded secret 检测）
  - `TestDiffExplainHandler`：3 tests（缺失参数/有效输入/diff_content 行数统计）
- **MCP 工具总数**：24 → 30
- **现有测试**（8 个文件）：更新硬编码工具总数（24 → 30）

测试基线：**1897 passed, 1 skipped**

### Added — Phase 11B Step 6: GuardRunner + CLI 入口

- **`smartdev/core/guard_runner.py`**（新增）：GuardRunner 组合执行层
  - `GuardEntryResult` / `GuardRunResult` 数据模型
  - `run_guard_runner()` 一键运行全部 5 个 Guard Skill，输出聚合报告
  - 支持 `select` 过滤只运行指定 Guard；无效名称返回错误不崩溃
  - 单个 Guard 异常时记录 error 字段，不中断整体流程
  - 聚合 `overall_passed` / per-guard `passed` / `summary` / `duration_ms` / `risks` / `next_steps`
  - 支持 `to_dict()` / `to_json()` JSON 序列化
  - 无 git 依赖，R0 只读，基于显式输入运行
- **`smartdev/cli.py`**（修改）：新增 `smartdev guard run` 命令
  - 支持参数：`--project` / `--changed-files` / `--select` / `--task` / `--diff-file` / `--max-files` / `--max-lines` / `--json`
  - 文本输出：overall、每个 guard 的 passed/summary、suggested_actions
  - JSON 输出：完整聚合报告
  - 错误处理：无效 guard 名称 / 不存在 diff-file / 不存在项目路径 → 返回非 0
- **`smartdev/core/snapshot.py`**（修改）：`_build_cli_parser` 同步 `smartdev guard run`
- **`tests/test_guard_runner.py`**（新增）：21 tests — 数据模型序列化 / 全量运行 / select 过滤 / 无效名称 / 空文件 / 聚合统计 / warning_count 语义 / 确定性
- **`tests/test_cli.py`**（修改）：新增 `TestGuardCLI`（11 tests） — help / run / json / select / invalid / missing-project / diff-file / max-files / text-output
- **`tests/test_snapshot.py`**（修改）：新增 `test_guard_run_present` + `test_guard_run_has_expected_args`

测试基线：**1871 passed, 1 skipped**

### Added — Phase 11B Step 5: diff.explain Guard Skill

- **`smartdev/core/guard_diff_explain.py`**（新增）：`diff.explain` patch 级规则引擎
  - `DiffExplainResult` 数据模型
  - `explain_diff()` 核心函数，覆盖逻辑分组 / 测试伴随 / 依赖匹配 / 跨模块检测 / 审查顺序建议
  - 与 `git.diff.explain`（仓库级）互补：面向显式传入的 patch 文件列表和 diff 内容
  - 支持 `base_signals` 参数合并外部既有信号（如 `git.diff.explain` 输出）
  - 零外部依赖，R0 只读，无 git 环境也能运行，不调用模型
  - 文件分类覆盖 source / test / doc / manifest / config / core / mcp / other
  - 穿透项目根前缀（smartdev/src/app/lib）进行功能模块分组
  - risk_hints 覆盖 cross_module_change / dependency_manifest_changed_without_code / missing_related_tests / core_module_touched / touches_protected_path / large_changeset / large_diff
- **`smartdev/skills/diff_explain_patch/__init__.py` + `skill.py` + `skill.yaml`**（新增）：`diff.explain` R0 只读 Skill
  - 调用 core 规则引擎，不复制规则逻辑
  - SkillResult.data 输出 summary / signals / file_categories / logical_groups / risk_hints / test_coverage / suggested_review_order
- **`smartdev/skills/__init__.py`**：注册 `diff.explain` Skill
- **`tests/test_guard_diff_explain.py`**（新增）：86 tests
  - 覆盖文件分类、diff 解析、信号计算（含 base_signals 合并）、逻辑分组、测试覆盖、依赖匹配、审查顺序、风险提示、Skill 集成、确定性和边界情况

测试基线：**1838 passed, 1 skipped**

### Added — Phase 11B Step 2: dev.guard Guard Skill

- **`smartdev/core/guard_dev.py`**（新增）：`dev.guard` 规则引擎
  - `DevGuardViolation` / `DevGuardResult` 数据模型
  - `check_dev_guard()` 核心函数，覆盖 mass_refactor / protected_path_hit / unrelated_change / test_deletion / config_in_code / forbidden_file_modification / large_commit 七类确定性规则
  - 支持显式输入运行，无 git 依赖，不调用模型，不接外部扫描器
- **`smartdev/skills/dev_guard/skill.py` + `skill.yaml`**（新增）：`dev.guard` R0 只读 Skill
  - 消费 `changed_files` / `protected_paths` / `denied_paths` / `forbidden_paths` / `task_description` / `diff_content` / `max_files_per_commit`
  - 输出结构化 `passed` / `checks` / `violations` / `summary`
- **`smartdev/skills/__init__.py`**：注册 `dev.guard` Skill
- **`tests/test_guard_dev.py`**（新增）：88 tests
  - 覆盖路径匹配、模块识别、关键词提取、文件类型分类、7 条规则、Skill 集成、序列化和确定性

测试基线：**1584 passed, 1 skipped**

### Added — Phase 11B Step 3: dependency.guard Guard Skill

- **`smartdev/core/guard_dependency.py`**（新增）：`dependency.guard` 规则引擎
  - `DependencyChange` / `DependencyViolation` / `DependencyResult` 数据模型
  - `check_dependency_guard()` 核心函数，覆盖 dependency_added / dependency_removed / dependency_version_changed / manifest_added / manifest_removed / lock_not_updated 六类确定性规则
  - 支持显式输入运行（changed_files / diff_content / manifest_before / manifest_after / lock_files_changed），无 git 依赖
  - 零外部依赖，R0 只读，不下载依赖，不调用外部扫描器
  - 4 种 manifest 解析器：`_parse_pyproject_toml`（tomllib 优先 + 行解析降级）、`_parse_package_json`（标准库 json）、`_parse_go_mod`（行解析 require 单行和块）、`_parse_requirements_txt`（行解析常见格式）
  - diff 分析：支持 before/after 精确对比 + unified diff 内容推断
  - lock 文件同步检查：pyproject.toml → poetry.lock/uv.lock/requirements.lock；package.json → package-lock.json/pnpm-lock.yaml/yarn.lock；go.mod → go.sum；requirements.txt → requirements.lock
  - 外部工具建议（只输出，不执行）：pip-audit / npm audit / govulncheck / semgrep
- **`smartdev/skills/dependency_guard/__init__.py` + `skill.py` + `skill.yaml`**（新增）：`dependency.guard` R0 只读 Skill
  - 调用 core 规则引擎，不复制规则逻辑
  - SkillResult.data 直接消费 core result
- **`smartdev/skills/__init__.py`**：注册 `dependency.guard` Skill
- **`tests/test_guard_dependency.py`**（新增）：99 tests
  - 覆盖 manifest 识别、4 种格式解析、diff 分析、lock 同步、建议命令、Skill 集成、确定性和边界情况

测试基线：**1683 passed, 1 skipped**

### Added — Phase 11B Step 4: security.review Guard Skill

- **`smartdev/core/guard_security.py`**（新增）：`security.review` 规则引擎
  - `SecurityViolation` / `SecurityResult` 数据模型
  - `check_security_review()` 核心函数，覆盖 input_validation / path_traversal / command_injection / sensitive_data / hardcoded_secrets / eval_exec 六类确定性安全检查
  - 支持显式输入运行（changed_files / diff_content / file_contents），无 git 依赖
  - 零外部依赖，R0 只读，不执行外部扫描器，不调用模型
  - 第一版只做文本/正则模式匹配，不做 AST/数据流分析
  - 外部工具建议（只输出，不执行）：bandit（Python）/ semgrep（JS/TS/多语言）
  - passed 语义：只有 error 阻断；仅 warning/info 时 passed=True
- **`smartdev/skills/security_review/__init__.py` + `skill.py` + `skill.yaml`**（新增）：`security.review` R0 只读 Skill
  - 调用 core 规则引擎，不复制规则逻辑
  - SkillResult.data 直接消费 core result
- **`smartdev/skills/__init__.py`**：注册 `security.review` Skill
- **`tests/test_guard_security.py`**（新增）：69 tests
  - 覆盖 6 类安全检查、建议命令、Skill 集成、确定性、diff_content 解析和边界情况

测试基线：**1752 passed, 1 skipped**

### Added — Phase 11B Step 1: change.budget Guard Skill

- **`smartdev/core/guard_budget.py`**（新增）：`change.budget` 规则引擎
  - `BudgetViolation` / `BudgetResult` 数据模型
  - `check_budget()` 核心函数，覆盖 file_count / line_count / schema_change / per_file_limit 四类确定性规则
  - 支持显式输入运行，无 git 依赖，不调用模型，不接外部扫描器
- **`smartdev/skills/change_budget/skill.py` + `skill.yaml`**（新增）：`change.budget` R0 只读 Skill
  - 消费 `changed_files` / `max_files` / `max_lines` / `allow_schema_change` / `per_file_limit` / `line_counts`
  - 输出结构化 `passed` / `checks` / `violations` / `summary`
- **`smartdev/skills/__init__.py`**：注册 `change.budget` Skill
- **`tests/test_guard_budget.py`**（新增）：60 tests
  - 覆盖 schema 文件检测、文件数/行数/单文件预算、schema 变更允许/拒绝、Skill 集成、序列化和确定性

测试基线：**1496 passed, 1 skipped**

### Added — Phase 11B Step 0: Guard Skills v0 执行前设计

- **`docs/phase-11b-design.md`**（新增）：Phase 11B Guard Skills v0 执行前设计
  - 定位：把 AI 编程限制在“人能理解、能判断、能验收、能回滚”的节奏里
  - 范围：`change.budget` / `dev.guard` / `dependency.guard` / `security.review` / `diff.explain`
  - 明确第一版只做确定性 checklist，不接外部扫描器，不调用模型
  - 定义 7 步实施路线：change.budget → dev.guard → dependency.guard → security.review → diff.explain → GuardRunner → MCP Guard 工具
  - 明确与 `scope_gate`、`git.diff.explain`、`doc.map`、Phase 11D handoff 的边界

测试基线：未运行（纯设计文档，无代码变更）

## [Unreleased] — Phase 11D: Collaboration Handoff v0（完成）

### Added — Phase 11D Step 7: MCP 暴露 handoff pack 工具

- **`smartdev/mcp/tools.py`**：新增 3 个 MCP handoff 工具 handler
  - `smartdev_handoff_code`：生成 `.smartdev/runs/<run_id>/handoff/code-agent-pack.md`
  - `smartdev_handoff_doc`：生成 `.smartdev/runs/<run_id>/handoff/doc-steward-pack.md`
  - `smartdev_handoff_review`：生成 `.smartdev/runs/<run_id>/handoff/reviewer-pack.md`
  - 三个 handler 均复用已有 core handoff 生成器，不复制 pack 组装逻辑，不调用模型
  - 成功 payload 固定包含 `run_id` / `output_path` / `char_count` / `sections` / `skipped` / `note`
  - 缺失 `run_id` 返回 `INVALID_ARGUMENT`，生成失败返回 `GENERATION_FAILED`
- **`smartdev/mcp/server.py`**：注册 3 个 MCP Tool schema + handler 路由
  - 工具权限标记为 `CACHE_WRITE`，说明只写 `.smartdev/runs/<run_id>/handoff/`，不修改源码
- **MCP 工具清单**：`smartdev_version` / `smartdev_list_tools` / MCP `tools/list` 工具数 21 → 24
- **`tests/test_mcp_handoff_tools.py`**（新增）：覆盖注册、权限、成功 payload、缺失参数、run 不存在和只写 run artifact
- **MCP 相关测试**：同步所有工具总数断言 21 → 24

测试基线：**1436 passed, 1 skipped**

### Added — Phase 11D Step 6B: smartdev run report + handoff doc 消费 agent-output

- **`smartdev/core/run_report.py`**（新增）：`write_run_report()` — Code Agent 报告写入核心
  - `--changed-files`：手动指定变更文件，写入 `agent-output/changed-files.txt`
  - `--auto-changed-files`：从 `git diff HEAD` 自动推断（git 不可用时优雅跳过）
  - `--tests <cmd>`：运行测试命令，输出写入 `agent-output/test-report.txt`
  - `--status <completed|blocked|partial>`：更新 `code-agent-result.md` Status 字段
  - `code-agent-result.md` 模板不存在时自动从 §14 结构生成
- **`smartdev/cli.py`**：新增 `smartdev run report <run_id>` CLI 子命令（R1）
- **`smartdev/core/handoff_doc.py`**：新增 `_try_agent_output()`
  - 若 `agent-output/code-agent-result.md` 存在，在 doc-steward-pack 中加入 "Agent Output" 节
  - Doc Steward 不再需要 Human 传递 Code Agent 的结果
- **`smartdev/core/snapshot.py`**：CLI Snapshot 同步 `smartdev run report`（23 → 24 commands）
- **`tests/test_run_report.py`**（新增）：17 tests
- **`tests/test_cli.py`**：`TestCLIRunReport` +3 tests
- **`tests/test_snapshot.py`**：`test_report_present` +1 test

测试基线：**1417 passed, 1 skipped**

### Added — Phase 11D Step 6 设计：Agent Output & Review Artifact Protocol

- **`docs/phase-11d-design.md`**：重大更新——固定输出回流协议
  - §4 Run Artifact 目录约定：扩展加入 `agent-output/` 和 `review/` 两层
    - `handoff/`（输入层）/ `agent-output/`（执行层）/ `review/`（审查层）三层职责划分
    - 每个目录明确"谁写 / 谁读 / 何时"
  - §7 协作流程：重写流程 A，Human 全程不复制聊天内容
    - Doc Steward 生成 code-agent-pack → Code Agent 写回 agent-output/ → Doc Steward 审查写 review/ → Human 读 commit-readiness.md 决策
  - §8 实施路线：Step 6 重定义为 Agent Output & Review Artifact Protocol，MCP 工具暴露后移为 Step 7
  - §13 验收标准：分 Step 1–5（已完成）/ Step 6（当前）/ Step 7（后续）三段
  - 新增 §14 Code Agent 输出协议：`code-agent-result.md` / `changed-files.txt` / `test-report.txt` 固定结构
  - 新增 §15 Doc Steward 输出协议：`commit-readiness.md` 固定结构，Human 唯一决策文件

测试基线：**1394 passed, 1 skipped**（纯文档，无代码变更）

### Added — Phase 11D Step 6A: agent-output/ review/ 目录协议落地

- **`smartdev/core/run_artifact.py`**：`create_run_artifact()` 新增强制创建 `agent-output/` 和 `review/` 子目录
  - `agent-output/code-agent-result.template.md` — 遵循 §14 固定结构（Status / Implemented / Changed Files / Tests / Open Questions）
  - `review/commit-readiness.template.md` — 遵循 §15 固定结构（Decision / Required Fixes / Gates / Documentation Status / Suggested Commits）
  - `--force` 覆盖时模板随 run 目录一起重建
- **`tests/test_run_artifact.py`**：新增 `TestAgentOutputAndReviewDirectories`（6 tests）
  - agent-output/ review/ 目录存在、模板内容完整性（Code Agent Result + Commit Readiness 固定节）、run_id 注入、force 覆盖后重建

测试基线：**1400 passed, 1 skipped**

### Added — Phase 11D Step 5: handoff review

- **`smartdev/core/handoff_review.py`**：新增 Reviewer Handoff Pack 生成能力
  - 生成 `.smartdev/runs/<run_id>/handoff/reviewer-pack.md`
  - pack 聚合 Risk + Impact / Changed Files / Test Report / Dependency Changes / Security Checklist / Git Diff Explain
  - 支持显式 `changed_files`，未提供时从 git diff 推断
  - 依赖变更识别覆盖 `pyproject.toml` / `package.json` / lockfile / `go.mod` / `Cargo.toml` 等常见清单
  - 安全清单基于路径信号提示认证、token、secret、password、命令执行、路径处理等重点审查项
- **`smartdev/cli.py`**：新增 `smartdev run handoff-review <run_id>` CLI 子命令
  - 支持 `--changed-files` / `--target` / `--run-tests`
  - 只写 `.smartdev/runs/<run_id>/handoff/reviewer-pack.md`
- **`smartdev/core/snapshot.py`**：CLI Snapshot 同步 `smartdev run handoff-review`
  - `smartdev snapshot cli` 命令数 21 → 22
- **`tests/test_handoff_review.py` / `tests/test_cli.py` / `tests/test_snapshot.py`**：新增 Step 5 覆盖
  - pack 生成、错误路径、字符预算、只写 run artifact、依赖/安全清单、CLI 和 snapshot 同步

测试基线：**1375 passed, 1 skipped**

### Added — Role Activation Preamble + smartdev run context

- **`smartdev/core/handoff_code.py`**：Code Agent Pack 新增角色激活前言
  - 明确协作架构（DeepSeek=Code Agent, Codex=Doc Steward, SmartDev=Handoff+Gates, Human=Apply/Commit/Release）
  - 包含角色职责、第一件事指引、输出格式和禁止项
- **`smartdev/core/handoff_doc.py`**：Doc Steward Pack 新增角色激活前言（对称设计）
- **`smartdev/core/handoff_review.py`**：Reviewer Pack 新增角色激活前言（对称设计）
- **`smartdev/cli.py`**：新增 `smartdev run context <run_id> --role` CLI 子命令（R0 只读）
  - 支持 `--role doc-steward|code-agent|reviewer`
  - 默认打印对应 pack 到 stdout（可管道/复制给目标模型）
  - `--info` 模式打印元信息（路径/是否存在/字符数/建议生成命令）
  - pack 不存在时给出明确错误和建议的 `handoff-*` 命令
- **`smartdev/core/snapshot.py`**：CLI Snapshot 同步 `smartdev run context`
  - `smartdev snapshot cli` 命令数 22 → 23
- **`tests/test_run_context.py` / `tests/test_cli.py` / `tests/test_snapshot.py`**：新增覆盖
  - pack 读取、`--info` 模式、三种角色、缺失 pack 提示、preamble 内容验证、CLI 和 snapshot 同步

测试基线：**1394 passed, 1 skipped**

---

### Added — Phase 11D Step 4: handoff doc

- **`smartdev/core/handoff_doc.py`**：新增 Doc Steward Handoff Pack 生成能力
  - 读取 `.smartdev/runs/<run_id>/task-card.md` 和 `scope.json`
  - 生成 `.smartdev/runs/<run_id>/handoff/doc-steward-pack.md`
  - pack 聚合 Change Manifest / Diff Summary / Test Report / Capability Snapshots / Doc Map / Phase Status / Doc Consistency / Update Focus
  - 所有数据源可选，git 不可用、无索引或 Skill 异常时优雅降级
  - Doc Steward 输出规范固定为 docs_required / issues / update_plan / patch_propose_only
- **`smartdev/cli.py`**：新增 `smartdev run handoff-doc <run_id>` CLI 子命令
  - 支持 `--run-tests`
  - 只写 `.smartdev/runs/<run_id>/handoff/doc-steward-pack.md`
- **`smartdev/core/snapshot.py`**：CLI Snapshot 同步 `smartdev run handoff-doc`
  - `smartdev snapshot cli` 命令数 20 → 21
- **`tests/test_handoff_doc.py` / `tests/test_cli.py` / `tests/test_snapshot.py`**：新增 Step 4 覆盖
  - pack 生成、错误路径、字符预算、只写 run artifact、数据源优雅降级、CLI 和 snapshot 同步
- **修复验证**：
  - Diff Summary 使用 `GitDiff.insertions` / `GitDiff.deletions`
  - Doc Map 正确处理 `mentions: dict[str, list[str]]`

测试基线：**1361 passed, 1 skipped**

---

### Added — Phase 11D Step 3: handoff code

- **`smartdev/core/handoff_code.py`**：新增 Code Agent Handoff Pack 生成能力
  - 读取 `.smartdev/runs/<run_id>/task-card.md` 和 `scope.json`
  - 生成 `.smartdev/runs/<run_id>/handoff/code-agent-pack.md`
  - pack 包含当前任务、修改范围、Scope Gate 结果、相关文件和代码片段、existing patterns、验收标准、禁止项、Code Agent 输出规范
  - 支持 `changed_files` 优先进入相关文件列表，避免把低相关文件排在实现上下文前面
  - 支持可选 Scope Gate 摘要和 impact 分析摘要，不调用任何模型
- **`smartdev/cli.py`**：新增 `smartdev run handoff-code <run_id>` CLI 子命令
  - 支持 `--changed-files` 和 `--target`
  - 只写 `.smartdev/runs/<run_id>/handoff/code-agent-pack.md`
- **`smartdev/core/snapshot.py`**：CLI Snapshot 同步 `smartdev run handoff-code`
  - `smartdev snapshot cli` 命令数 19 → 20
- **`tests/test_handoff_code.py` / `tests/test_cli.py` / `tests/test_snapshot.py`**：新增 Step 3 覆盖
  - pack 生成、错误路径、Scope Gate 集成、字符预算、只写 run artifact、changed_files 相关文件优先、CLI 和 snapshot 同步

测试基线：**1344 passed, 1 skipped**

---

### Added — Phase 11D Step 2: Scope Gate

- **`smartdev/core/scope_gate.py`**：新增 Scope Gate 只读检查能力
  - 读取 `.smartdev/runs/<run_id>/scope.json`
  - 对 `changed_files` 执行 max_files / denied_paths / protected_paths / outside_scope 四类检查
  - 输出 `passed` / `violations` / `warnings` / `summary` / `error` / `scope_config` 结构化结果
  - 支持 fnmatch glob、目录前缀和文件名匹配
- **`smartdev/cli.py`**：新增 `smartdev run scope-check <run_id>` CLI 子命令
  - 支持 `--changed-files` 和 `--json`
  - Scope Gate 通过返回 0；命中 error violation 或配置加载错误返回 1
- **`smartdev/core/snapshot.py`**：CLI Snapshot 同步 `smartdev run scope-check`
  - `smartdev snapshot cli` 命令数 18 → 19
- **`tests/test_scope_gate.py` / `tests/test_cli.py` / `tests/test_snapshot.py`**：新增 Step 2 覆盖
  - Scope Gate 正常通过、max_files、denied_paths、protected_paths、outside_scope、scope.json 缺失/格式错误
  - CLI 人类可读输出 / JSON 输出
  - CLI Snapshot 包含 `smartdev run scope-check`

测试基线：**1301 passed, 1 skipped**

---

### Added — Phase 11D Step 1: Run Artifact 目录约定

- **`smartdev/core/run_artifact.py`**：新增 Run Artifact 创建能力
  - 创建 `.smartdev/runs/<run_id>/task-card.md` 和 `scope.json`
  - `scope.json` 预留 `allowed_paths` / `denied_paths` / `max_files` / `protected_paths`，供 Step 2 Scope Gate 消费
  - run_id 格式校验；重复 run_id 默认报错，`force=True` 显式覆盖
- **`smartdev/cli.py`**：新增 `smartdev run new <id>` CLI 子命令
  - 支持 `--task` / `--force` / `--allowed-paths` / `--denied-paths` / `--max-files` / `--protected-paths`
  - 保留原 `smartdev run --project --task --target` workflow 模式
- **`smartdev/core/snapshot.py`**：CLI Snapshot 同步 `smartdev run new`
  - `smartdev snapshot cli` 命令数 17 → 18
  - 支持有自身参数且有子命令的 parser 同时输出父命令与子命令
- **`tests/test_run_artifact.py` / `tests/test_cli.py` / `tests/test_snapshot.py`**：新增 Step 1 覆盖
  - Run Artifact 创建、重复 run_id、非法 run_id、scope 默认值
  - `smartdev run new` CLI 集成
  - CLI Snapshot 包含 `smartdev run` 和 `smartdev run new`

测试基线：**1263 passed, 1 skipped**

---

## [Unreleased] — Phase 11C: Documentation Governance v0（完成）

### Fixed — doc.consistency Rule 3 误报修复

- **`smartdev/skills/doc_consistency/skill.py`**：Rule 3（capability_overpromise）误报大幅降低
  - 端到端测试发现 Rule 3 在真实项目上产生 42 个 high 误报（CHANGELOG/progress 的历史记录被误判为过度承诺）
  - 修复 1：只用最新设计文档（phase-11c/11d-design）作为 ❌ 声明来源，避免旧 Phase"范围内不做"被当作永久约束（如 git commit 在 Phase 10 不做、Phase 11A 已实现）
  - 修复 2：只检查面向用户的承诺文档（README.md），跳过 CLAUDE.md（内部规则）/ CHANGELOG / progress / 其他 design.md 等历史文档
  - 修复 3：新增 `_RULE3_STOPWORDS` 通用术语停用词表（apply/patch/agent/git/mcp/auto 等），过滤后要求 ≥2 个特异性关键词命中才触发
  - 效果：项目自检 issue 从 53 → 10，high 从 42 → 0，保留全部真实 low issue（README 缺命令 / CLAUDE Phase 状态 / 测试基线过时）
- **`tests/test_doc_consistency.py`**：更新 Rule 3 测试匹配新行为
  - 设计文档改用 phase-11c-design.md（最新文档）
  - 关键词改用特异性词（facial recognition biometric）避免被停用词过滤
  - 新增 `test_generic_stopwords_not_triggered`（apply/patch 不触发）
  - 新增 `test_changelog_not_checked`（CHANGELOG 被豁免）

测试基线：**1210 passed, 1 skipped**

---

## [Unreleased] — Phase 11C: Documentation Governance v0（Step 1-7 完成）

### Added — Phase 11C Step 7: MCP 暴露只读 Doc Governance 工具

- **`smartdev/mcp/tools.py`**：新增两个 handler
  - `handle_doc_consistency`：调用 `doc.consistency` Skill，所有快照现场生成，可选接受 `change_manifest` 参数（启用 Rule 5）
  - `handle_doc_update_plan`：调用 `doc.update.plan` Skill，可选接受 `consistency_issues` 参数（传空列表=不自动运行；不传=自动运行）
  - `handle_version` / `handle_list_tools` 工具清单更新（19 → 21 工具）
- **`smartdev/mcp/server.py`**：
  - 注册两个 Tool Schema（READ 权限，inputSchema 含可选参数说明）
  - `_HANDLERS` 路由新增两条
- **`tests/test_mcp_doc_tools.py`**：23 tests，全绿（新文件）
  - 工具注册验证（version / list_tools 各包含两个新工具）
  - 工具总数 21 / READ 权限
  - handle_doc_consistency：成功路径 / 预期字段 / 不存在项目报错 / change_manifest 参数
  - handle_doc_update_plan：成功路径 / 预期字段 / 不存在项目报错 / consistency_issues 参数驱动计划
- 旧测试工具计数更新（19 → 21）：test_mcp_server / test_mcp_readonly_tools / test_mcp_skill_tools / test_mcp_patch_propose / test_mcp_git_tools / test_mcp_integration

**MCP 工具总数：19 → 21（READ×18 + CACHE_WRITE×1 + PATCH_PROPOSE×1 + DOC_PROPOSE×1（暂不暴露））**

测试基线：**1208 passed, 1 skipped**

---

### Added — Phase 11C Step 6: doc.patch.propose Skill

- **`smartdev/skills/doc_patch_propose/skill.py`**：文档 Patch 生成 Skill（R1，不落盘）
  - `status_sync` 类型 → 确定性 find-replace patch（复用 Phase 9 `build_find_replace_patch` + `save_patch`）
    - `stale_test_baseline`：从 issue 提取旧数字/新数字，生成精确替换
    - `phase_status_mismatch`（版本类）：提取版本号对，生成版本替换
    - find_str 不在目标文档中时静默跳过，不崩溃
  - `capability_boundary` / `expression_alignment` 类型 → hint（不生成 patch，需人工起草内容）
  - patch 持久化到 `.smartdev/patches/`，源文档不修改（propose only）
  - `changed_files` 包含 patch 文件路径（供审计，不含源文档）
  - 明确区分"传入 update_items"与"未传（自动运行 doc.update.plan）"
- **`smartdev/skills/doc_patch_propose/skill.yaml`**：Skill 元数据（R1，propose_only）
- **`smartdev/skills/__init__.py`**：注册 `doc.patch.propose`（Skill 总数 21 → 22）
- **`tests/test_doc_patch_propose.py`**：40 tests，全绿
  - 注册 / R1 / can_run / 空 items
  - stale_test_baseline patch 生成（find/replace 内容 / patch_id / 持久化 / 源文档不修改）
  - find_str 不存在时跳过
  - version 类 phase_status_mismatch
  - capability_boundary → hint（无 patch）
  - 最简调用 / changed_files / to_dict 结构
  - _extract_test_baseline_pair / _extract_version_pair 单元测试

测试基线：**1185 passed, 1 skipped**

---

### Added — Phase 11C Step 5: doc.update.plan Skill

- **`smartdev/skills/doc_update_plan/skill.py`**：文档更新计划 Skill（R0 只读）
  - 消费 `doc.consistency` issues，输出结构化更新计划
  - 三类更新性质区分：
    - `status_sync`：状态同步（有明确新值，机械替换）← rule2 / rule4
    - `capability_boundary`：能力边界（新增/修正能力描述）← rule1 / rule3 / rule5
    - `expression_alignment`：表达口径（对齐多文档措辞）
  - `build_update_plan`：按 doc 分组 issues，计算 update_kind（取优先级最高 kind）、priority（取最高 severity）、合并 reasons / suggestions
  - `_is_no_change_doc`：设计文档（`-design.md`）/ CHANGELOG / LICENSE 自动归入不应修改列表
  - `_build_suggestion`：按 issue type 生成确定性建议（数字替换 / 命令补充 / 过度承诺修正）
  - `update_items` 按 priority 排序（high → medium → low）
  - 明确区分"传入空 issues（已检查）"与"未传（自动运行 doc.consistency）"
- **`smartdev/skills/doc_update_plan/skill.yaml`**：Skill 元数据
- **`smartdev/skills/__init__.py`**：注册 `doc.update.plan`（Skill 总数 20 → 21）
- **`tests/test_doc_update_plan.py`**：43 tests，全绿
  - 注册 / R0 / can_run / 空 issues
  - update_kind 分类（5 种 issue type）/ mixed kind 取最高优先
  - priority 计算 / mixed severities
  - no_change_items（design.md / CHANGELOG）/ _is_no_change_doc
  - suggestions 生成（stale_baseline 数字替换 / phase_mismatch 版本 / stale_capability CLI）
  - 多 issue 同一文档合并
  - update_items 排序
  - 最简调用 / 传入 consistency_issues
  - UpdateItem / NoChangeItem to_dict 结构
  - next_steps 建议

测试基线：**1145 passed, 1 skipped**

---

### Added — Phase 11C Step 4: doc.consistency Skill

- **`smartdev/skills/doc_consistency/skill.py`**：文档一致性检查 Skill（R0 只读）
  - 5 条确定性规则，全部独立执行（单条失败不阻断其他）：
    - **Rule 1** `stale_capability`：skill_count vs doc_map skill mentions 数量差 > 3 触发；CLI 命令未在文档中提及触发（severity: medium/low）
    - **Rule 2** `phase_status_mismatch`：CHANGELOG latest_version vs pyproject.toml version 不符；progress.md Phase mentions vs CLAUDE.md 差异（severity: medium/low）
    - **Rule 3** `capability_overpromise`：设计文档 ❌ 声明 vs 其他文档关键词匹配（≥2 词命中才触发，severity: high）
    - **Rule 4** `stale_test_baseline`：progress.md 最大测试数 vs 其他文档差距 > 50 触发（severity: low）
    - **Rule 5** `public_surface_changed_docs_not_updated`：manifest.public_surface_changed=True 且 README/CHANGELOG/CLAUDE.md mtime 早于 manifest timestamp（severity: medium）
  - 输入快照均为可选，不传时自动现场生成（方便 CLI 直接调用）
  - 不传 change_manifest 时跳过规则 5（不视为错误）
- **`smartdev/skills/doc_consistency/skill.yaml`**：Skill 元数据
- **`smartdev/skills/__init__.py`**：注册 `doc.consistency`（Skill 总数 19 → 20）
- **`tests/test_doc_consistency.py`**：39 tests，全绿
  - 注册 / R0 / can_run
  - 无问题路径（issue_count=0）
  - 各规则触发 / 不触发条件
  - 规则隔离（单条失败不阻断）
  - 最简调用自动生成快照
  - ConsistencyIssue.to_dict 结构 / severity_summary 统计

测试基线：**1102 passed, 1 skipped**

---

### Added — Phase 11C Step 3: doc.map Skill

- **`smartdev/skills/doc_map/skill.py`**：文档地图 Skill（R0 只读）
  - 扫描范围：项目根 README.md / CHANGELOG.md / CLAUDE.md / CONTRIBUTING.md / AGENTS.md + `docs/` 目录所有 `.md/.rst/.txt` + 可选 `extra_paths`
  - `_extract_headings`：Markdown `#`~`######` 标题提取，保留层级前缀
  - `_extract_mentions`：6 类确定性 mention 模式（version / phase / test_baseline / mcp_tool / cli_command / skill_name），去重，最多 20 个
  - CHANGELOG 专用：提取 `latest_version` / `version_sections`（`## [xxx]` 节）
  - `extra_paths` 参数：支持扫描额外指定文件
  - `mention_keywords` 参数：支持自定义精确字符串关键词（自动转为正则）
  - 文件不存在 / 读取失败时跳过，不崩溃；结果包含 `skipped` 列表
  - `_parse_skill_yaml_lite` 零依赖 YAML 解析（复用 snapshot.py）
- **`smartdev/skills/doc_map/skill.yaml`**：Skill 元数据
- **`smartdev/skills/__init__.py`**：注册 `doc.map`（Skill 总数 18 → 19）
- **`tests/test_doc_map.py`**：50 tests，全绿
  - 注册 / can_run / 空项目
  - README / CHANGELOG / docs/ 扫描
  - headings / mentions / last_modified / size_bytes
  - CHANGELOG latest_version / version_sections
  - extra_paths / mention_keywords 参数
  - _extract_headings / _extract_mentions / _collect_doc_paths 单元测试
  - DocEntry.to_dict 结构验证

测试基线：**1063 passed, 1 skipped**

---

### Added — Phase 11C Step 2: Capability Snapshot 导出

- **`smartdev/core/snapshot.py`**：三种能力快照导出器 + 数据模型
  - `SkillSnapshot`：从 `Skill.get_registry()` + `skill.yaml` 内省，含 inputs/outputs 字段
  - `CliSnapshot`：从 argparse 结构内省，递归遍历所有叶子命令（`_walk_subparsers`）
  - `McpSnapshot`：从 `mcp/server.py` `_TOOLS` 内省，mcp 未安装时返回 `available=False`（不崩溃）
  - `_parse_skill_yaml_lite`：零依赖 YAML 轻量解析，提取 inputs/outputs，内联注释自动剥离
  - `save_snapshot`：写入 `.smartdev/runs/<run_id>/<name>-snapshot.json`
- **`smartdev/cli.py`**：新增 `snapshot` 子命令组
  - `smartdev snapshot skills [--save]`：导出 Skill 注册表快照（18 个 Skill）
  - `smartdev snapshot cli [--save]`：导出 CLI 命令快照（17 条命令）
  - `smartdev snapshot mcp [--save]`：导出 MCP 工具快照（19 个工具）
- **`tests/test_snapshot.py`**：53 tests，全绿
  - 三种数据模型序列化 / 反序列化 / roundtrip
  - `_parse_skill_yaml_lite`：required/optional/内联注释/空文件
  - `build_skill_snapshot`：注册表完整性 / git.status outputs 来自 yaml
  - `build_cli_snapshot`：命令排序 / git commit args / snapshot 命令自身存在
  - `build_mcp_snapshot`：mcp 安装 / 未安装 mock / 工具排序 / ping 工具存在
  - `save_snapshot`：路径 / 内容 / 自动创建目录

测试基线：**1013 passed, 1 skipped**

---

### Added — Phase 11C Step 1: Change Manifest 生成

- **`smartdev/core/manifest.py`**：ChangeManifest 数据模型 + 生成器 + 持久化
  - `ChangeManifest` dataclass：run_id / source / timestamp / changed_files / change_type / risk_level / public_surface_changed / cli_changed / skill_changed / mcp_changed / docs_likely_needed / validation / commit_message / patch_id
  - 三种来源工厂函数：`manifest_from_git_diff`（working_tree_diff）/ `manifest_from_patch_apply`（patch_apply）/ `manifest_from_git_commit`（git_commit）
  - 通用入口 `manifest_from_files`：自动推断 change_type / risk_level / surface flags / docs_likely_needed
  - 持久化：`save_manifest` 写入 `.smartdev/runs/<run_id>/change-manifest.json`；`load_manifest` / `load_latest_manifest` 加载
  - git 不可用时 `manifest_from_git_diff` 返回空 manifest，不崩溃
- **`smartdev/cli.py`**：新增 `manifest` 子命令组
  - `smartdev manifest diff [--save] [--run-id]`：从工作区 diff 生成 ChangeManifest，可选保存
  - `smartdev manifest last`：展示最近一次已保存的 ChangeManifest
  - `smartdev manifest show <run_id>`：按 run_id 查看指定 ChangeManifest
- **`tests/test_manifest.py`**：54 tests，全绿
  - 数据模型序列化 / 反序列化 / roundtrip
  - change_type 推断（commit prefix 优先 / 文件路径特征）
  - risk_level 推断（文件数量 / public_surface）
  - surface flags（cli / mcp / skill / pyproject.toml / skill.yaml）
  - docs_likely_needed 推断
  - 三种来源工厂函数验证
  - 真实 git 仓库测试（staged / unstaged / dedup）
  - 持久化 save / load / load_latest 全路径

测试基线：**960 passed, 1 skipped**

---

## [Unreleased] — Phase 11A: Git Governance v0（已完成）

### Added — Phase 11D Step 0: Collaboration Handoff v0 设计文档 + 11C 修正

- **`docs/phase-11d-design.md`**：多模型协作交接层设计（独立于 11C，暂不实现）
  - 定位：把 SmartDev run artifacts 裁剪成角色化上下文包，降低 token，协作基于同一份工程事实
  - 角色权限矩阵：Code Agent / Doc Steward / Reviewer / SmartDev / Human
  - Run Artifact 目录约定（.smartdev/runs/<run_id>/）
  - 三个 handoff pack（code ≤8k / doc ≤6k / review ≤10k），只生成 markdown 不调模型
  - Scope Gate（11D 唯一新增核心）+ 其余 4 个 Gate 复用前序 Phase
  - 顺序协作 vs 高风险并行审查两种流程
  - 三阶段演进：模式 A 手动（现在可用）→ B MCP → C Model Router
- **`docs/phase-11c-design.md` 3 处修正**：
  - Change Manifest 支持三种来源（patch_apply / git_commit / working_tree_diff），Doc Steward 可在 commit 前介入
  - doc.patch.propose 第一版优先 find-replace/section replace，复杂改写走 update plan
  - MCP 暂不暴露 doc.patch.propose 的原因改为"生成质量需先在 CLI 跑稳"（而非"写文档"）
- **Phase 11 路线调整**：11A ✅ → 11C → 11D → 11B → Phase 12



- **`docs/phase-11c-design.md`**：Doc Governance v0 完整设计
  - 定位：SmartDev 提供文档一致性检查的工具链，高阶模型担任 Doc Steward 角色
  - 角色分工：高阶模型判断 + SmartDev 提供事实 + 人确认 apply
  - 两个模型协作协议：通过 run artifacts 共享上下文，不靠聊天记忆
  - 5 种结构化上下文：Change Manifest / Project Map / Skill Snapshot / CLI Snapshot / Doc Map
  - 5 条确定性检查规则：代码能力 / Phase 状态 / 能力边界 / 测试基线 / 公共接口
  - 8 步实施路线（Step 0–7）
  - 与 Phase 12 Model Collaboration Layer 的关系（Doc Steward 作为注册 role）

（工具总数 14 → 19）

- **`smartdev_git_status`**（READ）：查询 git 状态快照，调用 `git.status` Skill
- **`smartdev_git_diff_explain`**（READ）：确定性结构化 diff 解释，调用 `git.diff.explain` Skill
- **`smartdev_git_commit_plan`**（READ）：Conventional Commit 拆分建议，调用 `git.commit.plan` Skill
- **`smartdev_git_release_plan`**（READ）：semver bump 建议 + 发布清单，调用 `git.release.plan` Skill
- **`smartdev_git_merge_check`**（READ）：合并前检查（blockers/warnings），调用 `git.merge.check` Skill
- 所有工具在非 git 目录时返回 `GIT_NOT_FOUND`，不崩溃
- commit / tag / push / merge 永不进 MCP
- `handle_version` + `handle_list_tools` 更新工具清单（19 条）
- **`test_mcp_git_tools.py`**：33 tests（注册验证 / GIT_NOT_FOUND / 5 个工具集成）
- 更新旧有工具计数测试（14 → 19）：test_mcp_server / test_mcp_readonly_tools / test_mcp_skill_tools / test_mcp_patch_propose / test_mcp_integration

**Phase 11A（Git Governance v0）完成。** 7 步全部交付，906 tests，MCP 工具 19 个。



- **`smartdev git commit`**（R2，默认 dry-run）：
  - 默认只输出"将要执行什么"，不创建 commit
  - `--apply` 才调用 `GitService.commit()`，真正写 Git 历史
  - policy 门控：protected branch → blocker（rc=1）；超 max_files → warning
  - 执行后写审计到 `.smartdev/index.sqlite` runs 表
- **`smartdev git tag`**（R2，默认 dry-run）：
  - 默认 dry-run；`--apply` 才打 tag
  - 重复 tag → blocker（rc=1）
  - 支持 `--message` 创建 annotated tag
- **`_write_git_audit()`**：复用 code.apply 的审计模式，无索引时静默处理
- **`tests/test_git_commit_command.py`**：28 tests（dry-run / apply / policy / error / audit）



- **`.smartdev/git-policy.json`**：项目级 git policy 示例配置文件
  - policy 实现已在 Step 1 `core/git.py` 完成（`GitPolicy` + `load_git_policy()`）
  - 格式：JSON（零依赖，标准库 `json` 解析）
  - 字段：branch.protected / commit.convention+max_files / release.changelog+version_files / dangerous 全 forbid
  - 无文件时使用安全默认值；有文件时只覆盖明确指定字段
- **`docs/phase-11-design.md`**：Step 5 标注已完成，补充实现说明和示例

### Added — Phase 11A Step 4: git.release.plan + git.merge.check Skill

- **`git.release.plan` Skill**（R0 只读）：分析 commits / CHANGELOG / version 文件，给出 semver bump 建议
  - `_infer_bump()`：Conventional Commit type → major/minor/patch/none（BREAKING→major, feat→minor, 其余→patch）
  - `_bump_version()`：semver 字符串 bump，保留 v 前缀，格式非法时返回原值
  - `_read_version()`：读取 pyproject.toml / package.json 版本号，零依赖（正则/json）
  - `_check_changelog()`：检查 CHANGELOG 存在性 + [Unreleased] 节
  - `_build_release_checklist()`：发布前检查清单（含 major/dirty/backup 动态项）
  - since_tag 输入支持
- **`git.merge.check` Skill**（R0 只读）：合并前检查，blockers（阻断）vs warnings（警告）两级分类
  - `_check_working_tree()`：工作区脏 → blocker
  - `_check_patch_backups()`：未清理备份 → warning
  - `_check_target_branch()`：同分支 → blocker；从 protected 分支合 → warning
  - `_check_has_commits()`：无新 commit → warning
  - `_check_index_available()`：无索引 → warning
  - ready = blockers 为空
- **`test_git_release_plan.py`**：56 tests（infer_bump / bump_version / read_version / changelog / merge_check 全部单元 + 集成）

### Added — 防范"跳过提交"机制

- **CLAUDE.md §2a**：新增"每步完成后的强制 Checklist"，明确触发条件和严禁行为
- **Kiro hook**：`smartdev-step-commit-reminder`（postToolUse/write），每次写文件后自动检查是否完成可验证 Step



- **`git.commit.plan` Skill**（R0 只读）：分析 diff，生成 Conventional Commit 拆分建议
  - `build_commit_suggestions()`：按文件类别分桶（source/test/doc/manifest/config），source 按顶层目录拆
  - `_infer_type()`：category + status → Conventional Commit type（feat/fix/docs/test/build/chore/refactor）
  - `_infer_scope()`：从文件路径顶层目录启发式推导，scope_hint 优先
  - policy_warnings：超 max_files_per_commit / 在 protected branch 时提示
  - staged_only 模式支持
- **`git.commit.message` Skill**（R0 只读）：生成符合 Conventional Commit 规范的 commit 消息字符串
  - `build_commit_message()`：组装 header + body + footers（BREAKING CHANGE / Co-authored-by）
  - `validate_commit_inputs()`：6 项格式校验（type / 大写开头 / 句号结尾 / 超长 / 非法 type）— 只警告不拦截
  - breaking change：同时加 `!` 标记和 `BREAKING CHANGE:` footer
  - 不依赖 git 可用性（纯字符串生成）
- **`test_git_commit_plan.py`**：59 tests（infer_type / infer_scope / build_suggestions / Skill 集成 / message 生成 / validation）

### Added — Phase 11A Step 2: git.status + git.diff.explain Skill

- **`git.status` Skill**（R0 只读）：查询当前 git 仓库状态快照
  - 输出：branch / is_dirty / staged / unstaged / untracked / recent_commits / policy_hints
  - policy_hints：当前分支是 protected branch 时提示
  - next_steps：根据脏状态类型给出建议（diff.explain / commit.plan）
- **`git.diff.explain` Skill**（R0 只读）：确定性结构化 diff 解释，不做自然语言总结
  - `_classify_file()`：source / test / doc / manifest / config / other 6 分类
  - `_compute_signals()`：touches_tests / touches_docs / touches_manifest / touches_protected_path
  - `_compute_risk_hints()`：large_changeset / multi_file / cross_module / large_diff / manifest
  - `_suggest_commit_split()`：按类别建议 commit 拆分方案
  - staged=True / False 两种模式；空 diff 快速返回
- **`test_git_status.py`**：20 tests；**`test_git_diff_explain.py`**：37 tests

### Added — Phase 11A Step 1: core/git.py（GitService）

- **`smartdev/core/git.py`**：Git 底层封装，所有 git Skill 的唯一 subprocess 接触点
  - `GitNotAvailable`：统一异常，调用方捕获返回 GIT_NOT_FOUND，不崩溃
  - `GitFileChange / GitStatus / GitDiff`：结构化数据模型
  - `GitPolicy + load_git_policy()`：读取 `.smartdev/git-policy.json`，不存在时用安全默认值
  - `GitService`：只读方法（status/diff/tags/log）+ 执行方法（commit/tag，仅供 CLI Command）
  - subprocess 全部列表参数，无 shell=True，防注入
- **`test_git_service.py`**：36 tests（is_available / status / diff / tags / log / policy / commit / tag）

### Added — Phase 11A Step 0: 设计文档

- **`docs/phase-11-design.md`**：Phase 11A Git Governance v0 完整设计
  - 8 条硬原则（不自动提交 / Skill 只读 / Command 显式执行 / 默认 dry-run / 零依赖 / MCP 只暴露只读 / 不进 workflow / apply 与 commit 分离）
  - 7 个核心问题拍板（policy 格式改为 JSON）
  - 技术设计：GitService / Skill 模式 / CLI Command 模式 / MCP 工具接入
  - 7 步实施路线 + 验收标准 14 条



### Added — Phase 9 Step 3+4: code.apply / code.rollback Skill + 端到端验证

- **`code.apply` Skill**（首个写盘 Skill，R2/R3）：
  - 加载已持久化 patch_id（P0-1，不重新扫描）
  - protected_paths 校验 → 命中拒绝
  - R3 强确认门（P0-4）：`confirm_risk_r3="APPLY R3"` 才放行
  - 调用 `apply_patch()`（hash 校验 P0-2 + 路径安全 P0-3 + 备份 + 原子性）
  - 写盘后审计到 runs 表
  - `changed_files` 包含所有已应用文件
- **`code.rollback` Skill**（R1）：加载 backup_path → `rollback_patch()`，支持相对/绝对路径
- **skills `__init__.py`**：注册 code.apply + code.rollback
- **`test_code_apply.py`**：14 tests（元数据/missing_patch_id/patch_not_found/正常apply/备份/changed_files/审计/hash不一致/protected/R3无确认/R3有确认）
- **`test_code_rollback.py`**：5 tests（元数据/missing/nonexistent/端到端apply→rollback/相对路径）

**端到端闭环（propose→apply→rollback）通过：** Step 4 无需单独实现，已由 Step 3 测试完整覆盖。

**Phase 9（Safe Patch Agent）完成。** `code.patch` 从占位符升级为可控的安全执行能力（L3→L4 跳跃）。

### Added — Phase 9 Step 2: code.patch propose 真实化

- **`code.patch` find-replace 真实模式**：inputs 提供 `find`+`replace` 时调用 `build_find_replace_patch()`（确定性，无 LLM）
  - 支持 `glob`（文件范围）、`regex`（正则模式）可选参数
  - 持久化 patch_id 到 `.smartdev/patches/{id}.json`（P0-1 防 TOCTOU）
  - `mode` 字段区分 `find_replace` / `legacy`
- **可选 impact 增强**：有索引时 `_try_impact_for_patch()` 分析受影响文件 + 风险（复用 Phase 8 的 ImpactAnalyzer）；无索引退回 patch.risk_level（零回归）
- **零回归 legacy 路径**：无 find/replace inputs → 退回说明性占位符，data["mode"]="legacy"
- **输出新增字段**：`mode` / `patch_id` / `affected_files`（有 impact 时）
- **`test_code_patch.py` 扩展**：+9 tests（真实 diff / 无命中 / 不落地 / patch_id / legacy fallback / regex / 无索引 / 有索引 impact）

### Added — Phase 9 Step 1B: apply / rollback（写盘能力）

- **`apply_patch()`**：补丁应用到磁盘，三重保护：
  - 路径安全校验（P0-3，is_safe_target）→ 不安全则 skip
  - old_hash 一致性校验（P0-2）→ 不一致则 reject（防 TOCTOU）
  - 应用前备份原文件到 backup_dir
  - **原子性**：任一文件被 reject 则整体不应用
  - 支持 CREATE / MODIFY / DELETE 三种 action
- **`rollback_patch()`**：从备份目录恢复——普通文件写回原位，`.absent` 标记则删除（撤销 CREATE）
- **`ApplyResult` / `RollbackResult`**：结构化结果（applied/skipped/rejected/backup_path/errors）
- **`_backup_file()`**：保留相对目录结构备份，CREATE 场景写 `.absent` 标记
- **运行时风险约束**：apply_patch 是写盘能力（R2/R3），文档明确禁止绕过 Skill 层权限门直接调用
- **`test_patch.py` 扩展**：+11 tests（apply 修改/备份/hash 拒绝/CREATE/DELETE/路径跳过 + rollback 恢复/删除/缺备份 + 端到端 propose→apply→rollback 闭环）

### Test

- **512 passed, 1 skipped** — 测试基线（501 → 512，+11）

---

### Added — Phase 9 Step 1A: Safe Patch 可审查草案基础设施

- **`get_index_if_available()` schema 加固**（Phase 9 前置）：不仅检查 `.smartdev/index.sqlite` 存在，还用只读连接校验核心表（files/artifacts/relations）。损坏/缺表/不兼容 → fallback，不报错。理由：Phase 9 依赖 impact 判风险，旧/损坏索引会让判断不可靠。
- **`core/patch.py` 可审查草案能力**（不写盘）：
  - `FilePatch` 新增 `old_hash` / `old_size` / `old_mtime`（P0-2，apply 前一致性校验基础）
  - `Patch` 新增 `patch_id` / `affected_files` / `created_at`
  - `Patch.to_dict()` / `from_dict()`：JSON 序列化往返（行级 changes 从 old/new content 重算）
  - `compute_content_hash()`：内容 SHA256
  - `is_safe_target()`（P0-3）：路径安全过滤——拒绝 traversal/外部路径/二进制/symlink，跳过 .git/.smartdev/node_modules 等
  - `build_find_replace_patch()`：确定性 find-replace 补丁生成器（无 LLM），跨文件命中、记录 hash 元数据、路径安全过滤，**不落地**
  - `generate_patch_id()` / `save_patch()` / `load_patch()`（P0-1）：propose 持久化到 `.smartdev/patches/{patch_id}.json`，防 TOCTOU
- **`test_patch.py` 扩展**：+17 tests（内容 hash / 路径安全 5 项 / find-replace 6 项 / 序列化往返 4 项）

### Changed

- 仍不写真实源码——Step 1A 只做"可审查草案"，apply/rollback 在 Step 1B

### Test

- **501 passed, 1 skipped** — 测试基线（484 → 501，+17）

---

## [0.4.0] - 2026-06-07

### Added — Phase 8 Step 4: Context Layer ↔ Skill 端到端验证

- **`WorkflowEngine.run()` 新增 `target` 参数**：注入各步骤 inputs，驱动 risk.check / task.plan 的 code.impact 影响分析（不使用 target 的 Skill 忽略此键）
- **CLI `run` 新增 `--target`**：变更目标，驱动影响分析（需先建索引）
- **`test_skill_context_integration.py`**（新建，7 tests）：
  - workflow 中 architecture.map 自动用索引（source=index）
  - 传 target → risk.check 用 impact 增强 / task.plan 标注受影响文件
  - 无索引项目 workflow 正常运行（architecture.map 退回 AST，risk.check 退回关键词）
- **真实项目验证（只读）**：gnet-examples（11 Go 模块）workflow 6/6 成功，architecture.map source=index，risk.check risk_source=impact，验证后清理 .smartdev

**Phase 8（Context Layer ↔ Skill 接入打通）完成。** 三个核心 Skill 现在都消费 Context Layer。

### Added — Phase 8 Step 3: task.plan 接入 code.impact

- **`_extract_target()`**：确定 impact 目标——优先 inputs["target"]，否则从任务描述提取文件 token（.py/.js/.ts/.go/.css/.json/.md）
- **`_try_impact()`**：有 target + 索引时运行 `ImpactAnalyzer.analyze_import_impact()`，只读，R0 语义
- **推荐方案标注受影响文件**：把任务项的 `"（待分析）"` 占位符替换为真实受影响文件（前 10 个）
- **输出新增 `data["impact"]`**（仅当解析到影响）：target / affected_files / risk_level / validation
- **scope 标注 + next_steps 提示**受影响文件数
- **优雅降级**：无 target / 无索引 / 未解析 → 纯三档模板（零回归，无 impact 字段）
- **三档结构不变**：保守/推荐/深度结构和现有测试完全兼容
- **`test_task_plan.py` 扩展**：+6 tests（无索引 / inputs target / 描述提取 / 占位符替换 / 三档保留 / 未解析）

### Added — Phase 8 Step 2: architecture.map 接入 index relations

- **`_analyze_from_index()`**：从索引构建多语言依赖图
  - `code:module` artifacts → 模块节点（文件路径作节点标识，跨语言统一）
  - `imports` relations → 依赖边（internal `code:module:` / Python `module:{dotted}` 别名映射 / external）
  - 复用 `detectors.modules` 的 `ModuleInfo` + `_detect_circular_deps`，循环依赖算法与 AST 路径一致
- **数据源切换 + fallback**：有索引 → index（多语言）；无索引或无 module artifact → Python AST
- **can_run 放宽**：有索引时即使无 .py 也可分析（支持 Go/JS-TS 项目）
- **输出新增 `source` 字段**："index"（多语言）/ "ast"（Python）
- **`_safe_line_count()`**：语言无关的非空行计数（替代 Python 专属注释规则）
- **`test_architecture_map.py` 扩展**：+7 tests（fallback / index 源 / 依赖图 / 核心模块 / Go 多语言 / 循环依赖 / can_run）

### Added — Phase 8 Step 1: risk.check 接入 code.impact

- **`skills/_context_helper.py`**（新建）：Skill ↔ Context Layer 接入辅助
  - `get_index_if_available()`：检测 `.smartdev/index.sqlite`，存在则返回 ProjectIndex，否则 None（只读，不触发索引构建，异常安全）
  - `max_risk()`：多个 RiskLevel 取最高值（宁可保守，不可低估）
- **risk.check 可选接入 code.impact**：
  - inputs 提供 `target` 且项目已建索引 → 用 `ImpactAnalyzer.analyze_import_impact()` 增强
  - `final_risk = max(keyword_risk, impact_risk)`
  - 输出新增 `affected_files` / `impact_summary` / `impact_validation` / `risk_source`
  - 无 target / 无索引 / 解析失败 → 退回纯关键词匹配（零回归）
  - 保持 R0 只读语义（ImpactAnalyzer 只读索引）
- **已知问题 #1 缓解**：中文语序漏匹配问题，在有索引+target 时改用真实依赖分析判定风险
- **`test_risk_check.py` 扩展**：+6 tests（无 target / 无索引 / impact 增强 / max 风险 / 未解析 fallback / R0 只读）

### Changed

- risk.check 风险判断从"纯关键词"升级为"关键词 + 可选 impact 增强"

### Test

- **484 passed, 1 skipped** — 测试基线（458 → 484，+26：Step 1 +6, Step 2 +7, Step 3 +6, Step 4 +7）

---

## [0.3.0] - 2026-06-07

### Added — Phase 7 Step 1: TreeSitterProvider 骨架

- **TreeSitterProvider 骨架**：实现 `StructureExtractorProvider` 接口，依赖缺失时静默跳过
- **`_tree_sitter_available()`**：运行时检测 tree-sitter Python binding
- **`_try_create_tree_sitter_provider()`**：安全创建 Provider，异常不传播
- **auto_detect_treesitter**：`StructureExtractor.__init__` 新增自动注册入口
- **Step 1 不接真实 grammar**：此时 TreeSitterProvider 只注册接口，不提取任何代码结构
- **`test_tree_sitter_provider.py`**：20 tests（Provider 注册 + 接口合规 + 缺依赖跳过 + 不支持语言）
- 测试基线：405 passed, 1 skipped

### Added — Phase 7 Step 2: Go grammar 试点

- **`_load_language("go")`**：tree-sitter-go grammar 加载适配层，隔离 API 差异
- **`_extract_go()`**：Go AST 节点 → CodeSymbol 映射
  - `function_declaration` → function（exported by 首字母大写）
  - `method_declaration` → method（parent = receiver type）
  - `type_declaration` → class（struct）/ interface
  - `import_declaration` → import（单行 + block，alias/blank/dot 三种形式）
  - 语法错误不崩溃，返回 errors 列表
- **Go import relations**（`artifact_extractor.py`）：
  - `.go` 文件语言映射
  - `_parse_go_imports()` / `_resolve_go_import_target()`
  - 所有 Go import → `external:go:{module}`
  - import_kind 区分：go_import / go_import_alias / go_import_blank / go_import_dot
  - Step 2 不做 go.mod module path resolution
- **`test_go_extraction.py`**：27 tests
  - 15 Go 结构提取测试（function/method/struct/interface/import）
  - 5 Go import relation 测试
  - 2 Go 文件检测测试
  - 3 Go 全链路测试（index → artifact → relation → search）
  - 2 Provider 隔离测试（Python/TS 不受影响）
  - grammar 相关测试用 `skipif(_go_grammar_available)` 保护

### Added — Phase 7 Step 3: Go fixture 全链路验证

- **`tests/fixtures/go_project/`**：4 个 Go 源文件的磁盘 fixture 项目
  - `go.mod` — 模块声明（`github.com/example/goproject`）
  - `main.go` — 入口，import stdlib + 内部包
  - `pkg/models/user.go` — struct + methods
  - `pkg/models/types.go` — interfaces（Stringer / Validator）
  - `internal/service/user_service.go` — struct + methods + import models
- **`test_go_full_pipeline.py`**：26 tests（6 个 TestClass）
  - `TestGoFixtureExists`（4）：fixture 文件存在 + 源码不可变性检查
  - `TestGoFixtureIndexing`（4）：索引完整性 + language=go + 无源文件修改
  - `TestGoFixtureArtifacts`（4）：function / struct(class) / interface / module language
  - `TestGoFixtureImportRelations`（3）：relations 创建 + stdlib external + 内部包 external
  - `TestGoFixtureSearch`（4）：函数/结构体/接口/文件路径搜索
  - `TestGoFixtureProjectMap`（4）：map 生成 + language 统计 + modules + JSON 导出
  - `TestGoFixtureGraphValidation`（3）：validate 运行 + 无 error + stats 填充

### Added — Phase 7 Step 4: 真实 Go 项目验证（只读）

- **gnet-examples**（11 Go 文件）：13 function / 28 method / 12 class / 23 external dep，graph.validate 0 error 0 warning
- **feishu-cli**（1228 Go 文件）：8677 function / 928 method / 777 class / 40 interface，21 秒完成索引，0 error / 43 hotspot warning
- 验证 `smartdev index / search / impact` + project.map / graph.validate 对真实 Go 项目的端到端表现
- method receiver type 正确提取为 parent；stdlib + 第三方包归类为 `external:go:{module}`
- 验证产生的 `.smartdev/` 已清理，不污染外部项目
- 无代码变更（纯只读验证）

**Phase 7（Tree-sitter Go Provider）完成。**

### Changed

- `tree-sitter` + `tree-sitter-go` 已安装（optional dependency）
- Provider 链新增第三层：`TreeSitterProvider → go (confidence=0.98)`

### Test

- **458 passed, 1 skipped** — 测试基线（432 → 458，+26）

---

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

### Added — Phase 6.3 Step 1: Node Bridge 骨架（同日）

- **node_bridge/ 模块**：独立 Node 解析实验模块（`smartdev/context/node_bridge/`）
- **package.json**：@babel/parser 依赖，零其他 npm 依赖
- **extract_structure.js**：JSONL 协议，`--batch` 模式，`errorRecovery: true`
- **test_extract_structure.js**：6 场景 Node 侧测试（import/export/function/class/arrow/type）
- **README.md**：安装说明 + 协议文档
- 边界：不碰 Python，不碰索引链路

### Added — Phase 6.3 Step 2: Python NodeBridgeExtractor 集成（同日）

- **NodeBridgeProcess**：长期 Node 子进程单例管理，JSONL 协议通信，自动重启恢复
- **NodeBridgeExtractor**：实现 StructureExtractorProvider 接口，confidence=0.95
- **auto_detect_node**：StructureExtractor 初始化时自动检测 Node.js，可用时自动注册
- **三层 fallback**：Node 未安装 → 不注册；启动失败 → 静默跳过；单文件超时 → 返回空
- 新增 2 文件 + 修改 2 文件，22 tests（含 skipif 保护的真实集成测试）

### Added — Phase 6.3 Step 3: JS/TS 全链路验证（同日）

- **JS/TS import relation 构建**：`artifact_extractor.py` 新增 ES module import 解析，支持 7 种导入模式（named/default/namespace/side_effect/re-export/require/dynamic）
- **语言感知 dispatch**：`_build_import_relations()` 根据文件后缀自动选择 Python/JS/TS import 解析器
- **相对路径解析**：`./foo` / `../bar` 解析为 project 内路径，bare specifier 归类为 external
- **JS/TS 全链路集成测试**：18 tests 覆盖 index → search → project.map → graph.validate 端到端
- 修改 1 文件 + 新增 1 文件，无 breaking changes

### Changed

- `code:module` artifact 的 metadata 中 `language` 字段从硬编码 `"python"` 改为动态检测（`python`/`typescript`/`javascript`）

### Test

- 350 个测试全部通过（332 原有 + 18 新增）

### Added — Phase 6.3 Step 4.1: 排除 .d.ts 避免 Artifact 膨胀（同日）

- **跳过 .d.ts 文件**：`artifact_extractor.py` 增加 `.d.ts` 过滤（如 wrangler types 生成的声明文件）
- **scripts/verify_gateway.py**：真实项目 13 项指标收集脚本
- 修复：artifacts 756→78（-90%），全链路健康

### Added — Phase 6.3 Step 4.2: JS/TS Import Target 归一化（同日）

- **`_resolve_js_ts_import_target()`**：relative import 文件系统解析（ext + index 候选）
- **归一化到 `code:module:{path}`**：`../types` / `./types` / `../../types` → 同一 `code:module:src/types.ts`
- **`unresolved:relative_file_not_found`**：文件不存在的 import 明确标记
- **project_map hotspot 聚合**：按 resolved target_id 聚合而非 raw specifier
- **graph_validator 新增**：`unresolved_relative_import` warning
- 355 tests

### Added — Phase 6.3 Step 5: tsconfig paths alias 解析（同日）

- **`tsconfig_resolver.py`**：读取 `tsconfig.json` / `jsconfig.json` 的 `compilerOptions.paths` + `baseUrl`
- **精确匹配**：`@types → src/types.ts`
- **通配符匹配**：`@/* → src/*` → `@/lib/x → src/lib/x`
- **懒加载 + 缓存**：`_get_tsconfig_resolver()` 同一批次只读一次配置
- **graph_validator 新增**：`alias_target_not_found` warning
- 新增 `test_js_ts_path_alias.py`（15 tests）
- 370 tests

### Added — Phase 6.3 Step 3 补充: 磁盘 Fixture 全链路验证

- **`tests/fixtures/js_ts_project/`**：独立于 inline fixture 的磁盘项目
  - 7 个文件：`package.json` + `tsconfig.json` + 5 个 TS/TSX 源文件
  - 覆盖：interface, type alias, class, function, arrow function, import, re-export, JSX component
- **`TestJsTsFixtureProject`**（16 tests）：基于磁盘 fixture 的全链路验证
  - index → search → project.map → graph.validate 端到端
  - Node bridge Provider 注册 + TSX 命中验证
  - 源码不可变性验证
- **`TestJsTsFixtureNoNodeFallback`**（1 test）：Node 不可用时的 regex fallback 路径
- 395 tests（原有 370 + 25 新增）

### Fixed — Phase 6.3.1: CLI 测试基线修复

- **`test_cli.py` 修复**：`subprocess.run` 调用注入 `PYTHONPATH`，解决本地包未安装时的 `No module named smartdev` 错误
- **`_run_cli()` 辅助函数**：统一管理 CLI subprocess 调用的环境变量
- 7/7 CLI tests 通过，不再需要 `--ignore=tests/test_cli.py`
- 386 passed, 1 skipped — 全量测试基线清洁

### Changed

- Phase 6.3A 正式冻结：Node bridge (Babel) JS/TS 高置信度解析链路闭合，全量 386 tests 清洁基线

### Test（最终）

- **395 tests passed**（370 → 386，+16 fixture 验证测试 + 7 CLI 测试全部修复）
- 1 skipped（Node 不可用 fallback 测试，Node 可用时自动跳过）
- Phase 6.3 功能链路完整，测试基线清洁，正式冻结

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
