# Phase 10 — MCP Server v0 执行前设计

> 状态：设计文档（Step 0），不动代码
> 前置：Phase 9 已完成并冻结（540 tests，清洁基线）
> 目标：把 SmartDev 已有能力暴露给外部 Agent，而不是继续新增底层分析能力

---

## 1. 背景与定位

### 1.1 为什么是 MCP Server，而不是 Call Graph 或 FileWatcher

Phase 9 完成后，SmartDev 已具备 L1–L4 的完整闭环：

```
L1  诊断层     repo.scan / tech_stack / docs_status / entrypoints
L2  规划层     task.plan（三档方案）/ architecture.map / risk.check / qa.checklist
L3  语义层     code.index → SQLite + FTS5
               code.search / code.impact / project.map / graph.validate
               多语言 Provider：Python(1.0) / JS-TS(0.95) / Go(0.98)
               Phase 8：Context Layer ↔ Skill 接入（risk / architecture / plan 全部消费索引）
L4  执行层     code.patch(propose) → code.apply → code.rollback
               find-replace / 备份 / hash 校验 / 路径安全 / R3 强确认
```

三条候选路线的价值密度对比：

| 路线 | 性质 | 判断 |
|------|------|------|
| **A: MCP Server** | 能力分发 | ✅ Phase 10 推荐 |
| B: Call Graph | 能力深挖 | 暂缓，技术价值高但打开新的复杂度 |
| C: FileWatcher | 运行时体验 | 暂缓，属于长期运行基础设施 |

理由：SmartDev 现在最缺的不是更深的分析能力，而是把已有能力**分发出去**。
MCP Server 是乘数效应——现有能力 × N 个外部 Agent（Claude / Cursor / Kiro / Codex 等）。

### 1.2 Phase 10 的正确定位

```
MCP Server v0 = 现有 SmartDev 能力的安全工具出口
```

不是：

```
❌ 新一轮大平台化
❌ daemon / 后台服务
❌ 自动执行系统
❌ multi-agent 调度层
```

### 1.3 与 CLI 的关系

MCP Server 和 CLI 并存，互不替代：

- CLI：开发者直接使用，交互式确认，写盘操作（apply）
- MCP：外部 Agent 调用，只读 + propose，写盘操作在 v0 暂不暴露

---

## 2. 七个核心问题

### Q1: MCP transport 用哪种？

**答案：stdio（标准输入输出），v0 只做 stdio。**

理由：
- stdio 是 MCP 最简单的 transport，Claude Desktop / Kiro / Cursor 都原生支持
- 不需要管理端口、TLS、认证——外部 Agent 通过 JSON-RPC over stdio 调用
- 与 CLI 的运行方式一致（Python 子进程），运维复杂度最低
- 未来如需 HTTP/SSE transport，可在 v1 加，不影响 v0

**运行方式：**

```bash
# 外部 Agent 通过 MCP client 启动 SmartDev 子进程
python -m smartdev mcp --project /path/to/project
# 或
smartdev mcp --project /path/to/project
```

配置示例（Claude Desktop / Kiro mcp.json）：

```json
{
  "mcpServers": {
    "smartdev": {
      "command": "python",
      "args": ["-m", "smartdev", "mcp", "--project", "/path/to/project"],
      "disabled": false
    }
  }
}
```

### Q2: MCP Server 用哪个 Python 库？

**答案：`mcp`（Anthropic 官方 Python SDK）。**

```
pip install mcp
```

SmartDev 零外部依赖的原则只约束 Python core（pyproject.toml 的 dependencies 为空）。
MCP Server 是一个独立的可选入口，`mcp` 包作为 optional dependency 引入：

```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0"]
```

安装方式：

```bash
pip install smartdev[mcp]
```

没有安装 `mcp` 时，`smartdev mcp` 命令报明确错误：

```
错误: MCP Server 需要安装 mcp 包。
请运行: pip install smartdev[mcp]
```

**为什么不用 fastmcp？**

`fastmcp` 是高层封装，隐藏了协议细节。SmartDev 的工具权限逻辑、输出格式和错误处理需要精细控制，官方 SDK 更合适。

