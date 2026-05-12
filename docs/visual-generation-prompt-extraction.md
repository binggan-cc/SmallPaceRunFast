# 图片与视频生成提示词抽取文档 v1.0

## 0. 文档定位

本文档从以下两个目录抽取图片生成、视频生成、图生视频、视觉品牌解构、分镜和社媒视觉生产相关提示词：

* `提示词/`
* `learned/`

目标不是替代原始文件，而是把分散在两个目录中的视觉生成提示词先汇总成一份可继续整理、去重、模板化和 Skill 化的中间文档。

---

## 1. 抽取范围

### 纳入范围

纳入以下类型内容：

* GPT Image / GPT Image 2 图片生成提示词；
* Seedance / 即梦 / HappyHorse / Pollo AI / MiniMax 相关视频生成提示词；
* 图生视频、分镜表、动作表、角色设计表、故事板工作流；
* 视觉品牌解构、图片逆向、风格分析、Style DNA 相关流程；
* 社交媒体图文、TikTok slideshow、PPT 视觉设计、信息图、海报生成；
* FFmpeg、视频自动化等与 AI 视频生产后处理相关流程。

### 暂不纳入

暂不纳入以下内容：

* 纯 Agent 架构、记忆系统、软件工程、CLI 工具；
* 与图像/视频生成无直接关系的知识学习笔记；
* 纯网页设计灵感站点，除非能转化为视觉生成提示词；
* 图片归档、素材管理等非生成类工作流。

---

## 2. 核心提示词公式

### 2.1 通用图片生成公式

来源：

* `提示词/README.md`
* `提示词/2026-04-21-image-design-skill.md`
* `learned/2026-04-21-image-design-skill.md`

```text
[主体描述]
+ [构图位置]
+ [光线逻辑]
+ [相机视角]
+ [风格与质感]
```

扩展版：

```text
主体 = 谁 / 什么物体 / 关键特征
构图 = 位置 / 比例 / 留白 / 层级
光线 = 方向 × 光比 × 色温
视角 = 镜头高度 / 焦段 / 景深 / 透视
风格 = 媒介 / 材质 / 色彩 / 时代 / 品牌感
约束 = 不要什么 / 不出现什么 / 避免什么错误
```

### 2.2 通用视频生成公式

来源：

* `提示词/README.md`
* `提示词/seedance-prompt-skill-study.md`
* `learned/seedance-prompt-skill-study.md`

```text
(主体)
+ (动作)
+ (场景)
+ (镜头)
+ (风格)
+ (约束)
```

15 秒视频推荐结构：

```text
0-3s：建立场景 / 主体入场
4-8s：动作推进 / 关键变化
9-12s：情绪或视觉高潮
13-15s：收束 / 定格 / 反转 / 品牌露出
```

### 2.3 图生视频 I2V 公式

来源：

* `提示词/2026-04-27-GPT-Image2-Seedance-故事分镜动画工作流.md`
* `提示词/2026-04-28-GPTImage2-ClaudeOpus-HappyHorse-三步动画短片工作流.md`

```text
@参考图
+ 角色/主体保持一致
+ 本镜头发生什么动作
+ 镜头如何运动
+ 场景如何变化
+ 情绪与节奏
+ 画面风格与质量
+ 负面约束
```

---

## 3. 图片生成提示词模板

### 3.1 知识图文 / 信息图模板

来源：

* `提示词/2026-04-27-GPT-Image2-图文笔记模板.md`
* `提示词/2026-04-27-GPT-Image2-数学可视化提示词集.md`
* `提示词/2026-04-27-数学可视化信息图提示词模板.md`
* `提示词/2026-04-27-GPT-Image2-进化史信息图提示词.md`
* `/Volumes/elements/repos/codex/prompts/knowledgefxg-image2-english-learning-infographic.md`
* `/Volumes/elements/repos/codex/prompts/geekcatx-scrapbook-subject-infographic.md`
* `/Volumes/elements/repos/codex/prompts/kris-kashtanova-self-infographic-anime.md`

