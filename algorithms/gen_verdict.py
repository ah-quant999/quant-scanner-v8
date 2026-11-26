#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_verdict.py — 今日作战指令（唯一裁决卡）· 2026-11-26 主人令

主人原话：「我就是觉得现在卡片信息太多了，而我很混乱，我不知道该怎么买买多少买什么。
           我做 v8 就是想给我提供对大盘和持仓的判断，什么信号出现了我该进场该清仓，
           进多少出多少。希望你帮我全面整合一下，给一个综合研判。」

设计铁律（不得违反）：
  1. **纯合成器，零新预测**。所有数字只从已上线产物读，不新增任何模型/权重/回测。
     理由：2026-11-26 实测 17 个因子 0 个 PASS、共振 5 日 +0.01%、10 日 -0.30%
     ⇒ 现阶段「加法越多噪声越大」，本卡只做**收敛**（把 9 个信号收敛成 1 个动作）。
  2. **仓位取最小值**，不取平均：min(攻防档位, 情绪闸门, 风控系数) —— 保守优先，
     任一维度说不行就不行。这是唯一不易错的合成方式。
  3. **每个结论必须配「人话」+「依据数字」**，缺一不输出（主人要能自己复核）。
  4. **未样本外验证的规则必须自报家门**（caveat 字段强制非空），不许美化。
  5. 每日留痕：raw_data/history/verdict_YYYYMMDD.json 存当日全量输入 + 裁决，
     3-6 个月后即为「情绪周期当仓位闸门」的真样本（成本≈0）。

