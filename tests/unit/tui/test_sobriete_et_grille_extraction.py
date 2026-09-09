# -*- coding: utf-8 -*-
"""Story 11.4, lot G -- grille, glyphes, couleur, sobriete (AC 8).

Ce banc mesure les **douze** ecrans `E2-*` de l'atelier Extraction sur les cinq
proprietes que l'AC 8 pose, et il les mesure **des deux cotes a la fois** : sur
les maquettes ET sur les ecrans reels. C'est la seule disposition qui ferme le
mode de panne de la vague precedente -- une maquette propre au-dessus d'un
ecran fautif -- et ce mode de panne n'est pas theorique : la ligne d'etat de
`E2-3b` disait `Edition des noms. Echap abandonne, Entree valide.` alors que sa
maquette portait `31 caracteres sur 48 -- le nom reste valide`. Deux noms de
touche et un conseil d'usage, dans la zone ou `EPIC11-ARB-56` n'admet qu'une
mesure, sous une maquette conforme depuis trois commits.

**Ce que ce banc mesure, et ce qu'il ne prouve pas.** L'interdit
d'`EPIC11-ARB-56` porte sur trois choses : un nom de touche, un conseil
d'usage, un motif de conception.

* le **nom de touche** se mesure mecaniquement, sur un vocabulaire **lu du
  paquet lui-meme** -- c'est la moitie solide ;
* le **conseil d'usage** se mesure sur un lexique ferme de tournures
  directives, verifie mordant sur les cinq lignes reellement fautives du
  depot ;
* le **motif de conception** ne se mesure pas vraiment. `EPIC11-ARB-30` le dit
  deja : « aucun test generique ne distingue un constat d'un jugement », et
  c'est pour cela qu'il a ete promu en AC a inventaire ferme plutot qu'en test.
  Le lexique :data:`MOTIFS_DE_CONCEPTION` ci-dessous n'attrape que les deux
  tournures qu'une ligne du depot a portees ; le vrai filet est
  :func:`test_les_phrases_NON_CHIFFREES_des_lignes_d_etat_sont_dans_l_INVENTAIRE`,
  qui rougit des qu'une phrase non chiffree apparait sans avoir ete adossee a
  une constante nommee ou a un arbitrage.

Meme honnetete que le docstring de `jetons.jeton_d_etat` : on ecrit ce que la
forme ne prouve pas, plutot que de laisser croire a une preuve.

**Regle des fabriques** (`CLAUDE.md`) : les corpus de ce banc portent tous
plusieurs elements distinguables, la cible n'est jamais en premiere position,
et le rang du curseur passe a `peindre` vaut au moins 1 dans les bancs de
couleur -- un `peindre` qui surlignerait toujours la premiere ligne passerait
autrement.
"""
import re
import sys
import unicodedata
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.tui import (
    atelier_extraction,
    atelier_extraction_ecriture as ecriture,
    execution,
    jetons,
    noms as modele_des_noms,
    rushes,
)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.execution import EcranExecution, SurfaceExecution

# Les fabriques des trois bancs voisins sont **reutilisees, jamais recopiees** :
# une seconde fixture de rush ou de cadence divergerait de la premiere au
# premier ajustement, et c'est exactement le motif que `CLAUDE.md` documente
# pour les valeurs recopiees.
import test_atelier_extraction_cadences as banc_cadences
import test_atelier_extraction_rushes as banc_rushes
from test_repli_ascii import lignes_de_raccourcis_du_paquet

RACINE = Path(__file__).resolve().parents[3]
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: Les deux regimes, portes par tout test qui touche au rendu. « Ne jamais
#: ajuster un test au code : tout test parametre porte les deux regimes »
#: (`CLAUDE.md`, pieges deja payes).
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: **Les douze ecrans de l'atelier**, et non les neuf que la fiche annonce :
#: `E2-1b`, `E2-1c` et `E2-1d` sont nes du relink au lot E. Le compte est
#: **derive du disque**, jamais ecrit : une maquette ajoutee entre dans la
#: mesure sans que personne ait a y penser.
#: L'identifiant d'une maquette : `E2-`, son rang, et la lettre de variante
#: quand il y en a une. Rien d'autre -- surtout pas la partie descriptive.
IDENTIFIANT_DE_MAQUETTE = re.compile(r"^(E2-\d+[a-z]?)-")


def maquettes_de_l_atelier() -> dict[str, Path]:
    """Les maquettes de l'atelier, indexees par leur IDENTIFIANT.

    **La derivation a change le 2026-09-01, sur defaut mesure.** Elle retirait
    les suffixes descriptifs par une liste NOMMEE -- `.split("-extraction")[0]`
    puis `.split("-relink")[0]`. Toute famille neuve de maquettes echappait donc
    a la liste et recevait pour cle son **nom de fichier entier**, extension
    comprise : `E2-1e-declaration-confirmation.txt` au lieu de `E2-1e`. C'est
    exactement ce qui est arrive aux deux maquettes de la declaration de rush
    (`EPIC11-ARB-144`), et le cardinal ci-dessous ne l'a attrape que par
    accident -- il comptait, il ne regardait pas la FORME des cles.

    Une derivation qui enumere ce qu'elle retire doit etre tenue a jour a chaque
    ajout ; celle-ci extrait ce qu'elle garde, donc elle n'a rien a rattraper.
    """
    indexees = {}
    for chemin in sorted(MAQUETTES.glob("E2-*.txt")):
        trouve = IDENTIFIANT_DE_MAQUETTE.match(chemin.name)
        assert trouve is not None, (
            f"{chemin.name} ne porte pas d'identifiant de la forme "
            "`E2-<rang><variante>-<description>.txt`")
        indexees[trouve.group(1)] = chemin
    return indexees


#: Le rang de la ligne d'ETAT dans la grille, **derive** de la hauteur du
#: plancher : c'est l'avant-avant-derniere ligne (bordure basse, raccourcis,
#: etat). Compte depuis 1, comme le verificateur de maquettes compte.
RANG_DE_L_ETAT = jetons.HAUTEUR_PLANCHER - 2


def lignes_de_maquette(chemin: Path) -> list[str]:
    """Les 24 lignes de la GRILLE, sans les notes manuscrites qui la suivent."""
    lignes = chemin.read_text(encoding="utf-8").rstrip("\n").split("\n")
    return lignes[:jetons.HAUTEUR_PLANCHER]


def contenu_de_la_ligne(ligne: str) -> str:
    """Ce qu'une ligne de maquette porte a l'interieur de son cadre."""
    return ligne[1:-1].strip() if ligne.startswith("│") else ligne.strip()


# ===========================================================================
# Le vocabulaire des touches -- LU du paquet, jamais recopie
# ===========================================================================

#: Les noms de touche qui ne sont **pas** des lettres. Inventaire ferme, ecrit
#: ici parce que le depot n'en a aucune constante : ce sont les noms des
#: touches d'un clavier, pas des valeurs du produit. Il est **verifie non vide
#: et effectivement present dans le paquet** par le volet symetrique
#: ci-dessous, ce qui l'empeche de deriver en liste morte.
_TOUCHES_NOMMEES = re.compile(
    r"^(Tab|Échap|Echap|Entrée|Entree|Espace|Suppr|Retour"
    r"|Ctrl\+\S+|Alt\+\S+|Maj\+\S+|Cmd\+\S+|F\d{1,2})$")

#: Les glyphes qui **sont** des touches.
GLYPHES_DE_TOUCHE = ("↑", "↓", "←", "→", "⏎", "⌫")

#: **Les deux lettres que la mesure par lettre isolee ne peut pas prendre.**
#: `a` et `y` sont des mots francais courants (`il n'y a rien a conserver`) ;
#: exiger d'eux la meme frontiere que de `x` ou `o` ferait rougir des lignes
#: d'etat parfaitement mesurees. C'est une limite reconnue, pas un oubli : une
#: ligne qui nommerait vraiment la touche `a` la nommerait dans une tournure de
#: conseil (« a pour ajouter », « tapez a »), et le lexique des conseils la
#: prend alors. Meme honnetete que le docstring de `jetons.jeton_d_etat` : on
#: dit ce que la forme ne prouve pas.
LETTRES_AMBIGUES = frozenset({"a", "y"})


def touches_annoncees() -> set[str]:
    """Le vocabulaire des touches, **lu des lignes de raccourcis du paquet**.

    Une ligne de raccourcis est faite d'items separes par au moins deux blancs,
    chacun ouvert par sa touche : `⏎ choisir   ↑↓ naviguer   Tab ajouter`. Le
    premier mot de chaque item est donc une touche, et c'est la seule source de
    verite du depot sur ce qu'est une touche -- la recopier ici en ferait une
    seconde, qui divergerait au premier raccourci ajoute.

    Les deux touches du relink (`r`, `d`) s'y ajoutent depuis
    `rushes.TOUCHES_DE_MODE` : elles ne sont annoncees **que** sur la ligne du
    rush absent (`E2-1`), jamais en ligne de raccourcis, et un vocabulaire qui
    les ignorerait laisserait passer exactement la ligne d'etat que la maquette
    d'origine portait.
    """
    trouvees: set[str] = set(rushes.TOUCHES_DE_MODE)
    for ligne in lignes_de_raccourcis_du_paquet().values():
        for item in re.split(r"\s{2,}", ligne.strip()):
            mots = item.split()
            if not mots:
                continue
            premier = mots[0]
            if _TOUCHES_NOMMEES.match(premier):
                trouvees.add(premier)
            elif len(premier) == 1 and premier.isalpha():
                trouvees.add(premier)
    return trouvees


def _sans_le_glyphe_d_etat(ligne: str) -> str:
    """Retire le glyphe d'etat qui OUVRE une ligne d'etat.

    Il n'est pas une touche : c'est le second canal de `DESIGN.md` section 6.
    Le retirer est necessaire et non cosmetique -- en repli ASCII le glyphe
    `absent` est la lettre `x`, qui est aussi le raccourci « extraire sans
    voir » de `E2-2`. Sans ce retrait, la ligne d'etat de `E2-1d`
    (`x  candidats-multiples ...`) serait declaree fautive alors qu'elle est la
    forme meme que les maquettes prescrivent.
    """
    for ascii_seul in (False, True):
        for nom in jetons.NOMS_D_ETAT + ("neutre",):
            glyphe = jetons.glyphes(ascii_seul)[nom]
            if ligne.startswith(glyphe + " "):
                return ligne[len(glyphe):].lstrip()
    return ligne


