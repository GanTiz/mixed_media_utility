# -*- coding: utf-8 -*-
"""Ce qu'un GROUPE laisse derriere lui, et qui n'atteignait pas l'oeil.

Les findings `C1-1` / `C2-1` / `C3-3` (critique, trouve par les trois couches
independamment), `C1-2` (critique), `C3-2` / `C3-2b` (critique) et les deux
tolerances `C2-6` et `C2-7` de la revue de la vague 2.

**Deux causes, un seul effet pour l'operateur.** Un membre de groupe peut ne
pas partir parce que le PRODUIT ne sait pas le viser (`cible_du_noeud` rend
``None``) ou parce que le COEUR le refuse (`LigneDeGroupe.refus`). Le fichier
reste sur le disque dans les deux cas, et c'est la seule chose que l'operateur
constate : les bancs ci-dessous mesurent donc les deux familles ensemble, comme
:func:`ecartes_du_plan` les rassemble.

**Regle des fabriques.** Le groupe de reference porte QUATRE membres
distinguables -- noms, profils et cardinaux tous differents --, un ecarte en
TETE et un ecarte en QUEUE, deux membres visables au MILIEU. Un balayage
tronque d'un bord ou de l'autre laisse donc un ecarte non nomme, et un `find`
qui rendrait le premier membre se demasque. Un second groupe place l'ecarte au
MILIEU seul, ce que les bords ne mesurent pas.

**Regle des drapeaux.** `dry_run` varie dans les deux sens sur le meme cas,
`ascii_seul` aussi, `apres` aussi, et `est_un_groupe` aussi (un plan de groupe
contre un plan d'objet) -- c'etait la cause commune des huit survivants de la
couche 1.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]

#: Les maquettes, lues **a leur source** plutot que recopiees -- le geste que
#: `test_atelier_scan_rapport.py` pratique deja, et que
#: `test_frontiere_des_maquettes_recopiees.py` exige de tout banc qui asserte un
#: litteral dessine. Ce banc l'a d'abord recopie : la frontiere a rougi a la
#: course de controle du 2026-09-07, ce qu'aucune relecture n'avait vu.
MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")


def _mention_du_lot_entier() -> str:
    """La mention « tout le lot », LUE du cartouche d'`E6-2`.

    Elle n'est pas recopiee : le jour ou la maquette la reformule, ce banc
    rougit au lieu de mesurer un mot que le produit n'affiche plus. La lecture
    est bornee au titre du cartouche pour ne pas attraper une occurrence de
    corps qui, elle, pourrait bouger independamment.
    """
    dessin = (MAQUETTES / "E6-2-projet-suppression-confirmation.txt").read_text(
        encoding="utf-8")
    # Le cartouche porte « \u00c0 supprimer », avec l'accent et un tiret cadratin :
    # une classe couvre les deux graphies plutot que de figer celle du jour.
    trouve = re.search(r"[A\u00c0] supprimer [^\n]*?(tout le lot)", dessin)
    if trouve is None:
        raise AssertionError(
            "le cartouche d'E6-2 ne porte plus la mention « tout le lot » : "
            "ce banc mesurait un dessin qui a change.")
    return trouve.group(1)


#: Le libelle d'un plan d'OBJET, tel qu'`E6-2` le dessine.
MENTION_DU_LOT_ENTIER = _mention_du_lot_entier()
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.project_inventory import (NATURE_MASTER,
                                                   NATURE_PLANCHE,
                                                   ObjetInventorie)
from mixed_media_utility.project_maintenance import (LigneDeGroupe,
                                                     RapportDeGroupe,
                                                     RapportSuppression)
from mixed_media_utility.tui import projet_inventaire as pi
from mixed_media_utility.tui import projet_suppression as ps
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.execution import Issue

LOT = "plan-04_12p5"

#: Les deux masters que `profil_du_master` SAIT lire sous :data:`LOT`.
VISABLE_A = "plan-04_12p5_mmu_prores_hq.mov"
VISABLE_B = "plan-04_12p5_mmu_dnxhr_hqx.mov"
#: Un master RENOMME a la main : son nom ne nomme aucun profil du registre.
ECARTE_TETE = "renomme-a-la-main.mov"
#: Un second ecarte, d'une AUTRE cause : le noeud ne porte aucun objet de
#: coeur, donc rien ne le rattache a un lot. Deux causes distinctes dans un
#: meme groupe, sans quoi un motif code en dur passerait le banc.
ECARTE_QUEUE = "objet-sans-cible.pdf"


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


def _objet(nature: str, nom: str, rang: int = 1) -> pi.NoeudAffiche:
    return pi._objet_affiche(
        ObjetInventorie(nature=nature, nom=nom, chemin=f"outputs/{nom}",
                        etat=pi.ETAT_PRESENT, rang=rang), 3)


def _sans_cible(nature: str, nom: str) -> pi.NoeudAffiche:
    """Un noeud qu'aucun objet de coeur ne porte : `cible_du_noeud` rend None."""
    return pi.NoeudAffiche(nature=nature, nom=nom, etat=pi.ETAT_PRESENT,
                           profondeur=3, poids=0, fichiers=0, cardinal="",
                           cible=None)


