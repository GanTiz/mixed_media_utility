# -*- coding: utf-8 -*-
"""Atelier Exports — vague 3.

Le dernier atelier : un lot reconstruit se relit, se compare au rush d'origine
par balayage, puis s'encode. C'est le climax du parcours de Camille (flow 1,
etapes 14 a 16) : « elle tire le wipe et l'image se transforme sous le
curseur ».

Trois etats. Le troisieme montre l'encodage en cours, ou la previz se bloque --
et le dit, au lieu de devenir inerte sans explication.
"""
from coquille import (MOCKUPS, I, barre_vue, onglets, rail, noeud, chutier,
                      page, transport, lg, groupe, avis, replier)

# --- le chutier des Exports : arborescence INVERSEE, scan > lots reconstruits
ARBRE = noeud('scan', 'scan_2026-08-19.pdf', '3 lots', ouvert=True, sel=False, enfants=(
    noeud('lotr', 'lot 12,5 fps', '167 f.', sel=True)
    + noeud('lotr', 'lot 25 fps', '334 f.')
    + noeud('lotr', 'sequence_4 &middot; 25', '212 f.')))

BIN = chutier('scan_2026-08-19.pdf', '3 lots', ARBRE)
RAIL = rail('encode')

# Le bus de transport des Exports : le meme qu'ailleurs, moins la bascule de
# cadence (elle n'existe qu'en Extraction), plus l'interrupteur de balayage.
def transport_export(son=True):
    """Le bus de transport des Exports.

    EPIC7-ARB-24 : le balayage n'est plus ici. Il s'actionne par un bouton de
    la barre de vue, en haut de l'affichage. Le bus garde ce qui concerne la
    lecture, et rien d'autre.
    """
    t = transport()
    # le son ne s'affiche que si le rush d'origine est sur cette machine
    if not son:
        t = t.replace(f'<span class="tb son" title="Volume">{I["son"]}</span>', '')
    return t


def ecran(titre, tete, corps, panneau, legende, *, wrap='', carte=''):
    if carte:
        cote = carte
    elif panneau is None:
        # EPIC7-ARB-25 : vue sans usage du panneau -> ouverte retractee. La
        # poignee reste, sinon rien ne dit que le panneau peut revenir.
        cote = '      <div class="rappel">&lsaquo;</div>'
    else:
        cote = '      <div class="panel">' + replier() + panneau + '\n      </div>'
    return f'''
  <h2>{titre}</h2>
  <div class="app">
    <div class="app-header"><span class="app-title">Exports &middot; TEST_FILE_12p5 &middot; 12,5 fps</span></div>
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

TIMELINE = '''        <div class="piste">
            <div class="tete" style="left:37%"></div>
          </div>
          <div class="regle"><span>00:00:00:00</span><span>00:00:12:14</span><span>00:00:13:08</span></div>'''

# --- etat A : le lot reconstruit se relit, balayage eteint -----------------
tete_a = (onglets('Lecteur', 'Galerie', 'Lecteur')
          + barre_vue(pas=False, balayage='off')
          + '<div class="cad"><span class="cadb ok"><span class="p"></span>12,5</span>'
            '<span class="qual">pleine <span class="car">&#9662;</span></span></div>')

panneau_a = f'''        <h3>Le lot reconstruit</h3>
{groupe("Lot", lg("Frames", "167 &middot; complet", menu=False), lg("Taille", "1008 &times; 567", menu=False), lg("Cadence cible", "12,5", menu=False))}
        <button class="btn" type="button">Regler l'export</button>'''

etat_a = ecran(
    'Etat A &mdash; le lot reconstruit se relit, a sa cadence cible',
    tete_a,
    '        <div class="mat"><div class="scene"><span class="tc">00:00:12:14</span></div></div>\n' + TIMELINE,
    panneau_a,
    "Le rush d'origine est sur le disque : le son et le balayage sont la. "
    "Un seul bouton allume le balayage &mdash; c'est un mode d'inspection, pas une demonstration.",
    wrap=transport_export())

# --- etat B : le balayage tire, en pause, image par image ------------------
tete_b = (onglets('Lecteur', 'Galerie', 'Lecteur')
          + barre_vue(pas=False, balayage='on')
          + '<div class="cad"><span class="cadb ok"><span class="p"></span>12,5</span>'
            '<span class="qual">pleine <span class="car">&#9662;</span></span></div>')

wipe = '''        <div class="mat">
          <div class="wipe">
            <span class="tc">00:00:12:14</span>
            <div class="apres" style="clip-path:inset(0 0 0 54%)"></div>
            <div class="poignee" style="left:54%"></div>
            <span class="cote g">rush d'origine</span>
            <span class="cote d">lot reconstruit</span>
          </div>
        </div>'''

# EPIC7-ARB-24 : « Pas de panneau a droite c'est inutile. » J'avais vide sa
# prose a 14h19 sans voir qu'il n'avait aucune raison d'exister : un balayage
# se regle en tirant sa poignee. La vue s'ouvre donc panneau retracte.
panneau_b = None

