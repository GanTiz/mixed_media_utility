# -*- coding: utf-8 -*-
"""La barre de menus systeme — vague 5.

Egan : « les eventuels menus de la barre de menu windows/mac si pertinent ».

Pertinent, oui, et pour une raison precise : mmu est une application de bureau
native (Qt/PySide6, macOS 12+ et Windows 10+). Sur macOS, une application sans
barre de menus ne peut pas etre pilotee au clavier par le systeme, n'apparait
pas dans le repertoire des raccourcis, et ne repond pas aux conventions que
l'utilisateur applique sans y penser (Cmd+, pour les Preferences, Cmd+W).

Regle de la proposition : **la barre ne cree aucune fonction**. Elle donne un
second chemin, clavier et decouvrable, vers ce que les ateliers portent deja --
plus les quelques commandes que le systeme attend a un endroit precis.
"""
from coquille5 import MOCKUPS, page, entree, menu

MAC = ['mmu', 'Fichier', 'Edition', 'Affichage', 'Aller', 'Fenetre', 'Aide']
WIN = ['Fichier', 'Edition', 'Affichage', 'Aller', 'Outils', 'Aide']


def barre(noms, actif, *, pomme=False, app=None):
    p = '<span class="pomme" aria-label="menu systeme"></span>' if pomme else ''
    return ('<div class="osbar">' + p + ''.join(
        f'<span class="om{" on" if n == actif else ""}'
        f'{" appli" if n == app else ""}">{n}</span>' for n in noms) + '</div>')


def fenetre(barre_html, menu_html, gauche):
    return (f'{barre_html}<div class="osfen">'
            f'<div style="position:absolute; left:{gauche}px; top:4px">{menu_html}</div></div>')


def ecran(titre, corps, legende):
    return f'''
  <h2>{titre}</h2>
  <div class="app">
{corps}
  </div>
  <p class="caption">{legende}</p>
'''

# --- A : Fichier, sur macOS ------------------------------------------------
M_FICHIER = menu('',
    entree('Nouveau projet&hellip;', raccourci='&#8984;N'),
    entree('Ouvrir un dossier&hellip;', raccourci='&#8984;O'),
    entree('Importer un projet&hellip;', raccourci='&#8679;&#8984;O'),
    entree('Projets recents', fleche=True, separateur_avant=True),
    entree('Fermer le projet', raccourci='&#8984;W', separateur_avant=True),
    entree('Reveler le dossier de travail', raccourci='&#8984;R'),
    largeur=280)

etat_a = ecran('Etat A &mdash; Fichier, sur macOS',
    '    ' + fenetre(barre(MAC, 'Fichier', pomme=True, app='mmu'), M_FICHIER, 96),
    "Rien ici n'est une fonction nouvelle : les trois premieres entrees sont les trois boutons "
    "de l'ecran de projets. La barre leur donne un <b class=\"k\">second chemin, clavier et "
    "decouvrable</b> &mdash; c'est tout ce qu'on lui demande.")

# --- B : Affichage, et le menu applicatif macOS ---------------------------
M_AFFICHAGE = menu('',
    entree('Extraction', raccourci='&#8984;1'),
    entree('Pdf', raccourci='&#8984;2'),
    entree('Scan', raccourci='&#8984;3'),
    entree('Exports', raccourci='&#8984;4'),
    entree('Galerie', raccourci='&#8984;&#8679;G', separateur_avant=True),
    entree('Lecteur', raccourci='&#8984;&#8679;L'),
    entree('Ajuster', raccourci='&#8984;0', separateur_avant=True),
    entree('Zoom avant', raccourci='&#8984;+'),
    entree('Zoom arriere', raccourci='&#8984;&minus;'),
    entree('Chutier', raccourci='&#8984;&#8679;B', coche=True, separateur_avant=True),
    entree('Panneau lateral', raccourci='&#8984;&#8679;P', coche=True),
    entree('File des taches', raccourci='&#8984;&#8679;T', coche=False),
    entree('Plein ecran', raccourci='&#8963;&#8984;F', separateur_avant=True),
    largeur=290)

M_APP = menu('',
    entree('A propos de mmu'),
    entree('Preferences&hellip;', raccourci='&#8984;,', separateur_avant=True),
    entree('Masquer mmu', raccourci='&#8984;H', separateur_avant=True),
    entree('Quitter mmu', raccourci='&#8984;Q', separateur_avant=True),
    largeur=250)

