#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把本地凭据整理成「可直接粘贴到 GitHub Secrets」的形式打印出来。

背景：
  data/zsxq_token.json 被 .gitignore 屏蔽，云端 GitHub Actions checkout 后拿不到
  → 外资研投研报恒为 0 只。解决办法是把同样的值存进 GitHub 仓库 Secrets，
  workflow 已配好注入：
      .github/workflows/v8_algo_cloud.yml
        ZSXQ_TOKEN: ${{ secrets.ZSXQ_TOKEN }}

用法：
    python scripts/show_github_secrets.py

⚠️ 输出包含明文凭据，只在自己电脑上运行，别截图外发。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
ZSXQ_PATH = os.path.join(DATA_DIR, "zsxq_token.json")

REPO_SECRET_URL = "https://github.com/ah-quant999/quant-scanner-v8/settings/secrets/actions"


def read_zsxq():
    if not os.path.exists(ZSXQ_PATH):
        return None
    try:
        with open(ZSXQ_PATH, "r", encoding="utf-8") as f:
            return (json.load(f).get("token") or "").strip() or None
    except Exception as e:
        print(f"  [ERR] 解析 {ZSXQ_PATH} 失败: {e}")
        return None


def emit(secret_name, value, hint):
    print("-" * 68)
    print(f"Secret 名称（Name）： {secret_name}")
    if value:
        print("Secret 值（Secret）：↓↓↓ 整段复制，不要带引号、不要多空格 ↓↓↓")
        print()
        print(value)
        print()
        print(f"（长度 {len(value)} 字符）")
    else:
        print(f"⚠️ 本地还没有这个凭据 —— {hint}")
    print()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("=" * 68)
    print("GitHub Secrets 配置助手")
    print("=" * 68)
    print("填写地址（复制到浏览器打开，需已登录 GitHub）：")
    print(f"  {REPO_SECRET_URL}")
    print()
    print("在页面上点 [New repository secret]，按下面两组内容各建一条。")
    print()

    emit("ZSXQ_TOKEN", read_zsxq(),
         "先运行 python scripts/setup_credentials.py 写入外资研投 token")

    print("=" * 68)
    print("填完后，云端算法链（v8_algo_cloud.yml）下次运行就能抓外资研投源。")
    print("token 过期后重新执行上面的步骤，再回来更新同名 Secret 即可。")
    print("=" * 68)


if __name__ == "__main__":
    main()
