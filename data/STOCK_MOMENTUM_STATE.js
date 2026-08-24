window.STOCK_MOMENTUM_STATE = (function() {
  var data = {
 "update_time": "2026-08-24 23:30",
 "generated": "2026-08-24 23:30",
 "meta": {
  "generated": "2026-08-24 23:30",
  "source": "h_reverse_upgraded_breakout(脱离PDF OCR)",
  "total_days": 1,
  "days_with_consensus": 0,
  "total_consensus_stocks": 0
 },
 "days": [
  {
   "date": "2026-08-24",
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
