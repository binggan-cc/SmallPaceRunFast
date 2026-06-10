"""
security.review Guard Skill 测试 — Phase 11B Step 4

覆盖：
1. Skill 注册 + 基本属性
2. input_validation — 输入校验检查
3. path_traversal — 路径穿越检查
4. command_injection — 命令注入检查
5. sensitive_data — 敏感数据检查
6. hardcoded_secrets — 硬编码密钥检查
7. eval_exec — 动态代码执行检查
8. 建议命令生成
9. 空输入 / 无安全问题边界情况
10. Skill.run() 集成测试
11. 确定性验证
"""

from __future__ import annotations

from pathlib import Path

import pytest

from smartdev.core.guard_security import (
    SecurityResult,
    SecurityViolation,
    _check_command_injection,
    _check_eval_exec,
    _check_hardcoded_secrets,
    _check_input_validation,
    _check_path_traversal,
    _check_sensitive_data,
    _generate_security_suggestions,
    _has_sensitive_var_name,
    _has_user_input_var,
    _is_code_file,
    _is_env_file,
    check_security_review,
)
from smartdev.models import ProjectContext
from smartdev.skills.base import Skill


# ── Helpers ────────────────────────────────────────────────


def _ctx() -> ProjectContext:
    return ProjectContext(
        project_path=Path("/fake/project"),
        task_description="test security.review",
    )


def _make_lines(code: str) -> list[tuple[int, str]]:
    """将多行代码转换为 (行号, 文本) 列表。"""
    return [(i + 1, line) for i, line in enumerate(code.splitlines())]


def _all_added(lines: list[tuple[int, str]]) -> set[int]:
    """所有行都标记为新增。"""
    return {ln for ln, _ in lines}


def _run_check(check_func, code: str, file_path: str = "test.py"):
    """辅助运行单个检查函数。"""
    lines = _make_lines(code)
    return check_func(file_path, lines, _all_added(lines))


# ── Skill 注册验证 ───────────────────────────────────────────


def test_skill_registered():
    """import smartdev.skills 后 security.review 已注册。"""
    import smartdev.skills  # noqa: F401
    skill_cls = Skill.get_skill("security.review")
    assert skill_cls is not None


def test_skill_attributes():
    """验证 Skill 基本属性。"""
    skill = Skill.create("security.review")
    assert skill.name == "security.review"
    from smartdev.models import RiskLevel
    assert skill.risk_level == RiskLevel.R0
    assert skill.can_run(_ctx()) is True


# ── 辅助函数测试 ──────────────────────────────────────────────


class TestHelpers:
    def test_is_code_file_python(self):
        assert _is_code_file("src/main.py") is True
        assert _is_code_file("app.js") is True
        assert _is_code_file("utils.ts") is True

    def test_is_code_file_non_code(self):
        assert _is_code_file(".env") is False
        assert _is_code_file("config.json") is False
        assert _is_code_file("README.md") is False

    def test_is_env_file(self):
        assert _is_env_file(".env") is True
        assert _is_env_file(".env.local") is True
        assert _is_env_file(".env.production") is True
        assert _is_env_file("main.py") is False

    def test_has_user_input_var(self):
        assert _has_user_input_var("x = request.args.get('q')") is True
        assert _has_user_input_var("x = argv[1]") is True
        assert _has_user_input_var("x = input()") is True
        assert _has_user_input_var("x = normal_var") is False

    def test_has_sensitive_var_name(self):
        assert _has_sensitive_var_name("password = 'secret'") is True
        assert _has_sensitive_var_name("api_key = 'xxx'") is True
        assert _has_sensitive_var_name("token = 'abc'") is True
        assert _has_sensitive_var_name("name = 'foo'") is False


# ── input_validation 检查 ────────────────────────────────────


