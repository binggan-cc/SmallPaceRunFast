# Prompt Knowledge Base 历史原型分析

## 0. 文档定位

本文档用于分析历史记录 `docs/chat.md` 与本地目录 `prompt-knowledge-base/` 对当前“小步快跑 · 图片逆向提示词 / 视觉提示词系统”的参考价值。

结论：

> `prompt-knowledge-base/` 不应直接替代当前视觉提示词系统，而应作为“数据驱动的 Prompt 知识库 / 检索 / 模板组装层”补充到当前体系中。

---

## 1. 已发现的历史资产

### 1.1 设计记录

`docs/chat.md` 是早期设计记录，覆盖以下方向：

- 提示词原子化拆解；
- 多维度 taxonomy；
- 摄影角度标准化；
- PromptFill 式 `{{variable}}` 模板语法；
- 提示词检索、组装、导出；
- 图像逆向提示词与迭代优化；
- “小步快跑”作为提示词知识库项目名的形成过程。

### 1.2 本地知识库原型

`prompt-knowledge-base/` 已经具备一个较完整的原型结构：

| 模块 | 价值 |
| --- | --- |
| `01-raw-prompts/` | 来自 7 个视觉提示词相关仓库的原始数据 |
| `02-parsed-data/` | 结构化解析后的提示词数据 |
| `03-taxonomy/` | 角度、景别、镜头等分类体系 |
| `04-templates/` | 可复用 Prompt 模板 |
| `05-analysis/` | 统计报告与趋势分析 |
| `06-scripts/` | 提取、解析、统计脚本 |
| `web/` | 可视化筛选界面原型 |
| `skill/` | 旧 OpenClaw Skill 查询工具 |
| `core/` | 图像逆向、相似度比对、迭代优化原型 |
| `exports/` | JSON / CSV / Markdown 导出数据 |

该目录当前适合作为参考原型与素材池；不建议整体纳入主仓库。

已将可复用资产迁移到父级独立目录：

```text
/Volumes/elements/repos/codex/prompt-knowledge-assets/
```

迁移后的资产库保留文档、结构化数据、导出数据、taxonomy、模板、分析报告和轻量 pipeline；跳过 1.7GB 的原始克隆仓库。

---

## 2. 与当前视觉提示词系统的关系

当前 `docs/visual-prompt-system.md` 侧重方法论：

```text
参考图 / 需求 / Prompt
→ Style DNA
→ Style Shell + Content Slots
→ Prompt Pack
→ Tuning Loop
→ Golden Template
```

`prompt-knowledge-base/` 侧重数据工程：

```text
大量 Prompt 样本
→ 14 维解析
→ taxonomy
→ 统计规律
→ 检索推荐
→ 模板组装
```

两者合并后的完整结构应是：

```text
视觉方法论层
  ↓
任务路由与 Skill 层
  ↓
Prompt Schema / Taxonomy 层
  ↓
样本知识库 / 检索 / 模板组装层
  ↓
生成验证 / 调优 / 沉淀层
```

---

## 3. 最有扩展价值的内容

### 3.1 Visual Prompt Schema v1.0

历史记录中的 14 维解析模型可作为当前 Style DNA Report 的结构化升级：

| 维度 | 用途 |
| --- | --- |
| Subject | 主体类型、人物、产品、场景 |
| Action & Pose | 动作、姿态、表情、视线 |
| Shot Type | 极特写、特写、中景、全身、广角 |
| Camera Angle | 平视、仰拍、俯拍、鸟瞰、斜角、虫瞰 |
| Lens | 24mm、35mm、50mm、85mm、macro、fisheye、tilt-shift |
| Composition | 三分法、居中、对称、引导线、动态构图 |
| Lighting | 自然光、影棚光、黄金时刻、霓虹、电影光 |
| Mood | 戏剧性、神秘、宁静、怀旧、欢快 |
| Era & Style | 年代、艺术风格、具体流派 |
| Color & Tone | 色彩方案、主色、饱和度、对比度 |
| Background | 场景、背景复杂度、空间深度 |
| Technical | 分辨率、画幅、景深、质量标签 |
| Material | 金属、玻璃、织物、木材、液体等 |
| Additional | 道具、特效、文字、水印、附加元素 |

建议将该 Schema 用于：

- 图片逆向分析；
- Prompt 质量检查；
- 知识库检索条件；
- Golden Template 的变量槽设计。

### 3.2 Camera / Angle 专家层

历史原型中的角度速查和统计报告可以补强图片与视频 Skill：

