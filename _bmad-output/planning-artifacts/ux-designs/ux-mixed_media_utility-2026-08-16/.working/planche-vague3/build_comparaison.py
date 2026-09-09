# -*- coding: utf-8 -*-
"""Voir une frame de pres, et trancher — vague 3.

Trois etats qui repondent a trois demandes distinctes :

* etat A, la **vue vignette unique** reclamee le 22 aout a 11h29 (EPIC7-ARB-18)
  -- un clic sur une vignette ouvre la frame seule, plein panneau, avec zoom
  dedans. Ce n'est pas la galerie a grandes vignettes de la vague 2, qui reste
  et repond a un autre besoin ;
* etat B, la **comparaison de candidats** : deux scans du meme lot donnent deux
  images pour une meme frame, on les met cote a cote et on en designe une ;
* etat C, la **bascule d'une passe a l'autre au meme timecode** -- comparer
  deux passes entieres ne se fait pas cote a cote.
"""
from coquille import (MOCKUPS, I, barre_vue, onglets, rail, noeud, chutier,
                      page, transport, lg, groupe, avis, replier)

ARBRE = noeud('scan', 'scan_2026-08-19.pdf', '2 passes', ouvert=True, enfants=(
    noeud('lotr', 'passe du 19/08', '167 f.', sel=True)
    + noeud('lotr', 'passe du 21/08', '167 f.')))
BIN = chutier('scan_2026-08-19.pdf', '2 passes', ARBRE)
RAIL = rail('planche')