class TestInputValidation:
    def test_eval_input_error(self):
        violations = _run_check(_check_input_validation, "x = eval(input())")
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1
        assert any("input" in v.message.lower() for v in errors)

    def test_int_input_error(self):
        violations = _run_check(_check_input_validation, "x = int(input('Enter:'))")
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1

    def test_request_args_no_validation_warning(self):
        code = "name = request.args.get('name')\nresult = do_something(name)"
        violations = _run_check(_check_input_validation, code)
        warnings = [v for v in violations if v.severity == "warning"]
        # request.args.get 无校验 → warning
        assert len(warnings) >= 1

    def test_request_args_with_validation_passes(self):
        # 同一行有校验信号（if/try/assert/isinstance 等）
        code = "name = request.args.get('name') if validate(name) else None"
        violations = _run_check(_check_input_validation, code)
        # "validate" 在 _has_validation_sign 中，会被识别为有校验
        has_warning = any(
            v.severity == "warning" and "request" in v.message.lower()
            for v in violations
        )
        assert not has_warning

    def test_safe_code_no_violations(self):
        violations = _run_check(_check_input_validation, "x = 1 + 2\ny = x * 3")
        assert len(violations) == 0

    def test_comment_ignored(self):
        violations = _run_check(_check_input_validation, "# request.args.get('q')")
        assert len(violations) == 0


# ── path_traversal 检查 ──────────────────────────────────────


class TestPathTraversal:
    def test_os_path_join_with_user_input_warning(self):
        code = "path = os.path.join('/base', request.args.get('file'))"
        violations = _run_check(_check_path_traversal, code)
        assert len(violations) >= 1
        assert violations[0].severity == "warning"

    def test_open_with_user_input_warning(self):
        code = "f = open(sys.argv[1])"
        violations = _run_check(_check_path_traversal, code)
        assert len(violations) >= 1
        assert violations[0].severity == "warning"

    def test_path_with_resolve_passes(self):
        code = "path = Path(request.args.get('file')).resolve()"
        violations = _run_check(_check_path_traversal, code)
        # .resolve() 算安全处理
        assert len(violations) == 0

    def test_safe_path_no_user_input(self):
        code = "path = os.path.join('/base', 'static', filename)"
        violations = _run_check(_check_path_traversal, code)
        assert len(violations) == 0


# ── command_injection 检查 ───────────────────────────────────


class TestCommandInjection:
    def test_os_system_error(self):
        violations = _run_check(_check_command_injection, "os.system('ls -la')")
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1

    def test_os_popen_error(self):
        violations = _run_check(_check_command_injection, "os.popen('cat file')")
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1

    def test_subprocess_shell_true_error(self):
        violations = _run_check(
            _check_command_injection,
            "subprocess.run('ls', shell=True)"
        )
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1
        assert any("shell=True" in v.message for v in errors)

    def test_subprocess_with_user_input_warning(self):
        violations = _run_check(
            _check_command_injection,
            "subprocess.run(['echo', sys.argv[1]])"
        )
        warnings = [v for v in violations if v.severity == "warning"]
        assert len(warnings) >= 1

    def test_safe_subprocess(self):
        violations = _run_check(
            _check_command_injection,
            "subprocess.run(['ls', '-la'])"
        )
        assert len(violations) == 0


# ── sensitive_data 检查 ──────────────────────────────────────


class TestSensitiveData:
    def test_known_token_prefix_error(self):
        violations = _run_check(
            _check_sensitive_data,
            'token = "sk-proj-abc123def456ghi789jkl012mno345pqr678stu"'
        )
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1

    def test_github_token_prefix_error(self):
        violations = _run_check(
            _check_sensitive_data,
            'github_token = "ghp_abcdefghijklmnopqrstuvwxyz1234567890"'
        )
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1

    def test_hardcoded_password_warning(self):
        violations = _run_check(
            _check_sensitive_data,
            'password = "my_secret_pass_123"'
        )
        warnings = [v for v in violations if v.severity == "warning"]
        assert len(warnings) >= 1

    def test_placeholder_skipped(self):
        """占位符不应该标记。"""
        violations = _run_check(
            _check_sensitive_data,
            'api_key = "your-api-key-here"'
        )
        # "your-" 开头的占位符跳过
        assert len(violations) == 0

    def test_env_var_reference_skipped(self):
        violations = _run_check(
            _check_sensitive_data,
            'api_key = os.environ.get("API_KEY")'
        )
        # 环境变量引用不是硬编码
        # 实际上这不会匹配赋值模式因为等号右边不是纯字面量
        assert all(
            v.severity != "warning" or "硬编码" not in v.message
            for v in violations
        )

    def test_log_with_sensitive_var_info(self):
        violations = _run_check(
            _check_sensitive_data,
            'print(f"user token: {token}")'
        )
        infos = [v for v in violations if v.severity == "info"]
        assert len(infos) >= 1

    def test_env_file_in_changed_files_error(self):
        violations = _check_sensitive_data(
            "", [], set(), changed_files=[".env", "src/main.py"]
        )
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1
        assert any(".env" in v.message for v in errors)

    def test_env_local_in_changed_files_error(self):
        violations = _check_sensitive_data(
            "", [], set(), changed_files=[".env.local"]
        )
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1


