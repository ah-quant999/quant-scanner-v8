#!/usr/bin/env python3
# cloud_dispatcher.py — 云端原生兜底调度器
#
# 背景：小九本机(self-hosted runner)停电/离线后，原依赖「本机 WorkBuddy 每30分检查+dispatch」
# 的冗余失效。v8_algo_cloud(选股四模块/盘后算法产物) 与 v8_risk_gauge(风险温度计) 的 GitHub
# schedule cron 会被平台静默跳过，导致这些模块永久停更。
#
# 本脚本由 v8_cn_fetch_cloud（云端 ubuntu，已验证每30分可靠触发）在每次抓取后调用，
# 做幂等兜底：
#   1) 算法链 v8_algo_cloud：仅在北京时间 >= 18:00 且今日尚未成功跑过时才 dispatch（LHB 18点后发布）。
#   2) 风险温度计 v8_risk_gauge：若最近 90 分钟内无成功运行则 dispatch（补齐被跳过的 schedule）。
#
# 用法：python cloud_dispatcher.py
# 依赖：环境变量 GITHUB_TOKEN（workflow 注入）；无需第三方库（纯 urllib）。
import os, sys, json, re, urllib.request, urllib.error, datetime

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

API = "https://api.github.com"
REPO = os.environ.get("GITHUB_REPO", "ah-quant999/quant-scanner-v8")
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
if not TOKEN:
    print("❌ 缺少 GITHUB_TOKEN，跳过兜底调度"); sys.exit(0)

CST = datetime.timezone(datetime.timedelta(hours=8))

# 2026 A股交易日历（与 v8_health_check.py 一致）：节假日 + 补班日
_HOLIDAYS_2026 = {
    "01-01", "01-02", "01-03",
    "02-15", "02-16", "02-17", "02-18", "02-19", "02-20", "02-21", "02-22", "02-23",
    "04-04", "04-05", "04-06",
    "05-01", "05-02", "05-03", "05-04", "05-05",
    "06-19", "06-20", "06-21",
    "09-25", "09-26", "09-27",
    "10-01", "10-02", "10-03", "10-04", "10-05", "10-06", "10-07",
}
_MAKEUP_DAYS_2026 = {
    "2026-01-04", "2026-02-14", "2026-02-28",
    "2026-05-09", "2026-09-20", "2026-10-10",
}

def _is_trading_day(dt):
    """判断给定 CST 时间是否为 A 股交易日（周末 + 节假日剔除，补班日算交易日）。"""
    d = dt.date()
    if d.weekday() >= 5 and d.isoformat() not in _MAKEUP_DAYS_2026:
        return False
    return d.strftime("%m-%d") not in _HOLIDAYS_2026

def api(method, path, data=None):
    url = API + path
    headers = {"Authorization": f"Bearer {TOKEN}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ API {method} {path} -> HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}")
        return {}
    except Exception as e:
        print(f"  ⚠️ API {method} {path} -> {e}")
        return {}

def latest_run(wf_file):
    """返回该 workflow 最近一次 run 的 (created_at, conclusion) 或 None。"""
    d = api("GET", f"/repos/{REPO}/actions/workflows/{wf_file}/runs?per_page=5")
    runs = d.get("workflow_runs", [])
    if not runs:
        return None
    r = runs[0]
    return r.get("created_at"), r.get("conclusion")

def runs_of(wf_file, per_page=30):
    d = api("GET", f"/repos/{REPO}/actions/workflows/{wf_file}/runs?per_page={per_page}")
    return d.get("workflow_runs", [])


