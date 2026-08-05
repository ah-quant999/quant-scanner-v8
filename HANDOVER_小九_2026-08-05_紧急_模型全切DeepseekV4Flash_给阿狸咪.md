# 🔴 紧急交接 · 小九 → 阿狸咪 · 2026-08-05（模型一次性切换指令）

> **阿狸咪上线必读，先做这件事，再做其他任何事。**
> 来源：主人直接指令（2026-08-05 下午，已两次强调）。

## ⚠️ 最重要：这是一次性切换，不是长期/每日策略！

- **只执行今天这一次**。今晚 23:30 双机全部换回 hy3 后，这件事就结束了。
- **不要**把"白天 flash / 夜晚 hy3"做成每天定时任务，主人明确**不要每日定时**。
- 若你看到任何自动化/文档暗示这是长期策略，以本文件为准：**仅 2026-08-05 一次性**。

## 一、指令内容（两步）

### 第 1 步（现在）：把「家里机器」全部自动化模型改为 `deepseek-v4-flash`
- 覆盖范围：**全部**自动化任务，无论当前是 hy3 / auto / 其他 / 未设置，一律改。
- 目的：今天家里所有定时任务稳定运行（hy3 免费额度有限、flash 无额度限制）。

### 第 2 步（今晚 23:30）：把「家里机器」全部自动化模型改回 `hy3`
- **双机同步执行**：小九本机已有一次性任务（23:30 自动切回 hy3），**你也需要在今晚 23:30（或明早你上线时）把自己机器全部任务切回 hy3**。
- 到 23:30 后，双机全部恢复 hy3，本次切换彻底结束。

## 二、操作方法（两步共用同一套，只是把模型名换掉）

### 方式 A：工具逐个改
逐个任务执行 `automation_update`（mode=update, id=任务ID, modelId="deepseek-v4-flash" 或 "hy3"）。

### 方式 B：直接改数据库（推荐，速度快）
```bash
cp ~/.workbuddy/workbuddy.db ~/.workbuddy/workbuddy.db.bak_$(date +%Y%m%d_%H%M%S)
```
```python
import sqlite3
db = sqlite3.connect(r'C:/Users/<你的用户名>/.workbuddy/workbuddy.db')  # 家里机器用户名
c = db.cursor()
# 第 1 步用: model_id = "deepseek-v4-flash"；第 2 步用: model_id = "hy3"
c.execute('UPDATE automations SET model_id = "deepseek-v4-flash" WHERE model_id IS NULL OR model_id != "deepseek-v4-flash"')
db.commit()
print(f'已更新 {c.rowcount} 个任务')
```
⚠️ Windows 下 `~` 需替换为实际用户目录；Linux 下直接用 `~/.workbuddy/workbuddy.db`。

### 验证（两步都要做）
```bash
sqlite3 ~/.workbuddy/workbuddy.db "SELECT COALESCE(model_id,'NULL'), COUNT(*) FROM automations GROUP BY model_id"
```
- 第 1 步后：只剩 `deepseek-v4-flash | N`
- 第 2 步后：只剩 `hy3 | N`

## 三、注意事项

1. **别名自动纠错**：`ds-V4-FLASH`/`DS-V4-FLASH` 会被 MODEL_ALIASES 自动纠错到 `deepseek-v4-flash`——直接写规范名最省事。
2. **quota_guard 不影响**：只处理 hy3/auto 任务，不干扰手动设的模型。
3. **改库前先备份**，改错可回滚。
4. **只动模型，别动调度**：rrule/时间/状态都不要碰，仅改 model_id。
5. **不要建任何"每日切换"的自动化**——主人明确禁止。

## 四、执行完毕后回报
在当天交接文档里附一句验证结果（第 1 步/第 2 步各改了多少个、验证 SQL 输出），方便主人确认双机一次性切换落地。

---
*本交接文件位于 quant-scanner-v8 仓库根目录，随 git push 同步，家里 `git pull` 即可读到。*