# ── hardcoded_secrets 检查 ───────────────────────────────────


class TestHardcodedSecrets:
    def test_pem_private_key_error(self):
        code = '''key = """-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
-----END RSA PRIVATE KEY-----"""'''
        violations = _run_check(_check_hardcoded_secrets, code)
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1

    def test_jwt_token_warning(self):
        violations = _run_check(
            _check_hardcoded_secrets,
            'jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR"'
        )
        warnings = [v for v in violations if v.severity == "warning"]
        assert len(warnings) >= 1

    def test_high_entropy_string_info(self):
        # 生成一个高熵字符串
        violations = _run_check(
            _check_hardcoded_secrets,
            'secret_key = "xK9mP2vR7wQ4nB6jL8tY1cF3dH5gA0sZxK9mP2vR7wQ4nB6jL8tY"'
        )
        infos = [v for v in violations if v.severity == "info"]
        # 50字符且熵值高 → info
        assert len(infos) >= 1

    def test_low_entropy_string_no_violation(self):
        violations = _run_check(
            _check_hardcoded_secrets,
            'name = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"'
        )
        # 低熵（全是a）→ 不应标记
        assert len(violations) == 0

    def test_short_string_no_violation(self):
        violations = _run_check(
            _check_hardcoded_secrets,
            'key = "abc123"'
        )
        assert len(violations) == 0


# ── eval_exec 检查 ───────────────────────────────────────────


class TestEvalExec:
    def test_eval_error(self):
        violations = _run_check(_check_eval_exec, 'eval(user_input)')
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1

    def test_exec_error(self):
        violations = _run_check(_check_eval_exec, 'exec(code_string)')
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1

    def test_compile_error(self):
        violations = _run_check(_check_eval_exec, 'compile(src, "file", "exec")')
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) >= 1

    def test_dunder_import_warning(self):
        violations = _run_check(_check_eval_exec, '__import__("os")')
        warnings = [v for v in violations if v.severity == "warning"]
        assert len(warnings) >= 1

    def test_getattr_with_literal_no_violation(self):
        violations = _run_check(_check_eval_exec, 'getattr(obj, "attr_name")')
        # 第二个参数是字面量 → 安全
        assert len(violations) == 0

    def test_getattr_with_variable_info(self):
        violations = _run_check(_check_eval_exec, 'getattr(obj, attr_name)')
        infos = [v for v in violations if v.severity == "info"]
        assert len(infos) >= 1

    def test_safe_code_no_violation(self):
        violations = _run_check(_check_eval_exec, 'x = 1 + 2')
        assert len(violations) == 0


# ── 建议命令生成 ──────────────────────────────────────────────


class TestSuggestions:
    def test_python_suggestion(self):
        suggestions = _generate_security_suggestions(["src/main.py", "tests/test.py"])
        assert any("bandit" in s for s in suggestions)

    def test_js_ts_suggestion(self):
        suggestions = _generate_security_suggestions(["src/app.js", "src/utils.ts"])
        assert any("semgrep" in s for s in suggestions)

    def test_mixed_suggestion(self):
        suggestions = _generate_security_suggestions(["src/main.py", "src/app.js"])
        assert any("bandit" in s for s in suggestions)
        assert any("semgrep" in s for s in suggestions)

    def test_empty_no_suggestions(self):
        suggestions = _generate_security_suggestions([])
        assert suggestions == []


# ── check_security_review 核心函数测试 ────────────────────────


