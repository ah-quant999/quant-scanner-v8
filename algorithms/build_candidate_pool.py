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
import time
import threading
import gc
import akshare as ak
import requests as _requests

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
_ORIG_SESSION_REQUEST = _requests.Session.request

def _session_request_with_timeout(self, method, url, **kwargs):
    if kwargs.get("timeout") is None:
        kwargs["timeout"] = (15, 60)  # (connect, read)
    return _ORIG_SESSION_REQUEST(self, method, url, **kwargs)

_requests.Session.request = _session_request_with_timeout

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "out")
OUT = os.path.join(DATA, "candidate_pool.json")

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
    s = re.sub(r'^(XD|XR|DR|N)', '', s)
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


def _a_share_spot():
    """A股行情获取：云端优先 GTimg → mootdx(通达信) → akshare(新浪/东财)兜底。"""
    # 0) 云端 runner：mootdx/akshare 在美区网络几乎不可用，直接走腾讯 GTimg
    if _is_cloud():
        try:
            t = time.time()
            ig = _gtimg()
            df = ig.fetch_gtimg_spot()
            if df is not None and len(df):
                # 转成本脚本统一格式：列名 代码/名称/成交额
                df = df.rename(columns={"当前价": "price"})
                print(f"  [A股] GTimg OK 行数={len(df)} {time.time()-t:.1f}s")
                return df
        except Exception as e:
            print(f"  [A股] GTimg 失败: {type(e).__name__} {str(e)[:80]}")

    # 1) mootdx 优先（本机实测 22s/5000+只，稳定）
    #    SKIP_MOOTDX=1 时强制跳过 mootdx 直走 akshare（诊断/网络异常时用）
    if os.environ.get("SKIP_MOOTDX"):
        df = None
        print("  [A股] SKIP_MOOTDX 已设，跳过 mootdx")
    else:
        df = _a_share_spot_mootdx()
    if df is not None and len(df):
        return df

    # 2) akshare 兜底（外部网络可达场景）
    print("  [A股] mootdx 失败，尝试 akshare...")
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
    return None


def _hk_spot():
    # 家用机：新浪优先（已验证可靠），东财居家网络常挂死靠后
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
    return None


# ---------- 工具 ----------
def _enrich_industry_concepts(pool):
    """为候选股池补充 industry / concepts / board 字段。

    使用 akshare.stock_individual_info_em 单股查询，港股/北交所未覆盖。
    失败不阻断主流程，仅打印日志。
    """
    if not pool:
        return
    # 云端 runner 数据链路不稳定，跳过行业概念补全以控制耗时
    if _is_cloud():
        print("  [行业/概念] 云端 runner 跳过")
        return
    try:
        import akshare as ak
    except Exception as e:
        print(f"  [行业/概念] akshare 不可用，跳过: {e}")
        return

    ok = 0
    fail = 0
    skip = 0
    for key, st in pool.items():
        code = str(st.get("code", "")).strip()
        market = st.get("market", "")
        # 仅 A 股主板/创业板/科创板；港股/北交所/指数跳过
        if market not in ("sh", "sz") or not code.isdigit() or len(code) != 6:
            skip += 1
            continue
        try:
            df = ak.stock_individual_info_em(symbol=code)
            if df is None or df.empty:
                fail += 1
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
            # board 字段：细化上市板（主/创/科）
            if "board" not in st or not st["board"]:
                st["board"] = st.get("board_label") or _board_of_a(code) or ""
            ok += 1
        except Exception as e:
            fail += 1
            if fail <= 5:
                print(f"  [行业/概念] {code} 失败: {e}")
    print(f"  [行业/概念] 补充完成：成功 {ok}，失败 {fail}，跳过 {skip}")


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
        market, board = "sh", ("科创板" if code.startswith("688") else "主板")
    elif code.startswith("3"):
        market, board = "sz", "创业板"
    elif code.startswith(("0", "2")):
        market, board = "sz", "主板"
    else:
        market, board = "sh", ""
    return code, name, market, board


