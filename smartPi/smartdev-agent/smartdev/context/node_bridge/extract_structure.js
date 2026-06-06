#!/usr/bin/env node
/**
 * SmartDev Agent — Node Bridge: JS/TS Structure Extraction
 *
 * 协议：JSONL (NDJSON) over stdin/stdout
 * 每一行是一个独立的 JSON 请求/响应。
 *
 * 输入（stdin）：
 *   {"id":"req-1","file_path":"src/App.tsx","language":"typescript","content":"..."}
 *
 * 输出（stdout）：
 *   {"id":"req-1","symbols":[...],"imports":[...],"exports":[],"errors":[]}
 *
 * 能力边界（v1）：
 *   - P0: import / export / function / class 声明
 *   - P1: 箭头函数变量 / export const / export default
 *   - 不支持: Vue/Svelte SFC, call graph, type inference, module resolution, tsconfig paths
 *
 * 使用方式：
 *   单次: echo '{"id":"1",...}' | node extract_structure.js
 *   批量: node extract_structure.js --batch
 *
 * 对应文档：
 *   - phase-6.3-design.md §3.1（Node Bridge 协议）
 *   - phase-6.3-design.md §3.5（Node Bridge 脚本结构）
 */

const parser = require("@babel/parser");

// ── 插件映射 ──────────────────────────────────────────────

const PLUGIN_MAP = {
  javascript: ["flow", "jsx"],
  typescript: ["typescript", "jsx"],
};

const COMMON_PLUGINS = [
  "decorators-legacy",
  "classProperties",
  "objectRestSpread",
  "dynamicImport",
  "importMeta",
  "topLevelAwait",
  "optionalChaining",
  "nullishCoalescingOperator",
];

function getPlugins(language) {
  const base = PLUGIN_MAP[language] || PLUGIN_MAP["javascript"];
  return [...base, ...COMMON_PLUGINS];
}

// ── 行号计算 ──────────────────────────────────────────────

function getLine(content, pos) {
  return content.slice(0, pos).split("\n").length;
}

// ── 导出判断 ──────────────────────────────────────────────

function isExported(leadingComments) {
  if (!leadingComments || leadingComments.length === 0) return false;
  return leadingComments.some(
    (c) => c.value && c.value.trim() === "@export"
  );
}

// ── Symbol 构建 ───────────────────────────────────────────

const EXTRACTOR_NAME = "node_bridge_babel";
const CONFIDENCE = 0.95;
const LIMITATIONS = []; // v1 不设限制（完整 P0+P1 覆盖）

function makeSymbol(filePath, content, name, kind, startPos, endPos, signature, extra) {
  return {
    name,
    kind,
    file_path: filePath,
    start_line: getLine(content, startPos),
    end_line: getLine(content, endPos),
    signature: signature || "",
    parent: extra?.parent || "",
    is_exported: extra?.is_exported || false,
    confidence: CONFIDENCE,
    extractor: EXTRACTOR_NAME,
    limitations: LIMITATIONS,
  };
}

// ── Import Specifier 提取 ────────────────────────────────

function extractSpecifiers(specifiers) {
  return specifiers.map((s) => {
    // ImportDefaultSpecifier: import React from 'react'
    // ImportNamespaceSpecifier: import * as React from 'react'
    // ImportSpecifier: import { useState } from 'react'
    const imported =
      s.type === "ImportDefaultSpecifier"
        ? "default"
        : s.type === "ImportNamespaceSpecifier"
          ? "*"
          : s.imported?.name || s.imported?.value || "default";
    const local = s.local?.name || "";
    return { imported, local };
  });
}

// ── Export Specifier 提取 ────────────────────────────────

function extractExportSpecifiers(specifiers) {
  return specifiers.map((s) => ({
    exported: s.exported?.name || s.exported?.value || "",
    local: s.local?.name || "",
  }));
}

// ── 声明提取辅助 ─────────────────────────────────────────

