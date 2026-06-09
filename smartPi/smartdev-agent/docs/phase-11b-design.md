# Phase 11B — Guard Skills v0 执行前设计

> 状态：设计文档（Step 0），不动代码
> 前置：Phase 11A（Git Governance v0 ✅）/ Phase 11C（Documentation Governance v0 ✅）/ Phase 11D（Collaboration Handoff v0 ✅）
> 范围：本文档聚焦 Phase 11B Guard Skills v0 的边界、输入输出、实施路线和验收标准

---

## 1. 背景与定位

### 1.1 Phase 11B 在 SmartDev 全景中的位置

Phase 1–10 完成后，SmartDev 覆盖了 AI 编程闭环的前四步；Phase 11A/11C/11D 补上了交付记录、文档事实和协作层。现在还差一步：**"准备 apply / commit 的改动是否仍在人的工程规则内？"的自动化检查**。

```
理解项目 → 判断影响 → 生成改动 → Guard 审查 → 人工 apply/commit → 发布治理
  L1–L3      L3        L4/11D       11B          11A           11A
```

Phase 11B 的目标是：**在 AI 产出 patch / diff 之后、人点 apply 或 commit 之前，添一道确定性安全检查层。** 这道层不替代人的判断，而是确保每次改动都经过同一套 checklist 审查，让"人能理解、能判断、能验收、能回滚"从口头原则变成可执行的自动化流程。

### 1.2 一句话定位

> Phase 11B 把 AI 编程限制在"人能理解、能判断、能验收、能回滚"的节奏里——通过 5 个确定性 Guard Skill，在 patch apply 之前自动跑一次安全审查，输出结构化检查结果供人决策。

### 1.3 不是什么

```
❌ 不是让 SmartDev 替你拒绝 AI 的改动
❌ 不是代码审计工具（bandit / semgrep / npm audit 的替代品）
❌ 不是又一个 LLM-based review agent
❌ 不是 CI/CD pipeline 的替代
❌ 不是运行时安全监控
```

### 1.4 五个 Guard 能力一览

| Guard | 类型 | 说明 | 与已有能力的关系 |
|-------|------|------|-----------------|
| `change.budget` | R0 参数约束 | 单次变更文件数/行数上限检查 | 消费 scope_gate 的 max_files，扩展为独立 Skill |
| `dev.guard` | R0 规则检查 | 检查本轮任务是否违反 AI 编程硬规则 | 新增：大规模重构检测 / protected_paths 命中 / 跨模块越界 |
| `dependency.guard` | R0 只读分析 | 检测依赖 manifest 变更，输出审查报告 | 新增：package.json / pyproject.toml / go.mod diff 分析 |
| `security.review` | R0 安全清单 | 对 patch 做确定性安全 checklist | 新增：输入校验 / 路径穿越 / 命令执行 / 敏感数据 |
| `diff.explain` | R0 只读分析 | patch 级别的确定性 diff 解释 | 增强：在 git.diff.explain 基础上加 patch 专属信号 |

---

## 2. 八条硬原则（写死在设计里）

这些原则约束整个 Phase 11B，不被需求蔓延侵蚀：

1. **v0 只做确定性 checklist，不接外部扫描器。** 有 bandit / npm audit / semgrep 时打印建议命令，不强依赖。
2. **不调用任何 LLM / 模型。** 所有判断基于文件内容模式匹配、规则引擎、git diff 分析。
3. **Guard Skill 全部 R0 只读。** 输出检查结果，不修改任何文件，不拒绝任何操作。
4. **每个 Guard 独立可运行。** 不相互依赖，可按需单独调用。
5. **输出结构化 JSON + 人类可读摘要。** 复用 SkillResult 模式，所有输出同时支持机器消费和人工阅读。
6. **优雅降级。** 无 git / 无索引 / 无依赖文件时返回明确提示，不崩溃。
7. **零外部依赖。** 只用 Python 标准库和已有 SmartDev 内部能力；需要 diff 时复用现有 GitService / git diff 能力，不引第三方库，不调用外部扫描器。
8. **Guard 之间可组合。** 单独跑或 `smartdev guard run` 一键全跑，输出聚合报告。

---

## 3. 五个 Guard 详细设计

### 3.1 `change.budget` — 变更预算检查

**定位：** 把 scope_gate 的 max_files 约束从 Scope Gate 的一次性检查升级为独立可调用的 Guard Skill，增加行数预算和 schema 变更检查。

**输入：**
- `changed_files`: list[str] — 变更文件列表（来自 scope.json 或手动指定）
- `max_files`: int — 文件数上限（默认 10，可被 scope.json 覆盖）
- `max_lines`: int | None — 行数上限（可选，默认不限制）
- `allow_schema_change`: bool — 是否允许数据模型变更（默认 false）

