#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v8_sector_tech_fallback.py — 板块技术研判卡断更自愈（2026-11-23 主人令「一劳永逸」）

背景（实证 2026-11-23）：
  v8_sector_tech.yml 的 cron（UTC 8:00/9:40 = 北京 16:00/17:40 工作日）自 11-20 后
  连续 3 天被 GitHub schedule 整段漏触发（workflow state=active，但 11-21/11-22/11-23
  三条 schedule 全部 0 run），卡停在 2026-11-20 15:00。与 09-01/11-19 已根治的
  「GitHub cron 不可靠」是同一类根因，单靠 workflow 内置 cron 必然复发。

本探针挂在数据看门狗（v8_cn_fetch_watchdog.yml，每 15 分稳定运行，实测从未整段哑火），
基于**状态**自愈，不依赖准点：
  * 仅交易日 15:05-23:59 CST 执行（盘后日频数据，盘前/盘中今日数据尚未定稿）；
  * 线上 data/SECTOR_TECH_JUDG.js 的 data_date == 今日 → 已在位，退出；
  * 陈旧/缺失 → gh workflow run 补派 v8_sector_tech.yml（云端 ubuntu runner 抓真数据）。
幂等安全：生成器对当日产物幂等，重复派发不会写坏数据；
节流：每小时整点档（minute<15）才派发一次，失败重试最多每小时 1 次，防 API 风暴。
本脚本只做「只读探针 + 派发」，不写任何数据文件。
"""
import datetime
import json
import os
import re
import urllib.request

REPO = 'ah-quant999/quant-scanner-v8'
WORKFLOW = 'v8_sector_tech.yml'
NOW = datetime.datetime.utcnow() + datetime.timedelta(hours=8)  # CST

# 周末不跑（板块研判为交易日盘后数据）
if NOW.weekday() >= 5:
    raise SystemExit(0)
# 仅盘后窗口检查：15:05 之后今日收盘数据才定稿
if not (datetime.time(15, 5) <= NOW.time() <= datetime.time(23, 59)):
    raise SystemExit(0)
# 每小时整点档才派发（看门狗 15 分一班，仅 minute<15 放行）——节流防 API 风暴
if NOW.minute >= 15:
    raise SystemExit(0)

today = NOW.strftime('%Y-%m-%d')
tok = os.environ.get('GH_TOKEN', '')
if not tok:
    print('[sector_tech_fallback] 无 GH_TOKEN，跳过')
    raise SystemExit(0)

hdr = {'Authorization': 'token ' + tok, 'Accept': 'application/vnd.github.raw'}
raw = ''
try:
    req = urllib.request.Request(
        f'https://api.github.com/repos/{REPO}/contents/data/SECTOR_TECH_JUDG.js', headers=hdr)
    raw = urllib.request.urlopen(req, timeout=20).read().decode('utf-8', errors='replace')
except Exception as e:
    print('[sector_tech_fallback] 拉取线上数据失败，视为缺失:', str(e)[:80])

m = re.search(r'"data_date"\s*:\s*"(\d{4}-\d{2}-\d{2})"', raw)
data_date = m.group(1) if m else None
if data_date == today:
    print('[sector_tech_fallback] 今日板块研判已在位:', data_date, '→ 无需补派')
    raise SystemExit(0)

print('[sector_tech_fallback] SECTOR_TECH_JUDG 陈旧/缺失(',
      data_date or '无 data_date', ') today=', today, '→ 补派', WORKFLOW)
req = urllib.request.Request(
    f'https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/dispatches',
    method='POST',
    headers={'Authorization': 'token ' + tok, 'Accept': 'application/vnd.github+json',
             'Content-Type': 'application/json'},
    data=json.dumps({'ref': 'main'}).encode())
try:
    urllib.request.urlopen(req, timeout=20)
    print('[sector_tech_fallback] ✅ 已补派', WORKFLOW, '(ref=main)')
except Exception as e:
    print('[sector_tech_fallback] ❌ 补派失败:', str(e)[:160])
    raise SystemExit(1)
