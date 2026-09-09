# -*- coding: utf-8 -*-
"""Atelier Extraction — reprise de la vague 2, corrigee.

Deux retours du 22 aout portent sur cet ecran et sur lui seul :

* EPIC7-ARB-16 -- l'ecart d'une frame est CALCULE par la cadence demandee.
  La vague 2 le presentait comme un choix : des cases a cocher, un bouton
  « tout reprendre », et une note qui disait « decocher une frame la retire de
  l'extraction ». Tout cela disparait au profit d'un filtre de vue, qui montre
  ou masque sans rien selectionner ;
* EPIC7-ARB-17 -- le bouton s'appelle « ajuster ».

Et le fil ancre nº 13 restait ouvert : « comment passe-t-on d'une cadence a
l'autre en relecture ? ». L'etat A y repond, selecteur deplie.
"""
from coquille import (MOCKUPS, I, barre_vue, onglets, rail, noeud, chutier,
                      page, transport, lg, groupe, avis, replier)

ARBRE = noeud('rush', 'TEST_FILE_12p5.mov', '1080p', ouvert=True, sel=True, enfants=(
    noeud('extr', 'Extraction 12,5 fps', '167 f.')
    + noeud('extr', 'Extraction 25 fps', '334 f.')))
BIN = chutier('sequence 3', '1 rush', ARBRE)
RAIL = rail('rush')

TIMELINE = '''        <div class="piste">
            <div class="dedans" style="left:18%; right:34%"></div>
            <div class="mk2" style="left:31%"></div>
            <div class="mk2" style="left:52%"></div>
            <div class="tete" style="left:42%"></div>
          </div>
          <div class="regle"><span>00:00:00:00</span><span>in 00:00:08:04 &middot; out 00:00:21:12</span><span>00:00:32:00</span></div>'''


def ecran(titre, tete, corps, panneau, legende, *, wrap=''):
    cote = ('      <div class="rappel">&lsaquo;</div>' if panneau is None
            else '      <div class="panel">' + replier() + panneau + '\n      </div>')
    return f'''
  <h2>{titre}</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">Extraction &middot; TEST_FILE_12p5.mov</span></div>
    <div class="app-body">
      <div class="nav">{RAIL}</div>
{BIN}
      <div class="work">
        <div class="wh">{tete}</div>
{corps}
{wrap}
      </div>
{cote}
    </div>
  </div>
  <p class="caption">{legende}</p>
'''

# --- etat A : le selecteur de cadence, deplie -----------------------------
# Reponse au fil nº 13. Le selecteur liste les extractions DEJA FAITES du rush ;
# passer de l'une a l'autre garde le timecode.
# EPIC7-ARB-20 : le selecteur ne liste que les extractions QUI EXISTENT. Il ne
# cree rien -- mais il mene visiblement a la creation, sinon la question d'Egan
# reste sans reponse : « comment ajoute-t-on une cadence a cette liste ? »
MENU = '''<span class="cadsel">12,5 <span class="car">&#9662;</span>
            <span class="menu">
              <span class="li on">12,5 &mdash; 167 f.</span>
              <span class="li">25 &mdash; 334 f.</span>
              <span class="li seul">extractions existantes &middot; le timecode ne bouge pas</span>
              <span class="li creer">+ extraire a une autre cadence&hellip;</span>
            </span></span>'''

tete_a = (onglets('Lecteur', 'Galerie', 'Lecteur')
          + barre_vue(pas=False)
          + f'<div class="cad">{MENU}'
            '<span class="cadb ok"><span class="p"></span>12,5</span>'
            '<span class="qual">pleine <span class="car">&#9662;</span></span></div>')

# EPIC7-ARB-20 : la cadence est une valeur SAISIE. Les trois pastilles ne sont
# que des raccourcis du projet -- ce qui est offert n'est pas ce qui est
# possible. Le champ porte la reponse a « comment ajoute-t-on une cadence ».
panneau_a = '''        <h3>Extraire des frames</h3>
        <div class="grp"><span class="tl">Cadence</span>
          <div class="raccourcis">
            <span class="r on">12,5</span><span class="r">25</span><span class="r">50</span>
            <span class="r">24</span><span class="r">16</span>
          </div>
          <div class="saisie">
            <span class="champ2">12,5<span class="curs"></span><span class="u">images/s</span></span>
            <span class="plus">+</span>
          </div>
        </div>
        <div class="recap">
          entree 00:00:08:04 &middot; sortie 00:00:21:12<br>
          duree 00:00:13:08 &middot; 2 marqueurs<br>
          167 frames a cette cadence
        </div>
        <button class="btn" type="button">Extraire 167 frames</button>'''

etat_a = ecran(
    'Etat A &mdash; passer d\'une cadence a l\'autre en relecture',
    tete_a,
    '        <div class="mat"><div class="scene"><span class="tc">00:00:12:14</span></div></div>\n' + TIMELINE,
    panneau_a,
    "Ta question recoit sa reponse a droite : <b class=\"k\">la cadence est une valeur qu'on "
    "saisit</b>. Les pastilles ne sont que des raccourcis du projet, et « + raccourci » y ajoute "
    "celle qu'on vient de taper. Le selecteur de gauche, lui, ne liste que les extractions qui "
    "<i>existent</i> &mdash; il ne cree rien, mais sa derniere ligne mene a la creation.",
    wrap=transport())