**输出：**
```json
{
  "passed": true,
  "checks": {
    "file_count": {"actual": 3, "limit": 10, "passed": true},
    "line_count": {"actual": 142, "limit": 500, "passed": true},
    "schema_change": {"detected": false, "passed": true}
  },
  "violations": [],
  "summary": "✅ change.budget 通过：3/10 文件，142 行，无 schema 变更"
}
```

**确定性规则：**

| 规则 | 检测方式 | 违规级别 |
|------|---------|---------|
| 文件数超限 | `len(changed_files) > max_files` | error |
| 行数超限 | `sum(diff lines) > max_lines`（若指定） | warning |
| schema 变更 | 检测 `models.py` / `schema.py` / `*.sql` / migration 文件 | warning（allow_schema_change=false 时升级为 error）|
| 单文件过大 | 任一文件新增/删除 > 200 行 | warning |

**与现有能力的关系：**
- `scope_gate.py` 的 max_files 检查：change.budget 消费 scope.json 的 max_files 字段，但不替代 scope_gate。scope_gate 是 Run 粒度的边界检查；change.budget 是 patch 粒度的预算检查，可在 scope_gate 之后单独调用。
- `patch_propose` 的 `max_files` 参数：change.budget 使用相同的参数名和默认值，保持一致性。

**不做（v0 范围外）：**
- 不做限制强制执行（不拒绝 patch，只报告）
- 不做历史趋势分析（"你这个月改了太多文件"）
- 不做 per-author / per-session 配额

---

### 3.2 `dev.guard` — AI 编程规则守卫

**定位：** 检查本轮任务是否违反 AI 编程硬规则——那些在 CLAUDE.md / 协议中写死但当前靠人工自觉遵守的约束。

**输入：**
- `changed_files`: list[str] — 变更文件列表
- `diff_content`: str | None — 可选 diff 内容（更精确的规则检查）
- `project_path`: Path — 项目根目录
- `task_description`: str | None — 任务描述（用于检测"顺手优化"）

**输出：**
```json
{
  "passed": false,
  "checks": {
    "mass_refactor": {"triggered": true, "detail": "修改了 3+ 个模块目录"},
    "protected_path_hit": {"triggered": false},
    "unrelated_change": {"triggered": false},
    "test_deletion": {"triggered": false},
    "config_in_code": {"triggered": false}
  },
  "violations": [
    {"rule": "mass_refactor", "severity": "error", "message": "检测到大规模重构：3+ 模块目录同时修改"}
  ],
  "summary": "❌ dev.guard 未通过：1 个违规"
}
```

**确定性规则（第一版）：**

| 规则 | 检测方式 | 违规级别 |
|------|---------|---------|
| 大规模重构 | 变更文件分布在 3+ 个一级模块目录（如 `core/` / `skills/` / `context/` / `mcp/` 同时修改）| error |
| protected_path 命中 | 与 scope.protected_paths 的 glob 匹配 | error |
| 无关改动 | diff 中出现了与 task_description 关键词无关的文件修改（模糊匹配）| warning |
| 测试删除 | diff 中删除了 `test_*.py` 文件或测试函数（检测 `def test_` 删除行）| warning |
| 配置文件混入 | diff 中修改了 `config.json` / `.env` / `settings.py` 但同时有功能代码变更 | warning |
| 禁止文件修改 | 命中了 CLAUDE.md 中声明的禁止修改路径（如 CHANGELOG 历史记录 / phase-*-design.md）| error |
| 单 commit 过大 | 检测是否超过 max_files_per_commit（来自 git-policy.json）| warning |

**不做（v0 范围外）：**
- 不做自然语言理解（不解析 task_description 的语义，只用关键词匹配）
- 不做跨 commit 的行为分析
- 不做 git blame 分析
- 不做代码风格检查

---

### 3.3 `dependency.guard` — 依赖变更审查

**定位：** 检测项目依赖 manifest 是否变更，输出新增/删除/版本变更的审查报告。这是 AI 编程中容易被忽略但影响面大的变更类型。

**输入：**
- `changed_files`: list[str] — 变更文件列表
- `project_path`: Path — 项目根目录

**输出：**
```json
{
  "passed": true,
  "manifests_found": ["pyproject.toml"],
  "changes": {
    "added": [],
    "removed": [],
    "version_changed": [
      {"name": "fastapi", "old": "0.104.0", "new": "0.115.0", "risk": "medium"}
    ],
    "manifest_added": [],
    "manifest_removed": []
  },
  "warnings": [
    "建议运行: pip-audit 检查已知漏洞"
  ],
  "summary": "⚠ dependency.guard：pyproject.toml 中 1 个依赖版本变更（fastapi 0.104.0→0.115.0），0 个新增，0 个删除"
}
```

**确定性规则（第一版）：**

