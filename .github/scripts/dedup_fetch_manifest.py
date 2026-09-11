#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dedup_fetch_manifest.py — 派发风暴去重（B 点，小九 2026-09-03 接手）

问题：v8_cn_fetch_cloud.yml 用 `git status --porcelain raw_data/ data/` 收集变更清单，
交给 api_push_raw.py 走 GitHub Contents API 逐个文件 PUT。每个 raw_data/*.json 含
`update_time` 时间戳，cloud_fetch 每轮 save() 重写整文件 → 时间戳必变 → git status 永远
列出它们 → 每次 fetch 几十个文件 = 几十个远端 commit → 仓库快速膨胀逼近 1GB。

修复：在收集阶段就剔除「仅时间戳/生成时间变化、数据内容没变」的伪变更文件，
使 api_push_raw.py 收不到它们 → 不为时间戳重复 commit。

保守策略（安全优先）：
- 无法确认「仅时间戳变」的文件（解析失败/新增文件/HEAD 无此文件）一律保留推送，
  宁可偶尔多 commit，绝不漏推真数据（漏推导致线上陈旧更危险）。
- 只删除白名单时间戳字段比对；JSON 走结构化剥字段，非 JSON 走正则删时间戳行。

用法：python dedup_fetch_manifest.py [paths...]
  默认 paths = raw_data/ data/
  输出（stdout）：过滤后的逗号清单，供 `MANIFEST=$(...)` 直接消费；
  跳过日志输出到 stderr，不污染 stdout。
"""
import subprocess
import sys
import os
import re
import json

# 时间戳字段白名单（lower 比较）
SKIP_KEYS = {
    'update_time', 'updatetime', 'generated_at', 'generatedat',
    'timestamp', '_ts', 'fetch_time', 'fetchtime', 'last_update', 'lastupdate',
}

# 🛡 2026-09-11 一劳永逸（主人令「9 张红灯卡」根治）：强制推送白名单。
#
#   背景：本去重器的判据是「剥掉时间戳后内容是否改变」。对**数据内容天然稳定**的
#   研究/审计类卡片，剥掉时间戳后逐字节相同 → 被判定为「伪变更」→ 永不推送 →
#   其 update_time 永远停在首次落盘那一刻。
#
#   两层后果（实测 2026-09-11）：
#     ① 前端恒显示「昨日」红灯（卡片新鲜度 = update_time，而它永不前进）；
#     ② 批次闸门 v8_stage_gate.py 的 READY_SPEC 读同一批文件判就绪 →
#        永远判 STALE → B 批每轮都被判「未就绪」而反复重跑（60~90min/轮）。
#
#   为何这 5 张卡内容稳定：
#     · factor_audit     审计的是 generate_top10.py 的**源码**，源码不改则内容不变
#     · factor_progress  读 factor_audit 结果，同理
#     · index_value_framework 依赖 INDEX_HISTORY.js 的刷新节奏（自身可能滞后数日）
#     · valuation_percentile / ai_insights_compare 多数日子数值相同
#
#   故这 5 张卡的 raw/ js **一律强制推送**（单文件 1~8KB，开销可忽略），
#   保证 update_time 每日前进 —— 这正是它们作为「今日已刷新」指示灯的设计意图
#  （原 v8_cn_fetch_experiments.yml 也是无条件 git add + push 这 3 个文件）。
_ALWAYS_PUSH = {
    "raw_data/factor_audit.json",
    "raw_data/factor_progress.json",
    "raw_data/index_value_framework.json",
    "raw_data/valuation_percentile.json",
    "raw_data/ai_insights_compare.json",
    "data/FACTOR_AUDIT.js",
    "data/FACTOR_PROGRESS.js",
    "data/INDEX_VALUE_FRAMEWORK.js",
    "data/VALUATION_PERCENTILE.js",
    "data/AI_INSIGHTS_COMPARE.js",
}


def strip_ts(text):
    """剥离时间戳字段后返回规范化字符串，用于比对内容是否真变。"""
    try:
        d = json.loads(text)
    except Exception:
        # 非 JSON（如 data/*.js 的 window.X={...}）：删明确时间戳键值
        pat = r'"(' + '|'.join(re.escape(k) for k in SKIP_KEYS) + r')"\s*:\s*(?:"[^"]*"|\d{10,13})'
        return re.sub(pat, '', text)
    if not isinstance(d, (dict, list)):
        return text

    def clean(o):
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items() if k.lower() not in SKIP_KEYS}
        if isinstance(o, list):
            return [clean(x) for x in o]
        return o

    return json.dumps(clean(d), sort_keys=True, ensure_ascii=False)


def head_text(f):
    # 🔧 2026-09-03 一劳永逸升级：比对基准优先用远端真源 origin/main（消除本地 HEAD 陈旧边界），
    #   回退 HEAD；都取不到则视为新增/未知 → 保留推送（绝不漏推真数据）。
    for ref in ('origin/main', 'HEAD'):
        try:
            return subprocess.check_output(
                ['git', 'show', ref + ':' + f], stderr=subprocess.DEVNULL
            ).decode('utf-8', 'replace')
        except Exception:
            continue
    return None


def main():
    paths = sys.argv[1:] or ['raw_data/', 'data/']
    try:
        out = subprocess.check_output(
            ['git', 'status', '--porcelain'] + paths, stderr=subprocess.DEVNULL
        ).decode('utf-8', 'replace')
    except Exception as e:
        sys.stderr.write('dedup: git status failed: %s\n' % e)
        sys.exit(1)

    files = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) >= 2:
            f = parts[-1] if '->' in line else parts[1]
            files.append(f)

    real = []
    for f in files:
        if not os.path.exists(f):
            real.append(f)  # 工作树已删，保留（让推送层处理删除）
            continue
        if f in _ALWAYS_PUSH:
            # 🛡 强制推送白名单：研究/审计类卡片，update_time 即其新鲜度指示灯，
            #   内容稳定也不得被当作「伪变更」丢弃（详见 _ALWAYS_PUSH 注释）。
            sys.stderr.write('📌 force push (always-push card): %s\n' % f)
            real.append(f)
            continue
        try:
            cur = open(f, encoding='utf-8', errors='replace').read()
        except Exception:
            real.append(f)
            continue
        h = head_text(f)
        if h is None:
            real.append(f)  # 新增文件，保留
            continue
        if strip_ts(cur) == strip_ts(h):
            sys.stderr.write('⏭️ dedup skip (timestamp-only): %s\n' % f)
        else:
            real.append(f)

    sys.stdout.write(','.join(real))


if __name__ == '__main__':
    main()
