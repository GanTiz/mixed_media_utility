# -*- coding: utf-8 -*-
"""`EPIC11-ARB-267` -- l'adoption d'une planche etrangere SE DEMANDE.

Le fait que ce banc ferme
-------------------------
Egan, testant l'Epic 11 le 2026-09-07 : « un scan d'un projet etranger est
refuse. Il me semblait qu'on avait regle la question de l'adoption. » Il avait
raison sur les deux moities. L'adoption **etait** reglee -- `EPIC7-ARB-101` le
2026-08-27, et le coeur la porte depuis la 11.4b, avec dix-sept bancs verts
dans `tests/unit/test_adoption_de_planche_etrangere.py`. Mais son unique
interrupteur, `run_scan_detect(adopter=True)`, n'etait pose par **aucune**
surface : ni TUI, ni CLI, ni GUI. Le produit opposait donc le defaut du tri --
`hors-perimetre-projet-etranger`, un rapport sans lot, et une file qui nomme
« le projet a utiliser ». C'est-a-dire ce que l'arbitrage denoncait deja mot
pour mot : « un conseil inapplicable », qui renvoie l'operateur vers un projet
qu'il n'a pas et ne peut pas avoir.

`EPIC11-ARB-267`, tranche par Egan le meme jour, leve la seule question qui
restait : « ce que j'ai decide pour la GUI (fenetre volante) n'a pas a
s'appliquer a la TUI qui peut tout a fait utiliser un modele d'ecran de
confirmation connu avec une issue "adopter" a ajouter. » Il n'existe en effet
AUCUN `ModalScreen` dans ce paquet -- tous ses points de jugement sont des
ecrans empiles --, et `EPIC7-ARB-106` demandait une fenetre volante. Le grief
d'origine visait une case a cocher invisible faute de defilement ; un ecran
plein la corrige aussi bien.

Ce qui est repris d'`EPIC7-ARB-106` et **mesure ici** : une seule question,
meme quand plusieurs projets sont en cause, et **elle les nomme tous** ; un
« oui » **relance la detection tout seul**.

Regle des fabriques, appliquee a ce que le CODE parcourt
---------------------------------------------------------
`planches_etrangeres_de` **boucle** sur `partition.hors_perimetre` et
dedoublonne les projets. La fabrique produit donc **quatre** entrees portant
**trois** projets distinguables, dans un ordre qui n'est PAS l'ordre trie -- un
tri parasite ou son absence se verraient l'un comme l'autre --, avec une cible
en TETE, une au MILIEU et une en QUEUE : la cible au milieu demasque un `find`
fautif, elle ne demasque pas un balayage tronque (`CLAUDE.md`, point 4 des
fabriques). Une quatrieme entree porte un projet ILLISIBLE, en queue, parce que
c'est le seul cas ou le cardinal et la liste des noms divergent.

Ce que ce banc ne mesure pas, dit plutot que tu
------------------------------------------------
Il ne mesure **pas** l'adoption elle-meme -- la substitution d'identite, le
champ `adopted_from_project_id`, le manifeste d'accueil. Tout cela vit au coeur
et y est deja mesure, et le remesurer ici ferait une seconde definition de
l'adoption a cote de la premiere. Ce banc mesure exactement ce que le lot
livre : **que l'interrupteur du coeur devient atteignable a l'ecran, et que les
deux issues menent quelque part.**
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from types import SimpleNamespace

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE / "src") not in sys.path:  # pragma: no cover - amorce du banc
    sys.path.insert(0, str(RACINE / "src"))

import pytest

from mixed_media_utility import scan_sorting
from mixed_media_utility.tui import (atelier_scan_detection as atelier,
                                     atelier_scan_parcours, jetons)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin

PIED = "⏎ entrer   Q quitter"


# ---------------------------------------------------------------------------
# Fabriques -- quatre entrees, trois projets, les cibles aux DEUX bords
# ---------------------------------------------------------------------------

#: Les trois projets etrangers, **dans le desordre**. `aa_` serait premier une
#: fois trie, `zz_` dernier : les poser dans cet ordre-la fait qu'un tri absent
#: et un tri present rendent deux listes differentes.
PROJETS_ETRANGERS = ("zz_dernier_trie", "mm_au_milieu", "aa_premier_trie")


def entree_dehors(rang: int, projet: str | None):
    """Une `EntreeHorsPerimetre` de synthese, portant un localisateur REEL.

    **Le localisateur ne peut pas rester `None`**, et c'est le banc qui l'a
    appris plutot qu'une relecture : l'issue « ne pas adopter » montre le
    rapport, le rapport construit la file « en attente de lecture », et
    `_texte_de_localisateur` y lit `locator.page_index` sans garde. Un
    localisateur absent leve donc un `AttributeError` a l'endroit exact ou ce
    lot fait passer l'operateur.

    C'est la lecon du 2026-09-02 dans l'autre sens : une fixture de synthese
    trop pauvre fabrique une panne que le terrain n'a pas -- le coeur pose
    TOUJOURS un localisateur sur une entree hors perimetre. Les pages portent
    des noms et des index DIFFERENTS : deux entrees indiscernables ne
    demasqueraient aucune permutation.
    """
    return SimpleNamespace(
        read_rank=rang,
        locator=SimpleNamespace(source_path=f"planche_{rang:03d}.tif",
                                page_index=rang),
        motif=scan_sorting.HORS_PERIMETRE_PROJET_ETRANGER,
        projet_a_utiliser=projet)


def partition(projets=PROJETS_ETRANGERS, muette_en_queue: bool = True,
              reliquat=()):
    """Une partition dont le hors-perimetre porte `projets`, un par entree.

    ``muette_en_queue`` ajoute une quatrieme entree **sans** projet lisible, en
    DERNIERE position. C'est le seul regime ou le cardinal des pages et la
    longueur de la liste des noms divergent, et le poser en queue est ce qui
    demasque un balayage tronque -- une entree sautee en fin de liste serait
    invisible si toutes les cibles etaient au milieu.
    """
    dehors = [entree_dehors(rang, projet)
              for rang, projet in enumerate(projets, start=1)]
    if muette_en_queue:
        dehors.append(entree_dehors(len(dehors) + 1, None))
    return SimpleNamespace(reliquat=list(reliquat), hors_perimetre=dehors)


def coque(ascii_seul: bool = False) -> CoqueTui:
    """Deux paliers temoins : sans le menu des ateliers a cote de la racine, un
    retour au menu ne se distingue pas d'un simple depilement."""
    return CoqueTui([PalierTemoin("Projet", PIED),
                     PalierTemoin("Ateliers", PIED)],
                    Contexte(projet="projet_demo", palier="Scan"),
                    ascii_seul=ascii_seul)


