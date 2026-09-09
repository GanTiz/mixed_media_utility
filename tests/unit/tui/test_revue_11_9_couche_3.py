# -*- coding: utf-8 -*-
"""Story 11.9, lot E -- les DEUX mesures que la revue de couche 3 a trouvees absentes.

Ce fichier est un **rendu de revue**, pas un lot de developpement : il porte
les deux bancs sans lesquels deux mutants reinjectes le 2026-09-03 ont
**survecu** a l'integralite des bancs de la story. Il vit a part plutot que
dans `test_manuel_derive.py` et `test_ecran_manuel.py` pour une raison de
procedure et non de conception -- les couches 1 et 2 de la meme revue
travaillent en parallele sur ces deux fichiers, et `CLAUDE.md` interdit deux
lots sur un meme banc. La triage des findings les y repliera.

**Mutant `M9b` -- l'appariement constante -> ecran rend le PREMIER ecran du
module.** C'est litteralement le mutant `M25` de la story 5.7, sur la donnee
qu'`EPIC11-ARB-196` cree. Injecte dans
`manuel.ecrans_par_ligne` -- `directs = {sorted(ecrans)[0]}` au lieu des
classes qui **nomment** la constante -- il fausse **19 attributions sur 121**
et survit aux 47 tests de `test_manuel_derive.py` **et** aux 56 de
`test_ecran_manuel.py`. Le banc qui devait le fermer,
`test_les_NEUF_ecrans_porteurs_de_Q_sont_rendus_ENTIERS_et_pas_le_premier`,
mesure une **union** sur dix lignes : chacun des neuf ecrans de `Q` est
premier quelque part, si bien que l'union survit intacte a la troncature.
Une union est aveugle a l'appariement qui la compose.

**Mutant `M16` -- les trois colonnes du dessin.**
`ecran_manuel.COLONNE_DE_L_OUVREUR`, `COLONNE_DU_LIBELLE` et
`COLONNE_DE_L_ATELIER` sont documentees « relevees sur `T1-2` au caractere
pres ». Aucune ne l'est : decalees d'une colonne, les trois survivent aux 56
tests de `test_ecran_manuel.py`. La confrontation ligne a ligne de l'AC 4.1 ne
peut structurellement pas les voir -- des vingt lignes de la grille, les cinq
qui coincident sont le bandeau, trois blancs et un titre de bloc : **aucune
ligne de contenu ne coincide**, donc tout deplacement a l'interieur d'une
ligne de contenu deplace une ligne deja listee comme divergente.

Les deux bancs lisent la maquette et le paquet ; ils ne recopient ni colonne
ni appariement.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from mixed_media_utility.tui import ecran_manuel as em
from mixed_media_utility.tui import manuel

_PAQUET_TUI = "mixed_media_utility.tui"

MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")


# ===========================================================================
# `M9b` -- l'appariement constante -> ECRAN, sur le PAQUET REEL
# ===========================================================================

def ecrans_du_module(module: str) -> list[str]:
    """Les ecrans d'un module, **tries comme le code les rend**.

    C'est la liste que `ecrans_par_ligne` parcourt et sur laquelle un
    `sorted(...)[0]` fautif mordrait : la position des cibles ci-dessous se
    verifie donc sur elle, jamais sur une liste ecrite ici (regle des
    fabriques, point 4).
    """
    return sorted(nom for nom, classe in manuel.classes_d_ecran().items()
                  if classe.__module__ == module)


#: **Trois cibles reelles, une a chaque position** (regle des fabriques,
#: points 2, 2 bis et 4). Chacune est une constante que **son** ecran nomme, et
#: dont l'ecran occupe la position dite dans la liste triee de son module :
#:
#: * `RACCOURCIS_CADENCES` -> `EcranCadences`, **premier** des six de
#:   `atelier_extraction` -- c'est la seule position ou un `[0]` fautif reste
#:   juste, et elle est posee pour que le banc ne soit pas vert par
#:   coincidence sur les deux autres ;
#: * `RACCOURCIS_PREVIZ` -> `EcranPreviz`, **au milieu** (rang 2 sur 6) -- la
#:   cible qui demasque le `find` fautif ;
#: * `RACCOURCIS_MIRE_REGLAGES` -> `EcranMireReglages`, **dernier** des cinq de
#:   `atelier_pdf_calibration` -- la cible qui demasque un balayage tronque.
APPARIEMENTS = [
    pytest.param(f"{_PAQUET_TUI}.atelier_extraction", "RACCOURCIS_CADENCES",
                 "EcranCadences", "premier", id="premier-bord"),
    pytest.param(f"{_PAQUET_TUI}.atelier_extraction", "RACCOURCIS_PREVIZ",
                 "EcranPreviz", "milieu", id="AU-MILIEU"),
    pytest.param(f"{_PAQUET_TUI}.atelier_pdf_calibration",
                 "RACCOURCIS_MIRE_REGLAGES", "EcranMireReglages", "dernier",
                 id="dernier-bord"),
]


@pytest.mark.parametrize("module,constante,ecran,position", APPARIEMENTS)
def test_l_appariement_CONSTANTE_vers_ECRAN_vise_le_BON_ecran_du_module(
        module, constante, ecran, position):
    """`EPIC11-ARB-196` -- l'appartenance creee designe l'ecran qui NOMME la ligne.

    Trois modules a plusieurs ecrans, trois cibles distinguables, une a chaque
    position. Un resolveur qui rendrait le premier ecran du module reste vert
    sur la cible `premier` et rougit sur les deux autres : c'est exactement ce
    que la regle des fabriques exige, et c'est ce qui manquait -- le banc de
    `Q` mesure une union, qu'une troncature par ligne laisse intacte.
    """
    attribution = manuel.ecrans_par_ligne()
    attendu = f"{module}.{ecran}"
    ecrans, etage = attribution[f"{module}.{constante}"]
    assert ecrans == (attendu,), (constante, ecrans)
    assert etage == manuel.ETAGE_CLASSE, etage

    # La position se verifie sur la liste que le CODE parcourt.
    liste = ecrans_du_module(module)
    assert len(liste) >= 3, (module, liste)
    rang = liste.index(attendu)
    if position == "premier":
        assert rang == 0, (attendu, liste)
    elif position == "dernier":
        assert rang == len(liste) - 1, (attendu, liste)
    else:
        assert 0 < rang < len(liste) - 1, (attendu, liste)


def test_une_ligne_portee_par_DEUX_ecrans_les_rend_TOUS_LES_DEUX():
    """Le volet de troncature, distinct du precedent.

    Une attribution qui ne garderait que le **premier** de ses porteurs reste
    verte sur les trois appariements ci-dessus, qui n'en ont qu'un chacun.
    `RACCOURCIS_MIRE_JUGEMENT` est nommee par deux ecrans du meme module -- et
    ce n'est pas la seule : le paquet en porte **six** au 2026-09-03, dont les
    quatre lignes de l'explorateur d'`ecran_projet`.
    """
    attribution = manuel.ecrans_par_ligne()
    ecrans, etage = attribution[
        f"{_PAQUET_TUI}.atelier_pdf_calibration.RACCOURCIS_MIRE_JUGEMENT"]
    assert ecrans == (
        f"{_PAQUET_TUI}.atelier_pdf_calibration.EcranMireConfirmation",
        f"{_PAQUET_TUI}.atelier_pdf_calibration.EcranMireExiste"), ecrans
    assert etage == manuel.ETAGE_CLASSE, etage
    # Et la famille entiere : le cardinal des lignes a plusieurs porteurs ne
    # doit pas tomber a zero en silence, ce qui rendrait ce test tautologique.
    plusieurs = {cle for cle, (porteurs, _) in attribution.items()
                 if len(porteurs) > 1}
    assert len(plusieurs) >= 6, sorted(plusieurs)


# ===========================================================================
# `M16` -- les TROIS colonnes, LUES de `T1-2` et non recopiees
# ===========================================================================

def lignes_de_contenu_de_T1_2() -> list[str]:
    """Les lignes de la maquette, cadre retire -- meme lecture que le lot C."""
    lignes = (MAQUETTES / "T1-2-manuel-raccourcis.txt").read_text(
        encoding="utf-8").rstrip("\n").split("\n")[:24]
    return [ligne[2:-2].rstrip() if ligne.startswith("│") else ""
            for ligne in lignes]


def rangs_des_RACCOURCIS() -> list[int]:
    """Les rangs de `T1-2` qui ouvrent un raccourci, **derives du contenu**.

    Une ligne de raccourci laisse blanc jusqu'a `COLONNE_DE_L_OUVREUR` exclu et
    ecrit juste apres ; un titre de bloc s'indente de deux colonnes, une
    respiration ne porte rien. Aucun des trois n'a besoin d'etre nomme.

    **Ces rangs etaient ecrits en litteral jusqu'au 2026-09-05**, et c'est ce
    jour-la qu'ils ont coute : `EPIC11-ARB-141` a retire la ligne
    `e   éditer les noms produits` de la maquette a sa source, la ligne `r` a
    glisse d'un rang, et ce banc a rougi -- pour une raison etrangere a ce
    qu'il mesure, qui sont les COLONNES du dessin.
    """
    rangs = [rang for rang, ligne in enumerate(lignes_de_contenu_de_T1_2())
             if ligne[:em.COLONNE_DE_L_OUVREUR].strip() == ""
             and ligne[em.COLONNE_DE_L_OUVREUR:em.COLONNE_DU_LIBELLE].strip()]
    assert len(rangs) >= 5, (
        f"`T1-2` ne porte presque plus de raccourci : {rangs}")
    return rangs


def rangs_des_RACCOURCIS_PROPRES() -> list[int]:
    """Les raccourcis qui suivent le titre du bloc « Propres a un ecran ».

    Ce sont les seuls ou la troisieme colonne se releve. Le decoupage se fait
    par le **titre**, cherche dans la maquette, et non par la presence d'une
    parenthese : deux libelles du bloc « partout » en portent une
    (`cocher / décocher (listes à cases)`, `quitter (demande confirmation…)`),
    et une parenthese de prose n'est pas une annotation d'atelier.
    """
    contenu = lignes_de_contenu_de_T1_2()
    titre = "  " + em.TITRE_DU_BLOC_PROPRES
    rangs_du_titre = [rang for rang, ligne in enumerate(contenu)
                      if ligne == titre]
    assert len(rangs_du_titre) == 1, (titre, rangs_du_titre)
    rangs = [rang for rang in rangs_des_RACCOURCIS()
             if rang > rangs_du_titre[0]]
    assert len(rangs) >= 2, (
        f"`T1-2` ne porte plus assez de raccourci ANNOTE pour relever la "
        f"colonne de l'atelier : {rangs}")
    return rangs


def test_les_TROIS_colonnes_du_manuel_sont_CELLES_de_T1_2():
    """AC 4.1, la moitie que la confrontation ligne a ligne ne peut pas voir.

    La confrontation de `test_C3_le_manuel_est_confronte_a_T1_2_...` compare
    des lignes **entieres** et liste les rangs divergents. Or **aucune ligne de
    contenu ne coincide** : les cinq rangs qui coincident sont le bandeau,
    trois blancs et un titre. Un decalage d'une colonne deplace donc du texte
    a l'interieur de lignes deja listees comme divergentes, et rien ne rougit
    -- mesure de la revue : les trois constantes decalees d'une unite
    survivent aux 56 tests de `test_ecran_manuel.py`.

    Ce banc releve les trois colonnes **sur la maquette** plutot que de les
    recopier : le jour ou `T1-2` est corrigee a sa source (`EPIC11-ARB-142`),
    il suit au lieu de rester vert sur l'ancien dessin.
    """
    contenu = lignes_de_contenu_de_T1_2()

    ouvreurs = set()
    libelles = set()
    for rang in rangs_des_RACCOURCIS():
        ligne = contenu[rang]
        assert ligne.strip(), (rang, "la maquette ne porte plus de raccourci "
                                     "a ce rang : le releve ne mesure rien")
        ouvreurs.add(len(ligne) - len(ligne.lstrip()))
        reste = ligne.lstrip()
        # Le libelle commence apres le premier creux d'au moins deux blancs.
        tete = reste.split("  ")[0]
        apres = ligne.index(tete) + len(tete)
        libelles.add(apres + len(ligne[apres:]) - len(ligne[apres:].lstrip()))

    assert ouvreurs == {em.COLONNE_DE_L_OUVREUR}, sorted(ouvreurs)
    assert libelles == {em.COLONNE_DU_LIBELLE}, sorted(libelles)

    ateliers = {contenu[rang].index("(")
                for rang in rangs_des_RACCOURCIS_PROPRES()}
    assert ateliers == {em.COLONNE_DE_L_ATELIER}, sorted(ateliers)

    # RECTIFIE le 2026-09-04 : ces quatre lignes portaient un FAUX « tue ».
    #
    # Ce qu'elles disaient : « Le SEPARATEUR de roles se releve sur la meme
    # maquette : `T1-2` ecrit "champ suivant · compléter un chemin · voir le
    # journal". Change en ` ; `, il survivait lui aussi aux 56 tests du lot
    # C. » -- et l'assertion cherchait `em.SEPARATEUR_DES_LIBELLES` DANS le
    # texte de la maquette.
    #
    # Pourquoi c'etait faux, et c'est structurel : la constante y servait de
    # **sonde de recherche**. La ramener a un espace simple rend la recherche
    # PLUS FACILE -- l'espace est partout dans la maquette --, donc le banc
    # restait vert. Rejoue le 2026-09-04, le mutant `M42` SURVIVAIT. Un banc
    # qui emploie la constante pour trouver ce qu'il verifie ne verifie rien.
    #
    # Ce qui reste ici est un pur RELEVE, ecrit en dur, qui ne lit plus la
    # constante : il dit que la maquette porte toujours le separateur, donc
    # que le releve a de quoi mesurer. La confrontation du separateur au
    # PRODUIT vit desormais dans `test_revue_11_9_m23_m42.py`, ou elle est
    # mesuree par six mutants joues dans les deux sens.
    a_plusieurs_roles = [contenu[rang] for rang in rangs_des_RACCOURCIS()
                         if " \u00b7 " in contenu[rang]]
    assert a_plusieurs_roles, (
        "la maquette n'ecrit plus le separateur : le releve ne mesure rien")


@pytest.mark.parametrize("ascii_seul", [pytest.param(False, id="utf8"),
                                        pytest.param(True, id="ascii")])
def test_le_RENDU_pose_bien_ses_ouvreurs_et_libelles_AUX_colonnes(ascii_seul):
    """Le volet symetrique : les constantes sont justes ET le rendu les tient.

    Sans lui, les trois constantes pourraient coincider avec la maquette
    pendant que `lignes_d_une_entree` calerait ailleurs -- deux mesures
    valent mieux qu'une quand l'une porte la valeur et l'autre son emploi.
    Trois entrees distinguables, la cible **au milieu**, une a chaque bord.
    """
    entrees = tuple(e for e in manuel.entrees_du_manuel() if not e.partout)
    assert len(entrees) >= 3, entrees
    for entree in (entrees[0], entrees[len(entrees) // 2], entrees[-1]):
        premiere = em.lignes_d_une_entree(entree, ascii_seul=ascii_seul)[0]
        creux = len(premiere) - len(premiere.lstrip())
        assert creux == em.COLONNE_DE_L_OUVREUR, (entree.ouvreur, premiere)
        reste = premiere[em.COLONNE_DE_L_OUVREUR:]
        tete = reste.split("  ")[0]
        apres = premiere.index(tete) + len(tete)
        debut = apres + len(premiere[apres:]) - len(premiere[apres:].lstrip())
        assert debut == em.COLONNE_DU_LIBELLE, (entree.ouvreur, premiere)
