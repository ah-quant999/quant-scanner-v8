#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
name_utils.py — 股票名称/代码归一化共享模块（2026-08-14 抽出，消除多处重复）

集中维护：
  1) norm_code(code)        — 转纯数字 code（去 sh/sz/bj/hk 前缀与下划线）
  2) strip_entitlement_prefix(name) — 去交易所除权/除息/新股前缀 XD/XR/DR/N
  3) STANDARD_NAME_MAP      — code -> 标准中文名（港股/美股兜底 + A股除权日简称兜底）
  4) fix_name(code, name)   — 标准名优先（防 profile 错名覆盖），否则退回画像名

此前这些逻辑散落在 final_recommend.py / build_candidate_pool.py /
guanlan_extractor.py / scanner.py 共 4 处，已统一到这里。
新增算法脚本若需名称处理，一律 import 本模块，不要再写第 5 份。
"""
import re

# 常见港股/美股代码兜底名称表（当上游 name 缺失或等于 code 时使用）
# 格式：统一用纯数字 code（无 hk/sh 前缀）作为 key
STANDARD_NAME_MAP = {
    "00700": "腾讯控股",
    "09988": "阿里巴巴-W",
    "01024": "快手-W",
    "09618": "京东物流",
    "01093": "石药集团",
    "03690": "美团-W",
    "01810": "小米集团-W",
    "02331": "李宁",
    "02015": "理想汽车-W",
    "09888": "百度集团-SW",
    "06060": "众安在线",
    "01299": "友邦保险",
    "02318": "中国平安",
    "03988": "中国银行",
    "01398": "工商银行",
    "00939": "建设银行",
    "01208": "五矿资源",
    "00883": "中国海洋石油",
    "00857": "中国石油股份",
    "00386": "中国石油化工股份",
    "02628": "中国人寿",
    "02328": "中国财险",
    "03328": "交通银行",
    "06818": "中国光大银行",
    "01988": "民生银行",
    "01658": "邮储银行",
    "01199": "中远海运港口",
    "00489": "东风集团股份",
    "01797": "新东方在线",
    "02020": "安踏体育",
    "02319": "蒙牛乳业",
    "01898": "中煤能源",
    "01088": "中国神华",
    "00358": "江西铜业股份",
    "02600": "中国铝业",
    "01776": "广发证券",
    "06837": "海通证券",
    "06030": "中信证券",
    "03908": "中金公司",
    "06690": "海尔智家",
    "09633": "农夫山泉",
    "09868": "小鹏汽车-W",
    "02018": "瑞声科技",
    "02382": "舜宇光学科技",
    "01478": "丘钛科技",
    "02899": "紫金矿业",
    "01787": "山东黄金",
    # 2026-08-11 补：今日候选池出现的港股（之前缺失导致 09866/02269 等显示代码而非名称）
    # 同步 raw_data/candidate.json 中实际命中的 14 只港股，确保最终推荐卡 name 字段正确
    "00388": "香港交易所",
    "01209": "华润万象生活",
    "01211": "比亚迪股份",
    "01801": "信达生物",
    "02269": "药明生物",
    "02359": "药明康德",
    "06160": "百济神州",
    "06618": "京东健康",
    "06990": "科伦博泰",
    "09866": "蔚来-SW",
    # 2026-08-13 补：A 股除权除息日的简称兜底（交易所规定除权日简称前加 XD/XR/DR）
    # 上游 fetch 的 name 是 "XD中金黄"，剥 XD 后只剩 3 字，丢字看着像截断
    # 兜底用标准简称"中金黄金"，等除权除息完成后自动恢复
    "600489": "中金黄金",
}


def norm_code(c):
    """转纯数字 code（去 sh/sz/bj/hk 前缀与下划线），与小九原 final_recommend 实现保持一致。"""
    return str(c or "").replace("sh", "").replace("sz", "").replace("bj", "").replace("hk", "").replace("_", "").strip()


def strip_entitlement_prefix(name):
    """去除除权/除息/新股前缀 XD/XR/DR/N（交易所规定除权日简称前加）。

    例："XD中金黄" -> "中金黄"（注意：前缀剥离后若仍缺字，需用 STANDARD_NAME_MAP 按 code 还原标准名）
    """
    return re.sub(r'^(XD|XR|DR|N)', '', str(name).strip())


# ── 🛡 2026-10-01 一劳永逸（港股碰撞名 + 名码退化 消费点收口）─────────────
# 背景（10-01 主人截图实锤）：TOP10 第12名 000039 显示「中国北大荒」= hk00039 港股名
#   经「陈旧 out/gold_pool.json 遮蔽新鲜 raw_data」通路上位；第13名 000725 名=码退化。
# scanner/build_candidate_pool 各有带 EM 兜底的 resolve_*，但 generate_top10 /
#   final_recommend / gen_algo_track / build_pool_tracker 等【消费点】直接
#   s.get("name") 继承，绕过唯一校入口 ⇒ 本模块提供轻量纯本地收口（不再写第 5 份映射）。
_AUTH_CACHE = None


def _auth_maps():
    """延迟加载 raw_data/stock_names.json → (A股名映射{6位码:名}, 港股碰撞名集合)。
    与 scanner._stock_names_map_s 同规：顶层 dict 取 data；港股条目不进 6 位映射；
    去交易所排版空格。raw_data 版已入仓、任何环境恒可达。"""
    global _AUTH_CACHE
    if _AUTH_CACHE is not None:
        return _AUTH_CACHE
    amap, hk = {}, set()
    import os as _os, json as _json
    p = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                      "raw_data", "stock_names.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = _json.load(f)
        if isinstance(obj, dict):
            obj = obj.get("data") or []
        for it in (obj or []):
            if not isinstance(it, dict):
                continue
            c = (it.get("code") or "").strip()
            n = (it.get("name") or "").strip()
            if not c or not n:
                continue
            fc = (it.get("full_code") or "").strip().lower()
            mkt = (it.get("market") or "").strip().lower()
            if fc.startswith("hk") or mkt == "hk":
                hk.add(n)   # 收集港股名，供碰撞判据（中国北大荒/上海实业环境/FUTURE BRIGHT 家族）
                continue
            amap[c.zfill(6)] = (n.replace(" ", "").replace("\u3000", "")
                                .replace("Ａ", "A").replace("Ｂ", "B"))
    except Exception as e:
        print("  [WARN] name_utils 权威名映射加载失败: %s" % e)
    if not amap:
        print("  [WARN] name_utils A股名映射为空：raw_data/stock_names.json 不可读 ⇒ 名称将退化")
    _AUTH_CACHE = (amap, hk)
    return _AUTH_CACHE


def resolve_authoritative_name(code, name, market=""):
    """消费点统一收口：只拦两类【确定性错误】，不碰合法简称（防名称膨胀回归）。
      ① 名缺失 / 名==纯代码（000725 事故家族）
      ② 名 ∈ 港股碰撞名集合（hk00039 中国北大荒 顶 000039 中集集团 家族）
    合法冠名（N力勤/XD*/DR*）与正常简称原样放行；港股(market=="hk")不套用 A 股映射。"""
    n = (name or "").strip()
    c = norm_code(code)
    c6 = c.zfill(6)[-6:] if c else ""
    raw_code_s = str(code or "").strip()
    suspect = (not n) or n == raw_code_s or (c6 and n == c6) \
              or bool(re.fullmatch(r"[0-9A-Za-z]+", n))
    amap, hk = _auth_maps()
    if not suspect:
        if n in hk and (market or "").strip().lower() != "hk":
            m = amap.get(c6)
            if m:
                return m
        return n
    if (market or "").strip().lower() == "hk":
        return n or c6
    return amap.get(c6, n or c6)


def fix_name(code, name):
    """如果 name 为空或与 code 相同，用兜底映射表/画像修复。

    NAME_FIX_MAP 优先级 > profile name。
    背景：stock_profile.json 中 09618 给的是「京东集团-SW」（错），而港交所标准名称是「京东物流」。
    原逻辑「profile name 存在即用」会让上游 profile 的错误名称覆盖标准名。
    改为"标准名映射表兜底优先"，保证 09988/09618/09866/00700 等港股始终显示标准中文名。
    """
    c = norm_code(code)
    n = (name or "").strip()
    # 1) 标准映射表优先（防 profile 错覆盖标准名）
    if c in STANDARD_NAME_MAP:
        return STANDARD_NAME_MAP[c]
    # 2) profile name 合法时退回 profile
    if n and n != c:
        return n
    # 3) 兜底
    return n or c
