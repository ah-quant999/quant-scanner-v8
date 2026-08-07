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
import os, sys, json, urllib.request, urllib.error, datetime

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

def dispatch(wf_file, inputs=None):
    payload = {"ref": "main"}
    if inputs:
        payload["inputs"] = inputs
    r = api("POST", f"/repos/{REPO}/actions/workflows/{wf_file}/dispatches", payload)
    if r:
        print(f"  ✅ 已派发 {wf_file}")
    else:
        print(f"  ❌ 派发 {wf_file} 失败")

def main():
    now = datetime.datetime.now(CST)
    print(f"🛰️ 云端兜底调度器 @ {now.strftime('%Y-%m-%d %H:%M CST')}")

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
        print("  风险温度计: 超时未更新，派发")
        dispatch("v8_risk_gauge.yml")

    # 2) 算法链：仅 >=18:00 且今日未成功跑过才派发
    if now.hour >= 18:
        al = latest_run("v8_algo_cloud.yml")
        ran_today = False
        if al:
            created, concl = al
            ct = datetime.datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(CST)
            if concl == "success" and ct.date() == now.date():
                ran_today = True
                print(f"  算法链: 今日已成功于 {ct.strftime('%H:%M')}，无需补发")
        if not ran_today:
            print("  算法链: 今日尚未成功运行（或已过时），派发")
            dispatch("v8_algo_cloud.yml")
    else:
        print(f"  算法链: 当前 {now.hour}:xx 未到 18:00，跳过（等盘后 LHB 发布）")

    print("🛰️ 兜底调度完成")

if __name__ == "__main__":
    main()
