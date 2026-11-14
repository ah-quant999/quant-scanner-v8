# HANDOVER｜阿狸咪的工程师 → 小九｜2026-11-14 23:47｜akshare未pin云端新版移除接口四脚本AttributeError断裂

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

algo 链（☁️ v8 盘后算法链(云端) `v8_algo_cloud.yml`）23:18:55 chain-end **ok=39 fail=7**（前两轮 06:27/18:05 均 ok=43 fail=3），新增 4 个 akshare AttributeError 簇：`fetch_stock_names` / `build_candidate_pool`（`stock_hk_spot` 属性不存在）、`scripts/fetch_index_history`（`stock_zh_index_daily` 属性不存在）、`refresh_stock_metadata`（级联）。根因指向依赖**未 pin 上限**：workflow OPTIONAL 段 `pip install akshare baostock` 每轮装 PyPI 最新版，新版已移除上述接口。挂账 `akshare-unpinned-runner-api-removal-1114`（P1/todo/owner=你）。按铁律未派发未重试。

---

## 正文

### 实证（全部远端 API 实核，2026-11-14 23:37–23:45 CST）

| 项 | 证据 | 结果 |
|---|---|---|
| chain-end | run 43594897073（run_start 20:30:48，workflow_dispatch）raw_data/algo_run_report.json | ok=39 fail=7 |
| 对比基线 | 11-14 06:27:40 chain-end 与 18:05:01 chain-end | 均 ok=43 fail=3，无 akshare 错误 ⇒ 20:30 轮**新增 4 fail** |
| 栈帧逐字 | run 43594897073 job 132447260882，23:16:30 CST | 见下 |
| 影响面 | raw_data/algo_run_report.json failed_scripts | 港股名单/候选池生成/元数据巡检/指数历史 4 链路本轮全 fail |

```
for fn in (ak.stock_hk_spot, ak.stock_hk_spot_em):
                 ^^^^^^^^^^^^^^^^
AttributeError: module 'akshare' has no attribute 'stock_hk_spot'
```

`scripts/fetch_index_history.py`：`[fetch_index_history] akshare 拉取失败: module 'akshare' has no attribute 'stock_zh_index_daily'`（拉上证指数近 5 年日 K）。
`refresh_stock_metadata.py`：`❌ fetch_stock_names 失败，停止元数据巡检`（级联）。

### 根因指向（待你在 runner 实锤版本号）

1. `v8_algo_cloud.yml` 安装段：`OPTIONAL="akshare baostock"`，`python -m pip install -q --retries 2 --timeout 90 -i $IDX $OPTIONAL` —— **无版本上限**，每轮装 PyPI 最新。
2. `requirements.txt` 同样仅 `akshare>=1.15` 无上限。
3. workflow 注释自称「缺失不影响 B/D/E 算法链」—— 既有保护只覆盖「**没装上**」，**没覆盖「装上但 API 断裂」**。
4. 旁证：14:40 轮尚正常、20:30 轮突然 AttributeError，与「PyPI 新版本发布窗口内被拉到」一致。⚠️ OPTIONAL 安装为 `-q` 静默，日志无版本号，我未能直接实锤安装版本；请在 runner 实测 `pip show akshare` 或回放安装日志实锤。

### 请完成（一劳永逸口径，禁前端硬编）

1. **pin 版本**：`v8_algo_cloud.yml` OPTIONAL 行 + `requirements.txt`（参考挂账 `fetch_stock_quote_v8-third-source` 中「本机 akshare 1.18.64 已知可用」），并同步其它含 `pip install akshare` 的 workflow（如 `v8_cn_fetch_cloud.yml` L418）。
2. 或/并 **hasattr 探测降级**：`fetch_stock_names` 对 `stock_hk_spot` 缺失时单走 `stock_hk_spot_em`（注意先探测 em 接口在新版是否还在）；`fetch_index_history` 换替代接口。
3. **修复判据**：修复提交推 main 后，algo 链下一轮 run **head_sha ≥ 修复提交 sha** 且 run_report `failed_scripts` 不再含上述四脚本（**看产物不看 run conclusion**）；build_candidate_pool 候选池产物恢复产出。
4. 已知非问题：`refresh_kline_freshness`/`fetch_multiyear_kline` 超时=软闸基线；`market_regime` 缺 macro.json=你 23:31 已回执微修（item `market-regime-macro-json-bootstrap-fail-1114`），本件与其无重叠。

### 防踩踏声明

按铁律未派发未重试：algo 23:18 已有 in_progress 轮 43609472862（head c3d49b304e，早于你 23:31 微修提交 30b234583a，跑旧代码属预期，下轮自然复现修复后行为）。本件登记不触发任何派发。

HANDOFF.yaml 已同步（同批 ledger 重算，Git Data API 六步，base blob=4c4e4cdd46）。
