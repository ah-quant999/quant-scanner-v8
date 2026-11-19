#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8 盘中调度器漏触发兜底探针（2026-11-19 最高优先级主人令「实时数据怎么还没更新」根治）
背景：盘中准点档调度器 v8_cn_fetch_intraday_lemoncat.yml 的 schedule 再次被 GitHub
整段漏触发（2026-11-19 实测 09:30/09:40 档 0 run，最近一班停在凌晨 00:04）⇒ 实时卡
全停在盘前/昨收，开盘即断粮。morning_plan 兜底同款思路：随看门狗 15 分班自检自愈。
逻辑（幂等，只读+有条件 dispatch）：
  交易日（周一~五）盘中窗 CST 09:25-11:35 / 12:55-15:05 内：
  · 查 lemoncat 最近 1 班（任何 event）；
  · 最近班距今 > 25 分钟（该链最大档间隔 20min + 调度余量）且无 in_progress 班
    ⇒ 判定漏触发，dispatch lemoncat（ref=main）；
  · 其余情况零动作零输出，退出。
2026-11-19 主人令降频风控：本探针只在漏触发时才 dispatch，正常班次零 API 写操作。
"""
import datetime
import json
import os
import re
import urllib.request

REPO = 'ah-quant999/quant-scanner-v8'
WF = 'v8_cn_fetch_intraday_lemoncat.yml'

now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)  # CST
if now.weekday() >= 5:
    raise SystemExit(0)  # 周末
_t = now.hour * 60 + now.minute
if not ((9 * 60 + 25) <= _t <= (11 * 60 + 35) or (12 * 60 + 55) <= _t <= (15 * 60 + 5)):
    raise SystemExit(0)  # 非盘中窗
tok = os.environ.get('GH_TOKEN', '')
hdr = {'Authorization': 'token ' + tok, 'Accept': 'application/vnd.github+json'}

try:
    req = urllib.request.Request(
        f'https://api.github.com/repos/{REPO}/actions/workflows/{WF}/runs?per_page=3',
        headers=hdr)
    runs = json.loads(urllib.request.urlopen(req, timeout=20).read()).get('workflow_runs', [])
except Exception:
    raise SystemExit(0)
if not runs:
    raise SystemExit(0)

def _cst(r):
    try:
        return datetime.datetime.strptime(
            (r.get('run_started_at') or '').replace('Z', ''), '%Y-%m-%dT%H:%M:%S')
    except Exception:
        return None

if any(r.get('status') == 'in_progress' or r.get('status') == 'queued' for r in runs):
    raise SystemExit(0)  # 已有班在跑/排队，不重复派发
latest = _cst(runs[0])
if latest is None:
    raise SystemExit(0)
age_min = (datetime.datetime.utcnow() - latest).total_seconds() / 60.0
if age_min <= 25:
    raise SystemExit(0)  # 最近班够新鲜，调度器活着

# 漏触发实锤 → 补派
try:
    req = urllib.request.Request(
        f'https://api.github.com/repos/{REPO}/actions/workflows/{WF}/dispatches',
        method='POST',
        headers={**hdr, 'Content-Type': 'application/json', 'Content-Length': '13'},
        data=json.dumps({"ref": "main"}).encode())
    urllib.request.urlopen(req, timeout=20)
    print(f"[intraday-sched-fallback] 调度器最近班距今 {age_min:.0f}min(>25) → 已补派 lemoncat")
except Exception as e:
    print(f"[intraday-sched-fallback] dispatch 失败: {e}")
    raise SystemExit(1)
