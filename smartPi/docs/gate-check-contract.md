# `gate.check` v1 — 变更准入契约

> **`gate.check` v1 treats blocking as a policy decision, not a rule decision.**
> **Rules may report evidence and confidence; only policy may derive severity and verdict.**

`gate.check` 是 AI agent 在 **apply 之前**调用的变更准入闸门。它的产品承诺不是"发现很多问题",而是 **`block` 几乎不误报**。这个承诺集中在 policy 层,不下放给任何一条 rule。

本文件是 SmartDev 的**产品边界契约**。接口一旦发布即被多个 agent(Claude Code / Cursor / Codex / CI / 脚本)接入,字段与不变量不得一边实现一边漂移。任何破坏性变更必须 bump `contract_version`。

- 契约版本:`contract_version = "2026-06-25.v1"`
- 适用工具:MCP `smartdev_gate_check`、CLI `smartdev gate check`
- 定位:agent-neutral 代码变更治理层。SmartDev 不决定"谁来写代码",只保证"无论谁写,进入仓库前过同一个闸门"。

---

## 0. 职责分层（承重墙）

```
rule   →  上报事实：rule_id + confidence + evidence + suggestion + machine_action 候选
policy →  裁定动作：severity（info|warn|block）
gate   →  聚合裁定：verdict（allow|warn|block）+ audit
```

**规则只描述"我看到了什么"，policy 决定"这意味着什么"，gate 聚合成最终准入判断。**

三条铁律：

1. **rule 不得自报 severity。** rule 的输出里没有 `severity` 字段。severity 只能由 policy 产出。
2. **只有 policy 能把 finding 抬到 `block`。** 是否可 block 由 policy 持有的 `deterministic_blocklist` 白名单决定,不由 rule 声明。
3. **证据不足 → 最多 warn。** 任何无法满足 rule 专属证明要求的 finding,policy 一律降级到 ≤ warn,绝不 block。

---

## 1. 核心不变量

### 1.1 severity 推导

```
severity = policy(rule_id, confidence, evidence, policy_profile)

severity == block  当且仅当（iff）:
    rule_id ∈ deterministic_blocklist
    AND confidence == "high"
    AND evidence 满足该 rule 的 proof requirements（见 §4）

否则:
    severity <= warn
```

### 1.2 verdict 聚合

```
verdict = max(severity over all findings)

severity 偏序: info < warn < block

无 findings 或仅 info        => allow
存在 warn 且无 block         => warn
存在任一 block               => block
```

### 1.3 非法组合在 schema 层不可构造

- finding 的 schema **不含** `severity`(见 §3.1),因此 "rule 自报 block" 在数据层就无法表达。
- `block` 在输出里始终伴随 `confidence == "high"` 与 `rule_id ∈ deterministic_blocklist`;违反此条的输出视为**实现 bug**,消费方应按 `warn` 处理并记录 `gate.invariant_violation`。

---

## 2. 输入 schema

```jsonc
{
  "contract_version": "2026-06-25.v1",      // 必填。未知版本见 §6

  "task_scope": {
    "task_id": "optional",
    "description": "Fix patch apply rollback behavior",
    "allowed_paths":    ["smartdev/core/patch.py", "tests/test_patch.py"],
    "disallowed_paths": [".git/**", ".smartdev/index.sqlite", "node_modules/**"],
    "allowed_change_types": ["modify", "create_test"],   // 见 §2.1
    "risk_level": "R2"
  },

  "change": {
    "changed_files": [
      {
        "path": "smartdev/core/patch.py",
        "change_type": "modify",
        "old_hash": "sha256:...",   // 可选；缺失时 TOCTOU 类规则降级 warn
        "new_hash": "sha256:..."
      }
    ],
    "patch_id": "20260625-abcd1234",   // 主：指向 .smartdev/patches/{id}.json
    "diff": "unified diff text"        // fallback：仅当无 patch_id 时使用
  },

  "index_evidence": {                  // 可选增强信号，非必需
    "enabled": true,
    "affected_files": ["..."],
    "symbols_touched": ["apply_patch", "rollback_patch"],
    "entrypoints": ["code.apply", "code.rollback"]
  },

  "options": {
    "policy_profile": "conservative",  // 见 §5
    "emit_handoff": true
  }
}
```

> MCP 暴露层不得用 JSON Schema `required` 直接拦截这些字段。`contract_version` / `task_scope` / `change` 是契约语义上的必填字段,但畸形输入必须进入 `gate.check` core,由 core 返回结构化 `warn` finding(见 §6),避免 MCP SDK 在 handler 前返回非契约错误文本。

### 2.1 `change_type` 闭集

```
modify | create | delete | create_test | rename
```

### 2.2 `patch_id` 与 `diff` 的优先级（钉死）

- **`patch_id` 为主**:存在时,gate 以 `.smartdev/patches/{patch_id}.json` 持久化内容为准。
- **`diff` 为 fallback**:仅当无 `patch_id` 时使用。
- **二者同时存在** → 以 `patch_id` 为准,忽略 `diff`,并产出 info 级 finding `gate.diff_ignored_patch_id_present`。
- **二者皆无** → 无法验证变更来源,所有依赖文件内容/hash 的规则降级为 warn,产出 `patch.unverifiable_source`(warn)。

