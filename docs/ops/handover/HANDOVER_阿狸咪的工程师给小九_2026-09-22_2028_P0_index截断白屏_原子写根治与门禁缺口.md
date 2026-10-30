# P0 · index.html 被截断致整站白屏 —— 根因已根治，遗留「门禁拦不住线上」缺口

- **发件**：阿狸咪的工程师（家机 `alimi-cn`）
- **收件**：小九的工程师（单位机 `lemoncat-cn`）
- **时间**：2026-09-22 20:28 CST
- **等级**：🔴 P0（线上整站不可用约 9 分钟）
- **主人已亲自反馈**：「主站什么内容都打不开了，导航也按不了，管理员也进不去！！！」

---

## 一、现象

线上 `index.html` 被写成 **366,154 B**（正常 1,347,523 B）。因 `_renderPostReady` 等引导函数整体消失、
文件末尾无 `</body></html>`，**整页 JS 不初始化** ⇒ 导航不可点、分节不渲染、管理员入口打不开。

## 二、时间线（均为 CST，取自 commit 时间与 Pages 构建）

| 时间 | 事件 |
|---|---|
| 20:09:52 | `ac8355e1c` 生成器原子提交，index.html = 1,347,523 B（**最后一次正常**） |
| 20:10:13 | 🔴 `0320100b3`（`github-actions[bot]`，提交信息 `v8 cn fetch: 2026-09-22 20:09`）把 index.html 删掉 **14,220 行** ⇒ **366,154 B** |
| 20:10:40 | `b93852366`（缓存戳对齐）在已截断的版本上继续改 `?v`（同为 366,154 B） |
| 20:10:42 | 🔴 **Pages 构建成功并发布截断版** ⇒ 线上开始白屏 |
| 20:10:58 | `35725666086 ☁️ v8 构建部署` = **failure**（v8 门禁**确实抓到了**，但拦不住，见第四节） |
| 20:19:47 | `319aeb7e1` 紧急恢复 index.html（1,347,523 B，+14,222/−101 行） |
| 20:19:49 | Pages 重新构建成功 ⇒ **线上恢复** |

## 三、根因（已实测取证）

`update_v8.py` → `_rewrite_index_html_cache_busters()`：

```python
html = idx_path.read_text(encoding='utf-8')
...
idx_path.write_text(new_html, encoding='utf-8')   # ← 非原子写
```

`Path.write_text()` 的行为是**先 truncate 再逐块写**。进程在写入中途被杀（OOM / job 抢占/
runner 回收）⇒ **文件停在任意位置**，必留半个文件。

**取证**：截断版恰好 = 完整版**前 5,027 行**（完整 19,148 行），断点在
`window.__STAR_ALT_SOURCES = {` **对象定义正中间**（注释都未写完）⇒ 属「写入被中断」，
**非**逻辑截断，也**非**旧树覆盖（内容与当时 tip 同源，仅差 200 行 `?v`）。

**触发面很宽**：`update_v8.py --only-cache-busters` 被 **3 处**共用
（`v8_cn_fetch_cloud.yml` step `soft_15`、`v8_cache_buster_reconcile.yml`、`v8_build_deploy.yml`），
且当日 20:03–20:10 之间 index.html 被反复重写 —— 每次写都是一个中断窗口。

## 四、为什么门禁没拦住（🔴 结构性缺口，请评估）

- `[10/10] index 核心标记守卫` **确实红了**（截断版 21/34 标记消失，`35725666086` build job = failure）；
- **但 GitHub 内置的 `pages build and deployment` 是独立 workflow，不消费 v8 的 `pre_deploy_audit`**，
  只要 `main` 变了就直接构建发布 ⇒ **v8 门禁只能「喊」，不能「拦」线上**。

⇒ **任何**写坏 index.html 的路径（不限于本次）都会在数秒内上线。这是本次能白屏的结构性原因。

## 五、已做的修复（阿狸咪侧，已上线）

**commit `9037d76d22`**（父 `161b9a58fc`）——`update_v8.py` 原子写 + 落盘自证：

1. 新增 `_atomic_write_index_html()`：同目录 `.tmp` + `flush` + `os.fsync` + **`Path.replace` 原子换入**
   ⇒ 中断**只留 `.tmp`，绝不伤正本**；
2. **落盘后自证**：末尾须含 `</html>`，且行数/长度不得较基线缩水 >5%；不过则**抛异常**
   ⇒ 调用方（各 workflow 的 `bash -e` step，**均位于 `git add index.html` 之前**）直接失败
   ⇒ **半个文件永远上不了 main**；
3. 读写统一 `newline=''` **原样透传行尾**：`main:index.html` 实测为**纯 LF**（1,347,523 B 中 CR=0）；
   而 `write_text` 的 `newline=None` 在 Windows 侧写 CRLF、Linux 侧写 LF ⇒ 跨 OS 翻转会造成**全量假 diff**。

**自证（实测输出）**：
- `py_compile` rc=0；4 处锚点均唯一命中；无裸 `write_text` 残留；
- **场景 A**：真实 index.html 写入后 **1,347,523 B / CR=0 完全守恒**（无行尾翻转）；
- **场景 B**：截断输入 ⇒ 被拦下且**正本完好无损**；
- **场景 C**：缺 `</html>` ⇒ 被拦下；无 `.tmp` 残留；
- 推后**逐字节自证**：远端 = 本地（blob `8b2437f80b`，93,758 B）。

## 六、复核方法（给下一位）

```bash
# 1) index.html 完整性：末尾必须是 </html>，且 12 个分节 id 各 ≥1
git cat-file blob origin/main:index.html | tail -c 40
git cat-file blob origin/main:index.html | grep -c '_renderPostReady'   # 期望 8

# 2) 行尾判据：⚠️ 禁用 `grep -c $'\r'`（$'\r' 会被当空模式匹配所有行 ⇒ 假报有 CR）
python -c "import subprocess;b=subprocess.run(['git','cat-file','blob','origin/main:index.html'],capture_output=True).stdout;print('CR=',b.count(b'\r'),'bytes=',len(b))"

# 3) 任意历史版本是否被截断（一行判据）
git cat-file blob <sha>:index.html | tail -c 20    # 无 </html> 即为截断

# 4) 本次补丁是否在位
git cat-file blob origin/main:update_v8.py | grep -c '_atomic_write_index_html'   # 期望 4
```

## 七、遗留待办（建议挂账，需主人/小九拍板）

1. **🔴 P0-候选：给「上线」加一道不依赖 workflow 权限的校验**
   既然 `pages build and deployment` 不受 v8 门禁约束，建议评估：部署产物是否改由
   `v8_build_deploy` 的 artifact 路径产出（而非直接从 main 取），或引入可在
   `.github/scripts/` 落地的守卫（⚠️ 阿狸咪侧 PAT 无 `workflow` scope ⇒
   `.github/workflows/**` 一律 403，无法自助改 workflow，故此项须小九或主人处理）。
2. **P1：`unlockCoverCard` 未登记进 `docs/ops/index_protected_markers.txt`**
   （该卡 09-21 上线，锚点命中 0）⇒ 未来缓存戳重写可能静默顶掉。
3. **P2：本次白屏 9 分钟内，监控未产生「站点不可用」告警**（`v8_cloud_watchdog` 的
   infra 级判据疑似只判 HTTP 可达性，而截断版仍返回 200）⇒ 建议评估是否增加
   「关键标记在位性」这一探针。**本次未擅自改动监控**，等拍板。

---

*本件为变更通报与挂账建议，非回执。技术细节见 commit message。*
