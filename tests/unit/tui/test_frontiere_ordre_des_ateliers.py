# -*- coding: utf-8 -*-
"""L'ordre des ateliers est ecrit a SIX endroits : la frontiere qui les confronte.

**Le defaut que ce banc ferme, et il a ete paye le 2026-09-06.** Le retour
terrain d'Egan -- verbatim : « remonter l'atelier [PDF] dans la liste AVANT scan
(ordre logique) » -- porte sur **une** liste litterale,
`tui/projet_lecture.ATELIERS`. Mais l'ordre etait ecrit a six endroits, et aucun
banc ne les confrontait :

    tui/projet_lecture.py                     la source de verite
    tests/unit/tui/test_projet_lecture.py     un banc, en dur
    tests/unit/tui/test_ecran_ateliers.py     deux bancs, en dur
    docs/guide-utilisateur/tui.md             la doc LIVREE a l'utilisateur
    .../maquettes/E1-1-menu-ateliers.txt      la maquette de reference
    .../EXPERIENCE.md                         la source de l'arbitrage d'origine

Sans cette frontiere, la prochaine correction du code laisserait de nouveau la
doc utilisateur et la maquette annoncer l'ancien ordre, **sans que rien ne
rougisse** -- c'est la regle du depot : ce qui se mesure se tient, ce qui se
rappelle se perd.

**Un septieme lieu, et c'est le plus fort : la GUI.** `gui/coquille.ORDRE_ATELIERS`
porte le meme ordre sous d'autres noms (`atelier-pdf` contre `Pdf`), avec un
commentaire qui dit deja « l'ordre est l'ordre du flux, il ne se renegocie pas
ici ». Les deux listes ne sont reliees par **aucun** code : c'est ici, et nulle
part ailleurs, qu'elles se confrontent. C'est ce qui rend l'ecart d'origine --
« la TUI a un ordre delibrement different » -- impossible a rouvrir en silence.

**Ce que ce banc NE mesure pas, dit plutot que tu.** Il ne sait pas reconnaitre
qu'une prose neuve *parle* de l'ordre : un septieme document qui l'ecrirait sans
etre nomme ici lui reste invisible. Les cinq sources documentaires sont donc
nommees une a une, et :func:`test_les_cinq_sources_documentaires_sont_TOUTES_lues`
mesure ce cardinal -- une source retiree de la table fait rougir.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.gui import coquille  # noqa: E402
from mixed_media_utility.tui import projet_lecture  # noqa: E402

#: Les documents confrontes, a leur source.
_DOC_TUI = _RACINE / "docs" / "guide-utilisateur" / "tui.md"
_UX = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
       / "ux-tui-2026-08-27")
_MAQUETTE_E1_1 = _UX / "maquettes" / "E1-1-menu-ateliers.txt"
_EXPERIENCE = _UX / "EXPERIENCE.md"


# ---------------------------------------------------------------------------
# Le decoupage : chaque source rend le BLOC ou l'ordre est ecrit
# ---------------------------------------------------------------------------

def _entre(texte: str, ouvre: str, ferme: str) -> str:
    """Le morceau de `texte` entre deux reperes, bornes exclues.

    Un decoupage plutot qu'une lecture du fichier entier : les quatre noms
    d'atelier apparaissent des dizaines de fois dans la doc et dans
    `EXPERIENCE.md`, et un `index()` sur le fichier entier mesurerait l'ordre
    de la **premiere phrase qui les cite**, pas celui de la liste.
    """
    debut = texte.index(ouvre) + len(ouvre)
    return texte[debut:texte.index(ferme, debut)]


def _bloc_arborescence_de_la_doc() -> str:
    """Le dessin des trois zones de `docs/guide-utilisateur/tui.md`."""
    return _entre(_DOC_TUI.read_text(encoding="utf-8"),
                  "MENU DU", "└──────────────")


def _bloc_tableau_de_la_doc() -> str:
    """Le tableau « Entrée | Ce qu'elle fait | Objets » de la meme page."""
    return _entre(_DOC_TUI.read_text(encoding="utf-8"),
                  "| Entrée | Ce qu'elle fait | Objets |",
                  "L'atelier **Scan** enchaîne")


