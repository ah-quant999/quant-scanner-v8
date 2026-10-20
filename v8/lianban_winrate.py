#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""连板一进二 / 二进三 回测实证 · 真实信号流日累积（v8 · 2026-10-17 主人令「要日更」）

【为什么重写】原「📊 回测实证 · 一进二 / 二进三」卡是 2026-10-09 一次性静态跑批
（bt_lianban_winrate.py 在小九机用本地 kline_cache 全市场复盘，脚本不在仓内、无法日更），
徽章自述「静态回测 · 非日更」。主人 10-17 看图令「要日更」。

【口径裁定 · 10-11 回测口径铁律】唯一合法口径 = 真实信号流（历史规则回放含当前股池
幸存者偏差，禁作主榜/评级/上下架依据）。故本模块**不做历史重放**，改为真实信号流日累积：
  · 每日 post_close 从东财涨停池录入当日信号（首板 连板数==1 / 二连板 ==2，剔 ST）；
  · 信号先入 pending 在途队列，随交易日推进用新浪日K（与 first_board_alert 同源）
    逐笔补结果，**T+5 窗口成熟后才计入分组统计**——未成熟不计入，绝不半路插值；
  · 分组与 10-09 跑批表保持一致：① 全体首板 / 倍量≥3 / 3~5 / 5~8 / >8；
    ② 二连板全体 / 放量(倍量≥3) / 缩量(倍量<3)。

【指标口径（与跑批声明一致）】
  晋级率    = 次日涨停占比（分板块限幅：主板 10% / 双创 20% / 北交所 30%）
  隔夜高开  = 次日开盘 > 信号日收盘 占比
  T+1 胜率  = 次日开盘买入 → 当日收盘卖，收益 > 双边 0.3% 占比（全体样本）
  可成交T+1 = 同上，仅次日开盘非一字板子集（现实中买得进）
  T+5 胜率  = 次日开盘买入 → 第 5 个交易日收盘卖，收益 > 双边 0.3% 占比
  一字板信号（开=高=低=收）剔除：与跑批口径一致。

【执行位】post_close（akshare 涨停池 + 新浪日K 均 cn-IP 友好；小九 selfhosted 17:20 常规班）。
【产出】raw_data/lianban_winrate.json → data/LIANBAN_WINRATE.js（window.LIANBAN_WINRATE）
【幂等】信号按 (code, board_date) 去重；board_date=**涨停池的真实日期**（调用方显式传入，
        禁按运行日盖章——2026-10-20 事故：午夜跑按运行日错录上一交易日池，见
        cloud_fetch_v8.f_lianban_winrate 三道闸门）；同日多轮由调用方按 last_signal_date 判重；
        成熟即移出 pending，同日重跑不重复计数。

🔴 2026-10-20 一劳永逸修复（与本文件相关部分）：
  · store 新增 last_signal_date / signal_dates{日期:条数}——幂等判重从「运行日」改为
    「信号覆盖日」， midnight 看门狗派发（00:07-07:52 每 15 分）不再误伤晚场录入；
  · _record_new 支持行级 board_date（补录旧日期用），默认仍取调用方传入日期；
  · 受害数据修复：2026-10-17/18/19 三个 board_date 实为 10-16 池错录、10-20 实为
    10-19 池错录（东财对未发布日期返最新池的实锤见 cloud_fetch_v8），已由
    scripts/fix_lianban_store_1020.py 按真实池重建（58+44+48=150 条）。
