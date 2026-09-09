# -*- coding: utf-8 -*-
"""`E6-1` -- l'arborescence des objets produits (story 11.11, lot B, AC 2).

**Ce que ce banc mesure et que rien d'autre ne mesure** : le REGROUPEMENT PAR
NATURE. `project_inventory` ne produit aucun noeud de regroupement -- son banc
a lui ne peut donc pas voir un groupe mal forme --, et les maquettes `E6-1` et
`E6-1e` en posent un niveau entier entre le lot et ses objets. Tout ce niveau
vit dans `tui/projet_inventaire.py`, et il n'a pas d'autre banc que celui-ci.

**La regle des fabriques du depot, ses quatre points, appliquee ici** :
:func:`_inventaire` produit **trois** rushes et **deux** de chaque nature, aux
valeurs toutes distinctes -- une permutation ne se voit pas sur un remplissage
uniforme ; la cible des tests de position est **au milieu** (`plan-04`), et
deux tests la placent **a chaque bord** (`a-premier` en tete, `z-dernier` en
queue). Le quatrieme point est celui que ce depot paie le plus souvent : sur un
arbre, un balayage tronque est exactement le mode de panne qui fait disparaitre
un objet sans le dire.
"""
import json
import re
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[3]
for chemin in (str(_RACINE / "src"), str(_RACINE / "tests" / "unit")):
    if chemin not in sys.path:
        sys.path.insert(0, chemin)

import pytest

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility import codec_profiles
from mixed_media_utility.io import naming, version_ranks
from mixed_media_utility.project_inventory import (ETAT_DECLARE_ABSENT,
                                                   ETAT_NON_DECLARE,
                                                   ETAT_PRESENT, ETATS,
                                                   NATURES,
                                                   NATURE_FRAMES_EXTRAITES,
                                                   NATURE_FRAMES_SCANNEES,
                                                   NATURE_LOT,
                                                   NATURE_LOT_SCANNE,
                                                   NATURE_MASTER,
                                                   NATURE_PLANCHE,
                                                   NATURE_RUSH, NATURE_SCAN,
                                                   InventaireDuProjet,
                                                   ObjetInventorie,
                                                   inventorier_le_projet,
                                                   libelles_de_nature)
from mixed_media_utility.tui import jetons, projet_inventaire as pi

from mixed_media_utility.tui.coque import (Contexte, CoqueTui,
                                            PalierTemoin)

Mo = 1024 ** 2

# ---------------------------------------------------------------------------
# Les valeurs que les maquettes E6-1* DESSINENT
# ---------------------------------------------------------------------------
# Chacune est confrontee a sa source dans la derniere section du fichier.

#: Le prefixe du bandeau, dessine par les CINQ ecrans de l'inventaire.
PREFIXE_DESSINE_DU_BANDEAU = "inventaire · "

#: Ce que le bandeau porte a la place des compteurs pendant la lecture
#: (`E6-1a`), qui est le seul des cinq a ne pas pouvoir compter.
MENTION_DESSINEE_DE_LA_LECTURE = "lecture en cours"

#: Le debut du cardinal du lot riche de `E6-1e`.
CARDINAL_DESSINE_DU_LOT_RICHE = "9 objets · "

#: Le cardinal a quatre chiffres de `E6-1c`, avec son separateur de milliers.
#: C'est une espace ORDINAIRE dans le dessin comme dans le code, et la
#: confrontation le mesure au codepoint.
CARDINAL_DESSINE_A_QUATRE_CHIFFRES = "1 204 f."

# ---------------------------------------------------------------------------
# Fabriques -- DEUX de chaque, aux valeurs toutes distinctes
# ---------------------------------------------------------------------------


def _objet(nature, nom, chemin=None, etat=ETAT_PRESENT, poids=0, fichiers=0,
           enfants=()) -> ObjetInventorie:
    return ObjetInventorie(nature=nature, nom=nom, chemin=chemin, etat=etat,
                           poids=poids, fichiers=fichiers,
                           enfants=tuple(enfants))


def _scan(nom, poids, pages, lot_scanne, poids_frames, frames):
    """Un scan et SON lot scanne, filiation d'`EPIC11-ARB-244`."""
    contenu = _objet(NATURE_LOT_SCANNE, lot_scanne, enfants=[
        _objet(NATURE_FRAMES_SCANNEES, lot_scanne,
               f"frames-scannees/{lot_scanne}", poids=poids_frames,
               fichiers=frames)])
    return _objet(NATURE_SCAN, nom, f"scans/{nom}", poids=poids,
                  fichiers=pages, enfants=[contenu])


def _lot_riche(lot_id, base=1) -> ObjetInventorie:
    """Un lot a DEUX de chaque nature, **toutes les valeurs distinctes**.

    `base` decale tous les poids : deux lots de la meme fabrique ne peuvent
    donc pas se confondre, et une permutation entre eux se voit.
    """
    return _objet(NATURE_LOT, lot_id, enfants=[
        _objet(NATURE_FRAMES_EXTRAITES, lot_id, f"extract-frames/{lot_id}",
               poids=base * 100 * Mo, fichiers=base * 10),
        _objet(NATURE_MASTER, f"{lot_id}_mmu_prores_hq.mov",
               f"outputs/{lot_id}_mmu_prores_hq.mov",
               poids=base * 7 * Mo, fichiers=1),
        _objet(NATURE_MASTER, f"{lot_id}_mmu_dnxhr_hqx.mov",
               f"outputs/{lot_id}_mmu_dnxhr_hqx.mov",
               poids=base * 11 * Mo, fichiers=1),
        _objet(NATURE_PLANCHE, f"demo_{lot_id}_6f-pay.pdf",
               f"planches/demo_{lot_id}_6f-pay.pdf",
               poids=base * 3 * Mo, fichiers=1),
        _objet(NATURE_PLANCHE, f"demo_{lot_id}_6f-pay_v2.pdf",
               f"planches/demo_{lot_id}_6f-pay_v2.pdf",
               poids=base * 5 * Mo, fichiers=1),
        _scan(f"{lot_id}_scan", base * 13 * Mo, 4, lot_id,
              base * 200 * Mo, base * 20),
        _scan(f"{lot_id}_scan_v2", base * 17 * Mo, 6, f"{lot_id}_v2",
              base * 300 * Mo, base * 30),
    ])


def _inventaire(orphelins=()) -> InventaireDuProjet:
    """TROIS rushes, la cible usuelle AU MILIEU, et les deux bords occupes.

    `a-premier` en tete et `z-dernier` en queue ne sont pas decoratifs : la
    cible au milieu demasque un `find` fautif, elle ne demasque **pas** un
    balayage tronque, qui est un autre mode de panne (regle des fabriques,
    point 4). Leurs lots portent des valeurs distinctes de celles du milieu.
    """
    return InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="projet_demo",
        rushes=(
            _objet(NATURE_RUSH, "a-premier",
                   enfants=[_lot_riche("a-premier_25", base=2)]),
            _objet(NATURE_RUSH, "plan-04",
                   enfants=[_lot_riche("plan-04_25", base=1),
                            _lot_riche("plan-04_12p5", base=3)]),
            _objet(NATURE_RUSH, "z-dernier",
                   enfants=[_lot_riche("z-dernier_8", base=4)]),
        ),
        orphelins=tuple(orphelins))


def _inventaire_d_un_lot(lot, orphelins=()) -> InventaireDuProjet:
    """Un inventaire a UN SEUL lot, pour isoler une propriete du regroupement.

    Il ne remplace pas :func:`_inventaire` -- qui reste la fabrique par defaut,
    avec ses trois rushes et ses deux de chaque nature -- : il sert les tests
    ou la valeur mesuree doit etre lisible a l'oeil, et ou une seconde famille
    de valeurs brouillerait le nombre plutot que de le mesurer.
    """
    return InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="projet_demo",
        rushes=(_objet(NATURE_RUSH, "plan-04", enfants=[lot]),),
        orphelins=tuple(orphelins))


def _arbre(orphelins=()) -> pi.ArbreDuProjet:
    return pi.ArbreDuProjet.depuis_l_inventaire(_inventaire(orphelins))


def _tout_deplier(arbre: pi.ArbreDuProjet) -> None:
    for noeud in arbre.tous():
        noeud.deplie = True


def _par_nom(arbre: pi.ArbreDuProjet, nom: str, sous: str | None = None,
             nature: str | None = None) -> pi.NoeudAffiche:
    """LE noeud de ce nom, et il doit etre unique dans sa portee.

    `sous` restreint la recherche a un sous-arbre : `scans — 2 scans` existe
    sous CHAQUE lot de la fabrique, et un helper qui rendrait le premier ferait
    passer un test qui vise le troisieme -- exactement le mutant `M25` de la
    story 5.7, dans le banc cette fois.
    """
    portee = list(arbre.tous()) if sous is None else list(
        _par_nom(arbre, sous).parcourir())
    trouves = [n for n in portee if n.nom == nom
               and (nature is None or n.nature == nature)]
    assert len(trouves) == 1, (nom, sous, [n.nom for n in portee])
    return trouves[0]


# ---------------------------------------------------------------------------
# B1 -- la troisieme entree du palier (AC 2.1)
# ---------------------------------------------------------------------------


def test_le_palier_gagne_une_TROISIEME_entree_et_le_menu_la_NOMME():
    """AC 2.1, les deux volets : l'entree existe, et la phrase de menu la dit.

    Le second volet est celui qui manquerait sans qu'on le voie : une entree
    ajoutee au palier sans que `projet_lecture.PHRASES[PROJET]` suive serait
    la seule commande du produit qu'aucun menu n'annonce, et rien ne rougirait.
    """
    from mixed_media_utility.tui import palier_projet, projet_lecture

    cles = [issue.cle for issue in palier_projet.entrees_du_palier().issues]
    assert cles == ["project", "set-default-profile", "reconstruct-project"]
    phrase = projet_lecture.PHRASES[projet_lecture.PROJET]
    assert palier_projet.LIBELLES[palier_projet.ENTREE_MEDIAS] \
        .split()[0].lower() in phrase.lower()


def test_chaque_entree_du_palier_porte_un_LIBELLE_et_une_PHRASE():
    """Volet symetrique : les deux tables couvrent EXACTEMENT les entrees.

    Une entree sans phrase ferait tomber `EcranPalierProjet.lignes` sur un
    `KeyError` a l'ouverture -- c'est-a-dire au pire moment.
    """
    from mixed_media_utility.tui import palier_projet

    cles = {issue.cle for issue in palier_projet.entrees_du_palier().issues}
    assert set(palier_projet.LIBELLES) == cles
    assert set(palier_projet.PHRASES) == cles


# ---------------------------------------------------------------------------
# B2 -- deplier / replier, et la SOMME des descendants (AC 2.2)
# ---------------------------------------------------------------------------


def test_l_arbre_s_ouvre_REPLIE_au_niveau_des_lots():
    """AC 2.2 : les rushes sont deplies, tout ce qui pend d'un lot est replie.

    Un arbre entierement deplie ne tiendrait pas : `E6-1e` en fait la mesure,
    un seul lot deplie remplissant les dix-sept lignes de la zone.
    """
    arbre = _arbre()
    vus = arbre.lignes_visibles()
    assert [n.nature for n in vus] == [
        NATURE_RUSH, NATURE_LOT,
        NATURE_RUSH, NATURE_LOT, NATURE_LOT,
        NATURE_RUSH, NATURE_LOT]


def test_deplier_un_lot_montre_SES_groupes_et_ceux_d_AUCUN_autre():
    """`→` ouvre le noeud sous le curseur, et lui seul.

    La cible est **au milieu** (`plan-04_25`, second rush, premier lot) : un
    depliage fautif qui ouvrirait `racines[0]` resterait vert sur une cible de
    tete.
    """
    arbre = _arbre()
    arbre.viser("plan-04_25")
    assert arbre.deplier() is True
    vus = arbre.lignes_visibles()
    ouverts = [n.nom for n in vus if n.profondeur == 2]
    # L'ordre est celui des maquettes -- frames, planches, masters, scans --,
    # et non celui de `_enfants_du_lot` (frames, masters, planches). Un test
    # qui mesurerait l'ensemble laisserait passer la permutation.
    assert ouverts == ["frames — 10 frames", "planches — 2 planches",
                       "masters — 2 masters", "scans — 2 scans"]
    # `frames` est une ligne de groupe et un OBJET : elle se coche, les trois
    # autres non.
    assert [n.groupe for n in vus if n.profondeur == 2] == [
        False, True, True, True]
    # Et aucun autre lot ne s'est ouvert au passage.
    assert [n.nom for n in vus if n.profondeur == 1] == [
        "a-premier_25", "plan-04_25", "plan-04_12p5", "z-dernier_8"]


def test_replier_un_lot_deja_replie_REMONTE_a_son_parent():
    """`←` sur une feuille n'est pas muette : elle remonte et ferme le parent.

    Sans cela la touche serait indistinguable d'un clavier casse sur tout
    noeud terminal, ce qui est le finding `K1.1a`.
    """
    arbre = _arbre()
    arbre.viser("plan-04_12p5")
    assert arbre.replier() is True
    assert arbre.courant.nom == "plan-04"
    assert arbre.courant.deplie is False


def test_le_poids_d_un_noeud_REPLIE_est_la_somme_de_ses_DESCENDANTS():
    """AC 2.2, mesure sur la fabrique a trois rushes, cible **au milieu**.

    Le poids du rush est compare a la somme calculee **ici**, sur l'inventaire
    du coeur et non sur l'arbre d'affichage : deux fois la meme recette
    rendraient le meme resultat faux.
    """
    inventaire = _inventaire()
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventaire)
    milieu = [r for r in inventaire.rushes if r.nom == "plan-04"][0]
    attendu = sum(n.poids for n in milieu.parcourir())
    assert _par_nom(arbre, "plan-04").poids == attendu
    assert attendu > 0


def test_le_poids_d_un_rush_de_BORD_est_la_somme_de_SES_descendants():
    """Les deux bords, tete ET queue : un balayage tronque ne survit pas.

    Un `for rush in rushes[:-1]` -- ou `[1:]` -- rendrait un poids nul sur
    l'un des deux, et la cible du milieu ne le verrait jamais.
    """
    inventaire = _inventaire()
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventaire)
    for nom in ("a-premier", "z-dernier"):
        attendu = sum(
            n.poids for r in inventaire.rushes if r.nom == nom
            for n in r.parcourir())
        assert _par_nom(arbre, nom).poids == attendu, nom
        assert attendu > 0


def test_la_colonne_d_un_SCAN_dit_ses_pages_et_JAMAIS_son_lot_scanne():
    """Le seul noeud dont la colonne et la remontee different, et il est mesure.

    Sans cette distinction le groupe `scans` additionnerait des frames a des
    pages -- « 250 pages » sur `E6-1e` --, et le total du lot cesserait de
    tomber juste. Les deux valeurs sont comparees dans le meme test parce que
    c'est leur ECART qui est le sujet.
    """
    arbre = _arbre()
    scan = _par_nom(arbre, "plan-04_25_scan", sous="plan-04_25")
    assert scan.fichiers == 4
    assert scan.fichiers_porte == 4 + 20
    groupe = _par_nom(arbre, "scans — 2 scans", sous="plan-04_25")
    assert groupe.fichiers == 4 + 6
    assert groupe.fichiers_porte == 4 + 20 + 6 + 30
    assert groupe.cardinal == "10 pages"


def test_le_cardinal_d_un_LOT_compte_les_objets_et_JAMAIS_les_groupes():
    """`9 objets · 378 f.` d'`E6-1e` : frames, 2 planches, 2 masters, 2 scans,
    2 lots scannes. Les quatre lignes de GROUPE n'en sont pas.

    Compte a la main ici plutot que par la propriete mesuree : additionner
    `noeud.objets` a lui-meme ne mesurerait rien.
    """
    arbre = _arbre()
    lot = _par_nom(arbre, "plan-04_25")
    assert lot.objets == 9
    assert lot.cardinal.startswith(CARDINAL_DESSINE_DU_LOT_RICHE)


def test_un_enfant_de_rush_d_une_AUTRE_nature_ne_DISPARAIT_pas():
    """AC 1.4 un cran plus haut : `_rush_affiche` groupe ce qui n'est pas un lot.

    **La nature choisie n'est pas arbitraire : c'est celle qui a DEJA voyage.**
    `EPIC11-ARB-219` posait le scan sous le rush, `EPIC11-ARB-244` l'a
    redescendu sous son lot -- deux filiations en deux jours pour le meme
    objet. Rien ne garantit qu'un troisieme deplacement n'aura pas lieu, ni
    qu'une nature neuve n'arrivera pas la : cette branche de `_rush_affiche`
    est ce qui fait qu'un tel objet est MAL RANGE plutot qu'INVISIBLE, et un
    dossier d'images invisible est le sujet meme de la story.

    Elle etait, jusqu'ici, une surface que la docstring PROMETTAIT et qu'aucun
    banc ne touchait -- le coeur ne posant plus rien la, aucun autre test ne
    peut l'atteindre par accident.
    """
    egare = _scan("hors-lot_scan", 13 * Mo, 4, "hors-lot", 200 * Mo, 20)
    inventaire = InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="projet_demo",
        rushes=(_objet(NATURE_RUSH, "plan-04",
                       enfants=[_lot_riche("plan-04_25"), egare]),))
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventaire)

    # Il forme un GROUPE sous le rush, apres les lots, et il porte son scan.
    rush = _par_nom(arbre, "plan-04")
    natures = [enfant.nature for enfant in rush.enfants]
    assert natures == [NATURE_LOT, NATURE_SCAN], natures
    groupe = rush.enfants[1]
    assert groupe.groupe is True
    assert groupe.nom == "scans — 1 scan", groupe.nom
    assert [petit.nom for petit in groupe.enfants] == ["hors-lot_scan"]

    # Et il PESE dans le rush : un objet range ailleurs reste compte.
    assert rush.poids_porte == (_par_nom(arbre, "plan-04_25").poids_porte
                                + 13 * Mo + 200 * Mo)


# ---------------------------------------------------------------------------
# B3 -- la position se verifie sur la liste que le CODE parcourt
# ---------------------------------------------------------------------------


