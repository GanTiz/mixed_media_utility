# -*- coding: utf-8 -*-
"""Fermeture des findings de la revue de VAGUE B (2026-09-02).

La vague B a revu le diff du lot J2 (`E3-9` montre sa passe) et
d'`EPIC11-ARB-158` (la navigation du formulaire). Trois couches, en parallele,
sur un arbre isole chacune.

Un finding n'est ferme que si le mutant du finding, **reinjecte**, fait rougir
le test ecrit pour lui (politique du depot, section 6.2) -- « le rapport est
ecrit » n'est pas « ferme ». Les tests dont le docstring ouvre par « Mutant
vise » portent cette garantie : la forme exacte du mutant y est citee, pour
qu'une reinjection ulterieure se rejoue sans relire les rapports.

**Les autres n'en portent pas, et c'est dit plutot que tu.** L'en-tete de ce
banc a d'abord annonce « chaque test tue un mutant nomme » : la couche 3 du
second tour a compte onze mentions pour seize tests, et surtout trouve un
docstring qui *annoncait* un mutant qu'il ne tuait pas -- le pire des faux
verts, parce qu'il porte sa propre garantie. Un test sans mention mesure une
propriete que la campagne n'a pas mise a l'epreuve ; il vaut ce que vaut sa
lecture, ni plus.

Ce que la campagne avait laisse passer se range en deux familles, et la seconde
est la plus instructive :

* des **cablages non mesures** -- le rappel de progression, le montage de
  l'ecran, le trace de la ligne `Valider`, l'annonce des fleches au pied. Le
  mecanisme etait juste et personne ne mesurait qu'il etait branche ;
* des **bancs qui fournissaient eux-memes ce qu'ils pretendaient mesurer**. Le
  banc du canal de progression passait `rappel_progression=` a la main avant de
  verifier que les jalons arrivaient : il mesurait son propre cablage. C'est le
  frere exact du defaut `_appliquer_la_zone()` que la vague precedente avait
  ferme sur le pied de page.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

#: Le pied des paliers temoins. Il n'est pas invente : `E3-0` -- le menu de
#: l'atelier Scan -- et `E1-1` -- le menu des ateliers -- le dessinent, et la
#: confrontation en fin de fichier le verifie a leur source.
PIED_DU_PALIER = "Q quitter"

from mixed_media_utility import scan_calibrate
from mixed_media_utility.tui import (atelier_scan_calibrate,
                                     atelier_scan_parcours, execution, jetons)
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------


class _Mesure:
    forme, cardinal, octets, dpi, fichiers = "pdf", 3, 1000, 300.0, 1


class _Source:
    """Une source de scan **a trois pages**, et la cible au milieu.

    Regle des fabriques : au moins trois elements distinguables. Une source a
    une page ne distinguerait pas un jalon de son total.
    """

    mesure = _Mesure()
    forme, cardinal, dpi, fichiers = "pdf", 3, 300.0, 1
    est_multiple = False

    def __init__(self, chemin):
        self.chemin = chemin


def _formulaire(tmp_path: Path, *, dpi: str = "300",
                scan: bool = True) -> atelier_scan_calibrate.FormulaireDeCalibration:
    formulaire = atelier_scan_calibrate.FormulaireDeCalibration()
    if scan:
        formulaire.poser_le_scan(_Source(tmp_path / "mire.pdf"))
    formulaire.dpi = dpi
    return formulaire


def _coque(*ecrans, ascii_seul: bool = False) -> CoqueTui:
    return CoqueTui([PalierTemoin("Projet", PIED_DU_PALIER),
                     PalierTemoin("Ateliers", PIED_DU_PALIER), *ecrans],
                    Contexte(projet="projet_demo", palier="Scan"),
                    ascii_seul=ascii_seul)


class _CalibrationQuiJalonne:
    """Un double au contrat du coeur, **sans `**kwargs`**.

    Le docstring de `CalibrationFeinte` l'exige mot pour mot : « il porte la
    **meme signature** que le point d'entree du coeur, mots-cles compris et
    **sans `**kwargs`** -- un faux permissif laisserait passer un appel dont un
    mot-cle est mal nomme ». Deux doubles du lot J2 employaient pourtant
    `**kwargs` (tolerance `T-2` de la couche 3), donc ne pouvaient
    structurellement pas detecter un mot-cle renomme.
    """

    CHAINE = "900-png-cccccccccccc"

    def __init__(self, *, pages: int = 3, refus: str | None = None,
                 leve: BaseException | None = None):
        self.pages = pages
        self.refus = refus
        self.leve = leve
        self.appels: list[dict] = []
        self.jalons_emis: list[tuple[int, int]] = []
        #: Ce que le coeur a recu comme (etiquette, commentaire). C'est lu tard
        #: par le vrai coeur, donc c'est la mesure de ce que l'operateur a
        #: reellement valide -- et non de ce qu'il aurait pu taper apres.
        self.nomme: tuple[str, str] | None = None

    def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                 demander_le_nom_et_le_commentaire=None,
                 confirmer_l_ecrasement=None, rappel_progression=None):
        self.appels.append({"dpi": dpi, "logger": logger,
                            "rappel_progression": rappel_progression})
        if self.refus is not None:
            # **Un refus AVANT toute detection** : aucun jalon n'est emis, ce
            # qui est le regime que l'AC 9.6 vise.
            raise scan_calibrate.RefusDeCalibration(self.refus,
                                                    motif="PAS_DE_MIRE")
        if self.leve is not None:
            raise self.leve
        for faites in range(1, self.pages + 1):
            if rappel_progression is not None:
                rappel_progression(faites, self.pages)
                self.jalons_emis.append((faites, self.pages))
        # **Le nommage vient APRES les jalons**, comme dans le coeur reel : il
        # a lieu apres la detection. La premiere redaction du double le posait
        # AVANT, donc les bancs exercaient un ordre que le produit ne produit
        # jamais -- et c'est cet ordre qui decide de l'ecran sur lequel la
        # collision se pose (revue de reprise, couche 1).
        if demander_le_nom_et_le_commentaire is not None:
            self.nomme = demander_le_nom_et_le_commentaire(self.CHAINE)
        chemin = Path(project_dir) / "versions" / "calibration" / "p.json"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("{}", encoding="utf-8")
        return scan_calibrate.ProfilDeChaineConsigne(
            profile_path=chemin, chain_id=self.CHAINE, etiquette="beta",
            commentaire="", lot_correction=None, document={})


async def _tant_que(pilote, condition, tours: int = 600) -> bool:
    for _ in range(tours):
        if condition():
            return True
        await pilote.pause()
        await asyncio.sleep(0.005)
    return False


def _parcours(app, tmp_path: Path, feinte):
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    return atelier_scan_parcours.ParcoursScan(app, projet, calibration=feinte)


def _jouer_la_passe(banc, tmp_path, feinte, *, dpi: str = "300"):
    """Une passe complete, **par le point d'entree de l'operateur**.

    On passe par `consigner_le_profil` (ce que `Valider` appelle) puis par
    l'issue `lancer` retenue sur l'ecran de confirmation MONTE -- jamais par
    `lancer_la_passe_de_calibration`, qui court-circuiterait justement le
    cablage que ces bancs mesurent.
    """
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path, dpi=dpi))
        await pilote.pause()
        confirmation = pilote.app.screen
        assert isinstance(
            confirmation,
            atelier_scan_calibrate.EcranCalibrationAConfirmer), (
                "`Valider` doit ouvrir la confirmation")
        confirmation.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        confirmation.valider()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        await pilote.pause()
        vu["pile"] = [type(e).__name__ for e in pilote.app.screen_stack]
        vu["tache"] = pilote.app.tache_en_cours
        vu["ecran_de_passe"] = parcours.ecran_de_passe
        # **La garde de re-entrance se mesure ici**, dans la boucle :
        # `consigner_le_profil` monte un ecran, ce qui n'a pas de sens hors
        # pilote. C'est aussi la panne reelle -- « toute calibration suivante
        # est refusee » --, et une assertion sur le seul drapeau serait verte
        # sur un produit dont la garde lit un autre etat.
        vu["seconde_passe"] = parcours.consigner_le_profil(
            _formulaire(tmp_path))
        await pilote.pause()
        return vu

    return banc(app, scenario)


# ---------------------------------------------------------------------------
# `tache_en_cours` -- le defaut qui tuait l'atelier pour la SESSION
# ---------------------------------------------------------------------------


def test_le_drapeau_de_tache_TOMBE_apres_une_passe_refusee_vite(tmp_path, banc):
    """Le comportement de bout en bout, **et il ne tue aucun mutant a lui seul**.

    Ce docstring a d'abord annonce « Mutant vise : retirer `on_unmount` ». La
    reinjection l'a dementi : ce banc reste VERT sous ce mutant, parce que les
    autres chemins d'extinction suffisent au regime qu'il joue. C'est le test
    voisin, `..._ETEINT_au_demontage_ce_qu_il_allume_au_montage`, qui porte la
    garantie -- il mesure la propriete plutot que l'ordonnancement.

    Ce banc-ci garde son utilite propre : il mesure que l'atelier repart, ce
    qu'aucune mesure de propriete ne dit.

    `EcranExecution.on_mount` pose `tache_en_cours = True` et rien ne le
    retirait. `descendre` **differe** le montage, donc une passe refusee vite se
    termine avant que le message de montage ne soit traite, et l'ordre observe
    (18 tours sur 20) etait `True` / `False` / `True` -- le dernier `True` etant
    le montage, qui arrive apres la fin.

    Ce que le drapeau reste-a-vrai coute, mesure 10/10 : `Echap` ne depile plus,
    `q` ne quitte plus, et la garde de re-entrance refuse **toute calibration
    suivante**. Le banc mesure donc les deux : le drapeau tombe, ET une seconde
    passe part.
    """
    feinte = _CalibrationQuiJalonne(refus="pas de mire sur cette planche")
    vu = _jouer_la_passe(banc, tmp_path, feinte)

    assert vu["tache"] is False, (
        "le drapeau doit etre tombe apres la passe : sinon `Echap`, `q` et "
        "toute calibration suivante sont mortes pour la session")
    assert vu["seconde_passe"] is not None, (
        "une seconde calibration doit pouvoir partir")


def test_l_ecran_de_passe_ETEINT_au_demontage_ce_qu_il_allume_au_montage(
        tmp_path, banc):
    """Mutant vise : retirer `oublier_la_tache()` de `on_unmount`. La SYMETRIE.

    **Pourquoi cette mesure et pas seulement les deux bancs de bout en bout
    ci-dessous** : la campagne de reinjection les a joues sous ce mutant et ils
    sont restes VERTS. **Le motif a change sous ce docstring, pas le verdict**
    (releve le 2026-09-05) : il invoquait « le montage tardif (AC 9.6) », que
    `EPIC11-ARB-160` a retire le 2026-09-02 -- l'ecran se monte desormais avant
    le fil, donc y compris sur un refus. Ce qui ferme reellement la course dans
    les deux regimes exerces est le passage par la boucle : chaque montage et
    chaque jalon y repassent, ce qui laisse le temps au message de montage
    d'etre traite. La fenetre qui reste est etroite : une
    passe qui n'emet **qu'un** jalon et rend aussitot. Un banc qui viserait
    cette fenetre mesurerait un ordonnancement, donc rendrait un verdict
    instable.

    On mesure donc la propriete elle-meme, qui est deterministe : ce que le
    montage allume, le demontage l'eteint. `Mount` precede toujours `Unmount`
    pour une meme instance, donc cette symetrie est ce qui rend l'ordre
    d'arrivee des messages sans importance -- et c'est tout le correctif.
    """
    app = _coque()
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.ouvrir_la_calibration_en_cours(
            pilote.app)
        await pilote.pause()
        # `on_mount` a pose le drapeau : c'est le point de depart du defaut.
        vu["au_montage"] = pilote.app.tache_en_cours
        pilote.app.pop_screen()
        await pilote.pause()
        vu["au_demontage"] = pilote.app.tache_en_cours
        return vu

    banc(app, scenario)
    assert vu["au_montage"] is True, (
        "le montage de l'ecran d'execution pose bien le drapeau")
    assert vu["au_demontage"] is False, (
        "et son demontage doit le retirer : sinon `Echap`, `q` et toute "
        "calibration suivante sont mortes pour la session")


def test_une_passe_qui_JALONNE_laisse_aussi_le_drapeau_tombe(tmp_path, banc):
    """Le volet symetrique : la passe qui jalonne pour de bon.

    Le test precedent joue un refus sans jalon ; celui-ci joue les trois jalons.
    **Aucun des deux ne tue le mutant d'`on_unmount`** -- mesure faite, ils
    restent verts --, et c'est pourquoi la propriete est mesuree a part. Ce
    qu'ils mesurent, eux, est que le drapeau tombe dans les deux regimes du
    parcours.
    """
    feinte = _CalibrationQuiJalonne(pages=3)
    vu = _jouer_la_passe(banc, tmp_path, feinte)
    assert feinte.jalons_emis == [(1, 3), (2, 3), (3, 3)]
    assert vu["tache"] is False


# ---------------------------------------------------------------------------
# Le canal de progression -- cable, et mesure sans que le banc le cable
# ---------------------------------------------------------------------------


def test_le_rappel_de_progression_ATTEINT_le_coeur_sans_que_le_banc_le_cable(
        tmp_path, banc):
    """Mutant vise : `rappel_progression=noter_le_jalon` -> `None`. SURVIVANT.

    C'est **la** ligne qui relie la surface de l'ecran au coeur, et sous le
    mutant la barre reste a zero du debut a la fin de la passe -- litteralement
    la panne d'Egan (« RIEN n'indique qu'on a lance le processus »). Aucun des
    1465 tests du lot large ne rougissait.

    Le banc du lot annoncait « le canal de bout en bout » et appelait
    `consigner(..., rappel_progression=ecran.surface.noter)` **a la main** : il
    fournissait le cablage qu'il pretendait mesurer. Ici le banc ne passe
    aucun rappel ; il lit ce que le COEUR a recu.
    """
    feinte = _CalibrationQuiJalonne(pages=3)
    _jouer_la_passe(banc, tmp_path, feinte)

    assert len(feinte.appels) == 1
    recu = feinte.appels[0]["rappel_progression"]
    assert recu is not None, (
        "le parcours doit BRANCHER la surface sur le coeur ; sans ce mot-cle "
        "la barre reste a zero pendant toute la passe")
    assert callable(recu)
    # Et les jalons ont bien traverse : un mot-cle present mais inerte serait
    # vert sous la seule assertion ci-dessus.
    assert feinte.jalons_emis == [(1, 3), (2, 3), (3, 3)]


def test_l_ecran_d_execution_est_SUR_LA_PILE_pendant_la_passe(tmp_path, banc):
    """Mutant vise : supprimer `app.descendre(ecran)` du montage. SURVIVANT.

    Le banc du lot verifiait le **type de l'objet rendu** par la fabrique de
    montage, jamais qu'il etait sur la pile : un ecran construit et jamais
    empile ne s'abonne a rien, et l'operateur ne voit aucune progression.

    **Le double TIENT la passe ouverte**, et c'est ce qui rend la mesure
    possible : la pile ne se lit qu'entre le premier jalon et la fin, fenetre
    qu'un double instantane referme avant qu'on ait regarde.
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _CalibrationQuiTient(_CalibrationQuiJalonne):
        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            self.appels.append({"dpi": dpi, "logger": logger,
                                "rappel_progression": rappel_progression})
            # **DEUX jalons avant de tenir, pas un.** Un seul ne
            # distinguerait pas « l'ecran se monte une fois » de « l'ecran se
            # monte a chaque jalon » : le second montage n'aurait pas encore eu
            # lieu au moment ou le banc regarde la pile. Regle des fabriques,
            # transposee au temps plutot qu'a une collection.
            rappel_progression(1, 3)
            rappel_progression(2, 3)
            tenu.set()
            relache.wait(timeout=10)
            rappel_progression(3, 3)
            chemin = Path(project_dir) / "versions" / "calibration" / "p.json"
            chemin.parent.mkdir(parents=True, exist_ok=True)
            chemin.write_text("{}", encoding="utf-8")
            return scan_calibrate.ProfilDeChaineConsigne(
                profile_path=chemin, chain_id=self.CHAINE, etiquette="beta",
                commentaire="", lot_correction=None, document={})

    app = _coque()
    parcours = _parcours(app, tmp_path, _CalibrationQuiTient())
    vue = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        assert await _tant_que(pilote,
                               lambda: parcours.ecran_de_passe is not None)
        # **La pile se lit PENDANT la passe**, la seule fenetre ou l'ecran vit.
        vue["sur_la_pile"] = (parcours.ecran_de_passe
                              in pilote.app.screen_stack)
        vue["au_sommet"] = pilote.app.screen is parcours.ecran_de_passe
        vue["ecran"] = parcours.ecran_de_passe
        vue["avancement"] = parcours.ecran_de_passe.surface.avancement.faites
        # **UN seul ecran d'execution, pas un par jalon.** Le montage est
        # garde par `if self.ecran_de_passe is None` ; sans cette garde chaque
        # page detectee empilerait un ecran de plus, et rien ne le mesurait --
        # un mutant `if True:` restait vert sur 155 tests.
        vue["combien_d_ecrans"] = sum(
            1 for e in pilote.app.screen_stack
            if isinstance(e, execution.EcranExecution))
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        vue["depile_a_la_fin"] = (parcours.ecran_de_passe
                                  not in pilote.app.screen_stack)
        return vue

    banc(app, scenario)
    assert vue["sur_la_pile"] is True, (
        "l'ecran d'execution doit etre EMPILE, pas seulement construit")
    assert vue["au_sommet"] is True, "et visible, donc au sommet"
    assert isinstance(vue["ecran"], execution.EcranExecution)
    # Les deux premiers jalons ont traverse jusqu'a la surface de CET ecran.
    assert vue["avancement"] == 2
    assert vue["combien_d_ecrans"] == 1, (
        "un ecran d'execution pour la passe, pas un par jalon")
    # Et le volet symetrique : il est depile a la fin, sans quoi l'operateur
    # resterait devant une barre pleine avec le formulaire annote dessous.
    assert vue["depile_a_la_fin"] is True


