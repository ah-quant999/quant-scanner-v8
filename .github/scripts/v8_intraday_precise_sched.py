# -*- coding: utf-8 -*-
"""
盘中精准调度器（2026-11-19 根治 GitHub schedule 日间失灵）
背景：GitHub schedule 在本仓连续多日日间不投递/延迟数小时（11-16~11-19 实测：
  盘中档全部缺席，积压到 16:00 后/午夜集中补投 → 守卫判窗外空转，09:30 首档
  连续缺席）。而 workflow_dispatch 事件不经 schedule 队列、秒级投递（实测）。
方案：低峰分钟注册少量 entry cron（互相 dedupe，任一落地即接管），实例内部用
  本机时钟精准对时逐档 dispatch 三条盘中链。三重保险：
  ① 实例 dedupe：已有实例在跑 → 让位退出；
  ② 档位容差 7 分钟：深夜补投实例全部档位过期 → 空转退出；
  ③ 新鲜度兜底：目标链 >25min 无 run 即补派（限交易日窗口内）。
覆盖链：lemoncat 14档主链 / 实时报价 refresh（cn）/ 国债期货 futures_realtime（cn）
"""
import os, sys, time, json, datetime, urllib.request

TOK = os.environ["GITHUB_TOKEN"]
REPO = os.environ["REPO"]
ME = os.environ.get("GITHUB_RUN_ID", "")
PHASE = os.environ.get("PHASE", "auto")
BJ = datetime.timezone(datetime.timedelta(hours=8))
API = "https://api.github.com/repos/" + REPO + "/actions/workflows/"

TARGETS = {
    "v8_cn_fetch_intraday_lemoncat.yml": {
        "slots": ["09:32", "09:42", "10:02", "10:22", "10:42", "11:02", "11:22",
                  "11:42", "13:02", "13:22", "13:42", "14:02", "14:22", "14:42", "15:02"],
        "fresh_window": ("09:32", "15:05"), "fresh_thresh": 25},
    "v8_stock_quote_refresh.yml": {
        "slots": [f"{h:02d}:{m}" for h in range(9, 17) for m in ("02", "32")],
        "fresh_window": ("09:05", "16:30"), "fresh_thresh": 25},
    "v8_futures_realtime.yml": {
        "slots": [f"{h:02d}:{m}" for h in range(9, 16) for m in ("02", "17", "32", "47")] + ["16:02"],
        "fresh_window": ("09:05", "15:45"), "fresh_thresh": 25},
}
ENDS = {"morning": "14:45", "afternoon": "16:38"}
SLOT_TOL_MIN = 7      # 迟到超过此值放弃该档（深夜补投实例自灭）
DEDUPE_SEC = 300      # 目标链 5 分钟内已有 run → 视为已覆盖
FRESH_EVERY_SEC = 300 # 新鲜度兜底检查间隔
SELF_WF = "v8_intraday_precise_sched.yml"


def req(url, method="GET", payload=None):
    r = urllib.request.Request(url, method=method,
        data=json.dumps(payload).encode() if payload else None,
        headers={"Authorization": "Bearer " + TOK, "Accept": "application/vnd.github+json",
                 "User-Agent": "v8-precise-sched", "Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=45) as resp:
        body = resp.read()
    return resp.status, (json.loads(body) if body else None)


def dispatch(wf):
    try:
        st, _ = req(API + wf + "/dispatches", "POST", {"ref": "main"})
        return st == 204
    except Exception as e:
        print(f"  dispatch {wf} ERR {e}", flush=True)
        return False


def last_start(wf):
    try:
        st, data = req(API + wf + "/runs?per_page=1")
        runs = data.get("workflow_runs") or []
        if not runs:
            return None
        s = runs[0]["run_started_at"].replace("Z", "")
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=datetime.timezone.utc).astimezone(BJ)
    except Exception:
        return None


def hm(t):
    return t.strftime("%H:%M")


def main():
    if PHASE == "auto":
        phase = "morning" if datetime.datetime.now(datetime.timezone.utc).hour <= 5 else "afternoon"
    else:
        phase = PHASE
    end = ENDS[phase]
    print(f"phase={phase} end={end} BJ_now={hm(datetime.datetime.now(BJ))}", flush=True)

    # ① 实例 dedupe：已有别的实例排队/在跑 → 最多等 25 分钟，仍活则让位退出
    for _ in range(50):
        try:
            st, data = req(API + SELF_WF + "/runs?per_page=8")
            active = [r for r in data.get("workflow_runs", [])
                      if str(r["id"]) != ME and r["status"] in ("queued", "in_progress")]
            if not active:
                break
            print(f"  另一实例在跑(run {active[0]['id']})，等待让位…", flush=True)
        except Exception as e:
            print(f"  dedupe probe ERR {e}", flush=True)
            break
        time.sleep(30)
    else:
        print("让位退出：已有实例覆盖", flush=True)
        return

    fired = set()
    start = datetime.datetime.now(BJ)
    last_fresh = 0.0
    while True:
        t = datetime.datetime.now(BJ)
        if hm(t) >= end or t.date() != start.date():
            break
        tm = hm(t)
        cache = {}
        for wf, cfg in TARGETS.items():
            for s in cfg["slots"]:
                key = (wf, s)
                if key in fired or tm < s:
                    continue
                sd = datetime.datetime.strptime(f"{t.date()} {s}", "%Y-%m-%d %H:%M").replace(tzinfo=BJ)
                late_min = (t - sd).total_seconds() / 60
                if late_min > SLOT_TOL_MIN:      # ② 迟到过久 → 放弃（深夜补投自灭）
                    fired.add(key)
                    continue
                if wf not in cache:
                    cache[wf] = last_start(wf)
                ls = cache[wf]
                if ls and (t - ls).total_seconds() < DEDUPE_SEC:
                    fired.add(key)               # 5 分钟内刚跑过 = 已覆盖
                    continue
                if dispatch(wf):
                    fired.add(key)
                    print(f"[{tm}] dispatch {wf} slot={s}", flush=True)
        # ③ 新鲜度兜底（限交易日窗口内；>25min 无 run 即补派）
        if time.time() - last_fresh >= FRESH_EVERY_SEC:
            last_fresh = time.time()
            if t.weekday() < 5:
                for wf, cfg in TARGETS.items():
                    a, b = cfg["fresh_window"]
                    if not (a <= tm <= b):
                        continue
                    ls = cache.get(wf) or last_start(wf)
                    if ls is None:
                        continue
                    age = (t - ls).total_seconds() / 60
                    if cfg["fresh_thresh"] < age < 90:
                        if dispatch(wf):
                            print(f"[{tm}] fresh-rescue {wf} age={age:.0f}min", flush=True)
        time.sleep(20)
    print(f"done end={hm(datetime.datetime.now(BJ))}", flush=True)


if __name__ == "__main__":
    main()