# 🔴 2026-08-21 19:3x 一劳永逸根因修复（主人令「核查，一劳永逸式修复」）：
#   原逻辑「最近一条 run 不是今日 success → 派发」既不看有没有 run 正在跑，也没有冷却，
#   更没有失败熔断。算法链一失败就每 1-2 分钟被补派一次，实测今日堆到 150 个 run、
#   11-20 个并发 → 打爆 GitHub secondary rate limit(403) → 算法链 100% 超时失败，
#   连带 cn_fetch 的 api_push_raw 也 403（收盘数据推不上 main，实时卡停在 14:52）。
#   本守卫纯 API 判定、无状态：不依赖 repo 内锁文件（patrol 用 cancel-in-progress: true，
#   锁文件 push 常被 cancel → 锁永远写不回，data/.heal_dispatch.json 停在 13:56 即实证）。
def dispatch_guard(wf_file, now, cooldown_min=30, max_fail_today=3):
    """返回 (allow, reason)。三道闸：在跑/排队 → 冷却窗口 → 当日失败熔断。"""
    runs = runs_of(wf_file)
    if not runs:
        return True, "无历史 run，允许派发"
    live = [r for r in runs
            if r.get("status") in ("queued", "pending", "waiting", "requested", "in_progress")]
    if live:
        return False, "已有 %d 个 run 在跑/排队，再派发只会加剧并发限流 → 跳过" % len(live)
    last = runs[0]
    ct, ago = None, 9999.0
    try:
        ct = datetime.datetime.fromisoformat(
            last.get("created_at", "").replace("Z", "+00:00")).astimezone(CST)
        ago = (now - ct).total_seconds() / 60.0
    except Exception:
        pass
    if ago <= cooldown_min:
        return False, "最近一次 run 于 %s（%.0f 分钟前），%d 分钟冷却内不重复派发" % (
            ct.strftime("%H:%M") if ct else "?", ago, cooldown_min)
    # 🔴 2026-08-21 21:5x 二次根因修复（主人令「一劳永逸」）：
    #   初版熔断只按「今日失败次数」计，实测今日 algo_cloud 因 403 限流失败 84 次 →
    #   熔断永久生效到次日 0 点。后果：403 根因修好（checkout 替代逐 blob API 同步）后，
    #   自动派发仍被旧账熔断挡住，18:00 后的盘后选股链永远等不到自动恢复，只能人工派 ——
    #   这与「一劳永逸」正好相反：把一次故障变成一整晚的失能。
    #   正确语义：熔断是防「对同一个 bug 反复无效补派」，所以只该统计
    #   「与当前 main HEAD 同一份代码」的失败。代码一变（bug 已修）即自动解封。
    #   另留「探针」出口：同版本失败超阈值，但距最近一次失败 ≥ probe_after_min 时
    #   允许放 1 次探针 —— 覆盖「代码没错、是外部瞬时故障（GitHub 限流/数据源抖动）」的情形。
    head = None
    ref = api("GET", f"/repos/{REPO}/git/refs/heads/main")
    if isinstance(ref, dict):
        head = (ref.get("object") or {}).get("sha")
    fails_today = 0
    fails_same_code = 0
    last_fail_ago = 9999.0
    for r in runs:
        if r.get("conclusion") != "failure":
            continue
        try:
            rt = datetime.datetime.fromisoformat(
                r.get("created_at", "").replace("Z", "+00:00")).astimezone(CST)
        except Exception:
            continue
        if rt.date() != now.date():
            continue
        fails_today += 1
        if head and r.get("head_sha") == head:
            fails_same_code += 1
            last_fail_ago = min(last_fail_ago, (now - rt).total_seconds() / 60.0)
    if head is None:
        # 取不到 HEAD 时退回旧口径（保守，宁可熔断也不风暴）
        if fails_today >= max_fail_today:
            return False, ("🚨 熔断（保守口径，未取到 main HEAD）：%s 今日失败 %d 次 ≥ %d"
                           % (wf_file, fails_today, max_fail_today))
        return True, "允许派发（未取到 HEAD，按今日失败 %d < %d 放行）" % (fails_today, max_fail_today)
    if fails_same_code >= max_fail_today:
        probe_after_min = 60
        if last_fail_ago >= probe_after_min:
            return True, ("🔍 探针放行：%s 同版本(%s)今日失败 %d 次已熔断，但距最近失败 %.0f 分钟"
                          "（≥%d），放 1 次探针试探外部故障是否恢复"
                          % (wf_file, head[:7], fails_same_code, last_fail_ago, probe_after_min))
        return False, ("🚨 熔断：%s 在当前代码版本(%s)上今日已失败 %d 次（阈值 %d，今日总失败 %d），"
                       "距最近失败仅 %.0f 分钟 → 停止补派，属真故障需人工介入"
                       % (wf_file, head[:7], fails_same_code, max_fail_today, fails_today, last_fail_ago))
    return True, ("允许派发（当前代码版本 %s 今日失败 %d 次 < 阈值 %d；今日总失败 %d 次为旧版本旧账，不计）"
                  % (head[:7], fails_same_code, max_fail_today, fails_today))