| 规则 | 检测方式 | 违规级别 |
|------|---------|---------|
| 新增依赖 | `git diff` 依赖 manifest 文件，查找新增的依赖声明行 | warning |
| 删除依赖 | `git diff` 依赖 manifest 文件，查找删除的依赖声明行 | warning |
| 版本变更 | `git diff` 依赖 manifest 文件，查找版本号变更行 | warning |
| manifest 新增 | 新建了 `package.json` / `pyproject.toml` / `go.mod` 等文件 | info |
| manifest 删除 | 删除了依赖 manifest 文件 | error |
| 锁定文件未同步 | 修改了 manifest 但未修改对应的 lock 文件（如 `pyproject.toml` 变了但 `poetry.lock` 没变）| warning |

**支持的 manifest 文件类型（第一版）：**

| 文件 | 解析方式 | 提取内容 |
|------|---------|---------|
| `pyproject.toml` | 标准库 `tomllib`（Python 3.11+）或简单行解析 | `[project] dependencies` / `[tool.poetry.dependencies]` |
| `package.json` | 标准库 `json` | `dependencies` / `devDependencies` / `peerDependencies` |
| `go.mod` | 行解析（`require (...)` 块） | module 声明 + require 列表 |
| `requirements.txt` | 行解析（`package==version`） | 依赖名 + 版本 |

**外部工具建议（只打印，不调用）：**

```
检测到 Python 依赖变更 → 建议运行: pip-audit
检测到 Node.js 依赖变更 → 建议运行: npm audit
检测到 Go 依赖变更 → 建议运行: govulncheck ./...
检测到多文件变更 → 建议运行: semgrep --config=auto
```

**不做（v0 范围外）：**
- 不做依赖解析（不下载包、不解析传递依赖）
- 不做漏洞数据库查询
- 不做许可证检查
- 不调用 pip-audit / npm audit / semgrep（只打印建议命令）
- 不做依赖树可视化

---

### 3.4 `security.review` — 安全审查清单

**定位：** 对 patch 或受影响文件做确定性安全 checklist 检查。不替代专业安全审计，但覆盖 AI 生成代码最常见的 6 类安全问题。

**输入：**
- `changed_files`: list[str] — 变更文件列表
- `diff_content`: str | None — diff 内容（用于更精确的检查）
- `project_path`: Path — 项目根目录

**输出：**
```json
{
  "passed": true,
  "checks": {
    "input_validation": {"triggered": false, "files": []},
    "path_traversal": {"triggered": false, "files": []},
    "command_injection": {"triggered": false, "files": []},
    "sensitive_data": {"triggered": true, "files": ["config.py"], "detail": "检测到 API key 模式"},
    "hardcoded_secrets": {"triggered": false, "files": []},
    "eval_exec": {"triggered": false, "files": []}
  },
  "violations": [
    {"rule": "sensitive_data", "severity": "warning", "file": "config.py", "message": "检测到可能的 API key 硬编码: 'sk-...'"}
  ],
  "suggestions": [
    "建议运行: semgrep --config=auto 进行更全面的安全扫描"
  ],
  "summary": "⚠ security.review：1 个警告（sensitive_data），0 个错误"
}
```

**六类安全检查（第一版确定性规则）：**

#### 3.4.1 输入校验（input_validation）

| 检测模式 | 说明 | 级别 |
|---------|------|------|
| `request.args.get(` / `request.form[` / `req.body` 后无校验 | FastAPI/Flask 路由参数未校验 | warning |
| `int(input())` / `eval(input())` | 用户输入直接转换/执行 | error |
| 新文件包含 `<input` / `<form` 但无 `required` / `pattern` | HTML 表单无前端校验 | info |

#### 3.4.2 路径穿越（path_traversal）

| 检测模式 | 说明 | 级别 |
|---------|------|------|
| `os.path.join(` 参数包含用户输入变量 | 潜在路径穿越 | warning |
| `open(` 参数包含 `request`/`argv`/`input` 相关变量 | 文件操作使用用户输入 | warning |
| `Path(` 拼接用户输入且无 `.resolve()` 校验 | 路径未规范化 | warning |

#### 3.4.3 命令执行（command_injection）

| 检测模式 | 说明 | 级别 |
|---------|------|------|
| `subprocess.run(` 使用 `shell=True` | Shell 注入风险 | error |
| `os.system(` / `os.popen(` | 命令注入风险 | error |
| `subprocess.run(` 参数列表含用户输入且未过滤 | 潜在命令注入 | warning |
| `eval(` / `exec(` | 代码执行风险 | error |

#### 3.4.4 敏感数据（sensitive_data）

| 检测模式 | 说明 | 级别 |
|---------|------|------|
| 包含 `password` / `secret` / `token` / `api_key` 变量名且赋值为字符串字面量 | 硬编码凭证 | warning |
| `print(` / `console.log(` 包含 `password` / `token` 变量 | 可能日志泄露 | info |
| 匹配 `sk-` / `ghp_` / `gho_` / `xoxb-` / `xoxp-` 等已知 token 前缀 | 已知 API key 模式 | error |
| `.env` / `.env.local` 文件被加入 diff | 环境文件泄露 | error |

