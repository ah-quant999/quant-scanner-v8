# -*- coding: utf-8 -*-
"""市场攻防档位 · 五信号合成生成器（2026-11-24 主人拍板：方案B 自建，融合 A1 方法论）

主人目标：把「下跌段防守、进攻段加仓」的判断方法融进 v8，让 v8 判断更准。
口径（方案B=同方法自建，零新增抓取，全部读 v8 现有数据，规则可解释、logic.html 登记）：

  五路信号各给 −1 / 0 / +1：
  ① 趋势环境   = 平均股价(东财800005) 相对 MA20 / MA60 位置（双上=+1 双下=−1 纠缠=0）
  ② 涨跌广度   = 上证上涨家数占比（>55%=+1 <45%=−1 其余=0）
  ③ 涨停情绪   = 今日涨停总数 ÷ 近10交易日均值（>1.1=+1 <0.7=−1 其余=0）；
                 炸板率(炸板÷(涨停+炸板))>40% 时折减一档（封板质量差，情绪打折）
  ④ 量能配速   = ETF_PACE 全池：放量数−缩量数（≥2=+1 ≤−2=−1 其余=0）；缺数据/陈旧=0 如实标注
  ⑤ 板块资金   = 净流入板块数 ÷ 净流出板块数（>1.2=+1 <0.8=−1 其余=0）
  危机开关     = 危机雷达 score：40~59 记 −1；≥60 强制守档（一票否决）

  合成：总分 S∈[−5,+5]（危机分另计）→
        S ≥ +2  ⚔️ 攻（仓位参考 0.95）
        −2<S<+2 👁️ 观（0.50）
        S ≤ −2  🛡️ 守（0.30）
        危机 ≥60 → 无论总分，强制守。
  色彩：攻=红 #ef5350 / 观=金 #ffd024 / 守=绿 #26a69a（红涨绿跌铁律）。

数据源（全部现成管线，无新增网络调用）：
  raw_data/avg_price_data.json        趋势
  raw_data/index_quotes.json          广度
  raw_data/limit_up_heatmap.json      涨停情绪（涨停数）
  raw_data/limit_up_broken.json       涨停情绪（炸板率）
  data/ETF_PACE.js                    量能（盘中链上游产物，陈旧/缺失=0）
  raw_data/sector_fund_flow.json      资金
  raw_data/crisis_data.json           危机开关

产出：data/MARKET_TACTIC.js（window.MARKET_TACTIC）
      ⚠️ 命名纪律：window.MARKET_REGIME 已被利率板块推荐框架占用（v8/gen_invest_avoid.py 产出并回读，
      主人 2026-08-19 拍板），本卡命名 MARKET_TACTIC 避撞（2026-11-24 覆盖事故后改名根治）。
接线：update_v8 run_experiment_cards（gen_etf_pace 之后跑，保证读到当日量能）。
"""
import json, os, re, datetime

OUT = "data/MARKET_TACTIC.js"
BREADTH_UP, BREADTH_DOWN = 0.55, 0.45      # 广度阈值
ZT_HOT, ZT_COOL = 1.1, 0.7                 # 涨停均值倍数阈值
BROKEN_RATE_CAP = 0.40                     # 炸板率折减线
PACE_NET = 2                               # ETF 放量-缩量净差阈值
FLOW_RATIO_UP, FLOW_RATIO_DOWN = 1.2, 0.8  # 板块进出比阈值
CRISIS_WARN, CRISIS_FORCE = 40, 60         # 危机雷达两道线
S_ATTACK, S_DEFENSE = 2, -2                # 档位分数线
EXPOSURE = {"attack": 0.95, "watch": 0.50, "defense": 0.30}
COLOR = {"attack": "#ef5350", "watch": "#ffd024", "defense": "#26a69a"}
ICON = {"attack": "⚔️", "watch": "👁️", "defense": "🛡️"}
LABEL = {"attack": "攻", "watch": "观", "defense": "守"}


def bj_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _dim_trend():
    d = _load("raw_data/avg_price_data.json")
    if not d or d.get("position_vs_ma20") is None:
        return 0, "趋势环境：平均股价数据缺席 → 0", dict(score=0)
    p20, p60 = d["position_vs_ma20"], d.get("position_vs_ma60")
    above20 = p20 > 0
    above60 = (p60 > 0) if p60 is not None else above20
    if above20 and above60:
        s = 1
        txt = f"平均股价站上 MA20/MA60（+{p20:.1f}%/+{p60:.1f}%）→ 多头排列"
    elif not above20 and not above60:
        s = -1
        txt = f"平均股价跌破 MA20/MA60（{p20:.1f}%/{p60:.1f}%）→ 空头排列"
    else:
        s = 0
        txt = f"平均股价在 MA20/MA60 之间纠缠（{p20:.1f}%/{p60:.1f}%）→ 方向未定"
    return s, txt, dict(score=s, p20=round(p20, 1),
                        p60=(round(p60, 1) if p60 is not None else None))