"""
import json
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")

COST_RT = 0.003        # 双边成本（与 2026-10-09 跑批口径一致）
MATURE_BARS = 5        # T+5：信号日后第 5 根日K成熟
VR_MIN = 3.0           # 倍量门槛（①入选口径 / 二板放量-缩量分界）
VR_WINDOW = 20         # 倍量 = 当日量 / 前 20 日均量（不含当日，与 first_board_alert 同）
KLINES = 45            # 在途取数长度：信号日前 20 根 + 信号日 + 成熟 5 根 + 余量
SKIP_AGE_DAYS = 7      # 龄 < 7 自然日不可能已满 5 个交易日 → 不取数（省请求）
EXPIRE_DAYS = 30       # 在途超 30 自然日仍取不到信号日K → 过期丢弃（计 expired）
RECORDED_KEEP = 800    # 去重表有界保留条数

GROUP_KEYS = ["first_all", "first_vr3", "first_vr3_5", "first_vr5_8", "first_vr8",
              "second_all", "second_vr3", "second_vrlt3"]


def _now_cst():
    return datetime.now(CST)


def _sina_sym(code: str) -> str:
    code = str(code).strip()
    if code.startswith(("sh", "sz", "bj")):
        return code
    if code[0] == "6":
        return "sh" + code
    if code[0] in ("0", "3"):
        return "sz" + code
    if code[0] in ("8", "4"):
        return "bj" + code
    return "sh" + code


def _sina_kline(code: str, n: int = KLINES):
    """新浪日K（与 v8/first_board_alert.py 同源同参）。"""
    sym = _sina_sym(code)
    url = (f"https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService"
           f".getKLineData?symbol={sym}&scale=240&ma=no&datalen={n}")
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://finance.sina.com.cn/",
    })
    raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
    return json.loads(raw)


def _bars(k):
    """新浪日K → [(day, open, high, low, close, volume)]（升序，脏行跳过）"""
    out = []
    for d in k or []:
        try:
            out.append((d.get("day"), float(d.get("open") or 0), float(d.get("high") or 0),
                        float(d.get("low") or 0), float(d.get("close") or 0),
                        int(float(d.get("volume") or 0))))
        except Exception:
            continue
    return out


def _is_yiziban(o, h, l, c):
    """一字板：开=高=低=收（全天无波动，买不进）"""
    return abs(o - h) < 1e-6 and abs(o - l) < 1e-6 and abs(o - c) < 1e-6


def _limit_pct(code):
    c = str(code)
    if c[0] in ("8", "4"):
        return 0.30          # 北交所
    if c[:2] in ("30", "68"):
        return 0.20          # 创业板 / 科创板
    return 0.10              # 主板


def _empty_group():
    return {"n": 0, "promo": 0, "gap": 0, "t1_n": 0, "t1_win": 0,
            "t1t_n": 0, "t1t_win": 0, "t5_n": 0, "t5_win": 0}


def skeleton():
    return {
        "groups": {k: _empty_group() for k in GROUP_KEYS},
        "pending": [],
        "recorded": [],
        "signals_total": 0,
        "matured_total": 0,
        "expired": 0,
        "dropped_yiziban": 0,
        "first_date": None,
        "last_mature_date": None,
        "last_run_date": None,
        # 2026-10-20 一劳永逸修复：信号覆盖日口径（幂等判重从运行日改为信号日）
        "last_signal_date": None,   # 最后一次真实录入信号的日期（调用方闸门据此判重）
        "signal_dates": {},         # {board_date: 录入条数}——补录缺口判定与审计
        "params": {
            "cost_rt": COST_RT, "mature_bars": MATURE_BARS, "vr_min": VR_MIN,
            "vr_window": VR_WINDOW, "kline": "sina_daily",
            "universe": "akshare涨停池(连板数1/2)", "caliber": "真实信号流日累积",
        },
    }


def _norm_store(base):
    """基线清洗：坏字段一律回退骨架默认值，绝不让脏数据累积。"""
    st = skeleton()
    if not isinstance(base, dict):
        return st
    for k in ("pending", "recorded"):
        v = base.get(k)
        if isinstance(v, list):
            st[k] = [x for x in v if isinstance(x, (dict, str))]
    for k in ("signals_total", "matured_total", "expired", "dropped_yiziban"):
        try:
            st[k] = int(base.get(k) or 0)
        except Exception:
            pass
    for k in ("first_date", "last_mature_date", "last_run_date", "last_signal_date"):
        v = base.get(k)
        if isinstance(v, str) and v:
            st[k] = v
    sd = base.get("signal_dates")
    if isinstance(sd, dict):
        st["signal_dates"] = {str(k): int(v or 0) for k, v in sd.items()
                              if isinstance(k, str) and k[:4].isdigit()}
    g = base.get("groups")
    if isinstance(g, dict):
        for gk in GROUP_KEYS:
            gv = g.get(gk)
            if isinstance(gv, dict):
                st["groups"][gk] = {kk: int(gv.get(kk) or 0) for kk in _empty_group()}
    p = base.get("params")
    if isinstance(p, dict):
        st["params"].update(p)
    return st


def _record_new(st, pool_rows, board_date):
    """录入涨停池信号（lbc∈{1,2}，剔 ST，按 code|board_date 去重）。无取数——结果在成熟时才算。

    board_date = 该池的**真实日期**（调用方传入，禁按运行日盖章——2026-10-20 事故根因）；
    行内可带自带 "board_date"（补录旧日期用），优先于函数参数。"""
    seen = set(x for x in (st.get("recorded") or []) if isinstance(x, str))
    pend_keys = {(p.get("code"), p.get("board_date")) for p in st.get("pending", [])}
    added = 0
    added_by_date = {}
    for row in pool_rows or []:
        code = str(row.get("code") or "").strip()
        name = str(row.get("name") or "")
        try:
            lbc = int(row.get("lbc") or 1)
        except Exception:
            lbc = 1
        if not code or lbc not in (1, 2):
            continue
        if name.startswith(("ST", "*ST", "st", "*st")):
            continue
        bd = str(row.get("board_date") or board_date or "")
        if not bd:
            continue
        key = (code, bd)
        if key in pend_keys or f"{code}|{bd}" in seen:
            continue
        st["pending"].append({"code": code, "name": name,
                              "type": "first" if lbc == 1 else "second",
                              "board_date": bd})
        seen.add(f"{code}|{bd}")
        st["recorded"].append(f"{code}|{bd}")
        st["recorded"] = st["recorded"][-RECORDED_KEEP:]
        st["signals_total"] = int(st.get("signals_total") or 0) + 1
        added += 1
        added_by_date[bd] = added_by_date.get(bd, 0) + 1
    sd = st.setdefault("signal_dates", {})
    for bd, n in added_by_date.items():
        sd[bd] = int(sd.get(bd) or 0) + n
    if added:
        st["last_signal_date"] = max(added_by_date)     # 信号覆盖日（幂等判重键）
        if st.get("first_date") is None or min(added_by_date) < st["first_date"]:
            st["first_date"] = min(added_by_date)
    return added


def _mature_one(st, p, bars, today):
    """单笔在途信号成熟判定与计入。返回 True=已了结（成熟/一字剔除/过期），移出 pending。"""
    bd = p.get("board_date")
    idx = None
    for i, b in enumerate(bars):
        if b[0] == bd:
            idx = i
            break
    if idx is None:
        try:
            age = (today - datetime.strptime(bd, "%Y-%m-%d").date()).days
        except Exception:
            return False
        if age > EXPIRE_DAYS:
            st["expired"] = int(st.get("expired") or 0) + 1
            return True                      # 过期丢弃
        return False                         # 数据未到，留在途
    if len(bars) < idx + 1 + MATURE_BARS:
        return False                         # T+5 未满，留在途（绝不插值）
    day, o, h, l, c, v = bars[idx]
    if _is_yiziban(o, h, l, c):
        st["dropped_yiziban"] = int(st.get("dropped_yiziban") or 0) + 1
        return True                          # 一字板信号剔除（跑批口径）
    nxt = bars[idx + 1]
    t5 = bars[idx + MATURE_BARS]
    next_open = nxt[1]
    if next_open <= 0:
        st["expired"] += 1
        return True
    limit = _limit_pct(p.get("code"))
    promo = (nxt[4] / c - 1) >= (limit - 0.002)   # 容 0.2pp 价格取整
    gap = next_open > c
    tradable = not _is_yiziban(nxt[1], nxt[2], nxt[3], nxt[4])
    t1_ret = nxt[4] / next_open - 1
    t5_ret = t5[4] / next_open - 1
    vr = None
    if idx >= VR_WINDOW:
        prev = [b[5] for b in bars[idx - VR_WINDOW:idx]]
        avg = sum(prev) / len(prev)
        if avg > 0:
            vr = v / avg
    if p.get("type") == "first":
        targets = ["first_all"]
        if vr is not None:
            if vr >= VR_MIN:
                targets.append("first_vr3")
            if vr >= 8:
                targets.append("first_vr8")
            elif vr >= 5:
                targets.append("first_vr5_8")
            elif vr >= VR_MIN:
                targets.append("first_vr3_5")
    else:
        targets = ["second_all"]
        if vr is not None:
            targets.append("second_vr3" if vr >= VR_MIN else "second_vrlt3")
    for gk in targets:
        g = st["groups"][gk]
        g["n"] += 1
        g["promo"] += 1 if promo else 0
        g["gap"] += 1 if gap else 0
        g["t1_n"] += 1
        g["t1_win"] += 1 if t1_ret > COST_RT else 0
        if tradable:
            g["t1t_n"] += 1
            g["t1t_win"] += 1 if t1_ret > COST_RT else 0
        g["t5_n"] += 1
        g["t5_win"] += 1 if t5_ret > COST_RT else 0
    st["matured_total"] = int(st.get("matured_total") or 0) + 1
    st["last_mature_date"] = day
    return True


def update(base, pool_rows, kline=None, now=None, board_date=None):
    """主入口：基线 store + 涨停池信号行 → 更新后的 store。

    pool_rows: [{"code","name","lbc"[,"board_date"]}]（lbc=连板数；由 cloud_fetch_v8._get_zt_pool 提供；
               行内 board_date 优先——补录旧日期用；缺省取 board_date 参数）
    board_date: 本批信号对应的**涨停池真实日期**（缺省=运行日；2026-10-20 修复后调用方显式传入）
    kline:    可选取数函数(code, n) → 新浪日K list（测试可注入假数据）
    """
    fetch = kline or _sina_kline
    st = _norm_store(base)
    now = now or _now_cst()
    today = now.strftime("%Y-%m-%d")
    added = _record_new(st, pool_rows, board_date or today)
    still, matured = [], 0
    for p in st.get("pending", []):
        try:
            age = (now.date() - datetime.strptime(p.get("board_date"), "%Y-%m-%d").date()).days
        except Exception:
            still.append(p)
            continue
        if age < SKIP_AGE_DAYS:
            still.append(p)                  # 不可能成熟，不取数
            continue
        try:
            bars = _bars(fetch(p.get("code"), KLINES))
        except Exception as e:
            print(f"    ⚠️ {p.get('code')} K线取数失败: {e}")
            still.append(p)
            continue
        if _mature_one(st, p, bars, now.date()):
            matured += 1
        else:
            still.append(p)
    st["pending"] = still
    st["last_run_date"] = today
    print(f"  [LIANBAN] 本轮录入 {added} 笔 · 在途 {len(still)} 笔 · 本轮成熟 {matured} 笔 · "
          f"累计成熟 {st['matured_total']} · 过期 {st['expired']} · 一字剔除 {st['dropped_yiziban']} · "
          f"信号覆盖 {sorted(st.get('signal_dates') or {})}")
    return st


# ───────────────────────── 自测（合成K线，无网络） ─────────────────────────

def _selftest():
    """三场景：①正常成熟计分组 ② immature 留在途 ③ 过期丢弃。"""
    def _bar(day, o, h, l, c, v):
        return {"day": day, "open": o, "high": h, "low": l, "close": c, "volume": v}

    # ① 600000 主板：信号日 10-10 收 10.00；次日开 10.20 收 11.00（+10% 晋级、T+1 胜）
    #    第5日收 10.50（T+5 胜）；前 20 日量 1000、信号日量 4000 ⇒ 倍量 4.0（3~5 桶）
    pre = [(f"2026-09-{dd:02d}", 9.9, 10.0, 9.8, 9.9, 1000) for dd in range(1, 21)]
    sig = ("2026-10-10", 9.9, 10.0, 9.8, 10.00, 4000)
    nxt = ("2026-10-13", 10.20, 11.00, 10.10, 11.00, 5000)   # 开>信号收 ⇒ 高开；收=11.00 ⇒ +10% 晋级
    mid = [("2026-10-14", 11.0, 11.1, 10.9, 11.05, 4000),
           ("2026-10-15", 11.05, 11.2, 11.0, 11.10, 4000),
           ("2026-10-16", 11.1, 11.15, 10.8, 10.90, 4000),
           ("2026-10-19", 10.9, 10.95, 10.5, 10.70, 4000)]
    t5b = ("2026-10-20", 10.7, 10.75, 10.4, 10.50, 4000)     # T+5 收 10.50 ⇒ 收益 2.94% > 0.3% 胜
    fake = [_bar(*b) for b in (pre + [sig, nxt] + mid + [t5b])]

    st = skeleton()
    st["pending"] = [{"code": "600000", "name": "浦发银行", "type": "first",
                      "board_date": "2026-10-10"}]
    st = update(st, [], kline=lambda c, n: fake,
                now=datetime(2026, 10, 20, 17, 30, tzinfo=CST))
    g = st["groups"]["first_all"]
    assert st["pending"] == [], "成熟后应移出 pending"
    assert g["n"] == 1 and g["promo"] == 1 and g["gap"] == 1, g
    assert g["t1_win"] == 1 and g["t1t_win"] == 1 and g["t5_win"] == 1, g
    assert st["groups"]["first_vr3"]["n"] == 1, "倍量4.0 应进 first_vr3"
    assert st["groups"]["first_vr3_5"]["n"] == 1, "倍量4.0 应进 first_vr3_5"
    assert st["groups"]["first_vr5_8"]["n"] == 0
    assert st["groups"]["first_vr8"]["n"] == 0
    print("  ① 成熟计分组 OK", g)

    # ② immature：信号日 10-16，今天 10-20（age=4<7 跳过取数）⇒ 留在途
    st2 = skeleton()
    st2["pending"] = [{"code": "000001", "name": "平安银行", "type": "first",
                       "board_date": "2026-10-16"}]
    st2 = update(st2, [], kline=lambda c, n: fake,
                 now=datetime(2026, 10, 20, 17, 30, tzinfo=CST))
    assert len(st2["pending"]) == 1 and st2["matured_total"] == 0, " immature 应留在途"
    print("  ② immature 留在途 OK")

    # ③ 过期：board_date 早于假K线覆盖范围（2026-08-01，假数据最早 09-01）且超 30 天 ⇒ expired+1 移出
    st3 = skeleton()
    st3["pending"] = [{"code": "300750", "name": "宁德时代", "type": "second",
                       "board_date": "2026-08-01"}]
    st3 = update(st3, [], kline=lambda c, n: fake,
                 now=datetime(2026, 10, 20, 17, 30, tzinfo=CST))
    assert st3["pending"] == [] and st3["expired"] == 1, st3
    print("  ③ 过期丢弃 OK")

    # ④ 去重：同 (code, date) 重复入池不双录
    st4 = skeleton()
    st4 = update(st4, [{"code": "600000", "name": "浦发银行", "lbc": 1}],
                 kline=lambda c, n: fake, now=datetime(2026, 10, 10, 17, 30, tzinfo=CST))
    st4 = update(st4, [{"code": "600000", "name": "浦发银行", "lbc": 1}],
                 kline=lambda c, n: fake, now=datetime(2026, 10, 10, 18, 30, tzinfo=CST))
    assert st4["signals_total"] == 1 and len(st4["pending"]) == 1, st4
    print("  ④ 同日去重 OK")

    # ⑤ ST 剔除
    st5 = update(skeleton(), [{"code": "600000", "name": "*ST 例题", "lbc": 1}],
                 kline=lambda c, n: fake, now=datetime(2026, 10, 10, 17, 30, tzinfo=CST))
    assert st5["signals_total"] == 0 and st5["pending"] == []
    print("  ⑤ ST 剔除 OK")

    # ⑥ 2026-10-20 修复：信号覆盖日盖章（last_signal_date/signal_dates）
    st6 = update(skeleton(), [{"code": "600000", "name": "浦发银行", "lbc": 1}],
                 kline=lambda c, n: fake, now=datetime(2026, 10, 10, 17, 30, tzinfo=CST))
    assert st6["last_signal_date"] == "2026-10-10", st6["last_signal_date"]
    assert st6["signal_dates"] == {"2026-10-10": 1}, st6["signal_dates"]
    assert st6["first_date"] == "2026-10-10"
    print("  ⑥ 信号覆盖日盖章 OK", st6["signal_dates"])

    # ⑦ 2026-10-20 修复：行级 board_date 补录旧日期（复刻 10-16 池补录）
    st7 = skeleton()
    rows = [{"code": "600000", "name": "浦发银行", "lbc": 1, "board_date": "2026-10-16"},
            {"code": "000001", "name": "平安银行", "lbc": 2, "board_date": "2026-10-16"}]
    st7 = update(st7, rows, kline=lambda c, n: fake,
                 now=datetime(2026, 10, 20, 17, 30, tzinfo=CST))
    assert st7["signal_dates"] == {"2026-10-16": 2}, st7["signal_dates"]
    assert st7["last_signal_date"] == "2026-10-16" and st7["first_date"] == "2026-10-16"
    assert all(p["board_date"] == "2026-10-16" for p in st7["pending"])
    # 同批重复补录 → dedup 不虚增
    st7b = update(st7, rows, kline=lambda c, n: fake,
                  now=datetime(2026, 10, 20, 17, 31, tzinfo=CST))
    assert st7b["signal_dates"] == {"2026-10-16": 2} and st7b["signals_total"] == 2
    print("  ⑦ 行级补录日期+去重 OK", st7b["signal_dates"])

    # ⑧ 2026-10-20 修复：同 code 不同 board_date 不互相误去重（10-16 与 10-19 各录各的）
    st8 = update(skeleton(),
                 [{"code": "600000", "name": "浦发银行", "lbc": 1, "board_date": "2026-10-16"}],
                 kline=lambda c, n: fake, now=datetime(2026, 10, 20, 17, 30, tzinfo=CST))
    st8 = update(st8,
                 [{"code": "600000", "name": "浦发银行", "lbc": 1, "board_date": "2026-10-19"}],
                 kline=lambda c, n: fake, now=datetime(2026, 10, 20, 17, 31, tzinfo=CST))
    assert st8["signals_total"] == 2, st8["signals_total"]
    assert st8["signal_dates"] == {"2026-10-16": 1, "2026-10-19": 1}
    assert st8["first_date"] == "2026-10-16" and st8["last_signal_date"] == "2026-10-19"
    print("  ⑧ 跨日期不误去重 OK", st8["signal_dates"])
    print("LIANBAN 自测全部通过 ✅")


if __name__ == "__main__":
    _selftest()
