#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_peer_monitor.py — 小九心跳监控 + 自动接管（v8 去 v6 化版）
==============================================================
监控小九（单位机）通过 raw_data/hb_xiaojiu.json 上报、云端 build 生成
data/HB_XIAOJIU.js 的心跳；当沉默超过阈值时，发邮件告警并向云端
dispatch rescue workflow。

🔴 2026-09-14 午休一劳永逸四项（主人 08:13 令，诊断档见
   docs/ops/handover/2026-09-14_0855_小九的工程师给阿狸咪的工程师_紧急_*.md）：
   [1] 判定改读**远端权威**（git fetch + git show origin/main:…），不再读工作区文件。
       旧实现 `git pull --ff-only` 在本机（浅克隆 + 常有 WIP）极易失败，失败后
       **静默沿用工作区旧文件**比对 ⇒ 把「小九正常」误判为「掉线」。
       fetch 不受 WIP 影响、浅克隆可用、不碰工作树。
   [2] 心跳产物名统一**大写** HB_XIAOJIU.js（与实产/前端一致）。小写在 Windows
       侥幸能过，换 Linux/mac 必挂。并配套 CI 防漂移门禁（pre_deploy_audit 第 8 项）。
   [3] 阈值**由周期派生**（见下方常量对），不再硬编码 90。实测心跳间隔 61.9~63.1 分钟。
   [4] **监控自证**：每次运行都写「我跑过 + 判定结果」并推送远端（即使不告警），
       使「没告警」与「监控压根没在跑」可区分（旧 `_peer_alert_state.json` 自 7-30
       起没写过任何状态，期间 233 分钟空档都没触发 ⇒ 可观测性失效）。
   [5] 镜像：同时读 `origin/main:data/HB_ALIMI.js` 判**阿狸咪**存活（她落地发送侧后自动生效）。

🔴 2026-09-21 一劳永逸八项（主人令「我要的是科学的一劳永逸解决，不是看证据」）
   ── 根因：本文件曾有**多处硬缺陷**叠加，使「监控没跑」与「对方掉线」**永远无法区分**。
      9-20 阿狸咪心跳卡在 21:57、超阈值 180 分钟却**零告警**，主人靠肉眼才发现。
      线上 `data/_peer_alert_state.json` 实测停在 **2026-07-30**（七周零写入）＝告警路径自那
      日后**从未成功执行过**，与下列 B1/B7 逐项吻合。
   [B1] `_load_alert_state()` 被调用却**从未定义** ⇒ 掉线分支 100% 抛 NameError，
        告警邮件与 rescue dispatch **一次都执行不到**。已补定义。
   [B2] `main()` 只处置小九；`check_alimi_alive` 算出的 down **无任何分支消费**
        ⇒ 阿狸咪掉线永久静默（主人本次踩的正是这条）。已抽出 `handle_side()` 两侧对称，
        并按机侧隔离 `consec_down_<side>` / `last_alert_ts_<side>`。
   [B3] 自证文件写 `data/` 却推 `raw_data/` ⇒ 线上 `data/_peer_monitor_state.json`
        永久 404，自证形同虚设。已统一走 `raw_data/`。
   [B5] `in_monitor_window()` 仅工作日 08:00-21:30 ⇒ 夜间/周末**根本不跑**，
        那两段自证必然断档、又回到 B1 的混淆。已改**全周 24h 常开**
        （逃生舱：env `V8_PEER_MONITOR_WINDOW=workday`）。
   [B7] `_save_alert_state()` **无参且整文件覆盖写**，而调用处传 `consec_down=`
        ⇒ `TypeError`。与 B1 叠加后掉线分支在**两层上都是死的**。已改为「读→合并→写」。
   [B6] `_git()` 硬用裸名 `"git"` ⇒ 计划任务/服务会话 PATH 无 Git（本机 git 在
        `D:/PortableGit` 未进 PATH）时 `FileNotFoundError: [WinError 2]`。已加
        `_resolve_git_exe()`（env `V8_GIT_EXE` → PATH → 常见安装位）。
   [B8] 判定取证只认 `origin/main`，但本仓库实测**该引用根本不存在**
        （显式 refspec fetch 亦不落地）⇒ `git show origin/main:…` 必失败
        ⇒ **fail-closed 假掉线**（会误告警、误 dispatch rescue）。
        已改为 **`FETCH_HEAD` 优先、`origin/main` 备选**。
   [B9] 冷却「本侧键读不到就回落全局键」会退化成全局互压（阿狸咪告警压住小九）
        ⇒ 实测复现，已改为「本侧键存在与否」判定，旧全局键仅作一次性迁移来源。

   ⚠️ 与本次修复**无关但需知悉**：B4（urlopen 无 timeout）在线上这份里**并不存在**，
   三处 urlopen 本就带 timeout（25/60/30s）。此项原判断来自另一份本地草稿，特此澄清。

