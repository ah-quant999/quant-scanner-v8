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
// 最后更新：2026-11-12 16:13:48
// ═══════════════════════════════════════════════════════════════════════

window.SECTOR_CYCLE_ARCHIVE = {
  "update_time": "2026-11-12 16:13:48",
  "version": 1,
  "source": "raw_data/limit_up_heatmap.json",
  "params": {
    "hot_min": 3,
    "cycle_gap": 3,
    "min_len": 1
  },
  "range": [
    "09/24",
    "11/12"
  ],
  "columns": 30,
  "cycle_count": 20,
  "cycles": [
    {
      "sector": "其他",
      "start": "09/24",
      "end": "11/12",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 30,
      "peak": 123,
      "peak_date": "10/14",
      "total": 1666,
      "ongoing": true
    },
    {
      "sector": "医药",
      "start": "09/24",
      "end": "11/12",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 27,
      "peak": 36,
      "peak_date": "10/08",
      "total": 301,
      "ongoing": true
    },
    {
      "sector": "半导体",
      "start": "09/24",
      "end": "09/30",
      "start_idx": 0,
      "end_idx": 3,
      "days": 4,
      "hot_days": 4,
      "peak": 5,
      "peak_date": "09/29",
      "total": 15,
      "ongoing": false
    },
    {
      "sector": "新能源车",
      "start": "09/24",
      "end": "11/12",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 26,
      "peak": 30,
      "peak_date": "10/28",
      "total": 315,
      "ongoing": true
    },
    {
      "sector": "机器人",
      "start": "09/24",
      "end": "11/12",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 29,
      "peak": 37,
      "peak_date": "10/23",
      "total": 519,
      "ongoing": true
    },
    {
      "sector": "AI算力",
      "start": "09/28",
      "end": "11/12",
      "start_idx": 1,
      "end_idx": 29,
      "days": 29,
      "hot_days": 26,
      "peak": 25,
      "peak_date": "10/26",
      "total": 230,
      "ongoing": true
    },
    {
      "sector": "消费电子",
      "start": "09/28",
      "end": "11/12",
      "start_idx": 1,
      "end_idx": 29,
      "days": 29,
      "hot_days": 29,
      "peak": 19,
      "peak_date": "11/10",
      "total": 247,
      "ongoing": true
    },
    {
      "sector": "电力",
      "start": "09/28",
      "end": "10/19",
      "start_idx": 1,
      "end_idx": 11,
      "days": 11,
      "hot_days": 11,
      "peak": 17,
      "peak_date": "10/12",
      "total": 95,
      "ongoing": false
    },
    {
      "sector": "白酒消费",
      "start": "09/28",
      "end": "11/12",
      "start_idx": 1,
      "end_idx": 29,
      "days": 29,
      "hot_days": 28,
      "peak": 17,
      "peak_date": "11/02",
      "total": 187,
      "ongoing": true
    },
    {
      "sector": "地产链",
      "start": "10/12",
      "end": "10/16",
      "start_idx": 6,
      "end_idx": 10,
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
      "start_idx": 6,
      "end_idx": 6,
      "days": 1,
      "hot_days": 1,
      "peak": 3,
      "peak_date": "10/12",
      "total": 3,
      "ongoing": false
    },
    {
      "sector": "半导体",
      "start": "10/14",
      "end": "10/26",
      "start_idx": 8,
      "end_idx": 16,
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
      "start_idx": 13,
      "end_idx": 22,
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
      "start_idx": 16,
      "end_idx": 16,
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
      "end": "11/12",
      "start_idx": 17,
      "end_idx": 29,
      "days": 13,
      "hot_days": 12,
      "peak": 6,
      "peak_date": "11/04",
      "total": 51,
      "ongoing": true
    },
    {
      "sector": "光伏",
      "start": "11/04",
      "end": "11/12",
      "start_idx": 23,
      "end_idx": 29,
      "days": 7,
      "hot_days": 7,
      "peak": 12,
      "peak_date": "11/05",
      "total": 39,
      "ongoing": true
    },
    {
      "sector": "地产链",
      "start": "11/04",
      "end": "11/11",
      "start_idx": 23,
      "end_idx": 28,
      "days": 6,
      "hot_days": 5,
      "peak": 5,
      "peak_date": "11/05",
      "total": 23,
      "ongoing": true
    },
    {
      "sector": "半导体",
      "start": "11/05",
      "end": "11/11",
      "start_idx": 24,
      "end_idx": 28,
      "days": 5,
      "hot_days": 5,
      "peak": 10,
      "peak_date": "11/05",
      "total": 31,
      "ongoing": true
    },
    {
      "sector": "固态电池",
      "start": "11/05",
      "end": "11/10",
      "start_idx": 24,
      "end_idx": 27,
      "days": 4,
      "hot_days": 2,
      "peak": 6,
      "peak_date": "11/05",
      "total": 12,
      "ongoing": false
    },
    {
      "sector": "通信设备",
      "start": "11/11",
      "end": "11/12",
      "start_idx": 28,
      "end_idx": 29,
      "days": 2,
      "hot_days": 2,
      "peak": 6,
      "peak_date": "11/12",
      "total": 10,
      "ongoing": true
    }
  ]
};
