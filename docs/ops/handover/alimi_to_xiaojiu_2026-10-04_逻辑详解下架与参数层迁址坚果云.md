# 阿狸咪 → 小九 ｜ 逻辑详解「已下架」+ 参数层（完整版）迁址坚果云同步盘

- **撰写时刻**：2026-10-04（北京时间，周末夜班）
- **级别**：常规交接（非紧急）
- **状态**：**已改完、离线门禁全绿、本地已 commit，未 push**（等主人「上线」指令）
- **涉及文件**：`index.html` / `logic.html` / `align_logic_ops.py` / `.gitignore`（仓库根），外加仓库外 `v8_logic_private/logic.full.html`（坚果云同步盘）

---

## 1. 一句话

逻辑详解（含全部交易参数：阈值 / 权重 / 公式 / 胜率 / 评分 / 止损 / 仓位）**已对访客彻底不可见**：公开站点删掉入口 Tab、`logic.html` 降级为「已下架」说明页，**完整版只存本机私有副本（经坚果云同步盘双机共享）**，绝不进 GitHub Pages。

---

## 2. 为什么这么改（主人令脉络）

- 逻辑详解是主人「只能自己一个人看到」的核心资产，但平时三件套（双机收尾自检）依赖它对齐。
- 原方案想「建私有 GitHub 仓」→ 主人否决（要免费）→ 改为「本机仓库外目录」→ 再选「坚果云同步盘」（双机自动同步，小九也能在三件套时对齐）。
- 中间一步曾写「口径骨架版」公开页，主人看图后明确：**访客完全看不到，把逻辑详解下架**。故最终方案 = 彻底下架，而非拆层。

---

## 3. 具体改动（4 个仓库文件 + 1 个仓库外文件）

| 文件 | 改动 | 核验 |
|---|---|---|
| `index.html` | 删除顶部「🔒 逻辑详解」Tab 整行；运维页说明框改为「已下架」措辞 | grep 确认无残留公开跳转入口（仅限管理员 guarded 函数内的 `window.open('./logic.html')`） |
| `logic.html` | 重写为「已下架」说明页：无参数、无 `data/*.js` 引用；HTML 注释与正文均不含绝对路径泄露 | 已收敛为 `v8_logic_private/logic.full.html`（相对同步盘根） |
| `align_logic_ops.py` | `main()` 开头优先探测本地完整版：`V8_LOGIC_FULL` 环境变量 + 多候选路径（含 `E:/Nutstore/`、`C:/Users/HH20210606/Nutstore/`、`D:/Nutstore/` 等坚果云根），命中则 `DOC_SOURCES.insert(0, ...)` | 上轮门禁实测对齐 `logic.full.html#sec-lg 540770 字符` ✅ |
| `.gitignore` | 加防御行 `logic.full.html` | grep 第 80 行确认 ✅ |
| `v8_logic_private/logic.full.html`（仓库外） | 完整版从 `E:\v8_logic_private\` 移入坚果云 `E:\Nutstore\v8_logic_private\logic.full.html`（773163 字节），双机自动同步；旧目录已删 | ls 确认 773163 B 在位 ✅ |

### 口令
- `ADMIN_HASH` 已换为 `cat8899` 的 SHA-256：`c6d4fb79e8b66e7bcb829cdafed22a81042558b7e2dcb1090be5d9a14a52ecd4`（已用 `sha256sum` 复核一致）。**注释不写明文**。
- 前端锁本质仍是「挡普通访客」的减速带（哈希写在客户端 JS，可被离线爆破或绕过 JS 校验），**真正的安全边界是完整版不进公开站点**。

---

## 4. 口令牌守卫（铁律延续）

- `logic.html` 缓存戳守卫（`[15/15]`）只校验「带 `?v` 的 `data/*.js` 引用」→ 0 引用即放行。
- `new Function`（`[2/8]`）只扫 `index.html` 内联脚本 → 删 Tab / 改说明框不触发。
- `align_logic_ops` 只校验 workflow 名字是否在文档源出现（名字出现即通过），不校验参数内容 → 完整版对齐仅本机手动跑三件套时生效。

---

## 5. 离线门禁（三件套第②件）

- 重跑 `_gate_logic_20261004/gate.py`：**GATE_EXIT=0**（pre_deploy_audit 15 项 / align_logic_ops / v8_verify_layer_parity 三道全绿）。
- 复跑时间：2026-10-04 本轮改完两处（logic.html 注释收敛 + index.html 说明框）之后。

---

## 6. 时窗矩阵（三件套第①件）

- 本轮**无任何 cron / workflow 时段变更** → 时窗矩阵**无需调整**，维持现状。

---

## 7. 给小九（三件套对齐怎么用完整版）

- 需要三件套对齐逻辑详解参数层时，**确保本机坚果云已同步到 `v8_logic_private/logic.full.html`**，或设环境变量 `V8_LOGIC_FULL` 指向该文件绝对路径，再跑 `align_logic_ops.py`。
- 云端 CI 对齐 `logic.html` 时只能拿到「已下架」页（无参数）→ 仅本机手动跑三件套能对齐完整版。这是已知架构事实，不是 bug。

---

## 8. 待办 / 风险（不阻塞本次，另议）

- **git 历史**：曾公开提交过完整版（历史可读）。如需彻底清除需 `git filter-repo` 重写历史，建议另开专项，不阻塞本次下架。
- **未 push**：本地 4 文件改动已 commit，等主人「上线」指令再 push main → GitHub Pages 自动发布。
- **口令强度**：`cat8899` 非强口令，但前端锁本就只是减速带；若主人要求更强，可换 12+ 位或 4 词口令，届时改 `ADMIN_HASH` 单行 + 复核即可。
