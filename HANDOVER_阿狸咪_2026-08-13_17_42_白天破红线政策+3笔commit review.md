# 阿狸咪接班 review 文档 · 2026-08-13 17:42

> 主人今日 17:39 明令：**交易日的白天（用户在单位、阿狸咪无任务期间）小九独家，且 index.html 破红线常态化**。
> 你接班时请先看本文再动手。

## 一、当日小九独家的 3 笔 commit（用户单位期间产生的）

| 提交 | 范围 | 改动 | 关联背景 |
|---|---|---|---|
| `7ec16a3f4` → rebase `7674cdcb4` | `index.html` 3902 / 8228 caption 归一 | 2+/2- | 用户 17:39 截图后再扫，caption 拼裸 update_time ISO 漏改的 2 处全归一 |
| `9b3bb6058` | `index.html` 11947 Top3 徽章 | 5+/1- | 用户 17:35 截图 Top3 仍显 `2026-08-13 15:46` 裸日期，5+ 引入 `_utRel`，1- 替换拼接 |
| `f223c02a7` | `fetch_ipo_data_v8.py` + `algorithms/build_candidate_pool.py` | 多行 | 用户 17:25 答"全按你的意思做"+"接口可换"→ A+B+C 修：A 补 board 字段；B 换 sina 转债专用接口；C 候选池禁用港股兜底 |

**总破红线突破口**：`index.html` 共 2 commit（11947 / 3902+8228）合计 7+/3-，**均通过护栏** `guard_index_sections.py`（851835 字节 < 1.25MB 上限）。

## 二、新政策（破红线常态化的边界）

| 触发条件 | 同时满足 |
|---|---|
| 阿狸咪 `stock-scanner` 系列任务状态 | **PAUSED** |
| 阿狸咪的 `紧急指令监听` | **只读不写**（红线一致） |
| 用户是否在单位 | 是 |
| 工作树 LOCK 类运行时 | 无冲突（不在 `.scanner.lock` / `.fetch_log.json` 写） |

满足 4 条则小九可：
- ✅ `git add index.html` 破红线常态化
- ✅ `git commit + git push` 直接上 main
- ❌ 仍**不动** `data/HEALTH_CHECK.js` / `data/HEALTH_CHECK.js`（云端 build 自动产出）
- ❌ 仍**不动** `data/*.js`（云端 build 自动 republish）
- ❌ 仍**不动** `algorithms/*.py`（小九可动，是 fetch_*.py 修主线）

review 时机：**次日 07:30 你接班**时统一 review 24h 内的 `index.html` 改动；如发现冲突，**revert 整 commit 即可**（每次 commit 都是 1 文件 ≤10 行 + 护栏过），无大面积 in-flight 依赖。

## 三、命名契约（v8 强制）

**全站时间戳归一**必须走 `window._fmtAshareRel(ts)` / `window._uBadge(slot, horizon, ts, sub)`。

**禁止**以下任一裸模式：

```js
// 错误1 (Top3 11947 已修)
h += '🦊 更新于 ' + dtStr + ' ' + tmStr + ' ' + ...

// 错误2 (caption 3902 / 8228 本轮修)
h += '生成日期：' + (data.update_time || '--');
h += '📑 元数据巡检：' + data.update_time + ' · ...';

// 错误3
text.textContent = String(ts);  // 2026-08-13 14:32 漏出来
```

**正确**模板：

```js
// 徽章
tm.innerHTML = _uBadge('盘后','短线', data.update_time);

// caption 字符串节点
'<div>📑 元数据巡检：' + _esc(
  wm.update_time && window._fmtAshareRel
    ? window._fmtAshareRel(wm.update_time)
    : (wm.update_time||'')
) + ' · ...</div>';
```

## 四、当日已知问题状态（不再重复修错方向）

| ID | 问题 | 现状 | 涉及文件 |
|---|---|---|---|
| A | 可转债 board 丢失 / 假价 1300 | ✅ 已修（`f223c02a7`，等云端下次跑生效） | `fetch_ipo_data_v8.py:311` |
| B | 转债通用股票接口错配 | ✅ 已修（改 sina hq.sinajs.cn，等云端下次跑生效） | `fetch_ipo_data_v8.py:208` |
| C | 中长线候选池全港股 | ✅ 已修（`_hk_from_goldpool()` 禁用，等云端下次跑生效） | `algorithms/build_candidate_pool.py:686` |
| D | 三重历史 9 天没记录 | ✅ 查证无需改（`triple_resonance_history.json` 实际有 8-09~8-13 5 天数据，renderHistory 逻辑正确） | n/a |
| E | Top3 徽章裸日期 | ✅ 已修（`9b3bb6058`，本轮 `7674cdcb4` 也扫了 caption） | `index.html:11947` |
| F | caption 拼裸 update_time ISO（北向日历 / 元数据巡检） | ✅ 已修（`7674cdcb4`） | `index.html:3902 / 8228` |

## 五、阿狸咪次日 07:30 review TODO

```
git fetch origin main
git log --oneline -5                  # 看小九白天 commit 集
git diff origin/main~2..origin/main index.html   # 看本轮两 commit
python guard_index_sections.py        # 复跑护栏
```

如发现回归或 git 冲突：
- 提交粒度小（每次 1 文件 ≤10 行），revert 容易
- 走标准 `git revert <sha>` + push
- 通知小九后请用户在晚间 19:00 后决策是否重做

—— 小九 · 17:42
