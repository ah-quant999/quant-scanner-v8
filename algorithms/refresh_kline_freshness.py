# -*- coding: utf-8 -*-
"""
K 线缓存新鲜度修复（2026-10-22 ff3 对拍 ima 根因修复 · 一劳永逸）

═══ 事故（2026-10-22 实测）═══
  ff3 对拍 ima 前一周数据，Top8 命中 0/8、Bot8 命中 0/8，逐日排查定位到：
  raw_data/_wf_cache 里的日 K **大面积陈旧** ——
    · 全池 4518 只有效票中，10-13 之后仍有日线的仅 394 只（10-20 仅 77 只）
    · ima 每日 8 只在目标日「有 K 线」的仅 0~3 只
  ⇒ 算法在**物理上无法选中** ima 的票（不是因子不准，是没有当日数据）。

  根因两道：
  ① factor_walkforward.get_klines() 命中缓存即 return ⇒ **缓存永不更新**（无新鲜度校验）
  ② 抓取用 12~16 线程并发打新浪 ⇒ **触发 501 限流**（实测并发全 501、串行 100% 成功）
     ⇒ 失败被 catch 成「本票无数据」，于是缓存里留下半截/陈旧数据而不报错。

═══ 本脚本 ═══
  ① 逐票检查缓存最新日期；早于 TARGET 则重抓
  ② **串行 + 限速**（默认 0.35s/只）+ 失败重试 3 次（指数退避），规避 501
  ③ 新旧按 date 合并写回（保留更长历史，不丢早期数据）
  ④ 只补「陈旧」票，不做全量重抓 ⇒ 增量、幂等、可反复跑

用法（生产链）：
    python algorithms/refresh_kline_freshness.py                # 全量补到今天
    python algorithms/refresh_kline_freshness.py --target 2026-10-22
    python algorithms/refresh_kline_freshness.py --only 600693,002172
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "algorithms"))
import factor_walkforward as fw

CACHE = fw.CACHE
DEFAULT_TARGET = datetime.now().strftime("%Y-%m-%d")


def log(m=""):
    print(m, flush=True)


def load_cache(code):
    p = os.path.join(CACHE, code + ".json")
    if not os.path.exists(p):
        return None
    try:
        rows = json.load(open(p, encoding="utf-8"))
        return rows or None
    except Exception:
        return None


def fetch_with_retry(code, retries=3):
    """串行抓取 + 重试（新浪优先，腾讯兜底）。返回 (rows|None, 说明)。"""
    last = ""
    for a in range(retries):
        for fn, name in ((fw._fetch_sina, "sina"), (fw._fetch_gtimg, "gtimg")):
            try:
                rows = fn(code)
                if rows and len(rows) >= fw.MIN_BARS:
                    rows.sort(key=lambda r: r["date"])
                    return rows, "%s#%d" % (name, a + 1)
                last = "%s 返回 %d 根（不足 MIN_BARS=%d）" % (name, len(rows or []), fw.MIN_BARS)
            except Exception as e:
                last = "%s %s" % (name, e)
        time.sleep(1.5 * (a + 1))
    return None, last


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=DEFAULT_TARGET, help="目标最新日期（含）")
    ap.add_argument("--delay", type=float, default=0.35, help="每只之间的限速秒（规避新浪 501）")
    ap.add_argument("--only", default="", help="只刷指定 code（逗号分隔），调试用")
    ap.add_argument("--retries", type=int, default=3)
    args = ap.parse_args()

    t0 = time.time()
    log("=" * 74)
    log("  K 线缓存新鲜度修复  目标 ≥ %s  %s"
        % (args.target, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    log("=" * 74)
    os.makedirs(CACHE, exist_ok=True)
    codes = fw.load_universe()
    if args.only:
        keep = set(x.strip() for x in args.only.split(",") if x.strip())
        codes = [c for c in codes if c in keep]
    log("待检 %d 只" % len(codes))

    stale, ok_cnt = [], 0
    for c in codes:
        rows = load_cache(c)
        if rows and rows[-1].get("date", "") >= args.target:
            ok_cnt += 1
        else:
            stale.append(c)
    log("扫描完成：已是最新 %d  陈旧 %d" % (ok_cnt, len(stale)))
    if not stale:
        log("[ok] 全部已是最新，无需刷新")
        return 0

    fixed, err = 0, {}
    for i, c in enumerate(stale):
        new, src = fetch_with_retry(c, args.retries)
        if new:
            old = load_cache(c)
            if old:
                m = {r["date"]: r for r in old}
                for r in new:
                    m[r["date"]] = r
                merged = [m[k] for k in sorted(m)]
            else:
                merged = new
            with open(os.path.join(CACHE, c + ".json"), "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False)
            fixed += 1
        else:
            err[c] = src
        time.sleep(args.delay)
        if (i + 1) % 100 == 0:
            log("  刷新 %d/%d  成功 %d  失败 %d  用时 %.0fs"
                % (i + 1, len(stale), fixed, len(err), time.time() - t0))

    log("刷新完成：成功 %d / %d，失败 %d" % (fixed, len(stale), len(err)))
    for c, e in list(err.items())[:5]:
        log("  ⚠️ %s: %s" % (c, e))
    from collections import Counter
    cc = Counter()
    for c in codes:
        rows = load_cache(c)
        if rows:
            cc[rows[-1].get("date", "?")] += 1
    log("最新日期分布 TOP10：%s" % cc.most_common(10))
    log("用时 %.0fs" % (time.time() - t0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
