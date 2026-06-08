# Phase 11C — Documentation Governance v0 执行前设计

> 状态：设计文档（Step 0），不动代码
> 前置：Phase 11A Git Governance v0 完成（906 tests，19 个 MCP 工具）
> 定位：Doc Steward 工具链——让高阶模型能基于确定性事实检查文档一致性

---

## 1. 背景与定位

### 1.1 真实项目里的高频问题

Phase 11A 完成后，SmartDev 已能：
- 理解代码结构（L1–L3）
- 安全修改代码（L4）
- 治理提交记录（L5 via 11A）

但每次代码变更后，文档经常滞后或失真：

```
代码已经改了，但 README 没更新
Skill 已经新增，但 docs 里还写旧能力
Phase 已完成，但 CLAUDE.md / CHANGELOG / progress.md 状态不一致
CLI 参数变了，但使用示例没变
安全边界变了，但文档还在过度承诺
```

这类问题很适合高阶模型参与，因为它需要跨文件理解、抽象总结、一致性判断、能力边界表达。但模型必须基于 SmartDev 的**确定性事实**，而不是凭聊天记忆判断。

### 1.2 角色分工

```
高阶模型（Doc Steward）  →  判断文档是否一致、解释差异、生成更新建议
SmartDev               →  提供确定性事实上下文（project.map / skill snapshot / CLI snapshot / doc.map）
人                     →  确认是否 apply 文档 patch
```

这正好贴合 SmartDev 的核心原则：**AI 可以辅助，但不能夺走人的理解权、判断权和验收权。**

不靠聊天记忆协作，两个角色都读取同一份 SmartDev 结构化产物（run artifacts），通过 MCP 工具链共享上下文。

### 1.3 与现有 Phase 的关系

```
Phase 8   Context Layer ↔ Skill 接入（眼睛和大脑不再孤岛）
Phase 9   Safe Patch（propose / apply / rollback，任何修改都有安全边界）
Phase 11C Doc Governance（文档 patch 也走 propose / apply / rollback，不例外）
```

Phase 11C 是 Phase 9 Safe Patch 原则在文档层的延伸。

---

## 2. 核心定位

```
Doc Governance v0 = SmartDev 提供文档一致性检查的工具链
                  = 高阶模型的 Doc Steward 角色所需的事实基础设施
```

不是：

```
❌ 自动写文档的 Agent
❌ 自动 apply 文档变更
❌ 替代人审查文档
❌ LLM 生成的文档覆盖人工写的内容
❌ 只靠聊天记录同步文档状态
```

---

## 3. 两个模型的协作协议

### 3.1 协作流程

```
代码变更（commit / patch apply）
    ↓
SmartDev 生成 Change Manifest + capability snapshots
    ↓
高阶模型（Doc Steward）读取这些结构化产物
    ↓
调用 doc.consistency 检查规则
    ↓
输出 Doc Consistency Report
    ↓
调用 doc.update.plan 生成更新计划
    ↓
调用 doc.patch.propose 生成文档 patch（不落盘）
    ↓
人确认 apply
```

重点：**不是把聊天记录复制给另一个模型**，而是两个模型都读取同一份 SmartDev 事实产物。

### 3.2 Code Agent 输出格式（Change Manifest）

```json
{
  "run_id": "2026-06-xx-phase-11a-step-7",
  "changed_files": [
    "smartdev/mcp/tools.py",
    "smartdev/mcp/server.py",
    "tests/test_mcp_git_tools.py"
  ],
  "change_type": "feature",
  "risk_level": "R1",
  "public_surface_changed": true,
  "cli_changed": false,
  "skill_changed": false,
  "mcp_changed": true,
  "docs_likely_needed": true,
  "validation": ["python -m pytest tests/test_mcp_git_tools.py -q"]
}
```

### 3.3 Doc Steward 输入格式

```json
{
  "change_manifest": "...",
  "project_map": "...",
  "skill_snapshot": "...",
  "cli_snapshot": "...",
  "doc_map": "..."
}
```

### 3.4 Doc Steward 输出格式

```json
{
  "docs_required": true,
  "issues": [
    {
      "doc": "README.md",
      "type": "stale_capability",
      "code_fact": "MCP has 19 tools including 5 git tools",
      "doc_claim": "MCP Server v0 has 14 tools",
      "severity": "medium"
    }
  ],
  "update_plan": [...],
  "patch_proposals": [...],
  "human_review_required": true
}
```

---

## 4. 五种结构化上下文

### 4.1 Change Manifest（新建）

每次 `code.apply` 或 `git commit` 执行后生成，写入 `.smartdev/runs/`：

