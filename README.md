# 公众号情报站 · WeChat Radar

一个给 AI Agent 用的 Skill：监测任意微信公众号，抓取最新文章，生成 **AI 文章点评 + 每周主题总结 + 全年趋势洞察**，最后产出一个**手机打开就能看的多信息源展示页面**。

不需要自己部署服务器、不需要前端跨域折腾——数据抓取由 Agent 在后台执行，页面是纯静态 HTML（数据内嵌）。

## 页面长什么样

- **动态**：数据概览 → 今日焦点卡 → 紧凑文章列表（每篇带 AI 点评）
- **周报**：本周/上周切换，综述 + 主题分组
- **洞察**：月度发文/阅读趋势图、行业观察、历史热文 TOP10
- **配置**：Qovia Key、信息源公众号管理、抓取频率（配置保存在本机浏览器）
- 顶部**信息源筛选条**：多个公众号一键切换，三页内容联动

## 给 Agent 用（推荐）

1. 把本仓库的 `wechat-radar` 目录放进你的 Agent 的 Skills 目录（或直接让它阅读 `SKILL.md`）
2. 对它说：「用 wechat-radar 监测公众号 XXX，Key 是 sk-qovia-...，每天抓一次」
3. Agent 按 SKILL.md 流程执行：抓数据 → 写 AI 总结 → 生成页面 → 托管并给你可交互链接

## 手动用（无 Agent 也可以跑前两步）

```bash
git clone https://github.com/rannnnyihan/wechat-radar.git
cd wechat-radar
cp config.example.json config.json   # 填入你的 Qovia Key 和公众号名称
python3 scripts/fetch_wechat.py      # 抓取文章到 data/
python3 scripts/gen_page.py          # 生成 output/公众号情报站.html
```

只用脚本会得到统计版周报；AI 点评、主题分组、行业观察需要 LLM 撰写 `summaries/<公众号名>.json`（结构见 `scripts/gen_page.py` 注释），然后重新生成页面。把 HTML 部署到任意静态托管（GitHub Pages、Vercel、对象存储）即可手机访问。

## 你需要准备

- Qovia API Key（公众号数据服务）：https://www.qovia.ai/zh/wechat-api/
- Python 3.8+，仅标准库，无依赖

## 设计说明

- **为什么页面不直接抓数据**：Qovia API 不允许浏览器跨域调用，所以架构是「Agent 后台抓取 + 纯静态展示页」
- **AI 总结的依据**：公众号正文有反爬、摘要字段为空，AI 内容基于文章标题与阅读数据生成，页面明确标注为要点解读
- **费用意识**：Qovia 按次计费、空结果免费，脚本带增量去重与 402 余额保护

## 免责声明

本工具仅聚合公开公众号文章元数据，内容总结由 AI 生成，不构成任何投资建议。请遵守数据服务方与内容平台的使用条款。

## License

MIT
