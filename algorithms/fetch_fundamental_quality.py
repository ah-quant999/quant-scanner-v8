#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_fundamental_quality.py — 基本面质量评分
===============================================
为候选池/金股池股票拉取 ROE / EPS / 营收增速 等核心财务指标，
计算 quality_grade (A/B/C/D) 和 quality_score (0~100)，
输出 data/fundamental_quality.json。

数据源：
  S1: Baostock query_profit_data (ROE, EPS)
  S2: Baostock query_operation_data (营收增速)
  S3: Baostock query_growth_data (净利润增速)
  兜底: 仅使用已有的 PE/PB (来自 GTimg)

评分规则（当前测算方法：ROE + 营收增速，满分 70，权重/算法不变）：
  ROE >= 20% → 40分 | >=15% → 35 | >=10% → 25 | >=5% → 15
  营收增速 >= 20% → 30分 | >=10% → 25 | >=0% → 15
  （早期文档曾列 PE<30 / PB<3 各 15 分，未接入实现；保持测算方法纯净，不加估值因子）

  quality_grade（阈值按公式真实上限对齐，仅修复不可达的 A 档，其他档位不变）：
    A: >=70  极致优质（需 ROE>=20% 且 营收>=20%；熊市天然稀少，符合"不出好股正常"）
    B: >=60  良好
    C: >=40  一般
    D: <40   基本面差
    "": 无数据（中性，不惩罚。2026-07-25 修复：此前无数据被误判 D 冤枉扣分）

消息面加减分（2026-07-25 新增，输出 stocks[code].news = {score, tags}）：
  业绩预告(东财 yjyg): 预增/扭亏 +15 | 略增/续盈 +5 | 略减 -5 | 预减/首亏/续亏 -15
  重大公告(东财 notice, 近7天): 重组/收购/合并/要约 +10 | 中标/回购/增持 +8
                                立案/处罚/退市风险 -10 | 减持/问询/诉讼 -5
  news.score 截断在 [-20, +20]；grade 只反映财务面，消息分独立字段供下游加减。
