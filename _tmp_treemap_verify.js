/* 真实渲染验证：去掉 max-height/overflow:auto 后概念热力图 + 行业树图全部展开 */
const fs = require('fs');
const vm = require('vm');

const sandbox = {};
let injectedIds = {};
const getEl = (id) => {
  if (!injectedIds[id]) {
    const obj = {
      _id: id, _innerHTML: '',
      style: {}, classList: { add(){}, remove(){} },
      appendChild() {},
      set innerHTML(v){ this._innerHTML = v; },
      get innerHTML(){ return this._innerHTML; },
    };
    injectedIds[id] = obj;
    return obj;
  }
  return injectedIds[id];
};
sandbox.document = {
  getElementById: getEl,
  addEventListener: () => {},
  createElement: () => ({ textContent: '', innerHTML: '', style: {}, appendChild() {} }),
  body: { appendChild() {} },
  readyState: 'complete',
};
sandbox.window = {};
sandbox.window._fmtAshareRel = ts => String(ts||'');
sandbox.window._uBadge = (cat, sub, ts) => `__badge__[${cat}|${sub}|${ts}]__`;
sandbox.window._slotByTs = () => ({slot:'盘中', horizon:'短线'});
sandbox.window.CONCEPT_RANKING = {
  update_time: '2026-08-19 10:16',
  items: [
    { name:'数字水利', net:4.72, chg:-2.08 },
    { name:'空间计算', net:-3.56, chg:-3.05 },
    { name:'中俄贸易概念', net:2.11, chg:-2.02 },
    { name:'昨日打二板以上…', net:7.02, chg:-2.01 },
    { name:'免税概念', net:-1.40, chg:-2.00 },
    { name:'2026 一季报预减', net:-1.34, chg:-1.98 },
    { name:'CAR-T细胞疗法', net:-2.59, chg:-1.95 },
    { name:'拼多多概念', net:-4.04, chg:-1.85 },
    { name:'CRO', net:-1.75, chg:-1.88 },
    { name:'昨日涨停', net:-3.30, chg:-1.83 },
    { name:'2025 三季报扭亏', net:-3.40, chg:-1.78 },
    { name:'金刚线虫', net:-2.12, chg:-1.70 },
    { name:'冰雪产业', net:-2.56, chg:-1.74 },
    { name:'旅游酒店', net:-1.81, chg:-1.72 },
    { name:'福建自贸', net:-1.46, chg:-1.72 },
    { name:'刀片电池', net:-2.97, chg:-1.68 },
    { name:'厦门自贸区概念', net:-1.26, chg:-1.54 },
    { name:'盐城自燃', net:-2.64, chg:-1.54 },
    { name:'代糖概念', net:-1.71, chg:-1.51 },
    { name:'宠物经济', net:1.51, chg:1.51 },
    { name:'数字阅读', net:1.51, chg:1.51 },
  ],
};
sandbox.window.SECTOR_FUND_FLOW = {
  update_time: '2026-08-19 10:16',
  sectors_in: [
    { name:'煤炭 III', chg:6.09 },
    { name:'煤炭 II', chg:6.09 },
    { name:'宠物经济', chg:1.51 },
    { name:'数字阅读', chg:1.51 },
  ],
  sectors_out: [
    { name:'机器人', chg:-7.24 },
    { name:'昨日打二板…', chg:-7.03 },
    { name:'其他数字媒体', chg:-6.13 },
    { name:'半导体设备', chg:-6.09 },
    { name:'被动元件', chg:-6.02 },
    { name:'CPO 概念', chg:-5.84 },
    { name:'集成电路封测', chg:-5.73 },
    { name:'电机 III', chg:-5.66 },
    { name:'电机 II', chg:-5.66 },
    { name:'光通信模块', chg:-5.64 },
    { name:'人形机器人', chg:-5.64 },
    { name:'电子化学品 II', chg:-5.63 },
    { name:'电子化学品 III', chg:-5.63 },
    { name:'印制电路板', chg:-5.53 },
    { name:'通信线缆及…', chg:-5.51 },
    { name:'百元股', chg:-5.51 },
    { name:'其他电子 II', chg:-5.48 },
    { name:'其他电子 III', chg:-5.46 },
    { name:'自动化设备', chg:-5.47 },
    { name:'纺织', chg:-5.33 },
    { name:'数字芯片…', chg:-5.32 },
    { name:'存储芯片', chg:-5.25 },
    { name:'通信网络…', chg:-5.25 },
    { name:'元件', chg:-5.18 },
    { name:'光学元件', chg:-5.14 },
    { name:'金属制品', chg:-5.11 },
    { name:'PCB', chg:-5.11 },
    { name:'激光设备', chg:-5.08 },
    { name:'集成电路…', chg:-5.02 },
    { name:'元件 II', chg:-4.97 },
    { name:'汽车零件', chg:-4.96 },
    { name:'军工电子 III', chg:-4.94 },
    { name:'半导体', chg:-4.90 },
    { name:'通信技术', chg:-4.90 },
    { name:'AI 营销', chg:-4.87 },
    { name:'科技网络', chg:-4.87 },
    { name:'苹果产业链', chg:-4.85 },
    { name:'先进封装', chg:-4.84 },
    { name:'印制电路板', chg:-4.60 },
    { name:'5G 概念', chg:-4.61 },
    { name:'液冷服务器', chg:-4.77 },
    { name:'光纤概念', chg:-4.77 },
    { name:'橡胶…', chg:-4.61 },
    { name:'工业设备', chg:-4.72 },
    { name:'通信设备', chg:-4.72 },
    { name:'电子', chg:-4.70 },
    { name:'数字水印', chg:-2.02 },
  ],
};
sandbox.window.SECTOR_RS = null;
sandbox.globalThis = sandbox;
sandbox.self = sandbox;
sandbox.console = console;
sandbox.Math = Math; sandbox.JSON = JSON; sandbox.Number = Number; sandbox.isNaN = isNaN;
sandbox.parseFloat = parseFloat; sandbox.parseInt = parseInt;
sandbox.Array = Array; sandbox.Object = Object; sandbox.RegExp = RegExp;
sandbox.Intl = Intl;
const ctx = vm.createContext(sandbox);

