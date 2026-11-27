---
name: wechat-radar
description: 监测指定微信公众号，定时抓取最新文章，生成 AI 文章点评、每周主题总结与趋势洞察，并产出一个手机可打开的多信息源展示页面（纯静态 HTML）。当用户要求"监测/追踪某个公众号""做公众号文章总结/周报""生成公众号情报页面"时使用。需要 Qovia API Key（公众号数据服务）。
---

# 公众号情报站（WeChat Radar）

把「公众号监测 + AI 总结 + 移动展示页」整条流程自动化。最终交付一个**可交互的手机网页链接**，含四个 Tab：动态（焦点卡+文章列表+AI 点评）、周报（每周主题综述）、洞察（趋势图+热文榜）、配置（Key/信息源/频率）。

## 输入（向用户确认）

- `qovia_key`：Qovia API Key，申请入口 https://www.qovia.ai/zh/wechat-api/
- `sources`：公众号名称列表（一个或多个，尽量精确全称）
- 抓取频率：每 1 小时 / 每 3 小时 / 每天 / 每周（需要定时任务能力时配置）

## 执行流程

1. **准备配置**：复制 `config.example.json` 为 `config.json`，填入 key 与公众号列表。
2. **抓取数据**：运行 `python3 scripts/fetch_wechat.py --config config.json`。
   - 自动搜索公众号得到 `mp_id`（优先精确名称匹配），分页拉取文章，增量去重后保存到 `data/<公众号名>.json`。
3. **AI 内容撰写（Agent 完成，不是脚本）**：阅读 `data/*.json` 的文章标题与数据，为每个信息源写 `summaries/<公众号名>.json`：
   - `aiById`：重点文章（最新 15 篇 + 热文 Top10）的一句话点评，基于标题事实与行业背景；
   - `weekThis` / `weekLast`：本周/上周综述（title、text）与主题分组（topics: name + 文章 k 列表）；
   - `insight`：全年趋势与行业观察段落。
4. **生成页面**：运行 `python3 scripts/gen_page.py --config config.json`，得到 `output/公众号情报站.html`（多源架构，每个公众号一个筛选按钮）。
5. **托管交付**：用当前环境的文件上传/静态托管能力把 HTML 变成可访问 URL，以可交互网页形式交付（不要只发截图）。校验方式：浏览器打开链接，切换 Tab 与信息源，确认交互可用。
6. **定时更新（可选）**：按用户设定频率创建定时任务，重复步骤 2→5，更新后把新链接发给用户。

## 关键约束与已知坑（务必遵守）

- **不要在浏览器/前端直接调用 Qovia**：API 的 CORS 仅允许自家 Origin，静态页 fetch 必失败。抓取只能由 Agent 在后台（Python/curl）执行，页面纯展示。
- **不要假装读了正文**：Qovia 文章数据的 `digest` 通常为空；直接抓微信文章正文会触发反爬环境检测页。AI 总结基于标题+数据，页面文案保持"要点解读"表述。
- **费用**：Qovia 空结果页不计费；余额/试用不足返回 402。脚本会中断并保留已抓数据，此时告知用户充值，不要反复重试烧请求。
- **数据边界**：用户的 key、抓取的文章数据、AI 文案均不进入本 Skill 仓库；`config.json`、`data/`、`summaries/`、`output/` 已加入 .gitignore。
- **链接有效期**：部分托管方式是"每次上传生成新链接"，不要向用户承诺网址永久不变；更新后重新发送最新链接。

## 目录

```
wechat-radar/
├── SKILL.md                  # 本文件
├── config.example.json       # 配置示例
├── scripts/
│   ├── fetch_wechat.py       # Qovia 抓取（搜索/分页/增量/重试/402保护）
│   └── gen_page.py           # 数据+AI文案 → 多源 HTML
└── assets/
    └── page_template.html    # 展示页模板（设计规范/多源筛选/配置页）
```
