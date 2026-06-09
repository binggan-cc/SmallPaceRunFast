"""
CLI 测试

验证：
1. --help 输出正确
2. --version 输出正确
3. list 命令列出所有 Skill
4. scan 命令在有效项目上运行
5. plan 命令在有效项目上运行
6. 无效路径返回错误码

注意：所有 subprocess 调用必须通过 _run_cli() 确保 PYTHONPATH 正确，
      因为 smartdev 是本地包，未通过 pip install 安装。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# smartPi/smartdev-agent/（包含 smartdev/ 包的目录）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _cli_env() -> dict:
    """构建包含正确 PYTHONPATH 的环境变量"""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    project_root = str(_PROJECT_ROOT)
    if existing:
        env["PYTHONPATH"] = project_root + os.pathsep + existing
    else:
        env["PYTHONPATH"] = project_root
    return env


def _run_cli(*args: str, **kwargs) -> subprocess.CompletedProcess:
    """运行 smartdev CLI 命令，自动设置 PYTHONPATH"""
    cmd = [sys.executable, "-m", "smartdev"] + list(args)
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("env", _cli_env())
    return subprocess.run(cmd, **kwargs)


class TestCLI:
    """CLI 命令行测试"""

    def test_help(self):
        """--help 输出包含用法说明"""
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "SmartDev Agent" in result.stdout
        assert "scan" in result.stdout
        assert "plan" in result.stdout
        assert "list" in result.stdout

    def test_version(self):
        """--version 输出版本号"""
        result = _run_cli("--version")
        assert result.returncode == 0
        assert "smartdev" in result.stdout

    def test_list(self):
        """list 命令列出所有 Skill"""
        result = _run_cli("list")
        assert result.returncode == 0
        assert "repo.scan" in result.stdout
        assert "task.plan" in result.stdout

    def test_scan(self, tmp_path: Path):
        """scan 命令在有效项目上运行"""
        # 创建一个最小 Python 项目（需要标记文件触发检测）
        (tmp_path / "requirements.txt").write_text("requests\n")
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "README.md").write_text("# Test\n")

        result = _run_cli("scan", "--project", str(tmp_path))
        assert result.returncode == 0
        assert "扫描完成" in result.stdout
        assert "Python" in result.stdout

    def test_plan(self, tmp_path: Path):
        """plan 命令在有效项目上运行"""
        (tmp_path / "main.py").write_text("pass\n")

        result = _run_cli("plan", "--project", str(tmp_path), "--task", "测试任务")
        assert result.returncode == 0
        assert "保守方案" in result.stdout
        assert "推荐方案" in result.stdout
        assert "深度方案" in result.stdout

    def test_scan_invalid_path(self):
        """scan 命令对无效路径返回错误"""
        result = _run_cli("scan", "--project", "/nonexistent/path")
        assert result.returncode == 1

    def test_no_command(self):
        """无命令时显示帮助"""
        result = _run_cli()
        assert result.returncode == 1
        assert "usage:" in result.stdout.lower() or "usage:" in result.stderr.lower()


class TestCLIRunNew:
    """Phase 11D Step 1: smartdev run new <id> CLI 集成测试"""

    def _run_new(self, run_id: str, project: str, *extra_args: str):
        """辅助：运行 smartdev run new"""
        return _run_cli("run", "new", run_id, "--project", project, *extra_args)

    def test_creates_run_directory(self, tmp_path: Path):
        """创建 run artifact 目录"""
        result = self._run_new("test-task", str(tmp_path))
        assert result.returncode == 0
        assert "Run artifact 已创建" in result.stdout
        run_dir = tmp_path / ".smartdev" / "runs" / "test-task"
        assert run_dir.exists()
        assert (run_dir / "task-card.md").exists()
        assert (run_dir / "scope.json").exists()

    def test_with_task_description(self, tmp_path: Path):
        """--task 参数写入 task-card.md"""
        result = self._run_new("task-with-desc", str(tmp_path), "--task", "修复登录页Bug")
        assert result.returncode == 0
        content = (tmp_path / ".smartdev" / "runs" / "task-with-desc" / "task-card.md").read_text("utf-8")
        assert "修复登录页Bug" in content

    def test_duplicate_fails(self, tmp_path: Path):
        """重复 run_id 默认报错"""
        self._run_new("dup-task", str(tmp_path))
        result = self._run_new("dup-task", str(tmp_path))
        assert result.returncode == 1
        assert "已存在" in result.stderr

    def test_force_overwrites(self, tmp_path: Path):
        """--force 覆盖已存在的 run 目录"""
        self._run_new("force-task", str(tmp_path), "--task", "旧任务")
        result = self._run_new("force-task", str(tmp_path), "--force", "--task", "新任务")
        assert result.returncode == 0
        content = (tmp_path / ".smartdev" / "runs" / "force-task" / "task-card.md").read_text("utf-8")
        assert "新任务" in content

    def test_invalid_run_id(self, tmp_path: Path):
        """非法 run_id 返回错误"""
        result = self._run_new("", str(tmp_path))
        assert result.returncode == 1
        assert "不能为空" in result.stderr

        result = self._run_new("bad/name", str(tmp_path))
        assert result.returncode == 1
        assert "格式无效" in result.stderr

    def test_invalid_project_path(self):
        """不存在的项目路径返回错误"""
        result = self._run_new("test", "/nonexistent/path")
        assert result.returncode == 1
        assert "不存在" in result.stderr

    def test_custom_scope_params(self, tmp_path: Path):
        """--allowed-paths / --max-files 等参数生效"""
        import json
        result = self._run_new(
            "custom-scope", str(tmp_path),
            "--allowed-paths", "src/", "lib/",
            "--max-files", "3",
            "--force",
        )
        assert result.returncode == 0
        scope_path = tmp_path / ".smartdev" / "runs" / "custom-scope" / "scope.json"
        data = json.loads(scope_path.read_text("utf-8"))
        assert data["allowed_paths"] == ["src/", "lib/"]
        assert data["max_files"] == 3

    def test_workflow_still_works(self, tmp_path: Path):
        """确保原有 workflow 路径不受影响"""
        (tmp_path / "main.py").write_text("pass\n")
        result = _run_cli("run", "--project", str(tmp_path), "--task", "测试")
        assert result.returncode == 0


class TestCLIRunScopeCheck:
    """Phase 11D Step 2: smartdev run scope-check CLI 集成测试"""

    def _setup_run(self, tmp_path: Path, run_id: str = "sc-test", **scope_kwargs):
        """创建 run artifact 用于 scope-check 测试。"""
        import json as _json
        from smartdev.core.run_artifact import ScopeConfig
        scope = ScopeConfig(**scope_kwargs) if scope_kwargs else ScopeConfig()
        run_dir = tmp_path / ".smartdev" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "scope.json").write_text(scope.to_json(), encoding="utf-8")

    def test_passed_output(self, tmp_path: Path):
        """全部在范围内 → passed"""
        self._setup_run(tmp_path, "pass-sc", allowed_paths=["src/"])
        result = _run_cli(
            "run", "scope-check", "pass-sc",
            "--project", str(tmp_path),
            "--changed-files", "src/a.py", "src/b.py",
        )
        assert result.returncode == 0
        assert "通过" in result.stdout

    def test_violation_non_zero_exit(self, tmp_path: Path):
        """有 violation → 退出码 1"""
        self._setup_run(tmp_path, "fail-sc", max_files=1)
        result = _run_cli(
            "run", "scope-check", "fail-sc",
            "--project", str(tmp_path),
            "--changed-files", "src/a.py", "src/b.py",
        )
        assert result.returncode == 1
        assert "未通过" in result.stdout or "超过上限" in result.stdout

    def test_json_output(self, tmp_path: Path):
        """--json 输出可解析 JSON"""
        import json as _json
        self._setup_run(tmp_path, "json-sc", max_files=3)
        result = _run_cli(
            "run", "scope-check", "json-sc",
            "--project", str(tmp_path),
            "--changed-files", "src/a.py", "src/b.py",
            "--json",
        )
        assert result.returncode == 0
        data = _json.loads(result.stdout)
        assert data["passed"] is True

    def test_missing_scope_json(self, tmp_path: Path):
        """scope.json 不存在 → 报错"""
        result = _run_cli(
            "run", "scope-check", "no-such-run",
            "--project", str(tmp_path),
        )
        assert result.returncode == 1
        assert "不存在" in result.stdout or "不存在" in result.stderr


class TestCLIRunHandoffCode:
    """Phase 11D Step 3: smartdev run handoff-code CLI 集成测试"""

    def _setup_run(self, tmp_path: Path, run_id: str = "hc-test", **scope_kwargs):
        """创建 run artifact 用于 handoff-code 测试。"""
        from smartdev.core.run_artifact import ScopeConfig
        scope = ScopeConfig(
            allowed_paths=["smartdev/", "tests/"],
            **scope_kwargs,
        )
        run_dir = tmp_path / ".smartdev" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "scope.json").write_text(scope.to_json(), encoding="utf-8")
        (run_dir / "task-card.md").write_text(
            "# test\n\n## 目标\n\n测试任务目标\n\n## 验收标准\n\n验收通过\n",
            encoding="utf-8",
        )
        # 创建示例源码文件
        (tmp_path / "smartdev" / "core").mkdir(parents=True, exist_ok=True)
        (tmp_path / "smartdev" / "core" / "example.py").write_text("# example\n")

    def test_generates_pack(self, tmp_path: Path):
        """成功生成 code-agent-pack.md"""
        self._setup_run(tmp_path, "hc-1")
        result = _run_cli(
            "run", "handoff-code", "hc-1", "--project", str(tmp_path),
        )
        assert result.returncode == 0
        assert "Code Agent Pack" in result.stdout
        pack_path = tmp_path / ".smartdev" / "runs" / "hc-1" / "handoff" / "code-agent-pack.md"
        assert pack_path.exists()

    def test_missing_run_dir(self, tmp_path: Path):
        """run_id 不存在 → 报错"""
        result = _run_cli(
            "run", "handoff-code", "no-such-run", "--project", str(tmp_path),
        )
        assert result.returncode == 1
        assert "不存在" in result.stderr

    def test_with_changed_files(self, tmp_path: Path):
        """--changed-files 触发 Scope Gate"""
        self._setup_run(tmp_path, "hc-2", max_files=3)
        result = _run_cli(
            "run", "handoff-code", "hc-2", "--project", str(tmp_path),
            "--changed-files", "smartdev/a.py", "smartdev/b.py",
        )
        assert result.returncode == 0
        content = (tmp_path / ".smartdev" / "runs" / "hc-2" / "handoff" / "code-agent-pack.md").read_text("utf-8")
        assert "Scope Gate" in content


class TestCLIRunHandoffDoc:
    """Phase 11D Step 4: smartdev run handoff-doc CLI 集成测试"""

    def _setup_run(self, tmp_path: Path, run_id: str = "hd-test"):
        """创建 run artifact 用于 handoff-doc 测试。"""
        from smartdev.core.run_artifact import ScopeConfig
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        run_dir = tmp_path / ".smartdev" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "scope.json").write_text(scope.to_json(), encoding="utf-8")
        (run_dir / "task-card.md").write_text(
            "# test\n\n## 目标\n\n测试\n\n## 验收标准\n\n验收\n", encoding="utf-8",
        )
        # 最小项目骨架
        (tmp_path / "CLAUDE.md").write_text(
            "# CLAUDE\n\n## 当前阶段\n\nPhase 11D\n\n测试基线：1344 passed\n",
            encoding="utf-8",
        )
        (tmp_path / "smartdev").mkdir(exist_ok=True)
        (tmp_path / "smartdev" / "__init__.py").write_text("")
        (tmp_path / "README.md").write_text("# Test\n")

    def test_generates_pack(self, tmp_path: Path):
        """成功生成 doc-steward-pack.md"""
        self._setup_run(tmp_path, "hd-1")
        result = _run_cli(
            "run", "handoff-doc", "hd-1", "--project", str(tmp_path),
        )
        assert result.returncode == 0
        assert "Doc Steward Pack" in result.stdout
        pack_path = tmp_path / ".smartdev" / "runs" / "hd-1" / "handoff" / "doc-steward-pack.md"
        assert pack_path.exists()

    def test_missing_run_dir(self, tmp_path: Path):
        """run_id 不存在 → 报错"""
        result = _run_cli(
            "run", "handoff-doc", "no-such-run", "--project", str(tmp_path),
        )
        assert result.returncode == 1
        assert "不存在" in result.stderr


class TestCLIRunHandoffReview:
    """Phase 11D Step 5: smartdev run handoff-review CLI 集成测试"""

    def _setup_run(self, tmp_path: Path, run_id: str = "hr-test"):
        """创建 run artifact 用于 handoff-review 测试。"""
        from smartdev.core.run_artifact import ScopeConfig
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        run_dir = tmp_path / ".smartdev" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "scope.json").write_text(scope.to_json(), encoding="utf-8")
        (run_dir / "task-card.md").write_text(
            "# test\n\n## 目标\n\n测试\n\n## 验收标准\n\n验收\n", encoding="utf-8",
        )
        (tmp_path / "smartdev").mkdir(exist_ok=True)
        (tmp_path / "smartdev" / "__init__.py").write_text("")

    def test_generates_pack(self, tmp_path: Path):
        """成功生成 reviewer-pack.md"""
        self._setup_run(tmp_path, "hr-1")
        result = _run_cli(
            "run", "handoff-review", "hr-1", "--project", str(tmp_path),
            "--changed-files", "smartdev/core/auth.py", "pyproject.toml",
        )
        assert result.returncode == 0
        assert "Reviewer Pack" in result.stdout
        pack_path = tmp_path / ".smartdev" / "runs" / "hr-1" / "handoff" / "reviewer-pack.md"
        assert pack_path.exists()
        content = pack_path.read_text("utf-8")
        assert "Security Checklist" in content

    def test_missing_run_dir(self, tmp_path: Path):
        """run_id 不存在 → 报错"""
        result = _run_cli(
            "run", "handoff-review", "no-such-run", "--project", str(tmp_path),
        )
        assert result.returncode == 1
        assert "不存在" in result.stderr


class TestCLIRunContext:
    """smartdev run context CLI 集成测试"""

    def _setup_with_packs(self, tmp_path: Path, run_id: str = "ctx-cli"):
        """创建 run artifact 并预生成三个 pack。"""
        from smartdev.core.run_artifact import ScopeConfig
        scope = ScopeConfig(allowed_paths=["smartdev/", "tests/"])
        run_dir = tmp_path / ".smartdev" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "scope.json").write_text(scope.to_json(), encoding="utf-8")
        (run_dir / "task-card.md").write_text(
            "# test\n\n## 目标\n\n测试\n\n## 验收标准\n\n验收\n", encoding="utf-8",
        )
        (tmp_path / "CLAUDE.md").write_text("# CLAUDE\n\n## 当前阶段\n\nPhase 11D\n", encoding="utf-8")
        (tmp_path / "smartdev").mkdir(exist_ok=True)
        (tmp_path / "smartdev" / "__init__.py").write_text("")

        from smartdev.core.handoff_code import generate_code_agent_pack
        from smartdev.core.handoff_doc import generate_doc_steward_pack
        from smartdev.core.handoff_review import generate_reviewer_pack
        generate_code_agent_pack(tmp_path, run_id)
        generate_doc_steward_pack(tmp_path, run_id)
        generate_reviewer_pack(tmp_path, run_id)

    def test_context_code_agent(self, tmp_path: Path):
        """--role code-agent 打印 code-agent-pack.md"""
        self._setup_with_packs(tmp_path, "cc1")
        result = _run_cli(
            "run", "context", "cc1", "--project", str(tmp_path), "--role", "code-agent",
        )
        assert result.returncode == 0
        assert "Code Agent" in result.stdout

    def test_context_doc_steward(self, tmp_path: Path):
        """--role doc-steward 打印 doc-steward-pack.md"""
        self._setup_with_packs(tmp_path, "cc2")
        result = _run_cli(
            "run", "context", "cc2", "--project", str(tmp_path), "--role", "doc-steward",
        )
        assert result.returncode == 0
        assert "Doc Steward" in result.stdout

    def test_context_reviewer(self, tmp_path: Path):
        """--role reviewer 打印 reviewer-pack.md"""
        self._setup_with_packs(tmp_path, "cc3")
        result = _run_cli(
            "run", "context", "cc3", "--project", str(tmp_path), "--role", "reviewer",
        )
        assert result.returncode == 0
        assert "Reviewer" in result.stdout

    def test_context_info_mode(self, tmp_path: Path):
        """--info 打印元信息"""
        self._setup_with_packs(tmp_path, "cc4")
        result = _run_cli(
            "run", "context", "cc4", "--project", str(tmp_path), "--role", "doc-steward", "--info",
        )
        assert result.returncode == 0
        assert "exists:" in result.stdout
        assert "char_count:" in result.stdout

    def test_context_missing_pack(self, tmp_path: Path):
        """pack 不存在时给出建议命令"""
        result = _run_cli(
            "run", "context", "no-pack", "--project", str(tmp_path), "--role", "code-agent",
        )
        assert result.returncode == 1
        assert "不存在" in result.stderr
        assert "handoff-code" in result.stderr

    def test_context_info_missing_pack(self, tmp_path: Path):
        """--info + 不存在 pack → 打印建议并返回 1"""
        result = _run_cli(
            "run", "context", "no-pack", "--project", str(tmp_path),
            "--role", "reviewer", "--info",
        )
        assert result.returncode == 1
        assert "exists:" in result.stdout
        assert "handoff-review" in result.stdout
