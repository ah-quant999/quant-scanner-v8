#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_mahoro_signals.py
───────────────────────
拉取 mahoro.cn 投行信号数据，与金股池交叉比对。

运行时机：每天三次研报更新时（09:15 / 11:45 / 19:30），由 batch_update.py 统一调度。
数据存入：data/mahoro_signals.json

自动化模式：
  python fetch_mahoro_signals.py --non-interactive
  无有效 cookie 时跳过（不阻塞），返回 exit code 0（不影响 batch_update 其他步骤）。
  
首次使用需交互式登录一次，之后 cookie 缓存复用：
  python fetch_mahoro_signals.py
"""

import json, os, sys, time, argparse
import urllib.request, urllib.error

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# v8 原生化钩子（2026-08-02）：v8 仓通过 V8_OUT_DIR 环境变量重定向 DATA_DIR 到仓库根 out/
# 同时 v8 build_candidate_pool.py 读的是「mahoro_signals.json」（拼写 mahoro），
# 而本脚本默认写「maharo_signals.json」（拼写 maharo）—— 在 v8 环境下改写为正确名
_V8_OUT = os.environ.get("V8_OUT_DIR")
if _V8_OUT:
    DATA_DIR = _V8_OUT
    GOLD_POOL_JSON = os.path.join(DATA_DIR, "gold_pool.json")
    OUTPUT_JSON = os.path.join(DATA_DIR, "mahoro_signals.json")  # 拼写 mahoro 兼容下游
    # v8 cookie 在 v8 data/（被 .gitignore 屏蔽），不在 v8 out/
    COOKIE_FILE = os.path.join(os.path.dirname(_V8_OUT), "data", ".mahoro_cookies.txt")
    os.makedirs(DATA_DIR, exist_ok=True)
else:
    DATA_DIR = os.path.join(BASE_DIR, "data")
    OUTPUT_JSON = os.path.join(DATA_DIR, "maharo_signals.json")
    GOLD_POOL_JSON = os.path.join(DATA_DIR, "gold_pool.json")
    COOKIE_FILE = os.path.join(DATA_DIR, ".mahoro_cookies.txt")

MAHORO_API_SIGNALS = "https://data.mahoro.cn/api/signals"
MAHORO_AUTH_SEND = "https://data.mahoro.cn/api/auth/send-code"
MAHORO_AUTH_VERIFY = "https://data.mahoro.cn/api/auth/verify-code"

def load_json(path, default=None):
    if default is None: default = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def http_post(url, data, cookies=None):
    """Simple HTTP POST"""
    import ssl
    ctx = ssl.create_default_context()
    data_bytes = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=data_bytes, 
                                   headers={"Content-Type": "application/json"},
                                   method="POST")
    if cookies:
        req.add_header("Cookie", cookies)
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        return json.load(resp), resp.info().get_all("Set-Cookie") or []
    except Exception as e:
        print(f"  [ERR] POST {url}: {e}")
        return None, []

def http_get(url, cookies=""):
    """Simple HTTP GET"""
    import ssl
    ctx = ssl.create_default_context()
    req = urllib.request.Request(url, headers={"Cookie": cookies} if cookies else {})
    try:
        resp = urllib.request.urlopen(req, timeout=15, context=ctx)
        return json.load(resp)
    except Exception as e:
        print(f"  [ERR] GET {url}: {e}")
        return None

def authenticate(email, non_interactive=False, code=None):
    """登录 mahoro.cn，返回 cookie 字符串。
    非交互模式下：无有效 cookie 则直接返回 None，不阻塞。
    code 参数：直接使用提供的验证码，跳过 input()。
    """
    # Check saved cookies
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            saved = f.read().strip()
        if saved:
            # Test if cookie still valid
            test = http_get(MAHORO_API_SIGNALS + "?limit=1", saved)
            if test and test.get("signals") is not None:
                print(f"  ✓ 复用已有 cookie")
                return saved
            print(f"  ⚠️ cookie 已过期，需重新登录")

    # 非交互模式：无有效 cookie → 跳过
    if non_interactive:
        print(f"  ⚠️ 非交互模式：无有效 cookie，跳过 mahoro 信号拉取")
        print(f"  💡 手动运行 `python fetch_mahoro_signals.py` 登录一次后可复用")
        return None

    # 交互模式：引导登录
    print(f"  ℹ️  首次使用需登录 mahoro.cn")
    # Step 1: Send code（如果已提供 code 则直接验证，跳过发送）
    if code:
        code = code.strip()
        print(f"  使用提供的验证码: {code}")
    else:
        resp, _ = http_post(MAHORO_AUTH_SEND, {"email": email})
        if not resp or not resp.get("ok"):
            print(f"  ❌ 发送验证码失败: {resp}")
            return None
        print(f"  ✓ 验证码已发送到 {email}，5分钟有效")
        code = input("  请输入邮箱验证码: ").strip()
    
    if not code:
        print("  ❌ 未输入验证码")
        return None

    # Step 3: Verify
    resp, cookies = http_post(MAHORO_AUTH_VERIFY, {"email": email, "code": code})
    if not resp or not resp.get("ok"):
        print(f"  ❌ 验证失败: {resp}")
        return None

    # 保存 cookie（提取所有 set-cookie，不只挑名字）
    cookie_parts = []
    for c in cookies:
        cookie_parts.append(c.split(";")[0])
    cookie_str = "; ".join(cookie_parts)
    
    if cookie_str:
        with open(COOKIE_FILE, "w") as f:
            f.write(cookie_str)
        print(f"  ✓ 登录成功，cookie 已缓存")
    else:
        print(f"  ⚠️ 未获取到 cookie")
    
    return cookie_str

def fetch_signals(cookie_str):
    """拉取当天所有投行信号"""
    all_signals = []
    offset = 0
    limit = 200
    while True:
        data = http_get(f"{MAHORO_API_SIGNALS}?limit={limit}&offset={offset}", cookie_str)
        if not data:
            break
        signals = data.get("signals", [])
        if not signals:
            break
        all_signals.extend(signals)
        if len(signals) < limit:
            break
        offset += limit

    return all_signals, data.get("banks", []), data.get("stance_counts", {})

def cross_reference(signals, gold_pool):
    """将mahoro信号与金股池交叉比对"""
    # 建立金股池 ticker 映射
    gp_codes = {}
    for k, s in gold_pool.get("stocks", {}).items():
        code = s.get("code", "")
        market = k.split("_")[0] if "_" in k else ""
        if market == "sh": ticker = f"{code}.SH"
        elif market == "sz": ticker = f"{code}.SZ"
        elif market == "hk": ticker = f"{int(code):04d}.HK"
        else: ticker = ""
        if ticker:
            gp_codes[ticker] = {"code": code, "name": s.get("name", ""), "market": market}

    matches = []
    for signal in signals:
        for company in signal.get("companies", []):
            ticker = company.get("ticker", "")
            if ticker in gp_codes:
                gp = gp_codes[ticker]
                matches.append({
                    "code": gp["code"],
                    "name": gp["name"],
                    "market": gp["market"],
                    "bank": signal.get("bank", ""),
                    "stance": signal.get("stance", ""),
                    "key_point": signal.get("key_point", "")[:120],
                    "published_at": signal.get("published_at", ""),
                })

    return matches

def main():
    parser = argparse.ArgumentParser(description="拉取 mahoro.cn 投行信号")
    parser.add_argument("--non-interactive", "-n", action="store_true",
                        help="自动化模式：无有效 cookie 时跳过，不阻塞")
    parser.add_argument("--code", "-c", type=str, default=None,
                        help="直接提供邮箱验证码（跳过交互输入）")
    args = parser.parse_args()

    print("=== 拉取 mahoro 投行信号 ===\n")
    
    email = "ljcat999@gmail.com"
    cookie = authenticate(email, non_interactive=args.non_interactive, code=args.code)
    if not cookie:
        if args.non_interactive:
            print("\n⏭️  跳过（非交互模式无有效 cookie）")
            print("  ⚠️ cookie 已过期或不存在，需要手动运行登录刷新")
            return 2  # 非零退出码，让 batch_update 能感知失败（不阻塞但可记录）
        print("\n❌ 登录失败")
        return 1

    signals, banks, stance = fetch_signals(cookie)
    print(f"\n  今日信号: {len(signals)} 条, {len(banks)} 家投行")
    print(f"  立场分布: bullish={stance.get('bullish',0)}, neutral={stance.get('neutral',0)}, mixed={stance.get('mixed',0)}, bearish={stance.get('bearish',0)}")

    # 交叉比对
    gold_pool = load_json(GOLD_POOL_JSON)
    matches = cross_reference(signals, gold_pool)
    print(f"  金股池重叠: {len(matches)} 只")

    # 保存结果
    output = {
        "fetch_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_signals": len(signals),
        "banks": banks,
        "stance_counts": stance,
        "gold_pool_matches": matches,
        "raw_signals": signals,
    }
    save_json(OUTPUT_JSON, output)
    print(f"\n✅ 已保存: {OUTPUT_JSON}")
    
    return 0

if __name__ == "__main__":
    try:
        from fetch_logger import record_success, record_failure
    except ImportError:
        def record_success(_f): pass
        def record_failure(_f, _e=None): pass

    try:
        ret = main()
        if ret == 0:
            record_success(__file__)
        else:
            reason = "cookie过期" if ret == 2 else "登录失败"
            record_failure(__file__, f"exit={ret} ({reason})")
        sys.exit(ret)
    except Exception as e:
        record_failure(__file__, str(e))
        raise