def _bloc_menu_de_la_maquette() -> str:
    """Les lignes du menu de `E1-1`, filet du bas exclu."""
    return _entre(_MAQUETTE_E1_1.read_text(encoding="utf-8"),
                  "Que faire dans", "   ─────")


def _bloc_il_voit_d_experience() -> str:
    """Le paragraphe « Il voit cinq entrées … » de la fiche `E1-1`."""
    return _entre(_EXPERIENCE.read_text(encoding="utf-8"),
                  "**Il voit** cinq entrées", "**Il peut**")


def _bloc_ordre_d_experience() -> str:
    """Le paragraphe « Ordre des entrées » de la fiche `E1-1`.

    **La citation de revision en est RETIREE**, et c'est indispensable : ce
    paragraphe cite verbatim l'ancien ordre pour qu'une revue future ne le
    « re-corrige » pas, et une mesure qui la lirait rendrait exactement l'ordre
    qu'elle est censee interdire. Les lignes de citation sont celles qui
    ouvrent par `>`.
    """
    bloc = _entre(_EXPERIENCE.read_text(encoding="utf-8"),
                  "**Ordre des entrées.**", "**Cas limites.**")
    return "\n".join(ligne for ligne in bloc.splitlines()
                     if not ligne.lstrip().startswith(">"))


#: Les cinq sources documentaires, nommees une a une. Le cardinal est mesure
#: (`test_les_cinq_sources_documentaires_sont_TOUTES_lues`) : une source retiree
#: de cette table sortirait de la mesure en silence, ce qui est exactement le
#: mode de panne que ce fichier existe pour fermer.
SOURCES_DOCUMENTAIRES = {
    "docs/guide-utilisateur/tui.md · arborescence": _bloc_arborescence_de_la_doc,
    "docs/guide-utilisateur/tui.md · tableau": _bloc_tableau_de_la_doc,
    "maquettes/E1-1-menu-ateliers.txt": _bloc_menu_de_la_maquette,
    "EXPERIENCE.md · « Il voit »": _bloc_il_voit_d_experience,
    "EXPERIENCE.md · « Ordre des entrées »": _bloc_ordre_d_experience,
}


def ordre_lu(bloc: str) -> tuple[str, ...]:
    """Les quatre ateliers, **dans l'ordre ou le bloc les nomme**.

    Chaque nom doit y figurer : un bloc ou l'un manquerait rendrait un ordre
    partiel, qu'une comparaison de sequence lirait comme « different » plutot
    que comme « incomplet ». On le dit donc explicitement.
    """
    manquants = [nom for nom in projet_lecture.ATELIERS if nom not in bloc]
    assert manquants == [], (manquants, bloc)
    return tuple(sorted(projet_lecture.ATELIERS, key=bloc.index))


# ---------------------------------------------------------------------------
# La frontiere
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("source", sorted(SOURCES_DOCUMENTAIRES))
def test_chaque_document_dit_l_ordre_de_projet_lecture_ATELIERS(source):
    """La doc livree, la maquette et la fiche UX disent **la** liste du code.

    Une egalite de SEQUENCE, jamais d'appartenance : « les quatre y sont »
    serait vert sur l'ancien ordre, qui est precisement ce qu'on ferme.
    """
    bloc = SOURCES_DOCUMENTAIRES[source]()
    assert ordre_lu(bloc) == tuple(projet_lecture.ATELIERS), (
        source, ordre_lu(bloc), tuple(projet_lecture.ATELIERS))


