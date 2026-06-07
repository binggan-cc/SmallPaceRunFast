# Phase 9 Step 0 — Safe Patch Agent 执行前设计

> 状态：设计文档（Step 0），不动代码
> 前置：Phase 8 已完成并冻结（484 tests，清洁基线）
> 目标：把 code.patch 从占位符升级为"安全可控的代码执行能力"，完成 L3 诊断型 → L4 执行型的跳跃

---

## 1. 背景

### 1.1 现状

`code.patch` 当前生成一个占位符 note 文件（`_generate_simple_patch` 输出说明性内容，不做真实变更）。

但底层数据模型已完备：
- `core/patch.py`：`Patch` / `FilePatch` / `LineChange` / `PatchAction`（CREATE/MODIFY/DELETE）
- `to_unified_diff()`：结构化补丁 → unified diff
- `create_file_patch(old, new)`：从新旧内容计算行级 diff
- `compute_line_changes()`：逐行差异

**缺的不是数据模型，是"安全生成 + 安全应用"的机制。**

### 1.2 Phase 9 的定位

前 8 个 Phase 都是只读/分析（R0-R1）。Phase 9 第一次进入 **R2/R3——真正修改用户代码**。

这是整个项目最该守纪律的节点。`protocol §4` 禁止行为里与 patch 直接相关：
- #2 未说明影响就删文件
- #4 未提供回滚方案就做跨模块重构
- #5 一次性修改大量无关文件
- #6 "顺手优化"
- #7 改完不说验证方式

`core-spec §11`：**R2 需回滚方案，R3 必须先给方案等确认**。代码修改天然 R2 起步。

> **Phase 9 的核心不是 diff 算法，是"诊断 → 方案 → 确认 → 执行 → 验证 → 回滚"的完整安全闭环。**

---

## 2. 核心约束：零 LLM 下"真实补丁"指什么

### 2.1 诚实面对约束

本项目零外部依赖、零 LLM、确定性输出（pyproject.toml 明确）。
`agent.md §11 Phase 4/5` 当年设想"LLM 生成 patch"，但当前架构没有 LLM。

**所以 Phase 9 不做"智能代码生成"。** 强行接 LLM 会破坏项目的确定性根基和零依赖原则。

### 2.2 零 LLM 下能做且有价值的事

| 能力 | 是否做 | 理由 |
|------|--------|------|
| **安全应用机制**（apply + 备份 + rollback） | ✅ 核心 | 这是 L4 执行型的真正门槛，与 LLM 无关 |
| **impact 驱动风险门**（apply 前跑 code.impact + risk.check） | ✅ 核心 | 复用 Phase 8 成果 |
| **确定性补丁生成器**（find-replace / token 替换） | ✅ 旗舰场景 | 对应设计文档 SmartFav 硬编码颜色替换，无需 LLM |
| **结构化模板补丁**（加 docstring / 注释模板） | ✅ 可选 | 确定性，低风险 |
| LLM 代码生成 | ❌ 不做 | 破坏零依赖 + 确定性；留给未来接入 LLM 时 |

**旗舰场景**：`code.patch` 接受"find → replace"指令（如把硬编码 `#22C55E` 替换为 `var(--color-accent)`），跨文件预览 diff，确认后安全应用。这正是 `protocol §17 SmartFav` 和 `core-spec §5.4` token 治理的落地。

---

## 3. 五个核心问题

### Q1: 生成与应用如何分离？

**答案：propose（R1，默认）/ apply（R2/R3，显式且需确认）两段式。**

```
code.patch（propose）  → 生成 Patch 草案 + diff，不碰磁盘，R1
code.apply（apply）     → 把已确认的 Patch 写入磁盘，R2/R3，需确认 + 备份
code.rollback           → 从备份恢复，R1
```

`agent.md §11` 早已定好这个拆分：**默认只生成不应用；R2/R3 必须确认；每次 patch 带验证清单。**

CLI：
- `smartdev patch -p PROJ --find X --replace Y`（propose，输出 diff，默认不落地）
- `smartdev patch -p PROJ ... --apply`（apply，显式开关 + 二次确认）

### Q2: 如何 impact 驱动风险？

**答案：propose 阶段复用 Phase 8 的 code.impact + risk.check。**

