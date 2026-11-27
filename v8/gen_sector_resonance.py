#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板块共振度 · absorb ratio（第一主成分解释占比）生成器
=====================================================
来源：2026-11-27 主人提供的 absorb ratio 思路 ——
  「算十几个板块儿的协方差矩阵，看能被某个原因解释多少；解释力度相对它过去多少天的平均值
    越强，风险越大。因为下跌过程中一直会有这种共振出现，而上涨过程中比较少出现。」

指标定义（严格按上述口径，不偷换）：
  · 取 N 个板块近 W 个交易日的日收益率矩阵 R（N x W）
  · 协方差矩阵 C = cov(R)
  · 特征值分解，第一特征值 / 特征值总和 = PC1 占比 = 「能被单一共同因子解释的方差比例」
  · 该占比越高 ⇒ 板块同涨同跌越强 ⇒ 系统性联动（下跌时=系统性杀跌）
  · 再用 PC1 占比自身近 60 日的均值/标准差算 z：(pc1 - ma60) / sd60

⚠️ 方向必须显式给出，不能只看共振高低：
    共振高 + 大盘跌 = 系统性杀跌 → 减仓
    共振高 + 大盘涨 = 政策/情绪驱动的一致做多 → 可跟但不加杠杆
    共振低          = 板块轮动（A股常态）→ 只做最强主线

双路取数（一劳永逸，抓不到就自己攒，绝不编数）：
  A. method="kline"（首选）：akshare 抓东财行业板块历史日线 → 一次就有完整窗口。
     仅在具备 akshare 且网络可达东财时成功（云端 CN runner 通常可用）。
  B. method="accumulate"（兜底）：每天把 data/SECTOR_RS.js 的 90 个板块当日 pct_day
     追加进 data/SECTOR_RESONANCE.js 的 history；累积够 MIN_WINDOW 天后自动开始出 PC1。
     不足 MIN_WINDOW 天时 pc1_pct=null，前端如实显示「累积中 N/M 天」，绝不冒充。

