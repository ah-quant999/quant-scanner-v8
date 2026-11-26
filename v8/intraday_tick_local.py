# -*- coding: utf-8 -*-
"""盘中本机 tick（小九机 · 零 Actions 依赖 · 一劳永逸）

为什么存在（2026-11-26 实测诊断）：
  GitHub Actions 侧盘中链路的三个硬伤，靠打补丁修不掉：
  ① schedule 在 746 run/日 的高压下基本不投递（11-26：86 条 cron → 仅 14 次 schedule run）；
  ② 每档 job 实测 26-73 分钟（push 步单个就 21.7 分钟，api_push_raw 逐文件下载远端 blob
     比对 + 逐文件 PUT，一个文件一个 commit），而档间隔 20 分钟 ⇒ 结构性重叠 ⇒
     并发组互杀（11-26：lemoncat 50 run 中 33 个 cancelled）⇒ 断更；
  ③ 接力式调度（20 分钟一实例，退出前 dispatch 下一班）是单点：11-26 11:53 实例到期后
     下一班没派出去，全链真空到 13:32（100 分钟），只能靠人工救。

本脚本在同机（LEMONCAT=CN 数据机，交易日 7:45-17:45 在线）直接执行：
  抓取（并发 6）→ 一次原子提交（Git Trees API，全站 1 个 commit）→ 推送 main。
实测一档 2-4 分钟（云端 26-73 分钟），10 分钟节拍不再重叠，且不经过任何并发组。

用法：
  python intraday_tick_local.py --once            # 正常 tick（窗口外静默退出）
  python intraday_tick_local.py --once --force    # 忽略交易时段窗口（补数据/验证）
  python intraday_tick_local.py --once --dry-run  # 只抓取与比对，不写远端
"""
import os, re, sys, json, time, hashlib, base64, ssl, subprocess, argparse, datetime
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")

REPO_DIR = r"E:/qs_workspaces/quant-scanner-v8"
REPO = "ah-quant999/quant-scanner-v8"
TOKEN_FILE = r"C:/Users/Administrator/.workbuddy/v8_gh_token.txt"
PYLIBS = r"E:/v8data/qs8-tmp/pylibs"
LOG_DIR = r"E:/v8data/v8_live"
LOG = os.path.join(LOG_DIR, "tick.log")
STATE = os.path.join(LOG_DIR, "tick_state.json")
CST = datetime.timezone(datetime.timedelta(hours=8))

# 盘中要刷的模块（cloud_fetch_v8.py --only 的变量名，与 data/<VAR>.js 同名）
VARS = [
    "INDEX_QUOTES", "SECTOR_FUND_FLOW", "CAPITAL_FLOW_DATA",
    "ETF_PULSE", "ETF_INTRADAY_HEAT", "CONCEPT_RANKING",
    "LIMIT_UP_HEATMAP", "LIMIT_UP_BROKEN", "SEVERE_SWING",
    "MARKET_ALERTS", "OVERSEAS_MARKETS", "SH_SZ_HISTORY",
    "AVG_PRICE_DATA", "MARKET_FUND_FLOW_DATA", "CANDIDATE_QUOTES",
]
MARKER = "raw_data/local_tick.json"   # 心跳标记，供云端链判断「本机已接管」
MIN_GAP_MIN = 6      # 距上次成功推送不足 N 分钟则跳过（防 schtasks 抖动重复跑）
FETCH_TIMEOUT = 260  # 单模块超时（秒）
MAX_WORKERS = 6


# ---------------------------------------------------------------- 基础工具
def now():
    return datetime.datetime.now(CST)


def log(msg):
    line = f"[{now().strftime('%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        if os.path.exists(LOG) and os.path.getsize(LOG) > 2_000_000:
            os.replace(LOG, LOG + ".1")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def in_window(dt):
    """交易日 09:25-15:05（CST）。周末直接跳过；法定节假日靠内容不变自动跳过推送。"""
    return dt.weekday() < 5 and ("09:25" <= dt.strftime("%H:%M") <= "15:05")


