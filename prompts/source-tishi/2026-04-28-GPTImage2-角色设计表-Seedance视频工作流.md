# GPT Image 2 + Seedance 2.0 角色设计表工作流

- **主题：** AI 角色分镜 · 角色设计表作为视频关键帧参考
- **来源：** X/Twitter 分享
- **时间：** 2026-04-28

---

## 核心方法论

```
Step 1：用 Midjourney/GPT Image 2 生成角色设计表（Character Design Sheet）
Step 2：用角色设计表作为 Seedance 2.0 的参考图（Reference Image）
Step 3：Seedance 2.0 基于角色表生成动态场景视频
```

**为什么用角色设计表？**
- 提供角色在白底上的正面/侧面/背面多视角
- 中性背景 = 完美的 AI 视频生成参考
- 保持横跨多个场景的人物一致性

---

## Step 1：创建角色设计表

### GPT Image 2 提示词

```
Create a character design style sheet for [describe your character]:
front view, side view, back view on white background.
Make the aspect ratio 4:3
```

### 示例

```
Create a character design style sheet for a young circus performer girl
with wild curly hair, wearing a vintage circus costume with star motifs,
barefoot, with a mischievous smile:
front view, side view, back view on white background.
Make the aspect ratio 4:3
```

---

## Step 2：Seedance 2.0 视频生成

### 提示词公式

```
Image 1 meets Image 2 in [场景描述].
[对话/动作情节].
Then [动作延续].
Multiple cuts. Dynamic angles.
```

### 完整示例

```
Image 1 meets Image 2 in a Circus.
He asked her why she is wearing no shoes.
She answers she doesn't need them, she can fly.
Then she levitates.
Multiple cuts. Dynamic angles.
```

其中：
- **Image 1** = 角色设计表（白底多视角）
- **Image 2** = 场景参考图（可选）
- **情节描述** = 用自然语言编排场景和动作

---

## 物品同理：资产表（Asset Sheet）

```
Create an asset sheet for [describe object]:
multiple angles, front/side/top view on white background.
Make the aspect ratio 4:3
```

**适用场景：**
- 道具（魔法手杖、神秘盒子、古董钟）
- 服装配饰（帽子、披风、徽章）
- 建筑元素（神秘门、飞船、武器）
- 任何需要在多个场景中保持一致性的物体

---

## 工作流示意图

```
[GPT Image 2]
角色设计表（正面/侧面/背面，白底）
        ↓ 参考图
[Seedance 2.0]
Image 1（角色表）+ Image 2（场景描述/场景图）
        ↓
动态视频：角色在场景中演出情节
Multiple cuts. Dynamic angles.
```

---

## 避坑提示

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 角色特征乱飘 | 直接用 Midjourney 场景图做参考 | 必须先出角色设计表（白底多视角） |
| 物体角度不一致 | 每个场景单独生成物体 | 先出资产表，统一参考 |
| 场景有第一张图的残留元素 | Seedance 记住了参考图的细节 | 用白底角色表而非场景图做 Image 1 |

---

## 相关提示词

- `2026-04-28-GPTImage2-舞蹈分镜表-Seedance动画工作流.md`（分镜表→动画）
- `2026-04-27-GPTImage2-Codex-浏览器游戏工作流.md`（图片→游戏工作流）

---

标签：#GPTImage2 #Seedance2 #角色设计表 #角色一致性 #AI视频 #工作流
