# GPT-Image-2 + Claude Opus + HappyHorse-1.0 三步动画短片工作流

- **主题：** AI视频 · 图片生视频 · i2v一致性 · 国产模型 · 工作流
- **来源：** X/Twitter / APIMart
- **时间：** 2026-04-28

---

## 工作流总览

```
Step 1              Step 2                    Step 3
GPT-Image-2    →    Claude Opus         →    HappyHorse-1.0
3×3故事板              看图写i2v prompt           图+prompt→视频
9张连贯关键帧    →    相机运动/动作/节奏    →    15秒一镜
衣服/光线/镜头一致                              人物不漂/衣服不变色
```

**总成本：大幅降低**
**一致性：肉眼可见的好**

---

## Step 1：GPT-Image-2 出故事板

### 提示词公式

```
3×3 storyboard, [风格描述], [主体描述],
9 frames with coherent key characters,
consistent clothing, lighting, camera angles,
[具体场景/情节描述]
```

### 示例

```
Studio Ghibli 3×3 storyboard, 9 frames,
a small girl with red hat running through a forest,
consistent red dress, warm afternoon sunlight,
camera pans following her movement,
emotional story of finding a spirit creature
```

**关键帧数量：** 3×3 = 9张，覆盖整个15秒的情节

---

## Step 2：Claude Opus 看图写 i2v Prompt

### 指令

让 Claude Opus 观看每张关键帧图片，输出格式：

```
[Camera Movement] - 相机运动（推进/横移/环绕/固定）
[Character Action] - 角色具体动作（转头/伸手/奔跑/眨眼）
[Rhythm] - 节奏（快/慢/停顿/爆发）
[Pacing Note] - 每张图在15秒内的哪个时间点
```

### 示例输出

```
Frame 1 (0-2s):
- Camera: Static medium shot, slight push forward
- Action: Girl runs into frame from left, stops suddenly
- Rhythm: Fast entry, abrupt halt

Frame 2 (2-4s):
- Camera: Slow pan right following girl
- Action: Girl looks up at trees, curiosity
- Rhythm: Slow, wonder

...
```

### 为什么 Claude Opus 而不是 GPT-4o？

- Opus 对图像的细节理解更强
- 能精确捕捉角色的微小动作和衣物褶皱
- 输出的 prompt 更适合作为视频生成的控制信号

---

## Step 3：HappyHorse-1.0 图生视频

### 输入

- Image 1: 关键帧图片
- Prompt: Claude Opus 输出的 i2v prompt

### 输出特性

- **15秒一镜**：一个完整镜头，不分段
- **人物不漂**：锚点锁定，角色身份稳定
- **衣服不变色**：服装颜色一致性控制好
- **忠实执行相机运动**：push/pan/track 等指令能被遵循

### 平台选择：APIMart

APIMart 将 GPT-Image-2 和 HappyHorse-1.0 整合到同一 API，免去自己对接两家 API 的麻烦。

```
# APIMart 整合式调用示意
{
  "images": [GPT-Image-2 生成的故事板图片],
  "model": "happyhorse-1.0",
  "i2v_prompts": [Claude Opus 输出的描述]
}
```

---

## 三步各自的核心价值

| Step | 工具 | 核心价值 |
|------|------|---------|
| 1 | GPT-Image-2 | 故事板 = 视频的"剧本+关键帧"，保证美术风格和角色一致性 |
| 2 | Claude Opus | 看图写 prompt = 把视觉翻译成视频控制信号，比人写更精准 |
| 3 | HappyHorse-1.0 | 图生视频 = 真正执行，15秒一镜，人物不漂 |

---

## 为什么 HappyHorse-1.0 值得关注

| 优势 | 说明 |
|------|------|
| **锚点忠实** | 给它参考图后，会老老实实按图演，不自己发挥 |
| **颜色控制** | 衣服/皮肤/环境颜色不易漂移 |
| **性价比** | 比 Runway/Pika 等便宜一截 |
| **国产** | 中文语境下的内容审核更友好 |
| **API整合** | APIMart 打通 GPT-Image-2 + HappyHorse-1.0，一条 API 调用 |

---

## 适用场景

- 吉卜力/手绘风动画短片
- 竖版短剧（抖音/小红书/视频号）
- 快速原型验证（先出故事板看效果，再决定是否精修）
- 多集连续视频（同一角色跨集保持一致）

---

## 相关工作流

- `2026-04-28-GPTImage2-角色设计表-Seedance视频工作流.md`（角色设计表→视频）
- `2026-04-28-Seedance2-15秒电影动画短片-飞屋环游记风格.md`（Seedance分镜脚本）

---

标签：#HappyHorse #APIMart #GPTImage2 #ClaudeOpus #i2v #AI视频 #国产模型 #工作流 #吉卜力
