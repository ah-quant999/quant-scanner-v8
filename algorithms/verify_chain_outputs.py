#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_chain_outputs.py — v8 盘后算法链「产物完整性闸门」
=========================================================
🛡 2026-08-28 一劳永逸修复（主站审计 P0-1）：

症状
    盘后算法链「跑一半」无人知晓——Actions job 全绿 success，但核心选股产物
    实际停在昨晚甚至前天。2026-08-28 实测：
        CANDIDATE(候选池)   停 08-26 22:36 → 1.9 天
        CRDS(逆势龙头)      停 08-27 19:53
        STOCK_RPS(相对强度)  停 08-27 19:58
        FINAL_RECOMMEND     停 08-27 21:02

根因（三重叠加）
    ① run_algorithms.py 对每个脚本 continue-on-error，单脚本失败被静默吞掉，
       只在 stdout 打一行「⚠️ 退出码 N」，无人看、无汇总、无告警；
    ② workflow step「🧮 运行盘后算法链」用 `set +e` + `echo "algo exit: $?"`
       **显式丢弃退出码**，job 永远 success；
    ③ 上游不动则下游全停（候选池是 CRDS / RPS / 最终推荐的共同底座），
       但整条链没有任何「产物是否真的产出了」的校验环节。

修复
    链尾加一道闸门，按**文件内容里的 update_time** 校验核心产物是否本交易日产出。
    ⚠️ 刻意不使用文件 mtime —— actions/checkout 会把所有文件 mtime 重置为
    checkout 时刻，未更新的文件 mtime 同样是「新」的，用 mtime 判断会 100% 误判为新鲜。
    缺失 / 陈旧 → exit 1，让 job 显式失败并触发既有告警链路；
    同时写 $GITHUB_STEP_SUMMARY 与 raw_data/algo_chain_report.json，
    让主人一眼看到断在哪一环，而不是对着全绿的 job 发呆。

用法
    python algorithms/verify_chain_outputs.py               # 严格：核心项陈旧即 exit 1
    python algorithms/verify_chain_outputs.py --warn-only    # 只报告不失败（调试/非交易日）
    python algorithms/verify_chain_outputs.py --date 2026-08-28   # 指定基准日（默认今天 CST）
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

CST = timezone(timedelta(hours=8))
ALGO = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(ALGO)

# 核心产物清单：(展示名, 相对路径, 是否必需)
#   必需=True  → 陈旧/缺失直接判失败（exit 1）
#   必需=False → 只告警，不影响退出码（低频/依赖外部源的产物）
# 只列「每交易日必须刷新」的选股链路产物；PORTFOLIO_COST / CONCEPT_ETF_MAP
# 一类低频文件不在此列（它们陈旧属正常，由 HEALTH_CHECK 白名单管）。
CRITICAL = [
    ("候选池",       "raw_data/candidate.json",        True),
    ("候选池(前端)", "data/CANDIDATE.js",              True),
    ("逆势龙头CRDS", "raw_data/crds_card_data.json",   True),
    ("逆势龙头(前端)", "data/CRDS_CARD_DATA.js",       True),
    ("相对强度RPS",  "data/STOCK_RPS.js",              True),
    ("全站精选TOP10", "raw_data/top10_daily.json",     True),
    ("全站精选(前端)", "data/TOP10_DAILY.js",          True),
    ("三重共识",     "raw_data/triple_consensus.json", True),
    ("三重共识(前端)", "data/TRIPLE_CONSENSUS.js",     True),
    ("四量终极",     "data/FOUR_VOLUME.js",            True),
    ("四量终极60m",  "data/FOUR_VOLUME_60M.js",        True),
    ("最终推荐",     "raw_data/final_recommend.json",  True),
    ("最终推荐(前端)", "data/FINAL_RECOMMEND_DATA.js", True),
    ("金股池",       "raw_data/gold_pool.json",        False),
    ("MAHORO",       "raw_data/mahoro.json",           False),
]

# 时间戳字段名按优先级尝试（各生成器写法不统一，这里做兼容层）
TS_KEYS = ["update_time", "updated_at", "updated", "last_update", "更新时间", "date", "trade_date"]

_TS_RE_CACHE = {}


def _ts_regex():
    keys = "|".join(TS_KEYS)
    if keys not in _TS_RE_CACHE:
        _TS_RE_CACHE[keys] = re.compile(r'"(?:' + keys + r')"\s*:\s*"([^"]{6,32})"')
    return _TS_RE_CACHE[keys]


def extract_ts(path):
    """从 JSON / window.X={...} 形态的 js 中提取时间戳字符串。

    返回 (ts_str, err)；err ∈ {None, 'MISSING_FILE', 'READ_FAIL', 'NO_TS_FIELD'}
    """
    if not os.path.exists(path):
        return None, "MISSING_FILE"
    try:
        size = os.path.getsize(path)
        # 最大已知产物 434KB，8MB 上限足够；避免极端情况一次读入超大文件
        with open(path, encoding="utf-8", errors="ignore") as f:
            raw = f.read(8 * 1024 * 1024) if size <= 8 * 1024 * 1024 else f.read(2 * 1024 * 1024)
    except Exception:
        return None, "READ_FAIL"
    m = _ts_regex().search(raw)
    if not m:
        return None, "NO_TS_FIELD"
    return m.group(1), None