class CoeurEspion:
    """Un `run_scan_detect` de banc qui **capte l'appel entier**.

    `*args, **kwargs` a dessein : la mesure porte sur l'ensemble EXACT des
    mots-cles transmis, et un double a signature figee leverait un `TypeError`
    au lieu de rendre l'ensemble a comparer -- il mesurerait alors la signature
    du double, pas celle de l'appel.
    """

    def __init__(self, issues=()) -> None:
        #: Une issue par appel, consommees dans l'ordre : c'est ce qui permet
        #: de faire rendre au coeur une partition ETRANGERE a la premiere passe
        #: et une partition PROPRE a la relance, comme l'adoption reelle.
        self.issues = list(issues)
        self.appels: list[tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs):
        self.appels.append((args, dict(kwargs)))
        if self.issues:
            return self.issues.pop(0)
        return SimpleNamespace(documents=(), partition=None)


def issue_avec(part):
    return SimpleNamespace(documents=(), partition=part)


def parcours_sur(app, tmp_path: Path, coeur) -> "atelier_scan_parcours.ParcoursScan":
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    return atelier_scan_parcours.ParcoursScan(app, projet, detection=coeur)


# ---------------------------------------------------------------------------
# 1. Le modele : ce que la partition rend, et ce qu'elle ne rend pas
# ---------------------------------------------------------------------------

def test_les_projets_etrangers_sont_TOUS_nommes_tries_et_dedoublonnes():
    """`EPIC7-ARB-106` : « une seule question, meme quand plusieurs projets
    sont en cause, et **elle les nomme tous** ».

    Le tri est mesure sur une fabrique posee dans le DESORDRE : sans lui, la
    liste rendue serait celle de la fabrique, et les deux se distinguent.
    """
    vu = atelier.planches_etrangeres_de(partition(muette_en_queue=False))
    assert vu.projets == ("aa_premier_trie", "mm_au_milieu", "zz_dernier_trie")
    assert vu.pages == 3

    # Dedoublonnage : trente planches d'un meme projet font UNE entree de nom
    # et trente pages. Confondre les deux ferait annoncer « 1 projet » pour
    # trente planches.
    repete = atelier.planches_etrangeres_de(
        partition(("aa_meme",) * 30, muette_en_queue=False))
    assert repete.projets == ("aa_meme",)
    assert repete.pages == 30