def load_token():
    with open(TOKEN_FILE, encoding="utf-8") as f:
        t = f.read().strip()
    if len(t) < 20:
        raise RuntimeError("token 文件异常")
    return t


TOK = None
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def api(method, path, payload=None, tries=4, timeout=60):
    url = "https://api.github.com" + path
    body = json.dumps(payload).encode() if payload is not None else None
    last = None
    for i in range(tries):
        try:
            r = urllib.request.Request(url, method=method, data=body, headers={
                "Authorization": "Bearer " + TOK,
                "Accept": "application/vnd.github+json",
                "User-Agent": "v8-local-tick",
                "Content-Type": "application/json",
            })
            with urllib.request.urlopen(r, timeout=timeout, context=CTX) as resp:
                raw = resp.read()
                return resp.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {e.read()[:200]!r}"
            if e.code in (409, 422):      # 并发写冲突 → 重读 tip 后重试
                time.sleep(1.5 + i * 2)
                continue
            if e.code == 401:
                raise RuntimeError("token 失效：" + last)
            time.sleep(1.5 + i * 2)
        except Exception as e:
            last = repr(e)[:160]
            time.sleep(1.5 + i * 2)
    raise RuntimeError(f"{method} {path} 失败 {tries} 次：{last}")


def blob_sha(data: bytes):
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def ut_of(data: bytes):
    m = re.findall(rb'"update_time"\s*:\s*"([^"]+)"', data[:200000])
    return m[0].decode() if m else ""


# ---------------------------------------------------------------- 抓取
def run_one(var):
    env = dict(os.environ)
    env["PYTHONPATH"] = PYLIBS
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "cloud_fetch_v8.py", "--only", var],
                           cwd=REPO_DIR, capture_output=True, text=True, env=env,
                           timeout=FETCH_TIMEOUT, encoding="utf-8", errors="ignore")
        out = (p.stdout or "") + (p.stderr or "")
        bad = [l for l in out.splitlines() if "❌" in l or "Traceback" in l]
        return var, time.time() - t0, (bad[-1][:120] if bad else "ok")
    except subprocess.TimeoutExpired:
        return var, time.time() - t0, "TIMEOUT"
    except Exception as e:
        return var, time.time() - t0, repr(e)[:120]


def fetch_round():
    t0 = time.time()
    ok, fail = [], []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(run_one, v): v for v in VARS}
        for f in as_completed(futs):
            v, dt, msg = f.result()
            (ok if msg == "ok" else fail).append((v, round(dt), msg))
    log(f"抓取完成 {time.time()-t0:.0f}s  成功{len(ok)} 失败{len(fail)}"
        + (f"  失败项={[x[0] for x in fail]}" if fail else ""))
    # 板块资金日内快照（主力净额分时卡的直接来源）
    try:
        p = subprocess.run([sys.executable, "intraday_snapshot.py"], cwd=REPO_DIR,
                           capture_output=True, text=True, timeout=120, env={**os.environ, "PYTHONPATH": PYLIBS},
                           encoding="utf-8", errors="ignore")
        if p.returncode == 0:
            log("日内快照 ok")
        else:
            log(f"日内快照 rc={p.returncode} {(p.stderr or '')[:100]}")
    except Exception as e:
        log(f"日内快照异常 {repr(e)[:80]}")
    return time.time() - t0


