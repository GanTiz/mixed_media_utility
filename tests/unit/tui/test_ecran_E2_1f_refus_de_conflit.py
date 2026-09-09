# -*- coding: utf-8 -*-
"""`E2-1f` -- « Un rush identique existe déjà », du modele pur a l'ecran monte.

**Ce que ce banc ferme.** L'ecran de refus de conflit etait dessine
(`EPIC11-ARB-231`, trois sorties), porte par le coeur (`EPIC11-ARB-148` : le
refus expose `source_name`, `rush_id`, `entree` et `criteres`) et par la CLI --
et **absent de la TUI**, qui le remplacait par un ecran « pas encore » nommant
son propre manque. Les deux bancs voisins le disaient chacun de son cote :
`test_maquette_E2_1f_trois_sorties.py` (« elle mesure la MAQUETTE, pas le code
de la TUI ») et `test_ajout_de_rush_tui.py` (un volet qui EXIGEAIT que les
cardinaux divergent). Les deux ont ete corriges a la source ; celui-ci porte ce
qu'aucun des deux ne pouvait porter -- le cartouche, ses quatre criteres, et ce
que les trois issues font vraiment au disque.

**Trois familles de mesures, et elles ne se remplacent pas :**

* **le modele contre la maquette**, ligne a ligne, avec un inventaire FERME des
  ecarts nommes -- meme mecanisme que `test_ecrans_declaration_de_rush.py`, et
  pour le meme motif : un ecart tu est un ecran qui derive, un inventaire qui
  garde ses vieilles entrees cesse de mesurer ;
* **des frontieres NEGATIVES** : aucune valeur du cartouche n'est relue dans le
  manifeste (`EPIC11-ARB-148` tient la comparaison a un seul endroit), le cote
  MESURE ne s'affiche jamais a la place du cote DECLARE, et les **quatre
  autres** motifs de refus ne montent PAS cet ecran. Aucun test positif ne
  verrait ces trois-la ;
* **l'ecran monte**, avec le disque mesure de part et d'autre de chaque issue :
  deux des trois ECRIVENT, et c'est la premiere fois dans cet epic qu'un ecran
  de refus le fait.

**Regle des fabriques (`CLAUDE.md`), les quatre points, sur DEUX collections
imbriquees.**

1. *les quatre criteres du cartouche* -- valeurs toutes **distinguables** et
   d'especes differentes (un nom, un cardinal, une cadence, un timecode) ; le
   test d'omission vise chacun des quatre, donc la TETE (`Nom du fichier`) et
   la QUEUE (`Timecode initial`) autant que le milieu ; et le cote **declare**
   diverge du cote **mesure** sur CHAQUE axe, sans quoi une interversion des
   deux resterait invisible -- c'est le corollaire d'axe, paye cette semaine ;
2. *les trois issues* -- ordre mesure en egalite exacte, cible aux deux bords
   (le relink ouvre, `Annuler` ferme) et au milieu (la sortie neuve). Elle vit
   dans les deux bancs voisins et n'est pas recopiee ici ; ce banc-ci mesure ce
   que chaque issue FAIT.

Une troisieme collection est celle des cinq motifs de refus, ou la frontiere
negative place sa cible aux deux bords de `MOTIFS_DE_REFUS`.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import shutil
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
# Les fabriques des deux bancs voisins sont **reutilisees, jamais recopiees** :
# deux projets de synthese qui divergeraient feraient mesurer deux produits.
sys.path.insert(0, str(Path(__file__).resolve().parent))
# Le banc du RANG d'homonymie porte deja la fabrique d'un projet a 99 rangs
# consommes -- le seul regime reel ou le coeur remplace une de ses issues. La
# reecrire ici ferait deux projets de synthese qui divergeraient.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_ajout_de_rush_tui as voisin  # noqa: E402
import test_ecrans_declaration_de_rush as ecrans  # noqa: E402
import test_rang_de_desambiguisation as rangs  # noqa: E402

from mixed_media_utility.declaration_de_rush import (  # noqa: E402
    ISSUES_PAR_MOTIF,
    MOTIF_RUSH_DEJA_DECLARE,
    MOTIFS_DE_REFUS,
    RefusDeDeclaration,
    ecrire_la_declaration,
    preparer_une_declaration,
)
from mixed_media_utility import relink  # noqa: E402
from mixed_media_utility.extraction import (  # noqa: E402
    CriteresIdentiteRush,
    comparer_identite_rush,
)
from mixed_media_utility.gui.depot_projets import creer_projet  # noqa: E402
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    MANIFEST_FILENAME,
)
from mixed_media_utility.tui import ajout_de_rush, jetons, rushes  # noqa: E402
from mixed_media_utility.tui import atelier_extraction as amont  # noqa: E402
from mixed_media_utility.tui.coque import (  # noqa: E402
    Contexte,
    CoqueTui,
    EcranPasEncore,
    PalierTemoin,
)

MODES = voisin.MODES

MAQUETTE = "E2-1f-declaration-rush-deja-declare.txt"

#: La largeur ECRIVABLE du cartouche tel que la maquette le dessine. Elle est
#: **lue du banc voisin** et non recalculee : le dessin indente le cartouche de
#: deux colonnes de plus que le produit, et cet ecart de geometrie precede ce
#: lot (il vaut deja pour `E2-3`).
LARGEUR_DESSINEE = ecrans.LARGEUR_DU_CARTOUCHE_DESSINE


# ===========================================================================
# Les fabriques : une entree bloquante, une mesure QUI DIVERGE, un refus
# ===========================================================================

#: Les valeurs que `E2-1e` et `E2-1f` DESSINENT, nommees ici une seule fois.
#: Elles etaient tapees en clair sur une douzaine de sites, donc recopiees a la
#: main d'un dessin que ce banc citait -- une docstring dit meme « verbatim de
#: la maquette » -- sans jamais l'ouvrir. Chacune est confrontee a sa source en
#: fin de fichier, le dessin etant relu sur disque a chaque tour.
NOM_DESSINE = "plan séquence 12.mov"
CARDINAL_DESSINE = "6 300 frames"
DUREE_SOURCE_DESSINEE = "6 300 frames · 4:12"
ETAT_DESSINE = "3 issues, 2 écrivent"

#: Le rush deja declare, tel que la maquette le dessine. Les quatre valeurs
#: sont d'especes differentes -- un nom, un cardinal, une cadence, un
#: timecode -- et aucune n'est un remplissage uniforme : une interversion de
#: deux lignes du cartouche se verrait.
ENTREE_BLOQUANTE = {
    "rush_id": "plan-sequence-12",
    "source_name": NOM_DESSINE,
    "fps_source": 25.0,
    "fps_source_exact": "25/1",
    "source_frame_count": 6300,
    "source_frame_count_is_exact": True,
    "source_start_timecode": "00:00:04:12",
    "source_parent": "hd",
    "source_path": ("D:\\HOKO\\Documents\\rushes\\2026\\03_tournage_mai\\hd\\"
                    + NOM_DESSINE),
}

#: Le nom que porte le rush DEJA DECLARE -- le cote DECLARE du partage
#: d'`EPIC11-ARB-153`. **Lu sur l'entree, jamais recopie** : deux redactions du
#: meme nom divergeraient au premier ajustement de la fabrique, et le banc
#: cesserait alors de mesurer sans rougir.
NOM_DECLARE = ENTREE_BLOQUANTE["source_name"]

#: Le nom que l'operateur vient de DESIGNER, et il **DIVERGE** du precedent.
#:
#: C'est la fermeture de `F9` : le bandeau porte le nom DESIGNE et le cartouche
#: le nom DECLARE (`EPIC11-ARB-153`), et tant que la fabrique posait la MEME
#: chaine des deux cotes, un bandeau qui aurait lu l'entree rendait exactement
#: le meme ecran. C'est le point 1 de la regle des fabriques applique a un axe
#: plutot qu'a une collection : deux cotes qui ne divergent sur aucun canal
#: sont un remplissage uniforme.
#:
#: **Le regime est REEL, et il est mesure** par
#: :func:`test_F9_les_deux_noms_de_la_fabrique_rendent_le_MEME_rush_id` : les
#: deux fichiers rendent le meme identifiant, donc le second entre bien en
#: conflit avec le premier. Une divergence inventee -- deux noms qui ne se
#: seraient jamais rencontres sous le meme `rush_id` -- mesurerait un ecran que
#: le produit ne peut pas afficher.
NOM_DESIGNE = "plan sequence 12.MP4"

#: Le dossier que l'operateur vient de DESIGNER -- une AUTRE journee de
#: tournage. C'est ce que la note 4 d'Egan rend visible dans la sortie de
#: relink, et c'est aussi ce que la provenance du cartouche ne doit **jamais**
#: montrer.
DOSSIER_DESIGNE = "D:\\HOKO\\Documents\\rushes\\2026\\04_tournage_juin\\hd\\"
FICHIER_DESIGNE = DOSSIER_DESIGNE + NOM_DESIGNE

#: Le cote MESURE, **different du cote declare sur les TROIS axes comparables**.
#: Il ne peut pas se produire dans le produit -- un refus de conflit veut
#: precisement que les criteres coincident -- et c'est tout son interet ici :
#: un cartouche qui lirait `mesures` au lieu de `declares` afficherait ces
#: valeurs-la, et rien d'autre ne le dirait. Deux jeux identiques rendraient
#: l'interversion invisible, ce qui est le corollaire d'axe de la regle des
#: fabriques.
MESURES_DIVERGENTES = CriteresIdentiteRush(
    source_parent="camera_B",
    fps_source_exact="24000/1001",
    source_frame_count=9999,
    source_start_timecode="10:11:12:13",
)

#: Les quatre lignes du cartouche, et le LIBELLE qui les nomme, dans l'ordre de
#: la maquette. L'inventaire est ferme : il sert de cible aux tests d'omission,
#: donc a la TETE comme a la QUEUE.
LIBELLES_DES_CRITERES = (
    ajout_de_rush.LIBELLE_NOM,
    ajout_de_rush.LIBELLE_DUREE_SOURCE,
    ajout_de_rush.LIBELLE_BASE_DE_TIMECODE,
    ajout_de_rush.LIBELLE_TIMECODE_INITIAL,
)

#: Quelle cle de l'entree porte quel critere. C'est par elle que le test
#: d'omission retire UNE valeur a la fois.
CLE_PAR_LIBELLE = {
    ajout_de_rush.LIBELLE_NOM: "source_name",
    ajout_de_rush.LIBELLE_DUREE_SOURCE: "source_frame_count",
    ajout_de_rush.LIBELLE_BASE_DE_TIMECODE: "fps_source_exact",
    ajout_de_rush.LIBELLE_TIMECODE_INITIAL: "source_start_timecode",
}


def refus_de_conflit(entree: dict | None = None,
                     mesures: CriteresIdentiteRush | None = None,
                     motif: str = MOTIF_RUSH_DEJA_DECLARE,
                     source_name: str = NOM_DESIGNE,
                     rush_id: str | None = "plan-sequence-12",
                     sans_criteres: bool = False,
                     issue_de_remplacement: str | None = None,
                     rang_remplace: int = 1) -> RefusDeDeclaration:
    """Le refus que le coeur leve, fabrique **par les fonctions du coeur**.

    `comparer_identite_rush` et `CriteresIdentiteRush.declares` sont appelees
    plutot que doublees : une preuve fabriquee a la main ne partitionnerait pas
    forcement les criteres comme le produit, et le banc mesurerait alors sa
    propre idee du verdict. L'entree est reposee sur le conflit par le meme
    geste que `_preuve_de_l_identite`, champ pour champ.

    **`issue_de_remplacement` reproduit le seul geste du coeur que la fiche
    doit LIRE** (`EPIC11-ARB-233`, fermeture de `F1`) : quand une issue de la
    table serait FAUSSE, `_refus_de_rush_deja_declare` ne change pas le
    cardinal, il remplace **une entree** de la liste. Le texte pose ici n'est
    pas invente non plus -- :func:`issue_de_remplacement_du_coeur` le fait
    PRODUIRE par le seul producteur du depot.

    `rang_remplace` existe pour les cibles de BORD : le coeur ne remplace que
    le rang 1, et une fiche qui reagirait a un remplacement de rang 0 ou 2
    retirerait la sortie neuve sur un refus qui l'offre encore.

    **`source_name` est le nom DESIGNE, et il DIVERGE par defaut de celui que
    l'entree porte** (:data:`NOM_DESIGNE` contre :data:`NOM_DECLARE`,
    fermeture de `F9`). Les deux coincident dans le cas ordinaire du produit,
    et c'est precisement ce qui rendait la fabrique aveugle : un bandeau qui
    aurait lu `entree["source_name"]` rendait la meme chaine, sur les 107 tests
    du banc. Le seul test qui a besoin de la coincidence est celui qui compare
    le bandeau a la maquette VERBATIM, et il repose le nom declare a la main.
    """
    entree = ENTREE_BLOQUANTE if entree is None else entree
    criteres = None
    if not sans_criteres:
        criteres = dataclasses.replace(
            comparer_identite_rush(
                CriteresIdentiteRush.declares(entree),
                mesures if mesures is not None else MESURES_DIVERGENTES),
            entree=entree)
    # Les issues sont LUES dans la table publiee, jamais recopiees.
    issues = ISSUES_PAR_MOTIF[motif]
    if issue_de_remplacement is not None:
        remplacees = list(issues)
        remplacees[rang_remplace] = issue_de_remplacement
        issues = tuple(remplacees)
    return RefusDeDeclaration(
        "le coeur refuse", motif=motif,
        issues=issues,
        source_name=source_name, rush_id=rush_id,
        entree=entree, criteres=criteres)


def issue_de_remplacement_du_coeur(tige: str = "prise01") -> str:
    """Le texte que le coeur MET a la place de la seconde issue, **produit**.

    Il est leve par le seul producteur du depot -- `disambiguated_rush_id`, qui
    passe par `version_ranks.refus_de_rangs_epuises` -- plutot que recopie ici.
    Une chaine sentinelle rendrait le banc vert le jour ou le coeur cesserait
    de remplacer quoi que ce soit ; ce texte-la ne peut pas exister sans que le
    regime existe.

    Le regime est celui des **99 rangs consommes**, et il se fabrique sans
    disque et sans `ffprobe` : la famille complete d'homonymes suffit.
    """
    from mixed_media_utility.extraction import (
        RangsDeDesambiguisationEpuises,
        disambiguated_rush_id,
    )

    famille = [{"rush_id": tige}] + [
        {"rush_id": f"{tige}-{rang}"} for rang in range(2, 100)]
    try:
        disambiguated_rush_id(tige, famille)
    except RangsDeDesambiguisationEpuises as epuisement:
        return str(epuisement)
    raise AssertionError(
        "le coeur ne refuse plus a 99 rangs : le regime que ce banc mesure "
        "n'existe plus, et les frontieres de `F1` ne mesurent plus rien")


def fiche(**kwargs) -> ajout_de_rush.FicheDeRefusDeConflit:
    return ajout_de_rush.FicheDeRefusDeConflit(refus_de_conflit(**kwargs))


def sans(cle_du_critere: str) -> dict:
    """L'entree bloquante privee d'UN critere, les trois autres intacts."""
    ampute = dict(ENTREE_BLOQUANTE)
    ampute.pop(cle_du_critere, None)
    return ampute


# ===========================================================================
# 1. Le modele contre la maquette validee
# ===========================================================================

#: Ce que le produit rend AUTREMENT que la maquette, et **pourquoi**. Une
#: entree sans raison n'a pas sa place ici ; une entree qui cesse de diverger
#: fait rougir le volet symetrique.
#:
#: Cle : le rang de la ligne dans le corps du cartouche.
DIVERGENCES_NOMMEES = {
    1: ("la phrase d'explication est REPLIEE par jetons.envelopper, la "
        "maquette la coupe a la main. Le dessin passe a la ligne apres "
        "« rush » (61 colonnes sur 68), un repliement glouton y fait encore "
        "tenir « déjà ». Le TEXTE est le meme -- c'est ce que mesure "
        "test_la_PHRASE_est_la_MEME_une_fois_recollee --, seule la coupe "
        "differe, et une coupe ecrite en dur serait fausse a la premiere "
        "largeur differente. Or une TUI se redimensionne."),
    2: ("seconde ligne de la meme phrase, meme raison : elle porte ce que la "
        "premiere n'a pas pris."),
}


def corps_dessine() -> list[str]:
    return ecrans.corps_du_cartouche(MAQUETTE)


def test_le_cartouche_rend_la_maquette_LIGNE_A_LIGNE():
    """Le modele contre le dessin valide, a largeur egale et rang par rang.

    C'est la mesure qui attrape la DERIVE : un libelle retouche, la colonne de
    valeur deplacee, l'ordre des criteres change -- rien de tout cela ne se
    voit a la relecture, et tout se voit ici.
    """
    attendu = corps_dessine()
    rendu = [ligne.ljust(LARGEUR_DESSINEE)
             for ligne in fiche().lignes(LARGEUR_DESSINEE)]
    assert len(rendu) == len(attendu), (
        f"{len(rendu)} lignes rendues pour {len(attendu)} dessinees :\n"
        + "\n".join(rendu))
    for rang, (dessine, produit) in enumerate(zip(attendu, rendu)):
        if rang in DIVERGENCES_NOMMEES:
            assert dessine != produit, (
                f"le rang {rang} est declare divergent et ne l'est plus : "
                f"retirer l'entree de DIVERGENCES_NOMMEES "
                f"({DIVERGENCES_NOMMEES[rang]})")
            continue
        assert produit == dessine, f"rang {rang}"


def test_l_inventaire_des_DIVERGENCES_ne_porte_que_des_ecarts_REELS():
    """Volet symetrique : une entree qui ne correspond a rien rendrait muet.

    Deux facons de deriver, et les deux comptent : un rang qui n'existe plus
    dans le cartouche, et une raison vide -- « un rappel legitimement
    optionnel entre dans l'inventaire **avec son motif ecrit**, jamais en
    silence » est l'interdit d'Egan sur la garde voisine, et il vaut ici mot
    pour mot.
    """
    corps = corps_dessine()
    for rang, raison in DIVERGENCES_NOMMEES.items():
        assert 0 <= rang < len(corps), (rang, len(corps))
        assert raison and raison.strip(), rang


def test_la_PHRASE_est_la_MEME_une_fois_recollee():
    """Le volet que la divergence de repliement laisse ouvert, et il est le
    seul qui compte : le TEXTE.

    Sans lui, `DIVERGENCES_NOMMEES` couvrirait deux lignes qu'on pourrait
    reecrire entierement sans faire rougir personne -- une divergence nommee
    ne doit jamais devenir une zone franche.
    """
    dessinee = " ".join(ligne.strip() for ligne in corps_dessine()[1:3])
    rendue = " ".join(jetons.envelopper(ajout_de_rush.PHRASE_DU_CONFLIT,
                                        LARGEUR_DESSINEE))
    assert rendue == dessinee, (rendue, dessinee)
    assert ajout_de_rush.PHRASE_DU_CONFLIT.split() == dessinee.split()


def test_le_titre_du_CADRE_est_celui_de_la_maquette():
    """Le titre est porte par la bordure, jamais par une ligne du corps.

    C'est `DESIGN.md` 7.4, et c'est un defaut deja paye sur `E2-1d` : poser le
    titre des deux cotes l'affichait DEUX FOIS, trouve sur une capture reelle
    et jamais par un test -- le banc mesurait le corps, et le titre du cadre
    n'est pas dans le corps. Les deux volets sont donc mesures ici.
    """
    grille = ecrans.grille(MAQUETTE)
    assert any(f"┌ {ajout_de_rush.TITRE_DU_REFUS_DE_CONFLIT} " in ligne
               for ligne in grille), ajout_de_rush.TITRE_DU_REFUS_DE_CONFLIT
    corps = fiche().lignes(LARGEUR_DESSINEE)
    assert not any(ajout_de_rush.TITRE_DU_REFUS_DE_CONFLIT in ligne
                   for ligne in corps), (
        "le titre du cadre est AUSSI dans le corps : il s'afficherait deux "
        "fois, c'est le defaut paye sur E2-1d le 2026-08-30")


def test_la_ligne_d_etat_est_rendue_VERBATIM():
    """`EPIC11-ARB-56` : elle porte une MESURE de l'ecran courant.

    Aucune divergence n'est admise ici : c'est la ligne qui porte les deux
    cardinaux, et un cardinal perime est pire qu'absent -- il se lit comme une
    verification. C'est exactement la panne qu'`ARB-231` a produite du cote du
    dessin.
    """
    modele = fiche()
    choix = modele.suites(DOSSIER_DESIGNE)
    assert modele.etat(choix) == ecrans.ligne_d_etat(MAQUETTE)


def test_les_deux_cardinaux_de_la_ligne_d_etat_sont_COMPTES():
    """Le volet de MORSURE de la ligne d'etat : deux issues retirees, la ligne
    doit changer des deux cotes -- le cardinal ET l'accord du verbe.

    Sans lui, la ligne pourrait etre une constante qui se trouve juste.
    """
    from mixed_media_utility.tui.panneau import ChoixExclusif, Issue

    reduit = ChoixExclusif(issues=[
        Issue("ecrit", "une qui ecrit", ecrit=True),
        Issue("sort", "une qui sort", ecrit=False)])
    ligne = ajout_de_rush.etat_du_refus_de_conflit(MOTIF_RUSH_DEJA_DECLARE,
                                                   reduit)
    assert "2 issues, 1 écrit" in ligne, ligne
    assert "écrivent" not in ligne, (
        "l'accord du verbe ne suit pas le cardinal : « 1 écrivent » se lit "
        "comme une faute de frappe, et une relecture ne la rattrape pas plus "
        "qu'elle n'a rattrape le « 2 issues » perime d'ARB-231")


def test_le_bandeau_nomme_le_fichier_DESIGNE_et_le_dit_refuse():
    """`plan séquence 12.mov · refusé`, verbatim de la maquette.

    Le nom est celui que l'operateur vient de designer -- le bandeau dit ce
    qu'il vient de faire --, jamais l'identifiant derive (`EPIC11-ARB-228`).

    **C'est le SEUL test du banc qui repose le nom declare du cote designe**,
    et il le fait a la main plutot que par le defaut de la fabrique : la
    maquette dessine le cas ordinaire, ou l'operateur redesigne le fichier qui
    porte deja ce nom, donc les deux cotes y coincident. Mesurer la
    coincidence ici et la divergence ailleurs est ce qui permet aux deux
    d'etre vraies -- voir `F9` et
    :func:`test_F9_le_BANDEAU_porte_le_nom_DESIGNE_et_JAMAIS_le_DECLARE`.
    """
    grille = ecrans.grille(MAQUETTE)
    nominale = fiche(source_name=NOM_DECLARE)
    assert nominale.bandeau() in grille[1], grille[1]
    assert "plan-sequence-12" not in nominale.bandeau()


@pytest.mark.parametrize("ascii_seul", MODES)
def test_aucune_ligne_du_cartouche_ne_DEPASSE_sa_largeur(ascii_seul):
    """Mesure en COLONNES et jamais en `len()`.

    `textual` ne tronque pas une ligne trop longue, il la **replie** : sur une
    zone de hauteur fixe, la fin part sur une ligne qui n'est jamais dessinee.
    C'est le defaut paye sur `LigneChiffree`, puis a nouveau sur
    `ligne_de_fiche` au lot precedent (45 colonnes pour 40).
    """
    for largeur in (40, 55, LARGEUR_DESSINEE, 120):
        for ligne in fiche().lignes(largeur, ascii_seul):
            assert jetons.colonnes(ligne) <= largeur, (largeur, ligne)


# ===========================================================================
# 2. Les frontieres NEGATIVES
# ===========================================================================

def test_aucune_valeur_du_cartouche_n_est_RELUE_dans_le_MANIFESTE(tmp_path):
    """`EPIC11-ARB-148` : la comparaison se tient a UN SEUL endroit.

    **La mesure, et c'est la seule forme qui l'attrape** : un manifeste est
    ecrit sur le disque avec des valeurs DIFFERENTES pour le meme `rush_id`,
    puis le cartouche est rendu sur le refus. Si une seule valeur du disque
    apparaissait, c'est que la TUI serait allee la chercher -- une seconde
    source de verite pour la meme question, exactement ce que l'arbitrage
    interdit.

    Aucun test positif ne verrait cette regression : le cartouche resterait
    plausible, et il ne divergerait qu'un jour ou le manifeste aurait ete
    modifie entre le refus et le dessin.
    """
    dossier = creer_projet(tmp_path, "projet_menteur").chemin
    document = json.loads(
        (dossier / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    document["rushes"] = [dict(ENTREE_BLOQUANTE,
                               source_name="AUTRE_NOM_SUR_LE_DISQUE.mov",
                               fps_source_exact="48/1",
                               source_frame_count=1234,
                               source_start_timecode="23:59:59:23",
                               source_path="Z:\\ailleurs\\autre\\x.mov")]
    (dossier / MANIFEST_FILENAME).write_text(json.dumps(document),
                                             encoding="utf-8")
    rendu = "\n".join(fiche().lignes(LARGEUR_DESSINEE))
    for menteuse in ("AUTRE_NOM_SUR_LE_DISQUE", "48 fps", "1 234",
                     "23:59:59:23", "ailleurs"):
        assert menteuse not in rendu, (
            f"{menteuse!r} vient du MANIFESTE et non du refus : la TUI a "
            f"relu le disque\n{rendu}")
    # Volet positif : ce sont bien les valeurs du refus qui sont dessinees.
    for attendue in (NOM_DESSINE, CARDINAL_DESSINE, "25 fps",
                     "00:00:04:12", "03_tournage_mai"):
        assert attendue in rendu, attendue


@pytest.mark.parametrize("axe", ("fps_source_exact", "source_frame_count",
                                 "source_start_timecode"))
def test_le_cartouche_montre_le_cote_DECLARE_et_JAMAIS_le_MESURE(axe):
    """Le cote declare et le cote mesure divergent sur CHAQUE axe, un par un.

    **Le corollaire d'axe de la regle des fabriques**, paye cette semaine :
    deux sources qui portent la meme valeur rendent invisible un mutant qui
    inverse leur ordre. Ici les deux cotes coincident **par construction** dans
    le produit -- c'est ce qui fait le refus --, donc seule une fabrique qui
    les fait diverger peut mesurer lequel des deux est dessine.

    Et le bon cote n'est pas indifferent : le cartouche s'appelle « un rush
    identique existe **déjà** » et sa derniere ligne dit « **Déclaré** depuis ».
    Il decrit le rush enregistre.
    """
    valeur_mesuree = getattr(MESURES_DIVERGENTES, axe)
    rendu = "\n".join(fiche().lignes(LARGEUR_DESSINEE))
    if axe == "fps_source_exact":
        trace = "23,976"          # 24000/1001 rendu par cadence_lisible
    elif axe == "source_frame_count":
        trace = "9 999"
    else:
        trace = str(valeur_mesuree)
    assert trace not in rendu, (
        f"l'axe {axe} est dessine du cote MESURE ({trace}) : le cartouche "
        f"decrit le fichier designe au lieu du rush declare\n{rendu}")


# ---------------------------------------------------------------------------
# `F9` -- l'axe DESIGNE / DECLARE, le seul de cet ecran que rien ne mesurait
# ---------------------------------------------------------------------------

def test_F9_les_deux_noms_de_la_fabrique_rendent_le_MEME_rush_id():
    """La fabrique mesure un ecran REEL, et c'est mesure plutot que suppose.

    Sans ce volet, `F9` se fermerait sur une divergence inventee : deux noms
    qui ne se rencontreraient jamais sous le meme identifiant ne peuvent pas
    produire un refus de conflit, et le banc mesurerait alors un ecran que le
    produit ne peut pas afficher -- exactement la panne que `CLAUDE.md` nomme
    « une fixture de synthese peut fabriquer une panne que le terrain n'a
    PAS ».

    Le refus se leve sur le `rush_id`, et le coeur le derive du **radical** du
    nom (`extraction`, `normalize_identifier(video_path.stem)`). Les accents,
    les espaces et la casse de l'extension y sont replies ; `plan séquence
    12.mov` et `plan sequence 12.MP4` rendent donc le meme identifiant tout en
    etant deux fichiers differents -- un remuxage, le cas ordinaire du
    montage.

    Les deux volets comptent : le meme identifiant (sans quoi il n'y a pas de
    conflit) **et** deux textes differents (sans quoi il n'y a pas de mesure).
    """
    from mixed_media_utility.io.naming import normalize_identifier

    assert NOM_DESIGNE != NOM_DECLARE, (
        "les deux cotes de la fabrique portent la MEME chaine : le bandeau "
        "peut lire l'entree sans que rien ne rougisse, c'est le defaut `F9`")
    identifiants = {normalize_identifier(Path(nom).stem)
                    for nom in (NOM_DESIGNE, NOM_DECLARE)}
    assert identifiants == {ENTREE_BLOQUANTE["rush_id"]}, identifiants


def test_F9_le_BANDEAU_porte_le_nom_DESIGNE_et_JAMAIS_le_DECLARE():
    """« La seule place de cet ecran ou les deux se separent » (`ARB-153`).

    Le bandeau dit ce que l'operateur vient de faire, le cartouche ce que le
    projet porte deja. Le mutant que ce test tue est le symetrique exact de
    celui qui etait deja mort du cote du cartouche : `bandeau` lisant
    `entree["source_name"]` au lieu de `refus.source_name`.

    L'egalite est **exacte** plutot qu'une appartenance : le nom declare est
    presque le nom designe -- meme radical au repliement pres --, et une
    assertion d'appartenance survivrait a un bandeau qui les melangerait.
    """
    bandeau = fiche().bandeau()
    assert bandeau == f"{NOM_DESIGNE}{rushes.SEPARATEUR}" \
                      f"{ajout_de_rush.MENTION_REFUSE}", bandeau
    assert NOM_DECLARE not in bandeau, (
        f"le bandeau porte le nom du rush DECLARE ({NOM_DECLARE!r}) : il dit "
        f"ce que le projet contient au lieu de ce que l'operateur vient de "
        f"designer\n{bandeau}")
    assert ENTREE_BLOQUANTE["rush_id"] not in bandeau, (
        f"le bandeau porte l'identifiant derive et non le VRAI nom du "
        f"fichier (`EPIC11-ARB-228`)\n{bandeau}")


def test_F9_volet_symetrique_le_CARTOUCHE_porte_le_nom_DECLARE():
    """L'autre moitie du partage, sans laquelle la premiere ne prouve rien.

    Un ecran qui porterait le nom DESIGNE des DEUX cotes ferait rougir le test
    precedent sur son volet negatif, jamais sur le volet positif ; un ecran qui
    porterait le nom DECLARE des deux cotes ne le ferait rougir que la. Il faut
    donc les deux volets pour que l'axe soit tenu -- c'est le meme geste que
    :func:`test_le_cartouche_montre_le_cote_DECLARE_et_JAMAIS_le_MESURE`,
    applique a l'axe que la fabrique ne faisait pas diverger.

    La ligne visee est reconnue par son LIBELLE et non par son rang : un test
    qui asserterait « le rang 3 porte le nom » recopierait l'ordre du produit
    et mourrait avec lui.
    """
    modele = fiche()
    assert modele.nom_du_fichier() == NOM_DECLARE, modele.nom_du_fichier()
    lignes = modele.lignes(LARGEUR_DESSINEE)
    portant = [ligne for ligne in lignes
               if ligne.strip().startswith(ajout_de_rush.LIBELLE_NOM)]
    assert len(portant) == 1, lignes
    assert NOM_DECLARE in portant[0], portant[0]
    assert NOM_DESIGNE not in "\n".join(lignes), (
        f"le cartouche porte le nom DESIGNE ({NOM_DESIGNE!r}) : il decrit le "
        f"fichier qu'on vient de designer au lieu du rush deja declare\n"
        + "\n".join(lignes))


def test_F9_la_sortie_de_RELINK_nomme_le_fichier_DESIGNE():
    """La SECONDE place de l'ecran ou le nom designe passe, et le finding ne la
    nommait pas.

    `F9` ne parlait que du bandeau, sur la foi d'`EPIC11-ARB-153` (« la seule
    place de cet ecran ou les deux se separent »). Mesure : `suites` lit le
    meme `refus.source_name` pour composer « Relinker <fichier> vers <chemin
    designe> », et la note 3 d'Egan dit bien `[rushe]` -- le fichier que
    l'operateur vient de designer, celui vers lequel on repointe. Le meme
    mutant y vivait donc aussi, et le fermer d'un seul cote l'aurait laisse
    entier de l'autre.

    Le chemin est deja tenu par
    :func:`test_la_provenance_n_est_JAMAIS_le_dossier_que_l_OPERATEUR_a_DESIGNE`
    ; ce test-ci ne mesure que le NOM.
    """
    relink_libelle = fiche().suites(DOSSIER_DESIGNE, 120).issues[0].libelle
    assert relink_libelle.startswith(f"Relinker {NOM_DESIGNE} vers "), (
        relink_libelle)
    assert NOM_DECLARE not in relink_libelle, (
        f"la sortie de relink nomme le rush DECLARE ({NOM_DECLARE!r}) : elle "
        f"proposerait de repointer vers un fichier que l'operateur n'a pas "
        f"designe\n{relink_libelle}")


def test_la_provenance_n_est_JAMAIS_le_dossier_que_l_OPERATEUR_a_DESIGNE():
    """`EPIC11-ARB-153`, note 3, prise par son autre bout.

    Le cartouche dit d'ou vient le rush **declare** ; la sortie de relink dit
    ou il doit aller. Les confondre ferait proposer de relinker un fichier vers
    le dossier ou il est deja, et l'operateur ne verrait plus laquelle des deux
    journees de tournage est en cause -- ce qui est la seule raison d'etre de
    cet ecran.
    """
    modele = fiche()
    provenance = modele.ligne_de_provenance(LARGEUR_DESSINEE)
    assert "03_tournage_mai" in provenance, provenance
    assert "04_tournage_juin" not in provenance, provenance
    relink = modele.suites(DOSSIER_DESIGNE, 76).issues[0].libelle
    assert "04_tournage_juin" in relink, relink
    assert "03_tournage_mai" not in relink, relink


def test_la_provenance_est_un_DOSSIER_et_non_le_fichier():
    """Le dernier segment est retire, separateur final conserve.

    Sans ce volet, la ligne pourrait porter le chemin du fichier entier : elle
    resterait plausible, et elle dirait `Déclaré depuis <un fichier>`.
    """
    depuis = fiche().declare_depuis()
    assert depuis.endswith("\\"), depuis
    assert NOM_DESSINE not in depuis, depuis
    assert ENTREE_BLOQUANTE["source_path"].startswith(depuis)


def test_le_code_de_refus_est_DERIVE_du_motif_du_coeur():
    """Le code a tirets se derive, il ne se recopie pas a cote du motif.

    Deux redactions divergeraient au premier motif ajoute -- et le generateur
    des maquettes dit deja de son cote qu'« un code de refus est un
    identifiant enumere que rien n'autorise a renommer depuis une maquette ».
    """
    for motif in MOTIFS_DE_REFUS:
        code = ajout_de_rush.code_de_refus(motif)
        assert "_" not in code, code
        assert code.replace("-", "_") == motif, (code, motif)
    assert ajout_de_rush.code_de_refus(
        MOTIF_RUSH_DEJA_DECLARE) == "rush-deja-declare"


# ===========================================================================
# 3. Les quatre criteres : la regle des fabriques, aux deux bords
# ===========================================================================

def test_les_QUATRE_criteres_sont_dessines_dans_l_ordre_de_la_maquette():
    """L'ordre est mesure en egalite exacte, jamais en appartenance.

    Une permutation de deux criteres ne se verrait pas autrement, et elle
    changerait ce que l'operateur croit lire -- `6 300 frames` sous
    `Base de timecode` reste plausible une seconde de trop.
    """
    lignes = fiche().lignes_des_criteres(LARGEUR_DESSINEE)
    assert [ligne.split("  ")[0] for ligne in lignes] == list(
        LIBELLES_DES_CRITERES), lignes


@pytest.mark.parametrize("libelle", LIBELLES_DES_CRITERES)
def test_chaque_critere_ABSENT_retire_SA_ligne_et_ELLE_SEULE(libelle):
    """Omission stricte (`DESIGN.md` section 3), critere par critere.

    **Les quatre sont vises, donc la TETE et la QUEUE aussi** (point 4 de la
    regle des fabriques) : une cible au milieu ne demasque pas un balayage
    tronque, qui est un autre mode de panne que l'appariement fautif. Et le
    cas se produit vraiment -- un rush declare avant que la duree ne devienne
    un critere d'identite ne porte aucun cardinal, et le rush REEL du depot
    n'a pas de timecode de depart.

    Le volet « et elle seule » compte autant : une omission qui emporterait la
    LIGNE voisine passerait un test qui ne compterait que les lignes. Il porte
    sur les LIBELLES et non sur les lignes entieres, parce qu'une valeur
    voisine a le droit de maigrir -- voir
    :func:`test_la_DUREE_part_avec_la_CADENCE_et_c_est_une_derivation`.
    """
    entier = [ligne.split("  ")[0]
              for ligne in fiche().lignes_des_criteres(LARGEUR_DESSINEE)]
    ampute = [ligne.split("  ")[0]
              for ligne in fiche(entree=sans(CLE_PAR_LIBELLE[libelle]))
              .lignes_des_criteres(LARGEUR_DESSINEE)]
    assert ampute == [autre for autre in entier if autre != libelle], (
        entier, ampute)


def test_la_DUREE_part_avec_la_CADENCE_et_c_est_une_DERIVATION():
    """Le seul couplage entre deux lignes du cartouche, **nomme et mesure**.

    `Durée source` porte `6 300 frames · 4:12` : le cardinal est un critere, la
    duree en est **derivee** (`cardinal / cadence`, par `rushes.duree_de_rush`).
    Retirer la cadence retire donc la duree sans retirer la ligne, et c'est
    l'application de la regle d'omission plutot qu'une exception -- « une duree
    fausse est pire qu'une duree absente », que le coeur dit deja de son cote.

    Sans ce test, le couplage serait soit invisible, soit « repare » a tort en
    fabriquant une duree depuis une cadence par defaut. La TUI n'en fabrique
    aucune.
    """
    complet = fiche().texte_de_la_duree()
    sans_cadence = fiche(entree=sans("fps_source_exact")).texte_de_la_duree()
    assert complet == DUREE_SOURCE_DESSINEE, complet
    assert sans_cadence == CARDINAL_DESSINE, sans_cadence
    assert fiche(entree=sans("source_frame_count")).texte_de_la_duree() is None


@pytest.mark.parametrize("libelle", LIBELLES_DES_CRITERES)
def test_un_critere_ABSENT_est_NOMME_par_criteres_absents(libelle):
    """La mesure de ce que le cartouche ne peut pas montrer.

    Elle existe pour que l'ecart avec la maquette -- qui dessine QUATRE
    criteres -- soit visible plutot que tu. Le volet symetrique est le
    nominal : sur une entree complete, rien ne manque.
    """
    assert fiche().criteres_absents() == ()
    assert fiche(entree=sans(CLE_PAR_LIBELLE[libelle])).criteres_absents() == (
        libelle,)


def test_les_quatre_valeurs_du_cartouche_sont_DISTINGUABLES():
    """Point 1 de la regle des fabriques, sur la collection mesuree.

    Quatre valeurs egales rendraient invisible toute permutation, et les tests
    d'ordre et d'omission ci-dessus passeraient sans rien mesurer.
    """
    valeurs = [ligne[ajout_de_rush.COLONNE_DE_VALEUR:].strip()
               for ligne in fiche().lignes_des_criteres(LARGEUR_DESSINEE)]
    assert len(set(valeurs)) == len(valeurs) == 4, valeurs


def test_un_refus_SANS_criteres_reste_MONTRABLE():
    """Un refus fabrique a la main -- un banc qui substitue le coeur -- n'a pas
    forcement de preuve, et l'ecran ne doit pas lever pour autant.

    Le cartouche se reduit alors a ce que l'entree porte. Une exception ici
    remplacerait un refus lisible par une trace Python devant un operateur, ce
    que le depot interdit partout ailleurs.
    """
    modele = fiche(sans_criteres=True)
    lignes = modele.lignes(LARGEUR_DESSINEE)
    assert lignes[0] == modele.code()
    assert any(ajout_de_rush.LIBELLE_NOM in ligne for ligne in lignes)
    assert set(modele.criteres_absents()) == {
        ajout_de_rush.LIBELLE_DUREE_SOURCE,
        ajout_de_rush.LIBELLE_BASE_DE_TIMECODE,
        ajout_de_rush.LIBELLE_TIMECODE_INITIAL}


def test_une_cadence_ILLISIBLE_retire_sa_ligne_sans_LEVER():
    """Un manifeste corrompu ne fait pas tomber un ecran de refus.

    `fps_source_exact` est un rationnel ecrit par le coeur ; rien ne garantit
    qu'un manifeste edite a la main en porte un. La ligne disparait, le refus
    reste montrable -- c'est la seule chose qui compte devant un operateur
    bloque.
    """
    modele = fiche(entree=dict(ENTREE_BLOQUANTE,
                               fps_source_exact="pas/un/ratio"))
    assert modele.cadence() is None
    assert ajout_de_rush.LIBELLE_BASE_DE_TIMECODE in modele.criteres_absents()
    assert modele.lignes(LARGEUR_DESSINEE)


# ===========================================================================
# 4. L'ecran monte, et ce que chaque issue FAIT au disque
# ===========================================================================

#: Le rush deja declare est celui du MILIEU du projet, jamais le premier : un
#: `find` fautif qui rendrait la premiere entree relinkerait le mauvais rush,
#: avec un manifeste valide a l'arrivee. C'est le mode de panne de `_find_lot`
#: en 5.7.
RUSH_BLOQUANT = voisin.RUSHES[2]


def probe_du_banc(chemin):
    """Un probe qui repond ce que le rush declare attend, sans ffprobe.

    Le contenu importe peu : `verifier_designation_manuelle` compare aux
    criteres de la REFERENCE, et les entrees de `voisin.projet` n'en portent
    aucun. Ce que ce double garantit, c'est qu'aucun sous-processus n'est paye
    dans un banc qui mesure une navigation.
    """
    from mixed_media_utility import relink

    return relink.ProbeCandidat(nom_de_base=Path(chemin).name,
                                cardinal_frames=6300, cardinal_est_exact=True,
                                timecode_depart="00:00:04:12")


def preparation_qui_refuse(motif: str = MOTIF_RUSH_DEJA_DECLARE,
                           rush_id: str | None = RUSH_BLOQUANT,
                           issue_de_remplacement: str | None = None):
    """Un temps 1 de banc qui REFUSE, avec un refus complet.

    Le double de `test_ecrans_declaration_de_rush` refuse aussi, mais sans
    `entree` ni `criteres` : il datait du jour ou aucun ecran ne les lisait.
    Celui-ci porte la preuve, parce que c'est elle que `E2-1f` dessine.

    **`issue_de_remplacement` fait basculer le double dans le regime que `F1`
    nomme, et il ACCEPTE de moins.** Le double d'origine acceptait *toujours*
    `force_distinct=True` -- c'est ce qui rendait la boucle invisible : le
    second refus n'avait aucun banc.

    Le regime est reproduit tel que le VRAI coeur le joue, en DEUX temps --
    c'est ce que la section 6 bis mesure sans double :

    * le premier appel, sans drapeau, refuse avec la table PLEINE. Le coeur ne
      sait pas encore que les rangs sont epuises : il ne l'apprend qu'en
      cherchant un rang libre, ce qu'il ne fait que sous forcage. L'ecran offre
      donc bien ses trois sorties ;
    * le second, sous `force_distinct=True`, refuse a nouveau -- la garde qui
      cherche le rang est celle-la meme que le drapeau devait franchir -- et
      c'est LA que le coeur remplace sa seconde issue.

    Un double qui poserait le remplacement des le premier refus mesurerait un
    regime que le produit n'a pas, et raterait la moitie qui compte : la
    SECONDE monte de `E2-1f`, celle ou l'operateur bouclait.
    """
    vues = []

    def preparer(cible: Path, *, force_distinct: bool = False):
        vues.append((Path(cible), force_distinct))
        if force_distinct and issue_de_remplacement is None:
            # `EPIC11-ARB-232` : la separation forcee passe, et le chemin de
            # declaration ordinaire reprend -- panneau chiffre compris.
            return ecrans.preparee(chemin=str(cible))
        raise refus_de_conflit(
            motif=motif, rush_id=rush_id,
            source_name=Path(cible).name,
            issue_de_remplacement=(issue_de_remplacement
                                   if force_distinct else None),
            entree=dict(ENTREE_BLOQUANTE, rush_id=rush_id or "",
                        source_name=Path(cible).name))

    preparer.vues = vues
    return preparer


#: **Le predicat de presence du COEUR, et c'est une valeur par defaut qui a un
#: sens** (finding `F6`). Tous les bancs de ce paquet injectaient jusqu'ici un
#: `existe=` STATIQUE, indexe sur la chaine de chemin : le statut d'une ligne
#: ne dependait alors **pas du manifeste**, et la fraicheur d'une relecture
#: etait structurellement invisible -- un `relire()` joue avant l'ecriture
#: rendait exactement la meme liste qu'un `relire()` joue apres. Cette
#: sentinelle dit « laisse le coeur toucher le disque » ; c'est le seul regime
#: ou l'ORDRE des deux gestes s'observe.
_PREDICAT_REEL = object()


def au_refus(banc, monkeypatch, tmp_path, preparer, ecrire=None, suite=None,
             dossier=None, existe=_PREDICAT_REEL):
    """Monter `E2-1`, designer la video du MILIEU, jouer `suite` sur le dessus.

    Le parcours est celui du CLAVIER, jamais un appel direct : c'est le piege
    que `test_journal_du_produit.py` raconte. Tout se joue dans UNE seule
    session `run_test` -- remonter le meme ecran dans une seconde boucle
    `asyncio` casse les verrous que `textual` lui a attaches.

    `dossier` laisse l'appelant fabriquer SON projet -- c'est ce dont le volet
    `F6` a besoin, qui doit tuer des chemins avant le montage. `existe` reste a
    :data:`_PREDICAT_REEL`, c'est-a-dire au predicat du COEUR : voir sa note,
    un predicat injecte rend la fraicheur de la relecture invisible.
    """
    dossier = voisin.projet(tmp_path) if dossier is None else dossier
    monkeypatch.chdir(voisin.dossier_des_videos(tmp_path))
    ecran = amont.EcranRushes(dossier, preparer=preparer, ecrire=ecrire,
                              probe=probe_du_banc,
                              **({} if existe is _PREDICAT_REEL
                                 else {"existe": existe}))
    boite: dict = {"dossier": dossier}

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        boite["avant"] = ecrans.empreinte_du_manifeste(dossier)
        boite["cible"] = await voisin.designer_la_video(pilote, ecran)
        boite["apres_le_refus"] = ecrans.empreinte_du_manifeste(dossier)
        boite["dessus"] = pilote.app.screen
        if suite is not None:
            boite["suite"] = await suite(pilote, boite["dessus"])
        return boite

    boite = banc(voisin.coque(ecran), scenario)
    return ecran, boite


def test_le_refus_de_conflit_monte_E2_1f_et_n_ecrit_RIEN(tmp_path, banc,
                                                         monkeypatch):
    """L'ecran existe, il porte le bon cartouche, et le temps 1 n'a rien ecrit.

    C'est le pis-aller qui tombe : avant ce lot, `boite["dessus"]` etait un
    `EcranPasEncore` qui NOMMAIT l'ecran manquant.
    """
    ecran, boite = au_refus(banc, monkeypatch, tmp_path,
                            preparation_qui_refuse())
    dessus = boite["dessus"]
    assert isinstance(dessus, amont.EcranRefusDeConflit), type(dessus)
    assert not isinstance(dessus, EcranPasEncore)
    assert boite["apres_le_refus"] == boite["avant"], (
        "le temps 1 a touche le manifeste")
    lignes = dessus.fiche.lignes(72)
    assert lignes[0].endswith("rush-deja-declare"), lignes[0]
    assert any(voisin.VIDEO_CIBLE in ligne for ligne in lignes), lignes


def test_le_curseur_de_l_ecran_MONTE_part_sur_la_sortie_qui_n_ecrit_pas(
        tmp_path, banc, monkeypatch):
    """`EPIC11-ARB-7` sous la forme d'`EPIC11-ARB-45`, mesure sur l'ECRAN.

    Deux des trois issues ecrivent ici -- c'est une premiere pour un ecran de
    refus de cet epic --, donc la garde compte double : une ecriture ne doit
    pas etre atteignable en UNE frappe depuis le montage.
    """
    _ecran, boite = au_refus(banc, monkeypatch, tmp_path,
                             preparation_qui_refuse())
    choix = boite["dessus"].choix
    assert choix.issues[choix.curseur].cle == ajout_de_rush.CLE_ANNULER
    assert choix.issues[choix.curseur].ecrit is False
    assert choix.retenue is None, "aucune issue n'est preselectionnee"
    assert sum(1 for issue in choix.issues if issue.ecrit) == 2


def test_RELINKER_repointe_le_rush_DECLARE_vers_le_fichier_DESIGNE(
        tmp_path, banc, monkeypatch):
    """La premiere des deux issues qui ECRIVENT, mesuree sur le manifeste.

    Le rush repointe est **celui que le refus nomme**, pas celui sous le
    curseur : `rush_a_relinker()` ne rend que le rush courant s'il est ABSENT,
    or celui-ci est present et n'a aucune raison d'etre sous le curseur. Le
    test le verifie des deux cotes -- la bonne entree bouge, les autres ne
    bougent pas.
    """
    async def relinker(pilote, ecran_du_refus):
        ecran_du_refus.choix.viser(ajout_de_rush.CLE_RELINKER)
        ecran_du_refus.traiter("enter")
        await pilote.pause()

    ecran, boite = au_refus(banc, monkeypatch, tmp_path,
                            preparation_qui_refuse(), suite=relinker)
    dossier = boite["dossier"]
    document = json.loads(
        (dossier / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    par_id = {entree["rush_id"]: entree for entree in document["rushes"]}
    assert par_id[RUSH_BLOQUANT]["source_path"] == str(
        Path(boite["cible"]).resolve()), par_id[RUSH_BLOQUANT]
    # Volet symetrique : les quatre autres rushes n'ont pas bouge.
    for rush_id in voisin.RUSHES:
        if rush_id == RUSH_BLOQUANT:
            continue
        assert Path(par_id[rush_id]["source_path"]).name == f"{rush_id}.mov", (
            f"{rush_id} a ete relinke a la place de {RUSH_BLOQUANT}")
    assert ecran.liste.courant.rush_id == RUSH_BLOQUANT, (
        "le curseur ne s'est pas pose sur le rush repointe")


def test_DECLARER_SEPAREMENT_repasse_par_le_TEMPS_1_avec_FORCE_DISTINCT(
        tmp_path, banc, monkeypatch):
    """La seconde issue qui ecrit -- et elle **n'ecrit pas tout de suite**.

    `EPIC11-ARB-232` porte la separation jusqu'au coeur, `EPIC11-ARB-4` exige
    qu'un panneau chiffre precede toute ecriture : les deux se composent, donc
    la sortie neuve rend le panneau `E2-1e` plutot que d'ecrire. Le disque est
    mesure pour le dire, sans quoi « ca marche » recouvrirait une ecriture
    silencieuse.
    """
    preparer = preparation_qui_refuse()

    async def separer(pilote, ecran_du_refus):
        ecran_du_refus.choix.viser(ajout_de_rush.CLE_SEPARER)
        ecran_du_refus.traiter("enter")
        await pilote.pause()
        return (pilote.app.screen,
                ecrans.empreinte_du_manifeste(tmp_path / "projet_demo"))

    _ecran, boite = au_refus(banc, monkeypatch, tmp_path, preparer,
                             suite=separer)
    dessus, apres = boite["suite"]
    assert [force for _cible, force in preparer.vues] == [False, True], (
        "le second passage n'a pas pose force_distinct : la sortie neuve "
        f"refait exactement ce qui vient d'etre refuse. Vues : {preparer.vues}")
    assert [cible.name for cible, _f in preparer.vues] == [
        voisin.VIDEO_CIBLE, voisin.VIDEO_CIBLE], (
        "le second passage porte sur un AUTRE fichier que celui designe")
    assert isinstance(dessus, amont.EcranDeclaration), type(dessus)
    assert apres == boite["avant"], (
        "declarer separement a ecrit AVANT son panneau chiffre "
        "(EPIC11-ARB-4)")


def test_ANNULER_ne_touche_ni_le_DISQUE_ni_la_LISTE(tmp_path, banc,
                                                    monkeypatch):
    """La troisieme issue, et le volet symetrique des deux precedentes.

    Le mesurer sur l'empreinte du manifeste plutot que sur un compteur
    d'appels est delibere : un chemin d'ecriture contourne ne se verrait pas
    sur un compteur.
    """
    async def annuler(pilote, ecran_du_refus):
        ecran_du_refus.choix.viser(ajout_de_rush.CLE_ANNULER)
        ecran_du_refus.traiter("enter")
        await pilote.pause()
        return ecrans.empreinte_du_manifeste(tmp_path / "projet_demo")

    ecran, boite = au_refus(banc, monkeypatch, tmp_path,
                            preparation_qui_refuse(), suite=annuler)
    assert boite["suite"] == boite["avant"]
    assert ecran.zone == amont.ZONE_LISTE


#: Les quatre AUTRES motifs. L'inventaire est **derive du coeur** et non ecrit :
#: un sixieme motif ajoute demain entrerait tout seul dans la mesure, du bon
#: cote. Le motif de conflit, lui, est en QUEUE de `MOTIFS_DE_REFUS` -- voir
#: :func:`test_le_motif_qui_MONTE_l_ecran_est_en_QUEUE_de_l_inventaire_du_coeur`
#: pour ce que ce rang-la coute a un balayage tronque.
AUTRES_MOTIFS = tuple(motif for motif in MOTIFS_DE_REFUS
                      if motif != MOTIF_RUSH_DEJA_DECLARE)


@pytest.mark.parametrize("motif", AUTRES_MOTIFS)
def test_les_QUATRE_AUTRES_motifs_ne_montent_PAS_cet_ecran(motif, tmp_path,
                                                           banc, monkeypatch):
    """Frontiere NEGATIVE, et la cible est a CHAQUE BORD de l'inventaire.

    Ces quatre refus tombent AVANT toute comparaison : ni criteres a montrer,
    ni entree bloquante a nommer, ni relink a proposer. Leur faire monter
    `E2-1f` afficherait un cadre vide sous un titre qui affirme qu'un rush
    identique existe -- et proposerait de relinker vers un fichier qui,
    parfois, n'existe pas.

    Ils gardent donc le « pas encore », qui NOMME le motif : c'est le defaut
    `K1.1` pris par son autre bout, et il ne se rouvre pas.
    """
    _ecran, boite = au_refus(banc, monkeypatch, tmp_path,
                             preparation_qui_refuse(motif, rush_id=None))
    dessus = boite["dessus"]
    assert not isinstance(dessus, amont.EcranRefusDeConflit), motif
    assert isinstance(dessus, EcranPasEncore), type(dessus)
    dit = "\n".join(dessus.lignes())
    assert motif in dit, dit
    assert voisin.VIDEO_CIBLE in dit, dit
    assert boite["apres_le_refus"] == boite["avant"]


def test_le_motif_qui_MONTE_l_ecran_est_en_QUEUE_de_l_inventaire_du_coeur():
    """La garde de l'inventaire, et elle dit ou tombe la cible.

    **Mesure plutot que supposition** : le motif de conflit est le
    **dernier** de `MOTIFS_DE_REFUS`, pas celui du milieu. C'est le pire des
    rangs pour un balayage tronque -- un `MOTIFS_DE_REFUS[:-1]` ecrit quelque
    part le laisserait tomber en silence, et l'ecran ne monterait plus jamais.
    Le rang est donc mesure ici, et les quatre autres motifs -- ceux qui
    gardent le « pas encore » -- couvrent la TETE et le milieu.

    Retirer une entree d'un `parametrize` joue une cible de moins sans faire
    rougir personne : c'est pour cela que l'inventaire est DERIVE du coeur et
    que son contenu est confronte ici.
    """
    assert MOTIFS_DE_REFUS[-1] == MOTIF_RUSH_DEJA_DECLARE, (
        "le motif de conflit a change de rang : les cibles de bord de ce banc "
        "sont a relire, elles ne mesurent plus ce qu'elles annoncent")
    assert MOTIFS_DE_REFUS[0] in AUTRES_MOTIFS
    assert MOTIFS_DE_REFUS[1] in AUTRES_MOTIFS
    assert MOTIF_RUSH_DEJA_DECLARE not in AUTRES_MOTIFS
    assert len(AUTRES_MOTIFS) == len(MOTIFS_DE_REFUS) - 1


# ===========================================================================
# 5. Le TERRAIN : le vrai coeur, le vrai ffprobe, un vrai rush du depot
# ===========================================================================

#: Le rush de synthese du depot qui se DECODE vraiment -- 50 frames a 25 im/s.
#: `CLAUDE.md` : « une mesure de synthese mesure la synthese ; elle ne devient
#: une mesure du produit que confrontee a un artefact de terrain ».
#:
#: **Corrige le 2026-09-05, finding `F14` de la revue 11.4e.** Cette place
#: affirmait que les autres `rush_test_*.mp4` du dossier « sont des tetes de
#: fichier de 131 octets, qui ne passent pas `ffprobe` ». C'est faux du
#: FICHIER, et mesure tel : ils pesent 190 561, 210 153, 210 393 et 236 295
#: octets, et `ffprobe` les qualifie tous les quatre -- 125 frames a 25/1. Le
#: journal d'`EPIC11-ARB-230` de cette meme fiche disait deja correctement
#: l'inverse.
#:
#: 131 octets, c'est la taille d'un POINTEUR LFS, pas celle d'un rush. Ces
#: quatre-la ETAIENT des objets LFS orphelins de leurs attributs --
#: `git check-attr filter` y rendait `unspecified` depuis que la revision du
#: 2026-09-03 a scope le LFS par chemin --, si bien qu'un conteneur portant
#: `filter.lfs.smudge = --skip` les materialisait en pointeurs, et c'est le
#: pointeur qui ne passait pas `ffprobe`.
#:
#: **`EPIC11-ARB-247` (2026-09-06) a ferme cet ecart** : les CINQ rushes de ce
#: dossier sont desormais en git ordinaire, ~200 Ko piece, et `HEAD` porte leur
#: media. Aucun ne depend plus de l'etat LFS du conteneur, et le choix de
#: `..._50img.mp4` ne tient donc plus a son regime de stockage mais a sa
#: BRIEVETE -- 50 frames au lieu de 125, la ou ce banc n'a besoin que d'un rush
#: qui se decode. Le regime des rushes reste fige par
#: `REGIME_GIT_DES_RUSHES`, dans `tests/unit/test_rang_de_desambiguisation.py`.
#: La sonde de taille reste posee malgre tout -- c'est le seul verdict qui
#: vaille --, mais elle ROUGIT desormais au lieu de sauter
#: (`EPIC11-ARB-241`, Egan le 2026-09-05) : voir `rangs.exiger_le_media`, qui
#: porte le motif et le cout accepte.
RUSH_QUI_SE_DECODE = (_RACINE / "tests" / "fixtures" / "rushes"
                      / "rush_test_16x9_1920x1080_25fps_50img.mp4")


def test_le_refus_du_VRAI_coeur_remplit_le_cartouche(tmp_path):
    """Le meme fichier dans DEUX dossiers, declare une fois, redesigne ensuite.

    C'est le cas nominal d'`EPIC11-ARB-230` : le dossier ne separe plus, donc
    deux copies du meme rush font un conflit, quel que soit l'endroit. Rien
    n'est double ici -- vrai `ffprobe`, vrai manifeste, vrai refus -- et c'est
    le seul test du banc qui garantit que les cles lues par la fiche sont bien
    celles que le coeur ECRIT.

    **Il produit tout seul un critere non verifiable** : ce rush ne porte pas
    de timecode de depart, donc la ligne s'omet et `criteres_absents` la nomme.
    C'est l'ecart avec la maquette, qui en dessine quatre -- nomme ici plutot
    que resolu en inventant une formulation qu'Egan n'a pas validee.
    """
    rangs.exiger_le_media(RUSH_QUI_SE_DECODE)
    journal = logging.getLogger("banc.E2-1f")
    dossier = creer_projet(tmp_path, "projet_terrain").chemin
    mai = tmp_path / "03_tournage_mai" / "hd"
    juin = tmp_path / "04_tournage_juin" / "hd"
    for dossier_source in (mai, juin):
        dossier_source.mkdir(parents=True)
        shutil.copy(RUSH_QUI_SE_DECODE, dossier_source / "plan sequence 12.mp4")

    premiere = preparer_une_declaration(
        project_dir=dossier, video_path=mai / "plan sequence 12.mp4",
        logger=journal)
    ecrire_la_declaration(premiere, logger=journal)

    with pytest.raises(RefusDeDeclaration) as leve:
        preparer_une_declaration(
            project_dir=dossier, video_path=juin / "plan sequence 12.mp4",
            logger=journal)
    refus = leve.value
    assert refus.motif == MOTIF_RUSH_DEJA_DECLARE, refus.motif

    modele = ajout_de_rush.FicheDeRefusDeConflit(refus)
    lignes = modele.lignes(LARGEUR_DESSINEE)
    rendu = "\n".join(lignes)
    assert lignes[0].endswith("rush-deja-declare"), lignes[0]
    assert "plan sequence 12.mp4" in rendu, rendu
    assert "50 frames" in rendu, rendu
    assert "25 fps" in rendu, rendu
    # La PROVENANCE est celle du premier dossier, jamais du second.
    assert "03_tournage_mai" in rendu, rendu
    assert "04_tournage_juin" not in rendu, rendu
    # L'ecart avec la maquette, mesure et non suppose.
    assert modele.criteres_absents() == (
        ajout_de_rush.LIBELLE_TIMECODE_INITIAL,), modele.criteres_absents()
    # Et la ligne d'etat compte bien les trois sorties du refus reel.
    choix = modele.suites(str(juin) + "/", 76)
    assert ETAT_DESSINE in modele.etat(choix)


# ---------------------------------------------------------------------------
# F20 -- la garde a UN SEUL segment : morte pour le produit, et mesuree telle
# ---------------------------------------------------------------------------
#
# `declare_depuis` refuse un chemin qui ne porte qu'un segment -- un nom de
# fichier nu, sans separateur. Le produit ne peut pas l'atteindre :
# `source_path` est ecrit RESOLU ABSOLU (`EPIC7-ARB-41`), et un chemin absolu
# porte toujours au moins la racine plus un nom. La garde n'est donc pas un
# defaut ; elle est un contrat qu'aucun chemin du produit n'exerce.
#
# Ce qui manquait, et que ces deux tests posent : la mesure que le produit
# n'y arrive pas AUJOURD'HUI -- prise sur ce que le coeur ECRIT, jamais sur
# une relecture du code --, et le volet qui garde le contrat tenu pour le jour
# ou il redeviendrait atteignable.


def test_F20_le_source_path_que_le_COEUR_ecrit_a_TOUJOURS_deux_segments(tmp_path):
    """La garde est morte parce que le coeur ecrit des chemins ABSOLUS.

    Mesure sur le vrai coeur, trois rushes DISTINGUABLES declares depuis trois
    dossiers de tournage differents -- la cible est donc en tete, au milieu et
    en queue de la liste que le manifeste porte, les deux bords compris. Un
    banc a un seul rush ne dirait pas si c'est le premier qui est absolu ou
    tous.

    Ce test rougira le jour ou `source_path` cesserait d'etre resolu absolu :
    la garde redeviendrait alors atteignable, et son `None` -- une ligne de
    provenance qui s'omet en silence -- cesserait d'etre inoffensif.
    """
    rangs.exiger_le_media(RUSH_QUI_SE_DECODE)
    journal = logging.getLogger("banc.E2-1f.F20")
    dossier = creer_projet(tmp_path, "projet_f20").chemin
    noms = ["plan sequence 12.mp4", "insert 03.mp4", "raccord final.mp4"]
    for indice, nom in enumerate(noms):
        source = tmp_path / f"0{indice + 3}_tournage" / "hd"
        source.mkdir(parents=True)
        shutil.copy(RUSH_QUI_SE_DECODE, source / nom)
        ecrire_la_declaration(
            preparer_une_declaration(project_dir=dossier,
                                     video_path=source / nom, logger=journal),
            logger=journal)

    entrees = json.loads(
        (dossier / "project.json").read_text(encoding="utf-8"))["rushes"]
    assert len(entrees) == len(noms), entrees
    # Garde d'inventaire : trois entrees DISTINGUABLES, pas trois fois la meme.
    assert len({e["source_path"] for e in entrees}) == len(noms)

    for entree in entrees:
        chemin = entree["source_path"]
        assert Path(chemin).is_absolute(), chemin
        assert len(ajout_de_rush.segments_de_chemin(chemin)) >= 2, chemin
        # Et le modele rend bien une provenance, jamais le `None` de la garde.
        depuis = ajout_de_rush.FicheDeRefusDeConflit(
            refus_de_conflit(entree=entree)).declare_depuis()
        assert depuis is not None, chemin
        assert chemin.startswith(depuis), (depuis, chemin)


@pytest.mark.parametrize("chemin, attendu", [
    (NOM_DESSINE, None),                    # un seul segment : la garde
    ("hd/" + NOM_DESSINE, "hd/"),           # deux : le bord juste au-dessus
    ("hd\\" + NOM_DESSINE, "hd\\"),         # l'autre separateur
    ("/" + NOM_DESSINE, "/"),               # absolu le plus court possible
])
def test_F20_volet_symetrique_la_garde_a_UN_segment_reste_TENUE(chemin, attendu):
    """Le contrat de la garde, exerce directement puisque le produit ne peut pas.

    Les quatre cas encadrent la frontiere plutot que de la supposer : un seul
    segment -- le cas mort --, puis les deux ecritures a deux segments et le
    chemin absolu le plus court que le produit puisse ecrire. Sans les trois
    voisins, un `declare_depuis` qui rendrait `None` sur TOUT passerait le
    premier cas.
    """
    entree = dict(ENTREE_BLOQUANTE, source_path=chemin)
    assert ajout_de_rush.FicheDeRefusDeConflit(
        refus_de_conflit(entree=entree)).declare_depuis() == attendu


def test_le_RAFRAICHI_qui_SUIT_la_touche_ne_tombe_pas(tmp_path, banc,
                                                      monkeypatch):
    """La sequence REELLE du clavier : `traiter`, puis `rafraichir`.

    `on_key` fait les deux a la suite -- c'est le contrat de tous les ecrans du
    paquet --, et sur celui-ci la premiere depile l'ecran et en empile parfois
    un autre. Le second rafraichi porte donc sur un ecran qui n'est plus au
    sommet, et il recompose ses suites au passage.

    **Un test qui n'appellerait que `traiter` ne verrait pas cette moitie-la**,
    et c'est exactement ce que les autres tests de ce banc font : ils mesurent
    l'EFFET de l'issue. Celui-ci mesure la sequence.
    """
    async def au_clavier(pilote, ecran_du_refus):
        ecran_du_refus.choix.viser(ajout_de_rush.CLE_SEPARER)
        ecran_du_refus.traiter("enter")
        ecran_du_refus.rafraichir()
        await pilote.pause()
        return pilote.app.screen

    _ecran, boite = au_refus(banc, monkeypatch, tmp_path,
                             preparation_qui_refuse(), suite=au_clavier)
    assert isinstance(boite["suite"], amont.EcranDeclaration)


# ===========================================================================
# 6. Ce que seul l'ECRAN MONTE mesure -- findings `F4`, `F5`, `F6` et `F10`
#
# **Le fil qui relie ces quatre volets, et c'est lui qu'il faut garder.** Trois
# des quatre mesures qu'ils remplacent ne passaient jamais par l'ecran monte :
# elles appliquaient elles-memes, dans le test, le calcul qu'elles pretendaient
# mesurer, si bien que la ligne de production sous test n'etait **jamais
# executee**. C'est la tautologie que la section 6.2 de
# `politique-revue-et-mutation-testing.md` nomme, et le depot en a compte dix
# variantes depuis la story 5.16. Le remede est le meme partout : monter
# l'ecran et mesurer ce qu'il rend.
# ===========================================================================

#: Les largeurs de fenetre mesurees. Le plancher d'`EPIC11-ARB-21` d'abord --
#: en dessous la TUI ne dessine plus --, puis une largeur ou le chemin designe
#: commence a tenir. Elles ne sont pas prises au hasard :
#: `test_la_RESERVE_du_curseur_MORD_a_la_LARGEUR_mesuree` verifie qu'au moins
#: l'une d'elles fait deborder la ligne du relink si la reserve saute.
LARGEURS_DE_FENETRE = (jetons.LARGEUR_PLANCHER, 90)

#: La trajectoire du curseur, frappe par frappe, et elle touche les TROIS
#: rangs : le milieu, la TETE, le retour, la QUEUE, puis la borne basse qu'un
#: `deplacer` fautif franchirait. Le curseur part sur `Annuler`
#: (`EPIC11-ARB-7`), donc une cible qui serait `Annuler` d'entree ne mesurerait
#: rien -- c'est pourquoi la premiere frappe s'en eloigne.
TRAJET_DU_CURSEUR = (
    ("up", ajout_de_rush.CLE_SEPARER),
    ("up", ajout_de_rush.CLE_RELINKER),
    ("down", ajout_de_rush.CLE_SEPARER),
    ("down", ajout_de_rush.CLE_ANNULER),
    ("down", ajout_de_rush.CLE_ANNULER),
)

#: Le dernier dossier du chemin designe, **derive du chemin** et jamais recopie
#: -- c'est le segment que `jetons.ajuster` mangerait en coupant par la fin, et
#: donc la queue que la ligne du relink doit garder.
DERNIER_DOSSIER_DESIGNE = (
    DOSSIER_DESIGNE.rstrip("\\").rsplit("\\", 1)[-1] + "\\")


def coque_du_refus(ecran, ascii_seul: bool = False) -> CoqueTui:
    """La pile du banc autour d'un `E2-1f` monte SEUL.

    Monter l'ecran a nu plutot que par le parcours complet de `E2-1` n'est pas
    un raccourci : c'est le seul moyen de choisir le CHEMIN DESIGNE, dont la
    longueur decide si la reserve de deux colonnes mord. Le parcours complet
    designe une video sous `tmp_path`, dont la longueur varie d'une machine a
    l'autre -- une mesure de geometrie posee dessus serait sensible au nom du
    dossier temporaire.
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter"), ecran],
                    contexte=Contexte("projet_demo"), ascii_seul=ascii_seul)


def lignes_peintes(ecran, widget: str = "issues") -> list[str]:
    """Le texte REELLEMENT peint par l'ecran, ligne a ligne, sans son style."""
    return jetons.texte_affiche(
        str(ecran.query_one(f"#{widget}").content)).split(chr(10))


def rang_du_glyphe(ecran) -> int | None:
    """Le rang de la ligne peinte qui porte le glyphe de curseur.

    C'est la moitie VISIBLE du curseur : le modele peut tenir un rang juste et
    l'ecran en surligner un autre. Rend `None` quand aucune ligne ne le porte
    -- un resultat, pas un echec, et il fait rougir l'egalite qui l'attend.
    """
    marque = jetons.glyphes(ecran.app.ascii_seul)["curseur"]
    rangs = [rang for rang, ligne in enumerate(lignes_peintes(ecran))
             if ligne.startswith(marque)]
    return rangs[0] if len(rangs) == 1 else None


def styles_par_ligne(peint) -> list[tuple[str, str | None]]:
    """Chaque ligne peinte avec SON style, `None` quand elle n'en porte pas.

    Lire `peint.spans` a plat ne dit pas QUELLE ligne est teintee : une
    peinture qui teindrait toujours le rang 0 rendrait la meme liste de styles
    qu'une peinture juste. On rapporte donc chaque intervalle a son rang, en
    comptant les separateurs que `jetons.peindre` intercale. Meme geste que
    `_styles_par_ligne` de `test_couleur_et_choix.py`, qui mesure la fonction
    ou celui-ci mesure l'ecran.
    """
    lignes = jetons.texte_affiche(str(peint)).split(chr(10))
    rang_du_debut, curseur = {}, 0
    for rang, ligne in enumerate(lignes):
        rang_du_debut[curseur] = rang
        curseur += len(ligne) + 1
    styles: list[str | None] = [None] * len(lignes)
    for portee in peint.spans:
        if portee.style:
            styles[rang_du_debut[portee.start]] = str(portee.style)
    return list(zip(lignes, styles))


@pytest.mark.parametrize("largeur_fenetre", LARGEURS_DE_FENETRE)
def test_le_RECOMPOSITION_des_suites_conserve_le_CURSEUR(banc,
                                                         largeur_fenetre):
    """Le curseur survit au rafraichi, et c'est mesure SUR L'ECRAN MONTE.

    Les libelles dependent de la largeur -- celui du relink porte un chemin --,
    donc les trois suites sont refaites a chaque dessin. Les refaire en
    laissant `ChoixExclusif.__post_init__` reposer le curseur ramenerait
    l'operateur sur `Annuler` au milieu de son geste.

    **Cette redaction remplace un test TAUTOLOGIQUE** (finding `F4`). La
    precedente exercait le modele pur et **reecrivait elle-meme**
    `refait.curseur = min(rang, len(refait.issues) - 1)`, c'est-a-dire la ligne
    exacte de `_recomposer_les_suites` qu'elle pretendait mesurer ; la methode
    n'etait jamais appelee, et sa suppression laissait 334 tests verts. Le
    regime reel, exhibe par sonde a travers l'ecran monte : les FLECHES SONT
    MORTES -- `on_key` fait `traiter` puis `rafraichir`, donc chaque frappe
    ramene le curseur sur `Annuler` avant meme d'etre dessinee.

    **Le parcours est celui du clavier, jusqu'au bout** : `pilote.press`, la
    ou les autres tests de ce banc appellent `traiter` a la main. C'est
    `on_key` qui enchaine les deux gestes, et c'est cet enchainement-la que le
    defaut habite.

    **La trajectoire est mesuree apres CHAQUE frappe**, pas seulement a la fin,
    et c'est ce qui la rend non degeneree : une cible qui coincide avec le
    curseur de depart serait verte meme si le report ne marchait pas. Elle
    touche les TROIS rangs -- la tete (`relinker`), le milieu (`separer`) et la
    queue (`annuler`) -- et repasse une fois sur la borne basse, qui ne doit
    pas deborder.
    """
    ecran = amont.EcranRefusDeConflit(refus_de_conflit(), DOSSIER_DESIGNE)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        trace = []
        for touche, _ in TRAJET_DU_CURSEUR:
            await pilote.press(touche)
            await pilote.pause()
            trace.append((ecran.choix.issues[ecran.choix.curseur].cle,
                          rang_du_glyphe(ecran)))
        return trace

    trace = banc(coque_du_refus(ecran), scenario, (largeur_fenetre, 24))
    rangs = [issue.cle for issue in ecran.choix.issues]
    attendu = [(cle, rangs.index(cle)) for _, cle in TRAJET_DU_CURSEUR]
    assert trace == attendu, (trace, attendu)


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("largeur_fenetre", LARGEURS_DE_FENETRE)
def test_la_ligne_d_une_ISSUE_ne_DEBORDE_pas_la_zone_utile(banc, ascii_seul,
                                                           largeur_fenetre):
    """La reserve du glyphe de curseur, mesuree SUR L'ECRAN MONTE.

    `ChoixExclusif.rendu` prefixe chaque libelle de deux colonnes. Le libelle
    du relink est calcule sur une largeur ; s'il la prenait entiere, la ligne
    ferait deux colonnes de trop et `jetons.ajuster` la couperait **par la
    fin** -- en mangeant `04_tournage_juin\\hd\\`, c'est-a-dire la seule chose
    que la note 4 d'Egan met la pour etre lue.

    **Cette redaction remplace un test TAUTOLOGIQUE** (finding `F5`). La
    precedente appliquait elle-meme `max(zone - amont.RESERVE_DU_CURSEUR, 0)`
    au modele et ne montait aucun ecran : elle epinglait la VALEUR de la
    constante, jamais son USAGE, si bien que remplacer
    `max(largeur - RESERVE_DU_CURSEUR, 0)` par `largeur` laissait 334 tests
    verts pendant que le mutant de controle sur la valeur, lui, mourait.

    **Trois volets, et le troisieme est celui qui nomme le defaut** :

    1. ce que l'ecran COMPOSE tient dans la zone utile de la fenetre reelle ;
    2. ce qu'il PEINT est identique a ce qu'il a compose -- `jetons.ajuster`
       n'a rien eu a rogner. Une ligne rognee tiendrait la mesure 1 tout en
       ayant perdu sa queue, et c'est exactement le mode de panne ;
    3. la ligne du relink finit sur le DERNIER DOSSIER du chemin designe, et
       jamais sur la marque d'abregement.

    **La mesure part du PLANCHER, et c'est un choix ecrit.** En dessous de
    `jetons.LARGEUR_PLANCHER` (`EPIC11-ARB-21`, 80 x 24) la TUI ne dessine plus
    ses ecrans -- `_assez_grand_au_dernier_dessin` les remplace par l'ecran
    « fenetre trop petite ». Mesurer a 40 colonnes mesurerait donc un regime
    que le produit n'a pas.
    """
    ecran = amont.EcranRefusDeConflit(refus_de_conflit(), DOSSIER_DESIGNE)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return (ecran.choix.rendu(ascii_seul=pilote.app.ascii_seul),
                lignes_peintes(ecran))

    composees, peintes = banc(coque_du_refus(ecran, ascii_seul), scenario,
                              (largeur_fenetre, 24))
    zone = jetons.largeur_utile(largeur_fenetre)
    for ligne in composees:
        assert jetons.colonnes(ligne) <= zone, (zone, ligne)
    assert peintes == composees, (peintes, composees)
    ligne_du_relink = peintes[[i.cle for i in ecran.choix.issues].index(
        ajout_de_rush.CLE_RELINKER)]
    queue = DERNIER_DOSSIER_DESIGNE
    assert ligne_du_relink.endswith(
        jetons.replier_ascii(queue) if ascii_seul else queue), ligne_du_relink
    assert not ligne_du_relink.endswith(
        jetons.points_d_abregement(ascii_seul)), ligne_du_relink


def test_la_RESERVE_du_curseur_MORD_a_la_LARGEUR_mesuree():
    """La fabrique est-elle assez longue pour que la reserve compte ?

    **Ce test ne mesure pas le produit, il mesure le BANC**, et c'est pourquoi
    il est le seul de ce lot a recomposer un calcul : sans lui, le volet
    ci-dessus serait vert a n'importe quelle largeur, y compris a une largeur
    ou le chemin designe tient si largement que deux colonnes de plus ne
    changent rien -- il ne mesurerait alors plus rien du tout. C'est le meme
    geste que `PLANCHER_DE_RENDUS` dans `test_maquettes_couleur_a_jour.py` :
    exclure la mesure degeneree.

    Mesure faite le 2026-09-05 sur les quatre regimes du volet : trois d'entre
    eux debordent sans la reserve (80/utf8, 90/utf8, 90/ascii), le quatrieme
    non (80/ascii, ou le repli ASCII raccourcit le chemin autrement). **Un
    seul suffit a tuer le mutant** ; on exige donc « au moins un », jamais
    « tous », pour ne pas figer une geometrie que la maquette peut bouger.
    """
    sensibles = []
    for largeur_fenetre in LARGEURS_DE_FENETRE:
        for ascii_seul in (False, True):
            zone = jetons.largeur_utile(largeur_fenetre)
            sans_reserve = fiche().suites(DOSSIER_DESIGNE, zone, ascii_seul)
            if any(jetons.colonnes(ligne) > zone
                   for ligne in sans_reserve.rendu(ascii_seul)):
                sensibles.append((largeur_fenetre, ascii_seul))
    assert sensibles, (
        "aucune largeur mesuree ne fait deborder la ligne du relink sans la "
        "reserve : le volet de debordement ne mesure plus rien. Allonger le "
        "chemin designe, ou descendre la largeur.")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_d_une_ISSUE_ne_DEBORDE_pas_le_MODELE_PUR(ascii_seul):
    """Le MODELE tient le budget qu'on lui donne, glyphe de curseur compris.

    **Ce que ce volet mesure vraiment, dit plutot que tu** (finding `F5`). Il
    portait le titre « la reserve du glyphe de curseur » et ne mesurait PAS la
    reserve : il l'appliquait lui-meme au modele, si bien que le produit
    pouvait cesser de l'appliquer sans qu'il rougisse. Le volet qui mesure la
    reserve est desormais
    `test_la_ligne_d_une_ISSUE_ne_DEBORDE_pas_la_zone_utile`, qui monte
    l'ecran ; celui-ci garde ce qu'il tenait reellement, et qui reste utile :
    `suites` respecte le budget qu'on lui passe, et `ChoixExclusif.rendu` n'y
    ajoute que les deux colonnes du glyphe -- ni trois, ni zero. C'est le
    contrat sur lequel l'appelant peut calculer sa reserve.

    **La mesure part du PLANCHER, et c'est un choix ecrit.** En dessous de
    `jetons.LARGEUR_PLANCHER` (`EPIC11-ARB-21`, 80 x 24) la TUI ne dessine plus
    ses ecrans -- `_assez_grand_au_dernier_dessin` les remplace par l'ecran
    « fenetre trop petite ». Mesurer a 40 colonnes mesurerait donc un regime
    que le produit n'a pas : le libelle de la sortie neuve fait 43 colonnes a
    lui seul, il ne tient a AUCUN calcul dans une zone de 40, et le seul
    remede -- l'abreger -- rendrait « C'est un autre rush, le déc… ». C'est un
    texte de maquette, pas un chemin : il s'abrege mal et on ne le retaille pas
    ici.
    """
    for zone in (jetons.largeur_utile(jetons.LARGEUR_PLANCHER), 90, 120):
        modele = fiche()
        choix = modele.suites(DOSSIER_DESIGNE,
                              max(zone - amont.RESERVE_DU_CURSEUR, 0),
                              ascii_seul)
        for ligne in choix.rendu(ascii_seul):
            assert jetons.colonnes(ligne) <= zone, (zone, ligne)


# ---------------------------------------------------------------------------
# `F6` -- l'ENTRELACEMENT de `relire` et `ecrire_le_relink`
# ---------------------------------------------------------------------------

#: Les trois rangs ou la CIBLE du relink est placee, et le rush TEMOIN qui
#: reste delinke a cote d'elle. Regle des fabriques, points 2 et 4 : la cible
#: passe par la TETE, le MILIEU et la QUEUE de la liste des rushes, et le
#: temoin est toujours a l'autre bout -- deux elements delinkes distinguables,
#: dont un seul doit changer d'etat. Un relink qui relierait toute la liste
#: serait vert sur une fabrique a une seule cible.
CIBLES_ET_TEMOIN = (
    pytest.param(voisin.RUSHES[0], voisin.RUSHES[-1], id="tete"),
    pytest.param(voisin.RUSHES[2], voisin.RUSHES[0], id="milieu"),
    pytest.param(voisin.RUSHES[-1], voisin.RUSHES[0], id="queue"),
)


def projet_aux_chemins_morts(tmp_path, morts) -> Path:
    """Le projet du banc voisin, prive des fichiers source de `morts`.

    **Rien n'est injecte** : le predicat de presence reste celui du coeur, et
    ce sont les fichiers eux-memes qui manquent. C'est ce que le finding `F6`
    exige -- un `existe=` statique indexe sur la chaine de chemin rend le
    statut d'une ligne independant du manifeste, donc rend la fraicheur d'une
    relecture invisible par construction.
    """
    dossier = voisin.projet(tmp_path)
    for rush_id in morts:
        (tmp_path / "sources" / f"{rush_id}.mov").unlink()
    return dossier


@pytest.mark.parametrize("cible, temoin", CIBLES_ET_TEMOIN)
def test_le_relink_ECRIT_avant_de_RELIRE_et_la_liste_le_MONTRE(
        tmp_path, banc, monkeypatch, cible, temoin):
    """L'ordre des deux gestes, mesure par ce que la liste AFFICHE ensuite.

    `_appliquer_l_apercu_de_relink` ecrit le manifeste **puis** le relit. Les
    intervertir laisse `rushes.ecrire_le_relink` faire son travail et la liste
    porter l'etat d'AVANT : l'ecran annonce « relink reussi », le manifeste est
    juste, et la ligne du rush reste peinte **absente**. C'est une panne qu'un
    operateur lit comme un echec de l'outil.

    **Pourquoi aucun banc ne le voyait** (finding `F6`, mutant d'entrelacement
    a 455 verts et 4 sautes). Tous injectaient un predicat de presence
    STATIQUE -- `existe=SANS_HIVER`, `SANS_LES_DEUX` --, indexe sur la chaine
    de chemin : le statut ne dependait alors pas du manifeste, et deux
    relectures encadrant l'ecriture rendaient forcement la meme chose. C'est
    **litteralement un defaut de fabrique**, de la meme famille que les trois
    de `CLAUDE.md` : une fabrique qui ne peut pas distinguer deux etats rend
    invisible toute erreur d'appariement entre eux.

    **Une frontiere de CONTENU est aveugle a l'ORDRE** (section 6.1 bis de la
    politique, appliquee ici a un autre canal) : le manifeste est juste dans
    les deux regimes, et c'est seulement la suite des evenements croisee avec
    ce que l'ecran montre qui les separe.
    """
    dossier = projet_aux_chemins_morts(tmp_path, (cible, temoin))

    async def relinker(pilote, ecran_du_refus):
        ecran_du_refus.choix.viser(ajout_de_rush.CLE_RELINKER)
        ecran_du_refus.traiter("enter")
        await pilote.pause()

    ecran, boite = au_refus(banc, monkeypatch, tmp_path,
                            preparation_qui_refuse(rush_id=cible),
                            dossier=dossier, suite=relinker)

    # Le manifeste, lui, est juste des DEUX cotes du mutant : il ne separe
    # rien, et c'est tout l'objet de ce volet.
    entrees = {entree["rush_id"]: entree["source_path"]
               for entree in json.loads(
                   (dossier / MANIFEST_FILENAME).read_text(
                       encoding="utf-8"))["rushes"]}
    assert Path(entrees[cible]).name == voisin.VIDEO_CIBLE, entrees[cible]

    # Ce que la liste MONTRE apres le geste : la cible liee, le temoin
    # toujours mort, les trois autres inchangees.
    statuts = {rush.rush_id: rush.statut for rush in ecran.liste.rushes}
    assert statuts[cible] == relink.LIE, (
        "la liste montre encore un rush ABSENT alors que le manifeste porte "
        f"l'ecriture : {statuts}")
    assert statuts[temoin] == relink.DELINKE_CHEMIN_MORT, statuts
    assert [rush_id for rush_id, statut in statuts.items()
            if statut != relink.LIE] == [temoin], statuts


def test_le_predicat_de_presence_du_BANC_est_celui_du_COEUR(tmp_path, banc,
                                                            monkeypatch):
    """Le volet symetrique : sans fichier mort, la mesure ci-dessus est nulle.

    **Ce test mesure le BANC, pas le produit.** Si `projet_aux_chemins_morts`
    cessait de tuer quoi que ce soit -- un renommage de la fabrique voisine
    suffirait --, le volet `F6` verrait `lie` partout, avant comme apres, et
    passerait au vert sans plus rien separer. C'est exactement la mesure
    degeneree que la politique demande d'exclure explicitement.
    """
    cible, temoin = voisin.RUSHES[2], voisin.RUSHES[0]
    dossier = projet_aux_chemins_morts(tmp_path, (cible, temoin))
    ecran, _boite = au_refus(banc, monkeypatch, tmp_path,
                             preparation_qui_refuse(rush_id=cible),
                             dossier=dossier)
    statuts = {rush.rush_id: rush.statut for rush in ecran.liste.rushes}
    assert statuts[cible] == relink.DELINKE_CHEMIN_MORT, statuts
    assert statuts[temoin] == relink.DELINKE_CHEMIN_MORT, statuts
    assert sorted(statuts.values()) != sorted(
        [relink.LIE] * len(statuts)), statuts


# ---------------------------------------------------------------------------
# `F10` -- QUELLE ligne du cartouche est peinte en `absent`
# ---------------------------------------------------------------------------

def test_SEULE_la_ligne_du_CODE_est_peinte_en_ABSENT(tmp_path, banc,
                                                     monkeypatch):
    """La couleur du cartouche, mesuree sur l'ecran monte et par le CONTENU.

    `FicheDeRefusDeConflit.etats_des_lignes` promet dans son docstring que
    « c'est une MESURE du rendu valide, pas une deduction » : `maquettes-couleur/`
    peint la ligne du code en `state-absent` et **toutes** les autres en texte
    ordinaire -- la phrase d'explication comme les quatre criteres, parce
    qu'une preuve peinte en rouge se lirait comme quatre erreurs. Aucune
    frontiere ne tenait cette promesse (finding `F10`) : deplacer l'etat du
    rang 0 au rang 1 laissait 384 tests verts, tout en peignant la PHRASE
    d'explication en rouge et en laissant le CODE en texte ordinaire --
    l'inverse exact de ce que la maquette couleur valide.

    **La ligne visee est reconnue par son CONTENU, jamais par son rang.** Un
    test qui asserterait « le rang 0 est teinte » recopierait le dictionnaire
    du produit et mourrait avec lui : c'est la tautologie qu'on ferme. On
    cherche donc la ligne qui porte le code derive du motif, et on exige
    qu'elle soit la SEULE teintee.
    """
    async def peinture(pilote, ecran_du_refus):
        return styles_par_ligne(ecran_du_refus.query_one("#chiffres").content)

    _ecran, boite = au_refus(banc, monkeypatch, tmp_path,
                             preparation_qui_refuse(), suite=peinture)
    dessus, peintes = boite["dessus"], boite["suite"]

    code = ajout_de_rush.code_de_refus(MOTIF_RUSH_DEJA_DECLARE)
    absent = jetons.couleur("state-absent")
    teintees = [ligne for ligne, style in peintes if style]
    portant_le_code = [ligne for ligne, _ in peintes if ligne.endswith(code)]
    assert len(portant_le_code) == 1, (code, peintes)
    assert teintees == portant_le_code, (
        "la couleur `absent` n'est pas sur la ligne du code : "
        f"{[(l, s) for l, s in peintes if s]}")
    assert [style for _, style in peintes if style] == [absent], peintes
    # Le volet symetrique, et il nomme le regime du mutant : la phrase
    # d'explication et les quatre criteres restent en texte ORDINAIRE.
    assert all(style is None for ligne, style in peintes
               if not ligne.endswith(code)), peintes
    assert isinstance(dessus, amont.EcranRefusDeConflit), type(dessus)


# ===========================================================================
# 6. `F1` -- l'ecran LIT les issues du refus, il ne les REDECIDE pas
#
# Le defaut, mesure au clavier par deux couches de revue independantes :
# `suites()` composait ses trois sorties sans jamais ouvrir `refus.issues`, si
# bien que le mecanisme d'`issue_de_remplacement` -- ecrit dans le coeur pour
# cesser de proposer `--force-distinct` la ou il ne change rien
# (`EPIC11-ARB-233`) -- s'arretait au coeur. Entree sur la seconde sortie :
# meme ecran, memes sorties, aucune information neuve. Boucle indefinie, et
# c'est le « blocage sec deguise » qu'`EPIC11-ARB-89` interdit.
#
# **Regle des fabriques sur la collection mesuree -- les trois issues.** Elles
# sont distinguables (trois cles, trois libelles, deux regimes d'ecriture) ; la
# cible du retrait est au MILIEU (rang 1) ; les deux BORDS -- le relink en tete,
# `Annuler` en queue -- sont mesures comme SURVIVANTS, ce qui est la forme que
# prend ici « une cible a chaque bord » : un retrait qui emporterait un bord
# ferait rougir. Et le rang remplace est vise aux trois positions possibles,
# pour qu'une fiche qui reagirait a un remplacement de rang 0 ou 2 se voie.
# ===========================================================================

#: Le texte que le coeur ECRIT a la place de la seconde issue. Produit, jamais
#: recopie -- voir :func:`issue_de_remplacement_du_coeur`.
REMPLACEMENT_DU_COEUR = issue_de_remplacement_du_coeur()

#: Les trois cles, dans l'ordre de la maquette. Fermee : elle sert de reference
#: d'egalite exacte, et l'ordre porte la recommandation (`EPIC11-ARB-231`).
CLES_NOMINALES = (ajout_de_rush.CLE_RELINKER,
                  ajout_de_rush.CLE_SEPARER,
                  ajout_de_rush.CLE_ANNULER)

#: Ce qu'il reste quand le coeur a retire la seconde : les deux BORDS.
CLES_SANS_SEPARATION = (ajout_de_rush.CLE_RELINKER,
                        ajout_de_rush.CLE_ANNULER)


def test_F1_le_texte_de_remplacement_du_coeur_est_bien_CELUI_DU_COEUR():
    """La fabrique de ce lot mesure-t-elle le produit, ou son idee du produit ?

    Sans ce test, `REMPLACEMENT_DU_COEUR` pourrait etre n'importe quelle chaine
    et toutes les frontieres qui suivent resteraient vertes. On verifie donc
    qu'il vient du regime qu'il pretend representer -- 99 rangs consommes -- et
    qu'il ne cite PLUS la commande que le refus cessait justement d'offrir.
    """
    assert "CONSOMMES" in REMPLACEMENT_DU_COEUR, REMPLACEMENT_DU_COEUR
    assert "mmu project add-rush" not in REMPLACEMENT_DU_COEUR
    assert "--force-distinct" not in REMPLACEMENT_DU_COEUR
    # Et il DIFFERE bien de l'entree de la table qu'il remplace, sans quoi le
    # remplacement serait un non-evenement et rien ne pourrait le detecter.
    defaut = ISSUES_PAR_MOTIF[MOTIF_RUSH_DEJA_DECLARE]
    assert REMPLACEMENT_DU_COEUR != defaut[1]
    assert "--force-distinct" in defaut[1], (
        "la table du coeur ne cite plus le drapeau au rang 1 : la cible du "
        "retrait a bouge, ce banc est a relire")


async def apres_avoir_TAPE_la_separation(pilote, ecran_du_refus):
    """Le geste que la revue a joue au clavier : viser la sortie neuve, valider.

    `viser` leve si la cle n'existe pas -- c'est voulu : un premier ecran qui
    n'offrirait deja plus la separation ferait rougir ici plutot que de rendre
    verts, par accident, les tests qui suivent.
    """
    ecran_du_refus.choix.viser(ajout_de_rush.CLE_SEPARER)
    ecran_du_refus.traiter("enter")
    await pilote.pause()
    return pilote.app.screen


def test_F1_le_SECOND_ecran_ne_repropose_plus_la_sortie_qui_ne_change_RIEN(
        tmp_path, banc, monkeypatch):
    """Le defaut vivant de `F1`, joue de bout en bout au CLAVIER.

    La traversee est exactement celle que deux couches de revue ont mesuree :
    `E2-1f` monte avec ses trois sorties, l'operateur tape la seconde, le coeur
    refuse a nouveau -- les 99 rangs sont consommes, le drapeau n'y peut rien --
    et `E2-1f` remonte. **Avant le correctif, il remontait IDENTIQUE** : memes
    trois sorties, aucune information neuve, et la sortie neuve toujours la,
    prete a etre tapee une troisieme fois. Boucle indefinie.

    Ce qui est mesure ici est le SECOND ecran, et par egalite exacte -- ce que
    la docstring de `suites_du_rush_deja_declare` exige deja pour ces issues :
    une appartenance ne verrait ni une permutation ni une sortie de trop.

    Les deux BORDS survivent au retrait, et c'est la forme que prend ici « une
    cible a chaque bord » : le relink ouvre, `Annuler` ferme, seul le MILIEU
    tombe. Un retrait qui emporterait un bord laisserait un ecran sans relink,
    ou sans issue qui n'ecrit pas -- que `ChoixExclusif` refuse de monter.
    """
    preparer = preparation_qui_refuse(
        issue_de_remplacement=REMPLACEMENT_DU_COEUR)
    _ecran, boite = au_refus(banc, monkeypatch, tmp_path, preparer,
                             suite=apres_avoir_TAPE_la_separation)
    premier, second = boite["dessus"], boite["suite"]

    # Le PREMIER ecran offre bien les trois : sans ce volet, un ecran qui n'en
    # offrirait jamais que deux passerait pour un correctif.
    assert tuple(i.cle for i in premier.choix.issues) == CLES_NOMINALES

    # Le coeur a bien refuse une seconde fois -- c'est le regime, pas un echec.
    assert [force for _c, force in preparer.vues] == [False, True], (
        preparer.vues)
    assert isinstance(second, amont.EcranRefusDeConflit), type(second)
    assert second is not premier

    # Et le second n'offre plus ce que le coeur vient de retirer.
    rendues = tuple(issue.cle for issue in second.choix.issues)
    assert rendues == CLES_SANS_SEPARATION, rendues
    assert ajout_de_rush.CLE_SEPARER not in rendues
    # Rien n'a ete ecrit sur tout le parcours : deux refus, zero octet.
    assert ecrans.empreinte_du_manifeste(
        boite["dossier"]) == boite["avant"]


def test_F1_volet_SYMETRIQUE_quand_le_coeur_n_a_RIEN_retire_la_sortie_reste(
        tmp_path, banc, monkeypatch):
    """Sans lui, une fiche qui ne rendrait JAMAIS la sortie neuve serait verte.

    C'est le correctif le plus simple et le plus faux : retirer la sortie
    toujours. Ce volet le fait rougir en jouant le regime ordinaire -- le
    drapeau CHANGE quelque chose, la separation aboutit, et le panneau chiffre
    de `E2-1e` prend la suite (`EPIC11-ARB-4` : aucune ecriture avant lui).
    """
    preparer = preparation_qui_refuse()
    _ecran, boite = au_refus(banc, monkeypatch, tmp_path, preparer,
                             suite=apres_avoir_TAPE_la_separation)
    assert tuple(i.cle for i in boite["dessus"].choix.issues) == CLES_NOMINALES
    assert isinstance(boite["suite"], amont.EcranDeclaration), type(
        boite["suite"])
    assert [force for _c, force in preparer.vues] == [False, True]


@pytest.mark.parametrize("rang", (0, 1))
def test_F1_la_BOUCLE_est_fermee_le_CLAVIER_ne_pose_plus_force_distinct(
        rang, tmp_path, banc, monkeypatch):
    """La frontiere NEGATIVE de `F1`, et c'est la seule qui voit une boucle.

    Une frontiere de contenu -- « la sortie neuve n'est plus dans la liste » --
    dit ce que l'ecran montre. Elle ne dit pas ce qu'un operateur peut
    DECLENCHER. Celle-ci parcourt le choix au clavier et valide a chaque rang,
    puis relit ce que le temps 1 a recu : `force_distinct` n'y est jamais pose.
    Avant le correctif, le rang du milieu le posait, le coeur refusait a
    nouveau, et le meme ecran remontait -- indefiniment.

    Les deux rangs joues sont les deux BORDS de ce qui reste (il n'en reste que
    deux), et le cardinal est verifie pour qu'un `parametrize` tronque se voie :
    retirer une entree joue une cible de moins sans faire rougir personne.
    """
    preparer = preparation_qui_refuse(
        issue_de_remplacement=REMPLACEMENT_DU_COEUR)

    async def au_rang(pilote, ecran_du_refus):
        second = await apres_avoir_TAPE_la_separation(pilote, ecran_du_refus)
        # Remonter en tete par les FLECHES, puis descendre au rang vise : le
        # curseur ne se pose pas a la main, c'est le geste de l'operateur.
        for _ in second.choix.issues:
            second.traiter("up")
        for _ in range(rang):
            second.traiter("down")
        vise = second.choix.issues[second.choix.curseur].cle
        second.traiter("enter")
        await pilote.pause()
        return vise, len(second.choix.issues)

    _ecran, boite = au_refus(banc, monkeypatch, tmp_path, preparer,
                             suite=au_rang)
    vise, cardinal = boite["suite"]
    assert cardinal == len(CLES_SANS_SEPARATION), (
        "le cardinal des issues du second ecran a change : ce parametrize ne "
        f"couvre plus tous les rangs, il en joue 2 sur {cardinal}")
    assert vise == CLES_SANS_SEPARATION[rang], vise
    assert [force for _cible, force in preparer.vues] == [False, True], (
        "le clavier a repose force_distinct une SECONDE fois sur un refus que "
        f"le forcage ne leve pas : c'est la boucle de F1. Vues : "
        f"{preparer.vues}")


def test_F1_a_DEUX_issues_le_CURSEUR_reste_sur_celle_qui_n_ecrit_PAS(
        tmp_path, banc, monkeypatch):
    """`EPIC11-ARB-7` sous la forme d'`EPIC11-ARB-45`, dans le regime NEUF.

    Le retrait fait passer l'ecran de trois issues a deux, et c'est un regime
    qu'aucun banc n'avait : une ecriture atteignable en UNE frappe depuis le
    montage serait exactement l'accident que `ARB-7` existe pour empecher --
    et il compte double ici, l'issue qui reste au-dessus etant le relink, qui
    repointe un rush.

    Rien n'est pose a la main -- ni le curseur, ni le rang du relink :
    `ChoixExclusif.__post_init__` s'en charge, et c'est lui qu'on mesure. Le
    choix lu est celui du SECOND ecran, celui que `rafraichir` a recompose a la
    largeur reelle : un curseur repose au montage et perdu a la recomposition
    ne se verrait pas sur le modele seul (`F4`).
    """
    _ecran, boite = au_refus(
        banc, monkeypatch, tmp_path,
        preparation_qui_refuse(issue_de_remplacement=REMPLACEMENT_DU_COEUR),
        suite=apres_avoir_TAPE_la_separation)
    choix = boite["suite"].choix
    assert len(choix.issues) == len(CLES_SANS_SEPARATION)
    assert choix.retenue is None, "aucune issue n'est preselectionnee"
    assert choix.issues[choix.curseur].cle == ajout_de_rush.CLE_ANNULER
    assert choix.issues[choix.curseur].ecrit is False
    assert choix.action_qui_ecrit.cle == ajout_de_rush.CLE_RELINKER
    assert sum(1 for issue in choix.issues if issue.ecrit) == 1


@pytest.mark.parametrize("remplacement, attendu", [
    (None, ETAT_DESSINE),
    (REMPLACEMENT_DU_COEUR, "2 issues, 1 écrit"),
], ids=("le_coeur_offre_les_trois", "le_coeur_a_retire_la_seconde"))
def test_F1_la_ligne_d_ETAT_de_l_ecran_MONTE_recompte_et_ACCORDE(
        remplacement, attendu, tmp_path, banc, monkeypatch):
    """`EPIC11-ARB-56` : la ligne d'etat porte une MESURE, pas une phrase.

    C'est la panne exacte qu'`EPIC11-ARB-231` avait produite cote maquette --
    l'ecran gagne une sortie, la ligne d'etat continue d'en annoncer deux, et
    personne ne rougit. Le retrait de `F1` la rejoue par l'autre bout : l'ecran
    PERD une sortie.

    **Le texte est relu sur l'ecran, pas recalcule ici** : `_etat_courant` est
    ce que `rafraichir` a POSE. Le recomposer dans le test serait la tautologie
    que `F4` reproche a ce meme banc -- un test qui reecrit la ligne qu'il
    pretend mesurer.

    L'accord du verbe est mesure des deux cotes, et par une frontiere negative :
    `1 écrivent` se lirait comme une faute de frappe, et une relecture ne le
    rattrape pas plus qu'elle n'a rattrape le cardinal perime.

    L'ecran lu est celui ou le regime vit : le PREMIER quand le coeur n'a rien
    retire, le SECOND -- apres la frappe -- quand il a retire.
    """
    _ecran, boite = au_refus(
        banc, monkeypatch, tmp_path,
        preparation_qui_refuse(issue_de_remplacement=remplacement),
        suite=None if remplacement is None else apres_avoir_TAPE_la_separation)
    mesure = boite["dessus"] if remplacement is None else boite["suite"]
    pose = mesure._etat_courant
    assert attendu in pose, pose
    perime = ETAT_DESSINE if remplacement else "2 issues, 1 écrit"
    assert perime not in pose, pose
    assert "1 écrivent" not in pose, pose
    assert "2 écrit·" not in pose and "2 écrit " not in pose, pose


@pytest.mark.parametrize("rang_remplace, offerte", [
    (0, True),    # le BORD de tete : le coeur n'y touche jamais
    (1, False),   # le seul rang que le coeur remplace
    (2, True),    # le BORD de queue
])
def test_F1_seul_le_RANG_1_retire_la_separation(rang_remplace, offerte):
    """La cible aux trois positions de la liste d'issues du coeur.

    Le coeur remplace le rang 1 et lui seul -- c'est ce que
    `_refus_de_rush_deja_declare` compose. Une fiche qui reagirait a un
    remplacement quelconque retirerait la sortie neuve d'un refus qui l'offre
    encore, et une fiche qui comparerait la liste ENTIERE la retirerait sur le
    moindre ajustement de libelle des deux autres.

    Les trois cas sont joues, tete et queue comprises : une comparaison
    positionnelle fausse ne se demasque pas autrement.
    """
    modele = fiche(issue_de_remplacement=REMPLACEMENT_DU_COEUR,
                   rang_remplace=rang_remplace)
    assert modele.separation_offerte() is offerte
    cles = [issue.cle for issue in modele.suites(DOSSIER_DESIGNE).issues]
    assert (ajout_de_rush.CLE_SEPARER in cles) is offerte, cles


def test_F1_un_refus_SANS_liste_d_issues_garde_les_TROIS_sorties():
    """Le repli, et il va dans le sens de l'offre plutot que du retrait.

    Un banc qui substitue le coeur peut construire un refus sans issues -- la
    signature le permet depuis `EPIC11-ARB-148`. Un silence ne dit pas que le
    coeur a retire quoi que ce soit ; le retirer la-dessus serait le REDECIDER,
    c'est-a-dire le defaut que `F1` reproche par son autre bout.

    Trois replis, tous mesures : pas d'issues, un motif etranger a la table, et
    un attribut absent.
    """
    for refus in (refus_de_conflit(), refus_de_conflit()):
        refus.issues = ()
        assert ajout_de_rush.FicheDeRefusDeConflit(
            refus).separation_offerte() is True
    orphelin = refus_de_conflit()
    orphelin.motif = "motif_qui_n_existe_pas"
    assert ajout_de_rush.FicheDeRefusDeConflit(
        orphelin).separation_offerte() is True

    class RefusNu:
        motif = MOTIF_RUSH_DEJA_DECLARE

    assert ajout_de_rush.FicheDeRefusDeConflit(
        RefusNu()).separation_offerte() is True


def refus_reel_du_coeur(tmp_path, dernier_rang: int, *, force_distinct: bool):
    """Le refus que le VRAI coeur leve sur un projet a `dernier_rang` homonymes.

    La famille est posee **en QUEUE** de `rushes[]` -- le pire rang pour un
    balayage tronque --, et la fabrique est celle du banc du rang d'homonymie,
    reutilisee plutot que recopiee : deux projets de synthese qui divergeraient
    feraient mesurer deux produits.
    """
    projet = tmp_path / "projet"
    chemin = rangs.manifeste(
        projet, rangs.rushes_de(tuple(range(1, dernier_rang + 1)), "queue"))
    avant = rangs.rushes_du_manifeste(chemin)
    video = rangs.copie_du_rush(tmp_path / "trop_tard" / "hd", "prise01.mp4")
    try:
        preparer_une_declaration(project_dir=projet, video_path=video,
                                 logger=rangs.JournalMuet(),
                                 force_distinct=force_distinct)
        refus = None
    except RefusDeDeclaration as leve:
        refus = leve
    # Rien n'a ete ecrit : preparer ne touche aucun octet (AC 3.3).
    assert rangs.rushes_du_manifeste(chemin) == avant
    return refus, video


@pytest.mark.skipif(shutil.which("ffprobe") is None,
                    reason="ffprobe absent du PATH")
def test_F1_TERRAIN_le_VRAI_coeur_retire_la_sortie_au_SECOND_refus(tmp_path):
    """Le vrai coeur, le vrai `ffprobe`, le vrai rush -- et l'ecran au bout.

    `CLAUDE.md` : « une mesure de synthese mesure la synthese ; elle ne devient
    une mesure du produit que confrontee a un artefact de terrain ». Les doubles
    de la section 6 reproduisent le geste du coeur ; celui-ci ne reproduit rien
    -- et c'est lui qui etablit que le regime a **deux temps**, ce qu'aucun
    double n'aurait pu prouver :

    * sans drapeau, le coeur refuse avec sa table PLEINE. Il n'a pas encore
      cherche de rang libre, donc il ignore qu'il n'y en a plus, donc l'ecran
      offre bien ses trois sorties -- y compris celle qui ne changera rien ;
    * sous `force_distinct=True`, la recherche de rang echoue, et c'est LA que
      le coeur remplace sa seconde issue. C'est le second `E2-1f`, celui ou
      l'operateur bouclait.

    Les deux moities sont mesurees ici, sur le meme projet et le meme fichier.
    """
    rangs.exiger_le_media(rangs.RUSH_REEL)
    plein = rangs.naming.VERSION_RANK_MAX

    premier, video = refus_reel_du_coeur(tmp_path / "un", plein,
                                         force_distinct=False)
    assert premier is not None and premier.motif == MOTIF_RUSH_DEJA_DECLARE
    fiche_1 = ajout_de_rush.FicheDeRefusDeConflit(premier)
    assert fiche_1.separation_offerte() is True
    choix_1 = fiche_1.suites(str(video.parent) + "/", 76)
    assert [i.cle for i in choix_1.issues] == list(CLES_NOMINALES)
    assert ETAT_DESSINE in fiche_1.etat(choix_1)

    second, video = refus_reel_du_coeur(tmp_path / "deux", plein,
                                        force_distinct=True)
    assert second is not None and second.motif == MOTIF_RUSH_DEJA_DECLARE
    fiche_2 = ajout_de_rush.FicheDeRefusDeConflit(second)
    assert fiche_2.separation_offerte() is False
    choix_2 = fiche_2.suites(str(video.parent) + "/", 76)
    assert [i.cle for i in choix_2.issues] == list(CLES_SANS_SEPARATION)
    assert ajout_de_rush.CLE_SEPARER not in [i.cle for i in choix_2.issues]
    assert "2 issues, 1 écrit" in fiche_2.etat(choix_2)


@pytest.mark.skipif(shutil.which("ffprobe") is None,
                    reason="ffprobe absent du PATH")
def test_F1_TERRAIN_volet_SYMETRIQUE_a_98_rangs_le_forcage_ABOUTIT(tmp_path):
    """Un rang de moins, et le drapeau change de nouveau quelque chose.

    Sans ce volet, le test precedent serait vert sur un coeur qui refuserait
    TOUJOURS sous forcage -- et l'ecran aurait raison de ne plus jamais offrir
    la separation. C'est la borne haute du domaine prise par son autre bout :
    la 99e place est libre, la declaration passe, aucun refus a montrer.
    """
    rangs.exiger_le_media(rangs.RUSH_REEL)
    refus, _video = refus_reel_du_coeur(
        tmp_path, rangs.naming.VERSION_RANK_MAX - 1, force_distinct=True)
    assert refus is None, (
        "a 98 rangs le forcage doit aboutir : si le coeur refuse ici, le "
        "regime de F1 n'est plus borne par l'epuisement")


# ===========================================================================
# 7. `F16` -- l'inventaire des criteres absents NOMME ce que le cartouche OMET
#
# `EPIC11-ARB-237` (Egan, 2026-09-05) : un critere d'identite non mesurable
# s'OMET du cartouche. La position etant desormais tenue plutot que subie,
# `criteres_absents()` doit nommer **exactement** l'ensemble omis -- et elle
# sous-declarait : l'inventaire testait `is None`, le rendu la VERACITE.
#
# **Regle des fabriques, sur les quatre criteres.** Les quatre valeurs sont
# d'especes differentes et aucune n'est un remplissage uniforme ; la cible est
# jouee aux QUATRE positions, donc a la TETE (`Nom du fichier`) et a la QUEUE
# (`Timecode initial`) autant qu'au milieu -- un balayage tronque des deux cotes
# se voit. Le rang du milieu porte en plus le cas INVERSE (une valeur fausse au
# champ, VRAIE au rendu), sans lequel une frontiere qui lirait les champs bruts
# au lieu du rendu resterait verte.
# ===========================================================================

#: Comment rendre FAUSSE la valeur d'un critere, et ce que le cartouche en fait.
#:
#: Les trois valeurs vides passent par la preuve (`criteres.declares`) plutot
#: que par l'entree : `CriteresIdentiteRush.declares` normalise `""` en `None`,
#: donc l'ecart de `F16` est LATENT dans le produit d'aujourd'hui -- c'est
#: pourquoi la revue le classe en tolerance documentee et non en defaut vivant.
#: Il n'en est pas moins un contrat rompu : `CriteresIdentiteRush` est une
#: dataclasse publique sans validation, et la docstring de la fiche pose
#: nommement le cas d'« un banc qui substitue le coeur ».
CRITERES_FAUX = {
    # TETE -- l'entree, seul champ que la fiche lit hors de la preuve.
    ajout_de_rush.LIBELLE_NOM: ({"source_name": ""}, None, True),
    # Le cas INVERSE : le champ est faux (`0`), le rendu ne l'est pas.
    ajout_de_rush.LIBELLE_DUREE_SOURCE: (None, {"source_frame_count": 0},
                                         False),
    ajout_de_rush.LIBELLE_BASE_DE_TIMECODE: (None, {"fps_source_exact": ""},
                                             True),
    # QUEUE -- le seul champ ou une valeur FAUSSE n'est pas `None`, et donc le
    # seul qui separe les deux questions. C'est le regime que `F16` nomme.
    ajout_de_rush.LIBELLE_TIMECODE_INITIAL: (None,
                                             {"source_start_timecode": ""},
                                             True),
}


def fiche_au_critere_FAUX(libelle: str) -> ajout_de_rush.FicheDeRefusDeConflit:
    """La fiche dont UN critere porte une valeur fausse, les trois autres pleines."""
    dans_l_entree, dans_la_preuve, _omis = CRITERES_FAUX[libelle]
    entree = dict(ENTREE_BLOQUANTE, **(dans_l_entree or {}))
    refus = refus_de_conflit(entree=entree)
    if dans_la_preuve is not None:
        refus.criteres = dataclasses.replace(
            refus.criteres,
            declares=dataclasses.replace(refus.criteres.declares,
                                         **dans_la_preuve))
    return ajout_de_rush.FicheDeRefusDeConflit(refus)


def libelles_DESSINES(modele, largeur: int = LARGEUR_DESSINEE) -> set[str]:
    """Les libelles que le cartouche DESSINE vraiment, relus sur ses lignes.

    Relus plutot que deduits : deduire les libelles dessines de la meme liste
    qui les produit serait la tautologie que `F4` reproche a ce banc.
    """
    lignes = modele.lignes_des_criteres(largeur)
    return {libelle for libelle in LIBELLES_DES_CRITERES
            if any(ligne.startswith(libelle) for ligne in lignes)}


@pytest.mark.parametrize("libelle", LIBELLES_DES_CRITERES)
def test_F16_criteres_absents_nomme_EXACTEMENT_ce_que_le_cartouche_OMET(
        libelle):
    """La complementarite, et c'est elle la frontiere -- pas un cas particulier.

    `criteres_absents()` et `lignes_des_criteres()` partitionnent les quatre
    criteres : tout ce qui n'est pas dessine est nomme absent, tout ce qui est
    nomme absent n'est pas dessine, ni recouvrement ni oubli. Une egalite
    d'ensembles le dit d'un coup et **ne peut pas** rester verte sur un
    balayage tronque -- l'union cesserait d'etre complete.

    Le verdict attendu par critere est ecrit dans :data:`CRITERES_FAUX` plutot
    que deduit du produit : un test qui recalculerait l'omission comme le
    produit la calcule mesurerait sa propre copie.
    """
    _entree, _preuve, omis = CRITERES_FAUX[libelle]
    modele = fiche_au_critere_FAUX(libelle)
    absents = set(modele.criteres_absents())
    dessines = libelles_DESSINES(modele)

    assert (libelle in absents) is omis, (libelle, absents)
    assert (libelle not in dessines) is omis, (libelle, dessines)
    # La partition, sur les QUATRE : ni recouvrement, ni oubli.
    assert absents | dessines == set(LIBELLES_DES_CRITERES), (
        absents, dessines)
    assert not (absents & dessines), absents & dessines
    # Volet symetrique : les trois autres criteres sont intacts.
    assert len(absents) == (1 if omis else 0), absents


def test_F16_le_volet_NOMINAL_ne_nomme_RIEN_et_dessine_les_QUATRE():
    """Sans lui, une methode qui nommerait tout serait verte au test precedent.

    C'est le second bord de la complementarite : la partition doit tenir aussi
    quand l'ensemble omis est VIDE.
    """
    modele = fiche()
    assert modele.criteres_absents() == ()
    assert libelles_DESSINES(modele) == set(LIBELLES_DES_CRITERES)


def test_F16_sur_l_ecran_MONTE_la_ligne_ABSENTE_manque_et_est_NOMMEE(
        tmp_path, banc, monkeypatch):
    """La meme partition, relue sur la fiche que l'ECRAN porte.

    Le modele est pur, mais c'est l'ecran qui le monte, et `F4`/`F5` disent le
    prix d'une frontiere qui ne passe jamais par la : deux tests de ce banc
    sont tautologiques pour cette raison exacte. Ici, la fiche mesuree est
    celle qu'`EcranRefusDeConflit.__init__` a construite, et les lignes lues
    sont celles que `rafraichir` a dessinees.
    """
    timecode_vide = dict(ENTREE_BLOQUANTE, source_start_timecode="")

    def preparer(cible: Path, *, force_distinct: bool = False):
        refus = refus_de_conflit(
            entree=dict(timecode_vide, rush_id=RUSH_BLOQUANT,
                        source_name=Path(cible).name),
            source_name=Path(cible).name, rush_id=RUSH_BLOQUANT)
        # `declares` normalise `""` en `None` ; on repose la valeur FAUSSE sur
        # la preuve, la ou la fiche la lit.
        refus.criteres = dataclasses.replace(
            refus.criteres,
            declares=dataclasses.replace(refus.criteres.declares,
                                         source_start_timecode=""))
        raise refus

    _ecran, boite = au_refus(banc, monkeypatch, tmp_path, preparer)
    modele = boite["dessus"].fiche
    lignes = modele.lignes(LARGEUR_DESSINEE)
    rendu = "\n".join(lignes)
    assert ajout_de_rush.LIBELLE_TIMECODE_INITIAL not in rendu, rendu
    assert modele.criteres_absents() == (
        ajout_de_rush.LIBELLE_TIMECODE_INITIAL,), modele.criteres_absents()
    # Les trois autres criteres sont bien la : l'omission est etroite.
    for libelle in (ajout_de_rush.LIBELLE_NOM,
                    ajout_de_rush.LIBELLE_DUREE_SOURCE,
                    ajout_de_rush.LIBELLE_BASE_DE_TIMECODE):
        assert libelle in rendu, (libelle, rendu)


# ===========================================================================
# Les deux maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E2-1e` et `E2-1f` par
# leur code, et une de ses docstrings annonce meme « `plan séquence 12.mov ·
# refusé`, **verbatim de la maquette** » -- sans qu'aucun dessin soit ouvert.
# Huit de ses valeurs en etaient recopiees, sur une douzaine de sites. Le
# depot connait le geste juste et le pratique ailleurs
# (`test_atelier_scan_rapport.py` lit `E3-3` et `E3-4` a leur source).
#
# Les valeurs confrontees sont celles de `ENTREE_BLOQUANTE` et des lignes que
# le produit compose (`texte_de_la_duree`, `etat`), pas des litteraux poses a
# cote : chacune est desormais une constante nommee employee AUSSI par les
# sites d'assertion, ce qui empeche la mesure de diverger de l'emploi.

