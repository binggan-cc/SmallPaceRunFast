# 小步快跑 · 图片逆向提示词 / 视觉提示词系统 v1.0

## 0. 文档定位

**中文名称：** 小步快跑 · 图片逆向提示词 / 视觉提示词系统
**英文名称：** Small Pace, Run Fast · Iterative Prompt Architect System
**核心角色原型：** Iterative Prompt Architect（IPA）
**历史版本基底：** IPA v3.0
**文档版本：** v1.0
**文档性质：** 方法论文档 / Skill 设计基础 / 视觉 Prompt 系统原型说明 / 图片与视频创作工作流

---

## 1. 一句话定义

> **“小步快跑 · 图片逆向提示词 / 视觉提示词系统”是一套面向图片、视频、图生视频、分镜与视觉风格复用的迭代式提示词架构方法：它以参考图片、优质提示词、创作目标或生成结果为起点，通过深度解码、结构重建、生成验证、精细调参与模板沉淀，把一次偶然生成的 Lucky Hit，升级为可复用、可迁移、可稳定复现的 Golden Formula。**

---

## 2. 项目最初要解决的问题

### 2.1 传统图片逆向提示词的局限

许多“图片逆向 Prompt”工作停留在表层描述：

* 图里有什么；
* 是什么风格；
* 大概是什么色调；
* 把画面翻译成一段自然语言。

这种方式的问题在于：

1. **只能描述画面，不能解释画面为什么成立；**
2. **只能复述视觉结果，不能提炼可复用结构；**
3. **生成结果偏差时，无法定位该改哪一部分；**
4. **同风格换主体时，提示词往往失效；**
5. **无法把一次“运气好”的图，沉淀成稳定的方法。**

---

### 2.2 该系统真正想做的事

它不是一个简单的“反推提示词工具”，而是一个：

> **视觉风格解码器 + 提示词结构工程师 + 生成调参教练 + 模板沉淀系统。**

其真正目标不是“复制”，而是：

* 解码；
* 翻译；
* 优化；
* 模块化；
* 稳定复用。

---

## 3. 核心理念：从 Lucky Hit 到 Golden Formula

### 3.1 两个关键词

#### Lucky Hit

指一次偶然得到的好图：

* 可能来自一个不错的提示词；
* 可能来自某次偶发组合；
* 画面效果好，但生成逻辑尚未被拆解；
* 下次很难稳定复现。

#### Golden Formula

指经过拆解、验证与优化后形成的稳定视觉配方：

* 有明确的结构；
* 有不可动的风格核心；
* 有可替换的内容槽位；
* 能持续适配不同主题；
* 能保持一致的审美质量。

---

### 3.2 转化逻辑

```text
Lucky Hit
  ↓
Deep Decoding
  ↓
Style DNA Report
  ↓
Style Shell + Content Slots
  ↓
V1 Prompt
  ↓
Generation Test
  ↓
Precision Adjustment
  ↓
Golden Template
```

---

## 4. 与“小步快跑”的关系

“小步快跑”最早在图片逆向提示词场景中出现，是非常自然的。

因为这个场景本质上就是：

```text
给定图片
  ↓
先反推结构
  ↓
拆成主体 / 构图 / 风格 / 材质 / 光影 / 镜头
  ↓
生成第一版提示词
  ↓
出图验证
  ↓
局部修正提示词
  ↓
再生成
  ↓
最终沉淀为可复用模板
```

---

### 4.1 “小步”体现在哪里

* 不直接妄图一次性写出完美 Prompt；
* 先解码，再建模，再生成；
* 每次只调整一个或少数几个关键变量；
* 通过出图结果来验证哪一块结构有效；
* 让提示词从“整段黑盒”变成“可拆、可控、可修”的系统。

---

### 4.2 “快跑”体现在哪里

* 每一轮生成都服务于下一轮优化；
* 每轮反馈周期短；
* 每轮都让结构更清楚；
* 不是重复试错，而是带着判断推进；
* 最终沉淀为模板后，后续同类视觉需求可以显著提速。

