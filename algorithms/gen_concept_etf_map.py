#!/usr/bin/env python3
"""概念/行业 → 代表ETF 映射生成器（2026-11-21 主人令「B 新建」轻量重生，周更一次）

🔴 沿革：原 data/CONCEPT_ETF_MAP.js 为 2026-08-18 人工整理的一次性静态归档，仓库无生成器，
   停更半年（前端脚注亦如实标注「静态参考 2026-08-18 归档」）。主人拍板 B 方案新建。

🛡 真实性原则（铁律④真实标注 / 不弄虚作假）：
   - ETF 候选池 = raw_data/stock_names.json 的 market=='etf' 段（东财真值，≈1,666 只），
     输出的每只 ETF 都是交易所真实挂牌产品，绝不编造代码/名称；
   - 映射方法 = 板块名（东财概念/行业真名）与 ETF 真实名称的**关键词匹配**：
     ① 板块名本体（剥「概念/板块/指数/相关」尾缀）直接在 ETF 名中查找；
     ② 内置人工同义词表（覆盖主流板块）提供查找关键词——词表只提供「用哪个词去找」，
       命中的 ETF 仍是真实产品，与原 08-18 版「纯人工整理」相比可审计性更强；
   - 匹配不到的板块**不输出**（宁缺毋滥），前端已有「🎯 ETF暂无映射」优雅兜底；
   - leaders（龙头股）不再输出：与独立实时卡 SECTOR_LEADERS（fetch_sector_leaders.py，
     盘中实时龙头）口径重复，避免静态龙头误导（单一真源原则）。

🧭 输入：raw_data/concept_ranking.json（东财概念榜真名）+ raw_data/sector_fund_flow.json
   的 sectors_in（行业+概念真名）+ raw_data/stock_names.json（ETF 段真值）。
📤 输出：out/concept_etf_map.json（stage→raw_data→update_v8 转换 data/CONCEPT_ETF_MAP.js，
   顶层 dict 顶层键=板块名，消费端 window.CONCEPT_ETF_MAP[板块名].etf 直接兼容旧结构）。
🗓 周更门控：raw 旧版 update_time 距今 < 7 天 → 跳过重算（主人令「每周更新一次即可」），
   幂等退出 0，不产新文件。
"""

import json
import os
import re
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "out")
RAW_DIR = os.path.join(HERE, "..", "raw_data")
OUTPUT = os.path.join(OUT_DIR, "concept_etf_map.json")

WEEKLY_SECONDS = 7 * 86400

