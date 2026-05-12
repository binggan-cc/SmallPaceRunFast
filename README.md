# Small Pace, Run Fast

**小步快跑（Small Pace, Run Fast）** 是一套面向 AI 协作、软件开发、视觉提示词、内容生产与复杂项目推进的动态方法论。

它不把项目推进理解成固定流水线，而是强调：

```text
从任意阶段切入
→ 判断当前状态
→ 选择最小可验证动作
→ 执行
→ 验证
→ 回流或继续
→ 留痕沉淀
```

核心原则是：

* 任意阶段可进入；
* 阶段之间可前后校验；
* 流程强度按复杂度伸缩；
* 每次推进都形成“识别 → 行动 → 验证 → 留痕”的小闭环。

## 文档地图

建议阅读顺序：

1. [小步快跑方法论](docs/methodology.md)
   - 项目的核心文档。
   - 定义“小步快跑”的原则、阶段网络、任意阶段切入机制、复杂度裁剪方式和多场景落地。

2. [小步快跑 · 软件开发推进模型](docs/software-delivery-model.md)
   - 方法论在软件开发中的落地。
   - 覆盖需求门禁、任务拆解、小步实现、分层测试、Bug 回流、新需求处理和 Git 证据链。

3. [小步快跑 · 图片逆向提示词 / 视觉提示词系统](docs/visual-prompt-system.md)
   - 方法论在视觉生成和图片逆向 Prompt 中的落地。
   - 核心流程是从参考图或已有 Prompt 中提炼 Style DNA、构建 Style Shell、调优并沉淀 Golden Template。

4. [参考资料与推导记录](docs/references.md)
   - 早期研究笔记、英文资料对照、Skill 草案和方法论命名推导。
   - 适合用于追溯方法论形成过程，不作为主入口文档。

5. [项目进度](docs/progress.md)
   - 记录当前文档整理、外部参考提取和 Skill 沉淀进度。

6. [小步快跑 · 软件开发推进模型 Skill](skills/small-pace-run-fast-development/SKILL.md)
   - 面向 AI Agent 的可执行 Skill 版本。
   - 用于软件开发任务中的需求门禁、任务拆解、小步实现、分层验证、Bug 回流和 Git 证据链。

7. [Git Clone Accelerator Skill](skills/git-clone-accelerator/SKILL.md)
   - 克隆 GitHub 仓库时自动使用 `https://git.d8b.co/` 前缀进行加速。
   - 用于降低直接访问 GitHub 失败或过慢的概率。

## 当前定位

本仓库当前主要是方法论与工作流文档库，后续可以继续扩展为：

* AI 协作项目推进手册；
* 软件开发流程 Skill；
* Git 克隆加速 Skill；
* 视觉提示词 Skill；
* 内容生产 Skill；
* Agent 工作流编排规范；
* 团队项目推进模板。

## 最小表达

> **Small Pace, Run Fast：从任意阶段切入，用最小可验证步长推进复杂项目。**
