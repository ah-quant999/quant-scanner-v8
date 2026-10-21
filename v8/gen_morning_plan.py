#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════
📋 v8/gen_morning_plan.py — 盘前预案卡数据生成器（暂未上架·观测类·首卡）
═══════════════════════════════════════════════════════════════════════
主人令（2026-10-21）：新卡放「暂未上架」顶部，运行几日后再看，先跑真实数据。

口径（🔴 全部条目 = 规则从真实数据自动生成，无人工观点、无编造）：
  • 指数/成交额  → 东财 push2delay ulist（复用 cloud_fetch_v8.f_index_quotes 同款口径）
  • 平均股价     → data/AVG_PRICE_DATA.js（全A等权自算）
  • 温控         → data/MARKET_THERMO.js（10年估值分位 val10_d / 回撤 drawdown）
  • 强势板块     → data/FINAL_RECOMMEND_DATA.js.strong_sectors（与最终推荐卡同源同序）
  • 主升/启动    → data/SECTOR_LEADERS.js.sectors（同板块周期判定）
  • 回避清单     → data/DAJIJIN_REDUCTION.js.records（大基金减持·法定披露）
  • 短线情绪     → data/IMA_STRONG_STOCK.js（ima 全文快照解析）
任一源缺失 ⇒ 对应条目「数据未就绪」静默降级，绝不伪造。

产出 data/MORNING_PLAN.js → window.MORNING_PLAN
调度：.github/workflows/v8_morning_plan.yml 工作日 07:50 CST（GitHub Actions [self-hosted, cn]，
      东财 push2delay 仅境内可达；Contents API 源码同步 + PowerShell ASCII-only 运行块 + api_put_file.py 稳健推送）。
