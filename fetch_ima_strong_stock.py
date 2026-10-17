#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_ima_strong_stock.py — v2「短线情绪选股」换代版（阿狸咪的工程师 · 2026-09-30）

🔴 换代动因（实测，非推测）：
  源方（高手 梧谷枫灯）已在 ima 知识库重组中**下架「强势股跟踪」系列**——
  最后一篇《强势股跟踪日报 2026-09-15》，原文件夹 folder_7500817011604393 已删除
  （2026-09-30 连接器 get_knowledge_list 实测：库根目录仅剩 4 夹：
   短线情绪选股 / 短线情绪温度计 / 九型人格画像 / 月运合集）。
  换代系列 =「短线情绪选股」主报告《短线情绪选股 YYYY-MM-DD》：
    · 每日候选池（按强度分排序）：排名|代码|名称|强度分|换手率|量比|流通市值(亿)|封单(亿)|题材|判定说明
    · 头部：周期阶段（温度分）｜建议总仓位
    · 另有盘前《短线情绪选股竞价校验 YYYY-MM-DD》系列 —— **勿取**（非本卡水源）。

产物（**文件名不变**，下游 update_v8 / 前端卡 / 回测账本零改动即可衔接）：
  raw_data/ima_strong_stock.json   —— 中间数据
  data/IMA_STRONG_STOCK.js         —— window.IMA_STRONG_STOCK = {...}

schema v2（stocks[] 换代；旧「基准价/最新价/涨幅/回撤/状态」字段随旧系列绝版，
         新系列**源本无价格** ⇒ 绝不伪造，前端卡已同步换代为候选池列）：
  {rank, code(6位), market(SH/SZ/BJ), name, score, turnover_pct, vol_ratio,
   mktcap_yi, seal_yi, theme, note, first_selected(=数据日), trade_date(=数据日)}

分工（与 v1 相同，职责单一）：
  · 本机（ima 登录态·知识连接器 fetch_media_content）：取**全文** →
    落 raw_data/ima_strong_stock_full.md + .json（meta 记 fetched_at）→ 推仓；
  · 云端 15:45（v8_ima_strong_stock.yml）：跑本脚本**读快照**解析；
    快照缺失/过期(>72h) ⇒ 尝试访客 wiki 路（服务端 ~300 字硬墙，通常仅 1~2 条，
    如实标 detail_complete=false）；两条路都拿不到 ⇒ 保留上一版产物并降级标注，绝不伪造。

🔴🔴 2026-10-16 一劳永逸修复（实测断更 3 天全程无告警、前端把 3 天前数据当 1 天前展示）：
  A. retained-last 保留上一版时，**必须按保留的 data_date 重算** stale_days /
     source_stale / snapshot_expired（原只刷 update_time ⇒ 停更态永不进入、
     告警邮件永不触发、前端假新鲜）。两处 retained-last 分支共用 _write_retained()。
  B. load_snapshot() 增 meta 标题日期 vs 正文标题日期一致性校验
     （实测事故：meta 记 10-13 而正文实为 10-12 ⇒ 抓取器列表标题/正文错位）。
     内容日期优先，不一致只标记（snapshot_meta_mismatch）不阻断 —— 防回归守卫
     本就挡住旧内容覆盖已发布新版，无需丢弃真数据。
  C. B 的证据必须同样覆盖 retained-last 路径（_regress 分支传 snap_info=data，
     线上实测缺口：10-16 首轮修复后 retained 产物无 meta_mismatch 字段、
     snapshot_age_h 仍是 15.21 旧值与 expired=true 自相矛盾）——
     杜绝「正常路径有留证、retained 路径裸奔」的模块行为不一致。

用法：
  python fetch_ima_strong_stock.py            # 快照优先，缺失/过期回退访客路
  python fetch_ima_strong_stock.py --source snapshot-only   # 只读快照（云端默认够用）
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

# 🔴 源停更邮件告警（沿用 v1 闸门：v8_send_alert 统一发信；云端无配置时静默跳过）
try:
    import v8_send_alert
except Exception as _e:
    v8_send_alert = None
    print("[WARN] v8_send_alert 导入失败，源停更告警将只在日志体现：%s" % _e)

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(ROOT, "raw_data")
DATA_DIR = os.path.join(ROOT, "data")

