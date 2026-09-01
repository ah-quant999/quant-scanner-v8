// 概念/行业 → 代表ETF + 龙头股 参考映射
// ⚠️ 本文件为「研究参考」用途，所列 ETF / 个股仅为该板块代表性标的，不构成任何投资建议。
// 数据由人工整理的常见 A 股板块对应关系，非实时计算；新建/更名 ETF 以交易所公告为准。
// 前端在「概念热点 / 盘中追热」面板下渲染对应参考列，并始终带风险提示。
window.CONCEPT_ETF_MAP = {
  "update_time": "2026-08-18 17:43",

  // ===== 科技 / 半导体 / AI =====
  "半导体":      { etf: { code: "512480", name: "半导体ETF" }, leaders: [{ code: "688981", name: "中芯国际" }, { code: "603501", name: "韦尔股份" }, { code: "002049", name: "紫光国微" }] },
  "半导体设备":  { etf: { code: "561980", name: "半导体设备ETF" }, leaders: [{ code: "688012", name: "中微公司" }, { code: "688041", name: "海光信息" }, { code: "002371", name: "北方华创" }] },
  "芯片":        { etf: { code: "159995", name: "芯片ETF" }, leaders: [{ code: "688981", name: "中芯国际" }, { code: "603986", name: "兆易创新" }] },
  "高带宽内存":  { etf: { code: "159665", name: "芯片ETF" }, leaders: [{ code: "002409", name: "雅克科技" }, { code: "603986", name: "兆易创新" }, { code: "688008", name: "澜起科技" }] },
  "中芯概念":    { etf: { code: "512480", name: "半导体ETF" }, leaders: [{ code: "688981", name: "中芯国际" }, { code: "603501", name: "韦尔股份" }] },
  "人工智能":    { etf: { code: "515980", name: "人工智能ETF" }, leaders: [{ code: "002230", name: "科大讯飞" }, { code: "688111", name: "金山办公" }] },
  "AI":          { etf: { code: "159819", name: "人工智能ETF" }, leaders: [{ code: "002230", name: "科大讯飞" }, { code: "300308", name: "中际旭创" }] },
  "算力":        { etf: { code: "159819", name: "人工智能ETF" }, leaders: [{ code: "300308", name: "中际旭创" }, { code: "300502", name: "新易盛" }] },
  "机器人":      { etf: { code: "562500", name: "机器人ETF" }, leaders: [{ code: "300124", name: "汇川技术" }, { code: "002472", name: "双环传动" }] },
  "人形机器人":  { etf: { code: "562500", name: "机器人ETF" }, leaders: [{ code: "002472", name: "双环传动" }, { code: "300124", name: "汇川技术" }] },
  "消费电子":    { etf: { code: "561100", name: "消费电子ETF" }, leaders: [{ code: "002475", name: "立讯精密" }, { code: "601138", name: "工业富联" }] },
  "苹果链":      { etf: { code: "561100", name: "消费电子ETF" }, leaders: [{ code: "002475", name: "立讯精密" }, { code: "300433", name: "蓝思科技" }] },
  "5G":          { etf: { code: "515050", name: "5G通信ETF" }, leaders: [{ code: "000063", name: "中兴通讯" }, { code: "300136", name: "信维通信" }] },
  "通信":        { etf: { code: "515050", name: "5G通信ETF" }, leaders: [{ code: "601728", name: "中国电信" }, { code: "600941", name: "中国移动" }] },
  "云计算":      { etf: { code: "516510", name: "云计算ETF" }, leaders: [{ code: "600588", name: "用友网络" }, { code: "000977", name: "浪潮信息" }] },
  "信创":        { etf: { code: "562570", name: "信创ETF" }, leaders: [{ code: "600536", name: "中国软件" }, { code: "688111", name: "金山办公" }] },
  "数据要素":    { etf: { code: "560800", name: "数据ETF" }, leaders: [{ code: "600602", name: "云赛智联" }, { code: "002401", name: "中远海科" }] },
  "数字经济":    { etf: { code: "560800", name: "数据ETF" }, leaders: [{ code: "600570", name: "恒生电子" }, { code: "002230", name: "科大讯飞" }] },
  "低空经济":    { etf: { code: "159692", name: "低空经济ETF" }, leaders: [{ code: "002111", name: "威海广泰" }, { code: "300699", name: "光威复材" }] },
  "商业航天":    { etf: { code: "159692", name: "航天ETF" }, leaders: [{ code: "600879", name: "航天电子" }, { code: "002025", name: "航天电器" }] },
  "工业母机":    { etf: { code: "159667", name: "工业母机ETF" }, leaders: [{ code: "300607", name: "拓斯达" }, { code: "688017", name: "绿的谐波" }] },

  // ===== 新能源 / 电池 / 汽车 =====
  "锂电池概念":  { etf: { code: "159755", name: "锂电池ETF" }, leaders: [{ code: "002594", name: "比亚迪" }, { code: "300750", name: "宁德时代" }] },
  "电池技术":    { etf: { code: "159755", name: "锂电池ETF" }, leaders: [{ code: "300750", name: "宁德时代" }, { code: "002074", name: "国轩高科" }] },
  "储能概念":    { etf: { code: "159857", name: "储能ETF" }, leaders: [{ code: "300274", name: "阳光电源" }, { code: "300750", name: "宁德时代" }] },
  "光伏":        { etf: { code: "515790", name: "光伏ETF" }, leaders: [{ code: "601012", name: "隆基绿能" }, { code: "600438", name: "通威股份" }] },
  "风电":        { etf: { code: "159861", name: "风电ETF" }, leaders: [{ code: "601615", name: "明阳智能" }, { code: "002202", name: "金风科技" }] },
  "新能源车":    { etf: { code: "515030", name: "新能源车ETF" }, leaders: [{ code: "002594", name: "比亚迪" }, { code: "300750", name: "宁德时代" }] },
  "电力设备":    { etf: { code: "159611", name: "电力ETF" }, leaders: [{ code: "300274", name: "阳光电源" }, { code: "601012", name: "隆基绿能" }] },
  "汽车":        { etf: { code: "516110", name: "汽车ETF" }, leaders: [{ code: "002594", name: "比亚迪" }, { code: "601127", name: "赛力斯" }] },
  "智能驾驶":    { etf: { code: "516110", name: "汽车ETF" }, leaders: [{ code: "002920", name: "德赛西威" }, { code: "601127", name: "赛力斯" }] },
  "稀土":        { etf: { code: "516780", name: "稀土ETF" }, leaders: [{ code: "600111", name: "北方稀土" }, { code: "000831", name: "中国稀土" }] },

  // ===== 消费 / 食品 / 医药 =====
  "食品饮料":    { etf: { code: "512690", name: "酒ETF" }, leaders: [{ code: "000858", name: "五粮液" }, { code: "600519", name: "贵州茅台" }, { code: "000568", name: "泸州老窖" }] },
  "白酒":        { etf: { code: "512690", name: "酒ETF" }, leaders: [{ code: "600519", name: "贵州茅台" }, { code: "000858", name: "五粮液" }] },
  "味蕾经济":    { etf: { code: "512690", name: "食品饮料ETF" }, leaders: [{ code: "600887", name: "伊利股份" }, { code: "603288", name: "海天味业" }, { code: "000895", name: "双汇发展" }] },
  "消费":        { etf: { code: "159928", name: "消费ETF" }, leaders: [{ code: "600519", name: "贵州茅台" }, { code: "000333", name: "美的集团" }] },
  "家电":        { etf: { code: "561120", name: "家电ETF" }, leaders: [{ code: "000333", name: "美的集团" }, { code: "000651", name: "格力电器" }] },
  "医药":        { etf: { code: "512010", name: "医药ETF" }, leaders: [{ code: "600276", name: "恒瑞医药" }, { code: "300760", name: "迈瑞医疗" }] },
  "创新药":      { etf: { code: "159992", name: "创新药ETF" }, leaders: [{ code: "600276", name: "恒瑞医药" }, { code: "002821", name: "凯莱英" }] },
  "中药":        { etf: { code: "560080", name: "中药ETF" }, leaders: [{ code: "600085", name: "同仁堂" }, { code: "000538", name: "云南白药" }] },
  "CRO":         { etf: { code: "159992", name: "创新药ETF" }, leaders: [{ code: "300347", name: "泰格医药" }, { code: "002821", name: "凯莱英" }] },
  "养殖":        { etf: { code: "159865", name: "养殖ETF" }, leaders: [{ code: "300498", name: "温氏股份" }, { code: "002714", name: "牧原股份" }] },
  "猪肉":        { etf: { code: "159865", name: "养殖ETF" }, leaders: [{ code: "002714", name: "牧原股份" }, { code: "300498", name: "温氏股份" }] },
  "农业":        { etf: { code: "159825", name: "农业ETF" }, leaders: [{ code: "002311", name: "海大集团" }, { code: "000998", name: "隆平高科" }] },
  "医美":        { etf: { code: "159992", name: "医美ETF" }, leaders: [{ code: "300896", name: "爱美客" }, { code: "600223", name: "福瑞达" }] },
  "旅游":        { etf: { code: "159766", name: "旅游ETF" }, leaders: [{ code: "601888", name: "中国中免" }, { code: "300144", name: "宋城演艺" }] },

  // ===== 金融 / 周期 / 资源 =====
  "券商":        { etf: { code: "512000", name: "券商ETF" }, leaders: [{ code: "600030", name: "中信证券" }, { code: "600837", name: "海通证券" }] },
  "银行":        { etf: { code: "512800", name: "银行ETF" }, leaders: [{ code: "601398", name: "工商银行" }, { code: "601166", name: "兴业银行" }] },
  "保险":        { etf: { code: "512070", name: "保险ETF" }, leaders: [{ code: "601318", name: "中国平安" }, { code: "601601", name: "中国太保" }] },
  "房地产":      { etf: { code: "512200", name: "房地产ETF" }, leaders: [{ code: "000002", name: "万科A" }, { code: "600048", name: "保利发展" }] },
  "有色金属":    { etf: { code: "512400", name: "有色金属ETF" }, leaders: [{ code: "603993", name: "洛阳钼业" }, { code: "600362", name: "江西铜业" }] },
  "煤炭":        { etf: { code: "515220", name: "煤炭ETF" }, leaders: [{ code: "601088", name: "中国神华" }, { code: "600188", name: "兖矿能源" }] },
  "钢铁":        { etf: { code: "515210", name: "钢铁ETF" }, leaders: [{ code: "600019", name: "宝钢股份" }, { code: "000932", name: "华菱钢铁" }] },
  "化工":        { etf: { code: "159870", name: "化工ETF" }, leaders: [{ code: "600989", name: "宝丰能源" }, { code: "002493", name: "荣盛石化" }] },
  "贵金属":      { etf: { code: "518880", name: "黄金ETF" }, leaders: [{ code: "600547", name: "山东黄金" }, { code: "601899", name: "紫金矿业" }] },
  "黄金":        { etf: { code: "518880", name: "黄金ETF" }, leaders: [{ code: "600547", name: "山东黄金" }, { code: "601899", name: "紫金矿业" }] },
  "石油":        { etf: { code: "561760", name: "石油ETF" }, leaders: [{ code: "601857", name: "中国石油" }, { code: "600028", name: "中国石化" }] },
  "天然气":      { etf: { code: "159945", name: "油气ETF" }, leaders: [{ code: "601857", name: "中国石油" }, { code: "600256", name: "广汇能源" }] },

  // ===== 军工 / 基建 / 公用 =====
  "军工":        { etf: { code: "512660", name: "军工ETF" }, leaders: [{ code: "600893", name: "航发动力" }, { code: "000768", name: "中航西飞" }] },
  "工程机械":    { etf: { code: "516970", name: "基建ETF" }, leaders: [{ code: "600031", name: "三一重工" }, { code: "000425", name: "徐工机械" }] },
  "特高压":      { etf: { code: "561160", name: "电力ETF" }, leaders: [{ code: "600406", name: "国电南瑞" }, { code: "601567", name: "三星医疗" }] },
  "电网":        { etf: { code: "561160", name: "电网ETF" }, leaders: [{ code: "600406", name: "国电南瑞" }, { code: "002028", name: "思源电气" }] },
  "环保":        { etf: { code: "159861", name: "环保ETF" }, leaders: [{ code: "300070", name: "碧水源" }, { code: "601200", name: "上海环境" }] },

  // ===== 国企 / 红利 / 宽基 =====
  "国企改革":    { etf: { code: "512950", name: "央企改革ETF" }, leaders: [{ code: "601088", name: "中国神华" }, { code: "600028", name: "中国石化" }] },
  "中特估":      { etf: { code: "512950", name: "央企ETF" }, leaders: [{ code: "601398", name: "工商银行" }, { code: "601857", name: "中国石油" }] },
  "红利":        { etf: { code: "510880", name: "红利ETF" }, leaders: [{ code: "601088", name: "中国神华" }, { code: "600900", name: "长江电力" }] },
  "宁组合":      { etf: { code: "159761", name: "新材料ETF" }, leaders: [{ code: "300750", name: "宁德时代" }, { code: "300760", name: "迈瑞医疗" }] },
  "茅指数":      { etf: { code: "510310", name: "沪深300ETF" }, leaders: [{ code: "600519", name: "贵州茅台" }, { code: "300750", name: "宁德时代" }] }
};
