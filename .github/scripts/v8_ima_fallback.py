#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8_ima_fallback.py — 强势跟踪（IMA_STRONG_STOCK）断更自愈（2026-11-28 主人令「一劳永逸」）

背景（实证 2026-11-27）：
  v8_ima_strong_stock.yml 的 cron（UTC 07:45/13:00 = 北京 15:45/21:00 工作日）在
  11-27 全天**两条全部 0 run**（workflow state=active，最近一次成功是 11-26T22:13Z），
  数据停在 11-27 06:16 → 前端红卡「超过阈值 694 分钟」。
  与 09-01 / 11-19 / 11-23 已根治的「GitHub cron 不可靠」是同一类根因，
  单靠 workflow 内置 cron 必然复发（本仓已有 3 个同类 fallback 先例）。

本探针挂在数据看门狗（v8_cn_fetch_watchdog.yml，每 15 分稳定运行），基于**状态**自愈：
  * 仅交易日 16:00-23:59 CST 执行（源方「短线情绪选股」约 15:30 发稿，16:00 后判定才有意义）；
  * 线上 data/IMA_STRONG_STOCK.js 的 **update_time 日期 == 今日** → 今日解析批已跑过，退出；
  * 否则 → gh workflow run 补派 v8_ima_strong_stock.yml。

判据为什么用 update_time 而不是 data_date（关键，防误诊）：
  * update_time 每逢解析批执行就会刷新（即使源方没发新稿，脚本也按 retained-last 重算 stale）；
  * data_date 停在旧日 **有两种完全不同的原因**：
      ① workflow 没跑（本探针该管 → 补派）；
      ② workflow 跑了、但源方没发新稿 / 本机快照脏（补派无用，属另一层故障）。
    用 data_date 判会把 ② 也当成 ① 反复空派；用 update_time 判可精确区分两层，
    与前端诊断文案（按 source_stale / stale_days 归因）互为印证。

幂等安全：解析批对同一快照幂等，重复派发不会写坏数据；脚本自带 retained-last 防回归守卫。
节流：每小时整点档（minute<15）才派发一次，防 API 风暴。
本脚本只做「只读探针 + 派发」，不写任何数据文件。
"""
import datetime
import json
import os
import re
import urllib.request

REPO = 'ah-quant999/quant-scanner-v8'
WORKFLOW = 'v8_ima_strong_stock.yml'
NOW = datetime.datetime.utcnow() + datetime.timedelta(hours=8)  # CST

# 周末不跑：源方「短线情绪选股」按交易日发稿，周末无新稿
if NOW.weekday() >= 5:
    raise SystemExit(0)
# 仅盘后窗口：源方约 15:30 发稿，16:00 后判定
if not (datetime.time(16, 0) <= NOW.time() <= datetime.time(23, 59)):
    raise SystemExit(0)
# 每小时整点档才派发（看门狗 15 分一班，仅 minute<15 放行）—— 节流防 API 风暴
if NOW.minute >= 15:
    raise SystemExit(0)

today = NOW.strftime('%Y-%m-%d')
tok = os.environ.get('GH_TOKEN', '')
if not tok:
    print('[ima_fallback] 无 GH_TOKEN，跳过')
    raise SystemExit(0)

hdr = {'Authorization': 'token ' + tok, 'Accept': 'application/vnd.github.raw'}
raw = ''
try:
    req = urllib.request.Request(
        f'https://api.github.com/repos/{REPO}/contents/data/IMA_STRONG_STOCK.js', headers=hdr)
    raw = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='replace')
except Exception as e:
    print('[ima_fallback] 拉取线上数据失败，视为缺失:', str(e)[:80])

m = re.search(r'"update_time"\s*:\s*"(\d{4}-\d{2}-\d{2})', raw)
upd = m.group(1) if m else None
if upd == today:
    d = re.search(r'"data_date"\s*:\s*"(\d{4}-\d{2}-\d{2})"', raw)
    print('[ima_fallback] 今日解析批已在位:update_time=%s · data_date=%s'
          % (upd, (d.group(1) if d else '?')), '→ 无需补派')
    raise SystemExit(0)

print('[ima_fallback] IMA_STRONG_STOCK 今日未产出 (update_time=',
      upd or '无', ') today=', today, '→ 补派', WORKFLOW)
req = urllib.request.Request(
    f'https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches',
    method='POST',
    headers={'Authorization': 'token ' + tok, 'Accept': 'application/vnd.github+json',
             'Content-Type': 'application/json'},
    data=json.dumps({'ref': 'main'}).encode())
try:
    urllib.request.urlopen(req, timeout=20)
    print('[ima_fallback] ✅ 已补派', WORKFLOW, '(ref=main)')
except Exception as e:
    print('[ima_fallback] ❌ 补派失败:', str(e)[:160])
    raise SystemExit(1)
