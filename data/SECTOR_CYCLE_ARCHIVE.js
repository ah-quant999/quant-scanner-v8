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
// 最后更新：2026-10-09 14:45:19
// ═══════════════════════════════════════════════════════════════════════

window.SECTOR_CYCLE_ARCHIVE = {
  "update_time": "2026-10-09 14:45:19",
  "version": 1,
  "source": "raw_data/limit_up_heatmap.json",
  "params": {
    "hot_min": 3,
    "cycle_gap": 3,
    "min_len": 1
  },
  "range": [
    "08/21",
    "10/09"
  ],
  "columns": 30,
  "cycle_count": 17,
  "cycles": [
    {
      "sector": "其他",
      "start": "08/21",
      "end": "10/09",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 30,
      "peak": 296,
      "peak_date": "09/01",
      "total": 3099,
      "ongoing": true
    },
    {
      "sector": "医药",
      "start": "08/21",
      "end": "10/09",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 30,
      "peak": 47,
      "peak_date": "09/22",
      "total": 539,
      "ongoing": true
    },
    {
      "sector": "半导体",
      "start": "08/21",
      "end": "08/21",
      "start_idx": 0,
      "end_idx": 0,
      "days": 1,
      "hot_days": 1,
      "peak": 3,
      "peak_date": "08/21",
      "total": 3,
      "ongoing": false
    },
    {
      "sector": "机器人",
      "start": "08/21",
      "end": "09/10",
      "start_idx": 0,
      "end_idx": 14,
      "days": 15,
      "hot_days": 15,
      "peak": 27,
      "peak_date": "09/03",
      "total": 229,
      "ongoing": false
    },
    {
      "sector": "消费电子",
      "start": "08/21",
      "end": "10/09",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 27,
      "peak": 27,
      "peak_date": "09/21",
      "total": 256,
      "ongoing": true
    },
    {
      "sector": "电力",
      "start": "08/21",
      "end": "08/24",
      "start_idx": 0,
      "end_idx": 1,
      "days": 2,
      "hot_days": 2,
      "peak": 5,
      "peak_date": "08/21",
      "total": 8,
      "ongoing": false
    },
    {
      "sector": "白酒消费",
      "start": "08/21",
      "end": "09/10",
      "start_idx": 0,
      "end_idx": 14,
      "days": 15,
      "hot_days": 14,
      "peak": 33,
      "peak_date": "09/08",
      "total": 166,
      "ongoing": false
    },
    {
      "sector": "通信设备",
      "start": "08/21",
      "end": "08/25",
      "start_idx": 0,
      "end_idx": 2,
      "days": 3,
      "hot_days": 3,
      "peak": 4,
      "peak_date": "08/24",
      "total": 10,
      "ongoing": false
    },
    {
      "sector": "AI算力",
      "start": "08/25",
      "end": "10/09",
      "start_idx": 2,
      "end_idx": 29,
      "days": 28,
      "hot_days": 26,
      "peak": 28,
      "peak_date": "09/22",
      "total": 302,
      "ongoing": true
    },
    {
      "sector": "新能源车",
      "start": "08/25",
      "end": "10/09",
      "start_idx": 2,
      "end_idx": 29,
      "days": 28,
      "hot_days": 25,
      "peak": 20,
      "peak_date": "09/01",
      "total": 231,
      "ongoing": true
    },
    {
      "sector": "电力",
      "start": "08/28",
      "end": "10/09",
      "start_idx": 5,
      "end_idx": 29,
      "days": 25,
      "hot_days": 24,
      "peak": 13,
      "peak_date": "10/09",
      "total": 179,
      "ongoing": true
    },
    {
      "sector": "通信设备",
      "start": "08/31",
      "end": "09/23",
      "start_idx": 6,
      "end_idx": 23,
      "days": 18,
      "hot_days": 18,
      "peak": 8,
      "peak_date": "09/02",
      "total": 86,
      "ongoing": false
    },
    {
      "sector": "半导体",
      "start": "09/01",
      "end": "09/01",
      "start_idx": 7,
      "end_idx": 7,
      "days": 1,
      "hot_days": 1,
      "peak": 4,
      "peak_date": "09/01",
      "total": 4,
      "ongoing": false
    },
    {
      "sector": "半导体",
      "start": "09/08",
      "end": "09/30",
      "start_idx": 12,
      "end_idx": 27,
      "days": 16,
      "hot_days": 16,
      "peak": 21,
      "peak_date": "09/22",
      "total": 157,
      "ongoing": false
    },
    {
      "sector": "光伏",
      "start": "09/15",
      "end": "10/08",
      "start_idx": 17,
      "end_idx": 28,
      "days": 12,
      "hot_days": 12,
      "peak": 7,
      "peak_date": "09/29",
      "total": 55,
      "ongoing": true
    },
    {
      "sector": "机器人",
      "start": "09/16",
      "end": "10/09",
      "start_idx": 18,
      "end_idx": 29,
      "days": 12,
      "hot_days": 12,
      "peak": 32,
      "peak_date": "09/22",
      "total": 190,
      "ongoing": true
    },
    {
      "sector": "白酒消费",
      "start": "09/18",
      "end": "10/09",
      "start_idx": 20,
      "end_idx": 29,
      "days": 10,
      "hot_days": 9,
      "peak": 9,
      "peak_date": "09/23",
      "total": 58,
      "ongoing": true
    }
  ]
};
