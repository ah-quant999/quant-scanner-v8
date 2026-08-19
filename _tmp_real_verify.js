#!/usr/bin/env node
// 真实渲染验证：跑 renderSfIntradayChart() + _fillCommodityElasticity()，
// 把 innerHTML dump 出来给主人看，不再 PASS/FAIL 敷衍。
//
// 用 node vm sandbox 加载本地 index.html + data/*.js，
// 覆盖关键渲染函数，让两个 defer 数据对象可见，
// 然后调用渲染函数，dump ceBody/sfIntradayChart 真实 innerHTML。

const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = 'E:/workspace/quant-scanner-v8';

// 1. mock Date
const FAKE_NOW_CST = '2026-08-19T10:35:00+08:00';
const _RealDate = Date;
function FakeDate(...args) {
  if (args.length === 0) return new _RealDate(FAKE_NOW_CST);
  return new _RealDate(...args);
}
FakeDate.now = () => new _RealDate(FAKE_NOW_CST).getTime();
FakeDate.parse = _RealDate.parse;
FakeDate.UTC = _RealDate.UTC;
FakeDate.prototype = _RealDate.prototype;

// 2. mock DOM
function makeEl(tag) {
  return {
    tagName: tag || 'div',
    id: '', className: '',
    innerHTML: '', textContent: '', value: '', style: {}, dataset: {},
    children: [],
    appendChild(c) { this.children.push(c); c.parent = this; return c; },
    setAttribute(k, v) { this[k] = v; },
    querySelector() { return makeEl('span'); },
    querySelectorAll() { return []; },
    addEventListener() {},
    removeEventListener() {},
    classList: { add() {}, remove() {}, contains() { return false; } },
    getBoundingClientRect() { return { width: 600, height: 300, top: 0, left: 0 }; },
    parentNode: null,
    dispose() {},
  };
}
const _elCache = {};
const document = {
  getElementById(id) { if (!_elCache[id]) _elCache[id] = makeEl('div'); return _elCache[id]; },
  createElement(t) { return makeEl(t); },
  createTextNode(s) { return { nodeType: 3, textContent: s }; },
  body: makeEl('body'),
  documentElement: makeEl('html'),
  querySelector() { return null; },
  querySelectorAll() { return []; },
  addEventListener() {},
  readyState: 'complete',
};
const localStorage = { _: {}, getItem(k) { return this._[k] || null; }, setItem(k, v) { this._[k] = v; }, removeItem(k) { delete this._[k]; } };
const $ = (id) => document.getElementById(id);

// 3. mock echarts（避免 import 失败）
const echarts = { init: () => ({ setOption() {}, dispose() {}, resize() {} }) };

