window.BLOAT_CHECK = {
  "updated": "2026-08-05 12:04:06",
  "overall": "ok",
  "summary": {
    "ok": 8,
    "warn": 1,
    "fail": 0,
    "total": 9
  },
  "items": [
    {
      "name": "index.html 体积",
      "status": "ok",
      "message": "584.0 KB",
      "metric": 584.0
    },
    {
      "name": "index.html 行数",
      "status": "ok",
      "message": "9051 行",
      "metric": 9051
    },
    {
      "name": "script 标签平衡",
      "status": "ok",
      "message": "75 个 <script> 块，75 个 </script>",
      "metric": {
        "opens": 75,
        "closes": 75
      }
    },
    {
      "name": "重复 id 检查",
      "status": "ok",
      "message": "共 205 个 id，无重复",
      "metric": {
        "total": 205,
        "duplicates": 0
      }
    },
    {
      "name": "顶层重复函数",
      "status": "ok",
      "message": "顶层 function 10 个，无重复",
      "metric": {
        "total": 10,
        "duplicates": 0
      }
    },
    {
      "name": "node --check 语法闸门",
      "status": "ok",
      "message": "语法检查通过（75 个 script 块）",
      "metric": 75
    },
    {
      "name": "data/*.js 总体积",
      "status": "ok",
      "message": "55 个文件，共 3196.4 KB",
      "metric": {
        "files": 55,
        "kb": 3196.4
      }
    },
    {
      "name": "重复 window.X 注入",
      "status": "ok",
      "message": "55 个 window.X 注入，无重复",
      "metric": {
        "total": 55,
        "duplicates": 0
      }
    },
    {
      "name": "data/*.js 引用检查",
      "status": "warn",
      "message": "1 个未引用：MACRO_BRIEF.js",
      "metric": {
        "unreferenced": 1
      }
    }
  ]
};
