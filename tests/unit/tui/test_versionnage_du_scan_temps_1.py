# -*- coding: utf-8 -*-
"""Story 11.4e, lot E -- le **temps 1** du Scan offre la seconde issue d'`ARB-89`.

Le fait que ce banc ferme
-------------------------
Le temps 1 (`E3-2`) appelle `scan_detect.run_scan_detect`. Quand la pile visee
a **deja ete ingeree sous ce nom**, le coeur refuse -- « L'ingestion n'ecrase
pas un lot existant: la copie fait foi et peut etre la seule trace restante du
scan » (`scan_ingest._refuse_destructive_overwrite`) -- et la TUI ne savait
rendre qu'un `EcranRefus` : **une seule issue, qui remonte au menu**. C'est
litteralement le blocage sec qu'`EPIC11-ARB-89` interdit (« toujours permettre
une reecriture plutot qu'un blocage sec ») sur le scenario qui a fonde
`EPIC11-ARB-104` (« On me dit que le scan existe deja ! Pourtant j'ai modifie
quelque chose. »).

Le lot D de la meme story rend `scan detect --nouvelle-version` effectif en
ligne de commande ; celui-ci le rend **atteignable a l'ecran**.

Ce banc a un fichier a lui, et ce n'est pas de la coquetterie
--------------------------------------------------------------
`tests/unit/tui/test_versionnage_du_scan_en_tui.py` est le banc du lot du
2026-09-01 (`828de0d`), qui a cable la meme seconde issue sur le **temps 2**
(`E3-6`). « Quand un decoupage en lots fait converger deux agents vers un meme
banc, c'est le decoupage qu'il faut changer » (`CLAUDE.md`) : deux lots, deux
bancs.

Les quatre familles mesurees ici
--------------------------------
1. **E1** -- le drapeau `nouvelle_version` sur `DemandeDeDetection` et son
   trajet jusqu'au coeur, mesure a l'**ensemble EXACT** des mots-cles (une
   assertion positive laisserait passer toute divergence supplementaire) ;
2. **E2** -- l'ecran a **deux** issues sur le refus de conflit, **et lui
   seul**. Le volet symetrique est le vrai livrable : sans lui, l'AC est vraie
   par vacuite et rien n'empeche d'ajouter des issues partout. On mesure donc
   l'**ensemble exact** des refus qui montent le point de jugement, refus de
   dpi / chemin introuvable / lot ambigu compris ;
3. **E3** -- la ligne de cartouche **chiffree** (`EPIC11-ARB-4` : une issue
   neuve sans chiffre n'en est pas), et son volet symetrique : elle ne parait
   **qu'avec** l'issue ;
4. **la grille** -- 80x24, dans les deux regimes de glyphes. Le repli ASCII
   contraint la largeur, et une ligne qui tient en Unicode peut deborder en
   ASCII.

Regle des fabriques, appliquee sur la liste que le CODE parcourt
----------------------------------------------------------------
Le releve du dossier de lot **boucle** sur les entrees de `scans/` et sur les
fichiers du lot vise. Il y a donc **trois** lots de scan distinguables et
**trois** pages distinguables, et la cible est au **milieu** de l'ordre
reellement parcouru (`sorted(...)`), ni premiere ni derniere -- une cible en
seconde position d'une liste de deux est aussi en derniere, et les deux formes
y sont indiscernables (`CLAUDE.md`, point 2 bis).

Ce que ce banc ne mesure pas, dit plutot que tu
------------------------------------------------
Il ne mesure **pas** le rang de version qui sera pris : l'AC 5.5 le demandait a
l'ecran, et la frontiere negative livree par `828de0d`
(`test_versionnage_du_scan_en_tui.py::test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG`)
interdit `resolve_scan_version_rank` dans `tui/` **prose comprise**. Les deux
sont incompatibles ; c'est la frontiere qui gagne, pour le motif qu'`828de0d`
avait deja ecrit -- « l'annoncer avant l'appel serait une seconde regle de rang
en TUI ». Le cartouche chiffre donc ce qui **existe** (le lot occupe et le
nombre de pages qu'il porte), qui est mesurable sans rien resoudre.
"""

from __future__ import annotations

import ast
import logging
import sys
from pathlib import Path

import pytest

_TESTS_UNIT = Path(__file__).resolve().parents[1]
if str(_TESTS_UNIT) not in sys.path:
    sys.path.insert(0, str(_TESTS_UNIT))

