# Phase 11D — Collaboration Handoff v0 执行前设计

> 状态：Step 1–7 已完成
> 前置：Phase 11C Documentation Governance v0（必须先产出事实层）
> 定位：多模型协作交接层——把 SmartDev 的工程事实裁剪成角色化上下文包，并把模型输出回流到 run artifact

---

## 1. 定位

```
Collaboration Handoff v0 = 基于 SmartDev 的 run artifacts，
                           为不同模型角色生成裁剪后的上下文包，
                           降低 token 消耗，并保证协作基于同一份工程事实
```

一句话：**11C 负责产出可信事实，11D 负责把可信事实裁剪给不同模型。先有事实层，再有协作层。**

不是：

```
❌ 让两个模型在聊天里来回切换
❌ 给每个模型喂完整仓库
❌ 让模型共享聊天记忆
❌ 自动多模型流水线（Phase 12 范围）
```

而是：

```
Claude/Codex  ←  SmartDev Run Artifacts  →  DeepSeek
（Doc Steward）      （单一事实源）          （Code Agent）
```

---

## 2. 与 Phase 11C 的边界

| 维度 | Phase 11C（Documentation Governance）| Phase 11D（Collaboration Handoff）|
|------|------|------|
| 职责 | **生产**确定性事实 | **组装**事实给角色消费 |
| 产物 | change_manifest / snapshots / doc_map / doc.consistency | code-agent-pack / doc-steward-pack / reviewer-pack |
| 核心问题 | 文档与代码是否一致 | 不同模型如何不共享聊天记录而协作 |
| 别名 | 文档治理事实层 | 多模型协作交接层 |

**为什么不能合并：** `handoff doc` 依赖 11C 的全部产物（change_manifest / snapshot / doc.map / doc.consistency / doc.update.plan）。没有 11C，handoff 只能拼原始文档和聊天记录，退回"喂一大坨上下文"的老问题。

正确顺序：

```
Phase 11C：先把事实产物做出来
    ↓
Phase 11D：再把事实产物裁剪成角色上下文包
```

---

## 3. 角色与权限矩阵

| 角色 | 推荐模型 | 做什么 | 不做什么 |
|------|---------|--------|---------|
| **Code Agent** | DeepSeek / 便宜 coding 模型 | 小范围代码实现、补测试、修 bug、patch propose | 不改阶段文档、不做大范围架构判断、不做 release 判断 |
| **Doc Steward** | Claude Code / Codex / 高阶模型 | 审查文档与代码一致性、能力边界、Phase 状态、CHANGELOG/README、commit plan | 不直接改核心代码、不扩大功能范围、不执行 apply/commit |
| **Reviewer** | 高阶模型 | 风险 / 架构 / 安全审查 | 不改代码、不 apply |
| **SmartDev** | 本地工具层 | project.map / impact / diff / patch / validate / git 状态 + 上下文裁剪 + 风险门 | 不替人决定是否合并 |
| **Human** | — | 确认边界、验收、apply、commit、release | 不被模型拖着走 |

### 权限细则

**Code Agent**
- 允许：code.search / code.impact / task.plan / patch.propose / 测试建议
- 不允许：改 docs/progress / 改 CHANGELOG / git commit / git tag / patch.apply

**Doc Steward**
- 允许：doc.consistency / doc.update.plan / doc.patch.propose / diff.explain / project.map / skill snapshot
- 不允许：改核心源码 / patch.apply / git commit / 扩大功能范围

**Human（保留）**
- apply / commit / tag / merge / release / R3 确认

---

## 4. Run Artifact 目录约定

每个任务一个 run_id，**完整生命周期产物**集中在一个目录：

