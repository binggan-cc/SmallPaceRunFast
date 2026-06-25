# SmartDev Agent

> **面向真实软件项目的本地开发智能层。**
> 把代码仓库从"文件集合"变成 AI Agent 可查询、可判断、可安全修改的项目系统。

```
SmartDev = 项目语义图谱 + Skill 执行层 + 风险控制 + 安全 Patch + MCP 工具出口
```

目标不是替代 Claude、Codex、Kiro、Cursor，而是给这些 Agent 提供可信的本地项目上下文和安全执行能力。

---

## 分层架构

```
L1  诊断层      repo.scan / tech_stack / docs_status / entrypoints
L2  规划层      task.plan / architecture.map / risk.check / qa.checklist
L3  语义层      code.index / code.search / code.impact / project.map / graph.validate
               多语言 Provider：Python(1.0) / JS-TS(0.95) / Go(0.98)
L3a Skill接入   risk.check ← impact / architecture.map ← index / task.plan ← impact
L4  执行层      code.patch(propose) → code.apply → code.rollback
L5  版本治理层  git.status / git.diff.explain / git.commit.plan / git.release.plan / git.merge.check（11A ✅）
               manifest / snapshot / doc.map / doc.consistency / doc.update.plan / doc.patch.propose（11C ✅）
               dev.guard / dependency.guard / security.review / change.budget / diff.explain / guard.runner（11B ✅）
L6  外部接入层  MCP Server v0 → 31 工具 → Claude / Kiro / Cursor / Codex（Phase 10 ✅）
L7  模型协作层  handoff pack / scope gate（11D ✅）→ model registry / task router（Phase 12，可选增强）
```

---

## 安装

```bash
cd smartPi/smartdev-agent
pip install -e .
```

技术栈：Python 3.10+，core 零外部依赖（mcp 为 optional dependency）。

---

## CLI 命令（26 条）

| 命令 | 说明 |
|------|------|
| `smartdev scan --project` | 仓库扫描（技术栈/文档状态/入口点）|
| `smartdev plan --project --task` | 任务规划（保守/推荐/深度三档方案）|
| `smartdev list` | 列出可用 Skill |
| `smartdev diagnose --project` | 项目诊断 |
| `smartdev run --project --task --target` | 运行指定 Skill |
| `smartdev run new <id> --project` | 创建 Run Artifact 目录 |
| `smartdev run scope-check <id> --changed-files` | 执行 Scope Gate 检查 |
| `smartdev run handoff-code <id>` | 生成 Code Agent Handoff Pack |
| `smartdev run handoff-doc <id>` | 生成 Doc Steward Handoff Pack |
| `smartdev run handoff-review <id>` | 生成 Reviewer Handoff Pack |
| `smartdev run context <id> --role` | 打印角色激活包到 stdout（可管道/复制给目标模型）|
| `smartdev run report <id> --tests --status` | Code Agent 完成后写回 agent-output/（changed-files / test-report / result）|
| `smartdev guard run --changed-files` | 运行全部 5 个 Guard（change.budget / dev.guard / dependency.guard / security.review / diff.explain）|
| `smartdev gate check --request-json` | 运行 gate.check v1 变更准入闸门 |
| `smartdev index --project --force` | 构建语义索引 |
| `smartdev search --project <query> --limit` | FTS5 代码搜索 |
| `smartdev impact --project <target> --depth` | 影响分析 |
| `smartdev mcp --project` | 启动 MCP Server |
| `smartdev git commit --project --message --files --apply` | 执行 Git 提交 |
| `smartdev git tag --project --version --message --apply` | 创建 Git Tag |
| `smartdev manifest diff --project --run-id --save` | 生成变更 manifest |
| `smartdev manifest last --project` | 查看最近 manifest |
| `smartdev manifest show --project <run_id>` | 查看指定 manifest |
| `smartdev snapshot skills --project --save` | 生成 Skill 能力快照 |
| `smartdev snapshot cli --project --save` | 生成 CLI 命令快照 |
| `smartdev snapshot mcp --project --save` | 生成 MCP 工具快照 |

---

## MCP Server 接入

```bash
smartdev mcp --project .
```

启动后通过 stdio transport 暴露 **31 个工具**：

