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


def _load_today_intraday(today):
    """读当日 intraday 原始档（主文件 → .bak 回退）。非当日/损坏一律返回 None。"""
    for p in (INTRADAY_PATH, INTRADAY_PATH + ".bak"):
        if not os.path.exists(p):
            continue
        try:
            ex = json.loads(open(p, encoding="utf-8").read())
        except Exception:
            continue
        if ex.get("date") == today and isinstance(ex.get("snapshots"), list):
            return ex
    return None


def _write_outputs(data):
    """原子写 raw_data/sector_fund_flow_intraday.json（+ .bak）与 data/SECTOR_FUND_FLOW_INTRADAY.js。
    先写临时文件再 rename，避免被取消中途杀掉留下半截 JSON。"""
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    tmp = INTRADAY_PATH + ".tmp"
    open(tmp, "w", encoding="utf-8").write(blob)
    os.replace(tmp, INTRADAY_PATH)
    try:
        open(INTRADAY_PATH + ".bak", "w", encoding="utf-8").write(blob)
    except Exception:
        pass
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write("window.SECTOR_FUND_FLOW_INTRADAY = " + blob + ";\n")


def _purge_after_close(today):
    """🛡 2026-09-29 一劳永逸（小九）：幂等「盘后离群点」归并。

    根因：原时段守卫上界 16:05 过宽（A股 15:00 收盘）⇒ 15:00 之后的运行（fetch 链
      workflow_run 触发）把 15:29/15:59/16:03 这些**盘后点**也写进曲线，x 轴出现
      「非交易时段刻度」（主人 09-29 实拍「快照 15:29 → 16:03 不对」）。
    修法：把当日 snapshots 中所有 time > "15:00" 的点**归并为一个 "15:00" 收盘点**
      （取其最后一个盘后点的数值 —— A股 15:00 收盘后 sector_fund_flow 的累计净额本就
      是收盘口径，语义正确），而非直接删除（直接删会让当日曲线整体变空）。
    ⚠️ 必须在**时段守卫之前**调用：否则 15:05 后脚本直接 return，永远清不到脏点。
    幂等：无越界点时不写盘（返回 False）。"""
    ex = _load_today_intraday(today)
    if not ex:
        return False
    snaps = ex.get("snapshots") or []
    late = [s for s in snaps if str(s.get("time") or "") > "15:00"]
    if not late:
        return False
    merged = dict(late[-1])
    merged["time"] = "15:00"
    snaps = [s for s in snaps if str(s.get("time") or "") <= "15:00"]
    if any(str(s.get("time") or "") == "15:00" for s in snaps):
        snaps = [(merged if str(s.get("time") or "") == "15:00" else s) for s in snaps]
    else:
        snaps.append(merged)
    ex["snapshots"] = snaps
    ex["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M:%S")
    _write_outputs(ex)
    print("🧹 已归并 %d 个盘后离群点（%s）→ 15:00 收盘点"
          % (len(late), "/".join(str(s.get("time")) for s in late)))
    return True


