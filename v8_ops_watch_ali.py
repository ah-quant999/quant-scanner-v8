#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_ops_watch_ali.py — 阿狸咪（家里机）运维页/看板失败主动监控
================================================================
背景（2026-08-10 主人诉求）：
  云端虽有 hourly self-heal + 看门狗，但告警投递有盲区（仅超阈硬故障发邮件，
  且本地 SMTP 配置缺失 → 主人收不到），阿狸咪本地又没有主动盯盘任务，
  导致"运维页/看板显示失败"总是主人自己翻页面先发现。

本脚本作为阿狸咪本地自动化（每 2 小时）的执行体：
  1. git pull 拉最新 main（拿云端生成的 HEALTH_CHECK.js / freshness_status.json）
  2. 跑 v8_health_check.py --heal
       - 自带 debounce 锁，对陈旧数据卡片自动派发 cn_fetch / algo_run 重跑
       - 与云端 self-heal / 小九看门狗共用 _heal_dispatch.json 锁，不会三重重复派发
  3. 扫描 HEALTH_CHECK.js 中 status != ok 的卡片 + freshness_status.json 的 stale
  4. 把异常结构化写入 data/_ops_alert_pending.json（供自动化用 agent-mail 发邮件给主人）
  5. 打印摘要到 stdout（自动化可直接读）

设计原则：
  - 只读 + 触发重跑，不改动任何算法/管线代码（守"只读不写"底线）
  - 任何单步失败都不致命，确保"发现+通知"链路始终可用
  - 邮件发送交给自动化（agent-mail 连接器），本脚本只负责产出告警内容

用法：
  python v8_ops_watch_ali.py
