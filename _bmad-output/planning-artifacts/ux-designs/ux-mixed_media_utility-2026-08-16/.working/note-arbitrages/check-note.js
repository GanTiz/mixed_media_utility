const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const fs = require('fs');
const S = process.env.S;
const CAP = `window.claude={use:async n=>n==='artifact'?{publish:async h=>{window.__published=h;return{version:'v'}}}:null};`;
const NOCAP = `window.claude=undefined;`;
const NOSTORE = `try{Object.defineProperty(window,'localStorage',{get(){throw new Error('bloque')}});Object.defineProperty(window,'sessionStorage',{get(){throw new Error('bloque')}});}catch(e){}`;

async function ctx(b, scripts) {
  const c = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true });
  for (const s of scripts) await c.addInitScript(s);
  return c;
}
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });

  // ---------- A. regime nominal ----------
  let c = await ctx(b, [CAP]);
  let p = await c.newPage();
  const errs = [];
  p.on('console', m => { if (m.type() === 'error') errs.push(m.text()); });
  p.on('pageerror', e => errs.push('pageerror: ' + e.message));
  await p.goto('file://' + S + '/note-arbitrages.html');
  await p.waitForTimeout(300);
  console.log('[A] viewport:', await p.evaluate(() => document.documentElement.clientWidth),
    '| debordement:', await p.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1),
    '| memoire:', (await p.textContent('#memoire-etat')).slice(0, 46));

  // choix sur le point 1
  await p.click('.choix[data-point="1"] .opt[data-val="a"]');
  await p.waitForTimeout(200);
  console.log('[A] choix marque:', await p.getAttribute('.choix[data-point="1"]', 'data-choisi'),
    '| etat:', await p.textContent('.choix[data-point="1"] .choix-etat'),
    '| presse:', await p.getAttribute('.choix[data-point="1"] .opt[data-val="a"]', 'aria-pressed'));

  // note sur un passage
  await p.click('p[data-c="p1-motif"]');
  await p.waitForTimeout(300);
  await p.fill('#c-text', "D'accord, mais montre-moi les deux avant de trancher.");
  await p.click('#c-save');
  await p.waitForTimeout(300);
  console.log('[A] compteur:', await p.textContent('#c-n'), '| etat sauvegarde:', await p.textContent('#c-s'),
    '| pastille:', await p.locator('p[data-c="p1-motif"] .c-pin').count());

  await p.waitForTimeout(2200);   // republication differee
  const html = await p.evaluate(() => window.__published || '');
  fs.writeFileSync(S + '/note-republiee.html', html);
  const etat = (html.match(/id="etat">(.*?)<\/script>/s) || [])[1] || '';
  console.log('[A] republie:', (html.length/1024).toFixed(0) + ' Ko | doctype:', html.startsWith('<!doctype html>'),
    '| etat:', etat.slice(0, 120).replace(/\\u003c/g, '<'));
  console.log('[A] pas de pastille figee:', !html.includes('c-pin'), '| pas de barre figee:', !html.includes('c-bar'));

  // ---------- B. aller-retour ----------
  const p2 = await c.newPage();
  const errs2 = [];
  p2.on('pageerror', e => errs2.push('pageerror: ' + e.message));
  p2.on('console', m => { if (m.type() === 'error') errs2.push(m.text()); });
  await p2.goto('file://' + S + '/note-republiee.html');
  await p2.waitForTimeout(400);
  console.log('[B] choix restaure:', await p2.getAttribute('.choix[data-point="1"]', 'data-choisi'),
    '| note restauree:', await p2.locator('p[data-c="p1-motif"] .c-pin').count(),
    '| compteur:', await p2.textContent('#c-n'),
    '| css applique:', await p2.evaluate(() => getComputedStyle(document.body).fontFamily.slice(0, 18)));

  // export
  await p2.click('#c-btn-export');
  await p2.waitForTimeout(300);
  const ex = await p2.inputValue('#c-ex-text');
  console.log('[B] export contient la reponse:', /## Reponses\s+1a/.test(ex), '| la note:', ex.includes('avant de trancher'),
    '| bloc json:', /"choix": \{\s*"1": "a"/.test(ex));
  await p2.click('#c-ex-close');

  // ---------- C. stockage bloque, capacite presente ----------
  let c3 = await ctx(b, [CAP, NOSTORE]);
  const p3 = await c3.newPage();
  await p3.goto('file://' + S + '/note-arbitrages.html');
  await p3.waitForTimeout(300);
  await p3.click('p[data-c="a3"]');
  await p3.waitForTimeout(200);
  await p3.fill('#c-text', 'Note en stockage bloque.');
  await p3.click('#c-save');
  await p3.waitForTimeout(300);
  console.log('[C] etat:', await p3.textContent('#c-s'), '| alarme visible:',
    await p3.evaluate(() => !!document.querySelector('.c-alarm.on')));

  // ---------- D. stockage bloque, pas de capacite ----------
  let c4 = await ctx(b, [NOCAP, NOSTORE]);
  const p4 = await c4.newPage();
  await p4.goto('file://' + S + '/note-arbitrages.html');
  await p4.waitForTimeout(300);
  await p4.click('p[data-c="a3"]');
  await p4.waitForTimeout(200);
  await p4.fill('#c-text', 'Note sans filet.');
  await p4.click('#c-save');
  await p4.waitForTimeout(300);
  console.log('[D] etat:', await p4.textContent('#c-s'), '| alarme visible:',
    await p4.evaluate(() => !!document.querySelector('.c-alarm.on')),
    '| rappel export:', await p4.evaluate(() => !!document.querySelector('.c-nudge.on')),
    '| bandeau:', (await p4.textContent('#memoire-etat')).slice(0, 40));

  console.log('erreurs A:', errs.length ? errs : 'aucune');
  console.log('erreurs B:', errs2.length ? errs2 : 'aucune');
  await b.close();
})();
