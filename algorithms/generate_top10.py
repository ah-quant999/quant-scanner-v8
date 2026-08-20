#!/usr/bin/env python3
"""
generate_top10.py — 多维共振评分 + 每日TOP10精选
- 从 gold_pool.json 读取所有金股池股票
- 结合多维度数据（板块资金/龙虎榜/主力/北向/投行/分析师）计算综合共振评分
- 输出 data/top10_daily.json（TOP20 + 评分明细）
"""
import json
import os

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
import sys
from datetime import datetime

from fundamental_helper import fq_key_of, quality_points
from stop_target_logic import compute_stop_target_from_closes, board_from_code

WORKSPACE = os.path.dirname(os.path.abspath(__file__))
# 🔴 2026-08-06 修复：历史快照目录从 out/history（gitignore，云端丢）→ raw_data/history（git 跟踪 + api_push 推送持久化）
DATA_DIR = os.path.join(WORKSPACE, "..", "raw_data")
OUTPUT = os.path.join(DATA_DIR, "top10_daily.json")


def load_json(path, default=None):
    """安全加载JSON"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else {}


def _migrate_old_top10_scores(hist_dir):
    """将历史 top10_daily_YYYYMMDD.json 中旧 raw 评分（>100）统一归一化到 0~100，
    保证回测与阈值口径一致。按 250 理论满分折算，最高 100。"""
    if not os.path.isdir(hist_dir):
        return
    for fn in os.listdir(hist_dir):
        if not fn.startswith("top10_daily_") or not fn.endswith(".json"):
            continue
        path = os.path.join(hist_dir, fn)
        try:
            data = load_json(path, {})
            if not isinstance(data, dict):
                continue
            # max_score > 100 说明是旧 raw 分
            if data.get("max_score", 0) <= 100:
                continue
            top10 = data.get("top10", [])
            count_80 = 0
            max_s = 0
            for item in top10:
                raw = item.get("total_score", 0)
                norm = round(min(100, raw / 250 * 100), 1)
                item["total_score"] = norm
                max_s = max(max_s, norm)
                if norm >= 80:
                    count_80 += 1
            data["max_score"] = max_s
            data["count_80plus"] = count_80
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


def main():
    print("=" * 60)
    print(f"  多维共振评分 · 每日TOP20精选  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 🛡 2026-08-20 主人令·一劳永逸：TOP10 精选属于盘后选股策略，必须 18:00 后跑。
    from utils.time_gate import check_stock_picking_ready
    check_stock_picking_ready(by='generate_top10')

    # ── 1. 加载金股池 ──
    # 🔴 2026-08-11 修复顺序缺陷：本轮 fresh gold_pool 由 scanner.py 直产到 out/，
    #    raw_data/gold_pool.json 要等 stage_to_raw（run_algorithms step2）才刷新；
    #    本脚本在 step1 运行，直接读 raw_data 会拿到上一轮的旧/空文件 → "金股池为空"跳过。
    #    故优先读 out/gold_pool.json（本轮），回退 raw_data。
    _out_gp = os.path.join(WORKSPACE, "..", "out", "gold_pool.json")
    gold_pool = load_json(_out_gp, {})
    if not (isinstance(gold_pool, dict) and gold_pool.get("stocks")):
        gold_pool = load_json(os.path.join(DATA_DIR, "gold_pool.json"), {"stocks": {}})
    gp_stocks = gold_pool.get("stocks", {})
    if not gp_stocks:
        print("  ⚠️  金股池为空，跳过")
        print(f"\n  结果: 跳过 (金股池为空)")
        return
    print(f"  📊 金股池: {len(gp_stocks)} 只")

    # ── 2. 加载辅助数据 ──
    sector_flow = load_json(os.path.join(DATA_DIR, "sector_fund_flow.json"), {})
    lhb_data = load_json(os.path.join(DATA_DIR, "lhb_result.json"), {})
    main_stock = load_json(os.path.join(DATA_DIR, "main_stock.json"), {})
    north_fund = load_json(os.path.join(DATA_DIR, "north_fund.json"), {})
    mahoro = load_json(os.path.join(DATA_DIR, "mahoro_signals.json"), {})
    w52_high = load_json(os.path.join(DATA_DIR, "52w_high.json"), {})
    # 2026-07-21: 基本面质量分(A=+40, B=+5, D=-10, C=0)
    fundamental = load_json(os.path.join(DATA_DIR, "fundamental_quality.json"), {})
    fundamental_stocks = fundamental.get("stocks", {}) if isinstance(fundamental, dict) else {}
    analyst = load_json(os.path.join(DATA_DIR, "analyst_ratings.json"), {})
    industry_map = load_json(os.path.join(DATA_DIR, "industry_map.json"), {})

    # ── 2.5 加载驾驶舱回测胜率并按信号组合聚合 ──
    backtest = load_json(os.path.join(DATA_DIR, "cockpit_backtest.json"), {})
    bt_by_signal = {}
    bt_total_wins = bt_total_losses = 0
    for date_list in backtest.get("by_date", {}).values():
        for rec in date_list:
            sigs = rec.get("signals", {})
            key = (bool(sigs.get("chan")), bool(sigs.get("jinzuan")),
                   bool(sigs.get("jigou")), bool(sigs.get("trend")))
            st = bt_by_signal.setdefault(key, {"wins": 0, "losses": 0})
            if rec.get("is_win"):
                st["wins"] += 1
                bt_total_wins += 1
            elif rec.get("is_loss"):
                st["losses"] += 1
                bt_total_losses += 1
    # 整体胜率作为无样本/少样本时的平滑基准
    bt_total_n = bt_total_wins + bt_total_losses
    bt_base_rate = bt_total_wins / bt_total_n * 100 if bt_total_n > 0 else 50.0

    def bt_win_rate_for(sigs):
        """给定四信号布尔元组，返回带拉普拉斯平滑的历史 T+3 胜率(%)"""
        key = (bool(sigs[0]), bool(sigs[1]), bool(sigs[2]), bool(sigs[3]))
        st = bt_by_signal.get(key, {"wins": 0, "losses": 0})
        n = st["wins"] + st["losses"]
        # 拉普拉斯平滑：小样本向整体胜率回归；样本越多越相信自己
        wins = st["wins"] + bt_base_rate / 100 * 5  # 先验等效 5 个样本
        total = n + 5
        return wins / total * 100 if total > 0 else bt_base_rate

    # ── 3. 构建辅助查询映射 ──
    # 板块资金：板块名→净流入(亿)
    sector_flow_in = {}
    for s in sector_flow.get("sectors_in", []):
        sector_flow_in[s.get("name", "")] = s.get("net", 0)

    # 龙虎榜：code→inst_net_万
    lhb_map = {}
    for s in lhb_data.get("stocks", []):
        code = s.get("code", "")
        if code:
            lhb_map[code] = {
                "inst_net": s.get("inst_net_万", 0),
                "category": s.get("category", ""),
            }

    # 主力：code→net
    main_map = {}
    for s in main_stock.get("top_main_in", []):
        main_map[s.get("code", "")] = s.get("net", 0)
    for s in main_stock.get("top_main_out", []):
        code = s.get("code", "")
        if code not in main_map:
            main_map[code] = s.get("net", 0)

    # 投行覆盖：code→stance
    mahoro_map = {}
    for m in mahoro.get("gold_pool_matches", []):
        mahoro_map[m.get("code", "")] = m.get("stance", "")

    # 52周新高 (按名称粗略匹配)
    w52_names = set()
    for s in w52_high.get("stocks", []):
        w52_names.add(s.get("name", ""))

    # 分析师转向 (按名称)
    analyst_names = set()
    for a in analyst.get("upgrades", []):
        analyst_names.add(a.get("name", ""))

    # 行业映射：code→[sector_names]
    ind_map = {}
    im_stocks = industry_map.get("stocks", {})
    if isinstance(im_stocks, dict):
        for code_key, sectors in im_stocks.items():
            # normalize code
            clean = code_key.replace("sh_", "").replace("sz_", "").replace("hk_", "").replace("bj_", "")
            ind_map[clean] = sectors if isinstance(sectors, list) else sectors.get("sectors", [])

    # ── 4. 计算多维共振评分 ──
    scored = []
    for key, s in gp_stocks.items():
        hist = s.get("history", [])
        latest = hist[-1] if hist else {}
        if isinstance(latest, dict) and "latest" in latest:
            nested = latest["latest"]
            # 嵌套latest必须有close/pct_chg才使用，否则保留外层完整数据
            if isinstance(nested, dict) and nested.get("close") and nested.get("pct_chg") is not None:
                latest = nested
            # 否则保持latest=hist[-1]（外层已有close/pct_chg等字段）

        name = s.get("name", "")
        code = s.get("code", "")
        raw_code = code or key.replace("sz_", "").replace("sh_", "").replace("hk_", "")

        # 基础信号 (0-100)
        has_chan = bool(latest.get("缠论买_日K"))
        has_qizhang = bool(latest.get("金钻_起涨"))
        has_huangzhu = bool(latest.get("金钻_黄柱"))
        has_jigou = bool(latest.get("四量图_机构变红"))
        has_trend = bool(latest.get("上涨趋势"))
        sig_count = sum([has_chan, has_qizhang or has_huangzhu, has_jigou, has_trend])

        base = 0
        if has_chan:
            base += 25
        if has_qizhang or has_huangzhu:
            base += 25
        if has_jigou:
            base += 25
        if has_trend:
            base += 25
        if has_chan and has_qizhang:
            base += 10
        elif has_chan and has_huangzhu:
            base += 5

        # 增强因子 (-10 ~ +13)
        enhance = 0
        pct20 = latest.get("pct_chg_20d") or s.get("pct_chg_20d") or 0
        if pct20 >= 50:
            enhance -= 5
        elif pct20 >= 35:
            enhance += 5
        elif pct20 >= 20:
            enhance += 3

        rsi = latest.get("rsi_14") or s.get("rsi_14") or 50
        if rsi > 70:
            enhance -= 5
        elif rsi < 30:
            enhance += 3

        # 连续共振天数
        consecutive = 0
        sorted_hist = sorted(hist, key=lambda h: h.get("date", ""), reverse=True)
        for h in sorted_hist:
            h_sig = sum([
                bool(h.get("缠论买_日K")),
                bool(h.get("金钻_起涨") or h.get("金钻_黄柱")),
                bool(h.get("四量图_机构变红")),
                bool(h.get("上涨趋势")),
            ])
            if h_sig >= 3:
                consecutive += 1
            else:
                break
        enhance += min(consecutive * 2, 8)

        # ── 技术形态分 (2026-07-26): 把驾驶舱 A 档条件合并进主站打分 ──
        # 条件：上涨趋势 + 机构变红 + RSI<68 + 20日涨幅<35% + EMA>=5 + 非涨停
        ema_up = s.get("ema_up") or latest.get("ema_up") or 0
        limit_up = bool(s.get("当日涨停") or latest.get("当日涨停") or False)
        form_score = 0
        form_detail = []
        if ema_up >= 5:
            form_score += 5
            form_detail.append(f"EMA结构={ema_up}")
        elif ema_up >= 3:
            form_score += 3
            form_detail.append(f"EMA结构={ema_up}")
        elif ema_up >= 1:
            form_score += 1
            form_detail.append(f"EMA结构={ema_up}")
        if not limit_up:
            form_score += 2
            form_detail.append("非涨停")
        if pct20 < 35:
            form_score += 2
        if rsi < 68:
            form_score += 2
        if has_trend and has_jigou and ema_up >= 5 and rsi < 68 and pct20 < 35 and not limit_up:
            form_score += 5
            form_detail.append("形态A")
        # 涨停过热直接惩罚（与形态A条件对齐）
        if limit_up:
            form_score -= 5

        # 资金动力 (0 ~ +15)
        fund = 0
        fund_detail = []

        # 主力
        main_net = main_map.get(raw_code, 0)
        if main_net > 1000:
            fund += 5
            fund_detail.append(f"主力+{main_net:.0f}万")
        elif main_net > 0:
            fund += 2
            fund_detail.append(f"主力+{main_net:.0f}万")

        # 龙虎榜
        lhb_info = lhb_map.get(raw_code)
        if lhb_info and lhb_info["category"] == "机游共振":
            fund += 5
            fund_detail.append(f"龙虎榜机游共振")
        elif lhb_info and lhb_info["inst_net"] > 0:
            fund += 3
            fund_detail.append(f"龙虎榜+{lhb_info['inst_net']:.0f}万")

        # 北向资金：2024年5月起港交所不再披露明细，仅data_date空壳，不再加分
        # 铁律：宁可空着也不用假数据

        # 板块共振 (0 ~ +10)
        sector_score = 0
        sector_detail = ""
        stock_sectors = ind_map.get(raw_code, []) or s.get("sectors", [])
        if isinstance(stock_sectors, dict):
            # industry_map 格式可能是 {sector_name: ...}
            stock_sectors = list(stock_sectors.keys()) if isinstance(stock_sectors, dict) else []
        elif isinstance(stock_sectors, str):
            stock_sectors = [stock_sectors]

        sector = s.get("sector", "")
        if sector and sector not in stock_sectors:
            stock_sectors = [sector] + stock_sectors

        best_sector_flow = 0
        best_sector_name = ""
        for sec_name in stock_sectors:
            flow = sector_flow_in.get(sec_name, 0)
            if flow > best_sector_flow:
                best_sector_flow = flow
                best_sector_name = sec_name

        if best_sector_flow > 5:
            sector_score += 5
            sector_detail = f"{best_sector_name}+{best_sector_flow:.1f}亿"
        elif best_sector_flow > 1:
            sector_score += 2
            sector_detail = f"{best_sector_name}+{best_sector_flow:.1f}亿"
        elif best_sector_flow < -5:
            sector_score -= 3
            sector_detail = f"{best_sector_name}{best_sector_flow:.1f}亿"

        # 机构/投行 (0 ~ +10)
        inst = 0
        inst_detail = []

        stance = mahoro_map.get(raw_code, "")
        if stance == "bullish":
            inst += 3
            inst_detail.append("投行看多")
        elif stance in ("neutral", "mixed"):
            inst += 1
            inst_detail.append("投行关注")

        if name in w52_names:
            inst += 4
            inst_detail.append("52周新高")

        if name in analyst_names:
            inst += 3
            analyst_detail_name = name  # just use name
            inst_detail.append("分析师转向")

        # ── 止损位 / 目标价 ──
        close_price = latest.get("close") or s.get("close") or 0
        # 近5日最低/最高收盘价（用于辅助计算）
        recent_closes = []
        sorted_hist_all = sorted(hist, key=lambda h: h.get("date", ""), reverse=False)
        for h in sorted_hist_all:
            hc = h.get("close", 0)
            if hc and hc > 0:
                recent_closes.append(hc)
        recent5 = recent_closes[-5:] if len(recent_closes) >= 5 else recent_closes
        recent20 = recent_closes[-20:] if len(recent_closes) >= 20 else recent_closes

        # 方案三统一口径（此处只有收盘价序列，用降级版：固定10%止损 + R:R=1.5止盈）
        stop_loss, target_price = 0, 0
        stop_loss_method, target_price_method, risk_reward = "", "", 0
        if close_price and close_price > 0:
            _board = s.get("board_label", "") or board_from_code(raw_code)
            _st = compute_stop_target_from_closes(recent_closes or [close_price], board=_board, strategy="general")
            if _st:
                stop_loss = _st["stop_loss"]
                target_price = _st["target_price"]
                stop_loss_method = _st["stop_loss_method"]
                target_price_method = _st["target_price_method"]
                risk_reward = _st["risk_reward"]

        # ── 基本面质量分（复用 fundamental_helper，与驾驶舱口径一致；
        #     含港股中性兜底：旧数据 hk 误标 D 自动修正为中性；含消息面加减分）──
        # 格式: fundamental_stocks["hk_00005"] = {grade, score, roe, revenue_growth, reason, news}
        mkt = s.get("market", "")
        raw_code = s.get("code", "")
        fq_key = fq_key_of(mkt, raw_code)
        fq = fundamental_stocks.get(fq_key, {})
        quality_score, quality_grade, quality_detail = quality_points(fq)

        # ── 原始总分（各维度绝对加分之和）──
        raw_total = base + enhance + form_score + fund + sector_score + inst + quality_score

        # ── 回测胜率反哺（2026-07-25）──
        # 根据当前信号组合的历史 T+3 胜率做乘子修正：胜率越高越加分，越低越降权
        sig_tuple = (has_chan, has_qizhang or has_huangzhu, has_jigou, has_trend)
        win_rate = bt_win_rate_for(sig_tuple)
        # 以 50% 为中性基准；每偏离 10% ±5 分，限制 ±10 分
        score_backtest = max(-10, min(10, round((win_rate - 50) / 10 * 5)))
        raw_total = raw_total + score_backtest

        # ── 归一化到 0~100（2026-08-01 升级）──
        # 理论满分 ≈ 250（base 110 + enhance 16 + form 16 + fund 10 + sector 5 + inst 10 + quality 40 + backtest 10）
        # 避免 base 单项满分 110 却被下游当百分制阈值用的口径混乱
        total = round(min(100, raw_total / 250 * 100), 1)

        scored.append({
            "code": raw_code,
            "full_code": key,
            "name": name,
            "market": s.get("market", ""),
            "board": s.get("board_label", ""),
            "sig_count": sig_count,
            "close": latest.get("close") or s.get("close") or 0,
            "pct_chg": latest.get("pct_chg") or s.get("pct_chg") or 0,
            "pct_chg_20d": pct20 or 0,
            "total_score": total,
            "quality_grade": quality_grade,
            "quality_score": quality_score,
            "sectors": stock_sectors[:8] if isinstance(stock_sectors, list) else [],
            "stop_loss": stop_loss,
            "target_price": target_price,
            "stop_loss_method": stop_loss_method,
            "target_price_method": target_price_method,
            "risk_reward": risk_reward,
            "stop_precise": False,
            "breakdown": {
                "base": base,
                "enhance": enhance,
                "form": form_score,
                "fund": fund,
                "sector": sector_score,
                "inst": inst,
                "quality": quality_score,
                "backtest": score_backtest,
                "signals": {
                    "chan": has_chan,
                    "jinzuan": has_qizhang or has_huangzhu,
                    "jigou": has_jigou,
                    "trend": has_trend,
                    "form_A": has_trend and has_jigou and ema_up >= 5 and rsi < 68 and pct20 < 35 and not limit_up,
                },
            },
            "win_rate": round(win_rate, 1),
            "details": {
                "consecutive_days": consecutive,
                "form": " | ".join(form_detail) if form_detail else "",
                "fund": " | ".join(fund_detail) if fund_detail else "",
                "sector": sector_detail,
                "inst": " | ".join(inst_detail) if inst_detail else "",
                "quality": quality_detail,
            },
        })

    # ── 5. 排序取TOP20 ──
    scored.sort(key=lambda x: -x["total_score"])

    # 格式化为简洁输出（含完整评分明细）
    top10 = []
    for i, s in enumerate(scored[:20]):
        bd = s["breakdown"]
        dt = s["details"]
        top10.append({
            "rank": i + 1,
            "code": s["code"],
            "name": s["name"],
            "market": s["market"],
            "board": s["board"],
            "sig_count": s["sig_count"],
            "close": s["close"],
            "pct_chg": s["pct_chg"],
            "pct_chg_20d": s["pct_chg_20d"],
            "total_score": s["total_score"],
            "sectors": s["sectors"],
            "stop_loss": s["stop_loss"],
            "target_price": s["target_price"],
            "stop_loss_method": s.get("stop_loss_method", ""),
            "target_price_method": s.get("target_price_method", ""),
            "risk_reward": s.get("risk_reward", 0),
            "stop_precise": s.get("stop_precise", False),
            "score_base": bd["base"],
            "score_enhance": bd["enhance"],
            "score_form": bd.get("form", 0),
            "score_fund": bd["fund"],
            "score_sector": bd["sector"],
            "score_inst": bd["inst"],
            "score_quality": bd.get("quality", 0),
            "score_backtest": bd.get("backtest", 0),
            "win_rate": s.get("win_rate", None),
            "quality_grade": s.get("quality_grade", ""),
            "signals": bd["signals"],
            "consecutive_days": dt["consecutive_days"],
            "form_detail": dt.get("form", ""),
            "fund_detail": dt["fund"],
            "sector_detail": dt["sector"],
            "inst_detail": dt["inst"],
            "quality_detail": dt.get("quality", ""),
        })

    count_80plus = sum(1 for s in scored if s.get("total_score", 0) >= 80)
    max_score = max((s.get("total_score", 0) for s in scored), default=0)
    result = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_scored": len(scored),
        "count_80plus": count_80plus,
        "max_score": max_score,
        "top10": top10,
    }

    # 保存当日文件
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 保存历史：当日快照 + 历史汇总（供历史追踪）
    try:
        hist_dir = os.path.join(DATA_DIR, "history")
        os.makedirs(hist_dir, exist_ok=True)
        today_str = datetime.now().strftime("%Y-%m-%d")
        daily_file = os.path.join(hist_dir, f"top10_daily_{today_str.replace('-', '')}.json")
        with open(daily_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        hist_file = os.path.join(hist_dir, "top10_daily_history.json")
        hist = load_json(hist_file, {})
        if not isinstance(hist, dict):
            hist = {}
        hist[today_str] = {
            "count_80plus": count_80plus,
            "total_scored": len(scored),
            "max_score": max_score,
            "update_time": result["update_time"],
        }
        with open(hist_file, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False, indent=2)

        # 归一化历史快照（一次性过渡，保证旧 raw 分不影响回测口径）
        _migrate_old_top10_scores(hist_dir)
    except Exception as e:
        print(f"  [warn] 保存历史记录失败: {e}")

    print(f"  ✅ TOP10 已生成: {len(top10)} 只")
    for t in top10:
        print(f"     #{t['rank']} {t['name']}({t['code']}) 评分{t['total_score']} "
              f"基础{t['score_base']}+形态{t.get('score_form',0)}+增强{t['score_enhance']}+资金{t['score_fund']}+"
              f"板块{t['score_sector']}+机构{t['score_inst']}+"
              f"质量{t.get('score_quality',0)}{t.get('quality_grade','')}")
    print(f"  总评分: {len(scored)} 只")
    print(f"\n  输出: {OUTPUT}")
    print(f"\n  结果: ✓ 成功 ({datetime.now().strftime('%H:%M:%S')})")


if __name__ == "__main__":
    main()
