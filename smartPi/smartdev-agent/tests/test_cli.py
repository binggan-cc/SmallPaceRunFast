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
