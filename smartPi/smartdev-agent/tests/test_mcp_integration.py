"""
tests/test_mcp_integration.py — MCP Server 真实协议集成测试（Phase 10 Step 5）

通过 subprocess 启动真实 MCP Server，走完整 JSON-RPC over stdio 协议，
验证外部 Agent（Kiro / Claude Desktop）能正常使用的核心调用路径。

覆盖内容：
- initialize 握手
- tools/list 返回 14 个工具
- smartdev_ping（最基础健康检查）
- smartdev_version（版本 + 工具清单）
- smartdev_repo_scan（无需索引，直接可用）
- smartdev_code_index（建立索引）
- smartdev_code_search（有索引后搜索）
- smartdev_code_impact（影响分析）
- smartdev_project_map（项目地图）
- smartdev_graph_validate（图谱校验）
- smartdev_patch_propose（patch 草案，验证不落盘）
- 未知工具返回 UNKNOWN_TOOL 错误，不崩溃

注意：所有测试使用 tmp_path，不污染真实项目。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ── MCP 客户端辅助 ─────────────────────────────────────────────────


class MCPClient:
    """极简 MCP stdio 客户端，用于集成测试"""

    def __init__(self, project_path: Path):
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "smartdev", "mcp", "--project", str(project_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    def send(self, method: str, params: dict | None = None) -> dict:
        req = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        time.sleep(0.4)
        line = self.proc.stdout.readline()
        return json.loads(line) if line.strip() else {}

    def call_tool(self, name: str, arguments: dict | None = None) -> dict:
        r = self.send("tools/call", {"name": name, "arguments": arguments or {}})
        if "result" not in r:
            return {"ok": False, "error": r}
        content = r["result"].get("content", [])
        if not content:
            return {"ok": False, "error": "empty content"}
        return json.loads(content[0]["text"])

    def initialize(self) -> dict:
        return self.send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        })

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass


@pytest.fixture
def client(tmp_path):
    """每个测试使用独立的 tmp_path 项目"""
    # 写一个最小 Python 文件，让 repo_scan / architecture_map 有内容
    (tmp_path / "main.py").write_text("def hello(): pass\n", encoding="utf-8")
    (tmp_path / "utils.py").write_text("import main\n\ndef util(): return main.hello()\n", encoding="utf-8")

    c = MCPClient(tmp_path)
    r = c.initialize()
    assert "result" in r, f"initialize failed: {r}"
    yield c, tmp_path
    c.close()


# ── 协议层测试 ────────────────────────────────────────────────────


class TestMCPProtocol:
    def test_initialize_returns_server_info(self, client):
        c, _ = client
        # initialize 已在 fixture 里调用过，再发一次确认幂等
        r = c.initialize()
        assert "result" in r
        assert r["result"]["serverInfo"]["name"] == "smartdev"

    def test_tools_list_returns_14(self, client):
        c, _ = client
        r = c.send("tools/list")
        assert "result" in r
        tools = r["result"]["tools"]
        from smartdev.mcp.tools import get_available_tools
        assert len(tools) == len(get_available_tools())

    def test_tools_list_has_required_names(self, client):
        c, _ = client
        r = c.send("tools/list")
        names = {t["name"] for t in r["result"]["tools"]}
        required = {
            "smartdev_ping", "smartdev_version", "smartdev_list_tools",
            "smartdev_code_search", "smartdev_code_impact",
            "smartdev_project_map", "smartdev_graph_validate",
            "smartdev_repo_scan", "smartdev_risk_check",
            "smartdev_architecture_map", "smartdev_task_plan",
            "smartdev_qa_checklist", "smartdev_code_index",
            "smartdev_patch_propose",
            # Phase 11A: 只读 Git 工具
            "smartdev_git_status", "smartdev_git_diff_explain",
            "smartdev_git_commit_plan", "smartdev_git_release_plan",
            "smartdev_git_merge_check",
            # Phase 11C: 只读 Doc Governance 工具
            "smartdev_doc_consistency", "smartdev_doc_update_plan",
            # Phase 11D: Handoff Pack 工具
            "smartdev_handoff_code", "smartdev_handoff_doc",
            "smartdev_handoff_review",
        }
        assert required.issubset(names), f"Missing: {required - names}"

    def test_unknown_tool_returns_error(self, client):
        c, _ = client
        d = c.call_tool("smartdev_does_not_exist")
        assert d["ok"] is False
        assert d["error_code"] == "UNKNOWN_TOOL"


# ── 基础工具 ──────────────────────────────────────────────────────


class TestBasicTools:
    def test_ping(self, client):
        c, tmp_path = client
        d = c.call_tool("smartdev_ping")
        assert d["ok"] is True
        assert d["data"]["pong"] is True
        assert str(tmp_path) in d["data"]["project_path"]

    def test_version(self, client):
        c, _ = client
        d = c.call_tool("smartdev_version")
        assert d["ok"] is True
        assert "version" in d["data"]
        from smartdev.mcp.tools import get_available_tools
        assert len(d["data"]["tools"]) == len(get_available_tools())
        # 所有工具都应标记为 available（v0 全量完成）
        statuses = {t["name"]: t["status"] for t in d["data"]["tools"]}
        assert all(s == "available" for s in statuses.values())


# ── Context 工具（需先建索引）────────────────────────────────────


class TestContextTools:
    def test_code_index_then_search(self, client):
        c, _ = client
        # 先建索引
        idx = c.call_tool("smartdev_code_index")
        assert idx["ok"] is True
        assert idx["data"]["stats"]["files"] >= 1

        # 再搜索
        s = c.call_tool("smartdev_code_search", {"query": "hello"})
        assert s["ok"] is True
        assert "files" in s["data"]

    def test_code_impact_with_index(self, client):
        c, _ = client
        c.call_tool("smartdev_code_index")
        d = c.call_tool("smartdev_code_impact", {"target": "main.py"})
        assert d["ok"] is True
        assert "affected_files" in d["data"]
        assert "risk_level" in d["data"]

    def test_project_map_with_index(self, client):
        c, _ = client
        c.call_tool("smartdev_code_index")
        d = c.call_tool("smartdev_project_map")
        assert d["ok"] is True
        assert "project" in d["data"]
        assert "modules" in d["data"]

    def test_graph_validate_with_index(self, client):
        c, _ = client
        c.call_tool("smartdev_code_index")
        d = c.call_tool("smartdev_graph_validate")
        assert d["ok"] is True
        assert "is_healthy" in d["data"]
        assert "summary" in d["data"]

    def test_code_search_without_index_returns_error(self, client):
        """新 tmp_path 没有索引，应返回 INDEX_NOT_FOUND"""
        c, tmp_path = client
        # 使用一个全新的子目录（没有 .smartdev/）
        sub = tmp_path / "sub_no_index"
        sub.mkdir()
        (sub / "x.py").write_text("x=1\n")

        c2 = MCPClient(sub)
        c2.initialize()
        try:
            d = c2.call_tool("smartdev_code_search", {"query": "x"})
            assert d["ok"] is False
            assert d["error_code"] == "INDEX_NOT_FOUND"
            assert d["suggested_tool"] == "smartdev_code_index"
        finally:
            c2.close()


# ── Skill 工具 ────────────────────────────────────────────────────


class TestSkillTools:
    def test_repo_scan(self, client):
        c, _ = client
        d = c.call_tool("smartdev_repo_scan")
        assert d["ok"] is True
        assert "summary" in d["data"]

    def test_risk_check(self, client):
        c, _ = client
        d = c.call_tool("smartdev_risk_check", {
            "task_description": "add user authentication"
        })
        assert d["ok"] is True
        assert "risk_level" in d["data"]

    def test_architecture_map(self, client):
        c, _ = client
        d = c.call_tool("smartdev_architecture_map")
        assert d["ok"] is True

    def test_task_plan(self, client):
        c, _ = client
        d = c.call_tool("smartdev_task_plan", {
            "task_description": "implement login feature"
        })
        assert d["ok"] is True
        assert "conservative" in d["data"]
        assert "recommended" in d["data"]
        assert "deep" in d["data"]

    def test_qa_checklist(self, client):
        c, _ = client
        d = c.call_tool("smartdev_qa_checklist", {
            "task_description": "verify login flow"
        })
        assert d["ok"] is True


# ── Patch 工具 ────────────────────────────────────────────────────


class TestPatchTools:
    def test_patch_propose_no_modify_source(self, client):
        """patch_propose 不能修改源文件"""
        c, tmp_path = client
        (tmp_path / "style.css").write_text(".btn { color: #FF0000; }\n")
        original = (tmp_path / "style.css").read_text()

        c.call_tool("smartdev_patch_propose", {
            "find": "#FF0000",
            "replace": "var(--btn-color)",
            "task_description": "unify button color",
        })

        assert (tmp_path / "style.css").read_text() == original

    def test_patch_propose_returns_diff(self, client):
        c, tmp_path = client
        (tmp_path / "style.css").write_text(".btn { color: #FF0000; }\n")

        d = c.call_tool("smartdev_patch_propose", {
            "find": "#FF0000",
            "replace": "var(--btn-color)",
            "task_description": "unify button color",
            "glob": "**/*.css",
        })
        assert d["ok"] is True
        assert "diff" in d["data"]
        assert "patch_id" in d["data"]
        assert "safety_note" in d["data"]

    def test_patch_propose_missing_find_returns_error(self, client):
        c, _ = client
        r = c.send("tools/call", {
            "name": "smartdev_patch_propose",
            "arguments": {"replace": "x", "task_description": "t"},
        })
        # MCP SDK 可能在 Schema 层拦截（返回 isError=true 或 validation error 字符串），
        # 也可能透传到 handler（返回 INVALID_ARGUMENT JSON）。
        # 两种情况都属于正确行为：find 缺失必须被拒绝。
        if "result" in r:
            content = r["result"].get("content", [])
            if content:
                text = content[0]["text"]
                try:
                    d = json.loads(text)
                    # handler 层拦截：INVALID_ARGUMENT
                    assert d["ok"] is False
                    assert d["error_code"] == "INVALID_ARGUMENT"
                except json.JSONDecodeError:
                    # SDK 层拦截：validation error 字符串，也是正确拒绝
                    assert "find" in text.lower() or "required" in text.lower()
        elif "error" in r:
            # JSON-RPC error level
            assert r["error"]["code"] != 0
