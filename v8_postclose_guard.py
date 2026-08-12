# -*- coding: utf-8 -*-
"""
九宝量化 v8.0 — 盘后数据守护脚本
================================
作用：检测 lemoncat-cn runner 是否离线 / 盘后关键数据是否陈旧，
      一旦发现缺失就自动 dispatch 补救。

设计原则（落实主人「发现就马上修正」要求）：
- 幂等：只在「交易日 且 已过 15:30 CST 且 盘后数据非今日」时才 action；
- 自带 runner 离线检测，离线时只告警不空转；
- 不依赖本地 git，全走 GitHub REST API（本机仅 api.github.com 可达）。

🔴 2026-08-07 根因修复（勿回退）：
   旧版只监控 3 个 fetch 产物（MARKET_FUND_FLOW / EXPERIMENT），
   而真正会陈旧的是「盘后算法链产物」——候选池/黄金池/龙虎榜/机构买卖/
   三重共识/市场温度计/市场提示（这些由 v8_algo_run.yml 产出，
   旧版 POST_CLOSE_FILES 一个都没覆盖）→ 算法链一断就漏检，站点静默陈旧数天。
   同时旧版只 dispatch 到 cn 自托管 runner (v8_cn_fetch.yml)，
   该 runner 一离线 dispatch 就排队空转、永不执行（= 文档所述
   "post_close self_heal 空转 + CN_WORKFLOW_ID 未对齐"）。
   本轮对齐 v8_cloud_watchdog.py 的 08-06 修复：
   - 补上算法链产物监控；
   - **主派发改为云端 workflow**（v8_cn_fetch_cloud / v8_algo_cloud），
     cn 自托管 runner 仅作「在线时才兜底」的二级回退，离线绝不空转。

用法：
  python v8_postclose_guard.py            # 真实补救模式
  python v8_postclose_guard.py --dry-run # 只检查不 dispatch（调试用）
"""
import json
import base64
import http.client
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

TOKEN_FILE = r"E:/workspace/quant-scanner-v8/.workbuddy/v8_gh_token.txt"
REPO = "ah-quant999/quant-scanner-v8"
API = "https://api.github.com"
CST = timezone(timedelta(hours=8))

# ===== 盘后必须当日刷新的文件（update_time 应为今日） =====
# ① 盘后 fetch 产物（v8_cn_fetch[_cloud] 产出）
POST_CLOSE_FETCH_FILES = [
    "data/MARKET_FUND_FLOW_DATA.js",
    "data/EXPERIMENT.js",
    "raw_data/market_fund_flow_data.json",
]
# ② 盘后算法链产物（v8_algo_run[_cloud] 产出）—— 旧版漏检的根因
POST_CLOSE_ALGO_FILES = [
    "data/CANDIDATE.js",
    "data/GOLD_POOL.js",
    "data/LHB_DATA.js",
    "data/INST_TRADE.js",
    "data/TRIPLE_CONSENSUS.js",
    "data/SH_FIB.js",
    "data/NT_DATA.js",
    "raw_data/candidate.json",
    "raw_data/gold_pool.json",
    "raw_data/lhb_data.json",
    "raw_data/inst_trade.json",
    "raw_data/triple_consensus.json",
    "raw_data/sh_fib.json",
    "raw_data/nt_data.json",
]

# ===== workflow 派发目标 =====
# 云端主力（ubuntu-latest，与 v8_cloud_watchdog.py CN_WORKFLOW_ID 对齐）
WF_FETCH_CLOUD = 327687211   # v8_cn_fetch_cloud.yml
WF_ALGO_CLOUD = 324119592    # v8_algo_cloud.yml（无 inputs，跑全链）
# cn 自托管 runner 应急回退（仅当该 runner 在线时才用，避免离线空转）
WF_FETCH_CN = 324135267      # v8_cn_fetch.yml
WF_ALGO_CN = 324833339       # v8_algo_run.yml


def get_token():
    from pathlib import Path
    return Path(TOKEN_FILE).read_text(encoding="utf-8").strip()


