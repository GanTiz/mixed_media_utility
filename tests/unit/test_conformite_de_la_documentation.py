# -*- coding: utf-8 -*-
"""Story 11.14, lot D3 : la DOCUMENTATION se mesure, elle ne se relit pas.

**Le defaut que ce banc ferme, et il a ete paye le 2026-09-04.** Le lot C a
retire `--frames` de `project remove` en retrait pur (`EPIC11-ARB-220`). Le
meme jour, une frontiere de `test_conformite_sorties_nommees.py` a trouve dans
`scan_output_frames.py` un refus qui citait encore ce drapeau -- « un refus qui
nomme une sortie inexistante est un blocage sec deguise » (`EPIC11-ARB-89`),
et trois relectures ne l'avaient pas vu.

La documentation est exactement la meme classe de defaut, en pire : un exemple
de `docs/` qui cite un drapeau retire envoie l'operateur droit dans un
`unrecognized arguments`, et personne ne le voit jamais parce qu'aucun test ne
lit `docs/`. Le releve fait au moment d'ecrire ce banc l'a chiffre : **25
invocations fausses** dans les six documents du lot D3, dont deux commandes qui
n'existent pas du tout (`mmu calibrate`, `mmu reconstruct`) et une option
`--scanned` citee dans quatre fichiers.

**Ce qui se rappelle se perd ; ce qui se mesure se tient** (`CLAUDE.md`). Une
documentation juste aujourd'hui redevient fausse au prochain renommage si rien
ne la mesure -- et le prochain renommage aura lieu, celui-ci etant le
deuxieme en un mois (`EPIC11-ARB-171` puis `EPIC11-ARB-214`).

**La source de verite est le PARSEUR CONSTRUIT, pas la source de `cli.py`.**
Le banc voisin `test_conformite_sorties_nommees` lit `cli.py` a l'AST, et cette
lecture est **structurellement incomplete** -- mesure faite en ecrivant ce
banc, sur ses propres sorties :

* elle rend **11 commandes sur 17**. `relink`, `scan-write`,
  `set-default-profile`, `scan calibrate` et `scan detect` en sont absentes,
  parce que `cli.py` reassigne le meme nom de variable (`p13`) a deux parsers
  differents (lignes 4171 et 4339) : le second ecrase le premier dans sa table ;
* elle ne voit pas les options posees par une FONCTION AUXILIAIRE plutot que
  par un `add_argument` litteral -- `--profil`, partage par `scan`,
  `scan-write` et `set-default-profile`, n'y figure sur aucune.

Une frontiere batie dessus accuserait donc une documentation JUSTE. Un rouge
qui se trompe est pire que pas de frontiere : on apprend a l'ignorer. Ce banc
capture donc le parseur reellement construit par `main`, en interceptant
`parse_args`, et le parcourt : c'est le contrat que l'operateur rencontre, et
il inclut par construction tout ce qu'un auxiliaire ajoute.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
DOCS = RACINE / "docs"


class _ParseurCapture(Exception):
    """Portee du parseur construit, levee depuis `parse_args`."""

    def __init__(self, parseur):
        super().__init__("parseur capture")
        self.parseur = parseur


def _parseur_reel():
    """Le parseur que `main` construit, capture sans executer une commande.

    `main` batit son parseur en local et ne l'expose pas. Plutot que de
    relire sa source -- ce qui perd les commandes et les options posees par
    un auxiliaire --, on intercepte le premier `parse_args` : a cet instant
    le parseur est complet et rien n'a encore ete execute.
    """
    if str(RACINE / "src") not in sys.path:
        sys.path.insert(0, str(RACINE / "src"))
    from mixed_media_utility import cli

    origine = argparse.ArgumentParser.parse_args

    def _intercepter(self, *args, **kwargs):
        raise _ParseurCapture(self)

    argparse.ArgumentParser.parse_args = _intercepter
    try:
        cli.main([])
    except _ParseurCapture as capture:
        return capture.parseur
    finally:
        argparse.ArgumentParser.parse_args = origine
    raise AssertionError(
        "`cli.main` n'a appele aucun `parse_args` : la capture du parseur ne "
        "mesure plus rien.")


def _parcourir(parseur, prefixe: str, table: dict[str, set[str]]) -> None:
    """Ranger les options de chaque (sous-)commande sous son nom complet."""
    options = {
        chaine
        for action in parseur._actions
        for chaine in action.option_strings
        if chaine.startswith("--")
    }
    if prefixe:
        table[prefixe] = options
    for action in parseur._actions:
        if isinstance(action, argparse._SubParsersAction):
            for nom, sous in action.choices.items():
                _parcourir(sous, f"{prefixe} {nom}".strip(), table)


def _drapeaux_par_commande() -> dict[str, set[str]]:
    """Les `--drapeau` de chaque commande, lus du parseur construit."""
    table: dict[str, set[str]] = {}
    _parcourir(_parseur_reel(), "", table)
    return table


def _sans_accents(texte: str) -> str:
    """Comparer une prose accentuee a un identifiant ASCII.

    Les natures d'objet sont des identifiants (`frames_scannees`) ; la
    documentation est de la prose francaise accentuee (« frames scannées »).
    Sans ce pliage, la frontiere exigerait de la doc qu'elle ecrive les
    identifiants -- c'est-a-dire l'inverse de ce qu'elle doit enseigner.
    """
    plie = unicodedata.normalize("NFD", texte)
    return "".join(c for c in plie if unicodedata.category(c) != "Mn")


# ---------------------------------------------------------------------------
# Les documents, et la DETTE hors lot -- nommee ici, jamais en commentaire
# ---------------------------------------------------------------------------

#: Les documents dont la conformite est TENUE : les six du lot D3, plus les
#: deux pages de `reference/` **promues le 2026-09-07**.
#:
#: La promotion n'est pas un choix de confort, c'est ce que
#: `test_la_DETTE_est_encore_reelle` a EXIGE : la passe de documentation du
#: 2026-09-07 a reecrit `reference/commandes.md` et `reference/configuration.md`
#: depuis l'arbre argparse reel, `--scanned` et `--chain-id` ont disparu, et la
#: dette a donc rougi comme elle etait faite pour le faire. Une liste
#: d'exceptions qui se vide est une liste d'exceptions qui a servi.
DOCUMENTS_TENUS: tuple[str, ...] = (
    "guide-utilisateur/concepts.md",
    "guide-utilisateur/workflow.md",
    "guide-utilisateur/cli.md",
    "guide-utilisateur/tui.md",
    "guide-developpeur/architecture.md",
    "test-chaine-scan-epic5.md",
    "reference/commandes.md",
    "reference/configuration.md",
)

#: Les documents qui citent encore une commande d'avant, avec leur ORIGINE.
#:
#: Ils sont hors du perimetre du lot D3 (`docs/reference/` et les deux manuels
#: de la periode POC) et ne sont pas corriges ici : elargir le scope d'une
#: story pour absorber un finding est exactement ce que `CLAUDE.md` interdit.
#: Ils sont **nommes** plutot qu'enterres, et
#: `test_la_DETTE_est_encore_reelle` les rendra rouges quand ils seront
#: corriges -- ce qui force a les promouvoir dans `DOCUMENTS_TENUS` au lieu de
#: laisser la dette verte pour toujours.
DETTE_HORS_LOT: dict[str, str] = {
    "USAGE.md": "manuel de la periode POC : `extract-frames`, `gen-gabarit`, "
                "`apply-calibration`, sous-commandes qui n'existent plus",
    "HELP_MENU.md": "menu d'aide de la periode POC : `extract-frames`, "
                    "`gen-gabarit`",
    "test-atelier-extraction-tui.md":
        "TROUVE PAR CETTE FRONTIERE le 2026-09-04, et ce n'est pas un reste de "
        "renommage : la commande y est ecrite `--projet` (avec un E) et "
        "`--rush`, la ou `extract` attend `--project` et `--video`. Un lecteur "
        "qui la recopie recoit un `unrecognized arguments` immediat. Hors du "
        "perimetre du lot D3 : signale plutot que corrige en elargissant le "
        "scope (`CLAUDE.md`).",
}


# ---------------------------------------------------------------------------
# Le releve : chaque invocation citee dans `docs/`
# ---------------------------------------------------------------------------

#: Les trois facons dont un document appelle la ligne de commande. Le `(?<![/\w.])`
#: est ce qui empeche `src/mixed_media_utility/cli.py` -- une ligne de
#: `pyinstaller` dans `DEPLOYMENT.md` -- d'etre lu comme une invocation.
_APPEL = re.compile(
    r"(?<![/\w.-])(?:mmu|mixed-media-util|python3? -m mixed_media_utility\.cli)"
    r"(?![=\w.-])"
    r"((?:\s+\\\n|[^\n`|&;])*)")


def _noms_de_commande(par_commande: dict[str, set[str]]) -> set[str]:
    """Tous les SEGMENTS de nom de commande, `scan` comme `calibrate`."""
    segments: set[str] = set()
    for commande in par_commande:
        segments.update(commande.split())
    segments.discard("")
    return segments


def _invocations_des_docs(par_commande: dict[str, set[str]], racine: Path = None):
    """Rendre `(document, commande, drapeaux)` pour chaque appel cite.

    **La sous-commande n'est pas forcement le mot qui suit.** `scan` porte ses
    options AVANT sa sous-commande (`mmu scan --project X --dpi 600 calibrate
    --nom Y`), et `makepdf` aussi. On ne lit donc pas les deux premiers mots :
    on cherche, parmi TOUS les jetons de l'invocation, ceux qui sont des noms
    de commande connus, dans leur ordre d'apparition.

    Limite connue et dite plutot que tue : une VALEUR d'option qui vaudrait
    exactement un nom de commande (`--lot scan`) serait lue comme une
    sous-commande. Aucun document n'en porte aujourd'hui, et le cas se verrait
    en rouge plutot qu'en silence.
    """
    racine = DOCS if racine is None else racine
    segments = _noms_de_commande(par_commande)
    for document in sorted(racine.rglob("*.md")):
        texte = document.read_text(encoding="utf-8")
        relatif = document.relative_to(racine).as_posix()
        for trouve in _APPEL.finditer(texte):
            queue = trouve.group(1).replace("\\\n", " ")
            jetons = queue.split()
            mots = [j for j in jetons if j in segments]
            commande = ""
            for cardinal in (2, 1):
                candidat = " ".join(mots[:cardinal])
                if candidat and candidat in par_commande:
                    commande = candidat
                    break
            if not commande:
                # Un appel sans aucun nom connu : soit `--help` nu, soit une
                # commande qui n'existe pas. On ne rend que le second cas.
                premier = next((j for j in jetons if not j.startswith("-")), "")
                # Seul un jeton qui RESSEMBLE a un nom de commande est
                # denonce. Sans ce filtre, l'alias `mmu='python -m ...'` et le
                # `"$@"` d'un wrapper seraient lus comme des commandes
                # inconnues -- deux faux rouges sur une documentation juste.
                if re.fullmatch(r"[a-z][a-z-]*", premier):
                    yield (relatif, premier, ())
                continue
            drapeaux = tuple(
                j for j in jetons if re.fullmatch(r"--[a-z][a-z-]*", j))
            yield (relatif, commande, drapeaux)


def _drapeaux_admis(par_commande: dict[str, set[str]], commande: str) -> set[str]:
    """Les drapeaux d'une commande ET de ses parents.

    `mmu scan --project X --dpi 600 calibrate --nom Y` est une seule ligne qui
    porte legitimement les options de `scan` et celles de `calibrate` : les
    exiger sur la seule sous-commande ferait rougir une invocation juste.
    """
    admis: set[str] = set()
    mots = commande.split()
    for cardinal in range(1, len(mots) + 1):
        admis |= par_commande.get(" ".join(mots[:cardinal]), set())
    return admis


def _ecarts(document_filtre=None) -> list[str]:
    """Les invocations fautives, une ligne par faute."""
    par_commande = _drapeaux_par_commande()
    ecarts: list[str] = []
    for document, commande, drapeaux in _invocations_des_docs(par_commande):
        if document_filtre is not None and document != document_filtre:
            continue
        if commande not in par_commande:
            ecarts.append(f"{document}: `mmu {commande}` n'est pas une commande")
            continue
        admis = _drapeaux_admis(par_commande, commande)
        for drapeau in drapeaux:
            if drapeau not in admis:
                ecarts.append(
                    f"{document}: `mmu {commande}` n'accepte pas {drapeau}")
    return ecarts


# ---------------------------------------------------------------------------
# AC 4.5 -- aucune ligne de commande de `docs/` ne cite un nom retire
# ---------------------------------------------------------------------------


def test_la_lecture_des_drapeaux_MESURE_encore_quelque_chose():
    """Garde-fou : si la lecture cassait, tout passerait pour vert.

    Sans lui, un `cli.py` renomme ou un `argparse` restructure rendrait un
    dictionnaire vide, et **toutes** les assertions de ce fichier deviendraient
    des tautologies.
    """
    par_commande = _drapeaux_par_commande()
    assert "--lot-scanne" in par_commande.get("project remove", set()), (
        f"la lecture des drapeaux par commande a rendu {sorted(par_commande)} : "
        "la frontiere ne mesure plus rien."
    )
    # Les DEUX maillons retires de la meme chaine de renommages -- `--frames`
    # (`EPIC11-ARB-220`) puis `--frames-scannees` (`EPIC11-ARB-224`). Un seul
    # controle negatif laisserait revenir l'autre, et c'est exactement ce
    # qu'une frontiere par nom existe pour empecher.
    for retire in ("--frames", "--frames-scannees"):
        assert retire not in par_commande.get("project remove", set()), (
            f"`{retire}` est revenu sur `project remove` : le retrait est PUR, "
            "sans alias.")


def test_le_releve_des_docs_MESURE_encore_quelque_chose():
    """Second garde-fou : un motif trop etroit rendrait zero invocation.

    Une frontiere qui ne lit rien est verte. C'est le mode de panne exact que
    `CLAUDE.md` nomme (« un compteur qui court n'est pas un producteur
    vivant »), transpose au balayage d'un dossier.
    """
    par_commande = _drapeaux_par_commande()
    releve = list(_invocations_des_docs(par_commande))
    assert len(releve) > 40, (
        f"seulement {len(releve)} invocations relevees dans docs/ : le motif "
        "ne lit plus les documents."
    )
    documents = {document for document, _, _ in releve}
    assert len(documents) >= 5, (
        f"les invocations ne viennent que de {sorted(documents)}")


def test_le_releve_lit_le_PREMIER_et_le_DERNIER_document(tmp_path):
    """Regle des fabriques, point 4 : une cible a CHAQUE BORD.

    Un balayage tronque -- un `[:-1]` ou un `[1:]` sur la liste des documents
    -- reste vert tant que toutes les cibles sont au milieu. C'est le mutant
    survivant du lot A de la 11.11, et il mord ici de la meme facon puisque
    `rglob` est trie.

    **PREMIERE REDACTION TAUTOLOGIQUE, tuee par mutation.** Elle calculait ses
    deux bords depuis la sortie du collecteur lui-meme : un `[:-1]` deplacait
    simplement le bord, et les mutants `M5` et `M6` SURVIVAIENT. C'est le
    defaut exact que le lot C a paye le meme jour (« le temoin de bord ne
    mesurait que l'appariement, pas le COLLECTEUR »), et le remede est le
    sien : un corpus miniature, ecrit ici, traverse par le collecteur.

    Les trois documents portent des invocations **distinguables** -- trois
    commandes differentes, pas un remplissage uniforme : une permutation ou
    une troncature ne se voit que si les elements different.
    """
    par_commande = _drapeaux_par_commande()
    (tmp_path / "a-tete.md").write_text(
        "```bash\nmmu extract --project d --video r.mp4 --fps 5\n```\n",
        encoding="utf-8")
    (tmp_path / "m-milieu.md").write_text(
        "```bash\nmmu makepdf --project d --lot l\n```\n", encoding="utf-8")
    (tmp_path / "z-queue.md").write_text(
        "```bash\nmmu encode --project d --lot l --profile prores_hq\n```\n",
        encoding="utf-8")

    releve = list(_invocations_des_docs(par_commande, racine=tmp_path))
    par_document = {document: commande for document, commande, _ in releve}
    assert par_document == {
        "a-tete.md": "extract",
        "m-milieu.md": "makepdf",
        "z-queue.md": "encode",
    }, (
        "Le collecteur ne rend pas les trois documents du corpus temoin. Une "
        "cible perdue en TETE ou en QUEUE est un balayage tronque, pas un "
        "detail : c'est le mode de panne du point 4 de la regle des fabriques."
    )


def test_le_releve_lit_bien_le_DOSSIER_docs_du_depot():
    """Volet symetrique du temoin de bord : le corpus reel est bien parcouru.

    Sans lui, le test precedent serait satisfait par un collecteur qui ne
    lirait QUE ce qu'on lui donne en parametre -- vert sur la fabrique, aveugle
    sur `docs/`.
    """
    par_commande = _drapeaux_par_commande()
    portant = {document for document, _, _ in _invocations_des_docs(par_commande)}
    assert len(portant) >= 8, f"seuls {sorted(portant)} sont parcourus"
    assert "guide-utilisateur/cli.md" in portant


def test_tout_drapeau_cite_dans_la_DOC_TENUE_existe_sur_SA_commande():
    """Le coeur de l'AC 4.5, sur les six documents du lot D3."""
    ecarts = [ecart for ecart in _ecarts()
              if ecart.split(":")[0] in DOCUMENTS_TENUS]
    assert ecarts == [], (
        "Ces exemples de documentation citent une commande ou un drapeau qui "
        "n'existe pas. Un texte qui nomme une sortie inexistante envoie le "
        "lecteur dans un refus (EPIC11-ARB-89):\n  " + "\n  ".join(ecarts)
    )


def test_aucun_document_HORS_dette_n_est_fautif():
    """Le volet symetrique : un document neuf ne se glisse pas non trie.

    Sans lui, la frontiere serait satisfaite en ajoutant chaque nouveau
    document a `DETTE_HORS_LOT`. Ici, tout document qui n'est ni tenu ni
    inscrit a la dette doit etre juste.
    """
    connus = set(DOCUMENTS_TENUS) | set(DETTE_HORS_LOT)
    ecarts = [ecart for ecart in _ecarts() if ecart.split(":")[0] not in connus]
    assert ecarts == [], (
        "Ces documents ne sont ni tenus ni inscrits a la dette, et ils citent "
        "une commande ou un drapeau inexistant :\n  " + "\n  ".join(ecarts)
    )


@pytest.mark.parametrize("document", sorted(DETTE_HORS_LOT))
def test_la_DETTE_est_encore_reelle(document):
    """Une dette qui se corrige doit ROUGIR, pas rester verte en silence.

    C'est le mecanisme de l'`xfail(strict=True)` du lot A, transpose : le jour
    ou l'un de ces documents est mis a jour, ce test rougit et force a le
    promouvoir dans `DOCUMENTS_TENUS`. Une liste d'exceptions qui ne se vide
    jamais est une tolerance permanente deguisee.
    """
    assert (DOCS / document).exists(), (
        f"{document} a disparu ou a ete renomme : retirer son entree de "
        "DETTE_HORS_LOT.")
    assert _ecarts(document) != [], (
        f"{document} ne cite plus aucune commande d'avant. Retirer son entree "
        f"de DETTE_HORS_LOT et l'ajouter a DOCUMENTS_TENUS.\n"
        f"Origine de la dette : {DETTE_HORS_LOT[document]}")


def test_la_frontiere_MORD_sur_un_drapeau_INVENTE(tmp_path):
    """Controle negatif : un drapeau qui n'existe nulle part est attrape."""
    par_commande = _drapeaux_par_commande()
    faux = tmp_path / "faux.md"
    faux.write_text(
        "```bash\nmmu project remove --project d --lot l --drapeau-invente\n```\n",
        encoding="utf-8")
    trouve = _APPEL.search(faux.read_text(encoding="utf-8"))
    assert trouve, "le motif ne reconnait meme pas une invocation citee"
    drapeaux = re.findall(r"--[a-z][a-z-]*", trouve.group(1))
    assert "--drapeau-invente" in drapeaux
    assert "--drapeau-invente" not in _drapeaux_admis(par_commande,
                                                      "project remove")


def test_la_frontiere_MORD_sur_un_drapeau_REEL_d_une_AUTRE_commande():
    """Le trou qu'une frontiere PLATE ne voit pas.

    Un drapeau invente est attrape meme par une frontiere qui ne verifierait
    que « ce nom existe quelque part dans la CLI ». Le cas qui la demasque est
    un drapeau REEL, mais d'une autre commande -- c'est le defaut trouve en
    couche 3 sur le banc voisin, et il se transpose tel quel.
    """
    par_commande = _drapeaux_par_commande()
    assert "--video" not in _drapeaux_admis(par_commande, "project remove"), (
        "`--video` est devenu un drapeau de `project remove` : ce controle "
        "negatif doit etre reecrit sur un autre drapeau.")
    assert "--video" in _drapeaux_admis(par_commande, "extract")


def test_la_frontiere_MORD_sur_une_COMMANDE_qui_n_existe_pas(tmp_path):
    """Controle negatif du second mode de panne : le nom de commande."""
    par_commande = _drapeaux_par_commande()
    assert "calibrate" not in par_commande, (
        "`mmu calibrate` est devenu une commande de premier niveau : ce "
        "controle negatif doit viser un autre nom.")
    assert "reconstruct" not in par_commande, (
        "`mmu reconstruct` existe desormais : la commande reelle etait "
        "`reconstruct-project`.")


# ---------------------------------------------------------------------------
# AC 6.3 -- l'arborescence dessinee est celle que le code ECRIT
# ---------------------------------------------------------------------------

CONCEPTS = DOCS / "guide-utilisateur" / "concepts.md"


def _dossiers_dessines_dans_concepts() -> set[str]:
    """Les dossiers de premier niveau du schema d'arborescence de concepts.md.

    Lus depuis le bloc qui suit le titre « Architecture des donnees », a la
    seule profondeur 1 : les sous-dossiers y sont des exemples (`<slug>/`), pas
    des noms fixes.
    """
    texte = CONCEPTS.read_text(encoding="utf-8")
    debut = texte.index("## Architecture des données")
    bloc = texte[debut:].split("```")[1]
    return set(re.findall(r"^(?:├──|└──) ([a-z][a-z-]*)/", bloc, re.MULTILINE))


def _dossiers_que_le_code_ecrit() -> set[str]:
    """Les noms de dossier ECRITS, lus du code et jamais recopies ici."""
    import sys
    sys.path.insert(0, str(RACINE / "src"))
    from mixed_media_utility.io import project_layout as gabarit

    return set(gabarit.BASE_SUBDIRS) | {
        gabarit.EXTRACT_FRAMES_DIRNAME,
        gabarit.SCAN_FRAMES_DIRNAME,
        gabarit.OUTPUTS_DIRNAME,
    }


def test_l_arborescence_de_concepts_est_EXACTEMENT_celle_que_le_code_ecrit():
    """Egalite d'ENSEMBLES, dans les deux sens -- jamais de cardinaux.

    « Un cardinal stable n'est pas une preuve » : le lot B a mesure 147 noms
    ambigus avant ET apres son renommage, deux etant sortis et un neuf etant
    entre. Un dossier retire de la doc et un dossier invente s'annuleraient
    dans un compte.

    C'est cette assertion qui rendra la documentation ROUGE au prochain
    renommage de dossier, au lieu de la laisser perimer en silence -- ce que
    `frames/` et `output-frames/` ont fait pendant toute la story 11.14.
    """
    dessines = _dossiers_dessines_dans_concepts()
    ecrits = _dossiers_que_le_code_ecrit()
    assert dessines, "le schema d'arborescence de concepts.md n'a pas ete lu"
    assert dessines == ecrits, (
        "L'arborescence dessinee dans concepts.md n'est plus celle que le code "
        f"ecrit.\n  dessines et jamais ecrits : {sorted(dessines - ecrits)}"
        f"\n  ecrits et jamais dessines : {sorted(ecrits - dessines)}")


def test_les_ANCIENS_noms_de_dossier_ne_sont_PAS_dessines():
    """Frontiere negative (AC 2.3, volet documentaire).

    Les noms d'avant sont **reconnus en lecture, jamais ecrits**
    (`EPIC11-ARB-171`). Un schema qui les dessine comme l'arborescence
    courante enseigne le contraire.
    """
    import sys
    sys.path.insert(0, str(RACINE / "src"))
    from mixed_media_utility.io import project_layout as gabarit

    dessines = _dossiers_dessines_dans_concepts()
    for ancien in (gabarit.LEGACY_FRAMES_DIRNAME,
                   gabarit.LEGACY_OUTPUT_FRAMES_DIRNAME,
                   gabarit.LEGACY_SOURCES_DIRNAME):
        assert ancien not in dessines, (
            f"`{ancien}/` est dessine comme un dossier courant, alors qu'il "
            "n'est plus jamais ecrit.")


def test_les_ANCIENS_noms_sont_DITS_quelque_part_dans_concepts():
    """`EPIC11-ARB-222` : le sort d'un vieux projet doit etre DIT.

    Volet symetrique du test precedent, et sans lui il serait satisfait par un
    document qui ne parlerait pas du tout des anciens noms -- alors qu'un
    lecteur ouvrant un vieux projet verra `frames/` et `output-frames/` sur son
    disque et se demandera ce qu'il doit en faire. Le silence se paie en
    inquietude.
    """
    import sys
    sys.path.insert(0, str(RACINE / "src"))
    from mixed_media_utility.io import project_layout as gabarit

    texte = CONCEPTS.read_text(encoding="utf-8")
    for ancien in (gabarit.LEGACY_FRAMES_DIRNAME,
                   gabarit.LEGACY_OUTPUT_FRAMES_DIRNAME):
        assert f"`{ancien}/`" in texte, (
            f"concepts.md ne dit nulle part ce que devient `{ancien}/` "
            "(EPIC11-ARB-222 : reconnu en lecture, jamais ecrit, aucune "
            "conversion).")
    assert "conversion" in texte, (
        "concepts.md ne dit pas qu'il n'existe NI commande de conversion NI "
        "conversion automatique (EPIC11-ARB-222).")


def test_l_ecart_du_MANIFESTE_est_dit_plutot_que_tu():
    """`EPIC11-ARB-221` : le manifeste garde ses cles, et la doc le dit.

    « Le manifeste continuera de dire `output_frames_dir` la ou toute
    l'interface dit "frames scannees". [...] C'est le prix explicitement
    accepte. » Un ecart assume qui n'est ecrit nulle part n'est plus assume :
    c'est une incoherence que le lecteur decouvre seul.
    """
    texte = CONCEPTS.read_text(encoding="utf-8")
    assert "output_frames_dir" in texte, (
        "concepts.md ne nomme pas la cle `output_frames_dir`, alors que "
        "l'utilisateur peut ouvrir le manifeste et l'y lire (EPIC11-ARB-221).")
    # Nommer la cle ne suffit pas : il faut DIRE qu'elle ne change pas. Sans
    # cette seconde moitie, retirer toute la section laissait le test vert --
    # le mutant `M4` y a survecu a la premiere redaction.
    assert "noms de cles" in _sans_accents(texte), (
        "concepts.md nomme `output_frames_dir` mais ne dit nulle part que les "
        "NOMS DE CLES du manifeste ne changent pas (EPIC11-ARB-221). Un ecart "
        "assume qui n'est ecrit nulle part n'est plus assume.")


# ---------------------------------------------------------------------------
# Le vocabulaire ENSEIGNE : les huit natures, lues et jamais recopiees
# ---------------------------------------------------------------------------


def test_concepts_ENSEIGNE_les_huit_natures_publiees():
    """AC 6.3 : `concepts.md` est le seul lieu ou ces mots sont DEFINIS.

    La liste des natures est **lue** de `project_inventory.NATURES`, jamais
    recopiee : `project_inventory` reste le seul lieu du depot ou le
    vocabulaire est redige (AC 1.1), y compris vis-a-vis de ce banc.
    """
    import sys
    sys.path.insert(0, str(RACINE / "src"))
    from mixed_media_utility.project_inventory import NATURES

    texte = CONCEPTS.read_text(encoding="utf-8").lower()
    # `frames_extraites` s'enseigne « frames extraites » : la nature est un
    # identifiant, le document est de la prose.
    texte = _sans_accents(texte)
    manquantes = [nature for nature in NATURES
                  if nature.replace("_", " ") not in texte]
    assert manquantes == [], (
        "concepts.md n'enseigne pas ces natures d'objet, alors qu'il est le "
        f"seul document qui les definisse : {manquantes}")


def test_concepts_pose_la_distinction_CONTENANT_contenu():
    """Le coeur du lot D3, et la distinction que la story a fait apparaitre.

    Le CONTENANT versionne est un **lot scanne** ; le CONTENU est un **jeu de
    frames scannees**. Les deux libelles sont ceux que le produit a deja poses
    (`cli.py`, `project_maintenance.py`) : la doc ne doit pas en inventer un
    troisieme, ce qui serait exactement l'ambiguite que la story retire.
    """
    texte = CONCEPTS.read_text(encoding="utf-8").lower()
    assert "contenant" in texte and "contenu" in texte, (
        "concepts.md ne pose pas explicitement la distinction contenant / "
        "contenu, qui est ce que la story 11.14 a fait apparaitre.")
    assert "lot scanné" in texte, "le libelle « lot scanné » manque"
    assert "frames scannées" in texte, "le libelle « frames scannées » manque"


def test_aucun_document_TENU_ne_dit_plus_frames_rescannees():
    """« rescannees » n'etait le mot de personne.

    Ni celui du disque (`output-frames/`), ni celui du manifeste, ni celui
    d'Egan -- c'est ecrit dans `project_inventory.py`. Frontiere negative sur
    les six documents tenus.
    """
    fautifs = []
    for relatif in DOCUMENTS_TENUS:
        texte = _sans_accents(
            (DOCS / relatif).read_text(encoding="utf-8").lower())
        # C'est « frames rescannees » qui est proscrit, pas le verbe
        # « rescanner » : rescanner une planche est un geste reel
        # (`EPIC11-ARB-105`), et le rang de `--lot-scanne` porte
        # justement sur la passe de rescan.
        if "frames rescann" in texte or "rescannees (" in texte:
            fautifs.append(relatif)
    assert fautifs == [], (
        "Ces documents disent encore « rescannees », un mot qui n'est celui "
        f"d'aucune surface du produit : {fautifs}")


# ===========================================================================
# Les blocs a COPIER-COLLER se rendent la ou on les lit
# ===========================================================================

#: Les documents que cette frontiere garde : tout `docs/` plus le `README.md`,
#: c'est-a-dire exactement ce qu'un visiteur du depot ouvre.
def _documents_de_lecture() -> list[Path]:
    return sorted(DOCS.rglob("*.md")) + [RACINE / "README.md"]


def blocs_avales(texte: str) -> list[int]:
    """Les numeros de ligne des ouvertures de bloc qu'un rendu CommonMark AVALE.

    **Le defaut que ceci ferme, et Egan l'a trouve a la lecture, pas un banc**
    (2026-09-08, la veille de la publication, sur `installation/windows.md`) :
    « les blocs a copier coller sont eux memes dans d'autres blocs et ne
    fonctionnent pas ».

    **Le mecanisme, mesure.** Les pages employaient les onglets de MkDocs
    Material (`=== "En une commande"`), dont le corps s'indente de quatre
    espaces. `pymdownx.tabbed` etant actif, le SITE les rendait correctement.
    GitHub, lui, suit CommonMark : `=== "x"` y est un simple paragraphe, et
    les quatre espaces qui suivent font un **bloc de code indente**. Toute
    cloture ```` ``` ```` qui vit dedans est alors rendue LITTERALEMENT -- la
    commande apparait dans un bloc dans un bloc, et ne se copie plus.

    Releve du jour : **35 ouvertures avalees** sur six pages, dont 24 en
    onglets et 11 en admonitions. Et la surface qui comptait etait GitHub :
    `docs.yml` ne deploie les Pages que sur declenchement MANUEL, le site
    n'avait jamais ete publie, et le `README.md` pointe ces pages par chemin
    relatif -- donc cent pour cent des lecteurs voyaient la version cassee.

    **Ce que la mesure NE compte PAS, et c'est ce qui la rend utilisable.**
    Une indentation est LEGITIME sous une puce ou un numero : le bloc y
    appartient a l'element de liste, et GitHub le rend correctement. Une
    frontiere qui compterait toute ouverture indentee accuserait donc une
    documentation juste -- et « un rouge qui se trompe est pire que pas de
    frontiere : on apprend a l'ignorer », ce que l'en-tete de ce module dit
    deja. L'etat de liste est donc suivi, et l'interieur des blocs aussi : un
    exemple qui MONTRE du markdown en porte legitimement.
    """
    avalees: list[int] = []
    dans_un_bloc = False
    marque_ouvrante = ""
    indentation_de_liste: int | None = None
    for numero, ligne in enumerate(texte.splitlines(), start=1):
        depouillee = ligne.lstrip(" ")
        indentation = len(ligne) - len(depouillee)
        if dans_un_bloc:
            # **Une cloture est NUE**, et cette nuance a ete trouvee par le
            # volet symetrique, pas par la relecture. CommonMark n'accepte
            # comme cloture qu'une ligne faite des seuls caracteres de la
            # marque : une ouverture imbriquee `` ```powershell `` ne ferme
            # donc pas le bloc exterieur. Sans cette regle, un document qui
            # MONTRE la syntaxe fautive -- ce banc lui-meme -- se faisait
            # accuser par sa propre mesure.
            if depouillee.rstrip() == marque_ouvrante * (
                    len(depouillee.rstrip()) // len(marque_ouvrante)) and (
                    set(depouillee.rstrip()) == {marque_ouvrante[0]}):
                dans_un_bloc = False
            continue
        if depouillee.startswith("```") or depouillee.startswith("~~~"):
            dans_un_bloc = True
            marque_ouvrante = depouillee[:3]
            # Sous une liste, l'indentation est portee par l'element : elle est
            # juste, et le rendu GitHub la suit.
            if indentation >= 4 and indentation_de_liste is None:
                avalees.append(numero)
            continue
        if not ligne.strip():
            continue
        marqueur = re.match(r"^ *(?:[-*+]|\d+[.)]) ", ligne)
        if marqueur:
            indentation_de_liste = len(marqueur.group(0))
        elif indentation == 0:
            indentation_de_liste = None
    return avalees


@pytest.mark.parametrize(
    "document", _documents_de_lecture(),
    ids=lambda chemin: str(chemin.relative_to(RACINE)))
def test_aucun_bloc_a_COPIER_COLLER_n_est_avale_par_une_indentation(document):
    """Le volet qui garde la correction du 2026-09-08."""
    avalees = blocs_avales(document.read_text(encoding="utf-8"))
    assert avalees == [], (
        f"{document.relative_to(RACINE)} : ouverture(s) de bloc indentee(s) de "
        f"quatre espaces hors liste, aux lignes {avalees}. Un rendu CommonMark "
        "-- GitHub -- les met DANS un bloc de code indente, et la commande "
        "cesse d'etre copiable. C'est le defaut du 2026-09-08 : les onglets "
        "`=== \"...\"` et les admonitions `!!!` de Material indentent leur "
        "corps, et le site seul les rendait. Aplatir en titre `###`, ou sortir "
        "le bloc de l'indentation.")


def test_le_releve_des_blocs_LIT_encore_quelque_chose():
    """Volet d'anti-vacuite : sans lui, un motif casse rendrait tout vert.

    Les deux cardinaux sont bornes par le bas -- les documents parcourus, et
    les blocs qu'ils portent reellement. Un `rglob` qui cesserait de rendre des
    fichiers, ou un suivi de bloc qui n'en verrait plus aucun, laisserait la
    frontiere ci-dessus verte en n'observant RIEN.
    """
    documents = _documents_de_lecture()
    assert len(documents) >= 20, f"{len(documents)} document(s) parcouru(s)"
    portant_un_bloc = [d for d in documents
                       if "```" in d.read_text(encoding="utf-8")]
    assert len(portant_un_bloc) >= 10, (
        f"{len(portant_un_bloc)} document(s) portant un bloc de code")


def test_la_frontiere_MORD_sur_un_bloc_REINDENTE():
    """Le volet negatif, et c'est le seul qui prouve que la mesure mesure.

    On rejoue la forme EXACTE du defaut -- un onglet Material et une
    admonition, tels que les six pages les portaient avant le 2026-09-08.
    """
    onglet = '=== "En une commande"\n\n    ```powershell\n    irm ... | iex\n    ```\n'
    admonition = '!!! info "Un titre"\n\n    ```bash\n    mmu --help\n    ```\n'
    assert blocs_avales(onglet) == [3], blocs_avales(onglet)
    assert blocs_avales(admonition) == [3], blocs_avales(admonition)


def test_la_frontiere_NE_MORD_PAS_sur_un_bloc_legitime_de_LISTE():
    """Le volet symetrique, et il vaut autant que le precedent.

    Sans lui, la frontiere se durcirait jusqu'a interdire une forme JUSTE :
    sous une puce ou un numero, l'indentation appartient a l'element de liste
    et GitHub la rend correctement. Les deux marqueurs sont joues -- une
    numerotation ne s'indente pas comme une puce --, et la sortie de liste
    aussi : un bloc indente APRES le retour au niveau zero est de nouveau
    fautif, sinon une seule puce en tete de page desarmerait toute la suite.
    """
    puce = "* Faire ceci :\n\n    ```bash\n    mmu --help\n    ```\n"
    numero = "1. Faire ceci :\n\n    ```bash\n    mmu --help\n    ```\n"
    assert blocs_avales(puce) == []
    assert blocs_avales(numero) == []
    apres_la_liste = puce + "\nUn paragraphe au niveau zero.\n\n    ```bash\n    x\n    ```\n"
    assert blocs_avales(apres_la_liste) == [9], blocs_avales(apres_la_liste)


def test_la_frontiere_NE_MORD_PAS_sur_du_markdown_MONTRE_dans_un_bloc():
    """Un document qui ENSEIGNE cette syntaxe en porte legitimement l'exemple.

    Sans le suivi d'etat, la cloture du bloc exterieur serait lue comme une
    ouverture indentee, et ce banc-ci -- qui montre justement la forme fautive
    quelques lignes plus haut -- se ferait accuser par sa propre mesure.
    """
    montre = '```markdown\n=== "Un onglet"\n\n    ```powershell\n    x\n    ```\n```\n'
    assert blocs_avales(montre) == []


# ------------------------------------------------------ la cloture qui MANQUE
#
# Ce volet-ci est le SYMETRIQUE du precedent, et il a ete pose le 2026-09-08,
# quelques heures apres lui, parce qu'il manquait : la mesure des blocs avales
# regarde l'INDENTATION d'une ouverture, jamais si une ouverture a jamais ete
# FERMEE. Un defaut reel vivait dans `docs/installation/macos.md` pendant que
# la premiere mesure tournait verte :
#
#     ### pipx, a la main
#
#     ```bash
#     brew install pipx
#     pipx ensurepath
#     ```bash                          <- une OUVERTURE, pas une cloture
#     pipx install mmu-cli
#     ```
#
# CommonMark n'accepte comme cloture qu'une ligne faite des SEULS caracteres de
# la marque -- c'est exactement ce que la fonction `blocs_avales` ci-dessus
# avait deja etabli, sur l'autre bord. Une ouverture avec langue ne ferme donc
# rien : les quatre lignes suivantes tombaient DANS le bloc, et la commande
# `pipx install mmu-cli` s'affichait a cote d'un ```` ```bash ```` litteral.
# C'est mot pour mot le defaut qu'Egan avait signale la veille -- « les blocs a
# copier coller sont eux memes dans d'autres blocs et ne fonctionnent pas » --,
# retrouve par une autre porte, sur une page que la premiere frontiere lisait
# deja.


def blocs_mal_fermes(texte: str) -> list[int]:
    """Les numeros de ligne des ouvertures de bloc qui ne se ferment PAS.

    Deux formes, et une seule mesure :

    * une **ouverture avec langue** rencontree alors qu'un bloc est deja
      ouvert, et **a la meme indentation que lui** -- c'est une cloture
      oubliee ;
    * un bloc **encore ouvert a la fin du fichier**.

    **Ce que la mesure ne compte pas, et c'est ce qui la rend utilisable.**
    Un document qui ENSEIGNE cette syntaxe porte legitimement une ouverture
    imbriquee -- le banc juste au-dessus en montre une. Elle est alors
    INDENTEE par rapport a son bloc exterieur, parce qu'elle est du contenu et
    non de la structure. L'indentation est donc le discriminant, et il est
    mesure dans les deux sens par les deux tests qui suivent.
    """
    fautives: list[int] = []
    ouverture: tuple | None = None   # (numero, marque, indentation)
    for numero, ligne in enumerate(texte.splitlines(), start=1):
        depouillee = ligne.lstrip(" ")
        indentation = len(ligne) - len(depouillee)
        if not (depouillee.startswith("```") or depouillee.startswith("~~~")):
            continue
        marque = depouillee[:3]
        reste = depouillee[3:].strip()
        if ouverture is None:
            ouverture = (numero, marque, indentation)
            continue
        # Un bloc est ouvert. Une cloture est NUE, porte la meme marque, et
        # n'est pas indentee de plus de TROIS espaces au-dela de son
        # ouverture -- au-dela, CommonMark la lit comme du CONTENU. Cette
        # derniere condition n'est pas un raffinement : sans elle, la cloture
        # indentee d'un exemple imbrique fermait le bloc exterieur, et le vrai
        # ``` final passait pour une ouverture jamais fermee. Trouve par le
        # volet symetrique, pas par la relecture.
        if (not reste and marque == ouverture[1]
                and indentation <= ouverture[2] + 3):
            ouverture = None
            continue
        # Une ouverture avec langue, au meme niveau que son bloc : cloture
        # oubliee. Le bloc courant est repute remplace par elle, sinon une
        # seule faute rendrait tout le reste du fichier illisible a ce banc.
        if reste and indentation == ouverture[2]:
            fautives.append(numero)
            ouverture = (numero, marque, indentation)
    if ouverture is not None:
        fautives.append(ouverture[0])
    return fautives


def test_AUCUN_bloc_de_code_de_la_DOC_ne_reste_OUVERT():
    """La frontiere elle-meme, sur les documents que quelqu'un lit vraiment.

    Elle rend zero au 2026-09-08, apres reparation de `macos.md`. Il n'y a
    **aucune liste de dette** ici, et c'est delibere : une cloture oubliee
    n'est pas un arbitrage editorial qu'on pourrait porter, c'est un rendu
    casse. Le jour ou une page en aurait besoin, c'est la page qu'il faut
    reprendre.
    """
    documents = _documents_de_lecture()
    assert len(documents) >= 10, (
        "seulement %d documents releves : le releve a fondu, cette frontiere "
        "ne mesure plus grand-chose" % len(documents))
    fautifs = []
    for chemin in documents:
        for numero in blocs_mal_fermes(chemin.read_text(encoding="utf-8")):
            fautifs.append("%s:%d" % (chemin.relative_to(RACINE), numero))
    assert fautifs == [], (
        "un bloc de code n'est jamais ferme, ou une ouverture avec langue tient "
        "lieu de cloture : tout ce qui suit tombe DANS le bloc et ne se copie "
        "plus. %r" % (fautifs,))


def test_la_frontiere_MORD_sur_la_CLOTURE_OUBLIEE_reellement_trouvee():
    """Le volet negatif, joue sur la forme EXACTE trouvee dans `macos.md`.

    Sans lui, la frontiere ci-dessus serait verte par construction : elle l'a
    ete tout le temps qu'elle n'existait pas.
    """
    reel = ("```bash\n"
            "brew install pipx\n"
            "pipx ensurepath\n"
            "```bash\n"
            "pipx install mmu-cli\n"
            "```\n")
    assert blocs_mal_fermes(reel) == [4], blocs_mal_fermes(reel)
    jamais_ferme = "un texte\n\n```bash\nmmu --help\n"
    assert blocs_mal_fermes(jamais_ferme) == [3], blocs_mal_fermes(jamais_ferme)


def test_la_frontiere_NE_MORD_PAS_sur_du_markdown_MONTRE_ni_sur_deux_blocs_SAINS():
    """Le volet symetrique, et il vaut autant que le precedent.

    Trois formes justes, dont deux qu'une mesure trop large accuserait :
    l'exemple imbriquE et INDENTE d'un document qui enseigne la syntaxe, et
    deux blocs successifs correctement fermes -- le cas nominal, qu'il faut
    jouer parce qu'une frontiere qui rougirait dessus rougirait partout.
    """
    montre = "```markdown\n    ```bash\n    x\n    ```\n```\n"
    assert blocs_mal_fermes(montre) == [], blocs_mal_fermes(montre)
    deux_sains = "```bash\na\n```\n\ndu texte\n\n```powershell\nb\n```\n"
    assert blocs_mal_fermes(deux_sains) == [], blocs_mal_fermes(deux_sains)
    tilde = "~~~bash\na\n~~~\n"
    assert blocs_mal_fermes(tilde) == [], blocs_mal_fermes(tilde)


# ===========================================================================
# Story 8.13 : la voie MANUELLE se mesure, et le perimetre du support se DIT
# ===========================================================================
#
# **Le defaut que ces frontieres ferment.** Les trois pages d'installation
# portaient une section « pipx, a la main » et une section « pip, dans un
# venv », et **aucune ne partait d'une machine vierge** : les deux supposent
# Python, ffmpeg et pipx deja poses. Un lecteur qui refuse `curl | bash` --
# et c'est un refus legitime -- n'avait donc que des morceaux. C'est le
# regime exact dans lequel Egan a constate qu'un pipx pose a la main n'etait
# pas detecte (`EPIC11-ARB-271`).
#
# **Pourquoi des frontieres et non une relecture.** `macos.md` a porte
# jusqu'au 2026-09-08 un bloc jamais ferme que trois relectures n'avaient pas
# vu, et le releve du meme jour a trouve 35 ouvertures avalees sur six pages.
# Une documentation se mesure ou elle derive -- c'est ce que l'en-tete de ce
# module dit deja de `docs/`, applique ici a la voie manuelle.

#: Les trois pages qui portent la voie manuelle (`EPIC11-ARB-276`).
PAGES_D_INSTALLATION = {
    "linux": DOCS / "installation" / "linux.md",
    "macos": DOCS / "installation" / "macos.md",
    "windows": DOCS / "installation" / "windows.md",
}

#: Le titre de la section, replie en ASCII : la page l'ecrit accentue.
TITRE_VOIE_MANUELLE = "depuis une machine vierge, entierement a la main"

#: Le titre de la voie « tous les utilisateurs » (`EPIC11-ARB-275`).
TITRE_TOUS_LES_UTILISATEURS = "pour tous les utilisateurs de la machine"

#: La marque, invisible au rendu, qui designe le bloc de detection. Elle
#: existe pour que la frontiere JOUE le bloc plutot que de le relire : sans
#: ancre, il faudrait le retrouver par ressemblance, et « on ne cherche
#: jamais par ressemblance, toujours par identite » (`CLAUDE.md`).
MARQUE_DU_BLOC_DE_DETECTION = "<!-- BLOC-DE-DETECTION -->"

#: Les quatre outils que le bloc de detection doit nommer.
LES_QUATRE_OUTILS = ("ffmpeg", "ffprobe", "pipx")

SCRIPTS_D_INSTALLATION = (
    RACINE / "scripts" / "install.sh",
    RACINE / "scripts" / "install.ps1",
)


def _corps_de_section(texte: str, titre_ascii: str) -> str:
    """Le corps d'une section `###`, de son titre au prochain titre de meme
    niveau ou plus haut.

    Le titre est compare **replie en ASCII et en minuscules** : la page ecrit
    « entierement a la main » avec ses accents, et exiger l'inverse
    reviendrait a demander a la documentation d'ecrire des identifiants.
    """
    lignes = texte.splitlines()
    debut = None
    for numero, ligne in enumerate(lignes):
        if not ligne.startswith("### "):
            continue
        titre = _sans_accents(ligne[4:]).lower()
        # L'ancre `{ #... }` de MkDocs ne fait pas partie du titre.
        titre = titre.split("{")[0].strip()
        if titre.startswith(titre_ascii):
            debut = numero
            break
    if debut is None:
        return ""
    for numero in range(debut + 1, len(lignes)):
        depouillee = lignes[numero]
        if depouillee.startswith("### ") or (
                depouillee.startswith("## ") and not depouillee.startswith("###")):
            return "\n".join(lignes[debut:numero])
    return "\n".join(lignes[debut:])


def _sous_titres(corps: str) -> list[str]:
    """Les titres de niveau 4 d'une section, replies en ASCII minuscule."""
    titres = []
    for ligne in corps.splitlines():
        if ligne.startswith("#### "):
            titre = _sans_accents(ligne[5:]).lower().split("{")[0].strip()
            titres.append(titre)
    return titres


def _blocs_de_code(texte: str) -> list[str]:
    """Le CONTENU de chaque bloc cloture, sans les lignes de cloture."""
    blocs: list[str] = []
    courant: list[str] | None = None
    marque = ""
    for ligne in texte.splitlines():
        depouillee = ligne.lstrip(" ")
        if courant is None:
            if depouillee.startswith("```") or depouillee.startswith("~~~"):
                courant = []
                marque = depouillee[:3]
            continue
        if depouillee.rstrip() == marque:
            blocs.append("\n".join(courant))
            courant = None
            continue
        courant.append(ligne)
    return blocs


def bloc_de_detection(texte: str) -> str:
    """Le bloc de code qui SUIT la marque, ou la chaine vide."""
    lignes = texte.splitlines()
    for numero, ligne in enumerate(lignes):
        if ligne.strip() != MARQUE_DU_BLOC_DE_DETECTION:
            continue
        blocs = _blocs_de_code("\n".join(lignes[numero:]))
        return blocs[0] if blocs else ""
    return ""


# ---------------------------------------------------------------------------
# AC1 -- la section existe, et son ORDRE est la moitie de l'information
# ---------------------------------------------------------------------------

#: Les cinq etapes, dans l'ordre qu'`EPIC11-ARB-276` impose. L'ordre n'est pas
#: un gout : installer par-dessus ce qui est deja la est la premiere facon de
#: casser une installation qui marchait, donc l'etat des lieux vient d'abord ;
#: pipx a besoin de Python, et l'application a besoin de pipx.
ETAPES_ATTENDUES = (
    r"^1\..*ce qui est deja la",
    r"^2\..*python",
    r"^3\..*ffmpeg.*ffprobe",
    r"^4\..*pipx",
    r"^5\..*application",
)


@pytest.mark.parametrize("systeme", sorted(PAGES_D_INSTALLATION))
def test_chaque_page_porte_la_voie_manuelle_DANS_L_ORDRE(systeme):
    """AC1 : la section existe, et ses cinq etapes se suivent dans cet ordre."""
    page = PAGES_D_INSTALLATION[systeme]
    corps = _corps_de_section(page.read_text(encoding="utf-8"),
                              TITRE_VOIE_MANUELLE)
    assert corps, (
        "%s ne porte aucune section `### Depuis une machine vierge, "
        "entierement a la main` : un lecteur qui refuse `curl | bash` n'a que "
        "des morceaux." % page.relative_to(RACINE))
    titres = _sous_titres(corps)
    assert len(titres) == len(ETAPES_ATTENDUES), (
        "%s : %d etapes dans la voie manuelle, %d attendues. %r"
        % (page.relative_to(RACINE), len(titres), len(ETAPES_ATTENDUES), titres))
    for rang, (titre, motif) in enumerate(zip(titres, ETAPES_ATTENDUES), start=1):
        assert re.search(motif, titre), (
            "%s : l'etape %d est %r, or l'ordre d'`EPIC11-ARB-276` attend "
            "%r a cette place. L'ordre est la moitie de l'information : pipx "
            "a besoin de Python, l'application a besoin de pipx, et l'etat "
            "des lieux vient avant tout le reste."
            % (page.relative_to(RACINE), rang, titre, motif))


def test_la_voie_manuelle_est_un_titre_de_NIVEAU_3_atteignable(systeme=None):
    """AC11 : la section est ancree dans la navigation, pas noyee en prose.

    Un titre de niveau 3 entre dans le sommaire MkDocs ; un paragraphe en gras
    n'y entre pas. C'est ce qui distingue une page qui grossit AVEC structure
    d'une page qui grossit seulement.
    """
    for nom, page in sorted(PAGES_D_INSTALLATION.items()):
        texte = page.read_text(encoding="utf-8")
        titres = [l for l in texte.splitlines()
                  if l.startswith("### ")
                  and _sans_accents(l[4:]).lower().split("{")[0].strip()
                  .startswith(TITRE_VOIE_MANUELLE)]
        assert len(titres) == 1, (
            "%s : %d titre(s) `###` pour la voie manuelle, un seul attendu. %r"
            % (page.relative_to(RACINE), len(titres), titres))
        # L'ANCRE STABLE, ET ELLE NE PEUT PAS ETRE `{ #… }` (corrige le
        # 2026-09-08, quelques heures apres la premiere redaction de ce test).
        #
        # L'intention d'origine est juste et elle est conservee : une ancre
        # DERIVEE du titre casse au premier remaniement de prose, donc il en
        # faut une stable, que le `README` puisse pointer. Ce qui etait faux
        # est le MOYEN. `{ #machine-vierge }` est la syntaxe `attr_list`,
        # activee dans `mkdocs.yml` : le SITE la comprend, **GitHub non** -- il
        # l'affiche litteralement dans le titre et ne cree aucune ancre de ce
        # nom. Or `docs.yml` ne deploie les Pages que sur declenchement MANUEL,
        # le site n'a jamais ete publie, et le `README` pointe ces pages par
        # chemin relatif : cent pour cent des lecteurs sont sur GitHub.
        #
        # Meme famille que l'AC8 de la 8.10, qui avait recopie
        # l'IMPLEMENTATION d'une garde au lieu de sa REGLE. On mesure donc la
        # PROPRIETE -- « l'ancre existe pour un lecteur GitHub » -- et le
        # moyen redevient libre.
        ancres = ancres_du_document(texte)
        assert "machine-vierge" in ancres, (
            "%s : pas d'ancre stable `machine-vierge` atteignable par un "
            "lecteur GITHUB. Une ancre derivee du titre casserait au premier "
            "remaniement de prose ; une ancre `{ #… }` n'existe que sous "
            "MkDocs. La forme qui marche des deux cotes est "
            "`<a id=\"machine-vierge\"></a>` pose avant le titre."
            % page.relative_to(RACINE))


# ---------------------------------------------------------------------------
# AC2 -- le bloc de detection est REEL, et il se JOUE dans les deux regimes
# ---------------------------------------------------------------------------

def _atelier_de_binaires(racine, presents: bool):
    """Un PATH de machine, avec ou sans les quatre outils.

    Les utilitaires de base (`head`) y sont TOUJOURS : une machine vierge n'est
    pas une machine vide, et un PATH vide mesurerait une panne que le terrain
    n'a pas -- exactement le defaut symetrique que `CLAUDE.md` relate sur les
    fixtures de synthese.
    """
    import shutil as _shutil
    atelier = racine / ("complete" if presents else "vierge")
    atelier.mkdir(parents=True, exist_ok=True)
    for utilitaire in ("head", "sed", "tr"):
        chemin = _shutil.which(utilitaire)
        if chemin:
            cible = atelier / utilitaire
            if not cible.exists():
                cible.symlink_to(chemin)
    if presents:
        for outil in ("python3",) + LES_QUATRE_OUTILS:
            faux = atelier / outil
            faux.write_text('#!/bin/sh\necho "%s version 9.9 factice"\n' % outil,
                            encoding="utf-8")
            faux.chmod(0o755)
    return atelier


@pytest.mark.parametrize("systeme", ["linux", "macos"])
def test_le_bloc_de_detection_REND_UN_VERDICT_sur_une_machine_VIERGE(
        systeme, tmp_path):
    """AC2, premier regime : aucun des quatre outils n'est la.

    Le bloc est **execute**, pas relu. Une frontiere dont on n'a pas mesure
    qu'elle rougit sur son contre-exemple n'est pas une frontiere.
    """
    import subprocess
    bloc = bloc_de_detection(
        PAGES_D_INSTALLATION[systeme].read_text(encoding="utf-8"))
    assert bloc, "%s : aucun bloc apres %s" % (systeme,
                                               MARQUE_DU_BLOC_DE_DETECTION)
    atelier = _atelier_de_binaires(tmp_path, presents=False)
    rendu = subprocess.run(["/bin/sh", "-c", bloc], capture_output=True,
                           text=True, timeout=60,
                           env={"PATH": str(atelier)})
    sortie = rendu.stdout
    for outil in ("python3",) + LES_QUATRE_OUTILS:
        assert outil in sortie, (
            "%s : le bloc de detection ne nomme pas %r sur une machine "
            "vierge. Sortie : %r" % (systeme, outil, sortie))
    assert sortie.count("ABSENT") == 4, (
        "%s : %d lignes ABSENT, quatre attendues. Un verdict qui ne dit pas "
        "ce qui manque n'est pas un verdict. Sortie : %r"
        % (systeme, sortie.count("ABSENT"), sortie))
    assert rendu.stderr.strip() == "", (
        "%s : le bloc crache sur la sortie d'erreur d'une machine vierge, "
        "alors que c'est son regime NOMINAL de lecture. %r"
        % (systeme, rendu.stderr))


@pytest.mark.parametrize("systeme", ["linux", "macos"])
def test_le_bloc_de_detection_REND_UN_VERDICT_sur_une_machine_COMPLETE(
        systeme, tmp_path):
    """AC2, second regime : les quatre outils repondent, avec leur version."""
    import subprocess
    bloc = bloc_de_detection(
        PAGES_D_INSTALLATION[systeme].read_text(encoding="utf-8"))
    atelier = _atelier_de_binaires(tmp_path, presents=True)
    rendu = subprocess.run(["/bin/sh", "-c", bloc], capture_output=True,
                           text=True, timeout=60,
                           env={"PATH": str(atelier)})
    sortie = rendu.stdout
    assert "ABSENT" not in sortie, (
        "%s : un outil est annonce ABSENT alors que les quatre sont poses. %r"
        % (systeme, sortie))
    for outil in ("python3",) + LES_QUATRE_OUTILS:
        assert "%s version 9.9 factice" % outil in sortie, (
            "%s : le bloc ne rend pas la VERSION de %r. Un verdict qui dit "
            "seulement « present » laisse passer un ffmpeg de 2019, et la "
            "panne survient a l'encodage. Sortie : %r" % (systeme, outil, sortie))


def test_les_deux_pages_SH_portent_le_MEME_bloc_de_detection():
    """Deux copies qui derivent valent moins qu'une seule.

    `linux.md` et `macos.md` s'adressent au meme interprete ; un bloc corrige
    d'un cote et pas de l'autre est le defaut que ce depot a paye sur
    `CANONICAL_ID_MAX_LENGTH`, trois fois.
    """
    blocs = {nom: bloc_de_detection(
        PAGES_D_INSTALLATION[nom].read_text(encoding="utf-8"))
        for nom in ("linux", "macos")}
    assert blocs["linux"] == blocs["macos"], (
        "les deux blocs `sh` ont derive :\n--- linux ---\n%s\n--- macos ---\n%s"
        % (blocs["linux"], blocs["macos"]))


def test_le_bloc_de_detection_de_WINDOWS_nomme_les_quatre_outils():
    """AC2 pour PowerShell, volet STRUCTUREL.

    **Ce que ce volet ne mesure pas, dit plutot que tu** : il ne JOUE pas le
    bloc. Aucun `pwsh` n'existe dans le conteneur de developpement, et
    inventer une execution serait pire que d'en declarer l'absence. Le volet
    qui joue est juste en dessous, et il se saute la ou PowerShell manque.
    """
    bloc = bloc_de_detection(
        PAGES_D_INSTALLATION["windows"].read_text(encoding="utf-8"))
    assert bloc, "windows.md : aucun bloc apres %s" % MARQUE_DU_BLOC_DE_DETECTION
    for outil in ("python",) + LES_QUATRE_OUTILS:
        assert outil in bloc, (
            "windows.md : le bloc de detection ne nomme pas %r. %r"
            % (outil, bloc))
    assert "Get-Command" in bloc, (
        "windows.md : le bloc n'INTERROGE pas la machine. Un bloc illustratif "
        "qui ne se colle pas est ce que l'AC2 interdit. %r" % (bloc,))


@pytest.mark.skipif(__import__("shutil").which("pwsh") is None,
                    reason="PowerShell absent de ce conteneur : le volet "
                           "structurel au-dessus reste le seul verdict ici")
def test_le_bloc_de_detection_de_WINDOWS_SE_JOUE(tmp_path):
    """AC2 pour PowerShell, volet EXECUTE la ou `pwsh` existe."""
    import subprocess
    bloc = bloc_de_detection(
        PAGES_D_INSTALLATION["windows"].read_text(encoding="utf-8"))
    rendu = subprocess.run(["pwsh", "-NoProfile", "-Command", bloc],
                           capture_output=True, text=True, timeout=120)
    for outil in ("python",) + LES_QUATRE_OUTILS:
        assert outil in rendu.stdout, (rendu.stdout, rendu.stderr)


# ---------------------------------------------------------------------------
# AC3 -- `ffprobe` est nomme partout ou `ffmpeg` l'est
# ---------------------------------------------------------------------------

def blocs_citant_ffmpeg_SANS_ffprobe(corps: str) -> list[str]:
    """Les blocs de la voie manuelle qui nomment l'un sans l'autre.

    Le motif est mesure et il coute des heures : certains paquets
    minimalistes ne livrent que `ffmpeg`, et la panne ne survient qu'a
    l'encodage -- c'est-a-dire apres l'extraction, apres l'impression, apres
    le scan. `install.ps1` teste deja les DEUX (`$FfmpegPresent = (Test-Commande
    "ffmpeg") -and (Test-Commande "ffprobe")`) ; la documentation le doit
    aussi.
    """
    fautifs = []
    for bloc in _blocs_de_code(corps):
        if "ffmpeg" in bloc and "ffprobe" not in bloc:
            fautifs.append(bloc)
    return fautifs


@pytest.mark.parametrize("systeme", sorted(PAGES_D_INSTALLATION))
def test_aucun_bloc_de_la_voie_manuelle_ne_cite_ffmpeg_SEUL(systeme):
    """AC3, volet positif."""
    corps = _corps_de_section(
        PAGES_D_INSTALLATION[systeme].read_text(encoding="utf-8"),
        TITRE_VOIE_MANUELLE)
    # ANTI-VACUITE : une section vide n'a aucun bloc fautif, donc cette
    # frontiere serait verte sur une page qui ne porterait rien. Le cardinal
    # se borne par le bas avant de conclure -- meme geste que le releve des
    # documents plus haut dans ce module.
    citants = [b for b in _blocs_de_code(corps) if "ffmpeg" in b]
    assert citants, (
        "%s : aucun bloc de la voie manuelle ne cite `ffmpeg`. La frontiere "
        "ci-dessous serait verte a vide." % systeme)
    fautifs = blocs_citant_ffmpeg_SANS_ffprobe(corps)
    assert fautifs == [], (
        "%s : bloc(s) de la voie manuelle citant `ffmpeg` sans `ffprobe`. "
        "%r" % (systeme, fautifs))


def test_la_frontiere_ffprobe_MORD_sur_un_bloc_qui_OUBLIE_ffprobe():
    """AC3, volet negatif -- sans lui la frontiere serait verte par
    construction, comme elle l'a ete tout le temps qu'elle n'existait pas."""
    fautif = "### x\n\n```sh\nsudo apt-get install ffmpeg\n```\n"
    assert len(blocs_citant_ffmpeg_SANS_ffprobe(fautif)) == 1
    juste = ("### x\n\n```sh\nsudo apt-get install ffmpeg\n"
             "ffprobe -version\n```\n")
    assert blocs_citant_ffmpeg_SANS_ffprobe(juste) == []


# ---------------------------------------------------------------------------
# AC4 -- la doc et `commande_de_secours` NE DIVERGENT PAS
# ---------------------------------------------------------------------------

def _commande_nue(ligne_info: str) -> str:
    """La COMMANDE seule, sans la parenthese explicative qui la suit.

    `commande_de_secours` ecrit `sudo dnf install ffmpeg   (depot RPM Fusion
    sur Fedora/RHEL)` : la parenthese est une information utile pour le
    lecteur, mais elle n'est pas la commande. Exiger de la doc qu'elle recopie
    l'espacement exact d'un `info` mesurerait la mise en page du script, pas
    la non-divergence des commandes -- et ferait rougir sur une doc juste.
    """
    return re.split(r"\s{2,}\(", ligne_info.strip())[0].strip()


def commandes_ffmpeg_du_script() -> dict[str, str]:
    """Les commandes de secours `ffmpeg`, LUES dans `install.sh`.

    Elles ne se recopient pas de tete : c'est la troisieme fois dans ce depot
    qu'une valeur citee de memoire est fausse (`CANONICAL_ID_MAX_LENGTH`).
    La source est le script, et cette fonction la lit a chaque course.
    """
    texte = (RACINE / "scripts" / "install.sh").read_text(encoding="utf-8")
    debut = texte.find("commande_de_secours() {")
    assert debut != -1, "`commande_de_secours` a disparu de `install.sh`"
    corps = texte[debut:texte.find("\n}\n", debut)]
    arme = corps[corps.find("ffmpeg)"):]
    # LA COUPE SE FAIT SUR `esac`, PAS SUR LE PREMIER `;;`, et ce n'est pas un
    # raffinement : l'arme `ffmpeg)` porte un `case` IMBRIQUE dont chaque
    # branche finit par `;;`. Couper au premier ne rendait que `brew` -- mesure
    # a l'ecriture, et c'est le volet d'anti-vacuite ci-dessous qui l'a dit.
    arme = arme[:arme.find("esac")]
    trouvees: dict[str, str] = {}
    for gestionnaire in ("brew", "apt-get", "dnf"):
        motif = re.compile(
            r"^\s*%s\)\s+info\s+\"\s*(.+?)\"" % re.escape(gestionnaire),
            re.MULTILINE)
        rencontre = motif.search(arme)
        if rencontre:
            trouvees[gestionnaire] = _commande_nue(rencontre.group(1))
    generique = re.search(r"\*\)\s+info\s+\"\s*(https://\S+?)\"", arme)
    if generique:
        trouvees["*"] = generique.group(1).strip()
    return trouvees


def test_le_releve_des_commandes_de_secours_LIT_encore_quelque_chose():
    """Volet d'anti-vacuite : un motif casse rendrait l'AC4 verte a vide."""
    trouvees = commandes_ffmpeg_du_script()
    assert set(trouvees) == {"brew", "apt-get", "dnf", "*"}, trouvees
    for gestionnaire, commande in trouvees.items():
        assert commande, gestionnaire


#: Quelle page doit porter quelle commande de secours. `pacman`, `zypper` et
#: `apk` n'ont AUCUNE commande epinglee dans le script : ils tombent dans la
#: branche generique, dont l'issue est l'URL officielle du projet ffmpeg. La
#: page Linux doit donc porter cette URL aussi, sans quoi un utilisateur
#: d'Arch qui suit la doc et un utilisateur d'Arch dont le repli echoue ne
#: recevraient pas la meme chose.
DIVERGENCES_A_MESURER = (
    ("linux", "apt-get"),
    ("linux", "dnf"),
    ("linux", "*"),
    ("macos", "brew"),
    ("macos", "*"),
)


@pytest.mark.parametrize("systeme,gestionnaire", DIVERGENCES_A_MESURER)
def test_la_voie_manuelle_NE_DIVERGE_PAS_de_commande_de_secours(
        systeme, gestionnaire):
    """AC4 (`EPIC11-ARB-271`, `EPIC11-ARB-276`).

    Un lecteur qui suit la doc et un utilisateur dont le repli du script
    echoue doivent recevoir la MEME commande. Sans quoi l'un des deux est
    trompe, et une commande de doc qui diverge du script est pire qu'une doc
    absente.
    """
    attendue = commandes_ffmpeg_du_script()[gestionnaire]
    corps = _corps_de_section(
        PAGES_D_INSTALLATION[systeme].read_text(encoding="utf-8"),
        TITRE_VOIE_MANUELLE)
    assert attendue in corps, (
        "%s : la voie manuelle ne porte pas %r, que `commande_de_secours` "
        "donne pour le gestionnaire %r. Les deux chemins doivent rendre la "
        "meme chose." % (systeme, attendue, gestionnaire))


def test_la_page_LINUX_garde_ce_que_la_parenthese_de_dnf_apprend():
    """AC4, complement : `_commande_nue` retire la parenthese explicative de
    `commande_de_secours`, donc rien ne mesurerait plus qu'un utilisateur de
    Fedora a besoin de RPM Fusion. Cette frontiere-la le mesure.

    Sans elle, la coupe faite pour eviter un faux rouge aurait cree un trou --
    c'est le mode de panne que ce depot appelle « une surface morte ».
    """
    corps = _corps_de_section(
        PAGES_D_INSTALLATION["linux"].read_text(encoding="utf-8"),
        TITRE_VOIE_MANUELLE)
    assert "RPM Fusion" in corps, (
        "linux.md : la voie manuelle ne dit pas que `ffmpeg` vient de RPM "
        "Fusion sur Fedora et RHEL, alors que `commande_de_secours` le dit. "
        "Un `sudo dnf install ffmpeg` sans ce depot rend « No match ».")


# ---------------------------------------------------------------------------
# AC5 et AC6 -- « tous les utilisateurs » : DOCUMENTE, jamais un drapeau
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("systeme", sorted(PAGES_D_INSTALLATION))
def test_la_voie_TOUS_LES_UTILISATEURS_est_ecrite_ET_son_cout_est_dit(systeme):
    """AC5 (`EPIC11-ARB-275`).

    La voie existe, elle est exacte, et elle dit ce qu'elle NE dispense PAS de
    faire -- « tous les utilisateurs » ne supprime pas la corvee par compte,
    il la deplace.
    """
    corps = _corps_de_section(
        PAGES_D_INSTALLATION[systeme].read_text(encoding="utf-8"),
        TITRE_TOUS_LES_UTILISATEURS)
    assert corps, (
        "%s : aucune section « Pour tous les utilisateurs de la machine ». "
        "`EPIC11-ARB-275` la DOCUMENTE plutot que de l'automatiser -- si elle "
        "n'est ecrite nulle part, l'arbitrage n'a rien rendu." % systeme)
    plie = _sans_accents(corps).lower()
    if systeme == "windows":
        exiges = ("machine", "administrateur")
    else:
        exiges = ("PIPX_HOME", "PIPX_BIN_DIR", "sudo")
    for motif in exiges:
        assert motif.lower() in plie, (
            "%s : la voie « tous les utilisateurs » ne nomme pas %r."
            % (systeme, motif))
    # LE COUT, et il est la moitie de l'arbitrage : chaque compte garde son
    # PATH, son profil, son raccourci.
    assert "chaque compte" in plie, (
        "%s : la section ne dit pas ce qu'elle NE dispense PAS de faire. "
        "Un administrateur qui la lit croirait la corvee supprimee alors "
        "qu'elle est deplacee." % systeme)
    for reste_a_faire in ("path", "raccourci"):
        assert reste_a_faire in plie, (
            "%s : le cout ne nomme pas %r." % (systeme, reste_a_faire))


def drapeau_tous_les_utilisateurs(texte: str) -> list[int]:
    """Les lignes qui ajoutent un drapeau « tous les utilisateurs ».

    **Ce que ce balayage NE compte PAS, et c'est ce qui le rend utilisable** :
    `-AllUsers` a UN SEUL tiret, qui est le parametre de
    `Repair-WinGetPackageManager` (`install.ps1`, l. 716) et n'a rien a voir
    avec l'installation partagee de l'outil. Le compter ferait rougir la
    frontiere sur du code juste -- « un rouge qui se trompe est pire que pas
    de frontiere : on apprend a l'ignorer », ce que l'en-tete de ce module
    dit deja.
    """
    motif = re.compile(r"--tous[-_]les[-_]utilisateurs"
                       r"|--all[-_]users"
                       r"|-TousLesUtilisateurs", re.IGNORECASE)
    return [numero for numero, ligne in enumerate(texte.splitlines(), start=1)
            if motif.search(ligne)]


def test_AUCUN_drapeau_tous_les_utilisateurs_n_est_ajoute_aux_SCRIPTS():
    """AC6, frontiere NEGATIVE (`EPIC11-ARB-275`).

    Le jour ou la mesure qui renverserait cet arbitrage sera faite -- un
    `sudo PIPX_HOME=... pipx install` qui marche de bout en bout sur les trois
    systemes, exerce par la jambe `macos-15-intel` de la CI --, c'est l'arbitrage
    qui bouge, pas ce banc en silence.
    """
    fautifs = []
    for script in SCRIPTS_D_INSTALLATION:
        assert script.exists(), script
        for numero in drapeau_tous_les_utilisateurs(
                script.read_text(encoding="utf-8")):
            fautifs.append("%s:%d" % (script.relative_to(RACINE), numero))
    assert fautifs == [], (
        "un drapeau « tous les utilisateurs » est apparu dans les scripts. "
        "`EPIC11-ARB-275` l'a exclu : dans le one-liner, ces trois lignes "
        "deviennent un `curl | bash` qui reclame un mot de passe "
        "administrateur sur le chemin NOMINAL -- ce que quatre AC de la story "
        "8.11 ont travaille a rendre refusable pour un seul geste eleve. %r"
        % (fautifs,))


def test_la_frontiere_du_DRAPEAU_mord_sur_son_contre_exemple():
    """AC6, volet negatif du volet negatif.

    Une frontiere dont on n'a pas mesure qu'elle rougit ne mesure rien.
    """
    assert drapeau_tous_les_utilisateurs(
        'if [ "$1" = "--tous-les-utilisateurs" ]; then\n') == [1]
    assert drapeau_tous_les_utilisateurs("param([switch]$TousLesUtilisateurs)"
                                         ) == []
    assert drapeau_tous_les_utilisateurs("  -TousLesUtilisateurs\n") == [1]
    assert drapeau_tous_les_utilisateurs("pipx install --all-users x\n") == [1]
    # Le volet SYMETRIQUE : la ligne reelle d'`install.ps1` reste innocente.
    assert drapeau_tous_les_utilisateurs(
        "            Repair-WinGetPackageManager -AllUsers -ErrorAction Stop"
    ) == []


# ---------------------------------------------------------------------------
# AC7 -- le perimetre du support macOS est DIT, pas tu
# ---------------------------------------------------------------------------

#: Ce qu'`EPIC11-ARB-278` exige que la page NOMME. Trois choses sont mesurees
#: et une ne l'est pas ; taire la quatrieme ferait croire a un support eprouve.
CE_QUE_LE_PERIMETRE_NOMME = (
    "macos-15-intel",
    "macos-14",
    "sw_vers",
    "macosx_12_0_x86_64",
    "evermeet",
)


def test_le_perimetre_du_support_macOS_est_DIT():
    """AC7 (`EPIC11-ARB-278`).

    Une promesse DATEE ET BORNEE vaut mieux qu'un silence : un utilisateur de
    macOS 12 qui lit « raisonne, pas eprouve » sait quoi faire d'un echec --
    le remonter --, la ou un silence lui fait croire qu'il est seul.
    """
    texte = PAGES_D_INSTALLATION["macos"].read_text(encoding="utf-8")
    plie = _sans_accents(texte).lower()
    assert "raisonne, pas eprouve" in plie, (
        "macos.md ne dit pas que le support de macOS 12 est RAISONNE et non "
        "EPROUVE. C'est le seul mot qu'`EPIC11-ARB-278` exige, et c'est celui "
        "qui distingue une promesse bornee d'une promesse creuse.")
    assert "aucun runner" in plie, (
        "macos.md ne dit pas qu'aucun runner ne joue macOS 12. GitHub ne "
        "propose plus de `macos-12` : le taire ferait croire a une mesure.")
    for element in CE_QUE_LE_PERIMETRE_NOMME:
        assert element.lower() in plie, (
            "macos.md ne nomme pas %r parmi ce qui FONDE le support de "
            "macOS 12." % element)


# ---------------------------------------------------------------------------
# AC11 -- le `README` POINTE la voie manuelle, il ne la recopie pas
# ---------------------------------------------------------------------------

def test_le_README_POINTE_la_voie_manuelle_sans_la_recopier():
    """AC11.

    Une regle ecrite a deux endroits diverge -- c'est ce que le contexte
    projet dit de lui-meme, et ce que `CANONICAL_ID_MAX_LENGTH` a paye trois
    fois. Le `README` porte donc le lien, jamais le contenu.
    """
    readme = (RACINE / "README.md").read_text(encoding="utf-8")
    for systeme in sorted(PAGES_D_INSTALLATION):
        ancre = "docs/installation/%s.md#machine-vierge" % systeme
        assert ancre in readme, (
            "README.md ne pointe pas %r : un lecteur qui refuse `curl | bash` "
            "ne trouve pas la voie manuelle depuis la page d'accueil, qui est "
            "la seule que tout le monde lit." % ancre)
    assert MARQUE_DU_BLOC_DE_DETECTION not in readme, (
        "README.md porte le bloc de detection : il le RECOPIE au lieu de le "
        "POINTER, et les deux copies divergeront.")
    assert "PIPX_HOME" not in readme, (
        "README.md recopie la voie « tous les utilisateurs » au lieu de la "
        "pointer.")


def test_le_README_ne_reintroduit_AUCUNE_balise_HTML():
    """Volet de non-regression du 2026-09-08.

    Les deux commandes d'installation vivaient dans un `<table>` a deux
    colonnes, ce qui produisait un ascenseur horizontal sur la page que tout
    le monde lit. Elles sont depuis en pleine largeur, l'une sous l'autre --
    et il n'y a plus une seule balise dans le fichier. Une frontiere negative
    est le seul moyen d'attraper la reintroduction d'un defaut.
    """
    readme = (RACINE / "README.md").read_text(encoding="utf-8")
    balises = [numero for numero, ligne in enumerate(readme.splitlines(), 1)
               if re.search(r"</?(table|tr|td|th|div|br|img)\b", ligne,
                            re.IGNORECASE)]
    assert balises == [], (
        "README.md a regagne des balises HTML aux lignes %r. Le `<table>` a "
        "deux colonnes du 2026-09-08 rendait un ascenseur horizontal sur "
        "GitHub, et GitHub est la surface que tout le monde lit." % (balises,))


# --------------------------------------- l'ancre qu'un LIEN vise doit EXISTER
#
# Posé le 2026-09-08, sur un défaut trouvé à la relecture du travail de la
# story 8.13 -- pas par une frontière, et c'est le motif de celle-ci.
#
# Le `README.md` pointait `docs/installation/<page>.md#machine-vierge`, et les
# trois pages déclaraient cette ancre par `{ #machine-vierge }`. C'est la
# syntaxe `attr_list`, activée dans `mkdocs.yml` (l. 64) : le SITE la rend, et
# l'ancre y existe. **GitHub ne la connaît pas.** Il l'affiche littéralement
# dans le titre -- « … à la main { #machine-vierge } » -- et ne crée aucune
# ancre de ce nom ; les trois liens du README y tombaient donc en haut de page.
#
# C'est mot pour mot la leçon des `blocs_avales` du même jour, sur une autre
# construction : `docs.yml` ne déploie les Pages que sur déclenchement MANUEL,
# le site n'a jamais été publié, et le `README` pointe ces pages par chemin
# relatif. **Cent pour cent des lecteurs sont sur GitHub.** Une syntaxe que
# seul MkDocs comprend n'y est pas un raffinement : c'est un lien mort.
#
# Le remède, et il tient dans les deux rendus : une ancre HTML explicite
# (`<a id="…"></a>`) posée avant le titre. GitHub l'honore, MkDocs la laisse
# passer telle quelle.


def _ancre_github(titre: str) -> str:
    """Le fragment que GitHub fabrique pour un titre, sa règle telle qu'elle est.

    Minuscules, la ponctuation retirée, les espaces en tirets. **Les accents
    sont CONSERVÉS** -- c'est ce qui distingue cette règle de celle de
    `python-markdown`, qui les dépouille. Une ancre dérivée d'un titre accentué
    n'est donc PAS la même des deux côtés, et c'est une raison de plus de poser
    une ancre explicite plutôt que de compter sur le titre.
    """
    sans_attr = re.sub(r"\s*\{[^}]*\}\s*$", "", titre.strip())
    minuscule = sans_attr.strip().lower()
    sans_ponctuation = re.sub(r"[^\w\s-]", "", minuscule, flags=re.UNICODE)
    return re.sub(r"\s+", "-", sans_ponctuation.strip())


def ancres_du_document(texte: str) -> set:
    """Toutes les ancres qu'un lecteur GITHUB trouvera dans ce document.

    Deux sources, et deux seulement : les ancres HTML explicites, et les
    fragments que GitHub dérive des titres. **`{ #… }` n'en est pas une** --
    c'est précisément ce que cette frontière mesure.
    """
    ancres = set(re.findall(r"<a\s+(?:id|name)=[\"']([^\"']+)[\"']", texte))
    for titre in re.findall(r"^#{1,6}\s+(.+)$", texte, re.M):
        ancres.add(_ancre_github(titre))
    return ancres


def liens_internes_avec_fragment(texte: str) -> list:
    """Les liens Markdown vers un autre document du dépôt, portant un `#`."""
    trouves = []
    for cible in re.findall(r"\]\(([^)\s]+#[^)\s]+)\)", texte):
        if cible.startswith(("http://", "https://", "mailto:")):
            continue
        chemin, _, fragment = cible.partition("#")
        if chemin:
            trouves.append((chemin, fragment))
    return trouves


def test_CHAQUE_ancre_visee_par_un_LIEN_existe_pour_un_lecteur_GITHUB():
    """La frontière, sur les documents que quelqu'un lit vraiment.

    Elle ne mesure pas « l'ancre existe sous MkDocs » -- c'est le rendu qui a
    laissé passer le défaut. Elle mesure ce que GitHub, lui, trouvera.
    """
    documents = _documents_de_lecture()
    assert len(documents) >= 10, (
        "seulement %d documents relevés : le relevé a fondu" % len(documents))

    couples = []
    morts = []
    for chemin_source in documents:
        texte = chemin_source.read_text(encoding="utf-8")
        for cible, fragment in liens_internes_avec_fragment(texte):
            chemin_cible = (chemin_source.parent / cible).resolve()
            if not chemin_cible.is_file():
                continue          # un lien vers un fichier absent est un autre sujet
            couples.append((chemin_source, cible, fragment))
            if fragment not in ancres_du_document(
                    chemin_cible.read_text(encoding="utf-8")):
                morts.append("%s -> %s#%s"
                             % (chemin_source.relative_to(RACINE), cible, fragment))

    assert len(couples) >= 3, (
        "seulement %d liens internes à fragment relevés : cette frontière ne "
        "mesure plus grand-chose (le README en portait trois au 2026-09-08)"
        % len(couples))
    assert morts == [], (
        "un lien vise une ancre qu'un lecteur GitHub ne trouvera pas -- il "
        "atterrira en haut de la page. Une ancre `{ #… }` est comprise par "
        "MkDocs SEUL ; poser `<a id=\"…\"></a>` avant le titre marche des deux "
        "côtés. %r" % (morts,))


def test_la_frontiere_MORD_sur_une_ancre_attr_list_que_GITHUB_ignore():
    """Le volet négatif, sur la forme EXACTE trouvée le 2026-09-08.

    Sans lui, la frontière ci-dessus serait verte par construction -- elle
    l'a été tout le temps qu'elle n'existait pas.
    """
    cible = "### Depuis une machine vierge { #machine-vierge }\n"
    assert "machine-vierge" not in ancres_du_document(cible), (
        "`{ #… }` ne doit PAS compter comme une ancre : c'est le défaut mesuré")
    assert "depuis-une-machine-vierge" in ancres_du_document(cible), (
        "le fragment dérivé du titre, lui, existe bel et bien chez GitHub")


def test_la_frontiere_NE_MORD_PAS_sur_les_DEUX_formes_qui_marchent():
    """Le volet symétrique : l'ancre explicite ET le titre nu.

    Les accents sont joués exprès -- GitHub les conserve là où
    `python-markdown` les dépouille, et une frontière qui les retirerait
    accuserait un lien juste.
    """
    explicite = '<a id="machine-vierge"></a>\n\n### Depuis une machine vierge\n'
    assert "machine-vierge" in ancres_du_document(explicite)
    accentue = "### Depuis une machine vierge, entièrement à la main\n"
    assert "depuis-une-machine-vierge-entièrement-à-la-main" in ancres_du_document(accentue)


# ===========================================================================
# Story 8.13, AC8 : la DESINSTALLATION et la MISE A JOUR se mesurent aussi
# ===========================================================================
#
# **Le defaut que ces frontieres ferment.** L'AC8 a ete tenue en attente
# derriere la story 8.12 -- documenter des issues qui n'existaient pas encore
# aurait produit une doc qui MENT. La 8.12 livree, le risque change de bord et
# devient celui que tout ce module traite deja : une doc juste aujourd'hui
# redevient fausse au prochain renommage, et **rien ne le dirait**. Les quatre
# documents decrivent maintenant un mecanisme du produit -- trois issues, un
# recu, une liste negative -- dont chaque element vit dans les scripts. Un
# libelle d'invite qui bouge, un drapeau qui change de nom, un recu qui change
# de fichier : la doc doit rougir ICI, pas chez un lecteur.
#
# **Ce que ces frontieres LISENT plutot qu'elles ne recopient**, et c'est le
# meme geste que `commandes_ffmpeg_du_script()` pour l'AC4 : les trois libelles,
# le numero de l'issue par defaut, les drapeaux et le nom du fichier de recu
# sortent des scripts a chaque course. Aucun n'est ecrit en dur ici.
#
# **Le precedent qui l'exige** : `--mettre-a-jour` a ete ecrit faux quatre fois
# dans les artefacts de cette story avant d'etre lu a la source.

SCRIPT_BASH, SCRIPT_POWERSHELL = SCRIPTS_D_INSTALLATION

#: Les quatre documents que l'AC8 tient, et le drapeau de chacun.
#:
#: Le `README` porte les deux formes parce qu'il parle des trois systemes ;
#: chaque page ne porte que la sienne. Exiger la forme bash dans `windows.md`
#: ferait rougir une page juste.
DOCUMENTS_DE_L_AC8: dict[str, Path] = {
    "README.md": RACINE / "README.md",
    "linux": PAGES_D_INSTALLATION["linux"],
    "macos": PAGES_D_INSTALLATION["macos"],
    "windows": PAGES_D_INSTALLATION["windows"],
}

#: Par document : le drapeau de retrait, celui de mise a jour, celui du mode
#: muet. Ils sont confrontes aux SCRIPTS par la frontiere plus bas ; ce
#: dictionnaire dit seulement lesquels chaque document doit nommer.
DRAPEAUX_ATTENDUS: dict[str, tuple[str, ...]] = {
    "README.md": ("--desinstaller", "-Desinstaller",
                  "--mettre-a-jour", "-MettreAJour"),
    "linux": ("--desinstaller", "--mettre-a-jour", "--non-interactif"),
    "macos": ("--desinstaller", "--mettre-a-jour", "--non-interactif"),
    "windows": ("-Desinstaller", "-MettreAJour", "-NonInteractif"),
}


def _sans_ornement(texte: str) -> str:
    """Replie une prose en ASCII minuscule, SANS ses ornements Markdown.

    Le pliage d'accents seul ne suffit pas ici : la doc ecrit « ni `pipx` »
    avec des accents graves et « **ni Python** » en gras, et une frontiere qui
    exigerait « ni pipx » nu demanderait a la documentation de renoncer a sa
    typographie. Ce qui est mesure est le PROPOS, pas sa mise en forme.

    **Les blancs sont RAMENES A UN SEUL, et ce n'est pas un raffinement** :
    trouve a la premiere course de ce lot, sur le `README`, ou la phrase
    « il affiche les commandes officielles et n'execute rien » tombait de part
    et d'autre d'un retour a la ligne. Une frontiere qui depend de l'endroit
    ou la prose se replie rougit au premier remaniement de forme, sur un
    contenu juste -- et « un rouge qui se trompe est pire que pas de
    frontiere », ce que l'en-tete de ce module dit deja.
    """
    plie = _sans_accents(texte).lower().replace("`", "").replace("*", "")
    return re.sub(r"\s+", " ", plie)


def _corps_de_section_niveau_2(texte: str, titre_ascii: str) -> str:
    """Le corps d'une section `##`, de son titre au prochain titre `##`.

    Le numero de section est retire avant comparaison (`## 7. Desinstaller`) :
    il bouge des qu'une section s'intercale, et une frontiere qui en
    dependrait rougirait sur un remaniement innocent.
    """
    lignes = texte.splitlines()
    debut = None
    for numero, ligne in enumerate(lignes):
        if not ligne.startswith("## "):
            continue
        titre = _sans_accents(ligne[3:]).lower().split("{")[0].strip()
        titre = re.sub(r"^\d+\.\s*", "", titre)
        if titre.startswith(titre_ascii):
            debut = numero
            break
    if debut is None:
        return ""
    for numero in range(debut + 1, len(lignes)):
        if lignes[numero].startswith("## "):
            return "\n".join(lignes[debut:numero])
    return "\n".join(lignes[debut:])


def _paragraphe_du_README(marque_ascii: str) -> str:
    """Le bloc du `README` qui OUVRE sur cette marque en gras.

    Le `README` n'a pas de section `##` par sujet -- l'AC11 lui interdit de
    grossir --, donc la zone mesuree y est le paragraphe.

    **Il lit par `DOCUMENTS_DE_L_AC8` et non par `RACINE / "README.md"`**, et
    ce n'est pas un gout : un chemin ecrit en dur ici rendait la campagne de
    mutation du 2026-09-08 AVEUGLE au `README` -- deux mutants y ont survecu
    sans qu'aucune frontiere soit en cause, parce que le mutant n'etait
    simplement jamais lu. Une source de verite par lot, pas deux.
    """
    texte = DOCUMENTS_DE_L_AC8["README.md"].read_text(encoding="utf-8")
    for bloc in re.split(r"\n[ \t]*\n", texte):
        if _sans_ornement(bloc).strip().startswith(marque_ascii):
            return bloc
    return ""


def zone_de_la_MISE_A_JOUR(nom: str) -> str:
    """La region de ce document qui traite de la mise a jour."""
    if nom == "README.md":
        return _paragraphe_du_README("mettre a jour")
    return _corps_de_section_niveau_2(
        DOCUMENTS_DE_L_AC8[nom].read_text(encoding="utf-8"), "mettre a jour")


def zone_DU_RETRAIT(nom: str) -> str:
    """La region de ce document qui traite de la desinstallation."""
    if nom == "README.md":
        return _paragraphe_du_README("desinstaller")
    return _corps_de_section_niveau_2(
        DOCUMENTS_DE_L_AC8[nom].read_text(encoding="utf-8"), "desinstaller")


# ------------------------------------- ce qui est LU dans les scripts, pas ecrit

#: Les trois constantes de libelle, dans l'ordre des issues.
CLES_DES_TROIS_ISSUES = (
    "ISSUE_APPLICATION_SEULE",
    "ISSUE_TOUT_CE_QUE_LE_SCRIPT_A_POSE",
    "ISSUE_MONTRER_LES_COMMANDES",
)


def issues_du_retrait_du_script() -> dict[str, str]:
    """Les trois libelles de l'invite de retrait, LUS dans `install.sh`.

    `install.ps1` porte les memes mot pour mot, et c'est
    `test_installateur_interactif.py` qui compare les deux scripts entre eux.
    Ce module-ci mesure l'autre bord : la DOC ne diverge pas du produit.
    """
    texte = SCRIPT_BASH.read_text(encoding="utf-8")
    trouves: dict[str, str] = {}
    for cle in CLES_DES_TROIS_ISSUES:
        capture = re.search(r'^%s="([^"]+)"\s*$' % re.escape(cle), texte, re.M)
        if capture:
            trouves[cle] = capture.group(1)
    return trouves


def issue_par_DEFAUT_du_script() -> int | None:
    """Le numero d'issue que l'invite prend par defaut, LU dans `install.sh`.

    C'est le premier argument de `demander`. Le lire plutot que l'ecrire est
    ce qui fera rougir la doc le jour ou le defaut changerait -- une doc qui
    annonce « l'issue 1 est le defaut » sur un produit qui en prend une autre
    est pire qu'une doc muette.
    """
    capture = re.search(r'demander\s+(\d+)\s+"\$\{INTITULE_DU_RETRAIT\}"',
                        SCRIPT_BASH.read_text(encoding="utf-8"))
    return int(capture.group(1)) if capture else None


def fichier_de_RECU_des_scripts() -> set[str]:
    """Le nom du fichier de recu, LU dans les DEUX scripts."""
    noms: set[str] = set()
    for script in SCRIPTS_D_INSTALLATION:
        noms.update(re.findall(r"[a-z-]+-par-[a-z-]+\.txt",
                               script.read_text(encoding="utf-8")))
    return noms


def le_script_BASH_reconnait(drapeau: str) -> bool:
    """Ce drapeau est-il une branche de la boucle d'arguments d'`install.sh` ?"""
    return re.search(r"^\s+%s\)" % re.escape(drapeau),
                     SCRIPT_BASH.read_text(encoding="utf-8"), re.M) is not None


def le_script_POWERSHELL_reconnait(parametre: str) -> bool:
    """Ce parametre est-il declare dans le `param()` d'`install.ps1` ?

    L'ancrage sur `[switch] $` n'est pas un ornement : `install.ps1` porte une
    VARIABLE INTERNE `$MiseAJour`, qui ressemble au parametre sans en etre un.
    Une frontiere qui chercherait le seul nom accepterait une doc citant un
    drapeau inexistant. Le volet negatif ci-dessous le mesure.
    """
    return re.search(r"^\s*\[switch\]\s*\$%s\s*,?\s*$"
                     % re.escape(parametre.lstrip("-")),
                     SCRIPT_POWERSHELL.read_text(encoding="utf-8"),
                     re.M) is not None


# ---------------------------------------------------------------------------
# AC8 -- anti-vacuite : ce qui est lu dans les scripts EST encore lu
# ---------------------------------------------------------------------------

def test_le_releve_des_TROIS_ISSUES_LIT_encore_quelque_chose():
    """Sans lui, un renommage de constante rendrait tout le lot AC8 vert.

    Une frontiere alimentee par un releve qui ne trouve plus rien ne mesure
    plus rien, et elle le fait en silence : c'est le meme volet que
    `test_le_releve_des_commandes_de_secours_LIT_encore_quelque_chose`.
    """
    issues = issues_du_retrait_du_script()
    assert set(issues) == set(CLES_DES_TROIS_ISSUES), (
        "les trois libelles de l'invite de retrait ne sont plus lisibles dans "
        "install.sh : %r. Le releve est casse, pas la doc." % sorted(issues))
    for cle, libelle in issues.items():
        assert len(libelle) >= 20, (cle, libelle)
    # Les trois se distinguent -- un releve qui rendrait trois fois la meme
    # chose passerait les assertions ci-dessus sans rien mesurer.
    assert len(set(issues.values())) == 3, issues


def test_le_releve_du_DEFAUT_et_du_RECU_LIT_encore_quelque_chose():
    """Meme volet, pour les deux autres valeurs lues dans les scripts."""
    assert issue_par_DEFAUT_du_script() is not None, (
        "l'appel `demander <defaut> \"${INTITULE_DU_RETRAIT}\"` n'est plus "
        "lisible dans install.sh : le releve du defaut est casse")
    recus = fichier_de_RECU_des_scripts()
    assert len(recus) == 1, (
        "les deux scripts doivent nommer le MEME fichier de recu, or le "
        "releve rend %r" % sorted(recus))


# ---------------------------------------------------------------------------
# AC8 -- les TROIS issues sont ecrites, et elles ne divergent pas du produit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("systeme", sorted(PAGES_D_INSTALLATION))
def test_les_TROIS_ISSUES_du_retrait_sont_ECRITES_dans_chaque_page(systeme):
    """AC8 (`EPIC11-ARB-274`), et c'est une NON-DIVERGENCE, pas une presence.

    Les libelles sont LUS dans `install.sh` a chaque course : une invite
    reformulee fait rougir la page qui la citait. C'est le meme contrat que
    l'AC4 impose deja aux commandes de secours -- « un lecteur qui suit la doc
    et un utilisateur devant l'invite doivent recevoir la meme chose ».
    """
    plie = _sans_ornement(DOCUMENTS_DE_L_AC8[systeme].read_text(encoding="utf-8"))
    for cle, libelle in sorted(issues_du_retrait_du_script().items()):
        assert _sans_ornement(libelle) in plie, (
            "%s ne porte pas le libelle %s de l'invite de retrait, mot pour "
            "mot : %r. La page decrit alors des issues que l'utilisateur ne "
            "reconnaitra pas a l'ecran."
            % (DOCUMENTS_DE_L_AC8[systeme].relative_to(RACINE), cle, libelle))


def test_la_frontiere_des_TROIS_ISSUES_MORD_sur_un_libelle_REFORMULE():
    """Le volet negatif : une doc qui paraphrase l'invite doit rougir.

    Sans ce volet, la frontiere ci-dessus serait verte par construction le
    jour ou le pliage cesserait de plier quoi que ce soit.
    """
    libelle = issues_du_retrait_du_script()["ISSUE_MONTRER_LES_COMMANDES"]
    paraphrase = "rien pour l'instant, montrez-moi les commandes du reste"
    assert _sans_ornement(libelle) not in _sans_ornement(paraphrase), (
        "une paraphrase ne doit PAS satisfaire la frontiere")
    # Le volet SYMETRIQUE : la citation exacte, meme habillee de gras et
    # d'accents graves, reste innocente.
    habillee = "  1) **%s** [defaut]" % libelle
    assert _sans_ornement(libelle) in _sans_ornement(habillee)


# ---------------------------------------------------------------------------
# AC8 -- le DEFAUT est l'issue 1, et le mode muet la prend
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("systeme", sorted(PAGES_D_INSTALLATION))
def test_chaque_page_DIT_que_le_defaut_est_l_issue_1_et_que_le_mode_MUET_la_prend(
        systeme):
    """AC8 : « une machine muette ne retire jamais plus que l'application ».

    Le numero du defaut est LU dans `install.sh`. La page doit le nommer, et
    nommer le drapeau qui le prend sans poser de question -- c'est la moitie
    de l'information pour qui integre l'outil dans un script.
    """
    defaut = issue_par_DEFAUT_du_script()
    assert defaut == 1, (
        "le defaut de l'invite de retrait vaut %r dans install.sh. Ce n'est "
        "pas un banc a corriger : c'est `EPIC11-ARB-274` qui a bouge, et les "
        "quatre documents avec lui." % defaut)
    zone = _sans_ornement(zone_DU_RETRAIT(systeme))
    assert zone, "%s ne porte aucune section de desinstallation" % systeme
    assert "defaut" in zone, (
        "%s : la desinstallation ne dit pas laquelle des trois issues est le "
        "defaut." % systeme)
    muet = "-noninteractif" if systeme == "windows" else "--non-interactif"
    assert muet in zone, (
        "%s : la desinstallation ne nomme pas %r, donc elle ne dit pas ce que "
        "fait le script sans terminal -- exactement le regime d'un "
        "`curl | bash`, d'une image ou d'une integration continue."
        % (systeme, muet))


# ---------------------------------------------------------------------------
# AC8 -- les DRAPEAUX cites par la doc EXISTENT dans les scripts
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nom", sorted(DOCUMENTS_DE_L_AC8))
def test_chaque_document_NOMME_le_retrait_ET_la_mise_a_jour(nom):
    """AC8, la presence : les quatre documents, pas trois."""
    plie = DOCUMENTS_DE_L_AC8[nom].read_text(encoding="utf-8")
    for drapeau in DRAPEAUX_ATTENDUS[nom]:
        assert drapeau in plie, (
            "%s ne nomme pas %r. L'AC8 tient les QUATRE documents : un lecteur "
            "arrive par la page d'accueil aussi souvent que par la page de son "
            "systeme." % (DOCUMENTS_DE_L_AC8[nom].relative_to(RACINE), drapeau))


#: Le seul drapeau d'une AUTRE commande que les zones de l'AC8 citent.
#:
#: Il est NOMME plutot que filtre par une regle : `--include-injected`
#: appartient a `pipx`, pas aux scripts d'installation. Il n'est pas pour
#: autant « ignore » -- sa presence est EXIGEE par
#: `test_la_LISTE_NEGATIVE_de_la_mise_a_jour_est_ECRITE`, donc il est mesure
#: ailleurs et pour autre chose. Releve du 2026-09-08 : c'est le seul, sur les
#: huit zones des quatre documents.
DRAPEAUX_D_UNE_AUTRE_COMMANDE = frozenset({"--include-injected"})

#: Un drapeau bash (`--minuscules`) ou un parametre PowerShell (`-Capitale`).
_FORME_D_UN_DRAPEAU = r"(?<![\w-])(--[a-z][a-z-]*|-[A-Z][A-Za-z]+)(?![\w-])"


def drapeaux_d_installation_cites(texte: str) -> set[str]:
    """Les drapeaux que ce texte adresse aux SCRIPTS d'installation.

    Deux gisements, et pas un de plus :

    * ce qui **suit** un `install.sh` ou un `install.ps1` sur la meme ligne.
      « Suit » est le discriminant : `-ExecutionPolicy` et `-File` sont des
      options de `powershell.exe`, pas du script, et elles le PRECEDENT. Les
      compter ferait rougir une page juste ;
    * les drapeaux cites en prose entre accents graves, `--non-interactif`
      etant nomme sans etre invoque.

    **Ce que ce releve NE couvre PAS, dit plutot que tu** : les drapeaux cites
    ailleurs dans la page -- `--include-apps` et `--force` de `pipx` dans la
    voie manuelle, `--sans-couleur` de la TUI dans les problemes frequents.
    Ils appartiennent a d'autres commandes, et rien ici ne pretend les tenir.
    """
    cites: set[str] = set()
    for ligne in texte.splitlines():
        coupe = re.split(r"install\.(?:sh|ps1)", ligne)
        if len(coupe) > 1:
            cites.update(re.findall(_FORME_D_UN_DRAPEAU, " ".join(coupe[1:])))
        cites.update(re.findall(r"`(--[a-z][a-z-]*|-[A-Z][A-Za-z]+)`", ligne))
    return cites - DRAPEAUX_D_UNE_AUTRE_COMMANDE


@pytest.mark.parametrize("nom", sorted(DOCUMENTS_DE_L_AC8))
def test_tout_drapeau_d_INSTALLATION_cite_par_la_doc_EXISTE_dans_son_script(nom):
    """AC8, la non-divergence -- et le precedent qui l'exige est date.

    `--mettre-a-jour` a ete ecrit faux quatre fois dans les artefacts de cette
    story avant d'etre relu a la source. Une doc qui nomme un drapeau
    inexistant rend un `Option inconnue` immediat, et personne ne le voit
    parce qu'aucun banc ne lisait ces pages.

    **La premiere redaction de ce test etait TAUTOLOGIQUE**, et c'est une
    campagne de mutation qui l'a dit, pas la relecture : elle confrontait
    `DRAPEAUX_ATTENDUS` -- une liste ecrite ici -- aux scripts, sans jamais
    lire le document. Le mutant « `-MettreAJour` devient `-MiseAJour` dans le
    `README` » y survivait, puisque le document n'entrait pas dans la mesure.
    C'est le defaut que `CLAUDE.md` nomme sur la story 5.9, « un test
    tautologique portant sur la constante centrale ». La version ci-dessous
    lit les drapeaux DANS le document.
    """
    zones = "\n".join((zone_de_la_MISE_A_JOUR(nom), zone_DU_RETRAIT(nom)))
    cites = drapeaux_d_installation_cites(zones)
    assert cites, (
        "%s : aucune des deux zones ne cite de drapeau d'installation -- le "
        "releve est vide, donc la frontiere ne mesure rien." % nom)
    for drapeau in sorted(cites):
        if drapeau.startswith("--"):
            assert le_script_BASH_reconnait(drapeau), (
                "%s cite %r, qu'`install.sh` ne reconnait pas : un lecteur qui "
                "le recopie recoit `Option inconnue`." % (nom, drapeau))
        else:
            assert le_script_POWERSHELL_reconnait(drapeau), (
                "%s cite %r, qui n'est pas un parametre d'`install.ps1`."
                % (nom, drapeau))


def test_le_releve_des_DRAPEAUX_CITES_distingue_le_script_de_son_lanceur():
    """Le volet negatif du releve, sur les deux pieges qu'il doit eviter.

    Les deux lignes « innocentes » sont, mot pour mot, dans `windows.md`.
    """
    # Ce qui SUIT le script est a lui.
    assert drapeaux_d_installation_cites(
        "powershell -ExecutionPolicy Bypass -File .\\scripts\\install.ps1 "
        "-MettreAJour\n") == {"-MettreAJour"}
    assert drapeaux_d_installation_cites(
        "curl -fsSL https://x/install.sh | bash -s -- --desinstaller\n"
    ) == {"--desinstaller"}
    # Un drapeau d'une AUTRE commande n'est pas compte, et il est nomme.
    assert drapeaux_d_installation_cites(
        "`pipx upgrade mmu-tui --include-injected`\n") == set()
    # Et le releve MORD sur un drapeau invente.
    assert "--mise-a-jour" in drapeaux_d_installation_cites(
        "bash scripts/install.sh --mise-a-jour\n")


def test_la_frontiere_du_DRAPEAU_mord_sur_un_nom_INVENTE_des_DEUX_cotes():
    """Le volet negatif, et son volet SYMETRIQUE.

    Le cas `$MiseAJour` n'est pas theorique : `install.ps1` porte bel et bien
    cette variable interne, qui ressemble au parametre `$MettreAJour` sans en
    etre un. Une frontiere qui chercherait le nom nu la prendrait pour un
    drapeau et validerait une doc fausse.
    """
    # Les vrais passent.
    assert le_script_BASH_reconnait("--mettre-a-jour")
    assert le_script_BASH_reconnait("--desinstaller")
    assert le_script_POWERSHELL_reconnait("-MettreAJour")
    assert le_script_POWERSHELL_reconnait("-Desinstaller")
    # Les plausibles-mais-faux echouent.
    assert not le_script_BASH_reconnait("--mise-a-jour")
    assert not le_script_BASH_reconnait("--update")
    assert not le_script_POWERSHELL_reconnait("-MiseAJour")
    # Et la variable interne du meme nom EXISTE : c'est ce qui rend le
    # discriminant `[switch]` necessaire plutot que decoratif.
    assert "$MiseAJour" in SCRIPT_POWERSHELL.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# AC8 -- la LISTE NEGATIVE de la mise a jour, qui compte autant que l'autre
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nom", sorted(DOCUMENTS_DE_L_AC8))
def test_la_LISTE_NEGATIVE_de_la_mise_a_jour_est_ECRITE(nom):
    """AC8 (`EPIC11-ARB-277`), et c'est la moitie qu'on oublie d'ecrire.

    Un lecteur qui lit « mise a jour » sans precision suppose que TOUT est mis
    a jour, puis conclut a un bogue de l'outil le jour ou un `ffmpeg` de 2019
    refuse `-fps_mode`. Dire ce qui n'est pas touche coute trois mots et ferme
    un faux rapport de bogue.
    """
    zone = _sans_ornement(zone_de_la_MISE_A_JOUR(nom))
    assert zone, (
        "%s ne porte aucune region traitant de la mise a jour" % nom)
    for dependance in ("ni python", "ni ffmpeg", "ni pipx"):
        assert dependance in zone, (
            "%s : la mise a jour ne dit pas qu'elle ne touche pas %r. La liste "
            "NEGATIVE compte autant que la positive." % (nom, dependance))
    assert "--include-injected" in zone, (
        "%s : la mise a jour ne nomme pas `--include-injected`. Sans lui, pipx "
        "met a jour la distribution et laisse le `mmu-cli` greffe a son "
        "ancienne version -- la voie manuelle equivalente serait fausse." % nom)


def test_la_frontiere_de_la_LISTE_NEGATIVE_mord_sur_une_mise_a_jour_MUETTE():
    """Le volet negatif : une prose qui promet « tout » doit rougir."""
    muette = ("## 6. Mettre a jour\n\n"
              "Relancez le script : il met tout a jour.\n")
    zone = _sans_ornement(_corps_de_section_niveau_2(muette, "mettre a jour"))
    assert zone, "la section doit bien etre trouvee, sinon le test est vide"
    assert "ni python" not in zone
    assert "--include-injected" not in zone
    # Le volet SYMETRIQUE : la vraie section, elle, est reconnue.
    reelle = _sans_ornement(zone_de_la_MISE_A_JOUR("linux"))
    assert "ni python" in reelle and "--include-injected" in reelle


# ---------------------------------------------------------------------------
# AC8 -- le RECU est nomme par son chemin, et l'issue 3 AFFICHE sans FAIRE
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("systeme", sorted(PAGES_D_INSTALLATION))
def test_chaque_page_NOMME_le_RECU_et_sa_racine(systeme):
    """AC8 : l'issue 2 ne retire que ce qu'un recu enregistre.

    Le nom du fichier est LU dans les deux scripts : le renommer fait rougir
    les trois pages. La RACINE, elle, differe par systeme -- `XDG_STATE_HOME`
    d'un cote, `LOCALAPPDATA` de l'autre --, et exiger la mauvaise ferait
    rougir une page juste.
    """
    (nom_du_recu,) = fichier_de_RECU_des_scripts()
    texte = PAGES_D_INSTALLATION[systeme].read_text(encoding="utf-8")
    assert nom_du_recu in texte, (
        "%s ne nomme pas le fichier de recu %r : le lecteur ne peut donc pas "
        "verifier lui-meme ce que l'issue 2 reprendra." % (systeme, nom_du_recu))
    racine = "LOCALAPPDATA" if systeme == "windows" else "XDG_STATE_HOME"
    assert racine in texte, (
        "%s ne nomme pas la racine %r du recu." % (systeme, racine))
    plie = _sans_ornement(texte)
    assert "absent du recu" in plie, (
        "%s ne dit pas qu'un binaire present mais ABSENT du recu n'est jamais "
        "touche. C'est ce qui distingue l'issue 2 d'un balayage de la machine."
        % systeme)


@pytest.mark.parametrize("nom", sorted(DOCUMENTS_DE_L_AC8))
def test_l_ISSUE_3_est_dite_AFFICHER_sans_FAIRE(nom):
    """AC8 (`EPIC11-ARB-274`, l'issue 3 « AFFICHE au lieu de FAIRE »).

    Une issue qu'on croit destructive ne se choisit pas, et c'est precisement
    celle qui ne l'est pas.
    """
    zone = _sans_ornement(zone_DU_RETRAIT(nom))
    assert zone, "%s ne porte aucune region traitant de la desinstallation" % nom
    assert "affiche" in zone, (
        "%s : l'issue 3 n'est pas dite AFFICHER les commandes." % nom)
    assert any(marque in zone for marque in
               ("ne fait pas", "n'execute rien", "rien n'a bouge")), (
        "%s : l'issue 3 n'est pas dite NE RIEN FAIRE. Un lecteur qui la croit "
        "destructive ne la choisira pas." % nom)


# ---------------------------------------------------------------------------
# AC8 -- Python n'est JAMAIS retire : une frontiere NEGATIVE, cote doc
# ---------------------------------------------------------------------------

#: Un retrait de Python par un gestionnaire de paquets, sur une seule ligne.
#:
#: **Ce que ce balayage NE compte PAS, et c'est ce qui le rend utilisable** :
#: `python -m pip uninstall pipx` -- que `windows.md` porte legitimement --,
#: parce que `python` y precede le verbe de retrait et n'en est pas la cible ;
#: et `brew uninstall pipx`, ou `pipx` n'est pas `python`. Les deux sont
#: mesures par le volet symetrique.
_RETRAIT_DE_PYTHON = re.compile(
    r"(?:apt(?:-get)?\s+(?:remove|purge)"
    r"|dnf\s+remove|yum\s+remove"
    r"|pacman\s+-R\w*|zypper\s+remove|apk\s+del"
    r"|brew\s+uninstall|winget\s+uninstall)"
    r"[^\n]*?\bpython",
    re.IGNORECASE)


def retraits_de_python(texte: str) -> list[int]:
    """Les lignes qui donneraient une commande de retrait de Python."""
    return [numero for numero, ligne in enumerate(texte.splitlines(), start=1)
            if _RETRAIT_DE_PYTHON.search(ligne)]


@pytest.mark.parametrize("nom", sorted(DOCUMENTS_DE_L_AC8))
def test_AUCUN_document_ne_donne_de_commande_de_RETRAIT_de_PYTHON(nom):
    """AC8, frontiere NEGATIVE -- le jumeau, cote doc, de celle des scripts.

    « Python n'est jamais retire, meme s'il figure au recu » est une frontiere
    du PRODUIT, pas une prudence : sur Debian et Ubuntu le gestionnaire de
    paquets lui-meme en depend, et sur macOS `/usr/bin/python3` appartient aux
    outils d'Apple. Le script ne donne donc aucune commande -- il renvoie a
    python.org. Une doc qui l'ecrirait defairait la frontiere par l'autre bout :
    une ligne citee en avertissement se recopie exactement comme une autre.
    """
    document = DOCUMENTS_DE_L_AC8[nom]
    fautives = retraits_de_python(document.read_text(encoding="utf-8"))
    assert fautives == [], (
        "%s donne une commande de retrait de Python, lignes %r. Le produit "
        "refuse de la donner ; la documentation ne doit pas la donner a sa "
        "place." % (document.relative_to(RACINE), fautives))


def test_la_frontiere_du_RETRAIT_DE_PYTHON_mord_ET_laisse_INNOCENT_le_reste():
    """La preuve dans les deux sens, sur des lignes REELLES du depot.

    Le volet symetrique compte autant que l'autre : les trois lignes
    innocentes ci-dessous sont, mot pour mot, dans les scripts ou dans
    `windows.md`. Un rouge qui se trompe est pire que pas de frontiere.
    """
    # Elle MORD sur les formes qu'on ecrirait vraiment.
    assert retraits_de_python("sudo apt-get remove python3\n") == [1]
    assert retraits_de_python("  sudo dnf remove python3-pip\n") == [1]
    assert retraits_de_python("brew uninstall python@3.12\n") == [1]
    assert retraits_de_python(
        "winget uninstall --id Python.Python.3.12 -e\n") == [1]
    # Et elle laisse INNOCENTES les lignes reelles du depot.
    assert retraits_de_python("python -m pip uninstall pipx\n") == []
    assert retraits_de_python("  pipx uninstall-all\n") == []
    assert retraits_de_python("sudo apt-get remove ffmpeg\n") == []
    assert retraits_de_python("brew uninstall pipx\n") == []
    assert retraits_de_python(
        "winget uninstall --id Gyan.FFmpeg -e\n") == []


# ---------------------------------------------------------------------------
# AC8 et AC11 -- le `README` POINTE le detail, il ne le recopie pas
# ---------------------------------------------------------------------------

def test_le_README_POINTE_le_retrait_et_la_mise_a_jour_sans_les_RECOPIER():
    """AC11 applique a l'AC8 : une regle ecrite a deux endroits diverge.

    Les six ancres visees sont par ailleurs verifiees comme ATTEIGNABLES PAR
    UN LECTEUR GITHUB par `test_CHAQUE_ancre_visee_par_un_LIEN_existe_pour_un_
    lecteur_GITHUB` -- c'est le defaut du 2026-09-08, ou trois liens du README
    tombaient en haut de page parce que l'ancre etait posee en `{ #... }`.
    """
    readme = DOCUMENTS_DE_L_AC8["README.md"].read_text(encoding="utf-8")
    for systeme in sorted(PAGES_D_INSTALLATION):
        for ancre in ("desinstaller", "mettre-a-jour"):
            cible = "docs/installation/%s.md#%s" % (systeme, ancre)
            assert cible in readme, (
                "README.md ne pointe pas %r : un lecteur arrive sur la page "
                "d'accueil et n'a aucun chemin vers le detail." % cible)
    # Il ne RECOPIE pas les trois issues : deux copies divergent.
    plie = _sans_ornement(readme)
    for libelle in issues_du_retrait_du_script().values():
        assert _sans_ornement(libelle) not in plie, (
            "README.md recopie le libelle %r de l'invite au lieu de POINTER "
            "la page qui le porte." % libelle)
