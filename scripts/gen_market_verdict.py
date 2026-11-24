# -*- coding: utf-8 -*-
"""全站综合解析引擎（2026-11-24 主人拍板：升级综合研判卡 + 全套合成分析）

主人诉求原话：「全站数据太多了，有没有一个综合的给我准确分析的解析」——
现有综合研判卡只是 6 源等权并排数数（看多1·看空3·中性2），缺的不是数据是分析。

本生成器做四层事：
  ① 信号采集 15 源（全部现成管线/上游产物，零新增抓取）
  ② 加权合成（危机雷达一票否决权保留，环境/趋势/资金权重最高）
  ③ 交叉验证：自动检测信号矛盾（资金vs趋势背离 / 放量下跌 / 缩量涨停 / 档位vs综合分不一致
     / 共识乐观但风险升温 / 估值便宜但趋势空）→ 矛盾本身就是最值钱的信息
  ④ 边际变化：与昨日逐项对比（自建 raw_data/market_verdict_history.json）+ 自然语言叙事
     （主导逻辑 + 矛盾句 + 边际句 + 姿态与确认条件），非模板套话拼接。

信号与权重（vote ∈ −2..+2；权重 Σ≈10）：
  危机雷达 2.0（≥60 → −2 且一票否决强制守；40~59 → −1）
  攻防档位（五信号合成）1.5：攻 +1 / 守 −1 / 观 0
  上证主力资金 1.5：当日净额与5日累计同向 → ±1，分歧 0
  涨停情绪 1.0（含炸板折减，复用攻防档位 dims）
  ETF量能配速 0.8（陈旧如实 0）
  共振胜率超额 0.5（T+5 excess_avg%）
  隔夜美股 0.5 / 盘前共识 0.5 / 股债性价比(PE百分位) 0.5
  国债期货跷跷板 0.3 / 个股避雷 0.3 / 大基金减持 0.2

合成：score_raw=Σ vote·w → norm=score_raw/有效权重 ∈[−2,+2]
      norm ≥ +0.30 攻(0.95) / ≤ −0.25 守(0.30) / 其余 观(0.50)；危机 ≥60 一票否决。

产出：data/MARKET_VERDICT.js（window.MARKET_VERDICT）
      ⚠️ 命名纪律：新增 window 变量前必须 grep index.html 注入区查占用
      （MARKET_REGIME 撞名覆盖事故 2026-11-24 的教训）；MARKET_VERDICT 已核未占用。
接线：update_v8 run_experiment_cards，gen_market_regime 之后跑（复用其 TACTIC 产物）。
"""
import json, os, re, datetime

OUT = "data/MARKET_VERDICT.js"
HIST = "raw_data/market_verdict_history.json"
NORM_ATTACK, NORM_DEFENSE = 0.30, -0.25     # 归一化档位分数线
CRISIS_FORCE = 60                            # 一票否决线（与 gen_market_regime 一致）
VAL_CHEAP, VAL_EXPENSIVE = 30, 70            # PE 百分位便宜/贵分界
AVOID_HEAVY = 10                             # 避雷预警重压线
RES_EXCESS_BAD = -2.0                        # 共振超额显著为负

STANCE = {"attack": dict(label="攻", icon="⚔️", color="#ef5350", exposure=0.95),
          "watch":  dict(label="观", icon="👁️", color="#ffd024", exposure=0.50),
          "defense": dict(label="守", icon="🛡️", color="#26a69a", exposure=0.30)}


def bj_now():
    return datetime.datetime.utcnow() + datetime.timedelta(hours=8)


def _load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _load_js_obj(path, varname):
    """从 data/*.js 提取 window.VAR = {...} 的 json（括号配对，容忍前缀注释）。"""
    try:
        with open(path, encoding="utf-8") as f:
            s = f.read()
        i = s.index("window." + varname)
        i = s.index("{", i)
        depth = 0
        for j in range(i, len(s)):
            c = s[j]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(s[i:j + 1])
    except Exception:
        pass
    return None


def _sign(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)


# ─────────────────────────── 15 源采集 ───────────────────────────

