# -*- coding: utf-8 -*-
"""`EPIC11-ARB-264` cote ECRAN : `Suppr` sur une ligne de GROUPE.

Constat de terrain d'Egan du 2026-09-06 : « planches (l'ensemble) et masters
(l'ensemble d'un lot) ne sont pas selectionnables ». Ce banc mesure ce qui
remplace le refus : la case revient sur les lignes de groupe, `Espace` la
coche, et `Suppr` deplie la ligne en N cibles que `remove_project_group` porte.

**Aucun ecran neuf** (`EPIC11-ARB-144`) : le cartouche `E6-2` accueille un
total et une liste de dossiers sans qu'un trait change, ce qui est exactement
ce qu'un groupe produit. Le detail ligne par ligne voyage sur le plan
(`apercu_du_groupe`) sans etre dessine -- il attend sa maquette, et ce banc
mesure qu'il est bien la plutot que perdu.

**Regle des fabriques** : le groupe porte TROIS membres distinguables, la panne
est jouee en tete, au milieu et en queue, et le drapeau `groupe` varie dans les
deux sens (un groupe / un objet).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.project_inventory import (NATURE_MASTER,
                                                   NATURE_PLANCHE,
                                                   ObjetInventorie)
from mixed_media_utility.project_maintenance import (LigneDeGroupe,
                                                     ProjectMaintenanceError,
                                                     RapportDeGroupe,
                                                     RapportSuppression)
from mixed_media_utility.tui import projet_inventaire as pi
from mixed_media_utility.tui import projet_suppression as ps
from mixed_media_utility.tui.coque import (Contexte, CoqueTui, EcranPasEncore,
                                           PalierTemoin)
from mixed_media_utility.tui.execution import EcranRefus, Issue


# ---------------------------------------------------------------------------
# Fabriques : un groupe de TROIS membres distinguables.
# ---------------------------------------------------------------------------


def _objet(nature: str, nom: str, rang: int = 1) -> pi.NoeudAffiche:
    return pi._objet_affiche(
        ObjetInventorie(nature=nature, nom=nom, chemin=f"outputs/{nom}",
                        etat=pi.ETAT_PRESENT, rang=rang), 3)


def _groupe(nature: str, nom: str, membres) -> pi.NoeudAffiche:
    """Une ligne de GROUPE, batie comme l'arbre la bat : sans objet de coeur."""
    return pi.NoeudAffiche(
        nature=nature, nom=nom, etat=pi.ETAT_PRESENT, profondeur=2,
        poids=sum(m.poids for m in membres),
        fichiers=sum(m.fichiers for m in membres),
        cardinal="", enfants=list(membres), groupe=True, deplie=True)


def _groupe_de_trois_planches() -> pi.NoeudAffiche:
    """Trois planches DISTINGUABLES, de rangs differents et de noms differents.

    Un remplissage uniforme rendrait invisible une permutation entre la cible
    et son libelle -- la regle des fabriques, point 1.
    """
    membres = [
        _objet(NATURE_PLANCHE, "p_demo_L_2f-aaa.pdf", rang=1),
        _objet(NATURE_PLANCHE, "p_demo_L_2f-bbb_v2.pdf", rang=2),
        _objet(NATURE_PLANCHE, "p_demo_L_2f-ccc_v3.pdf", rang=3),
    ]
    return _groupe(NATURE_PLANCHE, "planches — 3 planches", membres)


def _rapport(cible: str, fichiers: tuple[str, ...], dry_run: bool,
             restes: tuple[str, ...] = ()) -> RapportSuppression:
    return RapportSuppression(
        cible=cible, fichiers_a_supprimer=fichiers, dry_run=dry_run,
        supprime=not dry_run and not restes,
        fichiers_non_supprimes=restes)


class _GroupeDouble:
    """Un double de `remove_project_group` : il refuse les libelles nommes."""

    def __init__(self, refuse: set[str] | None = None):
        self.refuse = refuse or set()
        self.appels: list[tuple] = []

    def __call__(self, projet, cibles, *, dry_run=True):
        self.appels.append((Path(projet), tuple(cibles), dry_run))
        lignes = []
        for rang, (libelle, cible) in enumerate(cibles, start=1):
            if not dry_run and libelle in self.refuse:
                lignes.append(LigneDeGroupe(
                    cible=dict(cible), libelle=libelle,
                    refus=f"Refus propre a {libelle}."))
                continue
            lignes.append(LigneDeGroupe(
                cible=dict(cible), libelle=libelle,
                # Un cardinal DISTINCT par ligne : une concatenation fautive
                # se voit, un remplissage uniforme la cacherait.
                rapport=_rapport(libelle,
                                 tuple(f"outputs/{libelle}#{n}"
                                       for n in range(rang)),
                                 dry_run)))
        return RapportDeGroupe(lignes=tuple(lignes), dry_run=dry_run)


