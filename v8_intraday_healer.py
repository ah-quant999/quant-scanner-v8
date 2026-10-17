#!/usr/bin/env python3
"""v8 盘中云端自愈器 — 检测 cn_fetch_cloud 新鲜度，过期自动 dispatch 补跑。

背景（2026-08-06）：
- GitHub schedule cron 不保证 100% 触发（实测 15:00 档漏触发），导致盘中数据缺口。
- 本 workflow 是云端第二道保险：交易日 09:03-15:33 CST 每 30 分钟跑一次，
  发现 cn_fetch_cloud 最近成功运行过期（>45 分钟）则自动 dispatch 补跑。
- 纯云端执行（ubuntu），不依赖本机/self-hosted runner；小九关机不受影响。

用法：
  正常（GHA）：GH_TOKEN=<secrets.GITHUB_TOKEN> python v8_intraday_healer.py
  本地只读测试：python v8_intraday_healer.py --dry-run --token <PAT>
"""

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com/repos/ah-quant999/quant-scanner-v8"
CN_FETCH_WF = 327687211          # v8 中国数据抓取(云端)
CN_FETCH_WF_NAME = "v8_cn_fetch_cloud.yml"
FRESH_MIN = 45                   # 与前端/本机兜底一致的新鲜度阈值（分钟）
CST = datetime.timezone(datetime.timedelta(hours=8))


def gh_get(path, token):
    req = urllib.request.Request(API + path, headers={
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "v8-intraday-healer",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def gh_dispatch(category, token, dry_run=False):
    if dry_run:
        print(f"  (dry-run) 将 dispatch v8_cn_fetch_cloud category={category}")
        return 204
    payload = json.dumps({"ref": "main", "inputs": {"category": category}}).encode()
    req = urllib.request.Request(
        API + f"/actions/workflows/{CN_FETCH_WF_NAME}/dispatches",
        data=payload, method="POST",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "v8-intraday-healer",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只检测不 dispatch")
    ap.add_argument("--token", default=os.environ.get("GH_TOKEN", ""), help="PAT/GITHUB_TOKEN")
    ap.add_argument("--now", default=None, help="模拟当前时间 YYYY-MM-DD HH:MM (测试用)")
    args = ap.parse_args()

    if not args.token:
        print("❌ 缺少 token（GH_TOKEN 环境变量或 --token）")
        sys.exit(2)

    if args.now:
        now = datetime.datetime.strptime(args.now, "%Y-%m-%d %H:%M").replace(tzinfo=CST)
    else:
        now = datetime.datetime.now(CST)
    dow = now.isoweekday()
    hm = now.hour * 100 + now.minute
    print(f"== 盘中自愈检查 {now:%Y-%m-%d %H:%M} CST (dow={dow} hm={hm}) {'DRY-RUN' if args.dry_run else ''} ==")

    # 非工作日跳过
    if dow > 5:
        print("非工作日，跳过")
        return 0

    # 交易时段 09:30-15:35 CST（15:35 后交给 15:45 盘后档/夜间兜底）
    if not (930 <= hm <= 1535):
        print(f"非交易时段({hm})，跳过")
        return 0

    # 查 cn_fetch_cloud 最近 5 次运行
    try:
        runs = gh_get(f"/actions/workflows/{CN_FETCH_WF}/runs?per_page=5", args.token).get("workflow_runs", [])
    except Exception as e:
        print(f"❌ 查询 runs 失败: {e}")
        return 1
    if not runs:
        print("❌ 无任何运行记录，无法判断，跳过")
        return 0

    last_success = next((r for r in runs if r.get("conclusion") == "success"), None)
    if last_success is None:
        print("🔴 最近 5 次运行无 success → 视为过期，需要补跑")
        need = True
    else:
        done = datetime.datetime.strptime(last_success["updated_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc).astimezone(CST)
        age_min = (now - done).total_seconds() / 60
        print(f"最近成功: run#{last_success['id']} 完成于 {done:%H:%M} CST，距今 {age_min:.0f} 分钟（阈值 {FRESH_MIN}）")
        need = age_min > FRESH_MIN

    if not need:
        print("✅ cn_fetch 新鲜，无需补跑")
        return 0

    # 过期 → 按当前时段选 category 补跑
    cat = "post_close" if 1530 <= hm <= 1540 else "intraday"
    print(f"🔴 cn_fetch 过期 → dispatch category={cat}")
    code = gh_dispatch(cat, args.token, dry_run=args.dry_run)
    ok = code in (204, 201)
    print(f"dispatch HTTP {code} {'✅' if ok else '❌'}")
    if ok:
        print(f"::warning::盘中自愈器检测到 cn_fetch 过期，已 dispatch {cat} 补跑")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