```text
Create an educational infographic poster about {TOPIC}.

Use a clear visual hierarchy:
- large title at the top
- central visual metaphor or diagram
- 3 to 5 labeled explanation blocks
- arrows or flow lines showing relationships
- concise annotations, readable typography

Style:
- clean editorial design
- high information density but not cluttered
- hand-drawn / technical illustration / premium textbook aesthetic
- consistent color palette

Constraints:
- all labels must be legible
- avoid random decorative icons
- avoid meaningless pseudo-text
- preserve logical structure
```

适用场景：

* 数学概念；
* 科普海报；
* 进化史 / 发展史；
* 工程力学、声学、经济学可视化；
* 公众号知识图文配图。
* 英语学习、学科知识、人物自我介绍信息图。

### 3.2 Apple 风自然科普海报模板

来源：

* `提示词/2026-04-27-Apple风自然科普海报生成系统.md`

```text
Create a vertical Apple-style natural science poster about {SPECIES_OR_OBJECT}.

Visual direction:
- minimal white or soft neutral background
- one precise central subject image
- clean high-end product-style lighting
- generous negative space
- thin typography, calm editorial layout

Structure:
- top-left title and Latin / English subtitle
- central detailed subject visual
- bottom four-column information bar
- one short poetic summary sentence

Quality:
- premium museum display feeling
- scientific but elegant
- no cluttered background
- no cartoonish rendering
```

### 3.3 博物标本解剖风模板

来源：

* `提示词/2026-04-28-GPTImage2-博物标本解刨风格-模板与鸡蛋示例.md`
* `提示词/2026-04-28-GPTImage2-博物标本解刨风格-扩展库-牛油果洋葱面包.md`

```text
Create a natural history specimen plate of {OBJECT}.

Show the object as a clean anatomical decomposition:
- whole object view
- sliced section
- internal layers
- small separated components
- labeled parts arranged with museum precision

Style:
- botanical / zoological specimen illustration
- clean parchment or off-white background
- delicate ink lines
- subtle watercolor or realistic material texture
- scientific labels and measurement marks

Constraints:
- no messy layout
- no fantasy elements
- no excessive decoration
- keep all parts spatially ordered
```

### 3.4 字体海报 / 大字报 / 水字体模板

来源：

* `提示词/2026-04-27-GPTImage2-字体美学-文字图鉴-大字报系列.md`
* `提示词/2026-04-28-平面几何字体海报生成器-GPTImage2.md`
* `提示词/2026-04-28-Ultra-Realistic-Macro-Water-Typography.md`

```text
Create a typographic poster centered on the word "{WORD}".

Typography:
- the word is the main visual subject
- strong geometric composition
- high legibility
- carefully balanced negative space

Visual style:
- {GEOMETRIC / POSTER / MACRO WATER / EDITORIAL}
- controlled color palette
- premium print design feeling
- no random decorative clutter

If macro water typography:
- letters formed by suspended water droplets or transparent fluid
- ultra-realistic macro photography
- clean studio lighting
- shallow depth of field
```

### 3.5 时尚大片 / 产品广告摄影模板

来源：

* `提示词/2026-04-27-GPT-Image2-时尚卡通混搭大片.md`
* `提示词/2026-04-28-Low-Angle-Fashion-Campaign-Photography-GPTImage2.md`
* `提示词/2026-04-28-GPTImage2-智能修图涂鸦互动叠加.md`
* `/Volumes/elements/repos/codex/prompts/xiaoxiaodong-adult-east-asian-female-editorial-portrait.md`

```text
Create a high-fashion campaign image featuring {SUBJECT_OR_PRODUCT}.

Composition:
- low-angle or editorial studio perspective
- strong foreground product presence
- model / character / product clearly staged
- clean background or controlled set design

Lighting:
- premium studio lighting
- crisp highlights
- controlled shadows
- luxury commercial photography feeling

Style:
- fashion editorial
- bold but restrained color accents
- high-end advertising finish

Constraints:
- no distorted anatomy
- no messy background
- no unreadable text
- product must remain recognizable
```

### 3.6 主题驱动编辑人像模板

来源：

* `/Volumes/elements/repos/codex/prompts/xiaoxiaodong-adult-east-asian-female-editorial-portrait.md`

