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
# 2026-08-18 主人令：云端 ubuntu-latest 才是主力，小九 self-hosted cn 只兜底。
# v8_cn_fetch_cloud.yml 固定 ubuntu-latest；v8_cn_fetch_cloud_selfhosted.yml 固定 [self-hosted, cn]，
# 仅由看门狗在云端连续失败时 dispatch。
CN_WORKFLOW_NAME = "🇨🇳 v8 中国数据抓取(云端)"              # v8_cn_fetch_cloud.yml（云端主力）
CN_WORKFLOW_NAME_FALLBACK = "🇨🇳 v8 中国数据抓取(云端·小九应急)"  # v8_cn_fetch_cloud_selfhosted.yml（应急）
BD_WORKFLOW_NAME = "☁️ v8 构建部署(云端ubuntu)"
RUNNER_DIR = Path("D:/actions-runner-v8")
RUNNER_EXE = RUNNER_DIR / "bin" / "Runner.Listener.exe"
CN_WORKFLOW_ID = 327687211                  # v8_cn_fetch_cloud.yml（云端 ubuntu-latest 主力）
CN_WORKFLOW_ID_FALLBACK = 336661558         # v8_cn_fetch_cloud_selfhosted.yml（小九 self-hosted 应急）
# ⚠️ 2026-08-18 修正：原 336655343 是 v8_cn_fetch_cloud_hosted.yml（旧「hosted兜底」）的过期 ID，
#    小九应急真身 workflow ID 为 336661558（经 /actions/workflows 实测核对）。
CN_SELFHOSTED_FALLBACK_FILE = "v8_cn_fetch_cloud_selfhosted.yml"  # 2026-08-18 主人令：小九只兜底
# 🔴 2026-08-18 主人根治令「小九不烧 TOKEN」：self-hosted 应急兜底派发 4 重门控
# 门控1 连续失败降级 / 门控2 静默期 / 门控3 云端 in_progress 不抢 / 门控4 真超阈才派
_SELFHOSTED_QUIET_MIN = 30                    # 同一 workflow 派发间隔下限（避免刚派就又派）
_SELFHOSTED_MAX_CONSEC_FAIL = 3               # 连续失败超此值 → 降级只告警不重试
_SELFHOSTED_DISPATCH_LOG = Path(".workbuddy/v8_selfhosted_dispatch.json")  # 派发状态文件
BD_WORKFLOW_ID = 324135263                  # v8_build_deploy.yml（☁️ v8 构建部署(云端ubuntu)）

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


def api_get(url, max_retries=2, retry_sleep=2.0):
    """GET GitHub API；网络层错误(URLError/超时/连接重置)重试一次后降级为错误字典，
    绝不向外抛出 —— 调用方统一以 `if "__error__" in <result>` 兜底，避免网络抖动整进程
    崩溃（2026-08-20 第289轮根因：api_get 未捕获 URLError(WinError 10060) 致看门狗中断）。"""
    import time as _time
    last_err = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # HTTP 层错误(4xx/5xx) 不重试，直接返回错误字典
            return {"__error__": e.code, "__msg__": e.read().decode("utf-8", "replace")}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            # 网络层错误(连接超时/DNS/重置)：瞬时抖动重试，仍失败返回错误字典
            last_err = e
            if attempt < max_retries:
                try:
                    _time.sleep(retry_sleep)
                except Exception:
                    pass
                continue
            return {"__error__": "URLError",
                    "__msg__": str(getattr(e, "reason", e))}
    return {"__error__": "URLError", "__msg__": str(getattr(last_err, "reason", last_err))}


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
    # 🛡️ 2026-08-16 双机互备修复（根治「单台离线 → 误报 FAIL 刷屏」）：
    #   双机设计工作日小九(lemoncat-cn)/周末阿狸咪(alimi-cn) 互备，cn_fetch 的
    #   runs-on=[self-hosted, cn] 会自动选**任一在线**机接任务。故只要有一台 cn
    #   runner 在线，cn_fetch 就能跑，整体视为 OK；离线机仅附注提示（信息不丢），
    #   不再判 FAIL。仅当**全部** cn runner 离线才真 FAIL（数据必然停更）。
    online = [r for r in runners if r.get("status") == "online"]
    offline = [r for r in runners if r.get("status") != "online"]
    parts = []
    ok = len(online) > 0
    for r in runners:
        on = r.get("status") == "online"
        busy = r.get("busy", False)
        parts.append(f"{r['name']}: online={on}, busy={busy}")
        if not on and heal:
            if not is_runner_process_alive():
                started, msg = start_runner()
                parts.append(f"heal={started}({msg})")
            else:
                parts.append("heal=skipped(local process alive, waiting GitHub connect)")
    if offline:
        names = ", ".join(r["name"] for r in offline)
        if ok:
            parts.append(f"注: {names} 离线（有在线备用机，cn_fetch 可自动兜底，不阻断）")
        else:
            parts.append(f"⚠ 全部 cn runner 离线: {names}")
    return ok, "; ".join(parts)


