# -*- coding: utf-8 -*-
"""Atelier Extraction — vague 2."""
import sys, pathlib
S = pathlib.Path('/tmp/claude-0/-home-user-mixed-media-utility/c54b30dd-4fc6-5b3c-9cf8-4e164b2f3aef/scratchpad')
sys.path.insert(0, str(S))
from picto import PICTOS as P
M = pathlib.Path('/home/user/mixed_media_utility/_bmad-output/planning-artifacts/ux-designs/ux-mixed_media_utility-2026-08-16/mockups')

def row(kind, nom, meta='', *, ouvert=None, puce=None, sel=False, enfants=''):
    exp = '<span class="exp none"></span>'
    if ouvert is True: exp = '<span class="exp">&minus;</span>'
    elif ouvert is False: exp = '<span class="exp">+</span>'
    pu = f'<span class="puce {puce}"></span>' if puce is not None else ''
    m = f'<span class="meta">{meta}</span>' if meta else ''
    return (f'<div class="node"><div class="row{" sel" if sel else ""}">{exp}{pu}{P[kind]}'
            f'<span class="nm">{nom}</span>{m}</div>'
            + (f'<div class="kids">{enfants}</div>' if enfants else '') + '</div>')

RAIL = ('<div class="rail">' + P['dossier'] + f'<span class="on">{P["rush"]}</span>' + P['extr'] + '</div>')

arbre = row('rush', 'TEST_FILE_12p5.mov', '1080p', ouvert=True, puce='', sel=True, enfants=(
    row('extr', 'Extraction 12,5 fps', '9 f.', puce='')
    + row('extr', 'Extraction 25 fps', '18 f.', puce='')))

TRANSPORT = '''        <div class="transport">
          <span class="grp">
            <span class="tb" title="Aller au debut">&#124;&#9664;</span>
            <span class="tb vit" title="Reculer, appuis successifs">&#9664;&#9664; x4</span>
            <span class="tb" title="Image precedente">&#9666;&#124;</span>
            <span class="tb play" title="Lecture ou pause">&#9654;</span>
            <span class="tb" title="Image suivante">&#124;&#9656;</span>
            <span class="tb" title="Avancer, appuis successifs">&#9654;&#9654;</span>
            <span class="tb" title="Aller a la fin">&#9654;&#124;</span>
          </span>
          <span class="sepv"></span>
          <span class="grp"><span class="lb">in / out</span>
            <span class="tb on">&#91;</span><span class="tb on">&#93;</span>
            <span class="tb">aller au in</span><span class="tb">retirer</span>
          </span>
          <span class="sepv"></span>
          <span class="grp"><span class="lb">marqueurs</span>
            <span class="tb">+</span><span class="tb">&#9666;</span><span class="tb">&#9656;</span>
          </span>
          <span class="sepv"></span>
          <span class="tb on" title="Lecture en boucle">&#8635;</span>
          <span class="sepv"></span>
          <span class="vol"><span class="lb">vol</span><span class="tb">&#9834;</span><span class="bar"></span></span>
        </div>'''

TIMELINE = '''        <div class="timeline">
          <div class="piste">
            <div class="dedans" style="left:18%; right:34%"></div>
            <div class="mk2" style="left:31%"></div>
            <div class="mk2" style="left:52%"></div>
            <div class="tete" style="left:42%"></div>
          </div>
          <div class="regle"><span>00:00:00:00</span><span>in 00:00:08:04 &middot; out 00:00:21:12</span><span>00:00:32:00</span></div>
        </div>'''

etat_a = f'''
  <h2>Etat A &mdash; mode Mouvement : poser les bornes sur le rush</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">Extraction &middot; TEST_FILE_12p5.mov</span></div>
    <div class="app-body">
      <div class="nav">{RAIL}</div>
      <div class="bin">
        <div class="bin-head"><span class="bin-scope">Chutier</span><span class="meta">1 rush</span></div>
        <div class="portee">Contenu de <b>sequence 3</b></div>
        <div class="tree">{arbre}</div>
      </div>
      <div class="work">
        <div class="wh">
          <div class="seg"><span class="off" title="Un rush n'a pas de zones">Zones</span><span>Images</span><span class="on">Mouvement</span></div>
          <div class="vue"><span class="b">&minus;</span><span>ajuste</span><span class="b">+</span><span class="b">Largeur</span></div>
          <div class="cad">
            <span class="cadb ok"><span class="p"></span>25,0 im/s</span>
            <span class="qual">pleine <span class="car">&#9662;</span></span>
          </div>
        </div>
        <div class="mat"><div class="scene"><span class="tc">00:00:12:14</span></div></div>
{TIMELINE}
{TRANSPORT}
      </div>
      <div class="panel">
        <h3>Extraire des frames</h3>
        <p>Le rush joue a sa cadence. Les bornes fixent ce qu'on extrait.</p>
        <div class="opt on"><span class="radio"></span><span class="tt">12,5 fps</span><span class="meta">167 f.</span></div>
        <div class="opt"><span class="radio"></span><span class="tt">25 fps</span><span class="meta">334 f.</span></div>
        <div class="opt"><span class="radio"></span><span class="tt">50 fps</span><span class="meta">668 f.</span></div>
        <div class="recap">
          entree 00:00:08:04<br>
          sortie 00:00:21:12<br>
          duree 00:00:13:08 &middot; 2 marqueurs
        </div>
        <button class="btn" type="button">Extraire 167 frames</button>
        <p class="hint">Le nombre annonce est celui des bornes posees, pas du rush entier. Changer
        une borne le change sous tes yeux.</p>
      </div>
    </div>
  </div>
  <p class="caption"><b class="k">Zones</b> est eteint : un rush n'a pas de decoupage a montrer.
  Les modes disponibles dependent de l'objet regarde, et l'interface le dit en les grisant plutot
  qu'en les cachant &mdash; sinon la barre changerait de forme d'un objet a l'autre.</p>
'''