def main():
    t = now_cst()
    hhmm = t.strftime("%H:%M")
    today = t.strftime("%Y-%m-%d")

    # 🛡 自愈①（2026-09-29）：归并盘后离群点 —— 必须放在时段守卫**之前**，
    #   否则 15:05 后脚本直接 return，已污染的盘后点永远清不掉。
    _purge_after_close(today)

    # 🛡 交易时段守卫：仅 09:25–15:05 写快照（A股 09:30 开盘 / 15:00 收盘，两端各留 5 分钟余量）。
    #   2026-09-29 修：上界原为 16:05（过宽）⇒ 15:00 后的运行点（15:29/15:59/16:03）污染曲线。
    if not ("09:25" <= hhmm <= "15:05"):
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

    # 🛡 2026-09-02 主人令一劳永逸：口径守卫 —— 只接受「今日」抓取的板块数据。
    #   原逻辑额外卡 update_time 时刻 ≥09:30，但开盘前累计数据的 update_time 本就是【昨天】，
    #   已被上面「startswith(today)」拦掉；保留"今天"检查即可，去掉 09:30 硬门槛。
    #   否则 9:30 后首笔今日盘中数据（09:25-09:30 集合竞价后）会被误判"开盘前"整段跳过
    #   → 上午前段空白（主人 2026-09-10 实锤「上午数据都没出来过」）。宁缺毋滥仅针对跨日口径，
    #   同日内开盘后数据一律可写。
    _src_ts = str(sector.get("update_time") or "")
    if not _src_ts.startswith(today):
        print(f"⏭️ 板块数据源非今日口径（update_time={_src_ts or '空'}），跳过写快照")
        return 0
    # 🛡 2026-09-10 主人令修复「上午数据空白」：陈旧阈值 40→90min。
    #   原 40min 太严——某档 intraday 抓取失败/延迟时，后续 40min 内快照脚本全因"数据陈旧"跳过
    #   → 上午曲线断成 1 个点。90min 覆盖"跳过 1-2 档"（每档 ~20min）的情况，
    #   宁可写稍旧点保曲线连续，也不空白。
    try:
        _src_dt = datetime.datetime.strptime(_src_ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CST)
        _age_min = (t - _src_dt).total_seconds() / 60.0
        if _age_min > 90:
            print(f"⏭️ 板块数据已陈旧（update_time={_src_ts}，距今 {_age_min:.0f} 分钟），跳过写快照")
            return 0
    except Exception:
        pass

    idx_chg = get_index_chg()
    top_in = [{"name": s["name"], "net": round(float(s.get("net", 0)), 2)}
              for s in si[:15] if s.get("name") not in _NOISE]
    top_out = [{"name": s["name"], "net": round(float(s.get("net", 0)), 2)}
               for s in so[:5] if s.get("name") not in _NOISE]

    # 🛡 2026-09-29：收盘归位 —— 15:00 后的运行点统一记作 "15:00"（A股收盘），
    #   避免 x 轴出现 15:01–15:05 这类非交易刻度；同刻幂等覆盖。
    _snap_hhmm = "15:00" if hhmm > "15:00" else hhmm
    snap = {"time": _snap_hhmm, "sectors_in": top_in, "sectors_out": top_out, "index_chg": idx_chg}

    # 读取 / 合并（盘日切换则清空旧数据；主文件损坏自动回退 .bak —— 复用 _load_today_intraday）
    data = _load_today_intraday(today) or {"date": today, "snapshots": []}

    # 🧹 2026-09-02 主人令一劳永逸：自愈清理 —— 剔除当日「口径断裂」的历史快照（幂等，每次运行都收敛）。
    #   判据：某快照的 sectors_in 板块名单与「当日最新一档」零交集 → 两者不是同一口径
    #   （典型：开盘前档写的是昨日收盘累计「互联网金融/农林牧渔」，盘中档是「线缆/铜缆/国防军工」）。
    #   这类点与后段画不成同一条累计曲线，且会撑爆 Y 轴 → 直接剔除，让曲线只保留同一口径的连续点。
    if len(data["snapshots"]) >= 2:
        _latest = data["snapshots"][-1]
        _l_names = {x.get("name") for x in (_latest.get("sectors_in") or []) if x.get("name")}
        if _l_names:
            _keep = []
            for s in data["snapshots"]:
                _s_names = {x.get("name") for x in (s.get("sectors_in") or []) if x.get("name")}
                if _s_names and not (_s_names & _l_names):
                    print(f"🧹 剔除口径断裂快照 {s.get('time')}（板块名单与最新档零交集，非同一口径）")
                    continue
                _keep.append(s)
            if len(_keep) != len(data["snapshots"]):
                data["snapshots"] = _keep

    # 幂等：按「归位后时刻」覆盖而非重复追加（杜绝双机/重试/盘后归位导致的重复快照，
    # 尤其 15:01–15:05 多次运行若不按 _snap_hhmm 比对会追加第二个 "15:00" 重影点）
    times = {s.get("time") for s in data["snapshots"]}
    if _snap_hhmm in times:
        for i, s in enumerate(data["snapshots"]):
            if s.get("time") == _snap_hhmm:
                data["snapshots"][i] = snap
                break
    else:
        data["snapshots"].append(snap)

    # 保留最近 80 个快照（约 13 小时 × 10min，足够覆盖延时长交易）
    if len(data["snapshots"]) > 80:
        data["snapshots"] = data["snapshots"][-80:]



    data["update_time"] = now_cst().strftime("%Y-%m-%d %H:%M:%S")  # 🛡 每次快照刷新，根治盘中超 4h 假陈旧

    # 原子写 raw_data + data js（复用 _write_outputs：主文件→.bak 回退→.js 一致）
    _write_outputs(data)

    print(f"📈 板块资金日内快照 {hhmm}（{len(top_in)}进{len(top_out)}出, 指数{idx_chg:+.2f}%）→ 已写 raw + data")
    return 0


if __name__ == "__main__":
    sys.exit(main())
