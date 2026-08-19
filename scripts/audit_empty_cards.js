#!/usr/bin/env node
/**
 * audit_empty_cards.js — 渲染审计：加载 index.html + 全部 data/*.js，
 * 找出渲染后内容为空 / "暂无数据" / "加载中…" 的卡片。
 *
 * 用法：node scripts/audit_empty_cards.js
 * 退出码：0=全绿  1=发现空卡片
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const ROOT = path.resolve(__dirname, '..');
const HTML_PATH = path.join(ROOT, 'index.html');
const DATA_DIR = path.join(ROOT, 'data');

// ---- 收集 data/*.js 内容 ----
const dataFiles = fs.readdirSync(DATA_DIR).filter(f => f.endsWith('.js'));
let dataScripts = '';
dataFiles.forEach(f => {
  try {
    dataScripts += fs.readFileSync(path.join(DATA_DIR, f), 'utf-8') + '\n';
  } catch (e) { console.error('读取失败', f, e.message); }
});

const html = fs.readFileSync(HTML_PATH, 'utf-8');

// 虚拟 console，捕获渲染期错误
const vc = new VirtualConsole();
const errors = [];
vc.on('jsdomError', e => errors.push('[jsdomError] ' + (e && e.message || e)));
vc.on('error', (...a) => errors.push('[console.error] ' + a.join(' ')));
vc.sendTo(console, { omitJSDOMErrors: true });

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  resources: 'usable',
  url: 'https://ah-quant999.github.io/quant-scanner-v8/',
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(window) {
    // 注入数据脚本
    try {
      window.eval(dataScripts);
    } catch (e) {
      errors.push('[DATA_EVAL] ' + (e && e.message || e));
    }
  }
});

const win = dom.window;
const doc = win.document;

// 等待渲染完成
setTimeout(() => {
  // ---- 1. 所有 .card 容器内容检查 ----
  const EMPTY_PATTERNS = /(加载中|暂无数据|暂无概念数据|暂无历史数据|暂无热点板块|暂无行业板块|数据暂不可用)/;
  const emptyCards = [];
  const cards = doc.querySelectorAll('.card');
  console.log(`== 共 ${cards.length} 个 .card 容器 ==`);
  cards.forEach((card, i) => {
    const h = card.querySelector('h3');
    const title = h ? h.textContent.replace(/\s+/g, ' ').slice(0, 70) : '(无标题)';
    const inner = card.innerHTML;
    // 找内容主体区域（排除 h3 标题）
    const bodyHTML = inner.replace(/<h3[\s\S]*?<\/h3>/, '');
    const text = bodyHTML.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    const hasEmptyMark = EMPTY_PATTERNS.test(bodyHTML);
    // 判断内容是否过短（基本没有实际内容）
    const dataLen = bodyHTML.length;
    const isEmpty = hasEmptyMark || (text.length < 2 && dataLen < 400);
    if (isEmpty) {
      const mark = hasEmptyMark ? bodyHTML.match(EMPTY_PATTERNS)[0] : '内容过短';
      emptyCards.push({ i, title, mark, dataLen });
      console.log(`❌ 卡片#${i} [${mark}] ${title} (bodyLen=${dataLen})`);
    }
  });

  // ---- 2. 全部 innerHTML 含"加载中…"的容器 ----
  console.log('\n== 含"加载中…"的容器 ==');
  let loadingCnt = 0;
  doc.querySelectorAll('[id]').forEach(el => {
    if (/加载中/.test(el.innerHTML)) {
      loadingCnt++;
      const h = el.closest('.card');
      const t = h && h.querySelector('h3');
      console.log(`   ⏳ id=${el.id} ${t ? '→ '+t.textContent.replace(/\s+/g,' ').slice(0,50) : ''}`);
    }
  });
  console.log(`   共 ${loadingCnt} 处`);

  // ---- 3. 渲染期错误 ----
  console.log('\n== 渲染期错误 ==');
  const realErrors = errors.filter(e => !/Could not load|Not implemented|resource/.test(e));
  if (realErrors.length) realErrors.forEach(e => console.log('   ❌ ' + e.slice(0, 200)));
  else console.log('   ✅ 无渲染期错误');

  // ---- 4. 关键全局数据是否存在 ----
  console.log('\n== 关键数据全局变量 ==');
  const keys = ['INDEX_QUOTES','ETF_PULSE','SECTOR_FUND_FLOW','CONCEPT_RANKING','LHB_DATA',
    'SH_FIB','CANDIDATE','GOLD_POOL','TRIPLE_CONSENSUS','FINAL_RECOMMEND_DATA','COCKPIT_ADVICE',
    'STOCK_RPS','MAHORO','CRDS_CARD_DATA','FOUR_VOLUME','SECTOR_RS','MARKET_FUND_FLOW_DATA',
    'ETF_INTRADAY_HEAT','LIMIT_UP_HEATMAP','AI_MARKET_BRIEF','STOCK_QUOTE','HEALTH_CHECK'];
  keys.forEach(k => {
    const v = win[k];
    const ok = !!(v && (Object.keys(v).length || (v.stocks && v.stocks.length)));
    console.log(`   ${ok ? '✅' : '❌'} ${k} ${v ? '' : '(undefined)'}`);
  });

  console.log(`\n== 空卡片汇总: ${emptyCards.length} ==`);
  process.exit(emptyCards.length ? 1 : 0);
}, 3000);
