# -*- coding: utf-8 -*-
"""Planche de contact de la vague 3 : trois ecrans, neuf etats.

Les retours deja poses par Egan sont reinjectes depuis `retours-v3.json` --
republier une planche sans cela EFFACE ses retours, c'est le piege le plus
couteux de ce dispositif.
"""
import base64, json, pathlib

ICI = pathlib.Path(__file__).resolve().parent
S = pathlib.Path('/tmp/claude-0/-home-user-mixed-media-utility/c54b30dd-4fc6-5b3c-9cf8-4e164b2f3aef/scratchpad')
V1 = S / 'v1'

def img(slug, state):
    return 'base64,' + base64.b64encode((S / f'z-{slug}-{state}.png').read_bytes()).decode()

RJ = ICI / 'retours-v3.json'
RETOURS = json.load(open(RJ, encoding='utf-8')) if RJ.exists() else {}

def notes_deja(key):
    out = []
    for n in RETOURS.get(key, []):
        txt = n['text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        out.append('<p class="note"><span class="body"><span class="when">'
                   + n['when'] + '</span>' + txt + '</span>'
                   + '<button class="del" type="button" aria-label="Supprimer ce retour">×</button></p>')
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
    d = 'data:image/png;' + img(slug, state)
    return f'''      <button class="shot" type="button" data-img="{d}" data-title="{title}">
        <span class="tag"><b>{tag}</b><span class="grow">Agrandir</span></span>
        <img src="{d}" alt="{alt}">
      </button>'''