def dispatch(wf_file, inputs=None):
    payload = {"ref": "main"}
    if inputs:
        payload["inputs"] = inputs
    r = api("POST", f"/repos/{REPO}/actions/workflows/{wf_file}/dispatches", payload)
    if r:
        print(f"  ✅ 已派发 {wf_file}")
    else:
        print(f"  ❌ 派发 {wf_file} 失败")


# 🛡 2026-09-07 22:2x 一劳永逸根治（主人令「互踢/暴风/覆盖不想再看到」·方案 B 配套 2）：
#   原 dispatch() 用 workflow_dispatch，触发 v8_algo_cloud.yml 时绕开探针路由（workflow_dispatch 不路由），
#   云端硬扛 2h40m 且触发 v8-algo-cloud concurrency 互踢（今日 13 次派发 9 cancelled），
#   同时多源（cloud_dispatcher + WorkBuddy 自动化）洪泛派发把 v8-algo-cloud 单并发槽打成死锁。
#   改用 repository_dispatch（type=trigger_algo）后：
#     ① 触发 v8_algo_cloud.yml:440 探针路由 → lemoncat-cn 在线则转派 v8_algo_run.yml（不同 concurrency
#        group v8-algo-cn，与云端完全分离 → 永不互踢）→ cn 跑全链 84min；cn 离线才回落云端。
#     ② 派发语义"唤醒"而非"覆盖"（type=trigger_algo），与 schedule 等同类，dispatch 内容级全收敛。
#     ③ WorkBuddy 自动化若仍用 workflow_dispatch 也无法绕过——因为探针路由不接它。
def dispatch_repo_dispatch(wf_file, event_type="trigger_algo", client_payload=None):
    """配套 2 根治：派发方式由 workflow_dispatch 改 repository_dispatch（type=trigger_algo）。
    触发 v8_algo_cloud.yml 的探针路由（line 440）：lemoncat-cn 在线则转派 v8_algo_run.yml（cn 链），
    离线才回落云端。这是治互踢/覆盖的关键。"""
    payload = {"event_type": event_type, "client_payload": client_payload or {}}
    r = api("POST", f"/repos/{REPO}/dispatches", payload)
    if r:
        print(f"  ✅ repository_dispatch {wf_file} type={event_type} payload={client_payload or {}}")
    else:
        print(f"  ❌ repository_dispatch {wf_file} 失败（HTTP 见上）")


def _final_recommend_still_stale():
    """配套 2 根治：检查核心产物（final_recommend/crds_card_data/candidate）是否本日已新鲜。
    至少一项仍陈旧 → True（仍要派），全部新鲜 → False（无需派），杜绝「成功假绿灯仍重派」覆盖风险。"""
    today = datetime.datetime.now(CST).strftime("%Y-%m-%d")
    files = [
        "raw_data/final_recommend.json",
        "raw_data/crds_card_data.json",
        "raw_data/candidate.json",
    ]
    for f in files:
        p = os.path.join(REPO_ROOT, f)
        if not os.path.exists(p):
            return True
        try:
            d = json.load(open(p, encoding="utf-8"))
            ut = (d.get("update_time") or d.get("generated_at") or "").strip()
            if not ut.startswith(today):
                return True
        except Exception:
            return True
    return False

