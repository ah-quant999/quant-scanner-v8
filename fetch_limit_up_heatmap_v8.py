#!/usr/bin/env python3
"""
fetch_limit_up_heatmap.py — 涨停热力矩阵数据采集
- 每日获取涨停股票 → 按概念板块归类统计 → 构建30日热力矩阵
- 输出 data/limit_up_heatmap.json
- 数据源：akshare stock_zt_pool_strong_em（强势涨停池）
- 支持全量重建（检测到脏数据时自动拉取近30日重建）
"""
import json
import os
import sys
import time
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

try:
    import akshare as ak
except ImportError:
    print("✗ akshare 未安装")
    sys.exit(1)

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WORKSPACE, "raw_data")
OUTPUT = os.path.join(DATA_DIR, "limit_up_heatmap.json")

# 概念板块关键词 → 规范板块名 映射
# ⚠️ 匹配顺序按关键词长度降序（具体词优先于泛义词），故此处无需手动排序
# ⚠️ 规范板块名必须与 fixed_sectors / 前端展示一致
SECTOR_MAP = [
    # 半导体（最具体，优先）
    ("半导体", "半导体"), ("电子化学", "半导体"), ("元件", "半导体"),
    ("其他电子", "半导体"), ("芯片", "半导体"),
    # 新能源车
    ("新能源车", "新能源车"), ("汽车零部", "新能源车"), ("汽车整", "新能源车"),
    ("摩托车及", "新能源车"), ("能源车", "新能源车"),
    # 机器人（设备/自动化类）
    ("机器人", "机器人"), ("人形机器人", "机器人"), ("通用设备", "机器人"),
    ("专用设备", "机器人"), ("自动化设", "机器人"), ("工程机械", "机器人"),
    ("电机", "机器人"), ("轨交设备", "机器人"),
    # 光伏（含风电等新能源设备）
    ("光伏", "光伏"), ("光伏设备", "光伏"), ("风电设备", "光伏"),
    ("电源设备", "光伏"), ("太阳能", "光伏"),
    # 军工
    ("军工", "军工"), ("军工电子", "军工"), ("航空装备", "军工"),
    ("地面兵装", "军工"),
    # 消费电子
    ("消费电子", "消费电子"), ("光学光电", "消费电子"), ("家电零部", "消费电子"),
    ("白色家电", "消费电子"), ("黑色家电", "消费电子"), ("照明设备", "消费电子"),
    ("厨卫电器", "消费电子"), ("小家电", "消费电子"),
    # 通信设备
    ("通信设备", "通信设备"), ("通信服务", "通信设备"), ("6G", "通信设备"),
    # AI算力
    ("算力", "AI算力"), ("人工智能", "AI算力"), ("软件开发", "AI算力"),
    ("计算机设", "AI算力"), ("IT服务", "AI算力"), ("互联网电", "AI算力"),
    ("云", "AI算力"), ("数据要素", "AI算力"),
    # 医药
    ("医药", "医药"), ("化学制药", "医药"), ("医疗服务", "医药"),
    ("生物制品", "医药"), ("医疗器械", "医药"), ("中药", "医药"),
    ("动物保健", "医药"),
    # 电力
    ("电力", "电力"), ("电网设备", "电力"), ("其他电源", "电力"),
    ("发电", "电力"),
    # 地产链
    ("房地产", "地产链"), ("装修装饰", "地产链"), ("装修建材", "地产链"),
    ("建材", "地产链"),
    # 白酒消费
    ("白酒", "白酒消费"), ("饮料", "白酒消费"), ("乳品", "白酒消费"),
    ("食品", "白酒消费"), ("农产品加", "白酒消费"), ("调味发酵", "白酒消费"),
    ("非白酒", "白酒消费"),
    # 券商
    ("券商", "券商"), ("证券", "券商"), ("保险", "券商"), ("期货", "券商"),
    # 固态电池
    ("固态电池", "固态电池"), ("电池", "固态电池"), ("能源金属", "固态电池"),
    # 其他概念词（兜底归其他）
    ("低空经济", "其他"), ("信创", "其他"), ("无人驾驶", "其他"),
    ("储能", "其他"), ("物联网", "其他"), ("智能驾驶", "其他"),
    ("光模块", "其他"), ("液冷", "其他"), ("氢能源", "其他"),
    ("商业航天", "其他"),
]


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def get_trade_dates(n=15):
    """获取最近n个交易日"""
    dates = []
    # 仅用 sina 源（akshare 1.18+ 已删除 _sse 变体，避免必然失败的冗余调用）
    for src in ("tool_trade_date_hist_sina",):
        try:
            df = getattr(ak, src)()
            if df is not None and len(df) > 0:
                all_dates = [str(d).replace("-", "") for d in df["trade_date"]]
                today = datetime.now().strftime("%Y%m%d")
                past_dates = [d for d in all_dates if d <= today]
                dates = past_dates[-n:]
                break
        except Exception as e:
            print(f"  ⚠ {src} 失败: {e}")
    if not dates:
        # 回退：倒推 n*2 个自然日，跳过周末 + 本地 2026 节假日表
        holidays_2026 = {
            "20260101","20260102","20260103",
            "20260216","20260217","20260218","20260219","20260220","20260222",
            "20260404","20260405","20260406",
            "20260501","20260502","20260503","20260504","20260505",
            "20260619","20260620","20260621",
        }
        d = datetime.now()
        while len(dates) < n:
            ds = d.strftime("%Y%m%d")
            if d.weekday() < 5 and ds not in holidays_2026:
                dates.append(ds)
            d -= timedelta(days=1)
        dates.reverse()
    return dates


