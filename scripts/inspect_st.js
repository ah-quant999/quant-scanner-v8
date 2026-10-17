#!/usr/bin/env node
/**
 * inspect_st.js — 切换到 st tab 后，检查 renderConsensus/renderTrack 是否被调用、数据是否到位
 */
'use strict';
const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
  });
  const page = await browser.newPage();
  page.on('pageerror', e => console.log('PAGEERROR:', String(e).slice(0,200)));
  page.on('console', m => { if (m.type()==='error' && !/404|echarts|canvas/.test(m.text())) console.log('CERR:', m.text().slice(0,200)); });

  await page.goto('https://ah-quant999.github.io/quant-scanner-v8/', { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(2500);

  // 切到 st tab
  await page.evaluate(() => { window.switchSec && window.switchSec('st'); });
  await page.waitForTimeout(1500);

  // 检查数据
  const inspect = await page.evaluate(() => {
    const dump = {};
    ['TRIPLE_CONSENSUS','TRIPLE_TRACK','TRIPLE_HISTORY'].forEach(k => {
      const v = window[k];
      if (v) dump[k] = { keys: Object.keys(v), stocks_len: (v.stocks||[]).length, near_miss_len: (v.near_miss||[]).length, tracked_len: (v.tracked||[]).length, alerts_len: (v.alerts||[]).length, backtest_total: (v.backtest_signal||{}).total };
      else dump[k] = 'UNDEFINED';
    });
    // 4 个空卡片的 DOM 内容
    dump.DOM = {
      tcPriority: document.getElementById('tcPriority')?.innerHTML?.slice(0, 200),
      tcExtended: document.getElementById('tcExtended')?.innerHTML?.slice(0, 200),
      ttAlerts: document.getElementById('ttAlerts')?.innerHTML?.slice(0, 200),
      ttBackNote: document.getElementById('ttBackNote')?.textContent,
      ttBackBody: document.getElementById('ttBackBody')?.innerHTML?.slice(0, 200),
    };
    return dump;
  });

  console.log('== TRIPLE 数据状态 ==');
  Object.entries(inspect).filter(([k]) => k!=='DOM').forEach(([k,v]) => console.log(k+':', JSON.stringify(v)));
  console.log('\n== 4 个空卡片 DOM ==');
  Object.entries(inspect.DOM).forEach(([k,v]) => console.log(k+':', v));

  await browser.close();
})();