# 人工同义词表：板块名(或其核心词) → 在 ETF 真实名称中查找的关键词组。
# 保守覆盖主流板块；未收录板块若本体词匹配不到 ETF 则如实无映射。
# 词表只提供查找关键词，命中 ETF 必须真实存在于 stock_names ETF 段（真值锚定）。
SYNONYMS = {
    "半导体": ["半导体", "芯片", "集成电路", "存储"],
    "芯片": ["芯片", "半导体"],
    "人工智能": ["人工智能", "AI", "智能", "算力", "大数据", "云计算"],
    "AI": ["AI", "人工智能", "智能"],
    "算力": ["算力", "大数据", "云计算", "通信"],
    "大模型": ["人工智能", "AI", "智能"],
    "CPO": ["通信", "5G", "光"],
    "光模块": ["通信", "光"],
    "机器人": ["机器人", "智能制造", "人工智能"],
    "券商": ["券商", "证券"],
    "证券": ["证券", "券商"],
    "银行": ["银行", "金融"],
    "保险": ["保险", "金融"],
    "金融": ["金融", "证券", "银行", "保险"],
    "军工": ["军工", "国防"],
    "国防": ["国防", "军工"],
    "医药": ["医药", "医疗", "生物医药"],
    "医疗": ["医疗", "医药", "医疗器械"],
    "创新药": ["创新药", "医药", "生物医药"],
    "疫苗": ["疫苗", "医药", "生物"],
    "CXO": ["医药", "生物医药"],
    "中药": ["中药", "医药"],
    "白酒": ["白酒", "食品饮料", "消费"],
    "消费": ["消费", "食品饮料", "酒"],
    "食品": ["食品饮料", "食品"],
    "预制菜": ["食品", "消费"],
    "新能源": ["新能源", "光伏", "绿色电力", "储能"],
    "光伏": ["光伏", "新能源", "绿色电力"],
    "储能": ["储能", "新能源", "电池"],
    "锂电": ["电池", "锂电池", "新能源"],
    "电池": ["电池", "锂电池", "新能源"],
    "新能源车": ["新能源车", "智能汽车", "电池", "新能源汽车"],
    "汽车": ["智能汽车", "新能源车", "汽车"],
    "智能驾驶": ["智能汽车", "智能驾驶", "汽车"],
    "无人驾驶": ["智能汽车", "汽车"],
    "有色": ["有色金属", "有色"],
    "稀土": ["稀土", "有色金属"],
    "黄金": ["黄金", "有色金属"],
    "铜": ["铜", "有色金属"],
    "煤炭": ["煤炭", "能源"],
    "钢铁": ["钢铁", "黑色金属"],
    "石油": ["石油", "能源", "石化"],
    "油气": ["石油", "石化", "能源"],
    "化工": ["化工", "石化"],
    "农业": ["农业", "养殖", "畜牧"],
    "养殖": ["养殖", "农业", "畜牧"],
    "猪": ["畜牧", "养殖", "农业"],
    "水产": ["农业", "养殖"],
    "电力": ["绿色电力", "电力", "电网", "能源"],
    "电网": ["电网", "电力", "绿色电力"],
    "绿电": ["绿色电力", "电力", "光伏"],
    "游戏": ["游戏", "传媒", "影视"],
    "传媒": ["传媒", "影视", "游戏"],
    "影视": ["影视", "传媒"],
    "短剧": ["传媒", "影视", "游戏"],
    "通信": ["通信", "5G"],
    "5G": ["5G", "通信"],
    "6G": ["通信", "5G"],
    "计算机": ["计算机", "软件", "信息技术", "大数据"],
    "软件": ["软件", "计算机", "信息技术"],
    "信创": ["计算机", "软件", "信息技术", "大数据"],
    "数据要素": ["大数据", "数据", "信息技术"],
    "云计算": ["云计算", "大数据", "计算机"],
    "大数据": ["大数据", "云计算", "计算机"],
    "网络安全": ["计算机", "软件", "信息技术"],
    "房地产": ["地产", "房地产"],
    "地产": ["地产", "房地产"],
    "基建": ["基建", "建材", "建筑"],
    "建材": ["建材", "基建", "建筑"],
    "建筑": ["基建", "建筑", "建材"],
    "家电": ["家电", "消费"],
    "家居": ["家电", "消费", "建材"],
    "环保": ["环保", "绿色"],
    "旅游": ["旅游", "消费"],
    "酒店": ["旅游", "消费"],
    "交通运输": ["物流", "运输", "交通"],
    "物流": ["物流", "运输", "交通"],
    "航运": ["物流", "运输", "交通"],
    "港口": ["物流", "运输", "交通"],
    "电力设备": ["电力", "新能源", "光伏"],
    "机械": ["智能制造", "机械", "机器人"],
    "机械设备": ["智能制造", "机械", "机器人"],
    "纺织": ["消费", "纺织服装", "服装"],
    "服装": ["纺织服装", "服装", "消费"],
    "白酒概念": ["白酒", "食品饮料"],
    "低空经济": ["军工", "机械", "机器人"],
    "卫星": ["军工", "通信", "国防"],
    "北斗": ["军工", "通信", "国防"],
    "黄金概念": ["黄金", "有色金属"],
    "资源开采": ["有色金属", "黄金", "煤炭", "石油"],
    "页岩气": ["石油", "石化", "能源"],
    "可燃冰": ["石油", "能源"],
    "地热能": ["绿色电力", "电力", "能源"],
    "酿酒": ["白酒", "食品饮料", "酒"],
    "啤酒": ["食品饮料", "酒", "消费"],
    "焦炭": ["煤炭", "能源"],
    "炼油": ["石油", "石化"],
    "炼化": ["石油", "石化"],
    "石油石化": ["石油", "石化", "能源"],
    "水力发电": ["绿色电力", "电力"],
    "核力发电": ["绿色电力", "电力", "核电"],
    "电信运营商": ["通信", "5G"],
    "航空运输": ["运输", "交通", "物流"],
    "铁路运输": ["交通", "运输", "物流"],
    "农林牧渔": ["农业", "养殖"],
    "渔业": ["农业", "养殖"],
    "水产养殖": ["农业", "养殖"],
    "种子": ["农业"],
    "基因测序": ["医药", "医疗", "生物医药"],
    "幽门螺杆菌": ["医药", "医疗"],
    "青蒿素": ["医药", "中药"],
    "长寿药": ["医药", "生物医药"],
    "民营医院": ["医疗", "医药"],
    "农产品加工": ["农业", "食品"],
    "禽饲料": ["农业", "养殖"],
    "畜禽饲料": ["农业", "养殖"],
    "钢铁结构": ["钢铁", "建材"],
    "工程机械": ["机械", "智能制造"],
    "机床": ["机械", "智能制造"],
    "轮毂电机": ["智能汽车", "汽车", "机械"],
    "汽车热管理": ["智能汽车", "汽车"],
    "宁德时代概念": ["电池", "新能源"],
    "麒麟电池": ["电池", "新能源"],
    "固态电池": ["电池", "新能源"],
    "熔盐储能": ["储能", "新能源", "绿色电力"],
    "空气能热泵": ["绿色电力", "家电"],
    "低碳冶金": ["钢铁", "绿色"],
    "转基因": ["农业"],
    "生态农业": ["农业"],
    "农村电商": ["消费", "物流"],
    "社区团购": ["消费", "零售"],
    "冰雪经济": ["旅游", "消费"],
    "体育产业": ["消费", "体育"],
    "盲盒经济": ["消费", "文娱"],
    "谷子经济": ["消费", "文娱"],
    "数字阅读": ["传媒", "计算机"],
    "知识产权": ["传媒", "计算机"],
    "网约车": ["计算机", "汽车"],
    "智慧政务": ["计算机", "软件", "大数据"],
    "时空大数据": ["大数据", "计算机"],
    "食品安全": ["食品饮料", "农业"],
    "保险": ["保险", "金融"],
    "国有大型银行": ["银行", "金融"],
    "固态电池": ["电池", "新能源"],
    "氢能源": ["新能源", "绿色电力", "石化"],
    "碳中和": ["环保", "绿色电力", "新能源"],
    "数字经济": ["大数据", "计算机", "软件"],
    "元宇宙": ["游戏", "传媒", "人工智能"],
    "跨境": ["消费", "物流"],
    "央企": ["央企", "国企"],
    "国企": ["央企", "国企"],
    "红利": ["红利", "央企"],
    "沪深300": ["沪深300"],
    "中证500": ["中证500"],
    "科创": ["科创", "科技"],
    "科技": ["科技", "信息技术", "计算机"],
    "养老": ["养老", "医药"],
    "婴童": ["消费", "乳业"],
    "乳业": ["乳业", "食品"],
    "多元金融": ["金融", "证券"],
    "金融科技": ["金融", "计算机", "软件"],
    "区块链": ["计算机", "软件", "金融"],
    "信息安全": ["计算机", "软件"],
    "智能穿戴": ["消费电子", "电子"],
    "消费电子": ["消费电子", "电子"],
    "电子": ["电子", "半导体", "消费电子"],
    "面板": ["电子", "面板"],
    "led": ["电子", "面板"],
    "军工电子": ["军工", "电子"],
    "航天": ["军工", "国防"],
    "航空": ["军工", "国防", "运输"],
    "船舶": ["军工", "国防"],
}