etat_b = f'''
  <h2>Etat B &mdash; Affichage, et le menu applicatif</h2>
  <div class="deux-os">
    <div class="osq">
      <span class="osq-t">Affichage &mdash; les vues et les panneaux</span>
      <div class="app">
    {fenetre(barre(MAC, 'Affichage', pomme=True, app='mmu'), M_AFFICHAGE, 232)}
      </div>
    </div>
    <div class="osq">
      <span class="osq-t">mmu &mdash; ce que macOS attend a cet endroit</span>
      <div class="app">
    {fenetre(barre(MAC, 'mmu', pomme=True, app='mmu'), M_APP, 40)}
      </div>
    </div>
  </div>
  <p class="caption">Les cases a cocher <b class="k">disent l'etat courant</b> : chutier et
  panneau ouverts, file des taches fermee. C'est ce qui fait de ce menu autre chose qu'une liste
  de raccourcis &mdash; on y lit l'ecran. Et <i>Preferences</i> est sous <b class="k">mmu</b> avec
  <code>&#8984;,</code>, parce que c'est la que macOS l'a mis pour tout le monde.</p>
'''

# --- C : Windows, ou les memes commandes changent de place ----------------
M_OUTILS = menu('',
    entree('Preferences&hellip;', raccourci='Ctrl+,'),
    entree('Calibration du scanner&hellip;', separateur_avant=True),
    entree('Generer une planche de calibration&hellip;'),
    entree('Ouvrir le dossier du journal', separateur_avant=True),
    largeur=300)

M_ALLER = menu('',
    entree('Image precedente', raccourci='&#8592;'),
    entree('Image suivante', raccourci='&#8594;'),
    entree('Aller a l\'entree', raccourci='&#8679;I', separateur_avant=True),
    entree('Aller a la sortie', raccourci='&#8679;O'),
    entree('Marqueur precedent', raccourci='&#8679;&#8592;', separateur_avant=True),
    entree('Marqueur suivant', raccourci='&#8679;&#8594;'),
    entree('Aller au timecode&hellip;', raccourci='Ctrl+G', separateur_avant=True),
    largeur=280)

etat_c = f'''
  <h2>Etat C &mdash; Windows : les memes commandes, une autre place</h2>
  <div class="deux-os">
    <div class="osq">
      <span class="osq-t">Outils &mdash; ou Windows attend les Preferences</span>
      <div class="app">
    {fenetre(barre(WIN, 'Outils'), M_OUTILS, 292)}
      </div>
    </div>
    <div class="osq">
      <span class="osq-t">Aller &mdash; identique sur les deux systemes</span>
      <div class="app">
    {fenetre(barre(WIN, 'Aller'), M_ALLER, 216)}
      </div>
    </div>
  </div>
  <p class="caption">Sur Windows il n'y a pas de menu applicatif : les Preferences passent sous
  <b class="k">Outils</b>, avec <code>Ctrl+,</code>. C'est le seul endroit ou les deux barres
  different, et c'est <b class="k">volontaire</b> &mdash; suivre la convention de chaque systeme
  coute moins cher que d'imposer la meme partout.</p>
'''

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>La barre ne cree aucune fonction.</b> Elle
    donne un second chemin, clavier et decouvrable, vers ce que les ateliers portent deja. Deux
    exceptions, et elles sont imposees par le systeme : <i>A propos</i> et <i>Quitter</i>.</p></div>
    <div class="note"><span class="num">2</span><p><b>Les cases a cocher lisent l'ecran.</b>
    Chutier, panneau lateral, file des taches : leur etat est dans le menu. Sans cela, la barre
    ne serait qu'une liste de raccourcis, et le clavier resterait a decouvrir ailleurs.</p></div>
    <div class="note"><span class="num">3</span><p><b>Une difference assumee entre les deux
    systemes.</b> Preferences est sous <i>mmu</i> sur macOS, sous <i>Outils</i> sur Windows.
    Imposer la meme place partout ferait chercher a la moitie des utilisateurs.</p></div>
    <div class="note"><span class="num">4</span><p><b>« Aller au timecode » n'existe que la.</b>
    C'est la seule entree sans equivalent a l'ecran, et c'est une commande de monteur : taper un
    timecode et y sauter. Elle merite d'exister ailleurs &mdash; a voir avec toi.</p></div>
  </div>
'''

HTML = page(
    "La barre de menus systeme",
    "Pertinent, oui : sur macOS une application sans barre de menus ne se pilote pas au clavier "
    "par le systeme et ne repond pas aux conventions qu'on applique sans y penser. La regle de "
    "la proposition : <b class=\"k\">la barre ne cree aucune fonction</b>, elle donne un second "
    "chemin vers ce qui existe deja.",
    etat_a + etat_b + etat_c, notes)

(MOCKUPS / 'key-barre-menus.html').write_text(HTML, encoding='utf-8')
print(f"key-barre-menus.html {(MOCKUPS / 'key-barre-menus.html').stat().st_size/1024:.0f} Ko")