---

## 3. 输出 schema

```jsonc
{
  "verdict": "allow",                       // allow | warn | block，§1.2 聚合
  "audit_id": "gate_20260625_abcd1234",
  "inputs_digest": "sha256:...",            // 见 §3.2，审计地基
  "contract_version": "2026-06-25.v1",
  "policy_version": "scope-gate.v1",
  "summary": "No blocking findings. 1 warning.",

  "findings": [
    {
      "rule_id": "scope.unlisted_file_modified",
      "confidence": "high",                 // low | medium | high（rule 上报）
      "severity": "block",                  // info | warn | block（policy 裁定）
      "subject": { "file": "pyproject.toml", "range": null },
      "evidence": {
        "changed_file": "pyproject.toml",
        "allowed_paths": ["smartdev/core/patch.py", "tests/test_patch.py"]
      },
      "suggestion": "Revert this file or update task_scope.allowed_paths before applying.",
      "machine_action": "remove_file_from_patch"   // 闭集 enum，见 §3.3
    }
  ],

  "handoff": {                              // 仅当 options.emit_handoff == true
    "changed_files": ["smartdev/core/patch.py"],
    "risk_notes": ["Rollback behavior changed"],
    "recommended_tests": ["python -m pytest tests/test_patch.py -q"],
    "rollback": {
      "available": true,
      "backup_path": ".smartdev/patch_backups/..."
    }
  }
}
```

### 3.1 finding 字段职责

| 字段 | 来源 | 说明 |
|------|------|------|
| `rule_id` | rule | 稳定标识,机器可消费 |
| `confidence` | **rule** | `low \| medium \| high` —— rule 唯一允许的"分级"输出 |
| `severity` | **policy** | `info \| warn \| block` —— rule **不得**写入此字段 |
| `subject` | rule | `{file, range}`,定位 |
| `evidence` | rule | 机器可消费的事实证据,审计与 proof requirement 的依据 |
| `suggestion` | rule | **给人看**的自然语言建议 |
| `machine_action` | rule | **给机器**的闭集动作(§3.3),agent 据此自动修正 |

> `suggestion`(给人)与 `machine_action`(给机器)职责分离,不得混用。

### 3.2 `inputs_digest`（可复现性地基）

```
inputs_digest = sha256( canonical_json(
    task_scope,
    sorted(changed_files by path: {path, change_type, old_hash, new_hash}),
    contract_version,
    policy_version,
    options.policy_profile
) )
```

用途:(1) 相同输入命中缓存,agent 重复调用免重算;(2) 事后审计可证明"当时闸门看到的就是这些输入"。`index_evidence` **不**纳入 digest(它是增强信号,不应改变同一变更的准入判定的可复现标识)。

### 3.3 `machine_action` 闭集 enum

```
remove_file_from_patch   // 把越界文件从 patch 移除
revert_hunk              // 回退某个 hunk
update_scope             // 请求更新 task_scope（需人确认）
rerun_with_index         // 建议带 index_evidence 重跑以获得更强判定
rerun_patch_propose      // 工作区已变化，重新生成 patch 草案
none                     // 无可自动化动作
```

**v1 保证:**所有 `severity = "block"` 的 finding 必须带非 `none` 的 `machine_action`。若无法给出机器可执行动作,policy 必须把该 finding 降级为 `warn`,避免上游 agent 收到不可自动修复的 block。

---

## 4. deterministic blocklist（v1 唯一可 block 的规则集）

**v1 只有以下 4 条确定性规则可能被 policy 裁为 `block`，且各自有 proof requirement。** 其余一切(依赖清单改动、语义影响、架构风险、测试不足、命名、复杂度……)**最多 warn**。

| `rule_id` | 含义 | proof requirement（满足才可 block） |
|-----------|------|-----------------------------------|
| `scope.unlisted_file_modified` | 改了 `allowed_paths` 之外的文件 | 该文件 ∉ allowed_paths 且匹配的 change 确实存在；dependency manifest 文件除外，交由 warn-only deps 规则处理 |
| `path.protected_modified` | 触碰 protected / disallowed 路径 | 文件匹配 `disallowed_paths` glob |
| `patch.hash_mismatch` | 声明的 `old_hash` 与仓库现状不符(TOCTOU) | **须有 `patch_id` 或 `old_hash`**;无则降级 warn(§2.2);block finding 必须给出 `rerun_patch_propose` |
| `patch.binary_or_generated_file_modified` | 改了二进制/生成文件 | 命中 `_BINARY_EXTS` 或已知 generated 路径 |

> **已从 v1 blocklist 移除**:
> - `patch.apply_not_atomic` —— 原子性属于 **apply 执行层**(`code.apply` 运行时保证 + 失败注入测试),`gate.check` 在 apply **之前**调用,无法预测执行期失败,纳入闸门属范畴错误。
> - `deps.manifest_changed_without_scope` —— 降为 **warn-only**(见下)。manifest 文件多义(版本号 / metadata / tool 配置 / pytest / ruff / 真依赖),"文件名命中"不足以达到 block 所需的低误杀。

