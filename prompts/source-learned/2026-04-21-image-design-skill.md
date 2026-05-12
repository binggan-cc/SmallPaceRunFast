---
title: 5种AI生图构图元素，一个skill全搞定
topic: AI生图 / 提示词工程 / 构图元素 / 摄影逻辑
source: 公众号文章
date: 2026-04-21
---

# 5种AI生图构图元素，一个skill全搞定

> 适用模型：GPT-image2 和 nanobanana 皆适用

这个 skill 结合了 **[主体描述] + [构图位置] + [光线逻辑] + [相机视角] + [风格与质感]** 这5种构图元素。你仅需用清晰的需求便可做出高质量的AI图片。

---

## Skill 元数据

- **Name:** image-design
- **Description:** 高级质感图片设计 — 基于摄影逻辑的 AI 图片提示词生成技能。根据用户需求，运用主体描述、构图位置、光线逻辑、相机视角、风格与质感五大模块，生成专业级 AI 绘图提示词。

---

## 核心公式

```
[主体描述] + [构图位置] + [光线逻辑] + [相机视角] + [风格与质感]
```

每一张高质量 AI 图片的提示词都应覆盖这五个维度。

---

## 一、主体描述 + 构图位置

### 模板

```
[主体], positioned at [left/right/top/bottom] one-third of the frame,
[leading lines / light direction] guiding toward the subject,
[balance element description],
[lighting style],
[environment],
--ar 3:4
```

### 位置提示词

| 场景需求 | 提示词 |
|---------|--------|
| 主体偏左 | subject positioned at left one-third of the frame |
| 主体偏右 | subject at right one-third of the frame |
| 主体偏上 | subject placed at top one-third of the frame |
| 主体偏下 | subject positioned near bottom third |

### 平衡元素写法

| 用法 | 提示词 | 效果 |
|------|--------|------|
| 光平衡 | balanced composition through contrast between light and shadow | 明暗平衡 |
| 物体平衡 | counterbalanced by small object on the opposite side | 物体对重 |
| 色彩平衡 | asymmetrical balance through warm and cool tones | 色彩平衡 |
| 结构平衡 | balanced by architectural elements in background | 结构支撑画面 |

### 动线写法

| 类型 | 提示词 | 效果 |
|------|--------|------|
| 道路动线 | leading lines from foreground toward the subject | 从前景引导视线进入画面 |
| 光线动线 | diagonal light from top-right guiding viewer's eye | 用光的方向引导视线 |
| 透视动线 | path leading into depth, vanishing perspective | 增强空间深度 |
| 目光动线 | subject looking toward distant light | 人物目光带出画外空间 |

### 构图示例

> a man in a raincoat walking at night, positioned at left one-third, road reflections leading toward him, balanced by bright street lamp on opposite side, cinematic lighting, wet asphalt, --ar 3:4

---

## 二、光线逻辑

**三角公式：光线 = 方向 × 光比 × 色温**

### 1. 方向：光从哪来、打在哪、造成什么结果

**错误写法：** `cinematic lighting, detailed portrait`（太笼统，AI 无法理解空间）

**正确写法：** `soft sunlight entering from the right window, lighting the subject's face, casting long shadows on the table`

三要素：**方向**（from right）、**照射对象**（subject's face）、**阴影结果**（long shadows）

#### 主光与辅光

- **主光（Key Light）**：塑造形体
- **辅光（Fill Light）**：平衡阴影
- **背光（Back Light）**：分离轮廓

写法：
```
(subject), lit by warm key light from the right, soft fill light from the left, creating balanced shadows
```

### 2. 光比：控制画面的深度与视觉节奏

AI 模型倾向于"亮度平均"，害怕阴影。但**明暗对比是深度的来源**。

必须明确告诉 AI：哪里是亮面、哪里是暗面、亮暗之间是突变还是渐变。

```
a man standing under a streetlight, face illuminated brightly, background fading into shadow, strong contrast ratio, smooth light falloff
```

- **高光比**：观众视线被引导到亮处（主光聚焦）
- **低光比**：注意力平均分布

光比提示词：`strong contrast lighting, bright on face, dark background, deep shadow on left side`

### 3. 色温：光的情绪与时间逻辑

**错误写法：** `warm lighting`（整张图偏橙，像套滤镜）

**正确写法：** `warm sunlight hitting the character's face, cool blue ambient light in the background`（建立冷暖对比，分出层次和氛围）

#### 色温与时间段

