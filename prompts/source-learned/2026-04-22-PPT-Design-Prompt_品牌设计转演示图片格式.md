---
title: "PPT-Design-Prompt — 将品牌设计指南转换为演示图片格式"
topic_keywords: [PPT-Design-Prompt, DESIGN.md, 品牌设计, 演示图片, 设计代理, 幻灯片图片系统, VoltAgent]
source: GitHub
original_url: https://github.com/Russell-cell/PPT-Design-Prompt
date: 2026-04-22
---

# PPT-Design-Prompt — 品牌设计指南转演示图片格式

## 核心定位

将 `DESIGN.md` 品牌参考文档转换为面向**演示图片系统**的 `DESIGN.md` 文件，供图片模型和设计代理使用。

**范围**：幻灯片图片系统（非完整幻灯片、非HTML演示、非产品UI实现）

**上游来源**：VoltAgent/awesome-design-md

---

## 仓库结构

```
├── DESIGN.md                    # 通用演示图片设计指南
├── ATTRIBUTION.md               # 许可和来源边界
├── catalog/brands.txt           # 可选品牌目录
├── examples/minimal/            # 测试用合成示例
├── ppt-image/                  # 生成的输出
├── scripts/                    # 便捷封装脚本
├── src/awesome_design_md_ppt_images/
│   ├── cli.py                  # 命令行接口
│   └── converter.py            # 转换器
└── tests/
```

---

## 快速开始

```bash
# 运行转换 — 输出到 ./ppt-image 和 ./conversion_manifest.json
python -m src.awesome_design_md_ppt_images

# 或指定路径
python -m src.awesome_design_md_ppt_images --source /path/to/source --output /path/to/output
```

---

## 适用场景

#PPT-Design-Prompt #DESIGN.md #设计代理 #演示图片 #品牌设计 #幻灯片
