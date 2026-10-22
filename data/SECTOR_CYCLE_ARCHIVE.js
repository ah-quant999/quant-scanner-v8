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
// 最后更新：2026-10-22 10:16:28
// ═══════════════════════════════════════════════════════════════════════

window.SECTOR_CYCLE_ARCHIVE = {
  "update_time": "2026-10-22 10:16:28",
  "version": 1,
  "source": "raw_data/limit_up_heatmap.json",
  "params": {
    "hot_min": 3,
    "cycle_gap": 3,
    "min_len": 1
  },
  "range": [
    "09/03",
    "10/22"
  ],
  "columns": 30,
  "cycle_count": 18,
  "cycles": [
    {
      "sector": "AI算力",
      "start": "09/03",
      "end": "10/22",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 28,
      "peak": 28,
      "peak_date": "09/22",
      "total": 321,
      "ongoing": true
    },
    {
      "sector": "其他",
      "start": "09/03",
      "end": "10/22",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 30,
      "peak": 236,
      "peak_date": "09/08",
      "total": 2516,
      "ongoing": true
    },
    {
      "sector": "医药",
      "start": "09/03",
      "end": "10/22",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 29,
      "peak": 47,
      "peak_date": "09/22",
      "total": 411,
      "ongoing": true
    },
    {
      "sector": "新能源车",
      "start": "09/03",
      "end": "10/22",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 24,
      "peak": 17,
      "peak_date": "09/03",
      "total": 230,
      "ongoing": true
    },
    {
      "sector": "机器人",
      "start": "09/03",
      "end": "09/10",
      "start_idx": 0,
      "end_idx": 5,
      "days": 6,
      "hot_days": 6,
      "peak": 27,
      "peak_date": "09/03",
      "total": 89,
      "ongoing": false
    },
    {
      "sector": "消费电子",
      "start": "09/03",
      "end": "10/22",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 28,
      "peak": 27,
      "peak_date": "09/21",
      "total": 247,
      "ongoing": true
    },
    {
      "sector": "电力",
      "start": "09/03",
      "end": "10/19",
      "start_idx": 0,
      "end_idx": 26,
      "days": 27,
      "hot_days": 26,
      "peak": 17,
      "peak_date": "10/12",
      "total": 207,
      "ongoing": false
    },
    {
      "sector": "通信设备",
      "start": "09/03",
      "end": "09/23",
      "start_idx": 0,
      "end_idx": 14,
      "days": 15,
      "hot_days": 15,
      "peak": 8,
      "peak_date": "09/21",
      "total": 68,
      "ongoing": false
    },
    {
      "sector": "白酒消费",
      "start": "09/04",
      "end": "09/10",
      "start_idx": 1,
      "end_idx": 5,
      "days": 5,
      "hot_days": 5,
      "peak": 33,
      "peak_date": "09/08",
      "total": 84,
      "ongoing": false
    },
    {
      "sector": "半导体",
      "start": "09/08",
      "end": "09/30",
      "start_idx": 3,
      "end_idx": 18,
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
      "end": "10/22",
      "start_idx": 9,
      "end_idx": 29,
      "days": 21,
      "hot_days": 21,
      "peak": 32,
      "peak_date": "09/22",
      "total": 297,
      "ongoing": true
    },
    {
      "sector": "白酒消费",
      "start": "09/18",
      "end": "10/22",
      "start_idx": 11,
      "end_idx": 29,
      "days": 19,
      "hot_days": 18,
      "peak": 9,
      "peak_date": "09/23",
      "total": 101,
      "ongoing": true
    },
    {
      "sector": "固态电池",
      "start": "10/12",
      "end": "10/16",
      "start_idx": 21,
      "end_idx": 25,
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
      "start_idx": 21,
      "end_idx": 25,
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
      "start_idx": 21,
      "end_idx": 21,
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
      "end": "10/20",
      "start_idx": 23,
      "end_idx": 27,
      "days": 5,
      "hot_days": 4,
      "peak": 9,
      "peak_date": "10/19",
      "total": 22,
      "ongoing": false
    },
    {
      "sector": "半导体",
      "start": "10/14",
      "end": "10/22",
      "start_idx": 23,
      "end_idx": 29,
      "days": 7,
      "hot_days": 6,
      "peak": 6,
      "peak_date": "10/15",
      "total": 30,
      "ongoing": true
    },
    {
      "sector": "通信设备",
      "start": "10/21",
      "end": "10/22",
      "start_idx": 28,
      "end_idx": 29,
      "days": 2,
      "hot_days": 2,
      "peak": 3,
      "peak_date": "10/21",
      "total": 6,
      "ongoing": true
    }
  ]
};