def test_un_refus_avant_la_detection_mene_DIRECTEMENT_au_refus(tmp_path, banc):
    """`EPIC11-ARB-160` : ce que l'AC 9.6 protege, et ce qu'elle ne peut pas.

    **Ce banc a d'abord mesure autre chose, et il faut le dire** : il lisait
    `parcours.ecran_de_passe` APRES la passe pour conclure « aucun ecran monte ».
    La fin de passe remet cet attribut a `None` : l'assertion etait devenue
    vide de sens des que le montage a change. On mesure donc la PILE.

    L'AC 9.6 demande qu'une passe refusee avant la detection « ne monte pas
    l'ecran d'execution et va directement au refus », et son motif est nomme :
    « un ecran de progression qui paraitrait sur un refus serait la meme faute
    qu'un jalon avant l'ecriture ». Sur un coeur synchrone, la lettre est
    inconciliable avec l'AC 9.4 -- on ne sait pas qu'une passe sera refusee
    avant de l'avoir lancee. Ce qui est tenu, et mesure ici :

    * **l'operateur va bien directement au refus** : a la fin, aucun ecran
      d'execution dans la pile ;
    * **aucun chiffre n'est invente** : le total reste a zero et aucun jalon
      n'est emis, donc rien ne promet un travail qui n'a pas eu lieu.
    """
    feinte = _CalibrationQuiJalonne(refus="pas de mire sur cette planche")
    vu = _jouer_la_passe(banc, tmp_path, feinte)

    assert feinte.jalons_emis == [], (
        "un refus avant la detection ne produit AUCUN jalon")
    # L'ensemble EXACT des classes de la pile a la fin, et non une appartenance.
    assert "EcranCalibrationEnCours" not in vu["pile"]
    assert "EcranExecution" not in vu["pile"]
    assert vu["ecran_de_passe"] is None, (
        "et le parcours ne garde aucune reference a l'ecran de la passe finie")


