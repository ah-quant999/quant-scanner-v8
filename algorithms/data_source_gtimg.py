#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""data_source_gtimg — v8 云端数据源模块（腾讯 GTimg 前复权日K + 新浪活跃股排行）

用途：scanner.py 在 CLOUD_RUNNER=true 时经 `_gtimg()` 调用本模块，避免云端
mootdx/东财不可达。接口与 scanner 期望完全一致：
  fetch_a_daily_gtimg(code, market='sh'|'sz', bars=250)
      -> pandas DataFrame(date/open/close/high/low/volume/pct_chg) 或 None
  fetch_volume_top_stocks_gtimg(top_cy, top_kc, top_zb, top_hk)
      -> [(code, name, market, board_label, 0, turnover_rate, 0, fund_type), ...]
      （新浪 getHQNodeData 按成交额排序，分流 创业板/科创板/主板；港股暂不支持）

数据来源：
  - 日K：web.ifzq.gtimg.cn（腾讯行情，前复权 qfqday）
  - 活跃股：vip.stock.finance.sina.com.cn（新浪沪深A排行 sort=amount）
两者均为 HTTP JSON，无需本地库。
"""
import json
import os
import time
import urllib.request
import urllib.error

import pandas as pd

KLINE_API = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
RANK_API = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_BASE_DIR)

# 候选股池兜底源（build_candidate_pool.py 产出，与新浪排行 API 相互独立）
# 2026-08-11 修复：新浪 hs_a 排行不可达时 _sina_rank() 静默返回空 →
#   A股股池 0 只 → gold_pool 无 A股 → TOP10_DAILY 全港股 → 全站精选卡告警。
#   改为从候选池回填活跃股，候选池每日由独立管线刷新，不会像硬编码池那样老化。
_CAND_FALLBACK_PATHS = (
    os.path.join(_REPO_ROOT, "raw_data", "candidate.json"),
    os.path.join(_REPO_ROOT, "out", "candidate_pool.json"),
    os.path.join(_BASE_DIR, "data", "candidate_pool.json"),
)


def _http(url, timeout=20, retries=3, referer="https://finance.sina.com.cn/"):
    """GET 并返回文本（带智能重试与异常处理）。

    修复点（2026-08-28）：
      - sina/腾讯接口多为 GBK 编码，原 utf-8+replace 会把中文名/板块名解码成乱码；
        改为按 Content-Type 探测，失败回退 GBK。
      - 仅对瞬时错误（连接重置/超时/5xx）重试；4xx 客户端错误立即失败，不浪费重试。
    """
    last = None
    for i in range(retries):
        try:
            headers = dict(_UA)
            if referer:
                headers["Referer"] = referer
            req = urllib.request.Request(url, headers=headers)
            resp = urllib.request.urlopen(req, timeout=timeout)
            raw = resp.read()
            charset = resp.headers.get_content_charset()
            try:
                return raw.decode(charset or "utf-8")
            except (UnicodeDecodeError, TypeError):
                return raw.decode("gbk", "replace")  # sina/腾讯兜底
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500:
                raise  # 4xx 客户端错误：不重试，立即失败
            last = e
            time.sleep(1 + i * 2)
        except Exception as e:  # 连接重置/超时/5xx 等瞬时错误才重试
            last = e
            time.sleep(1 + i * 2)
    raise last or RuntimeError("no attempts")


def fetch_a_daily_gtimg(code, market="sh", bars=250):
    """腾讯前复权日K → DataFrame(date/open/close/high/low/volume/pct_chg)。

    与 scanner.fetch_a_daily 的 mootdx 分支列结构一致；非未来函数（仅截至当日）。
    """
    sym = f"{market}{code}"
    raw = _http(f"{KLINE_API}?param={sym},day,,,{bars},qfq", referer="https://gu.qq.com/")
    d = json.loads(raw)
    node = (d.get("data") or {}).get(sym) or {}
    k = node.get("qfqday") or node.get("day") or []
    rows = []
    for it in k:
        if len(it) < 6:
            continue
        try:
            rows.append({
                "date": str(it[0]),
                "open": float(it[1]),
                "close": float(it[2]),
                "high": float(it[3]),
                "low": float(it[4]),
                "volume": float(it[5]),
            })
        except Exception:  # noqa: BLE001
            continue
    if len(rows) < 60:
        return None
    df = pd.DataFrame(rows)
    df["pct_chg"] = 0.0
    if len(df) > 1:
        df["pct_chg"] = ((df["close"] / df["close"].shift(1) - 1) * 100).round(2)
    return df


def _sina_rank(num=300, node="hs_a"):
    """新浪按成交额排序，最多翻 3 页×200。返回 list[dict]。

    node 指定板块：hs_a=全市场 / cyb=创业板 / kcb=科创板。
    """
    arr = []
    page = 1
    while len(arr) < num and page <= 3:
        url = f"{RANK_API}?page={page}&num=200&sort=amount&asc=0&node={node}"
        try:
            raw = _http(url)
            batch = json.loads(raw)
        except Exception as e:  # noqa: BLE001
            print(f"  [GTimg] 新浪排行第{page}页失败(node={node}): {e}")
            break
        if not batch:
            break
        arr.extend(batch)
        if len(batch) < 200:
            break
        page += 1
    return arr[:num]


def _board_of(code):
    """按代码前缀判定板块，返回 (board_label, market)。"""
    if code.startswith(("300", "301")):
        return "创业板", "sz"
    if code.startswith(("688", "689")):
        return "科创板", "sh"
    return "主板", ("sh" if code.startswith(("6", "9")) else "sz")


def _fallback_from_candidate_pool(top_cy, top_kc, top_zb):
    """排行 API 不可达时的兜底：从候选股池回填 A 股活跃股。

    返回与 fetch_volume_top_stocks_gtimg 完全一致的元组列表；无可用候选池时返回 []。
    """
    for path in _CAND_FALLBACK_PATHS:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:  # noqa: BLE001
            print(f"  [GTimg] 候选池兜底读取失败 {os.path.basename(path)}: {e}")
            continue

        stocks_obj = data.get("stocks") or {}
        rows = stocks_obj.values() if isinstance(stocks_obj, dict) else stocks_obj
        cy, kc, zb = [], [], []
        for it in rows:
            if not isinstance(it, dict):
                continue
            code = str(it.get("code") or "").strip()
            if not code.isdigit() or len(code) != 6:
                continue  # 跳过港股等非 A 股
            name = it.get("name") or code
            board, mkt_default = _board_of(code)
            market = it.get("market") or mkt_default
            row = (code, name, market, board, 0, 0, 0, "混合")
            if board == "创业板":
                cy.append(row)
            elif board == "科创板":
                kc.append(row)
            else:
                zb.append(row)

        out = cy[:top_cy] + kc[:top_kc] + zb[:top_zb]
        if out:
            print(f"  [GTimg][兜底] 候选池 {os.path.basename(path)} "
                  f"(更新于 {data.get('update_time', '未知')}): "
                  f"创业{len(cy[:top_cy])} 科创{len(kc[:top_kc])} 主板{len(zb[:top_zb])}")
            return out
    print("  [GTimg][兜底] 无可用候选池，A股股池为空")
    return []


def fetch_volume_top_stocks_gtimg(top_cy=100, top_kc=100, top_zb=100, top_hk=50):
    """活跃股池：分板块取数（创业板=cyb / 科创板=kcb / 主板=hs_a），避免主板在「全市场按成交额排序」中挤占创业/科创名额。

    港股暂不支持（返回空）。
    """
    def _split(rank):
        cy, kc, zb = [], [], []
        for x in rank:
            sym = (x.get("symbol") or "").lower()
            code = sym[2:] if sym.startswith(("sh", "sz")) else sym
            if not code.isdigit():
                continue
            market = "sh" if sym.startswith("sh") else "sz"
            name = x.get("name") or code
            try:
                to = float(x.get("turnoverratio") or 0)
            except Exception:  # noqa: BLE001
                to = 0.0
            if code.startswith(("300", "301")):
                cy.append((code, name, market, "创业板", 0, to, 0, "混合"))
            elif code.startswith(("688", "689")):
                kc.append((code, name, market, "科创板", 0, to, 0, "混合"))
            else:
                zb.append((code, name, market, "主板", 0, to, 0, "混合"))
        return cy, kc, zb

    # 2026-09-04 修复：分板块取数，杜绝主板挤占创业/科创名额。
    # 旧逻辑 _sina_rank(300) 全市场只取前 300，前 300 里创业+科创合计仅 ~65 只 →
    # 分流后 cy/kc 不足 100 → 前端「观测候选股池」标黄（误报）。
    cy, kc, zb = [], [], []
    try:
        cy = _split(_sina_rank(top_cy, node="cyb"))[0]
    except Exception as e:  # noqa: BLE001
        print(f"  [GTimg] 创业板排行失败: {e}")
    try:
        kc = _split(_sina_rank(top_kc, node="kcb"))[1]
    except Exception as e:  # noqa: BLE001
        print(f"  [GTimg] 科创板排行失败: {e}")
    try:
        # 主板无单一节点：合并沪市(sh_a)+深市(sz_a)活跃榜，过滤掉创业/科创后取前 top_zb。
        # （hs_a 全市场每页仅 100 只、主板占 ~62，不足以取满；两市分取可稳定得 ~120 主板）
        zb_rank = _sina_rank(top_zb, node="sh_a") + _sina_rank(top_zb, node="sz_a")
        zb = _split(zb_rank)[2]
    except Exception as e:  # noqa: BLE001
        print(f"  [GTimg] 主板排行失败(sh_a+sz_a)，回退 hs_a: {e}")
        try:
            zb = _split(_sina_rank(max(top_zb, 300), node="hs_a"))[2]
        except Exception as e2:  # noqa: BLE001
            print(f"  [GTimg] 主板排行失败: {e2}")

    stocks = cy[:top_cy] + kc[:top_kc] + zb[:top_zb]
    print(f"  [GTimg] 活跃股池: 创业{len(cy[:top_cy])} 科创{len(kc[:top_kc])} 主板{len(zb[:top_zb])}")

    # 部分板块为空（节点不可达等）→ 用候选池补齐缺失板块，不覆盖已抓到的
    missing = [b for b, lst in (("创业板", cy), ("科创板", kc), ("主板", zb)) if not lst]
    if missing:
        print(f"  [GTimg] 板块缺失 {missing}，候选池补齐...")
        have = {s[0] for s in stocks}
        for row in _fallback_from_candidate_pool(top_cy, top_kc, top_zb):
            if row[3] in missing and row[0] not in have:
                stocks.append(row)
                have.add(row[0])
        print(f"  [GTimg] 补齐后股池: {len(stocks)} 只")
    return stocks


if __name__ == "__main__":
    df = fetch_a_daily_gtimg("000001", "sz", 120)
    print("日K rows:", "None" if df is None else len(df),
          "| last:", "None" if df is None else f"{df.iloc[-1]['date']} close={df.iloc[-1]['close']}")
    st = fetch_volume_top_stocks_gtimg(5, 5, 5, 0)
    print("股池:", [(s[0], s[1], s[3]) for s in st])