def test_une_page_sans_projet_lisible_COMPTE_mais_ne_se_NOMME_pas():
    """Le coeur laisse `projet_a_utiliser` a `None` quand le QR ne porte pas
    d'identifiant lisible. La page est pourtant bien dehors, et l'oublier
    ferait annoncer un cardinal plus petit que ce que l'adoption ferait
    entrer -- un chiffre faux presente comme une mesure.

    Et on ne nomme pas un projet qu'on n'a pas lu : la liste l'ignore.
    """
    vu = atelier.planches_etrangeres_de(partition(muette_en_queue=True))
    assert vu.pages == 4, "la page au QR muet a ete perdue du cardinal"
    assert vu.projets == ("aa_premier_trie", "mm_au_milieu", "zz_dernier_trie")

    # Le cas pur : aucune page nommee, et pourtant deux pages dehors.
    aveugle = atelier.planches_etrangeres_de(partition((), muette_en_queue=True))
    assert aveugle.pages == 1 and aveugle.projets == ()


def test_RIEN_a_demander_rend_None_et_jamais_un_cardinal_nul():
    """`None` dit « rien a demander », et c'est ce que l'appelant teste pour
    savoir s'il monte l'ecran. Un objet a zero page ferait monter un point de
    jugement sur une question qui ne se pose pas.
    """
    assert atelier.planches_etrangeres_de(None) is None
    assert atelier.planches_etrangeres_de(partition((), muette_en_queue=False)) is None

    # Un RELIQUAT n'est pas un hors-perimetre : `scan_sorting` leve a l'import
    # si les deux vocabulaires se recouvrent, et la meme disjonction vaut ici.
    reste = SimpleNamespace(read_rank=1, locator=None, motif="reliquat-illisible",
                            projet_a_utiliser=None)
    seul_reliquat = SimpleNamespace(reliquat=[reste], hors_perimetre=[])
    assert atelier.planches_etrangeres_de(seul_reliquat) is None


def test_le_curseur_part_sur_l_issue_qui_N_ECRIT_PAS():
    """`EPIC11-ARB-45` : aucune ecriture atteignable en une seule frappe.

    L'adoption relance la passe, qui ingere : elle porte donc `ecrit=True`, et
    c'est ce qui fait partir le curseur sur l'autre. La marquer `ecrit=False`
    ferait partir le curseur **sur elle**.
    """
    issues = atelier.issues_de_l_adoption()
    assert [(i.cle, i.ecrit) for i in issues] == [
        (atelier.ISSUE_ADOPTER, True), (atelier.ISSUE_LAISSER_DEHORS, False)]

    choix = atelier.choix_de_l_adoption()
    assert choix.issue_sous_le_curseur.cle == atelier.ISSUE_LAISSER_DEHORS

    # **Jamais zero, jamais une** (`EPIC11-ARB-89`), et la sortie NOMME sa
    # destination -- une issue qui ne dit pas ou elle mene est un cul-de-sac
    # deguise.
    assert len(issues) == 2
    assert "rapport" in atelier.LIBELLE_LAISSER_DEHORS.lower()


# ---------------------------------------------------------------------------
# 2. Le cartouche chiffre, dans les DEUX regimes de glyphes
# ---------------------------------------------------------------------------

def test_le_cartouche_CHIFFRE_ce_qui_serait_adopte_et_se_replie_en_ASCII():
    """`EPIC11-ARB-4` : une issue neuve sans chiffre n'en est pas. Sans ces
    deux lignes, l'ecran offrirait d'adopter sans dire combien ni d'ou, et le
    consentement porterait sur rien.

    Le repli est mesure en faisant VARIER `ascii_seul` dans les deux sens, sur
    un cas ou il change quelque chose -- la regle des gardes du 2026-09-06 :
    un banc qui ne joue qu'un seul etat de son drapeau mesure la moitie du
    produit et l'annonce verte.
    """
    vu = atelier.planches_etrangeres_de(partition())
    for ascii_seul in (False, True):
        lignes = atelier.panneau_de_l_adoption(vu).rendu(76, ascii_seul)
        texte = "\n".join(lignes)
        assert "4 pages" in texte, texte
        for projet in PROJETS_ETRANGERS:
            assert projet in texte, (projet, texte)
        assert max(len(ligne) for ligne in lignes) <= 76, lignes
        if ascii_seul:
            assert texte.isascii(), texte


