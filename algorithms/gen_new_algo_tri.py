#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_new_algo_tri.py — 三新算法生成器（主人 2026-10-19 批准「都做吧」，按序实现）
============================================================

三个独立信号引擎，与现有算法不重叠（差异化口径见各节注释）：
  ① 缩量回踩·VCP（个股形态）：全 kline_cache 扫描 —— 中期多头 + 放量启动后
     缩量回踩 + 波动逐级收缩（VCP）。现有算法全是「动量/共识/突破」类，
     无一覆盖「缩量回踩买点」形态 ⇒ 不重叠。
  ② 板块资金共振轮动（板块级）：行业资金流(连续流入天数/net_5d/20d) ×
     SECTOR_RS(相对强度) × 涨停热力(扩散度) × SECTOR_LEADERS(龙头) 四源共振，
     输出「周期定位（吸筹/启动/主升/退潮）+ 龙头组合」。
     🆕 2026-10-21 主人令「链路闭环」：非主升/启动板块（sector_leaders 不覆盖）
     自动补**代理龙头**（同花顺行业成分当日涨幅前3，东财行业板块/NeoData 副援），
     产物标 leaders_src 与真实龙头区分；修复 rotation 回测 rot_codes 零样本
     （原病灶：信号全是吸筹/观察行业 ⇒ leaders 恒空 ⇒ 回测归档零交集）。
     「板块资金趋势」卡只展示资金数据，无周期判定/无龙头 ⇒ 不重叠。
  ③ 龙虎榜·机构跟随（个股事件）：LHB 机构席位净买 ≥3000万 的跟随榜单，
     分「顺势跟随/逆势接货」两档。「机游共振」卡是日历统计视角，
     本卡是个股可操作跟随意愿榜 ⇒ 不重叠。

输出：
  raw_data/new_algo_tri.json    （全量明细，含中间量）
  data/NEW_ALGO_TRI.js          window.NEW_ALGO_TRI = {vcp, rotation, lhb}

