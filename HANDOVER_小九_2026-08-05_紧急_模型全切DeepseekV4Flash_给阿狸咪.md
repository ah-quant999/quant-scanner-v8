# 🔴 紧急交接 · 小九 → 阿狸咪 · 2026-08-05（模型全量切换指令）

> **阿狸咪上线必读，先做这件事，再做其他任何事。**
> 来源：主人直接指令（2026-08-05 下午）。

## 一、指令内容（最高优先级）

**把「家里机器」WorkBuddy 里全部自动化任务（automations）的模型统一改为 `deepseek-v4-flash`。**

- 覆盖范围：**全部**自动化任务，无论当前是 hy3 / auto / 其他 / 未设置，一律改成 `deepseek-v4-flash`。
- 目标：家里机器所有定时任务稳定运行（hy3 免费额度有限、每天可能用完，flash 无额度限制、便宜稳定）。
- 分工策略（主人已定）：**本机（小九）全部 = hy3；家里（你）全部 = deepseek-v4-flash。**

## 二、操作方法（任选其一）

### 方式 A：工具逐个改（任务少时用）
逐个任务执行 `automation_update`（mode=update, id=任务ID, modelId="deepseek-v4-flash"）。
全部改完后用下方「验证」确认。

### 方式 B：直接改数据库（任务多时推荐，速度快）
先备份，再批量更新：

```bash
cp ~/.workbuddy/workbuddy.db ~/.workbuddy/workbuddy.db.bak_$(date +%Y%m%d_%H%M%S)
```

```python
import sqlite3
db = sqlite3.connect(r'C:/Users/<你的用户名>/.workbuddy/workbuddy.db')  # 家里机器用户名
c = db.cursor()
c.execute('UPDATE automations SET model_id = "deepseek-v4-flash" WHERE model_id IS NULL OR model_id != "deepseek-v4-flash"')
db.commit()
print(f'已更新 {c.rowcount} 个任务为 deepseek-v4-flash')
```

⚠️ Windows 下 `~` 需替换为实际用户目录；Linux 下直接用 `~/.workbuddy/workbuddy.db`。

### 验证（必须做）
```bash
sqlite3 ~/.workbuddy/workbuddy.db "SELECT COALESCE(model_id,'NULL'), COUNT(*) FROM automations GROUP BY model_id"
```
期望结果：**只剩一行 `deepseek-v4-flash | N`**（N=家里任务总数），无 hy3、无 NULL、无 auto。

## 三、注意事项

1. **别名自动纠错**：若写成 `ds-V4-FLASH`/`DS-V4-FLASH` 等别名，会被 audit_automations.py 的 MODEL_ALIASES 表自动纠错到 `deepseek-v4-flash`——直接写规范名最省事。
2. **quota_guard 不影响**：`audit_automations.py` 的 `quota_guard()` 只处理 hy3/auto 任务（429 连续 2 次切 flash、恢复切回）。全部设成 flash 后它不会乱动，无需担心。
3. **改库前先备份**：`workbuddy.db` 是本地文件，备份用 `cp` 即可，改错可回滚。
4. **只动模型，别动调度**：rrule/时间/状态都不要碰，仅改 model_id 一列。
5. **本机勿动**：这是给家里机器的指令；本机（小九这台）维持 hy3 不变。

## 四、执行完毕后回报
在当天交接文档里附一句验证结果（改了多少个、验证 SQL 输出），方便主人确认双机策略落地。

---
*本交接文件位于 quant-scanner-v8 仓库根目录，随 git push 同步，家里 `git pull` 即可读到。*
