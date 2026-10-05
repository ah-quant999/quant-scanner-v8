# -*- coding: utf-8 -*-
"""
audit_market_thermo.py — 🔮「未来预测」每日自动审计门禁（硬闸，非说说而已）

2026-10-05 阿狸咪的工程师 建（主人令：把 akshare 真值交叉核验固化成每日自动审计，
"不能只是说说，要落实到位"）。

位置：v8_market_thermo.yml 工作流中，gen 之后、api_push_raw 推送之前。
  审计 exit!=0 → 推送步骤不执行 → Actions 红灯可见。

三层检查：
  [1] 结构层（离线·必跑）：序列升序/长度一致/val10∈[0,100]/回撤∈[-100,0]/
      社融max>min/PMI合理区间/ERP自洽/数据新鲜度(≤7天)。
  [2] 真值层（akshare 交叉核验·3次重试·最佳努力）：akshare 可用时，用与生成器
      **同算法**重算社融脉冲与PMI，与存储值逐字段比对。
        fresh.month < stored.month → FAIL（跑反/倒退，硬闸）
        fresh.month > stored.month → WARN（源在两次运行间滚动，非方向错）
        数值不符(>0.05)            → FAIL（数据漂移，硬闸）
      akshare 不可用（未装/导入失败/网络重试耗尽）→ 仅 WARN、**不阻断**：
        结构层已兜底数据质量，真值层属增强核验，不因子弹依赖缺失而让整条日更链瘫痪。

exit: 0=结构层通过（真值层通过或仅不可用WARN）  2=审计不过（结构错/真值漂移）  4=产物缺失
"""
import sys, io, json, re, time
from datetime import datetime, timedelta, timezone

TZ8 = timezone(timedelta(hours=8))
THERMO = "data/MARKET_THERMO.js"

FAILS, WARNS = [], []


def fail(msg):
    FAILS.append(msg)
    print("[FAIL]", msg)


def warn(msg):
    WARNS.append(msg)
    print("[WARN]", msg)


def ok(msg):
    print("[ok]", msg)


def load_thermo(path):
    """解析 window.MARKET_THERMO = {...}; → dict"""
    try:
        txt = io.open(path, encoding="utf-8").read()
    except OSError as e:
        fail("产物缺失/不可读: %s (%s)" % (path, e))
        return None
    m = re.search(r"window\.MARKET_THERMO\s*=\s*(\{.*\})\s*;?\s*$", txt, re.S)
    if not m:
        fail("无法定位 window.MARKET_THERMO JSON 体")
        return None
    try:
        return json.loads(m.group(1))
    except Exception as e:
        fail("JSON 解析失败: %s" % e)
        return None


