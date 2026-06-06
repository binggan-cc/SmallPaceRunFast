"""
Project Adapter 测试

验证：
1. 从 JSON 加载适配器
2. 路径判断（editable/cautious/forbidden）
3. 自动检测项目类型
4. SmartFav 适配器加载
5. 适配器目录结构
"""

import json
from pathlib import Path

from smartdev.core.adapter import (
    ProjectAdapter,
    load_adapter,
    find_adapter,
    _detect_project_type,
)


class TestAdapterLoading:
    """适配器加载测试"""

    def test_load_from_json(self, tmp_path: Path):
        """从 JSON 文件加载适配器"""
        adapter_data = {
            "adapter": "test",
            "version": "1.0",
            "project": {"name": "Test", "type": "test-project"},
            "editable_regions": ["src/"],
            "forbidden_regions": ["config/"],
        }
        adapter_file = tmp_path / "test.json"
        adapter_file.write_text(json.dumps(adapter_data))

        adapter = load_adapter(adapter_file)

        assert adapter.name == "test"
        assert adapter.project_name == "Test"
        assert adapter.project_type == "test-project"
        assert "src/" in adapter.editable_regions

    def test_is_editable(self):
        """可编辑区域判断"""
        adapter = ProjectAdapter(
            editable_regions=["src/", "lib/"],
        )
        assert adapter.is_editable("src/main.py") is True
        assert adapter.is_editable("lib/utils.py") is True
        assert adapter.is_editable("config/settings.py") is False

    def test_is_forbidden(self):
        """禁止区域判断"""
        adapter = ProjectAdapter(
            forbidden_regions=["config/", "*.db"],
        )
        assert adapter.is_forbidden("config/secrets.json") is True
        assert adapter.is_forbidden("src/main.py") is False

    def test_is_cautious(self):
        """谨慎区域判断"""
        adapter = ProjectAdapter(
            cautious_regions=["manifest.json", "database.py"],
        )
        assert adapter.is_cautious("manifest.json") is True
        assert adapter.is_cautious("src/main.py") is False


class TestProjectTypeDetection:
    """项目类型检测测试"""

    def test_detect_chrome_extension(self, tmp_path: Path):
        """检测 Chrome Extension"""
        manifest = {"manifest_version": 3, "name": "Test"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        assert _detect_project_type(tmp_path) == "chrome-extension"

    def test_detect_fastapi(self, tmp_path: Path):
        """检测 FastAPI"""
        (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")

        assert _detect_project_type(tmp_path) == "fastapi"

    def test_detect_python(self, tmp_path: Path):
        """检测 Python CLI"""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        assert _detect_project_type(tmp_path) == "python-cli"

    def test_detect_nodejs(self, tmp_path: Path):
        """检测 Node.js"""
        (tmp_path / "package.json").write_text('{"name": "test"}')

        assert _detect_project_type(tmp_path) == "nodejs"

    def test_detect_generic(self, tmp_path: Path):
        """无法识别时返回 generic"""
        assert _detect_project_type(tmp_path) == "generic"


class TestAdapterDiscovery:
    """适配器发现测试"""

    def test_find_adapter_in_project(self, tmp_path: Path):
        """项目自带适配器时优先使用"""
        adapter_data = {"adapter": "local", "project": {"name": "Local"}}
        (tmp_path / "adapter.json").write_text(json.dumps(adapter_data))

        adapter = find_adapter(tmp_path)
        assert adapter is not None
        assert adapter.name == "local"

    def test_find_adapter_from_directory(self, tmp_path: Path):
        """从适配器目录匹配"""
        # 创建 Chrome Extension 项目
        manifest = {"manifest_version": 3, "name": "Test"}
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        # 创建适配器目录
        adapters_dir = tmp_path / "adapters"
        adapters_dir.mkdir()
        adapter_data = {
            "adapter": "chrome_ext",
            "project": {"type": "chrome-extension"},
        }
        (adapters_dir / "chrome.json").write_text(json.dumps(adapter_data))

        adapter = find_adapter(tmp_path, adapters_dir)
        assert adapter is not None
        assert adapter.name == "chrome_ext"

    def test_no_adapter_found(self, tmp_path: Path):
        """无匹配适配器时返回 None"""
        adapters_dir = tmp_path / "adapters"
        adapters_dir.mkdir()

        adapter = find_adapter(tmp_path, adapters_dir)
        assert adapter is None


class TestSmartFavAdapter:
    """SmartFav 适配器测试"""

    def test_loads_correctly(self):
        """SmartFav 适配器可正确加载"""
        adapter_path = Path(__file__).parent.parent / "smartdev" / "adapters" / "smartfav.json"
        if not adapter_path.exists():
            return  # 跳过（文件不存在时）

        adapter = load_adapter(adapter_path)

        assert adapter.name == "smartfav"
        assert adapter.project_type == "chrome-extension-local-first"
        assert len(adapter.tech_stack) >= 3
        assert len(adapter.editable_regions) >= 3
        assert len(adapter.forbidden_regions) >= 1

    def test_describe(self):
        """describe 输出正确"""
        adapter = ProjectAdapter(
            name="test",
            project_name="Test",
            editable_regions=["src/"],
            forbidden_regions=["config/"],
        )
        desc = adapter.describe()
        assert desc["name"] == "test"
        assert desc["editable_count"] == 1
        assert desc["forbidden_count"] == 1
