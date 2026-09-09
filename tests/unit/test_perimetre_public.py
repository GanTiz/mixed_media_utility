"""`EPIC11-ARB-268` -- ce que l'orphelin public porte de `_bmad-output/`.

Le depot public part **sans** `_bmad-output/` (`REGLE:
public-contenu-de-l-orphelin`), a quelques chemins pres : ceux que les bancs
lisent. Ils etaient cinq au 2026-09-07 au matin, **trois** apres la liaison du
soir -- le cardinal se lit dans `PORTES_PAR_LE_PUBLIC`, jamais ici, un nombre
recopie se perimant a chaque deplacement de fichier (et il s'est perime deux
fois dans la journee). Le recensement du 2026-09-07 a renverse l'estimation de cette regle --
elle annoncait « quelques bancs », il y en a **86**, dont 73 sur les seules
maquettes UX.

**Pourquoi une frontiere plutot qu'une liste d'exclusion dans un script de
publication.** La regle du matin **etait** une consigne ecrite, et son chiffre
etait faux d'un ordre de grandeur. Une liste recopiee ailleurs derive des qu'un
banc neuf lit un sixieme chemin, et **rien ne le dirait** : la CI publique
n'existe pas encore pour rougir. La garde vit donc du cote PRIVE, ou elle peut
mordre aujourd'hui -- avant la publication, pas apres.

**Mesuree sur l'AST, jamais sur le texte.** Les docstrings de ce depot citent
abondamment `_bmad-output/` -- celui-ci le fait a chaque paragraphe. Un `grep`
compterait la prose et rendrait le test faux dans les deux sens.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
BANCS = RACINE / "tests"

# L'aide qui distingue les DEUX REGIMES -- depot de travail contre historique
# orphelin du public -- vit dans `tests/_chemins_bmad.py`, ecrite une fois pour
# ses trois appelants (`conftest.py`, ce banc, `test_selection_par_dependance`).
# Une seconde redaction de `(RACINE / chemin).exists()` serait triviale a
# ecrire et divergerait sans que rien ne le dise, ce qui est le defaut exact
# que ce fichier existe pour attraper ailleurs.
sys.path.insert(0, str(BANCS))
from _chemins_bmad import porte_l_archive_privee  # noqa: E402

#: Le nom du dossier de methode, tel qu'il apparait dans un chemin construit.
DOSSIER = "_bmad-output"

#: Les chemins que l'orphelin public porte (`EPIC11-ARB-268`, Egan le
#: 2026-09-07, par invite). Tout le reste de `_bmad-output/` -- stories,
#: arbitrages, retrospectives, comptes rendus de mesure, rapports de revue --
#: reste prive : ~1 000 fichiers sur 1 091, et aucun banc ne les lit.
#:
#: **ILS ETAIENT CINQ, ILS SONT TROIS depuis la liaison du 2026-09-07**, et les
#: deux qui sortent ne sortent pas de la liste : ils sortent de
#: `_bmad-output/`. Le principe de l'arbitrage -- « les chemins que les bancs
#: LISENT » -- est inchange ; c'est l'arbre qui a bouge sous lui, deux fois et
#: dans le bon sens :
#:
#: * `_bmad-output/specs` vit desormais dans `src/mixed_media_utility/specs`,
#:   c'est-a-dire DANS la roue. C'est ce qui ferme « un `pip install mmu-tui`
#:   ne trouve pas ses schemas JSON » -- un defaut d'installation, pas de
#:   perimetre ;
#: * `ARCHITECTURE_DETAILED.md` vit sous `docs/guide-developpeur/`, avec la
#:   documentation livree, sur accord d'Egan du meme jour.
#:
#: Les deux etaient donc promis au public par ce tuple **et** deja portes au
#: public par un autre chemin. C'est cette frontiere qui l'a dit, en refusant
#: de promettre ce qui n'existe plus a l'endroit promis.
PORTES_PAR_LE_PUBLIC = (
    "_bmad-output/planning-artifacts/ux-designs",
    "_bmad-output/implementation-artifacts/deferred-work.md",
    "_bmad-output/test-artifacts/cible-de-mesure/cible_lut_v3.json",
)

#: Les chemins qui restent PRIVES bien qu'un banc les lise, et le banc qui les
#: lit est alors exclu de la CI publique. Quatre au 2026-09-07, tous trouves
#: par cette frontiere meme -- le recensement a la main qui a fonde
#: `EPIC11-ARB-268` en avait manque QUATRE sur neuf, parce qu'un `grep` ne
#: recompose pas une chaine de `/` etalee sur trois lignes.
#:
#: **Pourquoi ils ne rejoignent pas les cinq**, alors que la lettre de
#: l'arbitrage le voudrait : ce sont des documents d'ARCHIVE DE TRAVAIL -- une
#: fiche de story, deux dossiers d'arbitrage produit, une note de liaison --,
#: c'est-a-dire exactement ce que la regle du matin voulait garder prive. Et
#: les quatre bancs qui les lisent mesurent la TRACABILITE, jamais le produit :
#: chacun est un volet symetrique qui confronte le code a ce que le document
#: dit, ou qui prouve qu'un detecteur voit un message la ou il EST. Les exclure
#: de la CI publique ne retire aucune garde produit -- ce que l'option C
#: aurait fait, elle, en emportant les 73 confrontations aux maquettes.
PRIVES_ET_LEUR_BANC_EXCLU = {
    "_bmad-output/implementation-artifacts/11-7-atelier-pdf.md":
        "tests/unit/tui/test_atelier_pdf_confirmation.py",
    "_bmad-output/implementation-artifacts/"
    "decisions-2026-09-02-epic11-arb-176-scan-au-rang.md":
        "tests/unit/tui/test_versionnage_du_pdf_en_tui.py",
    "_bmad-output/implementation-artifacts/"
    "decisions-2026-09-03-epic11-arb-186-192-notes-planche-exports.md":
        "tests/unit/tui/test_atelier_exports_versions.py",
    "_bmad-output/implementation-artifacts/liaison-coeur-vague-3.md":
        "tests/unit/test_liaison_coeur_vague_3.py",
}


#: Les bancs qui NOMMENT un chemin de `_bmad-output/` sans jamais le lire,
#: parce que leur objet est de l'INTERDIRE. Ils restent verts sur le public,
#: ou le chemin n'existe pas du tout -- une prohibition qui ne trouve rien est
#: satisfaite, elle n'est pas cassee.
#:
#: **Pourquoi une exemption plutot qu'un detecteur plus fin.** Le detecteur
#: ci-dessous ne peut pas distinguer, dans l'AST, un litteral passe a
#: `in ligne` d'un litteral joint a une racine : ce sont le meme noeud. Il
#: garde donc sa prudence -- il attrape tout -- et l'exception est NOMMEE ici,
#: donc lisible, plutot que devinee la-bas.
#:
#: **Et elle est MESUREE, pas declaree** : `test_les_bancs_exemptes_NOMMENT_
#: vraiment_sans_JOINDRE` refuse toute entree de ce registre qui construirait
#: reellement un chemin (chaine de `/`). Sans ce volet, ce registre serait le
#: trou par lequel un vrai lecteur passerait -- exactement ce que la frontiere
#: existe pour empecher.
NOMMENT_SANS_LIRE = {
    "tests/unit/test_politiques_du_depot.py":
        "sa frontiere INTERDIT aux fichiers fonctionnels de resoudre les deux "
        "notes deplacees sous `docs/guide-developpeur/` ; elle cite l'ancien "
        "chemin pour le refuser, elle ne l'ouvre jamais",
}


def _feuilles(noeud: ast.AST) -> list[ast.AST]:
    """Aplatir une chaine de `/` en ses feuilles, de gauche a droite.

    `_RACINE / "_bmad-output" / "specs" / "project.schema.json"` est un arbre
    de `BinOp(Div)` imbrique a GAUCHE : sans cet aplatissement, on ne verrait
    que le dernier segment.
    """
    if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Div):
        return _feuilles(noeud.left) + _feuilles(noeud.right)
    return [noeud]


def _texte(noeud: ast.AST) -> str | None:
    """Le contenu d'une feuille quand c'est une chaine litterale, sinon `None`."""
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    return None


def _chemin_de_la_chaine(feuilles: list[ast.AST]) -> str | None:
    """Le chemin sous `_bmad-output/` qu'une chaine de `/` construit.

    On repart du segment qui NOMME le dossier -- il peut lui-meme porter la
    suite (`"_bmad-output/specs/project.schema.json"` en un seul litteral) --
    puis on colle les segments litteraux qui suivent. Un segment non litteral
    **arrete** la lecture : ce qui vient apres n'est pas connu ici, et deviner
    serait pire que de s'arreter.
    """
    for rang, feuille in enumerate(feuilles):
        texte = _texte(feuille)
        if texte is None:
            continue
        if not (texte == DOSSIER or texte.startswith(f"{DOSSIER}/")):
            continue
        segments = [texte.strip("/")]
        for suivante in feuilles[rang + 1:]:
            suite = _texte(suivante)
            if suite is None:
                break
            segments.append(suite.strip("/"))
        return "/".join(segments)
    return None


def chemins_lus_par_les_bancs() -> dict[str, set[str]]:
    """Tout chemin sous `_bmad-output/` qu'un fichier de banc CONSTRUIT.

    Rend `{chemin: {fichiers}}` plutot qu'un simple ensemble : un rouge doit
    nommer le banc a reprendre, pas seulement le chemin fautif.
    """
    releve: dict[str, set[str]] = {}
    for banc in sorted(BANCS.rglob("test_*.py")):
        # **Ce fichier-ci s'exclut, et ce n'est pas une commodite.** Ses deux
        # declarations sont des chaines litterales portant `_bmad-output/...` :
        # sans cette ligne, il se compte lui-meme comme LECTEUR de chacun des
        # neuf chemins, et le volet « plus aucun banc ne lit ce chemin »
        # deviendrait vert pour toujours -- une frontiere qui se satisfait
        # elle-meme. Il ne LIT aucun de ces fichiers a l'execution.
        if banc.resolve() == Path(__file__).resolve():
            continue
        # Meme famille, et pour le meme motif : un banc qui NOMME un chemin
        # afin de l'interdire n'en est pas un lecteur. Le registre est mesure
        # juste en dessous, il n'est pas cru sur parole.
        if str(banc.relative_to(RACINE)) in NOMMENT_SANS_LIRE:
            continue
        try:
            arbre = ast.parse(banc.read_text(encoding="utf-8"))
        except SyntaxError:                      # pragma: no cover - defensif
            continue
        vus: set[str] = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.BinOp) and isinstance(noeud.op, ast.Div):
                chemin = _chemin_de_la_chaine(_feuilles(noeud))
            else:
                texte = _texte(noeud)
                chemin = (texte.strip("/") if texte and (
                    texte == DOSSIER or texte.startswith(f"{DOSSIER}/")) else None)
            if chemin is not None:
                vus.add(chemin)
        for chemin in vus:
            releve.setdefault(chemin, set()).add(
                str(banc.relative_to(RACINE)))
    return releve


#: Borne du nombre de FICHIERS que les chemins portes selectionnent. Mesuree
#: sur cet arbre au 2026-09-07, apres la liaison :
#:
#:     porte aujourd'hui                       362   (360 de maquettes, + 2)
#:     avec `implementation-artifacts` ajoute  841   (479 de plus)
#:     tout `_bmad-output/`                   1117
#:
#: La borne se pose ENTRE les deux premiers, et le second n'est pas un exemple
#: choisi : c'est le mutant `N62`, qui a SURVECU a la premiere redaction de ce
#: banc. Ajouter un prefixe LARGE ne faisait rougir aucune frontiere, parce que
#: le volet « tout chemin porte est lu » est satisfait par HERITAGE -- un
#: dossier herite des lecteurs de ses enfants, et `deferred-work.md` est sous
#: `implementation-artifacts/`. Le perimetre pouvait donc grossir de 479
#: fichiers prives en silence, ce qui est litteralement ce
#: qu'`EPIC11-ARB-268` refuse.
BORNE_DE_FICHIERS_PORTES = 450


def _fichiers_portes(portes=PORTES_PAR_LE_PUBLIC) -> list[Path]:
    """Les fichiers reels que `portes` selectionne, dossiers developpes."""
    retenus: list[Path] = []
    for porte in portes:
        depart = RACINE / porte
        if depart.is_file():
            retenus.append(depart)
        elif depart.is_dir():
            retenus.extend(c for c in depart.rglob("*") if c.is_file())
    return retenus


def test_le_perimetre_porte_reste_sous_la_borne_de_fichiers():
    """Ce que l'orphelin emporte se compte, il ne se decrit pas.

    Les autres volets mesurent QUELS chemins sont portes ; celui-ci mesure
    COMBIEN de fichiers ils emportent, et c'est la seule question que le
    lecteur d'`EPIC11-ARB-268` se pose vraiment (« ~1 000 sur 1 091 restent
    prives »).
    """
    portes = _fichiers_portes()
    assert len(portes) <= BORNE_DE_FICHIERS_PORTES, (
        f"{len(portes)} fichiers de `{DOSSIER}/` partiraient au public, borne "
        f"{BORNE_DE_FICHIERS_PORTES}. Un chemin porte est probablement trop "
        "LARGE : il emporte l'archive de travail avec ce qu'un banc lit.")


def test_la_borne_MORD_sur_un_prefixe_TROP_LARGE():
    """La frontiere negative, et elle rejoue le mutant `N62` exactement.

    Une borne qu'aucune configuration plausible ne franchit ne mesure rien. On
    rejoue donc le calcul avec `implementation-artifacts` porte en entier --
    ce que la premiere redaction de ce banc laissait passer -- et on exige
    qu'il la franchisse.
    """
    # **La sonde porte sur les chemins PRIVES, et non sur le dossier large.**
    # Premiere redaction, mesuree fausse sur l'orphelin reel : elle sondait
    # `implementation-artifacts`, qui EXISTE sur le public -- il y porte
    # `deferred-work.md`, qui est l'une des trois portes. Le regime ne se lit
    # donc pas sur ce dossier mais sur ce que le public n'a PAS.
    if not porte_l_archive_privee(RACINE, PRIVES_ET_LEUR_BANC_EXCLU):
        pytest.skip(
            "aucune des archives declarees PRIVEES n'existe ici : ce depot "
            "n'est pas celui du TRAVAIL (historique orphelin du depot public, "
            "EPIC8-ARB-12). Le prefixe TROP LARGE n'y couvre que les fichiers "
            "deja portes -- mesure : 359 contre une borne de 450 --, si bien "
            "que cette frontiere negative n'y mesurerait que l'absence de "
            "l'archive, jamais la borne.")

    trop_large = (*PORTES_PAR_LE_PUBLIC, f"{DOSSIER}/implementation-artifacts")
    assert len(_fichiers_portes(trop_large)) > BORNE_DE_FICHIERS_PORTES, (
        "porter `implementation-artifacts` en entier ne franchit pas la "
        "borne : elle ne mesure rien")


def test_aucun_chemin_porte_n_est_ANCETRE_d_un_autre():
    """Deux portes dont l'une contient l'autre : la plus large decide seule.

    Le volet « tout chemin porte est lu » deviendrait alors vrai pour la large
    par heritage de la fine, et le perimetre grossirait sans qu'aucun autre
    volet ne bronche. C'est l'autre moitie du mutant `N62`, mesuree sur la
    FORME plutot que sur le cardinal -- les deux ensemble ferment le cas ou un
    prefixe large arriverait sous la borne.
    """
    for large in PORTES_PAR_LE_PUBLIC:
        for fine in PORTES_PAR_LE_PUBLIC:
            if large == fine:
                continue
            assert not fine.startswith(f"{large}/"), (
                f"`{large}` contient `{fine}` : la porte fine est inutile, et "
                "la large emporte tout ce qui est entre les deux")


def test_les_bancs_exemptes_NOMMENT_vraiment_sans_JOINDRE():
    """Le registre `NOMMENT_SANS_LIRE` ne doit jamais couvrir un vrai lecteur.

    Une exemption qu'on declare est une exemption qu'on peut elargir par
    inadvertance -- et celle-ci se trouve exactement sur le chemin qu'une
    frontiere de perimetre existe pour fermer. On mesure donc la propriete qui
    la justifie plutot que de la relire : un banc exempte ne construit AUCUN
    chemin sous `_bmad-output/` par une chaine de `/`. Il ne peut donc rien
    ouvrir la-bas, quelle que soit la prose de son entree.

    Le volet symetrique est dans la meme phrase : une entree qui ne
    correspondrait a aucun fichier fait rougir, sans quoi le registre
    survivrait a la suppression du banc qu'il protege.
    """
    for chemin_du_banc, motif in sorted(NOMMENT_SANS_LIRE.items()):
        banc = RACINE / chemin_du_banc
        assert banc.is_file(), (
            f"`{chemin_du_banc}` est exempte et n'existe pas : le registre "
            "survit a son banc")
        assert motif.strip(), f"`{chemin_du_banc}` est exempte sans motif"
        arbre = ast.parse(banc.read_text(encoding="utf-8"))
        joints = [c for noeud in ast.walk(arbre)
                  if isinstance(noeud, ast.BinOp)
                  and isinstance(noeud.op, ast.Div)
                  and (c := _chemin_de_la_chaine(_feuilles(noeud))) is not None]
        assert not joints, (
            f"`{chemin_du_banc}` est exempte comme « nomme sans lire », mais "
            f"il CONSTRUIT un chemin sous `{DOSSIER}/` : {sorted(set(joints))}. "
            "L'exemption couvrirait un vrai lecteur.")


def _est_porte(chemin: str) -> bool:
    """Un chemin est couvert s'il tombe DANS l'un des cinq, ou le CONTIENT.

    Le second sens n'est pas une facilite : `_RACINE / "_bmad-output"` affecte
    a une variable, puis complete ailleurs, ne rend ici que la racine. La
    refuser rendrait la frontiere rouge sur du code correct.
    """
    if chemin in PRIVES_ET_LEUR_BANC_EXCLU:
        return True
    for porte in PORTES_PAR_LE_PUBLIC:
        if chemin == porte:
            return True
        if chemin.startswith(f"{porte}/"):
            return True
        if porte.startswith(f"{chemin}/"):
            return True
    return False


def test_aucun_banc_ne_lit_un_SIXIEME_chemin_de_bmad_output():
    """La frontiere elle-meme : la liste des cinq reste SUFFISANTE.

    Un banc qui lirait ailleurs sous `_bmad-output/` serait vert ici et rouge
    sur le depot public -- c'est-a-dire decouvert au pire moment, apres la
    publication. Le remede est l'un des deux, jamais un blocage sec : ou bien
    le chemin rejoint les cinq (et l'arbitrage se revise, par invite), ou bien
    le banc lit ce dont il a besoin sous `tests/fixtures/`, qui est la regle
    generale du depot.
    """
    releve = chemins_lus_par_les_bancs()
    dehors = {chemin: sorted(bancs) for chemin, bancs in releve.items()
              if not _est_porte(chemin)}
    assert not dehors, (
        "ces bancs lisent un chemin de `_bmad-output/` que l'orphelin public "
        "NE PORTE PAS (`EPIC11-ARB-268`) -- ils seraient rouges sur le "
        f"public :\n" + "\n".join(
            f"    {chemin}\n        {', '.join(bancs)}"
            for chemin, bancs in sorted(dehors.items())))


def test_les_CINQ_chemins_sont_tous_LUS_et_tous_PRESENTS():
    """Le volet symetrique, sans lequel la frontiere pourrait tout avaler.

    Deux facons pour la liste de devenir fausse sans que le test precedent
    bronche : un chemin qu'on y laisse alors que plus aucun banc ne le lit --
    l'orphelin publierait alors pour rien --, et un chemin qui n'existe plus
    dans l'arbre. Les deux se mesurent, plutot que de se relire.
    """
    releve = chemins_lus_par_les_bancs()
    for porte in PORTES_PAR_LE_PUBLIC:
        assert (RACINE / porte).exists(), (
            f"`{porte}` est promis au depot public et n'existe pas dans "
            "l'arbre : la liste des cinq est perimee")
        lecteurs = {chemin for chemin in releve
                    if chemin == porte or chemin.startswith(f"{porte}/")}
        assert lecteurs, (
            f"plus aucun banc ne lit `{porte}` -- le publier serait publier "
            "pour rien. Le retirer des cinq est la bonne nouvelle.")


def test_le_RECENSEMENT_porte_sur_un_ensemble_NON_VIDE():
    """Une frontiere appliquee a un ensemble vide serait verte sans mesurer.

    Le cardinal n'est pas fige : il monte quand un banc neuf lit une maquette,
    et c'est normal. Le plancher, lui, dit que le releve FONCTIONNE encore --
    un aplatissement casse, un `rglob` qui ne trouve plus les bancs, et les
    deux tests ci-dessus deviendraient verts en ne mesurant rien.
    """
    releve = chemins_lus_par_les_bancs()
    bancs = {banc for lecteurs in releve.values() for banc in lecteurs}
    assert len(bancs) >= 60, (
        f"seulement {len(bancs)} bancs construisent un chemin sous "
        f"`{DOSSIER}/` -- il y en avait 86 au 2026-09-07. Le releve est "
        "probablement casse plutot que le depot nettoye.")
    assert any(chemin.startswith(
        "_bmad-output/planning-artifacts/ux-designs") for chemin in releve), (
        "les maquettes UX ne sont plus vues du tout : l'aplatissement des "
        "chaines de `/` ne fonctionne plus")


def test_chaque_chemin_PRIVE_est_encore_lu_par_le_banc_qui_le_declare():
    """La contrepartie de la dispense, et elle vaut pour les deux sens.

    Une dispense qui survit a sa raison d'etre est un trou : le banc a pu
    cesser de lire ce document, ou un AUTRE banc s'y etre mis -- et celui-la
    serait rouge sur le public sans que personne l'ait declare. Meme famille
    que « un garde-fou pose pour une operation ponctuelle se retire quand elle
    est finie » : ce qui se mesure se tient.
    """
    releve = chemins_lus_par_les_bancs()
    for chemin, banc_declare in sorted(PRIVES_ET_LEUR_BANC_EXCLU.items()):
        lecteurs = releve.get(chemin)
        assert lecteurs, (
            f"plus aucun banc ne lit `{chemin}` : la dispense a survecu a sa "
            "raison d'etre, elle se retire")
        assert lecteurs == {banc_declare}, (
            f"`{chemin}` est desormais lu par {sorted(lecteurs)} et non par "
            f"le seul `{banc_declare}` : la liste des bancs a exclure de la "
            "CI publique est fausse")
