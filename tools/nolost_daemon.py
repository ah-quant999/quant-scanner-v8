#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""nolost_daemon.py — 本机常驻的「零丢失」执行器（协议机件）

与云端 .github/workflows/v8_nolost_guard.yml 分工：
  · 云端：每 20 分钟查「远端受保护文件有没有被静默覆盖」→ 自愈（双机都关机也生效）；
  · 本机：每 10 分钟做**云端做不到的三件事**：
      ① 本地快照：受保护文件的当前内容按内容哈希存 backup/nolost/<path>/<sha12>.gz（只增不删）
      ② 未发布账本：把「工作区改了但没推」的受保护文件记进 docs/ops/UNPUBLISHED.json
         ⇒ 小九在我推之前能看见「她/我有哪些改动还没上线上」，不会再出现
           「她的 227 行未发布改动被我的推送静默绕开」这种事。
      ③ 前置自愈：本机体检发现远端被覆盖，就地补回（比等云端最快的那一轮还快）。

铁律：
  · 只碰受保护源文件（algorithms/ docs/ .github/ tools/ index.html 等），
    **绝不触碰 data/ 与 raw_data/**（构建产物，bot 每次重算，动了就会打架）。
  · 绝不自动提交工作区改动（防止把 bot 的盘中脏数据带上线）；只做快照与记账。
  · 凭证类文件（token / cookie / .env / .pem）一律不读不存不推。

用法：
  python3 tools/nolost_daemon.py --once                 # 跑一轮（适合 schtasks / cron）
  python3 tools/nolost_daemon.py --loop --interval 600  # 前台常驻
  python3 tools/nolost_daemon.py --install              # 注册 Windows 计划任务（每 10 分钟，开机自启）
  python3 tools/nolost_daemon.py --status               # 看最近状态
  python3 tools/nolost_daemon.py --uninstall
"""
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "algorithms"))
LEDGER = os.path.join(ROOT, ".nolost_daemon_state.json")
LOCK = os.path.join(ROOT, ".nolost_daemon.lock")
TASK_NAME = "v8-nolost-guard"


def _now():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def _write_state(d):
    try:
        json.dump(d, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    except Exception:
        pass


def _read_state():
    try:
        return json.load(open(LEDGER, encoding="utf-8"))
    except Exception:
        return {}


def _locked(max_age=240):
    """防止 schtasks 叠加执行：锁文件新鲜则跳过。"""
    try:
        st = os.stat(LOCK)
        if time.time() - st.st_mtime < max_age:
            return True
    except FileNotFoundError:
        pass
    try:
        open(LOCK, "w").write(str(os.getpid()))
    except Exception:
        pass
    return False


def run_once(force=False):
    if not force and _locked():
        return {"skipped": True, "reason": "lock fresh"}
    try:
        import nolost_guard as G
    except Exception as e:
        return {"error": f"import nolost_guard 失败: {e}"}
    try:
        out = G.cycle()
        out["daemon_at"] = _now()
        st = _read_state()
        st.update({"last_run": out["daemon_at"], "last": out,
                   "runs": int(st.get("runs", 0)) + 1})
        _write_state(st)
        return out
    except Exception:
        err = traceback.format_exc().strip().splitlines()[-3:]
        st = _read_state()
        st.update({"last_run": _now(), "last_error": err, "runs": int(st.get("runs", 0)) + 1})
        _write_state(st)
        return {"error": err}
    finally:
        try:
            os.remove(LOCK)
        except Exception:
            pass


def install(hours=False):
    """注册 Windows 计划任务：每 10 分钟 + 开机自启，无需管理员（当前用户级）。"""
    if os.name != "nt":
        print("非 Windows：请用 cron，例如 `*/10 * * * * cd %s && python3 tools/nolost_daemon.py --once`" % ROOT)
        return 1
    py = sys.executable
    script = os.path.join(ROOT, "tools", "nolost_daemon.py")
    cmd = f'"{py}" "{script}" --once'
    r = subprocess.run(["schtasks", "/Create", "/TN", TASK_NAME, "/TR", cmd,
                        "/SC", "MINUTE", "/MO", "10", "/F"],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    ok = r.returncode == 0
    if ok:
        # 立即跑一次，证明装好了
        out = run_once(force=True)
        print(json.dumps(out, ensure_ascii=False, indent=2)[:1200])
    return 0 if ok else 1


def uninstall():
    r = subprocess.run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    return 0 if r.returncode == 0 else 1


def status():
    st = _read_state()
    print(json.dumps({"task": TASK_NAME, "state": st}, ensure_ascii=False, indent=2))
    if os.name == "nt":
        r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
                           capture_output=True, text=True)
        print(r.stdout.strip() or r.stderr.strip())
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--interval", type=int, default=600)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.install:
        return install()
    if a.uninstall:
        return uninstall()
    if a.status:
        return status()
    if a.loop:
        print(f"[{_now()}] nolost daemon 启动，间隔 {a.interval}s")
        while True:
            out = run_once()
            print(f"[{_now()}] {json.dumps(out, ensure_ascii=False)[:400]}")
            time.sleep(a.interval)
    out = run_once(force=a.once)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
