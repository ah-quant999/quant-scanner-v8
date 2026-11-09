#!/usr/bin/env python3
# 九宝量化 v8.0 — 数据抓取看门狗探针（自 v8_cn_fetch_watchdog.yml 内嵌脚本抽出）
#
# 🔴 2026-11-09 一劳永逸抽出（GitHub "Exceeded max expression length 21000" 根治）：
#   原 320 行 python 内嵌在 run: | 块里且内含 ${{ }} 表达式，文件膨胀到 27.8KB 后
#   GitHub 表达式扫描器把整个 run 块误吞为一条表达式（>21K 上限）⇒ 整链被判
#   Invalid workflow file、每次 push 连坐红（11-09 实证 5 连坐，双机数据推送也被拦）。
#   抽出为独立脚本后：YAML run 块只剩一行调用，无表达式、体积恒小，两个雷同时拆除。
#   入参：环境变量 V8_FORCE_CATEGORY（原 workflow_dispatch inputs.force_category 经 env 传入）。

import os
import urllib.request, json, re, subprocess, datetime, sys

# 当前 CST 时间
cst = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
dow = cst.weekday()            # 0=周一
hhmm = cst.hour * 60 + cst.minute
print(f"[watchdog] CST={cst.strftime('%Y-%m-%d %H:%M')} dow={dow} hhmm={hhmm}")

force = (os.environ.get("V8_FORCE_CATEGORY") or "").strip()

# 仅交易日（周一至周五）
if dow >= 5 and not force:
    print("[watchdog] 非交易日，跳过"); sys.exit(0)

def in_window(a, b):
    return a <= hhmm <= b
# 🆕 2026-09-17 阿狸咪（拍-16 / 判据 90）：dispatch + cancel 统一留痕（纯观测）。
#   🔴 本 workflow 跑在**临时** ubuntu runner ⇒ 本地文件跑完即丢 ⇒ 只写
#     Actions step summary（每个 run 页面即时可查）+ 日志。
#   有意不推仓：本 workflow 每分钟一次调度，入库会造成 commit 风暴。
#   🔴 异常安全：整段 try/except，留痕绝不影响主流程。
def audit(event, **kw):
    try:
        ts = cst.strftime("%Y-%m-%d %H:%M:%S")
        detail = " ".join("{}={}".format(k, str(v).replace(chr(10), " ")[:80])
                          for k, v in kw.items())
        print("[audit] {} {} {}".format(ts, event, detail))
        import os as _os3
        sp = _os3.environ.get("GITHUB_STEP_SUMMARY")
        if sp:
            with open(sp, "a", encoding="utf-8") as f:
                f.write("- `{}` **{}** {}\n".format(ts, event, detail))
    except Exception:
        pass

# 交易时段 → 自适应类别
cat = None
if force:
    cat = force
# 🔴 2026-11-09 一劳永逸（主人令「盘前卡全显示昨日」根因修复之一）：
#   原盘前窗只有 08:25-09:00，而 07:10 档（INDEX_VALUE_FRAMEWORK / VALUATION_PERCENTILE）
#   整段无人值守 —— 07:10 档被应急僵尸堵住时，09:00 后看门狗转 intraday 探针
#   （名单不含盘前文件）⇒ 盘前文件整天烂着无人补派
#   （11-09 实证：两文件拖到 16:46/16:48 才产出，主人开盘看到的全是「昨日+红X」）。
#   现扩窗 07:05-09:55：覆盖 07:10 档产出窗口 + 08:25 档 + 开盘后 55 分钟补漏期；
#   09:55 后由既有 intraday 窗（09:00-11:30）无缝接管，无空隙。
elif in_window(7*60+5, 9*60+55):      # 07:05-09:55 盘前（覆盖07:10档+08:25档+开盘补漏）
    cat = "premarket"
elif in_window(9*60, 11*60+30):       # 09:00-11:30 上午盘中
    cat = "intraday"
elif in_window(13*60, 15*60+30):      # 13:00-15:30 下午盘中
    cat = "intraday"
