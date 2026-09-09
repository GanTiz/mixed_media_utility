# -*- coding: utf-8 -*-
"""Le menu contextuel — vague 5.

L'inventaire du clic droit etait dans `deferred-work.md` depuis le 22 aout :
« Il faudra qu'on voie tout ce que le clic droit dans le chutier permet. » Il
en sort ici, et il s'etend au-dela du chutier -- partout ou une decision a ete
prise de retirer une commande de l'interface au profit du clic droit.

Deux regles de la proposition :

1. **le clic droit ne cache jamais une action unique**. Ce qu'on y met est soit
   une variante d'un geste deja possible ailleurs, soit une action rare. Une
   action qu'on ne peut faire QUE par clic droit est introuvable ;
2. **une entree grisee dit pourquoi**. Un menu ou la moitie des lignes sont
   inertes sans explication apprend qu'il ne faut pas l'ouvrir.
"""
from coquille5 import (MOCKUPS, I, P, page, entree, menu, noeud, chutier,
                       rail, onglets, barre_vue, carte)

def ecran(titre, corps, legende):
    return f'''
  <h2>{titre}</h2>
  <div class="app">
{corps}
  </div>
  <p class="caption">{legende}</p>
'''

# --- A : le chutier, sur un rush et sur un lot ----------------------------
ARBRE = noeud('rush', 'TEST_FILE_12p5.mov', '1080p', ouvert=True, sel=True, enfants=(
    noeud('extr', 'Extraction 12,5 fps', '167 f.')
    + noeud('extr', 'Extraction 25 fps', '334 f.')))

MENU_RUSH = menu('Rush &mdash; TEST_FILE_12p5.mov',
    entree('Ouvrir dans l\'Extraction', raccourci='&#8629;'),
    entree('Reveler dans le Finder', raccourci='&#8984;R'),
    entree('Relinker&hellip;', separateur_avant=True),
    entree('Renommer', raccourci='&#8629;&#8629;'),
    entree('Rattacher a&hellip;', fleche=True),
    entree('Retirer du projet', separateur_avant=True),
    entree('Supprimer les fichiers', gris=True),
    entree('Le rush est hors du dossier de travail', gris=True, sous=True),
    largeur=270)

etat_a = ecran('Etat A &mdash; clic droit sur un rush du chutier',
    f'''    <div class="app-header"><span class="app-title">Extraction &middot; sequence 3</span></div>
    <div class="app-body">
      <div class="nav">{rail('rush')}</div>
      <div class="bin ctx">
        <div class="bin-head"><span class="bin-scope">Chutier</span><span class="meta">1 rush</span></div>
        <div class="portee">Contenu de <b>sequence 3</b></div>
        <div class="tree">{ARBRE}</div>
        <div style="left:96px; top:104px">{MENU_RUSH}</div>
      </div>
      <div class="work">
        <div class="wh">{onglets('Lecteur', 'Galerie', 'Lecteur')}{barre_vue(pas=False)}</div>
        <div class="mat"><div class="scene"><span class="tc">00:00:12:14</span></div></div>
      </div>
    </div>''',
    "<b class=\"k\">« Rattacher a&hellip; » est ici</b>, et nulle part ailleurs : c'est la "
    "decision du 20 aout, qui l'a retiree de l'interface. <i>Supprimer les fichiers</i> est grise "
    "parce que le rush n'est pas dans le dossier de travail &mdash; l'outil n'efface que ce qu'il "
    "a produit.")

# --- B : un marqueur, et une vignette de galerie --------------------------
MENU_MK = menu('Marqueur &mdash; 00:00:14:08',
    entree('Editer&hellip;', raccourci='double-clic'),
    entree('Aller au marqueur'),
    entree('Definir l\'entree ici', separateur_avant=True),
    entree('Definir la sortie ici'),
    entree('Supprimer', separateur_avant=True),
    largeur=250)

def gc(n, tc):
    return (f'<div class="gc"><div class="im"><span class="no">{n}</span></div>'
            f'<div class="fo"><span>{tc}</span></div></div>')

MENU_VG = menu('Frame 156 &middot; 00:00:12:14',
    entree('Ouvrir en vue unique', raccourci='&#8629;'),
    entree('Comparer les candidats', gris=True),
    entree('Cette frame n\'a qu\'un candidat', gris=True, sous=True),
    entree('Voir la page de la planche', separateur_avant=True),
    entree('Reveler le fichier', raccourci='&#8984;R'),
    entree('Copier le timecode', separateur_avant=True),
    largeur=260)

etat_b = ecran('Etat B &mdash; sur un marqueur, et sur une vignette',
    f'''    <div class="app-header"><span class="app-title">Extraction &middot; TEST_FILE_12p5.mov</span></div>
    <div class="app-body">
      <div class="work ctx">
        <div class="wh">{onglets('Galerie', 'Galerie', 'Lecteur')}{barre_vue(pas=False)}</div>
        <div class="gal">{''.join(gc(n, f'00:00:{8 + n//2:02d}:{(n*4) % 24:02d}') for n in range(1, 9))}</div>
        <div style="left:150px; top:190px">{MENU_VG}</div>
      </div>
      <div class="work ctx" style="border-left:1px solid var(--border)">
        <div class="wh">{onglets('Lecteur', 'Galerie', 'Lecteur')}{barre_vue(pas=False)}</div>
        <div class="mat"><div class="scene"><span class="tc">00:00:12:14</span></div></div>
        <div class="piste">
          <div class="dedans" style="left:18%; right:34%"></div>
          <div class="mk2" style="left:31%"></div>
          <div class="mk2" style="left:52%"></div>
          <div class="tete" style="left:42%"></div>
        </div>
        <div class="regle"><span>00:00:00:00</span><span>2 marqueurs</span><span>00:00:32:00</span></div>
        <div style="left:130px; bottom:40px">{MENU_MK}</div>
      </div>
    </div>''',
    "L'edition d'un marqueur est <b class=\"k\">ici et au double-clic</b> &mdash; jamais "
    "seulement ici. Le raccourci l'annonce dans le menu, ce qui evite de croire que le clic droit "
    "est le seul chemin. <i>Comparer les candidats</i> est grise : cette frame n'en a qu'un.")