def test_viser_un_noeud_le_trouve_sur_la_liste_QUE_LE_CODE_PARCOURT():
    """B3 : jamais sur celle que la fabrique ecrit.

    `rang()` balaye `lignes_visibles()`, qui est ce que l'ecran dessine. Un
    banc qui viserait par indice dans sa propre fabrique mesurerait sa
    fabrique -- et resterait vert sur un arbre rendu dans un autre ordre.
    """
    arbre = _arbre()
    vus = arbre.lignes_visibles()
    for cible in ("a-premier", "plan-04_12p5", "z-dernier"):
        rang = arbre.rang(cible)
        assert rang is not None, cible
        assert vus[rang].nom == cible


def test_le_curseur_ne_sort_JAMAIS_de_l_arbre():
    """Les deux bords, et la sortie par le haut autant que par le bas."""
    arbre = _arbre()
    for _ in range(50):
        arbre.deplacer(1)
    assert arbre.curseur == len(arbre.lignes_visibles()) - 1
    for _ in range(50):
        arbre.deplacer(-1)
    assert arbre.curseur == 0


def test_un_GROUPE_se_coche_depuis_ARB264_et_ne_coche_PAS_ses_membres():
    """`EPIC11-ARB-264` retourne ce test, et le motif de l'ancien tombe avec.

    Il mesurait « un groupe ne se coche pas », au motif que
    `remove_project_element` n'a aucune cible qui le vise. C'est toujours vrai
    du coeur mono-cible -- et sans effet depuis que `remove_project_group`
    porte les N appels. Le constat d'Egan du 2026-09-06 etait litteralement
    « planches (l'ensemble) et masters (l'ensemble d'un lot) ne sont pas
    selectionnables ».

    **Le second volet est le plus important** : cocher le groupe ne coche PAS
    ses membres. Propager la coche ferait `coches` de cardinal N+1 pour un seul
    geste, donc ferait tomber `visee()` dans sa branche « plusieurs coches » --
    l'inverse de ce que l'arbitrage ouvre.
    """
    arbre = _arbre()
    arbre.viser("plan-04_25")
    arbre.deplier()
    arbre.viser("planches — 2 planches")
    assert arbre.basculer() is True
    assert [n.nom for n in arbre.coches] == ["planches — 2 planches"]
    arbre.viser("plan-04_25")
    assert arbre.basculer() is True
    assert [n.nom for n in arbre.coches] == [
        "plan-04_25", "planches — 2 planches"]


def test_basculer_sur_un_arbre_VIDE_rend_faux():
    """Le seul refus qui reste, et il n'est pas un refus : c'est l'absence
    d'objet. Sans ce volet, `basculer` pourrait rendre vrai sur `None` et
    personne ne le verrait."""
    arbre = pi.ArbreDuProjet([])
    assert arbre.courant is None
    assert arbre.basculer() is False


# ---------------------------------------------------------------------------
# B4 -- les deux vocabulaires d'etat, LUS du coeur (AC 2.4)
# ---------------------------------------------------------------------------


def test_les_etats_de_l_ecran_sont_EXACTEMENT_ceux_du_coeur():
    """AC 2.4, dans les DEUX sens.

    L'ecran ne connait aucun troisieme etat -- un « avertissement » invente ici
    ferait promettre a l'ecran une couleur que le produit ne sait pas rendre --
    et il n'en oublie aucun : un etat du coeur sans projection ferait tomber
    `_glyphe_d_etat` sur un `KeyError`, a l'affichage.
    """
    projetes = set(pi._NOM_D_ETAT) | {ETAT_PRESENT}
    assert projetes == set(ETATS)
    assert set(pi._NOM_D_ETAT.values()) <= set(jetons.NOMS_D_ETAT)


def test_un_objet_DECLARE_ABSENT_porte_sa_croix_et_le_chemin_attendu():
    """AC 2.4 : le glyphe sur la ligne, le chemin attendu en ligne d'etat.

    C'est ce qui remplace `E6-1b` (`EPIC11-ARB-217`) : le CHEMIN ATTENDU,
    seule chose que l'ecran des ecarts disait de plus, se lit ici.
    """
    inventaire = _inventaire()
    lot = inventaire.rushes[1].enfants[0]
    absente = _objet(NATURE_PLANCHE, "demo_plan-04_25_6f-pay_v3.pdf",
                     "planches/demo_plan-04_25_6f-pay_v3.pdf",
                     etat=ETAT_DECLARE_ABSENT)
    lot = ObjetInventorie(nature=lot.nature, nom=lot.nom, chemin=lot.chemin,
                          etat=lot.etat, enfants=lot.enfants + (absente,))
    rush = ObjetInventorie(nature=NATURE_RUSH, nom="plan-04", chemin=None,
                           etat=ETAT_PRESENT, enfants=(lot,))
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        InventaireDuProjet(dossier=Path("/nulle-part"), project_id="p",
                           rushes=(rush,)))
    _tout_deplier(arbre)
    arbre.viser("demo_plan-04_25_6f-pay_v3.pdf")
    rang = arbre.rang("demo_plan-04_25_6f-pay_v3.pdf")
    assert jetons.GLYPHES["absent"] in arbre.ligne(rang)
    etat = arbre.ligne_de_l_ecart()
    assert pi.ETAT_DE_L_OBJET_ABSENT in etat
    assert "planches/" in etat


def test_un_objet_NON_DECLARE_porte_son_triangle_et_sa_mention():
    """L'autre vocabulaire, et il est different du premier -- glyphe ET mots.

    Deux etats qui rendraient le meme glyphe detruiraient le second canal de
    `DESIGN.md` section 6 : la couleur seule ne porte jamais l'information.
    """
    orphelin = _objet(NATURE_SCAN, "sans-parent_scan", "scans/sans-parent_scan",
                      etat=ETAT_NON_DECLARE, poids=9 * Mo, fichiers=3)
    arbre = _arbre(orphelins=[orphelin])
    _tout_deplier(arbre)
    arbre.viser(f"sans-parent_scan · {pi.MENTION_NON_DECLARE}")
    ligne = arbre.ligne(arbre.curseur)
    assert jetons.GLYPHES["substitute"] in ligne
    assert pi.MENTION_NON_DECLARE in ligne
    assert pi.ETAT_DE_L_OBJET_NON_DECLARE in arbre.ligne_de_l_ecart()


def test_un_orphelin_SANS_ancre_est_rendu_en_QUEUE_et_jamais_tu():
    """AC 1.4 remonte a l'ecran : ce que rien ne montre n'existe pas.

    Un orphelin dont la tige ne designe aucun noeud declare n'a pas de place
    dans l'arbre. Le taire serait exactement la panne que la story existe pour
    fermer -- « un dossier d'images qui pese sur le disque et qu'aucun ecran ne
    montre ».
    """
    orphelin = _objet(NATURE_SCAN, "sans-parent_scan", "scans/sans-parent_scan",
                      etat=ETAT_NON_DECLARE, poids=9 * Mo, fichiers=3)
    arbre = _arbre(orphelins=[orphelin])
    noms = [n.nom for n in arbre.tous()]
    assert any("sans-parent_scan" in nom for nom in noms), noms
    assert arbre.racines[-1].groupe is True
    # **Il garde SON nom**, il n'est pas fondu dans le libelle de sa nature :
    # un orphelin est precisement l'objet dont le nom est la seule information
    # disponible.
    assert arbre.racines[-1].enfants[0].nom \
        == f"sans-parent_scan · {pi.MENTION_NON_DECLARE}"


# ---------------------------------------------------------------------------
# La GREFFE des orphelins -- exacte, jamais approchee
# ---------------------------------------------------------------------------


def test_un_orphelin_dont_la_TIGE_egale_un_lot_declare_devient_SA_version():
    """L'arbitrage d'Egan du 2026-09-05, applique par la regle des versions.

    Ce n'est pas une ressemblance : la tige est lue par
    `naming.rang_du_fragment_de_version` et retiree par
    `format_version_suffix`, les deux seules recettes du depot.
    """
    orphelins = [
        _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_v2",
               "extract-frames/plan-04_25_v2", etat=ETAT_NON_DECLARE,
               poids=42 * Mo, fichiers=7),
        _objet(NATURE_SCAN, "plan-04_25_v2", "scans/plan-04_25_v2",
               etat=ETAT_NON_DECLARE, poids=8 * Mo, fichiers=2),
    ]
    arbre = _arbre(orphelins=orphelins)
    greffe = _par_nom(arbre, f"plan-04_25_v2 · {pi.MENTION_NON_DECLARE}",
                      sous="plan-04", nature=NATURE_LOT)
    assert greffe.nature == NATURE_LOT
    assert greffe.profondeur == 1
    assert greffe.objets == 2
    assert greffe.fichiers == 9
    parent = pi._parent_de(arbre.racines, greffe)
    assert parent.nom == "plan-04"


def test_un_orphelin_a_TIGE_AMBIGUE_ne_se_greffe_PAS():
    """Deux noeuds declares du meme nom laissent l'orphelin a plat.

    Choisir l'un des deux serait la filiation devinee que
    `project_maintenance` refuse : « un lien qui designe un autre lot ne se
    devine pas par ressemblance de nom ».
    """
    # Le meme nom de lot sous deux rushes differents : le manifeste l'interdit,
    # le disque non, et c'est le disque que cet ecran lit.
    inventaire = InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="p",
        rushes=(_objet(NATURE_RUSH, "r-a", enfants=[_lot_riche("meme", 1)]),
                _objet(NATURE_RUSH, "r-b", enfants=[_lot_riche("meme", 2)])),
        orphelins=(_objet(NATURE_FRAMES_EXTRAITES, "meme_v2",
                          "extract-frames/meme_v2", etat=ETAT_NON_DECLARE,
                          poids=Mo, fichiers=1),))
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventaire)
    greffes = [n for n in arbre.tous() if n.nom.startswith("meme_v2")]
    # Il existe -- il n'est pas avale --, et il est en QUEUE, hors des rushes.
    assert len(greffes) == 1, [n.nom for n in arbre.tous()]
    assert greffes[0] not in list(arbre.racines[0].parcourir())
    assert greffes[0] not in list(arbre.racines[1].parcourir())
    assert arbre.racines[-1].groupe is True


def test_un_orphelin_de_RANG_D_ORIGINE_ne_se_greffe_pas():
    """Sans fragment de version, il n'y a pas de tige a lire.

    `rang_du_fragment_de_version` rend `1` pour tout ce qui n'est pas un rang
    -- `_v0`, `_v100`, `_v02`, `_vx` --, et un nom qui se termine ainsi est le
    nom d'une origine, pas une version. Greffer dessus rattacherait un objet a
    un homonyme.
    """
    orphelin = _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_vx",
                      "extract-frames/plan-04_25_vx", etat=ETAT_NON_DECLARE,
                      poids=Mo, fichiers=1)
    assert naming.rang_du_fragment_de_version("plan-04_25_vx") \
        == version_ranks.RANG_ORIGINE
    arbre = _arbre(orphelins=[orphelin])
    assert arbre.racines[-1].groupe is True
    reste = _par_nom(arbre, f"plan-04_25_vx · {pi.MENTION_NON_DECLARE}")
    assert reste.profondeur == 1
    # Il n'est sous AUCUN rush : sa tige ne designe rien.
    assert all(reste not in list(r.parcourir())
               for r in arbre.racines if r.nature == NATURE_RUSH)


def test_la_greffe_RESOMME_le_lot_et_le_rush_qui_la_recoivent():
    """Un lot qui gagne une version gagne son poids **avec**.

    Une ligne de rush qui garderait le total d'avant ferait mentir la seule
    colonne qui dise ce qu'une suppression toucherait. Mesure sur l'ECART
    avant/apres, jamais sur une valeur absolue recopiee.
    """
    avant = _par_nom(_arbre(), "plan-04").poids
    orphelin = _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_v2",
                      "extract-frames/plan-04_25_v2", etat=ETAT_NON_DECLARE,
                      poids=42 * Mo, fichiers=7)
    apres = _par_nom(_arbre(orphelins=[orphelin]), "plan-04")
    assert apres.poids == avant + 42 * Mo
    assert apres.cardinal.endswith("f.")


def test_tige_et_rang_lit_les_DEUX_recettes_du_depot():
    """Volet symetrique de la greffe : la recette est bien celle du depot.

    Une tige calculee par une expression ecrite dans l'ecran serait une seconde
    convention sur `_vN`, exactement ce qu'`io.naming` existe pour empecher.
    """
    for rang in (2, 9, 99):
        nom = f"plan-04_25{naming.format_version_suffix(rang)}"
        assert pi.tige_et_rang(nom) == ("plan-04_25", rang)
    assert pi.tige_et_rang("plan-04_25") == ("plan-04_25",
                                             version_ranks.RANG_ORIGINE)


# ---------------------------------------------------------------------------
# Le VOCABULAIRE des groupes -- lu du coeur, ou declare et NOMME
# ---------------------------------------------------------------------------


def test_le_vocabulaire_declare_est_EXACTEMENT_celui_que_le_coeur_NE_REND_PAS():
    """La partition, dans les deux sens -- c'est une DETTE, pas un choix.

    `project_inventory._libelles` derive le singulier de l'identifiant, donc il
    ne peut rendre ni « frames » ni « lot scanné ». Le jour ou le coeur porte
    le mot accentue, ce test rougit et la table se vide : c'est ce qui empeche
    la dette de dormir.
    """
    assert set(pi.GROUPES_DECLARES) & set(pi.NATURES_AU_LIBELLE_DU_COEUR) == set()
    for nature in pi.NATURES_AU_LIBELLE_DU_COEUR:
        assert pi.nom_du_groupe(nature) == libelles_de_nature(nature)[1]
        assert pi.libelles_du_contenu(nature) == libelles_de_nature(nature)
    for nature, (nom, singulier, pluriel) in pi.GROUPES_DECLARES.items():
        # Le coeur rend bien AUTRE CHOSE : sans ce volet, la table pourrait
        # recopier le mot du coeur et rester verte pour rien.
        assert libelles_de_nature(nature) != (singulier, pluriel)
        assert pi.nom_du_groupe(nature) == nom


def test_chaque_nature_groupable_a_un_LIBELLE_et_l_ordre_les_couvre_toutes():
    """Volet symetrique : aucune nature d'objet ne sort de la table.

    Une nature absente d'`ORDRE_DES_GROUPES` n'est pas avalee -- elle est
    posee en queue --, mais elle sortirait avec un libelle derive du coeur, et
    l'ecart doit se voir ici plutot qu'a l'ecran.
    """
    groupables = set(NATURES) - {NATURE_RUSH, NATURE_LOT}
    assert set(pi.ORDRE_DES_GROUPES) == groupables
    for nature in pi.ORDRE_DES_GROUPES:
        assert pi.nom_du_groupe(nature)
        assert len(pi.libelles_du_contenu(nature)) == 2


def test_l_accord_du_contenu_ne_calcule_JAMAIS_un_pluriel():
    """`1 master`, `2 masters`, `0 scan`, `1 frame scannée`.

    Un `+ "s"` mecanique rendrait « 2 lot scannes » -- un pluriel calcule sur
    un groupe nominal accorde le dernier mot et jamais le premier, defaut deja
    paye dans `cli.py` (« les jeu de framess posterieurs »).
    """
    assert pi.accorder_le_contenu(1, NATURE_MASTER) == "1 master"
    assert pi.accorder_le_contenu(2, NATURE_MASTER) == "2 masters"
    assert pi.accorder_le_contenu(0, NATURE_SCAN) == "0 scan"
    assert pi.accorder_le_contenu(1, NATURE_LOT_SCANNE) == "1 frame scannée"
    assert pi.accorder_le_contenu(2, NATURE_LOT_SCANNE) == "2 frames scannées"
    assert pi.accorder_le_contenu(1204, NATURE_FRAMES_EXTRAITES) \
        == "1 204 frames"


def test_un_poids_NUL_rend_le_glyphe_neutre_et_jamais_zero_octet():
    """`·` et non `0 o` : « non renseigne, sans objet ».

    Un `0 o` se lirait comme un fichier vide, qui est une autre chose -- et
    c'est ce que `E6-1` pose sur la planche declaree-absente comme sur le rush
    sans lot.
    """
    assert pi.poids_lisible(0) == jetons.GLYPHES["neutre"]
    assert pi.poids_lisible(-1) == jetons.GLYPHES["neutre"]
    assert pi.poids_lisible(770 * Mo) == "770 Mo"


def test_un_SCAN_se_compte_en_pages_et_le_reste_en_fichiers():
    """« Un scan compte pour UN, jamais par page » (Egan, porte par `E6-1`).

    Les deux unites dans le meme test : c'est leur difference qui est mesuree,
    et une recette qui rendrait « f. » partout passerait la moitie.
    """
    assert pi.cardinal_lisible(4, NATURE_SCAN) == "4 pages"
    assert pi.cardinal_lisible(1, NATURE_SCAN) == "1 page"
    assert pi.cardinal_lisible(62, NATURE_FRAMES_EXTRAITES) == "62 f."
    assert pi.cardinal_lisible(1204, NATURE_LOT) == CARDINAL_DESSINE_A_QUATRE_CHIFFRES


# ---------------------------------------------------------------------------
# B5 -- la grille, le repli ASCII, et les colonnes des maquettes
# ---------------------------------------------------------------------------


def test_les_colonnes_de_l_arbre_font_EXACTEMENT_la_zone_utile():
    """5 + 46 + 17 + 8 = 76, la largeur utile de la grille 80x24.

    Les quatre constantes sont relevees sur les maquettes ; leur SOMME, elle,
    est une propriete du cadre, et c'est la seule chose qui garantisse qu'une
    ligne pleine ne deborde pas.
    """
    assert (pi.TETE_ARBRE + pi.NOM_ARBRE + pi.FICHIERS_ARBRE
            + pi.POIDS_ARBRE) == jetons.largeur_utile()