def latest_workflow_run(name=None, skip_neutral=True, workflow_id=None):
    """返回 (最近一条已完成且有实际结论的 run, err, 正在运行中的 run 或 None)。

    2026-08-13 第180轮修复【cn_fetch 假 FAIL】：GitHub Actions 的 workflow 显示名
    会被缓存/回退为文件名（实测 v8_cn_fetch_cloud.yml 的注册名变成
    '.github/workflows/v8_cn_fetch_cloud.yml'），硬编码显示名查找失配即误报 FAIL 并发
    告警邮件。⇒ 优先用稳定 workflow_id 解析（与 auto_dispatch 派发同源），显示名仅作
    兜底/错误信息，杜绝名称漂移导致的假 FAIL。
    """
    if workflow_id is not None:
        wf_id = workflow_id
    else:
        # list workflows then find by name
        wfs = api_get(f"https://api.github.com/repos/{REPO}/actions/workflows")
        if "__error__" in wfs:
            return None, f"workflows API error {wfs['__error__']}", None
        wf_id = None
        for w in wfs.get("workflows", []):
            if w["name"] == name:
                wf_id = w["id"]
                break
        if not wf_id:
            return None, f"找不到 workflow '{name}'", None
    # 2026-08-09 第119轮修复【skipped 误报】：
    #   GitHub Actions 并发触发时（如 workflow_run 与 push 同时命中），同一分钟内常出现
    #   一条 conclusion=skipped 的 run 与一条 success 并存；旧实现 per_page=1 取最新一条，
    #   恰好取到 skipped 即误判 FAIL 并发出告警邮件（实测 19:09 两条 run 并存致误报）。
    #   ⇒ 跳过 neutral 结论（skipped/cancelled/neutral/action_required），取最近一条
    #     有实际结论（success/failure）的 run；若整页全是 neutral 才退回第一条（真异常）。
    # 2026-08-11 第156轮修复【in_progress 误报】：
    #   status=in_progress/queued 的 run 其 conclusion 为 None，既不在 NEUTRAL 里，
    #   旧实现会把它当成"最新有结论的 run"直接返回，check_workflow 再以
    #   `con == "success"` 判定 → 每当巡检恰好撞上 cn_fetch 正在跑（交易时段高频 cron
    #   下极常见）就误判 FAIL 并发出告警邮件（实测 09:18 cn_fetch 启动 4 分钟即误报）。
    #   ⇒ 运行中的 run 单独摘出（running），不参与成败判定；成败仍看最近一条
    #     已完成且非 neutral 的 run，由 check_workflow 组合判断。
    NEUTRAL = ("skipped", "cancelled", "neutral", "action_required")
    runs = api_get(f"https://api.github.com/repos/{REPO}/actions/workflows/{wf_id}/runs?per_page=20")
    if "__error__" in runs:
        return None, f"runs API error {runs['__error__']}", None
    items = runs.get("workflow_runs", [])
    # 2026-08-15 修正【build_deploy 误报告警·根因】：
    #   旧逻辑在下方全局丢弃 event=="push" 的运行。但 build_deploy 的真实构建 100% 由
    #   push raw_data/data/index.html 触发（见 v8_build_deploy.yml 的 on.push.paths），
    #   丢弃后 latest_workflow_run 只能回退到最旧的「非 push」运行——常为 concurrency
    #   导致的 skipped 瞬时态（被新 run 取代），check_workflow 据此误判 FAIL 并每小时发邮件。
    #   ⇒ 不再全局丢弃 push；最近的 push success 即视为管线健康证据（真故障也不会漏判，
    #     因为 failure 结论本就不在 NEUTRAL 内，仍会被正常捕获）。
    #   注：历史上担心的「push 0-job 瞬时 failure」在当前 paths 下不会发生——push 工作流
    #   YAML 本身不在触发路径内，真正的 push 构建失败理应告警。
    if not items:
        return None, "无运行记录", None
    running = None
    for r in items:
        if r.get("status") != "completed":
            if running is None:
                running = r          # 记录最新一条运行中实例
            continue
        if skip_neutral and r.get("conclusion") in NEUTRAL:
            continue
        return r, None, running
    # 整页全是 neutral / 全在运行中：退回第一条，由 check_workflow 兜底判定
    return items[0], None, running


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

    # 2026-08-20 第293棒根治【cn_fetch 盘后空档结构性误报】：
    #   核实 .github/workflows/v8_cn_fetch_cloud.yml 只有 5 条 cron（平台隐性上限），
    #   工作日最后一档是 17:20 CST（'20 9 * * 1-5'）——旧注释所称「17:00 与 21:00 两个
    #   全量兜底 cron」早已不存在。⇒ 17:20 之后直到次日 08:25 之间没有任何排程，
    #   cn_fetch 的 age 只会线性增长，必然越过 max_age_min=120 阈值。
    #   实测坐实：08-18 20:24 FAIL(2.5h)、08-18 21:24 FAIL(3.5h)、08-20 20:25 FAIL(2.2h)，
    #   每个交易日傍晚固定刷 1~3 封"陈旧"告警邮件，且每轮 heal 都多派一次云端 fetch
    #   （违背主人「小九不烧 TOKEN」铁律，且盘后 A股无新数据，派了也无意义）。
    #   ⇒ 严查窗口下沉到 19:30 收口（17:20 最后一档 + 120min 阈值 + 10min 余量）。
    #     17:20 那档真失败仍会在 19:2x 那一轮被抓到，不漏报真故障。
    POSTCLOSE_GUARD = 19 * 60 + 30   # 19:30

    if kind == "cn_fetch":
        if weekend:
            return 9 <= h <= 11          # 周末只有 09:00 一轮
        return PREMARKET_GUARD <= mins <= POSTCLOSE_GUARD
    if kind == "build_deploy":
        # 🛡️ 2026-08-16 根治「周末刷邮件」：build_deploy 仅由上游 push 触发，周末无盘后
        #   算法链、通常无人 push，最近成功停留 >120min 属设计预期。旧逻辑周末 9-22 严查
        #   → 每轮 FAIL 刷邮件。⇒ 周末整段豁免（真构建故障由 site HTTP 200 检查 + 云端
        #   build workflow 失败兜底，不会漏报）。
        if weekend:
            return False
        return 8 <= h <= 22              # 盘后算法链 20:00 后仍会触发构建
    if kind == "raw_data":
        # 🛡️ 2026-08-16 根治「周末刷邮件」：raw_data 由 cn_fetch 产生，周末仅在 09:00~11:00
        #   有抓取轮次，11:00 之后停更属预期。旧逻辑周末 9-22 全严查 → 11:00 后必超 90min
        #   阈值每轮 FAIL 刷邮件。⇒ 周末仅 9-11 严查，其余时段豁免。
        if weekend:
            return 9 <= h <= 11
        return PREMARKET_GUARD <= mins and h <= 22
    if kind == "algo":
        # 🔴 2026-09-01 主人令：盘后算法链 19:15 / 20:00 两档（每天触发，内部交易日历 gate），
        #   失败后自愈重派可能延续到 21-23 点；凌晨 00:00-02:00 为次轮补跑窗口。
        #   周末/节假日无盘后选股（gate 跳过），整段豁免以防结构性误报。
        if weekend:
            return False
        return (19 <= h <= 23) or (0 <= h <= 2)
    return True


