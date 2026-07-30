#!/usr/bin/env python3
"""v8 数据构建脚本 — 从共享 data/ 注入真实JSON到 v8/index.html 模板"""

import json, os, re, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
V8_DIR = REPO / "v8"
TEMPLATE = V8_DIR / "index.html"
OUTPUT = V8_DIR / "dist" / "index.html"

# 需要注入到页面的数据源（key=window变量名, value=data目录文件名）
DATA_SOURCES = {
    "ETF_INTRADAY_HEAT": "etf_intraday_heat.json",
    "SECTOR_FUND_FLOW":  "sector_fund_flow.json",
    "SCAN_DATA":         "scan_data.json",
    "GOLD_POOL":         "gold_pool.json",
    "STOCK_LIST":        "stock_names.json",  # 实际是 stock_names
    "RECOMMEND":         "recommend.json",
    "MACRO_DATA":        "macro_data.json",
    "NT_DATA":           "nt_data.json",
    "LHB_DATA":          "lhb_data.json",
    "CONCEPT_RANKING":   "concept_ranking.json",
    "MARGIN_DATA":       "margin_data.json",
    "CFFEX_HOLDINGS":    "cffex_data.json",
    "IPO_DATA":          "ipo_score.json",
    "CRISIS_DATA":       "crisis_data.json",
}

def load_json(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def build():
    os.makedirs(V8_DIR / "dist", exist_ok=True)
    
    with open(TEMPLATE, encoding='utf-8') as f:
        html = f.read()
    
    # 在 </head> 前注入数据块
    data_blocks = []
    for var, file in DATA_SOURCES.items():
        jd = load_json(DATA / file)
        json_str = json.dumps(jd, ensure_ascii=False, default=str)
        data_blocks.append(f'<script>window.{var} = {json_str};</script>')
    
    inject_script = '\n'.join(data_blocks) + '\n'
    
    # 插入到 </head> 前
    html = html.replace('</head>', inject_script + '</head>')
    
    # 写入输出
    with open(OUTPUT, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ v8 数据注入完成")
    print(f"   数据源: {len(DATA_SOURCES)} 个")
    print(f"   输出: {OUTPUT}")
    print(f"   大小: {len(html):,} 字符")

if __name__ == '__main__':
    build()
