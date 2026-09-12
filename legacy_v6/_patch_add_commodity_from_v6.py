"""
2026-08-02 一次性补丁：v6 仓 etf_intraday_heat 的商品分类快照合并进 v8 raw_data。
v8 原生管道（cloud_fetch_v8.py::f_etf_intraday_heat）走的是东财 push2delay m:1+t:9
只返回 4 分类（宽基/行业/主题/跨境），不含商品/货币。本脚本用 v6 仓 7月29日
akshare fund_etf_spot_em 全市场分类的快照给商品分类兜底（货币按设计排除）。
标 stale_source 让用户能识别这是 4 天前快照，不是今天的实时数据。
"""
import json
import os
from datetime import datetime

V6_RAW = r"E:\workspace\stock-scanner\data\etf_intraday_heat.json"
V8_RAW = r"E:\workspace\quant-scanner-v8\raw_data\etf_intraday_heat.json"

def main():
    if not os.path.exists(V6_RAW):
        print(f"ERR: v6 raw_data 不存在 {V6_RAW}")
        return 1
    if not os.path.exists(V8_RAW):
        print(f"ERR: v8 raw_data 不存在 {V8_RAW}")
        return 1
    v6 = json.load(open(V6_RAW, 'r', encoding='utf-8'))
    v8 = json.load(open(V8_RAW, 'r', encoding='utf-8'))
    v6_com = (v6.get('categories') or {}).get('商品')
    if not v6_com:
        print("ERR: v6 没有商品分类数据")
        return 1
    v8_categories = v8.get('categories') or {}
    if v8_categories.get('商品'):
        print("INFO: v8 raw_data 已有商品分类，跳过合并")
        return 0
    # 字段对齐（v8 渲染只读 code/name/main_net_inflow/pct，其余字段保留无害）
    v8_categories['商品'] = {
        'net_inflow_yi': v6_com.get('net_inflow_yi', 0),
        'count': v6_com.get('count', 0),
        'top_inflow': v6_com.get('top_inflow', []),
        'top_outflow': v6_com.get('top_outflow', []),
        'stale_source': f"v6_snapshot_{v6.get('update_time','')}",
        'note': '来自 v6 仓快照（东财 push2delay 不含商品分类），待 v8 原生管道补齐后移除',
    }
    v8['categories'] = v8_categories
    # 加 note 标注合并动作
    note_old = v8.get('note', '')
    v8['note'] = (note_old + ' | 商品分类临时从 v6 快照同步').strip(' |')
    # 备份原文件再写
    bak = V8_RAW + '.bak'
    if not os.path.exists(bak):
        with open(V8_RAW, 'r', encoding='utf-8') as f: original = f.read()
        with open(bak, 'w', encoding='utf-8') as f: f.write(original)
        print(f"备份原文件 → {bak}")
    with open(V8_RAW, 'w', encoding='utf-8') as f:
        json.dump(v8, f, ensure_ascii=False, indent=2)
    print(f"OK: 商品分类合并完成")
    print(f"   count={v8_categories['商品']['count']}, net_yi={v8_categories['商品']['net_inflow_yi']}")
    print(f"   top_inflow={len(v8_categories['商品']['top_inflow'])}, top_outflow={len(v8_categories['商品']['top_outflow'])}")
    print(f"   stale_source={v8_categories['商品']['stale_source']}")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())