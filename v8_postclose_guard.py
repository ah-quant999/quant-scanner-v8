# -*- coding: utf-8 -*-
"""
九宝量化 v8.0 — 盘后数据守护脚本
================================
作用：检测 lemoncat-cn runner 是否离线 / 盘后关键数据是否陈旧，
      一旦发现缺失就自动 dispatch v8_cn_fetch 补救。

设计原则（落实主人「发现就马上修正」要求）：
- 幂等：只在「交易日 且 已过 15:30 CST 且 盘后数据非今日」时才 action；
- 自带 runner 离线检测，离线时只告警不空转；
- 不依赖本地 git，全走 GitHub REST API（本机仅 api.github.com 可达）。

用法：
  python v8_postclose_guard.py            # 真实补救模式
  python v8_postclose_guard.py --dry-run # 只检查不 dispatch（调试用）
"""
import json
import base64
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

TOKEN_FILE = r"E:/workspace/stock-scanner/.workbuddy/v8_gh_token.txt"
REPO = "ah-quant999/quant-scanner-v8"
API = "https://api.github.com"
CST = timezone(timedelta(hours=8))

# 盘后必须当日刷新的核心文件（update_time 应为今日）
POST_CLOSE_FILES = [
    "data/MARKET_FUND_FLOW_DATA.js",
    "data/EXPERIMENT.js",
    "raw_data/market_fund_flow_data.json",
]


def get_token():
    from pathlib import Path
    return Path(TOKEN_FILE).read_text(encoding="utf-8").strip()


def api_get(path):
    req = urllib.request.Request(
        API + path,
        headers={"Authorization": "token " + TOKEN,
                 "Accept": "application/vnd.github.v3+json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def api_post(path, data):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(data).encode("utf-8"),
        headers={"Authorization": "token " + TOKEN,
                 "Accept": "application/vnd.github.v3+json",
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def file_update_time(path):
    try:
        d = api_get(f"/repos/{REPO}/contents/{path}?ref=main")
        c = base64.b64decode(d["content"]).decode("utf-8", "ignore")
        m = re.search(r'"update_time"\s*:\s*"([^"]+)"', c)
        return m.group(1) if m else "NONE"
    except Exception as e:
        return f"ERR:{e}"


def runner_offline():
    try:
        runners = api_get(f"/repos/{REPO}/actions/runners")
        return [r["name"] for r in runners.get("runners", []) if not r.get("online")]
    except Exception as e:
        return [f"query_failed:{e}"]


def dispatch(category):
    api_post(
        f"/repos/{REPO}/actions/workflows/v8_cn_fetch.yml/dispatches",
        {"ref": "main", "inputs": {"category": category}},
    )


def main():
    global TOKEN
    TOKEN = get_token()
    now = datetime.now(CST)
    today = now.strftime("%Y-%m-%d")
    dry = "--dry-run" in sys.argv
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')} CST] 盘后守护检查" + (" [DRY-RUN]" if dry else ""))

    if now.weekday() >= 5:
        print("  非交易日，跳过")
        return
    if now.hour < 15 or (now.hour == 15 and now.minute < 30):
        print("  未到 15:30 盘后窗口，跳过")
        return

    stale = []
    for f in POST_CLOSE_FILES:
        ut = file_update_time(f)
        print(f"  {f}: {ut}")
        if ut and not ut.startswith(today) and not ut.startswith("ERR"):
            stale.append(f)

    if not stale:
        print("  ✅ 盘后数据已是最新，无需补救")
        return

    off = runner_offline()
    if off:
        print(f"  ⚠️ runner 离线: {off} —— dispatch 会排队，请上机重启 runner 服务")

    if dry:
        print(f"  [DRY-RUN] 将 dispatch: post_close, intraday（{len(stale)} 个文件陈旧）")
        return

    for cat in ("post_close", "intraday"):
        try:
            dispatch(cat)
            print(f"  ✅ 已 dispatch v8_cn_fetch category={cat}")
        except Exception as e:
            print(f"  ❌ dispatch {cat} 失败: {e}")


if __name__ == "__main__":
    main()