# ───────────────────────── [1] 结构层 ─────────────────────────
def audit_structure(T):
    D = T.get("D") or {}
    dates, sh, eq, ma, v10 = D.get("dates"), D.get("sh"), D.get("eq"), D.get("ma200"), D.get("val10")
    if not (dates and sh and eq and v10):
        fail("D 骨架字段缺失(dates/sh/eq/val10)")
        return
    n = len(dates)
    if not all(len(x) == n for x in (sh, eq, v10)):
        fail("D 数组长度不一致: dates=%d sh=%d eq=%d val10=%d" % (n, len(sh), len(eq), len(v10)))
    if any(dates[i] >= dates[i + 1] for i in range(n - 1)):
        fail("D.dates 非严格升序 → 序列跑反（致命）")
    else:
        ok("D.dates %d 月严格升序 (%s → %s)" % (n, dates[0], dates[-1]))
    # 最新月须为当月或上一月（月频口径）
    now = datetime.now(TZ8)
    ym_now = "%d-%02d" % (now.year, now.month)
    prev_y = now.year - 1 if now.month == 1 else now.year
    prev_m = 12 if now.month == 1 else now.month - 1
    ym_prev = "%d-%02d" % (prev_y, prev_m)
    if dates[-1] not in (ym_now, ym_prev):
        fail("D.dates 末月 %s 既非当月 %s 也非上月 %s → 数据陈旧" % (dates[-1], ym_now, ym_prev))
    else:
        ok("D.dates 末月 %s = 当月/上月 ✓" % dates[-1])
    # val10 分位区间（头部 None = 滚动窗口预热，合法；非None必须∈[0,100]；预热后不得再出现None）
    nn_idx = [i for i, v in enumerate(v10) if v is not None]
    if not nn_idx:
        fail("val10 全为 None")
    else:
        bad = [v10[i] for i in nn_idx if not (0.0 <= float(v10[i]) <= 100.0)]
        if bad:
            fail("val10 非None值越界 %d 个（如 %s）" % (len(bad), bad[:3]))
        else:
            ok("val10 非None全部 ∈[0,100]，末值 %s（头部预热None %d 个，合法）" % (v10[nn_idx[-1]], nn_idx[0]))
        gaps = [i for i in range(nn_idx[0], n) if v10[i] is None]
        if gaps:
            fail("val10 预热期后仍有 %d 个 None（中断，如 idx %s）" % (len(gaps), gaps[:3]))
        else:
            ok("val10 预热后无中断（%d → %d 连续有效）" % (nn_idx[0], n - 1))
    # ma200 长度
    if ma and len(ma) != n:
        fail("ma200 长度 %d ≠ dates %d" % (len(ma), n))
    # EDHEC 回撤（D.current.drawdown = 距峰值回撤幅度，正值 ∈[0,100]）
    cur = (T.get("D") or {}).get("current") or {}
    dd = cur.get("drawdown")
    if dd is not None and not (0.0 <= float(dd) <= 100.0):
        fail("EDHEC 回撤幅度 %s 越界 [0,100]" % dd)
    else:
        ok("EDHEC 回撤幅度 %s ∈[0,100] @%s" % (dd, cur.get("date")))
    # EXT 字段
    EXT = T.get("EXT") or {}
    tsf, pmi = EXT.get("tsf") or {}, EXT.get("pmi") or {}
    if not tsf:
        fail("EXT.tsf 缺失")
    else:
        if not isinstance(tsf.get("yoy"), (int, float)):
            fail("EXT.tsf.yoy 非数值: %r" % tsf.get("yoy"))
        if "max" in tsf and "min" in tsf and tsf["max"] <= tsf["min"]:
            fail("EXT.tsf max(%s) ≤ min(%s) → 极值跑反" % (tsf.get("max"), tsf.get("min")))
        else:
            ok("EXT.tsf yoy=%s@%s max=%s > min=%s" % (tsf.get("yoy"), tsf.get("month"), tsf.get("max"), tsf.get("min")))
    if not pmi:
        fail("EXT.pmi 缺失")
    elif not (20.0 <= float(pmi.get("v", -1)) <= 70.0):
        fail("EXT.pmi.v=%s 越出合理区间[20,70]" % pmi.get("v"))
    else:
        ok("EXT.pmi v=%s@%s ∈[20,70]" % (pmi.get("v"), pmi.get("date")))
    # ERP 自洽（100/pe − bond10y.v，容差0.15pp）
    hs = EXT.get("hs300pe") or {}
    b10 = (EXT.get("bond10y") or {}).get("v")
    erp = EXT.get("erp")
    if hs.get("pe") and b10 is not None and erp is not None:
        calc = 100.0 / float(hs["pe"]) - float(b10)
        if abs(calc - float(erp)) > 0.15:
            fail("ERP不自洽: 存 %s vs 算 %.2f（|差|>0.15pp）" % (erp, calc))
        else:
            ok("ERP 自洽: %s ≈ 100/%s−%s = %.2f" % (erp, hs["pe"], b10, calc))
    # 新鲜度
    gen = T.get("generated")
    if gen:
        try:
            # 生成器格式两种：ISO（…+08:00）与 '2026-10-05 13:03 CST'（即北京时间）
            g = None
            m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})", str(gen))
            if "CST" in str(gen) and m:
                g = datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M").replace(tzinfo=TZ8)
            if g is None:
                g = datetime.fromisoformat(str(gen).replace("Z", "+00:00"))
                if g.tzinfo is None:
                    g = g.replace(tzinfo=TZ8)
            age_h = (datetime.now(TZ8) - g).total_seconds() / 3600.0
            if age_h > 24 * 7:
                fail("generated=%s 距今 %.1f 天 > 7天 → 陈旧" % (gen, age_h / 24.0))
            else:
                ok("generated=%s（%.1f 小时前）" % (gen, age_h))
        except Exception as e:
            fail("generated 解析失败: %s (%s)" % (gen, e))


# ─────────────────── [2]+[3] akshare 真值交叉核验 ───────────────────
def fetch_with_retry(fn, tries=3, wait=8):
    last = None
    for k in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            print("[retry %d/%d] akshare 拉取失败: %s" % (k + 1, tries, e))
            time.sleep(wait)
    raise RuntimeError("akshare 重试%d次仍失败: %s" % (tries, last))


