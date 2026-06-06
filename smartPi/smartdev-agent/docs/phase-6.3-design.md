# Phase 6.3 — JS/TS Parser Provider 执行前设计

> 状态：设计文档（Step 0），不动代码
> 前置：Phase 6.2 已完成并冻结（310 tests）
> 目标：定清楚 Provider 接口、Node bridge 协议、Babel vs TS Compiler API 取舍、fallback 策略、测试范围、风险等级

---

## 1. 背景

Phase 6.2 的 JS/TS 结构提取使用 `JsTsRegexFallbackExtractor`，基于 4 个正则表达式，confidence=0.55。它有 5 个明确限制：

- 无嵌套作用域解析
- 无类型解析
- 无 JSX 组件语义
- 无装饰器处理
- 无复杂泛型解析

Phase 6.3 的目标不是"修正则"，而是为 JS/TS 提供一条**正式的、可升级的解析路径**。正则 fallback 保留，作为 Node 不可用时的降级方案。

---

## 2. 五个核心问题

### Q1: SmartDev 是否允许 Phase 6.3 引入 Node 运行时依赖？

**答案：允许，但作为 optional dependency。**

```
Python core            = 零外部依赖（pip install 不需要任何东西）
Node bridge            = optional dependency（有 Node 时启用）
JS/TS 高置信度解析      = 有 Node → Babel/TS Compiler API
无 Node 时             = regex fallback（维持现状，不扩）
```

**理由：**

1. SmartDev 的核心价值是"开发诊断 Agent"，不是"零依赖 Python 库"。目标用户（开发者）大概率有 Node 环境。
2. `pip install` 零依赖承诺不破 — Node bridge 是运行时检测，不是安装时依赖。
3. 这与许多 Python 工具的 optional dependency 模式一致（如 `black` 的 `--fast` 模式、`mypy` 的 `dmypy` daemon）。

**实现方式：**
- 启动时 `shutil.which("node")` 检测
- 有 Node → 自动注册 `NodeBridgeExtractor`，替换 regex fallback
- 无 Node → 静默使用 `JsTsRegexFallbackExtractor`（confidence=0.55）
- `smartdev index` 输出中标注 "JS/TS: Node bridge (confidence=0.95)" 或 "JS/TS: regex fallback (confidence=0.55)"

### Q2: JS/TS parser provider 是可选增强，还是默认能力？

**答案：可选增强，但默认启用检测。**

- 不是"用户必须手动安装"的插件 — 检测到 Node 就自动用
- 不是"替换 Python core"的架构变更 — 只是替换同语言的 Provider
- `register_provider()` 机制已支持：Node bridge 注册后自动覆盖 `javascript`/`typescript`

**Provider 注册优先级（从高到低）：**
1. `NodeBridgeExtractor` (Babel, confidence=0.95) — 有 Node 时
2. `JsTsRegexFallbackExtractor` (regex, confidence=0.55) — 无 Node 时
3. `NullStructureExtractor` — 不支持的语言

### Q3: 第一版优先支持 JS/TS/TSX 的哪些结构？

**按优先级排序（v1 最小可用集）：**

| 优先级 | 结构 | 理由 |
|--------|------|------|
| P0 | `import` / `export` 语句 | 直接服务 ImpactAnalyzer 的 import relations |
| P0 | `function` 声明 | 最基础的代码结构 |
| P0 | `class` 声明 | OOP 核心结构 |
| P1 | 箭头函数（`const x = () => {}`） | React 组件最常见的定义方式 |
| P1 | `export default` / `export const` | 模块导出分析 |
| P2 | `interface` / `type` 别名（TS） | TypeScript 项目的核心结构 |
| P2 | JSX component 识别（大写开头的函数/箭头函数） | React 项目特有 |
| P3 | `enum` / `namespace`（TS） | 使用频率较低 |
| 不做 | 函数调用图（call graph） | 需完整数据流分析，Phase 7 |
| 不做 | 类型推断/类型关系 | 需 TypeScript Compiler API 完整类型检查 |