# ---------------------------------------------------------------------------
# La traduction : une ligne de groupe -> N cibles du coeur.
# ---------------------------------------------------------------------------


def test_les_membres_DIRECTS_deviennent_N_cibles_dans_l_ordre_de_l_arbre():
    """L'ordre n'est pas trie : celui de l'arbre porte celui du manifeste."""
    groupe = _groupe_de_trois_planches()
    cibles, non_visables = ps.cibles_du_groupe(groupe, "L")
    assert non_visables == ()
    assert [libelle for libelle, _ in cibles] == [
        "p_demo_L_2f-aaa.pdf", "p_demo_L_2f-bbb_v2.pdf",
        "p_demo_L_2f-ccc_v3.pdf"]
    assert [c for _, c in cibles] == [
        {"lot_id": "L", "planche": True},
        {"lot_id": "L", "planche": True, "version": 2},
        {"lot_id": "L", "planche": True, "version": 3},
    ]


def test_un_membre_que_RIEN_ne_sait_viser_est_NOMME_et_pas_tu():
    """`EPIC11-ARB-258` : le taire ferait supprimer « le groupe » en en
    laissant une partie, sans un mot.

    Le membre non visable est place au MILIEU : en tete, un balayage qui
    s'arreterait a la premiere anomalie passerait ; en queue, un balayage
    tronque le manquerait.
    """
    membres = [
        _objet(NATURE_MASTER, "L_mmu_prores_422.mov"),
        _objet(NATURE_MASTER, "renomme-a-la-main.mov"),
        _objet(NATURE_MASTER, "L_mmu_dnxhr_hq.mov"),
    ]
    groupe = _groupe(NATURE_MASTER, "masters — 3 masters", membres)
    cibles, non_visables = ps.cibles_du_groupe(groupe, "L")
    assert non_visables == ("renomme-a-la-main.mov",)
    assert [libelle for libelle, _ in cibles] == [
        "L_mmu_prores_422.mov", "L_mmu_dnxhr_hq.mov"]


def test_seuls_les_membres_DIRECTS_sont_vises_jamais_les_petits_fils():
    """Descendre plus bas viserait deux fois les memes fichiers : le coeur
    supprime deja le sous-arbre d'un scan."""
    petit_fils = _objet(NATURE_PLANCHE, "p_petit_fils.pdf")
    membre = _objet(NATURE_PLANCHE, "p_membre.pdf")
    membre.enfants.append(petit_fils)
    groupe = _groupe(NATURE_PLANCHE, "planches — 1 planche", [membre])
    cibles, _ = ps.cibles_du_groupe(groupe, "L")
    assert [libelle for libelle, _ in cibles] == ["p_membre.pdf"]


def test_le_LIBELLE_du_groupe_reprend_le_nom_de_la_LIGNE():
    """Le recomposer d'une table de natures ferait lire au cartouche un mot
    different de celui de l'arbre -- le finding `F2` de la revue 11.14."""
    groupe = _groupe_de_trois_planches()
    assert ps.libelle_du_groupe(groupe, 3) == (
        "les 3 éléments de « planches — 3 planches »")
    assert ps.libelle_du_groupe(groupe, 1) == (
        "les 1 élément de « planches — 3 planches »")


# ---------------------------------------------------------------------------
# L'agregat : ce que les ecrans deja dessines lisent.
# ---------------------------------------------------------------------------


def _apercu(double, cibles):
    return double(Path("."), cibles, dry_run=True)


def test_l_agregat_CONCATENE_les_lignes_dans_leur_ordre():
    double = _GroupeDouble()
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    agrege = ps.rapport_agrege_du_groupe("les 3", _apercu(double, cibles))
    assert agrege.fichiers_a_supprimer == (
        "outputs/p_demo_L_2f-aaa.pdf#0",
        "outputs/p_demo_L_2f-bbb_v2.pdf#0",
        "outputs/p_demo_L_2f-bbb_v2.pdf#1",
        "outputs/p_demo_L_2f-ccc_v3.pdf#0",
        "outputs/p_demo_L_2f-ccc_v3.pdf#1",
        "outputs/p_demo_L_2f-ccc_v3.pdf#2",
    )
    assert agrege.dry_run is True
    assert agrege.cible == "les 3"


