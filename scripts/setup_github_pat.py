#!/usr/bin/env python3
"""
安全地把 GitHub PAT 写到本地文件，供本机脚本读取。
不通过网络发送 token，只是把它存在仓库 data/ 目录下的隐藏文件里。
"""
import getpass
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOKEN_FILE = os.path.join(ROOT, "data", ".github_pat.txt")

def main():
    print("为了让我能跟踪 GitHub Actions 运行状态，需要一个 Personal Access Token。")
    print("1) 打开 https://github.com/settings/tokens")
    print("2) 点击 Generate new token (classic)")
    print("3) 至少勾选：repo + workflow")
    print("4) 生成后复制 token（以 ghp_ 开头）")
    print()
    print("在下面粘贴 token（输入时不会显示）：")
    token = getpass.getpass("Token: ").strip()
    if not token:
        print("未输入，退出。")
        sys.exit(1)
    if not token.startswith("ghp_") and not token.startswith("github_pat_"):
        print("警告：token 格式看起来不像 GitHub PAT，请确认是否正确。")
        confirm = input("仍然保存吗？y/N: ").strip().lower()
        if confirm != "y":
            print("已取消。")
            sys.exit(1)
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token)
    print(f"已保存到：{TOKEN_FILE}")
    print("现在告诉我「写好了」，我会读取并跟踪 Actions 运行。")

if __name__ == "__main__":
    main()
