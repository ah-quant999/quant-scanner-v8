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
#
# 🔴 2026-09-14 小九（三件套·遗留②「去重」）：
#   本函数与 `update_v8.py::_make_lite` 曾是**两份独立实现**，且已**漂移两次**
#   （09-11 漏透传 `update_time`、09-14 漏透传 `entry_caliber_ver`），而本文件
#   原有注释自己就写着「两处是重复实现，改一处漏一处 = 漂移」。
#   实测两份分支覆盖也已不一致：本处只有 4 个分支（TDX/COMPREHENSIVE/GOLD_POOL/
#   W52_HIGH），另一侧有 8 个（另含 ANALYST_RATINGS/SUSPENSION_ALERT/IPO_DATA/
#   SECTOR_PHASE_HISTORY）—— 缺的 4 个在本处静默走 `return obj`，与本工具
#   「拆分时应裁剪」的预期不符。
#
#   现改为**单向委托**：`update_v8.py::_make_lite` 是唯一真源，本处只做转发。
#   · 惰性 import（写在函数体内）—— 避免两脚本互相 import 的顶层副作用与循环风险；
#   · `update_v8.py` 有 `if __name__ == '__main__'` 守卫（L1400），import 不触发主流程；
#   · 委托后本工具自动获得全部 8 个分支，与线上构建行为彻底一致。
def make_lite(name, obj):
    """转发到唯一真源 `update_v8.py::_make_lite`（理由见上方注释）。"""
    import update_v8
    return update_v8._make_lite(name, obj)


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