# 运行中的 workflow 允许的最长时长；超过视为卡死（v8 各 workflow 正常 2-15 分钟完成）
RUNNING_GRACE_MIN = 45

# ═══ 2026-09-01 主人令「监督跑算法更先进」：盘后算法链独立监督阈值 ═══
# 算法链与轻量 workflow 不同：单轮合法运行时长可达 60~150min（step 超时 150min / job 200min）。
# 故不能用 RUNNING_GRACE_MIN=45 一刀切（会误报）。这里用专属阈值：
ALGO_WORKFLOW_FILE = "v8_algo_cloud.yml"
ALGO_WORKFLOW_NAME = "☁️ v8 盘后算法链(云端)"   # 2026-09-04 修复：2bb75e57 引用但漏定义 → NameError 致看门狗整轮崩溃
ALGO_STUCK_MIN = 165        # 算法链 step 150min/job 200min：>165min 仍 in_progress 必为整条卡死
ALGO_STALE_MIN = 1500       # 距上次成功 >25h 且处于盘后窗口 → 疑似漏跑（交易日每天 19:15/20:00 两档）
ALGO_SILENCE_KILL_MIN = 15  # 与 run_algorithms.SILENCE_KILL_SEC 对齐：本地心跳静默超 15min+余量 → 卡死



def check_workflow(name, label, max_age_min=None, workflow_id=None):
    run, err, running = latest_workflow_run(name, workflow_id=workflow_id)
    if err:
        return False, err, False
    now_cst = datetime.now(timezone(timedelta(hours=8)))

    # ① 有正在运行的实例：运行中不是失败。未超时 → OK；超时 → 判卡死。
    if running is not None:
        r_created = utc_to_cst(running["created_at"])
        r_age = (now_cst - r_created).total_seconds() / 60
        r_str = r_created.strftime("%m-%d %H:%M") if r_created else "?"
        if r_age <= RUNNING_GRACE_MIN:
            tail = ""
            if run is not None and run.get("status") == "completed":
                p_created = utc_to_cst(run["created_at"])
                tail = f"；上轮 {run.get('conclusion')} @ {p_created.strftime('%m-%d %H:%M')}"
            return True, f"{label} 运行中({running['status']}) @ {r_str} (已 {fmt_age(r_age)}){tail}", False
        return False, f"{label} {running['status']} @ {r_str} 已 {fmt_age(r_age)} 未结束，疑似卡死", False

    if run is None:
        return False, f"{label} 无可判定的运行记录", False

    # ② 无运行中实例：按最近一条已完成 run 判成败 + 新鲜度
    status = run["status"]
    con = run.get("conclusion")
    created = utc_to_cst(run["created_at"])
    age_min = (now_cst - created).total_seconds() / 60
    created_str = created.strftime("%m-%d %H:%M") if created else "?"
    ok = status == "completed" and con == "success"
    if max_age_min and age_min > max_age_min:
        ok = False
    # 2026-08-18 第250轮修复【假绿盲区】：显式 failure 绝不受窗口/时段豁免，否则夜间/周末的
    # 真实构建失败会被 `in_schedule_window` 无条件掩成 OK（r230-r235 连续 7 轮假绿实证）。
    is_explicit_failure = status == "completed" and con == "failure"
    detail = f"{label} {status}/{con} @ {created_str} (age {fmt_age(age_min)})"
    return ok, detail, is_explicit_failure


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


def find_workflow_id_by_filename(filename):
    """按 workflow 文件路径（稳定，不像显示名会漂移为文件名）解析 workflow id。"""
    wfs = api_get(f"https://api.github.com/repos/{REPO}/actions/workflows")
    if "__error__" in wfs:
        return None
    for w in wfs.get("workflows", []):
        if w.get("path") == f".github/workflows/{filename}":
            return w["id"]
    return None


def _read_local_heartbeat():
    """读本地 raw_data/algo_heartbeat.json（cn-runner 同机场景可见最近一轮进度）。"""
    p = Path("raw_data/algo_heartbeat.json")
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def _algo_recover(run_id, run_number):
    """算法链卡死兜底：cancel 当前 run + repository_dispatch trigger_algo 重派。
    受全局派发冷却节流，避免重复派发风暴。"""
    try:
        if not _global_dispatch_allowed()[0]:
            print(f"[HEAL] algo 链 run #{run_number} 卡死，但处于全局派发冷却中，跳过重派")
            return
        # ① cancel 卡死 run
        cancel_url = f"https://api.github.com/repos/{REPO}/actions/runs/{run_id}/cancel"
        try:
            req = urllib.request.Request(cancel_url, headers=HEADERS, method="POST")
            urllib.request.urlopen(req, timeout=30).read()
        except Exception as e:
            print(f"[WARN] cancel algo run #{run_number} 失败: {e}")
        # ② repository_dispatch 重派 trigger_algo（v8_algo_cloud.yml 已注册该 types）
        disp_url = f"https://api.github.com/repos/{REPO}/dispatches"
        data = json.dumps({
            "event_type": "trigger_algo",
            "client_payload": {"reason": "watchdog_algo_stuck_recover", "stuck_run": run_number},
        }).encode("utf-8")
        req2 = urllib.request.Request(disp_url, data=data, headers=HEADERS, method="POST")
        try:
            with urllib.request.urlopen(req2, timeout=30) as r:
                print(f"[HEAL] algo 链 run #{run_number} 卡死 → 已 cancel + 重派 trigger_algo (HTTP {r.status})")
        except Exception as e:
            print(f"[WARN] 重派 trigger_algo 失败: {e}")
        _record_global_dispatch()
    except Exception as e:
        print(f"[WARN] algo 链自愈异常: {e}")


