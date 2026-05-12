# GPT Image 2 · Image Board Prompt Template

> 简单提示词模板，用于创建多格视觉参考网格
> 适合通过一致图像探索角色、地点或记忆，拥有强烈的情感/怀旧氛围
> 修改参数即可一键生成完整的故事型图像板

---

## 模板结构

```
[SUBJECT]: your main character, place, object, city or concept
[GRID_LAYOUT]: panel layout
[THEME]: story theme, memory type or visual concept
[MOOD]: emotional tone
[STYLE]: visual style
```

---

## 完整Prompt

```
Create a [GRID_LAYOUT] borderless grid where each panel is an independent image of the [SUBJECT]. Maintain strong subject consistency across all panels, with consistent color and lighting. Depict [THEME] with a [MOOD] mood in [STYLE] style. No text. No gap.
```

---

## 参数说明

| 参数 | 作用 | 示例 |
|---|---|---|
| `[SUBJECT]` | 主轴，一致性根源 | a young woman / a seaside town / a lost robot |
| `[GRID_LAYOUT]` | 画幅布局 | 4×3 / 3×3 / 2×4 / 5×2 / 6×6 |
| `[THEME]` | 叙事内容 | childhood memories / summer vacation / rainy day memories |
| `[MOOD]` | 情绪定调 | warm nostalgic wistful / dreamy quiet melancholic |
| `[STYLE]` | 视觉调色板 | nostalgic cinematic realism / sentimental film photography |

---

## 示例参数

**[SUBJECT]:** a young woman / Osaka / a medieval knight / a seaside town / a lost robot

**[GRID_LAYOUT]:** 4×3 / 3×3 / 2×4 / 5×2 / 6×6

**[THEME]:** childhood memories / school life memories / neon night city life / summer vacation memories / rainy day memories / color-themed memories

**[MOOD]:** warm nostalgic wistful / emotional heartfelt tender / dreamy quiet melancholic / bittersweet intimate reflective

**[STYLE]:** nostalgic cinematic realism / sentimental film photography / wistful slice-of-life realism / dreamy nostalgic realism / soft retro film still / emotional memory-like photography / warm vintage realism / melancholic cinematic still

---

## 设计要点

- **无边框 + 无间隙**（borderless / No gap）→ 格子之间视觉独立，不被边框线打断情绪
- **强主体一致性**贯穿所有格子 → 无论几×几，人/物/场景在所有格子中保持同一身份
- **Style = 情绪载体** → "film still / memory-like photography" 这类描述不只是风格词，而是情绪触发器

---

## 与可颂提示词的区别

| 维度 | Image Board模板 | 可颂流程 |
|---|---|---|
| 目的 | 叙事连贯性（角色/故事） | 工序流程展示 |
| 连续性 | 叙事弧线 | 时间/制作顺序 |
| 风格 | 情绪记忆型 | 动漫风制作过程 |
