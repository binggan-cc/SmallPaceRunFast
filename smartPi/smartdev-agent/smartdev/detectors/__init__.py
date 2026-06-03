"""SmartDev Agent 项目检测器"""

from smartdev.detectors.tech_stack import detect_tech_stack
from smartdev.detectors.docs_status import detect_docs_status
from smartdev.detectors.entrypoints import detect_entrypoints

__all__ = ["detect_tech_stack", "detect_docs_status", "detect_entrypoints"]