class TestCheckSecurityReview:
    def test_all_clean(self):
        """无安全问题。"""
        result = check_security_review(
            changed_files=["src/main.py"],
            file_contents={"src/main.py": "x = 1 + 2\ny = x * 3\nprint(y)\n"},
        )
        assert result.passed is True
        assert len(result.violations) == 0

    def test_env_file_in_changed_files(self):
        """.env 在变更列表中 → error。"""
        result = check_security_review(
            changed_files=[".env", "src/main.py"],
        )
        assert result.passed is False
        assert any(".env" in v.message for v in result.violations)

    def test_multiple_violations(self):
        """多个安全问题同时出现。"""
        code = '''import os
x = eval(input("cmd:"))
os.system("rm -rf /")
password = "hunter2"
'''
        result = check_security_review(
            changed_files=["src/danger.py"],
            file_contents={"src/danger.py": code},
        )
        # 至少应有 eval_exec 和 command_injection 和 sensitive_data
        rules = {v.rule for v in result.violations}
        assert "eval_exec" in rules
        assert "command_injection" in rules
        assert "sensitive_data" in rules

    def test_passed_with_warnings_only(self):
        """只有 warning/info 时 passed=True。"""
        code = 'name = request.args.get("name")\nresult = f"Hello {name}"\n'
        result = check_security_review(
            changed_files=["src/app.py"],
            file_contents={"src/app.py": code},
        )
        # 可能有 warning 但无 error → passed=True
        assert result.passed is True
        if result.violations:
            assert all(v.severity != "error" for v in result.violations)

    def test_suggestions_present(self):
        """Python 文件变更应有 bandit 建议。"""
        result = check_security_review(
            changed_files=["src/app.py"],
            file_contents={"src/app.py": "x = 1 + 2\n"},
        )
        assert "bandit" in " ".join(result.suggestions)

    def test_empty_input(self):
        """空变更列表。"""
        result = check_security_review(changed_files=[])
        assert result.passed is True

    def test_no_code_files(self):
        """只有非代码文件变更。"""
        result = check_security_review(
            changed_files=["README.md", "CHANGELOG.md"],
        )
        assert result.passed is True

    def test_checks_structure(self):
        """checks 包含所有 6 个类别。"""
        result = check_security_review(
            changed_files=["src/app.py"],
            file_contents={"src/app.py": "x = 1 + 2\n"},
        )
        expected_checks = [
            "input_validation", "path_traversal", "command_injection",
            "sensitive_data", "hardcoded_secrets", "eval_exec",
        ]
        for check_name in expected_checks:
            assert check_name in result.checks
            assert "triggered" in result.checks[check_name]
            assert "files" in result.checks[check_name]


# ── Skill.run() 集成测试 ────────────────────────────────────


class TestSkillRun:
    def test_skill_run_clean(self):
        """无安全问题的代码。"""
        skill = Skill.create("security.review")
        result = skill.run(_ctx(), {
            "changed_files": ["src/app.py"],
            "file_contents": {"src/app.py": "x = 1 + 2\n"},
        })
        assert result.success is True
        assert isinstance(result.data, dict)
        assert "passed" in result.data
        assert "checks" in result.data

    def test_skill_run_with_error(self):
        """有 error → success=False。"""
        skill = Skill.create("security.review")
        result = skill.run(_ctx(), {
            "changed_files": ["src/app.py"],
            "file_contents": {"src/app.py": "eval(user_input)\n"},
        })
        assert result.success is False

    def test_skill_run_empty_input(self):
        skill = Skill.create("security.review")
        result = skill.run(_ctx(), {})
        assert result.success is True

    def test_skill_run_next_steps(self):
        skill = Skill.create("security.review")
        result = skill.run(_ctx(), {
            "changed_files": ["src/app.py"],
            "file_contents": {"src/app.py": "x = 1\n"},
        })
        assert len(result.next_steps) > 0

    def test_skill_run_with_env_file(self):
        skill = Skill.create("security.review")
        result = skill.run(_ctx(), {
            "changed_files": [".env"],
        })
        assert result.success is False
        assert any(".env" in r for r in result.risks)


# ── 确定性验证 ──────────────────────────────────────────────


class TestDeterminism:
    def test_same_input_same_output(self):
        def run():
            return check_security_review(
                changed_files=["src/app.py"],
                file_contents={
                    "src/app.py": (
                        'password = "secret123"\n'
                        'eval(user_code)\n'
                        'os.system("ls")\n'
                    ),
                },
            )

        r1 = run()
        r2 = run()
        r3 = run()

        assert r1.passed == r2.passed == r3.passed
        assert len(r1.violations) == len(r2.violations) == len(r3.violations)
        assert r1.summary == r2.summary == r3.summary
        assert r1.suggestions == r2.suggestions == r3.suggestions

    def test_to_dict_deterministic(self):
        result = check_security_review(
            changed_files=["src/app.py"],
            file_contents={"src/app.py": 'password = "secret123"\n'},
        )
        d1 = result.to_dict()
        d2 = result.to_dict()
        assert d1 == d2