**v1 目标覆盖率：**
- Regex fallback: ~60-70% → confidence=0.55
- Node bridge v1: ~90-95% → confidence=0.95（P0+P1 结构全覆盖）

### Q4: Provider 输出是否复用当前 CodeSymbol / ImportRecord？

**答案：完全复用，零下游改动。**

现有数据流：
```
extract_structure() → CodeSymbol → _symbol_to_artifact() → ArtifactRecord → IndexStore
                                                                           ↓
                              _build_import_relations() → RelationRecord → IndexStore
```

Node bridge 的输出也是 `StructureExtractionResult`：
```python
@dataclass
class StructureExtractionResult:
    symbols: list[CodeSymbol]  # 复用现有模型
    imports: list[str]          # import 语句文本
    errors: list[str]
```

**不需要修改的文件：**
- `index_store.py` — 不变
- `project_index.py` — 不变
- `impact_analyzer.py` — 不变
- `project_map.py` — 不变
- `graph_validator.py` — 不变
- `code_search/skill.py` — 不变
- `code_impact/skill.py` — 不变

**需要修改/新增的文件：**
- `structure_extractor.py` — 新增 `NodeBridgeExtractor` 类
- `artifact_extractor.py` — 新增 `_build_js_import_relations()`（JS/TS import 语法不同于 Python）
- `node_bridge/extract_structure.js` — Node 端脚本（新文件）
- `node_bridge/package.json` — 声明 `@babel/parser` 依赖（新文件）

### Q5: 如果 Node 不存在，是否自动 fallback 到 JsTsRegexFallbackExtractor？

**答案：是。静默 fallback，不报错，不中断索引流程。**

具体行为：
```
1. StructureExtractor 初始化时检测 Node
2. 有 Node → register_provider(NodeBridgeExtractor())
3. 无 Node → 保持 JsTsRegexFallbackExtractor()（已在 _DEFAULT_PROVIDERS 中）
4. 索引时输出一行提示（非 error）：
   "JS/TS 解析: regex fallback (Node.js 未检测到，安装 Node 可启用高置信度解析)"
```

---

## 3. 技术设计

### 3.1 Node Bridge 协议

**通信方式：** Python `subprocess` 调用 Node 脚本，JSON over stdin/stdout。

**输入（stdin）：**
```json
{
  "file_path": "src/components/App.tsx",
  "content": "import React from 'react';\n\nexport default function App() {...}\n",
  "language": "typescript"
}
```

**输出（stdout）：**
```json
{
  "symbols": [
    {
      "name": "react",
      "kind": "import",
      "file_path": "src/components/App.tsx",
      "start_line": 1,
      "end_line": 1,
      "signature": "import React from 'react'",
      "parent": "",
      "is_exported": false,
      "confidence": 0.95,
      "extractor": "node_bridge_babel",
      "limitations": []
    },
    {
      "name": "App",
      "kind": "function",
      "file_path": "src/components/App.tsx",
      "start_line": 3,
      "end_line": 5,
      "signature": "export default function App()",
      "parent": "",
      "is_exported": true,
      "confidence": 0.95,
      "extractor": "node_bridge_babel",
      "limitations": []
    }
  ],
  "imports": [
    "import React from 'react'"
  ],
  "errors": []
}
```

**关键设计决策：**

1. **单文件协议**：每次调用传入一个文件的内容。批量处理在 Python 侧做（与现有 extract 循环一致）。
2. **Node 进程复用**：Python 侧维护一个长期运行的 Node 子进程，通过 stdin/stdout JSON 行协议通信，避免每个文件都启动新进程。
3. **超时处理**：单文件 30s 超时，超时后跳过该文件，记录 error。
4. **错误隔离**：Node 进程崩溃不影响 Python 主进程，自动重启 Node 进程并继续。

