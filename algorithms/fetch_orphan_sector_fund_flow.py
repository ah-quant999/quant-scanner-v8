#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 孤儿模块 SECTOR_FUND_FLOW_TREND：板块资金流趋势（5/10/20/60 日滚动累计）

2026-08-02 从 v6 fetch_sector_fund_flow.py 移植，路径适配 v8 raw_data，去 fetch_logger 依赖。
原 fetch_sector_fund_flow.py 在 stock-scanner 仓（1200+ 行，含多源降级与历史累加），本仓聚焦保留
全部成熟逻辑（akshare 主源 + neodata/同花顺/westock 多源降级 + 历史累加 + carry-forward），仅改：
  - OUTPUT  → raw_data/sector_fund_flow_trend.json
  - HISTORY → raw_data/sector_fund_flow_history.json（放 raw_data，既不被 cloud_fetch 按类别清空，
              又随 api_push_raw 自动持久化到 main，跨运行/跨机器一致）
  - net_10d / trend_10d 富集：原由 sync_v6_to_v8._enrich_sector_fund_flow_trend 负责，现移入原生 fetcher
  - V6 历史预热种子：首次运行若 raw_data 历史缺失，从 V6_DATA 复制，避免趋势从零冷启动
  - 修复 v6 潜在 bug：load_westock_items 用到 io.open 但顶部未 import io

用法：python algorithms/fetch_orphan_sector_fund_flow.py
输出：raw_data/sector_fund_flow_trend.json  (+ raw_data/sector_fund_flow_history.json 累加器)
"""

import json
import os
import re
import time
import io
from datetime import datetime, timedelta
import requests
import sys
import subprocess

try:
    import akshare as ak
except ImportError:
    print("❌ akshare 未安装，将使用模拟数据")
    ak = None

# ── v8 路径：向上两级到仓根 + raw_data/ ──
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(ROOT, "raw_data", "sector_fund_flow_history.json")
OUTPUT_FILE = os.path.join(ROOT, "raw_data", "sector_fund_flow_trend.json")
BASE_DIR = ROOT  # 兼容 v6 代码里 BASE_DIR 派生路径（.neodata_token / westock 缓存）
V6_DATA_DIR = os.environ.get("V6_DATA_DIR", r"\E:\workspace\quant-scanner-v8\raw_data")

# 板块代码模式（东方财富内部编码 pt02xxxx / pt01xxxx），不应作为板块名称存入历史
_INVALID_SECTOR_CODE_RE = re.compile(r"^pt\d+[A-Za-z0-9]+$")


def is_valid_sector_name(name):
    """校验板块名称：过滤空值、纯代码、疑似内部编码"""
    if not name or not isinstance(name, str):
        return False
    name = name.strip()
    if not name:
        return False
    if _INVALID_SECTOR_CODE_RE.match(name):
        return False
    return True


# ──────────────────────────────────────────────────────────────
# 腾讯自选股(westock) 第三数据源 — 独立于东财(akshare) + 腾讯 neodata 的冗余管线
# 通过 subprocess 调用 fetch_sector_fund_flow_westock.py 解析 markdown 表格。
# v8 仓未内置该拉取器 → refresh_westock_cache 自动跳过（优雅降级）。
# ──────────────────────────────────────────────────────────────
WESTOCK_CACHE = os.path.join(ROOT, "raw_data", "sector_fund_flow_westock.json")
WESTOCK_PULLER = os.path.join(ROOT, "algorithms", "fetch_sector_fund_flow_westock.py")
WESTOCK_MAX_AGE_MIN = 30   # 缓存新鲜窗口（分钟）
WESTOCK_MAX_STALE_H = 18   # 超过此陈旧时长直接弃用缓存


def _westock_cache_fresh(path, max_age_min=WESTOCK_MAX_AGE_MIN):
    """判断 westock 缓存是否新鲜（存在且在有效期）"""
    if not os.path.exists(path):
        return False
    age_min = (time.time() - os.path.getmtime(path)) / 60.0
    return age_min <= max_age_min


def refresh_westock_cache():
    """缓存缺失或超龄时，调用独立拉取器刷新 westock 板块资金缓存（失败静默）。"""
    try:
        if _westock_cache_fresh(WESTOCK_CACHE):
            return
        print("  🔄 刷新腾讯自选股(westock)板块资金缓存...")
        if not os.path.exists(WESTOCK_PULLER):
            print("    ⚠️ 未找到 westock 拉取器，跳过")
            return
        env = dict(os.environ)
        proc = subprocess.run(
            [sys.executable, WESTOCK_PULLER],
            cwd=ROOT, capture_output=True, text=True,
            timeout=240, env=env,
        )
        if proc.returncode != 0:
            print(f"    ⚠️ westock 拉取器返回非零: {proc.returncode}")
            return
        if os.path.exists(WESTOCK_CACHE):
            print("    ✅ westock 缓存已刷新")
        else:
            print("    ⚠️ westock 缓存未生成")
    except Exception as e:
        print(f"  ⚠️ westock 缓存刷新异常: {e}")


def load_westock_items():
    """读取 westock 缓存；超期 18h 直接弃用。"""
    try:
        if not os.path.exists(WESTOCK_CACHE):
            return []
        age_h = (time.time() - os.path.getmtime(WESTOCK_CACHE)) / 3600.0
        if age_h > WESTOCK_MAX_STALE_H:
            print(f"  ⚠️ westock 缓存已陈旧({age_h:.1f}h)，弃用")
            return []
        with io.open(WESTOCK_CACHE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("items", [])
    except Exception:
        return []


def _seed_history_from_v6():
    """首次运行预热：若 raw_data 历史缺失，从 V6_DATA 复制，避免趋势从零冷启动。"""
    if os.path.exists(HISTORY_FILE):
        return
    src = os.path.join(V6_DATA_DIR, "sector_fund_flow_history.json")
    if os.path.exists(src):
        try:
            import shutil
            os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
            shutil.copy2(src, HISTORY_FILE)
            print(f"  🌱 V6 历史预热种子：复制 {src} → {HISTORY_FILE}")
        except Exception as e:
            print(f"  ⚠️ V6 历史种子复制失败: {e}")


def load_history():
    """加载历史数据（带损坏保护：解析失败则从 .bak 恢复）"""
    _seed_history_from_v6()
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                return data
            raise ValueError("empty or invalid format")
        except Exception as e:
            print(f"  ⚠️ [历史] 加载失败({e})，尝试.bak恢复")
            bak = HISTORY_FILE + ".bak"
            if os.path.exists(bak):
                try:
                    with open(bak, "r", encoding="utf-8") as f:
                        print(f"  ↩️ 从 {bak} 恢复历史")
                        return json.load(f)
                except Exception:
                    pass
    return {}


def save_history(history):
    """保存历史数据（只保留最近60天，带防清空保护）"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    # ── 防清空保护 ──
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                old = json.load(f)
            old_max = max((len(v) for v in old.values()), default=0)
            new_max = max((len(v) for v in history.values()), default=0)
            if old_max >= 10 and new_max <= 2:
                print(f"  🛑 [历史防清空] 拒绝保存：旧最大{old_max}天→新{new_max}天，保留旧文件")
                return
        except Exception:
            pass
    # 备份当前版本
    if os.path.exists(HISTORY_FILE):
        try:
            import shutil
            shutil.copy2(HISTORY_FILE, HISTORY_FILE + ".bak")
        except Exception:
            pass
    for name in history:
        history[name] = history[name][-60:]
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def _carry_forward_history(today):
    """全源失败时：对已有历史的板块沿用上次净额追加今日（carry-forward，已标记不计入趋势）。"""
    history = load_history()
    cf = 0
    for name in list(history.keys()):
        hist = history[name]
        if not hist:
            continue
        last_net = hist[-1].get("net", 0)
        carried_entry = {"date": today, "net": last_net, "carried": True}
        if hist and hist[-1].get("date") == today:
            hist[-1] = carried_entry
        else:
            hist.append(carried_entry)
            history[name] = hist[-60:]
        cf += 1
    if cf:
        save_history(history)
        print(f"  🔄 [历史carry-forward] {cf} 个板块沿用上次净额追加今日（已标记 carried）")