def _groupe(membres, nom: str = "masters — 4 masters") -> pi.NoeudAffiche:
    return pi.NoeudAffiche(
        nature=NATURE_MASTER, nom=nom, etat=pi.ETAT_PRESENT, profondeur=2,
        poids=0, fichiers=0, cardinal="", enfants=list(membres), groupe=True,
        deplie=True)


def _groupe_aux_DEUX_BORDS() -> pi.NoeudAffiche:
    """Un ecarte en TETE, un ecarte en QUEUE, deux visables au milieu."""
    return _groupe([
        _objet(NATURE_MASTER, ECARTE_TETE),
        _objet(NATURE_MASTER, VISABLE_A),
        _objet(NATURE_MASTER, VISABLE_B),
        _sans_cible(NATURE_PLANCHE, ECARTE_QUEUE),
    ])


def _groupe_au_MILIEU() -> pi.NoeudAffiche:
    """L'ecarte entre deux visables : ce que les bords ne mesurent pas."""
    return _groupe([
        _objet(NATURE_MASTER, VISABLE_A),
        _objet(NATURE_MASTER, ECARTE_TETE),
        _objet(NATURE_MASTER, VISABLE_B),
    ], nom="masters — 3 masters")


def _rapport(cible: str, fichiers: tuple[str, ...], dry_run: bool,
             restes: tuple[str, ...] = (),
             scans: tuple[str, ...] = ()) -> RapportSuppression:
    return RapportSuppression(
        cible=cible, fichiers_a_supprimer=fichiers, dry_run=dry_run,
        supprime=not dry_run and not restes,
        fichiers_non_supprimes=restes, dossiers_de_scan=scans)


def _groupe_rendu(libelles_et_refus, dry_run: bool) -> RapportDeGroupe:
    """Un `RapportDeGroupe` ou chaque ligne porte un cardinal DISTINCT.

    Un remplissage uniforme cacherait une concatenation fautive : la regle des
    fabriques, point 1, appliquee aux chemins d'une ligne.
    """
    lignes = []
    for rang, (libelle, refus) in enumerate(libelles_et_refus, start=1):
        if refus:
            lignes.append(LigneDeGroupe(cible={"master": True},
                                        libelle=libelle, refus=refus))
            continue
        lignes.append(LigneDeGroupe(
            cible={"master": True}, libelle=libelle,
            rapport=_rapport(libelle,
                             tuple(f"outputs/{libelle}#{n}"
                                   for n in range(rang)), dry_run)))
    return RapportDeGroupe(lignes=tuple(lignes), dry_run=dry_run)


def _plan_de_groupe(*, ecartes=(), apercu=None,
                    execution=None) -> ps.PlanDeSuppression:
    return ps.PlanDeSuppression(
        projet=Path("/inexistant"), cible={}, libelle="les 2 éléments de « g »",
        rapport=_rapport("g", (), False),
        cibles_du_groupe=((VISABLE_A, {"master": True}),),
        apercu_du_groupe=apercu, execution_du_groupe=execution,
        membres_ecartes=tuple(ecartes))


# ---------------------------------------------------------------------------
# `C1-1` / `C2-1` / `C3-3` -- les membres que le PRODUIT ne sait pas viser
# ---------------------------------------------------------------------------


def test_les_ecartes_des_DEUX_BORDS_sont_nommes_avec_leur_motif_REEL():
    """Un ecarte en tete ET un en queue, chacun avec SA cause.

    Deux causes distinctes dans le meme groupe : un motif code en dur passerait
    un banc a une seule cause, et rendrait la meme phrase pour un master
    illisible et un objet sans lot.
    """
    ecartes = ps.ecartes_du_groupe(_groupe_aux_DEUX_BORDS(), LOT)

    assert [nom for nom, _ in ecartes] == [ECARTE_TETE, ECARTE_QUEUE], ecartes
    motifs = dict(ecartes)
    assert ECARTE_TETE in motifs[ECARTE_TETE], motifs[ECARTE_TETE]
    assert LOT in motifs[ECARTE_TETE], "le motif du master illisible NOMME le lot"
    # Les deux motifs DIFFERENT : c'est ce qui distingue une lecture reelle
    # d'une phrase generique recopiee.
    assert motifs[ECARTE_TETE] != motifs[ECARTE_QUEUE]
    assert motifs[ECARTE_QUEUE] == ps.PHRASE_SANS_LOT.format(
        objet=ps.OBJET_SANS_NOM)