### 3.2 Node 进程复用设计

**启动阶段：**
```python
class NodeBridgeProcess:
    def __init__(self):
        self.process = subprocess.Popen(
            ["node", "node_bridge/extract_structure.js", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def extract(self, file_path, content, language) -> dict:
        request = json.dumps({"file_path": file_path, "content": content, "language": language})
        self.process.stdin.write(request + "\n")
        self.process.stdin.flush()
        response = self.process.stdout.readline()
        return json.loads(response)
```

**为什么复用进程而不是每个文件启动新进程？**
- 启动 Node + 加载 Babel parser 约 200-500ms
- 一个项目可能有几十到几百个 JS/TS 文件
- 进程复用可节省 80%+ 的时间开销

### 3.3 Babel Parser vs TypeScript Compiler API

| 维度 | @babel/parser | TypeScript Compiler API |
|------|--------------|------------------------|
| 文件支持 | JS/JSX/TS/TSX（插件切换） | TS/TSX 原生，JS/JSX 需额外处理 |
| 安装大小 | ~2MB（仅 parser） | ~60MB（完整 typescript 包） |
| 速度 | 快（纯 parser，无类型检查） | 较慢（含类型检查） |
| tsconfig 感知 | ❌ | ✅ |
| 类型解析 | ❌ | ✅ |
| 社区成熟度 | 极高 | 极高 |
| import/export 提取 | ✅ | ✅ |
| class/function 提取 | ✅ | ✅ |
| JSX 处理 | ✅（jsx 插件） | ✅（原生） |
| 适合 Phase 6.3 | ✅ **推荐** | 仅 TS 项目有额外价值 |

**推荐：Babel Parser for Phase 6.3A**

理由：
1. 一套代码覆盖 JS/JSX/TS/TSX（通过插件切换）
2. 体积小，安装快
3. 只做结构提取，不需要类型检查 — Babel 的 AST 足够
4. TypeScript Compiler API 在 Phase 6.3B 作为可选增强（需要 tsconfig 感知时）

**Babel Parser 插件映射：**
```javascript
const plugins = {
  javascript: ["flow", "jsx"],
  typescript: ["typescript", "jsx"],
};
```

**⚠️ 重要：Babel Parser 不能天然覆盖 Vue / Svelte。**
Vue SFC（`.vue`）和 Svelte（`.svelte`）需要先抽取 `<script>` / `<script setup>` 块，再交给 Babel 解析。这个能力不在 Phase 6.3A/6.3B 范围内，标记为 Phase 6.3C：SFC Script Block Extraction。
```

### 3.4 JS/TS Import Relation 构建

**与 Python 的关键差异：**

| 特性 | Python | JS/TS |
|------|--------|-------|
| 语法 | `from X import Y` / `import X` | `import X from 'Y'` / `import { X } from 'Y'` / `import * as X from 'Y'` |
| 模块路径 | 点号分隔（`a.b.c`） | 斜杠或点号（`./a/b`, `../c`, `lodash`） |
| 路径解析 | `sys.path` / 绝对路径 | `node_modules` / `tsconfig paths` / `package.json exports` |
| 相对路径 | `.module` 前缀 | `./` 或 `../` 前缀 |
| 动态导入 | 不支持 | `import()` — **v1 不做** |
| 重新导出 | 罕见 | `export { X } from 'module'` — 需要处理 |

**目标 artifact 分类（与 Python 保持一致）：**

| JS/TS 路径 | artifact target_id | type |
|-----------|-------------------|------|
| `import React from 'react'` | `external:javascript:react` | external_module |
| `import { useState } from 'react'` | `external:javascript:react` | external_module |
| `import { Button } from './components/Button'` | `module:./components/Button` → resolved | module |
| `import { Button } from '@/components/Button'` | `module:src/components/Button`（tsconfig paths 解析后） | module |
| `import { X } from 'unresolved-pkg'` | `unresolved:javascript:unresolved-pkg` | unresolved_module |

**新增函数：`_build_js_import_relations()`**
- 位于 `artifact_extractor.py`
- 与 `_build_import_relations()` 并行，通过 language 参数路由
- 解析 import/export 语句，构建 `RelationRecord`
- 处理 `tsconfig.json` paths 映射（可选，v1 可先不做）

### 3.5 Node Bridge 脚本结构

```
smartPi/smartdev-agent/
└── smartdev/
    └── context/
        └── node_bridge/
            ├── package.json          ← { "dependencies": { "@babel/parser": "^7.x" } }
            ├── extract_structure.js  ← Node 入口脚本
            └── README.md             ← 安装说明：cd node_bridge && npm install