elif in_window(17*60, 17*60+40):      # 17:00-17:40 盘后
    cat = "post_close"
elif in_window(17*60+41, 21*60+30):   # 17:41-21:30 晚间盘后（2026-09-03 阿狸咪：补晚间空窗）
    cat = "post_close"
else:
    print("[watchdog] 非交易时段，跳过"); sys.exit(0)

# 🔴 2026-09-02 根治（涨停热力静默陈旧近 3 小时事故）：
#    原逻辑只读 HEALTH_CHECK.js 单一时间戳判断"数据是否新鲜"，存在系统性盲区——
#    HEALTH_CHECK 由 cn_fetch 每轮**结尾**刷新，即使该轮个别数据文件 blob 上传
#    HTTP 500 失败被跳过（见 api_push_raw.py 的 failed_paths 分支），
#    HEALTH_CHECK 依然"新鲜"，看门狗于是永远判定"无需派发"，坏文件持续陈旧无人察觉。
#    实测 2026-09-02：涨停热力卡 08:45 盘前值近 3 小时，而 HEALTH_CHECK 刷到 10:18。
#    改为：按类别并行抽查多个代表性数据文件，取【最旧】者作为判据，
#          任一文件陈旧即派发 —— 杜绝"整体健康、局部坏死"。
BASE_URL = "https://ah-quant999.github.io/quant-scanner-v8/data/"
PROBE = {
    "intraday": ["LIMIT_UP_HEATMAP.js", "CONCEPT_RANKING.js", "CAPITAL_FLOW_DATA.js",
                 "SECTOR_FUND_FLOW.js", "INDEX_QUOTES.js", "CANDIDATE_QUOTES.js",
                 "MARKET_ALERTS.js"],
    # 🔴 2026-11-09 一劳永逸（根因修复之二）：探针名单补入 07:10 档两文件——
    #   原名单 6 文件不含 INDEX_VALUE_FRAMEWORK / VALUATION_PERCENTILE，
    #   这两个文件烂了看门狗永远看不见（「整体健康、局部坏死」同类盲区）。
    "premarket": ["JUDGMENT_DATA.js", "CRISIS_DATA.js", "LIMIT_UP_HEATMAP.js", "US_HK_MAP.js", "V8_CALENDAR.js", "MARGIN_DATA.js",
                  "INDEX_VALUE_FRAMEWORK.js", "VALUATION_PERCENTILE.js"],
    "post_close": ["LHB_DATA.js", "CANDIDATE_QUOTES.js", "CAPITAL_FLOW_DATA.js",
               "MARKET_ALERTS.js"],
}
files = PROBE.get(cat) or ["LIMIT_UP_HEATMAP.js"]
# 🔴 2026-09-10 修正（主人令·13:00开盘数据停更事故）：
#   原盘中阈值 35min 太松，开盘后干等~10min 才兜底（实时盘不可接受）。
#   改为：盘中 12min、开盘前后窗口(09:25-09:40 / 12:55-13:10) 5min、盘前盘后 60min。
#   另设 dispatch_thr（派发兜底阈值）远高于主派发间隔：盘中 45min / 盘前盘后 90min，
#   仅当主派发 22505803 彻底失联(>45min)才由看门狗派 selfhosted 兜底，绝不抢主派发档。
in_open = in_window(9*60+25, 9*60+40) or in_window(12*60+55, 13*60+10)
if cat == "intraday":
    thr = 5 if in_open else 12
    dispatch_thr = 45
elif cat == "premarket":
    # 🔴 2026-11-09 一劳永逸（根因修复之四）：盘前档 60/90 太松 —— 07:10 档最坏
    #   08:40 才告警、09:55 才兜底，再叠加并发组被僵尸占用即拖到下午。
    #   收紧为 45 告警 / 60 兜底：07:10 档失败 → 08:10 告警、08:25 起兜底派发。
    thr = 45
    dispatch_thr = 60
else:
    thr = 60
    dispatch_thr = 90
PAT = re.compile(r'"?update_time"?\s*[:=]\s*"([^"]+)"')

