#!/usr/bin/env python3
"""
fetch_limit_up_ladder.py — 涨停连板梯队 + 强度榜
- 每日从 akshare 获取涨停池（stock_zt_pool_em）
- 按连板数分组，计算每只涨停股的强度分
- 输出 data/limit_up_ladder.json（供 v8 涨停联动卡片读取）
- 强度维度：连板高度 40% + 封单资金 35% + 封板质量 15% + 换手活跃度 10%
"""
import json
import os
import sys
import math
from datetime import datetime, timedelta

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(WORKSPACE, "data")
RAW_DIR = os.path.join(WORKSPACE, "raw_data")
OUTPUT = os.path.join(DATA_DIR, "limit_up_ladder.json")


def load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def inject_inline(index_path, var_name, obj):
    """把 window.VAR = {...} 幂等地注入到 index.html 的 </head> 之前。"""
    html = open(index_path, "r", encoding="utf-8").read()
    tag = f'<script>window.{var_name} = '
    # 移除旧的同变量 inline 块
    import re
    html = re.sub(rf'<script>window\.{var_name}\s*=.*?</script>\s*', '', html, flags=re.S)
    block = f'<script>window.{var_name} = {json.dumps(obj, ensure_ascii=False, separators=(",", ":"))};</script>'
    marker = '</head>'
    if marker in html:
        html = html.replace(marker, block + '\n' + marker, 1)
    else:
        html += '\n' + block
    open(index_path, "w", encoding="utf-8").write(html)


def get_trade_dates(n=5):
    """获取最近 n 个交易日（字符串 YYYYMMDD），优先用 akshare，失败则回退。"""
    dates = []
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if df is not None and len(df) > 0:
            all_dates = [str(d).replace("-", "").strip() for d in df["trade_date"]]
            today = datetime.now().strftime("%Y%m%d")
            past_dates = [d for d in all_dates if d <= today]
            dates = past_dates[-n:]
    except Exception as e:
        print(f"  ⚠ 交易日历获取失败: {e}")
    if not dates:
        # 回退：跳过周末
        d = datetime.now()
        while len(dates) < n:
            ds = d.strftime("%Y%m%d")
            if d.weekday() < 5:
                dates.append(ds)
            d -= timedelta(days=1)
    return dates


def fetch_zt_pool(date_str):
    """获取单日涨停池 DataFrame。"""
    import akshare as ak
    return ak.stock_zt_pool_em(date=date_str)


def norm_amount(x):
    """把元转成亿元并保留 2 位小数。"""
    try:
        v = float(x)
        return round(v / 1e8, 2)
    except Exception:
        return 0.0


def calc_strength(row, max_board, max_seal):
    """
    综合强度分 0-100。
    - 连板高度 40%：连板数 / 最高板 * 40
    - 封单资金 35%：log(封单资金+1) / log(最大封单+1) * 35
    - 封板质量 15%：炸板次数越少越好；首次封板时间越早越好
    - 换手活跃度 10%：换手率在 3%-20% 区间得分最高
    """
    board = int(row.get("连板数", 1) or 1)
    seal = float(row.get("封板资金", 0) or 0)
    max_seal = max(max_seal, 1)

    s_board = (board / max(max_board, 1)) * 40

    s_seal = (math.log(seal + 1) / math.log(max_seal + 1)) * 35

    bomb = int(row.get("炸板次数", 0) or 0)
    first_seal = str(row.get("首次封板时间", "154500"))
    try:
        first_min = int(first_seal[:2]) * 60 + int(first_seal[2:4])
    except Exception:
        first_min = 15 * 60
    # 925 最早 = 15 分，收盘 = 0 分
    time_score = max(0, min(15, (15 * 60 - first_min) / 60)) / 15 * 15
    s_quality = time_score - bomb * 3
    s_quality = max(0, min(15, s_quality))

    turnover = float(row.get("换手率", 0) or 0)
    if turnover < 3:
        s_turn = turnover / 3 * 10
    elif turnover <= 20:
        s_turn = 10
    else:
        s_turn = max(0, 10 - (turnover - 20) / 5)

    score = s_board + s_seal + s_quality + s_turn
    return round(min(100, score), 1)