SNAPSHOT_MD = os.path.join(RAW_DIR, "ima_strong_stock_full.md")
SNAPSHOT_META = os.path.join(RAW_DIR, "ima_strong_stock_full.json")

# ── 水源常量（与 v8/fetch_chan_buy_point.py 同源同库，三元组勿再丢）──────────
WIKI_SHARE_ID = "32c01f1da52044f743a01e4aa995d72e7940cc8e99cf413cc5f4c2eb39b4d389"
WIKI_API = "https://ima.qq.com/cgi-bin/knowledge_share_get/get_share_info"
WIKI_PAGE = "https://ima.qq.com/wiki/"
FOLDER_MAIN = "folder_7507701210837524"      # 「短线情绪选股」（2026-09-30 实测）
FOLDER_MAIN_NAME = "短线情绪选股"
KB_ID = "7500816604757970"
KB_NAME = "九型人格"
KB_CREATOR = "梧谷枫灯"
NOTE_URL = "https://ima.qq.com/wiki/?shareId=%s&folderId=%s" % (WIKI_SHARE_ID, FOLDER_MAIN)

# 🔴🔴 死夹黑名单（源方重组/改名后已下架或弃用，绝不可再读，防「读错/回退旧版」）
#   · folder_7500817011604393 = 旧「强势股跟踪」日报夹（2026-09-15 绝笔、已删除）
#   · folder_7506360161825717 = 旧「缠论买点每日推荐」夹（高手改名短线情绪选股后弃用）
# 当前唯一有效水源 = FOLDER_MAIN（folder_7507701210837524「短线情绪选股」）。
DEAD_FOLDERS = {"folder_7500817011604393", "folder_7506360161825717"}

SNAPSHOT_MAX_AGE_H = 72          # 快照 >72h 视为过期（降级，不伪造）
WIKI_STALE_DAYS_ALERT = 2        # 日报性质：停更 >2 自然日 = source_stale
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TITLE_RE = re.compile(r"^#\s*(短线情绪选股\s*20\d{2}-\d{2}-\d{2})\s*$", re.M)
# 竞价校验系列标题（盘前，勿取）
AJ_TITLE_RE = re.compile(r"竞价校验")


def to_float(x):
    try:
        return float(str(x).replace("%", "").strip())
    except Exception:
        return None


def to_int(x):
    try:
        return int(float(str(x).strip()))
    except Exception:
        return None


def parse_v2(text):
    """解析「短线情绪选股」主报告全文快照 → (stocks, header)。

    表结构（2026-09-30 实测 8 条，markdown 管道表、列位恒定）：
      |排名|代码|名称|强度分|换手率|量比|流通市值(亿)|封单(亿)|题材|判定说明|
    头部：周期阶段：X（温度分 N）｜建议总仓位：A-B%
    题材聚类表：|题材|涨停家数|（两列，取入 themes_top 供前端/审计）
    🔴 不猜不补：任何一格类型不符 ⇒ 该格留 None/空并计入 _parse_missing，绝不串位。
    """
    stocks = []
    themes_top = []
    cycle_stage = ""
    position_advice = ""
    for ln in (text or "").split("\n"):
        s = ln.strip()
        if not s.startswith("|"):
            m = re.search(r"周期阶段：(.+?)｜建议总仓位：([\d\-~％%\s]+)", s)
            if m and not cycle_stage:
                cycle_stage = m.group(1).strip()
                position_advice = m.group(2).strip()
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) == 2 and cells[0] and cells[0] != "题材" \
                and not cells[0].startswith("--") and cells[1].isdigit():
            themes_top.append([cells[0], int(cells[1])])
            continue
        if len(cells) != 10:
            continue
        if not re.fullmatch(r"\d{1,2}", cells[0]):
            continue                     # 排名（1~2 位数字）
        mc = re.match(r"(\d{6})\.(SH|SZ|BJ)", cells[1])
        if not mc:
            continue                     # 表头 / 分隔线
        miss = []
        score = to_int(cells[3])
        if score is None:
            miss.append("score")
        stocks.append({
            "rank": to_int(cells[0]),
            "code": mc.group(1),
            "market": mc.group(2),
            "name": cells[2],
            "score": score,
            "turnover_pct": to_float(cells[4]),
            "vol_ratio": to_float(cells[5]),
            "mktcap_yi": to_float(cells[6]),
            "seal_yi": to_float(cells[7]),
            "theme": cells[8],
            "note": cells[9],
            "_parse_missing": miss,
        })
    return stocks, {"cycle_stage": cycle_stage, "position_advice": position_advice,
                    "themes_top": themes_top}