| 时间 | 色温趋势 | 情绪表现 | 提示词参考 |
|------|---------|---------|-----------|
| 清晨 | 偏冷 | 宁静、朦胧 | misty morning light, cool tone |
| 正午 | 中性 | 清晰、真实 | neutral daylight |
| 傍晚 | 偏暖 | 柔和、浪漫 | golden hour sunlight |
| 夜晚 | 冷暖混合 | 孤独、都市感 | warm lamp light, cool ambient shadow |

- 暖光 → 有温度，适合叙事、人物、回忆
- 冷光 → 距离感，适合科技感、悬疑、未来感
- 冷暖对比 → 摄影中最经典的构图语言之一

### 光线综合示例

```
a woman standing near a window,
lit by warm sunlight entering from the right,
soft highlight on her face, background in cool shadow,
medium contrast lighting ratio, smooth gradient light transition
```

> "Light is not just what you see; it's how you feel what you see." — Roger Deakins

**核心原则：写的不只是"光的方向"，而是"情绪的方向"。冷光制造孤独；侧光增加戏剧性；逆光制造希望或终结感。描述光的逻辑，而不是光的形容词。**

---

## 三、相机视角

### 3 种角度

| 角度 | 画面感觉 | 什么时候用 | 提示词 |
|------|---------|-----------|--------|
| 平视 (Eye-level) | 自然、真实、纪实感强 | 想让画面可信度高、不"装" | `eye-level angle, camera positioned at human eye height, natural perspective, realistic proportions` |
| 低角度仰视 (Low Angle) | 主体巨大、有力量、史诗感 | 想让画面更高级、更商业化 | `low-angle shot, camera positioned near ground level, slight upward perspective, monumental feeling` |
| 高角度俯视 (High Angle) | 戏剧、视觉张力强 | 想做艺术风格，想展示更多信息 | `high-angle shot, overhead view, dramatic top-down perspective, strong visual tension` |

### 镜头焦段（Focal Length）

焦段决定"相机怎么看世界"——不同焦段就像换了不同的"眼睛"。

#### 广角 24-35mm — 空间感强、电影感十足
空间透视感强 / 景深更明显 / 前景更大、后景更远 / 更有"电影画幅感"
```
35mm lens photography, wide perspective, cinematic street style
```

#### 标准焦段 50mm — 最接近人眼、最真实
视角约 40°，最贴近人眼自然观察。不会改变脸型，不会拉伸或压扁空间。适合"写实风格"。
```
50mm lens, natural field of view, realistic proportions
```

#### 中长焦 85mm — 人像神器、背景虚化柔美
脸型更紧致、五官更立体，背景虚化柔和。最"讨好人"的焦段。
```
85mm portrait lens, shallow depth of field, soft bokeh background
```

#### 超广角 / 鱼眼 — 强烈视觉冲击
夸张透视，适合潮流、街头、运动、未来感题材。
```
fisheye lens, exaggerated perspective, bold visual impact
```

### 镜头提示词写法层级

**基础写法：** `35mm lens` / `50mm lens` / `85mm portrait lens` / `fisheye lens`

**专业写法：**
- `shot with a 35mm full-frame lens, subtle wide-angle distortion, realistic depth rendering`
- `50mm standard lens, natural field of view, lifelike spatial proportions`
- `85mm portrait lens, compressed background perspective, shallow depth separation`
- `ultra-wide 14mm lens, dramatic perspective exaggeration, strong foreground emphasis`

**高级写法：**
- `35mm focal length, full-frame wide perspective, foreground to background spatial continuity, cinematic depth rendering`
- `85mm medium telephoto lens, background compression, subject isolation, commercial portraiture style`

### 黄金组合公式

| 目标 | 组合 |
|------|------|
| 最自然真实的纪实照片 | eye-level angle + 35mm lens + f2.8 |
| 最高级的人像广告 | low-angle shot + 85mm lens + f1.8 |
| 最电影的环境人像 | eye-level shot + 35mm lens + f2.8 + cinematic depth |
| 最戏剧的艺术风格 | high-angle shot + 50mm lens + f5.6 |

### 常见错误与修正

| 错误 | 问题 | 修正 |
|------|------|------|
| 只写 `close-up / portrait` | AI 不知道用什么焦段，脸型奇怪 | `close-up portrait shot with 85mm lens, f1.8` |
| 想要电影感却写 `85mm` | 背景太虚，缺少故事空间 | `35mm cinematic lens` |
| 用广角拍特写 | 脸部变形 | `portrait shot with 50mm or 85mm lens` |