```

**`extract_structure.js` 核心逻辑：**
```javascript
const parser = require('@babel/parser');

function extractStructure(filePath, content, language) {
  const plugins = getPlugins(language);
  const ast = parser.parse(content, {
    sourceType: 'module',
    plugins: plugins,
    errorRecovery: true,  // Babel 7.26+ 支持，解析错误不中断
  });

  const symbols = [];
  const imports = [];

  // 遍历 AST 顶层节点
  for (const node of ast.program.body) {
    switch (node.type) {
      case 'ImportDeclaration':
        // import X from 'module' / import { X } from 'module'
        imports.push(getImportSource(node));
        symbols.push(importSymbol(node, filePath));
        break;
      case 'ExportNamedDeclaration':
      case 'ExportDefaultDeclaration':
        // export const X / export default X / export { X } from 'module'
        if (node.source) {
          imports.push(node.source.value);
          symbols.push(reExportSymbol(node, filePath));
        }
        if (node.declaration) {
          symbols.push(...extractDeclaration(node.declaration, filePath, true));
        }
        break;
      case 'FunctionDeclaration':
        symbols.push(functionSymbol(node, filePath, false));
        break;
      case 'ClassDeclaration':
        symbols.push(classSymbol(node, filePath, false));
        break;
      case 'VariableDeclaration':
        // const X = () => {} / const X = function() {}
        symbols.push(...extractVariable(node, filePath));
        break;
      case 'TSTypeAliasDeclaration':
        symbols.push(typeAliasSymbol(node, filePath));
        break;
      case 'TSInterfaceDeclaration':
        symbols.push(interfaceSymbol(node, filePath));
        break;
    }
  }

  return { symbols, imports, errors: [] };
}

// 批处理模式
if (process.argv.includes('--batch')) {
  const readline = require('readline');
  const rl = readline.createInterface({ input: process.stdin });
  rl.on('line', (line) => {
    const req = JSON.parse(line);
    const result = extractStructure(req.file_path, req.content, req.language);
    process.stdout.write(JSON.stringify(result) + '\n');
  });
}
```

### 3.6 Python 侧 `NodeBridgeExtractor`

```python
class NodeBridgeExtractor(StructureExtractorProvider):
    """Node + Babel Parser 提取器

    通过 Node 子进程调用 @babel/parser，实现 JS/TS/JSX/TSX 高置信度解析。

    confidence = 0.95（v1）
    """

    @property
    def name(self) -> str:
        return "node_bridge_babel"

    @property
    def supported_languages(self) -> list[str]:
        return ["javascript", "typescript"]

    @property
    def confidence(self) -> float:
        return 0.95

    def __init__(self):
        self._bridge: NodeBridgeProcess | None = None

    def extract(self, file_path: str, content: str) -> StructureExtractionResult:
        if self._bridge is None:
            self._bridge = NodeBridgeProcess()
        try:
            result = self._bridge.extract(file_path, content, language)
            return StructureExtractionResult(
                symbols=[CodeSymbol(**s) for s in result["symbols"]],
                imports=result["imports"],
                errors=result.get("errors", []),
            )
        except (TimeoutError, OSError) as e:
            return StructureExtractionResult(
                symbols=[], imports=[],
                errors=[f"Node bridge 失败: {e}"],
            )