function extractDeclaration(node, filePath, content, exported) {
  const symbols = [];

  if (node.type === "FunctionDeclaration") {
    const sig = buildFunctionSignature(node, content);
    symbols.push(
      makeSymbol(filePath, content, node.id?.name || "<anonymous>", "function", node.start, node.end, sig, {
        is_exported: exported,
      })
    );
  } else if (node.type === "ClassDeclaration") {
    const sig = buildClassSignature(node);
    symbols.push(
      makeSymbol(filePath, content, node.id?.name || "<anonymous>", "class", node.start, node.end, sig, {
        is_exported: exported,
      })
    );
  } else if (node.type === "VariableDeclaration") {
    for (const decl of node.declarations) {
      if (decl.init && (decl.init.type === "ArrowFunctionExpression" || decl.init.type === "FunctionExpression")) {
        const sig = buildArrowSignature(node, decl, filePath, content);
        symbols.push(
          makeSymbol(filePath, content, decl.id?.name || "<anonymous>", "function", node.start, node.end, sig, {
            is_exported: exported,
          })
        );
      } else {
        // 普通变量
        symbols.push(
          makeSymbol(filePath, content, decl.id?.name || "<anonymous>", "variable", node.start, node.end, "", {
            is_exported: exported,
          })
        );
      }
    }
  } else if (node.type === "TSTypeAliasDeclaration") {
    symbols.push(
      makeSymbol(filePath, content, node.id?.name || "<anonymous>", "type_alias", node.start, node.end, "", {
        is_exported: exported,
      })
    );
  } else if (node.type === "TSInterfaceDeclaration") {
    symbols.push(
      makeSymbol(filePath, content, node.id?.name || "<anonymous>", "interface", node.start, node.end, "", {
        is_exported: exported,
      })
    );
  }

  return symbols;
}

function buildFunctionSignature(node, content) {
  const name = node.id?.name || "<anonymous>";
  const params = node.params.map((p) => content.slice(p.start, p.end)).join(", ");
  const isAsync = node.async ? "async " : "";
  return `${isAsync}function ${name}(${params})`;
}

function buildClassSignature(node) {
  const name = node.id?.name || "<anonymous>";
  const extendsClause = node.superClass
    ? ` extends ${node.superClass.name || "..."}`
    : "";
  return `class ${name}${extendsClause}`;
}

function buildArrowSignature(node, decl, filePath, content) {
  const name = decl.id?.name || "<anonymous>";
  const isAsync = decl.init?.async ? "async " : "";
  const params = decl.init?.params
    ? decl.init.params.map((p) => content.slice(p.start, p.end)).join(", ")
    : "";
  return `${isAsync}${name} = (${params}) =>`;
}

// ── 主提取函数 ───────────────────────────────────────────

