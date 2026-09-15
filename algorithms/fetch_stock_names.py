#!/usr/bin/env python3
"""获取 A 股 + 港股 + ETF 全量股票名称列表（每周更新一次即可）

2026-08-13 修复：原脚本只产出 A 股，导致个股查询搜不到港股/ETF。
现加入：
  - ETF：akshare.fund_etf_spot_em() 全量 (~1500 只)
  - 港股：akshare.stock_hk_spot() 新浪接口优先，失败则 stock_hk_spot_em() 兜底
所有标的统一附加 market / full_code / py 字段，供 index.html _uniSearch 使用。
"""

import json, os, re, time
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "out")
OUTPUT = os.path.join(DATA_DIR, "stock_names.json")

# 本地拼音首字母映射（由月度维护脚本生成，避免 runner 安装 pypinyin）
PINYIN_FILE = os.path.join(os.path.dirname(__file__), "stock_pinyin.json")

# 本地行业/概念/板块映射（由 v6 industry_map.json 归一化生成，避免云端依赖 akshare/东财）
META_FILE = os.path.join(os.path.dirname(__file__), "stock_industry_concepts.json")

def _load_pinyin_map():
    """加载 code -> py 映射；缺失则返回空 dict，让后续 fallback。"""
    try:
        with open(PINYIN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _fallback_py(name):
    """无映射时的轻量 fallback：仅保留 A-Z/a-z 字母作为首字母，
    对纯中文名返回空字符串（避免乱猜）。"""
    if not name:
        return ""
    letters = []
    for ch in name:
        if "a" <= ch.lower() <= "z":
            letters.append(ch.lower())
    return "".join(letters)


def _generate_py(name):
    """用 pypinyin 生成中文名首字母；未安装或失败则 fallback。"""
    if not name:
        return ""
    try:
        from pypinyin import lazy_pinyin
        return "".join([p[0].lower() for p in lazy_pinyin(name) if p]).lower()
    except Exception:
        return _fallback_py(name)


def _attach_py(stocks):
    """给股票列表附加 py 字段。"""
    py_map = _load_pinyin_map()
    for s in stocks:
        code = str(s.get("code", "")).strip()
        name = s.get("name", "")
        # A 股优先用本地静态拼音映射；港股/ETF 动态生成
        s["py"] = py_map.get(code) or _generate_py(name)
    return stocks


def _load_meta_map():
    """加载 code -> {industry, concepts, board} 映射；缺失返回空 dict。"""
    try:
        with open(META_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _board_of_a(code):
    """A股/北交所代码 → 上市板（兼容 sh600000 / 600000 等格式）。"""
    c = re.sub(r"[^0-9]", "", str(code))
    if not c:
        return ""
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
    return ""


def _attach_meta(stocks):
    """给股票列表附加 industry / concepts / board 字段（来自本地静态映射，云端安全）。"""
    meta_map = _load_meta_map()
    for s in stocks:
        code = str(s.get("code", "")).strip()
        m = meta_map.get(code) or {}
        if m.get("industry"):
            s["industry"] = m["industry"]
        if m.get("concepts"):
            s["concepts"] = m["concepts"]
        # board：优先映射，缺失则按代码前缀推导
        board = m.get("board") or _board_of_a(code)
        if board:
            s["board"] = board
    return stocks

def _fetch_a_share_via_eastmoney():
    """东方财富全量 A 股代码→名称（akshare stock_zh_a_spot_em 经常超时丢数据时的兜底）"""
    import requests
    url = "https://push2.eastmoney.com/api/qianlong/clist/get?pn=1&pz=10000&po=1&np=1&fltt=2&invt=2&fs=m:0+t:6+f:!2,m:0+t:13+f:!2,m:0+t:80+f:!2,m:1+t:2+f:!2,m:1+t:23+f:!2&fields=f12,f14"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        data = r.json().get("data") or {}
        diff = data.get("diff") or []
        result = []
        for item in diff:
            code = str(item.get("f12", "")).strip()
            name = str(item.get("f14", "")).strip()
            if not code or not name:
                continue
            if not (code.startswith(("0", "3", "6")) and len(code) == 6):
                continue
            prefix = "sz" if code.startswith(("0", "3")) else "sh"
            result.append({"code": code, "name": name, "full_code": prefix + code})
        return result
    except Exception as e:
        print(f"  ⚠️ 东方财富 A股接口失败: {e}")
        return []

def _fetch_a_share_via_sina():
    """新浪全量 A 股代码→名称（分页拉沪A/深A/北A，更稳定的兜底）"""
    import requests, json
    result = []
    nodes = [
        ("sh", "sh_a", 2500),   # 沪A (沪市主板+科创板)
        ("sz", "sz_a", 3000),   # 深A (深市主板+中小板+创业板)
        ("bj", "hs_a", 300),    # 北A (北交所)
    ]
    for prefix, node, total in nodes:
        for offset in range(0, total, 80):
            try:
                url = f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?node={node}&sort=symbol&asc=1&num=80&page={offset//80 + 1}&_s_r_a=page"
                r = requests.get(url, timeout=15, headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://vip.stock.finance.sina.com.cn/"
                })
                txt = r.text.strip()
                if not txt.startswith("["):
                    break
                items = json.loads(txt)
                if not items:
                    break
                for item in items:
                    code = str(item.get("symbol", "")).strip()
                    name = str(item.get("name", "")).strip()
                    if not code or not name:
                        continue
                    # 取纯 6 位代码
                    code6 = code[2:] if len(code) > 6 else code
                    if not (code6.startswith(("0", "3", "6")) and len(code6) == 6):
                        continue
                    result.append({"code": code6, "name": name, "full_code": prefix + code6})
            except Exception as e:
                print(f"  ⚠️ 新浪 {node} 第{offset//80+1}页失败: {e}")
                break
    return result

def _fetch_hk_stocks():
    """抓取港股全量代码→名称。优先新浪 stock_hk_spot，失败再试东财 stock_hk_spot_em。"""
    try:
        import akshare as ak
    except Exception as e:
        print(f"  ⚠️ akshare 未安装，跳过港股: {e}")
        return []
    for fn in (ak.stock_hk_spot, ak.stock_hk_spot_em):
        try:
            df = fn()
            if df is None or df.empty:
                continue
            code_col = "代码" if "代码" in df.columns else "code"
            name_col = "名称" if "名称" in df.columns else ("中文名称" if "中文名称" in df.columns else "name")
            result = []
            for _, row in df.iterrows():
                code = str(row.get(code_col, "")).strip()
                name = str(row.get(name_col, "")).strip()
                if not code or not name or not code.isdigit():
                    continue
                code = code.zfill(5)
                result.append({"code": code, "name": name, "full_code": "hk" + code, "market": "hk"})
            print(f"  ✅ 港股: {fn.__name__} {len(result)} 只")
            return result
        except Exception as e:
            print(f"  ⚠️ 港股 {fn.__name__} 失败: {type(e).__name__} {str(e)[:60]}")
            time.sleep(1)
    return []


def _fetch_etf_stocks():
    """抓取 ETF 全量代码→名称。"""
    try:
        import akshare as ak
    except Exception as e:
        print(f"  ⚠️ akshare 未安装，跳过 ETF: {e}")
        return []
    try:
        df = ak.fund_etf_spot_em()
        if df is None or df.empty:
            print("  ⚠️ ETF 无数据")
            return []
        result = []
        for _, row in df.iterrows():
            code = str(row.get("代码", "")).strip()
            name = str(row.get("名称", "")).strip()
            if not code or not name or not code.isdigit() or len(code) != 6:
                continue
            prefix = "sh" if code.startswith("5") else "sz"
            result.append({"code": code, "name": name, "full_code": prefix + code, "market": "etf"})
        print(f"  ✅ ETF: {len(result)} 只")
        return result
    except Exception as e:
        print(f"  ⚠️ ETF 获取失败: {type(e).__name__} {str(e)[:60]}")
        return []


def main():
    print("=" * 50)
    print("  A 股 + 港股 + ETF 全量股票名称列表更新")
    print("=" * 50)

    all_stocks = []

    # ── A 股（新浪优先，东财次之，akshare 最后）──
    a_stocks = _fetch_a_share_via_sina()
    if not a_stocks:
        a_stocks = _fetch_a_share_via_eastmoney()
    if not a_stocks:
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    code = str(row.get("代码", "")).strip()
                    name = str(row.get("名称", "")).strip()
                    if not code or not name:
                        continue
                    prefix = "sz" if code.startswith(("0", "3")) else "sh"
                    a_stocks.append({"code": code, "name": name, "full_code": prefix + code, "market": prefix})
        except Exception as e:
            print(f"  ⚠️ A股获取失败: {e}")

    if a_stocks:
        all_stocks.extend(a_stocks)
        print(f"  ✅ A股: {len(a_stocks)} 只")
    else:
        print("  ⚠️ A股全失败，跳过")

    # ── 港股 ──
    time.sleep(1)
    hk_stocks = _fetch_hk_stocks()
    if hk_stocks:
        seen = {s["code"] for s in all_stocks}
        for s in hk_stocks:
            if s["code"] not in seen:
                all_stocks.append(s)
                seen.add(s["code"])

    # ── ETF ──
    time.sleep(1)
    etf_stocks = _fetch_etf_stocks()
    if etf_stocks:
        seen = {s["code"] for s in all_stocks}
        for s in etf_stocks:
            if s["code"] not in seen:
                all_stocks.append(s)
                seen.add(s["code"])

    if len(all_stocks) < 4000:
        # 抓取不足：保留旧文件，但仍把 py / 行业 / 概念 / 板块 重新合并进去，避免数据回退
        print(f"  ⚠️ 新抓取总数 {len(all_stocks)} 不足（预期>4000），尝试沿用并补全旧文件")
        try:
            with open(OUTPUT, "r", encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old, dict):
                old = old.get("data", old)
            if isinstance(old, list) and len(old) >= 4000:
                # 合并旧文件，保留旧文件里的港股/ETF 以防本次抓失败
                old_seen = {s["code"] for s in all_stocks}
                for s in old:
                    if s.get("code") not in old_seen:
                        all_stocks.append(s)
                        old_seen.add(s["code"])
                print(f"  ✅ 沿用旧文件补全后 {len(all_stocks)} 只，继续补全元数据")
            else:
                print("  ⚠️ 旧文件也不足，放弃写入")
                return
        except Exception as e:
            print(f"  ⚠️ 读取旧文件失败: {e}，放弃写入")
            return

    _attach_py(all_stocks)
    _attach_meta(all_stocks)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(all_stocks, f, ensure_ascii=False, indent=0)

    print(f"  ✅ 总计 {len(all_stocks)} 只 → {OUTPUT}")

if __name__ == "__main__":
    from fetch_logger import record_success, record_failure
    try:
        main()
        record_success(__file__)
    except Exception as e:
        record_failure(__file__, str(e))
        raise