### Q3: project_path 策略

**问题：**

MCP Server 服务的是哪个项目？外部 Agent 调用时如何指定？

**答案：启动时绑定单项目，运行时不切换。**

```
启动时：  smartdev mcp --project /path/to/project
运行中：  所有工具调用都服务这个项目
不支持：  运行时切换项目（v0）
```

理由：
1. 和 CLI 保持一致（`smartdev index -p /path`）
2. 避免多项目混用时的权限边界问题
3. 简化 Server 状态管理

外部 Agent 如果需要服务多个项目，启动多个 MCP Server 实例即可。

**project_path 验证：**

- 启动时验证目录存在
- 不允许 path traversal
- 工具调用时不接受 project_path 参数（已绑定，不暴露给外部 Agent 篡改）

### Q4: 工具分级与权限模型

MCP v0 开放三个权限层，暂不开放写盘：

| 权限 | MCP v0 | 说明 |
|------|--------|------|
| READ | ✅ 开放 | search / impact / map / validate / risk / plan / scan |
| CACHE_WRITE | ✅ 开放（明确标注） | code_index 写 .smartdev/，不改源码 |
| PATCH_PROPOSE | ✅ 开放 | patch_propose 生成 diff，不落盘 |
| WRITE_CODE | ❌ v0 禁用 | patch_apply 暂不暴露 |
| EXEC | ❌ 永久禁用 | 不执行 shell 命令 |
| SECRET | ❌ 永久禁用 | 不读 env / keys |

### Q5: 工具列表

**第一批：只读工具（READ）**

| 工具名 | 对应 Skill/能力 | 描述 |
|--------|----------------|------|
| `smartdev_ping` | — | 健康检查 |
| `smartdev_version` | `__version__` | 版本信息 + 能力清单 |
| `smartdev_repo_scan` | `repo.scan` | 扫描技术栈、入口、文档状态 |
| `smartdev_code_search` | `code.search` | 全文搜索文件和 artifact |
| `smartdev_code_impact` | `code.impact` | 变更影响分析（import reverse lookup） |
| `smartdev_project_map` | `project.map` | 导出项目结构地图 |
| `smartdev_graph_validate` | `graph.validate` | 图谱健康校验 |
| `smartdev_risk_check` | `risk.check` | 风险等级判断（含 impact 增强） |
| `smartdev_architecture_map` | `architecture.map` | 架构依赖图（多语言） |
| `smartdev_task_plan` | `task.plan` | 三档任务方案生成 |
| `smartdev_qa_checklist` | `qa.checklist` | 验收清单生成 |

**第二批：缓存写入工具（CACHE_WRITE）**

| 工具名 | 对应能力 | 描述 |
|--------|---------|------|
| `smartdev_code_index` | `code.index` | 建立 .smartdev/index.sqlite，不改源码 |

**第三批：Patch Propose 工具（PATCH_PROPOSE）**

| 工具名 | 对应能力 | 描述 |
|--------|---------|------|
| `smartdev_patch_propose` | `code.patch` | 生成 find-replace diff + patch_id，不落盘 |

**第四批：暂缓（v0 不暴露）**

| 工具名 | 理由 |
|--------|------|
| `smartdev_patch_apply` | 写盘操作，MCP 里确认协议需重新设计 |
| `smartdev_patch_rollback` | 依赖 apply，同上 |

**总计 MCP v0：14 个工具**

### Q6: 统一输出格式

每个工具返回统一的 JSON 结构：

**成功：**

```json
{
  "ok": true,
  "tool": "smartdev_code_impact",
  "project_path": "...",
  "data": {},
  "warnings": [],
  "risk_level": "R0",
  "next_steps": []
}
```

**失败：**

```json
{
  "ok": false,
  "tool": "smartdev_code_impact",
  "error_code": "INDEX_NOT_FOUND",
  "message": "No .smartdev/index.sqlite found. Run smartdev_code_index first.",
  "suggested_tool": "smartdev_code_index"
}
```

常见 error_code：

