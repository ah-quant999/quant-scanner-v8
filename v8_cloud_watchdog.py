#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 云端管线看门狗（只监督，不部署）
- 检查 self-hosted runner 在线/忙碌状态
- 检查 v8_cn_fetch / v8_build_deploy 最近运行状态
- 检查 raw_data 最新提交是否陈旧
- 检查站点 HTTP 200
- 把异常写入 _v8_watchdog.log，供人工/自动化追踪
- 集成健康检查与邮件告警
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 夜间静音时段（北京时间）：22:00-07:00 不发邮件，避免打扰休息。
# 严重基础设施问题仍会通过 write_urgent 留痕，但不在夜间发邮件。
QUIET_HOURS_START = 22
QUIET_HOURS_END = 7

# 健康检查类 fail 的告警门槛（分钟）：仅超阈项才在汇总邮件中提示（见 send_watchdog_alert docstring）
ALERT_OVERDUE_MIN = 120


def in_quiet_hours(now_cst=None):
    """判断当前是否处于夜间静音时段。"""
    n = now_cst or datetime.now(timezone(timedelta(hours=8)))
    h = n.hour
    if QUIET_HOURS_START <= QUIET_HOURS_END:
        return QUIET_HOURS_START <= h < QUIET_HOURS_END
    # 跨午夜：22:00-23:59 或 00:00-06:59
    return h >= QUIET_HOURS_START or h < QUIET_HOURS_END


# 邮件告警（配置在 .workbuddy/v8_smtp_config.json，gitignored）
try:
    from v8_send_alert import send_alert
except Exception:
    send_alert = None

REPO = "ah-quant999/quant-scanner-v8"
SITE_URL = "https://ah-quant999.github.io/quant-scanner-v8/"
# 2026-08-06 修正：阿狸咪 08-05 把中国数据抓取迁到云端 ubuntu，workflow 改名 + 新 id。
# 旧常量 "(cn)" / 324135267 已两个都不匹配 → 夜间靠 in_schedule_window 豁免掩盖成"假绿"，
# 白天调度窗口内会每小时误报一封告警邮件。此处切到云端主力，自建 runner 版降级为应急备份。
CN_WORKFLOW_NAME = "🇨🇳 v8 中国数据抓取(云端)"          # v8_cn_fetch_cloud.yml（主力）
CN_WORKFLOW_NAME_FALLBACK = "🇨🇳 v8 中国数据抓取(cn·应急)"  # v8_cn_fetch.yml（自建 runner 应急）
BD_WORKFLOW_NAME = "☁️ v8 构建部署(云端ubuntu)"
RUNNER_DIR = Path("D:/actions-runner-v8")
RUNNER_EXE = RUNNER_DIR / "bin" / "Runner.Listener.exe"
CN_WORKFLOW_ID = 327687211           # v8_cn_fetch_cloud.yml（云端 ubuntu 主力，用于 API 派发）
CN_WORKFLOW_ID_FALLBACK = 324135267  # v8_cn_fetch.yml（自建 cn runner 应急）

# 尝试从多个位置读取 token（本地文件优先，不落入仓库）
def _load_token():
    if os.environ.get("V8_GITHUB_TOKEN"):
        return os.environ["V8_GITHUB_TOKEN"]
    candidates = [
        Path("E:/workspace/quant-scanner-v8/.workbuddy/v8_gh_token.txt"),
        Path.home() / ".workbuddy" / "v8_gh_token.txt",
    ]
    for p in candidates:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return None

TOKEN = _load_token()
if not TOKEN:
    print("[FATAL] 找不到 GitHub token，请设置 V8_GITHUB_TOKEN 或 ~/.workbuddy/v8_gh_token.txt")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def utc_to_cst(s):
    if not s:
        return None
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone(timezone(timedelta(hours=8)))


def fmt_age(minutes):
    if minutes is None:
        return "N/A"
    if minutes < 60:
        return f"{int(minutes)}m"
    return f"{minutes/60:.1f}h"


def api_get(url):
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"__error__": e.code, "__msg__": e.read().decode("utf-8", "replace")}


