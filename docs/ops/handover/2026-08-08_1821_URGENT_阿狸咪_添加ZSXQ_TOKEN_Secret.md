# 🚨🚨 URGENT 阿狸咪→小九：**拿到后立即执行**（2 分钟）

**时间**: 2026-08-08 18:21 (周六)
**来源**: 主人（家里网络不行，上不了 GitHub）
**优先级**: **🔴 紧急** — **看到此文件后立刻操作，不要等周一！**
**预期效果**: 加好后今晚 18:30 云端算法链就能拉到观澜台+maharo 数据，主人晚上就能看到最新数据

## 背景

`guanlan_extractor.py` 已改为优先读 `ZSXQ_TOKEN` 环境变量，`v8_algo_cloud.yml` 已配好 `${{ secrets.ZSXQ_TOKEN }}` 和 `${{ secrets.MAHORO_COOKIE }}` 注入。

**但 GitHub 仓库里还没建这两个 Secret** → 云端跑时 token 为空 → 观澜台=0、maharo=0。

## ⏱️ 小九现在就做（2 分钟，两个 Secret）

| Secret | 值来源 | 用途 |
|--------|--------|------|
| `ZSXQ_TOKEN` | 小九本地 `data/zsxq_token.json` 的 `token` 字段 | 知识星球观澜台研报 |
| `MAHORO_COOKIE` | 小九本地 `data/.maharo_cookies.txt` | maharo 投行信号 |

### 操作步骤（每个 secret 重复一次）：

1. 打开：`https://github.com/ah-quant999/quant-scanner-v8/settings/secrets/actions`
2. 点 **"New repository secret"**
3. 填 Name + Value（见上表）
4. 点 **Add secret**

## 验证

配好后**今晚 18:30** `v8_algo_cloud` 跑完，运维页「🔌 外部数据源」卡片里观澜台+maharo 应该变绿。

## 备注

- 这两个 secret 不定期过期，过期后需重新向主人拿新值
- **做完后在 URGENT 文件末尾加一行"✅ 已完成"并 commit**，阿狸咪下次巡检会确认
