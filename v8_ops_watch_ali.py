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
  1. GitHub contents API 直读云端权威 HEALTH_CHECK.js / freshness_status.json
     （2026-09-30 一劳永逸重构：数据获取与本地 git 状态彻底解耦）
  2. 扫描 status != ok 的卡片 + freshness stale
  3. 🔴 远端真值复核（幽灵报警根治）：对每个 fail/warn 项读远端 data/<X>.js 的
     update_time——若远端已恢复而巡检报告未收敛（最长约 1h 空窗），剔出通知，
     不再拿"已修复"的项骚扰主人
  4. 把异常结构化写入 data/_ops_alert_pending.json（供自动化用 agent-mail 发邮件给主人）
  5. 打印摘要到 stdout（自动化可直接读）

2026-09-30 幽灵报警事故复盘（主人：「这个运维的还没修好，一劳永逸！」）：
  - 13:09 US_HK_MAP 数据已修复并推送，13:56 云端 patrol 报告已 ok；
  - 但本机自动化 13:17 仍报 fail「更新于 2天前」——因为本机 main 永久分叉
    （家机「永不 ff」铁律 + 所有推送走 Git Data API ⇒ git pull --ff-only 恒失败），
    本机永远读旧报告；
  - 且当时 git pull --rebase --autostash 的冲突 autostash 把本脚本工作区编辑卷走丢弃。
  根治：
  ① 主路径 = GitHub contents API 直读远端（真值源，与本地 git 完全解耦）；
  ② git pull 降级为 API 失败时的回落，且 🔴 禁 --rebase --autostash（防卷走工作区编辑）；
  ③ 远端复核 remote_recheck：报告声称的状态落后于远端实际 ⇒ 剔出（宁报勿漏，
     任何 API 失败/解析失败一律保留原项照报）。

设计原则：
  - 只读 + 产出告警内容，不改动任何算法/管线代码（守"只读不写"底线）
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
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
HEALTH_JS = DATA / "HEALTH_CHECK.js"
FRESH_JS = DATA / "freshness_status.json"
PENDING = DATA / "_ops_alert_pending.json"
REPO = "ah-quant999/quant-scanner-v8"
GH_TOKEN_PATH = Path.home() / ".workbuddy" / "v8_gh_pat"

# 通知冷却：相同异常签名在 N 小时内不重复写 pending（避免每 2h 轰炸主人）
NOTIFY_COOLDOWN_HOURS = 6
# 远端复核：message 无声称时间时，远端数据在 N 分钟内视为"已恢复"剔出。
# 通用红线=交易日 24h ⇒ 1440 分钟；声称时间可解析时走更精确的判据 A，不用此值。
RECHECK_FRESH_MIN = 1440

# 全站时间铁律：一律北京时间 CST+8
CST8 = datetime.timezone(datetime.timedelta(hours=8))


def _now8():
    return datetime.datetime.now(CST8)


def _ts():
    return _now8().strftime("%Y-%m-%d %H:%M:%S")


def _gh_token():
    try:
        return GH_TOKEN_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def fetch_remote_text(path):
    """GitHub contents API 直读远端 raw 内容（真值源，与本地 git 状态彻底解耦）。
    失败返回 None（调用方自行回落/保留原项，宁报勿漏）。"""
    tok = _gh_token()
    url = (
        f"https://api.github.com/repos/{REPO}/contents/"
        f"{urllib.parse.quote(path)}?ref=main"
    )
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github.raw+json",
        "User-Agent": "v8-ops-watch-ali",
    })
    if tok:
        req.add_header("Authorization", f"Bearer {tok}")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ⚠️ API 直读 {path} 失败: {e}")
        return None


def _clean_local_products():
    """丢弃脚本自身生成的 data/HEALTH_CHECK.js，保持工作区 clean，
    避免 dirty 阻止后续 git pull --ff-only（仅回落路径需要）。"""
    try:
        subprocess.run(
            ["git", "checkout", "--", "data/HEALTH_CHECK.js"],
            cwd=BASE, capture_output=True, text=True, timeout=30,
        )
    except Exception:
        pass


def git_pull():
    """尽力而为刷新本地副本（仅作 API 失败时的回落数据源）。
    已知态：本机 main 永久分叉（ahead 237 / behind 26+），ff-only 恒失败属正常，
    主路径已改 GitHub contents API 直读远端，不依赖 pull。
    🔴 禁 --rebase --autostash：2026-09-30 实证冲突 autostash 会把工作区未提交编辑卷走丢弃。"""
    _clean_local_products()
    try:
        r = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"],
            cwd=BASE, capture_output=True, text=True, timeout=120,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()[-200:]
    except Exception as e:
        return False, f"pull 异常: {e}"