```
propose():
    1. 确定 target files（find-replace 命中的文件）
    2. 对每个 target 跑 ImpactAnalyzer → 受影响范围
    3. 跑 risk.check → 风险等级（max(关键词, impact)）
    4. 把 affected_files + risk_level 写进 Patch 元数据
    5. 输出 diff + 影响范围 + 风险 + 验证清单 + 回滚说明
```

风险升级规则（基于命中范围）：
- 单文件、非核心 → R1/R2
- 多文件 / 命中核心模块（architecture.map 的 core_modules）→ R2/R3
- 命中 protected_paths（adapter 定义）→ 拒绝，记为需人工处理

### Q3: 回滚方案怎么做？

**答案：apply 前备份 + 两种回滚路径。**

```
apply 前：
    把每个将修改文件的原内容备份到 .smartdev/patch_backups/{timestamp}/{path}
apply 后回滚：
    1. code.rollback → 从备份恢复（不依赖 git）
    2. git 项目额外提示：git checkout / git revert
```

备份目录归 CACHE_WRITE（写 .smartdev/，不是源码）。

### Q4: 验证闭环怎么落地？

**答案：apply 后输出验证清单，可选执行项目测试。**

```
apply 后：
    1. 输出变更摘要（修改文件 / +N -M 行 / 理由）—— protocol §7
    2. 输出验证清单（复用 qa.checklist + adapter validation）
    3. 可选：若 adapter 定义了 test 命令且用户加 --verify，执行并报告
       （默认不自动跑重型命令，对齐 参考.md §7.4）
    4. 输出回滚指令
```

### Q5: 权限门怎么落地？

**答案：复用 RiskController.enforce + 显式 apply 开关 + 审计 + R3 强确认。**

```
propose: R1 → 自动执行（只生成）
apply:   R2 → 输出风险+回滚，需 --apply 显式开关
         R3 → 必须强确认（命中核心模块/数据模型/protected path）
rollback: R1 → 可执行
```

- RiskController 已有 enforce 拦截 R2/R3
- apply 操作写一条审计记录到 runs 表（task / files / timestamp / risk）
- protected_paths 命中 → 直接拒绝 apply

**R3 强确认机制（P0-4，比 --apply 更强）：**
```
R2: --apply 即可
R3: --apply --confirm-risk R3   （显式声明知晓 R3 风险）
    或交互式要求输入确认串：APPLY R3
```
仅 `--apply` 不足以放行 R3——R3 可能命中核心模块、数据模型、protected-like 区域。

---

## 3.5 安全加固设计（P0，写盘前必须落地）

Phase 9 第一次写磁盘，以下四项是硬性安全要求，不是可选优化。

### P0-1: propose 结果持久化为 patch_id（防 TOCTOU）

**问题**：若 apply 阶段重新扫描生成 find-replace，propose 与 apply 之间文件可能已变（TOCTOU 竞态）。

**方案**：propose 一次性生成 Patch 对象并持久化，apply 只消费已存在的 patch，不重新扫描。

```
smartdev patch --find X --replace Y
    → 生成 patch_id（如时间戳 + 内容 hash）
    → 保存 .smartdev/patches/{patch_id}.json（含 FilePatch + 元数据）
    → 输出 diff + patch_id

smartdev apply --patch-id {patch_id}
    → 加载已保存的 patch（不重新扫描）
    → 校验原文件 hash → 校验风险 → 备份 → 应用
```

便捷形式 `smartdev patch ... --apply` 仍允许，但**内部必须先生成 patch 对象、再立即 apply 同一对象**，绝不重复扫描生成第二份 patch。

### P0-2: apply 前校验原文件 hash

每个 `FilePatch` 在 propose 时记录：
```
old_hash   # propose 时文件内容 SHA256
old_size
old_mtime
```
apply 前检查：
```
当前文件 hash == old_hash → 允许 apply
当前文件 hash != old_hash → 拒绝，提示"文件已变更，请重新 propose"
```
防止 propose 和 apply 之间文件被改、patch 覆盖新内容。

### P0-3: 路径安全（写盘强约束）

apply 写盘前对每个目标路径强制校验：
```
✗ path traversal（../../ 逃出 project_path）→ 拒绝
✗ 写 project_path 外部 → 拒绝
✗ symlink（除非显式 --allow-symlink）→ 跳过
✗ 二进制文件 → 跳过
✗ protected_paths 命中（adapter 定义）→ 拒绝
默认跳过目录：.git/ / node_modules/ / dist/ / build/ / venv/ / __pycache__/
默认跳过 .smartdev/（备份目录除外）
```

