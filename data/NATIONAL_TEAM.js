window.NATIONAL_TEAM = {
  "data_date": "2026-11-13",
  "update_time": "2026-11-14 00:01:14",
  "source_time": "2026-11-13 23:56",
  "score": 42.9,
  "verdict": "中性",
  "verdict_color": "#38bdf8",
  "ready_count": 3,
  "subs": [
    {
      "key": "A",
      "name": "宽基ETF净申购突变",
      "weight": 40,
      "ready": true,
      "value": -27.5,
      "unit": "亿",
      "detail": "宽基净申购 -27.5 亿（兜底·老源宽基分类 180 只）",
      "status": "❌净赎回"
    },
    {
      "key": "B",
      "name": "大金融相对强度",
      "weight": 30,
      "ready": true,
      "value": -1.02,
      "unit": "%",
      "detail": "大金融 relative_5d 均值 -1.02%（保险/多元金融/银行/证券）",
      "status": "❌弱势"
    },
    {
      "key": "C",
      "name": "大金融资金净流入",
      "weight": 15,
      "ready": true,
      "value": 13.1,
      "unit": "亿",
      "detail": "大金融净流入 13.1 亿（银行 12.3;多元金融 0.8）",
      "status": "✅流入"
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
  "oneline": "综合 42.9（中性）：宽基ETF净赎回 -27.5 亿＝未见托盘，大金融弱势，大金融资金净流入 13.1 亿——无托盘且市场走弱，宜收紧防守。"
};