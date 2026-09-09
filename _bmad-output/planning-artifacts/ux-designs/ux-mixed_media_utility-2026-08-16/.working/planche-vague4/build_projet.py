# -*- coding: utf-8 -*-
"""L'ecran de gestion de projet — vague 4.

Jamais maquette : la spine le classait « spine seule — une liste et deux
actions ; la densite n'y fait rien ». Ce pari se tient sur la liste, mais pas
sur deux points qui ne se voient qu'a l'ecran : ce que « creer » demande
exactement, et a quoi ressemble un projet dont les rushes sont absents alors
qu'il doit rester ouvrable.

Contrat de la spine, verbatim : « Dernier projet en tete. Creer = designer un
dossier de travail. Ouvrir un projet dont les rushes sont absents reste
toujours possible. » Et : « Toujours affiche, meme quand un seul projet existe.
Aucun saut direct dans un atelier. »
"""
from coquille4 import MOCKUPS, I, page, groupe, lg

def pj(nom, chemin, modif, cree, *, tete=False):
    """Une ligne de la liste de projets.

    EPIC7-ARB-27 : elle ne porte AUCUN etat de contenu. J'y avais pose un badge
    « 4 rushes absents », ce qui regressait sur ARB-14 (« aucun badge de
    deduction ») et sur la regle de la spine -- un rush absent est peint en
    rouge dans les chutiers, sans badge ni mention. L'etat des rushes se
    decouvre en OUVRANT le projet.
    """
    return (f'<div class="pj{" premier" if tete else ""}">'
            f'<div class="pj-n"><span class="pj-t">{nom}</span>'
            f'<span class="pj-c">{chemin}</span></div>'
            f'<div class="pj-dd"><span>{modif}</span>'
            f'<span class="cree">cree le {cree}</span></div></div>')


def ecran(titre, corps, legende):
    return f'''
  <h2>{titre}</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">mixed_media_utility</span></div>
{corps}
  </div>
  <p class="caption">{legende}</p>
'''

# --- etat A : le seuil, dernier projet en tete -----------------------------
liste = (pj('Le vent se retourne', '/Volumes/HOKO/films/vent/mmu', 'hier 18:42', '02/08', tete=True)
         + pj('sequence 3 &mdash; essais', '/Volumes/HOKO/essais/seq3/mmu', '19/08 11:04', '19/08')
         + pj('Court metrage Anna', '/Users/egan/Films/anna/mmu', '11/08 09:22', '28/07')
         + pj('Calibration scanner', '/Users/egan/Films/calib/mmu', '02/08 16:41', '02/08'))

etat_a = ecran(
    'Etat A &mdash; le seuil de chaque lancement',
    f'''    <div class="seuil">
      <div class="seuil-g">
        <h2>Ouvrir un projet</h2>
        <div class="seuil-barre">
          <span class="chercher">Chercher un projet&hellip;</span>
          <span class="tri">modifie le <span class="car">&#9662;</span></span>
        </div>
        <div class="liste">{liste}</div>
      </div>
      <div class="seuil-d">
        <button class="btn" type="button">Creer un projet</button>
        <button class="btn ghost" type="button">Ouvrir un dossier&hellip;</button>
        <button class="btn ghost" type="button">Importer un projet&hellip;</button>
        <div class="recap">
          un projet = un film = un dossier<br>
          un seul projet ouvert a la fois
        </div>
      </div>
    </div>''',
    "La liste ne dit <b class=\"k\">rien du contenu</b> des projets : ni les lots, ni les scans, "
    "ni les rushes manquants. Elle porte le nom, le chemin et les deux dates, elle se trie et se "
    "cherche. Le reste se decouvre en ouvrant.")

