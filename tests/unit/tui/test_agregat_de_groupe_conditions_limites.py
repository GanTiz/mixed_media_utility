# -*- coding: utf-8 -*-
"""Les conditions limites de `rapport_agrege_du_groupe` (`EPIC11-ARB-264`).

**Ce banc est ne d'une campagne de mutation**, couche 2 de la revue de la
vague 2 de l'Epic 11 (2026-09-07). Il ne double aucun test de
`test_suppression_d_un_groupe_depuis_la_tui.py` : il joue les regimes que ce
banc-la ne visite pas, et par lesquels deux mutants sont passes vivants.

Les deux mutants, et le regime exact qui les demasque :

* `supprime=not groupe.dry_run and not restes and not groupe.refusees` ->
  la conjonction privee de `and not groupe.refusees`. **SURVIVANT** : le seul
  banc qui mesure `supprime is False` sur un refus le fait sur une ligne dont
  l'APERCU promettait des fichiers, si bien que `restes` suffit a le tenir. Le
  regime qui separe les deux est une ligne refusee dont l'apercu ne promettait
  RIEN -- un master deja disparu du disque, dont le dry-run annonce zero
  fichier et une annexe attendue-absente. Sous le mutant, un groupe dont une
  ligne a refuse s'annonce SUPPRIME, c'est-a-dire `E6-3b` (« reussite ») au
  lieu d'`E6-3` : l'operateur ne sait pas quoi relancer, ce que
  `EPIC11-ARB-264` existe precisement pour lui donner ;
* `if groupe.dry_run: restes = []` -> `if False:`. **SURVIVANT** : aucun
  appelant du produit ne passe a la fois un rapport d'APERCU et un apercu, si
  bien que la branche n'est atteinte par aucun banc. Elle enonce pourtant une
  regle -- « en apercu, ce qu'une ligne refusee promettait n'existe pas » --
  et une regle non mesuree est une prose. Elle est appelee ici a sa surface
  publique, comme le fait deja
  `test_la_ligne_d_eau_inexistante_LEVE_au_lieu_de_se_taire` pour l'autre
  interne du meme lot.
"""
from __future__ import annotations

import pytest

from mixed_media_utility.project_maintenance import (
    LigneDeGroupe, RapportDeGroupe, RapportSuppression)
from mixed_media_utility.tui import projet_suppression as ps


# ---------------------------------------------------------------------------
# La fabrique : TROIS lignes distinguables, la fautive a chaque BORD.
# ---------------------------------------------------------------------------


def _rapport(cible, fichiers=(), *, dry_run, restes=(), absents=()):
    return RapportSuppression(
        cible=cible, fichiers_a_supprimer=fichiers, dry_run=dry_run,
        supprime=not dry_run and not restes,
        fichiers_non_supprimes=restes, fichiers_attendus_absents=absents)


#: Trois libelles DISTINGUABLES, et des cardinaux de fichiers differents : une
#: permutation entre deux lignes ne se voit pas sur un remplissage uniforme
#: (regle des fabriques, point 1).
LIBELLES = ("master v1", "master v2", "master v3")


def _apercu(promesses: dict[str, tuple[str, ...]]) -> RapportDeGroupe:
    """L'apercu : chaque ligne promet la liste de chemins qu'on lui donne.

    Une promesse VIDE est le cas qui compte ici -- un objet declare dont le
    fichier a deja disparu : le dry-run le delie sans annoncer un seul chemin.
    """
    return RapportDeGroupe(dry_run=True, lignes=tuple(
        LigneDeGroupe(cible={"lot_id": "L", "master": True}, libelle=libelle,
                      rapport=_rapport(libelle, promesses[libelle],
                                       dry_run=True,
                                       absents=(() if promesses[libelle]
                                                else (f"outputs/{libelle}",))))
        for libelle in LIBELLES))


def _execution(promesses: dict[str, tuple[str, ...]],
               refuse: str) -> RapportDeGroupe:
    lignes = []
    for libelle in LIBELLES:
        if libelle == refuse:
            lignes.append(LigneDeGroupe(
                cible={"lot_id": "L", "master": True}, libelle=libelle,
                refus=f"Refus propre a {libelle}."))
            continue
        lignes.append(LigneDeGroupe(
            cible={"lot_id": "L", "master": True}, libelle=libelle,
            rapport=_rapport(libelle, promesses[libelle], dry_run=False)))
    return RapportDeGroupe(dry_run=False, lignes=tuple(lignes))