---

### 4.3 它不是慢工出细活，而是高密度有效迭代

> **小步，不是犹豫；快跑，不是乱试。**
> **它强调的是：每一步都足够小，足够清楚，足够可验证，因此整体反而更快。**

---

## 5. 系统角色：Iterative Prompt Architect（IPA）

### 5.1 角色定义

> **IPA 不是普通提示词生成器，而是 AI Visual Architect。**
> 它负责把一个模糊的视觉意图、参考图片或已有提示词，转化为具备工程结构的视觉生成方案。

---

### 5.2 IPA 的使命

#### 1. Decode & Translate

将模糊审美意图翻译为精确的视觉生成约束。

例如：

* Cozy → Warm Color Temperature + Soft Diffusion
* Professional → Symmetrical Composition + Clean Lines + Cool Lighting
* Realistic → Photorealistic Texture + Depth of Field + Natural Lens Behavior

#### 2. Optimize, Don’t Just Copy

如果原图有缺陷，不盲目照抄，而是在保留核心风格的前提下进行升级。

#### 3. Modular Architecture

把提示词视为由两部分组成：

* **Style Shell：** 风格外壳，决定视觉一致性；
* **Content Slots：** 内容槽位，允许更换主体、场景、对象。

---

## 6. 核心哲学：青出于蓝而胜于蓝

### 6.1 原始表述

> **Blue comes from Indigo, but is Bluer.**
> **青出于蓝而胜于蓝。**

---

### 6.2 在视觉提示词中的含义

图片逆向不是机械复刻，而是三步走：

1. **识别原图真正有效的审美机制；**
2. **剥离偶然因素和无效杂质；**
3. **把有效机制强化为更稳定的模板。**

也就是说：

* 可以保留原图的风格 DNA；
* 但不必保留原图的缺陷；
* 可以复现其视觉精神；
* 还可以让它更清晰、更稳定、更易迁移。

---

## 7. 核心工作流：The Transcendence Loop

该系统的核心不是一次性逆向，而是一个四阶段循环：

```text
Phase 1  Deep Decoding & Aesthetic Audit
Phase 2  Structural Engineering / Style Shell
Phase 3  Tuning Loop / Precision Adjustment
Phase 4  Golden Template / Final Deliverable
```

---

## 8. Phase 1：Deep Decoding & Aesthetic Audit

### 8.1 触发条件

当用户提供以下任一材料时进入：

* 一张参考图片；
* 一组参考图片；
* 一个已有 Prompt；
* 一张“效果很好但难以复现”的生成图。

---

### 8.2 阶段目标

不是立即写 Prompt，而是先进行视觉 X-Ray：

> **看清这张图真正成立的原因。**

---

### 8.3 三类分析动作

#### 1. Implicit Features：隐性特征识别

找出“看得见，但用户通常不会主动说出来”的特征，例如：

* Isometric View；
* Matte Finish；
* Tilt-Shift；
* Shallow Depth of Field；
* Editorial Poster Layout；
* Miniature Architectural Scale；
* Clean Solid Background；
* Soft Diffusion；
* Bokeh；
* Volumetric Light。

---

#### 2. The Magic Ingredient：魔法成分识别

回答：

> 这张图真正让人觉得“好”的关键是什么？

可能是：

* 光影对比；
* 材质混搭；
* 构图秩序；
* 低饱和配色；
* 留白比例；
* 视觉中心控制；
* 建筑级块面关系；
* 柔和但精准的层级组织。

---

#### 3. Aesthetic Audit：审美审计

判断原图是否存在问题：

* 主体被裁切；
* 背景过乱；
* 色彩脏；
* 层级不清；
* 细节密度不均；
* 风格不够统一；
* 材质表达冲突；
* 主体比例不高级。

---

### 8.4 输出物：Style DNA Report

建议格式：

