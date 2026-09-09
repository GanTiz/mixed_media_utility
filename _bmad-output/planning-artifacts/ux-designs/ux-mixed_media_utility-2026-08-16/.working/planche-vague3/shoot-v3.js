const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const S = process.env.S, M = process.env.M, F = process.env.F;
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  await p.goto('file://' + M + '/' + F + '.html', { waitUntil: 'load' });
  console.log('debordement:', await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1),
    '| erreurs:', errs.length ? errs : 'aucune');
  const els = await p.$$('.app');
  for (let i = 0; i < els.length; i++) {
    await els[i].screenshot({ path: `${S}/hi-${F}-${'abcdef'[i]}.png` });
  }
  console.log(els.length, 'etats captures');
  await b.close();
})();