#### 3.4.5 硬编码密钥（hardcoded_secrets）

| 检测模式 | 说明 | 级别 |
|---------|------|------|
| 正则匹配 `[a-zA-Z0-9]{32,}` 赋值为字符串字面量 | 长随机字符串可能是 key | info |
| `-----BEGIN.*PRIVATE KEY-----` | PEM 私钥硬编码 | error |
| JWT token 硬编码（`eyJ` 前缀 + base64 模式） | 硬编码 JWT | warning |

#### 3.4.6 eval/exec（eval_exec）

| 检测模式 | 说明 | 级别 |
|---------|------|------|
| AST 解析检测 `eval(` / `exec(` / `compile(` 调用 | 动态代码执行 | error |
| `__import__(` 调用 | 动态导入 | warning |
| `getattr(` / `setattr(` 参数非字面量 | 动态属性访问 | info |

**外部工具建议（只打印，不调用）：**
```
检测到 Python 文件变更 → 建议运行: bandit -r <project>
检测到 JS/TS 文件变更 → 建议运行: semgrep --config=auto
检测到多语言混合变更 → 建议运行: semgrep --config=auto && bandit -r <project>
```

**不做（v0 范围外）：**
- 不做数据流分析（不追踪变量从来源到汇点）
- 不做完整的语义分析（不用 AST 做深度检查，第一版只做文本模式匹配）
- 不维护 CVE 数据库
- 不做权限模型分析
- 不做加密算法强度审核

---

### 3.5 `diff.explain` — Patch 级差异解释

**定位：** 在已有 `git.diff.explain`（仓库级）基础上，增加 patch 专属信号：哪些变更属于同一个逻辑单元、是否有测试伴随、依赖变更是否与功能变更匹配。

**与 `git.diff.explain` 的关系：**

| 维度 | `git.diff.explain`（Phase 11A ✅） | `diff.explain`（Phase 11B） |
|------|-----------------------------------|---------------------------|
| 粒度 | 仓库级（整个 working tree diff）| Patch 级（code.patch 的输出） |
| 触发时机 | 任何时候（`smartdev git diff-explain`）| `smartdev guard run` 或 patch propose 之后 |
| 输出内容 | 文件分类 / 行数 / 风险信号 / 拆分建议 | 上述 + 逻辑分组 / 测试伴随 / 依赖匹配 |
| 消费方 | Git 工作流（拆分 commit）| Guard 工作流（安全审查） |

**输入：**
- `patch_files`: list[str] — patch 涉及的文件列表
- `diff_content`: str | None — diff 文本内容
- `project_path`: Path — 项目根目录

**输出：**
```json
{
  "summary": {
    "files_changed": 5,
    "insertions": 120,
    "deletions": 30,
    "logical_groups": 2
  },
  "signals": {
    "touches_tests": true,
    "touches_docs": false,
    "touches_dependency_manifest": true,
    "touches_protected_path": false,
    "touches_core": true,
    "touches_mcp": false,
    "cross_module": true
  },
  "logical_groups": [
    {
      "label": "core logic change",
      "files": ["smartdev/core/git.py", "smartdev/core/patch.py"],
      "description": "影响 L4-L5 核心运行时"
    },
    {
      "label": "test coverage",
      "files": ["tests/test_git.py", "tests/test_patch.py", "tests/test_integration.py"],
      "description": "测试伴随变更"
    }
  ],
  "risk_hints": [
    "cross_module_change",
    "dependency_manifest_changed_without_lock_file"
  ],
  "test_coverage": {
    "has_related_tests": true,
    "test_files_touched": 3,
    "untested_changed_modules": ["smartdev/cli.py"]
  },
  "suggested_review_order": [
    "1. 先审查 smartdev/core/git.py（核心逻辑）",
    "2. 再审查 smartdev/core/patch.py（接口变更）",
    "3. 确认 tests/ 覆盖所有变更路径"
  ]
}
```

**确定性规则（第一版）：**

| 规则 | 检测方式 | 说明 |
|------|---------|------|
| 逻辑分组 | 按目录层级将文件分组（`core/` / `skills/` / `tests/` / `docs/`） | 帮助理解变更结构 |
| 测试伴随 | 检查 `tests/` 目录下是否有对应测试文件被修改 | 功能变更没有测试 → warning |
| 依赖匹配 | 依赖 manifest 变更时，检查是否有对应的 import 变更 | manifest 变了但没改代码 → warning |
| 跨模块影响 | 变更文件分布在 2+ 个一级模块目录 | risk_hint |
| 审查顺序建议 | 按依赖关系排序审查顺序（core → skills → mcp → tests） | 帮助 reviewer 高效审查 |
| core 触及 | 变更文件包含 `core/` 路径 | risk_hint |