def _load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _weekly_gate():
    """周更门控：raw 旧版距今 < 7 天 → True（跳过）。"""
    old = _load_json(os.path.join(RAW_DIR, "concept_etf_map.json"))
    if not old:
        return False
    try:
        ts = datetime.strptime(str(old.get("update_time", ""))[:19], "%Y-%m-%d %H:%M:%S")
        age = (datetime.now() - ts).total_seconds()
        if 0 <= age < WEEKLY_SECONDS:
            print(f"  ⏭️  周更门控：旧版仅 {age/86400:.1f} 天前（<7 天），跳过重算")
            return True
    except Exception:
        pass
    return False


def _core_of_name(name):
    """剥掉板块名尾部通用词与 ETF 名尾部通用词（含东财行业分级罗马数字尾缀：白酒Ⅲ/保险Ⅱ等）。"""
    return re.sub(r"(概念|板块|指数|相关|题材|行业|[ⅠⅡⅢⅣⅠ]+)$", "", str(name or "").strip())


def _load_targets():
    """目标板块名集合（概念榜真名 + 资金流入的行业/概念真名）。"""
    names = []
    cr = _load_json(os.path.join(RAW_DIR, "concept_ranking.json")) or {}
    for it in (cr.get("items") or []):
        if isinstance(it, dict) and it.get("name"):
            names.append(str(it["name"]))
    sff = _load_json(os.path.join(RAW_DIR, "sector_fund_flow.json")) or {}
    for s in (sff.get("sectors_in") or []):
        if isinstance(s, dict) and s.get("name"):
            names.append(str(s["name"]))
    # 去重保序
    seen, out = set(), []
    for n in names:
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _load_etf_pool():
    """ETF 真值池：market=='etf' 段。"""
    sn = _load_json(os.path.join(RAW_DIR, "stock_names.json")) or {}
    data = sn.get("data", sn) if isinstance(sn, dict) else sn
    if not isinstance(data, list):
        return []
    pool = []
    for s in data:
        if isinstance(s, dict) and s.get("market") == "etf":
            code = str(s.get("code", "")).strip()
            name = str(s.get("name", "")).strip()
            if code and name:
                pool.append({"code": code, "name": name})
    return pool


