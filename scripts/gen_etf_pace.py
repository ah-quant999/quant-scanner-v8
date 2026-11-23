# -*- coding: utf-8 -*-
"""ETF 资金热度卡 · 配速比 + 局部异动灯 生成器（2026-11-23 主人拍板"做"）

口径（主人令：解析解读清楚，逻辑页登记完整，主站卡面脱敏）：
  ① 配速比 = 当日截至最新 5 分钟 bar 的累计成交额
             ÷ 近 20 个完整交易日「同一时刻槽位」的均累计成交额
     >1.2 超前放量（红） / <0.8 缩量观望（绿） / 其余正常（灰）
     —— 回答「今天量能相对历史同时刻是超前还是落后」，随盘中时间自动归一。
  ② 局部异动灯 = 最近 3 根已完成 5 分钟 bar（≈15 分钟窗口）成交额之和
             在近 20 日「同一时刻槽位的同长度窗口」分布中的分位
     >90 分位亮灯（这才是"哪一分钟开始放量"的答案），灯色按该窗口涨跌（红涨绿跌）。

数据源：新浪 5 分钟 K（quotes.sina.cn，1023 条 ≈ 22 交易日，含成交额），
        东财 push2his klt=5 兜底（cn runner 可达）。额口径为主，缺失降级量口径并如实标注。
槽位约定：新浪 5 分钟 bar 时间为 bar 结束时刻：09:35..11:30（24 槽）、13:05..15:00（24 槽），
        全日 48 槽；今日最后一根为已完成 bar，不含未走完的半根。

产出：data/ETF_PACE.js（window.ETF_PACE）
接线：update_v8 run_experiment_cards（盘中每轮重算，失败隔离）。
"""
import json, os, re, sys, datetime, threading

OUT = "data/ETF_PACE.js"
HEAT = "raw_data/etf_intraday_heat.json"
SLOTS_PER_DAY = 48          # 09:35..11:30 + 13:05..15:00
BASE_DAYS = 20              # 基线窗口
WIN_BARS = 3                # 局部窗口 = 3 根 5min bar ≈ 15 分钟
PACE_HOT, PACE_COOL = 1.2, 0.8
LIGHT_PCTL = 90

try:
    import requests
except ImportError:
    requests = None

UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn"}


def bj_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)


def _sym(code):
    """ETF 代码 → 新浪符号：5x=沪、15x=深。"""
    return ("sh" + code) if code.startswith(("5",)) else ("sz" + code)