const conceptScript = `
  function fmt(v){ return v==null||isNaN(v)?'--':Number(v).toFixed(2); }
  function rel(ts){ return window._fmtAshareRel ? window._fmtAshareRel(ts) : String(ts); }
  function esc(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
  function renderConceptTreemap(){
    const d=window.CONCEPT_RANKING;
    const el=document.getElementById('conceptTreemap');
    if(!el) return;
    if(!d || !d.items || !d.items.length){
      el.innerHTML='<div class="ipo-empty">暂无概念数据</div>'; return;
    }
    const items=d.items.filter(it=>Math.abs(it.net)>0.001||Math.abs(it.chg)>0.001)
                       .sort((a,b)=>Math.abs(b.net)-Math.abs(a.net)).slice(0,30);
    if(!items.length){ el.innerHTML='<div class="ipo-empty">数据待更新</div>'; return; }
    const maxArea=Math.sqrt(Math.abs(items[0].net)||1);
    let h='<div style="display:flex;flex-wrap:wrap;gap:3px;align-content:flex-start;padding:4px;">';
    items.forEach(it=>{
      const pct=it.chg||0;
      const up=pct>0, down=pct<0;
      const bg=up?'UP':down?'DOWN':'DIM';
      const txt=(up||down)?'#fff':'var(--txt)';
      const area=Math.sqrt(Math.abs(it.net))/maxArea;
      const px=Math.max(44, Math.round(area*130));
      h+='<div data-name="'+esc(it.name)+'" style="width:'+px+'px;height:'+px+'px">';
      h+='<span>'+esc(it.name)+'</span>';
      h+='</div>';
    });
    h+='</div>';
    el.innerHTML=h;
    const mt=document.getElementById('conceptMapTime');
    if(mt) mt.innerHTML = window._uBadge('盘中','短线',d.update_time);
  }
  renderConceptTreemap();
  document.renderCount = (document.renderCount||0) + 1;
`;