def _mahoro_ticker(ticker):
    """'2359.HK' → ('02359','hk','港股'); '601872.SS' → ('601872','sh','主板')"""
    if not ticker:
        return None
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


# ---------- 主构建 ----------
def build():
    pool = {}  # key -> {code,name,market,board_label,sources:[]}

    def add(key, code, name, market, board, source):
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
            }

    # 1) A股 主板/创业板/科创板 各前100（按成交额）
    df = _a_share_spot()
    if df is not None:
        code_col = "代码" if "代码" in df.columns else df.columns[0]
        name_col = "名称" if "名称" in df.columns else df.columns[1]
        amt_cols = [c for c in df.columns if "成交额" in c or "amount" in c.lower()]
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
                    add(f"{mkt}_{c}", c, r[name_col], mkt, b, f"{b}成交前{TOP_PER_BOARD}")
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
                add(f"hk_{raw}", raw, r[name_col], "hk", "港股", f"港股成交前{HK_TOP}")
            print(f"  [港股] 前{HK_TOP} 已并入")
        else:
            print("  [港股] 未找到成交额列，跳过")
    else:
        print("  [港股] 行情获取失败，跳过该层（生产机将正常拉取）")

    # 3) 观澜台 自选
    try:
        wl = json.load(open(os.path.join(DATA, "guanlan_watchlist.json"), encoding="utf-8"))
        for st in wl.get("stocks", []):
            code, name, mkt, board = _norm(st.get("code", ""), st.get("name", ""),
                                           st.get("market", ""), st.get("full_code", ""))
            if code:
                add(f"{mkt}_{code}", code, name, mkt, board, "观澜台")
        print(f"  [观澜台] 自选 {len(wl.get('stocks', []))} 只已并入")
    except Exception as e:
        print(f"  [观澜台] 自选读取失败: {e}")

    # 4) 观澜台 研报
    try:
        rp = json.load(open(os.path.join(DATA, "guanlan_reports.json"), encoding="utf-8"))
        n = 0
        for item in rp:
            for st in item.get("stocks", []):
                code, name, mkt, board = _norm(st.get("code", ""), st.get("name", ""),
                                               st.get("market", ""), st.get("full_code", ""))
                if code:
                    add(f"{mkt}_{code}", code, name, mkt, board, "观澜台研报")
                    n += 1
        print(f"  [观澜台] 研报个股 {n} 只已并入")
    except Exception as e:
        print(f"  [观澜台] 研报读取失败: {e}")

    # 5) mahoro 研报
    try:
        mh = json.load(open(os.path.join(DATA, "mahoro_signals.json"), encoding="utf-8"))
        n = 0
        seen = set()
        for sig in mh.get("raw_signals", []):
            for co in sig.get("companies", []):
                t = _mahoro_ticker(co.get("ticker", ""))
                if not t:
                    continue
                code, mkt, board = t
                key = f"{mkt}_{code}"
                if key in seen:
                    continue
                seen.add(key)
                add(key, code, co.get("name", ""), mkt, board, "maharo研报")
                n += 1
        for gm in mh.get("gold_pool_matches", []):
            t = _mahoro_ticker(gm.get("code", ""))
            if not t:
                continue
            code, mkt, board = t
            key = f"{mkt}_{code}"
            if key in seen:
                continue
            seen.add(key)
            add(key, code, gm.get("name", ""), mkt, board, "maharo研报")
            n += 1
        print(f"  [maharo] 研报个股 {n} 只已并入")
    except Exception as e:
        print(f"  [maharo] 读取失败: {e}")

    # 补充行业 / 概念 / 板块元数据（用于个股查询展示）
    _enrich_industry_concepts(pool)

    # 汇总来源分布
    from collections import Counter
    dist = Counter()
    for v in pool.values():
        for s in v["sources"]:
            dist[s] += 1
    out = {
        "update_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(pool),
        "source_dist": dict(dist),
        "stocks": pool,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 候选股池构建完成：{len(pool)} 只")
    print("   来源分布:", dict(dist))
    return out


if __name__ == "__main__":
    build()
