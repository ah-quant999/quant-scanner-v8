#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 数据层拆分脚本：将 index.html 中内联的 window.* 大数据块提取到 data/*.js，
并生成轻量 HTML 模板。保留前端算法，数据可独立更新、独立部署。
"""
import json, re, os, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(ROOT, 'index.html')
BACKUP_PATH = os.path.join(ROOT, 'index.html.inline.bak')
DATA_DIR = os.path.join(ROOT, 'data')

# 轻量裁剪策略：只保留累计/计算数值，去掉历史明细
def make_lite(name, obj):
    if name == 'BACKTEST_TDX':
        # 只保留全局汇总统计
        return {
            'calc_time': obj.get('calc_time'),
            'method': obj.get('method'),
            'gold_pool_size': obj.get('gold_pool_size'),
            'stocks_analyzed': obj.get('stocks_analyzed'),
            'summary': obj.get('summary', {}),
            '_lite_note': '个股历史信号明细已裁剪，仅保留汇总统计',
        }
    if name == 'BACKTEST_COMPREHENSIVE':
        # 去掉 details 明细，保留 overview/comparison
        lite = {k: v for k, v in obj.items() if k != 'details'}
        lite['_lite_note'] = 'details 回测明细已裁剪，仅保留 overview/comparison'
        return lite
    # 2026-09-04 主人令收尾：COCKPIT_BACKTEST 裁剪分支已删（驾驶舱模块下线）
    if name == 'GOLD_POOL':
        # 保留 stocks 的 latest 聚合字段，去掉每日 history 明细
        lite = {k: v for k, v in obj.items() if k != 'stocks'}
        stocks_lite = {}
        for sid, s in obj.get('stocks', {}).items():
            stocks_lite[sid] = {
                'code': s.get('code'),
                'name': s.get('name'),
                'market': s.get('market'),
                'board_label': s.get('board_label'),
                'fund_type': s.get('fund_type'),
                'first_date': s.get('first_date'),
                'first_signal': s.get('first_signal'),
                'max_signal': s.get('max_signal'),
                'signal_count': s.get('signal_count'),
                'sources': s.get('sources'),
                'latest': s.get('latest'),
                'industry': s.get('industry'),
                'sectors': s.get('sectors'),
                'concepts': s.get('concepts'),
                'board': s.get('board'),
            }
        lite['stocks'] = stocks_lite
        lite['_lite_note'] = 'stocks 已去掉 history 日明细，仅保留 latest 聚合'
        return lite
    if name == 'W52_HIGH':
        # 52周新高：保留 top_gainers 与统计，去掉 146 只完整 stocks 列表
        lite = {k: v for k, v in obj.items() if k != 'stocks'}
        lite['_lite_note'] = 'stocks 完整列表已裁剪，仅保留 top_gainers 与 total'
        return lite
    return obj


def main():
    if not os.path.exists(HTML_PATH):
        raise FileNotFoundError(HTML_PATH)

    # 备份原文件
    shutil.copy2(HTML_PATH, BACKUP_PATH)
    print(f'已备份原文件: {BACKUP_PATH}')

    os.makedirs(DATA_DIR, exist_ok=True)

    with open(HTML_PATH, encoding='utf-8') as f:
        html = f.read()

    # 匹配 <script>window.NAME = ...;</script> 单行/多行块
    # 注意：块可能跨多行，值内部不含 </script>；变量名可含数字(V8_CAL/W52_HIGH)
    pattern = re.compile(r'<script>window\.([A-Z_][A-Z0-9_]*)\s*=\s*(.*?);\s*</script>', re.S)
    matches = list(pattern.finditer(html))
    print(f'发现 {len(matches)} 个内联数据块')

    # 按位置排序，替换整块区域为 script src 引用
    replacements = []
    for m in matches:
        name = m.group(1)
        raw_value = m.group(2).strip()

        # 尝试解析 JSON
        try:
            obj = json.loads(raw_value)
        except json.JSONDecodeError as e:
            print(f'⚠️ {name} 不是合法 JSON ({e})，按原样保存')
            obj = None

        if obj is not None:
            lite_obj = make_lite(name, obj)
            json_bytes = json.dumps(lite_obj, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        else:
            # 非 JSON（如变量引用 d）按原样写入 .js
            json_bytes = ('window.' + name + ' = ' + raw_value + ';').encode('utf-8')

        js_path = os.path.join(DATA_DIR, f'{name}.js')
        with open(js_path, 'wb') as f:
            if obj is not None:
                f.write(f'window.{name} = '.encode('utf-8'))
                f.write(json_bytes)
                f.write(b';\n')
            else:
                f.write(json_bytes)
                f.write(b'\n')
        print(f'  → data/{name}.js ({len(json_bytes)} bytes)')

        replacements.append((m.start(), m.end(), name))

    # 生成新的 HTML：从后往前替换，避免位置偏移
    new_html = html
    for start, end, name in reversed(replacements):
        new_html = new_html[:start] + f'<script src="./data/{name}.js"></script>' + new_html[end:]

    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(new_html)

    # 统计
    orig_size = os.path.getsize(BACKUP_PATH)
    new_size = os.path.getsize(HTML_PATH)
    data_size = sum(os.path.getsize(os.path.join(DATA_DIR, p)) for p in os.listdir(DATA_DIR))
    print('\n拆分完成:')
    print(f'  原 index.html: {orig_size:,} bytes')
    print(f'  新 index.html: {new_size:,} bytes (减小 {orig_size-new_size:,} bytes, {100*(orig_size-new_size)/orig_size:.1f}%)')
    print(f'  data/ 总大小: {data_size:,} bytes ({len(os.listdir(DATA_DIR))} 个文件)')


if __name__ == '__main__':
    main()
