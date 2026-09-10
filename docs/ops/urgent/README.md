# 🔴 本目录已停用 —— 禁止在此交接

**2026-09-10 主人令：交接文档统一放 `docs/ops/handover/`，本目录不再接收任何新文档。**

---

## 为什么停用

同一份交接曾被复制到 3 个位置（`docs/ops/handover/`、本目录、仓库根），
而两个读取器各自只扫自己认得的那一处 → **谁都不知道该读哪份**。
为消除这个歧义，本次统一为**唯一目录**：

| 项 | 值 |
|---|---|
| 唯一目录 | `docs/ops/handover/` |
| 命名规范 | `YYYY-MM-DD_HHmm[_URGENT]_<发件>给<收件>_<主题>.md`（时间优先，`ls` 即按时间排序） |
| 规范全文 | [`../handover/README.md`](../handover/README.md) |
| 新建交接 | `python docs/ops/scripts/new_handover.py --from 阿狸咪 --to 小九 --topic "主题" [--urgent]` |

## 本目录原有文件

原有 7 份紧急文档已全部迁入 `docs/ops/handover/`（文件名前缀 `URGENT` 段保留）。
旧名 → 新名对照见 `../handover/_迁移对照表_20260910.md`。

> 读取器 `v8_urgent_listener.py` 已于 2026-09-10 改为**只扫** `docs/ops/handover/`，
> 不再扫描本目录与仓库根 —— 写在这里的文件**不会被任何自动化读到**。

**需要紧急交接请用 `--urgent`，落在 `docs/ops/handover/`，不要写在这里。**