```
.smartdev/runs/<run_id>/
├── task-card.md            # Human 创建：任务目标 / 范围 / 不做 / 验收
├── scope.json              # 允许 / 禁止修改的路径
│
├── handoff/                # 【输入层】SmartDev 生成，模型只读
│   ├── code-agent-pack.md      # 给 Code Agent 的实现包（≤ 8k token）
│   ├── doc-steward-pack.md     # 给 Doc Steward 的审查包（≤ 6k token）
│   └── reviewer-pack.md        # 给 Reviewer 的风险包（≤ 10k token）
│
├── agent-output/           # 【执行层】Code Agent 写回，Doc Steward 读取
│   ├── code-agent-result.md    # Code Agent 写：实现说明 / 变更文件 / 测试结果
│   ├── changed-files.txt       # Code Agent 写：机器可读，一行一个文件路径
│   ├── test-report.txt         # Code Agent 写：pytest 原始输出
│   └── open-questions.md       # Code Agent 写：遇到的问题 / 需要决策的点
│
└── review/                 # 【审查层】Doc Steward / Reviewer 写回，Human 读取
    ├── doc-steward-review.md   # Doc Steward 写：文档一致性分析
    ├── scope-gate.md           # SmartDev 自动生成：scope-check 结构化结果
    └── commit-readiness.md     # Doc Steward 写：Human 最终看这个文件决策
```

**三层职责划分：**

| 目录 | 谁写 | 谁读 | 时机 |
|------|------|------|------|
| `handoff/` | SmartDev 工具生成 | Code Agent / Doc Steward / Reviewer | Code Agent 开始工作前 |
| `agent-output/` | Code Agent 写回 | Doc Steward / SmartDev | Code Agent 完成后 |
| `review/` | Doc Steward 写回 | Human | Doc Steward 审查完成后 |

**核心原则：模型之间不共享聊天记录，只共享 run artifact 文件。**

这些是**运行产物**，不是长期文档。`.smartdev/` 已被 gitignore，不污染仓库。

---

## 5. 三个 Handoff Pack

所有 pack **只生成 markdown，不调用任何模型**——保持 SmartDev 模型中立。

### 5.1 code-agent-pack.md（token ≤ 8k）

给 Code Agent 的"实现包"，只给实现所需，不给全仓库：

```
1. 当前任务
2. 修改范围（允许 / 不允许）
3. 相关文件列表 + 关键代码片段（不是完整仓库）
4. impact 结果
5. existing patterns（参考的同类实现）
6. 验收标准
7. 禁止项
```

Code Agent 的输出固定为：改了哪些文件 / 每个为什么改 / 测试命令和结果 / 未完成项 / 是否需要文档更新。

### 5.2 doc-steward-pack.md（token ≤ 6k）

给 Doc Steward 的"审查包"，只给变更事实，不给全源码：

```
1. change_manifest
2. diff_summary
3. test_report
4. skill / cli / mcp snapshot
5. doc_map（相关文档片段）
6. 当前 Phase 状态
7. doc.consistency issues
8. 需要检查的一致性问题
```

Doc Steward 输出：docs_required / issues / update_plan / patch_propose_only。

### 5.3 reviewer-pack.md（token ≤ 10k）

给 Reviewer 的"风险审查包"：

```
1. risk + impact
2. changed_files
3. test_report
4. dependency changes
5. security checklist
6. git.diff.explain
```

---

## 6. Scope Gate（11D 唯一真正新增的核心）

5 个 Gate 大部分已由前序 Phase 提供，11D 只新增 Scope Gate，其余是聚合接线：

| Gate | 现状 | 11D 工作 |
|------|------|---------|
| **Scope Gate** | 🆕 新建 | 对比 changed_files vs scope.json |
| Impact Gate | ✅ code.impact（Phase 6+）| 聚合 |
| Test Gate | 半成品 | 解析测试结果并入 change_manifest |
| Doc Gate | ✅ doc.consistency（Phase 11C）| 聚合 |
| Git Gate | ✅ git.merge.check（Phase 11A）| 聚合 |

### Scope Gate 检查逻辑

```
changed_files vs scope.json 判断：
- 是否改了 scope 外文件
- 是否碰 protected path
- 是否超过 max_files（change.budget）
- 是否混入 docs / tests / core 无关变更
```

命中任一 → 输出 violation，要求 Code Agent 解释或拒绝。

---

## 7. 协作流程

### 流程 A：普通 R1 开发任务（顺序协作）