| error_code | 含义 | suggested_tool |
|-----------|------|---------------|
| `INDEX_NOT_FOUND` | 未建立索引 | `smartdev_code_index` |
| `PROJECT_NOT_FOUND` | 项目路径不存在 | — |
| `SKILL_CANNOT_RUN` | can_run() 返回 False | — |
| `INVALID_ARGUMENT` | 参数类型或格式错误 | — |
| `MCP_PACKAGE_MISSING` | mcp 包未安装 | — |
| `INTERNAL_ERROR` | 未预期内部错误 | — |

外部 Agent 消费这个格式可以做到：
1. 读 `ok` 判断是否成功
2. 读 `error_code` 决定下一步（是否重试、是否先建索引）
3. 读 `suggested_tool` 自动规划后续调用
4. 读 `next_steps` 获取建议

### Q7: patch_apply 如何处理

**答案：MCP v0 不暴露，文档明确说明原因。**

Phase 9 的 apply 依赖：
- 显式 `--apply` 开关（CLI 参数）
- R3 强确认（`confirm_risk_r3="APPLY R3"` 字符串）
- 备份到 `.smartdev/patch_backups/`
- hash 校验（防 TOCTOU）

在 MCP 协议里，这些确认机制需要**重新设计**：
- MCP 没有"交互式确认"概念，工具调用是一次性的
- 外部 Agent 自动调用 apply 没有人工审查节点
- 安全边界比 CLI 更难控制

**Phase 10 的正确答案是先不暴露 apply，而不是草率地搬过来。**

如果未来要暴露 apply，正确的方案应该是：
- Server 启动参数 `--allow-write` 明确开启写盘能力
- 工具参数里要求传入 `confirm_token`（防止 Agent 自动生成）
- apply 结果必须同步写审计日志

---

## 3. 技术设计

### 3.1 文件结构

```
smartPi/smartdev-agent/
└── smartdev/
    └── mcp/
        ├── __init__.py         ← 包入口，暴露 create_server()
        ├── server.py           ← MCP Server 主体（工具注册 + 启动）
        ├── tools.py            ← 14 个工具的实现（调用已有 Skill / Context）
        ├── formatter.py        ← 统一输出格式（ok/error/next_steps）
        └── README.md           ← 安装说明 + 工具清单
```

新增 CLI 入口（`cli.py` 新增 `mcp` 子命令）：

```python
# cli.py 新增
mcp_parser = subparsers.add_parser("mcp", help="启动 MCP Server（供外部 Agent 调用）")
mcp_parser.add_argument("--project", "-p", required=True, help="项目根目录路径")
mcp_parser.add_argument("--allow-write", action="store_true", help="允许写盘工具（v0 暂不开放）")
mcp_parser.set_defaults(func=_cmd_mcp)
```

新增 `pyproject.toml` optional dependency：

```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0"]
```

### 3.2 Server 初始化流程

```python
# server.py 核心结构

from mcp.server import Server
from mcp.server.stdio import stdio_server

def create_server(project_path: Path) -> Server:
    server = Server("smartdev")

    # 注册所有工具（14 个）
    _register_readonly_tools(server, project_path)
    _register_cache_write_tools(server, project_path)
    _register_patch_propose_tools(server, project_path)

    return server

async def run_mcp_server(project_path: Path) -> None:
    server = create_server(project_path)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, ...)
```

### 3.3 工具实现模式

每个工具的实现遵循统一模式：

```python
# tools.py 工具实现模式

@server.call_tool()
async def smartdev_code_search(arguments: dict) -> list[TextContent]:
    query = arguments.get("query", "")
    limit = arguments.get("limit", 20)

    try:
        # 调用已有 Skill 或 Context Layer
        index = ProjectIndex(project_path)
        results = index.search(query, limit=limit)
        index.close()

        return [TextContent(
            type="text",
            text=json.dumps({
                "ok": True,
                "tool": "smartdev_code_search",
                "project_path": str(project_path),
                "data": results,
                "warnings": [],
                "risk_level": "R0",
                "next_steps": [],
            }, ensure_ascii=False, indent=2)
        )]

    except FileNotFoundError:
        return [TextContent(
            type="text",
            text=json.dumps({
                "ok": False,
                "tool": "smartdev_code_search",
                "error_code": "INDEX_NOT_FOUND",
                "message": "No .smartdev/index.sqlite found. Run smartdev_code_index first.",
                "suggested_tool": "smartdev_code_index",
            }, ensure_ascii=False, indent=2)
        )]
```

