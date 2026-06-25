# `gate.check` v1 — Rule Proof Requirement 判定表

> 配套文档:[`gate-check-contract.md`](gate-check-contract.md)
> 本表是**契约到实现之间的最后一块拼图**:把每条 rule 的 proof requirement 精确到"什么 evidence 才算 high confidence",可直接对照写单测。

## 0. 全局约定（适用所有 rule）

- **rule 只上报 `confidence` + `evidence`;`severity` 由 policy 裁定**(承重墙)。本表 `can_block` 列描述的是 **policy 在 `conservative` profile 下**对该 rule 的最高裁定。
- **`block` 的充要条件**(§1.1):`rule_id ∈ deterministic_blocklist` AND `confidence == high` AND proof requirement 满足。任一不成立 → severity ≤ warn。
- **路径匹配**统一使用 glob(`**` 跨目录,`*` 单层),大小写敏感,POSIX 分隔符。
- **hash 格式**:`sha256:<hex>`。比较前两侧都按此规范化。
- 所有 rule **不抛异常**;无法判定时上报 `confidence: low` + evidence 说明,交 policy 降级。

---

## 1. 判定表（4 block rules + 1 warn deps rule）

### 1.1 `scope.unlisted_file_modified` — can_block: ✅

| 列 | 值 |
|----|----|
| **rule_id** | `scope.unlisted_file_modified` |
| **can_block** | ✅(deterministic) |
| **required_inputs** | `task_scope.allowed_paths`(非空)、`change.changed_files[].path` |
| **high_confidence_evidence** | 存在某 `changed_file.path`,对 `allowed_paths` 中**所有** glob 均不匹配,且对 `task_scope.disallowed_paths` 也不匹配(后者归 `path.protected_modified`),且不是 dependency manifest 文件(后者归 warn-only deps 规则)。evidence 须含:`{changed_file, allowed_paths, matched: false}` |
| **downgrade_to_warn_when** | `allowed_paths` 为空或缺失(scope 未声明范围 → 无基准可判越界,confidence=low → warn);或 `changed_file` 同时匹配 `disallowed_paths`(交由 protected 规则,本规则不重复 block);或 `changed_file` 是 dependency manifest(交由 `deps.manifest_changed_without_scope`,封顶 warn) |
| **machine_action** | `remove_file_from_patch \| update_scope` |
| **positive_test** | allowed=`["src/a.py"]`,changed=`["src/a.py","src/b.py"]` → finding on `src/b.py`,confidence=high,policy severity=block,verdict=block |
| **negative_test** | allowed=`["src/**"]`,changed=`["src/a.py","src/sub/c.py"]` → 无 finding,verdict=allow；allowed=`["src/**"]`,changed=`["pyproject.toml"]` → 不触发本规则 block,只触发 deps warn |

### 1.2 `path.protected_modified` — can_block: ✅

| 列 | 值 |
|----|----|
| **rule_id** | `path.protected_modified` |
| **can_block** | ✅(deterministic) |
| **required_inputs** | `task_scope.disallowed_paths`(非空)、`change.changed_files[].path` |
| **high_confidence_evidence** | 某 `changed_file.path` 匹配 `disallowed_paths` 任一 glob。evidence 须含:`{changed_file, matched_pattern}`(命中的具体 glob,审计可复核) |
| **downgrade_to_warn_when** | `disallowed_paths` 缺失/为空(无保护清单 → 无 high-confidence 依据)。**注**:此时不静默放行,而是产出 info `gate.no_protected_paths_declared` 提示 scope 不完整 |
| **machine_action** | `remove_file_from_patch \| revert_hunk` |
| **positive_test** | disallowed=`[".git/**",".smartdev/index.sqlite"]`,changed=`[".smartdev/index.sqlite"]` → confidence=high,severity=block,evidence.matched_pattern=`.smartdev/index.sqlite` |
| **negative_test** | disallowed=`[".git/**"]`,changed=`["src/git_helper.py"]` → 不匹配(`.git/**` 不命中 `src/git_helper.py`),verdict=allow |

### 1.3 `patch.hash_mismatch` — can_block: ✅（TOCTOU）

| 列 | 值 |
|----|----|
| **rule_id** | `patch.hash_mismatch` |
| **can_block** | ✅(deterministic) |
| **required_inputs** | `change.patch_id`(主)**或** `changed_files[].old_hash`(fallback);项目工作区可读 |
| **high_confidence_evidence** | 对某 `MODIFY/DELETE` 文件,重新读盘计算当前内容 sha256,与 `old_hash`(或 patch_id 指向的持久化 old_hash)**不一致**。evidence 须含:`{file, declared_old_hash, current_hash}` —— 两个 hash 都落审计,可复核 TOCTOU |
| **downgrade_to_warn_when** | 既无 `patch_id` 又无 `old_hash`(§2.2 `patch.unverifiable_source`,confidence=low → warn);或目标文件读取失败(IO/编码,confidence=medium → warn,evidence 记 reason) |
| **machine_action** | `rerun_patch_propose`(hash 不一致须重新 propose,非简单 remove;block finding 不得为 `none`) |
| **positive_test** | 文件落盘内容 hash=X,patch 声明 old_hash=Y(X≠Y) → confidence=high,severity=block,evidence 含 X 与 Y |
| **negative_test** | 文件落盘 hash=X,patch 声明 old_hash=X → 无 mismatch finding,verdict=allow(其他规则不触发时) |