def calc_consecutive_days(records):
    """计算连续流入/流出天数"""
    if not records:
        return 0, "neutral"
    days = 0
    trend = None
    for record in reversed(records):
        net = record["net"]
        if trend is None:
            if net > 0:
                trend = "in"
            elif net < 0:
                trend = "out"
            else:
                return 0, "neutral"
            days = 1
        else:
            if trend == "in" and net > 0:
                days += 1
            elif trend == "out" and net < 0:
                days += 1
            else:
                break
    return days, trend


def _try_stock_fund_flow(flow_type):
    """兼容 akshare 新旧版 API（行业/概念资金流）"""
    if flow_type == "industry":
        try:
            return ak.stock_fund_flow_industry()
        except Exception:
            pass
        try:
            return ak.stock_board_industry_flow_em(symbol="今日")
        except Exception:
            return None
    elif flow_type == "concept":
        try:
            return ak.stock_fund_flow_concept()
        except Exception:
            pass
        try:
            return ak.stock_concept_fund_flow_hist() if hasattr(ak, 'stock_concept_fund_flow_hist') else None
        except Exception:
            pass
        try:
            return ak.stock_board_concept_flow_em(symbol="今日")
        except Exception:
            return None
    return None


def fetch_with_retry(func, max_retries=3, delay=2):
    """带重试的抓取函数"""
    for i in range(max_retries):
        try:
            return func()
        except Exception as e:
            if i < max_retries - 1:
                print(f"  ⚠️ 重试 {i+1}/{max_retries}: {e}")
                time.sleep(delay)
            else:
                raise e


