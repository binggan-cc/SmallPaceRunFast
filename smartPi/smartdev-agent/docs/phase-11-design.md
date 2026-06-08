# Phase 11 — Human-Controlled AI Coding Layer 执行前设计

> 状态：设计文档（Step 0），不动代码
> 前置：Phase 10 已完成并冻结（637 tests，14 个 MCP 工具，清洁基线）
> 范围：本文档聚焦 **Phase 11A — Git Governance v0**；11B（Guard Skills）/ 11C（Model Collaboration Policy）只给方向，不在本次实施

---

## 1. 背景与定位

### 1.1 SmartDev 当前能做什么、缺什么

Phase 1–10 完成后，SmartDev 已覆盖 AI 编程闭环的前四步：

```
理解项目 → 判断影响 → 安全修改 → 测试验收 → [版本提交] → [发布治理]
  L1–L3      L3         L4(Phase9)    L2          ❌缺          ❌缺
```

已具备：
- 理解：code.index / code.search / project.map / architecture.map
- 规划：task.plan / risk.check / qa.checklist
- 影响：code.impact / graph.validate
- 安全修改：code.patch(propose) → code.apply → code.rollback
- 能力分发：MCP Server v0（14 工具）

**还缺闭环的后两步——"改完之后怎么交付"：**

```
解释 diff → 拆 commit → 写提交说明 → 合并前检查 → 版本规划
```

这正好接在 Phase 9 Safe Patch 之后。Phase 11A 补的是 **交付记录层（L5）**。

### 1.2 Phase 11A 的正确定位

```
Git Governance v0 = 让 SmartDev 帮你看懂改动、拆好提交、写清说明、
                    检查合并与发布风险；真正写 Git 历史由人显式触发
```

不是：

```
❌ 让 SmartDev 替你自动提交代码
❌ 让 SmartDev 自动 merge / push / 发布
❌ 又一个 Git 封装库
❌ LLM 风格的 diff 自然语言总结
```

### 1.3 一句话原则

> Phase 11A 的核心不是让 SmartDev 替你提交代码，而是让 SmartDev 帮你看懂当前改动、拆好提交、写清说明、检查合并和发布风险；真正写 Git 历史必须由人显式触发。

---

## 2. 八条硬原则（写死在设计里）

这些原则约束整个 Phase 11A，不被需求蔓延侵蚀：

1. Git Governance **不自动提交、不自动合并、不自动推送**。
2. Skill 只做**只读分析和建议**（R0）。
3. 写 Git 历史的操作**只能通过显式 CLI Command 执行**。
4. 所有执行类命令**默认 dry-run**，必须 `--apply` 才真正执行。
5. **不引 GitPython**，全部通过 `subprocess` 调系统 `git`，保持零依赖。
6. MCP **只暴露只读 Git 工具**，永不暴露 commit / tag / push / merge / rebase / reset。
7. Git commit / tag **不进入默认 workflow**。
8. `code.apply` 和 `git.commit` **必须分离**，apply 绝不自动 commit。

---

## 3. 七个核心问题（已拍板）

| 问题 | 结论 |
|------|------|
| Q1 11A vs 11B 先做 | **先做 11A Git Governance**；11B Guard Skills 在后，11C Model Policy 可选 |
| Q2 subprocess vs 库 | **纯 subprocess 调系统 git**，零依赖，不引 GitPython，不做 optional provider |
| Q3 diff.explain 形态 | **确定性结构化输出**，不用 LLM；自然语言解释留给外部 Agent |
| Q4 commit/tag 形态 | **建议/计划做 Skill（R0）；执行 commit/tag 做 CLI Command（R2，默认 dry-run）** |
| Q5 git-policy.yaml | **现在就做轻量读取 + 安全默认值**，不强制用户先写配置 |
| Q6 MCP 边界 | **MCP 只暴露只读 Git 工具**，写 Git 历史永不进 MCP |
| Q7 11B 范围 | **确定性 checklist，不接外部扫描器**（有 bandit/npm audit/semgrep 时打印建议命令）|

### Q1：先做 11A Git Governance