def check_algo_chain():
    """监督盘后算法链 run_algorithms 的运行状态（2026-09-01 主人令·监督跑算法更先进）。

      - 无运行中实例：按最近已完成 run 判成败 + 新鲜度（与现有其他 workflow 同口径）。
      - 有运行中实例：
          * 进程内监督器（run_algorithms._supervised_run）已对「单脚本静默卡死」实时杀进程续跑，
            此处只兜底「整条 run 卡死（runner 失联 / 进程冻结 / concurrency 卡死）」。
          * elapsed > ALGO_STUCK_MIN → 判卡死，cancel + 重派 trigger_algo。
          * 本地心跳 status=running 但更新时间已超静默阈值 → 判卡死（同机场景）。
    返回 (ok, detail, is_explicit_failure)。卡死自愈合路径返回 ok=False 但不带 is_failure，
    以免与「显式 failure」混淆；卡死总是硬告警（不受调度窗口豁免）。"""
    wf_id = find_workflow_id_by_filename(ALGO_WORKFLOW_FILE)
    if wf_id is None:
        return False, "找不到 v8_algo_cloud workflow（API 错误或文件名变更）", False
    run, err, running = latest_workflow_run(ALGO_WORKFLOW_NAME, workflow_id=wf_id)
    if err:
        return False, err, False
    now_cst = datetime.now(timezone(timedelta(hours=8)))

    if running is not None:
        r_created = utc_to_cst(running["created_at"])
        r_age = (now_cst - r_created).total_seconds() / 60
        r_num = running.get("run_number")
        # 整条 run 卡死兜底：超过 ALGO_STUCK_MIN 仍 in_progress → 必为异常
        if r_age > ALGO_STUCK_MIN:
            detail = (f"algo 链 run #{r_num} {running['status']} @ {r_created.strftime('%m-%d %H:%M')} "
                      f"已 {fmt_age(r_age)} 未结束（step 超时150min/job 200min），疑似整条卡死")
            _algo_recover(running["id"], r_num)
            return False, detail, False
        # 同机心跳兜底：status=running 但最后心跳已超静默阈值 → 进程冻结
        hb = _read_local_heartbeat()
        if hb and hb.get("status") == "running":
            try:
                hb_ts = datetime.strptime(hb["update_time"], "%Y-%m-%d %H:%M:%S")
                hb_age = (now_cst - hb_ts).total_seconds() / 60
                if hb_age > (ALGO_SILENCE_KILL_MIN + 5):
                    detail = (f"algo 链 run #{r_num} 心跳静默 {fmt_age(hb_age)}"
                              f"（最后脚本 {hb.get('script')}），疑似进程冻结，已触发 cancel+重派")
                    _algo_recover(running["id"], r_num)
                    return False, detail, False
            except Exception:
                pass
        return True, (f"algo 链 run #{r_num} {running['status']} @ {r_created.strftime('%m-%d %H:%M')} "
                      f"(已 {fmt_age(r_age)})"), False

    if run is None:
        return False, "algo 链 无可判定运行记录", False

    status = run["status"]
    con = run.get("conclusion")
    created = utc_to_cst(run["created_at"])
    age_min = (now_cst - created).total_seconds() / 60
    ok = status == "completed" and con == "success"
    is_failure = status == "completed" and con == "failure"
    detail = f"algo 链 {status}/{con} @ {created.strftime('%m-%d %H:%M')} (age {fmt_age(age_min)})"
    # 盘后窗口内距上次成功过久 → 漏跑
    if ok and age_min > ALGO_STALE_MIN and in_schedule_window("algo", now_cst):
        ok = False
        detail += (f" | 距上次成功 {fmt_age(age_min)} > {fmt_age(ALGO_STALE_MIN)}"
                   f"（盘后窗口内缺跑，疑似漏跑）")
    return ok, detail, is_failure


def check_site():
    """检查站点可达性（带 retry 吸收瞬时抖动）。"""
    import time as _time
    max_retries = 2
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(SITE_URL, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as r:
                code = r.status
                if code == 200:
                    return True, f"site HTTP {code}"
                last_err = f"HTTP {code}"
        except Exception as e:
            last_err = e
        if attempt < max_retries:
            _time.sleep(3)
    return False, f"site unreachable (已重试{max_retries}次): {last_err}"


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


# 健康检查报告卡片分组 -> 刷新类别映射（与 v8_health_check.py 保持一致）
_PAGE_TO_CAT = {
    "实时数据": "intraday",
    "今日事件": "premarket",
    "盘后数据": "post_close",
    "选股策略": "post_close",
}


def _load_health_report():
    """读取 v8_health_check.py 生成的结构化报告。"""
    p = Path(".workbuddy/v8_health_report.json")
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] 读取 health report 失败: {e}")
        return None


def _is_dispatch_active(now_cst):
    """判断是否处于允许自动派发的活跃时段（工作日 09-21，周末 ≤18）。"""
    weekday = now_cst.weekday()
    is_weekend = weekday >= 5
    return (9 <= now_cst.hour <= 21) and (not is_weekend or now_cst.hour <= 18)


