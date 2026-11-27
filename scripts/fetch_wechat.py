#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qovia 公众号文章抓取：搜索公众号 -> 分页拉文章 -> 增量去重 -> 落盘。

用法：
    python3 scripts/fetch_wechat.py --config config.json
    python3 scripts/fetch_wechat.py --config config.json --source 公众号名

输出：data/<公众号名>.json（精简文章列表，含 k/t/u/d/r/l/o/published_at）
注意：
    - 空结果页不计费；余额不足(402)时中断但保留已抓数据。
    - 重复运行自动按已保存数据去重（增量更新）。
"""
import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error

BASE = "https://api.qovia.ai"


def api(path, key, params=None, retries=4):
    url = BASE + path
    if params:
        from urllib.parse import urlencode
        url += "?" + urlencode(params)
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + key})
        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:200]
            if e.code == 402:
                print("  [402] 余额或试用额度不足，停止抓取（已抓数据会保留）")
                return {"__stop__": True}
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            print(f"  [HTTP {e.code}] {body}")
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            print("  请求失败:", e)
            return None
    return None


def find_mp_id(name, key):
    res = api("/v1/raw/wechat/account_search", key, {"keyword": name})
    if not res or res.get("__stop__"):
        return None
    items = res.get("data") or res.get("items") or []
    for it in items:
        if it.get("name") == name or it.get("nickname") == name:
            return it.get("mp_id") or it.get("fakeid")
    if items:
        it = items[0]
        print(f"  未找到精确匹配，采用首个候选: {it.get('name') or it.get('nickname')}")
        return it.get("mp_id") or it.get("fakeid")
    return None


def slim(item):
    """统一精简字段：k=文章ID尾6位 t=标题 u=链接 d=日期 r=阅读标签 l=点赞 o=原创"""
    aid = str(item.get("id") or item.get("aid") or "")
    ts = item.get("published_at") or item.get("create_time") or ""
    if isinstance(ts, (int, float)) and ts > 0:
        d = time.strftime("%Y-%m-%d", time.localtime(ts))
    else:
        d = str(ts)[:10]
    return {
        "k": aid[-6:],
        "id": aid,
        "t": item.get("title") or "",
        "u": item.get("url") or item.get("link") or "",
        "d": d,
        "published_at": d,
        "r": item.get("reads_label") or item.get("reads") or "—",
        "l": item.get("likes"),
        "o": bool(item.get("original") or item.get("is_original")),
        "ai": "",
    }


def fetch_source(name, key, cfg):
    print(f"[信息源] {name}")
    mp_id = find_mp_id(name, key)
    if not mp_id:
        print("  未找到公众号，跳过")
        return
    os.makedirs("data", exist_ok=True)
    path = f"data/{name}.json"
    existing = []
    if os.path.exists(path):
        existing = json.load(open(path, encoding="utf-8"))
    seen = {a.get("id") for a in existing}
    new_items = []
    cursor = None
    page_size = cfg.get("page_size", 20)
    for page in range(cfg.get("max_pages", 30)):
        params = {"mp_id": mp_id, "limit": page_size}
        if cursor:
            params["cursor"] = cursor
        res = api("/v1/raw/wechat/articles", key, params)
        if not res or res.get("__stop__"):
            break
        items = res.get("data") or res.get("items") or []
        if not items:
            break
        added = 0
        for it in items:
            s = slim(it)
            if s["id"] and s["id"] not in seen:
                seen.add(s["id"])
                new_items.append(s)
                added += 1
        print(f"  第{page+1}页: {len(items)} 条, 新增 {added}")
        cursor = res.get("next_cursor") or res.get("cursor")
        if not cursor or added == 0:
            break
        time.sleep(0.5)
    merged = sorted(existing + new_items, key=lambda a: a["d"], reverse=True)
    json.dump(merged, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  已保存 {path}，共 {len(merged)} 篇（新增 {len(new_items)}）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--source", help="只抓指定公众号")
    args = ap.parse_args()
    cfg = json.load(open(args.config, encoding="utf-8"))
    key = cfg["qovia_key"]
    if not key.startswith("sk-"):
        sys.exit("请先在 config.json 填 qovia_key")
    sources = [args.source] if args.source else cfg["sources"]
    for name in sources:
        fetch_source(name, key, cfg.get("fetch", {}))


if __name__ == "__main__":
    main()
