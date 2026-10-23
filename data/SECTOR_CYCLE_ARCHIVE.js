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
// 最后更新：2026-10-23 19:29:02
// ═══════════════════════════════════════════════════════════════════════

window.SECTOR_CYCLE_ARCHIVE = {
  "update_time": "2026-10-23 19:29:02",
  "version": 1,
  "source": "raw_data/limit_up_heatmap.json",
  "params": {
    "hot_min": 3,
    "cycle_gap": 3,
    "min_len": 1
  },
  "range": [
    "09/04",
    "10/23"
  ],
  "columns": 30,
  "cycle_count": 18,
  "cycles": [
    {
      "sector": "AI算力",
      "start": "09/04",
      "end": "10/23",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 28,
      "peak": 28,
      "peak_date": "09/22",
      "total": 319,
      "ongoing": true
    },
    {
      "sector": "其他",
      "start": "09/04",
      "end": "10/23",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 30,
      "peak": 236,
      "peak_date": "09/08",
      "total": 2403,
      "ongoing": true
    },
    {
      "sector": "医药",
      "start": "09/04",
      "end": "10/23",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 29,
      "peak": 47,
      "peak_date": "09/22",
      "total": 405,
      "ongoing": true
    },
    {
      "sector": "新能源车",
      "start": "09/04",
      "end": "10/23",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 24,
      "peak": 17,
      "peak_date": "09/21",
      "total": 227,
      "ongoing": true
    },
    {
      "sector": "机器人",
      "start": "09/04",
      "end": "09/10",
      "start_idx": 0,
      "end_idx": 4,
      "days": 5,
      "hot_days": 5,
      "peak": 17,
      "peak_date": "09/08",
      "total": 62,
      "ongoing": false
    },
    {
      "sector": "消费电子",
      "start": "09/04",
      "end": "10/23",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 28,
      "peak": 27,
      "peak_date": "09/21",
      "total": 245,
      "ongoing": true
    },
    {
      "sector": "电力",
      "start": "09/04",
      "end": "10/19",
      "start_idx": 0,
      "end_idx": 25,
      "days": 26,
      "hot_days": 25,
      "peak": 17,
      "peak_date": "10/12",
      "total": 198,
      "ongoing": false
    },
    {
      "sector": "白酒消费",
      "start": "09/04",
      "end": "09/10",
      "start_idx": 0,
      "end_idx": 4,
      "days": 5,
      "hot_days": 5,
      "peak": 33,
      "peak_date": "09/08",
      "total": 84,
      "ongoing": false
    },
    {
      "sector": "通信设备",
      "start": "09/04",
      "end": "09/23",
      "start_idx": 0,
      "end_idx": 13,
      "days": 14,
      "hot_days": 14,
      "peak": 8,
      "peak_date": "09/21",
      "total": 61,
      "ongoing": false
    },
    {
      "sector": "半导体",
      "start": "09/08",
      "end": "09/30",
      "start_idx": 2,
      "end_idx": 17,
      "days": 16,
      "hot_days": 16,
      "peak": 21,
      "peak_date": "09/22",
      "total": 157,
      "ongoing": false
    },
    {
      "sector": "机器人",
      "start": "09/16",
      "end": "10/23",
      "start_idx": 8,
      "end_idx": 29,
      "days": 22,
      "hot_days": 22,
      "peak": 37,
      "peak_date": "10/23",
      "total": 339,
      "ongoing": true
    },
    {
      "sector": "白酒消费",
      "start": "09/18",
      "end": "10/23",
      "start_idx": 10,
      "end_idx": 29,
      "days": 20,
      "hot_days": 19,
      "peak": 9,
      "peak_date": "09/23",
      "total": 107,
      "ongoing": true
    },
    {
      "sector": "固态电池",
      "start": "10/12",
      "end": "10/16",
      "start_idx": 20,
      "end_idx": 24,
      "days": 5,
      "hot_days": 4,
      "peak": 7,
      "peak_date": "10/12",
      "total": 19,
      "ongoing": false
    },
    {
      "sector": "地产链",
      "start": "10/12",
      "end": "10/16",
      "start_idx": 20,
      "end_idx": 24,
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
      "start_idx": 20,
      "end_idx": 20,
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
      "end": "10/23",
      "start_idx": 22,
      "end_idx": 29,
      "days": 8,
      "hot_days": 6,
      "peak": 9,
      "peak_date": "10/19",
      "total": 31,
      "ongoing": true
    },
    {
      "sector": "半导体",
      "start": "10/14",
      "end": "10/23",
      "start_idx": 22,
      "end_idx": 29,
      "days": 8,
      "hot_days": 7,
      "peak": 6,
      "peak_date": "10/15",
      "total": 35,
      "ongoing": true
    },
    {
      "sector": "通信设备",
      "start": "10/21",
      "end": "10/23",
      "start_idx": 27,
      "end_idx": 29,
      "days": 3,
      "hot_days": 3,
      "peak": 3,
      "peak_date": "10/21",
      "total": 9,
      "ongoing": true
    }
  ]
};
