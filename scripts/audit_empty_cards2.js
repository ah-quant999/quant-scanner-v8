#!/usr/bin/env node
/**
 * audit_empty_cards2.js — 渲染审计增强版：主动切换所有 tab + 触发全部渲染函数，
 * 找出最终仍为空 / "暂无数据" / "加载中…" 的卡片。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const ROOT = path.resolve(__dirname, '..');
const DATA_DIR = path.join(ROOT, 'data');

const dataFiles = fs.readdirSync(DATA_DIR).filter(f => f.endsWith('.js'));
let dataScripts = '';
dataFiles.forEach(f => dataScripts += fs.readFileSync(path.join(DATA_DIR, f), 'utf-8') + '\n');

const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf-8');

const vc = new VirtualConsole();
const errors = [];
vc.on('jsdomError', e => errors.push('[jsdomError] ' + (e && e.message || e)));
vc.on('error', (...a) => errors.push('[console.error] ' + a.join(' ')));

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  resources: 'usable',
  url: 'https://ah-quant999.github.io/quant-scanner-v8/',
  pretendToBeVisual: true,
  virtualConsole: vc,
  beforeParse(window) {
    try { window.eval(dataScripts); } catch (e) { errors.push('[DATA_EVAL] ' + (e && e.message || e)); }
  }
});

const win = dom.window;
const doc = win.document;

function getCardTitle(card) {
  const h = card.querySelector('h3');
  return h ? h.textContent.replace(/\s+/g, ' ').slice(0, 70) : '(无标题)';
}

function cardIsEmpty(card) {
  const bodyHTML = card.innerHTML.replace(/<h3[\s\S]*?<\/h3>/, '');
  const text = bodyHTML.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
  const EMPTY_MARK = /(暂无数据|暂无概念数据|暂无历史数据|暂无热点板块|暂无行业板块|数据暂不可用|加载中…|数据不可用|候选池数据暂不可用)/;
  const hasMark = EMPTY_MARK.test(bodyHTML);
  const isEmpty = hasMark || (text.length < 2 && bodyHTML.length < 500);
  return { isEmpty, hasMark, mark: hasMark ? bodyHTML.match(EMPTY_MARK)[0] : (text.length < 2 && bodyHTML.length < 500 ? '内容过短' : null), text: text.slice(0, 80) };
}

setTimeout(() => {
  console.log('== 主动切换所有 tab + 触发渲染 ==');
  const tabs = doc.querySelectorAll('.tab[data-sec]');
  let tabErr = 0;
  tabs.forEach(t => {
    const sec = t.dataset.sec;
    try {
      if (typeof win.switchSec === 'function') win.switchSec(sec, t);
    } catch (e) { tabErr++; console.log(`   ❌ switchSec('${sec}') 抛错: ${(e && e.message || e).slice(0,100)}`); }
  });
  // 子 tab
  try {
    if (typeof win.switchRcTab === 'function') win.switchRcTab('tab1', doc.querySelector('.rc-tab-btn.active'));
  } catch (e) { console.log('   rc-tab 切换抛错:', (e && e.message || e).slice(0,80)); }
  try {
    if (typeof win.opSwitchTab === 'function') win.opSwitchTab(2);
  } catch (e) { console.log('   op tab2 切换抛错:', (e && e.message || e).slice(0,80)); }

  setTimeout(() => {
    console.log(`\n== ${doc.querySelectorAll('.card').length} 个 .card 检查 ==`);
    let emptyCnt = 0;
    doc.querySelectorAll('.card').forEach((card, i) => {
      const { isEmpty, hasMark, mark, text } = cardIsEmpty(card);
      if (isEmpty) {
        emptyCnt++;
        console.log(`❌ 卡片#${i} [${mark||'空'}] ${getCardTitle(card)}`);
        if (text) console.log(`     body文本: ${text}`);
      }
    });
    if (!emptyCnt) console.log('   ✅ 所有卡片均已渲染');

    console.log('\n== 仍含"加载中…"的元素 ==');
    let lc = 0;
    doc.querySelectorAll('[id]').forEach(el => {
      if (/加载中…/.test(el.innerHTML)) {
        lc++;
        const h = el.closest('.card');
        console.log(`   ⏳ id=${el.id} ${h ? '→ '+getCardTitle(h) : ''}`);
      }
    });
    console.log(`   共 ${lc} 处`);

    console.log('\n== 渲染期错误 ==');
    const real = errors.filter(e => !/Could not load|Not implemented|resource|echarts|canvas/.test(e));
    if (real.length) real.forEach(e => console.log('   ❌ ' + e.slice(0, 180)));
    else console.log('   ✅ 无关键渲染错误');

    console.log(`\n== 空卡片汇总: ${emptyCnt} ==`);
    process.exit(emptyCnt ? 1 : 0);
  }, 800);
}, 300);
