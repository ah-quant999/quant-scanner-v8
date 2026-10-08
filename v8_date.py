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


def _fallback_is_trading_day(d: datetime.date) -> bool:
    """在线日历不可用时的兜底：**零依赖**静态权威节假日区间 + 周末判定。

    🔴 2026-09-25 阿狸咪·P0：本函数替代原「静默 weekday()<5」兜底。
      - 静态表来源 = v8_calendar.HOLIDAY_RANGES（零 import / 零副作用，任何环境可加载）；
        此前该表只存在于 guard_v8_freshness.py，而其顶部 `from update_v8 import ...`
        ⇒ 在未装第三方库的轻量 job（build_deploy gate / 依赖未装的 cn_fetch 早期步骤）
        根本 import 不进来 —— 这正是本 P0 的隐藏第二因。
      - 未覆盖年份（表外）退回周末判定，且不据此断言「是交易日」以外的结论。
    """
    iso = d.strftime("%Y-%m-%d")
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        import v8_calendar as _cal
        if _cal.covers(iso) and _cal.in_holiday_range(iso):
            return False
    except Exception:
        pass
    return d.weekday() < 5


def _is_trading_day_impl(date_str: str) -> bool:
    """底层交易日判断：优先复用 fetch_lhb 的交易日历（与既有链路保持一致）。"""
    # 🔴🔴 2026-10-01 国庆实证（workflow step5 'Invalid format' 事故根治）：
    #   fetch_lhb.is_trading_day 对「今天未被在线日历收录」一律保守判 True
    #   （该设计只防「交易日盘中日历滞后 ⇒ 误写空占位」），但**法定休市日全天
    #   都不可能被收录** ⇒ 2026-10-01 国庆被误判为交易日。
    #   放大器：fetch_lhb 的 log() print 到 stdout ⇒ workflow step5
    #   `$(python -c "import v8_date; print(v8_date.today_data_date())")`
    #   捕获两行（警告行+日期行）⇒ GITHUB_ENV/GITHUB_OUTPUT 'Invalid format'
    #   ⇒ step5 failure ⇒ 闸门输出断裂 ⇒ step9 起全 skipped + 问责 failure
    #   （run #36745715520 实证，接力派发整轮空烧）。
    #   修法（双层，fetch_lhb 自身行为零改动）：
    #   ① 静态权威日历（v8_calendar.HOLIDAY_RANGES = 国务院安排+交易所休市公告）
    #      前置校验：命中法定休市区间 ⇒ 直接判非交易日
    #      （与在线日历最终口径一致——休市日本就不在 trade_date 集合内，无冲突风险）；
    #   ② 调用 fetch_lhb 期间把其 stdout 警告重定向到 stderr
    #      （警告不丢，但不再污染 `$(...)` 命令替换 / GITHUB_ENV）。
    try:
        _root = os.path.dirname(os.path.abspath(__file__))
        if _root not in sys.path:
            sys.path.insert(0, _root)
        import v8_calendar as _cal
        if _cal.covers(date_str) and _cal.in_holiday_range(date_str):
            return False
        # 🔴 2026-10-10 根治（数据会话日误判·主人令「一劳永逸」）：静态权威表覆盖
        #   年份内的日期**离线终判**，不再依赖不稳定的在线日历层——本机/弱网实测：
        #   fetch_lhb 在线层把 2026-10-09/09-30 交易日误判 False（日历拉取失败时
        #   未收录日期保守判非交易），连带 data_session_date 把交易日归错会话。
        #   覆盖表 = 国务院安排 + 交易所休市公告 + MAKEUP_DAYS(调休交易日)：
        #   覆盖年份内 非假日 weekday 必为交易日；周末仅 MAKEUP_DAYS 内交易。
        if _cal.covers(date_str):
            import datetime as _dtmod
            _dd = _dtmod.datetime.strptime(date_str, "%Y-%m-%d").date()
            if _dd.weekday() < 5:
                return True
            return date_str in (getattr(_cal, "MAKEUP_DAYS", None) or set())
    except Exception:
        pass  # 静态日历不可用时回落原链路（fetch_lhb → 原兜底），不放大故障
    # 把 fetch_lhb 加入路径后复用其缓存的交易日历
    algo_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "algorithms")
    if algo_dir not in sys.path:
        sys.path.insert(0, algo_dir)
    try:
        from fetch_lhb import is_trading_day as _lhb_is_trading_day
        import contextlib
        import io
        _cap = io.StringIO()
        with contextlib.redirect_stdout(_cap):
            _r = _lhb_is_trading_day(date_str)
        if _cap.getvalue():
            sys.stderr.write(_cap.getvalue())
        return _r
    except Exception as e:
        # 🔴 2026-09-25 阿狸咪·P0（trading-day-gate-predeps-fallback）：
        #   原兜底 = `weekday() < 5` ⇒ **法定假日被判为交易日**（2026-09-25 中秋实证：
        #   V8_DATA_DATE 被标成休市日当天「假今日」+ 交易日闸门 proceed=true 全量空转）。
        #   改为回落零依赖静态权威日历 v8_calendar.HOLIDAY_RANGES（与 guard_v8_freshness 同源）。
        try:
            d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return True
        fb = _fallback_is_trading_day(d)
        print(f"⚠️ v8_date: 在线交易日历不可用({type(e).__name__}) ⇒ 回落静态权威日历: "
              f"{date_str} is_trading_day={fb}", file=sys.stderr)
        return fb
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


def data_session_date(
    ref: Optional[datetime.date | datetime.datetime | str] = None,
    close_hour: int = 15,
    close_min: int = 0,
) -> str:
    """解析「当前行情快照/K线数据归属的【已完成交易日】」——history/日期戳专用口径。

    与 resolve_data_date 的区别：交易日当天 close_hour 点收盘前，当日 K 线尚未
    走完、快照价实为上一交易日收盘 ⇒ 归上一交易日；收盘后归当天；非交易日回退
    上一交易日。

    🔴 2026-10-09 根治（金股池 history「日期错位双假行」·主人令「一劳永逸」）：
      - 09-30 02:14 跑批用 09-29 收盘 1638.5 冒充 09-30 行（运行自然日打戳）；
      - 10-01 假日跑批把 09-30 收盘 1613.0 盖上 10-01 的戳（日历失败回退自然日）。
      一律改用本口径打戳后，所有 history 写入变幂等（同日覆盖），假行不可能再产生。
    """
    if ref is None:
        dt = now_cst()
    elif isinstance(ref, datetime.datetime):
        dt = ref
    elif isinstance(ref, datetime.date):
        dt = datetime.datetime.combine(ref, datetime.time(12, 0))
    else:
        # 🔴 字符串可能带时刻（如 '2026-10-09 18:10:00'）——先按完整格式解析，
        #   失败再退纯日期（时刻缺失按 12:00 中性处理，不误判为收盘前）。
        _s = str(ref).strip()
        try:
            dt = datetime.datetime.strptime(_s[:19], "%Y-%m-%d %H:%M:%S")
        except Exception:
            dt = datetime.datetime.strptime(_s[:10], "%Y-%m-%d")
            dt = dt.replace(hour=12)
    d = dt.date()
    _is_td = _is_trading_day_impl(d.strftime("%Y-%m-%d"))
    if _is_td and dt.time() >= datetime.time(close_hour, close_min):
        return d.strftime("%Y-%m-%d")
    ref2 = d if not _is_td else d - datetime.timedelta(days=1)
    return last_trading_day(ref2)


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
