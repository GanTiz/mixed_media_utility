# -*- coding: utf-8 -*-
"""Le modele pur du palier 0 (story 11.2, task 2 -- AC 1, 2, 3, 4).

**Aucun `textual` ici, ni dans le module mesure.** C'est le point du lot : le
banc de la TUI n'a ni pilote de terminal ni ecran, donc tout ce qui peut etre
mesure hors banc doit l'etre hors banc. Les recents, la classification d'un
dossier, la resolution d'un chemin et la completion sont du calcul pur : ils se
verifient sans monter d'application, et ils sont exactement ce que les mutants
attaquent.
"""
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.tui import explorateur, projets

#: Le paquet mesure par les frontieres negatives de la story 11.2b.
PAQUET_TUI = Path(projets.__file__).parent


# ---------------------------------------------------------------------------
# Fabriques. **Toute fabrique de collection produit au moins TROIS elements
# distinguables**, aux valeurs differentes -- la regle du depot, nee de trois
# occurrences consecutives du meme defaut (5.6, 5.7, 5.8). Un remplissage
# uniforme rendrait une permutation invisible.
# ---------------------------------------------------------------------------

def _trois_projets(racine: Path) -> list[Path]:
    """Trois vrais projets, crees par le coeur, aux noms distinguables."""
    return [creer_projet(racine, nom).chemin
            for nom in ("projet_demo", "film_court_2026", "tests_calibration")]


@pytest.fixture
def fichier_recents(tmp_path) -> Path:
    """Le document de recents, TOUJOURS injecte : aucun test n'ecrit jamais
    dans les reglages reels de la machine (AC 2.3)."""
    return tmp_path / "reglages" / "recents-v1.json"


# ---------------------------------------------------------------------------
# AC 1 et AC 2 -- les recents
# ---------------------------------------------------------------------------

def test_le_plus_recent_est_en_tete(tmp_path, fichier_recents):
    """AC 1.1. Trois projets, trois dates differentes, ordre impose."""
    a, b, c = _trois_projets(tmp_path)
    recents = projets.Recents(fichier_recents)
    recents.noter_ouverture(a, quand="2026-08-14T10:00:00Z")
    recents.noter_ouverture(b, quand="2026-08-21T10:00:00Z")
    recents.noter_ouverture(c, quand="2026-08-26T10:00:00Z")

    assert [e.chemin for e in recents.lire()] == [c, b, a]


def test_ouvrir_celui_du_MILIEU_le_remonte_en_tete(tmp_path, fichier_recents):
    """AC 1.2, et c'est la mesure qui compte.

    La cible est **ni la premiere ni la derniere** : un tri fautif qui rendrait
    toujours `entrees[0]`, ou qui se contenterait d'appliquer `append`, reste
    vert sur une liste ou la cible est deja en tete. C'est le mutant `M25` de la
    story 5.7, ou `_find_lot` rendait le premier lot et 257 tests restaient
    verts.
    """
    a, b, c = _trois_projets(tmp_path)
    recents = projets.Recents(fichier_recents)
    recents.noter_ouverture(a, quand="2026-08-14T10:00:00Z")
    recents.noter_ouverture(b, quand="2026-08-21T10:00:00Z")
    recents.noter_ouverture(c, quand="2026-08-26T10:00:00Z")
    assert [e.chemin for e in recents.lire()] == [c, b, a]

    recents.noter_ouverture(b, quand="2026-08-28T09:00:00Z")

    ordre = [e.chemin for e in recents.lire()]
    assert ordre == [b, c, a], ordre
    # Les deux autres gardent leur ordre RELATIF : c avant a, comme avant.
    assert ordre.index(c) < ordre.index(a)


def test_un_chemin_note_deux_fois_ne_donne_qu_une_ligne(tmp_path, fichier_recents):
    """AC 2.5, cote ecriture."""
    a, b, _ = _trois_projets(tmp_path)
    recents = projets.Recents(fichier_recents)
    recents.noter_ouverture(a, quand="2026-08-14T10:00:00Z")
    recents.noter_ouverture(b, quand="2026-08-21T10:00:00Z")
    recents.noter_ouverture(a, quand="2026-08-26T10:00:00Z")

    entrees = recents.lire()
    assert len(entrees) == 2, entrees
    assert entrees[0].chemin == a
    assert entrees[0].ouvert_le == "2026-08-26T10:00:00Z"


def test_un_document_portant_deux_fois_le_meme_chemin_est_dedoublonne(
        tmp_path, fichier_recents):
    """AC 2.5, cote LECTURE -- un document fabrique a la main, pas produit.

    Le volet ecriture ci-dessus passerait meme si la deduplication n'existait
    qu'a l'ecriture. Celui-ci mesure l'autre moitie, et il garde **la plus
    recente** des deux entrees.
    """
    a, _, _ = _trois_projets(tmp_path)
    fichier_recents.parent.mkdir(parents=True, exist_ok=True)
    fichier_recents.write_text(json.dumps({"projets": [
        {"chemin": str(a), "ouvert_le": "2026-08-01T10:00:00Z"},
        {"chemin": str(a), "ouvert_le": "2026-08-27T10:00:00Z"},
    ]}), encoding="utf-8")

    entrees = projets.Recents(fichier_recents).lire()
    assert len(entrees) == 1
    assert entrees[0].ouvert_le == "2026-08-27T10:00:00Z"


