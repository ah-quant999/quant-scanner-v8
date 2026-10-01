#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_fr_factor_consistency.py — v8 跨产物硬断言（防「最终推荐」被旧数据覆盖）
==============================================================================
🔴 2026-10-01 一劳永逸（阿狸咪的工程师）：堵死今天早上那类「会话手动把旧 raw_data
   /final_recommend.json 推上去 ⇒ 最终推荐卡与因子榜对不上」的覆盖路径。

   根因回顾：最终推荐 = 因子榜 TOP10_DAILY 前 N 名（2026-09-20 唯一口径，
   final_score := 因子榜 total_score）。但 verify_chain_outputs.py 只校验
   「本交易日新鲜度」，不校验「两卡是否同序同分」。于是某次会话推送了旧 FR
   （读的是旧因子榜快照）时，新鲜度闸放行（它确实是当天推的），却与线上因子榜
   对不上，且无人报警。

本脚本断言：
   ① raw_data/final_recommend.json 的 stocks 列表（按序）必须 == 因子榜
      raw_data/top10_daily.json 按 total_score 降序的前 N 名（N = FR 实际条数）；
   ② 逐股 final_score 必须 == 因子榜对应 total_score。

退出码
   0  一致（唯一口径成立）
   1  不一致 —— 疑似最终推荐被旧/错数据覆盖，必须拦截
   2  输入缺失/解析失败，无法判定（不强制失败，交由新鲜度闸兜底）

用法
   python algorithms/verify_fr_factor_consistency.py
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(p):
    full = os.path.join(REPO, p)
    if not os.path.exists(full):
        return None, "MISSING:" + p
    try:
        s = open(full, encoding="utf-8").read()
        i = s.find("{")
        j = s.rfind("}")
        if i < 0 or j < 0:
            return None, "NO_JSON:" + p
        return json.loads(s[i:j + 1]), None
    except Exception as e:  # noqa: BLE001
        return None, "ERR:" + str(e)


def _norm(code):
    return str(code or "").replace("sz", "").replace("sh", "").lstrip(".").zfill(6)


def _factor_topN(fb, n):
    rows = []
    for s in (fb.get("top10") or []):
        c = _norm(s.get("code"))
        rows.append((c, float(s.get("total_score") or 0)))
    rows.sort(key=lambda x: -x[1])
    return rows[:n]


def main():
    fr, err1 = _load("raw_data/final_recommend.json")
    fb, err2 = _load("raw_data/top10_daily.json")
    if err1 or err2:
        print("⚠️ 输入缺失，跳过一致性断言:", err1, err2)
        return 2

    fr_codes = [_norm(s.get("code")) for s in fr.get("stocks", [])]
    n = len(fr_codes)
    if n == 0:
        print("⚠️ 最终推荐为空，跳过一致性断言（交由新鲜度闸判空产物）")
        return 2

    fb_top = _factor_topN(fb, n)
    fb_codes = [c for c, _ in fb_top]
    fb_map = dict(fb_top)

    order_ok = (fr_codes == fb_codes)
    score_ok = all(
        (float(s.get("final_score") or -1) == fb_map.get(_norm(s.get("code")), None))
        for s in fr.get("stocks", [])
    )

    print("最终推荐前%d:" % n, fr_codes)
    print("因子榜前%d  :" % n, fb_codes)
    print("同序:", order_ok, "| 同分:", score_ok)

    if order_ok and score_ok:
        print("✅ 最终推荐与因子榜完全一致（唯一口径，无覆盖）")
        return 0
    print("❌ 不一致：最终推荐与因子榜对不上 —— 疑似被旧/错数据覆盖！")
    return 1


if __name__ == "__main__":
    sys.exit(main())
