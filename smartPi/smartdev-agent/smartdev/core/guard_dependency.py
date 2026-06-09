"""
Guard: dependency.guard — 依赖变更审查（R0 只读）

功能：
─────
在 AI 产出 patch / diff 之后、人 apply 或 commit 之前，检查依赖 manifest
是否发生变化，并输出可人工审查的结构化报告：

  - 是否新增依赖
  - 是否删除依赖
  - 是否修改依赖版本
  - 是否新增/删除 manifest 文件
  - manifest 变更时对应 lock 文件是否同步
  - 根据语言生态输出建议命令，但不调用外部工具

设计约束：
─────────
- 零外部依赖（标准库 + pathlib + tomllib）
- 确定性规则引擎，不调用模型
- 无 git 环境也能运行（基于显式输入）
- R0 只读 — 不修改任何文件
- 不下载依赖，不调用外部扫描器

对应文档：
- docs/phase-11b-design.md §3.3（dependency.guard 详细设计）
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# ── 常量: manifest 文件名 ───────────────────────────────────────

_MANIFEST_NAMES = {
    "pyproject.toml",
    "package.json",
    "go.mod",
    "requirements.txt",
}

# manifest → 对应的 lock 文件列表
_MANIFEST_LOCK_MAP: dict[str, list[str]] = {
    "pyproject.toml": ["poetry.lock", "uv.lock", "requirements.lock"],
    "package.json": ["package-lock.json", "pnpm-lock.yaml", "yarn.lock"],
    "go.mod": ["go.sum"],
    "requirements.txt": ["requirements.lock"],
}

# 生态 → 建议的安全审计命令
_ECO_SUGGESTIONS: dict[str, list[str]] = {
    "python": ["pip-audit"],
    "nodejs": ["npm audit"],
    "go": ["govulncheck ./..."],
    "multi": ["semgrep --config=auto"],
}


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class DependencyChange:
    """单条依赖变更记录。

    Attributes:
        manifest:       manifest 文件路径
        change_type:    变更类型（added / removed / version_changed）
        name:           依赖名称
        old_version:    旧版本号（removed 或 version_changed 时有值）
        new_version:    新版本号（added 或 version_changed 时有值）
        source_section: 来源节（如 dependencies / devDependencies）
    """

    manifest: str
    change_type: str
    name: str
    old_version: str | None = None
    new_version: str | None = None
    source_section: str = ""

    def to_dict(self) -> dict:
        return {
            "manifest": self.manifest,
            "change_type": self.change_type,
            "name": self.name,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "source_section": self.source_section,
        }


@dataclass
class DependencyViolation:
    """单条依赖检查违规。

    Attributes:
        rule:     违规规则名
        severity: 严重程度（error / warning / info）
        message:  人类可读说明
        detail:   补充信息
    """

    rule: str
    severity: str
    message: str
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "detail": self.detail,
        }


@dataclass
class DependencyResult:
    """dependency.guard 检查结果。

    Attributes:
        passed:          是否通过（无 error 级别违规）
        manifests_found: 检测到的 manifest 文件列表
        changes:         依赖变更列表
        violations:      违规列表
        warnings:         额外警告（如建议运行的工具）
        suggestions:     外部工具建议命令
        summary:         人类可读摘要
    """

    passed: bool = True
    manifests_found: list[str] = field(default_factory=list)
    changes: list[DependencyChange] = field(default_factory=list)
    violations: list[DependencyViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "manifests_found": self.manifests_found,
            "changes": [c.to_dict() for c in self.changes],
            "violations": [v.to_dict() for v in self.violations],
            "warnings": self.warnings,
            "suggestions": self.suggestions,
            "summary": self.summary,
        }


# ── Manifest 文件检测 ──────────────────────────────────────────


def _is_manifest_file(file_path: str) -> bool:
    """检测文件是否为依赖 manifest 文件。

    匹配 pyproject.toml / package.json / go.mod / requirements.txt，
    不考虑路径前缀——只要文件名匹配即视为 manifest。
    """
    return Path(file_path).name in _MANIFEST_NAMES


def _get_lock_files_for_manifest(manifest_path: str) -> list[str]:
    """获取 manifest 对应的期望 lock 文件名列表。"""
    name = Path(manifest_path).name
    return _MANIFEST_LOCK_MAP.get(name, [])


def _get_ecosystem_for_manifest(manifest_path: str) -> str:
    """根据 manifest 判断所属生态。"""
    name = Path(manifest_path).name
    if name == "pyproject.toml" or name == "requirements.txt":
        return "python"
    elif name == "package.json":
        return "nodejs"
    elif name == "go.mod":
        return "go"
    return ""


# ── Manifest 解析器 ────────────────────────────────────────────


def _parse_pyproject_toml(content: str) -> dict[str, str]:
    """解析 pyproject.toml 中的依赖声明。

    优先使用标准库 tomllib（Python 3.11+），失败时降级为行解析。

    提取范围：
      - [project].dependencies
      - [project].optional-dependencies
      - [tool.poetry.dependencies]

    Returns:
        {依赖名: 版本字符串} 字典
    """
    deps: dict[str, str] = {}

    # 首先尝试用 tomllib 解析
    try:
        import tomllib

        data = tomllib.loads(content)

        # [project].dependencies — 可能是数组（PEP 621）或表格
        project = data.get("project", {})
        raw_deps = project.get("dependencies", [])
        if isinstance(raw_deps, list):
            for item in raw_deps:
                parsed = _parse_pep508_dep(item)
                if parsed:
                    k, v = parsed
                    deps[k] = v
        elif isinstance(raw_deps, dict):
            for k, v in raw_deps.items():
                deps[k] = str(v) if not isinstance(v, dict) else _extract_version_from_dict(v)

        # [project].optional-dependencies
        optional_deps = project.get("optional-dependencies", {})
        if isinstance(optional_deps, dict):
            for group, items in optional_deps.items():
                if isinstance(items, list):
                    for item in items:
                        parsed = _parse_pep508_dep(item)
                        if parsed:
                            k, v = parsed
                            deps[f"{k} [optional:{group}]"] = v

        # [tool.poetry.dependencies]
        poetry = data.get("tool", {}).get("poetry", {})
        poetry_deps = poetry.get("dependencies", {})
        if isinstance(poetry_deps, dict):
            for k, v in poetry_deps.items():
                if k == "python":
                    continue  # python 版本约束不是依赖
                if isinstance(v, str):
                    deps[k] = v
                elif isinstance(v, dict):
                    version = _extract_version_from_dict(v)
                    if version:
                        deps[k] = version
    except Exception:
        pass  # tomllib 解析失败，降级到行解析

    # 如果 tomllib 成功解析到内容，直接返回
    if deps:
        return deps

    # 降级：行解析
    deps = {}
    in_deps_section = False
    current_section = ""

    for line in content.splitlines():
        stripped = line.strip()

        # 跳过注释和空行
        if not stripped or stripped.startswith("#"):
            continue

        # 检测节标题
        if stripped.startswith("["):
            current_section = stripped.lower()
            in_deps_section = (
                current_section.startswith("[project.optional-dependencies]")
                or current_section == "[tool.poetry.dependencies]"
            )
            # [project] 下的 dependencies 可能紧跟其后
            if current_section == "[project]":
                in_deps_section = False
            continue

        # [project] dependencies 以列表形式出现
        if current_section.startswith("[project]"):
            if stripped.startswith("dependencies"):
                in_deps_section = True
                # 可能是 "dependencies = [" 行本身
                dep_match = re.search(r'"([^"]+)"', stripped)
                if dep_match:
                    parsed = _parse_pep508_dep(dep_match.group(1))
                    if parsed:
                        k, v = parsed
                        deps[k] = v
                continue

        if not in_deps_section:
            continue

        # 跳过 section header 和空列表标记
        if stripped in ("[", "]", "dependencies = [", "]"):
            continue

        # 解析依赖行：支持 "dep>=1.0" / "dep==1.0" / dep = "^1.0"
        # PEP 508 格式（列表内）
        dep_match = re.search(r'"([^"]+)"', stripped)
        if dep_match:
            dep_str = dep_match.group(1)
            parsed = _parse_pep508_dep(dep_str)
            if parsed:
                k, v = parsed
                deps[k] = v
            continue

        # TOML key = value 格式
        kv_match = re.match(r'^(\S+)\s*=\s*(.+)$', stripped)
        if kv_match:
            k = kv_match.group(1)
            v_raw = kv_match.group(2).strip().strip('"').strip("'")
            if not k.startswith("[") and not k.startswith("#"):
                # 提取版本号
                v_match = re.match(r'"([^"]*)"', v_raw)
                if v_match:
                    deps[k] = v_match.group(1)
                else:
                    deps[k] = v_raw

    return deps


def _parse_pep508_dep(dep_str: str) -> tuple[str, str] | None:
    """解析 PEP 508 格式的依赖字符串。

    Examples:
        "fastapi>=0.104.0,<1.0" → ("fastapi", ">=0.104.0,<1.0")
        "fastapi" → ("fastapi", "*")
        "fastapi [all]>=0.104.0" → ("fastapi[all]", ">=0.104.0")
    """
    dep_str = dep_str.strip()
    if not dep_str:
        return None

    # 匹配 name[extras]version_spec 格式
    match = re.match(
        r'^([a-zA-Z0-9_][a-zA-Z0-9_.-]*(\[[^\]]*\])?)\s*(.*)$', dep_str
    )
    if match:
        name = match.group(1)
        version_spec = match.group(3).strip()
        if not version_spec:
            version_spec = "*"
        return name, version_spec
    return None


def _extract_version_from_dict(d: dict) -> str:
    """从 Poetry 风格的 dict 中提取版本号。

    Examples:
        {"version": "^1.0", "optional": true} → "^1.0"
    """
    if "version" in d:
        return str(d["version"])
    # 可能是 git / path / url 引用
    if "git" in d:
        return f"git:{d['git']}"
    if "path" in d:
        return f"path:{d['path']}"
    if "url" in d:
        return f"url:{d['url']}"
    return "*"


def _parse_package_json(content: str) -> dict[str, str]:
    """解析 package.json 中的依赖声明。

    提取范围：dependencies / devDependencies / peerDependencies / optionalDependencies

    Returns:
        {依赖名: 版本字符串} 字典
    """
    deps: dict[str, str] = {}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return deps

    sections = ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]
    for section in sections:
        raw = data.get(section, {})
        if isinstance(raw, dict):
            for name, version in raw.items():
                version_str = str(version) if version is not None else "*"
                if section == "dependencies":
                    deps[name] = version_str
                else:
                    deps[f"{name} [{section}]"] = version_str

    return deps


def _parse_go_mod(content: str) -> dict[str, str]:
    """解析 go.mod 中的 require 声明。

    支持两种格式：
      - 单行: require module/path v1.2.3
      - 块:   require ( ... )

    Returns:
        {模块路径: 版本字符串} 字典
    """
    deps: dict[str, str] = {}
    in_require_block = False

    for line in content.splitlines():
        stripped = line.strip()

        # 跳过注释和空行
        if not stripped or stripped.startswith("//"):
            continue

        # require 块开始
        if stripped == "require (":
            in_require_block = True
            continue

        # require 块结束
        if stripped == ")" and in_require_block:
            in_require_block = False
            continue

        # 单行 require
        single_match = re.match(r'^require\s+(\S+)\s+(\S+)', stripped)
        if single_match and not in_require_block:
            deps[single_match.group(1)] = single_match.group(2)
            continue

        # require 块内行
        if in_require_block:
            # 跳过 indirect 注释（但保留依赖）
            dep_match = re.match(r'^(\S+)\s+(\S+)', stripped)
            if dep_match:
                # 检查是否 indirect
                is_indirect = "// indirect" in stripped or "//indirect" in stripped
                name = dep_match.group(1)
                version = dep_match.group(2)
                if is_indirect:
                    deps[f"{name} [indirect]"] = version
                else:
                    deps[name] = version

    return deps


def _parse_requirements_txt(content: str) -> dict[str, str]:
    """解析 requirements.txt 中的依赖声明。

    支持的格式：
      - name==version
      - name>=version
      - name~=version
      - name!=version
      - name<=version
      - name<version
      - name (无版本号，标记为 *)

    跳过：
      - 空行和注释
      - -r / -c / -e / -- 指令
      - 环境标记（; python_version < "3.13"）

    Returns:
        {包名: 版本字符串} 字典
    """
    deps: dict[str, str] = {}

    for line in content.splitlines():
        stripped = line.strip()

        # 跳过空行和注释
        if not stripped or stripped.startswith("#"):
            continue

        # 跳过指令行
        if stripped.startswith(("-r", "-c", "-e", "--")):
            continue

        # 去除环境标记（; python_version ...）
        semi_pos = stripped.find(";")
        if semi_pos >= 0:
            stripped = stripped[:semi_pos].strip()

        # 去除行内注释（# 后面）
        hash_pos = stripped.find(" #")
        if hash_pos >= 0:
            stripped = stripped[:hash_pos].strip()

        if not stripped:
            continue

        # 匹配 name[extras] 后跟可选版本号
        match = re.match(
            r'^([a-zA-Z0-9_][a-zA-Z0-9_.-]*(\[[^\]]*\])?)\s*([><=!~].*)?$', stripped
        )
        if match:
            name = match.group(1)
            version_spec = match.group(3)
            if version_spec:
                deps[name] = version_spec.strip()
            else:
                deps[name] = "*"

    return deps


# ── 统一的 manifest 解析入口 ───────────────────────────────────


def _parse_manifest(file_path: str, content: str) -> dict[str, str]:
    """根据文件类型选择对应的解析器。"""
    name = Path(file_path).name
    if name == "pyproject.toml":
        return _parse_pyproject_toml(content)
    elif name == "package.json":
        return _parse_package_json(content)
    elif name == "go.mod":
        return _parse_go_mod(content)
    elif name == "requirements.txt":
        return _parse_requirements_txt(content)
    else:
        return {}


# ── 依赖 diff 分析 ─────────────────────────────────────────────


def _diff_dependencies(
    before: dict[str, str],
    after: dict[str, str],
    manifest_path: str,
) -> list[DependencyChange]:
    """对比前后依赖列表，返回变更记录。

    Args:
        before:       变更前的依赖字典 {name: version}
        after:        变更后的依赖字典 {name: version}
        manifest_path: manifest 文件路径（用于变更记录）

    Returns:
        DependencyChange 列表
    """
    changes: list[DependencyChange] = []
    before_keys = set(before.keys())
    after_keys = set(after.keys())

    # 新增依赖
    added = after_keys - before_keys
    for name in sorted(added):
        changes.append(DependencyChange(
            manifest=manifest_path,
            change_type="added",
            name=name,
            new_version=after[name],
        ))

    # 删除依赖
    removed = before_keys - after_keys
    for name in sorted(removed):
        changes.append(DependencyChange(
            manifest=manifest_path,
            change_type="removed",
            name=name,
            old_version=before[name],
        ))

    # 版本变更
    common = before_keys & after_keys
    for name in sorted(common):
        old_v = before[name]
        new_v = after[name]
        if old_v != new_v:
            changes.append(DependencyChange(
                manifest=manifest_path,
                change_type="version_changed",
                name=name,
                old_version=old_v,
                new_version=new_v,
            ))

    return changes


def _analyze_diff_for_manifest_changes(
    diff_content: str,
    manifest_before: dict[str, str] | None = None,
    manifest_after: dict[str, str] | None = None,
) -> list[DependencyChange]:
    """从 diff 内容中分析依赖变更。

    如果提供了 manifest_before/manifest_after，则精确比较；
    否则从 diff 的 + / - 行中推断变更。

    Args:
        diff_content:   unified diff 文本
        manifest_before: 变更前的 manifest 内容 {path: content}
        manifest_after:  变更后的 manifest 内容 {path: content}

    Returns:
        DependencyChange 列表
    """
    changes: list[DependencyChange] = []

    # 首先从 manifest_before/after 精确对比
    if manifest_before and manifest_after:
        # 找出共同的 manifest 文件
        common = set(manifest_before.keys()) & set(manifest_after.keys())
        for path in sorted(common):
            before_content = manifest_before[path]
            after_content = manifest_after[path]
            if before_content != after_content:
                before_deps = _parse_manifest(path, before_content)
                after_deps = _parse_manifest(path, after_content)
                changes.extend(_diff_dependencies(before_deps, after_deps, path))

        # 新增的 manifest
        added_manifests = set(manifest_after.keys()) - set(manifest_before.keys())
        for path in sorted(added_manifests):
            after_deps = _parse_manifest(path, manifest_after[path])
            for name, version in sorted(after_deps.items()):
                changes.append(DependencyChange(
                    manifest=path,
                    change_type="added",
                    name=name,
                    new_version=version,
                ))

        # 删除的 manifest
        removed_manifests = set(manifest_before.keys()) - set(manifest_after.keys())
        for path in sorted(removed_manifests):
            before_deps = _parse_manifest(path, manifest_before[path])
            for name, version in sorted(before_deps.items()):
                changes.append(DependencyChange(
                    manifest=path,
                    change_type="removed",
                    name=name,
                    old_version=version,
                ))

        return changes

    # 从 diff_content 推断（没有 before/after 时的补充）
    if diff_content:
        # 查找 diff 中涉及的 manifest 文件
        manifest_diffs = _extract_manifest_diffs(diff_content)
        changes.extend(manifest_diffs)

    return changes


def _extract_manifest_statuses(diff_content: str) -> tuple[set[str], set[str]]:
    """从 unified diff 中提取新增/删除的 manifest 文件。

    Returns:
        (added_manifests, removed_manifests)
    """
    added: set[str] = set()
    removed: set[str] = set()
    file_blocks = re.split(r'^diff --git ', diff_content, flags=re.MULTILINE)

    for block in file_blocks:
        if not block.strip():
            continue
        block = "diff --git " + block if not block.startswith("diff --git ") else block

        old_match = re.search(r'^--- (?:a/(.+)|/dev/null)$', block, re.MULTILINE)
        new_match = re.search(r'^\+\+\+ (?:b/(.+)|/dev/null)$', block, re.MULTILINE)
        if not old_match or not new_match:
            continue

        old_path = old_match.group(1)
        new_path = new_match.group(1)

        if old_path is None and new_path and _is_manifest_file(new_path):
            added.add(new_path)
        elif new_path is None and old_path and _is_manifest_file(old_path):
            removed.add(old_path)

    return added, removed


def _extract_manifest_diffs(diff_content: str) -> list[DependencyChange]:
    """从 unified diff 中提取 manifest 文件的依赖变更。

    解析 +++/--- 行确定文件，然后分析每个 manifest 块的 + / - 行。
    """
    changes: list[DependencyChange] = []
    # 按文件分割 diff
    file_blocks = re.split(r'^diff --git ', diff_content, flags=re.MULTILINE)

    for block in file_blocks:
        if not block.strip():
            continue
        # 重新补回 diff --git 前缀
        block = "diff --git " + block if not block.startswith("diff --git ") else block

        # 提取文件路径。删除文件时 +++ 为 /dev/null，需要回退到 --- a/<path>。
        new_match = re.search(r'^\+\+\+ b/(.+)$', block, re.MULTILINE)
        old_match = re.search(r'^--- a/(.+)$', block, re.MULTILINE)
        if new_match:
            file_path = new_match.group(1).strip()
        elif old_match and re.search(r'^\+\+\+ /dev/null$', block, re.MULTILINE):
            file_path = old_match.group(1).strip()
        else:
            continue
        if not _is_manifest_file(file_path):
            continue

        # 解析此 manifest 的 + / - 行
        name = Path(file_path).name
        added_deps: dict[str, str] = {}
        removed_deps: dict[str, str] = {}

        for line in block.splitlines():
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                continue
            if line.startswith("@@"):
                continue

            if line.startswith("+") and not line.startswith("+++"):
                deps = _parse_manifest_line(name, line[1:])
                for k, v in deps.items():
                    added_deps[k] = v
            elif line.startswith("-") and not line.startswith("---"):
                deps = _parse_manifest_line(name, line[1:])
                for k, v in deps.items():
                    removed_deps[k] = v

        # 比较 added vs removed
        if added_deps or removed_deps:
            block_changes = _diff_dependencies(removed_deps, added_deps, file_path)
            changes.extend(block_changes)

    return changes


def _parse_manifest_line(manifest_name: str, line: str) -> dict[str, str]:
    """解析 manifest diff 中的单行，尝试提取 {name: version}。

    根据 manifest 类型选择合适的解析策略。
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return {}

    if manifest_name == "pyproject.toml":
        return _parse_pyproject_line(stripped)
    elif manifest_name == "package.json":
        return _parse_package_json_line(stripped)
    elif manifest_name == "go.mod":
        return _parse_go_mod_line(stripped)
    elif manifest_name == "requirements.txt":
        return _parse_requirements_line(stripped)
    return {}