```markdown
## Style DNA Report

### 1. Core Visual Identity
- ...

### 2. Non-negotiable Keywords
- ...

### 3. Implicit Visual Features
- ...

### 4. Magic Ingredient
- ...

### 5. Aesthetic Weaknesses to Improve
- ...

### 6. Recommended Optimization Direction
- ...
```

---

## 9. Phase 2：Structural Engineering（The Style Shell）

### 9.1 阶段目标

把 Phase 1 的分析结果，转化为可执行的第一版 Prompt。

---

### 9.2 核心思想：Style Shell + Content Slots

#### Style Shell

决定风格一致性的部分，一般不轻易动：

* 艺术方向；
* 渲染媒介；
* 画面构图；
* 镜头视角；
* 光线逻辑；
* 材质体系；
* 综合色调；
* 画面干净度；
* 风格关键词。

#### Content Slots

允许替换的部分：

* 主体；
* 场景对象；
* 品牌符号；
* 行业主题；
* 小道具；
* 局部内容。

---

### 9.3 Prompt 结构

基础结构可写作：

```text
[Art Direction / Medium]
+ [Camera / View]
+ [Lighting / Atmosphere]
+ {SUBJECT SLOT}
+ [Material / Texture]
+ [Composition / Background]
+ [Quality Reinforcement]
+ --parameters
```

---

### 9.4 示例

#### 原始描述

> Concept store shaped like a camera.

#### IPA 重构版

> Isometric 3D render, architectural scale model, **{SUBJECT: Vintage Camera}** converted into a concept store, translucent glass facade, warm interior glow, soft clay materials, octane render, clean solid background.

---

### 9.5 为什么更好

因为它新增了几个非常关键的控制项：

* **Isometric 3D render**：固定空间视角；
* **Architectural scale model**：避免只是“一个玩具相机”；
* **Translucent glass facade**：明确建筑感；
* **Warm interior glow**：增强叙事与空间深度；
* **Soft clay materials**：建立统一材质气质；
* **Clean solid background**：保持画面高级和可读。

---

### 9.6 阶段输出

* V1 Prompt；
* Prompt 结构说明；
* Style Shell；
* Content Slots；
* 关键技术词解释。

---

## 10. Phase 3：The Tuning Loop（Precision Adjustment）

### 10.1 阶段目标

根据生成结果的偏差，进行精准局部修正。

---

### 10.2 触发条件

* 用户反馈结果不准确；
* 生成结果与参考图差异明显；
* 同样风格换主体后失真；
* 视觉质量不稳定。

---

### 10.3 调整原则

1. 不要每次整条 Prompt 推倒重写；
2. 先判断问题属于哪个视觉维度；
3. 每次优先修正最关键的一处偏差；
4. 修改后要说明为什么这样改；
5. 尽量让用户理解提示词背后的控制逻辑。

---

### 10.4 常见问题 → 调整方向

| 问题          | 可能原因            | 调整思路                                                            |
| ----------- | --------------- | --------------------------------------------------------------- |
| 太像玩具，不像建筑   | 材质过软、缺少尺度参照     | 增加 concrete / glass / human-scale reference                     |
| 画面不够高级      | 背景乱、配色不统一       | clean background / restricted palette / editorial composition   |
| 主体像贴图，不融入环境 | 缺乏空间关系          | add volumetric light / contact shadow / integrated architecture |
| 不像参考图风格     | Style Shell 不够强 | 加强 medium / lighting / camera / material constraints            |
| 同风格换主体后崩掉   | 内容槽与风格壳耦合不清     | 重写 Content Slot，锁定 Shell                                        |

---

### 10.5 建议输出格式

每次调优都应包含：

```markdown
> **Architect's Analysis:**
> - Problem:
> - Cause:
> - Adjustment Strategy:

### Updated Prompt
（标注新增或修改的关键词）

### Why These Changes Matter
- ...
```

---

### 10.6 “小步快跑”的迭代特征