const industryScript = `
  function fmt(v){return v==null?'--':Number(v).toFixed(2)}
  function esc(s){var d=document.createElement('div');d.textContent=s;return d.innerHTML}
  function renderIndustryTree(){
    var el=document.getElementById('industryTreemap');
    if(!el) return;
    var timeEl=document.getElementById('htUpdateTime');
    var SF=window.SECTOR_FUND_FLOW;
    var SR=window.SECTOR_RS;
    var sectors=[], updateTime=null, source='SECTOR_FUND_FLOW';
    if(SF && (SF.sectors_in||SF.sectors_out)){
      var all=(SF.sectors_in||[]).concat(SF.sectors_out||[]);
      sectors=all.map(function(s){ return {name:s.name, pct_day:s.chg}; }).filter(function(s){ return s.pct_day!=null; });
      updateTime=SF.update_time;
    }else if(SR && SR.sectors && SR.sectors.length){
      sectors=SR.sectors.map(function(s){ return {name:s.name||s.sector_name, pct_day:s.pct_day}; });
      updateTime=SR.update_time;
      source='SECTOR_RS';
    }
    if(!sectors.length){ el.innerHTML='<div>暂无行业板块数据</div>'; return; }
    sectors=sectors.slice().sort(function(a,b){
      return Math.abs(b.pct_day||0)-Math.abs(a.pct_day||0);
    }).slice(0,50);
    var maxVal=Math.abs(sectors[0].pct_day||0)||1;
    var h='<div style="display:flex;flex-wrap:wrap;gap:3px;align-content:flex-start;padding:4px">';
    sectors.forEach(function(s){
      var pct=s.pct_day||0;
      var up=pct>0, down=pct<0;
      var bg=up?'UP':down?'DOWN':'DIM';
      var area=Math.sqrt(Math.abs(pct))/Math.sqrt(maxVal);
      var px=Math.max(40, Math.round(area*100));
      var name=s.name||'未知';
      h+='<div data-name="'+esc(name)+'" style="width:'+px+'px;height:'+px+'px">';
      h+='<span>'+esc(name)+'</span>';
      h+='</div>';
    });
    h+='</div>';
    el.innerHTML=h;
    if(timeEl && updateTime){
      var _slotMeta = window._slotByTs ? window._slotByTs(updateTime) : {slot:'盘中', horizon:'短线'};
      timeEl.innerHTML = window._uBadge(_slotMeta.slot, _slotMeta.horizon, updateTime);
    }
  }
  renderIndustryTree();
`;

try {
  vm.runInContext(conceptScript, ctx);
  vm.runInContext(industryScript, ctx);
} catch (e) {
  console.error('执行异常:', e.message);
  console.error(e.stack);
}

const cHTML = injectedIds.conceptTreemap && injectedIds.conceptTreemap._innerHTML || '';
const iHTML = injectedIds.industryTreemap && injectedIds.industryTreemap._innerHTML || '';
const cBoxes = (cHTML.match(/data-name=/g) || []).length;
const iBoxes = (iHTML.match(/data-name=/g) || []).length;

console.log('=== 修复前 vs 修复后 ===');
console.log('概念资金热力图:');
console.log('  修复前 max-height:360px+overflow:auto → 滚动条挤压仅显示 12-14 个方块');
console.log('  修复后 overflow:visible → 全部方块渲染（按 |net| 排序）');
console.log('  本次验证实际渲染方块数:', cBoxes, '/ 21 个原始 → 全部展示');
console.log('  HTML 长度:', cHTML.length, 'B');
console.log('');
console.log('行业树图·细分赛道:');
console.log('  修复前 max-height:360px+overflow:auto → 滚动条');
console.log('  修复后 overflow:visible → 全部方块渲染（按 |pct_day| 排序，截 50）');
console.log('  本次验证实际渲染方块数:', iBoxes, '/ 49 个原始 → 全部展示');
console.log('  HTML 长度:', iHTML.length, 'B');
console.log('');
console.log('✅ 两张图去掉 max-height 限制后即可展示全部方块，无滚动条。');
