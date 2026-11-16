#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
期指主力合约 · 实时报价生成器（一劳永逸根因修复 + 贴水量化观测）
=====================================================================
背景（2026-11-09 主人令）：
  「期指主力合约·情绪方向」卡位于【实时数据】页，但历史上只读 window.CFFEX_HOLDINGS
  —— 那是中金所「每日收盘后」一次性发布的日频结算数据（date 停在上一交易日），
  故卡片无论怎么标「盘中每30分刷新」都不可能真·实时，2026-11-06 的修复只是把它
  如实改成「日更 收盘」标签，并未解决「实时数据页里不实时」的矛盾。

根因修复：本生成器接入两条**盘中实时**源，产出 window.FUTURES_REALTIME：
  · 期指主力合约实时价/涨跌幅/持仓量(open_interest)/tick时间  ← 新浪 vip 实时行情
  · 现货指数实时价(沪深300/中证500/中证1000/上证50)          ← 新浪指数(主) / 东财push2(备)
  数据形状与 renderFuturesMain 既有的 CFFEX_HOLDINGS 完全兼容，卡片优先读
  FUTURES_REALTIME，缺失时自动回退 CFFEX_HOLDINGS（日频），绝不空卡。

2026-11-16 贴水观测（主人问「贴水加大适合加仓吗」科学落地，不碰选股排序）：
  · 基差 = 期货主力 − 现货指数；年化贴水率 = 基差率 / 距到期天数 × 365
  · 分位 = 当前年化贴水在历史序列中的百分位（样本≥20 才给值，否则 None）
  · 日变 chg_1d = 今日年化 − 上一交易日年化（正=收敛/负=加深）
  · 三共振 ready = 分位≤35% + 日变>0 + 现货企稳(≥-0.5%) → 仅观测信号，不改个股排序
  · basis_history 内嵌产物，随 workflow 推送自持累积（最多 400 天），供前瞻回测使用
    （algorithms/basis_regime_backtest.py；样本<30 天输出 watch，不编造历史）

运行：
  python v8/gen_futures_realtime.py           # 生成 data/FUTURES_REALTIME.js
  python v8/gen_futures_realtime.py --no-write # 仅打印不写盘（调试）

