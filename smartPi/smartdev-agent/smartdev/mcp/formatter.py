"""
SmartDev MCP — 统一输出格式

所有工具返回统一 JSON 结构：

成功：
{
    "ok": true,
    "tool": "smartdev_ping",
    "data": {...},
    "warnings": [],
    "risk_level": "R0",
    "next_steps": []
}

失败：
{
    "ok": false,
    "tool": "smartdev_ping",
    "error_code": "INDEX_NOT_FOUND",
    "message": "...",
    "suggested_tool": "smartdev_code_index"
}

对应文档：
    docs/phase-10-design.md §2 Q6
"""

from __future__ import annotations

import json


def ok(tool: str, data: dict, *, warnings: list[str] | None = None,
       risk_level: str = "R0", next_steps: list[str] | None = None) -> str:
    """生成成功响应 JSON 字符串"""
    return json.dumps({
        "ok": True,
        "tool": tool,
        "data": data,
        "warnings": warnings or [],
        "risk_level": risk_level,
        "next_steps": next_steps or [],
    }, ensure_ascii=False, indent=2)


def error(tool: str, error_code: str, message: str,
          suggested_tool: str | None = None) -> str:
    """生成失败响应 JSON 字符串"""
    result: dict = {
        "ok": False,
        "tool": tool,
        "error_code": error_code,
        "message": message,
    }
    if suggested_tool:
        result["suggested_tool"] = suggested_tool
    return json.dumps(result, ensure_ascii=False, indent=2)