function extractStructure(filePath, content, language) {
  const symbols = [];
  const imports = [];
  const exports = [];
  const errors = [];

  const plugins = getPlugins(language);

  let ast;
  try {
    ast = parser.parse(content, {
      sourceType: "unambiguous",
      plugins,
      errorRecovery: true, // 部分语法错误不中断解析
      allowImportExportEverywhere: false,
      allowReturnOutsideFunction: false,
      allowSuperOutsideMethod: false,
      allowUndeclaredExports: false,
    });
  } catch (e) {
    errors.push(`Parse error: ${e.message}`);
    return { symbols, imports, exports, errors };
  }

  // 遍历 AST 顶层节点
  for (const node of ast.program.body) {
    try {
      switch (node.type) {
        // ── Import ──
        case "ImportDeclaration": {
          const source = node.source?.value || "";
          const specifiers = extractSpecifiers(node.specifiers || []);
          const raw = content.slice(node.start, node.end).trim();
          imports.push({
            raw,
            source,
            specifiers,
            line: getLine(content, node.start),
          });

          // 将 import 本身也记录为 symbol
          symbols.push(
            makeSymbol(filePath, content, source, "import", node.start, node.end, raw, {
              is_exported: false,
            })
          );
          break;
        }

        // ── Export Named ──
        case "ExportNamedDeclaration":
          // export { X } from 'module' — re-export
          if (node.source) {
            const source = node.source.value;
            const specifiers = extractExportSpecifiers(node.specifiers || []);
            const raw = content.slice(node.start, node.end).trim();
            imports.push({
              raw,
              source,
              specifiers: specifiers.map((s) => ({ imported: s.local, local: s.exported })),
              line: getLine(content, node.start),
              kind: "re_export",
            });
            symbols.push(
              makeSymbol(filePath, content, source, "import", node.start, node.end, raw, {
                is_exported: true,
              })
            );
          }

          // export const X / export function X / export class X
          if (node.declaration) {
            symbols.push(
              ...extractDeclaration(node.declaration, filePath, content, true)
            );
          }

          // export { X, Y }
          if (node.specifiers && !node.source) {
            for (const s of node.specifiers) {
              const exportedName = s.exported?.name || s.local?.name || "";
              exports.push({
                exported: exportedName,
                local: s.local?.name || "",
                line: getLine(content, node.start),
              });
            }
          }
          break;

        // ── Export Default ──
        case "ExportDefaultDeclaration":
          if (node.declaration) {
            // export default function / class / expression
            if (
              node.declaration.type === "FunctionDeclaration" ||
              node.declaration.type === "ClassDeclaration"
            ) {
              symbols.push(
                ...extractDeclaration(node.declaration, filePath, content, true)
              );
            } else {
              // export default <expression>
              const raw = content.slice(node.start, node.end).split("\n")[0].trim();
              symbols.push(
                makeSymbol(filePath, content, "default", "export", node.start, node.end, raw, {
                  is_exported: true,
                })
              );
            }
          }
          break;

        // ── Function ──
        case "FunctionDeclaration":
          symbols.push(
            ...extractDeclaration(node, filePath, content, false)
          );
          break;

        // ── Class ──
        case "ClassDeclaration":
          symbols.push(
            ...extractDeclaration(node, filePath, content, false)
          );
          break;

        // ── Variable ──
        case "VariableDeclaration":
          symbols.push(
            ...extractDeclaration(node, filePath, content, false)
          );
          break;

        // ── TS Type Alias ──
        case "TSTypeAliasDeclaration":
          symbols.push(
            ...extractDeclaration(node, filePath, content, false)
          );
          break;

        // ── TS Interface ──
        case "TSInterfaceDeclaration":
          symbols.push(
            ...extractDeclaration(node, filePath, content, false)
          );
          break;

        default:
          // 跳过其他顶层节点类型
          break;
      }
    } catch (innerError) {
      errors.push(`Error extracting node type=${node.type}: ${innerError.message}`);
    }
  }

  return { symbols, imports, exports, errors };
}

// ── JSONL 批处理模式 ─────────────────────────────────────

function runBatchMode() {
  const readline = require("readline");
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false,
  });

  rl.on("line", (line) => {
    if (!line.trim()) return;

    let req;
    try {
      req = JSON.parse(line);
    } catch (e) {
      process.stderr.write(`JSON parse error: ${e.message}\n`);
      return;
    }

    const { id, file_path, content, language } = req;
    const result = extractStructure(file_path || "", content || "", language || "typescript");
    result.id = id || "";

    process.stdout.write(JSON.stringify(result) + "\n");
  });

  rl.on("close", () => {
    process.exit(0);
  });

  process.stderr.write("node_bridge: batch mode ready\n");
}

// ── 单次模式（直接读取 stdin 到 EOF）─────────────────────

function runSingleMode() {
  let data = "";
  process.stdin.setEncoding("utf-8");
  process.stdin.on("data", (chunk) => {
    data += chunk;
  });
  process.stdin.on("end", () => {
    if (!data.trim()) {
      process.exit(0);
    }
    try {
      const req = JSON.parse(data);
      const result = extractStructure(
        req.file_path || "",
        req.content || "",
        req.language || "typescript"
      );
      result.id = req.id || "";
      process.stdout.write(JSON.stringify(result) + "\n");
    } catch (e) {
      process.stderr.write(`Error: ${e.message}\n`);
      process.exit(1);
    }
  });
}

// ── 入口 ──────────────────────────────────────────────────

if (process.argv.includes("--batch")) {
  runBatchMode();
} else {
  runSingleMode();
}