def build_ladder(df):
    """把 DataFrame 转成连板梯队结构。"""
    max_board = int(df["连板数"].max()) if len(df) else 1
    max_seal = float(df["封板资金"].max()) if len(df) else 1

    rows = []
    for _, r in df.iterrows():
        code = str(r.get("代码", "")).zfill(6)
        name = r.get("名称", "")
        board = int(r.get("连板数", 1) or 1)
        industry = r.get("所属行业", "")
        seal = norm_amount(r.get("封板资金", 0))
        amount = norm_amount(r.get("成交额", 0))
        mv = norm_amount(r.get("流通市值", 0))
        seal_ratio = round(seal / max(mv, 0.01), 2)
        turnover = round(float(r.get("换手率", 0) or 0), 2)
        bomb = int(r.get("炸板次数", 0) or 0)
        first_seal = str(r.get("首次封板时间", ""))
        last_seal = str(r.get("最后封板时间", ""))
        pct = round(float(r.get("涨跌幅", 0) or 0), 2)
        stat = str(r.get("涨停统计", ""))  # e.g. "2/2"

        strength = calc_strength(r, max_board, max_seal)

        rows.append({
            "code": code,
            "name": name,
            "board": board,
            "industry": industry,
            "seal_amount": seal,
            "seal_ratio": seal_ratio,
            "amount": amount,
            "turnover": turnover,
            "bomb_count": bomb,
            "first_seal_time": first_seal,
            "last_seal_time": last_seal,
            "pct_chg": pct,
            "limit_stat": stat,
            "strength": strength,
        })

    # 按连板数分组，组内按强度降序
    groups = {}
    for r in rows:
        groups.setdefault(r["board"], []).append(r)

    ladder = []
    for board in sorted(groups.keys(), reverse=True):
        items = sorted(groups[board], key=lambda x: x["strength"], reverse=True)
        label = f"{board}板"
        if board >= 2 and len(items) > 1:
            label += f" × {len(items)}"
        elif board == 1 and len(items) > 1:
            label = f"首板 × {len(items)}"
        ladder.append({
            "board": board,
            "label": label,
            "count": len(items),
            "stocks": items,
        })

    return ladder, max_board


def build_sector_summary(df):
    """按所属行业统计今日涨停分布与强度。"""
    from collections import defaultdict
    sectors = defaultdict(lambda: {"count": 0, "total_seal": 0.0, "max_board": 0, "stocks": []})
    for _, r in df.iterrows():
        ind = r.get("所属行业", "其他") or "其他"
        sectors[ind]["count"] += 1
        sectors[ind]["total_seal"] += float(r.get("封板资金", 0) or 0)
        sectors[ind]["max_board"] = max(sectors[ind]["max_board"], int(r.get("连板数", 1) or 1))
        sectors[ind]["stocks"].append(str(r.get("名称", "")))

    # 转成列表并算强度分
    arr = []
    for name, s in sectors.items():
        # 行业强度：涨停数 50% + 最高连板 30% + 封单总额 20%
        count_score = min(50, s["count"] * 6)
        board_score = min(30, s["max_board"] * 6)
        seal_score = min(20, math.log(s["total_seal"] / 1e8 + 1) / math.log(100 + 1) * 20)
        strength = round(count_score + board_score + seal_score, 1)
        arr.append({
            "name": name,
            "count": s["count"],
            "max_board": s["max_board"],
            "total_seal": round(s["total_seal"] / 1e8, 2),
            "strength": strength,
            "lead_stocks": s["stocks"][:3],
        })
    arr.sort(key=lambda x: (x["strength"], x["count"]), reverse=True)
    return arr


def main():
    print("[fetch_limit_up_ladder] 启动...")
    try:
        import akshare as ak
    except ImportError:
        print("✗ akshare 未安装")
        return 1

    trade_dates = get_trade_dates(3)
    target_date = trade_dates[-1]  # 最近交易日
    print(f"  目标日期: {target_date}")

    df = None
    for d in reversed(trade_dates):
        try:
            df = fetch_zt_pool(d)
            if df is not None and len(df) > 0:
                target_date = d
                print(f"  成功获取 {d} 涨停池，共 {len(df)} 只")
                break
        except Exception as e:
            print(f"  ⚠ {d} 获取失败: {e}")

    if df is None or len(df) == 0:
        print("✗ 未能获取涨停池数据")
        return 1

    ladder, max_board = build_ladder(df)
    sectors = build_sector_summary(df)
    total = len(df)

    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "trade_date": target_date,
        "total": total,
        "max_board": max_board,
        "ladder": ladder,
        "sectors": sectors,
        "summary": {
            "highest_board_label": f"{max_board}板" if max_board > 0 else "无",
            "top_sector": sectors[0]["name"] if sectors else "-",
            "top_sector_strength": sectors[0]["strength"] if sectors else 0,
        },
    }

    save_json(OUTPUT, result)
    # 同时写入 raw_data，供 update_v8.py 生成 data/LIMIT_UP_LADDER.js
    raw_path = os.path.join(RAW_DIR, "limit_up_ladder.json")
    save_json(raw_path, result)
    print(f"✓ 已保存 {OUTPUT}（涨停 {total} 家，最高 {max_board} 板）")
    print(f"✓ 已注册 raw_data/limit_up_ladder.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