"""
import json
import os

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
import sys
import time
from datetime import datetime

import baostock as bs

BASE = os.path.dirname(os.path.abspath(__file__))
# 🔴 2026-08-06 修复：输出目录从 out/（gitignore，云端丢）→ raw_data/（git 跟踪 + api_push 推送持久化）。
#   fundamental_quality 是 generate_top10 的 score_quality 上游，之前每次云端跑完丢失 → quality 分永远 0 → TOP10 永远 <70 → 回测无信号。
DATA_DIR = os.path.join(BASE, "..", "raw_data")
OUTPUT = os.path.join(DATA_DIR, "fundamental_quality.json")
STOCK_NAMES = os.path.join(DATA_DIR, "stock_names.json")


def log(msg):
    print(msg, flush=True)


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def unify_code(raw):
    """统一代码格式为 baostock 格式: sh.600030 或 sz.300750"""
    c = str(raw).replace("sh_", "").replace("sz_", "").replace("hk_", "")
    c = c.strip()
    if not c.isdigit():
        return None
    if c.startswith("6"):
        return f"sh.{c}"
    return f"sz.{c}"


def query_financial(bsc):
    """查 Baostock 获取最近一期财报数据（ROE/EPS/营收）"""
    try:
        # 最近一期年报或季报（2025Q4 或 2026Q1）
        this_year = datetime.now().year
        for y in range(this_year, this_year - 2, -1):
            for q in [4, 2]:
                rs = bs.query_profit_data(code=bsc, year=y, quarter=q)
                if rs.error_code == "0" and rs.next():
                    row = rs.get_row_data()
                    # 字段: code, pubDate, statDate, roe, eps, ...
                    # roe 在第4列(索引3)
                    roe_val = float(row[3]) * 100 if row[3] else None  # 转为 %
                    eps_val = float(row[4]) if row[4] else None
                    return {"roe": roe_val, "eps": eps_val, "statDate": row[2], "source": "baostock_profit"}
        return None
    except Exception as e:
        return None


def query_operation(bsc):
    """查 Baostock 经营数据（营收增速）"""
    try:
        this_year = datetime.now().year
        for y in range(this_year, this_year - 2, -1):
            for q in [4, 2]:
                rs = bs.query_operation_data(code=bsc, year=y, quarter=q)
                if rs.error_code == "0" and rs.next():
                    row = rs.get_row_data()
                    # 字段: code, pubDate, statDate, turnoverRate, PEOperatingProfitMargin, ...
                    rev_growth = float(row[8]) * 100 if len(row) > 8 and row[8] else None
                    return {"revenue_growth": rev_growth, "source": "baostock_operation"}
        return None
    except Exception:
        return None


def calc_quality(roe, eps, revenue_growth):
    """根据 ROE/营收增速/PE/PB 计算质量分"""
    score = 0
    details = []

    if roe is not None:
        if roe >= 20:
            score += 40
            details.append(f"ROE优质({roe:.1f}%)")
        elif roe >= 15:
            score += 35
            details.append(f"ROE良好({roe:.1f}%)")
        elif roe >= 10:
            score += 25
            details.append(f"ROE一般({roe:.1f}%)")
        elif roe >= 5:
            score += 15
            details.append(f"ROE偏低({roe:.1f}%)")
        else:
            details.append(f"ROE差({roe:.1f}%)")
    else:
        details.append("ROE无数据")

    # 营收增速（最近一期）
    if revenue_growth is not None:
        if revenue_growth >= 20:
            score += 30
            details.append(f"营收高增({revenue_growth:.1f}%)")
        elif revenue_growth >= 10:
            score += 25
            details.append(f"营收增长({revenue_growth:.1f}%)")
        elif revenue_growth >= 0:
            score += 15
            details.append(f"营收持平({revenue_growth:.1f}%)")
        else:
            details.append(f"营收下滑({revenue_growth:.1f}%)")
    else:
        details.append("营收增速无数据")
        # 无营收数据时，ROE 权重降低
        if roe is None:
            score = 0
            details = ["无基本面数据"]

    # 评分（2026-07-25 修复：完全无数据 → grade=""中性，不再误判 D 冤枉扣分）
    if roe is None and revenue_growth is None:
        grade = ""
    else:
        # A 档阈值对齐公式真实上限(70)：仅 ROE>=20%(40)+营收>=20%(30) 的满分股可得 A；
        # 原阈值 80 在 70 分制下永不可达(死档)，本次仅修复不可达，权重/测算方法/B/C/D 档位均不变。
        grade = "A" if score >= 70 else "B" if score >= 60 else "C" if score >= 40 else "D"
    reason = " | ".join(details)
    return {
        "score": score,
        "grade": grade,
        "roe": roe,
        "revenue_growth": revenue_growth,
        "reason": reason,
    }


def fetch_news_signals(a_codes):
    """消息面加减分：业绩预告 + 近7天重大公告（仅A股）。
    返回 {6位代码: {"score": int, "tags": [str,...]}}，score 截断 [-20, +20]。
    铁律：每个接口单次尝试、异常即放弃（不重试不休眠），不拖慢流水线。
    """
    signals = {}
    try:
        import akshare as ak
    except ImportError:
        log("  ⚠️ akshare 不可用，跳过消息面加减分")
        return signals

    def add(code, sc, tag):
        e = signals.setdefault(code, {"score": 0, "tags": []})
        e["score"] += sc
        if tag not in e["tags"]:
            e["tags"].append(tag)

    # ── 1. 业绩预告（东财）：最近两个报告期，同一股票取最近一期 ──
    now = datetime.now()
    y = now.year
    if now.month >= 10:
        periods = [f"{y}0930", f"{y}0630"]
    elif now.month >= 7:
        periods = [f"{y}0630", f"{y}0331"]
    elif now.month >= 4:
        periods = [f"{y}0331", f"{y-1}1231"]
    else:
        periods = [f"{y-1}1231", f"{y-1}0930"]
    POS_TYPES = {"预增": 15, "扭亏": 15, "略增": 5, "续盈": 5}
    NEG_TYPES = {"预减": -15, "首亏": -15, "续亏": -15, "略减": -5}
    seen = set()
    for period in periods:
        try:
            df = ak.stock_yjyg_em(date=period)
        except Exception as e:
            log(f"  ⚠️ 业绩预告 {period} 获取失败: {str(e)[:80]}")
            continue
        if df is None or len(df) == 0:
            continue
        label = "中报" if period.endswith("0630") else ("年报" if period.endswith("1231") else ("三季报" if period.endswith("0930") else "一季报"))
        for _, r in df.iterrows():
            code = str(r.get("股票代码", "")).zfill(6)
            if code not in a_codes or code in seen:
                continue
            typ = str(r.get("预告类型", "")).strip()
            sc = POS_TYPES.get(typ) or NEG_TYPES.get(typ)
            if sc:
                seen.add(code)
                add(code, sc, f"{label}{typ}")
        log(f"  业绩预告 {period}: 命中候选池 {len([c for c in seen])} 只(累计)")

    # ── 2. 重大公告（东财）：近7天，关键词加减分 ──
    from datetime import timedelta
    POS_KW = [("重组", 10), ("收购", 10), ("合并", 10), ("要约", 10),
              ("中标", 8), ("回购", 8), ("增持", 8), ("战略合作", 5)]
    NEG_KW = [("立案", -10), ("处罚", -10), ("退市", -10), ("警示", -8),
              ("减持", -5), ("问询", -5), ("诉讼", -5)]
    notice_hits = 0
    for d_off in range(7):
        day = (now - timedelta(days=d_off)).strftime("%Y%m%d")
        try:
            df = ak.stock_notice_report(symbol="重大事项", date=day)
        except Exception:
            continue
        if df is None or len(df) == 0:
            continue
        for _, r in df.iterrows():
            code = str(r.get("代码", "")).zfill(6)
            if code not in a_codes:
                continue
            title = str(r.get("公告标题", ""))
            for kw, sc in POS_KW:
                if kw in title:
                    add(code, sc, kw)
                    notice_hits += 1
                    break
            else:
                for kw, sc in NEG_KW:
                    if kw in title:
                        add(code, sc, kw)
                        notice_hits += 1
                        break
    log(f"  重大公告(近7天): 命中 {notice_hits} 条")

    # 截断 [-20, +20]
    for code, e in signals.items():
        e["score"] = max(-20, min(20, e["score"]))
    log(f"  消息面信号: 共 {len(signals)} 只有加减分")
    return signals


def build_universe():
    """取 candidate_pool + gold_pool 并集
    🔴 2026-08-12 修复：stage_to_raw 的 V6_TO_V8 映射自 08-04 起把
    out/candidate_pool.json 改名搬运为 raw_data/candidate.json，raw_data 下
    不存在 candidate_pool.json → universe 只剩 gold_pool（全港股）→
    基本面 A 股全空 → 三重共识/TOP10 quality 分连续 8 天失效。
    现改为 candidate_pool.json 优先、candidate.json 兜底。"""
    codes = set()
    for fn in ("candidate_pool.json", "candidate.json", "gold_pool.json"):
        p = os.path.join(DATA_DIR, fn)
        d = load_json(p)
        codes.update(d.get("stocks", {}).keys())
    if not codes:
        # 全量股票名
        sn = load_json(STOCK_NAMES, [])
        for s in sn:
            fc = s.get("full_code", "")
            if fc.startswith(("sh", "sz")) and s.get("code"):
                codes.add(s["code"])
    return sorted(codes)


def build_name_map():
    """构建 code -> name 映射，优先候选池/金股池，再回退 stock_names.json
    （2026-08-12：同 build_universe，兼容 candidate.json 兜底）"""
    name_map = {}
    for fn in ("candidate_pool.json", "candidate.json", "gold_pool.json"):
        p = os.path.join(DATA_DIR, fn)
        d = load_json(p, {})
        for k, v in d.get("stocks", {}).items():
            if v.get("name"):
                name_map[k] = v["name"]
    sn = load_json(STOCK_NAMES, [])
    for s in sn:
        fc = str(s.get("full_code", ""))
        if fc.startswith(("sh", "sz")) and s.get("code"):
            key = f"{fc[:2]}_{s['code']}"
            if key not in name_map:
                name_map[key] = s.get("name", "")
    return name_map


def main():
    log("=" * 50)
    log("  基本面质量评分")
    log("=" * 50)

    universe = build_universe()
    log(f"待查股票: {len(universe)} 只")

    # 缓存 或 已有结果
    existing = load_json(OUTPUT, {})
    cache = existing.get("stocks", {})

    # ── 消息面信号（业绩预告+重大公告，仅A股）──
    a_codes = set()
    for raw_code in universe:
        c = str(raw_code).replace("sh_", "").replace("sz_", "").strip()
        if not str(raw_code).startswith("hk_") and c.isdigit() and len(c) == 6:
            a_codes.add(c)
    log(f"消息面扫描: A股 {len(a_codes)} 只")
    news_signals = fetch_news_signals(a_codes)

    lg = bs.login()
    log(f"Baostock: {lg.error_msg}")

    results = {}
    total_a = total_b = total_c = total_d = total_nodata = 0
    done = 0
    t0 = time.time()

    for raw_code in universe:
        # 港股：baostock 无数据源，直接中性处理（2026-07-25 修复：此前被映射成假 sz 代码→查无→误判 D）
        if str(raw_code).startswith("hk_"):
            results[raw_code] = {
                "score": 0, "grade": "", "roe": None, "revenue_growth": None,
                "reason": "港股暂无基本面数据源(中性不扣分)",
            }
            total_nodata += 1
            done += 1
            continue
        bsc = unify_code(raw_code)
        if not bsc:
            continue

        # 使用缓存或新查
        cached = cache.get(raw_code, {})
        fin = query_financial(bsc) if not cached.get("roe") else cached
        op = query_operation(bsc) if not cached.get("revenue_growth") else cached

        if fin and fin.get("roe") is not None:
            roe_val = fin["roe"]
        elif cached.get("roe"):
            roe_val = cached["roe"]
        else:
            roe_val = None

        if op and op.get("revenue_growth") is not None:
            rg_val = op["revenue_growth"]
        elif cached.get("revenue_growth"):
            rg_val = cached["revenue_growth"]
        else:
            rg_val = None

        quality = calc_quality(roe_val, None, rg_val)

        # 挂载消息面加减分（业绩预告/重大公告）
        pure = str(raw_code).replace("sh_", "").replace("sz_", "").strip()
        nw = news_signals.get(pure)
        if nw:
            quality["news"] = nw

        if quality["grade"] == "A": total_a += 1
        elif quality["grade"] == "B": total_b += 1
        elif quality["grade"] == "C": total_c += 1
        elif quality["grade"] == "D": total_d += 1
        else: total_nodata += 1

        results[raw_code] = quality
        done += 1
        if done % 50 == 0:
            log(f"  进度 {done}/{len(universe)}: A={total_a} B={total_b} C={total_c} D={total_d} 耗时{time.time()-t0:.0f}s")
        time.sleep(0.05)

    bs.logout()

    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "grade_summary": {"A": total_a, "B": total_b, "C": total_c, "D": total_d, "no_data": total_nodata},
        "stocks": results,
    }
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    log(f"\n=== 完成 ===")
    log(f"总 {len(results)} 只, A={total_a} B={total_b} C={total_c} D={total_d} 无数据={total_nodata}")
    log(f"输出: {OUTPUT}")


if __name__ == "__main__":
    main()