```text
Do not mechanically apply a fixed beauty template.

Start from this theme / inspiration:
{THEME_OR_INSPIRATION}

Extract:
- emotional core
- identity and temperament
- life state
- relationship tension
- sense of era

Translate those signals into:
- face and expression
- clothing
- hair condition
- posture
- scene details
- lighting direction
- color mood

Image:
- vertical 9:16
- single young adult East Asian female subject
- realistic editorial photography
- quiet, restrained, intimate, natural
- soft black mist filter, gentle bloom, low saturation
- posture must feel like a real story moment, not a staged influencer pose

Constraints:
- no repetitive internet beauty template
- no overexposure
- no empty generic studio
- attractiveness comes from emotion, distance, posture, fabric, light, and realism
```

### 3.7 世界观视觉系统模板

来源：

* `/Volumes/elements/repos/codex/prompts/aleenaamir-gpt-image2-worldbuilding-set.md`

```text
Create a complete visual worldbuilding set for {WORLD_CONCEPT}.

The set should include multiple images:
- architecture
- characters
- clothing
- vehicles or tools
- maps or environment layouts
- symbolic objects

Design requirements:
- cohesive design language
- consistent material system
- consistent color palette
- clear cultural logic
- cinematic realism
- ultra-detailed concept art quality

Purpose:
- game concept pack
- film concept exploration
- franchise visual system
- worldbuilding reference board
```

### 3.8 纸雕 / 微缩世界视觉公式

来源：

* `/Volumes/elements/repos/codex/prompts/0x00-krypt-layered-paper-pokemon-diorama.md`
* `/Volumes/elements/repos/codex/prompts/0x00-krypt-book-comes-alive-fountain-pen.md`

```text
Eye-level straight-on view into a hyper-vibrant 3D layered paper cut-out diorama of {WORLD_OR_SCENE}.

Visual formula:
- physical paper layers clearly visible
- hard cut edges
- thick paper cross-sections at every depth plane
- dense foreground, middle ground, and background layers
- strong handcrafted paper texture
- soft single-direction studio lighting
- deep drop shadows between layers
- high saturation signature colors
- maximalist composition with many recognizable scene elements

Constraints:
- no glow
- no soft edges
- no volumetric lighting
- no flat digital collage look
- preserve physical paper construction
```

### 3.9 小红书四宫格内容模板

来源：

* `/Volumes/elements/repos/codex/prompts/mrlarus-xiaohongshu-wellness-grid.md`

```text
Create a Xiaohongshu-style 3:4 vertical master image for {TOPIC}.

Layout:
- 2×2 grid
- four independent crop-safe panels
- clear margins and card boundaries
- each panel can be posted separately

Panel structure:
1. Cover: catchy Chinese title and subtitle
2. Self-check / resonance: 3-5 common symptoms, situations, or misconceptions
3. Methods: 3-5 gentle daily suggestions
4. Summary / checklist: one-sentence logic + saveable action list

Style:
- clean, warm, natural, lifestyle-oriented
- light information card + lifestyle poster + Xiaohongshu cover style
- soft natural light
- rounded cards, paper texture, notes, lifestyle props
- readable Chinese typography

Constraints:
- no medical diagnosis
- no exaggerated health claims
- no hard-sell supplement feel
- not too dense
```

---

## 4. 分镜图与动作表提示词

### 4.1 角色动作分镜表

来源：

* `提示词/2026-04-27-GPT-Image2-角色动作分镜表提示词.md`
* `提示词/2026-04-28-GPTImage2-舞蹈分镜表-Seedance动画工作流.md`
* `提示词/2026-04-28-GPTImage2-Seedance2-Movement-Sheet-Animation-Workflow.md`

```text
Create a 4×4 movement sheet for {CHARACTER}.

Each panel shows one continuous action pose in sequence.

Requirements:
- same character identity across all panels
- full body visible
- monochrome grayscale or limited palette
- clean white background
- motion arrows and direction indicators
- step number and short action label in each panel
- no extra characters
- no complex background

Purpose:
- the sheet will be used as reference for AI video animation
- emphasize motion clarity over decorative detail
```

工作流：

```text
GPT Image 2 生成 4×4 / 16 宫格 Movement Sheet
→ 将分镜图作为 Seedance / 视频模型参考图
→ 视频模型根据动作顺序生成连续动画
```

### 4.2 角色设计表 → 视频关键帧