用法:
  python v8_peer_monitor.py                 # 监控 + 告警 + dispatch rescue
  python v8_peer_monitor.py --alert-only    # 仅告警，不 dispatch
  python v8_peer_monitor.py --self-test     # 只跑判定与解析，不推送/不告警/不 dispatch
"""
import base64
import json
import os
import re
import shutil
import sys
import subprocess
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent

# ── [2] 心跳产物名（大写，与实产/前端一致；跨平台正确）──────────────
#   实产：data/HB_XIAOJIU.js（update_v8 映射 "hb_xiaojiu.json" -> "HB_XIAOJIU"）
#   镜像：data/HB_ALIMI.js （对方落地发送侧后由同一映射链生成）
HB_XIAOJIU_REL = "data/HB_XIAOJIU.js"
HB_ALIMI_REL = "data/HB_ALIMI.js"

# 兼容旧引用的本地路径（**不再用于判定**，仅保留给人工排查）
HB_FILE = BASE / "data" / "HB_XIAOJIU.js"

LOG_FILE = BASE / "data" / "_peer_monitor.log"
ALERT_STATE_FILE = BASE / "data" / "_peer_alert_state.json"
# [4] 监控自证状态文件（每轮运行都写，落 data/ 由 api_push_raw 天然带上远端）
# 🔴 2026-09-21（B3）：写盘目录必须与推送目标 SELFPROOF_REL 严格一致。
#   原为 data/ 却推 raw_data/ ⇒ 线上 data/_peer_monitor_state.json 永久 404。
SELFPROOF_FILE = BASE / "raw_data" / "_peer_monitor_state.json"
SELFPROOF_REL = "raw_data/_peer_monitor_state.json"

# ── [3] 阈值由周期派生（单一真源常量对）───────────────────────────────
#   实测依据（2026-09-14，origin/main 心跳提交时间戳逐条比对）：
#     小九心跳相邻两跳间隔稳定落在 **61.9 ~ 63.1 分钟**（多日样本，极稳，非抖动）。
#   心跳周期**不在任何脚本常量里** —— v8_runner_guard.py 里搜 HEARTBEAT/interval
#   零命中，它只是「每次 guard 运行就写一次」；真实节拍由调度侧决定。
#   ⇒ 故落成契约常量对：改 HEARTBEAT_INTERVAL_MIN 一个数字，阈值自动联动。
#     阈值 = 周期 × 系数 + 余量 = 63 × 2 + 54 = 180 分钟。
#   为什么 ×2 + 余量：63 分钟周期下，阈值若只留 27 分钟裕度（旧值 90），任一跳因
#   盘前启动 / 算法链六唤醒（16:40/18:10/20:00/21:00/22:30/00:30）runner 繁忙晚到即误报；
#   而误报后 ALERT_COOLDOWN_HOURS=6 冷却会**掩盖真掉线**。
HEARTBEAT_INTERVAL_MIN = 63          # 实测 09-14：61.9~63.1 分钟/跳
HEARTBEAT_THRESHOLD_FACTOR = 2       # 允许连续丢 2 跳
HEARTBEAT_GRACE_MIN = 54             # 额外宽限（覆盖 runner 繁忙晚到）
PEER_FAILOVER_THRESHOLD_MIN = HEARTBEAT_INTERVAL_MIN * HEARTBEAT_THRESHOLD_FACTOR + HEARTBEAT_GRACE_MIN   # = 180

ALERT_COOLDOWN_HOURS = 6
# 🔴 2026-09-14 主人令「能自愈的就不要一直发，实在解决不了的才发给我」：反骚扰加固
#   · fetch 抖动 / 远端瞬时读不到 / 解析失败 ⇒ 判「unknown」而非「掉线」→ 静默自愈，绝不发信、绝不 dispatch
#   · 连续 N 次「真·静默超阈值」才升级为掉线并告警（迟滞，滤掉单跳抖动）
#   · 恢复时只清零连续计数，**不**清零告警冷却 ⇒ 抖动期(掉线→在线→掉线)不会反复发信
CONSEC_DOWN_BEFORE_ALERT = 2          # 连续 2 次真·掉线判定才告警
REPO = "ah-quant999/quant-scanner-v8"
GH_API = f"https://api.github.com/repos/{REPO}/contents"

# 优先复用 v8_send_alert.py（配置在 .workbuddy/v8_smtp_config.json）
try:
    from v8_send_alert import send_alert
except Exception:
    send_alert = None


def _load_token():
    for env_name in ("V8_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(env_name)
        if v:
            return v.strip()
    for p in [
        BASE / ".workbuddy" / "v8_gh_token.txt",
        BASE / "data" / ".github_pat.txt",
        Path.home() / ".workbuddy" / "v8_gh_token.txt",
    ]:
        if p.exists():
            try:
                t = p.read_text(encoding="utf-8").strip().lstrip("\ufeff")
            except Exception:
                continue
            if t:
                return t
    return None


# 🔴 2026-09-21 时间锁铁律（B4）：一切网络调用必须带超时。原 _push_selfproof 与
#   dispatch_rescue 的 urlopen **无 timeout** ⇒ 网络卡住会把整个监控挂死，
#   违反主人 2026-09-16「一切可能长跑的命令必须先包时间锁」令。
HTTP_TIMEOUT_S = 30


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── [1] 远端权威读取（不碰工作树）──────────────────────────────────────

_GIT_EXE_CACHE = [None]


def _resolve_git_exe():
    """🔴 2026-09-21 一劳永逸（B6）：原实现硬用裸名 "git" ⇒ 在**计划任务/服务会话**里
    （PATH 不含 Git，本机 git 装在 D:/PortableGit 却未进 PATH）subprocess 直接
    `FileNotFoundError: [WinError 2]` ⇒ fetch 永久失败 ⇒ 两侧判定全废、
    自证文件却照旧推送 ⇒ 回到「静默 vs 监控没跑」无法区分。实测已复现该 WinError。

    解析顺序：env V8_GIT_EXE → PATH 里的 git → 常见安装位（含 WorkBuddy PortableGit）。"""
    if _GIT_EXE_CACHE[0]:
        return _GIT_EXE_CACHE[0]
    cands = []
    env_exe = (os.environ.get("V8_GIT_EXE") or "").strip()
    if env_exe:
        cands.append(env_exe)
    w = shutil.which("git")
    if w:
        cands.append(w)
    cands += [
        r"D:\PortableGit\cmd\git.exe",
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files (x86)\Git\cmd\git.exe",
        r"E:\PortableGit\cmd\git.exe",
    ]
    for base in (Path.home() / ".workbuddy" / "binaries" / "PortableGit",
                 Path("E:/workbuddy/resources/app.asar.unpacked/cli/vendor/git")):
        try:
            for hit in sorted(base.glob("**/git.exe")):
                cands.append(str(hit))
        except Exception:
            pass
    for c in cands:
        try:
            if c and Path(c).exists():
                _GIT_EXE_CACHE[0] = c
                return c
        except Exception:
            continue
    _GIT_EXE_CACHE[0] = "git"
    return "git"


def _git(*argv, timeout=60):
    """跑一条 git 命令，返回 (rc, stdout, stderr)。"""
    try:
        r = subprocess.run(
            [_resolve_git_exe(), "-c", "http.version=HTTP/1.1",
             "-c", "core.quotepath=false", *argv],
            cwd=BASE, capture_output=True, text=True, timeout=timeout,
        )
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return 1, "", f"{type(e).__name__}: {e}"


def fetch_origin_main():
    """只 fetch，不动工作树、不动本地分支。浅克隆 / 部分克隆 / blobless 克隆同样可用。

    🔴 2026-09-21（B8 实测修正）：本仓库实测 `remote.origin.fetch` 为
    `+refs/heads/*:refs/remotes/origin/*`，但 **`refs/remotes/origin/main` 并不存在**
    （`git branch -a` 无 `remotes/origin/main`）。即使显式 `fetch +refs/heads/main:refs/remotes/origin/main`
    返回 rc=0 且打印「new branch main -> origin/main」，`rev-parse --verify` 仍报
    `fatal: Needed a single revision` ⇒ 该仓库的远端引用层不可靠。

    ⇒ 结论：**判定必须以 `FETCH_HEAD` 为唯一可靠取证**（fetch 成功即成立），
    `origin/main` 降级为尽力而为的备选。原实现只认 `origin/main`
    ⇒ 在无该引用的克隆里 `git show` 必失败 ⇒ **fail-closed 假掉线**。"""
    rc, out, err = _git("fetch", "--depth=1", "origin", "main", timeout=90)
    if rc != 0:
        rc, out, err = _git("fetch", "origin", "main", timeout=90)
    if rc != 0:
        return False, (err or out or "").strip()[:200]
    return True, (err or out or "").strip()[:200] or "ok"


def _read_remote_file(rel_path):
    """读远端 main 上 `rel_path` 的原文；失败返回 (None, 原因)。不碰工作树。

    🔴 2026-09-21（B8 实测修正）：**先 `FETCH_HEAD`（可靠）、再 `origin/main`（备选）**。
    实测本仓库 `origin/main` 引用缺失而 `FETCH_HEAD` 正常，故顺序不可颠倒。"""
    rc, out, err = _git("show", f"FETCH_HEAD:{rel_path}", timeout=60)
    if rc == 0 and out.strip():
        return out, ""
    rc2, out2, err2 = _git("show", f"origin/main:{rel_path}", timeout=60)
    if rc2 == 0 and out2.strip():
        return out2, ""
    return None, (err or err2 or "").strip()[:160]


def _load_hb_from_text(text, var_name):
    """解析 `window.<var_name> = {...};` 为 dict，失败返回 None。"""
    if not text:
        return None
    m = re.search(r"window\.%s\s*=\s*(\{.*?\})\s*;" % re.escape(var_name), text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def _silent_minutes(last_ts):
    """把 CST '%Y-%m-%d %H:%M:%S' 转成「距今多少分钟」。解析失败抛异常。"""
    peer_time = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
    return (datetime.now() - peer_time).total_seconds() / 60.0


def check_peer_alive(rel_path=HB_XIAOJIU_REL, var_name="HB_XIAOJIU", peer_name="小九",
                     fetched=None):
    """判对方是否存活。返回 (alive, silent_min, last_time, detail)。

    [1] 判定**只读远端权威**（origin/main），不读工作区文件：
        她的工作区可能 WIP/陈旧，读它 = 用旧值比对 ⇒ 误报。

    fail-closed 保留（2026-09-12 主人令）：远端读不到 / 无 last_time / 解析失败
    ⇒ 判【掉线】。但此时 detail 会写明取证方式，与「真沉默」可区分。
    """
    if fetched is None:
        fetched, fmsg = fetch_origin_main()
    else:
        fmsg = ""
    if not fetched:
        log(f"  🔴 git fetch origin main 失败（{fmsg}）→ fail-closed")
        return False, 9999, "", f"fetch 失败: {fmsg}"

    text, rerr = _read_remote_file(rel_path)
    if text is None:
        log(f"  🔴 origin/main:{rel_path} 读不到（{rerr}）→ 判{peer_name}【掉线】(fail-closed)")
        return False, 9999, "", f"远端无 {rel_path}: {rerr}"

    hb = _load_hb_from_text(text, var_name)
    if hb is None:
        log(f"  🔴 origin/main:{rel_path} 解析失败（window.{var_name} 缺失/非法）→ 判{peer_name}【掉线】(fail-closed)")
        return False, 9999, "", "远端产物解析失败"

    last_ts = (hb.get("last_time") or "").strip()
    if not last_ts:
        log(f"  🔴 origin/main:{rel_path} 无 last_time → 判{peer_name}【掉线】(fail-closed)")
        return False, 9999, "", "远端产物无 last_time"

    try:
        elapsed = _silent_minutes(last_ts)
    except Exception as e:
        log(f"  🔴 解析 last_time 失败: {e} → 判{peer_name}【掉线】(fail-closed)")
        return False, 9999, "", f"last_time 解析失败: {e}"

    machine = hb.get("machine", "?")
    detail = f"远端权威 origin/main:{rel_path} · last_time={last_ts} · machine={machine} · 沉默 {elapsed:.0f}min"
    return ("down" if elapsed >= PEER_FAILOVER_THRESHOLD_MIN else "alive"), elapsed, last_ts, detail


def check_alimi_alive(fetched=None):
    """[5] 镜像逻辑：读远端 data/HB_ALIMI.js 判阿狸咪是否存活。
    对方落地发送侧（raw_data/hb_alimi.json）后本函数自动生效；
    产物不存在 ⇒ 视作「未知」（None），不误报。"""
    if fetched is None:
        fetched, _ = fetch_origin_main()
    if not fetched:
        return "unknown", None, "", "fetch 失败"
    text, rerr = _read_remote_file(HB_ALIMI_REL)
    if text is None:
        return "unknown", None, "", f"远端尚无 {HB_ALIMI_REL}（对方发送侧未落地）"
    hb = _load_hb_from_text(text, "HB_ALIMI")
    if not hb:
        return "unknown", None, "", f"{HB_ALIMI_REL} 解析失败"
    last_ts = (hb.get("last_time") or "").strip()
    if not last_ts:
        return "unknown", None, "", f"{HB_ALIMI_REL} 无 last_time"
    try:
        elapsed = _silent_minutes(last_ts)
    except Exception as e:
        return "unknown", None, "", f"last_time 解析失败: {e}"
    return ("down" if elapsed >= PEER_FAILOVER_THRESHOLD_MIN else "alive"), elapsed, last_ts, (
        f"{HB_ALIMI_REL} · last_time={last_ts} · machine={hb.get('machine','?')} · 沉默 {elapsed:.0f}min")


def _alert_cooldown_active(side="xiaoju"):
    """🔴 2026-09-21（B2-1）：冷却按机侧隔离。原为单一全局 last_alert_ts
    ⇒ 小九告警会把阿狸咪的告警一并压住（冷却期 6h 内对方再有事也不发信）。

    🔴 隔离铁律：**只认本机侧的 `last_alert_ts_<side>`**。
    旧全局键 `last_alert_ts` 仅当本侧键**完全不存在**时才作为一次性迁移来源，
    且**只对 xiaoju 生效**（历史上只有小九侧写过它）。
    若用「本侧键读不到就回落全局键」的写法，会退化成原来的全局互压 —— 实测已复现
    （阿狸咪告警后小九侧被压住），故此处必须是「存在与否」判定，不是「真值」判定。"""
    try:
        st = _load_alert_state()
        key = f"last_alert_ts_{side}"
        if key in st:
            last = st.get(key)
        elif side == "xiaoju":
            last = st.get("last_alert_ts")      # 一次性迁移来源
        else:
            last = None
        if last:
            last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - last_dt).total_seconds() < ALERT_COOLDOWN_HOURS * 3600:
                return True
    except Exception:
        pass
    return False


def _load_alert_state():
    """🔴 2026-09-21 一劳永逸（B1）：本函数此前**从未定义**，却被 _alert_cooldown_active
    与 reset_consec_counter 各调用一次 ⇒ 一旦进入「真·掉线」分支，立刻
    `NameError: _load_alert_state is not defined` ⇒ 掉线分支 100% 抛异常，
    告警邮件与 rescue dispatch **一次都执行不到**。

    这是「阿狸咪心跳超阈值却零告警」的直接根因，也是「静默」与「监控没跑」
    永远无法区分的技术原因。线上 data/_peer_alert_state.json 实测停在
    2026-07-30（七周无写入）即此项所致。

    统一返回 dict（读失败给空 dict ⇒ 抑制阈值视作 0 ⇒ 宁可多报不可漏报）。"""
    try:
        if ALERT_STATE_FILE.exists():
            st = json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(st, dict):
                return st
    except Exception as e:
        log(f"  ⚠️ 读取告警状态失败（按空处理）: {e}")
    return {}


def _save_alert_state(consec_down=None, extra=None):
    """🔴 2026-09-21 一劳永逸（B7）：原实现**无参且整文件覆盖写**，只写 last_alert_ts。
    而 main() 里调的是 `_save_alert_state(consec_down=consec)` ⇒ 直接
    `TypeError: _save_alert_state() got an unexpected keyword argument 'consec_down'`。
    与 B1 叠加后：掉线分支先撞 B1(NameError)、修好 B1 又撞 B7(TypeError)
    ⇒ **告警路径在两层上都是死的**，这就是线上 _peer_alert_state.json 自
    2026-07-30 起七周零写入的直接原因。

    改为「读 → 合并 → 写」，向后兼容两种调用：
      _save_alert_state()                       # 旧式：只记「刚告警」
      _save_alert_state(consec_down=2)          # 记连续掉线次数
      _save_alert_state(extra={"k": v})         # 任意附加字段
    """
    try:
        ALERT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        st = _load_alert_state()
        if not isinstance(st, dict):
            st = {}
        if consec_down is not None:
            st["consec_down"] = int(consec_down)
        if extra and isinstance(extra, dict):
            st.update(extra)
        ALERT_STATE_FILE.write_text(
            json.dumps(st, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log(f"  ⚠️ 写入告警状态失败: {e}")


# ── [4] 监控自证：每轮运行都留「跑过 + 判定结果」并推送 ──────────────────

def _selfproof_path():
    return SELFPROOF_FILE


def _write_selfproof(payload):
    """写本地自证状态（落 data/，由 api_push_raw.walk_extra 白名单带上远端）。"""
    try:
        SELFPROOF_FILE.parent.mkdir(parents=True, exist_ok=True)
        SELFPROOF_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception as e:
        log(f"  ⚠️ 自证状态写入失败: {e}")
        return False


def _host_name():
    return (os.environ.get("V8_ALERT_HOST")
            or os.environ.get("COMPUTERNAME")
            or os.environ.get("HOSTNAME")
            or "unknown-host")


def _push_selfproof(local_path):
    """把自证状态推送到远端 `raw_data/_peer_monitor_state.json`（Contents API，与
    心跳推送同源；不经过本地 git commit ⇒ 不碰工作树、不与任何本机推仓任务抢道）。
    失败只记日志，绝不阻断主流程。"""
    token = _load_token()
    if not token:
        return False, "无 GitHub token，跳过自证推送"
    rel = "raw_data/_peer_monitor_state.json"
    url = f"{GH_API}/{rel}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }
    try:
        content = local_path.read_bytes()
        sha = None
        remote_b64 = ""
        try:
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=25) as r:
                remote = json.loads(r.read().decode("utf-8"))
                sha = remote.get("sha")
                remote_b64 = remote.get("content", "") or ""
        except urllib.error.HTTPError as e:
            if e.code != 404:
                return False, f"GET sha 失败: HTTP {e.code}"
        except Exception as e:
            return False, f"GET sha 异常: {e}"
        if sha and remote_b64:
            try:
                if base64.b64decode(remote_b64.replace("\n", "")) == content:
                    return True, "远端自证状态已是最新，跳过推送"
            except Exception:
                pass
        payload = {
            "message": f"data: peer monitor 自证 {datetime.now().strftime('%Y%m%d-%H%M')}",
            "content": base64.b64encode(content).decode("utf-8"),
        }
        if sha:
            payload["sha"] = sha
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers=headers, method="PUT")
        with urllib.request.urlopen(req, timeout=60) as r:
            return True, f"HTTP {r.status}"
    except urllib.error.HTTPError as e:
        return False, f"Contents API 失败: HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:160]}"
    except Exception as e:
        return False, f"Contents API 异常: {e}"


def self_proof(run_ctx):
    """[4] 落盘 + 推送「本轮跑过 + 判定结果」。run_ctx 为判定上下文 dict。"""
    payload = {
        "runner": "v8_peer_monitor",
        "host": _host_name(),
        "run_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "threshold_min": PEER_FAILOVER_THRESHOLD_MIN,
        "interval_min": HEARTBEAT_INTERVAL_MIN,
        "xiaoju": {
            "alive": run_ctx.get("xj_alive"),
            "silent_min": (round(run_ctx["xj_silent"], 1)
                           if isinstance(run_ctx.get("xj_silent"), (int, float)) else run_ctx.get("xj_silent")),
            "last_time": run_ctx.get("xj_last", ""),
            "detail": run_ctx.get("xj_detail", ""),
        },
        "alimi": {
            "alive": run_ctx.get("al_alive"),
            "silent_min": (round(run_ctx["al_silent"], 1)
                           if isinstance(run_ctx.get("al_silent"), (int, float)) else run_ctx.get("al_silent")),
            "last_time": run_ctx.get("al_last", ""),
            "detail": run_ctx.get("al_detail", ""),
        },
        "verdict": run_ctx.get("verdict", ""),
        "note": "本文件由 v8_peer_monitor 每轮运行覆盖写 ⇒ 「没告警」与「监控没在跑」可区分",
    }
    if run_ctx.get("run_ctx_extra"):
        payload.update(run_ctx["run_ctx_extra"])
    if not _write_selfproof(payload):
        return False
    if os.environ.get("V8_SKIP_SELFPROOF_PUSH") == "1":
        log("  ⏭️ V8_SKIP_SELFPROOF_PUSH=1，跳过自证推送")
        return True
    ok, msg = _push_selfproof(SELFPROOF_FILE)
    log(f"  {'✅' if ok else '⚠️'} 自证推送: {msg}")
    return ok


def send_alert_email(silent_min, hb_last_time, peer_name="小九", side="xiaoju"):
    now = datetime.now()
    if _alert_cooldown_active(side):
        log(f"  ⏳ {peer_name} 邮件告警冷却中（{ALERT_COOLDOWN_HOURS}h），本次跳过")
        return False

    subject = f"🚨 v8 {peer_name}失联告警 ({now.strftime('%m-%d %H:%M')})"
    body = (
        "【九宝量化 v8 双机监控告警】\n\n"
        f"检测到 {peer_name} 心跳失联！\n\n"
        f"· {peer_name}最后心跳：{hb_last_time}\n"
        f"· 已沉默：{silent_min:.0f} 分钟（阈值 {PEER_FAILOVER_THRESHOLD_MIN} 分钟"
        f" = 周期 {HEARTBEAT_INTERVAL_MIN} × {HEARTBEAT_THRESHOLD_FACTOR} + 余量 {HEARTBEAT_GRACE_MIN}）\n"
        f"· 判定取证：远端权威 origin/main（非本地工作区）\n"
        f"· 检测时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "· 当前动作：已 dispatch v8 rescue workflow（云端兜底）\n\n"
        f"可能原因：{peer_name}停电 / 断网 / 系统崩溃 / 进程卡死。\n"
        "请确认状态；云端 rescue 已启动，若持续失联会反复兜底。\n\n"
        "---\nv8_peer_monitor.py 发送"
    )
    if send_alert:
        ok = send_alert(subject, body)
        if ok:
            _save_alert_state(extra={
                f"last_alert_ts_{side}": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                f"last_alert_peer_{side}": peer_name})
        return ok
    log("  ⚠️ v8_send_alert 未加载，无法发邮件")
    return False


def reset_consec_counter(side="xiaoju"):
    """对方恢复在线：只清零**该机侧**的「连续掉线计数」，🔴 绝不触碰 last_alert_ts 冷却。
    这样抖动期(掉线→在线→掉线)不会因冷却被清零而反复发信。
    🔴 2026-09-21（B2-2）：原无参、只有一个全局 consec_down ⇒ 双机计数互相污染
    （小九恢复会把阿狸咪的连败计数一并清零，反之亦然）。改为按机侧分别计数。"""
    key = f"consec_down_{side}"
    st = _load_alert_state()
    if side == "xiaoju":
        legacy = int(st.get("consec_down", 0) or 0)
    else:
        legacy = 0
    if int(st.get(key, 0) or 0) != 0 or legacy != 0:
        extra = {key: 0}
        if side == "xiaoju":
            extra["consec_down"] = 0
        _save_alert_state(extra=extra)


def handle_side(side, status, silent_min, hb_last, detail, peer_name, kind):
    """🔴 2026-09-21 新增（B2）：把「某机侧判定结果的处置」统一为**一条链路**，
    使两侧完全对称。原 main() 只处置小九——`check_alimi_alive()` 算出的 down
    被塞进 run_ctx 后再无任何分支消费 ⇒ **阿狸咪掉线永久静默**，
    正是主人在 9-20 亲眼看到「HB_ALIMI 卡在 21:57、超阈值却零告警」的原因。

    kind: "peer" = 对方机（小九）→ 掉线时 dispatch rescue 云端兜底
          "self" = 本机镜像（阿狸咪）→ 掉线时只告警，不 dispatch
                 （她本身不是兜底对象，dispatch 主链也救不了她的心跳）

    返回 exit code（0=正常/静默自愈，1=已确认异常）。"""
    if status == "alive":
        log(f"✅ {peer_name}正常（最近心跳 {silent_min:.0f} 分钟前） | {detail}")
        reset_consec_counter(side)
        return 0

    if status == "unknown":
        log(f"⚠️ {peer_name}心跳判定为「未知」(瞬时抖动: {detail})，静默自愈，下一轮再判")
        return 0

    # —— status == "down"：真·静默超阈值 ——
    key = f"consec_down_{side}"
    st = _load_alert_state()
    consec = int(st.get(key, 0) or 0) + 1
    if side == "xiaoju" and consec < int(st.get("consec_down", 0) or 0) + 1:
        consec = int(st.get("consec_down", 0) or 0) + 1
    _save_alert_state(extra={key: consec, "consec_down": consec} if side == "xiaoju"
                      else {key: consec})

    if consec < CONSEC_DOWN_BEFORE_ALERT:
        log(f"🔸 {peer_name}疑似掉线（连续第 {consec} 次，需 {CONSEC_DOWN_BEFORE_ALERT} 次才告警）"
            f"→ 观察中，暂不打扰 | {detail}")
        return 1

    if _alert_cooldown_active(side):
        log(f"🔴 {peer_name}已确认掉线（{silent_min:.0f}min>阈值），冷却中跳过邮件 | {detail}")
        if kind == "peer" and "--alert-only" not in sys.argv:
            dispatch_rescue()
        return 1

    send_alert_email(silent_min, hb_last, peer_name=peer_name, side=side)
    if kind == "peer" and "--alert-only" not in sys.argv:
        dispatch_rescue()
    return 1


def dispatch_rescue():
    """小九掉线时，向云端 dispatch 现存主链 workflow（v8_cn_fetch_cloud.yml / v8_algo_cloud.yml）补跑"""
    token = _load_token()
    if not token:
        log("  ❌ 未找到 GitHub token，无法 dispatch rescue")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    results = []
    # ✅ 2026-08-29 一劳永逸：dispatch 现存主链。删掉的 v8_safety_net.yml / v8_self_heal.yml
    #   已不存在（git log 1fe4f8c71 删），原派发 404/410。改为 dispatch v8_cn_fetch_cloud（盘中/盘后
    #   中国数据抓取）+ v8_algo_cloud（收盘后算法数据生产）—— 两者都是云端主链，可独立 workflow_dispatch。
    for wf in ["v8_cn_fetch_cloud.yml", "v8_algo_cloud.yml"]:
        url = f"https://api.github.com/repos/{REPO}/actions/workflows/{wf}/dispatches"
        data = json.dumps({"ref": "main"}).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                results.append((wf, True, f"HTTP {r.status}"))
        except Exception as e:
            results.append((wf, False, str(e)[:120]))
    for wf, ok, msg in results:
        log(f"  {'✅' if ok else '❌'} dispatch {wf}: {msg}")
    return all(ok for _, ok, _ in results)


def in_monitor_window():
    """🔴 2026-09-21 一劳永逸（B5）：原为「仅工作日 08:00-21:30」⇒ 夜间与周末**完全不跑**，
    那两段自证必然断档 ⇒ 「监控没跑」与「对方掉线」再次混淆（正是 B1 赖以藏身的盲区）。

    改为**全周 24 小时常开**（与「心跳腿全周 BYHOUR=7..23」对齐）；
    监控若不常开，就无法判「心跳腿本身挂了」。
    如需恢复旧窗口：设 env V8_PEER_MONITOR_WINDOW=workday。"""
    mode = (os.environ.get("V8_PEER_MONITOR_WINDOW") or "always").strip().lower()
    if mode == "workday":
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        h, m_ = now.hour, now.minute
        return 8 * 60 <= h * 60 + m_ <= 21 * 60 + 30
    return True



def main():
    if "--self-test" in sys.argv:
        fetched, fmsg = fetch_origin_main()
        print(f"fetch ok={fetched} {fmsg}")
        status, silent, last, detail = check_peer_alive(fetched=fetched)
        print(f"小九 status={status} silent={silent} last={last}\n  {detail}")
        aa, as_, al, ad = check_alimi_alive(fetched=fetched)
        print(f"阿狸咪 status={aa} silent={as_} last={al}\n  {ad}")
        print(f"阈值 = {HEARTBEAT_INTERVAL_MIN} × {HEARTBEAT_THRESHOLD_FACTOR} + {HEARTBEAT_GRACE_MIN}"
              f" = {PEER_FAILOVER_THRESHOLD_MIN}；连续 {CONSEC_DOWN_BEFORE_ALERT} 次才告警；冷却 {ALERT_COOLDOWN_HOURS}h（恢复不重置）")
        return 0

    if not in_monitor_window():
        log("⏭️ 非监控窗口（V8_PEER_MONITOR_WINDOW=workday 且当前在工作日 08:00-21:30 之外），跳过")
        return 0

    # [1] 一次 fetch 供两侧判定复用
    fetched, fmsg = fetch_origin_main()
    if not fetched:
        log(f"  ⚠️ fetch 失败: {fmsg}")

    status, silent_min, hb_last, detail = check_peer_alive(fetched=fetched)
    al_status, al_silent, al_last, al_detail = check_alimi_alive(fetched=fetched)

    # [4] 无论结论如何，先落自证（含两侧判定）
    run_ctx = {
        "xj_status": status, "xj_alive": (status == "alive"),
        "xj_silent": silent_min, "xj_last": hb_last, "xj_detail": detail,
        "al_status": al_status, "al_alive": (al_status == "alive"),
        "al_silent": al_silent, "al_last": al_last, "al_detail": al_detail,
        "verdict": f"xj={status}/al={al_status}",
        "monitor_window": "always",
    }

    # 🔴 2026-09-21 一劳永逸（B2）：两侧**完全对称**处置。
    #   原实现只处置小九；阿狸咪侧算完 al_status 后仅写入自证、无任何告警分支
    #   ⇒ 阿狸咪掉线**永远静默**（主人本次踩到的正是这条）。
    rc_xj = handle_side("xiaoju", status, silent_min, hb_last, detail,
                        peer_name="小九", kind="peer")
    rc_al = handle_side("alimi", al_status, al_silent, al_last, al_detail,
                        peer_name="阿狸咪", kind="self")

    run_ctx["verdict_xj"] = status
    run_ctx["verdict_al"] = al_status
    self_proof(run_ctx)
    return 1 if (rc_xj == 1 or rc_al == 1) else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