工具始终返回 `list[TextContent]`，不抛异常到 MCP 层。

### 3.4 工具 Schema 示例

每个工具的 inputSchema 精确定义，让外部 Agent 知道如何调用：

**`smartdev_code_search`：**

```json
{
  "name": "smartdev_code_search",
  "description": "Search files and artifacts in the indexed project. Requires running smartdev_code_index first.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "Search term (file name, function name, artifact type, etc.)"
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of results (default: 20)",
        "default": 20
      }
    },
    "required": ["query"]
  }
}
```

**`smartdev_code_impact`：**

```json
{
  "name": "smartdev_code_impact",
  "description": "Analyze the impact of changing a file, module, or artifact. Returns affected files, risk level, and validation checklist.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "target": {
        "type": "string",
        "description": "Target to analyze (file path, module name, or artifact name)"
      },
      "max_depth": {
        "type": "integer",
        "description": "Maximum depth for impact traversal (default: 3)",
        "default": 3
      }
    },
    "required": ["target"]
  }
}
```

**`smartdev_patch_propose`：**

```json
{
  "name": "smartdev_patch_propose",
  "description": "Generate a find-replace patch proposal. Returns unified diff, affected files, risk level, and patch_id. Does NOT modify any files.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "find": {
        "type": "string",
        "description": "Text or pattern to find"
      },
      "replace": {
        "type": "string",
        "description": "Replacement text"
      },
      "glob": {
        "type": "string",
        "description": "File glob pattern to scope the search (default: **/*)",
        "default": "**/*"
      },
      "regex": {
        "type": "boolean",
        "description": "Treat find as a regex pattern (default: false)",
        "default": false
      }
    },
    "required": ["find", "replace"]
  }
}
```

### 3.5 Skill 调用模式

工具实现直接复用已有 Skill 和 Context Layer，不新增业务逻辑：

```
smartdev_risk_check    → Skill.create("risk.check").run(context, inputs)
smartdev_architecture_map → Skill.create("architecture.map").run(context, inputs)
smartdev_task_plan     → Skill.create("task.plan").run(context, inputs)
smartdev_code_search   → ProjectIndex(project_path).search(query)
smartdev_code_impact   → ImpactAnalyzer(store).analyze(target)
smartdev_project_map   → ProjectMap(project_path).export()
smartdev_graph_validate → GraphValidator(project_path).validate()
smartdev_patch_propose → Skill.create("code.patch").run(context, inputs)
smartdev_code_index    → ProjectIndex(project_path).index()
```

MCP 层只做三件事：参数解析、Skill 调用、格式化输出。不包含任何新的业务逻辑。

---

## 4. 影响范围分析

### 需要新增/修改的文件

| 文件 | 变更 | 风险 |
|------|------|------|
| `smartdev/mcp/__init__.py` | 新建 | R0 |
| `smartdev/mcp/server.py` | 新建 | R1 |
| `smartdev/mcp/tools.py` | 新建 | R1 |
| `smartdev/mcp/formatter.py` | 新建 | R0 |
| `smartdev/mcp/README.md` | 新建 | R0 |
| `smartdev/cli.py` | +mcp 子命令（~20 行） | R1 |
| `pyproject.toml` | +mcp optional dependency | R0 |

### 完全不修改的文件

- `context/` 全部（index_store / project_index / impact_analyzer / structure_extractor 等）
- `skills/` 全部（所有 Skill 实现）
- `core/` 全部（risk / reporter / patch / workflow）
- `models.py`
- `detectors/` 全部
- 现有 `tests/` 全部（新增测试文件，不修改现有测试）

### 测试新增