from mixed_media_utility import scan_detect, scan_ingest  # noqa: E402
from mixed_media_utility.io import project_layout  # noqa: E402
from mixed_media_utility.tui import atelier_scan_detection as atelier  # noqa: E402
from mixed_media_utility.tui import jetons  # noqa: E402
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin  # noqa: E402
from mixed_media_utility.tui.execution import EcranRefus  # noqa: E402

_SRC = Path(__file__).resolve().parents[3] / "src"

#: Le module mesure par les frontieres a l'AST.
MODULE_DE_LA_DETECTION = _SRC / "mixed_media_utility" / "tui" / "atelier_scan_detection.py"


# ---------------------------------------------------------------------------
# Fabriques -- TROIS lots de scan, TROIS pages, la cible au MILIEU
# ---------------------------------------------------------------------------

#: Les trois lots deposes sous `scans/`, **distinguables par leur nom ET par
#: leur contenu**. Un remplissage uniforme cacherait une permutation (`M33` de
#: la story 5.6). L'ordre est celui que `sorted()` parcourt, et la cible est le
#: **second des trois** : ni premiere (ce qui masquerait un `find` fautif qui
#: rend toujours le premier), ni derniere (ce qui masquerait une terminaison de
#: boucle fautive).
LOTS_DE_SCAN = ("planches-a", "planches-b-cible", "planches-c")

#: Le lot vise. Il est au **milieu** de :data:`LOTS_DE_SCAN`.
LOT_CIBLE = LOTS_DE_SCAN[1]

#: Les trois pages du lot cible, distinguables par leur nom et par leurs
#: octets. Le comptage **boucle** dessus : trois, et non une.
PAGES_DU_LOT_CIBLE = (
    ("page_001.tiff", b"page 1 -- premiere du lot cible\n"),
    ("page_002.tiff", b"page 2 -- au milieu, et c'est la cible du comptage\n"),
    ("page_003.tiff", b"page 3 -- derniere du lot cible\n"),
)

#: Ce que les deux autres lots portent : **un** fichier chacun, et un cardinal
#: different de trois. Un comptage qui viserait le mauvais lot rendrait 1, pas
#: 3, et se verrait.
PAGES_DES_AUTRES_LOTS = 1


def coque(**kwargs) -> CoqueTui:
    """Une coque a deux paliers temoins : l'ecran projet et le menu ateliers.

    Deux et non un : le retour au menu des ateliers (`EPIC11-ARB-13`) ne se
    distingue d'un retour a la racine que si la racine existe a cote.
    """
    return CoqueTui(paliers=[PalierTemoin("Projet", "⏎ ouvrir   Q quitter"),
                             PalierTemoin("Ateliers", "⏎ entrer   Q quitter")],
                    contexte=Contexte("projet_demo"), **kwargs)


def projet_avec_trois_lots(tmp_path: Path, nom: str = "projet") -> Path:
    """Un projet reel dont `scans/` porte **trois** lots, la cible au milieu.

    Le dossier est peuple **avant** la passe : mesurer l'absence d'ecriture
    dans un dossier vide ne mesure presque rien -- un dossier vide reste vide
    par accident aussi bien que par contrat.
    """
    projet = tmp_path / nom
    project_layout.ensure_project_layout(projet)
    scans = projet / project_layout.SCANS_DIRNAME
    for rang, lot in enumerate(LOTS_DE_SCAN):
        dossier = scans / lot
        dossier.mkdir(parents=True, exist_ok=True)
        if lot == LOT_CIBLE:
            for nom_page, octets in PAGES_DU_LOT_CIBLE:
                (dossier / nom_page).write_bytes(octets)
        else:
            (dossier / f"unique_{rang}.tiff").write_bytes(
                f"lot {lot} -- une seule page\n".encode("utf-8"))
    return projet


def source_du_lot_cible(tmp_path: Path) -> Path:
    """Le dossier que l'operateur redepose : il porte le **nom de la cible**.

    C'est ce qui fait que `scan_ingest.slug_par_defaut` rend le slug du lot
    deja present -- le geste exact du scenario d'Egan : on rescanne la meme
    planche apres y avoir ajoute un point rouge.
    """
    dossier = tmp_path / "a-reingerer" / LOT_CIBLE
    dossier.mkdir(parents=True, exist_ok=True)
    for nom_page, octets in PAGES_DU_LOT_CIBLE:
        (dossier / nom_page).write_bytes(octets + b"avec le point rouge\n")
    return dossier


def demande(projet: Path, source, *, dpi=1200, ingest_slug=None,
            nouvelle_version=False):
    return atelier.DemandeDeDetection(
        dossier_projet=projet, source=source, dpi=dpi,
        ingest_slug=ingest_slug, nouvelle_version=nouvelle_version)


