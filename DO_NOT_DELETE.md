# 九宝量化 v8.0 - 禁止删除清单

**最后更新**: 2026-08-01 22:42
**维护人**: HH + AI助手
**用途**: 防止误删核心资产，每次项目瘦身/清理前必须核对此清单
**继承自**: v6 DO_NOT_DELETE.md（已验证 v6 2026-07-25 版本）

---

## 🔴 核心页面

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `index.html` | 主站单页面（全站 UI + 数据注入 + 逻辑详解） | 唯一入口，432KB，全站核心 |
| `calendar.html` | 共振日历月历视图 | index.html 内链跳转目标 |
| `v6_memo.html` | v6 遗留参考页（运维面板引用） | 迁移过渡期保留 |

## 🔴 核心数据文件 (data/)

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `data/*.js` (全部 48 个) | 前端数据注入层（window.X = {...}） | 全部由 update_v8.py 从 raw_data 构建，index.html 动态引用 |
| `data/STOCK_LIST.js` | 5202 只股票代码+名称+拼音首字母 | 个股查询唯一数据源，含 py 字段（_gen_pinyin.py 生成） |
| `data/LHB_HISTORY.js` | 龙虎榜历史数据（最大文件 1.3MB） | 共振日历数据源 |

**注意**: `data/` 下所有 `.js` 文件都是前端运行时依赖，**禁止批量删除**。`data/freshness_status.json` 由体检 workflow 自动生成。

---