def _promesses(vide: str) -> dict[str, tuple[str, ...]]:
    """Toutes les lignes promettent des chemins, sauf `vide`, qui n'en promet
    aucun : c'est ce contraste qui separe `restes` de `refusees`."""
    return {
        libelle: () if libelle == vide else tuple(
            f"outputs/{libelle}#{n}" for n in range(rang))
        for rang, libelle in enumerate(LIBELLES, start=1)
    }


# ---------------------------------------------------------------------------
# Un refus, meme sans un seul chemin a rendre, interdit « supprime ».
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fautive", LIBELLES, ids=["tete", "milieu", "queue"])
def test_une_ligne_REFUSEE_qui_ne_promettait_RIEN_interdit_quand_meme_SUPPRIME(
        fautive):
    """Le seul volet qui separe `refusees` de `restes`.

    Les trois positions sont jouees : la cible au milieu demasque un
    appariement fautif, elle ne demasque pas un balayage tronque, et ce sont
    deux modes de panne differents (regle des fabriques, point 4).
    """
    promesses = _promesses(vide=fautive)
    agrege = ps.rapport_agrege_du_groupe(
        "les 3", _execution(promesses, refuse=fautive), _apercu(promesses))
    assert agrege.fichiers_non_supprimes == (), (
        "la ligne refusee ne promettait aucun chemin : il n'y a rien a rendre")
    assert agrege.supprime is False, (
        "une ligne a REFUSE : le groupe n'est pas parti, meme si rien ne "
        "reste a nommer")


def test_le_volet_POSITIF_du_meme_champ_un_groupe_ENTIER_est_SUPPRIME():
    """Sans lui, un `supprime` cable a `False` passerait le test ci-dessus.

    La ligne dont l'apercu ne promettait rien est TOUJOURS la -- elle ne refuse
    simplement plus --, si bien que les deux mesures ne different que par le
    refus.
    """
    promesses = _promesses(vide="master v2")
    execution = RapportDeGroupe(dry_run=False, lignes=tuple(
        LigneDeGroupe(cible={"lot_id": "L", "master": True}, libelle=libelle,
                      rapport=_rapport(libelle, promesses[libelle],
                                       dry_run=False))
        for libelle in LIBELLES))
    agrege = ps.rapport_agrege_du_groupe("les 3", execution, _apercu(promesses))
    assert agrege.supprime is True
    assert agrege.fichiers_non_supprimes == ()


# ---------------------------------------------------------------------------
# L'APERCU ne porte pas de restes, et la regle se mesure a sa surface.
# ---------------------------------------------------------------------------


def test_en_APERCU_ce_qu_une_ligne_refusee_promettait_n_EXISTE_PAS():
    """« En apercu, rien n'a resiste et rien n'a ete refuse au sens du
    disque. »

    Le produit n'atteint pas cette branche -- `preparer_la_suppression_du_
    groupe` n'a pas d'apercu ANTERIEUR a passer --, mais la fonction est
    publique et sa regle est ecrite. Sans cette garde, un appelant neuf lirait
    en apercu une liste de « fichiers qui restent » qui n'a pas de sens : rien
    n'a encore ete detruit.
    """
    promesses = _promesses(vide="master v3")
    apercu = _apercu(promesses)
    refuse = RapportDeGroupe(dry_run=True, lignes=(
        LigneDeGroupe(cible={"lot_id": "L", "master": True},
                      libelle="master v1", refus="Refus a l'apercu."),
    ) + apercu.lignes[1:])
    agrege = ps.rapport_agrege_du_groupe("les 3", refuse, apercu)
    assert agrege.dry_run is True
    assert agrege.fichiers_non_supprimes == (), (
        "en apercu, ce qu'une ligne refusee promettait n'a pas ete detruit")
    assert agrege.supprime is False


def test_une_ligne_ACCEPTEE_dont_des_fichiers_ont_RESISTE_remplit_les_restes():
    """L'autre moitie des « restes », et elle n'est pas de la meme nature.

    Un refus n'a rien detruit ; un echec partiel a detruit une partie et laisse
    le reste sur le disque. Les deux remontent au meme champ parce que
    l'operateur y lit la meme chose -- ce qui occupe encore le disque --, mais
    ils n'arrivent pas par le meme chemin, et le banc de la vague ne joue que
    le premier : son double de groupe ne modelise aucune resistance de fichier.
    """
    lignes = (
        LigneDeGroupe(cible={}, libelle="master v1",
                      rapport=_rapport("master v1", ("outputs/v1.mov",),
                                       dry_run=False)),
        LigneDeGroupe(cible={}, libelle="master v2",
                      rapport=_rapport("master v2", ("outputs/v2.mov",),
                                       dry_run=False,
                                       restes=("outputs/v2.mov",))),
    )
    agrege = ps.rapport_agrege_du_groupe(
        "les 2", RapportDeGroupe(dry_run=False, lignes=lignes))
    assert agrege.fichiers_a_supprimer == ("outputs/v1.mov", "outputs/v2.mov")
    assert agrege.fichiers_non_supprimes == ("outputs/v2.mov",), (
        "un fichier qui a resiste occupe toujours le disque : le taire ferait "
        "annoncer une reussite")
    assert agrege.supprime is False


