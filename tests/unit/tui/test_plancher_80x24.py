# -*- coding: utf-8 -*-
"""Le PLANCHER de `EPIC11-ARB-21` -- 80x24 --, mesure sur tous les ecrans.

**L'angle mort que ce banc ferme, et il etait entier.** L'audit du parcours
complet du 2026-09-06 dit lui-meme, section « Ce que cet audit N'A PAS
mesure » : « Une seule taille de terminal, 100x30. [...] **Aucun ecran n'a ete
mesure au plancher**, ni en `--ascii`. » Tout le produit a donc ete verifie
au-dessus de sa propre borne basse, et dans un seul de ses deux modes de
rendu -- alors que la borne basse est justement le regime ou une ligne
deborde.

**Ce que la mesure a trouve le 2026-09-06**, et qui justifie que ce banc
existe plutot qu'une relecture : en UTF-8, aucune anomalie sur 14 ecrans
montes ; en `--ascii`, **onze bandeaux sur quatorze ampute leur droite**, tous
par la meme cause unique -- :meth:`coque.Palier.bandeau` composait le bandeau
en geometrie UTF-8 puis laissait `compose` le replier, si bien que la ligne
calee a 76 colonnes en passait 78 une fois repliee et se faisait couper.
C'est exactement la regression que le docstring de `coque.Contexte.rendu`
declare fermee (« Replier AVANT de mesurer, jamais apres », mesure du
2026-08-28) : elle etait fermee DANS le module et rouverte par son APPELANT.
Aucune relecture ne l'aurait vue, les deux moities etant justes separement.

**Trois volets, trois modes de panne differents.**

* *volet A*, statique et exhaustif : l'inventaire des lignes de raccourcis.
  Il ne monte rien, donc il couvre les **55 ecrans** du produit -- y compris
  les quarante que le banc ne sait pas construire faute de donnee de terrain
  -- et il couvre par construction ceux qu'on ecrira demain ;
* *volet B*, dynamique : le chrome reellement rendu par un ecran monte a
  80x24, dans les DEUX modes. C'est le seul volet qui voit l'assemblage, donc
  le seul qui pouvait voir le defaut du bandeau ;
* *volet C* : la hauteur du centre. Dix-sept lignes utiles, pas dix-huit.

**Les bornes sont ecrites EN CLAIR dans ce banc, jamais relues du module
mesure** -- 80, 24, 76, 17. Un banc qui lirait `jetons.largeur_utile()` pour
en verifier le respect serait tautologique : deplacer la borne dans le module
deplacerait l'attente du meme mouvement, et le banc resterait vert en laissant
passer un ecran soudain trop large.
:func:`test_les_bornes_ecrites_ici_sont_CELLES_du_produit` est le seul point
de contact, et c'est une egalite entre deux nombres ecrits separement.

**Ce que ce banc NE mesure pas, dit plutot que tu :**

* il ne mesure **pas** les quarante ecrans qu'il ne sait pas construire, pour
  ce qui est du volet B. Ils sont nommes un a un dans :data:`SANS_FABRIQUE`,
  et une garde rougit si un ecran concret n'est ni fabrique ni declare la --
  un ecran neuf ne peut donc pas se glisser hors mesure en silence ;
* il ne mesure pas le regime SOUS le plancher (le message « terminal trop
  petit »), qui a son propre banc, ni le redimensionnement ;
* il ne balaye pas `--sans-couleur`, et c'est **mesure plutot que suppose** :
  trois ecrans montes a 80x24 dans les quatre combinaisons de
  `--ascii` x `--sans-couleur` rendent un chrome et un centre **identiques au
  caractere pres** une fois le balisage retire. La couleur ne passe que par du
  balisage, que :func:`jetons.texte_affiche` retire de toutes les mesures
  ci-dessous ; la balayer doublerait le temps du banc pour ne rien mesurer de
  neuf. Si un jour un ecran choisissait un GLYPHE selon la couleur, cette
  conclusion tomberait et le balayage serait a poser.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import pkgutil
import sys
from pathlib import Path
from types import MappingProxyType

import pytest

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility.tui import coque, jetons  # noqa: E402
from mixed_media_utility.tui import (  # noqa: E402
    atelier_scan_detection as _scan_det)
from mixed_media_utility.tui.coque import CoqueTui, Palier, PalierTemoin  # noqa: E402

# ---------------------------------------------------------------------------
# Les bornes, ecrites en clair. Voir le docstring : les relire du module
# mesure ferait de tout ce fichier une tautologie.
# ---------------------------------------------------------------------------

#: Le plancher de `EPIC11-ARB-21`, en colonnes et en lignes.
LARGEUR_DU_PLANCHER = 80
HAUTEUR_DU_PLANCHER = 24

#: Colonnes ecrivables une fois le cadre (1+1) et les marges (1+1) retires.
COLONNES_UTILES = 76

#: Lignes de contenu une fois le cadre, les deux filets, le bandeau, la ligne
#: d'etat et la ligne de raccourcis retires.
LIGNES_DE_CENTRE = 17

#: Les deux marques d'abregement, **ecrites ici** et non relues de `jetons` :
#: c'est par elles qu'on reconnait une ligne amputee, donc les relire de la
#: surface mesuree rendrait la detection aveugle a son propre deplacement.
MARQUE_UTF8 = "…"
MARQUE_ASCII = "..."


def marque_du_mode(ascii_seul: bool) -> str:
    """La marque d'abregement attendue dans le mode demande."""
    return MARQUE_ASCII if ascii_seul else MARQUE_UTF8


