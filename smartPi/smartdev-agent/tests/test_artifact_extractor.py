"""
ArtifactExtractor 测试

验证 8 种 artifact 类型的提取能力：
1. api_endpoint — FastAPI 路由
2. manifest — Chrome Extension manifest
3. design_token — CSS 变量
4. document — Markdown 文档
5. model — 数据模型
6. config — 配置文件
7. server_file — FastAPI 服务文件
8. extension_file — Chrome Extension 文件
"""

from pathlib import Path

import pytest

from smartdev.context.artifact_extractor import (
    ARTIFACT_TYPE_API_ENDPOINT,
    ARTIFACT_TYPE_CONFIG,
    ARTIFACT_TYPE_DESIGN_TOKEN,
    ARTIFACT_TYPE_DOCUMENT,
    ARTIFACT_TYPE_EXTENSION_FILE,
    ARTIFACT_TYPE_MANIFEST,
    ARTIFACT_TYPE_MODEL,
    ARTIFACT_TYPE_SERVER_FILE,
    ArtifactExtractor,
)


class TestAPIEndpointExtraction:
    """API 端点提取"""

    def test_extract_fastapi_routes(self, tmp_path: Path):
        """提取 FastAPI 路由"""
        (tmp_path / "main.py").write_text('''
from fastapi import FastAPI
app = FastAPI()

@app.get("/items")
def get_items():
    return []

@app.post("/items")
def create_item():
    return {}
''')
        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        endpoints = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_API_ENDPOINT]
        assert len(endpoints) == 2
        names = {a.name for a in endpoints}
        assert "GET /items" in names
        assert "POST /items" in names

    def test_extract_with_router(self, tmp_path: Path):
        """提取使用 router 的 FastAPI 路由"""
        (tmp_path / "api.py").write_text('''
from fastapi import APIRouter
router = APIRouter()

@router.get("/users")
def get_users():
    return []
''')
        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        endpoints = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_API_ENDPOINT]
        assert len(endpoints) == 1
        assert "GET /users" in endpoints[0].name


class TestManifestExtraction:
    """Manifest 提取"""

    def test_extract_chrome_manifest(self, tmp_path: Path):
        """提取 Chrome Extension manifest"""
        import json
        manifest = {
            "manifest_version": 3,
            "name": "Test Extension",
            "version": "1.0.0",
            "permissions": ["storage", "tabs"],
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest))

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        manifests = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_MANIFEST]
        assert len(manifests) == 1
        assert "Test Extension" in manifests[0].name
        assert "v1.0.0" in manifests[0].name


class TestDesignTokenExtraction:
    """设计令牌提取"""

    def test_extract_css_variables(self, tmp_path: Path):
        """提取 CSS 变量"""
        (tmp_path / "tokens.css").write_text('''
:root {
    --color-primary: #3b82f6;
    --color-secondary: #6366f1;
    --spacing-sm: 8px;
    --spacing-md: 16px;
}
''')
        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        tokens = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_DESIGN_TOKEN]
        assert len(tokens) == 4
        names = {a.name for a in tokens}
        assert "--color-primary" in names
        assert "--spacing-sm" in names

    def test_no_tokens_in_non_css(self, tmp_path: Path):
        """非 CSS 文件不提取 token"""
        (tmp_path / "app.js").write_text("const x = '--color: red';\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        tokens = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_DESIGN_TOKEN]
        assert len(tokens) == 0


class TestDocumentExtraction:
    """文档提取"""

    def test_extract_readme(self, tmp_path: Path):
        """提取 README"""
        (tmp_path / "README.md").write_text("# My Project\n\nA test project.\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        docs = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_DOCUMENT]
        assert len(docs) == 1
        assert docs[0].name == "My Project"

    def test_extract_nested_doc(self, tmp_path: Path):
        """提取嵌套目录中的文档"""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "ARCHITECTURE.md").write_text("# Architecture\n")

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        docs = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_DOCUMENT]
        assert len(docs) >= 1


class TestModelExtraction:
    """数据模型提取"""

    def test_extract_pydantic_model(self, tmp_path: Path):
        """提取 Pydantic BaseModel"""
        (tmp_path / "models.py").write_text('''
from pydantic import BaseModel

class Item(BaseModel):
    name: str
    price: float

class User(BaseModel):
    username: str
    email: str
''')
        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        models = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_MODEL]
        assert len(models) == 2
        names = {a.name for a in models}
        assert "Item" in names
        assert "User" in names

    def test_extract_dataclass(self, tmp_path: Path):
        """提取 dataclass"""
        (tmp_path / "models.py").write_text('''
from dataclasses import dataclass

@dataclass
class Config:
    debug: bool = False
    port: int = 8000
''')
        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        models = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_MODEL]
        assert len(models) == 1
        assert models[0].name == "Config"


class TestConfigExtraction:
    """配置文件提取"""

    def test_extract_pyproject_toml(self, tmp_path: Path):
        """提取 pyproject.toml"""
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "test"\n')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        configs = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_CONFIG]
        assert len(configs) == 1
        assert configs[0].file_path == "pyproject.toml"

    def test_extract_package_json(self, tmp_path: Path):
        """提取 package.json"""
        import json
        pkg = {"name": "my-app", "version": "1.0.0"}
        (tmp_path / "package.json").write_text(json.dumps(pkg))

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        configs = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_CONFIG]
        assert len(configs) == 1
        assert "my-app" in configs[0].name


class TestServerFileExtraction:
    """服务文件提取"""

    def test_extract_fastapi_server(self, tmp_path: Path):
        """识别 FastAPI 服务文件"""
        (tmp_path / "server.py").write_text('''
from fastapi import FastAPI
app = FastAPI()

@app.get("/")
def root():
    return {"hello": "world"}
''')
        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        servers = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_SERVER_FILE]
        assert len(servers) == 1
        assert servers[0].name == "server"


class TestExtensionFileExtraction:
    """Chrome Extension 文件提取"""

    def test_extract_sidepanel(self, tmp_path: Path):
        """识别 sidepanel.js"""
        (tmp_path / "sidepanel.js").write_text('''
chrome.sidePanel.setOptions({ enabled: true });
document.getElementById("btn").addEventListener("click", () => {});
''')
        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        ext_files = [a for a in result.artifacts if a.type == ARTIFACT_TYPE_EXTENSION_FILE]
        assert len(ext_files) == 1
        assert ext_files[0].name == "sidepanel"


class TestExtractionResult:
    """提取结果"""

    def test_extracts_multiple_types(self, tmp_path: Path):
        """一个项目提取多种类型"""
        # 构造一个小型 SmartFav-like 项目
        (tmp_path / "manifest.json").write_text('{"manifest_version": 3, "name": "Ext", "version": "1.0"}')
        (tmp_path / "tokens.css").write_text(":root { --primary: #3b82f6; }\n")
        (tmp_path / "README.md").write_text("# Project\n")
        (tmp_path / "server.py").write_text('from fastapi import FastAPI\napp = FastAPI()\n@app.get("/api")\ndef api(): pass\n')

        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)

        types = {a.type for a in result.artifacts}
        assert ARTIFACT_TYPE_MANIFEST in types
        assert ARTIFACT_TYPE_DESIGN_TOKEN in types
        assert ARTIFACT_TYPE_DOCUMENT in types
        assert len(result.errors) == 0

    def test_no_errors_on_empty_project(self, tmp_path: Path):
        """空项目无错误"""
        extractor = ArtifactExtractor()
        result = extractor.extract(tmp_path)
        assert result.artifacts == []
        assert result.errors == []
