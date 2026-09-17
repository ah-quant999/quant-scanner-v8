# 补丁存档 · ima 同步链「产物形状断言」CI 步

**日期**：2026-09-18 08:50（北京时间）
**作者**：阿狸咪的工程师
**状态**：⚠️ **待应用**（我方 PAT 无 `workflow` scope，改 `.github/workflows/` 会 403）
**目标文件**：`.github/workflows/v8_ima_strong_stock.yml`
**优先级**：**P2 / 可选**（生产者自检已覆盖同等效果，见下）

---

## 一、为什么我没直接改

GitHub PAT 若无 `workflow` scope，通过任何 API（含 Git Data API 的
`POST /git/trees`）改动 `.github/workflows/**` 都会返回：

```
403 Resource not accessible by personal access token
```

⇒ 故本补丁**只存不改**，由有权限的一方（小九 / 主人 / 带 workflow scope 的 PAT）应用。

---

## 二、为什么它是「可选」而不是「必须」

**同等效果已由生产者自检落地**：`fetch_ima_strong_stock.py` 的 `main()` 在写出产物前
已内联断言（五字段存在 / `no_first_selected == 0` / `field_missing_counts` 为空），
**不通过则 `raise SystemExit(1)`** ⇒ CI 里该步直接失败、job 变红。

这样做的两个理由：
1. **绕开权限**（PAT 无 workflow scope）；
2. **更内聚**：谁产出谁负责 —— 连人工在本机跑一次也受同样保护。

⇒ 本 CI 步的价值是**显式化**（在 Actions 日志里独立成一步、错误信息带 `::error::` 注解，
便于一眼看出「是形状问题」而不是「抓取失败」）。**不做也不影响防护生效**。

---

## 三、补丁内容（`.diff`，可直接 `git apply`）

```diff
--- a/.github/workflows/v8_ima_strong_stock.yml
+++ b/.github/workflows/v8_ima_strong_stock.yml
@@ -46,6 +46,14 @@ jobs:
       - name: "🕸️ 抓取 ima 强势股日报"
         run: python fetch_ima_strong_stock.py
 
+      # 🔴 2026-09-18 阿狸咪的工程师 新增：产物形状断言（杜绝「旧脚本假成功」）
+      #   真因实证：新版脚本 09-17 21:53 上线，而本 workflow cron 是 CST 15:45 ⇒
+      #   当天早已用旧脚本跑完 ⇒ 五字段（data_date/source_stale/...）至今一次未写出，
+      #   前端红胶囊判据恒假、回测样本被砍到 40/112，**而整条链全绿、无人知晓**。
+      #   故在此硬断言：形状不对即 fail，并指名是「旧脚本」还是「解析串位复发」。
+      - name: "🔎 产物形状断言（五字段 + 解析健康度）"
+        run: python verify_ima_sync.py
+
       - name: "🔁 重写 index.html 的 ?v 缓存戳（与刚生成的 data 文件对齐）"
         run: python update_v8.py --only-cache-busters
 
```

**依赖**：`verify_ima_sync.py`（本次已随同推送，根目录，4951 B）。
**cron 不变**：仍 `45 7 * * 1-5`（北京 15:45），故**时窗矩阵无变化**。

---

## 四、应用方式（两种任选）

```bash
# 方式 A：直接 apply 本文件内嵌的 diff
git apply docs/ops/patches/2026-09-18_0850_...diff   # 需先把上面的 diff 落到文件

# 方式 B：手工插入（3 行有效内容，位置：抓取步之后、重写 ?v 步之前）
#   - name: "🔎 产物形状断言（五字段 + 解析健康度）"
#     run: python verify_ima_sync.py
```

应用后建议自证：`python verify_ima_sync.py` 应 `EXIT 0`（在 09-18 15:45 cron 跑出
新版产物之后；在那之前产物仍是旧形状，脚本会正确地红）。

---

## 五、相关背景（一句话）

本次同时根治了 `fetch_ima_strong_stock.py` 的**空单元格折叠**缺陷 ——
它让 112 只里 **72 只丢了「首次入选日」**（有效仅 40/112），回测侧静默丢弃 64% 样本、
结果系统性偏乐观。自证：修复前六字段缺失数 `{72,72,72,72,70,70}` 与线上 `parse_health`
**逐项完全一致**，修复后归 0、有效日 **112/112**。详见同日交接件。

*本补丁仅供研究参考，不构成个人投资建议。*
