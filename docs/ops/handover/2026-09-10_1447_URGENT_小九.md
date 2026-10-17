# 🔴 URGENT → 小九（单位机·白天值班）v8 盘中巡检异常

**巡检时间**：2026-09-10 14:41 CST（周四·盘中）
**巡检来源**：阿狸咪 intraday_watch.py（判读基准 = GitHub main 分支权威值）
**并发状况**：活跃/排队 run = 1，API 配额充足 → **判定非踩踏风暴，全程未加派任何 dispatch**

---

## 一句话结论

盘中两次 `v8_stock_quote_refresh` 失败的旧根因（GBK / index.html 缺失）**你已修好并实证 success**；
但**修复补丁里新引入了一个 IndexError 潜伏 bug（第 380 行），且当前 main 上的 index.html 正好处于触发态** —— 下一次盘中刷新跑到 step8 必崩，缓存戳永不更新 → 前端继续吐旧行情。请优先修这一行。

---

## 一、🔴 活跃异常（必修）

### A. `.github/workflows/v8_stock_quote_refresh.yml` L379-380 正则组越界 → IndexError

**证据链**
| 项 | 值 |
|---|---|
| 位置 | main 分支 `v8_stock_quote_refresh.yml` 第 **379-380** 行 |
| 代码 | `pattern = r'(data/STOCK_QUOTE\.js\?v=)([a-f0-9]+)'` ← **只有 2 个捕获组**<br>`re.subn(pattern, lambda m: m.group(1)+content_sha+**m.group(3)**, html)` ← 取第 3 组 |
| 本地复现 | `IndexError: no such group`（已用 managed python 3.13.12 实测） |
| 触发条件 | index.html 当前 `?v` ≠ 本次算出的 sha10 → 进入替换分支即崩 |
| **当前状态** | main 上 index.html `?v=1789021504`（时间戳口径，14:25:04 写入），而 `data/STOCK_QUOTE.js` 实际 sha10 = `9a16bda41c`（14:27:36 提交）→ **二者不等 → 下次必崩** |
| 为何之前没炸 | 14:10 / 14:25 两次 success 时 index.html 的 `?v` 恰好已是 sha10 → 走 `new_html == html` 分支，未进入 lambda |

**一劳永逸修复（1 行）**
```diff
- new_html, n = re.subn(pattern, lambda m: m.group(1) + content_sha + m.group(3), html)
+ new_html, n = re.subn(pattern, lambda m: m.group(1) + content_sha, html)
```
（pattern 只有 2 组，group(2) 就是旧 sha；替换即丢弃旧值，无需再拼接。建议同时把 pattern 放宽为 `(data/STOCK_QUOTE\.js\?v=)([A-Za-z0-9]+)`，兼容未来非 hex 口径。）

**验收**：手动 dispatch 一次，step8 日志出现 `替换了 1 处 STOCK_QUOTE.js?v= → <sha10>` 且 index.html 提交成功，随后校验 `index.html ?v == sha1(data/STOCK_QUOTE.js)[:10]`。

---

### B. 缓存戳 `?v` 口径分裂：sha10 vs 时间戳，两方互顶

**现象**：main 上 index.html 的 `STOCK_QUOTE.js?v=` 由**两个互不知情的写入方**轮番覆盖：

| 写入方 | 口径 | 实证 commit |
|---|---|---|
| `v8_stock_quote_refresh.yml` step8 | 内容 sha1 前 10 位（如 `9a16bda41c`） | `chore(cache): STOCK_QUOTE.js?v=…` |
| 云端生成器「原子提交 ?v → 防覆盖」 | **unix 时间戳**（`1789021504` = 2026-09-10 14:25:04 CST） | `33062c8d45` / `c7bdf39228` / `6aa741ddc9` |

**后果**：谁后写谁赢；`?v` 与数据文件不同步时，GitHub Pages CDN 继续吐旧副本 → **看板行情肉眼可见落后**（当前 STOCK_QUOTE.js 14:27:36 已更新，index.html 停在 14:25 口径）。

**一劳永逸修复**
1. **全站统一为「内容 sha1 前 10 位」**，禁止时间戳。sha10 幂等可判定，能直接比对出失配；时间戳只能"看起来在变"，无法校验真假对齐。
2. 定位生成器侧写时间戳的代码（查 `update_v8.py` / 云端 cn fetch 链里 `?v=` 的赋值，大概率是 `int(time.time())`），改为 `hashlib.sha1(open(f,'rb').read()).hexdigest()[:10]`。
3. 写方收敛：同一次提交内原子写入「data 文件 + index.html ?v」，避免 A 推数据、B 推戳的窗口。

**验收**：连续两次刷新后 `index.html ?v == sha1(data/STOCK_QUOTE.js)[:10]` 恒成立（可加一条 CI 断言，失配即 fail）。

---

## 二、✅ 已自愈，仅备案（无需再动）

| # | 旧根因 | 现状 |
|---|---|---|
| 1 | **GBK emoji 崩溃**：self-hosted Windows runner 上 `print("✅ …")` → `UnicodeEncodeError: 'gbk' codec can't encode '\u2705'`（run `34443405596` step7） | 已修：job 级 `PYTHONIOENCODING: utf-8` + `PYTHONUTF8: 1`（L67-72），覆盖全部 step。实证 run `34444087831`(14:10) / `34445111017`(14:25) 均 success |
| 2 | **step8 `FileNotFoundError: index.html`**：self-hosted 不 checkout，工作区无 index.html（run `34444228482`，head `91ef5b438`） | 已修：改为经 Contents API 取 index.html（L359-361）。注：run92 那次 success 是靠 runner 工作区残留碰运气 |

---

## 三、⏰ 沿用 13:21 交接（未闭环）

`INDEX_HISTORY` 落后 **45.8h**（阈值 30h，main 权威值停在 09-08 盘后）。
根因仍是 13:21 交接的**「多源派发互顶 pending run」型踩踏**（7 个派发源 + `v8-cn-fetch-cloud` 组只保留 1 个 pending + `v8_cloud_watchdog.py:432` 主动 cancel 误杀）。属盘后批次断档，修完踩踏后由 cron 自然补齐，**不建议手工补历史**。

---

## 四、给下次巡检的复用判据

1. **job logs 401 的解法**：自定义 `HTTPRedirectHandler`，跨主机重定向时不转发 `Authorization` → 可正常拿到日志（本轮已验证，见 `tmp/_log_grep.py`）。
2. **判定一律以 main 远端为准**：本地工作区是坚果云回退版本，看本地必误判。
3. **被 cancel 的 run 若 jobs 为空** ⇒ 排队阶段被顶掉，不是跑挂；去查 concurrency 槽位与派发源，别翻日志。
4. **缓存戳是否对齐** = `sha1(data/X.js)[:10]` 与 `index.html ?v=` 比对，只看 mtime 无效。