SCREENS = [
  dict(slug='key-exports', h2="L'atelier Exports", states='trois etats &middot; le balayage',
    shots=[('a', '&Eacute;tat A &mdash; le lot reconstruit se relit',
            "Le lot reconstruit dans le lecteur, cadence cible choisie, balayage eteint.",
            'Exports - etat A, le lot se relit', 'le lot reconstruit'),
           ('b', '&Eacute;tat B &mdash; le balayage tire, en pause',
            "Balayage entre le rush d'origine a gauche et le lot reconstruit a droite, poignee neutre.",
            'Exports - etat B, le balayage', 'le balayage'),
           ('c', '&Eacute;tat C &mdash; la carte d\'export, et l\'encodage',
            "Carte d'export ouverte sur le cote avec les reglages video et audio, previsualisation bloquee.",
            "Exports - etat C, la carte d'export", "la carte d'export")],
    paras=["<strong>Les réglages sont refaits sur ton retour.</strong> Résolution, cadence, codec et variante, débit, profondeur, codec audio, échantillonnage, pistes — plus le nom et la destination. Le vocabulaire et le groupement suivent ceux de Resolve : un terme inventé ici te coûterait une traduction mentale à chaque export.",
           "Ils ne tenaient plus dans un panneau d'atelier : c'est une <strong>carte, ouverte sur le côté</strong>, qui se referme sans perdre la saisie. Le preset devient un jeu complet de ces valeurs, modifiable ponctuellement sans être écrasé.",
           "<strong>Le panneau du balayage est vidé.</strong> Le timecode, le numéro de frame et la position de la poignée sont dans l'image : les répéter à droite ne disait rien de plus. Il ne reste que des contrôles.",
           "Sans le rush d'origine sur la machine, le son et le balayage ne sont pas grisés : ils sont absents. Au relink, les deux reviennent."],
    question="la liste des reglages : il en manque, ou l'un d'eux n'a pas sa place ici ?",
    governs="Flow 1, etapes 14 a 16 &middot; le climax du parcours"),

  dict(slug='key-comparaison', h2='Voir une frame de pres, et trancher', states='trois facons de regarder',
    shots=[('a', '&Eacute;tat A &mdash; la vue vignette unique, avec zoom',
            "Une frame seule en plein panneau, zoomee a 240 %, la bande des frames voisines en bas.",
            'Comparaison - etat A, vignette unique', 'la vue vignette unique'),
           ('b', '&Eacute;tat B &mdash; deux candidats pour la meme frame',
            "Deux candidats cote a cote, celui de gauche designe par un lisere pose hors de l'image.",
            'Comparaison - etat B, deux candidats', 'les deux candidats'),
           ],
    paras=["<strong>C'est la vue que tu demandais</strong> : on clique une vignette, la frame s'ouvre seule, plein panneau, et on zoome dedans. Les flèches passent à la voisine sans repasser par la grille.",
           "<strong>Le panneau de droite redevient une liste à cocher</strong>, comme tu l'as demandé — celle de l'atelier Extraction, la même forme pour le même geste. Le paragraphe d'explication et le bouton à libellé long ont disparu.",
           "Le second groupe fait le choix en bloc sur les 9 frames à plusieurs candidats. C'est un raccourci vers le même geste : il reste défaisable frame par frame.",
           "<strong>Un troisième état manque, et c'est volontaire.</strong> Tu penses que la bascule entre deux passes entières n'est pas une fonction listée — elle l'est, dans la spine, et je te cite la ligne plus bas. Mais tant que son terrain n'est pas tranché, je ne la dessine pas."],
    question="la bascule entre passes : on la restreint a la selection multiple, ou on la retire de la spine ?",
    governs='EPIC7-ARB-18 et 21 &middot; composition a la frame'),

  dict(slug='key-extraction-v3', h2="L'atelier Extraction, corrige", states='trois etats &middot; deux corrections',
    shots=[('a', '&Eacute;tat A &mdash; le selecteur de cadence, deplie',
            "Le selecteur ouvert listant les deux extractions existantes, et le panneau portant les raccourcis de cadence et un champ de saisie.",
            'Extraction - etat A, le selecteur', 'le selecteur de cadence'),
           ('b', '&Eacute;tat B &mdash; la galerie, sans aucune case a cocher',
            "Galerie ou deux frames sont hachurees et marquees ecartees, avec un filtre de vue dans la barre.",
            'Extraction - etat B, la galerie corrigee', 'la galerie corrigee'),
           ('c', '&Eacute;tat C &mdash; la meme galerie, vignettes agrandies',
            "La meme galerie en grandes vignettes, la taille se reglant par la loupe.",
            'Extraction - etat C, vignettes agrandies', 'les vignettes agrandies')],
    paras=["<strong>Ta correction est appliquée telle quelle</strong> : ce n'est pas toi qui écartes une frame, c'est la cadence demandée. Les cases à cocher ont disparu, le bouton « tout reprendre » aussi. Reste un <em>filtre de vue</em> — toutes, retenues, écartées — qui affiche et ne sélectionne rien.",
           "À côté du bouton, une ligne dit <em>pourquoi</em> deux frames tombent et <em>comment</em> les reprendre : passer à 25 fps, il n'y a pas d'autre moyen. Un signe seul, sans motif, n'apprend rien.",
           "<strong>Ta question reçoit sa réponse à droite.</strong> La cadence est une <em>valeur qu'on saisit</em>, pas un choix fermé : les pastilles ne sont que des raccourcis du projet, et « + raccourci » y ajoute celle qu'on vient de taper.",
           "Le sélecteur de gauche, lui, ne liste que les extractions qui <em>existent</em> — ici deux, parce que 50 n'a pas encore été extrait. Il ne crée rien, mais sa dernière ligne mène à la création. C'est la même séparation qu'entre le badge de cadence effective et le menu de qualité : constater d'un côté, décider de l'autre."],
    question="le champ de saisie et les raccourcis dans le panneau : c'est la que tu les attendais, ou tu veux pouvoir saisir une cadence directement depuis le selecteur du lecteur ?",
    governs='EPIC7-ARB-16, 17 et 20 &middot; fil ancre nº 13'),
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

CSS = (V1 / 'planche.css').read_text(encoding='utf-8')
JS = (V1 / 'planche.js').read_text(encoding='utf-8')
BODY = (ICI / 'vague3-body.html').read_text(encoding='utf-8').replace('__FRAMES__', '\n\n'.join(frames))

out = (
  '<title>Vague 3</title>\n'
  '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">\n'
  '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
  '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@400;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@500&display=swap">\n'
  f'<style id="css">\n{CSS}\n</style>\n'
  f'<div id="app">\n{BODY}\n</div>\n'
  f'<script id="app-js">\n{JS}\n</script>\n'
)
p = S / 'planche-vague3.html'
p.write_text(out, encoding='utf-8')
print(f'{p} {p.stat().st_size/1024/1024:.2f} MiB')
