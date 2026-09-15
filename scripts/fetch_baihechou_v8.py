#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""白河愁博士（雪球 u/7251377368）宏观观点 fetcher —— v8

为什么要用真实浏览器：
  雪球主域（xueqiu.com）上了阿里云 WAF，curl/urllib 直连一律返回挑战页（实测 110KB 的
  `<textarea id="renderData">` 反爬页，拿不到任何内容）。而雪球个人主页是 SPA，
  正文由 JS 渲染 —— 因此必须用真实浏览器执行 JS 拿到渲染后的 DOM。
  本机已装 Chrome，`--headless=new --dump-dom` 即可（实测可过 WAF、标题/正文全出）。

与「平均股价」fetcher 的区别：
  scripts/fetch_avg_price.py 走的是 `stock.xueqiu.com/v5/stock/chart/kline.json`（行情子域，无 WAF）；
  本脚本要的是**用户时间线**，只有主域提供，故走浏览器。

输出：data/BAIHECHOU_MACRO.js   （单行压缩，window.BAIHECHOU_MACRO = {...};  LF）
历史：raw_data/baihechou_posts.json（累积帖池，供去重与「连续未更新」判定）

🔴 铁律：本脚本 **绝不覆盖 analysis 字段**。
   analysis 由每日 AI 解析步骤写入；fetcher 只负责原文与元信息。
   若分析结果比帖子新，原样保留（否则每天的抓取会把解析抹掉）。
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import html as _html

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JS = os.path.join(BASE, "data", "BAIHECHOU_MACRO.js")
RAW_JSON = os.path.join(BASE, "raw_data", "baihechou_posts.json")

UID = "7251377368"
PROFILE_URL = f"https://xueqiu.com/u/{UID}"

# 主帖保留上限（页面一次给 20 条左右；累积池留 120 条，JS 只发最近 N 条）
RAW_KEEP = 120
JS_KEEP_MAIN = 30
JS_KEEP_REPLY = 12

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def log(m):
    print(f"  [baihechou] {m}", flush=True)


def find_browser():
    for p in CHROME_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None


def dump_dom(url, timeout=90):
    """用无头浏览器取渲染后的 DOM。失败返回 None。"""
    exe = find_browser()
    if not exe:
        log("未找到 Chrome/Edge，无法渲染雪球 SPA")
        return None
    ud = os.path.join(tempfile.gettempdir(), "baihechou_ud_%d" % os.getpid())
    shutil.rmtree(ud, ignore_errors=True)
    cmd = [exe, "--headless=new", "--disable-gpu", "--no-sandbox",
           "--disable-dev-shm-usage", "--no-first-run", "--disable-extensions",
           f"--user-data-dir={ud}", "--virtual-time-budget=15000",
           "--dump-dom", url]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        dom = r.stdout.decode("utf-8", "replace")
        if len(dom) < 20000 or "timeline__item" not in dom:
            log(f"DOM 异常（{len(dom)} 字节，可能被 WAF 拦）")
            return None
        return dom
    except subprocess.TimeoutExpired:
        log("浏览器超时")
        return None
    except Exception as e:
        log(f"浏览器异常：{e}")
        return None
    finally:
        shutil.rmtree(ud, ignore_errors=True)


def strip_tags(s):
    s = re.sub(r"<script[\s\S]*?</script>", " ", s)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s)
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</(p|div|h3)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = _html.unescape(s)
    s = s.replace("\u200b", "").replace("\xa0", " ")
    lines = [x.strip() for x in s.split("\n")]
    return "\n".join(x for x in lines if x)


def rel_to_abs(rel, now):
    """雪球相对时间 → 绝对时间字符串。无法解析返回 ''。"""
    rel = (rel or "").strip()
    if not rel:
        return ""
    m = re.match(r"^(\d+)\s*分钟前$", rel)
    if m:
        return (now - datetime.timedelta(minutes=int(m.group(1)))).strftime("%Y-%m-%d %H:%M")
    m = re.match(r"^(\d+)\s*秒前$", rel)
    if m:
        return (now - datetime.timedelta(seconds=int(m.group(1)))).strftime("%Y-%m-%d %H:%M")
    m = re.match(r"^(\d+)\s*小时前$", rel)
    if m:
        return (now - datetime.timedelta(hours=int(m.group(1)))).strftime("%Y-%m-%d %H:%M")
    if rel in ("刚刚", "刚才"):
        return now.strftime("%Y-%m-%d %H:%M")
    m = re.match(r"^昨天\s*(\d{1,2}):(\d{2})$", rel)
    if m:
        d = (now - datetime.timedelta(days=1)).date()
        return f"{d} {int(m.group(1)):02d}:{m.group(2)}"
    m = re.match(r"^(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$", rel)
    if m:
        return f"{now.year}-{int(m.group(1)):02d}-{int(m.group(2)):02d} {int(m.group(3)):02d}:{m.group(4)}"
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})$", rel)
    if m:
        return f"{int(m.group(1))}-{int(m.group(2)):02d}-{int(m.group(3)):02d} {int(m.group(4)):02d}:{m.group(5)}"
    return ""