def test_la_hauteur_de_l_arbre_est_DERIVEE_de_la_grille():
    """Le titre et ses deux respirations prennent trois lignes de la zone.

    Une hauteur recopiee de la maquette figerait une place perdue le jour ou
    le cadre change -- et `E6-1c` en dessine justement une de douze la ou le
    budget en rend quatorze.
    """
    assert pi.HAUTEUR_ARBRE == jetons.hauteur_centrale() - 3


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_aucune_ligne_de_l_arbre_ne_DEBORDE_dans_les_deux_regimes(ascii_seul):
    """La grille tient sur des noms LONGS, dans les deux regimes.

    Le nom est pousse a la borne du produit (`CANONICAL_ID_MAX_LENGTH`) : c'est
    le cas ou l'elision doit mordre, et c'est celui qu'une fabrique a noms
    courts ne visite jamais.
    """
    long = "x" * naming.CANONICAL_ID_MAX_LENGTH
    inventaire = InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id=long,
        rushes=(_objet(NATURE_RUSH, long,
                       enfants=[_lot_riche(long, base=9)]),))
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventaire)
    _tout_deplier(arbre)
    lignes = arbre.lignes_de_l_arbre(ascii_seul)
    assert len(lignes) == pi.HAUTEUR_ARBRE
    for ligne in lignes:
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(), repr(ligne)


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_les_colonnes_de_droite_restent_ALIGNEES_quel_que_soit_le_regime(
        ascii_seul):
    """Les cardinaux et les poids se calent a DROITE, en colonnes.

    Un `rjust` calerait un champ de dix caracteres sur vingt colonnes des qu'un
    ideogramme y entre, et toutes les colonnes de droite partiraient avec.
    """
    arbre = _arbre()
    _tout_deplier(arbre)
    pleines = [l for l in arbre.lignes_de_l_arbre(ascii_seul) if l.strip()]
    assert pleines
    for ligne in pleines:
        if "…" in ligne or "..." in ligne:
            continue
        assert jetons.colonnes(ligne) <= jetons.largeur_utile()


def test_le_repli_ASCII_ne_laisse_AUCUN_caractere_hors_ASCII():
    """`--ascii` doit rendre le meme SENS, sans un seul octet hors table.

    Un `?` a la place d'un glyphe est le mode de panne que `REPLIS_DE_TEXTE`
    existe pour fermer, et il ne se voit que sur une ligne rendue.
    """
    arbre = _arbre(orphelins=[
        _objet(NATURE_SCAN, "orphelin_scan", "scans/orphelin_scan",
               etat=ETAT_NON_DECLARE, poids=Mo, fichiers=1)])
    _tout_deplier(arbre)
    # La barre de raccourcis est repliee par la coque au dessin, comme celle
    # de tous les ecrans : c'est sa CONSTANTE qui est mesuree, pas son rendu.
    rendus = arbre.lignes_de_l_arbre(True) + [
        arbre.ligne_de_compte(True),
        jetons.replier_ascii(arbre.raccourcis())]
    ecart = arbre.ligne_de_l_ecart(True)
    if ecart:
        rendus.append(ecart)
    for ligne in rendus:
        assert ligne.isascii(), repr(ligne)


def test_la_marque_de_pliage_precede_le_RATTACHEMENT():
    """L'ordre du generateur des maquettes, et il n'est pas libre.

    `└─` dit d'ou la feuille pend, la marque dit si le noeud se plie ; dans
    l'autre ordre le `└─` s'ecarte de trois colonnes de son nom et
    l'indentation cesse de dire la profondeur, qui est la seule chose qu'elle
    dit.
    """
    arbre = _arbre()
    arbre.viser("plan-04_25")
    arbre.deplier()
    arbre.viser("scans — 2 scans")
    arbre.deplier()
    rang = arbre.rang("plan-04_25_scan")
    ligne = arbre.ligne(rang)
    # Un scan est au niveau des OBJETS et se plie quand meme : il porte sa
    # marque, jamais le `└─` d'une feuille (`EPIC11-ARB-244`, seconde passe).
    assert pi.PLIAGE_REPLIE in ligne
    assert jetons.GLYPHES["rattachement"] not in ligne
    arbre.viser("plan-04_25_scan")
    assert arbre.deplier() is True
    attendu = f"lot scanné — {pi.accorder_le_contenu(20, NATURE_LOT_SCANNE)}"
    interne = arbre.ligne(arbre.rang(attendu))
    # Le lot scanne, lui, est une feuille : il porte le `└─` et aucune marque.
    assert jetons.GLYPHES["rattachement"] in interne
    assert pi.PLIAGE_REPLIE not in interne


def test_la_fenetre_montre_les_POINTS_des_deux_cotes_quand_l_arbre_deborde():
    """L'idiome de `X4`, repris : un `…` en tete, un `…` en pied avec sa
    position. La cible est au MILIEU, donc les deux cotes debordent.
    """
    arbre = _arbre()
    _tout_deplier(arbre)
    arbre.viser("plan-04_12p5")
    lignes = arbre.lignes_de_l_arbre()
    assert lignes[0].strip() == "…"
    assert lignes[-1].strip().startswith("…")
    assert " sur " in lignes[-1]


def test_le_rang_du_curseur_est_DONNE_et_jamais_devine():
    """`EPIC11-ARB-47` / `-71` : la peinture recoit le rang, elle ne le cherche
    pas.

    L'auto-detection teste `startswith` sur le glyphe de curseur, et ces lignes
    sont indentees de trois blancs : elle ne trouverait rien, **en silence**.
    """
    arbre = _arbre()
    _tout_deplier(arbre)
    arbre.viser("plan-04_12p5")
    rang = arbre.rang_du_curseur()
    assert rang is not None
    assert jetons.GLYPHES["curseur"] in arbre.lignes_de_l_arbre()[rang]


def test_seules_les_lignes_d_ECART_portent_un_etat_de_couleur():
    """Peindre les lignes `present` ferait un arbre entierement colore, ou
    l'ecart ne se verrait plus -- le contraire de ce que la couleur sert ici.
    """
    arbre = _arbre(orphelins=[
        _objet(NATURE_SCAN, "orphelin_scan", "scans/orphelin_scan",
               etat=ETAT_NON_DECLARE, poids=Mo, fichiers=1)])
    _tout_deplier(arbre)
    arbre.viser(f"orphelin_scan · {pi.MENTION_NON_DECLARE}")
    etats = arbre.etats_des_lignes()
    lignes = arbre.lignes_de_l_arbre()
    assert etats, etats
    for rang, nom in etats.items():
        assert nom in jetons.NOMS_D_ETAT
        assert jetons.GLYPHES[nom] in lignes[rang]


# ---------------------------------------------------------------------------
# La ligne d'etat et la barre de raccourcis (AC 2.3, `EPIC11-ARB-215`)
# ---------------------------------------------------------------------------


def test_la_ligne_d_etat_LIT_l_arbre_et_ne_recalcule_rien():
    """AC 2.3 : « tous deux lus de l'inventaire, jamais recalcules a l'ecran ».

    Les deux chiffres sont confrontes a la somme faite **sur l'inventaire du
    coeur**, pas sur l'arbre : deux fois la meme recette rendraient le meme
    resultat faux.
    """
    inventaire = _inventaire()
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventaire)
    assert arbre.fichiers_total == inventaire.fichiers_total
    assert arbre.poids_total == inventaire.poids_total
    etat = arbre.ligne_de_compte()
    assert "3 rushes" in etat
    assert "4 lots" in etat
    assert pi.grouper_les_milliers(inventaire.fichiers_total) in etat


def test_la_ligne_d_etat_compte_les_ECARTS_des_DEUX_familles():
    """`EPIC11-ARB-217` les a fondues : declare-absent ET non-declare.

    N'en compter qu'une rendrait un nombre plus petit que ce que l'arbre
    montre, sur la ligne meme qui est censee resumer l'arbre.
    """
    absente = _objet(NATURE_PLANCHE, "manquante.pdf", "planches/manquante.pdf",
                     etat=ETAT_DECLARE_ABSENT)
    lot = _objet(NATURE_LOT, "solo", enfants=[absente])
    rush = _objet(NATURE_RUSH, "r", enfants=[lot])
    inventaire = InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="p", rushes=(rush,),
        orphelins=(_objet(NATURE_SCAN, "orphelin", "scans/orphelin",
                          etat=ETAT_NON_DECLARE, poids=Mo, fichiers=1),))
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventaire)
    assert arbre.ecarts == 2
    assert "2 écarts" in arbre.ligne_de_compte()


def test_la_barre_n_annonce_PLUS_Ctrl_L_sur_un_objet_produit_declare_absent():
    """`EPIC11-ARB-263` (Egan par invite, 2026-09-07) : « garder le refus
    nomme mais retirer l'annonce partout ou ce n'est pas actif ».

    **Ce que ce test disait avant, et pourquoi il change.** Il mesurait
    `EPIC11-ARB-215` issue C, qui annonce `Ctrl+L relinker` sur tout objet
    declare absent. Cette regle etait juste sur maquette et fausse en fait :
    une planche declaree absente est exactement ce que le coeur ne sait PAS
    relinker. `rushes[].source_path` est la SEULE exception a l'invariant
    « aucun chemin absolu au manifeste » (`EPIC7-ARB-41`) ; les cinq autres
    natures vivent dans le projet et leur emplacement est CALCULE par
    `io/project_layout`, donc il n'y a aucune reference a reparer.

    **L'exclusion `Ctrl+D` / `Ctrl+L`, elle, reste mesuree** -- c'est elle qui
    fait tenir la ligne sous les 76 colonnes de la zone utile, et l'annoncer
    ensemble valait 105 colonnes au pire cas reel.

    **Et le refus se prononce quand meme si la touche est frappee** : c'est la
    seconde moitie de l'arbitrage, sans laquelle un operateur qui a appris le
    raccourci sur un rush tomberait dans le vide. Les deux moities dans le
    meme test, parce qu'aucune ne vaut sans l'autre -- retirer l'annonce SANS
    le refus est precisement l'option qu'Egan n'a pas prise.
    """
    absente = _objet(NATURE_PLANCHE, "manquante.pdf", "planches/manquante.pdf",
                     etat=ETAT_DECLARE_ABSENT)
    lot = _objet(NATURE_LOT, "solo", enfants=[
        _objet(NATURE_FRAMES_EXTRAITES, "solo", "extract-frames/solo",
               poids=Mo, fichiers=1),
        absente])
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="p",
        rushes=(_objet(NATURE_RUSH, "r", enfants=[lot]),)))
    _tout_deplier(arbre)
    arbre.viser("solo")
    assert arbre.raccourcis() == pi.RACCOURCIS_INVENTAIRE_DECLARER
    # Le cas qui change : une planche DECLAREE ABSENTE n'annonce plus la
    # touche, parce que rien ne la relinkerait.
    arbre.viser("manquante.pdf")
    assert arbre.raccourcis() == pi.RACCOURCIS_INVENTAIRE_DECLARER
    assert "Ctrl+D" not in pi.RACCOURCIS_INVENTAIRE_RELINKER
    assert "Ctrl+L" not in pi.RACCOURCIS_INVENTAIRE_DECLARER

    # La seconde moitie de l'arbitrage, sur CE noeud-la : la touche frappee
    # ici n'est pas muette. Sans cette assertion, retirer l'annonce ET le
    # gestionnaire rendrait ce test vert -- et ce n'est pas ce qu'Egan a
    # choisi.
    ecran = pi.EcranInventaireDuProjet(arbre, relinker=lambda *_: None)
    assert ecran.traiter("ctrl+l") is True
    assert ecran._message == pi.MOTIF_DU_RELINK_HORS_RUSH.format(
        nature=libelles_de_nature(NATURE_PLANCHE)[0])


@pytest.mark.parametrize("ligne", [pi.RACCOURCIS_INVENTAIRE_DECLARER,
                                   pi.RACCOURCIS_INVENTAIRE_RELINKER,
                                   pi.RACCOURCIS_LECTURE])
@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_budget_de_colonnes_des_raccourcis_TIENT(ligne, ascii_seul):
    """AC 5.3 : le budget mesure, dans les DEUX regimes.

    Le repli ASCII rallonge (`⏎` devient `Entree`) : une ligne qui tient en
    UTF-8 peut deborder repliee, et c'est le cas que le commentaire
    `MESURE:` doit avoir vu.
    """
    texte = jetons.replier_ascii(ligne) if ascii_seul else ligne
    assert jetons.colonnes(texte) <= jetons.largeur_utile(), texte


# ---------------------------------------------------------------------------
# L'ecran monte : `E6-1`, `E6-1a`, et les touches
# ---------------------------------------------------------------------------


def _app(ecran, projet="projet_demo", **kwargs) -> CoqueTui:
    """La coque du depot, montee sur un palier temoin puis sur l'ecran.

    Meme geste que `test_ecran_ateliers` : le temoin tient la place du palier
    Projet, faute de quoi `Échap` n'aurait nulle part ou remonter.
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"), ecran],
                    contexte=Contexte(projet=projet), **kwargs)


def _monte(app, scenario, banc):
    """Descendre au palier de l'ecran, puis derouler le scenario."""
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def test_l_ecran_sans_arbre_est_E6_1a_et_n_annonce_QUE_F1(banc):
    """`E6-1a` : le rotor, et aucune touche qui n'agisse.

    « La ligne de raccourcis ne porte pas d'annulation, pour le meme motif que
    `E6-2c` : aucun point d'interruption n'existe dans ce chemin. Une touche
    annoncee qui n'agit pas est le finding `I8`. »
    """
    ecran = pi.EcranInventaireDuProjet()

    async def scenario(pilote):
        return ecran.lignes(), ecran.raccourcis, ecran.etat(), \
            ecran.objet_du_bandeau()

    lignes, raccourcis, etat, bandeau = _monte(_app(ecran), scenario, banc)
    assert raccourcis == pi.RACCOURCIS_LECTURE
    assert etat == pi.ETAT_DE_LA_LECTURE
    assert MENTION_DESSINEE_DE_LA_LECTURE in bandeau
    assert any(pi.PHRASE_DE_LECTURE in ligne for ligne in lignes)
    assert any(jetons.ROTOR[0] in ligne for ligne in lignes)


def test_aucune_touche_n_agit_PENDANT_la_lecture():
    """Volet symetrique du test precedent : ce qui n'est pas annonce n'agit pas.

    Une touche qui agirait sans etre annoncee est le symetrique exact du
    finding `I8`, et il ne se voit que si on l'essaie.
    """
    ecran = pi.EcranInventaireDuProjet()
    for touche in ("up", "down", "left", "right", "space", "delete",
                   "ctrl+a", "ctrl+d", "ctrl+l"):
        assert ecran.traiter(touche) is False, touche


def test_l_ecran_avec_arbre_est_E6_1_et_son_bandeau_LIT_l_arbre(banc):
    """AC 2.3 : le bandeau porte les deux mesures, lues et non recalculees."""
    arbre = _arbre()
    ecran = pi.EcranInventaireDuProjet(arbre)

    async def scenario(pilote):
        return ecran.objet_du_bandeau(), ecran.etat(), ecran.lignes()

    bandeau, etat, lignes = _monte(_app(ecran), scenario, banc)
    assert bandeau.startswith(PREFIXE_DESSINE_DU_BANDEAU)
    assert pi.grouper_les_milliers(arbre.fichiers_total) in bandeau
    assert pi.poids_lisible(arbre.poids_total) in bandeau
    assert etat == arbre.ligne_de_compte()
    assert len(lignes) <= jetons.hauteur_centrale()
    assert lignes[-1] == arbre.lignes_de_l_arbre()[-1]


def test_la_zone_centrale_TIENT_sa_hauteur_LIGNE_A_LIGNE(banc):
    """Le defaut que `Composition` ferme : `textual` coupe par le bas, en
    silence, et aucun banc de largeur ne le voit.

    **Ce test asserte la zone ENTIERE, pas seulement son cardinal.** Un
    cardinal seul survit a une permutation, a une respiration de trop
    compensee par une ligne d'arbre de moins, et a un `HAUTEUR_ARBRE` faux
    d'autant : trois mutants qu'un `len(...) == 17` laisserait passer. La
    composition d'`E6-1` est donc epelee -- blanc, titre, blanc, puis les
    quatorze lignes d'arbre --, et la DERNIERE ligne de la zone est confrontee
    a la derniere ligne d'arbre, qui est ce que `textual` couperait.

    **Ecart nomme, et il n'est pas corrige ici** : les maquettes ne s'accordent
    pas entre elles sur la fenetre d'arbre -- `E6-1` en dessine 14, `E6-1d` 13
    plus un blanc, `E6-1c` 12 plus deux blancs, `E6-1e` 16 sans aucun blanc.
    Seul le 14 d'`E6-1` tombe du budget quand les deux respirations tiennent,
    et c'est celui que le code derive. Les trois autres sont au registre de la
    story.
    """
    arbre = _arbre()
    _tout_deplier(arbre)
    ecran = pi.EcranInventaireDuProjet(arbre)

    async def scenario(pilote):
        return ecran.composer(80, False)

    lignes, rang, etats = _monte(_app(ecran), scenario, banc)
    lignes_d_arbre = arbre.lignes_de_l_arbre()
    assert len(lignes) == jetons.hauteur_centrale()
    assert lignes[0].strip() == ""
    assert lignes[1].strip() == arbre.titre
    assert lignes[2].strip() == ""
    assert lignes[3:] == lignes_d_arbre
    #: La derniere ligne de la zone EST la derniere ligne d'arbre : c'est
    #: exactement ce qu'une zone trop haute perdrait, et en silence.
    assert lignes[-1] == lignes_d_arbre[-1]