# --- etat B : la galerie, ecart calcule et filtre de vue -------------------
def gc(n, tc, ecartee=False):
    cls = 'gc calc' if ecartee else 'gc'
    marque = '<span class="ec">ecartee</span>' if ecartee else ''
    return (f'<div class="{cls}"><div class="im"><span class="no">{n}</span></div>{marque}'
            f'<div class="fo"><span>{tc}</span></div></div>')

galerie = ''.join(gc(n, f'00:00:{8 + n//2:02d}:{(n*4) % 24:02d}', ecartee=(n in (4, 9)))
                  for n in range(1, 13))

FILTRE = ('<div class="filtre"><span class="on">toutes</span>'
          '<span>retenues</span><span>ecartees</span></div>')

tete_b = (onglets('Galerie', 'Galerie', 'Lecteur')
          + barre_vue() + FILTRE
          + '<span class="px">165 / 167</span>')

panneau_b = '''        <h3>12,5 fps &mdash; 167 frames</h3>
        <div class="recap">
          entree 00:00:08:04 &middot; sortie 00:00:21:12<br>
          165 retenues &middot; 2 ecartees<br>
          1008&times;567 &middot; ratio verrouille
        </div>
        <button class="btn" type="button">Extraire 165 frames</button>
        <div class="avis"><span class="pt"></span><span>Deux frames tombent en dehors de la
        cadence demandee. Passer a 25 les reprend &mdash; c'est le seul moyen.</span></div>'''

etat_b = ecran(
    'Etat B &mdash; la galerie : ce qui est ecarte l\'est par la cadence',
    tete_b, f'        <div class="gal">{galerie}</div>', panneau_b,
    "Correction du 22 aout : <b class=\"k\">ce n'est pas l'utilisateur qui ecarte une frame</b>. "
    "La cadence demandee decide seule. Il n'y a donc aucune case a cocher : le filtre de la barre "
    "montre ou masque les ecartees, et rien de plus.")

# --- etat C : la meme galerie, vignettes agrandies -------------------------
galerie_g = ''.join(gc(n, f'00:00:{8 + n//2:02d}:{(n*4) % 24:02d}', ecartee=(n == 4))
                    for n in range(1, 5))

tete_c = (onglets('Galerie', 'Galerie', 'Lecteur')
          + barre_vue() + FILTRE
          + '<span class="px">165 / 167</span>')

panneau_c = '''        <h3>12,5 fps &mdash; 167 frames</h3>
        <div class="recap">
          165 retenues &middot; 2 ecartees<br>
          1008&times;567 &middot; ratio verrouille
        </div>
        <button class="btn" type="button">Extraire 165 frames</button>'''

etat_c = ecran(
    'Etat C &mdash; la meme galerie, vignettes agrandies',
    tete_c, f'        <div class="gal grand">{galerie_g}</div>', panneau_c,
    "Le ratio ne bouge pas, la grille se recompose. C'est le reglage de taille, pas la vue "
    "vignette unique &mdash; celle-la s'ouvre au clic sur une vignette.")

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>Aucune case a cocher sur une frame.</b>
    L'interface ne doit pas laisser croire qu'on peut outrepasser la selection : la cadence
    demandee determine seule ce qui est extrait. Le filtre affiche, il ne selectionne pas.</p></div>
    <div class="note"><span class="num">2</span><p><b>Le motif est ecrit.</b> A cote du bouton,
    une ligne dit <i>pourquoi</i> deux frames tombent et <i>comment</i> les reprendre. Un signe
    seul, sans motif, n'apprend rien.</p></div>
    <div class="note"><span class="num">3</span><p><b>« Ajuster », pas « largeur ».</b> Le
    libelle vient de la coquille commune : il est ecrit une fois, pour les quatre ateliers.</p></div>
    <div class="note"><span class="num">4</span><p><b>Ce qui existe, et ce qu'on peut demander.</b>
    Le selecteur constate &mdash; il liste les extractions faites. Le panneau demande &mdash; il
    saisit une cadence. C'est la meme separation qu'entre le badge de cadence effective et le
    menu de qualite : constater d'un cote, decider de l'autre.</p></div>
  </div>
'''

CSS_MENU = '''
/* le selecteur de cadence, deplie : une liste, pas une palette */
.cadsel{position:relative}
.cadsel .menu{position:absolute; left:0; top:22px; z-index:3; display:flex; flex-direction:column;
  min-width:150px; background:var(--surface-raised); border:1px solid var(--border-strong);
  border-radius:var(--r-md); padding:var(--sp3) 0}
.cadsel .li{padding:3px var(--sp5); font-family:var(--f-data); font-size:11px; color:var(--text-secondary); white-space:nowrap}
.cadsel .li.on{background:var(--surface-hover); color:var(--text-primary)}
.cadsel .li.seul{border-top:1px solid var(--border); margin-top:var(--sp3); padding-top:var(--sp3);
  font-family:var(--f-ui); font-size:10.5px; color:var(--text-disabled)}
'''

HTML = page(
    "L'atelier Extraction, corrige",
    "Trois corrections du 22 aout, appliquees ici : <b class=\"k\">l'ecart d'une frame est "
    "calcule</b>, jamais choisi ; le bouton dit <b class=\"k\">ajuster</b> ; et le selecteur de "
    "cadence repond enfin au fil laisse ouvert &mdash; comment passer d'une cadence a l'autre "
    "sans perdre son point de lecture.",
    etat_a + etat_b + etat_c, notes, css_extra=CSS_MENU)

(MOCKUPS / 'key-extraction-v3.html').write_text(HTML, encoding='utf-8')
print(f"key-extraction-v3.html {(MOCKUPS / 'key-extraction-v3.html').stat().st_size/1024:.0f} Ko")