def load_health():
    """云端权威报告优先（API 直读远端），失败回落本地副本（git pull 产物）。"""
    txt = fetch_remote_text("data/HEALTH_CHECK.js")
    if txt is None:
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
    """同 load_health 范式：API 直读优先，本地副本回落。"""
    txt = fetch_remote_text("data/freshness_status.json")
    if txt is None:
        if not FRESH_JS.exists():
            return None
        try:
            return json.load(open(FRESH_JS, encoding="utf-8"))
        except Exception:
            return None
    try:
        return json.loads(txt)
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


# ---------------------------------------------------------------------------
# 远端真值复核（幽灵报警根治，2026-09-30）
# ---------------------------------------------------------------------------
def _js_name_of(a):
    """从告警项推远端产物 js 文件名：message 里的「X.js 更新于」优先；
    兜底用 id（去 all_ 前缀）。推不出返回 None（保留原项）。"""
    msg = a.get("message", "") or ""
    m = re.search(r"([A-Za-z0-9_]+\.js)\s*更新于", msg)
    if m:
        return m.group(1)
    ident = a.get("id") or a.get("name") or ""
    ident = re.sub(r"^all_", "", ident)
    if ident and re.fullmatch(r"[A-Za-z0-9_]+", ident):
        return f"{ident}.js"
    return None


