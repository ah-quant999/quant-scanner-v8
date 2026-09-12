#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
_fill_kcbj_concepts.py — 补全 科创板/北交所 概念映射 (P1, 小九/unit-machine 或 GHA 执行)

数据源（按优先级）:
  1) akshare.stock_board_concept_cons_em(symbol=code)  -> 东财「个股所属概念板块」(主源)
  2) akshare.stock_individual_info_em(symbol=code)    -> 东财个股资料页 '概念' 字段 (备选)
注意：本机(单位机)东财常被防火墙拦截(RemoteDisconnected)；请在 GHA(ubuntu-latest, 出网通畅)运行。

纪律:
  - 单位机/ GHA 执行并推送到 ah-quant999/quant-scanner-v8 的 main。
  - 推送前确认 git add -f（该 JSON 在 .gitignore 白名单内）。
  - 不要硬上：单只失败回退空，不中断整批；抽检后再 --apply。

用法:
  python _fill_kcbj_concepts.py --check-only        # 仅统计目标，不联网
  python _fill_kcbj_concepts.py --apply             # 联网抓取并写回（默认 dry-run 输出 .filled.json）
  python _fill_kcbj_concepts.py --apply --max 20    # 仅前 20 只（调试）
"""
import os, sys, time, json, argparse, random

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "stock_industry_concepts.json")
OUT = os.path.join(HERE, "stock_industry_concepts.filled.json")

KCB_PREFIX = ("688", "689")
BJ_PREFIX = ("8", "4", "92")  # 北交所代码特征（83/87/43/92 开头）


def load():
    with open(SRC, encoding="utf-8") as f:
        return json.load(f)


def is_kcb_empty(d, code):
    if not (code[:3] in KCB_PREFIX):
        return False
    return not d.get(code, {}).get("concepts")


def is_bj_missing(d, code):
    if not (code[0] in ("8", "4") or code[:2] == "92"):
        return False
    return code not in d


def get_bj_list(ak):
    """获取北交所股票列表（东财，GHA 出网通畅时可用）。"""
    try:
        df = ak.stock_bj_a_spot_em()
        col = "代码" if "代码" in df.columns else df.columns[0]
        return [str(c) for c in df[col].tolist()]
    except Exception as e:
        print("  [warn] 北交所列表获取失败:", e)
        return []


def fetch_concepts(ak, code, ind):
    """返回 (concepts_list, industry_str)。失败返回 ([], None)。"""
    # 主源：个股所属概念板块（东财）
    try:
        r = ak.stock_board_concept_cons_em(symbol=code)
        if r is not None and hasattr(r, "columns") and "概念名称" in r.columns:
            cons = [str(x) for x in r["概念名称"].tolist() if x]
            if cons:
                return cons, None
    except Exception as e:
        pass
    # 备选：个股资料页
    try:
        r = ak.stock_individual_info_em(symbol=code)
        if isinstance(r, dict):
            c = r.get("概念")
            if isinstance(c, str) and c:
                cons = [x.strip() for x in c.replace("、", ",").split(",") if x.strip()]
                ind = ind or r.get("行业") or r.get("主营")
                return cons, ind
            if isinstance(c, list):
                return [str(x) for x in c], (ind or r.get("行业"))
    except Exception as e:
        pass
    return [], ind


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写回（默认仅 dry-run 输出 .filled.json）")
    ap.add_argument("--check-only", action="store_true", help="仅统计目标，不联网")
    ap.add_argument("--max", type=int, default=0, help="最多处理 N 只（调试）")
    ap.add_argument("--delay", type=float, default=1.2, help="单只间隔秒（限速）")
    args = ap.parse_args()

    d = load()
    # 目标识别
    kcb_targets = [c for c in list(d.keys()) if is_kcb_empty(d, c)]
    bj_targets = []
    if not args.check_only:
        import akshare as ak
        bj_list = get_bj_list(ak)
        bj_targets = [c for c in bj_list if is_bj_missing(d, c)]
    else:
        # check-only 时也粗略统计已映射北交所数
        bj_targets = [c for c in list(d.keys()) if is_bj_missing(d, c)]

    print(f"[targets] 科创板空概念: {len(kcb_targets)} | 北交所待新增(估算): {len(bj_targets)}")

    if args.check_only:
        print("[check-only] 完成，未联网。")
        return

    import akshare as ak
    targets = kcb_targets + bj_targets
    if args.max:
        targets = targets[: args.max]
    print(f"[run] 处理 {len(targets)} 只, apply={args.apply}")

    filled = 0
    failed = []
    out = dict(d)  # 复制，避免污染
    for i, code in enumerate(targets, 1):
        ind = out.get(code, {}).get("industry")
        board = "科创板" if code[:3] in KCB_PREFIX else "北交所"
        cons, ind2 = fetch_concepts(ak, code, ind)
        if cons:
            rec = dict(out.get(code, {}))
            rec["board"] = rec.get("board") or board
            rec["industry"] = ind2 or rec.get("industry") or ""
            rec["concepts"] = cons
            out[code] = rec
            filled += 1
            print(f"  [{i}/{len(targets)}] {code} {board} OK concepts={len(cons)}")
        else:
            failed.append(code)
            print(f"  [{i}/{len(targets)}] {code} {board} EMPTY/FAIL")
        time.sleep(args.delay + random.random() * 0.6)  # 限速 + 抖动

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"[done] filled={filled} failed={len(failed)} -> {os.path.basename(OUT)}")
    if failed:
        print("[failed sample]", failed[:20])

    if args.apply:
        with open(SRC, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        print(f"[applied] 写回 {os.path.basename(SRC)}")


if __name__ == "__main__":
    main()
