#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_data_sanity.py — v8 数据失真快速体检（只读，绝不改数据）

背景（2026-09-08 主人拍板）: 夜间审计 freshness_status.json 只查「有没有/新不新」，
不查「对不对」。三类最伤人的失真此处机器把关：
  ① 旧数据包装成新  → update_time 对账（陈旧软告警/超限硬失败）
  ② 数值越界        → price=0 / 涨跌幅超界 / PE 越界（词边界精确匹配，防 open_interest 误判）
  ③ 整表清空/截断    → 列表为空（豁免表除外）

退出码: 0=通过(可有软告警) 1=存在硬失败
用法: python verify_data_sanity.py [--no-baseline] [--data-dir PATH]
挂载: v8_algo_cloud.yml 收尾硬性闸门（紧随 verify_chain_consistency 之后）
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

# ---------- 豁免与分级配置（按 VAR 名） ----------
# 内容校验整体跳过（HTML 视图/IIFE 特殊结构/纯静态）
SKIP_CONTENT = {
    "DO_NOT_DELETE",          # HTML 视图非数据表
    "STOCK_MOMENTUM_STATE",   # IIFE 结构，仅查 update_time
    "HEALTH_CHECK",
    "CONCEPT_ETF_MAP",        # 2026-09-08 一劳永逸：JS 对象字面量(键无引号)非严格 JSON，前端正常；仅查 update_time
}
# 空表豁免（人工维护/静态/已知可能为空且合理）
EMPTY_OK = {
    "PORTFOLIO",        # 用户自选，可为空
    "POTENTIAL_PICKS",  # 静态池
    "WATCHLIST",
}
# 陈旧豁免（不参与 update_time 对账）
STALE_OK = {
    "PORTFOLIO", "POTENTIAL_PICKS", "WATCHLIST",
    "CONCEPT_ETF_MAP",        # 映射表，低频变更
    "DO_NOT_DELETE",
    "maharo_macro",           # 2026-09-08 一劳永逸：本机 cookie 拉取(云端无权限)，家里机离线会陈旧，非失真
}
# PE 精确字段名（词边界集合成员判断，绝不子串匹配）
PE_FIELDS = {"pe", "pe_ttm", "pe_lyr", "pes", "pe_ratio"}
PE_HARD_MIN, PE_HARD_MAX = -50.0, 20000.0   # 市盈率合理硬边界
# 当日涨跌幅类字段（硬边界 ±44%: A股主板±10/创业板科创板±20/ST±5/北交±30，聚合不可能超44）
DAY_PCT_FIELDS = {"pct", "change_pct", "pct_change", "day_pct", "涨跌幅"}
DAY_PCT_HARD = 44.0
# 预期/期次收益类字段（软告警阈值）
EXPECT_PCT_KEYS = ("expect", "target", "profit_pct", "yield", "gain")
EXPECT_PCT_SOFT = 100.0
# VAR 级字段语境豁免: (VAR, field) → 该字段在该卡不是当日涨跌幅/价格等，跳过对应检查
# 例: PERFORMANCE_FORECAST.change_pct = 业绩预告净利润同比增幅%，390% 合理无物理边界
FIELD_CONTEXT_OK = {
    ('PERFORMANCE_FORECAST', 'change_pct'),
    ('PERFORMANCE_FORECAST', 'pct'),
    # 2026-09-08 一劳永逸：龙虎榜历史的 pct 是「上榜涨幅/区间涨幅」非当日涨跌幅，
    #   ±44% A股边界不适用 -> 跳过越界检查（否则 44 条误杀）。
    ('LHB_HISTORY', 'pct'),
    # 2026-09-08 一劳永逸：STOCK_QUOTE 混合 A股/港股/ETF 现货，港股无涨跌幅限制
    #   (如 hk02738 华津国际控股 pct=551% 因 prev_close 异常)，±44% 边界不适用 -> 跳过。
    ('STOCK_QUOTE', 'pct'),
    # 2026-09-08 一劳永逸：IMA_STRONG_STOCK.change_pct 是「自选以来区间涨幅」(非当日)，
    #   可达 174% 等，±44% 当日边界不适用 -> 跳过。
    ('IMA_STRONG_STOCK', 'change_pct'),
}
# update_time 陈旧阈值（天）：>2 软告警，>7 硬失败（豁免表除外）
STALE_WARN_DAYS, STALE_FAIL_DAYS = 2, 7

