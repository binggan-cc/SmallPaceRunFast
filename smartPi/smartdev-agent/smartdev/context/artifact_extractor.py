"""
SmartDev Agent Artifact 提取器

设计原理：
─────────
Artifact（工件）是"非代码实体"的统称。SmartDev 的图谱不只是"纯代码图"，
而是"项目开发图"，包含路由、端点、设计令牌、文档、配置、数据模型等。

借鉴来源：
- Understand-Anything 的 GraphBuilder：把 YAML、Docker、CI、SQL 等也转成节点
- "SmartDev 的图谱不是纯代码图，而是项目开发图"

Phase 6-MVP 支持 8 种 artifact 类型：
- api_endpoint: FastAPI/Flask/Django 路由
- manifest: Chrome Extension manifest.json
- design_token: CSS 变量定义（--xxx: value）
- document: Markdown 文档
- server_file: FastAPI 服务文件
- extension_file: Chrome Extension 文件
- model: 数据模型定义（class Xxx(BaseModel)）
- config: 配置文件

提取策略：正则 + 简单 AST（不用 tree-sitter，保持零依赖）。

对应文档：
- next-phase-code-intelligence.md §11（Task 3：SmartFav artifact 提取）
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from smartdev.context.index_store import ArtifactRecord, RelationRecord
from smartdev.context.structure_extractor import CodeSymbol, extract_structure


# ── Artifact 类型常量 ──────────────────────────────────────

ARTIFACT_TYPE_API_ENDPOINT = "api_endpoint"
ARTIFACT_TYPE_MANIFEST = "manifest"
ARTIFACT_TYPE_DESIGN_TOKEN = "design_token"
ARTIFACT_TYPE_DOCUMENT = "document"
ARTIFACT_TYPE_SERVER_FILE = "server_file"
ARTIFACT_TYPE_EXTENSION_FILE = "extension_file"
ARTIFACT_TYPE_MODEL = "model"
ARTIFACT_TYPE_CONFIG = "config"


# ── 提取结果 ──────────────────────────────────────────────

@dataclass
class ExtractionResult:
    """提取结果"""
    artifacts: list[ArtifactRecord]
    relations: list[RelationRecord]
    errors: list[str]


# ── API Endpoint 提取 ─────────────────────────────────────

# FastAPI 路由装饰器模式
_FASTAPI_ROUTE_PATTERN = re.compile(
    r'@(?:app|router)\.(get|post|put|delete|patch|head|options)'
    r'\s*\(\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)

# Flask 路由模式
_FLASK_ROUTE_PATTERN = re.compile(
    r'@(?:app|bp|blueprint)\.route\s*\(\s*["\']([^"\']+)["\']',
    re.MULTILINE,
)


def _extract_api_endpoints(file_path: Path, content: str) -> list[ArtifactRecord]:
    """提取 API 端点"""
    artifacts = []
    rel_path = str(file_path)

    # FastAPI 路由
    for match in _FASTAPI_ROUTE_PATTERN.finditer(content):
        method = match.group(1).upper()
        path = match.group(2)
        line_num = content[:match.start()].count("\n") + 1
        artifacts.append(ArtifactRecord(
            id=f"api:{method.lower()}:{path.replace('/', '_').strip('_')}",
            type=ARTIFACT_TYPE_API_ENDPOINT,
            name=f"{method} {path}",
            file_path=rel_path,
            start_line=line_num,
            end_line=line_num,
            metadata_json=json.dumps({"method": method, "path": path, "framework": "fastapi"}),
        ))

    # Flask 路由
    for match in _FLASK_ROUTE_PATTERN.finditer(content):
        path = match.group(1)
        line_num = content[:match.start()].count("\n") + 1
        artifacts.append(ArtifactRecord(
            id=f"api:get:{path.replace('/', '_').strip('_')}",
            type=ARTIFACT_TYPE_API_ENDPOINT,
            name=f"GET {path}",
            file_path=rel_path,
            start_line=line_num,
            end_line=line_num,
            metadata_json=json.dumps({"method": "GET", "path": path, "framework": "flask"}),
        ))

    return artifacts


# ── Manifest 提取 ─────────────────────────────────────────

def _extract_manifest(file_path: Path, content: str) -> list[ArtifactRecord]:
    """提取 Chrome Extension manifest"""
    if file_path.name != "manifest.json":
        return []

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    artifacts = []
    name = data.get("name", "unknown")
    version = data.get("version", "unknown")
    manifest_version = data.get("manifest_version", 0)

    artifacts.append(ArtifactRecord(
        id=f"manifest:{file_path}",
        type=ARTIFACT_TYPE_MANIFEST,
        name=f"{name} v{version} (MV{manifest_version})",
        file_path=str(file_path),
        metadata_json=json.dumps({
            "name": name,
            "version": version,
            "manifest_version": manifest_version,
            "permissions": data.get("permissions", []),
        }),
    ))

    return artifacts


# ── Design Token 提取 ─────────────────────────────────────

# CSS 变量定义模式
_CSS_VAR_PATTERN = re.compile(
    r'(--[\w-]+)\s*:\s*([^;]+);',
    re.MULTILINE,
)

# SCSS 变量模式
_SCSS_VAR_PATTERN = re.compile(
    r'(\$[\w-]+)\s*:\s*([^;]+);',
    re.MULTILINE,
)


def _extract_design_tokens(file_path: Path, content: str) -> list[ArtifactRecord]:
    """提取设计令牌（CSS 变量）"""
    suffix = file_path.suffix.lower()
    if suffix not in {".css", ".scss", ".less", ".styl"}:
        return []

    artifacts = []
    rel_path = str(file_path)

    # CSS 变量
    for match in _CSS_VAR_PATTERN.finditer(content):
        var_name = match.group(1)
        var_value = match.group(2).strip()
        line_num = content[:match.start()].count("\n") + 1
        artifacts.append(ArtifactRecord(
            id=f"token:{rel_path}:{var_name}",
            type=ARTIFACT_TYPE_DESIGN_TOKEN,
            name=var_name,
            file_path=rel_path,
            start_line=line_num,
            end_line=line_num,
            metadata_json=json.dumps({"value": var_value, "format": "css"}),
        ))

    # SCSS 变量
    if suffix == ".scss":
        for match in _SCSS_VAR_PATTERN.finditer(content):
            var_name = match.group(1)
            var_value = match.group(2).strip()
            line_num = content[:match.start()].count("\n") + 1
            artifacts.append(ArtifactRecord(
                id=f"token:{rel_path}:{var_name}",
                type=ARTIFACT_TYPE_DESIGN_TOKEN,
                name=var_name,
                file_path=rel_path,
                start_line=line_num,
                end_line=line_num,
                metadata_json=json.dumps({"value": var_value, "format": "scss"}),
            ))

    return artifacts


# ── Document 提取 ─────────────────────────────────────────

_DOC_NAMES = {
    "README.md", "README.rst", "README.txt",
    "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE", "LICENSE.md",
    "ARCHITECTURE.md", "DESIGN.md", "API.md",
}


def _extract_documents(file_path: Path, content: str) -> list[ArtifactRecord]:
    """提取文档"""
    name = file_path.name
    if name not in _DOC_NAMES and not name.endswith(".md"):
        return []

    # 计算行数
    line_count = content.count("\n") + 1

    # 尝试提取标题作为 name
    title = name
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break

    artifacts = [ArtifactRecord(
        id=f"doc:{file_path}",
        type=ARTIFACT_TYPE_DOCUMENT,
        name=title,
        file_path=str(file_path),
        end_line=line_count,
        metadata_json=json.dumps({
            "lines": line_count,
            "size": len(content),
            "is_primary": name in _DOC_NAMES,
        }),
    )]

    return artifacts


# ── Model 提取 ────────────────────────────────────────────

# Python class 定义模式（含 BaseModel 继承）
_PYTHON_CLASS_PATTERN = re.compile(
    r'^class\s+(\w+)\s*\(([^)]*)\)\s*:',
    re.MULTILINE,
)

# Pydantic / dataclass 装饰器模式
_DATACLASS_PATTERN = re.compile(
    r'@dataclass\s*\nclass\s+(\w+)',
    re.MULTILINE,
)


def _extract_models(file_path: Path, content: str) -> list[ArtifactRecord]:
    """提取数据模型定义"""
    if file_path.suffix.lower() != ".py":
        return []

    artifacts = []
    rel_path = str(file_path)

    # 带继承的 class（检测 Pydantic BaseModel, SQLAlchemy Model 等）
    for match in _PYTHON_CLASS_PATTERN.finditer(content):
        class_name = match.group(1)
        bases = match.group(2)

        # 只关注模型相关的基类
        model_bases = {"BaseModel", "Schema", "Model", "Document",
                       "AbstractBaseUser", "db.Model"}
        if not any(b.strip() in model_bases for b in bases.split(",")):
            continue

        line_num = content[:match.start()].count("\n") + 1
        # 找到 class 结束行（下一个 class 或文件结束）
        end_line = _find_class_end(content, match.end())

        artifacts.append(ArtifactRecord(
            id=f"model:{rel_path}:{class_name}",
            type=ARTIFACT_TYPE_MODEL,
            name=class_name,
            file_path=rel_path,
            start_line=line_num,
            end_line=end_line,
            metadata_json=json.dumps({"bases": [b.strip() for b in bases.split(",")]}),
        ))

    # @dataclass 装饰的类
    for match in _DATACLASS_PATTERN.finditer(content):
        class_name = match.group(1)
        line_num = content[:match.start()].count("\n") + 1
        end_line = _find_class_end(content, match.end())

        artifacts.append(ArtifactRecord(
            id=f"model:{rel_path}:{class_name}",
            type=ARTIFACT_TYPE_MODEL,
            name=class_name,
            file_path=rel_path,
            start_line=line_num,
            end_line=end_line,
            metadata_json=json.dumps({"bases": ["dataclass"]}),
        ))

    return artifacts


def _find_class_end(content: str, start_pos: int) -> int:
    """找到 class 定义的结束行号"""
    lines = content[start_pos:].splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and not stripped.startswith("def ") and not stripped.startswith("class "):
            # 简单启发：遇到下一级缩进的 def 或 class 就停止
            pass
    # 简化处理：返回文件总行数（Phase 6.2 再用 AST 精确计算）
    return content.count("\n") + 1


# ── Config 提取 ───────────────────────────────────────────

_CONFIG_FILES = {
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "package.json", "tsconfig.json", "vite.config.ts", "vite.config.js",
    "webpack.config.js", ".eslintrc.js", ".prettierrc",
    "Dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "Makefile", ".gitignore", ".env.example",
    "manifest.json",
}


def _extract_configs(file_path: Path, content: str) -> list[ArtifactRecord]:
    """提取配置文件"""
    name = file_path.name
    if name not in _CONFIG_FILES:
        return []

    # 尝试解析 JSON 获取描述信息
    description = name
    metadata = {}
    if name.endswith(".json"):
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                # package.json
                if "name" in data and "version" in data:
                    description = f"{data['name']} v{data['version']}"
                    metadata = {"name": data["name"], "version": data["version"]}
                # manifest.json 已单独处理
        except json.JSONDecodeError:
            pass

    artifacts = [ArtifactRecord(
        id=f"config:{file_path}",
        type=ARTIFACT_TYPE_CONFIG,
        name=description,
        file_path=str(file_path),
        metadata_json=json.dumps(metadata),
    )]

    return artifacts


# ── Server File 提取 ──────────────────────────────────────

def _extract_server_files(file_path: Path, content: str) -> list[ArtifactRecord]:
    """识别 FastAPI/Flask 服务文件"""
    if file_path.suffix.lower() != ".py":
        return []

    # 检测 FastAPI 特征
    has_fastapi = "fastapi" in content.lower() or "FastAPI" in content
    has_flask = "from flask" in content or "import flask"
    has_route = "@app." in content or "@router." in content or "@app.route" in content

    if not (has_fastapi or has_flask) or not has_route:
        return []

    framework = "fastapi" if has_fastapi else "flask"

    return [ArtifactRecord(
        id=f"server:{file_path}",
        type=ARTIFACT_TYPE_SERVER_FILE,
        name=file_path.stem,
        file_path=str(file_path),
        metadata_json=json.dumps({"framework": framework}),
    )]


# ── Extension File 提取 ───────────────────────────────────

_EXT_DIRS = {"background", "content", "content_scripts", "sidepanel", "popup", "options"}
_EXT_FILES = {"background.js", "content.js", "sidepanel.js", "popup.js", "options.js",
              "background.ts", "content.ts", "sidepanel.ts", "popup.ts", "options.ts"}


def _extract_extension_files(file_path: Path, content: str) -> list[ArtifactRecord]:
    """识别 Chrome Extension 文件"""
    name = file_path.name
    parts = file_path.parts

    # 检查文件名是否匹配
    is_ext_file = name in _EXT_FILES

    # 检查是否在扩展目录中
    is_ext_dir = any(d in parts for d in _EXT_DIRS)

    # 检查 Chrome Extension API 使用
    has_chrome_api = "chrome." in content

    if not (is_ext_file or (is_ext_dir and has_chrome_api)):
        return []

    return [ArtifactRecord(
        id=f"ext:{file_path}",
        type=ARTIFACT_TYPE_EXTENSION_FILE,
        name=file_path.stem,
        file_path=str(file_path),
        metadata_json=json.dumps({"has_chrome_api": has_chrome_api}),
    )]


# ── 主提取器 ──────────────────────────────────────────────

# 所有提取函数
_EXTRACTORS = [
    _extract_api_endpoints,
    _extract_manifest,
    _extract_design_tokens,
    _extract_documents,
    _extract_models,
    _extract_configs,
    _extract_server_files,
    _extract_extension_files,
]


# ── 结构提取辅助 ──────────────────────────────────────────

# 文件后缀 → 语言标识（与 structure_extractor 对齐）
_EXT_LANG = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".vue": "vue", ".svelte": "svelte",
}


def _symbol_to_artifact(symbol: CodeSymbol, rel_path: str) -> ArtifactRecord:
    """将 CodeSymbol 转换为 ArtifactRecord

    映射关系：
    - function → code:function
    - class → code:class
    - method → code:method（附带 parent 信息）
    - import → code:import
    - variable → code:variable
    """
    kind = f"code:{symbol.kind}"
    metadata = {
        "signature": symbol.signature,
        "parent": symbol.parent,
        "is_exported": symbol.is_exported,
        "confidence": symbol.confidence,
    }

    return ArtifactRecord(
        id=f"{kind}:{rel_path}:{symbol.name}",
        type=kind,
        name=symbol.name,
        file_path=rel_path,
        start_line=symbol.start_line,
        end_line=symbol.end_line,
        metadata_json=json.dumps(metadata),
    )


# ── Import Relation 构建 ──────────────────────────────────

# Python import 语句解析模式
# from smartdev.models import RiskLevel（绝对 import，module 不以点号开头）
_IMPORT_FROM = re.compile(
    r'^from\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)\s+import\s+(.+)$',
    re.MULTILINE,
)
# import os / import numpy as np
_IMPORT_DIRECT = re.compile(
    r'^import\s+([\w.]+)(?:\s+as\s+(\w+))?',
    re.MULTILINE,
)
# from .models import RiskLevel（相对 import，module 以点号开头）
_IMPORT_RELATIVE = re.compile(
    r'^from\s+(\.+[\w.]*)\s+import\s+(.+)$',
    re.MULTILINE,
)


def _parse_alias(names_str: str) -> tuple[list[str], dict[str, str]]:
    """解析 import 名称和 alias

    输入: "OrderedDict as OD, defaultdict"
    输出: (["OrderedDict", "defaultdict"], {"OrderedDict": "OD"})
    """
    names = []
    aliases: dict[str, str] = {}
    for part in names_str.split(","):
        part = part.strip()
        if " as " in part:
            real_name, alias = part.split(" as ", 1)
            names.append(real_name.strip())
            aliases[real_name.strip()] = alias.strip()
        else:
            names.append(part)
    return names, aliases


def _parse_imports(content: str, base_line: int = 1) -> list[dict]:
    """解析 Python import 语句

    参数：
        content: import 语句文本（可以是单行或多行）
        base_line: 起始行号偏移（用于计算真实行号）

    返回结构化 import 信息列表：
    [{
        "module": "smartdev.models",
        "names": ["RiskLevel", "SkillResult"],
        "aliases": {"RiskLevel": "RL"},
        "is_relative": False,
        "relative_level": 0,
        "import_kind": "from_import",
        "line": 12,
        "raw": "from smartdev.models import RiskLevel, SkillResult"
    }]
    """
    imports = []

    for match in _IMPORT_FROM.finditer(content):
        module = match.group(1)
        names_str = match.group(2)
        names, aliases = _parse_alias(names_str)
        line = base_line + content[:match.start()].count("\n")
        imports.append({
            "module": module,
            "names": names,
            "aliases": aliases,
            "is_relative": False,
            "relative_level": 0,
            "import_kind": "from_import",
            "line": line,
            "raw": match.group(0).strip(),
        })

    for match in _IMPORT_DIRECT.finditer(content):
        module = match.group(1)
        alias = match.group(2)  # None if no "as"
        line = base_line + content[:match.start()].count("\n")
        raw = match.group(0).strip()
        names = [module.split(".")[-1]]
        aliases = {names[0]: alias} if alias else {}
        imports.append({
            "module": module,
            "names": names,
            "aliases": aliases,
            "is_relative": False,
            "relative_level": 0,
            "import_kind": "import",
            "line": line,
            "raw": raw,
        })

    for match in _IMPORT_RELATIVE.finditer(content):
        rel_module = match.group(1)
        names_str = match.group(2)
        names, aliases = _parse_alias(names_str)
        level = rel_module.count(".")
        module_path = rel_module.lstrip(".")
        line = base_line + content[:match.start()].count("\n")
        imports.append({
            "module": module_path,
            "names": names,
            "aliases": aliases,
            "is_relative": True,
            "relative_level": level,
            "import_kind": "from_import",
            "line": line,
            "raw": match.group(0).strip(),
        })

    return imports


def _build_import_relations(
    rel_path: str,
    symbols: list[CodeSymbol],
    all_artifacts: list[ArtifactRecord],
) -> tuple[list[ArtifactRecord], list[RelationRecord]]:
    """从 import symbols 构建 relation candidates

    返回：
        (placeholder_artifacts, relations)
        placeholder_artifacts: 为 module / external / unresolved import 创建的 artifact
        relations: import 关系列表
    """
    placeholders: list[ArtifactRecord] = []
    relations: list[RelationRecord] = []

    # 当前文件的 module 名（如 smartdev/context/artifact_extractor.py → smartdev.context.artifact_extractor）
    module_name = rel_path.replace("/", ".").replace("\\", ".")
    if module_name.endswith(".py"):
        module_name = module_name[:-3]

    # ── P0-1：为当前文件创建 module artifact ──
    module_artifact_id = f"code:module:{rel_path}"
    placeholders.append(ArtifactRecord(
        id=module_artifact_id,
        type="code:module",
        name=module_name,
        file_path=rel_path,
        metadata_json=json.dumps({
            "language": "python",
            "module_name": module_name,
        }),
    ))

    # 构建已有 artifact 索引（用于查找 target）
    artifact_index: dict[str, ArtifactRecord] = {}
    for art in all_artifacts:
        artifact_index[art.id] = art

    for symbol in symbols:
        if symbol.kind != "import":
            continue

        sig = symbol.signature

        # 解析 import 语句（传入真实行号）
        parsed = _parse_imports(sig, base_line=symbol.start_line)
        if not parsed:
            continue

        for imp in parsed:
            module = imp["module"]
            names = imp["names"]
            aliases = imp["aliases"]
            relative_level = imp["relative_level"]

            # 构建 target_id
            if imp["is_relative"]:
                # 相对 import：暂时标记为 unresolved
                target_id = f"unresolved:relative:{rel_path}:{module}:{','.join(names)}"
                metadata = json.dumps({
                    "relative_level": relative_level,
                    "resolved": False,
                    "module": module,
                    "names": names,
                    "aliases": aliases,
                    "line": imp["line"],
                    "confidence": symbol.confidence,
                    "extractor": symbol.extractor,
                })
                # 创建 placeholder
                placeholders.append(ArtifactRecord(
                    id=target_id,
                    type="unresolved_module",
                    name=f"{'.' * relative_level}{module}",
                    file_path=rel_path,
                    metadata_json=json.dumps({
                        "relative_level": relative_level,
                        "resolved": False,
                        "external": False,
                    }),
                ))
            else:
                # 绝对 import
                is_external = _is_external_module(module)
                target_id = f"module:{module}"

                if target_id not in artifact_index:
                    if is_external:
                        target_id = f"external:python:{module}"
                        placeholders.append(ArtifactRecord(
                            id=target_id,
                            type="external_module",
                            name=module,
                            file_path="",
                            metadata_json=json.dumps({
                                "external": True,
                                "resolved": True,
                                "module": module,
                            }),
                        ))
                    else:
                        # 项目内模块，创建 placeholder
                        placeholders.append(ArtifactRecord(
                            id=target_id,
                            type="module",
                            name=module,
                            file_path="",
                            metadata_json=json.dumps({
                                "resolved": False,
                                "module": module,
                            }),
                        ))

                metadata = json.dumps({
                    "import_kind": imp["import_kind"],
                    "module": module,
                    "names": names,
                    "aliases": aliases,
                    "line": imp["line"],
                    "external": is_external,
                    "confidence": symbol.confidence,
                    "extractor": symbol.extractor,
                })

            relations.append(RelationRecord(
                source_id=module_artifact_id,
                target_id=target_id,
                type="imports",
                confidence=symbol.confidence,
                metadata_json=metadata,
            ))

    return placeholders, relations


# Python 标准库模块列表（fallback，Python 3.10+ 可用 sys.stdlib_module_names）
_PYTHON_STDLIB_FALLBACK = {
    "os", "sys", "json", "re", "ast", "pathlib", "time", "datetime",
    "typing", "collections", "abc", "dataclasses", "enum", "hashlib",
    "subprocess", "threading", "logging", "unittest", "pytest",
    "functools", "itertools", "operator", "string", "textwrap",
    "io", "csv", "xml", "html", "http", "urllib", "socket",
    "sqlite3", "tempfile", "shutil", "glob", "fnmatch",
    "argparse", "getopt", "configparser", "secrets", "base64",
    "struct", "codecs", "locale", "gettext", "unicodedata",
    "contextlib", "weakref", "types", "copy", "pprint",
    "calendar", "math", "random", "statistics", "decimal",
    "fractions", "array", "heapq", "bisect", "queue",
    "sched", "select", "signal", "mmap", "ctypes",
    "concurrent", "asyncio", "multiprocessing",
}

# Python 3.10+ 可直接获取标准库模块名
try:
    import sys as _sys
    _STDLIB_MODULES: set[str] = getattr(_sys, "stdlib_module_names", set())
except ImportError:
    _STDLIB_MODULES = set()


def _is_external_module(module: str) -> bool:
    """判断是否是 Python 标准库或第三方模块（非项目内模块）"""
    top_level = module.split(".")[0]
    if _STDLIB_MODULES:
        return top_level in _STDLIB_MODULES
    return top_level in _PYTHON_STDLIB_FALLBACK


class ArtifactExtractor:
    """项目工件提取器

    扫描项目文件，提取各类工件（artifact）。
    每种工件类型由独立的提取函数处理。

    使用示例：
        extractor = ArtifactExtractor()
        result = extractor.extract(project_path)
        for artifact in result.artifacts:
            print(f"{artifact.type}: {artifact.name}")
    """

    def __init__(self, max_file_size: int = 1 * 1024 * 1024) -> None:
        self.max_file_size = max_file_size

    def extract(self, project_path: Path,
                file_paths: list[str] | None = None) -> ExtractionResult:
        """提取项目工件

        参数：
            project_path: 项目根目录
            file_paths: 要扫描的文件列表（相对路径）。
                        如果为 None，扫描所有已索引文件。

        返回：
            ExtractionResult 包含工件列表和错误列表
        """
        artifacts: list[ArtifactRecord] = []
        relations: list[RelationRecord] = []
        errors: list[str] = []

        # 确定要扫描的文件
        if file_paths is None:
            file_paths = self._discover_files(project_path)

        for rel_path in file_paths:
            abs_path = project_path / rel_path
            if not abs_path.is_file():
                continue

            # 跳过大文件
            try:
                if abs_path.stat().st_size > self.max_file_size:
                    continue
            except OSError:
                continue

            # 读取内容
            try:
                content = abs_path.read_text(encoding="utf-8", errors="ignore")
            except OSError as e:
                errors.append(f"读取失败 {rel_path}: {e}")
                continue

            # 运行所有提取器（传入相对路径，确保 artifact 记录存储相对路径）
            for extractor_fn in _EXTRACTORS:
                try:
                    extracted = extractor_fn(abs_path, content)
                    # 将绝对路径替换为相对路径
                    for art in extracted:
                        art.file_path = rel_path
                    artifacts.extend(extracted)
                except Exception as e:
                    errors.append(f"提取失败 {rel_path} ({extractor_fn.__name__}): {e}")

            # ── 结构提取（Phase 6.2 新增）──
            # 对代码文件提取函数、类、方法等结构化符号
            language = _EXT_LANG.get(abs_path.suffix.lower())
            if language:
                try:
                    struct_result = extract_structure(abs_path, content, language)
                    for symbol in struct_result.symbols:
                        artifacts.append(_symbol_to_artifact(symbol, rel_path))

                    # ── Import 关系构建（Phase 6.2 Step 2A）──
                    placeholders, file_relations = _build_import_relations(
                        rel_path, struct_result.symbols, artifacts,
                    )
                    artifacts.extend(placeholders)
                    relations.extend(file_relations)

                    errors.extend(struct_result.errors)
                except Exception as e:
                    errors.append(f"结构提取失败 {rel_path}: {e}")

        return ExtractionResult(artifacts=artifacts, relations=relations, errors=errors)

    def _discover_files(self, project_path: Path) -> list[str]:
        """发现项目中的文件"""
        skip_dirs = {
            ".git", "__pycache__", "node_modules", ".venv", "venv",
            ".pytest_cache", ".smartdev", "dist", "build",
        }
        files = []
        for root, dirs, filenames in project_path.walk():
            dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith(".")]
            for fname in filenames:
                if fname.startswith(".") or fname.endswith((".pyc", ".pyo")):
                    continue
                rel = (root / fname).relative_to(project_path)
                files.append(str(rel))
        return sorted(files)

    def extract_incremental(self, project_path: Path,
                            changed_files: list[str]) -> ExtractionResult:
        """增量提取：只处理变化的文件

        用于文件变更后重新提取工件。
        """
        return self.extract(project_path, file_paths=changed_files)