# 🔴🔴 2026-10-14 主人令「立即修复」·first_selected 差集计算（根治 v2 换代断流）
# ───────────────────────────────────────────────────────────────────────────
# 根因（2026-10-14 凌晨线上铁证）：parse_v2 的 docstring 声明
#   first_selected(=数据日)/trade_date(=数据日)，但实现**从未写这两个键** ⇒
#   下游回测 backtest_life_cards._load_sigs 按 first_selected 定位信号时点，
#   拿不到即跳过 ⇒ 线上 IMA_STRONG_BACKTEST 112 笔样本**全部来自 v1 历史归档**
#   （signal_date_range 2026-06-09~08-28），v2「短线情绪选股」（09-30 换代至今）
#   贡献 0 笔，当日候选 8 只全被跳过（skipped_no_signal_date=8）——
#   覆盖度守卫只看总量 112>下限 ⇒ 断流静默 2 周无人报。
# 修法（差集法，语义严谨）：
#   · 滚动归档 raw_data/ima_strong_daily.json = {data_date: [codes]}，只增不改、同日幂等；
#   · first_selected = 该 code 在归档中**最早出现**的日期；从未出现 ⇒ 数据日（当日首入）；
#   · ⛔ 绝不直接填「=数据日」：那会让同一只票每天都被当成「新信号」，
#     回测把持有期每天重复计一笔（样本爆炸+语义错误）。
#   · 冷启动（归档为空）= 当日池全部记为首次入选（系统视角如实，不伪造历史）。
#   · 衔接：回测与最终推荐「符合入选的」判据统一为 first_selected == data_date。
def _update_daily_archive(dd, codes):
    p = os.path.join(RAW_DIR, "ima_strong_daily.json")
    arch = {}
    try:
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                arch = json.load(f) or {}
    except Exception as e:
        print(f"[warn] ima_strong_daily 读取失败，按空归档处理: {e}")
    if dd and codes:
        arch[dd] = sorted(set(codes))   # 同日幂等覆盖
    try:
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(arch, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"[warn] ima_strong_daily 写入失败: {e}")
    return arch


def _first_selected(dd, code, arch):
    """差集法取首次入选日：归档中最早出现日；从未出现 ⇒ dd；dd 也空 ⇒ None（回测跳过）。"""
    days = sorted(d for d, cs in (arch or {}).items() if code in (cs or []))
    if days:
        return days[0]
    return dd or None


