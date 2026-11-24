# 交接件：龙头股卡二次被洗回根治 —— 生成器 NeoData 第四层兜底正式落仓（阿狸咪→小九）

**时间**：2026-10-02 18:41（CST，国庆休市）
**提交**：`f875d7dff2ba72eb1bd21a69b19c935f2c38323b`（**脚本+数据同批单提交**）
**署名**：阿狸咪的工程师（alimi-cn）

## 1. 事件时间线
| 时刻 | 事件 |
|---|---|
| 10-01 21:12 | 首次修复：推 `data/SECTOR_LEADERS.js`（4 板块×5 龙头，NeoData 兜底），提交 `721ef29` |
| 10-01 21:20 | 交接件推送 `a85e0906`；**但漏推了生成器脚本本身（本人失误）** |
| 10-02 00:36 | cn fetch 跑批用**远端旧脚本**重生成 ⇒ 4 板块 `leaders:[]` 洗回（提交 `5fce49`）——主人截图质询「怎么又被覆盖了」 |
| 10-02 18:3x | 复盘时还发现本地脚本改动被**同步盘静默回退**（Nutstore 未提交改动回退，§100 铁律场景） |
| 10-02 18:41 | 根治：脚本+数据双文件单提交推送，回读逐字节一致 |

## 2. 二次洗回双根因
1. **我方失误**：10-01 只推产物数据、漏推 `scripts/fetch_sector_leaders.py` ⇒ 跑批用旧脚本必然重生成空白版。**教训：改生成器的修复必须「脚本+当轮产物」同批推，单推产物=定时炸弹。**（与 10-01 namefix 10 卡「js+raw json 同批推」教训同构）
2. **同步盘回退**：本地工作区的脚本改动（未 git 提交，本机 main 孤儿化禁 push）被 Nutstore 数十秒内静默回退 ⇒ 修复字节必须产自仓外（`E:/_alimi_tools/tmp_compare/`），推送不依赖工作区。

## 3. 本次落仓内容
- `scripts/fetch_sector_leaders.py`（27934B）：正式落 **NeoData 第四层兜底**——`_neo_token()`（algorithms/.neodata_token 优先，云端跑批机器上该文件存在——SECTOR_RS 一直正常产出即铁证）/ `_neo_cons()`（urllib 实现，无新依赖；仅前三层〔东财在线/名单缓存/腾讯行情〕全失效时启用；任何失败 return None 不抛错）。`build()` 两分支（no_match / cons 失败）接入，payload 加 `neo_fallback_count`，source 追加 NeoData 标注，log 加 `neo_fallback=%d`。
- `data/SECTOR_LEADERS.js`（3041B）：`update_time=2026-10-02 02:33`（取 SECTOR_RS 源时戳）、`data_date=2026-09-30`、`republish_time=2026-10-02 18:39:46`、`neo_fallback_count=4`、4 板块各 5 龙头 `match=neodata`。

## 4. 数据质量核验
- 东财 push2 **此刻仍全断**（RemoteDisconnected 实锤，推送前刚复测）。
- 风电设备/生物制品/房地产 3 板块与 10-01 腾讯核验基线**逐股完全一致**。
- 汽车整车 5 只（江淮 5.49/千里 3.41/上汽 1.59/比亚迪 1.57/宇通 1.44）经腾讯 `qt.gtimg.cn` **逐股核验全真**。
- ⚠️ **已知限制**：NeoData 今日成分快照漏广汽集团（真值 +4.29%，理应列第 2）——自然语言检索的成分覆盖波动，**非代码缺陷**；不手工拼数据（纪律），东财恢复后自动回归完整口径。

## 5. 小九须知
- **下轮跑批即带兜底**：脚本已落仓，跑批机器 `algorithms/.neodata_token` 存在即可用 NeoData；若该文件在跑批机缺失 ⇒ 兜底自动降级为旧行为（no_match 明示），不会崩。
- **节后观察**：东财恢复后 `em_boards_source` 应回 `available`、`neo_fallback_count` 归 0、`match` 回 `exact/norm`。
- 若东财长期不恢复，可考虑给 NeoData 兜底加「腾讯行情补真值重排」增强（本次从简未做）。
- 阿狸咪本轮未碰 index.html / 算法链产物，零洗版。