该阶段是“小步快跑”最明显的体现：

* 一轮只修正关键偏差；
* 一轮就能看到效果；
* 一轮结果又反哺下一轮 Prompt；
* 越跑越稳，而不是越改越乱。

---

## 11. Phase 4：The Golden Template（Final Deliverable）

### 11.1 触发条件

当结果已经满足以下条件时进入：

* 视觉效果稳定；
* 风格核心清楚；
* 换主体后仍能保持一致性；
* 关键控制词已验证有效；
* 冗余词已被削减；
* 具备复用价值。

---

### 11.2 最终交付内容

#### 1. Modular Template

明确标记：

* 不可动的 Style Shell；
* 可替换的 Content Slots；
* 可选增强项；
* 负面约束；
* 模型参数。

#### 2. Lock the Style

说明哪些关键词尽量不要动，以维持风格稳定，例如：

* isometric；
* soft lighting；
* architectural scale model；
* clean solid background；
* premium editorial render。

#### 3. Change This Section

明确告诉用户应该替换哪里：

```text
{SUBJECT}
{BRAND OBJECT}
{SCENE ELEMENT}
{COLOR ACCENT}
```

#### 4. Reference Enhancement（可选）

如果平台支持，可建议：

* 使用最优结果作为 style reference；
* 使用 sref / cref / image reference；
* 使用结构参考或局部图像锚定。

---

### 11.3 示例模板结构

```text
[STYLE SHELL]
Isometric 3D render, architectural scale model, premium editorial composition, soft diffused lighting, warm interior glow, subtle ambient occlusion, clean solid background, refined material contrast, highly coherent visual hierarchy.

[CONTENT SLOT]
{SUBJECT} transformed into {FUNCTIONAL SCENE OR ARCHITECTURAL CONCEPT}, featuring {KEY STRUCTURAL ELEMENTS}.

[MATERIAL & DETAIL]
Translucent glass facade, matte clay surfaces, brushed metal accents, soft shadow transitions, elegant micro details.

[NEGATIVE CONSTRAINTS]
No cluttered background, no messy text, no distorted proportions, no oversaturated colors, no low-detail toy-like appearance.
```

---

## 12. Mental Framework：Implicit to Explicit Table

### 12.1 方法目标

将用户的主观感受，翻译为模型可执行的视觉约束。

---

### 12.2 示例

| 用户语言         | IPA 转译                                                                             |
| ------------ | ---------------------------------------------------------------------------------- |
| Cute         | Chibi proportions, rounded edges, pastel palette                                   |
| Professional | Symmetrical composition, cool blue lighting, high contrast, clean lines            |
| Real         | Photorealistic texture, depth of field, ray tracing, natural lens behavior         |
| Cozy         | Warm color temperature, soft diffusion, fabric texture, low contrast               |
| Premium      | Restrained palette, editorial balance, material refinement, negative space         |
| Futuristic   | Sleek geometry, luminous accents, high-tech material contrast, clean spatial order |

---

## 13. 标准输出规范

### 13.1 每次回答建议从分析块开始

```markdown
> **Architect's Analysis:**
> ...
```

---

### 13.2 必须解释“为什么”

不仅要给 Prompt，还要解释：

* 为什么加入这个词；
* 它控制什么；
* 解决什么偏差；
* 对最终风格稳定性有什么意义。

---

### 13.3 调整时应标记变化

对于二次修改或迭代版本，应尽量：

* 标出新增词；
* 标出删除词；
* 标出加重权重的词；
* 说明本轮主要修正目标。

---

## 14. 初始化交互

当系统首次启动时，应询问用户提供 Source Material：

* 图片；
* Prompt；
* 或者一个已有但不稳定的生成结果。

并确认本次目标：

> **Do you want to strictly replicate this style, or should we optimize and elevate it?**

中文可表达为：

> **你希望我严格复刻这套视觉风格，还是在保留核心风格的前提下，把它优化并升级成更稳定的模板？**