def test_l_agregat_ne_porte_AUCUN_rang_et_n_ouvre_donc_aucune_liberation():
    """Un groupe n'est pas un objet versionne.

    En rendre un ferait apparaitre l'issue « Supprimer et libérer les rangs »
    sur un ENSEMBLE, c'est-a-dire une liberation en bloc que personne n'a
    demandee -- l'inverse du point 3 d'`EPIC11-ARB-92`. Le volet qui compte est
    l'issue, pas le champ : c'est elle que l'operateur verrait.
    """
    double = _GroupeDouble()
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    plan = ps.preparer_la_suppression_du_groupe(
        Path("."), cibles, "les 3", retirer_le_groupe=double)
    assert plan.rapport.rangs_liberables == ()
    assert plan.rapport.objet_en_queue is False
    assert plan.rapport.rang_independant is False
    cles = [issue.cle for issue in ps.issues_de_la_suppression(plan).issues]
    assert ps.CLE_SUPPRIMER_ET_LIBERER not in cles, cles
    assert ps.CLE_SUPPRIMER in cles and ps.CLE_ANNULER in cles


@pytest.mark.parametrize("fautif", [
    "p_demo_L_2f-aaa.pdf",       # en TETE
    "p_demo_L_2f-bbb_v2.pdf",    # au MILIEU
    "p_demo_L_2f-ccc_v3.pdf",    # en QUEUE
])
def test_une_ligne_REFUSEE_laisse_ses_fichiers_dans_les_RESTES(fautif):
    """A l'execution, un refus ne rend aucun chemin : ils se relisent de
    l'APERCU.

    Sans cela, un groupe a moitie parti s'annoncerait REUSSI -- l'ecran `E6-3b`
    au lieu d'`E6-3` --, et l'operateur ne saurait pas quoi relancer. Les trois
    positions sont jouees : un balayage tronque ne se demasque pas autrement.
    """
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    apercu = _GroupeDouble()(Path("."), cibles, dry_run=True)
    reel = _GroupeDouble(refuse={fautif})(Path("."), cibles, dry_run=False)
    agrege = ps.rapport_agrege_du_groupe("les 3", reel, apercu)
    assert agrege.supprime is False
    attendus = tuple(
        c for ligne in apercu.lignes if ligne.libelle == fautif
        for c in ligne.rapport.fichiers_a_supprimer)
    assert agrege.fichiers_non_supprimes == attendus
    assert fautif not in [
        chemin.split("#")[0].removeprefix("outputs/")
        for chemin in agrege.fichiers_a_supprimer]


def test_un_groupe_ENTIEREMENT_parti_est_annonce_SUPPRIME():
    """Le volet symetrique : sans lui, un `supprime=False` cable en dur
    passerait le test ci-dessus."""
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    apercu = _GroupeDouble()(Path("."), cibles, dry_run=True)
    reel = _GroupeDouble()(Path("."), cibles, dry_run=False)
    agrege = ps.rapport_agrege_du_groupe("les 3", reel, apercu)
    assert agrege.supprime is True
    assert agrege.fichiers_non_supprimes == ()


def test_le_DETAIL_ligne_par_ligne_survit_sur_le_plan():
    """`EPIC11-ARB-264` veut « pourquoi pour chacun ». L'agregat dit un total ;
    le detail doit rester atteignable, sinon il est perdu avant meme d'avoir un
    ecran ou l'afficher."""
    double = _GroupeDouble()
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    plan = ps.preparer_la_suppression_du_groupe(
        Path("."), cibles, "les 3", retirer_le_groupe=double)
    assert plan.est_un_groupe is True
    assert plan.apercu_du_groupe is not None
    assert [l.libelle for l in plan.apercu_du_groupe.lignes] == [
        libelle for libelle, _ in cibles]


def test_un_plan_ORDINAIRE_n_est_PAS_un_groupe():
    """L'autre sens du drapeau : sans ce volet, un `est_un_groupe` toujours
    vrai passerait tout ce qui precede et ferait passer chaque suppression
    d'objet par le chemin de groupe."""
    plan = ps.PlanDeSuppression(
        projet=Path("."), cible={"lot_id": "L"}, libelle="tout le lot L",
        rapport=_rapport("L", (), True))
    assert plan.est_un_groupe is False
    assert plan.apercu_du_groupe is None