# ── 边界情况 ────────────────────────────────────────────────


class TestEdgeCases:
    def test_zero_division_code_has_no_security_issues(self):
        """纯业务逻辑不应有安全问题。"""
        result = check_security_review(
            changed_files=["src/math.py"],
            file_contents={"src/math.py": "def div(a, b):\n    return a / b\n"},
        )
        assert result.passed is True

    def test_mixed_language_js(self):
        """JS 文件检查。"""
        code = 'eval(userInput);\nconsole.log("token:", token);\n'
        result = check_security_review(
            changed_files=["src/app.js"],
            file_contents={"src/app.js": code},
        )
        # JS eval( 应被检测到（eval_exec 检查）
        assert len(result.violations) >= 1

    def test_multiple_files_aggregated(self):
        """多文件汇总报告。"""
        result = check_security_review(
            changed_files=["src/a.py", "src/b.py"],
            file_contents={
                "src/a.py": 'eval(user_input)\n',
                "src/b.py": 'password = "secret"\n',
            },
        )
        # 两个文件都应有违规
        files_with_violations = {v.file for v in result.violations}
        assert "src/a.py" in files_with_violations
        assert "src/b.py" in files_with_violations

    def test_data_model_to_dict(self):
        """to_dict 方法返回合法字典。"""
        v = SecurityViolation(
            rule="input_validation",
            severity="error",
            message="test",
            file="test.py",
            line=10,
        )
        d = v.to_dict()
        assert d["rule"] == "input_validation"
        assert d["severity"] == "error"
        assert d["line"] == 10

        result = SecurityResult(
            passed=True,
            checks={"test": {"triggered": False}},
            violations=[],
            suggestions=["bandit"],
            summary="ok",
        )
        d = result.to_dict()
        assert d["passed"] is True
        assert "bandit" in d["suggestions"]
        assert d["summary"] == "ok"

    def test_result_to_dict_comprehensive(self):
        """result.to_dict() 包含所有必需字段。"""
        result = check_security_review(
            changed_files=["src/app.py"],
            file_contents={"src/app.py": "x = 1\n"},
        )
        d = result.to_dict()
        required_keys = [
            "passed", "checks", "violations", "suggestions", "summary",
        ]
        for key in required_keys:
            assert key in d, f"Missing key: {key}"

    def test_too_short_sensitive_value_skipped(self):
        """短敏感值（≤3 字符）跳过。"""
        code = 'password = "ab"\n'
        result = check_security_review(
            changed_files=["src/a.py"],
            file_contents={"src/a.py": code},
        )
        # "ab" 只有 2 字符 → 不应触发硬编码凭证警告
        assert all(
            not (v.severity == "warning" and "password" in v.message.lower())
            for v in result.violations
        ) or len(result.violations) == 0

    def test_slack_token_detected(self):
        """Slack token 前缀应被检测。"""
        code = 'token = "xoxb-1234567890-1234567890123-abcdefghijklmnopqrstuvwx"'
        result = check_security_review(
            changed_files=["src/a.py"],
            file_contents={"src/a.py": code},
        )
        errors = [v for v in result.violations if v.severity == "error"]
        assert any("Slack" in v.message for v in errors)

    def test_diff_content_parsing(self):
        """从 diff 内容中提取新增行进行检查。"""
        diff = """diff --git a/src/app.py b/src/app.py
--- a/src/app.py
+++ b/src/app.py
@@ -1,2 +1,3 @@
 x = 1
+eval(user_input)
 y = 2
"""
        result = check_security_review(
            changed_files=["src/app.py"],
            diff_content=diff,
            file_contents={"src/app.py": "x = 1\neval(user_input)\ny = 2\n"},
        )
        # eval 应该被检测到
        assert any(
            "eval" in v.message.lower() or v.rule == "eval_exec"
            for v in result.violations
        )