def test_aucun_projet_lisible_rend_le_GLYPHE_NEUTRE_et_jamais_un_vide():
    """`·` dit « pas mesure », le vide ne dit rien. C'est la regle que ce
    paquet tient partout ailleurs, appliquee a la ligne d'origine."""
    aveugle = atelier.PlanchesEtrangeres(projets=(), pages=2)
    rendu = "\n".join(atelier.panneau_de_l_adoption(aveugle).rendu(76, False))
    assert jetons.GLYPHES["neutre"] in rendu, rendu


# ---------------------------------------------------------------------------
# 3. Le cablage : le drapeau traverse, et les deux issues menent quelque part
# ---------------------------------------------------------------------------

def test_le_drapeau_adopter_traverse_VERBATIM_jusqu_au_coeur(banc, tmp_path):
    """Le cablage nu. Mesure a l'**ensemble EXACT** des mots-cles : une
    assertion d'appartenance laisserait passer toute divergence
    supplementaire, et c'est la lecon que la frontiere du lot E a payee.
    """
    coeur = CoeurEspion([issue_avec(None)])
    app = coque()

    async def scenario(pilote):
        parcours = parcours_sur(pilote.app, tmp_path, coeur)
        pilote.app.descendre()
        await pilote.pause()
        parcours.detecter(tmp_path / "source", 1200)
        await pilote.pause()
        return {}

    banc(app, scenario)
    assert len(coeur.appels) == 1, coeur.appels
    _args, kwargs = coeur.appels[0]
    assert set(kwargs) == {"dpi", "ingest_slug", "logger",
                           "rappel_progression", "nouvelle_version",
                           "adopter"}, kwargs
    # **Le defaut est FAUX**, et il le reste : l'adoption est une issue retenue
    # par l'operateur, jamais un regime.
    assert kwargs["adopter"] is False


def test_une_pile_ETRANGERE_ouvre_le_point_de_jugement_au_lieu_du_rapport(banc, tmp_path):
    """Le bloquant produit, mesure de bout en bout : la ou l'operateur voyait
    « Aucun document de detection n'a ete ecrit » et une file qui le renvoie
    vers un projet qu'il n'a pas, il voit maintenant une question."""
    coeur = CoeurEspion([issue_avec(partition())])
    app = coque()
    vu: dict = {}

    async def scenario(pilote):
        parcours = parcours_sur(pilote.app, tmp_path, coeur)
        pilote.app.descendre()
        await pilote.pause()
        parcours.detecter(tmp_path / "source", 1200)
        await pilote.pause()
        vu["nom"] = type(pilote.app.screen).__name__
        vu["lignes"] = list(pilote.app.screen.lignes())
        return vu

    banc(app, scenario)
    assert vu["nom"] == "EcranAdoptionDeLaPlanche", vu["nom"]
    texte = "\n".join(vu["lignes"])
    # La question NOMME TOUS les projets, sur l'ecran REEL -- pas seulement
    # dans le panneau mesure a part.
    for projet in PROJETS_ETRANGERS:
        assert projet in texte, (projet, texte)
    assert atelier.LIBELLE_ADOPTER in texte


def test_le_OUI_relance_la_detection_TOUT_SEUL_avec_le_drapeau_pose(banc, tmp_path):
    """`EPIC7-ARB-106` : « un Oui relance la detection tout seul ».

    C'est ce qui fait de l'issue une ecriture reelle et non une decoration --
    le finding `K3`, paye quatre fois dans cet epic, est exactement l'issue
    navigable qui n'appelle personne.

    La seconde passe rend une partition PROPRE, comme l'adoption reelle : le
    coeur a substitue l'identite, il n'y a plus rien hors perimetre.
    """
    coeur = CoeurEspion([issue_avec(partition()), issue_avec(None)])
    app = coque()
    vu: dict = {}

    async def scenario(pilote):
        parcours = parcours_sur(pilote.app, tmp_path, coeur)
        pilote.app.descendre()
        await pilote.pause()
        parcours.detecter(tmp_path / "source", 1200)
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(atelier.ISSUE_ADOPTER)
        ecran.traiter("enter")
        await pilote.pause()
        vu["nom"] = type(pilote.app.screen).__name__
        return vu

    banc(app, scenario)
    assert len(coeur.appels) == 2, coeur.appels
    assert coeur.appels[0][1]["adopter"] is False
    assert coeur.appels[1][1]["adopter"] is True, coeur.appels[1][1]
    # **La source, le dpi et le slug voyagent tels quels** : la relance rejoue
    # la MEME demande, un drapeau de plus. Les recomposer ferait une seconde
    # construction qui divergerait de la premiere.
    assert coeur.appels[0][0] == coeur.appels[1][0]
    for cle in ("dpi", "ingest_slug"):
        assert coeur.appels[0][1][cle] == coeur.appels[1][1][cle]