def gc(n, tc, prise=True, hors=False):
    cls = 'gc' + ('' if prise else ' hors')
    pu = '<span class="puce all"></span>' if prise else '<span class="puce"></span>'
    return (f'<div class="{cls}"><div class="im"><span class="no">{n}</span></div>{pu}'
            f'<div class="fo"><span>{tc}</span><span>1008&times;567</span></div></div>')

galerie = ''.join(gc(i, f'00:00:{8 + i//2:02d}:{(i*4) % 24:02d}', prise=(i not in (4, 9))) for i in range(1, 11))

etat_b = f'''
  <h2>Etat B &mdash; mode Images : la galerie des frames a extraire</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">Extraction &middot; TEST_FILE_12p5.mov &middot; 12,5 fps</span></div>
    <div class="app-body">
      <div class="nav">{RAIL}</div>
      <div class="bin">
        <div class="bin-head"><span class="bin-scope">Chutier</span><span class="meta">1 rush</span></div>
        <div class="portee">Contenu de <b>sequence 3</b></div>
        <div class="tree">{arbre}</div>
      </div>
      <div class="work">
        <div class="wh">
          <div class="seg"><span class="off">Zones</span><span class="on">Images</span><span>Mouvement</span></div>
          <div class="vue"><span class="b">&minus;</span><span>vignettes</span><span class="b">+</span></div>
          <span class="px">167 frames &middot; 165 retenues</span>
        </div>
        <div class="gal">{galerie}</div>
      </div>
      <div class="panel">
        <h3>12,5 fps &mdash; 167 frames</h3>
        <div class="recap">
          entree 00:00:08:04 &middot; sortie 00:00:21:12<br>
          165 retenues &middot; 2 ecartees<br>
          1008&times;567 &middot; ratio verrouille
        </div>
        <button class="btn" type="button">Extraire 165 frames</button>
        <button class="btn ghost" type="button">Tout reprendre</button>
        <p class="hint">Decocher une frame la retire de l'extraction sans toucher au rush. Le
        bouton suit : il annonce toujours ce qu'il va reellement produire.</p>
      </div>
    </div>
  </div>
  <p class="caption">Meme coquille, meme chutier, meme barre : seul le mode change. C'est ce qui
  permet de passer d'un atelier a l'autre sans reapprendre l'ecran.</p>
'''

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>Les trois modes sont la coquille commune.</b>
    <i>Zones</i> montre un decoupage, <i>Images</i> montre des frames, <i>Mouvement</i> les joue.
    Tous les ateliers portent la meme barre ; ce qui change, c'est ce que l'objet a a montrer.</p></div>
    <div class="note"><span class="num">2</span><p><b>Le transport, au complet.</b> Lecture et
    pause, image par image dans les deux sens, avance et recul avec x2, x4, x8 par appuis
    successifs &mdash; le recul est une vraie lecture arriere, pas un saut &mdash; points d'entree
    et de sortie (poser, y aller, retirer), marqueurs, lecture en boucle, volume.</p></div>
    <div class="note"><span class="num">3</span><p><b>Le badge dit la cadence effective</b>, pas la
    cadence visee : 25,0 im/s en vert parce qu'elle est tenue. La qualite est un menu <i>a cote</i>
    du badge, pas dedans &mdash; pleine, demie, quart, auto &mdash; et c'est toi qui la choisis.</p></div>
    <div class="note"><span class="num">4</span><p><b>L'action porte son cardinal, toujours.</b>
    « Extraire 167 frames », puis « Extraire 165 frames » quand deux sont ecartees. Un bouton qui
    annonce autre chose que ce qu'il fait est un piege, surtout sur une operation longue.</p></div>
  </div>
'''

TOKENS = (S / 'tokens.css').read_text(encoding='utf-8')
CSS = (S / 'v2-css.css').read_text(encoding='utf-8')
HTML = f'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Atelier Extraction — maquette d'ecran cle</title>
<style>
/* ===========================================================================
   MAQUETTE D'ECRAN CLE — L'ATELIER EXTRACTION (vague 2)
   Egan : « je ne vois absolument pas en quoi extraction herite de pdf ? Rien a
   voir. » En effet : on y regarde un rush bouger, on y pose des bornes, et on
   en tire des frames. Rien de la mise en page d'une planche.
   Porte la coquille commune decidee le 22 aout : deux panneaux, et trois modes
   de regard — Zones, Images, Mouvement — au lieu des quatre onglets de page.
   Porte aussi la liste complete des controles de transport donnee par Egan, et
   le badge de cadence avec la qualite en menu voisin.
   =========================================================================== */
{TOKENS}
{CSS}
</style>
</head>
<body>
<div class="sheet">
  <h1>L'atelier Extraction</h1>
  <p class="sub">Un rush, des bornes, des frames. <b class="k">Trois modes de regard</b> plutot que
  quatre onglets de page : on ne change pas d'atelier, on change de ce qu'on regarde. La barre est
  la meme partout &mdash; c'est ce qui permet de passer d'un ecran a l'autre sans le reapprendre.</p>
{etat_a}
{etat_b}
{notes}
</div>
</body>
</html>
'''
(M / 'key-extraction.html').write_text(HTML, encoding='utf-8')
print(f'{(M / "key-extraction.html").stat().st_size/1024:.0f} Ko')
