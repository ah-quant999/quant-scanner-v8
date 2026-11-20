# -*- coding: utf-8 -*-
"""
risk_guard.py —— ① 真实回撤闸（基石 2 落地）

【2026-11-21 主人令「数据真实且及时·不得弄虚作假」根治】
  旧实现读 data/RISK_GUARD_INPUT.json —— 该文件是 2026-10-26 手工构造的线性假曲线
  （100→116→109→…，每日整齐 +0.32/+0.24），属占位假数据，已从仓库删除、永不回用。

  真实净值源 = data/PORTFOLIO.js（westock 练习赛组合 account.total_assets，真实账户快照）：
    · 每次运行把当日 total_assets 按日累积进 raw_data/history/equity_curve.json
      （按日去重、同日覆盖、幂等），净值曲线随时间真实生长；
    · 回撤闸据该真实曲线计算最大回撤 → 档位 → position_multiplier；
    · 曲线 <2 点 ⇒ multiplier=1.0 + 如实标注「真实净值累积中」，绝不谎报回撤；
    · PORTFOLIO.js 停更 >3 天 ⇒ data_degraded=true 如实标注（仍用已累积曲线）。

【契约 / 输出】（与前端「收益转化算法」执行卡 schema 兼容）
  data/RISK_GUARD.js: window.RISK_GUARD = { update_time, source, has_equity,
    equity_points, curve_range, max_drawdown, peak_idx, trough_idx, tier,
    multiplier, thresholds, note, data_degraded }

【档位】（与前端原展示文案一致；阈值可调）
  max_dd < 8%   → ×1.00  正常
  8% ≤ dd <12%  → ×0.50  减半
  12% ≤ dd <15% → ×0.25  半仓(上限)
  dd ≥ 15%      → ×0.00  清仓

【用法】
  python3 risk_guard.py          # 挂链（E 批）自动运行
"""
import os
import re
import json
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")
HIST_DIR = os.path.join(HERE, "..", "raw_data", "history")
CURVE_PATH = os.path.join(HIST_DIR, "equity_curve.json")
PORTFOLIO_PATH = os.path.join(DATA_DIR, "PORTFOLIO.js")
OUTPUT_PATH = os.path.join(DATA_DIR, "RISK_GUARD.js")

# (上限回撤, 乘数, 档位名)
DD_TIERS = [
    (0.08, 1.00, "正常"),
    (0.12, 0.50, "减半"),
    (0.15, 0.25, "半仓(上限)"),
    (float("inf"), 0.00, "清仓"),
]


def _load_portfolio_point():
    """从 data/PORTFOLIO.js 取当日真实账户快照。返回 (date_str, total_assets) 或 (None, None)。"""
    if not os.path.exists(PORTFOLIO_PATH):
        return None, None
    try:
        t = open(PORTFOLIO_PATH, "r", encoding="utf-8").read()
        t = re.sub(r"^\s*window\.PORTFOLIO_DATA\s*=\s*", "", t).strip().rstrip(";")
        d = json.loads(t)
        acct = d.get("account") or {}
        ta = acct.get("total_assets")
        if ta is None:
            return None, None
        ta = float(ta)
        upd = str(d.get("updated_at") or d.get("update_time") or "")
        m = re.search(r"(20\d\d-\d\d-\d\d)", upd)
        date = m.group(1) if m else datetime.date.today().isoformat()
        return date, ta
    except Exception as e:
        print(f"  ⚠️ 解析 PORTFOLIO.js 失败: {e}")
        return None, None


def _load_curve():
    if not os.path.exists(CURVE_PATH):
        return []
    try:
        d = json.load(open(CURVE_PATH, "r", encoding="utf-8"))
        pts = d.get("points") if isinstance(d, dict) else d
        return [p for p in (pts or []) if isinstance(p, dict) and p.get("date")]
    except Exception:
        return []