**不做（v0 范围外）：**
- 不做语义 diff（不比较 AST，不做函数级别的影响分析）
- 不做与 git.diff.explain 的完全合并（两个 Skill 保持独立，分别面向不同场景）
- 不做自动 assign reviewer

---

## 4. 文件结构设计

```
smartPi/smartdev-agent/
└── smartdev/
    ├── core/
    │   ├── guard_budget.py       ← 新建：change.budget 规则引擎（R0）
    │   ├── guard_dev.py          ← 新建：dev.guard 规则引擎（R0）
    │   ├── guard_dependency.py   ← 新建：dependency.guard 规则引擎（R0）
    │   ├── guard_security.py     ← 新建：security.review 规则引擎（R0）
    │   ├── guard_diff_explain.py ← 新建：diff.explain patch 级规则引擎（R0）
    │   └── guard_runner.py       ← 新建：GuardRunner — 一键全跑 + 聚合报告（R0）
    └── skills/
        ├── change_budget/        ← 新建：change.budget Skill（R0）
        ├── dev_guard/            ← 新建：dev.guard Skill（R0）
        ├── dependency_guard/     ← 新建：dependency.guard Skill（R0）
        ├── security_review/      ← 新建：security.review Skill（R0）
        └── diff_explain_patch/   ← 新建：diff.explain Skill（R0，patch 级）
```

每个 Guard Skill 沿用现有约定：`skills/<name>/skill.py + skill.yaml`，靠 `__init_subclass__` 自动注册。

**为什么不放在一个文件里：**
- 每个 Guard 是独立的规则引擎，可单独测试、单独调用、单独演进
- 与 Phase 11A git skills 的设计模式一致（每个 git skill 独立目录）
- GuardRunner 负责组合，不增加单个文件的复杂度

---

## 5. 与现有能力的边界说明

### 5.1 `change.budget` vs `scope_gate`

| 维度 | scope_gate（Phase 11D ✅） | change.budget（Phase 11B） |
|------|--------------------------|---------------------------|
| 触发时机 | `smartdev run scope-check` | `smartdev guard run` 或 patch propose 阶段 |
| 检查级别 | Run 级别（整个任务） | Patch 级别（单次 patch） |
| 检查内容 | max_files / denied / protected / allowed | max_files + max_lines + schema_change + per_file_limit |
| 输出消费者 | Handoff Pack（告知 Code Agent 边界） | Guard Report（告知 Human 变更风险） |
| 关系 | scope_gate 先做准入判断 | change.budget 后做粒度审查，消费 scope_gate 的 max_files |

两者不替代，是协作关系：scope_gate 决定"能不能改这些文件"，change.budget 决定"这次改的量是否合理"。

### 5.2 `diff.explain` vs `git.diff.explain`

| 维度 | git.diff.explain（Phase 11A ✅） | diff.explain（Phase 11B） |
|------|--------------------------------|---------------------------|
| 粒度 | 仓库级（working tree diff） | Patch 级（code.patch 输出文件） |
| 触发方 | 开发者随时调用 | Guard Runner 自动调用 |
| 特有信号 | commit_split / file_categories / protected_path_hits | logical_groups / test_coverage / review_order |
| 消费方 | Git 工作流 | Guard 工作流 + Human Review |
| MCP 工具 | `smartdev_git_diff_explain`（已有） | 不单独暴露 MCP，作为 guard run 的一部分 |

两者独立，各司其职。`diff.explain` 在输出中引用 `git.diff.explain` 的既有信号（如 file_categories），但新增 patch 专属维度。

### 5.3 `dependency.guard` vs `doc.map` manifest 检测

| 维度 | doc.map（Phase 11C ✅） | dependency.guard（Phase 11B） |
|------|------------------------|------------------------------|
| 功能 | 列出项目中的所有文档和 manifest 文件 | 检测 manifest 文件的 diff 变更 |
| 输入 | 文件系统（全量扫描） | git diff（增量变更） |
| 输出 | 文档地图 | 依赖变更报告 |
| 关系 | doc.map 告诉我们有哪些 manifest | dependency.guard 告诉我们 manifest 变了什么 |

---

## 6. 实施路线

