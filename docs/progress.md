# 项目进度

## 当前状态

**阶段：** 方法论文档整理与软件开发推进模型细化

**最近更新时间：** 2026-05-12

当前项目已经从原始讨论资料整理为一个以“小步快跑 Small Pace, Run Fast”为核心的方法论文档库，并开始将软件开发场景沉淀为可执行模型和 Skill。

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

---

## 下一步

1. 试用 `skills/small-pace-run-fast-development/SKILL.md` 处理一个真实开发任务。
2. 试用 `skills/git-clone-accelerator/SKILL.md` 处理一次 GitHub 仓库克隆。
3. 根据试用结果压缩 Skill 文本，必要时拆出 `references/`。
4. 继续沉淀视觉提示词系统对应 Skill。
5. 决定是否将 `docs/software-delivery-model.md` 中的模板拆成独立模板文件。

---

## 当前文档地图

- `README.md`：项目入口与文档地图
- `docs/methodology.md`：小步快跑总方法论
- `docs/software-delivery-model.md`：软件开发推进模型
- `docs/visual-prompt-system.md`：视觉提示词系统
- `docs/references.md`：参考资料与推导记录
- `docs/progress.md`：项目进度
- `skills/small-pace-run-fast-development/SKILL.md`：软件开发推进模型 Skill
- `skills/git-clone-accelerator/SKILL.md`：GitHub 克隆加速 Skill
