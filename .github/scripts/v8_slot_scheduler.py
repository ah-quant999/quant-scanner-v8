#!/usr/bin/env python3
# v8_slot_scheduler.py — 云端档期兜底调度器（事件驱动，只补缺口，不盲轮询，防风暴）
#
# 背景：GitHub Actions schedule cron 存在静默丢触发问题，盘中/盘后档期会漏。
# 本脚本每 20 分钟被唤起一次，只检查「应当触发的档期是否真的被成功覆盖」：
#   - 未覆盖且当前无在跑 run → 派一发对应 category 的云端抓取
#   - 已覆盖/有在跑/最近已派发过 → 跳过
#  thus 平均每天派发量 ≈ 档位数（~25 次），不会比现在多，只在 cron 漏时补。
#
# 调用：python .github/scripts/v8_slot_scheduler.py
# 环境：GITHUB_TOKEN（需 actions:write 以 dispatch workflow）
import os, sys, json, urllib.request, urllib.error, datetime

try:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

API = 'https://api.github.com'
REPO = os.environ.get('GITHUB_REPO', 'ah-quant999/quant-scanner-v8')
TOKEN = os.environ.get('GITHUB_TOKEN') or os.environ.get('V8_GITHUB_TOKEN')
CST = datetime.timezone(datetime.timedelta(hours=8))

# 2026 A股交易日历（与 cloud_dispatcher.py / v8_health_check.py 一致）
_HOLIDAYS_2026 = {
    '01-01', '01-02', '01-03',
    '02-15', '02-16', '02-17', '02-18', '02-19', '02-20', '02-21', '02-22', '02-23',
    '04-04', '04-05', '04-06',
    '05-01', '05-02', '05-03', '05-04', '05-05',
    '06-19', '06-20', '06-21',
    '09-25', '09-26', '09-27',
    '10-01', '10-02', '10-03', '10-04', '10-05', '10-06', '10-07',
}
_MAKEUP_DAYS_2026 = {
    '2026-01-04', '2026-02-14', '2026-02-28',
    '2026-05-09', '2026-09-20', '2026-10-10',
}

FETCH_WF = 'v8_cn_fetch_cloud.yml'
ALGO_WF = 'v8_algo_cloud.yml'


def _is_trading_day(dt):
    d = dt.date()
    if d.weekday() >= 5 and d.isoformat() not in _MAKEUP_DAYS_2026:
        return False
    return d.strftime('%m-%d') not in _HOLIDAYS_2026


def _api(method, path, data=None):
    url = API + path
    headers = {
        'Authorization': f'Bearer {TOKEN}',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
    }
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f'  ⚠️ API {method} {path} -> HTTP {e.code}: {e.read().decode("utf-8","replace")[:200]}')
        return {}
    except Exception as e:
        print(f'  ⚠️ API {method} {path} -> {e}')
        return {}


def _parse_ts(s):
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(CST)


def _list_runs(wf_file, per_page=50):
    d = _api('GET', f'/repos/{REPO}/actions/workflows/{wf_file}/runs?per_page={per_page}')
    return d.get('workflow_runs', []) if isinstance(d, dict) else []


def _dispatch(wf_file, inputs=None):
    payload = {'ref': 'main'}
    if inputs:
        payload['inputs'] = inputs
    r = _api('POST', f'/repos/{REPO}/actions/workflows/{wf_file}/dispatches', payload)
    if r == {}:
        print(f'  ❌ 派发 {wf_file} 失败')
        return False
    print(f'  ✅ 已派发 {wf_file}' + (f' 输入 {inputs}' if inputs else ''))
    return True


def _slot_covered(runs, slot_time, window_after_min=35, window_before_min=5):
    """判断档期是否被某次成功的 fetch run 覆盖。"""
    start = slot_time - datetime.timedelta(minutes=window_before_min)
    end = slot_time + datetime.timedelta(minutes=window_after_min)
    for r in runs:
        if r.get('conclusion') != 'success':
            continue
        try:
            ct = _parse_ts(r['created_at'])
        except Exception:
            continue
        if start <= ct <= end:
            return True, ct
    return False, None


def _make_slots(now):
    """生成今日所有预期档期（pre-market/intraday/post-close）。
    返回 (category, slot_time, window_before_min, window_after_min)。
    窗口：盘前到 10:30，盘中 ±35 分钟，盘后到 22:00（容忍 cron 延迟）。"""
    base = datetime.datetime(now.year, now.month, now.day, tzinfo=CST)
    slots = []
    # 盘前
    slots.append(('premarket', base.replace(hour=8, minute=25), 5, 125))
    # 盘中：09:00-11:30 / 13:00-15:30 每 30 分
    for h, m in [
        (9, 0), (9, 30), (10, 0), (10, 30), (11, 0), (11, 30),
        (13, 0), (13, 30), (14, 0), (14, 30), (15, 0), (15, 30),
    ]:
        slots.append(('intraday', base.replace(hour=h, minute=m), 5, 35))
    # 盘后：容忍延迟到 22:00
    slots.append(('post_close', base.replace(hour=17, minute=20), 5, 280))
    return slots