def test_les_chemins_ne_sont_JAMAIS_RETRIES_par_dessus_les_lignes():
    """Chaque appel au coeur a deja trie SA liste (`EPIC11-ARB-243`).

    Un tri global par-dessus melangerait les objets et ferait perdre la seule
    chose que la liste de groupe ajoute : savoir quel fichier part avec quelle
    ligne. La mesure ne vaut que sur un ordre de lignes qui DIFFERE de l'ordre
    trie -- le banc de la vague nomme ses trois planches `aaa`, `bbb`, `ccc`,
    c'est-a-dire dans l'ordre ou un tri les rendrait, si bien qu'un tri y
    resterait invisible.
    """
    lignes = (
        LigneDeGroupe(cible={}, libelle="z-dernier",
                      rapport=_rapport("z", ("outputs/z0.mov",
                                             "outputs/z1.mov"),
                                       dry_run=True)),
        LigneDeGroupe(cible={}, libelle="a-premier",
                      rapport=_rapport("a", ("outputs/a0.mov",),
                                       dry_run=True)),
    )
    agrege = ps.rapport_agrege_du_groupe(
        "les 2", RapportDeGroupe(dry_run=True, lignes=lignes))
    assert agrege.fichiers_a_supprimer == (
        "outputs/z0.mov", "outputs/z1.mov", "outputs/a0.mov")


# ---------------------------------------------------------------------------
# Le groupe PARTIELLEMENT visable : le cartouche compte les VISABLES.
# ---------------------------------------------------------------------------


def _objet_de_membre(nature: str, nom: str):
    from mixed_media_utility.project_inventory import (ETAT_PRESENT,
                                                       ObjetInventorie)
    from mixed_media_utility.tui import projet_inventaire as pi
    return pi._objet_affiche(ObjetInventorie(
        nature=nature, nom=nom, chemin=f"outputs/{nom}", etat=ETAT_PRESENT,
        rang=1), 3)


class _ApplicationTemoin:
    """Le strict minimum que `_ouvrir_la_suppression_du_groupe` appelle."""

    def __init__(self):
        self.montes = []

    def descendre(self, ecran):
        self.montes.append(ecran)


def test_le_CARTOUCHE_d_un_groupe_PARTIELLEMENT_visable_compte_les_VISABLES():
    """Le cardinal du libelle est celui des cibles, jamais celui des membres.

    **C'est le seul regime ou les deux different**, et aucun banc de la vague
    ne le visite : sur un groupe entierement visable, `len(cibles)` et
    `len(noeud.enfants)` sont egaux, si bien qu'un mutant qui echange les deux
    reste vert. Le regime qui les separe est un membre que `cible_du_noeud` ne
    sait pas designer -- ici un master renomme a la main, dont le nom ne nomme
    aucun profil du registre --, place au MILIEU pour qu'un balayage qui
    s'arrete a la premiere anomalie ne le rattrape pas.

    Le cartouche `E6-2` annonce ce qui va etre detruit : y compter un membre
    qui ne partira pas ferait confirmer une destruction plus large que celle
    qui aura lieu.
    """
    from mixed_media_utility.project_inventory import NATURE_MASTER
    from mixed_media_utility.tui import projet_inventaire as pi

    membres = [
        _objet_de_membre(NATURE_MASTER, "L_mmu_prores_422.mov"),
        _objet_de_membre(NATURE_MASTER, "renomme-a-la-main.mov"),
        _objet_de_membre(NATURE_MASTER, "L_mmu_dnxhr_hq.mov"),
    ]
    groupe = pi.NoeudAffiche(
        nature=NATURE_MASTER, nom="masters — 3 masters", etat=pi.ETAT_PRESENT,
        profondeur=2, poids=0, fichiers=0, cardinal="", enfants=membres,
        groupe=True, deplie=True)

    def _double(projet, cibles, *, dry_run=True):
        return RapportDeGroupe(dry_run=dry_run, lignes=tuple(
            LigneDeGroupe(cible=dict(c), libelle=lib,
                          rapport=_rapport(lib, (f"outputs/{lib}",),
                                           dry_run=dry_run))
            for lib, c in cibles))

    application = _ApplicationTemoin()
    assert ps._ouvrir_la_suppression_du_groupe(
        application, groupe, projet="/projet", lot_id="L",
        retirer_le_groupe=_double) is True
    plan = application.montes[-1].plan
    assert len(plan.cibles_du_groupe) == 2
    assert plan.libelle == "les 2 éléments de « masters — 3 masters »", (
        "le cartouche annonce ce qui part, pas ce que la ligne porte")
    # **L'ORDRE de l'arbre, jamais trie** (`EPIC11-ARB-109`) : c'est aussi
    # l'ordre de DESTRUCTION. Les deux visables sont donnes ici dans un ordre
    # que `sorted` renverserait (`dnxhr` avant `prores`), sans quoi un tri pose
    # sur le chemin resterait invisible.
    assert [libelle for libelle, _ in plan.cibles_du_groupe] == [
        "L_mmu_prores_422.mov", "L_mmu_dnxhr_hq.mov"]