def ecran(titre, tete, corps, panneau, legende, *, wrap=''):
    # EPIC7-ARB-25 : panneau None -> la vue s'ouvre retractee, poignee gardee.
    cote = ('      <div class="rappel">&lsaquo;</div>' if panneau is None
            else '      <div class="panel">' + replier() + panneau + '\n      </div>')
    return f'''
  <h2>{titre}</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">Scan &middot; TEST_FILE_12p5 &middot; lot reconstruit</span></div>
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

# --- etat A : la vue vignette unique --------------------------------------
def bande(actif):
    v = []
    for n in range(152, 161):
        cls = 'v on' if n == actif else 'v'
        if n in (154, 159):          # ecartees par la cadence, pas par la main
            cls += ' calc'
        v.append(f'<span class="{cls}"><span>{n}</span></span>')
    return f'<div class="bande">{"".join(v)}</div>'

tete_a = (onglets('Frame', 'Page', 'Galerie', 'Frame', 'Lecteur')
          + barre_vue()
          + '<span class="px">frame 156 / 167</span>')

solo_a = f'''        <div class="solo">
          <div class="cadre">
            <div class="im1 zoom">
              <span class="tc">00:00:12:14 &middot; frame 156</span>
              <span class="lo">240 %</span>
            </div>
          </div>
{bande(156)}
        </div>'''

# EPIC7-ARB-25 : « Le menu a droite est inutile, ou alors il faut pouvoir le
# retirer. » En vue vignette unique on regarde une image : elle doit avoir
# toute la largeur. La vue s'ouvre donc panneau retracte.
panneau_a = None

etat_a = ecran(
    'Etat A &mdash; la vue vignette unique, avec zoom dedans',
    tete_a, solo_a, panneau_a,
    "Le panneau est parti, comme tu l'as demande : on regarde une image, elle prend toute la "
    "largeur. La poignee de gauche le rappelle quand on en a besoin.")

# --- etat B : deux candidats cote a cote ----------------------------------
tete_b = (onglets('Frame', 'Page', 'Galerie', 'Frame', 'Lecteur')
          + barre_vue(loupe=True)
          + '<span class="px">2 candidats</span>')

duo = '''        <div class="duo">
          <div class="cand pris">
            <div class="im2"></div>
            <div class="lg"><span>scan du 19/08 &middot; p. 14</span><span class="rt">retenu</span></div>
          </div>
          <div class="cand autre">
            <div class="im2"></div>
            <div class="lg"><span>scan du 21/08 &middot; p. 14</span><span>designer</span></div>
          </div>
        </div>'''

# Retour d'Egan, 14h23 : « On veut un choix comme tu avais fait avant. Liste de
# choix et on coche le lot prioritaire. Moins bavard. » Le paragraphe
# d'explication et le bouton a libelle long disparaissent au profit de la forme
# `.opt` deja utilisee dans l'atelier Extraction -- la meme forme pour le meme
# geste, d'un ecran a l'autre.
panneau_b = '''        <h3>Candidats</h3>
        <div class="opt on"><span class="radio"></span><span class="tt">scan du 19/08</span><span class="meta">p. 14</span></div>
        <div class="opt"><span class="radio"></span><span class="tt">scan du 21/08</span><span class="meta">p. 14</span></div>
        <div class="grp"><span class="tl">Sur tout le lot</span>
          <div class="opt"><span class="radio"></span><span class="tt">scan du 19/08 prioritaire</span><span class="meta">9 f.</span></div>
          <div class="opt"><span class="radio"></span><span class="tt">scan du 21/08 prioritaire</span><span class="meta">9 f.</span></div>
        </div>
        <div class="recap">lot complet &middot; 167 / 167</div>'''

etat_b = ecran(
    'Etat B &mdash; comparer deux candidats pour la meme frame',
    tete_b, duo, panneau_b,
    "La designation est un lisere autour de la vignette, pose HORS de l'image : l'accent ne "
    "touche jamais une image que l'on juge. Le mot <i>retenu</i> le redit, pour que la couleur "
    "ne porte pas seule.")

# --- etat C RETIRE, en attente d'EPIC7-ARB-21 -----------------------------
# Egan, 14h24 : « Je ne crois pas que ce soit une fonction listee. Pourquoi pas
# en cas de selection multiple c'est interessant. Mais pas le cas d'un lot
# reconstruit. » La fonction EST listee -- EXPERIENCE.md, section « Composer un
# lot » -- mais son terrain est a trancher : la restreindre a la selection
# multiple, ou la retirer de la spine. Rien n'est dessine tant que ce n'est pas
# tranche : dessiner un ecran, c'est deja choisir.
etat_c = ''

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>Un onglet de plus, parce qu'il a un
    objet.</b> Ici les onglets sont <i>page, galerie, frame, lecteur</i> : la vue vignette unique
    est une vue a part entiere. Sur les ecrans ou elle n'a pas d'objet, elle n'apparait pas
    &mdash; on ne grise pas, on n'ecrit pas.</p></div>
    <div class="note"><span class="num">2</span><p><b>Trancher ne supprime rien.</b> Le candidat
    non retenu reste disponible, et le choix se defait. La garde centrale reste la completude :
    l'interface ne laisse pas construire un choix qui ferait disparaitre une frame.</p></div>
    <div class="note"><span class="num">3</span><p><b>Un lot ne change pas d'identite en etant
    compose.</b> Une composition est une variante datee du meme lot : le chutier garde son
    arborescence, aucune branche parallele n'apparait a chaque essai.</p></div>
    <div class="note"><span class="num">5</span><p><b>Un troisieme etat manque, et c'est
    volontaire.</b> La bascule entre deux passes entieres au meme timecode est ecrite dans la
    spine, mais tu dis qu'elle n'a pas d'objet sur un lot reconstruit. Tant que son terrain
    n'est pas tranche, je ne la dessine pas : dessiner un ecran, c'est deja choisir.</p></div>
    <div class="note"><span class="num">4</span><p><b>Les frames grisees de la bande sont des
    ecartees de cadence</b>, pas des frames decochees. Elles se voient, elles ne se cliquent
    pas.</p></div>
  </div>
'''

HTML = page(
    "Voir une frame de pres, et trancher",
    "Deux facons de regarder de pres : <b class=\"k\">une frame seule avec zoom</b>, et "
    "<b class=\"k\">deux candidats cote a cote</b> dont on coche celui qui l'emporte. Une "
    "troisieme attend ton arbitrage.",
    etat_a + etat_b + etat_c, notes)

(MOCKUPS / 'key-comparaison.html').write_text(HTML, encoding='utf-8')
print(f"key-comparaison.html {(MOCKUPS / 'key-comparaison.html').stat().st_size/1024:.0f} Ko")
