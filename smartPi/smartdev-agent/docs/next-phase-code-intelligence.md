# SmartDev Agent 下一阶段参考文档：Code Intelligence

> **基于 CodeGraph、Understand-Anything 及同类项目的深度分析，规划 SmartDev 的语义项目上下文层（Semantic Project Context Layer）**

**状态：已完成技术调研，进入 MVP 实现**
**下一步：实现 repo.scan + index.sqlite + SmartFav artifact extractor**

---

## 概述

### 背景

SmartDev Agent 已完成 Phase 1-5，拥有 8 个 Skill、27 个 Python 模块、165 个测试。当前状态：

- ✅ 项目诊断（repo.scan）
- ✅ 架构分析（architecture.map）
- ✅ 风险检查（risk.check）
- ✅ 任务规划（task.plan）
- ✅ 文档生成（doc.generate）
- ✅ 代码补丁（code.patch，占位符）
- ⚠️ **缺少：代码库理解层 / Semantic Project Context Layer**

核心差距：SmartDev 目前是"没有眼睛的 Agent"——靠 grep + read 临时探索代码库，没有持久化的代码理解。

### 本次分析目标

分析多个高价值开源仓库和论文，为 SmartDev 规划下一阶段能力：

| 项目 | 类型 | 定位 | 对 SmartDev 的价值 |
|------|------|------|-------------------|
| [CodeGraph](https://github.com/colbymchenry/codegraph) | 开源仓库 | 给编码 Agent 提供本地语义代码智能 | ⭐⭐⭐⭐⭐ 极高 |
| [Understand-Anything](https://github.com/Lum1104/Understand-Anything) | 开源仓库 | 把代码库变成可交互的知识图谱 | ⭐⭐⭐⭐ 高 |
| [Codebase-Memory](https://arxiv.org/abs/2603.27277) | 论文 | 基于 Tree-sitter + MCP 的持久代码知识图谱 | ⭐⭐⭐ 中高 |
| [CodexGraph](https://arxiv.org/abs/2408.03910) | 论文 | 代码仓库 → 图数据库接口，LLM 通过图查询理解仓库 | ⭐⭐⭐ 中高 |
| [RANGER](https://arxiv.org/abs/2509.25257) | 论文 | 仓库级图增强检索，实体查询 + 自然语言查询双通道 | ⭐⭐⭐ 中高 |
| [Code2MCP](https://github.com/DEFENSE-SEU/Code2MCP) | 开源仓库 | GitHub 仓库 → MCP 服务，7 节点 workflow | ⭐⭐ 中 |

### 一句话结论

> **CodeGraph 是"Agent 的眼睛"，Understand-Anything 是"项目的地图"。SmartDev 下一步应该先给自己装上眼睛（Code Intelligence），再画出地图（Project Knowledge Graph）。**

### SmartDev 后续主线

```txt
项目扫描
  ↓
代码语义索引
  ↓
符号 / 文件 / 路由 / 数据模型 / 文档关系图谱
  ↓
影响范围分析
  ↓
任务拆解
  ↓
安全执行 / Patch / 验证
```

---

# 第一部分：同类项目分析

## 一、CodeGraph 深度分析

### 1.1 核心定位

CodeGraph 给 Claude Code、Cursor、Codex、OpenCode、Hermes Agent、Gemini 等编码 Agent 提供本地语义代码智能。核心目标是 **减少 Agent 通过 grep、glob、read 反复探索代码库的成本**。

- **100% local**，不调 API，不发数据
- **MCP 协议**，标准化接口，任何 Agent 都能用
- **20+ 语言支持**：TypeScript、JavaScript、Python、Go、Rust、Java、C#、PHP、Ruby、C/C++、Swift、Kotlin、Dart、Svelte、Vue 等

### 1.2 基准测试结果

在 7 个真实开源代码库上的测试结果（Opus 4.8，median of 4 runs）：

| 指标 | 平均值 |
|------|--------|
| 成本节省 | 16% |
| Token 减少 | 47% |
| 时间节省 | 22% |
| 工具调用减少 | 58% |

**关键发现：CodeGraph 的 `codegraph_explore` 一次调用就返回调用者、被调用者、源码片段、关系图、影响半径。不再需要 grep → read → grep → read 的循环。**

### 1.3 源码模块架构

CodeGraph 的 `src/` 目录结构清晰：

```txt
src/
├── bin              # CLI 入口
├── context          # 给 Agent 构建上下文
├── db               # SQLite schema / query
├── extraction       # 文件扫描、Tree-sitter 解析、语言抽取
├── graph            # 图查询、图遍历
├── installer        # 安装到 Claude/Codex/Cursor/Hermes 等
├── mcp              # MCP Server
├── resolution       # 符号引用解析
├── search           # 搜索与查询解析
├── sync             # 文件变更同步 / watcher
└── ui               # CLI/TUI 相关展示
```

### 1.4 核心入口：CodeGraph 类

`src/index.ts` 里的 `CodeGraph` 类是总门面，组合了：

```txt
DatabaseConnection
QueryBuilder
ExtractionOrchestrator
ReferenceResolver
GraphQueryManager
GraphTraverser
ContextBuilder
FileWatcher
Mutex / FileLock
```

**对 SmartDev 的借鉴：SmartDev 也需要一个 `ProjectIndex` / `ProjectContext` 门面对象，代表"当前项目的可查询语义上下文"。**

建议 SmartDev 做成：

```txt
SmartDevProject
├── repoScanner
├── indexStore
├── symbolIndex
├── relationIndex
├── adapter
├── impactAnalyzer
└── contextBuilder
```

### 1.5 SQLite Schema（精华所在）

CodeGraph 的核心是 SQLite 知识图谱：

```sql
-- 符号表：存储函数、类、变量等代码符号
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,          -- file/class/function/method/...
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    language TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    docstring TEXT,
    signature TEXT,
    visibility TEXT,
    is_exported INTEGER DEFAULT 0,
    is_async INTEGER DEFAULT 0,
    is_static INTEGER DEFAULT 0,
    is_abstract INTEGER DEFAULT 0,
    decorators TEXT,             -- JSON array
    type_parameters TEXT,        -- JSON array
    updated_at INTEGER NOT NULL
);

-- 关系表：存储符号之间的关系
CREATE TABLE edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    kind TEXT NOT NULL,          -- contains/calls/imports/extends/...
    metadata TEXT,               -- JSON object
    line INTEGER,
    col INTEGER,
    provenance TEXT,             -- tree-sitter/scip/heuristic
    FOREIGN KEY (source) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target) REFERENCES nodes(id) ON DELETE CASCADE
);

-- 文件表：追踪源文件
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,  -- 变更检测
    language TEXT NOT NULL,
    size INTEGER NOT NULL,
    modified_at INTEGER NOT NULL,
    indexed_at INTEGER NOT NULL,
    node_count INTEGER DEFAULT 0,
    errors TEXT                  -- JSON array
);

-- 待解析引用表
CREATE TABLE unresolved_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_node_id TEXT NOT NULL,
    reference_name TEXT NOT NULL,
    reference_kind TEXT NOT NULL,
    line INTEGER NOT NULL,
    col INTEGER NOT NULL,
    candidates TEXT,             -- JSON array
    FOREIGN KEY (from_node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- FTS5 全文搜索索引
CREATE VIRTUAL TABLE nodes_fts USING fts5(
    id, name, qualified_name, docstring, signature,
    content='nodes', content_rowid='rowid'
);

-- FTS 同步触发器
CREATE TRIGGER nodes_ai AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, id, name, qualified_name, docstring, signature)
    VALUES (NEW.rowid, NEW.id, NEW.name, NEW.qualified_name, NEW.docstring, NEW.signature);
END;

-- 项目元数据表
CREATE TABLE project_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at INTEGER NOT NULL
);
```

### 1.6 类型系统

CodeGraph 的 `types.ts` 定义了节点和边类型：

**节点类型（21 种）：**

```typescript
const NODE_KINDS = [
  'file', 'module', 'class', 'struct', 'interface', 'trait', 'protocol',
  'function', 'method', 'property', 'field', 'variable', 'constant',
  'enum', 'enum_member', 'type_alias', 'namespace', 'parameter',
  'import', 'export', 'route', 'component'
];
```

**边类型（12 种）：**

```typescript
type EdgeKind =
  | 'contains'        // 父包含子
  | 'calls'           // 函数调用
  | 'imports'         // 文件导入
  | 'exports'         // 文件导出
  | 'extends'         // 类继承
  | 'implements'      // 接口实现
  | 'references'      // 通用引用
  | 'type_of'         // 类型标注
  | 'returns'         // 返回类型
  | 'instantiates'    // 实例化
  | 'overrides'       // 方法重写
  | 'decorates';      // 装饰器
```

### 1.7 核心能力

| 能力 | 实现方式 | 关键函数 | 对 SmartDev 的启发 |
|------|---------|---------|-------------------|
| **Impact Analysis** | BFS 遍历 incoming edges，排除 `contains` 防止爆炸 | `getImpactRadius()` | `risk.check` 可以接入 |
| **Call Graph** | 递归遍历 calls/imports edges | `getCallers()` / `getCallees()` | `architecture.map` 可以接入 |
| **Dead Code Detection** | 无 incoming references 的非导出符号 | `findDeadCode()` | `token.audit` 可以接入 |
| **Circular Dependencies** | DFS 检测环 | `findCircularDependencies()` | `risk.check` 可以接入 |
| **Type Hierarchy** | extends/implements 遍历 | `getTypeHierarchy()` | `architecture.map` 可以接入 |
| **FTS5 Search** | name + docstring + signature 全文搜索 | `nodes_fts` | `code.search` 可以接入 |
| **Auto-Sync** | FSEvents/inotify 文件监听 + debounce | `watcher.ts` | SmartDev 也可以用 |
| **Context Building** | 搜索 + 遍历 + 提取代码块 | `buildContext()` | 给 LLM 提供结构化上下文 |

### 1.8 Extraction：文件扫描和索引策略

CodeGraph 的 `ExtractionOrchestrator` 做了很实用的事：

1. 对文件内容做 SHA256 hash，用于变更检测
2. 默认跳过超过 1MB 的文件，避免生成文件、bundle、vendored blob 撑爆解析器
3. 非常详细的默认忽略目录：`node_modules`、`.next`、`dist`、`build`、`coverage`、`.venv`、`__pycache__`、`target`、`vendor` 等
4. 优先用 `git ls-files` 获取 tracked + untracked 但未 ignore 的文件
5. 对 Tree-sitter 解析 worker 设置超时和 worker recycle

**对 SmartDev 的启发：`repo.scan` 不能只是 `os.walk`，必须有 git-aware scan、ignore 策略、文件大小限制、hash 增量检测、解析失败记录。**

### 1.9 MCP 工具集

| 工具 | 用途 |
|------|------|
| `codegraph_explore` | **主力工具**。回答几乎所有问题：流程、结构、关系 |
| `codegraph_search` | 按名称搜索符号 |
| `codegraph_callers` | 查找调用者 |
| `codegraph_callees` | 查找被调用者 |
| `codegraph_impact` | 分析变更影响半径 |
| `codegraph_node` | 获取单个符号的详情和源码 |
| `codegraph_files` | 获取文件结构 |
| `codegraph_status` | 检查索引健康状态 |

### 1.10 Tool 设计：上下文预算和安全边界

CodeGraph 的 `tools.ts` 里有很多 Agent 工程细节：

- `MAX_OUTPUT_LENGTH = 15000`，限制输出，防止上下文膨胀
- `MAX_INPUT_LENGTH = 10000`，限制自由字符串输入
- `MAX_PATH_LENGTH = 4096`，限制路径输入长度
- 根据项目文件数计算调用预算
- 对容器节点返回结构轮廓而不是完整 body

**SmartDev 的 Skill 输出也要有预算：**

```yaml
output_budget:
  max_chars: 12000
  max_files: 8
  include_code: false
  include_relationships: true
  include_validation: true
```

### 1.11 设计亮点总结

1. **100% 本地** — 不调 API，不发数据，隐私安全
2. **MCP 协议** — 标准化接口，任何 Agent 都能用
3. **Provenance 标记** — 每条边标记 `tree-sitter/scip/heuristic`，知道数据来源
4. **Batch-fetch 优化** — 避免 N+1 查询
5. **Staleness Banner** — 编辑后未同步时提醒 Agent 直接读文件
6. **`buildContext()` API** — 给定任务描述，自动搜索 + 遍历 + 提取代码块
7. **Framework-aware Routes** — 识别 14 种 Web 框架的路由
8. **Mixed iOS/React Native** — 跨语言桥接

---

## 二、Understand-Anything 深度分析

### 2.1 核心定位

Understand-Anything 是一个 **Claude Code Plugin**，通过 multi-agent pipeline 分析项目，构建知识图谱，生成交互式 Dashboard。

- **7 阶段 pipeline**：SCAN → BATCH → ANALYZE → ASSEMBLE → ARCHITECTURE → TOUR → REVIEW → SAVE
- **确定性 + LLM 混合**：tree-sitter 做结构解析，LLM 做语义总结
- **增量更新**：fingerprint 变更检测，只重分析变化文件
- **10 种语言支持**：TS/JS/Python/Go/Rust/Java/Ruby/PHP/C/C++

### 2.2 源码模块架构

Understand-Anything 是 pnpm monorepo：

```txt
understand-anything-plugin/
├── agents/                    # Agent 定义
│   ├── project-scanner.md
│   ├── file-analyzer.md
│   ├── architecture-analyzer.md
│   ├── tour-builder.md
│   ├── graph-reviewer.md
│   ├── domain-analyzer.md
│   └── article-analyzer.md
├── skills/                    # Skill 定义
│   ├── understand/           # 主 Skill
│   ├── understand-dashboard/
│   ├── understand-chat/
│   ├── understand-diff/
│   ├── understand-explain/
│   ├── understand-onboard/
│   ├── understand-domain/
│   └── understand-knowledge/
├── packages/
│   ├── core/                 # 核心库
│   │   ├── schema.ts         # 图谱 schema + 校验
│   │   ├── types.ts          # 类型定义
│   │   ├── search.ts         # 搜索引擎
│   │   ├── embedding-search.ts
│   │   ├── fingerprint.ts    # 变更检测
│   │   ├── staleness.ts
│   │   └── change-classifier.ts
│   └── dashboard/            # 可视化 Dashboard
└── homepage/                  # 项目主页
```

核心包 `@understand-anything/core` 暴露了 `search`、`types`、`schema`、`languages` 等模块，依赖 `tree-sitter-*`、`web-tree-sitter`、`fuse.js`、`yaml`、`zod`。

### 2.3 知识图谱 Schema

#### 21 种节点类型

```typescript
type NodeType =
  // 代码类（5种）
  | "file" | "function" | "class" | "module" | "concept"
  // 非代码类（8种）
  | "config" | "document" | "service" | "table" | "endpoint"
  | "pipeline" | "schema" | "resource"
  // 业务域类（3种）
  | "domain" | "flow" | "step"
  // 知识类（5种）
  | "article" | "entity" | "topic" | "claim" | "source";
```

#### 35 种边类型（8 大类）

```typescript
type EdgeType =
  | "imports" | "exports" | "contains" | "inherits" | "implements"  // 结构
  | "calls" | "subscribes" | "publishes" | "middleware"             // 行为
  | "reads_from" | "writes_to" | "transforms" | "validates"        // 数据流
  | "depends_on" | "tested_by" | "configures"                      // 依赖
  | "related" | "similar_to"                                        // 语义
  | "deploys" | "serves" | "provisions" | "triggers"               // 基础设施
  | "migrates" | "documents" | "routes" | "defines_schema"         // Schema
  | "contains_flow" | "flow_step" | "cross_domain"                 // 业务域
  | "cites" | "contradicts" | "builds_on" | "exemplifies"          // 知识
  | "categorized_under" | "authored_by";
```

#### 完整知识图谱结构

```typescript
interface KnowledgeGraph {
  version: string;
  kind?: "codebase" | "knowledge";
  project: ProjectMeta;
  nodes: GraphNode[];
  edges: GraphEdge[];
  layers: Layer[];
  tour: TourStep[];
}

interface GraphNode {
  id: string;
  type: NodeType;
  name: string;
  filePath?: string;
  lineRange?: [number, number];
  summary: string;
  tags: string[];
  complexity: "simple" | "moderate" | "complex";
  languageNotes?: string;
  domainMeta?: DomainMeta;
  knowledgeMeta?: KnowledgeMeta;
}

interface GraphEdge {
  source: string;
  target: string;
  type: EdgeType;
  direction: "forward" | "backward" | "bidirectional";
  description?: string;
  weight: number; // 0-1
}
```

### 2.4 7 阶段 Pipeline

```
Phase 0: Pre-flight
  ├── 确定全量/增量分析
  ├── 处理 git worktree
  └── 语言配置

Phase 1: SCAN (project-scanner)
  ├── Step A: 读 README + manifest（LLM）
  ├── Step B: scan-project.mjs（确定性）
  └── Step C: extract-import-map.mjs（确定性）

Phase 1.5: BATCH
  └── compute-batches.mjs（语义分批）

Phase 2: ANALYZE (file-analyzer × 5 并发)
  ├── Step 1: extract-structure.mjs（确定性）
  ├── Step 2: 语义分析（LLM）
  └── 输出: batch-*.json

Phase 3: ASSEMBLE REVIEW
  └── merge-batch-graphs.py（合并 + 去重 + 修复）

Phase 4: ARCHITECTURE (architecture-analyzer)
  └── 识别架构层 + 语言上下文

Phase 5: TOUR (tour-builder)
  └── 生成导览

Phase 6: REVIEW
  └── 确定性验证 或 LLM 图审查

Phase 7: SAVE
  ├── 写入 knowledge-graph.json
  ├── 生成 fingerprint 基线
  └── 写入 meta.json
```

### 2.5 Multi-Agent Pipeline

| Agent | 角色 | 运行方式 |
|-------|------|---------|
| `project-scanner` | 发现文件、检测语言和框架 | 单次 |
| `file-analyzer` | 提取函数、类、导入；生成节点和边 | **5 并发** |
| `architecture-analyzer` | 识别架构层 | 单次 |
| `tour-builder` | 生成导览 | 单次 |
| `graph-reviewer` | 验证图完整性（确定性或 LLM） | 单次 |
| `domain-analyzer` | 提取业务域、流程、步骤 | 可选 |
| `article-analyzer` | 提取实体、主张、隐式关系 | 可选 |

### 2.6 Schema 校正能力（最值得学）

Understand-Anything 的 `schema.ts` 里有实用的 alias / sanitize / autofix 机制：

**NODE_TYPE_ALIASES：**

```typescript
const NODE_TYPE_ALIASES = {
  func: "function",
  fn: "function",
  method: "function",
  interface: "class",
  struct: "class",
  mod: "module",
  container: "service",
  deployment: "service",
  doc: "document",
  readme: "document",
  route: "endpoint",
  api: "endpoint",
  migration: "table",
  database: "table",
  // ...更多别名
};
```

**EDGE_TYPE_ALIASES：**

```typescript
const EDGE_TYPE_ALIASES = {
  extends: "inherits",
  invokes: "calls",
  uses: "depends_on",
  requires: "depends_on",
  relates_to: "related",
  describes: "documents",
  // ...更多别名
};
```

**COMPLEXITY_ALIASES：**

```typescript
const COMPLEXITY_ALIASES = {
  low: "simple",
  easy: "simple",
  medium: "moderate",
  high: "complex",
  hard: "complex",
};
```

**sanitizeGraph：** 把 null 的 `tour/layers` 变成空数组，enum-like 字符串转小写，删除 optional field 的 null。

**autoFixGraph：** 修补缺失 type、complexity、tags、summary 等字段，clamp 权重到 [0, 1]。

**对 SmartDev 的启发：SmartDev 后续如果让 LLM 参与生成图谱、任务、验收清单，一定会出现字段缺失、类型别名、大小写不一致、边方向写反、ID 格式混乱。所以 SmartDev 需要自己的 `GraphNormalizer`、`TaskNormalizer`、`SkillResultNormalizer`。**

### 2.7 确定性 + LLM 混合

| 层级 | 用什么 | 说明 |
|------|--------|------|
| 文件、函数、类、导入、调用 | **Tree-sitter** | 确定性结构解析 |
| 架构层判断 | **LLM 辅助** | 语义理解 |
| 业务流程解释 | **LLM** | 语义理解 |
| 修改影响范围 | **静态分析 + LLM** | 结构 + 语义 |
| 任务拆解 | **LLM** | 语义理解 |
| 验收清单 | **LLM + Adapter 规则** | 语义 + 规则 |

**关键洞察：不应该让 LLM 直接读全项目"凭感觉分析"，而应该给它结构化上下文。**

### 2.8 Persistence：隐私处理

Understand-Anything 在写盘前清理绝对路径：项目内绝对路径转相对路径，项目外路径只保留文件名，避免泄露用户 home directory、用户名、公司目录结构。

**SmartDev 必须吸收这个设计。**

---

## 三、其他同类项目

### 3.1 Codebase-Memory

**论文：** [Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP](https://arxiv.org/abs/2603.27277)

**核心价值：** 基于 Tree-sitter 和 MCP 构建持久代码知识图谱，目标是减少 LLM 反复 grep/read 代码的成本。

**对 SmartDev 的参考：** 适合作为 `code.index + code.query` 的理论参考。评估中声称能用更少 token 和工具调用达到接近文件探索 Agent 的答案质量。

### 3.2 CodexGraph

**论文：** [CodexGraph: Bridging Large Language Models and Code Repositories via Code Graph Databases](https://arxiv.org/abs/2408.03910)

**核心价值：** 把代码仓库转成图数据库接口，让 LLM 通过结构化图查询理解仓库。

**对 SmartDev 的参考：** 适合参考"图数据库 schema + Agent 查询接口"。

### 3.3 RANGER

**论文：** [RANGER -- Repository-Level Agent for Graph-Enhanced Retrieval](https://arxiv.org/abs/2509.25257)

**核心价值：** 仓库级图增强检索，同时处理实体查询和自然语言查询——实体查询走图查询，自然语言查询走图探索与检索。

**对 SmartDev 的参考：** 适合参考 SmartDev 的"双检索"：符号检索 + 语义检索。

### 3.4 Code2MCP

**仓库：** [DEFENSE-SEU/Code2MCP](https://github.com/DEFENSE-SEU/Code2MCP)

**核心价值：** 自动把 GitHub 仓库转成 MCP 服务，有 7 节点 workflow：download → analysis → env → generate → run → review → finalize。

**对 SmartDev 的参考：** 适合参考"任务流水线 + Run-Review-Fix"模式。

---

# 第二部分：两个核心仓库源码深度分析

## 四、CodeGraph 源码模块分析

### 4.1 MCP Server：Direct / Proxy / Daemon 三种运行模式

CodeGraph 的 MCP 层支持：

```txt
direct   # 一个进程服务一个 MCP client
proxy    # stdio ↔ socket 代理到共享 daemon
daemon   # 后台共享进程，服务多个 client
```

多个 Agent / IDE 客户端共享一个 CodeGraph、一个 watcher、一个 SQLite handle。

**对 SmartDev 的启发：第一阶段不用做 daemon，但架构上要保留 direct CLI mode → future MCP server mode → future long-running project daemon。**

SmartDev 后续可以是：

```txt
smartdev diagnose /path
smartdev serve --mcp
smartdev daemon start
```

但第一版只做 CLI。

### 4.2 QueryBuilder：查询层封装

`QueryBuilder` 把 SQLite row 转成领域对象，并维护 prepared statements 和节点缓存。它还对低价值文件做过滤（test/spec/generated 文件不应主导"dominant file"判断）。

**SmartDev 应借鉴的模式：DB Row 不直接给 Agent，先转换成 Project Entity，再由 Context Builder 控制输出。**

### 4.3 Resolution：符号引用解析

CodeGraph 的 `resolution/` 模块处理：

- `import-resolver.ts` — 导入路径解析
- `name-matcher.ts` — 符号名匹配
- `path-aliases.ts` — 路径别名（TypeScript `paths`、Webpack `alias`）
- `go-module.ts` — Go 模块解析
- `swift-objc-bridge.ts` — Swift ↔ ObjC 桥接
- `callback-synthesizer.ts` — 回调函数合成
- `workspace-packages.ts` — monorepo 包解析

---

## 五、Understand-Anything 源码模块分析

### 5.1 GraphBuilder：从结构分析结果构建图谱

`graph-builder.ts` 是核心之一。它通过 `GraphBuilder` 维护 nodes、edges、languages、nodeIds、edgeKeys，基于 `StructuralAnalysis` 结果创建节点和关系。

**它不是把所有文件都当代码，而是把 YAML、Docker、CI、SQL、GraphQL、Terraform 等非代码结构也转成节点：**

```txt
definition → table / schema
service → service
endpoint → endpoint
step → pipeline
resource → resource
```

**这正是 SmartDev 应该借鉴的地方。** SmartDev 的 `ProjectGraphBuilder` 可以设计成：

```txt
ProjectGraphBuilder
├── addSourceFile()
├── addFunction()
├── addClass()
├── addApiEndpoint()
├── addDbModel()
├── addDesignToken()
├── addDocument()
├── addBugRecord()
├── addTask()
└── addValidationCase()
```

这样 SmartDev 的图谱不是"纯代码图"，而是"项目开发图"。

### 5.2 Search：简单但实用

Understand-Anything 的 `SearchEngine` 用 Fuse.js 做模糊搜索，字段权重：

```txt
name: 0.4
tags: 0.3
summary: 0.2
languageNotes: 0.1
```

**对 SmartDev 的启发：第一阶段不一定要直接上向量数据库。可以先做 SQLite FTS → 实体搜索 → 关系扩展 → 必要时再补 embedding。**

### 5.3 Normalize Graph：图谱归一化

`normalize-graph.ts` 处理 node id 前缀、复杂度别名、边引用重写、节点/边去重、悬空边丢弃。

**SmartDev 后续一定需要这个能力，尤其是生成任务图、影响图、测试图时。**

建议 SmartDev 定义：

```txt
normalizeEntityId()
normalizeRelationType()
normalizeRiskLevel()
normalizeTaskStatus()
dedupeRelations()
dropDanglingRelations()
```

---

# 第三部分：架构对比与整合设计

## 六、两个仓库的架构思路对比

| 维度 | CodeGraph | Understand Anything | SmartDev 应吸收 |
|------|-----------|---------------------|----------------|
| 核心目标 | Agent 低成本理解代码 | 人和 Agent 理解项目 | 两者结合 |
| 存储 | SQLite + FTS5 | JSON graph + meta/fingerprint | SQLite 索引 + JSON 导出 |
| 图谱粒度 | 代码符号 / 文件 / 关系 | 代码 + 非代码 + 业务域 + 知识 | 项目开发图谱 |
| 增量能力 | hash、files 表、watcher、sync | fingerprints / meta | 第一版做 hash + fingerprints |
| 查询 | FTS + graph traversal + MCP tools | Fuse 搜索 + dashboard | `code.search` + `project.map` |
| Agent 接入 | MCP server，支持 daemon/proxy/direct | plugin / dashboard / 多平台 | 第一版 CLI，第二版 MCP |
| LLM 输出容错 | 不是重点 | schema alias / autofix / normalize 很强 | **必须借鉴** |
| 影响分析 | 明确作为核心能力 | 更偏理解与导览 | SmartDev 必做 |
| 非代码文件 | 有 route/framework 等 | 很强，包含 config/service/table/endpoint/pipeline/resource | SmartDev 必做 |
| 适合阶段 | M2：Code Intelligence | M3：Project Knowledge Graph | 分阶段吸收 |

## 七、同类项目对 SmartDev 的取舍

### 7.1 必须吸收

```txt
CodeGraph:
- 本地索引
- SQLite + FTS5
- nodes / edges / files / unresolved refs
- hash 增量检测
- git-aware scan
- ignore 策略
- MCP 工具输出预算
- 影响分析

Understand Anything:
- 项目图谱不只包含代码
- LLM 输出 normalize / autofix
- 非代码节点：endpoint / service / table / config / document
- persistence 隐私清理
- dashboard / onboarding 思路
```

### 7.2 暂不吸收

```txt
CodeGraph:
- daemon/proxy/shared MCP engine
- 多客户端共享 watcher
- 大量语言和框架支持
- 复杂 installer

Understand Anything:
- 完整 dashboard
- multi-agent pipeline
- persona-adaptive UI
- guided tours
- embedding search
```

---

# 第四部分：SmartDev 重新设计

## 八、SmartDev 架构升级

### 8.1 新增一层：Semantic Project Context Layer

```
SmartDev Agent
├── Core Runtime (risk + reporter + adapter + workflow + patch)
├── Workflow Layer
├── Skill Layer (8 个现有 Skill)
├── Semantic Project Context Layer  ← 新增
│   ├── project_index.py    ← 项目索引（文件 + artifact）
│   ├── index_store.py      ← SQLite 存储
│   ├── artifact_extractor.py ← artifact 提取
│   ├── impact_analyzer.py  ← 影响分析
│   └── context_builder.py  ← 上下文构建
└── Project Adapter Layer
```

这一层的职责：

> **把项目从"文件集合"变成"可查询的语义结构"**

### 8.2 Phase 6-MVP 只做 4 个新 Skill

```txt
repo.scan             # 扫目录、识别文件、识别技术栈（增强现有）
code.index            # 建立 .smartdev/index.sqlite
code.search           # 按名称/路径搜索文件和 artifact
code.impact           # 文件级 + artifact 级影响分析
```

`project.map` 和 `graph.validate` 放到 Phase 6.2。

### 8.3 Skill 设计

#### `repo.scan`

```yaml
id: repo.scan
risk: R0
permission: READ
description: 扫描目录、识别技术栈、识别重要文件、识别文档状态、应用 ignore 策略
inputs:
  - project_root: str
outputs:
  - files: List[FileRecord]
  - languages: List[str]
  - important_files: List[str]
  - docs: List[str]
  - configs: List[str]
```

#### `code.index`

```yaml
id: code.index
risk: R1
permission: CACHE_WRITE
description: 为项目建立本地代码索引，不修改源代码
inputs:
  - project_root: str
  - force_reindex: bool = False
outputs:
  - files: List[FileRecord]
  - symbols: List[Symbol]
  - relations: List[Relation]
  - index_path: str
```

#### `code.search`

```yaml
id: code.search
risk: R0
permission: READ
description: 按名称、路径、类型搜索函数、类、变量、路由
inputs:
  - query: str
  - kind_filter: Optional[str] = None
  - limit: int = 20
outputs:
  - results: List[SearchResult]
```

#### `code.impact`

```yaml
id: code.impact
risk: R0
permission: READ
description: 分析某个文件、符号、模型或 API 变更可能影响哪些模块
inputs:
  - target: str  # 文件路径或符号 ID
  - max_depth: int = 3
outputs:
  - direct_references: List[Symbol]
  - callers: List[Caller]
  - callees: List[Callee]
  - affected_files: List[str]
  - risk_level: str  # R0/R1/R2/R3
```

#### `project.map`

```yaml
id: project.map
risk: R1
permission: CACHE_WRITE
description: 导出项目结构图或 onboarding 地图
inputs:
  - project_root: str
  - format: str = "json"  # json/markdown/html
outputs:
  - architecture_map: dict
  - onboarding: Optional[str]
```

#### `graph.validate`

```yaml
id: graph.validate
risk: R0
permission: READ
description: 校验节点类型、边类型、修复别名、删除悬空边
inputs:
  - graph_path: str
outputs:
  - issues: List[ValidationIssue]
  - fixed_graph: Optional[dict]
```

---

## 九、SmartDev 自有数据模型

### 9.1 SQLite Schema

```sql
-- SmartDev Code Intelligence Schema
-- Version 1

-- 文件表
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    language TEXT NOT NULL,
    size INTEGER NOT NULL,
    modified_at INTEGER NOT NULL,
    indexed_at INTEGER NOT NULL
);

-- 符号/实体表
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    qualified_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    start_line INTEGER NOT NULL,
    end_line INTEGER NOT NULL,
    signature TEXT,
    summary TEXT,
    is_exported INTEGER DEFAULT 0,
    updated_at INTEGER NOT NULL
);

-- 关系表
CREATE TABLE IF NOT EXISTS relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    file_path TEXT,
    line INTEGER,
    metadata TEXT,
    FOREIGN KEY (source_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- 项目工件表（SmartDev 特有）
CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,          -- route/endpoint/db_model/config/document/test_case/task/bug_note
    name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    metadata TEXT,
    updated_at INTEGER NOT NULL
);

-- FTS5 全文搜索
CREATE VIRTUAL TABLE IF NOT EXISTS entities_fts USING fts5(
    id, name, qualified_name, signature, summary,
    content='entities', content_rowid='rowid'
);

-- FTS 同步触发器
CREATE TRIGGER IF NOT EXISTS entities_ai AFTER INSERT ON entities BEGIN
    INSERT INTO entities_fts(rowid, id, name, qualified_name, signature, summary)
    VALUES (NEW.rowid, NEW.id, NEW.name, NEW.qualified_name, NEW.signature, NEW.summary);
END;

CREATE TRIGGER IF NOT EXISTS entities_ad AFTER DELETE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, id, name, qualified_name, signature, summary)
    VALUES ('delete', OLD.rowid, OLD.id, OLD.name, OLD.qualified_name, OLD.signature, OLD.summary);
END;

CREATE TRIGGER IF NOT EXISTS entities_au AFTER UPDATE ON entities BEGIN
    INSERT INTO entities_fts(entities_fts, rowid, id, name, qualified_name, signature, summary)
    VALUES ('delete', OLD.rowid, OLD.id, OLD.name, OLD.qualified_name, OLD.signature, OLD.summary);
    INSERT INTO entities_fts(rowid, id, name, qualified_name, signature, summary)
    VALUES (NEW.rowid, NEW.id, NEW.name, NEW.qualified_name, NEW.signature, NEW.summary);
END;

-- 索引
CREATE INDEX IF NOT EXISTS idx_entities_kind ON entities(kind);
CREATE INDEX IF NOT EXISTS idx_entities_file_path ON entities(file_path);
CREATE INDEX IF NOT EXISTS idx_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON relations(target_id);
CREATE INDEX IF NOT EXISTS idx_relations_kind ON relations(kind);
CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind);
```

### 9.2 Entity 类型

```txt
Code:
- file
- module
- class
- function
- method
- component

App:
- api_endpoint
- route
- service
- db_model
- db_table
- config
- env_var

UI:
- design_token
- page
- style_file

Docs:
- document
- requirement
- decision
- bug_note
- test_case

Workflow:
- task
- skill
- adapter
- validation
```

### 9.3 Relation 类型

```txt
Structural:
- contains
- imports
- exports
- depends_on

Behavior:
- calls
- routes_to
- reads_from
- writes_to
- validates

Project:
- documents
- tests
- configures
- implements
- affects

Workflow:
- requires
- blocks
- verifies
- updates
```

### 9.4 Risk 计算

```txt
R0: 只读 / 文档 / 无代码影响
R1: 单文件、无跨模块关系
R2: 多文件、有 API / UI / 数据影响
R3: 数据模型、权限、schema、核心协议、构建链影响
```

### 9.5 存储目录结构

```
.smartdev/
├── index/
│   ├── codegraph.sqlite       ← 代码图谱数据库
│   └── metadata.json          ← 项目元数据
├── cache/
│   ├── file_hashes.json       ← 文件哈希缓存
│   └── symbol_cache.json      ← 符号缓存
├── reports/
│   ├── architecture.json      ← 架构分析报告
│   ├── impact.json            ← 影响分析报告
│   └── onboarding.md          ← Onboarding 文档
└── config.json                ← 项目配置
```

**隐私规则：**

```txt
绝对路径不写入长期图谱
用户目录统一替换为 ~ 或相对路径
env / key / token 不入图谱
数据库真实数据不入图谱
```

---

## 十、对 SmartDev 的具体改造建议

### 10.1 现有 Skill 升级

| 现有 Skill | 升级方式 | 借鉴来源 | 阶段 |
|-----------|---------|---------|------|
| `repo.scan` | 底层接入 `code.index`，扫描后自动建立符号索引 | CodeGraph: extraction pipeline | Phase 6-MVP |
| `architecture.map` | 接入 `code.graph` 查询调用关系 | Understand-Anything: architecture-analyzer | Phase 6.2 |
| `risk.check` | 接入 `code.impact` 分析变更影响范围 | CodeGraph: `getImpactRadius()` | Phase 6-MVP |
| `task.plan` | 基于影响分析做更精准的任务拆解 | Understand-Anything: tour-builder | Phase 6.2 |
| `token.audit` | 接入符号索引，统计更准确 | CodeGraph: dead code detection | Phase 6-MVP |

### 10.2 集成策略

#### CodeGraph：Phase 6.2 再考虑适配器

第一版不做 CodeGraph 适配器。等文件级图谱跑通后再考虑。

#### Understand-Anything：先借鉴，不直接集成

适合后续做：SmartDev Project Map、SmartDev Onboarding View、SmartDev Architecture Dashboard。

---

# 第五部分：实施路线

## 十一、进入开发的建议顺序（Phase 6-MVP）

### Task 1：实现 `repo.scan`

验收标准：

```txt
能扫描项目目录
能识别主要语言
能忽略 node_modules / dist / build / .git / __pycache__
能识别 README / docs / package.json / pyproject.toml / manifest.json
能输出 files.json 或写入 files 表
```

### Task 2：实现 `index.sqlite`

验收标准：

```txt
首次运行创建 .smartdev/index.sqlite
包含 files / artifacts / relations / runs 表
重复运行不重复插入
文件 hash 变化能识别
```

### Task 3：实现 SmartFav artifact 提取

先不做通用多项目，只做 SmartFav：

```txt
manifest.json → artifact: manifest
tokens.css → artifact: design_token
FastAPI main.py → artifact: api_endpoint
development-progress.md → artifact: document
sidepanel.js / api-client.js → artifact: extension_file
```

验收标准：

```txt
能识别至少 5 类 artifact
能写入 artifacts 表
能按文件路径查询 artifact
```

### Task 4：实现 `code.search`

验收标准：

```txt
smartdev search token
smartdev search api
smartdev search ResourceItem
smartdev search sidepanel
```

能返回：

```txt
匹配文件
匹配 artifact
artifact 类型
路径
简短说明
```

### Task 5：实现 `code.impact`

第一版只做规则型影响分析，不做复杂调用图。

例如输入：

```txt
smartdev impact tokens.css
```

输出：

```txt
直接影响：
- tokens.css
- Demo 页面引用
- sidepanel.css

间接影响：
- Dark Mode
- design-tokens docs
- Side Panel 视觉验收

风险：R1/R2
验证：
- Demo 显示
- Side Panel 显示
- 320 / 400 / 480px
```

### 新增目录结构

```txt
smartdev/
├── context/
│   ├── project_index.py      ← 项目索引主入口
│   ├── index_store.py        ← SQLite 存储层
│   ├── artifact_extractor.py ← artifact 提取
│   ├── impact_analyzer.py    ← 影响分析
│   └── context_builder.py    ← 上下文构建
│
├── skills/
│   ├── code_index.py         ← code.index Skill
│   ├── code_search.py        ← code.search Skill
│   └── code_impact.py        ← code.impact Skill
│
└── adapters/
    └── smartfav.py           ← SmartFav 专用适配器
```

### `.smartdev/` 目录

```txt
.smartdev/
├── index.sqlite              ← 代码图谱数据库
├── project-graph.json        ← 项目图谱导出（可选）
├── fingerprints.json         ← 文件指纹（增量检测）
├── runs/                     ← 运行记录
└── config.json               ← 项目配置
```

注意：`.smartdev/` 是缓存和项目语义上下文，不是源代码。写入这里应归为 `CACHE_WRITE`，不是 `WRITE_CODE`。

### Benchmark 说明

文档中引用的 CodeGraph 基准数据来自其 README / 官方文档，**未在 SmartDev 项目中复测**。SmartDev 后续应做自己的小 benchmark：

```txt
任务：分析 SmartFav tokens.css 影响范围
对比：
1. 仅 grep/read
2. 使用 .smartdev/index.sqlite
指标：
- 工具调用次数
- 输出准确率
- 漏掉文件数
- 人工修正次数
```

---

## 十二、对 SmartFav 的直接落地

### 第一轮 Code Intelligence 测试

**目标：让 SmartDev 自动理解 SmartFav 的扩展端和后端关系**

任务：

1. 扫描 `apps/extension`
2. 扫描 `apps/server`
3. 识别 `sidepanel.js` 调用哪些 service
4. 识别 `api-client.js` 对应哪些 FastAPI endpoint
5. 识别 `ResourceItem` 在前后端的映射
6. 输出影响图

### 第二轮 Impact Analysis 测试

**任务：如果修改 `ResourceItem.category`，会影响哪些模块？**

期望输出：

```
直接影响：
- item model
- storage service
- api-client
- server models

间接影响：
- database resources table
- markdown frontmatter
- tag/category manager
- search/filter logic
- development-progress docs

风险：R2
验证项：API 测试、存储测试、前端渲染测试
```

### SmartFav 专用最小图谱 v0

```txt
SmartFav Project Graph v0
├── apps/extension/src/sidepanel
├── apps/extension/src/services
├── apps/server
├── assets Demo
├── docs
├── tokens.css
└── development-progress.md
```

优先识别 5 类实体：

```txt
1. files
2. api endpoints
3. resource model
4. design tokens
5. docs
```

第一轮测试任务：

```txt
任务：如果统一 tokens.css，会影响哪些文件？
```

期望 SmartDev 输出：

```txt
直接影响：
- apps/extension/assets/styles/tokens.css
- assets/tokens.css
- Demo 页面引用
- sidepanel.css

间接影响：
- Dark Mode
- README / design-tokens docs
- Side Panel 视觉验收
- Demo 视觉一致性

风险：R1 / R2，取决于是否删除重复 token 文件

验证：
- Demo 页面显示
- Side Panel 显示
- 320 / 400 / 480px
- 无硬编码主色残留
```

---

## 十三、后续路线规划

### Phase 6-MVP：Code Intelligence v0（当前阶段）

> **目标不是做完整代码图谱，而是让 SmartDev 能知道项目里有哪些关键文件、关键工件，以及某个改动大概会影响哪里。**

**只做 5 件事：**

```
1. repo.scan          — git-aware 文件扫描、ignore、重要文件识别
2. .smartdev/index.sqlite — 建立 files / artifacts / relations / runs 表
3. artifact.extract   — SmartFav 专用 artifact 提取（manifest、tokens、endpoint、doc）
4. code.search        — 基于 SQLite FTS 或简单 LIKE 搜索
5. code.impact        — 文件级 + artifact 级影响分析，不做完整调用图
```

**第一版不要做的事：**

- ❌ Tree-sitter 多语言解析 → Phase 6.2
- ❌ 完整调用图 / 引用解析 → Phase 6.2
- ❌ MCP Server → Phase 7+
- ❌ Dashboard → Phase 8
- ❌ Multi-Agent Pipeline → Phase 9
- ❌ Embedding Search → 暂缓
- ❌ Daemon / watcher → 暂缓
- ❌ CodeGraph 适配器 → Phase 6.2

**最小数据库表（第一版）：**

```sql
files(
  path TEXT PRIMARY KEY,
  hash TEXT,
  language TEXT,
  kind TEXT,
  size INTEGER,
  modified_at TEXT,
  indexed_at TEXT
);

artifacts(
  id TEXT PRIMARY KEY,
  type TEXT,          -- api_endpoint / manifest / design_token / document / ...
  name TEXT,
  file_path TEXT,
  start_line INTEGER,
  end_line INTEGER,
  metadata_json TEXT
);

relations(
  id TEXT PRIMARY KEY,
  source_id TEXT,
  target_id TEXT,
  type TEXT,
  confidence REAL,
  metadata_json TEXT
);

runs(
  id TEXT PRIMARY KEY,
  task TEXT,
  created_at TEXT,
  summary_json TEXT
);
```

**第一版支持的 artifact 类型：**

```txt
api_endpoint
manifest
design_token
document
server_file
extension_file
model
config
```

**开发顺序：**

```
M1: repo.scan（文件扫描 + ignore）
M2: .smartdev/index.sqlite（建表 + 增量）
M3: SmartFav artifact 提取（5 类实体）
M4: code.search（FTS 搜索）
M5: code.impact（文件级 + artifact 级影响分析）
M6: Tree-sitter 多语言（后续）
```

**验收命令：**

```bash
smartdev scan /path/to/smartfav
smartdev index /path/to/smartfav
smartdev search /path/to/smartfav token
smartdev impact /path/to/smartfav tokens.css
```

### Phase 6.2：Code Intelligence v1（后续）

```
Phase 6.2: Code Intelligence v1
├── Tree-sitter 多语言解析（Python ast / TS parser）
├── 完整调用图 / 引用解析
├── project.map 导出
├── graph.validate
└── CodeGraph 适配器（可选增强）
```

### Phase 7: Safe Patch Agent

```
Phase 7: Safe Patch Agent
├── code.patch 真实实现（替换占位符）
├── 影响分析驱动的风险评估
├── 自动验证（测试 + lint）
└── 变更摘要生成
```

### Phase 8: Project Knowledge Graph

```
Phase 8: Project Knowledge Graph
├── architecture.map 增强
├── domain.map — 业务域视图
├── onboarding 生成
└── Dashboard（可选，后期）
```

### Phase 9: Workflow / Multi-Agent

```
Phase 9: Workflow / Multi-Agent
├── scanner-agent
├── analyzer-agent
├── reviewer-agent
├── qa-agent
└── doc-agent
```

---

## 十四、最终判断

### 是否值得参考？

值得，而且价值很明确：

```txt
CodeGraph → 学本地代码索引、SQLite 图谱、FTS、impact analysis
Understand Anything → 学项目知识图谱、normalize/autofix、非代码节点、隐私处理
同类论文 → 学理论框架和双通道检索思路
```

### 是否现在就集成？

不建议直接集成两个完整项目。

建议：

1. **CodeGraph 先作为外部可选增强工具**（适配器模式）
2. **Understand-Anything 先作为产品形态和知识图谱设计参考**
3. **SmartDev 自己先实现最小 code.index / impact.analyze**

### 对 SmartDev 的一句话修正

原来 SmartDev 是：

> 项目开发与仓库改进 Agent。

结合这两个项目后，可以更准确地升级为：

> **基于项目语义图谱的开发诊断、任务拆解、影响分析与安全执行 Agent。**

### 最小闭环

```txt
扫描项目
  ↓
建立轻量索引
  ↓
识别关键符号和依赖
  ↓
分析变更影响
  ↓
拆解任务
  ↓
给出验收清单
```

**这就是 SmartDev Agent 进入下一阶段的核心。**

---

## 附录 A：参考资源

| 资源 | 链接 | 用途 |
|------|------|------|
| CodeGraph GitHub | https://github.com/colbymchenry/codegraph | 代码图谱实现参考 |
| CodeGraph Docs | https://colbymchenry.github.io/codegraph/ | 文档和 API 参考 |
| Understand-Anything GitHub | https://github.com/Lum1104/Understand-Anything | 知识图谱实现参考 |
| Understand-Anything Demo | https://understand-anything.com/demo/ | Dashboard 体验 |
| Codebase-Memory 论文 | https://arxiv.org/abs/2603.27277 | 持久代码知识图谱理论 |
| CodexGraph 论文 | https://arxiv.org/abs/2408.03910 | 图数据库接口设计 |
| RANGER 论文 | https://arxiv.org/abs/2509.25257 | 双通道检索 |
| Code2MCP GitHub | https://github.com/DEFENSE-SEU/Code2MCP | MCP 服务生成 workflow |
| tree-sitter | https://tree-sitter.github.io/ | 代码解析库 |
| SQLite FTS5 | https://www.sqlite.org/fts5.html | 全文搜索 |

## 附录 B：术语表

| 术语 | 定义 |
|------|------|
| Semantic Project Context | 项目的语义化结构表示，包括文件、符号、关系、架构层 |
| Code Intelligence | 基于代码结构的智能分析能力，包括索引、搜索、影响分析 |
| Knowledge Graph | 知识图谱，用节点和边表示实体及其关系 |
| Impact Analysis | 变更影响分析，追踪修改可能波及的范围 |
| Call Graph | 调用图，函数之间的调用关系 |
| Dead Code | 死代码，未被引用的代码 |
| FTS5 | SQLite 的全文搜索扩展 |
| MCP | Model Context Protocol，Agent 与工具的通信协议 |
| tree-sitter | 增量解析框架，用于代码 AST 提取 |
| Artifact | 项目工件，非代码实体（路由、配置、文档、任务等） |

---

*文档版本：2.1*
*创建日期：2026-06-06*
*更新日期：2026-06-06*
*状态：已完成技术调研，进入 MVP 实现*
*作者：SmartDev Agent Team*