def test_retirer_ote_la_ligne_et_ne_touche_PAS_au_dossier(tmp_path, fichier_recents):
    """AC 1.3 -- frontiere de comptage a zero, `EPIC11-ARB-39`."""
    a, b, c = _trois_projets(tmp_path)
    recents = projets.Recents(fichier_recents)
    for chemin, quand in ((a, "2026-08-14T10:00:00Z"), (b, "2026-08-21T10:00:00Z"),
                          (c, "2026-08-26T10:00:00Z")):
        recents.noter_ouverture(chemin, quand=quand)

    avant = sorted(p.name for p in b.rglob("*"))
    recents.retirer(b)

    assert [e.chemin for e in recents.lire()] == [c, a]
    assert sorted(p.name for p in b.rglob("*")) == avant
    assert (b / "project.json").is_file()


def test_le_comptage_du_dossier_MORD(tmp_path):
    """Volet symetrique du precedent : sans lui, la mesure serait verte meme si
    `retirer` supprimait le dossier -- il suffirait que la comparaison porte sur
    deux listes vides."""
    a, _, _ = _trois_projets(tmp_path)
    avant = sorted(p.name for p in a.rglob("*"))
    assert avant, "un projet cree par le coeur n'est jamais vide"
    (a / "project.json").unlink()
    assert sorted(p.name for p in a.rglob("*")) != avant


def test_le_document_ne_porte_QUE_des_chemins_et_des_dates(tmp_path, fichier_recents):
    """AC 2.2 -- frontiere de perimetre `EPIC11-ARB-16`.

    « Ni les derniers reglages d'atelier, ni l'historique des commandes. » La
    mesure porte sur les **cles** du document ecrit, ce qui la rend capable de
    rougir a l'ajout d'une quatrieme donnee -- alors qu'une mesure sur les
    valeurs ne le ferait pas.
    """
    a, b, _ = _trois_projets(tmp_path)
    recents = projets.Recents(fichier_recents)
    recents.noter_ouverture(a, quand="2026-08-14T10:00:00Z")
    recents.noter_ouverture(b, quand="2026-08-21T10:00:00Z")

    document = json.loads(fichier_recents.read_text(encoding="utf-8"))
    assert set(document) == {"projets"}
    for entree in document["projets"]:
        assert set(entree) == {"chemin", "ouvert_le"}, entree


def test_la_frontiere_de_perimetre_MORD(tmp_path, fichier_recents):
    """Volet symetrique : un document a quatre cles doit sortir de l'egalite."""
    fichier_recents.parent.mkdir(parents=True, exist_ok=True)
    fichier_recents.write_text(json.dumps({"projets": [
        {"chemin": str(tmp_path), "ouvert_le": "2026-08-01T10:00:00Z",
         "derniere_cadence": 25},
    ]}), encoding="utf-8")
    document = json.loads(fichier_recents.read_text(encoding="utf-8"))
    assert set(document["projets"][0]) != {"chemin", "ouvert_le"}


@pytest.mark.parametrize("contenu", [
    None,                    # fichier absent
    "",                      # fichier vide
    "{ pas du json",         # illisible
    '{"projets": "pas une liste"}',
    '{"projets": [{"sans_chemin": 1}]}',
    "[]",                    # forme inattendue : une liste au lieu d'un objet
])
def test_un_document_de_recents_casse_ne_fait_pas_tomber_la_tui(
        fichier_recents, contenu):
    """AC 2.4. C'est le premier ecran que voit un operateur en panne."""
    if contenu is not None:
        fichier_recents.parent.mkdir(parents=True, exist_ok=True)
        fichier_recents.write_text(contenu, encoding="utf-8")
    assert projets.Recents(fichier_recents).lire() == []


def test_le_fichier_de_recents_vit_chez_l_utilisateur(monkeypatch, tmp_path):
    """AC 2.1 : `%APPDATA%` sous Windows, `~/.config` ailleurs."""
    monkeypatch.setenv("APPDATA", str(tmp_path / "AppData"))
    chemin = projets.chemin_du_fichier_de_recents(windows=True)
    assert chemin == tmp_path / "AppData" / "mixed_media_utility" / "recents-v1.json"

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    chemin = projets.chemin_du_fichier_de_recents(windows=False)
    assert chemin == tmp_path / "config" / "mixed_media_utility" / "recents-v1.json"


# ---------------------------------------------------------------------------
# AC 4 -- les trois refus, et les deux situations qui n'en sont pas
# ---------------------------------------------------------------------------

def test_un_projet_lisible_n_est_pas_un_refus(tmp_path):
    a, _, _ = _trois_projets(tmp_path)
    diag = projets.diagnostiquer(a)
    assert diag.etat == projets.PROJET_LISIBLE
    assert not diag.est_un_refus
    assert not diag.porte_la_croix
    assert diag.motif is None


def test_refus_a__le_dossier_existe_sans_project_json(tmp_path):
    """AC 4.1 (a). La phrase est de la TUI : c'est une CLASSIFICATION qu'elle
    fait, pas un verdict du coeur -- `lire_projet` rend ici le meme
    `[Errno 2]` que pour un dossier inexistant, mesure a l'ecriture de la
    fiche."""
    dossier = tmp_path / "rushes_bruts"
    dossier.mkdir()
    (dossier / "un_rush.mov").write_bytes(b"x")

    diag = projets.diagnostiquer(dossier)
    assert diag.etat == projets.SANS_PROJET
    assert diag.est_un_refus
    assert diag.porte_la_croix
    assert "project.json" in diag.phrase


