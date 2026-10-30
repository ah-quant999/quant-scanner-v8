#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
v8 孤儿模块 KEY_NOTICES：重要公告速览（暂未上架 › 观测类）

2026-10-30 主人令新建（查重结论：全站 0 覆盖，不与任何现有卡重复）。
口径：当日公告中筛选对盘面有实际影响的关键类别 ——
  停复牌 / 回购 / 重大资产重组 / 业绩预增预亏 / 股东增减持 / 风险警示(立案·问询)。
数据源：akshare stock_notice_report（巨潮资讯，云端已验证可达——分红链同源）。
用法：python fetch_orphan_key_notices.py
输出：raw_data/key_notices.json
"""

import json
import os
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "raw_data")
OUT = os.path.join(DATA_DIR, "key_notices.json")

# 关键词 → 展示类别（按重要性排序，先命中先归类）
KEYWORD_RULES = [
    (("复牌", "停牌"), "停复牌"),
    (("立案", "问询", "警示", "处罚", "违规"), "风险警示"),
    (("重组", "收购", "并购"), "重组并购"),
    (("回购",), "回购"),
    (("预增", "预亏", "预减", "扭亏", "业绩预告", "业绩快报"), "业绩预告"),
    (("增持",), "股东增持"),
    (("减持", "拟减持"), "股东减持"),
    (("中标", "签订", "重大合同"), "重大合同"),
]

# 展示上限（每类别）
PER_CAT_LIMIT = 6
TOTAL_LIMIT = 30


def log(msg):
    print(f"[key_notices {datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")


def classify(title):
    for kws, cat in KEYWORD_RULES:
        for kw in kws:
            if kw in title:
                return cat
    return None


def main():
    items = []
    try:
        import akshare as ak
        today = datetime.datetime.now()
        date_str = today.strftime("%Y%m%d")
        df = None
        for attempt in range(2):
            try:
                df = ak.stock_notice_report(symbol="全部", date=date_str)
                if df is not None and not df.empty:
                    break
            except Exception as e:
                log(f"  第{attempt + 1}次抓取失败: {e}")
                df = None
        if df is None or df.empty:
            log("  公告接口为空（非交易日/接口失败）")
        else:
            # 兼容列名：公告标题/标题, 代码/股票代码, 名称/股票简称
            tcol = next((c for c in ("公告标题", "标题", "公告内容") if c in df.columns), None)
            ccol = next((c for c in ("代码", "股票代码", "证券代码") if c in df.columns), None)
            ncol = next((c for c in ("名称", "股票简称", "证券简称") if c in df.columns), None)
            if tcol is None:
                log(f"  列名异常: {list(df.columns)[:8]}")
            else:
                cat_count = {}
                for _, row in df.iterrows():
                    title = str(row.get(tcol, "") or "").strip()
                    if not title:
                        continue
                    cat = classify(title)
                    if not cat:
                        continue
                    if cat_count.get(cat, 0) >= PER_CAT_LIMIT:
                        continue
                    cat_count[cat] = cat_count.get(cat, 0) + 1
                    items.append({
                        "code": str(row.get(ccol, "") or "").strip() if ccol else "",
                        "name": str(row.get(ncol, "") or "").strip() if ncol else "",
                        "title": title[:60],
                        "cat": cat,
                        "date": date_str,
                    })
                    if len(items) >= TOTAL_LIMIT:
                        break
            log(f"  命中关键公告 {len(items)} 条")
    except Exception as e:
        log(f"  公告抓取异常: {e}")

    out = {
        "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "items": items,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"  ✅ 已保存: {OUT}")


if __name__ == "__main__":
    main()