| Step | 测试文件 | 覆盖内容 | 预计数量 |
|------|---------|---------|---------|
| Step 1 | `test_mcp_server.py` | Server 骨架 + ping/version/list_capabilities | 8–12 |
| Step 2 | `test_mcp_readonly_tools.py` | 只读工具 + INDEX_NOT_FOUND 错误路径 | 15–20 |
| Step 3 | `test_mcp_skill_tools.py` | Skill 工具（risk/arch/plan） + Context 增强路径 | 12–18 |
| Step 4 | `test_mcp_patch_propose.py` | patch_propose 工具 + diff 输出 | 8–12 |
| Step 5 | `test_mcp_integration.py` | 真实 Agent 调用验证（可选 skipif） | 5–8 |

---

## 5. 风险等级与回滚方案

### 按 Step 拆分

| Step | 风险 | 理由 |
|------|------|------|
| Step 0 | R0 | 只写设计文档，不动代码 |
| Step 1 | R1 | 新建 mcp/ 模块骨架，不改任何现有逻辑 |
| Step 2 | R1 | 只读工具，调用已有 Context Layer，无写盘 |
| Step 3 | R1 | Skill 工具，调用已有 Skill，无写盘 |
| Step 4 | R2 | patch_propose 涉及 core/patch.py，但仍不落盘 |
| Step 5 | R1 | 真实验证，只读，不修改生产代码 |

### 回滚方案

1. 任一 Step 出问题 → `git revert` 对应 commit，CLI 和所有现有功能不受影响
2. mcp 模块完全独立，删除 `smartdev/mcp/` + cli.py 的 mcp 子命令即可完全回滚
3. `mcp` 包是 optional dependency，不安装时不影响 CLI 工作
4. 不修改任何现有 Skill / Context Layer，无需担心 regression

---

## 6. 实施路线

```
Phase 10 Step 0 ✅ 当前 — 设计确认（本文档）

Phase 10 Step 1：MCP Server 骨架（R1，~555 tests）
- smartdev/mcp/ 目录骨架
- mcp optional dependency
- cli.py +mcp 子命令
- 只暴露：smartdev_ping / smartdev_version / smartdev_list_capabilities
- 目标：跑通 MCP 基础协议，不接任何业务

Phase 10 Step 2：只读 Context 工具（R1，~575 tests）
- smartdev_code_search
- smartdev_code_impact
- smartdev_project_map
- smartdev_graph_validate
- INDEX_NOT_FOUND 错误处理
- 不写任何文件

Phase 10 Step 3：Skill 工具接入（R1，~593 tests）
- smartdev_repo_scan
- smartdev_risk_check（含 Context Layer 增强路径）
- smartdev_architecture_map（含 index 数据源路径）
- smartdev_task_plan（含 impact 标注路径）
- smartdev_qa_checklist
- 体现 Phase 8 价值：Skill 已能消费 Context Layer

Phase 10 Step 4：Patch Propose 工具（R2，~605 tests）
- smartdev_code_index（CACHE_WRITE，明确标注只写 .smartdev/）
- smartdev_patch_propose（PATCH_PROPOSE，不落盘）
  - 新增 `max_files` 参数（change.budget 约束，默认 10，超过时返回警告）
  - 新增 `diff_explain` 字段：每个文件改了什么 / 为什么改 / 潜在风险（确定性摘要，非 LLM）
- patch_id 持久化到 .smartdev/patches/（与 Phase 9 一致）
- 明确输出：patch_id / diff / diff_explain / affected_files / risk_level / rollback_hint

Phase 10 Step 5：真实 Agent 验证（R1，~613 tests）
- 用 Kiro / Claude Desktop 配置 MCP Server
- 对已索引项目执行只读验证：查项目结构 / 搜索符号 / 分析影响范围
- 验证工具描述让外部 Agent 能理解调用时机
- 验证产生的 .smartdev/patches/ 已清理
```

---

## 7. Phase 10 不做的事（硬约束）

写死在设计里，不被需求蔓延侵蚀：

```
❌ 不做 daemon（后台长期运行进程）
❌ 不做 file watcher（文件变化自动重索引）
❌ 不做 call graph（函数调用图）
❌ 不做 patch_apply MCP 工具（写盘操作 v0 禁用）
❌ 不做 Git 执行命令（git.commit / git.merge / git.push / git.tag / git.rebase / git.reset）
❌ 不做 multi-agent 调度层
❌ 不做 Dashboard / Web UI
❌ 不做 LLM 代码生成
❌ 不让 MCP 自动修改源码
❌ 不做 HTTP/SSE transport（stdio 已够用）
❌ 不做多项目切换（运行时固定 project_path）
```

