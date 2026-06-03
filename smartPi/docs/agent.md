可以。后续要抽出“通用 SmartDev Agent”，关键不是再写更多说明文档，而是把现在这些内容拆成**可执行结构**：

```txt
SmartDev Agent = 通用内核 + 能力 Skill + 项目适配器 + 执行协议
```

你现在已有的文档基础已经够用了：`core-spec` 已经定义了通用能力、工作流、状态机、输入输出协议和项目适配器机制；`protocol` 负责约束“先诊断后修改、小步快跑、每步可验证、不扩大范围”；`SmartFav adapter` 则说明了项目适配器要理解具体项目结构、技术约束、可修改范围和验证方式。  

---

# 1. 先明确：通用 Agent 不等于一个大 Prompt

如果只是把所有文档塞进一个超长 Prompt，短期能跑，长期会失控。

更合理的是：

```txt
SmartDev Agent Core
├── Workflow Engine      # 控制流程
├── Skill Registry       # 管理技能
├── Adapter Loader       # 加载项目适配器
├── Risk Controller      # 判断是否可自动执行
├── Context Manager      # 管理项目上下文
└── Result Reporter      # 输出执行前/后总结
```

也就是说，**Agent Core 只负责调度，不负责把所有能力写死在自己身上**。

---

# 2. 通用 Agent 的四层结构

建议最终抽成 4 层，而不是只保留三层。

你现有 core-spec 是三层：

```txt
Core Workflow Layer
Capability Modules Layer
Project Adapter Layer
```

这个是正确的。但如果要支持 skill 调用，需要加一层：

```txt
SmartDev Agent
├── 1. Core Runtime Layer        # Agent 运行内核
├── 2. Workflow Layer            # 接入、诊断、规划、执行、验证、总结
├── 3. Skill Layer               # 可调用技能
└── 4. Project Adapter Layer     # 项目适配器
```

## 各层职责

| 层级           | 作用              | 例子                                         |
| ------------ | --------------- | ------------------------------------------ |
| Core Runtime | 负责调度、状态、权限、风险控制 | 判断是否需要确认、是否能执行                             |
| Workflow     | 负责流程推进          | 诊断 → 计划 → 执行 → 验证                          |
| Skill        | 负责具体能力          | 扫目录、查 token、生成 README、跑测试                  |
| Adapter      | 负责项目差异          | SmartFav、Document Factory、Chrome Extension |

这样 Skill 是“手”，Adapter 是“地图”，Workflow 是“步骤”，Core Runtime 是“大脑”。

---

# 3. Skill 应该怎么定义

Skill 不要定义成“随便一段 Prompt”，而应该是一个有输入、输出、风险等级、适用场景的能力单元。

建议每个 Skill 至少包含：

```yaml
id: repo.scan
name: 仓库扫描
capability: project_diagnose
risk: R0
mode: read_only
description: 扫描项目目录、识别技术栈、入口文件和文档状态
inputs:
  - project_path
  - include_patterns
  - exclude_patterns
outputs:
  - repo_tree
  - tech_stack
  - entrypoints
  - docs_status
preconditions:
  - project_path_exists
postconditions:
  - no_file_modified
```

关键点是：**Skill 必须可控、可验证、可复用**。

---

# 4. Skill 分类建议

不要一上来做几十个 Skill。第一阶段只抽最核心的 10 个。

## 第一批 Skill

| Skill ID           | 能力       |       风险 | 说明                          |
| ------------------ | -------- | -------: | --------------------------- |
| `repo.scan`        | 项目扫描     |       R0 | 扫描目录、识别技术栈                  |
| `repo.diagnose`    | 项目诊断     |       R0 | 输出项目诊断报告                    |
| `architecture.map` | 架构分析     |       R0 | 分析模块、数据流、依赖                 |
| `token.audit`      | Token 检查 |       R0 | 查重复 token、硬编码颜色             |
| `task.plan`        | 任务拆解     |       R0 | 把需求拆成小任务                    |
| `risk.check`       | 风险判断     |       R0 | 判断任务风险等级                    |
| `doc.generate`     | 文档生成     |       R1 | 生成 README / CONTRIBUTING 草案 |
| `code.patch`       | 代码修改     | R1/R2/R3 | 根据任务生成或应用 patch             |
| `qa.checklist`     | 验收清单     |       R0 | 生成测试清单                      |
| `change.summary`   | 变更总结     |       R0 | 输出修改后总结                     |

第一阶段最好只实现 **R0 只读类 Skill**，先不自动改代码。

---

# 5. Skill 调用流程

一次任务可以这样流转：

