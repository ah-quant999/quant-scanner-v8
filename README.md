# 九宝量化 V8.0

独立部署的量化系统原型。暗色主题、六板块设计、ETF/IPO/宏观数据接入。

## 部署

```bash
python update_v8.py    # 构建 + 注入数据 → dist/index.html
python deploy_v8.py    # 推 gh-pages
python guard_v8.py     # 守护（防止被覆盖）
```

URL: https://ah-quant999.github.io/quant-scanner-v8/
