# 项目进度

## 当前状态

**阶段：** 方法论文档整理、软件开发推进模型细化、视觉提示词系统 Skill 化 + SmartDev Agent Phase 6.2 完成

**最近更新时间：** 2026-06-06

当前项目已经从原始讨论资料整理为一个以”小步快跑 Small Pace, Run Fast”为核心的方法论文档库，并开始将软件开发场景和视觉提示词场景沉淀为可执行模型和 Skill。

### SmartDev Agent — Code Intelligence v1（2026-06-06 完成）

SmartDev Agent（`smartPi/smartdev-agent/`）已完成 Phase 6.2，具备基于 Python AST 的轻量代码结构提取、模块级 import 关系图谱、反向依赖影响分析、项目地图导出和图谱健康校验能力。310 tests passed。

该阶段已冻结，能力边界为 module-level impact analysis。下一步：Phase 6.3 — JS/TS Parser Provider。

---

## 已完成

### 文档结构整理

- [x] 将主方法论文档整理为 `docs/methodology.md`
- [x] 将视觉提示词系统整理为 `docs/visual-prompt-system.md`
- [x] 将原始资料整理为 `docs/references.md`
- [x] 新增项目入口 `README.md`
- [x] 新增软件开发推进模型 `docs/software-delivery-model.md`

### 软件开发推进模型

- [x] 建立 v1.0 文档框架
- [x] 补充核心原则
- [x] 补充复杂度裁剪
- [x] 补充阶段入口与回流机制
- [x] 补充 Gate 0 / Gate 1 / Gate 2
- [x] 补充需求发散与收敛模板
- [x] 补充 Spec、实现计划、任务卡、验收清单模板
- [x] 补充分层测试、Bug 回流、Git 证据链与 Agent 执行规范

### 外部参考资料

- [x] 克隆 `addyosmani/agent-skills`
- [x] 克隆 `Fission-AI/OpenSpec`
- [x] 克隆 `github/spec-kit`
- [x] 将外部仓库放入 `external/github/`
- [x] 将 `external/` 加入 `.gitignore`，避免第三方源码进入当前仓库提交
- [x] 将 GitHub 克隆加速规则沉淀为通用 Skill

### SmartDev Agent

- [x] Phase 1-5：10 Skill + Workflow + Adapter（8 类 Skill，完整迭代闭环）
- [x] Phase 6-MVP：SQLite 索引 + artifact 提取 + code.search + code.impact
- [x] Phase 6.2：结构提取 + import relations + ImpactAnalyzer 升级 + project.map + graph.validate
- [x] 310 tests passed，Phase 6.2 已冻结

### 视觉提示词系统

- [x] 识别 `提示词/` 目录中的图片与视频生成提示词
- [x] 识别 `learned/` 目录中的图片、视频、分镜、PPT 和社媒视觉生产相关笔记
- [x] 扫描父仓库 `prompts/` 中可复用的视觉生成提示词
- [x] 扫描父仓库 `notes/` 中与 GPT Image 2、图像工作流、视频原型相关的笔记
- [x] 新增 `docs/visual-generation-prompt-extraction.md`
- [x] 将抽取文档加入 README 文档地图
- [x] 将抽取文档引用的 69 份来源文档复制到 `prompts/` 目录
- [x] 基于抽取文档升级 `docs/visual-prompt-system.md` 的 v1.0 落地层
- [x] 提取视觉提示词总入口 Skill
- [x] 提取图片生成与图片逆向 Skill
- [x] 提取视频生成与图生视频 Skill
- [x] 分析 `docs/chat.md` 与 `prompt-knowledge-base/` 的历史原型价值
- [x] 新增 Prompt Knowledge Base 历史原型分析文档
- [x] 提取 Prompt 知识库检索 Skill
- [x] 提取视觉 Prompt 模板组装 Skill
- [x] 将 `prompt-knowledge-base/` 中可复用文档与数据资产迁移到 `/Volumes/elements/repos/codex/prompt-knowledge-assets/`

---

## 进行中

- [x] 从外部参考仓库中提取有价值的开发流程规则
- [x] 将提取内容整合进 `docs/software-delivery-model.md`
- [x] 从软件开发推进模型提取一份可复用 Skill

---

## 本轮新增