def test_l_ecarte_du_MILIEU_est_nomme_lui_aussi():
    """Le supplement du point 4 : « au milieu » reste exige, il ne suffit pas.

    Un balayage tronque d'un bord laisse cet ecarte-la visible ; c'est
    l'inverse du cas precedent, et les deux ensemble ferment les deux modes.
    """
    ecartes = ps.ecartes_du_groupe(_groupe_au_MILIEU(), LOT)

    assert [nom for nom, _ in ecartes] == [ECARTE_TETE], ecartes


def test_les_ecartes_sont_EXACTEMENT_les_non_visables_de_cibles_du_groupe():
    """La frontiere du second PARCOURS : deux marches, un seul jugement.

    `ecartes_du_groupe` refait la boucle de `cibles_du_groupe` pour lever les
    motifs. Les deux appellent `cible_du_noeud`, donc elles ne peuvent pas
    diverger -- mais « ne peut pas » se mesure, sinon un filtre ajoute d'un
    seul cote passerait inapercu.
    """
    for groupe in (_groupe_aux_DEUX_BORDS(), _groupe_au_MILIEU()):
        cibles, non_visables = ps.cibles_du_groupe(groupe, LOT)
        ecartes = ps.ecartes_du_groupe(groupe, LOT)

        assert tuple(nom for nom, _ in ecartes) == non_visables
        assert len(cibles) + len(ecartes) == len(groupe.enfants)


def test_aucun_ecarte_quand_TOUS_les_membres_sont_visables():
    """L'autre sens du drapeau : un groupe sain ne fabrique aucun bloc."""
    groupe = _groupe([_objet(NATURE_MASTER, VISABLE_A),
                      _objet(NATURE_MASTER, VISABLE_B)])

    assert ps.ecartes_du_groupe(groupe, LOT) == ()


# ---------------------------------------------------------------------------
# `ecartes_du_plan` -- les DEUX familles, aux DEUX temps
# ---------------------------------------------------------------------------


def test_le_plan_rassemble_les_ecartes_du_PRODUIT_et_les_refus_du_COEUR():
    """Un master que rien ne vise et un master que le coeur refuse.

    L'operateur ne distingue pas les deux : les deux fichiers restent. Les
    lister separement l'obligerait a lire deux blocs pour repondre a une seule
    question.
    """
    apercu = _groupe_rendu([(VISABLE_A, ""),
                            (VISABLE_B, "Annexe partagée avec 'plan-09_25'.")],
                           dry_run=True)
    plan = _plan_de_groupe(ecartes=((ECARTE_TETE, "illisible"),),
                           apercu=apercu)

    assert ps.ecartes_du_plan(plan) == (
        (ECARTE_TETE, "illisible"),
        (VISABLE_B, "Annexe partagée avec 'plan-09_25'."))


def test_le_plan_lit_l_EXECUTION_des_qu_elle_existe_et_l_apercu_avant():
    """Les deux TEMPS du meme plan, et ils ne disent pas la meme chose.

    Le coeur relit `project.json` a chaque ligne : une ligne acceptee en apercu
    peut refuser a l'execution -- c'est meme le sujet de `remove_project_group`.
    Lire l'apercu apres coup annoncerait la promesse pour le fait.
    """
    apercu = _groupe_rendu([(VISABLE_A, ""), (VISABLE_B, "")], dry_run=True)
    execution = _groupe_rendu([(VISABLE_A, ""),
                               (VISABLE_B, "Refus survenu a l'ecriture.")],
                              dry_run=False)

    avant = _plan_de_groupe(apercu=apercu)
    assert ps.ecartes_du_plan(avant) == ()

    apres = _plan_de_groupe(apercu=apercu, execution=execution)
    assert ps.ecartes_du_plan(apres) == (
        (VISABLE_B, "Refus survenu a l'ecriture."),)
    # Et l'apercu reste lisible EXPLICITEMENT : c'est ce que la confirmation
    # demande, sur un plan qui porte deja son execution.
    assert ps.ecartes_du_plan(apres, apercu) == ()


def test_un_plan_d_OBJET_n_a_jamais_d_ecarte():
    """L'autre sens du drapeau `est_un_groupe`.

    Sans ce volet, une lecture des ecartes qui deborderait sur le chemin d'un
    objet seul monterait `E6-3` sur une suppression parfaitement reussie.
    """
    plan = ps.PlanDeSuppression(
        projet=Path("/inexistant"), cible={"lot_id": LOT},
        libelle=f"{MENTION_DU_LOT_ENTIER} {LOT}",
        rapport=_rapport(LOT, ("a",), False))

    assert not plan.est_un_groupe
    assert ps.ecartes_du_plan(plan) == ()


