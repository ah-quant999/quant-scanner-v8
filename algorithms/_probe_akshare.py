import sys, time
try:
    import akshare as ak
    print("akshare version:", ak.__version__)
except Exception as e:
    print("IMPORT FAIL:", e); sys.exit(1)

def try_call(name, fn, *a, **k):
    """调用 fn 并打印类型/行数/耗时；仅对瞬时网络错误退避重试（1/3/5s）。"""
    try:
        import requests
    except ImportError:
        requests = None
    last = None
    for i in range(3):
        try:
            t = time.time()
            r = fn(*a, **k)
            print(f"[{name}] OK type={type(r).__name__} rows={getattr(r,'shape',None)} sec={time.time()-t:.1f}")
            return r
        except Exception as e:
            transient = requests and isinstance(
                e, (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                    requests.exceptions.ChunkedEncodingError)
            )
            if transient and i < 2:
                last = e
                print(f"[{name}] 网络抖动重试({i+1}/3): {type(e).__name__}")
                time.sleep(1 + i * 2)
                continue
            print(f"[{name}] FAIL: {type(e).__name__}: {str(e)[:160]}")
            return None
    print(f"[{name}] 重试后仍失败: {type(last).__name__}")
    return None

r1 = try_call("stock_individual_info_em(688001)", ak.stock_individual_info_em, symbol="688001")
if r1 is not None:
    try:
        print("  info keys:", list(r1.keys()) if hasattr(r1, 'keys') else 'n/a')
        if '概念' in r1:
            print("  概念:", r1['概念'])
    except Exception as e:
        print("  parse err", e)

r2 = try_call("stock_board_concept_cons_em(688001)", ak.stock_board_concept_cons_em, symbol="688001")
if r2 is not None:
    try:
        cols = list(r2.columns) if hasattr(r2, 'columns') else None
        print("  cols:", cols)
        if cols and '概念名称' in cols:
            print("  概念列表:", r2['概念名称'].tolist()[:20])
    except Exception as e:
        print("  parse err", e)

r3 = try_call("stock_bj_a_spot_em", ak.stock_bj_a_spot_em)
if r3 is not None:
    try:
        print("  北交所 rows:", len(r3))
        print("  cols:", list(r3.columns)[:15])
        code_col = '代码' if '代码' in r3.columns else r3.columns[0]
        print("  sample codes:", r3[code_col].tolist()[:10])
    except Exception as e:
        print("  parse err", e)