@pytest.mark.parametrize("contenu, fragment_attendu", [
    ("{ pas du json", "Expecting property name"),
    ('{"schema_version": "9.9"}', "is not a supported manifest schema_version"),
])
def test_refus_b__project_json_illisible_rend_le_motif_du_coeur_VERBATIM(
        tmp_path, contenu, fragment_attendu):
    """AC 4.1 (b). **Un seul refus, deux motifs** -- `EXPERIENCE.md` groupe
    « illisible ou version inconnue » en un troisieme message.

    Le motif n'est jamais paraphrase : « une maquette qui ecrivait
    `LOT_INCOMPLET` la ou le coeur ecrit `LOT_INCOMPLETE` a deja coute une
    divergence a ce depot ».
    """
    dossier = tmp_path / "projet_casse"
    dossier.mkdir()
    (dossier / "project.json").write_text(contenu, encoding="utf-8")

    diag = projets.diagnostiquer(dossier)
    assert diag.etat == projets.PROJET_ILLISIBLE
    assert diag.est_un_refus
    assert diag.porte_la_croix
    assert fragment_attendu in diag.motif, diag.motif


def test_refus_c__un_recent_disparu_du_disque(tmp_path):
    """AC 4.1 (c) et AC 1.5. **Meme etat de disque que le cas « a creer »** --
    seul le CONTEXTE les separe : un recent qui a disparu est une anomalie (un
    disque externe debranche), un chemin qu'on tape est une intention."""
    disparu = tmp_path / "sur_un_disque_debranche"

    diag = projets.diagnostiquer(disparu, depuis_les_recents=True)
    assert diag.etat == projets.DISPARU
    assert diag.est_un_refus
    assert diag.porte_la_croix


def test_le_meme_chemin_TAPE_n_est_PAS_un_refus(tmp_path):
    """`EPIC11-ARB-40` : « un chemin qui ne designe rien est traite comme une
    intention de creation, pas comme une faute de frappe ».

    C'est le **volet symetrique** du test precedent, sur le meme etat de disque.
    Les deux ensemble prouvent que le contexte est bien lu -- une
    implementation qui ignorerait `depuis_les_recents` en ferait rougir un.
    """
    absent = tmp_path / "pas_encore_la"

    diag = projets.diagnostiquer(absent)
    assert diag.etat == projets.ABSENT_A_CREER
    assert not diag.est_un_refus
    assert diag.porte_la_croix is False


def test_un_dossier_VIDE_n_a_meme_pas_la_croix(tmp_path):
    """AC 4.3. « Un dossier vide n'est pas une anomalie, c'est un point de
    depart » -- il se distingue donc du dossier qui porte des fichiers mais pas
    de `project.json`, lequel porte bien le `✕`."""
    vide = tmp_path / "tout_neuf"
    vide.mkdir()

    diag = projets.diagnostiquer(vide)
    assert diag.etat == projets.VIDE_A_CREER
    assert not diag.est_un_refus
    assert diag.porte_la_croix is False


def test_aucun_refus_ne_propose_de_REPARER(tmp_path):
    """AC 4.2 -- frontiere de vocabulaire, comptage a zero."""
    interdits = ("reparer", "corriger le fichier", "reconstruire")
    dossier = tmp_path / "projet_casse"
    dossier.mkdir()
    (dossier / "project.json").write_text("{ casse", encoding="utf-8")

    textes = []
    for cible, contexte in ((dossier, False), (tmp_path / "vide", False),
                            (tmp_path / "disparu", True)):
        diag = projets.diagnostiquer(cible, depuis_les_recents=contexte)
        textes += [diag.phrase or "", diag.motif or ""]

    for mot in interdits:
        assert not any(mot in t.lower() for t in textes), (mot, textes)


def test_la_frontiere_de_vocabulaire_MORD():
    """Volet symetrique : la mesure doit sortir sur une phrase fautive."""
    interdits = ("reparer", "corriger le fichier", "reconstruire")
    fautive = "Ce project.json est casse : voulez-vous le reparer ?"
    assert any(mot in fautive.lower() for mot in interdits)


# ---------------------------------------------------------------------------
# AC 1.4 -- la frontiere negative de `EPIC11-ARB-48` : « un grep de `completer`
# dans `src/mixed_media_utility/tui/` rend zero ».
#
# Elle etait confiee a un COMMENTAIRE ecrit a cet endroit meme -- « la
# frontiere negative de la story 11.2b le mesure » --, et aucun test ne la
# portait. Le grep reel rendait **1**, pas 0. C'etait le troisieme lot
# consecutif de cet epic ou une frontiere negative citee est confiee a une
# phrase (findings `F11`, `E24`, `F-3`).
# ---------------------------------------------------------------------------

#: **RESSERREE le 2026-08-31 par `EPIC11-ARB-127`** (Egan) : « la frontiere qui
#: interdisait le mot `completer` dans `tui/` visait la completion de CHEMIN, pas
#: celle du QR ».
#:
#: Ce qu'elle mesurait : **le mot**. Ce qu'elle devait mesurer : la **chose** --
#: la completion `Tab` d'un chemin, celle que l'explorateur a remplacee partout.
#: Les deux ont coincide tant qu'aucun ecran ne parlait d'autre chose. La story
#: 11.5 en a fait entrer un : `E3-4b` s'appelle « Compléter le QR »
#: (`EPIC11-ARB-29`), et le lot D avait du contourner la frontiere en nommant sa
#: cle d'issue `saisir-le-qr` -- c'est-a-dire **renommer la chose au lieu de
#: resserrer la frontiere**, ce qu'`EPIC11-ARB-127` corrige.
#:
#: La mesure porte donc desormais sur la **co-occurrence** du verbe et d'un mot
#: de chemin sur la meme ligne. Elle reste un grep de TEXTE et non une lecture
#: d'AST -- l'AC dit « un grep », et ce qui doit disparaitre est aussi bien un
#: appel qu'une ligne de raccourcis, un docstring qui decrirait encore le
#: mecanisme, ou un commentaire laisse derriere.