def parse_profile(dom):
    """昵称 / 粉丝 / 简介 / 帖子数。"""
    out = {"uid": UID, "url": PROFILE_URL}
    m = re.search(r"<title>([^<]*)</title>", dom)
    if m:
        out["name"] = _html.unescape(m.group(1)).split("-")[0].strip()
    # 简介：紧跟在 profiles__base（关注/粉丝/地址）之后的第一个 <p>
    m = re.search(r'class="profiles__base"[\s\S]{0,1500}?<p>([\s\S]*?)</p>', dom)
    if m:
        out["desc"] = strip_tags(m.group(1))[:200]
    if not out.get("desc"):
        m = re.search(r'<h2[^>]*class="[^"]*profiles__hd[^"]*"[\s\S]{0,400}?<p>([\s\S]*?)</p>', dom)
        if m:
            out["desc"] = strip_tags(m.group(1))[:200]
    # 「100 关注 18580 粉丝」
    m = re.search(r"([\d,\.万]+)\s*关注\s*([\d,\.万]+)\s*粉丝", re.sub(r"<[^>]+>", " ", dom))
    if m:
        out["following"] = m.group(1)
        out["followers"] = m.group(2)
    m = re.search(r"帖子\s*(\d+)", re.sub(r"<[^>]+>", " ", dom))
    if m:
        out["post_count"] = m.group(1)
    return out


