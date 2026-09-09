# -*- coding: utf-8 -*-
"""Genere la planche de contact publiee : contenu statique + retours enregistres
dans la page elle-meme (capacite artifact.publish)."""
import base64, pathlib

S = pathlib.Path('/tmp/claude-0/-home-user-mixed-media-utility/c54b30dd-4fc6-5b3c-9cf8-4e164b2f3aef/scratchpad')
URLS = {
 'key-chutier': 'https://claude.ai/code/artifact/4a2b4946-4da1-4e69-99d0-c63d94c963ad',
 'key-scan-mode-pdf': 'https://claude.ai/code/artifact/72890f59-9f2f-4d27-a2a2-e0943d671a29',
 'key-atelier-pdf': 'https://claude.ai/code/artifact/753ecf67-40d9-440d-854c-f5b050fb3376',
 'key-mode-lecteur': 'https://claude.ai/code/artifact/79e12912-78c0-42e2-88ba-6ff90e0cba03',
}

def img(slug, state):
    b = base64.b64encode((S / f'z-{slug}-{state}.png').read_bytes()).decode()
    return 'data:image/png;base64,' + b

def note_block(key, label):
    return f'''      <div class="note-block" data-key="{key}">
        <div class="notes"></div>
        <div class="compose">
          <textarea class="note-input" rows="2" aria-label="Retour sur {label}" placeholder="Ton retour sur {label}&hellip;"></textarea>
          <div class="compose-row"><span class="status" role="status"></span><button type="button" class="save">Enregistrer</button></div>
        </div>
      </div>'''

def shot(slug, state, tag, alt, title):
    return f'''      <button class="shot" type="button" data-img="{img(slug, state)}" data-title="{title}">
        <span class="tag"><b>{tag}</b><span class="grow">Agrandir</span></span>
        <img src="{img(slug, state)}" alt="{alt}">
      </button>'''

