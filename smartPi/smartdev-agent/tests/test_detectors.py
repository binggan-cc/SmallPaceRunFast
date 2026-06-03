"""
检测器测试

验证三个检测器在不同项目类型下的检测能力。
使用 tmp_path fixture 创建临时项目目录模拟真实场景。
"""

from pathlib import Path

import pytest

from smartdev.detectors.tech_stack import detect_tech_stack
from smartdev.detectors.docs_status import detect_docs_status
from smartdev.detectors.entrypoints import detect_entrypoints


# ── 技术栈检测 ────────────────────────────────────────────


class TestTechStackDetection:
    """技术栈检测器测试"""

    def test_detect_python_project(self, tmp_path: Path):
        """检测纯 Python 项目"""
        (tmp_path / "requirements.txt").write_text("requests>=2.28\n")
        (tmp_path / "main.py").write_text("print('hello')\n")

        result = detect_tech_stack(tmp_path)
        tech_names = result.tech_names()

        assert "Python" in tech_names
        assert "Git" not in tech_names  # 没有 .git 目录

    def test_detect_nodejs_project(self, tmp_path: Path):
        """检测 Node.js 项目"""
        (tmp_path / "package.json").write_text('{"name": "test"}\n')
        (tmp_path / "index.js").write_text("console.log('hello')\n")

        result = detect_tech_stack(tmp_path)
        tech_names = result.tech_names()

        assert "Node.js" in tech_names

    def test_detect_chrome_extension(self, tmp_path: Path):
        """检测 Chrome Extension MV3"""
        manifest = {
            "manifest_version": 3,
            "name": "Test Extension",
            "background": {"service_worker": "background.js"},
            "action": {"default_popup": "popup.html"},
            "side_panel": {"default_path": "sidepanel.html"},
        }
        import json
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        result = detect_tech_stack(tmp_path)
        tech_names = result.tech_names()

        assert "Chrome Extension MV3" in tech_names

    def test_detect_fastapi_project(self, tmp_path: Path):
        """检测 FastAPI 项目"""
        (tmp_path / "requirements.txt").write_text("fastapi>=0.100\nuvicorn\n")
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")

        result = detect_tech_stack(tmp_path)
        tech_names = result.tech_names()

        assert "FastAPI" in tech_names
        assert "Python" in tech_names

    def test_detect_empty_project(self, tmp_path: Path):
        """空项目不检测到任何技术"""
        result = detect_tech_stack(tmp_path)

        assert len(result.all_techs()) == 0
        assert result.tech_names() == []

    def test_detect_combined_project(self, tmp_path: Path):
        """检测混合技术栈（Python + FastAPI + Docker + Git）"""
        (tmp_path / "requirements.txt").write_text("fastapi\n")
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\n")
        (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
        (tmp_path / ".git").mkdir()

        result = detect_tech_stack(tmp_path)
        tech_names = result.tech_names()

        assert "Python" in tech_names
        assert "FastAPI" in tech_names
        assert "Docker" in tech_names
        assert "Git" in tech_names


# ── 文档状态检测 ──────────────────────────────────────────


class TestDocsStatusDetection:
    """文档状态检测器测试"""

    def test_all_docs_missing(self, tmp_path: Path):
        """空项目所有文档缺失"""
        result = detect_docs_status(tmp_path)

        assert len(result.missing_docs) > 0
        assert result.coverage_rate == 0.0

    def test_readme_exists(self, tmp_path: Path):
        """项目有 README"""
        (tmp_path / "README.md").write_text("# Test Project\n")

        result = detect_docs_status(tmp_path)

        assert any(d.name == "README.md" and d.exists for d in result.docs)
        assert result.coverage_rate > 0.0

    def test_empty_readme_detected(self, tmp_path: Path):
        """空 README 被标记为空文档"""
        (tmp_path / "README.md").write_text("")

        result = detect_docs_status(tmp_path)

        assert any(d.name == "README.md" and d.is_empty for d in result.docs)

    def test_coverage_rate(self, tmp_path: Path):
        """覆盖率计算正确"""
        (tmp_path / "README.md").write_text("# Test\n")
        (tmp_path / "LICENSE").write_text("MIT\n")

        result = detect_docs_status(tmp_path)

        # 总共检查 10 个文档，存在 2 个
        assert result.coverage_rate == pytest.approx(0.2, abs=0.01)


# ── 入口文件检测 ──────────────────────────────────────────


class TestEntrypointsDetection:
    """入口文件检测器测试"""

    def test_python_entrypoint(self, tmp_path: Path):
        """检测 Python 入口"""
        (tmp_path / "main.py").write_text("print('hello')\n")

        result = detect_entrypoints(tmp_path)

        assert len(result.entrypoints) >= 1
        assert any(e.name == "main.py" for e in result.entrypoints)

    def test_nodejs_entrypoint(self, tmp_path: Path):
        """检测 Node.js 入口"""
        import json
        pkg = {
            "name": "test",
            "main": "index.js",
            "scripts": {"start": "node index.js"},
        }
        (tmp_path / "package.json").write_text(json.dumps(pkg))

        result = detect_entrypoints(tmp_path)

        assert any(e.name == "main" for e in result.entrypoints)
        assert any(e.name == "start" for e in result.entrypoints)

    def test_chrome_extension_entrypoints(self, tmp_path: Path):
        """检测 Chrome Extension 入口"""
        import json
        manifest = {
            "manifest_version": 3,
            "background": {"service_worker": "background.js"},
            "action": {"default_popup": "popup.html"},
            "side_panel": {"default_path": "sidepanel.html"},
            "content_scripts": [{"js": ["content.js"]}],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        result = detect_entrypoints(tmp_path)

        names = [e.name for e in result.entrypoints]
        assert "service_worker" in names
        assert "popup" in names
        assert "side_panel" in names
        assert "content_script" in names

    def test_empty_project(self, tmp_path: Path):
        """空项目无入口"""
        result = detect_entrypoints(tmp_path)

        assert len(result.entrypoints) == 0