**warn-only deps 规则(v1 不可 block):**

| `rule_id` | severity 上界 | machine_action |
|-----------|--------------|----------------|
| `deps.manifest_changed_without_scope` | `warn` | `update_scope \| none` |

> 将来若要恢复可 block,必须拆成更窄的 deterministic rule,且 proof 须**解析 manifest 前后的依赖集合**确认 runtime dependency 增删,不能只凭文件名命中:
> `deps.runtime_dependency_added_without_scope` / `deps.runtime_dependency_removed_without_scope` / `deps.lockfile_changed_without_manifest_change`。

非确定性规则示例(v1 **永远 ≤ warn**):`deps.manifest_changed_without_scope`、`impact.wide_blast_radius`、`arch.layer_violation`、`tests.insufficient_coverage`、`patch.large_diff`、`patch.unverifiable_source`。

完整的 per-rule proof requirement 与单测判定表见 [`gate-check-rule-decision-table.md`](gate-check-rule-decision-table.md)。

---

## 5. policy_profile

| profile | 行为 |
|---------|------|
| `conservative`（v1 默认） | 严格执行 §1:仅 deterministic + high confidence + proof 满足才 block;其余 ≤ warn。**早期产品唯一推荐档**。 |
| `standard`（预留） | 未来可放宽,**v1 不实现**;收到时按 `conservative` 处理并产出 info `gate.profile_downgraded`。 |

> "宁可漏报,不可误杀"是 **policy 配置**,不是散落在规则里的承诺。回滚保守策略 = 改 policy 一处,无需动任何 rule。

---

## 6. 版本兼容（保守降级）

- 收到**未知 `contract_version`** → 返回 `verdict: "warn"` + finding `gate.contract_version_unsupported`(severity warn),**绝不 block,也绝不假装兼容**。
- 缺失 `contract_version` → 返回 `verdict: "warn"` + finding `gate.contract_version_missing`(severity warn)。这是兼容性降级,不是 MCP/CLI 结构错误。
- 缺失或类型错误的 `task_scope` / `change` / `change.changed_files` → 返回合法 gate 响应:`verdict: "warn"` + `gate.malformed_request` + `gate_error: true`。MCP 层不得抛异常或返回非契约 JSON。
- MCP input schema 不得把上述语义必填字段放进 JSON Schema `required`;畸形输入必须进入 handler/core,由 `gate.malformed_request` / `gate.contract_version_missing` 结构化返回,而不是被 MCP SDK 提前拒绝。
- `contract_version`(契约结构)与 `policy_version`(裁定逻辑)是**两条独立演进轴**;输出同时回显二者。
- 破坏性结构变更 → bump `contract_version`;仅裁定阈值/blocklist 调整 → bump `policy_version`。

### 6.1 CLI 退出码

| 情况 | 退出码 |
|------|--------|
| `verdict = allow` 或 `warn` | `0` |
| `verdict = block` | `1` |
| gate 自身错误 / malformed request / JSON 读取失败 | `2` |

---

## 7. 对接点（贴现有代码）

| 模块 | 角色 | 现有签名 / 迁移注记 |
|------|------|--------------------|
| `_TOOL_REGISTRY`（mcp/tools.py） | 注册 `smartdev_gate_check`(permission: `READ`) | 在"单一事实源"列表追加一条 |
| `core/scope_gate.py` | scope/path/change-type **事实判定** | `check_scope(project_path, run_id, changed_files)` 已存在 |
| `core/guard_runner.py` | 多 rule 编排 + finding 聚合 | `run_guard_runner(...)` 已存在 |
| `core/patch.py` | 提供 patch hash / changed files / rollback evidence | `load_patch` / `compute_content_hash` / `apply_patch` 的 backup_path |
| `run_artifact` | 落 `audit_id` / `inputs_digest` / handoff / evidence | `create_run_artifact(...)` |

### 7.1 ⚠️ 关键迁移注记（不写实现必塌）

现有 `ScopeViolation.severity`(值如 `"error"`)与 `GuardRunResult.error_count` 是**旧的"rule 自报 severity"模式**。在 `gate.check` 语境下:

- 这些字段**降级为原始事实信号**,gate 适配层**不得**直接把 `severity="error"` 透传为 finding 的 block。
- gate 适配层须把旧 violation 映射为 `{rule_id, confidence, evidence}`,**重新过 policy** 裁定 severity。
- 即:`scope_gate` / `guard_runner` 继续产出事实,**severity 一律由 gate 的 policy 层重算**。直接复用旧 severity = 承重墙倒塌。

---

## 8. 一句话边界

> `gate.check` 不和 Cursor / Claude / Codex 抢"写代码";它接管"能不能改、改得是否越界、是否可审查、是否可回滚、是否留下证据"。
> Blocking is a policy decision, not a rule decision.