---

## 15. 与 Visual Prompt OS 的关系

“小步快跑 · 图片逆向提示词系统”可以视为 Visual Prompt OS 的早期核心模块之一。

如果 Visual Prompt OS 是一个完整的视觉提示词资产系统，那么 IPA / 图片逆向模块负责解决其中的：

* 视觉参考输入；
* 风格 DNA 提取；
* Prompt 模板化；
* 风格壳与内容槽拆分；
* 模板迭代与验证；
* 从单次生成到可复用资产的跃迁。

可以对应为：

```text
Observe → Deconstruct → Structure → Optimize
```

其中：

* **Observe：** 看图、读图、识别隐性特征；
* **Deconstruct：** 拆成主体、构图、材质、风格等维度；
* **Structure：** 搭建 Style Shell 与 Content Slots；
* **Optimize：** 通过 Tuning Loop 沉淀 Golden Template。

---

## 16. v1.0 落地扩展：多入口视觉 Prompt 系统

`docs/visual-generation-prompt-extraction.md` 已经把 `提示词/`、`learned/`、父仓库 `prompts/` 和 `notes/` 中的图片、视频、图生视频、分镜、社媒视觉、PPT 视觉与风格解构材料抽取为素材中间层。v1.0 的升级目标，是把这些材料从“模板集合”组织成“按任务入口自动路由的创作系统”。

---

### 16.1 入口路由

| 用户输入 | 进入模块 | 首要动作 | 输出物 |
| --- | --- | --- | --- |
| 参考图、好图、已有 Prompt | Reverse Engineering | 解码 Style DNA 与可迁移结构 | Style DNA Report、V1 Prompt、Golden Template |
| 想生成一张图 | Image Prompt Architecture | 选择图片模板族并构造视觉约束 | Image Prompt Pack |
| 想让图片动起来 | Image-to-Video Architecture | 锁定主体身份、运动、镜头与时长 | I2V Prompt Pack |
| 想生成视频 | Video Prompt Architecture | 拆成镜头、动作、时间、节奏 | Video Prompt Pack |
| 想做分镜、动作页、角色设定 | Storyboard / Sheet Architecture | 转换为画格、镜头、姿态与一致性约束 | Storyboard Prompt Pack |
| 已经出图或出片但不满意 | Tuning Loop | 定位偏差维度并小步修正 | Updated Prompt、Adjustment Notes |
| 想形成一套长期风格 | Style System | 提炼 Style Shell、可变槽位与禁止项 | Visual Style System |

---

### 16.2 模板选择地图

| 创作目标 | 优先参考抽取文档章节 | 适合场景 |
| --- | --- | --- |
| 知识科普图、教育海报 | `3.1 Knowledge Infographic`、`3.2 Apple-style Science Poster` | 知识号、课程、科普图文 |
| 标本图、解剖图、结构图 | `3.3 Specimen / Anatomical Plate` | 生物、器物、产品结构展示 |
| 字体海报、水滴字、宏观文字 | `3.4 Typography / Macro Water Typography` | 品牌字效、封面、视觉实验 |
| 时尚大片、产品摄影 | `3.5 Fashion / Product Editorial` | 电商、品牌视觉、广告图 |
| 主题肖像、人物大片 | `3.6 Theme-driven Editorial Portrait` | 头像、IP 人设、人物封面 |
| 世界观设定、概念场景 | `3.7 Worldbuilding Visual System` | 游戏、影视、小说设定 |
| 纸雕、微缩、立体书 | `3.8 Paper Diorama / Miniature World` | 趣味场景、儿童内容、展示图 |
| 小红书四宫格、社媒封面 | `3.9 Xiaohongshu 2x2 Wellness Grid`、`7. Social / Ad / PPT` | 社媒种草、轻知识、生活方式 |
| 动作页、角色设定、专业分镜 | `4. Storyboard / Action Sheet` | 动画、短片、游戏动作设计 |
| 15 秒短片、VFX 视频、图生视频 | `5. Video Prompt Templates`、`6. Camera Presets` | Seedance、Veo、Runway、Kling 类工作流 |
| 风格逆向、品牌视觉 DNA | `8. Style DNA / Reverse Engineering` | 参考图拆解、品牌模板沉淀 |

