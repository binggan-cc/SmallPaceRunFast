# 移动端武术动画工作流 — GPT Image 2 + Seedance 2.0 + Pollo AI

**主题**：动作分镜表 → AI动画（移动端实现）
**工具**：GPT Image 2 + Seedance 2.0 + Pollo AI（手机App）
**时间**：2026-04-28

---

## 工作流

```
GPT Image 2（生成动作分镜表）
    ↓ img1
Seedance 2.0（分镜转视频）
    ↓ img2
Pollo AI（移动端App处理） + 音乐 aud1
    ↓
最终武术动画视频
```

---

## 第一步：GPT Image 2 生成 Movement Sheet

（与前一条笔记相同模板，详见）

```
Monochrome grayscale illustration, 3D-rendered character,
clean instructional reference sheet, white background,
comic-style cell grid layout, technical diagram aesthetic.

[LAYOUT]
4×4 grid layout (16 panels total), thin black border lines,
cells numbered 1–16, consistent panel sizes.

[CHARACTER]
image1 (same character appears in all panels)

[PANEL STRUCTURE – per cell]
Top-left: bold number badge + English title text
Center: full-body character pose
Bottom-left: English description (3–4 lines)
Overlay: directional arrows showing motion flow

[ARROWS / MOTION INDICATORS]
Curved arrows, straight arrows, circular rotation indicators.

[RENDERING STYLE]
Highly detailed 3D sculpted, soft studio lighting,
subtle shadows, grayscale, clean linework, game concept art.

[NEGATIVE]
No background scenery, no color tones,
no additional characters, no complex background.
```

---

## 第二步：Seedance 2.0 转视频

```
Create img2 that follows the exact sequence and movements
from steps 1–16 shown in img1. The music should be aud1.

There should be no dialogue, text, or narration.
```

**关键点**：Seedance的prompt极度简洁——不需要描述动作细节，只需要说"按img1的1–16步序列执行"。

---

## 第三步：Pollo AI（移动端）

- 在手机App内完成最终处理
- 接入音乐（aud1）
- 输出最终视频

---

## 核心洞察

```
GPT Image 2   → 出分镜（静态结构）
Seedance 2.0  → 分镜动画化（序列动作）
Pollo AI      → 移动端处理 + 音乐合成
↓
全链路移动端可跑通
```

---

## 标签

GPT-Image-2 / Seedance-2.0 / Pollo-AI / 武术动画 / 动作分镜 / 移动端AI / img2video / 4×16分镜表 / AI动画工作流
