#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_trading_day.py — 判断今天是否为 A 股交易日。
输出到 GitHub Actions 环境文件 $GITHUB_OUTPUT（键 is_trading_day）。
被 v8_algo_cloud.yml 用于控制非交易日跳过整个盘后算法链，避免覆盖上一交易日数据。
"""
import datetime
import os
import sys

ALGO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ALGO)

def main():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    try:
        from fetch_lhb import is_trading_day
        ok = is_trading_day(today)
    except Exception as e:
        # 交易日历拉取失败时保守视为交易日（不跳过），避免调休上班日漏跑
        print(f"⚠️ 交易日历判断失败: {e}，保守视为交易日继续跑")
        ok = True
    flag = "true" if ok else "false"
    print(f"📅 {today} is_trading_day={flag}")
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        try:
            with open(github_output, "a", encoding="utf-8") as f:
                f.write(f"is_trading_day={flag}\n")
        except Exception as e:
            print(f"⚠️ 写入 GITHUB_OUTPUT 失败: {e}")
    # 非交易日以非零退出码退出，便于 workflow if 条件判断（但不用这个，主要用 output）
    sys.exit(0 if ok else 0)

if __name__ == "__main__":
    main()