class CoeurEspion:
    """Un `run_scan_detect` de banc qui **capte l'appel entier**.

    Il accepte `*args, **kwargs` **a dessein**, et c'est le seul double du banc
    qui le fait : la mesure porte sur l'**ensemble exact** des mots-cles
    transmis, et un double a signature figee leverait un `TypeError` au lieu de
    rendre l'ensemble a comparer -- il mesurerait alors la signature du double,
    pas celle de l'appel.
    """

    def __init__(self, *, leve=None, issue=None) -> None:
        self.leve = leve
        self.issue = issue
        self.appels: list[tuple[tuple, dict]] = []

    def __call__(self, *args, **kwargs):
        self.appels.append((args, dict(kwargs)))
        if self.leve is not None:
            raise self.leve
        return self.issue


def issue_factice():
    """Un `ScanDetectOutcome` **reel**, pas un double a attributs libres."""
    return scan_detect.ScanDetectOutcome(
        report=object(), rapport_d_ingestion=Path("ingest.json"),
        documents=(), pages_identifiees=0)


def photographie(racine: Path) -> dict[str, tuple]:
    """L'etat du sous-arbre, **aux inodes et au `st_mtime_ns`**.

    **Jamais un condensat** : une reecriture d'un contenu deterministe rend les
    memes octets, donc le meme condensat, et la mesure serait verte a tort
    (`EPIC11-ARB-83`). `lstat` et non `stat` : un lien symbolique substitue a
    un fichier est une ecriture, et la suivre la rendrait invisible.
    """
    photo: dict[str, tuple] = {}
    for chemin in [racine] + sorted(racine.rglob("*")):
        etat = chemin.lstat()
        cle = "." if chemin == racine else str(chemin.relative_to(racine))
        photo[cle] = (chemin.is_dir(), etat.st_ino, etat.st_mtime_ns,
                      etat.st_size)
    return photo


def divergences(avant: dict[str, tuple], apres: dict[str, tuple]) -> set[str]:
    """L'ensemble **exact** des chemins qui ont bouge -- ajouts et retraits compris."""
    return {cle for cle in set(avant) | set(apres)
            if avant.get(cle) != apres.get(cle)}


def conclure(app, ecran, une_demande, coeur, *, sur_rapport=None):
    """Un tour complet de `executer_et_conclure`, avec le coeur donne."""
    return atelier.executer_et_conclure(
        app, ecran, une_demande, logger=logging.getLogger("banc-lotE"),
        detection=coeur, sur_rapport=sur_rapport or (lambda _r: None))


def jouer(une_demande, coeur, *, sur_rapport=None, apres=None,
          ascii_seul=False):
    """Monter `E3-2` depuis le menu des ateliers, tourner, rendre ce qu'on voit.

    **On part du menu des ateliers, comme le produit** : mesurer le retour
    depuis la racine ne distinguerait pas `revenir_aux_ateliers` d'un simple
    depilement.

    Les **lignes** sont relevees pendant que l'application est montee : une
    fois le gestionnaire de contexte referme, l'arbre de widgets n'existe plus
    et `lignes()` leve `NoActiveAppError` -- une assertion posee apres coup ne
    mesurerait rien.
    """
    vu: dict = {}

    async def scenario(pilote):
        app = pilote.app
        app.descendre()
        await pilote.pause()
        ecran = atelier.ouvrir_la_detection(app)
        await pilote.pause()
        conclure(app, ecran, une_demande, coeur, sur_rapport=sur_rapport)
        await pilote.pause()
        vu["nom"] = type(app.screen).__name__
        vu["ecran"] = app.screen
        # Les ecrans du paquet ne portent pas tous `lignes()` : `E3-2` reste
        # monte quand la passe aboutit, et il peint par un autre chemin.
        rendu = getattr(app.screen, "lignes", None)
        vu["lignes"] = list(rendu()) if callable(rendu) else []
        vu["rang_du_curseur"] = getattr(app.screen, "rang_du_curseur",
                                        lambda: None)()
        if apres is not None:
            vu["apres"] = apres(app)
            await pilote.pause()
            vu["nom_final"] = type(app.screen).__name__
            vu["rang_final"] = app.rang
        return vu

    from conftest import piloter
    return piloter(coque(ascii_seul=ascii_seul), scenario)


# ===========================================================================
# E1 -- le drapeau et son trajet jusqu'au coeur
# ===========================================================================