// 4. 沙箱
const sandbox = { document, localStorage, $, console,
  setTimeout, clearTimeout, setInterval, clearInterval,
  Date: FakeDate, _RealDate,
  parseInt, parseFloat, isNaN, isFinite, Math, JSON, Array, Object, String, Number, Boolean,
  RegExp, Error, URL, Symbol, Map, Set, Promise,
  fetch: () => Promise.reject(new Error('no fetch')),
  requestAnimationFrame: (cb) => setTimeout(cb, 16),
  echarts, window: null, globalThis: null, self: null,
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
sandbox.self = sandbox;
// mock 文件级 var（vm 沙箱拿不到 index.html 里的 var 声明）
sandbox._SF_INTRADAY_CHART = null;
sandbox._MFF_RESIZE_HANDLERS = [];
sandbox._secPhCharts = [];
const ctx = vm.createContext(sandbox);

// 5. load data/*.js
const dataDir = path.join(ROOT, 'data');
const dataFiles = fs.readdirSync(dataDir).filter(f => f.endsWith('.js'));
for (const f of dataFiles) {
  try {
    const text = fs.readFileSync(path.join(dataDir, f), 'utf8');
    new vm.Script(text, { filename: f }).runInContext(ctx);
  } catch (e) { /* ignore */ }
}
console.log('--- data/*.js 加载完成 ---');
console.log('window.SECTOR_FUND_FLOW_INTRADAY:', JSON.stringify(sandbox.SECTOR_FUND_FLOW_INTRADAY ? {date: sandbox.SECTOR_FUND_FLOW_INTRADAY.date, snap_count: (sandbox.SECTOR_FUND_FLOW_INTRADAY.snapshots||[]).length, times: (sandbox.SECTOR_FUND_FLOW_INTRADAY.snapshots||[]).map(s=>s.time)} : null));
console.log('window.COMMODITY_ELASTICITY:', sandbox.COMMODITY_ELASTICITY ? `有 (update_time=${sandbox.COMMODITY_ELASTICITY.update_time}, commodities=${(sandbox.COMMODITY_ELASTICITY.commodities||[]).length})` : '无');

// 6. load index.html 关键函数（grep function NAME 起始 → 数 {} 找结束）
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');

function findFnCode(name) {
  // 三种形式：function NAME / window.NAME = function / var NAME = function
  const pats = [
    { re: new RegExp('function\\s+' + name + '\\s*\\(', 'g'), mode: 'decl' },
    { re: new RegExp('window\\.' + name + '\\s*=\\s*function', 'g'), mode: 'assign' },
    { re: new RegExp('var\\s+' + name + '\\s*=\\s*function', 'g'), mode: 'varassign' },
  ];
  for (const { re, mode } of pats) {
    re.lastIndex = 0;
    const m = re.exec(html);
    if (!m) continue;
    let start;
    if (mode === 'decl') {
      start = m.index;
    } else {
      const sub = html.slice(m.index);
      const fnKw = sub.indexOf('function');
      if (fnKw < 0) continue;
      start = m.index + fnKw;
    }
    let depth = 0;
    for (let i = start; i < html.length; i++) {
      if (html[i] === '{') depth++;
      else if (html[i] === '}') { depth--; if (depth === 0) return html.slice(start, i + 1); }
    }
  }
  return null;
}

const wantFns = ['_fillCommodityElasticity', 'renderSfIntradayChart', '_uBadge'];
let loaded = 0;
for (const name of wantFns) {
  const code = findFnCode(name);
  if (!code) { console.log(`[load] ⚠️ ${name}: not found in html`); continue; }
  let wrap;
  if (/^function\s+\w+/.test(code)) {
    const m = code.match(/^function\s+(\w+)/);
    const actualName = m ? m[1] : name;
    wrap = code + `\n;try{window.${actualName} = ${actualName};}catch(e){}`;
  } else {
    const alias = '__fn_' + name;
    wrap = `var ${alias} = ${code};\n;try{window.${name} = ${alias};}catch(e){}`;
  }
  try {
    new vm.Script(wrap, { filename: 'fn:' + name }).runInContext(ctx);
    loaded++;
    console.log(`[load] ✅ ${name}`);
  } catch (e) { console.log(`[load] ❌ ${name}: ${e.message.substring(0, 200)}`); }
}
console.log(`--- 加载 ${loaded} 个渲染函数 ---`);

// 7. 真实跑 + dump
console.log('\n=== 真实渲染验证 ===\n');

// (a) SECTOR_FUND_FLOW_INTRADAY
if (typeof sandbox.renderSfIntradayChart === 'function') {
  console.log('--- renderSfIntradayChart() 调用前 ---');
  const beforeChart = document.getElementById('sfIntradayChart').innerHTML;
  const beforeTime = document.getElementById('sfIntradayTime').innerHTML;
  console.log('  sfIntradayChart.innerHTML:', JSON.stringify(beforeChart.substring(0, 200)));
  console.log('  sfIntradayTime.innerHTML:', JSON.stringify(beforeTime));
  try {
    sandbox.renderSfIntradayChart();
    console.log('  ✅ renderSfIntradayChart() 调用成功');
    const afterChart = document.getElementById('sfIntradayChart').innerHTML;
    const afterTime = document.getElementById('sfIntradayTime').innerHTML;
    console.log('  sfIntradayChart.innerHTML 长度:', afterChart.length);
    console.log('  sfIntradayChart.innerHTML 头 200:', JSON.stringify(afterChart.substring(0, 200)));
    console.log('  sfIntradayTime.innerHTML:', JSON.stringify(afterTime));
  } catch (e) {
    console.log('  ❌ renderSfIntradayChart() 抛错:', e.message.substring(0, 300));
  }
}

// (b) COMMODITY_ELASTICITY
if (typeof sandbox._fillCommodityElasticity === 'function') {
  console.log('\n--- _fillCommodityElasticity() 调用前 ---');
  const beforeCE = document.getElementById('ceBody').innerHTML;
  const beforeFresh = document.getElementById('prCEFresh').innerHTML;
  console.log('  ceBody.innerHTML:', JSON.stringify(beforeCE.substring(0, 200)));
  console.log('  prCEFresh.innerHTML:', JSON.stringify(beforeFresh));
  try {
    sandbox._fillCommodityElasticity();
    console.log('  ✅ _fillCommodityElasticity() 调用成功');
    const afterCE = document.getElementById('ceBody').innerHTML;
    const afterFresh = document.getElementById('prCEFresh').innerHTML;
    console.log('  ceBody.innerHTML 长度:', afterCE.length);
    console.log('  ceBody.innerHTML 头 400:', JSON.stringify(afterCE.substring(0, 400)));
    console.log('  prCEFresh.innerHTML:', JSON.stringify(afterFresh));
    // 关键检查：是否还显示"加载中…"
    if (afterCE.includes('加载中')) {
      console.log('  ❌ ceBody 仍包含"加载中"，渲染失败');
    } else if (afterCE.includes('数据不可用')) {
      console.log('  ⚠️ ceBody 显示"数据不可用"');
    } else {
      console.log('  ✅ ceBody 已渲染为真实内容（含商品卡片）');
    }
  } catch (e) {
    console.log('  ❌ _fillCommodityElasticity() 抛错:', e.message.substring(0, 300));
  }
}

console.log('\n=== 验证完成 ===');