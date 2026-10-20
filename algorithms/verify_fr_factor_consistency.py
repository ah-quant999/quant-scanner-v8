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

🔴🔴 2026-10-20 二劳永逸（主人截图实锤第二宗事故）：上一条只校 raw_data 层，
   而**页面真实显示的是 data/*.js 层**。当晚 raw 层两文件恰为同批旧版（互校
   通过、放行），data 层却分裂：data/TOP10_DAILY.js 18:12（佰维18.2/德明利17.8/
   长飞17.3）vs data/FINAL_RECOMMEND_DATA.js 19:07（佰维18.6/迪安诊断78.0/长飞17.2）
   —— 名单第 2 名对不上、同票分对不上，链闸全程无报警。
   根因：FR 运行时读的因子榜快照 ≠ 页面展示的因子榜版本（快照漂移），
   叠加 10-14 双源混排竞位（已按主人 10-20 令废止，见 final_recommend.py）。
   ⇒ 本版起**两层都校**：raw 归档层 + data 页面层，任一层不同序同分即 exit 1。

本脚本断言（每层各一遍）：
   ① 最终推荐 stocks 列表（按序）必须 == 因子榜 top10 按 total_score 降序的前 N 名
      （N = 最终推荐实际条数）；
   ② 逐股 final_score 必须 == 因子榜对应 total_score。

退出码
   0  两层均一致（唯一口径成立）
   1  任一层不一致 —— 疑似最终推荐被旧/错数据覆盖，必须拦截
   2  输入缺失/解析失败，无法判定（不强制失败，交由新鲜度闸兜底）

用法
   python algorithms/verify_fr_factor_consistency.py
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# (层名, 最终推荐文件, 因子榜文件) —— raw 归档层 + data 页面层
LAYERS = [
    ("raw 归档层", "raw_data/final_recommend.json", "raw_data/top10_daily.json"),
    ("data 页面层", "data/FINAL_RECOMMEND_DATA.js", "data/TOP10_DAILY.js"),
]


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


def _check_layer(name, fr_path, fb_path):
    """返回 (rc, lines)。rc: 0=一致 1=不一致 2=无法判定"""
    fr, err1 = _load(fr_path)
    fb, err2 = _load(fb_path)
    if err1 or err2:
        return 2, ["⚠️ %s 输入缺失，跳过一致性断言: %s %s" % (name, err1, err2)]

    fr_codes = [_norm(s.get("code")) for s in fr.get("stocks", [])]
    n = len(fr_codes)
    if n == 0:
        return 2, ["⚠️ %s 最终推荐为空，跳过一致性断言（交由新鲜度闸判空产物）" % name]

    fb_top = _factor_topN(fb, n)
    fb_codes = [c for c, _ in fb_top]
    fb_map = dict(fb_top)

    order_ok = (fr_codes == fb_codes)
    score_ok = all(
        (float(s.get("final_score") or -1) == fb_map.get(_norm(s.get("code")), None))
        for s in fr.get("stocks", [])
    )

    lines = ["%s 最终推荐前%d: %s" % (name, n, fr_codes),
             "%s 因子榜前%d  : %s" % (name, n, fb_codes),
             "%s 同序: %s | 同分: %s" % (name, order_ok, score_ok)]
    if order_ok and score_ok:
        lines.append("✅ %s 最终推荐与因子榜完全一致（唯一口径，无覆盖）" % name)
        return 0, lines
    lines.append("❌ %s 不一致：最终推荐与因子榜对不上 —— 疑似被旧/错数据覆盖！" % name)
    return 1, lines


def main():
    worst = 0
    for name, fr_path, fb_path in LAYERS:
        rc, lines = _check_layer(name, fr_path, fb_path)
        for l in lines:
            print(l)
        print()
        if rc == 1:
            worst = 1
        elif rc == 2 and worst == 0:
            worst = 2

    if worst == 1:
        print("🛑 跨产物一致性未通过（至少一层不同序同分）——最终推荐疑似被旧/错数据覆盖，"
              "与因子榜对不上。交由告警链路处理；请勿绕过本闸门。")
        return 1
    if worst == 2:
        print("⚠️ 部分层输入缺失，无法完整判定（交由新鲜度闸兜底）")
        return 2
    print("✅ 两层（raw 归档 + data 页面）均同序同分：最终推荐与因子积分榜口径、评分完全一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
