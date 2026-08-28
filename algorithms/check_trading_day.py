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

# 🛡 2026-08-19 一劳永逸根因：v8_algo_cloud.yml 19:15 cron 连续多天 0 算法执行，
# 17 张盘后/选股卡停在 08:27 红卡——皆因本脚本 print("📅 ...") 在 cn runner
# （中文 Windows 默认 GBK 终端）触发 UnicodeEncodeError → exit 1 → workflow 失败。
# cloud_fetch_v8.py 早就有同款兜底（line 33-37），本脚本漏抄。补齐：
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass
# 兜底再 wrap print：即便 reconfigure 失败（极老版 Python），emoji 也降级为 ASCII。
_orig_print = print
def print(*args, **kwargs):
    try:
        _orig_print(*args, **kwargs)
    except UnicodeEncodeError:
        s = " ".join(str(a) for a in args)
        _orig_print(s.encode("ascii", "replace").decode("ascii"), **kwargs)


def main():
    # 2026-08-29 主人令：周末/假期审计验证时，可通过 V8_FORCE_RUN=1 强制视为交易日运行
    # （用于「代码审计/验证」场景刷新上一交易日数据，不依赖交易日历）。仅 manual dispatch 传入，
    # 日常 cron 不受影响（仍按交易日历 gate，避免周末无意义覆盖）。
    if os.environ.get("V8_FORCE_RUN", "") == "1":
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        print(f"📅 {today} V8_FORCE_RUN=1 → 强制 is_trading_day=true（周末/假期审计验证）")
        github_output = os.environ.get("GITHUB_OUTPUT")
        if github_output:
            try:
                with open(github_output, "a", encoding="utf-8") as f:
                    f.write("is_trading_day=true\n")
            except Exception as e:
                print(f"⚠️ 写入 GITHUB_OUTPUT 失败: {e}")
        sys.exit(0)
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
