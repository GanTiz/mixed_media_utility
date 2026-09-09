const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const dir = '/home/user/mixed_media_utility/_bmad-output/planning-artifacts/ux-designs/ux-mixed_media_utility-2026-08-16/mockups/';
const files = ['key-chutier','key-scan-mode-pdf','key-atelier-pdf','key-mode-lecteur'];
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const p = await b.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
  for (const f of files) {
    await p.goto('file://' + dir + f + '.html', { waitUntil: 'load' });
    const els = await p.$$('.app');
    for (let i = 0; i < els.length; i++) {
      const tag = i === 0 ? 'a' : 'b';
      await els[i].screenshot({ path: `${process.env.S}/hi-${f}-${tag}.png` });
    }
    console.log(f, els.length + ' etats');
  }
  await b.close();
})();
