"""
CLI 测试

验证：
1. --help 输出正确
2. --version 输出正确
3. list 命令列出所有 Skill
4. scan 命令在有效项目上运行
5. plan 命令在有效项目上运行
6. 无效路径返回错误码
"""

import subprocess
import sys
from pathlib import Path

import pytest


class TestCLI:
    """CLI 命令行测试"""

    def test_help(self):
        """--help 输出包含用法说明"""
        result = subprocess.run(
            [sys.executable, "-m", "smartdev", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "SmartDev Agent" in result.stdout
        assert "scan" in result.stdout
        assert "plan" in result.stdout
        assert "list" in result.stdout

    def test_version(self):
        """--version 输出版本号"""
        result = subprocess.run(
            [sys.executable, "-m", "smartdev", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "smartdev" in result.stdout

    def test_list(self):
        """list 命令列出所有 Skill"""
        result = subprocess.run(
            [sys.executable, "-m", "smartdev", "list"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "repo.scan" in result.stdout
        assert "task.plan" in result.stdout

    def test_scan(self, tmp_path: Path):
        """scan 命令在有效项目上运行"""
        # 创建一个最小 Python 项目（需要标记文件触发检测）
        (tmp_path / "requirements.txt").write_text("requests\n")
        (tmp_path / "main.py").write_text("print('hello')\n")
        (tmp_path / "README.md").write_text("# Test\n")

        result = subprocess.run(
            [sys.executable, "-m", "smartdev", "scan", "--project", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "扫描完成" in result.stdout
        assert "Python" in result.stdout

    def test_plan(self, tmp_path: Path):
        """plan 命令在有效项目上运行"""
        (tmp_path / "main.py").write_text("pass\n")

        result = subprocess.run(
            [sys.executable, "-m", "smartdev", "plan",
             "--project", str(tmp_path), "--task", "测试任务"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "保守方案" in result.stdout
        assert "推荐方案" in result.stdout
        assert "深度方案" in result.stdout

    def test_scan_invalid_path(self):
        """scan 命令对无效路径返回错误"""
        result = subprocess.run(
            [sys.executable, "-m", "smartdev", "scan", "--project", "/nonexistent/path"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1

    def test_no_command(self):
        """无命令时显示帮助"""
        result = subprocess.run(
            [sys.executable, "-m", "smartdev"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "usage:" in result.stdout.lower() or "usage:" in result.stderr.lower()
