#!/usr/bin/env python3
# intraday_snapshot.py — 独立的「板块资金流向日内快照」追加器（轻量 / 解耦 / 幂等 / 可重试）
#
# 🛡 2026-08-27 主人令一劳永逸式修复（盘中快照随重抓取被 cancel / 漏触发而断档的根因）：
#   原快照追加写在 cloud_fetch_v8.py f_sector_fund_flow() 内 —— 重抓取整轮 ~23 分钟、极易被
#   cancel 风暴杀掉（13:30 档被 cancel）或压根没触发（14:00 档）。重抓取一挂，快照随之丢失
#   → 板块资金日内曲线断档（主人实锤：13:22 后主站曲线停更）。
#
#   现彻底解耦：本脚本只读「已提交的 raw_data/sector_fund_flow.json」（重抓取每 30 分提交一次，
#   健康时快照用 ≤30 分钟新鲜数据；重抓取挂了也只是用上次提交值 → 曲线连续不断、绝不空窗），
#   追加一笔快照，并直接生成 data/SECTOR_FUND_FLOW_INTRADAY.js 推送。
#
#   不依赖 akshare / pandas，仅 stdlib + 单次东方财富小请求（取上证涨跌幅，失败则记 0），
#   秒级完成。由 workflow 的「intraday-snapshot」独立并发组 + 重试驱动，
#   绝不会被重抓取的取消风暴波及。
import os
import sys
import json
import datetime
import urllib.request
import urllib.error
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")
_BASE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(_BASE, "raw_data")
INTRADAY_PATH = os.path.join(RAW_DIR, "sector_fund_flow_intraday.json")
SECTOR_PATH = os.path.join(RAW_DIR, "sector_fund_flow.json")
DATA_DIR = os.path.join(_BASE, "data")
DATA_PATH = os.path.join(DATA_DIR, "SECTOR_FUND_FLOW_INTRADAY.js")

# 噪声概念（与 cloud_fetch_v8._NOISE_CONCEPTS 对齐）：境外指数/成分标签不是真实 A 股概念板块
_NOISE = {
    "融资融券", "深股通", "沪股通", "昨日高振幅", "富时罗素", "MSCI中国",
    "深成500", "标准普尔", "HS300_", "中证500", "上证50", "上证180",
    "标普道琼斯", "QFII重仓", "上证380", "上证100", "央视50", "环球影城",
}


def now_cst():
    return datetime.datetime.now(CST)


def get_index_chg():
    """取上证指数涨跌幅%（用于双轴对照）。失败返回 0.0，绝不强依赖。"""
    try:
        url = "https://push2.eastmoney.com/api/qt/stock/get?secid=1.000001&fields=f3&fltt=2"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            j = json.loads(r.read().decode("utf-8"))
        f = j.get("data", {}).get("f3")
        return round(float(f), 2) if f is not None else 0.0
    except Exception:
        return 0.0


def main():
    t = now_cst()
    hhmm = t.strftime("%H:%M")
    today = t.strftime("%Y-%m-%d")

    # 🛡 交易时段守卫：仅 09:25–16:05 写快照，杜绝盘前/盘后离群点污染曲线
    if not ("09:25" <= hhmm <= "16:05"):
        print(f"⏭️ 非交易时段 {hhmm}，跳过板块资金日内快照")
        return 0

    if not os.path.exists(SECTOR_PATH):
        print(f"⚠️ 缺少 {SECTOR_PATH}，跳过（重抓取尚未提交板块数据，稍后下一档补齐）")
        return 0
    try:
        sector = json.loads(open(SECTOR_PATH, encoding="utf-8").read())
    except Exception as e:
        print(f"⚠️ 读取 sector_fund_flow.json 失败: {e}")
        return 0

    si = sector.get("sectors_in", []) or []
    so = sector.get("sectors_out", []) or []
    if not si and not so:
        print("⚠️ sector_fund_flow.json 无 sectors_in/out，跳过（数据暂空）")
        return 0

    idx_chg = get_index_chg()
    top_in = [{"name": s["name"], "net": round(float(s.get("net", 0)), 2)}
              for s in si[:15] if s.get("name") not in _NOISE]
    top_out = [{"name": s["name"], "net": round(float(s.get("net", 0)), 2)}
               for s in so[:5] if s.get("name") not in _NOISE]

    snap = {"time": hhmm, "sectors_in": top_in, "sectors_out": top_out, "index_chg": idx_chg}

    # 读取 / 合并（盘日切换则清空旧数据）
    data = {"date": today, "snapshots": []}
    if os.path.exists(INTRADAY_PATH):
        try:
            ex = json.loads(open(INTRADAY_PATH, encoding="utf-8").read())
            if ex.get("date") == today and isinstance(ex.get("snapshots"), list):
                data = ex
        except Exception:
            # 主文件损坏 → 尝试 .bak 恢复，而非静默重置清空（曾致午后丢失）
            bak = INTRADAY_PATH + ".bak"
            if os.path.exists(bak):
                try:
                    ex = json.loads(open(bak, encoding="utf-8").read())
                    if ex.get("date") == today and isinstance(ex.get("snapshots"), list):
                        data = ex
                        print("↩️ 从 .bak 恢复 intraday（主文件读取损坏）")
                except Exception:
                    pass
    if not isinstance(data.get("snapshots"), list):
        data["snapshots"] = []
    data["date"] = today

    # 幂等：同时间快照覆盖而非重复追加（杜绝双机/重试导致的重复快照）
    times = {s.get("time") for s in data["snapshots"]}
    if hhmm in times:
        for i, s in enumerate(data["snapshots"]):
            if s.get("time") == hhmm:
                data["snapshots"][i] = snap
                break
    else:
        data["snapshots"].append(snap)

    # 保留最近 80 个快照（约 13 小时 × 10min，足够覆盖延时长交易）
    if len(data["snapshots"]) > 80:
        data["snapshots"] = data["snapshots"][-80:]



    data["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M:%S")  # 🛡 每次快照刷新，根治盘中超 4h 假陈旧

    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # 先写临时文件再原子 rename，避免被取消中途杀掉留下半截 JSON
    tmp = INTRADAY_PATH + ".tmp"
    open(tmp, "w", encoding="utf-8").write(blob)
    os.replace(tmp, INTRADAY_PATH)
    try:
        open(INTRADAY_PATH + ".bak", "w", encoding="utf-8").write(blob)
    except Exception:
        pass

    # 直接生成 data/SECTOR_FUND_FLOW_INTRADAY.js（与 update_v8 同构：window.X = raw）
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.SECTOR_FUND_FLOW_INTRADAY = " + blob + ";\n")

    print(f"📈 板块资金日内快照 {hhmm}（{len(top_in)}进{len(top_out)}出, 指数{idx_chg:+.2f}%）→ 已写 raw + data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