```json
{
  "run_id": "string",
  "timestamp": "ISO",
  "changed_files": ["path"],
  "change_type": "feature | fix | refactor | docs | test",
  "risk_level": "R0 | R1 | R2 | R3",
  "public_surface_changed": true,
  "cli_changed": false,
  "skill_changed": true,
  "mcp_changed": false,
  "docs_likely_needed": true,
  "validation": ["pytest command"]
}
```

### 4.2 Project Map（已有）

`project.map` + `architecture-summary` + `graph.validate` 输出。高阶模型用它理解项目结构，不需要重新猜。

### 4.3 Skill Registry Snapshot（新建）

从 `Skill.get_registry()` + `skill.yaml` 导出：

```json
{
  "generated_at": "ISO",
  "skill_count": 18,
  "skills": [
    {
      "name": "git.status",
      "risk": "R0",
      "task_type": "diagnose",
      "description": "查询 git 状态...",
      "inputs": ["project_path", "recent_commit_count"],
      "outputs": ["branch", "is_dirty", "staged", "unstaged", "untracked"]
    }
  ]
}
```

### 4.4 CLI Capability Snapshot（新建）

从 `cli.py` argparse 结构内省导出：

```json
{
  "generated_at": "ISO",
  "commands": [
    {
      "command": "smartdev git commit",
      "description": "创建 git commit（默认 dry-run；--apply 才写 Git 历史）",
      "args": ["--message", "--files", "--apply", "--project"]
    }
  ]
}
```

### 4.5 Doc Map（新建）

轻量文档索引——知道"该检查哪些文档"：

```json
{
  "generated_at": "ISO",
  "docs": [
    {
      "path": "README.md",
      "headings": ["Overview", "Usage", "Capabilities", "MCP Tools"],
      "mentions": ["Phase 10", "MCP", "14 tools", "patch.propose"],
      "last_modified": "ISO"
    },
    {
      "path": "CHANGELOG.md",
      "latest_version": "Unreleased",
      "latest_section": "Phase 11A Step 7"
    },
    {
      "path": "CLAUDE.md",
      "mentions": ["Phase 10", "637 tests", "MCP Server v0"]
    }
  ]
}
```

---

## 5. 五条确定性检查规则

高阶模型基于这些规则判断，不靠"感觉"。

### 规则 1：代码能力 vs 文档描述

如果新增了 Skill / CLI command / MCP tool，文档中对应能力章节是否提到？

- 触发条件：`skill_snapshot.skill_count` > `doc_map mentions Skill 数量`
- 触发条件：`cli_snapshot.commands` 中有 `doc_map` 未提及的命令
- 输出：`stale_capability` issue

### 规则 2：Phase 状态一致性

检查以下文件对当前阶段状态的描述是否一致：
CHANGELOG / CLAUDE.md / docs/progress.md / phase-x-design.md / README

- 触发：`progress.md` 写 Phase 10 完成，但 `CLAUDE.md` 仍写"Phase 10 planned"
- 触发：`CHANGELOG` 最新版本号与 `pyproject.toml` `version` 不符
- 输出：`phase_status_mismatch` issue

### 规则 3：能力边界一致性

如果设计文档写"不支持 patch.apply in MCP"，但 README 或 MCP README 暗示可以 apply：

- 触发：design doc 写 `❌ 不做 X`，但 doc_map mentions 包含 X 的能力声明
- 输出：`capability_overpromise` issue（严重度 high）

### 规则 4：测试基线一致性

```
code_fact: 当前实际测试数（从最近 pytest 输出或 progress.md 读取）
doc_claim: progress.md 测试基线行写的数字
```

- 触发：两者不一致
- 输出：`stale_test_baseline` issue（严重度 low）

### 规则 5：公共接口变化后的文档检查

如果变更了以下文件：`cli.py` / `mcp/tools.py` / `skill.yaml` / `pyproject.toml`

- 必须检查：README / CHANGELOG / CLAUDE.md 是否同步更新
- 输出：`public_surface_changed_docs_not_updated` issue

---

## 6. 高阶模型的职责边界

### 适合做：

1. 判断文档是否过时（基于 SmartDev 事实）
2. 判断文档是否过度承诺（vs 设计文档的"不做"清单）
3. 判断代码能力和文档描述是否一致
4. 生成更清楚的能力边界说明
5. 统一 README / CHANGELOG / progress 的表达口径
6. 审查 phase 文档是否有"为了修改而修改"

### 不适合做（永远不做）：