# ---------------------------------------------------------------------------
# L'execution.
# ---------------------------------------------------------------------------


def test_l_execution_passe_par_remove_project_GROUP_et_pas_par_l_element():
    double = _GroupeDouble()
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    plan = ps.preparer_la_suppression_du_groupe(
        Path("/projet"), cibles, "les 3", retirer_le_groupe=double)
    appels_element = []
    rapport = ps.executer_la_suppression(
        plan, Issue(ps.CLE_SUPPRIMER, "peu importe", ecrit=True),
        retirer_du_projet=lambda *a, **k: appels_element.append(k),
        retirer_le_groupe=double)
    assert appels_element == [], "le coeur mono-cible ne doit pas etre appele"
    assert double.appels[-1][2] is False, "l'execution n'est pas un dry-run"
    assert rapport is not None and rapport.dry_run is False


def test_l_issue_qui_N_ECRIT_PAS_n_appelle_RIEN_sur_un_groupe():
    """`Annuler` ne touche pas le coeur du tout -- pas meme un dry-run."""
    double = _GroupeDouble()
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    plan = ps.preparer_la_suppression_du_groupe(
        Path("/projet"), cibles, "les 3", retirer_le_groupe=double)
    avant = len(double.appels)
    rendu = ps.executer_la_suppression(
        plan, Issue(ps.CLE_ANNULER, ps.MENTION_RIEN_TOUCHE),
        retirer_le_groupe=double)
    assert rendu is None
    assert len(double.appels) == avant


def test_les_mots_cles_d_un_plan_de_GROUPE_LEVENT_au_lieu_de_mentir():
    """Frontiere NEGATIVE. `plan.cible` est vide sur un groupe : l'etaler
    produirait `remove_project_element(projet, dry_run=False)`, que le coeur
    refuse -- mais sous un message qui parle de `lot_id`, pas de groupe."""
    double = _GroupeDouble()
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    plan = ps.preparer_la_suppression_du_groupe(
        Path("/projet"), cibles, "les 3", retirer_le_groupe=double)
    with pytest.raises(ProjectMaintenanceError) as erreur:
        ps.mots_cles_de_l_issue(
            plan, Issue(ps.CLE_SUPPRIMER, "peu importe", ecrit=True))
    assert "remove_project_group" in str(erreur.value)


# ---------------------------------------------------------------------------
# `Suppr` depuis l'ecran, de bout en bout.
# ---------------------------------------------------------------------------


def _app(ecran) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"), ecran],
                    contexte=Contexte(projet="projet_demo"))


def _capture(app):
    app.descendus = []
    return app.descendus.append


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def test_Suppr_sur_un_GROUPE_monte_la_CONFIRMATION_et_pas_un_refus(
        tmp_path, banc):
    """Ce que `EPIC11-ARB-264` remplace : l'ecran disait
    `MOTIF_DU_GROUPE_NON_SUPPRIMABLE` et rendait la main."""
    double = _GroupeDouble()
    groupe = _groupe_de_trois_planches()
    temoin = pi.EcranInventaireDuProjet(pi.ArbreDuProjet([groupe]))

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        rendu = ps.ouvrir_la_suppression(
            temoin, groupe, projet=tmp_path, lot_id="L",
            retirer_le_groupe=double)
        return rendu, pilote.app.descendus

    rendu, descendus = _monte(_app(temoin), scenario, banc)
    assert rendu is True
    assert isinstance(descendus[-1], ps.EcranSuppressionConfirmation)
    assert not any(isinstance(e, EcranPasEncore) for e in descendus)
    plan = descendus[-1].plan
    assert plan.est_un_groupe is True
    assert len(plan.cibles_du_groupe) == 3
    assert double.appels[0][2] is True, "l'ouverture est un APERCU"


