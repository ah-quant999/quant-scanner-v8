#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
refresh_stock_metadata.py — 周度全量股票基础元数据巡检
============================================================
由 v8_weekend_light.py 在周末调用（不抓行情，只更新基础映射）。
职责：
  1. 调用 fetch_stock_names.py 拉取当前 A 股 + 港股全量列表；
  2. 与 raw_data/stock_names.json 比对，识别新股上市 / 退市股；
  3. 为新股补充 industry/board/concepts/pinyin 到静态映射文件；
  4. 退市股写入 raw_data/delisted_stocks.json，保留最后已知的板块/行业；
  5. 把最新列表提升为 raw_data/stock_names.json，供 update_v8.py → STOCK_LIST。

注意：本脚本不修改任何行情类数据时间戳，周末可安全运行。
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "out"
RAW = BASE / "raw_data"
ALGO = BASE / "algorithms"

META_FILE = ALGO / "stock_industry_concepts.json"
PINYIN_FILE = ALGO / "stock_pinyin.json"
DELISTED_FILE = RAW / "delisted_stocks.json"
REPORT_FILE = RAW / "weekend_meta_report.json"


def _load_json(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=0)


def _board_of_a(code):
    """A股/北交所代码 → 上市板。"""
    c = re.sub(r"[^0-9]", "", str(code))
    if not c:
        return ""
    if c.startswith(("600", "601", "603", "605", "000", "001", "002", "003")):
        return "主板"
    if c.startswith(("300", "301")):
        return "创业板"
    if c.startswith(("688", "689")):
        return "科创板"
    if c.startswith(("8", "4", "92")):
        return "北交所"
    return ""


def _run_fetch_stock_names():
    """调用 fetch_stock_names.py，让它按自己的降级链路产出 out/stock_names.json。"""
    script = ALGO / "fetch_stock_names.py"
    if not script.exists():
        raise FileNotFoundError(f"缺失 {script}")
    print(f"  ▶ 运行 {script.name} ...")
    r = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(BASE),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=600,
    )
    # 打印末尾摘要
    tail = "\n".join((r.stdout or "").strip().splitlines()[-5:])
    if tail:
        print("     " + tail.replace("\n", "\n     "))
    if r.returncode != 0:
        err = "\n".join((r.stderr or "").strip().splitlines()[-5:])
        print(f"     ⚠️ 退出码 {r.returncode}: {err}")
        return False
    return True


def _fetch_ipo_meta_eastmoney(code):
    """
    尝试从东方财富获取新股行业。优先 akshare，失败则 requests 直接调接口。
    返回 dict：可能含 industry / board / concepts(list)。
    """
    result = {}
    # 1) akshare
    try:
        import akshare as ak

        df = ak.stock_individual_info_em(symbol=code)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                item = str(row.get("item", "")).strip()
                value = str(row.get("value", "")).strip()
                if item == "行业" and value:
                    result["industry"] = value
                if item == "板块" and value:
                    result["board"] = value
    except Exception as e:
        print(f"     akshare 个股信息({code})失败: {e}")

    # 2) 直接请求东财概念/行业接口（概念可能分散在多个接口，这里取核心行业）
    if not result.get("industry"):
        try:
            import requests

            market = "1" if code.startswith(("6", "68", "69")) else "0"
            url = (
                "https://push2.eastmoney.com/api/qt/stock/get"
                f"?secid={market}.{code}&fields=f43,f44,f45,f57,f58,f60,f107,f116,f117,f162"
            )
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            data = r.json().get("data", {})
            if data.get("f58"):
                # f107 行业（不一定稳定，备用）
                pass
        except Exception as e:
            print(f"     东财个股信息({code})失败: {e}")

    return result


def _generate_pinyin(name):
    """
    生成拼音首字母。优先 pypinyin（若 runner 已装），否则纯字母 fallback。
    """
    if not name:
        return ""
    try:
        from pypinyin import lazy_pinyin

        return "".join([p[0].lower() for p in lazy_pinyin(name) if p]).lower()
    except Exception:
        # fallback：仅保留名称中的 a-z 字母
        return "".join([c.lower() for c in name if "a" <= c.lower() <= "z"])


