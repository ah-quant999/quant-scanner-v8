#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_delisted.py — 已下线停用（2026-09-09 主人令整链下线 DELISTED）。

历史职责：从 raw_data/delisted_stocks.json 生成 data/DELISTED.js（window.DELISTED_STOCKS）。
下线处置：
  · 前端「已下架股票目录」卡已从 index.html / logic.html 的 _renderV8StockLists() 删除；
  · data/DELISTED.js 已从仓库删除；
  · v8_health_check.py CARD_DEFS 移除 DELISTED 登记；
  · v8_rollback_guard.py CRITICAL_FILES / STRUCTURAL_MARKERS 移除 DELISTED 引用。
本脚本保留为 no-op 占位，避免任何遗留 import / 调度误触发重建污染数据。如需彻底删除可物理删。
"""
import sys


def main():
    print("[DISABLED] build_delisted.py 已于 2026-09-09 整链下线，不再生成 data/DELISTED.js。")


if __name__ == "__main__":
    main()