def fetch_neodata_5d20d_supplement(sector_names):
    """用 neodata 接口补充 5日/20日累计净流入（返回失败就保持为0，绝不造假）"""
    import requests as req
    import time as tm

    alt_paths = [
        os.path.join(BASE_DIR, ".neodata_token"),
        "E:/WorkBuddy/resources/app.asar.unpacked/resources/builtin-skills/.neodata_token",
        os.path.expanduser("~/.workbuddy/.neodata_token"),
    ]
    token = None
    for tp in alt_paths:
        if os.path.exists(tp):
            try:
                with open(tp, "r") as f:
                    cache = json.load(f)
                    t = cache.get("token")
                    if t:
                        token = t
                        break
            except Exception:
                continue

    if not token:
        print("  ℹ️ neodata token 文件缺失或格式错误，跳过5d/20d补充")
        return {}

    def _call_neodata(query_desc, query_text):
        try:
            resp = req.post(
                "https://copilot.tencent.com/agenttool/v1/neodata",
                json={"query": query_text, "channel": "neodata", "sub_channel": "workbuddy"},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30
            )
            if resp.status_code != 200:
                print(f"    ❌ {query_desc} HTTP {resp.status_code}")
                return []
            data = resp.json()
            if not data.get("suc"):
                return []
            api_recall = data.get("data", {}).get("apiData", {}).get("apiRecall", [])
            results = []
            for item in api_recall:
                if item.get("type") != "板块当日资金主力统计":
                    continue
                content = item.get("content", "")
                for line in content.strip().split("\n"):
                    cols = [c.strip() for c in line.split("|")]
                    if len(cols) < 15:
                        continue
                    hdr_keywords = ["近N天数据", "板块名称", "板块代码", ":---:"]
                    if any(k in cols[2] for k in hdr_keywords):
                        continue
                    name = cols[5]
                    if not is_valid_sector_name(name):
                        continue
                    try:
                        net_wan = float(cols[12])
                        net5_wan = float(cols[13]) if cols[13] else 0
                        net20_wan = float(cols[14]) if cols[14] else 0
                    except (ValueError, TypeError):
                        continue
                    results.append({
                        "name": name,
                        "net": round(net_wan / 10000, 2),
                        "net_5d": round(net5_wan / 10000, 2),
                        "net_20d": round(net20_wan / 10000, 2),
                    })
            filtered = []
            for r in results:
                n5 = r.get("net_5d", 0)
                n20 = r.get("net_20d", 0)
                if n5 != 0 and n20 != 0 and abs(n5 - n20) < 0.1:
                    continue
                filtered.append(r)
            results = filtered
            print(f"    ✓ {query_desc}: {len(results)}只板块")
            return results
        except Exception as e:
            print(f"    ❌ {query_desc}: {e}")
            return []

    print("  🔍 [补充] 调用 neodata 获取5日/20日累计...")
    inflow_list = _call_neodata("当日流入TOP10(含5d/20d)", "今日A股行业板块和概念板块主力资金净流入TOP10，包含近5日和近20日累计净流入")
    outflow_list = _call_neodata("当日流出TOP10(含5d/20d)", "今日A股行业板块和概念板块主力资金净流出TOP10，包含近5日和近20日累计净流入")

    supplement = {}
    for item in inflow_list + outflow_list:
        name = item["name"]
        if name not in supplement or abs(item.get("net", 0)) > abs(supplement[name].get("net", 0)):
            supplement[name] = {
                "net_5d": item.get("net_5d", 0),
                "net_20d": item.get("net_20d", 0),
            }
    matched = sum(1 for n in sector_names if n in supplement)
    print(f"  ✅ neodata 补充: 匹配到 {matched}/{len(sector_names)} 个板块的5d/20d数据")
    return supplement


