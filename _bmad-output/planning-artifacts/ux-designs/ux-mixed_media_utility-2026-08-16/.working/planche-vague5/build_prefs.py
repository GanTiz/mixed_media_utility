# -*- coding: utf-8 -*-
"""L'ecran de Preferences — vague 5.

La spine le classait « Reglages globaux, avances — **contenu renvoye a un
second temps** ». Egan, 23 aout : « j'aimerais que l'on fixe ensemble l'ecran
de preferences […] Je te laisse proposer. » Ce second temps est arrive.

Principe de la proposition : **les Preferences ne portent que ce qui vaut pour
tous les projets**. Tout ce qui appartient a un projet (cadences raccourcies,
preset d'export, profil de scanner) vit dans le projet, pas ici -- sinon
ouvrir un autre film change silencieusement les reglages du precedent.

Second principe : **rien de ce qui garantit le jugement colorimetrique n'est
reglable**. Ces lignes apparaissent, figees, avec leur motif. Les cacher
laisserait croire qu'elles n'existent pas ; les rendre modifiables casserait
le produit.
"""
from coquille5 import MOCKUPS, page, groupe, lg

def lg3(cle, aide, controle, *, fige=None):
    m = f'<span class="fige-m">{fige}</span>' if fige else ''
    a = f'<small>{aide}</small>' if aide else ''
    return (f'<div class="lg3{" fige" if fige else ""}">'
            f'<span class="k">{cle}{a}</span>{m}{controle}</div>')

def inter(on=True):
    return f'<span class="inter{" on" if on else ""}"></span>'

def val(v, menu=True):
    car = '<span class="car">&#9662;</span>' if menu else ''
    return f'<span class="v">{v}{car}</span>'

SECTIONS = ['Jugement', 'Previsualisation', 'Taches', 'Fichiers', 'Avance']

def ecran(actif, titre, corps, legende):
    nav = ''.join(f'<div class="pf-s{" on" if s == actif else ""}">{s}</div>' for s in SECTIONS)
    return f'''
  <h2>{titre}</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">Preferences</span></div>
    <div class="prefs">
      <div class="pf-nav">{nav}</div>
      <div class="pf-corps">
{corps}
      </div>
    </div>
  </div>
  <p class="caption">{legende}</p>
'''

# --- A : Jugement — ce qui n'est PAS reglable, et pourquoi -----------------
etat_a = ecran('Jugement', 'Etat A &mdash; Jugement : ce qui ne se regle pas, et pourquoi',
    '''        <h2>Jugement</h2>
        <div class="grp"><span class="tl">Couleur</span>
''' + lg3('Conversion colorimetrique', 'Aucune, sur toute la chaine',
          '<span class="v">desactivee</span>', fige='non modifiable') + '''
''' + lg3('Profil de l\'ecran', 'Lu dans le systeme, applique a l\'affichage seul',
          val('Automatique')) + '''
''' + lg3('Fond des zones d\'image', 'Neutre R=G=B, toujours',
          '<span class="v">#2B2B2B</span>', fige='non modifiable') + '''
        </div>
        <div class="grp"><span class="tl">Interface</span>
''' + lg3('Theme', '', val('Sombre')) + '''
''' + lg3('Taille du texte', '', val('Normale')) + '''
''' + lg3('Langue', 'Prend effet au prochain lancement', val('Francais')) + '''
        </div>
        <div class="avis"><span class="pt"></span><span>Les deux lignes figees sont ce qui rend
        un jugement colorimetrique possible. Elles apparaissent quand meme : les cacher
        laisserait croire qu'elles n'existent pas, ou qu'elles sont reglables ailleurs.</span></div>''',
    "Ma proposition tient a deux regles. La premiere : <b class=\"k\">ce qui garantit le jugement "
    "n'est pas reglable</b>, mais reste visible, avec son motif a cote. Un reglage absent se "
    "cherche ; un reglage fige s'accepte.")