Phase 9 解决"怎么安全改"，Phase 11A 解决"改完后怎么提交、记录、合并、发布"。11B 的 guard skills 大量依赖 diff / commit / manifest 变更上下文，必须在 11A 之后。

顺序：**11A Git Governance → 11B Guard Skills → 11C Model Collaboration Policy（可选）**

### Q2：纯 subprocess 调系统 git

新增 `smartdev/core/git.py`，封装只读 git 命令：

```
git status --porcelain=v1
git diff --name-status
git diff --numstat
git diff --cached --numstat
git branch --show-current
git log --oneline
git tag
```

没有 git 时：返回 `GitNotAvailable` / `GIT_NOT_FOUND`，不抛未处理异常，不自动安装。Git Governance 本身就是 Git 项目能力，不需要像 NodeBridge 那样做 optional provider，没有 git 时明确报错即可。

### Q3：git.diff.explain 做确定性结构化解释

守住"零 LLM、确定性输出、结构化判断"的项目基因。第一版不做"像人一样总结语义"，而是输出可被 MCP / 外部 Agent 消费的结构化信息：

```json
{
  "summary": {
    "files_changed": 7,
    "insertions": 214,
    "deletions": 32
  },
  "signals": {
    "touches_tests": true,
    "touches_docs": true,
    "touches_dependency_manifest": false,
    "touches_protected_path": false
  },
  "risk_hints": ["multi_file_change", "context_layer_change"],
  "suggested_commit_split": ["core change", "tests", "docs"]
}
```

字段全集：`changed_files / staged_files / unstaged_files / added_lines / deleted_lines / file_categories / protected_path_hits / dependency_manifest_changed / test_files_changed / docs_changed / likely_scope / risk_hints / suggested_split`。

自然语言解释由外部 Agent 拿到结构化 diff 后自己组织（与 `patch_propose` 的 `diff_explain` 思路一致）。

### Q4：建议做 Skill，执行做 CLI Command

把"判断"和"执行"彻底拆开：

| 能力 | 形态 | 风险 | 说明 |
|------|------|------|------|
| `git.status` | Skill | R0 | 只读状态 |
| `git.diff.explain` | Skill | R0 | 确定性 diff 解释 |
| `git.commit.plan` | Skill | R0 | 拆 commit 建议 |
| `git.commit.message` | Skill | R0 | 只生成 Conventional Commit message |
| `git.release.plan` | Skill | R0 | semver bump 建议 |
| `git.merge.check` | Skill | R0 | 合并前检查 |
| `git.tag.plan` | Skill | R0 | tag 建议 |
| `git commit` | **CLI Command** | **R2** | 默认 dry-run，`--apply` 才写 Git 历史 |
| `git tag` | **CLI Command** | **R2** | 默认 dry-run，`--apply` 才打 tag |

对应关系：

```
Skill    = propose / explain / plan      （R0，只读，自动注册，可进 MCP）
Command  = execute                       （R2，写 Git 历史，显式 --apply，不进 MCP）
```

呼应 Phase 9：`code.patch → propose` / `code.apply → explicit apply`；Git 这里 `git.commit.plan → propose` / `git commit → explicit apply`。

**为什么 commit/tag 不做成普通 Skill：**
- 普通 Skill 会被 `__init_subclass__` 自动注册，进而可能被 MCP 暴露——而写 Git 历史永不能进 MCP。
- 做成 CLI Command 天然隔离，外部 Agent 无法通过工具调用触发。
- 如需复用内部逻辑，可实现内部 `GitCommitAction` 类，但不作为外部可注册 Skill。

**为什么按 R2 而不是 R1：** commit/tag 虽然通常不改源码，但会**改变 Git 历史**，影响不可随手撤销，按 R2 管控（需确认）。

### Q5：git-policy.yaml 现在就做轻量读取 + 安全默认值

路径优先级：`.smartdev/git-policy.json`（优先）→ 项目根 `smartdev.git.json`。

第一版支持：