def noms_de_touche_trouves(ligne: str) -> list[str]:
    """Les noms de touche que porte une ligne d'etat. Vide = conforme.

    Trois formes, et elles ne se mesurent pas de la meme facon :

    * un **glyphe** de touche se cherche tel quel, il ne peut rien vouloir dire
      d'autre ;
    * un **nom** de touche se cherche entre frontieres de mot ;
    * une **lettre** de raccourci ne se cherche qu'isolee par des blancs. Sans
      cette derniere restriction, le `a` de « il n'a rien ecrit » serait pris
      pour la touche `a` de `E2-2`.
    """
    nue = _sans_le_glyphe_d_etat(ligne)
    trouves = []
    for glyphe in GLYPHES_DE_TOUCHE:
        if glyphe in nue:
            trouves.append(glyphe)
    cherchees = set()
    for touche in touches_annoncees():
        cherchees.add(touche)
        if len(touche) > 1:
            # **Le repli ASCII du nom compte aussi.** `Échap` s'ecrit `Echap`
            # une fois replie, et c'est sous cette forme exacte que la ligne
            # d'etat de `E2-3b` portait la touche : un vocabulaire qui ne
            # connaitrait que la forme accentuee l'aurait laissee passer.
            cherchees.add(jetons.replier_ascii(touche))
    cherchees.add(jetons.REPLIS_DE_TEXTE["⏎"])      # `Entree`, repli de `⏎`
    for touche in sorted(cherchees):
        if len(touche) == 1:
            if touche in LETTRES_AMBIGUES:
                continue
            motif = rf"(?<![^\s]){re.escape(touche)}(?![^\s])"
        else:
            motif = rf"(?<![\w+]){re.escape(touche)}(?![\w])"
        if re.search(motif, nue):
            trouves.append(touche)
    return trouves


#: Les marques d'un **conseil d'usage** : une phrase qui dit a l'operateur quoi
#: faire, plutot que de mesurer ce qu'il regarde. Inventaire ferme, et le volet
#: symetrique le fait mordre sur les quatre lignes d'etat reellement fautives
#: du 2026-08-29 -- sans quoi il pourrait derive en liste sans effet.
#:
#: `pour <infinitif>` est le motif central : c'est la forme d'une consigne
#: (`↑↓ pour choisir`, `Echap pour en ajouter`), la ou une mesure emploie `sur`,
#: `de` ou un separateur.
CONSEILS = (
    r"pour\s+(?:en\s+|y\s+|le\s+|la\s+|les\s+|se\s+)?\w+(?:er|ir|re)\b",
    r"\bpas besoin\b",
    r"\bil suffit\b",
    r"\bil faut\b",
    r"\bvous pouvez\b",
    r"\bpensez\b",
    r"\bessayez\b",
    r"\btapez\b",
    r"\bappuyez\b",
    r"\bretirez\b",
    r"\bpressez\b",
)


#: Les marques d'un **motif de conception** : une phrase qui explique ce qu'une
#: chose EST ou N'EST PAS, au lieu de mesurer ce qu'elle vaut. Lexique ferme et
#: volontairement etroit -- `EPIC11-ARB-30` dit deja qu'« aucun test generique
#: ne distingue un constat d'un jugement », et c'est
#: :func:`test_les_phrases_NON_CHIFFREES_des_lignes_d_etat_sont_dans_l_INVENTAIRE`
#: qui porte le filet general. Ces deux motifs-ci ne sont la que parce qu'ils
#: mordent sur des lignes REELLEMENT ecrites : `Previsualiser n'ecrit rien :
#: c'est une lecture, pas une extraction.` (maquette `E2-2`, commit `289f29d`).
MOTIFS_DE_CONCEPTION = (
    r"\bc'est\s+(?:une?|du|de\s+la)\b",
    r"\bn'est\s+pas\s+(?:une?|du|de\s+la)\b",
    r",\s*pas\s+une?\s+\w+",
)


def conseils_trouves(ligne: str) -> list[str]:
    """Les marques de conseil d'usage que porte une ligne d'etat."""
    return [motif for motif in CONSEILS
            if re.search(motif, ligne, flags=re.IGNORECASE)]


def motifs_trouves(ligne: str) -> list[str]:
    """Les marques de motif de conception que porte une ligne d'etat."""
    return [motif for motif in MOTIFS_DE_CONCEPTION
            if re.search(motif, ligne, flags=re.IGNORECASE)]


def ecarts_de_sobriete(ligne: str) -> list[str]:
    """Tout ce qu'`EPIC11-ARB-56` interdit et qui se mesure mecaniquement."""
    return (noms_de_touche_trouves(ligne) + conseils_trouves(ligne)
            + motifs_trouves(ligne))


# ---------------------------------------------------------------------------
# Volets symetriques du vocabulaire : sans eux, une liste devenue vide
# passerait pour une conformite.
# ---------------------------------------------------------------------------

def test_le_vocabulaire_des_touches_est_LU_du_paquet_et_NON_VIDE():
    """Le vocabulaire vient du paquet ; s'il s'effondrait, tout serait vert."""
    touches = touches_annoncees()
    assert len(touches) >= 8, sorted(touches)
    # Les cinq familles doivent etre representees : un nom, une lettre de
    # raccourci d'atelier, une lettre de relink, une touche a modificateur, une
    # touche de fonction. Une seule famille suffirait a rendre la liste inutile.
    #
    # **`X` en majuscule et `r` en minuscule, et l'ecart est la regle** (lot
    # `O`, 2026-08-30) : le vocabulaire est lu des lignes de RACCOURCIS, ou
    # toute lettre s'affiche desormais en majuscule, et de `TOUCHES_DE_MODE`,
    # qui est une table de TOUCHES CABLEES et reste donc en minuscule. Les deux
    # formes cohabitent ici parce qu'elles mesurent deux choses differentes.
    for attendue in ("Tab", "Échap", "X", "r", "F1"):
        assert attendue in touches, (attendue, sorted(touches))


@pytest.mark.parametrize("ligne,attendu", [
    # Les QUATRE lignes d'etat fautives du 2026-08-29, verbatim du commit
    # `289f29d` -- ce sont elles que l'AC 8.4 nomme (« quatre des neuf
    # maquettes E2-* violent cette regle aujourd'hui ») et qu'`EPIC11-ARB-56`
    # vise : « la ligne d'etat [...] ne porte aucune touche [...] aucun conseil
    # d'usage [...] aucun motif de conception ».
    ("Un rush absent se rebranche depuis ici — pas besoin de sortir de "
     "l'écran.", "E2-1"),
    ("Prévisualiser n'écrit rien : c'est une lecture, pas une extraction.",
     "E2-2"),
    ("Seules les cadences prévisualisées sont ici. Échap pour en ajouter.",
     "E2-2c"),
    ("Rien n'a encore été écrit. ↑↓ pour choisir, Entrée pour valider.",
     "E2-3"),
    # La cinquieme, trouvee dans le CODE et non sur une maquette : la ligne
    # d'etat de `E2-3b` en edition. Elle est la raison d'etre de ce banc.
    ("Edition des noms. Echap abandonne, Entree valide.", "E2-3b"),
])
def test_la_frontiere_de_SOBRIETE_MORD(ligne, attendu):
    """Le volet symetrique, et il porte sur des lignes REELLEMENT ecrites.

    Une frontiere negative qui ne mord sur rien de mesure ne prouve pas
    grand-chose ; celle-ci mord sur les cinq lignes que le depot a portees,
    quatre en maquette et une en code.
    """
    assert ecarts_de_sobriete(ligne), (attendu, ligne)


@pytest.mark.parametrize("ligne", [
    # Des lignes d'etat CONFORMES, et volontairement pieges :
    "3 rushes déclarés · 2 liés, 1 introuvable",           # aucune touche
    "✕  candidats-multiples · le manifest est inchangé",   # glyphe d'etat en tete
    "x  candidats-multiples · le manifest est inchange",   # le meme, replie
    "2 lots · 166 frames · ~ 2,8 Go (majorant)",
    "31 caractères sur 48 — le nom reste valide",
    "34 fichiers · 31 vidéos, 3 ignorés",
    # `a` verbe, `y a`, `d'` : les pieges de la mesure par lettre isolee.
    "Rien n'a encore ete ecrit, il n'y a rien a conserver",
])
def test_la_frontiere_de_SOBRIETE_ne_mord_PAS_sur_une_MESURE(ligne):
    """Volet symetrique inverse : une frontiere qui mord sur tout est inutile.

    Les deux derniers cas sont les faux positifs qu'une mesure naive produit :
    le glyphe ASCII de l'etat `absent` EST la lettre `x`, raccourci de `E2-2`,
    et `a` est un verbe francais courant.
    """
    assert ecarts_de_sobriete(ligne) == [], ligne


# ===========================================================================
# AC 8.4 -- les MAQUETTES : aucune ligne d'etat ne porte de touche
# ===========================================================================

@pytest.mark.parametrize("nom", sorted(maquettes_de_l_atelier()))
def test_aucune_ligne_d_etat_des_MAQUETTES_d_extraction_ne_porte_un_NOM_DE_TOUCHE(
        nom):
    """AC 8.4, volet maquette. Les quatre ecarts de `289f29d` sont fermes.

    La correction s'est faite **a la source** (`_gen_extraction.py`), jamais
    dans le fichier rendu : c'est ce que ce banc constate a posteriori, en
    lisant les maquettes que le generateur produit.
    """
    ligne = contenu_de_la_ligne(
        lignes_de_maquette(maquettes_de_l_atelier()[nom])[RANG_DE_L_ETAT - 1])
    assert ecarts_de_sobriete(ligne) == [], (nom, ligne)


