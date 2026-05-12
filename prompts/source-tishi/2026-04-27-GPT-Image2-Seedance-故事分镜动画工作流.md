# GPT Image 2 + Seedance 2 分镜→动画工作流

- **主题：** 故事分镜生成 / 静态→动态工作流 / GPT Image 2 + Seedance 2
- **来源：** 用户实战分享
- **时间：** 2026-04-27

---

## 工作流总览

```
Step 1：GPT Image 2 生成彩色故事分镜
         ↓
Step 2：Seedance 2 接收分镜作为参考图（@storyboard）
         ↓
Step 3：Seedance 输出多镜头动画短片
```

---

## Step 1：GPT Image 2 生成故事分镜

### 提示词

```
Storyboard — colored.
The troll is walking alone in the mountains, through snow and wind.
He gets back home to his cave, all exhausted.
The troll spots a tiny flower in a beam of light on a ridge outside the cave.
Add a shot where focus is on the flower, then focus shifts to the troll and he says "what is this?" in a deep troll voice.
He goes in really close and sniffs. He smiles and picks up the little flower, including the dirt around it.
Ensure shots are cinematic and have great composition. We don't need the troll in every shot.
Include text and instructions.
```

### 输出要求
- **彩色分镜**（非灰度）
- 包含**文字说明和分镜指示**
- 每个镜头独立，有**电影感的构图**
- 不需要每个镜头都出现角色

---

## Step 2：Seedance 2 动画化

### 提示词

```
Multi-shot scene. Low-pace cinematic animation. High quality. Detailed. Photorealistic. Grain. 35mm film.

The troll is walking alone in the mountains, through snow and wind.
He gets back home to his cave, all exhausted.
The troll spots a tiny flower in a beam of light on a ridge outside the cave.
Add a shot where focus is on the flower, then focus shifts to the troll and he says "what is this?" in a deep troll voice.
He goes in really close and sniffs. He smiles and picks up the little flower, including the dirt around it.

No music. No text.
Storyboard: @[storyboard]
```

### 关键参数
- `@[storyboard]` = GPT Image 2 生成的分镜作为参考图
- 多镜头场景（Multi-shot scene）
- 低节奏电影感动画（Low-pace cinematic）
- 35mm 胶片质感（Grain + Film look）
- 无音乐、无文字

---

## 核心技巧

| 技巧 | 说明 |
|------|------|
| **分镜先行** | 用 Image 2 标准化镜头结构，Seedance 照着动起来 |
| **@引用语法** | `@storyboard` 把分镜注入 Seedance 作为参考，保持一致性 |
| **无文字叠加** | 动画里不要 text/music，分镜里的文字指示只给 AI 看 |
| **低节奏** | 奇幻叙事类内容用 Low-pace，不用快节奏动作片参数 |
| **胶片颗粒感** | 35mm film + Grain = 电影质感，抵消 AI 生成的光滑感 |

---

## 适用场景

#故事分镜 #分镜到动画 #Seedance #GPTImage2 #奇幻短片 #电影感工作流