# 🔴 2026-09-09 盘中更新审计·一劳永逸：不仅看「有没有在跑」，还要看「最近一次是否失败/拥堵」。
#    云端 ubuntu-latest 队列拥堵时（>=2 run 在排队 或 最近一次 failure），改派 self-hosted cn runner
#    兜底，避免 13:00 数据停滞 70min 同类事故。
def queue_detail():
    """查询云端 cn_fetch 队列细节：返回 (执行中数, 排队中数, 最近一次完成结论)。

    🔴 2026-09-24 新增：per_page 5 → 20。并发组已按 category 拆分
       （intraday / post_close / scheduled 各自成组），5 条窗口覆盖不到两组，
       会把「另一组在跑」误判成「队列已空」。
    """
    try:
        import os as _os
        rq = urllib.request.Request(
            "https://api.github.com/repos/ah-quant999/quant-scanner-v8"
            "/actions/workflows/v8_cn_fetch_cloud.yml/runs?per_page=20",
            headers={"User-Agent": "Mozilla/5.0",
                     "Authorization": "Bearer " + _os.environ.get("GH_TOKEN", "")})
        j = json.loads(urllib.request.urlopen(rq, timeout=20).read())
        runs = j.get("workflow_runs", [])
        inprog = sum(1 for x in runs if x.get("status") == "in_progress")
        queued = sum(1 for x in runs if x.get("status") in (
            "queued", "pending", "waiting", "requested"))
        latest = None
        for x in runs:
            if x.get("status") == "completed":
                latest = x.get("conclusion")
                break
        return inprog, queued, latest
    except Exception as e:
        print(f"[watchdog] 查云端状态失败: {e}")
        return 0, 0, None

def cloud_state():
    """兼容包装：返回 (未完成总数, 最近一次完成结论)。"""
    _a, _b, _latest = queue_detail()
    return _a + _b, _latest

