#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qovia 公众号文章抓取，双路径：
  A. /v1/search（推荐）：query + author 过滤直接搜文章，无需 gh_ ID，带正文摘要。
     在 config.json 的 search_method 中配置 {"源名": {"query": [关键词...], "author": "源名"}}。
  B. /v1/raw/wechat：account_search 找 mp_id -> articles 分页（适合有 gh_ 完整档案的号，
     含阅读数标签）。v1 只给微信号时自动回退 v2 换算 gh_。
增量去重 -> 落盘。

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


def api_post(path, key, body, retries=4):
    """POST 请求（/v1/search 通用搜索端点）"""
    data = json.dumps(body).encode("utf-8")
    for attempt in range(retries):
        req = urllib.request.Request(BASE + path, data=data, method="POST",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode("utf-8", "ignore")[:200]
            if e.code == 402:
                print("  [402] 余额或试用额度不足，停止抓取（已抓数据会保留）")
                return {"__stop__": True}
            if e.code in (429, 500, 502, 503) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            print(f"  [HTTP {e.code}] {body_txt}")
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            print("  请求失败:", e)
            return None
    return None


import re
import hashlib

def valid_mp_id(mid):
    return bool(mid and re.match(r"^(gh|wxid)_[0-9a-zA-Z_]+$", mid))


def _walk_gh(o, name):
    """在 v2 响应里递归找 gh_/wxid_ 格式的 userName，优先名称精确匹配"""
    best = [None]
    def rec(o):
        if isinstance(o, dict):
            un = o.get("userName")
            if un and valid_mp_id(un):
                nick = o.get("nickName") or o.get("name")
                if nick == name:
                    best[0] = un
                    return
                if best[0] is None:
                    best[0] = un
            for v in o.values():
                rec(v)
        elif isinstance(o, list):
            for it in o:
                rec(it)
    rec(o)
    return best[0]


def find_mp_id(name, key):
    res = api("/v1/raw/wechat/account_search", key, {"keyword": name})
    if not res or res.get("__stop__"):
        return None
    items = (res.get("data") or {}).get("items") or []
    if not items:
        print(f"  Qovia 未收录公众号「{name}」（搜索无结果）")
        return None
    cand = None
    for it in items:
        if it.get("name") == name or it.get("nickname") == name:
            cand = it
            break
    if cand is None:
        cand = items[0]
        print(f"  未找到精确匹配，采用首个候选: {cand.get('name') or cand.get('nickname')}")
    mid = cand.get("mp_id") or cand.get("fakeid")
    if valid_mp_id(mid):
        return mid
    # v1 只给了微信号：自动回退 v2 换算 gh_ 原始 ID
    print(f"  v1 返回的 ID 为微信号格式({mid})，文章接口不支持，自动尝试 v2 换算…")
    v2 = api("/v1/raw/wechat/account_search_v2", key, {"keyword": name})
    if v2 and not v2.get("__stop__"):
        gh = _walk_gh(v2.get("data") or v2, name)
        if gh:
            print(f"  v2 换算成功: {gh}")
            return gh
    print("  ✗ 暂无法获得合规 mp_id：Qovia 对该号收录不全且 v2 接口不可用。")
    print("    可稍后重试，或提供该公众号文章链接改用单篇接口（article_metrics/article_content_v3）。")
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
        params = {"mp_id": mp_id}
        if cursor:
            params["cursor"] = cursor
        res = api("/v1/raw/wechat/articles", key, params)
        if not res or res.get("__stop__"):
            break
        items = (res.get("data") or {}).get("items") or []
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
        cursor = (res.get("data") or {}).get("cursor")
        if not cursor or not (res.get("data") or {}).get("has_more"):
            break
        time.sleep(0.5)
    if not existing and not new_items:
        print("  未获取到任何文章，不写入数据文件")
        return
    merged = sorted(existing + new_items, key=lambda a: a["d"], reverse=True)
    json.dump(merged, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  已保存 {path}，共 {len(merged)} 篇（新增 {len(new_items)}）")


def slim_search(item):
    """/v1/search 条目转统一字段；k 用 url 的 md5 前6位，与既有数据保持一致"""
    u = item.get("url") or ""
    ts = item.get("published_at") or ""
    m = item.get("metrics") or {}
    return {
        "k": hashlib.md5(u.encode()).hexdigest()[:6],
        "id": item.get("id") or hashlib.md5(u.encode()).hexdigest()[:12],
        "t": (item.get("title") or "").strip(),
        "u": u,
        "d": str(ts)[:10],
        "published_at": ts,
        "r": m.get("reads") or 0,
        "l": m.get("likes") or 0,
        "o": 0,
        "text": (item.get("text") or "")[:600],
        "ai": "",
    }


def fetch_search_source(name, key, sm):
    """走 /v1/search 按作者名抓文章：无需 gh_ ID，带正文摘要。
    sm = {"query": [关键词...], "author": 名称（默认同 name）}
    仅保留 author.name 精确匹配的条目，按 url 去重合并。"""
    print(f"[信息源] {name}（/v1/search 路径）")
    author = sm.get("author", name)
    queries = sm.get("query") or ["新闻"]
    os.makedirs("data", exist_ok=True)
    path = f"data/{name}.json"
    existing = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []
    seen = {a.get("u") for a in existing}
    latest = max((a.get("d") or "" for a in existing), default="")
    new_items = []
    for q in queries:
        body = {"query": q, "platforms": ["wechat"], "author": author, "limit": 20, "page": 1}
        if latest:
            body["since"] = latest
        res = api_post("/v1/search", key, body)
        if not res:
            continue
        if res.get("__stop__"):
            break
        items = (res.get("data") or {}).get("items") or []
        added = 0
        for it in items:
            if (it.get("author") or {}).get("name") != author:
                continue
            s2 = slim_search(it)
            if s2["u"] and s2["u"] not in seen:
                seen.add(s2["u"])
                new_items.append(s2)
                added += 1
        print(f"  query={q}: {len(items)} 条, 新增 {added}")
        time.sleep(0.5)
    if not existing and not new_items:
        print("  未获取到任何文章（该号可能未被搜索索引收录），不写入数据文件")
        return
    merged = sorted(existing + new_items, key=lambda a: a["published_at"], reverse=True)
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
        sm = (cfg.get("search_method") or {}).get(name)
        if sm:
            fetch_search_source(name, key, sm)
        else:
            fetch_source(name, key, cfg.get("fetch", {}))


if __name__ == "__main__":
    main()
