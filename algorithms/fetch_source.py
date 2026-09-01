#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_source.py — v8 云端算法「数据源可靠性层」（2026-09-01 主人令·监督跑算法更先进）

要解决的核心问题（用户原话：数据来源必须真实及时 + 万一算法卡住怎么办）：
  1. baostock / akshare 底层 socket 调用常常没有超时 → 网络一抖就永久挂起
     （实测 calc_stock_rps / backtest_tdx 因此卡 30~60 分钟，整轮算法被拖死）。
  2. 某个源连续失败时仍反复重试，浪费整轮时间窗口。

设计铁律（不可逾越）：
  - 只用真实数据源（mootdx / 东财 / baostock / akshare / 腾讯 gtimg），
    **绝不编造 / 插值 / 回退到假数据**。
  - 超时 = 本次取数失败 → 交由各脚本既有的「多源兜底」逻辑切换下一个真实源。
  - 熔断器只「在冷却期内跳过近期连续失败的真实源、加速兜底」，不替代任何源、
    不产出任何假数据；冷却结束自动复位。

用法（各算法脚本 import 后用）：
  from fetch_source import socket_timeout, SOURCE_BREAKER
  if SOURCE_BREAKER.is_open("baostock"):
      return None                       # 该源近期连续失败，直接走下一真实源
  try:
      with socket_timeout(25):
          bs.login(); rs = bs.query_history_k_data_plus(...); bs.logout()
      SOURCE_BREAKER.mark_success("baostock")
  except Exception:
      SOURCE_BREAKER.mark_failure("baostock")
      return None
"""
import threading
import time
import contextlib
import socket

# 单次外部取数的网络超时（秒）。覆盖 baostock/akshare 底层 socket，避免永久挂起。
# 25s 足够一次正常 K 线查询，又远小于单脚本 30~60min 超时，故挂起能被快速感知并走兜底。
DEFAULT_SOCKET_TIMEOUT = 25

_breaker_lock = threading.Lock()
_breaker_state = {}  # name -> {"failures": int, "open_until": float(epoch)}

# 连续失败达到该次数 → 熔断（在冷却期内跳过该源，直接走兜底）
BREAKER_FAILURE_THRESHOLD = 3
# 熔断冷却时间（秒）：冷却期内该源被视为不可用，避免反复重试死源
BREAKER_COOLDOWN_SEC = 600


@contextlib.contextmanager
def socket_timeout(sec=DEFAULT_SOCKET_TIMEOUT):
    """在 with 块内为所有 socket 调用设置默认超时，退出后恢复。

    这样 baostock/akshare 内部任何阻塞的 socket 调用都会在 sec 秒后抛出
    socket.timeout，被各脚本既有 try/except 捕获 → 走下一真实源兜底。
    不影响成功路径上的任何数据（仅给无超时的网络调用加一把安全锁）。
    """
    prev = socket.getdefaulttimeout()
    socket.setdefaulttimeout(sec)
    try:
        yield
    finally:
        socket.setdefaulttimeout(prev)


class _SourceBreaker:
    """极简熔断器：记录每个真实源的最近连续失败，冷却期内标记为不可用。"""

    def mark_success(self, name):
        with _breaker_lock:
            _breaker_state.pop(name, None)

    def mark_failure(self, name):
        with _breaker_lock:
            st = _breaker_state.setdefault(name, {"failures": 0, "open_until": 0.0})
            st["failures"] += 1
            if st["failures"] >= BREAKER_FAILURE_THRESHOLD:
                st["open_until"] = time.time() + BREAKER_COOLDOWN_SEC

    def is_open(self, name):
        """True = 该源处于熔断冷却期（应跳过，直接走兜底源）。"""
        with _breaker_lock:
            st = _breaker_state.get(name)
            if not st:
                return False
            if st["open_until"] and time.time() < st["open_until"]:
                return True
            # 冷却结束，复位
            if st["open_until"] and time.time() >= st["open_until"]:
                _breaker_state.pop(name, None)
            return False

    def status(self):
        with _breaker_lock:
            return dict(_breaker_state)


SOURCE_BREAKER = _SourceBreaker()