# ---------------------------------------------------------------- 原子推送
def collect_candidates(since_ts, wide=False):
    """本轮抓取写过的文件。
    常规 tick：只推盘中核心卡（15 个模块 data/*.js + 日内快照 + 新鲜度）——
      实测全量 136 文件推送 4.5 分钟，会把 10 分钟节拍吃掉；核心卡 ~18 个文件 <60s。
    wide=True：本次补数据用，data/ 下所有本轮重写过的文件都推。
    """
    out = []
    if wide:
        for fn in os.listdir(os.path.join(REPO_DIR, "data")):
            if not fn.endswith(".js"):
                continue
            fp = os.path.join(REPO_DIR, "data", fn)
            try:
                if os.path.getmtime(fp) >= since_ts and 200 < os.path.getsize(fp) <= 1_500_000:
                    out.append("data/" + fn)
            except OSError:
                pass
    else:
        for fn in [v + ".js" for v in VARS] + ["SECTOR_FUND_FLOW_INTRADAY.js", "FRESHNESS_STATUS.js"]:
            fp = os.path.join(REPO_DIR, "data", fn)
            try:
                if os.path.getmtime(fp) >= since_ts and os.path.getsize(fp) > 200:
                    out.append("data/" + fn)
            except OSError:
                pass
    # raw_data：只推本次抓取模块对应的那批（避免 376MB 大块被扫进来）
    want = {v.lower() for v in VARS} | {"sector_fund_flow"}
    rawdir = os.path.join(REPO_DIR, "raw_data")
    if os.path.isdir(rawdir):
        for fn in os.listdir(rawdir):
            if not fn.endswith(".json") or fn[:-5] not in want:
                continue
            fp = os.path.join(rawdir, fn)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            if st.st_mtime >= since_ts and st.st_size <= 1_500_000:
                out.append("raw_data/" + fn)
    return sorted(set(out))


def push_atomic(paths, dry=False, note=""):
    """一次原子提交推 main。父提交被抢跑（422 not fast-forward）时重新取 tip 重建，
    已上传的 blob 由 GitHub 按 sha 去重，重试代价极小。"""
    ts = now().strftime("%H:%M")
    for attempt in range(4):
        st, ref = api("GET", f"/repos/{REPO}/git/refs/heads/main")
        tip = ref["object"]["sha"]
        st, commit = api("GET", f"/repos/{REPO}/git/commits/{tip}")
        base_tree = commit["tree"]["sha"]
        st, tree = api("GET", f"/repos/{REPO}/git/trees/{base_tree}?recursive=1")
        remote = {e["path"]: e["sha"] for e in tree.get("tree", []) if e.get("type") == "blob"}

        changed = []
        for p in paths:
            fp = os.path.join(REPO_DIR, p.replace("/", os.sep))
            try:
                data = open(fp, "rb").read()
            except OSError:
                continue
            if len(data) < 80:
                continue
            sha = blob_sha(data)
            if remote.get(p) == sha:
                continue
            changed.append((p, data, sha))
        if not changed:
            log("无内容变化，跳过推送（重试轮/节假日自然空转）")
            return 0
        if dry:
            log(f"[dry-run] 待推 {len(changed)} 个文件：" + ", ".join(c[0] for c in changed[:8])
                + (" …" if len(changed) > 8 else ""))
            return len(changed)

        def put_blob(item):
            p, data, sha = item
            st, r = api("POST", f"/repos/{REPO}/git/blobs",
                        {"content": base64.b64encode(data).decode(), "encoding": "base64"})
            return p, r["sha"]

        entries = []
        with ThreadPoolExecutor(max_workers=8) as ex:
            for p, sha in ex.map(put_blob, changed):
                entries.append({"path": p, "mode": "100644", "type": "blob", "sha": sha})

        st, newtree = api("POST", f"/repos/{REPO}/git/trees", {"base_tree": base_tree, "tree": entries})
        msg = f"v8 盘中 tick {ts}：{len(entries)} 文件原子提交{note}"
        st, newc = api("POST", f"/repos/{REPO}/git/commits",
                       {"message": msg, "tree": newtree["sha"], "parents": [tip]})
        try:
            api("PATCH", f"/repos/{REPO}/git/refs/heads/main",
                {"sha": newc["sha"], "force": False}, tries=1)
        except RuntimeError as e:
            if "422" in str(e) and attempt < 3:
                log(f"main 被抢跑，{2*(attempt+1)}s 后基于新 tip 重建（attempt {attempt+1}/4）")
                time.sleep(2 * (attempt + 1))
                continue
            log(f"ref 更新失败：{e}")
            return 0
        log(f"✅ 已推 main {newc['sha'][:10]}  {len(entries)} 文件  {msg}")
        return len(entries)
    return 0


