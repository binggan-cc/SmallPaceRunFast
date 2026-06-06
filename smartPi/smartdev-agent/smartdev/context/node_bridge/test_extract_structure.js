#!/usr/bin/env node
/**
 * SmartDev Agent — Node Bridge 测试
 *
 * 覆盖 6 个场景（Phase 6.3 Step 1 最小验证集）：
 *   1. import React from "react"
 *   2. import { useState as useReactState } from "react"
 *   3. export function foo() {}
 *   4. export default class App {}
 *   5. const Button = () => {}
 *   6. TSX function component
 *
 * 运行：node test_extract_structure.js
 * 结果：pass/fail 计数，非零退出码表示有失败
 */

const { spawn } = require("child_process");
const path = require("path");

const BRIDGE_SCRIPT = path.join(__dirname, "extract_structure.js");

const TEST_CASES = [
  {
    name: "1. import React from 'react'",
    input: {
      id: "test-1",
      file_path: "src/App.js",
      language: "javascript",
      content: `import React from 'react';\n`,
    },
    expect: (result) => {
      const hasImport = result.imports.some(
        (i) => i.source === "react"
      );
      const hasSpecifier = result.imports.some(
        (i) => i.specifiers && i.specifiers.some((s) => s.imported === "default" && s.local === "React")
      );
      return hasImport && hasSpecifier && result.errors.length === 0;
    },
  },
  {
    name: "2. import { useState as useReactState } from 'react'",
    input: {
      id: "test-2",
      file_path: "src/hooks.ts",
      language: "typescript",
      content: `import { useState as useReactState } from 'react';\n`,
    },
    expect: (result) => {
      const hasAlias = result.imports.some((i) => {
        return (
          i.source === "react" &&
          i.specifiers &&
          i.specifiers.some(
            (s) => s.imported === "useState" && s.local === "useReactState"
          )
        );
      });
      return hasAlias && result.errors.length === 0;
    },
  },
  {
    name: "3. export function foo() {}",
    input: {
      id: "test-3",
      file_path: "src/utils.ts",
      language: "typescript",
      content: `export function foo() {\n  return 42;\n}\n`,
    },
    expect: (result) => {
      const hasFunc = result.symbols.some(
        (s) => s.name === "foo" && s.kind === "function" && s.is_exported === true
      );
      return hasFunc && result.errors.length === 0;
    },
  },
  {
    name: "4. export default class App {}",
    input: {
      id: "test-4",
      file_path: "src/App.js",
      language: "javascript",
      content: `export default class App {\n  render() {}\n}\n`,
    },
    expect: (result) => {
      const hasClass = result.symbols.some(
        (s) => s.name === "App" && s.kind === "class" && s.is_exported === true
      );
      return hasClass && result.errors.length === 0;
    },
  },
  {
    name: "5. const Button = () => {}",
    input: {
      id: "test-5",
      file_path: "src/Button.jsx",
      language: "javascript",
      content: `const Button = () => {\n  return <button>Click</button>;\n};\n`,
    },
    expect: (result) => {
      const hasArrow = result.symbols.some(
        (s) => s.name === "Button" && s.kind === "function"
      );
      return hasArrow && result.errors.length === 0;
    },
  },
  {
    name: "6. TSX function component",
    input: {
      id: "test-6",
      file_path: "src/Header.tsx",
      language: "typescript",
      content: `interface Props {\n  title: string;\n}\n\nexport const Header: React.FC<Props> = ({ title }) => {\n  return <h1>{title}</h1>;\n};\n`,
    },
    expect: (result) => {
      const hasHeader = result.symbols.some(
        (s) => s.name === "Header" && s.kind === "function" && s.is_exported === true
      );
      const hasInterface = result.symbols.some(
        (s) => s.name === "Props" && s.kind === "interface"
      );
      return hasHeader && hasInterface && result.errors.length === 0;
    },
  },
];

// ── 运行测试（通过 stdin/stdout 喂输入）─────────────────

function runTests() {
  let passed = 0;
  let failed = 0;

  const requests = TEST_CASES.map((tc) => JSON.stringify(tc.input)).join("\n") + "\n";

  const child = spawn("node", [BRIDGE_SCRIPT, "--batch"], {
    stdio: ["pipe", "pipe", "pipe"],
  });

  const responses = [];
  let responseCount = 0;

  child.stdout.on("data", (data) => {
    const lines = data.toString().split("\n").filter((l) => l.trim());
    for (const line of lines) {
      try {
        responses.push(JSON.parse(line));
        responseCount++;
      } catch (e) {
        console.error(`  FAIL: JSON parse error in response: ${e.message}`);
        failed++;
      }
    }
  });

  child.stderr.on("data", (data) => {
    // stderr 用于 debug，不标记为失败
    process.stderr.write(`  [bridge] ${data.toString().trim()}\n`);
  });

  child.on("close", (code) => {
    // 等待响应收集完成
    setTimeout(() => {
      console.log(`\nSmartDev Node Bridge Tests\n`);
      console.log(`Results: ${TEST_CASES.length} tests\n`);

      for (let i = 0; i < TEST_CASES.length; i++) {
        const tc = TEST_CASES[i];
        const response = responses.find((r) => r.id === tc.input.id);

        if (!response) {
          console.log(`  FAIL: ${tc.name} — no response`);
          failed++;
          continue;
        }

        try {
          if (tc.expect(response)) {
            console.log(`  PASS: ${tc.name}`);
            passed++;
          } else {
            console.log(`  FAIL: ${tc.name} — assertion failed`);
            console.log(`    symbols: ${JSON.stringify(response.symbols.map((s) => ({ name: s.name, kind: s.kind, is_exported: s.is_exported })))}`);
            console.log(`    imports: ${JSON.stringify(response.imports)}`);
            failed++;
          }
        } catch (e) {
          console.log(`  FAIL: ${tc.name} — ${e.message}`);
          failed++;
        }
      }

      console.log(`\n${passed} passed, ${failed} failed`);
      process.exit(failed > 0 ? 1 : 0);
    }, 100);
  });

  // 写入所有请求
  child.stdin.write(requests);
  child.stdin.end();
}

runTests();