# ---------------------------------------------------------------------------
# L'inventaire du paquet TUI. Parcouru, jamais enumere.
# ---------------------------------------------------------------------------

def modules_de_la_tui() -> list:
    """Tous les modules du paquet TUI, importes.

    Parcourir le paquet plutot qu'ecrire une liste est ce qui fait de ce banc
    une frontiere : un module ajoute demain entre dans la mesure sans qu'on
    ait rien a poser.
    """
    import mixed_media_utility.tui as paquet

    trouves = []
    for info in pkgutil.iter_modules(paquet.__path__):
        if info.name.startswith("__"):
            continue
        trouves.append(importlib.import_module(
            "mixed_media_utility.tui." + info.name))
    return trouves


def _textes_de(valeur) -> list[str]:
    """Les chaines portees par une constante : elle-meme, ou celles d'une table."""
    if isinstance(valeur, str):
        return [valeur]
    if isinstance(valeur, (dict, MappingProxyType)):
        return [sous for sous in valeur.values() if isinstance(sous, str)]
    return []


def inventaire_des_raccourcis() -> dict[str, str]:
    """Toute ligne de raccourcis du paquet, `{origine: texte}`.

    **Deux gisements, et il faut les deux.** Les constantes de module
    (`RACCOURCIS_*`, `PIED_*`) portent les lignes contextuelles -- celles que
    `raccourcis_de_l_explorateur` ou `Reglages.raccourcis()` choisissent a
    l'execution, et qu'un balayage des seuls attributs de classe manquerait,
    puisqu'aucune classe ne les porte. Les attributs de classe portent les six
    lignes ecrites en litteral a meme l'ecran, qu'aucune constante ne nomme.
    Mesure du 2026-09-06 : 126 origines, dont ces six.

    Le nom de l'origine est la cle, si bien que deux origines distinctes ne se
    recouvrent jamais -- une table qui les ecraserait ferait passer un
    debordement pour absent.
    """
    trouves: dict[str, str] = {}
    for module in modules_de_la_tui():
        court = module.__name__.split(".")[-1]
        for nom, valeur in vars(module).items():
            if not (nom.startswith("RACCOURCIS") or nom.startswith("PIED")):
                continue
            for rang, texte in enumerate(_textes_de(valeur)):
                suffixe = "" if isinstance(valeur, str) else f"[{rang}]"
                trouves[f"{court}.{nom}{suffixe}"] = texte
    for module, nom, cls in paliers_du_paquet():
        texte = cls.__dict__.get("raccourcis")
        if isinstance(texte, str) and texte:
            trouves[f"{module}.{nom}.raccourcis"] = texte
    return trouves


def paliers_du_paquet() -> list[tuple[str, str, type]]:
    """`(module, nom, classe)` de toute sous-classe de `Palier`, triee.

    **Les classes PARESSEUSES sont forcees d'abord** (2026-09-07), pour la
    meme raison que dans `test_montee_reelle_des_ecrans.py`, ou le defaut a
    ete paye : `atelier_scan_calibrate` sous-classe `EcranExecution` a
    l'interieur d'une fonction et memorise le resultat dans un attribut de
    module. La classe n'est donc dans `vars(module)` que si quelque chose l'a
    deja demandee dans ce processus -- et ce banc rendait alors un inventaire
    qui dependait de l'ORDRE des tests. Sous `-n 4`, c'est un rouge qu'on
    prend pour un alea.
    """
    from mixed_media_utility.tui import atelier_scan_calibrate

    atelier_scan_calibrate._classe_de_l_ecran_de_passe()
    trouves = []
    for module in modules_de_la_tui():
        for nom, obj in vars(module).items():
            if (inspect.isclass(obj) and issubclass(obj, Palier)
                    and obj is not Palier
                    and obj.__module__ == module.__name__):
                trouves.append((module.__name__.split(".")[-1], nom, obj))
    return sorted(trouves, key=lambda t: (t[0], t[1]))


def est_un_ecran_concret(cls: type) -> bool:
    """Une classe qui DESSINE, par opposition a une base d'heritage.

    Le critere est ce que la classe redefinit elle-meme : un ecran concret
    porte au moins son contenu, sa ligne de raccourcis ou ses lignes. Une base
    n'en porte aucun et n'est jamais montee telle quelle.
    """
    return any(cle in cls.__dict__
               for cle in ("contenu", "raccourcis", "lignes"))


def ecrans_concrets() -> list[tuple[str, str, type]]:
    return [t for t in paliers_du_paquet() if est_un_ecran_concret(t[2])]


# ---------------------------------------------------------------------------
# Volet A -- l'inventaire des lignes de raccourcis
# ---------------------------------------------------------------------------

