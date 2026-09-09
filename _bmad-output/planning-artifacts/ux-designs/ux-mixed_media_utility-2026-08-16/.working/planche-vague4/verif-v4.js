// Banc de verification des maquettes.
//
// Il a trois controles, et chacun vient d'un defaut reellement passe :
//  1. debordement horizontal du document ;
//  2. barre d'atelier qui deborde sur le panneau (defaut du 22 aout, vu deux
//     fois : signale par Egan sur la galerie, reapparu sur trois ecrans) ;
//  3. element ecrase a une largeur derisoire -- le cas de `.pj.tete`, qui
//     heritait de la tete de lecture de la chronologie et se reduisait a un
//     trait de 26 px sur 1108. Ni (1) ni (2) ne le voyaient.
//
// Il ne remplace pas l'ouverture des captures : il attrape ce qui se mesure.
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const M = process.env.M;
const FICHIERS = process.argv.slice(2);
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
  const p = await b.newPage({ viewport: { width: 1280, height: 1100 } });
  let ko = 0;
  for (const f of FICHIERS) {
    await p.goto('file://' + M + '/' + f + '.html', { waitUntil: 'load' });
    const r = await p.evaluate(() => {
      const out = { deborde: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1, barres: [], ecrases: [] };
      document.querySelectorAll('.wh').forEach((wh, i) => {
        if (wh.scrollWidth > wh.clientWidth + 1) out.barres.push(`wh#${i} ${wh.scrollWidth}>${wh.clientWidth}`);
      });
      // exceptions nommees : des elements volontairement etroits et hauts.
      // On les liste plutot que d'abaisser le seuil -- une exception nommee
      // reste lisible, un seuil relache attrape moins.
      const VOULU = ['rappel', 'replier', 'sepv', 'piste', 'curseur'];
      document.querySelectorAll('.sheet *').forEach(el => {
        if (!el.textContent.trim()) return;
        if (VOULU.some(c => el.classList && el.classList.contains(c))) return;
        const b = el.getBoundingClientRect();
        // un bloc porteur de texte plus haut que large d'un facteur 4 et
        // large de moins de 60 px est ecrase, pas etroit.
        if (b.width > 0 && b.width < 60 && b.height > b.width * 4) {
          out.ecrases.push(`${el.className || el.tagName} ${Math.round(b.width)}x${Math.round(b.height)}`);
        }
      });
      return out;
    });
    const pb = [];
    if (r.deborde) pb.push('document deborde');
    if (r.barres.length) pb.push('barre ' + r.barres.join(', '));
    if (r.ecrases.length) pb.push('ecrase ' + r.ecrases.slice(0, 4).join(', '));
    if (pb.length) { ko++; console.log(`${f}  KO  ${pb.join(' | ')}`); }
    else console.log(`${f}  ok`);
  }
  await b.close();
  process.exit(ko ? 1 : 0);
})();