def test_les_DIX_HUIT_maquettes_de_l_atelier_sont_VUES_par_la_mesure():
    """Volet symetrique du balayage : un glob qui ne rendrait rien serait vert.

    Dix-huit : neuf a l'origine, plus `E2-1b`, `E2-1c` et `E2-1d` nees du
    relink, plus `E2-1e` et `E2-1f` nees de la declaration d'un rush
    (`EPIC11-ARB-144`, 2026-09-01), plus `E2-1g` nee le meme jour de la
    relecture d'Egan, plus `E2-1h` nee de sa relecture v2 le meme jour encore,
    plus `E2-1i` nee d'`EPIC11-ARB-227` le 2026-09-05, plus `E2-1j` nee
    d'`EPIC11-ARB-239` le meme jour.

    **Ni `E2-1g`, ni `E2-1h`, ni `E2-1i` ne sont un ecran de plus : ce sont les
    DEUXIEME, TROISIEME et QUATRIEME ETATS de `E2-1e`**, et chacun ne fait
    varier qu'une chose. `E2-1j`, lui, est le SECOND ETAT de `E2-1f`.

    * `E2-1g` -- la colorimetrie n'est pas signalee par la source. La relecture
      v2 (note 1) y a retire la liste a une entree et le raccourci qui l'ouvrait
      -- « pas de raccourci car pas de choix » -- et y a pose a la place une
      **assertion de traitement** : « le rushe sera traite comme Rec709 par
      defaut ». L'etat se dessine encore, et davantage qu'avant : c'est
      justement parce qu'aucun choix ne s'offre que l'ecran doit dire ce que la
      machine fera ;
    * `E2-1h` -- le chemin source ne tient pas sur ses deux lignes (note 6 :
      « 2 lignes puis on coupe au milieu en gardant les 3 premiers dossiers de
      l'arborescence et les deux derniers au moins »). Une regle de coupe ne se
      lit que contre son cas non coupe, donc les deux se dessinent ;
    * `E2-1i` -- le moteur n'a pas corrobore le cardinal de frames, donc le
      compte s'OMET (`EPIC11-ARB-227`, verbatim d'Egan : « On n'affiche rien si
      on ne corrobore pas »). Meme motif que les deux precedents : une regle
      d'omission ne se lit que contre le cas ou le chiffre est la.
    * `E2-1j` -- les 99 rangs d'homonyme sont pris, donc la sortie « le
      declarer separement » n'a plus rien a consommer et s'efface, remplacee
      par UNE ligne d'explication (`EPIC11-ARB-239`). C'est le meme motif une
      fois de plus : une sortie qui disparait ne se lit que contre l'ecran ou
      elle est la, c'est-a-dire `E2-1f`.

      **Et cette maquette-la est la raison d'etre du cardinal.** Nee a 27
      lignes pour une grille de 24, elle a fait rougir ce banc ET le volet
      `R26` de `test_majuscules_des_raccourcis` -- alors qu'a l'oeil, sur son
      rendu SVG, elle avait l'air juste : la toile est dimensionnee pour 24
      rangs, donc les trois lignes en trop etaient simplement ABSENTES de
      l'image validee. Un cardinal fige est ce qui force a regarder.
    """
    vues = maquettes_de_l_atelier()
    assert len(vues) == 18, sorted(vues)
    for attendue in ("E2-1", "E2-1d", "E2-1e", "E2-1f", "E2-1g", "E2-1h",
                     "E2-1i", "E2-1j", "E2-2c", "E2-3c", "E2-5"):
        assert attendue in vues, sorted(vues)


def test_toute_cle_de_maquette_est_un_IDENTIFIANT_et_non_un_nom_de_fichier():
    """Le volet que le cardinal seul ne donne pas -- et qui a manque.

    Un cardinal compte ; il ne regarde pas la FORME de ce qu'il compte. Quand
    `E2-1e` et `E2-1f` sont arrivees, leur cle etait leur nom de fichier entier,
    extension comprise, et **seul le cardinal a rougi** : la forme, elle, est
    passee inapercue. Une cle qui porte `.txt` casse toute selection par nom.
    """
    vues = maquettes_de_l_atelier()
    fautives = [cle for cle in vues
                if re.fullmatch(r"E2-\d+[a-z]?", cle) is None]
    assert fautives == [], fautives


# ===========================================================================
# AC 8.4 -- les ECRANS REELS. C'est ici que la vague precedente a laisse
# passer un ecart : la maquette etait propre, l'ecran ne l'etait pas.
# ===========================================================================

def coque_de(ecran) -> CoqueTui:
    """Deux paliers temoins sous l'ecran mesure -- comme les bancs voisins."""
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter"), ecran],
                    contexte=Contexte("projet_demo"))


def etat_brut(ecran) -> str:
    """La ligne d'etat **telle que l'ecran l'a posee**, avant ajustement.

    `poser_etat` memorise le texte brut puis l'ajuste a la largeur courante :
    lire le widget rendrait un texte deja abrege, donc une mesure de largeur
    toujours verte et une mesure de sobriete amputee de sa fin. C'est le brut
    qui fait foi des deux cotes.
    """
    return ecran._etat_courant


def lignes_d_etat_reelles(tmp_path, banc, ascii_seul: bool) -> dict[str, str]:
    """La ligne d'etat de chacun des douze ecrans, **montes pour de vrai**.

    Chaque ecran est monte sur le banc headless et rafraichi : c'est son propre
    `etat()` qui est mesure, jamais une constante relue. Un ecran dont la ligne
    d'etat serait posee ailleurs que par `poser_etat` -- c'est le cas de `E2-5`,
    posee par `ouvrir_le_resultat` -- est donc couvert par la meme mesure.
    """
    vues: dict[str, str] = {}
    # **Un dossier par banc voisin.** Les deux fabriques creent un projet
    # nomme `projet_demo` a la racine qu'on leur donne, et `creer_projet`
    # refuse d'ecraser : les melanger leve `ProjetExistantError` au deuxieme.
    des_rushes = tmp_path / "rushes"
    du_jugement = tmp_path / "jugement"
    du_resultat = tmp_path / "resultat"
    for dossier in (des_rushes, du_jugement, du_resultat):
        dossier.mkdir(exist_ok=True)

    # -- E2-1, E2-1b, E2-1c : le meme ecran, ses trois zones ----------------
    ecran = banc_rushes.ecran_de(des_rushes)
    ecran.liste.viser("rush_hiver")          # l'absent est le TROISIEME rush

    async def parcourir_les_rushes(pilote):
        pilote.app.ascii_seul = ascii_seul
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.rafraichir()
        releve = {"E2-1": etat_brut(ecran)}
        for cle, touche in (("E2-1b", "r"), ("E2-1c", "d")):
            ecran.traiter(touche, touche)
            ecran.rafraichir()
            await pilote.pause()
            releve[cle] = etat_brut(ecran)
            ecran.traiter("escape")
            ecran.rafraichir()
        return releve

    application = coque_de(ecran)
    application.ascii_seul = ascii_seul
    vues.update(banc(application, parcourir_les_rushes))

    # -- E2-1d : le refus du relink, par son CODE ---------------------------
    vues["E2-1d"] = _monte(banc, atelier_extraction.EcranRefusRelink(
        banc_rushes.refus_long()), ascii_seul)

    # -- E2-2, E2-2b, E2-2c : les trois ecrans de cadences ------------------
    vues["E2-2"] = _monte(banc, banc_cadences.ecran_de_cadences(), ascii_seul)
    vues["E2-2b"] = _monte(banc, banc_cadences.ecran_de_previz(), ascii_seul)
    vues["E2-2c"] = _monte(banc, banc_cadences.ecran_de_choix(), ascii_seul)

    # -- E2-3 : le point de jugement. **Ses deux etats de nom ont disparu**
    # avec le mode d'edition (`EPIC11-ARB-141`, story 11.4e lot G) : `E2-3b` et
    # `E2-3c` n'etaient pas des ecrans mais des ETATS de celui-ci, et l'ecran
    # n'a plus de champ ou entrer.
    vues.update(_lignes_du_jugement(du_jugement, banc, ascii_seul))

    # -- E2-4 : l'execution en cours ----------------------------------------
    surface = SurfaceExecution("frames")
    surface.emetteur(124).emettre(28)
    vues["E2-4"] = _monte(banc, EcranExecution(surface, "Extraction en cours"),
                          ascii_seul)

    # -- E2-5 : le resultat, dont la ligne d'etat est posee par l'ouverture --
    vues["E2-5"] = _ligne_du_resultat(du_resultat, banc, ascii_seul)
    return vues


def _monte(banc, ecran, ascii_seul: bool) -> str:
    """Monter un ecran, le rafraichir, et rendre sa ligne d'etat brute."""
    application = coque_de(ecran)
    application.ascii_seul = ascii_seul

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.rafraichir()
        await pilote.pause()
        return etat_brut(ecran)

    return banc(application, scenario)


def _lignes_du_jugement(tmp_path, banc, ascii_seul: bool) -> dict[str, str]:
    """`E2-3`, et lui seul depuis `EPIC11-ARB-141`.

    Il rendait aussi `E2-3b` (edition valide) et `E2-3c` (nom refuse) en
    entrant dans le mode d'edition. Le mode est retire : `Tab` n'a plus de
    destination, et les deux etats ne sont plus **atteignables** -- ils ne sont
    donc plus mesurables, ce qui est la forme que prend un retrait dans un banc
    de rendu. Le retrait lui-meme est mesure ailleurs, par une frontiere
    negative (`test_aucun_nom_editable.py`), la seule forme qui rougit a la
    reintroduction.

    Le geste garde ici est celui qui reste : `Tab` **ne change rien**. Sans
    lui, le mode pourrait revenir sans que cette fonction s'en apercoive.
    """
    async def scenario(pilote, ecran):
        avant = etat_brut(ecran)
        assert ecran.traiter("tab") is False
        ecran.rafraichir()
        assert etat_brut(ecran) == avant
        return {"E2-3": avant}

    releve, _ecrit, _boite = banc_ecriture().monter_le_jugement(
        tmp_path, banc, scenario, ascii_seul=ascii_seul)
    return releve


def banc_ecriture():
    """Le banc voisin de l'ecriture, importe **paresseusement**.

    Son import de premier niveau monte des projets reels et coute cher ; il
    n'est fait que par les tests qui en ont besoin.
    """
    import test_atelier_extraction_ecriture as module
    return module