def test_un_GROUPE_dont_AUCUN_membre_n_est_visable_monte_un_REFUS_qui_les_NOMME(
        tmp_path, banc):
    """Jamais un blocage sec (`EPIC11-ARB-89`) : le refus dit quoi cocher a la
    place, membre par membre."""
    membres = [_objet(NATURE_MASTER, "renomme-a.mov"),
               _objet(NATURE_MASTER, "renomme-b.mov")]
    groupe = _groupe(NATURE_MASTER, "masters — 2 masters", membres)
    temoin = pi.EcranInventaireDuProjet(pi.ArbreDuProjet([groupe]))

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        rendu = ps.ouvrir_la_suppression(
            temoin, groupe, projet=tmp_path, lot_id="L")
        return rendu, pilote.app.descendus

    rendu, descendus = _monte(_app(temoin), scenario, banc)
    assert rendu is True
    ecran = descendus[-1]
    assert isinstance(ecran, EcranRefus), type(ecran).__name__
    # `message` plutot que `lignes()` : le rendu demande une application
    # active, et ce banc mesure le CONTENU du refus, pas son dessin.
    assert ecran.code == ps.CODE_GROUPE_SANS_CIBLE
    assert "renomme-a.mov" in ecran.message
    assert "renomme-b.mov" in ecran.message


def test_le_refus_du_COEUR_sur_un_groupe_monte_le_meme_ecran_de_REFUS(
        tmp_path, banc):
    """Le message du coeur passe VERBATIM : c'est lui qui sait pourquoi."""
    groupe = _groupe_de_trois_planches()
    temoin = pi.EcranInventaireDuProjet(pi.ArbreDuProjet([groupe]))

    def _refuse(*_a, **_k):
        raise ProjectMaintenanceError("Le coeur refuse, et voici pourquoi.")

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        ps.ouvrir_la_suppression(temoin, groupe, projet=tmp_path, lot_id="L",
                                 retirer_le_groupe=_refuse)
        return pilote.app.descendus

    ecran = _monte(_app(temoin), scenario, banc)[-1]
    assert isinstance(ecran, EcranRefus), type(ecran).__name__
    assert ecran.message == "Le coeur refuse, et voici pourquoi."


def test_Suppr_sur_un_OBJET_ne_passe_PAS_par_le_chemin_du_groupe(
        tmp_path, banc):
    """L'autre sens du drapeau `groupe`. Sans ce volet, un chemin de groupe
    pris pour tout le monde passerait les tests ci-dessus et casserait la
    suppression d'un objet."""
    double = _GroupeDouble()
    objet = _objet(NATURE_PLANCHE, "p_demo_L_2f-aaa.pdf")
    temoin = pi.EcranInventaireDuProjet(pi.ArbreDuProjet([objet]))
    appels = []

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        ps.ouvrir_la_suppression(
            temoin, objet, projet=tmp_path, lot_id="L",
            retirer_du_projet=lambda *a, **k: (
                appels.append(k) or _rapport("L", (), True)),
            retirer_le_groupe=double)
        return pilote.app.descendus

    _monte(_app(temoin), scenario, banc)
    assert double.appels == [], "le chemin de groupe ne doit pas etre pris"
    assert appels and appels[0].get("planche") is True


# ---------------------------------------------------------------------------
# La maquette que ce banc citait sans la LIRE
# ---------------------------------------------------------------------------
#
# **Le defaut, mesure le 2026-09-07 par la course `cloture0907b`.** L'en-tete
# de ce banc annonce que `E6-2` accueille la confirmation d'un groupe, et
# `test_l_issue_qui_N_ECRIT_PAS_n_appelle_RIEN_sur_un_groupe` fabriquait son
# issue `Annuler` avec la mention « rien n'est touché » RECOPIEE a la main --
# alors que `projet_suppression` porte deja `MENTION_RIEN_TOUCHE`, et que ce
# banc importe ce module. Deux ecritures d'une meme valeur, dont une seule
# atteint l'ecran : la maquette pouvait changer sans que rien ne rougisse.
#
# **Et la frontiere a trouve plus que la recopie.** Le litteral est parti au
# profit de la constante, ce qui ferme la recopie ; mais la constante, elle,
# n'etait confrontee a `E6-2` PAR AUCUN banc du depot -- ni ici, ni dans
# `test_suppression_depuis_la_tui.py`, qui lit pourtant les quatre dessins de
# la famille. La valeur que l'ecran rend n'etait donc mesuree nulle part contre
# le dessin qui la commande. C'est ce que la section ci-dessous ferme.
#
# **Ce que ce geste NE ferme pas, dit plutot que tu, et c'est mesure.** En
# portant le chemin des dessins dans un litteral de code, ce banc devient un
# LECTEUR au sens de la frontiere, donc exempte en bloc de son balayage. Le
# temoin de morsure de cette frontiere -- rendre un lecteur aveugle et mesurer
# qu'il se denonce -- ne dit rien de celui-ci : aveugle, il ne denonce plus
# RIEN, puisqu'il ne reste aucun litteral dessine a denoncer (mesure le
# 2026-09-07 : `recopies_d_un_banc(aveugle(source))` rend l'ensemble vide, la
# valeur passant desormais par `ps.MENTION_RIEN_TOUCHE` et non par une chaine).
# C'est l'etat voulu, pas un contournement -- mais il a un prix : une recopie
# AJOUTEE ici demain ne fera plus rougir la frontiere. La confrontation se
# fait alors dans cette section, a la main, comme partout dans le dossier.