```txt
用户输入
  ↓
Intent Parser 判断任务类型
  ↓
Adapter Loader 判断项目类型
  ↓
Workflow Planner 生成步骤
  ↓
Skill Registry 选择可用 Skill
  ↓
Risk Controller 判断是否可执行
  ↓
Skill Executor 执行
  ↓
Verifier 验证
  ↓
Reporter 输出总结
```

比如用户说：

```txt
帮我统一 SmartFav 的 tokens.css，并检查 Side Panel 适配。
```

Agent 应该调用：

```txt
repo.scan
  ↓
token.audit
  ↓
architecture.map
  ↓
task.plan
  ↓
risk.check
  ↓
等待确认
  ↓
code.patch
  ↓
qa.checklist
  ↓
change.summary
```

这就比“直接改 CSS”安全得多。

---

# 6. Skill 与 Adapter 的关系

这是核心设计点。

## Adapter 不执行任务

Adapter 只告诉 Agent：

```txt
这个项目是什么
目录在哪里
哪些地方能改
哪些地方不能改
用哪些验证清单
有哪些已知坑
当前优先任务是什么
```

比如 SmartFav Adapter 里已经定义了项目是 Chrome Extension + Local Server，前端是 Vanilla JS + CSS Custom Properties，后端是 FastAPI + SQLite，并且有可修改区域、谨慎修改区域、禁止修改区域。

## Skill 负责执行能力

Skill 负责：

```txt
扫描
诊断
检查
生成
修改
验证
总结
```

所以：

```txt
Adapter = 项目地图
Skill = 可执行工具
Protocol = 行为规则
Core = 调度系统
```

---

# 7. 推荐的目录结构

如果做成一个真实项目，可以这样：

```txt
smartdev-agent/
├── smartdev/
│   ├── core/
│   │   ├── runtime.py
│   │   ├── workflow.py
│   │   ├── router.py
│   │   ├── risk.py
│   │   └── reporter.py
│   │
│   ├── skills/
│   │   ├── repo_scan/
│   │   │   ├── skill.yaml
│   │   │   └── skill.py
│   │   ├── token_audit/
│   │   │   ├── skill.yaml
│   │   │   └── skill.py
│   │   ├── task_plan/
│   │   │   ├── skill.yaml
│   │   │   └── skill.py
│   │   └── doc_generate/
│   │       ├── skill.yaml
│   │       └── skill.py
│   │
│   ├── adapters/
│   │   ├── smartfav.yaml
│   │   ├── chrome_extension.yaml
│   │   ├── fastapi.yaml
│   │   └── document_factory.yaml
│   │
│   ├── protocols/
│   │   └── execution_protocol.yaml
│   │
│   └── prompts/
│       ├── diagnose.md
│       ├── plan.md
│       ├── verify.md
│       └── summarize.md
│
├── docs/
│   ├── smartdev-agent-core-spec.md
│   ├── smartdev-agent-protocol.md
│   └── smartdev-adapter-smartfav.md
└── pyproject.toml
```

这不是要求现在马上建项目，而是说明后续抽象方向。

---

# 8. Skill 调用接口建议

可以先设计成统一函数：

```python
class Skill:
    id: str
    name: str
    capability: str
    risk: str
    mode: str

    def can_run(self, context) -> bool:
        ...

    def run(self, context, inputs) -> SkillResult:
        ...
```

统一结果：

```python
class SkillResult:
    success: bool
    summary: str
    data: dict
    changed_files: list[str]
    risks: list[str]
    validation: list[str]
    next_steps: list[str]
```

这样无论是 `repo.scan`、`token.audit` 还是 `doc.generate`，输出都能被 Core Runtime 接住。

---

# 9. Skill Manifest 示例

以 `token.audit` 为例：

```yaml
id: token.audit
name: Design Token Audit
capability: token_governance
risk: R0
mode: read_only

description: >
  检查项目中的设计令牌来源、重复 tokens.css、硬编码颜色、
  Tailwind 重复配置和 token 覆盖率。

inputs:
  required:
    - project_path
  optional:
    - token_files
    - include_patterns
    - exclude_patterns

outputs:
  - token_sources
  - duplicated_tokens
  - hardcoded_colors
  - token_usage_count
  - coverage_rate
  - recommendations

preconditions:
  - project_path_exists

postconditions:
  - no_file_modified

adapter_support:
  - smartfav
  - chrome_extension
  - web_app

validation:
  - 输出 token 来源
  - 输出硬编码颜色清单
  - 输出是否建议统一 token 来源
```

---

# 10. Skill 风险等级

直接继承你现有的 R0–R3 就够了。