def _ligne_du_resultat(tmp_path, banc, ascii_seul: bool) -> str:
    """`E2-5`, ouvert par `ouvrir_le_resultat` -- deux lots DISTINGUABLES."""
    module = banc_ecriture()
    rapport = module.rapport_temoin(tmp_path)
    boite = {}

    async def scenario(pilote):
        pilote.app.descendre()
        await pilote.pause()
        boite["ecran"] = ecriture.ouvrir_le_resultat(pilote.app, rapport)
        await pilote.pause()
        return etat_brut(boite["ecran"])

    application = module.coque()
    application.ascii_seul = ascii_seul
    return banc(application, scenario)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_d_etat_des_ecrans_d_extraction_ne_porte_un_NOM_DE_TOUCHE(
        tmp_path, banc, ascii_seul):
    """AC 8.4, volet ECRAN -- `EPIC11-ARB-56`, verbatim : la ligne d'etat « ne
    porte **aucune touche** [...] **aucun conseil d'usage** [...] **aucun motif
    de conception** ».

    **C'est ce test qui a trouve l'ecart**, et il n'aurait pas ete trouve par
    le volet maquette : `E2-3b` portait la mesure sur sa maquette et le conseil
    dans son code.
    """
    vues = lignes_d_etat_reelles(tmp_path, banc, ascii_seul)
    assert len(vues) == 10, sorted(vues)
    fautives = {nom: (ligne, ecarts_de_sobriete(ligne))
                for nom, ligne in vues.items() if ecarts_de_sobriete(ligne)}
    assert fautives == {}, fautives


# **`test_la_ligne_d_etat_de_E2_3b_est_la_MESURE_de_sa_MAQUETTE` est RETIRE**
# (`EPIC11-ARB-141`, story 11.4e lot G). Il confrontait la ligne d'etat de
# l'ecran EN MODE EDITION a celle de la maquette `E2-3b`. Le mode n'existe plus
# sur cet ecran : la ligne qu'il mesurait n'est plus atteignable, et un test qui
# ne peut plus atteindre son sujet ne mesure rien. La maquette `E2-3b`, elle,
# reste sur le disque -- elle decrit le mode de l'ecran PARTAGE de
# `execution.py`, que ce lot n'a pas le droit de toucher --, et
# `test_aucun_nom_editable.py` la tient dans un ensemble EXACT qui rougira le
# jour ou elle partira.


def _sans_les_chiffres(texte: str) -> str:
    return re.sub(r"\d+", "#", texte)


#: **L'inventaire ferme des phrases NON CHIFFREES** des lignes d'etat de
#: l'atelier (`EPIC11-ARB-30`, promu en AC : « toute phrase d'interface qui
#: porte un jugement metier doit pouvoir etre rattachee a une fonction du coeur
#: ou a une decision numerotee. Une phrase orpheline est un defaut, meme si elle
#: est vraie. »).
#:
#: C'est la mesure qui tient lieu de « aucun motif de conception » : aucun test
#: generique ne distingue un constat d'un jugement, mais un inventaire ferme
#: rougit des qu'une phrase nouvelle apparait sans rattachement.
PHRASES_ADOSSEES = {
    modele_des_noms.MOTIF_VIDE: "EPIC11-ARB-25 (le message NOMME le motif)",
    modele_des_noms.MOTIF_CARACTERES: "EPIC11-ARB-25 (idem)",
    # `motif_de_longueur` n'est PAS ici, et c'est voulu : depuis le lot I il
    # porte sa mesure (`50 caracteres pour 48 admis`), donc il tombe dans la
    # branche « une ligne chiffree est une mesure et n'a rien a justifier ».
    # Il ne vit d'ailleurs plus en ligne d'etat mais dans le CORPS de `E2-3c`.
    execution.PHRASE_ACTION_INACCESSIBLE: "maquette E2-3c (mesure du refus)",
    execution.AUCUNE_ISSUE: "EPIC11-ARB-7 / -45",
    execution.RIEN_ECRIT: "story 11.1, AC 1.3 (rien n'a encore ete ecrit)",
    atelier_extraction.PHRASE_AUCUNE_LECTURE: "EPIC11-ARB-41",
    atelier_extraction.PHRASE_CADENCE_NON_CORROBOREE: "EPIC11-ARB-76",
    # `execution.PHRASE_NOM_VALIDE` a quitte cet inventaire avec le mode
    # d'edition (`EPIC11-ARB-141`) : aucune ligne d'etat de cet atelier ne
    # la porte plus, et une entree qui ne peut plus etre atteinte protege
    # une phrase que rien ne rend.
    rushes.MANIFESTE_INCHANGE: "AC 4.5 (rien n'est ecrit avant validation)",
}


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_phrases_NON_CHIFFREES_des_lignes_d_etat_sont_dans_l_INVENTAIRE(
        tmp_path, banc, ascii_seul):
    """`EPIC11-ARB-30` : une phrase orpheline est un defaut, meme si elle est
    vraie.

    Une ligne d'etat qui porte un chiffre est une **mesure** et n'a rien a
    justifier. Une ligne d'etat sans aucun chiffre affirme quelque chose : elle
    doit se rattacher a une constante nommee de l'inventaire.
    """
    inventaire = {jetons.replier_ascii(phrase) if ascii_seul else phrase
                  for phrase in PHRASES_ADOSSEES}
    orphelines = []
    for nom, ligne in lignes_d_etat_reelles(tmp_path, banc, ascii_seul).items():
        # **Le repli s'applique aux DEUX cotes**, comme sur la mesure de
        # `E2-3b`. `etat_brut` rend la ligne AVANT dessin, donc accentuee ; ne
        # replier que l'inventaire comparait un accent a son repli. Le defaut
        # ne se voyait pas tant que les phrases du produit etaient ecrites sans
        # accents -- c'est-a-dire tant que le finding `I6` durait.
        if ascii_seul:
            ligne = jetons.replier_ascii(ligne)
        if any(caractere.isdigit() for caractere in ligne):
            continue
        if not any(phrase and phrase in ligne for phrase in inventaire):
            orphelines.append((nom, ligne))
    assert orphelines == [], orphelines


def test_l_inventaire_des_phrases_est_NON_VIDE_et_lu_des_MODULES():
    """Volet symetrique : un inventaire vide rendrait le test precedent muet."""
    assert len(PHRASES_ADOSSEES) >= 6, PHRASES_ADOSSEES
    assert all(isinstance(phrase, str) and phrase
               for phrase in PHRASES_ADOSSEES), PHRASES_ADOSSEES


# ===========================================================================
# AC 8.1 -- la grille 80x24, en UTF-8 ET en repli ASCII, mesuree en COLONNES
# ===========================================================================

def test_les_maquettes_d_extraction_tiennent_la_grille_80x24():
    """AC 8.1, volet maquette : 24 lignes de 80 colonnes, notes exclues."""
    for nom, chemin in sorted(maquettes_de_l_atelier().items()):
        lignes = lignes_de_maquette(chemin)
        assert len(lignes) == jetons.HAUTEUR_PLANCHER, (nom, len(lignes))
        for rang, ligne in enumerate(lignes, 1):
            assert jetons.colonnes(ligne) == jetons.LARGEUR_PLANCHER, (
                nom, rang, jetons.colonnes(ligne))


def test_les_maquettes_d_extraction_tiennent_la_grille_EN_REPLI_ASCII():
    """AC 8.1, et **c'est le piege central du lot G** : un repli ASCII peut
    ALLONGER une ligne.

    `⏎` rend `Entree`, `…` rend `...`, `—` rend `--` : une ligne calee juste en
    UTF-8 deborde une fois repliee. Mesure du 2026-08-29 sur la ligne de
    raccourcis de `E2-2` : 75 colonnes en UTF-8, **80** repliee, pour une zone
    de 76. La mesure porte donc ici sur **toutes** les lignes de contenu, et
    pas sur la seule ligne de raccourcis que le verificateur regarde.
    """
    utile = jetons.largeur_utile()
    debordements = []
    for nom, chemin in sorted(maquettes_de_l_atelier().items()):
        for rang, ligne in enumerate(lignes_de_maquette(chemin), 1):
            if not ligne.startswith("│"):
                continue
            replie = jetons.replier_ascii(contenu_de_la_ligne(ligne))
            if jetons.colonnes(replie) > utile:
                debordements.append((nom, rang, jetons.colonnes(replie),
                                     replie))
    assert debordements == [], debordements


def test_le_repli_ASCII_ALLONGE_bien_au_moins_une_ligne_des_maquettes():
    """Volet symetrique du test precedent : sans allongement, il ne mesure rien.

    Une mesure de repli sur un corpus qui ne se replierait pas serait verte en
    permanence, et c'est exactement ce que le verificateur de maquettes faisait
    avant le 2026-08-29.
    """
    allongees = [
        (nom, ligne)
        for nom, chemin in maquettes_de_l_atelier().items()
        for ligne in map(contenu_de_la_ligne, lignes_de_maquette(chemin))
        if jetons.colonnes(jetons.replier_ascii(ligne)) > jetons.colonnes(ligne)
    ]
    assert allongees, "aucune ligne ne s'allonge : le corpus ne mesure rien"


#: Trois noms de projet **distinguables**, de largeurs croissantes, dont deux en
#: DOUBLE CHASSE : `len()` et `colonnes()` y disent des choses differentes, et
#: c'est la seule facon de demasquer une mesure faite en caracteres. Le premier
#: est latin et long, les deux autres portent des ideogrammes.
NOMS_LONGS_ET_DOUBLE_CHASSE = (
    "projet_demo_planche_4f_heteroclite_tres_long_nom_de_tournage",
    "撮影_" + "夕日" * 8,
    "夕日" * 24,
)


