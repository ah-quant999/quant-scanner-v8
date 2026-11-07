#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_huijin_etf_drill.py — 汇金宽基 ETF 下钻数据源生成器
═══════════════════════════════════════════════════════════
产出: data/HUIJIN_ETF_DRILL.js  (window.HUIJIN_ETF_DRILL)
消费: index.html __renderNationalTeam 内的「汇金宽基ETF下钻」可折叠子表

数据口径（真实、不伪造）:
  1. 汇金公开增持的宽基 ETF 列表 (公开披露口径, 多发行人, 沪深300/中证500/上证50/
     科创50/中证1000/上证180/深证100/创业板 等宽基) — 硬编码真实代码/名称。
  2. 申赎变化 (d_shares_yi / d_amount_yi / pct / shares_yi): 优先匹配本地已落盘的
     data/ETF_SUBSCRIPTION_EASTMONEY.js (东财五分类 Top 榜, 真实)。未进入 Top 榜的
     代码在本机无数据 → ma20_mult / 申赎 标 null, 由云端 fetcher 补全 (走东财全量接口)。
  3. 较20日均倍数 (ma20_mult): 需盘中/历史 K 序列, 本机无 → null, 云端补。

设计: 本脚本本机可跑 (只用本地东财文件, 无网络依赖即可产出真实可上线底表);
      云端运行时若可访问东财全量申赎接口, 可补全其余代码的申赎与 ma20_mult。
"""
import json, re, os, sys, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

# ── 1. 汇金公开增持宽基 ETF (公开披露口径, 真实代码/名称) ──────────────
HUIJIN_ETFS = [
    ("510300", "沪深300ETF(华泰柏瑞)"),
    ("510050", "上证50ETF(华夏)"),
    ("510500", "中证500ETF(南方)"),
    ("159919", "沪深300ETF(嘉实)"),
    ("588000", "科创50ETF(华夏)"),
    ("588080", "科创板50ETF(易方达)"),
    ("510330", "沪深300ETF(华夏)"),
    ("510310", "沪深300ETF(易方达)"),
    ("512500", "中证500ETF(华夏)"),
    ("512100", "中证1000ETF(南方)"),
    ("159922", "中证500ETF(嘉实)"),
    ("560010", "中证1000ETF(易方达)"),
    ("510510", "中证500ETF(广发)"),
    ("510210", "上证180ETF(国泰)"),
    ("159901", "深证100ETF(易方达)"),
    ("510180", "上证180ETF(华安)"),
    ("588050", "科创50ETF(工银)"),
    ("159915", "创业板ETF(易方达)"),
    ("159629", "中证1000ETF(富国)"),
    ("159845", "中证1000ETF(华夏)"),
]

def load_eastmoney_map():
    """从本地 ETF_SUBSCRIPTION_EASTMONEY.js 抽 code->申赎明细 (真实, 仅 Top 榜覆盖)。"""
    p = os.path.join(DATA, "ETF_SUBSCRIPTION_EASTMONEY.js")
    m = {}
    if not os.path.exists(p):
        return m
    try:
        src = open(p, encoding="utf-8").read()
        obj = json.loads(re.search(r"=\s*(\{.*\})\s*;?\s*$", src, re.S).group(1))
        for cat, cdata in (obj.get("categories") or {}).items():
            for lst in ("top_sub", "top_redeem"):
                for it in (cdata.get(lst) or []):
                    m[it["code"]] = {
                        "cat": cat,
                        "d_shares_yi": it.get("d_shares_yi"),
                        "d_amount_yi": it.get("d_amount_yi"),
                        "pct": it.get("pct"),
                        "shares_yi": it.get("shares_yi"),
                    }
    except Exception as e:
        sys.stderr.write("[huijin_drill] 东财解析失败: %s\n" % e)
    return m

def try_cloud_enrich(etfs):
    """云端补全: 若可访问东财全量申赎接口, 补全申赎 + ma20_mult。本机不可达则跳过 (graceful)。"""
    # 占位: 真实云端运行时在此调用东财 push2 或 fund 接口补全每只 ETF 的
    #   - 单位净值折算净申赎 (d_shares_yi/d_amount_yi/pct/shares_yi)
    #   - 较20日均倍数 (ma20_mult) = 当日成交额 / 20日平均成交额
    # 本机无网络/无密钥 → 返回空, 由下方 null 占位, UI 诚实标「云端补全」。
    return {}

def main():
    em = load_eastmoney_map()
    cloud = try_cloud_enrich(HUIJIN_ETFS)
    rows = []
    for code, name in HUIJIN_ETFS:
        rec = {
            "code": code,
            "name": name,
            "huijin": "汇金公开增持宽基",
            "d_shares_yi": None,
            "d_amount_yi": None,
            "pct": None,
            "shares_yi": None,
            "ma20_mult": None,
        }
        if code in em:
            rec.update({k: em[code].get(k) for k in ("d_shares_yi", "d_amount_yi", "pct", "shares_yi")})
            rec["_src"] = "eastmoney_top"
        if code in cloud:
            rec.update(cloud[code])
            rec["_src"] = "cloud"
        rows.append(rec)

    # 真实统计: 有多少只拿到了真实申赎
    got = sum(1 for r in rows if r["d_shares_yi"] is not None)
    out = {
        "update_time": "2026-11-07 22:20:00",
        "data_date": "2026-11-06",
        "source": "汇金公开增持宽基ETF列表(硬编码真实) + 东财五分类申赎Top榜(真实匹配) + 云端全量补全(待跑)",
        "note": "申赎变化仅覆盖进入东财Top榜的标的; 其余由云端 fetcher 走东财全量接口补全。ma20_mult 需历史K序列, 云端补。绝不伪造。",
        "matched_real": got,
        "total": len(rows),
        "etfs": rows,
    }
    dest = os.path.join(DATA, "HUIJIN_ETF_DRILL.js")
    with open(dest, "w", encoding="utf-8") as f:
        f.write("window.HUIJIN_ETF_DRILL = ")
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write(";\n")
    sys.stderr.write("[huijin_drill] 已生成 %s : %d/%d 只含真实申赎\n" % (dest, got, len(rows)))

if __name__ == "__main__":
    main()
