# -*- coding: utf-8 -*-
"""Planche de contact de la vague 3 : trois ecrans, neuf etats.

Les retours deja poses par Egan sont reinjectes depuis `retours-v5.json` --
republier une planche sans cela EFFACE ses retours, c'est le piege le plus
couteux de ce dispositif.
"""
import base64, json, pathlib

ICI = pathlib.Path(__file__).resolve().parent
S = pathlib.Path('/tmp/claude-0/-home-user-mixed-media-utility/c54b30dd-4fc6-5b3c-9cf8-4e164b2f3aef/scratchpad')
V1 = S / 'v1'

def img(slug, state):
    return 'base64,' + base64.b64encode((S / f'z-{slug}-{state}.png').read_bytes()).decode()

RJ = ICI / 'retours-v5.json'
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
  dict(slug='key-preferences', h2='Les Preferences', states='trois etats &middot; deux regles',
    shots=[('a', '&Eacute;tat A &mdash; Jugement : ce qui ne se regle pas, et pourquoi',
            "Section Jugement des preferences, avec deux lignes figees portant la mention non modifiable.",
            'Preferences - etat A, Jugement', 'la section Jugement'),
           ('b', '&Eacute;tat B &mdash; Previsualisation et taches',
            "Qualite par defaut, repli automatique, seuil du bandeau a 5 s, et les reglages de la file des taches.",
            'Preferences - etat B, Previsualisation', 'la previsualisation'),
           ('c', '&Eacute;tat C &mdash; Fichiers et avance',
            "Dossier de projets par defaut, recherche des rushes deplaces, chemin de ffmpeg et journal.",
            'Preferences - etat C, Fichiers', 'les fichiers et l\'avance')],
    paras=["Tu m'as laisse proposer. La proposition tient a <strong>deux regles</strong>, et tout le reste en decoule.",
           "<strong>La premiere : ce qui garantit le jugement n'est pas reglable, mais reste visible.</strong> La conversion colorimetrique desactivee, le fond neutre des zones d'image, le fait que le repli de qualite <em>se voie</em> : trois lignes figees, chacune avec son motif a cote. Les cacher ferait chercher ; les ouvrir casserait le produit.",
           "<strong>La seconde : les Preferences ne portent que ce qui vaut pour tous les projets.</strong> Les cadences raccourcies, le preset d'export et le profil de scanner vivent <em>dans le projet</em> — sinon ouvrir un autre film changerait les reglages du precedent sans rien dire.",
           "Deux de tes decisions sont ici, modifiables : le seuil de cinq secondes du bandeau de cadence, et le seuil de largeur sous lequel la file des taches se superpose. Et un endroit pour <strong>rallumer les avertissements</strong> desactives — sans lui, cette facilite devient un piege."],
    question="la liste des sections &mdash; Jugement, Previsualisation, Taches, Fichiers, Avance &mdash; te parait juste, ou il manque une famille ?",
    governs='Spine : contenu renvoye a un second temps, leve ici'),

  dict(slug='key-clic-droit', h2='Le menu contextuel', states='trois etats &middot; l\'inventaire',
    shots=[('a', '&Eacute;tat A &mdash; clic droit sur un rush du chutier',
            "Menu contextuel sur un rush, portant rattacher a, relinker, renommer, et une entree grisee expliquee.",
            'Clic droit - etat A, un rush', 'le clic droit sur un rush'),
           ('b', '&Eacute;tat B &mdash; sur un marqueur, et sur une vignette',
            "Deux menus contextuels : sur une vignette de galerie, et sur un marqueur de la chronologie.",
            'Clic droit - etat B, marqueur et vignette', 'le marqueur et la vignette'),
           ('c', '&Eacute;tat C &mdash; sur une carte de tache, et sur un projet',
            "Menus contextuels sur une tache en cours et sur une ligne de la liste de projets.",
            'Clic droit - etat C, tache et projet', 'la tache et le projet')],
    paras=["L'inventaire que tu attendais depuis le 22 aout, etendu au-dela du chutier : partout ou une commande a ete retiree de l'interface au profit du clic droit.",
           "<strong>Premiere regle : il ne cache jamais une action unique.</strong> Chaque entree est soit une variante d'un geste possible ailleurs, soit une action rare. Une commande qu'on ne peut atteindre que par clic droit est introuvable pour qui ne pense pas a essayer — la seule exception est <em>rattacher a</em>, que tu as voulue la.",
           "<strong>Seconde regle : une entree grisee dit pourquoi</strong>, dans le menu et non dans une legende. <em>Supprimer les fichiers</em> est grise parce que le rush est hors du dossier de travail ; <em>comparer les candidats</em> parce que cette frame n'en a qu'un.",
           "Le titre nomme l'objet : dans un chutier a six niveaux, savoir sur quoi on a clique n'est pas un detail. Et le raccourci clavier est affiche — c'est ce qui fait sortir du clic droit."],
    question="il manque des entrees ? Le clic droit sur la zone tampon, sur une planche de calibration ou sur un scan n'est pas encore couvert.",
    governs='deferred-work.md &middot; inventaire du clic droit, ouvert le 22 aout'),

  dict(slug='key-barre-menus', h2='La barre de menus systeme', states='trois etats &middot; macOS et Windows',
    shots=[('a', '&Eacute;tat A &mdash; Fichier, sur macOS',
            "Barre de menus macOS avec le menu Fichier ouvert : nouveau projet, ouvrir, importer, recents.",
            'Barre de menus - etat A, Fichier', 'le menu Fichier'),
           ('b', '&Eacute;tat B &mdash; Affichage, et le menu applicatif',
            "Le menu Affichage avec ses cases a cocher, et le menu mmu portant Preferences avec Cmd virgule.",
            'Barre de menus - etat B, Affichage', 'le menu Affichage'),
           ('c', '&Eacute;tat C &mdash; Windows : les memes commandes, une autre place',
            "Le menu Outils de Windows portant les Preferences, et le menu Aller identique sur les deux systemes.",
            'Barre de menus - etat C, Windows', 'la version Windows')],
    paras=["Pertinent, oui, et pour une raison precise : sur macOS, une application sans barre de menus ne se pilote pas au clavier par le systeme, n'apparait pas dans le repertoire des raccourcis, et ne repond pas aux conventions qu'on applique sans y penser.",
           "<strong>La regle : la barre ne cree aucune fonction.</strong> Elle donne un second chemin, clavier et decouvrable, vers ce que les ateliers portent deja. Deux exceptions seulement, imposees par le systeme : <em>A propos</em> et <em>Quitter</em>.",
           "<strong>Les cases a cocher lisent l'ecran</strong> — chutier ouvert, panneau ouvert, file des taches fermee. C'est ce qui fait de ce menu autre chose qu'une liste de raccourcis.",
           "Une seule difference entre les deux systemes, et elle est assumee : <em>Preferences</em> est sous <strong>mmu</strong> avec <code>&#8984;,</code> sur macOS, sous <strong>Outils</strong> avec <code>Ctrl+,</code> sur Windows. Imposer la meme place partout ferait chercher a la moitie des utilisateurs."],
    question="<i>Aller au timecode</i> est la seule commande sans equivalent a l'ecran &mdash; taper un timecode et y sauter. Elle merite un chemin visible : dans le bus de transport, ou en cliquant le timecode de la chronologie ?",
    governs='Qt/PySide6 &middot; macOS 12+ et Windows 10+'),
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
BODY = (ICI / 'vague5-body.html').read_text(encoding='utf-8').replace('__FRAMES__', '\n\n'.join(frames))

out = (
  '<title>Vague 5</title>\n'
  '<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=5">\n'
  '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
  '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Chivo:wght@400;600;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&family=JetBrains+Mono:wght@500&display=swap">\n'
  f'<style id="css">\n{CSS}\n</style>\n'
  f'<div id="app">\n{BODY}\n</div>\n'
  f'<script id="app-js">\n{JS}\n</script>\n'
)
p = S / 'planche-vague5.html'
p.write_text(out, encoding='utf-8')
print(f'{p} {p.stat().st_size/1024/1024:.2f} MiB')