def load_snapshot():
    """读全文快照。任何异常返回 None（调用方回退/降级），绝不抛死整条链。"""
    if not (os.path.exists(SNAPSHOT_MD) and os.path.exists(SNAPSHOT_META)):
        print("ℹ️ [snapshot] 无全文快照 ⇒ 走访客兜底/降级")
        return None
    try:
        with open(SNAPSHOT_META, encoding="utf-8") as f:
            snap = json.load(f)
        with open(SNAPSHOT_MD, encoding="utf-8") as f:
            md = f.read()
    except Exception as e:
        print("⚠️ [snapshot] 不可读：%s %s" % (type(e).__name__, str(e)[:100]))
        return None
    if not md.strip():
        return None
    if AJ_TITLE_RE.search(md[:200]):
        print("⚠️ [snapshot] 快照是「竞价校验」盘前系列（非主报告）⇒ 视为无效")
        return None

    _fa = str(snap.get("fetched_at") or "")
    try:
        _dt = datetime.strptime(_fa, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone(timedelta(hours=8)))
        age_h = (datetime.now(timezone(timedelta(hours=8))) - _dt).total_seconds() / 3600.0
    except Exception:
        print("⚠️ [snapshot] fetched_at 非法（%r）⇒ 视为无效" % _fa[:40])
        return None
    if age_h < -1:
        print("⚠️ [snapshot] fetched_at 在未来（%.1f h）⇒ 视为无效" % age_h)
        return None
    snapshot_expired = age_h > SNAPSHOT_MAX_AGE_H

    stocks, header = parse_v2(md)
    if not stocks:
        print("⚠️ [snapshot] 候选池解析出 0 条（源格式可能又变）⇒ 视为无效")
        return None
    m = TITLE_RE.search(md)
    title = m.group(1).strip() if m else str(snap.get("title") or "")
    md_date = re.search(r"(20\d{2})-(\d{2})-(\d{2})", title)
    data_date = "%s-%s-%s" % md_date.groups() if md_date else ""
    # 🔴 2026-10-16 一劳永逸：meta 与正文一致性校验。
    #   实测事故（2026-10-13 17:48 快照）：meta title 记「短线情绪选股 2026-10-13」
    #   而正文实为「# 短线情绪选股 2026-10-12」⇒ 抓取器「列表标题 / 正文内容」
    #   错位（标题取自列表最新篇、正文取到另一篇）。**内容日期优先**（正文才是
    #   可信全文），不一致只标记不阻断 —— 防回归守卫会挡住旧内容覆盖已发布的新版，
    #   本就挡住旧内容覆盖已发布新版，无需在此丢弃真数据。
    meta_title = str(snap.get("title") or "")
    _mt = re.search(r"(20\d{2}-\d{2}-\d{2})", meta_title)
    meta_date = _mt.group(1) if _mt else ""
    snapshot_meta_mismatch = bool(meta_date and data_date and meta_date != data_date)
    if snapshot_meta_mismatch:
        print("⚠️ [snapshot] meta 标题日期 %s 与正文标题日期 %s 不一致"
              "（内容优先；疑抓取器列表标题/正文错位）—— 已记录 snapshot_meta_mismatch"
              % (meta_date, data_date))
    print("%s [snapshot] %s · 候选 %d 条 · 数据日 %s · 快照龄 %.1f h%s"
          % ("⚠️" if snapshot_expired else "✅", title or "?", len(stocks),
             data_date or "?", age_h, "[已过期]" if snapshot_expired else ""))
    return {"title": title, "data_date": data_date, "stocks": stocks, "header": header,
            "age_h": age_h, "snapshot_expired": snapshot_expired,
            "snapshot_meta_mismatch": snapshot_meta_mismatch,
            "meta_title": meta_title,
            "fetched_at": _fa, "channel": "full-snapshot"}


