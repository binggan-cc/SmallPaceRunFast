# Phase 8 Step 0 — Context Layer ↔ Skill 接入打通 执行前设计

> 状态：设计文档（Step 0），不动代码
> 前置：Phase 7 已完成并冻结（458 tests，清洁基线）
> 目标：把已建好的 Context Layer（索引/impact/relations）真正喂给 Skill 层，消除"眼睛和大脑两座孤岛"

---

## 1. 背景

### 1.1 问题陈述

经过 Phase 6-MVP / 6.2 / 6.3 / 7，SmartDev 已经有一套完整的 **Context Layer**：

- 三语言结构提取（Python 1.0 / JS-TS 0.95 / Go 0.98）
- SQLite + FTS5 索引
- artifact 提取（8 类）
- module 级 import relations
- ImpactAnalyzer（reverse lookup 依赖方）
- project.map / graph.validate

但核对代码发现一个关键断层：**5 个核心 Skill 全部没有接入 Context Layer**。

| Skill | next-phase-code-intelligence.md §10.1 计划 | 实际状态 |
|-------|------|------|
| `risk.check` | 接入 `code.impact` 算影响范围 | ❌ 仍用关键词匹配 |
| `architecture.map` | 接入 index 查依赖关系 | ❌ 自己跑独立 AST |
| `task.plan` | 基于影响分析精准拆解 | ❌ 纯模板 |
| `token.audit` | 接入符号索引统计 | ❌ 独立扫描 |
| `code.patch` | 真实补丁生成 | ❌ 占位符 |

结果：用户运行 `smartdev run` 时，强大的 Context Layer 根本没被 Skill 消费。

### 1.2 Phase 8 的定位

> **Phase 8 不新增解析能力，只做"接线"——让 Skill 消费 Context Layer。**

参考文档（§14）对 SmartDev 的定位升级是：

> 基于项目语义图谱的开发诊断、任务拆解、影响分析与安全执行 Agent。

"语义图谱驱动"这一点，只有当 Skill 真正消费图谱时才成立。Phase 8 是兑现这个定位的关键一步。

code.patch 的真实化（Safe Patch Agent）独立为 Phase 9，不在本阶段。

---

## 2. 核心设计原则

### P1: 优雅降级，零回归

所有接入必须是**可选增强**，不破坏现有行为：

```
有索引（.smartdev/index.sqlite 存在）→ 用 Context Layer 增强
无索引                              → 退回现有逻辑（关键词 / 独立 AST）
```

理由：
- `risk.check` 是 R0 只读 Skill，必须在任何项目（哪怕没索引）都能跑
- 现有 458 测试不能有任何回归
- 索引是"加分项"，不是"前置条件"

### P2: 不改 Context Layer，只改 Skill

Phase 8 只动 `skills/` 目录，不动 `context/`：
- `ImpactAnalyzer` / `IndexStore` / `project_map` 接口保持不变
- Skill 作为 Context Layer 的**消费方**接入

### P3: 风险信号取最大值

当关键词判断和 impact 判断同时存在时，最终风险等级取两者较高值：

```
final_risk = max(keyword_risk, impact_risk)
```

理由：风险判断宁可保守，不可低估。

---

## 3. 五个核心问题

### Q1: risk.check 如何接入 code.impact 又不破坏 R0 只读语义？

**答案：通过可选 `target` 输入 + 索引存在性检测。**

现状：`risk.check` 只吃 `context.task_description`，做关键词匹配。

接入方式：
```
1. 如果 inputs 提供 target（文件/符号）AND 索引存在
   → 运行 ImpactAnalyzer.analyze_import_impact(target)
   → 得到 impact_risk + 受影响文件 + 验证建议
2. final_risk = max(keyword_risk, impact_risk)
3. 把受影响文件 / 验证建议合并进输出
4. 无 target 或无索引 → 纯关键词匹配（现状，零回归）
```

关键：仍是 R0 只读，ImpactAnalyzer 只读索引，不写任何文件。

### Q2: architecture.map 接入 index 是替换还是增强？

**答案：增强优先，保留 fallback。**