def test_les_bornes_ecrites_ici_sont_CELLES_du_produit():
    """Le SEUL point de contact entre ce banc et la geometrie du produit.

    Il est ecrit comme une egalite entre deux nombres rediges separement, et
    non comme une lecture : c'est ce qui empeche les trois volets ci-dessous
    d'etre tautologiques. Deplacer une borne dans `jetons` fait rougir ici, et
    la conversation a lieu -- au lieu que toutes les attentes du banc suivent
    silencieusement le deplacement.
    """
    assert jetons.LARGEUR_PLANCHER == LARGEUR_DU_PLANCHER
    assert jetons.HAUTEUR_PLANCHER == HAUTEUR_DU_PLANCHER
    assert jetons.largeur_utile(LARGEUR_DU_PLANCHER) == COLONNES_UTILES
    assert jetons.HAUTEUR_CENTRE_AU_PLANCHER == LIGNES_DE_CENTRE


#: Les deux ecrans dont la ligne de raccourcis n'est **pas** un litteral de
#: classe : elle leur est passee a la construction. Ils sont nommes plutot que
#: tolerés en masse -- une exception qui se compte reste une exception.
LIGNE_POSEE_A_LA_CONSTRUCTION = frozenset({
    ("atelier_extraction", "_EcranDeCadences"),
    ("coque", "PalierTemoin"),
})


def test_l_inventaire_des_raccourcis_couvre_TOUT_ecran_concret():
    """La garde de couverture : un ecran hors inventaire ne se mesure pas.

    Sans elle, le volet A serait vert le jour ou une ligne de raccourcis
    cesserait d'etre un litteral -- composee par une f-string, par exemple --,
    puisqu'elle disparaitrait simplement du balayage : le volet A ne verrait
    plus rien a mesurer et resterait vert **en ne mesurant rien**, ce qui est
    le mode de panne le plus couteux d'une frontiere.

    **La resolution suit la MRO, et ce n'est pas un raffinement.** Trois des
    ecrans du produit heritent leur ligne d'une base ecrite dans un autre
    module -- `EcranConflitDeDetection` tient la sienne d'`EcranDeJugement`,
    dans `atelier_scan_calibrate`. Une garde par MODULE les declarait
    manquants alors qu'ils sont couverts ; une garde par ECRAN, qui lit
    l'attribut resolu, dit la verite.
    """
    valeurs = set(inventaire_des_raccourcis().values())
    manquants = []
    for module, nom, cls in ecrans_concrets():
        if (module, nom) in LIGNE_POSEE_A_LA_CONSTRUCTION:
            continue
        if not cls.raccourcis or cls.raccourcis not in valeurs:
            manquants.append(f"{module}.{nom} -> {cls.raccourcis!r}")
    assert not manquants, (
        "la ligne de raccourcis de ces ecrans concrets n'est pas dans "
        f"l'inventaire mesure, donc elle n'est pas mesuree :\n  "
        + "\n  ".join(manquants))


def test_les_exceptions_de_couverture_designent_encore_un_ecran():
    """Le volet symetrique : une exception perimee affaiblit la garde.

    Sans lui, `LIGNE_POSEE_A_LA_CONSTRUCTION` pourrait grossir a chaque
    difficulte et finir par exempter tout le produit sans que rien ne rougisse.
    """
    concrets = {(module, nom) for module, nom, _ in ecrans_concrets()}
    perimees = sorted(LIGNE_POSEE_A_LA_CONSTRUCTION - concrets)
    assert not perimees, perimees
    assert len(LIGNE_POSEE_A_LA_CONSTRUCTION) <= 4, (
        "trop d'ecrans exemptes : la garde ne mesure plus grand-chose")


def test_l_inventaire_porte_plusieurs_origines_DISTINGUABLES():
    """La regle des fabriques, point 1, appliquee a l'inventaire lui-meme.

    Un inventaire d'une seule entree, ou de N entrees identiques, rendrait
    invisible tout defaut de parcours : le balayage pourrait n'en lire qu'une
    et rester vert. On exige donc plusieurs origines ET plusieurs textes
    differents -- un remplissage uniforme ne mesure pas un parcours.
    """
    origines = inventaire_des_raccourcis()
    assert len(origines) >= 50, len(origines)
    assert len(set(origines.values())) >= 20, sorted(set(origines.values()))


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_aucune_ligne_de_raccourcis_ne_deborde_au_plancher(ascii_seul):
    """Volet A. 76 colonnes, dans les DEUX modes.

    **Le mode ASCII n'est pas le mode UTF-8 a une decoration pres**, et c'est
    mesure : `⏎` rend `Entree`, donc une ligne portant le symbole d'entree
    gagne **cinq colonnes** au repli. `RACCOURCIS_RUSHES` fait 59 colonnes en
    UTF-8 et 64 en ASCII ; `atelier_pdf_reglages.RACCOURCIS_CHOIX` fait 71 en
    UTF-8 et **76 en ASCII**, c'est-a-dire la borne exacte. Mesurer un seul
    des deux modes laisserait passer cinq colonnes de derive.

    Les fleches, elles, ne changent rien -- `↑` rend `^`, une colonne pour une
    colonne. Le brief qui a commande ce banc le supposait sans le savoir ; la
    mesure le confirme, et c'est la seule raison de le croire.
    """
    trop_larges = []
    for origine, texte in sorted(inventaire_des_raccourcis().items()):
        rendu = jetons.replier_ascii(texte) if ascii_seul else texte
        largeur = jetons.colonnes(rendu)
        if largeur > COLONNES_UTILES:
            trop_larges.append(f"{origine} : {largeur} colonnes -- {rendu!r}")
    assert not trop_larges, (
        f"au plancher de {LARGEUR_DU_PLANCHER} colonnes, la zone utile en "
        f"fait {COLONNES_UTILES} ; ces lignes de raccourcis seraient "
        "AMPUTEES :\n  " + "\n  ".join(trop_larges))