#: Le dossier des dessins, a sa source. Le meme chemin que celui de
#: `test_suppression_depuis_la_tui.py`, pour la meme raison : un dessin se lit,
#: il ne se recopie pas.
MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire, notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


#: Les QUATRE dessins de la famille de la suppression, dont les deux qui
#: portent la mention sont en TETE et au MILIEU, et les deux qui ne la portent
#: pas au MILIEU et en QUEUE. C'est le point 4 de la regle des fabriques : une
#: cible a chaque bord, sans quoi un balayage tronque resterait vert.
DESSINS_DE_LA_SUPPRESSION = (
    ("E6-2", "E6-2-projet-suppression-confirmation.txt", True),
    ("E6-2b", "E6-2b-projet-suppression-dernier-lot.txt", True),
    ("E6-2c", "E6-2c-projet-suppression-execution.txt", False),
    ("E6-3b", "E6-3b-projet-suppression-reussie.txt", False),
)


@pytest.mark.parametrize("code,fichier,dessinee", DESSINS_DE_LA_SUPPRESSION,
                         ids=[c for c, _, _ in DESSINS_DE_LA_SUPPRESSION])
def test_la_MENTION_du_renoncement_est_dessinee_par_les_ecrans_qui_l_OFFRENT(
        code, fichier, dessinee):
    """`MENTION_RIEN_TOUCHE`, confrontee au dessin lu a sa source.

    **Les deux sens dans la meme mesure, et c'est ce qui la rend utile.** Les
    deux ecrans de CONFIRMATION offrent `Annuler`, donc ils dessinent la
    mention ; les deux ecrans d'APRES -- l'execution en cours et la reussite --
    ne l'offrent plus, parce qu'il n'y a plus rien a annuler. Une mesure qui ne
    porterait que sur la presence serait tout aussi verte sur quatre copies du
    meme dessin, et elle laisserait passer une mention affichee trop tard,
    c'est-a-dire un renoncement propose sur une destruction deja faite.

    La constante est prise de `projet_suppression`, jamais reecrite ici : c'est
    la valeur que l'ecran rend, et c'est elle -- pas une jumelle -- qui doit
    etre celle du dessin.
    """
    dessin = dessin_de_la_maquette(fichier)
    assert (ps.MENTION_RIEN_TOUCHE in dessin) is dessinee, (
        f"{code} : la mention {ps.MENTION_RIEN_TOUCHE!r} est "
        f"{'absente' if dessinee else 'presente'} du dessin, contre ce que "
        "l'ecran rend.")


def test_les_deux_ecrans_qui_dessinent_la_mention_dessinent_AUSSI_Annuler():
    """Volet symetrique : la mention accompagne une issue, elle n'erre pas.

    Sans lui, la mesure ci-dessus resterait verte sur un dessin qui porterait
    la phrase en prose de bas de page, sans aucune issue a laquelle
    l'accrocher -- et la ligne d'issue est justement ce dont la mention est la
    colonne de droite.
    """
    porteurs = [f for _, f, dessinee in DESSINS_DE_LA_SUPPRESSION if dessinee]
    assert len(porteurs) == 2, porteurs
    for fichier in porteurs:
        dessin = dessin_de_la_maquette(fichier)
        rang = dessin.find(ps.MENTION_RIEN_TOUCHE)
        assert "Annuler" in dessin[:rang], fichier


# ---------------------------------------------------------------------------
# Ce que la campagne de mutation de la couche 1 a trouve (2026-09-07).
#
# Le point commun des cinq mutants ci-dessous : la fabrique `_GroupeDouble` ne
# refuse QUE `dry_run=False` (`if not dry_run and libelle in self.refuse`), si
# bien qu'aucun banc ne jouait un apercu dont une ligne REFUSE, ni un groupe
# dont les membres ne sont pas tous visables. C'est la regle des drapeaux
# appliquee a `dry_run` et au caractere visable d'un membre : un banc qui ne
# joue qu'un sens mesure la moitie du produit et l'annonce verte.
# ---------------------------------------------------------------------------