def test_la_demande_porte_le_drapeau_et_il_vaut_FAUX_par_defaut():
    """AC 5.1, premiere moitie. Le defaut est le comportement d'aujourd'hui.

    Un drapeau dont le defaut serait `True` versionnerait toute passe, ce qui
    est l'inverse exact de l'arbitrage : le versionnage est une **issue
    retenue**, jamais un regime.
    """
    nue = atelier.DemandeDeDetection(dossier_projet=Path("p"), source="s",
                                     dpi=1200)
    assert nue.nouvelle_version is False


def test_l_ensemble_EXACT_des_mots_cles_transmis_au_coeur(tmp_path):
    """AC 5.1 : l'ensemble **exact**, pas l'inclusion.

    « Une assertion positive laisse passer toute divergence supplementaire »
    (`CLAUDE.md`) : « `nouvelle_version` est passe » ne mesure rien, « les
    mots-cles transmis sont **exactement** ceux-ci » mesure la chose ET son
    unicite -- donc aussi qu'aucun mot-cle n'a ete perdu en chemin.
    """
    coeur = CoeurEspion(issue=issue_factice())
    projet = tmp_path / "projet"
    source = tmp_path / "source"
    jouer(demande(projet, source), coeur)

    assert len(coeur.appels) == 1, coeur.appels
    args, kwargs = coeur.appels[0]
    # `adopter` s'ajoute avec le lot d'`EPIC11-ARB-267` (2026-09-07) : le
    # temps 1 porte l'adoption d'une planche etrangere, et le drapeau traverse
    # jusqu'au coeur comme `nouvelle_version` avant lui. L'ensemble reste
    # mesure EXACTEMENT, et il se met a jour dans le commit qui l'ajoute.
    assert set(kwargs) == {"dpi", "ingest_slug", "logger",
                           "rappel_progression", "nouvelle_version",
                           "adopter"}, kwargs
    # Les deux positionnels sont le projet et la source, **telle quelle**.
    assert args == (projet, source)


@pytest.mark.parametrize("valeur", [False, True])
def test_le_drapeau_VOYAGE_A_SA_VALEUR_et_n_est_pas_recalcule(valeur, tmp_path):
    """Les **deux** regimes. Un seul serait vert sur une constante cablee."""
    coeur = CoeurEspion(issue=issue_factice())
    jouer(demande(tmp_path / "projet", tmp_path / "source",
                  nouvelle_version=valeur), coeur)
    _args, kwargs = coeur.appels[0]
    assert kwargs["nouvelle_version"] is valeur


def test_le_drapeau_TRAVERSE_sans_etre_interprete():
    """Frontiere a l'AST : dans `detecter`, le mot-cle vient de la **demande**.

    Mesure a l'AST plutot qu'au texte : ce qui compte est que le mot-cle
    `nouvelle_version=` de l'appel au coeur soit alimente par l'attribut de la
    demande, et non par une expression qui le recalculerait -- une regle de
    versionnage ecrite en TUI est exactement ce qu'`EPIC11-ARB-108` interdit.
    """
    arbre = ast.parse(MODULE_DE_LA_DETECTION.read_text(encoding="utf-8"))
    corps = [noeud for noeud in ast.walk(arbre)
             if isinstance(noeud, ast.FunctionDef) and noeud.name == "detecter"]
    assert len(corps) == 1, "il n'y a qu'une fonction `detecter`"
    passages = [ast.dump(mot.value)
                for noeud in ast.walk(corps[0])
                if isinstance(noeud, ast.Call)
                for mot in noeud.keywords
                if mot.arg == "nouvelle_version"]
    assert passages == [ast.dump(ast.parse("demande.nouvelle_version",
                                           mode="eval").body)], passages


# ===========================================================================
# E2 -- l'ecran a DEUX issues sur le conflit, et LUI SEUL
# ===========================================================================

def refus_du_conflit(projet: Path) -> scan_ingest.UnsupportedScanInputError:
    """Le refus **verbatim** du coeur sur un lot deja ingere.

    Il est leve par le vrai `_refuse_destructive_overwrite` plutot que redige
    ici : une phrase recopiee divergerait au premier ajustement du coeur, et le
    banc mesurerait alors un refus que le produit ne leve plus.
    """
    return scan_ingest.UnsupportedScanInputError(
        f"Le lot '{LOT_CIBLE}' contient deja 3 fichier(s) de meme nom mais de "
        "contenu different.")


def test_un_scan_DEJA_INGERE_monte_le_point_de_jugement_a_DEUX_issues(tmp_path):
    """AC 5.2 : plus d'`EcranRefus` nu la ou le coeur refuse une ecriture.

    L'ensemble des cles est mesure **exactement** : une issue de plus, ou une
    issue renommee, se voit.
    """
    projet = projet_avec_trois_lots(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)), coeur)

    assert vu["nom"] == "EcranConflitDeDetection", vu["nom"]
    cles = [issue.cle for issue in vu["ecran"].choix.issues]
    assert cles == [atelier.ISSUE_NOUVELLE_VERSION, atelier.ISSUE_RENONCER]


