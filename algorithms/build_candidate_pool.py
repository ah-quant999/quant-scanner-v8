# -*- coding: utf-8 -*-
"""
构建「候选股池」(candidate_pool.json)
====================================
股池 = 主板成交前100 + 创业板成交前100 + 科创板成交前100 + 港股成交前50
      + 观澜台(自选+研报) + mahoro研报
后续金股池 = 股池 ∩ (信号共振≥2 或 研报来源)，见 scanner.py。

数据源（生产健壮）：
  A股：stock_zh_a_spot_em(东财) → stock_zh_a_spot(新浪) 回退
  港股：stock_hk_spot_em(东财) → stock_hk_spot(新浪) 回退
  观澜台 / mahoro：直接读 data/*.json（已每日更新）
任一行情源失败不致命，其余层继续构建。
"""
import os

try:
    _ = BASE
except NameError:
    BASE = os.path.dirname(os.path.abspath(__file__))
import json
import re
import sys
import time
import threading
import gc
import datetime

# 名称归一化共享模块（2026-08-14 抽出，消除与 final_recommend/guanlan_extractor/scanner 的重复）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from name_utils import strip_entitlement_prefix  # noqa: E402
try:
    import akshare as ak
except ModuleNotFoundError:
    ak = None
try:
    import requests as _requests
except ModuleNotFoundError:
    _requests = None

# ════════════════════════════════════════════════════════════════
# 云端数据源：GitHub Actions 美区 runner 无法访问 akshare/东财/BaoStock，
# 改走腾讯 GTimg（实时行情 + 前复权日K）。本地双机仍用 mootdx/akshare。
# ════════════════════════════════════════════════════════════════
_IG = None
def _gtimg():
    global _IG
    if _IG is None:
        import data_source_gtimg as _IG
    return _IG

def _is_cloud():
    try:
        return _gtimg().is_cloud_runner()
    except Exception:
        return os.environ.get("GITHUB_ACTIONS", "").lower() == "true" or \
               os.environ.get("CLOUD_RUNNER", "").lower() == "true"

# ════════════════════════════════════════════════════════════════
# 给 akshare HTTP 底层加默认连接/读取超时，根治家用机网络层卡死
# ════════════════════════════════════════════════════════════════
# akshare 内部直接调 requests.get/post 但不传 timeout，家用机 WiFi 丢包时会
# 永久挂起且无法被 batch_update.py 的进程级超时捕获。此处 monkey-patch
# requests.Session.request，在未显式指定 timeout 时注入 (15,60)。
if _requests is not None:
    _ORIG_SESSION_REQUEST = _requests.Session.request

    def _session_request_with_timeout(self, method, url, **kwargs):
        if kwargs.get("timeout") is None:
            kwargs["timeout"] = (15, 60)  # (connect, read)
        return _ORIG_SESSION_REQUEST(self, method, url, **kwargs)

    _requests.Session.request = _session_request_with_timeout

# 2026-08-09 修复：优先用 V8_OUT_DIR（run_algorithms 注入 = 与 guanlan_extractor 写入同目录），消除任何「脚本写 out/A、本脚本读 out/B」的口径偏差。
# 兜底才用 algorithms/../out（与 guanlan 的 BASE/../out 等价）。
_DATA_FALLBACK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
DATA = os.environ.get("V8_OUT_DIR") or _DATA_FALLBACK
OUT = os.path.join(DATA, "candidate_pool.json")
# #14 解耦：慢变成员表（独立于每日指标，hysteresis 防抖）
#   - out/ 为工作副本；raw_data/ 为持久副本（云端工作流会 git add raw_data/ 入库，
#     保证跨云端 runner 运行 hysteresis 不失效）。
MEMBERS_OUT = os.path.join(DATA, "candidate_members.json")
MEMBERS_RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "raw_data", "candidate_members.json")
MEMBER_HYSTERESIS_DAYS = 5   # 掉出成交额前N后仍保留的交易日数（防每日 churn）

# ════════════════════════════════════════════════════════════════
# mootdx TrafficStatSocket 泄漏长期修复：
# client.quotes()/stocks() 不释放底层 socket，约 170 次调用后触发
# Windows 进程终止。方案：每 50 次调用主动 close+gc+重建，并加线程锁。
# ════════════════════════════════════════════════════════════════
_TDX_LOCK = threading.Lock()
_TDX_MAX_CALLS = 50

# ════════════════════════════════════════════════════════════════
# 干净名字解析（根治观澜台研报把新闻稿当股票名的污染）
# 优先级: 东财 f58(云端权威, 可纠正 stock_names/mootdx 错名)
#        > stock_names.json(A股本地权威, 含个别校正)
#        > 原始名(若看起来干净) > 代码兜底(绝不输出新闻稿/指数垃圾)
# ════════════════════════════════════════════════════════════════
STOCK_NAMES_FILE = os.path.join(DATA, "stock_names.json")

_EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://quote.eastmoney.com/",
}
_EM_NAME_CACHE = {}
_SN_MAP = None
# 注: 不在此硬编码个别校正——股票名以 东财 f58(云端/本机均可达) 为权威,
#      stock_names.json 作为本地兜底。任何"疑似错名"须联网核实后再动, 严禁凭记忆改。