class _GroupeQuiRefuseAUSSI_EN_APERCU(_GroupeDouble):
    """Le double, mais le refus tombe des l'APERCU.

    C'est le regime reel d'un membre que le coeur ne resout pas : un master
    greffe en orphelin dans le groupe de son lot ancre est visable au sens de
    `cible_du_noeud` (son nom nomme un profil), et le coeur repond pourtant
    « ce lot ne declare aucun master a ce profil » -- en apercu comme a
    l'ecriture.
    """

    def __call__(self, projet, cibles, *, dry_run=True):
        self.appels.append((Path(projet), tuple(cibles), dry_run))
        lignes = []
        for rang, (libelle, cible) in enumerate(cibles, start=1):
            if libelle in self.refuse:
                lignes.append(LigneDeGroupe(
                    cible=dict(cible), libelle=libelle,
                    refus=f"Refus propre a {libelle}."))
                continue
            lignes.append(LigneDeGroupe(
                cible=dict(cible), libelle=libelle,
                rapport=_rapport(libelle,
                                 tuple(f"outputs/{libelle}#{n}"
                                       for n in range(rang)),
                                 dry_run)))
        return RapportDeGroupe(lignes=tuple(lignes), dry_run=dry_run)


@pytest.mark.parametrize("fautif", [
    "p_demo_L_2f-aaa.pdf",       # en TETE
    "p_demo_L_2f-bbb_v2.pdf",    # au MILIEU
    "p_demo_L_2f-ccc_v3.pdf",    # en QUEUE
])
def test_un_groupe_dont_une_ligne_a_REFUSE_n_est_JAMAIS_annonce_supprime(
        fautif):
    """Mutant `M40`, survivant : retirer `and not groupe.refusees` de
    `supprime=` passait les 19 tests du banc.

    Le regime que les bancs ne jouaient pas : une ligne refusee **des
    l'apercu**. Elle n'a alors aucun rapport d'apercu, donc rien n'entre dans
    les restes, donc `not restes` reste vrai -- et sans le troisieme terme
    l'agregat annonce `supprime=True` sur un groupe dont un membre n'est
    jamais parti. L'ecran de reussite (`E6-3b`) au lieu du compte rendu, sur
    une destruction PARTIELLE : exactement ce qu'`EPIC11-ARB-264` existe pour
    empecher (« relancer en sachant ce qui reste »).
    """
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    double = _GroupeQuiRefuseAUSSI_EN_APERCU(refuse={fautif})
    apercu = double(Path("."), cibles, dry_run=True)
    reel = double(Path("."), cibles, dry_run=False)
    assert [l.libelle for l in apercu.refusees] == [fautif]
    agrege = ps.rapport_agrege_du_groupe("les 3", reel, apercu)
    assert agrege.supprime is False, (
        "un groupe dont une ligne a refuse des l'apercu ne laisse AUCUN reste "
        "a compter : seul le terme `not groupe.refusees` le rattrape")
    assert agrege.fichiers_non_supprimes == ()


def test_un_groupe_dont_les_FICHIERS_resistent_n_est_pas_annonce_supprime():
    """Mutant `M41`, survivant : retirer `and not restes` de `supprime=`
    passait les 19 tests.

    Le pendant de `LigneDeGroupe.passee`, qui mesure deja ce regime ligne par
    ligne -- mais l'AGREGAT, qui est ce que l'ecran lit, ne le mesurait nulle
    part. Un fichier verrouille laisse alors le groupe annonce reussi pendant
    qu'il occupe toujours le disque.
    """
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    lignes = tuple(
        LigneDeGroupe(cible=dict(cible), libelle=libelle,
                      rapport=_rapport(libelle, (f"outputs/{libelle}",),
                                       False,
                                       restes=((f"outputs/{libelle}",)
                                               if rang == 2 else ())))
        for rang, (libelle, cible) in enumerate(cibles, start=1))
    reel = RapportDeGroupe(lignes=lignes, dry_run=False)
    assert reel.refusees == ()
    agrege = ps.rapport_agrege_du_groupe("les 3", reel)
    assert agrege.supprime is False
    assert agrege.fichiers_non_supprimes == (
        "outputs/p_demo_L_2f-bbb_v2.pdf",)


