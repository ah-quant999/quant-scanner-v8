# -*- coding: utf-8 -*-
"""
板块周期阶段快照（SECTOR_PHASE_HISTORY）本地自愈生成器
================================================================
2026-11-23 主人令「一劳永逸修复」：

真根因：fetch_sector_rs.py 虽在成功时会 append 当日 phase 快照，但 cn_fetch 链的
「抓取→推送」多机交接中，raw_data/sector_phase_history.json 多次被旧版覆盖
（线上实证 11-20/11-22 均有新 sector_rs.json，快照却停在 11-18），
且该卡未登记 CARD_DEFS，只落在「全量数据」通用红线下，自愈链够不到 ⇒ 永久 fail。

本脚本只读**已落盘的真实 raw_data/sector_rs.json**（最新数据日 + 90 板块涨跌幅），
按与前端/主生成器**同一个 _phase_of 规则**（直接 import，禁止复制规则造成漂移）
补写缺失数据日的快照，再用 update_v8._write_js 重建 data/SECTOR_PHASE_HISTORY.js。
零网络、零臆造：sector_rs.json 没有的日期一律不补。

被 v8_health_check.py 的 LOCAL_GEN 映射为 heal_cat=local_gen 的自愈入口。
"""
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw_data")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "algorithms"))

# 唯一规则真相源：与 algorithms/fetch_sector_rs.py 共用，杜绝两处判定漂移
from fetch_sector_rs import (  # noqa: E402
    _phase_of, _is_weekend_date, PHASE_RULE_VER, PHASE_HISTORY_PATH,
)

CST = ZoneInfo("Asia/Shanghai")


def main():
    sr_path = os.path.join(RAW, "sector_rs.json")
    if not os.path.exists(sr_path):
        print("[phase_history] raw_data/sector_rs.json 缺失，放弃（不编造）")
        return 2
    with open(sr_path, encoding="utf-8") as f:
        sr = json.load(f)
    sectors = sr.get("sectors") or []
    dd = str(sr.get("data_date") or "")[:10]
    phases = {s["name"]: _phase_of(s) for s in sectors if s.get("name")}
    if not phases or len(dd) != 10 or _is_weekend_date(dd):
        print(f"[phase_history] 无有效板块或数据日非法/周末 data_date={dd}，放弃")
        return 2

    history = {"version": 1, "snaps": []}
    if os.path.exists(PHASE_HISTORY_PATH):
        try:
            with open(PHASE_HISTORY_PATH, encoding="utf-8") as f:
                history = json.load(f)
        except Exception as e:
            print(f"[phase_history] 旧档读取失败，重建: {e}")
            history = {"version": 1, "snaps": []}

    now_str = datetime.now(CST).strftime("%Y-%m-%d %H:%M")
    snaps = []
    for s in history.get("snaps", []):
        sd = str(s.get("date", ""))[:10]
        # 与 fetch_sector_rs._save_phase_snapshot 同口径清污：未来日/周末幻影档剔除
        if (not sd) or (sd > dd) or _is_weekend_date(sd):
            continue
        if sd != dd:
            snaps.append(s)
    existed = any(str(s.get("date"))[:10] == dd for s in history.get("snaps", []))
    snaps.append({"date": dd, "update_time": now_str,
                  "rule_ver": PHASE_RULE_VER, "phases": phases})

    history["version"] = 1
    history["rule_ver"] = PHASE_RULE_VER
    history["snaps"] = snaps
    # 🛡 2026-11-25 小九的工程师（治本 crosslayer-deploy-block-1125）：
    #   落盘必须同步刷新顶层 update_time / republish_time。原实现沿用旧档陈值
    #   ⇒ raw 顶层标签冻结（线上实证停 2026-11-23 01:22 不动），而 data/*.js 每次重建
    #   经 update_v8._write_js「保留较新者」取到更近时刻 ⇒ v8_verify_layer_parity.py
    #   判「data 比 raw 新 = 真错位」恒阻断 build_deploy「部署到 main」，结构性、不会自愈。
    #   修复后 raw 顶层标签 = 本次写入时刻（本脚本 now_str 为 ZoneInfo CST，无时区漂移），
    #   data 重建取同一语义戳 ⇒ 两层恒对齐。
    history["update_time"] = now_str
    history["republish_time"] = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
    # 跨机器行尾统一 LF（见 fetch_sector_rs 注释：Windows CRLF 会造 4840 行假 diff）
    with open(PHASE_HISTORY_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

    import update_v8 as u  # noqa: E402
    u._write_js("SECTOR_PHASE_HISTORY", history)
    print(f"[phase_history] {'覆盖' if existed else '补写'}数据日 {dd} "
          f"({len(phases)} 板块)，共 {len(snaps)} 天 → data/SECTOR_PHASE_HISTORY.js")
    return 0


if __name__ == "__main__":
    sys.exit(main())