# ---------------------------------------------------------------------------
# Le balayage, et sa propre mesure. Regle des fabriques, points 2 et 4.
# ---------------------------------------------------------------------------

def origines_trop_larges(inventaire: dict[str, str],
                         ascii_seul: bool = False) -> list[str]:
    """Les origines de `inventaire` qui depassent la zone utile.

    **Ecrite comme une fonction, et non en ligne dans le test**, pour qu'elle
    soit elle-meme mesurable : les trois tests de bord ci-dessous lui donnent
    un inventaire dont ils savent ou est la cible, et verifient qu'elle la
    trouve. Un balayage tronque -- qui sauterait la premiere ou la derniere
    entree -- ne se demasque pas autrement.
    """
    trouvees = []
    for origine, texte in sorted(inventaire.items()):
        rendu = jetons.replier_ascii(texte) if ascii_seul else texte
        if jetons.colonnes(rendu) > COLONNES_UTILES:
            trouvees.append(origine)
    return trouvees


#: Trois lignes de raccourcis **distinguables**, toutes tenant au plancher :
#: des longueurs differentes, des touches differentes, des mots differents.
#: Un remplissage uniforme rendrait toute permutation invisible (regle des
#: fabriques, point 1).
LIGNES_QUI_TIENNENT = (
    ("courte", "Q quitter"),
    ("moyenne", "⏎ choisir  ↑↓ naviguer  Échap revenir"),
    ("longue", "⏎ choisir  ↑↓ naviguer  Tab ajouter un rush  Échap ateliers"),
)

#: Une ligne qui NE tient pas : 96 colonnes en UTF-8, davantage en ASCII.
LIGNE_QUI_DEBORDE = ("⏎ choisir  ↑↓ naviguer  Tab ajouter un rush  "
                     "Échap ateliers  F1 aide  Q quitter  Ctrl+H caches")


def inventaire_avec_la_cible_en(position: int) -> dict[str, str]:
    """Un inventaire de quatre origines, la debordante placee en `position`.

    Les cles sont numerotees dans l'ordre de placement, si bien que le tri par
    cle du balayage suit ce meme ordre : la cible est donc reellement en tete,
    au milieu ou en queue de ce que la boucle lit, et non seulement de ce que
    ce dictionnaire declare.
    """
    tenues = list(LIGNES_QUI_TIENNENT)
    entrees = tenues[:position] + [("debordante", LIGNE_QUI_DEBORDE)] \
        + tenues[position:]
    return {f"{rang}_{nom}": texte
            for rang, (nom, texte) in enumerate(entrees)}


def test_le_balayage_trouve_la_cible_EN_TETE():
    """Regle des fabriques, point 4, bord de tete.

    Un balayage qui partirait du deuxieme element -- une boucle sur
    `entrees[1:]`, un `next()` consomme avant la boucle -- resterait vert avec
    une cible au milieu. Il ne l'est pas ici.
    """
    inventaire = inventaire_avec_la_cible_en(0)
    assert origines_trop_larges(inventaire) == ["0_debordante"]


def test_le_balayage_trouve_la_cible_AU_MILIEU():
    """Regle des fabriques, point 2 : la cible ailleurs qu'en premiere
    position. Un balayage qui rendrait toujours le premier element ne se
    demasque pas autrement."""
    inventaire = inventaire_avec_la_cible_en(1)
    assert origines_trop_larges(inventaire) == ["1_debordante"]


def test_le_balayage_trouve_la_cible_EN_QUEUE():
    """Regle des fabriques, point 4, bord de queue.

    C'est le mode de panne que « au milieu » ne demasque PAS : un balayage
    tronque d'une entree -- `entrees[:-1]`, un `range(len - 1)` -- laisse
    passer exactement la derniere, et toutes les cibles du milieu le laissent
    vert.
    """
    inventaire = inventaire_avec_la_cible_en(len(LIGNES_QUI_TIENNENT))
    assert origines_trop_larges(inventaire) == ["3_debordante"]


def test_le_balayage_ne_crie_pas_sur_un_inventaire_SAIN():
    """Le volet symetrique : sans cible, aucune origine n'est rendue.

    Sans lui, un balayage qui rendrait TOUTE origine passerait les trois tests
    de bord ci-dessus sans rien mesurer.
    """
    sain = {f"{rang}_{nom}": texte
            for rang, (nom, texte) in enumerate(LIGNES_QUI_TIENNENT)}
    assert origines_trop_larges(sain) == []


def test_le_balayage_voit_ce_que_le_REPLI_ASCII_allonge():
    """La cible ne deborde qu'une fois repliee -- 76 colonnes, puis 81.

    C'est le regime que la mesure du 2026-09-06 a trouve sur le bandeau, et
    aucun balayage UTF-8 seul ne le voit. Le meme inventaire est donc mesure
    dans les deux modes, et il doit rendre deux verdicts DIFFERENTS.
    """
    ligne = ("⏎ choisir  ↑↓ naviguer  Tab ajouter un rush  Échap ateliers  "
             "F1 aide  Q quit")
    assert jetons.colonnes(ligne) == COLONNES_UTILES
    assert jetons.colonnes(jetons.replier_ascii(ligne)) > COLONNES_UTILES
    inventaire = {"0_courte": "Q quitter", "1_repliee": ligne}
    assert origines_trop_larges(inventaire, ascii_seul=False) == []
    assert origines_trop_larges(inventaire, ascii_seul=True) == ["1_repliee"]