def is_runner_process_alive():
    try:
        output = subprocess.check_output(
            ["tasklist.exe", "/FI", "IMAGENAME eq Runner.Listener.exe", "/NH"],
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).decode("gbk", errors="ignore")
        return "Runner.Listener.exe" in output
    except Exception:
        return False


def start_runner():
    """当 runner 离线且本地无进程时，尝试重新拉起监听进程。"""
    if not RUNNER_EXE.exists():
        return False, f"找不到 {RUNNER_EXE}"
    try:
        subprocess.Popen(
            [str(RUNNER_EXE), "run"],
            cwd=str(RUNNER_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return True, f"已尝试启动 {RUNNER_EXE} run"
    except Exception as e:
        return False, f"启动 runner 失败: {e}"


def check_runner(heal=False):
    d = api_get(f"https://api.github.com/repos/{REPO}/actions/runners")
    if "__error__" in d:
        return False, f"runner API error {d['__error__']}"
    runners = d.get("runners", [])
    if not runners:
        return False, "无 self-hosted runner"
    parts = []
    ok = True
    for r in runners:
        online = r.get("status") == "online"
        busy = r.get("busy", False)
        parts.append(f"{r['name']}: online={online}, busy={busy}")
        if not online:
            ok = False
            if heal:
                if not is_runner_process_alive():
                    started, msg = start_runner()
                    parts.append(f"heal={started}({msg})")
                else:
                    parts.append("heal=skipped(local process alive, waiting GitHub connect)")
    return ok, "; ".join(parts)


def latest_workflow_run(name):
    # list workflows then find by name
    wfs = api_get(f"https://api.github.com/repos/{REPO}/actions/workflows")
    if "__error__" in wfs:
        return None, f"workflows API error {wfs['__error__']}"
    wf_id = None
    for w in wfs.get("workflows", []):
        if w["name"] == name:
            wf_id = w["id"]
            break
    if not wf_id:
        return None, f"找不到 workflow '{name}'"
    runs = api_get(f"https://api.github.com/repos/{REPO}/actions/workflows/{wf_id}/runs?per_page=1")
    if "__error__" in runs:
        return None, f"runs API error {runs['__error__']}"
    items = runs.get("workflow_runs", [])
    if not items:
        return None, "无运行记录"
    return items[0], None


def in_schedule_window(kind, now_cst=None):
    """判断当前是否处于该项的"应有调度"时段。

    非调度时段（夜间/周末/收盘后）没有 cron，数据不刷新属于设计预期，
    此时不应判 FAIL —— 否则夜间每轮巡检必然满屏红灯，把真问题淹没。

    调度事实（北京时间）：
      cn_fetch     周一~周五 08:25-15:30（周末仅 09:00 一轮）
      algo_run     周一~周五 18:30 / 20:00
      build_deploy 由上游 push / workflow_run 触发，白天到夜间早段
    """
    now = now_cst or datetime.now(timezone(timedelta(hours=8)))
    h, wd = now.hour, now.weekday()
    weekend = wd >= 5
    mins = h * 60 + now.minute       # 当日分钟数，用于精确到分钟的窗口边界

    # 2026-08-06 第三十八轮修正【当日首刷盲区】：
    #   旧窗口下界写成整点 8（= 08:00 起就算"应有调度"），但当日第一份数据其实来自
    #   08:15 本地盘前全量 / 08:25 云端 cn_fetch_cloud(+约10分钟跑完)。
    #   ⇒ 每个工作日 08:00-08:30 之间，raw_data 与 cn_fetch 必然还停在昨晚的时间戳，
    #     必然判 FAIL，必然发一封"陈旧"告警邮件 —— 结构性误报，与真故障无法区分。
    #   本轮实测坐实：08:14:22 巡检报 raw_data 8.1h + cn_fetch 14.7h 双 FAIL 并发信；
    #     08:15:16 盘前自动化提交 7290336 后两项自动转绿，前后仅差 54 秒。
    #   ⇒ 工作日下界统一后移到 08:45（08:25 cron + 跑完 + 推送的安全余量）。
    #     整点巡检落在每小时 :14，边界取 08:45 意味着 08:14 豁免、09:14 起照常严查，
    #     真故障最迟 09:14 必被抓到，不会漏。
    PREMARKET_GUARD = 8 * 60 + 45    # 08:45

    if kind == "cn_fetch":
        if weekend:
            return 9 <= h <= 11          # 周末只有 09:00 一轮
        # 2026-08-06 修正：云端 v8_cn_fetch_cloud 除盘中槽外新增 16:30 港股补抓、
        # 17:00 与 21:00 两个全量兜底 cron，旧窗口 8-16 会把 17:00/21:00 故障静默掉。
        return PREMARKET_GUARD <= mins and h <= 22   # 云端 08:25~21:00 + 容错
    if kind == "build_deploy":
        if weekend:
            return 9 <= h <= 22
        return 8 <= h <= 22              # 盘后算法链 20:00 后仍会触发构建
    if kind == "raw_data":
        if weekend:
            return 9 <= h <= 22
        return PREMARKET_GUARD <= mins and h <= 22
    return True


def check_workflow(name, label, max_age_min=None):
    run, err = latest_workflow_run(name)
    if err:
        return False, err
    status = run["status"]
    con = run.get("conclusion")
    created = utc_to_cst(run["created_at"])
    now_cst = datetime.now(timezone(timedelta(hours=8)))
    age_min = (now_cst - created).total_seconds() / 60
    created_str = created.strftime("%m-%d %H:%M") if created else "?"
    ok = status == "completed" and con == "success"
    if max_age_min and age_min > max_age_min:
        ok = False
    detail = f"{label} {status}/{con} @ {created_str} (age {fmt_age(age_min)})"
    return ok, detail


def check_raw_data_stale(threshold_min=90):
    commits = api_get(f"https://api.github.com/repos/{REPO}/commits?path=raw_data&per_page=1")
    if "__error__" in commits:
        return False, f"commits API error {commits['__error__']}"
    if not commits:
        return False, "raw_data 无提交记录"
    c = commits[0]
    dt = utc_to_cst(c["commit"]["author"]["date"])
    now_cst = datetime.now(timezone(timedelta(hours=8)))
    age_min = (now_cst - dt).total_seconds() / 60
    ok = age_min <= threshold_min
    detail = f"raw_data last commit {dt.strftime('%m-%d %H:%M')} (age {fmt_age(age_min)}, threshold {fmt_age(threshold_min)})"
    return ok, detail


def check_site():
    try:
        req = urllib.request.Request(SITE_URL, method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as r:
            code = r.status
            return code == 200, f"site HTTP {code}"
    except Exception as e:
        return False, f"site unreachable: {e}"


def choose_category(now_cst):
    """按当前北京时刻选择派发类别（绕过 GitHub schedule 下午失效）。"""
    h = now_cst.hour + now_cst.minute / 60.0
    if h < 9:
        return "premarket"
    if h < 15:
        return "intraday"
    if h < 16.5:
        return "post_close"
    return "all"


def auto_dispatch(cat):
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{CN_WORKFLOW_ID}/dispatches"
    data = json.dumps({"ref": "main", "inputs": {"category": cat}}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers=HEADERS,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return True, f"已派发 cn_fetch category={cat} (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        return False, f"派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}"


def write_urgent(reason_lines):
    """邮件失败或需要留痕时，写 URGENT 文件到仓库根目录。"""
    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d_%H%M")
    p = Path(f"URGENT_小九_{ts}_v8看门狗告警.md")
    body = [f"# v8 看门狗告警 {ts}", ""] + reason_lines + ["", "请检查 v8_cloud_watchdog.py / v8_health_check.py 日志。"]
    p.write_text("\n".join(body), encoding="utf-8")
    print(f"[INFO] 已写紧急文件 {p}")


def run_health_check(alert=False):
    """调用 v8_health_check.py 做完整前端健康检查。"""
    cmd = [sys.executable, "v8_health_check.py"]
    if alert:
        cmd.append("--alert")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=300)
        return result.returncode, result.stdout + result.stderr
    except Exception as e:
        return 1, f"调用 v8_health_check.py 失败: {e}"


def send_watchdog_alert(now, results, health_rc=None, health_out=None):
    """发送看门狗汇总告警邮件；邮件失败时写 URGENT 文件。

    告警门槛（2026-08-04 修订）：
    - 管线类（runner/cn_fetch/build_deploy/raw_data/site）：任一 fail 即告警（基础设施问题）
    - 健康检查类：仅「超阈值 ≥ 120 分钟」的 fail 才触发邮件，纯空值/盘前数据不骚扰

    2026-08-05 新增：22:00-07:00 夜间静音时段不发邮件，避免打扰休息；
    严重问题仍写 URGENT 文件留痕，次日处理。
    """
    if not send_alert:
        write_urgent(["邮件发送器未加载"])
        return False

    now_cst = datetime.now(timezone(timedelta(hours=8)))
    quiet = in_quiet_hours(now_cst)

    # 管线类异常（基础设施，始终告警）
    infra_fails = [f"✗ {name}: {msg}" for name, ok, msg in results if not ok]
    # 健康检查类（数据卡片陈腐）改由 v8_health_check.py 自身负责：
    # 它已内置自愈（自动派发对应类别刷新）并发送「已自愈 / 需人工」邮件。
    # 此处不再重复告警，避免对同一次自愈既发「已自愈」又发「数据陈旧」造成噪声。
    health_alert_items = []

    total_alerts = len(infra_fails) + len(health_alert_items)
    if total_alerts == 0:
        print(f"[INFO] watchdog 跳过邮件：无管线异常且健康检查无超阈 ≥ {ALERT_OVERDUE_MIN}min 的项")
        return False

    if quiet:
        print(f"[INFO] 当前处于夜间静音时段（{QUIET_HOURS_START}:00-{QUIET_HOURS_END}:00），"
              f"跳过邮件告警，改写入 URGENT 文件留痕（共 {total_alerts} 项异常）")
        write_urgent(infra_fails + health_alert_items)
        return False

    subject = f"【v8看门狗告警】{total_alerts}项异常 @ {now}"
    lines = [f"v8 看门狗巡检时间：{now}", f"站点：{SITE_URL}", ""]
    if infra_fails:
        lines.extend(["管线异常：", *infra_fails, ""])
    if health_alert_items:
        lines.extend(["数据陈旧（≥2h）：", *health_alert_items])
    ok = send_alert(subject, "\n".join(lines))
    if not ok:
        write_urgent(infra_fails + health_alert_items)
    return ok


def main():
    parser = argparse.ArgumentParser(description="v8 云端管线看门狗")
    parser.add_argument("--heal", action="store_true", help="runner 离线时尝试自动拉起本地进程")
    parser.add_argument("--auto-dispatch", action="store_true", default=True,
                        help="数据陈旧且处于交易时段时，经 API 主动派发 cn_fetch 刷新（绕过 GitHub schedule，默认开）")
    parser.add_argument("--no-auto-dispatch", dest="auto_dispatch", action="store_false",
                        help="关闭自动派发（仅诊断）")
    parser.add_argument("--health-check", action="store_true",
                        help="同时运行 v8_health_check.py 做前端数据/空值/部署同步检查")
    parser.add_argument("--alert", action="store_true",
                        help="异常时发送邮件告警（依赖 .workbuddy/v8_smtp_config.json）")
    args = parser.parse_args()

    now_cst = datetime.now(timezone(timedelta(hours=8)))
    now = now_cst.strftime("%Y-%m-%d %H:%M:%S")
    results = []

    ok, msg = check_runner(heal=args.heal)
    results.append(("runner", ok, msg))

    ok, msg = check_workflow(CN_WORKFLOW_NAME, "cn_fetch", max_age_min=120)
    if not ok and not in_schedule_window("cn_fetch", now_cst):
        ok, msg = True, msg + " —— 非调度时段，豁免（cn_fetch 工作日 08:25-21:00 有 cron，周末仅 09:00）"
    results.append(("cn_fetch", ok, msg))

    ok, msg = check_workflow(BD_WORKFLOW_NAME, "build_deploy", max_age_min=120)
    if not ok and not in_schedule_window("build_deploy", now_cst):
        ok, msg = True, msg + " —— 非调度时段，豁免（夜间无上游推送属预期）"
    results.append(("build_deploy", ok, msg))

    raw_ok, raw_msg = check_raw_data_stale(threshold_min=90)
    if not raw_ok and not in_schedule_window("raw_data", now_cst):
        raw_ok, raw_msg = True, raw_msg + " —— 非调度时段，豁免（夜间数据不刷新属预期）"
    results.append(("raw_data_fresh", raw_ok, raw_msg))

    ok, msg = check_site()
    results.append(("site", ok, msg))

    # === 自动派发修复（紧急交接核心） ===
    if args.auto_dispatch:
        commits = api_get(f"https://api.github.com/repos/{REPO}/commits?path=raw_data&per_page=1")
        stale_min = None
        if "__error__" not in commits and commits:
            dt = utc_to_cst(commits[0]["commit"]["author"]["date"])
            stale_min = (now_cst - dt).total_seconds() / 60

        # 🔴 2026-08-06 修复判定盲点（勿回退）：
        #   raw_data 目录的提交可能由 build / risk_gauge 等链路产生，会把「中国数据实际已停摆」
        #   伪装成新鲜。08-06 事故实例：raw_data 最近提交 08:15 是 "v8 build: ... premarket"，
        #   而真正的 "v8 cn fetch" 停在 00:05（停摆 9.5h），看门狗却判定 1.2h 新鲜 → 跳过派发，
        #   兜底机制完全失效。故这里单独追踪 cn fetch 提交的新鲜度，取两者中更陈旧者作为派发依据。
        cn_stale_min = None
        cn_commits = api_get(f"https://api.github.com/repos/{REPO}/commits?path=raw_data&per_page=30")
        if "__error__" not in cn_commits and cn_commits:
            for c in cn_commits:
                if "cn fetch" in c["commit"]["message"].lower():
                    cn_dt = utc_to_cst(c["commit"]["author"]["date"])
                    cn_stale_min = (now_cst - cn_dt).total_seconds() / 60
                    break
        _cands = [v for v in (stale_min, cn_stale_min) if v is not None]
        effective_stale = max(_cands) if _cands else None

        weekday = now_cst.weekday()
        is_weekend = weekday >= 5
        active = (9 <= now_cst.hour <= 21) and (not is_weekend or now_cst.hour <= 18)

        def _age_detail():
            a = f"{stale_min/60:.1f}h" if stale_min is not None else "N/A"
            b = f"{cn_stale_min/60:.1f}h" if cn_stale_min is not None else "N/A"
            return f"raw_data={a}, cn_fetch={b}"

        if effective_stale is not None and effective_stale > 150 and active:
            cat = choose_category(now_cst)
            d_ok, d_msg = auto_dispatch(cat)
            results.append(("auto_dispatch", d_ok, f"{d_msg} [{_age_detail()}]"))
        elif effective_stale is not None and effective_stale > 150 and not active:
            results.append(("auto_dispatch", True,
                            f"数据陈旧但处于非活跃时段，跳过派发（防打扰）[{_age_detail()}]"))
        else:
            results.append(("auto_dispatch", True, f"数据新鲜（{_age_detail()}），无需派发"))

    overall = all(ok for _, ok, _ in results)
    flag = "OK" if overall else "ALERT"

    lines = [f"{now} | {flag} | watchdog check"]
    for name, ok, msg in results:
        status = "OK" if ok else "FAIL"
        lines.append(f"  [{status}] {name}: {msg}")

    log_text = "\n".join(lines) + "\n"
    log_path = Path("_v8_watchdog.log")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_text)

    print(log_text, end="")

    # === 健康检查（二期） ===
    health_rc, health_out = None, None
    if args.health_check:
        health_rc, health_out = run_health_check(alert=args.alert)
        # health check 失败也算 overall 失败
        if health_rc != 0:
            overall = False
            print(f"[ALERT] v8_health_check.py 返回非零: {health_rc}")

    # === 邮件告警（三期） ===
    if args.alert and not overall:
        send_watchdog_alert(now, results, health_rc=health_rc, health_out=health_out)

    sys.exit(0 if overall else 2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