def test_Suppr_appelle_le_rappel_sur_un_OBJET_COMME_sur_un_GROUPE():
    """AC 4.1 : l'ecran monte un point de jugement, il ne supprime rien.

    **RENOMME le 2026-09-07** (finding `C2-8`). Il s'appelait
    `test_Suppr_sur_un_OBJET_appelle_le_rappel_et_sur_un_GROUPE_non`, et son
    nom affirmait donc l'inverse exact de ce que son corps mesure depuis
    qu'`EPIC11-ARB-264` a rendu le groupe supprimable -- le corps avait ete
    retourne et commente, le nom non. Un nom de banc est lu par la liste des
    verdicts bien plus souvent que son corps.

    Les deux volets ensemble, parce que c'est leur difference qui compte : un
    `_retirer` qui rendrait toujours `True` passerait le premier tout seul --
    ce qui reste vrai, la difference se lisant desormais sur le RAPPEL et sur
    le MESSAGE plutot que sur la valeur rendue.

    **Ce que ce test affirmait avant le 2026-09-06, garde plutot qu'efface** :
    « `assert ecran.traiter("delete") is False` » sur un groupe. C'etait le
    finding `F5` de la couche 1 : `traiter` rendant faux, `on_key` ne faisait
    ni `stop()` ni `rafraichir()`, donc **rien ne se passait et rien ne le
    disait**, alors que les deux lignes de raccourcis annoncent `Suppr
    retirer` inconditionnellement. La touche est desormais consommee et le
    refus se lit sur la ligne d'etat ; ce qui n'a pas bouge d'un iota, c'est
    qu'aucun rappel de suppression n'est appele sur un groupe.
    """
    arbre = _arbre()
    arbre.viser("plan-04_25")
    arbre.deplier()
    vises = []
    ecran = pi.EcranInventaireDuProjet(arbre, supprimer=vises.append)
    arbre.viser("planches — 2 planches")
    assert ecran.traiter("delete") is True
    # **RETOURNE par `EPIC11-ARB-264`** : le groupe atteint desormais le rappel
    # comme un objet, et c'est `ouvrir_la_suppression` qui le deplie en N
    # cibles. Ce que l'ancienne redaction mesurait -- « aucun rappel n'est
    # appele sur un groupe » -- etait la consequence du refus, pas une
    # propriete a tenir.
    assert [n.nom for n in vises] == ["planches — 2 planches"]
    assert ecran._message == ""
    vises.clear()
    arbre.viser("plan-04_25")
    assert ecran.traiter("delete") is True
    assert [n.nom for n in vises] == ["plan-04_25"]
    # Et le message ne SURVIT pas a la touche suivante : il dirait alors un
    # refus qui n'a pas eu lieu.
    assert ecran._message == ""


def test_les_touches_de_l_arbre_DELEGUENT_au_modele():
    """Le clavier ne calcule rien : il appelle le modele, qui est mesure seul.

    La cible du depliage est **au milieu** ; un `traiter` qui aurait cable
    `racines[0]` resterait vert sur une cible de tete.
    """
    arbre = _arbre()
    ecran = pi.EcranInventaireDuProjet(arbre)
    assert ecran.traiter("down") is True
    assert arbre.curseur == 1
    arbre.viser("plan-04_25")
    assert ecran.traiter("right") is True
    assert arbre.courant.deplie is True
    assert ecran.traiter("space") is True
    assert [n.nom for n in arbre.coches] == ["plan-04_25"]
    assert ecran.traiter("left") is True
    assert arbre.courant.deplie is False
    assert ecran.traiter("f5") is False


# ---------------------------------------------------------------------------
# Les TROIS gestes de media -- deux cables, un filet (lot H, 2026-09-07)
#
# **La fabrique de cette section a ses rushes ABSENTS aux trois places**
# (regle des fabriques, points 2 et 4) : `a-premier` en tete, `plan-04` au
# milieu, `z-dernier` en queue. Un `Ctrl+L` cable sur « le premier rush delie »
# resterait vert sur une cible de tete ; un balayage tronque resterait vert sur
# une cible de milieu. Les deux modes de panne sont mesures.
# ---------------------------------------------------------------------------


def _inventaire_a_rushes(non_declares=()) -> InventaireDuProjet:
    """Les trois rushes de la fabrique, ceux qu'on nomme NON DECLARES.

    **Un noeud de rush ne porte que DEUX etats, et c'est mesure**
    (2026-09-07) : `project_inventory` le construit avec `chemin=None` et
    `etat=ETAT_PRESENT` des qu'il est au manifeste, `ETAT_NON_DECLARE` quand
    il n'est connu que du disque -- il ne regarde **jamais** si le
    `source_path` existe, la source vivant hors du projet. Un rush
    `ETAT_DECLARE_ABSENT` n'existe donc pas, et une fabrique qui en produirait
    mesurerait un arbre que le coeur ne rend pas.
    """
    def rush(nom, lots):
        etat = ETAT_NON_DECLARE if nom in non_declares else ETAT_PRESENT
        return _objet(NATURE_RUSH, nom, etat=etat, enfants=lots)

    return InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="projet_demo",
        rushes=(rush("a-premier", [_lot_riche("a-premier_25", base=2)]),
                rush("plan-04", [_lot_riche("plan-04_25", base=1),
                                 _lot_riche("plan-04_12p5", base=3)]),
                rush("z-dernier", [_lot_riche("z-dernier_8", base=4)])))


def _arbre_a_rushes(non_declares=()) -> pi.ArbreDuProjet:
    return pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_a_rushes(non_declares))


def _viser_le_rush(arbre: pi.ArbreDuProjet, rush_id: str) -> pi.NoeudAffiche:
    """Poser le curseur sur un rush par son IDENTIFIANT, pas par son affichage.

    `ArbreDuProjet.viser` prend le nom **affiche**, et celui d'un rush non
    declare porte sa mention (`z-dernier · non déclaré`). Viser par
    l'identifiant du coeur est ce que fait le produit -- `_relinker_l_objet`
    lit `noeud.cible.nom` --, et c'est la seule cle qui ne change pas avec
    l'etat.
    """
    for rang, noeud in enumerate(arbre.lignes_visibles()):
        if noeud.nature == NATURE_RUSH and noeud.cible.nom == rush_id:
            arbre.curseur = rang
            return noeud
    raise AssertionError(
        f"aucun rush {rush_id!r} ; vus : "
        f"{[n.nom for n in arbre.lignes_visibles()]}")


def test_les_gestes_de_MEDIA_sans_rappel_ne_se_TAISENT_pas(banc):
    """`Ctrl+A`, `Ctrl+D`, `Ctrl+L` sont annonces : ils ne peuvent pas etre muets.

    **Deux des trois sont desormais CABLES** (lot H, 2026-09-07) : ce que ce
    banc mesure sur eux est le REPLI -- un appelant qui construirait
    l'inventaire sans `ajouter=` ni `relinker=` --, pas le parcours, qui a son
    propre banc. Le repli reste ce qu'il etait : la touche NOMME ce qui manque,
    parce qu'« une touche qui ne fait rien et ne dit rien est indistinguable
    d'un clavier casse ».

    `Ctrl+L` vise ici le rush du MILIEU, declare au manifeste : un repli qui
    aurait lu le premier rush aurait rendu le motif de refus au lieu du filet.
    """
    from mixed_media_utility.tui.coque import EcranPasEncore

    attendus = {"ctrl+a": pi.CE_QUI_MANQUE_A_L_AJOUT,
                "ctrl+d": pi.CE_QUI_MANQUE_A_LA_DECLARATION,
                "ctrl+l": pi.CE_QUI_MANQUE_AU_RELINK}
    for touche, phrase in attendus.items():
        arbre = _arbre_a_rushes()
        arbre.viser("plan-04")
        ecran = pi.EcranInventaireDuProjet(arbre)

        async def scenario(pilote, touche=touche):
            ecran.traiter(touche)
            await pilote.pause()
            return pilote.app.screen

        dessus = _monte(_app(ecran), scenario, banc)
        assert isinstance(dessus, EcranPasEncore), touche
        assert dessus.ce_qui_manque == phrase, touche


def test_Ctrl_D_annonce_ce_qui_manque_SANS_echeance_inventee(banc):
    """`EPIC11-ARB-260` : ce qui manque a `Ctrl+D` est un COEUR, pas un dessin.

    L'echeance precedente -- « il arrive avec les ecrans de gestion des medias
    du palier Projet » -- etait annoncee a un operateur qui **est** dans ces
    ecrans, puisqu'il vient d'y frapper la touche. La mesure du 2026-09-07 ne
    trouve aucune commande de coeur qui inscrive au manifeste un objet deja
    present sur le disque ; la phrase le dit desormais elle-meme, et l'ecran ne
    promet plus de date.

    **Le drapeau varie** : l'absence d'echeance doit tenir dans les DEUX
    geometries, sans quoi une ligne pourrait reapparaitre en repli ASCII.
    """
    from mixed_media_utility.tui.coque import EcranPasEncore

    for ascii_seul in (False, True):
        ecran = pi.EcranInventaireDuProjet(_arbre())

        async def scenario(pilote):
            ecran.traiter("ctrl+d")
            await pilote.pause()
            dessus = pilote.app.screen
            return dessus.quand, dessus.lignes()

        quand, lignes = _monte(_app(ecran, ascii_seul=ascii_seul), scenario,
                               banc)
        assert quand == "", ascii_seul
        assert not any("Il arrive avec" in ligne for ligne in lignes), lignes
    assert "coeur" in pi.CE_QUI_MANQUE_A_LA_DECLARATION


def test_la_barre_annonce_Ctrl_L_sur_un_RUSH_DECLARE_et_pas_sur_un_orphelin():
    """La touche est annoncee LA OU ELLE PEUT AGIR (2026-09-07).

    **Ce que la mesure a corrige.** Le rush declare est le SEUL objet que le
    coeur sache relinker (`mmu relink --rush`), et il n'entrait pas dans la
    garde : `project_inventory` lui pose `etat=ETAT_PRESENT` sans jamais
    regarder si son `source_path` existe. `Ctrl+L relinker` etait donc annonce
    sur les planches, masters et scans -- que le coeur ne relinke pas -- et tu
    sur les rushes, qu'il relinke.

    Les trois places sont jouees : un rush declare en **tete** et en
    **queue**, un rush orphelin au **milieu**. L'orphelin retombe sur
    `Ctrl+D`, qui est bien ce qui le declarerait.
    """
    arbre = _arbre_a_rushes(("plan-04",))
    for declare in ("a-premier", "z-dernier"):
        _viser_le_rush(arbre, declare)
        assert arbre.raccourcis() == pi.RACCOURCIS_INVENTAIRE_RELINKER, declare
    _viser_le_rush(arbre, "plan-04")
    assert arbre.raccourcis() == pi.RACCOURCIS_INVENTAIRE_DECLARER


def test_Ctrl_A_appelle_le_parcours_d_ajout_sans_lire_le_CURSEUR():
    """`Ctrl+A` ne vise rien : ce qu'on ajoute n'est pas encore dans l'arbre.

    La cible est posee **en queue** puis **en tete** : un `Ctrl+A` qui aurait
    visite `visee()` aurait refuse sur un groupe ou sur une selection multiple,
    et ce banc-la le verrait.
    """
    for cible in ("z-dernier", "a-premier"):
        prises = []
        arbre = _arbre()
        arbre.viser(cible)
        ecran = pi.EcranInventaireDuProjet(arbre,
                                           ajouter=lambda: prises.append(True))
        assert ecran.traiter("ctrl+a") is True, cible
        assert prises == [True], cible
        assert ecran._message == "", cible


def test_Ctrl_L_relinke_ce_que_l_arbre_DESIGNE_a_CHAQUE_place():
    """`EPIC11-ARB-257` : la selection cochee PRIME sur la ligne active.

    C'est le piege exact d'Egan du 2026-09-06, transpose au relink : un rush
    coche, le curseur reste ailleurs, et le geste part sur ce que l'operateur
    n'a pas designe.

    Les trois places de la fabrique sont jouees -- tete, milieu, queue --, et
    le curseur est **toujours pose ailleurs que sur la cible** : un cablage qui
    lirait `courant` rendrait le mauvais identifiant sur les trois.
    """
    for cible, ailleurs in (("a-premier", "z-dernier"),
                            ("plan-04", "a-premier"),
                            ("z-dernier", "plan-04")):
        prises = []
        arbre = _arbre_a_rushes()
        arbre.viser(cible)
        assert arbre.basculer() is True
        arbre.viser(ailleurs)
        ecran = pi.EcranInventaireDuProjet(arbre, relinker=prises.append)
        assert ecran.traiter("ctrl+l") is True, cible
        assert prises == [cible], (cible, prises)


def test_Ctrl_L_sur_le_seul_curseur_vise_la_ligne_ACTIVE():
    """Sans aucune coche, `Ctrl+L` retombe sur la ligne active.

    Sans ce repli, la touche serait inerte sur un arbre jamais coche -- le
    defaut inverse, et pas un progres (`ArbreDuProjet.visee`).
    """
    prises = []
    arbre = _arbre_a_rushes()
    arbre.viser("z-dernier")
    ecran = pi.EcranInventaireDuProjet(arbre, relinker=prises.append)
    assert ecran.traiter("ctrl+l") is True
    assert prises == ["z-dernier"]


def test_Ctrl_L_refuse_et_le_DIT_sur_les_QUATRE_cibles_impossibles():
    """`EPIC11-ARB-258` : un refus se dit, et aucun n'ouvre le parcours.

    Les quatre regimes, et aucun n'est un blocage sec : la ligne d'etat porte
    le motif, l'arbre ne bouge pas, et le rappel n'est **jamais** appele --
    c'est ce dernier point qui distingue un refus d'un relink silencieux sur
    une autre cible.
    """
    prises = []

    def ecran_sur(arbre):
        return pi.EcranInventaireDuProjet(arbre, relinker=prises.append)

    # 1. plusieurs coches -- le modele est mono-cible de bout en bout.
    arbre = _arbre_a_rushes()
    for nom in ("a-premier", "z-dernier"):
        arbre.viser(nom)
        assert arbre.basculer() is True
    ecran = ecran_sur(arbre)
    assert ecran.traiter("ctrl+l") is True
    assert "2" in ecran._message and "cochés" in ecran._message

    # 2. un GROUPE -- il n'est pas un objet du produit.
    arbre = _arbre_a_rushes()
    _tout_deplier(arbre)
    arbre.viser("planches — 2 planches")
    ecran = ecran_sur(arbre)
    assert ecran.traiter("ctrl+l") is True
    assert ecran._message == pi.MOTIF_DU_GROUPE_NON_RELINKABLE

    # 3. un objet qui n'est PAS un rush -- limite du coeur, nommee.
    arbre = _arbre_a_rushes()
    _tout_deplier(arbre)
    arbre.viser("plan-04_25")
    ecran = ecran_sur(arbre)
    assert ecran.traiter("ctrl+l") is True
    assert ecran._message == pi.MOTIF_DU_RELINK_HORS_RUSH.format(
        nature=libelles_de_nature(NATURE_LOT)[0])

    # 4. un rush ORPHELIN -- connu du disque, absent du manifeste. Il est en
    #    QUEUE, et deux rushes declares le precedent : un cablage qui aurait
    #    lu le premier rush rendrait le parcours au lieu du refus.
    arbre = _arbre_a_rushes(("z-dernier",))
    _viser_le_rush(arbre, "z-dernier")
    ecran = ecran_sur(arbre)
    assert ecran.traiter("ctrl+l") is True
    assert ecran._message == pi.MOTIF_DU_RUSH_NON_DECLARE.format(
        rush_id="z-dernier")

    assert prises == [], prises


def test_les_motifs_de_refus_du_relink_TIENNENT_la_zone_utile():
    """`EPIC11-ARB-21` : rien ne se coupe au plancher de 80 colonnes.

    Les trois motifs portent une valeur variable -- un identifiant, un libelle
    de nature -- et c'est elle qui peut les faire deborder. La plus longue de
    chaque famille est prise, pas une valeur commode : `frames extraites` est
    le libelle le plus long du coeur, et un identifiant de rush realiste en
    fait dix.

    **Le drapeau varie** : un motif qui tiendrait en UTF-8 et deborderait en
    repli ASCII est exactement le defaut de `coque.Palier.bandeau`.
    """
    utile = jetons.largeur_utile(80)
    plus_longue = max((libelles_de_nature(n)[0] for n in NATURES), key=len)
    motifs = [pi.MOTIF_DU_GROUPE_NON_RELINKABLE,
              pi.MOTIF_DU_RELINK_HORS_RUSH.format(nature=plus_longue),
              pi.MOTIF_DU_RUSH_NON_DECLARE.format(rush_id="plan-04_25")]
    for ascii_seul in (False, True):
        for motif in motifs:
            rendu = pi._replie(motif, ascii_seul)
            assert jetons.colonnes(rendu) <= utile, (motif, ascii_seul,
                                                     jetons.colonnes(rendu))


def test_reprendre_RELIT_l_inventaire_quand_le_dossier_est_connu(tmp_path):
    """`EPIC11-ARB-46` : au retour d'une ecriture, l'arbre ne ment pas.

    Depuis que `Ctrl+A` declare et que `Ctrl+L` relinke, revenir sur
    l'inventaire montrait l'arbre d'AVANT -- un rush declare absent de la
    liste, un rush relinke encore marque absent. C'est le defaut `V2-M2`.

    **Le second volet est le symetrique** : sans dossier -- un ecran monte nu
    par un banc --, `reprendre` se contente de redessiner et ne leve pas.
    """
    lus = []

    def inventorier(dossier):
        lus.append(Path(dossier))
        return _inventaire_a_rushes(("z-dernier",))

    ecran = pi.EcranInventaireDuProjet(_arbre(), dossier=tmp_path)
    assert pi.relire_l_inventaire(ecran, tmp_path,
                                  inventorier=inventorier) is True
    assert lus == [tmp_path]
    assert ecran.arbre.raccourcis() is not None

    nu = pi.EcranInventaireDuProjet(_arbre())
    assert nu.dossier is None
    nu.rafraichir = lambda: lus.append("dessine")
    nu.reprendre()
    assert lus[-1] == "dessine"


def test_Suppr_sans_rappel_ne_se_TAIT_pas(banc):
    """Le finding `K1.1a` : un `if ... is not None` sans branche `else`.

    Un rappel optionnel qu'aucun appel n'injecte transforme la touche en
    silence, et la garde structurelle des rappels existe pour l'attraper.
    """
    from mixed_media_utility.tui.coque import EcranPasEncore

    ecran = pi.EcranInventaireDuProjet(_arbre())

    async def scenario(pilote):
        ecran.traiter("delete")
        await pilote.pause()
        return pilote.app.screen

    dessus = _monte(_app(ecran), scenario, banc)
    assert isinstance(dessus, EcranPasEncore)
    assert dessus.ce_qui_manque == pi.CE_QUI_MANQUE_A_LA_SUPPRESSION


# ---------------------------------------------------------------------------
# Contre le VRAI producteur -- et il assert sur CHAQUE famille de valeurs
# ---------------------------------------------------------------------------


