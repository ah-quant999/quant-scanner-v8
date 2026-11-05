#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fr_coverage_check.py — 强板块龙头股覆盖检查（v8_fr_leaders_followup 自愈闭环用）。

🆕 2026-11-05 主人令「一劳永逸修复」：『最终推荐·强势板块龙头股』卡反复出现
「本轮新晋板块，龙头股名单下轮自动生成（上游字典尚未收录）」占位 —— 根因是
FINAL（云端产出，连不上东财）换板块后 fr_sectors 停旧名单。本助手做纯本地
覆盖判定，供自愈工作流决策：

  exit 0  = 全部 strong_sectors 在 fr_sectors 且 leaders 非空 ⇒ 无需自愈
  exit 42 = 有缺失板块或空龙头 ⇒ 需要跑 scripts/fetch_sector_leaders.py --fr-only
  exit 1  = 文件缺失 / 解析失败 ⇒ 链路异常，显式 ::error 报错
"""
import io
import json
import os
import sys


def _rdjs(p):
    t = io.open(p, encoding="utf-8", errors="ignore").read()
    i = t.find("{")
    j = t.rfind("}")
    return json.loads(t[i:j + 1]) if 0 <= i < j else None


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    frp = os.path.join(root, "data", "FINAL_RECOMMEND_DATA.js")
    slp = os.path.join(root, "data", "SECTOR_LEADERS.js")
    for p in (frp, slp):
        if not os.path.exists(p):
            print("::error title=v8-fr-coverage-check::missing %s (source sync incomplete)" % p)
            return 1
    try:
        fr = _rdjs(frp) or {}
        sl = _rdjs(slp) or {}
    except Exception as e:  # noqa: BLE001
        print("::error title=v8-fr-coverage-check::parse fail: %s" % e)
        return 1
    names = [str(x) for x in (fr.get("strong_sectors") or []) if x]
    if not names:
        print("[skip] FINAL has no strong_sectors => nothing to heal")
        return 0
    frs = {}
    for x in (sl.get("fr_sectors") or []):
        if isinstance(x, dict) and x.get("name"):
            frs[str(x["name"])] = x
    missing = [n for n in names if n not in frs]
    empty = [n for n in names if n in frs and not (frs[n].get("leaders") or [])]
    if not missing and not empty:
        print("[ok] fr_sectors covers %d/%d strong sectors with leaders => nothing to heal"
              % (len(names), len(names)))
        return 0
    print("NEED_FIX missing=%s empty=%s" % (missing, empty))
    return 42


if __name__ == "__main__":
    sys.exit(main())
