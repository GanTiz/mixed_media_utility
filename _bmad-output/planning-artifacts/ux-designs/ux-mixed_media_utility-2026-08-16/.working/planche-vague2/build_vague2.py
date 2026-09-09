# -*- coding: utf-8 -*-
"""Planche de contact de la vague 1 : trois ecrans, six etats, retours par vignette."""
import base64, json, pathlib

S = pathlib.Path('/tmp/claude-0/-home-user-mixed-media-utility/c54b30dd-4fc6-5b3c-9cf8-4e164b2f3aef/scratchpad')

def img(slug, state):
    return 'data:image/png;base64,' + base64.b64encode((S / f'z-{slug}-{state}.png').read_bytes()).decode()

RETOURS = json.load(open(S / 'retours-v2.json', encoding='utf-8'))

def notes_deja(key):
    out = []
    for n in RETOURS.get(key, []):
        txt = (n['text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
        out.append('<p class="note"><span class="body"><span class="when">'
                   + n['when'] + '</span>' + txt + '</span>'
                   + '<button class="del" type="button" aria-label="Supprimer ce retour">\u00d7</button></p>')
    return ''.join(out)

def note_block(key, label):
    return f'''      <div class="note-block" data-key="{key}">
        <div class="notes">{notes_deja(key)}</div>
        <div class="compose">
          <textarea class="note-input" rows="2" aria-label="Retour sur {label}" placeholder="Ton retour sur {label}&hellip;"></textarea>
          <div class="compose-row"><span class="status" role="status"></span><button type="button" class="save">Enregistrer</button></div>
        </div>
      </div>'''

def shot(slug, state, tag, alt, title):
    d = img(slug, state)
    return f'''      <button class="shot" type="button" data-img="{d}" data-title="{title}">
        <span class="tag"><b>{tag}</b><span class="grow">Agrandir</span></span>
        <img src="{d}" alt="{alt}">
      </button>'''

SCREENS = [
  dict(slug='key-extraction', h2="L'atelier Extraction", states='deux modes &middot; la coquille commune',
    shots=[('a', '&Eacute;tat A &mdash; mode Mouvement : poser les bornes sur le rush',
            "Le rush joue, la chronologie porte l'entree, la sortie et deux marqueurs ; le transport est au complet.",
            'Extraction - etat A, mode Mouvement', 'les bornes et le transport'),
           ('b', '&Eacute;tat B &mdash; la galerie des frames a extraire',
            "Galerie des frames comprises entre les bornes, deux frames ecartees, le bouton annoncant le nombre reel.",
            'Extraction - etat B, la galerie', 'la galerie des frames'),
           ('c', '&Eacute;tat C &mdash; la meme galerie, vignettes agrandies',
            "La meme galerie en grandes vignettes, la taille se reglant par la loupe de la barre.",
            'Extraction - etat C, vignettes agrandies', 'les vignettes agrandies')],
    paras=["<strong>Le transport est refait sur tes treize retours</strong> : une seule ligne sous l'image, quinze icônes au trait, aucun libellé. Les bornes encadrent la barre — l'entrée à gauche, la sortie à droite — et les deux boutons extrêmes du groupe central y conduisent, ce qui fait disparaître « aller au in ». La progression est un trait de 3 px.",
           "Volume en haut-parleur, curseur vertical et silence au clic. Marqueur en bouton unique — son édition rejoint le chantier du clic droit. La cadence s'écrit <em>25</em>.",
           "<strong>Ton renommage l'emporte</strong> : les onglets sont <em>page, galerie, lecteur</em>, et un onglet sans objet n'est pas grisé, il est absent. Un rush n'a pas de page.",
           "Et ta question sur les cadences reçoit une proposition : <strong>un sélecteur à gauche du badge</strong>, qui liste les extractions du rush et <em>garde le timecode</em> quand tu en changes — comparer 12,5 et 25 sur le même instant sans se replacer."],
    question="le selecteur de cadence a gauche du badge, est-ce le bon endroit &mdash; ou le veux-tu dans la barre de transport ?",
    governs='Vague 2 &middot; coquille commune, transport complet'),

  dict(slug='key-cadence', h2='La cadence, et ce qu\'on fait quand elle lache', states='trois regimes',
    shots=[('a', '&Eacute;tat A &mdash; la cadence est tenue',
            "Badge vert affichant la cadence effective, qualite pleine dans le menu voisin.",
            'Cadence - etat A, tenue', 'la cadence tenue'),
           ('b', '&Eacute;tat B &mdash; la cadence n\'est pas tenue',
            "Badge rouge, qualite pleine affichee a cote : le badge constate sans rien decider.",
            'Cadence - etat B, lachee', 'la cadence lachee'),
           ('c', '&Eacute;tat C &mdash; rouge prolonge : un seul bandeau',
            "Bandeau unique sous la scene, refermable et desactivable pour la session.",
            'Cadence - etat C, le bandeau', 'le bandeau unique')],
    paras=["Ta conception, prise telle quelle. Le badge affiche la cadence <strong>effective</strong> ; vert si elle est tenue, rouge sinon. Il constate, il ne décide pas.",
           "La qualité est un menu à côté — pleine, demie, quart, auto. C'est toi qui dégrades, sauf en <em>auto</em>.",
           "<strong>Ton seuil est appliqué : cinq secondes</strong> de rouge continu, puis un seul bandeau, refermable et désactivable pour la session. En dessous, le rouge ne dit rien d'utile : il arrive au démarrage, sur un saut, au changement de lot."],
    question="cinq secondes : est-ce que ca tient aussi au demarrage d'une lecture, ou faut-il un delai de grace au lancement ?",
    governs='A3, A4 &middot; conception d\'Egan du 20/08'),
]

frames = []
for sc in SCREENS:
    parts = []
    for state, tag, alt, title, short in sc['shots']:
        parts.append(shot(sc['slug'], state, tag, alt, title))
        parts.append(note_block(f"{sc['slug']}-{state}", short))
    paras = '\n'.join(f'    <p>{p}</p>' for p in sc['paras'])
    frames.append(f'''  <article class="frame">
    <div class="frame-head">
      <h2>{sc['h2']}</h2>
      <span class="states">{sc['states']}</span>
    </div>
    <div class="shots">
{chr(10).join(parts)}
    </div>
{paras}
    <p class="open"><b>Ce dont j'ai besoin :</b> {sc['question']}</p>
    <p class="governs">{sc['governs']}</p>
  </article>''')

CSS = (S / 'v1' / 'planche.css').read_text(encoding='utf-8')
JS = (S / 'v1' / 'planche.js').read_text(encoding='utf-8')
BODY = (S / 'vague2-body.html').read_text(encoding='utf-8').replace('__FRAMES__', '\n\n'.join(frames))

out = (
  '<title>Vague 2</title>\n'
  '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">\n'
  '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
  '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@400;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@500&display=swap">\n'
  f'<style id="css">\n{CSS}\n</style>\n'
  f'<div id="app">\n{BODY}\n</div>\n'
  f'<script id="app-js">\n{JS}\n</script>\n'
)
p = S / 'planche-vague2.html'
p.write_text(out, encoding='utf-8')
print(f'{p.stat().st_size/1024/1024:.2f} MiB')
