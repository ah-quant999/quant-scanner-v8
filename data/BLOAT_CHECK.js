window.BLOAT_CHECK = {
  "updated": "2026-08-05 12:57:57",
  "overall": "ok",
  "summary": {
    "ok": 9,
    "warn": 0,
    "fail": 0,
    "total": 9
  },
  "items": [
    {
      "name": "index.html 体积",
      "status": "ok",
      "message": "582.9 KB",
      "metric": 582.9
    },
    {
      "name": "index.html 行数",
      "status": "ok",
      "message": "9075 行",
      "metric": 9075
    },
    {
      "name": "script 标签平衡",
      "status": "ok",
      "message": "77 个 <script> 块，77 个 </script>",
      "metric": {
        "opens": 77,
        "closes": 77
      }
    },
    {
      "name": "重复 id 检查",
      "status": "ok",
      "message": "共 208 个 id，无重复",
      "metric": {
        "total": 208,
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
      "message": "语法检查通过（77 个 script 块）",
      "metric": 77
    },
    {
      "name": "data/*.js 总体积",
      "status": "ok",
      "message": "55 个文件，共 3196.5 KB",
      "metric": {
        "files": 55,
        "kb": 3196.5
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
      "status": "ok",
      "message": "全部已引用",
      "metric": {
        "unreferenced": 0
      }
    }
  ]
};
