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

## 🔴 AI 会话入口（2026-09-21 起强制）

**动本仓任何文件前，先读 [`AGENTS.md`](AGENTS.md)。**
它给出必读清单（状态源 / 并发协议 / 安全铁律 / 时序表）、一屏速查与硬禁区。

工具侧入口（**四者指向同一份权威，均不含协议正文**）：

| 文件 | 谁会自动读 |
|---|---|
| `AGENTS.md` | WorkBuddy 项目根、Codex、Claude Code 等（[官方支持](https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Project)） |
| `.codebuddy/CODEBUDDY.md` | WorkBuddy 项目级记忆 |
| `docs/ops/skills/v8-handoff-gateway/SKILL.md` | 双机并发协议**唯一正文**（需引用时从仓内读） |
| `docs/ops/HANDOFF.yaml` | 「什么还没做」**唯一状态源** |

---

## 🔴 交接文档规范（2026-09-10 主人令）

- **唯一交接目录**：`docs/ops/handover/`（规范全文见该目录 `README.md`）
- **命名：时间优先** —— `YYYY-MM-DD_HHmm[_URGENT]_<发件>给<收件>_<主题>.md`
  → `ls` 默认排序即时间排序，不依赖 mtime（坚果云同步会重写 mtime）
- **禁止**在仓库根目录、`docs/ops/urgent/`、`_handover_*` 等位置新建交接文档
- 新建：`python docs/ops/scripts/new_handover.py --from 阿狸咪 --to 小九 --topic "主题" [--urgent]`
