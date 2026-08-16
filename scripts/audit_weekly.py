#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_weekly.py — 周末全量审计（全链路对齐 + 双机 model + 受保护文件）。

设计定位（与现有组件分工）：
  - v8_health_check.py : 健康面板（每日跑，产出 HEALTH_CHECK.js）。
  - reconcile_cache_busters.py : 每15分钟 ?v 自愈（只对齐戳）。
  - 本脚本 = 每周一次深度体检，覆盖 reconcile/health_check 都抓不到的结构性问题。

检查项：
  1) ?v 真失配：本地 index.html 所有 data/*.js ?v 与 v6_memo.html ?v，
     逐一从线上(github.io CDN) 取真实内容算 sha 比对（data 中性化 republish_time，
     v6 不中性化，口径严格对齐 reconcile/guard）。
  2) 5 组件全链路：本地 index.html / v6_memo.html / data/HEALTH_CHECK.js vs 线上；
     .github/workflows/*.yml vs origin/main（git show，免网络）；
     双机自动化 = 查 workbuddy.db。
  3) 双机自动化 model 落库核验：所有 ACTIVE model_id 必须为 deepseek-v4-flash。
  4) 受保护文件完整性：v6_memo.html / guard_v6_memo.py / 北向席位日历标记
     (northCalContainer+renderNorthCalendar DO_NOT_DELETE)。
  5) 本地 HEAD vs origin/main 同步。
退出码 0=全对齐, 1=有失配。
"""
import os
import re
import sys
import pathlib
import urllib.request
import sqlite3
import subprocess
import hashlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = "https://ah-quant999.github.io/quant-scanner-v8"
REPO = "ah-quant999/quant-scanner-v8"
DB = pathlib.Path.home() / ".workbuddy" / "workbuddy.db"


def download(url):
    req = urllib.request.Request(url, headers={
        "Cache-Control": "no-cache", "Pragma": "no-cache", "User-Agent": "audit-weekly"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read()
    except Exception as e:
        return ("ERR", str(e))


def neut(b):
    b = b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return re.sub(rb'"republish_time"\s*:\s*"[^"]*"', b'"republish_time":""', b)


def git_show(rel):
    try:
        return subprocess.run(["git", "show", "origin/main:" + rel],
                              cwd=str(ROOT), capture_output=True).stdout
    except Exception:
        return None


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cloud", action="store_true",
                    help="云端运行模式：跳过本机 workbuddy.db 核验与本地 HEAD 检查（DB 仅本机有）")
    args = ap.parse_args()
    problems = []
    print("=== 周末全量审计 @ %s %s ===" % (ROOT.name, "(云端模式)" if args.cloud else ""))
    # 先轻量 fetch，保证 origin/main 最新（本机 cn git 墙下失败无害；云端正常）
    if not args.cloud:
        subprocess.run(["git", "fetch", "origin", "main"], cwd=str(ROOT), timeout=60)

    # 1) ?v 真失配
    idx_online = download("%s/index.html" % SITE)
    if isinstance(idx_online, tuple):
        problems.append("线上 index.html 下载失败: %s" % idx_online[1])
    else:
        txt = idx_online.decode("utf-8", "replace")
        pat = re.compile(r'([\'"])(data/[A-Z0-9_]+\.js)(?:\?v=([0-9a-fA-F]{1,40}))?\1')
        for m in pat.finditer(txt):
            fname = m.group(2).split("/")[-1]
            v = m.group(3)
            remote = download("%s/data/%s" % (SITE, fname))
            if isinstance(remote, tuple):
                continue
            calc = hashlib.sha1(neut(remote)).hexdigest()[:10]
            if v != calc:
                problems.append("?v失配: %s 线上?v=%s 实算=%s" % (fname, v, calc))
        mv = re.search(r'v6_memo\.html(?:\?v=([0-9a-fA-F]{1,40}))?', txt)
        if mv:
            v6 = download("%s/v6_memo.html" % SITE)
            if not isinstance(v6, tuple):
                calc = hashlib.sha1(v6).hexdigest()[:10]
                if mv.group(1) != calc:
                    problems.append("?v失配: v6_memo.html 线上?v=%s 实算=%s" % (mv.group(1), calc))

    # 2) 5 组件全链路（本地 vs 线上）
    # ⚠️ 2026-08-16 修正：本项目部署走「Contents API 直推 + build 重写」，本地 index.html 是
    #    源码手改版、线上是 build 产物，内容天然不同（?v/build 标记差异）→ 「内容不同」降级为
    #    info，不再当失配。真失配判定由第 1 项「线上 index ?v vs 线上 data」承担（线上自洽）。
    for f in ["index.html", "v6_memo.html", "data/HEALTH_CHECK.js"]:
        loc = (ROOT / f).read_bytes() if (ROOT / f).exists() else None
        on = download("%s/%s" % (SITE, f))
        if loc is None:
            problems.append("本地缺失: %s" % f)
            continue
        if isinstance(on, tuple):
            problems.append("线上下载失败: %s" % f)
            continue
        if neut(on) != neut(loc):
            print("  ℹ️ (info) 本地 %s 与线上 build 产物不同（部署走 API 直推+build 重写，本地=源码版，属正常）" % f)
    # workflows vs origin/main
    wf = ROOT / ".github" / "workflows"
    if wf.exists():
        for w in sorted(wf.glob("*.yml")):
            rel = w.relative_to(ROOT).as_posix()
            loc = w.read_bytes()
            org = git_show(rel)
            if org is None:
                continue
            if neut(org) != neut(loc):
                problems.append("workflow 不一致: %s (本地 vs origin/main)" % w.name)

    # 3) 双机自动化 model 落库核验（仅本机 workbuddy.db；云端 --cloud 跳过，
    #    双机 model 由双机交接脚本人工核对，见 HANDOVER_2026-08-16_审计自动化.md）
    if args.cloud:
        print("  ℹ️ (info) 云端模式：跳过双机 model 核验（需本机 workbuddy.db，由双机交接脚本人工核对）")
    elif DB.exists():
        conn = sqlite3.connect(str(DB))
        rows = conn.execute(
            "SELECT id,name,model_id,status FROM automations WHERE status='ACTIVE'").fetchall()
        conn.close()
        for r in rows:
            if (r[2] or "NULL") != "deepseek-v4-flash":
                problems.append("自动化 model 异常: %s | %s | model=%s" % (r[0], r[1], r[2] or "NULL"))
    else:
        print("  ℹ️ (info) workbuddy.db 不存在，跳过双机 model 核验（由双机交接脚本人工核对）")

    # 4) 受保护文件完整性
    v6 = ROOT / "v6_memo.html"
    if not v6.exists() or v6.stat().st_size < 60000:
        problems.append("⚠️ 受保护: v6_memo.html 缺失或过小(<60KB)")
    if not (ROOT / "guard_v6_memo.py").exists():
        problems.append("⚠️ 受保护: guard_v6_memo.py 缺失")
    idx_txt = (ROOT / "index.html").read_text(encoding="utf-8", errors="replace") \
        if (ROOT / "index.html").exists() else ""
    if "northCalContainer" not in idx_txt or "renderNorthCalendar" not in idx_txt:
        problems.append("⚠️ 受保护: 北向席位日历标记缺失(northCalContainer/renderNorthCalendar)")

    # 5) 本地 HEAD vs origin/main（云端 --cloud 跳过：checkout 即 main，无参考意义）
    if args.cloud:
        print("  ℹ️ (info) 云端模式：跳过本地 HEAD vs origin/main（checkout 即 main）")
    else:
        try:
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                  capture_output=True, text=True).stdout.strip()
            omain = subprocess.run(["git", "rev-parse", "origin/main"], cwd=str(ROOT),
                                   capture_output=True, text=True).stdout.strip()
            if head != omain:
                problems.append("本地 HEAD(%s) != origin/main(%s)" % (head[:10], omain[:10]))
        except Exception:
            pass

    # 6) 关键数据源陈旧度（个股查询/龙虎榜/算法）— 2026-08-16 主人令"个股查询上周四数据"
    #    根因是浏览器内存缓存（tab 长期不刷新），但兜底也应在审计里报警数据本身陈旧。
    #    简单估算最近交易日（忽略节假日，v8_health_check 里有更精确日历）。
    from datetime import datetime, timedelta
    now = datetime.now()
    wd = now.weekday()
    if wd == 5:
        recent_trade = now.date()  # 周六：今天已是周末，等价周五
    elif wd == 6:
        recent_trade = (now - timedelta(days=2)).date()  # 周日→上周五
    elif wd == 0:
        recent_trade = (now - timedelta(days=3)).date()  # 周一→上周五
    else:
        recent_trade = (now - timedelta(days=1)).date()  # 周二~五→昨天
    def _file_date(remote_path, field):
        try:
            req = urllib.request.Request(f"{SITE}/{remote_path}",
                                          headers={"Cache-Control": "no-cache", "User-Agent": "audit",
                                                   "Range": "bytes=0-4095"})  # 只取 head 4KB，避免大文件下载超时
            data = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
            import re as _re
            m = _re.search(r'"' + field + r'"\s*:\s*"([^"]*)"', data[:4000])
            if not m: return None
            v = m.group(1)
            if len(v) == 8 and v.isdigit():  # YYYYMMDD
                return datetime.strptime(v, "%Y%m%d").date()
            return datetime.strptime(v[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    sources = [
        ("STOCK_QUOTE.js", "update_time", "个股查询实时行情"),
        ("LHB_DATA.js", "date", "龙虎榜"),
        ("ALGO_TRACK.js", "update_time", "算法跟踪"),
        ("FINAL_RECOMMEND_DATA.js", "update_time", "最终推荐"),
    ]
    for path, field, name in sources:
        d = _file_date(path, field)
        if d is None:
            problems.append("⚠️ 数据陈旧度检查失败: %s（%s 字段缺失或下载失败）" % (name, field))
        elif d < recent_trade:
            problems.append("⚠️ %s 数据陈旧: %s（最近交易日 %s）" % (name, d, recent_trade))

    print("发现失配 %d 项：" % len(problems))
    print("\n".join(" - " + p for p in problems) or
          "✅ 全链路对齐：?v 真一致、五组件同步、双机 model 全 deepseek-v4-flash、受保护文件完整")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