def _parse_pyproject_line(line: str) -> dict[str, str]:
    """解析 pyproject.toml 的依赖声明行。"""
    deps: dict[str, str] = {}

    # PEP 508 列表项格式（带引号）：优先匹配以避免 >= 中的 = 被误判为 KV 分隔符
    dep_match = re.search(r'"([^"]+)"', line)
    if dep_match:
        parsed = _parse_pep508_dep(dep_match.group(1))
        if parsed:
            deps[parsed[0]] = parsed[1]
            return deps

    # TOML key = value 格式（key 必须是裸标识符，不加引号）
    kv_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_-]*)\s*=\s*(.+)$', line)
    if kv_match:
        k = kv_match.group(1)
        v_raw = kv_match.group(2).strip().strip('"').strip("'").rstrip(",")
        if not k.startswith("#") and k != "python":
            deps[k] = v_raw

    return deps


def _parse_package_json_line(line: str) -> dict[str, str]:
    """解析 package.json 的依赖声明行。"""
    deps: dict[str, str] = {}
    # JSON key: value 格式
    match = re.search(r'"([a-zA-Z@][^"]*)"\s*:\s*"([^"]*)"', line)
    if match:
        deps[match.group(1)] = match.group(2)
    return deps


def _parse_go_mod_line(line: str) -> dict[str, str]:
    """解析 go.mod 的 require 行。"""
    deps: dict[str, str] = {}
    # require module/path v1.2.3
    match = re.match(r'^require\s+(\S+)\s+(\S+)', line)
    if match:
        deps[match.group(1)] = match.group(2)
        return deps
    # 块内行: module/path v1.2.3
    match = re.match(r'^(\S+)\s+(v\S+)', line)
    if match and not line.startswith("module "):
        deps[match.group(1)] = match.group(2)
    return deps


