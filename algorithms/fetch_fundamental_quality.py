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
import os
import time
import subprocess
import tempfile
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
    """统一代码格式为 baostock 格式: sh.600030 或 sz.300750。
    🛡 2026-09-09 健壮性：同时兼容下划线(sh_600000)与点(sh.600000)两种
    universe 编码，避免任一种格式时 unify_code 静默返回 None 导致全量空跑。"""
    c = str(raw).replace("sh_", "").replace("sz_", "").replace("hk_", "").replace(".", "")
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


def build_universe(max_codes: int = 500):
    """取 candidate_pool + gold_pool 并集
    🔴 2026-08-12 修复：stage_to_raw 的 V6_TO_V8 映射自 08-04 起把
    out/candidate_pool.json 改名搬运为 raw_data/candidate.json，raw_data 下
    不存在 candidate_pool.json → universe 只剩 gold_pool（全港股）→
    基本面 A 股全空 → 三重共识/TOP10 quality 分连续 8 天失效。
    现改为 candidate_pool.json 优先、candidate.json 兜底。
    🛡 2026-09-08 加 max_codes 护栏：候选池缺失 fallback 到全量 stock_names 时，
       全量 5000+ 只串行查 Baostock 会产生网络风暴；超过阈值则截断并告警，保留核心标的。"""
    codes = set()
    for fn in ("candidate_pool.json", "candidate.json", "gold_pool.json"):
        p = os.path.join(DATA_DIR, fn)
        d = load_json(p)
        codes.update(d.get("stocks", {}).keys())
    source = "candidate_pool/gold_pool"
    if not codes:
        source = "stock_names fallback"
        sn = load_json(STOCK_NAMES, [])
        for s in sn:
            fc = s.get("full_code", "")
            if fc.startswith(("sh", "sz")) and s.get("code"):
                codes.add(s["code"])
    codes = sorted(codes)
    if len(codes) > max_codes:
        log(f"  ⚠️ universe 过大({len(codes)} > {max_codes})，按{source}截断前 {max_codes} 只，防止 ROE 串行网络风暴")
        codes = codes[:max_codes]
    return codes


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
    log("  基本面质量评分 (subprocess 并发版 · 真实全量)")
    log("=" * 50)

    # 🛡 2026-09-09 根治：baostock 单连接非线程安全 + 本机 Windows 下
    # ProcessPoolExecutor spawn 必 BrokenProcessPool。改用标准 subprocess 并发启动
    # N 个独立子进程（_fq_worker.py，每进程独立 baostock 连接，完全隔离），
    # 主进程分块派发 + 汇总。真实全量计算，无缩水无造假。
    # max_codes 默认 2000（远超实际 universe ~528），确保不截断、不丢标的。
    _max = int(os.environ.get("V8_FUND_MAX_CODES", "2000"))
    universe = build_universe(max_codes=_max)
    log(f"待查股票: {len(universe)} 只 (max_codes={_max}, 真实全量)")

    # 缓存 或 已有结果
    existing = load_json(OUTPUT, {})
    cache = existing.get("stocks", {})

    # ── 消息面信号（业绩预告+重大公告，仅A股，主进程 akshare）──
    a_codes = set()
    for raw_code in universe:
        c = str(raw_code).replace("sh_", "").replace("sz_", "").strip()
        if not str(raw_code).startswith("hk_") and c.isdigit() and len(c) == 6:
            a_codes.add(c)
    log(f"消息面扫描: A股 {len(a_codes)} 只")
    news_signals = fetch_news_signals(a_codes)

    results = {}
    total_a = total_b = total_c = total_d = total_nodata = 0
    done = 0
    t0 = time.time()

    def _classify(roe_val, rg_val, raw_code):
        """算 quality、挂消息面、累加评级计数，返回 quality dict"""
        nonlocal total_a, total_b, total_c, total_d, total_nodata
        quality = calc_quality(roe_val, None, rg_val)
        pure = str(raw_code).replace("sh_", "").replace("sz_", "").strip()
        nw = news_signals.get(pure)
        if nw:
            quality["news"] = nw
        g = quality["grade"]
        if g == "A": total_a += 1
        elif g == "B": total_b += 1
        elif g == "C": total_c += 1
        elif g == "D": total_d += 1
        else: total_nodata += 1
        return quality

    # 港股 / 缓存命中 → 直接处理；其余进子进程并发查
    to_query = []
    for raw_code in universe:
        if str(raw_code).startswith("hk_"):
            results[raw_code] = {
                "score": 0, "grade": "", "roe": None, "revenue_growth": None,
                "reason": "港股暂无基本面数据源(中性不扣分)",
            }
            total_nodata += 1
            done += 1
            continue
        cached = cache.get(raw_code, {})
        if cached.get("roe") is not None or cached.get("revenue_growth") is not None:
            results[raw_code] = _classify(cached.get("roe"), cached.get("revenue_growth"), raw_code)
            done += 1
        else:
            to_query.append(raw_code)

    log(f"  缓存命中 {done} 只，需查询 {len(to_query)} 只 → 启动 {min(12, max(1, len(to_query)))} 个子进程并发...")

    if to_query:
        N = min(12, len(to_query))
        # 轮转分块，保证各子进程负载均衡
        chunks = [to_query[i::N] for i in range(N)]
        tmpdir = tempfile.mkdtemp(prefix="fq_")
        worker = os.path.join(BASE, "_fq_worker.py")
        pybin = os.environ.get("V8_PYTHON", "python")
        chunk_paths, out_paths, procs = [], [], []
        for i, ch in enumerate(chunks):
            if not ch:
                continue
            cp = os.path.join(tmpdir, f"chunk_{i}.json")
            op = os.path.join(tmpdir, f"out_{i}.json")
            with open(cp, "w", encoding="utf-8") as f:
                json.dump(ch, f, ensure_ascii=False)
            chunk_paths.append(cp)
            out_paths.append(op)
            p = subprocess.Popen([pybin, worker, cp, op], cwd=BASE,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, bufsize=1, encoding="utf-8", errors="replace")
            procs.append(p)
            log(f"    worker[{i}] 启动 pid={p.pid} 处理 {len(ch)} 只")
        # 等待所有子进程结束（带总超时保护，单 worker 卡死不影响汇总）
        deadline = time.time() + 5400  # 90min 总预算
        alive = list(procs)
        while alive and time.time() < deadline:
            for p in list(alive):
                rc = p.poll()
                if rc is not None:
                    alive.remove(p)
                    out = p.stdout.read() if p.stdout else ""
                    if rc != 0:
                        log(f"    ⚠️ worker 退出码 {rc}: {out[-200:].strip()}")
            if alive:
                time.sleep(3)
        for p in alive:  # 超时仍有存活 → 强杀（产物视为未产出，下游门控拒用陈旧数据）
            try: p.kill()
            except Exception: pass
            log(f"    💀 worker pid={p.pid} 超时强杀")
        # 汇总子进程输出
        for op in out_paths:
            try:
                d = load_json(op)
                results.update(d.get("stocks", {}))
                done += len(d.get("stocks", {}))
            except Exception as e:
                log(f"    ⚠️ 汇总 {os.path.basename(op)} 失败: {e}")
        # 对子进程产出的结果做质量分级 + 消息面挂载
        cache_hit = set()
        for raw_code in universe:
            if raw_code.startswith("hk_"):
                continue
            c = cache.get(raw_code, {})
            if c.get("roe") is not None or c.get("revenue_growth") is not None:
                cache_hit.add(raw_code)
        for raw_code, q in results.items():
            if raw_code in cache_hit:
                continue  # 已是缓存命中分类过的（含 news），跳过
            g = q.get("grade", "")
            if g == "A": total_a += 1
            elif g == "B": total_b += 1
            elif g == "C": total_c += 1
            elif g == "D": total_d += 1
            else: total_nodata += 1
            pure = str(raw_code).replace("sh_", "").replace("sz_", "").strip()
            nw = news_signals.get(pure)
            if nw:
                q["news"] = nw
        log(f"  子进程汇总完成，累计 {done} 只")
    else:
        log("  无需查询（全部缓存命中）")

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