# ---------------------------------------------------------------------------
# Volet B -- le chrome REELLEMENT rendu, ecran monte a 80x24
# ---------------------------------------------------------------------------

#: Les ecrans concrets que ce banc ne sait pas construire : ils exigent une
#: donnee de terrain (un plan de scan, un rapport de detection, un panneau
#: chiffre, un formulaire de reglages) que le montage direct n'a pas.
#:
#: **Ils sont nommes plutot que tus** : leur ligne de raccourcis EST mesuree
#: par le volet A, qui ne monte rien ; c'est leur bandeau et leur centre qui
#: ne le sont pas. La garde
#: :func:`test_tout_ecran_concret_est_fabrique_ou_DECLARE_non_mesure` fait
#: rougir un ecran neuf qui ne serait ni dans une fabrique ni dans cette
#: liste, de sorte qu'un ecran ne peut pas sortir de la mesure en silence.
SANS_FABRIQUE = frozenset({
    ("atelier_exports_confirmation", "EcranExportsConfirmation"),
    ("atelier_exports_execution", "EcranEncodageEnCours"),
    ("atelier_exports_lot", "EcranDesLotsAEncoder"),
    ("atelier_exports_reglages", "EcranReglagesDeL_encodage"),
    ("atelier_exports_versions", "EcranMasterExistant"),
    ("atelier_extraction", "EcranCadences"),
    ("atelier_extraction", "EcranChoixDesCadences"),
    ("atelier_extraction", "EcranDeclaration"),
    ("atelier_extraction", "EcranPreviz"),
    ("atelier_extraction", "EcranRefusDeConflit"),
    ("atelier_extraction", "EcranRefusRelink"),
    ("atelier_extraction", "EcranRushes"),
    ("atelier_extraction", "_EcranDeCadences"),
    ("atelier_extraction_ecriture", "EcranExtractionEcrasement"),
    ("atelier_pdf_calibration", "EcranMireConfirmation"),
    ("atelier_pdf_calibration", "EcranMireExiste"),
    ("atelier_pdf_confirmation", "EcranPdfConfirmation"),
    ("atelier_pdf_execution", "EcranGenerationDesPlanches"),
    ("atelier_pdf_lots", "EcranLotsAPlanches"),
    ("atelier_pdf_reglages", "EcranReglagesDesPlanches"),
    ("atelier_pdf_resultat", "EcranResultatDesPlanches"),
    ("atelier_pdf_versions", "_EcranDeConflit"),
    ("atelier_scan_calibrate", "EcranCalibrerLaChaine"),
    ("atelier_scan_calibrate", "EcranDeJugement"),
    ("atelier_scan_calibration", "EcranChoixDeCalibration"),
    ("atelier_scan_completion", "EcranCompletionQr"),
    ("atelier_scan_confirmation", "EcranScanConfirmation"),
    ("atelier_scan_detection", "EcranConflitDeDetection"),
    ("atelier_scan_parcours", "EcranRapportDeDetection"),
    ("execution", "EcranChiffre"),
    ("execution", "EcranEcrasement"),
    ("execution", "EcranExecution"),
    ("execution", "EcranInterruption"),
    ("execution", "EcranResultat"),
    ("execution", "PanneauConfirmation"),
    ("projet_suppression", "EcranResultatDeSuppression"),
    ("projet_suppression", "EcranReussiteDeSuppression"),
    ("projet_suppression", "EcranSuppressionConfirmation"),
    ("projet_suppression", "EcranSuppressionEnCours"),
})


def _refus_temoin(cls):
    """Un refus **garni** : deux listes de deux elements distinguables.

    Un refus vide rendrait un centre d'une ligne, ou aucun debordement
    vertical ne peut se voir. La regle des fabriques vaut ici aussi : deux
    elements par liste, tous differents.
    """
    return cls("REFUS_SOURCE_ABSENTE",
               "Le rush designe n'existe plus a l'emplacement enregistre.",
               conserve=["le lot plan-04", "les frames deja extraites"],
               non_ecrit=["le master mp4", "les planches a imprimer"],
               suites=["Revoir la source", "Abandonner l'extraction"])


def _apercu_temoin():
    """L'apercu d'une pose de profil, **sans disque et sans coeur**.

    `ProfilPose` est un simple porteur de trois valeurs : le construire ici ne
    simule rien, il donne a l'ecran exactement ce que
    `palier_projet.apercu_de_profil` lui donnerait. Les trois valeurs sont
    **longues et distinguables** -- un cartouche mesure sur des valeurs courtes
    ne pourrait pas deborder, donc ne mesurerait rien.
    """
    from mixed_media_utility.tui.palier_projet import ProfilPose

    return ProfilPose(
        chaine="epson-v850_papier-mat-310g_2026-08",
        forme="affine-par-canal-v2",
        chemin=Path("versions/calibration/"
                    "epson-v850_papier-mat-310g_2026-08.json"))