```
Human 只说一句话：开始/继续 <run_id>，用双模型协作
    ↓
Doc Steward（Codex/Claude）：
  smartdev run new <run_id>（如需新建）
  smartdev run handoff-code <run_id>
  → 生成 handoff/code-agent-pack.md
    ↓
Human 给 Code Agent 一行指令：
  读取并执行 .smartdev/runs/<run_id>/handoff/code-agent-pack.md
  完成后把结果写入 .smartdev/runs/<run_id>/agent-output/
    ↓
Code Agent（DeepSeek）：
  读取 handoff/code-agent-pack.md
  实现代码 + 跑测试
  写入 agent-output/code-agent-result.md
         agent-output/changed-files.txt
         agent-output/test-report.txt
         agent-output/open-questions.md（如有）
  聊天里只回复：已完成，结果写入 agent-output/code-agent-result.md
    ↓
Human 给 Doc Steward 一行指令：
  Code Agent 已写回 agent-output，继续审查。
    ↓
Doc Steward（Codex/Claude）：
  读取 agent-output/ + git diff + handoff/doc-steward-pack.md
  写入 review/doc-steward-review.md
         review/scope-gate.md（或调用 SmartDev scope-check）
         review/commit-readiness.md
  聊天里只回复：审查完成，结论见 review/commit-readiness.md
    ↓
Human 读取 review/commit-readiness.md
  → 决定：apply + commit / 返工 / 拆分 / 放弃
```

**关键原则：Human 只做决策，不搬运内容。每一轮模型交接都通过文件，不通过聊天复制粘贴。**

### 流程 B：R2/R3 高风险任务（并行审查）

```
SmartDev task.plan + impact + risk.check
    ↓
Reviewer / Doc Steward 提前审查方案边界（代码前介入）
写入 review/doc-steward-review.md（方案审查版本）
    ↓
Human 确认范围（读取 review/，做决策）
    ↓
Code Agent 执行小 patch
写入 agent-output/
    ↓
SmartDev validate（scope-check + doc.consistency）
    ↓
Doc Steward 审查文档和规格
写入 review/commit-readiness.md
    ↓
Human 确认 apply / commit
```

高风险任务在**写代码前**让 Reviewer/Doc Steward 参与，但仍通过文件协作，不靠对话。

---

## 8. 实施路线（Phase 11D）

```
Step 0  设计文档 phase-11d-design.md（本文档）                   ✅ 完成

Step 1  Run Artifact 目录约定（R1）                              ✅ 完成
        - .smartdev/runs/<run_id>/ 结构
        - task-card.md / scope.json schema
        - CLI: smartdev run new <id>

Step 2  Scope Gate（R0 只读）                                    ✅ 完成
        - changed_files vs scope.json 对比
        - protected path / max_files / 无关变更检查

Step 3  handoff code（R1，只写 .smartdev/runs/）                 ✅ 完成
        - 组装 code-agent-pack.md（token ≤ 8k）
        - Role Activation Preamble（角色激活前言）

Step 4  handoff doc（R1，只写 .smartdev/runs/）                  ✅ 完成
        - 组装 doc-steward-pack.md（token ≤ 6k）
        - 依赖 11C 的 change_manifest / snapshot / doc.consistency
        - Role Activation Preamble

Step 5  handoff review + Role Activation + run context          ✅ 完成
        - 组装 reviewer-pack.md（token ≤ 10k）+ Role Activation Preamble
        - smartdev run context <run_id> --role <role>（打印 pack 到 stdout）
        - --info 模式：元信息 + 建议生成命令

Step 6  Agent Output & Review Artifact Protocol                  ✅ 完成
        - 固定 agent-output/ 目录文件协议（Code Agent 输出规范）
        - 固定 review/ 目录文件协议（Doc Steward 输出规范）
        - doc-steward-pack 扩展消费 agent-output/（可选）
        - 可选：smartdev run report / smartdev run review 命令骨架

Step 7  MCP 暴露 handoff pack 工具                              ✅ 完成
        - smartdev_handoff_code / smartdev_handoff_doc / smartdev_handoff_review
        - 只写 .smartdev/runs/<run_id>/handoff/，不改源码
        - 不包含 smartdev_run_read / smartdev_run_write（后续单独任务）
```

---

## 9. 三阶段演进（不要一上来做复杂多模型）

| 模式 | 说明 | 时机 |
|------|------|------|
| **模式 A：Manual Dual-Model Handoff** | 人手动维护 run 目录，DeepSeek 看 code pack，Claude 看 doc pack | **现在就能用**（不依赖 11D 代码）|
| **模式 B：MCP 协作** | 两个模型都通过 MCP 调 SmartDev，共享 .smartdev/runs | Phase 11D 完成后 |
| **模式 C：Model Router** | SmartDev 自动决定用哪个模型、给什么上下文、输出什么 contract | Phase 12 |