---

### 16.3 图片 Prompt 输出契约

图片生成任务不只输出一段 Prompt，而应输出一个可迭代包：

```markdown
## Image Prompt Pack

### 1. Visual Goal
- ...

### 2. Selected Template Family
- ...

### 3. Core Prompt
...

### 4. Style Shell
- Medium:
- Composition:
- Lighting:
- Camera / Lens:
- Material:
- Palette:
- Detail Density:

### 5. Content Slots
- {SUBJECT}
- {SCENE}
- {OBJECT}
- {TEXT}
- {COLOR_ACCENT}

### 6. Negative Constraints
- ...

### 7. Variants
- Safer:
- More editorial:
- More realistic:

### 8. First Test Focus
- This round should verify ...
```

---

### 16.4 视频与图生视频 Prompt 输出契约

视频任务必须显式控制时间、动作和镜头，不能只把图片 Prompt 改成动态描述。

```markdown
## Video Prompt Pack

### 1. Format
- Text-to-video / Image-to-video / Multi-shot storyboard
- Duration:
- Aspect ratio:
- Platform:

### 2. Subject Lock
- Identity:
- Clothing / object consistency:
- Scene consistency:

### 3. Timeline
- 0-3s:
- 3-6s:
- 6-10s:
- 10-15s:

### 4. Motion
- Subject motion:
- Environmental motion:
- Transition:

### 5. Camera
- Framing:
- Movement:
- Lens behavior:

### 6. Visual Style
- ...

### 7. Negative Constraints
- no identity drift
- no warped anatomy
- no unstable text
- no flicker
- no sudden scene jump

### 8. Verification Focus
- This round should verify ...
```

---

### 16.5 图片逆向与风格复用输出契约

逆向任务要先解释视觉成立机制，再生成可迁移模板。

```markdown
## Reverse Prompt Pack

### 1. Style DNA Report
- Core visual identity:
- Non-negotiable keywords:
- Implicit visual features:
- Magic ingredient:
- Weaknesses to improve:

### 2. Reconstructed Prompt
...

### 3. Style Shell
- Keep:
- Avoid changing:

### 4. Replaceable Slots
- ...

### 5. Upgrade Direction
- Strict replication:
- Elevated version:

### 6. Golden Template
...
```

---

### 16.6 调优回路

当用户提供生成结果时，必须先定位偏差，再改 Prompt。

| 偏差类型 | 优先检查 | 修正方向 |
| --- | --- | --- |
| 主体不像 | Subject Lock / Content Slot | 加强身份、比例、关键特征、参考约束 |
| 风格不像 | Style Shell | 强化媒介、光线、材质、镜头、构图 |
| 画面乱 | Composition / Negative Constraints | 收紧背景、层级、色彩、元素数量 |
| 视频跳变 | Timeline / Camera / Subject Lock | 减少镜头切换、锁定服装和环境、简化动作 |
| 图生视频变形 | Motion Strength / Identity Lock | 降低运动幅度、明确不可变化区域 |
| 字体或文字错误 | Text Strategy | 减少可生成文字，必要时后期排版 |

每轮调优只改变最关键的 1-3 个变量，并说明：

```markdown
Problem → Cause → Adjustment → Expected Effect
```

---

### 16.7 Skill 拆分

v1.0 建议沉淀为五类可执行 Skill：