def _profil_pose_temoin(cls):
    """L'ecran de succes de la pose, avec un cartouche **garni**."""
    from mixed_media_utility.tui.palier_profil_defaut import (
        OBJET_DU_BANDEAU, panneau_du_profil_pose)

    return cls(panneau_du_profil_pose(_apercu_temoin()),
               objet=OBJET_DU_BANDEAU)


#: Les ecrans que ce banc sait construire, et **comment**. Une entree absente
#: renvoie au constructeur sans argument.
FABRIQUES = {
    ("coque", "EcranPasEncore"):
        lambda cls: cls("la designation d'un fichier", quand="story 11.11"),
    ("coque", "PalierTemoin"): lambda cls: cls("Ateliers", "q quitter"),
    ("execution", "EcranRefus"): _refus_temoin,
    # Les trois ecrans du profil par defaut du projet se montent **sans
    # disque** : la liste accepte `dossier=None` (elle n'affiche alors que sa
    # porte « autre fichier… »), et les deux autres ne prennent que des valeurs
    # deja calculees. Aucun n'a donc a etre declare non mesurable.
    ("palier_profil_defaut", "EcranProfilParDefaut"):
        lambda cls: cls(None, confirmer=lambda _chemin: None),
    ("palier_profil_defaut", "EcranPoseDuProfil"):
        lambda cls: cls(_apercu_temoin(),
                        Path("/valise/profil-designe.json"),
                        poser=lambda _source: None,
                        defaut_actuel="profil-precedent.json"),
    ("palier_profil_defaut", "EcranProfilPose"): _profil_pose_temoin,
    # `EPIC11-ARB-267`. Il se monte **sans disque** -- `PlanchesEtrangeres`
    # est une dataclasse de faits deja comptes --, donc il entre dans les
    # fabriques plutot que dans `SANS_FABRIQUE`, contrairement a son voisin
    # `EcranConflitDeDetection`, qui exige un refus du coeur. DEUX projets et
    # TROIS pages : un cartouche mono-element ne mesurerait ni la jointure des
    # noms ni le pluriel, et c'est justement la ligne la plus longue.
    ("atelier_scan_detection", "EcranAdoptionDeLaPlanche"):
        lambda cls: cls(
            _scan_det.PlanchesEtrangeres(
                projets=("aa_projet_voisin", "zz_projet_ailleurs"), pages=3),
            retenir=lambda _issue: None),
}


def ecrans_fabricables() -> list[tuple[str, str, type]]:
    """Les ecrans concrets que ce banc monte, hors :data:`SANS_FABRIQUE`."""
    return [(module, nom, cls) for module, nom, cls in ecrans_concrets()
            if (module, nom) not in SANS_FABRIQUE]


def construire(module: str, nom: str, cls: type):
    fabrique = FABRIQUES.get((module, nom))
    return fabrique(cls) if fabrique else cls()


def chrome_rendu(ecran, ascii_seul: bool) -> tuple[dict[str, str], list[str]]:
    """Monte `ecran` a 80x24 et rend `({zone: texte}, lignes du centre)`.

    **On lit ce que le widget porte, pas ce que le compositeur peint** : le
    compositeur coupe a la largeur du terminal par definition, donc il ne peut
    rien montrer de trop large -- une ligne trop longue s'y verrait comme une
    ligne absente, ce qui ne se distingue pas d'un ecran vide. Le modele du
    widget, lui, porte exactement ce que l'ecran a demande d'afficher.
    """
    app = CoqueTui(paliers=[ecran, PalierTemoin("Ateliers", "q quitter")],
                   ascii_seul=ascii_seul)

    async def tour():
        async with app.run_test(
                size=(LARGEUR_DU_PLANCHER, HAUTEUR_DU_PLANCHER)) as pilote:
            monte = pilote.app.screen
            zones = {}
            for zone in ("bandeau", "etat", "raccourcis"):
                try:
                    widget = monte.query_one("#" + zone)
                except Exception:
                    continue
                zones[zone] = jetons.texte_affiche(str(widget.content))
            centre: list[str] = []
            for enfant in monte.query_one("#centre").walk_children():
                contenu = getattr(enfant, "content", None)
                if contenu is not None:
                    centre += jetons.texte_affiche(str(contenu)).split("\n")
            return zones, centre

    return asyncio.run(tour())


def _se_monte_sans_argument(cls: type) -> bool:
    """`cls()` a-t-il tous ses arguments ? Lu de la SIGNATURE, jamais essaye.

    Onze ecrans du produit se construisent nus -- un menu n'a besoin de rien --
    et `construire` les monte par `cls()` quand aucune fabrique ne les nomme.
    Ils sont donc legitimement absents de :data:`FABRIQUES` **et** de
    :data:`SANS_FABRIQUE`, et la garde ci-dessous doit les reconnaitre plutot
    que de les compter orphelins.
    """
    try:
        signature = inspect.signature(cls)
    except (TypeError, ValueError):      # pragma: no cover - classe exotique
        return False
    return all(parametre.default is not inspect.Parameter.empty
               or parametre.kind in (inspect.Parameter.VAR_POSITIONAL,
                                     inspect.Parameter.VAR_KEYWORD)
               for parametre in signature.parameters.values())