# ---------------------------------------------------------------------------
# Le RENDU du bloc : les deux temps, les deux geometries
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("apres,attendu", [
    (False, "ne partiront pas"),
    (True, "ne sont pas partis"),
])
def test_le_bloc_se_conjugue_au_TEMPS_de_son_ecran(apres, attendu):
    """`E6-2` promet, `E6-3` constate. Le drapeau `apres` varie dans les deux
    sens sur le MEME contenu : une phrase unique ferait lire au compte rendu
    une promesse pour un fait."""
    lignes = ps.lignes_des_ecartes(
        [(ECARTE_TETE, "illisible"), (VISABLE_B, "partagé")], apres=apres)

    assert attendu in lignes[0], lignes[0]
    assert f"2 {ps.UNITE_ELEMENTS}" in lignes[0]


@pytest.mark.parametrize("apres,attendu", [
    (False, "ne partira pas"),
    (True, "n'est pas parti"),
])
def test_le_bloc_ACCORDE_son_verbe_sur_un_seul_ecarte(apres, attendu):
    """Le bord du cardinal, aux deux temps."""
    lignes = ps.lignes_des_ecartes([(ECARTE_TETE, "illisible")], apres=apres)

    assert attendu in lignes[0], lignes[0]
    assert f"1 {ps.UNITE_ELEMENT}" in lignes[0]
    assert ps.UNITE_ELEMENTS not in lignes[0], "le pluriel ne doit pas fuiter"


def test_chaque_ecarte_est_NOMME_et_porte_SA_raison_sous_lui():
    """Un cardinal seul ne permettrait pas d'aller chercher ce qui reste."""
    lignes = ps.lignes_des_ecartes(
        [(ECARTE_TETE, "motif du premier"), (VISABLE_B, "motif du second")])
    texte = "\n".join(lignes)

    for nom, motif in ((ECARTE_TETE, "motif du premier"),
                       (VISABLE_B, "motif du second")):
        assert nom in texte and motif in texte
    # La raison est INDENTEE sous son membre, jamais accolee : accolee, la
    # troncature a la largeur emporterait le nom avec elle.
    assert lignes.index(f"  {ECARTE_TETE}") + 1 == lignes.index(
        "    motif du premier")


def test_le_bloc_est_VIDE_sans_ecarte():
    """Aucune ligne vide, aucun titre orphelin : le bloc n'existe pas."""
    assert ps.lignes_des_ecartes([]) == []
    assert ps.lignes_des_ecartes((), apres=True) == []


def test_le_bloc_se_REPLIE_en_ascii_et_le_drapeau_varie_dans_les_deux_sens():
    """Le glyphe d'absence et la raison passent par `_replie`, ou rien ne passe.

    Une garde qui ne ferait pas varier `ascii_seul` mesurerait la moitie du
    produit et l'annoncerait verte -- le defaut paye le 2026-09-06 sur onze
    des quatorze ecrans montables.
    """
    raison = "le lot « L » ne déclare rien — voir plus haut…"
    riche = ps.lignes_des_ecartes([(ECARTE_TETE, raison)], False)
    ascii_seul = ps.lignes_des_ecartes([(ECARTE_TETE, raison)], True)

    assert riche != ascii_seul, "aucun repli n'a eu lieu"
    joint = "\n".join(ascii_seul)
    for glyphe in ("…", "—", "«", "»"):
        assert glyphe not in joint, f"{glyphe!r} survit au repli ASCII"


# ---------------------------------------------------------------------------
# `C3-2` / `C3-2b` -- l'ecran choisi, et le cartouche qui va avec
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("refus,attendu", [
    ("", "EcranReussiteDeSuppression"),
    ("Le coeur refuse cette ligne.", "EcranResultatDeSuppression"),
])
def test_un_groupe_REFUSE_ne_monte_PAS_l_ecran_de_reussite(refus, attendu):
    """Le drapeau « une ligne a-t-elle refuse » varie dans les deux sens.

    Sans le volet negatif, un choix d'ecran cable en dur sur `E6-3` passerait
    le volet positif et casserait tout le chemin nominal.
    """
    execution = _groupe_rendu([(VISABLE_A, ""), (VISABLE_B, refus)],
                              dry_run=False)
    plan = _plan_de_groupe(execution=execution)
    agrege = ps.rapport_agrege_du_groupe(plan.libelle, execution)

    ecran = ps.monter_le_compte_rendu(None, plan, agrege,
                                      Issue(ps.CLE_SUPPRIMER, "x", ecrit=True))

    assert type(ecran).__name__ == attendu


