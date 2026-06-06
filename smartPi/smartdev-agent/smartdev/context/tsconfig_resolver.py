"""
SmartDev Agent — tsconfig/jsconfig paths alias 解析器

设计原理：
─────────
Phase 6.3 Step 5: 支持 TypeScript/JavaScript 项目中的 paths alias，
将 @/lib/foo、@core/utils 解析为项目内真实文件路径。

只做 baseUrl + paths 的轻量解析：
- 不支持 extends / references / 多文件继承
- 不支持 package exports / node_modules resolution
- 第一版只读根目录配置，不递归子包

alias 匹配规则：
1. 精确匹配: "@types": ["src/types.ts"] → import "@types" → src/types.ts
2. 通配符匹配: "@/*": ["src/*"] → import "@/lib/x" → src/lib/x

对应文档：
- phase-6.3-design.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AliasRule:
    """单条 alias 规则"""
    pattern: str          # 原始 pattern（如 "@/*", "@types"）
    is_wildcard: bool     # 是否包含 * 通配符
    prefix: str           # 前缀（* 之前的部分），通配符用；精确匹配时等于 pattern
    mappings: list[str]   # 映射目标列表（取第一个，如 ["src/*"]）


@dataclass
class TsConfigPaths:
    """从 tsconfig/jsconfig 解析出的 paths 配置"""
    base_url: str = "."
    rules: list[AliasRule] = field(default_factory=list)
    has_config: bool = False
    config_file: str = ""
    supports_extends: bool = False  # v1 不支持


def _parse_alias_rules(paths: dict) -> list[AliasRule]:
    """解析 tsconfig paths 字段为 AliasRule 列表

    tsconfig paths 格式：
    {
      "@/*": ["src/*"],
      "@types": ["src/types.ts"],
      "~/*": ["./lib/*"]
    }
    """
    rules = []
    for pattern, targets in paths.items():
        if not targets:
            continue
        mapping = targets[0]  # 取第一个 target（TypeScript 标准行为）
        is_wildcard = "*" in pattern
        prefix = pattern.split("*")[0] if is_wildcard else pattern
        rules.append(AliasRule(
            pattern=pattern,
            is_wildcard=is_wildcard,
            prefix=prefix,
            mappings=[mapping],
        ))
    # 精确匹配优先于通配符
    rules.sort(key=lambda r: (0 if not r.is_wildcard else 1, -len(r.prefix)))
    return rules


class TsConfigResolver:
    """tsconfig/jsconfig paths alias 解析器

    使用示例：
        resolver = TsConfigResolver(project_path)
        result = resolver.resolve("@/lib/foo")
        if result:
            print(result["mapped_path"])  # "src/lib/foo"
    """

    def __init__(self, project_path: Path) -> None:
        self.project_path = project_path
        self.paths = TsConfigPaths()
        self._load()

    def _load(self) -> None:
        """加载 tsconfig.json 或 jsconfig.json"""
        for config_name in ("tsconfig.json", "jsconfig.json"):
            config_path = self.project_path / config_name
            if not config_path.is_file():
                continue
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            co = data.get("compilerOptions", {})
            if not isinstance(co, dict):
                continue

            base_url = co.get("baseUrl", ".")
            paths_raw = co.get("paths", {})

            if not paths_raw or not isinstance(paths_raw, dict):
                # 有 tsconfig 但无 paths → alias 不启用
                continue

            rules = _parse_alias_rules(paths_raw)
            if not rules:
                continue

            self.paths = TsConfigPaths(
                base_url=str(base_url),
                rules=rules,
                has_config=True,
                config_file=config_name,
                supports_extends=False,
            )
            return  # 找到配置即停止

    def resolve(self, specifier: str) -> dict | None:
        """尝试将 specifier 匹配为 alias

        参数：
            specifier: import 模块说明符（如 "@/lib/foo", "@types"）

        返回：
            dict: {
                "matched_alias": "@/*",
                "mapped_path": "src/lib/foo",
                "mapping": "src/*",
            }
            None: 不匹配任何 alias
        """
        if not self.paths.has_config:
            return None

        for rule in self.paths.rules:
            if rule.is_wildcard:
                # 通配符匹配：specifier 去掉 prefix 后的部分替换 mapping 中的 *
                if specifier.startswith(rule.prefix):
                    suffix = specifier[len(rule.prefix):]
                    mapping = rule.mappings[0]
                    if "*" in mapping:
                        resolved = mapping.replace("*", suffix)
                    else:
                        resolved = mapping + suffix
                    return {
                        "matched_alias": rule.pattern,
                        "mapped_path": resolved,
                        "mapping": mapping,
                    }
            else:
                # 精确匹配
                if specifier == rule.pattern:
                    return {
                        "matched_alias": rule.pattern,
                        "mapped_path": rule.mappings[0],
                        "mapping": rule.mappings[0],
                    }

        return None

    def resolve_path(self, specifier: str) -> str | None:
        """便捷方法：直接返回 mapped_path 或 None"""
        result = self.resolve(specifier)
        return result["mapped_path"] if result else None