1. `visual-prompt-architect`：总入口与路由，负责判断任务类型、选择输出契约、管理小步快跑调优。
2. `image-prompt-architect`：图片生成、图片逆向、视觉模板化与风格复用。
3. `video-prompt-architect`：视频生成、图生视频、分镜、动作页与镜头节奏控制。
4. `prompt-knowledge-base-query`：从 `prompt-knowledge-base/` 的样本、统计和 taxonomy 中提取参考模式。
5. `visual-prompt-template-composer`：使用 `{{variable}}` 语法把 Prompt 沉淀为可复用 Golden Template。

---

### 16.8 知识库层与模板组装层

历史原型 `docs/chat.md` 与 `prompt-knowledge-base/` 提供了当前系统缺少的数据工程层：

```text
大量 Prompt 样本
→ 14 维解析
→ taxonomy
→ 统计规律
→ 检索推荐
→ 模板组装
```

这部分可作为视觉提示词系统的“知识库层”，但不替代 IPA 工作流。它的作用是为 Style DNA、Prompt Pack 和 Golden Template 提供参考证据与变量候选。

建议统一使用以下 14 维 Visual Prompt Schema：

| 维度 | 用途 |
| --- | --- |
| Subject | 主体、人物、产品、场景 |
| Action & Pose | 动作、姿态、表情、视线 |
| Shot Type | 景别与主体范围 |
| Camera Angle | 平视、仰拍、俯拍、鸟瞰、斜角等 |
| Lens | 焦距、微距、鱼眼、移轴 |
| Composition | 构图秩序与画面组织 |
| Lighting | 光源类型、方向、质量、色温 |
| Mood | 情绪与氛围 |
| Era & Style | 年代、艺术风格、具体流派 |
| Color & Tone | 主色、饱和度、对比度 |
| Background | 背景类型、细节密度、空间深度 |
| Technical | 画幅、分辨率、景深、质量标签 |
| Material | 材质与表面特征 |
| Additional | 道具、特效、文字、水印等 |

模板组装层统一采用 `{{variable}}` 槽位语法：

```text
{{subject}}, {{shot_type}}, {{camera_angle}}, {{lens}},
{{lighting}}, {{style_shell}}, {{background}},
{{quality_tags}}, {{negative_constraints}}
```

其中：

* `Style Shell` 中的变量默认锁定；
* `Content Slots` 中的变量默认可替换；
* 同名变量在模板中必须保持一致；
* 变量银行应保留英文生成词与中文解释。

未来如果素材继续增长，可继续拆出：

* `visual-style-reverse-engineering`：专注参考图、品牌视觉和 Style DNA。
* `storyboard-prompt-architect`：专注短片、广告、动画和游戏分镜。
* `social-visual-prompt-architect`：专注小红书、TikTok、PPT 和社媒广告视觉。

---

## 17. 后续可产品化的方向

### 17.1 Skill 形态

可做成：

* 图片逆向 Prompt Skill；
* 视觉模板提炼 Skill；
* 出图调优 Skill；
* 风格 Shell 生成 Skill。

---

### 17.2 产品功能形态

可进一步产品化为：

1. 上传参考图；
2. 自动生成 Style DNA Report；
3. 生成结构化 V1 Prompt；
4. 用户补充生成结果；
5. 系统进行差异分析；
6. 自动给出调优 Prompt；
7. 多轮迭代；
8. 最终保存为模板资产。

---

### 17.3 资产库形态

最终可沉淀：

* 风格模板库；
* 构图模板库；
* 材质模板库；
* 镜头模板库；
* 行业视觉模板；
* 品牌视觉提示词模板。

---

## 18. v1.0 总结

“小步快跑 · 图片逆向提示词系统”不是“看图写描述”，而是：

> **从参考图中提炼视觉结构，从一次好运中提炼稳定配方，从偶然的好图中提炼可复用的生成能力。**

它的核心不是复制，而是：

* 解码；
* 优化；
* 模块化；
* 迭代；
* 沉淀。

最终目标，是让用户从：

> **“我偶然做出过一张好图”**

进入到：

> **“我知道这类图为什么好，也知道如何稳定地再做出来。”**
