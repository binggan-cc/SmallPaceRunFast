"""
Guard: security.review — 安全审查清单（R0 只读）

功能：
─────
对 patch 或受影响文件做确定性安全 checklist 检查。不替代专业安全审计，
但覆盖 AI 生成代码最常见的 6 类安全问题：

  1. input_validation  — 输入校验缺失
  2. path_traversal     — 路径穿越风险
  3. command_injection  — 命令注入风险
  4. sensitive_data     — 敏感数据泄露
  5. hardcoded_secrets  — 硬编码密钥
  6. eval_exec          — 动态代码执行

设计约束：
─────────
- 零外部依赖（标准库 + re）
- 确定性规则引擎，不调用模型
- 无 git 环境也能运行（基于显式输入）
- R0 只读 — 不修改任何文件
- 第一版只做文本模式匹配，不做 AST 解析
- 外部工具只输出建议，不执行（bandit / semgrep）

对应文档：
- docs/phase-11b-design.md §3.4（security.review 详细设计）
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ──────────────────────────────────────────────────


@dataclass
class SecurityViolation:
    """单条安全检查违规。

    Attributes:
        rule:     违规规则名（input_validation / path_traversal / ...）
        severity: 严重程度（error / warning / info）
        message:  人类可读说明
        file:     发现违规的文件路径
        line:     行号（如果可确定）
        detail:   补充信息
    """

    rule: str
    severity: str
    message: str
    file: str = ""
    line: int | None = None
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "message": self.message,
            "file": self.file,
            "line": self.line,
            "detail": self.detail,
        }


@dataclass
class SecurityResult:
    """security.review 检查结果。

    Attributes:
        passed:      是否通过（无 error 级别违规）
        checks:      各项检查结果
        violations:  违规列表
        suggestions: 外部工具建议命令
        summary:     人类可读摘要
    """

    passed: bool = True
    checks: dict = field(default_factory=dict)
    violations: list[SecurityViolation] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "violations": [v.to_dict() for v in self.violations],
            "suggestions": self.suggestions,
            "summary": self.summary,
        }


# ── 代码文件扩展名 ────────────────────────────────────────────

_PYTHON_EXTS = {".py", ".pyw"}
_JS_TS_EXTS = {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
_HTML_EXTS = {".html", ".htm", ".vue", ".svelte"}
_CODE_EXTS = _PYTHON_EXTS | _JS_TS_EXTS

# ── 危险函数名模式 ────────────────────────────────────────────

# 用户输入来源变量名关键词
_USER_INPUT_KEYWORDS = [
    "request", "req", "argv", "input", "stdin",
    "params", "query", "body", "form", "args",
    "environ", "getenv",
]

# 敏感变量名关键词
_SENSITIVE_VAR_KEYWORDS = [
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "private_key", "privatekey", "access_key", "accesskey",
    "credential", "auth", "pwd",
]

# 已知的 API Token 前缀模式
_TOKEN_PREFIX_PATTERNS = [
    (r'\b(sk-[a-zA-Z0-9-]{20,})', "OpenAI API key (sk-...)"),
    (r'\b(ghp_[a-zA-Z0-9]{36,})', "GitHub personal access token (ghp_...)"),
    (r'\b(gho_[a-zA-Z0-9]{36,})', "GitHub OAuth token (gho_...)"),
    (r'\b(xoxb-[0-9]+-[0-9]+-[a-zA-Z0-9]+)', "Slack bot token (xoxb-...)"),
    (r'\b(xoxp-[0-9]+-[0-9]+-[a-zA-Z0-9]+)', "Slack user token (xoxp-...)"),
    (r'\b(gitlab_[a-zA-Z0-9]{20,})', "GitLab token"),
]


# ── 辅助函数 ──────────────────────────────────────────────────


def _is_code_file(file_path: str) -> bool:
    """判断是否为代码文件（非 .env / .json / .yaml 等配置）。"""
    return Path(file_path).suffix in _CODE_EXTS


def _is_html_file(file_path: str) -> bool:
    """判断是否为 HTML/模板 文件。"""
    return Path(file_path).suffix in _HTML_EXTS


def _is_python_file(file_path: str) -> bool:
    return Path(file_path).suffix in _PYTHON_EXTS


def _is_js_ts_file(file_path: str) -> bool:
    return Path(file_path).suffix in _JS_TS_EXTS


def _is_env_file(file_path: str) -> bool:
    """判断是否为环境变量/机密文件。"""
    name = Path(file_path).name
    return name in (".env", ".env.local", ".env.production", ".env.development")


def _has_user_input_var(text: str) -> bool:
    """检查文本中是否包含用户输入变量引用。"""
    for kw in _USER_INPUT_KEYWORDS:
        # 匹配变量名引用（不作为子串匹配，防止误报如 'require'）
        if re.search(rf'\b{re.escape(kw)}\b', text, re.IGNORECASE):
            return True
    return False


def _has_sensitive_var_name(text: str) -> bool:
    """检查文本中是否包含敏感变量名。"""
    for kw in _SENSITIVE_VAR_KEYWORDS:
        if re.search(rf'\b{re.escape(kw)}\b', text, re.IGNORECASE):
            return True
    return False


# ── 1. input_validation 检查 ──────────────────────────────────


def _check_input_validation(
    file_path: str,
    lines: list[tuple[int, str]],
    is_added_line: set[int],
) -> list[SecurityViolation]:
    """检查输入校验缺失。

    规则：
      - request.args.get( / request.form[ / req.body 后无校验 → warning
      - int(input()) / eval(input()) → error
      - HTML 新文件含 <input / <form 但无 required / pattern → info
    """
    violations: list[SecurityViolation] = []
    added_lines = [(ln, text) for ln, text in lines if ln in is_added_line]

    for ln, text in added_lines:
        stripped = text.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        # int(input()) / eval(input())
        if re.search(r'\b(int|float|eval|exec)\s*\(\s*input\s*\(', stripped):
            violations.append(SecurityViolation(
                rule="input_validation",
                severity="error",
                message=f"用户输入直接传给 {stripped[:40]}...（代码执行风险）",
                file=file_path,
                line=ln,
                detail={"pattern": "eval/exec of input()", "code": stripped[:80]},
            ))
            continue

        # request.args.get( / request.form[ / req.body 无校验迹象
        if re.search(r'(request\.(args|form|json|query|body)|req\.(body|query|params))', stripped, re.IGNORECASE):
            # 查找是否有验证迹象
            if not _has_validation_sign(stripped):
                violations.append(SecurityViolation(
                    rule="input_validation",
                    severity="warning",
                    message=f"用户输入读取无明显校验: {stripped[:60]}",
                    file=file_path,
                    line=ln,
                    detail={"pattern": "unvalidated_input", "code": stripped[:80]},
                ))

    # HTML 文件检查：<input / <form 但无 required / pattern
    if _is_html_file(file_path) and (file_path not in _seen_files_cache):
        # 收集所有新增行来检查
        file_text = "\n".join(text for _, text in added_lines)
        input_tags = re.findall(r'<input\b[^>]*>', file_text, re.IGNORECASE)
        form_tags = re.findall(r'<form\b[^>]*>', file_text, re.IGNORECASE)

        for tag in input_tags:
            if not re.search(r'\b(required|pattern)\b', tag, re.IGNORECASE):
                violations.append(SecurityViolation(
                    rule="input_validation",
                    severity="info",
                    message=f"HTML <input> 标签无 required/pattern 属性",
                    file=file_path,
                    detail={"pattern": "html_input_no_validation", "tag": tag[:80]},
                ))
        for tag in form_tags:
            if not re.search(r'\b(required|pattern)\b', tag, re.IGNORECASE):
                violations.append(SecurityViolation(
                    rule="input_validation",
                    severity="info",
                    message="HTML <form> 标签无 required/pattern 属性",
                    file=file_path,
                    detail={"pattern": "html_form_no_validation", "tag": tag[:80]},
                ))

    return violations


def _has_validation_sign(code: str) -> bool:
    """检查代码中是否有输入校验的迹象（保守检测）。

    注意：不将 .get( / .post( 等 HTTP 方法视为校验，
    因为它们在 request.args.get( 等位置本身就是输入入口。
    """
    validation_patterns = [
        r'\.(isdigit|isnumeric|isalpha|isalnum|strip|replace)\(',
        r'\b(int|float|str)\s*\(',       # 类型转换算轻微校验
        r'\b(if|assert|raise|validate|check|verify|sanitize|escape)\b',
        r'\btry\b',
    ]
    return any(re.search(p, code, re.IGNORECASE) for p in validation_patterns)


# 全局缓存，用于跨多次调用记住已检查的 HTML 文件
_seen_files_cache: set[str] = set()


# ── 2. path_traversal 检查 ────────────────────────────────────


def _check_path_traversal(
    file_path: str,
    lines: list[tuple[int, str]],
    is_added_line: set[int],
) -> list[SecurityViolation]:
    """检查路径穿越风险。

    规则：
      - os.path.join( 参数含用户输入变量 → warning
      - open( 参数含 request/argv/input 相关变量 → warning
      - Path( 拼接用户输入且无 .resolve() 校验 → warning
    """
    violations: list[SecurityViolation] = []
    added_lines = [(ln, text) for ln, text in lines if ln in is_added_line]

    for ln, text in added_lines:
        stripped = text.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        # os.path.join( / Path( 参数含用户输入变量
        path_join_match = re.search(
            r'(os\.path\.join|pathlib\.Path|Path)\s*\(', stripped
        )
        open_match = re.search(r'\bopen\s*\(', stripped)

        if path_join_match or open_match:
            if _has_user_input_var(stripped):
                # 检查是否有 .resolve() 或路径白名单校验
                if not _has_path_sanitization(stripped):
                    severity = "warning"
                    if open_match:
                        detail_pattern = "file_open_with_user_input"
                    else:
                        detail_pattern = "path_join_with_user_input"

                    violations.append(SecurityViolation(
                        rule="path_traversal",
                        severity=severity,
                        message=f"文件路径操作使用用户输入且无校验: {stripped[:60]}",
                        file=file_path,
                        line=ln,
                        detail={"pattern": detail_pattern, "code": stripped[:80]},
                    ))

    return violations


def _has_path_sanitization(code: str) -> bool:
    """检查代码是否有路径安全处理迹象。"""
    sanitization_patterns = [
        r'\.resolve\(',
        r'\bos\.path\.(realpath|abspath|normpath)\(',
        r'\b(allowlist|whitelist|safe_paths|ALLOWED|allowed)',
        r'\bif\s+.*\bin\b',  # 可能存在 in 检查
    ]
    return any(re.search(p, code, re.IGNORECASE) for p in sanitization_patterns)


# ── 3. command_injection 检查 ─────────────────────────────────


def _check_command_injection(
    file_path: str,
    lines: list[tuple[int, str]],
    is_added_line: set[int],
) -> list[SecurityViolation]:
    """检查命令注入风险。

    规则：
      - subprocess.run(..., shell=True) → error
      - os.system( / os.popen( → error
      - subprocess.run( 参数含用户输入变量名 → warning
    """
    violations: list[SecurityViolation] = []
    added_lines = [(ln, text) for ln, text in lines if ln in is_added_line]

    for ln, text in added_lines:
        stripped = text.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        # os.system( / os.popen( → error
        if re.search(r'\bos\.(system|popen)\s*\(', stripped):
            violations.append(SecurityViolation(
                rule="command_injection",
                severity="error",
                message=f"使用 os.{'system' if 'system' in stripped else 'popen'}() 存在命令注入风险",
                file=file_path,
                line=ln,
                detail={"pattern": "os_system_or_popen", "code": stripped[:80]},
            ))
            continue

        # eval( / exec( 也属于命令执行（如果还没在 eval_exec 中捕获）
        # 不在此处重复检测

        # subprocess.run(..., shell=True) → error
        if re.search(r'\bsubprocess\.(run|call|check_output|Popen)\s*\(', stripped):
            if re.search(r'\bshell\s*=\s*True\b', stripped):
                violations.append(SecurityViolation(
                    rule="command_injection",
                    severity="error",
                    message=f"subprocess 使用 shell=True 存在 Shell 注入风险",
                    file=file_path,
                    line=ln,
                    detail={"pattern": "subprocess_shell_true", "code": stripped[:80]},
                ))
            elif _has_user_input_var(stripped):
                # subprocess 参数含用户输入
                violations.append(SecurityViolation(
                    rule="command_injection",
                    severity="warning",
                    message=f"subprocess 调用参数含用户输入变量: {stripped[:60]}",
                    file=file_path,
                    line=ln,
                    detail={"pattern": "subprocess_with_user_input", "code": stripped[:80]},
                ))

    return violations


# ── 4. sensitive_data 检查 ────────────────────────────────────


def _check_sensitive_data(
    file_path: str,
    lines: list[tuple[int, str]],
    is_added_line: set[int],
    changed_files: list[str] | None = None,
) -> list[SecurityViolation]:
    """检查敏感数据泄露。

    规则：
      - password / secret / token / api_key 赋值为字符串字面量 → warning
      - print( / console.log( 输出 password/token 等变量 → info
      - sk- / ghp_ / gho_ / xoxb- / xoxp- 等 token 前缀 → error
      - .env / .env.local 在 changed_files 中 → error
    """
    violations: list[SecurityViolation] = []
    added_lines = [(ln, text) for ln, text in lines if ln in is_added_line]

    for ln, text in added_lines:
        stripped = text.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        # 检测已知 token 前缀 → error
        for pattern, desc in _TOKEN_PREFIX_PATTERNS:
            if re.search(pattern, stripped):
                # 排除 JWT_SECRET 这种变量名定义
                if "JWTSECRET" in pattern:
                    severity = "info"
                else:
                    severity = "error"
                violations.append(SecurityViolation(
                    rule="sensitive_data",
                    severity=severity,
                    message=f"检测到可能的 {desc}",
                    file=file_path,
                    line=ln,
                    detail={"pattern": "known_token_prefix", "desc": desc},
                ))
                break  # 一行只报一次 token 前缀

        # 敏感变量赋值为字符串字面量 → warning
        # 匹配: password = "xxx" / secret = 'xxx' / token = "xxx"
        sensitive_assign = re.match(
            r'^([a-zA-Z_]\w*)\s*[:=]\s*(["\'])(.+)\2\s*$', stripped
        )
        if sensitive_assign:
            var_name = sensitive_assign.group(1)
            literal_value = sensitive_assign.group(3)
            if _has_sensitive_var_name(var_name) and len(literal_value) > 3:
                severity = "warning"
                # 如果值看起来是占位符或环境变量引用，降级
                if re.match(r'^(your[-_\s]|xxx|TODO|FIXME|<|$)',
                           literal_value, re.IGNORECASE):
                    continue  # 跳过占位符
                if literal_value.startswith("$") or "${" in literal_value:
                    continue  # 跳过环境变量引用

                violations.append(SecurityViolation(
                    rule="sensitive_data",
                    severity=severity,
                    message=f"变量 '{var_name}' 赋值为硬编码敏感值",
                    file=file_path,
                    line=ln,
                    detail={"pattern": "hardcoded_credential",
                           "variable": var_name},
                ))

        # print( / console.log( 输出敏感变量 → info
        log_match = re.search(
            r'\b(print|console\.log|logger\.(info|debug|warn|error))\s*\(', stripped
        )
        if log_match:
            if _has_sensitive_var_name(stripped):
                violations.append(SecurityViolation(
                    rule="sensitive_data",
                    severity="info",
                    message=f"日志输出可能包含敏感变量: {stripped[:60]}",
                    file=file_path,
                    line=ln,
                    detail={"pattern": "sensitive_logging", "code": stripped[:80]},
                ))

    # .env 文件检查 → error
    if changed_files:
        for f in changed_files:
            if _is_env_file(f):
                violations.append(SecurityViolation(
                    rule="sensitive_data",
                    severity="error",
                    message=f"环境变量文件 '{f}' 出现在变更列表中，可能泄露密钥",
                    file=f,
                    detail={"pattern": "env_file_in_diff"},
                ))

    return violations


# ── 5. hardcoded_secrets 检查 ─────────────────────────────────


def _check_hardcoded_secrets(
    file_path: str,
    lines: list[tuple[int, str]],
    is_added_line: set[int],
) -> list[SecurityViolation]:
    """检查硬编码密钥。

    规则：
      - 32+ 位高熵样式字符串字面量 → info
      - -----BEGIN ... PRIVATE KEY----- → error
      - JWT eyJ... 样式 token → warning
    """
    violations: list[SecurityViolation] = []
    added_lines = [(ln, text) for ln, text in lines if ln in is_added_line]

    for ln, text in added_lines:
        stripped = text.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        # PEM 私钥 → error
        if re.search(r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----', stripped):
            violations.append(SecurityViolation(
                rule="hardcoded_secrets",
                severity="error",
                message="检测到 PEM 私钥硬编码",
                file=file_path,
                line=ln,
                detail={"pattern": "pem_private_key"},
            ))
            continue

        # JWT token 硬编码 → warning
        jwt_match = re.search(r'["\']?(eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{10,})["\']?', stripped)
        if jwt_match:
            violations.append(SecurityViolation(
                rule="hardcoded_secrets",
                severity="warning",
                message="检测到硬编码 JWT token",
                file=file_path,
                line=ln,
                detail={"pattern": "hardcoded_jwt"},
            ))
            continue

        # 32+ 位高熵样式字符串（保守检测） → info
        # 匹配引导内的长字符串字面量
        long_string_matches = re.findall(
            r'["\']([A-Za-z0-9+/=_-]{32,})["\']', stripped
        )
        for match in long_string_matches:
            # 计算简单熵值：唯一字符比例
            entropy = len(set(match)) / len(match) if match else 0
            if entropy > 0.45:  # 高熵阈值
                violations.append(SecurityViolation(
                    rule="hardcoded_secrets",
                    severity="info",
                    message=f"发现高熵字符串（{len(match)} 字符），可能是硬编码密钥",
                    file=file_path,
                    line=ln,
                    detail={
                        "pattern": "high_entropy_string",
                        "length": len(match),
                        "entropy": round(entropy, 2),
                    },
                ))
                break  # 一行只报一次

    return violations


# ── 6. eval_exec 检查 ─────────────────────────────────────────


def _check_eval_exec(
    file_path: str,
    lines: list[tuple[int, str]],
    is_added_line: set[int],
) -> list[SecurityViolation]:
    """检查动态代码执行。

    规则：
      - eval( / exec( / compile( → error
      - __import__( → warning
      - getattr( / setattr( 参数非字面量 → info
    """
    violations: list[SecurityViolation] = []
    added_lines = [(ln, text) for ln, text in lines if ln in is_added_line]

    for ln, text in added_lines:
        stripped = text.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("//"):
            continue

        # eval( / exec( / compile( → error
        if re.search(r'\b(eval|exec|compile)\s*\(', stripped):
            func_name = "eval" if "eval" in stripped else ("exec" if "exec" in stripped else "compile")
            violations.append(SecurityViolation(
                rule="eval_exec",
                severity="error",
                message=f"使用 {func_name}() 存在动态代码执行风险",
                file=file_path,
                line=ln,
                detail={"pattern": f"{func_name}_call", "code": stripped[:80]},
            ))
            continue

        # __import__( → warning
        if re.search(r'\b__import__\s*\(', stripped):
            violations.append(SecurityViolation(
                rule="eval_exec",
                severity="warning",
                message="使用 __import__() 存在动态导入风险",
                file=file_path,
                line=ln,
                detail={"pattern": "dunder_import", "code": stripped[:80]},
            ))
            continue

        # getattr( / setattr( 参数非字面量 → info
        ga_match = re.search(r'\b(getattr|setattr)\s*\(', stripped)
        if ga_match:
            func = ga_match.group(1)
            # 简化检测：查找第二个参数是否为字符串字面量
            # getattr(obj, 'attr_name') 是安全的；getattr(obj, var) 有风险
            args_match = re.search(
                rf'\b{func}\s*\(\s*\w+\s*,\s*["\']', stripped
            )
            if not args_match:
                # 第二个参数不是字面量，可能是动态的
                violations.append(SecurityViolation(
                    rule="eval_exec",
                    severity="info",
                    message=f"{func}() 参数可能非静态: {stripped[:60]}",
                    file=file_path,
                    line=ln,
                    detail={"pattern": "dynamic_getattr_setattr", "code": stripped[:80]},
                ))

    return violations


# ── Suggestion 生成 ───────────────────────────────────────────


def _generate_security_suggestions(changed_files: list[str]) -> list[str]:
    """根据变更文件类型生成安全审计建议。"""
    suggestions: list[str] = []
    has_python = any(_is_python_file(f) for f in changed_files)
    has_js_ts = any(_is_js_ts_file(f) for f in changed_files)

    if has_python:
        suggestions.append("bandit -r <project>")
    if has_js_ts:
        suggestions.append("semgrep --config=auto")
    if has_python and has_js_ts:
        # 多语言：semgrep 最通用
        if "semgrep --config=auto" not in suggestions:
            suggestions.append("semgrep --config=auto")

    return suggestions


# ── 核心规则引擎 ──────────────────────────────────────────────


def _parse_file_to_lines(
    file_path: str,
    content: str,
) -> list[tuple[int, str]]:
    """将文件内容按行解析为 (行号, 文本) 列表。"""
    return [(i + 1, line) for i, line in enumerate(content.splitlines())]


def _get_added_lines_from_diff(
    diff_content: str,
    file_path: str,
) -> set[int]:
    """从 unified diff 中提取指定文件的新增行号集合。

    解析 @@ -a,b +c,d @@ 头部获取新文件行号范围，
    然后统计 + 开头的行对应的行号。
    """
    added_lines: set[int] = set()

    # 查找对应文件的 diff 块
    # 每个 diff 块以 @@ 行开头
    pattern = re.compile(
        rf'^@@\s+-(\d+),?\d*\s+\+(\d+),?\d*\s+@@',
        re.MULTILINE
    )

    # 按文件分割 diff
    file_blocks = re.split(
        r'^diff --git ', diff_content, flags=re.MULTILINE
    )

    target_file = Path(file_path).name
    # 也匹配完整路径
    target_variants = {target_file, file_path, f"a/{file_path}", f"b/{file_path}"}

    for block in file_blocks:
        if not block.strip():
            continue
        block = "diff --git " + block if not block.startswith("diff --git ") else block

        # 提取文件路径
        file_match = re.search(r'^\+\+\+ b/(.+)$', block, re.MULTILINE)
        if not file_match:
            continue
        fpath = file_match.group(1).strip()
        if fpath != file_path and Path(fpath).name != target_file:
            continue

        # 解析该文件的 hunk
        for hunk_match in re.finditer(
            r'^@@\s+-(\d+),?\d*\s+\+(\d+),?\d*\s+@@', block, re.MULTILINE
        ):
            new_start = int(hunk_match.group(2))
            # 从 hunk 头部后开始跟踪新文件行号
            hunk_start = hunk_match.end()
            hunk_text = block[hunk_start:]
            # 取到下一个 @@ 或文件块结束
            next_hunk = re.search(r'^@@\s+-', hunk_text, re.MULTILINE)
            if next_hunk:
                hunk_text = hunk_text[:next_hunk.start()]
            # strip leading newline so splitlines() doesn't produce empty first element
            hunk_text = hunk_text.lstrip('\n')

            new_line_num = new_start
            for hunk_line in hunk_text.splitlines():
                if not hunk_line:
                    new_line_num += 1
                    continue
                if hunk_line.startswith("+") and not hunk_line.startswith("+++"):
                    added_lines.add(new_line_num)
                    new_line_num += 1
                elif hunk_line.startswith("-"):
                    # 删除行不增加新文件行号
                    pass
                else:
                    # 上下文行
                    new_line_num += 1

    return added_lines


def check_security_review(
    changed_files: list[str],
    diff_content: str | None = None,
    file_contents: dict[str, str] | None = None,
) -> SecurityResult:
    """执行 security.review 检查。

    对每个变更文件（或通过 file_contents 提供的文件）执行 6 类安全检查。
    优先使用 diff_content 提取新增行（只检查新增代码），
    降级为 file_contents 全量扫描。

    Args:
        changed_files: 变更文件列表（相对项目根目录的路径字符串）
        diff_content:  完整的 unified diff 文本（可选，用于增量分析）
        file_contents: 文件内容映射 {path: content}（可选，用于全量扫描）

    Returns:
        SecurityResult: 结构化检查结果
    """
    violations: list[SecurityViolation] = []
    checks: dict = {
        "input_validation": {"triggered": False, "files": [], "violation_count": 0},
        "path_traversal": {"triggered": False, "files": [], "violation_count": 0},
        "command_injection": {"triggered": False, "files": [], "violation_count": 0},
        "sensitive_data": {"triggered": False, "files": [], "violation_count": 0},
        "hardcoded_secrets": {"triggered": False, "files": [], "violation_count": 0},
        "eval_exec": {"triggered": False, "files": [], "violation_count": 0},
    }

    # 确定要检查的文件及内容
    files_to_check: dict[str, str] = {}

    # 从 file_contents 获取
    if file_contents:
        for path, content in file_contents.items():
            files_to_check[path] = content

    # 从 changed_files 补充（标记为需检查，但无内容时跳过代码检查）
    for f in changed_files:
        if f not in files_to_check and _is_code_file(f):
            # 没有内容可用，无法做代码级检查
            pass

    # 没有内容时无法做代码检查，但仍可做 .env 等文件名检查
    if not files_to_check:
        # 仅做 .env 文件检查
        env_violations = _check_sensitive_data(
            "", [], set(), changed_files=changed_files
        )
        violations.extend(env_violations)
        if env_violations:
            checks["sensitive_data"]["triggered"] = True
            checks["sensitive_data"]["violation_count"] = len(env_violations)
            for v in env_violations:
                if v.file not in checks["sensitive_data"]["files"]:
                    checks["sensitive_data"]["files"].append(v.file)

        suggestions = _generate_security_suggestions(changed_files)

        error_count = sum(1 for v in violations if v.severity == "error")
        warning_count = sum(1 for v in violations if v.severity == "warning")
        info_count = sum(1 for v in violations if v.severity == "info")
        passed = error_count == 0

        if passed and not violations:
            summary = "✅ security.review 通过：无安全问题"
        elif passed:
            summary = (
                f"⚠ security.review 通过（{warning_count} 个警告"
                + (f"，{info_count} 个提示" if info_count else "")
                + "）"
            )
        else:
            summary = (
                f"❌ security.review 未通过（{error_count} 个错误"
                + (f"，{warning_count} 个警告" if warning_count else "")
                + "）"
            )

        return SecurityResult(
            passed=passed,
            checks=checks,
            violations=violations,
            suggestions=suggestions,
            summary=summary,
        )

    # 对每个文件执行检查
    for file_path, content in files_to_check.items():
        lines = _parse_file_to_lines(file_path, content)

        # 确定新增行
        is_added_line: set[int] = set()
        if diff_content:
            is_added_line = _get_added_lines_from_diff(diff_content, file_path)

        # 如果没有 diff 信息，全量扫描（检查所有行）
        if not is_added_line:
            is_added_line = {ln for ln, _ in lines}

        # 执行 6 类检查
        check_funcs = [
            ("input_validation", _check_input_validation),
            ("path_traversal", _check_path_traversal),
            ("command_injection", _check_command_injection),
            ("sensitive_data", lambda fp, lns, ial: _check_sensitive_data(
                fp, lns, ial, changed_files=changed_files
            )),
            ("hardcoded_secrets", _check_hardcoded_secrets),
            ("eval_exec", _check_eval_exec),
        ]

        for rule_name, check_func in check_funcs:
            file_violations = check_func(file_path, lines, is_added_line)
            if file_violations:
                checks[rule_name]["triggered"] = True
                checks[rule_name]["violation_count"] += len(file_violations)
                if file_path not in checks[rule_name]["files"]:
                    checks[rule_name]["files"].append(file_path)
                violations.extend(file_violations)

    # 也检查非代码文件（.env 等）
    env_violations = _check_sensitive_data(
        "", [], set(), changed_files=changed_files
    )
    for v in env_violations:
        # 避免重复
        if not any(existing.file == v.file and existing.rule == v.rule
                   for existing in violations):
            violations.append(v)
            checks["sensitive_data"]["triggered"] = True
            checks["sensitive_data"]["violation_count"] += 1
            if v.file not in checks["sensitive_data"]["files"]:
                checks["sensitive_data"]["files"].append(v.file)

    # 生成建议
    suggestions = _generate_security_suggestions(
        changed_files if changed_files else list(files_to_check.keys())
    )

    # 构建摘要
    error_count = sum(1 for v in violations if v.severity == "error")
    warning_count = sum(1 for v in violations if v.severity == "warning")
    info_count = sum(1 for v in violations if v.severity == "info")
    passed = error_count == 0

    if passed and not violations:
        summary = (
            f"✅ security.review 通过："
            f"{len(files_to_check)} 个文件无安全问题"
        )
    elif passed:
        parts = ["⚠ security.review 通过"]
        detail_parts = []
        if warning_count:
            detail_parts.append(f"{warning_count} 个警告")
        if info_count:
            detail_parts.append(f"{info_count} 个提示")
        parts.append("，".join(detail_parts))
        summary = "：".join(parts)
    else:
        parts = [
            f"❌ security.review 未通过（{error_count} 个错误"
            + (f"，{warning_count} 个警告" if warning_count else "")
            + (f"，{info_count} 个提示" if info_count else "")
            + "）"
        ]
        error_rules = set(v.rule for v in violations if v.severity == "error")
        parts.append(f"涉及: {', '.join(sorted(error_rules))}")
        summary = "；".join(parts)

    return SecurityResult(
        passed=passed,
        checks=checks,
        violations=violations,
        suggestions=suggestions,
        summary=summary,
    )