def get_limit_up_by_date(date_str):
    """获取指定日期的涨停股票数据"""
    stocks = []
    # 方案1：强势股池
    try:
        df = ak.stock_zt_pool_strong_em(date=date_str)
        if df is not None and len(df) > 0:
            for _, row in df.iterrows():
                stocks.append({
                    "name": str(row.get("名称", "")),
                    "code": str(row.get("代码", "")),
                    "pct_chg": float(row.get("涨跌幅", 0)) if row.get("涨跌幅") else 0,
                    "limit_times": int(row.get("涨停次数", 1)) if row.get("涨停次数") else 1,
                    "sector": str(row.get("所属行业", "")),
                })
            return stocks
    except Exception as e:
        pass

    # 方案2：当日涨停池
    try:
        df = ak.stock_zt_pool_em(date=date_str)
        if df is not None and len(df) > 0:
            for _, row in df.iterrows():
                stocks.append({
                    "name": str(row.get("名称", "")),
                    "code": str(row.get("代码", "")),
                    "pct_chg": float(row.get("涨跌幅", 0)) if row.get("涨跌幅") else 0,
                    "limit_times": int(row.get("连板数", 1)) if row.get("连板数") else 1,
                    "sector": str(row.get("所属行业", "")),
                })
            return stocks
    except Exception:
        pass

    return stocks


def classify_by_sector(stocks):
    """将涨停股票归类到概念板块，返回 {板块名: {股票名: 涨停次数}}"""
    sector_counts = defaultdict(lambda: defaultdict(int))

    # 按关键词长度降序，优先匹配更具体的词（如「汽车零部」先于「车」）
    kw_map = sorted(SECTOR_MAP, key=lambda x: -len(x[0]))

    for s in stocks:
        sector_str = (s.get("sector", "") or "").strip()
        if not sector_str:
            sector_counts["其他"][s["name"]] = s.get("limit_times", 1)
            continue

        matched = False
        for kw, canonical in kw_map:
            if kw.lower() in sector_str.lower():
                sector_counts[canonical][s["name"]] = s["limit_times"]
                matched = True
                break

        if not matched:
            sector_counts["其他"][s["name"]] = s.get("limit_times", 1)

    return sector_counts