def write_marker(reason):
    """心跳：告诉云端调度器「本机已接管盘中」，避免双源互踢。
    注意：本文件必须与本轮数据在**同一个 commit** 落地——推送失败时线上标记保持陈旧，
    云端 20 分钟后自动接管。绝不能推送前单独写（那会让云端误以为本机正常）。"""
    fp = os.path.join(REPO_DIR, MARKER.replace("/", os.sep))
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "w", encoding="utf-8") as f:
        json.dump({"host": "lemoncat", "update_time": now().strftime("%Y-%m-%d %H:%M:%S"),
                   "reason": reason}, f, ensure_ascii=False)


LOCK = os.path.join(LOG_DIR, "tick.lock")


def single_instance():
    """防多实例并发（schtasks/守护/人工同时拉起）"""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        if os.path.exists(LOCK):
            age = time.time() - os.path.getmtime(LOCK)
            if age < 900:
                return False
        open(LOCK, "w").write(str(os.getpid()))
        return True
    except Exception:
        return True


def read_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_state(d):
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(d, f)


# ---------------------------------------------------------------- main
def run_tick(a, dt0=None):
    """一个完整 tick：抓取 → 生成 → 原子推送。返回实际耗时秒数。"""
    global TOK
    dt = dt0 or now()
    if not a.force and not in_window(dt):
        return -1
    st = read_state()
    last_ok = st.get("last_ok", "")
    if not a.force and last_ok:
        try:
            gap = (dt - datetime.datetime.strptime(last_ok, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)).total_seconds() / 60
            if gap < MIN_GAP_MIN:
                return -1
        except Exception:
            pass
    if not single_instance():
        log("已有实例在跑，跳过本轮")
        return -1

    TOK = load_token()
    t_start = time.time() - 5 - a.since_min * 60   # 允许 5s 时钟抖动
    log(f"tick start{' [force]' if a.force else ''}{' [push-only]' if a.push_only else ''}")
    spent = 0
    if not a.push_only:
        spent = fetch_round()
        try:
            env = {**os.environ, "PYTHONPATH": PYLIBS, "V8_SKIP_EXPERIMENT_CARDS": "1"}
            p = subprocess.run([sys.executable, "update_v8.py", "--category", "intraday"], cwd=REPO_DIR,
                               capture_output=True, text=True, timeout=240, env=env,
                               encoding="utf-8", errors="ignore")
            log(f"生成 data/*.js rc={p.returncode} {(p.stderr or '')[-100:] if p.returncode else 'ok'}")
        except Exception as e:
            log(f"生成异常 {repr(e)[:100]}")

    paths = collect_candidates(t_start, wide=a.wide)
    write_marker("intraday tick")          # 只随本轮数据一起提交；推失败则线上标记保持陈旧
    n = push_atomic(paths + [MARKER], dry=a.dry_run)
    log(f"候选 {len(paths)} 个 → 推送 {n} 个")
    if n or a.dry_run:
        write_state({"last_ok": now().strftime("%Y-%m-%d %H:%M:%S"), "files": n, "cost_s": round(spent)})
    cost = time.time() - t_start
    log(f"tick done {cost:.0f}s")
    return cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="跑一个 tick")
    ap.add_argument("--loop", action="store_true", help="常驻守护（登录自启，交易时段自行节拍）")
    ap.add_argument("--force", action="store_true", help="忽略交易时段窗口")
    ap.add_argument("--dry-run", action="store_true", help="只抓取与比对，不写远端")
    ap.add_argument("--push-only", action="store_true", help="跳过抓取/生成，只把已落盘的数据推上去")
    ap.add_argument("--since-min", type=int, default=0, help="候选文件 mtime 回看分钟数（默认 0=仅本轮）")
    ap.add_argument("--wide", action="store_true", help="补数据模式：data/ 下本轮重写的文件全推")
    a = ap.parse_args()

    if a.loop:
        log("=" * 20 + " 盘中 tick 守护启动（交易日 09:25-15:05 自行节拍）")
        while True:
            try:
                run_tick(a)
            except Exception as e:
                log(f"tick 异常 {repr(e)[:160]}")
            try:
                os.remove(LOCK)
            except OSError:
                pass
            time.sleep(60)
    run_tick(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