# 🔴 2026-08-24 一劳永逸根因修复（主人令「修复 2-3 号问题」之 #3）：
#   盘后算法链 step（🧮 运行盘后算法链）偶发挂死（数据源/网络调用无超时等），
#   会以 in_progress 状态长期占用 v8-algo-cloud 单并发槽（concurrency cancel-in-progress:false），
#   把当晚 19:15 的盘后生成堵在队列里 → CANDIDATE/all_* 等卡片停更（#3 慢性陈旧根因）。
#   僵尸看门狗：仅对「北京时间 < 18:00 创建、却仍 in_progress」的 algo run 出手取消——
#   这类 run 按设计会跳过全部选股脚本（run_algorithms 内部 18:00 时间窗 gate），
#   不产生任何卡片数据，且正常 5-15 分钟即结束；若 in_progress 超 60 分钟必为挂死，
#   取消它零数据损失、并立即释放并发槽给当晚 19:15 生成。
#   绝不碰「>=18:00 创建」的盘后生成 run（那才是真正产出卡片的轮次），避免误杀真生成。
ZOMBIE_WF = "v8_algo_cloud.yml"
ZOMBIE_STALE_MAX_MIN = 60  # run 最后更新(updated_at)超 60 分钟无进展即判定卡死僵尸（不论盘前盘后）

def api_delete(path):
    """DELETE 并返回 HTTP 状态码（204=成功；看门狗取消 run 用）。"""
    url = API + path
    headers = {"Authorization": f"Bearer {TOKEN}",
               "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    req = urllib.request.Request(url, headers=headers, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"  ⚠️ DELETE {path} -> HTTP {e.code}")
        return e.code
    except Exception as e:
        print(f"  ⚠️ DELETE {path} -> {e}")
        return -1

def kill_zombie_stale(now, wf=ZOMBIE_WF):
    """取消「仍 in_progress/pending/queued 但最后更新超阈值静止」的 run，释放并发槽。
    判定用 updated_at 陈旧度（而非创建时间）：正常 run 的 updated_at 会随步骤推进持续刷新，
    卡死僵尸则静止不动——这样不论盘前盘后创建，只要静止超 ZOMBIE_STALE_MAX_MIN 分钟就清，
    避免旧逻辑把 18:xx 创建的挂死 run 误当「盘后生成轮」保护而漏杀（曾导致占槽堵死当晚盘后链）。
    真正在跑的盘后生成轮 updated_at 持续刷新，不会被误杀。"""
    d = api("GET", f"/repos/{REPO}/actions/workflows/{wf}/runs?per_page=30")
    runs = d.get("workflow_runs", []) if isinstance(d, dict) else []
    killed = 0
    for r in runs:
        stt = r.get("status")
        if stt not in ("in_progress", "pending", "queued"):
            continue
        try:
            ut = datetime.datetime.fromisoformat(
                r.get("updated_at", "").replace("Z", "+00:00")).astimezone(CST)
        except Exception:
            continue
        stale_min = (now - ut).total_seconds() / 60.0
        if stale_min <= ZOMBIE_STALE_MAX_MIN:
            continue  # 仍在活跃推进，正常跑
        rid = r.get("id")
        print(f"  🧟 卡死僵尸 {wf} run {rid}（{stt} 最后更新 {ut.strftime('%H:%M')}CST，"
              f"已静止 {stale_min:.0f} 分钟），取消以释放并发槽")
        st = api_delete(f"/repos/{REPO}/actions/runs/{rid}")
        if st in (200, 202, 204):
            killed += 1
            print(f"     ✅ 已取消 {rid} (HTTP {st})")
        else:
            print(f"     ⚠️ 取消 {rid} 返回 HTTP {st}")
    if killed == 0:
        print("  🧟 当前无卡死僵尸 run（并发槽干净）")

# 3) 动量共识筛选重算（2026-08-22 起脱离 PDF，由 gen_momentum_self 每日盘后自合成）：
#    V2 与 MOMENTUM_FILTER 现已随盘后构建(update_v8.run_experiment_cards)每日自动重算。
#    本 dispatcher 仅作兜底：当 V2 生成日 < 今日（盘后构建漏跑/被冲掉）时，派发轻量链补算。
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
MOMENTUM_LITE_WF = "v8_algo_intraday_lite.yml"
MOMENTUM_LITE_COOLDOWN_MIN = 120

def _first_date(s):
    """从字符串提取首个 YYYY-MM-DD（generated/date 通用）。"""
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s or "")
    return m.group(1) if m else None