```

---

## 4. 影响范围分析

### 需要修改的文件

| 文件 | 变更 | 风险 |
|------|------|------|
| `structure_extractor.py` | 新增 `NodeBridgeExtractor` + `NodeBridgeProcess` | R1 |
| `artifact_extractor.py` | 新增 `_build_js_import_relations()` | R2（影响 import 关系构建） |
| `node_bridge/package.json` | 新建，声明 `@babel/parser` 依赖 | R0 |
| `node_bridge/extract_structure.js` | 新建，Node 端 Babel 解析脚本 | R1 |
| `node_bridge/README.md` | 新建，安装说明 | R0 |

### 不需要修改的文件

- `index_store.py`, `project_index.py`, `impact_analyzer.py`
- `project_map.py`, `graph_validator.py`
- `code_search/`, `code_impact/`, 所有其他 Skills
- `CLI.py`（但建议在 `smartdev index` 输出中添加 Node bridge 状态）

### 测试新增

| 测试文件 | 覆盖内容 | 预计测试数 |
|---------|---------|-----------|
| `test_node_bridge_extractor.py` | NodeBridgeExtractor 单元测试（需要 Node） | 10-15 |
| `test_js_import_relations.py` | JS/TS import relation 构建 | 10-15 |
| `test_js_structure_via_bridge.py` | 集成测试：extract → artifact → relation（需要 Node） | 5-10 |
| 更新 `test_structure_extractor.py` | Node 检测/fallback 测试 | 3-5 |

---

## 5. 风险等级与回滚方案

### 风险等级：R2

- **多文件变更**：5 个文件（3 新建 + 2 修改）
- **新依赖**：Node.js + `@babel/parser`（optional）
- **不影响核心链路**：Python AST 提取、artifact 提取、现有测试完全不受影响

### 回滚方案

1. **Node bridge 失败**：静默 fallback 到 `JsTsRegexFallbackExtractor`，不中断索引
2. **Babel 解析错误**：单个文件失败不影响其他文件，错误记录到 `errors` 列表
3. **完全回滚**：删除 `NodeBridgeExtractor` 注册，恢复 regex fallback 为默认 Provider

---

## 6. 实施路线

### Phase 6.3A: Node Parser Bridge 最小实现（建议先做）

```
Step 1: node_bridge/ 项目骨架（package.json + extract_structure.js）
Step 2: NodeBridgeProcess（Python 子进程管理）
Step 3: NodeBridgeExtractor（实现 StructureExtractorProvider 接口）
Step 4: _build_js_import_relations()（artifact_extractor.py 新增）
Step 5: Node 检测 + 自动注册/fallback 逻辑
Step 6: 测试
```

### Phase 6.3B: TypeScript Compiler API 增强（后续可选）

```
- tsconfig.json paths 解析
- 类型级别 import 关系
- JSX 组件层级关系
```

### 不做（Phase 6.3 范围内）

```
❌ 继续强化 regex fallback
❌ Tree-sitter 集成（Phase 7）
❌ 函数调用图
❌ 类型推断/类型关系
❌ Webpack/Vite alias 解析
```

---

## 7. 验收标准

1. `python -m pytest tests/ -q` — 所有现有 310 tests 通过，无回归
2. 新增测试：Node bridge 有/无两种场景的测试
3. `smartdev index` 在 Node 可用时输出 confidence=0.95 的 JS/TS artifact
4. `smartdev index` 在 Node 不可用时静默 fallback 到 regex（confidence=0.55）
5. `smartdev impact` 能基于 Node bridge 提取的 import 关系做反向分析
6. `project-map.json` 中 JS/TS 文件的 module artifact 置信度正确标注
7. `graph-validation-report.md` 对 JS/TS 关系的校验结果合理