_GARBAGE_KW = ['我们', '看好', '完成', '通过', '闪电', '带动', '新增', '包括',
               '给予', '推荐', '关注', '建议', '认为', '预计', '有望', '中标',
               '签订', '取得', '获得', '基石', '其中', '以及', '此外', '例如',
               '如下', '对于', '关于', '除了', '根据', '也']
# 注: '有限公司'/'股份有限' 不作垃圾词——合法名常带此后缀, 由 _norm_name 剥离;
#     真正污染是新闻句式(我们/看好/完成/闪电...), 已被 _GARBAGE_KW 覆盖。


def _stock_names_map():
    global _SN_MAP
    if _SN_MAP is not None:
        return _SN_MAP
    _SN_MAP = {}
    try:
        with open(STOCK_NAMES_FILE, "r", encoding="utf-8") as f:
            for s in json.load(f):
                c = (s.get("code") or "").strip()
                n = (s.get("name") or "").strip()
                if c and n:
                    _SN_MAP[c.zfill(6)] = n
    except Exception:
        pass
    return _SN_MAP


def _em_secid(code, market):
    c = str(code)
    if market == "hk" or (c.isdigit() and len(c) <= 5):
        return "116." + c.zfill(5)
    if c.startswith(("6", "9")):
        return "1." + c.zfill(6)
    if c.startswith(("0", "3", "2", "8")):
        return "0." + c.zfill(6)
    return None


def _em_name(code, market):
    """云端 runner 不走东财 HTTP（避免 60s 超时），直接返回 None。"""
    if _is_cloud():
        return None
    key = f"{market}_{code}"
    if key in _EM_NAME_CACHE:
        return _EM_NAME_CACHE[key]
    _EM_NAME_CACHE[key] = None
    secid = _em_secid(code, market)
    if not secid:
        return None
    # 快速失败: 东财 push2 偶发不可达(如 RemoteDisconnected)时立即返回 None,
    # 名称回退 stock_names.json / 行情原始名。原 3 次重试 + 0.8s 休眠会让 300 只
    # 股票的解析拖到 ~570s, 远超看门狗 300s 超时被杀, 导致候选池永不刷新。
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
    """去除权/新股前缀、全角字母、有限公司/括号后缀。"""
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


def resolve_clean_name(code, market, raw_name):
    """返回干净股票名(见文件头优先级说明)。"""
    em = _em_name(code, market)          # 云端权威
    if em:
        return _norm_name(em)
    c = str(code).zfill(6)
    snm = _stock_names_map().get(c)
    if market != "hk" and snm:           # A股本地权威
        return _norm_name(snm)
    if _looks_clean(raw_name):           # 原始名若干净则采用
        return _norm_name(raw_name)
    return str(code).strip()             # 兜底代码(不出垃圾)

TOP_PER_BOARD = 100   # 主板/创业板/科创板 各取成交额前 N
HK_TOP = 50           # 港股取成交额前 N

# 港股精选代码池：HSI 蓝筹 + 港股通权重（稳定不易老化），用于 GTimg 批量行情兜底。
# 2026-08-11 替代方案：akshare 港股双接口（stock_hk_spot / stock_hk_spot_em）在本机与云端均不可达，
# 东财 clist 列表接口也不可达 → 改用「自有代码池 + GTimg 单票批量行情」（qt.gtimg.cn 双环境可达）。
# 运行时 GTimg 对无效代码自动跳过（无 name/价格为 0 即丢弃），故少量代码偏差不会引发崩溃或脏数据。
HK_UNIVERSE = [
    "00700","09988","03690","01810","01299","00939","01398","03988","01658",
    "03968","01288","01988","02318","02628","01339","02601","06030","00998",
    "00941","00728","00762","00005","00011","02388","01024","09888","09999",
    "09618","09626","02015","09866","09868","02020","02331","02313","01929",
    "01109","00688","03311","00960","02007","00823","00001","00002","00003",
    "00066","01038","01997","00027","01928","00267","00291","00241","01833",
    "06618","02400","00268","01787","02899","03993","01772","01347","00981",
    "01801","02269","02359","01177","01093","03692","01530","06160","00883",
    "00857","00386","01088","01171","02380","00956","01250","01898","00168",
    "00016","00012","00101","00868","03606","02382","02018","00285","06060",
    "01336","02202","02777","01918","06862","03898","01877","02196","00347",
    "00921","06099","06881","00390","01186","00902","09633","09987","06690",
    "06969","09966","02039","06178","09961","06826","01772","01579","01810",
]


