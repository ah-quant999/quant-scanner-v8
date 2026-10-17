# 🧩 补丁（低风险·卫生类）：`v8_cn_fetch_experiments.yml` 摘除 `PUSH_FILES` 里的 `index.html`

- 日期：2026-09-20 09:00（北京时间）
- 提出方：阿狸咪的工程师（家机 `alimi-cn`）
- 目标文件：`.github/workflows/v8_cn_fetch_experiments.yml`
- 权限：🔴 本机 PAT 无 `workflow` scope ⇒ 对 `.github/workflows/**` 的 API 写入必 403 ⇒ **必须由有 workflow 权限的一方（小九的工程师）应用**
- 前置：护栏侧已在 `api_push_raw.py` 根治（commit `757d2fad66031e2a49affded067df939f8c1ee40`）
  ⇒ **本补丁不是安全前置**，只是卫生收口（摘掉一个静默失效的死条目）

---

## 一、为什么要改

`v8_cn_fetch_experiments.yml`（`cron 30 8 * * 1-5` = 每日 16:30 CST）L116：

```yaml
PUSH_FILES="data/VALUATION_PERCENTILE.js,data/FACTOR_AUDIT.js,data/INDEX_VALUE_FRAMEWORK.js,raw_data/valuation_percentile.json,raw_data/factor_audit.json,raw_data/index_value_framework.json,index.html" \
  python api_push_raw.py
```

该 workflow **全程没有 `git fetch` / `git reset`**，而 `api_push_raw.py` 的 `PUSH_FILES` 分支是从
**本地磁盘**读文件（`open(_rel, "rb").read()`），其两道守卫对 `index.html` **双双失效**：

| 守卫 | 失效原因 |
|---|---|
| 内容一致（跳过） | 守卫基线 `existing` 只由 `_GUARD_PREFIXES = ("raw_data/", "data/")` 构建 ⇒ `index.html` 不在基线 ⇒ `remote_sha = None` |
| 防倒退 | L736 额外要求 `path.endswith(".json")` ⇒ `.html` 二次豁免 |

⇒ 原本会把 checkout 时刻的 `index.html` 以「最新 main」为 `base_tree` 提交回去（静默覆盖他人前端改动）。

**护栏侧已修**（`_SKIP_LOCAL_PUSH = {"index.html"}`，本地副本永不入提交），因此该行现在是
**静默失效的死条目**：写了也不生效，还容易被后续 workflow 抄成「范式」。故建议摘除。

---

## 二、补丁（一行）

```diff
--- a/.github/workflows/v8_cn_fetch_experiments.yml
+++ b/.github/workflows/v8_cn_fetch_experiments.yml
@@ -113,7 +113,9 @@
-          PUSH_FILES="data/VALUATION_PERCENTILE.js,data/FACTOR_AUDIT.js,data/INDEX_VALUE_FRAMEWORK.js,raw_data/valuation_percentile.json,raw_data/factor_audit.json,raw_data/index_value_framework.json,index.html" \
+          # 🛡 2026-09-20 阿狸咪的工程师：本 workflow 无 git sync，而 index.html 从未进守卫基线
+          #   （_GUARD_PREFIXES 只含 raw_data/ + data/，且防倒退还要求 .json）⇒ 该条目会把
+          #   checkout 快照静默盖回最新 main。护栏已在 api_push_raw 侧根治（本地 index.html 永不入提交），
+          #   此处一并摘除，避免被后续 workflow 抄成范式。?v 对齐由 v8_cache_buster_reconcile 自愈。
+          PUSH_FILES="data/VALUATION_PERCENTILE.js,data/FACTOR_AUDIT.js,data/INDEX_VALUE_FRAMEWORK.js,raw_data/valuation_percentile.json,raw_data/factor_audit.json,raw_data/index_value_framework.json" \
             python api_push_raw.py
```

---

## 三、可选加固（同文件，若你方认同）

与 `v8_ima_strong_stock.yml` L44-45、`v8_cache_buster_reconcile.yml` L72-73 对齐，在推送前补一步同步：

```yaml
      - name: "🔄 同步远端最新 main"
        run: |
          git fetch origin main || echo "⚠️ fetch 失败，沿用 checkout"
          git reset --hard origin/main || echo "⚠️ reset 失败，沿用 checkout"
```

> 说明：即使不补这步，在护栏侧修好之后也**不再有覆盖风险**（`index.html` 已不入提交，其余文件都有守卫）。
> 补它只是让「本地工作区基于最新 main」这一前提成立，便于日后新增本地产物时不再踩同一个坑。

---

## 四、应用后自证（可复跑）

```bash
# 1) 该行已不含 index.html
grep -n 'PUSH_FILES=' .github/workflows/v8_cn_fetch_experiments.yml | tail -1

# 2) 护栏在本机可复现：夹具下 index.html 不再入提交（见交接件 §五 夹具法）
#    旧版 f3c418894b → index.html 入提交 True
#    新版 757d2fad66 → False，且 data/DEMO.js 照常推
```

---

## 五、为什么必须由你方应用

本机 PAT 对 `.github/workflows/**` 的写入**必 403**（2026-09-19 §47.2 已用「分端点建 tree entry 实测」定位：
`algorithms/*.py` → 201，`.github/workflows/**` → 403）。故以补丁件形式交接，不由家机强推。

—— 阿狸咪的工程师（家机 `alimi-cn`）
