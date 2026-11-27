#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""页面生成器：data/*.json (+ 可选 summaries/*.json) -> 多源展示页 HTML。

用法：
    python3 scripts/gen_page.py --config config.json

输入：
    data/<公众号名>.json         fetch_wechat.py 的输出（必需）
    summaries/<公众号名>.json    AI 增强内容（可选），结构：
        {
          "aiById":   {"文章k": "一句话AI点评", ...},
          "weekThis": {"title": "...", "text": "...", "topics": [{"name": "...", "ids": ["k", ...]}]},
          "weekLast": {...同上...},
          "insight":  "全年行业观察段落"
        }
        由 Agent（LLM）阅读文章标题后撰写；缺失时脚本自动生成统计版周报。

输出：output/公众号情报站.html（纯静态，数据内嵌，无外部接口）
"""
import argparse
import datetime
import json
import os


def reads_num(r):
    s = str(r or "")
    try:
        return float(s.replace("万", "")) * 10000 if "万" in s else float(s)
    except ValueError:
        return 0


def basic_week(arts, monday, title):
    week = [a for a in arts if monday <= a["d"] < (datetime.date.fromisoformat(monday) + datetime.timedelta(days=7)).isoformat()]
    week.sort(key=lambda a: reads_num(a["r"]), reverse=True)
    total_reads = sum(reads_num(a["r"]) for a in week)
    text = (f"本周期共发布 {len(week)} 篇，合计阅读约 {total_reads/10000:.1f} 万。"
            if week else "本周期暂无文章。")
    return {"title": title, "text": text,
            "topics": [{"name": "全部文章", "arts": week}]} if week else {"title": title, "text": text, "topics": []}


def build_source(name, out_dir):
    arts = json.load(open(f"data/{name}.json", encoding="utf-8"))
    summ_path = f"summaries/{name}.json"
    summ = json.load(open(summ_path, encoding="utf-8")) if os.path.exists(summ_path) else {}
    ai_by_id = summ.get("aiById", {})
    for a in arts:
        if a["k"] in ai_by_id:
            a["ai"] = ai_by_id[a["k"]]

    months = {}
    for a in arts:
        m = a["d"][:7]
        months.setdefault(m, {"m": m[2:], "n": 0, "r": 0})
        months[m]["n"] += 1
        months[m]["r"] += reads_num(a["r"])
    months = [months[m] for m in sorted(months)]

    today = datetime.date.today()
    this_monday = (today - datetime.timedelta(days=today.weekday())).isoformat()
    last_monday = (today - datetime.timedelta(days=today.weekday() + 7)).isoformat()

    def week_pack(key, monday, title):
        w = summ.get(key)
        if w and w.get("topics"):
            byk = {a["k"]: a for a in arts}
            return {"title": w["title"], "text": w["text"],
                    "topics": [{"name": t["name"], "arts": [byk[i] for i in t["ids"] if i in byk]}
                               for t in w["topics"]]}
        return basic_week(arts, monday, title)

    hot = sorted(arts, key=lambda a: reads_num(a["r"]), reverse=True)[:10]
    return {
        "name": name,
        "dataUntil": max(a["d"] for a in arts) if arts else "",
        "total": len(arts),
        "articles": arts[:10],
        "hot": hot,
        "months": months,
        "weekThis": week_pack("weekThis", this_monday, "本周综述"),
        "weekLast": week_pack("weekLast", last_monday, "上周综述"),
        "insight": summ.get("insight", f"共收录 {len(arts)} 篇文章。AI 行业观察可在 summaries/{name}.json 的 insight 字段补充。" if arts else "该信息源正在接入中，接口恢复后将自动抓取文章并生成 AI 行业观察。"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()
    cfg = json.load(open(args.config, encoding="utf-8"))
    sources = [build_source(name, cfg.get("output_dir", "output")) for name in cfg["sources"]
               if os.path.exists(f"data/{name}.json")]
    if not sources:
        raise SystemExit("没有可用数据，请先运行 fetch_wechat.py")
    data = {"generatedAt": datetime.date.today().isoformat(), "sources": sources}
    template = open(os.path.join(os.path.dirname(__file__), "..", "assets", "page_template.html"), encoding="utf-8").read()
    out = template.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    out_dir = cfg.get("output_dir", "output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "公众号情报站.html")
    open(path, "w", encoding="utf-8").write(out)
    print("生成完成:", path, f"({len(out)} 字符, {len(sources)} 个信息源)")


if __name__ == "__main__":
    main()
