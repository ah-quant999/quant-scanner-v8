# 交接文档：今日判定卡 posAdvice 崩溃修复

## 现象
主人截图反馈：「暂未上架底部挂了」。
浏览器控制台错误：
```
renderUnlisted 错误：ReferenceError: posAdvice is not defined
  at index.html:8638:97
```

## 根因
`index.html` 中「今日判定 · 可入手候选 + 决策纪律」卡片的横幅文案引用了 `posAdvice` 变量（显示仓位建议），但该变量仅在「情绪周期 · 连板天梯」卡片内部定义，未在当前 IIFE 中声明，导致运行时 ReferenceError，整个 `renderUnlisted` 异常中断。

## 修复内容
### `index.html`
1. 在「今日判定」卡片 IIFE 内新增 `posAdvice` 定义，按危机分档：
   - crisisPct ≥ 70 → 空仓
   - crisisPct ≥ 50 → 轻仓
   - crisisPct ≥ 30 → 中性
   - 否则 → 重仓
2. 修正横幅文案为「XX分危机 · 仓位XX」，避免原「空仓仓位」重复。
3. 未影响情绪周期卡自身的 `posAdvice` 逻辑。

## 验证
- `node --check`：81 个 script 块全部通过
- 浏览器端 `posAdvice is not defined` 已消除

## 提交
- commit: `5ed70d5`
- 已 push 到 `origin/main`

## 小九注意事项
- 该错误仅发生在前端渲染阶段，不是数据源问题；08:25 premarket 重新生成数据后不会自愈。
- 如后续再调整今日判定卡文案，注意检查 IIFE 内部变量是否在当前作用域内定义；跨脚本块变量需经 `window.X = X` 暴露。