来源：

* `提示词/2026-04-28-GPTImage2-角色设计表-Seedance视频工作流.md`
* `提示词/2026-04-28-Seedance2-15秒电影动画短片-飞屋环游记风格.md`

```text
Create a character design sheet for {CHARACTER}.

Include:
- front view
- side view
- back view
- facial expressions
- key props
- color palette
- material details
- action pose thumbnails

Style:
- animation production design sheet
- clean layout
- consistent proportions
- clear silhouette
- readable annotations

Purpose:
- this image will be used as character reference for video generation
```

### 4.3 专业动画故事板 Sheet

来源：

* `/Volumes/elements/repos/codex/prompts/studio-tora-images2-seedance-storyboard.md`

```text
Create a professional theatrical storyboard sheet for {STORY_TITLE}.

Canvas:
- 16:9
- clean production document layout
- 3-column grid of 9 scenes

Each scene panel includes:
- Scene number
- timecode
- scene title
- START FRAME and END FRAME
- arrow connecting the two frames
- annotation rows: CAMERA / DIALOGUE / SFX / ACTION

Bottom section:
- key character portraits
- tone and direction box
- music and SFX plan timeline
- technical specs

Style:
- {ANIME / CINEMATIC / GAME / LIVE_ACTION} production storyboard
- detailed key visuals inside each frame
- clean infographic layout
- consistent color palette and art direction

Workflow:
Generate storyboard image first → feed it as reference to Seedance or another video model.
```

---

## 5. 视频生成提示词模板

### 5.1 Seedance 15 秒电影短片

来源：

* `提示词/2026-04-28-Seedance2-15秒电影动画短片-飞屋环游记风格.md`
* `提示词/seedance-prompt-skill-study.md`
* `learned/seedance-prompt-skill-study.md`

```text
Create a 15-second cinematic animated short.

Subject:
{MAIN_CHARACTER_OR_OBJECT}

Style:
{ANIMATION_STYLE}, cinematic lighting, expressive motion, coherent character identity.

Shot list:
0.0-3.0s:
- Establishing shot.
- Show {LOCATION} and introduce {CHARACTER}.
- Camera: {CAMERA_MOVE}.

3.0-5.0s:
- Character begins {ACTION}.
- Camera moves closer.

5.0-8.5s:
- Main action escalates.
- Add visual tension or comedic contrast.

8.5-11.0s:
- Emotional / visual peak.
- Strong motion arc.

11.0-15.0s:
- Resolution, reaction, or poetic ending.
- Hold final cinematic frame.

Constraints:
- keep character consistent
- no random cuts
- no unreadable text
- no extra limbs or distorted faces
- avoid flickering identity
```

### 5.2 Seedance VFX Showcase

来源：

* `提示词/2026-04-28-Seedance2-召唤术VFX-Showcase-Video.md`

```text
Create a 15-second cinematic VFX showcase.

Reference:
@image1 is the character reference. Keep the same face, outfit, proportions, and identity.

Scene:
{CHARACTER} stands in {LOCATION}.

Action:
The character performs a summoning gesture.
Energy particles gather around the hands.
A glowing magic circle appears.
The summoned object or creature emerges in stages.

Camera:
- slow push-in
- dramatic low angle
- controlled orbit during the VFX reveal

VFX:
- volumetric light
- particle trails
- glowing runes
- smoke and energy distortion
- cinematic depth of field

Constraints:
- no identity drift
- no random extra characters
- no chaotic camera movement
- no text overlay
```

### 5.3 Claude Opus 看图写 I2V Prompt

来源：

* `提示词/2026-04-28-GPTImage2-ClaudeOpus-HappyHorse-三步动画短片工作流.md`

```text
Look at this keyframe image and write an image-to-video prompt.

Output format:

Scene:
- What is visible in the image?

Main action:
- What should move?

Camera:
- How should the camera move?

Motion details:
- What small secondary motions should happen?

Style:
- What visual style should be preserved?

Constraints:
- What must not change?
```

用途：

```text
GPT Image 2 生成故事板 / 关键帧
→ Claude Opus 分析每张图并写 I2V prompt
→ HappyHorse / Seedance / Pollo AI 生成视频
```

---

