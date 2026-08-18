#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
板块相对强度 & 领涨/抗跌追踪
用法：python fetch_sector_rs.py
输出：data/sector_rs.json

v2 (2026-06-26): 新增相对强度计算（板块vs大盘指数）
   - 拉取上证指数/沪深300的5日/20日涨跌
   - relative_5d = 板块5日涨跌 - 指数5日涨跌
   - relative_20d = 板块20日涨跌 - 指数20日涨跌
   - 新增 strong_relative_5d / strong_relative_20d / anti_drop 排名
"""
import json, os, sys, datetime, requests as req
from fetch_logger import record_success, record_failure
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))   # 迁移守卫漏注入（合并 import 行未匹配），此处补上
OUT = os.path.join(BASE, "..", "out", "sector_rs.json")
NEODATA_URL = "https://copilot.tencent.com/agenttool/v1/neodata"

# 2026-08-17 主人令：阶段快照存 raw_data/ 供前端"今日 vs 上次"对比
# 每次盘后跑成功时，把今日 phases append 到 sector_phase_history.json（云端持久化）
RAW_DIR = os.path.join(BASE, "..", "raw_data")
PHASE_HISTORY_PATH = os.path.join(RAW_DIR, "sector_phase_history.json")
PHASE_BUCKETS = ['主升', '启动', '震荡', '退潮', '底部']


def _phase_of(s):
    """前端一致的阶段判定（与 index.html line 6482-6487 完全一致）。"""
    d5 = s.get('pct_5d') or 0
    d20 = s.get('pct_20d') or 0
    if d5 > 3 and d20 > 5:
        return '主升'
    if d5 > 1.5 and d20 > 0:
        return '启动'
    if d5 < -3 and d20 < -10:
        return '底部'
    if d5 < -1.5 and d20 < -5:
        return '退潮'
    return '震荡'


def _save_phase_snapshot(sectors, update_time_str, today_str):
    """把今日 phase 快照写入 raw_data/sector_phase_history.json（累积历史）。

    格式：{"version":1, "snaps":[{"date","update_time","phases":{name→phase}}]}
    同一日重复跑 → 覆盖当日；新一日 → append；最多保留 30 天（防止 raw_data 无限增长）。
    """
    phases = {s['name']: _phase_of(s) for s in sectors if s.get('name')}
    if not phases:
        log("  [phase_history] sectors 为空，跳过快照")
        return

    # 读现有
    history = {"version": 1, "snaps": []}
    if os.path.exists(PHASE_HISTORY_PATH):
        try:
            with open(PHASE_HISTORY_PATH, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except Exception as e:
            log(f"  [phase_history] 读历史失败: {e}，重建")

    snaps = history.get("snaps", [])
    # 覆盖当日
    snaps = [s for s in snaps if s.get("date") != today_str]
    snaps.append({
        "date": today_str,
        "update_time": update_time_str,
        "phases": phases,
    })
    # 保留最近 30 天
    snaps = snaps[-30:]

    history["version"] = 1
    history["snaps"] = snaps
    try:
        with open(PHASE_HISTORY_PATH, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        log(f"  [phase_history] 已存今日快照 ({len(phases)} 板块 phase)，共 {len(snaps)} 天")
    except Exception as e:
        log(f"  [phase_history] 写历史失败: {e}")

# 读取neodata token（优先用仓库内的 .neodata_token）
TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".neodata_token")
token = None
import time as _time
# 回退：从 builtin skill 复制 token
if not os.path.exists(TOKEN_FILE):
    alt_paths = [
        "E:/workbuddy/resources/app.asar.unpacked/resources/builtin-skills/.neodata_token",
        os.path.expanduser("~/.workbuddy/.neodata_token"),
        os.path.expanduser("~/.workbuddy/skills/.neodata_token"),
    ]
    for p in alt_paths:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    cache = json.load(f)
                    token = cache.get("token")
                    saved = cache.get("saved_at", 0)
                    if _time.time() - saved < 43200:
                        break
                    else:
                        token = None
            except:
                continue
else:
    try:
        with open(TOKEN_FILE) as f:
            cache = json.load(f)
            token = cache.get("token")
    except:
        with open(TOKEN_FILE) as f:
            token = f.read().strip()

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def query_neodata(query_text):
    try:
        resp = req.post(NEODATA_URL, json={
            "query": query_text, "channel": "neodata", "sub_channel": "workbuddy"
        }, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, timeout=30)
        if resp.status_code != 200:
            return []
        data = resp.json()
        if not data.get("suc"): return []
        return data.get("data", {}).get("apiData", {}).get("apiRecall", [])
    except: return []

def _find_col(headers, *patterns):
    """根据表头关键字找列索引，返回第一个匹配，未找到返回None"""
    for i, h in enumerate(headers):
        h = str(h).replace("涨跌幅", "").replace("涨幅", "").strip()
        for p in patterns:
            if p in h:
                return i
    return None

def parse_ranking(api_recall):
    """解析行业涨跌幅排行表格，基于表头识别列（兼容 5/20/52 和 5/20/30/60/90/180/52w 两种格式）"""
    results = []
    seen = set()
    for item in api_recall:
        if "排行" not in item.get("type", ""): continue
        content = item.get("content", "")
        lines = content.strip().split("\n")
        col_idx = None
        for line in lines:
            cols = [c.strip() for c in line.split("|")]
            if ":---:" in line:
                # 上一行是表头
                break
            if any(k in line for k in ["名称", "板块", "行业"]):
                # 当前行是表头，记录下来
                col_idx = {key: _find_col(cols, *patterns) for key, patterns in {
                    "name": ["名称", "板块", "行业"],
                    "pct_day": ["当日", "当天", "今日"],
                    "pct_5d": ["5日", "5天"],
                    "pct_20d": ["20日", "20天"],
                    "pct_30d": ["30日", "30天"],
                    "pct_60d": ["60日", "60天"],
                    "pct_90d": ["90日", "90天"],
                    "pct_180d": ["180日", "180天", "半年"],
                    "pct_52w": ["52周", "一年", "近一年", "年初至今"],
                }.items()}
        if not col_idx or col_idx.get("name") is None:
            continue
        name_i = col_idx["name"]
        for line in lines:
            cols = [c.strip() for c in line.split("|")]
            if len(cols) <= name_i: continue
            if ":---:" in line: continue
            if "名称" in cols[name_i] or "板块" in cols[name_i] or "行业" in cols[name_i]: continue
            name = cols[name_i]
            if not name or name in seen: continue
            seen.add(name)
            row = {"name": name}
            for key, i in col_idx.items():
                if key == "name" or i is None: continue
                v = cols[i] if i < len(cols) else ""
                try:
                    row[key] = float(v) if v and v != '-' else None
                except:
                    row[key] = None
            # 至少有一个周期字段才保留
            if any(k.startswith("pct_") and row.get(k) is not None for k in row):
                results.append(row)
    return results

def get_index_pct(api_recall):
    """从neodata OHLCV表格提取指数各周期涨跌（累加最近N日涨跌幅）。需要至少252个交易日才能算52周。"""
    idx = {"sh": None, "hs300": None}

    for item in api_recall:
        content = item.get("content", "")
        name = ""
        if "股票名称：上证指数" in content:
            name = "sh"
        elif "股票名称：沪深300" in content:
            name = "hs300"
        else:
            continue

        # 解析OHLCV表格：分隔线后 col[4] 是单日涨跌幅
        daily_pcts = []
        past_sep = False
        for line in content.split("\n"):
            line = line.strip()
            if ":---:" in line:
                past_sep = True
                continue
            if not past_sep:
                continue
            if "省略" in line or "未开盘" in line:
                continue
            cols = [c.strip() for c in line.split("|")]
            if len(cols) < 5:
                continue
            try:
                pct_str = cols[4]
                if pct_str and pct_str not in ('-', '--', ''):
                    pct = float(pct_str)
                    daily_pcts.append(pct)
            except:
                continue

        if daily_pcts:
            n = len(daily_pcts)
            def sum_pct(offset):
                return round(sum(daily_pcts[-offset:]), 2) if n >= offset else round(sum(daily_pcts), 2)
            idx[name] = {
                "5d": sum_pct(5), "20d": sum_pct(20), "30d": sum_pct(30),
                "60d": sum_pct(60), "90d": sum_pct(90), "180d": sum_pct(180), "52w": sum_pct(252),
                "name": "上证指数" if name == "sh" else "沪深300"
            }

    return idx

def main():
    log("板块相对强度抓取...")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # ===== 主方案: neodata API =====
    if token:
        # 查涨幅（请求全周期列）
        up_data = query_neodata("今日A股行业板块涨幅排名TOP15，显示5日、20日、30日、60日、90日、180日、52周涨跌幅")
        # 查跌幅
        down_data = query_neodata("今日A股行业板块跌幅排名TOP15，显示5日、20日、30日、60日、90日、180日、52周涨跌幅")
        # 查指数全周期涨跌（至少252个交易日才能算52周；请求近一年）
        sh_data = query_neodata("上证指数近一年每个交易日单日涨跌幅数据")
        hs300_data = query_neodata("沪深300指数近一年每个交易日单日涨跌幅数据")
        index_data = sh_data + hs300_data

        sectors = parse_ranking(up_data + down_data)
        log(f"✓ neodata 获取到 {len(sectors)} 个行业板块")

        # 解析指数基准
        idx = get_index_pct(index_data)
        benchmark = idx.get("hs300") or idx.get("sh")
        if not benchmark:
            log("⚠️ 无法获取指数基准数据，相对强度不可用")
            benchmark = {"5d": 0, "20d": 0, "30d": 0, "60d": 0, "90d": 0, "180d": 0, "52w": 0, "name": "未知"}

        # 检查是否拿到全周期字段（至少要有30/60/90/180才认为满足本次需求）
        has_long_windows = sectors and all(
            any(s.get(f"pct_{k}") is not None for s in sectors[:3])
            for k in ["30d", "60d", "90d", "180d", "52w"]
        )

        if len(sectors) >= 10 and has_long_windows:
            log(f"✓ 基准指数: {benchmark['name']} 5日{benchmark['5d']:.2f}% 20日{benchmark['20d']:.2f}% 52周{benchmark['52w']:.2f}%")
            result = _build_result(sectors, benchmark, now_str, source="neodata")
            with open(OUT, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            log(f"✅ 已保存 (来源: neodata, {len(sectors)}板块)")
            _save_phase_snapshot(sectors, now_str, now_str[:10])
            record_success(__file__)
            return
        else:
            if len(sectors) < 10:
                log(f"⚠️ neodata 只返回 {len(sectors)} 个板块，切换到备用方案...")
            else:
                log("⚠️ neodata 未返回全周期字段（30/60/90/180/52w），切换到备用方案...")

    # ===== 备用方案: 同花顺(akshare) =====
    log("⚠️ 使用备用方案: 同花顺行业板块...")
    try:
        import akshare as ak
        result = _fetch_via_ths(now_str)
        with open(OUT, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        log(f"✅ 已保存 (来源: 同花顺, {len(result.get('sectors',[]))}板块)")
        _save_phase_snapshot(result.get("sectors", []), now_str, now_str[:10])
        record_success(__file__)
        return
    except Exception as e:
        log(f"❌ 备用方案也失败: {e}")

    # ===== 全部失败: 写入空结构 =====
    empty_lists = {f"strong_{k}": [] for k, _ in WINDOWS}
    empty_lists.update({f"strong_relative_{k}": [] for k, _ in WINDOWS})
    result = {"update_time": now_str, "data_date": now_str[:10], "data_available": False, "sectors": [], "weak_5d": [], "anti_drop": [],
              "index": {}, **empty_lists}
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"⚠️ 所有数据源均失败，写入空结构")
    record_failure(__file__, "所有数据源均失败，写入空结构")


WINDOWS = [
    ("5d", 5), ("20d", 20), ("30d", 30), ("60d", 60),
    ("90d", 90), ("180d", 180), ("52w", 252)
]

def _build_result(sectors, benchmark, now_str, source="unknown"):
    """构建最终结果 JSON（支持 5/20/30/60/90/180日及52周）"""
    for s in sectors:
        for key, _ in WINDOWS:
            pct_f = f"pct_{key}"
            rel_f = f"relative_{key}"
            if s.get(pct_f) is not None:
                s[rel_f] = round(s[pct_f] - benchmark.get(key, 0), 2)
            else:
                s[rel_f] = None

    result = {
        "update_time": now_str,
        "data_date": now_str[:10],   # 2026-08-18 补：板块周期卡比对锚点
        "data_available": True,
        "source": source,
        "sectors": sectors,
    }

    # 各周期涨幅榜 / 相对强度榜
    for key, _ in WINDOWS:
        pct_f = f"pct_{key}"
        rel_f = f"relative_{key}"
        result[f"strong_{key}"] = sorted(
            [s for s in sectors if s.get(pct_f) is not None],
            key=lambda x: x[pct_f], reverse=True
        )[:10]
        result[f"strong_relative_{key}"] = sorted(
            [s for s in sectors if s.get(rel_f) is not None],
            key=lambda x: x[rel_f], reverse=True
        )[:10]

    # 5日跌幅榜
    result["weak_5d"] = sorted(
        [s for s in sectors if s.get("pct_5d") is not None],
        key=lambda x: x["pct_5d"]
    )[:10]

    # 抗跌榜（20日跌幅但相对强度最高）
    anti_drop_candidates = [s for s in sectors if s.get("pct_20d") is not None and s.get("relative_20d") is not None and s["pct_20d"] < 0]
    result["anti_drop"] = sorted(anti_drop_candidates, key=lambda x: x["relative_20d"], reverse=True)[:10]

    result["index"] = {"name": benchmark.get("name", "未知")}
    for key, _ in WINDOWS:
        result["index"][f"pct_{key}"] = benchmark.get(key, 0)

    return result


def _fetch_via_ths(now_str):
    """备用方案：通过同花顺获取行业板块数据（400日历史，覆盖30/60/90/180日及52周）"""
    import akshare as ak
    from datetime import timedelta

    end_d = datetime.datetime.now().strftime("%Y%m%d")
    start_d_400 = (datetime.datetime.now() - timedelta(days=400)).strftime("%Y%m%d")

    # 1. 获取行业板块列表
    board_list = ak.stock_board_industry_name_ths()
    board_names = board_list['name'].tolist()
    total = len(board_names)
    log(f"  同花顺行业列表: {total} 个板块")

    # 2. 逐个获取历史数据计算涨跌幅
    sectors = []
    for i, name in enumerate(board_names):
        try:
            df = ak.stock_board_industry_index_ths(symbol=name, start_date=start_d_400, end_date=end_d)
            if df is None or len(df) < 2:
                continue
            df['日期'] = pd.to_datetime(df['日期']) if '日期' in df.columns else pd.to_datetime(df.index)

            closes = df['收盘价'].values
            n = len(closes)
            def pct(offset):
                return round((closes[-1] - closes[-offset-1]) / closes[-offset-1] * 100, 2) if n >= offset + 1 else None

            pct_day = pct(1) if n >= 2 else None
            sectors.append({
                "name": name,
                "pct_day": pct_day,
                "pct_5d": pct(5),
                "pct_20d": pct(20),
                "pct_30d": pct(30),
                "pct_60d": pct(60),
                "pct_90d": pct(90),
                "pct_180d": pct(180),
                "pct_52w": pct(252)
            })

            if (i+1) % 20 == 0 or i == total - 1:
                log(f"  进度 {i+1}/{total} ({name})")
        except:
            continue

    log(f"  ✓ 成功获取 {len(sectors)} 个板块数据")

    # 3. 获取指数基准（用上证指数）
    try:
        sh_df = ak.stock_board_industry_index_ths(symbol='上证指数', start_date=start_d_400, end_date=end_d)
        closes = sh_df['收盘价'].values
        n = len(closes)
        def bench_pct(offset):
            return round((closes[-1] - closes[-offset-1]) / closes[-offset-1] * 100, 2) if n >= offset + 1 else 0
        benchmark = {
            "name": "上证指数",
            "5d": bench_pct(5), "20d": bench_pct(20), "30d": bench_pct(30),
            "60d": bench_pct(60), "90d": bench_pct(90), "180d": bench_pct(180),
            "52w": bench_pct(252)
        }
    except:
        benchmark = {"name": "上证指数(近似)", "5d": 0, "20d": 0, "30d": 0, "60d": 0, "90d": 0, "180d": 0, "52w": 0}

    return _build_result(sectors, benchmark, now_str, source="同花顺")

if __name__ == "__main__":
    main()