# --- B : Previsualisation et Taches ---------------------------------------
etat_b = ecran('Previsualisation', 'Etat B &mdash; Previsualisation et taches',
    '''        <h2>Previsualisation</h2>
        <div class="grp"><span class="tl">Qualite</span>
''' + lg3('Qualite par defaut', 'A l\'ouverture d\'un lecteur', val('Pleine')) + '''
''' + lg3('Repli automatique', 'Degrade l\'image pour tenir la cadence', inter(True)) + '''
''' + lg3('Le repli se voit', 'Le badge dit la cadence effective, toujours',
          inter(True), fige='non modifiable') + '''
        </div>
        <div class="grp"><span class="tl">Alerte de cadence</span>
''' + lg3('Seuil du bandeau', 'Duree de rouge continu avant le bandeau unique',
          '<span class="v libre">5 s</span>') + '''
''' + lg3('Reafficher les bandeaux desactives', 'Tu en as desactive 2 pour la session',
          '<span class="v">Reactiver</span>') + '''
        </div>
        <div class="grp"><span class="tl">Taches</span>
''' + lg3('Mode de la file', 'Ancree, ou superposee a la scene', val('Ancree')) + '''
''' + lg3('Seuil de superposition', 'En dessous, la file flotte par defaut',
          '<span class="v libre">1100 px</span>') + '''
''' + lg3('Garder les taches terminees', '', val('Jusqu\'a la fermeture')) + '''
        </div>''',
    "Le seuil de cinq secondes que tu as tranche est ici, modifiable. Le fait que le repli "
    "<i>se voie</i> ne l'est pas : c'est la contrepartie de l'avoir autorise. Et le seuil de "
    "superposition de la file vient de ton retour d'hier soir.")

# --- C : Fichiers et Avance -----------------------------------------------
etat_c = ecran('Fichiers', 'Etat C &mdash; Fichiers et avance',
    '''        <h2>Fichiers</h2>
        <div class="grp"><span class="tl">Emplacements</span>
''' + lg3('Dossier de projets par defaut', '', '<span class="v libre">/Volumes/HOKO/films</span>') + '''
''' + lg3('Rouvrir le dernier projet au lancement', 'L\'ecran de projets s\'affiche toujours',
          inter(False), fige='non modifiable') + '''
''' + lg3('Chercher les rushes deplaces', 'Au chargement, dans les dossiers voisins', inter(True)) + '''
        </div>
        <div class="grp"><span class="tl">Avance</span>
''' + lg3('ffmpeg', 'Utilise celui du systeme si vide', '<span class="v libre">/opt/homebrew/bin/ffmpeg</span>') + '''
''' + lg3('Journal', 'Ce que l\'outil ecrit dans son journal', val('Normal')) + '''
''' + lg3('Ouvrir le dossier du journal', '', '<span class="v">Reveler</span>') + '''
        </div>
        <div class="avis"><span class="pt"></span><span>Rien ici n'appartient a un projet. Les
        cadences raccourcies, le preset d'export et le profil de scanner vivent <b>dans le
        projet</b> &mdash; sinon ouvrir un autre film changerait les reglages du precedent sans
        rien dire.</span></div>''',
    "La seconde regle : <b class=\"k\">les Preferences ne portent que ce qui vaut pour tous les "
    "projets</b>. C'est ce qui explique ce qui n'est pas ici &mdash; et la ligne figee du haut "
    "est le corollaire de ta decision d'hier : l'ecran de projets s'affiche toujours.")

notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>Ce qui n'est pas reglable reste
    visible.</b> Trois lignes sont figees et portent leur motif : la conversion colorimetrique,
    le fond neutre des zones d'image, et le fait que le repli de qualite se voie. Les cacher
    ferait chercher ; les ouvrir casserait le produit.</p></div>
    <div class="note"><span class="num">2</span><p><b>Ce qui appartient a un projet n'est pas
    ici.</b> Cadences raccourcies, preset d'export, profil de scanner : dans le projet. Sinon
    ouvrir un autre film modifie silencieusement les reglages du precedent.</p></div>
    <div class="note"><span class="num">3</span><p><b>Meme ossature que les ateliers.</b> Un rail
    de sections a gauche, des reglages a droite. On ne reapprend pas un ecran pour changer une
    valeur.</p></div>
    <div class="note"><span class="num">4</span><p><b>Reactiver les avertissements.</b> Le
    bandeau de cadence est desactivable pour la session ; sans un endroit pour le rallumer, cette
    facilite devient un piege.</p></div>
  </div>
'''

HTML = page(
    "Les Preferences",
    "Tu m'as laisse proposer : voici la proposition, et elle tient a "
    "<b class=\"k\">deux regles</b>. Ce qui garantit le jugement n'est pas reglable mais reste "
    "visible avec son motif ; et les Preferences ne portent que ce qui vaut pour "
    "<b class=\"k\">tous les projets</b>.",
    etat_a + etat_b + etat_c, notes)

(MOCKUPS / 'key-preferences.html').write_text(HTML, encoding='utf-8')
print(f"key-preferences.html {(MOCKUPS / 'key-preferences.html').stat().st_size/1024:.0f} Ko")