def test_un_refus_avant_la_detection_ne_PROMET_aucun_chiffre(tmp_path, banc):
    """Mutant vise : `surface.noter(0, 42)` au montage, avant le fil. SURVIVANT.

    **L'autre moitie du motif de l'AC 9.6, et elle n'etait pas mesuree.**
    `EPIC11-ARB-160` retient deux choses de ce motif : « l'operateur va bien
    directement au refus » -- que le banc voisin mesure sur la pile finale --
    et « **aucun chiffre n'est invente** ». La seconde ne l'etait pas.

    Ce qui la laissait passer est precis : le banc voisin lit
    `feinte.jalons_emis == []`, c'est-a-dire ce que **le coeur** a emis. Or la
    surface n'est pas alimentee par le seul coeur : le parcours la construit et
    la tient avant de lancer le fil, et tout ce qu'il y ecrirait lui-meme
    paraitrait a l'ecran sans qu'aucun jalon existe. Mesure : un
    `surface.noter(0, 42)` glisse dans `consigner_le_profil` laisse les
    **34 bancs verts**, pendant que l'operateur voit promis « 42 pages » sur
    une passe qui sera refusee a l'ingestion. C'est litteralement « un chiffre
    invente presente comme une mesure », que `ouvrir_la_calibration_en_cours`
    dit dans son propre docstring vouloir ecarter.

    **La fenetre se lit PENDANT le refus, pas apres.** Depuis
    `EPIC11-ARB-160`, l'ecran d'execution est monte avant le fil : sur une
    passe refusee il parait le temps de l'ingestion, et c'est exactement ce
    temps-la qu'il faut regarder. Un double instantane le referme avant qu'on
    ait regarde -- le refus tient donc, comme le double du banc voisin retient
    la passe.
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _RefusQuiTient(_CalibrationQuiJalonne):
        """Un refus **avant toute detection**, mais qui laisse le temps de voir.

        Il n'emet aucun jalon -- c'est le regime de l'AC 9.6 --, et il ne rend
        la main qu'une fois le banc passe.
        """

        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            self.appels.append({"dpi": dpi, "logger": logger,
                                "rappel_progression": rappel_progression})
            tenu.set()
            relache.wait(timeout=10)
            raise scan_calibrate.RefusDeCalibration(
                "pas de mire sur cette planche", motif="PAS_DE_MIRE")

    feinte = _RefusQuiTient()
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        assert await _tant_que(pilote,
                               lambda: parcours.ecran_de_passe is not None)
        avancement = parcours.ecran_de_passe.surface.avancement
        vu["total_pendant"] = avancement.total
        vu["faites_pendant"] = avancement.faites
        vu["temps_restant"] = avancement.temps_restant
        # **Le journal aussi**, et pas seulement les compteurs : une ligne
        # « 0/42 pages » posee la survivrait au depilement, puisque c'est ce
        # que l'operateur relit.
        vu["journal_pendant"] = list(
            parcours.ecran_de_passe.surface.journal.lignes)
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        await pilote.pause()
        vu["pile_a_la_fin"] = [type(e).__name__
                               for e in pilote.app.screen_stack]
        return vu

    banc(app, scenario)

    assert feinte.jalons_emis == [], (
        "le regime mesure est bien celui d'un refus AVANT toute detection")
    # Le total est ce que le coeur n'a pas encore dit : **zero**, et zero se
    # dessine comme une barre vide plutot que comme une promesse.
    assert vu["total_pendant"] == 0, (
        "l'ecran monte sur une passe qui sera refusee ne doit promettre AUCUN "
        f"total ; recu {vu['total_pendant']!r}")
    assert vu["faites_pendant"] == 0, (
        f"ni aucun fait accompli ; recu {vu['faites_pendant']!r}")
    assert vu["temps_restant"] is None, (
        "ni une estimation de duree, qui serait tiree d'un total invente ; "
        f"recu {vu['temps_restant']!r}")
    assert vu["journal_pendant"] == [], (
        "et le journal ne garde aucune ligne d'avancement d'un travail qui "
        f"n'a pas eu lieu ; recu {vu['journal_pendant']!r}")
    # Le volet que le banc voisin porte, reaffirme ici parce que les deux
    # moities du motif se tiennent : promettre zero ne vaudrait rien si
    # l'ecran restait ensuite en travers du refus.
    assert "EcranExecution" not in vu["pile_a_la_fin"]


def test_les_jalons_du_coeur_ATTEIGNENT_la_barre_du_premier_au_DERNIER(
        tmp_path, banc):
    """Le volet symetrique du banc ci-dessus. Sans lui, zero serait gratuit.

    Une frontiere negative qui exige « total a zero » est tenue a la
    perfection par un cablage mort : il suffit que la surface ne soit jamais
    alimentee. Ce banc mesure donc que les chiffres du coeur, eux, arrivent --
    et il les fait arriver a **trois valeurs distinguables**, jamais un
    remplissage uniforme (regle des fabriques, point 1).

    **Et il regarde les DEUX bords** (point 4, pose le 2026-09-03 sur un mutant
    de balayage tronque). Le premier jalon mesure que le canal s'ouvre ; le
    **dernier** mesure qu'aucun balayage ne saute la queue -- une cible au
    milieu demasque un `find` fautif, elle ne demasque pas une troncature. Le
    journal est ici la collection : trois lignes distinctes, la premiere et la
    derniere assertees nommement.
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _TroisJalonsPuisTient(_CalibrationQuiJalonne):
        """Trois jalons **de valeurs differentes**, puis la passe tient.

        La tenue est apres le troisieme, pour que la queue du journal soit
        ecrite au moment ou le banc regarde.

        **La fin de passe est DELEGUEE a la classe mere, pas recopiee.** Les
        doubles voisins recopient `Path(project_dir) / "versions" / ...`, que
        la frontiere de composition compte comme une dette
        (`test_la_DETTE_de_composition_ne_peut_que_DESCENDRE`, plafond qui « ne
        monte pas »). Ce banc n'en ajoute donc aucune.

        **Et la premiere redaction de ce paragraphe etait FAUSSE, mesuree puis
        corrigee** : elle affirmait que recopier le litteral faisait rougir la
        frontiere « ici et maintenant ». Comptage fait -- ce fichier porte
        **2 compositions avant comme apres** ce banc, et le plafond est deja
        depasse (300 pour 297) a la tete de la branche, independamment de lui.
        La delegation reste le bon geste ; elle ne repare pas ce rouge-la, qui
        est au registre.

        `rappel_progression=None` est passe a la mere pour qu'elle n'emette pas
        une SECONDE serie de jalons par-dessus les trois d'ici.
        """

        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            for faites in (1, 2, 3):
                rappel_progression(faites, 3)
                self.jalons_emis.append((faites, 3))
            tenu.set()
            relache.wait(timeout=10)
            return super().__call__(
                project_dir, scan_path, dpi=dpi, logger=logger,
                demander_le_nom_et_le_commentaire=(
                    demander_le_nom_et_le_commentaire),
                confirmer_l_ecrasement=confirmer_l_ecrasement,
                rappel_progression=None)

    feinte = _TroisJalonsPuisTient()
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        assert await _tant_que(pilote,
                               lambda: parcours.ecran_de_passe is not None)
        # **L'ecran se CAPTURE ici, et on ne relit plus l'attribut.**
        # `conclure_la_passe` remet `ecran_de_passe` a `None` a la fin ; une
        # attente qui dereferencerait l'attribut a chaque tour leverait un
        # `AttributeError` des que la passe se termine sous elle, et un mutant
        # se ferait alors « tuer » par une pile d'appels au lieu d'une
        # assertion nommee. Mesure : le mutant de troncature en queue rendait
        # `'NoneType' object has no attribute 'surface'`, ce qui ne dit rien de
        # la barre.
        ecran_de_passe = parcours.ecran_de_passe
        vu["attendu_la_queue"] = await _tant_que(
            pilote,
            lambda: ecran_de_passe.surface.avancement.faites == 3)
        avancement = ecran_de_passe.surface.avancement
        vu["total"] = avancement.total
        vu["faites"] = avancement.faites
        vu["journal"] = list(ecran_de_passe.surface.journal.lignes)
        # Les lots DECLARES, pour que le total compose s'asserte contre ce qui
        # le compose et non contre un « 6 » recopie.
        vu["lots"] = [(lot.nom, lot.cardinal)
                      for lot in ecran_de_passe.surface.passe.lots]
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        return vu

    banc(app, scenario)

    assert feinte.jalons_emis == [(1, 3), (2, 3), (3, 3)], (
        "trois jalons DISTINGUABLES, jamais un remplissage uniforme")
    # **Le total vient du coeur, pas d'une invention -- mais il n'est plus le
    # meme 3, et c'est la dette `CALIB-N1` qui l'a change le 2026-09-07.**
    #
    # La barre couvre desormais les DEUX phases de la calibration : l'ingestion,
    # qui rasterise et etait muette -- c'est le grief d'Egan « la progression de
    # la calibration saute de 0 a 100 » --, puis la detection. La passe declare
    # donc un lot par phase, chacun au cardinal que le coeur vient de mesurer,
    # et le total global vaut ce cardinal AUTANT DE FOIS qu'il y a de phases.
    #
    # Ce banc a rougi sur cette ligne a la non-regression du 2026-09-07, et sa
    # correction n'est PAS un relachement : l'attente se lit maintenant des lots
    # DECLARES plutot que d'un « 6 » recopie, si bien qu'une phase perdue ou une
    # phase declaree sans son cardinal la font rougir toutes les deux. Les noms
    # des deux lots sont assertes juste apres, sans quoi « deux lots » serait
    # tenu par n'importe quelle paire.
    assert vu["lots"] == [
        (atelier_scan_calibrate.LOT_DE_L_INGESTION, 3),
        (atelier_scan_calibrate.LOT_DE_LA_DETECTION, 3),
    ], ("la passe declare un lot par phase, chacun au cardinal du coeur ; recu "
        f"{vu['lots']!r}")
    assert vu["total"] == sum(cardinal for _libelle, cardinal in vu["lots"]), (
        "le total de la barre est la somme des lots declares, pas un chiffre "
        f"invente ; recu {vu['total']!r} pour {vu['lots']!r}")
    # **La QUEUE** : le dernier jalon a bien ete compte.
    assert vu["attendu_la_queue"] is True, (
        "la barre doit atteindre le dernier jalon ; elle s'est arretee a "
        f"{vu['faites']!r} sur {vu['total']!r}")
    assert vu["faites"] == 3, (
        "le DERNIER jalon doit atteindre la barre -- un balayage tronque "
        f"s'arreterait avant ; recu {vu['faites']!r}")
    # **La moitie que ce banc ne mesure PAS**, dite plutot que tue : la feinte
    # n'emet qu'UNE phase (elle passe `rappel_progression=None` a sa mere), donc
    # la barre s'arrete legitimement a mi-course. Que le total soit ATTEINT
    # quand les deux phases emettent est mesure par le banc suivant -- et sans
    # lui, une barre qui plafonnerait a 50 % passerait ici pour verte.
    # **La TETE et la QUEUE du journal**, nommees toutes les deux.
    assert vu["journal"][0] == "1/3 pages", (
        f"la tete du journal, premier jalon ; recu {vu['journal']!r}")
    assert vu["journal"][-1] == "3/3 pages", (
        f"la queue du journal, dernier jalon ; recu {vu['journal']!r}")
    assert len(vu["journal"]) == 3, (
        f"une ligne par jalon, ni plus ni moins ; recu {vu['journal']!r}")