## 🔴 核心原始数据 (raw_data/)

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `raw_data/*.json` (全部 45 个) | 数据抓取原始 JSON | data/*.js 的上游源，update_v8.py 构建输入 |

**注意**: `raw_data/` 由 cn runner 的 cloud_fetch_v8.py / algorithms/run_algorithms.py 产出，经 api_push_raw.py 推送。云端 weekly_cleanup 会清理 orphan，但不会删有映射的文件。

---

## 🟠 核心脚本 (根目录 *.py)

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `cloud_fetch_v8.py` | 中国数据抓取总入口（akshare/东财） | v8_cn_fetch.yml 唯一抓取入口 |
| `api_push_raw.py` | raw_data → GitHub API 推送 | 所有 cn runner 工作流的推送通道 |
| `update_v8.py` | raw_data → data/*.js 选择性构建 | v8_build_deploy.yml 唯一构建入口 |
| `deploy_v8.py` | 本地 SSH 强制部署脚本 | 本机部署入口（git push main → Pages） |
| `guard_v8_freshness.py` | 46 模块新鲜度守卫 | v8_algo / cloud_weekly_cleanup 调用 |
| `guard_v8.py` | 站点健康检查 | 手动诊断工具 |
| `sync_v6_to_v8.py` | v6→v8 数据同步桥（应急） | v8_sync_v6_data.yml 调用 |
| `backfill_lhb_history.py` | LHB 历史回填生成器 | post_close 时段自动跑 |
| `fetch_ipo_data_v8.py` | IPO/打新数据抓取 | premarket 时段调用 |
| `fetch_limit_up_heatmap_v8.py` | 涨停热力矩阵抓取 | intraday 时段调用 |
| `_gen_pinyin.py` | STOCK_LIST.js 拼音首字母生成器 | 重生成 STOCK_LIST 时必须重跑补 py 字段 |
| `split_inline_data.py` | index.html 内联数据拆分工具 | 维护工具 |

**注意**: 根目录下所有 `*.py` 脚本都是核心管线组件，**禁止批量删除**。

---

## 🟠 算法脚本 (algorithms/)

| 目录/文件 | 内容描述 | 禁止删除原因 |
|-----------|---------|------------|
| `algorithms/run_algorithms.py` | 盘后算法链总控 | v8_algo_run.yml 唯一入口 |
| `algorithms/*.py` (全部 22 个) | 选股/回测/龙虎榜/波动率等算法 | 算法链依赖，缺失则对应卡片冻结 |
| `algorithms/stage_to_raw.py` | 算法输出 → raw_data 格式转换 | run_algorithms.py 调用 |

**注意**: `algorithms/data/` 和 `algorithms/out/` 已在 .gitignore 中，可随时重建。

---

## 🟢 GitHub Actions 工作流 (.github/workflows/)

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `v8_cn_fetch.yml` | 中国数据抓取（cn runner，7个 cron + dispatch） | **唯一数据源工作流**，丢失则全站不更新 |
| `v8_algo_run.yml` | 盘后算法链（cn runner，18:30） | **唯一算法工作流** |
| `v8_build_deploy.yml` | 构建+部署（ubuntu，push 触发） | **唯一部署工作流** |
| `v8_algo.yml` | 每日数据体检（ubuntu，09:00/17:00） | 新鲜度监控 |
| `v8_safety_net.yml` | Safety Net 兜底监控（ubuntu，工作日每30min） | **P0 保险**：cn 断线自动补跑 |
| `v8_self_heal.yml` | 云端自愈器（ubuntu，周六14:00） | **P1 自愈**：周末检测陈旧模块并补跑 |
| `cloud_weekly_cleanup.yml` | 每周清理（ubuntu，周六21:00） | orphan 清理 + 新鲜度体检 |
| `v8_cleanup.yml` | 周日清理（ubuntu，23:00） | 缓存/日志修剪 |
| `v8_sync_v6_data.yml` | v6→v8 应急同步（仅 dispatch） | 应急工具，无定时 |

**注意**: **9 个 yml 缺一不可**。丢失任何一个都会导致对应能力永久失效。特别是 `v8_cn_fetch.yml` 和 `v8_build_deploy.yml` 是整站的「呼吸」和「心跳」。

---

## 🟢 配置和文档

| 文件路径 | 内容描述 | 禁止删除原因 |
|---------|---------|------------|
| `.gitignore` | Git 忽略规则 | 保护临时文件不被入库 |
| `.gitattributes` | 换行符规范（LF） | 防止 Windows CRLF 导致 ubuntu runner bash 报错 |
| `README.md` | 项目说明 | 仓库门面 |
| `V8_PRINCIPLES.md` | v8 设计原则文档 | 架构决策记录 |
| `DO_NOT_DELETE.md` (本文件) | 禁止删除清单 | 防误删核心文档 |
| `HANDOVER*.md` | 双机交接文档 | 小九↔阿狸咪协作记录 |

---

## ⚪ 可清理文件/目录（超过N天可删除）

| 文件路径/模式 | 可删除条件 | 注意事项 |
|------------|-----------|---------|
| `__pycache__/` | 随时可删 | Python 字节码缓存，自动重建 |
| `algorithms/__pycache__/` | 随时可删 | 同上 |
| `out/` | 随时可删 | 算法中间产物，run_algorithms.py 重建 |
| `_tmp_*/` | 随时可删 | 临时切片目录 |
| `*.log` / `*.err` | 随时可删 | 空日志文件 |
| `_check_scripts.js` | 随时可删 | 一次性语法校验脚本 |

**清理前必须**:
1. 核对本清单，确认不在禁止删除列表中
2. 确认文件不以 `data/`、`raw_data/`、`.github/`、`algorithms/` 开头
3. 如有疑问，先询问再删除

---

## 📝 历史误删记录（教训）

| 日期 | 误删文件 | 原因 | 恢复方法 |
|-----|---------|------|---------|
| （暂无） | — | — | — |

**教训**: v6 曾于 2026-07-03 误删 `data/sh_sz_history.json`（瘦身时清空），从 git 历史恢复。v8 从一开始就建立此清单，避免重蹈覆辙。

---

## 🔄 维护说明

- **本文件必须持续维护**: 每次新增核心文件/目录，必须同步更新此清单
- **清理前必须核对**: 每次 cleanup / 瘦身，必须先读此清单
- **pre-commit hook 已安装**: 删除本清单内文件时 git commit 会自动拦截（exit 1）
- **定期审查**: 每周审查一次，确保清单完整性

---

**最后核对**: 2026-08-01 22:42 ✅
**下次审查**: 2026-08-08 (每周审查)