## 6. 镜头语言与场景预设

来源：

* `提示词/shot-motion-scene-presets-cheatsheet.md`
* `learned/shot-motion-scene-presets-cheatsheet.md`
* `learned/shot-motion-scene-presets-cheatsheet.abstract`

核心公式：

```text
单一运动 × 单一调色板 × 节拍标注
```

推荐约束：

```text
10 秒视频 = 2 到 3 个镜头组合
每个镜头只承担一个清晰动作
每个镜头只使用一个主要运镜
每段提示词明确时间、镜头、动作、场景、节奏
```

可复用镜头词：

```text
slow push-in
low-angle tracking shot
orbit camera
handheld documentary shot
top-down shot
dolly zoom
macro close-up
wide establishing shot
over-the-shoulder shot
locked-off static shot
```

---

## 7. 社媒 / 广告 / PPT 视觉生产模板

### 7.1 UGC 广告故事板

来源：

* `提示词/2026-04-28-Offer-Stack-Visualizer-UGC广告故事板模板.md`

```text
Create a UGC ad storyboard for {PRODUCT}.

Campaign details:
- Product:
- Audience:
- Main pain point:
- Offer:
- Platform:

Storyboard concepts:
1. Hook / pattern interrupt
2. Pain point demonstration
3. Product reveal
4. Benefit proof
5. Social proof or comparison
6. CTA frame

Art direction:
- native social media look
- vertical 9:16 layout
- realistic creator-style framing
- clear product visibility
- readable overlay text
```

### 7.2 TikTok Slideshow 视觉工作流

来源：

* `learned/2026-04-21-tiktok-slideshow-automation-workflow.md`

```text
Analyze this viral TikTok slideshow and extract:
1. hook structure
2. slide count
3. visual style
4. text overlay rhythm
5. emotional arc
6. reusable template
```

Pinterest 搜索词生成：

```text
Based on this slideshow, suggest 10 Pinterest search queries matching the visual style and content theme.
Focus on aesthetic keywords, composition, niche-specific visuals.
```

### 7.3 PPT / 演示图片设计

来源：

* `learned/2026-04-22-PPT-Design-Prompt_品牌设计转演示图片格式.md`
* `learned/2026-04-27-PPT-Design-Prompt.md`
* `learned/2026-04-27-guizang-ppt-skill.md`

```text
Turn this concept into a high-end presentation visual.

Requirements:
- magazine-style layout
- strong title hierarchy
- one dominant visual metaphor
- concise supporting text blocks
- editorial spacing
- brand-consistent colors
- suitable for a single slide or article cover

Avoid:
- dense bullet slides
- generic gradient background
- clipart
- unreadable small text
```

---

## 8. 视觉品牌解构 / 图片逆向相关

来源：

* `提示词/2026-04-28-GPT55-视觉品牌解构工作流.md`
* `docs/visual-prompt-system.md`

可转化为视觉提示词系统的分析模板：

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

Prompt 重构公式：

```text
[Art Direction / Medium]
+ [Camera / View]
+ [Lighting / Atmosphere]
+ {SUBJECT SLOT}
+ [Material / Texture]
+ [Composition / Background]
+ [Quality Reinforcement]
+ [Negative Constraints]
```

---

## 9. 视频自动化与后处理

来源：

* `learned/2026-04-27-ffmpeg-cheatsheet.md`
* `learned/2026-05-10-PHP-Webman-FFmpeg-HLS视频流.md`
* `提示词/2026-04-13-minimax-mmx-cli-video-workflow.md`
* `learned/2026-04-13-minimax-mmx-cli-video-workflow.md`
* `/Volumes/elements/repos/codex/notes/rosebud-ai-game-pipeline.md`
* `/Volumes/elements/repos/codex/notes/binghe-codex-image2-ui-workflow.md`
* `/Volumes/elements/repos/codex/notes/tz-codex-gpt-image-2-resolution-limit.md`

可沉淀方向：

```text
AI 生成视频
→ FFmpeg 裁切 / 拼接 / 转码 / 加字幕 / 抽帧
→ HLS 或社媒格式输出
→ 定时发布 / 分发
```

视频生成项目常见字段：

