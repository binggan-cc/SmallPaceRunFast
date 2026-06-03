# SmartDev Agent｜SmartFav 项目适配器 v1.0

> 让 SmartDev Agent 理解 SmartFav 的项目结构、技术约束、可修改范围和验证方式。

---

## 1. 项目基础信息

| 项目 | 内容 |
|------|------|
| 项目名称 | SmartFav / SmartFAV |
| 项目类型 | Chrome Extension + FastAPI Local Server |
| 当前版本 | v1.6 |
| 产品定位 | 本地优先的智能收藏管理器 |
| 前端技术 | Vanilla JS、ES Modules、CSS Custom Properties |
| 扩展规范 | Chrome Extension Manifest V3 |
| 后端技术 | FastAPI + SQLite |
| AI 能力 | OpenAI-compatible + Ollama |
| 文档导出 | Markdown 单文件导出、Vault 多文件同步 |

---

## 2. 目录职责

```
smartfav/
├── apps/
│   ├── extension/          # Chrome Extension 正式代码
│   │   ├── manifest.json
│   │   ├── assets/styles/tokens.css  # 设计令牌唯一来源
│   │   └── src/
│   │       ├── background/  # Service Worker（不支持 ES modules）
│   │       ├── content/     # Content Script（不支持 ES modules）
│   │       ├── sidepanel/   # Side Panel（支持 ES modules）
│   │       ├── popup/       # Popup（支持 ES modules）
│   │       ├── services/    # 业务逻辑服务
│   │       ├── models/      # 数据模型
│   │       └── utils/       # 工具函数
│   │
│   └── server/             # FastAPI 后端
│       ├── main.py
│       ├── database.py
│       ├── models.py
│       ├── ai_service.py
│       └── vault_service.py
│
├── assets/                 # Demo 页面（UI 参考，非生产代码）
├── docs/                   # 项目文档
└── old/                    # 旧项目参考（只读）
```

---

## 3. 可修改区域

| 区域 | 可修改 | 说明 |
|------|--------|------|
| apps/extension/src/sidepanel | 是 | Side Panel 功能、样式、交互 |
| apps/extension/src/popup | 是 | Popup 快速入口 |
| apps/extension/src/services | 是 | 存储、API、AI、Markdown 服务 |
| apps/extension/src/utils | 是 | 工具函数 |
| apps/server | 是 | API、数据库、AI、Vault |
| docs | 是 | 文档沉淀 |
| assets Demo 页面 | 是 | UI Demo、设计样式调整 |

---

## 4. 谨慎修改区域

| 区域 | 原因 | 要求 |
|------|------|------|
| manifest.json | 影响扩展权限和加载 | 必须说明权限变化 |
| background/index.js | MV3 Service Worker 敏感 | 必须检查兼容性 |
| content/index.js | 注入网页上下文 | 必须避免页面污染 |
| database.py | 影响数据结构 | 必须说明迁移影响 |
| models.py | 影响前后端协议 | 必须同步检查前端 |
| ResourceItem 模型 | 核心协议 | 必须说明 schemaVersion 影响 |

---

## 5. 禁止修改区域

| 区域 | 规则 |
|------|------|
| old/ | 默认只读 |
| 数据库真实数据文件 | 不得删除或重置 |
| API Key、Token、密钥文件 | 不得打印、提交、暴露 |

---

## 6. Chrome Extension 约束

1. Background Service Worker 不支持 ES modules
2. Content Script 不支持 ES modules
3. Side Panel 和 Popup 支持 ES modules
4. 权限必须最小化
5. 右键菜单、Badge、消息路由集中在 Background 层

---

## 7. FastAPI 约束

1. 保持轻量、本地可启动
2. SQLite 优先
3. 不过早引入复杂用户系统、多租户、微服务

---

## 8. Token 当前状态

- 唯一来源：`apps/extension/assets/styles/tokens.css`
- Token 覆盖率：100%（无硬编码颜色）
- 待补充：Dark Mode token（v1.7）

---

## 9. Side Panel 验收规则

### 宽度适配

| 宽度 | 验收 |
|------|------|
| 320px | 无横向滚动 |
| 400px | 信息密度正常 |
| 480px | 内容不松散 |

### 必须检查的状态

- 默认状态、搜索结果、空状态、加载态、错误态
- 编辑对话框、图片预览、AI 结果对话框
- 标签管理对话框、分类管理对话框
- 服务在线/离线状态
- 遮罩不误覆盖（`[hidden] { display: none !important; }`）

---

## 10. 当前优先任务

| 优先级 | 任务 |
|--------|------|
| P1 | 规划 v1.7 Dark Mode |
| P1 | 沉淀 Bug 知识库 |
| P2 | 生成 docs/design-tokens.md |

---

## 11. Agent 配置

```json
{
  "adapter": "SmartFav",
  "version": "1.0",
  "project": {
    "name": "SmartFav",
    "type": "chrome-extension-local-first",
    "current_version": "v1.6",
    "next_version": "v1.7"
  },
  "paths": {
    "extension": "apps/extension",
    "server": "apps/server",
    "demo": "assets",
    "docs": "docs"
  },
  "protected_paths": ["old", "database files", "secrets"],
  "principles": [
    "先诊断后修改",
    "小步快跑",
    "不扩大改动范围",
    "每步可验证",
    "文档同步更新"
  ]
}
```
