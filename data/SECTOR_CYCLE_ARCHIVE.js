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
// 最后更新：2026-11-25 05:35:42
// ═══════════════════════════════════════════════════════════════════════

window.SECTOR_CYCLE_ARCHIVE = {
  "update_time": "2026-11-25 05:35:42",
  "version": 1,
  "source": "raw_data/limit_up_heatmap.json",
  "params": {
    "hot_min": 3,
    "cycle_gap": 3,
    "min_len": 1
  },
  "range": [
    "10/15",
    "11/25"
  ],
  "columns": 30,
  "cycle_count": 12,
  "cycles": [
    {
      "sector": "AI算力",
      "start": "10/15",
      "end": "11/25",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 24,
      "peak": 25,
      "peak_date": "10/26",
      "total": 185,
      "ongoing": true
    },
    {
      "sector": "其他",
      "start": "10/15",
      "end": "11/25",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 30,
      "peak": 83,
      "peak_date": "11/04",
      "total": 1468,
      "ongoing": true
    },
    {
      "sector": "医药",
      "start": "10/15",
      "end": "11/19",
      "start_idx": 0,
      "end_idx": 25,
      "days": 26,
      "hot_days": 22,
      "peak": 17,
      "peak_date": "11/02",
      "total": 190,
      "ongoing": false
    },
    {
      "sector": "机器人",
      "start": "10/15",
      "end": "11/25",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 28,
      "peak": 37,
      "peak_date": "10/23",
      "total": 460,
      "ongoing": true
    },
    {
      "sector": "消费电子",
      "start": "10/15",
      "end": "11/25",
      "start_idx": 0,
      "end_idx": 29,
      "days": 30,
      "hot_days": 29,
      "peak": 19,
      "peak_date": "11/10",
      "total": 276,
      "ongoing": true
    },
    {
      "sector": "电力",
      "start": "10/15",
      "end": "10/19",
      "start_idx": 0,
      "end_idx": 2,
      "days": 3,
      "hot_days": 3,
      "peak": 7,
      "peak_date": "10/19",
      "total": 17,
      "ongoing": false
    },
    {
      "sector": "白酒消费",
      "start": "10/15",
      "end": "11/19",
      "start_idx": 0,
      "end_idx": 25,
      "days": 26,
      "hot_days": 25,
      "peak": 17,
      "peak_date": "11/02",
      "total": 172,
      "ongoing": false
    },
    {
      "sector": "新能源车",
      "start": "10/19",
      "end": "11/25",
      "start_idx": 2,
      "end_idx": 29,
      "days": 28,
      "hot_days": 25,
      "peak": 30,
      "peak_date": "10/28",
      "total": 299,
      "ongoing": true
    },
    {
      "sector": "通信设备",
      "start": "10/21",
      "end": "11/03",
      "start_idx": 4,
      "end_idx": 13,
      "days": 10,
      "hot_days": 8,
      "peak": 4,
      "peak_date": "10/26",
      "total": 28,
      "ongoing": false
    },
    {
      "sector": "电力",
      "start": "10/27",
      "end": "11/25",
      "start_idx": 8,
      "end_idx": 29,
      "days": 22,
      "hot_days": 20,
      "peak": 18,
      "peak_date": "11/17",
      "total": 129,
      "ongoing": true
    },
    {
      "sector": "通信设备",
      "start": "11/11",
      "end": "11/23",
      "start_idx": 19,
      "end_idx": 27,
      "days": 9,
      "hot_days": 5,
      "peak": 6,
      "peak_date": "11/12",
      "total": 26,
      "ongoing": false
    },
    {
      "sector": "半导体",
      "start": "11/20",
      "end": "11/20",
      "start_idx": 26,
      "end_idx": 26,
      "days": 1,
      "hot_days": 1,
      "peak": 4,
      "peak_date": "11/20",
      "total": 4,
      "ongoing": false
    }
  ]
};
