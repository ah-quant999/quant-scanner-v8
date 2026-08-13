"""
run_dividend_refresh.py — 分红方案每日刷新调度入口（供盘前/晚间 automation 调用）。

流程（一劳永逸 + 防冲突）：
  1. 调 algorithms/refresh_dividend_cninfo.py 用 cninfo 刷新重点池(持仓+候选池+黄金池)分红方案
     → 写回 raw_data/stock_quote.json 并重建 data/STOCK_QUOTE.js
  2. git add 仅这两个数据文件（显式路径，绝不 git add -A）
  3. 有变更才 commit（无变更直接退出，避免空提交）
  4. git fetch origin + git rebase origin/main（云端 build 频繁推送，先接远端再推，避免 non-fast-forward）
  5. git push origin main

注意：
  - 本机 SSH 已配（remote=git@github.com:ah-quant999/quant-scanner-v8.git），push 走 SSH 不触发凭据助手挂死。
  - cloud_fetch_v8.py 不生成 stock_quote，故 data/STOCK_QUOTE.js 不会被云端覆盖；本提交是权威源。
  - 全量重建行情(fetch_stock_quote_v8.py)后会用 em 旧源覆盖 dividend，务必在其后补跑本脚本。
"""
import subprocess
import sys
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
while not (HERE / "raw_data").exists() and HERE.parent != HERE:
    HERE = HERE.parent
PY = r"C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
FILES = ["raw_data/stock_quote.json", "data/STOCK_QUOTE.js"]


def run(cmd, **kw):
    return subprocess.run(cmd, cwd=str(HERE), **kw)


def main():
    print("== 1/5 刷新 cninfo 分红方案 ==")
    r = run([PY, "algorithms/refresh_dividend_cninfo.py"])
    if r.returncode != 0:
        print("❌ refresh 失败 rc=", r.returncode)
        sys.exit(1)

    print("== 2/5 暂存数据文件 ==")
    run(["git", "add"] + FILES, check=True)

    st = run(["git", "status", "--porcelain", "--"] + FILES, capture_output=True, text=True)
    if not st.stdout.strip():
        print("✅ 无分红变更，跳过提交")
        sys.exit(0)

    print("== 3/5 提交 ==")
    run(["git", "commit", "-m",
         "chore(v8/dividend): 每日cninfo分红方案刷新(重点池 持仓+候选+黄金)"], check=True)

    print("== 4/5 fetch + rebase 接远端 ==")
    run(["git", "fetch", "origin"], check=True)
    rb = run(["git", "rebase", "origin/main"])
    if rb.returncode != 0:
        # 云端频繁重建 data/STOCK_QUOTE.js / raw_data/stock_quote.json → 大概率冲突。
        # 自愈：对冲突的数据文件取 origin 干净版，再依据 raw_data 重建 STOCK_QUOTE.js，
        # 重新跑 refresh 补回 cninfo 分红，避免手解 5MB JSON 冲突标记。
        print("⚠️ rebase 冲突，尝试自愈（重建生成文件）...")
        st = run(["git", "status", "--porcelain"], capture_output=True, text=True)
        conflicted = [ln.split()[-1] for ln in st.stdout.splitlines()
                      if ln[:2] in ("UU", "AA", "UA", "AU") or ln[0] == "U" or ln[1] == "U"]
        if "data/STOCK_QUOTE.js" in conflicted:
            run(["git", "checkout", "--ours", "data/STOCK_QUOTE.js"])
        if "raw_data/stock_quote.json" in conflicted:
            run(["git", "checkout", "--ours", "raw_data/stock_quote.json"])
            # 取回 origin 干净版后，重新跑 refresh 把 cninfo 分红补到最新 base 上
            run([PY, "algorithms/refresh_dividend_cninfo.py"])
        # 无论哪种冲突，最终都用 raw_data 重建一次 STOCK_QUOTE.js 保证一致
        run([PY, "-c",
             "import json,sys;sys.path.insert(0,'.');import update_v8;"
             "q=json.load(open('raw_data/stock_quote.json',encoding='utf-8'));"
             "update_v8._write_js('STOCK_QUOTE',q)"])
        run(["git", "add"] + FILES)
        rb2 = run(["git", "rebase", "--continue"],
                  env={**os.environ, "GIT_EDITOR": "true"})
        if rb2.returncode != 0:
            run(["git", "rebase", "--abort"])
            print("❌ rebase 自愈失败，已 abort，未推送（人工介入）")
            sys.exit(1)

    print("== 5/5 push ==")
    p = run(["git", "push", "origin", "main"])
    print("push rc=", p.returncode)
    sys.exit(p.returncode)


if __name__ == "__main__":
    main()