```
Step 0  设计文档 phase-11b-design.md（本文档）                        ✅ 完成

Step 1  change.budget（R0，优先级最高）                               ✅ 完成
        - smartdev/core/guard_budget.py（规则引擎）
        - smartdev/skills/change_budget/skill.py + skill.yaml
        - 消费 scope.json 的 max_files，扩展 max_lines / schema_change / per_file_limit
        - tests/test_guard_budget.py（60 tests）

Step 2  dev.guard（R0）                                                ← 下一步
        - smartdev/core/guard_dev.py（规则引擎）
        - smartdev/skills/dev_guard/skill.py + skill.yaml
        - 7 条 AI 编程硬规则检查
        - tests/test_guard_dev.py（预计 14-20 tests）

Step 3  dependency.guard（R0）
        - smartdev/core/guard_dependency.py（规则引擎 + manifest 解析）
        - smartdev/skills/dependency_guard/skill.py + skill.yaml
        - 4 种 manifest 格式解析 + 外部工具建议
        - tests/test_guard_dependency.py（预计 16-22 tests）

Step 4  security.review（R0）
        - smartdev/core/guard_security.py（规则引擎，6 类安全检查）
        - smartdev/skills/security_review/skill.py + skill.yaml
        - tests/test_guard_security.py（预计 20-28 tests）

Step 5  diff.explain（R0，patch 级）
        - smartdev/core/guard_diff_explain.py（规则引擎）
        - smartdev/skills/diff_explain_patch/skill.py + skill.yaml
        - 消费 git.diff.explain 既有信号 + patch 专属逻辑分组/测试伴随
        - tests/test_guard_diff_explain.py（预计 14-20 tests）

Step 6  GuardRunner 组合 + CLI 入口（R0）
        - smartdev/core/guard_runner.py（一键全跑 + 聚合报告）
        - CLI: smartdev guard run [--select change.budget,dev.guard]
        - tests/test_guard_runner.py（预计 10-14 tests）

Step 7  MCP 暴露只读 Guard 工具（R0）
        - MCP 工具: smartdev_guard_run（聚合报告）
        - MCP 工具: smartdev_change_budget / smartdev_dev_guard / smartdev_dependency_guard
        - MCP 工具: smartdev_security_review / smartdev_diff_explain
        - MCP 工具总数: 24（Phase 11D）→ 30（Phase 11B）
        - tests/test_mcp_guard_tools.py（预计 14-18 tests）
```

每步独立可测、可回滚，节奏与 Phase 9 / 10 / 11A 一致。

### 推荐实施顺序理由

1. **change.budget 先做**：它是最基础的约束，scope_gate 已经做了前半段（文件数），change.budget 补上后半段（行数/schema），且有最大的复用价值（patch_propose / handoff-code 都可以消费）。
2. **dev.guard 其次**：直接落地 AI 编程硬规则，是从"约定"到"可执行"的关键一步。dev.guard 的规则最稳定（不依赖外部数据），实施风险最低。
3. **dependency.guard 第三**：依赖变更检测是 AI 编程中最容易被忽略但影响面最大的变更。需要解析 4 种 manifest 格式，工作量中等。
4. **security.review 第四**：6 类安全检查规则最多，需要逐类实现和调参。放在后面是因为前面三个 Guard 的实施经验可以帮助确定规则引擎的模式。
5. **diff.explain 最后**：它在 git.diff.explain 基础上增强，不引入全新概念，依赖前面 Guard 的信号（如 dependency.guard 的 manifest 检测结果）。

---

## 7. 聚合报告格式（GuardRunner 输出）

`smartdev guard run` 一键跑完 5 个 Guard，输出聚合报告：

```json
{
  "run_id": "phase-11b-design",
  "timestamp": "2026-06-09T16:00:00",
  "overall_passed": false,
  "guards": {
    "change.budget": {
      "passed": true,
      "summary": "✅ 3/10 文件，142 行，无 schema 变更",
      "duration_ms": 12
    },
    "dev.guard": {
      "passed": false,
      "summary": "❌ 检测到跨模块重构（3+ 模块同时修改）",
      "duration_ms": 45
    },
    "dependency.guard": {
      "passed": true,
      "summary": "⚠ pyproject.toml 版本变更：fastapi 0.104.0→0.115.0",
      "duration_ms": 89
    },
    "security.review": {
      "passed": true,
      "summary": "⚠ 1 个警告：config.py 检测到 API key 模式",
      "duration_ms": 156
    },
    "diff.explain": {
      "passed": true,
      "summary": "✅ 5 文件，2 个逻辑分组，测试伴随完整",
      "duration_ms": 34
    }
  },
  "total_duration_ms": 336,
  "error_count": 1,
  "warning_count": 2,
  "info_count": 0,
  "suggested_actions": [
    "1. 检查跨模块重构是否必要，考虑拆分为多次小改动",
    "2. 确认 fastapi 版本升级的兼容性",
    "3. 将 config.py 中的 API key 迁移到环境变量"
  ]
}
```

---

## 8. 影响范围分析

### 需要新增/修改的文件