def test_les_DEUX_phases_emettent_et_la_barre_ATTEINT_son_terme(tmp_path,
                                                                banc):
    """La moitie que le banc precedent ne pouvait pas mesurer.

    **Le defaut que ce banc ferme est le SYMETRIQUE exact du grief d'Egan.**
    Le sien etait « la progression de la calibration saute de 0 a 100 » : une
    barre qui ne montre rien puis tout. Depuis que la barre couvre les deux
    phases (dette `CALIB-N1`), le mode de panne s'inverse -- une barre qui
    plafonne a **50 %** parce que la seconde phase n'est jamais routee vers son
    lot. Une passe qui reste a mi-course quand tout est fini ment autant qu'une
    passe qui saute a 100.

    Rien ne le mesurait : le banc voisin emet UNE seule phase, donc il voit
    3 sur 6 et c'est correct pour lui. Le total compose y est asserte, jamais
    son ATTEINTE.

    **La frontiere de phase se lit sur un jalon non progressif** -- la seconde
    suite repart a `1` alors que la premiere s'est arretee plus haut. La feinte
    joue donc deux suites de trois, avec des valeurs distinguables dans chacune
    (regle des fabriques, point 1), et le banc regarde les deux BORDS du total :
    qu'il soit atteint, et que le journal porte la tete de la premiere phase
    comme la queue de la seconde (point 4).
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _DeuxPhasesPuisTient(_CalibrationQuiJalonne):
        """Deux suites de trois jalons, la seconde repartant a 1.

        C'est la forme exacte que le coeur produit -- mesuree cote coeur par
        `test_les_DEUX_phases_emettent_et_la_seconde_REPART_a_un` -- et non une
        invention de banc. `rappel_progression=None` est passe a la mere pour
        qu'elle n'en ajoute pas une troisieme par-dessus.
        """

        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            for _phase in (1, 2):
                for faites in (1, 2, 3):
                    rappel_progression(faites, 3)
                    self.jalons_emis.append((faites, 3))
            tenu.set()
            relache.wait(timeout=10)
            return super().__call__(
                project_dir, scan_path, dpi=dpi, logger=logger,
                demander_le_nom_et_le_commentaire=(
                    demander_le_nom_et_le_commentaire),
                confirmer_l_ecrasement=confirmer_l_ecrasement,
                rappel_progression=None)

    feinte = _DeuxPhasesPuisTient()
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        assert await _tant_que(pilote,
                               lambda: parcours.ecran_de_passe is not None)
        # Meme discipline que le banc voisin : l'ecran se CAPTURE, on ne relit
        # plus l'attribut, que `conclure_la_passe` remet a `None`.
        ecran_de_passe = parcours.ecran_de_passe
        vu["a_atteint"] = await _tant_que(
            pilote,
            lambda: (ecran_de_passe.surface.avancement.faites
                     == ecran_de_passe.surface.avancement.total))
        avancement = ecran_de_passe.surface.avancement
        vu["faites"] = avancement.faites
        vu["total"] = avancement.total
        vu["journal"] = list(ecran_de_passe.surface.journal.lignes)
        # **On mesure l'etat du PRODUIT, pas celui du routeur.** Le relais est
        # une locale du parcours ; l'exposer pour ce banc ouvrirait une surface
        # que rien d'autre n'emploie. Le lot courant de la passe dit la meme
        # chose et il est ce que l'ecran dessine.
        passe = ecran_de_passe.surface.passe
        vu["lot_courant"] = passe.lot_courant.nom
        vu["rang_du_lot"] = passe.rang_du_lot_courant
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        return vu

    banc(app, scenario)

    assert feinte.jalons_emis == [(1, 3), (2, 3), (3, 3),
                                  (1, 3), (2, 3), (3, 3)], (
        "deux suites de trois, la seconde repartant a 1 -- c'est la frontiere "
        "de phase que le routeur lit")
    # **LE point du banc** : la barre atteint son terme, elle ne plafonne pas.
    assert vu["a_atteint"] is True, (
        "la barre doit ATTEINDRE son total quand les deux phases ont emis ; "
        f"elle s'est arretee a {vu['faites']!r} sur {vu['total']!r}")
    assert (vu["faites"], vu["total"]) == (6, 6), (
        "six jalons pour deux lots de trois ; recu "
        f"{vu['faites']!r} sur {vu['total']!r}")
    # La seconde phase a bien ete OUVERTE, et non entassee dans la premiere :
    # sans cette assertion, un routeur qui laisserait tout dans le lot 1
    # afficherait aussi 6 -- par debordement, pas par composition. Le libelle
    # nom est asserte en plus du rang, sans quoi « le second lot » serait tenu par
    # n'importe quel second lot.
    assert vu["rang_du_lot"] == 1, (
        "la passe doit avoir ouvert son SECOND lot ; recu "
        f"{vu['rang_du_lot']!r}")
    assert vu["lot_courant"] == atelier_scan_calibrate.LOT_DE_LA_DETECTION, (
        f"le second lot est celui de la detection ; recu {vu['lot_courant']!r}")
    # **Les deux BORDS du journal**, sur toute la passe cette fois.
    assert vu["journal"][0] == "1/3 pages", (
        f"la tete, premier jalon de la PREMIERE phase ; recu {vu['journal']!r}")
    assert vu["journal"][-1] == "3/3 pages", (
        f"la queue, dernier jalon de la SECONDE phase ; recu {vu['journal']!r}")
    assert len(vu["journal"]) == 6, (
        f"une ligne par jalon des deux phases ; recu {vu['journal']!r}")


def test_sur_une_MIRE_d_UNE_page_les_deux_phases_s_ouvrent_quand_meme(tmp_path,
                                                                      banc):
    """Le cas de bord que le banc voisin ne pouvait pas voir -- et c'est CELUI
    d'Egan.

    **Trouve par mutation, pas par relecture** (2026-09-07). Le mutant
    `faites <= self._dernier` -> `faites < self._dernier` dans
    `RelaisDesPhasesDeLaCalibration.noter` **survivait** au banc des deux
    phases : celui-la joue trois pages par phase, donc la seconde suite repart
    a `1` apres un `3`, et un `<` strict detecte la frontiere aussi bien qu'un
    `<=`. L'egalite n'etait jamais atteinte.

    Or l'egalite est precisement le cas d'une **mire** : une seule page, donc
    les deux phases emettent `(1, 1)` et `faites == self._dernier`. Sous `<`
    strict, les deux jalons restent dans le premier lot, la seconde phase ne
    s'ouvre jamais, et la barre plafonne a `1/2` -- c'est-a-dire le grief
    d'origine sous une autre forme. Le code le disait dans son commentaire ;
    aucun banc ne le mesurait.

    C'est la regle des fabriques appliquee aux CARDINAUX plutot qu'aux
    collections : une fabrique qui produit toujours trois elements ne demasque
    pas ce qui ne mord qu'a un seul. La mire n'est pas un cas theorique -- c'est
    l'objet meme que la calibration lit.
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _UneMirePuisTient(_CalibrationQuiJalonne):
        """Deux phases d'UNE page : `(1, 1)` puis `(1, 1)`.

        Le cardinal 1 n'est pas une commodite de banc : une page de mire est ce
        que `mmu scan calibrate` lit, et le raster reel du depot
        (`tests/fixtures/scans/Page calibration HP ENVY La Seyne.pdf`) en porte
        exactement une.
        """

        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            for _phase in (1, 2):
                rappel_progression(1, 1)
                self.jalons_emis.append((1, 1))
            tenu.set()
            relache.wait(timeout=10)
            return super().__call__(
                project_dir, scan_path, dpi=dpi, logger=logger,
                demander_le_nom_et_le_commentaire=(
                    demander_le_nom_et_le_commentaire),
                confirmer_l_ecrasement=confirmer_l_ecrasement,
                rappel_progression=None)

    feinte = _UneMirePuisTient()
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        assert await _tant_que(pilote,
                               lambda: parcours.ecran_de_passe is not None)
        ecran_de_passe = parcours.ecran_de_passe
        vu["a_atteint"] = await _tant_que(
            pilote,
            lambda: (ecran_de_passe.surface.avancement.faites
                     == ecran_de_passe.surface.avancement.total))
        avancement = ecran_de_passe.surface.avancement
        vu["faites"] = avancement.faites
        vu["total"] = avancement.total
        passe = ecran_de_passe.surface.passe
        vu["lot_courant"] = passe.lot_courant.nom
        vu["rang_du_lot"] = passe.rang_du_lot_courant
        vu["journal"] = list(ecran_de_passe.surface.journal.lignes)
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        return vu

    banc(app, scenario)

    assert feinte.jalons_emis == [(1, 1), (1, 1)], (
        "deux phases d'une page : c'est l'EGALITE `faites == dernier` que ce "
        "banc existe pour atteindre")
    # **Le mutant que ce banc tue** : sous `<` strict, la seconde phase ne
    # s'ouvre pas et la barre reste a 1 sur 2.
    assert vu["rang_du_lot"] == 1, (
        "sur une mire aussi, la seconde phase doit OUVRIR son lot ; la passe "
        f"est restee au lot {vu['rang_du_lot']!r}")
    assert vu["lot_courant"] == atelier_scan_calibrate.LOT_DE_LA_DETECTION, (
        f"le second lot est celui de la detection ; recu {vu['lot_courant']!r}")
    assert vu["a_atteint"] is True, (
        "la barre doit atteindre son terme sur une mire comme ailleurs ; elle "
        f"s'est arretee a {vu['faites']!r} sur {vu['total']!r}")
    assert (vu["faites"], vu["total"]) == (2, 2), (
        "deux lots d'une page ; recu "
        f"{vu['faites']!r} sur {vu['total']!r}")
    # Les deux bords du journal, qui portent ici la MEME valeur -- c'est le
    # propre du cas limite, et l'asserter dit que les deux lignes existent.
    assert vu["journal"] == ["1/1 pages", "1/1 pages"], (
        f"une ligne par phase, meme libelle ; recu {vu['journal']!r}")


