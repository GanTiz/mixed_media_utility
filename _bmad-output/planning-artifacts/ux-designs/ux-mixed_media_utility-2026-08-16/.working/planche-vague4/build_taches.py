# -*- coding: utf-8 -*-
"""Le panneau de progression et les cartes de taches — vague 4.

Egan, 22 aout 16h39 : « La carte sur le cote est une carte de tache comme
toutes les autres : export, progression temps ecoule et temps restant. On n'a
pas revu cette surface dans toutes tes maquettes. »

C'est exact : le `Panneau de progression` est dans l'architecture d'information
depuis le debut — « File des taches en cours et terminees, toutes fonctions
confondues » — mais il n'apparaissait qu'en arriere-plan de `key-atelier-pdf`,
jamais seul. Le voici, avec le contrat de la carte tel que la spine l'ecrit :
fonction, objet, barre, faits/total, temps passe, temps restant ; et, terminee,
les boutons dossier et fichier — dossier seul quand le resultat est une
collection de frames.
"""
from coquille4 import (MOCKUPS, I, barre_vue, onglets, rail, noeud, chutier,
                       page, carte, replier, groupe, lg)

ARBRE = noeud('rush', 'TEST_FILE_12p5.mov', '1080p', ouvert=True, sel=True, enfants=(
    noeud('extr', 'Extraction 12,5 fps', '167 f.')
    + noeud('extr', 'Extraction 25 fps', '334 f.')))
BIN = chutier('sequence 3', '1 rush', ARBRE)
RAIL = rail('rush')

BASCULE = ('<span class="tq-bascule on">taches <span class="n">3</span></span>')


def ecran(titre, tete, corps, cote, legende):
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
      </div>
{cote}
    </div>
  </div>
  <p class="caption">{legende}</p>
'''

TETE = (onglets('Galerie', 'Galerie', 'Lecteur')
        + barre_vue(pas=False)
        + f'<span class="wh-fin">{BASCULE}</span>')


def gc(n, tc):
    return (f'<div class="gc"><div class="im"><span class="no">{n}</span></div>'
            f'<div class="fo"><span>{tc}</span></div></div>')

GALERIE = ''.join(gc(n, f'00:00:{8 + n//2:02d}:{(n*4) % 24:02d}') for n in range(1, 13))
CORPS = f'        <div class="gal">{GALERIE}</div>'


MODE = ('<span class="tq-mode"><span class="on">ancree</span>'
        '<span>superposee</span></span>')


def file_taches(*cartes, titre='3 en cours'):
    return f'''      <div class="taches">
        <div class="tq-head"><h3>Taches</h3>{MODE}<span class="x">Fermer</span></div>
        <div class="tq-corps">
{''.join(cartes)}
        </div>
      </div>'''


# --- etat A : trois taches de trois fonctions differentes, en meme temps ---
# Le point de la surface est justement la : « toutes fonctions confondues ».
# Une file qui ne montrerait qu'un encodage ne prouverait rien.
etat_a = ecran(
    'Etat A &mdash; la file, trois fonctions en meme temps',
    TETE, CORPS,
    file_taches(
        '<span class="tq-sec">En cours</span>',
        carte('Encodage', 'TEST_FILE_12p5 &middot; 12,5', pct=38,
              fait='63', total='167', passe='1 min 12 s', reste='1 min 58 s'),
        carte('Extraction', 'sequence_4 &middot; 25 fps', pct=71,
              fait='150', total='212', passe='48 s', reste='19 s'),
        carte('Detection', 'scan_2026-08-19.pdf', pct=12,
              fait='4', total='34', passe='6 s', reste='42 s')),
    "La file est ouverte par la bascule d'en-tete, depuis les quatre ateliers, et elle melange "
    "les fonctions : encodage, extraction, detection. C'est ce melange qui fait sa raison d'etre "
    "&mdash; une file par atelier obligerait a chercher ou en est un travail.")

# --- etat B : terminees et echouee ----------------------------------------
etat_b = ecran(
    'Etat B &mdash; terminees, et une qui a echoue',
    TETE, CORPS,
    file_taches(
        '<span class="tq-sec">En cours</span>',
        carte('Detection', 'scan_2026-08-19.pdf', pct=64,
              fait='22', total='34', passe='24 s', reste='13 s'),
        '<span class="tq-sec">Terminees</span>',
        carte('Extraction', 'TEST_FILE_12p5 &middot; 12,5', etat='fini',
              fait='167', total='167', passe='2 min 04 s',
              boutons=('Dossier',)),
        carte('Encodage', 'sequence_4 &middot; 25', etat='fini',
              fait='212', total='212', passe='3 min 41 s',
              boutons=('Dossier', 'Fichier')),
        carte('Encodage', 'Court metrage Anna &middot; 25', etat='echec',
              fait='0', total='212', passe='2 s',
              motif='LOT_INCOMPLET')),
    "Une extraction produit une collection de frames : elle n'ouvre qu'un <b class=\"k\">dossier</b>. "
    "Un encodage produit un fichier : il ouvre les <b class=\"k\">deux</b>. Une carte finie ne se "
    "peint pas en vert &mdash; sa jauge le dit, et le bouton qui apparait suffit.")

# --- etat C : la question ouverte, retrecir ou superposer ------------------
etat_c = f'''
  <h2>Etat C &mdash; les deux modes, et la bascule entre eux</h2>
  <div class="deux-cotes">
    <div class="cote">
      <span class="cote-t">Ancree &mdash; elle retrecit la scene</span>
      <div class="app mini">
        <div class="app-header"><span class="app-title">Exports</span></div>
        <div class="app-body">
          <div class="work">
            <div class="wh">{onglets('Lecteur', 'Galerie', 'Lecteur')}<span class="wh-fin">{BASCULE}</span></div>
            <div class="mat"><div class="scene petite"><span class="tc">00:00:12:14</span></div></div>
          </div>
          <div class="taches etroit">
            <div class="tq-head"><h3>Taches</h3></div>
            <div class="tq-corps">{carte('Encodage', '12,5', pct=38, fait='63', total='167', passe='1 min 12 s', reste='1 min 58 s')}</div>
          </div>
        </div>
      </div>
    </div>
    <div class="cote">
      <span class="cote-t">Superposee &mdash; l'image ne bouge pas</span>
      <div class="app mini">
        <div class="app-header"><span class="app-title">Exports</span></div>
        <div class="app-body">
          <div class="work">
            <div class="wh">{onglets('Lecteur', 'Galerie', 'Lecteur')}<span class="wh-fin">{BASCULE}</span></div>
            <div class="mat"><div class="scene"><span class="tc">00:00:12:14</span></div></div>
            <div class="flottant">
              <div class="tq-head"><h3>Taches</h3></div>
              <div class="tq-corps">{carte('Encodage', '12,5', pct=38, fait='63', total='167', passe='1 min 12 s', reste='1 min 58 s')}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
  <p class="caption">Ta reponse, appliquee : <b class="k">les deux, par bascule</b>, dans
  l'en-tete de la file. Et <b class="k">superposee par defaut sous un seuil de largeur</b> de
  fenetre &mdash; ancrer 320 px dans une fenetre etroite ne laisse plus rien a la previz. Un mode
  choisi a la main survit au franchissement du seuil : le seuil fixe le defaut, il ne reprend pas
  la main sur un choix.</p>
