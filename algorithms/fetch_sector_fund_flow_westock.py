#!/usr/bin/env python3
"""
板块资金流 — 腾讯自选股(westock) 第三源独立拉取器
数据源：westock-data-skillhub (npx 单文件包，腾讯自选股行情接口，独立管线)
输出：data/sector_fund_flow_westock.json (归一化缓存，供 fetch_sector_fund_flow.py 第三源使用)

设计：
- 仅作"第三源"冗余：东财(akshare) 为主，腾讯 neodata 为备，腾讯自选股(westock) 为
  另一条完全独立的腾讯管线（与 neodata 的 copilot.tencent.com 端点不同），
  主要价值 = 东财限流 / neodata token 失效时的独立兜底 + 为 top_list 回填 5日净额。
- 由 fetch_sector_fund_flow.py 在缓存缺失/超龄时调用；自身失败静默降级，绝不阻断主流程。
- 单位换算：腾讯返回 mainNetInflow 为"万元"，统一 ÷10000 转"亿元"，与 fetch 主脚本一致。
"""
import json
import os
import sys
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(BASE_DIR, "data", "sector_fund_flow_westock.json")
WESTOCK_PKG = "westock-data-skillhub@1.0.3"


def _which_npx():
    import shutil
    p = shutil.which("npx")
    return p or "npx"


def run_board():
    """调用 npx westock board 返回 markdown 文本；失败返回空串。"""
    try:
        proc = subprocess.run(
            [_which_npx(), "-y", WESTOCK_PKG, "board"],
            capture_output=True, text=True, timeout=200, encoding="utf-8",
        )
        return proc.stdout or ""
    except Exception as e:
        print(f"  ⚠️ [westock] npx 调用失败: {e}")
        return ""


def _to_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def parse_board(text):
    """解析 board 的 markdown 表格 → 归一化板块列表。

    资金流表(含 mainNetInflow)：行业/概念 资金流入/流出 TopN
        → name, net(亿元, 今日主力净流入), net_5d(亿元, 5日累计)
    涨幅排名表(含 changePct5d)：仅取价格区间涨跌幅(非资金)，存 chg5d/chg20d 备用。
    """
    items = {}
    cur_section = None
    headers = None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("**") and s.endswith("**"):
            cur_section = s.strip("*").strip()
            headers = None
            continue
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|") if c.strip() != ""]
        # 分隔行（全为 --- ）：跳过，保留已有 headers（下一行是数据，勿重置）
        if cells and all(c == "-" * len(c) for c in cells):
            continue
        if headers is None:
            headers = cells
            continue
        if len(cells) != len(headers):
            continue
        row = dict(zip(headers, cells))
        name = (row.get("name") or "").strip()
        if not name:
            continue
        typ = "概念" if "概念" in cur_section else "行业"

        if "mainNetInflow" in row:  # 资金流表
            it = items.setdefault(name, {"name": name, "type": typ})
            net = _to_float(row.get("mainNetInflow")) / 10000.0   # 万元→亿
            net5 = _to_float(row.get("mainNetInflow5d")) / 10000.0
            it["net"] = round(net, 2)
            if net5:
                it["net_5d"] = round(net5, 2)
        elif "changePct5d" in row:  # 涨幅排名表（价格区间，非资金）
            it = items.setdefault(name, {"name": name, "type": typ})
            it["chg5d"] = _to_float(row.get("changePct5d"))
            it["chg20d"] = _to_float(row.get("changePct20d"))
    # 仅保留含主力净流入(net)的板块；纯涨幅表无资金流，对资金流冗余无意义
    return [v for v in items.values() if v.get("net") is not None]


def main():
    out = run_board()
    items = parse_board(out) if out else []
    if not items and os.path.exists(CACHE):
        try:
            d = json.load(open(CACHE, encoding="utf-8"))
            items = d.get("items", [])
            if items:
                print("  ⚠️ [westock] npx 无新数据，沿用旧缓存")
        except Exception:
            pass
    data = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source": "腾讯自选股(westock-npx)",
        "items": items,
    }
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ [westock] 板块资金缓存: {len(items)} 个板块 → {os.path.relpath(CACHE, BASE_DIR)}")


if __name__ == "__main__":
    main()