def sig_crisis():
    d = _load("raw_data/crisis_data.json")
    if not d:
        return 0, 2.0, False, "危机雷达：数据缺席", {}
    score = float(d.get("score") or 0)
    level = d.get("level") or ""
    if score >= CRISIS_FORCE:
        v, txt = -2, f"危机雷达 {score:.0f}（{level}）→ 一票否决，强制守"
    elif score >= 40:
        v, txt = -1, f"危机雷达 {score:.0f}（{level}）→ 权重压分"
    else:
        v, txt = 0, f"危机雷达 {score:.0f}（{level}）→ 无压分"
    return v, 2.0, True, txt, dict(radar=score, level=level)


def sig_tactic():
    d = _load_js_obj("data/MARKET_TACTIC.js", "MARKET_TACTIC")
    if not d:
        return 0, 1.5, False, "攻防档位：缺席（上游未跑）", {}
    reg = d.get("regime") or "watch"
    v = 1 if reg == "attack" else (-1 if reg == "defense" else 0)
    lbl = d.get("label") or reg
    dims = d.get("dims") or {}
    return v, 1.5, True, f"攻防档位（五信号合成）={lbl}（score {d.get('score')}）", dict(
        regime=reg, label=lbl, dims=dims, tactic_score=d.get("score"),
        forced=d.get("forced"))


def sig_sh_money():
    """上证主力资金：当日净额 + 近5日累计 + 边际（5日累计 vs 前5日累计）。"""
    d = _load("raw_data/market_fund_flow_data.json")
    daily = (d or {}).get("daily") or []
    if len(daily) < 11:
        return 0, 1.5, False, "上证主力资金：序列不足", {}
    rows = sorted(daily, key=lambda r: str(r.get("date") or ""))[-11:]
    today_net = float(rows[-1].get("net_yi") or 0)
    net5 = sum(float(r.get("net_yi") or 0) for r in rows[-5:])
    net5_prev = sum(float(r.get("net_yi") or 0) for r in rows[-10:-5])
    st, s5, s5p = _sign(today_net), _sign(net5), _sign(net5 - net5_prev)
    if st == s5 == 1:
        v = 1
    elif st == s5 == -1:
        v = -1
    else:
        v = 0
    q = {1: "资金净流入", 0: "资金方向分歧", -1: "资金净流出"}[v]
    marg = "改善" if s5p > 0 else ("恶化" if s5p < 0 else "持平")
    txt = (f"上证主力：当日 {today_net:+.0f} 亿 / 5日累计 {net5:+.0f} 亿"
           f"（较前5日 {marg}）→ {q}")
    return v, 1.5, True, txt, dict(today=round(today_net, 1), net5=round(net5, 1),
                                   net5_prev=round(net5_prev, 1), margin5=s5p)


def sig_zt():
    t = _load_js_obj("data/MARKET_TACTIC.js", "MARKET_TACTIC")
    z = ((t or {}).get("dims") or {}).get("zt") or {}
    if not z:
        return 0, 1.0, False, "涨停情绪：复用源缺席", {}
    v = z.get("score") or 0
    return v, 1.0, True, f"涨停情绪：今日 {z.get('zt')} 家（均值倍 {z.get('zt_ratio')}）", dict(z)


def sig_pace():
    t = _load_js_obj("data/MARKET_TACTIC.js", "MARKET_TACTIC")
    p = ((t or {}).get("dims") or {}).get("volume") or {}
    if not p or not p.get("available"):
        return 0, 0.8, False, "ETF量能配速：未刷新/陈旧 → 不计分（如实）", dict(available=False)
    v = p.get("score") or 0
    return v, 0.8, True, f"ETF量能：放量 {p.get('hot')} / 缩量 {p.get('cool')}", dict(p)


def sig_resonance():
    d = _load("raw_data/resonance_track.json")
    t5 = ((d or {}).get("per_horizon") or {}).get("T+5") or {}
    if not t5:
        return 0, 0.5, False, "共振胜率：缺席", {}
    ex = t5.get("excess_avg%")
    win = t5.get("win%")
    if ex is None:
        return 0, 0.5, False, "共振胜率：超额字段缺席", {}
    v = 1 if ex > 0 else (-1 if ex < RES_EXCESS_BAD else 0)
    q = {1: "跑赢基准", 0: "略输基准", -1: "显著跑输基准"}[v]
    return v, 0.5, True, f"共振信号 T+5 胜率 {win}%、超额 {ex:+.1f}pp → {q}", dict(
        win=win, excess=ex, mature=t5.get("mature"))