def test_les_noms_du_banc_SEPARENT_bien_colonnes_et_caracteres():
    """Volet symetrique : sans double chasse, la mesure en colonnes ne mesure
    rien de plus que `len()`."""
    assert any(jetons.colonnes(nom) > len(nom)
               for nom in NOMS_LONGS_ET_DOUBLE_CHASSE), \
        NOMS_LONGS_ET_DOUBLE_CHASSE


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("projet", NOMS_LONGS_ET_DOUBLE_CHASSE)
def test_les_ecrans_d_extraction_tiennent_la_grille_80x24(
        tmp_path, banc, ascii_seul, projet):
    """AC 8.1, volet ECRAN : les douze lignes d'etat tiennent la zone utile,
    dans les deux regimes, sous un contexte de projet long et en double chasse.

    `EPIC11-ARB-21`, verbatim : « Au-dela de 80 colonnes, la place gagnee
    **allonge les lignes** ; elle n'ajoute **jamais** une seconde colonne. » La
    mesure se fait donc au **plancher**, la ou tout doit deja tenir.

    La ligne d'etat est mesuree **brute puis repliee** : replier apres avoir
    mesure ferait deborder de deux colonnes une ligne calee juste.
    """
    utile = jetons.largeur_utile()
    vues = lignes_d_etat_reelles(tmp_path, banc, ascii_seul)
    trop_larges = {}
    for nom, ligne in vues.items():
        replie = jetons.replier_ascii(ligne) if ascii_seul else ligne
        if jetons.colonnes(replie) > utile:
            trop_larges[nom] = (jetons.colonnes(replie), replie)
    assert trop_larges == {}, (projet, trop_larges)
    # Le bandeau porte le nom du projet : c'est LUI que la double chasse met en
    # defaut, et il cede sur le projet, jamais sur l'objet travaille.
    bandeau = Contexte(projet, "Extraction", "rush_hiver").rendu(
        jetons.LARGEUR_PLANCHER, ascii_seul)
    assert jetons.colonnes(bandeau) == utile, (projet, jetons.colonnes(bandeau))
    assert bandeau.endswith("rush_hiver"), bandeau


def test_les_ecrans_d_extraction_n_ouvrent_AUCUNE_seconde_colonne():
    """`EPIC11-ARB-21`, frontiere negative : « elle n'ajoute **jamais** une
    seconde colonne ».

    Elle se mesure sur le CODE : aucun des deux modules d'atelier n'importe le
    conteneur horizontal de `textual`. Un grep de texte confondrait une prose
    d'explication avec un import ; l'arbre syntaxique, non.
    """
    from outils_frontiere import identifiants

    paquet = Path(_SRC) / "mixed_media_utility" / "tui"
    for module in ("atelier_extraction.py", "atelier_extraction_ecriture.py"):
        noms = identifiants(paquet / module)
        assert "Horizontal" not in noms, module
        assert "Grid" not in noms, module


# ===========================================================================
# AC 8.2 -- aucun glyphe hors de la table fermee
# ===========================================================================

def alphabet_autorise(ascii_seul: bool) -> set[str]:
    """Ce qu'un ecran peut porter en dehors de l'ASCII imprimable.

    Trois sources, **toutes lues de `jetons`** : la table de glyphes du mode,
    les symboles de texte que le repli connait, et l'ellipse d'abregement. Rien
    d'autre : un glyphe hors de la table peut manquer dans une police de
    console, et c'est tout l'objet de `DESIGN.md` section 6.
    """
    autorises = set(jetons.glyphes(ascii_seul).values())
    autorises |= set(jetons.REPLIS_DE_TEXTE)
    autorises |= set(jetons.REPLIS_DE_TEXTE.values())
    autorises.add(jetons.ELLIPSE)
    # Les valeurs de la table peuvent porter plusieurs caracteres (`└─`) : on
    # mesure caractere par caractere, donc on les eclate.
    return {caractere for valeur in autorises for caractere in valeur}


def glyphes_hors_table(texte: str, ascii_seul: bool) -> set[str]:
    """Les caracteres non ASCII qu'aucune table ne couvre.

    Les lettres accentuees ne sont **pas** des glyphes : ce sont des lettres, et
    le francais en porte. Elles disparaissent du repli par decomposition, pas
    par la table -- les compter ici confondrait l'orthographe et la charte.
    """
    autorises = alphabet_autorise(ascii_seul)
    hors = set()
    for caractere in texte:
        if caractere.isascii() or caractere in autorises:
            continue
        if unicodedata.category(caractere).startswith("L"):
            continue          # une lettre, accentuee ou non
        hors.add(caractere)
    return hors


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucun_glyphe_HORS_TABLE_dans_les_lignes_d_etat_de_l_atelier(
        tmp_path, banc, ascii_seul):
    """AC 8.2 : « Aucun glyphe hors de la table fermee »."""
    fautifs = {}
    for nom, ligne in lignes_d_etat_reelles(tmp_path, banc, ascii_seul).items():
        rendue = jetons.replier_ascii(ligne) if ascii_seul else ligne
        hors = glyphes_hors_table(rendue, ascii_seul)
        if hors:
            fautifs[nom] = (sorted(hors), rendue)
    assert fautifs == {}, fautifs


def test_en_repli_ASCII_une_ligne_d_etat_est_de_l_ASCII_PUR(tmp_path, banc):
    """Le volet dur du meme AC : `--ascii` ne laisse passer aucun non-ASCII.

    Une table complete ne prouve pas un repli complet : c'est ce qui a laisse
    passer `1920×1080` -> `1920?1080` jusqu'au 2026-08-29.
    """
    restes = {}
    for nom, ligne in lignes_d_etat_reelles(tmp_path, banc, True).items():
        replie = jetons.replier_ascii(ligne)
        if not replie.isascii() or "?" in replie:
            restes[nom] = replie
    assert restes == {}, restes


def corps_des_ecrans(tmp_path, ascii_seul: bool) -> dict[str, list[str]]:
    """Les lignes de CORPS des ecrans que l'on peut composer sans clavier.

    Quatre ecrans, quatre mises en page differentes : une liste de rushes, deux
    listes cochables, un rapport de previz. Ce sont les zones qui portent le
    plus de glyphes -- les cases, les etats, les verdicts --, et donc celles ou
    un glyphe hors table passerait inapercu.
    """
    liste = banc_rushes.ecran_de(tmp_path).liste
    # La largeur PLEINE : `rendu` retire lui-meme cadre et marges
    # (`I7` -- la double deduction abregeait la duree).
    corps = {"E2-1": liste.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)}
    for nom, fabrique in (("E2-2", banc_cadences.ecran_de_cadences),
                          ("E2-2b", banc_cadences.ecran_de_previz),
                          ("E2-2c", banc_cadences.ecran_de_choix)):
        corps[nom] = fabrique().composer(jetons.LARGEUR_PLANCHER, ascii_seul)[0]
    return corps


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucun_glyphe_HORS_TABLE_dans_le_CORPS_des_ecrans_d_extraction(
        tmp_path, ascii_seul):
    """AC 8.2, sur les zones CENTRALES et pas seulement sur la ligne d'etat.

    Le corps est ce qui porte les cases a cocher, les etats et les verdicts :
    c'est la que la table fermee sert vraiment, et c'est la qu'un glyphe
    emprunte ailleurs se glisserait.
    """
    fautifs = {}
    for nom, lignes in corps_des_ecrans(tmp_path, ascii_seul).items():
        for rang, ligne in enumerate(lignes):
            hors = glyphes_hors_table(ligne, ascii_seul)
            if hors:
                fautifs[(nom, rang)] = (sorted(hors), ligne)
    assert fautifs == {}, fautifs


@pytest.mark.parametrize("texte,attendu", [
    ("── Bornes ──────", "-- Bornes ------"),
    ("── Lots à produire ──", "-- Lots a produire --"),
    # Le rattachement porte le MEME caractere et se replie AVANT lui : la table
    # des glyphes passe en premier, `└─` sort donc en `\\_` et pas en `\\-`.
    ("  └─ lot_a", "  \\_ lot_a"),
])
def test_le_FILET_titre_se_replie_en_TIRET_et_pas_en_point_d_interrogation(
        texte, attendu):
    """Le troisieme cas de la famille du signe `×` (correctif du 2026-08-29).

    `─` n'est pas de l'ASCII et la decomposition Unicode ne le connait pas : le
    repli general rendait `?? Bornes ??`. Les deux sites qui composent un filet
    choisissent aujourd'hui leur trait eux-memes, si bien que le defaut ne mord
    pas -- mais un texte porteur d'un filet qui passerait par le repli general
    sortait en points d'interrogation, et c'est une propriete de la TABLE, pas
    de ses appelants.
    """
    assert jetons.replier_ascii(texte) == attendu


def test_le_CORPS_des_ecrans_porte_bien_des_GLYPHES_de_la_table(tmp_path):
    """Volet symetrique : une mesure de glyphes sur un corps sans glyphe serait
    verte sans rien mesurer."""
    table = set(jetons.GLYPHES.values())
    vus = {caractere
           for lignes in corps_des_ecrans(tmp_path, False).values()
           for ligne in lignes for caractere in ligne if caractere in table}
    assert len(vus) >= 3, sorted(vus)


def test_aucune_couleur_LITTERALE_dans_les_deux_modules_de_l_atelier():
    """AC 8.2, second volet : « aucune couleur litterale hors de `jetons` ».

    La mesure generale existe deja sur tout le paquet
    (`test_jetons_tui.test_aucune_couleur_litterale_dans_le_paquet_tui`) ; celle
    -ci la porte **nommement sur les deux modules de l'atelier**, pour que la
    frontiere de l'AC 8 soit lisible la ou l'AC la pose.
    """
    from outils_frontiere import chaines_de_code

    paquet = Path(_SRC) / "mixed_media_utility" / "tui"
    motif = re.compile(r"#[0-9a-fA-F]{3,8}$")
    for module in ("atelier_extraction.py", "atelier_extraction_ecriture.py"):
        for chaine in chaines_de_code(paquet / module):
            assert not motif.match(chaine.strip()), (module, chaine)


# ===========================================================================
# AC 8.3 -- chaque etat, mesure DES DEUX COTES
# ===========================================================================

#: Un corps de liste a **quatre** lignes distinguables, chacune portant un etat
#: different, et la cible jamais en premiere position. Un remplissage uniforme
#: rendrait invisible toute permutation (`CLAUDE.md`, regle des fabriques).
def corps_a_quatre_etats(ascii_seul: bool) -> tuple[list[str], dict[int, str]]:
    table = jetons.glyphes(ascii_seul)
    lignes = [
        f"  rush_01     25 fps   {jetons.marque('complete', 'lie', ascii_seul)}",
        f"  rush_02     50 fps   {jetons.marque('substitute', 'a verifier', ascii_seul)}",
        f"  rush_hiver  24 fps   {jetons.marque('absent', 'absent', ascii_seul)}",
        f"{table['curseur']} rush_ete    30 fps   "
        f"{jetons.marque('complete', 'lie', ascii_seul)}",
    ]
    return lignes, {0: "complete", 1: "substitute", 2: "absent"}


