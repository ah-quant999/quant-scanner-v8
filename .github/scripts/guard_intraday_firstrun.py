#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 盘中链首跑探活（P1 护栏 · 2026-09-18 主人令）

════════════════════════════════════════════════════════════════════════
为什么需要它（2026-09-18 事故全貌 · 全部为实测取证）
════════════════════════════════════════════════════════════════════════
事故：09:2x 主人反馈「开盘了，实时数据还都是旧数据」。

【第一层】三条盘中链今日 run 数 = 0
    v8_intraday_snapshot.yml           cron '*/10 1-7 * * 1-5'
    v8_algo_intraday_lite.yml          cron '0 1,3,5,7 * * 1-5'
    v8_cn_fetch_intraday_lemoncat.yml  cron 14 条定点

【第二层】不是 cron 配置错、不是 runner 离线 —— 是 GitHub schedule 大面积哑火
    全仓今日 event 分布（实测）：
      dynamic 84 / workflow_dispatch 34 / push 16 / workflow_run 13 / schedule **仅 3**
    今日 schedule 明细仅三条：
      01:55 v8_risk_gauge / 01:29 v8_cache_buster_reconcile / 00:45 v8_health_patrol
    ⇒ 其余全部 schedule 类 workflow 今天一次没派发。

【第三层】现有两套守卫为何没拦住（关键教训）
    · v8_cn_fetch_watchdog.yml  只有 schedule('7,22,37,52 0-7 * * 1-5')
      ⇒ 今日 run=0，**自身随 schedule 一起哑火**
    · v8_health_patrol.yml      schedule 部分哑火，仅靠 workflow_run 跑了 5 次
    ⇒ 教训：**任何以 schedule 为唯一入口的守卫，都会在 schedule 哑火时一起哑。**

【第四层】为什么「数据陈旧度」判据也不够
    今日 10:58 实测 HEALTH_CHECK：盘中卡全部 ok
      SECTOR_FUND_FLOW_INTRADAY age=1.6min / INDEX_QUOTES 7.4min / LIMIT_UP_HEATMAP 4.5min
    但这些是 **cn_fetch_intraday_lemoncat（14 档定点）+ cn_fetch_cloud** 喂的，
    与 v8_intraday_snapshot 是否跑无关。
    ⇒ 若只看「数据陈旧」，当某链长期低频时数据仍可能看起来「没陈旧」（双盲区形态）；
      只看「run 数」又会在「该链本就低频、但数据由他链覆盖」时误报。
    ⇒ **必须双判**：run 数（链路活性）+ 产物新鲜度（结果正确性），且每链绑定它真正负责的产物。

【第五层】长期隐患（本次连带发现）
    v8_intraday_snapshot 全历史 run 仅 12 条，**每天固定只跑 2 次**（UTC 05:xx / 10:xx），
    而非 `*/10` 应有的每天 42 次 ⇒ GitHub 对高频 cron 存在**节流/降频**。
    该链负责的产物 SECTOR_FUND_FLOW_INTRADAY.js 目前由他链兜底覆盖，故未显故障，
    但属**隐性单点**，已记入交接档待评估。

════════════════════════════════════════════════════════════════════════
本护栏设计（逐条对齐上面五层）
════════════════════════════════════════════════════════════════════════
1. **不新建 schedule workflow**：搭车 v8_build_deploy.yml 的 build job
   （由 push / workflow_run / workflow_dispatch 三路驱动，09-18 实测三路全通）⇒ 绕开 schedule 失效。
2. **双判据**：每链 = (今日 run 数 ≥ 1) AND (其绑定产物 age ≤ 阈值)。
   两者任一不满足且已过判定时刻 ⇒ 告警。
3. **首档时间意识**：每链设 due_min，未到不判（防误报）。
4. **防雪崩**：每日每链最多自动补派 1 次（锁文件）。
5. **只读优先 + 永不阻断**：任何异常一律 exit 0，绝不阻断 build_deploy 主流程。

用法：
    python .github/scripts/guard_intraday_firstrun.py             # 只判定+报告
    python .github/scripts/guard_intraday_firstrun.py --dispatch  # 判定+自动补派
环境：
    GITHUB_TOKEN / V8_GITHUB_TOKEN / GH_TOKEN（--dispatch 需 actions:write）
    GITHUB_REPOSITORY（云端自动注入）