### 1.4 `patch.binary_or_generated_file_modified` — can_block: ✅

| 列 | 值 |
|----|----|
| **rule_id** | `patch.binary_or_generated_file_modified` |
| **can_block** | ✅(deterministic) |
| **required_inputs** | `changed_files[].path`;复用 `patch.py::_BINARY_EXTS` + generated 路径清单 |
| **high_confidence_evidence** | 文件后缀 ∈ `_BINARY_EXTS`,**或**路径匹配已知 generated 清单(如 `**/*.lock`、`dist/**`、`build/**`、`*.min.js`)。evidence 须含:`{file, reason: "binary_ext" \| "generated_path", matched}` |
| **downgrade_to_warn_when** | 仅"疑似生成"但无确定特征(如普通 `.json` 既可能手写也可能生成 → confidence=medium → warn);后缀不在闭集内 |
| **machine_action** | `remove_file_from_patch` |
| **positive_test** | changed=`["assets/logo.png"]`(`.png ∈ _BINARY_EXTS`) → confidence=high,severity=block,reason=binary_ext |
| **negative_test** | changed=`["src/config.py"]`(文本源码) → 无 finding,verdict=allow |

### 1.5 `deps.manifest_changed_without_scope` — can_block: ❌（warn-only）

| 列 | 值 |
|----|----|
| **rule_id** | `deps.manifest_changed_without_scope` |
| **can_block** | ❌ **severity 上界 = warn**(v1 不可 block,无论 confidence) |
| **required_inputs** | `changed_files[].path`;manifest 清单(pyproject.toml / package.json / go.mod / Cargo.toml / requirements*.txt / pom.xml …) |
| **high_confidence_evidence** | manifest 文件在 changed_files 且未列入 `allowed_paths`。evidence 含 `{manifest_file, in_allowed_paths: false}` —— **注意:即便 confidence=high,policy 仍封顶 warn**(manifest 多义,文件名命中不足以低误杀) |
| **downgrade_to_warn_when** | N/A —— 本规则**恒定 ≤ warn**;无 manifest 改动时不产 finding(→ 对该规则 allow) |
| **machine_action** | `update_scope \| none` |
| **positive_test** | changed=`["pyproject.toml"]`,不在 allowed_paths → finding,confidence=high,**policy severity=warn**(非 block),verdict=warn(若无其他 block) |
| **negative_test** | changed=`["src/a.py"]`(无 manifest) → 无 deps finding;**断言:绝不出现 severity=block 的本规则 finding,即便构造 confidence=high 也封顶 warn**(承重墙回归测试) |

---

## 2. 必备的不变量回归测试（跨 rule）

这些不测单条 rule,而是测**承重墙本身**,建议独立成 `test_gate_invariants.py`:

| 测试 | 断言 |
|------|------|
| **INV-1 rule 无 severity 字段** | 任意 rule 的原始输出对象不含 `severity` 键(schema 层) |
| **INV-2 只有 blocklist 能 block** | 构造一条非 blocklist rule(如 `tests.insufficient_coverage`)即便 confidence=high,policy 裁定 severity ≤ warn |
| **INV-3 deps 永不 block** | `deps.manifest_changed_without_scope` 在任何 profile / confidence 下,policy severity ≤ warn |
| **INV-4 verdict 聚合** | findings=[info, warn] → verdict=warn;findings=[warn, block] → verdict=block;findings=[] → allow |
| **INV-5 无 patch_id 降级** | block 类 hash 规则在无 patch_id 且无 old_hash 时,severity 降为 warn,产出 `patch.unverifiable_source` |
| **INV-6 contract_version 降级** | 缺失版本 → verdict=warn + `gate.contract_version_missing`;未知版本 → verdict=warn + `gate.contract_version_unsupported`;二者**绝不 block** |
| **INV-7 inputs_digest 可复现** | 相同输入两次调用 → 相同 `inputs_digest`;改变 `index_evidence` → digest 不变(增强信号不入 digest) |
| **INV-8 旧 severity 不透传** | 喂入带 `severity="error"` 的旧 `ScopeViolation`,gate 适配层重过 policy,不得直接产出 block(§7.1 迁移注记回归) |
| **INV-9 block finding 可机器处理** | 任意 `severity=block` finding 必须带非 `none` 的闭集 `machine_action`;无动作则 policy 降级 warn |

---

## 3. 实现顺序建议

1. 先写 **INV-1 / INV-2 / INV-3**(承重墙骨架),让"rule 不能 block"在测试里立住。
2. 再实现 4 条 block rule 的 positive/negative(§1.1–1.4)。
3. 然后 §1.5 deps warn-only(连同 INV-3 双重保险)。
4. 最后 INV-4–INV-8(聚合 / 降级 / 版本 / digest / 迁移)。

> 顺序的用意:**先让承重墙的回归测试存在,再往上加规则**。任何后续 rule 若不小心引入 block 能力,INV-2 会立刻失败。