'''

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>L'ordre des elements est un contrat.</b>
    Fonction, objet, barre, faits sur total, temps passe, temps restant. C'est ce qu'on lit en
    diagonale quand trois taches tournent : la fonction dit <i>quoi</i>, l'objet dit <i>sur
    quoi</i>, le reste dit <i>ou ca en est</i>.</p></div>
    <div class="note"><span class="num">2</span><p><b>Dossier seul, ou dossier et fichier.</b>
    Une extraction rend une collection de frames : il n'y a pas de fichier a ouvrir. Un encodage
    rend un master : les deux boutons ont un objet. La carte suit le resultat, pas la
    fonction.</p></div>
    <div class="note"><span class="num">3</span><p><b>L'echec porte son motif en verbatim.</b>
    <code>LOT_INCOMPLET</code> est un code de <code>encode.ENCODE_REFUSAL_CODES</code>, affiche
    tel quel. On ne le traduit pas en « une erreur est survenue » : c'est ce qui permet de
    reprendre le travail sans relancer pour voir. Le refus arrive ici a zero frame ecrite
    &mdash; le coeur verifie avant d'ecrire.</p></div>
    <div class="note"><span class="num">4</span><p><b>Deux modes, un seul choix a faire.</b>
    La bascule est dans l'en-tete de la file. Sous un seuil de largeur de fenetre, le mode
    superpose devient le defaut &mdash; mais un mode choisi a la main n'est jamais repris par le
    seuil. En Qt, basculer revient a reparenter la file : rien d'inhabituel.</p></div>
  </div>
'''

CSS_X = '''
.wh-fin{margin-left:auto}
.deux-cotes{display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:var(--sp6)}
.cote{display:flex; flex-direction:column; gap:var(--sp4); min-width:0}
.cote-t{font-family:var(--f-data); font-size:11px; color:var(--text-disabled)}
.app.mini .app-body{min-height:250px}
.app.mini .scene{width:250px}
.app.mini .scene.petite{width:170px}
.taches.etroit{width:212px; flex:0 0 212px}
.taches.etroit .tk-o{display:none}
/* la file superposee : elle flotte au-dessus de la scene, l'image ne bouge pas */
.flottant{position:absolute; right:var(--sp5); top:calc(var(--header-height) + var(--sp5));
  width:216px; background:var(--surface-panel); border:1px solid var(--border-strong);
  border-radius:var(--r-md); box-shadow:0 6px 20px rgba(0,0,0,.5); overflow:hidden}
.flottant .tq-head{height:30px}
.flottant .tq-head h3{font-size:11.5px}
.flottant .tq-corps{padding:var(--sp4)}
.flottant .tk-o{display:none}
/* dans une file etroite la carte empile ses chiffres au lieu de les couper :
   « 63 / 167 » sur deux lignes ne se lit pas. */
.taches.etroit .tk-nb, .flottant .tk-nb{flex-direction:column; align-items:flex-start; gap:1px}
'''

HTML = page(
    "Les cartes de taches",
    "La surface que tu as nommee : <b class=\"k\">une carte par tache longue</b>, toutes "
    "fonctions confondues, avec sa progression, son temps passe et son temps restant. Elle "
    "existait dans la spine depuis le debut &mdash; elle n'avait jamais ete montree seule.",
    etat_a + etat_b + etat_c, notes, css_extra=CSS_X)

(MOCKUPS / 'key-taches.html').write_text(HTML, encoding='utf-8')
print(f"key-taches.html {(MOCKUPS / 'key-taches.html').stat().st_size/1024:.0f} Ko")
