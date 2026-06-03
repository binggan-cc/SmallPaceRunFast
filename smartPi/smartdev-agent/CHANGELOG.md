# Changelog

本文档记录 SmartDev Agent 的重要变更。格式遵循 [Keep a Changelog](https://keepachangelog.com/)。

## [0.1.0] - 2026-06-03

### Added

- **项目骨架**：pyproject.toml，零外部依赖，Python >= 3.10
- **核心数据模型**：RiskLevel(R0-R3), TaskType(8种), SkillResult, ProjectContext
- **Skill 基类**：`__init_subclass__` 自动注册，can_run/run 接口分离
- **技术栈检测器**：11 种技术标记文件检测（Python/Node/Chrome Extension/FastAPI/Vue/React/Tailwind/Docker/Vite/Git/TypeScript）
- **文档状态检测器**：10 种常见文档覆盖率检测
- **入口文件检测器**：Python/Node.js/Chrome Extension 入口检测
- **repo.scan Skill**：仓库扫描（技术栈 + 入口 + 文档 + 目录树），R0 只读
- **Risk Controller**：运行时风险检查，R2/R3 enforce 拦截
- **Reporter**：执行前/后输出模板（协议 §6 + §7）
- **task.plan Skill**：三档方案（保守/推荐/深度），R0 只读
- **开发进度文档**：docs/development-progress.md

### Changed

- repo_scan 从单文件重构为 skill.yaml + skill.py 目录结构
- 协议加入 git 提交规则（§3.6 + §5 第 10 步 + §4 第 16 条）

### Test

- 64 个测试全部通过
- 覆盖：Skill 基类、三个检测器、repo.scan、Risk Controller、Reporter、task.plan
