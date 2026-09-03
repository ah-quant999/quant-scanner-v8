#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
strong_breakout.py — 「强势突破」选股（高手算法反推版）

🎯 背景（2026-09-03 主人令「反推高手算法做成 v8 选股策略」）：
  高手（梧谷枫灯）每日 ima 报告「盘后选股·强势突破筛选」= 两层结构：
    池层   = 涨幅≥3% + 量比≥1.2(4日均量)  → 即 auto_run_dn_algorithm.py 的 h_auto_buy 池
             （2026-09-03 实证：高手 31 只 31/31 全部 ⊆ 本池 346 只）
    过滤层 = 「强势突破」→ 本脚本反推的量化规则

📐 反推规则（9.3 单日样本 31/31 全召回，规则通过 86/346；多日样本持续校准中）：
  1) 当日涨幅 ≥ 5%
  2) 量比（当日量 / 前5日均量）≥ 1.35
  3) 收盘位置 (close-low)/(high-low) ≥ 0.55（收在日内高位）
  4) 5日累计涨幅 ∈ [0.5%, 15%]（已启动、未过热）
  「突破」不是创新高口径：9.3 样本破20日高仅 13/31、破60日高仅 2/31。

📊 排序：score = 量比 + 涨幅 + 收位×10；top 30 标记 core（9.3 样本高手股中位排名 39/86，
   剩余差距为高手主观形态/行业分散部分，如实全量呈现通过股，不做激进裁剪）。

📤 输出：
  raw_data/strong_breakout_<date>.json —— 当日结果（留档/跟踪用）
  raw_data/strong_breakout.json        —— 最新镜像（运维/审计读这份的 update_time）
  data/STRONG_BREAKOUT.js              —— window.STRONG_BREAKOUT（前端注入，?v= 由 update_v8 维护）

用法：
  python algorithms/strong_breakout.py                    # 默认：今天，池缺失自动回退最近有池交易日
  python algorithms/strong_breakout.py --date 2026-09-03  # 指定日期
  python algorithms/strong_breakout.py --no-emit-js       # 只写 raw_data 不写 data/*.js
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "raw_data")
DATA_DIR = os.path.join(ROOT, "data")
OUT_JS = os.path.join(DATA_DIR, "STRONG_BREAKOUT.js")

# 反推规则阈值（2026-09-03 定稿 v1；后续多日样本校准只改这里）
PCT_MIN = 5.0        # 当日涨幅 ≥ 5%
VR_MIN = 1.35        # 量比(5日均量) ≥ 1.35
CLOSE_POS_MIN = 0.55 # 收盘位置 ≥ 0.55
RET5_MIN, RET5_MAX = 0.5, 15.0  # 5日累计涨幅区间（%）
KLINE_BARS = 80      # 拉 80 根日K（前复权）
CORE_TOP_N = 30      # 前 N 名标记 core
MAX_WORKERS = 8      # K线并发拉取线程数

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _norm_code(code):
    return re.sub(r"\D", "", str(code or ""))


def _sym(code):
    if code.startswith(("6", "9")):
        return "sh" + code
    if code.startswith(("4", "8")):
        return "bj" + code
    return "sz" + code


def _fetch_kline_gtimg(code, n):
    """gtimg 日K前复权：[date, open, close, high, low, volume(手)]（云端生产主源）"""
    s = _sym(code)
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={s},day,,,{n},qfq"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode("utf-8"))
    node = d["data"][s]
    k = node.get("qfqday") or node.get("day")
    return [[row[0], float(row[1]), float(row[2]), float(row[3]),
             float(row[4]), float(row[5])] for row in k]


def _fetch_kline_sina(code, n):
    """新浪日K兜底（不复权；量比/收位为同源比值与比率，不受复权影响；
    仅当近5日内有除权除息时 pct/ret5 有微小偏差，主源不可用时的容灾）。"""
    s = _sym(code)
    if s.startswith("bj"):
        raise RuntimeError("sina: 不支持北交所")
    url = (f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20d=/"
           f"CN_MarketDataService.getKLineData?symbol={s}&scale=240&ma=no&datalen={n}")
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=15) as r:
        txt = r.read().decode("utf-8")
    m = re.search(r"\((\[.*\])\)", txt, re.S)
    if not m:
        raise RuntimeError("sina: 响应解析失败")
    arr = json.loads(m.group(1))
    return [[row["day"], float(row["open"]), float(row["close"]), float(row["high"]),
             float(row["low"]), float(row["volume"])] for row in arr]


def _fetch_kline(code, n=KLINE_BARS, retries=2):
    """双源容灾：gtimg 主源（云端生产）→ 新浪兜底（本地/风控期容灾）。"""
    last_err = None
    for _ in range(retries + 1):
        try:
            return _fetch_kline_gtimg(code, n)
        except Exception as e:  # noqa: BLE001
            last_err = e
    try:
        return _fetch_kline_sina(code, n)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(f"kline {code}: gtimg={last_err} sina={e}")


def _feats(k):
    """从日K序列算 9.3 反推规则所需特征（最后一根为基准日）。"""
    o, c, h, l, v = k[-1][1], k[-1][2], k[-1][3], k[-1][4], k[-1][5]
    pc = k[-2][2]
    pct = (c / pc - 1) * 100 if pc else 0.0
    v5 = sum(r[5] for r in k[-6:-1]) / 5 if len(k) >= 6 else 0
    vr5 = (v / v5) if v5 else 0.0
    rng = h - l
    pos = (c - l) / rng if rng else 1.0
    upper = (h - c) / c * 100 if c else 0.0
    ma20 = sum(r[2] for r in k[-20:]) / 20 if len(k) >= 20 else c
    ret5 = (c / k[-6][2] - 1) * 100 if len(k) >= 6 and k[-6][2] else 0.0
    return {"close": c, "pct": pct, "vol_ratio": round(vr5, 3),
            "close_pos": round(pos, 3), "upper_shadow": round(upper, 2),
            "ret5": round(ret5, 2), "above_ma20": c > ma20,
            "trade_date": k[-1][0]}