def _dim_breadth():
    d = _load("raw_data/index_quotes.json")
    it = (d or {}).get("items") or []
    sh = next((x for x in it if x.get("code") == "000001"), None)
    if not sh:
        return 0, "涨跌广度：上证家数缺席 → 0", dict(score=0)
    up, down = sh.get("up") or 0, sh.get("down") or 0
    if up + down <= 0:
        return 0, "涨跌广度：家数异常 → 0", dict(score=0)
    ratio = up / (up + down)
    if ratio > BREADTH_UP:
        s, q = 1, "普涨"
    elif ratio < BREADTH_DOWN:
        s, q = -1, "普跌"
    else:
        s, q = 0, "分化"
    return s, f"上涨家数占比 {ratio*100:.0f}%（{up}涨/{down}跌）→ {q}", dict(
        score=s, ratio=round(ratio, 2), up=up, down=down)


def _dim_zt():
    hm = _load("raw_data/limit_up_heatmap.json")
    if not hm or not hm.get("sectors") or not hm.get("dates"):
        return 0, "涨停情绪：热力矩阵缺席 → 0", dict(score=0)
    dates, sectors = hm["dates"], hm["sectors"]
    n = len(dates)
    totals = [sum(int(row["data"][i] or 0) for row in sectors) for i in range(n)]
    today_zt = totals[-1]
    base = totals[-11:-1] if n >= 11 else totals[:-1]
    base = [t for t in base if t > 0]
    if not base or today_zt <= 0:
        return 0, f"涨停情绪：样本不足（今日涨停 {today_zt}）→ 0", dict(score=0, zt=today_zt)
    avg10 = sum(base) / len(base)
    ratio = today_zt / avg10
    s = 1 if ratio > ZT_HOT else (-1 if ratio < ZT_COOL else 0)
    txt = f"今日涨停 {today_zt} 家（近10日均 {avg10:.0f}，{ratio:.2f}倍）"
    broken_rate = None
    bk = _load("raw_data/limit_up_broken.json")
    if bk and (bk.get("date") == dates[-1] or True):   # 炸板池同日才精确，异日仅参考
        broken = bk.get("total") or 0
        if today_zt + broken > 0:
            broken_rate = broken / (today_zt + broken)
            if broken_rate > BROKEN_RATE_CAP and s == 1:
                s = 0
                txt += f"；炸板率 {broken_rate*100:.0f}% 偏高 → 情绪折减"
            else:
                txt += f"；炸板率 {broken_rate*100:.0f}%"
    q = {1: "情绪升温", 0: "情绪中性", -1: "情绪降温"}[s]
    return s, txt + f" → {q}", dict(score=s, zt=today_zt, zt_ratio=round(ratio, 2),
                                    broken_rate=(round(broken_rate, 2) if broken_rate is not None else None))


def _dim_volume(today):
    """读 data/ETF_PACE.js（上游产物）。当日才算，陈旧/缺失=0 如实标注。"""
    try:
        with open("data/ETF_PACE.js", encoding="utf-8") as f:
            txt = f.read()
        m = re.search(r"window\.ETF_PACE\s*=\s*(\{.*\});?\s*$", txt, re.S)
        d = json.loads(m.group(1)) if m else None
    except Exception:
        d = None
    if not d or d.get("data_date") != today:
        return 0, "量能配速：ETF 盘中量能未刷新/陈旧 → 0（不计分）", dict(score=0, available=False)
    summ = d.get("summary") or {}
    hot, cool = summ.get("hot") or 0, summ.get("cool") or 0
    net = hot - cool
    s = 1 if net >= PACE_NET else (-1 if net <= -PACE_NET else 0)
    q = {1: "量能超前", 0: "量能均衡", -1: "量能收缩"}[s]
    return s, f"ETF 全池量能：放量 {hot} / 缩量 {cool}（净差 {net:+d}）→ {q}", dict(
        score=s, hot=hot, cool=cool, available=True)