def test_une_TROISIEME_suite_de_jalons_reste_dans_le_second_lot(tmp_path,
                                                                banc):
    """Ce qu'une troisieme suite fait a la passe -- et un mutant TOLERE, dit.

    **Ce banc a ete ecrit pour tuer un mutant, et il ne le tue pas.** Le dire
    vaut mieux que de laisser croire l'inverse : retirer `and
    self.phases_ouvertes < 2` de la frontiere du routeur laisse ce banc vert,
    mesure le 2026-09-07 apres l'avoir ecrit exactement pour ca.

    **Pourquoi -- et la premiere redaction de ce paragraphe se trompait.** Elle
    affirmait qu'une troisieme suite ferait « reculer la barre », chaque
    `commencer_le_lot_suivant` remettant `faites_du_lot_courant` a zero. La
    remise a zero a bien lieu, mais le rang est **ecrete a la queue**
    (`min(self._commences, len(self.lots) - 1)`), donc la troisieme suite
    refait le compte du MEME second lot et le termine au meme endroit. L'etat
    final est identique ; seul un creux TRANSITOIRE de la barre distingue les
    deux versions, et aucune observation de fin de passe ne peut le voir.

    Le docstring du routeur avait donc raison, et c'est mon hypothese qui etait
    fausse.

    **Les DEUX gardes sont redondantes, et c'est mesure -- pas suppose.** Trois
    campagnes, sur ce banc :

    | ce qui est mute | verdict |
    |---|---|
    | la borne du routeur (`phases_ouvertes < 2`) seule | **survit** |
    | l'affectation du routeur (`phases_ouvertes = 2` -> `= 1`) seule | **survit** |
    | l'ecretage du rang (`min(...)` de `commencer_le_lot_suivant`) seul | **survit** |
    | la borne **et** l'ecretage | **MEURT** (`IndexError`, rang `2`) |
    | l'affectation **et** l'ecretage | **MEURT** (`IndexError`, rang `2`) |

    Chacune masque l'autre : sans la borne, l'ecretage ramene le rang au second
    lot ; sans l'ecretage, la borne empeche le troisieme appel d'avoir lieu.
    Aucun banc ne peut donc tuer l'une des deux isolement, et ce n'est pas un
    defaut de ce banc-ci -- c'est une propriete du code. Les survivants sont
    **toleres et documentes** a ce titre, avec la mesure qui l'etablit.

    **La DEUXIEME ligne du tableau a ete ajoutee le 2026-09-07**, sur un second
    survivant trouve par la couche 1 de la revue **sur la meme instruction** :
    `self.phases_ouvertes = 2` passe a `= 1` et les 34 tests de ce fichier
    restent verts. C'est le meme masquage, par le meme ecretage, et il tient a
    ceci : `phases_ouvertes` a `1` apres la frontiere laisse la condition
    `phases_ouvertes < 2` vraie, donc la troisieme suite ouvre un troisieme lot
    au lieu d'etre ignoree -- mais `min(self._commences, len(self.lots) - 1)`
    ramene son rang sur le second lot, et l'etat final est celui de l'original.
    Les deux mutations de cette ligne -- la borne et l'affectation -- sont donc
    la MEME tolerance, pas deux : ce qui n'est pas mesurable, c'est le nombre de
    phases que le routeur s'autorise a ouvrir, parce que la surface d'execution
    le borne une seconde fois en aval.

    **Ce que ca dit du code, plutot que du banc** : la borne du routeur est
    aujourd'hui une garde de CEINTURE, l'ecretage etant les bretelles. La
    retirer ne changerait rien d'observable -- et c'est precisement pourquoi
    elle doit rester : elle est ce qui empeche le routeur de mentir *au premier
    jalon d'une troisieme phase*, en declarant un lot que la passe ne porte pas.
    Une garde redondante qui documente son intention vaut mieux qu'un
    debordement rattrape trois couches plus bas.

    **Ce que le banc mesure quand meme, et pourquoi il reste** : qu'une
    troisieme suite ne cree pas un troisieme lot, ne fait pas deborder le
    total, et laisse la barre atteindre son terme. Le double mutant montre que
    ces trois proprietes-la ne sont tenues par aucune des deux gardes seule,
    mais bien par leur conjonction -- et rien ne les mesurait avant lui.

    **Ce banc joue un producteur qui n'existe pas aujourd'hui**, et c'est
    assume : la calibration n'a que deux phases. Il mesure une GARDE, pas un
    parcours -- sans quoi elle se fait retirer au premier nettoyage comme du
    code mort. La troisieme suite repart a `1` comme les deux autres : c'est la
    forme qu'aurait une phase de plus, pas une valeur choisie pour passer.
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _TroisSuitesPuisTient(_CalibrationQuiJalonne):
        """Trois suites de deux jalons, chacune repartant a 1."""

        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            for _suite in (1, 2, 3):
                for faites in (1, 2):
                    rappel_progression(faites, 2)
                    self.jalons_emis.append((faites, 2))
            tenu.set()
            relache.wait(timeout=10)
            return super().__call__(
                project_dir, scan_path, dpi=dpi, logger=logger,
                demander_le_nom_et_le_commentaire=(
                    demander_le_nom_et_le_commentaire),
                confirmer_l_ecrasement=confirmer_l_ecrasement,
                rappel_progression=None)

    feinte = _TroisSuitesPuisTient()
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        assert await _tant_que(pilote,
                               lambda: parcours.ecran_de_passe is not None)
        ecran_de_passe = parcours.ecran_de_passe
        vu["a_atteint"] = await _tant_que(
            pilote,
            lambda: (ecran_de_passe.surface.avancement.faites
                     == ecran_de_passe.surface.avancement.total))
        avancement = ecran_de_passe.surface.avancement
        vu["faites"] = avancement.faites
        vu["total"] = avancement.total
        passe = ecran_de_passe.surface.passe
        vu["rang_du_lot"] = passe.rang_du_lot_courant
        vu["lots"] = [(lot.nom, lot.cardinal) for lot in passe.lots]
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        return vu

    banc(app, scenario)

    assert len(feinte.jalons_emis) == 6, (
        f"trois suites de deux jalons ; recu {feinte.jalons_emis!r}")
    # La CONJONCTION des deux gardes -- voir le tableau du docstring. Ces quatre
    # assertions ne rougissent que si les deux tombent ensemble.
    assert vu["a_atteint"] is True, (
        "une troisieme suite ne doit pas faire reculer la barre ; elle s'est "
        f"arretee a {vu['faites']!r} sur {vu['total']!r}")
    assert (vu["faites"], vu["total"]) == (4, 4), (
        "la passe reste a DEUX lots de deux, la troisieme suite s'y ajoute "
        f"sans en creer un ; recu {vu['faites']!r} sur {vu['total']!r}")
    assert vu["rang_du_lot"] == 1, (
        "le rang reste borne au second lot ; recu "
        f"{vu['rang_du_lot']!r}")
    assert len(vu["lots"]) == 2, (
        f"deux lots declares, jamais un troisieme ; recu {vu['lots']!r}")


def test_le_formulaire_n_est_PAS_editable_pendant_que_la_passe_tourne(tmp_path,
                                                                      banc):
    """Ce que le montage precoce protege, et que le montage tardif ouvrait.

    `consigner` ne lit l'etiquette et le commentaire qu'a la FIN de la passe.
    Si `E3-9` reste au sommet pendant que le fil tourne, l'operateur peut y
    remonter et retaper : mesure de la revue de reprise, etiquette `alpha` a la
    validation, trois frappes pendant l'ingestion, et le coeur recoit
    `alphazzz`. **Le profil serait nomme par ce qui a ete tape APRES la
    validation.**

    Le banc joue les frappes par le pilote, pas par un appel direct a
    `traiter` : ce qui compte est qu'elles n'atteignent pas le formulaire.
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _CalibrationQuiTient(_CalibrationQuiJalonne):
        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            tenu.set()
            relache.wait(timeout=10)
            return super().__call__(
                project_dir, scan_path, dpi=dpi, logger=logger,
                demander_le_nom_et_le_commentaire=(
                    demander_le_nom_et_le_commentaire),
                confirmer_l_ecrasement=confirmer_l_ecrasement,
                rappel_progression=rappel_progression)

    feinte = _CalibrationQuiTient(pages=3)
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        formulaire = _formulaire(tmp_path)
        formulaire.etiquette = "alpha"
        parcours.consigner_le_profil(formulaire)
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        vu["sommet"] = type(pilote.app.screen).__name__
        # Trois frappes de navigation puis trois lettres, comme un operateur
        # qui se ravise pendant l'attente.
        for touche in ("up", "up", "up", "z", "z", "z"):
            await pilote.press(touche)
        vu["etiquette_apres_les_touches"] = formulaire.etiquette
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        return vu

    banc(app, scenario)
    assert vu["sommet"] != "EcranCalibrerLaChaine", (
        "le formulaire ne doit pas rester au sommet pendant la passe")
    assert vu["etiquette_apres_les_touches"] == "alpha", (
        "les frappes ne doivent pas atteindre le formulaire pendant la passe")
    assert feinte.nomme == ("alpha", ""), (
        "le coeur doit recevoir ce que l'operateur a VALIDE, pas ce qu'il "
        f"aurait tape ensuite ; recu {feinte.nomme!r}")