def build_heatmap(days_data):
    """
    构建热力矩阵
    days_data: [(date_str, {sector: {name: count}}), ...]
    返回 (dates_list, sectors_list)
    """
    # 固定规范板块（必须与前端展示、SECTOR_MAP 规范名一致）
    # 2026-07-24 移除：光伏、固态电池（持续多日 sum=0，无跟踪价值；当日有数据再动态纳入）
    fixed_sectors = ["其他", "半导体", "军工",
                     "消费电子", "通信设备", "AI算力", "医药", "电力",
                     "地产链", "白酒消费", "券商", "机器人", "新能源车"]

    # 固定板块始终纳入，再补充数据中出现的其他板块
    all_sectors_set = set(fixed_sectors)
    for _, sc in days_data:
        all_sectors_set.update(sc.keys())

    # 排序：固定板块保底优先，其余按最后一天涨停数降序；最终取前15
    last_day_sc = days_data[-1][1] if days_data else {}
    sorted_sectors = sorted(
        all_sectors_set,
        key=lambda x: (0 if x in fixed_sectors else 1,
                       sum(last_day_sc.get(x, {}).values())),
        reverse=True
    )[:15]

    dates = []
    sectors_output = []

    for sec in sorted_sectors:
        sec_data = []
        for date_str, sc in days_data:
            dates.append(date_str)  # 每次都会append，后面去重
            cnt = sum(sc.get(sec, {}).values())
            sec_data.append(cnt)
        sectors_output.append({"name": sec, "data": sec_data})

    # dates 去重（因为上面循环中每个板块都会append）
    unique_dates = []
    seen = set()
    for d in dates:
        if d not in seen:
            unique_dates.append(d)
            seen.add(d)

    return unique_dates, sectors_output


def _check_dates_integrity(existing_dates):
    """检查已有日期序列是否完整覆盖最近30个交易日，防止丢列/错列。"""
    if not existing_dates or len(existing_dates) < 30:
        return False, f"日期不足30列 ({len(existing_dates)})"
    if len(existing_dates) != len(set(existing_dates)):
        return False, "存在重复日期"
    expected = get_trade_dates(30)
    expected_labels = {datetime.strptime(d, "%Y%m%d").strftime("%m/%d") for d in expected}
    actual_set = set(existing_dates)
    missing = expected_labels - actual_set
    extra = actual_set - expected_labels
    if missing:
        return False, f"缺失交易日 {sorted(missing)}"
    if extra:
        return False, f"包含非最近30日日期 {sorted(extra)}"
    return True, "OK"