# ---------- 行情抓取（带回退） ----------
def _a_share_spot_mootdx():
    """mootdx(通达信直连) 取全市场A股实时行情，按成交额排序。

    已修复 TrafficStatSocket 泄漏：
      - 加 _TDX_LOCK 线程互斥，防止双任务并发创建多个 client
      - 每 50 次 client.quotes() 调用后主动 close + gc.collect() + 重建 client
    失败时返回 None，调用方自动回退到 akshare 兜底。
    """
    with _TDX_LOCK:
        try:
            import socket as _sock
            # 根治 mootdx 在 TDX 服务器不可达时无限挂起（其 TrafficStatSocket
            # 不设超时，会永久阻塞且无法被进程级超时捕获，导致候选池永不刷新）。
            # 设默认超时后，连接/读取超时会抛异常 → 被 except 捕获 → 自动回退 akshare。
            _sock.setdefaulttimeout(30)
            from mootdx.quotes import Quotes
            import pandas as pd
            t = time.time()
            client = Quotes.factory(market='std')
            BOARD_PREFIXES = ('600', '601', '603', '605', '688',
                              '000', '001', '002', '003', '300', '301')
            NAME_EXCLUDE = ('指数', 'Ａ股', 'Ｂ股', '基金', 'ETF', '债券', '转债', '回购')
            rows = []
            call_count = 0
            for market_id in (1, 0):
                all_stocks = client.stocks(market=market_id)
                if all_stocks is None or len(all_stocks) == 0:
                    continue
                target_codes, target_names = [], {}
                for _, r in all_stocks.iterrows():
                    code = str(r['code']).zfill(6)
                    name = str(r.get('name', '')).replace('\x00', '').strip()
                    if not any(code.startswith(p) for p in BOARD_PREFIXES):
                        continue
                    if name and name.startswith(('N', 'ST', '*ST', '退')):
                        continue
                    if any(x in name for x in NAME_EXCLUDE):
                        continue
                    target_codes.append(code)
                    target_names[code] = name
                qparts = []
                for i in range(0, len(target_codes), 80):
                    batch = target_codes[i:i + 80]
                    try:
                        q = client.quotes(symbol=batch)
                        call_count += 1
                        if q is not None and len(q) > 0:
                            qparts.append(q)
                    except Exception:
                        continue
                    # 每 50 次 quotes 调用重置 client，根治 TrafficStatSocket 泄漏
                    if call_count >= _TDX_MAX_CALLS:
                        try:
                            client.close()
                        except Exception:
                            pass
                        client = None
                        gc.collect()
                        client = Quotes.factory(market='std')
                        call_count = 0
                    time.sleep(0.05)
                if not qparts:
                    continue
                qdf = pd.concat(qparts, ignore_index=True)
                qdf = qdf[qdf['price'] > 0].copy()
                for _, r in qdf.iterrows():
                    code = str(r['code']).zfill(6)
                    name = target_names.get(code, '')
                    if not name or name == code:
                        continue
                    rows.append({'代码': code, '名称': name,
                                 '成交额': float(r.get('amount', 0) or 0)})
            try:
                if client is not None:
                    client.close()
            except Exception:
                pass
            client = None
            gc.collect()
            if not rows:
                return None
            df = pd.DataFrame(rows)
            print(f"  [A股-mootdx] OK 行数={len(df)} {time.time() - t:.1f}s")
            return df
        except Exception as e:
            print(f"  [A股-mootdx] 失败: {type(e).__name__} {str(e)[:60]}")
            return None


def _a_share_spot_gtimg():
    """GTimg 新浪活跃股排行兜底：返回 DataFrame(代码/名称/成交额/_b)。

    适用场景：mootdx/akshare 均失败时（家用机网络异常或云端美区 runner）。
    新浪排行按成交额排序，取主板/创业板/科创板各前 N 只，足以支撑候选池构建。
    """
    try:
        t = time.time()
        import pandas as pd
        ig = _gtimg()
        rows = ig.fetch_volume_top_stocks_gtimg(TOP_PER_BOARD, TOP_PER_BOARD, TOP_PER_BOARD, 0)
        if not rows:
            return None
        df_rows = []
        for r in rows:
            code, name, market, board = r[0], r[1], r[2], r[3]
            df_rows.append({"代码": code, "名称": name, "成交额": 0.0, "_b": board})
        df = pd.DataFrame(df_rows)
        print(f"  [A股-GTimg] OK 行数={len(df)} {time.time()-t:.1f}s")
        return df
    except Exception as e:
        print(f"  [A股-GTimg] 失败: {type(e).__name__} {str(e)[:80]}")
        return None


def _a_share_spot():
    """A股行情获取：本地 mootdx → akshare → GTimg；云端 GTimg → akshare。"""
    # 0) 本地 runner：mootdx 优先（本机实测 22s/5000+只，稳定）
    if not _is_cloud() and not os.environ.get("SKIP_MOOTDX"):
        df = _a_share_spot_mootdx()
        if df is not None and len(df):
            return df
    else:
        print("  [A股] 云端/SKIP_MOOTDX，跳过 mootdx")

    # 1) 云端 runner：GTimg 优先（美区网络 mootdx/akshare 均不可靠）
    if _is_cloud():
        df = _a_share_spot_gtimg()
        if df is not None and len(df):
            return df

    # 2) akshare 兜底（外部网络可达场景）
    if ak is not None:
        print("  [A股] 尝试 akshare...")
        for fn in (ak.stock_zh_a_spot, ak.stock_zh_a_spot_em):
            try:
                t = time.time()
                df = fn()
                if df is not None and len(df):
                    print(f"  [A股] {fn.__name__} OK 行数={len(df)} {time.time()-t:.1f}s")
                    return df
            except Exception as e:
                print(f"  [A股] {fn.__name__} 失败: {type(e).__name__} {str(e)[:60]}")
                time.sleep(2)
    else:
        print("  [A股] akshare 未安装，跳过 akshare 兜底")

    # 3) 最终兜底：GTimg 新浪排行（本地+云端通用，不依赖 akshare）
    print("  [A股] 尝试 GTimg 新浪排行最终兜底...")
    return _a_share_spot_gtimg()