def test_le_curseur_ne_vise_JAMAIS_l_issue_qui_ecrit(tmp_path):
    """`EPIC11-ARB-45` : l'issue qui ecrit n'est pas atteignable en une frappe.

    L'invariant est leve par `ChoixExclusif.__post_init__` et **jamais reecrit
    ici** : ce test mesure qu'il s'applique, donc que l'issue de versionnage
    porte bien `ecrit=True`.
    """
    projet = projet_avec_trois_lots(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)), coeur)
    choix = vu["ecran"].choix

    assert choix.action_qui_ecrit is not None
    assert choix.action_qui_ecrit.cle == atelier.ISSUE_NOUVELLE_VERSION
    assert choix.issues[choix.curseur].ecrit is False
    assert choix.issues[choix.curseur].cle == atelier.ISSUE_RENONCER


def test_le_rendu_du_choix_ne_pose_QUE_LA_FLECHE_une_ligne_par_issue(tmp_path):
    """`EPIC11-ARB-45` et `EPIC11-ARB-126` : ni case a cocher, ni puce.

    Les **deux** regimes de glyphes : le repli ASCII n'est pas une variante
    cosmetique, il change la fleche et la largeur.
    """
    projet = projet_avec_trois_lots(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)), coeur)
    choix = vu["ecran"].choix

    for ascii_seul in (False, True):
        table = jetons.glyphes(ascii_seul)
        rendu = choix.rendu(ascii_seul)
        assert len(rendu) == len(choix.issues)
        for rang, ligne in enumerate(rendu):
            tete = table["curseur"] if rang == choix.curseur else " "
            assert ligne == f"{tete} {choix.issues[rang].libelle}", ligne


# -- le volet symetrique : l'ensemble EXACT des refus qui montent l'ecran ----

def selection_ambigue(tmp_path: Path) -> tuple:
    """Une **selection** de trois fichiers dont deux portent le meme nom.

    C'est la forme reelle du « lot ambigu » : la quatrieme forme d'entree
    (`EPIC7-ARB-88`), refusee par `_refuser_les_noms_en_double`. Son slug par
    defaut est le nom du **dossier parent commun** -- ici `depot-mixte`, qui
    n'occupe aucun lot sous `scans/`. Trois fichiers et non deux : la
    verification **boucle** sur la selection, et le doublon est au milieu.
    """
    racine = tmp_path / "depot-mixte"
    for sous, nom in (("un", "page_a.tiff"), ("deux", "page_b.tiff"),
                      ("trois", "page_c.tiff")):
        (racine / sous).mkdir(parents=True, exist_ok=True)
        (racine / sous / nom).write_bytes(f"{sous}/{nom}\n".encode("utf-8"))
    return (racine / "un" / "page_a.tiff",
            racine / "deux" / "page_b.tiff",
            racine / "trois" / "page_c.tiff")


def scenarios_de_refus(tmp_path: Path) -> dict[str, tuple]:
    """Les quatre refus du temps 1, et **un seul** est un conflit d'ecriture.

    Chacun est leve avec la **classe reelle** que le coeur leverait : c'est la
    classe qui nomme la panne (`refus_de` en fait le code), et un double qui
    leverait toujours la meme classe ne mesurerait pas la discrimination.
    """
    projet = projet_avec_trois_lots(tmp_path)
    source = source_du_lot_cible(tmp_path)
    introuvable = tmp_path / "nulle-part" / "jamais-ecrit"
    return {
        "conflit": (demande(projet, source), refus_du_conflit(projet)),
        "dpi": (demande(projet, source),
                scan_ingest.InvalidScanDpiError("dpi hors bornes: 0")),
        "introuvable": (demande(projet, introuvable),
                        scan_ingest.UnsupportedScanInputError(
                            f"Chemin de scan introuvable: {introuvable}")),
        "ambigu": (demande(projet, selection_ambigue(tmp_path)),
                   scan_ingest.UnsupportedScanInputError(
                       "Deux fichiers portent le meme nom a la casse pres.")),
    }