def test_ECHAP_pendant_l_INGESTION_ouvre_deja_l_interruption(tmp_path, banc):
    """AC 9.5 « pendant la passe », et non « a partir du premier jalon ».

    Avec le montage tardif, `Echap` etait inerte ET muet pendant toute
    l'ingestion : pile inchangee, ligne d'etat vide, et un
    `interruption_demandee` que rien ne lit puis qu'`oublier_la_tache` efface --
    exactement « une touche annoncee qui ne fait rien et ne dit rien », alors
    que le pied annonce `Echap menu Scan`.

    Le double tient la passe **avant** son premier jalon : c'est la fenetre
    d'ingestion, la plus longue sur un vrai scan.
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _CalibrationQuiTientAvantLesJalons(_CalibrationQuiJalonne):
        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            tenu.set()
            relache.wait(timeout=10)
            return super().__call__(
                project_dir, scan_path, dpi=dpi, logger=logger,
                demander_le_nom_et_le_commentaire=(
                    demander_le_nom_et_le_commentaire),
                confirmer_l_ecrasement=confirmer_l_ecrasement,
                rappel_progression=rappel_progression)

    feinte = _CalibrationQuiTientAvantLesJalons(pages=3)
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        vu["jalons_avant_echap"] = list(feinte.jalons_emis)
        await pilote.press("escape")
        await pilote.pause()
        vu["sommet"] = type(pilote.app.screen).__name__
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        return vu

    banc(app, scenario)
    assert vu["jalons_avant_echap"] == [], (
        "la fenetre visee est bien celle d'AVANT le premier jalon")
    assert vu["sommet"] == "EcranInterruption", (
        "`Echap` doit ouvrir l'interruption des le debut de la passe ; "
        f"sommet trouve : {vu['sommet']}")


# ---------------------------------------------------------------------------
# Les issues annoncees qui ne faisaient rien
# ---------------------------------------------------------------------------


def test_REVENIR_au_formulaire_depile_MEME_drapeau_pose(tmp_path, banc):
    """Mutant vise : rendre `action_remonter()` a `trancher_la_confirmation`.

    `action_remonter` est gardee par `tache_en_cours` : drapeau pose, l'issue
    « Revenir au formulaire » ne depilait **rien** et armait au passage
    `interruption_demandee`, que rien sur ce chemin ne lit. Le meme commit avait
    ecrit le motif du correctif huit methodes plus bas, dans `sortir_du_refus`,
    sans l'appliquer ici.

    **Le drapeau est pose expres** : c'est le seul regime ou le defaut mord, et
    un banc drapeau tombe serait vert sur les deux redactions.
    """
    app = _coque()
    parcours = _parcours(app, tmp_path, _CalibrationQuiJalonne())
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        confirmation = atelier_scan_calibrate.EcranCalibrationAConfirmer(
            _formulaire(tmp_path),
            sur_issue=lambda issue: parcours.trancher_la_confirmation(
                issue, _formulaire(tmp_path)))
        pilote.app.descendre(confirmation)
        await pilote.pause()
        vu["avant"] = list(pilote.app.screen_stack)
        # **Le drapeau, pose comme une passe voisine le poserait.**
        pilote.app.tache_en_cours = True
        confirmation.choix.viser(atelier_scan_calibrate.ISSUE_REVENIR)
        confirmation.valider()
        await pilote.pause()
        vu["apres"] = list(pilote.app.screen_stack)
        vu["interruption"] = pilote.app.interruption_demandee
        return vu

    banc(app, scenario)
    assert len(vu["apres"]) == len(vu["avant"]) - 1, (
        "« Revenir au formulaire » doit DEPILER, drapeau pose ou non")
    assert vu["apres"] == vu["avant"][:-1]
    assert vu["interruption"] is False, (
        "un choix explicite ne doit pas armer une demande d'interruption")


def test_RENOMMER_depile_MEME_drapeau_pose(tmp_path, banc):
    """Mutant vise : rendre `action_remonter()` a `sortir_du_refus`. SURVIVANT.

    C'est le correctif que le diff de la vague B mettait en avant, et il
    n'avait **aucun test** : le mutant survivait aux 183 tests cibles, y compris
    au banc qui s'annonce comme mesurant les deux issues de l'impasse. Ce banc-la
    emploie un double **lent**, c'est-a-dire le seul regime ou la course ne mord
    pas.
    """
    app = _coque()
    parcours = _parcours(app, tmp_path, _CalibrationQuiJalonne())
    vu = {}

    class _Passe:
        a_ecrit = False
        refus = "l'empreinte differenciante n'a pas separe les deux"
        motif = "AMBIGU"
        chemin = ""
        chaine = ""
        recalibration = False
        date_ecrite = ""
        date_precedente = ""

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        refus = atelier_scan_calibrate.EcranRefusDeCalibration(
            _Passe(), retenir=parcours.sortir_du_refus)
        pilote.app.descendre(refus)
        await pilote.pause()
        vu["avant"] = list(pilote.app.screen_stack)
        pilote.app.tache_en_cours = True
        parcours.sortir_du_refus(
            type("I", (), {"cle": atelier_scan_calibrate.CLE_RENOMMER})())
        await pilote.pause()
        vu["apres"] = list(pilote.app.screen_stack)
        return vu

    banc(app, scenario)
    assert vu["apres"] == vu["avant"][:-1], (
        "« Renommer l'etiquette et reprendre » doit depiler, drapeau pose")


def test_les_issues_d_INTERRUPTION_atteignent_l_atelier(tmp_path, banc):
    """AC 9.5 : « et n'est plus inerte ». Il l'etait aux **deux tiers**.

    Mutant vise : retirer `sur_issue=` du montage de l'ecran de passe.

    `EcranExecution.issue_d_interruption` traite « Reprendre » elle-meme et
    relaie les deux autres a `_sur_issue`. Monte sans rappel -- seul des trois
    sites du paquet --, « interrompre et garder » et « interrompre et effacer »
    (annoncee DESTRUCTIVE) ne faisaient rien : pile inchangee, pas un mot, et
    `interruption_demandee` restait faux.
    """
    app = _coque()
    ecran = None

    async def scenario(pilote):
        return atelier_scan_calibrate.ouvrir_la_calibration_en_cours(
            pilote.app)

    ecran = banc(app, scenario)
    assert ecran._sur_issue is not None, (
        "sans ce rappel l'ecran d'interruption est un cul-de-sac clavier")

    # Le geste, joue et non suppose : une issue qui n'est pas « Reprendre »
    # arme la demande d'interruption.
    app.interruption_demandee = False
    ecran.issue_d_interruption(
        type("I", (), {"cle": "garder"})())
    assert app.interruption_demandee is True


def test_le_depilement_ne_DEMONTE_pas_la_pile_quand_E3_9_n_y_est_pas(tmp_path,
                                                                     banc):
    """Mutant vise : retirer la garde `ecran in self.app.screen_stack`.

    Quand `ecran` n'est pas dans la pile -- `None` compris, et le meme attribut
    est garde contre `None` deux fois dans la meme classe --, la condition
    d'arret `self.app.screen is ecran` ne tombait jamais et le repli
    `len(stack) <= 1` **demontait toute la navigation**, puis `annoter_la_passe`
    levait un `AttributeError` dans le fil.
    """
    app = _coque()
    parcours = _parcours(app, tmp_path, _CalibrationQuiJalonne())
    vu = {}

    async def scenario(pilote):
        # Trois ecrans distinguables, la cible AU MILIEU : une pile a deux
        # etages ne distinguerait pas « depile jusqu'a » de « depile tout ».
        for nom in ("E3-0", "E3-9", "T6-1"):
            pilote.app.descendre(PalierTemoin(nom, PIED_DU_PALIER))
            await pilote.pause()
        vu["avant"] = len(pilote.app.screen_stack)
        pilote.app.tache_en_cours = True
        # `ecran` absent de la pile : le cas exact du defaut.
        parcours.conclure_la_passe(None, _PasseSansRefus())
        await pilote.pause()
        vu["apres"] = len(pilote.app.screen_stack)
        vu["tache"] = pilote.app.tache_en_cours
        return vu

    banc(app, scenario)
    assert vu["apres"] == vu["avant"], (
        "une cible absente de la pile ne doit RIEN depiler, et surtout pas "
        "toute la navigation")
    assert vu["tache"] is False, "le `finally` reste la moitie qui tient"


class _PasseSansRefus:
    a_ecrit = False
    refus = None
    motif = None
    chemin = ""
    chaine = ""
    recalibration = False
    date_ecrite = ""
    date_precedente = ""


# ---------------------------------------------------------------------------
# Le formulaire : ce qui est DESSINE, et pas seulement structure
# ---------------------------------------------------------------------------


def _sur_le_formulaire(tmp_path, banc, geste, *, ascii_seul: bool = False,
                       formulaire=None):
    """Jouer `geste(ecran)` **dans la boucle**, et n'en rendre que le resultat.

    Rendre l'ecran puis l'interroger apres coup leve `NoActiveAppError` : le
    rendu d'un `Palier` lit `self.app`, qui n'existe que sous le pilote. La
    mesure se prend donc la ou l'ecran vit.
    """
    app = _coque(ascii_seul=ascii_seul)

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            tmp_path, calibrer=lambda f: None)
        pilote.app.descendre(ecran)
        await pilote.pause()
        if formulaire is not None:
            ecran.formulaire = formulaire
        return geste(ecran)

    return banc(app, scenario)


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_la_ligne_VALIDER_est_DESSINEE_et_pas_seulement_atteignable(
        tmp_path, banc, ascii_seul):
    """Mutant vise : supprimer `corps += ["", ligne_de_champ(CHAMP_VALIDER)]`.
    SURVIVANT sur 1465 tests.

    `champs()` contient toujours `CHAMP_VALIDER`, `↓` y mene toujours, `⏎` y
    lance toujours -- mais la ligne n'etait **pas dessinee**, et l'operateur
    descendait sur une ligne invisible. Egan : « il faut qu'il y ait un choix
    explicite en bas du formulaire : Valider ». Ce choix n'a d'existence que
    visuelle, et rien ne le mesurait.

    Les deux regimes, parce que le repli ASCII est le seul ou la ligne pourrait
    disparaitre sans que l'autre le voie.
    """
    lignes = _sur_le_formulaire(tmp_path, banc, lambda e: e.lignes(),
                                ascii_seul=ascii_seul)
    portantes = [ligne for ligne in lignes
                 if atelier_scan_calibrate.LIBELLE_VALIDER in ligne]
    assert len(portantes) == 1, (
        "la ligne d'action doit etre dessinee une fois et une seule")
    assert atelier_scan_calibrate.ACTION_VALIDER in portantes[0], (
        "et elle doit dire ce qu'elle FAIT")
    # **La derniere ligne non vide du corps** : « en bas du formulaire ».
    non_vides = [ligne for ligne in lignes if ligne.strip()]
    assert non_vides[-1] == portantes[0].rstrip() or \
        non_vides[-1].strip() == portantes[0].strip()


def test_le_pied_ANNONCE_les_fleches_et_pas_seulement_PLUS_Tab(tmp_path,
                                                               banc):
    """Mutant vise : `"↑↓ champ  Échap menu Scan  F1 aide"` -> sans `↑↓ champ`.
    SURVIVANT sur 1465 tests.

    Le banc du lot mesurait un ensemble exact **du cote negatif seulement**
    (`portant_tab == set()`), alors que son propre nom promet la moitie
    positive. Or Egan a retire `Tab` **pour** mettre les fleches : la seule
    chose que l'operateur lit desormais pour savoir comment changer de champ
    est cette annonce.

    Le repli ASCII de cette ligne est mesure par `test_repli_ascii.py`, qui
    balaie les constantes du paquet ; ce banc-ci mesure ce qu'elle DIT.
    """
    pied = _sur_le_formulaire(tmp_path, banc, lambda e: e.raccourcis)
    # **Le geste ET son support.** « champ » seul serait vert sur un pied qui
    # nommerait le champ sans dire comment y aller ; les fleches seules
    # seraient vertes sur un pied qui les annoncerait pour autre chose.
    assert "champ" in pied, (
        f"le pied doit annoncer le geste de navigation ; recu {pied!r}")
    assert "↑↓" in pied, (
        f"le pied doit annoncer les FLECHES ; recu {pied!r}")
    # Et le volet negatif, conserve : `Tab` reste un synonyme NON annonce.
    assert "Tab" not in pied
    # **Les CINQ lignes contextuelles**, et pas seulement celle du curseur au
    # repos : le pied a ete multiplie par cinq, et une mesure prise dans un
    # seul etat de curseur laisse quatre lignes hors de portee.
    contextuelles = set(atelier_scan_calibrate.PIED_PAR_CHAMP.values())
    contextuelles.add(atelier_scan_calibrate.RACCOURCIS_CALIBRATE)
    assert len(contextuelles) == 5, (
        f"cinq lignes de pied distinctes attendues ; recu {contextuelles}")
    for ligne in contextuelles:
        assert "↑↓ champ" in ligne, (
            f"chaque ligne de pied doit annoncer la navigation ; {ligne!r}")
        assert "Tab" not in ligne


def test_ESPACE_sur_la_resolution_ne_fait_pas_passer_le_champ_pour_rempli(
        tmp_path, banc):
    """`Espace` est un reflexe que ce lot vient d'installer sur la ligne voisine.

    Frappe sur `Resolution de scan`, elle tombait sur `frapper(" ")` : `dpi`
    devenait `" "`, donc VRAI, et la ligne perdait **les deux** canaux qui
    disent « rien ici » -- le glyphe neutre et la mention `requis` -- pendant
    que `peut_calibrer` restait faux. Un champ requis qui se lit comme rempli.
    """
    def _geste(ecran):
        ecran.formulaire.champ = atelier_scan_calibrate.CHAMP_DPI
        ecran.traiter("space", " ")
        return {
            "peut": ecran.formulaire.peut_calibrer,
            "dpi_brut": ecran.formulaire.dpi,
            "mention": ecran.mention_du_champ(
                atelier_scan_calibrate.CHAMP_DPI),
            "ligne": ecran.ligne_de_champ(atelier_scan_calibrate.CHAMP_DPI,
                                          76),
        }

    vu = _sur_le_formulaire(tmp_path, banc, _geste,
                            formulaire=_formulaire(tmp_path, dpi=""))
    assert not vu["peut"]
    assert vu["mention"] == atelier_scan_calibrate.MENTION_REQUIS_DPI, (
        "la mention `requis` doit survivre a une frappe de blancs")
    assert atelier_scan_calibrate.MENTION_REQUIS_DPI in vu["ligne"]


def test_la_ligne_Valider_nomme_le_PREMIER_champ_requis_vide(tmp_path, banc):
    """`peut_calibrer` est faux pour DEUX motifs, la ligne n'en nommait qu'un.

    Sur un `E3-9` vierge, la mention disait « resolution requise » alors que la
    resolution n'etait meme pas en cause -- une mention qui nomme le mauvais
    manque envoie l'operateur corriger un champ qui va bien. Les deux regimes
    sont mesures, et leurs mentions doivent DIFFERER : deux constantes egales
    passeraient une assertion prise separement.
    """
    sans_dpi = _formulaire(tmp_path, dpi="")

    def _geste(ecran):
        vues = {"sans_scan": ecran.mention_du_champ(
            atelier_scan_calibrate.CHAMP_VALIDER)}
        ecran.formulaire = sans_dpi
        vues["sans_dpi"] = ecran.mention_du_champ(
            atelier_scan_calibrate.CHAMP_VALIDER)
        return vues

    vues = _sur_le_formulaire(
        tmp_path, banc, _geste,
        formulaire=_formulaire(tmp_path, scan=False, dpi="600"))
    mention_sans_scan, mention_sans_dpi = vues["sans_scan"], vues["sans_dpi"]

    assert mention_sans_scan == atelier_scan_calibrate.MENTION_VALIDER_SANS_SCAN
    assert mention_sans_dpi == atelier_scan_calibrate.MENTION_VALIDER_SANS_DPI
    assert mention_sans_scan != mention_sans_dpi, (
        "deux manques differents doivent se dire differemment")


def test_le_titre_de_la_CONFIRMATION_est_DESSINE(tmp_path, banc):
    """Mutant vise : `TITRE_DE_LA_CONFIRMATION = ""`. SURVIVANT sur 1465 tests.

    Les deux ecrans neufs du lot J2 -- la page de confirmation et l'ecran
    d'execution de la passe -- n'entrent dans aucun corpus de frontiere : ils
    echappent au repli ASCII, a la grille 80x24 et a la table des glyphes.
    Leur titre pouvait donc s'effacer sans qu'un test rougisse, alors que son
    propre docstring dit qu'il « porte la promesse que la page existe pour
    tenir : rien n'est encore ecrit ».
    """
    app = _coque()

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrationAConfirmer(
            _formulaire(tmp_path), sur_issue=lambda issue: None)
        pilote.app.descendre(ecran)
        await pilote.pause()
        return {"rendu": "\n".join([ecran.titre_du_cartouche()]
                                   + ecran.lignes_du_panneau()
                                   + ecran.rendu_des_issues()),
                "titre": ecran.titre}

    vu = banc(app, scenario)
    assert atelier_scan_calibrate.TITRE_DE_LA_CONFIRMATION.strip(), (
        "le titre du cartouche ne peut pas etre vide")
    assert atelier_scan_calibrate.TITRE_DE_LA_CONFIRMATION in vu["rendu"]
    # **Le bandeau porte DEUX segments**, comme les deux autres ecrans du geste.
    assert vu["titre"] == atelier_scan_calibrate.PALIER_DE_L_ECRAN


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_les_deux_ecrans_NEUFS_tiennent_le_plancher_80x24(tmp_path, banc,
                                                          ascii_seul):
    """Le corpus des frontieres s'arretait a six maquettes du temps 2.

    Les deux ecrans que le lot J2 ajoute au parcours n'y sont pas -- ils n'ont
    pas de maquette --, donc rien ne mesurait leur grille ni leur repli ASCII.
    Ce banc leur applique la meme regle.

    **La largeur se mesure sur la ligne BRUTE.** La premiere redaction mesurait
    `colonnes(ajuster(ligne, utile))`, or `ajuster` **tronque** avant de rendre :
    l'expression passe sur une ligne de 500 colonnes, dans les deux regimes. La
    moitie « largeur » de cette mesure ne pouvait pas rougir.
    """
    app = _coque(ascii_seul=ascii_seul)
    utile = jetons.largeur_utile(80)

    async def scenario(pilote):
        rendus = {}
        confirmation = atelier_scan_calibrate.EcranCalibrationAConfirmer(
            _formulaire(tmp_path), sur_issue=lambda issue: None)
        pilote.app.descendre(confirmation)
        await pilote.pause()
        rendus["confirmation"] = (
            [confirmation.titre_du_cartouche()]
            + confirmation.lignes_du_panneau()
            + confirmation.rendu_des_issues(),
            [confirmation.raccourcis])
        passe = atelier_scan_calibrate.ouvrir_la_calibration_en_cours(
            pilote.app)
        await pilote.pause()
        rendus["passe"] = ([passe.titre_tache], [passe.raccourcis])
        return rendus

    rendus = banc(app, scenario)
    for nom, (lignes, raccourcis) in rendus.items():
        assert len(lignes) <= 20, f"{nom} deborde les 24 lignes"
        for ligne in lignes + raccourcis:
            assert jetons.colonnes(ligne) <= utile, (
                f"{nom} deborde les {utile} colonnes utiles : {ligne!r}")
        if ascii_seul:
            # **Les GLYPHES replies, pas les accents.** Le repli du depot porte
            # sur la table de `jetons`, pas sur la langue : « Calibration de la
            # chaine » garde son accent circonflexe en mode ASCII, et c'est
            # voulu. Ce qui doit disparaitre, ce sont les caracteres de la
            # table UTF-8 -- et on les lit DANS la table plutot que de les
            # recopier, sans quoi un glyphe ajoute demain echapperait a cette
            # mesure.
            #
            # **Le corps seul, pas la ligne de raccourcis** : cette derniere est
            # une constante du module, repliee au dessin, et c'est
            # `test_repli_ascii.py` qui balaie les constantes du paquet.
            table_utf8 = {glyphe for glyphe in jetons.glyphes(False).values()
                          if glyphe and not glyphe.isascii()}
            assert table_utf8, "la table UTF-8 ne peut pas etre vide"
            for ligne in lignes:
                restants = {g for g in table_utf8 if g in ligne}
                assert restants == set(), (
                    f"{nom} garde des glyphes UTF-8 en repli : {restants} "
                    f"dans {ligne!r}")


# ---------------------------------------------------------------------------
# Second tour de revue -- ce que le premier correctif avait ouvert
# ---------------------------------------------------------------------------


def test_DEUX_passes_de_suite_montrent_chacune_leur_barre(tmp_path, banc):
    """Mutant vise : reutiliser l'ecran de la passe precedente.

    Sous ce mutant, **toute calibration apres la premiere dans une session ne
    montre plus rien** -- litteralement « RIEN n'indique qu'on a lance le
    processus », la panne d'origine. Aucun banc ne jouait deux passes
    completes ; le mutant survivait a 292 tests (revue de reprise, couche 1).

    Les deux passes sont jouees **entierement**, et le banc mesure que la
    seconde monte un ecran **distinct** : un `is not None` seul serait vert sur
    un produit qui garde le premier, demonte.
    """
    feinte = _CalibrationQuiJalonne(pages=3)
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        ecrans = []
        for rang in range(2):
            parcours.consigner_le_profil(_formulaire(tmp_path))
            await pilote.pause()
            pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
            pilote.app.screen.valider()
            assert await _tant_que(
                pilote, lambda: parcours.ecran_de_passe is not None), (
                    f"la passe {rang + 1} doit monter son ecran d'execution")
            ecrans.append(parcours.ecran_de_passe)
            await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
            await pilote.pause()
        vu["ecrans"] = ecrans
        vu["appels"] = len(feinte.appels)
        return vu

    banc(app, scenario)
    assert vu["appels"] == 2, "les deux passes doivent atteindre le coeur"
    premier, second = vu["ecrans"]
    assert premier is not None and second is not None
    assert premier is not second, (
        "la seconde passe doit monter SON ecran, pas reutiliser le premier "
        "-- lequel est demonte, donc invisible")


def test_ECHAP_pendant_la_passe_puis_fin_ramene_bien_sur_E3_9(tmp_path, banc):
    """Mutant vise : reduire la boucle de depilement a un seul `pop_screen()`.

    La boucle existe pour un cas que son propre commentaire nomme : l'ecran
    d'execution n'est plus le sommet des que l'operateur a appuye sur `Echap`
    pendant la passe -- ce que l'AC 9.5 rend precisement possible. Reduite a un
    seul `pop`, **aucun test ne rougissait** (mutant survivant sur 181 tests) :
    l'operateur restait devant la barre pleine avec `E3-9` annote cache dessous.

    Regle des fabriques transposee a la pile : il faut DEUX ecrans au-dessus de
    `E3-9` pour distinguer « depile jusqu'a » de « depile d'un cran ».
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _CalibrationQuiTient(_CalibrationQuiJalonne):
        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            rappel_progression(1, 3)
            tenu.set()
            relache.wait(timeout=10)
            return super().__call__(
                project_dir, scan_path, dpi=dpi, logger=logger,
                demander_le_nom_et_le_commentaire=(
                    demander_le_nom_et_le_commentaire),
                confirmer_l_ecrasement=confirmer_l_ecrasement,
                rappel_progression=rappel_progression)

    feinte = _CalibrationQuiTient(pages=3)
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        await pilote.press("escape")     # ouvre l'interruption PAR-DESSUS
        await pilote.pause()
        vu["hauteur_pendant"] = len(pilote.app.screen_stack)
        vu["sommet_pendant"] = type(pilote.app.screen).__name__
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        await pilote.pause()
        vu["sommet_final"] = type(pilote.app.screen).__name__
        # **`E3-9` est-il ENCORE dans la pile ?** C'est l'invariant que ce banc
        # protege, et il ne se lit plus au sommet depuis le 2026-09-06 : la
        # passe qui aboutit monte son ecran de resultat PAR-DESSUS `E3-9`, qui
        # reste dessous, annote. Mesurer le seul sommet confondrait « `E3-9` a
        # ete depile sous l'annonce » -- le defaut -- avec « un ecran de succes
        # a ete monte au-dessus » -- la correction.
        vu["E3-9 dans la pile"] = any(
            isinstance(ecran, atelier_scan_calibrate.EcranCalibrerLaChaine)
            for ecran in pilote.app.screen_stack)
        return vu

    banc(app, scenario)
    assert vu["sommet_pendant"] == "EcranInterruption"
    assert vu["hauteur_pendant"] >= 4, (
        "deux ecrans au-dessus de `E3-9` : c'est ce qui distingue « depile "
        "jusqu'a » de « depile d'un cran »")
    # **La fin de passe ne laisse PAS l'operateur devant une barre pleine**, et
    # c'est toujours ce qui est mesure. Ce qui a change est ou elle le mene :
    # sur l'ecran de succes (retour terrain d'Egan, 2026-09-06 : « pas d'ecran
    # de succes et on revient directement a la page pour lancer une
    # calibration. Incoherent avec le reste »), avec `E3-9` annote dessous.
    assert vu["sommet_final"] == "EcranCalibrationEcrite", (
        "la fin de passe doit mener a l'ecran de succes, pas laisser "
        f"l'operateur devant une barre pleine ; recu {vu['sommet_final']}")
    assert vu["E3-9 dans la pile"] is True, (
        "`E3-9` a ete depile sous l'annonce : c'est le defaut d'origine, et "
        "l'ecran de succes ne le remplace pas, il se pose dessus")