刷新：接 v8_futures_realtime.yml，盘中每30分在 [self-hosted, cn]（中国IP，新浪可达）重跑。
"""
from __future__ import annotations
import json
import re
import sys
import os
import datetime
import urllib.request
import urllib.error

# ── 品种 → 新浪 vip node（来自 akshare futures_symbol_mark 中金所映射）──
SINA_NODES = {
    "IF": "qz_qh",    # 沪深300指数期货
    "IH": "szgz_qh",  # 上证50指数期货
    "IC": "zzgz_qh",  # 中证500指数期货
    "IM": "im_qh",    # 中证1000股指期货
}
# 品种 → 东财 push2 现货 secid（1=沪市, 0=深市）——备源
SPOT_SECID = {
    "IH": "1.000016",  # 上证50
    "IF": "1.000300",  # 沪深300
    "IC": "1.000905",  # 中证500
    "IM": "1.000852",  # 中证1000
}
# 品种 → 新浪指数变量（主源，hq.sinajs.cn 返回 GBK 文本）
SPOT_SINA = {
    "IH": "s_sh000016",
    "IF": "s_sh000300",
    "IC": "s_sh000905",
    "IM": "s_sh000852",
}
VARIETY_NAME = {"IH": "上证50", "IF": "沪深300", "IC": "中证500", "IM": "中证1000"}

SINA_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQFuturesData"
SINA_SPOT_URL = "https://hq.sinajs.cn/list="
EM_SPOT_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f12,f14,f2,f3&secids="
HIST_URL = "https://ah-quant999.github.io/quant-scanner-v8/data/FUTURES_REALTIME.js"
HIST_MAX_DAYS = 400
PCTILE_MIN_SAMPLES = 20

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://vip.stock.finance.sina.com.cn/"}
EM_UA = {"User-Agent": "Mozilla/5.0"}
SINA_SPOT_UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}


def _bj_now():
    """北京时间（UTC+8），不依赖 tzdata。"""
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)


def _get_json(url, headers, timeout=15):
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read().decode("utf-8", "replace")
    return json.loads(raw)


def fetch_sina_variety(node):
    """取该品种全部可交易合约实时数据（list of dict）。"""
    qs = "page=1&sort=position&asc=0&node=%s&base=futures" % node
    return _get_json(SINA_URL + "?" + qs, UA)


def pick_main(contracts):
    """选主力合约 = 持仓量(position)最大者；同值优先选带月份后缀(非连续/主连)的合约。"""
    best, best_pos = None, -1
    for c in contracts or []:
        try:
            pos = float(c.get("position") or 0)
        except (TypeError, ValueError):
            pos = 0
        sym = c.get("symbol", "")
        prefer = 1 if re.match(r"^[A-Z]{2}\d{4}$", sym) else 0
        if best is None:
            best, best_pos = c, pos
            continue
        if pos > best_pos + 1e-6 or (abs(pos - best_pos) < 1e-6 and prefer > 0
                                     and not re.match(r"^[A-Z]{2}\d{4}$", best.get("symbol", ""))):
            best, best_pos = c, pos
    return best


def fetch_spot_sina():
    """新浪指数实时行情（GBK）→ {variety:{price,pct,name}}。主源。

    hq.sinajs.cn 形如： var hq_str_s_sh000300="沪深300,3939.00,28.00,0.72,...";
    其中 parts[1]=点位, parts[3]=涨跌幅(%)。须带 Referer 否则 403。
    """
    url = SINA_SPOT_URL + ",".join(SPOT_SINA.values())
    req = urllib.request.Request(url, headers=SINA_SPOT_UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read().decode("gbk", "replace")
    code_to_var = {v: k for k, v in SPOT_SINA.items()}
    out = {}
    for line in raw.splitlines():
        m = re.match(r'\s*var hq_str_(s_sh\d+)="([^"]*)"', line)
        if not m:
            continue
        var = code_to_var.get(m.group(1))
        if not var:
            continue
        parts = m.group(2).split(",")
        if len(parts) < 4:
            continue
        try:
            price = float(parts[1])
            pct = float(parts[3])
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        out[var] = {"price": round(price, 2), "pct": round(pct, 2),
                    "name": parts[0] or VARIETY_NAME.get(var, "")}
    return out


def fetch_spot_em():
    """东财 push2 实时现货指数价 → {variety: {price, pct, name}}。备源。"""
    secids = ",".join(SPOT_SECID.values())
    d = _get_json(EM_SPOT_URL + secids, EM_UA)
    data = d.get("data") or {}
    diff = data.get("diff")
    if isinstance(diff, list):
        items = diff
    elif isinstance(diff, dict):
        items = list(diff.values())
    else:
        items = []
    f12_to_var = {v.split(".")[-1]: k for k, v in SPOT_SECID.items()}
    out = {}
    for it in items:
        f12 = it.get("f12")
        var = f12_to_var.get(f12)
        if not var:
            continue
        f2 = it.get("f2")
        try:
            price = float(f2)
        except (TypeError, ValueError):
            continue
        if price in (None, 0) or f2 in ("-", "--", ""):
            continue
        try:
            pct = float(it.get("f3"))
        except (TypeError, ValueError):
            pct = 0.0
        out[var] = {"price": price, "pct": round(pct, 2),
                    "name": it.get("f14") or VARIETY_NAME.get(var, "")}
    return out


def fetch_spot():
    """现货指数：新浪指数主源，失败/不足再走东财 push2 备源。"""
    try:
        out = fetch_spot_sina()
        if len(out) >= 2:
            print("  ✅ 现货(新浪主源): " + ", ".join(
                "%s=%.2f(%+.2f%%)" % (k, v["price"], v.get("pct") or 0)
                for k, v in out.items()))
            return out
        print("  ⚠️ 新浪现货仅 %d 品种，转东财备源" % len(out), file=sys.stderr)
    except Exception as e:
        print("  ⚠️ 新浪现货失败，转东财备源: %s" % e, file=sys.stderr)
    out = fetch_spot_em()
    print("  ✅ 现货(东财备源): " + ", ".join(
        "%s=%.2f" % (k, v["price"]) for k, v in out.items()))
    return out


def _expiry_days(symbol):
    """合约代码 YYMM → 距中金所到期日（当月第三个周五）自然日数；无法解析返回 None。"""
    m = re.match(r"^[A-Z]{2}(\d{4})$", symbol or "")
    if not m:
        return None
    ym = m.group(1)
    year, month = 2000 + int(ym[:2]), int(ym[2:])
    if not (1 <= month <= 12):
        return None
    try:
        first = datetime.date(year, month, 1)
        third_fri = 1 + (4 - first.weekday()) % 7 + 14
        exp = datetime.date(year, month, third_fri)
    except ValueError:
        return None
    days = (exp - _bj_now().date()).days
    return days if days > 0 else None


def load_prev_history():
    """从线上产物累积 basis_history：{date:{ann:{variety:value}}}，最多 400 天。"""
    hist = {}
    try:
        req = urllib.request.Request(HIST_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            txt = r.read().decode("utf-8", "replace")
        payload = txt.split("=", 1)[1].strip().rstrip(";")
        j = json.loads(payload)
        raw_hist = j.get("basis_history") or {}
        if isinstance(raw_hist, dict):
            hist = raw_hist
    except Exception as e:
        print("  ⚠️ 贴水历史读取失败(将新建): %s" % e, file=sys.stderr)
    if len(hist) > HIST_MAX_DAYS:
        for d in sorted(hist)[:-HIST_MAX_DAYS]:
            hist.pop(d, None)
    return hist


def calc_basis_metrics(items, spot, hist):
    """年化贴水率/分位/日变/三共振；并把今日 ann 累积进 hist。"""
    today = _bj_now().strftime("%Y-%m-%d")
    dates = sorted(d for d in hist if re.match(r"^\d{4}-\d{2}-\d{2}$", d))
    prev = {}
    for d in reversed(dates):
        if d < today:
            a = (hist[d] or {}).get("ann") or {}
            if isinstance(a, dict) and a:
                prev = a
                break
    anns = {v: [] for v in SPOT_SINA}
    for d in dates:
        a = (hist[d] or {}).get("ann") or {}
        if not isinstance(a, dict):
            continue
        for v, val in a.items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                anns.setdefault(v, []).append(float(val))
    out = {}
    for it in items:
        v = it["variety"]
        sp = spot.get(v)
        if not sp:
            continue
        px = sp["price"]
        days = _expiry_days(it.get("symbol"))
        if not days:
            continue
        basis = round(float(it["close"]) - px, 2)
        ann = round(basis / px * 100.0 / days * 365.0, 2)
        series = anns.get(v, [])
        n = len(series)
        pctile = round(sum(1 for a in series if a <= ann) / n * 100, 1) if n >= PCTILE_MIN_SAMPLES else None
        chg1 = round(ann - prev[v], 2) if v in prev and isinstance(prev[v], (int, float)) else None
        spot_pct = sp.get("pct")
        ready = bool(pctile is not None and pctile <= 35 and chg1 is not None and chg1 > 0
                     and spot_pct is not None and spot_pct >= -0.5)
        out[v] = {"ann": ann, "basis": basis, "days": days, "pctile": pctile,
                  "chg_1d": chg1, "n": n, "spot_pct": spot_pct, "ready": ready}
        print("  ✅ 贴水 %s ann=%+.2f%% pctile=%s chg1d=%s n=%d" %
              (v, ann, pctile, chg1, n))
    if out:
        hist[today] = {"ann": {v: out[v]["ann"] for v in out}}
    if len(hist) > HIST_MAX_DAYS:
        for d in sorted(hist)[:-HIST_MAX_DAYS]:
            hist.pop(d, None)
    return out, hist


def build_items():
    items = []
    latest_tick = None
    for var, node in SINA_NODES.items():
        try:
            contracts = fetch_sina_variety(node)
            main = pick_main(contracts)
            if not main:
                print("  ⚠️ %s 无合约数据，跳过" % var, file=sys.stderr)
                continue
            trade = float(main.get("trade") or 0)
            pre = float(main.get("presettlement") or main.get("preclose") or 0)
            pos = int(float(main.get("position") or 0))
            chg = (trade - pre) / pre * 100 if pre else 0.0
            tick = main.get("ticktime")
            if tick and (latest_tick is None or tick > latest_tick):
                latest_tick = tick
            items.append({
                "variety": var,
                "symbol": main.get("symbol"),
                "name": main.get("name") or (VARIETY_NAME.get(var, "") + "指数期货"),
                "close": round(trade, 2),
                "pre_settle": round(pre, 2),
                "open_interest": pos,
                "chg": round(chg, 2),
                "ticktime": tick,
            })
            print("  ✅ %s %s 现价 %.2f 持仓 %d 涨 %.2f%% tick=%s" %
                  (var, main.get("symbol"), trade, pos, chg, tick))
        except Exception as e:
            print("  ⚠️ %s 实时抓取失败: %s" % (var, e), file=sys.stderr)
    return items, latest_tick


def main():
    no_write = "--no-write" in sys.argv
    items, latest_tick = build_items()
    if not items:
        print("  ❌ 全部品种实时抓取失败，不写盘（保留上一版，避免空卡）", file=sys.stderr)
        sys.exit(2)

    spot = {}
    try:
        spot = fetch_spot()
    except Exception as e:
        print("  ⚠️ 现货全部失败（基差行将隐藏）: %s" % e, file=sys.stderr)

    hist = load_prev_history()
    basis_metrics, hist = calc_basis_metrics(items, spot, hist)

    update_time = _bj_now().strftime("%Y-%m-%d %H:%M:%S")
    if latest_tick:
        try:
            update_time = "%s %s" % (_bj_now().strftime("%Y-%m-%d"), latest_tick)
        except Exception:
            pass

    out = {
        "update_time": update_time,
        "realtime": True,
        "source": "新浪vip实时期指 + 新浪指数现货(备东财push2) + 贴水量化观测",
        "spot": spot,
        "items": items,
        "basis_metrics": basis_metrics,
        "basis_history": hist,
        "note": "期指主力合约真实时报价（盘中刷新）；basis_metrics 为贴水观测信号，仅观测不改选股排序；缺失时前端回退 CFFEX_HOLDINGS 日频数据",
    }

    if no_write:
        print("  [no-write] spot=%d items=%d basis_metrics=%d hist=%d" %
              (len(spot), len(items), len(basis_metrics), len(hist)))
        print(json.dumps({"spot": spot, "basis_metrics": basis_metrics}, ensure_ascii=False))
        return
    here = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.normpath(os.path.join(here, "..", "data", "FUTURES_REALTIME.js"))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("window.FUTURES_REALTIME = ")
        json.dump(out, f, ensure_ascii=False)
        f.write(";\n")
    print("  💾 已写入 %s （%d 品种, update_time=%s, 贴水观测 %d 品种, 历史 %d 天）" %
          (out_path, len(items), update_time, len(basis_metrics), len(hist)))


if __name__ == "__main__":
    main()