def test_le_NON_montre_le_RAPPORT_et_ne_revient_PAS_au_menu(banc, tmp_path):
    """La passe a REUSSI : les lots que la meme pile a produits existent.

    Les perdre pour une question a laquelle on repond « non » serait le refus
    d'aujourd'hui sous un autre nom -- et c'est precisement ce que la sortie du
    CONFLIT fait, elle, a juste titre : la, aucun rapport n'existe.
    """
    coeur = CoeurEspion([issue_avec(partition())])
    app = coque()
    vu: dict = {}

    async def scenario(pilote):
        parcours = parcours_sur(pilote.app, tmp_path, coeur)
        pilote.app.descendre()
        await pilote.pause()
        parcours.detecter(tmp_path / "source", 1200)
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(atelier.ISSUE_LAISSER_DEHORS)
        ecran.traiter("enter")
        await pilote.pause()
        vu["nom"] = type(pilote.app.screen).__name__
        return vu

    banc(app, scenario)
    assert vu["nom"] == "EcranRapportDeDetection", vu["nom"]
    # Le « non » n'appelle PAS le coeur : il ne relance rien.
    assert len(coeur.appels) == 1, coeur.appels


def test_l_ecran_ne_se_remonte_JAMAIS_sur_lui_meme(banc, tmp_path):
    """La borne de la reprise, et elle est EXPLICITE plutot que deduite.

    Le coeur ayant substitue l'identite, la passe relancee ne rend en principe
    plus aucune page hors perimetre -- mais « en principe » n'est pas une
    borne. Ce banc force le cas pathologique : le coeur rend une partition
    ENCORE etrangere apres l'adoption, comme le ferait une adoption partielle.
    L'ecran ne doit pas se remonter, sans quoi l'operateur ne peut plus
    quitter la boucle de points de jugement.
    """
    coeur = CoeurEspion([issue_avec(partition()), issue_avec(partition())])
    app = coque()
    vu: dict = {}

    async def scenario(pilote):
        parcours = parcours_sur(pilote.app, tmp_path, coeur)
        pilote.app.descendre()
        await pilote.pause()
        parcours.detecter(tmp_path / "source", 1200)
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(atelier.ISSUE_ADOPTER)
        ecran.traiter("enter")
        await pilote.pause()
        vu["nom"] = type(pilote.app.screen).__name__
        return vu

    banc(app, scenario)
    assert len(coeur.appels) == 2, "la relance n'a pas eu lieu"
    assert vu["nom"] == "EcranRapportDeDetection", (
        "l'ecran d'adoption s'est remonte sur lui-meme : la boucle est ouverte")


def test_la_question_ne_se_repose_PAS_a_chaque_retour_du_rapport(banc, tmp_path):
    """« Une seule question » (`EPIC7-ARB-106`), et c'est ce que l'emplacement
    du branchement achete sans compteur ni drapeau : `conclure` joue UNE fois
    par passe, la ou `montrer_le_rapport` se rejoue a chaque retour de `E3-4b`.

    Frontiere NEGATIVE : `montrer_le_rapport` appele seul ne doit JAMAIS monter
    l'ecran d'adoption, meme quand la partition en porte encore.
    """
    coeur = CoeurEspion([issue_avec(partition())])
    app = coque()
    vu: dict = {}

    async def scenario(pilote):
        parcours = parcours_sur(pilote.app, tmp_path, coeur)
        pilote.app.descendre()
        await pilote.pause()
        parcours.detecter(tmp_path / "source", 1200)
        await pilote.pause()
        ecran = pilote.app.screen
        ecran.choix.viser(atelier.ISSUE_LAISSER_DEHORS)
        ecran.traiter("enter")
        await pilote.pause()
        # Le retour de `E3-4b` : le rapport se RECALCULE.
        parcours.montrer_le_rapport()
        await pilote.pause()
        vu["nom"] = type(pilote.app.screen).__name__
        return vu

    banc(app, scenario)
    assert vu["nom"] == "EcranRapportDeDetection", (
        "la question s'est reposee a un retour du rapport")


