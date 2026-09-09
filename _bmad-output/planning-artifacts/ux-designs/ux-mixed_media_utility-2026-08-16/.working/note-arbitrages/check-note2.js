const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const S = process.env.S;
const CAP = `window.claude={use:async n=>n==='artifact'?{publish:async h=>{window.__published=h;return{version:'v'}}}:null};`;
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const c = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  await c.addInitScript(CAP);
  const p = await c.newPage();
  const errs = [];
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  await p.goto('file://' + S + '/note-republiee.html');
  await p.waitForTimeout(400);

  // export -> on garde le texte
  await p.click('#c-btn-export');
  await p.waitForTimeout(200);
  const bloc = await p.inputValue('#c-ex-text');
  await p.click('#c-ex-close');

  // purge
  await p.click('#c-btn-import');
  await p.waitForTimeout(200);
  p.once('dialog', d => d.accept());
  await p.click('#c-im-clear');
  await p.waitForTimeout(400);
  console.log('[E] apres purge — notes:', await p.textContent('#c-n'),
    '| pastilles:', await p.locator('.c-pin').count());

  // reprise par collage (la feuille est restee ouverte apres la purge)
  await p.fill('#c-im-paste', bloc);
  await p.click('#c-im-load');
  await p.waitForTimeout(500);
  console.log('[E] apres collage — notes:', await p.textContent('#c-n'),
    '| pastilles:', await p.locator('.c-pin').count(),
    '| choix 1:', await p.getAttribute('.choix[data-point="1"]', 'data-choisi'),
    '| message:', await p.textContent('#c-im-msg'));
  await p.waitForTimeout(600);
  await p.click('#c-im-close').catch(() => {});

  // index des notes et saut au passage
  await p.click('#c-btn-index');
  await p.waitForTimeout(300);
  console.log('[E] index:', await p.locator('#c-list .c-idx').count(), 'entree(s)');
  await p.evaluate(() => document.querySelector('#c-list .c-idx').click());
  await p.waitForTimeout(400);
  console.log('[E] saut au passage — feuille fermee:', await p.evaluate(() => !document.querySelector('.c-sheet.open')), '| passage a l ecran:', await p.evaluate(() => { var r = document.querySelector('p[data-c="p1-motif"]').getBoundingClientRect(); return r.top > -50 && r.top < innerHeight; }));
  console.log('erreurs:', errs.length ? errs : 'aucune');
  await p.screenshot({ path: S + '/note-haut.png' });
  await p.evaluate(() => document.querySelector('.choix[data-point="1"]').scrollIntoView({block:'center'}));
  await p.waitForTimeout(200);
  await p.screenshot({ path: S + '/note-choix.png' });
  await b.close();
})();
