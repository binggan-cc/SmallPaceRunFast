# Phase 11D — Collaboration Handoff v0 执行前设计

> 状态：设计文档（Step 0），**暂不进入实现**
> 前置：Phase 11C Documentation Governance v0（必须先产出事实层）
> 定位：多模型协作交接层——把 SmartDev 的工程事实裁剪成角色化上下文包

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

每个任务一个 run_id，所有协作产物集中在一个目录：

```
.smartdev/runs/<run_id>/
├── task-card.md            # 人创建的任务卡片（目标/范围/不做/验收）
├── scope.json              # 允许 / 禁止修改的路径
├── change-manifest.json    # 11C 产出
├── diff-summary.json       # git.diff.explain 产出
├── impact.json             # code.impact 产出
├── test-report.json        # 测试结果
├── doc-consistency.json    # 11C 产出
├── git-commit-plan.json    # git.commit.plan 产出
└── handoff/
    ├── code-agent-pack.md
    ├── doc-steward-pack.md
    └── reviewer-pack.md
```

这些是**运行产物**，不是长期文档，不算"为了文档而文档"。它们的作用是让不同模型共享同一套事实。`.smartdev/` 已被 gitignore，不污染仓库。

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
Human 创建 task-card
    ↓
SmartDev 生成 code-agent-pack
    ↓
Code Agent（DeepSeek）实现代码
    ↓
SmartDev 跑测试 + git.diff.explain + Scope Gate + change_manifest
    ↓
SmartDev 生成 doc-steward-pack
    ↓
Doc Steward（Claude/Codex）审查文档一致性
    ↓
SmartDev 生成 doc.patch.propose
    ↓
Human 确认 apply + commit
```

**先代码，再审查，再文档，再提交。不要每改一个文件就切一次模型。**

### 流程 B：R2/R3 高风险任务（并行审查）

```
SmartDev task.plan + impact + risk.check
    ↓
Reviewer / Doc Steward 提前审查方案边界（代码前介入）
    ↓
Human 确认范围
    ↓
Code Agent 执行小 patch
    ↓
SmartDev validate
    ↓
Doc Steward 审查文档和规格
    ↓
Human 确认 apply / commit
```

高风险任务在**写代码前**让 Reviewer/Doc Steward 参与，但仍通过 task.json / scope.json / impact.json 协作，不靠对话。

---

## 8. 实施路线（Phase 11D）

```
Step 0  设计文档 phase-11d-design.md（本文档）          ✅ 当前（暂不实现）

Step 1  Run Artifact 目录约定（R1）
        - .smartdev/runs/<run_id>/ 结构
        - task-card.md / scope.json schema
        - CLI: smartdev run new <id>

Step 2  Scope Gate（R0 只读）
        - changed_files vs scope.json 对比
        - protected path / max_files / 无关变更检查

Step 3  handoff code（R1，只写 .smartdev/runs/）
        - 组装 code-agent-pack.md（token ≤ 8k）

Step 4  handoff doc（R1，只写 .smartdev/runs/）
        - 组装 doc-steward-pack.md（token ≤ 6k）
        - 依赖 11C 的 change_manifest / snapshot / doc.consistency

Step 5  handoff review（R1，只写 .smartdev/runs/）
        - 组装 reviewer-pack.md（token ≤ 10k）

Step 6  MCP 暴露只读 handoff 工具
        - smartdev_handoff_code / smartdev_handoff_doc / smartdev_handoff_review
        - 只读 + 写 .smartdev/runs/<run_id>/handoff/，不改源码
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

## 13. 验收标准（Phase 11D，实现时适用）

1. `smartdev run new <id>` 创建标准 run 目录结构
2. Scope Gate 能检出 scope 外文件 / protected path / 超 max_files / 无关变更
3. `smartdev handoff code` 生成 ≤ 8k 的 code-agent-pack.md
4. `smartdev handoff doc` 生成 ≤ 6k 的 doc-steward-pack.md（消费 11C 产物）
5. `smartdev handoff review` 生成 ≤ 10k 的 reviewer-pack.md
6. 所有 handoff 命令只写 .smartdev/runs/，不修改源码
7. handoff 命令不调用任何模型
8. MCP 工具 smartdev_handoff_code / doc / review 可正常调用
9. 模式 A（手动）流程可端到端走通
10. 全量测试无回归
