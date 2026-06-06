# SmartDev Node Bridge

> SmartDev Agent — Node bridge for JS/TS structure extraction via `@babel/parser`.
> Phase 6.3 Step 1：项目骨架，不接 Python。

## 安装

```bash
cd smartdev/context/node_bridge
npm install
```

## 快速开始

```bash
# 单次模式：JSON in → JSON out
echo '{"id":"1","file_path":"src/App.tsx","language":"typescript","content":"export const App = () => <div/>"}' | node extract_structure.js

# 批量模式（JSONL）：每行一个请求，每行一个响应
node extract_structure.js --batch
```

## 协议

JSONL (NDJSON) over stdin/stdout。每行一个 JSON。

**输入（stdin）：**
```json
{"id":"req-1","file_path":"src/App.tsx","language":"typescript","content":"..."}
```

**输出（stdout）：**
```json
{"id":"req-1","symbols":[...],"imports":[...],"exports":[],"errors":[]}
```

- `stderr` 用于 debug 信息，不污染 stdout JSON。
- `id` 字段用于请求/响应对齐。

## 能力边界（v1）

| 优先级 | 支持 | 说明 |
|--------|------|------|
| P0 | `import` declaration | default / named / namespace import |
| P0 | `export` declaration | named / default / re-export |
| P0 | `function` declaration | async function |
| P0 | `class` declaration | extends |
| P1 | 箭头函数变量 | `const X = () => {}` |
| P1 | `export const` / `export default` | 标记 `is_exported: true` |
| P2 | `interface` / `type` alias (TS) | 基础提取 |
| 不支持 | Vue / Svelte SFC | Phase 6.3C |
| 不支持 | call graph / type inference | Phase 7 |
| 不支持 | module resolution / tsconfig paths | Phase 6.3B |

## 测试

```bash
npm test
```

覆盖 6 个场景：
1. `import React from "react"`
2. `import { useState as useReactState } from "react"`
3. `export function foo() {}`
4. `export default class App {}`
5. `const Button = () => {}`
6. TSX function component + interface

## 依赖

- `@babel/parser` ^7.26.0
- Node.js >= 16.0.0

## 对应文档

- `phase-6.3-design.md` — 完整设计文档
- `structure_extractor.py` — Python 侧 Provider 接口（Phase 6.3 Step 2 集成）
- `artifact_extractor.py` — JS/TS import relation 构建（Phase 6.3 Step 4）
