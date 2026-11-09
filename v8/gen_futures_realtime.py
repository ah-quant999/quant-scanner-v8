#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
期指主力合约 · 实时报价生成器（一劳永逸根因修复）
=====================================================================
背景（2026-11-09 主人令）：
  「期指主力合约·情绪方向」卡位于【实时数据】页，但历史上只读 window.CFFEX_HOLDINGS
  —— 那是中金所「每日收盘后」一次性发布的日频结算数据（date 停在上一交易日），
  故卡片无论怎么标「盘中每30分刷新」都不可能真·实时，2026-11-06 的修复只是把它
  如实改成「日更 收盘」标签，并未解决「实时数据页里不实时」的矛盾。

根因修复：本生成器接入两条**盘中实时**源，产出 window.FUTURES_REALTIME：
  · 期指主力合约实时价/涨跌幅/持仓量(open_interest)/tick时间  ← 新浪 vip 实时行情
    （https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQFuturesData）
  · 现货指数实时价(沪深300/中证500/中证1000/上证50)            ← 东财 push2 实时
    （https://push2.eastmoney.com/api/qt/ulist.np.get?secids=...）
  数据形状与 renderFuturesMain 既有的 CFFEX_HOLDINGS 完全兼容
  （items:[{variety,symbol,close,pre_settle,open_interest}], spot:{variety:{price}}），
  卡片优先读 FUTURES_REALTIME，缺失时自动回退 CFFEX_HOLDINGS（日频），绝不空卡。

运行：
  python v8/gen_futures_realtime.py          # 生成 data/FUTURES_REALTIME.js
  python v8/gen_futures_realtime.py --no-write  # 仅打印不写盘（调试）

刷新：接 v8_futures_realtime.yml，盘中每30分在 [self-hosted, cn]（中国IP，新浪/东财可达）重跑。
"""
from __future__ import annotations
import json
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
# 品种 → 东财 push2 现货 secid（1=沪市, 0=深市）
SPOT_SECID = {
    "IH": "1.000016",  # 上证50
    "IF": "1.000300",  # 沪深300
    "IC": "1.000905",  # 中证500
    "IM": "1.000852",  # 中证1000
}
VARIETY_NAME = {"IH": "上证50", "IF": "沪深300", "IC": "中证500", "IM": "中证1000"}

SINA_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQFuturesData"
EM_SPOT_URL = "https://push2.eastmoney.com/api/qt/ulist.np/get?fltt=2&invt=2&fields=f12,f14,f2&secids="

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://vip.stock.finance.sina.com.cn/"}
EM_UA = {"User-Agent": "Mozilla/5.0"}


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
        # 比较：持仓高者胜；持仓相等时，优先 symbol 形如 XX2612（非 IF0/主连）
        prefer = 1 if (__import__("re").match(r"^[A-Z]{2}\d{4}$", sym)) else 0
        if best is None:
            best, best_pos = c, pos
            continue
        if pos > best_pos + 1e-6 or (abs(pos - best_pos) < 1e-6 and prefer > 0
                                     and not __import__("re").match(r"^[A-Z]{2}\d{4}$", best.get("symbol", ""))):
            best, best_pos = c, pos
    return best


def fetch_spot():
    """东财 push2 实时现货指数价 → {variety: {price, name}}。

    注：ulist 多 secid 时 data.diff 是 list（每项含 f12=代码, f14=名称, f2=现价），
    与 clist 的 dict 形态不同，这里统一按 list 处理并按 f12 反查明细。
    """
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
    # f12(如 "000300") → variety 反向映射
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
        out[var] = {"price": price, "name": it.get("f14") or VARIETY_NAME.get(var, "")}
    return out


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
        print("  ✅ 现货: " + ", ".join("%s=%.2f" % (k, v["price"]) for k, v in spot.items()))
    except Exception as e:
        print("  ⚠️ 现货抓取失败（基差行将隐藏）: %s" % e, file=sys.stderr)

    # update_time 优先用最新 tick 时间（北京时间），否则用当前北京时间
    update_time = _bj_now().strftime("%Y-%m-%d %H:%M:%S")
    if latest_tick:
        # ticktime 形如 "14:09:23"，拼上今天日期
        try:
            today = _bj_now().strftime("%Y-%m-%d")
            update_time = "%s %s" % (today, latest_tick)
        except Exception:
            pass

    out = {
        "update_time": update_time,
        "realtime": True,
        "source": "新浪vip实时期指 + 东财push2实时现货",
        "spot": spot,
        "items": items,
        "note": "期指主力合约真实时报价（盘中刷新）；缺失时前端自动回退 CFFEX_HOLDINGS 日频数据",
    }

    here = os.path.dirname(os.path.abspath(__file__))
    out_path = os.path.join(here, "..", "data", "FUTURES_REALTIME.js")
    out_path = os.path.normpath(out_path)
    if no_write:
        print(json.dumps(out, ensure_ascii=False, indent=2)[:1500])
        return
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("window.FUTURES_REALTIME = ")
        json.dump(out, f, ensure_ascii=False)
        f.write(";\n")
    print("  💾 已写入 %s （%d 品种, update_time=%s）" % (out_path, len(items), update_time))


if __name__ == "__main__":
    main()