```json
{
  "branch": {
    "protected": ["main", "master"]
  },
  "commit": {
    "convention": "conventional",
    "require_tests_before_commit": false,
    "require_changelog_for_phase": true,
    "max_files_per_commit": 12
  },
  "release": {
    "changelog_file": "CHANGELOG.md",
    "version_files": ["pyproject.toml"]
  },
  "dangerous": {
    "forbid_push": true,
    "forbid_force_push": true,
    "forbid_reset_hard": true,
    "forbid_rebase": true,
    "forbid_merge_apply": true
  }
}
```

**没有 policy 文件用默认值；有则只覆盖明确字段，不要求完整配置。** 默认安全值：protected = main/master，dangerous 全部 forbid。

> 注：policy 文件格式用 **JSON**（`.smartdev/git-policy.json`），用标准库 `json` 解析，保持零依赖。YAML 不引入。

### Q6：MCP 只暴露只读 Git 工具

可进 MCP：

```
smartdev_git_status
smartdev_git_diff_explain
smartdev_git_commit_plan
smartdev_git_release_plan
smartdev_git_merge_check
```

永不进 MCP：`git commit` / `git tag` / `git merge` / `git push` / `git rebase` / `git reset`。

原因：Git 写操作改变项目历史，外部 Agent 不能默认拥有这个权限。边界写死。

### Q7：11B 第一版确定性 checklist，不接外部扫描器

11B（后续阶段）只做：`dependency.guard` / `security.review` / `change.budget` / `dev.guard` / `diff.explain`，全部确定性规则。有外部工具时打印建议命令（`npm audit` / `pip-audit` / `semgrep`），不强依赖。本设计文档不展开 11B 实现。

---

## 4. 技术设计

### 4.1 文件结构

```
smartPi/smartdev-agent/
└── smartdev/
    ├── core/
    │   └── git.py              ← 新建：GitService + GitStatus/GitDiff/GitFileChange + git-policy 读取
    ├── skills/
    │   ├── git_status/         ← 新建：git.status（R0）
    │   ├── git_diff_explain/   ← 新建：git.diff.explain（R0）
    │   ├── git_commit_plan/    ← 新建：git.commit.plan（R0）
    │   ├── git_commit_message/ ← 新建：git.commit.message（R0）
    │   ├── git_release_plan/   ← 新建：git.release.plan（R0）
    │   ├── git_merge_check/    ← 新建：git.merge.check（R0）
    │   └── git_tag_plan/       ← 新建：git.tag.plan（R0）
    ├── cli.py                  ← 修改：+git commit / git tag 执行 Command（R2，默认 dry-run）
    └── mcp/
        └── tools.py            ← 修改：+5 个只读 git 工具
```

每个 git Skill 沿用现有约定：`skills/<name>/skill.py + skill.yaml`，靠 `name` 类属性自动注册。

### 4.2 GitService（core/git.py）

底层封装，所有 git Skill / Command 共用，唯一接触 subprocess 的地方：

```python
class GitNotAvailable(Exception):
    """系统未安装 git 或当前目录不是 git 仓库。"""

@dataclass
class GitFileChange:
    path: str
    status: str          # M / A / D / R / ??（porcelain code）
    staged: bool
    added_lines: int
    deleted_lines: int

@dataclass
class GitStatus:
    branch: str
    is_dirty: bool
    staged: list[GitFileChange]
    unstaged: list[GitFileChange]
    untracked: list[str]
    recent_commits: list[str]   # git log --oneline -n

@dataclass
class GitDiff:
    files: list[GitFileChange]
    insertions: int
    deletions: int

class GitService:
    def __init__(self, project_path: Path): ...
    def is_available(self) -> bool: ...        # git 存在 + .git 目录存在
    def status(self) -> GitStatus: ...
    def diff(self, staged: bool = False) -> GitDiff: ...
    def current_branch(self) -> str: ...
    def recent_commits(self, n: int = 10) -> list[str]: ...
    def tags(self) -> list[str]: ...
    # 执行类（仅供 CLI Command 调用，不暴露给 Skill）
    def commit(self, message: str, files: list[str] | None = None) -> str: ...
    def tag(self, name: str, message: str | None = None) -> str: ...
```

