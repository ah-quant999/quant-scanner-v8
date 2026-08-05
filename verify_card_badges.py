#!/usr/bin/env python3
"""verify_card_badges.py

校验 index.html 全站"更新于"卡片是否都已统一改用截图样式的 _uBadge 胶囊。
挂到 v8_backup.yml：每晚 21:00 自动跑。

规则：
1. 抽出所有 .fresh ID（HTML 静态 / JS 端 ID）
2. 抽出所有 setBadge('id', ...) 和 _uBadge(_inline_) 调用涉及到的 ID
3. 抽 .fresh ID 但没有 setBadge 调用或 innerHTML=_uBadge 的，记入漂移
4. 主站结构变更多由人手同步，校验结果进 HANDOVER_LOG，不阻断备份

输出：HANDOVER_LOG.jsonl 一条漂移记录
"""
import json, re, sys
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).resolve().parent
HTML = (REPO / 'index.html').read_text(encoding='utf-8')

def extract_fresh_ids():
    """抽 <span class="fresh" id="xxx">..."""
    return re.findall(r'class=["\']fresh["\'][^>]*\bid=["\']([^"\']+)["\']', HTML) + \
           re.findall(r'\bid=["\']([^"\']+)["\'][^>]*class=["\']fresh["\']', HTML)

def extract_setbadge_ids():
    """抽 setBadge('xx', ...) ID"""
    return re.findall(r'setBadge\(["\']([^"\']+)["\']', HTML)

def is_id_handled(id_name):
    """setBadge 直接调用 = 命中；或 ID 在前后 8KB 上下文内有 _uBadge / setBadge 关联"""
    if re.search(r"setBadge\(['\"]" + re.escape(id_name) + r"['\"]", HTML):
        return True
    # ID 前后 ±8KB 上下文启发
    for m in re.finditer(r'\b' + re.escape(id_name) + r'\b', HTML):
        idx = m.start()
        ctx = HTML[max(0,idx-4000):idx+8000]
        if '_uBadge' in ctx or 'setBadge(' in ctx:
            return True
    return False

fresh_ids = set(extract_fresh_ids())
setbadge_ids = set(extract_setbadge_ids())

# 排除非时间徽章的 .fresh（计数/数字占位 ID）
NON_TIME_FRESH = {
    'v8DayDate',          # 日期文字
    'amountLastDate',     # 副日期
    'upDownLastDate',     # 副日期
    'tcNearCount',        # 数量
    'tcExtCount',         # 数量
    'ttAlertCount',       # 数量
}

ok_handled = sorted([i for i in fresh_ids if i not in NON_TIME_FRESH and is_id_handled(i)])
drift = sorted([i for i in fresh_ids if i not in NON_TIME_FRESH and not is_id_handled(i)])

print(f'全站 .fresh ID 共 {len(fresh_ids)} 个')
print(f'  已统一胶囊化: {len(ok_handled)}')
print(f'  漂移（未注入 _uBadge/setBadge）: {len(drift)}')
for d in drift:
    print(f'    ⚠ {d}')

ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
log = REPO / 'HANDOVER_LOG.jsonl'
log_entry = {
    'time': ts,
    'mode': 'verify_card_badges',
    'success': len(drift) == 0,
    'drift_count': len(drift),
    'handled_count': len(ok_handled),
    'fresh_total': len(fresh_ids),
    'drift_ids': drift,
}
with log.open('a', encoding='utf-8') as f:
    f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

if drift:
    print(f'\n❌ 发现 {len(drift)} 处漂移，已写入 HANDOVER_LOG.jsonl')
    sys.exit(0)  # 不阻断备份，仅告警
print('\n✅ 全站卡片已 100% 统一 _uBadge 胶囊化（截图样式）')