**焦段决定叙事：** 35mm 讲故事 / 50mm 呈现真实 / 85mm 打造美感 / 鱼眼制造冲击

---

## 四、风格与质感

### 质感：制造"不完美"的真实感

AI 默认追求锐利清晰。真正的高手敢于加入"灰尘"、"颗粒"、"磨损"。

#### 设定"反 AI"的拍摄设备与行为

- `iPhone-style`：手机的真实感，而非单反景深
- `Candid shot` / `Secretly photographed`：抓拍核心词，降低人物"配合度"，姿态更自然
- `Slightly shaky` / `Softly blurred due to motion`：动态模糊打破静止僵硬

**完美的照片是摆出来的，不完美的照片才是抓拍的生活。**

### 定义媒介：锁定画面的物理属性

#### 摄影胶卷（Film Stock）

| 胶卷 | 特点 | 适合场景 |
|------|------|---------|
| Kodak Portra 400 | 肤色还原极佳，色彩细腻温润 | 人像、生活感 |
| Fujifilm Pro 400H | 偏冷调，绿蓝色出色 | 日系、清冷、风景 |
| Kodak Gold 200 | 暖调，高饱和，复古感强 | 怀旧、街头、夏日氛围 |
| Cinestill 800T | 夜景神卷，高光光晕（Halation） | 夜景、电影感 |

写法：`shot on Kodak Portra 400, film grain, vintage aesthetic`

#### 数字化渲染风格

- `Unreal Engine 5` / `Octane Render`：极致光影计算，科幻、产品设计、超现实
- `Ray Tracing`：强调反射和折射的真实感

写法：`Cyberpunk street, neon lights reflection, Octane render, ray tracing, hyper-detailed, 8k resolution`

**注意：胶片感和 3D 渲染感冲突，不要混用。**

### 风格化借用

#### 导演 / 艺术家风格

- **Wes Anderson style**：素雅、对称、高饱和配色
- **Blade Runner 2049 aesthetic**：赛博朋克、高对比霓虹
- **Hiroshi Sugimoto**：极致极简主义和留白

**一次只借用一种核心美学，不要堆砌。**

#### 常用美学关键词

- `Minimalist`：干净、高级、留白
- `Brutalist`：水泥、混凝土、几何、冷峻
- `Ethereal`：柔光、梦幻、仙气
- `Gritty`：高对比、脏脏的、暗黑真实

---

## 五、综合示例

### 小白写法

```
A beautiful girl standing in street.
```

（结果：平平无奇，像个塑料手办）

### 大师写法

```
Ultra-realistic iPhone-style candid shot of a young Korean woman in her 20s
(idol-like facial ratio, natural beauty), captured from a distance as if
secretly photographed. She is walking through a quiet autumn city street
rain at night, expression neutral with no smile, eyes slightly down or
looking forward naturally (not toward the camera). Her outfit is casual
office-casual: light knit top + simple slacks + thin jacket or cardigan,
soft neutral colors. Hair long, slightly wavy, neatly styled with natural
movement. The photo is slightly shaky and softly blurred due to motion
true candid feel. Background: soft autumn morning light, muted golden tones,
blurred buildings and commuters passing far behind. Realistic depth, no
cinematic contrast. Shot from a distance with slight zoom, 45-degree angle
from the side. Film tone: soft Kodak Portra 400 grain, warm but subtle
color fade, realistic skin texture. No illustration style, no dramatic
lighting pure realism, everyday emotion, quiet atmosphere.
Aspect ratio 9:16 for Shorts. Candid motion, long-shot feeling
```

---

## 使用指南

当用户请求生成图片时，按以下流程工作：

1. **理解需求**：用户想要什么主体？什么情绪？什么用途？
2. **构建提示词**：按公式逐一填充五大模块
3. **选择生成工具**：使用 `generate-image-fast`（快速）或 `generate-image-hq`（高质量）
4. **审查与迭代**：检查生成结果，根据问题调整对应模块

### 关键注意事项

- 风格材质词放在提示词**后半段**，作为整体画面的"润色"
- 胶片风格和 3D 渲染风格**不要混用**
- 一次只借用**一种**核心美学风格
- 描述光的**逻辑**，而不是光的**形容词**
- 镜头和角度**必须一起写**，AI 才能完全理解拍摄方式
- **不完美才真实**：适当加入动态模糊、颗粒感、抓拍行为词

---

## 适用场景

#AI生图 #提示词工程 #构图元素 #摄影逻辑 #GPT-image2 #nanobanana #image-design #光线逻辑 #相机视角 #风格质感