def fetch_akshare_ths_5d20d_backup(sector_names):
    """neodata 不可用时的备用方案：同花顺行业指数历史(涨跌幅) + 东财当日资金流估算（标注 source）"""
    import akshare as ak_mod
    result = {}
    try:
        industry_list = None
        concept_list = None
        for retry in range(3):
            try:
                industry_list = ak_mod.stock_board_industry_name_ths()
                break
            except Exception:
                if retry < 2:
                    time.sleep(3)
                else:
                    raise
        for retry in range(3):
            try:
                concept_list = ak_mod.stock_board_concept_name_ths()
                break
            except Exception:
                if retry < 2:
                    time.sleep(3)
                else:
                    concept_list = None
        ths_data = {}
        count = 0
        max_ind = min(25, len(industry_list) if industry_list is not None else 0)
        for idx, row in (industry_list.head(max_ind) if industry_list is not None else []).iterrows():
            name = str(row.get("name", "")).strip()
            if name not in sector_names:
                continue
            try:
                df = ak_mod.stock_board_industry_index_ths(
                    symbol=name,
                    start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d")
                )
                if len(df) >= 5:
                    ths_data[name] = df
                    count += 1
            except Exception:
                pass
        max_con = min(25, len(concept_list) if concept_list is not None else 0)
        for idx, row in (concept_list.head(max_con) if concept_list is not None else []).iterrows():
            name = str(row.get("name", "")).strip()
            if name not in sector_names or name in ths_data:
                continue
            try:
                df = ak_mod.stock_board_concept_index_ths(
                    symbol=name,
                    start_date=(datetime.now() - timedelta(days=30)).strftime("%Y%m%d"),
                    end_date=datetime.now().strftime("%Y%m%d")
                )
                if len(df) >= 5:
                    ths_data[name] = df
                    count += 1
            except Exception:
                pass
        print(f"  ✅ [备用] 同花顺: 获取到 {count} 个板块历史数据(行业+概念)")
        for name, df in ths_data.items():
            if len(df) < 3:
                continue
            df = df.sort_values("日期")
            if len(df) >= 5:
                recent_5 = df.tail(5)
                vol_5_yi = recent_5["成交额"].sum() / 1e8
                pct_5 = (recent_5.iloc[-1]["收盘价"] / recent_5.iloc[0]["开盘价"] - 1) * 100
                net_5d_est = round(vol_5_yi * pct_5 / 100, 2)
            else:
                net_5d_est = 0
            if len(df) >= 20:
                recent_20 = df.tail(20)
                vol_20_yi = recent_20["成交额"].sum() / 1e8
                pct_20 = (recent_20.iloc[-1]["收盘价"] / recent_20.iloc[0]["开盘价"] - 1) * 100
                net_20d_est = round(vol_20_yi * pct_20 / 100, 2)
            else:
                net_20d_est = 0
            if len(df) >= 60:
                recent_60 = df.tail(60)
                vol_60_yi = recent_60["成交额"].sum() / 1e8
                pct_60 = (recent_60.iloc[-1]["收盘价"] / recent_60.iloc[0]["开盘价"] - 1) * 100
                net_60d_est = round(vol_60_yi * pct_60 / 100, 2)
            else:
                net_60d_est = None
            MAX_REASONABLE = 5000.0
            if net_5d_est and abs(net_5d_est) > MAX_REASONABLE:
                net_5d_est = 0
            if net_20d_est and abs(net_20d_est) > MAX_REASONABLE:
                net_20d_est = 0
            result[name] = {
                "net_5d": net_5d_est,
                "net_20d": net_20d_est,
                "net_60d": net_60d_est,
                "source": "同花顺估算"
            }
        matched = sum(1 for n in sector_names if n in result)
        print(f"  ✅ [备用] 同花顺估算: 匹配到 {matched}/{len(sector_names)} 个板块")
    except Exception as e:
        print(f"  ⚠️ [备用] 同花顺方案也失败: {e}")
    return result


def _fetch_akshare_real_5d20d(top_list):
    """用akshare真实历史资金流接口获取5日/20日精确累计（快速失败模式）"""
    import akshare as ak_mod
    result = {}
    start_20d = (datetime.now() - timedelta(days=30)).strftime("%Y%m%d")
    end_d = datetime.now().strftime("%Y%m%d")
    sorted_items = sorted(top_list, key=lambda x: abs(x.get("net", 0)), reverse=True)[:10]
    total_ok = 0
    server_down = False
    for idx, item in enumerate(sorted_items):
        if server_down:
            continue
        name = item["name"]
        stype = item.get("type", "概念")
        func = (ak_mod.stock_board_industry_hist_em if stype == "行业"
                else ak_mod.stock_board_concept_hist_em)
        try:
            df = func(symbol=name, start_date=start_20d, end_date=end_d)
            if df is not None and len(df) >= 2:
                net_col = None
                for c in ["净额", "主力净流入"]:
                    if c in df.columns:
                        net_col = c
                        break
                if net_col and len(df) >= 2:
                    nets = [float(x) / 1e8 for x in df[net_col].astype(float).tolist()]
                    if len(nets) >= 5:
                        net_5d = round(sum(nets[-5:]), 2)
                        net_20d = round(sum(nets[-20:]), 2)
                        result[name] = {"net_5d": net_5d, "net_20d": net_20d}
                        total_ok += 1
                        print(f"    ✓ [{idx+1}/{len(sorted_items)}] {name}: 5d={net_5d}亿 20d={net_20d}亿")
        except Exception as e:
            err_name = type(e).__name__
            if "Connection" in err_name or "Timeout" in err_name or "Remote" in str(e):
                server_down = True
                print(f"    ✗ [{idx+1}] {name}: {err_name}(服务器不可用，跳过剩余)")
            else:
                print(f"    ✗ [{idx+1}] {name}: {err_name}")
        time.sleep(0.2)
    print(f"    ══ akshare真实历史: 成功{total_ok}/查询{min(10,len(sorted_items))}" + (" [服务器不可用]" if server_down else ""))
    return result