#: Les deux maquettes, a leur source.
MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


#: Les deux dessins et ce que chacun porte EN PROPRE. `E2-1e` est la
#: confirmation (rien n'est encore ecrit), `E2-1f` le refus : deux etats
#: distinguables du meme rush, et c'est ce qui rend une permutation visible.
DESSINS_DE_LA_DECLARATION = [
    ("E2-1e", "E2-1e-declaration-confirmation.txt",
     (DUREE_SOURCE_DESSINEE, "00:00:04:12")),
    ("E2-1f", "E2-1f-declaration-rush-deja-declare.txt",
     (DUREE_SOURCE_DESSINEE, ETAT_DESSINE, "00:00:04:12")),
]


@pytest.mark.parametrize(("code", "fichier", "propres"),
                         DESSINS_DE_LA_DECLARATION,
                         ids=[c for c, _, _ in DESSINS_DE_LA_DECLARATION])
def test_les_valeurs_de_la_declaration_sont_VERBATIM_de_leur_maquette(
        code, fichier, propres):
    """Chaque valeur est DANS le dessin, lu sur disque a ce tour-ci.

    Le nom et le cardinal sont communs aux deux ecrans -- c'est le meme rush
    vu deux fois --, le reste est propre a chacun.
    """
    dessin = dessin_de_la_maquette(fichier)
    for attendu in (NOM_DESSINE, CARDINAL_DESSINE) + tuple(propres):
        assert attendu in dessin, (code, attendu)


