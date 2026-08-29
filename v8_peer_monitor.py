#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_peer_monitor.py — 小九心跳监控 + 自动接管（v8 去 v6 化版）
==============================================================
监控小九（单位机）通过 data/hb_xiaojiu.json 推送的心跳；
当沉默超过阈值时，发邮件告警并向云端 dispatch rescue workflow。

用法:
  python v8_peer_monitor.py              # 监控 + 告警 + dispatch rescue
  python v8_peer_monitor.py --alert-only # 仅告警，不 dispatch
"""
import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
HB_FILE = BASE / "data" / "hb_xiaojiu.json"
LOG_FILE = BASE / "data" / "_peer_monitor.log"
ALERT_STATE_FILE = BASE / "data" / "_peer_alert_state.json"
PEER_FAILOVER_THRESHOLD_MIN = 90
ALERT_COOLDOWN_HOURS = 6
REPO = "ah-quant999/quant-scanner-v8"

# 优先复用 v8_send_alert.py（配置在 .workbuddy/v8_smtp_config.json）
try:
    from v8_send_alert import send_alert
except Exception:
    send_alert = None


def _load_token():
    if os.environ.get("V8_GITHUB_TOKEN"):
        return os.environ["V8_GITHUB_TOKEN"]
    for p in [
        BASE / ".workbuddy" / "v8_gh_token.txt",
        Path.home() / ".workbuddy" / "v8_gh_token.txt",
    ]:
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    return None


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _git_pull():
    """轻量拉取最新 main，确保拿到最新心跳文件。"""
    try:
        r = subprocess.run(
            ["git", "-c", "http.version=HTTP/1.1", "pull", "--ff-only", "origin", "main"],
            cwd=BASE, capture_output=True, text=True, timeout=60,
        )
        if r.returncode != 0:
            log(f"  ⚠️ git pull 失败: {r.stderr[:200]}")
    except Exception as e:
        log(f"  ⚠️ git pull 异常: {e}")


def check_peer_alive():
    """返回 (alive, silent_min, last_time)"""
    _git_pull()
    if not HB_FILE.exists():
        log("  ⚠️ hb_xiaojiu.json 不存在，默认认为小九活着（可能从未初始化）")
        return True, 0, ""
    try:
        hb = json.loads(HB_FILE.read_text(encoding="utf-8"))
        last_ts = hb.get("last_time", "")
        if not last_ts:
            log("  ⚠️ hb_xiaojiu.json 无 last_time 字段")
            return True, 0, ""
        peer_time = datetime.strptime(last_ts, "%Y-%m-%d %H:%M:%S")
        elapsed = (datetime.now() - peer_time).total_seconds() / 60.0
        return elapsed < PEER_FAILOVER_THRESHOLD_MIN, elapsed, last_ts
    except Exception as e:
        log(f"  ❌ 读 hb_xiaojiu.json 失败: {e}")
        return True, 0, ""


def _alert_cooldown_active():
    try:
        if ALERT_STATE_FILE.exists():
            st = json.loads(ALERT_STATE_FILE.read_text(encoding="utf-8"))
            last = st.get("last_alert_ts")
            if last:
                last_dt = datetime.strptime(last, "%Y-%m-%d %H:%M:%S")
                if (datetime.now() - last_dt).total_seconds() < ALERT_COOLDOWN_HOURS * 3600:
                    return True
    except Exception:
        pass
    return False


def _save_alert_state():
    try:
        ALERT_STATE_FILE.write_text(
            json.dumps({"last_alert_ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def send_alert_email(silent_min, hb_last_time):
    now = datetime.now()
    if _alert_cooldown_active():
        log(f"  ⏳ 邮件告警冷却中（{ALERT_COOLDOWN_HOURS}h），本次跳过")
        return False

    subject = f"🚨 v8 小九失联告警 ({now.strftime('%m-%d %H:%M')})"
    body = (
        "【九宝量化 v8 双机监控告警】\n\n"
        "阿狸咪（家里机）检测到小九（单位机）心跳失联！\n\n"
        f"· 小九最后心跳：{hb_last_time}\n"
        f"· 已沉默：{silent_min:.0f} 分钟（阈值 {PEER_FAILOVER_THRESHOLD_MIN} 分钟）\n"
        f"· 检测时间：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
        "· 当前动作：已 dispatch v8 rescue workflow（云端兜底）\n\n"
        "可能原因：小九停电 / 断网 / 系统崩溃 / 进程卡死。\n"
        "请确认小九状态；云端 rescue 已启动，若持续失联会反复兜底。\n\n"
        "---\nv8_peer_monitor.py 发送"
    )
    if send_alert:
        ok = send_alert(subject, body)
        if ok:
            _save_alert_state()
        return ok
    log("  ⚠️ v8_send_alert 未加载，无法发邮件")
    return False


def reset_alert_state():
    try:
        if ALERT_STATE_FILE.exists():
            ALERT_STATE_FILE.unlink()
    except Exception:
        pass


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
        req = __import__("urllib.request").request.Request(url, data=data, headers=headers, method="POST")
        try:
            with __import__("urllib.request").request.urlopen(req, timeout=30) as r:
                results.append((wf, True, f"HTTP {r.status}"))
        except Exception as e:
            results.append((wf, False, str(e)[:120]))
    for wf, ok, msg in results:
        log(f"  {'✅' if ok else '❌'} dispatch {wf}: {msg}")
    return all(ok for _, ok, _ in results)


def in_monitor_window():
    """仅工作日 08:00-21:30 监控；周末小九本来就不跑盘中。"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    h, m = now.hour, now.minute
    start = 8 * 60
    end = 21 * 60 + 30
    return start <= h * 60 + m <= end


def main():
    if not in_monitor_window():
        log("⏭️ 非监控窗口（工作日 08:00-21:30），跳过")
        return 0

    alive, silent_min, hb_last = check_peer_alive()
    if alive:
        log(f"✅ 小九正常（最近心跳 {silent_min:.0f} 分钟前）")
        reset_alert_state()
        return 0

    log(f"🔴 小九心跳已 {silent_min:.0f} 分钟（> {PEER_FAILOVER_THRESHOLD_MIN}min），判为掉线！")
    send_alert_email(silent_min, hb_last)

    if "--alert-only" in sys.argv:
        log("🚨 ALERT-ONLY 模式：仅报警，不 dispatch rescue。请人工确认小九状态！")
        return 1

    dispatch_rescue()
    return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
