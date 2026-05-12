# GPT Image 2 + Seedance 2.0 动作分镜表动画工作流

**主题**：动作分镜表 → 视频动画
**模型**：GPT Image 2（生成动作分镜）+ Seedance 2.0（分镜转视频动画）
**时间**：2026-04-28

---

## 第一步：生成 Movement Sheet（GPT Image 2）

### Prompt 模板

```
Monochromatic grayscale illustration, 3D-rendered character, clean instructional reference sheet.
White background, comic-style cell grid layout, technical diagram aesthetic.

[LAYOUT]
4×4 grid layout (16 panels total).
Each panel separated by thin black border lines.
Panels are evenly sized and consistently aligned.
Each cell is clearly numbered from 1 to 16.

[CHARACTER]
(Insert character description)
Example: Young female dancer with an athletic build, ponytail hairstyle, wearing a crop top, baggy pants, and sneakers.
The same character must appear consistently in all panels.

[PANEL STRUCTURE – per cell]
Top-left: bold number badge + Korean title text
Center: full-body character pose illustration
Bottom-left: Korean description text (3–4 lines)
Overlay: directional arrows indicating movement flow

[ARROWS / MOTION INDICATORS]
Curved arrows, straight arrows, and circular rotation indicators.
Arrows should be placed around the character to clearly show movement direction and flow.

[RENDERING STYLE]
Highly detailed 3D sculpted style.
Soft studio lighting with subtle shadows.
No color — grayscale only.
Clean linework, polished finish, game concept art quality.

[NEGATIVE PROMPT]
No background scenery.
No color tones.
No additional characters.
No cluttered or complex backgrounds.
```

---

## 布局结构

```
┌──────┬──────┬──────┬──────┐
│  1   │  2   │  3   │  4   │
│ 动作1 │ 动作2 │ 动作3 │ 动作4 │
├──────┼──────┼──────┼──────┤
│  5   │  6   │  7   │  8   │
│ 动作5 │ 动作6 │ 动作7 │ 动作8 │
├──────┼──────┼──────┼──────┤
│  9   │ 10   │ 11   │ 12   │
│ 动作9 │ 动作10│ 动作11│ 动作12│
├──────┼──────┼──────┼──────┤
│ 13   │ 14   │ 15   │ 16   │
│ 动作13│ 动作14│ 动作15│ 动作16│
└──────┴──────┴──────┴──────┘
```

---

## 第二步：分镜表 → 视频动画（Seedance 2.0）

用第一步生成的动作分镜表作为参考图，输入 Seedance 2.0，指定舞者角色动画。

### 关键技巧
- Movement Sheet 作为参考图锚定动作序列
- 保持角色一致性（同一角色出现在所有分镜格）
- 动作箭头标注清晰 → 模型理解运动方向和流程
- 单色（灰度）→ 排除颜色干扰，聚焦动作本身

---

## 核心工作流

```
GPT Image 2（生成4×4分镜表）
    ↓ 参考图
Seedance 2.0（读懂分镜，输出连贯动画）
```

---

## 适用场景

- 舞蹈动作设计参考
- 动画师/编舞教学素材
- 游戏角色动作序列
- 短视频舞蹈内容创作

---

## 标签

GPT-Image-2 / Seedance-2.0 / 动作分镜 / 舞蹈参考 / 动画工作流 / 单色渲染 / 4×4网格 / 动作序列 / 分镜表
