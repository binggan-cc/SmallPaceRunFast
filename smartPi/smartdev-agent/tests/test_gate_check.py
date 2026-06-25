"""
gate.check v1 contract tests.

These tests intentionally lock the "load-bearing wall":
rules report facts and confidence, while policy alone derives severity.
"""

from pathlib import Path

from smartdev.core.patch import compute_content_hash


def _request(
    changed_files,
    *,
    allowed_paths=None,
    disallowed_paths=None,
    contract_version="2026-06-25.v1",
    index_evidence=None,
):
    return {
        "contract_version": contract_version,
        "task_scope": {
            "description": "contract test",
            "allowed_paths": allowed_paths if allowed_paths is not None else ["src/**"],
            "disallowed_paths": disallowed_paths if disallowed_paths is not None else [],
            "allowed_change_types": ["modify", "create", "delete", "create_test"],
            "risk_level": "R2",
        },
        "change": {"changed_files": changed_files},
        "index_evidence": index_evidence or {},
        "options": {"policy_profile": "conservative", "emit_handoff": False},
    }


def _finding(result, rule_id):
    return next((f for f in result["findings"] if f["rule_id"] == rule_id), None)


def test_rule_findings_do_not_carry_severity():
    from smartdev.core.gate import RuleFinding

    finding = RuleFinding(
        rule_id="tests.insufficient_coverage",
        confidence="high",
        evidence={"reason": "synthetic"},
    )

    assert "severity" not in finding.to_dict()


def test_policy_is_the_only_place_that_can_block():
    from smartdev.core.gate import RuleFinding, apply_policy

    findings = apply_policy([
        RuleFinding(
            rule_id="tests.insufficient_coverage",
            confidence="high",
            evidence={"reason": "synthetic"},
        )
    ])

    assert findings[0].severity == "warn"


def test_deps_manifest_is_warn_only_even_with_high_confidence():
    from smartdev.core.gate import RuleFinding, apply_policy

    findings = apply_policy([
        RuleFinding(
            rule_id="deps.manifest_changed_without_scope",
            confidence="high",
            subject={"file": "pyproject.toml", "range": None},
            evidence={"manifest_file": "pyproject.toml", "in_allowed_paths": False},
        )
    ])

    assert findings[0].severity == "warn"


def test_scope_unlisted_file_blocks(tmp_path: Path):
    from smartdev.core.gate import gate_check

    result = gate_check(
        tmp_path,
        _request(
            [{"path": "src/a.py", "change_type": "modify"},
             {"path": "lib/b.py", "change_type": "modify"}],
            allowed_paths=["src/**"],
        ),
    )

    finding = _finding(result, "scope.unlisted_file_modified")
    assert result["verdict"] == "block"
    assert finding["severity"] == "block"
    assert finding["confidence"] == "high"
    assert finding["evidence"]["changed_file"] == "lib/b.py"


def test_dependency_manifest_outside_scope_warns_instead_of_blocking(tmp_path: Path):
    from smartdev.core.gate import gate_check

    result = gate_check(
        tmp_path,
        _request(
            [{"path": "pyproject.toml", "change_type": "modify"}],
            allowed_paths=["src/**"],
        ),
    )

    assert result["verdict"] == "warn"
    assert _finding(result, "scope.unlisted_file_modified") is None
    finding = _finding(result, "deps.manifest_changed_without_scope")
    assert finding["severity"] == "warn"
    assert finding["confidence"] == "high"


def test_protected_path_blocks(tmp_path: Path):
    from smartdev.core.gate import gate_check

    result = gate_check(
        tmp_path,
        _request(
            [{"path": ".smartdev/index.sqlite", "change_type": "modify"}],
            allowed_paths=["src/**"],
            disallowed_paths=[".smartdev/index.sqlite"],
        ),
    )

    finding = _finding(result, "path.protected_modified")
    assert result["verdict"] == "block"
    assert finding["severity"] == "block"
    assert finding["evidence"]["matched_pattern"] == ".smartdev/index.sqlite"


def test_hash_mismatch_blocks(tmp_path: Path):
    from smartdev.core.gate import gate_check

    target = tmp_path / "src" / "a.py"
    target.parent.mkdir()
    target.write_text("current\n")

    result = gate_check(
        tmp_path,
        _request(
            [{
                "path": "src/a.py",
                "change_type": "modify",
                "old_hash": "sha256:" + compute_content_hash("old\n"),
            }],
            allowed_paths=["src/**"],
        ),
    )

    finding = _finding(result, "patch.hash_mismatch")
    assert result["verdict"] == "block"
    assert finding["severity"] == "block"
    assert finding["evidence"]["declared_old_hash"] != finding["evidence"]["current_hash"]


def test_binary_file_modification_blocks(tmp_path: Path):
    from smartdev.core.gate import gate_check

    result = gate_check(
        tmp_path,
        _request(
            [{"path": "assets/logo.png", "change_type": "modify"}],
            allowed_paths=["assets/**"],
        ),
    )

    finding = _finding(result, "patch.binary_or_generated_file_modified")
    assert result["verdict"] == "block"
    assert finding["severity"] == "block"
    assert finding["evidence"]["reason"] == "binary_ext"


def test_missing_hash_source_downgrades_to_warn(tmp_path: Path):
    from smartdev.core.gate import gate_check

    result = gate_check(
        tmp_path,
        _request(
            [{"path": "src/a.py", "change_type": "modify"}],
            allowed_paths=["src/**"],
        ),
    )

    finding = _finding(result, "patch.unverifiable_source")
    assert result["verdict"] == "warn"
    assert finding["severity"] == "warn"


def test_unknown_contract_version_warns_and_never_blocks(tmp_path: Path):
    from smartdev.core.gate import gate_check

    result = gate_check(
        tmp_path,
        _request(
            [{"path": ".smartdev/index.sqlite", "change_type": "modify"}],
            disallowed_paths=[".smartdev/index.sqlite"],
            contract_version="2099-01-01.v9",
        ),
    )

    assert result["verdict"] == "warn"
    finding = _finding(result, "gate.contract_version_unsupported")
    assert finding["severity"] == "warn"


def test_inputs_digest_is_stable_and_excludes_index_evidence(tmp_path: Path):
    from smartdev.core.gate import gate_check

    base = _request(
        [{"path": "src/a.py", "change_type": "modify", "old_hash": "sha256:abc"}],
        index_evidence={"affected_files": ["src/a.py"]},
    )
    enriched = _request(
        [{"path": "src/a.py", "change_type": "modify", "old_hash": "sha256:abc"}],
        index_evidence={"affected_files": ["src/a.py", "src/b.py"]},
    )

    first = gate_check(tmp_path, base)
    second = gate_check(tmp_path, enriched)

    assert first["inputs_digest"] == second["inputs_digest"]


def test_legacy_scope_violation_severity_is_not_transmitted_as_block():
    from smartdev.core.gate import adapt_scope_violation, apply_policy
    from smartdev.core.scope_gate import ScopeViolation

    legacy = ScopeViolation(
        file="docs/readme.md",
        rule="outside_scope",
        severity="error",
        message="legacy error must not become block directly",
    )

    raw = adapt_scope_violation(legacy)
    assert "severity" not in raw.to_dict()
    finding = apply_policy([raw])[0]
    assert finding.severity == "block"
    assert finding.rule_id == "scope.unlisted_file_modified"
