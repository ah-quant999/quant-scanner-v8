#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地凭据配置助手。
把观澜台（知识星球）token 安全写入 data/ 目录，
不会提交到 Git（.gitignore 已忽略该文件）。

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

    # maharo 已下线——全链路移除后不再设置 cookie（保留 zsxq token 写入以供本机自愈兜底）

    print("=" * 60)
    print("配置完成。下一次运行 guanlan_extractor.py / self_heal_monitor.py 时会自动读取该凭据。")
    print("=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已取消。")
        sys.exit(1)
