# Magazine Web PPT (guizang-ppt-skill) 研究报告

- **主题：** AI生成网页PPT / 电子杂志风演示工具
- **来源：** GitHub - op7418/guizang-ppt-skill
- **链接：** https://github.com/op7418/guizang-ppt-skill
- **时间：** 2026-04-27

---

## Step 1: 项目定位

- **一句话描述：** 将 Prompt 转化为"电子杂志 × 电子墨水"风格的单文件 HTML 横向翻页 PPT
- **核心问题：** 解决演讲/分享场景下 PPT 视觉品质不足的问题——不做成"商务幻灯片"，而是做成像 Monocle 杂志贴上代码的样子
- **目标用户：** 独立创始人 / 一人公司 / 线下分享 / AI 产品发布 / 个人风格演讲

---

## Step 2: 技术栈分析

- **语言/框架：** 纯 HTML + CSS + JS（单文件，无需构建）
- **WebGL：** 流体/等高线/色散背景（hero 页可见）
- **字体分工：**
  - 衬线（Noto Serif SC + Playfair Display）→ 大标题
  - 非衬线（Noto Sans SC + Inter）→ 正文
  - 等宽（IBM Plex Mono）→ 元数据
- **图标：** Lucide（不用 emoji）
- **动画：** Motion One（default-on，2026-04-26 集成）
- **目录结构：**
  ```
  assets/template.html    ← 完整可运行模板
  references/
    components.md         ← 组件手册
    layouts.md            ← 10种页面布局骨架
    themes.md             ← 5套主题色预设
    checklists.md         ← P0/P1/P2/P3质量检查清单
  ```

---

## Step 3: 活跃度评估

- **Stars:** ⭐ 3.4k | **Forks:** 347
- **最近活动：** 8 commits，昨天仍有更新（Motion One 动画集成）
- **社区状态：** 高活跃，Issue 和 PR 开放贡献

---

## Step 4: 竞品对比

| 维度 | guizang-ppt-skill | 普通PPT工具 | Web PPT工具 |
|---|---|---|---|
| 输出格式 | 单HTML文件 | .pptx | 通常需服务器 |
| 视觉风格 | 电子杂志风 | 商务模板 | 多为互联网风格 |
| 主题色 | 5套预设，禁止自定义 | 自由但易丑 | 自由 |
| 翻页 | 横向左右滑动 | 纵向/随机 | 不一定 |
| WebGL背景 | hero页有 | 无 | 可能有但无克制 |

**核心差异：** "保护美学比给自由更重要"——5套预设色不允许自定义，硬约束驱动质量

---

## Step 5: 价值判断

- **值得研究：** 是
- **启发点：**
  1. **预设约束 > 无限自由**——不让用户自定义hex值，颜色反而不会翻车
  2. **类名预检机制**——layouts.md用到的每个class，必须先确认template.html里有定义，否则样式全崩
  3. **主题节奏规划**——每页必须有`hero light/dark`或`light/dark`，连续3页同主题=视觉疲劳，禁止
  4. **P0/P1/P2/P3检查清单**——真实踩坑经验的系统化沉淀，每一条都对应一次翻车

- **核心设计原则（5条）：**
  1. 克制优于炫技 — WebGL只在hero页透出
  2. 结构优于装饰 — 不用阴影/浮动卡片，靠字号+字体对比+网格留白
  3. 图片是第一公民 — 只裁底部，保证顶/左右完整
  4. 节奏靠hero页 — hero/non-hero交替，不累眼睛
  5. 术语统一 — Skills就是Skills，不中英混译

---

## 适用场景

#PPT生成 #网页演示 #电子杂志风 #单文件HTML #ClaudeCodeSkill #演示工具