@pytest.mark.parametrize("ascii_seul", MODES)
def test_chaque_etat_est_COLORE_en_regime_nominal(ascii_seul):
    """AC 8.3, premier cote : **colore en regime nominal**.

    Les trois etats sont poses sur trois lignes DIFFERENTES, et le rang du
    curseur vaut 3 -- jamais 0 : un `peindre` qui surlignerait toujours la
    premiere ligne masquerait l'etat de cette ligne-la et passerait.
    """
    lignes, etats = corps_a_quatre_etats(ascii_seul)
    peint = jetons.peindre(lignes, ascii_seul=ascii_seul,
                           ligne_du_curseur=3, etats=etats)
    styles = [str(ligne.spans[0].style) if ligne.spans else ""
              for ligne in peint.split("\n")]
    for rang, nom in etats.items():
        assert jetons.couleur(f"state-{nom}") in styles[rang], (rang, styles)
    # Les trois teintes sont DISTINCTES : une table qui rendrait la meme
    # couleur partout passerait les trois assertions ci-dessus.
    assert len({styles[rang] for rang in etats}) == 3, styles
    # Et la ligne du curseur, elle, porte l'accentuation -- pas son etat.
    assert jetons.couleur("accent") in styles[3], styles


@pytest.mark.parametrize("ascii_seul", MODES)
def test_chaque_etat_reste_LISIBLE_SANS_couleur(ascii_seul):
    """AC 8.3, second cote -- `EPIC11-ARB-43`, verbatim : « la couleur ne porte
    **jamais seule** une information ».

    Sans couleur, les trois etats restent **distinguables** parce que leurs
    glyphes different, et le texte est **identique** a celui du regime nominal :
    le repli ne change pas ce qui est lisible, seulement ce qui est teinte.
    """
    lignes, etats = corps_a_quatre_etats(ascii_seul)
    nominal = jetons.peindre(lignes, ascii_seul=ascii_seul,
                             ligne_du_curseur=3, etats=etats)
    sans = jetons.peindre(lignes, ascii_seul=ascii_seul, sans_couleur=True,
                          ligne_du_curseur=3, etats=etats)
    assert jetons.texte_affiche(sans) == jetons.texte_affiche(nominal)
    assert all(not ligne.spans for ligne in sans.split("\n")), "aucun style"
    # Le second canal tient tout seul : les trois glyphes sont distincts.
    glyphes = [jetons.glyphes(ascii_seul)[nom] for nom in etats.values()]
    assert len(set(glyphes)) == 3, glyphes
    for rang, glyphe in zip(etats, glyphes):
        assert glyphe in jetons.texte_affiche(sans).split("\n")[rang]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_etats_des_cadences_sont_COLORES_en_nominal_ET_lisibles_SANS_couleur(
        banc, ascii_seul):
    """AC 8.3 sur un ecran REEL, et pas sur une fixture de laboratoire.

    `E2-2` porte une cadence refusee par le coeur : elle est en `state-absent`,
    non cochable, et elle doit se lire sans couleur comme avec. La cadence
    refusee n'est **pas** la premiere de la liste.
    """
    ecran = banc_cadences.ecran_de_cadences()
    ecran.liste.curseur = 2                 # la cible n'est PAS la premiere
    lignes, rang, etats = ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)
    # Le rang rendu est celui de la ligne DANS L'ECRAN, pas celui du modele :
    # l'ecran pose un titre et un filet avant sa liste. Ce qui doit tenir, et
    # que la comparaison a `0` ne dirait pas, c'est qu'il SUIT le modele.
    assert rang is not None and rang > 0, rang
    ecran.liste.curseur = 3
    assert ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)[1] == rang + 1
    ecran.liste.curseur = 2
    nominal = jetons.peindre(lignes, ascii_seul=ascii_seul,
                             ligne_du_curseur=rang, etats=etats)
    sans = jetons.peindre(lignes, ascii_seul=ascii_seul, sans_couleur=True,
                          ligne_du_curseur=rang, etats=etats)
    assert jetons.texte_affiche(sans) == jetons.texte_affiche(nominal)
    assert any(ligne.spans for ligne in nominal.split("\n")), (
        "aucune ligne teintee en regime nominal")
    assert all(not ligne.spans for ligne in sans.split("\n"))


# ===========================================================================
# AC 8.5 -- le rang du curseur est PASSE, jamais devine
# ===========================================================================

class PeintureEspionnee:
    """Un espion de `jetons.peindre` qui garde CE QUE L'ECRAN A PASSE.

    Il delegue au vrai : mesurer l'appel sans peindre changerait le rendu, donc
    mesurerait autre chose que le produit.
    """

    def __init__(self) -> None:
        self.appels: list[dict] = []
        self._vrai = jetons.peindre

    def __call__(self, lignes, **kwargs):
        lignes = list(lignes)
        self.appels.append({"lignes": lignes, **kwargs})
        return self._vrai(lignes, **kwargs)

    @property
    def rangs(self) -> list[object]:
        return [appel.get("ligne_du_curseur") for appel in self.appels]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_RANG_DU_CURSEUR_est_PASSE_a_peindre_par_les_ecrans_a_curseur(
        tmp_path, banc, monkeypatch, ascii_seul):
    """AC 8.5 : « Le rang de la ligne surlignee est **passe explicitement** ».

    **Pourquoi ce n'est pas une coquetterie.** L'auto-detection de `peindre`
    teste `startswith` sur le glyphe de curseur. Elle ne trouve rien sur une
    ligne indentee -- et elle ne leve pas : elle cesse simplement de surligner,
    en silence. C'est un des trois defauts trouves au developpement de la story
    11.2.

    La mesure porte sur les quatre ecrans a curseur de l'atelier, montes pour
    de vrai, et le rang releve n'est **jamais 0** sur au moins l'un d'eux : un
    ecran qui passerait `0` en dur satisferait un test moins exigeant.
    """
    espion = PeintureEspionnee()
    monkeypatch.setattr(jetons, "peindre", espion)
    monkeypatch.setattr(atelier_extraction.jetons, "peindre", espion)
    monkeypatch.setattr(execution.jetons, "peindre", espion)

    ecran = banc_rushes.ecran_de(tmp_path)
    ecran.liste.viser("rush_hiver")        # le TROISIEME rush, jamais le premier

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.rafraichir()
        await pilote.pause()

    application = coque_de(ecran)
    application.ascii_seul = ascii_seul
    banc(application, scenario)

    assert espion.appels, "aucun appel a peindre : la mesure ne mesure rien"
    rangs = [rang for rang in espion.rangs if rang is not None]
    assert rangs, f"aucun rang passe explicitement : {espion.rangs}"
    # **Le rang est celui de la ligne DANS L'ECRAN, pas dans le modele.**
    # Depuis le lot I, `E2-1` pose sa question au-dessus de la liste (`I2`) :
    # le troisieme rush n'est donc plus la troisieme ligne, et le rang attendu
    # se LIT de la composition plutot que d'etre recopie. Le comparer a 2
    # mesurerait la mise en page, ce que le test jumeau ci-dessous ne fait
    # deja plus.
    lignes, attendu, _etats = ecran.composer(jetons.LARGEUR_PLANCHER,
                                             ascii_seul)
    assert attendu not in (None, 0), (attendu, lignes)
    assert "rush_hiver" in lignes[attendu], (attendu, lignes)
    assert attendu in rangs, (
        "le rang passe doit etre celui de la LIGNE du rush vise, pas 0 : "
        f"{espion.rangs}")


def _deplacer_le_curseur(ecran, rang: int) -> None:
    """Poser le curseur du MODELE de l'ecran, quel que soit le modele."""
    if hasattr(ecran, "liste"):
        ecran.liste.curseur = rang
    else:
        ecran.choix.curseur = rang


@pytest.mark.parametrize("ecran_nomme", ["E2-2", "E2-2c", "E2-3", "E2-1d"])
def test_chaque_ecran_a_curseur_PASSE_un_rang_qui_SUIT_son_modele(
        tmp_path, banc, monkeypatch, ecran_nomme):
    """Le meme AC, ecran par ecran, et la mesure est un **ecart**, pas une
    egalite.

    Le rang passe est celui de la ligne DANS L'ECRAN : un titre, un filet ou
    un cartouche le decalent, si bien que le comparer au curseur du modele ne
    mesurerait que la mise en page. Ce qui doit tenir est qu'il **suit** le
    modele -- deplacer le curseur d'un cran deplace le rang d'un cran.

    C'est aussi ce qui distingue « le rang est passe » de « le rang est
    devine » : l'auto-detection de `peindre` teste `startswith` et rendrait
    `None` ou un rang qui ne bouge pas, sur les ecrans dont les lignes sont
    indentees.

    **La cible n'est jamais en premiere position** : les deux rangs mesures
    sont 1 et 2, jamais 0 (regle des fabriques).
    """
    espion = PeintureEspionnee()
    monkeypatch.setattr(jetons, "peindre", espion)
    monkeypatch.setattr(atelier_extraction.jetons, "peindre", espion)
    monkeypatch.setattr(execution.jetons, "peindre", espion)

    releves: list[int | None] = []

    if ecran_nomme == "E2-3":
        async def scenario(pilote, ecran):
            for rang in (1, 2):
                _deplacer_le_curseur(ecran, rang)
                espion.appels.clear()
                ecran.rafraichir()
                releves.append(_rang_du_bloc_a_curseur(espion, rang, ecran))

        banc_ecriture().monter_le_jugement(tmp_path, banc, scenario)
    else:
        ecran = {
            "E2-2": banc_cadences.ecran_de_cadences,
            "E2-2c": banc_cadences.ecran_de_choix,
            "E2-1d": lambda: atelier_extraction.EcranRefusRelink(
                banc_rushes.refus_long()),
        }[ecran_nomme]()

        async def scenario(pilote):
            pilote.app.descendre(ecran)
            await pilote.pause()
            for rang in (1, 2):
                _deplacer_le_curseur(ecran, rang)
                espion.appels.clear()
                ecran.rafraichir()
                await pilote.pause()
                releves.append(_rang_du_bloc_a_curseur(espion, rang, ecran))

        banc(coque_de(ecran), scenario)

    assert all(rang is not None for rang in releves), (ecran_nomme, releves)
    assert releves[1] == releves[0] + 1, (ecran_nomme, releves)


