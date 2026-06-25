"""
gate.check CLI end-to-end acceptance tests.

These tests exercise the path an external agent would use before apply:
write an authorized_scope.json, write a gate request JSON, then call
`python -m smartdev gate check` through the real CLI.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.test_cli import _run_cli


def _write_authorized_scope(project_path: Path, run_id: str, allowed_paths: list[str]) -> None:
    target = project_path / ".smartdev" / "runs" / run_id / "authorized_scope.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({
            "schema_version": "authorized-scope.v1",
            "run_id": run_id,
            "issued_by": "human",
            "allowed_paths": allowed_paths,
            "disallowed_paths": [],
            "risk_level": "R2",
        }),
        encoding="utf-8",
    )


def _request(
    changed_files: list[dict],
    *,
    run_id: str | None,
    allowed_paths: list[str],
) -> dict:
    request = {
        "contract_version": "2026-06-25.v1",
        "task_scope": {
            "description": "CLI e2e gate check",
            "authority": "agent-self-report-ignored",
            "allowed_paths": allowed_paths,
            "disallowed_paths": [],
            "allowed_change_types": ["modify", "create", "delete", "create_test"],
            "risk_level": "R2",
        },
        "change": {"changed_files": changed_files},
        "options": {"policy_profile": "conservative", "emit_handoff": False},
    }
    if run_id is not None:
        request["run_id"] = run_id
    return request


def _run_gate(project_path: Path, request: dict):
    request_path = project_path / "gate-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    result = _run_cli(
        "gate", "check",
        "--project", str(project_path),
        "--request-json", str(request_path),
    )
    data = json.loads(result.stdout)
    return result, data


def _finding(data: dict, rule_id: str) -> dict | None:
    return next((item for item in data["findings"] if item["rule_id"] == rule_id), None)


def test_gate_cli_e2e_allows_anchored_authorized_change(tmp_path: Path):
    _write_authorized_scope(tmp_path, "e2e-gate-001", ["src/a.py"])

    result, data = _run_gate(
        tmp_path,
        _request(
            [{"path": "src/a.py", "change_type": "create"}],
            run_id="e2e-gate-001",
            allowed_paths=["src/a.py"],
        ),
    )

    assert result.returncode == 0
    assert data["verdict"] == "allow"
    assert data["authority"]["status"] == "anchored"
    assert data["authority"]["source"] == ".smartdev/runs/e2e-gate-001/authorized_scope.json"


def test_gate_cli_e2e_blocks_anchored_unlisted_change_with_machine_action(tmp_path: Path):
    _write_authorized_scope(tmp_path, "e2e-gate-002", ["src/a.py"])

    result, data = _run_gate(
        tmp_path,
        _request(
            [{"path": "src/b.py", "change_type": "create"}],
            run_id="e2e-gate-002",
            allowed_paths=["src/a.py"],
        ),
    )

    assert result.returncode == 1
    assert data["verdict"] == "block"
    finding = _finding(data, "scope.unlisted_file_modified")
    assert finding is not None
    assert finding["severity"] == "block"
    assert finding["machine_action"] == "remove_file_from_patch"
    assert finding["evidence"]["authority_status"] == "anchored"


def test_gate_cli_e2e_blocks_authorized_scope_tampering(tmp_path: Path):
    _write_authorized_scope(tmp_path, "e2e-gate-003", [".smartdev/**"])

    result, data = _run_gate(
        tmp_path,
        _request(
            [{
                "path": ".smartdev/runs/e2e-gate-003/authorized_scope.json",
                "change_type": "create",
            }],
            run_id="e2e-gate-003",
            allowed_paths=[".smartdev/**"],
        ),
    )

    assert result.returncode == 1
    assert data["verdict"] == "block"
    finding = _finding(data, "path.protected_modified")
    assert finding is not None
    assert finding["severity"] == "block"
    assert finding["machine_action"] == "remove_file_from_patch"


def test_gate_cli_e2e_warns_without_anchored_authority(tmp_path: Path):
    result, data = _run_gate(
        tmp_path,
        _request(
            [{"path": "src/b.py", "change_type": "create"}],
            run_id=None,
            allowed_paths=["src/a.py"],
        ),
    )

    assert result.returncode == 0
    assert data["verdict"] == "warn"
    assert data["authority"]["status"] == "unverified"
    assert _finding(data, "scope.authority_unverified") is not None
    scope = _finding(data, "scope.unlisted_file_modified")
    assert scope is not None
    assert scope["severity"] == "warn"