def _clean_body(raw):
    """去掉雪球正文里的控件文案（展开/收起/转发/收藏/投诉）与残留空白。"""
    s = strip_tags(raw)
    s = re.sub(r"\b(展开|收起|转发|收藏|投诉|查看对话)\b", "", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def parse_posts(dom, now):
    items = re.split(r'<article class="timeline__item"', dom)[1:]
    posts = []
    for it in items:
        sid_m = re.search(r'data-id="(\d+)"', it)
        if not sid_m:
            continue
        sid = sid_m.group(1)
        # 时间：class 含 date 的元素文本
        dt = re.search(r'class="[^"]*\bdate\b[^"]*"[^>]*>([^<]{2,30})<', it)
        rel = dt.group(1).strip() if dt else ""
        title = ""
        tm = re.search(r'class="timeline__item__title">([\s\S]*?)</h3>', it)
        if tm:
            title = strip_tags(tm.group(1))[:120]
        # 正文：content--description 块（长文）/ 普通 content 块都落在这里
        cm = re.search(r'<div class="content content--description">([\s\S]*?)</div>\s*</div>', it)
        if not cm:
            cm = re.search(r'<div class="timeline__item__content[^"]*">([\s\S]*?)</div>\s*</div>', it)
        body = _clean_body(cm.group(1)) if cm else ""
        # 配图（纯图片帖正文为空，图片在 content__addition 块）
        img = ""
        im = re.search(r'class="content__addition[^"]*"[\s\S]{0,200}?<img src="([^"]+)"', it)
        if im:
            img = im.group(1)
        if body in ("展开", "收起"):
            body = ""
        is_reply = body.startswith("回复@") or body.startswith("//@")
        if not body and not title and not img:
            continue          # 空壳（转发无内容等），不入池
        posts.append({
            "id": sid,
            "url": f"https://xueqiu.com/{UID}/{sid}",
            "rel": rel,
            "time": rel_to_abs(rel, now),
            "title": title,
            "text": body[:2000],
            "img": img,
            "is_reply": is_reply,
            "pinned": "置顶" in it[:800],
        })
    return posts


def load_raw():
    try:
        with open(RAW_JSON, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def load_existing_analysis():
    """从已有 data/BAIHECHOU_MACRO.js 里救出 analysis 与 meta（fetcher 绝不抹掉）。"""
    try:
        with open(OUT_JS, "r", encoding="utf-8") as f:
            t = f.read()
        m = re.search(r"window\.BAIHECHOU_MACRO\s*=\s*", t)
        if not m:
            return {}
        s = t[m.end():]
        i = s.find("{")
        depth, end = 0, -1
        for j in range(i, len(s)):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
        d = json.loads(s[i:end])
        return {"analysis": d.get("analysis"), "meta": d.get("meta")}
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只打印，不写文件")
    ap.add_argument("--debug-dom", metavar="PATH", help="用已保存的 DOM 文件解析（离线调试）")
    args = ap.parse_args()

    now = datetime.datetime.now()
    now_s = now.strftime("%Y-%m-%d %H:%M:%S")

    if args.debug_dom:
        dom = open(args.debug_dom, encoding="utf-8", errors="replace").read()
        log(f"离线解析 DOM {len(dom)} 字节")
    else:
        log("渲染雪球主页（Chrome headless）...")
        dom = dump_dom(PROFILE_URL)
        if not dom:
            log("❌ 抓取失败 —— 保持现有产物不动（绝不写脏数据）")
            return 1

    prof = parse_profile(dom)
    posts = parse_posts(dom, now)
    log(f"解析到 {len(posts)} 条（主帖 {sum(1 for p in posts if not p['is_reply'])} / 回复 {sum(1 for p in posts if p['is_reply'])}）")
    if not posts:
        log("❌ 0 条帖 —— DOM 结构可能已变，保持现有产物不动")
        return 1

    # ── 合并历史池（按 id 去重，新的覆盖旧的）──
    raw = load_raw()
    old = raw.get("posts") or []
    by_id = {p["id"]: p for p in old if isinstance(p, dict) and p.get("id")}
    for p in posts:
        prev = by_id.get(p["id"]) or {}
        # 保留首次抓到的绝对时间（相对时间会随时间漂移）
        if not p.get("time") and prev.get("time"):
            p["time"] = prev["time"]
        if not p.get("time"):
            p["time"] = prev.get("time") or ""
        by_id[p["id"]] = p
    pool = sorted(by_id.values(), key=lambda x: (x.get("time") or "", x.get("id") or ""), reverse=True)
    pool = pool[:RAW_KEEP]

    mains = [p for p in pool if not p.get("is_reply")]
    replies = [p for p in pool if p.get("is_reply")]
    latest_main = mains[0] if mains else None

    # 连续未更新天数（以主帖计）
    stale_days = None
    if latest_main and latest_main.get("time"):
        try:
            d0 = datetime.datetime.strptime(latest_main["time"][:10], "%Y-%m-%d").date()
            stale_days = (now.date() - d0).days
        except Exception:
            stale_days = None

    sal = load_existing_analysis()
    analysis = sal.get("analysis") or None

    payload = {
        "update_time": now_s,
        "source": "雪球 @白河愁博士（xueqiu.com/u/%s）" % UID,
        "fetch_mode": "chrome-headless-dump-dom",
        "profile": prof,
        "stats": {
            "total": len(pool),
            "main": len(mains),
            "reply": len(replies),
            "latest_main_time": (latest_main or {}).get("time") or "",
            "stale_days": stale_days,
        },
        "posts": mains[:JS_KEEP_MAIN],
        "replies": replies[:JS_KEEP_REPLY],
        "analysis": analysis,
        "meta": (sal.get("meta") or {"owner": "master", "note": "analysis 由每日 AI 解析步骤写入，fetcher 不覆盖"}),
    }

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    js = "window.BAIHECHOU_MACRO = " + body + ";\n"

    if args.dry:
        log("--dry：不写文件。预览如下：")
        print(json.dumps(payload, ensure_ascii=False, indent=1)[:2500])
        return 0

    os.makedirs(os.path.dirname(OUT_JS), exist_ok=True)
    os.makedirs(os.path.dirname(RAW_JSON), exist_ok=True)
    # 二进制写 + LF：避免 Windows 下 open('w') 把 \n 变 \r\n 造成整文件改写
    with open(OUT_JS, "wb") as f:
        f.write(js.encode("utf-8"))
    with open(RAW_JSON, "wb") as f:
        f.write(json.dumps({"update_time": now_s, "posts": pool},
                           ensure_ascii=False, indent=1).encode("utf-8"))

    log(f"✅ 已写 {os.path.relpath(OUT_JS, BASE)}（{len(js.encode('utf-8'))} 字节）")
    log(f"   最新主帖：{(latest_main or {}).get('time') or '—'}  停更 {stale_days} 天")
    log("   analysis 字段：" + ("保留既有解析" if analysis else "暂无（待 AI 解析步骤写入）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