约束：
- `is_available()` 为 False 时，所有调用方返回 `GIT_NOT_FOUND`，不抛未捕获异常。
- subprocess 一律用列表参数（`["git", "status", ...]`），不用 shell 字符串拼接，防注入。
- `commit()` / `tag()` 只被 CLI Command 调用，Skill 层不导入这两个方法。

### 4.3 Skill 输出模式（以 git.diff.explain 为例）

所有 git Skill 是 R0，沿用 `SkillResult`：

```python
class GitDiffExplainSkill(Skill):
    name = "git.diff.explain"
    description = "确定性解释当前 diff：文件分类 / 行数统计 / 风险信号 / 拆分建议（只读）"
    risk_level = RiskLevel.R0
    task_type = TaskType.DIAGNOSE

    def can_run(self, context) -> bool:
        return GitService(context.project_path).is_available()

    def run(self, context, inputs=None) -> SkillResult:
        svc = GitService(context.project_path)
        diff = svc.diff(staged=inputs.get("staged", False) if inputs else False)
        signals = self._compute_signals(diff, context)   # 确定性规则
        return SkillResult(
            success=True,
            summary=f"diff 解释：{diff.insertions}+ / {diff.deletions}- across {len(diff.files)} files",
            data={"summary": {...}, "signals": signals, "risk_hints": [...], "suggested_commit_split": [...]},
        )
```

`can_run()` 在无 git 时返回 False，Runtime 不执行 run()。

### 4.4 CLI 执行 Command 模式（git commit / git tag）

新增 CLI 子命令，**不是 Skill**，默认 dry-run：

**commit：**

```bash
# 默认 dry-run
smartdev git commit --message "feat(context): add git status skill"
```

```
Will commit:
  branch:  feature/git-governance
  files:
    - smartdev/skills/git_status/skill.py
    - smartdev/skills/git_status/skill.yaml
  message: feat(context): add git status skill
  policy checks:
    ✓ branch not protected
    ✓ files (2) <= max_files_per_commit (12)
    ✓ conventional commit format

No commit created. Add --apply to execute.
```

```bash
# 真正执行
smartdev git commit --message "..." --apply
```

**tag：**

```bash
smartdev git tag --version v0.4.0            # dry-run
smartdev git tag --version v0.4.0 --apply    # 执行
```

执行 Command 的门控（按 R2）：
- 默认 dry-run，必须 `--apply` 才调用 `GitService.commit()/tag()`。
- 命中 protected 分支（main/master）直接拒绝，除非 policy 显式允许。
- 超过 `max_files_per_commit` 给出警告。
- **永不执行** push / merge / rebase / reset / force-push（policy `dangerous` 全 forbid）。
- 执行后写审计到 `.smartdev/index.sqlite` runs 表（复用 code.apply 的审计模式）。

### 4.5 MCP 工具接入（mcp/tools.py）

新增 5 个只读 git 工具，沿用 Phase 10 的统一输出格式（`ok / tool / data / warnings / risk_level / next_steps`）和优雅降级（无 git 返回 `GIT_NOT_FOUND`）：

```
smartdev_git_status        → Skill.create("git.status")
smartdev_git_diff_explain  → Skill.create("git.diff.explain")
smartdev_git_commit_plan   → Skill.create("git.commit.plan")
smartdev_git_release_plan  → Skill.create("git.release.plan")
smartdev_git_merge_check   → Skill.create("git.merge.check")
```

MCP 工具总数：14（Phase 10）→ 19（Phase 11A）。

新增 error_code：

| error_code | 含义 | suggested_tool |
|-----------|------|---------------|
| `GIT_NOT_FOUND` | 未安装 git 或非 git 仓库 | — |

---

## 5. 影响范围分析

### 需要新增/修改的文件

| 文件 | 变更 | 风险 |
|------|------|------|
| `smartdev/core/git.py` | 新建（GitService + 数据模型 + policy 读取）| R1 |
| `smartdev/skills/git_status/` | 新建 | R1 |
| `smartdev/skills/git_diff_explain/` | 新建 | R1 |
| `smartdev/skills/git_commit_plan/` | 新建 | R1 |
| `smartdev/skills/git_commit_message/` | 新建 | R1 |
| `smartdev/skills/git_release_plan/` | 新建 | R1 |
| `smartdev/skills/git_merge_check/` | 新建 | R1 |
| `smartdev/skills/git_tag_plan/` | 新建 | R1 |
| `smartdev/cli.py` | +`git commit` / `git tag` 执行 Command | R2 |
| `smartdev/mcp/tools.py` | +5 个只读 git 工具 | R1 |