#: Le verbe et ses formes, en **frontieres de mot** : sans elles, `completude`
#: et `COMPLETUDE_COMPLET` -- le vocabulaire de completude des lots, qui vient du
#: coeur -- seraient comptes comme des completions de chemin.
_VERBE_DE_COMPLETION = re.compile(
    r"\bcomplet(?:er|ion|ions|ees|ee|es|e|ait|ez)\b")

#: Ce qui fait d'une completion une completion de **chemin**. Le mot `tab` y est
#: suivi d'un blanc : `tab` seul attraperait `table`, `tableau`, `tabulation`.
_MOTS_DU_CHEMIN = ("chemin", "dossier", "fichier", "path", "tab ",
                   "repertoire", "adresse")


def _sans_accent(texte: str) -> str:
    """Le texte replie sur l'ASCII, pour que `compléter` compte comme `completer`.

    Le depot ecrit ses commentaires **avec** accents (CLAUDE.md) et ses
    identifiants sans : une mesure qui ne verrait qu'une des deux formes
    laisserait passer la moitie de ce qu'elle cherche, et c'est la moitie
    visible a l'ecran.
    """
    return "".join(
        c for c in unicodedata.normalize("NFD", texte)
        if unicodedata.category(c) != "Mn").lower()


#: Les citations TOLEREES, nommees ici plutot que tues. Chacune est une
#: **prose** qui parle du mecanisme retire, ou une coincidence de mise en page ;
#: aucune n'offre une completion de chemin :
#:
#: * `explorateur.py` porte, sur une meme ligne, le jeton d'etat `complete`
#:   (un glyphe de `DESIGN.md` section 6) et la variable `chemin`. Les deux n'ont
#:   aucun rapport : c'est la limite d'un grep de ligne, dite plutot que tue ;
#: * `palier_profil_defaut.py` est la MEME coincidence, arrivee le 2026-09-07
#:   avec l'ecran du profil par defaut : le meme jeton d'etat `complete`, choisi
#:   selon qu'un `chemin` est pose ou non. Deuxieme occurrence du meme motif, ce
#:   qui dit que la limite du grep de ligne est structurelle et non anecdotique ;
#: * `projets.py` porte un titre de section, « Chemins : resolution et
#:   completion », herite de l'epoque ou la completion existait.
#:
#: `atelier_scan_rapport.py` y figurait et n'y est plus : la note d'histoire
#: qu'il portait a disparu avec son module, et la ligne du docstring qui
#: annoncait « trois citations » comptait donc une exclusion morte.
#:
#: Le test `..._est_PORTANTE` ci-dessous verifie qu'elles restent **toutes**
#: vivantes : une exclusion qui ne correspond plus a rien transformerait la
#: frontiere en tautologie sans que rien ne le dise.
CITATIONS_TOLEREES = (
    ("explorateur.py", 'jetons.marque("complete", "projet")'),
    ("palier_profil_defaut.py",
     'etat = "substitute" if chemin is None else "complete"'),
    ("projets.py", "Chemins : resolution et completion."),
)


def _occurrences_de_completion_de_chemin(dossier, tolerees=()):
    """Les lignes de `dossier` qui offrent une completion de **chemin**.

    Deux conditions **cumulatives**, et c'est tout le resserrement
    d'`EPIC11-ARB-127` : le verbe de completion, en frontiere de mot, **et** un
    mot de chemin sur la meme ligne. « Compléter le QR » ne porte aucun mot de
    chemin ; « Tab complete le chemin » les porte tous les deux.

    Sur le TEXTE et non sur l'AST : l'AC dit « un grep », et ce qui doit
    disparaitre est aussi bien un appel qu'une ligne de raccourcis, un docstring
    qui decrirait encore le mecanisme, ou un commentaire laisse derriere. Un test
    qui ne regarderait que les appels laisserait vivre la moitie de ce que la
    story a supprime.
    """
    trouvees = []
    for module in sorted(dossier.rglob("*.py")):
        lignes = module.read_text(encoding="utf-8").splitlines()
        for rang, ligne in enumerate(lignes, 1):
            plie = _sans_accent(ligne)
            if not _VERBE_DE_COMPLETION.search(plie):
                continue
            if not any(mot in plie for mot in _MOTS_DU_CHEMIN):
                continue
            if any(module.name == fichier and motif in ligne
                   for fichier, motif in tolerees):
                continue
            trouvees.append(f"{module.name}:{rang}: {ligne.strip()}")
    return trouvees


def test_la_frontiere_de_COMPLETER_rend_zero_sur_le_paquet_TUI():
    """AC 1.4, `EPIC11-ARB-48`, resserree par `EPIC11-ARB-127`.

    Aucun module du paquet n'offre de completion de chemin -- « il n'y a plus de
    completion a rendre disponible, l'explorateur l'a remplacee **partout** ».
    """
    assert _occurrences_de_completion_de_chemin(
        PAQUET_TUI, CITATIONS_TOLEREES) == []


