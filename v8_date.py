#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8_date.py — v8 统一交易日历与数据日期中枢

目标：消灭全链路各脚本各自用 datetime.now() 打日期的「冒充今日」问题。
所有写入 raw_data / data 的日期字段，均应通过本模块解析为「真实 A 股交易日」。

原则：
- 若 ref_date 是交易日 → 返回该日。
- 若 ref_date 是非交易日（周末/假期） → 返回往前最近一个交易日。
- FORCE_RUN 只控制「是否跑 workflow」，不改变「数据属于哪天」。
"""
from __future__ import annotations

import datetime
import os
import sys
from typing import Optional

# 中国标准时间（北京时间）
TZ_CN = datetime.timezone(datetime.timedelta(hours=8))


def now_cst() -> datetime.datetime:
    """当前中国标准时间 datetime。"""
    return datetime.datetime.now(TZ_CN)


def _is_trading_day_impl(date_str: str) -> bool:
    """底层交易日判断：优先复用 fetch_lhb 的交易日历（与既有链路保持一致）。"""
    # 把 fetch_lhb 加入路径后复用其缓存的交易日历
    algo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "algorithms")
    if algo_dir not in sys.path:
        sys.path.insert(0, algo_dir)
    try:
        from fetch_lhb import is_trading_day as _lhb_is_trading_day
        return _lhb_is_trading_day(date_str)
    except Exception:
        # 交易日历不可用时的保守兜底：周末视为非交易，其他视为交易
        try:
            d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return True
        return d.weekday() < 5
    finally:
        if algo_dir in sys.path and sys.path[0] == algo_dir:
            sys.path.pop(0)


def is_trading_day(date: Optional[datetime.date | datetime.datetime | str] = None) -> bool:
    """判断给定日期是否为 A 股交易日；缺省为今天。"""
    if date is None:
        date = now_cst().date()
    if isinstance(date, datetime.datetime):
        date = date.date()
    if isinstance(date, datetime.date):
        date_str = date.strftime("%Y-%m-%d")
    else:
        date_str = date
    return _is_trading_day_impl(date_str)


def last_trading_day(
    ref: Optional[datetime.date | datetime.datetime | str] = None,
    max_lookback: int = 15,
) -> str:
    """返回 ref 当天或往前最近一个 A 股交易日（字符串 YYYY-MM-DD）。"""
    if ref is None:
        d = now_cst().date()
    elif isinstance(ref, datetime.datetime):
        d = ref.date()
    elif isinstance(ref, datetime.date):
        d = ref
    else:
        d = datetime.datetime.strptime(ref, "%Y-%m-%d").date()

    for _ in range(max_lookback + 1):
        ds = d.strftime("%Y-%m-%d")
        if _is_trading_day_impl(ds):
            return ds
        d -= datetime.timedelta(days=1)
    # 兜底：最多回退 max_lookback 天仍找不到，返回 ref 前一天（避免返回空）
    return (now_cst().date() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")


def resolve_data_date(
    ref: Optional[datetime.date | datetime.datetime | str] = None,
) -> str:
    """解析「数据应该属于哪一天」：交易日即当天，非交易日回退到上一交易日。"""
    return last_trading_day(ref)


def today_data_date() -> str:
    """今天对应的数据日期（与 resolve_data_date(now_cst()) 等价）。"""
    return resolve_data_date(now_cst())


def trading_days_between(start: str, end: str) -> int:
    """统计 [start, end] 之间（含端点）的交易日数量；要求日期格式 YYYY-MM-DD。"""
    s = datetime.datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.datetime.strptime(end, "%Y-%m-%d").date()
    if s > e:
        s, e = e, s
    cnt = 0
    d = s
    while d <= e:
        if _is_trading_day_impl(d.strftime("%Y-%m-%d")):
            cnt += 1
        d += datetime.timedelta(days=1)
    return cnt


def close_datetime(date_str: str, time_str: str = "15:00:00") -> str:
    """返回「date_str 收盘时刻」的格式化字符串，默认 15:00:00。"""
    return f"{date_str} {time_str}"


def main() -> None:
    """CLI：打印今日数据日期，供工作流一步设置 GITHUB_OUTPUT / GITHUB_ENV。"""
    today = now_cst().strftime("%Y-%m-%d")
    data_date = today_data_date()
    print(f"today={today} data_date={data_date} is_trading_day={is_trading_day()}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        try:
            with open(github_output, "a", encoding="utf-8") as f:
                f.write(f"data_date={data_date}\n")
        except Exception as e:
            print(f"⚠️ 写入 GITHUB_OUTPUT 失败: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
