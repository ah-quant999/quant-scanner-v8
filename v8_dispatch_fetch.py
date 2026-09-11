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

# 🛡 2026-09-11 主人令「盘中安静窗」：交易时段两段必须给盘中更新让出通道与锁，
#   除盘中更新(intraday/intraday_lite)外，任何派发都不许占用盘中更新通道与 _DISPATCH_LOCK。
#     窗1：09:20 → 11:30（开盘前 10 分 ~ 上午收盘）—— 防非盘中风抓取顶掉盘中种子档 /
#                                               长期持有派发锁导致盘中刷新卡死
#     窗2：12:50 → 15:00（午后开盘前 10 分 ~ 下午收盘）
#   注：11:30-12:50 午间休市、15:00 后盘后、09:20 前盘前 均不限制（非盘中更新可正常跑）。
_QUIET_WINDOWS = [((9, 20), (11, 30)), ((12, 50), (15, 0))]
_INTRADAY_CATS = {"intraday", "intraday_lite"}

# 2026 A股交易日历（与 cloud_dispatcher.py / v8_health_check.py 一致；每年初需更新）
_HOLIDAYS_2026 = {
    "01-01", "01-02", "01-03",
    "02-15", "02-16", "02-17", "02-18", "02-19", "02-20", "02-21", "02-22", "02-23",
    "04-04", "04-05", "04-06",
    "05-01", "05-02", "05-03", "05-04", "05-05",
    "06-19", "06-20", "06-21",
    "09-25", "09-26", "09-27",
    "10-01", "10-02", "10-03", "10-04", "10-05", "10-06", "10-07",
}
_MAKEUP_DAYS_2026 = {
    "2026-01-04", "2026-02-14", "2026-02-28",
    "2026-05-09", "2026-09-20", "2026-10-10",
}


def _is_trading_day(dt):
    """给定 CST 时间是否为 A 股交易日（周末 + 节假日剔除，补班日算交易日）。"""
    d = dt.date()
    if d.weekday() >= 5 and d.isoformat() not in _MAKEUP_DAYS_2026:
        return False
    return d.strftime("%m-%d") not in _HOLIDAYS_2026


def in_trading_quiet_window(now=None):
    """当前是否处于「盘中安静窗」（交易日 + 09:20-11:30 / 12:50-15:00）。"""
    now = now or _now_cst()
    if not _is_trading_day(now):
        return False
    hhmm = (now.hour, now.minute)
    return any(o <= hhmm < c for (o, c) in _QUIET_WINDOWS)


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

    # 🛡 2026-09-11 主人令「盘中安静窗」守卫：交易时段 09:20-11:30 / 12:50-15:00 内，
    #   非盘中更新类派发一律 no-op，绝不占用盘中更新通道与 _DISPATCH_LOCK，给盘中更新让出通道。
    if category not in _INTRADAY_CATS and in_trading_quiet_window():
        now = _now_cst()
        print(f"⏰ 盘中安静窗守卫：当前 CST {now:%H:%M} 处于安静窗(09:20-11:30 / 12:50-15:00)，"
              f"非盘中类 category={category!r} 跳过派发（给盘中更新让出通道与锁）")
        return True  # no-op 视为成功

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
