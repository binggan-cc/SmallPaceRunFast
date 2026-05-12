# GPT Image 2 + Seedance 2.0 舞蹈分镜动画工作流

- **主题：** AI 舞蹈分镜生成 · 动作表 → 图片 → 动画
- **来源：** 用户分享/GitHub
- **时间：** 2026-04-28

---

## 工作流概述

```
舞蹈动作分镜表（Movement Sheet）
    ↓ 作为参考图
GPT Image 2.0 → 生成16宫格分镜图（连续舞蹈动作）
    ↓
Seedance 2.0 → 将静态分镜动画化
```

---

## GPT Image 2.0 完整提示词

```
Dance Sequence Instruction Sheet

[VISUAL STYLE]
A composition featuring a highly detailed 3D-rendered female dancer. Designed like a professional choreography guide with a technical, diagram-inspired layout. Clean white background, soft studio lighting, and strong contrast to highlight body movement and posture.

[GRID LAYOUT]
Structured 4×4 panel grid (16 frames total), evenly spaced with thin black divider lines. Each panel is identical in size and clearly numbered from 1 to 16 to show a continuous dance progression.

[CHARACTER]
Use image1 as the base character. The same female dancer appears consistently across all panels with accurate likeness and proportions.

[WARDROBE]
The dancer wears a stylish, performance-ready outfit: a well-fitted top paired with a short, flowy skirt. The look should feel modern and visually appealing while still practical for dance movement. Fabric should subtly respond to motion (slight flow and folds), even in grayscale.

[PANEL STRUCTURE – EACH FRAME]
Top-left: Step number + short dance move title (e.g., "Step 5 – Spin Transition")
Center: Full-body pose capturing a precise moment in the choreography
Bottom-left: 3–4 lines of concise instruction describing the move
Overlay: Motion arrows and directional guides illustrating how the dancer transitions

[MOTION INDICATORS]
Incorporate curved arrows for fluid motion, straight arrows for directional steps, and circular indicators for spins or turns. Emphasize rhythm, weight shifts, and body isolation.

[RENDER QUALITY]
High-detail sculpted 3D style with smooth grayscale shading, subtle shadows, and clean linework. Maintain a polished, concept-art level finish with clarity in every pose.

[RESTRICTIONS]
No color, no background scenery, no extra characters, no visual clutter, only the dancer and instructional elements.
```

---

## 核心设计要点

| 要素 | 说明 |
|------|------|
| **网格结构** | 4×4 = 16宫格，每格独立编号，展示连续动作 |
| **分镜内容** | 左上：步数+动作名；中央：全身造型；左下：动作描述；覆盖层：运动箭头 |
| **运动指示** | 曲线箭头=流畅动作；直线箭头=方向步伐；圆形=旋转 |
| **人物一致性** | 以 image1 为基础角色，保持横跨16格的人物相似度 |
| **服装** | 合身上衣+短裙，兼具现代感与舞蹈功能性 |
| **色调** | 纯灰度，无彩色，干净白底 |

---

## 适用场景

- 舞蹈教学分解动作图
-  choreographer 参考分镜
- AI 动画素材生成（接 Seedance 2.0 动起来）
- 体育/健身动作说明书
- 武术/太极套路分解图

---

## 相关提示词

- `2026-04-27-GPT-Image2-角色动作分镜表提示词.md`（角色动作分解模板）
- `2026-04-27-GPTImage2-Seedance2-可颂制作流程工作流.md`（图片→视频工作流）

---

标签：#GPTImage2 #Seedance2 #舞蹈分镜 #动作表 #AI动画 #工作流
