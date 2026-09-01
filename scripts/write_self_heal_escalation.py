#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""write_self_heal_escalation.py — health_patrol 自愈闭环失败升级标记

🛡 2026-08-19 阿狸咪根治抽离：
原 .github/workflows/v8_health_patrol.yml 在「自愈验证 10 分钟后回查」step 里写了多行
python -c（import + try/except + 多语句 + 多行单引号字符串），YAML 解析器把字符串内的换行
当成普通字符，Python 看到多行字符串需要三引号包裹 → SyntaxError → 整个 workflow 文件无效 →
每次 push 到 main 都产生 1 个 event=push failure run（无 job 无日志），云端巡检/自愈
(workflow_run + schedule) 从 8/18 09:05 死到 8/19 22:00 共 37h。修法：把 Python 抽到本独立脚本，
workflow 里单行 REMAIN_FAIL="$REMAIN_FAIL" python scripts/write_self_heal_escalation.py 调用。

环境变量：
    REMAIN_FAIL  - int, 自愈 10 分钟后仍 fail 的卡片数（由 workflow step 传）

输出文件：
    .workbuddy/self_heal_escalations.json  - 追加新条目，保留最近 30 条
"""
import json
import os
import datetime
import sys

P = '.workbuddy/self_heal_escalations.json'


def main():
    ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    remaining = int(os.environ.get('REMAIN_FAIL', 0))
    entry = {
        'ts': ts,
        'remaining_fail': remaining,
        'detail': '自愈闭环未达成',
    }
    try:
        try:
            d = json.load(open(P, encoding='utf-8'))
            if not isinstance(d, list):
                d = []
        except Exception:
            d = []
        d.append(entry)
        os.makedirs(os.path.dirname(P), exist_ok=True)
        with open(P, 'w', encoding='utf-8') as f:
            f.write(json.dumps(d[-30:], ensure_ascii=False, indent=1))
        print(f"✅ 已写入 {P}（保留 {len(d[-30:])} 条历史）")
    except Exception as e:
        print(f"⚠️ 写入失败（不影响 workflow 主流程）: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()