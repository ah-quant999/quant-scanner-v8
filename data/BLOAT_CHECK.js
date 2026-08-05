window.BLOAT_CHECK = {
  "updated": "2026-08-05 10:32:28",
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
      "message": "580.9 KB",
      "metric": 580.9
    },
    {
      "name": "index.html 行数",
      "status": "ok",
      "message": "9018 行",
      "metric": 9018
    },
    {
      "name": "script 标签平衡",
      "status": "ok",
      "message": "76 个 <script> 块，76 个 </script>",
      "metric": {
        "opens": 76,
        "closes": 76
      }
    },
    {
      "name": "重复 id 检查",
      "status": "ok",
      "message": "共 207 个 id，无重复",
      "metric": {
        "total": 207,
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
      "message": "语法检查通过（76 个 script 块）",
      "metric": 76
    },
    {
      "name": "data/*.js 总体积",
      "status": "ok",
      "message": "55 个文件，共 3197.4 KB",
      "metric": {
        "files": 55,
        "kb": 3197.4
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