产出：data/SECTOR_RESONANCE.js → window.SECTOR_RESONANCE
刷新：.github/workflows/v8_sector_resonance.yml，交易日 18:40 CST。
"""
from __future__ import annotations

import io
import json
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "SECTOR_RESONANCE.js"
SRC = ROOT / "data" / "SECTOR_RS.js"          # 每日板块快照（90 个板块 pct_day）
CST = timezone(timedelta(hours=8))

TOP_N = 20            # 参与协方差的板块数（十几个到二十个，按成交额/市值取代表）
WINDOW = 60           # 滚动窗口交易日数（用户口径「过去多少天」取 60）
MIN_WINDOW = 20       # 累积路径下开始出值的最小天数（低于此只记录不出结论）
HIST_KEEP = 120       # history 最多保留天数（防文件膨胀）
KLINE_DAYS = 180      # akshare 路径回看的自然日


def log(msg):
    print("[resonance] " + str(msg), flush=True)


def now_str():
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def read_window_var(path: Path, var_hint: str):
    """读取 window.X = {...} 形式的 JS 数据文件。"""
    if not path.exists():
        return None
    try:
        s = io.open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return None
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(s[i:j + 1])
    except Exception:
        return None


# ─────────────────────────── 路径 A：akshare 抓板块日线 ───────────────────────────
def fetch_kline(top_n=TOP_N, days=KLINE_DAYS):
    """返回 (dates, matrix, names) 或 (None, None, None)。matrix 为 list[list[float]]，按日对齐。"""
    try:
        import akshare as ak  # noqa
        import pandas as pd   # noqa
    except Exception as e:
        log("akshare/pandas 不可用，跳过 kline 路径：%s" % e)
        return None, None, None

    try:
        names_df = ak.stock_board_industry_name_em()
    except Exception as e:
        log("板块列表接口失败，跳过 kline 路径：%s" % e)
        return None, None, None

    # 列名容错：不同 akshare 版本列名有差异
    def pick_col(df, cands):
        for c in df.columns:
            for k in cands:
                if k in str(c):
                    return c
        return None

    name_col = pick_col(names_df, ["板块名称", "名称"])
    amt_col = pick_col(names_df, ["成交额", "总市值", "换手率"])
    if name_col is None:
        log("板块列表缺名称列：%s" % list(names_df.columns))
        return None, None, None

    df = names_df.copy()
    if amt_col is not None:
        df["_rank"] = pd.to_numeric(df[amt_col], errors="coerce").fillna(0)
        df = df.sort_values("_rank", ascending=False)
    sectors = [str(x) for x in df[name_col].head(top_n).tolist()]
    log("kline 路径取板块 %d 个：%s" % (len(sectors), "、".join(sectors[:8]) + "…"))

    end = datetime.now(CST).strftime("%Y%m%d")
    beg = (datetime.now(CST) - timedelta(days=days)).strftime("%Y%m%d")
    closes = {}
    for name in sectors:
        try:
            h = ak.stock_board_industry_hist_em(symbol=name, start_date=beg, end_date=end,
                                                period="日k", adjust="")
            ccol = pick_col(h, ["收盘"])
            dcol = pick_col(h, ["日期"])
            if ccol is None or dcol is None:
                continue
            ser = {}
            for _, row in h.iterrows():
                try:
                    ser[str(row[dcol])[:10]] = float(row[ccol])
                except Exception:
                    continue
            if len(ser) >= WINDOW + 5:
                closes[name] = ser
        except Exception as e:
            log("  板块 %s 取数失败：%s" % (name, str(e)[:80]))
    if len(closes) < 8:
        log("可用板块不足 8 个（实际 %d），放弃 kline 路径" % len(closes))
        return None, None, None

    # 对齐日期
    all_dates = sorted(set().union(*[set(v.keys()) for v in closes.values()]))
    names = sorted(closes.keys())
    dates, matrix = [], []
    for d in all_dates:
        row = []
        ok = True
        for n in names:
            v = closes[n].get(d)
            if v is None:
                ok = False
                break
            row.append(v)
        if ok:
            dates.append(d)
            matrix.append(row)
    if len(dates) < WINDOW + 5:
        log("对齐后仅 %d 个交易日，不足 %d，放弃 kline 路径" % (len(dates), WINDOW + 5))
        return None, None, None
    log("kline 路径对齐成功：%d 个板块 × %d 个交易日" % (len(names), len(dates)))
    return dates, matrix, names


# ─────────────────────────── 核心计算 ───────────────────────────
def pc1_series(dates, closes, window=WINDOW):
    """对每个 t（>=window），用 [t-window, t) 的日收益率算 PC1 占比。返回 [(date, pc1)]。"""
    import numpy as np
    arr = np.asarray(closes, dtype=float)          # T x N 收盘价
    if arr.shape[0] < window + 2 or arr.shape[1] < 4:
        return []
    rets = np.diff(arr, axis=0) / arr[:-1]         # (T-1) x N 日收益率
    out = []
    for t in range(window, rets.shape[0] + 1):
        seg = rets[t - window:t]
        # 去掉零方差列（停牌/无波动）
        std = seg.std(axis=0)
        keep = std > 1e-12
        if keep.sum() < 4:
            continue
        seg2 = seg[:, keep]
        try:
            cov = np.cov(seg2, rowvar=False)
            vals = np.linalg.eigvalsh(cov)
            vals = np.clip(vals, 0, None)
            tot = float(vals.sum())
            if tot <= 0:
                continue
            out.append((dates[t], float(vals[-1] / tot)))
        except Exception:
            continue
    return out


def build_from_kline():
    dates, matrix, names = fetch_kline()
    if not dates:
        return None
    ser = pc1_series(dates, matrix)
    if not ser:
        return None
    return {
        "method": "kline",
        "sectors": names,
        "n_sectors": len(names),
        "data_date": ser[-1][0],
        "pc1": ser[-1][1],
        "series": ser,
    }


def build_from_accumulate(prev):
    """从 SECTOR_RS 当日快照累积；prev 为上一次的 SECTOR_RESONANCE 内容。"""
    sr = read_window_var(SRC, "SECTOR_RS")
    if not sr or not sr.get("sectors"):
        log("SECTOR_RS 不可用，累积路径无法推进")
        return None
    d = str(sr.get("data_date") or "")[:10]
    if not d:
        log("SECTOR_RS 缺 data_date，累积路径无法推进")
        return None
    pcts = {}
    for s in sr["sectors"]:
        nm, v = s.get("name"), s.get("pct_day")
        if nm is None or v is None:
            continue
        try:
            pcts[str(nm)] = round(float(v), 4)
        except Exception:
            continue
    if len(pcts) < 30:
        log("可用板块仅 %d 个，累积路径放弃" % len(pcts))
        return None

    hist = {}
    if isinstance(prev, dict) and isinstance(prev.get("history"), list):
        for rec in prev["history"]:
            if isinstance(rec, dict) and rec.get("date") and isinstance(rec.get("pcts"), dict):
                hist[str(rec["date"])] = rec["pcts"]
    hist[d] = pcts
    ordered = sorted(hist.keys())[-HIST_KEEP:]

    # 只用多日都出现的板块（保证矩阵对齐）
    from collections import Counter
    cnt = Counter()
    for k in ordered:
        for nm in hist[k].keys():
            cnt[nm] += 1
    common = [nm for nm, c in cnt.items() if c == len(ordered)]
    common = sorted(common)[:TOP_N]

    res = {
        "method": "accumulate",
        "sectors": common,
        "n_sectors": len(common),
        "history": [{"date": k, "pcts": hist[k]} for k in ordered],
        "data_date": d,
        "pc1": None,
        "series": [],
    }
    if len(ordered) >= MIN_WINDOW and len(common) >= 8:
        closes, dates = [], []
        for k in ordered:
            closes.append([hist[k][nm] for nm in common])
            dates.append(k)
        # 累积路径下 pcts 是「当日涨跌幅」，不是收盘价 → 直接当收益率矩阵用
        import numpy as np
        arr = np.asarray(closes, dtype=float)
        ser = []
        for t in range(MIN_WINDOW, arr.shape[0] + 1):
            seg = arr[t - MIN_WINDOW:t]
            std = seg.std(axis=0)
            keep = std > 1e-12
            if keep.sum() < 4:
                continue
            try:
                vals = np.linalg.eigvalsh(np.cov(seg[:, keep], rowvar=False))
                vals = np.clip(vals, 0, None)
                tot = float(vals.sum())
                if tot > 0:
                    ser.append((dates[t], float(vals[-1] / tot)))
            except Exception:
                continue
        res["series"] = ser
        if ser:
            res["pc1"] = ser[-1][1]
            res["window_used"] = MIN_WINDOW
    return res


def finalize(built, prev):
    import numpy as np
    series = built.get("series") or []
    pc1 = built.get("pc1")
    ma = sd = z = None
    tail = []
    if series:
        vals = [x[1] for x in series]
        recent = vals[-60:]
        ma = float(np.mean(recent))
        sd = float(np.std(recent))
        if pc1 is not None and sd > 1e-9:
            z = float((pc1 - ma) / sd)
        tail = [{"date": x[0], "pc1": round(x[1], 4)} for x in series[-30:]]

    level, tone, verdict = "unknown", "dim", "数据累积中，暂不出共振结论"
    if pc1 is not None and z is not None:
        if z >= 1.5:
            level, tone = "high", "up"
            verdict = "共振偏高：板块同涨同跌明显（下跌中→系统性杀跌需减仓；上涨中→政策/情绪驱动的一致性行情，可跟但别加杠杆）"
        elif z <= -1.0:
            level, tone = "low", "gold"
            verdict = "共振偏低：板块各走各的（轮动行情，只做最强主线，别指望普涨）"
        else:
            level, tone = "normal", "sub"
            verdict = "共振正常：结构性行情，按各自信号做"

    out = {
        "version": 1,
        "update_time": now_str(),
        "data_date": built.get("data_date"),
        "method": built.get("method"),
        "n_sectors": built.get("n_sectors"),
        "window": built.get("window_used") or WINDOW,
        "sectors": built.get("sectors") or [],
        "pc1_pct": round(pc1 * 100, 2) if pc1 is not None else None,
        "pc1_ma": round(ma * 100, 2) if ma is not None else None,
        "pc1_sd": round(sd * 100, 2) if sd is not None else None,
        "z": round(z, 2) if z is not None else None,
        "level": level,
        "tone": tone,
        "verdict": verdict,
        "accumulated_days": len(built.get("history") or []) or (len(series) + WINDOW if series else 0),
        "min_window": MIN_WINDOW,
        "history_tail": tail,
        "note": ("板块日收益协方差矩阵第一主成分解释占比（absorb ratio）；"
                 "method=kline 为板块指数日线直算，method=accumulate 为逐日快照自累积；"
                 "z=(PC1-近60日均值)/标准差，z 越高=共振越强"),
        "source": "gen_sector_resonance.py",
    }
    if built.get("history"):
        out["history"] = built["history"]
    return out


def main():
    prev = read_window_var(OUT, "SECTOR_RESONANCE")
    built = None
    if os.environ.get("SECTOR_RESONANCE_FORCE_ACC", "").strip() != "1":
        try:
            built = build_from_kline()
        except Exception:
            log("kline 路径异常：\n" + traceback.format_exc(limit=3))
            built = None
    if not built:
        log("回退累积路径")
        built = build_from_accumulate(prev)
    if not built:
        log("两条路径都失败 → 保留旧文件，不覆盖（避免把页面打成空）")
        return 0

    payload = finalize(built, prev)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    banner = ("/* 板块共振度 · absorb ratio（PC1 解释占比）\n"
              "   生成：v8/gen_sector_resonance.py · %s\n"
              "   method=%s · data_date=%s · n=%s */\n"
              % (payload["update_time"], payload["method"], payload["data_date"], payload["n_sectors"]))
    body = "window.SECTOR_RESONANCE = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(banner + body)
    log("已写出 %s（%.1f KB）method=%s pc1=%s z=%s level=%s"
        % (OUT.name, len(banner + body) / 1024, payload["method"],
           payload["pc1_pct"], payload["z"], payload["level"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