def test_l_execution_RELIT_l_apercu_du_plan_pour_nommer_ce_qui_reste():
    """Mutant `M47`, survivant : `rapport_agrege_du_groupe(..., None)` a
    l'execution passait les 19 tests.

    `test_une_ligne_REFUSEE_laisse_ses_fichiers_dans_les_RESTES` mesure la
    fonction ; personne ne mesurait le CABLAGE qui lui passe
    `plan.apercu_du_groupe`. Sans ce troisieme argument, un refus survenu a
    l'ecriture ne rend aucun chemin et le groupe s'annonce sans reste --
    l'operateur relance sans savoir ce qui reste.
    """
    fautif = "p_demo_L_2f-ccc_v3.pdf"
    cibles = ps.cibles_du_groupe(_groupe_de_trois_planches(), "L")[0]
    plan = ps.preparer_la_suppression_du_groupe(
        Path("."), cibles, "les 3", retirer_le_groupe=_GroupeDouble())
    rapport = ps.executer_la_suppression(
        plan, Issue(ps.CLE_SUPPRIMER, "libelle", ecrit=True),
        retirer_le_groupe=_GroupeDouble(refuse={fautif}))
    assert rapport.supprime is False
    assert rapport.fichiers_non_supprimes == (
        f"outputs/{fautif}#0", f"outputs/{fautif}#1", f"outputs/{fautif}#2")


def test_le_refus_d_un_groupe_SANS_cible_compte_les_MEMBRES_pas_les_cibles(
        tmp_path, banc):
    """Mutant `M49`, survivant : `cardinal=len(cibles)` -- c'est-a-dire ZERO
    dans cette branche -- passait les 19 tests.

    « Aucun des 0 éléments de masters — 2 masters ne peut être visé » : le
    chiffre contredit la ligne que l'operateur a sous les yeux, dans la meme
    phrase.
    """
    membres = [_objet(NATURE_MASTER, "renomme-a.mov"),
               _objet(NATURE_MASTER, "renomme-b.mov")]
    groupe = _groupe(NATURE_MASTER, "masters — 2 masters", membres)
    temoin = pi.EcranInventaireDuProjet(pi.ArbreDuProjet([groupe]))

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        ps.ouvrir_la_suppression(temoin, groupe, projet=tmp_path, lot_id="L")
        return pilote.app.descendus

    ecran = _monte(_app(temoin), scenario, banc)[-1]
    assert "Aucun des 2 éléments" in ecran.message, ecran.message


def test_le_cartouche_d_un_groupe_MIXTE_compte_ce_qu_il_VISE(tmp_path, banc):
    """Mutant `M50`, survivant : `libelle_du_groupe(noeud, len(noeud.enfants))`
    passait les 19 tests, parce qu'AUCUNE fabrique du banc ne melangeait des
    membres visables et non visables.

    Le regime est reel et il vient de l'arbre : un master orphelin se greffe
    **dans le groupe des masters** de son lot d'ancrage
    (`orphelins_greffes` insere dans `parent.enfants`, ou `parent` est le
    groupe), a cote de masters declares. Un nom que `profil_du_master` ne lit
    pas est alors un membre non visable au milieu de membres visables.

    Le cartouche doit compter ce qu'il VISE. Ce que ce banc NE mesure PAS,
    dit plutot que tu : que le membre laisse de cote soit NOMME quelque part
    -- il ne l'est nulle part, et c'est le finding `C1-1` de la couche 1.
    """
    membres = [_objet(NATURE_MASTER, "L_mmu_prores_422.mov"),
               _objet(NATURE_MASTER, "renomme-a-la-main.mov"),
               _objet(NATURE_MASTER, "L_mmu_prores_hq.mov")]
    groupe = _groupe(NATURE_MASTER, "masters — 3 masters", membres)
    cibles, non_visables = ps.cibles_du_groupe(groupe, "L")
    assert len(cibles) == 2 and non_visables == ("renomme-a-la-main.mov",)
    double = _GroupeDouble()
    temoin = pi.EcranInventaireDuProjet(pi.ArbreDuProjet([groupe]))

    async def scenario(pilote):
        pilote.app.descendre = _capture(pilote.app)
        ps.ouvrir_la_suppression(temoin, groupe, projet=tmp_path, lot_id="L",
                                 retirer_le_groupe=double)
        return pilote.app.descendus

    plan = _monte(_app(temoin), scenario, banc)[-1].plan
    assert plan.libelle == "les 2 éléments de « masters — 3 masters »"
    assert len(plan.cibles_du_groupe) == 2