def auto_dispatch_smart(now_cst, health_rc, health_out):
    """基于健康检查逐源报告做智能派发，解决只看 raw_data commit 时间的粒度缺陷。

    策略：
      1. 优先读取 .workbuddy/v8_health_report.json 中未自愈的 fail 数据卡片；
         按 page 归类为 category，每类只派发一次（去重 25 分钟）。
      2. 若报告不可读或无 action 项，回退到旧逻辑：检查 raw_data/cn_fetch commit 时间。
    """
    if not _is_dispatch_active(now_cst):
        return True, "当前非活跃时段，跳过自动派发（防打扰）"

    report = _load_health_report()
    dispatched_cats = []
    failed_msgs = []

    if report:
        # 逐源 actionable 项：数据卡片 fail，且未被 self_heal 标记为「已自动派发刷新/已自愈】
        actionable = {}
        for it in report.get("items", []):
            if it.get("status") != "fail":
                continue
            page = it.get("page")
            cat = _PAGE_TO_CAT.get(page)
            if not cat:
                continue
            heal = it.get("heal", "")
            if heal.startswith("已自动派发刷新") or heal.startswith("已自愈"):
                continue  # self_heal 已成功处理，不重复派发
            actionable.setdefault(cat, []).append(it)

        if actionable:
            for cat, items in actionable.items():
                names = [it.get("name", it.get("id", "?")) for it in items]
                ok, msg = auto_dispatch_with_fallback(cat)
                if ok:
                    dispatched_cats.append(f"{cat}[{','.join(names)}]")
                else:
                    failed_msgs.append(f"{cat}: {msg}")
            if dispatched_cats:
                return True, f"基于 health report 逐源派发: {'; '.join(dispatched_cats)}" + (
                    f" | 失败: {'; '.join(failed_msgs)}" if failed_msgs else "")
            if failed_msgs:
                return False, f"health report 派发全部失败: {'; '.join(failed_msgs)}"

    # 回退：旧逻辑（raw_data / cn_fetch commit 时间）
    commits = api_get(f"https://api.github.com/repos/{REPO}/commits?path=raw_data&per_page=1")
    stale_min = None
    if "__error__" not in commits and commits:
        dt = utc_to_cst(commits[0]["commit"]["author"]["date"])
        stale_min = (now_cst - dt).total_seconds() / 60

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

    def _age_detail():
        a = f"{stale_min/60:.1f}h" if stale_min is not None else "N/A"
        b = f"{cn_stale_min/60:.1f}h" if cn_stale_min is not None else "N/A"
        return f"raw_data={a}, cn_fetch={b}"

    # 🛡 2026-08-28 主人令 Option A：30 分钟心跳兜底派发，与 staleness 彻底解耦。
    # GitHub schedule cron 可能整日静默；仅靠 health fail / commit 陈旧才派发，
    # 会出现「guard 部分补抓把数据刷得很新 → 全量 cn_fetch 不派发」的断档窗口。
    # 活跃时段内，只要全局 30min 冷却已过，就强制派发一次，保底刷新。
    cat = choose_category(now_cst)
    d_ok, d_msg = auto_dispatch_with_fallback(cat)
    if d_ok:
        ctx = "commit 兜底" if (effective_stale is not None and effective_stale > 150) else "30min 心跳兜底"
        return True, f"{d_msg} ({ctx} [{_age_detail()}])"
    return False, f"心跳/兜底派发失败: {d_msg} [{_age_detail()}]"


_PENDING_STATES = ("queued", "pending", "waiting", "requested")

# 2026-08-12 第173轮：与 v8_health_check.py::_PENDING_MAX_AGE_MIN 同源同值。
# pending 超该分钟数视为 GitHub 侧僵尸排队（实测 run#93 挂 queued 35min+ 不启动），
# 不再阻断派发，否则第172轮守卫会让自愈对该 workflow 死锁整天。
_PENDING_MAX_AGE_MIN = 15


def has_pending_run(workflow_id, headers=None):
    """检查指定 workflow 是否已有「排队中(未开始)」的运行。

    2026-08-12 第172轮根因修复：v8_cn_fetch_cloud.yml 配置
    `concurrency: {group: v8-cn-fetch-cloud, cancel-in-progress: false}`。
    GitHub 在该模式下**每个 concurrency group 只保留 1 个 pending run**——
    当已有一个 run 在跑、另一个在排队时，再来一次 workflow_dispatch 会把
    **原先排队的那个直接 cancel 掉**，只留最新的。

    实测证据（08-12）：14:25 dispatch → cancelled，14:35 dispatch → cancelled，
    14:52 in_progress + 14:53 → cancelled；raw_data/index_quotes.json 提交史
    13:41:15 之后直接跳到 14:50:18，**盘中数据断档 69 分钟**，9 张盘中卡
    (INDEX_QUOTES/ETF_PULSE/SECTOR_FUND_FLOW/CONCEPT_RANKING/... ) 全部超 45min 阈值转 FAIL。
    此现象在第 169/171/172 轮反复出现，此前被误判为「盘中过渡态」或「本地落后假阳性」。

    自伤链路：同一次看门狗调用内，看门狗 auto_dispatch 与子进程
    v8_health_check.py::self_heal **各派发一次** → 后者把前者的 pending run 顶掉，
    等于每轮只有最后一次派发生效，且把已排队的刷新白白取消。

    守卫策略：仅当已存在 pending(排队未开始) run 时跳过派发——因为它必然会跑，
    再派发只会取消它、把刷新推迟一整轮。若只有 in_progress 而无 pending，
    则允许派发（我方进入排队，不会取消任何人）。
    查询失败时返回 False（保守放行，宁可多派发也不漏刷新）。

    2026-08-12 第173轮加固：pending 年龄超 _PENDING_MAX_AGE_MIN 视为僵尸排队，
    **不阻断派发**（否则卡死的 queued run 会让自愈对该 workflow 死锁整天）。
    """
    hdrs = headers or HEADERS
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{workflow_id}/runs?per_page=10"
    try:
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        now_utc = datetime.now(timezone.utc)
        for run in data.get("workflow_runs") or []:
            if (run.get("status") or "").lower() not in _PENDING_STATES:
                continue
            created = run.get("created_at")
            age_min = None
            try:
                dt = datetime.strptime(created, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                age_min = (now_utc - dt).total_seconds() / 60
            except Exception:
                age_min = None
            if age_min is not None and age_min > _PENDING_MAX_AGE_MIN:
                print(f"[WARN] workflow {workflow_id} 存在僵尸 pending run(created {created}, "
                      f"排队 {age_min:.0f}min > {_PENDING_MAX_AGE_MIN}min)，不阻断派发")
                continue
            return True, created
        return False, None
    except Exception:
        return False, None


def auto_dispatch(cat):
    pending, since = has_pending_run(CN_WORKFLOW_ID)
    if pending:
        return True, (f"已有排队中的 cn_fetch 运行(created {since})，跳过派发"
                      f"（避免 concurrency 顶掉该 pending run 致刷新被取消）category={cat}")
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
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # 网络层失败(超时/连接重置)降级为派发失败，不向上抛（2026-08-20 一劳永逸兜底）
        return False, f"派发失败 network: {getattr(e, 'reason', e)}"


def _load_selfhosted_log():
    """读取 self-hosted 派发状态（连续失败计数 / 上次派发时间）。文件缺失视为全 0。"""
    if not _SELFHOSTED_DISPATCH_LOG.exists():
        return {"consec_fail": 0, "last_dispatch": None, "last_dispatch_ok": None}
    try:
        return json.loads(_SELFHOSTED_DISPATCH_LOG.read_text(encoding="utf-8"))
    except Exception:
        return {"consec_fail": 0, "last_dispatch": None, "last_dispatch_ok": None}


def _save_selfhosted_log(st):
    """写回 self-hosted 派发状态（.workbuddy/ 下，不落入仓库主目录）。"""
    try:
        _SELFHOSTED_DISPATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
        _SELFHOSTED_DISPATCH_LOG.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[WARN] 写 self-hosted 派发状态失败: {e}")


def _check_selfhosted_throttle(now_cst):
    """门控 1+2：连续失败降级 + 静默期。返回 (allowed, reason)。"""
    st = _load_selfhosted_log()
    if st.get("consec_fail", 0) >= _SELFHOSTED_MAX_CONSEC_FAIL:
        return False, (f"self-hosted 连续失败 {st['consec_fail']} 次 ≥ "
                       f"{_SELFHOSTED_MAX_CONSEC_FAIL} → 降级只告警不重试（主人令：小九不烧 TOKEN）")
    last = st.get("last_dispatch")
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            quiet_left = _SELFHOSTED_QUIET_MIN - (now_cst - last_dt).total_seconds() / 60
            if quiet_left > 0:
                return False, f"距上次 self-hosted 派发仅 {quiet_left:.0f}min < {_SELFHOSTED_QUIET_MIN}min 静默期，跳过"
        except Exception:
            pass
    return True, ""


def _record_selfhosted_dispatch(ok):
    """记录派发结果：成功清零连续失败；失败累加（供下轮门控1降级）。"""
    st = _load_selfhosted_log()
    if ok:
        st["consec_fail"] = 0
    else:
        st["consec_fail"] = st.get("consec_fail", 0) + 1
    st["last_dispatch"] = datetime.now(timezone(timedelta(hours=8))).isoformat()
    st["last_dispatch_ok"] = bool(ok)
    _save_selfhosted_log(st)


def _check_cloud_in_progress():
    """门控 3：云端主力 workflow 有 in_progress 运行就不派 self-hosted，让云端自然完成。"""
    try:
        url = f"https://api.github.com/repos/{REPO}/actions/workflows/{CN_WORKFLOW_ID}/runs?per_page=5"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode("utf-8"))
        for run in data.get("workflow_runs") or []:
            st = (run.get("status") or "").lower()
            if st in ("in_progress", "queued", "pending", "waiting", "requested"):
                return True, f"云端 cn_fetch 有 run #{run.get('run_number')} {st} 在跑，不抢派"
        return False, None
    except Exception as e:
        return False, None