def _rang_du_bloc_a_curseur(espion, curseur_du_modele, ecran):
    """Le rang que l'ecran a PASSE pour la zone qui porte le curseur.

    Un ecran peint plusieurs blocs -- un cartouche, puis ses issues -- et un
    seul porte le curseur. On retient le dernier rang non nul passe : les blocs
    sans curseur passent `None`, jamais un rang faux.
    """
    rangs = [rang for rang in espion.rangs if rang is not None]
    return rangs[-1] if rangs else None


# ===========================================================================
# AC 8.1, LOT I -- la grille a DEUX dimensions : les colonnes ET les lignes
#
# **Ce que ce banc ne mesurait pas, et ce que ca a coute.** Tout ce qui precede
# mesure la LARGEUR : les lignes d'etat, les corps composes, les maquettes. Rien
# ne mesurait leur NOMBRE. Or `textual` coupe une zone trop haute **par le bas
# et en silence** : sur `E2-2` sans affichage, le bloc de refus faisait deux
# lignes, la composition dix-huit pour dix-sept dessinees, et la ligne
# `Borne de sortie` disparaissait -- sur l'ecran meme de l'AC 5.2, dans les DEUX
# regimes. Aucun banc ne l'a vu ; une capture d'ecran l'a montre (`I1`).
#
# La hauteur se mesure donc ici sur toutes les compositions de l'atelier, et
# **sur leurs etats variables** : c'est un etat variable -- le refus, le champ
# de saisie -- qui fait deborder, jamais le nominal.
#
# **Ce que ce banc ne couvre pas, et pourquoi on l'ecrit.** Les cinq ecrans de
# `execution.py` (`E2-3`, `E2-3b`, `E2-3c`, `E2-4`, `E2-5`) ne composent pas
# leur corps en une liste de lignes : ils montent des widgets, dont un
# cartouche a bordure. Leur hauteur ne se lit donc pas de la meme facon, et
# elle reste hors de cette mesure. Meme honnetete que le docstring de
# `jetons.jeton_d_etat` : on ecrit ce que la forme ne prouve pas.
# ===========================================================================

def compositions_de_l_atelier(tmp_path, ascii_seul: bool) -> dict:
    """Les corps composables de l'atelier, **etats variables compris**.

    La cle nomme l'ecran ET son etat : deux etats d'un meme ecran n'ont pas la
    meme hauteur, et c'est justement le seul qui deborde qu'un corpus par ecran
    aurait manque.
    """
    largeur = jetons.LARGEUR_PLANCHER
    corps: dict[str, list[str]] = {}

    # -- `E2-1`, ses deux etats de liste et sa zone d'explorateur ------------
    ecran = banc_rushes.ecran_de(tmp_path / "rushes")
    ecran.liste.viser("rush_01")
    corps["E2-1 (rush lie)"] = ecran.composer(largeur, ascii_seul)[0]
    ecran.liste.viser("rush_hiver")
    corps["E2-1 (rush absent, bloc r/d)"] = ecran.composer(largeur,
                                                           ascii_seul)[0]
    for cle, touche, mode in (("E2-1b", "r", rushes.MODE_RETROUVER),
                              ("E2-1c", "d", rushes.MODE_DESIGNER)):
        ecran.traiter(touche, touche)
        corps[cle] = ecran.explorateur.lignes(
            largeur, titre=rushes.titre_de_relink("rush_hiver", mode),
            libelle="Dossier", ascii_seul=ascii_seul)
        ecran.traiter("escape")

    # -- `E2-1d` : un cartouche a BORDURE, un blanc, puis les trois issues ---
    # La bordure du cartouche occupe deux lignes de la zone centrale : les
    # compter est la seule facon de comparer cet ecran aux autres.
    refus = banc_rushes.refus_long()
    corps["E2-1d"] = (
        ["┌ Refus ┐"]
        + refus.lignes(largeur, ascii_seul)
        + ["└───────┘", ""]
        + rushes.issues_apres_refus().rendu(ascii_seul=ascii_seul))

    # -- `E2-2` : nominal, sans affichage, en saisie, et les deux a la fois --
    for cle, sans_ecran, saisie in (("E2-2 (nominal)", False, None),
                                    ("E2-2 (sans affichage)", True, None),
                                    ("E2-2 (saisie de cadence)", False, "10"),
                                    ("E2-2 (sans affichage + saisie)", True,
                                     "10")):
        ecran = banc_cadences.ecran_de_cadences(
            verifier_l_affichage=(banc_cadences.refuser_l_affichage
                                  if sans_ecran else (lambda: None)))
        ecran.demarrer()
        ecran.saisie = saisie
        corps[cle] = ecran.composer(largeur, ascii_seul)[0]

    # -- `E2-2b` et `E2-2c` --------------------------------------------------
    corps["E2-2b"] = banc_cadences.ecran_de_previz().composer(largeur,
                                                              ascii_seul)[0]
    corps["E2-2c"] = banc_cadences.ecran_de_choix().composer(largeur,
                                                             ascii_seul)[0]
    return corps


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_compositions_de_l_atelier_tiennent_les_24_LIGNES_de_la_grille(
        tmp_path, ascii_seul):
    """AC 8.1, la dimension que le lot G ne mesurait pas.

    La hauteur admise est **derivee** de la grille par
    `jetons.HAUTEUR_CENTRE_AU_PLANCHER` -- bordure, filets, bandeau, etat et
    raccourcis deduits --, jamais ecrite en dur : dix-sept pose ici serait une
    seconde source de verite, qui divergerait a la premiere retouche du cadre.
    """
    plafond = jetons.HAUTEUR_CENTRE_AU_PLANCHER
    trop_hautes = {cle: len(lignes)
                   for cle, lignes in compositions_de_l_atelier(
                       tmp_path, ascii_seul).items()
                   if len(lignes) > plafond}
    assert trop_hautes == {}, (plafond, trop_hautes)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_compositions_de_l_atelier_tiennent_aussi_les_80_COLONNES(
        tmp_path, ascii_seul):
    """L'autre dimension, sur le MEME corpus.

    Elle etait deja mesuree, mais sur quatre corps seulement et sans leurs
    etats variables : le bloc de refus d'affichage et le champ de saisie n'y
    passaient pas.
    """
    utile = jetons.largeur_utile()
    trop_larges = {}
    for cle, lignes in compositions_de_l_atelier(tmp_path, ascii_seul).items():
        for rang, ligne in enumerate(lignes):
            if jetons.colonnes(ligne) > utile:
                trop_larges[(cle, rang)] = (jetons.colonnes(ligne), ligne)
    assert trop_larges == {}, trop_larges


def test_le_corpus_de_HAUTEUR_porte_un_ecran_qui_FROLE_le_plafond(tmp_path):
    """Volet symetrique : un corpus de petits ecrans ne mesure rien.

    `E2-2` sans affichage tient la grille **a une ligne pres** : c'est lui qui
    donne sa valeur a la mesure, et un corpus qui cesserait de le porter
    laisserait le test precedent vert en permanence -- exactement ce qu'etait
    le verificateur de maquettes avant le 2026-08-29.
    """
    hauteurs = {cle: len(lignes) for cle, lignes
                in compositions_de_l_atelier(tmp_path, False).items()}
    assert max(hauteurs.values()) == jetons.HAUTEUR_CENTRE_AU_PLANCHER, hauteurs
    assert len(hauteurs) >= 9, hauteurs


@pytest.mark.parametrize("ascii_seul", MODES)
def test_E2_2_SANS_AFFICHAGE_garde_sa_BORNE_DE_SORTIE(ascii_seul):
    """`I1`, l'instance exacte, dans les deux regimes.

    C'est l'ecran de l'AC 5.2. Le bloc de refus s'ajoute, et **aucune ligne de
    texte ne part** : la ligne `Borne de sortie` est la, le refus est la, et
    les deux tiennent sous le plafond. Ce sont les respirations qui cedent.
    """
    ecran = banc_cadences.ecran_de_cadences(
        verifier_l_affichage=banc_cadences.refuser_l_affichage)
    ecran.demarrer()
    lignes, _rang, etats = ecran.composer(jetons.LARGEUR_PLANCHER, ascii_seul)
    rendu = "\n".join(lignes)

    borne = atelier_extraction.LIBELLE_BORNE_DE_SORTIE
    if ascii_seul:
        borne = jetons.replier_ascii(borne)
    assert borne in rendu, (borne, rendu)
    assert atelier_extraction.MENTION_FACULTATIF in rendu, rendu
    assert ecran.refus_d_affichage and ecran.refus_d_affichage.split(":")[0] \
        in rendu, rendu
    assert len(lignes) <= jetons.HAUTEUR_CENTRE_AU_PLANCHER, len(lignes)
    # Les etats du refus suivent le texte : une respiration retiree au-dessus
    # les decalerait toutes, et le bloc serait rouge une ligne trop haut.
    for rang, nom in etats.items():
        if nom == "absent":
            assert jetons.glyphes(ascii_seul)["absent"] in lignes[rang] \
                or lignes[rang].strip(), (rang, lignes[rang])


