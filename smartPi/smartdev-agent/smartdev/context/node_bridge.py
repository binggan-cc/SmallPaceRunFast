"""
SmartDev Agent — Node Bridge Python 适配层

设计原理：
─────────
Phase 6.3 Step 1 创建了独立的 Node bridge（node_bridge/extract_structure.js），
基于 @babel/parser 提供 JS/TS/JSX/TSX 高置信度结构提取。

Step 2 提供 Python 侧的集成层：
- NodeBridgeProcess: 管理长期 Node 子进程，JSONL 协议通信
- NodeBridgeExtractor: 实现 StructureExtractorProvider 接口
- 单例模式：Node 进程启动一次，所有文件复用

关键设计决策：
1. Node 进程单例 — 避免每个文件启动一个新进程（省 80%+ 开销）
2. atexit 清理 — 确保 Python 退出时 Node 子进程也被关闭
3. 三层 fallback — Node 不可用 / bridge 启动失败 / 单文件超时
4. 零 Python 依赖 — 只用标准库 subprocess + select

对应文档：
- phase-6.3-design.md §3.1（Node Bridge 协议）
- phase-6.3-design.md §3.2（Node 进程复用设计）
- phase-6.3-design.md §3.6（Python 侧 NodeBridgeExtractor）
"""

from __future__ import annotations

import atexit
import json
import select
import shutil
import subprocess
import sys
from pathlib import Path

from smartdev.context.structure_extractor import (
    CodeSymbol,
    StructureExtractionResult,
    StructureExtractorProvider,
)

# ── 常量 ──────────────────────────────────────────────────

_BRIDGE_SCRIPT = Path(__file__).parent / "node_bridge" / "extract_structure.js"
_DEFAULT_TIMEOUT = 3.0  # 秒


def is_node_available() -> bool:
    """检测 Node.js 是否可用

    用于 Provider 注册前的判断。不抛异常。
    """
    return shutil.which("node") is not None


# ── NodeBridgeProcess（单例子进程管理）──────────────────────

_node_bridge_instance: NodeBridgeProcess | None = None


def get_node_bridge(timeout: float = _DEFAULT_TIMEOUT) -> NodeBridgeProcess | None:
    """获取全局唯一的 NodeBridgeProcess 实例

    线程安全：不保证（SmartDev 当前为单线程）。
    如果 Node 不可用或启动失败，返回 None。
    """
    global _node_bridge_instance
    if _node_bridge_instance is None:
        try:
            _node_bridge_instance = NodeBridgeProcess(timeout=timeout)
        except Exception:
            return None
    return _node_bridge_instance


def _cleanup_node_bridge() -> None:
    """atexit 回调：清理 Node 子进程"""
    global _node_bridge_instance
    if _node_bridge_instance is not None:
        try:
            _node_bridge_instance.close()
        except Exception:
            pass
        _node_bridge_instance = None


atexit.register(_cleanup_node_bridge)


