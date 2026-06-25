"""
gate.check Scope Authority tests.

These tests lock the anchored-authority model:
the reviewed agent may declare scope, but only a gate-read
authorized_scope.json can anchor the effective scope.
"""

from __future__ import annotations

import json
from pathlib import Path


def _request(
    changed_files,
    *,
    run_id: str | None = None,
    allowed_paths=None,
    disallowed_paths=None,
    declared_authority: str | None = None,
):
    task_scope = {
        "description": "authority test",
        "allowed_paths": allowed_paths if allowed_paths is not None else ["src/**"],
        "disallowed_paths": disallowed_paths if disallowed_paths is not None else [],
        "allowed_change_types": ["modify", "create", "delete", "create_test"],
        "risk_level": "R2",
    }
    if declared_authority is not None:
        task_scope["authority"] = declared_authority

    request = {
        "contract_version": "2026-06-25.v1",
        "task_scope": task_scope,
        "change": {"changed_files": changed_files},
        "options": {"policy_profile": "conservative", "emit_handoff": False},
    }
    if run_id is not None:
        request["run_id"] = run_id
    return request


def _write_authorized_scope(
    project_path: Path,
    run_id: str,
    *,
    allowed_paths,
    disallowed_paths=None,
) -> Path:
    path = project_path / ".smartdev" / "runs" / run_id / "authorized_scope.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "source": "human",
            "description": "anchored authority fixture",
            "allowed_paths": allowed_paths,
            "disallowed_paths": disallowed_paths if disallowed_paths is not None else [],
            "risk_level": "R2",
        }),
        encoding="utf-8",
    )
    return path


def _finding(result, rule_id):
    return next((f for f in result["findings"] if f["rule_id"] == rule_id), None)


def test_missing_run_id_marks_authority_unverified_and_scope_cannot_block(tmp_path: Path):
    from smartdev.core.gate import gate_check

    result = gate_check(
        tmp_path,
        _request(
            [{"path": "src/b.py", "change_type": "create"}],
            allowed_paths=["src/a.py"],
        ),
    )

    assert result["verdict"] == "warn"
    assert result["authority"]["status"] == "unverified"
    authority = _finding(result, "scope.authority_unverified")
    assert authority["severity"] == "warn"

    scope = _finding(result, "scope.unlisted_file_modified")
    assert scope["severity"] == "warn"
    assert scope["evidence"]["authority_status"] == "unverified"


def test_self_asserted_human_authority_is_only_an_audit_label(tmp_path: Path):
    from smartdev.core.gate import gate_check

    result = gate_check(
        tmp_path,
        _request(
            [{"path": "src/b.py", "change_type": "create"}],
            allowed_paths=["src/a.py"],
            declared_authority="human",
        ),
    )

    assert result["verdict"] == "warn"
    assert result["authority"]["status"] == "unverified"
    assert result["authority"]["declared_authority"] == "human"
    assert _finding(result, "scope.authority_unverified") is not None


def test_anchored_scope_unlisted_file_can_block(tmp_path: Path):
    from smartdev.core.gate import gate_check

    _write_authorized_scope(tmp_path, "run-1", allowed_paths=["src/a.py"])

    result = gate_check(
        tmp_path,
        _request(
            [{"path": "src/b.py", "change_type": "create"}],
            run_id="run-1",
            allowed_paths=["src/a.py"],
        ),
    )

    assert result["verdict"] == "block"
    assert result["authority"]["status"] == "anchored"
    scope = _finding(result, "scope.unlisted_file_modified")
    assert scope["severity"] == "block"
    assert scope["evidence"]["authority_status"] == "anchored"


def test_declared_scope_exceeding_authorized_scope_warns(tmp_path: Path):
    from smartdev.core.gate import gate_check

    _write_authorized_scope(tmp_path, "run-2", allowed_paths=["src/**"])

    result = gate_check(
        tmp_path,
        _request(
            [{"path": "src/a.py", "change_type": "create"}],
            run_id="run-2",
            allowed_paths=["src/**", "docs/**"],
        ),
    )

    assert result["verdict"] == "warn"
    finding = _finding(result, "scope.declared_exceeds_authorized")
    assert finding["severity"] == "warn"
    assert finding["evidence"]["declared_only_patterns"] == ["docs/**"]


def test_broad_declared_scope_excess_is_not_suppressed_by_blocked_file(tmp_path: Path):
    from smartdev.core.gate import gate_check

    _write_authorized_scope(tmp_path, "run-broad", allowed_paths=["src/a.py"])

    result = gate_check(
        tmp_path,
        _request(
            [{"path": "src/b.py", "change_type": "create"}],
            run_id="run-broad",
            allowed_paths=["src/**"],
        ),
    )

    assert result["verdict"] == "block"
    assert _finding(result, "scope.unlisted_file_modified")["severity"] == "block"
    declared = _finding(result, "scope.declared_exceeds_authorized")
    assert declared is not None
    assert declared["severity"] == "warn"
    assert declared["evidence"]["declared_only_patterns"] == ["src/**"]


def test_inputs_digest_excludes_authorized_scope_snapshot(tmp_path: Path):
    from smartdev.core.gate import gate_check

    request = _request(
        [{"path": "src/a.py", "change_type": "create"}],
        run_id="run-3",
        allowed_paths=["src/**"],
    )
    _write_authorized_scope(tmp_path, "run-3", allowed_paths=["src/**"])
    first = gate_check(tmp_path, request)

    _write_authorized_scope(tmp_path, "run-3", allowed_paths=["app/**"])
    second = gate_check(tmp_path, request)

    assert first["inputs_digest"] == second["inputs_digest"]
    assert first["authority"]["authorized_scope_digest"] != second["authority"]["authorized_scope_digest"]
    assert first["authority"]["authorized_scope_snapshot"]["allowed_paths"] == ["src/**"]
    assert second["authority"]["authorized_scope_snapshot"]["allowed_paths"] == ["app/**"]


def test_authorized_scope_file_is_protected_even_when_declared_allowed(tmp_path: Path):
    from smartdev.core.gate import gate_check

    result = gate_check(
        tmp_path,
        _request(
            [{
                "path": ".smartdev/runs/run-4/authorized_scope.json",
                "change_type": "create",
            }],
            allowed_paths=[".smartdev/**"],
        ),
    )

    assert result["verdict"] == "block"
    finding = _finding(result, "path.protected_modified")
    assert finding["severity"] == "block"
    assert finding["evidence"]["matched_pattern"] == ".smartdev/runs/**/authorized_scope.json"