def test_les_ANNEXES_attendues_absentes_remontent_DEDUPLIQUEES_et_dans_l_ordre(
):
    """L'union des absences, sans doublon et sans tri.

    Deux lignes peuvent nommer la meme annexe -- deux masters d'un meme lot
    dont le PDF de planches se recalcule au meme nom --, et l'operateur ne doit
    la lire qu'une fois. Un tri, lui, detruirait l'ordre des lignes, qui est
    l'ordre de destruction.
    """
    lignes = (
        LigneDeGroupe(cible={}, libelle="z-dernier",
                      rapport=_rapport("z", (), dry_run=False,
                                       absents=("outputs/z.mov",
                                                "outputs/commun.pdf"))),
        LigneDeGroupe(cible={}, libelle="a-premier",
                      rapport=_rapport("a", (), dry_run=False,
                                       absents=("outputs/commun.pdf",
                                                "outputs/a.mov"))),
    )
    agrege = ps.rapport_agrege_du_groupe(
        "les 2", RapportDeGroupe(dry_run=False, lignes=lignes))
    assert agrege.fichiers_attendus_absents == (
        "outputs/z.mov", "outputs/commun.pdf", "outputs/a.mov")


# ---------------------------------------------------------------------------
# `Espace` : le drapeau de la coche VARIE dans les deux sens.
# ---------------------------------------------------------------------------


def test_ESPACE_DECOCHE_aussi_et_pas_seulement_sur_un_groupe():
    """L'autre sens du geste, sur les DEUX natures de ligne.

    `EPIC11-ARB-264` a ouvert la coche aux groupes, et les bancs de la vague
    cochent -- jamais ils ne decochent. Un `noeud.coche = True` cable a la
    place de la bascule passe donc l'ensemble : mesure le 2026-09-07, il
    survit aux quatre bancs TUI du lot. Ce qu'il coute a l'operateur est une
    impasse : deux lignes cochees par erreur, et `Suppr` ne rend plus que
    `MOTIF_DE_LA_SELECTION_MULTIPLE` sans qu'aucune touche ne defasse la
    coche.

    Le groupe ET l'objet sont joues, parce que `basculer` ne les distingue plus
    et que c'est exactement ce que la vague a change.
    """
    from mixed_media_utility.project_inventory import (ETAT_PRESENT,
                                                       NATURE_PLANCHE)
    from mixed_media_utility.tui import projet_inventaire as pi

    membre = _objet_de_membre(NATURE_PLANCHE, "p_demo_L_2f-aaa.pdf")
    groupe = pi.NoeudAffiche(
        nature=NATURE_PLANCHE, nom="planches — 1 planche", etat=ETAT_PRESENT,
        profondeur=2, poids=0, fichiers=0, cardinal="", enfants=[membre],
        groupe=True, deplie=True)
    arbre = pi.ArbreDuProjet([groupe])

    for nom in ("planches — 1 planche", "p_demo_L_2f-aaa.pdf"):
        arbre.viser(nom)
        assert arbre.basculer() is True
        assert [n.nom for n in arbre.coches] == [nom], nom
        assert arbre.basculer() is True
        assert arbre.coches == (), (
            f"`Espace` doit DECOCHER {nom!r}, pas seulement cocher")
