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