### P0-4: 运行时写盘能力的风险定级

`core/patch.py` 的 `apply_patch()` 作为**代码新增**是 R1（新增纯函数），
但作为**运行时能力**是 R2/R3（写盘）。

> **约束：任何对真实项目调用 apply_patch() 都必须经 Skill 层的权限门（risk.check + --apply + R3 强确认），禁止绕过 Skill 直接调用 core.patch.apply_patch()。**

---

---

## 4. 技术设计

### 4.1 core/patch.py 增强

新增 patch 序列化 + hash 元数据 + 应用 + 备份 + 回滚（纯文件操作，无新依赖）：

```python
@dataclass  # FilePatch 扩展字段（P0-2）
class FilePatch:
    ...                # 现有字段不变
    old_hash: str = ""    # propose 时原文件 SHA256
    old_size: int = 0
    old_mtime: float = 0.0

def build_find_replace_patch(
    project_path, find: str, replace: str,
    include_glob: str = "**/*", regex: bool = False,
) -> Patch:
    """跨文件 find→replace，生成 Patch（不落地）。
    命中行级 diff 用现有 create_file_patch / compute_line_changes。
    每个 FilePatch 记录 old_hash/old_size/old_mtime（P0-2）。
    路径安全过滤见 P0-3。
    """

def save_patch(patch: Patch, patches_dir: Path) -> str:
    """持久化 Patch 为 .smartdev/patches/{patch_id}.json，返回 patch_id（P0-1）。"""

def load_patch(patch_id: str, patches_dir: Path) -> Patch:
    """加载已保存的 Patch。"""

def apply_patch(patch: Patch, project_path: Path, backup_dir: Path) -> ApplyResult:
    """应用补丁到磁盘，应用前：
    1. 校验每个文件 old_hash（P0-2），不一致则拒绝
    2. 路径安全校验（P0-3）
    3. 备份原文件到 backup_dir
    然后 CREATE/MODIFY/DELETE。返回 ApplyResult（applied / skipped / rejected / backup_path）。
    """

def rollback_patch(backup_path: Path, project_path: Path) -> RollbackResult:
    """从备份恢复文件。"""
```

### 4.2 Skill 设计

| Skill | 风险 | 职责 |
|-------|------|------|
| `code.patch`（增强现有） | R1 | propose：find-replace 生成 diff + impact + 风险 + 验证清单，不落地 |
| `code.apply`（新增） | R2/R3 | 把已确认 Patch 写盘 + 备份 + 审计，需显式开关 |
| `code.rollback`（新增） | R1 | 从备份恢复 |

`code.patch` propose 输出（data）：
```
{
    "diff": "...",
    "files": [...],
    "affected_files": [...],   # 来自 impact
    "risk_level": "R2",
    "validation": [...],
    "rollback": "code.rollback 或 git checkout",
    "backup_hint": "apply 时将备份到 .smartdev/patch_backups/"
}
```

### 4.3 CLI

```
smartdev patch -p PROJ --find "#22C55E" --replace "var(--color-accent)" [--glob "**/*.css"]
    → propose：输出 diff + 影响 + 风险（不落地）
smartdev patch -p PROJ --find ... --replace ... --apply
    → apply：R2 输出风险确认，写盘 + 备份
smartdev rollback -p PROJ [--backup TIMESTAMP]
    → 从备份恢复
```

---

## 5. 影响范围分析

| 文件 | 变更 | 风险 |
|------|------|------|
| `core/patch.py` | +apply/rollback/find_replace（纯文件操作） | R1（新增函数，不改现有） |
| `skills/code_patch/skill.py` | propose 真实化（find-replace + impact） | R2 |
| `skills/code_apply/skill.py` | 新建（apply Skill） | R2 |
| `skills/code_rollback/skill.py` | 新建（rollback Skill） | R1 |
| `cli.py` | +patch/rollback 命令参数 | R1 |
| `core/workflow.py` | **不修改**（patch 不进默认 workflow） | — |

### 不修改

- `context/` 全部
- 其他所有 Skill（risk.check / architecture.map / task.plan / ...）
- 默认 workflow（patch 是显式操作，不自动串进诊断流程）