- [x] 新增 `.gitignore`，忽略 `external/`
- [x] 新增 `docs/progress.md`
- [x] 扩展 `docs/software-delivery-model.md`
- [x] 新增 `skills/small-pace-run-fast-development/SKILL.md`
- [x] 新增 `skills/git-clone-accelerator/SKILL.md`
- [x] 新增 `docs/visual-generation-prompt-extraction.md`
- [x] 扩展 `docs/visual-prompt-system.md`，增加多入口路由、模板选择地图和输出契约
- [x] 新增 `skills/visual-prompt-architect/SKILL.md`
- [x] 新增 `skills/image-prompt-architect/SKILL.md`
- [x] 新增 `skills/video-prompt-architect/SKILL.md`
- [x] 新增 `prompts/`，保存视觉生成提示词系统引用的本地参考副本
- [x] 新增 `docs/prompt-knowledge-base-analysis.md`
- [x] 新增 `skills/prompt-knowledge-base-query/SKILL.md`
- [x] 新增 `skills/visual-prompt-template-composer/SKILL.md`
- [x] 新增父级资产库 `/Volumes/elements/repos/codex/prompt-knowledge-assets/`

---

## 下一步

1. 试用 `skills/small-pace-run-fast-development/SKILL.md` 处理一个真实开发任务。
2. 试用 `skills/git-clone-accelerator/SKILL.md` 处理一次 GitHub 仓库克隆。
3. 根据试用结果压缩 Skill 文本，必要时拆出 `references/`。
4. 试用 `skills/visual-prompt-architect/SKILL.md` 处理一次真实图片逆向任务。
5. 试用 `skills/video-prompt-architect/SKILL.md` 处理一次图生视频或短视频分镜任务。
6. 试用 `skills/prompt-knowledge-base-query/SKILL.md` 从 `prompt-knowledge-base/` 查询一组真实参考模式。
7. 试用 `skills/visual-prompt-template-composer/SKILL.md` 将一个 Lucky Hit Prompt 沉淀为 `{{variable}}` 模板。
8. 决定是否将视觉 Prompt 模板拆成图片、视频、分镜、品牌解构四份子文档。
9. 清理当前仓库中未跟踪的历史素材 `docs/chat.md` 与 `prompt-knowledge-base/`。
10. 决定是否将父级资产库 `prompt-knowledge-assets/` 作为独立资产库提交。
11. 决定是否将 `docs/software-delivery-model.md` 中的模板拆成独立模板文件。

---

## 当前文档地图

- `README.md`：项目入口与文档地图
- `docs/methodology.md`：小步快跑总方法论
- `docs/software-delivery-model.md`：软件开发推进模型
- `docs/visual-prompt-system.md`：视觉提示词系统
- `docs/visual-generation-prompt-extraction.md`：图片与视频生成提示词抽取文档
- `docs/prompt-knowledge-base-analysis.md`：Prompt Knowledge Base 历史原型分析
- `docs/references.md`：参考资料与推导记录
- `docs/progress.md`：项目进度
- `smartPi/README.md`：SmartDev Agent 入口与架构概览
- `smartPi/smartdev-agent/`：SmartDev Agent Python CLI 实现（310 tests）
- `smartPi/smartdev-agent/CHANGELOG.md`：SmartDev Agent 变更记录
- `smartPi/smartdev-agent/CLAUDE.md`：SmartDev Agent 项目行为规则
- `smartPi/smartdev-agent/docs/development-progress.md`：SmartDev Agent 开发进度
- `smartPi/smartdev-agent/docs/samples/`：project.map + graph.validate 示例输出
- `prompts/`：视觉生成提示词系统引用的来源文档本地副本
- `skills/small-pace-run-fast-development/SKILL.md`：软件开发推进模型 Skill
- `skills/git-clone-accelerator/SKILL.md`：GitHub 克隆加速 Skill
- `skills/visual-prompt-architect/SKILL.md`：视觉提示词总入口与任务路由 Skill
- `skills/image-prompt-architect/SKILL.md`：图片生成与图片逆向 Skill
- `skills/video-prompt-architect/SKILL.md`：视频生成与图生视频 Skill
- `skills/prompt-knowledge-base-query/SKILL.md`：Prompt 知识库检索与参考模式提取 Skill
- `skills/visual-prompt-template-composer/SKILL.md`：视觉 Prompt 模板组装 Skill
