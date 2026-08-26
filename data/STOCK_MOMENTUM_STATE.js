window.STOCK_MOMENTUM_STATE = (function() {
  var data = {
 "update_time": "2026-08-26 17:12",
 "generated": "2026-08-26 17:12",
 "meta": {
  "generated": "2026-08-26 17:12",
  "source": "h_reverse_upgraded_breakout(脱离PDF OCR)",
  "total_days": 2,
  "days_with_consensus": 0,
  "total_consensus_stocks": 0
 },
 "days": [
  {
   "date": "2026-08-25",
   "categories": {
    "突破": [
     {
      "code": "600028",
      "name": "中国石化",
      "change_pct": 4.51,
      "price": 5.33,
      "category": "突破"
     },
     {
      "code": "600409",
      "name": "三友化工",
      "change_pct": 3.13,
      "price": 6.92,
      "category": "突破"
     }
    ],
    "短线选股": [
     {
      "code": "600028",
      "name": "中国石化",
      "change_pct": 4.51,
      "price": 5.33,
      "category": "短线选股"
     },
     {
      "code": "600409",
      "name": "三友化工",
      "change_pct": 3.13,
      "price": 6.92,
      "category": "短线选股"
     }
    ]
   },
   "consensus": []
  },
  {
   "date": "2026-08-26",
   "categories": {},
   "consensus": []
  }
 ]
};
  return {
    getDays: function() { return data.days; },
    getConsensus: function(date) {
      for (var i=0;i<data.days.length;i++) { if(data.days[i].date===date) return data.days[i].consensus; }
      return [];
    },
    getTopConsensus: function(n) { return []; },
    getSummary: function() { return data.meta; },
    getAll: function() { return data; }
  };
})();