现状：`architecture.map` 自己跑一套 Python AST + 循环依赖检测。

接入方式：
```
1. 索引存在 → 从 IndexStore 读 relations 构建依赖图（覆盖多语言）
2. 索引不存在 → 退回现有独立 AST（仅 Python）
```

收益：
- 复用索引 = 支持 Python/JS-TS/Go 多语言依赖图（现有 AST 只有 Python）
- 消除重复解析逻辑

注意：循环依赖检测逻辑保留，只是数据源从"现场 AST"换成"索引 relations"。

### Q3: task.plan 如何接入 impact？

**答案：用 impact 给任务标注影响范围，不改变三档方案结构。**

现状：`task.plan` 输出保守/推荐/深度三档纯模板方案。

接入方式：
```
1. 如果 task 描述中能解析出 target（文件/模块）AND 索引存在
   → 运行 impact 分析
   → 在推荐方案的任务项上标注"影响 N 个文件：xxx"
2. 风险等级用 impact 结果校准（替代纯关键词）
3. 无 target/无索引 → 现状三档模板
```

约束：不破坏三档方案的结构和现有测试。

### Q4: 接入后如何验证端到端？

**答案：用 WorkflowEngine 串起来 + 真实项目跑一遍。**

```
1. 单元测试：每个 Skill 接入后的 有索引/无索引 两条路径
2. 集成测试：workflow 在有索引项目上，risk/architecture/plan 都消费索引
3. 真实验证：在已索引的 Go/Python 项目上跑 smartdev run，确认输出带影响范围
```

### Q5: 哪些先做，哪些后做？

**答案：按价值密度排序，risk.check 优先。**

```
Step 1: risk.check ← code.impact   （价值最高，顺带修已知问题 #1）
Step 2: architecture.map ← index   （多语言依赖图）
Step 3: task.plan ← impact          （精准拆解）
Step 4: 端到端验证
```

token.audit 接入符号索引价值较低（它已能独立工作），放到 Phase 8 之后的优化项，本阶段不做。
code.patch 真实化独立为 Phase 9。

---

## 4. 技术设计

### 4.1 共享辅助：索引可用性检测

新增一个 Skill 层共享的辅助函数（位置：`skills/base.py` 或新建 `skills/_context_helper.py`）：

```python
def get_index_if_available(project_path: Path) -> ProjectIndex | None:
    """如果项目已建立索引，返回 ProjectIndex，否则 None。

    用于 Skill 优雅降级：有索引则增强，无索引退回原逻辑。
    只读，不触发索引构建。
    """
    db_path = project_path / ".smartdev" / "index.sqlite"
    if not db_path.exists():
        return None
    try:
        return ProjectIndex(project_path)
    except Exception:
        return None
```

### 4.2 Step 1: risk.check 接入 code.impact

**改动文件：** `skills/risk_check/skill.py`

**新增逻辑：**
```
run():
    keyword_risk, factors, reasoning = _analyze_risk_level(task_description)  # 现状保留

    target = (inputs or {}).get("target")
    impact_result = None
    if target:
        index = get_index_if_available(context.project_path)
        if index:
            impact_result = ImpactAnalyzer(index.store).analyze_import_impact(target)
            index.close()

    if impact_result:
        impact_risk = RiskLevel(impact_result.risk_level)
        final_risk = max(keyword_risk, impact_risk, key=lambda r: r.value)
        # 合并受影响文件 / 验证建议进输出
    else:
        final_risk = keyword_risk  # 零回归
```

**输出新增字段（仅当有 impact 时）：**
- `affected_files`: 受影响文件列表
- `impact_summary`: impact 分析摘要
- `risk_source`: "keyword" / "impact" / "both"

**风险等级：R1**（单文件修改，逻辑增强，有 fallback 保护）

### 4.3 Step 2: architecture.map 接入 index relations

**改动文件：** `skills/architecture_map/skill.py`

**需先读现有实现**确认循环依赖检测和输出结构，再决定数据源切换方式。

**设计方向：**
```
run():
    index = get_index_if_available(context.project_path)
    if index:
        relations = index.store 读取 imports relations
        构建依赖图（多语言）
        循环依赖检测复用现有算法
    else:
        现有独立 AST 路径（仅 Python）
```

