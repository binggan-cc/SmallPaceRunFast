"""
Skill: qa.checklist — 验收清单

功能：根据任务类型和风险等级，生成对应的验收检查清单。
风险：R0（只读，不修改任何文件）
类型：plan

对应文档：
- smartPi/docs/smartdev-agent-core-spec.md §13（验收标准规范）
- smartPi/docs/smartdev-agent-core-spec.md §5.7（QA Verify）
"""

from __future__ import annotations

from smartdev.models import RiskLevel, SkillResult, TaskType
from smartdev.skills.base import Skill


# ── 验收清单模板 ──────────────────────────────────────────
# 对应 core-spec §13 的 5 类验收标准
#
# 为什么用模板而非 LLM 生成？
# Phase 1 需要确定性输出，方便测试和验证。
# 模板覆盖最常见的验收场景，LLM 可以在后续版本补充。

_CHECKLISTS = {
    # 通用检查（所有任务都适用）
    "general": [
        "代码无语法错误",
        "现有测试全部通过",
        "无新增 lint 警告",
    ],
    # 功能验收
    "functional": [
        "功能入口可见",
        "用户可完成主流程",
        "异常情况有反馈",
        "数据保存正确",
        "页面刷新后状态正常",
    ],
    # UI 验收
    "ui": [
        "默认状态正常",
        "Hover 状态正常",
        "Active 状态正常",
        "Disabled 状态正常",
        "Loading 状态正常",
        "Empty 状态正常",
        "Error 状态正常",
        "响应式状态正常",
    ],
    # API 验收
    "api": [
        "正常请求返回正确",
        "错误请求返回合理",
        "空数据返回合理",
        "中文内容正常",
        "分页正常",
        "筛选正常",
        "权限边界正常",
    ],
    # 数据验收
    "data": [
        "创建正常",
        "更新正常",
        "删除正常",
        "去重正常",
        "导入正常",
        "导出正常",
        "同步正常",
        "迁移兼容",
    ],
    # 文档验收
    "documentation": [
        "README 已更新",
        "CHANGELOG 已更新",
        "development-progress 已更新",
        "API 文档已更新",
    ],
}

# 任务描述 → 检查类别的映射规则
# 匹配到的类别会被加入最终清单
_CATEGORY_RULES = [
    # (关键词列表, 类别列表)
    (["功能", "feature", "新增", "添加", "实现"], ["general", "functional"]),
    (["UI", "界面", "样式", "CSS", "布局", "页面", "按钮"], ["general", "ui"]),
    (["API", "接口", "endpoint", "路由", "GET", "POST"], ["general", "api"]),
    (["数据", "数据库", "存储", "导入", "导出", "同步"], ["general", "data"]),
    (["文档", "README", "CONTRIBUTING", "CHANGELOG", "说明"], ["general", "documentation"]),
    (["Bug", "bug", "修复", "fix"], ["general", "functional"]),
    (["Token", "token", "设计令牌", "变量"], ["general", "ui"]),
    (["架构", "重构", "refactor"], ["general"]),
]


def _detect_categories(task_description: str) -> list[str]:
    """根据任务描述检测需要的检查类别"""
    task_lower = task_description.lower()
    categories = set()

    for keywords, cats in _CATEGORY_RULES:
        for kw in keywords:
            if kw.lower() in task_lower:
                categories.update(cats)
                break

    # 至少包含 general
    if not categories:
        categories.add("general")

    return sorted(categories)


def _build_checklist(categories: list[str]) -> list[dict]:
    """根据类别构建验收清单"""
    checklist = []
    seen = set()

    for category in categories:
        items = _CHECKLISTS.get(category, [])
        for item in items:
            if item not in seen:
                seen.add(item)
                checklist.append({
                    "category": category,
                    "item": item,
                    "passed": False,
                })

    return checklist


class QAChecklistSkill(Skill):
    """验收清单 Skill

    根据任务类型和风险等级，生成对应的验收检查清单。

    使用示例：
        context = ProjectContext(
            project_path=Path("/path/to/project"),
            task_description="添加暗色模式",
        )
        skill = Skill.create("qa.checklist")
        result = skill.run(context)
    """

    name = "qa.checklist"
    description = "根据任务类型生成验收检查清单"
    risk_level = RiskLevel.R0
    task_type = TaskType.PLAN

    def can_run(self, context) -> bool:
        """前置条件：有任务描述"""
        return bool(context.task_description.strip())

    def run(self, context, inputs: dict | None = None) -> SkillResult:
        """执行验收清单生成"""
        task_description = context.task_description

        # 检测需要的检查类别
        categories = _detect_categories(task_description)

        # 构建验收清单
        checklist = _build_checklist(categories)

        # 摘要
        summary_parts = [
            f"验收清单生成完成：{task_description}",
            f"检查类别：{', '.join(categories)}",
            f"检查项：{len(checklist)} 个",
        ]

        return SkillResult(
            success=True,
            summary="\n".join(summary_parts),
            data={
                "task_description": task_description,
                "categories": categories,
                "checklist": checklist,
                "total_items": len(checklist),
            },
            next_steps=[
                "执行任务后，逐项检查清单",
                "所有检查项通过后，可提交 git",
            ],
        )
