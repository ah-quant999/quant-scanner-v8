# -*- coding: utf-8 -*-
"""v8 全站审计：前端变量 / 构建映射 / raw 源 / 新鲜度 四方对账"""
import os, re, json, sys
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')
R = os.path.dirname(os.path.abspath(__file__))

html = open(os.path.join(R, 'index.html'), encoding='utf-8').read()
upd = open(os.path.join(R, 'update_v8.py'), encoding='utf-8').read()
fetch = open(os.path.join(R, 'cloud_fetch_v8.py'), encoding='utf-8').read()

fe_vars = set(re.findall(r'window\.([A-Z][A-Z0-9_]{2,})', html))
fe_vars.discard('X')

m = re.search(r'DATA_SOURCES\s*=\s*\{(.*?)\n\}', upd, re.S)
mapping = {}
if m:
    for k, v in re.findall(r'["\']([^"\']+\.json)["\']\s*:\s*["\']([A-Z0-9_]+)["\']', m.group(1)):
        mapping[v] = k
build_vars = set(mapping.keys())

data_files = {}
ddir = os.path.join(R, 'data')
for fn in sorted(os.listdir(ddir)):
    if not fn.endswith('.js'):
        continue
    p = os.path.join(ddir, fn)
    s = open(p, encoding='utf-8', errors='ignore').read(400000)
    mv = re.match(r'\s*window\.([A-Z0-9_]+)', s)
    var = mv.group(1) if mv else fn[:-3]
    mt = re.search(r'"update_time"\s*:\s*"([0-9][0-9\-: ]{8,19})"', s)
    data_files[var] = dict(file=fn, bytes=os.path.getsize(p), ut=mt.group(1) if mt else None)
data_vars = set(data_files.keys())

raw_files = {}
rdir = os.path.join(R, 'raw_data')
for fn in sorted(os.listdir(rdir)):
    if fn.endswith('.json'):
        raw_files[fn] = os.path.getsize(os.path.join(rdir, fn))

print("=" * 78)
print("[A] 前端引用变量 vs 构建映射 vs 实际数据文件")
print("=" * 78)
print(f"前端引用 window 变量: {len(fe_vars)} | DATA_SOURCES 映射: {len(build_vars)} | data/*.js: {len(data_vars)}")
print()
orphan = sorted(fe_vars - data_vars)
print(f"[X] 孤儿模块 - 前端引用但 data/ 无文件 ({len(orphan)}):")
for v in orphan:
    print(f"    - window.{v}")
print()
dead = sorted(data_vars - fe_vars)
print(f"[!] 死数据 - data/ 有文件但前端从不引用 ({len(dead)}):")
for v in dead:
    print(f"    - {data_files[v]['file']}  ({data_files[v]['bytes']}B)")
print()
nobuild = sorted(data_vars - build_vars)
print(f"[!] 无构建映射 - data/ 有文件但 DATA_SOURCES 无映射，不会自动更新 ({len(nobuild)}):")
for v in nobuild:
    d = data_files[v]
    print(f"    - {d['file']:<34} {d['bytes']:>8}B  ut={d['ut']}")
print()
print("=" * 78)
print("[B] 数据新鲜度")
print("=" * 78)
now = datetime.now()
rows = []
for v, d in data_files.items():
    age = None
    if d['ut']:
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                age = (now - datetime.strptime(d['ut'], f)).total_seconds() / 86400
                break
            except ValueError:
                pass
    rows.append((age if age is not None else 999, v, d))
rows.sort(reverse=True)
for age, v, d in rows:
    if age == 999:
        flag = "?? 无时间戳"
    elif age > 3:
        flag = f"[X] {age:.1f}天"
    elif age > 1.2:
        flag = f"[!] {age:.1f}天"
    else:
        flag = f"[OK] {age:.1f}天"
    inmap = "映射" if v in build_vars else "无映射"
    print(f"  {flag:<13} {d['file']:<34} {d['bytes']:>8}B [{inmap}]")
print()
print("=" * 78)
print("[C] raw_data 覆盖")
print("=" * 78)
missing_raw = [(var, j) for var, j in sorted(mapping.items()) if j not in raw_files]
print(f"[X] DATA_SOURCES 声明但 raw_data/ 缺失 ({len(missing_raw)}) - 该模块永不刷新:")
for var, j in missing_raw:
    print(f"    - {j:<34} -> window.{var}")
print()
extra_raw = sorted(set(raw_files) - set(mapping.values()))
print(f"[!] raw_data/ 有但 DATA_SOURCES 未映射 ({len(extra_raw)}) - 抓了没用:")
for j in extra_raw:
    print(f"    - {j} ({raw_files[j]}B)")