def parse_date(ts):
    """从任意时间戳串里取出 YYYY-MM-DD（兼容 'YYYY-MM-DD HH:MM:SS' / 'T' 分隔 / 纯日期）。"""
    if not ts:
        return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", ts)
    return m.group(0) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--warn-only", action="store_true", help="只报告，不因陈旧而 exit 1")
    ap.add_argument("--date", default=None, help="基准交易日 YYYY-MM-DD（默认今天 CST）")
    args = ap.parse_args()

    today = args.date or datetime.now(CST).strftime("%Y-%m-%d")
    print("=" * 72)
    print(f"🛡 盘后算法链产物完整性闸门 | 基准交易日 {today}"
          f"{'（warn-only 模式）' if args.warn_only else ''}")
    print("=" * 72)

    rows = []
    for name, rel, required in CRITICAL:
        path = os.path.join(ROOT, rel)
        ts, err = extract_ts(path)
        if err == "MISSING_FILE":
            rows.append((name, rel, "❌ 缺失", "-", required, "文件不存在"))
            continue
        if err == "READ_FAIL":
            rows.append((name, rel, "❌ 读取失败", "-", required, "文件不可读"))
            continue
        if err == "NO_TS_FIELD":
            # 无法判定新鲜度 = 盲区，必需项按失败处理（推动补齐时间戳字段）
            rows.append((name, rel, "⚠️ 无时间戳", "-", required,
                         "未找到 update_time 等字段，无法判定新鲜度"))
            continue
        d = parse_date(ts)
        if not d:
            rows.append((name, rel, "⚠️ 时间戳异常", ts, required, "无法解析日期"))
        elif d == today:
            rows.append((name, rel, "✅ 本日新鲜", ts, required, ""))
        else:
            try:
                gap = (datetime.strptime(today, "%Y-%m-%d") - datetime.strptime(d, "%Y-%m-%d")).days
            except Exception:
                gap = -1
            rows.append((name, rel, f"❌ 陈旧 {gap} 天", ts, required,
                         f"基准日 {today}，产物停留在 {d}"))

    # 控制台输出
    print(f"{'产物':16s} {'状态':14s} {'时间戳':22s} {'权重':6s} 路径")
    print("-" * 72)
    for name, rel, status, ts, required, note in rows:
        print(f"{name:16s} {status:14s} {str(ts)[:22]:22s} {'必需' if required else '可选':6s} {rel}")
        if note:
            print(f"{'':16s} ↳ {note}")

    bad_required = [r for r in rows if r[4] and r[2].startswith("❌")]
    bad_ts = [r for r in rows if r[4] and r[2].startswith("⚠️")]
    ok_count = len([r for r in rows if r[2].startswith("✅")])

    print("-" * 72)
    print(f"✅ 新鲜 {ok_count} / ❌ 必需项失败 {len(bad_required)} / ⚠️ 时间戳盲区 {len(bad_ts)} / 共 {len(rows)}")

    # GitHub Actions Step Summary（在 Actions 页面直接可见，不用翻日志）
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(f"## 🛡 盘后算法链产物完整性闸门（基准 {today}）\n\n")
                f.write("| 产物 | 状态 | 时间戳 | 权重 | 说明 |\n|---|---|---|---|---|\n")
                for name, rel, status, ts, required, note in rows:
                    f.write(f"| {name} | {status} | {ts} | {'必需' if required else '可选'} | {note or '-'} |\n")
                f.write(f"\n**新鲜 {ok_count} / 必需项失败 {len(bad_required)} / 时间戳盲区 {len(bad_ts)}**\n")
        except Exception as e:
            print(f"  ⚠️ 写 Step Summary 失败: {e}")

    # 落盘报告，供前端运维面板 / 后续排查消费
    try:
        report = {
            "update_time": datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S"),
            "base_trade_date": today,
            "ok": ok_count,
            "failed_required": len(bad_required),
            "ts_blind": len(bad_ts),
            "items": [
                {"name": n, "path": p, "status": s, "ts": t, "required": r, "note": nt}
                for n, p, s, t, r, nt in rows
            ],
        }
        rp = os.path.join(ROOT, "raw_data", "algo_chain_report.json")
        os.makedirs(os.path.dirname(rp), exist_ok=True)
        with open(rp, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"  📄 报告已写入 raw_data/algo_chain_report.json")
    except Exception as e:
        print(f"  ⚠️ 写报告失败: {e}")

    if bad_required:
        print("\n🛑 闸门未通过——以下核心产物本交易日未产出：")
        for name, rel, status, ts, _, note in bad_required:
            print(f"   • {name}（{rel}）{status} | {note}")
        print("   → job 显式失败，交由告警链路处理；请勿绕过本闸门。")
        if args.warn_only:
            print("   ⚠️ warn-only 模式：不返回非零退出码")
            return 0
        return 1

    print("\n✅ 闸门通过：全部核心产物均为本交易日产出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