def _wiki_post(body, timeout=30):
    import urllib.request
    req = urllib.request.Request(
        WIKI_API, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Accept": "application/json, text/plain, */*",
                 "Origin": "https://ima.qq.com", "Referer": "https://ima.qq.com/",
                 "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                "AppleWebKit/537.36 (KHTML, like Gecko) "
                                "Chrome/131.0.0.0 Safari/537.36")})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "ignore"))


def _wiki_ssr_latest(folder_id):
    """访客兜底：SSR 深页抠最新一篇 introduction（服务端 ~300 字硬墙，如实降级）。"""
    import urllib.request
    url = "%s?shareId=%s&folderId=%s" % (WIKI_PAGE, WIKI_SHARE_ID, folder_id)
    req = urllib.request.Request(url, headers={
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    html = urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "ignore")
    m = re.search(r'__remixContext\.streamController\.enqueue\("(.*?)"\)', html, re.S)
    if not m:
        return None
    payload = json.loads('"' + m.group(1) + '"')
    arr = json.loads(payload)
    flat = [x for x in arr if isinstance(x, str)]
    title, intro = "", ""
    for x in flat:
        if re.match(r"^短线情绪选股\s*20\d{2}-\d{2}-\d{2}$", x) and x > title:
            title = x            # 主报告（竞价校验不含日期尾部独立段，前缀即排除）
    for x in flat:
        if x.startswith("周期阶段") and len(x) > len(intro):
            intro = x
    if not title:
        return None
    return {"title": title, "introduction": intro}


def parse_intro_v2(intro):
    """访客兜底解析：introduction 是空格分隔单行（无管道），按 6位代码.SH/SZ 锚点切分。"""
    stocks = []
    if not intro:
        return stocks
    codes = [(m.start(), m.group(0)) for m in
             re.finditer(r"(?<![\d.])(\d{6})\.(?:SH|SZ|BJ)", intro)]
    for i, (st, code) in enumerate(codes):
        en = codes[i + 1][0] if i + 1 < len(codes) else len(intro)
        tk = intro[st:en].split()
        if len(tk) < 7:
            continue                     # 残缺尾条：不猜不补，如实丢弃
        rec = {
            "rank": len(stocks) + 1,
            "code": code.split(".")[0],
            "market": code.split(".")[1],
            "name": tk[1],
            "score": to_int(tk[2]),
            "turnover_pct": to_float(tk[3]),
            "vol_ratio": to_float(tk[4]),
            "mktcap_yi": to_float(tk[5]),
            "seal_yi": to_float(tk[6]),
            "theme": tk[7] if len(tk) > 7 else "",
            "note": " ".join(tk[8:]) if len(tk) > 8 else "",
            "_parse_missing": [],
        }
        if rec["score"] is None:
            continue
        stocks.append(rec)
    return stocks


def _recompute_stale(prev, now=None):
    """🔴 2026-10-16 一劳永逸：retained-last 保留上一版时，按保留的数据日**重算**
    stale_days / source_stale / snapshot_expired。

    根因（实测）：原 retained-last 分支只刷 update_time，三个陈旧度字段全部冻结在
    上一次「好写入」的值 ⇒ 源停更 N 天仍显示「1 天前 / source_stale=false /
    snapshot_expired=false」，停更告警永不触发、前端把 3 天前数据当新的展示
    （线上 2026-10-16 15:53 产物实证：data_date=10-13 而 stale_days=1）。
    返回 (stale_days, source_stale, snapshot_expired)；数据日缺失 ⇒ 不猜（None）。
    """
    now = now or datetime.now(timezone(timedelta(hours=8)))
    _pd = str(prev.get("data_date") or "")
    try:
        stale_days = (now.date() - datetime.strptime(_pd, "%Y-%m-%d").date()).days
    except Exception:
        stale_days = None
    source_stale = bool(stale_days is not None and stale_days > WIKI_STALE_DAYS_ALERT)
    # 快照龄：按上一版记录的 snapshot_fetched_at 重算（拿不到则沿用旧值，不猜）
    snapshot_expired = bool(prev.get("snapshot_expired"))
    _fa = str(((prev.get("sample_coverage") or {}).get("snapshot_fetched_at")) or "")
    try:
        _dt = datetime.strptime(_fa, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone(timedelta(hours=8)))
        snapshot_expired = (now - _dt).total_seconds() / 3600.0 > SNAPSHOT_MAX_AGE_H
    except Exception:
        pass
    return stale_days, source_stale, snapshot_expired


def _write_retained(prev, degraded_reason, now=None, snap_info=None):
    """两处 retained-last 分支共用：重算停更态 → 按需发停更邮件 → 落盘 raw/js。

    邮件纪律（与主路径同阈、2026-09-29 立）：仅「非停更 → 停更」迁移当次发一封，
    此后静默留证；stale 级仅交易日放行（周末/节假日属预期静默）。
    now 仅供单测注入固定时刻，生产路径不传。
    snap_info：本次 load_snapshot() 的返回（_regress 分支必传）——retained-last
      也必须如实带上「本次快照的过期/错位」证据，否则前端只见陈旧数据却无任何
      留证（2026-10-16 线上实测缺口：snapshot_expired=true 而 age_h=15.21 旧值）。
    """
    now = now or datetime.now(timezone(timedelta(hours=8)))
    _prev_stale = bool(prev.get("source_stale"))   # 迁移判据取「本次写入前」的值
    stale_days, source_stale, snapshot_expired = _recompute_stale(prev, now)
    # 本次快照证据合并（内容日期优先；不一致只标记不阻断）
    _si = snap_info or {}
    _snap_expired_now = bool(_si.get("snapshot_expired"))
    _meta_mismatch_now = bool(_si.get("snapshot_meta_mismatch"))
    _prefix = []
    if _snap_expired_now:
        _prefix.append("snapshot_age>%.0fh" % (_si.get("age_h") or 0))
    if _meta_mismatch_now:
        _prefix.append("meta-md-date-mismatch")
    prev["stale_days"] = stale_days
    prev["source_stale"] = source_stale
    prev["snapshot_expired"] = snapshot_expired or _snap_expired_now
    prev["snapshot_meta_mismatch"] = _meta_mismatch_now
    if _si.get("meta_title"):
        prev["meta_title"] = _si["meta_title"]
    prev["detail_channel"] = "retained-last"
    degraded_reason = ";".join(_prefix + [degraded_reason]) if _prefix else degraded_reason
    if source_stale and stale_days is not None:
        degraded_reason = "%s;source-stale-%dd" % (degraded_reason, stale_days)
    prev["degraded_reason"] = degraded_reason
    # snapshot_age_h 展示值与 snapshot_expired 对齐（重算，杜绝「已过期却显示 15h」）
    _fa = str(((prev.get("sample_coverage") or {}).get("snapshot_fetched_at")) or "")
    try:
        _dt = datetime.strptime(_fa, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone(timedelta(hours=8)))
        prev.setdefault("sample_coverage", {})["snapshot_age_h"] = \
            round((now - _dt).total_seconds() / 3600.0, 2)
    except Exception:
        pass
    prev["update_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
    if source_stale and not _prev_stale and v8_send_alert:
        try:
            v8_send_alert.send_alert(
                "ima 短线情绪选股源停更 %s 天" % stale_days,
                "源笔记：%s\n数据日：%s\n已停更：%s 天（阈值 %d 天）\n源 URL：%s\n"
                "（retained-last 保留上一版期间检测到停更；仅停更态进入时发一次，此后静默留证）"
                % (prev.get("source_title"), prev.get("data_date"), stale_days,
                   WIKI_STALE_DAYS_ALERT, NOTE_URL),
                level="stale")
        except Exception as _ae:
            print("[WARN] 源停更邮件发送失败（非致命）: %s" % _ae)
    with open(os.path.join(RAW_DIR, "ima_strong_stock.json"), "w",
              encoding="utf-8", newline="\n") as f:
        json.dump(prev, f, ensure_ascii=False, indent=2)
    with open(os.path.join(DATA_DIR, "IMA_STRONG_STOCK.js"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("window.IMA_STRONG_STOCK = ")
        json.dump(prev, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print("⛔ 已保留上一版产物并**重算停更态**：数据日 %s · 停更 %s 天 · source_stale=%s"
          % (prev.get("data_date"), stale_days, source_stale))
    return prev


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["auto", "snapshot-only"], default="auto",
                    help="auto = 快照优先、无效时走访客兜底（默认）；snapshot-only = 只读快照")
    args = ap.parse_args()

    # 🔴 死夹拒绝：FOLDER_MAIN 一旦指向已下架/弃用水源 ⇒ 直接拒绝（绝不允许读旧源/覆盖旧版）
    if FOLDER_MAIN in DEAD_FOLDERS:
        raise SystemExit(
            "❌ FOLDER_MAIN=%s 属于已弃用/下架水源（DEAD_FOLDERS），"
            "拒绝读取旧源，以防「读错 / 覆盖回旧版」。请确认水源已切到 folder_7507701210837524。" % FOLDER_MAIN)

    data = load_snapshot()
    channel = "full-snapshot" if data else "none"
    degraded_reason = ""
    snapshot_expired = bool(data and data.get("snapshot_expired"))
    snapshot_meta_mismatch = bool(data and data.get("snapshot_meta_mismatch"))
    if data and snapshot_expired:
        degraded_reason = "snapshot_age>%.0fh" % data["age_h"]
    if data and snapshot_meta_mismatch:
        degraded_reason = (degraded_reason + ";" if degraded_reason else "") \
            + "meta-md-date-mismatch"

    if data is None and args.source == "auto":
        # 访客兜底（~300 字硬墙：通常仅 1~2 条，detail_complete=false 如实降级）
        try:
            print("🌐 [wiki] 访客兜底：SSR 深页 folder=%s" % FOLDER_MAIN)
            ssr = _wiki_ssr_latest(FOLDER_MAIN)
            if ssr:
                stocks = parse_intro_v2(ssr.get("introduction") or "")
                if stocks:
                    md_date = re.search(r"(20\d{2})-(\d{2})-(\d{2})", ssr["title"])
                    data = {"title": ssr["title"],
                            "data_date": md_date.group(0) if md_date else "",
                            "stocks": stocks, "header": {},
                            "age_h": None, "snapshot_expired": False,
                            "fetched_at": "", "channel": "introduction"}
                    channel = "introduction"
                    print("⚠️ [wiki] 访客兜底仅拿到 %d 条（服务端硬墙）—— 如实降级" % len(stocks))
        except Exception as e:
            print("⚠️ [wiki] 访客兜底失败：%s %s" % (type(e).__name__, str(e)[:120]))

    if data is None:
        # 🔴 两条路都空：保留上一版产物 + 降级标注（绝不写空 stocks 把卡打白，也绝不伪造）
        #   2026-10-16：改走 _write_retained —— 重算 stale_days/source_stale/snapshot_expired，
        #   否则断更期间产物永远显示「新鲜」（实测线上 10-16：data_date=10-13 而 stale_days=1）。
        prev_path = os.path.join(RAW_DIR, "ima_strong_stock.json")
        if os.path.exists(prev_path):
            try:
                with open(prev_path, encoding="utf-8") as f:
                    prev = json.load(f)
                _write_retained(prev, "both-channels-empty;retained-last-good")
                print("⛔ 两条取数路均无数据 —— 已保留上一版产物并标注 degraded（不伪造）。")
                return
            except Exception as e:
                print("❌ 保留上一版也失败：%s" % e)
        raise SystemExit("❌ 无快照、访客兜底失败、且无上一版产物 —— 需人工接水源。")

    _now = datetime.now(timezone(timedelta(hours=8)))
    stocks = data["stocks"]
    data_date = data["data_date"]
    # 🔴🔴 2026-10-14 first_selected 差集修复（根因与语义见 _update_daily_archive 注释）：
    #   先落当日滚动归档，再逐只算 first_selected/trade_date 并写回 stocks。
    _codes_today = [str(s.get("code") or "").strip() for s in stocks if s.get("code")]
    _daily_arch = _update_daily_archive(data_date, _codes_today)
    _fs_new = 0
    for s in stocks:
        _c = str(s.get("code") or "").strip()
        if not _c:
            continue
        s["first_selected"] = _first_selected(data_date, _c, _daily_arch)
        s["trade_date"] = data_date or None
        if s["first_selected"] == data_date and data_date:
            _fs_new += 1
    print(f"[first_selected] 数据日 {data_date or '?'}：池 {len(stocks)} 只，"
          f"当日新入选 {_fs_new} 只，延续 {len(stocks) - _fs_new} 只（差集法·滚动归档）")
    try:
        stale_days = (_now.date() - datetime.strptime(data_date, "%Y-%m-%d").date()).days
    except Exception:
        stale_days = None
    source_stale = bool(stale_days is not None and stale_days > WIKI_STALE_DAYS_ALERT)

    # 源停更邮件：仅「非停更 → 停更」迁移当次发一封（2026-09-29 邮件纪律）
    _prev_stale = None
    try:
        with open(os.path.join(RAW_DIR, "ima_strong_stock.json"), encoding="utf-8") as _pf:
            _prev_stale = bool((json.load(_pf) or {}).get("source_stale"))
    except Exception:
        _prev_stale = None
    if source_stale and _prev_stale is not True and v8_send_alert:
        try:
            v8_send_alert.send_alert(
                "ima 短线情绪选股源停更 %s 天" % stale_days,
                "源笔记：%s\n数据日：%s\n已停更：%s 天（阈值 %d 天）\n源 URL：%s\n"
                "（仅停更态进入时发一次，此后静默留证）"
                % (data["title"], data_date, stale_days, WIKI_STALE_DAYS_ALERT, NOTE_URL),
                level="stale")
        except Exception as _ae:
            print("[WARN] 源停更邮件发送失败（非致命）: %s" % _ae)

    no_score = sum(1 for s in stocks if s.get("score") is None)
    out = {
        "update_time": _now.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "ima",
        "note_url": NOTE_URL,
        "source_kind": "wiki",
        "detail_channel": channel,
        "source_title": data["title"],
        "source_updated_at": "",
        "data_date": data_date,
        "stale_days": stale_days,
        "source_stale": source_stale,
        "snapshot_expired": snapshot_expired,
        "snapshot_meta_mismatch": snapshot_meta_mismatch,
        "degraded_reason": degraded_reason,
        # ── v2 新增：情绪周期头部（源侧自述，如实搬运）──
        "cycle_stage": (data.get("header") or {}).get("cycle_stage", ""),
        "position_advice": (data.get("header") or {}).get("position_advice", ""),
        "themes_top": (data.get("header") or {}).get("themes_top", []),
        "summary": {"pool": len(stocks)},
        "sample_coverage": {
            "rows_parsed": len(stocks),
            "expected": None,            # 新系列无「自述总数」⇒ 不伪造 expected
            "source_channel": channel,
            "snapshot_fetched_at": data.get("fetched_at", ""),
            "snapshot_age_h": (round(data["age_h"], 2) if data.get("age_h") is not None else None),
            "truncated": False,
            "note": ("v2 换代水源「短线情绪选股」主报告全文快照（成员连接器）；"
                     "introduction 兜底通道受 ~300 字硬墙（如实降级 detail_complete=false）。"),
        },
        "detail_complete": channel == "full-snapshot",
        "wiki_latest": data["title"],
        "parse_health": {
            "total": len(stocks),
            "no_score": no_score,
            "no_score_pct": (round(no_score / len(stocks) * 100, 1) if stocks else 0),
            "note": ("v2 候选池 schema；score 缺失数必须为 0，>0 说明源表格列位变了。"),
        },
        "stocks": stocks,
        "kb": {"kb_id": KB_ID, "kb_name": KB_NAME, "kb_creator": KB_CREATOR,
               "folder_id": FOLDER_MAIN, "folder_name": FOLDER_MAIN_NAME},
    }

    # 🔴🔴 防回归：数据源日期倒退 ⇒ 绝不覆盖已发布的好版本（堵死「又回到旧版」）
    #   触发场景：快照/源意外给了比线上更旧的 data_date（如陈旧快照、源临时回滚）。
    _prev_path = os.path.join(RAW_DIR, "ima_strong_stock.json")
    _regress = False
    try:
        if os.path.exists(_prev_path):
            with open(_prev_path, encoding="utf-8") as _pf:
                _prev = json.load(_pf) or {}
            _pd = _prev.get("data_date")
            if _pd and re.fullmatch(r"\d{4}-\d{2}-\d{2}", _pd) and data_date \
                    and re.fullmatch(r"\d{4}-\d{2}-\d{2}", data_date):
                _new_d = datetime.strptime(data_date, "%Y-%m-%d").date()
                _prev_d = datetime.strptime(_pd, "%Y-%m-%d").date()
                if _new_d < _prev_d:
                    _regress = True
    except Exception as _e:
        print("[WARN] 回归检查读上一版失败（不阻断，按正常写）：%s" % _e)
    if _regress:
        # 保留上一版（已是 newer 的好版本），标注 degraded，绝不回写旧数据
        #   2026-10-16：同改走 _write_retained（重算停更态 + 停更邮件）—— 本分支正是
        #   2026-10-14~16 连续三日断更的实发通道（快照 meta 10-13 / 正文 10-12 错位）。
        try:
            with open(_prev_path, encoding="utf-8") as _pf:
                _prev = json.load(_pf) or {}
            _write_retained(
                _prev,
                "data_date-regressed(%s<%s);retained-last-good" % (
                    data_date, _prev.get("data_date")),
                snap_info=data)
            print("⛔ 数据日倒退（%s < 上一版 %s）—— 已保留上一版产物，拒绝回退到旧版。"
                  % (data_date, _prev.get("data_date")))
            return
        except Exception as _e:
            print("❌ 回归保留上一版也失败：%s" % _e)
            raise SystemExit(1)

    # 🔴 生产者自检（沿用 v1「谁产出谁负责」）：形状不对拒绝写出
    _viol = []
    for _k in ("data_date", "source_stale", "stale_days", "source_title", "cycle_stage",
               "snapshot_meta_mismatch"):
        if _k not in out:
            _viol.append("产物缺字段 %s" % _k)
    if not stocks:
        _viol.append("候选池 0 条（不应到达此处）")
    if no_score:
        _viol.append("no_score=%d（强度分列解析失败/串位）" % no_score)
    if channel == "full-snapshot" and not data_date:
        _viol.append("快照通道解析不出数据日（标题格式变了）")
    if _viol:
        print("❌ 产物自检失败 —— 拒绝写出坏产物：")
        for _v in _viol:
            print("   · " + _v)
        raise SystemExit(1)

    print("🩺 解析健康度: 候选 %d 只 · 数据日 %s · 停更 %s 天%s · %s"
          % (len(stocks), data_date, stale_days,
             "（⚠️源停更）" if source_stale else "",
             "周期=%s 仓位=%s" % (out["cycle_stage"] or "?", out["position_advice"] or "?")))

    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    raw_path = os.path.join(RAW_DIR, "ima_strong_stock.json")
    with open(raw_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("✅ 写入 %s" % raw_path)
    js_path = os.path.join(DATA_DIR, "IMA_STRONG_STOCK.js")
    with open(js_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.IMA_STRONG_STOCK = ")
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")
    print("✅ 写入 %s" % js_path)


if __name__ == "__main__":
    main()