def test_un_groupe_ENTIEREMENT_refuse_ne_monte_PAS_l_ecran_de_reussite():
    """L'autre bord du meme drapeau : plus rien ne part.

    Sans ce volet, une correction qui ne traiterait que le cas partiel
    passerait pour complete -- et le cas total est le pire des deux, puisque
    l'ecran annoncerait « Supprimes 0 fichiers » comme un travail accompli.
    """
    execution = _groupe_rendu([(VISABLE_A, "Refus du premier."),
                               (VISABLE_B, "Refus du second.")],
                              dry_run=False)
    plan = _plan_de_groupe(execution=execution)
    agrege = ps.rapport_agrege_du_groupe(plan.libelle, execution)

    assert agrege.fichiers_non_supprimes == (), (
        "le regime du finding : la liste des restes est VIDE, et c'est "
        "pourquoi l'ecran de reussite se montait")
    ecran = ps.monter_le_compte_rendu(None, plan, agrege,
                                      Issue(ps.CLE_SUPPRIMER, "x", ecrit=True))

    assert type(ecran).__name__ == "EcranResultatDeSuppression"


def test_un_membre_NON_VISABLE_suffit_a_ecarter_l_ecran_de_reussite():
    """La seconde cause, seule. Le coeur n'a rien refuse -- il n'a jamais vu
    ce membre --, et pourtant le groupe n'est pas parti en entier."""
    execution = _groupe_rendu([(VISABLE_A, "")], dry_run=False)
    plan = _plan_de_groupe(ecartes=((ECARTE_TETE, "illisible"),),
                           execution=execution)
    agrege = ps.rapport_agrege_du_groupe(plan.libelle, execution)

    ecran = ps.monter_le_compte_rendu(None, plan, agrege,
                                      Issue(ps.CLE_SUPPRIMER, "x", ecrit=True))

    assert type(ecran).__name__ == "EcranResultatDeSuppression"


def test_le_cartouche_d_E6_3_compte_les_ecartes_en_ELEMENTS():
    """Sans cette ligne, le cartouche se contredisait : « Restés 0 fichiers »
    au-dessus d'un bloc qui nomme deux membres restes. Les deux disent vrai --
    aucun FICHIER n'a resiste --, d'ou l'unite en elements."""
    execution = _groupe_rendu([(VISABLE_A, "Refus A."), (VISABLE_B, "Refus B.")],
                              dry_run=False)
    plan = _plan_de_groupe(execution=execution)
    agrege = ps.rapport_agrege_du_groupe(plan.libelle, execution)

    panneau = ps.panneau_du_resultat(plan, agrege)
    libelles = [ligne.libelle for ligne in panneau.lignes]
    ecartes = [l for l in panneau.lignes if l.libelle == ps.LIBELLE_ECARTES]

    assert ps.LIBELLE_ECARTES in libelles, libelles
    assert ecartes[0].valeur == 2
    assert ecartes[0].unite == ps.UNITE_ELEMENTS


def test_le_cartouche_d_E6_3_n_a_PAS_de_ligne_d_ecartes_sans_ecarte():
    """L'autre sens : une ligne a zero serait une ligne sans objet."""
    plan = ps.PlanDeSuppression(
        projet=Path("/inexistant"), cible={"lot_id": LOT},
        libelle=MENTION_DU_LOT_ENTIER,
        rapport=_rapport(LOT, ("a",), False, restes=("a",)))

    panneau = ps.panneau_du_resultat(plan, plan.rapport)

    assert ps.LIBELLE_ECARTES not in [l.libelle for l in panneau.lignes]


# ---------------------------------------------------------------------------
# `C2-6` -- l'appariement apercu / execution
# ---------------------------------------------------------------------------