def _load_pool(target_date, max_back=7):
    """读 target_date 的 h_auto_buy 池；缺失自动回退最近有池的日期。
    返回 (pool_dict, real_date)；找不到返回 (None, None)。"""
    base = datetime.strptime(target_date, "%Y-%m-%d")
    for i in range(max_back + 1):
        d = (base - timedelta(days=i)).strftime("%Y-%m-%d")
        p = os.path.join(RAW_DIR, f"h_auto_buy_{d.replace('-', '')}.json")
        if os.path.exists(p):
            try:
                with open(p, encoding="utf-8") as f:
                    j = json.load(f)
                cands = j.get("candidates") or []
                if cands:
                    if i:
                        print(f"ℹ️ {target_date} 无池，回退用 {d} 的池（{len(cands)} 只）")
                    return j, d
            except Exception as e:  # noqa: BLE001
                print(f"⚠️ 读 {p} 失败: {e}")
    return None, None


def run(target_date=None, emit_js=True):
    if target_date is None:
        target_date = datetime.now().strftime("%Y-%m-%d")
    pool, real_date = _load_pool(target_date)
    if pool is None:
        print(f"❌ strong_breakout: 找不到任何 h_auto_buy 池（{target_date} 起 7 天内）")
        return None
    cands = pool["candidates"]

    # 并发拉K线
    klines, failures = {}, []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futs = {ex.submit(_fetch_kline, c["code"]): c["code"] for c in cands}
        for fu in as_completed(futs):
            code = futs[fu]
            try:
                klines[code] = fu.result()
            except Exception as e:  # noqa: BLE001
                failures.append((code, str(e)[:60]))

    picked, rule_fail = [], 0
    for c in cands:
        code = c["code"]
        k = klines.get(code)
        if not k or len(k) < 21:
            rule_fail += 1
            continue
        f = _feats(k)
        ok = (f["pct"] >= PCT_MIN
              and f["vol_ratio"] >= VR_MIN
              and f["close_pos"] >= CLOSE_POS_MIN
              and RET5_MIN <= f["ret5"] <= RET5_MAX)
        if not ok:
            rule_fail += 1
            continue
        picked.append({
            "code": code,
            "symbol": c.get("symbol") or _sym(code),
            "name": c.get("name", ""),
            "industry": c.get("industry", ""),
            "board": c.get("board", ""),
            "close": f["close"],
            "pct": round(f["pct"], 2),
            "vol_ratio": f["vol_ratio"],
            "close_pos": f["close_pos"],
            "ret5": f["ret5"],
            "upper_shadow": f["upper_shadow"],
            "above_ma20": f["above_ma20"],
            "trade_date": f["trade_date"],
            # 排序分：量比 + 涨幅 + 收位×10（9.3 样本高手股中位排名最优）
            "score": round(f["vol_ratio"] + f["pct"] + f["close_pos"] * 10, 3),
        })
    picked.sort(key=lambda x: -x["score"])
    for i, s in enumerate(picked):
        s["rank"] = i + 1
        s["core"] = i < CORE_TOP_N

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date": real_date,
        "method": (f"强势突破(高手反推v1): 涨幅≥{PCT_MIN}% + 量比≥{VR_MIN}(5日均量) "
                   f"+ 收位≥{CLOSE_POS_MIN} + 5日累计∈[{RET5_MIN},{RET5_MAX}]%"),
        "version": "v1 (2026-09-03 样本 31/31 全召回)",
        "pool_count": len(cands),
        "kline_fail": len(failures),
        "picked_count": len(picked),
        "core_top_n": CORE_TOP_N,
        "stocks": picked,
    }

    # 写 raw_data（留档 + 最新镜像）
    os.makedirs(RAW_DIR, exist_ok=True)
    dated_path = os.path.join(RAW_DIR, f"strong_breakout_{real_date.replace('-', '')}.json")
    with open(dated_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    with open(os.path.join(RAW_DIR, "strong_breakout.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    if emit_js:
        payload = ("/* 强势突破选股（高手算法反推版） strong_breakout.py 产出 */\n"
                   "window.STRONG_BREAKOUT = " + json.dumps(out, ensure_ascii=False) + ";\n")
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(OUT_JS, "w", encoding="utf-8") as f:
            f.write(payload)

    print(f"✅ strong_breakout[{real_date}]: 池 {len(cands)} → 通过 {len(picked)} "
          f"(core {min(len(picked), CORE_TOP_N)}) | K线失败 {len(failures)} | 特征不达标/数据不足 {rule_fail}")
    return out


def main():
    ap = argparse.ArgumentParser(description="强势突破选股（高手算法反推版）")
    ap.add_argument("--date", default=None, help="基准交易日 YYYY-MM-DD（默认今天）")
    ap.add_argument("--no-emit-js", action="store_true", help="不写 data/STRONG_BREAKOUT.js")
    a = ap.parse_args()
    run(target_date=a.date, emit_js=not a.no_emit_js)


if __name__ == "__main__":
    main()