def _dim_flow():
    """名单是固定 100+100 的 top 榜 ⇒ 条数恒等无信息，改用净额合计对比。"""
    d = _load("raw_data/sector_fund_flow.json")
    if not d:
        return 0, "板块资金：缺席 → 0", dict(score=0)
    sin = [(x.get("net") or 0) for x in (d.get("sectors_in") or [])]
    sout = [(x.get("net") or 0) for x in (d.get("sectors_out") or [])]
    fin, fout = sum(sin), abs(sum(sout))
    if fin + fout <= 0:
        return 0, "板块资金：净额皆空 → 0", dict(score=0)
    ratio = fin / fout if fout > 0 else 99.0
    if ratio > FLOW_RATIO_UP:
        s, q = 1, "流入压过流出，资金进攻"
    elif ratio < FLOW_RATIO_DOWN:
        s, q = -1, "流出压过流入，资金防守"
    else:
        s, q = 0, "资金进出均衡"
    return s, f"板块净流入合计 +{fin:.0f} 亿 / 净流出合计 -{fout:.0f} 亿（{ratio:.2f}倍）→ {q}", dict(
        score=s, flow_in=round(fin, 1), flow_out=round(fout, 1),
        ratio=(round(ratio, 2) if ratio < 99 else None))


def _crisis():
    d = _load("raw_data/crisis_data.json")
    if not d:
        return 0, None, dict(score=0)
    score = float(d.get("score") or 0)
    level = d.get("level") or ""
    if score >= CRISIS_FORCE:
        s, txt = -2, f"危机雷达 {score:.0f}（{level}）→ 强制守档（一票否决）"
    elif score >= CRISIS_WARN:
        s, txt = -1, f"危机雷达 {score:.0f}（{level}）→ 扣 1 分"
    else:
        s, txt = 0, f"危机雷达 {score:.0f}（{level}）→ 无扣分"
    return s, txt, dict(score=s, radar=score, level=level)


def main():
    today = bj_now().strftime("%Y-%m-%d")
    dims = {}
    reasons = []
    total = 0
    for key, fn in (("trend", _dim_trend), ("breadth", _dim_breadth),
                    ("zt", _dim_zt)):
        s, txt, det = fn()
        dims[key] = det
        total += s
        reasons.append(txt)
    s, txt, det = _dim_volume(today)
    dims["volume"] = det
    if det.get("available"):
        total += s
    reasons.append(txt)
    s, txt, det = _dim_flow()
    dims["flow"] = det
    total += s
    reasons.append(txt)

    cs, ctxt, cdet = _crisis()
    dims["crisis"] = cdet
    if ctxt:
        reasons.append(ctxt)
    total += cs

    forced = (cdet.get("radar") or 0) >= CRISIS_FORCE
    if forced:
        regime = "defense"
    elif total >= S_ATTACK:
        regime = "attack"
    elif total <= S_DEFENSE:
        regime = "defense"
    else:
        regime = "watch"

    out = dict(
        update_time=bj_now().strftime("%Y-%m-%d %H:%M:%S"),
        data_date=today,
        regime=regime, label=LABEL[regime], icon=ICON[regime],
        color=COLOR[regime], exposure=EXPOSURE[regime],
        score=total, forced=forced,
        thresholds=dict(breadth=[BREADTH_DOWN, BREADTH_UP], zt=[ZT_COOL, ZT_HOT],
                        broken_rate_cap=BROKEN_RATE_CAP, pace_net=PACE_NET,
                        flow=[FLOW_RATIO_DOWN, FLOW_RATIO_UP],
                        crisis=[CRISIS_WARN, CRISIS_FORCE], s=[S_DEFENSE, S_ATTACK]),
        dims=dims, reasons=reasons,
        note="五信号合成攻防档位：防守降仓、进攻加仓（方法论同趋势跟随/波动率目标仓位）；口径见逻辑详解页；观测参考非交易指令",
    )
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// MARKET_TACTIC · 五信号合成攻防档位 · gen_market_regime.py\n")
        f.write("// 口径详情见 logic.html 登记条目\n")
        f.write("window.MARKET_TACTIC = " + json.dumps(out, ensure_ascii=False) + ";\n")
    print(f"MARKET_TACTIC: {LABEL[regime]}({regime}, {EXPOSURE[regime]}) "
          f"score={total} forced={forced} | dims=" +
          ",".join(f"{k}:{v.get('score')}" for k, v in dims.items()))


if __name__ == "__main__":
    main()
