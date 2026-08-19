#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_dispatch_fetch.py — 经 GitHub REST API 主动派发云端 workflow
（绕过 GitHub Actions 不可靠的 on.schedule 定时器，下午/收盘档常漏触发）

用法:
    python v8_dispatch_fetch.py                     # 默认 all（全量兜底）
    python v8_dispatch_fetch.py intraday            # cn_fetch 盘中刷新
    python v8_dispatch_fetch.py post_close          # cn_fetch 收盘数据 + 龙虎榜回填
    python v8_dispatch_fetch.py premarket           # cn_fetch 盘前
    python v8_dispatch_fetch.py intraday_lite       # ⏰ 盘中动量+算法追踪轻量重算（时间窗守卫 09:30-15:00 CST）

依赖: E:/workspace/quant-scanner-v8/.workbuddy/v8_gh_token.txt （OAuth token，不入库）

🛡 2026-08-19 一劳永逸+时间窗守卫：intraday_lite 与 BACKTEST 不可同日而语
    （BACKTEST 重，盘中跑会污染盘后权威产物；intraday_lite 轻量，是为盘中追踪入池而生）。
    派发前先判时间窗：09:30≤CST 时间≤15:00 才放行，超窗直接退出 0（no-op）,
    绝不让盘中误派替代 18:30 CST 的 v8_algo_cloud.yml（盘后算法权威生产者）。
"""
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

REPO = "ah-quant999/quant-scanner-v8"
# workflow_id 字典：category -> 该派哪个 workflow
WF_IDS = {
    "premarket":   324135267,  # v8_cn_fetch
    "intraday":    324135267,  # v8_cn_fetch
    "post_close":  324135267,  # v8_cn_fetch
    "all":         324135267,  # v8_cn_fetch
    "intraday_lite": None,     # ⛔ 动态解析一次（v8_algo_intraday_lite.yml）
}
WF_NAME_INTRADAY_LITE = "v8_algo_intraday_lite.yml"
TOKEN_PATH = "E:/workspace/quant-scanner-v8/.workbuddy/v8_gh_token.txt"
VALID = {"premarket", "intraday", "post_close", "all", "intraday_lite"}

# 盘中兜底时间窗（CST）— BACKTEST 重型仍 18:30 由 v8_algo_cloud.yml cron 跑
WINDOW_INTRADAY_LITE_OPEN = (9, 30)   # 09:30
WINDOW_INTRADAY_LITE_CLOSE = (15, 0)  # 15:00 收盘


def load_token():
    try:
        return open(TOKEN_PATH, encoding="utf-8").read().strip()
    except Exception as e:
        print(f"[FATAL] 读取 token 失败: {e}")
        sys.exit(1)


def _now_cst():
    return datetime.now(timezone(timedelta(hours=8)))


def resolve_wf_id(name):
    """通过文件名解析 workflow_id（避免硬编码漂移）"""
    token = load_token()
    # 注意：API path 用 workflows/{filename-without-yml}，GitHub 会自动匹配
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{name.replace('.yml','')}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
            return data.get("id")
    except Exception as e:
        print(f"[warn] 解析 workflow_id 失败（{name}）: {e}")
        return None


def dispatch(category):
    token = load_token()
    if category not in VALID:
        print(f"[FATAL] 非法 category={category!r}，可选: {sorted(VALID)}")
        sys.exit(1)

    # 🛡 2026-08-19 一劳永逸时间窗守卫：盘中兜底只在 09:30-15:00 CST 派发
    # 注：BACKTEST 重型仍 18:30 由 v8_algo_cloud.yml cron 跑，不受影响
    if category == "intraday_lite":
        now = _now_cst()
        hhmm = (now.hour, now.minute)
        if not (WINDOW_INTRADAY_LITE_OPEN <= hhmm <= WINDOW_INTRADAY_LITE_CLOSE):
            print(f"⏰ intraday_lite 时间窗守卫：当前 CST {hhmm[0]:02d}:{hhmm[1]:02d} 超出 09:30-15:00 窗口，跳过派发（盘中兜底不该顶替 18:30 CST 盘后链）")
            return True  # 视为成功（no-op）
        # 解析 workflow_id（首次缓存）
        global WF_IDS
        if WF_IDS["intraday_lite"] is None:
            wf_id = resolve_wf_id(WF_NAME_INTRADAY_LITE)
            if wf_id is None:
                print(f"[FATAL] 无法解析 {WF_NAME_INTRADAY_LITE} workflow_id")
                sys.exit(1)
            WF_IDS["intraday_lite"] = wf_id
        wf_id = WF_IDS["intraday_lite"]
        inputs = {}
    else:
        wf_id = WF_IDS[category]
        inputs = {"category": category}

    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{wf_id}/dispatches"
    data = json.dumps({"ref": "main", "inputs": inputs}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            now_str = _now_cst().strftime("%H:%M:%S")
            print(f"[{now_str}] ✅ 已派发 category={category} (HTTP {r.status})")
            return True
    except urllib.error.HTTPError as e:
        print(f"❌ 派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}")
        return False


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    cat = sys.argv[1] if len(sys.argv) > 1 else "all"
    ok = dispatch(cat)
    sys.exit(0 if ok else 1)