def test_le_vocabulaire_du_SCAN_ne_fait_PLUS_rougir_la_frontiere():
    """`EPIC11-ARB-127`, l'autre moitie : « cesser de mordre sur le vocabulaire
    du Scan ».

    Sans ce test, quelqu'un pourrait re-elargir la frontiere au mot seul et le
    contournement d'hier -- une cle d'issue renommee pour ne pas la declencher --
    reviendrait en silence. On mesure donc que les trois formes du vocabulaire du
    Scan passent : le titre de l'ecran, sa cle d'issue, et le nom de son module.
    """
    for phrase in ("LIBELLE = \"Compléter le QR\"",
                   "ISSUE_COMPLETER = \"completer-le-qr\"",
                   "from .atelier_scan_completion import EcranCompletionQr"):
        plie = _sans_accent(phrase)
        assert _VERBE_DE_COMPLETION.search(plie) or "completion" in plie, phrase
        assert not any(mot in plie for mot in _MOTS_DU_CHEMIN), phrase


def test_le_vocabulaire_de_COMPLETUDE_du_coeur_n_est_pas_confondu():
    """`completude`, `complet`, `pages_completables` viennent du coeur et ne sont
    pas des completions : la frontiere de mot les separe du verbe."""
    for mot in ("completude", "COMPLETUDE_COMPLET", "pages_completables",
                "completable"):
        assert not _VERBE_DE_COMPLETION.search(_sans_accent(mot)), mot


def test_l_EXCLUSION_de_la_frontiere_de_COMPLETER_est_PORTANTE():
    """Les exclusions nommees doivent rester VIVANTES, et rester les SEULES.

    Une exclusion qui ne correspond plus a rien transformerait la frontiere en
    tautologie sans que rien ne le dise : le test ci-dessus resterait vert en
    ne mesurant plus le motif qu'on croit exclure. On mesure donc les deux
    sens -- sans exclusion il y a exactement trois occurrences, et ce sont
    celles qu'on a nommees.
    """
    sans_exclusion = _occurrences_de_completion_de_chemin(PAQUET_TUI)
    assert len(sans_exclusion) == len(CITATIONS_TOLEREES), sans_exclusion
    for fichier, motif in CITATIONS_TOLEREES:
        assert any(trouvee.startswith(f"{fichier}:") and motif in trouvee
                   for trouvee in sans_exclusion), (fichier, motif)


def test_la_frontiere_de_COMPLETER_MORD(tmp_path):
    """Volet symetrique : la mesure doit SORTIR sur un paquet qui offre une
    completion de chemin, sous chacune des formes que la story a supprimees.

    Le volet precedent de cette famille -- `test_la_frontiere_de_sobriete_MORD`
    -- etait une tautologie : il comparait deux chaines ecrites dans le test.
    Celui-ci fait tourner la MEME fonction de mesure que la frontiere, sur un
    paquet fabrique pour l'occasion.

    Le quatrieme fichier est celui que `EPIC11-ARB-127` **exempte** : il porte le
    verbe, accentue, sans aucun mot de chemin. Il ne doit pas sortir -- sans quoi
    la frontiere n'aurait pas ete resserree, seulement deplacee.
    """
    faux = tmp_path / "faux_paquet"
    faux.mkdir()
    (faux / "sain.py").write_text("VALEUR = 1\n", encoding="utf-8")
    (faux / "champ.py").write_text(
        'def completer(chemin):\n    """Le mecanisme supprime."""\n'
        '    return chemin\n', encoding="utf-8")
    (faux / "raccourcis.py").write_text(
        '# `Tab` completer le chemin\nLIGNE = "Tab compléter"\n',
        encoding="utf-8")
    (faux / "scan.py").write_text(
        'TITRE = "Compléter ce que le QR aurait dit"\n'
        'ISSUE = "completer-le-qr"\n', encoding="utf-8")

    trouvees = _occurrences_de_completion_de_chemin(faux)
    assert len(trouvees) == 3, trouvees
    assert not any(t.startswith("sain.py") for t in trouvees), trouvees
    assert not any(t.startswith("scan.py") for t in trouvees), trouvees
    # Et l'exclusion nommee **ne blanchit pas** un autre fichier : elle est
    # attachee au nom du module autant qu'au motif.
    (faux / "autre.py").write_text(
        "# Chemins : resolution et completion.\n", encoding="utf-8")
    assert len(_occurrences_de_completion_de_chemin(
        faux, CITATIONS_TOLEREES)) == 4


# ---------------------------------------------------------------------------
# AC 3 / AC 6.8 -- la resolution d'un chemin, et le fait qu'il n'y en ait
# qu'UNE
# ---------------------------------------------------------------------------

def _appels_de_methode(fichier, noms):
    """Les appels `<quelque chose>.<nom>(...)` d'un module, lus a l'AST.

    A l'AST et pas au texte : les deux modules PARLENT de `resolve()` dans
    leurs docstrings, pour dire pourquoi ils ne l'appellent pas. Un grep de
    chaine y trouverait la prose et rendrait le test faux dans les deux sens.
    """
    import ast

    arbre = ast.parse(Path(fichier).read_text(encoding="utf-8"))
    return [f"{Path(fichier).name}:{n.func.attr} (ligne {n.lineno})"
            for n in ast.walk(arbre)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr in noms]


