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
// 最后更新：2026-10-16 23:28:23
// ═══════════════════════════════════════════════════════════════════════

window.SECTOR_CYCLE_ARCHIVE = {
  "update_time": "2026-10-16 23:28:23",
  "version": 1,
  "source": "raw_data/limit_up_heatmap.json",
  "params": {
    "hot_min": 3,
    "cycle_gap": 3,
    "min_len": 1
  },
  "range": [
    "08/25",
    "10/16"
  ],
  "columns": 33,
  "cycle_count": 20,
  "cycles": [
    {
      "sector": "AI算力",
      "start": "08/25",
      "end": "10/16",
      "start_idx": 0,
      "end_idx": 32,
      "days": 33,
      "hot_days": 31,
      "peak": 28,
      "peak_date": "09/22",
      "total": 347,
      "ongoing": true
    },
    {
      "sector": "其他",
      "start": "08/25",
      "end": "10/16",
      "start_idx": 0,
      "end_idx": 32,
      "days": 33,
      "hot_days": 33,
      "peak": 296,
      "peak_date": "09/01",
      "total": 3374,
      "ongoing": true
    },
    {
      "sector": "医药",
      "start": "08/25",
      "end": "10/16",
      "start_idx": 0,
      "end_idx": 32,
      "days": 33,
      "hot_days": 33,
      "peak": 47,
      "peak_date": "09/22",
      "total": 538,
      "ongoing": true
    },
    {
      "sector": "新能源车",
      "start": "08/25",
      "end": "10/14",
      "start_idx": 0,
      "end_idx": 30,
      "days": 31,
      "hot_days": 27,
      "peak": 20,
      "peak_date": "09/01",
      "total": 239,
      "ongoing": false
    },
    {
      "sector": "机器人",
      "start": "08/25",
      "end": "09/10",
      "start_idx": 0,
      "end_idx": 12,
      "days": 13,
      "hot_days": 13,
      "peak": 27,
      "peak_date": "09/03",
      "total": 213,
      "ongoing": false
    },
    {
      "sector": "消费电子",
      "start": "08/25",
      "end": "10/16",
      "start_idx": 0,
      "end_idx": 32,
      "days": 33,
      "hot_days": 31,
      "peak": 27,
      "peak_date": "09/21",
      "total": 270,
      "ongoing": true
    },
    {
      "sector": "白酒消费",
      "start": "08/25",
      "end": "09/10",
      "start_idx": 0,
      "end_idx": 12,
      "days": 13,
      "hot_days": 12,
      "peak": 33,
      "peak_date": "09/08",
      "total": 158,
      "ongoing": false
    },
    {
      "sector": "通信设备",
      "start": "08/25",
      "end": "08/25",
      "start_idx": 0,
      "end_idx": 0,
      "days": 1,
      "hot_days": 1,
      "peak": 3,
      "peak_date": "08/25",
      "total": 3,
      "ongoing": false
    },
    {
      "sector": "电力",
      "start": "08/28",
      "end": "10/16",
      "start_idx": 3,
      "end_idx": 32,
      "days": 30,
      "hot_days": 29,
      "peak": 17,
      "peak_date": "10/12",
      "total": 223,
      "ongoing": true
    },
    {
      "sector": "通信设备",
      "start": "08/31",
      "end": "09/23",
      "start_idx": 4,
      "end_idx": 21,
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
      "start_idx": 5,
      "end_idx": 5,
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
      "start_idx": 10,
      "end_idx": 25,
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
      "end": "10/12",
      "start_idx": 15,
      "end_idx": 28,
      "days": 14,
      "hot_days": 13,
      "peak": 9,
      "peak_date": "10/12",
      "total": 65,
      "ongoing": false
    },
    {
      "sector": "机器人",
      "start": "09/16",
      "end": "10/16",
      "start_idx": 16,
      "end_idx": 32,
      "days": 17,
      "hot_days": 17,
      "peak": 32,
      "peak_date": "09/22",
      "total": 241,
      "ongoing": true
    },
    {
      "sector": "白酒消费",
      "start": "09/18",
      "end": "10/16",
      "start_idx": 18,
      "end_idx": 32,
      "days": 15,
      "hot_days": 14,
      "peak": 9,
      "peak_date": "09/23",
      "total": 80,
      "ongoing": true
    },
    {
      "sector": "固态电池",
      "start": "10/12",
      "end": "10/16",
      "start_idx": 28,
      "end_idx": 32,
      "days": 5,
      "hot_days": 4,
      "peak": 7,
      "peak_date": "10/12",
      "total": 19,
      "ongoing": true
    },
    {
      "sector": "地产链",
      "start": "10/12",
      "end": "10/16",
      "start_idx": 28,
      "end_idx": 32,
      "days": 5,
      "hot_days": 4,
      "peak": 7,
      "peak_date": "10/14",
      "total": 19,
      "ongoing": true
    },
    {
      "sector": "通信设备",
      "start": "10/12",
      "end": "10/12",
      "start_idx": 28,
      "end_idx": 28,
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
      "end": "10/16",
      "start_idx": 30,
      "end_idx": 32,
      "days": 3,
      "hot_days": 2,
      "peak": 7,
      "peak_date": "10/16",
      "total": 10,
      "ongoing": true
    },
    {
      "sector": "半导体",
      "start": "10/14",
      "end": "10/16",
      "start_idx": 30,
      "end_idx": 32,
      "days": 3,
      "hot_days": 3,
      "peak": 6,
      "peak_date": "10/15",
      "total": 15,
      "ongoing": true
    }
  ]
};
