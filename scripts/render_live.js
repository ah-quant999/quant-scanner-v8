#!/usr/bin/env node
/**
 * render_live.js — 用真实 Chrome 渲染线上主站，截图各 tab 并提取卡片内容状态。
 */
'use strict';
const { chromium } = require('playwright-core');

const SITE = 'https://ah-quant999.github.io/quant-scanner-v8/';
const OUT = __dirname + '/../.workbuddy/';

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
  });
  const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();

  // 捕获 console 错误
  const consoleErrors = [];
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text().slice(0, 200)); });
  page.on('pageerror', e => consoleErrors.push('PAGEERROR: ' + String(e).slice(0, 200)));

  try {
    await page.goto(SITE, { waitUntil: 'domcontentloaded', timeout: 30000 });
  } catch (e) {
    console.log('导航超时，继续用已有 DOM');
  }
  await page.waitForTimeout(5000);

  // 各主 tab 截图
  const tabs = await page.$$eval('.tab[data-sec]', els => els.map(e => e.dataset.sec));
  console.log('主 tabs:', tabs.join(', '));

  const results = {};
  for (const sec of tabs) {
    try {
      await page.evaluate(s => { window.switchSec && window.switchSec(s); }, sec);
      await page.waitForTimeout(1200);
      const shot = `${OUT}live_${sec}.png`;
      await page.screenshot({ path: shot, fullPage: true });
      // 收集当前 tab 的卡片内容状态
      const cardInfo = await page.evaluate(() => {
        const out = [];
        const cards = document.querySelectorAll('.card');
        cards.forEach(c => {
          if (c.offsetParent === null) return; // 只检查可见的
          const h = c.querySelector('h3');
          const title = h ? h.textContent.replace(/\s+/g,' ').slice(0,50) : '(无标题)';
          const body = c.innerHTML.replace(/<h3[\s\S]*?<\/h3>/,'');
          const text = body.replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
          const marks = (body.match(/(加载中…|暂无数据|暂无概念数据|暂无历史数据|暂无热点板块|数据暂不可用|数据不可用)/g)||[]);
          const visible = c.getBoundingClientRect().height > 5;
          out.push({ title, textLen: text.length, marks: marks.slice(0,3), visible });
        });
        return out;
      });
      results[sec] = cardInfo;
    } catch (e) {
      console.log(`切换 ${sec} 失败: ${e.message.slice(0,100)}`);
    }
  }

  console.log('\n== 各 tab 卡片状态（可见卡片中，含空态标记的） ==');
  const EMPTY_RE = /(加载中…|暂无数据|暂无概念数据|暂无历史数据|暂无热点板块|数据暂不可用|数据不可用)/;
  for (const [sec, cards] of Object.entries(results)) {
    const bad = cards.filter(c => c.visible && (c.textLen < 3 || EMPTY_RE.test(c.marks.join(' '))));
    if (bad.length) {
      console.log(`\n[${sec}] 异常 ${bad.length}/${cards.length} 个可见卡片:`);
      bad.forEach(c => console.log(`   ❌ ${c.marks.join(',')||'内容过短'} | ${c.title} (textLen=${c.textLen})`));
    } else {
      console.log(`\n[${sec}] ✅ ${cards.length} 个可见卡片全部正常`);
    }
  }

  console.log('\n== 关键 console 错误（前15条） ==');
  consoleErrors.slice(0, 15).forEach(e => console.log('   ❌ ' + e));

  await browser.close();
  console.log('\n截图已保存到 .workbuddy/live_*.png');
})();