class NodeBridgeProcess:
    """管理一个长期运行的 Node 子进程

    JSONL 协议：每行一个请求/响应。
    - stdin:  write JSON request lines
    - stdout: read JSON response lines
    - stderr: debug 信息（不解析）

    故障恢复：
    - 写入失败（BrokenPipe）→ 自动重启进程
    - 读取超时（select timeout）→ 返回 None
    - 进程崩溃 → 自动重启

    使用示例：
        bridge = NodeBridgeProcess(timeout=3.0)
        result = bridge.extract("src/App.tsx", content, "typescript")
        bridge.close()
    """

    def __init__(self, timeout: float = _DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._start()

    def _start(self) -> None:
        """启动 Node 子进程"""
        if not _BRIDGE_SCRIPT.exists():
            raise FileNotFoundError(
                f"Node bridge script not found: {_BRIDGE_SCRIPT}\n"
                f"Run: cd {_BRIDGE_SCRIPT.parent} && npm install"
            )
        self._proc = subprocess.Popen(
            ["node", str(_BRIDGE_SCRIPT), "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # 行缓冲
        )

    def _restart(self) -> None:
        """重启 Node 子进程（用于崩溃恢复）"""
        if self._proc is not None:
            try:
                self._proc.stdin.close()
                self._proc.stdout.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=1)
            except (subprocess.TimeoutExpired, Exception):
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._start()

    def extract(
        self, file_path: str, content: str, language: str
    ) -> dict | None:
        """发送单文件提取请求

        参数：
            file_path: 文件路径
            content: 文件内容
            language: 语言标识（javascript/typescript）

        返回：
            dict: 解析结果，包含 symbols/imports/exports/errors
            None: 超时或进程失败
        """
        if self._proc is None:
            return None

        request = json.dumps({
            "id": "req",
            "file_path": file_path,
            "content": content,
            "language": language,
        })

        # 写入请求
        try:
            self._proc.stdin.write(request + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError):
            # 进程崩溃 → 重启后重试一次
            try:
                self._restart()
                self._proc.stdin.write(request + "\n")
                self._proc.stdin.flush()
            except Exception:
                return None

        # 读取响应（带超时）
        try:
            ready, _, _ = select.select(
                [self._proc.stdout], [], [], self.timeout
            )
        except (ValueError, OSError):
            return None

        if not ready:
            # 超时：返回 None，由调用方决定 fallback
            return None

        try:
            line = self._proc.stdout.readline()
        except Exception:
            return None

        if not line or not line.strip():
            return None

        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def close(self) -> None:
        """关闭 Node 子进程"""
        if self._proc is not None:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.stdout.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None


# ── NodeBridgeExtractor ────────────────────────────────────

class NodeBridgeExtractor(StructureExtractorProvider):
    """Node + Babel Parser 提取器

    通过 Node 子进程调用 @babel/parser，实现 JS/TS/JSX/TSX 高置信度解析。

    confidence = 0.95
    extractor = node_bridge_babel

    三层 fallback：
    1. Node 不可用 → 不注册此 Provider（由 structure_extractor.py 处理）
    2. Bridge 启动/通信失败 → extract() 返回空结果 + error
    3. 单文件超时 → 返回空结果，不中断索引

    注意：
    - 此 Provider 不持有 NodeBridgeProcess 的引用（使用全局单例）
    - 多次 extract() 调用共享同一个 Node 进程
    """

    @property
    def name(self) -> str:
        return "node_bridge_babel"

    @property
    def supported_languages(self) -> list[str]:
        return ["javascript", "typescript"]

    def extract(self, file_path: str, content: str) -> StructureExtractionResult:
        """使用 Node bridge 提取文件结构

        失败时返回空结果（不抛异常），由上游决定如何处理。
        """
        bridge = get_node_bridge()
        if bridge is None:
            return StructureExtractionResult(
                symbols=[],
                imports=[],
                errors=["Node bridge not available (node not found or startup failed)"],
            )

        # 根据文件后缀确定 language 参数
        suffix = Path(file_path).suffix.lower()
        if suffix in (".ts", ".tsx"):
            language = "typescript"
        else:
            language = "javascript"

        result = bridge.extract(file_path, content, language)
        if result is None:
            return StructureExtractionResult(
                symbols=[],
                imports=[],
                errors=[f"Node bridge timeout or communication failure for {file_path}"],
            )

        return _convert_node_result(result, file_path)


def _convert_node_result(
    result: dict, file_path: str
) -> StructureExtractionResult:
    """将 Node bridge JSON 输出转换为 Python StructureExtractionResult

    映射关系：
    - result.symbols[] → CodeSymbol（字段一一对应）
    - result.imports[] → imports（取 raw 字段作为字符串）
    - result.errors[] → errors

    注意：imports 当前以 raw 字符串形式传递，
    结构化 specifiers 在 Phase 6.3 Step 4（JS/TS import relations）中使用。
    """
    symbols: list[CodeSymbol] = []
    imports: list[str] = []
    errors: list[str] = []

    for s in result.get("symbols", []):
        symbols.append(CodeSymbol(
            name=s.get("name", ""),
            kind=s.get("kind", ""),
            file_path=s.get("file_path", file_path),
            start_line=s.get("start_line", 0),
            end_line=s.get("end_line", 0),
            signature=s.get("signature", ""),
            parent=s.get("parent", ""),
            is_exported=s.get("is_exported", False),
            confidence=s.get("confidence", 0.95),
            extractor=s.get("extractor", "node_bridge_babel"),
            limitations=s.get("limitations", []),
        ))

    for imp in result.get("imports", []):
        if isinstance(imp, dict):
            imports.append(imp.get("raw", str(imp)))
        else:
            imports.append(str(imp))

    errors.extend(result.get("errors", []))

    return StructureExtractionResult(
        symbols=symbols,
        imports=imports,
        errors=errors,
    )
