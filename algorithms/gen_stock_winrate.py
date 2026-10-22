# -*- coding: utf-8 -*-
"""
gen_stock_winrate.py · 个股级胜率 / 收益榜生成器（v8 选股引擎 rank-fusion 数据源）

为什么需要它
------------
原 final_recommend 的 final_score = 因子榜 total_score（信号强弱分），
排序本质不反映"这只票历史上赚不赚钱 / 胜率高不高"。本脚本用真实历史信号流
（raw_data/history 信号日快照 + raw_data/kline_cache 真实日K）逐只复算：
  · 信号日次一交易日【开盘】买入，持有 N 日【收盘】卖出，扣双边 0.30% 成本
  · 与官方 final_recommend_backtest.json 完全同一口径
产出 data/STOCK_WINRATE.js（window.STOCK_WINRATE），供 final_recommend 做 rank-fusion：
把"最高分"做实为"最高期望"（胜率高 + 收益高）。

用法（仓库内，随 run_algorithms.py 在 final_recommend 之前自动跑；亦可独立定时）
  python3 algorithms/gen_stock_winrate.py        # 默认路径自动解析到仓库根 raw_data/history + kline_cache → data/
本地验证
  python3 algorithms/gen_stock_winrate.py --hist src_audit/hist --kline src_audit/kline --out .

设计原则
  · 收缩（shrinkage k=10）防小样本假高分：样本极小自动向 50%/0% 回归；
  · 港股无 A 股日K（kline_cache 不含港股），自然不入榜——不影响原候选池；
  · 全程 try/except + 字段缺失兜底，绝不因单票异常打死整轮。
"""
import json, os, glob, re, argparse, statistics, datetime as dt

COST_PCT = 0.30          # 双边合计成本（与官方 final_recommend_backtest 一致）
HORIZONS = [1, 3, 5, 10, 20]
SHRINK_K = 10            # 与 v8 shrinkage_k=10 同源
SIGNAL_SRC_EXCLUDE = ("archive",)