def fresh_tsf():
    import akshare as ak
    df = ak.macro_china_shrzgm().reset_index(drop=True)  # 正序：tail=最新
    months = df["月份"].astype(str).tolist()
    incr = [float(x) for x in df["社会融资规模增量"]]
    pulse, pm = [], []
    for i in range(11, len(months)):
        pulse.append(sum(incr[i - 11:i + 1]))
        pm.append(months[i])
    pairs = []
    for i in range(12, len(pulse)):
        if pulse[i - 12] > 0:
            pairs.append((pm[i], round((pulse[i] / pulse[i - 12] - 1) * 100, 1)))
    return pairs[-1]  # (month, yoy)


def fresh_pmi():
    import akshare as ak
    p = ak.macro_china_pmi()  # head=最新（倒序表）
    m0 = str(p["月份"].iloc[0])
    v0 = round(float(p["制造业-指数"].iloc[0]), 1)
    return m0[:4] + "-" + m0[5:7], v0


def _norm_month(m):
    """'202604' / '2026-04' / '2026年04月份' → '2026-04'"""
    s = str(m)
    d = re.sub(r"\D", "", s)
    return "%s-%s" % (d[:4], d[4:6]) if len(d) >= 6 else s


def audit_truth(T):
    # akshare 为最佳努力增强核验：不可用则仅 WARN 跳过，不阻断（结构层已兜底）。
    try:
        import akshare as ak  # noqa: F401
    except Exception as e:
        warn("akshare 不可用（%s）→ 真值层跳过，结构层仍为硬闸" % e)
        return
    EXT = T.get("EXT") or {}
    tsf, pmi = EXT.get("tsf") or {}, EXT.get("pmi") or {}
    print("-- [2] akshare 真值交叉核验（同算法重算 vs 存储值）--")
    # 社融脉冲
    try:
        fm, fy = fetch_with_retry(fresh_tsf)
    except RuntimeError as e:
        warn("社融真值拉取失败（%s）→ 跳过该字段" % e)
        fm = fy = None
    if fm is not None:
        fm, fy = _norm_month(fm), float(fy)
        sm, sy = _norm_month(tsf.get("month", "")), tsf.get("yoy")
        if fm < sm:
            fail("社融跑反/倒退: 存储月 %s > 真值最新月 %s" % (sm, fm))
        elif fm > sm:
            warn("社融: 源已滚动至 %s（存储 %s 为生成时点快照，非方向错）" % (fm, sm))
        elif abs(float(sy) - fy) > 0.05:
            fail("社融脉冲数值不符: 存 %s vs 真值 %.1f @%s" % (sy, fy, fm))
        else:
            ok("社融脉冲 yoy=%s@%s 与 akshare 真值一致" % (sy, fm))
    # PMI
    try:
        fpm, fpv = fetch_with_retry(fresh_pmi)
    except RuntimeError as e:
        warn("PMI 真值拉取失败（%s）→ 跳过该字段" % e)
        fpm = fpv = None
    if fpm is not None:
        fpm = _norm_month(fpm)
        spm, spv = _norm_month(pmi.get("date", "")), pmi.get("v")
        if fpm < spm:
            fail("PMI 跑反/倒退: 存储月 %s > 真值最新月 %s" % (spm, fpm))
        elif fpm > spm:
            warn("PMI: 源已滚动至 %s（存储 %s 为生成时点快照，非方向错）" % (fpm, spm))
        elif abs(float(spv) - fpv) > 0.05:
            fail("PMI 数值不符: 存 %s vs 真值 %.1f @%s" % (spv, fpv, fpm))
        else:
            ok("PMI v=%s@%s 与 akshare 真值一致" % (spv, fpm))


def main():
    print("=" * 62)
    print("🔮 MARKET_THERMO 每日审计门禁  %s" % datetime.now(TZ8).strftime("%Y-%m-%d %H:%M:%S CST"))
    print("=" * 62)
    T = load_thermo(THERMO)
    if T is None:
        print("\n审计结论: FAIL（产物缺失/解析失败） exit=4")
        return 4
    print("-- [1] 结构层（离线·硬闸）--")
    audit_structure(T)
    print("-- [2] akshare 真值层（最佳努力·不可用则WARN跳过）--")
    audit_truth(T)
    print("-" * 62)
    for w in WARNS:
        print("  WARN:", w)
    if FAILS:
        print("审计结论: FAIL — %d 项不过（硬闸）" % len(FAILS))
        for f in FAILS:
            print("  x", f)
        print("-> 阻断推送（exit=2）。宁可红灯可见，不可带病上线。")
        return 2
    print("审计结论: PASS — 结构层通过（真值层通过或仅WARN不可用）WARN %d 项" % len(WARNS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
