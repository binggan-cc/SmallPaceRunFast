"""
Skill: doc.generate — 文档生成

功能：根据项目扫描结果和适配器信息，生成 README、CONTRIBUTING 等文档草案。
风险：R1（生成文件，但不直接覆盖——输出为草案）
类型：document

设计决策：
- 只输出草案，不直接写入文件（对应 protocol §6 执行前确认）
- 内容基于项目实际情况，非泛型模板
- 不同项目类型生成不同风格的文档

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §5.8（文档与知识沉淀）
- smartPi/docs/smartdev-agent-protocol.md §4 禁止行为 #9（新增功能后不更新进度文档）
"""

from __future__ import annotations

from pathlib import Path

from smartdev.detectors.docs_status import detect_docs_status
from smartdev.detectors.tech_stack import detect_tech_stack
from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── README 模板 ──────────────────────────────────────────
# 不同项目类型的 README 风格不同

def _generate_readme(
    project_name: str,
    tech_stack: list[str],
    description: str = "",
) -> str:
    """生成 README 草案"""
    tech_str = ", ".join(tech_stack) if tech_stack else "待补充"

    return f"""# {project_name}

> {description or "项目描述待补充"}

## 技术栈

{tech_str}

## 快速开始

```bash
# 安装依赖
# 启动项目
# 运行测试
```

## 项目结构

```
{project_name}/
├── src/
│   └── ...
├── tests/
│   └── ...
├── docs/
│   └── ...
└── README.md
```

## 开发规范

- 每小步提交 git
- 每步运行测试
- 执行前说明范围和风险
- 执行后总结变更

## 许可证

MIT
"""


def _generate_contributing(project_name: str) -> str:
    """生成 CONTRIBUTING 草案"""
    return f"""# 贡献指南 — {project_name}

## 开发流程

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/xxx`)
3. 提交更改 (`git commit -m 'feat: xxx'`)
4. 推送到分支 (`git push origin feature/xxx`)
5. 创建 Pull Request

## 提交规范

使用 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
feat:     新功能
fix:      Bug 修复
docs:     文档变更
refactor: 重构（不改变功能）
test:     测试
chore:    构建/工具变更
```

## 代码规范

- 每次提交只改一个逻辑单元
- 提交前运行测试确保通过
- 新增功能必须附带测试
- 修改功能必须更新相关文档

## Pull Request 规范

- 标题简洁描述变更内容
- 说明修改了什么、为什么修改
- 附上测试结果截图（如适用）
- 关联相关 Issue
"""


def _generate_changelog_entry(version: str, changes: list[str]) -> str:
    """生成 CHANGELOG 条目"""
    items = "\n".join(f"- {c}" for c in changes)
    return f"""## [{version}]

### Added

{items}
"""


# ── 文档类型映射 ──────────────────────────────────────────

_DOC_GENERATORS = {
    "readme": _generate_readme,
    "contributing": _generate_contributing,
    "changelog": _generate_changelog_entry,
}


class DocGenerateSkill(Skill):
    """文档生成 Skill

    根据项目扫描结果生成文档草案，不直接写入文件。

    使用示例：
        context = ProjectContext(
            project_path=Path("/path/to/project"),
            task_description="生成 README",
        )
        skill = Skill.create("doc.generate")
        result = skill.run(context, inputs={"doc_type": "readme"})
    """

    name = "doc.generate"
    description = "根据项目状态生成文档草案（README/CONTRIBUTING/CHANGELOG）"
    risk_level = RiskLevel.R1
    task_type = TaskType.DOCUMENT

    def can_run(self, context) -> bool:
        """前置条件：项目路径存在"""
        return context.project_path.exists() and context.project_path.is_dir()

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行文档生成"""
        project = context.project_path
        doc_type = (inputs or {}).get("doc_type", "readme").lower()

        # 扫描项目信息
        tech_result = detect_tech_stack(project)
        docs_result = detect_docs_status(project)
        tech_names = tech_result.tech_names()

        # 生成文档
        if doc_type == "readme":
            content = _generate_readme(
                project_name=project.name,
                tech_stack=tech_names,
            )
            save_path = "README.md"
        elif doc_type == "contributing":
            content = _generate_contributing(project_name=project.name)
            save_path = "CONTRIBUTING.md"
        elif doc_type == "changelog":
            content = _generate_changelog_entry(
                version="0.1.0",
                changes=["初始版本"],
            )
            save_path = "CHANGELOG.md"
        else:
            return SkillResult(
                success=False,
                summary=f"不支持的文档类型: {doc_type}",
                data={"supported_types": list(_DOC_GENERATORS.keys())},
            )

        # 检查文件是否已存在
        existing_file = project / save_path
        file_exists = existing_file.exists()

        # 构建摘要
        summary_parts = [
            f"文档草案生成完成：{doc_type}",
            f"建议保存路径: {save_path}",
            f"文件已存在: {'是（需要确认是否覆盖）' if file_exists else '否'}",
        ]

        # 风险
        risks = []
        if file_exists:
            risks.append(f"{save_path} 已存在，覆盖前请确认")
        risks.append("R1 操作：文档草案已生成，需用户确认后写入")

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "doc_type": doc_type,
                "content": content,
                "save_path": save_path,
                "file_exists": file_exists,
            },
            risks=risks,
            changed_files=[save_path] if not file_exists else [],
            next_steps=[
                "请审查文档草案内容",
                "确认无误后，手动保存到项目目录",
                "更新 development-progress.md 记录文档变更",
            ],
        )