def test_les_restes_d_une_ligne_refusee_sont_relus_par_RANG_et_non_par_libelle():
    """Deux membres HOMONYMES, et le survivant est le PREMIER.

    Mesure du finding, par libelle : `restes` portait `outputs/SECOND.pdf`
    alors que le survivant est `PREMIER.pdf` -- le second ecrasait le premier
    dans le dictionnaire, et la ligne refusee relisait la promesse de l'autre.

    **Ce banc ne ferme pas un regime de terrain**, et il ne faut pas le
    surcoter : aucune des deux couches de revue qui ont vu ce finding n'a su
    produire un manifeste sain donnant deux membres homonymes. Il tient une
    simplification -- une dependance a une unicite non garantie a disparu.
    """
    homonyme = "MEME-NOM.pdf"
    apercu = RapportDeGroupe(dry_run=True, lignes=(
        LigneDeGroupe(cible={"planche": True}, libelle=homonyme,
                      rapport=_rapport(homonyme, ("outputs/PREMIER.pdf",), True)),
        LigneDeGroupe(cible={"planche": True}, libelle=homonyme,
                      rapport=_rapport(homonyme, ("outputs/SECOND.pdf",), True)),
    ))
    execution = RapportDeGroupe(dry_run=False, lignes=(
        # La PREMIERE refuse : c'est sa promesse qu'il faut relire.
        LigneDeGroupe(cible={"planche": True}, libelle=homonyme,
                      refus="Refus de la premiere."),
        LigneDeGroupe(cible={"planche": True}, libelle=homonyme,
                      rapport=_rapport(homonyme, ("outputs/SECOND.pdf",), False)),
    ))

    agrege = ps.rapport_agrege_du_groupe("les 2", execution, apercu)

    assert agrege.fichiers_non_supprimes == ("outputs/PREMIER.pdf",), \
        agrege.fichiers_non_supprimes
    assert agrege.fichiers_a_supprimer == ("outputs/SECOND.pdf",)


def test_un_apercu_PLUS_COURT_que_l_execution_ne_leve_pas():
    """Le rang deborde-t-il ? Une garde d'indice qui manquerait ferait planter
    l'ecran la ou l'ancienne lecture par libelle rendait ``None``.

    Le regime n'est pas atteignable par `remove_project_group`, qui emet une
    ligne par cible des deux cotes ; il l'est par un double de banc, et une
    frontiere vaut mieux qu'un pari.
    """
    execution = _groupe_rendu([(VISABLE_A, "Refus A."), (VISABLE_B, "Refus B.")],
                              dry_run=False)
    court = RapportDeGroupe(dry_run=True, lignes=execution.lignes[:1])

    agrege = ps.rapport_agrege_du_groupe("les 2", execution, court)

    assert agrege.fichiers_non_supprimes == ()


@pytest.mark.parametrize("dry_run", [True, False])
def test_l_agregat_ne_porte_JAMAIS_de_dossier_de_scan(dry_run):
    """`C2-7`, premiere moitie, et le drapeau `dry_run` varie dans les deux sens.

    Mesure du 2026-09-07 sur les six cibles du coeur : les cinq cibles FINES
    rendent `dossiers_de_scan=()`, seul le lot entier renseigne le champ, et un
    groupe ne porte que des cibles fines. La ligne qui collectait ce champ ne
    pouvait donc rien collecter -- mutant `M32`, survivant.

    Ce banc joue le regime que le coeur ne produit pas : une ligne qui SIGNALE
    un dossier de scan. Si le champ etait a nouveau collecte, il deviendrait
    `plan.scans_nommes`, donc l'issue « Supprimer avec les scans » -- que
    :func:`executer_la_suppression` IGNORE sur un groupe, ou seul `issue.ecrit`
    est lu. C'est-a-dire une issue sans effet, la promesse cassee
    qu'`issues_de_la_suppression` interdit.
    """
    groupe = RapportDeGroupe(dry_run=dry_run, lignes=(
        LigneDeGroupe(cible={"lot_id": LOT}, libelle=VISABLE_A,
                      rapport=_rapport(VISABLE_A, ("outputs/a",), dry_run,
                                       scans=("scans/scan-du-lundi",))),
    ))

    agrege = ps.rapport_agrege_du_groupe("les 1", groupe)

    assert agrege.dossiers_de_scan == ()
    assert agrege.scan_inclus is False
    plan = _plan_de_groupe()
    plan.rapport = agrege
    assert plan.scans_nommes == ()


# ---------------------------------------------------------------------------
# `C2-7`, seconde moitie -- « Emportés avec le lot » sur un groupe sans lot
# ---------------------------------------------------------------------------


def test_le_cartouche_d_un_GROUPE_n_annonce_pas_un_emport_PAR_LE_LOT():
    """Un groupe ne retire aucun lot : ses cibles sont FINES, et le lot reste
    declare apres chacune. Le drapeau `est_un_groupe` varie dans les deux sens
    sur le meme rapport -- sans le volet negatif, un libelle cable en dur
    passerait ici et casserait le cartouche d'un objet."""
    rapport = _rapport(LOT, ("outputs/a.pdf", "outputs/b.pdf"), True)
    commun = dict(projet=Path("/inexistant"), libelle="x", rapport=rapport,
                  groupes=(ps.GroupeEmporte("outputs/", 2, 10),))

    groupe = ps.PlanDeSuppression(
        cible={}, cibles_du_groupe=((VISABLE_A, {"master": True}),), **commun)
    objet = ps.PlanDeSuppression(cible={"lot_id": LOT}, **commun)

    libelles_du_groupe = [l.libelle for l
                          in ps.panneau_de_la_confirmation(groupe).lignes]
    libelles_de_l_objet = [l.libelle for l
                           in ps.panneau_de_la_confirmation(objet).lignes]

    assert ps.LIBELLE_EMPORTES_DU_GROUPE in libelles_du_groupe
    assert ps.LIBELLE_EMPORTES not in libelles_du_groupe, (
        "le cartouche d'un groupe annonce un emport PAR LE LOT : "
        f"{libelles_du_groupe}")
    assert ps.LIBELLE_EMPORTES in libelles_de_l_objet