def _code_key(stock):
    return str(stock.get("code", "")).strip()


def _normalize_list(data):
    if isinstance(data, dict):
        return data.get("data", data.get("stocks", []))
    return data or []


def main():
    print("=" * 60)
    print("  周度股票基础元数据巡检")
    print("=" * 60)

    old_raw = _normalize_list(_load_json(RAW / "stock_names.json", []))
    old_by_code = {_code_key(s): s for s in old_raw}

    # 1. 抓取最新全量列表
    if not _run_fetch_stock_names():
        print("  ❌ fetch_stock_names 失败，停止元数据巡检")
        return 1

    fresh = _normalize_list(_load_json(OUT / "stock_names.json", []))
    fresh_by_code = {_code_key(s): s for s in fresh}

    # 2. 比对 IPO / 退市
    ipos = [s for c, s in fresh_by_code.items() if c and c not in old_by_code]
    delisted = [s for c, s in old_by_code.items() if c and c not in fresh_by_code]

    print(f"\n  比对结果：新股 {len(ipos)} 只，退市 {len(delisted)} 只，当前总数 {len(fresh)}")

    # 🛡 2026-09-01 主人令一劳永逸：退市判定「合理性护栏」
    # ------------------------------------------------------------------
    # 事故复盘：上面的退市判定是「昨日全量列表 − 今日全量列表」的裸差集，零阈值护栏。
    #   当 fetch_stock_names 某轮口径塌缩（网络/接口异常只返回单一市场）时，
    #   另一市场的全部在市股票会被整体判成"退市"并归档，且 build_delisted 下游按
    #   existing_delisted_codes 去重 ⇒ 污染写进去就永久留存、无法自愈。
    #   实际后果（已确认）：
    #     · 2026-08-19 整个港股主板被归档（00001 长和 / 00002 中电控股 / 00005 汇丰控股…）
    #     · 2026-08-27 整个 A 股主板被归档（600000 浦发银行 / 600028 中国石化 / 600036 招商银行…）
    #     · raw_data/delisted_stocks.json 累计污染 7935 条，前端「已下架股票目录」长期展示在市蓝筹
    # 护栏三条，任一触发即放弃本轮「退市归档 + 列表提升」（其余流程照常，不阻断周度巡检）：
    #   ① fresh 总数过小（< 1000）→ 抓取明显失败
    #   ② fresh < old 的 90% → 口径塌缩
    #   ③ 单轮退市数 > max(20, old 的 1%) → 真实退市每交易日仅 0~5 只，超阈值必属误判
    # ------------------------------------------------------------------
    _old_n, _fresh_n = len(old_by_code), len(fresh_by_code)
    _max_delist = max(20, int(_old_n * 0.01))
    _guard_hits = []
    if _fresh_n < 1000:
        _guard_hits.append(f"fresh 总数过小({_fresh_n} < 1000)，fetch_stock_names 疑似失败")
    if _old_n and _fresh_n < _old_n * 0.9:
        _guard_hits.append(f"口径塌缩：fresh({_fresh_n}) < old({_old_n}) 的 90%")
    if len(delisted) > _max_delist:
        _guard_hits.append(f"单轮退市 {len(delisted)} 只 > 阈值 {_max_delist} 只（真实退市每日 0~5 只）")

    _guard_tripped = bool(_guard_hits)
    if _guard_tripped:
        print("  🛡 退市归档护栏触发 —— 本轮放弃退市归档与列表提升：")
        for _m in _guard_hits:
            print(f"     ✗ {_m}")
        print("     → raw_data/stock_names.json 保持原样，等下一轮全量列表抓取正常后再比对。")
        # ⚠️ 一劳永逸：护栏触发时必须**主动清空**已被污染的累加文件 delisted_stocks.json。
        #    仅「跳过写入」不够——历史误判已写进该文件（如 7935/2806 条在市蓝筹），它作为
        #    累加源会永久存活、被 CI 的 build_delisted 反复重建上线。放空它，下一轮
        #    build_delisted 才会产出 total:0，误判展示彻底消失。
        try:
            _old_n_bad = len(_load_json(DELISTED_FILE, []))
        except Exception:
            _old_n_bad = -1
        if _old_n_bad > 0:
            _save_json(DELISTED_FILE, [])
            print(f"     🧹 已清空被污染的 delisted_stocks.json（原 {_old_n_bad} 条），毒库不再参与后续重建。")
        else:
            print("     ℹ️ delisted_stocks.json 当前已为空，无需清空。")
        delisted = []
        ipos = []

    # 3. 为新股补全静态映射
    meta_map = _load_json(META_FILE, {})
    pinyin_map = _load_json(PINYIN_FILE, {})
    enriched = 0

    for s in ipos:
        code = _code_key(s)
        if not code:
            continue
        existing = meta_map.get(code) or {}
        needs_update = False

        # 行业/板块缺失时抓取
        if not existing.get("industry"):
            m = _fetch_ipo_meta_eastmoney(code)
            if m.get("industry"):
                board = m.get("board") or existing.get("board") or _board_of_a(code) or s.get("board", "")
                meta_map[code] = {
                    "industry": m["industry"],
                    "board": board,
                    "concepts": existing.get("concepts", []),
                }
                needs_update = True
        # 拼音缺失时生成
        if code not in pinyin_map:
            py = _generate_pinyin(s.get("name", ""))
            if py:
                pinyin_map[code] = py
                needs_update = True

        if needs_update:
            enriched += 1

    if enriched:
        _save_json(META_FILE, meta_map)
        _save_json(PINYIN_FILE, pinyin_map)
        print(f"  ✅ 为 {enriched} 只新股补全了行业/拼音静态映射")
        # 重新跑一次 fetch，让新映射附着到 stock_names
        _run_fetch_stock_names()
        fresh = _normalize_list(_load_json(OUT / "stock_names.json", []))
    else:
        print("  ℹ️ 无需补全新股元数据")

    # 4. 退市股归档
    delisted_records = _load_json(DELISTED_FILE, [])
    existing_delisted_codes = {str(d.get("code", "")).strip() for d in delisted_records}
    today_str = datetime.now().strftime("%Y-%m-%d")
    for s in delisted:
        code = _code_key(s)
        if not code or code in existing_delisted_codes:
            continue
        delisted_records.append({
            "code": code,
            "name": s.get("name", ""),
            "delisted_date": today_str,
            "last_board": s.get("board", ""),
            "last_industry": s.get("industry", ""),
        })
    if delisted:
        _save_json(DELISTED_FILE, delisted_records)
        print(f"  ✅ 已归档 {len(delisted)} 只退市股到 {DELISTED_FILE}")

    # 5. 提升为 raw_data/stock_names.json
    # 🛡 2026-09-01 护栏联动：口径塌缩时若仍提升，下一轮会把塌缩后的列表当成"昨日基准"，
    #   污染从"单轮误判"升级为"基准被改写"，后续再也判不出真实退市。故护栏触发时不提升。
    if _guard_tripped:
        print("  🛡 护栏触发 → 跳过 raw_data/stock_names.json 提升（保留上一轮可信基准）")
    else:
        _save_json(RAW / "stock_names.json", fresh)
        print(f"  ✅ 已提升 raw_data/stock_names.json（{len(fresh)} 只）")

    # 6. 写巡检报告
    report = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(fresh),
        "new_listings_count": len(ipos),
        "delisted_count": len(delisted),
        "new_listings": [f"{_code_key(s)} {s.get('name','')}" for s in ipos[:50]],
        "delisted": [f"{_code_key(s)} {s.get('name','')}" for s in delisted[:50]],
        "meta_enriched": enriched,
        # 🛡 2026-09-01：护栏审计字段，便于运维面板/看门狗判断本轮是否被护栏拦下
        "guard_tripped": _guard_tripped,
        "guard_reasons": _guard_hits,
        "old_universe": _old_n,
        "fresh_universe": _fresh_n,
    }
    _save_json(REPORT_FILE, report)
    print(f"  ✅ 巡检报告 → {REPORT_FILE}")

    print("\n  完成。")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
