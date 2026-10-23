#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
intraday_first_batch_gate.py —— 「9:30 / 13:30 第一批盘中数据必须上线」守门

🔴 2026-10-22 主人令（实测血证）：
    「9点30和13点30必须第一批数据上线」——今天 9:30 档因 GitHub cron 未触发
    （lemoncat 调度器 0 次 schedule 事件）⇒ 主站板块资金/日内快照/涨停热力等
    整批停在昨日 20:33/昨日 15:03，主人 10:14 实锤「根本没新数据」。
    事后 10:16-10:26 靠人工 dispatch 才补上 ⇒ **cron 单点不可靠，必须守门**。

本脚本 = 准点守门（可在 WorkBuddy 本地 automation 触发，不依赖 GitHub cron）：
    1) 硬 HTTP 抓 GitHub Pages 主站 data/*.js 的 update_time（以主站实际吐出为准，不看 raw）
    2) 判定「第一批必需卡」是否全部 ≥ 当日 09:25（13:30 档则 ≥ 13:25）
    3) 不达标 → 调 GitHub API dispatch：重抓取(云端·hosted) + 板块资金日内快照 + STOCK_QUOTE 轻量刷新
    4) 复检（默认 3 轮 × 4 分钟），达标即绿
    5) 输出中文摘要（短，不刷屏）

用法：
    python scripts/intraday_first_batch_gate.py                # 自动判定档位（09:30 / 13:30）
    python scripts/intraday_first_batch_gate.py --slot 0930    # 强制 09:30 档判定
    python scripts/intraday_first_batch_gate.py --slot 1330    # 强制 13:30 档判定
    python scripts/intraday_first_batch_gate.py --check-only   # 只检查不派发
"""
import argparse
import datetime as dt
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = "https://ah-quant999.github.io/quant-scanner-v8/data"
API = "https://api.github.com/repos/ah-quant999/quant-scanner-v8"

# 第一批必需卡（缺一即判「第一批未上线」）
REQUIRED = [
    ("STOCK_QUOTE", "个股行情"),
    ("SECTOR_FUND_FLOW", "板块资金全量"),
    ("SECTOR_FUND_FLOW_INTRADAY", "板块资金日内快照"),
    ("LIMIT_UP_HEATMAP", "涨停热力"),
    ("MARKET_FUND_FLOW_DATA", "大盘资金流向"),
    ("CANDIDATE_QUOTES", "候选池行情"),
    ("AI_MARKET_BRIEF", "AI盘面速览"),
]
# 可选卡（陈旧只告警不判红）
OPTIONAL = [
    ("VALUATION_PERCENTILE", "估值分位"),
    ("CITIC_PE_THERMO", "中信PE温度计"),
    ("CITIC_PE_BACKTEST", "中信PE回测"),
    ("LHB_DATA", "龙虎榜"),
    ("MORNING_PLAN", "盘前预案"),
]

# 派发目标（workflow 文件名 → GitHub workflow 路径）
DISPATCH_WFS = [
    ".github/workflows/v8_cn_fetch_cloud_hosted.yml",   # 重抓取（板块资金/涨停/大盘/候选池…）
    ".github/workflows/v8_intraday_snapshot.yml",       # 板块资金日内快照
    ".github/workflows/v8_stock_quote_refresh.yml",     # 行情轻量刷新
]

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def _token():
    cands = [
        os.path.join(REPO, ".workbuddy", "v8_gh_token.txt"),
        r"E:\v8data\qs8-tmp\.workbuddy\v8_gh_token.txt",
    ]
    for p in cands:
        try:
            if os.path.exists(p):
                t = open(p, encoding="utf-8").read().strip()
                if t:
                    return t
        except Exception:
            pass
    return os.environ.get("GITHUB_TOKEN", "")


def now_cst():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Asia/Shanghai"))
    except Exception:
        return dt.datetime.now() + dt.timedelta(hours=8)


def fetch_update_time(var):
    """硬 HTTP 抓主站 data/<var>.js，取 update_time（缺失则试 gen_time / data_date）。"""
    url = "%s/%s.js" % (PAGES, var)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "v8-intraday-gate/1.0",
                                                   "Cache-Control": "no-cache"})
        raw = urllib.request.urlopen(req, timeout=25, context=CTX).read().decode("utf-8", "replace")
    except Exception as e:
        return None, "取数失败(%s)" % (type(e).__name__,)
    for key in ("update_time", "gen_time", "republish_time", "data_date"):
        m = re.search(r'"%s"\s*:\s*"([^"]+)"' % key, raw)
        if m:
            return m.group(1), None
    return None, "无时间戳字段"


def parse_ts(s):
    if not s:
        return None
    tz = now_cst().tzinfo
    s = s.strip().replace("/", "-")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s, fmt).replace(tzinfo=tz)
        except Exception:
            pass
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=tz)
    return None


def check(slot_cutoff):
    """返回 (是否全绿, 明细行列表)"""
    rows = []
    ok = True
    for var, label in REQUIRED:
        ts, err = fetch_update_time(var)
        t = parse_ts(ts)
        green = bool(t and t >= slot_cutoff)
        if not green:
            ok = False
        rows.append((green, var, label, ts or (err or "无"), slot_cutoff))
    return ok, rows


def optional_rows():
    out = []
    for var, label in OPTIONAL:
        ts, err = fetch_update_time(var)
        out.append((var, label, ts or (err or "无")))
    return out


def dispatch():
    tok = _token()
    if not tok:
        print("❌ 无 GitHub token，未派发（请检查 .workbuddy/v8_gh_token.txt）")
        return 0
    ok = 0
    for wf in DISPATCH_WFS:
        # workflow_id 只认裸文件名；带 .github/workflows/ 前缀必 404（2026-10-23 实测血证）
        url = "%s/actions/workflows/%s/dispatches" % (API, wf.rsplit("/", 1)[-1])
        body = json.dumps({"ref": "main"}).encode()
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Authorization": "token %s" % tok,
                                              "Accept": "application/vnd.github+json",
                                              "Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=30, context=CTX).read()
            print("  📤 已派发 %s" % os.path.basename(wf))
            ok += 1
        except urllib.error.HTTPError as e:
            print("  ⚠️ 派发失败 %s => HTTP %s" % (os.path.basename(wf), e.code))
        except Exception as e:
            print("  ⚠️ 派发异常 %s => %s" % (os.path.basename(wf), type(e).__name__))
        time.sleep(1.0)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", choices=["auto", "0930", "1330"], default="auto")
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--wait", type=int, default=240, help="复检间隔秒")
    args = ap.parse_args()

    n = now_cst()
    if args.slot == "auto":
        slot = "1330" if (n.hour, n.minute) >= (13, 25) else "0930"
    else:
        slot = args.slot
    if slot == "0930":
        cutoff = n.replace(hour=9, minute=30, second=0, microsecond=0)
    else:
        cutoff = n.replace(hour=13, minute=30, second=0, microsecond=0)
    if cutoff > n:
        cutoff = n  # 尚未到该档位 ⇒ 降级为「本档位尚未开始」，仅报告

    # 🔴 2026-10-23 主人令「盘中高频盯住·一劳永逸」：盘中时段判定线动态抬升。
    #   旧逻辑只认 09:30/13:30 档位线 ⇒ 10:32 跑守门时 10:0x 的数据也判「达标」，
    #   30+ 分钟陈旧数据漏网（10-23 上午实证：10:03-10:06 卡到 10:40 仍报✅）。
    #   盘中(交易日 09:30-11:30 / 13:00-15:00)时：判定线 = max(档位线, now-25分钟)，
    #   与 20 分钟哨兵节奏对齐；非盘中维持原档位线不变。
    def _is_trading_now(t):
        if t.weekday() >= 5:
            return False
        hm = (t.hour, t.minute)
        return ((9, 30) <= hm < (11, 30)) or ((13, 0) <= hm < (15, 0))
    if _is_trading_now(n):
        dyn = n - dt.timedelta(minutes=25)
        if dyn > cutoff:
            cutoff = dyn

    print("══ v8 第一批盘中数据守门 ══  %s  档位=%s 判定线=%s" % (
        n.strftime("%Y-%m-%d %H:%M:%S"), slot, cutoff.strftime("%H:%M")))

    for rnd in range(1, max(1, args.rounds) + 1):
        ok, rows = check(cutoff)
        print("── 第 %d 次检查 ──" % rnd)
        for green, var, label, ts, cut in rows:
            print("  %s %-26s %-16s %s" % ("✅" if green else "❌", var, label, ts))
        if ok:
            print("✅ 第一批全部达标（≥%s）→ 守门通过" % cutoff.strftime("%H:%M"))
            for var, label, ts in optional_rows():
                print("  · %-24s %-16s %s" % (var, label, ts))
            return 0
        if args.check_only:
            print("❌ 第一批未齐（--check-only，不派发）")
            for var, label, ts in optional_rows():
                print("  · %-24s %-16s %s" % (var, label, ts))
            return 2
        if rnd < args.rounds:
            print("  🚨 立即派发重抓取/快照/轻量刷新…")
            dispatch()
            print("  ⏳ 等待 %ds 后复检…" % args.wait)
            time.sleep(args.wait)
    print("❌ 守门未通过：%d 轮复检后第一批仍未齐" % args.rounds)
    return 3


if __name__ == "__main__":
    sys.exit(main())
