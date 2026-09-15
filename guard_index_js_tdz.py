# -*- coding: utf-8 -*-
"""
guard_index_js_tdz.py —— index.html 内联 JS「先用后定义」静态守卫

【用途】
拦截一类**不会报错、只会静默失效**的前端 bug：某个辅助函数（如 _uBadge / setBadge）
被上游 IIFE 在其定义之前调用 → 抛 ReferenceError → 整段 IIFE 被浏览器静默吞掉 →
卡片渲染成 "--" 或旧值。健康检查看不到（HTTP 200、数据文件正常），
只有主人肉眼截图才能发现。2026-08-06 01639aa 就是这么被发现的（判定/宏观解读两张子卡）。

【判定规则】
- 内联 <script> 块之间**不共享 hoist**：块 N 里的 `function f(){}` 对块 M(M<N) 不可见。
  → 跨块的「先用后定义」= 真 ReferenceError（CROSS-BLOCK）
- 同块内 `const/let f = ...` 有 TDZ，执行期在定义行之前调用同样抛错（TDZ-SAMEBLOCK）
- 同块内 `function f(){}` 会 hoist → 安全，不报
- 调用行若带防御守卫（`typeof f === 'function'` / `window.f &&` / `window.f?.`）→ 视为安全，不报

【数据去向】无。纯静态扫描，只读 index.html，不写任何文件。
【依赖】仅标准库。
【退出码】0=通过；1=发现风险点（CI 可据此 fail）
【调用方】人工 / 可挂到 v8_health_check 或 build workflow（当前未挂，2026-08-06 由小九新增）
"""
import re
import sys

ID = r'[A-Za-z_$][\w$]*'
KW = {'if', 'for', 'while', 'switch', 'catch', 'return', 'function', 'typeof',
      'new', 'await', 'else', 'do', 'try', 'delete', 'void', 'in', 'of', 'yield'}


def _strip_comments(code):
    """把 JS 注释替换为空格（保持字符/行位置不变），避免注释里的函数名被误识别为调用。
    注意：为简化实现，字符串内部的 // 也会被替换，但这不会导致漏报真正的函数调用。"""
    # 1) /* ... */ 块注释：替换为等长空格，保留内部换行符以保持行号
    def repl_block(m):
        return ''.join(' ' if c != '\n' else c for c in m.group(0))
    code = re.sub(r'/\*.*?\*/', repl_block, code, flags=re.S)
    # 2) // 行注释：从 // 到行尾替换为空格
    code = re.sub(r'//[^\n]*', lambda m: ' ' * len(m.group(0)), code)
    return code


def scan(path='index.html'):
    src = open(path, encoding='utf-8').read()
    lines = src.split('\n')

    blocks = []
    for m in re.finditer(r'<script([^>]*)>(.*?)</script>', src, re.S | re.I):
        if 'src=' in m.group(1).lower():
            continue
        blocks.append((m.start(2), m.group(2)))

    def line_of(off):
        return src.count('\n', 0, off) + 1

    defs = {}
    for bi, (boff, code) in enumerate(blocks):
        for m in re.finditer(r'\b(?:const|let|var)\s+(' + ID + r')\s*=\s*(?:async\s*)?'
                             r'(?:function\b|\([^)]*\)\s*=>|' + ID + r'\s*=>)', code):
            n, o = m.group(1), boff + m.start(1)
            if n not in defs or o < defs[n][0]:
                defs[n] = (o, bi, 'TDZ')
        for m in re.finditer(r'\bfunction\s+(' + ID + r')\s*\(', code):
            n, o = m.group(1), boff + m.start(1)
            if n not in defs or o < defs[n][0]:
                defs[n] = (o, bi, 'hoist')

    risks, guarded = [], []
    for bi, (boff, code) in enumerate(blocks):
        code_no_comments = _strip_comments(code)
        for m in re.finditer(r'(' + ID + r')\s*\(', code_no_comments):
            n = m.group(1)
            if n in KW or n not in defs:
                continue
            o = boff + m.start(1)
            doff, dbi, kind = defs[n]
            if o >= doff:
                continue
            prev = code[max(0, m.start(1) - 14):m.start(1)]
            if re.search(r'(function\s+|\.|const\s+|let\s+|var\s+)$', prev):
                continue  # 定义处本身 / 成员调用 obj.fn()
            if bi != dbi:
                risk = 'CROSS-BLOCK'
            elif kind == 'TDZ':
                risk = 'TDZ-SAMEBLOCK'
            else:
                continue  # 同块 function 声明 → hoist 安全

            ul = line_of(o)
            ltxt = lines[ul - 1]
            esc = re.escape(n)
            has_guard = bool(
                re.search(r"typeof\s+" + esc + r"\s*===?\s*['\"]function['\"]", ltxt) or
                re.search(r'window\.' + esc + r'\s*(&&|\?\.)', ltxt) or
                re.search(r'window\.' + esc + r'\s*\|\|', ltxt)
            )
            item = (risk, n, ul, bi, line_of(doff), dbi, kind)
            (guarded if has_guard else risks).append(item)

    def dedup(seq):
        seen, out = set(), []
        for r in seq:
            k = (r[1], r[2])
            if k in seen:
                continue
            seen.add(k)
            out.append(r)
        return out

    return len(blocks), len(defs), dedup(risks), dedup(guarded)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'index.html'
    nb, nd, risks, guarded = scan(path)
    print('[guard-tdz] %s: 内联 script 块 %d 个 / 可识别函数定义 %d 个' % (path, nb, nd))
    if guarded:
        print('[guard-tdz] 已加防御守卫（安全，仅记录）: %d 处' % len(guarded))
        for risk, n, ul, ub, dl, db, kind in guarded:
            print('    [%s·guarded] %s()  调用@L%d(块%d)  定义@L%d(块%d,%s)'
                  % (risk, n, ul, ub, dl, db, kind))
    if risks:
        print('[guard-tdz] ❌ 发现「先用后定义」风险 %d 处（会静默吞掉整段 IIFE）:' % len(risks))
        for risk, n, ul, ub, dl, db, kind in risks:
            print('    [%s] %s()  调用@L%d(块%d)  定义@L%d(块%d,%s)'
                  % (risk, n, ul, ub, dl, db, kind))
        print('[guard-tdz] 修法：把定义 HOIST 到首次调用之前的独立 <script> 块，'
              '或在调用处加 typeof/window 守卫')
        return 1
    print('[guard-tdz] ✅ 无「先用后定义」风险')
    return 0


if __name__ == '__main__':
    sys.exit(main())
