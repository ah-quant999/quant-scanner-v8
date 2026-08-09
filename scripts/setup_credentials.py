#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地凭据配置助手。
把观澜台（知识星球）token 和 maharo cookie 安全写入 data/ 目录，
不会提交到 Git（.gitignore 已忽略这两个文件）。

用法：
    python scripts/setup_credentials.py
然后按提示粘贴凭据即可。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
ZSXQ_PATH = os.path.join(DATA_DIR, "zsxq_token.json")
# ⚠️ 拼写必须是 mahoro（不是 maharo）——algorithms/fetch_maharo_signals.py
#    读的是 data/.mahoro_cookies.txt。写错名字会导致凭据永远读不到，
#    脚本静默走「无有效 cookie → 跳过」分支，研报来源恒为 0 只。
MAHARO_PATH = os.path.join(DATA_DIR, ".mahoro_cookies.txt")


def input_multiline(prompt):
    """读取多行输入，以空行结束（适合粘贴 cookie 字符串）。"""
    print(prompt)
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "" and lines:
            break
        lines.append(line)
    return "\n".join(lines).strip()


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    print("=" * 60)
    print("九宝量化 v8 本地凭据配置")
    print("=" * 60)
    print("说明：你的凭据只保存在本地 data/ 目录，不会进入 Git。\n")

    # 观澜台 token
    print("【观澜台 / 知识星球】")
    print("获取方式：浏览器打开 https://wx.zsxq.com/ → F12 → Application/Storage")
    print("→ Cookies → 找到 zsxq_access_token，或看请求头里的 authorization。")
    token = input("请粘贴 token（直接回车表示不修改）：").strip()

    if token:
        with open(ZSXQ_PATH, "w", encoding="utf-8") as f:
            json.dump({"token": token}, f, ensure_ascii=False, indent=2)
        print(f"✅ 已保存到 {ZSXQ_PATH}\n")
    else:
        if os.path.exists(ZSXQ_PATH):
            print("ℹ️ 未输入，保留现有文件。\n")
        else:
            print("ℹ️ 未输入，未创建文件。\n")

    # maharo cookie
    print("【maharo 研报】")
    print("获取方式：登录 maharo 网站 → F12 → Network → 抓任意 .json/.api 请求")
    print("→ 复制 Request Headers 里的 Cookie 整串。")
    print("请粘贴 cookie（粘贴完后按一次回车结束）：")
    cookie = input_multiline(
        "提示：如果 cookie 只有一行，粘贴后按两下回车即可。"
    ).strip()

    if cookie:
        with open(MAHARO_PATH, "w", encoding="utf-8") as f:
            f.write(cookie)
        print(f"✅ 已保存到 {MAHARO_PATH}\n")
    else:
        if os.path.exists(MAHARO_PATH):
            print("ℹ️ 未输入，保留现有文件。\n")
        else:
            print("ℹ️ 未输入，未创建文件。\n")

    print("=" * 60)
    print("配置完成。下一次运行 run_algorithms.py 时会自动读取这两个凭据。")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。")
        sys.exit(1)