def fetch_from_neodata():
    """使用 NeoData 接口获取板块资金流向（备选数据源）"""
    import requests as req
    import re
    import time as tm

    token = None
    alt_paths = [
        os.path.join(BASE_DIR, ".neodata_token"),
        "E:/WorkBuddy/resources/app.asar.unpacked/resources/builtin-skills/.neodata_token",
        os.path.expanduser("~/.workbuddy/.neodata_token"),
    ]
    for tp in alt_paths:
        if os.path.exists(tp):
            try:
                with open(tp, "r") as f:
                    cache = json.load(f)
                    t = cache.get("token")
                    if t:
                        token = t
                        break
            except Exception:
                continue

    if not token:
        print("  ℹ️ neodata token 文件缺失或格式错误，已跳过")
        return []

    def _parse_neodata_response(api_recall):
        results = []
        seen_local = set()
        for item in api_recall:
            if item.get("type") != "板块当日资金主力统计":
                continue
            content = item.get("content", "")
            for line in content.strip().split("\n"):
                cols = [c.strip() for c in line.split("|")]
                if len(cols) < 15:
                    continue
                hdr_keywords = ["近N天数据", "板块名称", "板块代码", ":---:"]
                if any(k in cols[2] for k in hdr_keywords):
                    continue
                pt_type = cols[1]
                name = cols[5]
                if not is_valid_sector_name(name):
                    continue
                try:
                    net_wan = float(cols[12])
                    net5_wan = float(cols[13]) if cols[13] else 0
                    net20_wan = float(cols[14]) if cols[14] else 0
                except (ValueError, TypeError):
                    continue
                net_yi = round(net_wan / 10000, 2)
                net5_yi = round(net5_wan / 10000, 2)
                net20_yi = round(net20_wan / 10000, 2)
                if net5_yi != 0 and net20_yi != 0 and abs(net5_yi - net20_yi) < 0.1:
                    continue
                if name and net_yi != 0 and name not in seen_local:
                    seen_local.add(name)
                    results.append({
                        "name": name,
                        "net": net_yi,
                        "net_5d": net5_yi,
                        "net_20d": net20_yi,
                        "type": "行业" if "行业" in pt_type else "概念"
                    })
        return results

    def _call_neodata(query_desc, query_text):
        try:
            resp = req.post(
                "https://copilot.tencent.com/agenttool/v1/neodata",
                json={"query": query_text, "channel": "neodata", "sub_channel": "workbuddy"},
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                timeout=30
            )
            if resp.status_code != 200:
                return []
            data = resp.json()
            if not data.get("suc"):
                return []
            api_recall = data.get("data", {}).get("apiData", {}).get("apiRecall", [])
            return _parse_neodata_response(api_recall)
        except Exception:
            return []

    inflow_list = _call_neodata("当日流入TOP10", "今日A股行业板块和概念板块主力资金净流入TOP10，按净流入降序")
    outflow_list = _call_neodata("当日流出TOP10", "今日A股行业板块和概念板块主力资金净流出TOP10，按净流出降序")
    trend20_list = _call_neodata("近20日净流入TOP10", "近20个交易日A股行业板块和概念板块主力资金净流入TOP10，按净流入降序")
    trend20_out = _call_neodata("近20日净流出TOP10", "近20个交易日A股行业板块和概念板块主力资金净流出TOP10，按净流出降序")

    seen = set()
    top_list = []
    for item in inflow_list + outflow_list + trend20_list + trend20_out:
        if item["name"] not in seen:
            seen.add(item["name"])
            top_list.append(item)
    if top_list:
        top_list.sort(key=lambda x: x["net"], reverse=True)
        in_cnt = sum(1 for x in top_list if x["net"] > 0)
        out_cnt = sum(1 for x in top_list if x["net"] < 0)
        print(f"  ✅ neodata 汇总: {len(top_list)}只板块（流入{in_cnt} 流出{out_cnt}）")
        return top_list
    return []