def _projet_reel(tmp_path) -> Path:
    """Un projet REEL sur le disque, ecrit par le coeur puis complete.

    Les octets sont **distincts d'un fichier a l'autre** : un poids agrege qui
    prendrait le premier fichier au lieu de la somme rendrait un nombre
    plausible, donc invisible, sur une fabrique a fichiers identiques.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    document = json.loads((chemin / "project.json").read_text(encoding="utf-8"))
    document["rushes"] = [{"rush_id": "a-premier"}, {"rush_id": "plan-04"},
                          {"rush_id": "z-dernier"}]
    document["lots"] = [
        {"lot_id": "a-premier_25", "rush_id": "a-premier",
         "frames_dir": "extract-frames/a-premier_25"},
        {"lot_id": "plan-04_25", "rush_id": "plan-04",
         "frames_dir": "extract-frames/plan-04_25",
         "encoded_masters": [{"path": "outputs/plan-04_25_mmu_prores_hq.mov"}],
         "output_frames_dir": "frames-scannees/plan-04_25"},
        {"lot_id": "z-dernier_8", "rush_id": "z-dernier",
         "frames_dir": "extract-frames/z-dernier_8"},
    ]
    (chemin / "project.json").write_text(json.dumps(document), encoding="utf-8")
    tailles = {
        "extract-frames/a-premier_25/f0.tiff": 11,
        "extract-frames/plan-04_25/f0.tiff": 101,
        "extract-frames/plan-04_25/f1.tiff": 202,
        "extract-frames/z-dernier_8/f0.tiff": 33,
        "outputs/plan-04_25_mmu_prores_hq.mov": 4004,
        "frames-scannees/plan-04_25/s0.tiff": 55,
        # L'ORPHELIN : sur le disque, declare par personne, et version d'un
        # lot declare -- c'est le cas que la greffe doit prendre.
        "extract-frames/plan-04_25_v2/f0.tiff": 707,
    }
    for relatif, octets in tailles.items():
        cible = chemin / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"o" * octets)
    return chemin


def test_l_arbre_bati_sur_le_VRAI_coeur_assert_sur_CHAQUE_famille(tmp_path):
    """`EPIC5-ARB-39` : un test d'integration ne suffit pas s'il n'assert pas.

    Cinq familles de valeurs sont projetees par cet ecran -- la structure, les
    noms, les poids, les cardinaux, les etats -- et chacune est confrontee ici
    a ce que le disque porte reellement. Un test qui se contenterait de « ca ne
    leve pas » survivrait aux trois mutations qu'il est cense attraper.
    """
    chemin = _projet_reel(tmp_path)
    inventaire = inventorier_le_projet(chemin)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventaire)

    # (1) structure : trois rushes declares, dans l'ordre du manifeste.
    assert [r.nom for r in arbre.racines if r.nature == NATURE_RUSH] == [
        "a-premier", "plan-04", "z-dernier"]
    # (2) noms : le master porte SON nom de fichier, jamais un libelle.
    lot = _par_nom(arbre, "plan-04_25", sous="plan-04", nature=NATURE_LOT)
    _tout_deplier(arbre)
    masters = _par_nom(arbre, "masters — 1 master", sous="plan-04_25")
    assert [n.nom for n in masters.enfants] == [
        "plan-04_25_mmu_prores_hq.mov"]
    # (3) poids : la SOMME des octets ecrits, pas le premier fichier.
    #     Le lot DECLARE ne porte que les siens ; la greffe est une VERSION du
    #     lot, donc un lot SOEUR sous le meme rushe -- ses 707 octets remontent
    #     au rushe, jamais au lot dont elle derive. Les deux nombres sont
    #     assertes ensemble : c'est ce qui attrape un poids compte deux fois.
    rush = _par_nom(arbre, "plan-04", nature=NATURE_RUSH)
    assert lot.poids == 101 + 202 + 4004 + 55
    assert rush.poids == 101 + 202 + 4004 + 55 + 707
    # (4) cardinaux : quatre fichiers sous le lot, cinq sous le rushe.
    assert lot.fichiers == 4
    assert rush.fichiers == 5
    # (5) etats : la greffe porte l'ecart, le lot declare non.
    greffe = _par_nom(arbre, f"plan-04_25_v2 · {pi.MENTION_NON_DECLARE}",
                      sous="plan-04", nature=NATURE_LOT)
    assert greffe.etat == ETAT_NON_DECLARE
    assert lot.etat == ETAT_PRESENT
    assert greffe.poids == 707


def test_le_total_du_projet_reel_EGALE_les_octets_reellement_ecrits(tmp_path):
    """Le total est confronte au DISQUE, jamais a une seconde somme du modele.

    C'est le seul volet qui puisse attraper un poids compte deux fois -- un
    noeud absorbe et son parent, par exemple --, et aucune addition faite dans
    le modele ne le verrait.
    """
    chemin = _projet_reel(tmp_path)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(inventorier_le_projet(chemin))
    ecrits = sum(f.stat().st_size for f in chemin.rglob("*") if f.is_file()
                 and f.name != "project.json")
    assert arbre.poids_total == ecrits


# ---------------------------------------------------------------------------
# Ce que la campagne de mutation du 2026-09-05 a trouve, et qui manquait
# ---------------------------------------------------------------------------


def test_MUTANT_la_colonne_d_un_GROUPE_somme_les_COLONNES_pas_le_PORTE():
    """Mutant `B-resommer-colonne`, survivant de la premiere campagne.

    C'est la distinction qui fait tomber les colonnes d'`E6-1e` : un SCAN
    affiche ses **pages** dans sa colonne et remonte les **octets de ses frames
    scannees**. Un groupe qui sommerait ce que ses membres REMONTENT ecrirait
    donc « scans — 2 scans   250 pages   4,0 Go » au lieu de « 8 pages
    1,1 Go » -- un chiffre plausible, donc invisible.

    Le banc ne l'attrapait pas : ses scans portaient des valeurs ou colonne et
    porte coincidaient. La fabrique pose ici l'ECART explicitement -- un scan
    de 4 pages qui porte 124 frames --, et les deux nombres du groupe sont
    assertes ensemble, parce que c'est leur DIFFERENCE qui mesure quelque
    chose.
    """
    def scan(nom, pages, poids_du_scan, frames, poids_des_frames):
        return _objet(
            NATURE_SCAN, nom, poids=poids_du_scan, fichiers=pages,
            enfants=(_objet(NATURE_LOT_SCANNE, nom, poids=poids_des_frames,
                            fichiers=frames),))

    lot = _objet(NATURE_LOT, "plan-04_25", enfants=(
        scan("plan-04_25_scan", 4, 550, 124, 1500),
        scan("plan-04_25_scan_v2", 4, 551, 118, 1400)))
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(_inventaire_d_un_lot(lot))
    _tout_deplier(arbre)
    groupe = _par_nom(arbre, "scans — 2 scans")

    # (1) la COLONNE du groupe somme les colonnes : 4 + 4 pages, 550 + 551 o.
    assert groupe.fichiers == 8
    assert groupe.poids == 550 + 551
    assert "8 pages" in groupe.cardinal
    # (2) ce qu'il REMONTE somme ce que ses membres remontent : leurs pages ET
    #     les frames qu'ils portent -- c'est `ObjetInventorie.fichiers_total`,
    #     lu du coeur et non recompose.
    assert groupe.fichiers_porte == (4 + 124) + (4 + 118)
    assert groupe.poids_porte == (550 + 1500) + (551 + 1400)
    # (3) et les deux DIFFERENT -- sans quoi le test ne mesurerait rien.
    assert groupe.poids != groupe.poids_porte


def test_MUTANT_un_orphelin_au_rang_d_ORIGINE_ne_se_greffe_JAMAIS():
    """Mutant `B-greffe-origine`, survivant de la premiere campagne.

    Un orphelin dont le nom EGALE celui d'un noeud declare n'est pas une
    version de ce noeud : il n'a aucun fragment `_vN`, et `EPIC11-ARB-88` dit
    que le rang d'origine n'en porte pas. Le greffer le renommerait
    `<nom>_v1` -- un nom que le depot n'ecrit jamais --, et surtout il
    affirmerait une filiation que rien ne dit.

    La sortie n'est pas le silence : l'orphelin est rendu en QUEUE d'arbre,
    sous son propre nom, comme tout ce qui ne se greffe pas.
    """
    lot = _objet(NATURE_LOT, "plan-04_25", enfants=(
        _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25", poids=303, fichiers=2),))
    #: L'orphelin porte le nom du LOT, sans fragment de version : sa tige EGALE
    #: donc le nom d'une ancre declaree, et seul le rang le distingue.
    orphelin = _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25", poids=707,
                      fichiers=1, etat=ETAT_NON_DECLARE)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(lot, orphelins=(orphelin,)))
    _tout_deplier(arbre)
    #: `format_version_suffix(1)` LEVE -- le depot refuse d'ecrire un fragment
    #: pour le rang d'origine (`EPIC11-ARB-88`), et c'est precisement ce que ce
    #: test protege. Le litteral est donc ecrit ici, avec sa raison.
    with pytest.raises(naming.NamingError):
        naming.format_version_suffix(version_ranks.RANG_ORIGINE)
    assert "plan-04_25_v1" not in [n.nom for n in arbre.tous()]
    # Le lot declare n'a rien gagne : sa greffe n'a pas eu lieu.
    declare = _par_nom(arbre, "plan-04_25", nature=NATURE_LOT)
    assert declare.poids == 303
    # Et l'orphelin n'est PAS perdu : il est en queue, sous son propre nom.
    assert arbre.poids_total == 303 + 707


def test_MUTANT_une_greffe_ne_sert_JAMAIS_d_ANCRE_a_une_autre_greffe():
    """Mutant `B-declares-non-declare`, survivant de la premiere campagne.

    L'index des ancres ne retient que les noeuds DECLARES. Sans ce filtre, un
    orphelin greffe -- donc une filiation deja deduite -- deviendrait l'ancre
    d'un second orphelin : une deduction batie sur une deduction, qui est
    exactement ce que `project_maintenance` refuse (« un lien qui designe un
    autre lot ne se devine pas par ressemblance de nom »).

    Le montage : `plan-04_25_v2` se greffe sur le lot declare, puis
    `plan-04_25_v2_v3` chercherait `plan-04_25_v2` comme ancre. Il ne doit rien
    trouver.
    """
    lot = _objet(NATURE_LOT, "plan-04_25", enfants=(
        _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25", poids=303, fichiers=2),))
    greffable = _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_v2", poids=707,
                       fichiers=1, etat=ETAT_NON_DECLARE)
    en_cascade = _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_v2_v3", poids=99,
                        fichiers=1, etat=ETAT_NON_DECLARE)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(lot, orphelins=(greffable, en_cascade)))
    _tout_deplier(arbre)

    # Le premier se greffe : c'est le cas nominal, et il doit rester vrai.
    greffe = _par_nom(arbre, f"plan-04_25_v2 · {pi.MENTION_NON_DECLARE}",
                      nature=NATURE_LOT)
    assert greffe.poids == 707
    # Le second ne s'y accroche PAS. La mention `· non declare` ne suffit pas a
    # le dire -- elle est portee par TOUT noeud non declare, greffe ou non : ce
    # qui distingue une greffe est qu'elle est un LOT DE SYNTHESE pose sous le
    # rushe, a cote de son ancre.
    cascade = next(n for n in arbre.tous()
                   if n.nom.startswith("plan-04_25_v2_v3"))
    assert cascade.nature != NATURE_LOT, "greffe sur une greffe"
    rush = _par_nom(arbre, "plan-04", nature=NATURE_RUSH)
    assert cascade not in list(rush.parcourir()), "greffe : pose sous le rushe"
    assert cascade not in list(greffe.parcourir())
    # Et il n'est pas perdu pour autant : son poids est dans le total.
    assert arbre.poids_total == 303 + 707 + 99


def test_MUTANT_le_coeur_ne_pose_JAMAIS_un_non_declare_DANS_un_rushe(tmp_path):
    """La mesure qui rend TOLERABLE le mutant `B-declares-non-declare`.

    Ce mutant -- retirer le filtre `etat == ETAT_NON_DECLARE` de l'index des
    ancres -- a survecu a deux campagnes, et il est **equivalent** : l'index
    est bati AVANT toute greffe, et le coeur ne pose aucun noeud non declare a
    l'interieur d'un rushe. Le filtre ne peut donc rien retirer.

    **Une equivalence se MESURE, elle ne se declare pas.** Ce test tient le
    contrat de coeur d'ou l'equivalence decoule : le jour ou le coeur poserait
    un non-declare sous un rushe, il rougirait -- et c'est ce jour-la, pas
    avant, que le filtre cesserait d'etre defensif pour devenir necessaire.

    Le projet est REEL et porte un orphelin : mesurer ce contrat sur une
    fabrique de synthese le mesurerait sur ma propre fabrique.
    """
    chemin = _projet_reel(tmp_path)
    inventaire = inventorier_le_projet(chemin)
    assert inventaire.orphelins, "sans orphelin, le contrat n'est pas exerce"
    for rush in inventaire.rushes:
        for objet in rush.parcourir():
            assert objet.etat != ETAT_NON_DECLARE, (
                f"{objet.nature} {objet.nom!r} est non declare DANS un rushe : "
                "le filtre de `_declares_par_nom` cesse d'etre defensif")


def test_MUTANT_un_GROUPE_n_a_jamais_de_cible_et_c_est_le_TYPE_qui_le_tient():
    """La mesure qui rend TOLERABLE le mutant `C-cible-groupe`.

    Retirer la garde `noeud.groupe` de `cible_du_noeud` est **equivalent** :
    `NoeudAffiche.__post_init__` refuse a la construction un groupe qui
    porterait une cible, si bien que la seconde garde (`cible is None`) attrape
    tous les cas que la premiere attraperait.

    Rendu impossible plutot qu'improbable : c'est la forme que ce depot prefere,
    et c'est pourquoi le mutant survit sans que ce soit un trou de mesure.
    """
    with pytest.raises(pi.InventaireMalForme):
        pi.NoeudAffiche(nature=NATURE_LOT, nom="x", etat=ETAT_PRESENT,
                        profondeur=0, poids=0, fichiers=0, cardinal="",
                        groupe=True, cible=_objet(NATURE_LOT, "x"))
    #: Et le volet positif : un groupe reel, bati par le chemin de l'ecran,
    #: porte bien `cible is None`.
    arbre = _arbre()
    _tout_deplier(arbre)
    groupes = [n for n in arbre.tous() if n.groupe]
    assert groupes, "aucun groupe : le test ne mesure rien"
    assert all(n.cible is None for n in groupes)


# ---------------------------------------------------------------------------
# F3 et F5 -- deux findings CRITIQUE de la couche 1, et leurs mesures
# ---------------------------------------------------------------------------


def _deux_lots_aux_groupes_HOMONYMES() -> pi.ArbreDuProjet:
    """Deux lots portant UNE planche chacun : deux groupes strictement egaux.

    `planches — 1 planche` est un nom FORMULAIRE : il ne depend que de la
    nature et du cardinal. Ce n'est donc pas un cas exotique -- c'est le cas
    courant des que deux lots portent le meme nombre d'objets de la meme
    nature. Les poids different d'un lot a l'autre pour qu'une permutation se
    voie (regle des fabriques, point 1).
    """
    def lot(lot_id, base):
        return _objet(NATURE_LOT, lot_id, enfants=[
            _objet(NATURE_PLANCHE, f"demo_{lot_id}_6f-pay.pdf",
                   f"planches/demo_{lot_id}_6f-pay.pdf",
                   poids=base * 3 * Mo, fichiers=1)])

    return pi.ArbreDuProjet.depuis_l_inventaire(InventaireDuProjet(
        dossier=Path("/nulle-part"), project_id="projet_demo",
        rushes=(_objet(NATURE_RUSH, "plan-04",
                       enfants=[lot("aaa_25", 1), lot("bbb_25", 7)]),)))


def test_replier_pose_le_curseur_par_IDENTITE_et_pas_sur_un_HOMONYME():
    """Finding `F3` : `←` teleportait le curseur dans un AUTRE sous-arbre.

    `self.rang(parent.nom)` rendait le PREMIER noeud visible de ce nom. Les
    deux groupes etant strictement homonymes, `←` depuis la planche du SECOND
    lot posait le curseur sur le groupe du PREMIER : le repliage s'appliquait
    au bon noeud, le curseur atterrissait ailleurs.

    La cible est le second lot, jamais le premier -- un `find` fautif qui rend
    toujours le premier ne se demasque pas autrement.
    """
    arbre = _deux_lots_aux_groupes_HOMONYMES()
    _tout_deplier(arbre)
    # Temoin : les deux groupes portent bien le MEME nom, sans quoi ce test
    # mesurerait un arbre qui n'a pas la propriete qu'il vise.
    groupes = [n for n in arbre.lignes_visibles() if n.groupe]
    assert len(groupes) == 2
    assert groupes[0].nom == groupes[1].nom == "planches — 1 planche"

    arbre.viser("demo_bbb_25_6f-pay.pdf")
    assert arbre.replier() is True

    # Le curseur est sur le groupe du SECOND lot, celui qu'on repliait.
    assert arbre.courant is groupes[1]
    assert groupes[1].deplie is False
    # Et celui du PREMIER lot n'a pas bouge d'un iota.
    assert groupes[0].deplie is True


def test_rang_du_noeud_distingue_deux_HOMONYMES_la_ou_rang_ne_le_peut_pas():
    """Le lecteur par IDENTITE, mesure contre celui par NOM qui reste juste.

    `rang(nom)` n'est pas fautif -- il repond a une autre question, et un banc
    qui vise un OBJET par son nom reste bien servi. Ce test dit exactement ou
    les deux divergent, plutot que d'affirmer que l'un remplace l'autre.
    """
    arbre = _deux_lots_aux_groupes_HOMONYMES()
    _tout_deplier(arbre)
    premier, second = [n for n in arbre.lignes_visibles() if n.groupe]

    assert arbre.rang(premier.nom) == arbre.rang(second.nom)
    assert arbre.rang_du_noeud(premier) != arbre.rang_du_noeud(second)
    assert arbre.lignes_visibles()[arbre.rang_du_noeud(second)] is second
    # Un noeud hors de l'arbre n'a pas de rang, et ne rend pas zero.
    assert arbre.rang_du_noeud(_objet_hors_arbre()) is None


def _objet_hors_arbre() -> pi.NoeudAffiche:
    return pi.NoeudAffiche(nature=NATURE_LOT, nom="ailleurs", etat="present",
                           profondeur=1, poids=0, fichiers=0, cardinal="")


def test_replier_depuis_le_PREMIER_noeud_visible_ne_retombe_pas_sur_zero():
    """`or 0` avalait le rang 0, qui est un rang legitime.

    Le defaut ne se voyait pas -- le rang cherche VALAIT zero dans ce cas --,
    mais il valait zero par coincidence et non par calcul. Une mesure qui ne
    distingue pas les deux laisse passer le jour ou ils divergent.
    """
    arbre = _arbre()
    arbre.viser("a-premier")
    arbre.deplier()
    arbre.viser("a-premier_25")
    assert arbre.replier() is True
    assert arbre.curseur == 0
    assert arbre.courant.nom == "a-premier"


def test_Suppr_sur_un_noeud_SANS_objet_ni_membre_ecrit_son_refus(banc):
    """Finding `F5`, mesure jusqu'a la ligne d'etat REELLE de la coque.

    `_message` seul ne prouverait rien : c'est `etat()` qui atteint
    l'operateur, et un message pose sur une instance que le rendu ne lit pas
    serait exactement la surface morte que ce depot nomme ailleurs.

    **Ce test visait un GROUPE, et il ne le peut plus** (`EPIC11-ARB-264`) : un
    groupe se supprime desormais. Ce qui reste dans cette branche est le noeud
    qui ne porte NI objet de coeur NI membres -- un cas que l'arbre ne produit
    pas aujourd'hui, et c'est justement pourquoi il se fabrique a la main : une
    branche que rien ne mesure est une branche qu'on croit avoir.

    **Et la phrase lue a change avec lui le 2026-09-07** (`C1-4` / `C2-3`,
    trouve par deux couches). Jusque-la ce banc fabriquait le bon noeud et
    assertait `MOTIF_DU_GROUPE_NON_SUPPRIMABLE`, « Un groupe n'est pas un
    objet : ses elements se retirent un par un. » -- le cas exclu par la
    condition qu'il croyait mesurer. Il ressemblait a une couverture du refus
    de GROUPE et n'en etait pas une.
    """
    arbre = _arbre()
    orphelin = pi.NoeudAffiche(
        nature="planche", nom="ni objet ni membre", etat=pi.ETAT_PRESENT,
        profondeur=1, poids=0, fichiers=0, cardinal="")
    arbre = pi.ArbreDuProjet([orphelin])
    ecran = pi.EcranInventaireDuProjet(arbre)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.traiter("delete")
        ecran.rafraichir()
        await pilote.pause()
        return ecran.etat()

    app = CoqueTui(paliers=[PalierTemoin("Projet", "q quitter")],
                   contexte=Contexte(projet="projet_demo"))
    assert banc(app, scenario) == pi.MOTIF_DU_NOEUD_SANS_OBJET


def test_le_refus_du_NOEUD_SANS_OBJET_se_replie_en_ASCII_PUR():
    """Il porte un accent : il passe donc par le repli comme tout le reste."""
    assert not pi.MOTIF_DU_NOEUD_SANS_OBJET.isascii()
    ecran = pi.EcranInventaireDuProjet(_arbre())
    ecran._message = pi.MOTIF_DU_NOEUD_SANS_OBJET
    assert pi._replie(ecran._message, True).isascii()


def test_le_refus_du_NOEUD_SANS_OBJET_dit_ce_qui_MARCHE_et_pas_seulement_non():
    """`EPIC11-ARB-89` : un refus sans issue est aussi fautif qu'une destruction.

    Mesure sur le CONTENU plutot que sur l'egalite a la constante, qui ne
    mesurerait que la constante contre elle-meme.

    **Les deux moities sont asserties separement, et c'est le finding `C1-4`
    qui l'exige** : la phrase d'avant nommait bien une issue (« un par un »),
    mais l'issue d'un AUTRE cas que celui de sa branche. On mesure donc les
    deux -- ce que la ligne n'a pas, et ce qu'il faut viser a la place --,
    ainsi que l'absence du mot qui a menti pendant une journee.
    """
    motif = pi.MOTIF_DU_NOEUD_SANS_OBJET
    assert "ni objet ni élément" in motif, motif
    assert "visez un objet ou un groupe" in motif, motif
    # `EPIC11-ARB-264` a rendu le groupe supprimable : cette phrase-ci ne peut
    # plus dire qu'un groupe ne se supprime pas.
    assert "un par un" not in motif, motif


def test_le_refus_du_NOEUD_SANS_OBJET_tient_le_budget_de_colonnes():
    """`MESURE: 71/76` -- le commentaire de la constante se mesure.

    Un motif plus large que la ligne d'etat serait coupe a droite, et le
    coupage tombe precisement sur l'issue, qui est en queue de phrase.
    """
    assert jetons.colonnes(pi.MOTIF_DU_NOEUD_SANS_OBJET) == 71
    assert jetons.colonnes(pi.MOTIF_DU_NOEUD_SANS_OBJET) <= jetons.largeur_utile()


# ---------------------------------------------------------------------------
# Les SURVIVANTS de la couche 1, fermes un par un
# ---------------------------------------------------------------------------


def test_les_versions_greffees_sortent_en_rang_CROISSANT():
    """Finding `F4` / mutant `B08` : elles sortaient `v4, v3, v2`.

    Chaque greffe s'insere juste apres l'ancre, donc elle REPOUSSE la
    precedente : parcourues dans l'ordre d'arrivee, les versions ressortaient
    a l'envers. Deterministe, rien ne disparaissait -- mais l'inverse de ce
    que la maquette montre des versions DECLAREES, `E6-1e` posant
    `…_6f-pay.pdf` puis `…_6f-pay_v2.pdf`. Deux familles voisines rangees a
    l'envers l'une de l'autre sur le meme ecran est un ecart qui se lit.

    Les orphelins sont FOURNIS dans le desordre (`v3, v2, v4`) : les fournir
    croissants ferait passer un code qui se contenterait de les recopier.
    """
    lot = _lot_riche("plan-04_25")
    orphelins = [
        _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_v3",
               "extract-frames/plan-04_25_v3", poids=30 * Mo, fichiers=3),
        _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_v2",
               "extract-frames/plan-04_25_v2", poids=20 * Mo, fichiers=2),
        _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_v4",
               "extract-frames/plan-04_25_v4", poids=40 * Mo, fichiers=4),
    ]
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(lot, orphelins))
    rush = _par_nom(arbre, "plan-04")
    noms = [enfant.nom for enfant in rush.enfants]
    mention = " · " + pi.MENTION_NON_DECLARE
    assert noms == ["plan-04_25"] + [f"plan-04_25_v{n}{mention}"
                                     for n in (2, 3, 4)], noms


def test_la_RESOMMATION_est_de_BAS_en_HAUT_sur_une_greffe_DANS_un_groupe():
    """Mutant `B04`, le survivant le plus cher de la couche 1.

    La docstring de `_resommer_en_profondeur` annonce exactement le defaut --
    « un lot resomme avant le groupe qui le porte lirait le total d'avant la
    greffe » -- et rien ne le mesurait. Le regime ou il mord n'est PAS la
    greffe au niveau du lot, ou l'ordre n'a aucun effet (0 ecart sur 13
    noeuds, mesure par la couche 1) : c'est la greffe qui atterrit **dans un
    groupe**, c'est-a-dire un scan orphelin a cote d'un scan declare.

    Ce que ce test mesure, c'est que le poids et le cardinal du GROUPE, du LOT
    et du RUSH portent tous les trois la greffe -- trois niveaux, parce que
    c'est la remontee qui est en cause et non une valeur isolee.
    """
    lot = _lot_riche("plan-04_25")
    greffe = _scan("plan-04_25_scan_v3", 900 * Mo, 9, "plan-04_25_v3",
                   700 * Mo, 7)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(lot, [greffe]))

    # La greffe a bien atterri DANS le groupe, sinon ce test mesure autre chose.
    groupe = _par_nom(arbre, "scans — 3 scans", sous="plan-04_25")
    # Et il est en QUEUE de famille : la version greffee se pose APRES la
    # version DECLAREE de rang inferieur, jamais entre l'ancre et elle.
    assert [n.nom for n in groupe.enfants] == [
        "plan-04_25_scan", "plan-04_25_scan_v2", "plan-04_25_scan_v3"]

    # Les neuf pages et les sept frames scannees remontent aux TROIS niveaux.
    porte = 900 * Mo + 700 * Mo
    fichiers = 9 + 7
    sans_greffe = _par_nom(pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(_lot_riche("plan-04_25"))), "scans — 2 scans",
        sous="plan-04_25")
    assert groupe.poids_porte == sans_greffe.poids_porte + porte
    assert groupe.fichiers_porte == sans_greffe.fichiers_porte + fichiers

    lot_affiche = _par_nom(arbre, "plan-04_25")
    rush = _par_nom(arbre, "plan-04")
    assert lot_affiche.poids_porte == rush.poids_porte
    assert rush.poids_porte >= porte
    assert rush.fichiers_porte >= fichiers


def test_un_noeud_NON_DECLARE_n_est_JAMAIS_une_ancre_de_greffe():
    """Mutant `B09` : greffer sur un orphelin ferait une chaine de devinettes.

    `_declares_par_nom` n'indexe que les noeuds DECLARES. Sans cette garde,
    `plan-04_25_v2_v3` se greffe sur `plan-04_25_v2`, lui-meme greffe --
    c'est-a-dire une filiation batie sur une filiation devinee.
    """
    lot = _lot_riche("plan-04_25")
    orphelins = [
        _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_v2",
               "extract-frames/plan-04_25_v2", poids=20 * Mo, fichiers=2),
        _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25_v2_v3",
               "extract-frames/plan-04_25_v2_v3", poids=30 * Mo, fichiers=3),
    ]
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(lot, orphelins))
    rush = _par_nom(arbre, "plan-04")

    # `_v2` se greffe (son ancre est declaree), `_v2_v3` NON.
    mention = " · " + pi.MENTION_NON_DECLARE
    assert [e.nom for e in rush.enfants] == ["plan-04_25",
                                             f"plan-04_25_v2{mention}"]
    # Et il n'a pas disparu pour autant : il est en QUEUE d'arbre, hors du rush.
    en_queue = [n.nom for racine in arbre.racines if racine is not rush
                for n in racine.parcourir()]
    assert any("plan-04_25_v2_v3" in nom for nom in en_queue), en_queue


def test_une_nature_INCONNUE_de_la_table_ne_DISPARAIT_pas_du_lot():
    """Mutant `B26` : elle serait avalee, et un objet disparaitrait en silence.

    C'est l'AC 1.4 au niveau du lot -- le pendant exact de
    `test_un_enfant_de_rush_d_une_AUTRE_nature_ne_DISPARAIT_pas`, qui le
    mesure au niveau du rush. Les deux existent parce que le regroupement se
    fait aux deux niveaux et qu'une garde posee a l'un ne dit rien de l'autre.
    """
    lot = _objet(NATURE_LOT, "plan-04_25", enfants=[
        _objet(NATURE_FRAMES_EXTRAITES, "plan-04_25",
               "extract-frames/plan-04_25", poids=100 * Mo, fichiers=10),
        _objet("nature_de_demain", "objet-neuf", "ailleurs/objet-neuf",
               poids=7 * Mo, fichiers=2)])
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(_inventaire_d_un_lot(lot))
    affiche = _par_nom(arbre, "plan-04_25")

    natures = [enfant.nature for enfant in affiche.enfants]
    assert "nature_de_demain" in natures, natures
    # En QUEUE, apres les natures connues : un ecart se pose apres le nominal.
    assert natures[-1] == "nature_de_demain", natures
    assert affiche.fichiers_porte == 12


def test_une_version_GREFFEE_se_pose_apres_une_version_DECLAREE_inferieure():
    """Le second volet de `F4`, et le tri seul ne le donnait PAS.

    Trier les greffes par rang corrige l'ordre ENTRE greffes ; il ne voit pas
    les versions **declarees** qui sont deja dans la liste. Une greffe `_v3`
    s'inserait alors entre l'ancre et le `_v2` declare, rendant
    `scan, scan_v3, scan_v2`. C'est ce qui a fait remplacer le tri par un rang
    d'insertion CALCULE, independant de l'ordre de parcours.
    """
    lot = _lot_riche("plan-04_25")   # il porte `_scan` et `_scan_v2` DECLARES
    greffes = [_scan("plan-04_25_scan_v4", 400 * Mo, 4, "s4", 40 * Mo, 4),
               _scan("plan-04_25_scan_v3", 300 * Mo, 3, "s3", 30 * Mo, 3)]
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(lot, greffes))
    groupe = _par_nom(arbre, "scans — 4 scans", sous="plan-04_25")

    assert [n.nom for n in groupe.enfants] == [
        "plan-04_25_scan", "plan-04_25_scan_v2", "plan-04_25_scan_v3",
        "plan-04_25_scan_v4"]


def test_AUCUN_identifiant_du_PRODUIT_n_est_une_chaine_LITTERALE(tmp_path):
    """AC 2.6, second volet -- **le test que l'AC exige et qui n'existait pas**.

    Nomme par la couche 3 de la revue (finding `T-1`) : « le banc du lot B ne
    fait aucun AST (`ast.parse` : 0 occurrence) ». La propriete de fond tenait
    -- les noms viennent de l'inventaire, la regle des rangs vient d'`io.naming`
    -- mais elle n'etait pas MESUREE, et le registre ne nommait pas ce manque.

    **Ce qu'un identifiant du produit ecrit en dur produirait** : un ecran qui
    reconnaitrait un master a la chaine `"_mmu_"` ou une version au motif
    `"_v2"` serait une seconde redaction des fabriques de `io.naming`, et elle
    divergerait au premier renommage -- exactement la panne que la borne
    `CANONICAL_ID_MAX_LENGTH` a payee trois fois, citee de memoire et fausse.

    Les trois familles mesurees sont celles que le produit FABRIQUE : le
    marqueur de master, le fragment de version, et les identifiants du registre
    ferme des profils.
    """
    from outils_frontiere import chaines_de_code

    familles = {
        "marqueur de master": lambda ch: naming.MASTER_FILENAME_MARKER in ch,
        "fragment de version": lambda ch: re.search(r"_v\d+", ch) is not None,
        "identifiant de profil": lambda ch: ch in codec_profiles.PROFILES,
    }
    for module in (pi, ps_module()):
        chemin = Path(module.__file__)
        for motif, voit in familles.items():
            fautives = [ch for ch in chaines_de_code(chemin) if voit(ch)]
            assert fautives == [], (chemin.name, motif, fautives)

    # Le volet symetrique, sur la VRAIE fonction et une source de synthese :
    # sans lui, la mesure passerait aussi bien sur un module vide.
    fautif = tmp_path / "fautif.py"
    fautif.write_text(
        'MARQUEUR = "_mmu_"\nVERSION = "plan_v2"\nPROFIL = "prores_hq"\n',
        encoding="utf-8")
    chaines = chaines_de_code(fautif)
    for motif, voit in familles.items():
        assert [ch for ch in chaines if voit(ch)], motif


def ps_module():
    from mixed_media_utility.tui import projet_suppression
    return projet_suppression


# ---------------------------------------------------------------------------
# C2-1 -- la greffe des MASTERS et des PLANCHES, qui ne marchait pas du tout
# ---------------------------------------------------------------------------


def test_une_version_de_MASTER_se_greffe_sur_son_master_declare():
    """Finding `C2-1` de la couche 2, le plus cher de la revue.

    `tige_et_rang` lit `_vN` en FIN de nom ; `build_master_filename` pose le
    rang AVANT l'extension, parce qu'un fichier garde son extension en queue.
    Mesure de la couche 2 :

        tige_et_rang('plan-04_25_mmu_prores_hq_v2.mov')
          -> ('plan-04_25_mmu_prores_hq_v2.mov', 1)   # le nom INTACT

    Donc l'entree `NATURE_MASTER` d'`ANCRES_DES_ORPHELINS` etait **morte** :
    aucune version de master ne se greffait, toutes partaient en queue
    d'arbre. Le defaut ne se voyait pas parce que la fabrique du banc ne
    greffait que des natures SANS extension -- lots et scans --, c'est-a-dire
    la regle des fabriques prise en defaut sur son point 1.
    """
    lot = _lot_riche("plan-04_25")
    orphelin = _objet(NATURE_MASTER, "plan-04_25_mmu_prores_hq_v2.mov",
                      "outputs/plan-04_25_mmu_prores_hq_v2.mov",
                      poids=99 * Mo, fichiers=1)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(lot, [orphelin]))

    groupe = _par_nom(arbre, "masters — 3 masters", sous="plan-04_25")
    noms = [n.nom for n in groupe.enfants]
    assert "plan-04_25_mmu_prores_hq_v2.mov" in noms, noms
    # A cote de SON master, jamais a cote de l'autre profil.
    assert noms.index("plan-04_25_mmu_prores_hq_v2.mov") == noms.index(
        "plan-04_25_mmu_prores_hq.mov") + 1, noms
    # Et son poids remonte : une greffe qui ne pese pas n'a pas eu lieu.
    assert groupe.poids_porte == (7 + 11 + 99) * Mo


def test_une_version_de_PLANCHE_se_greffe_sur_sa_planche_declaree():
    """Le second volet de `C2-1` : l'autre entree morte du registre d'ancres.

    Les deux natures a extension sont mesurees, pas une seule : une correction
    qui n'aurait accorde que les masters resterait verte sur l'autre moitie.
    """
    lot = _lot_riche("plan-04_25")
    orphelin = _objet(NATURE_PLANCHE, "demo_plan-04_25_6f-pay_v3.pdf",
                      "planches/demo_plan-04_25_6f-pay_v3.pdf",
                      poids=13 * Mo, fichiers=1)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(lot, [orphelin]))

    groupe = _par_nom(arbre, "planches — 3 planches", sous="plan-04_25")
    noms = [n.nom for n in groupe.enfants]
    # Et en rang CROISSANT derriere le `_v2` DECLARE : les deux corrections se
    # composent, `_place_de_la_version` lisant elle aussi le rang a travers
    # l'extension.
    assert noms == ["demo_plan-04_25_6f-pay.pdf",
                    "demo_plan-04_25_6f-pay_v2.pdf",
                    "demo_plan-04_25_6f-pay_v3.pdf"], noms


def test_le_nom_d_une_version_de_FICHIER_garde_son_EXTENSION_en_queue():
    """La recomposition va par PAIRE avec la decomposition, ou elle diverge.

    `nom_de_version` seule rendrait `…_prores_hq.mov_v2` : un nom que rien ne
    sait relire et qu'aucun lecteur ne reconnaitrait comme un `.mov`. Les deux
    fonctions sont mesurees l'une contre l'autre plutot que chacune seule --
    c'est l'aller-retour qui porte la propriete.
    """
    for nom in ("plan-04_25_mmu_prores_hq.mov", "demo_p_6f-pay.pdf",
                "plan-04_25", "plan-04_12p5"):
        for rang in (2, 7, 99):
            versionne = naming.nom_de_version_de_fichier(nom, rang)
            assert naming.tige_et_rang_de_fichier(versionne) == (nom, rang)
    # Et l'extension reste bien en QUEUE, ce que l'aller-retour seul ne dit pas.
    assert naming.nom_de_version_de_fichier(
        "plan-04_25_mmu_prores_hq.mov", 2).endswith(".mov")


def test_un_suffixe_qui_n_est_PAS_une_extension_ne_se_coupe_pas():
    """La borne plutot qu'un registre ferme, et son volet symetrique.

    Fermer la liste des extensions ferait echouer la decomposition sur la
    premiere extension neuve, et echouer en SILENCE -- par un orphelin qui
    part en queue. Ce qui est mesure est donc la borne : un suffixe court et
    purement alphanumerique est une extension, les autres non.
    """
    assert naming.tige_et_rang_de_fichier("plan-04.12p5_v2") == (
        "plan-04.12p5", 2)
    # Un suffixe trop long n'en est pas une : le nom reste entier.
    trop_long = "a_v2." + "x" * (naming.LONGUEUR_MAX_D_EXTENSION + 1)
    assert naming.tige_et_rang_de_fichier(trop_long) == (trop_long, 1)
    # Un suffixe non alphanumerique non plus.
    assert naming.tige_et_rang_de_fichier("a_v2.mo-v") == ("a_v2.mo-v", 1)


def test_un_nom_ENTIEREMENT_fait_d_une_extension_garde_sa_TETE():
    """Un fichier CACHE reste cache quand on le versionne.

    Survivant `M-C2-1f` de la campagne, ferme apres mesure. Le mutant remplace
    `point <= 0` par `point < 0` dans `_coupe_l_extension`, et il est
    **equivalent sur la decomposition** -- les sept cas de bord mesures
    (`.mov`, `.mov_v2`, `.a`, `.`, `..mov`, `.mp4`, `a.mov`) rendent tous la
    meme paire. Il ne mord que sur la RECOMPOSITION, et d'une facon qui compte :

        nom_de_version_de_fichier('.mov', 2)
          sain    -> '.mov_v2'     # toujours cache
          mutant  -> '_v2.mov'     # VISIBLE, et d'une tige inventee

    `.mov` n'a pas de tige : c'est un nom de fichier cache, pas une extension
    posee sur quelque chose. Lui en inventer une le sort de son etat cache --
    une consequence sur le SYSTEME DE FICHIERS, pas seulement sur l'affichage.
    """
    for cache in (".mov", ".mp4", ".pdf"):
        versionne = naming.nom_de_version_de_fichier(cache, 2)
        assert versionne.startswith("."), versionne
        assert naming.tige_et_rang_de_fichier(versionne) == (cache, 2)


def test_le_recomposeur_de_FICHIER_ne_diverge_PAS_sur_un_identifiant_de_LOT():
    """Pourquoi `M-C2-1b` survit, et la frontiere qui garde l'equivalence VRAIE.

    Le mutant remplace `nom_de_version_de_fichier` par `nom_de_version` dans
    :func:`greffer_les_orphelins`. Il survit parce que le nom recompose n'est
    consomme que sur la branche `NATURE_LOT` -- les autres greffes rendent
    l'orphelin par son PROPRE nom de fichier --, et parce qu'un identifiant de
    lot ne peut pas porter de point : `_MANIFEST_ID_PATTERN` vaut
    `^[A-Za-z0-9_-]+$`. Sans point, `_coupe_l_extension` ne trouve jamais
    d'extension, et les deux redactions coincident. Mesure : **zero ecart sur
    4000 identifiants legaux tires au hasard, a trois rangs chacun**.

    C'est donc une EQUIVALENCE, pas une tolerance. Mais elle repose sur une
    contrainte qui vit dans un AUTRE module : le jour ou le point entrerait
    dans la charte des identifiants, la greffe de lot nommerait `plan-04_v2.5`
    la version de `plan-04.5`. Ce test rougit ce jour-la, et il est le seul
    endroit qui relie les deux faits.
    """
    assert "." not in naming.normalize_identifier("plan.04_25")
    with pytest.raises(Exception):
        naming.validate_manifest_identifier("plan-04.5")
    for identifiant in ("plan-04_25", "a", "z-dernier", "LOT_9-b", "plan-04_12p5"):
        assert naming._MANIFEST_ID_PATTERN.match(identifiant), identifiant
        for rang in (2, 9, 99):
            assert (naming.nom_de_version_de_fichier(identifiant, rang)
                    == naming.nom_de_version(identifiant, rang))


def _lot_au_scan_HOMONYME(lot_id="plan-04_25"):
    """Un lot dont UN scan declare porte exactement le nom du lot.

    **Ce n'est pas un cas tordu, c'est ce que le module dit du produit** : « un
    slug d'ingestion est libre : il vaut souvent `<lot_id>_scan`, **parfois le
    `lot_id` lui-meme** ». Quand il vaut le `lot_id`, une tige de scan designe
    DEUX ancres candidates -- le scan declare et le lot -- et c'est l'ordre du
    tuple d'`ANCRES_DES_ORPHELINS` qui tranche. La fabrique usuelle ne produit
    que des slugs `<lot_id>_scan`, donc l'ambiguite ne s'y leve jamais.
    """
    base = _lot_riche(lot_id)
    homonyme = _scan(lot_id, 19 * Mo, 8, f"{lot_id}_scanne", 400 * Mo, 40)
    return _objet(NATURE_LOT, lot_id, enfants=list(base.enfants) + [homonyme])


@pytest.mark.parametrize("nature", [NATURE_SCAN, NATURE_LOT_SCANNE])
def test_une_ancre_de_SCAN_prime_sur_le_LOT_du_meme_nom(nature):
    """Finding `C2-2` : les DEUX natures a deux ancres, et aucune n'etait mesuree.

    Un scan est plus SPECIFIQUE qu'un lot : une version de scan se greffe sur
    le scan. Prendre le lot d'abord fait remonter la greffe d'un cran -- elle
    devient soeur du lot au lieu d'etre sa petite-fille --, et le poids greffe
    **sort du total du lot**, c'est-a-dire de la seule colonne dont le module
    dit qu'elle « dit ce qu'une suppression toucherait vraiment ». Mesure des
    mutants `N03` et `N04` (ordre du tuple inverse) :

    | | profondeur de la greffe | poids porte du lot | fichiers |
    |---|---|---|---|
    | sain | 3 | 1 128 219 200 | 131 |
    | ordre inverse | 1 | 1 127 219 200 | 122 |

    Le rang **3** plutot que 2 evite l'homonyme que `_lot_riche` pose deja au
    rang 2 (`<lot>_scan_v2` declare un lot scanne `<lot>_v2`) : la mesure
    porterait sinon sur deux noeuds du meme nom.
    """
    lot = _lot_au_scan_HOMONYME()
    orphelin = _objet(nature, "plan-04_25_v3", "x/plan-04_25_v3",
                      etat=ETAT_NON_DECLARE, poids=1_000_000, fichiers=9)
    arbre = pi.ArbreDuProjet.depuis_l_inventaire(
        _inventaire_d_un_lot(lot, [orphelin]))

    greffes = [n for n in arbre.tous() if "plan-04_25_v3" in n.nom]
    assert len(greffes) == 1, [(n.profondeur, n.nom) for n in greffes]
    # Sous le GROUPE de scans du lot, jamais a cote du lot.
    assert greffes[0].profondeur == 3, greffes[0].profondeur

    noeud_du_lot = _par_nom(arbre, "plan-04_25", nature=NATURE_LOT)
    # Et le poids greffe reste DANS le lot : c'est ce que l'ordre inverse perd.
    assert noeud_du_lot.poids_porte == 1_128_219_200
    assert noeud_du_lot.fichiers == 131


def test_le_cardinal_d_un_groupe_d_ORPHELINS_compte_les_FICHIERS():
    """Finding `C2-5`, et c'est le point 1 de la regle des fabriques sur une VALEUR.

    `_mention_de_groupe` a deux recettes : les natures de `GROUPES_DECLARES`
    comptent leurs FICHIERS (`frames — 42 frames`), les autres comptent leurs
    MEMBRES (`planches — 2 planches`). La branche « fichiers » n'est atteinte,
    dans un groupe de queue, que par :func:`orphelins_affiches` -- exactement
    les objets qu'aucun manifeste ne declare, sujet de la story.

    Elle n'etait pourtant mesuree par rien : la seule fabrique d'orphelin sans
    ancre portait `fichiers=1`, si bien que `sum(membre.fichiers)` et
    `len(membres)` rendaient le MEME nombre. Mutant `N06` (`len(membres)`
    partout) : `frames — 42 frames` devient `frames — 1 frame`.
    """
    orphelin = _objet(NATURE_FRAMES_EXTRAITES, "sans-ancre-du-tout",
                      "extract-frames/sans-ancre-du-tout",
                      etat=ETAT_NON_DECLARE, poids=5 * Mo, fichiers=42)
    arbre = _arbre([orphelin])

    groupes = [n for n in arbre.tous()
               if n.profondeur == 0 and n.nom.startswith("frames")]
    assert len(groupes) == 1, [n.nom for n in groupes]
    assert groupes[0].nom == "frames — 42 frames", groupes[0].nom
    # Le volet qui distingue les deux recettes : une nature comptee en MEMBRES
    # ne suit pas les fichiers, et deux orphelins de planche en font DEUX.
    planches = [_objet(NATURE_PLANCHE, f"seule-{i}.pdf", f"planches/seule-{i}.pdf",
                       etat=ETAT_NON_DECLARE, poids=Mo, fichiers=7)
                for i in (1, 2)]
    autre = _arbre(planches)
    groupe = [n for n in autre.tous()
              if n.profondeur == 0 and n.nom.startswith("planches")]
    assert groupe[0].nom == "planches — 2 planches", groupe[0].nom


def test_orphelins_le_groupe_SE_COCHE_et_Suppr_nomme_ses_membres_non_visables():
    """Finding `C1-5` : la prose d'`orphelins_affiches` disait l'inverse du code.

    Elle affirmait « le groupe qui les porte est un vrai noeud de regroupement,
    donc il ne se coche pas ». `EPIC11-ARB-264` a retourne `basculer`, qui
    coche desormais TOUS les groupes ; la phrase, elle, n'avait pas bouge. Ce
    banc mesure les deux moities de ce qui la remplace, parce qu'une prose
    corrigee sans banc redevient fausse au commit suivant.

    **La seconde moitie est la seule qui distingue un orphelin d'un groupe
    ordinaire** : un orphelin vit a la racine, `lot_ancetre` ne lui trouve
    aucun lot, et les cinq cibles fines du coeur se designent DANS un lot. Le
    produit ne se tait pas pour autant -- il NOMME chaque membre qu'il ne sait
    pas viser (`EPIC11-ARB-258`).

    Trois orphelins, aux noms et aux poids **distincts** : un refus qui ne
    citerait qu'un membre, ou qui sauterait celui de tete ou celui de queue,
    se verrait (regle des fabriques, points 1 et 4).
    """
    from mixed_media_utility.tui import projet_suppression as ps

    orphelins = [_objet(NATURE_PLANCHE, f"seule-{i}.pdf",
                        f"planches/seule-{i}.pdf", etat=ETAT_NON_DECLARE,
                        poids=i * Mo, fichiers=i)
                 for i in (1, 2, 3)]
    arbre = _arbre(orphelins)
    groupe = _par_nom(arbre, "planches — 3 planches")
    assert groupe.groupe is True

    # Moitie 1 : `Espace` coche le groupe d'orphelins comme tout autre groupe.
    arbre.viser(groupe.nom)
    assert arbre.basculer() is True
    assert [n.nom for n in arbre.coches] == [groupe.nom]
    vise, motif = arbre.visee()
    assert vise is groupe and motif == "", (vise, motif)

    # Moitie 2 : `Suppr` n'aboutit pas, et ne se tait pas. Les trois membres
    # sont nommes, DANS L'ORDRE DE L'ARBRE, tete et queue comprises.
    assert ps.lot_ancetre(arbre, groupe) is None
    cibles, non_visables = ps.cibles_du_groupe(groupe, ps.lot_ancetre(arbre, groupe))
    assert cibles == ()
    assert non_visables == ("seule-1.pdf", "seule-2.pdf", "seule-3.pdf"), \
        non_visables


def test_le_RATTACHEMENT_ne_parait_qu_au_niveau_OBJET_et_y_parait_TOUJOURS():
    """Finding `C2-6` : la BORNE du rattachement n'etait mesuree sur aucune ligne.

    `test_la_marque_de_pliage_precede_le_RATTACHEMENT` mesure l'ORDRE des deux
    marques ; il ne mesure jamais ce qui decide qu'il y en a une. Mutant `N07`
    (`>` au lieu de `>=` dans `est_terminal`) : **toutes** les lignes d'objet
    perdent leur `└─` d'un coup et la colonne du nom se decale de deux --
    « l'indentation cesse de dire la profondeur, qui est la seule chose qu'elle
    dit », ce que le docstring de `ligne()` nomme comme le defaut a ne pas
    avoir.

    Les deux sens sont mesures : present a partir de la profondeur d'objet,
    absent au-dessus. Une borne ne se mesure pas d'un seul cote -- un test qui
    n'exigerait que la presence resterait vert sur un `est_terminal` toujours
    vrai, qui mettrait un `└─` sur le rush lui-meme.
    """
    arbre = _arbre()
    _tout_deplier(arbre)
    vues = arbre.lignes_visibles()
    assert len(vues) > 20, len(vues)

    rattachement = jetons.GLYPHES["rattachement"]
    vus_en_objet = 0
    for rang, noeud in enumerate(vues):
        ligne = arbre.ligne(rang)
        if noeud.profondeur >= pi.PROFONDEUR_OBJET and not noeud.pliable:
            assert rattachement in ligne, (noeud.profondeur, ligne)
            vus_en_objet += 1
        elif noeud.profondeur < pi.PROFONDEUR_OBJET:
            assert rattachement not in ligne, (noeud.profondeur, ligne)
    # Temoin de vitalite : une boucle qui ne visite aucun objet ne mesure rien.
    assert vus_en_objet >= 10, vus_en_objet


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E6-1`, `E6-1a`, `E6-1c`,
# `E6-1d` et `E6-1e` -- souvent en tete de docstring, comme reference d'un
# comportement -- et n'ouvrait aucun dessin. Vingt et un litteraux en etaient
# recopies, plus que dans n'importe quel autre banc du dossier.
#
# **La confrontation est GENERATIVE et non ligne a ligne, et c'est ce qui la
# rend forte.** Les noms de groupe de l'inventaire ne sont pas des libelles
# fixes : ils sont produits par `accorder_le_contenu(cardinal, nature)`. Une
# table recopiee a la main mesurerait donc une seconde recopie. Ce qui suit
# LIT les cinq dessins, en extrait chaque ligne de groupe, et confronte la
# fonction du module a ce que le dessin porte -- de sorte qu'un dessin
# retouche fait rougir sans qu'aucune table soit a tenir a jour.

#: Les dessins repris ici, a leur source.
MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"

#: Les cinq ecrans de l'inventaire. Fabrique a cinq elements distinguables :
#: la cible est mesuree en tete (`E6-1`), au milieu et en queue (`E6-1e`).
DESSINS_DE_L_INVENTAIRE = (
    ("E6-1", "E6-1-projet-inventaire.txt"),
    ("E6-1a", "E6-1a-projet-inventaire-lecture.txt"),
    ("E6-1c", "E6-1c-projet-inventaire-defilement.txt"),
    ("E6-1d", "E6-1d-projet-inventaire-selection.txt"),
    ("E6-1e", "E6-1e-projet-inventaire-filiation.txt"),
)

#: L'etiquette que chaque dessin ecrit a gauche du tiret, et la nature du
#: coeur qui la produit. C'est le SEUL appariement recopie de cette section,
#: et il est mesure en retour : `nom_du_groupe(nature)` doit rendre
#: l'etiquette.
ETIQUETTES_DESSINEES = {
    "frames": NATURE_FRAMES_EXTRAITES,
    "planches": NATURE_PLANCHE,
    "masters": NATURE_MASTER,
    "scans": NATURE_SCAN,
    "lot scanné": NATURE_LOT_SCANNE,
}

#: Une ligne de groupe repliee : `masters — 1 master 1 f. 206 Mo`. L'accord
#: court jusqu'au chiffre suivant, qui ouvre la colonne des cardinaux.
LIGNE_DE_GROUPE = re.compile(
    r"(frames|planches|masters|scans|lot scanné) — (\d+) ([A-Za-zé ]+?)(?= \d)")


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def groupes_dessines(nom: str) -> list[tuple[str, int, str]]:
    """Les (etiquette, cardinal, accord) que ce dessin porte."""
    return [(etiquette, int(nombre), accord)
            for etiquette, nombre, accord
            in LIGNE_DE_GROUPE.findall(dessin_de_la_maquette(nom))]


#: Le dessin qui NE porte PAS le prefixe du bandeau, et l'objet qu'il porte
#: a la place. Voir
#: :func:`test_E6_1d_dessine_un_bandeau_de_SELECTION_que_le_module_ne_rend_PAS`.
DESSIN_SANS_LE_PREFIXE = "E6-1d"
OBJET_DESSINE_DE_LA_SELECTION = "sélection · 3 objets cochés"


@pytest.mark.parametrize("code,fichier", [
    (code, fichier) for code, fichier in DESSINS_DE_L_INVENTAIRE
    if code != DESSIN_SANS_LE_PREFIXE
], ids=[code for code, _ in DESSINS_DE_L_INVENTAIRE
        if code != DESSIN_SANS_LE_PREFIXE])
def test_le_BANDEAU_de_CHAQUE_ecran_de_l_inventaire_porte_son_prefixe(code,
                                                                      fichier):
    """Les quatre, un par un -- pas « au moins un des quatre ».

    Le prefixe est ce qui identifie la station : un ecran qui le perdrait se
    lirait comme un autre atelier. Une mesure globale resterait verte tant
    qu'un seul dessin le porte.

    Le cinquieme, `E6-1d`, est ecarte ICI et mesure JUSTE EN DESSOUS : il ne
    le porte pas, et ce n'est pas un oubli du dessin.
    """
    assert PREFIXE_DESSINE_DU_BANDEAU in dessin_de_la_maquette(fichier), code


def test_E6_1d_dessine_un_bandeau_de_SELECTION_que_le_module_ne_rend_PAS():
    """**Un ecart entre une maquette APPROUVEE et le code, nomme et non
    corrige.**

    `E6-1d` -- l'etat « objets coches » -- dessine `sélection · 3 objets
    cochés` a la place de `inventaire · …`. `objet_du_bandeau` n'a que deux
    branches, la lecture et le decompte, et rend `inventaire · ` dans les
    deux : le bandeau de selection n'existe nulle part dans le module.

    **Ce n'est pas a ce banc de le corriger** -- ce serait elargir le
    perimetre d'un lot d'audit a une decision d'interface. C'est verse a
    `deferred-work.md` avec son origine. Ce que ce test tient, c'est que
    l'ecart ne puisse pas disparaitre en silence : le jour ou le module
    rendra le bandeau de selection, ce test rougira et se fera retirer.

    Les deux moities sont mesurees, parce qu'une seule ne dirait rien : le
    dessin porte bien l'objet de selection, et le module ne le porte nulle
    part.
    """
    selection = dessin_de_la_maquette("E6-1d-projet-inventaire-selection.txt")
    assert OBJET_DESSINE_DE_LA_SELECTION in selection
    assert PREFIXE_DESSINE_DU_BANDEAU not in selection

    source = (_RACINE / "src" / "mixed_media_utility" / "tui"
              / "projet_inventaire.py").read_text(encoding="utf-8")
    assert "sélection · " not in source
    assert PREFIXE_DESSINE_DU_BANDEAU in source


def test_SEUL_E6_1a_remplace_les_compteurs_par_la_mention_de_lecture():
    """Volet symetrique : la mention appartient a l'ecran qui ne peut pas
    compter, et a lui seul.

    Mesurer sa presence sans son absence ailleurs laisserait passer un
    bandeau bloque en « lecture en cours » une fois l'arbre lu -- ce qui est
    precisement le mode de panne que `E6-1a` existe pour cadrer.
    """
    porteurs = [code for code, fichier in DESSINS_DE_L_INVENTAIRE
                if MENTION_DESSINEE_DE_LA_LECTURE in dessin_de_la_maquette(fichier)]
    assert porteurs == ["E6-1a"], porteurs


def test_l_ACCORD_du_coeur_rend_EXACTEMENT_ce_que_les_dessins_portent():
    """La mesure generative : chaque ligne de groupe des cinq dessins.

    Pour chaque `<etiquette> — <n> <accord>` trouve dans un dessin, le coeur
    doit rendre le meme accord pour le meme cardinal. Rien n'est recopie ici
    sauf l'appariement etiquette/nature, qui est lui-meme mesure en retour
    par `nom_du_groupe`.

    Ce que ca attrape et qu'une table ne pourrait pas : un dessin retouche.
    Ce que ca attrape et qu'un test unitaire ne pourrait pas : un accord
    juste dans le module et faux dans l'ecran approuve.
    """
    vus = []
    for code, fichier in DESSINS_DE_L_INVENTAIRE:
        for etiquette, cardinal, accord in groupes_dessines(fichier):
            nature = ETIQUETTES_DESSINEES[etiquette]
            assert pi.accorder_le_contenu(cardinal, nature) == (
                f"{cardinal} {accord}"), (code, etiquette, cardinal)
            assert pi.nom_du_groupe(nature) == etiquette, (code, etiquette)
            vus.append((etiquette, cardinal))

    # Temoin de vitalite : un balayage casse rendrait zero ligne et le test
    # serait vert sans avoir rien mesure. Les cinq etiquettes sont vues, et
    # au moins un accord SINGULIER et un PLURIEL le sont aussi -- sans quoi
    # la mesure ne dirait rien de l'accord lui-meme.
    assert {etiquette for etiquette, _ in vus} == set(ETIQUETTES_DESSINEES)
    assert any(cardinal == 1 for _, cardinal in vus)
    assert any(cardinal > 1 for _, cardinal in vus)
    assert len(vus) >= 10, vus


def test_le_CARDINAL_a_quatre_chiffres_est_dessine_avec_une_espace_ORDINAIRE():
    """`E6-1c` est le seul des cinq a franchir le millier.

    Le separateur de milliers se mesure au CODEPOINT : une espace insecable
    ou fine se lirait pareil a l'oeil et casserait toute comparaison de
    chaine. C'est un piege deja paye ailleurs dans ce depot.
    """
    defilement = dessin_de_la_maquette("E6-1c-projet-inventaire-defilement.txt")
    assert CARDINAL_DESSINE_A_QUATRE_CHIFFRES in defilement

    separateur = CARDINAL_DESSINE_A_QUATRE_CHIFFRES[1]
    assert separateur == " ", hex(ord(separateur))
    assert ord(separateur) == 0x20


def test_le_CARDINAL_du_lot_riche_est_dessine_par_E6_1e_et_par_lui_seul():
    """`9 objets · ` : le lot qui porte toute la filiation.

    Les autres dessins montrent des lots a 3 et 5 objets. Mesurer les trois
    valeurs plutot que la seule cible est ce qui distingue « ce dessin porte
    ce cardinal » de « ce cardinal existe quelque part ».
    """
    filiation = dessin_de_la_maquette("E6-1e-projet-inventaire-filiation.txt")
    inventaire = dessin_de_la_maquette("E6-1-projet-inventaire.txt")

    assert CARDINAL_DESSINE_DU_LOT_RICHE in filiation
    assert CARDINAL_DESSINE_DU_LOT_RICHE not in inventaire
    assert "3 objets · " in inventaire
    assert "5 objets · " in filiation


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    for _, fichier in DESSINS_DE_L_INVENTAIRE:
        dessin = dessin_de_la_maquette(fichier)
        assert "masters — 1 masters" not in dessin
        assert "planches — 2 planche " not in dessin
        assert "inventaire ·  " not in dessin


# ---------------------------------------------------------------------------
# `EPIC11-ARB-257` -- `Suppr` agit sur la SELECTION, pas sur la ligne active
# ---------------------------------------------------------------------------
#
# **Le piege d'Egan, verbatim (2026-09-06)** : « Suppr lance la suppression pour
# la ligne active plutot que pour la selection cochee (Lot coche, curseur sur le
# rush - j'obtiens la page pour la suppression du rushe qui me dit qu'un lot
# existe encore) ». Deux notions existaient et ne se parlaient pas : le curseur
# et la coche. `coches` n'avait **aucun consommateur en production** -- `Espace`
# dessinait une croix qui ne produisait rien.
#
# **Le drapeau que ces tests font varier** : selection vide / a un / a
# plusieurs, avec le curseur pose AILLEURS que la coche dans les deux derniers
# cas. Un banc qui ne jouerait que la selection vide mesurerait le seul chemin
# qui marchait deja.


def _coche(arbre: pi.ArbreDuProjet, *noms: str) -> None:
    """Cocher par NOM, en visant : le produit ne coche que sous le curseur."""
    for nom in noms:
        arbre.viser(nom)
        assert arbre.basculer() is True, nom


def test_la_VISEE_est_la_selection_quand_il_y_en_a_UNE_et_le_curseur_sinon():
    """Les trois regimes de :meth:`ArbreDuProjet.visee`, dans un seul test.

    Ensemble parce que c'est leur **difference** qui compte : une `visee` qui
    rendrait toujours `courant` passerait le premier volet, et une qui rendrait
    toujours la premiere coche passerait le deuxieme.

    Le curseur est pose sur un rush de BORD pendant que la coche est au milieu :
    si les deux coincidaient, le test serait vert sur les deux implementations.
    """
    arbre = _arbre()
    # Selection VIDE -> la ligne active, et c'est le repli qui garde `Suppr`
    # utile sur un arbre jamais coche.
    arbre.viser("plan-04")
    assert arbre.visee() == (arbre.courant, "")
    assert arbre.visee()[0].nom == "plan-04"

    # UNE coche, curseur AILLEURS -> la coche gagne. C'est le cas d'Egan.
    arbre.viser("plan-04_25")
    assert arbre.basculer() is True
    arbre.viser("z-dernier")
    vise, motif = arbre.visee()
    assert motif == ""
    assert vise.nom == "plan-04_25", "le curseur a gagne sur la coche"

    # PLUSIEURS coches -> rien, et le motif le dit.
    arbre.viser("plan-04_12p5")
    assert arbre.basculer() is True
    vise, motif = arbre.visee()
    assert vise is None
    assert motif == pi.MOTIF_DE_LA_SELECTION_MULTIPLE.format(cardinal="2")


def test_Suppr_vise_la_LIGNE_COCHEE_et_pas_celle_du_curseur():
    """Le piege d'Egan, joue au clavier sur l'ecran.

    **Les deux volets ensemble** : le rappel est bien appele -- donc `Suppr`
    n'est pas devenu inerte -- et il l'est sur le LOT coche, pas sur le rush
    sous le curseur. Le second volet seul serait passe par un `_retirer` qui
    ne ferait rien.
    """
    arbre = _arbre()
    vises = []
    ecran = pi.EcranInventaireDuProjet(arbre, supprimer=vises.append)

    _coche(arbre, "plan-04_25")
    arbre.viser("plan-04")
    assert arbre.courant.nature == NATURE_RUSH, "le curseur porte bien le rush"

    assert ecran.traiter("delete") is True
    assert [n.nom for n in vises] == ["plan-04_25"]
    assert ecran._message == "", "un geste qui aboutit n'ecrit aucun refus"


def test_Suppr_sur_PLUSIEURS_coches_le_DIT_et_n_appelle_RIEN():
    """La limite du modele mono-cible, **nommee** plutot que silencieuse.

    Agir sur le curseur en silence serait la destruction non demandee
    qu'`EPIC11-ARB-257` ferme ; ne rien faire sans le dire serait le finding
    `I8`. Les deux volets negatifs sont donc mesures avec le positif.
    """
    arbre = _arbre()
    vises = []
    ecran = pi.EcranInventaireDuProjet(arbre, supprimer=vises.append)

    _coche(arbre, "a-premier_25", "z-dernier_8")
    arbre.viser("plan-04")

    assert ecran.traiter("delete") is True
    assert vises == [], "le coeur a ete vise malgre la selection multiple"
    assert ecran._message == pi.MOTIF_DE_LA_SELECTION_MULTIPLE.format(
        cardinal="2")


def test_les_coches_de_BORD_sont_vues_par_la_VISEE_comme_celles_du_milieu():
    """Regle des fabriques, point 4 : la cible a CHAQUE bord.

    Un `coches` qui sauterait la premiere ou la derniere racine rendrait un
    cardinal de 1 la ou il y en a 2, donc laisserait `Suppr` agir sur la seule
    coche vue -- une suppression sur un objet que l'operateur n'a pas designe
    seul. La cible du milieu ne demasque pas ce mode de panne.
    """
    for tete, queue in (("a-premier", "a-premier_25"),
                        ("z-dernier", "z-dernier_8")):
        arbre = _arbre()
        _coche(arbre, queue)
        assert [n.nom for n in arbre.coches] == [queue], tete
        assert arbre.visee()[0].nom == queue, tete

    arbre = _arbre()
    _coche(arbre, "a-premier_25", "plan-04_25", "z-dernier_8")
    assert [n.nom for n in arbre.coches] == [
        "a-premier_25", "plan-04_25", "z-dernier_8"]


def test_le_refus_de_SELECTION_MULTIPLE_se_replie_en_ASCII_PUR():
    """La garde d'epic : un glyphe oublie rend `?` en `--ascii`."""
    ecran = pi.EcranInventaireDuProjet(_arbre())
    ecran._message = pi.MOTIF_DE_LA_SELECTION_MULTIPLE.format(cardinal="12")
    assert not ecran._message.isascii()
    assert jetons.replier_ascii(ecran._message).isascii()
    assert jetons.colonnes(jetons.replier_ascii(ecran._message)) \
        <= jetons.largeur_utile()


# ---------------------------------------------------------------------------
# `EPIC11-ARB-264` -- la case a cocher revient sur les lignes de groupe
# ---------------------------------------------------------------------------
#
# **Le retour d'Egan, verbatim** : « Planches (l'ensemble de toutes les
# planches) n'est pas selectionnable. Problematique. »
#
# Le 2026-09-06, la reponse fut de RETIRER la case : elle etait dessinee
# inconditionnellement pendant que `basculer` la refusait, donc c'etait une
# promesse faite a l'oeil que la touche ne tenait pas (`EPIC11-ARB-258`,
# finding `I8`). Le 2026-09-07, `EPIC11-ARB-264` a change le FAIT sous la
# regle : le coeur porte `remove_project_group`, la case n'est plus inerte, et
# elle revient. Le commentaire de `_case_a_cocher` annoncait lui-meme cette
# sortie.
#
# **L'ecart entre les deux maquettes est tranche par le fait** : `E6-1d` -- le
# dessin de la SELECTION, c'est-a-dire l'ecran dont la question relevait --
# porte `[ ]` sur `planches — 2 planches` et sur `masters — 1 master`. Le
# produit le suit.
#
# **Le drapeau que ces tests font varier** : noeud de groupe / noeud d'objet, et
# les deux regimes de repli.


def _ligne_du_noeud(arbre: pi.ArbreDuProjet, noeud: pi.NoeudAffiche,
                    ascii_seul: bool = False) -> str:
    """La ligne rendue de CE noeud, retrouvee par IDENTITE.

    Par identite et non par nom : `planches — 2 planches` existe sous CHACUN
    des quatre lots de la fabrique, et un helper qui rendrait le premier ferait
    passer un test qui vise le troisieme -- le mutant `M25` de la 5.7, dans le
    banc cette fois.
    """
    rang = arbre.rang_du_noeud(noeud)
    assert rang is not None, noeud.nom
    return arbre.ligne(rang, ascii_seul)


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_une_ligne_de_GROUPE_porte_une_case_COMME_un_objet(ascii_seul):
    """Les deux volets, parce que c'est leur EGALITE qui compte desormais.

    L'ancienne redaction mesurait leur DIFFERENCE, et elle avait raison tant
    que la case etait inerte sur un groupe. Sans le second volet, un rendu qui
    n'ecrirait plus jamais de case passerait le premier tout seul -- et il
    retirerait la selection de l'ecran entier.
    """
    arbre = _arbre()
    _tout_deplier(arbre)
    table = jetons.glyphes(ascii_seul)

    groupe = _ligne_du_noeud(
        arbre, _par_nom(arbre, "planches — 2 planches", sous="plan-04_25"),
        ascii_seul)
    assert table["decoche"] in groupe, groupe

    objet = _ligne_du_noeud(
        arbre, _par_nom(arbre, "demo_plan-04_25_6f-pay.pdf"), ascii_seul)
    assert table["decoche"] in objet, objet


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_case_d_un_groupe_SUIT_sa_coche_et_garde_la_LARGEUR(ascii_seul):
    """L'indentation est la seule chose qui dise la filiation : elle ne bouge pas.

    Deux promesses dans le meme test, et la seconde est ce qui restait de
    l'ancienne : cochee ou non, la case fait la MEME largeur, donc le nom se
    pose a la meme colonne. Le drapeau `coche` varie dans les deux sens -- une
    case cablee sur `decoche` passerait un test qui ne coche jamais.
    """
    arbre = _arbre()
    _tout_deplier(arbre)
    table = jetons.glyphes(ascii_seul)
    noeud = _par_nom(arbre, "planches — 2 planches", sous="plan-04_25")

    decochee = pi._case_a_cocher(noeud, table)
    noeud.coche = True
    cochee = pi._case_a_cocher(noeud, table)

    assert table["decoche"] in decochee
    assert table["coche"] in cochee
    assert jetons.colonnes(cochee) == jetons.colonnes(decochee)


def test_ESPACE_sur_un_GROUPE_le_COCHE_et_n_ecrit_aucun_refus():
    """`EPIC11-ARB-264` : la touche annoncee tient enfin sa promesse.

    Le volet symetrique est dans le meme test : sur un objet, la touche coche
    aussi et n'ecrit **aucun** message -- sans quoi un `_message` pose a chaque
    frappe passerait le premier volet.
    """
    arbre = _arbre()
    _tout_deplier(arbre)
    ecran = pi.EcranInventaireDuProjet(arbre)

    arbre.viser("planches — 2 planches")
    assert ecran.traiter("space") is True
    assert [n.nom for n in arbre.coches] == ["planches — 2 planches"]
    assert ecran._message == ""

    arbre.viser("plan-04_25")
    assert ecran.traiter("space") is True
    assert sorted(n.nom for n in arbre.coches) == [
        "plan-04_25", "planches — 2 planches"]
    assert ecran._message == ""


def test_le_MOTIF_de_coche_a_ete_RETIRE_et_pas_seulement_decable():
    """Frontiere NEGATIVE (`EPIC11-ARB-220`, retrait PUR).

    `MOTIF_DU_GROUPE_NON_COCHABLE` disait une regle que le produit ne tient
    plus. Le laisser en place, meme sans appelant, ferait croire a un lecteur
    -- et a un agent -- qu'un groupe ne se coche pas ; aucun test positif ne
    verrait cette constante revenir.
    """
    assert not hasattr(pi, "MOTIF_DU_GROUPE_NON_COCHABLE")
    assert "MOTIF_DU_GROUPE_NON_COCHABLE" not in pi.__all__
