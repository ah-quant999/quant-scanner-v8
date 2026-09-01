import time
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
            print(f"[{name}] FAIL: {type(e).__name__}: {str(e)[:140]}")
            return None
    print(f"[{name}] 重试后仍失败: {type(last).__name__}")
    return None

# 同花顺概念 (fallback 1)
try:
    import akshare as ak
    r = try_call("stock_board_concept_name_ths", ak.stock_board_concept_name_ths)
    if r is not None:
        print("  ths concept cols:", list(r.columns)[:10] if hasattr(r,'columns') else 'n/a')
    r2 = try_call("stock_board_concept_cons_ths(symbol=000001)", ak.stock_board_concept_cons_ths, symbol="000001")
    if r2 is not None:
        print("  ths cons cols:", list(r2.columns)[:10] if hasattr(r2,'columns') else 'n/a')
except Exception as e:
    print("ths import/run err", e)

# Sina 个股资料 (fallback 2 via stock_sina)
try:
    import akshare as ak
    r3 = try_call("stock_individual_info_em(sina)", ak.stock_individual_info_em, symbol="688001")
except Exception as e:
    print("sina err", e)

# 试试 stock_zh_a_spot_em (东财全A快照) 是否也连不上 -> 确认是东财整体不可达
try:
    import akshare as ak
    r4 = try_call("stock_zh_a_spot_em", ak.stock_zh_a_spot_em)
    if r4 is not None:
        print("  spot cols:", list(r4.columns)[:8])
except Exception as e:
    print("spot err", e)
