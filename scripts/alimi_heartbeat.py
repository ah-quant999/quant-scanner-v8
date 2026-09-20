#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
alimi_heartbeat.py — 阿狸咪（家机 alimi-cn）心跳上报
====================================================
写入 raw_data/hb_alimi.json 并经 Contents API 推送到 main；云端 build 的
部署步跑【全量】update_v8.py，据 DATA_SOURCES 映射
`"hb_alimi.json" -> "HB_ALIMI"` 生成 data/HB_ALIMI.js（window.HB_ALIMI）。

用途：补齐「双机互看」的**反向心跳腿**。小九侧由 v8_runner_guard.py 的
write_heartbeat()/push_heartbeat() 写 raw_data/hb_xiaojiu.json
(machine=lemoncat-cn)；本脚本是阿狸咪侧的对称实现（machine=alimi-cn）。
接收侧：v8_peer_monitor.py 的 check_alimi_alive() 读 data/HB_ALIMI.js 判定，
阈值 = 63 x 2 + 54 = 180 分钟；产物不存在时判 "unknown"（不误报）。

🔴 2026-09-14 主人令（反向心跳·第 5 条我方半）：「发送侧（写 raw_data/hb_alimi.json）
   由阿狸咪独占落地」。本脚本即该落地件。此前该文件一直不存在 —— 后果不是误报，
   而是「对方永远看不到我活着」（check_alimi_alive 恒为 unknown）＋ 层一致性校验
   持续吐一条「缺失 raw_data: HB_ALIMI」噪声。

字段格式与小九侧**逐字对齐**（4 字段）：
  { "last_time": "YYYY-MM-DD HH:MM:SS", "status": "ok",
    "machine": "alimi-cn", "source": "alimi_heartbeat" }

用法：
  python scripts/alimi_heartbeat.py              # 写文件 + 推送（默认）
  python scripts/alimi_heartbeat.py --check      # 只读现状，不写不推
  python scripts/alimi_heartbeat.py --dry-run    # 写文件但不推送
  python scripts/alimi_heartbeat.py --force      # 忽略幂等窗口，强制刷新
  python scripts/alimi_heartbeat.py --quiet      # 静默成功（仅异常输出）

退出码：0 成功 / 1 失败
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "raw_data" / "hb_alimi.json"
TARGET_REL = "raw_data/hb_alimi.json"
REPO = "ah-quant999/quant-scanner-v8"
MACHINE = "alimi-cn"
SOURCE = "alimi_heartbeat"
# 节拍契约：调度侧理应 ~60 分钟一跳。25 分钟窗口用于吃掉「同小时内重复触发」
# （手动重跑 / 任务补偿），不影响正常跳。真周期由 automation 的 rrule 决定。
MIN_GAP_MIN = 25