# 网络类异常元组。⚠️ 2026-08-11（165 轮）：http.client.IncompleteRead 继承
# HTTPException，**不是 OSError 子类**（157 轮 api_push_raw.py 已被咬过一次），
# 必须显式列出，否则响应体截断时异常逃逸。
NET_ERRORS = (TimeoutError, urllib.error.URLError, OSError,
              http.client.HTTPException, json.JSONDecodeError)
GET_RETRY = 3


def api_get(path, retry=GET_RETRY):
    """GET 幂等，失败退避重试；重试耗尽后**抛出**，绝不返回降级值。"""
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(
                API + path,
                headers={"Authorization": "token " + TOKEN,
                         "Accept": "application/vnd.github.v3+json"},
            )
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # 404 等确定性状态码不重试，交由调用方语义化处理
            if e.code in (404, 401, 403):
                raise
            last = e
        except NET_ERRORS as e:
            last = e
        if i < retry - 1:
            time.sleep(2 ** i)
    raise last


def api_post(path, data):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(data).encode("utf-8"),
        headers={"Authorization": "token " + TOKEN,
                 "Accept": "application/vnd.github.v3+json",
                 "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def file_update_time(path):
    """返回 (kind, value)：
       ("ok", "2026-08-11 15:31")  远端 update_time 读取成功
       ("nofield", "NONE")         文件在但无 update_time 字段 → 按陈旧处理（真问题）
       ("missing", "404")          远端文件不存在 → 按陈旧处理（真问题）
       ("err", "<原因>")           基线获取失败 → **不得当作新鲜**，由 main 拒绝判定

    🔴 2026-08-11 根因修复（165 轮看门狗，勿回退）：
       旧版统一返回字符串，失败返 "ERR:xxx"，而 stale_in_group 用
       `not ut.startswith("ERR")` 把 ERR 排除在陈旧之外 →
       一旦 contents API 全挂（网络抖动 / token 过期 / 403 限流），
       17 个文件全 ERR → stale 两个空列表 → 打印「✅ 盘后数据已是最新」exit 0。
       守卫 100% 静默失效，且日志与退出码完全看不出异常
       （调用它的自动化只记录「退出码 0，无 stderr」= 永远发现不了）。
       这与 159 轮 api_push_raw.py 的「防倒退基线静默变空」同族：
       **基线获取失败必须 fail-loud，绝不允许降级为「一切正常」。**
    """
    try:
        d = api_get(f"/repos/{REPO}/contents/{path}?ref=main")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return ("missing", "404 远端文件不存在")
        return ("err", f"HTTP {e.code}")
    except Exception as e:
        return ("err", f"{type(e).__name__}: {e}")
    try:
        c = base64.b64decode(d["content"]).decode("utf-8", "ignore")
    except Exception as e:
        # 内容字段缺失/解码失败属基线不可信，不能当新鲜
        return ("err", f"content 解析失败 {type(e).__name__}: {e}")
    m = re.search(r'"update_time"\s*:\s*"([^"]+)"', c)
    return ("ok", m.group(1)) if m else ("nofield", "NONE")


def runner_offline():
    """返回离线 runner 名称列表；空列表=全部在线。"""
    try:
        runners = api_get(f"/repos/{REPO}/actions/runners")
        return [r["name"] for r in runners.get("runners", []) if not r.get("online")]
    except Exception as e:
        return [f"query_failed:{e}"]


def dispatch(wf_id, category=None):
    """派发指定 workflow。fetch 类可带 category；algo 类不传 inputs。"""
    payload = {"ref": "main"}
    if category:
        payload["inputs"] = {"category": category}
    return api_post(
        f"/repos/{REPO}/actions/workflows/{wf_id}/dispatches",
        payload,
    )


def stale_in_group(files, today):
    """返回 (stale, errors)。
       stale：确认非今日（含 missing/nofield，均为真问题）
       errors：基线获取失败，**单独上报**，绝不静默并入「新鲜」
    """
    stale, errors = [], []
    for f in files:
        kind, val = file_update_time(f)
        if kind == "err":
            errors.append((f, val))
        elif kind in ("missing", "nofield"):
            stale.append((f, val))
        elif not val.startswith(today):
            stale.append((f, val))
    return stale, errors


def main():
    global TOKEN
    TOKEN = get_token()
    now = datetime.now(CST)
    today = now.strftime("%Y-%m-%d")
    dry = "--dry-run" in sys.argv
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')} CST] 盘后守护检查" + (" [DRY-RUN]" if dry else ""))

    if now.weekday() >= 5:
        print("  非交易日，跳过")
        return
    if now.hour < 15 or (now.hour == 15 and now.minute < 30):
        print("  未到 15:30 盘后窗口，跳过")
        return

    fetch_stale, fetch_err = stale_in_group(POST_CLOSE_FETCH_FILES, today)
    algo_stale, algo_err = stale_in_group(POST_CLOSE_ALGO_FILES, today)
    errors = fetch_err + algo_err

    print(f"  fetch 产物陈旧: {len(fetch_stale)} 个")
    for f, ut in fetch_stale:
        print(f"    - {f}: {ut}")
    print(f"  算法链产物陈旧: {len(algo_stale)} 个")
    for f, ut in algo_stale:
        print(f"    - {f}: {ut}")

    # 🔴 基线不完整 → fail-loud（165 轮根因修复）。
    # 有任何文件读不到远端 update_time，就没有资格宣称「已是最新」。
    if errors:
        print(f"  ❌ 基线获取失败 {len(errors)} 个文件（已重试 {GET_RETRY} 次）——"
              f"拒绝判定「已是最新」，本轮检测结果不可信：")
        for f, why in errors:
            print(f"    - {f}: {why}")

    if not fetch_stale and not algo_stale:
        if errors:
            print("  ⚠️ 未发现确认陈旧项，但基线不完整，不作「无需补救」结论 → 退出码 2 供上游告警")
            sys.exit(2)
        print("  ✅ 盘后数据已是最新，无需补救")
        return

    off = runner_offline()
    cn_online = not off
    if off:
        print(f"  ⚠️ cn runner 离线: {off} —— 不向其派发（避免空转），改用云端主力")

    if dry:
        cats = []
        if fetch_stale:
            cats.append("fetch→cloud(327687211) category=all")
        if algo_stale:
            cats.append("algo→cloud(324119592)")
        print(f"  [DRY-RUN] 将派发: {', '.join(cats)}（{len(fetch_stale)+len(algo_stale)} 个文件陈旧）")
        return

    # —— 真实派发：云端主力优先，cn runner 仅在线时兜底 ——
    def _dispatch_with_fallback(kind, cloud_id, cn_id, category=None):
        """先云端，失败且 cn 在线时回退 cn runner。返回 (ok, msg)。"""
        try:
            dispatch(cloud_id, category)
            return True, f"云端 {cloud_id} 已派发" + (f" category={category}" if category else "")
        except Exception as e:
            if cn_online:
                try:
                    dispatch(cn_id, category)
                    return True, f"云端失败→cn 兜底 {cn_id} 已派发 ({e})"
                except Exception as e2:
                    return False, f"云端失败({e}) 且 cn 兜底也失败({e2})"
            return False, f"云端失败({e})；cn runner 离线未兜底"

    failed = False
    if fetch_stale:
        ok, msg = _dispatch_with_fallback("fetch", WF_FETCH_CLOUD, WF_FETCH_CN, "all")
        print(f"  [{'✅' if ok else '❌'}] fetch 补救: {msg}")
        failed = failed or not ok

    if algo_stale:
        ok, msg = _dispatch_with_fallback("algo", WF_ALGO_CLOUD, WF_ALGO_CN, None)
        print(f"  [{'✅' if ok else '❌'}] algo 补救: {msg}")
        failed = failed or not ok

    # 派发失败或基线不完整 → 非零退出，让上游自动化/看门狗能看见
    if failed or errors:
        sys.exit(2)


if __name__ == "__main__":
    main()