def test_l_issue_d_interruption_DEPILE_sa_question_et_DIT_ce_qui_se_passe(
        tmp_path, banc):
    """Poser le drapeau ne suffisait pas : vu de l'operateur, rien ne bougeait.

    Le calque d'`atelier_scan_detection._interrompre` se contente d'armer un
    drapeau parce que la detection, elle, le **consulte** et conclut. Ici
    personne ne le consulte : l'ecran d'interruption restait au sommet, rien
    n'etait dit, et il fallait un second `Echap` pour sortir -- c'est-a-dire le
    regime que le rappel etait cense fermer (revue de reprise, couche 2).

    Le banc passe par le VRAI chemin : `Echap`, puis l'issue retenue sur
    l'`EcranInterruption` monte. La premiere redaction lisait l'attribut prive
    `_sur_issue` et appelait la couture a la main avec un objet fabrique.
    """
    tenu = threading.Event()
    relache = threading.Event()

    class _CalibrationQuiTient(_CalibrationQuiJalonne):
        def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                     demander_le_nom_et_le_commentaire=None,
                     confirmer_l_ecrasement=None, rappel_progression=None):
            rappel_progression(1, 3)
            tenu.set()
            relache.wait(timeout=10)
            return super().__call__(
                project_dir, scan_path, dpi=dpi, logger=logger,
                demander_le_nom_et_le_commentaire=(
                    demander_le_nom_et_le_commentaire),
                confirmer_l_ecrasement=confirmer_l_ecrasement,
                rappel_progression=rappel_progression)

    feinte = _CalibrationQuiTient(pages=3)
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    vu = {}

    async def scenario(pilote):
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            parcours.dossier_projet, calibrer=parcours.consigner_le_profil)
        pilote.app.descendre(ecran)
        await pilote.pause()
        parcours.ecran_de_calibration = ecran
        parcours.consigner_le_profil(_formulaire(tmp_path))
        await pilote.pause()
        pilote.app.screen.choix.viser(atelier_scan_calibrate.ISSUE_LANCER)
        pilote.app.screen.valider()
        assert await _tant_que(pilote, tenu.is_set)
        await pilote.pause()
        await pilote.press("escape")
        await pilote.pause()
        interruption = pilote.app.screen
        assert type(interruption).__name__ == "EcranInterruption"
        # L'issue destructive, celle qui etait annoncee et inerte.
        interruption.choix.viser("effacer")
        interruption.valider()
        await pilote.pause()
        vu["sommet_apres"] = type(pilote.app.screen).__name__
        vu["interruption_demandee"] = pilote.app.interruption_demandee
        vu["journal"] = list(
            parcours.ecran_de_passe.surface.journal.lignes)
        relache.set()
        await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
        return vu

    banc(app, scenario)
    assert vu["interruption_demandee"] is True, "la demande est enregistree"
    assert vu["sommet_apres"] != "EcranInterruption", (
        "la question a laquelle l'operateur vient de repondre doit etre "
        "consommee, pas laissee au sommet")
    # **Au journal**, qui garde la trace : la ligne d'etat porte l'avancement
    # et se fait reecrire au jalon suivant.
    assert atelier_scan_calibrate.PHRASE_ARRET_SANS_POINT_D_ARRET in (
        vu["journal"]), (
        "l'ecran doit DIRE ce qui se passe : une issue qui pose un drapeau en "
        f"silence est indistinguable d'un clavier casse ; recu {vu['journal']!r}")


