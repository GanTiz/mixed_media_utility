# -*- coding: utf-8 -*-
"""Les modales — vague 4.

Jamais maquettees. Contrat de la spine, verbatim : « 1 niveau. Confirmation
d'extraction : cadences cochables + espace disque annonce. Ecrasement : dit ce
qui est detruit, jamais force. Calibration scanner : nom du scanner, dpi,
format, commentaire libre sur les reglages du scanner. »

Ces trois modales sont les seuls endroits ou une ecriture est consentie. Le
consentement se rejoue integralement au lancement, quelle que soit la fraicheur
de la previz affichee.
"""
from coquille4 import MOCKUPS, page, lg, groupe


def modale(titre, corps, pied):
    return f'''    <div class="scrim">
      <div class="mod">
        <div class="mod-h"><h3>{titre}</h3></div>
        <div class="mod-c">
{corps}
        </div>
        <div class="mod-p">
{pied}
        </div>
      </div>
    </div>'''


def ecran(titre, corps, legende):
    return f'''
  <h2>{titre}</h2>
  <div class="app">
{corps}
  </div>
  <p class="caption">{legende}</p>
'''


def coche(nom, meta, on=False):
    p = '<span class="puce all"></span>' if on else '<span class="puce"></span>'
    return f'<div class="coche">{p}<span>{nom}</span><span class="meta">{meta}</span></div>'


# --- A : confirmation d'extraction ----------------------------------------
# « cadences cochables + espace disque annonce ». L'espace est la parce qu'une
# extraction TIFF remplit un disque en quelques minutes, et qu'on ne le
# decouvre autrement qu'a l'echec.
etat_a = ecran(
    'Modale A &mdash; confirmer une extraction',
    modale('Extraire les lots &mdash; TEST_FILE_12p5.mov',
           f'''          <div class="grp"><span class="tl">Cadences a extraire</span>
{coche("12,5 images/s", "167 f. &middot; 1,4 Go", on=True)}
{coche("25 images/s", "334 f. &middot; 2,8 Go", on=True)}
{coche("50 images/s", "668 f. &middot; 5,6 Go")}
          </div>
          <div class="grp"><span class="tl">Bornes</span>
{lg("Entree", "00:00:08:04", menu=False)}
{lg("Sortie", "00:00:21:12", menu=False)}
          </div>''',
           '''          <span class="esp">4,2 Go a ecrire &middot; 218 Go libres sur /Volumes/HOKO</span>
          <button class="btn ghost" type="button">Annuler</button>
          <button class="btn" type="button">Extraire 501 frames</button>'''),
    "Les cadences sont cochables : on en lance plusieurs d'un coup. L'<b class=\"k\">espace "
    "disque est annonce</b> avant, pas decouvert a l'echec &mdash; une extraction TIFF remplit "
    "un disque en quelques minutes. L'action porte son cardinal, comme partout ailleurs.")

# --- B : ecrasement -------------------------------------------------------
etat_b = ecran(
    'Modale B &mdash; ecraser un lot existant',
    modale('Ce lot existe deja',
           '''          <div class="detruit">
            <b>Ce qui serait detruit</b>
            <span>167 frames TIFF &middot; 1,4 Go</span>
            <span>extraites le 19/08 a 14:32</span>
            <span>/Volumes/HOKO/films/vent/mmu/lots/TEST_FILE_12p5_125/</span>
          </div>
          <p class="hint">Les planches deja generees a partir de ces frames ne sont pas
          touchees, mais elles ne correspondront plus au contenu du lot.</p>''',
           '''          <span class="esp">aucune action par defaut</span>
          <button class="btn ghost" type="button">Annuler</button>
          <button class="btn" type="button">Garder les deux</button>
          <button class="btn ghost rouge" type="button">Ecraser</button>'''),
    "Elle <b class=\"k\">nomme ce qui serait detruit</b> &mdash; le nombre, la taille, la date, "
    "le chemin &mdash; au lieu d'une phrase generale sur laquelle on ne peut pas decider. "
    "<i>Garder les deux</i> porte le bouton plein : l'emphase visuelle va au chemin qui ne detruit "
    "rien, et <i>Ecraser</i> reste offert, en creux et cerne de rouge.")

# --- C : calibration scanner ----------------------------------------------
etat_c = ecran(
    'Modale C &mdash; enregistrer une calibration de scanner',
    modale('Calibration du scanner',
           f'''          <div class="grp"><span class="tl">Le scanner</span>
{lg("Nom", "Epson V850 &mdash; atelier", libre=True, menu=False)}
{lg("Resolution", "1200 dpi", libre=True, menu=False)}
{lg("Format", "A3")}
          </div>
          <div class="grp"><span class="tl">Commentaire</span>
            <div class="zone vide">ex. gestion des couleurs desactivee, nettete a 0,
            detourage automatique off, correction de poussiere off, vitre nettoyee</div>
          </div>''',
           '''          <span class="esp">le profil sera lie a ce projet</span>
          <button class="btn ghost" type="button">Annuler</button>
          <button class="btn" type="button">Enregistrer le profil</button>'''),
    "Le champ s'appelle <b class=\"k\">Commentaire</b>, et l'exemple est en texte de substitution "
    "&mdash; il montre quoi ecrire sans faire croire que quelque chose a deja ete saisi. Ce n'est "
    "pas un champ de confort : les reglages d'un "
    "scanner ne se lisent nulle part dans le fichier produit. Sans lui, on ne sait pas six mois "
    "plus tard pourquoi deux calibrations du meme materiel ne donnent pas la meme chose.")

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>Un seul niveau.</b> Une modale n'en ouvre
    jamais une autre. Si un choix en appelle un second, les deux tiennent dans la meme fenetre
    ou le second n'est pas une modale.</p></div>
    <div class="note"><span class="num">2</span><p><b>La previz n'autorise rien.</b> Ce qui est
    affiche a l'ecran, si frais soit-il, ne vaut pas consentement : il se rejoue integralement
    ici, au lancement de l'ecriture. C'est la seule porte.</p></div>
    <div class="note"><span class="num">3</span><p><b>Une erreur de lot se leve avant la
    modale.</b> Sur le parcours de Camille, le lot deja existant se signale au clic sur
    « extraire les lots », pas dans la fenetre de confirmation &mdash; une metadonnee manquante
    rougit son champ et bloque l'action avant meme d'en arriver la.</p></div>
    <div class="note"><span class="num">4</span><p><b>L'emphase ne va jamais a la
    destruction.</b> Sur la modale d'ecrasement, le bouton plein est <i>Garder les deux</i> ;
    <i>Ecraser</i> est en creux, cerne de rouge. Et rien n'est preselectionne : la touche entree
    n'y detruit pas 1,4 Go.</p></div>
  </div>
'''

HTML = page(
    "Les modales",
    "Les trois seuls endroits ou une ecriture est consentie. Elles ont un contrat commun : "
    "<b class=\"k\">un seul niveau</b>, et le consentement se rejoue integralement au lancement "
    "&mdash; ce qu'affiche la previz, si frais soit-il, n'autorise jamais rien.",
    etat_a + etat_b + etat_c, notes)

(MOCKUPS / 'key-modales.html').write_text(HTML, encoding='utf-8')
print(f"key-modales.html {(MOCKUPS / 'key-modales.html').stat().st_size/1024:.0f} Ko")