| 权限级别 | 数量 | 工具 |
|---------|------|------|
| READ | 26 | ping / version / list_tools / code_search / code_impact / project_map / graph_validate / repo_scan / risk_check / architecture_map / task_plan / qa_checklist / git_status / git_diff_explain / git_commit_plan / git_release_plan / git_merge_check / doc_consistency / doc_update_plan / guard_run / change_budget / dev_guard / dependency_guard / security_review / diff_explain / gate_check |
| CACHE_WRITE | 4 | code_index / handoff_code / handoff_doc / handoff_review（只写 .smartdev/runs/）|
| PATCH_PROPOSE | 1 | patch_propose |

在 Claude / Kiro / Cursor / Codex 的 `mcp.json` 中配置即可接入。

---

## Skill 列表（27 个）

| Skill | 风险 | 说明 |
|-------|------|------|
| repo.scan | R0 | 仓库扫描 |
| task.plan | R0 | 任务规划（三档方案）|
| architecture.map | R0 | 架构分析 |
| token.audit | R0 | Token 审计 |
| risk.check | R0 | 风险检查 |
| qa.checklist | R0 | 验收清单 |
| code.search | R0 | FTS5 代码搜索 |
| code.impact | R0 | 影响分析 |
| doc.map | R0 | 文档地图 |
| doc.consistency | R0 | 文档一致性检查（5 条规则）|
| doc.update.plan | R0 | 文档更新计划 |
| git.status | R0 | Git 状态快照 |
| git.diff.explain | R0 | Diff 结构化解释 |
| git.commit.plan | R0 | Commit 拆分建议 |
| git.commit.message | R0 | Commit message 生成 |
| git.release.plan | R0 | Semver bump 建议 |
| git.merge.check | R0 | 合并前检查 |
| change.budget | R0 | 变更预算检查（文件数/行数/schema）|
| dev.guard | R0 | AI 编程规则守卫（mass refactor / protected paths）|
| dependency.guard | R0 | 依赖变更审查（added/removed/version-changed）|
| security.review | R0 | 安全审查清单（输入校验/路径遍历/命令注入/凭据）|
| diff.explain | R0 | Patch 级 diff 解释 |
| doc.generate | R1 | 文档草案生成 |
| code.patch | R1 | 代码补丁生成 |
| doc.patch.propose | R1 | 文档 patch 生成 |
| code.apply | R2 | 安全写盘执行 |
| code.rollback | R1 | 回滚 |

---

## Standalone 使用示例

无需启动 MCP Server、无需调用模型，纯本地 CLI 即可完成一次完整工程协作循环：

```bash
# 1. 创建任务
smartdev run new my-fix --project .

# 2. 模拟 Code Agent 完成后写回 agent-output
smartdev run report my-fix \
  --changed-files "smartdev/core/a.py" "tests/test_a.py" \
  --tests "echo 'all passed'" \
  --status completed \
  --project .

# 3. 生成三类 Handoff Pack
smartdev run handoff-code my-fix --project .
smartdev run handoff-doc my-fix --project .
smartdev run handoff-review my-fix --project .

# 4. 查看 Handoff Pack（可管道给 Claude/DeepSeek 等外部模型）
smartdev run context my-fix --role code-agent --project . | pbcopy
smartdev run context my-fix --role reviewer --project .

# 5. 运行 Guard 检查
smartdev guard run --changed-files "smartdev/core/a.py" "tests/test_a.py" --project .

# 6. Scope Gate 检查
smartdev run scope-check my-fix --changed-files "smartdev/core/a.py" "tests/test_a.py" --project .
```

---

## 当前状态

- **Phase**：Phase 11 已全部完成 — Standalone Hardened（11A / 11B / 11C / 11D ✅）
- **Version**：0.5.0
- **测试**：1925 passed，1 skipped
- **MCP 工具**：31 个（READ×26 + CACHE_WRITE×4 + PATCH_PROPOSE×1）
- **Skill**：27 个
- **CLI 命令**：26 条
- Phase 12（Model Router）为可选后续增强，非完整性前提

---

## 开发

```bash
# 运行全部测试
cd smartPi/smartdev-agent && python -m pytest tests/ -q
# 完整测试基线依赖 mcp extra；JS/TS pipeline 测试还依赖 Node bridge 环境。

# 构建语义索引
smartdev index --project .

# 启动 MCP Server
smartdev mcp --project .
```

详见 [CLAUDE.md](CLAUDE.md) 了解完整项目规则与执行协议。