1. 自己决定修改源码
2. 自己 apply 文档 patch
3. 自己修改版本号
4. 自己删除历史文档
5. 自己合并 phase 状态

---

## 7. 实施路线（Phase 11C）

```
Step 0  设计文档 phase-11c-design.md（本文档）                 ✅ 当前

Step 1  Change Manifest 生成（R0，确定性）
        - ChangeManifest 数据模型
        - code.apply / git commit 执行后自动写入 .smartdev/runs/
        - CLI: smartdev manifest --last / --run-id

Step 2  Capability Snapshot 导出（R0，确定性）
        - skill_snapshot: 从 Skill.get_registry() + skill.yaml 导出 JSON
        - cli_snapshot: 从 argparse 结构内省导出 JSON
        - MCP 工具 snapshot: 从 mcp/server.py _TOOLS 导出 JSON
        - CLI: smartdev snapshot skills / cli / mcp

Step 3  doc.map Skill（R0，只读）
        - 扫描 docs/ + README.md + CHANGELOG.md + CLAUDE.md
        - 提取 headings / mentions / last_modified
        - 输出结构化 doc_map JSON

Step 4  doc.consistency Skill（R0，只读）
        - 5 条确定性规则检查
        - 输入：skill_snapshot + cli_snapshot + doc_map + change_manifest
        - 输出：issues 列表（type / severity / code_fact / doc_claim）

Step 5  doc.update.plan Skill（R0，只读）
        - 消费 doc.consistency 输出
        - 输出：哪些文档需要改 / 为什么 / 不应该改哪些
        - 区分：状态同步 vs 能力边界 vs 表达口径

Step 6  doc.patch.propose（R1，不落盘）
        - 生成文档 patch（复用 Phase 9 的 find-replace patch 模型）
        - patch_id 持久化到 .smartdev/patches/
        - 不自动 apply

Step 7  MCP 暴露只读工具
        - smartdev_doc_consistency
        - smartdev_doc_update_plan
        - 不暴露 doc.patch.propose（写文档需要人确认）
```

---

## 8. 风险等级

| Step | 风险 | 说明 |
|------|------|------|
| Step 0 | R0 | 设计文档 |
| Step 1 | R1 | 新增运行时写入 .smartdev/runs/（只写 cache，不动源码）|
| Step 2 | R0 | 纯读取内省，不修改任何文件 |
| Step 3 | R0 | 只读扫描 |
| Step 4 | R0 | 只读检查 |
| Step 5 | R0 | 只读规划 |
| Step 6 | R1 | 生成文档 patch，不落盘 |
| Step 7 | R1 | MCP 暴露只读工具 |

---

## 9. Phase 11C 不做的事

```
❌ 不自动 apply 文档 patch
❌ 不自动调用 LLM 生成文档内容
❌ 不替代人审查文档
❌ 不删除历史文档
❌ 不修改版本号
❌ 不做自动多模型流水线（Phase 12 范围）
❌ 不做"自动文档 Agent"（第一版只做工具链，Agent 是第二版）
```

---

## 10. 与 Phase 12 的关系

Phase 11C 完成后，Phase 12（Model Collaboration Layer）可以把 Doc Steward 作为一个可注册的**角色（role）**纳入：

```
Phase 12 模型协作角色表：
  Planner    → 高阶推理模型，需求 / 方案 / 边界
  Coder      → 编码模型，patch propose
  Reviewer   → 高阶模型，风险 / 架构 / 安全
  Doc Steward → 高阶模型，文档一致性 / 能力边界（Phase 11C 提供工具链）
  Tester     → 中等模型 + SmartDev 工具，测试建议
```

Phase 11C 先把 Doc Steward 的工具链做出来，Phase 12 直接用，不需要重造。

---

## 11. 验收标准（Phase 11C）

1. 代码变更后 `smartdev manifest` 能输出结构化 Change Manifest
2. `smartdev snapshot skills` 输出与 `Skill.get_registry()` 完全一致的 JSON
3. `smartdev snapshot cli` 输出与 `cli.py` argparse 结构一致
4. `doc.map` 能正确扫描项目文档，提取 headings 和 mentions
5. `doc.consistency` 能检出规则 1–5 的各类 issue
6. `doc.update.plan` 输出按文档分组的更新计划（含"不应改"判断）
7. `doc.patch.propose` 生成文档 patch，patch_id 持久化，不修改任何文档
8. MCP 工具 `smartdev_doc_consistency` / `smartdev_doc_update_plan` 可正常调用
9. 高阶模型（通过 MCP）能读取所有结构化上下文并生成 Doc Consistency Report
10. 全量测试无回归
