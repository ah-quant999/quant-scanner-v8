// ═══════════════════════════════════════════════════════════════════════
// 🔴🔴 重要档案文件 · 禁止删除 · 禁止 git rm · 禁止加入清理白名单 🔴🔴
//
// 板块周期档案（SECTOR_CYCLE_ARCHIVE）
//   —— 由 raw_data/limit_up_heatmap.json 的累积长表派生，记录每个板块的
//      「启动 → 退潮」周期区间（几几年几月启动、几月结束），可逐年回查。
//
// ⚠️ 本文件是**长期累积数据**，价值随年月增长，一旦删除无法恢复
//    （涨停数据源只保留最近 1 个月，历史无法重新拉取）。
//    已登记于 PROTECTED_FILES.json，由 guard_protected_files.py 守卫。
//
// 生成器：build_sector_cycle_archive.py
// 最后更新：2026-11-05 17:27:51
// ═══════════════════════════════════════════════════════════════════════

window.SECTOR_CYCLE_ARCHIVE = {
  "update_time": "2026-11-05 17:27:51",
  "version": 1,
  "source": "raw_data/limit_up_heatmap.json",
  "params": {
    "hot_min": 3,
    "cycle_gap": 3,
    "min_len": 1
  },
  "range": [
    "09/11",
    "11/05"
  ],
  "columns": 34,
  "cycle_count": 21,
  "cycles": [
    {
      "sector": "AI算力",
      "start": "09/11",
      "end": "11/05",
      "start_idx": 0,
      "end_idx": 33,
      "days": 34,
      "hot_days": 32,
      "peak": 28,
      "peak_date": "09/22",
      "total": 327,
      "ongoing": true
    },
    {
      "sector": "其他",
      "start": "09/11",
      "end": "11/05",
      "start_idx": 0,
      "end_idx": 33,
      "days": 34,
      "hot_days": 34,
      "peak": 123,
      "peak_date": "10/14",
      "total": 2044,
      "ongoing": true
    },
    {
      "sector": "医药",
      "start": "09/11",
      "end": "11/05",
      "start_idx": 0,
      "end_idx": 33,
      "days": 34,
      "hot_days": 33,
      "peak": 47,
      "peak_date": "09/22",
      "total": 457,
      "ongoing": true
    },
    {
      "sector": "半导体",
      "start": "09/11",
      "end": "09/30",
      "start_idx": 0,
      "end_idx": 12,
      "days": 13,
      "hot_days": 13,
      "peak": 21,
      "peak_date": "09/22",
      "total": 134,
      "ongoing": false
    },
    {
      "sector": "消费电子",
      "start": "09/11",
      "end": "11/05",
      "start_idx": 0,
      "end_idx": 33,
      "days": 34,
      "hot_days": 32,
      "peak": 27,
      "peak_date": "09/21",
      "total": 289,
      "ongoing": true
    },
    {
      "sector": "电力",
      "start": "09/11",
      "end": "10/19",
      "start_idx": 0,
      "end_idx": 20,
      "days": 21,
      "hot_days": 20,
      "peak": 17,
      "peak_date": "10/12",
      "total": 162,
      "ongoing": false
    },
    {
      "sector": "通信设备",
      "start": "09/11",
      "end": "09/23",
      "start_idx": 0,
      "end_idx": 8,
      "days": 9,
      "hot_days": 9,
      "peak": 8,
      "peak_date": "09/21",
      "total": 40,
      "ongoing": false
    },
    {
      "sector": "新能源车",
      "start": "09/14",
      "end": "11/05",
      "start_idx": 1,
      "end_idx": 33,
      "days": 33,
      "hot_days": 29,
      "peak": 30,
      "peak_date": "10/28",
      "total": 299,
      "ongoing": true
    },
    {
      "sector": "机器人",
      "start": "09/16",
      "end": "11/05",
      "start_idx": 3,
      "end_idx": 33,
      "days": 31,
      "hot_days": 31,
      "peak": 37,
      "peak_date": "10/23",
      "total": 541,
      "ongoing": true
    },
    {
      "sector": "白酒消费",
      "start": "09/18",
      "end": "11/05",
      "start_idx": 5,
      "end_idx": 33,
      "days": 29,
      "hot_days": 28,
      "peak": 17,
      "peak_date": "11/02",
      "total": 191,
      "ongoing": true
    },
    {
      "sector": "地产链",
      "start": "10/12",
      "end": "10/16",
      "start_idx": 15,
      "end_idx": 19,
      "days": 5,
      "hot_days": 4,
      "peak": 7,
      "peak_date": "10/14",
      "total": 19,
      "ongoing": false
    },
    {
      "sector": "通信设备",
      "start": "10/12",
      "end": "10/12",
      "start_idx": 15,
      "end_idx": 15,
      "days": 1,
      "hot_days": 1,
      "peak": 3,
      "peak_date": "10/12",
      "total": 3,
      "ongoing": false
    },
    {
      "sector": "军工",
      "start": "10/14",
      "end": "10/26",
      "start_idx": 17,
      "end_idx": 25,
      "days": 9,
      "hot_days": 7,
      "peak": 9,
      "peak_date": "10/19",
      "total": 37,
      "ongoing": false
    },
    {
      "sector": "半导体",
      "start": "10/14",
      "end": "10/26",
      "start_idx": 17,
      "end_idx": 25,
      "days": 9,
      "hot_days": 8,
      "peak": 6,
      "peak_date": "10/15",
      "total": 39,
      "ongoing": false
    },
    {
      "sector": "通信设备",
      "start": "10/21",
      "end": "11/03",
      "start_idx": 22,
      "end_idx": 31,
      "days": 10,
      "hot_days": 8,
      "peak": 4,
      "peak_date": "10/26",
      "total": 28,
      "ongoing": false
    },
    {
      "sector": "地产链",
      "start": "10/26",
      "end": "10/26",
      "start_idx": 25,
      "end_idx": 25,
      "days": 1,
      "hot_days": 1,
      "peak": 4,
      "peak_date": "10/26",
      "total": 4,
      "ongoing": false
    },
    {
      "sector": "电力",
      "start": "10/27",
      "end": "11/05",
      "start_idx": 26,
      "end_idx": 33,
      "days": 8,
      "hot_days": 7,
      "peak": 6,
      "peak_date": "11/04",
      "total": 31,
      "ongoing": true
    },
    {
      "sector": "光伏",
      "start": "11/04",
      "end": "11/05",
      "start_idx": 32,
      "end_idx": 33,
      "days": 2,
      "hot_days": 2,
      "peak": 12,
      "peak_date": "11/05",
      "total": 15,
      "ongoing": true
    },
    {
      "sector": "地产链",
      "start": "11/04",
      "end": "11/05",
      "start_idx": 32,
      "end_idx": 33,
      "days": 2,
      "hot_days": 2,
      "peak": 5,
      "peak_date": "11/05",
      "total": 9,
      "ongoing": true
    },
    {
      "sector": "半导体",
      "start": "11/05",
      "end": "11/05",
      "start_idx": 33,
      "end_idx": 33,
      "days": 1,
      "hot_days": 1,
      "peak": 10,
      "peak_date": "11/05",
      "total": 10,
      "ongoing": true
    },
    {
      "sector": "固态电池",
      "start": "11/05",
      "end": "11/05",
      "start_idx": 33,
      "end_idx": 33,
      "days": 1,
      "hot_days": 1,
      "peak": 6,
      "peak_date": "11/05",
      "total": 6,
      "ongoing": true
    }
  ]
};