def sig_overnight_us():
    d = _load_js_obj("data/JUDGMENT_DATA.js", "JUDGMENT_DATA")
    us = (d or {}).get("us") or ""
    if not us:
        return 0, 0.5, False, "隔夜美股：缺席", {}
    v = -1 if ("跌" in us or "下挫" in us) else (1 if ("涨" in us or "上涨" in us) else 0)
    return v, 0.5, True, f"隔夜美股：{us[:40]}", dict(us=us[:60])


def sig_judgment():
    d = _load_js_obj("data/JUDGMENT_DATA.js", "JUDGMENT_DATA")
    vd = (d or {}).get("verdict") or ""
    if not vd:
        return 0, 0.5, False, "盘前共识：缺席", {}
    if "偏空" in vd:
        v = -1
    elif "偏多" in vd or "偏强" in vd:
        v = 1
    else:
        v = 0
    return v, 0.5, True, f"盘前共识：{vd[:40]}", dict(verdict=vd[:60])


def sig_valuation():
    d = _load_js_obj("data/EQBOND_ATTRACTION.js", "EQBOND_ATTRACTION")
    pe = (d or {}).get("pe_pct")
    if pe is None:
        return 0, 0.5, False, "股债性价比：缺席", {}
    if pe < VAL_CHEAP:
        v = 1
    elif pe > VAL_EXPENSIVE:
        v = -1
    else:
        v = 0
    q = {1: "估值便宜（安全垫厚）", 0: "估值中性区", -1: "估值偏贵"}[v]
    return v, 0.5, True, f"沪深300 PE 百分位 {pe:.0f}% → {q}", dict(pe_pct=pe, pb_pct=(d or {}).get("pb_pct"))


def sig_bond():
    d = _load_js_obj("data/BOND_FUTURES.js", "BOND_FUTURES")
    jd = (d or {}).get("judgment") or {}
    level = jd.get("level") or ""
    if not level:
        return 0, 0.3, False, "国债期货：缺席", {}
    if "下行" in level:
        v = 1
    elif "上行" in level:
        v = -1
    else:
        v = 0
    return v, 0.3, True, f"国债期货：{level}（长端 {jd.get('long_chg')}%）→ 权益{'偏暖' if v>0 else ('承压' if v<0 else '中性')}", dict(level=level, spread=jd.get("spread"))


def sig_avoid():
    d = _load_js_obj("data/INVEST_AVOID.js", "INVEST_AVOID")
    if not d:
        return 0, 0.3, False, "个股避雷：缺席", {}
    dj = len(((d.get("dajijin") or {}).get("records")) or [])
    susp = len(((d.get("suspension") or {}).get("stocks")) or [])
    total = dj + susp
    v = -1 if total >= AVOID_HEAVY else 0
    return v, 0.3, True, f"个股避雷：预警 {total} 只（减持 {dj}+停牌 {susp}）", dict(dj=dj, susp=susp, total=total)


def sig_dajijin():
    d = _load_js_obj("data/INVEST_AVOID.js", "INVEST_AVOID")
    recs = ((d or {}).get("dajijin") or {}).get("records") or []
    if not recs:
        return 0, 0.2, False, "大基金：无近期记录", {}
    # 近 7 个自然日内有减持动作才算
    import datetime as _dt
    now = bj_now()
    recent = 0
    for r in recs:
        ds = str(r.get("date") or r.get("trade_date") or "")
        m = re.search(r"(\d{4})[-/年]?(\d{1,2})[-/月]?", ds)
        if m:
            try:
                dt = _dt.date(int(m.group(1)), int(m.group(2)), 1)
                if (now.date() - dt).days <= 37:
                    recent += 1
            except Exception:
                pass
    v = -1 if recent else 0
    return v, 0.2, True, f"大基金：近期记录 {recent} 条（120日窗口共 {len(recs)} 条）", dict(recent=recent, total=len(recs))


# ─────────────────────────── 边际历史 ───────────────────────────

def _hist_load():
    d = _load(HIST)
    return d if isinstance(d, dict) and isinstance(d.get("records"), list) else {"records": []}