def test_AUCUN_des_deux_modeles_purs_n_appelle_resolve():
    """AC 6.8 : « un lien symbolique est suivi **une fois**, jamais resolu
    recursivement ».

    La frontiere existait deja, mais **sur `explorateur.py` seul** -- et le
    defaut vivait dans `projets.py`, ou `resoudre` appelait
    `resolve(strict=False)`. `resolve()` reecrit chaque maillon jusqu'a la
    cible reelle ; `strict=False` n'en concerne que l'existence, jamais la
    recursion. Les cinq appelants d'`ecran_projet` (champs `dossier_parent` et
    apercu de creation) affichaient donc la cible REELLE d'un parent saisi via
    un lien, avant validation.
    """
    for module in (projets, explorateur):
        appels = _appels_de_methode(module.__file__, {"resolve"})
        assert appels == [], appels


def test_la_garde_du_RESOLVE_MORD(tmp_path):
    """Volet symetrique : la lecture AST doit bien VOIR un `.resolve(`.

    Sans lui, `_appels_de_methode` pourrait rendre la liste vide sur un fichier
    illisible ou apres une refonte de son parcours, et la garde ci-dessus
    serait verte en ne mesurant rien.
    """
    faux = tmp_path / "faux.py"
    faux.write_text("from pathlib import Path\n\n\n"
                    "def r(p):\n    return Path(p).resolve(strict=False)\n",
                    encoding="utf-8")
    assert _appels_de_methode(faux, {"resolve"}) == ["faux.py:resolve (ligne 5)"]


def test_la_resolution_de_chemin_n_a_qu_UNE_implementation():
    """Elles ont ete deux, et elles ne faisaient pas la meme chose.

    `explorateur.resoudre_sans_recursion` etait une copie locale ecrite pour
    contourner `projets.resoudre` : sa duplication etait signalee dans son
    propre docstring, et les deux divergeaient sur le seul point qui compte --
    l'une reecrivait les liens, l'autre non. Deux implementations d'une meme
    regle divergent au premier ajustement ; celle-ci avait divergee d'avance.

    Mesure a l'identite d'objet **et** a la structure : un jour ou l'autre
    quelqu'un reecrira une fonction plutot que de rendre l'alias.
    """
    import ast

    assert projets.resoudre is explorateur.normaliser
    assert not hasattr(explorateur, "resoudre_sans_recursion")

    noms = {"resoudre", "normaliser", "resoudre_sans_recursion"}
    definitions = []
    for module in (projets, explorateur):
        arbre = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        definitions += [f"{Path(module.__file__).name}:{n.name}"
                        for n in ast.walk(arbre)
                        if isinstance(n, ast.FunctionDef) and n.name in noms]
    assert definitions == ["explorateur.py:normaliser"], definitions


def test_resoudre_ne_reecrit_AUCUN_maillon_SYMBOLIQUE(tmp_path):
    """AC 6.8, sur le chemin d'`ecran_projet` : le parent SAISI, pas sa cible.

    `ecran_projet` appelle cette fonction sur ses champs `dossier_parent` et
    sur l'apercu de creation. Avec `resolve()`, taper un parent atteint par un
    lien faisait afficher sa cible reelle **avant validation** : l'ecran
    montrait un chemin que l'operateur n'avait pas donne, ce qui est la meme
    famille de mensonge qu'un apercu de creation faux.
    """
    reel = tmp_path / "volume_reel" / "montages"
    reel.mkdir(parents=True)
    atelier = tmp_path / "atelier"
    (atelier / "voisin").mkdir(parents=True)
    (atelier / "pont").symlink_to(reel)
    (atelier / "pont_du_pont").symlink_to(atelier / "pont")

    # Le chemin PRIS, et pas la cible reelle -- sur un maillon comme sur deux.
    assert projets.resoudre(str(atelier / "pont")) == atelier / "pont"
    assert projets.resoudre(str(atelier / "pont_du_pont")) == \
        atelier / "pont_du_pont"

    # `..` reste resolu LEXICALEMENT : « reviens d'ou tu viens », la meme regle
    # que `←`. C'est le discriminant le plus net avec `resolve()`, qui rendrait
    # ici `volume_reel/voisin`, un dossier qui n'existe pas.
    assert projets.resoudre(str(atelier / "pont" / ".." / "voisin")) == \
        atelier / "voisin"

    # `EPIC11-ARB-40` : un chemin qui n'existe pas encore se resout quand meme,
    # parce que c'est le cas nominal de la creation.
    neuf = atelier / "pont" / "projet_neuf"
    assert not neuf.exists()
    assert projets.resoudre(str(neuf)) == neuf

    # Et un chemin relatif reste resolu en absolu depuis le dossier donne
    # (`EXPERIENCE.md`, `E0-2`).
    assert projets.resoudre("dedans", depuis=atelier) == atelier / "dedans"

def _manifeste(tmp_path, lots, nom="projet", rushes=3):
    """Un projet jetable. **La fabrique produit des lots DISTINGUABLES** : c'est
    la regle des fabriques du depot, et elle mord ici -- une fixture ou tous les
    lots portent le meme etat ne demasquerait aucune erreur d'appariement entre
    un lot et le cardinal qu'il alimente.

    `rushes` est reglable pour la meme raison, un cran plus haut : tant que le
    cardinal des rushes vaut 3 comme celui des planches, une permutation des
    deux reste invisible. Les tests d'appariement passent donc une valeur qui
    ne collisionne avec aucune autre.
    """
    import json
    dossier = tmp_path / nom
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "project.json").write_text(json.dumps({
        "rushes": [{"rush_id": f"r{n}"} for n in range(rushes)],
        "lots": [{"lot_id": f"lot_{n}", "state": etat}
                 for n, etat in enumerate(lots)],
    }), encoding="utf-8")
    return dossier


