# Phase 7 Step 0 — Tree-sitter Multi-language Graph Provider 执行前设计

> 状态：设计文档（Step 0），不动代码
> 前置：Phase 6.3 已完成并冻结（386 tests，清洁基线）
> 目标：定清楚 Tree-sitter 的依赖策略、Provider 策略、首批语言、fallback、测试范围和回滚方案

---

## 1. 背景

SmartDev 当前有两条稳定的代码结构提取链路：

| 语言 | Provider | 引擎 | confidence | 依赖 |
|------|----------|------|-----------|------|
| Python | `PythonAstExtractor` | stdlib `ast` | 1.0 | 零 |
| JavaScript / TypeScript | `NodeBridgeExtractor` | `@babel/parser` | 0.95 | Node.js (optional) |

不支持的语言（Go, PHP, Rust, Java, Ruby, C, C++ 等）返回空结果。

Tree-sitter 是一个增量解析框架，提供 100+ 语言的语法解析。目标是把 Tree-sitter 作为第三层 Provider（**多语言扩展层**），而不是替换已有的 Python / JS/TS 稳定链路。

---

## 2. 六个核心问题

### Q1: Tree-sitter 是 optional dependency 还是默认依赖？

**答案：optional dependency，与 Node bridge 同级别。**

```
Python core                        = 零外部依赖（pip install 不需要任何东西）
Node bridge                        = optional（有 Node 时启用 JS/TS 解析）
Tree-sitter bridge                 = optional（有 tree-sitter 时启用多语言解析）
Python ast                         = 始终可用
```

**理由：**

1. Python core 零依赖原则不动 — `pip install` 不需要 tree-sitter
2. 目标用户（开发者）可以通过 `pip install tree-sitter` 手动安装
3. 检测到 tree-sitter Python binding 可用 → 自动注册 Provider
4. 不可用 → 该语言返回空结果（与当前行为一致，不降级）

**实现方式：**
```python
def _tree_sitter_available() -> bool:
    try:
        import tree_sitter
        return True
    except ImportError:
        return False
```

Phase 7 不引入 Node/WASM bridge 作为 Tree-sitter 的接入方式。只通过 Python binding。

### Q2: 使用 Python tree-sitter binding 还是 Node/WASM bridge？

**答案：Python binding（`tree-sitter` PyPI 包）。**

推荐理由：
- `tree-sitter` Python 包（py-tree-sitter）已在 PyPI 可用，支持 0.23+
- 与 Python AST extractor 在同一进程内运行，无 IPC 开销
- grammar 文件可以按需编译或使用预编译 wheel
- 无需管理额外运行时（与 Node bridge 不同）

Node/WASM 方案不考虑的原因：
- WASM 性能开销显著（跨 VM 序列化）
- Node bridge 已有成熟的 Babel 方案覆盖 JS/TS
- 为多语言再建一个 Node 子进程方案会增加运维复杂度

**注意：** 如果未来 Python binding 维护停滞，可用 `tree-sitter-{lang}` 的预编译包作为备选。

### Q3: 首批支持哪 1–2 个语言？

**答案：Go — 单个语言试点。**

理由：
- Go 语法结构清晰（`func`, `type`, `struct`, `interface`, `import`）
- function / method / struct / import 提取路径直接
- Tree-sitter Go grammar 成熟度高（`tree-sitter-go`）
- 对后续跨语言 Agent 路线有价值（Go 在微服务/后端领域广泛使用）
- 不与现有 Python / JS/TS 链路产生任何冲突

**暂不做：**
- PHP：语法复杂度高（`$var`, 动态调用, `use` 语义多样），需更多设计
- Rust：生命周期/宏处理复杂度高
- 多语言同时做：分散精力，测试矩阵爆炸

### Q4: TreeSitterProvider 是否复用现有 Provider 接口？

**答案：完全复用 `StructureExtractorProvider` 接口。**

```python
class TreeSitterProvider(StructureExtractorProvider):
    """Tree-sitter 多语言结构提取器

    作为 optional multi-language provider，不替换 Python AST / NodeBridge。
    confidence = 0.98（tree-sitter 确定性解析，但语法错误时 degrades）
    """

    @property
    def name(self) -> str:
        return "tree_sitter"

    @property
    def supported_languages(self) -> list[str]:
        return ["go"]  # Step 1 只注册 go

    def extract(self, file_path: str, content: str) -> StructureExtractionResult:
        ...
```

**Provider 注册优先级（Phase 7 最终状态）：**