def _hist_append(rec):
    hist = _hist_load()
    recs = [r for r in hist["records"] if r.get("date") != rec["date"]]
    recs.append(rec)
    recs = recs[-120:]
    os.makedirs("raw_data", exist_ok=True)
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump({"records": recs}, f, ensure_ascii=False, indent=1)


def _margins(today_rec, hist):
    """与最近一条非今日记录逐项对比。"""
    prev = None
    for r in reversed(hist["records"]):
        if r.get("date") != today_rec["date"]:
            prev = r
            break
    if not prev:
        return None, []
    out = []
    pairs = [("危机分", "crisis", "lower_better"),
             ("涨停家数", "zt", "higher_better"),
             ("上证5日资金(亿)", "sh_net5", "higher_better"),
             ("攻防档位分", "tactic_score", "higher_better"),
             ("ETF放量数", "pace_hot", "higher_better"),
             ("共振T+5胜率", "res_win", "higher_better")]
    for name, key, sense in pairs:
        a, b = prev.get(key), today_rec.get(key)
        if a is None or b is None:
            continue
        d = round(b - a, 1)
        if d == 0:
            tag = "flat"
            dtxt = "持平"
        else:
            good = (d > 0) if sense == "higher_better" else (d < 0)
            tag = "better" if good else "worse"
            dtxt = f"{a}→{b}（{'+' if d>0 else ''}{d}）"
        out.append(dict(name=name, prev=a, cur=b, delta=d, tag=tag, txt=dtxt))
    return prev.get("stance"), out


# ─────────────────────────── 矛盾检测 ───────────────────────────

def _conflicts(sigs, stance):
    out = []

    def V(n):
        return sigs.get(n, {}).get("vote")

    def A(n):
        return sigs.get(n, {}).get("available")

    # ① 资金 vs 趋势
    if A("sh_money") and A("tactic"):
        tr = (((sigs["tactic"].get("detail") or {}).get("dims") or {}).get("trend") or {}).get("score")
        if tr is not None and _sign(V("sh_money") or 0) * _sign(tr) == -1:
            if V("sh_money") == 1:
                out.append(dict(type="lead", desc="资金与趋势背离：趋势仍空但资金先动——资金常领先价格，观察是否为左侧布局，也可能是反弹诱多，以 5 日资金持续性裁决"))
            else:
                out.append(dict(type="risk", desc="资金与趋势背离：趋势尚可但主力资金持续流出——警惕资金先撤的顶部信号"))
    # ② 量价矛盾
    if A("pace") and A("tactic"):
        tr = (((sigs["tactic"].get("detail") or {}).get("dims") or {}).get("trend") or {}).get("score")
        zt = (((sigs["tactic"].get("detail") or {}).get("dims") or {}).get("zt") or {}).get("score")
        if V("pace") == 1 and tr == -1:
            out.append(dict(type="risk", desc="放量下跌：量能超前但趋势空头——派发嫌疑大于承接，反弹遇量不涨要减仓"))
        if V("pace") == -1 and (zt == 1):
            out.append(dict(type="risk", desc="缩量涨停潮：情绪热但量能收缩——接力资金不足，连板梯队脆弱性高"))
    # ③ 档位 vs 综合分不一致
    reg = ((sigs.get("tactic") or {}).get("detail") or {}).get("regime")
    if reg and stance and reg != stance:
        out.append(dict(type="diverge", desc=f"档位与综合分不一致：五信号档位={ {'attack':'攻','watch':'观','defense':'守'}.get(reg,reg)}，全站综合={STANCE[stance]['label']}——其余源（估值/资金/风险）与短线五信号看法相左，说明市场处在风格切换带，等一边走出 2-3 日趋势再跟"))
    # ④ 共识乐观但危机升温
    if V("judgment") == 1 and A("crisis") and (sigs["crisis"]["detail"] or {}).get("radar", 0) >= 40:
        out.append(dict(type="risk", desc="共识乐观但风险雷达升温——盘前共识只看盘面，危机雷达看宏观/海外，两者打架时以危机雷达优先"))
    # ⑤ 估值便宜但趋势空
    if V("valuation") == 1 and A("tactic"):
        tr = (((sigs["tactic"].get("detail") or {}).get("dims") or {}).get("trend") or {}).get("score")
        if tr == -1:
            out.append(dict(type="lead", desc="左侧区域：估值百分位已便宜但趋势仍空——长线资金可分批、短线资金继续等右侧确认"))
    return out