| 风险 | Skill 类型         | 是否可自动执行 |
| -- | ---------------- | ------- |
| R0 | 只读分析             | 可以      |
| R1 | 文档生成、小范围样式建议     | 可执行但要说明 |
| R2 | 多文件修改、API 调整     | 需要风险和回滚 |
| R3 | 数据模型、权限、技术栈、目录重构 | 必须确认    |

这和执行协议里的“高风险任务必须先给方案，不允许直接执行”一致。

---

# 11. 通用 Agent 抽取路线

不要一下子做完整平台。建议分 5 步。

## Phase 1：只抽“只读诊断 Agent”

目标：不改代码，只读项目。

实现 Skill：

```txt
repo.scan
repo.diagnose
architecture.map
token.audit
task.plan
qa.checklist
```

这一步最安全，也最容易验证。

## Phase 2：接入 Project Adapter

目标：让 Agent 能区分项目类型。

实现：

```txt
adapter.load
adapter.match
adapter.constraints
adapter.validation
```

SmartFav 是第一个适配器。后面再抽：

```txt
chrome_extension.yaml
fastapi.yaml
document_factory.yaml
```

## Phase 3：支持文档类 Skill

目标：生成 README、CONTRIBUTING、bug-notes，但不直接覆盖文件。

实现：

```txt
doc.generate_readme
doc.generate_contributing
doc.generate_bug_notes
```

输出为草案，用户确认后再写入。

## Phase 4：支持 Patch 类 Skill

目标：生成小范围代码修改。

实现：

```txt
code.propose_patch
code.apply_patch
code.rollback_patch
```

关键约束：

```txt
默认只生成 patch，不直接应用
R2/R3 必须确认
每次 patch 必须有验证清单
```

## Phase 5：支持完整迭代闭环

目标：一次完成“小任务 → 修改 → 验证 → 总结 → 文档更新”。

这个阶段才是真正的 SmartDev Agent L4 / L5。

---

# 12. 一个实际调用例子

用户输入：

```txt
检查 SmartFav 的 tokens.css 重复问题，并给出下一步执行方案。
```

运行过程：

```yaml
task:
  mode: ui_governance
  project: SmartFav
  intent: token_unify

runtime:
  load_adapter: smartfav
  risk_policy: protocol.default

skills:
  - repo.scan
  - token.audit
  - task.plan
  - qa.checklist
  - change.summary
```

输出：

```md
# 当前理解
本轮只检查 token 重复和统一方案，不修改代码。

# 项目状态判断
SmartFav 存在 Demo tokens.css 与扩展 tokens.css 双来源。

# 关键问题
token 来源不唯一，会导致 Demo 和扩展主题漂移。

# 推荐方案
保留 apps/extension/assets/styles/tokens.css 为当前唯一来源。

# 执行任务
- 对比两份 tokens.css
- 更新 Demo 引用路径
- 废弃 assets/tokens.css
- 更新 design-tokens 说明

# 验收标准
- Demo 正常显示
- 扩展正常显示
- token 来源唯一

# 下一步
等待确认后生成 patch。
```

---

# 13. 是否需要新增文档？

目前**不建议新增完整文档**。

只需要在 `smartdev-agent-core-spec.md` 里补一节即可：

```txt
## Skill 调用机制
```

并在 `smartdev-agent-protocol.md` 中补一条：

```txt
所有 Skill 调用必须遵守风险等级和执行前/后输出协议。
```

如果后续真的开始写代码实现，再单独创建：

```txt
skills/README.md
```

它的存在理由很明确：给开发者说明如何新增 Skill。现在还没到这一步，不用提前写。

---

# 14. 最小可行实现

最小版本不用很复杂，可以先做成一个 CLI：

```bash
smartdev diagnose --project /path/to/smartfav
smartdev token-audit --project /path/to/smartfav
smartdev plan --project /path/to/smartfav --task "统一 tokens.css"
smartdev verify --project /path/to/smartfav --scope sidepanel
```

内部对应：

```txt
diagnose     → repo.scan + repo.diagnose
token-audit  → token.audit
plan         → task.plan + risk.check
verify       → qa.checklist
```

这样 SmartDev Agent 就从“文档里的 Agent”变成“可以跑的 Agent”。

---

# 15. 最终建议

后续抽通用 Agent 的路线应该是：

```txt
1. 不再扩写文档
2. 在 core-spec 中补 Skill 调用机制
3. 把能力模块拆成 Skill Registry
4. 把 SmartFav 抽成第一个 Project Adapter
5. 先实现只读 Skill
6. 再实现文档 Skill
7. 最后实现代码 Patch Skill
```

一句话：

> **先把 SmartDev Agent 做成“会读项目、会诊断、会拆任务”的 Agent，再让它逐步变成“能小步修改、能验证、能沉淀”的 Agent。**
