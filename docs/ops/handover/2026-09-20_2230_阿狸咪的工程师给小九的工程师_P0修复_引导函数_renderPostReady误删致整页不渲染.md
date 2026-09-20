# 2026-09-20 22:30 阿狸咪的工程师 → 小九的工程师 · P0 线上事故修复（整页不渲染）

## 0. 一句话
线上主站「回测汇总」等整片区域卡在「加载中」不渲染，根因是 **21:07 提交 `0d3482be4` 删死代码时误删了引导函数 `_renderPostReady` 的定义**（调用点仍在）⇒ `ReferenceError` ⇒ 初始渲染链整条不执行。已在最新基线上修复并上线（`b2d217a8e8`），并加了防复发守卫。

## 1. 事故现象（主人 21:52 反馈）
- 页面：「📊 回测汇总」卡内 `⏳ 回测总览 加载中...` 常驻不消失，下方亦「加载中...」。
- 控制台：`Uncaught ReferenceError: _renderPostReady is not defined`
  at `quant-scanner-v8/?v=…:8353:51`（`document.addEventListener('DOMContentLoaded', _renderPostReady)`）

## 2. 根因（已逐层取证）
| 项 | 证据 |
|---|---|
| 调用点仍在 | 最新版 L8353/8355 两处引用 `_renderPostReady` |
| 定义已丢 | `grep -c "function _renderPostReady"` = **0** |
| 谁删的 | `git log -S "function _renderPostReady"` → **`0d3482be4`**「🧹 删 __renderFactorLab 死代码（因子卡去两步后容器已删，函数恒早退）」21:07 |
| 删除形态 | 该提交 hunk 里 `-  function _renderPostReady(){ … } try{ window.renderLifeBacktests(); }catch(e){}` 被整行带走 |

机制：`document.addEventListener('DOMContentLoaded', _renderPostReady)` 是**求值即抛**（标识符未定义），
异常发生在 `<script>` 顶层 ⇒ 该块后续语句与后续注册全部不生效 ⇒ `_renderPostReady` 永不执行 ⇒
`__renderBacktestSection()` / `__renderLifecycleSection()` 等 **11 个渲染器**从不上屏。这就是「卡加载中」。

## 3. 修复（commit `b2d217a8e8`，已上线）
- 在最新远端版（`0129fd6` 基线，非本地旧树）上重打补丁：**恢复 `_renderPostReady` 定义**，
  并按 `0d3482be4` 本意**剔除已删除的 `__renderFactorLab()` 调用**；其余 11 个渲染函数实测全部存活。
- 补丁前后 `+868B`，语法 28 块 0 错、div/span 闭合 1534/1534、1330/1330。
- 门禁 `pre_deploy_audit` **10/10 全绿** + `align_logic_ops` 通过 + `v8_verify_layer_parity` 通过。
- CI：`☁️ v8 构建部署` + `pages build and deploy` 双 success；已在**最新 main（54474c20）**复验定义仍在。

## 4. 效果验证（夹具 + 回退版对照，非「跑通即算」）
| 版本 | 运行时首个错误 |
|---|---|
| 回退版（远端 `0129fd6`，bug 在位） | `ReferenceError: _renderPostReady is not defined`（**与主人控制台逐字一致**） |
| 线上版（修复后） | **NO_ERROR** |

方法：抽含该标识符的 inline `<script>` 块，在 Proxy 沙箱 `vm.runInContext` 真跑（`_a_ppr_ab.js`），
另加静态顺序守卫「定义必须在调用点之前且同块」（`_a_ppr_order.js`，线上版 `def@187032 < call@187971`）。
> 说明：`agent-browser` 守护进程本轮起不来（SIGTERM），故改用上述可复现的运行时夹具替代真浏览器终验。

## 5. 防复发加固（本次新增，防同类二次发生）
1. `docs/ops/index_protected_markers.txt` 追加 2 条长期锚点（**32 → 34 条**）：
   - `function _renderPostReady` — 引导函数定义（初渲入口）
   - `DOMContentLoaded', _renderPostReady` — 调用点；与定义必须同块且定义在前
2. **守卫效力 A/B 验证**：把回退版放进仓跑 `[10/10]`
   ⇒ `❌ 1/34 条核心标记消失：function _renderPostReady`（**当场阻断 deploy**）；
   修复版 ⇒ `✅ 34/34 全部在位`。（验证后本地已还原，md5 一致）
3. ⚠️ **给小九的操作纪律**：`0d3482be4` 那类「删死代码」提交，删前必须 grep 该标识符的**调用点**；
   凡是被 `addEventListener` / `DOMContentLoaded` 引用的**引导函数**，删函数必须同步删/改调用点，
   否则求值即抛、整块 script 失效。今后该类误删会被 `[10/10]` 拦在 deploy 前。

## 6. 验收判据（给主人）
1. **Ctrl + F5 硬刷新**（清 Pages CDN 缓存）；
2. 「📊 回测汇总」应正常显示四量终极/三重共识/强势跟踪/逆势龙头四行回测数据，**不再出现「加载中」**；
3. 控制台 `F12` 应**无** `_renderPostReady is not defined`（其余历史 warning 不属本条）。

## 7. 附件 / 复现路径
- 补丁脚本：`_a_ppr_patch.py`（锚文本替换，命中数断言）
- 一站式流水线：`_a_ppr_pipeline.py`（拉最新→验 bug 在位→打补丁→语法→推送→自证）
- A/B 夹具：`_a_ppr_ab.js`｜顺序守卫：`_a_ppr_order.js`｜悬空引用审计：`_a_ppr_audit.py`
  （审计结论：`0d3482be4` 删除的 7 个定义名中，**0 处悬空引用**，无同类残留）
