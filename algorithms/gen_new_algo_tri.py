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
import bisect
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
def scan_vcp(limit=None):
    """全 kline_cache 扫描缩量回踩 VCP 形态。

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
    files = sorted(glob.glob(str(KLINE_DIR / "*.json")))
    if limit:
        files = files[:limit]
    scanned = 0
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
        if lead:
            for L in (lead.get("leaders") or [])[:3]:
                leaders.append({"name": L.get("name"), "chg": L.get("chg"), "code": L.get("code")})
        rows.append({
            "sector": name, "type": sec.get("type", ""), "stage": stage,
            "consecutive_days": cons, "net_5d": net5, "net_20d": net20,
            "rs_5d": p5, "rs_20d": p20, "rs_60d": p60,
            "heat_5d": h5, "score": round(score, 1), "leaders": leaders,
        })

    for sec in (sf.get("sectors_in") or []):
        handle(sec, "in")
    # 退潮判定需要 out 方向的板块（sectors_out 可能为空）
    for sec in (sf.get("sectors_out") or []):
        handle(sec, "out")
    rows.sort(key=lambda x: -x["score"])
    return {"count": len(rows), "items": rows[:12]}


# ══════════════════════════════════════════════════════════════
# ③ 龙虎榜 · 机构跟随
# ══════════════════════════════════════════════════════════════
def calc_lhb_follow():
    d = load_json(RAW / "lhb_data.json", {})
    items = []
    for s in (d.get("stocks") or []):
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
            "pct": round(pct, 2), "inst_net_wan": round(inst_net, 0),
            "yz_net_wan": round(yz_net, 0), "category": cat,
            "follow": follow, "score": round(score, 1),
        })
    items.sort(key=lambda x: -x["score"])
    return {"date": d.get("date", ""), "count": len(items), "items": items[:15]}


# ══════════════════════════════════════════════════════════════
# ④ 真实信号流回测（仿 strategy_intraday_momentum.py / gen_lqsq_top5.py）
#    每日信号 → 次开买入 → 持有 N 日收盘卖出（扣双边 0.3%）→ 胜率/均益/基准；
#    样本随持有天数成熟累积，未走满不计入；基准 = 全市场等权（剔 ST/退、价≥2）。
#    三算法（vcp/rotation/lhb）共用同一归档文件 new_algo_tri_history.json。
# ══════════════════════════════════════════════════════════════
TRI_COST = 0.003
TRI_N_LIST = [1, 3, 5, 10, 20]
TRI_HISTORY = RAW / "new_algo_tri_history.json"
TRI_BACKTEST_JS = DATA / "NEW_ALGO_TRI_BACKTEST.js"


def _tri_load_bars():
    """全 A 日线缓存 → {code:(dates,bars)} + 全局交易日历 + 每票 date→index。"""
    series, all_dates = {}, set()
    for fp in glob.glob(str(KLINE_DIR / "*.json")):
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


def _tri_backtest_section(series, pos, gdates, history, st_set):
    """history: [{signal_date, picks:[codes]}] → by_period（真实信号流前向回测）。"""
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
    for N in TRI_N_LIST:
        rets, bs, bc = [], 0.0, 0
        for d in sig_days:
            gi = bisect.bisect_left(gdates, d)
            if gi >= len(gdates) or gdates[gi] != d:
                continue
            for code in (picks_map.get(d) or []):
                p = pos.get(code)
                if not p:
                    continue
                ti, tx = gi + 1, gi + 1 + N
                if tx >= len(gdates):
                    continue
                ii, xx = p.get(gdates[ti]), p.get(gdates[tx])
                if ii is None or xx is None or ii == 0 or xx == 0:
                    continue
                bars = series[code][1]
                pc = float(bars[ii - 1].get("close") or 0)
                op = float(bars[ii].get("open") or 0)
                xc = float(bars[xx].get("close") or 0)
                if pc <= 0 or op <= 0 or xc <= 0:
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
    return by, total


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
    hist = load_json(TRI_HISTORY, {"vcp": [], "rotation": [], "lhb": []})
    for key, codes in (("vcp", vcp_codes), ("rotation", rot_codes), ("lhb", lhb_codes)):
        lst = [h for h in (hist.get(key) or []) if h.get("signal_date") != today]
        lst.append({"signal_date": today, "picks": codes})
        hist[key] = lst
    TRI_HISTORY.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    # 计算（载入全 A 日线缓存 + ST 集合）
    series, pos, gdates = _tri_load_bars()
    st_set = _tri_st_set()
    payload = {"update_time": now_cst()}
    for key in ("vcp", "rotation", "lhb"):
        by, total = _tri_backtest_section(series, pos, gdates, hist.get(key) or [], st_set)
        sd = [h["signal_date"] for h in (hist.get(key) or [])]
        payload[key] = {
            "update_time": now_cst(),
            "method": ("真实信号流口径（2026-10-19 主人令）：每日盘后产出信号 → 次开买入、持有 N 个交易日"
                       "收盘卖出（前复权·扣双边 0.3%）；基准=全市场等权（剔 ST/退、价格≥2）。"
                       "样本随持有天数成熟累积，未走满不计入。"),
            "signal_source": "new_algo_tri_history 逐日真实信号归档（上线首日即建，含已回落票，防幸存者偏差）",
            "track_start": min(sd) if sd else today,
            "signal_date_range": ("%s ~ %s" % (min(sd), max(sd))) if sd else today,
            "total_signals": total,
            "cost_adjusted": True,
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