def dispatch_selfhosted_fallback(cat):
    """2026-08-18 主人令：云端 ubuntu-latest 失败时，派发到小九 self-hosted cn 应急兜底。

    🔴 2026-08-18 主人根治令加 3 重门控（小九不烧 TOKEN）：
      门控1 连续失败 ≥3 次 → 永久只发邮件不重试
      门控2 30 分钟静默期 → 避免刚派就又派
      门控3 云端 in_progress → 在跑就别抢，让云端自然完成
    """
    now_cst = datetime.now(timezone(timedelta(hours=8)))
    # 门控 1+2：连续失败降级 + 静默期
    allowed, reason = _check_selfhosted_throttle(now_cst)
    if not allowed:
        # 2026-08-24 根因修复：连续失败≥3 是真问题(需人工)保留 False 告警；
        # 静默期/距上次派发过近属「安全跳过」降级为 True，避免误报 auto_dispatch 失败邮件。
        if "连续失败" in reason:
            return False, f"self-hosted 派发被门控拦截: {reason}"
        return True, f"self-hosted 派发安全跳过(门控): {reason}"
    # 门控 3：云端在跑就不抢
    cloud_busy, cmsg = _check_cloud_in_progress()
    if cloud_busy:
        # 2026-08-24 根因修复：云端正在刷新,无需抢派,属安全跳过而非失败。
        return True, f"self-hosted 派发安全跳过(云端在跑): {cmsg}"
    url = f"https://api.github.com/repos/{REPO}/actions/workflows/{CN_SELFHOSTED_FALLBACK_FILE}/dispatches"
    data = json.dumps({"ref": "main", "inputs": {"category": cat}}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            _record_selfhosted_dispatch(True)
            return True, f"已派发小九应急兜底 category={cat} (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        _record_selfhosted_dispatch(False)
        return False, f"小九应急兜底派发失败 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:150]}"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # 网络层失败(超时/连接重置)降级为派发失败，不向上抛（2026-08-20 一劳永逸兜底）
        _record_selfhosted_dispatch(False)
        return False, f"小九应急兜底派发失败 network: {getattr(e, 'reason', e)}"


# 🔴 2026-08-22 主人令根治：本机看门狗被外部调度每分钟调用一次，
#   曾造成 13:00-16:30「每分钟一个 dispatch」风暴 → concurrency 堆积 → 盘中数据断链。
#   加全局派发冷却锁：无论被调多频繁，每 30 分钟内最多真正派发一次（与 enqueue 同 chokepoint）。
_DISPATCH_LOCK = Path(".workbuddy/v8_dispatch_lock.json")
_GLOBAL_DISPATCH_MIN = 30


def _global_dispatch_allowed():
    now = datetime.now(timezone(timedelta(hours=8)))
    if _DISPATCH_LOCK.exists():
        try:
            st = json.loads(_DISPATCH_LOCK.read_text(encoding="utf-8"))
            last = st.get("last")
            if last:
                age = (now - datetime.fromisoformat(last)).total_seconds() / 60
                if age < _GLOBAL_DISPATCH_MIN:
                    return False, f"全局派发冷却中({age:.0f}min < {_GLOBAL_DISPATCH_MIN}min)"
        except Exception:
            pass
    return True, ""


def _record_global_dispatch():
    try:
        _DISPATCH_LOCK.parent.mkdir(parents=True, exist_ok=True)
        _DISPATCH_LOCK.write_text(
            json.dumps({"last": datetime.now(timezone(timedelta(hours=8))).isoformat()},
                       ensure_ascii=False),
            encoding="utf-8")
    except Exception:
        pass


def auto_dispatch_with_fallback(cat):
    """2026-08-18 主人令：优先派发云端 ubuntu-latest（v8_cn_fetch_cloud.yml）；
    若其最近 failure 或派发失败，自动切到小九 self-hosted cn 应急兜底。
    小九机器只兜底，不主动跑主链路。

    🔴 2026-08-18 主人根治令：云端是【唯一】主力。self-hosted 兜底受 4 重门控
    （连续失败降级 / 30min 静默期 / 云端 in_progress 不抢 / 真超阈才派），
    历史 9+ 连败 → 不再每小时烧 token 重试。

    🔴 2026-08-22 主人令：进入即查全局派发冷却锁，杜绝每分钟风暴。
    """
    allowed, reason = _global_dispatch_allowed()
    if not allowed:
        # 2026-08-24 根因修复：30 分钟全局派发冷却中 = 近期已成功派发，无需再派，
        # 属「安全跳过」而非失败。原 return False 被看门狗当成管线故障，
        # 造成每小时一封 auto_dispatch 失败邮件轰炸（数据其实在正常刷新）。
        return True, f"派发冷却中(近期已派发,安全跳过): {reason}"
    # 先检查主 workflow 最近状态
    ok, msg, is_failure = check_workflow(CN_WORKFLOW_NAME, "cn_fetch", max_age_min=120, workflow_id=CN_WORKFLOW_ID)
    if is_failure:
        # 云端主力最近已 failure，直接派 self-host 兜底（受 3 重门控约束）
        fh_ok, fh_msg = dispatch_selfhosted_fallback(cat)
        if fh_ok:
            _record_global_dispatch()
        return fh_ok, f"云端主力最近 failure → {fh_msg}"
    # 正常路径：尝试派发云端主力 workflow
    d_ok, d_msg = auto_dispatch(cat)
    if d_ok:
        _record_global_dispatch()
        return True, d_msg
    # 派发失败：触发 self-hosted 兜底（受 3 重门控约束）
    fh_ok, fh_msg = dispatch_selfhosted_fallback(cat)
    if fh_ok:
        _record_global_dispatch()
    return fh_ok, f"云端派发失败({d_msg}) → {fh_msg}"


def write_urgent(reason_lines):
    """邮件失败或需要留痕时，写 URGENT 文件到仓库根目录。"""
    ts = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d_%H%M")
    p = Path(f"URGENT_小九_{ts}_v8看门狗告警.md")
    body = [f"# v8 看门狗告警 {ts}", ""] + reason_lines + ["", "请检查 v8_cloud_watchdog.py / v8_health_check.py 日志。"]
    p.write_text("\n".join(body), encoding="utf-8")
    print(f"[INFO] 已写紧急文件 {p}")


def run_health_check(alert=False, heal=True):
    """调用 v8_health_check.py 做完整前端健康检查 + 自动治愈。

    heal 默认 True：确保看门狗每次巡检都触发 self_heal（发现 fail 卡片即派发刷新），
    不再依赖 v8_health_check.py 的 --heal 默认值。2026-08-10 修复：此前未显式传 --heal，
    导致本机看门狗那路自愈形同虚设，运维 stale 全靠人工看图才发现。
    """
    cmd = [sys.executable, "v8_health_check.py"]
    if alert:
        cmd.append("--alert")
    if heal:
        cmd.append("--heal")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=480)
        return result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired as e:
        # 健康检查自身卡死（如 API 持续超时）→ 以专属 rc=3 返回，让看门狗兜底告警，
        # 避免被 send_watchdog_alert 当成「无异常」静默吞掉（2026-08-12 第171轮）。
        return 3, f"调用 v8_health_check.py 超时(>480s): {e}"
    except Exception as e:
        return 1, f"调用 v8_health_check.py 失败: {e}"