def _match_one(sector, pool):
    """单板块匹配最佳 ETF。返回 {"code","name"} 或 None。
    🛡 评分（2026-11-21 冒烟修正）：**本体词最优先**（板块名直接命中 > 词表词按声明顺序），
    同词内取最短 ETF 名（简洁通用）→ code 升序（稳定）。
    ⚠️ 禁止「最长匹配词优先」——冒烟实证会把「白酒」抢成「食品饮料ETF」、「印制电路板」
    误配到「半导体ETF」（宽泛二级词骑到本体词头上）。
    """
    core = _core_of_name(sector)
    words = [core] + [w for w in SYNONYMS.get(core, SYNONYMS.get(sector, []))]
    best = None
    best_key = None
    for wi, w in enumerate(words):
        w = w.strip()
        if len(w) < 2:
            continue
        for etf in pool:
            en = etf["name"]
            en_core = re.sub(r"(ETF|LOF|联接|基金|指数)$", "", en)
            hit = None
            if w in en:
                hit = len(w)
            elif len(en_core) >= 2 and en_core in w:
                hit = len(en_core)
            if hit is None:
                continue
            # 词序优先（wi=0 本体词最高），词内命中越长越精确，再按 ETF 名短、code 稳定
            key = (0 if wi == 0 else 1, wi, hit, -len(en), [ord(c) for c in etf["code"]])
            if best_key is None or key > best_key:
                best_key = key
                best = etf
        if best is not None:
            break  # 本体词/靠前词命中即停，宽泛二级词不得骑到前面词头上
    return best


def main():
    print("=" * 50)
    print("  概念/行业 → 代表ETF 映射生成器（周更）")
    print("=" * 50)
    if _weekly_gate():
        print("  ✅ 本周已有新鲜映射，幂等跳过")
        return

    targets = _load_targets()
    pool = _load_etf_pool()
    print(f"  📥 目标板块 {len(targets)} 个 | ETF 真值池 {len(pool)} 只")
    if len(pool) < 500:
        print("  ::error title=v8-etf-map-pool-empty::ETF 真值池不足 500 只（stock_names ETF 段残缺），"
              "拒绝生成映射（宁缺毋滥，保留线上旧版）")
        return

    mapping = {}
    for name in targets:
        m = _match_one(name, pool)
        if m:
            mapping[name] = {"etf": {"code": m["code"], "name": m["name"]}}

    print(f"  🧩 匹配成功 {len(mapping)}/{len(targets)} 板块（未匹配 {len(targets)-len(mapping)} 个如实省略）")
    if not mapping:
        print("  ::error title=v8-etf-map-empty::零匹配，拒绝写盘（保留线上旧版）")
        return

    os.makedirs(OUT_DIR, exist_ok=True)
    out = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "note": "概念/行业→代表ETF 映射：板块名为东财概念/行业真名；ETF 为交易所真实挂牌产品"
                "（从全量 ETF 名单按名称关键词匹配选出，每周刷新）；仅为研究参考，不构成投资建议。",
        "matched_ratio": f"{len(mapping)}/{len(targets)}",
    }
    out.update(mapping)  # 顶层键=板块名，兼容旧结构 window.CONCEPT_ETF_MAP[板块名].etf
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"  ✅ {len(mapping)} 板块 → {OUTPUT}")


if __name__ == "__main__":
    main()