def test_la_phrase_d_arret_DIT_les_deux_choses_qu_elle_promet(tmp_path, banc):
    """Mutant vise : vider `PHRASE_ARRET_SANS_POINT_D_ARRET`. SURVIVANT.

    **Le banc voisin est tautologique sur le contenu, et il faut le dire.**
    `..._DEPILE_sa_question_et_DIT_ce_qui_se_passe` asserte
    `PHRASE_ARRET_SANS_POINT_D_ARRET in journal` -- la constante des deux
    cotes. Elle bouge, l'assertion bouge avec elle : la phrase peut devenir
    `""` et le banc reste vert, pendant que le journal recoit une ligne vide et
    que l'operateur voit exactement ce que l'AC 9.5 existe pour empecher, « une
    issue qui pose un drapeau en silence ». C'est la famille du test
    tautologique de la story 5.9, portant la sur la constante centrale de la
    calibration.

    Ce banc mesure donc le **contenu**, une fois, la ou le voisin mesure le
    **cablage**. Il n'asserte pas la phrase mot pour mot -- ce serait un
    detecteur de changement, et la formulation appartient aux maquettes -- mais
    les deux faits qu'elle doit porter, et que son propre docstring nomme :

    * l'arret est **enregistre** (« arrêt demandé ») -- sans quoi l'operateur
      ne sait pas que sa touche a compte ;
    * la passe **va jusqu'a son terme** -- sans quoi il attend un arret qui ne
      viendra pas, ce que l'absence de point d'arret dans `calibrer_la_chaine`
      rend impossible et qui reste au registre.
    """
    phrase = atelier_scan_calibrate.PHRASE_ARRET_SANS_POINT_D_ARRET

    assert phrase.strip(), (
        "une phrase vide inscrite au journal est un silence, et le silence "
        "sur une touche annoncee est le defaut meme que l'AC 9.5 ferme")
    minuscules = phrase.lower()
    assert "arr" in minuscules and "demand" in minuscules, (
        "la phrase doit dire que l'arret est ENREGISTRE, sans quoi la touche "
        f"reste indistinguable d'un clavier casse ; recue {phrase!r}")
    assert "terme" in minuscules, (
        "et qu'il n'aura pas lieu tout de suite -- la passe va jusqu'a son "
        f"terme, faute de point d'arret dans le coeur ; recue {phrase!r}")


def test_le_demontage_n_eteint_que_le_drapeau_de_SA_passe(tmp_path, banc):
    """Mutant vise : rendre l'extinction d'`on_unmount` inconditionnelle.

    `on_unmount` est **differe** lui aussi. Demonter l'ecran d'une passe finie
    puis lancer la suivante dans le meme tour de boucle faisait tomber le
    drapeau de la passe NEUVE : fil vivant, garde de re-entrance desarmee, et
    « deux ingestions, deux ecritures de profil » -- le risque que le docstring
    de `lancer_la_passe_de_calibration` nomme lui-meme. C'est le symetrique
    exact du defaut que cette classe ferme (revue de reprise, couches 1 et 2).

    Le banc reproduit l'ordre : on demonte l'ecran de la premiere passe, on
    pose le drapeau d'une seconde, **puis** on laisse la boucle tourner.
    """
    app = _coque()
    vu = {}

    async def scenario(pilote):
        premier = atelier_scan_calibrate.ouvrir_la_calibration_en_cours(
            pilote.app)
        await pilote.pause()
        pilote.app.pop_screen()          # `Unmount` poste, pas encore traite
        # La passe suivante part dans le meme tour : elle pose son drapeau et
        # monte son propre ecran.
        pilote.app.tache_en_cours = True
        second = atelier_scan_calibrate.ouvrir_la_calibration_en_cours(
            pilote.app)
        await pilote.pause()
        await pilote.pause()
        vu["premier"], vu["second"] = premier, second
        vu["tache"] = pilote.app.tache_en_cours
        return vu

    banc(app, scenario)
    assert vu["premier"] is not vu["second"]
    assert vu["tache"] is True, (
        "le demontage de l'ecran d'une passe finie ne doit pas eteindre le "
        "drapeau d'une passe qui vient de partir")


def test_un_champ_de_BLANCS_dit_vide_sur_LES_TROIS_surfaces(tmp_path, banc):
    """Une seule lecture de « ce champ est-il vide ? », et elle est mesuree.

    La premiere redaction ne strippait que la VALEUR dessinee : une etiquette
    de blancs affichait alors le glyphe neutre -- qui signifie vide -- pendant
    que sa mention disparaissait, et le coeur recevait `'   '` comme nom de
    chaine, ecrit tel quel dans le document de profil. Les deux canaux de
    l'ecran se contredisaient (revue de reprise, trouve par les trois couches).

    Les **trois** surfaces sont mesurees ensemble : la valeur, la mention, et ce
    qui part au coeur. Deux d'entre elles seraient vertes sur la redaction
    fautive.
    """
    def _geste(ecran):
        ecran.formulaire.etiquette = "   "
        ecran.formulaire.commentaire = "  "
        return {
            "valeur_etiquette": ecran.valeur_du_champ(
                atelier_scan_calibrate.CHAMP_ETIQUETTE),
            "mention_etiquette": ecran.mention_du_champ(
                atelier_scan_calibrate.CHAMP_ETIQUETTE),
            "mention_commentaire": ecran.mention_du_champ(
                atelier_scan_calibrate.CHAMP_COMMENTAIRE),
            "saisie_etiquette": ecran.formulaire.saisie(
                atelier_scan_calibrate.CHAMP_ETIQUETTE),
        }

    vu = _sur_le_formulaire(tmp_path, banc, _geste,
                            formulaire=_formulaire(tmp_path))
    assert vu["saisie_etiquette"] == ""
    assert vu["mention_etiquette"] == (
        atelier_scan_calibrate.MENTION_ETIQUETTE_VIDE), (
        "la mention qui dit ce qui se passera doit rester quand le champ est "
        "vide -- des blancs ne le remplissent pas")
    assert vu["mention_commentaire"] == (
        atelier_scan_calibrate.MENTION_COMMENTAIRE)

    # **Et le coeur recoit vide**, ce qui est la troisieme surface : sans elle,
    # le document de profil portait `label: '   '` pendant que l'ecran affichait
    # le glyphe neutre.
    formulaire = _formulaire(tmp_path)
    formulaire.etiquette = "   "
    formulaire.commentaire = "  "
    recu = {}

    def _calibrer(dossier, scan, *, dpi, logger=None,
                  demander_le_nom_et_le_commentaire=None,
                  confirmer_l_ecrasement=None, rappel_progression=None):
        recu["nomme"] = demander_le_nom_et_le_commentaire("900-png-aaaa")
        raise scan_calibrate.RefusDeCalibration("arret du banc",
                                                motif="PAS_DE_MIRE")

    atelier_scan_calibrate.consigner(
        tmp_path, formulaire, poser_la_collision=lambda c: "annuler",
        calibrer=_calibrer)
    assert recu["nomme"] == ("", ""), (
        f"ce que l'ecran dit vide doit partir vide ; recu {recu['nomme']!r}")


def test_le_motif_du_refus_de_partir_a_TROIS_regimes_et_non_deux(tmp_path,
                                                                 banc):
    """`peut_calibrer` est faux pour trois raisons ; la mention n'en nommait
    que deux.

    Le troisieme est un dpi **present mais invalide** : l'ecran affichait
    « resolution requise » avec `999999` ecrit dans le champ, c'est-a-dire son
    propre argument retourne -- « une mention qui nomme le mauvais manque
    envoie l'operateur corriger un champ qui va bien ».

    Les trois mentions doivent **differer deux a deux** : deux constantes egales
    passeraient une assertion prise regime par regime.
    """
    def _geste(ecran):
        vues = {}
        for nom, scan, dpi in (("sans_scan", False, "600"),
                               ("sans_dpi", True, ""),
                               ("dpi_refuse", True, "999999")):
            ecran.formulaire = _formulaire(tmp_path, scan=scan, dpi=dpi)
            assert not ecran.formulaire.peut_calibrer, nom
            vues[nom] = ecran.mention_du_champ(
                atelier_scan_calibrate.CHAMP_VALIDER)
        return vues

    vues = _sur_le_formulaire(tmp_path, banc, _geste)
    assert vues["sans_scan"] == atelier_scan_calibrate.MENTION_VALIDER_SANS_SCAN
    assert vues["sans_dpi"] == atelier_scan_calibrate.MENTION_VALIDER_SANS_DPI
    assert vues["dpi_refuse"] == (
        atelier_scan_calibrate.MENTION_VALIDER_DPI_REFUSE)
    assert len(set(vues.values())) == 3, (
        f"trois manques differents, trois mentions differentes ; recu {vues}")


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E3-0` et `E3-9` -- il
# nomme meme `E3-0` comme etage d'une pile de trois -- et n'ouvrait aucun
# dessin : le pied de ses paliers temoins en etait recopie a la main.

#: Les dessins repris ici, a leur source.
MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
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


def test_le_PIED_des_paliers_temoins_est_celui_des_MENUS_dessines():
    """`Q quitter` est le pied d'un MENU, pas d'un ecran de travail.

    Ce banc empile deux temoins -- « Projet » et « Ateliers » -- puis des
    ecrans par-dessus. La mesure distingue les deux natures, sur trois
    dessins qui ne repondent pas pareil :

    * `E1-1`, le menu des ateliers, dessine le pied : c'est la source du
      temoin « Ateliers » ;
    * `E3-0`, le menu de l'atelier Scan, le dessine aussi : c'est l'etage que
      la pile de trois nomme en premier ;
    * `E3-9`, le formulaire de calibration, ne le dessine PAS -- son pied
      s'arrete a `Échap menu Scan`. Un ecran de travail n'offre pas la sortie
      directe que son palier offre, et c'est exactement ce que cette pile
      met en scene.
    """
    ateliers = dessin_de_la_maquette("E1-1-menu-ateliers.txt")
    menu_scan = dessin_de_la_maquette("E3-0-scan-menu.txt")
    formulaire = dessin_de_la_maquette("E3-9-scan-calibrate.txt")

    assert PIED_DU_PALIER in ateliers
    assert PIED_DU_PALIER in menu_scan
    assert PIED_DU_PALIER not in formulaire


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative -- et elle a mordu sur MOI avant de mordre ailleurs.

    Sa premiere redaction affirmait que `T6-1`, le troisieme etage de la pile
    de ce banc, « n'a pas de dessin du tout ». C'etait faux :
    `T6-1-interruption.txt` existe, et l'assertion a fait rougir la
    confrontation dans l'heure. C'est precisement ce a quoi sert une frontiere
    negative -- attraper une affirmation invente, y compris celle de son
    auteur -- alors qu'une relecture aurait laisse passer la phrase.

    Ce que le dessin dit vraiment est plus interessant : `T6-1` est un
    PANNEAU d'interruption, pas un palier, et son pied ne porte donc PAS
    `Q quitter` -- il s'arrete a `Échap reprendre l'écriture`. Les trois
    etages de la pile se repartissent ainsi en deux paliers qui offrent la
    sortie et un panneau qui ne l'offre pas, ce qui est exactement ce que la
    pile met en scene.
    """
    menu_scan = dessin_de_la_maquette("E3-0-scan-menu.txt")
    assert PIED_DU_PALIER + " et revenir" not in menu_scan
    assert "Q fermer" not in menu_scan

    interruption = dessin_de_la_maquette("T6-1-interruption.txt")
    assert PIED_DU_PALIER not in interruption
    assert "Échap reprendre l'écriture" in interruption
