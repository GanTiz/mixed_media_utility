# -*- coding: utf-8 -*-
"""Planche de contact de la vague 3 : trois ecrans, neuf etats.

Les retours deja poses par Egan sont reinjectes depuis `retours-v4.json` --
republier une planche sans cela EFFACE ses retours, c'est le piege le plus
couteux de ce dispositif.
"""
import base64, json, pathlib

ICI = pathlib.Path(__file__).resolve().parent
S = pathlib.Path('/tmp/claude-0/-home-user-mixed-media-utility/c54b30dd-4fc6-5b3c-9cf8-4e164b2f3aef/scratchpad')
V1 = S / 'v1'

def img(slug, state):
    return 'base64,' + base64.b64encode((S / f'z-{slug}-{state}.png').read_bytes()).decode()

RJ = ICI / 'retours-v4.json'
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
  dict(slug='key-taches', h2='Les cartes de taches', states='trois etats &middot; toutes fonctions confondues',
    shots=[('a', '&Eacute;tat A &mdash; la file, trois fonctions en meme temps',
            "File des taches avec un encodage, une extraction et une detection en cours, chacune avec sa progression.",
            'Taches - etat A, trois fonctions', 'la file de taches'),
           ('b', '&Eacute;tat B &mdash; terminees, et une qui a echoue',
            "File montrant deux taches terminees avec leurs boutons, et une echouee portant son code de refus.",
            'Taches - etat B, terminees et echec', 'les taches terminees'),
           ('c', '&Eacute;tat C &mdash; retrecir la scene, ou se superposer',
            "Deux mini-ecrans cote a cote : a gauche la file retrecit l'image, a droite elle flotte au-dessus.",
            'Taches - etat C, la question ouverte', 'la place de la file')],
    paras=["<strong>C'est la surface que tu as nommee.</strong> Elle etait dans l'architecture d'information depuis le debut — « file des taches en cours et terminees, toutes fonctions confondues » — mais elle n'apparaissait qu'en arriere-plan d'une autre maquette, jamais seule. Tu avais raison de dire qu'on ne l'avait pas revue.",
           "L'ordre des elements vient de la spine et ne se reamenage pas : <em>fonction, objet, barre, faits sur total, temps passe, temps restant</em>. C'est ce qu'on lit en diagonale quand trois choses tournent.",
           "<strong>Une extraction n'ouvre qu'un dossier</strong> — elle rend une collection de frames, il n'y a pas de fichier a ouvrir. Un encodage rend un master : les deux boutons ont un objet. La carte suit le resultat, pas la fonction.",
           "L'echec porte son motif en verbatim : <code>LOT_INCOMPLET</code> vient de <code>encode.ENCODE_REFUSAL_CODES</code>, affiche tel quel. Et il arrive a zero frame ecrite — le coeur verifie avant d'ecrire.",
           "<strong>Et la jauge de l'encodage n'etait pas un mecanisme a part</strong> : ce que j'avais pose sur la previz a la vague 3 est cette carte-la, vue depuis l'atelier. Il n'y a qu'une seule forme."],
    question="l'etat C pose une question que la spine laisse ouverte depuis le debut : la file <b>retrecit-elle la scene</b> (l'image change de taille pendant que tu la juges) ou <b>se superpose-t-elle</b> (elle cache un coin) ?",
    governs='EPIC7-ARB-23 &middot; Panneau de progression, contrat de la spine'),

  dict(slug='key-projet', h2="L'ecran de gestion de projet", states='trois etats &middot; le seuil',
    shots=[('a', '&Eacute;tat A &mdash; le seuil de chaque lancement',
            "Liste des projets recents, le dernier en tete avec un lisere, et deux actions a droite.",
            'Projet - etat A, la liste', 'la liste des projets'),
           ('b', '&Eacute;tat B &mdash; creer, c\'est designer un dossier',
            "Formulaire de creation : un nom de film et un dossier de travail, avec l'avertissement sur ce qu'il contiendra.",
            'Projet - etat B, la creation', 'la creation de projet'),
           ('c', '&Eacute;tat C &mdash; les rushes manquent, le projet s\'ouvre',
            "Un projet dont quatre rushes sur six sont absents, avec le bouton Ouvrir plein.",
            'Projet - etat C, rushes absents', 'les rushes absents')],
    paras=["Le premier ecran de chaque lancement, et le seul qui ne soit pas un atelier. La spine le classait « une liste et deux actions ; la densite n'y fait rien » — c'est vrai de la liste, et faux de deux points qui ne se voient qu'en le dessinant.",
           "<strong>Le premier : ce que creer demande.</strong> Un nom et un dossier, rien d'autre. La ligne d'avertissement est le seul texte legitime du panneau — elle dit pourquoi ce dossier ne contiendra pas tes rushes.",
           "<strong>Le second : un projet aux rushes absents s'ouvre quand meme.</strong> C'est le parcours d'Ines, qui recoit le projet sans le disque. Le contour rouge informe, il n'interdit pas — un aplat rouge ou un bouton grise laisseraient croire le contraire.",
           "Le dernier projet est <em>en tete</em>, pas preselectionne : un lisere le distingue, aucune touche ne l'ouvre. La difference compte quand deux projets portent des noms proches."],
    question="les quatre lignes de la liste : nom, chemin, date, et le signe des rushes absents &mdash; il manque quelque chose que tu regardes avant d'ouvrir ?",
    governs="Spine : dernier projet en tete &middot; aucun saut direct dans un atelier"),

  dict(slug='key-modales', h2='Les modales', states='trois etats &middot; un seul niveau',
    shots=[('a', '&Eacute;tat A &mdash; confirmer une extraction',
            "Modale avec les cadences cochables, leurs poids, les bornes, et l'espace disque annonce en pied.",
            'Modales - etat A, extraction', "la modale d'extraction"),
           ('b', '&Eacute;tat B &mdash; ecraser un lot existant',
            "Modale nommant ce qui serait detruit, avec Garder les deux en bouton plein et Ecraser en creux rouge.",
            'Modales - etat B, ecrasement', "la modale d'ecrasement"),
           ('c', '&Eacute;tat C &mdash; enregistrer une calibration de scanner',
            "Modale avec nom du scanner, resolution, format, et un commentaire libre sur les reglages.",
            'Modales - etat C, calibration', 'la modale de calibration')],
    paras=["Les trois seuls endroits ou une ecriture est consentie. <strong>Un seul niveau</strong> : une modale n'en ouvre jamais une autre. Et le consentement se rejoue integralement au lancement — ce qu'affiche la previz, si frais soit-il, n'autorise rien.",
           "<strong>L'espace disque est annonce avant, pas decouvert a l'echec.</strong> Une extraction TIFF remplit un disque en quelques minutes ; le chiffre est a cote du bouton, avec ce qui reste libre sur le volume vise.",
           "<strong>L'ecrasement nomme ce qu'il detruit</strong> — le nombre, la taille, la date, le chemin — au lieu d'une phrase generale sur laquelle on ne peut pas decider. Et le bouton plein est <em>Garder les deux</em> : l'emphase visuelle ne va jamais a la destruction.",
           "Le commentaire libre de la calibration n'est pas un champ de confort : les reglages d'un scanner ne se lisent nulle part dans le fichier produit. Sans lui, on ne sait pas six mois plus tard pourquoi deux calibrations du meme materiel divergent."],
    question="la modale d'extraction : les cadences cochables, l'espace disque et les bornes suffisent, ou tu veux y choisir aussi la destination ?",
    governs='Spine : 1 niveau &middot; la previz n\'autorise rien'),
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
BODY = (ICI / 'vague4-body.html').read_text(encoding='utf-8').replace('__FRAMES__', '\n\n'.join(frames))

out = (
  '<title>Vague 4</title>\n'
  '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">\n'
  '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
  '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@400;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@500&display=swap">\n'
  f'<style id="css">\n{CSS}\n</style>\n'
  f'<div id="app">\n{BODY}\n</div>\n'
  f'<script id="app-js">\n{JS}\n</script>\n'
)
p = S / 'planche-vague4.html'
p.write_text(out, encoding='utf-8')
print(f'{p} {p.stat().st_size/1024/1024:.2f} MiB')
