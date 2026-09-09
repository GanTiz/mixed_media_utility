"""Le NOM d'un tirage porte sa MISE EN PAGE -- `EPIC11-ARB-171` (lot B0, AC 2.9).

Ce que l'arbitrage ferme, verbatim de la mesure qui l'a fonde :

```
4 f/page -> projet_demo_plan-04_25_planches.pdf
8 f/page -> projet_demo_plan-04_25_planches.pdf
                                            => IDENTIQUES
```

Deux mises en page du **meme lot** rendaient le meme nom. Ce n'etait pas de la
destruction silencieuse -- le conflit de tirage tombait, donc `EPIC11-ARB-89`
jouait --, mais le motif du refus devenait **opaque** : « ce tirage existe
deja » sans dire que c'est une autre forme, et deux PDF sur un disque que rien
ne distingue.

**Ce banc ne mesure pas la longueur comme une garde**, et c'est l'objet de sa
derniere section : la fonction n'a **aucune** borne, elle n'en gagne pas ici, et
un grep de frontiere negative le mesure -- une absence ne se mesure pas
autrement.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from mixed_media_utility import page_templates
from mixed_media_utility.io import naming


#: Les couples `(orientation, cardinal)` que le vocabulaire offre, **lus** et
#: jamais recopies : `frames_per_page_vocabulary` est retire par orientation
#: (`EPIC5-ARB-62` / `-64`), donc une liste ecrite a la main ici perimerait au
#: premier cardinal retire, en silence.
def _couples_du_vocabulaire() -> list[tuple[str, int]]:
    return [(orientation, cardinal)
            for orientation in page_templates.ORIENTATIONS
            for cardinal in page_templates.frames_per_page_vocabulary(orientation)]


def _gabarit(orientation: str, cardinal: int) -> str:
    return page_templates.build_template_id(
        orientation, cardinal, page_templates.DEFAULT_MARGIN_PRESET)


# ---------------------------------------------------------------------------
# B0.1 -- la forme du nom, et la disparition du mot `planches`
# ---------------------------------------------------------------------------


def test_le_nom_porte_le_cardinal_et_l_orientation_abregee():
    """La forme des maquettes, a la lettre : `..._<Nf-ori>[_vN].pdf`.

    L'exemple est celui d'`E5-0` (`projet_demo_plan-04_25_8f-pay_v3.pdf`), et
    c'est le seul endroit de ce banc ou un nom complet est ecrit en clair : il
    vient d'une maquette validee, pas d'une deduction.
    """
    assert naming.build_sheets_pdf_filename(
        "projet_demo", "plan-04", "plan-04_25", 3,
        template_id=_gabarit(page_templates.ORIENTATION_PAYSAGE, 8),
    ) == "projet_demo_plan-04_25_8f-pay_v3.pdf"

    assert naming.build_sheets_pdf_filename(
        "projet_demo", "plan-04", "plan-04_25",
        template_id=_gabarit(page_templates.ORIENTATION_PORTRAIT, 4),
    ) == "projet_demo_plan-04_25_4f-por.pdf"


@pytest.mark.parametrize("orientation,cardinal", _couples_du_vocabulaire())
def test_AUCUN_nom_ne_porte_plus_le_mot_planches(orientation, cardinal):
    """Frontiere negative, sur **tout** le vocabulaire et pas sur un echantillon.

    Le mot ne portait aucune information -- tous les fichiers de `planches/` qui
    ne sont pas une mire sont des planches -- et il occupait la place ou la mise
    en page devait aller. Un producteur qui le reintroduirait, meme pour une
    seule forme, ferait revenir la collision d'`EPIC11-ARB-171`.
    """
    nom = naming.build_sheets_pdf_filename(
        "demo", "R", "R_24", template_id=_gabarit(orientation, cardinal))
    assert "planches" not in nom, nom
    assert nom.endswith(f"_{cardinal}f-{orientation[:3]}.pdf"), nom


def test_l_ancienne_forme_n_est_plus_ECRITE_mais_reste_RECONNUE():
    """`legacy_sheets_pdf_filename` est le seul survivant du mot `planches`.

    Il existe pour une raison mesuree ailleurs (`test_enumeration_des_tirages`)
    : un tirage deja pose sur un disque a **consomme son rang**, et aucun
    fichier deja ecrit n'est renomme. Ce test tient la moitie qui le concerne
    ici -- l'ancienne forme est produite par une fonction SEPAREE, jamais par
    un repli du producteur.
    """
    assert naming.legacy_sheets_pdf_filename("demo", "R", "R_24", 2) \
        == "demo_R_24_planches_v2.pdf"
    # Et le producteur, lui, exige un gabarit : il n'a aucun repli qui
    # reproduirait l'ancienne forme par omission.
    with pytest.raises(TypeError):
        naming.build_sheets_pdf_filename("demo", "R", "R_24")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# B0.2 -- le fragment est DERIVE du gabarit, jamais compose a part
# ---------------------------------------------------------------------------


def test_changer_le_GABARIT_change_le_nom_meme_a_arguments_egaux():
    """AC 2.9a : le nom **suit** le gabarit.

    Les trois autres arguments sont rigoureusement identiques d'un appel a
    l'autre : la seule variable est le `template_id`, donc le seul ecart
    possible entre les noms vient de lui.
    """
    noms = {
        gabarit: naming.build_sheets_pdf_filename(
            "demo", "R", "R_24", template_id=gabarit)
        for gabarit in (_gabarit(page_templates.ORIENTATION_PORTRAIT, 2),
                        _gabarit(page_templates.ORIENTATION_PORTRAIT, 8),
                        _gabarit(page_templates.ORIENTATION_PAYSAGE, 2))
    }
    assert len(set(noms.values())) == 3, noms


def test_le_fragment_vient_du_REGISTRE_et_non_d_un_decoupage_de_la_chaine():
    """Le mutant que l'AC 2.9 nomme : « composer le fragment a part ».

    Un `template_id` que le registre ne resout pas est **refuse**. C'est la
    difference observable entre lire le registre et decouper la chaine : un
    decoupage syntaxique accepterait `tpl-a4-portrait-7f-v2`, qui a la bonne
    forme et n'existe pas -- et rendrait `7f-por`, un nom de fichier pour une
    planche impossible.
    """
    faux = "tpl-a4-portrait-7f-v2"
    assert faux not in page_templates.known_template_ids()
    with pytest.raises(naming.NamingError):
        naming.build_sheets_pdf_filename("demo", "R", "R_24", template_id=faux)
    # Et le refus vaut aussi pour ce qui n'a pas la forme d'un gabarit.
    for absurde in ("", "tpl-a4-portrait-2f", "8f-pay", None):
        with pytest.raises(naming.NamingError):
            naming.build_sheets_pdf_filename(
                "demo", "R", "R_24", template_id=absurde)  # type: ignore[arg-type]


def test_les_abreviations_d_orientation_restent_DISTINCTES():
    """Frontiere negative sur la troncature, et elle mesure l'avenir.

    Le fragment abrege l'orientation par troncature -- ce qui la fait suivre le
    vocabulaire au lieu d'une table figee -- au prix d'une collision possible :
    deux orientations partageant leurs premieres lettres rendraient le meme
    fragment, donc le meme nom pour deux mises en page differentes, c'est-a-dire
    le defaut exact qu'`EPIC11-ARB-171` ferme. Le jour ou une troisieme
    orientation entrerait dans `ORIENTATIONS`, ce test rougirait avant elle.
    """
    abreges = [o[:naming.ORIENTATION_ABBREV_LENGTH]
               for o in page_templates.ORIENTATIONS]
    assert len(set(abreges)) == len(page_templates.ORIENTATIONS), abreges


# ---------------------------------------------------------------------------
# B0.3 -- ensemble EXACT : nom egal <=> mise en page egale
# ---------------------------------------------------------------------------


def test_l_ensemble_des_couples_qui_rendent_le_MEME_nom_est_EXACTEMENT_les_couples_EGAUX():
    """AC 2.9c, et c'est une equivalence, pas une implication.

    « Deux mises en page rendent deux noms differents » se satisferait d'un
    seul contre-exemple trouve ; ce qui est mesure ici est l'ensemble des
    couples `(gauche, droite)` dont les noms coincident, compare a l'ensemble
    des couples egaux. Une forme qui se mettrait a partager son nom avec une
    autre entrerait dans le premier et pas dans le second.

    Le lot, le projet et le rang sont **fixes** : ce sont les seules autres
    entrees du nom, donc tout ecart mesure ici vient bien de la mise en page.
    """
    couples = _couples_du_vocabulaire()
    assert len(couples) >= 3, couples
    noms = {couple: naming.build_sheets_pdf_filename(
        "demo", "R", "R_24", 2, template_id=_gabarit(*couple))
        for couple in couples}

    coincidences = {(gauche, droite) for gauche in couples for droite in couples
                    if noms[gauche] == noms[droite]}
    egaux = {(couple, couple) for couple in couples}
    assert coincidences == egaux, sorted(coincidences - egaux)


def test_les_deux_mises_en_page_du_MEME_lot_de_la_mesure_ne_se_confondent_plus():
    """Le cas litteral de la mesure d'`EPIC11-ARB-171`, 4 f contre 8 f."""
    quatre, huit = (naming.build_sheets_pdf_filename(
        "projet_demo", "plan-04", "plan-04_25",
        template_id=_gabarit(page_templates.ORIENTATION_PORTRAIT, cardinal))
        for cardinal in (4, 8))
    assert quatre != huit, (quatre, huit)