def fetch_sina_min5(sym):
    """新浪 5 分钟 K → [(date, slot_idx, amount, close), ...]；bar 时间=结束时刻。"""
    if requests is None:
        return None
    url = ("https://quotes.sina.cn/cn/api/jsonp_v2.php/var _=/"
           "CN_MarketDataService.getKLineData")
    r = requests.get(url, params={"symbol": sym, "scale": "5", "ma": "no",
                                  "datalen": "1023"}, headers=UA, timeout=15)
    i, j = r.text.find("("), r.text.rfind(")")
    arr = json.loads(r.text[i + 1:j])
    out = []
    for b in arr:
        day, hm = b["day"][:10], b["day"][11:16]
        if hm <= "09:30":
            continue
        if hm <= "11:30":                       # 09:35..11:30 → 槽 0..23
            slot = int((int(hm[:2]) * 60 + int(hm[3:]) - 575) // 5)
        else:                                   # 13:05..15:00 → 槽 24..47
            slot = 24 + int((int(hm[:2]) * 60 + int(hm[3:]) - 785) // 5)
        if not (0 <= slot < SLOTS_PER_DAY):
            continue
        amt = float(b.get("amount") or 0) or float(b.get("volume") or 0)
        out.append((day, slot, amt, float(b["close"])))
    return out


def fetch_em_min5(code):
    """东财 push2his 5 分钟 K 兜底（额口径）。新浪全败时用。"""
    if requests is None:
        return None
    secid = ("1." if code.startswith(("5",)) else "0.") + code
    try:
        r = requests.get("https://push2his.eastmoney.com/api/qt/stock/kline/get",
            params={"secid": secid, "klt": "5", "fqt": "1", "lmt": "1023",
                    "end": "20500101", "iscca": "1",
                    "fields1": "f1,f2,f3", "fields2": "f51,f52,f53,f54,f55,f56,f57"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        kl = ((r.json().get("data") or {}).get("klines")) or []
        out = []
        for line in kl:
            p = line.split(",")
            dt = p[0]                            # 2026-11-23 09:35
            day, hm = dt[:10], dt[11:16]
            if hm <= "09:30":
                continue
            if hm <= "11:30":
                slot = int((int(hm[:2]) * 60 + int(hm[3:]) - 575) // 5)
            else:
                slot = 24 + int((int(hm[:2]) * 60 + int(hm[3:]) - 785) // 5)
            if not (0 <= slot < SLOTS_PER_DAY):
                continue
            vol = float(p[5]); amt = float(p[6])
            out.append((day, slot, amt if amt > 0 else vol, float(p[2])))
        return out
    except Exception:
        return None


def analyze(bars, today):
    """bars: [(day, slot, amt, close)] 已按时间升序。
    返回 dict(pace/state/win_pct/win_dir/today_amt/base_amt/amount_basis/done) 或 None。"""
    by_day = {}
    for d, s, a, c in bars:
        by_day.setdefault(d, {})[s] = (a, c)
    days = sorted(by_day)
    past = [d for d in days if d < today]
    if not past:
        return None
    past = past[-BASE_DAYS:]
    # 今日累计曲线
    t_slots = by_day.get(today, {})
    if not t_slots:
        return None
    last_slot = max(t_slots)
    cum_today = 0.0
    today_amt_by_slot = {}
    for s in sorted(t_slots):
        cum_today += t_slots[s][0]
        today_amt_by_slot[s] = cum_today
    # 基线：过去 N 日同槽累计均额（只取当日有完整该槽的天）
    base_cum = {}                             # slot -> [每日累计]
    for d in past:
        slots = by_day[d]
        c = 0.0
        for s in sorted(slots):
            c += slots[s][0]
            base_cum.setdefault(s, []).append(c)
    base_last = base_cum.get(last_slot)
    if not base_last or len(base_last) < max(5, BASE_DAYS // 2):
        return None                           # 样本不足（新上市/长期停牌）如实不算
    base_avg = sum(base_last) / len(base_last)
    if base_avg <= 0:
        return None
    pace = today_amt_by_slot[last_slot] / base_avg
    # 今日已走槽位数 ≥3 才可判局部窗口
    done = last_slot + 1
    res = dict(pace=round(pace, 2), done=done,
               today_amt=round(today_amt_by_slot[last_slot] / 1e8, 2),
               base_amt=round(base_avg / 1e8, 2))
    res["amount_basis"] = "amount"
    if pace > PACE_HOT:
        res["state"] = "hot"
    elif pace < PACE_COOL:
        res["state"] = "cool"
    else:
        res["state"] = "normal"
    # 局部 15 分钟窗口分位
    if done >= WIN_BARS:
        w = sum(t_slots[s][0] for s in range(last_slot - WIN_BARS + 1, last_slot + 1))
        # 涨跌方向：窗口首 bar 开盘未存 → 用窗口首槽收盘 vs 末槽收盘
        dir_chg = t_slots[last_slot][1] - t_slots[last_slot - WIN_BARS + 1][1]
        hist = []
        for d in past:
            slots = by_day[d]
            if all(s in slots for s in range(last_slot - WIN_BARS + 1, last_slot + 1)):
                hist.append(sum(slots[s][0] for s in
                                range(last_slot - WIN_BARS + 1, last_slot + 1)))
        if len(hist) >= max(5, BASE_DAYS // 2):
            rank = sum(1 for h in hist if h <= w)
            res["win_pct"] = int(rank * 100 / len(hist))
            res["win_dir"] = 1 if dir_chg > 0 else (-1 if dir_chg < 0 else 0)
        else:
            res["win_pct"] = None
    else:
        res["win_pct"] = None
    return res


def main():
    heat = json.load(open(HEAT, encoding="utf-8"))
    items = heat.get("items", [])
    today = bj_now().strftime("%Y-%m-%d")
    results, errs = {}, []
    lock = threading.Lock()

    def work(it):
        code = it.get("code") or it.get("代码")
        name = it.get("name") or it.get("名称")
        try:
            bars = fetch_sina_min5(_sym(code))
            src = "sina"
            if not bars or len(bars) < 100:
                bars2 = fetch_em_min5(code)
                if bars2:
                    bars, src = bars2, "eastmoney"
            if not bars:
                with lock: errs.append(f"{code} 无分钟数据")
                return
            a = analyze(bars, today)
            if a is None:
                # 次新 ETF：上市不足 20 日，基线建立中（如实标注，不算 pace）
                n_days = len(set(b[0] for b in bars))
                with lock:
                    results[code] = dict(name=name, state="new", pace=None,
                                         win_pct=None, src=src, n_days=n_days)
                return
            a["name"] = name
            a["src"] = src
            with lock: results[code] = a
        except Exception as e:
            with lock: errs.append(f"{code} {type(e).__name__}: {e}")

    ths = [threading.Thread(target=work, args=(it,)) for it in items]
    for t in ths: t.start()
    for t in ths: t.join(timeout=120)

    n_hot = sum(1 for v in results.values() if v["state"] == "hot")
    n_cool = sum(1 for v in results.values() if v["state"] == "cool")
    n_light = sum(1 for v in results.values() if (v.get("win_pct") or 0) > LIGHT_PCTL)
    out = dict(
        update_time=bj_now().strftime("%Y-%m-%d %H:%M:%S"),
        data_date=today, slots_per_day=SLOTS_PER_DAY, base_days=BASE_DAYS,
        win_bars=WIN_BARS, pace_hot=PACE_HOT, pace_cool=PACE_COOL,
        light_pctl=LIGHT_PCTL,
        universe=dict(total=len(items), ok=len(results)),
        summary=dict(hot=n_hot, cool=n_cool, light=n_light),
        items=results,
        errors=errs[:10],
        note="配速比与异动灯口径见逻辑详解页；信号为观测参考，非交易指令",
    )
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// ETF_PACE · 配速比+局部异动灯 · gen_etf_pace.py\n")
        f.write("// 口径详情见 logic.html 登记条目\n")
        f.write("window.ETF_PACE = " + json.dumps(out, ensure_ascii=False) + ";\n")
    print(f"ETF_PACE: {len(results)}/{len(items)} ok | 放量{n_hot} 缩量{n_cool} 异动灯{n_light} | errs={len(errs)}")


if __name__ == "__main__":
    main()