def test_SEUL_le_conflit_d_ecriture_monte_le_point_de_jugement(tmp_path):
    """AC 5.3, et c'est le vrai livrable du lot.

    Sans ce volet, l'AC 5.2 serait vraie **par vacuite** : un ecran a deux
    issues monte sur tous les refus la satisferait, et « une issue de
    versionnage offerte sur un refus qui n'est pas un conflit d'ecriture serait
    un mensonge d'ecran ».

    On mesure l'**ensemble exact** des scenarios qui montent le jugement, pas
    la presence de l'un d'eux.
    """
    juges: set[str] = set()
    refus: set[str] = set()
    for nom, (une_demande, exception) in scenarios_de_refus(tmp_path).items():
        vu = jouer(une_demande, CoeurEspion(leve=exception))
        if vu["nom"] == "EcranConflitDeDetection":
            juges.add(nom)
        elif isinstance(vu["ecran"], EcranRefus):
            refus.add(nom)
    assert juges == {"conflit"}, juges
    # Le volet du volet : les trois autres gardent **exactement** l'ecran
    # d'aujourd'hui. Sans lui, un refus qui ne monterait plus rien du tout
    # passerait pour un succes de la discrimination.
    assert refus == {"dpi", "introuvable", "ambigu"}, refus


def test_L_EXCEDENT_de_la_condition_est_NOMME_plutot_que_tu(tmp_path):
    """Ce que la condition attrape en trop, mesure plutot que suppose.

    La discrimination porte sur le **code** du refus et sur ce que le disque
    porte au nom vise ; elle ne rejoue pas la regle du coeur, qui refuse sur
    les fichiers de meme nom et de contenu different
    (`_refuse_destructive_overwrite`). Les deux divergent sur les refus
    **marginaux qui partagent la classe** `UnsupportedScanInputError` et qui
    tombent sur un nom deja occupe : une forme d'entree non supportee, une
    selection ambigue deposee sous ce nom-la.

    Ce test **mesure** cet excedent au lieu de le taire. C'est un excedent et
    non un manque, et l'excedent est le bon sens du risque : offrir une issue
    de trop ne detruit rien -- l'operateur qui la retient obtient ce qu'elle
    annonce, un lot voisin --, n'en offrir aucune est le blocage sec.

    **Il est aussi borne** : si le second refus revient, la passe porte alors
    `nouvelle_version=True` et l'ecran de jugement ne remonte plus.
    """
    projet = projet_avec_trois_lots(tmp_path)
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)),
               CoeurEspion(leve=scan_ingest.UnsupportedScanInputError(
                   "Forme d'entree non supportee.")))
    assert vu["nom"] == "EcranConflitDeDetection", (
        "excedent attendu et documente : ce refus partage la classe du conflit "
        "et tombe sur un nom deja occupe")


def test_un_refus_NON_conflictuel_garde_EXACTEMENT_l_ecran_d_aujourd_hui(tmp_path):
    """Le code, la phrase et la mention du temps 1, inchanges (`EPIC11-ARB-30`)."""
    projet = projet_avec_trois_lots(tmp_path)
    exception = scan_ingest.InvalidScanDpiError("dpi hors bornes: 0")
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)),
               CoeurEspion(leve=exception))
    ecran = vu["ecran"]

    assert isinstance(ecran, EcranRefus)
    assert ecran.code == "InvalidScanDpiError"
    assert ecran.message == str(exception)
    assert ecran.non_ecrit == [atelier.NON_ECRIT_PAR_LE_TEMPS_1]


def test_une_passe_DEJA_VERSIONNEE_ne_repropose_PAS_l_issue(tmp_path):
    """La boucle est **bornee**, et c'est mesure plutot qu'espere.

    Un rang de version epuise (`version_ranks`, rangs `_v2`..`_v99`) est lui
    aussi un `UnsupportedScanInputError`, et il n'arrive **que** sur une passe
    qui demandait deja une version. Reproposer « ingerer une nouvelle version »
    y serait un mensonge d'ecran, et surtout un cycle sans sortie.
    """
    projet = projet_avec_trois_lots(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path),
                       nouvelle_version=True), coeur)
    assert isinstance(vu["ecran"], EcranRefus), vu["nom"]


def test_un_projet_SANS_ce_lot_garde_l_ecran_d_aujourd_hui(tmp_path):
    """Le volet symetrique du **renseignement** : rien sur le disque, pas d'issue.

    Meme refus, meme classe, meme phrase : seule la presence du lot sur le
    disque change. C'est ce qui mesure que la condition est bien le conflit
    d'ecriture et non le code du refus tout seul.
    """
    projet = tmp_path / "projet-vierge"
    project_layout.ensure_project_layout(projet)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)), coeur)
    assert isinstance(vu["ecran"], EcranRefus), vu["nom"]