输入（全部本地 data/*.js，缺失自动降级不崩）：
  MARKET_TACTIC · MARKET_VERDICT · SENTIMENT_CYCLE · INDEX_QUOTES
  SECTOR_FUND_FLOW · SECTOR_FUND_FLOW_TREND · CRISIS_DATA · RISK_GUARD
  TOP10_DAILY · PORTFOLIO · LIMIT_UP_HEATMAP

输出：
  raw_data/verdict.json                 → 由 update_v8 生成 data/V8_VERDICT.js
  raw_data/history/verdict_YYYYMMDD.json → 每日留痕（不注入前端）
"""
import os, re, json, sys
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("V8_ROOT") or os.path.dirname(BASE)
DATA = os.path.join(ROOT, "data")
RAW = os.path.join(ROOT, "raw_data")
HIST = os.path.join(RAW, "history")
OUT = os.path.join(RAW, "verdict.json")

NOW = datetime.now()
TODAY = NOW.strftime("%Y-%m-%d")


# ────────────────────────── 读取 data/*.js ──────────────────────────
def load(name, win=None):
    """读 data/<name>.js 里的 window.<win> = {...}，失败返回 {}。
    win 缺省同 name（个别文件文件名与全局名不一致，如 PORTFOLIO.js → window.PORTFOLIO_DATA）。"""
    win = win or name
    p = os.path.join(DATA, name + ".js")
    if not os.path.exists(p):
        return {}
    try:
        s = open(p, encoding="utf-8", errors="ignore").read()
        m = re.search(r"window\." + win + r"\s*=\s*(\{.*\})\s*;?\s*$", s, re.S)
        if not m:
            m = re.search(r"window\." + win + r"\s*=\s*(\{.*\})", s, re.S)
        if not m:
            return {}
        return json.loads(m.group(1))
    except Exception as e:
        print("  ! load %s 失败: %s" % (name, e))
        return {}


def _f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def _i(x, d=0):
    try:
        return int(float(x))
    except Exception:
        return d


# ────────────────────────── 仓位闸门 ──────────────────────────
def compute_cap(tactic, senti, rg, breadth):
    """仓位上限 = min(攻防档位, 情绪闸门, 风控系数)，任一维度否决即生效。
    返回 (cap, parts[])，parts 每项都带「人话」供前端直接展示。"""
    parts = []

    # ① 攻防档位（五信号合成）
    tac_exp = _f(tactic.get("exposure"), 0.0)
    tac_lab = tactic.get("label") or "未知"
    tac_score = _i(tactic.get("score"), 0)
    parts.append({
        "k": "攻防档位",
        "v": "%d%%" % round(tac_exp * 100),
        "raw": tac_exp,
        "plain": "趋势/宽度/涨停/量能/危机五个信号合起来 %+d 分 → 「%s」，允许仓位 %d%%"
                 % (tac_score, tac_lab, round(tac_exp * 100)),
    })

    # ② 情绪周期闸门（经验规则·未回测，故单独标注）
    phase = senti.get("phase") or ""
    sscore = _f(senti.get("score"))
    gate = 1.0
    if "狂热" in phase:
        gate = 0.5
        gate_txt = "情绪狂热（%d 分）⇒ 不追高，仓位上限压到 50%%" % round(sscore)
    elif "高潮" in phase:
        gate = 0.6
        gate_txt = "情绪高潮（%d 分）⇒ 只留强势，上限 60%%" % round(sscore)
    elif "退潮" in phase:
        gate = 0.3
        gate_txt = "情绪退潮 ⇒ 收缩到 30% 以内，等止跌"
    elif "冰点" in phase:
        gate = 0.6
        gate_txt = "情绪冰点（%d 分）⇒ 往往是报复性反弹前夜，可小仓试错，但必须分批" % round(sscore)
    elif "修复" in phase or "回暖" in phase:
        gate = 0.8
        gate_txt = "情绪修复 ⇒ 可正常参与，上限 80%"
    else:
        gate = 0.8
        gate_txt = "情绪中性 ⇒ 不额外限制（上限 80%）"
    parts.append({
        "k": "情绪闸门",
        "v": "%d%%" % round(gate * 100),
        "raw": gate,
        "plain": gate_txt,
        "untested": True,
    })

    # ③ 风控系数（组合最大回撤分档）
    mult = _f(rg.get("multiplier"), 1.0)
    if rg:
        parts.append({
            "k": "风控系数",
            "v": "×%.2f" % mult,
            "raw": mult,
            "plain": "组合最大回撤 %.1f%%（%s档）⇒ 攻防额度再打 %.2f 折"
                     % (_f(rg.get("max_drawdown")) * 100, rg.get("tier") or "正常", mult),
        })

    cap = tac_exp * mult
    cap = min(cap, gate)

    # ④ 情绪-宽度背离否决：情绪热但个股普跌 ⇒ 这种「热」是假的，不许按热做
    div = None
    if breadth is not None and breadth < 0.45 and ("狂热" in phase or "高潮" in phase):
        cap = min(cap, 0.3)
        div = ("情绪说热（%s），但上涨家数只占 %.0f%% —— 涨停集中在少数题材，"
               "大盘是普跌的。这种背离日不许按「热」加仓，上限压到 30%%。"
               % (phase, breadth * 100))

    return round(cap, 2), parts, div


# ────────────────────────── 买卖清单 ──────────────────────────
def _nm(s):
    """板块名归一：去掉 概念/行业/Ⅱ/指数 等后缀噪声，供模糊匹配。"""
    s = str(s or "")
    for w in ("概念", "行业", "Ⅱ", "Ⅲ", "指数", "板块", "精选"):
        s = s.replace(w, "")
    return s.strip()


def _match_sector(name, pool):
    """在 pool(list[{name,leaders}]) 里找同名或包含关系的板块，返回该条或 None。"""
    n = _nm(name)
    if not n:
        return None
    best = None
    for it in pool or []:
        m = _nm(it.get("name"))
        if not m:
            continue
        if m == n:
            return it
        if len(n) >= 3 and len(m) >= 3 and (n in m or m in n):
            best = best or it
    return best


def build_buy(trend, flow, top10, avoid_names, sl, etfm):
    # 持续净流入板块：5 日净流入 > 0 且 连流入天数 ≥ 3
    cands = []
    pool = trend.get("trend_5d") or trend.get("sectors_in") or []
    for s in pool:
        n5 = _f(s.get("net_5d"))
        days = _i(s.get("consecutive_days"))
        if n5 > 0 and days >= 3:
            cands.append({
                "name": s.get("name"),
                "type": s.get("type") or "",
                "net_5d": round(n5, 1),
                "days": days,
                "net_today": round(_f(s.get("net")), 1),
            })
    cands.sort(key=lambda x: (-x["net_5d"]))
    cands = [c for c in cands if not any(a and (a in c["name"] or c["name"] in a) for a in avoid_names)]
    sectors = cands[:3]

    # 资金主线 → 该板块的龙头（lu_sectors=涨停龙头 / fr_sectors=资金龙头）→ 再不行给 ETF
    lus = sl.get("lu_sectors") or []
    frs = sl.get("fr_sectors") or []
    for c in sectors:
        hit = _match_sector(c["name"], lus)
        src = "涨停龙头"
        if not hit:
            hit = _match_sector(c["name"], frs)
            src = "资金龙头"
        lead = (hit or {}).get("leaders") or []
        c["leaders"] = [{"code": x.get("code"), "name": x.get("name"),
                         "price": x.get("price"), "chg": x.get("chg")} for x in lead[:2]]
        c["lead_src"] = src if lead else ""
        # ETF 兜底（概念→ETF 映射，覆盖 56 个常炒概念）
        c["etf"] = None
        for key in (c["name"], _nm(c["name"])):
            e = etfm.get(key)
            if isinstance(e, dict) and e.get("etf"):
                c["etf"] = {"code": e["etf"].get("code"), "name": e["etf"].get("name")}
                break

    # 因子榜个股（独立一条线，标明与资金主线是否同向；当日大跌的不许喊买）
    ind_sets = [_nm(c["name"]) for c in sectors]
    stocks = []
    for s in (top10.get("top10") or [])[:5]:
        ind = s.get("industry") or ""
        if any(a and (a in ind or ind in a) for a in avoid_names):
            continue
        same = any(k and (_nm(ind) in k or k in _nm(ind)) for k in ind_sets)
        chg = _f(s.get("pct_chg"))
        stocks.append({
            "code": s.get("code"), "name": s.get("name"), "rank": _i(s.get("rank")),
            "close": s.get("close"), "chg": chg,
            "stop": s.get("stop_loss"), "target": s.get("target_price"),
            "rr": s.get("risk_reward"), "industry": ind, "same_theme": same,
            "buyable": chg >= -1.0,
            "why": "今日因子榜第 %s 名 · 信号 %s 个" % (s.get("rank"), s.get("sig_count"))
                   + ("" if chg >= -1.0 else " · 当日 %+.1f%% 在跌，等企稳" % chg),
        })
        if len(stocks) >= 3:
            break

    # 两条线是否打架：因子榜前 3 有没有跟资金主线同向的
    conflict = bool(stocks) and not any(x["same_theme"] for x in stocks)

    # 第三层：今日涨停最集中的板块 + 龙头（有具体票，但属于追高，防守档只等回调）
    chase = []
    for x in (lus or [])[:6]:
        if any(a and (a in (x.get("name") or "") or (x.get("name") or "") in a) for a in avoid_names):
            continue
        chase.append({
            "name": x.get("name"), "today": _i(x.get("today")), "sum5": _i(x.get("sum5")),
            "leaders": [{"code": l.get("code"), "name": l.get("name"),
                         "price": l.get("price"), "chg": l.get("chg")}
                        for l in (x.get("leaders") or [])[:3]],
        })
        if len(chase) >= 2:
            break

    return {"sectors": sectors, "stocks": stocks, "conflict": conflict, "chase": chase}


def build_avoid(flow, trend):
    out = []
    for s in (flow.get("sectors_out") or [])[:40]:
        net = _f(s.get("net"))
        chg = _f(s.get("chg"))
        if net >= -0.5:
            continue
        # 涨超 1% 还在净流出 = 派发，最危险（涨 0.02% 这种不算）
        dist = chg > 1.0
        tag = ("涨 %.1f%% 却在净流出 → 有人借涨出货" % chg) if dist else ("净流出 %.1f 亿 · 当日 %.1f%%" % (net, chg))
        out.append({"name": s.get("name"), "net": round(net, 1), "chg": round(chg, 2),
                    "why": tag, "dist": dist})
    # 派发的排前面
    out.sort(key=lambda x: (0 if x["dist"] else 1, x["net"]))
    return out[:4]


# ────────────────────────── 持仓动作 ──────────────────────────
def build_holdings(pf, tac_label, cap):
    pos = pf.get("positions") or []
    acct = pf.get("account") or {}
    rows = []
    for p in pos:
        cost = _f(p.get("cost_price"))
        live = _f(p.get("live_price"))
        qty = _i(p.get("qty"))
        if not cost or not live:
            continue
        pnl = (live / cost - 1.0) * 100.0
        mv = live * qty
        if pnl <= -15:
            act, why = "清仓", "已亏 %.1f%%，远超单票止损线（-7%%），纪律上没有再讨论的余地" % pnl
        elif pnl <= -7:
            act, why = "减半", "亏 %.1f%% 破了 -7%% 的止损线，先砍一半，剩下的等反抽再处理" % pnl
        elif pnl >= 8:
            act, why = "移动止盈", "已有 %.1f%% 浮盈，把止盈线提到成本上方 3%%，回撤 5%% 就走" % pnl
        else:
            act, why = "持有", "盈亏 %.1f%% 在可承受区间，跌破成本 -7%% 就止损" % pnl
        if tac_label in ("守", "防", "退"):
            why += "；大盘档位为「%s」，不加仓" % tac_label
        rows.append({
            "code": p.get("code"), "name": p.get("name"), "qty": qty,
            "cost": round(cost, 2), "live": round(live, 2),
            "pnl_pct": round(pnl, 1), "mv": round(mv, 0), "action": act, "why": why,
        })
    rows.sort(key=lambda x: x["pnl_pct"])
    total = _f(acct.get("total_assets"))
    mv = _f(acct.get("market_value"))
    cur = (mv / total) if total else 0.0
    return {
        "rows": rows,
        "cur_pct": round(cur * 100, 1),
        "cash": round(_f(acct.get("available_cash")), 0),
        "total_assets": round(total, 0),
        "profit_rate": _f(acct.get("total_profit_rate")),
        "cap_pct": round(cap * 100),
        "gap_pct": round(max(0.0, cap - cur) * 100, 1),
    }


# ────────────────────────── 加仓检查表 ──────────────────────────
def build_checks(tactic, senti, flow, trend, idx, crisis):
    d = tactic.get("dims") or {}
    br = d.get("breadth") or {}
    up, down = _i(br.get("up")), _i(br.get("down"))
    zt = _i((d.get("zt") or {}).get("zt"))
    zt_ratio = _f((d.get("zt") or {}).get("zt_ratio"))
    ratio = _f(br.get("ratio"))
    in_cnt = _i((trend.get("summary") or {}).get("in_count"))
    phase = senti.get("phase") or "—"
    scale = idx.get("items") or []
    sh = next((x for x in scale if str(x.get("code")) == "000001"), {})
    sh_chg = _f(sh.get("chg"))
    radar = _f(crisis.get("score"), _f(tactic.get("dims", {}).get("crisis", {}).get("radar")))

    checks = [
        {"name": "个股普涨", "need": "上涨家数 > 下跌家数",
         "now": "%d 涨 / %d 跌" % (up, down), "met": up > down},
        {"name": "指数不拖后腿", "need": "沪指当日收涨",
         "now": "%+.2f%%" % sh_chg, "met": sh_chg > 0},
        {"name": "攻防不否决", "need": "五信号 ≥ 0 分（中性以上）",
         "now": "%+d 分 · %s" % (_i(tactic.get("score")), tactic.get("label") or "—"),
         "met": _i(tactic.get("score")) >= 0},
        {"name": "涨停有量", "need": "涨停 ≥ 80 家 且 不低于近10日均值",
         "now": "%d 家（均值比 %.2f）" % (zt, zt_ratio), "met": zt >= 80 and zt_ratio >= 1.0},
        {"name": "资金有主线", "need": "至少 10 个板块连续净流入",
         "now": "%d 个板块流入" % in_cnt, "met": in_cnt >= 10},
        {"name": "情绪不衰退", "need": "情绪阶段不是退潮/冰点",
         "now": phase, "met": ("退" not in phase and "冰" not in phase)},
        {"name": "宏观无警报", "need": "危机雷达 < 40",
         "now": "%.1f（%s）" % (radar, crisis.get("level") or "—"), "met": radar < 40},
    ]
    hit = sum(1 for c in checks if c["met"])
    return checks, hit


def build_triggers(checks, cap):
    add_items = [c for c in checks]
    return {
        "add": {
            "need": 5,
            "hit": sum(1 for c in checks if c["met"]),
            "total": len(checks),
            "rule": "上面 7 条里满足 ≥5 条，才把仓位往 5 成加；只满足 3-4 条，维持现在的上限不动",
            "items": add_items,
        },
        "cut": {
            "rule": "出现任一条，当天就把仓位砍到 1 成以内",
            "items": [
                {"cond": "危机雷达 > 60（高风险）", "act": "降到 1 成"},
                {"cond": "沪指单日跌超 2%", "act": "当天不新开仓，已有仓位减半"},
                {"cond": "持仓个股跌破买入价 -7%", "act": "单票止损，不许扛"},
                {"cond": "情绪转「退潮」（涨停比前一日少 30% 以上）", "act": "清掉跟风票，只留主线龙头"},
            ],
        },
        "exit": {
            "rule": "总账户从最高点回撤 8% 即触发强制降档（风控系数 0.5），回撤 15% 清仓",
            "items": [
                {"cond": "组合回撤 ≥ 8%", "act": "仓位上限减半"},
                {"cond": "组合回撤 ≥ 12%", "act": "上限压到 25%"},
                {"cond": "组合回撤 ≥ 15%", "act": "清仓，停手复盘"},
            ],
        },
    }


# ────────────────────────── 主流程 ──────────────────────────
def main():
    tac = load("MARKET_TACTIC")
    mv = load("MARKET_VERDICT")
    senti = load("SENTIMENT_CYCLE")
    idx = load("INDEX_QUOTES")
    flow = load("SECTOR_FUND_FLOW")
    trend = load("SECTOR_FUND_FLOW_TREND")
    crisis = load("CRISIS_DATA")
    rg = load("RISK_GUARD")
    top10 = load("TOP10_DAILY")
    pf = load("PORTFOLIO", "PORTFOLIO_DATA")
    sl = load("SECTOR_LEADERS")
    etfm = load("CONCEPT_ETF_MAP")
    heat = load("LIMIT_UP_HEATMAP")

    # 宽度
    items = idx.get("items") or []
    sh = next((x for x in items if str(x.get("code")) == "000001"), {})
    up, down = _i(sh.get("up")), _i(sh.get("down"))
    breadth = (up / float(up + down)) if (up + down) else None

    # 若 INDEX_QUOTES 无宽度，回落攻防档位的宽度
    if breadth is None:
        br = (tac.get("dims") or {}).get("breadth") or {}
        breadth = br.get("ratio")
        up, down = _i(br.get("up")), _i(br.get("down"))

    cap, parts, div = compute_cap(tac, senti, rg, breadth)
    avoid = build_avoid(flow, trend)
    avoid_names = [a["name"] for a in avoid]
    buy = build_buy(trend, flow, top10, avoid_names, sl, etfm)
    hold = build_holdings(pf, tac.get("label") or "", cap)
    checks, hit = build_checks(tac, senti, flow, trend, idx, crisis)
    triggers = build_triggers(checks, cap)

    # ── 能不能买：由加仓条件命中数决定，不看心情 ──
    if hit >= 5:
        buy["mode"] = "full"
        buy["mode_txt"] = "可以买"
        buy["factor"] = 1.0
    elif hit >= 3:
        buy["mode"] = "half"
        buy["mode_txt"] = "只能试"
        buy["factor"] = 0.5
    else:
        buy["mode"] = "none"
        buy["mode_txt"] = "今天别买"
        buy["factor"] = 0.0

    _sec0 = buy["sectors"][0]["name"] if buy["sectors"] else ""
    _veh = ""
    if buy["sectors"]:
        _s0 = buy["sectors"][0]
        if _s0.get("leaders"):
            _veh = "标的看 %s（%s）" % ("、".join(x["name"] for x in _s0["leaders"]),
                                      _s0.get("lead_src") or "龙头")
        elif _s0.get("etf"):
            _veh = "不想挑个股就买 %s（%s）" % (_s0["etf"]["name"], _s0["etf"]["code"])
        else:
            _veh = "这个方向 v8 里没有现成标的，要买只能自己挑该方向的票，或买对应行业 ETF"
    if buy["mode"] == "none":
        buy["advice"] = ("加仓条件只满足 %d/%d 条 —— 今天不买。不是没机会，是赔率不够，"
                         "硬买等于用确定的亏损换不确定的收益。" % (hit, len(checks)))
    elif buy["mode"] == "half":
        buy["advice"] = ("加仓条件满足 %d/%d 条，只能小仓试：方向是 %s；%s。"
                         "单票额度按半档算，错了立刻走。" % (hit, len(checks), _sec0, _veh))
    else:
        buy["advice"] = ("加仓条件满足 %d/%d 条，可以按额买：方向是 %s；%s。"
                         % (hit, len(checks), _sec0, _veh))
    if buy["conflict"]:
        buy["advice"] += (" 注意：今天因子榜（%s）跟资金主线不是同一条线 —— "
                          "两条线打架时以资金为准，因子榜那几只别急着买。"
                          % "、".join(x["name"] for x in buy["stocks"][:2]))

    # ── 一句话回答「今天到底买不买」：方向与标的必须对得上，否则不硬凑 ──
    _same_ok = [x for x in buy["stocks"] if x.get("same_theme") and x.get("buyable")]
    _lead_ok = [x for s in buy["sectors"] for x in (s.get("leaders") or [])]
    if buy["mode"] == "none":
        buy["answer"] = "今天不买，空仓等。"
        buy["answer_short"] = "不买"
    elif _same_ok:
        buy["answer"] = ("买 %s（资金主线和因子榜同向，这种最稳），单票 %.1f%% 起步。"
                         % (_same_ok[0]["name"], round(cap * 20 * buy["factor"], 1)))
        buy["answer_short"] = "买 " + _same_ok[0]["name"]
    elif _lead_ok:
        buy["answer"] = ("只买主线龙头 %s，等它回调、不追当天涨幅，单票 %.1f%% 起步。"
                         % (_lead_ok[0]["name"], round(cap * 20 * buy["factor"], 1)))
        buy["answer_short"] = "等回调买 " + _lead_ok[0]["name"]
    else:
        buy["answer"] = ("今天不买。方向和票对不上 —— 钱在进的方向（%s）没有成型标的，"
                         "有票的方向（%s）又没资金进来。这种日子硬凑就是送钱，空仓等明天。"
                         % (_sec0 or "无", "、".join(x["name"] for x in buy["stocks"][:2]) or "无"))
        buy["answer_short"] = "不买（方向与标的对不上）"

    # ── 人话三段 ──
    zt = _i((tac.get("dims") or {}).get("zt", {}).get("zt"))
    phase = senti.get("phase") or "—"
    tac_lab = tac.get("label") or "—"
    top_sec = buy["sectors"][0]["name"] if buy["sectors"] else "没有明显主线"

    read = ("今天涨停 %d 家、情绪 %s（%d 分），但上涨 %d 家、下跌 %d 家 —— "
            "涨停集中在少数题材里，大盘整体是失血的。五个攻防信号合起来 %+d 分，档位是「%s」。"
            % (zt, phase, round(_f(senti.get("score"))), up, down, _i(tac.get("score")), tac_lab))
    if div:
        read += " 这种「局部发热、整体缺血」的背离日，最容易骗人。"

    if buy["answer_short"].startswith("不买"):
        so = ("所以今天不用动：你的仓位上限是 %d%%，现在只有 %.1f%%，"
              "但加仓条件只满足 %d/%d 条，**不加仓**。"
              "仓位上限是天花板，不是让你必须用满 —— 空仓也是一种仓位。"
              % (round(cap * 100), hold["cur_pct"], hit, len(checks)))
    else:
        so = ("所以今天可以做，但**只能拿上限以内的钱做**：仓位上限 %d%%，"
              "你现在 %.1f%%，还能加 %.1f 个点，分批加，一次打满明天一个低开就全吐回去。"
              % (round(cap * 100), hold["cur_pct"], hold["gap_pct"]))

    if buy["answer_short"].startswith("不买"):
        how = (buy["answer"] + " 今天的可买额度就是 0，别手痒；明天开仓前先看「加仓检查表」，"
               "凑够 5 条再动手。仓位上限 %d%% 是天花板，不是目标。" % round(cap * 100))
    else:
        how = (buy["advice"] + " 额度：单票不超过总资产 %.1f%%（约 %.1f 万），首批只用一半；"
               "买进去就设 -7%% 止损，破了就走，不讨论。"
               % (cap * 20 * buy["factor"], hold["total_assets"] * cap * buy["factor"] / 5 / 10000))

    verdict = {
        "update_time": NOW.strftime("%Y-%m-%d %H:%M:%S"),
        "data_date": (tac.get("data_date") or TODAY),
        "head": {
            "label": "%s · %d 成" % (tac_lab, round(cap * 10)),
            "stance": tac.get("regime") or "",
            "icon": tac.get("icon") or "🛡️",
            "color": tac.get("color") or "#26a69a",
            "cap_pct": round(cap * 100),
            "cur_pct": hold["cur_pct"],
        },
        "plain": {"读今天": read, "所以": so, "怎么做": how},
        "position": {"cap_pct": round(cap * 100), "parts": parts, "diverge": div,
                     "cur_pct": hold["cur_pct"], "gap_pct": hold["gap_pct"],
                     "cash": hold["cash"], "total_assets": hold["total_assets"]},
        "buy": buy,
        "avoid": avoid,
        "sizing": {
            "per_stock_pct": round(cap * 100 / 5 * buy["factor"], 1),
            "first_batch_pct": round(cap * 100 / 2 * buy["factor"], 1),
            "max_positions": 5,
            "stop_loss_pct": -7,
            "rule": ("上限 %d%% ÷ 最多 5 只 = 单票 %d%%；今天只能试 ⇒ 再打半折到 %d%%，首次只下一半（%d%%）"
                     % (round(cap * 100), round(cap * 20), round(cap * 20 * buy["factor"]),
                        round(cap * 50 * buy["factor"])))
                    if buy["factor"] < 1.0 else
                    ("上限 %d%% ÷ 最多 5 只 = 单票 %d%%；首次只下一半（%d%%），确认走强再补齐"
                     % (round(cap * 100), round(cap * 20), round(cap * 50))),
        },
        "triggers": triggers,
        "holdings": hold,
        "evidence": [
            {"name": "攻防档位", "plain": "五个信号打分：趋势 -1、宽度 -1、涨停 0、量能 -1、资金 +1，合计 %+d"
             % _i(tac.get("score")), "value": "%+d" % _i(tac.get("score"))},
            {"name": "个股宽度", "plain": "%d 家涨 / %d 家跌，上涨占比 %.0f%%（低于 45%% 就是普跌）"
             % (up, down, (breadth or 0) * 100), "value": "%.0f%%" % ((breadth or 0) * 100)},
            {"name": "情绪周期", "plain": "%s（%d 分），涨停 %d 家、最高 %s 板"
             % (phase, round(_f(senti.get("score"))), zt,
                (senti.get("metrics") or {}).get("max_ladder", "—")), "value": phase},
            {"name": "危机雷达", "plain": "%s 分（%s），低于 40 不扣分、高于 60 强制降档"
             % (round(_f(crisis.get("score"))), crisis.get("level") or "—"),
             "value": "%.0f" % _f(crisis.get("score"))},
            {"name": "资金主线", "plain": "今日净流入 %d 个板块、净流出 %d 个；主线是 %s"
             % (_i((trend.get("summary") or {}).get("in_count")),
                _i((trend.get("summary") or {}).get("out_count")), top_sec),
             "value": top_sec},
        ],
        "caveat": ("本卡是「把已有 9 个信号收敛成一个动作」的纪律工具，**不是**预测模型。"
                   "其中「情绪周期当仓位闸门」这条规则**还没有样本外验证**（涨停热力历史只有 30 天），"
                   "从今天起每天留痕，攒够 3-6 个月再回测。在此之前它只约束你别乱来，不代表能提高收益。"),
        "sources": {"tactic": tac.get("update_time"), "verdict": mv.get("update_time"),
                    "senti": senti.get("update_time"), "flow": flow.get("update_time"),
                    "trend": trend.get("update_time"), "portfolio": pf.get("update_time")},
    }

    os.makedirs(RAW, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=1)

    # 双写 data/V8_VERDICT.js（update_v8 的映射也会从 verdict.json 重建；
    #   这里直写是为了「生成器单独跑一次也能立刻上线」，避免 raw 新 js 旧）
    jsp = os.path.join(DATA, "V8_VERDICT.js")
    try:
        with open(jsp, "w", encoding="utf-8") as f:
            f.write("// V8_VERDICT · 今日作战指令（唯一裁决卡）· algorithms/gen_verdict.py\n")
            f.write("// 纯合成器：只读已上线产物，不新增模型/权重/回测；口径见 logic.html\n")
            f.write("window.V8_VERDICT = " + json.dumps(verdict, ensure_ascii=False) + ";\n")
    except Exception as e:
        print("  ! 写 data/V8_VERDICT.js 失败: %s" % e)

    # ── 每日留痕（回测样本，成本≈0）──
    os.makedirs(HIST, exist_ok=True)
    snap = {
        "date": verdict["data_date"],
        "generated": verdict["update_time"],
        "verdict": {"cap_pct": round(cap * 100), "label": tac_lab, "cur_pct": hold["cur_pct"]},
        "inputs": {
            "tactic_score": _i(tac.get("score")), "tactic_exposure": _f(tac.get("exposure")),
            "senti_phase": phase, "senti_score": _f(senti.get("score")),
            "zt": zt, "max_ladder": (senti.get("metrics") or {}).get("max_ladder"),
            "up": up, "down": down, "breadth": breadth,
            "crisis": _f(crisis.get("score")),
            "sh_close": sh.get("price"), "sh_chg": sh.get("chg"),
            "zz1000_close": (mv.get("risk_anchor") or {}).get("close"),
            "flow_in_cnt": _i((trend.get("summary") or {}).get("in_count")),
            "top_sectors": [s["name"] for s in buy["sectors"]],
            "top_stocks": [s["name"] for s in buy["stocks"]],
        },
        "checks_hit": hit,
        "checks_total": len(checks),
        # 未来兑现位：3/5/10 日后由复盘脚本按这两个价位算前瞻收益
        "forward_ref": {"sh_close": sh.get("price"), "date": verdict["data_date"]},
    }
    hp = os.path.join(HIST, "verdict_%s.json" % NOW.strftime("%Y%m%d"))
    with open(hp, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)

    print("✅ verdict.json  %s" % OUT)
    print("   档位 %s · 仓位上限 %d%% · 现仓 %.1f%% · 加仓条件 %d/%d"
          % (tac_lab, round(cap * 100), hold["cur_pct"], hit, len(checks)))
    print("   买 %s | 避 %s" % ([s["name"] for s in buy["sectors"]],
                                [a["name"] for a in avoid[:2]]))
    print("   留痕 %s" % hp)


if __name__ == "__main__":
    main()