```
1. PythonAstExtractor      → python (confidence=1.0)         ← 不替换
2. NodeBridgeExtractor     → javascript, typescript (0.95)  ← 不替换
3. TreeSitterProvider      → go, ... (confidence=0.98)       ← 新增，不覆盖已有
4. JsTsRegexFallbackExtractor → fallback (0.55)              ← 保留
5. NullStructureExtractor  → 不支持的语言
```

关键约束：`TreeSitterProvider` 的 `supported_languages` 不包含 `python`、`javascript`、`typescript`。已有语言通过已有 Provider 处理。

### Q5: 输出是否继续映射到 CodeSymbol / ImportRecord？

**答案：完全复用，零下游改动。**

Tree-sitter AST 节点 → `CodeSymbol` 映射：

| Tree-sitter 节点 | CodeSymbol kind | 示例 |
|-----------------|----------------|------|
| `function_declaration` | function | `func NewUser(name string) User` |
| `method_declaration` | method | `func (u *User) Name() string` |
| `type_declaration` → `struct_type` | class | `type User struct { ... }` |
| `type_declaration` → `interface_type` | interface | `type Reader interface { ... }` |
| `import_declaration` | import | `import "fmt"` |

现有 `_symbol_to_artifact()` 和 `_build_import_relations()` 不需要修改。
Tree-sitter 提取的 `CodeSymbol` 会自然进入现有 artifact → relation → index → search → project.map → graph.validate 链路。

**注意：** Go 的 import 语法（`import "fmt"` / `import ("fmt"; "os")`）与 Python 不同，但与 JS/TS 一样需要在 `_build_import_relations()` 中增加 Go import 的解析分支。这部分在 Step 2 实现，Step 0 只标记为需要。

### Q6: 没有 grammar 或解析失败时如何 fallback？

**答案：三层 fallback，静默处理。**

```
1. tree-sitter 包未安装
   → _tree_sitter_available() = False
   → TreeSitterProvider 不注册
   → 该语言使用 NullStructureExtractor（返回空结果，不报错）

2. 特定语言 grammar 不可用
   → Provider 注册，但 extract() 返回 errors=["grammar not available for go"]
   → 不影响其他语言的提取

3. 单文件解析失败（语法错误 / 超时）
   → extract() 返回 errors=["parse error: ..."] / ["timeout"]
   → 不影响其他文件的索引
```

**confidence 调整：**
- 正常解析 → 0.98
- 解析失败 → 该文件返回空结果，errors 记录原因

---

## 3. 技术设计概览

### 3.1 Python tree-sitter binding 使用模型（概念示例，非最终 API）

```python
# Tree-sitter Python binding 和各语言 grammar 包的 API 版本可能变化。
# 通过 _load_language() 适配层封装，不把具体调用方式散落在 Provider 里。
# Step 1 不调用以下任何 API — 只做骨架。

def _load_language(language: str):
    """语言 grammar 加载适配层

    封装 grammar 加载的所有变体：
    - tree-sitter-{lang} 预编译 wheel
    - tree_sitter.Language(path, name)
    - 动态 .so 文件
    - 未来可能的其它 tree-sitter language package
    """
    ...
```

### 3.2 结构提取映射（Go 首批，Step 2 实现）

仅提取顶层声明（与 Python AST / NodeBridge extractor 对齐）：

```python
def _extract_go(code: bytes, root_node) -> list[CodeSymbol]:
    symbols = []
    for child in root_node.children:
        if child.type == "function_declaration":
            symbols.append(_func_symbol(child))
        elif child.type == "method_declaration":
            symbols.append(_method_symbol(child))
        elif child.type == "import_declaration":
            symbols.append(_import_symbol(child))
        elif child.type == "type_declaration":
            symbols.extend(_type_symbols(child))
    return symbols
```

**p0 提取（Phase 7 Step 2）：**
- `function_declaration` → function
- `method_declaration` → method（parent = receiver type）
- `import_declaration` → import
- `type_declaration` → class（struct）/ interface

**不做（Phase 7 范围内）：**
- 函数内局部变量
- 函数调用关系
- 表达式级类型推断
- interface 实现关系
- struct 字段级解析（标记为 P2）

### 3.3 文件结构

```
smartPi/smartdev-agent/
└── smartdev/
    └── context/
        ├── tree_sitter_provider.py   ← Phase 7 Step 1 新建
        └── tree_sitter_grammars/     ← 放置 grammar .so 文件
            └── README.md             ← 安装说明
```

### 3.4 自动检测