def test_le_rush_de_la_FABRIQUE_est_celui_que_les_deux_dessins_montrent():
    """`ENTREE_BLOQUANTE` n'invente pas son rush : elle reprend le dessine.

    C'est le point qui fait tenir tout le reste du fichier. Une fabrique dont
    le rush ne serait pas celui du dessin mesurerait un ecran que personne n'a
    approuve, et les douze sites qui en tirent leurs attendus mentiraient
    ensemble, sans qu'aucun ne rougisse.
    """
    for _, fichier, _ in DESSINS_DE_LA_DECLARATION:
        dessin = dessin_de_la_maquette(fichier)
        assert ENTREE_BLOQUANTE["source_name"] in dessin
        assert ENTREE_BLOQUANTE["source_start_timecode"] in dessin
        assert ENTREE_BLOQUANTE["source_path"].endswith(NOM_DESSINE)
    # Le cardinal du dessin est celui de la fabrique, a l'espace de milliers
    # pres -- que le dessin pose et que le manifeste ne connait pas.
    chiffres = "".join(c for c in CARDINAL_DESSINE if c.isdigit())
    assert chiffres == str(ENTREE_BLOQUANTE["source_frame_count"])


def test_l_ETAT_du_refus_n_est_dessine_que_par_E2_1f():
    """Le volet symetrique : la confirmation ne porte AUCUN refus.

    Sans lui, une valeur presente dans les deux dessins rendrait la table
    verte en confondant l'ecran qui ecrit et celui qui refuse -- c'est-a-dire
    exactement la distinction que ces deux maquettes existent pour porter.
    """
    confirmation = dessin_de_la_maquette("E2-1e-declaration-confirmation.txt")
    refus = dessin_de_la_maquette("E2-1f-declaration-rush-deja-declare.txt")
    assert ETAT_DESSINE in refus
    assert ETAT_DESSINE not in confirmation
    assert "refusé" in refus and "refusé" not in confirmation
    assert "rien n'a encore été écrit" in confirmation
    assert "rien n'a encore été écrit" not in refus


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : le pli absorbe la mise en page, PAS un ecart.

    Quatre contre-exemples, dont trois a un chiffre ou un mot pres.
    """
    refus = dessin_de_la_maquette("E2-1f-declaration-rush-deja-declare.txt")
    assert "6 301 frames · 4:12" not in refus
    assert "3 issues, 3 écrivent" not in refus
    assert "plan séquence 13.mov" not in refus
    assert "00:00:04:13" not in refus


# ===========================================================================
# `E2-1j` -- la ligne d'explication des rangs d'homonyme epuises
# ===========================================================================
#
# **La moitie non codee d'un arbitrage tranche, mesuree le 2026-09-06.**
# `EPIC11-ARB-239` (Egan, 2026-09-05) tranche : quand les 99 rangs d'homonyme
# sont pris, la sortie « le declarer separement » s'efface et **une ligne
# d'explication** prend sa place -- pas une quatrieme sortie. Le lot de `F1`
# avait code la moitie qui RETIRE (`separation_offerte`, fermee par mutants) ;
# la moitie qui AJOUTE n'existait nulle part -- un grep du litteral dessine
# rendait zero dans `src/`. Le dessin, lui, etait valide depuis la veille.
#
# C'est le defaut symetrique de celui que ce banc mesure plus haut : la, un
# banc citait un dessin sans le lire ; ici, un dessin valide n'etait pas lu du
# tout.

#: Le dessin de `E2-1j`, second etat de `E2-1f` -- pas un ecran de plus.
MAQUETTE_RANGS_EPUISES = "E2-1j-declaration-rangs-epuises.txt"


def refus_aux_rangs_epuises() -> RefusDeDeclaration:
    """Le refus du regime `E2-1j`, avec l'issue que le COEUR met a la place.

    Le texte de remplacement est **produit** par le coeur
    (:func:`issue_de_remplacement_du_coeur`), jamais une sentinelle : une
    chaine posee ici rendrait ce banc vert le jour ou le coeur cesserait de
    remplacer quoi que ce soit.
    """
    return refus_de_conflit(
        issue_de_remplacement=issue_de_remplacement_du_coeur())


def zone_centrale(pilote) -> list[tuple[str | None, list[str]]]:
    """Ce que la zone centrale AFFICHE, widget par widget.

    Les widgets retires de la mise en page (`display = False`) sont **omis**,
    et c'est tout l'interet : le cardinal des lignes rendues ici est celui que
    l'operateur voit, pas celui des widgets construits.
    """
    rendus = []
    for widget in pilote.app.screen.query_one("#centre").children:
        if not widget.display:
            continue
        contenu = jetons.texte_affiche(str(getattr(widget, "content", "")))
        rendus.append((widget.id, contenu.split("\n")))
    return rendus


def test_la_LIGNE_de_E2_1j_est_verbatim_de_son_dessin():
    """La phrase FORMATEE est dans le dessin valide, lu sur disque a ce tour.

    Formatee, et non recopiee : le nombre vient de
    :func:`~mixed_media_utility.io.version_ranks.cardinal_des_homonymes`. Un
    deplacement de la borne fait donc rougir **ici**, ce qui est juste -- il
    faudrait regenerer le dessin.
    """
    dessin = dessin_de_la_maquette(MAQUETTE_RANGS_EPUISES)
    assert ajout_de_rush.phrase_des_rangs_epuises() in dessin


def test_la_ligne_de_E2_1j_n_est_PAS_dessinee_par_E2_1f():
    """Le volet symetrique, sans lequel la mesure ci-dessus ne distingue rien.

    Une phrase presente dans les deux dessins rendrait la confrontation verte
    en confondant l'etat ordinaire et l'etat epuise -- exactement le defaut
    que `test_l_ETAT_du_refus_n_est_dessine_que_par_E2_1f` ferme plus haut sur
    l'autre couple.
    """
    ordinaire = dessin_de_la_maquette(MAQUETTE)
    assert ajout_de_rush.phrase_des_rangs_epuises() not in ordinaire
    # Et la reciproque : la suite que `E2-1j` retire est dessinee par `E2-1f`
    # et par lui seul.
    epuise = dessin_de_la_maquette(MAQUETTE_RANGS_EPUISES)
    assert ajout_de_rush.LIBELLE_SEPARER in ordinaire
    assert ajout_de_rush.LIBELLE_SEPARER not in epuise


def test_la_BORNE_de_la_phrase_vient_du_COEUR_et_n_est_pas_un_99_recopie():
    """Frontiere ANTI-TAUTOLOGIE : la phrase SUIT la borne.

    Sans elle, `PHRASE_DES_RANGS_D_HOMONYME_EPUISES` pourrait porter un `99`
    en dur et les deux mesures ci-dessus resteraient vertes -- ce depot a paye
    TROIS fois une borne citee de memoire et fausse. La greffe est **en
    memoire** : on ne modifie pas le module sur disque.

    **La greffe porte sur la FONCTION du coeur depuis le 2026-09-06**, et non
    plus sur une constante importee par le module de dessin. Ce n'est pas un
    detail de forme : l'import etait le defaut lui-meme, attrape par
    `test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG`, et une greffe
    posee sur lui mesurait donc la persistance de ce defaut. Greffer l'appel
    mesure ce qui reste vrai -- que la phrase SUIT le coeur.
    """
    from unittest import mock
    with mock.patch.object(ajout_de_rush, "cardinal_des_homonymes",
                           lambda: 42):
        greffee = ajout_de_rush.phrase_des_rangs_epuises()
    assert "42" in greffee, greffee
    assert "99" not in greffee, greffee
    assert ajout_de_rush.phrase_des_rangs_epuises() != greffee


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_ne_parait_QUE_quand_la_separation_est_RETIREE(ascii_seul):
    """Le modele, dans les DEUX regimes, et les deux drapeaux joues.

    Une garde qui ne fait varier aucun de ses drapeaux ne mesure qu'un seul
    chemin (CLAUDE.md, 2026-09-06) : le repli ASCII est joue des deux cotes,
    meme la ou la phrase courante n'a rien a replier -- c'est justement le
    jour ou elle gagnera un glyphe que cette mesure servira.
    """
    ordinaire = fiche()
    assert ordinaire.separation_offerte() is True
    assert ordinaire.ligne_des_rangs_epuises(ascii_seul) is None

    epuise = ajout_de_rush.FicheDeRefusDeConflit(refus_aux_rangs_epuises())
    assert epuise.separation_offerte() is False
    assert epuise.ligne_des_rangs_epuises(ascii_seul) == (
        ajout_de_rush.phrase_des_rangs_epuises(ascii_seul))


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("largeur_fenetre", LARGEURS_DE_FENETRE)
def test_l_ecran_MONTE_echange_la_suite_contre_la_ligne_SANS_changer_de_hauteur(
        banc, ascii_seul, largeur_fenetre):
    """`E2-1j` REMPLACE une ligne de `E2-1f`, il n'en ajoute pas une.

    **C'est la mesure qui compte**, et elle se prend sur l'ecran monte : la
    zone centrale de cet ecran est pleine a 17 sur 17 (docstring
    d'`EcranRefusDeConflit`). Une ligne de plus la ferait deborder, une de
    moins y laisserait un trou -- et ni l'un ni l'autre ne se voit sur un
    modele.

    Le cardinal est compare **entre les deux etats**, jamais a un 17 ecrit
    ici : un nombre pose en dur cesserait de mesurer le jour ou le cartouche
    gagnerait ou perdrait une ligne, et il rougirait pour la mauvaise raison.
    """
    hauteurs = {}
    for cle, refus in (("ordinaire", refus_de_conflit()),
                       ("epuise", refus_aux_rangs_epuises())):
        ecran = amont.EcranRefusDeConflit(refus, DOSSIER_DESIGNE)

        async def scenario(pilote, ecran=ecran):
            pilote.app.descendre(ecran)
            await pilote.pause()
            return zone_centrale(pilote)

        rendus = banc(coque_du_refus(ecran, ascii_seul), scenario,
                      (largeur_fenetre, 24))
        hauteurs[cle] = sum(len(lignes) for _, lignes in rendus)
        toutes = [ligne for _, lignes in rendus for ligne in lignes]
        phrase = ajout_de_rush.phrase_des_rangs_epuises(ascii_seul)
        if cle == "epuise":
            assert any(phrase in ligne for ligne in toutes), toutes
            # La ligne est AVANT les issues, comme le dessin la place.
            identifiants = [ident for ident, _ in rendus]
            assert identifiants.index("explication") < identifiants.index(
                "issues"), identifiants
        else:
            assert not any(phrase in ligne for ligne in toutes), toutes
            assert "explication" not in [ident for ident, _ in rendus]

    assert hauteurs["ordinaire"] == hauteurs["epuise"], hauteurs


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("largeur_fenetre", LARGEURS_DE_FENETRE)
def test_la_ligne_de_E2_1j_ne_DEBORDE_pas_la_zone_utile(banc, ascii_seul,
                                                        largeur_fenetre):
    """Ce qui est PEINT tient dans la zone, et n'a rien eu a se faire rogner.

    Deux volets, comme sur la ligne du relink : une ligne rognee tiendrait la
    premiere mesure tout en ayant perdu sa queue -- et sa queue est ici
    « ou renommer », c'est-a-dire la moitie de l'issue que la ligne nomme.
    """
    ecran = amont.EcranRefusDeConflit(refus_aux_rangs_epuises(),
                                      DOSSIER_DESIGNE)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        return lignes_peintes(ecran, "explication")

    peintes = banc(coque_du_refus(ecran, ascii_seul), scenario,
                   (largeur_fenetre, 24))
    zone = jetons.largeur_utile(largeur_fenetre)
    assert len(peintes) == 1, peintes
    assert jetons.colonnes(peintes[0]) <= zone, (zone, peintes)
    assert peintes[0].strip() == ajout_de_rush.phrase_des_rangs_epuises(
        ascii_seul)


def test_le_REPLI_ascii_de_la_phrase_est_EMPLOYE_et_pas_seulement_appele():
    """Frontiere ANTI-TAUTOLOGIE, seconde : la phrase PASSE par `_replie`.

    **Elle ferme un mutant qui avait survecu** (`M5`, campagne du 2026-09-06,
    102 verts) : retirer l'appel a :func:`_replie` de
    :func:`phrase_des_rangs_epuises` ne rougissait rien, parce que la
    redaction du jour ne porte **aucun glyphe a replier** -- l'apostrophe et
    les deux-points sont deja de l'ASCII. Le mutant etait donc equivalent
    SOUS CETTE REDACTION, et seulement sous elle.

    C'est exactement la famille de defaut que `PHRASE_DERNIER_LOT` a paye le
    meme jour, et le meme motif que le finding `F5` de ce banc : une mesure
    qui epingle la PRESENCE d'un appel, jamais son USAGE, cesse de mesurer
    des que la valeur change. La greffe pose donc une redaction qui, elle, a
    quelque chose a replier -- et le mode ASCII doit alors la changer.
    """
    from unittest import mock
    avec_glyphe = "Les {rangs} rangs — « pris » — en retirer un, ou renommer."
    with mock.patch.object(ajout_de_rush,
                           "PHRASE_DES_RANGS_D_HOMONYME_EPUISES", avec_glyphe):
        utf8 = ajout_de_rush.phrase_des_rangs_epuises(False)
        ascii_ = ajout_de_rush.phrase_des_rangs_epuises(True)
    assert utf8 != ascii_, (utf8, ascii_)
    assert "—" in utf8 and "«" in utf8
    assert "—" not in ascii_ and "«" not in ascii_
    # Et le volet qui rattache la greffe au produit : c'est bien la MEME
    # fonction que l'ecran appelle, pas une redaction du banc.
    assert ajout_de_rush.phrase_des_rangs_epuises(True) == (
        ajout_de_rush.FicheDeRefusDeConflit(
            refus_aux_rangs_epuises()).ligne_des_rangs_epuises(True))
