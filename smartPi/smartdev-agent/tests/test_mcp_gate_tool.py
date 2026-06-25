"""
MCP gate.check tool tests.

The MCP layer should expose the core gate.check contract without weakening
the policy invariants.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("mcp")


def _parse(text_content) -> dict:
    return json.loads(text_content[0].text)


def _gate_request(changed_files, *, allowed_paths=None, disallowed_paths=None, run_id=None):
    request = {
        "contract_version": "2026-06-25.v1",
        "task_scope": {
            "description": "MCP gate test",
            "allowed_paths": allowed_paths if allowed_paths is not None else ["src/**"],
            "disallowed_paths": disallowed_paths if disallowed_paths is not None else [],
            "allowed_change_types": ["modify", "create", "delete", "create_test"],
            "risk_level": "R2",
        },
        "change": {"changed_files": changed_files},
        "options": {"policy_profile": "conservative", "emit_handoff": False},
    }
    if run_id is not None:
        request["run_id"] = run_id
    return request


def _write_authorized_scope(project_path: Path, run_id: str, allowed_paths):
    target = project_path / ".smartdev" / "runs" / run_id / "authorized_scope.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({
            "source": "human",
            "description": "MCP gate authority",
            "allowed_paths": allowed_paths,
            "disallowed_paths": [],
            "risk_level": "R2",
        }),
        encoding="utf-8",
    )


class TestMcpGateToolRegistered:
    @pytest.mark.asyncio
    async def test_gate_tool_in_version_and_list_tools(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_list_tools, handle_version

        version = _parse(await handle_version({}, tmp_path))
        listed = _parse(await handle_list_tools({}, tmp_path))

        version_names = {t["name"] for t in version["data"]["tools"]}
        listed_names = {t["name"] for t in listed["data"]["available_tools"]}
        assert "smartdev_gate_check" in version_names
        assert "smartdev_gate_check" in listed_names

    def test_gate_tool_in_server_schema_and_handlers(self):
        import inspect
        from smartdev.mcp import server as srv

        src = inspect.getsource(srv.create_server)
        assert 'name="smartdev_gate_check"' in src or "name='smartdev_gate_check'" in src
        assert '"smartdev_gate_check"' in src
        gate_start = src.index('name="smartdev_gate_check"')
        gate_end = src.index("# Phase 11D Step 7", gate_start)
        gate_schema = src[gate_start:gate_end]
        assert '"contract_version"' in gate_schema
        assert '"task_scope"' in gate_schema
        assert '"change"' in gate_schema
        # Do not enforce required at MCP schema level: malformed inputs must
        # reach handle_gate_check so core can return structured warn findings.
        assert '"required": []' in gate_schema
        assert '"smartdev_gate_check":      t.handle_gate_check' in src

    def test_gate_tool_registry_schema_contract_do_not_drift(self):
        import inspect
        from smartdev.mcp import server as srv
        from smartdev.mcp.tools import get_available_tools

        registry_entry = next(
            tool for tool in get_available_tools()
            if tool["name"] == "smartdev_gate_check"
        )
        assert registry_entry["permission"] == "READ"
        assert registry_entry["status"] == "available"

        src = inspect.getsource(srv.create_server)
        gate_start = src.index('name="smartdev_gate_check"')
        gate_end = src.index("# Phase 11D Step 7", gate_start)
        gate_schema = src[gate_start:gate_end]
        semantic_fields = {
            "contract_version",
            "task_scope",
            "change",
            "index_evidence",
            "options",
            "request",
        }
        for field in semantic_fields:
            assert f'"{field}"' in gate_schema
        assert '"required": []' in gate_schema


class TestMcpGateToolHandler:
    @pytest.mark.asyncio
    async def test_gate_check_returns_contract_output_inside_data(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_gate_check

        _write_authorized_scope(tmp_path, "mcp-run", ["src/**"])

        result = await handle_gate_check(
            _gate_request(
                [{"path": "lib/outside.py", "change_type": "modify"}],
                allowed_paths=["src/**"],
                run_id="mcp-run",
            ),
            tmp_path,
        )

        data = _parse(result)
        assert data["ok"] is True
        assert data["tool"] == "smartdev_gate_check"
        assert data["data"]["verdict"] == "block"
        assert data["data"]["contract_version"] == "2026-06-25.v1"
        assert data["data"]["policy_version"] == "scope-gate.v1"
        assert data["data"]["inputs_digest"].startswith("sha256:")
        assert any(
            f["rule_id"] == "scope.unlisted_file_modified"
            and f["severity"] == "block"
            for f in data["data"]["findings"]
        )

    @pytest.mark.asyncio
    async def test_gate_check_accepts_request_wrapper(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_gate_check

        result = await handle_gate_check(
            {"request": _gate_request([
                {"path": "pyproject.toml", "change_type": "modify"}
            ])},
            tmp_path,
        )

        data = _parse(result)
        assert data["ok"] is True
        assert data["data"]["verdict"] == "warn"
        assert any(
            f["rule_id"] == "deps.manifest_changed_without_scope"
            and f["severity"] == "warn"
            for f in data["data"]["findings"]
        )

    @pytest.mark.asyncio
    async def test_gate_check_missing_contract_version_returns_warn_response(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_gate_check

        result = await handle_gate_check({"change": {"changed_files": []}}, tmp_path)
        data = _parse(result)

        assert data["ok"] is True
        assert data["data"]["verdict"] == "warn"
        assert any(
            f["rule_id"] == "gate.contract_version_missing"
            and f["severity"] == "warn"
            for f in data["data"]["findings"]
        )

    @pytest.mark.asyncio
    async def test_gate_check_missing_changed_files_returns_malformed_warning(self, tmp_path: Path):
        from smartdev.mcp.tools import handle_gate_check

        result = await handle_gate_check(
            {
                "contract_version": "2026-06-25.v1",
                "task_scope": {
                    "description": "malformed",
                    "allowed_paths": ["src/**"],
                    "disallowed_paths": [],
                    "risk_level": "R2",
                },
                "change": {},
            },
            tmp_path,
        )
        data = _parse(result)

        assert data["ok"] is True
        assert data["data"]["verdict"] == "warn"
        assert data["data"]["gate_error"] is True
        assert any(
            f["rule_id"] == "gate.malformed_request"
            and f["severity"] == "warn"
            for f in data["data"]["findings"]
        )