def test_la_grille_80x24_tient_sur_l_ecran_d_adoption(banc, tmp_path):
    """Le plancher du depot, dans les DEUX regimes de glyphes. Le repli ASCII
    contraint la largeur, et une ligne qui tient en Unicode peut deborder en
    ASCII -- c'est le finding `E10`, et il se paie a chaque ecran neuf.
    """
    for ascii_seul in (False, True):
        coeur = CoeurEspion([issue_avec(partition())])
        app = coque(ascii_seul=ascii_seul)
        vu: dict = {}

        async def scenario(pilote, _vu=vu):
            parcours = parcours_sur(pilote.app, tmp_path, coeur)
            pilote.app.descendre()
            await pilote.pause()
            parcours.detecter(tmp_path / "source", 1200)
            await pilote.pause()
            _vu["lignes"] = list(pilote.app.screen.lignes())
            return _vu

        banc(app, scenario)
        lignes = vu["lignes"]
        assert lignes, "l'ecran n'a rendu aucune ligne"
        assert max(len(ligne) for ligne in lignes) <= 76, (ascii_seul, lignes)
        assert len(lignes) <= 17, (ascii_seul, len(lignes))

        # **La purete ASCII n'est mesuree que sur ce que CE lot controle** --
        # le cartouche et la phrase --, et pas sur les libelles d'issue. Motif
        # mesure le 2026-09-07 et **verse en dette**, pas tu :
        # `ChoixExclusif.rendu` (`panneau.py`) replie le GLYPHE du curseur par
        # `jetons.glyphes` et laisse passer `issue.libelle` BRUT, la ou
        # `LigneChiffree.rendu` replie ses deux moities quinze lignes plus
        # haut. Le produit porte 98 libelles accentues ; ils sortent tous
        # accentues en `--ascii`. Le correctif fait deux lignes et rougit
        # QUATRE bancs d'autres stories -- l'elargir ici serait elargir le
        # scope de ce lot pendant la fenetre de packaging, ce que `CLAUDE.md`
        # interdit nommement. Entree « Les libelles d'issue ne se replient pas
        # en ASCII » de `deferred-work.md`.
        if ascii_seul:
            corps = [l for l in lignes
                     if atelier.LIBELLE_ADOPTER not in l
                     and atelier.LIBELLE_LAISSER_DEHORS not in l]
            assert all(ligne.isascii() for ligne in corps), corps


# ---------------------------------------------------------------------------
# 4. La frontiere NEGATIVE : l'adoption n'est pas un REGIME
# ---------------------------------------------------------------------------

def test_AUCUN_chemin_de_la_TUI_ne_pose_adopter_a_VRAI_par_defaut():
    """Le volet symetrique, et c'est le vrai livrable de cette famille : sans
    lui, « l'adoption est atteignable » serait vrai d'un produit qui adopte
    TOUT, ce qui est l'inverse exact de l'arbitrage.

    Mesure sur le defaut de la dataclasse et sur la construction que le
    parcours fait : les deux doivent rendre faux. La seule ecriture de `True`
    du paquet est le `replace` de `ParcoursScan.adopter`, c'est-a-dire derriere
    une issue retenue.
    """
    assert atelier.DemandeDeDetection(
        dossier_projet=Path("p"), source=Path("s"), dpi=1200).adopter is False

    # **Mesuree sur l'AST, jamais sur le texte** : les deux modules PARLENT
    # d'`adopter=True` dans leurs docstrings, pour dire ou il se pose et
    # pourquoi il ne se pose pas ailleurs. Un grep de chaine y trouverait la
    # prose et rendrait le test faux dans les deux sens -- c'est la lecon que
    # la frontiere negative de `normaliser` a deja payee dans ce depot.
    poses = []
    for module in (atelier_scan_parcours, atelier):
        arbre = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            for mot in noeud.keywords:
                if (mot.arg == "adopter"
                        and isinstance(mot.value, ast.Constant)
                        and mot.value.value is True):
                    poses.append(f"{Path(module.__file__).name}:{noeud.lineno}")

    assert len(poses) == 1, (
        "l'adoption doit se poser a UN seul endroit -- derriere l'issue "
        f"retenue de `ParcoursScan.adopter`. Trouvee ici : {poses}")
    assert poses[0].startswith("atelier_scan_parcours.py"), poses