def test_les_cinq_cardinaux_comptent_les_lots_par_etat_ATTEINT(tmp_path):
    """Quatre lots a quatre etats differents, dans un ordre qui n'est pas celui
    de la chaine : un comptage qui suivrait l'ordre de la liste au lieu de
    l'etat rendrait les memes chiffres sur une fixture triee."""
    dossier = _manifeste(tmp_path, ["encode", "extraction", "scan", "pdf"])
    c = projets.compter(dossier)
    assert c.rushes == 3
    assert c.lots == 4
    assert c.planches == 3, "trois lots ont ATTEINT pdf ou au-dela"
    assert c.scans == 2
    assert c.masters == 1


def test_un_lot_ENCORE_a_l_extraction_ne_compte_dans_aucun_des_trois(tmp_path):
    """Volet symetrique : le seuil est bien « a atteint », pas « a depasse »."""
    c = projets.compter(_manifeste(tmp_path, ["extraction", "extraction"]))
    assert (c.planches, c.scans, c.masters) == (0, 0, 0)
    assert c.lots == 2


def test_un_etat_INCONNU_rend_None_et_non_zero(tmp_path):
    """`None` se rendra `·`. Compter sur une machine a etats qu'on ne reconnait
    pas donnerait un chiffre faux presente comme une mesure."""
    c = projets.compter(_manifeste(tmp_path, ["pdf", "etat_venu_d_ailleurs"]))
    assert c.planches is None and c.scans is None and c.masters is None
    assert c.lots == 2, "le cardinal QUI se mesure reste mesure"


def test_les_etats_comptes_viennent_du_COEUR_et_ne_sont_pas_recopies():
    """Deux listes d'etats divergeraient au premier etat ajoute cote coeur, et
    c'est la TUI qui aurait tort sans que rien ne le dise."""
    from mixed_media_utility.io.manifest import LOT_STATES

    assert projets.ETATS_DE_LOT is LOT_STATES


def test_la_legende_porte_CINQ_lettres_distinctes():
    lettres = [lettre for lettre, _ in projets.LEGENDE_DES_CARDINAUX]
    assert len(lettres) == 5 and len(set(lettres)) == 5, lettres


#: Ce que chaque lettre de la legende designe, cote `Compteurs`. **Cette table
#: est ecrite ici, dans le test, et pas lue de la production** : la relire de
#: `LEGENDE_DES_CARDINAUX` ferait suivre au test toute permutation de celle-ci,
#: c'est-a-dire exactement le defaut qu'il existe pour voir. Le libelle de la
#: legende ne peut pas non plus servir de cle : `S` dit « scannés » quand le
#: champ s'appelle `scans` (frontiere de vocabulaire de la story 11.2).
CHAMP_PAR_LETTRE = {
    "R": "rushes", "L": "lots", "P": "planches", "S": "scans", "M": "masters",
}


def test_chaque_LETTRE_de_la_legende_designe_SON_cardinal(tmp_path):
    """L'appariement lettre <-> cardinal, mesure cote modele.

    `LEGENDE_DES_CARDINAUX` et `Compteurs.tous` sont deux tuples ecrits a deux
    endroits differents du module, et l'ecran les joint par un `zip`
    **positionnel** : permuter l'un des deux fait lire a l'operateur « 3
    planches / 2 scannes » quand c'est « 2 planches / 3 scannes ». Jusqu'ici
    rien ne l'interdisait -- le seul test de cardinalite comptait cinq lettres
    distinctes sans jamais dire laquelle est laquelle.

    La fixture porte **cinq valeurs deux a deux distinctes** (7, 4, 3, 2, 1) :
    la regle des fabriques du depot, dans sa forme la plus directe -- un
    remplissage uniforme rendrait toute permutation invisible.
    """
    # 7 rushes ; 4 lots, dont 3 ont ATTEINT `pdf` (pdf, encode, scan),
    # 2 ont atteint `scan` (encode, scan) et 1 a atteint `encode`.
    dossier = _manifeste(tmp_path, ["extraction", "pdf", "encode", "scan"],
                         rushes=7)
    c = projets.compter(dossier)
    assert (c.rushes, c.lots, c.planches, c.scans, c.masters) == (7, 4, 3, 2, 1)

    apparies = {lettre: valeur
                for (lettre, _libelle), valeur
                in zip(projets.LEGENDE_DES_CARDINAUX, c.tous)}
    assert set(apparies) == set(CHAMP_PAR_LETTRE), apparies
    for lettre, champ in CHAMP_PAR_LETTRE.items():
        assert apparies[lettre] == getattr(c, champ), (
            f"la lettre {lettre} est appariee a {apparies[lettre]}, alors que "
            f"{champ} vaut {getattr(c, champ)}"
        )