def _save_curve(pts):
    os.makedirs(os.path.dirname(CURVE_PATH), exist_ok=True)
    json.dump({"points": pts}, open(CURVE_PATH, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)


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


def _write_out(out):
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("window.RISK_GUARD = ")
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write(";")


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    # ① 真实净值累积：PORTFOLIO.js 当日 total_assets → equity_curve.json（按日去重、幂等）
    p_date, p_ta = _load_portfolio_point()
    pts = _load_curve()
    appended = False
    if p_date and p_ta:
        pts = [p for p in pts if p.get("date") != p_date]  # 同日覆盖（当日最新快照为准）
        pts.append({"date": p_date, "total_assets": round(p_ta, 2)})
        pts.sort(key=lambda x: x.get("date") or "")
        _save_curve(pts)
        appended = True

    # ② PORTFOLIO 新鲜度（真实标注）
    degraded = False
    if p_date:
        try:
            d0 = datetime.date.fromisoformat(p_date)
            if (datetime.date.today() - d0).days > 3:
                degraded = True
        except Exception:
            pass

    equity = [float(p["total_assets"]) for p in pts if p.get("total_assets") is not None]

    # ③ 曲线 <2 点：如实标注，绝不谎报
    if len(equity) < 2:
        out = {
            "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": f"PORTFOLIO(westock 练习赛组合) total_assets 真实累积 · 现有 {len(equity)} 点",
            "has_equity": len(equity) >= 2,
            "equity_points": len(equity),
            "curve_range": (f"{pts[0]['date']}~{pts[-1]['date']}" if pts else None),
            "max_drawdown": 0.0,
            "tier": "正常(真实净值累积中)" if equity else "正常(未接入净值)",
            "multiplier": 1.0,
            "thresholds": [
                {"dd_lt": 0.08, "mult": 1.0, "tier": "正常"},
                {"dd_lt": 0.12, "mult": 0.5, "tier": "减半"},
                {"dd_lt": 0.15, "mult": 0.25, "tier": "半仓(上限)"},
                {"dd_lt": 1.0, "mult": 0.0, "tier": "清仓"},
            ],
            "data_degraded": degraded,
            "note": ("真实账户净值曲线累积中（<2 点），回撤闸暂不降杠杆 ×1.00；"
                     "随 PORTFOLIO.js 逐日快照累积，曲线生长后自动真实生效。"
                     "旧 RISK_GUARD_INPUT.json 假曲线已于 2026-11-21 根除。"
                     + (" ⚠️ PORTFOLIO.js 停更>3天。" if degraded else "")),
        }
        _write_out(out)
        print(f"  🛡️ 回撤闸：真实净值 {len(equity)} 点（累积中）⇒ multiplier=1.00，已写 {OUTPUT_PATH}")
        return out

    mdd, pk, tr = max_drawdown(equity)
    mult, tier = tier_of(mdd)
    out = {
        "update_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": (f"PORTFOLIO(westock 练习赛组合) total_assets 真实累积 · "
                   f"{pts[0]['date']}~{pts[-1]['date']} 共 {len(equity)} 点"),
        "has_equity": True,
        "equity_points": len(equity),
        "curve_range": f"{pts[0]['date']}~{pts[-1]['date']}",
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
        "data_degraded": degraded,
        "note": (f"真实账户最大回撤 {mdd*100:.2f}%，触发「{tier}」档 ⇒ 仓位乘数 ×{mult:.2f}。"
                 f"净值=练习赛组合 total_assets 逐日真实累积（当日快照{'已入账' if appended else '未取到，用已累积曲线'}）。"
                 + (" ⚠️ PORTFOLIO.js 停更>3天，data_degraded。" if degraded else "")),
    }
    _write_out(out)
    print(f"  🛡️ 回撤闸：真实净值 {len(equity)} 点 max_dd={mdd*100:.2f}% ⇒ {tier} ⇒ multiplier={mult:.2f}，已写 {OUTPUT_PATH}")
    return out


if __name__ == "__main__":
    main()
