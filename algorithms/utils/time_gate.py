#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""算法调度时间守卫 — 防"数据未就绪就跑算法"错配

🛡 2026-08-19 阿狸咪根治（主人令）：
小九 16:18 在单位机本地手动跑了 final_recommend，但港股 16:00 收市后还要 16:10-16:30
数据完整同步，结果 17 张盘后/选股卡数据不准。主人令「所有算法链全部安排在数据全部
就绪后跑」。本模块给关键算法入口加硬守门：早于数据就绪时间直接 sys.exit(1)。

各市场数据就绪时间（CST）：
    A股: 15:30 后（集合竞价 15:00-15:30 完成；数据源 15:30-16:00 陆续同步）
    港股: 16:30 后（16:00 收市 + 16:10 收盘竞价 + 16:30 数据完整；eastmoney push2 16:30 才全量）
    LHB: 17:30 后（17:00 发布 + 30 分钟缓冲，部分券源 17:30 才齐）
    美股: 06:00 后（22:30-05:00 盘前数据 + 06:00 后数据完整）

用法：
    # 算法入口加：
    from utils.time_gate import check, markets_required
    check(markets_required(['hk', 'lhb']))  # 港股 + LHB 都就绪才跑

    # workflow_dispatch 手动触发可加 bypass：
    if not os.environ.get('TIME_GATE_BYPASS'):
        check(markets_required(['hk']))