def test_une_COMPOSITION_sacrifie_ses_respirations_AVANT_toute_ligne_de_texte():
    """Le mecanisme, mesure a nu -- et sa frontiere.

    Trois lignes de texte distinguables et deux respirations, la cible du
    curseur **au milieu** : c'est la seule disposition qui demasque a la fois
    un retrait qui prendrait la premiere ligne et un rang de curseur laisse a
    son index d'origine.
    """
    composition = atelier_extraction.Composition()
    composition.respirer()
    composition.bloc(["haut", "milieu", "bas"],
                     etats={1: "absent"}, curseur=1)
    composition.respirer()
    composition.poser("pied")

    entiere, rang, etats = composition.rendu(6)
    assert entiere == ["", "haut", "milieu", "bas", "", "pied"]
    assert rang == 2 and etats == {2: "absent"}

    # Une ligne de trop : la respiration de TETE tombe, celle qui ne separe
    # rien -- le filet du bandeau le fait deja --, et tout le texte reste.
    serree, rang, etats = composition.rendu(5)
    assert serree == ["haut", "milieu", "bas", "", "pied"]
    assert rang == 1 and etats == {1: "absent"}

    # Les deux respirations tombees, il ne reste que du texte : rien n'est
    # tronque en silence, la composition rend son debordement pour que le banc
    # le voie.
    nue, rang, etats = composition.rendu(1)
    assert nue == ["haut", "milieu", "bas", "pied"]
    assert rang == 1 and etats == {1: "absent"}


# ===========================================================================
# `EPIC11-ARB-245` -- la HAUTEUR des ecrans a CARTOUCHE d'`execution.py`
#
# **Le corpus precedent les EXCLUAIT nommement**, et le commentaire qui ouvre
# la section ci-dessus le dit : « les cinq ecrans de `execution.py` [...] ne
# composent pas leur corps en une liste de lignes : ils montent des widgets,
# dont un cartouche a bordure. Leur hauteur ne se lit donc pas de la meme
# facon, et elle reste hors de cette mesure. » L'exclusion etait ecrite et
# assumee ; sa CONSEQUENCE ne l'etait pas -- l'ecran d'ecrasement de
# l'Extraction rendait vingt-deux lignes pour dix-sept, et **le debordement
# preexistait** au lot F qui l'a aggrave.
#
# La hauteur se lit donc ici de la facon dont elle se lit deja pour `E2-1d`,
# qui est un cartouche a bordure lui aussi : la bordure compte pour deux
# lignes, le cartouche pour ce qu'il AFFICHE (`lignes_du_cartouche`, et non
# ce qu'il contient), puis le corps du refus s'il est visible, une
# respiration, et les issues -- c'est-a-dire exactement l'ordre que
# `EcranChiffre.contenu` monte.
#
# **Ce que ce corpus ne couvre toujours pas, dit plutot que tu.** `E2-4`
# (execution en cours) et `E2-5` (resultat) ne derivent pas d'`EcranChiffre` :
# ils n'ont ni cartouche ni issues, leur corps se compose autrement, et les
# faire entrer demanderait une seconde forme de mesure. Ils restent hors de
# ce banc ; les deux ecrans a cartouche de l'atelier y entrent, avec les
# QUATRE etats de conflit du second.
# ===========================================================================

def banc_des_versions():
    """Le banc voisin des versions de lot, importe **paresseusement**.

    Ses fabriques sont **reutilisees, jamais recopiees** : elles portent deja
    trois cadences a comptes distinguables, la famille visee au MILIEU du
    manifeste et un lot etranger en TETE comme en QUEUE (regle des fabriques,
    points 1, 2 et 4). Une seconde fabrique ici divergerait de celle-la, et
    c'est elle qui est mesuree par ailleurs.
    """
    import test_versions_de_lot_tui as module
    return module


def lignes_composees_du_cartouche(ecran, ascii_seul: bool) -> list[str]:
    """Ce qu'un `EcranChiffre` monte occupe dans la zone centrale.

    Le meme decompte que `E2-1d` dans le corpus voisin -- deux lignes de
    bordure encadrent le cartouche --, et le meme ORDRE que
    `EcranChiffre.contenu` : le cartouche, le corps du refus quand il est
    visible, une respiration, les issues.

    **`lignes_du_cartouche` et non `lignes_du_panneau`** : c'est l'AFFICHAGE
    qui occupe la grille. Mesurer le contenu ferait rougir un ecran dont le
    pli tient sa promesse, et -- pire -- rendrait vert un pli qui montrerait
    plus de lignes qu'il n'en annonce.
    """
    return (["┌ " + ecran.titre_du_cartouche(ascii_seul) + " ┐"]
            + list(ecran.lignes_du_cartouche())
            + ["└" + "─" * 8 + "┘"]
            + list(ecran.lignes_du_refus())
            + [""]
            + list(ecran.rendu_des_issues()))


def ecrans_a_cartouche_de_l_atelier(tmp_path, banc, ascii_seul: bool) -> dict:
    """Les ecrans a cartouche de l'atelier, **etats variables compris**.

    La cle nomme l'ecran ET son etat, comme dans le corpus voisin : c'est un
    etat variable qui deborde, jamais le nominal. Les quatre etats de conflit
    sont ceux qu'`EPIC11-ARB-245` nomme -- un lot en conflit de DOSSIER, un lot
    en conflit d'ETAT, DEUX lots, et les deux chemins de conflit **ensemble**,
    qui est le cartouche le plus charge que l'atelier sache produire.
    """
    versions = banc_des_versions()
    corps: dict[str, list[str]] = {}

    def dossier_de(cle: str) -> Path:
        # Un dossier par cas : `creer_projet` refuse d'ecraser un projet
        # existant, et les fabriques nomment toutes le leur `projet_demo`.
        chemin = tmp_path / re.sub(r"[^a-z0-9]+", "_", cle.lower())
        chemin.mkdir(parents=True, exist_ok=True)
        return chemin

    def deux_lots_en_conflit_de_dossier(racine):
        """Le lot en conflit est en TETE **et** en QUEUE du plan.

        Les trois lots du plan portent trois cadences distinguables ; peupler
        le premier et le dernier place une cible a **chaque bord**, ce qu'un
        balayage tronque du bloc « Deja sur le disque » ne survivrait pas
        (regle des fabriques, point 4).
        """
        projet = versions.projet(racine)
        provisoire = versions.plan(racine, dossier=projet)
        versions.peupler(provisoire.lots[0])
        versions.peupler(provisoire.lots[-1])
        return versions.plan(racine, dossier=projet)

    def les_deux_chemins_de_conflit(racine):
        """Un lot en conflit de DOSSIER et un AUTRE en conflit d'ETAT.

        Le lot en conflit d'etat est le **dernier** du plan et celui en
        conflit de dossier le **premier** : les deux blocs du cartouche
        s'ouvrent, et chacun porte une cible de bord.
        """
        cibles = [versions.build_lot_id(versions.RUSH, valeur)
                  for valeur, _ in versions.TROIS_CADENCES]
        lots = [versions.entree_de_lot(
                    lot_id, etat="pdf" if rang == len(cibles) - 1
                    else "extraction")
                for rang, lot_id in enumerate(cibles)]
        projet = versions.projet(racine, lots=lots)
        provisoire = versions.plan(racine, dossier=projet)
        versions.peupler(provisoire.lots[0])
        return versions.plan(racine, dossier=projet)

    plans = {
        "E2-3c (un lot, conflit de dossier)":
            lambda r: versions.plan_en_conflit_de_dossier(r),
        "E2-3c (un lot, conflit d'etat)":
            lambda r: versions.plan_en_conflit_d_etat(r),
        "E2-3c (DEUX lots, conflit de dossier)":
            deux_lots_en_conflit_de_dossier,
        "E2-3c (conflit de dossier ET d'etat)": les_deux_chemins_de_conflit,
        # Le point de jugement NOMINAL : sans conflit, aucun lot n'est deja
        # la, et c'est `EcranExtractionConfirmation` qui monte. Il entre au
        # corpus pour la meme raison que `E2-2` nominal y est : un corpus qui
        # ne porterait que l'ecran fautif ne mesurerait que lui.
        "E2-3 (nominal)": lambda r: versions.plan(r),
    }
    for cle, fabrique in plans.items():
        p = fabrique(dossier_de(cle))
        corps[cle] = versions.monter(
            banc, p, ascii_seul=ascii_seul,
            mesure=lambda e: lignes_composees_du_cartouche(e, ascii_seul))[2]
    return corps


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_ecrans_a_CARTOUCHE_tiennent_les_24_LIGNES_de_la_grille(
        tmp_path, banc, ascii_seul):
    """`EPIC11-ARB-245`, la dimension que l'exclusion laissait passer.

    Le plafond est **derive** de `jetons.HAUTEUR_CENTRE_AU_PLANCHER`, jamais
    ecrit : dix-sept pose ici serait une seconde source de verite.
    """
    plafond = jetons.HAUTEUR_CENTRE_AU_PLANCHER
    trop_hauts = {cle: len(lignes)
                  for cle, lignes in ecrans_a_cartouche_de_l_atelier(
                      tmp_path, banc, ascii_seul).items()
                  if len(lignes) > plafond}
    assert trop_hauts == {}, (plafond, trop_hauts)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_ecrans_a_CARTOUCHE_tiennent_aussi_les_80_COLONNES(
        tmp_path, banc, ascii_seul):
    """L'autre dimension, sur le MEME corpus.

    Une ligne de cartouche s'ajuste a `jetons.largeur_de_cartouche`, pas a la
    largeur utile : c'est la borne de la bordure du cartouche qui commande, et
    c'est elle qu'une ligne trop longue traverse.
    """
    utile = jetons.largeur_utile()
    trop_larges = {}
    for cle, lignes in ecrans_a_cartouche_de_l_atelier(
            tmp_path, banc, ascii_seul).items():
        for rang, ligne in enumerate(lignes):
            if jetons.colonnes(ligne) > utile:
                trop_larges[(cle, rang)] = (jetons.colonnes(ligne), ligne)
    assert trop_larges == {}, trop_larges


def test_le_corpus_des_CARTOUCHES_porte_un_ecran_qui_FROLE_le_plafond(
        tmp_path, banc):
    """Volet symetrique : un corpus de petits ecrans ne mesure rien.

    Le cartouche qui defile **remplit** la place que la grille lui laisse --
    c'est le principe du pli, qui montre tout ce qui tient. Le corpus porte
    donc au moins un ecran exactement au plafond, et un corpus qui cesserait
    d'en porter laisserait le test de hauteur vert en permanence.
    """
    hauteurs = {cle: len(lignes) for cle, lignes
                in ecrans_a_cartouche_de_l_atelier(tmp_path, banc,
                                                   False).items()}
    assert max(hauteurs.values()) == jetons.HAUTEUR_CENTRE_AU_PLANCHER, hauteurs
    assert len(hauteurs) >= 5, hauteurs