SCREENS = [
  dict(slug='key-chutier', h2='Le chutier', states='deux p&eacute;rim&egrave;tres &middot; huit r&ocirc;les annot&eacute;s',
    shots=[
      ('a', 'P&eacute;rim&egrave;tre 1 &mdash; Extraction / Pdf', "Le chutier c&ocirc;t&eacute; Extraction : l'arbre descend du rush vers les lots puis les planches.", 'Chutier - perimetre Extraction / Pdf', 'le p&eacute;rim&egrave;tre Extraction'),
      ('b', 'P&eacute;rim&egrave;tre 2 &mdash; Scan / Exports', "Le chutier c&ocirc;t&eacute; Scan : l'arbre remonte des planches scann&eacute;es vers les lots reconstruits.", 'Chutier - perimetre Scan / Exports, arborescence inversee', 'le p&eacute;rim&egrave;tre Scan'),
    ],
    paras=["À gauche, l'arbre d'Extraction descend : <em>rush &gt; lots &gt; planches</em>. Au Scan, il <em>remonte</em> : on part des planches scannées pour reconstruire les lots. C'est l'écran où une erreur de conception coûterait le plus cher, parce que les huit rôles y passent tous.",
           'À regarder : la couleur ne porte jamais seule &mdash; complet <span class="dot ok"></span> disque plein, absent <span class="dot no"></span> anneau creux, remplacement <span class="dot sub"></span> disque hachuré.'],
    question="l'inversion de l'arbre du Scan se lit-elle sans qu'on te l'explique ?",
    governs='EXPERIENCE.md &rsaquo; Information Architecture &middot; Le chutier, huit roles &middot; State Patterns &middot; Accessibility Floor'),

  dict(slug='key-scan-mode-pdf', h2='Atelier Scan, mode PDF', states="le QR gouverne ce que l'outil ose proposer",
    shots=[
      ('a', "&Eacute;tat A &mdash; le QR n'est pas lu", "Atelier Scan, QR non lu : aucune zone d'image propos&eacute;e, le formulaire est vide, l'action est bloqu&eacute;e.", "Atelier Scan - etat A, le QR n'est pas lu", "l'&eacute;tat A"),
      ('b', '&Eacute;tat B &mdash; QR compl&eacute;t&eacute;', "Atelier Scan, QR compl&eacute;t&eacute; : les zones d'image sont propos&eacute;es, une poign&eacute;e est saisie, la loupe est ouverte.", 'Atelier Scan - etat B, QR complete', "l'&eacute;tat B"),
    ],
    paras=["État A : le QR de la page n'a pas été lu, <em>aucune</em> zone d'image n'est proposée et l'action est bloquée. Aucun champ n'est prérempli non plus &mdash; un champ vide appelle la vérification, un champ faux ne l'appelle pas. État B : le lot est connu, l'outil propose, on ajuste une poignée, la loupe s'ouvre dans le passe-partout."],
    question="le blocage de l'état A est-il vécu comme une protection ou comme un mur ?",
    governs='EXPERIENCE.md &rsaquo; State Patterns (<code>PAGE_QR_UNREADABLE</code>) &middot; Interaction Primitives &middot; Key Flows'),

  dict(slug='key-atelier-pdf', h2="L'atelier Pdf", states="l'aper&ccedil;u vivant, sans bouton de rafra&icirc;chissement",
    shots=[
      ('a', '&Eacute;tat A &mdash; marge &agrave; 0 mm', "Atelier Pdf, marge de travail &agrave; z&eacute;ro : la planche occupe toute la surface utile.", 'Atelier Pdf - etat A, marge de travail a 0', 'la marge &agrave; 0'),
      ('b', '&Eacute;tat B &mdash; marge &agrave; 8 mm', "Atelier Pdf, marge de travail &agrave; 8 mm : la planche s'est redessin&eacute;e, les images ont recul&eacute;.", 'Atelier Pdf - etat B, marge de travail a 8 mm', 'la marge &agrave; 8 mm'),
    ],
    paras=["Camille demande 8 mm pour déborder à la gouache. La planche se redessine <em>à la frappe</em> : il n'y a pas de bouton de rafraîchissement, parce qu'un aperçu qu'il faut demander n'est pas un aperçu. Chaque image jugée garde son passe-partout neutre &mdash; la même règle que celle qui encadre ces vignettes."],
    question="les réglages sont-ils dans l'ordre où tu les prends, ou dans l'ordre où je les ai rangés ?",
    governs='EXPERIENCE.md &rsaquo; Component Patterns &middot; Interaction Primitives &middot; DESIGN.md &rsaquo; Layout &amp; Spacing'),

  dict(slug='key-mode-lecteur', h2='Le mode lecteur', states="ta consigne du jour, devenue une r&egrave;gle d'&eacute;cran",
    shots=[
      ('a', '&Eacute;tat A &mdash; la machine suit', "Mode lecteur, cadence tenue : la sc&egrave;ne de pr&eacute;visualisation et la barre de transport.", 'Mode lecteur - etat A, la machine tient la cadence', 'la cadence tenue'),
      ('b', '&Eacute;tat B &mdash; elle ne suit pas', "Mode lecteur, repli de qualit&eacute; : un bandeau ambre sous la sc&egrave;ne annonce la baisse de d&eacute;finition.", 'Mode lecteur - etat B, repli de qualite visible', 'le repli de qualit&eacute;'),
    ],
    paras=["Sur une machine lente, la previz dégrade <em>l'image</em>, jamais la cadence &mdash; c'est le rythme qu'on juge à cet instant. Mais elle ne peut pas le faire en silence. Le bandeau se voit, se nomme (<code>PREVIEW_QUALITY_REDUCED</code>), et se refuse en un clic : <em>tenir la qualité, perdre la cadence</em>.",
           "Il est ambre et non rouge : c'est un compromis, pas un échec. Et il se pose <em>sous</em> la scène, jamais par-dessus l'image."],
    question="le repli doit-il se souvenir de ton choix pour les lots suivants, ou se reposer à chaque fois ?",
    governs='EXPERIENCE.md &rsaquo; State Patterns &middot; Responsive &amp; Platform &middot; Voice and Tone'),
]

frames = []
for sc in SCREENS:
    shots_html = []
    for state, tag, alt, title, short in sc['shots']:
        shots_html.append(shot(sc['slug'], state, tag, alt, title))
        shots_html.append(note_block(f"{sc['slug']}-{state}", short))
    paras = '\n'.join(f'    <p>{p}</p>' for p in sc['paras'])
    frames.append(f'''  <article class="frame">
    <div class="frame-head">
      <h2>{sc['h2']}</h2>
      <span class="states">{sc['states']}</span>
    </div>
    <div class="shots">
{chr(10).join(shots_html)}
    </div>
{paras}
    <p class="open"><b>Ce dont j'ai besoin :</b> {sc['question']}</p>
    <p class="governs">{sc['governs']}</p>
  </article>''')

CSS = (S / 'planche.css').read_text(encoding='utf-8')
JS = (S / 'planche.js').read_text(encoding='utf-8')
BODY = (S / 'planche-body.html').read_text(encoding='utf-8').replace('__FRAMES__', '\n\n'.join(frames))
for slug, url in URLS.items():
    BODY = BODY.replace(f'__URL_{slug}__', url)

out = (
  '<title>Planche de contact</title>\n'
  '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">\n'
  '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
  '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@400;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@500&display=swap">\n'
  f'<style id="css">\n{CSS}\n</style>\n'
  f'<div id="app">\n{BODY}\n</div>\n'
  f'<script id="app-js">\n{JS}\n</script>\n'
)
p = S / 'planche-de-contact.html'
p.write_text(out, encoding='utf-8')
print(f'{p.stat().st_size/1024/1024:.2f} MiB')