# ---------------------------------------------------------------------------
# B0.4 -- la longueur, mesuree et comparee a l'ancienne forme
# ---------------------------------------------------------------------------


def test_le_nom_ne_GRANDIT_pas_sur_l_exemple_des_maquettes():
    """La contrainte d'Egan (« garder la meme longueur »), **mesuree**.

    Les deux longueurs sont calculees, pas recopiees : 38 caracteres pour
    l'ancienne forme, 36 pour la neuve, sur l'exemple que la maquette `E5-0`
    porte. Le mot `planches` (8 caracteres) part, `8f-pay` (6) le remplace.
    """
    ancien = naming.legacy_sheets_pdf_filename(
        "projet_demo", "plan-04", "plan-04_25", 3)
    neuf = naming.build_sheets_pdf_filename(
        "projet_demo", "plan-04", "plan-04_25", 3,
        template_id=_gabarit(page_templates.ORIENTATION_PAYSAGE, 8))
    assert len(neuf) <= len(ancien), (neuf, ancien)
    assert (len(ancien), len(neuf)) == (38, 36), (ancien, neuf)


@pytest.mark.parametrize("orientation,cardinal", _couples_du_vocabulaire())
def test_AUCUNE_mise_en_page_du_vocabulaire_n_allonge_le_nom(orientation, cardinal):
    """Volet symetrique du precedent : la mesure ne vaut pas que sur `8f-pay`.

    Le fragment le plus long du vocabulaire est de meme largeur que les autres
    (`Nf-ori`, N a un chiffre), donc aucune forme n'allonge le nom -- et si un
    cardinal a deux chiffres entrait au vocabulaire, ce test le dirait au lieu
    de laisser la promesse d'Egan se perimer en silence.
    """
    ancien = naming.legacy_sheets_pdf_filename("demo", "R", "R_24", 2)
    neuf = naming.build_sheets_pdf_filename(
        "demo", "R", "R_24", 2, template_id=_gabarit(orientation, cardinal))
    assert len(neuf) <= len(ancien), (neuf, ancien)