Git 相关的只读查询（git.status / git.diff.explain / git.commit.plan）属于 Phase 11 范围，不进入 Phase 10。
MCP v0 不暴露任何 Git 操作工具，保持 READ / CACHE_WRITE / PATCH_PROPOSE 三个权限层的边界清晰。

---

## 8. 后续路线（Phase 10 之后）

整体路线收束为五个主阶段，按价值类型排序：

| 阶段 | 价值类型 | 核心目标 |
|------|---------|---------|
| Phase 10 | 能力分发 | 让外部 Agent 立刻安全使用 SmartDev（模式 A） |
| Phase 11 | 人类控制权 | 补齐提交 / 审查 / 安全 / 防依赖失控的闭环 |
| Phase 12 | 模型协作控制 | 模型无关的任务路由、输出契约、风险上限（模式 B 基础） |
| Phase 13 | 分析深度 | 把 impact 从模块级推进到函数级 |
| Phase 14 | 运行体验 | 让索引持续新鲜，服务长期开发流 |

```
Phase 10：MCP Server v0              ← 当前，能力分发（模式 A）
    ↓
Phase 11：Human-Controlled AI Coding Layer
    ├── 11A: Git Governance v0
    │         git.status / git.diff.explain / git.commit.plan / git.release.plan / git.merge.check
    │         git.commit / git.tag（显式执行，需 --apply）
    │         永久禁止：git.push / git.rebase / git.reset / 自动 merge / 自动发布
    └── 11B: Guard Skills
              change.budget → dev.guard → dependency.guard → security.review → diff.explain
    ↓
Phase 12：Model Collaboration Layer  ← 横向协作控制层
    ├── 12A: Policy（配置层，不调用真实 API）
    │         model registry / capability profile / task router
    │         output contract / risk policy（.smartdev/model-policy.yaml）
    └── 12B: Router（真实路由，依赖 Phase 10 MCP 跑稳）
              select_model / validate_output_contract / handoff_to_patch / second_review
    不做：自动多模型流水线 / 模型自动 apply / 模型自动 commit / agent swarm
    ↓
Phase 13：Call Graph                 ← 能力深挖，函数级引用分析
    Python(ast.Call) + JS-TS(CallExpression) + Go(Tree-sitter)
    relations 表新增 calls 类型 / ImpactAnalyzer function-level reverse lookup
    ↓
Phase 14：FileWatcher / Incremental Sync  ← 运行时体验
    增量索引 API + 文件变更检测 + debounce + watcher 状态报告
```

不建议在 Phase 14 完成前新增横向 Phase（Dashboard / Multi-Agent 全自动 / LLM 生成 / Cloud Sync）。

---

## 9. 验收标准

1. 现有 540 tests 全部通过，无回归
2. `pip install smartdev[mcp]` 成功安装 mcp 包
3. `smartdev mcp --project /path` 启动后，MCP client 能建立连接
4. `smartdev_ping` 返回 `{"ok": true, "pong": true}`
5. `smartdev_version` 返回版本号 + 14 个工具的能力清单
6. `smartdev_code_search` 在有索引时返回匹配结果，无索引时返回 `INDEX_NOT_FOUND`
7. `smartdev_code_impact` 返回影响范围 + risk_level + validation
8. `smartdev_risk_check` 有索引时用 impact 增强，无索引时退回关键词（优雅降级）
9. `smartdev_patch_propose` 返回 diff + patch_id，不写源码文件
10. `smartdev_code_index` 只写 `.smartdev/`，不改任何源码文件
11. 所有工具在 project_path 不存在时返回 `PROJECT_NOT_FOUND`，不抛异常
12. mcp 包未安装时，`smartdev mcp` 输出明确安装提示，不崩溃
13. 真实 Agent（Kiro / Claude Desktop）能配置并调用 MCP Server 完成只读验证
14. CLI（scan / plan / index / search / impact / run）不受任何影响，全部保持原有行为

