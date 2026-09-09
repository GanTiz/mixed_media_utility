# -*- coding: utf-8 -*-
"""Planche de contact de la vague 1 : trois ecrans, six etats, retours par vignette."""
import base64, json, pathlib

S = pathlib.Path('/tmp/claude-0/-home-user-mixed-media-utility/c54b30dd-4fc6-5b3c-9cf8-4e164b2f3aef/scratchpad')

def img(slug, state):
    return 'data:image/png;base64,' + base64.b64encode((S / f'z-{slug}-{state}.png').read_bytes()).decode()

RETOURS = json.load(open(S / 'retours-v1b.json', encoding='utf-8'))

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
  dict(slug='key-chutier-v2', h2='Le chutier, version 2', states='revise &middot; six retours appliques',
    shots=[('a', "&Eacute;tat A &mdash; le panneau lateral designe, le chutier montre",
            "Deux panneaux : l'arborescence a gauche, et le chutier qui porte le contenu de la sequence designee.",
            'Chutier - etat A, deux panneaux', 'les deux panneaux'),
           ('b', '&Eacute;tat B &mdash; un lot designe, le panneau replie',
            "Le panneau lateral replie en pictogrammes, le chutier borne au contenu d'une extraction, un media en attente et l'import qui demande.",
            'Chutier - etat B, panneau replie', 'le panneau replie')],
    paras=["<strong>Ton fil sur Resolve a défait le mode « entrer dans ».</strong> Tu avais raison : ce n'était pas une opération à inventer. L'arborescence passe dans un <strong>panneau latéral rétractable</strong> et sert à se placer ; le chutier montre le <strong>contenu de l'objet désigné</strong>. Clique <em>sequence 3</em> à gauche, le chutier porte tous ses rushes et leurs enfants ; clique une extraction, il ne porte que cette extraction. La question « quelle opération fait qu'on entre dans une branche » n'a plus lieu d'être, et le fil d'Ariane disparaît : le panneau latéral <em>est</em> le fil, et il est toujours là.",
           "S'ajoutent le mode <strong>plein écran</strong>, la poignée de largeur entre les deux panneaux, et le repli automatique sous une certaine largeur de fenêtre &mdash; le chutier passe avant l'arborescence. La portée est écrite au-dessus de l'arbre : sans elle, un chutier borné ressemble à un chutier vide.",
           "Le reste de tes six retours tient : pictogrammes au trait, puce de sélection à trois états, le signe + dont l'<em>absence</em> dit qu'il n'y a pas d'enfant, les traits qui s'arrêtent au dernier objet, les filtres repliés, et un lot reconstruit qui compte des <strong>frames</strong>.",
           "État B : un média confirmé comme scan <strong>reste dans la file d'attente</strong> et n'en sort qu'au décodage de son QR &mdash; avec la saisie manuelle du parent en sortie de secours. Et l'import <strong>demande</strong> au lieu de déduire, puisque la détection automatique n'est pas prioritaire."],
    question="le panneau lateral a la bonne largeur par defaut, ou faut-il qu'il s'ouvre plus etroit ?",
    governs='Retours du 21/08 &middot; EPIC7-ARB-3, 4, 9, 10, 13, 14'),

  dict(slug='key-lot-hybride', h2="L'extraction composite", states='refaite sur ton parcours &middot; trois temps',
    shots=[('a', '&Eacute;tat A &mdash; selectionner des scans, nommer ce qu\'on en fait',
            "Trois scans coches sous une planche, action creer une extraction composite, fenetre de nommage et de scan prioritaire.",
            'Composite - etat A, creation', 'la creation'),
           ('b', '&Eacute;tat B &mdash; la galerie dit ou il reste un choix',
            "Galerie du lot composite : pastilles comptant les candidats sur quatre frames, deux choix verrouilles, une mire.",
            'Composite - etat B, la galerie', 'la galerie'),
           ('c', '&Eacute;tat C &mdash; comparer, quand il y a trois candidats',
            "Comparaison au volet entre deux des trois candidats, choix des deux affiches, verrou du choix.",
            'Composite - etat C, comparer', 'la comparaison')],
    paras=["Ton parcours a défait ma version, et il avait raison de la défaire. Le point d'entrée n'est pas l'écran de comparaison : on <strong>sélectionne plusieurs scans</strong>, l'action devient <em>créer une extraction composite</em>, une fenêtre nomme le lot et choisit le <strong>scan prioritaire</strong> sur les doublons. C'est ensuite la galerie qui signale où il reste un choix, par une pastille qui compte les candidats.",
           "<strong>Trois choses ont disparu.</strong> Le mode automatique &mdash; <em>« c'est toujours un choix utilisateur, avec un défaut éventuel mais pas de critère technique »</em>. Les mesures de netteté et de marqueurs lus sur l'écran de décision, dans la foulée : c'est l'image qui tranche, sous tes yeux. Et le mode A/B, qui ne faisait rien que le volet ne fasse mieux.",
           "Le verrou que tu aimais est là : un choix verrouillé résiste au changement de scan prioritaire, ce qui te laisse changer d'avis en bloc sans perdre les frames déjà tranchées à la main. Au-delà de deux candidats, tu choisis les deux que le volet compare ; le côte à côte les montre tous."],
    question="le verrou sous forme de point vert sur la vignette, est-ce assez visible &mdash; ou faut-il qu'il se voie aussi dans la comparaison ?",
    governs="Retours du 21/08 &middot; parcours decrit par Egan"),

  dict(slug='key-scan-v2', h2='Atelier Scan, version 2', states='deux verrous &middot; navigation de pages',
    shots=[('a', '&Eacute;tat A &mdash; QR lu, mais il manque un marqueur',
            "Atelier Scan : identite lue, geometrie a trois marqueurs sur quatre, proposition des zones bloquee.",
            'Scan v2 - etat A', 'le verrou de geometrie'),
           ('b', '&Eacute;tat B &mdash; les deux verrous verts, et la bande de pages',
            "Atelier Scan : six zones proposees, bande de vignettes de pages, extraction du lot entier.",
            'Scan v2 - etat B', 'les zones et la navigation')],
    paras=["<strong>Le ratio est verrouillé, et la taille reste une.</strong> Tu as attrapé un vrai défaut : ma zone ajustée à la main ne faisait pas la même taille que les cinq autres. Déplacer ou retailler une zone ne change désormais ni son rapport ni ses dimensions &mdash; les 54 zones d'un lot ont exactement la même taille. Sans ce verrou, une frame retouchée sortirait au format des autres après mise à l'échelle, et le lot perdrait son identité sans que rien ne le signale.",
           "Le bouton portait les six zones de la page affichée : il porte maintenant <strong>le lot entier</strong> &mdash; 54 TIFF &mdash; avec la page seule en second bouton. Sélectionner la planche parente vaut sélectionner toutes ses pages.",
           "La navigation de page est sous la main : une bande de vignettes, les flèches, et l'état de chaque page &mdash; les hachures disent <em>pas encore scannée</em>. Le numéro de page reconnu s'affiche et se corrige : sans ça, un scan en images déposé en désordre écrirait les frames sur les mauvais timecodes.",
           "<strong>Ta réserve est inscrite dans la maquette</strong> : cette planche n'est pas un gabarit de production. La mise en page sera réajustée sur le vrai template avant développement."],
    question="la bande de pages en bas, ou plutot en colonne a gauche pres du chutier ?",
    governs='Retours du 21/08 &middot; A7, A8, A9, A10'),
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
BODY = (S / 'vague1-body.html').read_text(encoding='utf-8').replace('__FRAMES__', '\n\n'.join(frames))

out = (
  '<title>Vague 1</title>\n'
  '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">\n'
  '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
  '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@400;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@500&display=swap">\n'
  f'<style id="css">\n{CSS}\n</style>\n'
  f'<div id="app">\n{BODY}\n</div>\n'
  f'<script id="app-js">\n{JS}\n</script>\n'
)
p = S / 'planche-vague1.html'
p.write_text(out, encoding='utf-8')
print(f'{p.stat().st_size/1024/1024:.2f} MiB')