# ─────────────────────────── 叙事生成 ───────────────────────────

def _narrative(stance, sigs, conflicts, margins, prev_stance):
    S = STANCE[stance]
    # 主导逻辑：挑权重最大的空方与多方源
    neg = sorted([s for s in sigs.values() if s["available"] and s["vote"] < 0],
                 key=lambda s: (s["vote"] * s["weight"]))
    pos = sorted([s for s in sigs.values() if s["available"] and s["vote"] > 0],
                 key=lambda s: (-s["vote"] * s["weight"]))
    neg_txt = "、".join(s["name"] for s in neg[:3]) or "无"
    pos_txt = "、".join(s["name"] for s in pos[:3]) or "无"
    head = {
        "defense": f"空方主导逻辑是「{neg_txt}」，多方仅剩「{pos_txt}」。",
        "attack":  f"多方主导逻辑是「{pos_txt}」，空方仅剩「{neg_txt}」。",
        "watch":   f"多方（{pos_txt}）与空方（{neg_txt}）势均力敌，方向未选择。",
    }[stance]
    # 矛盾句
    lead = [c["desc"] for c in conflicts if c["type"] in ("lead", "diverge")]
    risk = [c["desc"] for c in conflicts if c["type"] == "risk"]
    mid = ""
    if risk:
        mid += "⚠️ " + risk[0] + "。"
    if lead:
        mid += "💡 " + lead[0] + "。"
    # 边际句
    tail = ""
    if margins:
        worse = [m["name"] for m in margins if m["tag"] == "worse"]
        better = [m["name"] for m in margins if m["tag"] == "better"]
        parts = []
        if worse:
            parts.append("较昨日恶化：" + "、".join(worse))
        if better:
            parts.append("好转：" + "、".join(better))
        if parts:
            tail += "边际变化——" + "；".join(parts) + "。"
    # 姿态 + 确认条件
    stance_txt = f"综合姿态：{S['icon']} {S['label']}（参考仓位 {S['exposure']:.2f}）。"
    watch_txt = {
        "defense": "转观确认条件：上证主力资金 5 日累计转正，或涨停家数回到近 10 日均值上方且炸板率降回 40% 以内。",
        "watch":   "选方向确认条件：上证主力资金连续 2 日净流入 + 涨停梯队不塌（今日家数不低于昨日），则向攻靠拢；主力再度放量流出则向守降档。",
        "attack":  "转守警戒条件：上证主力资金单日流出超 300 亿，或炸板率跳升超 50%，或危机雷达突破 60。",
    }[stance]
    if prev_stance and prev_stance != stance:
        tail += f"档位较昨日从「{ {'attack':'攻','watch':'观','defense':'守'}.get(prev_stance, prev_stance)}」调至「{S['label']}」。"
    # 🔴 2026-11-24 主人令「解析不要挤一行，一条一行」：narrative_lines 逐条分行输出，
    #   ⚠️/💡 矛盾句不进 lines（前端 conflicts 区已逐行渲染，避免重复）；narrative 保持整串兼容旧前端。
    lines = [head]
    if tail:
        lines.append(tail)
    lines.append(stance_txt)
    lines.append(watch_txt)
    return head + mid + tail + stance_txt + watch_txt, lines


# ─────────────────────────── 结构化风险位 ───────────────────────────
# 📍 2026-11-24 主人拍板（雪球敲入带锚点）·按「研判层零成本」轻量落地：
#    静态锚点写进研判生成器（v8 硬编码表先例如日历），不动数据链、不加 fetcher。
#    定位纪律：只做解析参考，不投票、不改档位判定——档位仍由 v8 自身量价+资金数据说话
#    （口径松绑令：参考不封口）。
#    机制（公开共识）：跌破雪球敲入线 → 券商对冲盘（IC 空单+卖成分股）机械性加压，
#    下行自我加速（反射性）。点位=券商金工测算转述口径（主人微信截图，未核研报原文），
#    故 caliber 如实标注可信度。
#    数据源：raw_data/volatility.json（baostock 日K·盘前 05:30 更新=最近一交易日收盘；
#    该文件 git 内随链更新，云端 checkout 自带，零新增抓取）。缺失 ⇒ 本条不产出，不冒充。
SNOWBALL_BAND_1 = (5600.0, 5800.0)   # 第一档：近期新发雪球敲入线集中区
SNOWBALL_BAND_2 = (5300.0, 5400.0)   # 第二档：更深一层集中敲入带


