#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
guanlan_extractor.py — 知识星球研报自动提取器（API优先 + Selenium兜底）
═══════════════════════════════════════════════════════
用途: 从知识星球(zsxq.com)抓取投行/机构研报，解析出机构名、评级、
      涉及股票、原文，输出数据文件:
        - data/guanlan_reports.json    观澜台研报列表
        - data/guanlan_watchlist.json  合并推股池

数据源:
  - 观澜台: wx.zsxq.com/group/28882555515111 (group_id=28882555515111)
  - 甲股文: wx.zsxq.com/group/51115218441414 (可选, 未启用)

认证: cookie名=zsxq_access_token（非 xq_a_token！）
凭据: data/zszxq_token.json {"token": "...", "updated": "..."}

⚠️ 铁律: 本文件是生产脚本，禁止误删。
============================================================
更新历史:
  2026-07-07  重写为 API 优先模式，新增摘星阁双星球支持
             根因修复: cookie 名从 xq_a_token → zsxq_access_token
  2026-07-17  放弃摘星阁源(数据陈旧且未被候选池消费)，从 GROUPS 移除
"""
import json
import os
import re
import sys
import time
import urllib.request

# 名称归一化共享模块（2026-08-14 抽出，消除与 final_recommend/build_candidate_pool/scanner 的重复）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from name_utils import strip_entitlement_prefix  # noqa: E402
import requests as _requests
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BASE_DIR)
# v8 原生化钩子（2026-08-02）：v8 仓通过 V8_OUT_DIR 环境变量重定向 DATA_DIR 到仓库根 out/
# 2026-08-10 修复：V8_OUT_DIR 被设为空字符串时（workflow env 与 input 同名导致），
# 原 `if _V8_OUT:` 会把它当 False，本脚本写 algorithms/data/ 而 build_candidate_pool.py
# 读 out/，造成观澜台/maharo 来源恒为 0。空/未设置时统一回退到仓库根 out/。
_V8_OUT = os.environ.get("V8_OUT_DIR") or os.path.join(REPO_ROOT, "out")
DATA_DIR = _V8_OUT

# 🔴 2026-08-09 修复：凭据路径不能跟着 DATA_DIR 走 out/。
#    v8 环境下 V8_OUT_DIR=仓库根/out，原写法把 token 指向 out/zsxq_token.json——
#    但 out/ 是中间产物目录（每轮被覆盖，也不在 .gitignore 的凭据保护清单里），
#    用户按文档写入的 data/zsxq_token.json 永远读不到 → 观澜台恒为 0 只。
#    统一为「仓库根/data/」，.gitignore 已保护该凭据文件。
_TOKEN_CANDIDATES = [
    os.path.join(os.path.dirname(BASE_DIR), "data", "zsxq_token.json"),  # v8 标准位置（.gitignore 已保护）
    os.path.join(DATA_DIR, "zsxq_token.json"),                            # 兼容旧路径（out/ 或 algorithms/data/）
]
TOKEN_FILE = next((p for p in _TOKEN_CANDIDATES if os.path.exists(p)), _TOKEN_CANDIDATES[0])

# ── 星球配置 ──
GROUPS = {
    "guanlan": {
        "name": "观澜台",
        "group_id": "28882555515111",
        "out_reports": os.path.join(DATA_DIR, "guanlan_reports.json"),
    },
}
WATCHLIST_OUT = os.path.join(DATA_DIR, "guanlan_watchlist.json")

# API 基址
ZSXQ_API = "https://api.zsxq.com/v2/groups/{group_id}/topics"

# ── 机构名识别 ──
INSTITUTION_KEYWORDS = [
    "高盛", "摩根士丹利", "摩根大通", "花旗", "美银", "瑞银", "瑞信",
    "汇丰", "德意志银行", "德银", "野村", "三菱", "大和", "巴克莱",
    "中金", "中信", "华泰", "国君", "申万", "招商", "广发", "兴业",
    "东方证券", "光大", "海通", "财通", "普徕仕", "埃弗科", "杰富瑞",
]

RATING_MAP = {
    "买入": "买入", "增持": "增持", "推荐": "推荐", "强烈推荐": "强烈推荐",
    "跑赢行业": "跑赢行业", "优于大市": "优于大市",
    "中性": "中性", "持有": "持有", "减持": "减持", "卖出": "卖出",
    "未评级": "未评级", "观望": "观望",
}

EXCHANGE_PATTERNS = [
    (r"\.SS$", "SH", "沪市"),
    (r"\.SZ$", "SZ", "深市"),
    (r"\.HK$", "HK", "港股"),
    (r"\.BJ$", "BJ", "北交所"),
]

# ── 股票名→代码索引（用于"只写名字没写代码"的研报反向匹配）──
STOCK_NAMES_FILE = os.path.join(DATA_DIR, "stock_names.json")
GOLD_POOL_FILE = os.path.join(DATA_DIR, "gold_pool.json")  # 港股补充索引源
_NAME_INDEX = None  # [(name, code, full_code, exchange, market), ...] 按名字长度降序
NAME_INDEX = None   # 全局索引（main 中构建后供 parse_stock_codes 使用）


def build_name_index():
    """加载 stock_names.json(A股) + gold_pool.json(港股)，构建 (名字, 代码) 索引，按名字长度降序排列。

    用途: 研报原文常写 '招商证券 - H 股' / '中国农业银行 - H 股' / '金茂(0817.HK)'
          这类只给名字不给标准格式代码的研报 → 用名字反查代码。
          港股名从 gold_pool.json 补充（stock_names.json 只有 A 股）。
    """
    global _NAME_INDEX
    if _NAME_INDEX is not None:
        return _NAME_INDEX
    idx = []

    # ── 1) A 股索引（stock_names.json）──
    try:
        with open(STOCK_NAMES_FILE, "r", encoding="utf-8") as f:
            names = json.load(f)
        for s in names:
            nm = (s.get("name") or "").strip()
            code = (s.get("code") or "").strip()
            fc = (s.get("full_code") or "").strip()
            if not nm or not code:
                continue
            exch, market = "SH", "沪市"
            if fc.startswith("sz"):
                exch, market = "SZ", "深市"
            elif fc.startswith("bj"):
                exch, market = "BJ", "北交所"
            idx.append((nm, code, fc, exch, market))
    except Exception as e:
        print(f"  [WARN] A股名索引加载失败: {e}")

    # ── 2) 港股补充索引（gold_pool.json 中 board_label=港股 的）──
    try:
        with open(GOLD_POOL_FILE, "r", encoding="utf-8") as f:
            gp = json.load(f)
        hk_count = 0
        for k, v in gp.get("stocks", {}).items():
            if v.get("board_label") != "港股":
                continue
            nm = (v.get("name") or "").strip()
            code = (v.get("code") or "").strip()
            if not nm or not code:
                continue
            # 港股 full_code 格式: 如 01288.HK
            fc = f"{code}.HK"
            # 去掉后缀 -W / -S 等（如 快手-W → 快手）
            nm_clean = re.sub(r"[-‐]\w$", "", nm)
            idx.append((nm, code, fc, "HK", "港股"))
            if nm_clean != nm:
                idx.append((nm_clean, code, fc, "HK", "港股"))
            hk_count += 1
        print(f"  ▸ 港股补充索引: {hk_count} 只")
    except Exception as e:
        print(f"  [WARN] 港股索引加载失败: {e}")

    # 按名字长度降序，长名优先匹配（避免短名误吞）
    idx.sort(key=lambda x: len(x[0]), reverse=True)
    _NAME_INDEX = idx
    return _NAME_INDEX


# ── 干净名字解析(根治: 研报句子绝不信任, 名字一律按 code 反查权威源) ──
_CODE_NAME_MAP = None
_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_EM_NAME_CACHE = {}
_GARBAGE_KW = ['我们', '看好', '完成', '通过', '闪电', '带动', '新增', '包括',
               '给予', '推荐', '关注', '建议', '认为', '预计', '有望', '中标',
               '签订', '取得', '获得', '基石', '其中', '以及', '此外', '例如',
               '如下', '对于', '关于', '除了', '根据', '也']


def _build_code_name_map():
    """A股 code→name (来自 stock_names.json, 干净)。"""
    global _CODE_NAME_MAP
    if _CODE_NAME_MAP is not None:
        return _CODE_NAME_MAP
    _CODE_NAME_MAP = {}
    try:
        with open(STOCK_NAMES_FILE, "r", encoding="utf-8") as f:
            for s in json.load(f):
                c = (s.get("code") or "").strip()
                n = (s.get("name") or "").strip()
                if c and n:
                    _CODE_NAME_MAP[c.zfill(6)] = n
    except Exception:
        pass
    return _CODE_NAME_MAP


def _em_name(code, exchange):
    key = f"{exchange}_{code}"
    if key in _EM_NAME_CACHE:
        return _EM_NAME_CACHE[key]
    _EM_NAME_CACHE[key] = None
    if exchange == "HK":
        secid = "116." + str(code).zfill(5)
    elif exchange in ("SH", "SZ"):
        secid = ("1." if exchange == "SH" else "0.") + str(code).zfill(6)
    else:
        return None
    try:
        r = _requests.get("https://push2.eastmoney.com/api/qt/stock/get",
                          params={"secid": secid, "fields": "f57,f58"},
                          headers=_EM_HEADERS, timeout=8)
        if r.status_code == 200:
            d = r.json().get("data") or {}
            nm = (d.get("f58") or "").strip()
            if nm and not re.fullmatch(r'[0-9A-Za-z]+', nm):
                _EM_NAME_CACHE[key] = nm
    except Exception:
        pass
    return _EM_NAME_CACHE[key]


def _norm_name(n):
    s = str(n).strip()
    s = strip_entitlement_prefix(s)
    s = s.replace('Ａ', 'A').replace('Ｂ', 'B')
    s = re.sub(r'(股份)?有限公司$', '', s)
    s = re.sub(r'[（(].*?[)）]$', '', s)
    return s.strip()


def _looks_clean(n):
    s = str(n).strip()
    if not s or re.fullmatch(r'[0-9A-Za-z]+', s):
        return False
    if s in ('A', 'B', '股', '20', 'ETF', '基金'):
        return False
    if any(k in s for k in _GARBAGE_KW):
        return False
    if '债' in s or '指数' in s or 'ETF' in s or '基金' in s:
        return False
    t = re.sub(r'(股份)?有限公司$', '', s)
    t = re.sub(r'[-‐][WSR]$', '', t)  # 容忍港股 -W/-S/-R 双重上市后缀
    return 2 <= len(t) <= 8 and re.fullmatch(r'[一-鿿]+', t)


def resolve_guanlan_name(code, exchange, hint_name):
    """研报股票名字: 一律按 code 反查权威源, 绝不信任研报句子。
    优先级: 东财 f58(云端权威) > stock_names.json(A股) > 干净 hint > 代码兜底。
    """
    em = _em_name(code, exchange)
    if em:
        return _norm_name(em)
    if exchange in ("SH", "SZ"):
        snm = _build_code_name_map().get(str(code).zfill(6))
        if snm:
            return _norm_name(snm)
    if _looks_clean(hint_name):
        return _norm_name(hint_name)
    return str(code).strip()


def detect_exchange_hint(text, pos):
    """在 text 的 pos 位置附近检测 'H股'/'A股' 提示，返回 'HK'/'A'/'?'"""
    window = text[pos:pos + 20]
    if "H股" in window or "H 股" in window or "港股" in window:
        return "HK"
    if "A股" in window or "A 股" in window:
        return "A"
    return "?"


def load_token():
    """读取 token 字符串

    优先级：环境变量 ZSXQ_TOKEN（云端 GitHub Secret 注入）> data/zsxq_token.json（本地文件）
    """
    # 1) 环境变量优先（云端 workflow 通过 secrets.ZSXQ_TOKEN 注入）
    env_tok = os.environ.get("ZSXQ_TOKEN", "").strip()
    if env_tok:
        return env_tok

    # 2) 回退本地文件
    if not os.path.exists(TOKEN_FILE):
        print(f"  [ERR] token 文件不存在: {TOKEN_FILE} 且无 ZSXQ_TOKEN 环境变量")
        return None
    with open(TOKEN_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    tok = data.get("token", "")
    if not tok:
        print(f"  [ERR] token 文件为空: {TOKEN_FILE}")
        return None
    return tok


def api_fetch_topics(group_id, token, count=20):
    """通过知识星球 API 获取星球帖子列表（纯 HTTP，无需 Selenium）

    认证方式: Cookie header 中设置 zsxq_access_token
    ⚠️ 知识星球 API 有频率限制，短时间内多次请求可能返回空结果
       本函数内置 2 次重试 + 3 秒间隔
    返回: list of dict (API 原始 topic 结构)
    """
    url = ZSXQ_API.format(group_id=group_id) + f"?count={count}"
    headers = {
        "cookie": f"zsxq_access_token={token}",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }

    for attempt in range(3):  # 最多重试 2 次
        if attempt > 0:
            time.sleep(3)  # 等待限流恢复
        try:
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=20)
            data = json.loads(resp.read())
            topics = data.get("resp_data", {}).get("topics", [])
            if topics or attempt >= 2:  # 有数据或最后一次尝试
                if attempt > 0 and topics:
                    print(f"    (第{attempt+1}次尝试成功)")
                return topics
            # 空结果但还有重试机会 → 继续重试
            print(f"    (第{attempt+1}次返回空，等待重试...)")
        except Exception as e:
            print(f"    (第{attempt+1}次异常: {e})")
            if attempt >= 2:
                return []
    return []


def parse_stock_codes(text, name_index=None):
    """从文本提取股票名+代码+交易所。

    三阶段:
      1) 正则A: 标准格式 '名称(代码.SS/SZ/HK/BJ)'
      2) 正则B: 宽松格式 '名称（代码.HK/SZ/SS，评级/文字）' — 处理全角括号+后缀文字
      3) 名字反查: 用 stock_names(A股) + gold_pool(港股) 索引匹配只写名字的
    """
    results = []
    seen_codes = set()
    seen_names = set()

    # ── 阶段1: 标准正则 ──
    pattern = re.compile(
        r'([\u4e00-\u9fa5·A-Za-z0-9\-]+)\s*[（(]\s*(\d{4,6})\.(SS|SZ|HK|BJ)\s*[）)]'
    )
    for m in pattern.finditer(text):
        name = m.group(1).strip()
        code = m.group(2)
        exch_suffix = m.group(3)
        exchange, market = "SH", "沪市"
        for pat, ex, mk in EXCHANGE_PATTERNS:
            if re.search(pat, f".{exch_suffix}"):
                exchange, market = ex, mk
                break
        full = f"{code}.{exchange}"
        if full not in seen_codes:
            seen_codes.add(full)
            seen_names.add(name)
            results.append({
                "name": resolve_guanlan_name(code, exchange, name),
                "code": code,
                "full_code": full,
                "exchange": exchange,
                "market": market,
            })

    # ── 阶段2: 宽松正则（处理研报中常见的不标准格式）──
    # 匹配: 名称（代码.HK/SZ/SS，xxx）或 名称 (代码.HK xxx)
    # 特征: 全角/半角括号内是 位数.HK/SZ/SS/BJ 后面可能有中文逗号+评级等文字
    loose_patterns = [
        # 中国金茂（0817.HK，买入）或 金茂(0817.HK，买入)
        re.compile(
            r'([\u4e00-\u9fa5·A-Za-z0-9\-]+)\s*[（(]'
            r'\s*(\d{4,6})\.(HK|SZ|SS|BJ)'
            r'[）)\s\u3000,，]*[\u4e00-\u9fa5]*'  # 允许后缀如 ，买入 / ）等
        ),
        # 换行分隔: 名称\n(0817.HK，买入）
        re.compile(
            r'([\u4e00-\u9fa5·A-Za-z0-9\-]{2,})\s*\n\s*[（(]'
            r'\s*(\d{4,6})\.(HK|SZ|SS|BJ)'
        ),
        # 纯代码引用: （2330.TW）台股标记用（不注入结果但记录）
        re.compile(
            r'([\u4e00-\u9fa5·A-Za-z0-9\-]+)\s*[（(]\s*(\d{4,6})\.(TW|TWO|TT)\s*[）)]'
        ),
    ]
    for pat in loose_patterns:
        for m in pat.finditer(text):
            name = m.group(1).strip()
            code = m.group(2)
            exch_suffix = m.group(3)
            # 跳过台股(TW/TWO/TT) — 不在A股/港股池中
            if exch_suffix in ("TW", "TWO", "TT"):
                continue
            exchange, market = "SH", "沪市"
            for epat, ex, mk in EXCHANGE_PATTERNS:
                if exch_suffix == epat.lstrip(r"\^").lstrip(r"\$").replace("\\.", "."):
                    exchange, market = ex, mk
                    break
            if exch_suffix == "HK":
                exchange, market = "HK", "港股"
            full = f"{code}.{exchange}"
            # 避免名字太短导致误匹配（至少2字）
            if len(name) < 2:
                continue
            # 1. 过滤掉误匹配的前缀词（包括研报推荐用语）
            _bad_prefixes = ("其中", "包括", "以及", "此外", "例如", "如下",
                            "对于", "关于", "除了", "通过", "根据",
                            "我们也看好", "我们看好", "我们推荐", "我们建议",
                            "强烈推荐", "建议关注", "可以关注",
                            "今日关注", "短线关注", "中线关注")
            cleaned = name
            for _bp in _bad_prefixes:
                if cleaned.startswith(_bp):
                    cleaned = cleaned[len(_bp):]
                    break
            if not cleaned or len(cleaned) < 2:
                continue
            name = cleaned  # 用清洗后的名字

            # 2. 用 stock_names.json 验证名字合法性（兜底）
            _sn_path = os.path.join(os.path.dirname(__file__), "data", "stock_names.json")
            _name_index = []
            if os.path.exists(_sn_path):
                try:
                    with open(_sn_path, "r", encoding="utf-8") as _f:
                        _name_index = json.load(_f)
                except:
                    pass
            if len(name) > 6 and _name_index:
                # 从尾部截取已知的股票名
                found = False
                for known in _name_index:
                    if isinstance(known, (list, tuple)) and len(known) > 0:
                        kn = known[0]
                        if kn and kn in name:
                            name = kn
                            found = True
                            break
                    elif isinstance(known, str) and known in name:
                        name = known
                        found = True
                        break
                if not found:
                    # 多次清洗无果，弃用该条目防止污染扩散
                    continue
            if full not in seen_codes and name not in seen_names:
                seen_codes.add(full)
                seen_names.add(name)
                results.append({
                    "name": resolve_guanlan_name(code, exchange, name),
                    "code": code,
                    "full_code": full,
                    "exchange": exchange,
                    "market": market,
                })

    # ── 阶段3: 名字反查（只写名字没写代码）──
    if name_index:
        # 虚词/连词前缀黑名单（避免"其中金茂"、"包括XX"这类误匹配）
        _grammar_words = frozenset(
            "其中包括以及此外例如如下对于关于除了通过根据"
            "另外还有如果因为但是然而因此由于或者虽然"
            "这那该上其内个"
        )
        for nm, code, fc, exch, market in name_index:
            if len(nm) < 2:
                continue
            if nm in seen_names:
                continue
            idx = text.find(nm)
            if idx == -1:
                continue
            # ── 单词边界检查：名字前面如果是完整虚词则跳过 ──
            if idx > 0:
                # 检查前2个字是否构成虚词（覆盖"其中"、"包括"等）
                before = text[max(0, idx - 2):idx]
                if before in _grammar_words or (idx > 1 and text[idx - 1] in _grammar_words):
                    continue
            hint = detect_exchange_hint(text, idx + len(nm))
            if fc not in seen_codes:
                seen_codes.add(fc)
                seen_names.add(nm)
                entry = {
                    "name": nm,
                    "code": code,
                    "full_code": fc,
                    "exchange": exch,
                    "market": market,
                }
                if hint == "HK":
                    entry["hk_hint"] = True
                results.append(entry)
    return results


def detect_institution(text):
    for kw in INSTITUTION_KEYWORDS:
        if kw in text[:300]:
            return kw
    return "未知机构"


def detect_rating(text):
    for kw, rating in RATING_MAP.items():
        if kw in text:
            return rating
    return "未评级"


def parse_api_time(time_str):
    """解析 ISO 时间字符串为 YYYY-MM-DD"""
    # 2026-07-07T09:01:00.040+0800
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", time_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return datetime.now().strftime("%Y-%m-%d")


def process_group(key, config, token):
    """处理单个星球: API抓取 → 解析 → 写文件

    返回: (reports_list, watch_stocks_dict)
    """
    name = config["name"]
    group_id = config["group_id"]
    out_path = config["out_reports"]

    print(f"\n  ── {name} ({group_id}) ──")

    # 1. API 抓取
    topics = api_fetch_topics(group_id, token, count=20)
    print(f"  ✓ API 获取帖子: {len(topics)} 条")

    if not topics:
        print(f"  ⚠️ {name} 无数据（可能 token 过期或未加入该星球）")
        return [], {}

    dates = []
    # 2. 解析研报
    reports = []
    watch_stocks = {}
    for t in topics:
        talk = t.get("talk", {})
        text = talk.get("text", "")
        if not text or len(text) < 20:
            continue

        author = talk.get("owner", {}).get("name", "")
        create_time = t.get("create_time", "")
        date = parse_api_time(create_time)
        dates.append(date)

        inst = detect_institution(text)
        rating = detect_rating(text)
        stocks = parse_stock_codes(text, NAME_INDEX)

        # 有股票的才算研报
        if not stocks and inst == "未知机构":
            continue

        reports.append({
            "institution": inst,
            "rating": rating,
            "date": date,
            "stocks": stocks,
            "topic_id": t.get("topic_id", ""),
            "author": author,
            "source": name,  # 标注来源星球
            "raw_text": text[:2000],
            "create_time": create_time,
        })
        # 入推股池
        for s in stocks:
            watch_stocks[s["full_code"]] = {
                "name": s["name"],
                "code": s["code"],
                "full_code": s["full_code"],
                "exchange": s["exchange"],
                "market": s["market"],
                "institution": inst,
                "rating": rating,
                "source": name,
                "added_date": date,
            }

    # 排序：按日期降序
    reports.sort(key=lambda r: r.get("create_time", ""), reverse=True)

    # 3. 写文件（包装为对象，带 update_time，供前端状态表读取）
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out_obj = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(reports),
        "date_range": f"{min(dates)} ~ {max(dates)}" if dates else "?",
        "reports": reports,
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)

    date_range = out_obj["date_range"]
    print(f"  ✓ 研报(含股票): {len(reports)} 条 | 日期: {date_range}")
    print(f"  ✓ 推股池新增: {len(watch_stocks)} 只")
    print(f"  ✓ 已保存: {os.path.basename(out_path)}")

    return reports, watch_stocks


def main():
    print("=== 知识星球研报提取 (guanlan_extractor) ===")
    print("   模式: API优先 | 星球: 观澜台\n")

    # 构建股票名索引（用于只写名字没写代码的研报反查）
    global NAME_INDEX
    NAME_INDEX = build_name_index()
    print(f"  ▸ 股票名索引: {len(NAME_INDEX)} 只")

    token = load_token()
    if not token:
        print("❌ 无有效 token，退出")
        return 1

    all_watch = {}  # 合并推股池
    total_reports = 0

    for key, config in GROUPS.items():
        try:
            reps, watches = process_group(key, config, token)
            total_reports += len(reps)
            all_watch.update(watches)  # 观澜台股票入推股池
        except Exception as e:
            print(f"  [ERR] {config['name']} 处理异常: {e}")

    # 写合并推股池
    watchlist = {
        "version": "2.0",
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sources": list(GROUPS.keys()),
        "total": len(all_watch),
        "stocks": list(all_watch.values()),
    }
    os.makedirs(os.path.dirname(WATCHLIST_OUT), exist_ok=True)
    with open(WATCHLIST_OUT, "w", encoding="utf-8") as f:
        json.dump(watchlist, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ 总计: {total_reports} 条研报告, {len(all_watch)} 只推股")
    print(f"   {WATCHLIST_OUT}")
    for key, cfg in GROUPS.items():
        print(f"   {cfg['out_reports']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