def test_compter_ne_LIT_que_le_manifeste_et_ne_PARCOURT_aucun_dossier(
        tmp_path, monkeypatch):
    """La frontiere d'`EPIC11-ARB-30` : **aucun comptage sur le disque**.

    Les trois cardinaux de fin de chaine se deduisent de l'etat de chaque lot
    dans le manifeste deja charge ; les compter en listant `planches/`,
    `scans/` ou `masters/` ferait ecrire a la TUI un jugement metier que le
    coeur ne porte pas, et bloquerait la liste sur un volume lent (`E0-1`).
    C'etait vrai en fait et mesure par rien : un `glob` ajoute plus tard serait
    passe inapercu.

    La fixture pose les trois dossiers ou un comptage naif irait chercher ses
    chiffres, et **rend fatal** tout parcours de repertoire.
    """
    dossier = _manifeste(tmp_path, ["extraction", "pdf", "encode", "scan"],
                         rushes=7)
    for atelier in ("planches", "scans", "masters"):
        (dossier / atelier).mkdir()
        (dossier / atelier / "un_fichier").write_text("x", encoding="utf-8")

    lus: list[Path] = []
    vrai_read_text = Path.read_text

    def read_text_espionne(self, *args, **kwargs):
        lus.append(Path(self))
        return vrai_read_text(self, *args, **kwargs)

    def parcours_interdit(cible, *args, **kwargs):
        raise AssertionError(f"parcours de disque interdit : {cible!r}")

    monkeypatch.setattr(Path, "read_text", read_text_espionne)
    for nom in ("iterdir", "glob", "rglob"):
        monkeypatch.setattr(Path, nom, parcours_interdit)
    monkeypatch.setattr(os, "scandir", parcours_interdit)
    monkeypatch.setattr(os, "listdir", parcours_interdit)
    monkeypatch.setattr(os, "walk", parcours_interdit)

    c = projets.compter(dossier)

    assert lus == [dossier / projets.NOM_FICHIER_PROJET], (
        "compter() ne doit ouvrir que le manifeste du projet", lus)
    # Volet symetrique : la frontiere serait verte sur une fonction qui ne
    # compte plus rien. Les cinq cardinaux sont bien la, et justes.
    assert (c.rushes, c.lots, c.planches, c.scans, c.masters) == (7, 4, 3, 2, 1)


def test_les_compteurs_sont_lus_du_manifest(tmp_path):
    a, _, _ = _trois_projets(tmp_path)
    manifeste = json.loads((a / "project.json").read_text(encoding="utf-8"))
    manifeste["rushes"] = [{"rush_id": "r1"}, {"rush_id": "r2"}, {"rush_id": "r3"}]
    manifeste["lots"] = [{"lot_id": "l1"}, {"lot_id": "l2"}]
    (a / "project.json").write_text(json.dumps(manifeste), encoding="utf-8")

    compteurs = projets.compter(a)
    assert (compteurs.rushes, compteurs.lots) == (3, 2)


def test_les_compteurs_valent_None_quand_le_projet_ne_se_lit_pas(tmp_path):
    """AC 1.6 : `·` tant qu'il n'est pas lu -- et `None` est ce que l'ecran
    rendra en `·`. Un `0` a la place serait un chiffre FAUX presente comme
    mesure, ce que `DESIGN.md` refuse."""
    illisible = tmp_path / "casse"
    illisible.mkdir()
    (illisible / "project.json").write_text("{ casse", encoding="utf-8")

    compteurs = projets.compter(illisible)
    assert compteurs.rushes is None
    assert compteurs.lots is None


def test_un_projet_vide_compte_zero_et_non_None(tmp_path):
    """Volet symetrique du precedent : `0` et « non lu » ne sont pas la meme
    information, et l'ecran ne doit pas les confondre."""
    a, _, _ = _trois_projets(tmp_path)
    compteurs = projets.compter(a)
    assert (compteurs.rushes, compteurs.lots) == (0, 0)


# ---------------------------------------------------------------------------
# Frontiere de lot : ce module est du calcul pur
# ---------------------------------------------------------------------------

def _racines_importees(fichier: Path) -> set[str]:
    """Les paquets de premier niveau importes par un module, lus a l'AST.

    A l'AST et pas au texte : un `grep` compterait le mot « textual » vu dans
    un commentaire ou un docstring, et resterait vert sur un import ecrit
    autrement.
    """
    import ast

    arbre = ast.parse(fichier.read_text(encoding="utf-8"))
    racines: set[str] = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            racines.update(a.name.split(".")[0] for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            racines.add((noeud.module or "").split(".")[0])
    return racines


def test_le_modele_pur_n_importe_ni_textual_ni_la_coque():
    """C'est ce qui le rend mesurable sans banc, et le banc est aveugle a deux
    familles de defauts. Mesure a l'AST, pas au texte."""
    racines = _racines_importees(Path(projets.__file__))
    assert "textual" not in racines, racines
    assert "coque" not in racines, racines


def test_l_explorateur_non_plus_n_importe_ni_textual_ni_la_coque():
    """Meme propriete, meme raison, **sur l'autre modele pur du palier**.

    La tache T1 l'exige des deux modules ; elle n'etait gardee que sur
    `projets.py`. `explorateur.py` porte tout le parcours de l'arborescence --
    fenetre, saut, rang du curseur -- et c'est precisement ce qui doit rester
    mesurable sans monter d'application : le banc n'a ni pilote de terminal ni
    ecran. Un `from textual…` ajoute la un jour ferait basculer cette surface
    dans l'angle mort, sans que rien ne le dise.
    """
    module = Path(projets.__file__).with_name("explorateur.py")
    assert module.exists(), module
    racines = _racines_importees(module)
    assert "textual" not in racines, racines
    assert "coque" not in racines, racines


def test_la_garde_du_modele_pur_MORD():
    """Volet symetrique : la lecture AST doit bien voir un import de `textual`.

    Sans lui, `_racines_importees` pourrait rendre l'ensemble vide -- sur un
    fichier illisible, ou apres une refonte de son parcours -- et les deux
    gardes ci-dessus seraient vertes en ne mesurant rien. On la mesure donc
    sur un module de la TUI qui, lui, importe bien `textual`.
    """
    coque = Path(projets.__file__).with_name("coque.py")
    assert "textual" in _racines_importees(coque)
