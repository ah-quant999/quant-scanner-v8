window.NATIONAL_TEAM = {
  "data_date": "2026-10-28",
  "update_time": "2026-10-28 02:22:04",
  "source_time": "2026-10-28 01:33",
  "score": 48.2,
  "verdict": "中性",
  "verdict_color": "#38bdf8",
  "ready_count": 3,
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
      "value": -1.08,
      "unit": "%",
      "detail": "大金融 relative_5d 均值 -1.08%（保险/多元金融/银行/证券）",
      "status": "❌弱势"
    },
    {
      "key": "C",
      "name": "大金融资金净流入",
      "weight": 20,
      "ready": true,
      "value": 7.7,
      "unit": "亿",
      "detail": "大金融净流入 7.7 亿（银行 7.7）",
      "status": "✅流入"
    },
    {
      "key": "D",
      "name": "汇金持仓环比",
      "weight": 0,
      "ready": true,
      "value": 9.82,
      "unit": "亿股",
      "detail": "汇金股票披露净增持 9.82 亿股（2024Q2），环比上季(2023Q4) +8.74 亿股 · 披露口径滞后",
      "status": "✅增持"
    }
  ],
  "method": "4 子信号加权（缺失项权重重分）；宽基ETF净申购45% + 大金融相对强度35% + 大金融资金净流入20%；汇金持仓环比权重0%（季报披露滞后1-3月，不参与实时评分，仅作定性印证）。",
  "disclaimer": "代理推算·非汇金官方实时持仓；宽基ETF净申购为最强国资托盘指纹，披露存 T+1 滞后；汇金持仓环比取自东方财富股东增减持披露（中央汇金投资有限责任公司），属法定义务披露、口径滞后且稀疏，如实标注，不构成交易建议。",
  "oneline": "综合 48.2（中性）：大金融弱势，大金融资金净流入 7.7 亿。"
};