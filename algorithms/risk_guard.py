# -*- coding: utf-8 -*-
"""
risk_guard.py —— ① 真实回撤闸（基石 2 落地）

【契约 / 数据源】
  本脚本读取一份「账户净值序列」（权益曲线），计算策略真实最大回撤，
  按档位映射为 position_multiplier（仓位乘数），写出 data/RISK_GUARD.js，
  供前端「收益转化算法」执行卡真实作用于每只仓位（不再是空话）。

【净值输入】（任选其一，放在 INPUT_PATH，默认 data/RISK_GUARD_INPUT.json）
  {"equity": [100.0, 101.2, 98.5, ...]}      # 累计净值（任意基准，1.0 或 100 均可）
  {"returns":[0.01, -0.02, 0.03, ...]}       # 日收益序列，脚本自动累乘成净值

  若文件不存在 / 为空 / 无有效序列 ⇒ multiplier=1.0，tier="正常(未接入净值)"，
  并在 note 中明确标注，不谎报回撤。

【档位】（与前端原展示文案一致；阈值可调）
  max_dd < 8%   → ×1.00  正常
  8% ≤ dd <12%  → ×0.50  减半
  12% ≤ dd <15% → ×0.25  半仓(上限)
  dd ≥ 15%      → ×0.00  清仓

【用法】
  python3 risk_guard.py
  RISK_GUARD_INPUT=/path/to/equity.json python3 risk_guard.py
"""
import os
import sys
import json
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")
INPUT_PATH = os.environ.get(
    "RISK_GUARD_INPUT",
    os.path.join(DATA_DIR, "RISK_GUARD_INPUT.json"),
)
OUTPUT_PATH = os.path.join(DATA_DIR, "RISK_GUARD.js")

# (上限回撤, 乘数, 档位名)
DD_TIERS = [
    (0.08, 1.00, "正常"),
    (0.12, 0.50, "减半"),
    (0.15, 0.25, "半仓(上限)"),
    (float("inf"), 0.00, "清仓"),
]


def build_equity(payload):
    """从输入 payload 还原累计净值序列。返回 (equity_list, source_desc)。"""
    if not isinstance(payload, dict):
        return None, "输入非对象"
    eq = payload.get("equity")
    if isinstance(eq, list) and len(eq) >= 2:
        vals = []
        for x in eq:
            try:
                vals.append(float(x))
            except Exception:
                pass
        if len(vals) >= 2:
            return vals, "equity(累计净值)"
    rt = payload.get("returns")
    if isinstance(rt, list) and len(rt) >= 2:
        vals = [1.0]
        for x in rt:
            try:
                vals.append(vals[-1] * (1.0 + float(x)))
            except Exception:
                pass
        if len(vals) >= 2:
            return vals, "returns(日收益累乘)"
    return None, "无有效序列"


def max_drawdown(equity):
    """返回 (max_dd_ratio, peak_idx, trough_idx)。dd 为正的比例。"""
    if not equity or len(equity) < 2:
        return 0.0, 0, 0
    peak = equity[0]
    mdd = 0.0
    pk = 0
    tr = 0
    for i, v in enumerate(equity):
        if v > peak:
            peak = v
            pk = i
        if peak > 0:
            dd = (peak - v) / peak
            if dd > mdd:
                mdd = dd
                tr = i
    return mdd, pk, tr


def tier_of(dd):
    for up, mult, name in DD_TIERS:
        if dd < up:
            return mult, name
    return 1.0, "正常"


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = None
    src_file = ""
    if os.path.exists(INPUT_PATH):
        try:
            with open(INPUT_PATH, "r", encoding="utf-8") as f:
                payload = json.load(f)
            src_file = os.path.basename(INPUT_PATH)
        except Exception as e:
            print(f"  ⚠️ 读取 {INPUT_PATH} 失败: {e}")
            payload = None

    equity, src_desc = build_equity(payload or {})
    if equity is None:
        # 未接入净值：安全默认，明确标注
        out = {
            "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "未接入账户净值序列",
            "has_equity": False,
            "equity_points": 0,
            "max_drawdown": 0.0,
            "tier": "正常(未接入净值)",
            "multiplier": 1.0,
            "thresholds": [
                {"dd_lt": 0.08, "mult": 1.0, "tier": "正常"},
                {"dd_lt": 0.12, "mult": 0.5, "tier": "减半"},
                {"dd_lt": 0.15, "mult": 0.25, "tier": "半仓(上限)"},
                {"dd_lt": 1.0, "mult": 0.0, "tier": "清仓"},
            ],
            "note": "回撤闸已编码但未接入账户权益曲线；默认 ×1.00 不降杠杆。"
                    "把真实账户净值（累计或日收益）写入 data/RISK_GUARD_INPUT.json 即自动生效。",
        }
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write("window.RISK_GUARD = ")
            json.dump(out, f, ensure_ascii=False, indent=2)
            f.write(";")
        print(f"  🛡️ 回撤闸：未接入净值 ⇒ multiplier=1.00（正常），已写 {OUTPUT_PATH}")
        return out

    mdd, pk, tr = max_drawdown(equity)
    mult, tier = tier_of(mdd)
    out = {
        "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": f"{src_file} · {src_desc}",
        "has_equity": True,
        "equity_points": len(equity),
        "max_drawdown": round(mdd, 4),
        "peak_idx": pk,
        "trough_idx": tr,
        "tier": tier,
        "multiplier": mult,
        "thresholds": [
            {"dd_lt": 0.08, "mult": 1.0, "tier": "正常"},
            {"dd_lt": 0.12, "mult": 0.5, "tier": "减半"},
            {"dd_lt": 0.15, "mult": 0.25, "tier": "半仓(上限)"},
            {"dd_lt": 1.0, "mult": 0.0, "tier": "清仓"},
        ],
        "note": f"策略真实最大回撤 {mdd*100:.2f}%，触发「{tier}」档 ⇒ 仓位乘数 ×{mult:.2f}。"
                "前端执行卡已据此真实缩放每只建议仓位。",
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("window.RISK_GUARD = ")
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write(";")
    print(f"  🛡️ 回撤闸：max_dd={mdd*100:.2f}% ⇒ {tier} ⇒ multiplier={mult:.2f}"
          f"（{len(equity)} 个净值点，源={src_desc}），已写 {OUTPUT_PATH}")
    return out


if __name__ == "__main__":
    main()