### 测试新增

| Step | 测试文件 | 覆盖 |
|------|---------|------|
| Step 1 | `test_patch.py` 扩展 | apply / rollback / 备份 / find-replace 生成 |
| Step 2 | `test_code_patch.py` 扩展 | propose 真实 diff + impact 接入 |
| Step 3 | `test_code_apply.py` 新建 | apply 写盘 + 权限门 + protected_path 拒绝 |
| Step 4 | `test_code_rollback.py` 新建 | 备份恢复 + 端到端 propose→apply→rollback |

---

## 6. 风险等级与回滚方案

### 按 Step 拆分

| Step | 风险 | 理由 |
|------|------|------|
| Step 1 | R1 | core/patch.py 新增纯函数（apply/rollback/find-replace），不改现有，单测覆盖 |
| Step 2 | R2 | code.patch propose 真实化，但仍不落地（只生成 diff） |
| Step 3 | R2 | code.apply 写盘——本阶段最高风险，备份 + 权限门 + protected_path 三重保护 |
| Step 4 | R1 | rollback + 端到端测试 |

### 回滚方案

1. apply 本身有备份机制（.smartdev/patch_backups/）
2. 任一 Step 出问题 → `git revert` 对应 commit
3. apply Skill 默认不启用（需显式 --apply），不会误伤
4. 所有测试在 tmp_path 内操作，不碰真实项目

---

## 7. 实施路线

前置确认（开工前必须满足，已收口）：
- ✅ Phase 8 已**代码完成**（非仅设计）：risk.check 的 impact 分支可用、architecture.map 的 core_modules 可用、484 tests 清洁
- task.plan 非强依赖（patch propose 主要用 code.impact + risk.check）

```
Phase 9 Step 0 ✅ 当前 — 设计确认（含安全加固 P0-1~P0-4）
Phase 9 Step 1A: core/patch.py — find_replace_patch + Patch 序列化(save/load) + hash 元数据 + unified diff（R1，~495 tests）
Phase 9 Step 1B: core/patch.py — apply/rollback + backup + 路径安全（R1 代码 / R2 运行时能力，~505 tests）
Phase 9 Step 2: code.patch propose 真实化 — diff + impact + risk + patch_id（R2，~512 tests）
Phase 9 Step 3: code.apply Skill — 权限门 + hash 校验 + protected_path + R3 强确认 + 审计（R2，~520 tests）
Phase 9 Step 4: code.rollback + 端到端 propose→apply→rollback 验证（R1，~528 tests）
```

**拆分理由**：先把 patch 的"可审查草案"（patch_id / hash / serialization / diff）做稳（Step 1A），再赋予写盘能力（Step 1B），避免单步过大、降低写盘风险。这对应审查意见"先做稳可审查草案，再让它具备写盘能力"。

### 不做（Phase 9 范围内）

```
❌ LLM 代码生成（破坏零依赖 + 确定性，留给未来 LLM 接入）
❌ 复杂语义重构（重命名符号跨文件等，需 LSP）
❌ patch 进默认 workflow（patch 是显式操作）
❌ 自动跑重型测试（默认只输出验证清单，--verify 才执行）
❌ 多 patch 事务 / 冲突合并
```

---

## 8. 验收标准

1. 现有 484 tests 全部通过，无回归
2. `code.patch` propose 输出真实 find-replace diff + patch_id + 受影响文件 + 风险等级 + 验证清单 + 回滚说明
3. propose 持久化到 `.smartdev/patches/{patch_id}.json`（P0-1）
4. `code.apply` 写盘前校验原文件 hash（P0-2），不一致拒绝
5. `code.apply` 路径安全：拒绝 traversal/外部路径，跳过 symlink/二进制，拒绝 protected_path（P0-3）
6. `code.apply` R2 需 `--apply`，R3 需强确认（`--confirm-risk R3`）（P0-4）
7. `code.rollback` 能从备份完整恢复
8. 端到端：propose → apply → 验证文件已改 → rollback → 验证文件复原
9. 默认安全：不加 --apply 时绝不碰磁盘
10. 所有测试在 tmp_path 内，不污染真实项目
11. 审计：apply 写一条记录到 runs 表
12. 禁止绕过 Skill 直接调用 core.patch.apply_patch()（文档约束 + Skill 层权限门）