════════════════════════════════════════════════════════════════════════
上线挂载点（2026-09-18 v8_build_deploy.yml）
════════════════════════════════════════════════════════════════════════
本脚本挂在 `v8_build_deploy.yml` 的 **独立 job `intraday_patrol`**，而非 build job。

🔴 为什么必须是独立 job（关键，勿改回 build）：
    build job 的 if 含 `needs.gate.outputs.trading != 'true'`
    ⇒ **交易时段 build job 整体 skipped**。
    而本探活的使命恰恰是「盘中 09:15-15:05 检查盘中链是否派发」
    ⇒ 若挂在 build 里，盘中必然不执行 = 形同虚设（等于又造一个双盲区）。

    故新 job 条件与之互补：
        if: needs.gate.outputs.trading == 'true'      # 只在盘中跑
    build job  跑「非盘中」，intraday_patrol 跑「盘中」，两者恰好覆盖全时段。

触发：由 push / workflow_run / workflow_dispatch 三路带起（绕开 schedule 哑火）。
永不阻断：任何异常都 exit 0；调用处亦加 `|| true`。
"""
import json
import os
import sys
import http.client
import datetime
import urllib.request
import urllib.error

REPO = os.environ.get("GITHUB_REPOSITORY", "ah-quant999/quant-scanner-v8")
API = "https://api.github.com/repos/" + REPO
RAW = "https://raw.githubusercontent.com/" + REPO + "/main/"
# 🔴 2026-09-18 v6：锁文件**不落仓**。
#   原因：data/.workbuddy/** 在 v8_build_deploy.yml 的 push.paths 白名单里，
#   写锁 = 触发一次 push → 触发 build_deploy → 再跑本探活 → 再写锁 …… 自激循环。
#   改为落在 runner 临时目录（云端 $RUNNER_TEMP / 本地 tempfile.gettempdir()），
#   跨 step 不共享也无所谓：同日重跑顶多多补派一次，有每链每日 1 次的键控兜底。
def _lock_path():
    base = os.environ.get("RUNNER_TEMP") or os.environ.get("TEMP") or "/tmp"
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        base = "."
    return os.path.join(base, "v8_intraday_firstrun_lock.json")


LOCK_PATH = _lock_path()
CST = datetime.timezone(datetime.timedelta(hours=8))

# ── 三条盘中链：各绑定「它真正负责的产物」+ 判定时刻 + 新鲜度阈值(分钟)
CHAINS = [
    {
        "wf": "v8_cn_fetch_intraday_lemoncat.yml",
        "name": "盘中准点档调度器(14 档)",
        "cron_desc": "09:40 起每 20 分共 14 档",
        "due_min": 9 * 60 + 55,        # 09:40 首档 + 15min 容差
        "gate_mode": "intraday",       # 盘中 14 档定点，应有持续 run
        "artifacts": ["data/INDEX_QUOTES.js", "data/LIMIT_UP_HEATMAP.js"],
        "max_age": 45,
    },
    {
        "wf": "v8_algo_intraday_lite.yml",
        "name": "盘中算法追踪(轻量)",
        "cron_desc": "09:00 / 11:00 / 13:00 / 15:00",
        # 🔴 2026-09-18 实测修正（v4）：本链 algo_track_lite job 有硬闸门
        #     if: needs.gate.outputs.trading != 'true'
        #     gate 判 trading=09:25-11:30/13:00-14:59 ⇒ **盘中永不执行**，
        #     只放行 09:00 盘前 / 15:00 盘后两档。
        #     实测 #178（09-18 09:56 dispatch）→ job=skipped，run 顶层却 conclusion=success。
        #     ⇒ 本链必须用 morning_only：只在 09:05-09:25 判定「09:00 档是否派发」，
        #       过窗后不再用产物陈旧度误伤（否则盘中每轮都误报）。
        "gate_mode": "morning_only",
        "due_min": 9 * 60 + 5,         # 09:00 档 + 5min：此时刻只可能有 09:00 档
        "due_max": 9 * 60 + 25,        # 超过 09:25 即出窗（其后 trading 闸门接管）
        "artifacts": ["data/ALGO_TRACK.js"],
        "max_age": 150,
    },
    {
        "wf": "v8_intraday_snapshot.yml",
        "name": "板块资金日内快照",
        "cron_desc": "每 10 分（09:00-15:50）",
        "due_min": 10 * 60 + 30,       # ⚠ 该链实测被 GitHub 降频（每天仅 2 次），
                                       #   故判定时刻压到 10:30，避免早盘误报
        "gate_mode": "intraday",
        "artifacts": ["data/SECTOR_FUND_FLOW_INTRADAY.js"],
        "max_age": 60,
        "throttled": True,             # 标记：已知被降频，告警文案不同
    },
]

WIN_START = 9 * 60 + 15
WIN_END = 15 * 60 + 5


def _token():
    for k in ("V8_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip()
    try:
        import ctypes
        import ctypes.wintypes as wt

        class CREDENTIAL(ctypes.Structure):
            _fields_ = [
                ("Flags", wt.DWORD), ("Type", wt.DWORD),
                ("TargetName", wt.LPWSTR), ("Comment", wt.LPWSTR),
                ("LastWritten", wt.FILETIME), ("CredentialBlobSize", wt.DWORD),
                ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
                ("Persist", wt.DWORD), ("AttributeCount", wt.DWORD),
                ("Attributes", ctypes.c_void_p), ("TargetAlias", wt.LPWSTR),
                ("UserName", wt.LPWSTR),
            ]

        pc = ctypes.POINTER(CREDENTIAL)()
        if ctypes.windll.advapi32.CredReadW("git:https://github.com", 1, 0, ctypes.byref(pc)):
            c = pc.contents
            blob = ctypes.string_at(c.CredentialBlob, c.CredentialBlobSize)
            ctypes.windll.advapi32.CredFree(pc)
            return blob.decode("utf-16-le").strip()
    except Exception:
        pass
    return None


def _read_all(resp, tries=4):
    """稳健读取响应体：抵御跨境半程截断 IncompleteRead。

    🔴 2026-09-18 实测：取 runs?per_page=30（1.26MB）时命中
        http.client.IncompleteRead(1268304 bytes read, 50669 more expected)
    与 v8-tree-recursive-truncation skill 同族（HTTP 侧）。
    这里做「重试 + 累计拼接」：IncompleteRead.partial 是已收到的部分，
    续读下一段拼上去，直到拿全或放弃。
    """
    buf = b""
    for _ in range(tries):
        try:
            buf += resp.read()
            return buf
        except http.client.IncompleteRead as e:
            got = getattr(e, "partial", b"") or b""
            buf += got
            if not got:
                break
        except Exception:
            break
    return buf


def _get_json(url, tok, timeout=45, _attempt=0):
    r = urllib.request.Request(url, headers={"User-Agent": "v8-firstrun-guard",
                                            "Accept": "application/vnd.github+json"})
    if tok:
        r.add_header("Authorization", "Bearer " + tok)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            body = _read_all(resp)
        return json.loads(body.decode("utf-8"))
    except Exception as e:
        # 截断/网络抖动 ⇒ 退避重试一次（只重试一次，避免长跑）
        if _attempt < 1:
            import time as _t
            _t.sleep(2)
            return _get_json(url, tok, timeout=timeout, _attempt=_attempt + 1)
        raise


def _post(url, tok, payload):
    data = json.dumps(payload).encode("utf-8")
    r = urllib.request.Request(url, data=data, method="POST",
                               headers={"User-Agent": "v8-firstrun-guard",
                                        "Accept": "application/vnd.github+json",
                                        "Content-Type": "application/json"})
    if tok:
        r.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(r, timeout=45) as resp:
        return resp.status


def today_runs(wf, today, tok):
    """返回 (今日 run 数, 最新 created_at, 其中被 skip 的 run 数)。

    第三项用于识别**假成功**：run 顶层 conclusion=success，但主 job 因
    闸门 skipped（实测 v8_algo_intraday_lite #178）。
    """
    n = 0
    n_skip = 0
    latest = ""
    seen = []
    for pg in range(1, 4):
        try:
            d = _get_json("%s/actions/workflows/%s/runs?per_page=30&page=%d" % (API, wf, pg), tok)
        except urllib.error.HTTPError as e:
            return None, "HTTP %s" % e.code, 0
        except Exception as e:
            return None, str(e), 0
        runs = d.get("workflow_runs", [])
        if not runs:
            break
        hit_today = False
        for r in runs:
            ca = r.get("created_at", "")
            if ca.startswith(today):
                hit_today = True
                n += 1
                seen.append(r.get("id"))
                if not latest or ca > latest:
                    latest = ca
        if not hit_today and seen:
            break
    # skip 判定只对「今日的 run」做，最多查 3 个，避免 API 过量
    for rid in seen[:3]:
        try:
            j = _get_json("%s/actions/runs/%s/jobs" % (API, rid), tok)
            jobs = j.get("jobs", [])
            # 🔴 v5 修正：v4 用 all(...) 对**全部** job 判定，而 gate job 恒 success
            #   ⇒ all() 恒 False ⇒ 永远 skip=0（实测 #178 gate=success +
            #   algo_track_lite=skipped 被漏判）。
            #   修法：只看「实际工作 job」（名字非 gate/不变），全 skipped 才算 skip。
            work = [x for x in jobs if (x.get("name") or "").lower() not in ("gate",)]
            if work and all(x.get("conclusion") == "skipped" for x in work):
                n_skip += 1
        except Exception:
            pass
    return n, latest, n_skip


def artifact_age(path, now):
    """返回 (age_minutes, update_time_str, err)。用 raw 直取（带时间戳防缓存）。"""
    url = RAW + path.lstrip("/") + "?nc=%d" % int(now.timestamp())
    try:
        r = urllib.request.Request(url, headers={"User-Agent": "v8-firstrun-guard",
                                                "Cache-Control": "no-cache"})
        with urllib.request.urlopen(r, timeout=45) as resp:
            t = resp.read().decode("utf-8", "replace")
    except Exception as e:
        return None, "", str(e)

    # 产物形如 window.X = {... "update_time":"2026-09-18 10:53:12" ...}
    import re
    m = re.search(r'"update_time"\s*:\s*"([^"]+)"', t)
    if not m:
        m = re.search(r'"republish_time"\s*:\s*"([^"]+)"', t)
    if not m:
        return None, "", "no update_time field"
    s = m.group(1).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(s, fmt).replace(tzinfo=CST)
            return (now - dt).total_seconds() / 60.0, s, None
        except ValueError:
            continue
    return None, s, "unparsable: " + s


def _load_lock():
    try:
        with open(LOCK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_lock(d):
    try:
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        with open(LOCK_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        return True
    except Exception:
        return False


def self_test():
    """不触网的状态机冒烟：验证「三态 × gate_mode」判定矩阵无逻辑倒挂。"""
    print("=" * 72)
    print("[首跑探活] --self-test 状态机冒烟（不触网）")
    print("=" * 72)
    cases = [
        # (mode, due, out_win, n, n_skip, age, max_age, 期望 state)
        ("intraday",     True,  False, 1, 0, 5,    45,  "OK"),      # 正常
        ("intraday",     True,  False, 0, 0, 5,    45,  "WARN"),    # 零 run 但产物新
        ("intraday",     True,  False, 0, 0, 900,  45,  "FAIL"),    # 零 run + 陈旧
        ("intraday",     True,  False, 1, 1, 900,  45,  "FAIL"),    # 全 skip + 陈旧
        ("intraday",     True,  False, 1, 0, None, 45,  "OK"),      # 产物不可读，不误报
        ("intraday",     False, False, 0, 0, 900,  45,  "WAIT"),    # 未到判定时刻
        ("morning_only", True,  True,  1, 1, 900,  150, "INFO"),    # 出窗 + 被闸门 skip
        ("morning_only", True,  True,  0, 0, 900,  150, "FAIL"),    # 出窗 + 零派发
    ]
    bad = 0
    for mode, due, out_win, n, n_skip, age, mx, exp in cases:
        # 复刻 main 的判定链
        fresh = "UNKNOWN" if age is None else ("FRESH" if age <= mx else "STALE")
        n_eff = None if n is None else max(0, n - n_skip)
        n_ok = (n_eff is not None and n_eff >= 1)
        if mode == "morning_only" and out_win:
            state = ("OK" if n_eff >= 1 else "INFO") if (n is not None and n >= 1) else "FAIL"
        elif not due:
            state = "WAIT"
        elif n_ok and fresh != "STALE":
            state = "OK"
        elif n is not None and n_eff == 0 and fresh == "STALE":
            state = "FAIL"
        elif n is not None and n == 0 and fresh == "STALE":
            state = "FAIL"
        elif n is not None and n == 0 and fresh == "FRESH":
            state = "WARN"
        elif n is not None and n == 0 and fresh == "UNKNOWN":
            state = "WARN"
        elif fresh == "STALE":
            state = "WARN"
        else:
            state = "OK"
        ok = (state == exp)
        bad += 0 if ok else 1
        print("  %s mode=%-13s due=%-5s out=%-5s n=%s skip=%s age=%-5s → %-4s (期望 %s)"
              % ("PASS" if ok else "FAIL", mode, due, out_win, n, n_skip,
                 "None" if age is None else age, state, exp))
    print()
    if bad:
        print("[首跑探活] ❌ 自检 %d 例倒挂" % bad)
        return 2
    print("[首跑探活] ✅ 自检 %d/%d 全通" % (len(cases), len(cases)))
    return 0


def main():
    do_dispatch = "--dispatch" in sys.argv
    now = datetime.datetime.now(CST)
    today = now.strftime("%Y-%m-%d")
    hhmm = now.hour * 60 + now.minute
    dow = now.weekday()

    print("=" * 72)
    print("[首跑探活] CST=%s  周%d" % (now.strftime("%Y-%m-%d %H:%M:%S"), dow))
    print("=" * 72)

    if dow >= 5:
        print("[首跑探活] 非交易日，跳过")
        return 0
    if not (WIN_START <= hhmm <= WIN_END):
        print("[首跑探活] 不在盘中窗口(%d-%d)，跳过" % (WIN_START, WIN_END))
        return 0

    tok = _token()
    if not tok:
        print("[首跑探活] ⚠ 无可用 token（仍可判定，但无法自动补派）")
    print()

    lock = _load_lock()
    if lock.get("date") != today:
        lock = {"date": today, "dispatched": {}}

    problems = []
    for ch in CHAINS:
        wf = ch["wf"]
        n, latest, n_skip = today_runs(wf, today, tok)
        mode = ch.get("gate_mode", "intraday")
        due_min = ch["due_min"]
        due_max = ch.get("due_max")          # 仅 morning_only 有
        due = hhmm >= due_min
        out_of_window = (due_max is not None and hhmm > due_max)

        # 产物新鲜度（取该链绑定的第一个产物作代表）—— 三态，不再用 bool
        art = ch["artifacts"][0]
        age, ats, aerr = artifact_age(art, now)

        # 三态：FRESH / STALE / UNKNOWN
        #   UNKNOWN == 抓取失败或无 update_time —— 这是「不知道」，不是「陈旧」，
        #   绝不能与 STALE 合并（v2 缺陷：跨境 raw 抓取超时被误报成陈旧）。
        if age is None:
            fresh = "UNKNOWN"
        elif age <= ch["max_age"]:
            fresh = "FRESH"
        else:
            fresh = "STALE"

        n_eff = None if n is None else max(0, n - n_skip)   # 有效 run（排除整 job skipped 的假成功）
        n_ok = (n_eff is not None and n_eff >= 1)

        # ── morning_only 链：过了判定窗就退化为「今日是否派发过（含被闸门 skip）」
        if mode == "morning_only" and out_of_window:
            if n is not None and n >= 1:
                # 今日已派发过（哪怕本次被 trading 闸门 skip，也算「09:00 档已存在」）
                state = "OK" if n_eff >= 1 else "INFO"
                print("  [%-4s] %-36s run=%s(skip=%s)  产物 %s %s   (morning_only·已出窗)" % (
                    state, wf, n, n_skip, art.split("/")[-1],
                    fresh if fresh == "UNKNOWN" else ("%s(%.1fmin)" % (fresh, age))))
                if state == "INFO":
                    print("           ℹ 今日 %d 次 run 全被 trading 闸门 skip（预期：盘中不跑本链）" % n_skip)
                continue
            # 今日一次都没派发 ⇒ 这才是真问题（09:00 档丢了）
            state = "FAIL"
            problems.append((ch, "今日零派发（09:00 档丢失；产物 %s）" %
                             ("不可读" if fresh == "UNKNOWN" else "%.1fmin" % age)))
            print("  [%-4s] %-36s run=0  产物 %s %s   (morning_only)" % (
                state, wf, art.split("/")[-1],
                fresh if fresh == "UNKNOWN" else ("%s(%.1fmin)" % (fresh, age))))
            continue

        if not due:
            state = "WAIT"
        elif n_ok and fresh != "STALE":
            # run 有 + 产物不陈旧（FRESH 或 UNKNOWN）⇒ 链路活着，不告警
            state = "OK"
        elif n is not None and n_eff == 0 and fresh == "STALE":
            state = "FAIL"      # 链路断 + 产物确认陈旧 = 真故障
            problems.append((ch, "今日有效 run=0（%d 次全 skip）且产物陈旧 %.1fmin>%dmin"
                             % (n_skip, age, ch["max_age"])))
        elif n is not None and n == 0 and fresh == "STALE":
            state = "FAIL"
            problems.append((ch, "run=0 且产物陈旧 %.1fmin>%dmin" % (age, ch["max_age"])))
        elif n is not None and n == 0 and fresh == "FRESH":
            state = "WARN"      # 链路零 run 但产物还新鲜（他链兜底）
            problems.append((ch, "run=0（产物暂由他链兜底，%.1fmin）" % age))
        elif n is not None and n == 0 and fresh == "UNKNOWN":
            state = "WARN"      # 链路零 run 且产物不可读 ⇒ 值得留意，但不是确证故障
            problems.append((ch, "run=0 且产物不可读（%s）" % aerr))
        elif fresh == "STALE":
            state = "WARN"
            problems.append((ch, "产物陈旧 %.1fmin>%dmin" % (age, ch["max_age"])))
        else:
            state = "OK"        # run 数不可读 + 产物不陈旧 ⇒ 不误报

        print("  [%-4s] %-36s run=%s(skip=%s)  产物 %s %s" % (
            state, wf, ("?" if n is None else n), n_skip, art.split("/")[-1],
            fresh if fresh == "UNKNOWN" else ("%s(%.1fmin)" % (fresh, age))))
        if n is None:
            print("           ⚠ run 数不可读：%s" % latest)
        if fresh == "UNKNOWN":
            print("           ⚠ 产物不可读（抓取失败，非陈旧，不计入告警）：%s" % aerr)

    print()
    if not problems:
        print("[首跑探活] ✅ 全部盘中链活性与产物新鲜度均正常")
        _save_lock(lock)
        return 0

    print("[首跑探活] ⚠ 命中 %d 项：" % len(problems))
    for ch, why in problems:
        tag = "（⚠ 该链已知被 GitHub 降频）" if ch.get("throttled") else ""
        print("     · %-36s %s%s" % (ch["wf"], why, tag))
    print()
    print("  根因梯队：① cron 配置错 ② runner 离线 ③ GitHub schedule 未派发 ④ 高频 cron 被降频")
    print("  09-18 实证：全仓当日 schedule 仅 3 次（push=16 / workflow_run=13）⇒ 命中 ③/④")

    if not do_dispatch:
        print()
        print("  （未带 --dispatch，仅报告）")
        _save_lock(lock)
        return 0
    if not tok:
        print("  ⚠ 无 token，无法补派")
        _save_lock(lock)
        return 0

    print()
    print("[首跑探活] 自动补派（每链每日最多 1 次）：")
    done = dict(lock.get("dispatched", {}))
    fired = 0
    for ch, _why in problems:
        wf = ch["wf"]
        # 🛡 morning_only 链出窗后不补派：此时 trading 闸门必 skip ⇒ 纯浪费配额
        if ch.get("gate_mode") == "morning_only":
            dm = ch.get("due_max")
            if dm is not None and hhmm > dm:
                print("     ⏭ %s 已出 %02d:%02d 判定窗，补派必被 trading 闸门 skip ⇒ 跳过"
                      % (wf, dm // 60, dm % 60))
                continue
        if done.get(wf):
            print("     ⏭ %s 今日已补派（%s）" % (wf, done[wf]))
            continue
        try:
            st = _post("%s/actions/workflows/%s/dispatches" % (API, wf), tok, {"ref": "main"})
            ok = st in (204, 201, 200)
            print("     %s %s → HTTP %s" % ("✅" if ok else "⚠", wf, st))
            if ok:
                done[wf] = now.strftime("%H:%M:%S")
                fired += 1
        except urllib.error.HTTPError as e:
            print("     ❌ %s → HTTP %s %s" % (wf, e.code, e.read().decode("utf-8", "replace")[:150]))
        except Exception as e:
            print("     ❌ %s → %s" % (wf, e))

    lock["dispatched"] = done
    lock["last_run"] = now.strftime("%Y-%m-%d %H:%M:%S")
    _save_lock(lock)
    print()
    print("[首跑探活] 本轮补派 %d 条链；锁文件 %s（本路径不在 build_deploy 关注列表，不会引发重建）"
          % (fired, LOCK_PATH))
    return 0


if __name__ == "__main__":
    try:
        if "--self-test" in sys.argv:
            sys.exit(self_test())
        sys.exit(main())
    except Exception as e:
        print("[首跑探活] ⚠ 自身异常（已忽略，不影响部署）: %s" % e)
        sys.exit(0)
