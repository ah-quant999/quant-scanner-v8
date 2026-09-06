#!/usr/bin/env python3
"""
gen_triple_consensus.py — 三重共识选股
共识定义（2026-09-06 审计修复，驾驶舱 09-03 下线后由三维权变二维）：
  1) 主站 TOP10 精选（generate_top10.py 输出前 10 名，且
     total_score >= max(max_score * 0.5, 25)，避免评分尺度变化后硬门槛失效）
  2) 基本面 A 档（fundamental_quality.json 中 grade 为 A）

同时输出 near_miss：有 TOP10 精选但缺基本面 A 档（差1步）的观察清单。
输出：data/triple_consensus.json
"""
import json
import os
import re

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
from datetime import datetime

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WORKSPACE, "..", "raw_data")  # 🔴 2026-08-06 改 raw_data：fundamental/top10/backtest 输入均已持久化在 raw_data（out/ 被 gitignore 云端丢）
OUTPUT = os.path.join(DATA_DIR, "triple_consensus.json")
HISTORY_FILE = os.path.join(DATA_DIR, "triple_resonance_history.json")
META_FILE = os.path.join(WORKSPACE, "stock_industry_concepts.json")


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def normalize_code(c):
    return str(c or "").replace("sh_", "").replace("sz_", "").replace("hk_", "").replace("bj_", "").replace("sh.", "").replace("sz.", "").replace("hk.", "").replace("bj.", "")