def test_la_frontiere_MORD_quand_un_document_garde_l_ANCIEN_ordre():
    """Volet de morsure, sur chaque source et **par le vrai chemin**.

    Sans lui, un decoupage qui rendrait un bloc vide -- un repere renomme, un
    titre deplace -- rendrait les cinq cas verts sans rien mesurer. On rejoue
    donc la permutation exacte que le retour d'Egan a fermee, `Pdf` et `Scan`
    echanges, et on exige un rouge de **chacune** des cinq sources.
    """
    muets = []
    for source, decoupe in sorted(SOURCES_DOCUMENTAIRES.items()):
        ancien = re.sub(r"\bScan\b", "\x00", decoupe())
        ancien = re.sub(r"\bPdf\b", "Scan", ancien).replace("\x00", "Pdf")
        if ordre_lu(ancien) == tuple(projet_lecture.ATELIERS):
            muets.append(source)
    assert muets == [], muets


def test_les_cinq_sources_documentaires_sont_TOUTES_lues():
    """Anti-vacuite : la table ne maigrit pas sans qu'on le voie.

    Et chaque bloc decoupe est **non vide** -- un repere qui aurait bouge
    rendrait `_entre` sur une chaine vide, donc `ordre_lu` rougirait deja ;
    cette mesure-ci dit la meme chose plus tot et plus clairement.
    """
    assert len(SOURCES_DOCUMENTAIRES) == 5, sorted(SOURCES_DOCUMENTAIRES)
    for source, decoupe in sorted(SOURCES_DOCUMENTAIRES.items()):
        assert decoupe().strip(), source


def test_l_ordre_de_la_TUI_est_EXACTEMENT_celui_de_la_GUI():
    """`EPIC11-ARB` du 2026-09-06 : l'ecart delibere est **ferme**.

    Les deux listes n'ont aucun element en commun -- la GUI porte des noms
    d'onglet (`atelier-pdf`), la TUI des libelles d'ecran (`Pdf`) --, donc la
    confrontation passe par le suffixe. C'est le seul point de contact des deux
    coquilles, et sans lui « la TUI a son propre ordre » se rouvre en silence.
    """
    de_la_gui = tuple(nom.removeprefix("atelier-")
                      for nom in coquille.ORDRE_ATELIERS)
    de_la_tui = tuple(nom.casefold() for nom in projet_lecture.ATELIERS)
    assert de_la_gui == de_la_tui, (de_la_gui, de_la_tui)
    # Anti-tautologie : le `removeprefix` a bien retire quelque chose, sinon la
    # comparaison porterait sur deux listes deja identiques et ne mesurerait
    # pas la traduction d'un vocabulaire a l'autre.
    assert all(nom.startswith("atelier-") for nom in coquille.ORDRE_ATELIERS)


def test_la_confrontation_a_la_GUI_MORD():
    """Volet symetrique : une GUI reordonnee doit sortir de la mesure."""
    permutee = ("atelier-extraction", "atelier-scan", "atelier-pdf",
                "atelier-exports")
    de_la_tui = tuple(nom.casefold() for nom in projet_lecture.ATELIERS)
    assert tuple(n.removeprefix("atelier-") for n in permutee) != de_la_tui


# ---------------------------------------------------------------------------
# Le defaut adjacent : l'arborescence de la doc porte les CINQ entrees
# ---------------------------------------------------------------------------

def test_l_arborescence_de_la_doc_porte_les_CINQ_entrees_Projet_compris():
    """`E1-1` a **cinq** entrees depuis la story 11.11, et la doc les dessine.

    Mesure posee parce que le brief du 2026-09-06 annoncait l'inverse
    (« l'arborescence est sans `Projet` ») : elle l'a **toujours** portee, et
    c'est la mesure qui le dit plutot qu'une relecture. Le volet a de la valeur
    dans l'autre sens -- une entree perdue au prochain reformatage.
    """
    bloc = _bloc_arborescence_de_la_doc()
    dessinees = re.findall(r"•\s+(\w+)", bloc)
    attendues = list(projet_lecture.ATELIERS) + [projet_lecture.PROJET]
    assert dessinees == attendues, (dessinees, attendues)