```text
source_images:
source_video:
prompt:
duration:
aspect_ratio:
fps:
style:
negative_prompt:
postprocess:
output_format:
```

### 9.1 AI 游戏视觉原型管线

来源：

* `/Volumes/elements/repos/codex/notes/rosebud-ai-game-pipeline.md`
* `/Volumes/elements/repos/codex/prompts/chongu-topdown-battle-royale-mockup.md`

```text
Idea
→ GPT Image 2 生成角色概念 / 场景概念
→ Grok Imagine 或其他视频模型生成 motion mockup
→ fal / MeshyAI 生成 3D 资产
→ Rosebud 或游戏工具继续做 playable prototype
```

价值：

* 将静态图、视频预览、3D 资产和游戏原型拆成独立阶段；
* 适合快速验证游戏概念，而不是直接进入生产级资产流程。

### 9.2 Codex ↔ Image2 UI 视觉迭代

来源：

* `/Volumes/elements/repos/codex/notes/binghe-codex-image2-ui-workflow.md`

```text
Codex 生成简单产品网页
→ 对网页截图使用 GPT Image 2 生成更好看的 UI
→ 从生成图反推 UI spec
→ 将截图和 spec 交回 Codex 重建前端
```

价值：

* 把截图作为代码与视觉之间的中间表示；
* 适合快速个人原型；
* 可并入视觉逆向提示词系统的 Tuning Loop。

### 9.3 GPT Image 2 输出分辨率观察

来源：

* `/Volumes/elements/repos/codex/notes/tz-codex-gpt-image-2-resolution-limit.md`

观察：

```text
不同画幅可能共享接近固定的总像素预算。
1:1、16:9、3:1、1:3 输出都约为 1.57M 像素。
```

用途：

* 规划信息图和海报时不要假设可直接得到 2K / 4K 级别细节；
* 对文字密度、网格数量和小字大小保持克制；
* 复杂海报可先生成结构，再局部重绘或后期排版。

---

## 10. 源文件清单

### 10.1 `提示词/` 中纳入的文件