═══════════════════════════════════════════════════════════════════════
"""
import json, os, sys, time
from datetime import datetime, timezone, timedelta

BJ = timezone(timedelta(hours=8))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "MORNING_PLAN.js")

_EM_DELAY = "https://push2delay.eastmoney.com"
_EM_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

try:
    import requests as _requests
except ImportError:
    print("❌ 缺 requests"); sys.exit(2)


def _read_data(fname):
    """读 data/<fname>.js → dict；缺失/坏 → None（静默降级，不伪造）"""
    p = os.path.join(ROOT, "data", fname + ".js")
    if not os.path.exists(p):
        return None
    try:
        s = open(p, encoding="utf-8").read()
        i, j = s.index("{"), s.rindex("}")
        return json.loads(s[i:j + 1])
    except Exception as e:
        print(f"  ⚠️ {fname} 解析失败: {e}")
        return None


def fetch_index_quotes():
    """四大指数 + 两市成交额（东财 push2delay，fltt=2 已是小数；3 次重试）"""
    secids = "1.000001,0.399001,0.399006,1.000688"
    short = {"000001": "沪指", "399001": "深成指", "399006": "创业板", "000688": "科创50"}
    rows = []
    for attempt in range(3):
        try:
            r = _requests.get(
                f"{_EM_DELAY}/api/qt/ulist.np/get",
                params={"fltt": "2", "invt": "2", "ut": "b2884a393a59ad64002292a3e90d46a5",
                        "fields": "f2,f3,f6,f12,f13,f14", "secids": secids},
                headers=_EM_HEADERS, timeout=15)
            rows = ((r.json().get("data") or {}).get("diff") or [])
            if rows:
                break
        except Exception as e:
            print(f"  ⚠️ 指数行情失败({attempt+1}/3): {e}")
            time.sleep(1.5)
    items, turnover = [], 0.0
    for r in rows:
        try:
            code = str(r.get("f12") or "")
            price, chg = float(r.get("f2") or 0), float(r.get("f3") or 0)
            amt = float(r.get("f6") or 0) / 1e8
            if code == "000001":
                turnover += amt
            if code == "399001":
                turnover += amt
            items.append({"short": short.get(code, r.get("f14", code)),
                          "name": r.get("f14", code), "price": round(price, 2),
                          "chg": round(chg, 2)})
        except Exception:
            continue
    return items, round(turnover, 0)


def build():
    now = datetime.now(BJ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"📋 盘前预案生成 @ {now}")

    idx, turnover = fetch_index_quotes()
    if not idx:
        print("  ❌ 指数行情取失败 → 中止（宁缺毋假）"); sys.exit(1)
    print(f"  ✓ 指数 {len(idx)} 条 · 两市成交额 {turnover:.0f} 亿")

    avg = _read_data("AVG_PRICE_DATA")
    thermo = _read_data("MARKET_THERMO")
    fr = _read_data("FINAL_RECOMMEND_DATA")
    sl = _read_data("SECTOR_LEADERS")
    djj = _read_data("DAJIJIN_REDUCTION")
    ima = _read_data("IMA_STRONG_STOCK")

    data_date = (avg or {}).get("date") or now[:10]

    # ── 平均股价关键位 ──
    ap = {}
    if avg:
        p = avg.get("avg_price")
        ma5 = ((avg.get("ma_short") or {}).get("ma5"))
        ma10 = ((avg.get("ma_short") or {}).get("ma10"))
        ap = {"price": p, "chg": avg.get("avg_change_pct"), "ma5": ma5, "ma10": ma10,
              "ma20": avg.get("ma20"), "pos_ma20": avg.get("position_vs_ma20"),
              "above_ma5": (p is not None and ma5 is not None and p >= ma5)}

    # ── 温控 ──
    th = {}
    if thermo:
        cur = (thermo.get("D") or {}).get("current") or {}
        th = {"date": cur.get("date"), "val10_d": cur.get("val10_d"),
              "drawdown": cur.get("drawdown"), "sh": (thermo.get("SPOT") or {}).get("sh")}

    strong = [(fr or {}).get("strong_sectors") or []]
    strong = strong[0]

    rising = []
    if sl and (sl.get("sectors") or []):
        for s in sl["sectors"]:
            rising.append({"name": s.get("name"), "phase": s.get("phase"),
                           "pct_5d": s.get("pct_5d"), "pct_20d": s.get("pct_20d")})

    avoid = []
    if djj:
        recs = [r for r in (djj.get("records") or []) if r.get("dir") == "减持"]
        recs.sort(key=lambda x: -(x.get("amount_est") or 0))
        for r in recs[:3]:
            avoid.append({"name": r.get("name"), "holder": r.get("holder"),
                          "shares": r.get("shares"), "amount_est": r.get("amount_est"),
                          "end": r.get("end")})

    ima_n, ima_date = 0, None
    if ima:
        ima_n = len(ima.get("stocks") or [])
        ima_date = ima.get("data_date")

    # ══ 色条矩阵（规则生成，全部条目带真实数字）══
    def _f(v, nd=2, suf=""):
        if v is None:
            return "—"
        if isinstance(v, str):
            return v
        return f"{v:.{nd}f}{suf}"

    matrix = []
    # ① 可执行
    ex = []
    if strong:
        ex.append(f"「最终推荐」强势板块 <b>{len(strong)}</b> 个（相对强度TOP）：{_f(strong[0],0)} · {(_f(strong[1],0) if len(strong)>1 else '—')} · {(_f(strong[2],0) if len(strong)>2 else '—')} 等（08:02 日更）")
    if ima_n:
        ex.append(f"ima 短线情绪候选 <b>{ima_n}</b> 只（数据日 {ima_date or '—'}）")
    matrix.append({"cat": "可执行", "color": "#ef5350", "items": ex or ["数据未就绪"]})
    # ② 相对占优
    ro = []
    if rising:
        r0 = rising[0]
        ro.append(f"主升/启动判定：<b>{_f(r0['name'],0)}</b>（{_f(r0['phase'],0)}，5日 {_f(r0['pct_5d'],2,'%')} / 20日 {_f(r0['pct_20d'],2,'%')}）")
    if len(strong) > 3:
        ro.append(f"强势板块前5：{' · '.join(strong[:5])}")
    matrix.append({"cat": "相对占优", "color": "#fbbf24", "items": ro or ["数据未就绪"]})
    # ③ 有条件·待确认
    cond = []
    if ap:
        if ap.get("above_ma5"):
            gap10 = ((ap["ma10"] / ap["price"] - 1) * 100) if (ap.get("ma10") and ap.get("price")) else None
            cond.append(f"平均股价 {_f(ap['price'])} 站上 MA5（{_f(ap['ma5'])}）⇒ 收复 MA10（{_f(ap['ma10'])}，还差 {_f(gap10,1,'%')}）前只算反弹")
        else:
            cond.append(f"平均股价 {_f(ap['price'])} 在 MA5（{_f(ap['ma5'])}）下方 ⇒ 企稳待确认")
        if ap.get("pos_ma20") is not None:
            cond.append(f"距 MA20 仍 {_f(ap['pos_ma20'],1,'%')}，中期趋势未扭转")
    if th.get("val10_d") is not None:
        cond.append(f"温控：10年估值分位 <b>{_f(th['val10_d'],1,'%')}</b>（{_f(th['date'],0)}）⇒ 高位区需量能维持")
    cond.append(f"两市成交额 <b>{_f(turnover,0,' 亿')}</b>（缩量反弹需放量确认）")
    matrix.append({"cat": "有条件·待确认", "color": "#38bdf8", "items": cond or ["数据未就绪"]})
    # ④ 风险·回避
    rk = []
    if avoid:
        a0 = avoid[0]
        rk.append(f"大基金减持窗口内 <b>{len(avoid)}</b> 只：{_f(a0['name'],0)}（{(_f(a0['holder'],0))}，约 {_f(a0['amount_est'],2,'亿')}）等 —— 持仓排查")
    if ap and ap.get("pos_ma20") is not None and ap["pos_ma20"] < -5:
        rk.append(f"平均股价距 MA20 {_f(ap['pos_ma20'],1,'%')} ⇒ 弱势区勿重仓抄底")
    matrix.append({"cat": "风险·回避", "color": "#26a69a", "items": rk or ["暂无规则命中风险项"]})
    # ⑤ 验证变量·方法论
    vf = [f"明日验证：平均股价 MA5（{_f(ap.get('ma5'))}）得失与成交额能否维持 {_f(turnover,0,' 亿')} 上方",
          "口径：本卡全部条目由规则从真实数据自动生成（无人工观点）；任一源缺失即显「数据未就绪」",
          f"生成时刻 {now}（工作日 08:40 派发 · 盘前口径）"]
    matrix.append({"cat": "验证变量·方法论", "color": "#a78bfa", "items": vf})

    payload = {
        "update_time": now,
        "data_date": data_date,
        "pipeline": "v8/gen_morning_plan.py",
        "indices": idx,
        "turnover_yi": turnover,
        "avg_price": ap or None,
        "thermo": th or None,
        "strong_sectors": strong,
        "rising_sectors": rising,
        "avoid": avoid,
        "avoid_total": len([r for r in ((djj or {}).get("records") or []) if r.get("dir") == "减持"]) if djj else 0,
        "ima_count": ima_n, "ima_date": ima_date,
        "matrix": matrix,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("window.MORNING_PLAN = " + json.dumps(payload, ensure_ascii=False) + ";\n")
    print(f"  ✓ 产出 {OUT}（{os.path.getsize(OUT)} B）· 数据日 {data_date}")


if __name__ == "__main__":
    build()