def cancel_stuck_cloud_runs():
    """🔴 2026-09-24 一劳永逸重写（主人令「主站还是13点多的数据」根因修复之二 · 小九的工程师）

    【病灶·本仓实证】旧判据 `age(x["created_at"]) > 12` 有两处致命缺陷：
      ① **不看 status** —— pending/queued（正常排队）也被当成"卡死 run"。
         本仓盘中每 20 分派发、单轮执行 20+ 分 ⇒ 排队是**预期行为**；
         旧口径会把排队中的 run 批量砍掉 ⇒ 队列被清空
         （实测 09-24 13:25:24 一次 canc 6 个、14:06:09 一次 canc 7 个），
         且砍完**不补派** ⇒ 数据空窗 2.8 小时（CAPITAL_FLOW 卡 11:35）。
      ② `created_at` **包含排队时间** —— post_close 是合法长跑
         （job timeout 60 min；实测 #35956823600 占槽 12:43→13:45 共 62 分），
         会在第 12 分钟就被判死，连"长跑自己"也被砍。
    【修法】只对「**in_progress 且【真正开始执行】超过阈值**」的 run 出手：
      · pending/queued/waiting/requested → **绝不 cancel**（排队是正常语义）；
      · 执行时长改用 `run_started_at` 计（**不含排队时间**）；
      · 阈值按窗区分：盘后长跑窗（CST 15:30–20:30）70 分（job timeout 60 + 余量），
        其余时段 25 分（intraday 正常 7–17 分，超 25 分即真卡）。
    【职责已变】并发组 2026-09-24 起按 category 拆分（见 v8_cn_fetch_cloud.yml
      `group: v8-cn-fetch-cloud-<category>`）⇒ post_close 与 intraday 互不占槽，
      本函数不再承担"释放槽位"职责，只需兜住**真僵尸** ⇒ 故判据从宽、宁可少杀。
    """
    try:
        import os as _os
        hdr = {"User-Agent": "Mozilla/5.0",
               "Authorization": "Bearer " + _os.environ.get("GH_TOKEN", ""),
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
        rq = urllib.request.Request(
            "https://api.github.com/repos/ah-quant999/quant-scanner-v8"
            "/actions/workflows/v8_cn_fetch_cloud.yml/runs?per_page=20", headers=hdr)
        j = json.loads(urllib.request.urlopen(rq, timeout=20).read())
        in_postclose = (15 * 60 + 30) <= hhmm <= (20 * 60 + 30)
        exec_limit = 70 if in_postclose else 25
        now_utc = datetime.datetime.utcnow()
        for x in j.get("workflow_runs", []):
            stt = x.get("status")
            if stt == "completed":
                continue
            if stt != "in_progress":
                # 🛡 排队中的 run 一律不动 —— 这是本次断档事故的直接教训。
                created = datetime.datetime.strptime(
                    x["created_at"][:19], "%Y-%m-%dT%H:%M:%S")
                wait_min = (now_utc - created).total_seconds() / 60
                print(f"[watchdog] ⏳ run#{x['id']} 处于「{stt}」排队中"
                      f"（已等 {wait_min:.0f} 分）→ **不取消**（排队是正常语义）")
                continue
            started = x.get("run_started_at") or x.get("created_at")
            st = datetime.datetime.strptime(started[:19], "%Y-%m-%dT%H:%M:%S")
            exec_min = (now_utc - st).total_seconds() / 60
            if exec_min > exec_limit:
                req2 = urllib.request.Request(
                    f"https://api.github.com/repos/ah-quant999/quant-scanner-v8"
                    f"/actions/runs/{x['id']}/cancel",
                    data=b"", method="POST", headers=hdr)
                try:
                    urllib.request.urlopen(req2, timeout=20)
                    print(f"[watchdog] 🔓 破锁：取消真僵尸 cloud run#{x['id']}"
                          f"（**已执行** {exec_min:.0f} 分 > {exec_limit} 分）")
                    audit("cancel", target="cloud_stuck_lock", run=x['id'],
                          exec_min=round(exec_min, 1), limit=exec_limit,
                          ok=True, why="zombie_in_progress")
                except Exception as e:
                    audit("cancel", target="cloud_stuck_lock", run=x['id'],
                          exec_min=round(exec_min, 1), limit=exec_limit,
                          ok=False, why="zombie_in_progress", err=str(e)[:120])
                    print(f"[watchdog] 取消 run#{x['id']} 失败: {e}")
            else:
                print(f"[watchdog] 🏃 run#{x['id']} 执行中（{exec_min:.0f} 分，"
                      f"阈值 {exec_limit} 分）→ 正常，不动")
    except Exception as e:
        print(f"[watchdog] 破锁查询失败: {e}")

def cancel_stuck_selfhosted_runs():
    """🔴 2026-11-09 一劳永逸新增（主人令「盘前卡全显示昨日」根因修复之三）

    【病灶】cancel_stuck_cloud_runs 只盯云端主链 v8_cn_fetch_cloud.yml，而应急链
      v8_cn_fetch_cloud_selfhosted.yml 跑在 [self-hosted, cn] **单机独占** runner 上
      （job timeout 75 分）—— 僵尸 run 一面占住 runner、一面占着并发组
      v8-cn-fetch-cloud-<category> ⇒ 云端补派也在同组排队
      （11-09 实证：应急 run 卡 35+ 分，美股专链拖到 14:31、盘前档拖到 16:46/16:48）。
    【修法】与云端破锁同构：只杀 in_progress 且【真正开始执行】超过阈值的 run；
      排队中一律不动（排队是正常语义）。阈值 80 分 = job timeout 75 分 + 5 分余量
      （GitHub timeout 失灵 / runner 卡死时由本函数兜底，宁少杀）。
    """
    try:
        import os as _os
        hdr = {"User-Agent": "Mozilla/5.0",
               "Authorization": "Bearer " + _os.environ.get("GH_TOKEN", ""),
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
        rq = urllib.request.Request(
            "https://api.github.com/repos/ah-quant999/quant-scanner-v8"
            "/actions/workflows/v8_cn_fetch_cloud_selfhosted.yml/runs?per_page=20", headers=hdr)
        j = json.loads(urllib.request.urlopen(rq, timeout=20).read())
        now_utc = datetime.datetime.utcnow()
        for x in j.get("workflow_runs", []):
            stt = x.get("status")
            if stt == "completed":
                continue
            if stt != "in_progress":
                continue   # 排队中的 run 一律不动
            started = x.get("run_started_at") or x.get("created_at")
            st = datetime.datetime.strptime(started[:19], "%Y-%m-%dT%H:%M:%S")
            exec_min = (now_utc - st).total_seconds() / 60
            if exec_min > 80:
                req2 = urllib.request.Request(
                    f"https://api.github.com/repos/ah-quant999/quant-scanner-v8"
                    f"/actions/runs/{x['id']}/cancel",
                    data=b"", method="POST", headers=hdr)
                try:
                    urllib.request.urlopen(req2, timeout=20)
                    print(f"[watchdog] 🔓 破锁：取消僵尸 selfhosted run#{x['id']}"
                          f"（已执行 {exec_min:.0f} 分 > 80 分）—— 释放单机独占 runner")
                    audit("cancel", target="selfhosted_stuck_lock", run=x['id'],
                          exec_min=round(exec_min, 1), limit=80,
                          ok=True, why="zombie_in_progress")
                except Exception as e:
                    audit("cancel", target="selfhosted_stuck_lock", run=x['id'],
                          exec_min=round(exec_min, 1), limit=80,
                          ok=False, why="zombie_in_progress", err=str(e)[:120])
                    print(f"[watchdog] 取消 selfhosted run#{x['id']} 失败: {e}")
            else:
                print(f"[watchdog] 🏃 selfhosted run#{x['id']} 执行中（{exec_min:.0f} 分，"
                      f"阈值 80 分）→ 正常，不动")
    except Exception as e:
        print(f"[watchdog] selfhosted 破锁查询失败: {e}")

def cancel_stuck_algo_runs():
    """盘后算法链（v8_algo_cloud.yml）僵尸破锁 —— 🔴 2026-11-09 一劳永逸（主人令·终选/最终推荐全被堵）。

    【病灶】11-09 实证：16:50 起的算法链 run 卡死在「运行盘后算法链」步骤 3.5h+，
      concurrency 组 v8-algo-cloud 被独占 ⇒ 20:00/21:00 唤醒与 2 笔 dispatch 全部 pending，
      终选输出 / 最终推荐 / 金钻跟随 全断供到深夜；而看门狗 cron 原只覆盖 CST 08:00-15:59，
      算法链全在 16:30-23:00 跑 ⇒ 卡死整段无人值守（第二个结构性盲区）。
    【修法】与云端/应急链破锁同构：只杀 in_progress 且【真正开始执行】超过 240 分钟的
      算法链 run（全链实测最长 84min，240 = 3 倍冗余，绝不误杀合法长跑）；
      pending/queued 一律不动（排队是正常语义）。cancel 后 concurrency 组自然放行，
      下一个唤醒档（cron 20:00/21:00/22:30 接力）按批次闸门自动补跑，无需主动补派。
    """
    import os as _os
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/ah-quant999/quant-scanner-v8/actions/workflows/v8_algo_cloud.yml/runs?per_page=10",
            headers={"Authorization": "Bearer " + _os.environ.get("GH_TOKEN", ""),
                     "User-Agent": "v8-watchdog"})
        runs = json.loads(urllib.request.urlopen(req, timeout=20).read()).get("workflow_runs", [])
    except Exception as e:
        print(f"[watchdog] algo 破锁查询失败: {e}")
        return
    import time as _time
    now_ts = _time.time()
    for x in runs:
        if x.get("status") != "in_progress":
            continue
        st = x.get("run_started_at")
        if not st:
            continue
        try:
            started = datetime.datetime.strptime(st.replace("Z", ""),
                                                 "%Y-%m-%dT%H:%M:%S").replace(
                tzinfo=datetime.timezone.utc)
            exec_min = (now_ts - started.timestamp()) / 60.0
        except Exception:
            continue
        if exec_min > 240:
            print(f"[watchdog] 🧟 算法链 run#{x['id']} 执行 {exec_min:.0f} 分（>240 阈值）→ 僵尸破锁 cancel")
            try:
                creq = urllib.request.Request(
                    "https://api.github.com/repos/ah-quant999/quant-scanner-v8" + f"/actions/runs/{x['id']}/cancel",
                    method="POST",
                    headers={"Authorization": "Bearer " + _os.environ.get("GH_TOKEN", ""),
                             "User-Agent": "v8-watchdog"})
                urllib.request.urlopen(creq, timeout=20)
                audit("cancel", target="algo_stuck_lock", run=x['id'],
                      exec_min=round(exec_min, 1), limit=240,
                      ok=True, why="zombie_in_progress")
            except Exception as e:
                audit("cancel", target="algo_stuck_lock", run=x['id'],
                      exec_min=round(exec_min, 1), limit=240,
                      ok=False, why="zombie_in_progress", err=str(e)[:120])
                print(f"[watchdog] 取消算法链 run#{x['id']} 失败: {e}")
        else:
            print(f"[watchdog] 🏃 算法链 run#{x['id']} 执行中（{exec_min:.0f} 分，"
                  f"阈值 240 分）→ 正常，不动")

def dispatch_cat(category, use_selfhosted=False):
    """按拥堵状态派发：云端正常 -> 派云端；拥堵/刚失败 -> 派 selfhosted 兜底。

    🛡 2026-11-09 抽脚本时补硬：gh CLI 缺失/异常不再炸整链（ FileNotFoundError 等兜底
      为告警留痕），与本仓「异常安全」惯例对齐 —— 探针脚本绝不让巡检自身变红。
    """
    import subprocess
    if use_selfhosted:
        try:
            r = subprocess.run(
                ["gh", "workflow", "run", "v8_cn_fetch_cloud_selfhosted.yml",
                 "-f", f"category={category}"],
                capture_output=True, text=True, check=False)
        except Exception as e:
            print(f"[watchdog] ⚠️ selfhosted 派发异常（gh 缺失?）: {e}")
            audit("dispatch", path="selfhosted", cat=category, ok=False,
                  trigger="cloud_congested_or_failed", err=str(e)[:120])
            return
        print(r.stdout.strip(), r.stderr.strip())
        print(f"[watchdog] 🛰️ 已派 selfhosted {category}（云端拥堵/刚失败兜底）")
        audit("dispatch", path="selfhosted", cat=category, ok=(r.returncode == 0),
              trigger="cloud_congested_or_failed")
        return
    try:
        r = subprocess.run(["gh", "workflow", "run", "v8_cn_fetch_cloud.yml",
                          "-f", f"category={category}"],
                         capture_output=True, text=True, check=False)
    except Exception as e:
        print(f"[watchdog] ⚠️ 云端派发异常（gh 缺失?）: {e}")
        audit("dispatch", path="cloud_main", cat=category, ok=False,
              trigger="stale_probe", err=str(e)[:120])
        return
    print(r.stdout.strip(), r.stderr.strip())
    print(f"[watchdog] ☁️ 已派云端 {category}")
    audit("dispatch", path="cloud_main", cat=category, ok=(r.returncode == 0),
          trigger="stale_probe")

# 🔴 2026-09-24 一劳永逸**接线**（小九的工程师）：
#   实本函数此前**只有定义、从无调用** —— 全仓 grep `cancel_stuck_cloud_runs`
#   仅 1 处命中（就是定义本身）⇒ 死代码 ⇒ 所谓"看门狗破锁"从未生效过。
#   而 09-24 13:25:24 / 14:06:09 的批量 cancel（一次 6~7 个）另有来源，
#   清空队列后**无人补派** ⇒ 空窗 2.8 小时。现正式接线：先清真僵尸
#   （只砍 in_progress 且执行超阈值者，绝不动 pending，见函数 docstring），
#   再继续往下走陈旧度探测与兜底派发。
cancel_stuck_cloud_runs()
# 🔴 2026-11-09 接线：应急链僵尸同样破锁（self-hosted 单机独占，
#   应急僵尸不破锁 = 云端补派也排队，美股专链/盘前档全被堵，见 11-09 事故）。
cancel_stuck_selfhosted_runs()
# 🔴 2026-11-09 接线：盘后算法链僵尸破锁（concurrency 组 v8-algo-cloud 被独占时
#   20:00/21:00 唤醒与 dispatch 全 pending，终选/最终推荐全断供，见 11-09 卡死 3.5h 事故）。
cancel_stuck_algo_runs()

stale, newest = [], None
for fn in files:
    try:
        r2 = urllib.request.Request(BASE_URL + fn, headers={"User-Agent": "Mozilla/5.0"})
        t2 = urllib.request.urlopen(r2, timeout=20).read().decode("utf-8", "replace")
        mm = PAT.search(t2)
        if not mm:
            print(f"[watchdog]   ? {fn}: 无 update_time 字段，跳过"); continue
        dt = datetime.datetime.strptime(mm.group(1)[:19], "%Y-%m-%d %H:%M:%S")
        if newest is None or dt > newest: newest = dt
        age = (cst.replace(tzinfo=None) - dt).total_seconds() / 60
        if age > thr:
            stale.append((fn, age))
            print(f"[watchdog]   ✗ {fn}: {dt} ({age:.0f}min 陈旧)")
        else:
            print(f"[watchdog]   ✓ {fn}: {dt} ({age:.0f}min)")
    except Exception as e:
        print(f"[watchdog]   ! {fn}: 读取失败 {e}")

if newest is None:
    print(f"[watchdog] 无法解析任何数据时间戳，保守派发 {cat}")
    n, latest = cloud_state()
    if n >= 2 or latest == "failure":
        print(f"[watchdog] 云端拥堵({n} run)或刚失败({latest})，改派 selfhosted")
        dispatch_cat(cat, use_selfhosted=True)
    else:
        dispatch_cat(cat, use_selfhosted=False)
    sys.exit(0)

# 🔴 2026-09-10 修正：区分「监控告警阈值 thr」与「派发兜底阈值 dispatch_thr」。
#   - age ∈ (thr, dispatch_thr]：仅告警（主派发 22505803 应已在跑，看门狗不抢档、不杀 run）。
#   - age > dispatch_thr（盘中45/盘后90）：主派发疑似死透，才派 selfhosted 兜底。
hard_stale = [(fn, a) for fn, a in stale if a > dispatch_thr]
if hard_stale:
    print(f"[watchdog] ❌ {len(hard_stale)}/{len(files)} 个文件极陈旧（派发阈值 {dispatch_thr}min），主派发疑似失联，派 selfhosted 兜底 {cat}")
    if cat == "intraday":
        dispatch_cat(cat, use_selfhosted=True)
    else:
        n, latest = cloud_state()
        if n >= 2 or latest == "failure":
            dispatch_cat(cat, use_selfhosted=True)
        else:
            dispatch_cat(cat, use_selfhosted=False)
    print("::error title=数据极陈旧·已派兜底::" +
          ", ".join(f"{fn}({a:.0f}min)" for fn, a in hard_stale))
elif stale:
    # 🔴 2026-09-24 一劳永逸（小九的工程师）：数据偏旧时**先查队列是否真空**。
    #   病灶（09-24 实证）：队列被批量 cancel 清空后，旧判据是
    #   「age ≤ dispatch_thr(45min) ⇒ 仅告警不派发」⇒ 空窗被硬拖到 45 分钟以上，
    #   而空窗期数据以分钟计在腐烂（CAPITAL_FLOW 卡 11:35，13:22 时 age 已 107min；
    #   实际是主人先发现，不是看门狗自愈）。
    #   修法：**队列真空**（既无执行中、也无排队中 run）= 没有任何一轮在跑，
    #   此时"不派"就是纯空转 ⇒ **立即补派**，不再等 dispatch_thr。
    _ip, _q, _latest = queue_detail()
    if _ip == 0 and _q == 0:
        print(f"[watchdog] 🚑 队列真空（执行中 0 / 排队中 0）且 {len(stale)} 个文件偏旧"
              f" ⇒ 无任何一轮在跑，立即补派 {cat}（不等 {dispatch_thr}min 兜底阈值）")
        if _latest == "failure":
            dispatch_cat(cat, use_selfhosted=True)
        else:
            dispatch_cat(cat, use_selfhosted=False)
        print("::error title=队列真空·已补派::" +
              ", ".join(f"{fn}({a:.0f}min)" for fn, a in stale))
    else:
        print(f"[watchdog] ⚠️ {len(stale)}/{len(files)} 个文件偏旧（监控阈值 {thr}min，"
              f"派发阈值 {dispatch_thr}min；队列 执行中{_ip}/排队{_q}）"
              f"→ 仅告警不派发（已有 run 在跑，不抢档）")
        print("::warning title=数据偏旧::" +
              ", ".join(f"{fn}({a:.0f}min)" for fn, a in stale))
else:
    print(f"[watchdog] ✅ {len(files)} 个文件全部新鲜（最新 {newest}，监控阈值 {thr}min），无需派发")

# 🔴 2026-11-09 金钻跟踪兜底（主人令「金钻跟踪新卡也是空的」）：
#   【病灶】v8_jinzuan_track.yml cron '0 10 * * *'（北京 18:00）上线首日（11-09）零触发
#     —— GitHub schedule 高负载跳过是本仓已知常态（盘前 08:25 档曾被静默丢弃 4h46m），
#     金钻数据断更无人管。
#   【修法】CST ≥19:00（给官方 cron 1 小时延迟余量）且线上 JINZUAN_TRACK.update_time
#     日期 ≠ 今日 ⇒ 视为今日档缺失，gh dispatch 补跑（该 workflow 自带 workflow_dispatch）。
#     执行机为云端 ubuntu（gen_jinzuan_track.py 纯 pandas/numpy + 本地缓存，无需中国 IP）。
if hhmm >= 1140:
    try:
        r2 = urllib.request.Request(BASE_URL + "JINZUAN_TRACK.js",
                                    headers={"User-Agent": "Mozilla/5.0"})
        _jt = urllib.request.urlopen(r2, timeout=20).read().decode("utf-8", "replace")
        # 🔴 判据用 data_date（数据归属日）而非 update_time：今晨 07:23 用周五 kline
        #   跑出的回放档 update_time 也=今日，会误判「已鲜」；data_date 只在
        #   18:00 盘后档（当日 kline 就绪）才会翻到今天。
        _m3 = re.search(r'"data_date"\s*:\s*"([^"]+)"', _jt)
        _dd = _m3.group(1) if _m3 else ""
        if _dd == cst.strftime("%Y-%m-%d"):
            print(f"[watchdog] 💎 金钻跟踪今日档已鲜（data_date={_dd}），无需兜底")
        else:
            print(f"[watchdog] 💎 金钻跟踪今日档缺失（data_date={_dd or '无'}，今日 {cst:%Y-%m-%d}）→ dispatch 补跑")
            try:
                _r = subprocess.run(["gh", "workflow", "run", "v8_jinzuan_track.yml"],
                                    capture_output=True, text=True, check=False)
                print(_r.stdout.strip(), _r.stderr.strip())
                audit("dispatch", path="jinzuan_track", ok=(_r.returncode == 0),
                      trigger="cron_missed_fallback", stale_data_date=_dd)
            except Exception as _e:
                print(f"[watchdog] ⚠️ 金钻兜底派发异常（gh 缺失?）: {_e}")
                audit("dispatch", path="jinzuan_track", ok=False,
                      trigger="cron_missed_fallback", err=str(_e)[:120])
    except Exception as _e:
        print(f"[watchdog] 金钻新鲜度检查失败（跳过兜底）: {_e}")
