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

  "run_id": "20260625-fix-patch",            // 可选但强烈建议。gate 据此反查 anchored authority，见 §2.3

  "task_scope": {
    "task_id": "optional",
    "description": "Fix patch apply rollback behavior",
    "authority": "human",        // declared_authority：仅作 audit label，不参与裁决（§2.3）
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

## 2.3 Scope Authority（anchored authority，定位的根）

**核心原则:被审查方不能定义审查范围。** `gate.check` 实际裁决用的范围(`effective_scope`)不得来自请求自报,而必须由 gate **自己反查**一个 agent 碰不到的带外锚点。

### 三层 scope

| 层 | 来源 | 信任级别 | 用途 |
|----|------|---------|------|
| `declared_scope` | 请求 `task_scope.allowed_paths` | **不可信**(agent 自报) | 记录 agent"认为"要改什么 |
| `authorized_scope` | gate 反查 `.smartdev/runs/{run_id}/authorized_scope.json` | **anchored**(带外锚点) | 真正的授权范围 |
| `effective_scope` | 见下方决议 | — | gate 裁决实际使用的范围 |

### effective_scope 决议

```
有 run_id 且 authorized_scope.json 存在可读
    → effective_scope = authorized_scope        (status: "anchored")
    → 若 declared_scope ⊄ authorized_scope，产出 scope.declared_exceeds_authorized

无 run_id，或文件不存在/不可读
    → effective_scope = declared_scope           (status: "unverified")
    → 产出 scope.authority_unverified（conservative=warn / enforcing=block 预留）

run_id 提供但路径校验失败（如 run_id 含 .. 或越界）
    → effective_scope = declared_scope           (status: "missing")
    → 产出 scope.authority_unverified
```

### 信任边界（诚实声明）

`authorized_scope.json` **不是强加密授权(verified authority)**,而是 **anchored authority**——可信性仅来自两点:

1. **gate 自己读,不从 agent 请求接收**——agent 能传 `run_id`,但碰不到 run_id 指向的内容。
2. **`.smartdev/runs/**/authorized_scope.json` 必须在 protected paths 内**(§7),agent 改它即触发 `path.protected_modified` block。

> 它比 self-reported authority 高一个数量级,但**不要在任何文档/输出里称它为 "verified"**。v1 的信任模型止于 anchored。强签名授权是未来版本的事。

### `request.task_scope.authority` 的地位

请求里若带 `authority` 字段,**仅作 `declared_authority` 审计标签**,回显进 audit,**绝不参与裁决**。self-asserted authority 不是 authority。

### `authorized_scope.json` 格式

```jsonc
{
  "schema_version": "authorized-scope.v1",
  "run_id": "20260625-fix-patch",
  "issued_by": "human|ci|issue|run_artifact",   // 授权来源（带外，非 agent 自报）
  "issued_at": "2026-06-25T10:00:00Z",
  "allowed_paths":    ["smartdev/core/patch.py", "tests/**"],
  "disallowed_paths": [".git/**", ".smartdev/**"],
  "max_files": 10,
  "allowed_change_types": ["modify", "create_test"]
}
```

> 谁写这个文件不属于 `gate.check` 契约范围——它由任务派发侧(人工 / CI / issue 同步 / `create_run_artifact`)生成。gate 只负责**读取与裁决**,不负责生成,这正是"被审查者不写授权"的体现。

---

## 3. 输出 schema

```jsonc
{
  "verdict": "allow",                       // allow | warn | block，§1.2 聚合
  "audit_id": "gate_20260625_abcd1234",
  "inputs_digest": "sha256:...",            // 见 §3.2，审计地基（不含反查结果）
  "contract_version": "2026-06-25.v1",
  "policy_version": "scope-gate.v1",
  "summary": "No blocking findings. 1 warning.",

  "authority": {                            // 见 §2.3 / §3.4
    "status": "anchored",                   // anchored | unverified | missing
    "run_id": "20260625-fix-patch",
    "declared_authority": "human",          // 请求自报，仅 audit，不参与裁决
    "source": ".smartdev/runs/20260625-fix-patch/authorized_scope.json",
    "authorized_scope_digest": "sha256:...",        // 反查到的授权快照摘要
    "authorized_scope_snapshot": { "allowed_paths": ["..."] }   // 当时查到的授权
  },

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
    run_id,
    policy_version,
    options.policy_profile
) )
```

用途:(1) 相同输入命中缓存,agent 重复调用免重算;(2) 事后审计可证明"当时闸门看到的就是这些输入"。`index_evidence` **不**纳入 digest(它是增强信号,不应改变同一变更的准入判定的可复现标识)。

> **`inputs_digest` 也不纳入反查到的 `authorized_scope`**(见 §3.4)。digest 只对**请求本身**稳定;反查结果是 gate 在某时刻读到的外部状态,放进 audit 而非 digest。

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

### 3.4 `authority` 输出与两类摘要的分工

`gate.check` 反查 anchored authority 后,**不再是纯函数**(要读 `.smartdev/runs/{run_id}/`)。这与 `inputs_digest` 的可复现性有张力,契约用**两个独立摘要**化解:

| 摘要 | 覆盖 | 回答的问题 |
|------|------|-----------|
| `inputs_digest` | 仅请求(task_scope / changed_files / 版本 / profile) | "同样的请求是否会被同样对待?" → 可复现性 |
| `authorized_scope_digest` | 反查到的 `authorized_scope.json` 快照 | "gate 当时看到的授权是什么?" → 可审计性 |

- `authority.status`:`anchored`(反查成功) / `unverified`(无 run_id 或文件不可读) / `missing`(run_id 路径校验失败)。
- `authority.authorized_scope_snapshot`:落审计的授权快照,事后可复核 effective_scope 的依据。
- 同一请求在两个时刻反查到不同授权 → `inputs_digest` 相同、`authorized_scope_digest` 不同。这是**预期行为**,正好把"请求可复现"与"授权可审计"分开。

---

## 4. deterministic blocklist（v1 唯一可 block 的规则集）

**v1 只有以下 4 条确定性规则可能被 policy 裁为 `block`，且各自有 proof requirement。** 其余一切(依赖清单改动、语义影响、架构风险、测试不足、命名、复杂度……)**最多 warn**。

| `rule_id` | 含义 | proof requirement（满足才可 block） |
|-----------|------|-----------------------------------|
| `scope.unlisted_file_modified` | 改了 **effective_scope** 之外的文件 | 该文件 ∉ effective_scope.allowed_paths 且匹配的 change 确实存在(effective_scope 定义见 §2.3) |
| `path.protected_modified` | 触碰 protected / disallowed 路径 | 文件匹配 `disallowed_paths` glob |
| `patch.hash_mismatch` | 声明的 `old_hash` 与仓库现状不符(TOCTOU) | **须有 `patch_id` 或 `old_hash`**;无则降级 warn(§2.2);block finding 必须给出 `rerun_patch_propose` |
| `patch.binary_or_generated_file_modified` | 改了二进制/生成文件 | 命中 `_BINARY_EXTS` 或已知 generated 路径 |

> **`scope.unlisted_file_modified` 与 `scope.declared_exceeds_authorized` 的分工(消歧,必读):**
> - `scope.unlisted_file_modified` 判的是"**实际改动 vs effective_scope**"——当 `status==anchored` 时 effective_scope = authorized_scope,此规则可 block(改了被授权范围外的文件,确定性违规)。当 `status==unverified/missing` 时 effective_scope = declared_scope,此规则**降级为 warn**(因为基准本身不可信,见下方注)。
> - `scope.declared_exceeds_authorized` 判的是"**declared_scope vs authorized_scope**"——agent 声明的意图范围超出授权,是关于"意图"的 warn,不直接拦具体文件。
> - 二者不重叠:前者管"改了什么",后者管"声称要改什么"。
> - 若某 declared pattern 是**精确文件路径**且该文件已被 `scope.unlisted_file_modified` block,则抑制对应的 `scope.declared_exceeds_authorized` warn,避免同一越界事实同时给出 `remove_file_from_patch` 与 `update_scope` 两种机器动作。宽 glob(如 `src/**`)不抑制,因为它表达的是更宽的越权意图。
>
> **关键补充**:`scope.unlisted_file_modified` 可 block 的前提是 **`authority.status == anchored`**。若 authority 未锚定,基准是 agent 自报的 declared_scope,用不可信基准去 block 等于让 agent 自己定义"什么算越界"——故 unanchored 时此规则封顶 warn,另由 `scope.authority_unverified` 提示授权缺失。

> **已从 v1 blocklist 移除**:
> - `patch.apply_not_atomic` —— 原子性属于 **apply 执行层**(`code.apply` 运行时保证 + 失败注入测试),`gate.check` 在 apply **之前**调用,无法预测执行期失败,纳入闸门属范畴错误。
> - `deps.manifest_changed_without_scope` —— 降为 **warn-only**(见下)。manifest 文件多义(版本号 / metadata / tool 配置 / pytest / ruff / 真依赖),"文件名命中"不足以达到 block 所需的低误杀。

**warn-only deps / scope 规则(v1 不可 block):**

| `rule_id` | severity 上界 | machine_action |
|-----------|--------------|----------------|
| `deps.manifest_changed_without_scope` | `warn` | `update_scope \| none` |
| `scope.authority_unverified` | `warn`(conservative)/ **block 预留**(enforcing) | `update_scope \| none` |
| `scope.declared_exceeds_authorized` | `warn`(v1)/ **block 预留**(enforcing) | `update_scope \| remove_file_from_patch` |

> `scope.authority_unverified`:无 `run_id` 可反查,或反查不到 `authorized_scope.json`(§2.3)。v1 `conservative`=warn,`enforcing`=block(预留,不实现)——"无授权时多严"是 policy 决策,不写死。
>
> `scope.declared_exceeds_authorized`:`declared_scope ⊄ authorized_scope`,即 agent 声明范围超出反查到的授权。这是**确定性**关系(可证明),v1 先 warn-only,enforcing 可 block。**v1 不做"过宽"启发式检测**(`**/*` 这类),因为模式宽窄是猫鼠游戏;只做"超出授权"这条可证明的关系。

> 将来若要恢复可 block,必须拆成更窄的 deterministic rule,且 proof 须**解析 manifest 前后的依赖集合**确认 runtime dependency 增删,不能只凭文件名命中:
> `deps.runtime_dependency_added_without_scope` / `deps.runtime_dependency_removed_without_scope` / `deps.lockfile_changed_without_manifest_change`。

非确定性规则示例(v1 **永远 ≤ warn**):`deps.manifest_changed_without_scope`、`impact.wide_blast_radius`、`arch.layer_violation`、`tests.insufficient_coverage`、`patch.large_diff`、`patch.unverifiable_source`。

> `patch.unverifiable_source` 按请求聚合输出:当多个文件同时缺少 `patch_id` / `old_hash`,返回一条 finding,`evidence.affected_files` 列出受影响文件,避免逐文件刷屏。

完整的 per-rule proof requirement 与单测判定表见 [`gate-check-rule-decision-table.md`](gate-check-rule-decision-table.md)。

---

## 5. policy_profile

| profile | 行为 |
|---------|------|
| `conservative`（v1 默认） | 严格执行 §1:仅 deterministic + high confidence + proof 满足才 block;其余 ≤ warn。**早期产品唯一推荐档**。 |
| `standard`（预留） | 未来可放宽,**v1 不实现**;收到时按 `conservative` 处理并产出 info `gate.profile_downgraded`。 |
| `enforcing`（预留） | CI 硬门槛档,**v1 不实现**。预留语义:`scope.authority_unverified` 与 `scope.declared_exceeds_authorized` 在此档可 **block**(无授权/超授权时硬拦)。收到时 v1 按 `conservative` 处理并产出 info `gate.profile_downgraded`。 |

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
| **anchored authority** | gate 反查 `.smartdev/runs/{run_id}/authorized_scope.json`(§2.3) | run_id 须做路径校验(拒 `..` / 越界);文件不存在→unverified |

### 7.0 ⚠️ Protected path 硬性要求（anchored authority 的前提）

anchored authority 成立的前提是 agent **改不到**授权文件。因此 gate 的默认 protected paths **必须包含**:

```
.smartdev/runs/**/authorized_scope.json
.smartdev/**              # 整个 .smartdev 目录建议保护（含 index、runs、patches）
```

> 若 agent 的 patch 触碰这些路径 → `path.protected_modified`(可 block)。**这条不配,anchored authority 形同虚设**——agent 可以先改 authorized_scope.json 再让自己"被授权"。这是整个 scope authority 机制的闭环锁。


### 7.1 ⚠️ 关键迁移注记（不写实现必塌）

现有 `ScopeViolation.severity`(值如 `"error"`)与 `GuardRunResult.error_count` 是**旧的"rule 自报 severity"模式**。在 `gate.check` 语境下:

- 这些字段**降级为原始事实信号**,gate 适配层**不得**直接把 `severity="error"` 透传为 finding 的 block。
- gate 适配层须把旧 violation 映射为 `{rule_id, confidence, evidence}`,**重新过 policy** 裁定 severity。
- 即:`scope_gate` / `guard_runner` 继续产出事实,**severity 一律由 gate 的 policy 层重算**。直接复用旧 severity = 承重墙倒塌。

---

## 8. 一句话边界

> `gate.check` 不和 Cursor / Claude / Codex 抢"写代码";它接管"能不能改、改得是否越界、是否可审查、是否可回滚、是否留下证据"。
> Blocking is a policy decision, not a rule decision.