def test_le_releve_vise_le_lot_CIBLE_et_compte_SES_pages(tmp_path):
    """Regle des fabriques : trois lots, la cible **au milieu** de l'ordre parcouru.

    Le cardinal attendu est **trois** et non un : les deux autres lots portent
    une seule page chacun, si bien qu'un releve qui viserait le premier lot, le
    dernier, ou `scans/` entier rendrait un autre chiffre.
    """
    projet = projet_avec_trois_lots(tmp_path)
    scans = projet / project_layout.SCANS_DIRNAME
    # La position se verifie sur la liste que le CODE parcourt.
    parcourus = [chemin.name for chemin in sorted(scans.iterdir())]
    assert parcourus == list(LOTS_DE_SCAN), parcourus
    assert parcourus.index(LOT_CIBLE) == 1, "la cible n'est ni premiere ni derniere"

    conflit = atelier.conflit_de(
        demande(projet, source_du_lot_cible(tmp_path)),
        atelier.refus_de(refus_du_conflit(projet)))
    assert conflit is not None
    assert conflit.slug == LOT_CIBLE
    assert conflit.pages == len(PAGES_DU_LOT_CIBLE)
    assert conflit.pages != PAGES_DES_AUTRES_LOTS


# -- les deux issues MENENT quelque part -------------------------------------

def test_l_issue_de_VERSIONNAGE_relance_la_passe_avec_le_drapeau(tmp_path):
    """`EPIC11-ARB-89` : la seconde issue **ecrit**, elle ne decore pas.

    Le finding `K3` est ce qui rend ce test necessaire : une issue navigable
    qui n'appelle personne est un cul-de-sac clavier, et elle a l'air de
    marcher.
    """
    projet = projet_avec_trois_lots(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))

    def retenir(app):
        ecran = app.screen
        ecran.choix.viser(atelier.ISSUE_NOUVELLE_VERSION)
        ecran.traiter("enter")
        return True

    jouer(demande(projet, source_du_lot_cible(tmp_path)), coeur, apres=retenir)

    assert len(coeur.appels) == 2, (
        "la passe doit etre relancee, et une seule fois")
    assert coeur.appels[0][1]["nouvelle_version"] is False
    assert coeur.appels[1][1]["nouvelle_version"] is True
    # Le reste de l'appel est **identique** : seul le drapeau change.
    premier, second = coeur.appels
    assert premier[0] == second[0]
    assert {cle: valeur for cle, valeur in premier[1].items()
            if cle not in ("nouvelle_version", "rappel_progression")} == \
           {cle: valeur for cle, valeur in second[1].items()
            if cle not in ("nouvelle_version", "rappel_progression")}


def test_l_issue_QUI_N_ECRIT_PAS_remonte_au_menu_sans_relancer(tmp_path):
    """Le volet symetrique : renoncer ne rappelle pas le coeur."""
    projet = projet_avec_trois_lots(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))

    def retenir(app):
        ecran = app.screen
        ecran.choix.viser(atelier.ISSUE_RENONCER)
        ecran.traiter("enter")
        return None

    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)), coeur,
               apres=retenir)
    assert len(coeur.appels) == 1, coeur.appels
    assert vu["rang_final"] == CoqueTui.RANG_DES_ATELIERS
    assert vu["nom_final"] == "PalierTemoin"


# -- et le refus n'a RIEN ecrit ---------------------------------------------

def test_le_conflit_n_ecrit_RIEN_mesure_aux_inodes_et_par_temoin(tmp_path):
    """Le refus, l'ecran de jugement et le releve ne touchent pas le disque.

    Mesure aux **inodes**, au **`st_mtime_ns`** et par les **temoins** deja
    deposes -- jamais par condensat : sur une fixture deterministe, une
    reecriture rend exactement les memes octets (`EPIC11-ARB-83`).
    """
    projet = projet_avec_trois_lots(tmp_path)
    source = source_du_lot_cible(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))

    avant = photographie(projet)
    jouer(demande(projet, source), coeur)
    apres = photographie(projet)

    assert divergences(avant, apres) == set()
    # Temoin : la photographie porte bien de la matiere, sans quoi l'egalite
    # ci-dessus serait verte sur deux dictionnaires vides.
    scans = str(Path(project_layout.SCANS_DIRNAME) / LOT_CIBLE
                / PAGES_DU_LOT_CIBLE[1][0])
    assert scans in avant, sorted(avant)


# ===========================================================================
# E3 -- la ligne de cartouche CHIFFREE, et son volet symetrique
# ===========================================================================