### 完全不修改的文件

- `context/` 全部（索引 / impact / relations 等）
- `core/` 现有文件（risk / reporter / patch / workflow / adapter）— 只新增 git.py
- `skills/` 现有 Skill（不改任何已有 Skill）
- `models.py` / `detectors/` 全部
- 现有 `tests/` 全部（只新增测试文件）

### 测试新增（预估）

| Step | 测试文件 | 覆盖内容 | 预计数量 |
|------|---------|---------|---------|
| Step 1 | `test_git_service.py` | GitService subprocess 封装 + GIT_NOT_FOUND + 数据模型 | 15–20 |
| Step 2 | `test_git_status.py` / `test_git_diff_explain.py` | 只读状态 + 确定性 diff 信号 | 18–24 |
| Step 3 | `test_git_commit_plan.py` | commit 拆分 + Conventional message | 12–16 |
| Step 4 | `test_git_release_plan.py` / `test_git_merge_check.py` | semver bump + 合并前检查 | 12–16 |
| Step 5 | `test_git_policy.py` | policy 读取 + 默认值 + 字段覆盖 | 10–14 |
| Step 6 | `test_git_commit_command.py` | dry-run / --apply / protected 分支拒绝 / 审计 | 12–18 |
| Step 7 | `test_mcp_git_tools.py` | 5 个 MCP 只读 git 工具 + GIT_NOT_FOUND | 12–16 |

测试用 git fixture：在临时目录 `git init` 构造小仓库，避免依赖真实项目历史。

---

## 6. 风险等级与回滚方案

### 按 Step 拆分

| Step | 风险 | 说明 |
|------|------|------|
| Step 0 | R0 | 设计文档 |
| Step 1 | R1 | 新增 GitService，只读 subprocess |
| Step 2 | R1 | 只读 Skill |
| Step 3 | R1 | 只读建议 Skill |
| Step 4 | R1 | 只读检查 Skill |
| Step 5 | R1 | policy 读取，不执行 |
| Step 6 | **R2** | 会写 Git 历史，必须显式 `--apply` |
| Step 7 | R1 | MCP 只读工具 |

> 注意：`git commit` / `git tag` 虽不改源码，但会改 Git 历史，按 **R2** 管控，不是 R1。

### 回滚方案

1. 任一 Step 出问题 → `git revert` 对应 commit，现有功能不受影响。
2. git Skill 完全独立，删除 `skills/git_*/` + `core/git.py` + cli/mcp 的 git 入口即可完全回滚。
3. 不修改任何现有 Skill / Context Layer / 现有 core 文件，无 regression 风险。
4. 执行 Command 默认 dry-run，即使误调用也不会写 Git 历史。

---

## 7. 实施路线（Phase 11A）