def _momentum_filter_needs_recompute():
    """V2 生成日 < 今日(交易日漏跑)或 filter 缺失 → 需重算（兜底，非 OCR 触发）。"""
    f = os.path.join(REPO_ROOT, "data", "MOMENTUM_FILTER.js")
    s = os.path.join(REPO_ROOT, "data", "STOCK_MOMENTUM_STATE_V2.js")
    if not os.path.exists(f):
        return True, "MOMENTUM_FILTER.js 缺失"
    if not os.path.exists(s):
        return True, "STOCK_MOMENTUM_STATE_V2.js 缺失(需补算)"
    try:
        ssrc = open(s, encoding="utf-8").read()
        mg = re.search(r'["\']generated["\']\s*:\s*["\']([\d-]+)', ssrc)
        vg = _first_date(mg.group(1)) if mg else None
        today = datetime.datetime.now(CST).strftime("%Y-%m-%d")
        if not vg:
            return True, "V2 无法解析 generated"
        if vg < today:
            return True, "V2 陈旧(生成 %s < 今日 %s)，需补算" % (vg, today)
        return False, "V2 已为今日(%s)，无需重算" % vg
    except Exception as e:
        return True, "解析异常: " + str(e)

def dispatch_momentum_intraday(now):
    need, why = _momentum_filter_needs_recompute()
    if not need:
        print("  动量轻量: " + why + "，跳过")
        return
    # 冷却：最近冷却窗口内已成功跑过则跳过（防 30 分轮询频派发）
    lr = latest_run(MOMENTUM_LITE_WF)
    if lr:
        created, concl = lr
        ct = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(CST)
        ago = (now - ct).total_seconds() / 60.0
        if concl == "success" and ago <= MOMENTUM_LITE_COOLDOWN_MIN:
            print("  动量轻量: %s 成功于 %s(%.0f分钟前)，冷却跳过" % (MOMENTUM_LITE_WF, ct.strftime("%H:%M"), ago))
            return
    print("  动量轻量: " + why + "，派发 " + MOMENTUM_LITE_WF)
    dispatch(MOMENTUM_LITE_WF)