# ---------------------------------------------------------------------------
# B0.5 -- AUCUNE garde de longueur n'est ajoutee (frontiere negative)
# ---------------------------------------------------------------------------

#: Ce qu'une garde de longueur ressemblerait, dans ce module. La liste est
#: volontairement large : c'est une frontiere **negative**, et une frontiere
#: negative qui ne chercherait qu'une seule forme ne mesurerait qu'elle.
_FORMES_DE_GARDE = (
    "CANONICAL_ID_MAX_LENGTH",
    "LEGACY_ID_MAX_LENGTH",
    "MAX_LENGTH",
    "len(",
    "255",
)


def _code_sans_prose(fonction) -> str:
    """Le CODE d'une fonction, docstrings et commentaires retires.

    Le retrait se fait a l'**AST** et non par un filtre de lignes : les
    docstrings de ces trois fonctions citent `CANONICAL_ID_MAX_LENGTH` et la
    borne de 255 octets precisement pour dire qu'elles ne sont PAS posees, et
    un filtre naif ferait rougir la frontiere sur la prose qui l'explique --
    c'est-a-dire qu'il rendrait la documentation impossible a ecrire.
    """
    arbre = ast.parse(textwrap.dedent(inspect.getsource(fonction)))
    for noeud in ast.walk(arbre):
        corps = getattr(noeud, "body", None)
        if not isinstance(corps, list) or not corps:
            continue
        premier = corps[0]
        if (isinstance(premier, ast.Expr)
                and isinstance(premier.value, ast.Constant)
                and isinstance(premier.value.value, str)):
            corps.pop(0)
    # `ast.unparse` ne rend jamais les commentaires : ils sortent avec.
    return ast.unparse(arbre)