def needs_rebuild(existing):
    """判断是否需要全量重建"""
    dates = existing.get("dates", [])
    if not dates or len(dates) < 3:
        return True
    # 有重复日期 → 需要重建
    if len(dates) != len(set(dates)):
        return False  # 不在这里触发，由清洗逻辑处理；改为让调用方决定
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true", help="强制全量重建近30个交易日")
    args = parser.parse_args()

    print("=" * 60)
    print(f"  涨停热力矩阵采集  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    existing = load_json(OUTPUT, {"dates": [], "sectors": []})
    existing_dates = existing.get("dates", [])

    # ── 判断是否需要全量重建 ──
    need_rebuild = False
    if args.rebuild:
        print("  🔄 用户指定 --rebuild，触发全量重建")
        need_rebuild = True
    elif len(existing_dates) != len(set(existing_dates)):
        print(f"  🧹 检测到重复日期（{len(existing_dates)}列中有重复），触发全量重建")
        need_rebuild = True
    elif len(existing_dates) < 5:
        print(f"  📊 历史数据不足（{len(existing_dates)}列），触发全量重建")
        need_rebuild = True
    else:
        ok, reason = _check_dates_integrity(existing_dates)
        if not ok:
            print(f"  🧹 日期序列异常：{reason}，触发全量重建")
            need_rebuild = True

    if need_rebuild:
        # ── 全量重建：拉取近30个交易日 ──
        trade_dates = get_trade_dates(30)
        print(f"  📅 拉取 {len(trade_dates)} 个交易日数据...")

        days_data = []
        for td in trade_dates:
            dt_obj = datetime.strptime(td, "%Y%m%d")
            label = dt_obj.strftime("%m/%d")
            stocks = get_limit_up_by_date(td)
            time.sleep(0.3)  # 限流

            if stocks:
                sc = classify_by_sector(stocks)
                total = sum(sum(v.values()) for v in sc.values())
                print(f"    {label}: {total} 只涨停")
                days_data.append((label, sc))
            else:
                print(f"    {label}: 无数据（可能非交易日或休市）")
                days_data.append((label, {}))

        if not days_data:
            print("  ✗ 未获取到任何数据")
            return

        new_dates, new_sectors = build_heatmap(days_data)

    else:
        # ── 增量更新：只更新今天 ──
        today = datetime.now()
        today_str = today.strftime("%m/%d")
        today_yyyymmdd = today.strftime("%Y%m%d")

        # 非交易日（周末/节假日）跳过，避免 API 返回前交易日脏数据污染
        trade_dates = get_trade_dates(1)
        if not trade_dates or trade_dates[-1] != today_yyyymmdd:
            print(f"  ⚠️ 今日 {today_str} 非交易日，跳过增量更新")
            return

        limit_stocks = get_limit_up_by_date(today_yyyymmdd)
        if not limit_stocks:
            print("  ⚠️ 今日无涨停数据（休市或API异常），保持原数据不变")
            existing["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            print(f"  ✅ 保持原数据: {OUTPUT}")
            return

        sector_counts = classify_by_sector(limit_stocks)
        print(f"  📊 今日({today_str}): {len(limit_stocks)} 只涨停")

        # 合并新旧板块（固定板块保底优先）
        # 2026-07-24 移除：光伏、固态电池（持续多日 sum=0）
        fixed_sectors = ["其他", "半导体", "军工",
                         "消费电子", "通信设备", "AI算力", "医药", "电力",
                         "地产链", "白酒消费", "券商", "机器人", "新能源车"]
        all_sec = set(fixed_sectors) | set(s["name"] for s in existing.get("sectors", [])) | set(sector_counts.keys())
        # 防御：剔除「10日全 0 且今日仍 0」的板块（米业/国产电池这类历史遗留不会复活）
        all_sec = {x for x in all_sec if not (
            all(v == 0 for v in [
                next((s["data"][i] for s in existing.get("sectors", []) if s["name"] == x), 0)
                for i in range(len(existing_dates))
            ]) and sum(sector_counts.get(x, {}).values()) == 0
        )}
        sorted_sec = sorted(
            all_sec,
            key=lambda x: (0 if x in fixed_sectors else 1,
                           sum(sector_counts.get(x, {}).values())),
            reverse=True
        )[:15]

        # 日期：如果今天已存在则替换，否则追加
        ed = list(existing_dates)
        if today_str in ed:
            # 替换今天的列（保留今天位置之后的所有日期，不再截断！）
            idx = len(ed) - 1 - ed[::-1].index(today_str)
            new_dates = ed[:idx] + [today_str] + ed[idx + 1:]
        else:
            new_dates = (ed[-29:] + [today_str]) if len(ed) >= 29 else (ed + [today_str])
        new_dates = new_dates[-30:]

        # 用「日期→板块→数值」映射做精确对齐，避免丢列/错位
        old_by_date = {}
        for i, dd in enumerate(existing_dates):
            old_by_date[dd] = {
                s["name"]: (s["data"][i] if i < len(s["data"]) else 0)
                for s in existing.get("sectors", [])
            }

        new_sectors = []
        for sec in sorted_sec:
            row = []
            for dd in new_dates:
                if dd == today_str:
                    row.append(sum(sector_counts.get(sec, {}).values()))
                else:
                    row.append(old_by_date.get(dd, {}).get(sec, 0))
            new_sectors.append({"name": sec, "data": row})

    # ── 写入结果 ──
    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dates": new_dates if need_rebuild else new_dates,
        "sectors": new_sectors if need_rebuild else new_sectors,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ 热力矩阵: {len(result['dates'])} 日 × {len(result['sectors'])} 板块")
    for s in result["sectors"]:
        total = sum(s["data"])
        print(f"     {s['name']}: {s['data']}  (累计{total})")
    print(f"\n  输出: {OUTPUT}")


def generate():
    """供 cloud_fetch_v8.py 调用的无参数入口：自动判断重建/增量，返回结果 dict。"""
    import argparse
    class Args:
        rebuild = False
    # 直接复用 main 的内部逻辑：手动执行判断
    existing = load_json(OUTPUT, {"dates": [], "sectors": []})
    existing_dates = existing.get("dates", [])
    need_rebuild = False
    if len(existing_dates) != len(set(existing_dates)):
        need_rebuild = True
    elif len(existing_dates) < 5:
        need_rebuild = True
    else:
        ok, reason = _check_dates_integrity(existing_dates)
        if not ok:
            print(f"  🧹 日期序列异常：{reason}，触发全量重建")
            need_rebuild = True

    if need_rebuild:
        trade_dates = get_trade_dates(30)
        days_data = []
        for td in trade_dates:
            dt_obj = datetime.strptime(td, "%Y%m%d")
            label = dt_obj.strftime("%m/%d")
            stocks = get_limit_up_by_date(td)
            time.sleep(0.3)
            if stocks:
                sc = classify_by_sector(stocks)
                total = sum(sum(v.values()) for v in sc.values())
                print(f"    {label}: {total} 只涨停")
                days_data.append((label, sc))
            else:
                print(f"    {label}: 无数据")
                days_data.append((label, {}))
        if not days_data:
            return None
        new_dates, new_sectors = build_heatmap(days_data)
    else:
        today = datetime.now()
        today_str = today.strftime("%m/%d")
        today_yyyymmdd = today.strftime("%Y%m%d")
        trade_dates = get_trade_dates(1)
        if not trade_dates or trade_dates[-1] != today_yyyymmdd:
            print(f"  ⚠️ 今日 {today_str} 非交易日，跳过增量更新")
            return existing
        limit_stocks = get_limit_up_by_date(today_yyyymmdd)
        if not limit_stocks:
            print("  ⚠️ 今日无涨停数据，保持原数据不变")
            existing["update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(OUTPUT, "w", encoding="utf-8") as f:
                json.dump(existing, f, ensure_ascii=False, indent=2)
            return existing
        sector_counts = classify_by_sector(limit_stocks)
        fixed_sectors = ["其他", "半导体", "军工",
                         "消费电子", "通信设备", "AI算力", "医药", "电力",
                         "地产链", "白酒消费", "券商", "机器人", "新能源车"]
        all_sec = set(fixed_sectors) | set(s["name"] for s in existing.get("sectors", [])) | set(sector_counts.keys())
        all_sec = {x for x in all_sec if not (
            all(v == 0 for v in [
                next((s["data"][i] for s in existing.get("sectors", []) if s["name"] == x), 0)
                for i in range(len(existing_dates))
            ]) and sum(sector_counts.get(x, {}).values()) == 0
        )}
        sorted_sec = sorted(
            all_sec,
            key=lambda x: (0 if x in fixed_sectors else 1,
                           sum(sector_counts.get(x, {}).values())),
            reverse=True
        )[:15]
        ed = list(existing_dates)
        if today_str in ed:
            idx = len(ed) - 1 - ed[::-1].index(today_str)
            new_dates = ed[:idx] + [today_str] + ed[idx + 1:]
        else:
            new_dates = (ed[-29:] + [today_str]) if len(ed) >= 29 else (ed + [today_str])
        new_dates = new_dates[-30:]
        old_by_date = {}
        for i, dd in enumerate(existing_dates):
            old_by_date[dd] = {
                s["name"]: (s["data"][i] if i < len(s["data"]) else 0)
                for s in existing.get("sectors", [])
            }
        new_sectors = []
        for sec in sorted_sec:
            row = []
            for dd in new_dates:
                if dd == today_str:
                    row.append(sum(sector_counts.get(sec, {}).values()))
                else:
                    row.append(old_by_date.get(dd, {}).get(sec, 0))
            new_sectors.append({"name": sec, "data": row})

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "dates": new_dates,
        "sectors": new_sectors,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  ✅ 热力矩阵: {len(result['dates'])} 日 × {len(result['sectors'])} 板块")
    return result


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"  ❌ 涨停热力矩阵失败: {e}")
        raise