def _extract_update_time(txt):
    """从远端 js/json 原文提取 update_time 绝对时间戳（aware CST+8）。
    优先精确匹配 update_time 键；失败再全文取最新时间戳。推不出返回 None。"""
    if not txt:
        return None
    m = re.search(
        r"update_time[\"']?\s*[:=]\s*[\"'](\d{4}-\d{2}-\d{2})[ T](\d{1,2}:\d{2}(?::\d{2})?)",
        txt,
    )
    cands = []
    if m:
        cands.append((m.group(1), m.group(2)))
    else:
        cands = re.findall(r"(\d{4}-\d{2}-\d{2})[ T](\d{1,2}:\d{2}(?::\d{2})?)", txt)
        if not cands:
            d_only = re.findall(r"(\d{4}-\d{2}-\d{2})", txt)
            if d_only:
                try:
                    return datetime.datetime.strptime(
                        d_only[-1], "%Y-%m-%d").replace(tzinfo=CST8)
                except Exception:
                    return None
            return None
    best = None
    for d, t in cands:
        if t.count(":") == 1:
            t += ":00"
        try:
            dt = datetime.datetime.strptime(
                f"{d} {t}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST8)
            if best is None or dt > best:
                best = dt
        except Exception:
            continue
    return best


def _parse_claim_ts(msg):
    """从 message 解析「更新于」声称时间 → aware datetime(CST+8)。失败返回 None。
    支持：今日 HH:MM / 昨日 HH:MM / N天前 HH:MM / YYYY-MM-DD [HH:MM[:SS]]"""
    if not msg:
        return None
    m = re.search(r"更新于\s*([^;；，,]+)", msg)
    seg = m.group(1).strip() if m else msg
    now = _now8()
    m2 = re.search(r"今日\s*(\d{1,2}):(\d{2})", seg)
    if m2:
        d = now.replace(hour=int(m2.group(1)), minute=int(m2.group(2)),
                        second=0, microsecond=0)
        if d > now + datetime.timedelta(hours=1):  # 跨零点边缘：实为昨日
            d -= datetime.timedelta(days=1)
        return d
    m2 = re.search(r"昨日\s*(\d{1,2}):(\d{2})", seg)
    if m2:
        return (now - datetime.timedelta(days=1)).replace(
            hour=int(m2.group(1)), minute=int(m2.group(2)),
            second=0, microsecond=0)
    m2 = re.search(r"(\d+)\s*天前\s*(\d{1,2}):(\d{2})", seg)
    if m2:
        return (now - datetime.timedelta(days=int(m2.group(1)))).replace(
            hour=int(m2.group(2)), minute=int(m2.group(3)),
            second=0, microsecond=0)
    m2 = re.search(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?", seg)
    if m2:
        try:
            hh = int(m2.group(2) or 0)
            mi = int(m2.group(3) or 0)
            ss = int(m2.group(4) or 0)
            return datetime.datetime.strptime(
                m2.group(1), "%Y-%m-%d").replace(
                hour=hh, minute=mi, second=ss, tzinfo=CST8)
        except Exception:
            return None
    return None


def remote_recheck(real):
    """远端真值复核：把「报告已过时」的项剔出通知（幽灵报警根治）。
    判据：
      A. message 声称时间可解析 且 远端 update_time 比声称新 >5 分钟
         ⇒ 巡检报告滞后（数据已更新、报告未收敛）⇒ recovered（不推主人）
      B. 无声称时间 且 远端 age < RECHECK_FRESH_MIN ⇒ recovered（宁报勿漏：
         仅明确新鲜才剔出）
    远端文件名先按 message/id 原样，404 再试大写变体。
    任何 API 失败/解析异常 ⇒ 保留原项（宁报勿漏）。
    返回 (kept, recovered)。"""
    kept, recovered = [], []
    for a in real:
        try:
            js = _js_name_of(a)
            if not js:
                kept.append(a)
                continue
            txt = None
            cands = [f"data/{js}"]  # message 提取名优先；404 再试大写变体（id 兜底可能小写）
            if js.upper() != js:
                cands.append(f"data/{js.upper()}")
            for cand in cands:
                txt = fetch_remote_text(cand)
                if txt is not None:
                    break
            if txt is None:
                kept.append(a)
                continue
            remote_dt = _extract_update_time(txt)
            if remote_dt is None:
                kept.append(a)
                continue
            claim = _parse_claim_ts(a.get("message", ""))
            stamp = remote_dt.strftime("%Y-%m-%d %H:%M:%S")
            if claim is not None:
                if remote_dt > claim + datetime.timedelta(minutes=5):
                    recovered.append({**a, "remote_update": stamp})
                else:
                    kept.append(a)  # 远端没比声称新 ⇒ 报告如实 ⇒ 保留
                continue
            age_min = (_now8() - remote_dt).total_seconds() / 60
            if age_min < RECHECK_FRESH_MIN:
                recovered.append({**a, "remote_update": stamp})
            else:
                kept.append(a)
        except Exception as e:
            print(f"  ⚠️ 远端复核异常 {a.get('id')}: {e}（保留原项）")
            kept.append(a)
    return kept, recovered


def main():
    print(f"=== 阿狸咪运维页主动监控 {_ts()} ===")
    ok, msg = git_pull()
    print(f"  git pull(回落源，尽力而为): {'✅' if ok else 'ℹ️'} {msg}")

    # 2026-08-30 起：阿狸咪监控机「只读云端报告」，不本地跑 --heal。
    # 2026-09-30 起：主路径 = GitHub contents API 直读远端（与本地 git 解耦）。
    health = load_health()
    if not health:
        print("  ⚠️ API 直读与本地副本均无 HEALTH_CHECK.js，跳过本轮扫描")
        return 0
    updated = health.get("updated")
    if updated:
        try:
            up = datetime.datetime.strptime(updated, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST8)
            age_h = (_now8() - up).total_seconds() / 3600
            if age_h > 6:
                print(f"  ⚠️ 云端报告陈旧（{updated}，{age_h:.1f}h 前）→ 监控/抓取链路疑似中断，写 notify=false 边障报告，不骚扰主人")
                alert = {
                    "check_time": _ts(), "repo": REPO,
                    "health_summary": health.get("summary", {}),
                    "anomaly_count": 0, "anomalies": [], "noise_count": 0, "noise": [],
                    "recovered_count": 0, "recovered": [],
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

    # 🔴 远端真值复核：报告已滞后的项剔出（幽灵报警根治）
    real, recovered = remote_recheck(real)
    if recovered:
        print(f"  🔄 远端复核剔除 {len(recovered)} 项幽灵报警（远端已恢复、巡检报告未收敛）:")
        for a in recovered:
            print(f"     - [{a['id']}] 报告称: {a['message'][:60]} | 远端实际: {a.get('remote_update')}")

    # 冷却判定（仅基于真异常签名）；修复 last_notify_ts 持久化缺失导致的每轮重发
    prev = {}
    if PENDING.exists():
        try:
            prev = json.load(open(PENDING, encoding="utf-8"))
        except Exception:
            prev = {}
    prev_sig = prev.get("signature", "")
    cur_sig = sig(real)
    now = _now8()
    last_notify = prev.get("last_notify_ts")
    cooled = False
    if last_notify:
        try:
            ld = datetime.datetime.strptime(last_notify, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST8)
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
        "recovered_count": len(recovered),
        "recovered": recovered,
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
    if recovered:
        print(f"（另有 {len(recovered)} 项经远端复核确认已恢复，未计入通知）")
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