def _risk_anchor():
    """中证1000 × 雪球敲入带定位。返回 None=数据缺席（调用方跳过本条，不冒充）。"""
    d = _load("raw_data/volatility.json") or _load_js_obj("data/VOLATILITY.js", "VOLATILITY")
    if not d:
        return None
    csi = next((x for x in (d.get("indices") or []) if x.get("code") == "000852"), None)
    if not csi or csi.get("close") is None:
        return None
    close = float(csi["close"])
    lo1, hi1 = SNOWBALL_BAND_1
    lo2, hi2 = SNOWBALL_BAND_2
    if close < lo2:
        pos = "第二档敲入带（5300-5400）下方"
        risk = "对冲加压已穿越两档敲入带，需防连环敲入后的对冲踩踏；反弹至 5300-5400 带或遇解盘抛压"
    elif close <= hi2:
        pos = "第二档雪球集中敲入带（5300-5400）内"
        risk = "更深层集中敲入区，下行风险显著放大"
    elif close < lo1:
        pos = "两档敲入带之间（5400-5600）"
        risk = "下方 5600=第一档敲入带下沿警戒线，跌破则下行风险机械性放大"
    elif close <= hi1:
        pct = (close - lo1) / lo1 * 100
        pos = f"第一档雪球集中敲入带（5600-5800）内、距下沿 +{pct:.1f}%"
        risk = "跌破 5600 将触发券商对冲盘机械性加压、下行风险明显放大——此处破位与否，是「派发嫌疑」要不要升级为真下行风险的关键独立判据"
    else:
        pct = (close - hi1) / hi1 * 100
        pos = f"第一档敲入带上沿（5800）上方 +{pct:.1f}%"
        risk = "雪球敲入压力暂不构成压制；若回落进 5600-5800 带内需转入警戒"
    return dict(code="000852", name="中证1000", close=close,
                data_update=str(d.get("update_date") or d.get("update_time") or ""),
                band1=list(SNOWBALL_BAND_1), band2=list(SNOWBALL_BAND_2),
                position=pos, risk_note=risk,
                caliber="静态锚点：雪球敲入集中带（券商金工测算·转述口径，未核研报原文）；盘前更新=最近收盘，盘中击穿以实时行情为准；压力位参考，不投票、不改档位判定")


# ─────────────────────────── 主流程 ───────────────────────────