| 控制项 | 可沉淀用途 |
| --- | --- |
| Shot Type | 决定主体范围与信息密度 |
| Camera Angle | 决定权力关系、心理感受、戏剧性 |
| Lens | 决定空间压缩、透视、虚化和真实感 |
| Depth of Field | 决定焦点控制和质感 |
| Composition | 决定视觉秩序和可读性 |

这部分不需要变成独立大文档，短期可放入模板组装 Skill 的变量银行。

### 3.3 `{{variable}}` 模板语法

当前视觉系统已经使用 `{SUBJECT}`、`{SCENE}` 这类槽位。历史原型中 PromptFill 的 `{{variable}}` 更适合作为统一语法：

```text
{{subject}}, {{shot_type}}, {{camera_angle}}, {{lens}},
{{lighting}}, {{style_shell}}, {{background}},
{{quality_tags}}, {{negative_constraints}}
```

建议统一规则：

- `{{variable}}` 表示可替换槽位；
- `Style Shell` 中的核心变量默认锁定；
- `Content Slots` 中的变量默认允许替换；
- 同一变量名在模板中出现多次时必须保持一致；
- 变量银行同时保留中文解释和英文生成词。

### 3.4 知识库检索能力

`prompt-knowledge-base/` 已有 7092 条提示词样本和统计数据。它可以用于：

- 找相似提示词；
- 统计某类镜头、角度、风格的常见组合；
- 给新 Prompt 提供参考模块；
- 给图片逆向任务提供“相似案例”；
- 给模板组装提供变量候选。

这部分建议先沉淀为 `prompt-knowledge-base-query` Skill，而不是直接改造旧 JS 工具。

### 3.5 迭代优化原型

历史原型中的图像逆向迭代链路：

```text
原图
→ 图像分析
→ 初始 Prompt
→ 知识库匹配
→ Prompt 优化
→ 生成图像
→ 相似度比对
→ 继续迭代
```

与当前 `Tuning Loop` 高度一致，但工具化成本更高。建议暂时作为路线图，不立即拆成正式 Skill。

---

## 4. 建议新增 Skill

### 4.1 `prompt-knowledge-base-query`

定位：数据驱动的视觉 Prompt 参考检索 Skill。

适用场景：

- 用户要求“从知识库找参考”；
- 用户指定镜头、角度、风格、主体进行查询；
- 用户希望用历史提示词样本增强当前 Prompt；
- 当前图片或视频 Prompt 需要相似案例支持。

核心输出：

```markdown
## Query Intent
## Matching Dimensions
## Reference Patterns
## Reusable Prompt Blocks
## Suggested Template
```

### 4.2 `visual-prompt-template-composer`

定位：基于 `{{variable}}` 的视觉 Prompt 模板组装 Skill。

适用场景：

- 把 Prompt 模板化；
- 将 Style Shell 与 Content Slots 拆开；
- 建立变量银行；
- 生成多个模板实例；
- 把一次 Lucky Hit 沉淀为 Golden Template。

核心输出：

```markdown
## Template
## Variables
## Variable Bank
## Locked Style Shell
## Replaceable Slots
## Example Instantiations
```

---

## 5. 暂不建议立刻新增的 Skill

### `visual-iteration-optimizer`

该方向有价值，但暂不建议立刻做成正式 Skill。

原因：

- 依赖图像生成 API；
- 依赖图像相似度算法；
- 需要验证工具链；
- 容易从方法论扩展成完整产品工程。

建议先保留为后续路线：

```text
Phase A: 手动 Tuning Loop
Phase B: 知识库辅助检索
Phase C: 模板化变量控制
Phase D: 半自动图像对比
Phase E: 自动迭代优化
```

---

## 6. 与当前文档的整合方式

建议整合为三层：

1. `docs/visual-prompt-system.md`
   - 增加“知识库层 / 模板组装层”概念；
   - 保持为主方法论文档。

2. `docs/visual-generation-prompt-extraction.md`
   - 继续作为精选提示词素材抽取层；
   - 适合手工归纳高价值模板。

3. `docs/prompt-knowledge-base-analysis.md`
   - 记录历史原型分析；
   - 决定哪些能力进入主体系；
   - 避免把旧项目整体混入主文档。

---

## 7. 下一步

1. 新增 `prompt-knowledge-base-query` Skill。
2. 新增 `visual-prompt-template-composer` Skill。
3. 更新 README 与进度文档。
4. 已将历史素材迁移到 `/Volumes/elements/repos/codex/prompt-knowledge-assets/`。
5. 后续再决定是否：
   - 删除当前仓库中未跟踪的 `docs/chat.md`；
   - 删除当前仓库中未跟踪的 `prompt-knowledge-base/`；
   - 将 `prompt-knowledge-assets/` 作为独立资产库提交到父仓库；
   - 将 Visual Prompt Schema 拆成独立规范文档。