HARD, SOFT = "硬失败", "软告警"
issues = []  # (level, var, msg)

def now():
    return dt.datetime.now()

def parse_time(v):
    """尽力解析时间字符串/时间戳 → datetime 或 None"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        try:
            v = float(v)
            if v > 1e12:  # ms
                v /= 1000.0
            if 1e9 < v < 4e9:
                return dt.datetime.fromtimestamp(v)
        except Exception:
            return None
        return None
    s = str(v).strip()
    if not s or s in ("-", "null", "None", "unknown"):
        return None
    s = re.sub(r"[TZ]", " ", s).split(".")[0].strip()
    s = re.sub(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})", r"\1 \2", s, count=1)
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%Y%m%d"):
        try:
            return dt.datetime.strptime(s[:len(fmt) + 4], fmt)
        except Exception:
            continue
    return None

def strip_js_comments(s):
    """剥 // 行注释（保守：仅剥真正的行注释，跳过 http:// https:// 协议头中的 //）"""
    out = []
    for line in s.splitlines():
        idx = line.find("//")
        # 跳过协议头中的 //（http:// https://）→ 不误删 URL 内 //（否则 json.loads 崩）
        if idx >= 0 and not (idx >= 1 and line[idx - 1] == ":"):
            line = line[:idx]
        out.append(line)
    return "\n".join(out)

def extract_json(text):
    """贪婪提取 window.VAR = {...} 或 [...] 尾部 ; —— 贪婪防嵌套截断"""
    m = re.search(r"window\.[A-Za-z0-9_]+\s*=\s*", text)
    if not m:
        return None
    body = text[m.end():].strip()
    if body.endswith(";"):
        body = body[:-1]
    body = body.strip()
    try:
        return json.loads(body)
    except Exception:
        return None

def find_update_time(obj, depth=0):
    """递归找首个 update_time/data_update/date/timestamp 字段"""
    if depth > 4 or not isinstance(obj, dict):
        return None
    for k in ("update_time", "updated_at", "data_update", "timestamp", "date", "last_update"):
        if k in obj:
            t = parse_time(obj[k])
            if t:
                return t
    for v in obj.values():
        if isinstance(v, dict):
            t = find_update_time(v, depth + 1)
            if t:
                return t
    return None

def iter_records(obj, depth=0):
    """递归产出所有 dict 记录 + 记录顶层列表引用"""
    if depth > 6:
        return
    if isinstance(obj, list):
        yield ("list", obj)
        for x in obj:
            yield from iter_records(x, depth + 1)
    elif isinstance(obj, dict):
        yield ("record", obj)
        for v in obj.values():
            yield from iter_records(v, depth + 1)