def _parse_requirements_line(line: str) -> dict[str, str]:
    """解析 requirements.txt 的依赖行。"""
    deps: dict[str, str] = {}
    # 去除环境标记和注释
    semi_pos = line.find(";")
    if semi_pos >= 0:
        line = line[:semi_pos].strip()
    hash_pos = line.find(" #")
    if hash_pos >= 0:
        line = line[:hash_pos].strip()

    if not line:
        return deps

    match = re.match(
        r'^([a-zA-Z0-9_][a-zA-Z0-9_.-]*(\[[^\]]*\])?)\s*([><=!~].*)?$', line
    )
    if match:
        name = match.group(1)
        version_spec = match.group(3)
        deps[name] = version_spec.strip() if version_spec else "*"
    return deps


# ── Lock 文件检查 ──────────────────────────────────────────────


def _check_lock_sync(
    manifest_changes: list[DependencyChange],
    changed_files: list[str],
    lock_files_changed: list[str] | None = None,
) -> list[DependencyViolation]:
    """检查 manifest 变更时对应的 lock 文件是否已同步更新。

    Args:
        manifest_changes: 依赖变更列表
        changed_files:   所有变更文件（用于检查 lock 是否在变更中）
        lock_files_changed: 明确指定的 lock 文件变更列表（可选）

    Returns:
        违规列表
    """
    violations: list[DependencyViolation] = []

    # 所有变更文件的文件名集合
    changed_basenames = {Path(f).name for f in changed_files}
    if lock_files_changed:
        changed_basenames |= {Path(f).name for f in lock_files_changed}

    # 收集所有有变更的 manifest
    manifests_with_changes: set[str] = set()
    for c in manifest_changes:
        manifests_with_changes.add(c.manifest)

    for manifest_path in sorted(manifests_with_changes):
        expected_locks = _get_lock_files_for_manifest(manifest_path)
        if not expected_locks:
            continue

        synced = any(lock in changed_basenames for lock in expected_locks)
        if not synced:
            violations.append(DependencyViolation(
                rule="lock_not_updated",
                severity="warning",
                message=(
                    f"manifest '{manifest_path}' 有依赖变更，"
                    f"但对应的 lock 文件（{', '.join(expected_locks)}）均未出现在变更中"
                ),
                detail={
                    "manifest": manifest_path,
                    "expected_locks": expected_locks,
                    "locks_found_in_changes": [],
                },
            ))

    return violations