def _source_des_deux_producteurs() -> str:
    return "\n".join(_code_sans_prose(fonction) for fonction in (
        naming.build_sheets_pdf_filename,
        naming.legacy_sheets_pdf_filename,
        naming.sheets_layout_fragment,
    ))


def test_le_producteur_de_nom_de_tirage_ne_pose_AUCUNE_garde_de_longueur():
    """AC 2.9e : un grep qui rend zero, et c'est la seule mesure d'une absence.

    La fonction n'avait aucune borne avant cet arbitrage -- mesure du
    2026-09-02 : 266 caracteres a 200/200 d'identifiants, **1066** a 1000/1000,
    sans qu'aucun `NamingError` soit leve. En poser une ici serait un arbitrage
    neuf que personne n'a demande, et il se prendrait pour un effet de bord de
    l'AC 2.9.

    La vraie borne est celle du **systeme de fichiers** (255 octets par
    composant sur ext4), que ce module ne connait pas et qui etait deja
    franchissable avant `EPIC11-ARB-171`. Elle est routee en dette.
    """
    code = _source_des_deux_producteurs()
    trouvees = [forme for forme in _FORMES_DE_GARDE if forme in code]
    assert trouvees == [], (trouvees, code)

    # **Volet symetrique de la frontiere elle-meme** : sans lui, un
    # `_code_sans_prose` qui rendrait la chaine vide -- ou une liste de formes
    # devenue vide -- ferait passer ce test en ne mesurant plus rien.
    assert "build_sheets_pdf_filename" in code and _FORMES_DE_GARDE
    assert any(forme in inspect.getsource(naming.build_sheets_pdf_filename)
               for forme in _FORMES_DE_GARDE), (
        "les docstrings ne citent plus la borne : la frontiere ci-dessus ne "
        "distingue plus le code de la prose, elle serait verte par vacuite")


def test_le_nom_d_un_tirage_est_NON_BORNE_et_le_banc_le_montre():
    """Volet symetrique de la frontiere ci-dessus.

    Sans lui, le grep resterait vert sur une garde ecrite autrement -- une
    comparaison posee dans une fonction voisine, une exception levee plus haut.
    La preuve qui ne se contourne pas est un nom **effectivement** produit
    au-dela de toute borne du depot.
    """
    long_lot = "L" * 1000
    nom = naming.build_sheets_pdf_filename(
        "P" * 1000, "R", long_lot,
        template_id=_gabarit(page_templates.ORIENTATION_PORTRAIT, 2))
    assert len(nom) > naming.CANONICAL_ID_MAX_LENGTH
    assert len(nom) > naming.LEGACY_ID_MAX_LENGTH
    assert long_lot in nom