# --- C : une tache, et une ligne de projet --------------------------------
MENU_TK = menu('Tache &mdash; Encodage',
    entree('Annuler la tache'),
    entree('Relancer', gris=True),
    entree('Reveler le resultat', gris=True, separateur_avant=True),
    entree('Copier le motif d\'echec', gris=True),
    entree('La tache n\'est pas terminee', gris=True, sous=True),
    largeur=250)

MENU_PJ = menu('Projet &mdash; Court metrage Anna',
    entree('Ouvrir', raccourci='&#8629;'),
    entree('Reveler le dossier', raccourci='&#8984;R'),
    entree('Dupliquer le projet&hellip;', separateur_avant=True),
    entree('Retirer de la liste', separateur_avant=True),
    entree('Les fichiers ne sont pas touches', gris=True, sous=True),
    largeur=280)

etat_c = ecran('Etat C &mdash; sur une carte de tache, et sur un projet',
    f'''    <div class="app-header"><span class="app-title">Menus contextuels &middot; taches et projets</span></div>
    <div class="app-body">
      <div class="taches ctx" style="flex:1 1 auto; width:auto; border-left:0">
        <div class="tq-head"><h3>Taches</h3></div>
        <div class="tq-corps">
{carte('Encodage', 'lot 12,5', pct=38, fait='63', total='167', passe='1 min 12 s', reste='1 min 58 s')}
{carte('Extraction', 'sequence_4', etat='fini', fait='212', total='212', passe='3 min 41 s', boutons=('Dossier',))}
        </div>
        <div style="left:120px; top:110px">{MENU_TK}</div>
      </div>
      <div class="seuil ctx" style="flex:1 1 auto; min-height:0; border-left:1px solid var(--border)">
        <div class="seuil-g">
          <h2>Ouvrir un projet</h2>
          <div class="liste">
            <div class="pj premier"><div class="pj-n"><span class="pj-t">Court metrage Anna</span>
            <span class="pj-c">/Users/egan/Films/anna/mmu</span></div>
            <div class="pj-dd"><span>11/08 09:22</span><span class="cree">cree le 28/07</span></div></div>
            <div class="pj"><div class="pj-n"><span class="pj-t">Le vent se retourne</span>
            <span class="pj-c">/Volumes/HOKO/films/vent/mmu</span></div>
            <div class="pj-dd"><span>hier 18:42</span><span class="cree">cree le 02/08</span></div></div>
          </div>
        </div>
        <div style="left:60px; top:120px">{MENU_PJ}</div>
      </div>
    </div>''',
    "Sur une tache en cours, seul <i>Annuler</i> a un objet ; le reste est grise et le restera "
    "jusqu'a la fin. Sur un projet, <b class=\"k\">« Retirer de la liste » porte sa consequence "
    "en clair</b> &mdash; c'est le genre d'action qu'on croit destructrice, et une ligne suffit a "
    "lever le doute.")

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>Le clic droit ne cache jamais une action
    unique.</b> Chaque entree est soit une variante d'un geste possible ailleurs, soit une action
    rare. Une commande qu'on ne peut atteindre que par clic droit est introuvable pour qui ne
    pense pas a essayer &mdash; sauf « rattacher a », que tu as explicitement voulu la.</p></div>
    <div class="note"><span class="num">2</span><p><b>Une entree grisee dit pourquoi.</b> Soit par
    une ligne sous elle, soit parce que le titre du menu rend le motif evident. Un menu dont la
    moitie est inerte sans explication apprend qu'il ne faut pas l'ouvrir.</p></div>
    <div class="note"><span class="num">3</span><p><b>Le titre du menu nomme l'objet.</b> Sur
    quoi ai-je clique ? Dans un chutier a six niveaux, la question se pose vraiment, et un menu
    sans titre fait agir sur le mauvais element.</p></div>
    <div class="note"><span class="num">4</span><p><b>Le raccourci clavier est affiche.</b> C'est
    ce qui fait sortir du clic droit : on apprend le geste rapide en utilisant le geste lent.</p></div>
  </div>
'''

CSS_X = '''
.ctx > div[style]{position:absolute}
.app-body > .work.ctx{min-width:0}
'''

HTML = page(
    "Le menu contextuel",
    "L'inventaire que tu attendais depuis le 22 aout, etendu au-dela du chutier : partout ou une "
    "commande a ete retiree de l'interface au profit du clic droit. Deux regles &mdash; "
    "<b class=\"k\">il ne cache jamais une action unique</b>, et <b class=\"k\">une entree grisee "
    "dit pourquoi</b>.",
    etat_a + etat_b + etat_c, notes, css_extra=CSS_X)

(MOCKUPS / 'key-clic-droit.html').write_text(HTML, encoding='utf-8')
print(f"key-clic-droit.html {(MOCKUPS / 'key-clic-droit.html').stat().st_size/1024:.0f} Ko")