**风险等级：R2**（多语言数据源切换，需保证循环依赖检测结果一致）

### 4.4 Step 3: task.plan 接入 impact

**改动文件：** `skills/task_plan/skill.py`

**设计方向：**
```
run():
    现有三档方案生成（保留）
    target = 从 task_description 解析 或 inputs.get("target")
    if target AND 索引存在:
        impact = ImpactAnalyzer.analyze_import_impact(target)
        在推荐方案任务项标注影响范围
        风险等级用 impact 校准
```

**风险等级：R1**（增量标注，不改变三档结构）

### 4.5 Step 4: 端到端验证

```
- 新增集成测试：workflow 在已索引项目上消费 Context Layer
- 真实项目验证（只读）：gnet-examples / SmartFav（若可用）
```

---

## 5. 影响范围分析

| 文件 | 变更 | 风险 |
|------|------|------|
| `skills/_context_helper.py` | 新建（索引检测辅助） | R1 |
| `skills/risk_check/skill.py` | +impact 接入（可选增强） | R1 |
| `skills/architecture_map/skill.py` | 数据源切换 + fallback | R2 |
| `skills/task_plan/skill.py` | +impact 标注 | R1 |

### 不修改的文件

- `context/` 全部（ImpactAnalyzer / IndexStore / project_map / graph_validator）
- `core/` 全部
- `models.py`
- 其他 Skill（token.audit / code.patch / code.search / code.impact / repo.scan / doc.generate / qa.checklist）

### 测试新增

| Step | 测试文件 | 覆盖 |
|------|---------|------|
| Step 1 | `test_risk_check.py` 扩展 | 有索引/无索引两路径 + max 风险合并 |
| Step 2 | `test_architecture_map.py` 扩展 | 索引数据源 + fallback + 循环依赖一致性 |
| Step 3 | `test_task_plan.py` 扩展 | impact 标注 + 无 target fallback |
| Step 4 | `test_skill_context_integration.py` 新建 | workflow 端到端消费索引 |

---

## 6. 风险等级与回滚方案

### 按 Step 拆分风险

| Step | 风险 | 理由 |
|------|------|------|
| Step 1 | R1 | 单文件，可选增强，有 fallback |
| Step 2 | R2 | 数据源切换，需保证循环依赖检测一致 |
| Step 3 | R1 | 增量标注，不改三档结构 |
| Step 4 | R1 | 测试 + 只读验证 |

### 回滚方案

1. 任一 Step 出问题 → 该 Skill 的索引分支用 `if index:` 包裹，删除分支即恢复原行为
2. 完全回滚 → `git revert` 对应 commit，Context Layer 不受影响
3. 优雅降级本身就是安全网：索引检测失败 → 自动走原逻辑

---

## 7. 实施路线

```
Phase 8 Step 0 ✅ 当前 — 设计确认
Phase 8 Step 1: risk.check ← code.impact      （R1，~470 tests）
Phase 8 Step 2: architecture.map ← index       （R2，~480 tests）
Phase 8 Step 3: task.plan ← impact              （R1，~488 tests）
Phase 8 Step 4: 端到端验证                       （R1，~495 tests）
```

### 不做（Phase 8 范围内）

```
❌ code.patch 真实化（→ Phase 9 Safe Patch Agent）
❌ token.audit 接入符号索引（→ 后续优化项）
❌ 新增解析语言
❌ 符号级调用图（call graph）
❌ MCP Server / Dashboard / Multi-Agent
❌ normalize/autofix 层（→ 当 LLM 参与生成图谱时再做）
```

---

## 8. 验收标准

1. 现有 458 tests 全部通过，无回归
2. risk.check 在有索引时输出受影响文件，无索引时退回关键词（两路径都有测试）
3. architecture.map 在有索引时支持多语言依赖图，无索引时退回 Python AST
4. task.plan 在有 target 时标注影响范围
5. workflow 端到端能消费 Context Layer
6. 真实项目验证：smartdev run 输出带影响范围信息
7. 优雅降级：所有接入在无索引时不报错、不中断