| 文件 | 变更 | 风险 | Step |
|------|------|------|------|
| `smartdev/core/guard_budget.py` | 新建 | R1 | 1 |
| `smartdev/core/guard_dev.py` | 新建 | R1 | 2 |
| `smartdev/core/guard_dependency.py` | 新建 | R1 | 3 |
| `smartdev/core/guard_security.py` | 新建 | R1 | 4 |
| `smartdev/core/guard_diff_explain.py` | 新建 | R1 | 5 |
| `smartdev/core/guard_runner.py` | 新建 | R1 | 6 |
| `smartdev/skills/change_budget/` | 新建 | R1 | 1 |
| `smartdev/skills/dev_guard/` | 新建 | R1 | 2 |
| `smartdev/skills/dependency_guard/` | 新建 | R1 | 3 |
| `smartdev/skills/security_review/` | 新建 | R1 | 4 |
| `smartdev/skills/diff_explain_patch/` | 新建 | R1 | 5 |
| `smartdev/cli.py` | +`smartdev guard run` 命令 | R1 | 6 |
| `smartdev/mcp/tools.py` | +6 个 MCP Guard 工具 | R1 | 7 |
| `smartdev/mcp/server.py` | 注册 6 个 Guard 工具 schema | R1 | 7 |
| `docs/phase-11b-design.md` | 新建 | R0 | 0 |

### 完全不修改的文件

- `context/` 全部（索引 / impact / relations 等）
- `core/` 现有文件（git / patch / risk / reporter / workflow）——只新增 guard_*.py
- `skills/` 现有 Skill（不改任何已有 Skill）
- `models.py` / `detectors/` 全部
- 现有 `tests/` 全部（只新增测试文件）

### 测试新增（预估）

| Step | 测试文件 | 覆盖内容 | 预计数量 |
|------|---------|---------|---------|
| Step 1 | `test_guard_budget.py` | max_files / max_lines / schema_change / per_file / 边界情况 | 12–16 |
| Step 2 | `test_guard_dev.py` | 7 条规则 + 边界 + 组合违规 | 14–20 |
| Step 3 | `test_guard_dependency.py` | 4 种 manifest 解析 + diff 检测 + 外部工具建议 | 16–22 |
| Step 4 | `test_guard_security.py` | 6 类安全检查 + 误报控制 + 边界 | 20–28 |
| Step 5 | `test_guard_diff_explain.py` | 逻辑分组 / 测试伴随 / 依赖匹配 / 审查顺序 | 14–20 |
| Step 6 | `test_guard_runner.py` | 组合运行 / 聚合报告 / --select 过滤 | 10–14 |
| Step 7 | `test_mcp_guard_tools.py` | 6 个 MCP Guard 工具 + 优雅降级 | 14–18 |

测试用 fixture：在临时目录构造小项目（含各种 manifest / 代码模式），避免依赖真实项目状态。

---

## 9. 风险等级与回滚方案

### 按 Step 拆分

| Step | 风险 | 说明 |
|------|------|------|
| Step 0 | R0 | 设计文档 |
| Step 1 | R1 | 新增 guard_budget.py + change_budget Skill |
| Step 2 | R1 | 新增 guard_dev.py + dev_guard Skill |
| Step 3 | R1 | 新增 guard_dependency.py + dependency_guard Skill |
| Step 4 | R1 | 新增 guard_security.py + security_review Skill |
| Step 5 | R1 | 新增 guard_diff_explain.py + diff_explain_patch Skill |
| Step 6 | R1 | GuardRunner + CLI 入口 |
| Step 7 | R1 | MCP 只读 Guard 工具 |

> 所有 Guard Skill 为 R0 只读，不修改任何文件。风险主要来自新增代码的 bug（如规则误报/漏报），而非对现有系统的破坏。

### 回滚方案

1. 任一 Step 出问题 → `git revert` 对应 commit，现有功能不受影响。
2. 所有 Guard 完全独立，删除 `guard_*.py` + `skills/<guard_name>/` + cli/mcp 的 guard 入口即可完全回滚。
3. 不修改任何现有 Skill / Context Layer / 现有 core 文件，无 regression 风险。
4. Guard Runner 是一键调用，不改变任何现有 workflow。

---

## 10. Phase 11B 不做的事（硬约束）

```
❌ 不接外部扫描器（bandit / npm audit / semgrep / pip-audit / govulncheck）
❌ 不调用 LLM / 模型做判断
❌ Guard 运行时不修改任何被审查源码文件（全部 R0 只读）
❌ 不拒绝任何 patch（只输出报告，不强制执行）
❌ 不引入第三方 Python 依赖（保持 core 零依赖）
❌ 不改变现有 Skill / Context Layer / MCP 工具的行为语义（后续 Step 6/7 只新增入口和注册）
❌ 不做数据流分析 / 语义分析（第一版只做文本模式匹配）
❌ 不做历史趋势 / 统计数据
❌ 不做自动修复 / 自动回滚
❌ 不替代 scope_gate（change.budget 与 scope_gate 各司其职）
❌ 不替代 git.diff.explain（diff.explain 与 git.diff.explain 各司其职）
```

---

## 11. 验收标准