def _hk_spot_gtimg():
    """GTimg 港股批量行情兜底（akshare 不可达时启用）。

    用自带精选港股代码池（HK_UNIVERSE：HSI 蓝筹 + 港股通权重，稳定不易老化）批量拉
    qt.gtimg.cn 单票行情，按 成交额 = 现价 × 成交量 排序取前 HK_TOP。
    GTimg 在本机与云端美区 runner 均可达（与 A股 gtimg 兜底同源）；无效代码会被自动跳过。
    """
    try:
        import pandas as pd
        import urllib.request, ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        codes = sorted(set(HK_UNIVERSE))
        rows = []
        for i in range(0, len(codes), 80):
            batch = codes[i:i + 80]
            q = "https://qt.gtimg.cn/q=" + ",".join("hk" + c for c in batch)
            try:
                req = urllib.request.Request(q, headers={
                    "User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
                b = urllib.request.urlopen(req, timeout=12, context=ctx).read().decode("gbk", "ignore")
            except Exception as e:
                print(f"  [港股-GTimg] 批次失败: {type(e).__name__} {str(e)[:60]}")
                continue
            for line in b.split(";"):
                line = line.strip()
                if not line.startswith("v_hk"):
                    continue
                try:
                    code = line[2:line.index("=")]
                    payload = line[line.index('"') + 1:line.rindex('"')]
                    f = payload.split("~")
                    name = f[1]
                    price = float(f[3]) if len(f) > 3 and f[3] else 0.0
                    vol = float(f[6]) if len(f) > 6 and f[6] else 0.0
                    if not name or price <= 0 or vol <= 0:
                        continue
                    rows.append({"代码": code, "名称": name, "成交额": price * vol})
                except Exception:
                    continue
        if not rows:
            print("  [港股-GTimg] 无有效数据")
            return None
        df = pd.DataFrame(rows)
        print(f"  [港股-GTimg] OK 行数={len(df)}")
        return df
    except Exception as e:
        print(f"  [港股-GTimg] 失败: {type(e).__name__} {str(e)[:60]}")
        return None


def _hk_spot():
    # 1) akshare（本地可达时优先）：新浪 stock_hk_spot → 东财 stock_hk_spot_em
    if ak is not None:
        for fn in (ak.stock_hk_spot, ak.stock_hk_spot_em):
            try:
                t = time.time()
                df = fn()
                if df is not None and len(df):
                    print(f"  [港股] {fn.__name__} OK 行数={len(df)} {time.time()-t:.1f}s")
                    return df
            except Exception as e:
                print(f"  [港股] {fn.__name__} 失败: {type(e).__name__} {str(e)[:60]}")
                time.sleep(2)
    # 2) GTimg 批量行情兜底（双环境可达，akshare 不可达时主力路径）
    df = _hk_spot_gtimg()
    if df is not None and len(df):
        return df
    # GTimg 暂无港股成交额排行接口；港股缺失不阻断 A股候选池
    print("  [港股] 无可用数据源，本次跳过港股层")
    return None



def _hk_from_goldpool(limit, add):
    """从 gold_pool.json 港股板块补入候选池（akshare 不可达时的兜底）。

    🔴 2026-08-13 用户指令：禁止无条件补入港股。
    原因：gold_pool 满港股时，兜底会把候选池全部刷成港股，遮蔽 A 股候选。
    保留该函数仅供并发 HK_TOP-only 单独跑批时显式调用（极少见）。
    普通流水线里请走 akshare 主源；akshare 失败时空也优于错港股。
    """
    return  # 🚫 已禁用无条件兜底，避免 A 股候选池被港股刷屏
    gp_path = os.path.join(DATA, "gold_pool.json")
    if not os.path.isfile(gp_path):
        print("  [港股兜底] gold_pool.json 不存在，跳过")
        return
    try:
        with open(gp_path, "r", encoding="utf-8") as f:
            gp = json.load(f)
    except Exception as e:
        print(f"  [港股兜底] 读取失败: {e}")
        return

    hk_stocks = []
    for k, v in gp.get("stocks", {}).items():
        if v.get("board_label") == "港股" or v.get("market") == "hk":
            code = str(v.get("code", "")).strip()
            name = str(v.get("name", "")).strip()
            if code and name:
                hk_stocks.append((code, name))

    if not hk_stocks:
        print("  [港股兜底] gold_pool 中无港股板块数据")
        return

    count = 0
    for code, name in hk_stocks[:limit]:
        raw = "".join(ch for ch in code if ch.isdigit()).zfill(5)
        if raw:
            add(f"hk_{raw}", raw, name, "hk", "港股", f"港股gold_pool前{limit}")
            count += 1

    print(f"  [港股兜底] 从 gold_pool 补入 {count} 只（共{len(hk_stocks)}只候选）")


# ---------- 工具 ----------
def _enrich_industry_concepts(pool):
    """为候选股池补充 industry / concepts / board 字段。

    优先用本地静态映射 algorithms/stock_industry_concepts.json（由 v6 industry_map.json
    归一化生成，云端可达、不依赖 akshare/东财）；缺失项在本地（非云端）用 akshare
    单股查询补充，云端跳过 akshare 以免卡死。
    失败不阻断主流程，仅打印日志。
    """
    if not pool:
        return
    # 1) 静态映射（主来源，云端安全）
    meta_path = os.path.join(os.path.dirname(__file__), "stock_industry_concepts.json")
    meta_map = {}
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta_map = json.load(f)
    except Exception:
        meta_map = {}
    ok = skip = 0
    for key, st in pool.items():
        code = str(st.get("code", "")).strip()
        market = st.get("market", "")
        # 仅 A 股主板/创业板/科创板；港股/北交所/指数跳过
        if market not in ("sh", "sz") or not code.isdigit() or len(code) != 6:
            skip += 1
            continue
        m = meta_map.get(code) or {}
        if m.get("industry"):
            st["industry"] = m["industry"]
        if m.get("concepts"):
            st["concepts"] = m["concepts"]
        if "board" not in st or not st.get("board"):
            st["board"] = m.get("board") or st.get("board_label") or _board_of_a(code) or ""
        if m:
            ok += 1
    print(f"  [行业/概念] 静态映射补充：命中 {ok}，跳过 {skip}")

    # 2) 本地 akshare 兜底（仅非云端，填补静态映射缺口，限制数量防超时）
    if _is_cloud():
        return
    missing = [k for k, st in pool.items()
               if st.get("market") in ("sh", "sz") and not st.get("industry")]
    if not missing:
        return
    try:
        import akshare as ak
    except Exception as e:
        print(f"  [行业/概念] akshare 不可用，跳过兜底: {e}")
        return
    ak_ok = ak_fail = 0
    for key in missing[:200]:
        st = pool[key]
        code = str(st.get("code", "")).strip()
        try:
            df = ak.stock_individual_info_em(symbol=code)
            if df is None or df.empty:
                ak_fail += 1
                continue
            kv = {}
            for _, row in df.iterrows():
                item = str(row.get("item", "")).strip()
                value = str(row.get("value", "")).strip()
                if item:
                    kv[item] = value
            industry = kv.get("所属行业") or kv.get("行业") or ""
            concepts = kv.get("所属概念") or kv.get("概念") or ""
            if industry:
                st["industry"] = industry
            if concepts:
                st["concepts"] = [c.strip() for c in concepts.split(",") if c.strip()]
            if "board" not in st or not st.get("board"):
                st["board"] = st.get("board_label") or _board_of_a(code) or ""
            ak_ok += 1
        except Exception:
            ak_fail += 1
    print(f"  [行业/概念] akshare 兜底：成功 {ak_ok}，失败 {ak_fail}")


def _board_of_a(code):
    """A股代码 → 上市板（兼容 sh600000 / 600000.SH / 600000 等格式）"""
    c = str(code).strip().upper()
    c = c.split(".")[0]                      # 去掉 .SH/.SZ 后缀
    c = "".join(ch for ch in c if ch.isdigit())  # 去掉 sh/sz 等前缀，仅留数字
    if not c:
        return None
    if c.startswith(("600", "601", "603", "605")):
        return "主板"
    if c.startswith(("000", "001", "002", "003")):
        return "主板"
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith(("688", "689")):
        return "科创板"
    if c.startswith(("8", "4", "92")):
        return "北交所"
    return None


def _norm(code, name, market_raw, full_code):
    """统一成 (code6/5位, name, market, board_label)"""
    code = str(code).strip()
    fc = str(full_code or "")
    if market_raw == "港股" or ".HK" in fc.upper() or (code.isdigit() and len(code) <= 5 and market_raw != "A股"):
        code = code.zfill(5)
        return code, name, "hk", "港股"
    code = code.zfill(6)
    if code.startswith("6"):
        market, board = "sh", ("科创板" if code.startswith(("688", "689")) else "主板")
    elif code.startswith("3"):
        market, board = "sz", "创业板"
    elif code.startswith(("0", "2")):
        market, board = "sz", "主板"
    else:
        market, board = "sh", ""
    return code, name, market, board


    t = str(ticker).strip().upper()
    if ".HK" in t:
        code = t.split(".HK")[0].zfill(5)
        return code, "hk", "港股"
    if ".SS" in t:
        return t.split(".SS")[0].zfill(6), "sh", "主板"
    if ".SZ" in t:
        return t.split(".SZ")[0].zfill(6), "sz", "创业板" if t.startswith("3") else "主板"
    # 纯数字
    if t.isdigit():
        if len(t) <= 5:
            return t.zfill(5), "hk", "港股"
        return t.zfill(6), ("sh" if t.startswith("6") else "sz"), ""
    return None


# ---------- 候选池解耦（#14）：慢变成员表 + 快变每日指标 ----------
def _fetch_price_amount_gtimg(codes):
    """批量取现价/成交额（仅用确认安全的 f[3]=现价、f[6]=成交量 字段），用于补全
    历史留存成员的当日指标。失败返回空 dict（非致命）。qt.gtimg.cn 本机+云端双环境可达。"""
    if not codes:
        return {}
    import urllib.request, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    out = {}
    for i in range(0, len(codes), 80):
        batch = codes[i:i + 80]
        q = "https://qt.gtimg.cn/q=" + ",".join(batch)
        try:
            req = urllib.request.Request(q, headers={
                "User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
            b = urllib.request.urlopen(req, timeout=12, context=ctx).read().decode("gbk", "ignore")
        except Exception as e:
            print(f"  [指标-GTimg] 批次失败: {type(e).__name__} {str(e)[:60]}")
            continue
        for line in b.split(";"):
            line = line.strip()
            if not line.startswith("v_"):
                continue
            try:
                code = line[2:line.index("=")]
                payload = line[line.index('"') + 1:line.rindex('"')]
                f = payload.split("~")
                price = float(f[3]) if len(f) > 3 and f[3] else 0.0
                vol = float(f[6]) if len(f) > 6 and f[6] else 0.0
                out[code] = {"price": price, "amount": price * vol}
            except Exception:
                continue
    print(f"  [指标-GTimg] 取到 {len(out)}/{len(codes)} 只现价/成交额")
    return out


def _merge_membership(today, prev, hyst_days, today_date):
    """慢变成员表合并：今日派生集合 ∪ 历史成员(hysteresis 防抖)。

    - 今日出现的成员：采用今日数据，更新 last_seen=today。
    - 今日未出现但历史在册的成员：
        * 来源含「观澜台」(自选/研报) → 永久保留(pinned)；
        * 否则若在 hyst_days 内曾出现 → 保留（防单日成交额排名抖动 churn）；
        * 否则 → 剔除（真正退出活跃区）。
    - 首次运行(prev 为空) → 成员 = 今日集合。
    """
    members = {}
    for k, v in today.items():
        e = dict(v)
        e["first_seen"] = (prev.get(k) or {}).get("first_seen") or today_date
        e["last_seen"] = today_date
        members[k] = e
    for k, v in prev.items():
        if k in members:
            continue
        last = v.get("last_seen") or ""
        pinned = any(s == "观澜台" for s in v.get("sources", []))
        days_gone = 999
        if last:
            try:
                days_gone = (datetime.date.fromisoformat(today_date) -
                             datetime.date.fromisoformat(last)).days
            except Exception:
                days_gone = 999
        if pinned or days_gone <= hyst_days:
            e = dict(v)
            e.pop("_today", None)
            members[k] = e
    return members


# ---------- 主构建 ----------
def build():
    pool = {}  # key -> {code,name,market,board_label,sources:[]}

    def add(key, code, name, market, board, source, metrics=None):
        if not key or not code:
            return
        # ★ 干净名字解析: 无论哪层(raw/研报/行情)传入的 name 都强制校正,
        #   杜绝观澜台研报把新闻稿当股票名污染候选池(根治点)
        clean = resolve_clean_name(code, market, name)
        if key in pool:
            if source not in pool[key]["sources"]:
                pool[key]["sources"].append(source)
            # 名字以更权威来源刷新(东财/stock_names 已在校正内统一)
            if clean and clean != pool[key]["code"]:
                pool[key]["name"] = clean
        else:
            pool[key] = {
                "code": code, "name": clean, "market": market,
                "board_label": board, "sources": [source],
                # 快变每日指标（#14）：成交额/现价/涨跌幅/量比，由调用方随行情一并传入
                "_metrics": metrics or {"price": 0.0, "pct_chg": 0.0,
                                       "volume_ratio": 0.0, "amount": 0.0},
            }

    # 1) A股 主板/创业板/科创板 各前100（按成交额）
    df = _a_share_spot()
    if df is not None:
        code_col = "代码" if "代码" in df.columns else df.columns[0]
        name_col = "名称" if "名称" in df.columns else df.columns[1]
        amt_cols = [c for c in df.columns if "成交额" in c or "amount" in c.lower()]
        price_col = next((c for c in df.columns if c in ("最新价", "price", "现价", "收盘")), None)
        pct_col = next((c for c in df.columns if c in ("涨跌幅", "pct_chg", "涨跌幅(%)", "changepct")), None)
        vr_col = next((c for c in df.columns if c in ("量比", "volume_ratio", "turnoverratio")), None)
        if amt_cols:
            amt = amt_cols[0]
            df = df.copy()
            df["_b"] = df[code_col].astype(str).map(_board_of_a)
            for b in ("主板", "创业板", "科创板"):
                sub = df[df["_b"] == b].sort_values(amt, ascending=False).head(TOP_PER_BOARD)
                for _, r in sub.iterrows():
                    raw = str(r[code_col]).strip().upper().split(".")[0]
                    raw = "".join(ch for ch in raw if ch.isdigit())
                    if not raw:
                        continue
                    c = raw.zfill(6)
                    mkt = "sh" if c.startswith("6") else "sz"
                    m = {
                        "amount": float(r[amt]) if amt in r and r[amt] is not None else 0.0,
                        "price": float(r[price_col]) if price_col and r.get(price_col) is not None else 0.0,
                        "pct_chg": float(r[pct_col]) if pct_col and r.get(pct_col) is not None else 0.0,
                        "volume_ratio": float(r[vr_col]) if vr_col and r.get(vr_col) is not None else 0.0,
                    }
                    add(f"{mkt}_{c}", c, r[name_col], mkt, b, f"{b}成交前{TOP_PER_BOARD}", metrics=m)
            print(f"  [A股] 主板/创业板/科创板 各前{TOP_PER_BOARD} 已并入")
        else:
            print("  [A股] 未找到成交额列，跳过")
    else:
        print("  [A股] 行情获取失败，跳过该层")

    # 2) 港股 前50（按成交额）
    hk = _hk_spot()
    if hk is not None:
        code_col = "代码" if "代码" in hk.columns else hk.columns[0]
        name_col = "名称" if "名称" in hk.columns else hk.columns[1]
        amt_cols = [c for c in hk.columns if "成交额" in c or "amount" in c.lower()]
        if amt_cols:
            amt = amt_cols[0]
            sub = hk.sort_values(amt, ascending=False).head(HK_TOP)
            for _, r in sub.iterrows():
                raw = str(r[code_col]).strip().upper().split(".")[0]
                raw = "".join(ch for ch in raw if ch.isdigit()).zfill(5)
                if not raw:
                    continue
                m = {"amount": float(r[amt]) if amt in r and r[amt] is not None else 0.0,
                     "price": 0.0, "pct_chg": 0.0, "volume_ratio": 0.0}
                add(f"hk_{raw}", raw, r[name_col], "hk", "港股", f"港股成交前{HK_TOP}", metrics=m)
            print(f"  [港股] 前{HK_TOP} 已并入（akshare实时）")
        else:
            print("  [港股] 未找到成交额列，跳过")
    else:
        # ── 兜底：从 gold_pool.json 港股板块补入 ──
        # akshare 在云端 runner 可能因网络/限速返回空（非安装问题），
        # 而 gold_pool 由算法链上游产出，含完整港股列表（board_label=港股）。
        _hk_from_goldpool(HK_TOP, add)

    # 3) 观澜台 自选
    try:
        wl_path = os.path.join(DATA, "guanlan_watchlist.json")
        wl = json.load(open(wl_path, encoding="utf-8"))
        for st in wl.get("stocks", []):
            code, name, mkt, board = _norm(st.get("code", ""), st.get("name", ""),
                                           st.get("market", ""), st.get("full_code", ""))
            if code:
                add(f"{mkt}_{code}", code, name, mkt, board, "观澜台")
        print(f"  [观澜台] 自选 {len(wl.get('stocks', []))} 只已并入")
    except FileNotFoundError:
        print(f"  [观澜台] 自选文件不存在（{os.path.join(DATA, 'guanlan_watchlist.json')}）"
              f"—— guanlan_extractor 可能未运行或 token 缺失")
    except Exception as e:
        print(f"  [观澜台] 自选读取失败: {e}")

    # 4) 观澜台 研报（合并入「观澜台」来源，不再单独计为「观澜台研报」——
    #     2026-08-10 确认研报61只与自选100%重叠，去重）
    try:
        rp = json.load(open(os.path.join(DATA, "guanlan_reports.json"), encoding="utf-8"))
        # 2026-08-09 修复：guanlan_extractor 产出的是
        # {update_time, count, date_range, reports:[...]}，
        # 原先直接 `for item in rp` 会遍历 dict 的键(str)，抛
        # "'str' object has no attribute 'get'" → 研报来源恒为 0 只。
        if isinstance(rp, dict):
            rp = rp.get("reports") or []
        n = 0
        for item in rp:
            for st in item.get("stocks", []):
                code, name, mkt, board = _norm(st.get("code", ""), st.get("name", ""),
                                               st.get("market", ""), st.get("full_code", ""))
                if code:
                    add(f"{mkt}_{code}", code, name, mkt, board, "观澜台")  # ← 合并入观澜台
                    n += 1
        print(f"  [观澜台] 研报个股 {n} 只已并入观澜台（去重）")
    except FileNotFoundError:
        print(f"  [观澜台] 研报文件不存在（{os.path.join(DATA, 'guanlan_reports.json')}）"
              f"—— guanlan_extractor 可能未运行或 token 缺失")
    except Exception as e:
        print(f"  [观澜台] 研报读取失败: {e}")


    # 补充行业 / 概念 / 板块元数据（用于个股查询展示）
    _enrich_industry_concepts(pool)

    # ── #14 解耦：慢变成员表（hysteresis 防抖） ──
    # 今日派生集合(pool) 仅代表「当日成交额前N」；若直接用作候选池，个股会随每日
    # 排名抖动而每日 churn。改为：并入历史成员表，掉出前N者仍保留
    # MEMBER_HYSTERESIS_DAYS 个交易日（观澜台来源永久保留），成员稳定后才交给下游扫描。
    today_date = time.strftime("%Y-%m-%d")
    prev_members = {}
    for _pp in (MEMBERS_RAW, MEMBERS_OUT):
        if os.path.exists(_pp):
            try:
                prev_members = json.load(open(_pp, encoding="utf-8")).get("stocks", {}) or {}
                if prev_members:
                    break
            except Exception:
                continue
    members = _merge_membership(pool, prev_members, MEMBER_HYSTERESIS_DAYS, today_date)

    # 汇总来源分布（基于慢变成员表）
    from collections import Counter
    dist = Counter()
    for v in members.values():
        for s in v["sources"]:
            dist[s] += 1
    out = {
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(members),
        "source_dist": dict(dist),
        "stocks": members,
    }
    # 🛡 2026-08-27 主人令（运维股池黄色根因）增强：
    #   今日任一 A股来源数量 < TOP_PER_BOARD*0.6 时，行情抓取不完整；
    #   把历史成员表中该板成员「视同今日出现」补回，杜绝缩水覆盖。
    try:
        _merged = 0
        for _b in ("主板", "创业板", "科创板"):
            _src = f"{_b}成交前{TOP_PER_BOARD}"
            if dist.get(_src, 0) < TOP_PER_BOARD * 0.6 and prev_members:
                for _k, _v in prev_members.items():
                    if _k in members:
                        continue
                    if _src not in (_v.get("sources") or []):
                        continue
                    members[_k] = {kk: _v.get(kk) for kk in
                                  ("code", "name", "market", "board_label", "sources",
                                   "first_seen", "last_seen", "metrics")}
                    _merged += 1
        if _merged:
            dist = Counter()
            for v in members.values():
                for s in v["sources"]:
                    dist[s] += 1
            print(f"  🛡 候选池数量不足保护：补回历史成员 {_merged} 只 → total={len(members)}")
    except Exception as e:
        print(f"  ⚠️ 候选池数量保护异常（继续）: {e}")
    # 6) 快变每日指标：今日成员用当日指标覆盖；历史留存成员 GTimg 补全现价/成交额（best-effort）
    _retain_codes = []
    for k, v in members.items():
        if "_metrics" in v:
            v["metrics"] = dict(v.pop("_metrics"))
            v["metrics"]["date"] = today_date
        else:
            c = v["code"]
            _retain_codes.append(("hk" + c) if v.get("market") == "hk"
                                 else (("sh" if c.startswith("6") else "sz") + c))
    if _retain_codes:
        try:
            _pa = _fetch_price_amount_gtimg(_retain_codes)
            for k, v in members.items():
                if "metrics" in v:
                    continue
                c = v["code"]
                gkey = ("hk" + c) if v.get("market") == "hk" else (("sh" if c.startswith("6") else "sz") + c)
                pa = _pa.get(gkey)
                if pa:
                    v["metrics"] = {"price": pa["price"], "pct_chg": 0.0,
                                    "volume_ratio": 0.0, "amount": pa["amount"], "date": today_date}
                else:
                    v["metrics"] = {"price": 0.0, "pct_chg": 0.0,
                                    "volume_ratio": 0.0, "amount": 0.0, "date": today_date}
        except Exception as e:
            print(f"  ⚠️ 留存成员指标补全失败（置零）: {e}")
            for k, v in members.items():
                if "metrics" not in v:
                    v["metrics"] = {"price": 0.0, "pct_chg": 0.0,
                                    "volume_ratio": 0.0, "amount": 0.0, "date": today_date}

    # 7) 落盘：慢变成员表（纯成员基线，不含每日指标）→ out/ + 持久 raw_data/
    _members_out = {
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(members),
        "hysteresis_days": MEMBER_HYSTERESIS_DAYS,
        "source_dist": dict(dist),
        "stocks": {k: {kk: vv for kk, vv in v.items() if kk not in ("metrics", "_metrics")}
                   for k, v in members.items()},
    }
    with open(MEMBERS_OUT, "w", encoding="utf-8") as f:
        json.dump(_members_out, f, ensure_ascii=False, indent=2)
    try:
        os.makedirs(os.path.dirname(MEMBERS_RAW), exist_ok=True)
        with open(MEMBERS_RAW, "w", encoding="utf-8") as f:
            json.dump(_members_out, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ 慢变成员表写 raw_data 失败（out 已写）: {e}")
    print(f"  ✅ 慢变成员表已写：{len(members)} 只 → candidate_members.json")

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 候选股池构建完成：{len(members)} 只")
    print("   来源分布:", dict(dist))
    # 2026-08-09 调试：把读取侧的真实状态落盘，便于云端 run 后核验
    # 「双源是否真的并入库」（step_run 吞掉了 stdout，CI 日志看不到内部打印）。
    try:
        import os as _os
        wl = _os.path.join(DATA, "guanlan_watchlist.json")
        rp = _os.path.join(DATA, "guanlan_reports.json")
        mh = _os.path.join(DATA, "mahoro_signals.json")
        def _cnt(p, key):
            if not _os.path.exists(p):
                return {"exists": False, "stocks": 0}
            try:
                d = json.load(open(p, encoding="utf-8"))
                if key == "stocks":
                    return {"exists": True, "stocks": len(d.get("stocks", []))}
                if key == "reports":
                    rps = d.get("reports", d if isinstance(d, list) else [])
                    return {"exists": True, "reports": len(rps),
                            "stocks_in_reports": sum(len(x.get("stocks", [])) for x in rps)}
                if key == "raw":
                    return {"exists": True,
                            "raw_signals": len(d.get("raw_signals", [])),
                            "gold_pool_matches": len(d.get("gold_pool_matches", []))}
            except Exception as e:
                return {"exists": True, "error": str(e)[:80]}
            return {"exists": True}
        dbg = {"DATA": DATA, "V8_OUT_DIR": _os.environ.get("V8_OUT_DIR", ""),
               "guanlan_watchlist": _cnt(wl, "stocks"),
               "guanlan_reports": _cnt(rp, "reports"),
               "source_dist": dict(dist)}
        # 同时写 raw_data/（api_push 会推送），便于云端 run 后经 API 取回核验
        _rd = _os.path.join(_os.path.dirname(DATA), "raw_data")
        try:
            _os.makedirs(_rd, exist_ok=True)
            with open(_os.path.join(_rd, "build_candidate_debug.json"), "w", encoding="utf-8") as f:
                json.dump(dbg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        with open(_os.path.join(DATA, "build_candidate_debug.json"), "w", encoding="utf-8") as f:
            json.dump(dbg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  [debug] 落盘失败: {e}")
    return out


if __name__ == "__main__":
    # 🛡 2026-08-20 主人令：算法一律云端算法链执行，本地禁止手动跑（护栏）
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from utils.time_gate import check_cloud_only
    if not check_cloud_only("algorithms/build_candidate_pool.py"):
        sys.exit(2)
    build()
