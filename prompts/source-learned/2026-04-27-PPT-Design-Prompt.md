# PPT-Design-Prompt 研究报告

- **主题：** DESIGN.md 转换 / PPT 图片资产生成 / 设计系统
- **来源：** GitHub - Russell-cell/PPT-Design-Prompt
- **链接：** https://github.com/Russell-cell/PPT-Design-Prompt
- **时间：** 2026-04-27

---

## Step 1: 项目定位

- **一句话描述：** 将品牌级 `DESIGN.md` 文件转换为演示图片导向格式的 Python CLI 工具，专为 PowerPoint / Keynote / PDF / 视觉文章生成资产
- **上游来源：** VoltAgent/awesome-design-md（设计系统文档库）
- **核心任务：** 把 Web/UI 导向的设计参考重新解释为"演示图片提示词"

---

## Step 2: 技术栈分析

- **语言：** Python
- **安装：** `python -m pip install -e .`
- **CLI 命令：** `design-md-ppt convert`
- **核心模块：**
  - `src/awesome_design_md_ppt_images/cli.py` — 命令行入口
  - `src/awesome_design_md_ppt_images/converter.py` — 转换器核心

### 仓库布局

```
DESIGN.md                    # 通用演示图片设计指南
ATTRIBUTION.md               # 许可证和来源边界
catalog/brands.txt           # 品牌目录（可选）
examples/minimal/            # 合成测试示例
ppt-image/                   # 生成输出目录
scripts/                     # 便捷包装脚本
src/awesome_design_md_ppt_images/
  cli.py                     # CLI 入口
  converter.py               # 转换器
tests/
```

---

## Step 3: 核心功能

### 设计.md → ppt-image//DESIGN.md 转换

```bash
# 基本用法
design-md-ppt convert

# 指定路径
design-md-ppt convert \
  --source-root ./source \
  --output-root ./ppt-image \
  --manifest ./conversion_manifest.json \
  --brands-file ./catalog/brands.txt
```

### 品牌目录机制

| 模式 | 行为 |
|------|------|
| 提供 `brands.txt` | 转换器知道哪些品牌是预期的，缺失的可以发出占位符 |
| 不提供 | 简单转换 source/ 下存在的文件 |

---

## Step 4: 明确边界

| 能做 | 不能做 |
|------|--------|
| DESIGN.md → 演示图片格式转换 | 生成完整 PPT / Keynote 文件 |
| 为 PowerPoint/Keynote/PDF 生成图片资产 | 导出 HTML 演示文稿 |
| 视觉文章的图片生成指导 | 产品 UI 实现 |

---

## Step 5: 价值判断

- **值得研究：** 是
- **核心洞察：**
  1. **定位精准** — 只做"演示图片资产"的生成指导，不是全流程 PPT 生成器，边界清晰
  2. **上游解耦** — `source/` 目录被 `.gitignore`，本地下载源保持本地，解决了开源再分发问题
  3. **品牌目录机制** — 可选 `brands.txt` 让转换器知道预期品牌，缺失时发出占位符而非报错
  4. **VoltAgent 生态** — 上游 `awesome-design-md` 是更大的设计系统文档集合，PPT-Design-Prompt 是其演示图片的专用转换层

- **对我们的启发：**
  - 设计系统文档（DESIGN.md）可以被垂直领域专用化——Web UI → 演示图片，是一次"再解释"而非重写
  - 开源边界设计（source/ 隔离 + ATTRIBUTION.md）值得借鉴，保护品牌材料版权的同时允许代码开源

## 适用场景

#PPT设计 #DESIGN.md #品牌设计系统 #PythonCLI #图片资产生成 #演示文稿
