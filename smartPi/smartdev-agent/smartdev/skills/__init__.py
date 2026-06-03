"""SmartDev Agent Skill 系统

所有 Skill 模块必须在此导入，以触发 __init_subclass__ 自动注册。
新增 Skill 时，只需在此添加一行 import 即可。
"""

from smartdev.skills.base import Skill

# ── 导入所有 Skill 模块 ──────────────────────────────────
# 为什么需要显式导入？
#   __init_subclass__ 只在类定义执行时触发。
#   如果模块从未被 import，类定义不会执行，注册不会发生。
#   这里统一导入，确保 `from smartdev.skills import Skill` 时
#   所有 Skill 都已注册到 Skill._registry 中。

from smartdev.skills.repo_scan import skill as _repo_scan_skill  # noqa: F401
from smartdev.skills.task_plan import skill as _task_plan_skill  # noqa: F401
from smartdev.skills.architecture_map import skill as _architecture_map_skill  # noqa: F401
from smartdev.skills.token_audit import skill as _token_audit_skill  # noqa: F401
from smartdev.skills.risk_check import skill as _risk_check_skill  # noqa: F401
from smartdev.skills.qa_checklist import skill as _qa_checklist_skill  # noqa: F401

__all__ = ["Skill"]
