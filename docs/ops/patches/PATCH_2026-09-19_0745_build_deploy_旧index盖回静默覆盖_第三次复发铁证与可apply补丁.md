# 🧩 补丁（第三次复发 · 附可 apply 文件）：`v8_build_deploy.yml` 陈旧备份把新 `index.html` 盖回

- 日期：2026-09-19 07:45（北京时间）
- 提出方：阿狸咪的工程师（家机 `alimi-cn`）
- 目标文件：`.github/workflows/v8_build_deploy.yml`
- 可 apply 补丁：`docs/ops/patches/v8_build_deploy_index_clobber_fix_20260919.patch`
- 前序同题补丁：`docs/ops/patches/PATCH_2026-09-18_2220_build_deploy_重试路径旧index.html盖回新版本静默覆盖.md`（**尚未应用**）
- 权限：🔴 本机 PAT 无 `workflow` scope ⇒ 对 `.github/workflows/` 的 API 写入必 403 ⇒ **必须由有 workflow 权限的一方（小九的工程师）应用**

---

## 一、第三次复发实证（2026-09-19）

| 时间(CST) | 提交 | `index.html` blob | 字节 | 说明 |
|---|---|---|---|---|
| 07:20:46 | `8164d8f623` | `363aec5152443119` | 1349925 | **阿狸咪的改动**（逆势龙头页判据条 + 回测块 + 汇总表分组） |
| **07:22:10** | **`df63f016d1`（v8 build）** | `75dc33af686b5679` | **1333265** | 🔴 **被盖回旧版**（我的块 `stcrdsGateBox`/`stcrdsBtBox`/`_btMainRow`… 全为 0 次） |
| 07:24:42 | `2acd970321`（v8 build，另一趟） | `b991178daa1b26a8` | 1349925 | ✅ 由 checkout=我的提交的 run 恢复 ⇒ 现在线正常 |

`df63f016d1` 的 parent **就是** `8164d8f623`（fast-forward，**无冲突、无告警**）。

---

## 二、判据铁证（本次新证据，比前两次更硬）

`df63f016d1` 的 `index.html` 内：

```
var BUILD = "8164d8f62"        ← 等于「被覆盖那笔提交」的 sha
```

`BUILD` 由构建步用 `git rev-parse --short HEAD` 注入。它等于**我的提交** ⇒ 注入那一刻 `HEAD` **已经是我的提交**；
但**文件正文却是旧版** ⇒ 只可能是 `git reset --hard FETCH_HEAD` **之后**，文件被一个**更旧的备份**覆盖。

该 run（id `35405186551`，head `162a42d5`）日志（全文中 `HEAD is now at` **仅出现 1 次**）：

```
23:21:40.146  From https://github.com/ah-quant999/quant-scanner-v8
23:21:40.146   * branch                main       -> FETCH_HEAD
23:21:40.619  HEAD is now at 8164d8f62 feat(crds): 逆势龙头页加危机雷达判据条...
23:21:40.726  [ws-guard] ⚠️ E:\workspace\stock-scanner 不是 git 仓库 → 跳过（不阻断）
23:21:40.726  🔍 全量构建模式
23:21:54.996  ✅ index.html cache-busting 参数已更新
23:22:09.619  ✅ index.html cache-busting 参数已更新
23:22:09.920  ✅ index.html 保留「逻辑详解」入口 → logic.html（v6备忘录 可达）
23:22:10.097  ✅ index.html cache-busting 参数已更新
23:22:10.xxx  ✅ 已注入构建版本戳 8164d8f62
23:22:11.508  ✅ 已部署 main（第 1 次尝试，GitHub Pages 自动重建）
```

⇒ `reset` 到位（HEAD 已是新提交）**且只做了一次**；随后 index.html 被改回旧版。

---

## 三、根因（对 09-18 补丁件的修正：dirty 来源不止 `update_v8.py`）

`v8_build_deploy.yml` 两处（主路径约 L288、重试路径约 L429）：

```bash
if ! git diff --quiet -- index.html; then
  cp index.html /tmp/index.html.manual      # ← 备份的是「checkout 时刻」的内容
  git reset --hard FETCH_HEAD               # ← 拿到的是「最新远端」
  cp /tmp/index.html.manual index.html      # ← 把旧的盖回新的
else
  git reset --hard FETCH_HEAD
fi
```

**该 `if` 在 CI 里必然为真**，且本次日志给出了 dirty 的**完整来源链**：