"""
import json
import re
import subprocess
import sys
import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
HEALTH_JS = DATA / "HEALTH_CHECK.js"
FRESH_JS = DATA / "freshness_status.json"
PENDING = DATA / "_ops_alert_pending.json"
REPO = "ah-quant999/quant-scanner-v8"

# 通知冷却：相同异常签名在 N 小时内不重复写 pending（避免每 2h 轰炸主人）
NOTIFY_COOLDOWN_HOURS = 6


def _ts():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _clean_local_products():
    """丢弃脚本自身生成的 data/HEALTH_CHECK.js，保持工作区 clean，
    避免 dirty 阻止后续 git pull --ff-only（否则永远读旧数据）。"""
    try:
        subprocess.run(
            ["git", "checkout", "--", "data/HEALTH_CHECK.js"],
            cwd=BASE, capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass


def git_pull():
    _clean_local_products()  # 先清本地脚本产物，确保可 ff
    try:
        r = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"],
            cwd=BASE, capture_output=True, text=True, timeout=120,
        )
        if r.returncode == 0:
            return True, (r.stdout + r.stderr).strip()[-200:]
    except Exception as e:
        return False, f"pull 异常: {e}"
    # 兜底：rebase（--autostash 处理残留）
    try:
        r2 = subprocess.run(
            ["git", "pull", "--rebase", "--autostash", "origin", "main"],
            cwd=BASE, capture_output=True, text=True, timeout=120,
        )
        return r2.returncode == 0, (r2.stdout + r2.stderr).strip()[-200:]
    except Exception as e:
        return False, f"rebase pull 异常: {e}"


def load_health():
    if not HEALTH_JS.exists():
        return None
    txt = HEALTH_JS.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"window\.HEALTH_CHECK\s*=\s*(\{.*?\})\s*;", txt, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def load_freshness():
    if not FRESH_JS.exists():
        return None
    try:
        return json.load(open(FRESH_JS, encoding="utf-8"))
    except Exception:
        return None


def extract_items(health):
    if not health:
        return []
    # 兼容 items / cards 两种键
    return health.get("items") or health.get("cards") or []


def build_alert(health, fresh):
    items = extract_items(health)
    anomalies = []
    for it in items:
        st = it.get("status")
        if st in ("fail", "warn"):
            anomalies.append({
                "name": it.get("name"),
                "id": it.get("id"),
                "page": it.get("page"),
                "status": st,
                "message": it.get("message", ""),
                "last_update": it.get("last_update") or it.get("update_time"),
                "heal": it.get("heal"),
            })
    # freshness 中的 core 过期（硬故障，必报）
    if fresh:
        for c in fresh.get("core_stale", []):
            anomalies.append({
                "name": c.get("var"), "id": c.get("var"), "page": "新鲜度守卫",
                "status": "fail", "message": f"核心数据过期: {c.get('reason','')}",
                "last_update": None, "heal": None,
            })
        for w in fresh.get("warn_stale", []):
            # warn_stale 中带「无云端生产者」的才是真问题；普通网络抖动的归并到卡片
            anomalies.append({
                "name": w.get("var"), "id": w.get("var"), "page": "新鲜度守卫",
                "status": "warn", "message": f"数据过期: {w.get('reason','')}",
                "last_update": None, "heal": None,
            })

    # 去重（按 id+status）
    seen, uniq = set(), []
    for a in anomalies:
        key = f"{a['id']}|{a['status']}"
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq


def is_noise(a):
    """过滤阿狸咪监控机自身的 git 状态噪音（不是运维页数据失败）：
    如『本地与 origin 同步』『Pages 部署同步』等——这是监控机落后云端所致，属正常。"""
    if a.get("page") == "管线":
        msg = a.get("message", "") or ""
        if any(k in msg for k in ["同步", "落后", "本地与origin", "部署同步", "本地 HEAD"]):
            return True
    return False


def split_notify(anomalies):
    """拆成『需通知主人的真异常』与『已知/自身状态噪音』。"""
    real, noise = [], []
    for a in anomalies:
        (noise if is_noise(a) else real).append(a)
    return real, noise


def sig(anomalies):
    return "|".join(sorted(f"{a['id']}:{a['status']}" for a in anomalies))


def main():
    print(f"=== 阿狸咪运维页主动监控 {_ts()} ===")
    ok, msg = git_pull()
    print(f"  git pull: {'✅' if ok else '⚠️'} {msg}")

    # 2026-08-30 一劳永逸：阿狸咪监控机改为「只读云端报告」。
    # 不再本地跑 v8_health_check.py --heal —— 监控机无数据访问、且 --heal 联网派发易挂死，
    # 会再生成本地过时/误报报告；自 8/10 起多次未能跑完，留下 notify:true 陈旧文件反复推送。
    # 云端 v8_health_patrol.yml 每小时已跑 --heal 并产出权威 HEALTH_CHECK.js / freshness_status.json。
    health = load_health()
    if not health:
        print("  ⚠️ 本地无 HEALTH_CHECK.js（git pull 可能失败），跳过本轮扫描")
        return 0
    updated = health.get("updated")
    if updated:
        try:
            up = datetime.datetime.strptime(updated, "%Y-%m-%d %H:%M:%S")
            age_h = (datetime.datetime.now() - up).total_seconds() / 3600
            if age_h > 6:
                print(f"  ⚠️ 云端报告陈旧（{updated}，{age_h:.1f}h 前）→ 监控/抓取链路疑似中断，写 notify=false 边障报告，不骚扰主人")
                alert = {
                    "check_time": _ts(), "repo": REPO,
                    "health_summary": health.get("summary", {}),
                    "anomaly_count": 0, "anomalies": [], "noise_count": 0, "noise": [],
                    "signature": "monitor_stale", "notify": False, "cooled": False,
                    "note": f"云端报告陈旧 {age_h:.1f}h，疑似监控/抓取链路中断，非站点数据故障",
                }
                PENDING.write_text(json.dumps(alert, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"\n⚠️ 监控数据陈旧，已写入 notify=false 边障报告: {PENDING}")
                return 0
        except Exception:
            pass

    fresh = load_freshness()
    anomalies = build_alert(health, fresh)
    real, noise = split_notify(anomalies)

    # 冷却判定（仅基于真异常签名）；修复 last_notify_ts 持久化缺失导致的每轮重发
    prev = {}
    if PENDING.exists():
        try:
            prev = json.load(open(PENDING, encoding="utf-8"))
        except Exception:
            prev = {}
    prev_sig = prev.get("signature", "")
    cur_sig = sig(real)
    now = datetime.datetime.now()
    last_notify = prev.get("last_notify_ts")
    cooled = False
    if last_notify:
        try:
            ld = datetime.datetime.strptime(last_notify, "%Y-%m-%d %H:%M:%S")
            cooled = (now - ld).total_seconds() < NOTIFY_COOLDOWN_HOURS * 3600
        except Exception:
            cooled = False
    # 有真异常 且（签名变化 或 冷却已过的首轮）才通知；同一异常不每轮重发
    notify = bool(real) and (cur_sig != prev_sig or not cooled)

    last_notify_ts = _ts() if notify else prev.get("last_notify_ts")
    alert = {
        "check_time": _ts(),
        "repo": REPO,
        "health_summary": health.get("summary", {}),
        "anomaly_count": len(real),
        "anomalies": real,
        "noise_count": len(noise),
        "noise": noise,
        "signature": cur_sig,
        "notify": notify,
        "cooled": cooled,
        "last_notify_ts": last_notify_ts,
    }
    PENDING.write_text(json.dumps(alert, ensure_ascii=False, indent=2), encoding="utf-8")

    if real:
        print(f"\n🔴 发现 {len(real)} 项需通知的异常（{'将通知主人' if notify else '冷却期内/无变化，本次不重发'}）：")
        for a in real:
            tag = "❌FAIL" if a["status"] == "fail" else "⚠️WARN"
            print(f"  {tag} [{a['page']}] {a['name']}: {a['message'][:80]}")
            if a.get("heal"):
                print(f"       自愈: {a['heal']}")
    else:
        print("\n✅ 运维页/看板全部正常（无 fail/warn 需通知）")
    if noise:
        print(f"\n（已忽略 {len(noise)} 项监控机自身 git 状态噪音，如本地与 origin 同步）")

    print(f"\n告警已写入: {PENDING}")

    # 清理脚本生成的产物，保持工作区 clean（不污染 git status，不影响下次 pull）
    _clean_local_products()
    # rc=0 即使有异常也不影响自动化后续步骤；异常通过 pending 文件传递
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