def _load_token():
    """PAT 多源探测（禁写死任何文件）。家机单点 = ~/.workbuddy/v8_gh_pat。"""
    cands = [
        Path.home() / ".workbuddy" / "v8_gh_pat",
        Path.home() / ".workbuddy" / "v8_gh_token.txt",
        ROOT / "data" / ".github_pat.txt",
    ]
    for c in cands:
        try:
            if c.exists():
                t = c.read_text(encoding="utf-8", errors="replace").strip()
                if t:
                    return t
        except Exception:
            pass
    for k in ("V8_GH_PAT", "V8_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip()
    return ""


def _api(method, path, token, body=None, timeout=60):
    url = "https://api.github.com/" + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": "token " + token,
        "Accept": "application/vnd.github+json",
        "User-Agent": "v8-alimi-heartbeat",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        return None, "HTTP %d %s" % (e.code, e.read().decode("utf-8", "replace")[:200])
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def _read_local_last():
    try:
        if TARGET.exists():
            return json.loads(TARGET.read_text(encoding="utf-8")).get("last_time")
    except Exception:
        pass
    return None


def _read_remote(token):
    """读远端现状（诊断/幂等用）。走 raw（Accept: vnd.github.raw）避免 contents 空串假成功。"""
    req = urllib.request.Request(
        "https://api.github.com/repos/%s/contents/%s?ref=main" % (REPO, TARGET_REL),
        headers={"Authorization": "token " + token,
                 "Accept": "application/vnd.github.raw",
                 "User-Agent": "v8-alimi-heartbeat"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
        return json.loads(b.decode("utf-8")), None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None, "404"
        return None, "HTTP %d" % e.code
    except Exception as e:
        return None, str(e)


def _push(token, content_bytes, message):
    """Contents API 推送。带 sha 走更新、无 sha 走新建；409/422 重取 sha 重试。"""
    body = {"message": message, "branch": "main",
            "content": base64.b64encode(content_bytes).decode("ascii")}
    info, _ = _api("GET", "repos/%s/contents/%s?ref=main" % (REPO, TARGET_REL), token)
    if info and info.get("sha"):
        body["sha"] = info["sha"]
    last_err = None
    for attempt in range(3):
        res, err = _api("PUT", "repos/%s/contents/%s" % (REPO, TARGET_REL), token, body)
        if res and (res.get("content") or {}).get("sha"):
            return res["content"]["sha"], None
        last_err = err
        time.sleep(2 + 2 * attempt)
        info, _ = _api("GET", "repos/%s/contents/%s?ref=main" % (REPO, TARGET_REL), token)
        if info and info.get("sha"):
            body["sha"] = info["sha"]
        elif info is None and last_err and "404" in str(last_err):
            body.pop("sha", None)
    return None, last_err


def main():
    ap = argparse.ArgumentParser(description="阿狸咪心跳上报")
    ap.add_argument("--check", action="store_true", help="只读现状")
    ap.add_argument("--dry-run", action="store_true", help="写文件但不推送")
    ap.add_argument("--force", action="store_true", help="忽略幂等窗口")
    ap.add_argument("--quiet", action="store_true", help="静默成功")
    args = ap.parse_args()

    def say(*a):
        if not args.quiet:
            print(*a)

    token = _load_token()
    if not token:
        print("[FAIL] 未找到 PAT（探测：~/.workbuddy/v8_gh_pat / v8_gh_token.txt / data/.github_pat.txt / 环境变量）")
        return 1

    if args.check:
        loc = _read_local_last()
        rem, rerr = _read_remote(token)
        say("本地 %s last_time = %s" % (TARGET_REL, loc or "(无)"))
        if rem:
            say("远端 %s last_time = %s  machine=%s" % (TARGET_REL, rem.get("last_time"), rem.get("machine")))
        else:
            say("远端 %s 读取: %s" % (TARGET_REL, rerr))
        if rem and rem.get("last_time"):
            try:
                dt = datetime.strptime(rem["last_time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
                mins = (datetime.now(CST) - dt).total_seconds() / 60.0
                say("远端心跳沉默 = %.1f 分钟（接收侧阈值 180 分钟）" % mins)
            except Exception:
                pass
        return 0

    now = datetime.now(CST)
    # 幂等：距上次（本地优先，本地无则读远端）不足 MIN_GAP_MIN 则跳过
    if not args.force:
        prev = _read_local_last()
        if not prev:
            rem, _ = _read_remote(token)
            prev = (rem or {}).get("last_time")
        if prev:
            try:
                dt = datetime.strptime(prev, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
                gap = (now - dt).total_seconds() / 60.0
                if 0 <= gap < MIN_GAP_MIN:
                    say("[SKIP] 距上次心跳仅 %.1f 分钟（< %d），幂等跳过。--force 可强制。" % (gap, MIN_GAP_MIN))
                    return 0
            except Exception:
                pass

    payload = {"last_time": now.strftime("%Y-%m-%d %H:%M:%S"),
               "status": "ok", "machine": MACHINE, "source": SOURCE}
    content = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    # 双机双 OS 铁律：写盘固定 LF
    with open(TARGET, "w", encoding="utf-8", newline="\n") as f:
        f.write(content.decode("utf-8"))
    say("[OK] 已写 %s  last_time=%s" % (TARGET_REL, payload["last_time"]))

    if args.dry_run:
        say("[DRY-RUN] 跳过推送。")
        return 0

    msg = "data: 阿狸咪心跳上报 %s" % now.strftime("%Y%m%d-%H%M")
    sha, err = _push(token, content, msg)
    if not sha:
        print("[FAIL] 推送失败: %s" % err)
        return 1
    say("[OK] 已推送 %s  blob=%s" % (TARGET_REL, sha[:10]))
    say("     云端 build 全量 update_v8 后生成 data/HB_ALIMI.js，peer_monitor 即可判阿狸咪存活。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
