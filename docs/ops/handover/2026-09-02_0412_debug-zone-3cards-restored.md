# HANDOVER 2026-09-02 04-12 debug-zone-3cards-restored

## 一句话定位
主人 04:08 令「加回！」→ 调试专区 3 卡（宏观+板块推荐+曲线新卡）22:55 082e27fc0 误删 → 4 处精确插入恢复 → 已 push `bd38dc891`，主站将 5-10 min 重建。

## 4 处精确插入（HEAD = f264bc818 commit 后状态）

| # | 插入点 | 位置 | 内容 |
|---|---|---|---|
| A | 容器段 | line 10746-10751（`h += '<div id="ulSectorFundTrackPanel">加载中…</div>';` 后） | 注释改写：把"全部清出"改为"已下沉至「已下架」"+ "2026-09-02 主人令恢复" + 2 个 div（ulMacroPanel / ulSecPanel） |
| B | 渲染调用段 | line 10768-10772（`renderSectorFundTrackCard` 调用后） | 加 2 个 try{ renderMarketRegimeCard() } + try{ renderSectorRecommendationCard() } 渲染兜底 |
| C | 函数定义段 | line 10657 后（`window.renderSectorFundTrackCard = renderSectorFundTrackCard;` 后） | 从 c80d42bc1 完整恢复 ~85 行（renderMarketRegimeCard 35 行 + renderSectorRecommendationCard 50 行） |
| D | window 挂载段 | line 12417 后（"市场路径概率已随三卡删除"注释后） | 加 `window.renderMarketRegimeCard = renderMarketRegimeCard;` + `window.renderSectorRecommendationCard = renderSectorRecommendationCard;` |

diff: `1 file changed, 91 insertions(+), 10 deletions(-)`（仅 index.html）。

## 背景算法链状态（主人 03:51「灵活一点跑出来」自跑应急）

- 后台 `python algorithms/run_algorithms.py` 已起，**3 个 python.exe 进程活跃**（128MB / 39MB / 27MB）
- 心跳 `raw_data/algo_heartbeat.json`:
  - `update_time: 2026-09-02 04:10:40`
  - `step: run_algorithms / status: running / pid: 6320`
  - `started: 2026-09-02 04:09:55`（本次重启时间）
  - `silent_sec: 45`（45 秒没新输出，仍在算）
- 已产今日数据：`GOLD_POOL 2026-09-02 03:53` / `COCKPIT_ADVICE 2026-09-02 03:53` / `SECTOR_RECOMMENDATION 2026-09-02 03:53` / `MARKET_REGIME 2026-09-02T03:15`
- **仍陈旧**（链没跑完）：`FINAL_RECOMMEND 08-31 21:19` / `TRIPLE_CONSENSUS 08-31 19:53` / `TOP10_DAILY 08-31 19:16` / `FOUR_VOLUME 09-01 21:03`

## 等链跑完要做的事（预计 30-60 min 后）

1. **链跑完自动收尾**（不用主人动）：
   - 后台 Python 写完 `raw_data/*.json` → `update_v8.py` 重生成 `data/*.js`
   - `v8_health_check.py` 刷 `data/HEALTH_CHECK.js`
2. **立即原子推**（Nutstore 铁律）：
   - `git add raw_data/ data/ HEALTH_CHECK.js`（显式路径，禁 `-A`）
   - `git commit + fetch + rebase -X theirs + push` 一气
3. 盯防 `f159e4c1-f526-487c-9504-1c6b2b4f9fbb`（已延至 08:00）转绿自动邮件 `2814546@qq.com`

## Nutstore 4 次踩坑（彻底铁律）

1. **`git add -A`** × 误删整目录：必须**显式 add 具体路径**
2. **index.html.bak_<时间戳>** × 把 .bak 当主版本反向同步：备份放仓库外 `C:\Users\HH20210606\WorkBuddy\<session>\`
3. **后台链跑批期间改 index.html** × 频繁被 Nutstore 回滚：要么等链跑完再改、要么 `git add <具体路径>` 后立即原子 commit
4. **工作时间门户 Git 改 `.bak` 备份**：放仓库外（本轮已用）

## 4 处插入后验证（本地 grep 实证）

```
[1] function renderMarketRegimeCard        → line 10661 ✓
[2] var host = document.getElementById('ulMacroPanel')  → line 10662 ✓
[3] h+='<div id="ulMacroPanel"></div>'    → line 10826 ✓
[4] try{ if(typeof window.renderMarketRegimeCard==='function')...  → line 10847 ✓
[5] window.renderMarketRegimeCard = ...   → line 12496 ✓
[6] window.renderSectorRecommendationCard = ...  → line 12497 ✓
```