def _guard_allow(runs, now, cooldown_min=15, max_fail_today=3, wf_name=''):
    """通用防风暴守卫：有在跑/排队 → 跳过；最近派发太近 → 跳过；同版本失败太多 → 熔断。"""
    live = [r for r in runs if r.get('status') in ('queued', 'pending', 'waiting', 'requested', 'in_progress')]
    if live:
        return False, f'已有 {len(live)} 个 {wf_name} run 在跑/排队，跳过'
    if runs:
        try:
            last_ct = _parse_ts(runs[0]['created_at'])
            ago = (now - last_ct).total_seconds() / 60.0
            if ago < cooldown_min:
                return False, f'最近 {wf_name} run 于 {last_ct.strftime("%H:%M")}（{ago:.0f} 分钟前），{cooldown_min} 分钟冷却内跳过'
        except Exception:
            pass
    # 失败熔断：同 main HEAD 今日失败 >= max_fail_today 不补派（防同一 bug 反复风暴）
    ref = _api('GET', f'/repos/{REPO}/git/refs/heads/main')
    head = (ref.get('object') or {}).get('sha') if isinstance(ref, dict) else None
    fails_same = 0
    last_fail_ago = 9999.0
    for r in runs:
        if r.get('conclusion') != 'failure':
            continue
        try:
            rt = _parse_ts(r['created_at'])
        except Exception:
            continue
        if rt.date() != now.date():
            continue
        if head and r.get('head_sha') == head:
            fails_same += 1
            last_fail_ago = min(last_fail_ago, (now - rt).total_seconds() / 60.0)
    if head and fails_same >= max_fail_today:
        if last_fail_ago >= 60:
            return True, f'同版本 {head[:7]} 已失败 {fails_same} 次，但距最近失败 {last_fail_ago:.0f} 分钟，放探针一次'
        return False, f'同版本 {head[:7]} 今日已失败 {fails_same} 次，熔断'
    return True, '守卫通过'


def _dispatch_fetch_slot(cat, now, fetch_runs):
    allow, why = _guard_allow(fetch_runs, now, cooldown_min=15, max_fail_today=3, wf_name=FETCH_WF)
    if not allow:
        print(f'  ⏭️ {cat} 缺口：{why}')
        return False
    inputs = {'category': cat}
    return _dispatch(FETCH_WF, inputs)


def _handle_algo(now, algo_runs, fetch_runs):
    """盘后算法链调度：>=18:00、交易日、且今日尚未成功跑过，则补派一次。"""
    if now.hour < 18:
        print(f'  ⏭️ 算法链：当前 {now.hour}:xx 未到 18:00，跳过')
        return
    if not _is_trading_day(now):
        print(f'  ⏭️ 算法链：非交易日，跳过')
        return
    today_success = False
    for r in algo_runs:
        if r.get('conclusion') != 'success':
            continue
        try:
            ct = _parse_ts(r['created_at'])
        except Exception:
            continue
        # 18:00 前创建的 algo run 会跳过候选池/三重共识/最终推荐等主模块，
        # 只有 18:00 后（含 19:15 主档/20:00 兜底）的成功才算真正完成盘后选股。
        if ct.date() == now.date() and ct.hour >= 18:
            today_success = True
            print(f'  ✅ 算法链：今日 18:00 后已成功于 {ct.strftime("%H:%M")}，无需补派')
            break
    if today_success:
        return
    # 额外：确认 post_close 数据已经抓取（今天有成功的 fetch run 在 17:15 后）
    post_close_ready = False
    for r in fetch_runs:
        if r.get('conclusion') != 'success':
            continue
        try:
            ct = _parse_ts(r['created_at'])
        except Exception:
            continue
        if ct.date() == now.date() and ct.hour >= 17 and ct.minute >= 15:
            post_close_ready = True
            break
    if not post_close_ready:
        print('  ⏭️ 算法链：post_close 数据尚未就绪（17:15 后无成功 fetch），暂不派发')
        return
    allow, why = _guard_allow(algo_runs, now, cooldown_min=45, max_fail_today=3, wf_name=ALGO_WF)
    if not allow:
        print(f'  ⏭️ 算法链：{why}')
        return
    _dispatch(ALGO_WF)


def main():
    now = datetime.datetime.now(CST)
    print(f'🛰️ v8 slot scheduler @ {now.strftime("%Y-%m-%d %H:%M CST")}')

    if not TOKEN:
        print('❌ 缺少 GITHUB_TOKEN，跳过'); sys.exit(0)
    if not _is_trading_day(now):
        print(f'✅ 非交易日（{now.strftime("%Y-%m-%d")}），跳过'); return

    fetch_runs = _list_runs(FETCH_WF, per_page=50)
    algo_runs = _list_runs(ALGO_WF, per_page=20)

    # 1) 处理每个预期档期
    slots = _make_slots(now)
    dispatched = 0
    for cat, slot_time, win_before, win_after in slots:
        if now < slot_time:
            print(f'  ⏳ {cat} {slot_time.strftime("%H:%M")} 尚未到点，跳过')
            continue
        # 档期内是否已被覆盖？
        covered, cov_ct = _slot_covered(fetch_runs, slot_time, window_after_min=win_after, window_before_min=win_before)
        if covered:
            print(f'  ✅ {cat} {slot_time.strftime("%H:%M")} 已被覆盖（{cov_ct.strftime("%H:%M")}）')
            continue
        # 太久远的盘中档不再补（市场已变化），但 post_close 永远补
        age_min = (now - slot_time).total_seconds() / 60.0
        if cat == 'intraday' and age_min > 90:
            print(f'  ⏭️ {cat} {slot_time.strftime("%H:%M")} 已过去 {age_min:.0f} 分钟，放弃补派')
            continue
        if cat == 'premarket' and age_min > 120:
            print(f'  ⏭️ {cat} {slot_time.strftime("%H:%M")} 已过去 {age_min:.0f} 分钟，放弃补派')
            continue
        print(f'  🚨 {cat} {slot_time.strftime("%H:%M")} 缺失（过去 {age_min:.0f} 分钟）')
        if _dispatch_fetch_slot(cat, now, fetch_runs):
            dispatched += 1

    # 2) 盘后算法链兜底
    _handle_algo(now, algo_runs, fetch_runs)

    print(f'🛰️ 调度完成，本次补派 {dispatched} 档')


if __name__ == '__main__':
    main()