"""
import os
import sys
import datetime
import logging


# 2026-08-20 根因修复：Ubuntu/GitHub Actions 默认 UTC，朴素 datetime.now() 会把
# 18:30 CST 当成 10:30 UTC → 选股策略门控永远通不过（盘中被跳过、盘后也不跑）。
# 以下函数显式按 UTC+8 计算中国标准时间，不依赖系统时区或 TZ 环境变量。
_CST_OFFSET = datetime.timedelta(hours=8)

# 各市场数据就绪时间（CST, 24h 格式）
MARKET_READY = {
    'a': (15, 30),   # A股 15:30
    'hk': (16, 30),  # 港股 16:30
    'lhb': (17, 30), # 龙虎榜 17:30
    'us': (6, 0),    # 美股盘前 06:00
}

# 依赖哪个市场的中文说明
MARKET_LABEL = {
    'a': 'A股',
    'hk': '港股',
    'lhb': '龙虎榜',
    'us': '美股',
}


def _now_cst():
    return datetime.datetime.now(datetime.timezone.utc) + _CST_OFFSET


def markets_required(markets):
    """返回 markets 列表"""
    return list(markets)


# 🔴 2026-08-20 主人令·一劳永逸：所有选股策略统一守门
STOCK_PICKING_READY = (18, 0)  # CST 18:00


def check_stock_picking_ready(by='unknown'):
    """盘后选股策略统一门控：必须 ≥ 18:00 CST。

    所有选股策略（CRDS / TOP10 / 三重共识 / 四量 / 最终推荐等）必须在
    A股收盘、港股收盘、龙虎榜、北向、板块资金等全部盘后数据稳定就绪后才跑。
    早于 18:00 直接 sys.exit(1)。
    """
    if os.environ.get('TIME_GATE_BYPASS') == '1':
        logging.warning(f'[time_gate] BYPASS 已设置，跳过选股策略守门')
        return
    now = _now_cst()
    wd = now.weekday()
    if wd >= 5:
        # 周末不交易，选股策略无意义；这里不拦截，让上游决定是否跑
        logging.info('[time_gate] 周末，跳过选股策略守门')
        return
    hh, mm = STOCK_PICKING_READY
    ready = now.hour * 60 + now.minute >= hh * 60 + mm
    if not ready:
        print(f'\n🚫 [time_gate] 盘后选股策略禁止执行（需 ≥ {hh:02d}:{mm:02d} CST，当前 {now:%H:%M}）', file=sys.stderr)
        print(f'   触发方: {by}', file=sys.stderr)
        print(f'   原因: 所有盘后数据（龙虎榜/北向/板块资金/个股行情等）18:00 后才稳定就绪', file=sys.stderr)
        print(f'   绕开（应急）: TIME_GATE_BYPASS=1 环境变量', file=sys.stderr)
        sys.exit(1)
    logging.info(f'[time_gate] 选股策略守门通过（{now:%H:%M}）')


def check_cloud_only(script_name='unknown'):
    """云端/CI 算法链专属护栏（主人 2026-08-20 一劳永逸令）。

    根因：阿狸咪曾在本地手动跑 gen_lhb_7d 等算法产数据并推仓，
    与云端算法链产物分叉，造成「本地 file:/// 版 ≠ 主站」的数据不一致。
    铁律：算法（含数据生产脚本）一律由云端算法链定时任务（v8_algo_cloud 19:15 /
    v8_cn_fetch_cloud / build_deploy 等）执行，本地只改代码+推仓+镜像拉取。

    判定：GITHUB_ACTIONS=true（GitHub Actions，含云端与自托管 runner）或
    CI=true（通用 CI 标记）放行；本地手动执行默认拦截并退出，
    仅显式 ALLOW_LOCAL_ALGO=1（应急调试）可放行。
    """
    if os.environ.get('GITHUB_ACTIONS', '').lower() == 'true':
        return True
    if os.environ.get('CI', '').lower() == 'true':
        return True
    if os.environ.get('ALLOW_LOCAL_ALGO', '0') == '1':
        logging.warning(f'[time_gate] ALLOW_LOCAL_ALGO=1 显式放行本地执行（{script_name}）')
        return True
    print(f'\n🚫 [time_gate] {script_name} 仅允许云端算法链定时任务执行', file=sys.stderr)
    print(f'   铁律（主人 2026-08-20）：算法一律由云端定时任务跑，本地禁止手动跑算法产数据', file=sys.stderr)
    print(f'   否则会造成本地 file:/// 版与主站分叉。如需本地调试请设 ALLOW_LOCAL_ALGO=1', file=sys.stderr)
    return False


def check(markets, by='unknown'):
    """检查所有 markets 是否都过了数据就绪时间
    markets: list of 'a'/'hk'/'lhb'/'us'
    by: 触发方（用于日志）
    早于就绪时间：sys.exit(1) + 红字报错
    """
    if os.environ.get('TIME_GATE_BYPASS') == '1':
        logging.warning(f'[time_gate] BYPASS 已设置，跳过时间守门（{markets}）')
        return
    now = _now_cst()
    wd = now.weekday()  # 0=Mon..6=Sun
    # 周末不交易：仅 a/hk/lhb 周末无数据，但 us 周末有
    if wd >= 5 and 'us' not in markets:
        # A股/港股/LHB 周末无数据：跳过（不是时间门问题）
        logging.info(f'[time_gate] 周末，跳过 {markets} 守门')
        return
    for m in markets:
        if m not in MARKET_READY:
            logging.warning(f'[time_gate] 未知市场 {m}，跳过')
            continue
        hh, mm = MARKET_READY[m]
        ready = now.hour * 60 + now.minute >= hh * 60 + mm
        if not ready:
            print(f'\n🚫 [time_gate] {MARKET_LABEL[m]} 数据未就绪（需 ≥ {hh:02d}:{mm:02d} CST，当前 {now:%H:%M}）', file=sys.stderr)
            print(f'   触发方: {by}', file=sys.stderr)
            print(f'   等待 markets: {", ".join(MARKET_LABEL[x] for x in markets)}', file=sys.stderr)
            print(f'   绕开（应急）: TIME_GATE_BYPASS=1 环境变量', file=sys.stderr)
            sys.exit(1)
    logging.info(f'[time_gate] 守门通过：{markets}（{now:%H:%M}）')


if __name__ == '__main__':
    # 单元测试：模拟时间
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--markets', default='hk,lhb', help='依赖市场（逗号分隔）')
    args = ap.parse_args()
    mks = args.markets.split(',')
    check(mks, by='cli-test')
    print(f'✅ {mks} 都已就绪（{_now_cst():%H:%M}）')