def test_tout_ecran_concret_est_fabrique_ou_DECLARE_non_mesure():
    """La garde qui empeche un ecran neuf de sortir de la mesure en silence.

    Le volet B enumere -- il n'a pas le choix, un ecran de confirmation ne se
    monte pas sans son plan. La consigne du depot est alors explicite : « si
    tu dois enumerer, tu poses en plus une garde qui rougit quand un ecran
    concret manque a la liste ». La voici, et elle mesure les DEUX sens : un
    ecran ni fabrique ni declare fait rougir, et une declaration qui ne
    correspond plus a aucun ecran aussi -- sans quoi la liste pourrirait en
    couvrant des noms disparus.

    **La premiere assertion etait TAUTOLOGIQUE, et deux couches de revue plus
    une relecture l'ont trouvee le meme soir** (2026-09-06). Elle calculait
    `concrets - fabricables - SANS_FABRIQUE` alors qu'`ecrans_fabricables()`
    rend exactement `concrets - SANS_FABRIQUE` : l'ensemble etait vide **par
    construction**, et aucun ecran neuf n'aurait jamais pu la faire rougir.
    Elle se lit desormais sur :data:`FABRIQUES` -- la table reelle --, plus
    les ecrans que `cls()` sait monter nus, qui sont l'autre facon legitime
    d'entrer dans le volet B.
    """
    concrets = {(module, nom): cls for module, nom, cls in ecrans_concrets()}
    nus = {cle for cle, cls in concrets.items() if _se_monte_sans_argument(cls)}
    orphelins = sorted(set(concrets) - set(FABRIQUES) - SANS_FABRIQUE - nus)
    assert not orphelins, (
        "ces ecrans concrets ne sont ni fabriques ni declares non mesurables "
        f"et ne se montent pas nus : {orphelins}")
    perimees = sorted(SANS_FABRIQUE - set(concrets))
    assert not perimees, (
        f"ces declarations ne designent plus aucun ecran concret : {perimees}")