```python
# structure_extractor.py 新增

def _tree_sitter_available() -> bool:
    try:
        import tree_sitter
        return True
    except ImportError:
        return False

def _try_create_tree_sitter_provider() -> StructureExtractorProvider | None:
    try:
        from smartdev.context.tree_sitter_provider import TreeSitterProvider
        return TreeSitterProvider()
    except Exception:
        return None

# StructureExtractor.__init__ 新增
# if auto_detect_treesitter and _tree_sitter_available():
#     provider = _try_create_tree_sitter_provider()
#     if provider:
#         self.register_provider(provider)
```

---

## 4. 影响范围分析

| 文件 | 变更 | 风险 |
|------|------|------|
| `tree_sitter_provider.py` | 新建 | R1 |
| `structure_extractor.py` | +tree-sitter 自动检测注册 | R1 |
| `artifact_extractor.py` | +Go import 解析分支（后续 Step 2） | R2 |
| 其他模块 | **不修改** | — |

### 不修改的文件

- `index_store.py` / `project_index.py` / `impact_analyzer.py`
- `project_map.py` / `graph_validator.py`
- `node_bridge.py` / `node_bridge/`
- 所有 Skills
- SQLite schema

### 测试新增

| Step | 测试文件 | 覆盖内容 |
|------|---------|---------|
| Step 1 | `test_tree_sitter_provider.py` | Provider 注册、接口合规、缺依赖静默、不支持语言 |
| Step 2 | `test_go_extraction.py` | Go 文件 function/struct/interface/import 提取 |
| Step 3 | `tests/fixtures/go_project/` | Go fixture 全链路验证 |
| Step 4 | `test_tree_sitter_full_pipeline.py` | 真实 Go 项目 index → search → map → validate |

---

## 5. 风险等级与回滚方案

### 按 Step 拆分风险

| Step | 风险 | 理由 |
|------|------|------|
| Step 1 | **R1** | 只新增 Provider 骨架 + 自动检测，不接 grammar，不改变现有解析输出 |
| Step 2 | **R2** | 接 Go grammar + 修改 `artifact_extractor.py` 处理 Go import |
| Step 3 | R1 | fixture 全链路验证，不碰生产代码 |
| Step 4 | R1 | 真实项目验证，只读 |

### 回滚方案

1. Tree-sitter 未安装 → Provider 不注册，行为不变
2. Grammar 加载失败 → extract() 返回 errors，不中断索引
3. 单 Step 回滚 → 删除对应 Provider 注册或 tmp 移除 auto_detect 调用
4. 完全回滚 → 删除 `tree_sitter_provider.py` + 移除 `structure_extractor.py` 中的 auto_detect 调用

---

## 6. 实施路线

### Phase 7 Step 0 ✅ 当前 — 设计确认

### Phase 7 Step 1: TreeSitterProvider 骨架

- `tree_sitter_provider.py` — 实现 `StructureExtractorProvider` 接口
- 依赖检测 `_tree_sitter_available()`
- `structure_extractor.py` 新增 auto_detect 入口
- 测试：Provider 注册 + 缺依赖跳过 + 不支持语言
- **此时不接真实 grammar，不提取任何代码结构**
- 预期：386 → ~392 tests

### Phase 7 Step 2: Go 语言试点

- `tree_sitter_provider.py` 内实现 Go AST 节点 → CodeSymbol 映射
- `artifact_extractor.py` 增加 Go import 解析分支
- 测试：Go function / struct / interface / import 提取
- 预期：~400 tests

### Phase 7 Step 3: Go fixture 全链路验证

- `tests/fixtures/go_project/` — 小型 Go 项目
- 验证：index → search → project.map → graph.validate
- 预期：~410 tests

### Phase 7 Step 4: 真实 Go 项目验证

- 拿一个小型 Go 项目跑一次（如单文件工具）

### 不做（Phase 7 范围内）

```
❌ 替换 PythonAstExtractor
❌ 替换 NodeBridgeExtractor
❌ 完整调用图（call graph）
❌ 类型推断
❌ 跨语言调用解析
❌ Tree-sitter Dashboard / UI
❌ 一次性支持所有语言
❌ 让 tree-sitter 成为必装依赖
❌ Node/WASM bridge 接入 Tree-sitter
```

---

## 7. 验收标准

1. 设计文档所有 6 个问题有明确答案
2. Phase 7 边界清晰（做什么 / 不做什么）
3. 与 Python AST / NodeBridge 不冲突
4. 回滚方案可执行
5. 后续 Steps 可逐步验证
