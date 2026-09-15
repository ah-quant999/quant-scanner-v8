#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_fq_worker.py — fetch_fundamental_quality 的子进程 worker（每进程独立 baostock 连接）
================================================================
🔴 2026-09-15 重建：09-09 subprocess 并发重构时本文件被遗漏提交（git 里从未存在），
导致 fetch_fundamental_quality.py 自 09-09 起 12 个 worker 全数 rc!=0（can't open file），
永远只回写旧缓存（"缓存假活"），基本面数据再无任何新查询。本次重建并补 T0 的 CFO/A 抓取。

输入: sys.argv[1] = chunk json（代码列表, 如 ["sh_600030", ...]）
输出: sys.argv[2] = 结果 json（{"stocks": {code: quality_dict}}）
主进程按 run_algorithms 预算看护；本 worker 不做重试风暴，单股异常即记 None 继续。
"""
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_fundamental_quality import (
    query_financial, query_operation, query_cash_quality, calc_quality, log,
)
import baostock as bs
from fetch_fundamental_quality import unify_code


def main():
    if len(sys.argv) < 3:
        print("usage: _fq_worker.py <chunk.json> <out.json>", flush=True)
        sys.exit(2)
    chunk_path, out_path = sys.argv[1], sys.argv[2]
    with open(chunk_path, "r", encoding="utf-8") as f:
        codes = json.load(f)

    lg = bs.login()
    if lg.error_code != "0":
        log(f"  ❌ worker baostock 登录失败: {lg.error_code} {lg.error_msg}")
        sys.exit(3)

    out = {}
    try:
        for i, raw_code in enumerate(codes):
            bsc = unify_code(raw_code)
            if not bsc:
                continue
            fin = query_financial(bsc) or {}
            op = query_operation(bsc) or {}
            cf = query_cash_quality(bsc) or {}
            q = calc_quality(fin.get("roe"), None, op.get("revenue_growth"))
            if fin.get("statDate"):
                q["statDate"] = fin["statDate"]
            for k in ("cfo_to_asset", "cfo_to_or", "asset_turn"):
                if cf.get(k) is not None:
                    q[k] = cf[k]
            # cf_queried 恒置 True（哪怕无数据），供主进程缓存判据，防每轮重查
            q["cf_queried"] = True
            out[raw_code] = q
            if (i + 1) % 20 == 0:
                log(f"    worker {os.getpid()}: {i + 1}/{len(codes)}")
    finally:
        try:
            bs.logout()
        except Exception:
            pass

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"stocks": out}, f, ensure_ascii=False)
    log(f"    worker {os.getpid()} 完成 {len(out)}/{len(codes)}")


if __name__ == "__main__":
    main()