def attr_date(update_time):
    """信号日归属：小时<9 归前一自然日（与 v8 _NIGHT_CUT 同源）。"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):", update_time or "")
    if not m:
        return None
    d = dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if int(m.group(4)) < 9:
        d -= dt.timedelta(days=1)
    return d.isoformat()


def norm_code(raw):
    return re.sub(r"\D", "", str(raw or ""))


def load_occurrences(hist_dir):
    """提取 (code, name, signal_date, kind, rank, score) 信号记录。"""
    occ = []
    for fp in sorted(glob.glob(os.path.join(hist_dir, "*.json"))):
        base = os.path.basename(fp)
        if any(x in base for x in SIGNAL_SRC_EXCLUDE):
            continue
        try:
            d = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        sd = attr_date(d.get("update_time"))
        if not sd:
            continue
        kind = "final" if base.startswith("final_recommend") else "top10"
        entries = d.get("stocks") if kind == "final" else (d.get("top10") or d.get("top"))
        for e in entries or []:
            code = norm_code(e.get("code"))
            if len(code) != 6:
                continue
            occ.append({
                "code": code, "name": e.get("name"), "signal_date": sd,
                "kind": kind, "rank": e.get("rank"),
                "score": e.get("final_score") or e.get("total_score") or e.get("score"),
            })
    return occ


class KlineDB:
    def __init__(self, kline_dir):
        self.dir = kline_dir
        self._c = {}

    def get(self, code):
        if code not in self._c:
            fp = os.path.join(self.dir, code + ".json")
            if not os.path.exists(fp):
                self._c[code] = None
            else:
                try:
                    rows = json.load(open(fp, encoding="utf-8"))
                    self._c[code] = sorted(rows, key=lambda r: r["date"]) if isinstance(rows, list) else None
                except Exception:
                    self._c[code] = None
        return self._c[code]

    def entry_index(self, code, signal_date):
        ks = self.get(code)
        if not ks:
            return None
        for i, r in enumerate(ks):
            if r["date"] > signal_date:
                return i
        return None

    def trade_return(self, code, signal_date, h):
        ks = self.get(code)
        if not ks:
            return None
        i = self.entry_index(code, signal_date)
        if i is None or i + h >= len(ks):
            return None
        buy, sell = ks[i]["open"], ks[i + h]["close"]
        if not buy or not sell:
            return None
        return (sell / buy - 1.0) * 100.0 - COST_PCT


def shrink(value, n, k=SHRINK_K):
    return value * (n / (n + k)) if n > 0 else 0.0


def shrink_win(wr, n, k=SHRINK_K):
    return 50.0 + (wr - 50.0) * (n / (n + k)) if n > 0 else 50.0


def main():
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--hist", default=os.path.join(_REPO_ROOT, "raw_data", "history"))
    ap.add_argument("--kline", default=os.path.join(_REPO_ROOT, "raw_data", "kline_cache"))
    ap.add_argument("--out", default=os.path.join(_REPO_ROOT, "data"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    occ = load_occurrences(a.hist)
    db = KlineDB(a.kline)
    print(f"[gen_stock_winrate] 信号记录 {len(occ)} 条 | hist={a.hist} kline={a.kline}")

    by_code = {}
    for o in occ:
        by_code.setdefault(o["code"], {"name": o["name"], "occs": [], "kinds": set()})
        by_code[o["code"]]["occs"].append(o)
        by_code[o["code"]]["kinds"].add(o["kind"])

    stocks = []
    for code, info in sorted(by_code.items()):
        rec = {"code": code, "name": info["name"], "n_signals": len(info["occs"]),
               "kinds": sorted(info["kinds"]),
               "first_seen": min(o["signal_date"] for o in info["occs"]),
               "last_seen": max(o["signal_date"] for o in info["occs"]),
               "is_final": "final" in info["kinds"]}
        h_stats = {}
        for h in HORIZONS:
            rets = [r for r in (db.trade_return(code, o["signal_date"], h) for o in info["occs"]) if r is not None]
            n = len(rets)
            if n == 0:
                continue
            wr = sum(1 for x in rets if x > 0) / n * 100.0
            h_stats[str(h)] = {
                "n": n, "win": round(wr, 1),
                "avg": round(statistics.mean(rets), 2),
                "med": round(statistics.median(rets), 2),
                "best": round(max(rets), 2), "worst": round(min(rets), 2),
                "win_shrunk": round(shrink_win(wr, n), 1),
                "avg_shrunk": round(shrink(statistics.mean(rets), n), 2),
            }
        if not h_stats:
            continue
        rec["horizons"] = h_stats
        s5, s10 = h_stats.get("5"), h_stats.get("10")
        score = 0.0
        if s5:
            score += (s5["win_shrunk"] - 50.0) * 0.5 + s5["avg_shrunk"] * 3.0
        if s10:
            score += (s10["win_shrunk"] - 50.0) * 0.5 + s10["avg_shrunk"] * 2.0
        rec["winrate_score"] = round(score, 2)
        stocks.append(rec)

    stocks.sort(key=lambda r: r["winrate_score"], reverse=True)
    for i, r in enumerate(stocks):
        r["rank"] = i + 1

    out = {
        "update_time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "meta": {
            "method": "信号日次一交易日开盘买入，持有N日收盘卖出；扣双边0.30%；真实日K",
            "cost_pct_roundtrip": COST_PCT,
            "shrinkage_k": SHRINK_K,
            "score_formula": "winrate_score = Σ_h [(win_shrunk_h−50)×0.5 + avg_shrunk_h×w2]，h∈{5:3.0, 10:2.0}",
            "n_signals": len(occ),
            "n_stocks": len(stocks),
            "signal_date_range": [min(o["signal_date"] for o in occ), max(o["signal_date"] for o in occ)] if occ else [],
        },
        "stocks": stocks,
    }

    jp = os.path.join(a.out, "STOCK_WINRATE.json")
    js = os.path.join(a.out, "STOCK_WINRATE.js")
    json.dump(out, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(js, "w", encoding="utf-8", newline="\n").write(
        "window.STOCK_WINRATE = " + json.dumps(out, ensure_ascii=False) + ";\n")

    pos = [s for s in stocks if (s["horizons"].get("5") or {}).get("avg", 0) > 0]
    print(f"[gen_stock_winrate] 个股 {len(stocks)} 只 | T+5 正期望 {len(pos)} 只 → {js}")
    print("  TOP15（收缩后胜率+期望综合分）:")
    for r in stocks[:15]:
        h5 = r["horizons"].get("5", {})
        h10 = r["horizons"].get("10", {})
        print(f"    #{r['rank']:>2} {r['code']} {r['name'] or '':<8} 信号{r['n_signals']:>2}次"
              f"{' [曾入最终推荐]' if r['is_final'] else ''} "
              f"T+5: n={h5.get('n','-')} 胜率{h5.get('win','-')}% 均益{h5.get('avg','-')}% | "
              f"T+10: n={h10.get('n','-')} 胜率{h10.get('win','-')}% 均益{h10.get('avg','-')}%")


if __name__ == "__main__":
    main()
