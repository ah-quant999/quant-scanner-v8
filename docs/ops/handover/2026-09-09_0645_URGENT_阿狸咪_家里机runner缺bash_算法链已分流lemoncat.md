# URGENT · 阿狸咪 · 2026-09-09 06:45 · 家里机 runner 缺 bash 致算法链六连败 · 已分流至 lemoncat-cn

## 一句话
云端算法链 #1613-1618 **六连败**根因实锤：**alimi-cn（你那台机）runner 服务环境的 PATH 里没有 bash/git**，任何 `shell: bash` 的 step 必死。小九已把两条算法链**固定调度到 lemoncat-cn**（label `xiaojiu`），今晚链可正常跑。**请你在家里机根治环境**，修好后按第五节恢复双跑。

## 二、日志实证（#1618，job 102158940218，勿凭猜）
- 失败点：step 4「🗓 解析数据日期」→ `##[error]bash: command not found`
- runner 工作目录：`D:\actions\cn-runner\_work\...`（= 你那台机）
- checkout 退化为 REST API 下载 archive，日志原话：`To create a local Git repository instead, add Git 2.18 or higher to the PATH`
- 结论：不是链的问题，是**你的 runner 服务账户 PATH** 找不到 bash.exe / git.exe（可能被 WSL 的 `C:\Windows\System32\bash.exe` 截胡，或服务 PATH 与桌面用户 PATH 不同）。

## 三、小九已做（你无需重做）
1. **lemoncat-cn 加自定义 label `xiaojiu`**（GitHub API 动态加，runner 未重启，已复核生效：`['self-hosted','Windows','X64','cn','xiaojiu']`）。
2. **两条算法链 yml runs-on 收紧**为 `[self-hosted, cn, xiaojiu]`（v8_algo_cloud.yml L91 / v8_algo_run.yml L128，含根因注释）。
   - 效果：算法链 100% 落 lemoncat-cn（bash/python/akshare 环境齐全）。本机若掉线，job 排队（queued）不会失败，勿恐慌、勿手动重派。

## 四、请阿狸咪在家里机做（环境根治，四步）
1. 安装/确认 **Git for Windows**（需要 `git.exe` 与 `bash.exe`，如 `C:\Program Files\Git\`）。
2. 把 `C:\Program Files\Git\cmd` 与 `C:\Program Files\Git\bin` 加入 **runner 服务可见的系统级 PATH**（注意：runner 以服务运行，服务 PATH ≠ 你桌面会话的 PATH；改**系统环境变量** Path 后必须**重启 runner 服务**才生效）。
3. 重启 alimi-cn runner 服务，确认 online。
4. 验证：任跑一个含 `shell: bash` 的最小 job（或等下一次 cn 抓取分到你），日志应不再出现 `bash: command not found`。

## 五、环境修好后恢复双跑（可选，由小九执行或你告知小九）
- 把两条 yml 的 `, xiaojiu` 从 runs-on 移除即恢复 `[self-hosted, cn]` 双跑随机分配。
- 若 WSL bash 截胡是根因，也可选择卸载/禁用 WSL bash 与 Git bash 二选一，避免再次误配。

## 六、附带说明（今日早班已根治的其余项，你只读即可）
- CRDS_BACKTEST 孤儿已挂链（`v8/backtest_crds.py` 进 ORDER+STAGES["E"]，自校验 ORDER42==STAGE_UNION42 通过，commit `530a51040`）。
- 三个红灯（FACTOR_LAB / BACKTEST_COMPREHENSIVE / CRDS_BACKTEST）今晚 21:00 E 批应全绿（链已能落本机 + factor_lab_gen 心跳/静默预算 3600s 已配）。
- 盘前清空取消 v2 与 12 文件恢复已确认收到，小九**不会**恢复清空逻辑、**不会**补 premarket_cleared 标记。

## 七、主人看板对应关系（今日截图问题闭环）
| 截图问题 | 根因 | 状态 |
|---|---|---|
| 数据健康总览 3 红点（成功13失败0 却红点） | 盘前清空六连清的后遗症 | ✅ 你已根治（纯跳过+恢复数据），开盘后首抓即消 |
| 失败/诊断详情 3 项 fail | 链落 alimi-cn 必死（本文档根因） | ✅ runs-on 已固定 lemoncat-cn，今晚自愈 |
| 回测汇总/因子实验室「昨日 02:49 / 11:27」时间戳 | 链未按日跑 | ✅ 链修通后每日 21:00 E 批自动刷新 |

---
**本报告仅供研究参考，不构成投资建议。**