# ── 建议命令生成 ───────────────────────────────────────────────


def _generate_suggestions(
    manifests_found: list[str],
    has_changes: bool,
) -> list[str]:
    """根据涉及的生态生成建议的安全审计命令（只输出建议，不执行）。

    Args:
        manifests_found: 检测到的 manifest 文件列表
        has_changes:     是否有实际依赖变更

    Returns:
        建议命令列表
    """
    if not has_changes:
        return []

    ecosystems: set[str] = set()
    for mf in manifests_found:
        eco = _get_ecosystem_for_manifest(mf)
        if eco:
            ecosystems.add(eco)

    suggestions: list[str] = []
    for eco in sorted(ecosystems):
        if eco in _ECO_SUGGESTIONS:
            suggestions.extend(_ECO_SUGGESTIONS[eco])

    # 多生态或无法确定时建议 semgrep
    if len(ecosystems) > 1 and "multi" in _ECO_SUGGESTIONS:
        suggestions.extend(_ECO_SUGGESTIONS["multi"])

    return suggestions


# ── 核心规则引擎 ──────────────────────────────────────────────


def check_dependency_guard(
    changed_files: list[str],
    diff_content: str | None = None,
    manifest_before: dict[str, str] | None = None,
    manifest_after: dict[str, str] | None = None,
    lock_files_changed: list[str] | None = None,
) -> DependencyResult:
    """执行 dependency.guard 检查。

    整体流程：
    1. 从 changed_files 和 before/after 中识别所有涉及的 manifest
    2. 对每个 manifest 解析依赖并对比差异
    3. 检查 manifest 新增/删除
    4. 检查 lock 文件同步
    5. 生成建议命令
    6. 汇总 passed / violations / summary

    Args:
        changed_files:      变更文件列表（相对项目根目录的路径字符串）
        diff_content:        完整的 unified diff 文本（可选）
        manifest_before:     变更前的 manifest 内容 {path: content}（可选）
        manifest_after:      变更后的 manifest 内容 {path: content}（可选）
        lock_files_changed: 明确变更的 lock 文件列表（可选）

    Returns:
        DependencyResult: 结构化检查结果
    """
    violations: list[DependencyViolation] = []
    changes: list[DependencyChange] = []
    warning_messages: list[str] = []

    # ── 步骤 1: 识别所有涉及的 manifest ─────────────────────────
    all_manifests: set[str] = set()

    # 从 changed_files 中识别
    for f in changed_files:
        if _is_manifest_file(f):
            all_manifests.add(f)

    # 从 manifest_before / manifest_after 中补充
    if manifest_before:
        for path in manifest_before:
            if _is_manifest_file(path):
                all_manifests.add(path)
    if manifest_after:
        for path in manifest_after:
            if _is_manifest_file(path):
                all_manifests.add(path)

    manifests_found = sorted(all_manifests)

    if not manifests_found:
        return DependencyResult(
            passed=True,
            manifests_found=[],
            changes=[],
            violations=[],
            warnings=[],
            suggestions=[],
            summary="✅ dependency.guard：无依赖 manifest 变更",
        )

    # ── 步骤 2: 检测 manifest 新增 / 删除 ────────────────────────
    status_added_from_diff: set[str] = set()
    status_removed_from_diff: set[str] = set()
    if diff_content:
        status_added_from_diff, status_removed_from_diff = _extract_manifest_statuses(
            diff_content
        )

    if manifest_before is not None and manifest_after is not None:
        before_manifests = {p for p in manifest_before if _is_manifest_file(p)}
        after_manifests = {p for p in manifest_after if _is_manifest_file(p)}

        # 新增的 manifest — info
        added_manifests = after_manifests - before_manifests
        for mf in sorted(added_manifests):
            violations.append(DependencyViolation(
                rule="manifest_added",
                severity="info",
                message=f"新增依赖 manifest 文件: '{mf}'",
                detail={"manifest": mf},
            ))

        # 删除的 manifest — error
        removed_manifests = before_manifests - after_manifests
        for mf in sorted(removed_manifests):
            violations.append(DependencyViolation(
                rule="manifest_removed",
                severity="error",
                message=(
                    f"删除依赖 manifest 文件: '{mf}'。"
                    f"删除 manifest 可能导致项目不可构建，请确认"
                ),
                detail={"manifest": mf},
            ))

    # 补充 unified diff 中的 /dev/null 状态；当没有 before/after 时尤其重要。
    existing_statuses = {
        (v.rule, v.detail.get("manifest"))
        for v in violations
        if v.rule in ("manifest_added", "manifest_removed")
    }
    for mf in sorted(status_added_from_diff):
        if ("manifest_added", mf) not in existing_statuses:
            violations.append(DependencyViolation(
                rule="manifest_added",
                severity="info",
                message=f"新增依赖 manifest 文件: '{mf}'",
                detail={"manifest": mf},
            ))
    for mf in sorted(status_removed_from_diff):
        if ("manifest_removed", mf) not in existing_statuses:
            violations.append(DependencyViolation(
                rule="manifest_removed",
                severity="error",
                message=(
                    f"删除依赖 manifest 文件: '{mf}'。"
                    f"删除 manifest 可能导致项目不可构建，请确认"
                ),
                detail={"manifest": mf},
            ))

    # ── 步骤 3: 分析依赖变更 ────────────────────────────────────
    changes = _analyze_diff_for_manifest_changes(
        diff_content or "",
        manifest_before=manifest_before,
        manifest_after=manifest_after,
    )

    # 当没有 before/after 时，如果 diff_content 也没提取到，尝试从 manifest_before/after
    # 的 inside 对比来做（针对 changed_files 中的 manifest 有 before/after 内容的情况）
    if not changes and manifest_before and manifest_after:
        for mf in manifests_found:
            if mf in manifest_before and mf in manifest_after:
                before_deps = _parse_manifest(mf, manifest_before[mf])
                after_deps = _parse_manifest(mf, manifest_after[mf])
                mf_changes = _diff_dependencies(before_deps, after_deps, mf)
                changes.extend(mf_changes)

    # ── 步骤 4: 将变更归类为违规 ─────────────────────────────────
    for change in changes:
        if change.change_type == "added":
            violations.append(DependencyViolation(
                rule="dependency_added",
                severity="warning",
                message=(
                    f"[{change.manifest}] 新增依赖: "
                    f"'{change.name}' {change.new_version or ''}"
                ),
                detail={
                    "manifest": change.manifest,
                    "name": change.name,
                    "new_version": change.new_version,
                },
            ))
        elif change.change_type == "removed":
            violations.append(DependencyViolation(
                rule="dependency_removed",
                severity="warning",
                message=(
                    f"[{change.manifest}] 删除依赖: "
                    f"'{change.name}' (原版本 {change.old_version or '*'})"
                ),
                detail={
                    "manifest": change.manifest,
                    "name": change.name,
                    "old_version": change.old_version,
                },
            ))
        elif change.change_type == "version_changed":
            violations.append(DependencyViolation(
                rule="dependency_version_changed",
                severity="warning",
                message=(
                    f"[{change.manifest}] 依赖版本变更: "
                    f"'{change.name}' {change.old_version or '*'} → {change.new_version or '*'}"
                ),
                detail={
                    "manifest": change.manifest,
                    "name": change.name,
                    "old_version": change.old_version,
                    "new_version": change.new_version,
                },
            ))

    # ── 步骤 5: Lock 文件同步检查 ────────────────────────────────
    lock_violations = _check_lock_sync(
        manifest_changes=changes,
        changed_files=changed_files,
        lock_files_changed=lock_files_changed,
    )
    violations.extend(lock_violations)

    # ── 步骤 6: 生成建议 ─────────────────────────────────────────
    has_changes = len(changes) > 0
    suggestions = _generate_suggestions(manifests_found, has_changes)

    # 添加生态特定的警告
    for suggestion in suggestions:
        warning_messages.append(f"建议运行: {suggestion}")

    # ── 步骤 7: 计算 passed ──────────────────────────────────────
    error_count = sum(1 for v in violations if v.severity == "error")
    warning_count = sum(1 for v in violations if v.severity == "warning")
    info_count = sum(1 for v in violations if v.severity == "info")
    passed = error_count == 0

    # ── 步骤 8: 构建摘要 ────────────────────────────────────────
    if passed and not violations:
        summary = (
            f"✅ dependency.guard 通过：{len(manifests_found)} 个 manifest 无变更"
        )
    elif passed:
        parts = [f"⚠ dependency.guard 通过"]
        detail_parts = []
        added_count = sum(1 for c in changes if c.change_type == "added")
        removed_count = sum(1 for c in changes if c.change_type == "removed")
        version_count = sum(1 for c in changes if c.change_type == "version_changed")
        if added_count:
            detail_parts.append(f"{added_count} 个新增依赖")
        if removed_count:
            detail_parts.append(f"{removed_count} 个删除依赖")
        if version_count:
            detail_parts.append(f"{version_count} 个版本变更")
        if detail_parts:
            parts.append(f"{', '.join(detail_parts)}")
        parts.append(f"({warning_count} 个警告" if warning_count else "(0 个警告")
        if info_count:
            parts[-1] += f"，{info_count} 个提示"
        parts[-1] += ")"
        summary = "：".join(parts)
    else:
        parts = [f"❌ dependency.guard 未通过（{error_count} 个错误"]
        if warning_count:
            parts[-1] += f"，{warning_count} 个警告"
        if info_count:
            parts[-1] += f"，{info_count} 个提示"
        parts[-1] += ")"
        error_details = [
            v.message for v in violations if v.severity == "error"
        ]
        if error_details:
            parts.append("；".join(error_details[:3]))
            if len(error_details) > 3:
                parts[-1] += f" ... 及其他 {len(error_details) - 3} 个错误"
        summary = "：".join(parts)

    return DependencyResult(
        passed=passed,
        manifests_found=manifests_found,
        changes=changes,
        violations=violations,
        warnings=warning_messages,
        suggestions=suggestions,
        summary=summary,
    )
