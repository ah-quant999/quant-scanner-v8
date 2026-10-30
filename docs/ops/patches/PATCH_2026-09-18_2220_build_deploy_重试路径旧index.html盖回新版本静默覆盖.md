🧩 补丁：v8_build_deploy.yml「重试路径」旧 index.html 盖回新版本（静默覆盖他人前端改动）

- 日期：2026-09-18 22:20（北京时间）
- 提出方：阿狸咪的工程师（家机 `alimi-cn`）
- 目标文件：`.github/workflows/v8_build_deploy.yml`
- 权限说明：🔴 本机 PAT 无 `workflow` scope，任何对 `.github/workflows/` 的 API 写入必 403 ⇒ 本补丁**必须由有 workflow 权限的一方（小九的工程师）应用**。

---

## 一、事故实证（全部可复核）

| 时间(CST) | 提交 | index.html 内 `const cpa = null` | 字节 |
|---|---|---|---|
| 21:24 | `c0c3e98771`（我推送前） | 1（存在） | 1296290 |
| **21:32** | **`cd1ccb3dd0`（阿狸咪清理提交）** | **0（已删）** | 1296058 |
| 21:33 | `851ed39cf3` 缓存戳 bot | 0（未动） | 1296058 |
| **21:42** | **`149d5a2a30` v8 build** | **1（被还原）** | 1296290 |
| 21:55 / 22:01 / 22:02 / 22:05 | cloud-bot / 缓存bot ×3 / v8-deploy | 1 | 1296290→1297015 |

结论：**21:42 的 `v8 build` 把 index.html 的内容整体退回 21:31 之前的状态**，覆盖掉了 21:32 的前端删除。`git push` 是 fast-forward、无冲突、无告警 ⇒ 静默覆盖。

## 二、根因（代码级，两处同源）

`v8_build_deploy.yml` 里两处「备份 → reset → 盖回」：

```bash
# 主路径（约 L226）
if ! git diff --quiet -- index.html; then
  cp index.html /tmp/index.html.manual
  git reset --hard FETCH_HEAD
  cp /tmp/index.html.manual index.html
else
  git reset --hard FETCH_HEAD
fi

# 重试路径（约 L367，push 被拒后）
if ! git diff --quiet -- index.html; then
  cp index.html /tmp/index.html.manual
  git reset --hard FETCH_HEAD
  cp /tmp/index.html.manual index.html
else
  git reset --hard FETCH_HEAD
fi
```

2026-09-16 的修复把条件从「无条件」改成「确有未提交改动时」——**但该条件在 CI 里恒为真**：
本步之前刚跑过 `python update_v8.py`（重写 index.html 的 73+ 个 `?v=`），工作区**必然 dirty** ⇒ 走 then 分支 ⇒
备份的是**旧内容**、reset 拿到的是**最新远端（含他人在 21:32 的改动）**、随后 `cp` 把旧的盖回去 ⇒
下一句 `git commit` 因为 HEAD 已是最新远端，**只有 index.html 一处差异**，push 天然 fast-forward ✅ ⇒ 静默覆盖。

触发条件：**push 首次被拒（并发推送）→ 重试**。21:42 那次正是被 21:33 缓存戳 bot 的提交顶掉后进入重试路径。

## 三、修复（二选一，推荐 A）

### A. 重试路径去掉「盖回」（最小、最正确）

CI 内 index.html 的本地改动 **100% 由脚本生成**（`update_v8.py` 的 `?v` 重写、`guard_v6_memo.py` 的 v6 戳、BUILD 注入），
而这三步在**重试路径里都会紧接着重跑一遍** ⇒ 备份/恢复是纯粹的多余动作且引入覆盖漏洞。
人工前端改动一定是**已提交**的，`reset --hard FETCH_HEAD` 不会丢。

```bash
# 主路径 与 重试路径 统一改为（删除整个 if/else，只留一行）：
git reset --hard FETCH_HEAD
```

### B. 若坚持保留「保护人工未提交改动」意图（归一化后才盖回）

```bash
git reset --hard FETCH_HEAD
# 归一化比对：把可再生 token（?v= 值、BUILD sha、v6 戳）抹平后仍相同 ⇒ 备份没有实质内容，不盖回
python - <<'PY'
import re, pathlib, difflib, sys
bak = pathlib.Path('/tmp/index.html.manual')
if not bak.exists():
    sys.exit(0)
cur = pathlib.Path('index.html')
norm = lambda s: re.sub(r'(\?v=)[0-9a-zA-Z]+', r'\1X',
                re.sub(r'(var BUILD = ")[0-9a-f]{7,40}(")', r'\1X\2', s))
if norm(bak.read_text(encoding='utf-8')) != norm(cur.read_text(encoding='utf-8')):
    cur.write_text(bak.read_text(encoding='utf-8'), encoding='utf-8')
    print('⚠️ 备份含实质差异，已盖回（请核对该差异是否为人工改动）')
else:
    print('✅ 备份仅含可再生 token 差异 → 不盖回（避免覆盖他人改动）')
PY
```

## 四、应用后的验收

1. 打一次「必然进入重试路径」的验证（或手工 `workflow_dispatch` 后并发推一次 data），确认：
   `git log --oneline` 里 build 提交的 `index.html` 差异**只含 `?v=` 与 BUILD 行**，不再出现任何业务代码增删。
2. 复核命令（任一时间点可跑）：

```bash
curl -s -H "Authorization: Bearer $PAT" \
  "https://api.github.com/repos/ah-quant999/quant-scanner-v8/commits?path=index.html&per_page=5"
# 逐个取 blob，比对相邻提交差异集合 ⊆ { ?v= 行, BUILD 行 }
```

---

本补丁由阿狸咪的工程师提出，证据链全部来自 GitHub Git Data API 实测（blob 字节级），未经推测。