# ---------------------------------------------------------------------------
# Le detail de l'execution est GARDE plutot que jete
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dry_run_de_l_issue", [True, False])
def test_executer_la_suppression_POSE_le_rapport_de_groupe_sur_le_plan(
        dry_run_de_l_issue):
    """Le champ symetrique d'`apercu_du_groupe`, et il manquait.

    Sans lui, la phrase du coeur -- la seule chose qui dise POURQUOI une ligne
    a refuse -- etait produite puis jetee entre l'appel au coeur et l'ecran.
    """
    appels = []

    def _double(projet, cibles, *, dry_run=True):
        appels.append(dry_run)
        return _groupe_rendu([(VISABLE_A, ""), (VISABLE_B, "Refus B.")],
                             dry_run=False)

    plan = _plan_de_groupe()
    assert plan.execution_du_groupe is None

    ps.executer_la_suppression(
        plan, Issue(ps.CLE_SUPPRIMER, "x", ecrit=True),
        retirer_le_groupe=_double)

    assert plan.execution_du_groupe is not None
    assert [l.libelle for l in plan.execution_du_groupe.lignes] == [
        VISABLE_A, VISABLE_B]
    # **L'ecriture part toujours en `dry_run=False`**, quelle que soit l'issue :
    # le consentement se joue sur `issue.ecrit`, jamais sur un dry-run rejoue.
    assert appels == [False]


def test_l_issue_qui_N_ECRIT_PAS_ne_pose_aucun_rapport_d_execution():
    """L'autre sens du drapeau `issue.ecrit` : `Annuler` ne touche pas le coeur,
    donc il ne doit rien laisser sur le plan non plus."""
    plan = _plan_de_groupe()

    def _double(*_a, **_k):  # pragma: no cover - il ne doit pas etre appele
        raise AssertionError("le coeur a ete appele sous une issue qui n'ecrit pas")

    assert ps.executer_la_suppression(
        plan, Issue(ps.CLE_ANNULER, "x"), retirer_le_groupe=_double) is None
    assert plan.execution_du_groupe is None


# ---------------------------------------------------------------------------
# Le nom que le bloc porte : celui du COEUR, jamais celui que l'ecran AFFICHE
# ---------------------------------------------------------------------------


def test_l_ecarte_porte_le_nom_du_COEUR_et_non_la_mention_d_affichage():
    """Mutant survivant de la premiere campagne : `identifiant_du_noeud(...) or
    membre.nom` reduit a `membre.nom`.

    `_nom_affiche` suffixe ` · non déclaré` a tout objet que le manifeste
    ignore -- c'est une mention DESSINEE, pas un identifiant. Toutes les
    fabriques de ce banc produisaient des objets declares, si bien que les deux
    noms coincidaient et que la reduction passait : exactement le defaut `F2`,
    et exactement la regle des fabriques (un remplissage uniforme cache une
    permutation).

    Le regime est reel et c'est le pire : un orphelin non declare est
    precisement l'objet que cet ecran existe pour rendre visible, et le nommer
    par sa mention ferait chercher a l'operateur un fichier qui n'a pas ce
    nom-la sur le disque.
    """
    non_declare = pi._objet_affiche(
        ObjetInventorie(nature=NATURE_MASTER, nom=ECARTE_TETE,
                        chemin=f"outputs/{ECARTE_TETE}",
                        etat=pi.ETAT_NON_DECLARE, rang=1), 3)
    assert non_declare.nom != ECARTE_TETE, (
        "la fabrique ne produit pas la mention d'affichage : le banc ne "
        f"mesurerait rien ({non_declare.nom!r})")

    ecartes = ps.ecartes_du_groupe(
        _groupe([non_declare, _objet(NATURE_MASTER, VISABLE_A)]), LOT)

    assert [nom for nom, _ in ecartes] == [ECARTE_TETE], ecartes
    assert pi.MENTION_NON_DECLARE not in ecartes[0][0]


# ---------------------------------------------------------------------------
# Le bloc SUR L'ECRAN : `C1-2` cote confirmation, `C3-2` cote compte rendu
# ---------------------------------------------------------------------------


