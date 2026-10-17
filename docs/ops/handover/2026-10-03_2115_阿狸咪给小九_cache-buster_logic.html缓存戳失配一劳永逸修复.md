# HANDOVER｜阿狸咪的工程师 → 小九｜2026-10-03 21:15｜cache-buster logic.html 缓存戳失配一劳永逸修复（三件套补登）

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）
> 本件为**补登**：该修复 `2dfb2d1e4d` 已于 2026-10-02 推送，当时缺交接件③。现按主人令补齐。

---

## 一句话结论

`logic.html` 的 `?v` 缓存戳与数据内容哈希长期存在「格式回潮 / 两页戳漂移」隐患（曾致旧版页面被浏览器缓存顶住）。本次一劳永逸修复 `logic.html` 152 行戳逻辑 + `update_v8.py` 20 行 + 新增 `pre_deploy_audit.py` **[15/15] logic.html 缓存戳守卫**（防两页戳漂移/旧格式回潮）+ `v8_cache_buster_reconcile.yml` 4 行。根因闭合，防回归已就位。**三件套①审计②四方对齐已复核通过，③交接件现补登。**

---

## 正文

### 1. 改动清单（`2dfb2d1e4d`，2026-10-02）
- 文件（4 个）：
  - `.github/scripts/pre_deploy_audit.py`（+66）：新增 `[15/15] logic.html 缓存戳守卫`，逐文件校验 logic.html 全部带 `?v` data 引用戳 == 数据内容哈希。
  - `.github/workflows/v8_cache_buster_reconcile.yml`（+4）：协调流程加固。
  - `logic.html`（152 行变动）：重写 `?v` 戳生成/替换逻辑，统一中性化内容哈希口径。
  - `update_v8.py`（+20）：写入侧同步新戳口径。
- 性质：一劳永逸修复 + 防回归守卫（非临时补丁）。

### 2. 三件套复核
- **① 审计（门禁）**：`pre_deploy_audit.py` 对当前树（含本修复）**15/15 全绿**（本次 21:10 补跑实证）。其中 `[15/15] logic.html 缓存戳守卫` 即本修复落地的守卫，实证 logic.html 76 个带 `?v` data 引用戳**全部与数据内容哈希一致**——证明本修复有效且未回潮。
- **② 四方对齐（含 logic.html 平行副本）**：本修复核心就是让 `logic.html` 戳与 index.html / 数据层一致。`[4/8] align_logic_ops EXIT 0`（逻辑详解页与真 workflow 对齐）+ `[15/15]` 守卫双重背书，两页戳口径已统一，无分歧。
- **③ 推仓防覆盖**：`2dfb2d1e4d` 已于 2026-10-02 推送（fast-forward，零顶掉），现为补登交接，无二次推送。

### 3. 关联提醒（与小九相关）
- `v8_cache_buster_reconcile.yml` 流程改动后，若日后 logic.html 再出现「线上看到旧版」，优先查 `[15/15]` 守卫是否仍 0 漂移，而非盲目 bump——本修复已从根上消除戳失配类缓存顶版。

---

阿狸咪的工程师 ｜ 2026-10-03 21:15 补登
