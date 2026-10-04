# HANDOVER｜阿狸咪 → 小九｜2026-10-04 08:47｜宏观观测AI速览整卡降级根修_RenderMahoroCard残留d死引用ReferenceError

> 规范：`docs/ops/handover/README.md`（唯一交接目录，时间优先命名）

---

## 一句话结论

主人 10-04 08:39 截图实锤「AI 速览（Mahoro）渲染异常·已降级：d is not defined」——根因是 2026-10-03 maharo_macro 退役（commit 92628b37b5）删了 `renderMahoroCard` 里的 `var d` 声明却**漏删函数体后半部分 7 处 `d.xxx` 死引用**；此前靠 `window.MAHORO_INSIGHTS ||` 短路侥幸不炸，insights 一加载成功走到 `d.sources` 即 ReferenceError 整卡降级。已删净 7 处死引用 + 退役两块孤儿 UI（d.sources 来源徽章 / d.watched·core·all_lite 原始条目录），logic.html 同步，`3ce2629401`+`4c56b12aac` 已快进推送 origin/main，门禁 15/15 全绿。

---

## 正文

### 根因链（实锤）

1. `renderMahoroCard()`（index.html 原 16062~16100）残留 7 处 `d.` 引用：`d.insights`（有 `||` 短路保护，侥幸不炸）、`d.sources`×2（**无保护，必炸点**）、`d.watched/d.core/d.all_lite`×4。
2. 触发条件：`window.MAHORO_INSIGHTS` 加载成功且 `daily.generated_at` 非空 → 通过 15943 闸门 → 16082 `if(d.sources && ...)` 直接对未定义的 `d` 取属性 → `ReferenceError: d is not defined` → 整卡降级。
3. 若 MAHORO_INSIGHTS 未加载则提前 return「暂未生成」，不触发——所以这雷自 10-03 部署后一直潜伏，今日 insights 正常产出才引爆。

### 修复内容（commit `3ce2629401`，index.html +9/-20）

- `var ins = window.MAHORO_INSIGHTS || d.insights || {}` → `var ins = ins0`（ins0 函数头已兜底）。
- **整块删除** `d.sources` 来源徽章块（maharo_macro 数据源已退役，该 UI 永不渲染有意义内容）。
- **整块删除** `d.watched/core/all_lite` 原始条目录 `<details>` 块（同属 maharo_macro 孤儿 UI）。
- 「解析待生成」兜底 + 免责声明尾行保留不变。
- 全文件扫描自证：`d.watched/d.sources/d.insights/d.all_lite/d.core` 代码级引用 0 处（仅剩修复注释）。11918 处 `d.` 为 `renderMarketFundFlow` 合法局部变量，已排除。

### 四方对齐

- logic.html:2081 `<details>` 计数描述追加 2026-10-04 变更记录（commit `4c56b12aac`）。
- `pre_deploy_audit` 15/15 全绿（含 [10/10] 43/43 核心标记、[12/12] 调用点 156 个全有定义、[15/15] logic.html 76 戳一致）；inline JS：index 29/29、logic 6/6 零错。

### 推仓自证

- `05bc70f672..3ce2629401..4c56b12aac` 快进推送零顶掉；index.html blob `c1873b4a3e`、logic.html blob `afe9c05a90` 均 local==remote 一致。

### 待小九项

- 无阻断项。仅提醒：今后删「声明+消费」型代码块时须同删函数体内全部消费点（[12/12] 调用点定义守卫会拦，但本例 `d` 是裸标识符非函数调用，守卫不覆盖该形态——已在修复注释中留档）。

### 复核命令

```bash
git fetch && git log --oneline -2 origin/main   # 应见 4c56b12aac / 3ce2629401
grep -n "d\.sources\|d\.watched" index.html      # 应只剩注释
```