def _app(ecran) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"), ecran],
                    contexte=Contexte(projet="projet_demo"))


def _monte(ecran, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(_app(ecran), tour)


def _plan_a_deux_ecartes() -> ps.PlanDeSuppression:
    """Un plan de groupe portant les DEUX familles d'ecartes a la fois."""
    apercu = _groupe_rendu([(VISABLE_A, ""),
                            (VISABLE_B, "Annexe partagée avec 'plan-09_25'.")],
                           dry_run=True)
    plan = _plan_de_groupe(ecartes=((ECARTE_TETE, "Nom illisible du master."),),
                           apercu=apercu)
    plan.rapport = ps.rapport_agrege_du_groupe(plan.libelle, apercu)
    return plan


def test_la_CONFIRMATION_montre_le_bloc_des_ecartes(banc):
    """Mutant survivant de la premiere campagne : le bloc retire d'`E6-2` seul.

    `C3-3` lisait la confirmation ET le compte rendu dans une meme chaine, si
    bien que le bloc pouvait disparaitre du point de JUGEMENT sans qu'un banc
    rougisse -- alors que c'est le seul des deux ecrans ou l'operateur decide
    encore quelque chose. C'est le finding `C1-2` lui-meme, et il exige zero
    survivant.
    """
    plan = _plan_a_deux_ecartes()
    ecran = ps.EcranSuppressionConfirmation(plan, sur_issue=lambda issue: None)

    async def scenario(pilote):
        return ecran.lignes_du_panneau()

    texte = "\n".join(_monte(ecran, scenario, banc))

    assert ECARTE_TETE in texte, texte
    assert VISABLE_B in texte, texte
    assert "Nom illisible du master." in texte
    assert "Annexe partagée" in texte
    # **Au FUTUR sur la confirmation** : rien n'est encore ecrit (AC 3.3).
    assert "ne partiront pas" in texte, texte
    assert "ne sont pas partis" not in texte


def test_le_COMPTE_RENDU_conjugue_le_bloc_au_PASSE(banc):
    """Mutant survivant : `apres=True` reduit a `apres=False` sur `E6-3`.

    `lignes_des_ecartes` etait mesuree aux deux temps, mais rien ne mesurait
    QUEL temps l'ecran lui demande. Un compte rendu au futur annoncerait ce
    qu'il allait faire -- l'ecart exact qu'`AC 4.2` ferme de l'autre cote.
    """
    execution = _groupe_rendu([(VISABLE_A, ""), (VISABLE_B, "Refus du coeur.")],
                              dry_run=False)
    plan = _plan_de_groupe(execution=execution)
    rapport = ps.rapport_agrege_du_groupe(plan.libelle, execution)
    ecran = ps.EcranResultatDeSuppression(plan, rapport)

    async def scenario(pilote):
        ecran.rafraichir()
        return ecran.lignes()

    texte = "\n".join(_monte(ecran, scenario, banc))

    assert VISABLE_B in texte and "Refus du coeur." in texte, texte
    assert "ne sont pas partis" in texte or "n'est pas parti" in texte, texte
    assert "ne partiront pas" not in texte
    assert "ne partira pas" not in texte


def test_le_CURSEUR_d_E6_3_designe_une_SUITE_et_non_une_ligne_du_bloc(banc):
    """Mutant survivant : le rang du curseur ne comptait pas le bloc ajoute.

    Le module ecrit lui-meme le piege -- « un rang herite ne planterait pas :
    il colorerait la mauvaise ligne, ce qui est pire ». Intercaler un bloc sans
    l'ajouter au compte fait exactement ca, et aucune assertion ne le voyait.

    La mesure porte sur les lignes RENDUES : le rang designe la ligne qui porte
    le curseur, pour chacune des trois suites.
    """
    execution = _groupe_rendu([(VISABLE_A, ""), (VISABLE_B, "Refus du coeur.")],
                              dry_run=False)
    plan = _plan_de_groupe(execution=execution)
    rapport = ps.rapport_agrege_du_groupe(plan.libelle, execution)
    ecran = ps.EcranResultatDeSuppression(plan, rapport)

    async def scenario(pilote):
        vus = []
        for rang in range(len(ecran.suites)):
            ecran.curseur = rang
            ecran.rafraichir()
            vus.append((ecran.rang_du_curseur(), ecran.lignes(),
                        ecran.suites[rang]))
        return vus

    for rang, lignes, suite in _monte(ecran, scenario, banc):
        assert rang is not None and 0 <= rang < len(lignes), (rang, len(lignes))
        assert suite in lignes[rang], (
            f"le curseur designe {lignes[rang]!r} au lieu de la suite "
            f"{suite!r} -- le bloc des ecartes n'est pas compte")