def load_meta_map(path=META_FILE):
    """加载本地静态行业/概念/板块映射（云端安全，不依赖 akshare/东财）。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def board_from_code(code):
    c = re.sub(r"[^0-9]", "", str(code))
    if not c:
        return ""
    if c.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
        return "主板"
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith(("688", "689")):
        return "科创板"
    if c.startswith(("8", "4", "92")):
        return "北交所"
    return ""


def enrich_extra(record, code, gp_map, meta_map=None):
    """从 stock_industry_concepts.json 补充行业/板块/概念；gold_pool 仅作兜底。"""
    meta_map = meta_map or {}
    code = normalize_code(code)
    meta = meta_map.get(code) or {}
    gp = gp_map.get(code) or {}

    # 板块：优先静态映射，次选代码前缀，再次 gold_pool/board
    board = meta.get("board") or record.get("board") or gp.get("board_label") or gp.get("board") or board_from_code(code)
    if board:
        record["board"] = board

    # 行业
    if not record.get("industry"):
        record["industry"] = meta.get("industry") or gp.get("industry", "")

    # 板块/行业主题标签（sectors）：合并 meta 的 concepts 前端、gold_pool.sectors、industry
    existing_sectors = set(record.get("sectors") or [])
    if record.get("industry"):
        existing_sectors.add(record["industry"])
    for s in gp.get("sectors") or []:
        if s:
            existing_sectors.add(s)
    merged_sectors = [s for s in existing_sectors if s]
    if merged_sectors:
        record["sectors"] = merged_sectors

    # 概念
    concepts = meta.get("concepts") or gp.get("concepts") or record.get("concepts") or []
    if concepts:
        record["concepts"] = concepts
    return record


def load_tracking_enter_dates():
    """从历史追踪文件读取每只股的首次入选日期，用于区分"今日新入仓"与"持续持仓"。"""
    hist = load_json(HISTORY_FILE, {})
    tracking = hist.get("_tracking_latest", {})
    if not isinstance(tracking, dict):
        return {}
    return {code: info.get("enter_date", "") for code, info in tracking.items() if info.get("enter_date")}


def main():
    print(f"  三重共识选股  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 🛡 2026-08-20 主人令·一劳永逸：三重共识属于盘后选股策略，必须 18:00 后跑。
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by='gen_triple_consensus')

    top10 = load_json(os.path.join(DATA_DIR, "top10_daily.json"), {})
    # 2026-09-03 主人令：驾驶舱(分档)已下线，三重共识不再依赖驾驶舱分档（in_a/in_b 恒为假）。
    # 保留 tier={} 占位，避免加载已删除文件报错；严格三重共识改为仅以 TOP10+基本面A 判定。
    tier = {}
    fundamental = load_json(os.path.join(DATA_DIR, "fundamental_quality.json"), {})
    gold_pool = load_json(os.path.join(DATA_DIR, "gold_pool.json"), {})

    # 从 gold_pool / 静态映射补充行业/板块/概念信息
    gp_map = {}
    for key, s in (gold_pool.get("stocks", {}) if isinstance(gold_pool, dict) else {}).items():
        gp_map[normalize_code(key)] = s
    meta_map = load_meta_map()


    # 1) 主站 TOP10 精选：排名前 10 + 相对分兜底
    # 2026-08-05 修正：原 score>=70 在 generate_top10.py 归一化到 0~100 后失效
    #（昨晚最高分仅 39.2）。改为 rank<=10 且 score>=max(max_score*0.5, 25)，
    # 既保留“当日相对最强”语义，又避免极端弱市硬塞入票。
    max_score = top10.get("max_score", 0) or 0
    top_threshold = max(max_score * 0.5, 25)
    top_map = {}
    for s in top10.get("top10", []):
        score = s.get("total_score", 0) or 0
        rank = s.get("rank", 999)
        if rank <= 10 and score >= top_threshold:
            top_map[normalize_code(s.get("code", ""))] = s

    # 2) A 档 / B 档
    a_map = {}
    for s in tier.get("tier_a", []):
        a_map[normalize_code(s.get("code", ""))] = s
    b_map = {}
    for s in tier.get("tier_b", []):
        b_map[normalize_code(s.get("code", ""))] = s

    # 3) 基本面 A 档
    fund_stocks = fundamental.get("stocks", {}) if isinstance(fundamental, dict) else {}
    good_fund = set()
    fund_map = {}
    for key, f in fund_stocks.items():
        grade = (f.get("grade") or "").upper()
        nc = normalize_code(key)
        fund_map[nc] = f
        if grade == "A":
            good_fund.add(nc)

    # 收集所有候选 code
    all_codes = set(top_map.keys()) | set(a_map.keys()) | set(b_map.keys())

    today_str = datetime.now().strftime("%Y-%m-%d")
    tracking_enter = load_tracking_enter_dates()

    consensus = []
    near_miss = []
    for code in all_codes:
        top = top_map.get(code)
        a = a_map.get(code)
        b = b_map.get(code)
        in_top = bool(top)
        in_a = bool(a)
        in_ab = bool(a or b)
        in_fund = code in good_fund

        # 🐛 2026-09-06 审计修复（P0级）：原 `in_top and in_a and in_fund` 在驾驶舱下线（tier={}，
        # in_a 恒 False）后导致严格共识自 09-03 起【永远为空】。现共识 = 主站TOP10精选 ∩ 基本面A档（二维）。
        if in_top and in_fund:
            src = top or a
            rec = {
                "code": src.get("code", code),
                "name": src.get("name", ""),
                "market": src.get("market", ""),
                "board": src.get("board", src.get("market", "")),
                "total_score": top.get("total_score", 0),
                "top10_rank": top.get("rank", 0),
                "a_score": a.get("total_score", 0),
                "quality_grade": top.get("quality_grade", a.get("quality_grade", "")),
                "quality_score": top.get("score_quality", a.get("quality_score", 0)),
                "close": top.get("close", 0),
                "pct_chg": top.get("pct_chg", 0),
                "pct_chg_20d": top.get("pct_chg_20d", 0),
                "stop_loss": top.get("stop_loss", 0),
                "target_price": top.get("target_price", 0),
                "signals": top.get("signals", {}),
                "sectors": top.get("sectors", []),
                "fund_detail": top.get("fund_detail", ""),
                "sector_detail": top.get("sector_detail", ""),
                "inst_detail": top.get("inst_detail", ""),
                "win_rate": top.get("win_rate", None),
                "enter_date": tracking_enter.get(code, today_str),
            }
            consensus.append(enrich_extra(rec, code, gp_map, meta_map))
            continue

        # near_miss（2026-09-06 审计修复）：有 TOP10 精选但缺基本面 A 档 → 差1步观察清单。
        # 驾驶舱 A/B 档来源已随 09-03 下线消失（in_a/in_b 恒 False），差2步无来源。
        if in_top and not in_fund:
            src = top or a or b
            rec = {
                "code": src.get("code", code),
                "name": src.get("name", ""),
                "market": src.get("market", ""),
                "board": src.get("board", src.get("market", "")),
                "total_score": top.get("total_score", 0) if top else (a.get("total_score", 0) if a else b.get("total_score", 0)),
                "top10_rank": top.get("rank", 0) if top else 0,
                "a_score": a.get("total_score", 0) if a else 0,
                "quality_grade": (top.get("quality_grade") if top else None) or (a.get("quality_grade") if a else None) or (fund_map.get(code) or {}).get("grade", ""),
                "in_top10": in_top,
                "in_tier_a": in_a,
                "in_tier_b": bool(b),
                "in_good_fund": in_fund,
                # 距离严格共识还差几步（按质量档位感知）：
                # A档候选只差1步（缺另一个条件即可严格）；B档候选相当于差2步（B→A一档，再到严格又一档）。
                "miss_steps": 1 if in_a else (2 if b else 1),
                "close": src.get("close", 0),
                "pct_chg": src.get("pct_chg", 0),
                "pct_chg_20d": src.get("pct_chg_20d", 0),
                "signals": top.get("signals", {}) if top else {},
                "sectors": src.get("sectors", []),
                "enter_date": tracking_enter.get(code, today_str),
            }
            near_miss.append(enrich_extra(rec, code, gp_map, meta_map))

    consensus.sort(key=lambda x: -x["total_score"])
    near_miss.sort(key=lambda x: -x["total_score"])

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_time": top10.get("update_time", ""),
        "count": len(consensus),
        "near_miss_count": len(near_miss),
        "criteria": "主站TOP10精选（rank≤10 & score≥max(max_score×0.5,25)） · 基本面A档（驾驶舱维度 2026-09-03 下线后移除）",
        "near_miss_criteria": "有TOP10精选但缺基本面A档（差1步）",
        "stocks": consensus,
        "near_miss": near_miss,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    # 2026-08-24 抗丢失：原子写 + .bak，避免被并发取消风暴杀掉时留下半截 JSON 清空数据。
    _bak = OUTPUT + ".bak"
    _tmp = OUTPUT + ".tmp"
    with open(_tmp, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    os.replace(_tmp, OUTPUT)
    try:
        with open(_bak, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    print(f"  ✅ 三重共识: {len(consensus)} 只")
    for s in consensus:
        print(f"     {s['name']}({s['code']}) TOP10#{s['top10_rank']} 评分{s['total_score']} A档{s['a_score']} 基本面{s['quality_grade']}")
    print(f"  ⚠️ 差一步(缺基本面A): {len(near_miss)} 只")
    for s in near_miss[:5]:
        tags = []
        if s["in_top10"]: tags.append("TOP10")
        if s["in_tier_a"]: tags.append("A档")
        if s.get("in_tier_b"): tags.append("B档")
        if s["in_good_fund"]: tags.append("基本面A档")
        print(f"     {s['name']}({s['code']}) 评分{s['total_score']} {'+'.join(tags)}")
    print(f"\n  输出: {OUTPUT}")


if __name__ == "__main__":
    main()
