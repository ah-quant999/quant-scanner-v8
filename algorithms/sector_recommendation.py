#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""板块推荐融合：宏观框架（market_regime）+ 板块实时数据（RS/资金流/周期）
- 输入：
    - out/market_regime.json（宏观判定 + 推荐池）
    - data/SECTOR_RS.js / data/SECTOR_FUND_FLOW.js / data/SECTOR_PHASE_HISTORY.js
- 输出：out/sector_recommendation.json + data/SECTOR_RECOMMENDATION.js
- 关键逻辑：
    1. 每个推荐板块打「位置分」(pct_5d/pct_20d)
    2. 「已涨过」过滤：pct_5d > 8% → 标"已涨过"（按主人「创新药涨过就排除」逻辑）
    3. 「异动跟随」标：pct_day > 3% + 净流入 > 5亿 → 标"早盘异动"
    4. 综合优先级排序
"""
import json
import os
import subprocess
import sys
import datetime
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "out", "sector_recommendation.json")


def log(msg):
    print(f"  [sector_recommendation] {msg}", flush=True)


def load_window_var(path):
    """从 data/X.js 读 window.X = {...}; """
    raw = open(path, encoding="utf-8").read()
    m = re.match(r"window\.[A-Z0-9_]+\s*=\s*(\{.*\});?\s*$", raw, re.DOTALL)
    if not m:
        raise ValueError(f"{path} 格式不符")
    return json.loads(m.group(1))


def _bootstrap_regime(macro_path):
    """🔴 2026-08-25 治本：out/ 被 .gitignore 忽略，云端全新 checkout 永远没有
    out/market_regime.json，旧逻辑只打印「先跑 market_regime.py」就 return 1（光说不做）→
    本卡自 2026-08-22 07:59 起永久冻结，链尾保底重跑(step_ensure_cockpit_sector)也救不回来
    （因为重跑的是同一个必失败脚本）。现改为真的去跑 market_regime.py 自举依赖。
    严格附加：自举失败则维持原 return 1 行为，不会比现状更差。"""
    regime = os.path.join(BASE, "algorithms", "market_regime.py")
    if not os.path.exists(regime):
        log(f"缺 {macro_path} 且找不到 {regime}，无法自举")
        return False
    log(f"缺 {macro_path}，自动先跑 market_regime.py 自举依赖…")
    try:
        r = subprocess.run([sys.executable, regime], cwd=BASE,
                           capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            log(f"market_regime.py 退出码 {r.returncode}: {(r.stderr or '')[-300:]}")
    except Exception as e:
        log(f"market_regime.py 异常: {e}")
    return os.path.exists(macro_path)


def main():
    macro_path = os.path.join(BASE, "out", "market_regime.json")
    if not os.path.exists(macro_path) and not _bootstrap_regime(macro_path):
        log(f"缺 {macro_path}，自举 market_regime.py 后仍不存在，放弃")
        return 1
    with open(macro_path, encoding="utf-8") as f:
        macro = json.load(f)

    try:
        rs = load_window_var(os.path.join(BASE, "data", "SECTOR_RS.js"))
        fund = load_window_var(os.path.join(BASE, "data", "SECTOR_FUND_FLOW.js"))
    except Exception as e:
        log(f"板块数据加载失败: {e}")
        return 1

    # 板块名 → RS pct_day/pct_5d/pct_20d
    rs_by_name = {}
    for s in rs.get("sectors", []):
        rs_by_name[s["name"]] = {
            "pct_day": s.get("pct_day"),
            "pct_5d": s.get("pct_5d"),
            "pct_20d": s.get("pct_20d"),
        }
    # 板块名 → 资金流 net
    fund_by_name = {}
    for s in fund.get("sectors_in", []) + fund.get("sectors_out", []) + fund.get("top_list", []):
        n = s.get("name")
        if n:
            fund_by_name.setdefault(n, {"net": s.get("net"), "chg": s.get("chg")})

    # 同名映射（板块 RS 用同花顺行业分类，资金流用东方财富分类，可能名称有差）
    name_alias = {
        "银行": ["银行"],
        "煤炭": ["煤炭开采加工", "煤炭"],
        "通信运营": ["通信服务"],
        "公用事业": ["电力", "公用事业"],
        "贵金属": ["贵金属"],
        "油气": ["油气开采及服务", "石油加工贸易", "石油石化"],
        "保险": ["保险"],
        "中药": ["中药"],
        "化学制药": ["化学制药"],
        "医疗服务": ["医疗服务"],
        "半导体": ["半导体"],
        "通信设备": ["通信设备"],
        "计算机设备": ["计算机设备"],
        "白酒": ["白酒", "白酒Ⅱ"],
        "食品饮料": ["食品饮料"],
        "家用电器": ["家用电器", "白色家电"],
        "创新药": ["化学制药"],
        "医疗器械": ["医疗器械"],
        "CXO": ["医疗服务"],
        "计算机": ["计算机设备", "软件开发", "IT 服务"],
        "电子元件": ["电子元件"],
    }

    # 给每个推荐板块打分
    results = []
    for grp in macro.get("recommendation_groups", []):
        for sec_name in grp.get("sectors", []):
            aliases = name_alias.get(sec_name, [sec_name])
            # 在 RS / 资金流里找匹配
            pct_day, pct_5d, pct_20d, net, chg = None, None, None, None, None
            for a in aliases:
                if a in rs_by_name:
                    r = rs_by_name[a]
                    pct_day = r.get("pct_day")
                    pct_5d = r.get("pct_5d")
                    pct_20d = r.get("pct_20d")
                if a in fund_by_name:
                    f = fund_by_name[a]
                    net = f.get("net")
                    chg = f.get("chg")
            # 「已涨过」过滤（主人 8/19 逻辑：创新药涨过就排除）——阈值 7%（半导体 7.14% 应触发）
            flags = []
            if pct_5d is not None and pct_5d > 7:
                flags.append(f"已涨过(5d+{pct_5d:.1f}%)")
            if pct_day is not None and pct_day > 3 and net and net > 5:
                flags.append(f"🔥早盘异动({pct_day:+.1f}%, 净流入{net:.1f}亿)")
            elif pct_day is not None and pct_day > 5:
                flags.append(f"⚡单日急涨({pct_day:+.1f}%)")
            if net and net > 5:
                flags.append(f"资金流入({net:.1f}亿)")
            elif net and net < -5:
                flags.append(f"资金流出({net:.1f}亿)")

            results.append({
                "group": grp["name"],
                "priority": grp["priority"],
                "sector": sec_name,
                "logic": grp["logic"],
                "pct_day": pct_day,
                "pct_5d": pct_5d,
                "pct_20d": pct_20d,
                "net_inflow_yi": net,
                "pct_chg": chg,
                "flags": flags,
                "action": "🔥 跟随" if any("🔥" in f for f in flags) else (
                    "⏸️ 观望(已涨过)" if any("已涨过" in f for f in flags) else "✅ 关注"
                ),
            })

    # 按优先级 + 异动排序
    results.sort(key=lambda x: (x["priority"], 0 if any("🔥" in f for f in x["flags"]) else 1))

    out = {
        "meta": {
            "update_time": datetime.datetime.now().isoformat(timespec="seconds"),
            "regime_label": macro.get("regime", {}).get("label"),
            "framework_match": macro.get("framework_match"),
            "disclaimer": "⚠️ 框架+实时数据融合，板块轮动回测胜率 55-65% 上限。实盘验证 ≥3 个月。",
        },
        "regime": macro.get("regime"),
        "current_rates": macro.get("current_rates"),
        "trends": macro.get("trends"),
        "recommendations": results,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log(f"已写入 {OUT}")

    # 🔴 2026-08-25 一劳永逸：直接导出 data/SECTOR_RECOMMENDATION.js（脱离云端未知导出步）
    #   见 gen_cockpit_advice.py 同款说明。脚本自带 data 导出 → 云端跑到即写新鲜 data/X.js，不被旧 out 覆盖。
    DATA_JS = os.path.join(BASE, "data", "SECTOR_RECOMMENDATION.js")
    with open(DATA_JS, "w", encoding="utf-8") as f:
        f.write("window.SECTOR_RECOMMENDATION = ")
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";")
    log(f"已导出 {DATA_JS}")
    log(f"推荐板块数: {len(results)}")
    for r in results[:10]:
        flags_s = " ".join(r["flags"]) if r["flags"] else "—"
        log(f"  P{r['priority']} {r['sector']:<6} | {r['action']:<10} | 5d={r['pct_5d']} | 资金={r['net_inflow_yi']} | {flags_s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())