```
Step 0  设计文档 phase-11-design.md（本文档）                          ✅ 当前

Step 1  core/git.py（R1，~655 tests）
        - GitService（subprocess 封装）
        - GitStatus / GitDiff / GitFileChange 数据模型
        - is_available() + GIT_NOT_FOUND 错误处理
        - 列表参数调用，防注入

Step 2  git.status + git.diff.explain（R1，~677 tests）
        - 确定性 diff 统计（行数 / 文件分类）
        - protected branch / protected path 信号
        - dependency manifest 信号 / test / docs 信号

Step 3  git.commit.plan + git.commit.message（R1，~693 tests）
        - commit 拆分建议（按文件类别）
        - Conventional Commit message 生成（确定性模板）
        - 不执行 commit

Step 4  git.release.plan + git.merge.check（R1，~707 tests）
        - CHANGELOG / version 文件检查
        - semver bump 建议
        - 当前分支干净度 / 测试基线提示
        - graph.validate / patch_backups 信号

Step 5  git-policy.json 读取 + 默认策略（R0，Step 1 已实现，845 tests）✅
        - GitPolicy 数据类（含安全默认值）已在 core/git.py 实现
        - load_git_policy()：.smartdev/git-policy.json（优先）或 smartdev.git.json
        - 字段覆盖：只覆盖明确指定字段，缺失字段保留默认值
        - 静默降级：文件不存在或格式错误时退回默认值
        - policy 格式：JSON（零依赖，标准库 json）
        - 示例文件：.smartdev/git-policy.json（已创建）
        - 6 个 policy 测试已在 test_git_service.py 覆盖

Step 6  git commit / git tag CLI Command（R2，~735 tests）
        - 默认 dry-run，--apply 才执行
        - 禁止 main/master 直接 commit（除非 policy 允许）
        - 不做 push / merge / rebase / reset
        - 执行后写审计 runs 表

Step 7  MCP 暴露只读 Git 工具（R1，~749 tests）
        - smartdev_git_status / git_diff_explain / git_commit_plan
        - smartdev_git_release_plan / git_merge_check
        - GIT_NOT_FOUND 优雅降级
        - MCP 工具数 14 → 19
```

每步独立可测、可回滚，节奏与 Phase 9 / 10 一致。

---

## 8. Phase 11A 不做的事（硬约束）

```
❌ 不自动提交 / 自动合并 / 自动推送
❌ 不做 git push（任何形式）
❌ 不做 git merge 执行（只做 merge.check 只读检查）
❌ 不做 git rebase / reset / force-push
❌ 不把 commit / tag 做成自动注册的普通 Skill
❌ 不把 commit / tag 暴露给 MCP
❌ 不把 commit / tag 放进默认 workflow
❌ 不引 GitPython 或任何第三方 git 库
❌ 不做 LLM 风格的 diff 自然语言总结
❌ 不让 code.apply 自动触发 commit
❌ 不在 11A 实现 Guard Skills（11B 范围）
```

---

## 9. 后续路线（Phase 11A 之后）

```
Phase 11A  Git Governance v0           ← 本设计，交付记录层（L5）
    ↓
Phase 11B  Guard Skills（L5 防护）
           dev.guard / dependency.guard / security.review / change.budget / diff.explain
           确定性 checklist，不接外部扫描器
    ↓
Phase 11C  Model Collaboration Policy（可选，L7 配置层）
           或直接进入 Phase 12（Model Collaboration Layer）
    ↓
Phase 12   Model Collaboration Layer（横向 L7）
Phase 13   Call Graph（函数级引用分析）
Phase 14   FileWatcher / Incremental Sync
```

---

## 10. 验收标准（Phase 11A）

1. 现有 637 tests 全部通过，无回归。
2. `core/git.py` 不引入任何第三方依赖（仅标准库 + subprocess）。
3. 系统无 git 或非 git 仓库时，所有 git Skill / 工具返回 `GIT_NOT_FOUND`，不崩溃。
4. `git.status` 返回当前分支 / dirty files / staged / 最近提交。
5. `git.diff.explain` 返回确定性结构化信号（行数 / 分类 / risk_hints / suggested_split），无自然语言总结。
6. `git.commit.plan` 输出 commit 拆分建议 + Conventional Commit message。
7. `git.release.plan` 输出 semver bump 建议 + CHANGELOG / version 检查。
8. `git.merge.check` 输出合并前检查（分支干净度 / 测试基线 / protected path / patch backup）。
9. `git-policy.yaml` 不存在时用安全默认值；存在时只覆盖明确字段。
10. `smartdev git commit`（无 --apply）只输出计划，不创建 commit。
11. `smartdev git commit --apply` 在 protected 分支（main/master）被拒绝（除非 policy 允许）。
12. `smartdev git commit --apply` 执行成功后写审计到 runs 表。
13. MCP 暴露 5 个只读 git 工具，工具总数 19；commit / tag 不在 MCP 工具列表中。
14. CLI / MCP 现有功能（scan / plan / index / search / impact / run / 14 个 MCP 工具）不受任何影响。
