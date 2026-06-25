"""
gate.check v1 — conservative pre-apply gate policy.

Rules report facts and confidence. Policy alone derives severity and verdict.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from smartdev.core.patch import _BINARY_EXTS, compute_content_hash


CONTRACT_VERSION = "2026-06-25.v1"
POLICY_VERSION = "scope-gate.v1"

_SEVERITY_ORDER = {"info": 0, "warn": 1, "block": 2}
_DETERMINISTIC_BLOCKLIST = {
    "scope.unlisted_file_modified",
    "path.protected_modified",
    "patch.hash_mismatch",
    "patch.binary_or_generated_file_modified",
}
_WARN_ONLY_RULES = {"deps.manifest_changed_without_scope"}
_WARN_ONLY_RULES.update({
    "scope.authority_unverified",
    "scope.declared_exceeds_authorized",
})
_INFO_RULES = {
    "gate.diff_ignored_patch_id_present",
    "gate.profile_downgraded",
    "gate.no_protected_paths_declared",
}
_GATE_ERROR_RULES = {"gate.malformed_request"}
_MACHINE_ACTIONS = {
    "remove_file_from_patch",
    "revert_hunk",
    "update_scope",
    "rerun_with_index",
    "rerun_patch_propose",
    "none",
}
_MANIFEST_FILES = {
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
}
_GENERATED_PATTERNS = [
    "**/*.lock",
    "dist/**",
    "build/**",
    "**/*.min.js",
]
_DEFAULT_PROTECTED_PATTERNS = [
    ".smartdev/runs/**/authorized_scope.json",
]


@dataclass
class RuleFinding:
    """Raw rule fact. This intentionally has no severity field."""

    rule_id: str
    confidence: str
    subject: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    suggestion: str = ""
    machine_action: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "confidence": self.confidence,
            "subject": self.subject,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
            "machine_action": _machine_action(self.machine_action),
        }


@dataclass
class GateFinding:
    """Policy-derived finding returned by gate.check."""

    rule_id: str
    confidence: str
    severity: str
    subject: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    suggestion: str = ""
    machine_action: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "confidence": self.confidence,
            "severity": self.severity,
            "subject": self.subject,
            "evidence": self.evidence,
            "suggestion": self.suggestion,
            "machine_action": _machine_action(self.machine_action),
        }


def _machine_action(action: str) -> str:
    return action if action in _MACHINE_ACTIONS else "none"


def _match_any(path: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if fnmatch.fnmatch(path, pattern):
            return pattern
        if pattern.endswith("/") and path.startswith(pattern):
            return pattern
        if fnmatch.fnmatch(Path(path).name, pattern):
            return pattern
    return None


def _is_manifest(path: str) -> bool:
    name = Path(path).name
    return (
        name in _MANIFEST_FILES
        or fnmatch.fnmatch(name, "requirements*.txt")
    )


def _is_generated(path: str) -> str | None:
    return _match_any(path, _GENERATED_PATTERNS)


def _normalize_hash(value: str) -> str:
    if not value:
        return ""
    return value if value.startswith("sha256:") else f"sha256:{value}"


def derive_severity(finding: RuleFinding, policy_profile: str = "conservative") -> str:
    """Derive severity from policy. Rules never choose severity."""
    if finding.rule_id in _INFO_RULES:
        return "info"
    if finding.rule_id in _WARN_ONLY_RULES:
        return "warn"
    if (
        finding.rule_id == "scope.unlisted_file_modified"
        and finding.evidence.get("authority_status") != "anchored"
    ):
        return "warn"
    if (
        finding.rule_id in _DETERMINISTIC_BLOCKLIST
        and finding.confidence == "high"
        and bool(finding.evidence)
    ):
        return "block"
    return "warn"


def apply_policy(
    findings: list[RuleFinding],
    policy_profile: str = "conservative",
) -> list[GateFinding]:
    """Apply conservative policy to raw findings."""
    return [
        GateFinding(
            rule_id=f.rule_id,
            confidence=f.confidence,
            severity=derive_severity(f, policy_profile),
            subject=f.subject,
            evidence=f.evidence,
            suggestion=f.suggestion,
            machine_action=f.machine_action,
        )
        for f in findings
    ]


def aggregate_verdict(findings: list[GateFinding]) -> str:
    if not findings:
        return "allow"
    max_score = max(_SEVERITY_ORDER.get(f.severity, 1) for f in findings)
    if max_score >= _SEVERITY_ORDER["block"]:
        return "block"
    if max_score >= _SEVERITY_ORDER["warn"]:
        return "warn"
    return "allow"


def compute_inputs_digest(request: dict[str, Any]) -> str:
    task_scope = request.get("task_scope", {})
    changed_files = request.get("change", {}).get("changed_files", [])
    canonical_changed = sorted(
        (
            {
                "path": item.get("path", ""),
                "change_type": item.get("change_type", ""),
                "old_hash": item.get("old_hash", ""),
                "new_hash": item.get("new_hash", ""),
            }
            for item in changed_files
            if isinstance(item, dict)
        ),
        key=lambda item: item["path"],
    )
    payload = {
        "task_scope": task_scope,
        "changed_files": canonical_changed,
        "contract_version": request.get("contract_version", ""),
        "run_id": request.get("run_id", ""),
        "policy_version": POLICY_VERSION,
        "policy_profile": request.get("options", {}).get(
            "policy_profile", "conservative"
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _malformed_finding(reason: str) -> RuleFinding:
    return RuleFinding(
        rule_id="gate.malformed_request",
        confidence="high",
        evidence={"reason": reason},
        suggestion="Provide a complete gate.check request matching contract_version 2026-06-25.v1.",
        machine_action="none",
    )


def _canonical_digest(data: dict[str, Any]) -> str:
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _safe_run_id(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts or len(candidate.parts) != 1:
        return None
    return value


def _authority_state(
    project_path: Path,
    request: dict[str, Any],
    declared_scope: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], RuleFinding | None]:
    """Resolve anchored authority from run_id without trusting request labels."""
    run_id = request.get("run_id")
    declared_authority = declared_scope.get("authority")
    base = {
        "status": "unverified",
        "run_id": run_id if isinstance(run_id, str) else None,
        "declared_authority": declared_authority,
        "source": "",
        "authorized_scope_digest": "",
        "authorized_scope_snapshot": {},
    }

    safe_run_id = _safe_run_id(run_id)
    if safe_run_id is None:
        status = "unverified" if not run_id else "missing"
        base["status"] = status
        return base, declared_scope, RuleFinding(
            rule_id="scope.authority_unverified",
            confidence="high",
            evidence={"run_id": run_id, "status": status, "source": ""},
            suggestion="Provide a run_id with an anchored authorized_scope.json.",
            machine_action="update_scope",
        )

    source = project_path / ".smartdev" / "runs" / safe_run_id / "authorized_scope.json"
    base["source"] = str(source.relative_to(project_path))
    try:
        authorized_scope = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        base["status"] = "unverified"
        return base, declared_scope, RuleFinding(
            rule_id="scope.authority_unverified",
            confidence="high",
            evidence={
                "run_id": safe_run_id,
                "status": "unverified",
                "source": base["source"],
                "reason": str(exc),
            },
            suggestion="Create a valid authorized_scope.json for this run_id.",
            machine_action="update_scope",
        )

    if not isinstance(authorized_scope, dict):
        base["status"] = "unverified"
        return base, declared_scope, RuleFinding(
            rule_id="scope.authority_unverified",
            confidence="high",
            evidence={
                "run_id": safe_run_id,
                "status": "unverified",
                "source": base["source"],
                "reason": "authorized_scope_not_object",
            },
            suggestion="Create a valid authorized_scope.json object for this run_id.",
            machine_action="update_scope",
        )

    snapshot = {
        "description": authorized_scope.get("description", ""),
        "allowed_paths": authorized_scope.get("allowed_paths") or [],
        "disallowed_paths": authorized_scope.get("disallowed_paths") or [],
        "risk_level": authorized_scope.get("risk_level", ""),
        "source": authorized_scope.get("source", ""),
    }
    base.update({
        "status": "anchored",
        "authorized_scope_digest": _canonical_digest(snapshot),
        "authorized_scope_snapshot": snapshot,
    })
    return base, snapshot, None


def _pattern_is_covered(pattern: str, authorized_patterns: list[str]) -> bool:
    for authorized in authorized_patterns:
        if pattern == authorized or authorized in {"*", "**", "**/*"}:
            return True
        if authorized.endswith("/**"):
            prefix = authorized[:-3]
            if pattern == prefix or pattern.startswith(prefix + "/"):
                return True
        if not any(ch in pattern for ch in "*?[]") and fnmatch.fnmatch(pattern, authorized):
            return True
    return False


def _pattern_matches_path(pattern: str, path: str) -> bool:
    return (
        fnmatch.fnmatch(path, pattern)
        or fnmatch.fnmatch(Path(path).name, pattern)
        or (pattern.endswith("/") and path.startswith(pattern))
    )


def adapt_scope_violation(violation: Any) -> RuleFinding:
    """Map legacy ScopeViolation to raw gate facts without copying severity."""
    rule_map = {
        "outside_scope": "scope.unlisted_file_modified",
        "denied_paths": "path.protected_modified",
        "protected_paths": "path.protected_modified",
    }
    rule_id = rule_map.get(getattr(violation, "rule", ""), "scope.legacy_violation")
    return RuleFinding(
        rule_id=rule_id,
        confidence="high",
        subject={"file": getattr(violation, "file", ""), "range": None},
        evidence={
            "legacy_rule": getattr(violation, "rule", ""),
            "message": getattr(violation, "message", ""),
        },
        suggestion=getattr(violation, "message", ""),
        machine_action="update_scope",
    )


def gate_check(project_path: Path, request: dict[str, Any]) -> dict[str, Any]:
    """Run gate.check v1 and return structured content."""
    if not isinstance(request, dict):
        digest = compute_inputs_digest({})
        findings = apply_policy([_malformed_finding("request_not_object")])
        return _result_dict(findings, digest)

    project_path = Path(project_path)
    digest = compute_inputs_digest(request)
    policy_profile = request.get("options", {}).get("policy_profile", "conservative")

    contract_version = request.get("contract_version")
    if contract_version in (None, ""):
        findings = apply_policy([
            RuleFinding(
                rule_id="gate.contract_version_missing",
                confidence="high",
                evidence={"supported": CONTRACT_VERSION},
                suggestion="Retry with contract_version 2026-06-25.v1.",
                machine_action="none",
            )
        ], policy_profile)
        return _result_dict(findings, digest)

    if contract_version != CONTRACT_VERSION:
        findings = apply_policy([
            RuleFinding(
                rule_id="gate.contract_version_unsupported",
                confidence="high",
                evidence={
                    "received": contract_version,
                    "supported": CONTRACT_VERSION,
                },
                suggestion="Retry with a supported gate.check contract version.",
                machine_action="none",
            )
        ], policy_profile)
        return _result_dict(findings, digest)

    raw_findings: list[RuleFinding] = []
    task_scope = request.get("task_scope", {})
    change = request.get("change", {})
    if not isinstance(task_scope, dict):
        raw_findings.append(_malformed_finding("task_scope_not_object"))
        task_scope = {}
    if not isinstance(change, dict):
        raw_findings.append(_malformed_finding("change_not_object"))
        change = {}
    elif not isinstance(change.get("changed_files"), list):
        raw_findings.append(_malformed_finding("change.changed_files_missing_or_not_array"))

    changed_files = [
        item for item in change.get("changed_files", [])
        if isinstance(item, dict)
    ]
    authority, effective_scope, authority_finding = _authority_state(
        project_path, request, task_scope
    )
    if authority_finding is not None:
        raw_findings.append(authority_finding)

    allowed_paths = effective_scope.get("allowed_paths") or []
    disallowed_paths = list(effective_scope.get("disallowed_paths") or [])
    for pattern in _DEFAULT_PROTECTED_PATTERNS:
        if pattern not in disallowed_paths:
            disallowed_paths.append(pattern)

    unlisted_paths = []
    for item in changed_files:
        path = item.get("path", "")
        disallowed_match = _match_any(path, disallowed_paths)
        allowed_match = _match_any(path, allowed_paths)
        if (
            allowed_paths
            and not allowed_match
            and not disallowed_match
            and not _is_manifest(path)
        ):
            unlisted_paths.append(path)

    declared_paths = task_scope.get("allowed_paths") or []
    if authority["status"] == "anchored":
        declared_only = [
            pattern for pattern in declared_paths
            if not _pattern_is_covered(pattern, allowed_paths)
            and not any(_pattern_matches_path(pattern, path) for path in unlisted_paths)
        ]
        if declared_only:
            raw_findings.append(RuleFinding(
                rule_id="scope.declared_exceeds_authorized",
                confidence="high",
                evidence={
                    "declared_only_patterns": declared_only,
                    "authorized_scope": {
                        "allowed_paths": allowed_paths,
                        "disallowed_paths": disallowed_paths,
                    },
                },
                suggestion="Narrow declared task_scope or update authorized_scope.json.",
                machine_action="update_scope",
            ))

    if change.get("patch_id") and change.get("diff"):
        raw_findings.append(RuleFinding(
            rule_id="gate.diff_ignored_patch_id_present",
            confidence="high",
            evidence={"patch_id": change.get("patch_id")},
            suggestion="patch_id is authoritative; diff was ignored.",
            machine_action="none",
        ))

    unverifiable_files: list[str] = []
    for item in changed_files:
        path = item.get("path", "")
        change_type = item.get("change_type", "")
        disallowed_match = _match_any(path, disallowed_paths)
        allowed_match = _match_any(path, allowed_paths)

        if disallowed_match:
            raw_findings.append(RuleFinding(
                rule_id="path.protected_modified",
                confidence="high",
                subject={"file": path, "range": None},
                evidence={"changed_file": path, "matched_pattern": disallowed_match},
                suggestion="Remove this protected path from the patch.",
                machine_action="remove_file_from_patch",
            ))

        if _is_manifest(path) and not allowed_match:
            raw_findings.append(RuleFinding(
                rule_id="deps.manifest_changed_without_scope",
                confidence="high",
                subject={"file": path, "range": None},
                evidence={"manifest_file": path, "in_allowed_paths": False},
                suggestion="Update task scope if the manifest change is intentional.",
                machine_action="update_scope",
            ))
        elif allowed_paths and not allowed_match and not disallowed_match:
            raw_findings.append(RuleFinding(
                rule_id="scope.unlisted_file_modified",
                confidence="high",
                subject={"file": path, "range": None},
                evidence={
                    "changed_file": path,
                    "effective_scope": {
                        "allowed_paths": allowed_paths,
                        "disallowed_paths": disallowed_paths,
                    },
                    "authority_status": authority["status"],
                    "matched": False,
                },
                suggestion="Remove this file from the patch or update task scope.",
                machine_action="remove_file_from_patch",
            ))

        binary_reason = None
        binary_match = ""
        suffix = Path(path).suffix.lower()
        if suffix in _BINARY_EXTS:
            binary_reason = "binary_ext"
            binary_match = suffix
        else:
            generated_match = _is_generated(path)
            if generated_match:
                binary_reason = "generated_path"
                binary_match = generated_match
        if binary_reason:
            raw_findings.append(RuleFinding(
                rule_id="patch.binary_or_generated_file_modified",
                confidence="high",
                subject={"file": path, "range": None},
                evidence={
                    "file": path,
                    "reason": binary_reason,
                    "matched": binary_match,
                },
                suggestion="Remove binary or generated files from the patch.",
                machine_action="remove_file_from_patch",
            ))

        old_hash = _normalize_hash(item.get("old_hash", ""))
        if change_type in {"modify", "delete"}:
            if not change.get("patch_id") and not old_hash:
                unverifiable_files.append(path)
            elif old_hash:
                target = project_path / path
                try:
                    current_hash = "sha256:" + compute_content_hash(
                        target.read_text(encoding="utf-8")
                    )
                except (OSError, UnicodeDecodeError) as exc:
                    raw_findings.append(RuleFinding(
                        rule_id="patch.hash_unreadable",
                        confidence="medium",
                        subject={"file": path, "range": None},
                        evidence={"file": path, "reason": str(exc)},
                        suggestion="Re-run patch proposal after the file is readable.",
                        machine_action="none",
                    ))
                else:
                    if current_hash != old_hash:
                        raw_findings.append(RuleFinding(
                            rule_id="patch.hash_mismatch",
                            confidence="high",
                            subject={"file": path, "range": None},
                            evidence={
                                "file": path,
                                "declared_old_hash": old_hash,
                                "current_hash": current_hash,
                            },
                            suggestion="Re-run patch proposal; the file changed.",
                            machine_action="rerun_patch_propose",
                        ))

    if unverifiable_files:
        raw_findings.append(RuleFinding(
            rule_id="patch.unverifiable_source",
            confidence="low",
            evidence={
                "affected_files": unverifiable_files,
                "reason": "missing_patch_id_and_old_hash",
            },
            suggestion="Provide patch_id or old_hash before applying.",
            machine_action="rerun_with_index",
        ))

    findings = apply_policy(raw_findings, policy_profile)
    return _result_dict(findings, digest, authority)


def _result_dict(
    findings: list[GateFinding],
    digest: str,
    authority: dict[str, Any] | None = None,
) -> dict[str, Any]:
    verdict = aggregate_verdict(findings)
    finding_dicts = [f.to_dict() for f in findings]
    gate_error = any(f.rule_id in _GATE_ERROR_RULES for f in findings)
    authority = authority or {
        "status": "unverified",
        "run_id": None,
        "declared_authority": None,
        "source": "",
        "authorized_scope_digest": "",
        "authorized_scope_snapshot": {},
    }
    return {
        "verdict": verdict,
        "audit_id": "gate_" + digest.removeprefix("sha256:")[:12],
        "inputs_digest": digest,
        "contract_version": CONTRACT_VERSION,
        "policy_version": POLICY_VERSION,
        "authority": authority,
        "summary": _summary(verdict, finding_dicts),
        "gate_error": gate_error,
        "findings": finding_dicts,
    }


def _summary(verdict: str, findings: list[dict[str, Any]]) -> str:
    block_count = sum(1 for f in findings if f.get("severity") == "block")
    warn_count = sum(1 for f in findings if f.get("severity") == "warn")
    if verdict == "allow":
        return "No blocking or warning findings."
    return f"{block_count} blocking findings. {warn_count} warnings."
