#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性诊断：统计四量终极各组件命中数，判断 0 命中是「罕见」还是「全挂」。"""
import os, sys
BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)
from strategy_four_volume import fetch_volume_top_stocks, calc_siliang_ultimate_signal, fetch_a_daily, fetch_hk_daily

stocks = fetch_volume_top_stocks(60, 60, 60, 0)  # 不扫港股，排除 hk 代码干扰
print(f"池大小: {len(stocks)}")
c_yzc=c_jg=c_xc=c_four=c_xg=0
scanned=0
for s in stocks:
    code, name, market = s[0], s[1], s[2]
    try:
        df = fetch_a_daily(code)
        if df is None or len(df) < 60:
            continue
        df = calc_siliang_ultimate_signal(df)
        last = df.iloc[-1]
        scanned += 1
        if bool(last["四量终极_YZC"]): c_yzc+=1
        if bool(last["四量终极_JG"]): c_jg+=1
        if bool(last["四量终极_XC"]): c_xc+=1
        if bool(last["四量终极_FOUR"]): c_four+=1
        if bool(last["四量终极_XG"]): c_xg+=1
    except Exception as e:
        pass
print(f"实际扫描 A股: {scanned}")
print(f"  YZC(游资点火): {c_yzc}")
print(f"  JG(机构托底):  {c_jg}")
print(f"  XC(当天金叉):  {c_xc}")
print(f"  FOUR(四路翻多):{c_four}")
print(f"  XG(终极共振):  {c_xg}")