🛡 门控：K线缓存不足 / LHB 缺失时对应节降级为空并标注 reason，绝不编造数据。
用法：python algorithms/gen_new_algo_tri.py [--vcp-limit N]
"""
import json
import os
import re
import sys
import glob
import time
import bisect
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "raw_data"
DATA = ROOT / "data"
KLINE_DIR = RAW / "kline_cache"
OUT_RAW = RAW / "new_algo_tri.json"
OUT_JS = DATA / "NEW_ALGO_TRI.js"

CST = timezone(timedelta(hours=8))


def now_cst():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def read_window_js(path):
    """从 data/X.js 提取 window.X = {...} 的 JSON（无则 None）。"""
    try:
        s = Path(path).read_text(encoding="utf-8", errors="replace")
        i, j = s.find("{"), s.rfind("}")
        if i < 0 or j <= i:
            return None
        return json.loads(s[i:j + 1])
    except Exception:
        return None


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return default


# ══════════════════════════════════════════════════════════════
# 名称映射：本地多源合并（gold_pool/scan_result/lhb/sector_leaders）
#           + 腾讯 gtimg 批量兜底（仅对最终命中股，≤25 只一次请求）
# ══════════════════════════════════════════════════════════════
def build_local_name_map():
    m = {}
    gp = load_json(ROOT / "out" / "gold_pool.json", {})
    for v in (gp.get("stocks") or {}).values():
        if isinstance(v, dict) and v.get("code"):
            m[str(v["code"])] = v.get("name", "")
    sr = load_json(ROOT / "out" / "scan_result.json", {})
    for key in ("all_results", "double_signals", "guanlan"):
        for v in (sr.get(key) or []):
            if isinstance(v, dict) and v.get("code"):
                m.setdefault(str(v["code"]), v.get("name", ""))
    d = load_json(RAW / "lhb_data.json", {})
    for v in (d.get("stocks") or []):
        if v.get("code"):
            m.setdefault(str(v["code"]), v.get("name", ""))
    sl = load_json(RAW / "sector_leaders.json", {})
    for s in (sl.get("sectors") or []):
        for L in (s.get("leaders") or []):
            if L.get("code"):
                m.setdefault(str(L["code"]), L.get("name", ""))
    return {k: v for k, v in m.items() if v}


def fetch_names_gtimg(codes):
    """腾讯 gtimg 批量取名（v_sz000001="51~平安银行~000001~..." 字段2=名称/字段3=代码）。"""
    out = {}
    syms = []
    for c in codes:
        if c.startswith("6"):
            syms.append("sh" + c)
        elif c[0] in ("0", "3"):
            syms.append("sz" + c)
        # 北交所（4/8/9 开头）gtimg 无可靠前缀，交由本地映射或留空
    if not syms:
        return out
    try:
        import urllib.request
        url = "https://qt.gtimg.cn/q=" + ",".join(syms[:60])
        req = urllib.request.Request(url, headers={"User-Agent": "M", "Referer": "https://gu.qq.com/"})
        raw = urllib.request.urlopen(req, timeout=15).read().decode("gbk", "replace")
        for line in raw.split(";"):
            if '="' not in line:
                continue
            body = line.split('="', 1)[1].rstrip('"')
            parts = body.split("~")
            if len(parts) > 2 and parts[2]:
                out[parts[2]] = parts[1]
    except Exception as e:
        print(f"  ⚠️ gtimg 取名失败（留空处理）: {e}")
    return out


# ══════════════════════════════════════════════════════════════
# ① 缩量回踩 · VCP
# ══════════════════════════════════════════════════════════════
def _tri_bar_files():
    """K线文件清单（ext 优先 + cache 兜底）——2026-10-21 一劳永逸修复（主人令）。

    根因（实测）：kline_cache 是 gen_strong_breakout 的**副产物缓存**（只逐晚回写
    强势股、末根碎片化），VCP 直接扫它 ⇒ 扫描池每日随强势股回写范围漂移——
    10-19/10-20 盘后批各命中 9 只、10-21 早盘批新鲜池骤降到 525 只且不含前两日
    命中票 ⇒ 0 命中，卡面「时有时无」（主人报障「昨天就没数据」）。
    修法：改读 **kline_cache_ext**（gen_lqsq_top5 在 ORDER 中先行维护的全市场
    700 根新鲜缓存，GTimg 前复权与实盘同通道、runner 持久），kline_cache 只补
    ext 缺票；同票 ext 覆盖 cache（数据更新更全）。fresh 闸与形态口径零改动。
    """
    out = {}
    ext_dir = RAW / "kline_cache_ext"
    if ext_dir.is_dir():
        for fp in glob.glob(str(ext_dir / "*.json")):
            c = Path(fp).stem
            if len(c) == 6 and c[0] in "0368":
                out[c] = fp
    for fp in glob.glob(str(KLINE_DIR / "*.json")):
        c = Path(fp).stem
        if len(c) == 6 and c[0] in "0368" and c not in out:
            out[c] = fp
    return sorted(out.items())


def scan_vcp(limit=None):
    """全市场扫描缩量回踩 VCP 形态（K线源见 _tri_bar_files：ext 优先 + cache 兜底）。

    口径（全部显式，可回测复现）：
      - 样本：K线 ≥60 根，最新一根为最新交易日
      - 中期多头：close > MA20 > MA60
      - 启动日：近 25 根内存在 vol ≥ 2.0×前5日均量 且 当日涨幅 ≥ 5%
      - 回踩：自启动日后最高收盘回撤 3%~15%（未破位）
      - 缩量：近3日均量 ≤ 启动日量×0.55 且 ≤ 启动日前5日均量×0.75
      - 波动收缩：近3日平均振幅 ≤ 启动段(启动日+1..+5)平均振幅×0.75，
                  且近3日最大振幅 ≤ 近40日最大振幅×0.65
      - 守位：close ≥ MA20×0.97
    """
    items = []
    files = [fp for _c, fp in _tri_bar_files()]
    if limit:
        files = files[:limit]
    scanned = 0
    # ── 第一遍：载池 + 取全池最新K线日（数据日闸基准）；载入即截尾 70 根
    #    （形态只用近 60 根，ext 700 根/只 × 全市场直接全载会白白多占数倍内存）──
    pool = {}
    for fp in files:
        code = Path(fp).stem
        if not code.isdigit() or len(code) != 6:
            continue
        try:
            bars = load_json(fp, [])
        except Exception:
            continue
        if not isinstance(bars, list) or len(bars) < 60:
            continue
        bars = bars[-70:]
        pool[code] = bars
    latest = max((b[-1].get("date") or "" for b in pool.values()), default="")
    fresh = {c: b for c, b in pool.items() if (b[-1].get("date") or "") == latest}
    if latest and len(fresh) < TRI_VCP_MIN_FRESH:
        return {"scanned": len(pool), "items": [], "data_date": latest,
                "fresh_count": len(fresh),
                "reason": ("K线缓存整体陈旧：全池最新日 %s（新鲜票 %d < %d）"
                           "——拒绝用旧形态冒充满仓信号，等缓存刷新" %
                           (latest, len(fresh), TRI_VCP_MIN_FRESH))}
    for code, bars in sorted(fresh.items()):
        scanned += 1
        b = bars[-60:]
        closes = [x["close"] for x in b]
        vols = [float(x.get("volume") or 0) for x in b]
        n = len(b)
        ma20 = sum(closes[-20:]) / 20.0
        ma60 = sum(closes[-60:]) / 60.0
        c = closes[-1]
        if not (c > ma20 > ma60):
            continue
        # 启动日：近 25 根内（不含最后3根回踩段）
        launch = None
        for i in range(n - 25, n - 3):
            if i < 5:
                continue
            prev5 = vols[i - 5:i]
            if not prev5 or min(prev5) <= 0:
                continue
            vma5 = sum(prev5) / len(prev5)
            pct = (closes[i] / closes[i - 1] - 1) * 100
            if vols[i] >= 2.0 * vma5 and pct >= 5.0:
                launch = i  # 取最近一次启动
        if launch is None:
            continue
        peak = max(closes[launch:])
        pullback = (peak - c) / peak * 100
        if not (3.0 <= pullback <= 15.0):
            continue
        v3 = sum(vols[-3:]) / 3.0
        v_launch = vols[launch]
        pre5 = vols[max(0, launch - 5):launch]
        v_pre5 = sum(pre5) / len(pre5) if pre5 else 0
        if v_pre5 <= 0 or v_launch <= 0:
            continue
        if not (v3 <= 0.55 * v_launch and v3 <= 0.75 * v_pre5):
            continue
        amp = lambda k: (b[k]["high"] - b[k]["low"]) / b[k - 1]["close"] * 100 if k > 0 else 0
        a3 = [amp(n - 3 + t) for t in range(3)]
        a_launch_seg = [amp(min(launch + 1 + t, n - 1)) for t in range(5)]
        avg3 = sum(a3) / 3.0
        avg_seg = sum(a_launch_seg) / len(a_launch_seg) or 1
        max3 = max(a3)
        max40 = max(amp(k) for k in range(1, n))
        if not (avg3 <= 0.75 * avg_seg and max3 <= 0.65 * max40):
            continue
        if c < ma20 * 0.97:
            continue
        contractions = sum(1 for t in range(1, 3) if a3[t] < a3[t - 1])
        pct20 = (c / closes[-21] - 1) * 100 if n >= 21 else 0
        score = (
            min(30.0, (1 - v3 / (0.55 * v_launch)) * 60)          # 缩量深度 30
            + min(25.0, (1 - avg3 / (0.75 * avg_seg)) * 50)       # 振幅收缩 25
            + min(20.0, contractions * 10 + 5)                     # 收缩级数 20
            + (20.0 if c >= ma20 else 10.0)                        # 守位 20
            + max(0.0, min(25.0, pct20 * 2))                       # 强度 25
        )
        items.append({
            "code": code,
            "close": round(c, 2),
            "pullback_pct": round(pullback, 1),
            "vol_shrink": round(v3 / v_launch, 2),        # 近3日均量/启动日量
            "amp_shrink": round(avg3 / avg_seg, 2),       # 振幅收缩比
            "contractions": contractions,
            "ma20_dist": round((c / ma20 - 1) * 100, 1),
            "pct20d": round(pct20, 1),
            "trigger": round(max(closes[-5:]) * 1.005, 2),  # 突破5日高
            "score": round(score, 1),
            "date": b[-1]["date"],
        })
    items.sort(key=lambda x: -x["score"])
    return {"scanned": scanned, "items": items[:20]}


# ══════════════════════════════════════════════════════════════
# 🆕 2026-10-21 主人令「链路闭环」：rotation 代理龙头引擎
#   病灶实证：sector_leaders.json 只覆盖主升/启动板块（2026-10-21 全市场仅
#     「厨卫电器」1 个），而 rotation 信号经 RS 闸门后全是同花顺行业名且多为
#     吸筹/观察 ⇒ leaders 恒空 ⇒ _tri_run_backtest 的 rot_codes 零样本
#     ⇒ 上线 3 天回测空表（主人令「后两个算法为什么没有真实回测数据」）。
#   修法：复用 scripts/fetch_sector_leaders.py 同款取数设施（不另起炉灶）——
#     ① 同花顺行业成分：ths_industry_cache 行业名→代码（缓存 90 个，今日 6 个
#        信号板块 6/6 命中）+ 详情页涨幅降序名单 + 腾讯行情补 chg；
#     ② 东财行业板块在线：fetch_em_boards → _resolve_bk → fetch_cons_safe
#        （其内含成员名单缓存 + 腾讯行情两层兜底）；
#     ③ NeoData「板块成分明细」末援（东财全断日）。
#   产物标记 leaders_src='proxy(...)'，与真实龙头（sector_leaders）区分，绝不混算；
#   任何一层失败返回 ([], '')，该板块 leaders 留空——不编造。
# ══════════════════════════════════════════════════════════════
ROT_PROXY_MAX = 6           # 每轮最多代理 enriched 板块数（按 score 降序，防网络预算爆）
ROT_PROXY_BUDGET_SEC = 90   # 代理龙头总时间预算（东财/同花顺全断日不拖死 B 批）


def _rot_proxy_engine():
    """懒加载代理龙头引擎。返回 fetch(name) -> (rows, src)；
    rows=[{code,name,chg,price}] 涨幅降序；失败 ([], '')。任何异常绝不外抛。"""
    def _dead(_n):
        return [], ""

    try:
        _sp = str(ROOT / "scripts")
        if _sp not in sys.path:
            sys.path.insert(0, _sp)
        import fetch_sector_leaders as fsl
    except Exception as e:
        print("  ⚠️ 代理龙头引擎加载失败（%s）—— 本轮无代理龙头" % str(e)[:80])
        return _dead

    _t0 = time.time()
    _n = [0]
    _boards = [None]

    def _em_boards():
        if _boards[0] is None:
            try:
                _boards[0] = fsl.fetch_em_boards()
            except Exception:
                _boards[0] = ({}, {})
        return _boards[0]

    def _fetch(name):
        if _n[0] >= ROT_PROXY_MAX or (time.time() - _t0) >= ROT_PROXY_BUDGET_SEC:
            return [], ""
        # ① 同花顺行业成分（rotation 名即同花顺行业名）
        try:
            members = fsl._ths_members_by_name(name)
            if members:
                try:
                    rows = fsl._tx_cons(members)
                except Exception:
                    # 腾讯行情不可用：详情页本身已按涨幅降序，chg 留空不编造
                    rows = [{"code": m.get("code"), "name": m.get("name"),
                             "chg": None, "price": None} for m in members]
                if rows:
                    _n[0] += 1        # 闸门按**成功 enriched 数**计：取数失败的
                    return rows, "ths"   # 板块不占额度，不饿死后面能成的板块
        except Exception as e:
            print("  ⚠️ 代理龙头(ths) %s: %s" % (name, str(e)[:60]))
        # ② 东财行业板块在线（fetch_cons_safe 内含名单缓存 + 腾讯兜底）
        try:
            exact, norm = _em_boards()
            bk, how = fsl._resolve_bk(name, exact, norm)
            if bk:
                try:
                    rows = fsl.fetch_cons_safe(bk)
                except Exception:
                    rows = fsl._neo_cons(name)   # ③ NeoData 末援
                if rows:
                    _n[0] += 1
                    return rows, "em:" + (how or "exact")
        except Exception as e:
            print("  ⚠️ 代理龙头(em) %s: %s" % (name, str(e)[:60]))
        return [], ""

    return _fetch


# ══════════════════════════════════════════════════════════════
# ② 板块资金共振轮动
# ══════════════════════════════════════════════════════════════
def calc_rotation():
    sf = load_json(RAW / "sector_fund_flow_trend.json", {})
    rs = read_window_js(DATA / "SECTOR_RS.js") or {}
    hm = read_window_js(DATA / "LIMIT_UP_HEATMAP.js") or {}
    sl = load_json(RAW / "sector_leaders.json", {})

    rs_map = {}
    for s in (rs.get("sectors") or []):
        rs_map[s.get("name")] = s
    # 涨停热度：每板块近5列合计
    heat = {}
    try:
        dts = hm.get("dates") or []
        for sec in (hm.get("sectors") or []):
            heat[sec.get("name")] = sum(v or 0 for v in (sec.get("data") or [])[-5:])
    except Exception:
        pass
    lead_map = {}
    for s in (sl.get("sectors") or []):
        lead_map[s.get("name")] = s

    rows = []
    def handle(sec, direction):
        name = sec.get("name")
        r = rs_map.get(name) or {}
        net5 = sec.get("net_5d") or 0
        net20 = sec.get("net_20d") or 0
        cons = int(sec.get("consecutive_days") or 0)
        p5, p20, p60 = r.get("pct_5d"), r.get("pct_20d"), r.get("pct_60d")
        if p5 is None:
            return  # 无 RS 数据不评级（不编造）
        h5 = heat.get(name, 0)
        # ── 周期定位 ──
        if net5 < 0 and (p5 or 0) < 0 and (p60 or 0) > 0:
            stage = "退潮"
        elif net5 > 0 and net20 <= 0 and (p20 or 0) < 0:
            stage = "吸筹"
        elif net5 > 0 and cons >= 3 and (p5 or 0) > 0 and h5 >= 3:
            stage = "启动"
        elif net20 > 0 and (p20 or 0) > 0 and (p60 or 0) > 0:
            stage = "主升"
        else:
            stage = "观察"
        flow_score = min(40.0, cons * 4 + max(0.0, min(15.0, net5 / 2)))
        rs_score = max(0.0, min(30.0, 15 + (p5 or 0) * 1.5 + (p20 or 0) * 0.5))
        heat_score = min(20.0, h5 * 3)
        lead = lead_map.get(name)
        lead_score = 10.0 if lead else 0.0
        score = flow_score + rs_score + heat_score + lead_score
        leaders = []
        leaders_src = ""
        if lead:
            for L in (lead.get("leaders") or [])[:3]:
                leaders.append({"name": L.get("name"), "chg": L.get("chg"), "code": L.get("code")})
            leaders_src = "sector_leaders"
        rows.append({
            "sector": name, "type": sec.get("type", ""), "stage": stage,
            "consecutive_days": cons, "net_5d": net5, "net_20d": net20,
            "rs_5d": p5, "rs_20d": p20, "rs_60d": p60,
            "heat_5d": h5, "score": round(score, 1), "leaders": leaders,
            "leaders_src": leaders_src,
        })

    for sec in (sf.get("sectors_in") or []):
        handle(sec, "in")
    # 退潮判定需要 out 方向的板块（sectors_out 可能为空）
    for sec in (sf.get("sectors_out") or []):
        handle(sec, "out")
    rows.sort(key=lambda x: -x["score"])
    # 🆕 2026-10-21 主人令「链路闭环」：无真实龙头的信号板块（吸筹/观察/退潮等，
    #   sector_leaders 只覆盖主升/启动）补**代理龙头**——同花顺行业成分当日涨幅前 3
    #   （rotation 名即同花顺行业名）+ 东财行业板块副援；标记 leaders_src='proxy(...)'
    #   与真实龙头区分，前端卡面同标「（代理）」。只 enrichment 上榜 items（rows[:12]，
    #   与 _tri_run_backtest 的 rot_codes 取数范围一致），按 score 降序、条数/时间
    #   双闸门（_rot_proxy_engine）。全失败该板块 leaders 留空——不编造。
    _need = [r for r in rows[:12] if not r.get("leaders")]
    if _need:
        _proxy = _rot_proxy_engine()
        for r in _need:
            prows, src = _proxy(r.get("sector") or "")
            if prows:
                r["leaders"] = [{"name": x.get("name"), "chg": x.get("chg"),
                                 "code": x.get("code")} for x in prows[:3]]
                r["leaders_src"] = "proxy(%s)" % (src or "?")
                print("  🔗 代理龙头 %s → %s" % (
                    r["sector"], "、".join(str(x.get("name")) for x in prows[:3])))
    return {"count": len(rows), "items": rows[:12]}


# ══════════════════════════════════════════════════════════════
# ③ 龙虎榜 · 机构跟随
# ══════════════════════════════════════════════════════════════
def _lhb_picks_from_stocks(stocks, date_str):
    """LHB 机构跟随信号规则 —— **唯一实现**，实盘(calc_lhb_follow)与时点回填共用。

    规则（全部显式、可复现）：category ∈ (机构独买, 机游共振) 且 机构净买 ≥3000万
    → 信号；按 score 降序取 TOP 15（与实盘卡面 items[:15] 同口径）。
    🛡 2026-10-21 抽出为本函数：回填若另抄一份规则，实盘与回测口径分叉 ＝ 双权威
    （主人铁律禁）；实测 10-19 历史节点规则命中与实盘归档逐只一致，复刻无误。
    """
    items = []
    for s in (stocks or []):
        cat = s.get("category", "")
        if cat not in ("机构独买", "机游共振"):
            continue
        try:
            inst_net = float(s.get("inst_net_万") or 0)
            yz_net = float(s.get("yz_net_万") or 0)
            pct = float(s.get("pct") or 0)
        except (TypeError, ValueError):
            continue
        if inst_net < 3000:  # 门槛：机构净买 ≥3000万
            continue
        follow = "顺势跟随" if pct > 0 else "逆势接货"
        score = (
            min(50.0, inst_net / 200.0)                # 机构净买额（亿级封顶）50
            + (15.0 if cat == "机游共振" else 5.0)      # 机游共振加分 15
            + max(0.0, min(20.0, yz_net / 300.0))      # 游资净买 20
            + max(0.0, min(15.0, pct * 1.5))           # 顺势 15（逆势接货不改分，标注档位）
        )
        items.append({
            "code": s.get("code"), "name": s.get("name"),
            "date": date_str,
            "pct": round(pct, 2), "inst_net_wan": round(inst_net, 0),
            "yz_net_wan": round(yz_net, 0), "category": cat,
            "follow": follow, "score": round(score, 1),
        })
    items.sort(key=lambda x: -x["score"])
    return items[:15]


def calc_lhb_follow():
    d = load_json(RAW / "lhb_data.json", {})
    date_str = (lambda _s: "%s-%s-%s" % (_s[:4], _s[4:6], _s[6:8])
                if len(_s) == 8 and _s.isdigit() else _s)(str(d.get("date") or ""))
    items = _lhb_picks_from_stocks(d.get("stocks"), date_str)
    return {"date": d.get("date", ""), "count": len(items), "items": items}


# ══════════════════════════════════════════════════════════════
# ④ 真实信号流回测（仿 strategy_intraday_momentum.py / gen_lqsq_top5.py）
#    每日信号 → 次开买入 → 持有 N 日收盘卖出（扣双边 0.3%）→ 胜率/均益/基准；
#    样本随持有天数成熟累积，未走满不计入；基准 = 全市场等权（剔 ST/退、价≥2）。
#    三算法（vcp/rotation/lhb）共用同一归档文件 new_algo_tri_history.json。
# ══════════════════════════════════════════════════════════════
# 🛡 2026-10-20 数据日闸（一劳永逸·防旧形态冒充满仓信号）：
#   实证 10-20 早批次：vcp 命中 9 只的 K 线 date 散布 09-07~10-14（kline_cache 陈旧），
#   却被打包进 10-20 批次、按自然日归档进前向回测 ⇒ 信号日与形态日错配近一个月。
#   门控：① vcp 只收「末根K线=全池最新日」的票；新鲜票不足 ⇒ 整节降级不产出；
#         ② 归档 signal_date 用**信号真实数据日**而非自然日；
#         ③ lhb 用榜单自身 date；数据日缺失/陈旧 ⇒ 不归档（保留旧档，绝不污染）。
TRI_STALE_SKIP_DAYS = 5       # 容忍滞后（停牌/节假日/缓存欠账）
TRI_VCP_MIN_FRESH = 200       # 新鲜票下限：低于此判「缓存整体陈旧」，VCP 整节降级
TRI_COST = 0.003
TRI_N_LIST = [1, 3, 5, 10, 20]
TRI_HISTORY = RAW / "new_algo_tri_history.json"
TRI_BACKTEST_JS = DATA / "NEW_ALGO_TRI_BACKTEST.js"

# ══════════════════════════════════════════════════════════════
# 🛡 2026-10-21 一劳永逸修复（主人令「可以，确保科学有效」）—— 两块：
#   A. 信号票取价自愈（_tri_ensure_signal_bars）：
#      实证 10-21：10-19/10-20 两批 9 只 lhb 信号票末根散布 09-02~10-20
#      （kline_cache_ext 仅 226 只全新鲜池且不含它们；kline_cache 是
#      gen_strong_breakout 副产物只回写强势股）⇒ 回测「次开买入」取不到价
#      ⇒ by_period 恒空、记分卡 sample=None（算法被误判「无样本」）。
#      修法：按已成熟窗口逐票检测，缺覆盖即 GTimg 前复权补拉 700 根落 ext。
#   B. LHB 归档时点回填（_tri_backfill_lhb_archive）：
#      lhb_history.json 有 2026-06-10 起逐日盘后快照（stage_to_raw 累积，
#      字段与信号规则同构、10-19 规则命中与实盘归档逐只一致已实证）⇒ 按
#      同一规则回填，让回测立刻有 4 个月真实样本，而非空等 30 天。
#      回填条目带 backfill=true 标记，method 明示「时点回填+实盘跟踪」双来源。
# ══════════════════════════════════════════════════════════════
KLINE_EXT_DIR = RAW / "kline_cache_ext"   # 与 gen_lqsq_top5 同域（ext 优先 + cache 兜底）
TRI_EXT_BARS = 700                        # 补拉根数（与 gen_lqsq_top5 EXT_BARS 对齐）
TRI_FETCH_MIN_BARS = 20                   # 次新股放行（<60 根闸误杀新股，见 data_source_gtimg）
TRI_ENSURE_MAX_CODES = 300                # 单轮补拉只数上限（防归档膨胀失控，剩余下轮接力）
TRI_ENSURE_BUDGET_SEC = 150               # 单轮补拉时间预算


def _tri_load_bars():
    """全 A 日线缓存 → {code:(dates,bars)} + 全局交易日历 + 每票 date→index。

    2026-10-21 一劳永逸：与 scan_vcp 同源走 _tri_bar_files（ext 优先 + cache 兜底）——
    历史信号票（如 10-19/10-20 的 9 只 VCP）多数不在 kline_cache 新鲜数据里，
    只扫 cache 会让回测连「次开买入」的价格都拿不到（by_period 恒空的帮凶之一）。
    """
    series, all_dates = {}, set()
    for _c, fp in _tri_bar_files():
        code = Path(fp).stem
        if len(code) != 6 or code[0] not in "0368":
            continue
        try:
            bars = json.loads(Path(fp).read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(bars, list) or len(bars) < 60:
            continue
        ds = [b.get("date") for b in bars]
        series[code] = (ds, bars)
        all_dates.update(d for d in ds if d)
    gdates = sorted(all_dates)
    pos = {c: {d: i for i, d in enumerate(ds)} for c, (ds, _) in series.items()}
    return series, pos, gdates


def _tri_st_set():
    """ST / 退 股票代码集合（基准排除用）。"""
    st = set()
    try:
        d = json.loads((RAW / "stock_names.json").read_text(encoding="utf-8"))
        rows = d.get("data") if isinstance(d, dict) else d
        if isinstance(rows, list):
            for it in rows:
                if isinstance(it, dict) and "name" in it and "code" in it:
                    nm = str(it["name"])
                    if "ST" in nm.upper() or "退" in nm:
                        st.add(str(it["code"]))
    except Exception:
        pass
    return st


def _tri_fetch_bars(code):
    """补拉单票日K（前复权）→ kline records（与缓存同构）；失败返回 None。

    通道：GTimg 优先（本机/云端同通道，2026-10-21 本机实测可通、与缓存零差异），
    scanner.fetch_a_daily 兜底（mootdx/BaoStock/东财链，适配 GTimg 被墙的环境）。
    次新股放行 min_bars=20：上市不足 60 个交易日的新票（如宇树科技 688836）
    若按 60 根闸一律拒收 ⇒ LHB 信号票里的新股永远无法回测（样本偏差）。
    """
    market = "sh" if code.startswith(("6", "688", "9")) else "sz"
    df = None
    try:
        import data_source_gtimg as _gt
        df = _gt.fetch_a_daily_gtimg(code, market=market, bars=TRI_EXT_BARS,
                                     min_bars=TRI_FETCH_MIN_BARS)
    except Exception:
        df = None
    if df is None:
        try:
            from scanner import fetch_a_daily
            df = fetch_a_daily(code, bars=TRI_EXT_BARS)
        except Exception:
            df = None
    if df is None:
        return None
    try:
        need = ("date", "open", "close", "high", "low", "volume")
        if any(c not in df.columns for c in need):
            return None
        return [{"date": str(d), "open": round(float(o), 4), "high": round(float(h), 4),
                 "low": round(float(l), 4), "close": round(float(c), 4),
                 "volume": round(float(v), 2)}
                for d, o, h, l, c, v in zip(df["date"], df["open"], df["high"],
                                            df["low"], df["close"], df["volume"])]
    except Exception:
        return None


def _tri_ext_save(code, records):
    """原子写 kline_cache_ext/<code>.json（tmp + replace，防半写文件）。"""
    try:
        KLINE_EXT_DIR.mkdir(parents=True, exist_ok=True)
        tmp = KLINE_EXT_DIR / ("%s.json.tmp" % code)
        tmp.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        os.replace(str(tmp), str(KLINE_EXT_DIR / ("%s.json" % code)))
        return True
    except Exception:
        return False


def _tri_backfill_lhb_archive(hist):
    """LHB 归档时点回填（2026-10-21 主人令「确保科学有效」）。

    数据源：raw_data/lhb_history.json 逐日盘后快照（stage_to_raw 累积，
    2026-06-10 起；字段与信号规则同构）+ raw_data/lhb_data.json（当日全量，
    覆盖 history 中缺 stocks 的日期——fetch_lhb 曾以 {trading,pure} 格式
    占写过 10-20，全量节点以 lhb_data.json 为准）。

    时点完整性：每个节点 = 当日盘后发布的榜单（信号字段为当日原值；席位别名
    标签可能后续增补，不影响 category/inst_net 信号口径）；买点=信号日次日
    开盘、卖点=持有 N 交易日收盘 ⇒ 无未来函数。实盘归档条目优先（as-of 原票），
    回填只补缺失日期；回填条目带 backfill=true，payload method 明示双来源。
    返回回填充数。
    """
    hist_lhb = [h for h in (hist.get("lhb") or [])]
    have = {h.get("signal_date") for h in hist_lhb}
    sources = []
    lhb_hist = load_json(RAW / "lhb_history.json", {})
    for k, node in (lhb_hist or {}).items():
        if k in ("update_time", "range") or not isinstance(node, dict):
            continue
        stocks = node.get("stocks") or []
        if not stocks:
            continue
        sources.append((k, stocks))
    cur = load_json(RAW / "lhb_data.json", {})
    if cur.get("stocks"):
        ds = str(cur.get("date") or "")
        iso = "%s-%s-%s" % (ds[:4], ds[4:6], ds[6:8]) if len(ds) == 8 and ds.isdigit() else ""
        if iso:
            sources.append((iso, cur.get("stocks")))
    added = 0
    for day, stocks in sorted(sources):
        if day in have:
            continue
        picks = [x["code"] for x in _lhb_picks_from_stocks(stocks, day) if x.get("code")]
        if not picks:
            continue
        hist_lhb.append({"signal_date": day, "picks": picks, "backfill": True})
        have.add(day)
        added += 1
    hist_lhb.sort(key=lambda h: h.get("signal_date") or "")
    hist["lhb"] = hist_lhb
    if added:
        print("  🕰 LHB 归档时点回填：+%d 日（现共 %d 日，实盘+回填双来源）" % (
            added, len(hist_lhb)))
    return added


def _tri_ensure_signal_bars(hist, series, pos, gdates):
    """信号票取价自愈（2026-10-21 一劳永逸修复，主人令「确保科学有效」）。

    根因实证：lhb/vcp 信号票多数不在 kline_cache_ext（仅 226 只全新鲜池），
    kline_cache 又是 gen_strong_breakout 副产物（只回写强势股）⇒ 10-19/10-20
    两批 9 只 lhb 信号票末根散布 09-02~10-20，回测「次开买入」取不到价
    ⇒ by_period 恒空、记分卡 sample=None（算法被误判「无样本」实为「取价缺失」）。

    修法：回测取价前，按**已成熟窗口**（买点=信号日次日、卖点=买点+N 个交易日，
    两者均已在全局日历中）逐票检测 ext/cache 覆盖；缺覆盖即 _tri_fetch_bars
    补拉 700 根落 ext（tmp+replace 原子写）。预算内收敛：每票成功一次即永久
    覆盖全部历史窗口，下轮零成本。返回 {"fetched": [...], "failed": [...]}。
    """
    t0 = time.time()
    need = set()
    for _key, lst in (hist or {}).items():
        for h in (lst or []):
            d = h.get("signal_date") or ""
            gi = bisect.bisect_left(gdates, d)
            if gi >= len(gdates) or gdates[gi] != d:
                continue
            for N in TRI_N_LIST:
                tx = gi + 1 + N
                if tx >= len(gdates):
                    continue  # 未成熟（卖点在未来）——现在无需取价
                dt_i, dt_x = gdates[gi + 1], gdates[tx]
                for code in (h.get("picks") or []):
                    p = pos.get(code)
                    if p is not None and p.get(dt_i) is not None and p.get(dt_x) is not None:
                        continue
                    need.add(code)
    fetched, failed = [], []
    for i, code in enumerate(sorted(need)):
        if i >= TRI_ENSURE_MAX_CODES or (time.time() - t0) > TRI_ENSURE_BUDGET_SEC:
            failed.append(code)  # 预算/只数耗尽：下轮接力（归档在，不会漏）
            continue
        recs = _tri_fetch_bars(code)
        if recs and _tri_ext_save(code, recs):
            fetched.append(code)
        else:
            failed.append(code)
    if need:
        print("  🛠 信号票取价自愈：需补 %d 只 → 成功 %d、仍缺 %d（%.0fs）" % (
            len(need), len(fetched), len(failed), time.time() - t0))
        if failed:
            print("     ⚠️ 仍缺（停牌/退市/网络，如实不计入，绝不编造）: %s" % ", ".join(failed[:20]))
    return {"fetched": fetched, "failed": failed}


def _tri_backtest_section(series, pos, gdates, history, st_set):
    """history: [{signal_date, picks:[codes]}] → by_period（真实信号流前向回测）。

    返回 (by, total, missing)：missing = 已成熟窗口（买点+卖点均在日历中）但
    取不到价的信号票集合（补拉后仍缺：停牌/退市/价格缺失）——如实透出，
    绝不把「算不出」静默当成「没信号」（2026-10-21 主人令「确保科学有效」）。
    """
    picks_map = {h["signal_date"]: (h.get("picks") or []) for h in history}
    sig_days = sorted(picks_map.keys())
    bench_cache = {}

    def bench(gi, N):
        key = (gi, N)
        if key in bench_cache:
            return bench_cache[key]
        ti, tx = gi + 1, gi + 1 + N
        if tx >= len(gdates):
            bench_cache[key] = None
            return None
        dt_i, dt_x = gdates[ti], gdates[tx]
        s, k = 0.0, 0
        for code, p in pos.items():
            if code in st_set:
                continue
            ii, xx = p.get(dt_i), p.get(dt_x)
            if ii is None or xx is None or ii == 0 or xx == 0:
                continue
            bars = series[code][1]
            pc = float(bars[ii - 1].get("close") or 0)
            op = float(bars[ii].get("open") or 0)
            xc = float(bars[xx].get("close") or 0)
            if pc <= 0 or op <= 0 or xc <= 0:
                continue
            if pc < 2.0:  # 价格≥2 过滤（与文档基准口径对齐）
                continue
            s += xc / op - 1.0 - TRI_COST
            k += 1
        res = (s, k) if k >= 50 else None
        bench_cache[key] = res
        return res

    by = {}
    missing = set()
    for N in TRI_N_LIST:
        rets, bs, bc = [], 0.0, 0
        for d in sig_days:
            gi = bisect.bisect_left(gdates, d)
            if gi >= len(gdates) or gdates[gi] != d:
                continue
            for code in (picks_map.get(d) or []):
                ti, tx = gi + 1, gi + 1 + N
                if tx >= len(gdates):
                    continue  # 未成熟：卖点在未来，现在无需取价
                p = pos.get(code)
                ii = xx = None
                if p:
                    ii, xx = p.get(gdates[ti]), p.get(gdates[tx])
                if not p or ii is None or xx is None or ii == 0 or xx == 0:
                    missing.add(code)  # 已成熟但取不到价（补拉后仍缺）——如实计数
                    continue
                bars = series[code][1]
                pc = float(bars[ii - 1].get("close") or 0)
                op = float(bars[ii].get("open") or 0)
                xc = float(bars[xx].get("close") or 0)
                if pc <= 0 or op <= 0 or xc <= 0:
                    missing.add(code)  # 有K线但价格缺失——同样不计入、不编造
                    continue
                rets.append(xc / op - 1.0 - TRI_COST)
            b = bench(gi, N)
            if b is not None:
                bs += b[0] / b[1]   # 先除以个股数 k 得「当日等权均值」，再跨日累加（仿日内动量 bsum += s/k）
                bc += 1
        if rets:
            by[str(N)] = {
                "samples": len(rets),
                "win_rate": round(100.0 * sum(1 for r in rets if r > 0) / len(rets), 1),
                "avg_return": round(100.0 * sum(rets) / len(rets), 2),
                "best_return": round(100.0 * max(rets), 2),
                "worst_return": round(100.0 * min(rets), 2),
                "bench_avg_return": round(100.0 * bs / bc, 2) if bc else None,
                "bench_days": bc,
            }
    total = sum(len(h.get("picks") or []) for h in history)
    return by, total, sorted(missing)


def _tri_run_backtest(out):
    today = datetime.now(CST).strftime("%Y-%m-%d")
    vcp_codes = [x["code"] for x in (out.get("vcp") or {}).get("items") or [] if x.get("code")]
    lhb_codes = [x["code"] for x in (out.get("lhb") or {}).get("items") or [] if x.get("code")]
    rot_codes = []
    for it in (out.get("rotation") or {}).get("items") or []:
        for L in (it.get("leaders") or []):
            c = L.get("code")
            if c:
                rot_codes.append(c)
    # 载入/更新归档（同 signal_date 去重，防重跑重复追加）
    # 🛡 2026-10-20 数据日闸：signal_date = 信号**真实数据日**（非自然日）——
    #   vcp=全池最新K线日；lhb=榜单 date（20261019→2026-10-19）；rotation=板块数据日。
    #   无数据日/无信号 ⇒ 不归档（保留旧档，绝不用陈旧数据污染前向跟踪）。
    hist = load_json(TRI_HISTORY, {"vcp": [], "rotation": [], "lhb": []})

    def _norm_day(s):
        s = str(s or "").strip().replace("-", "")
        if len(s) == 8 and s.isdigit():
            return "%s-%s-%s" % (s[:4], s[4:6], s[6:8])
        return str(s or "")

    _sf_day = ""
    try:
        _sf_day = _norm_day((load_json(RAW / "sector_fund_flow_trend.json", {})
                             .get("update_time") or "")[:10])
    except Exception:
        pass
    sig_days = {
        "vcp": (out.get("vcp") or {}).get("data_date") if (out.get("vcp") or {}).get("items") else "",
        "rotation": _sf_day if rot_codes else "",
        "lhb": _norm_day((out.get("lhb") or {}).get("date")) if lhb_codes else "",
    }
    for key, codes in (("vcp", vcp_codes), ("rotation", rot_codes), ("lhb", lhb_codes)):
        d = sig_days.get(key) or ""
        if not d:
            print("  ⏭ %s 无数据日/无信号 —— 不归档（保留旧档）" % key)
            continue
        lst = [h for h in (hist.get(key) or []) if h.get("signal_date") != d]
        lst.append({"signal_date": d, "picks": codes})
        hist[key] = lst
    # 🕰 LHB 时点回填（2026-10-21）：lhb_history 逐日快照按同一规则补缺失日期，
    #   实盘条目优先。回填后才落盘，保证归档文件即完整状态。
    _tri_backfill_lhb_archive(hist)
    TRI_HISTORY.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    # 计算（载入全 A 日线缓存 + ST 集合）
    series, pos, gdates = _tri_load_bars()
    # 🛠 信号票取价自愈（2026-10-21）：缺覆盖的信号票 GTimg 补拉落 ext，再重载生效
    ensure = _tri_ensure_signal_bars(hist, series, pos, gdates)
    if ensure["fetched"]:
        series, pos, gdates = _tri_load_bars()
    st_set = _tri_st_set()
    payload = {"update_time": now_cst()}
    for key in ("vcp", "rotation", "lhb"):
        by, total, miss = _tri_backtest_section(series, pos, gdates, hist.get(key) or [], st_set)
        sd = [h["signal_date"] for h in (hist.get(key) or [])]
        bf = sum(1 for h in (hist.get(key) or []) if h.get("backfill"))
        src = "new_algo_tri_history 逐日真实信号归档（上线首日即建，含已回落票，防幸存者偏差）"
        if key == "lhb" and bf:
            src += ("；另含 %d 日时点回填（lhb_history 逐日盘后快照按同一信号规则回补，"
                    "实盘条目优先）" % bf)
        payload[key] = {
            "update_time": now_cst(),
            "method": ("真实信号流口径（2026-10-19 主人令）：每日盘后产出信号 → 次开买入、持有 N 个交易日"
                       "收盘卖出（前复权·扣双边 0.3%）；基准=全市场等权（剔 ST/退、价格≥2）。"
                       "样本随持有天数成熟累积，未走满不计入。"),
            "signal_source": src,
            "track_start": min(sd) if sd else today,
            "signal_date_range": ("%s ~ %s" % (min(sd), max(sd))) if sd else today,
            "total_signals": total,
            "backfill_days": bf,
            "live_days": len(sd) - bf,
            "cost_adjusted": True,
            "price_missing": miss,
            "price_missing_note": (
                "%d 只信号票已成熟但取不到价（停牌/退市/价格缺失，补拉后仍缺）——"
                "如实不计入样本，绝不用陈旧数据充数" % len(miss)) if miss else None,
            "summary": {"by_period": by},
        }
    TRI_BACKTEST_JS.write_text(
        "window.NEW_ALGO_TRI_BACKTEST = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8")
    print("  ✅ 回测已写 %s（vcp档=%d rotation档=%d lhb档=%d）" % (
        TRI_BACKTEST_JS.name, len(payload["vcp"]["summary"]["by_period"]),
        len(payload["rotation"]["summary"]["by_period"]),
        len(payload["lhb"]["summary"]["by_period"])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vcp-limit", type=int, default=None)
    args = ap.parse_args()

    print("=" * 60)
    print(f"  三新算法生成器  —  {now_cst()}")
    print("=" * 60)

    out = {"update_time": now_cst()}

    try:
        out["vcp"] = scan_vcp(args.vcp_limit)
        # 名称映射：本地多源合并 + gtimg 兜底（仅 TOP 命中股）
        _missing = [x["code"] for x in out["vcp"]["items"] if not x.get("name")]
        _nm = build_local_name_map()
        _need = [c for c in _missing if c not in _nm]
        if _need:
            _nm.update(fetch_names_gtimg(_need))
        for x in out["vcp"]["items"]:
            x["name"] = x.get("name") or _nm.get(x["code"], "")
        print(f"  ① 缩量回踩VCP: 扫描 {out['vcp']['scanned']} 只，命中 {len(out['vcp']['items'])}")
    except Exception as e:
        out["vcp"] = {"scanned": 0, "items": [], "reason": f"error: {e}"}
        print(f"  ① VCP 失败: {e}")

    try:
        out["rotation"] = calc_rotation()
        print(f"  ② 板块共振轮动: {out['rotation']['count']} 个板块参与，输出 {len(out['rotation']['items'])}")
    except Exception as e:
        out["rotation"] = {"count": 0, "items": [], "reason": f"error: {e}"}
        print(f"  ② 轮动失败: {e}")

    try:
        out["lhb"] = calc_lhb_follow()
        print(f"  ③ LHB机构跟随: {out['lhb']['date']} 榜单，命中 {len(out['lhb']['items'])}")
    except Exception as e:
        out["lhb"] = {"date": "", "count": 0, "items": [], "reason": f"error: {e}"}
        print(f"  ③ LHB 失败: {e}")

    # ── 真实信号流回测（三算法共用归档 new_algo_tri_history.json → NEW_ALGO_TRI_BACKTEST.js）──
    try:
        _tri_run_backtest(out)
    except Exception as e:
        print(f"  ⚠️ 三新算法回测计算失败（不影响信号产出）: {e}")

    OUT_RAW.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    OUT_JS.write_text("window.NEW_ALGO_TRI = " + json.dumps(out, ensure_ascii=False) + ";\n",
                      encoding="utf-8")
    print(f"  ✅ 已写 {OUT_RAW.name} / {OUT_JS.name}")


if __name__ == "__main__":
    main()