def test_le_cartouche_CHIFFRE_le_lot_occupe_et_ce_qui_l_occupe(tmp_path):
    """AC 5.5 / `EPIC11-ARB-4` : une issue neuve sans chiffre n'en est pas.

    Deux lignes, et les deux sont **mesurees** sur le disque : le lot occupe
    (son slug, verbatim) et le nombre de pages qu'il porte. Aucun rang n'est
    annonce -- voir l'en-tete de ce banc.
    """
    projet = projet_avec_trois_lots(tmp_path)
    conflit = atelier.conflit_de(
        demande(projet, source_du_lot_cible(tmp_path)),
        atelier.refus_de(refus_du_conflit(projet)))
    panneau = atelier.panneau_du_conflit(conflit)

    assert [ligne.libelle for ligne in panneau.lignes] == [
        atelier.LIBELLE_LOT_OCCUPE, atelier.LIBELLE_PAGES_OCCUPANTES]
    assert [ligne.valeur for ligne in panneau.lignes] == [
        LOT_CIBLE, len(PAGES_DU_LOT_CIBLE)]
    # Tout chiffre porte son unite (story 11.1, AC 1.2).
    assert panneau.lignes[1].unite == atelier.UNITE
    assert panneau.porte_un_majorant is False, (
        "les deux chiffres sont mesures sur le disque, aucun n'est un majorant")


def test_la_ligne_chiffree_ne_parait_QU_AVEC_l_issue(tmp_path):
    """Le volet symetrique d'`EPIC11-ARB-4`, dans l'autre sens.

    Un refus qui n'est pas un conflit ne porte aucun chiffre : `EcranRefus` n'a
    pas de cartouche, et rien ne doit lui en poser un. Mesure sur les lignes
    **rendues**, pas sur la presence d'un attribut.
    """
    projet = projet_avec_trois_lots(tmp_path)
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)),
               CoeurEspion(leve=scan_ingest.InvalidScanDpiError("dpi: 0")))
    lignes = vu["lignes"]
    assert not any(atelier.LIBELLE_LOT_OCCUPE in ligne for ligne in lignes)
    assert not any(atelier.LIBELLE_PAGES_OCCUPANTES in ligne
                   for ligne in lignes)


def test_le_cartouche_est_RENDU_par_l_ecran_de_jugement(tmp_path):
    """La ligne chiffree n'est pas seulement construite : elle est a l'ecran.

    Un panneau fabrique et jamais peint serait exactement le finding `K3` dans
    sa version chiffree -- un objet correct que personne ne montre.
    """
    projet = projet_avec_trois_lots(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)), coeur)
    lignes = vu["lignes"]

    assert any(LOT_CIBLE in ligne for ligne in lignes), lignes
    assert any(atelier.LIBELLE_PAGES_OCCUPANTES in ligne for ligne in lignes)
    assert any(f"{len(PAGES_DU_LOT_CIBLE)} {atelier.UNITE}" in ligne
               for ligne in lignes), lignes


def test_le_curseur_RENDU_designe_bien_l_issue_qui_n_ecrit_pas(tmp_path):
    """Le rang du curseur est **derive**, jamais compte a la main.

    L'insertion du cartouche decale les issues : un rang calcule a la main se
    peindrait sur une autre ligne, et l'operateur verrait le curseur sur
    l'issue qui ecrit.
    """
    projet = projet_avec_trois_lots(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)), coeur)
    lignes = vu["lignes"]
    rang = vu["rang_du_curseur"]

    assert lignes[rang].strip().endswith(atelier.LIBELLE_RENONCER), lignes[rang]


# ===========================================================================
# La grille -- 80x24, dans les DEUX regimes de glyphes
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", [False, True])
def test_l_ecran_de_jugement_TIENT_dans_la_grille_80x24(ascii_seul, tmp_path):
    """`EPIC11-ARB-21` : le plancher est 80x24, et le repli ASCII contraint la largeur.

    Mesurer les deux regimes n'est pas une precaution : une ligne qui tient en
    Unicode peut deborder en ASCII, ou l'inverse -- les glyphes n'ont pas la
    meme largeur de colonne.
    """
    projet = projet_avec_trois_lots(tmp_path)
    coeur = CoeurEspion(leve=refus_du_conflit(projet))
    vu = jouer(demande(projet, source_du_lot_cible(tmp_path)), coeur,
               ascii_seul=ascii_seul)
    assert vu["nom"] == "EcranConflitDeDetection", vu["nom"]

    utile = jetons.largeur_utile(80)
    trop_larges = [ligne for ligne in vu["lignes"]
                   if jetons.colonnes(ligne) > utile]
    assert trop_larges == [], trop_larges
    assert len(vu["lignes"]) <= 24, len(vu["lignes"])
    assert len(vu["lignes"]) >= 5, "temoin : l'ecran porte de la matiere"