def fetch_sector_flow():
    """抓取板块资金流向（v8 原生版，路径适配 raw_data）"""
    today = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    result = {
        "update_time": now_str,
        "data_type": "real",
        "summary": {},
        "sectors_in": [],
        "sectors_out": [],
        "top_list": [],
        "consecutive": {}
    }

    top_list = []
    use_mock = False

    if ak is not None:
        print("📊 正在抓取板块资金流向（v8 原生）...")
        try:
            print("  📊 方法1: 行业板块资金流...")
            df = fetch_with_retry(lambda: _try_stock_fund_flow("industry"), max_retries=2)
            if df is not None and len(df) > 0:
                has_main_net_col = "主力净流入" in df.columns
                for _, row in df.iterrows():
                    name = str(row.get("行业", "")).strip()
                    if has_main_net_col:
                        net_val = float(row.get("主力净流入", 0)) / 100000000
                    else:
                        net_val = float(row.get("净额", 0) or 0)
                    if name and net_val != 0:
                        if not is_valid_sector_name(name):
                            continue
                        top_list.append({"name": name, "net": round(net_val, 2),
                                         "net_5d": 0, "net_20d": 0, "type": "行业"})
                print(f"    ✅ 获取到 {len(top_list)} 个行业板块")
        except Exception as e:
            print(f"    ⚠️ 方法1失败: {e}")

        try:
            print("  📊 方法2: 概念板块资金流...")
            df2 = fetch_with_retry(lambda: _try_stock_fund_flow("concept"), max_retries=2)
            if df2 is not None and len(df2) > 0:
                has_main_net_col_2 = "主力净流入" in df2.columns
                for _, row in df2.iterrows():
                    name = str(row.get("行业", "")).strip()
                    if has_main_net_col_2:
                        net_val = float(row.get("主力净流入", 0)) / 100000000
                    else:
                        net_val = float(row.get("净额", 0) or 0)
                    if name and net_val != 0:
                        if not is_valid_sector_name(name):
                            continue
                        if not any(x["name"] == name for x in top_list):
                            top_list.append({"name": name, "net": round(net_val, 2),
                                             "net_5d": 0, "net_20d": 0, "type": "概念"})
                print(f"    ✅ 获取到 {len(top_list)} 个板块（含概念）")
        except Exception as e:
            print(f"    ⚠️ 方法2失败: {e}")

    # 行业数据缺失检测+重试
    if ak is not None and not any(s.get("type") == "行业" for s in top_list):
        print("  🔄 未获取到任何行业板块数据，重试方法1(行业)...")
        try:
            df = fetch_with_retry(lambda: _try_stock_fund_flow("industry"), max_retries=2)
            if df is not None and len(df) > 0:
                has_main_net_col = "主力净流入" in df.columns
                added = 0
                for _, row in df.iterrows():
                    name = str(row.get("行业", "")).strip()
                    if has_main_net_col:
                        net_val = float(row.get("主力净流入", 0)) / 100000000
                    else:
                        net_val = float(row.get("净额", 0) or 0)
                    if name and net_val != 0 and is_valid_sector_name(name):
                        if not any(x["name"] == name for x in top_list):
                            top_list.append({"name": name, "net": round(net_val, 2),
                                             "net_5d": 0, "net_20d": 0, "type": "行业"})
                            added += 1
                print(f"    ✅ 重试方法1获取到 {added} 个行业板块")
        except Exception as e:
            print(f"    ⚠️ 重试方法1失败: {e}")

    # neodata 补充 5d/20d
    if top_list and ak is not None:
        sector_names = [item["name"] for item in top_list]
        supplement = fetch_neodata_5d20d_supplement(sector_names)
        if not supplement:
            print("  ℹ️ neodata 无数据，尝试同花顺备用方案...")
            supplement = fetch_akshare_ths_5d20d_backup(sector_names)
        for item in top_list:
            name = item["name"]
            if name in supplement:
                s = supplement[name]
                net_5d = s.get("net_5d", 0)
                net_20d = s.get("net_20d", 0)
                net_60d = s.get("net_60d")
                if net_5d != 0 and net_20d != 0 and abs(net_5d - net_20d) < 0.1:
                    continue
                if net_5d != 0:
                    item["net_5d"] = net_5d
                if net_20d != 0:
                    item["net_20d"] = net_20d
                if net_60d is not None and net_60d != 0 and net_60d != net_20d:
                    item["net_60d"] = net_60d

        # === P0: 从本地history累加（最可靠，每天累积） ===
        hist_5d_count = 0
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as hf:
                hist_data = json.load(hf)
            for item in top_list:
                name = item["name"]
                if name in hist_data and len(hist_data[name]) >= 2:
                    real_entries = [x for x in hist_data[name] if not x.get("carried")]
                    nets = [x.get("net", 0) for x in real_entries]
                    if len(nets) >= 5:
                        item["net_5d"] = round(sum(nets[-5:]), 2)
                        item["source"] = "本地累加"
                        hist_5d_count += 1
                    if len(nets) >= 20:
                        item["net_20d"] = round(sum(nets[-20:]), 2)
                    if len(nets) >= 60:
                        item["net_60d"] = round(sum(nets[-60:]), 2)
            if hist_5d_count > 0:
                print(f"  📊 [P0本地累加] {hist_5d_count} 个板块有真实5日累计(来自{len(hist_data)}个板块history)")
        except Exception as e:
            print(f"  📊 [P0本地累加] 失败: {e}")

        # === P1: akshare东财历史接口（快速失败模式） ===
        print("  🔍 [P1东财历史] 尝试akshare接口获取5日/20日累计...")
        ak_hist = _fetch_akshare_real_5d20d(top_list)
        ak_matched = 0
        for item in top_list:
            name = item["name"]
            if name in ak_hist:
                h = ak_hist[name]
                item["net_5d"] = h["net_5d"]
                item["net_20d"] = h["net_20d"]
                item["source"] = "东财历史"
                ak_matched += 1
        if ak_matched > 0:
            print(f"  ✅ [P1东财历史] {ak_matched} 个板块覆盖为东财精确值")

        final_has_5d = sum(1 for x in top_list if x.get("net_5d", 0) != 0)
        print(f"  📋 5日累计: {final_has_5d}/{len(top_list)} 有数据, {len(top_list)-final_has_5d} 显示'--'")

        # 腾讯自选股 westock 第三源回填
        wsk_items = load_westock_items()
        if wsk_items:
            wsk_map = {x.get("name", "").strip(): x for x in wsk_items if x.get("name")}
            bf_5d = bf_net = 0
            for item in top_list:
                nm = item.get("name", "").strip()
                w = wsk_map.get(nm)
                if not w:
                    continue
                if item.get("net_5d", 0) == 0 and w.get("net_5d", 0) != 0:
                    item["net_5d"] = w["net_5d"]
                    bf_5d += 1
                if item.get("net", 0) == 0 and w.get("net", 0) != 0:
                    item["net"] = w["net"]
                    bf_net += 1
                _ws = item.get("source", "")
                if "腾讯自选股" not in _ws:
                    item["source"] = (_ws + "+腾讯自选股").strip("+")
            if bf_5d or bf_net:
                print(f"  🟣 [P2 westock] 回填: 5日净额×{bf_5d}, 当日净额×{bf_net}")

    # 如果真实数据获取失败，尝试 neodata / westock 兜底
    if not top_list:
        print("akshare数据获取失败，尝试腾讯自选股(westock)兜底...")
        wsk_items = load_westock_items()
        if wsk_items:
            top_list = [dict(x) for x in wsk_items]
            for it in top_list:
                it.setdefault("source", "腾讯自选股")
            in_cnt = sum(1 for x in top_list if x.get("net", 0) > 0)
            out_cnt = sum(1 for x in top_list if x.get("net", 0) < 0)
            print("westock 兜底获取到 %d 个板块（流入%d 流出%d）" % (len(top_list), in_cnt, out_cnt))
            result["data_type"] = "westock"
        else:
            print("westock 无数据，尝试 neodata 备选...")
            top_list = fetch_from_neodata()
            if top_list:
                in_cnt = sum(1 for x in top_list if x["net"] > 0)
                out_cnt = sum(1 for x in top_list if x["net"] < 0)
                print("neodata 获取到 %d 个板块（流入%d 流出%d）" % (len(top_list), in_cnt, out_cnt))
                result["data_type"] = "neodata"
            else:
                print("所有数据源均失败，返回空数据（铁律：宁可空着也不用假数据）")
                top_list = []
                result["data_type"] = "empty"
                result["data_note"] = "所有数据源不可用"
                _carry_forward_history(today)

    # 去重并排序
    seen = {}
    for item in top_list:
        name = item["name"]
        if name not in seen or abs(item["net"]) > abs(seen[name]["net"]):
            seen[name] = item
    top_list = list(seen.values())
    top_list.sort(key=lambda x: x["net"], reverse=True)
    result["top_list"] = top_list[:40]

    # 加载历史数据
    history = load_history()

    # 更新今日数据到历史
    for item in result["top_list"]:
        name = item["name"]
        net = item["net"]
        if not is_valid_sector_name(name):
            continue
        if name not in history:
            history[name] = []
        if history[name] and history[name][-1].get("date") == today:
            history[name][-1] = {"date": today, "net": net}
        else:
            history[name].append({"date": today, "net": net})
        history[name] = history[name][-60:]

    # 计算连续天数
    for item in result["top_list"]:
        name = item["name"]
        days, trend = calc_consecutive_days(history.get(name, []))
        item["consecutive_days"] = days
        item["trend"] = trend
        result["consecutive"][name] = {"days": days, "trend": trend}

    # 候选列表：含历史-only板块（保留长期趋势）
    candidate_map = {}
    for item in result["top_list"]:
        candidate_map[item["name"]] = dict(item)
    for name, hist in history.items():
        if name in candidate_map:
            continue
        if len(hist) < 5:
            continue
        candidate_map[name] = {
            "name": name,
            "net": hist[-1]["net"] if hist else 0,
            "net_5d": 0, "net_20d": 0, "net_60d": None,
            "type": "行业" if "概念" not in name else "概念",
            "consecutive_days": 0, "trend": "neutral",
        }
        days, trend = calc_consecutive_days(hist)
        candidate_map[name]["consecutive_days"] = days
        candidate_map[name]["trend"] = trend
    candidate_list = list(candidate_map.values())

    # 🛡 2026-08-19 主人令一劳永逸修复：对 candidate_list 做 net_5d/10d/20d/60d 累加
    #   原代码先累加 sectors_in/out（那时 sectors_in/out 还没 append 仍空 list → 循环无效）。
    #   同时也修阈值：10/20/60 日一律 >=3（history.max=9 天，原 >=20 永不可能满足）。层级最稳。
    seen_names = set()
    for item in candidate_list:
        nm = item.get("name", "")
        if not nm or nm in seen_names:
            continue
        seen_names.add(nm)
        hist = history.get(nm, [])

        def _real_n(hist, n):
            arr = [h for h in hist[-n:] if not h.get("carried")]
            return arr, round(sum(h["net"] for h in arr), 2)
        real_5, net_5d_val = _real_n(hist, 5)
        real_10, net_10d_val = _real_n(hist, 10)
        real_20, net_20d_val = _real_n(hist, 20)
        real_60, net_60d_val = _real_n(hist, 60)
        if net_5d_val != 0 and len(real_5) >= 3:
            item["net_5d"] = net_5d_val
            item["net_5d_days"] = len(real_5)
        if net_10d_val != 0 and len(real_10) >= 3:
            item["net_10d"] = net_10d_val
            item["net_10d_days"] = len(real_10)
        if net_20d_val != 0 and len(real_20) >= 3:
            item["net_20d"] = net_20d_val
            item["net_20d_days"] = len(real_20)
        if net_60d_val != 0 and len(real_60) >= 3:
            item["net_60d"] = net_60d_val
            item["net_60d_days"] = len(real_60)


    trend_5d = sorted([x for x in candidate_list if x.get("net_5d") is not None and x["net_5d"] != 0],
                      key=lambda x: x.get("net_5d", 0), reverse=True)
    trend_20d = sorted([x for x in candidate_list if x.get("net_20d") is not None and x["net_20d"] != 0],
                       key=lambda x: x.get("net_20d", 0), reverse=True)
    trend_60d = sorted([x for x in candidate_list if x.get("net_60d") is not None and x["net_60d"] != 0],
                       key=lambda x: x.get("net_60d", 0), reverse=True)
    # trend_10d：从 sectors_in/out 去重（net_10d 已注入）
    seen_t10 = set()
    trend_10d = []
    for key in ("sectors_in", "sectors_out"):
        for s in result.get(key, []):
            nm = s.get("name")
            if nm and nm not in seen_t10 and s.get("net_10d") is not None and s["net_10d"] != 0:
                seen_t10.add(nm)
                trend_10d.append(s)
    # 兜底：若 sectors_in/out 无 net_10d（历史不足10天），从 candidate 派生
    if not trend_10d:
        trend_10d = sorted([x for x in candidate_list if x.get("net_10d") is not None and x["net_10d"] != 0],
                           key=lambda x: x.get("net_10d", 0), reverse=True)
    result["trend_5d"] = trend_5d[:12]
    result["trend_10d"] = trend_10d[:12]
    result["trend_20d"] = trend_20d[:12]
    result["trend_60d"] = trend_60d[:12]

    # 保存历史
    save_history(history)

    # 🛡 2026-08-19 主人令一劳永逸修复：先构造 sectors_in/out，再做 net_5/10/20/60d 累加。
    #   原代码累加发生在 sectors_in/out 构造之前，循环遍历空 list → 累加完全失效 → 全部"暂无"。
    # 生成汇总
    THRESHOLD = 1.0
    for item in result["top_list"]:
        if item["net"] >= THRESHOLD:
            result["sectors_in"].append(item)
        elif item["net"] <= -THRESHOLD:
            result["sectors_out"].append(item)

    # 🛡 2026-08-19 主人令一劳永逸修复：从 candidate_list 按 name 同步 net_5d/10d/20d/60d
    #   到 sectors_in/out（top_list 引用，但 candidate_list 是 dict 浅拷贝，identity 不同，
    #   不能直接引用；只能按 name 显式复制）。
    cand_map_sync = {c["name"]: c for c in candidate_list}
    for item in result["sectors_in"] + result["sectors_out"]:
        nm = item.get("name", "")
        c = cand_map_sync.get(nm)
        if not c:
            continue
        for k in ("net_5d", "net_10d", "net_20d", "net_60d"):
            if item.get(k) in (None, 0) and c.get(k) not in (None, 0):
                item[k] = c[k]

    in_names = [f"{s['name']}({s['net']:.1f}亿)" for s in result["sectors_in"]]
    out_names = [f"{s['name']}({s['net']:.1f}亿)" for s in result["sectors_out"]]

    result["summary"] = {
        "in_count": len(result["sectors_in"]),
        "out_count": len(result["sectors_out"]),
        "in_text": "、".join(in_names[:5]) if in_names else "无",
        "out_text": "、".join(out_names[:5]) if out_names else "无",
        "alert": ""
    }

    alerts = []
    if len(result["sectors_in"]) >= 3:
        alerts.append(f"🔥 {len(result['sectors_in'])}个板块大幅流入")
    if len(result["sectors_out"]) >= 3:
        alerts.append(f"⚠️ {len(result['sectors_out'])}个板块大幅流出")
    in_details = []
    for s in result["sectors_in"][:3]:
        if s["net"] >= 10:
            detail = f"{s['name']}+{s['net']:.1f}亿"
            if s.get("consecutive_days", 0) > 1:
                detail += f"(连{s['consecutive_days']}天)"
            in_details.append(detail)
    if in_details:
        alerts.append("🚀 " + "、".join(in_details))
    out_details = []
    for s in result["sectors_out"][:3]:
        if s["net"] <= -10:
            detail = f"{s['name']}{s['net']:.1f}亿"
            if s.get("consecutive_days", 0) > 1:
                detail += f"(连{s['consecutive_days']}天)"
            out_details.append(detail)
    if out_details:
        alerts.append("💨 " + "、".join(out_details))
    result["summary"]["alert"] = "；".join(alerts) if alerts else "板块资金流向平稳"

    # 写文件
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 板块资金流向已保存: {OUTPUT_FILE}")
    dt = result.get("data_type", "unknown")
    dt_label = {"real": "真实数据", "neodata": "Neodata备选", "empty": "❌ 无数据", "mock": "⚠️ 模拟数据", "westock": "腾讯自选股兜底"}.get(dt, dt)
    print(f"   数据类型: {dt_label}")
    print(f"   大幅流入: {len(result['sectors_in'])} 个")
    print(f"   大幅流出: {len(result['sectors_out'])} 个")
    if result.get("summary", {}).get("alert"):
        print(f"   预警: {result['summary']['alert']}")
    return result


if __name__ == "__main__":
    try:
        fetch_sector_flow()
    except Exception as e:
        print(f"❌ 异常: {e}")
        raise
