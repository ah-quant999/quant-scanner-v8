window.NATIONAL_TEAM = {
  "data_date": "2026-11-10",
  "update_time": "2026-11-11 21:44:33",
  "source_time": "2026-11-11 18:24",
  "score": 50.8,
  "verdict": "中性",
  "verdict_color": "#38bdf8",
  "ready_count": 3,
  "subs": [
    {
      "key": "A",
      "name": "宽基ETF净申购突变",
      "weight": 40,
      "ready": true,
      "value": 5.0,
      "unit": "亿",
      "detail": "宽基净申购 5.0 亿（1 只宽基ETF·东财五分类）",
      "status": "🟡中性"
    },
    {
      "key": "B",
      "name": "大金融相对强度",
      "weight": 30,
      "ready": true,
      "value": -0.11,
      "unit": "%",
      "detail": "大金融 relative_5d 均值 -0.11%（保险/多元金融/银行/证券）",
      "status": "🟡中性"
    },
    {
      "key": "C",
      "name": "大金融资金净流入",
      "weight": 15,
      "ready": true,
      "value": -3.2,
      "unit": "亿",
      "detail": "大金融净流入 -3.2 亿（银行 -3.2）",
      "status": "❌流出"
    },
    {
      "key": "D",
      "name": "宽基ETF放量异动",
      "weight": 15,
      "ready": false,
      "value": null,
      "unit": "×",
      "detail": "broad_etf_volume.json 缺失/过期（post_close 档未落盘）",
      "status": "—未就绪"
    }
  ],
  "method": "4 子信号加权（缺失项权重重分）；宽基ETF净申购40% + 大金融相对强度30% + 大金融资金净流入15% + 宽基ETF放量异动15%（2026-11-05 主人令新接入：下跌日头部宽基ETF成交额/20日均额，护盘公开指纹）。汇金持仓环比胶囊已于 2026-11-04 移除（季报滞后约2年、权重0%、无增量信息）。",
  "disclaimer": "代理推算·非汇金官方实时持仓；宽基ETF净申购为最强国资托盘指纹，披露存 T+1 滞后，如实标注，不构成交易建议。",
  "oneline": "综合 50.8（中性）：宽基ETF净申购 5.0 亿＝托盘力度中性，大金融中性，大金融资金净流出 3.2 亿。"
};