def main():
    today = bj_now().strftime("%Y-%m-%d")
    builders = [
        ("crisis", sig_crisis, "危机雷达"),
        ("tactic", sig_tactic, "攻防档位·五信号"),
        ("sh_money", sig_sh_money, "上证主力资金"),
        ("zt", sig_zt, "涨停情绪"),
        ("pace", sig_pace, "ETF量能配速"),
        ("resonance", sig_resonance, "共振胜率超额"),
        ("overnight_us", sig_overnight_us, "隔夜美股"),
        ("judgment", sig_judgment, "盘前共识"),
        ("valuation", sig_valuation, "股债性价比"),
        ("bond", sig_bond, "国债期货跷跷板"),
        ("avoid", sig_avoid, "个股避雷"),
        ("dajijin", sig_dajijin, "大基金减持"),
    ]
    sigs = {}
    score_raw = 0.0
    weight_used = 0.0
    forced = False
    radar = 0.0
    for key, fn, name in builders:
        try:
            v, w, avail, txt, det = fn()
        except Exception as e:
            v, w, avail, txt, det = 0, getattr(fn, "weight", 0.3), False, f"{name}：计算异常 {e}", {}
        sigs[key] = dict(name=name, vote=v, weight=w, available=avail, txt=txt, detail=det)
        if avail:
            score_raw += v * w
            weight_used += w
            if key == "crisis":
                radar = det.get("radar") or 0
                if radar >= CRISIS_FORCE:
                    forced = True
            if key == "tactic":
                forced = forced or bool(det.get("forced"))
    norm = round(score_raw / weight_used, 3) if weight_used > 0 else 0.0

    if forced or norm <= NORM_DEFENSE:
        stance = "defense"
    elif norm >= NORM_ATTACK:
        stance = "attack"
    else:
        stance = "watch"
    S = STANCE[stance]

    # 边际历史（先对比后写入）
    t = sigs["tactic"]["detail"] if sigs["tactic"]["available"] else {}
    p = sigs["pace"]["detail"] if sigs["pace"]["available"] else {}
    rec = dict(date=today, stance=stance, score_norm=norm,
               crisis=round(radar, 1),
               zt=(t.get("dims") or {}).get("zt", {}).get("zt") if t else None,
               zt_ratio=(t.get("dims") or {}).get("zt", {}).get("zt_ratio") if t else None,
               sh_net5=(sigs["sh_money"]["detail"] or {}).get("net5") if sigs["sh_money"]["available"] else None,
               tactic_score=t.get("tactic_score") if t else None,
               pace_hot=p.get("hot") if p else None,
               pace_cool=p.get("cool") if p else None,
               res_win=(sigs["resonance"]["detail"] or {}).get("win"))
    prev_stance, margins = _margins(rec, _hist_load())
    _hist_append(rec)

    conflicts = _conflicts(sigs, stance)
    narrative, narrative_lines = _narrative(stance, sigs, conflicts, margins, prev_stance)

    # 📍 结构化风险位（2026-11-24 主人拍板）：只进解析行（AI速览同步），不参与投票/档位。
    anchor = _risk_anchor()
    if anchor:
        _aline = (f"📍 结构化风险位：中证1000 最近收盘 {anchor['close']:.0f}（{anchor['data_update']} 盘前更新）"
                  f"{anchor['position']}——{anchor['risk_note']}。")
        narrative_lines.append(_aline)
        narrative += _aline

    out = dict(
        update_time=bj_now().strftime("%Y-%m-%d %H:%M:%S"),
        data_date=today,
        stance=stance, label=S["label"], icon=S["icon"],
        color=S["color"], exposure=S["exposure"],
        score_norm=norm, score_raw=round(score_raw, 2),
        weight_used=round(weight_used, 1),
        forced=forced, radar=radar,
        dominant=dict(up=[s["name"] for s in sorted(
            [s for s in sigs.values() if s["available"] and s["vote"] > 0],
            key=lambda s: -s["vote"] * s["weight"])[:3]],
            down=[s["name"] for s in sorted(
            [s for s in sigs.values() if s["available"] and s["vote"] < 0],
            key=lambda s: s["vote"] * s["weight"])[:3]]),
        conflicts=conflicts,
        margins=margins or [],
        risk_anchor=anchor,
        prev_stance=prev_stance,
        narrative=narrative,
        narrative_lines=narrative_lines,
        signals=[dict(name=s["name"], vote=s["vote"], weight=s["weight"],
                      available=s["available"], txt=s["txt"])
                 for s in sigs.values()],
        thresholds=dict(norm=[NORM_DEFENSE, NORM_ATTACK], crisis_force=CRISIS_FORCE,
                        val=[VAL_CHEAP, VAL_EXPENSIVE], avoid_heavy=AVOID_HEAVY),
        note="全站综合解析：15源加权合成+交叉矛盾检测+边际变化；守=控仓等确认，攻=顺势，观=分歧观望；口径见逻辑详解页；观测参考非交易指令",
    )
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("// MARKET_VERDICT · 全站综合解析（15源加权+矛盾检测+边际变化）· gen_market_verdict.py\n")
        f.write("// 口径详情见 logic.html 登记条目\n")
        f.write("window.MARKET_VERDICT = " + json.dumps(out, ensure_ascii=False) + ";\n")
    print(f"MARKET_VERDICT: {S['label']}({stance}, {S['exposure']}) norm={norm} "
          f"raw={score_raw:.1f}/w={weight_used:.1f} forced={forced} "
          f"conflicts={len(conflicts)} margins={len(margins or [])} "
          f"| sigs=" + ",".join(f"{k}:{sigs[k]['vote']}" for k in sigs))


if __name__ == "__main__":
    main()