| 步骤 | 动作 | 是否改 `index.html` | 日志证据 |
|---|---|---|---|
| 步骤 8 | `python guard_v6_memo.py` | ✅ | `✅ index.html 保留「逻辑详解」入口 → logic.html` |
| 步骤 9 | 选择性构建 + `update_v8.py` 缓存戳重写 | ✅ | `✅ index.html cache-busting 参数已更新` |
| 步骤 13 | `python update_v8.py`（全量，含 `_rewrite_index_html_cache_busters`） | ✅ | 同上（多次） |
| 步骤 13 | `git fetch` → `git reset --hard FETCH_HEAD` | — | `HEAD is now at 8164d8f62` |

⇒ 到达检查点时工作区**必然 dirty** ⇒ 走 then 分支 ⇒ **备份 = 陈旧 checkout 的 index.html** ⇒ reset 后又盖回 ⇒ 覆盖。

**触发窗口**：本 run 自触发（`github.sha`）到执行 `git fetch` 之间，远端若有新 push（当前 `?v` 轮换 bot 约每 2 分钟一次）⇒ `FETCH_HEAD` 前进 ⇒ 覆盖发生。

**与前两次的关系**：2026-09-16 的「加条件」修改把触发面从「无条件」缩到「确有未提交改动」，但**未消除危害**——危害的本质不是「有没有未提交改动」，而是**备份可能比 `FETCH_HEAD` 旧**。

---

## 四、修复（方案 A，已生成可 apply 补丁）

两处 `if/else` 统一替换为单行：

```bash
# 🔴🔴 2026-09-19 阿狸咪的工程师（第三次复发后根因修复）：
#   原「备份 → reset → 盖回」意图是保护**人工未提交**的 index.html 改动。
#   但该前提在 CI 里不成立，且会造成静默覆盖（详见注释全文）。
#   ⇒ 删除备份/盖回。CI 里人工前端改动一定是**已提交**的，reset 不会丢；
#     而脚本生成的改动（?v / v6 戳 / BUILD）在 reset 之后都会重跑。
git reset --hard FETCH_HEAD
```

**应用步骤**（补丁已在隔离目录 `patch -p1 --dry-run` + 实跑验证可干净应用）：

```bash
cd <repo root>
git apply --check docs/ops/patches/v8_build_deploy_index_clobber_fix_20260919.patch
git apply        docs/ops/patches/v8_build_deploy_index_clobber_fix_20260919.patch
python - <<'PY'
import io, pathlib
s = pathlib.Path('.github/workflows/v8_build_deploy.yml').read_text(encoding='utf-8')
assert 'index.html.manual' not in s, '❌ 备份/盖回未删净'
assert s.count('git reset --hard FETCH_HEAD') >= 5, '❌ reset 行数异常'
print('✅ 补丁已生效：备份/盖回 0 处，reset 到位')
PY
```

**改动量**：`+36 / −14` 行（两处 hunk：`@@ -285,13 +285,24 @@`、`@@ -426,13 +437,24 @@`）

### 备选方案 B（若坚持保留「保护未提交改动」意图）

保留备份，但**归一化后再决定是否盖回**：「把可再生 token（`?v=` 值、`BUILD` sha、v6 戳）抹平后，若备份与 `FETCH_HEAD` 版本仍相同 ⇒ 不盖回」。实现见 09-18 同题补丁件 §三-B。**推荐 A（更小、更不易再错）。**

---

## 五、为什么必须尽快修（风险量级）

当前 `main` 上有 ≥3 个写入者（`?v` 轮换 bot、`v8 cn fetch`、v8 build），**每 2 分钟级**推送；
而每次 `v8 build` 都有这一段窗口 ⇒ **任何人（两次都是我）对 `index.html` 的改动都可能在下一次 build 被静默抹掉，且不报警**。
2026-09-18 21:42（`149d5a2a30`）、2026-09-19 07:22（`df63f016d1`）已各发生一次，**本次是第三次**。

---

## 六、复核用命令（任何人可复现）

```bash
# 1) 看某次 build 提交的 index.html 是否被盖回
curl -s -H "Authorization: Bearer $PAT" \
  https://api.github.com/repos/ah-quant999/quant-scanner-v8/commits/df63f016d1 \
  | python -c "import json,sys; [print(f['filename'], f['additions'], f['deletions']) for f in json.load(sys.stdin)['files']]"

# 2) 取该提交的 index.html，验证 BUILD 戳与正文是否自相矛盾
#    BUILD=8164d8f62（父提交的 sha）但正文无 stcrdsGateBox ⇒ 已被陈旧备份盖回
```

> 署名：阿狸咪的工程师
