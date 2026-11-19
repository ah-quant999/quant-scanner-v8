#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8_morning_plan_fallback.py — 盘前计划兜底（2026-11-19 主人令「一劳永逸」）

背景：v8_morning_plan.yml 的 cron（北京 07:50 工作日）长期受 GitHub schedule
高负载漏触发影响（2026-11-19 实测当日整段未触发，昨日触发也迟了约 5 小时）。
本探针由数据看门狗（v8_cn_fetch_watchdog.yml，每 15 分）附带调用：

  * 仅交易日 07:45-09:35 CST 执行（其余时段直接退出，零开销）；
  * 线上 MORNING_PLAN.js 的 data_date == 今日 → 已在位，退出；
  * 陈旧/缺失/拉取失败 → gh workflow run 补发 v8_morning_plan（ref=main）。

幂等安全：补发后下一轮 15 分窗口内计划已生成即不再重复派发；
本脚本只做「只读探针 + 派发」，不写任何数据文件。
"""
import datetime
import json
import os
import re
import urllib.request

REPO = 'ah-quant999/quant-scanner-v8'

now = datetime.datetime.utcnow() + datetime.timedelta(hours=8)  # CST
if now.weekday() >= 5:
    raise SystemExit(0)  # 周末
if not (datetime.time(7, 45) <= now.time() <= datetime.time(9, 35)):
    raise SystemExit(0)  # 非盘前窗口
today = now.strftime('%Y-%m-%d')
tok = os.environ.get('GH_TOKEN', '')
hdr = {'Authorization': 'token ' + tok, 'Accept': 'application/vnd.github.raw'}

try:
    req = urllib.request.Request(
        f'https://api.github.com/repos/{REPO}/contents/data/MORNING_PLAN.js', headers=hdr)
    t = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='replace')
except Exception as e:
    print('[morning_fallback] 拉取失败，视为缺失:', str(e)[:80])
    t = ''

m = re.search(r'"data_date"\s*:\s*"(\d{4}-\d{2}-\d{2})"', t)
if m and m.group(1) == today:
    print('[morning_fallback] 今日盘前计划已在位:', m.group(1), '→ 无需补发')
    raise SystemExit(0)

print('[morning_fallback] MORNING_PLAN 陈旧/缺失(',
      m.group(1) if m else '无 data_date', ') today=', today, '→ 补发 v8_morning_plan')
req = urllib.request.Request(
    f'https://api.github.com/repos/{REPO}/actions/workflows/v8_morning_plan.yml/dispatches',
    method='POST',
    headers={'Authorization': 'token ' + tok, 'Accept': 'application/vnd.github+json',
             'Content-Type': 'application/json'},
    data=json.dumps({'ref': 'main'}).encode())
try:
    urllib.request.urlopen(req, timeout=20)
    print('[morning_fallback] ✅ 已补发 (ref=main)')
except Exception as e:
    print('[morning_fallback] ❌ 补发失败:', str(e)[:160])
    raise SystemExit(1)
