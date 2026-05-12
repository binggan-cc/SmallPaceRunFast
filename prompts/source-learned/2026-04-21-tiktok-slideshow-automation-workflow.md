---
title: TikTok Slideshow 自动化制作工作流（Claude + Pinterest + Node.js + Postiz）
topic: TikTok内容自动化 | 社媒运营工作流 | 内容流水线
source: 直接粘贴分享
original_link: (用户直接粘贴内容)
date: 2026-04-21
---

# TikTok Slideshow 自动化制作工作流

## 核心信息

- **成本**: ~$0（几乎开源）
- **技术栈**: TikTok · SnapTik · Claude Opus 4.7 · Pinterest · Node.js Canvas · Postiz Agent CLI
- **目标**: 批量生成 slideshow 内容，一周 30 条，2 小时完成

## 核心价值主张

1. **无昂贵工具**: Buffer/Later/Hootsuite 免费额度有限，Postiz 自托管无限
2. **可扩展**: 配置好后批量生产
3. **数据驱动**: Hook 来自真实病毒视频，不是猜测

## 工作流总览（5步）

```
[TikTok Scroll] → [SnapTik Download] → [Claude Opus 4.7 Extract Hook]
        ↓
[Pinterest Pick Images] → [Node.js Canvas Script → PNG Slides]
        ↓
[Postiz Agent CLI → Schedule Draft]
        ↓
[TikTok App → Drafts → Tap Post at peak time]
```

---

## Step 1: 从 TikTok 找 Hook

**什么是 Hook**: 前3秒决定用户是否停止滑动

**找 Hook 方法**:
- TikTok 搜索关键词（StudyTok/GymTok/BookTok），按 Most Liked 或 Most Recent 筛选
- 关注：前2秒文字overlay、开场白（问题或震惊陈述）、重复格式

**常见 Hook 格式**:
- "You're doing X wrong"
- "X things Y never tells you"
- "I did X and here's what happened"

**下载视频工具**: SnapTik.app / SSSTik.io（无水印下载）

## Step 2: Claude Opus 4.7 分析 Hook

### Prompt（上传slideshow图片后）:
> Analyze this TikTok slideshow and:
> 1. Identify the main hook used in the first slide
> 2. Explain why this hook works
> 3. Break down the hook structure
> 4. Write 5 similar hook variations for your niche

### Prompt（只有文字内容时）:
> Here is the content of a viral TikTok slideshow in the niche [NICHE]:
> [PASTE CONTENT]
> Task:
> - Identify the core hook from the first slide
> - Write 7 hook variations triggering: curiosity / FOMO / empathy
> - Max 8 words per hook

### Bonus: 生成 Pinterest 搜索词
> Based on this slideshow, suggest 10 Pinterest search queries matching the visual style and content theme.
> Focus on: aesthetic keywords, composition, niche-specific visuals

## Step 3: Pinterest 选图

**好图片标准**:
- 比例: 竖版 9:16优先
- 颜色: Bold、高对比度，避免柔和粉彩
- 内容: 图片上文字尽量少（文字会在脚本中覆盖）
- 氛围: 与 Hook 情绪匹配

**下载方式**:
1. PinDown Chrome 扩展
2. 右键保存原图
3. Python 批量下载脚本

**目录结构**:
```
pinterest_images/
├── finance/
├── fitness/
└── lifestyle/
```

## Step 4: Node.js Canvas 生成幻灯片

### 安装依赖
```bash
npm init -y
npm install canvas @napi-rs/canvas sharp
```

### 幻灯片结构
```
Slide 1: HOOK
Slide 2: Problem / Setup
Slide 3: Point 1
Slide 4: Point 2
Slide 5: Point 3
Slide 6: CTA (Follow/Save/Comment)
```

### 核心脚本功能 (generate-slides.js)
- 读取 pinterest 图片，cover-fit 到 1080x1920
- 添加半透明深色遮罩 (rgba 0,0,0, 0.52)
- 居中白字 + 阴影
- 导出 1080×1920 PNG

### JSON 配置驱动
slides-config.json 示例:
```json
[
  {
    "imagePath": "./pinterest_images/finance/image_001.jpg",
    "lines": [
      { "text": "I saved $5k in 6 months", "size": 88, "weight": "bold", "y": 860 },
      { "text": "doing this one thing", "size": 72, "weight": "normal", "y": 970 }
    ]
  }
]
```

## Step 5: Postiz Agent CLI 定时发布

### 安装和配置
```bash
npm install -g postiz
export POSTIZ_API_KEY=your_api_key_here
postiz integrations:list  # 验证连接
```

### 核心命令
```bash
# 上传幻灯片获取CDN URL
postiz upload ./output/slide_01.png | jq -r '.path'

# 创建定时帖子
postiz posts:create \
  -c "Caption text" \
  -m "$SLIDE1" -m "$SLIDE2" \
  -s "2025-04-21T09:00:00Z" \
  -i "integration-id"
```

### 批量定时
- schedule.json 定义每周排期
- batch-schedule.js 循环调用 Postiz CLI
- 一条命令搞定整周排期

## Step 6: 避免 Spam Detection——Draft 模式

**直接API发布的风险**:
- 服务器IP发起 → 被识别为机器人
- 一致的时间间隔 → 算法降权/封号

**安全做法**:
1. 用 `-t draft` 或 `content_posting_method: "UPLOAD"` 上传到草稿箱
2. Postiz 设置 Notify 模式，在高峰期推送通知
3. 用户打开 TikTok App → 草稿 → 手动发布

**核心逻辑**: 从算法角度看，草稿发布 = 真实设备 + 真实网络的人类行为，无服务器指纹

---

## 故障排除

| 问题 | 解决方案 |
|------|---------|
| POSTIZ_API_KEY 未设置 | echo 'export POSTIZ_API_KEY=...' >> ~/.zshrc && source ~/.zshrc |
| integrations:list 返回空 | 在 app.postiz.com 连接 TikTok 账号 |
| 上传失败 | 检查 API Key 有效性 |
| 定时帖子未发出 | posts:list 查看状态，通常是 OAuth token 过期 |

---

## 适用场景

- **个人品牌/内容创作者**: 需要批量生产 TikTok slideshow
- **MCP/AI Agent 工作流**: 可整合到自动化 pipeline
- **出海/社媒运营**: 低成本内容矩阵打法

## 标签

#TikTok #内容自动化 #社媒运营 #Claude #Pinterest #NodeJS #Postiz #工作流 #生产力