**先把模式 A 跑顺，再做模式 B，最后才是模式 C。不要反过来一开始就做自动多模型。**

---

## 10. Token 经济（核心价值）

三条原则：

1. **给 Code Agent 少文档多代码片段**：不塞完整 README/CHANGELOG/phase 文档/对话历史
2. **给 Doc Steward 少源码多变更事实**：不塞完整源码/所有测试文件/上下文历史
3. **中间交接用结构化 JSON**：比复制聊天记录可靠且省 token

模型使用策略：

| 任务 | 模型 | 上下文 |
|------|------|--------|
| 小代码实现 | DeepSeek | 4–8k |
| 测试补充 | DeepSeek | 3–6k |
| 文档一致性 | Claude/Codex | 3–6k |
| 架构方案审查 | Claude/Codex | 6–10k |
| 安全审查 | Claude/Codex | 4–8k |
| commit plan / diff / impact | SmartDev 确定性工具 | 不用模型 token |

**原则：确定性工具能做的，不花模型 token。**

---

## 11. Phase 11D 不做的事

```
❌ 两个模型互相长对话
❌ 给两个模型喂完整仓库
❌ 让 Doc Steward 直接改源码
❌ 让 Code Agent 直接改 CHANGELOG / progress
❌ 让任一模型自动 commit
❌ 让任一模型自动 apply R2/R3 patch
❌ 每个小文件都切模型审一次
❌ handoff 工具自己调用模型（只生成 pack，不调模型）
❌ 自动 Model Router（Phase 12 范围）
```

---

## 12. 整体路线

```
Phase 11A：Git Governance v0          ✅ 完成
    ↓
Phase 11C：Documentation Governance v0  ← 当前进入实现
    ↓
Phase 11D：Collaboration Handoff v0     ← 本文档，独立建档，暂不实现
    ↓
Phase 11B：Guard Skills（可稍后增强）
    ↓
Phase 12：Model Collaboration Router
```

> 顺序调整说明：原计划 11A→11B→11C，但当前已在实际使用双模型协作，Doc Steward 需求更急，Guard Skills 可稍后。故调整为 **11A → 11C → 11D → 11B → 12**。

---

## 13. 验收标准（Phase 11D）

### Step 1–5 已完成验收

1. ✅ `smartdev run new <id>` 创建标准 run 目录结构
2. ✅ Scope Gate 能检出 scope 外文件 / protected path / 超 max_files / 无关变更
3. ✅ `smartdev run handoff-code` 生成 ≤ 8k 的 code-agent-pack.md（含角色激活前言）
4. ✅ `smartdev run handoff-doc` 生成 ≤ 6k 的 doc-steward-pack.md（消费 11C 产物，含角色激活前言）
5. ✅ `smartdev run handoff-review` 生成 ≤ 10k 的 reviewer-pack.md（含角色激活前言）
6. ✅ `smartdev run context <id> --role` 打印对应 pack 到 stdout
7. ✅ 所有 handoff 命令只写 .smartdev/runs/，不修改源码
8. ✅ handoff 命令不调用任何模型

### Step 6 验收标准（当前目标）

9. agent-output/ 目录协议文档化（本文档 §14）
10. review/ 目录协议文档化（本文档 §15）
11. `code-agent-result.md` 有固定可解析结构
12. `commit-readiness.md` 有固定可解析结构，Human 看一眼能做决策
13. 模式 A（手动文件交接）流程可端到端走通，Human 全程不需要复制聊天内容

### Step 7 验收标准（已完成）

14. ✅ MCP 工具 smartdev_handoff_code / doc / review 可正常调用
15. ✅ 全量测试无回归（1436 passed, 1 skipped）

---

## 14. Code Agent 输出协议（agent-output/）

> 适用场景：Code Agent 完成任务后，把结果写回 run artifact。
> 聊天里只说一句话，细节全在文件里。

### 14.1 目录结构

```
.smartdev/runs/<run_id>/agent-output/
├── code-agent-result.md    # 必须：实现说明 / 变更文件 / 测试结果
├── changed-files.txt       # 必须：机器可读，一行一个文件路径
├── test-report.txt         # 必须：pytest 原始输出（直接复制终端）
└── open-questions.md       # 可选：遇到的问题 / 需要决策的点
```

