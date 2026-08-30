window.STOCK_MOMENTUM_STATE = (function() {
  var data = {
 "update_time": "2026-08-30 17:43",
 "generated": "2026-08-30 17:43",
 "meta": {
  "generated": "2026-08-30 17:43",
  "source": "h_reverse_upgraded_breakout(脱离PDF OCR)",
  "total_days": 0,
  "days_with_consensus": 0,
  "total_consensus_stocks": 0
 },
 "days": []
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