def _save_alert_state(path, ts, key):
    """持久化最近一次邮件告警的去抖状态（本机运行态，不进仓库）。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"last_ts": ts, "last_key": key}), encoding="utf-8")
    except Exception:
        pass


def _health_rc_consecutive_bad(rc, threshold=3):
    """记录连续非 0/2 的 health_rc；返回是否达到阈值（持续异常才升级为邮件告警）。

    2026-08-30 一劳永逸修复：health_check rc=3 = 子进程超时/沙箱 urllib 挂死，
    属已知假阳性（handover 8/29 第 N 次证伪）。偶发 rc=3 不邮件轰炸，
    仅当连续 >= threshold 次才视为真故障升级；rc=0/2 会重置计数。
    """
    p = Path(".workbuddy/v8_watchdog_health_state.json")
    try:
        st = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        st = {}
    if rc in (0, 2):
        st["count"] = 0
    else:
        st["count"] = (st.get("count", 0) + 1) if st.get("last_rc") == rc else 1
    st["last_rc"] = rc
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(st), encoding="utf-8")
    except Exception:
        pass
    return st.get("count", 0) >= threshold


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
    # 2026-08-12 第171轮修复：健康检查进程自身崩溃（rc not in {0,2}）时，
    # v8_health_check.py 不会自发邮件，看门狗必须兜底告警，否则 9 张盘中卡陈旧等
    # 真故障会被「无声漏报」。rc=2=有失败项(健康检查已自发邮件)，rc=0=全绿，
    # 其余(1=进程崩退/3=看门狗侧超时)均视为崩溃需兜底。
    # 2026-08-30 一劳永逸：rc=3=子进程超时/沙箱 urllib 挂死（已知假阳性，handover 8/29 第N次证伪）。
    # 偶发 rc=3 不邮件轰炸，仅当连续 >=3 次才升级；rc=0/2 会重置计数。
    _health_persistent = _health_rc_consecutive_bad(health_rc) if health_rc is not None else None
    if health_rc is not None and health_rc not in (0, 2):
        if health_rc == 3 and not _health_persistent:
            print("[INFO] 健康检查超时(rc=3)假阳性规避：偶发超时(疑似网络/沙箱挂死)不邮件告警；连续 3 次才升级")
        else:
            label = "连续超时(rc=3)" if health_rc == 3 else f"进程异常(rc={health_rc})"
            health_alert_items.append(
                f"✗ 健康检查{label}：未生成报告，可能漏报数据陈旧，请查 v8_health_check.py 日志"
            )

    total_alerts = len(infra_fails) + len(health_alert_items)
    if total_alerts == 0:
        print(f"[INFO] watchdog 跳过邮件：无管线异常且健康检查无超阈 ≥ {ALERT_OVERDUE_MIN}min 的项")
        return False

    # 🛡️ 2026-08-16 邮件去抖：同组异常 30min 内只发一封，避免真故障（或周末结构性误报）刷屏
    state_path = Path(".workbuddy/v8_watchdog_alert_state.json")
    try:
        st = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    except Exception:
        st = {}
    key = "|".join(sorted(name for name, ok, msg in results if not ok))
    now_epoch = now_cst.timestamp()
    DEDUPE_MIN = 30
    if st.get("last_ts") and st.get("last_key") == key and (now_epoch - st["last_ts"]) < DEDUPE_MIN * 60:
        print(f"[INFO] 邮件去抖：同组异常[{key}] 距上次告警 {int((now_epoch - st['last_ts']) / 60)}min "
              f"< {DEDUPE_MIN}min，跳过邮件（仅写 URGENT 留痕）")
        write_urgent(infra_fails + health_alert_items)
        _save_alert_state(state_path, now_epoch, key)
        return False

    if quiet:
        print(f"[INFO] 当前处于夜间静音时段（{QUIET_HOURS_START}:00-{QUIET_HOURS_END}:00），"
              f"跳过邮件告警，改写入 URGENT 文件留痕（共 {total_alerts} 项异常）")
        write_urgent(infra_fails + health_alert_items)
        _save_alert_state(state_path, now_epoch, key)
        return False

    subject = f"【v8看门狗告警】{total_alerts}项异常 @ {now}"
    lines = [f"v8 看门狗巡检时间：{now}", f"站点：{SITE_URL}", ""]
    if infra_fails:
        lines.extend(["管线异常：", *infra_fails, ""])
    if health_alert_items:
        lines.extend(["数据陈旧（≥2h）：", *health_alert_items])
    # 🔴 2026-08-30 一劳永逸（主人令「邮件怎么还在报警，赶紧查改一劳永逸式修复」）：
    #   分级交给 v8_send_alert.py 统一闸门判定——
    #     含管线异常（runner 离线 / build 失败 / 站点不可达）→ infra，任何时间都发；
    #     仅「数据陈旧」→ stale，周末与法定节假日静默（非交易日无新数据源属预期）。
    #   主题前缀（机器溯源）由发送器统一加。
    _level = "infra" if infra_fails else "stale"
    ok = send_alert(subject, "\n".join(lines), level=_level)
    if not ok:
        write_urgent(infra_fails + health_alert_items)
    _save_alert_state(state_path, now_epoch, key)
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

    ok, msg, is_failure = check_workflow(CN_WORKFLOW_NAME, "cn_fetch", max_age_min=120, workflow_id=CN_WORKFLOW_ID)
    if not ok and not is_failure and not in_schedule_window("cn_fetch", now_cst):
        ok, msg = True, msg + " —— 非调度时段，豁免（cn_fetch 工作日 cron 08:25~17:20，19:30 后无排程；周末仅 09:00）"
    results.append(("cn_fetch", ok, msg))

    ok, msg, is_failure = check_workflow(BD_WORKFLOW_NAME, "build_deploy", max_age_min=120, workflow_id=BD_WORKFLOW_ID)
    if not ok and not is_failure and not in_schedule_window("build_deploy", now_cst):
        ok, msg = True, msg + " —— 非调度时段，豁免（夜间无上游推送属预期）"
    results.append(("build_deploy", ok, msg))

    # 🔴 2026-09-01 主人令：把盘后算法链纳入看门狗监督（此前完全未监督）。
    #   卡死自愈（cancel+重派 trigger_algo）在 check_algo_chain 内完成；此处只采集结果。
    ok, msg, is_failure = check_algo_chain()
    if not ok and not is_failure and not in_schedule_window("algo", now_cst):
        ok, msg = True, msg + " —— 非调度时段豁免（周末/盘中无盘后选股属预期）"
    results.append(("algo_chain", ok, msg))

    raw_ok, raw_msg = check_raw_data_stale(threshold_min=90)
    if not raw_ok and not in_schedule_window("raw_data", now_cst):
        raw_ok, raw_msg = True, raw_msg + " —— 非调度时段，豁免（周末/夜间数据不刷新属预期）"
    results.append(("raw_data_fresh", raw_ok, raw_msg))

    ok, msg = check_site()
    results.append(("site", ok, msg))

    # === 健康检查（二期）：先跑，生成结构化报告供 auto_dispatch 做逐源决策 ===
    health_rc, health_out = None, None
    if args.health_check:
        health_rc, health_out = run_health_check(alert=args.alert)
        if health_rc != 0:
            print(f"[ALERT] v8_health_check.py 返回非零: {health_rc}")

    # === 自动派发修复（紧急交接核心）：基于健康检查逐源报告 + raw_data commit 兜底 ===
    if args.auto_dispatch:
        dispatched, dispatch_msg = auto_dispatch_smart(now_cst, health_rc, health_out)
        results.append(("auto_dispatch", dispatched, dispatch_msg))
    else:
        results.append(("auto_dispatch", True, "自动派发已关闭（--no-auto-dispatch）"))

    overall = all(ok for _, ok, _ in results)
    # health check 失败也算 overall 失败
    if health_rc is not None and health_rc != 0:
        overall = False
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

    # === 自愈优先（2026-08-16 一劳永逸）：告警前先对 cn_fetch/raw_data 真故障派发重抓 ===
    # 即便本机以 --no-auto-dispatch 运行，真故障也应先自愈，而非直接刷邮件（去抖止刷）。
    # 2026-08-18 升级：self-hosted cn 网络中断时自动 fallback 到 GitHub hosted runner 兜底。
    if not overall and _is_dispatch_active(now_cst):
        for name, ok, msg in list(results):
            if not ok and name in ("cn_fetch", "raw_data_fresh"):
                d_ok, d_msg = auto_dispatch_with_fallback(choose_category(now_cst))
                print(f"[HEAL] {name} FAIL → 已派发自愈: {d_msg}")

    # === 邮件告警 ===
    if args.alert and not overall:
        send_watchdog_alert(now, results, health_rc=health_rc, health_out=health_out)

    sys.exit(0 if overall else 2)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    main()
