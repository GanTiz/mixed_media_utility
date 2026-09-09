# -*- coding: utf-8 -*-
"""Mode Mouvement : le badge de cadence dans ses trois regimes — vague 2."""
import sys, pathlib
S = pathlib.Path('/tmp/claude-0/-home-user-mixed-media-utility/c54b30dd-4fc6-5b3c-9cf8-4e164b2f3aef/scratchpad')
sys.path.insert(0, str(S))
from picto import PICTOS as P
from transport import transport
from icones import ICONES as I
M = pathlib.Path('/home/user/mixed_media_utility/_bmad-output/planning-artifacts/ux-designs/ux-mixed_media_utility-2026-08-16/mockups')

RAIL = ('<div class="rail">' + P['dossier'] + P['rush'] + f'<span class="on">{P["lotr"]}</span>' + '</div>')
BIN = '''      <div class="bin">
        <div class="bin-head"><span class="bin-scope">Chutier</span><span class="meta">1 lot</span></div>
        <div class="portee">Contenu de <b>Lot reconstruit 12,5 fps</b></div>
        <div class="tree"><div class="node"><div class="row sel"><span class="exp none"></span><span class="puce"></span>%s<span class="nm">Lot reconstruit</span><span class="meta">9 f.</span></div></div></div>
      </div>''' % P['lotr']

TIMELINE = """        <div class="piste"><div class="tete" style="left:38%"></div></div>
          <div class="regle"><span>00:00:00:00</span><span>9 frames</span><span>00:00:00:18</span></div>"""
TRANSPORT = transport()

def ecran(titre, badge, qualite, bandeau='', note=''):
    return f'''
  <h2>{titre}</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">Exports &middot; Lot reconstruit 12,5 fps</span></div>
    <div class="app-body">
      <div class="nav">{RAIL}</div>
{BIN}
      <div class="work">
        <div class="wh">
          <div class="seg"><span>Galerie</span><span class="on">Lecteur</span></div>
          <div class="vue"><span class="b">{I["loupe"]}</span><span class="b">&minus;</span><span class="b">+</span></div>
          <div class="cad">{badge}{qualite}</div>
        </div>
        <div class="mat"><div class="scene"><span class="tc">00:00:00:07</span></div></div>
{bandeau}{TIMELINE}
{TRANSPORT}
      </div>
    </div>
  </div>
  {note}
'''

CADSEL = '<span class="cadsel">12,5 <span class="car">&#9662;</span></span>'
BADGE_OK = CADSEL + '<span class="cadb ok"><span class="p"></span>12,5</span>'
BADGE_KO = CADSEL + '<span class="cadb ko"><span class="p"></span>7,8</span>'
Q_PLEINE = '<span class="qual">pleine <span class="car">&#9662;</span></span>'
Q_DEMIE = '<span class="qual">demie <span class="car">&#9662;</span></span>'

BANDEAU = '''        <div class="bandeau">
          <span class="ic2">&#9888;</span>
          <p>La lecture ne se fait pas en temps reel. Reduis la qualite de visionnage.</p>
          <span class="x">Ne plus afficher</span><span class="x">Fermer</span>
        </div>
'''

a = ecran('Etat A &mdash; la cadence est tenue', BADGE_OK, Q_PLEINE,
  note='''<p class="caption">Vert : la cadence effective est celle qu'on vise, a la marge pres du
  previz en ligne de commande. Rien d'autre ne s'affiche &mdash; il n'y a rien a dire.</p>''')
b = ecran('Etat B &mdash; la cadence n\'est pas tenue', BADGE_KO, Q_PLEINE,
  note='''<p class="caption">Rouge, et la qualite affichee a cote dit pourquoi : <b class="k">pleine</b>.
  Le badge ne decide rien, il constate. Aucun bandeau pour l'instant : un rouge passager, sur un
  saut ou un changement de lot, ne merite pas qu'on interrompe la lecture.</p>''')
c = ecran('Etat C &mdash; cinq secondes de rouge : un seul bandeau, et il se refuse', BADGE_KO, Q_DEMIE,
  bandeau=BANDEAU,
  note='''<p class="caption">Le bandeau n'apparait qu'apres un rouge <i>prolonge</i>, une seule fois.
  Il se ferme, et il se desactive pour toute la session. Il se pose <b class="k">sous</b> la scene,
  jamais par-dessus l'image.</p>''')

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>Le badge constate, il ne decide pas.</b> Il
    affiche la cadence <i>effective</i> et la compare a la cadence visee, avec la marge du previz
    en ligne de commande. Vert : tenue. Rouge : pas tenue. C'est tout ce qu'il fait.</p></div>
    <div class="note"><span class="num">2</span><p><b>La qualite est un menu a cote, pas dans le
    badge.</b> Pleine, demie, quart, auto. C'est toi qui degrades, sauf en <i>auto</i>.</p></div>
    <div class="note"><span class="num">2b</span><p><b>Le selecteur de cadence est a gauche du
    badge</b> : il liste les extractions du meme rush, et en changer garde le timecode. C'est ce
    qui permet de comparer 12,5 et 25 sur le meme instant sans se replacer.</p></div>
    <div class="note"><span class="num">3</span><p><b>Cinq secondes de rouge, puis un seul
    bandeau.</b> Le seuil est le tien. En dessous, le rouge ne dit rien d'utile : il arrive au
    demarrage, sur un saut, au changement de lot. Le bandeau se ferme d'un geste et se desactive
    pour la session &mdash; il ne revient pas te chercher.</p></div>
    <div class="note"><span class="num">4</span><p><b>Ce qui se degrade, c'est l'image, jamais la
    cadence.</b> C'est le rythme qu'on juge a cet instant : une previz qui ralentit pour rester
    nette ne montre plus rien de ce qu'on est venu voir.</p></div>
  </div>
'''

TOKENS = (S / 'tokens.css').read_text(encoding='utf-8')
CSS = (S / 'v2-css.css').read_text(encoding='utf-8')
HTML = f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cadence et repli — maquette d'ecran cle</title>
<style>
/* ===========================================================================
   MAQUETTE D'ECRAN CLE — LE BADGE DE CADENCE (vague 2)
   Conception d'Egan, du 20 aout, prise telle quelle : un badge au-dessus du
   lecteur qui affiche la cadence EFFECTIVE, vert si elle est tenue, rouge
   sinon ; la qualite en menu voisin — pleine, demie, quart, auto ; et un
   bandeau UNIQUE apres un rouge prolonge, refermable et desactivable pour la
   session. « C'est l'utilisateur qui degrade la qualite, sauf en mode auto. »
   Trois etats parce qu'il y a trois regimes, et que le troisieme ne se
   comprend qu'apres avoir vu les deux premiers.
   =========================================================================== */
{TOKENS}
{CSS}
</style>
</head>
<body>
<div class="sheet">
  <h1>La cadence, et ce qu'on fait quand elle lache</h1>
  <p class="sub">Le bandeau permanent est mort le 20 aout : il etait lourd, et il decidait a ta
  place. A la place, <b class="k">un badge qui constate</b> et <b class="k">un menu qui te laisse
  choisir</b>. Le bandeau ne survit que comme avertissement unique, apres un rouge prolonge.</p>
{a}{b}{c}{notes}
</div>
</body>
</html>
'''
(M / 'key-cadence.html').write_text(HTML, encoding='utf-8')
print(f'{(M / "key-cadence.html").stat().st_size/1024:.0f} Ko')
