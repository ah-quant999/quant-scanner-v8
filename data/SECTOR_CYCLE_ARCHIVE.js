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
// 最后更新：2026-09-22 10:39:39
// ═══════════════════════════════════════════════════════════════════════

window.SECTOR_CYCLE_ARCHIVE = {
  "update_time": "2026-09-22 10:39:39",
  "version": 1,
  "source": "raw_data/limit_up_heatmap.json",
  "params": {
    "hot_min": 3,
    "cycle_gap": 3,
    "min_len": 1
  },
  "range": [
    "08/10",
    "09/22"
  ],
  "columns": 32,
  "cycle_count": 21,
  "cycles": [
    {
      "sector": "AI算力",
      "start": "08/10",
      "end": "08/19",
      "start_idx": 0,
      "end_idx": 7,
      "days": 8,
      "hot_days": 8,
      "peak": 9,
      "peak_date": "08/13",
      "total": 56,
      "ongoing": false
    },
    {
      "sector": "其他",
      "start": "08/10",
      "end": "09/22",
      "start_idx": 0,
      "end_idx": 31,
      "days": 32,
      "hot_days": 32,
      "peak": 296,
      "peak_date": "09/01",
      "total": 3086,
      "ongoing": true
    },
    {
      "sector": "军工",
      "start": "08/10",
      "end": "08/11",
      "start_idx": 0,
      "end_idx": 1,
      "days": 2,
      "hot_days": 2,
      "peak": 5,
      "peak_date": "08/10",
      "total": 8,
      "ongoing": false
    },
    {
      "sector": "医药",
      "start": "08/10",
      "end": "09/22",
      "start_idx": 0,
      "end_idx": 31,
      "days": 32,
      "hot_days": 32,
      "peak": 82,
      "peak_date": "08/20",
      "total": 802,
      "ongoing": true
    },
    {
      "sector": "半导体",
      "start": "08/10",
      "end": "08/21",
      "start_idx": 0,
      "end_idx": 9,
      "days": 10,
      "hot_days": 9,
      "peak": 10,
      "peak_date": "08/10",
      "total": 52,
      "ongoing": false
    },
    {
      "sector": "机器人",
      "start": "08/10",
      "end": "09/10",
      "start_idx": 0,
      "end_idx": 23,
      "days": 24,
      "hot_days": 24,
      "peak": 27,
      "peak_date": "09/03",
      "total": 313,
      "ongoing": false
    },
    {
      "sector": "白酒消费",
      "start": "08/10",
      "end": "09/10",
      "start_idx": 0,
      "end_idx": 23,
      "days": 24,
      "hot_days": 23,
      "peak": 33,
      "peak_date": "09/08",
      "total": 248,
      "ongoing": false
    },
    {
      "sector": "通信设备",
      "start": "08/10",
      "end": "08/25",
      "start_idx": 0,
      "end_idx": 11,
      "days": 12,
      "hot_days": 11,
      "peak": 4,
      "peak_date": "08/10",
      "total": 40,
      "ongoing": false
    },
    {
      "sector": "新能源车",
      "start": "08/11",
      "end": "09/22",
      "start_idx": 1,
      "end_idx": 31,
      "days": 31,
      "hot_days": 26,
      "peak": 20,
      "peak_date": "09/01",
      "total": 208,
      "ongoing": true
    },
    {
      "sector": "电力",
      "start": "08/11",
      "end": "08/24",
      "start_idx": 1,
      "end_idx": 10,
      "days": 10,
      "hot_days": 10,
      "peak": 6,
      "peak_date": "08/19",
      "total": 42,
      "ongoing": false
    },
    {
      "sector": "消费电子",
      "start": "08/12",
      "end": "09/22",
      "start_idx": 2,
      "end_idx": 31,
      "days": 30,
      "hot_days": 24,
      "peak": 27,
      "peak_date": "09/21",
      "total": 224,
      "ongoing": true
    },
    {
      "sector": "军工",
      "start": "08/18",
      "end": "08/18",
      "start_idx": 6,
      "end_idx": 6,
      "days": 1,
      "hot_days": 1,
      "peak": 3,
      "peak_date": "08/18",
      "total": 3,
      "ongoing": false
    },
    {
      "sector": "AI算力",
      "start": "08/25",
      "end": "09/22",
      "start_idx": 11,
      "end_idx": 31,
      "days": 21,
      "hot_days": 20,
      "peak": 25,
      "peak_date": "09/01",
      "total": 228,
      "ongoing": true
    },
    {
      "sector": "军工",
      "start": "08/27",
      "end": "09/22",
      "start_idx": 13,
      "end_idx": 31,
      "days": 19,
      "hot_days": 15,
      "peak": 24,
      "peak_date": "09/09",
      "total": 105,
      "ongoing": true
    },
    {
      "sector": "电力",
      "start": "08/28",
      "end": "09/22",
      "start_idx": 14,
      "end_idx": 31,
      "days": 18,
      "hot_days": 18,
      "peak": 12,
      "peak_date": "09/09",
      "total": 129,
      "ongoing": true
    },
    {
      "sector": "通信设备",
      "start": "08/31",
      "end": "09/22",
      "start_idx": 15,
      "end_idx": 31,
      "days": 17,
      "hot_days": 17,
      "peak": 8,
      "peak_date": "09/02",
      "total": 83,
      "ongoing": true
    },
    {
      "sector": "半导体",
      "start": "09/01",
      "end": "09/01",
      "start_idx": 16,
      "end_idx": 16,
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
      "end": "09/22",
      "start_idx": 21,
      "end_idx": 31,
      "days": 11,
      "hot_days": 11,
      "peak": 21,
      "peak_date": "09/22",
      "total": 122,
      "ongoing": true
    },
    {
      "sector": "光伏",
      "start": "09/15",
      "end": "09/22",
      "start_idx": 26,
      "end_idx": 31,
      "days": 6,
      "hot_days": 6,
      "peak": 5,
      "peak_date": "09/21",
      "total": 23,
      "ongoing": true
    },
    {
      "sector": "机器人",
      "start": "09/16",
      "end": "09/22",
      "start_idx": 27,
      "end_idx": 31,
      "days": 5,
      "hot_days": 5,
      "peak": 28,
      "peak_date": "09/22",
      "total": 77,
      "ongoing": true
    },
    {
      "sector": "白酒消费",
      "start": "09/18",
      "end": "09/22",
      "start_idx": 29,
      "end_idx": 31,
      "days": 3,
      "hot_days": 3,
      "peak": 5,
      "peak_date": "09/22",
      "total": 13,
      "ongoing": true
    }
  ]
};
