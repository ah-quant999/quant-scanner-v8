window.NATIONAL_TEAM = {
  "data_date": "2026-10-27",
  "update_time": "2026-10-27 02:53:08",
  "source_time": "2026-10-27 00:33",
  "score": 46.6,
  "verdict": "中性",
  "verdict_color": "#38bdf8",
  "ready_count": 2,
  "subs": [
    {
      "key": "A",
      "name": "宽基ETF净申购突变",
      "weight": 45,
      "ready": false,
      "value": null,
      "unit": "亿",
      "detail": "etf_subscription_eastmoney.js 未就绪",
      "status": "—未就绪"
    },
    {
      "key": "B",
      "name": "大金融相对强度",
      "weight": 35,
      "ready": true,
      "value": -1.37,
      "unit": "%",
      "detail": "大金融 relative_5d 均值 -1.37%（保险/多元金融/银行/证券）",
      "status": "❌弱势"
    },
    {
      "key": "C",
      "name": "大金融资金净流入",
      "weight": 20,
      "ready": true,
      "value": 0.8,
      "unit": "亿",
      "detail": "大金融净流入 0.8 亿（银行 0.8）",
      "status": "✅流入"
    },
    {
      "key": "D",
      "name": "汇金持仓环比",
      "weight": 0,
      "ready": false,
      "value": null,
      "unit": "",
      "detail": "v8 无季报十大股东源 ⇒ 未接入（季报滞后1-3月，无法实时）",
      "status": "—未接入"
    }
  ],
  "method": "3 子信号加权（缺失项权重重分）；宽基ETF净申购45% + 大金融相对强度35% + 大金融资金净流入20%；汇金持仓季报未接入。",
  "disclaimer": "代理推算·非汇金官方实时持仓；宽基ETF净申购为最强国资托盘指纹，但披露存 T+1 滞后，仅作 regime 参考，不构成交易建议。",
  "oneline": "综合 46.6（中性）：大金融弱势，大金融资金净流入 0.8 亿。"
};