def main():
    now = datetime.datetime.now(CST)
    print(f"🛰️ 云端兜底调度器 @ {now.strftime('%Y-%m-%d %H:%M CST')}")

    # 0) 僵尸看门狗：先清掉卡死（updated_at 静止超阈值）的 run，避免它占用单并发槽
    #    把当晚盘后生成轮堵死（#3 慢性陈旧根因）。每 30 分随 cn_fetch 触发一次。
    #    #1 改 cancel-in-progress:false 后，v8_cn_fetch_cloud 自身也不再自取消，
    #    故一并清理其可能堆积的卡死 run，防止队列雪崩。
    #    ⚠️ 2026-08-24 修正：旧逻辑按 created_at 的 hour>=18 误判 18:xx 僵尸为「盘后生成轮」而漏杀，
    #    改用 updated_at 静止度判定后，不论盘前盘后，卡死即清、在跑不误杀。
    print("🧟 僵尸看门狗（按 updated_at 静止度判定卡死 run）：")
    kill_zombie_stale(now, "v8_algo_cloud.yml")
    kill_zombie_stale(now, "v8_cn_fetch_cloud.yml")

    # 1) 风险温度计：最近 90 分钟内无成功运行则补发
    rg = latest_run("v8_risk_gauge.yml")
    need_rg = True
    if rg:
        created, concl = rg
        # created 为 UTC ISO；转 CST 计算差
        ct = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(CST)
        ago = (now - ct).total_seconds() / 60.0
        if concl == "success" and ago <= 90:
            need_rg = False
            print(f"  风险温度计: 最近成功于 {ct.strftime('%H:%M')}（{ago:.0f}分钟前），无需补发")
    if need_rg:
        allow, why = dispatch_guard("v8_risk_gauge.yml", now, cooldown_min=30, max_fail_today=5)
        if allow:
            print("  风险温度计: 超时未更新，派发（%s）" % why)
            dispatch("v8_risk_gauge.yml")
        else:
            print("  风险温度计: %s" % why)

    # 2) 算法链：仅交易日且 >=18:00 且今日 18:00 后未成功跑过才派发
    #    2026-08-22 根因⑫：非交易日（周末/节假日）不派发——v8_algo_cloud 的交易日历
    #    gate 会跳过 step7（实证 08-22 03:2x 一批 run 全 skipped 秒退），派了也白跑。
    #    2026-09-02 根因：16:xx 创建的 algo run 会被 run_algorithms 的 18:00 时间门跳过，
    #    仍判 success 但无候选池/三重共识/最终推荐；必须要求成功 run 创建于 18:00 后。
    if now.hour >= 18 and _is_trading_day(now):
        al = latest_run("v8_algo_cloud.yml")
        ran_today = False
        if al:
            created, concl = al
            ct = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(CST)
            if concl == "success" and ct.date() == now.date() and ct.hour >= 18:
                ran_today = True
                print(f"  算法链: 今日 18:00 后已成功于 {ct.strftime('%H:%M')}，无需补发")
        if not ran_today:
            # 🛡 2026-09-07 22:2x 一劳永逸根治（主人令「互踢/暴风/覆盖不想再看到」·方案 B 配套 1+2）：
            #   ① cooldown 45→20 分钟（用户令≥20min）：与 v8_cn_fetch_cloud 30 分轮询错峰，永不重叠。
            #   ② max_fail_today 3→2：熔断更激进（今日已观察 13 派发 9 cancelled 2 failure 浪费 2h+）。
            #   ③ 派发改 repository_dispatch（dispatch_repo_dispatch）：触发 v8_algo_cloud.yml 探针路由
            #      → lemoncat-cn 在线则转派 v8_algo_run.yml（cn 链，**与云端不同 concurrency group**
            #      → 永不互踢）→ cn 跑全链 84min；cn 离线才回落云端，从根上治互踢/覆盖。
            #   ④ _final_recommend_still_stale() 二次校验：防止 run "success 但无 final_recommend" 的
            #      假绿灯（已被 2026-09-02 根因锁过：18:xx 创建的 run 18:00 门控跳过、success 但 0 产物）。
            if not _final_recommend_still_stale():
                print("  算法链: 核心产物（final_recommend/crds/candidate）均已今日新鲜，跳过重派")
            else:
                allow, why = dispatch_guard("v8_algo_cloud.yml", now,
                                            cooldown_min=20, max_fail_today=2)
                if allow:
                    print(f"  算法链: 产物仍陈旧 + {why} → repository_dispatch 触发探针路由（自动转派 cn）")
                    dispatch_repo_dispatch("v8_algo_cloud.yml", client_payload={})
                else:
                    print("  算法链: %s" % why)
    else:
        if not _is_trading_day(now):
            print(f"  算法链: 非交易日（{now.strftime('%Y-%m-%d %H:%M')}），跳过算法链派发")
        else:
            print(f"  算法链: 当前 {now.hour}:xx 未到 18:00，跳过（等盘后 LHB 发布）")

    # 3) 动量共识筛选重算（新 OCR 输入触发 + 冷却）
    dispatch_momentum_intraday(now)

    print("🛰️ 兜底调度完成")

if __name__ == "__main__":
    main()