| 类型 | 文件 |
| --- | --- |
| 视频生成 / Seedance | `提示词/seedance-prompt-skill-study.md` |
| 视频镜头语言 | `提示词/shot-motion-scene-presets-cheatsheet.md` |
| MiniMax 视频工作流 | `提示词/2026-04-13-minimax-mmx-cli-video-workflow.md` |
| 图片生成基础 | `提示词/2026-04-21-image-design-skill.md` |
| 信息图 / 知识图文 | `提示词/2026-04-27-GPT-Image2-图文笔记模板.md` |
| 信息图 / 数学可视化 | `提示词/2026-04-27-GPT-Image2-数学可视化提示词集.md` |
| 信息图 / 进化史 | `提示词/2026-04-27-GPT-Image2-进化史信息图提示词.md` |
| 信息图 / 数学模板 | `提示词/2026-04-27-数学可视化信息图提示词模板.md` |
| 海报 / 自然科普 | `提示词/2026-04-27-Apple风自然科普海报生成系统.md` |
| 海报 / 城市地图 | `提示词/2026-04-27-立体浮雕城市地图海报生成系统.md` |
| 产品形态设计 | `提示词/2026-04-27-概念转化设计提示词-自然形态到产品.md` |
| 字体设计 | `提示词/2026-04-27-GPTImage2-字体美学-文字图鉴-大字报系列.md` |
| 字体海报 | `提示词/2026-04-28-平面几何字体海报生成器-GPTImage2.md` |
| 微距水字体 | `提示词/2026-04-28-Ultra-Realistic-Macro-Water-Typography.md` |
| 博物标本 | `提示词/2026-04-28-GPTImage2-博物标本解刨风格-模板与鸡蛋示例.md` |
| 博物标本扩展 | `提示词/2026-04-28-GPTImage2-博物标本解刨风格-扩展库-牛油果洋葱面包.md` |
| 时尚大片 | `提示词/2026-04-27-GPT-Image2-时尚卡通混搭大片.md` |
| 低视角产品摄影 | `提示词/2026-04-28-Low-Angle-Fashion-Campaign-Photography-GPTImage2.md` |
| 修图 / 涂鸦叠加 | `提示词/2026-04-28-GPTImage2-智能修图涂鸦互动叠加.md` |
| 表情包贴纸 | `提示词/2026-04-27-GPT-Image2-真人表情包贴纸套装.md` |
| Image Board | `提示词/2026-04-27-GPTImage2-ImageBoard模板.md` |
| 角色动作表 | `提示词/2026-04-27-GPT-Image2-角色动作分镜表提示词.md` |
| 故事分镜动画 | `提示词/2026-04-27-GPT-Image2-Seedance-故事分镜动画工作流.md` |
| 可颂制作流程动画 | `提示词/2026-04-27-GPTImage2-Seedance2-可颂制作流程工作流.md` |
| 舞蹈分镜动画 | `提示词/2026-04-28-GPTImage2-舞蹈分镜表-Seedance动画工作流.md` |
| Movement Sheet | `提示词/2026-04-28-GPTImage2-Seedance2-Movement-Sheet-Animation-Workflow.md` |
| 角色设计表视频 | `提示词/2026-04-28-GPTImage2-角色设计表-Seedance视频工作流.md` |
| 15 秒动画短片 | `提示词/2026-04-28-Seedance2-15秒电影动画短片-飞屋环游记风格.md` |
| VFX 视频 | `提示词/2026-04-28-Seedance2-召唤术VFX-Showcase-Video.md` |
| HappyHorse 图生视频 | `提示词/2026-04-28-GPTImage2-ClaudeOpus-HappyHorse-三步动画短片工作流.md` |
| Pollo AI 移动端动画 | `提示词/2026-04-28-Movement-Sheet-Pollo-AI-Mobile-Workflow.md` |
| 3D 动画分镜 | `提示词/2026-04-28-Stylized-3D-Animation-Chef-Customer-Storyboard.md` |
| UGC 广告故事板 | `提示词/2026-04-28-Offer-Stack-Visualizer-UGC广告故事板模板.md` |
| 视觉品牌解构 | `提示词/2026-04-28-GPT55-视觉品牌解构工作流.md` |
| 商业化视觉服务 | `提示词/2026-04-27-GPT-Image2-15种可卖视觉服务.md` |
| 生图需求案例 | `提示词/2026-04-28-GPTImage2-自动化生图套利-6个真实需求案例.md` |

### 10.2 `learned/` 中纳入的文件

| 类型 | 文件 |
| --- | --- |
| Seedance 学习笔记 | `learned/seedance-prompt-skill-study.md` |
| Seedance 摘要 | `learned/seedance-prompt-skill-study.abstract` |
| 镜头运动预设 | `learned/shot-motion-scene-presets-cheatsheet.md` |
| 镜头运动摘要 | `learned/shot-motion-scene-presets-cheatsheet.abstract` |
| MiniMax 视频工作流 | `learned/2026-04-13-minimax-mmx-cli-video-workflow.md` |
| 图片设计 Skill | `learned/2026-04-21-image-design-skill.md` |
| PPT 视觉 Prompt | `learned/2026-04-22-PPT-Design-Prompt_品牌设计转演示图片格式.md` |
| PPT 视觉 Prompt 研究 | `learned/2026-04-27-PPT-Design-Prompt.md` |
| 交互图解规格 | `learned/2026-04-27-illustrated-explainer-spec.md` |
| TikTok Slideshow | `learned/2026-04-21-tiktok-slideshow-automation-workflow.md` |
| 社媒爆款图文 | `learned/2026-04-22-Agent工作流_社交媒体爆款图文制作.md` |
| FFmpeg 视频自动化 | `learned/2026-04-27-ffmpeg-cheatsheet.md` |
| Magazine Web PPT | `learned/2026-04-27-guizang-ppt-skill.md` |
| 纸张生成器 | `learned/2026-04-27-PaperMe纸张生成器分析.md` |

### 10.3 父仓库 `prompts/` 中纳入的文件