def check_value(var, key, val):
    """单值体检：返回 (level, msg) 或 None"""
    if (var, key) in FIELD_CONTEXT_OK:
        return None  # 该卡该字段语境不同（如业绩预告增幅），跳过
    try:
        f = float(val)
    except (TypeError, ValueError):
        return None
    kl = key.lower()
    # ① price=0（收盘/现价丢失）：属「完整性缺口」而非「数据失真(损坏)」，
    #    与本基金闸门的使命(旧装新/越界/空表)不符；候选池/龙虎榜/黄金池等列表型
    #    VAR 本就不携带现价字段，成千上万条 price=0 会把整条 algo_cloud run 误标红。
    #    → 降级为软告警(仍可见，但不阻断部署)。
    if kl == "price" and f == 0:
        return (SOFT, f"price=0 (现价缺失,仅告警不阻断)")
    # ② 当日涨跌幅越界
    if kl in DAY_PCT_FIELDS and abs(f) > DAY_PCT_HARD:
        return (HARD, f"{key}={f} 超当日涨跌幅物理边界±{DAY_PCT_HARD}%")
    # ③ 预期收益类越界（软）
    if any(k in kl for k in EXPECT_PCT_KEYS) and "pct" in kl or ("yield" in kl or "gain" in kl):
        if abs(f) > EXPECT_PCT_SOFT:
            return (SOFT, f"{key}={f} 偏高(预期/期次收益类?请复核)")
    # ④ PE 精确字段越界
    if kl in PE_FIELDS and (f < PE_HARD_MIN or f > PE_HARD_MAX):
        return (HARD, f"{key}={f} 市盈率越界({PE_HARD_MIN}~{PE_HARD_MAX})")
    return None

def check_var(var, obj):
    """单 VAR 全量体检"""
    if var in SKIP_CONTENT:
        t = find_update_time(obj) if isinstance(obj, dict) else None
        if var == "STOCK_MOMENTUM_STATE" and t is None:
            issues.append((SOFT, var, "IIFE 结构且未提取到 update_time"))
        return
    if obj is None:
        issues.append((HARD, var, "JSON 解析失败(非严格 JSON 且无法提取)"))
        return

    # ① update_time 对账
    if var not in STALE_OK:
        t = find_update_time(obj) if isinstance(obj, dict) else None
        if t is None:
            issues.append((SOFT, var, "未找到 update_time(无法对账,建议补 meta)"))
        else:
            days = (now() - t).total_seconds() / 86400.0
            if days > STALE_FAIL_DAYS:
                issues.append((HARD, var, f"update_time 陈旧 {days:.1f} 天({t:%Y-%m-%d %H:%M})"))
            elif days > STALE_WARN_DAYS:
                issues.append((SOFT, var, f"update_time 陈旧 {days:.1f} 天({t:%Y-%m-%d %H:%M})"))

    # ② 空表
    saw_record = False
    for kind, node in iter_records(obj):
        if kind == "record":
            saw_record = True
            for k, v in node.items():
                r = check_value(var, k, v)
                if r:
                    issues.append((r[0], var, f"{r[1]} @记录({node.get('code', node.get('name', '?'))})"))
        elif kind == "list" and len(node) == 0:
            # 只报有意义的顶层/一级列表（var 级），深层空列表多为结构占位
            pass
    if not saw_record and var not in EMPTY_OK:
        issues.append((HARD, var, "整表无记录(空/截断?)"))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-baseline", action="store_true", help="不读取/不写基线(纯体检)")
    ap.add_argument("--data-dir", default="data")
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"[sanity] data 目录不存在: {data_dir}")
        sys.exit(1)

    files = sorted(data_dir.glob("*.js"))
    print(f"[sanity] 扫描 {len(files)} 个 data/*.js  (只读,绝不改数据)")
    for fp in files:
        var = fp.stem
        text = fp.read_text(encoding="utf-8", errors="replace")
        if "window." not in text:
            continue  # 非注入文件
        obj = extract_json(strip_js_comments(text))
        check_var(var, obj)

    hard = [x for x in issues if x[0] == HARD]
    soft = [x for x in issues if x[0] == SOFT]
    print("")
    if hard:
        print(f"❌ 硬失败 {len(hard)} 项:")
        for lv, var, msg in hard:
            print(f"   [{var}] {msg}")
    if soft:
        print(f"⚠️ 软告警 {len(soft)} 项(不阻断):")
        for lv, var, msg in soft[:20]:
            print(f"   [{var}] {msg}")
    if not hard and not soft:
        print("✅ 全部体检项通过")
    print(f"\n[sanity] 结论: {len(hard)} 硬失败 / {len(soft)} 软告警 / {len(files)} 文件")
    sys.exit(1 if hard else 0)

if __name__ == "__main__":
    main()