# --- etat B : creer, c'est designer un dossier de travail ------------------
etat_b = ecran(
    'Etat B &mdash; creer, c\'est designer un dossier de travail',
    f'''    <div class="seuil">
      <div class="seuil-g">
        <h2>Creer un projet</h2>
        <div class="grp"><span class="tl">Le projet</span>
{lg("Nom du film", "Le vent se retourne", libre=True, menu=False)}
{lg("Dossier de travail", "/Volumes/HOKO/films/vent/mmu", libre=True, menu=False)}
        </div>
        <div class="grp"><span class="tl">Ce qui sera ecrit dans ce dossier</span>
          <div class="zone">/Volumes/HOKO/films/vent/mmu/<br>
          &nbsp;&nbsp;le-vent-se-retourne.json<br>
          &nbsp;&nbsp;lots/ &middot; planches/ &middot; scans/<br>
          &nbsp;&nbsp;lots-reconstruits/ &middot; exports/</div>
        </div>
        <div class="avis"><span class="pt"></span><span>L'outil ne cree <b>pas</b> de sous-dossier
        a ton nom de film : le fichier de projet et les dossiers de travail sont poses directement
        dans le dossier que tu designes. Tes rushes restent ou ils sont &mdash; l'outil n'en garde
        que le chemin.</span></div>
      </div>
      <div class="seuil-d">
        <button class="btn" type="button">Creer</button>
        <button class="btn ghost" type="button">Annuler</button>
        <div class="recap">
          dossier vide requis<br>
          ou dossier a creer
        </div>
      </div>
    </div>''',
    "Creer ne demande que deux choses : un nom et un dossier. L'encart montre <b class=\"k\">ce "
    "qui sera ecrit</b> et ou &mdash; c'est la reponse a ta question, et c'est ce qui evite de "
    "decouvrir apres coup qu'un sous-dossier a ete cree. Les noms de dossiers sont ceux que tu "
    "proposes ; ils ne sont pas encore ceux du coeur.")

# --- etat C : un projet dont les rushes sont absents s'ouvre quand meme ----
liste_c = (pj('Court metrage Anna', '/Users/egan/Films/anna/mmu', '11/08 09:22', '28/07', tete=True)
           + pj('Le vent se retourne', '/Volumes/HOKO/films/vent/mmu', 'hier 18:42', '02/08')
           + pj('sequence 3 &mdash; essais', '/Volumes/HOKO/essais/seq3/mmu', '19/08 11:04', '19/08'))

etat_c = ecran(
    'Etat C &mdash; le projet est ouvert : les rushes manquent, et alors',
    f'''    <div class="seuil">
      <div class="seuil-g">
        <h2>Court metrage Anna</h2>
        <div class="liste">{liste_c}</div>
      </div>
      <div class="seuil-d">
        <div class="grp"><span class="tl">Au chargement</span>
{lg("Lots", "6", menu=False)}
{lg("Scans", "3", menu=False)}
{lg("Rushes", "2 sur 6 trouves", menu=False)}
        </div>
        <div class="avis"><span class="pt"></span><span>Quatre rushes sont declares mais absents
        de cette machine. Ils apparaitront en rouge dans les chutiers. Le scan, la detection et la
        reconstruction fonctionnent sans eux ; le son et le balayage reviendront au relink.</span></div>
        <button class="btn ghost" type="button">Relinker&hellip;</button>
      </div>
    </div>''',
    "Tu as raison : l'etat des rushes ne se dit pas dans la liste, il se decouvre <b class=\"k\">"
    "en ouvrant</b>. Rien n'a empeche l'ouverture, et rien n'est bloque &mdash; le scan, la "
    "detection et la reconstruction n'ont pas besoin des rushes.")

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>Pas de saut direct dans un atelier.</b>
    Meme avec un seul projet, l'ecran s'affiche. Ouvrir un projet est un geste conscient : c'est
    ce qui evite d'ecrire dans le mauvais dossier de travail sans s'en apercevoir.</p></div>
    <div class="note"><span class="num">2</span><p><b>Le dernier projet est en tete, pas
    preselectionne.</b> Un lisere le distingue ; aucune touche ne l'ouvre par defaut. La
    difference compte quand deux projets portent des noms proches.</p></div>
    <div class="note"><span class="num">3</span><p><b>Le dossier de travail ne contient que ce
    que mmu produit.</b> Les rushes restent ou ils sont, l'outil n'en garde que le chemin et sait
    les relinker. C'est ce qui rend un projet transmissible sans les medias.</p></div>
    <div class="note"><span class="num">4</span><p><b>La liste ne dit rien du contenu.</b>
    Ni les lots, ni les scans, ni les rushes manquants : deux dates, un nom, un chemin. Un badge
    d'etat sur cette surface obligerait a ouvrir chaque projet pour l'y ecrire.</p></div>
  </div>
'''

HTML = page(
    "L'ecran de gestion de projet",
    "Le premier ecran de chaque lancement, et le seul qui ne soit pas un atelier. "
    "<b class=\"k\">Une liste et deux actions</b> &mdash; mais deux choses ne se voyaient pas "
    "sans le dessiner : ce que <i>creer</i> demande exactement, et a quoi ressemble un projet "
    "dont les rushes manquent alors qu'il doit rester ouvrable.",
    etat_a + etat_b + etat_c, notes)

(MOCKUPS / 'key-projet.html').write_text(HTML, encoding='utf-8')
print(f"key-projet.html {(MOCKUPS / 'key-projet.html').stat().st_size/1024:.0f} Ko")
