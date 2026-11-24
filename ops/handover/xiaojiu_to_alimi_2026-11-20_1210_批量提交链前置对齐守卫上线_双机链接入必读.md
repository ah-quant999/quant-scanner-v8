# 交接：批量提交链前置对齐守卫上线（小九 → 阿狸咪）2026-11-20 12:10

## 一句话
主人令「加！不要一直被覆盖！」——批量提交链覆盖事故（今晨 01:51 的 8760 文件/189 万行怪物提交把
stock_names/resonance_track 盖回 11-11）的治本机件已上线：**`algorithms/safe_batch_commit.py`**（commit `8b1337ff62`）。

## 你（阿狸咪侧）必须做的三件事（今日夜班内完成）
1. **你的批量提交链全部改走守卫**：凡是「持久工作区整批 add+commit+push」的本地自动化
   （交接档链/心跳链/工作区同步链），提交动作一律替换为：
   ```bash
   python algorithms/safe_batch_commit.py --msg "..."          # 整树
   python algorithms/safe_batch_commit.py --msg "..." --paths data/ raw_data/   # 指定路径
   ```
   禁再裸 `git add -A && git commit && git push`。
2. **你的本地铁律各自增补**（协议⑩：本文件各机本地、不跨机传播，须双机各自写入）：
   - 批量提交链一律经 `safe_batch_commit.py` 提交；提交前强制 fetch+rebase 对齐，
     对齐失败 exit 1 绝不带旧树提交；data/raw_data 文件时间戳本地更旧 ⇒ 自动否决取远端。
3. **守卫行为须知**（不要误判为故障）：
   - 输出 `⚠️ 本地落后 origin/main N 笔 → 强制 pull --rebase --autostash 对齐` ＝ 正常自愈；
   - 输出 `🛑 陈旧否决：<file> (本地X < 远端Y)` ＝ 守卫把你的旧内容丢弃、取了远端新版（正确行为，
     2026-11-20 parity 拦截的同类场景，以前这种会把线上新数据盖回旧版）；
   - `❌ 对齐失败（绝不带旧树提交）` ＝ 真冲突，人工解决后重跑，**禁止绕过守卫直接 commit**。

## 三道闸（机制摘要，详见脚本头注释）
| 闸 | 行为 |
|---|---|
| ① 对齐 | fetch + 落后即 `pull --rebase --autostash`；失败 exit 1——消灭「落后基线建树重放旧内容」（事故机制本体） |
| ② 否决 | data/ raw_data/ 差异文件比对顶层权威时间戳（update_time > generated > data_date > generated_at），本地旧 ⇒ checkout 远端版 |
| ③ 重试 | push 被拒 fetch+rebase 重试 3 次（与 algo_intraday_lite 同款） |

## 已验证（本班实测）
- 临时克隆端到端演练：落后检出+rebase ✓；真冲突 fail-closed ✓；陈旧 data 文件否决 ✓；
  porcelain 行首空格路径错位 bug 已修（git() 助手 strip() 吃行首空格，status 改走原始输出）。
- ubuntu-latest 新 checkout 链（backup/cleanup 等 17 条）结构性无此病（每次全新 checkout 必对齐），豁免。

## 边界（不碰什么）
- 本守卫只管「提交前对齐+否决」，不改任何链的调度/触发/抓取逻辑。
- Contents API 单文件净室推送（v8_push_files.py）不变，守卫是批量链的补充而非替代。
