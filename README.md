# 九宝量化 V8.0

独立部署的量化系统原型。暗色主题、六板块设计、ETF/IPO/宏观数据接入。

## 部署

```bash
python update_v8.py    # 构建 + 注入数据 → dist/index.html
python deploy_v8.py    # 推 gh-pages
python guard_v8.py     # 守护（防止被覆盖）
```

URL: https://ah-quant999.github.io/quant-scanner-v8/

---

## 🔴 交接文档规范（2026-09-10 主人令）

- **唯一交接目录**：`docs/ops/handover/`（规范全文见该目录 `README.md`）
- **命名：时间优先** —— `YYYY-MM-DD_HHmm[_URGENT]_<发件>给<收件>_<主题>.md`
  → `ls` 默认排序即时间排序，不依赖 mtime（坚果云同步会重写 mtime）
- **禁止**在仓库根目录、`docs/ops/urgent/`、`_handover_*` 等位置新建交接文档
- 新建：`python docs/ops/scripts/new_handover.py --from 阿狸咪 --to 小九 --topic "主题" [--urgent]`