| 类型 | 文件 |
| --- | --- |
| 英语学习信息图 | `/Volumes/elements/repos/codex/prompts/knowledgefxg-image2-english-learning-infographic.md` |
| 动漫人物信息图 | `/Volumes/elements/repos/codex/prompts/kris-kashtanova-self-infographic-anime.md` |
| 手账学科知识图解 | `/Volumes/elements/repos/codex/prompts/geekcatx-scrapbook-subject-infographic.md` |
| 编辑感人像 | `/Volumes/elements/repos/codex/prompts/xiaoxiaodong-adult-east-asian-female-editorial-portrait.md` |
| 小红书养生四宫格 | `/Volumes/elements/repos/codex/prompts/mrlarus-xiaohongshu-wellness-grid.md` |
| 复古电影票根海报 | `/Volumes/elements/repos/codex/prompts/geekcatx-vintage-black-white-movie-ticket.md` |
| 世界观视觉系统 | `/Volumes/elements/repos/codex/prompts/aleenaamir-gpt-image2-worldbuilding-set.md` |
| Images2 → Seedance 故事板 | `/Volumes/elements/repos/codex/prompts/studio-tora-images2-seedance-storyboard.md` |
| 俯视角游戏概念图 | `/Volumes/elements/repos/codex/prompts/chongu-topdown-battle-royale-mockup.md` |
| 鹿鼎记角色海报系列 | `/Volumes/elements/repos/codex/prompts/caiziboshi-ludingji-poster-series.md` |
| Midjourney 风格预设 | `/Volumes/elements/repos/codex/prompts/oscarai-midjourney-v7-sref-1808075808.md` |
| 3D 纸雕宝可梦世界 | `/Volumes/elements/repos/codex/prompts/0x00-krypt-layered-paper-pokemon-diorama.md` |
| 巨型钢笔 + 纸上微缩世界 | `/Volumes/elements/repos/codex/prompts/0x00-krypt-book-comes-alive-fountain-pen.md` |

### 10.4 父仓库 `notes/` 中纳入的文件

| 类型 | 文件 |
| --- | --- |
| GPT Image 2 竞技场表现 | `/Volumes/elements/repos/codex/notes/arena-ai-gpt-image-2-image-arena-result.md` |
| 游戏视觉原型管线 | `/Volumes/elements/repos/codex/notes/rosebud-ai-game-pipeline.md` |
| Codex 内置 GPT Image 2 分辨率观察 | `/Volumes/elements/repos/codex/notes/tz-codex-gpt-image-2-resolution-limit.md` |
| Codex ↔ Image2 UI 工作流 | `/Volumes/elements/repos/codex/notes/binghe-codex-image2-ui-workflow.md` |
| ChatGPT Image Reasoning Pop-Up Book 测试 | `/Volumes/elements/repos/codex/notes/goldengrape-chatgpt-image-reasoning-pop-up-book.md` |
| 小红书封面 Skill 线索 | `/Volumes/elements/repos/codex/notes/ahang-xiaohongshu-cover-skill-github.md` |

### 10.5 本仓库参考副本

上述纳入分析的文件已复制到当前仓库 `prompts/` 目录，按来源保留子目录：

| 本地目录 | 来源 |
| --- | --- |
| `prompts/source-tishi/` | 当前仓库 `提示词/` |
| `prompts/source-learned/` | 当前仓库 `learned/` |
| `prompts/source-parent-prompts/` | 父仓库 `/Volumes/elements/repos/codex/prompts/` |
| `prompts/source-parent-notes/` | 父仓库 `/Volumes/elements/repos/codex/notes/` |

这些文件作为视觉提示词系统 v1.0 的可追溯参考素材，不直接替代 `docs/visual-generation-prompt-extraction.md` 中已经抽取、归纳后的模板层。

---

## 11. 后续整理方向

建议下一步将本文档继续拆成三类资产：

1. **视觉 Prompt 模板库**
   - 图片生成；
   - 信息图；
   - 海报；
   - 字体；
   - 产品摄影；
   - 博物标本；
   - 表情包 / 贴纸。

2. **视频 Prompt 模板库**
   - Seedance；
   - I2V；
   - Movement Sheet；
   - 角色设计表；
   - VFX；
   - 广告故事板；
   - 镜头语言。

3. **视觉提示词 Skill**
   - 输入参考图或需求；
   - 输出 Style DNA Report；
   - 生成 Style Shell + Content Slots；
   - 生成图片 Prompt 或视频 Prompt；
   - 根据结果做 Tuning Loop；
   - 沉淀 Golden Template。