etat_b = ecran(
    'Etat B &mdash; le balayage tire, en pause',
    tete_b, wipe, panneau_b,
    "La poignee est neutre, comme le passe-partout : rien de colore ne se pose sur une image "
    "qu'on juge. Le balayage se coupe et se remet d'un clic, sans quitter le point de lecture.",
    wrap=transport_export())

# --- etat C : reglages, puis encodage ; la previz se bloque et le dit ------
tete_c = (onglets('Lecteur', 'Galerie', 'Lecteur')
          + barre_vue(pas=False, balayage='gris')
          + '<div class="cad"><span class="cadb ok"><span class="p"></span>12,5</span></div>')

bloque = '''        <div class="mat"><div class="scene"><span class="tc">00:00:12:14</span></div></div>
        <div class="bloque">
          <span class="txt">Encodage en cours &mdash; la previsualisation reprend a la fin.</span>
          <div class="jauge"><i></i></div>
          <span class="meta">38 % &middot; 63 frames sur 167</span>
        </div>'''

# EPIC7-ARB-23 : « le menu d'export que tu proposes tient dans ce panneau qui
# fait la meme largeur. Tu peux donc le mettre directement. » Les reglages
# n'ont donc pas de surface propre -- ce qui ne retire rien a leur contenu,
# arrete en ARB-19. La carte, elle, est autre chose : une carte de TACHE, et
# c'est l'objet de la vague 4.
panneau_c = f'''        <h3>Reglages d'export</h3>
{groupe("Preset", lg("Preset", "HOKO &mdash; master ProRes"), lg("Etat", "modifie, non enregistre", menu=False))}
{groupe("Video", lg("Format", "QuickTime"), lg("Codec", "Apple ProRes"), lg("Variante", "422 HQ"), lg("Resolution", "1008 &times; 567", libre=True, menu=False), lg("Cadence", "12,5", libre=True, menu=False), lg("Debit", "automatique"), lg("Profondeur", "10 bits"))}
{groupe("Audio", lg("Exporter le son", "oui"), lg("Codec", "PCM 24 bits"), lg("Echantillonnage", "48 kHz"), lg("Pistes", "1 stereo"))}
{groupe("Fichier", lg("Nom", "TEST_FILE_12p5_125_master", libre=True, menu=False), lg("Destination", "/Volumes/HOKO/exports/", libre=True, menu=False))}
        <div class="recap">167 frames &middot; taille estimee 1,4 Go</div>
        <button class="btn" type="button">Exporter</button>'''

etat_c = ecran(
    "Etat C &mdash; les reglages dans le panneau, et l'encodage en cours",
    tete_c, bloque, panneau_c,
    "Tu avais raison : tout tient dans le panneau, qui fait deja la bonne largeur. Le balayage "
    "est grise ici parce qu'un encodage tourne &mdash; meme forme que lorsque le rush natif "
    "manque, et pour la meme raison : il reviendra.")

# --- l'etat degrade, en note : le rush n'est pas sur cette machine ---------
notes = '''
  <div class="notes hors">
    <div class="note"><span class="num">1</span><p><b>Sans le rush, le balayage est grise.</b>
    Pas absent : il redeviendra actionnable au relink, et le faire disparaitre ferait croire que
    la fonction n'existe pas. C'est la difference avec un onglet sans objet, qui lui n'existe
    pas du tout. Le chutier peint le rush en rouge, sans badge ni mention.</p></div>
    <div class="note"><span class="num">2</span><p><b>Pas de bascule de cadence ici.</b> Les
    fleches qui passent d'une cadence a l'autre n'existent qu'en Extraction : sur Exports, on
    encode un lot precis, pas une famille de lots.</p></div>
    <div class="note"><span class="num">3</span><p><b>Le panneau se retire.</b> Sur les quatre
    ateliers, par la meme commande. Une vue qui n'a rien a y mettre s'ouvre deja retractee
    &mdash; le balayage en est le cas type : il se regle en tirant sa poignee, pas dans un
    formulaire. La poignee de rappel reste, sinon rien ne dirait qu'il revient.</p></div>
    <div class="note"><span class="num">4</span><p><b>Le refus d'encodage se dit en toutes
    lettres.</b> Le motif vient de <code>ENCODE_REFUSAL_CODES</code>, affiche verbatim sur la
    carte de tache, a cote du plan prevu quand il en existe un. On ne traduit pas un code du coeur en
    formule vague.</p></div>
  </div>
'''

HTML = page(
    "L'atelier Exports",
    "Un lot reconstruit, le rush d'origine a cote, et un master a la fin. "
    "<b class=\"k\">Le balayage est le point de jugement</b> : c'est la que l'on voit si le geste "
    "de la main est entre dans le plan, et il s'inspecte image par image.",
    etat_a + etat_b + etat_c, notes)

(MOCKUPS / 'key-exports.html').write_text(HTML, encoding='utf-8')
print(f"key-exports.html {(MOCKUPS / 'key-exports.html').stat().st_size/1024:.0f} Ko")
