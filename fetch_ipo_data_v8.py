#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v8 打新价值评分数据获取 —— 支持申购期/上市首日/上市后追踪 + 可转债
用法: python fetch_ipo_data_v8.py          # 直接写 raw_data/ipo_score.json
      import fetch_ipo_data_v8 as ipo; ipo.generate_ipo_score()  # 返回 dict 给 cloud_fetch_v8.py
输出: raw_data/ipo_score.json

状态分类:
  - applying: 待申购（显示评分+建议申购等级）
  - listed_today: 今日上市（显示首日表现）
  - tracking: 上市后5日内追踪（显示是否值得追入）
  - 超5天: 隐藏

数据源:
  1. 东方财富 datacenter API — 新股申购/上市列表 (RPTA_APP_IPOAPPLY)
  2. 东方财富 datacenter API — 可转债列表 (RPT_BOND_CB_LIST)
  3. 东方财富行情 API — 实时行情（收盘价、涨幅、换手率）
  4. 同花顺 — 最近上市新股补充 (stock_xgsr_ths)

注: 本文件由 v6 fetch_ipo_data.py 移植，去掉 fetch_logger/is_trading_day/.machine_role
    等 v6 专用依赖，以便 v8 中国 runner 独立运行。
"""

#####  可转债 —— 数据获取 + 评分  #####

def fetch_bond_list():
    """从东方财富 datacenter API 获取可转债列表"""
    import urllib.parse
    bonds = []
    today_str = datetime.now().strftime("%Y%m%d")
    today_int = int(today_str)

    fields = "ALL"
    url = (f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
           f"sortColumns=PUBLIC_START_DATE&sortTypes=-1&pageSize=50&pageNumber=1"
           f"&reportName=RPT_BOND_CB_LIST&columns={urllib.parse.quote(fields)}")

    try:
        data = http_get(url, retry=2)
        if not data.get("success"):
            print(f"  ⚠️ 可转债 API 返回失败: {data.get('message','?')}")
            return bonds
        rows = data.get("result", {}).get("data", [])
        print(f"  ✓ 可转债 API: {len(rows)} 条")
    except Exception as e:
        print(f"  ⚠️ 可转债 API 失败: {e}")
        return bonds

    for row in rows:
        code = row.get("SECURITY_CODE", "")
        name = row.get("SECURITY_NAME_ABBR", "")

        # 已有字段名：SECUCODE, SECURITY_CODE, SECURITY_NAME_ABBR, BOND_CODE
        # code 取 SECUCODE（如 123275.SZ）里的纯数字部分，或直接用 SECURITY_CODE
        bond_code = str(code).split(".")[0] if "." in str(code) else str(code)
        if not bond_code or bond_code == "None":
            bond_code = str(row.get("BOND_CODE",""))
            if not bond_code or bond_code == "None":
                continue

        apply_date = _parse_date(row.get("PUBLIC_START_DATE"))
        listing_date = _parse_date(row.get("LISTING_DATE"))

        # 规模（亿）
        scale = row.get("ACTUAL_ISSUE_SCALE") or row.get("PLAN_ISSUE_SCALE") or 0
        try:
            scale = float(scale)
        except (ValueError, TypeError):
            scale = 0

        # 转股价
        transfer_price = row.get("INITIAL_TRANSFER_PRICE") or 0
        try:
            transfer_price = float(transfer_price)
        except (ValueError, TypeError):
            transfer_price = 0

        # 正股代码/名称（用于计算转股溢价）
        stock_code = row.get("STOCK_CODE", "") or row.get("UNDERLYING_CODE", "")

        # 状态分类
        status = _bond_classify_status(apply_date, listing_date, today_int)
        if status == "expired":
            continue

        bonds.append({
            "type": "bond",
            "code": bond_code,
            "name": name or bond_code,
            "issue_price": 100.0,  # 可转债面值100元
            "transfer_price": round(transfer_price, 2),
            "bond_scale": round(scale, 2),
            "stock_code": str(stock_code) if stock_code else "",
            "apply_date": apply_date,
            "listing_date": listing_date,
            "status": status,
            "market_code": "SZ" if bond_code.startswith("12") else "SH",
            "dec_sumfina": scale,  # 兼容旧字段
        })

    # 统计
    applying = sum(1 for b in bonds if b["status"] == "applying")
    pre_listing = sum(1 for b in bonds if b["status"] == "pre_listing")
    listed = sum(1 for b in bonds if b["status"] == "listed_today")
    tracking = sum(1 for b in bonds if b["status"] == "tracking")
    print(f"    分类: 待申购={applying} 待上市={pre_listing} 今日上市={listed} 追踪={tracking}")
    return bonds


def _bond_classify_status(apply_date, listing_date, today_int):
    """可转债状态分类（同股票逻辑）"""
    if listing_date:
        try:
            list_int = int(listing_date)
            if list_int == today_int:
                return "listed_today"
            if list_int > today_int:
                return "pre_listing"
            if today_int - list_int <= 5:
                return "tracking"
            return "expired"
        except ValueError:
            pass
    if apply_date:
        try:
            apply_int = int(apply_date)
            if apply_int >= today_int:
                return "applying"
            if today_int - apply_int <= 7:
                return "pre_listing"
            return "expired"
        except ValueError:
            pass
    return "applying"


def calculate_bond_scores(bonds):
    """可转债评分：双维度分列（套利分+基本面分），与股票评分口径一致"""
    results = []
    for b in bonds:
        transfer_price = b.get("transfer_price", 0)
        scale = b.get("bond_scale", 0)

        # ── 套利分：规模溢价 + 转股价合理性（转股价越低越容易转股套利）
        arbitrage = 50
        if scale >= 20:      arbitrage += 15
        elif scale >= 10:  arbitrage += 10
        elif scale >= 5:   arbitrage += 5
        if transfer_price > 0 and transfer_price < 50:   arbitrage += 10
        elif transfer_price > 0 and transfer_price < 100: arbitrage += 5
        arbitrage = min(arbitrage, 80)

        # ── 基本面分：债底安全（规模大 + 转股价合理 → 债底更厚）
        fundamental = 35
        if scale >= 20:      fundamental += 20
        elif scale >= 10:   fundamental += 15
        elif scale >= 5:    fundamental += 10
        if transfer_price > 0 and transfer_price < 100:  fundamental += 10
        elif transfer_price > 0 and transfer_price < 150: fundamental += 5
        fundamental = min(fundamental, 70)

        # 总分与股票口径一致：套利*0.6 + 基本面*0.4
        score = int(round(arbitrage * 0.6 + fundamental * 0.4))

        # 建议等级
        if score >= 70:
            recommend, tag_color, bg_color = "建议申购", "#0d7d4a", "#e8f5e9"
        elif score >= 55:
            recommend, tag_color, bg_color = "谨慎参与", "#f57f17", "#fffde7"
        else:
            recommend, tag_color, bg_color = "不建议申购", "#c62828", "#ffebee"

        b["score"] = score
        b["arbitrage_score"] = arbitrage
        b["fundamental_score"] = fundamental
        b["recommend"] = recommend
        b["tag_color"] = tag_color
        b["bg_color"] = bg_color
        b["board"] = "可转债"
        b["fundamentals"] = {
            "track": "可转债",
            "scale": round(scale, 2),
            "transfer_price": round(transfer_price, 2) if transfer_price > 0 else 0,
            "bond_safety": "高" if fundamental >= 55 else "中" if fundamental >= 45 else "低",
        }
        b["highlights"] = [
            (f"转股价 ¥{transfer_price:.2f}" if transfer_price > 0 else ""),
            (f"规模 {scale:.1f}亿" if scale > 0 else ""),
            f"债底安全 {b['fundamentals']['bond_safety']}",
        ]
        b["highlights"] = [h for h in b["highlights"] if h]
        results.append(b)
    return results


def _sina_bond_quote(code, market_code):
    """可转债专用行情：新浪 hq.sinajs.cn（用户允许换接口）。

    URL: https://hq.sinajs.cn/list={market}{code}（如 sh110103, sz127115）
    返回 CSV 字段顺序：名称, 开, 昨收, 现价, 最高, 最低, 买价, 卖价, 成交量, 成交额, ...
    因子：f43 不再除 100（已是元）；f47 成交额已是元。
    返回 None 表示接口不可用，需上层 fallback。
    """
    prefix = "sh" if str(market_code).upper() in ("SH",) else "sz"
    url = f"https://hq.sinajs.cn/list={prefix}{code}"
    try:
        raw = http_get(url)
        # http_get 默认会 json.loads，sina 返回 CB 第一行带 var hq_str_xxx="..."; 需直接用 text
        # 改成 urllib 文本读取绕过 JSON 解析
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://finance.sina.com.cn/",
            "Accept": "*/*",
        })
        with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as resp:
            txt = resp.read().decode("gbk", errors="ignore")
        # 匹配 "..." 内容
        import re as _re
        m = _re.search(r'"([^"]*)"', txt)
        if not m:
            return None
        parts = m.group(1).split(",")
        if len(parts) < 6:
            return None
        def _f(x):
            try: return float(x)
            except: return 0.0
        # sina 可转债字段：0名字,1今开,2昨收,3现价,4最高,5最低,6买入,7卖出,8成交量,9成交额
        open_p = _f(parts[1])
        prev_close = _f(parts[2])
        latest = _f(parts[3])
        turnover_yuan = _f(parts[9])  # 元
        turnover = turnover_yuan / 1e4  # 转为万元（与 f168 口径接近）
        return {
            "latest": latest,
            "open_price": open_p,
            "prev_close": prev_close,
            "change_pct": (latest - prev_close) / prev_close * 100 if prev_close > 0 else 0,
            "turnover": turnover,
        }
    except Exception as e:
        print(f"    ⚠️ sina转债 {code} 行情失败: {e}")
        return None


def process_bond_listed(bonds):
    """处理可转债上市首日/追踪 —— 基于实时行情给双维度分

    2026-08-13 修复：
      1) 之前没设 b["board"]，导致渲染层无法识别"可转债"标签（红 A bug）。
      2) 东财 push2 不返回可转债真实行情，强行除 100 会算出 1300 假价（红 A bug）。
         改为优先 sina hq.sinajs.cn 专用接口（用户允许换接口），回退 None 不再假算。
      3) quote 双源失败时，latest/change_pct/total_return 写 None，渲染层读 None 应标"行情暂缺"。
    """
    results = []
    for b in bonds:
        issue_price = 100.0  # 可转债面值
        market_code = b.get("market_code", "SH")

        # 三源 fallback：sina(转债专用) → 东财通用 → None（不再假算）
        quote = _sina_bond_quote(b["code"], market_code)
        if not quote:
            quote = fetch_realtime_quote(b["code"], market_code)

        if quote and quote.get("latest"):
            latest = quote["latest"]
            open_p = quote["open_price"]
            change_pct = quote["change_pct"]
            turnover = quote["turnover"]
            total_return = (latest - issue_price) / issue_price * 100 if latest > 0 else None
            open_return = (open_p - issue_price) / issue_price * 100 if open_p > 0 else None
        else:
            # 双源全挂：不假算 None，让渲染层显示"行情暂缺"
            latest = None
            open_p = None
            change_pct = None
            turnover = None
            total_return = None
            open_return = None

        # 双源都失败：不再假算，直接走"行情暂缺"分支
        if latest is None:
            score = 0
            arbitrage = 0
            fundamental = 0
            if b["status"] == "tracking":
                advice, tcol, bg = "数据不足，需重试", "#999", "#f5f5f5"
            else:
                advice = "行情暂缺"
                tcol = "#999"
                bg = "#f5f5f5"
            highlights = ["行情暂缺", "—"]
        else:
            # ── 套利分：上市涨幅/热度（越高越好）
            arbitrage = 50
            if total_return > 10:      arbitrage += 30
            elif total_return > 5:     arbitrage += 25
            elif total_return > 2:     arbitrage += 15
            elif total_return > 0:     arbitrage += 5
            elif total_return < -5:    arbitrage -= 20
            elif total_return < 0:     arbitrage -= 10
            arbitrage = max(0, min(arbitrage, 85))

            # ── 基本面分：流动性/成交额 + 债底安全
            fundamental = 40
            # turnover 单位可能是万元级，按常见行情接口口径处理
            turnover_wan = turnover / 10000 if turnover > 1000 else turnover
            if turnover_wan > 1000:       fundamental += 20
            elif turnover_wan > 500:      fundamental += 15
            elif turnover_wan > 100:      fundamental += 10
            elif turnover_wan > 10:       fundamental += 5
            fundamental = min(fundamental, 75)

            score = int(round(arbitrage * 0.6 + fundamental * 0.4))

            # 追踪建议
            if b["status"] == "tracking":
                advice, tcol, bg = tracking_advice(issue_price, latest, change_pct, turnover)
            else:
                advice = "上市首日"
                tcol = "#0d7d4a"
                bg = "#e8f5e9"

            highlights = [
                f"较发行 {total_return:+.1f}%",
                f"现价 ¥{latest:.2f}",
            ]
            if b["status"] == "tracking":
                highlights.append(advice)

        # 写入数据字段（保留 None 不假算，渲染层处理 None → "行情暂缺"）
        b["latest"] = None if latest is None else round(latest, 2)
        b["open_price"] = None if open_p is None else round(open_p, 2)
        b["change_pct"] = None if change_pct is None else round(change_pct, 2)
        b["turnover"] = None if turnover is None else round(turnover, 2)
        b["total_return"] = None if total_return is None else round(total_return, 1)
        b["open_return"] = None if open_return is None else round(open_return, 1)
        b["score"] = score
        b["arbitrage_score"] = arbitrage
        b["fundamental_score"] = fundamental
        b["recommend"] = advice
        b["tag_color"] = tcol
        b["bg_color"] = bg
        # 🔴 2026-08-13 修复：之前 process_bond_listed 从未写 board，导致渲染层
        # 拿不到"可转债"标签，3 张转债卡片显示为同一通用标签。
        b["board"] = "可转债"
        b["market"] = b.get("market_code", "SH").lower()  # 渲染层多维列表用得上
        b["fundamentals"] = {
            "track": "可转债",
            "total_return": b["total_return"],
            "turnover": b["turnover"],
        }
        b["highlights"] = highlights
        results.append(b)
    return results

#####  可转债 END  #####
import json
import os
import sys
import time
import subprocess
from datetime import datetime, date, timedelta

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_data")
os.makedirs(DATA_DIR, exist_ok=True)

def _ssl_ctx():
    """创建宽松 SSL 上下文（东方财富 API 有时对 schannel 不友好）"""
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def http_get(url, retry=3):
    """HTTP GET using urllib（比 curl 更可靠穿过东方财富 schannel 问题）"""
    import urllib.request
    import urllib.error
    last_err = None
    for i in range(retry):
        try:
            if i > 0:
                time.sleep(3 * i)
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://data.eastmoney.com/xg/xg/",
                "Accept": "application/json, text/html, */*",
            })
            with urllib.request.urlopen(req, timeout=20, context=_ssl_ctx()) as resp:
                raw = resp.read().decode("utf-8")
                if not raw or not raw.strip():
                    raise ValueError("Empty response")
                return json.loads(raw)
        except Exception as e:
            last_err = e
    raise last_err

def board_name(market_code):
    m = {"SH": "沪市主板", "SZ": "深市主板", "CY": "创业板", "KC": "科创板", "BJ": "北交所"}
    return m.get(market_code, "其他")

def board_score(board):
    s = {"沪市主板": 15, "深市主板": 14, "创业板": 12, "科创板": 10, "北交所": 8}
    return s.get(board, 8)

def score_price(price):
    if not price or price <= 0:
        return 10
    if price <= 5: return 12
    if price <= 15: return 20
    if price <= 30: return 18
    if price <= 50: return 14
    if price <= 80: return 8
    return 4

def fetch_apply_dates_from_calendar():
    """从东方财富新股申购日历获取真实申购日期"""
    result = {}
    try:
        raw = subprocess.run(
            ["curl", "-s", "--max-time", "15",
             "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
             "https://data.eastmoney.com/xg/xg/calendar.html"],
            capture_output=True, text=True, timeout=20
        )
        if raw.returncode == 0 and raw.stdout.strip():
            import re
            html = raw.stdout
            json_pattern = re.compile(
                r'\{"SECUCODE":"[^"]+","TRADE_DATE":"([^"]+)","DATE_TYPE":"([^"]+)"'
                r',"SECURITY_CODE":"(\d{6})","SECURITY_NAME_ABBR":"([^"]+)"[^}]*\}'
            )
            matches = json_pattern.findall(html)
            for trade_date, date_type, code, name in matches:
                if date_type != "申购":
                    continue
                apply_date = trade_date.split(" ")[0].replace("-", "")
                if code and apply_date and len(apply_date) >= 8:
                    result[code] = apply_date
            if result:
                return result
    except Exception as e:
        print(f"  ⚠️ 日历抓取失败: {e}")
    return result

def fetch_realtime_quote(code, market_code):
    """获取实时行情：收盘价、涨幅、换手率"""
    # 北交所也用 0 前缀
    if market_code in ("SZ", "CY", "BJ"):
        secid = f"0.{code}"
    else:
        secid = f"1.{code}"
    url = f"https://push2.eastmoney.com/api/qt/stock/get?secid={secid}&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f170,f168"
    try:
        data = http_get(url)
        info = data.get("data", {})
        # f43=最新价, f44=最高价, f45=最低价, f46=开盘价, f47=成交量, f48=成交额
        # f57=代码, f58=名称, f60=昨收, f170=涨幅, f168=换手率
        latest = info.get("f43", 0) or 0
        open_price = info.get("f46", 0) or 0
        prev_close = info.get("f60", 0) or 0
        change_pct = info.get("f170", 0) or 0
        turnover = info.get("f168", 0) or 0
        return {
            "latest": float(latest) / 100 if latest else 0,  # 注意：有些接口需要除以100
            "open_price": float(open_price) / 100 if open_price else 0,
            "prev_close": float(prev_close) / 100 if prev_close else 0,
            "change_pct": float(change_pct) / 100 if change_pct else 0,
            "turnover": float(turnover) / 100 if turnover else 0,
        }
    except Exception as e:
        print(f"    ⚠️ {code} 行情获取失败: {e}")
        return None

def classify_status(listing_str, today_str):
    """判断新股状态"""
    if listing_str in ("-", "", "None", None):
        return "applying", None
    try:
        listing_int = int(listing_str)
        today_int = int(today_str)
        if listing_int == today_int:
            return "listed_today", listing_int
        elif today_int - listing_int <= 5:
            return "tracking", listing_int
        else:
            return "expired", listing_int
    except:
        return "applying", None

def tracking_advice(issue_price, latest_price, change_pct, turnover):
    """上市后追踪建议：是否值得追入"""
    if not issue_price or issue_price <= 0 or not latest_price or latest_price <= 0:
        return "数据不足，无法判断", "#999", "#f5f5f5"
    
    total_return = (latest_price - issue_price) / issue_price * 100
    
    # 判断逻辑
    if total_return > 50 and change_pct > 5:
        return "🔴 强势上涨，可考虑追入", "#c62828", "#ffebee"
    elif total_return > 20 and change_pct > 0:
        return "🟡 表现良好，观望等回调", "#e65100", "#fff3e0"
    elif total_return > 0 and change_pct > -3:
        return "🟠 温和上涨，可小仓位", "#f57f17", "#fffde7"
    elif total_return < 0 or change_pct < -5:
        return "🟢 已破发或走弱，不建议追", "#2e7d32", "#e8f5e9"
    else:
        return "⚪ 震荡，建议观望", "#888", "#f5f5f5"

def _parse_date(raw):
    """解析 API 返回的日期：支持 2026-07-10 00:00:00 和 20260710 两种格式"""
    if not raw or str(raw) in ("-", "", "None", "null", "NoneType"):
        return ""
    s = str(raw)[:10].replace("-", "")
    return s if len(s) == 8 else ""

def _to_float(v):
    """安全转 float，失败/None/空返回 0.0"""
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0

def fetch_ipo_list():
    """从东方财富 datacenter API 获取新股列表（push2 API 经常被 ban，改用 datacenter）"""
    candidates = []
    today_str = datetime.now().strftime("%Y%m%d")
    today_int = int(today_str)

    # datacenter API: 按申购日期降序，取最近 60 条
    fields = ("SECURITY_CODE,SECURITY_NAME,TRADE_MARKET_CODE,APPLY_DATE,LISTING_DATE,ISSUE_PRICE,"
              "INDUSTRY_PE_NEW,AFTER_ISSUE_PE,DEC_SUMFINA,ISSUE_NUM,MARKET_TYPE,IS_REGISTRATION,"
              "MAIN_BUSINESS,INDUSTRY_NAME,BVPS,PROFIT,IS_PROFIT,PREDICT_RAISE_FUNDS")
    url = (f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
           f"sortColumns=APPLY_DATE&sortTypes=-1&pageSize=60&pageNumber=1"
           f"&reportName=RPTA_APP_IPOAPPLY&columns={fields}")

    try:
        data = http_get(url)
        if not data.get("success"):
            print(f"  ⚠️ datacenter API 返回失败: {data.get('message', '?')}")
            return candidates

        rows = data.get("result", {}).get("data", [])
        print(f"  ✓ datacenter API: {len(rows)} 条原始记录")
    except Exception as e:
        print(f"  ⚠️ datacenter API 失败: {e}")
        return candidates

    for row in rows:
        code = row.get("SECURITY_CODE", "")
        name = row.get("SECURITY_NAME", "")
        if not code or not name:
            continue

        apply_date = _parse_date(row.get("APPLY_DATE"))
        listing_date = _parse_date(row.get("LISTING_DATE"))
        
        # 取行情补充 PE（datacenter 有 AFTER_ISSUE_PE = 发行后PE）
        issue_price_raw = row.get("ISSUE_PRICE")
        try:
            issue_price = float(issue_price_raw) if issue_price_raw else 0
        except (ValueError, TypeError):
            issue_price = 0

        industry_pe = row.get("INDUSTRY_PE_NEW", 0)
        try:
            industry_pe = float(industry_pe) if industry_pe else 20
        except (ValueError, TypeError):
            industry_pe = 20

        after_issue_pe = row.get("AFTER_ISSUE_PE", 0)
        try:
            after_issue_pe = float(after_issue_pe) if after_issue_pe else 0
        except (ValueError, TypeError):
            after_issue_pe = 0

        # 募集资金（亿）
        dec_sumfina = row.get("DEC_SUMFINA", 0)
        try:
            dec_sumfina = float(dec_sumfina) if dec_sumfina else 0
        except (ValueError, TypeError):
            dec_sumfina = 0

        # ⚠️ 单位修正：北交所API返回的是"元"，科创板/创业板返回的是"亿"
        # 阈值判断：如果原始值 > 1000，说明是元（因为正常IPO募资不会超过1000亿）
        if dec_sumfina > 1000:
            dec_sumfina = dec_sumfina / 1e8  # 元 → 亿

        # 板块判断：优先用 MARKET_TYPE 字段
        market_type = row.get("MARKET_TYPE", "")
        if "科创板" in str(market_type): market_code = "KC"
        elif "创业板" in str(market_type): market_code = "CY"
        elif "北交所" in str(market_type): market_code = "BJ"
        elif "沪市" in str(market_type): market_code = "SH"
        elif "深市" in str(market_type): market_code = "SZ"
        else:
            # fallback to code prefix
            code_str = str(code)
            if code_str.startswith("688"): market_code = "KC"
            elif code_str.startswith("30"): market_code = "CY"
            elif code_str.startswith("92"): market_code = "BJ"
            elif code_str.startswith("00") or code_str.startswith("001"): market_code = "SZ"
            else: market_code = "SH"

        # 状态分类（完整版，区分申购/待上市/上市首日/追踪）
        status = classify_status_v2(apply_date, listing_date, today_int)

        # 隐藏：已过时（上市超过5天且不在未来范围）
        if status == "expired":
            continue

        candidates.append({
            "code": code,
            "name": name,
            "issue_price": round(issue_price, 2) if issue_price > 0 else 0,
            "issue_pe": after_issue_pe,  # AFTER_ISSUE_PE = 发行后市盈率
            "industry_pe": round(industry_pe, 1),
            "market_code": market_code,
            "apply_date": apply_date,
            "listing_date": listing_date,
            "status": status,
            "dec_sumfina": dec_sumfina,  # 募集资金（亿）
            # ── 基本面维度字段（来自 RPTA_APP_IPOAPPLY 通用字段，对所有 IPO 可得）──
            "main_business": (row.get("MAIN_BUSINESS", "") or "").strip(),
            "industry_name": (row.get("INDUSTRY_NAME", "") or "").strip(),
            "bvps": _to_float(row.get("BVPS")),             # 每股净资产
            "profit": _to_float(row.get("PROFIT")),         # 最近一年净利润（万元，多为空）
            "is_profit": row.get("IS_PROFIT"),              # 是否盈利标记（1/0/None）
            "predict_raise_funds": _to_float(row.get("PREDICT_RAISE_FUNDS")),  # 计划募资（亿）
        })

    applying = [c for c in candidates if c["status"] == "applying"]
    pre_listing = [c for c in candidates if c["status"] == "pre_listing"]
    listed = [c for c in candidates if c["status"] == "listed_today"]
    tracking = [c for c in candidates if c["status"] == "tracking"]
    print(f"  ✓ 分类: 待申购={len(applying)} 待上市={len(pre_listing)} 今日上市={len(listed)} 追踪={len(tracking)}")

    return candidates

def classify_status_v2(apply_date, listing_date, today_int):
    """新版状态分类：申购中 / 待上市 / 上市首日 / 追踪 / 过期"""
    if listing_date:
        try:
            list_int = int(listing_date)
            if list_int == today_int:
                return "listed_today"
            if list_int > today_int:
                return "pre_listing"  # 已申购待上市
            if today_int - list_int <= 5:
                return "tracking"
            return "expired"
        except ValueError:
            pass

    if apply_date:
        try:
            apply_int = int(apply_date)
            # 申购日当天或未来 → 待申购
            if apply_int >= today_int:
                return "applying"
            # 申购已过但没上市日期 → 还在等（7天内算待上市）
            if today_int - apply_int <= 7:
                return "pre_listing"
            # 超过7天还没上市日期 → 可能数据异常，也算待上市但不显示太旧
            return "expired"
        except ValueError:
            pass

    return "applying"  # 默认兜底

def score_track(industry, main_business):
    """赛道热度评分(0-40)：基于行业/主营关键词映射，命中高景气赛道给高分"""
    text = f"{industry} {main_business}".lower()
    hot = ["半导体", "芯片", "集成电路", "dram", "存储", "ai", "人工智能", "算力", "机器人",
           "新能源", "储能", "光伏", "创新药", "生物", "疫苗", "医药", "航天",
           "军工", "新材料", "高端装备", "光模块", "cpo", "云计算", "数据",
           "自动驾驶", "锂电池", "固态电池", "无人机", "传感器", "激光", "面板", "光刻"]
    if any(k in text for k in hot):
        return 38, "高景气赛道"
    mid = ["设备", "制造", "电子", "软件", "通信", "医疗", "化工", "汽车",
           "机械", "电气", "计算机", "仪器"]
    if any(k in text for k in mid):
        return 28, "制造/科技赛道"
    return 18, "传统/其他赛道"


def calc_fundamental(c):
    """计算基本面维度评分(0-100)与明细，基于发行披露可得信号。
    说明：未上市新股无统一营收/毛利/研发 API，故用可得信号构建——
    赛道热度(0-40) + 超募比例(0-20) + 估值安全PB(0-20) + 盈利(0-20)。
    字段缺失时给基础分(不罚)，前端标注'基于发行披露'。
    """
    # 1) 赛道热度 0-40
    track_score, track_label = score_track(c.get("industry_name", ""), c.get("main_business", ""))
    # 2) 超募比例 0-20（实际募资/计划募资，反映市场认可度）
    raise_f = c.get("dec_sumfina", 0) or 0
    pred_f = c.get("predict_raise_funds", 0) or 0
    if raise_f and pred_f and pred_f > 0:
        ratio = raise_f / pred_f
        if ratio >= 1.5:
            over, over_label = 20, f"超募{ratio:.1f}倍"
        elif ratio >= 1.2:
            over, over_label = 15, f"超募{ratio:.1f}倍"
        elif ratio >= 1.0:
            over, over_label = 10, "足额募资"
        else:
            over, over_label = 5, f"募资{ratio:.1f}倍计划"
        over_ratio = round(ratio, 2)
    else:
        over, over_label, over_ratio = 10, "募资待定", None  # 无数据不罚
    # 3) 估值安全 PB 0-20（发行价/每股净资产）
    price = c.get("issue_price", 0) or 0
    bvps = c.get("bvps", 0) or 0
    if price > 0 and bvps > 0:
        pb = price / bvps
        if pb < 1:
            pbs, pb_label = 20, f"破净PB{pb:.1f}"
        elif pb < 2:
            pbs, pb_label = 16, f"低PB{pb:.1f}"
        elif pb < 3:
            pbs, pb_label = 12, f"PB{pb:.1f}"
        elif pb < 5:
            pbs, pb_label = 8, f"PB{pb:.1f}"
        else:
            pbs, pb_label = 4, f"高PB{pb:.1f}"
        pb_val = round(pb, 2)
    else:
        pbs, pb_label, pb_val = 10, "PB待定", None
    # 4) 盈利 0-20
    is_profit = c.get("is_profit")
    profit = c.get("profit", 0) or 0
    if is_profit == 1 or profit > 0:
        ps, profit_label = 20, "已盈利"
    elif is_profit == 0 and profit < 0:
        ps, profit_label = 4, "亏损"
    else:
        ps, profit_label = 10, "盈利待披露"  # 无数据不罚
    score = track_score + over + pbs + ps
    return score, {
        "track_label": track_label,
        "main_business": c.get("main_business", ""),
        "industry": c.get("industry_name", ""),
        "over_subscription": over_ratio,
        "over_label": over_label,
        "pb": pb_val,
        "pb_label": pb_label,
        "profitable": (ps == 20),
        "profit_label": profit_label,
        "data_source": "发行披露(营收/毛利/研发需上市后F10补充)",
    }


# ── IPO 情绪/热度因子（2026-08-13 升级） ──

def _load_sector_rs():
    """读取板块相对强弱数据，用于 IPO 行业情绪分。"""
    try:
        path = os.path.join(DATA_DIR, "sector_rs.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data.get("data_available"):
            return None
        sectors = data.get("sectors") or []
        if not sectors:
            return None
        return sectors
    except Exception as e:
        print(f"  ⚠️ 读取 sector_rs.json 失败: {e}")
        return None


def _industry_momentum_score(industry_name, sectors):
    """基于行业近5日/20日涨幅在全市场的排名给分（0-12）。"""
    if not sectors or not industry_name:
        return 8.0
    matched = [s for s in sectors if s.get("name") == industry_name]
    if not matched:
        matched = [s for s in sectors
                   if industry_name in s.get("name", "")
                   or s.get("name", "") in industry_name]
    if not matched:
        return 8.0
    s = matched[0]
    pct_5d = s.get("pct_5d", 0) or 0
    pct_20d = s.get("pct_20d", 0) or 0

    all_5d = sorted([x.get("pct_5d", 0) or 0 for x in sectors])
    all_20d = sorted([x.get("pct_20d", 0) or 0 for x in sectors])

    def _rank_score(val, all_vals, top, mid, low):
        if not all_vals:
            return mid
        rank_pct = sum(1 for v in all_vals if v <= val) / len(all_vals)
        if rank_pct >= 0.8:
            return top
        if rank_pct >= 0.6:
            return top * 0.7
        if rank_pct >= 0.4:
            return mid
        if rank_pct >= 0.2:
            return low
        return low * 0.5

    score_5d = _rank_score(pct_5d, all_5d, 7, 4, 2)
    score_20d = _rank_score(pct_20d, all_20d, 5, 3, 1)
    return round(score_5d + score_20d, 1)


def _load_limit_up_heat():
    """读取涨停heatmap，用于 IPO 行业短线情绪。"""
    try:
        path = os.path.join(DATA_DIR, "limit_up_heatmap.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  ⚠️ 读取 limit_up_heatmap.json 失败: {e}")
        return None


def _limit_up_heat_score(industry_name, heat_data):
    """基于行业近5日涨停数均值排名给分（0-3）。"""
    if not heat_data or not industry_name:
        return 2.0
    sectors = heat_data.get("sectors") or []
    if not sectors:
        return 2.0
    matched = [s for s in sectors if s.get("name") == industry_name]
    if not matched:
        matched = [s for s in sectors
                   if industry_name in s.get("name", "")
                   or s.get("name", "") in industry_name]
    if not matched:
        return 2.0
    s = matched[0]
    data = s.get("data", [])[:-1]  # 去掉今日（盘前可能是0）
    if not data:
        return 2.0
    avg = sum(data) / len(data)
    all_avgs = []
    for x in sectors:
        xd = x.get("data", [])[:-1]
        if xd:
            all_avgs.append(sum(xd) / len(xd))
    if not all_avgs:
        return 2.0

    rank_pct = sum(1 for v in all_avgs if v <= avg) / len(all_avgs)
    if rank_pct >= 0.8:
        return 3
    if rank_pct >= 0.6:
        return 2.5
    if rank_pct >= 0.4:
        return 2
    if rank_pct >= 0.2:
        return 1.5
    return 1


def _oversubscription_sentiment_score(over_ratio):
    """超募倍数反映申购情绪：1.5倍+给高分（0-4）。"""
    if over_ratio is None:
        return 2
    if over_ratio >= 2.0:
        return 4
    if over_ratio >= 1.5:
        return 3
    if over_ratio >= 1.2:
        return 2
    if over_ratio >= 1.0:
        return 1
    return 0.5


def calculate_scores(candidates, status_filter=None):
    """计算申购/待上市新股的评分（双维度：套利分 + 基本面分）
    status_filter: None=全部, 或指定列表如 ["applying", "pre_listing"]

    2026-08-13 升级：heat_score 从固定 15 改为动态情绪分（0-15），
    综合行业近5日/20日涨幅排名、行业涨停heatmap排名、超募倍数，
    更好识别高涨幅潜力标的。
    """
    sector_rs = _load_sector_rs()
    heat_data = _load_limit_up_heat()

    results = []
    for c in candidates:
        if status_filter and c["status"] not in status_filter:
            continue

        price = c["issue_price"]
        board = board_name(c["market_code"])
        industry_pe = c.get("industry_pe", 20)
        industry_name = (c.get("industry_name") or "").strip()

        # 发行PE：优先用 AFTER_ISSUE_PE，否则估算
        issue_pe = c.get("issue_pe", 0) or 0
        if issue_pe <= 0:
            issue_pe = industry_pe * 0.85  # 发行PE通常低于行业PE约15%

        # PE折价评分
        if issue_pe > 0 and industry_pe > 0 and industry_pe > issue_pe:
            pe_discount = round((industry_pe - issue_pe) / industry_pe * 100, 1)
            pe_discount = min(pe_discount, 80)
        else:
            pe_discount = 0
        pe_score = min(40, max(0, pe_discount * 0.5)) if pe_discount > 0 else 0

        # 发行价合理性
        price_score = score_price(price) if price > 0 else 10
        # 板块溢价
        board_bonus = board_score(board)

        # ── 基本面维度（先算，需要其中的超募倍数做情绪分）──
        fundamental_score, fund_detail = calc_fundamental(c)

        # 情绪/热度（0-15）：行业动量 + 涨停heatmap + 超募情绪
        heat_score = min(15, round(
            _industry_momentum_score(industry_name, sector_rs)
            + _limit_up_heat_score(industry_name, heat_data)
            + _oversubscription_sentiment_score(fund_detail.get("over_subscription")),
            1
        ))

        # ── 套利维度 ──
        arbitrage_raw = pe_score + heat_score + price_score + board_bonus
        arbitrage_score = round(min(arbitrage_raw, 90) / 90 * 100)

        # 总分：套利 60% + 基本面 40%
        total = round(arbitrage_score * 0.6 + fundamental_score * 0.4)

        if total >= 80:
            recommend, tag_color, bg_color = "强烈推荐申购", "#2e7d32", "#e8f5e9"
        elif total >= 65:
            recommend, tag_color, bg_color = "建议申购", "#e65100", "#fff3e0"
        elif total >= 50:
            recommend, tag_color, bg_color = "谨慎参与", "#f57f17", "#fffde7"
        else:
            recommend, tag_color, bg_color = "不建议申购", "#c62828", "#ffebee"

        # 价格未知的标注
        # 发行价未知时不再覆盖 recommend；前端已按 issue_price==0 归入「待定价」tab，
        # recommend 保持按 score 阈值生成的建议等级，避免污染 shadowBlock 判断。

        # ── highlights：dims 已渲染发行价/板块/PE折价/PE/行业PE/申购日，这里补独特亮点 ──
        highlights = []
        if c["listing_date"]:
            highlights.append(f"预计{c['listing_date'][4:6]}.{c['listing_date'][6:]}上市")
        if fund_detail.get("track_label") == "高景气赛道":
            highlights.append("高景气赛道")
        if fund_detail.get("over_label", "").startswith("超募"):
            highlights.append(fund_detail["over_label"])
        if fund_detail.get("profit_label") == "已盈利":
            highlights.append("已盈利")
        if c.get("dec_sumfina", 0) >= 1:
            highlights.append(f"募资{c['dec_sumfina']:.0f}亿")
        if board in ("沪市主板", "深市主板"):
            highlights.append(f"{board}流动性溢价")
        if heat_score >= 12:
            highlights.append(f"情绪分{heat_score:.0f}·热度高")
        elif heat_score <= 6:
            highlights.append(f"情绪分{heat_score:.0f}·偏冷")

        actual_status = "pre_listing" if c["status"] == "pre_listing" else "applying"
        results.append({
            "code": c["code"], "name": c["name"],
            "issue_price": price, "issue_pe": round(issue_pe, 2),
            "industry_pe": round(industry_pe, 1), "pe_discount": pe_discount,
            "board": board, "apply_date": c["apply_date"],
            "listing_date": c["listing_date"],
            "score": total, "recommend": recommend,
            "tag_color": tag_color, "bg_color": bg_color,
            # ── 双维度分列：套利分 + 基本面分 + 结构化基本面 ──
            "arbitrage_score": arbitrage_score,
            "fundamental_score": fundamental_score,
            "heat_score": heat_score,
            "fundamentals": fund_detail,
            "highlights": highlights[:5],
            "status": actual_status,
        })
    results.sort(key=lambda x: -x["score"])
    return results

# 保留旧函数名兼容性
calculate_applying_scores = calculate_scores

def process_listed_and_tracking(candidates):
    """处理已上市新股：抓取行情并生成建议。
    优先使用同花顺已提供的行情快照；缺失时尝试东财实时行情；失败亦不丢弃（确保今日上市可见）。
    """
    results = []
    for c in candidates:
        if c["status"] not in ("listed_today", "tracking"):
            continue

        # 1) 优先使用候选中已带有的同花顺行情快照
        latest = c.get("latest_price", 0) or 0
        open_price = c.get("open_price", 0) or 0
        change_pct = c.get("change_pct", 0) or 0
        turnover = c.get("turnover", 0) or 0

        # 2) 快照缺失时再用东财行情补充
        if not latest:
            quote = fetch_realtime_quote(c["code"], c["market_code"])
            if quote:
                latest = quote.get("latest", latest) or latest
                open_price = quote.get("open_price", open_price) or open_price
                change_pct = quote.get("change_pct", change_pct) or change_pct
                turnover = quote.get("turnover", turnover) or turnover

        issue_price = c["issue_price"]
        
        # 计算首日/累计收益率
        if issue_price > 0:
            total_return = round((latest - issue_price) / issue_price * 100, 2)
            open_return = round((open_price - issue_price) / issue_price * 100, 2) if open_price > 0 else 0
        else:
            total_return = 0
            open_return = 0
        
        if c["status"] == "listed_today":
            # 上市首日：展示首日表现（dims已有涨幅/换手率，这里只补充开盘信息）
            recommend = "上市首日"
            tag_color = "#1565c0"
            bg_color = "#e3f2fd"
            highlights = []
            if open_return != total_return and open_return > 0:
                highlights.append(f"开盘涨{open_return}%")
        else:
            # 上市后追踪：给出是否值得追入建议（dims已有涨跌幅/换手/较发行，这里只补充特殊标记）
            advise, tag_color, bg_color = tracking_advice(issue_price, latest, change_pct, turnover)
            recommend = advise
            highlights = []
        
        results.append({
            "code": c["code"], "name": c["name"],
            "issue_price": issue_price,
            "latest_price": latest,
            "open_price": open_price,
            "change_pct": change_pct,
            "turnover": turnover,
            "total_return": total_return,
            "open_return": open_return,
            "board": board_name(c["market_code"]),
            "listing_date": c["listing_date"],
            "score": 0,  # 上市后不评分
            "recommend": recommend,
            "tag_color": tag_color, "bg_color": bg_color,
            "highlights": highlights[:3],
            "status": c["status"],
        })
    return results

def fetch_recent_listed_ths(days=5):
    """从同花顺获取最近 N 天内已上市新股，填补东方财富申购接口不含已上市股的缺口。
    上市日期等于今日 → listed_today；过去 5 日内（不含今日）→ tracking。
    """
    import akshare as ak
    from datetime import datetime, timedelta

    today = datetime.now().date()
    start = today - timedelta(days=days)

    try:
        df = ak.stock_xgsr_ths()
    except Exception as e:
        print(f"  ⚠️ 同花顺上市数据获取失败: {e}")
        return []

    candidates = []
    for _, row in df.iterrows():
        code = str(row.get("股票代码", "")).strip()
        name = str(row.get("股票简称", "")).strip()
        listing_date_raw = row.get("上市日期")
        issue_price = float(row.get("发行价", 0) or 0)

        if not code or not name:
            continue

        # 统一解析上市日期 -> YYYYMMDD
        if isinstance(listing_date_raw, str):
            listing_date = listing_date_raw.replace("-", "")
        else:
            try:
                listing_date = listing_date_raw.strftime("%Y%m%d")
            except Exception:
                continue

        if not listing_date or len(listing_date) != 8:
            continue

        try:
            list_date = datetime.strptime(listing_date, "%Y%m%d").date()
        except ValueError:
            continue

        if not (start <= list_date <= today):
            continue

        # 上市日期等于今日 → listed_today；其余最近 N 日 → tracking
        status = "listed_today" if list_date == today else "tracking"

        # 与 fetch_ipo_list 保持一致的板块判定
        if code.startswith("688"): market_code = "KC"
        elif code.startswith("30"): market_code = "CY"
        elif code.startswith("92"): market_code = "BJ"
        elif code.startswith("00") or code.startswith("001"): market_code = "SZ"
        else: market_code = "SH"

        # 同花顺已提供最新价/开盘价/涨跌幅，优先保存避免东财行情接口失败
        ths_latest = float(row.get("最新价", 0) or 0)
        ths_open = float(row.get("首日开盘价", 0) or 0)
        ths_change = float(row.get("首日涨跌幅", 0) or 0)

        candidates.append({
            "code": code,
            "name": name,
            "issue_price": round(issue_price, 2) if issue_price > 0 else 0,
            "issue_pe": 0,
            "industry_pe": 20,
            "market_code": market_code,
            "apply_date": "",
            "listing_date": listing_date,
            "status": status,
            "dec_sumfina": 0,
            "main_business": "",
            "industry_name": "",
            "bvps": 0,
            "profit": 0,
            "is_profit": None,
            "predict_raise_funds": 0,
            # 同花顺行情快照（东财接口不可用时兜底）
            "latest_price": ths_latest,
            "open_price": ths_open,
            "change_pct": ths_change,  # 同花顺已为小数形式（4.0252 = 402.52%）
            "turnover": 0,
        })

    print(f"  ✓ 同花顺最近{days}日上市: {len(candidates)} 只")
    return candidates


def generate_summary(applying, pre_listing, listed, tracking):
    """生成综合打新判断"""
    parts = []
    if applying:
        high = sum(1 for r in applying if r["score"] >= 80)
        mid = sum(1 for r in applying if 65 <= r["score"] < 80)
        if high > 0: parts.append(f"{high}只强烈推荐申购")
        if mid > 0: parts.append(f"{mid}只建议申购")
        if not parts: parts.append(f"{len(applying)}只待评估")
    
    if pre_listing:
        parts.append(f"{len(pre_listing)}只待上市")

    if listed:
        parts.append(f"今日{len(listed)}只上市")
    
    if tracking:
        strong = sum(1 for r in tracking if r.get("total_return", 0) > 20)
        if strong > 0: parts.append(f"{strong}只上市后表现强势")
    
    if not parts:
        return "当前无可关注新股，建议关注后续IPO安排。"
    
    return f"{'，'.join(parts)}。"

def generate_ipo_score():
    """抓取并计算打新评分，返回 v8 前端需要的 dict（不直接写文件）。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    print("=" * 50)
    print("v8 打新价值评分数据获取（申购+上市+追踪）")
    print("=" * 50)

    # 1. 获取新股列表
    print("[1/5] 获取新股列表...")
    candidates = fetch_ipo_list()

    # 1.5 补充/校正同花顺已上市新股（东财行情接口不稳定时，用同花顺行情快照兜底）
    print("[1.5/5] 补充同花顺已上市新股...")
    ths_listed = fetch_recent_listed_ths(days=5)
    existing = {c["code"]: c for c in candidates}
    for c in ths_listed:
        if c["code"] not in existing:
            candidates.append(c)
            existing[c["code"]] = c
        else:
            # 同花顺对已上市股更准确：覆盖状态、上市日期、行情快照
            old = existing[c["code"]]
            old["status"] = c["status"]
            old["listing_date"] = c["listing_date"] or old["listing_date"]
            old["issue_price"] = c["issue_price"] or old["issue_price"]
            for k in ["latest_price", "open_price", "change_pct", "turnover"]:
                if c.get(k):
                    old[k] = c[k]

    applying_list = [c for c in candidates if c["status"] == "applying"]
    pre_listing_list = [c for c in candidates if c["status"] == "pre_listing"]
    listed_list = [c for c in candidates if c["status"] == "listed_today"]
    tracking_list = [c for c in candidates if c["status"] == "tracking"]

    print(f"  待申购: {len(applying_list)}, 待上市: {len(pre_listing_list)}, 今日上市: {len(listed_list)}, 追踪中: {len(tracking_list)}")

    # 2. 获取可转债列表
    print("[2/5] 获取可转债列表...")
    bond_candidates = fetch_bond_list()

    bond_applying = [b for b in bond_candidates if b["status"] == "applying"]
    bond_pre_listing = [b for b in bond_candidates if b["status"] == "pre_listing"]
    bond_listed = [b for b in bond_candidates if b["status"] == "listed_today"]
    bond_tracking = [b for b in bond_candidates if b["status"] == "tracking"]

    # 3. 补充待申购/待上市新股的详细数据（PE等）
    print("[3/5] 补充待申购/待上市新股详情...")
    need_detail = applying_list + pre_listing_list
    for c in need_detail:
        if c["issue_price"] <= 0 or c["issue_pe"] <= 0:
            detail = fetch_realtime_quote(c["code"], c["market_code"])
            if detail and detail.get("prev_close") > 0 and c["issue_price"] <= 0:
                c["issue_price"] = round(detail["prev_close"], 2)
            time.sleep(0.3)

    # 4. 计算待申购+待上市评分
    print("[4/5] 计算评分...")
    applying_results = calculate_scores(applying_list, status_filter=["applying"])
    pre_listing_results = calculate_scores(pre_listing_list, status_filter=["pre_listing"])

    # 可转债评分
    bond_applying_results = calculate_bond_scores(bond_applying + bond_pre_listing)
    bond_applying_r = [b for b in bond_applying_results if b["status"] == "applying"]
    bond_pre_listing_r = [b for b in bond_applying_results if b["status"] == "pre_listing"]

    # 5. 处理已上市/追踪中的新股
    print("[5/5] 获取已上市新股+可转债行情...")
    listed_results = process_listed_and_tracking(listed_list)
    tracking_results = process_listed_and_tracking(tracking_list)

    # 可转债上市/追踪行情
    bond_listed_results = process_bond_listed(bond_listed)
    bond_tracking_results = process_bond_listed(bond_tracking)

    # 合并所有结果
    all_results = (applying_results + pre_listing_results + listed_results + tracking_results +
                   bond_applying_r + bond_pre_listing_r + bond_listed_results + bond_tracking_results)

    summary = generate_summary(applying_results, pre_listing_results, listed_results, tracking_results)
    bond_total = len(bond_applying_r) + len(bond_pre_listing_r) + len(bond_listed_results) + len(bond_tracking_results)
    if bond_total > 0:
        summary += f" 📋 可转债{len(bond_applying_r)}待申购" + (f"，{len(bond_listed_results)}只今日上市" if bond_listed_results else "")

    return {
        "update_time": now,
        "eligible_count": len(applying_results),
        "pre_listing_count": len(pre_listing_results),
        "listed_count": len(listed_results),
        "tracking_count": len(tracking_results),
        "summary": summary,
        "stocks": all_results,
    }


def main():
    """命令行入口：写 raw_data/ipo_score.json，并做数据保护（新空旧有则保留旧）。"""
    ipo_data = generate_ipo_score()
    all_results = ipo_data.get("stocks", [])

    out_path = os.path.join(DATA_DIR, "ipo_score.json")
    old_data = None
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            pass

    # 新数据完全为空但旧数据有股票 → 保留旧数据
    if not all_results and old_data and old_data.get("stocks"):
        print(f"  ⚠️ 新股API返回空结果，保留已有数据（{len(old_data['stocks'])}只）")
        old_data["update_time"] = ipo_data.get("update_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        ipo_data = old_data

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ipo_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 写入 {out_path}")
    print(f"   总计 {len(ipo_data.get('stocks', []))} 只（新股+可转债）")
    print(f"\n💡 {ipo_data.get('summary', '')}")


if __name__ == "__main__":
    main()
