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

**答案：复用 RiskController.enforce + 显式 apply 开关 + 审计。**

```
propose: R1 → 自动执行（只生成）
apply:   R2 → 输出风险+回滚，需 --apply 显式开关
         R3 → 必须二次确认（命中核心模块/数据模型/protected path）
rollback: R1 → 可执行
```

- RiskController 已有 enforce 拦截 R2/R3
- apply 操作写一条审计记录到 runs 表（task / files / timestamp / risk）
- protected_paths 命中 → 直接拒绝 apply

---

## 4. 技术设计

### 4.1 core/patch.py 增强

新增 patch 应用 + 备份 + 回滚（纯文件操作，无新依赖）：

```python
def apply_patch(patch: Patch, project_path: Path, backup_dir: Path) -> ApplyResult:
    """应用补丁到磁盘，应用前备份原文件。
    - CREATE: 写新文件（若已存在则拒绝）
    - MODIFY: 备份原文件 → 写 new_content
    - DELETE: 备份原文件 → 删除
    返回 ApplyResult（applied_files / backup_path / errors）
    """

def rollback_patch(backup_path: Path, project_path: Path) -> RollbackResult:
    """从备份恢复文件。"""
```

新增 `find_replace_patch()` 确定性生成器：

```python
def build_find_replace_patch(
    project_path, find: str, replace: str,
    include_glob: str = "**/*", regex: bool = False,
) -> Patch:
    """跨文件 find→replace，生成 Patch（不落地）。
    命中行级 diff 用现有 create_file_patch / compute_line_changes。
    """
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

```
Phase 9 Step 0 ✅ 当前 — 设计确认
Phase 9 Step 1: core/patch.py — apply/rollback/find-replace 基础设施（R1，~495 tests）
Phase 9 Step 2: code.patch propose 真实化 + impact 接入（R2，~505 tests）
Phase 9 Step 3: code.apply Skill + 权限门 + protected_path（R2，~515 tests）
Phase 9 Step 4: code.rollback + 端到端 propose→apply→rollback 验证（R1，~525 tests）
```

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
2. `code.patch` propose 输出真实 find-replace diff + 受影响文件 + 风险等级 + 验证清单 + 回滚说明
3. `code.apply` 写盘前备份原文件，protected_path 命中拒绝，R2/R3 需显式确认
4. `code.rollback` 能从备份完整恢复
5. 端到端：propose → apply → 验证文件已改 → rollback → 验证文件复原
6. 默认安全：不加 --apply 时绝不碰磁盘
7. 所有测试在 tmp_path 内，不污染真实项目
8. 审计：apply 写一条记录到 runs 表