### 14.2 code-agent-result.md 固定结构

```markdown
# Code Agent Result — <run_id>

## Status
completed / blocked / partial

## Implemented
- 简要说明实现了什么（每项一行）

## Changed Files
| 文件 | 操作 | 原因 |
|------|------|------|
| smartdev/core/xxx.py | 新增 | 实现 xxx 功能 |
| tests/test_xxx.py    | 新增 | 覆盖 xxx 功能 |

## Tests
Command:
```bash
python -m pytest tests/test_xxx.py -v
```
Result: X passed, Y failed, Z skipped

## Open Questions
- （如果没有，写"无"）
```

### 14.3 changed-files.txt 格式

机器可读，SmartDev scope-check 和 doc-steward-pack 可直接消费：

```
smartdev/skills/xxx/skill.py
smartdev/skills/xxx/skill.yaml
tests/test_xxx.py
```

每行一个相对于项目根目录的文件路径，不含空行、不含注释。

### 14.4 聊天里只说这一句

```
已完成。结果写入：
.smartdev/runs/<run_id>/agent-output/code-agent-result.md
测试结果：
.smartdev/runs/<run_id>/agent-output/test-report.txt
```

不要在聊天里贴完整代码、完整测试输出或长篇总结。

### 14.5 现实限制

| 场景 | 处理方式 |
|------|---------|
| 本地 Agent（Codex CLI / Claude Code）有文件系统权限 | 直接写 .smartdev/runs/<run_id>/agent-output/ |
| 网页 DeepSeek / 无本地文件权限 | 按结构模板回复，Human 把短结果保存到 agent-output/ |
| 未来 MCP 接入 | smartdev_run_write 工具直接写入，不经过 Human |

---

## 15. Doc Steward 输出协议（review/）

> 适用场景：Doc Steward 审查完 agent-output/ 和 git diff 后，把结论写回 run artifact。
> Human 只看 commit-readiness.md，不需要读完整审查报告。

### 15.1 目录结构

```
.smartdev/runs/<run_id>/review/
├── commit-readiness.md     # 必须：Human 最终决策文件
├── doc-steward-review.md   # 必须：文档一致性完整分析
└── scope-gate.md           # 可选：SmartDev scope-check 格式化结果
```

### 15.2 commit-readiness.md 固定结构

这是 Human 的**唯一决策输入**，必须简洁可扫描：

```markdown
# Commit Readiness — <run_id>

## Decision
ready_for_human_commit / needs_fix / blocked

## Required Fixes（needs_fix 时填写）
- 文件 X：需要更新 Y（说明原因）

## Gates
| Gate | 状态 | 说明 |
|------|------|------|
| Scope Gate | ✅ passed / ❌ failed | 变更文件在 scope 内 |
| Test Gate  | ✅ passed / ❌ failed | X passed, Y failed |
| Doc Gate   | ✅ passed / ⚠ warning | issue 列表见 doc-steward-review.md |

## Documentation Status
- CHANGELOG.md: no change needed / update required（说明内容）
- README.md: no change needed / update required（说明内容）
- development-progress.md: update required（测试基线 X → Y）

## Suggested Commits
1. feat(scope): <主要变更描述>
2. docs(progress): 更新测试基线和阶段状态

## Human Decision Needed
- （如果没有，写"无，可直接提交"）
```

### 15.3 聊天里只说这一句

```
Doc Steward 审查完成。
结论：ready_for_human_commit / needs_fix
详情见：.smartdev/runs/<run_id>/review/commit-readiness.md
```

不要在聊天里贴完整 doc.consistency 输出、完整 diff 分析或长篇文档建议。

### 15.4 Doc Steward 的读取顺序

Doc Steward 在审查时按以下顺序读取，不需要 Human 传递任何内容：

```
1. .smartdev/runs/<run_id>/agent-output/code-agent-result.md
2. .smartdev/runs/<run_id>/agent-output/changed-files.txt
3. .smartdev/runs/<run_id>/agent-output/test-report.txt
4. .smartdev/runs/<run_id>/handoff/doc-steward-pack.md（11C 事实）
5. git diff（通过 SmartDev git.diff.explain 或直接读）
```

不需要 Human 再次解释"DeepSeek 做了什么"——这些文件已经是完整事实。