1. `docs/phase-11b-design.md` 存在且结构完整（本文档）。
2. 文档包含 11B 目标：把 AI 编程限制在"人能理解、能判断、能验收、能回滚"的节奏里。
3. 文档包含 5 个 Guard 能力的完整设计：
   - `change.budget`：边界、输入输出、确定性规则、与 scope_gate 的关系
   - `dev.guard`：7 条 AI 编程硬规则、检查方式、违规级别
   - `dependency.guard`：4 种 manifest 格式支持、diff 检测规则、外部工具建议
   - `security.review`：6 类安全检查、检测模式、级别定义
   - `diff.explain`：patch 级增强、与 git.diff.explain 的关系、逻辑分组/测试伴随
4. 文档明确推荐实施顺序和理由：
   - Step 1: `change.budget`（基础约束，scope_gate 已做前半段）
   - Step 2: `dev.guard`（AI 编程硬规则，从约定到可执行）
   - Step 3: `dependency.guard`（依赖变更检测，影响面大）
   - Step 4: `security.review`（规则最多，经验积累后实施）
   - Step 5: `diff.explain`（在既有能力上增强）
5. 文档明确"确定性 checklist，不接外部扫描器"原则。
6. 文档允许输出建议命令但不强依赖：`npm audit` / `pip-audit` / `semgrep` / `bandit` / `govulncheck`。
7. 文档说明 `change.budget` 与现有 `scope_gate` / `patch_propose.max_files` 的关系（§5.1）。
8. 文档说明 `diff.explain` 与既有 `git.diff.explain` / patch `diff_explain` 的关系（§5.2）。
9. 文档说明 `dependency.guard` 与 `doc.map` manifest 检测的关系（§5.3）。
10. 7 步实施路线定义清晰，每步独立可测可回滚。
11. 所有 Guard 定位为 R0 只读，不修改任何文件，不拒绝任何操作。
12. 聚合报告格式（GuardRunner 输出）定义完整。
13. Scope Gate 通过：变更文件仅 `docs/phase-11b-design.md`（1 个文件，≤3，在 allowed_paths 内）。

---

## 12. 与后续 Phase 的关系

```
Phase 11B  Guard Skills v0           ← 本设计，安全防护层（L5）
    ↓
Phase 12   Model Collaboration Layer（横向 L7）
           - 12A: Policy 配置层（model registry + task router）
           - 12B: Router 真实路由（依赖 Phase 10 跑稳）
           - Guard Skills 的守护报告可作为 model router 的输入信号
    ↓
Phase 13   Call Graph（函数级引用分析）
    ↓
Phase 14   FileWatcher / Incremental Sync
```

Phase 11B 完成后，Human-Controlled AI Coding Loop 的六个门全部闭合：

| 门 | 对应能力 | 覆盖阶段 |
|----|---------|---------|
| 理解门 | code.index / code.search / project.map / architecture.map | Phase 1–7 ✅ |
| 影响门 | code.impact / graph.validate | Phase 6–8 ✅ |
| 风险门 | risk.check（含 impact 增强）/ RiskController | Phase 8 ✅ |
| 权限门 | R0–R3 等级 / protected_paths / apply 显式确认 | Phase 9 ✅ |
| 测试门 | qa.checklist / patch propose 输出验证清单 | Phase 10 ✅ |
| 回滚门 | code.rollback / .smartdev/patch_backups/ 备份 | Phase 9 ✅ |
| 守护门 | change.budget / dev.guard / dependency.guard / security.review / diff.explain | **Phase 11B ← 本设计** |

加上 Phase 11A（Git 交付记录）和 Phase 11C（文档治理）和 Phase 11D（模型协作 Handoff），Phase 11 四块共同构成 Human-Controlled AI Coding Layer 的完整闭环。

---

## 13. 参考

| 文档 | 路径 | 相关内容 |
|------|------|---------|
| Phase 11 整体设计 | `docs/phase-11-design.md` | §2 Q7（11B 第一版确定性 checklist）/ §8（11B 不做的事）/ §9（11B 范围） |
| Phase 11A 设计 | `docs/phase-11-design.md` | git.diff.explain Skill（diff.explain 的前置能力） |
| Phase 11C 设计 | `docs/phase-11c-design.md` | doc.map / manifest 检测（dependency.guard 的前置能力） |
| Phase 11D 设计 | `docs/phase-11d-design.md` | scope_gate / change.budget 引用 / handoff pack |
| Phase 9 设计 | `docs/phase-9-design.md` | Safe Patch（patch_propose / apply / rollback） |
| 开发进度 | `docs/development-progress.md` | 当前测试基线 / 路线图 |
| Scope Gate 实现 | `smartdev/core/scope_gate.py` | max_files 检查（change.budget 的前半段） |
| Git Diff Explain | `smartdev/skills/git_diff_explain/skill.py` | 仓库级 diff 解释（diff.explain 的参考实现） |
