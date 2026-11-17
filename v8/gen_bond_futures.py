#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
国债期货 · 利率预期罗盘生成器（2026-11-17 主人令「TL 要接入，结合给判断」）
====================================================================
背景：主人问 TL（30年国债期货，中金所代码 TL）是什么、对 v8 有何观测作用。
  TL = 30年期国债期货，是长端利率/避险情绪的代理。债期走强(价涨)=收益率下行=
  宽松/避险预期升温 → 权益风险偏好趋于谨慎（股债跷跷板）。

数据源：新浪 nf_ 实时期货接口（hq.sinajs.cn，GBK，中国IP可达，实测 15:15 到账）
  nf_TL0=30年 / nf_T0=10年 / nf_TF0=5年 / nf_TS0=2年（连续合约）
字段索引（实测 2026-11-17）：
  [3]最新 [4]成交量 [6]持仓 [13]昨结算 [14]昨收盘 [36]日期 [37]时间 [48]均价 [49]名称

产出：data/BOND_FUTURES.js → window.BOND_FUTURES
  含四品种实时价/涨跌 + 期限结构判断（牛陡/熊平/牛平/熊陡）+ 股债跷跷板研判。
  红涨绿跌由前端按 chg 正负处理；本脚本只产出客观数值与判断文本。

刷新：接 v8_bond_futures.yml，盘中每30分 [self-hosted, cn]（中国IP，新浪可达）。
运行：python v8/gen_bond_futures.py [--no-write]
"""
from __future__ import annotations
import json, re, sys, os, datetime, urllib.request

SINA_URL = "https://hq.sinajs.cn/list="
VARIETIES = [
    ("TL", "nf_TL0", "30年期", 30),
    ("T",  "nf_T0",  "10年期", 10),
    ("TF", "nf_TF0", "5年期",  5),
    ("TS", "nf_TS0", "2年期",  2),
]
UA = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.sina.com.cn/"}


def _bj_now():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)


def fetch_all():
    codes = ",".join(v[1] for v in VARIETIES)
    req = urllib.request.Request(SINA_URL + codes, headers=UA)
    raw = urllib.request.urlopen(req, timeout=15).read().decode("gbk", "replace")
    by_code = {}
    for line in raw.splitlines():
        m = re.match(r'\s*var hq_str_(nf_\w+)="([^"]*)"', line)
        if m:
            by_code[m.group(1)] = m.group(2).split(",")
    return by_code


def build_items(by_code):
    items = []
    tick = None
    for var, code, label, tenor in VARIETIES:
        p = by_code.get(code)
        if not p or len(p) < 15:
            print("  ⚠️ %s 无数据，跳过" % var, file=sys.stderr)
            continue
        try:
            last = float(p[3])
            pre_settle = float(p[13])
            pre_close = float(p[14])
            vol = int(float(p[4]))
            oi = int(float(p[6]))
            avg = float(p[48]) if len(p) > 48 and p[48] else None
        except (TypeError, ValueError):
            print("  ⚠️ %s 字段解析失败，跳过" % var, file=sys.stderr)
            continue
        if last <= 0 or pre_settle <= 0:
            continue
        chg = (last - pre_settle) / pre_settle * 100
        d = p[36] if len(p) > 36 else ""
        t = p[37] if len(p) > 37 else ""
        if t and (tick is None or t > tick):
            tick = t
        items.append({
            "variety": var, "code": code, "label": label, "tenor": tenor,
            "name": (p[49] if len(p) > 49 and p[49] else label + "国债期货连续"),
            "last": round(last, 3), "pre_settle": round(pre_settle, 3),
            "pre_close": round(pre_close, 3), "chg": round(chg, 3),
            "volume": vol, "open_interest": oi,
            "avg": round(avg, 3) if avg else None,
            "date": d, "ticktime": t,
        })
        print("  ✅ %s(%s) %.3f 昨结 %.3f 涨 %+.2f%% 持仓 %d tick=%s" %
              (var, label, last, pre_settle, chg, oi, t))
    return items, tick


def judge(items):
    """期限结构 + 股债跷跷板研判（客观规则，不含编造数据）。"""
    by = {x["variety"]: x for x in items}
    if "TL" not in by or "TS" not in by:
        return {"level": "数据不足", "curve": "—", "equity": "—", "detail": "TL/TS 缺失，无法判断期限结构"}
    long_chg = by["TL"]["chg"]      # 长端(30Y)
    short_chg = by["TS"]["chg"]     # 短端(2Y)
    spread = round(long_chg - short_chg, 3)  # 长短端涨跌差：正=长端更强=曲线牛陡

    # 利差方向：长端涨得多于短端 → 长端收益率降更多 → 曲线牛陡(宽松/避险预期)
    if spread >= 0.30:
        curve = "牛陡（长端显著强于短端）"
        level = "宽松/避险升温"
        equity = "🛡 债市长端走强→收益率曲线牛陡，通常对应货币宽松或避险预期升温，权益风险偏好趋于谨慎"
    elif spread <= -0.30:
        curve = "熊平（长端显著弱于短端）"
        level = "紧缩/通胀预期"
        equity = "⚠️ 债市长端走弱→曲线熊平，长端收益率上行，权益估值端承压（利率敏感板块尤甚）"
    else:
        # 曲线整体方向
        if long_chg >= 0.20:
            curve = "牛平/普涨（长端偏强）"
            level = "利率下行"
            equity = "➖ 债市普涨、长端偏强→利率温和下行，对权益中性偏友好，关注是否演变为牛陡"
        elif long_chg <= -0.20:
            curve = "熊陡/普跌（长端偏弱）"
            level = "利率上行"
            equity = "⚠️ 债市普跌、长端偏弱→利率上行，权益估值端有压力"
        else:
            curve = "横盘（期限结构变化不大）"
            level = "中性"
            equity = "➖ 国债期货各期限窄幅波动，利率预期无明显方向，对权益无显著指引"

    detail = ("TL(30Y) %+.2f%% vs TS(2Y) %+.2f%%，长短端涨跌差 %+.2fpp。"
              "债期价涨=收益率下行；长端强于短端=曲线牛陡（宽松/避险），短端强于长端=曲线熊平（紧缩/通胀）。"
              "该信号为宏观环境研判，仅作观测，不直接改选股排序。") % (long_chg, short_chg, spread)
    return {"level": level, "curve": curve, "equity": equity, "detail": detail,
            "spread": spread, "long_chg": long_chg, "short_chg": short_chg}


def main():
    no_write = "--no-write" in sys.argv
    by_code = fetch_all()
    items, tick = build_items(by_code)
    if not items:
        print("  ❌ 全部抓取失败，不写盘（保留上一版）", file=sys.stderr)
        sys.exit(2)
    j = judge(items)
    update_time = _bj_now().strftime("%Y-%m-%d ") + (tick or _bj_now().strftime("%H:%M:%S"))
    out = {
        "update_time": update_time,
        "data_date": (items[0].get("date") or _bj_now().strftime("%Y-%m-%d")),
        "realtime": True,
        "source": "新浪 nf_ 实时国债期货（hq.sinajs.cn，中国IP）",
        "items": items,
        "judgment": j,
        "note": "国债期货=长端利率/避险情绪代理。TL=30年期。价涨=收益率下行=宽松/避险预期→权益风险偏好趋于谨慎（股债跷跷板）。仅观测，不改选股排序。",
    }
    if no_write:
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return
    if "--out" in sys.argv:
        out_path = os.path.abspath(sys.argv[sys.argv.index("--out") + 1])
    else:
        here = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.normpath(os.path.join(here, "..", "data", "BOND_FUTURES.js"))
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("window.BOND_FUTURES = ")
        json.dump(out, f, ensure_ascii=False)
        f.write(";\n")
    print("  💾 已写入 %s (%d 品种, update=%s, 判断=%s)" %
          (out_path, len(items), update_time, j["level"]))


if __name__ == "__main__":
    main()