def test_le_volet_B_monte_PLUSIEURS_ecrans_distinguables():
    """Un volet dynamique qui ne monterait qu'un ecran ne mesurerait rien.

    Regle des fabriques, point 1, transposee : la collection balayee ici est
    celle des ecrans, et on exige qu'elle en porte plusieurs, portant des
    titres differents -- un balayage sur une collection uniforme reste vert
    quelle que soit la permutation.
    """
    fabricables = ecrans_fabricables()
    assert len(fabricables) >= 5, [n for _, n, _ in fabricables]
    titres = {cls.titre for _, _, cls in fabricables if cls.titre}
    assert len(titres) >= 3, sorted(titres)


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_aucun_chrome_n_est_AMPUTE_au_plancher(ascii_seul):
    """Volet B, le coeur de ce banc.

    **Le defaut qu'il a trouve, et qu'aucune relecture n'aurait vu** : en
    `--ascii`, onze des quatorze ecrans montables amputaient leur bandeau, et
    ce qu'ils perdaient etait sa DROITE -- l'objet travaille, c'est-a-dire les
    chiffres du parcours en cours, que rien d'autre ne reaffiche.
    `coque.Contexte.rendu` sait pourtant composer un bandeau ASCII correct ;
    ses deux appelants de `coque.py` ne lui passaient simplement pas le mode,
    si bien que la ligne etait calee a 76 colonnes en geometrie UTF-8, repliee
    ensuite a 78, puis coupee.

    La marque d'abregement est le marqueur : un bandeau qui la porte en queue
    a perdu quelque chose. On tolere qu'elle apparaisse AILLEURS dans la ligne
    -- un chemin abrege en son milieu est un abregement voulu, pas une
    amputation de bord.
    """
    marque = marque_du_mode(ascii_seul)
    amputes = []
    for module, nom, cls in ecrans_fabricables():
        zones, _ = chrome_rendu(construire(module, nom, cls), ascii_seul)
        for zone, texte in sorted(zones.items()):
            for ligne in texte.split("\n"):
                largeur = jetons.colonnes(ligne)
                if largeur > COLONNES_UTILES:
                    amputes.append(
                        f"{module}.{nom} / {zone} : {largeur} colonnes -- "
                        f"{ligne!r}")
                elif ligne.rstrip().endswith(marque):
                    amputes.append(
                        f"{module}.{nom} / {zone} : AMPUTE -- {ligne!r}")
    assert not amputes, (
        f"a {LARGEUR_DU_PLANCHER}x{HAUTEUR_DU_PLANCHER}"
        f"{' en --ascii' if ascii_seul else ''}, ce chrome ne tient pas dans "
        f"les {COLONNES_UTILES} colonnes utiles :\n  " + "\n  ".join(amputes))


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_le_bandeau_garde_sa_DROITE_dans_les_deux_modes(ascii_seul):
    """Le volet symetrique du precedent, et il mesure autre chose.

    Le test ci-dessus verifie qu'aucune marque d'abregement ne termine le
    bandeau ; celui-ci verifie que l'objet travaille est **la, en entier**.
    Sans lui, un correctif qui ferait simplement disparaitre la droite --
    plutot que de l'abreger -- rendrait le premier test vert.

    L'objet est pose par le contexte de session, donc il traverse
    `Contexte.rendu` exactement comme celui d'un ecran reel, et il est choisi
    LONG a dessein : 24 colonnes, de quoi rendre le budget serre sans le
    depasser.
    """
    objet = "12 rushes · 3 lots"
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "q quitter")],
                   ascii_seul=ascii_seul)
    app.contexte = coque.Contexte(projet=None, palier="", objet=objet)

    async def tour():
        async with app.run_test(
                size=(LARGEUR_DU_PLANCHER, HAUTEUR_DU_PLANCHER)) as pilote:
            return jetons.texte_affiche(
                str(pilote.app.screen.query_one("#bandeau").content))

    rendu = asyncio.run(tour())
    attendu = jetons.replier_ascii(objet) if ascii_seul else objet
    assert rendu.rstrip().endswith(attendu), (
        f"le bandeau a perdu sa droite : {rendu!r} ne se termine pas par "
        f"{attendu!r}")
    assert jetons.colonnes(rendu) <= COLONNES_UTILES, jetons.colonnes(rendu)


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_un_chrome_DEMESURE_est_borne_plutot_que_de_deborder(ascii_seul):
    """Le dernier recours, exerce -- et il ne l'etait par rien d'autre.

    **Le trou que ce test ferme, et il a ete trouve par mutation.** Tous les
    textes du produit tiennent au plancher : c'est ce que les volets A et B
    mesurent, et c'est tant mieux. Mais il en resulte que le chemin
    d'abregement de :func:`jetons.ajuster` et le dernier `ajuster` de
    :meth:`coque.Contexte.rendu` n'etaient **jamais joues** par ce banc.
    Deux mutants l'ont montre en survivant : supprimer le bornage final du
    bandeau, et fausser le budget de l'abregement de trois colonnes,
    laissaient les dix-neuf tests verts.

    Ce que la frontiere promet n'est donc pas seulement « les textes
    d'aujourd'hui tiennent » -- ce serait une photographie -- mais « un texte
    trop grand est COUPE plutot que de defoncer la grille ». C'est la
    difference entre un banc qui constate et une frontiere qui tient : l'ecran
    qu'on ecrira demain avec un libelle trop long doit degrader proprement.

    Le titre et l'objet sont demesures **tous les deux**, et a des tailles
    differentes : un bornage qui n'agirait que sur l'un des deux cotes
    resterait vert si l'autre seul debordait.
    """
    app = CoqueTui(paliers=[PalierTemoin(
        "Un palier au titre deraisonnablement long, comme personne n'en "
        "ecrirait jamais mais comme un jour quelqu'un en ecrira un",
        "Q quitter")], ascii_seul=ascii_seul)
    app.contexte = coque.Contexte(
        projet="un_projet_au_nom_tres_long_2026_08_31_camera_B_v3",
        palier="",
        objet="12 rushes · 3 lots · 480 frames · 2 masters · 7 planches")

    async def tour():
        async with app.run_test(
                size=(LARGEUR_DU_PLANCHER, HAUTEUR_DU_PLANCHER)) as pilote:
            monte = pilote.app.screen
            return {zone: jetons.texte_affiche(
                        str(monte.query_one("#" + zone).content))
                    for zone in ("bandeau", "raccourcis")}

    for zone, texte in asyncio.run(tour()).items():
        for ligne in texte.split("\n"):
            assert jetons.colonnes(ligne) <= COLONNES_UTILES, (
                f"{zone} : {jetons.colonnes(ligne)} colonnes -- {ligne!r}")


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_le_bandeau_reste_borne_meme_sur_un_contexte_INTENABLE(ascii_seul):
    """Le meme dernier recours, mais **sans monter d'application**.

    Le test ci-dessus passe par la coque, donc il mesure la chaine complete ;
    celui-ci interroge :meth:`coque.Contexte.rendu` directement, avec un objet
    qui a lui seul depasse la zone utile. Les deux sont necessaires : le
    premier peut etre rendu vert par un bornage pose dans `compose`, le second
    exige que le bornage soit dans `rendu` -- c'est-a-dire au seul endroit ou
    les cinq surcharges d'atelier en profitent aussi.
    """
    contexte = coque.Contexte(
        projet="projet_demo_planche_4f_heteroclite",
        palier="Calibration",
        objet="temps 2 sur 2 · ecrire la mire · 300 dpi · A4 · marge 5 mm")
    rendu = contexte.rendu(LARGEUR_DU_PLANCHER, ascii_seul)
    assert jetons.colonnes(rendu) <= COLONNES_UTILES, (
        f"{jetons.colonnes(rendu)} colonnes -- {rendu!r}")


# ---------------------------------------------------------------------------
# Volet C -- la hauteur du centre
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_aucun_centre_ne_depasse_les_dix_sept_lignes(ascii_seul):
    """Volet C. Ce qui depasse 17 lignes au plancher n'est jamais dessine.

    `textual` ne signale rien : la zone centrale a la hauteur qu'elle a, et
    les lignes en trop sortent du cadre. Un ecran qui perdrait sa derniere
    ligne -- typiquement la ligne d'issues d'un refus -- serait indistinguable
    d'un ecran qui n'en a pas.
    """
    trop_hauts = []
    for module, nom, cls in ecrans_fabricables():
        _, centre = chrome_rendu(construire(module, nom, cls), ascii_seul)
        if len(centre) > LIGNES_DE_CENTRE:
            trop_hauts.append(f"{module}.{nom} : {len(centre)} lignes")
    assert not trop_hauts, (
        f"au plancher, la zone centrale fait {LIGNES_DE_CENTRE} lignes ; "
        "ces ecrans en demandent davantage :\n  " + "\n  ".join(trop_hauts))
