# -*- coding: utf-8 -*-
"""Le nom d'un profil de chaine : **saisie -> libelle du QR -> `chain_id`**.

Retour terrain d'Egan, 2026-09-06, verbatim et c'est la specification :

> Calibration : sans renseigner de nom, le nom de la chaine stocke dans le QR
> ne remplace pas le nom, qui est alors celui du pdf (avec .pdf a la fin).

**Le defaut mesure, et il l'a ete sur son scan reel avant d'etre corrige.** Le
QR de sa mire porte `scan_chain_label = 'hp envy Gambetta'`, decode sans
reglage particulier par `scan_detection` du depot ; son profil s'appelait
`HP envy Gambetta.pdf`, c'est-a-dire le NOM DU FICHIER. Les deux chaines
different par la **casse** ET par l'**extension** : c'est une preuve directe
que la valeur affichee ne venait pas de la feuille. Le champ etait decode et
n'etait lu par personne -- zero occurrence de `scan_chain_label` dans
`scan_calibrate.py` avant ce jour.

**Ce que ce banc mesure, et dans cet ordre** : que le libelle se lit sur la
page de calibration **que l'ajustement a retenue** (pas une autre), qu'il ne
prend la main que sur une saisie vide, qu'il est rendu **verbatim** -- ni
`strip`, ni `title`, ni `capitalize` --, et qu'un libelle qui ne peut pas
nommer un fichier ne fait **rien echouer**.

**Regle des fabriques** (`CLAUDE.md`) : la fabrique de pile produit au moins
deux pages **distinguables** -- des `page_index` et des `lot_id` differents,
jamais un remplissage uniforme --, et la page visee est jouee au **milieu**,
en **tete** et en **queue**. Le point 4 est celui que ce depot paie le plus
souvent : une cible au milieu demasque un `find` fautif, elle ne demasque pas
un balayage tronque.

**Regle des drapeaux** : la saisie de l'operateur varie dans les deux sens
(vide / renseignee), et c'est le drapeau dont toute la precedence depend.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import page_roles, scan_calibrate, scan_detection
from mixed_media_utility.io import payload as payload_io

#: La valeur **mesuree sur le scan reel d'Egan** (`hp_envy_gambetta.pdf`,
#: ingere a 300 dpi puis detecte par le code du depot). Sa casse mixte et son
#: espace ne sont pas decoratifs : ce sont eux qui rendent le banc
#: discriminant. Un test ecrit sur `chaine-a` serait vert sur une
#: normalisation abusive comme sur le nom du fichier.
LIBELLE_REEL = "hp envy Gambetta"

#: Les deux identifiants de gabarit lus sur la meme feuille reelle. Ils ne
#: servent a rien ici -- rien n'en depend --, et c'est justement pourquoi ils
#: valent d'etre les vrais : une fabrique calibree sur des valeurs inventees
#: mesure la synthese.
PRESET_REEL = "patches-17-v4"
TEMPLATE_REEL = "tpl-a4-portrait-2f-v2"

#: Le raster de terrain, et **il est DANS le depot depuis le 2026-09-07**.
#:
#: Ce bloc a designe pendant deux redactions un `hp_envy_gambetta.pdf` qui n'a
#: jamais existe au depot : d'abord par un chemin absolu vers le bloc-notes de
#: la session qui l'avait ecrit (finding `T1`, revue du 2026-09-07), puis par
#: un nom attendu sous `tests/fixtures/scans/` que personne n'y a jamais pose.
#: Les deux bancs de terrain SAUTAIENT donc partout, depuis toujours -- et un
#: banc qu'on ne peut pas rendre vert n'est pas un banc qui saute, c'est un
#: banc mort. La regle etait deja ecrite deux lignes plus haut ; elle n'avait
#: simplement pas ete appliquee a elle-meme.
#:
#: Ce qui a ferme le trou n'est pas un fichier de plus : c'est d'avoir REGARDE
#: ce que le depot portait deja. `tests/fixtures/scans/` contient une VRAIE
#: planche de calibration, et le code y lit son libelle de bout en bout. Les
#: deux autres PDF du dossier n'en sont pas -- ils rendent un libelle vide,
#: mesure le 2026-09-07. C'est exactement le geste que `CLAUDE.md` prescrit :
#: « interroger le raster reel du depot, pas seulement la fabrique ».
#:
#: Elle est meilleure que celle qu'on attendait, et pour une raison precise :
#: son libelle ne ressemble EN RIEN a son nom de fichier. Les deux assertions
#: negatives des bancs ci-dessous -- le profil ne porte ni le nom du scan ni
#: l'identite derivee -- deviennent donc discriminantes, la ou
#: `hp_envy_gambetta.pdf` et `hp-envy-gambetta.json` ne differaient que par
#: leurs separateurs.
NOM_DU_SCAN_REEL = "Page calibration HP ENVY La Seyne.pdf"

#: Le libelle **mesure** sur cette planche le 2026-09-07, par
#: `scan_calibrate.libelle_de_chaine_du_scan` apres ingestion a 300 dpi. Il est
#: fige en litteral et non recalcule : le derive du code qu'on mesure rendrait
#: le banc tautologique, defaut que ce depot a paye sur la constante centrale
#: de la calibration (`CLAUDE.md`, 17 mutants survivants de 5.9).
LIBELLE_DU_SCAN_REEL = "hp envy 4520 tiff 600 dpi auto corr off"

#: Le nom de fichier attendu, derive A LA MAIN de la recette de
#: `slugify_label` (minuscules, espaces -> tiret unique) plutot que par un
#: appel a cette fonction, pour la meme raison.
PROFIL_DU_SCAN_REEL = "hp-envy-4520-tiff-600-dpi-auto-corr-off.json"

#: Une autre planche se substitue a celle-ci par la PAIRE `MMU_SCAN_REEL` et
#: `MMU_SCAN_REEL_LIBELLE` -- jamais le chemin seul : sans le libelle attendu,
#: le banc comparerait la nouvelle planche a l'ancienne mesure et rougirait en
#: annoncant un defaut qui n'existe pas.
SCAN_REEL = Path(os.environ.get(
    "MMU_SCAN_REEL",
    Path(__file__).resolve().parents[1] / "fixtures" / "scans"
    / NOM_DU_SCAN_REEL))
LIBELLE_ATTENDU = os.environ.get("MMU_SCAN_REEL_LIBELLE", LIBELLE_DU_SCAN_REEL)


class _PageDeBanc:
    """Une page detectee, reduite a ce que `_read_calibration_pages` en lit.

    Trois attributs et pas un de plus : le role et le libelle vivent dans le
    payload, le statut et l'homographie sont les deux conditions de lisibilite.
    Un double plus riche mesurerait `DetectedPage`, qui a son propre banc.
    """

    def __init__(self, *, role, page_index, lot_id, libelle=None,
                 status=scan_detection.PAGE_OK, homography=object()):
        self.status = status
        self.homography = homography
        if role is None:
            self.payload = None
            return
        self.payload = {
            "page_role": role,
            # **Distinguables** : deux pages d'une meme pile ne partagent ni
            # leur index ni leur lot. Un remplissage uniforme rendrait une
            # permutation invisible.
            "page_index": page_index,
            "lot_id": lot_id,
            "template_id": TEMPLATE_REEL,
            "patch_preset_id": PRESET_REEL,
        }
        if libelle is not None:
            self.payload[payload_io.SCAN_CHAIN_LABEL_FIELD] = libelle


class _DetectionDeBanc:
    def __init__(self, pages):
        self.pages = tuple(pages)


def _planche(rang: int) -> _PageDeBanc:
    """Une planche d'images, distinguable de toutes les autres."""
    return _PageDeBanc(role=page_roles.PAGE_ROLE_IMAGES, page_index=rang,
                       lot_id=f"rush{rang}_24p0")


def _mire(libelle: str = LIBELLE_REEL) -> _PageDeBanc:
    return _PageDeBanc(role=page_roles.PAGE_ROLE_CALIBRATION, page_index=0,
                       lot_id="rush9_12p5", libelle=libelle)


def _pile(position: str, libelle: str = LIBELLE_REEL) -> _DetectionDeBanc:
    """Une pile de TROIS pages, la mire posee la ou on la demande.

    Trois et non deux : a deux, « en queue » et « ailleurs qu'en premiere
    position » sont le meme cas, et une faute de terminaison de boucle y est
    indiscernable d'une faute d'appariement.
    """
    mire = _mire(libelle)
    if position == "tete":
        return _DetectionDeBanc([mire, _planche(1), _planche(2)])
    if position == "queue":
        return _DetectionDeBanc([_planche(1), _planche(2), mire])
    return _DetectionDeBanc([_planche(1), mire, _planche(2)])


# ---------------------------------------------------------------------------
# Le libelle se lit sur la page de calibration, ou qu'elle soit dans la pile
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("position", ["tete", "milieu", "queue"])
def test_le_libelle_se_lit_quelle_que_soit_la_POSITION_de_la_mire(position):
    """Les trois positions, dont les **deux bords** (`CLAUDE.md`, point 4).

    Au milieu, un `find` fautif qui rendrait toujours la premiere page se
    demasque. En queue, c'est un balayage tronque qui se demasque -- un autre
    mode de panne, que la cible au milieu ne voit pas. En tete, c'est la
    symetrie du precedent.
    """
    assert scan_calibrate.libelle_de_chaine_du_scan(
        _pile(position)) == LIBELLE_REEL


def test_le_libelle_est_rendu_VERBATIM_casse_comprise():
    """Ni `strip`, ni `title`, ni `capitalize`.

    « Ce que la feuille porte est ce que le profil doit porter » : une
    normalisation cosmetique ferait diverger le nom du profil du nom imprime
    sur la page, et c'est exactement l'ecart -- de casse -- qui a rendu le
    defaut d'origine visible sur le scan d'Egan.
    """
    lu = scan_calibrate.libelle_de_chaine_du_scan(_pile("milieu"))
    assert lu == "hp envy Gambetta"
    assert lu != lu.title(), "un `.title()` s'est glisse dans le chemin"
    assert lu != lu.capitalize()
    # Les blancs de bord ne sont pas ronges non plus : le champ est de la prose.
    espace = scan_calibrate.libelle_de_chaine_du_scan(
        _pile("milieu", "  hp envy  "))
    assert espace == "  hp envy  "


def test_une_pile_SANS_page_de_calibration_ne_rend_RIEN():
    """`""` et jamais une valeur inventee : la ligne se replie, elle ne ment pas."""
    assert scan_calibrate.libelle_de_chaine_du_scan(
        _DetectionDeBanc([_planche(1), _planche(2)])) == ""


def test_DEUX_pages_de_calibration_ne_font_choisir_NI_l_une_NI_l_autre():
    """Le volet symetrique, et il compte autant.

    Le coeur **refuse** une pile a deux pages de calibration -- « en choisir
    une ajusterait la correction de tout le lot sur une feuille prise au hasard
    entre deux ». Nommer le profil d'apres la premiere des deux referait ce
    choix-la par la bande, sur le seul champ que ce chemin lit.
    """
    detection = _DetectionDeBanc([_mire("chaine du bureau"), _planche(1),
                                  _mire("chaine du labo")])
    assert scan_calibrate.libelle_de_chaine_du_scan(detection) == ""


def test_une_page_de_calibration_ILLISIBLE_ne_nomme_rien():
    """Statut refuse, homographie absente : la page est declaree, pas LUE.

    C'est la distinction d'`EPIC5-ARB-70`, et elle vaut ici pour la meme
    raison qu'a l'ajustement : une feuille dont la geometrie n'est pas resolue
    n'a pas ete lue, donc son payload n'a pas ete confronte a la page.
    """
    illisible = _PageDeBanc(role=page_roles.PAGE_ROLE_CALIBRATION,
                            page_index=0, lot_id="rush9_12p5",
                            libelle=LIBELLE_REEL,
                            status=scan_detection.PAGE_REFUSED,
                            homography=None)
    assert scan_calibrate.libelle_de_chaine_du_scan(
        _DetectionDeBanc([_planche(1), illisible])) == ""


# ---------------------------------------------------------------------------
# La precedence : saisie -> libelle du QR -> `chain_id`
# ---------------------------------------------------------------------------

CHAIN_ID = "300-pdf-abcdef012345"


def test_la_SAISIE_de_l_operateur_l_emporte_sur_le_libelle_du_QR():
    """Premier terme. Il vient de nommer ; une feuille imprimee il y a trois
    semaines ne doit pas le contredire."""
    assert scan_calibrate.etiquette_du_profil(
        "chaine du labo", _pile("milieu"), CHAIN_ID) == "chaine du labo"


def test_une_saisie_VIDE_laisse_la_main_au_libelle_du_QR():
    """Second terme -- **le defaut qu'Egan a signale**, mesure a l'endroit ou
    il se produit."""
    assert scan_calibrate.etiquette_du_profil(
        "", _pile("milieu"), CHAIN_ID) == LIBELLE_REEL


def test_une_saisie_de_BLANCS_vaut_une_saisie_vide():
    """Le drapeau a trois valeurs et non deux : vide, blancs, renseignee.

    `profile_file_stem` traite deja `'   '` comme une absence d'etiquette ; si
    la precedence ne le faisait pas, une saisie de blancs eteindrait le libelle
    du QR **et** se replierait ensuite sur le `chain_id` -- c'est-a-dire
    exactement le defaut d'origine, atteint par une autre porte.
    """
    assert scan_calibrate.etiquette_du_profil(
        "   ", _pile("milieu"), CHAIN_ID) == LIBELLE_REEL


def test_SANS_libelle_au_QR_la_precedence_tombe_sur_le_chain_id():
    """Troisieme terme, et il n'est pas ecrit dans cette fonction.

    Rendre `""` **est** le troisieme terme : `profile_file_stem` replie
    lui-meme une etiquette vide sur le `chain_id`, et le recopier ici ferait
    deux redactions de la meme regle. Le banc mesure donc `""`, et le mesure
    **avec** le repli qui suit, pour qu'un lecteur ne prenne pas ce vide pour
    un oubli.
    """
    from mixed_media_utility.io import calibration_profile

    feuille_ancienne = _PageDeBanc(role=page_roles.PAGE_ROLE_CALIBRATION,
                                   page_index=0, lot_id="rush9_12p5")
    detection = _DetectionDeBanc([_planche(1), feuille_ancienne])
    assert scan_calibrate.etiquette_du_profil("", detection, CHAIN_ID) == ""
    assert calibration_profile.profile_file_stem(
        {"chain_id": CHAIN_ID, "label": ""}) == CHAIN_ID


def test_un_libelle_qui_ne_peut_pas_NOMMER_un_fichier_ne_BLOQUE_rien(caplog):
    """La garde que le defaut d'origine n'avait pas, et sans elle D2 casse.

    `payload.validate_scan_chain_label` accepte de la **prose** -- « seules les
    longueurs et le vide sont refuses » -- la ou
    `calibration_profile.slugify_label` refuse tout ce qui n'est pas lettre,
    chiffre, espace, tiret ou souligne. Sans garde, une feuille legitimement
    nommee « hp envy 4520 (bureau) » ferait **refuser la calibration entiere**
    (`write_profile` levant) alors qu'elle aboutissait avant : une correction
    qui transforme un profil mal nomme en blocage sec, ce que
    `EPIC11-ARB-89` interdit nommement.

    Le repli se **dit** au journal : un nom qu'on ne peut pas porter n'est pas
    un silence.
    """
    with caplog.at_level(logging.WARNING):
        etiquette = scan_calibrate.etiquette_du_profil(
            "", _pile("milieu", "hp envy 4520 (bureau)"), CHAIN_ID)
    assert etiquette == ""
    assert "(bureau)" in caplog.text
    assert CHAIN_ID in caplog.text


def test_la_garde_du_nommage_INTERROGE_slugify_et_ne_la_RECOPIE_pas():
    """Volet symetrique : elle ne refuse pas ce que `slugify_label` accepte.

    Un libelle a espaces et a casse mixte -- le cas reel -- passe. Une garde
    ecrite trop large (une liste de caracteres recopiee a la main, qui
    divergerait de l'autorite) le refuserait, et le produit retomberait
    silencieusement sur le `chain_id` : le defaut d'origine, reintroduit par
    son propre correctif.
    """
    from mixed_media_utility.io import calibration_profile

    assert scan_calibrate.etiquette_du_profil(
        "", _pile("milieu"), CHAIN_ID) == LIBELLE_REEL
    assert calibration_profile.slugify_label(LIBELLE_REEL) == "hp-envy-gambetta"


def test_la_SAISIE_de_l_operateur_n_a_PAS_cette_garde_et_n_en_veut_pas():
    """L'asymetrie est deliberee, et la dire vaut mieux que la taire.

    Il a **demande** ce nom-la : le refus nomme de `write_profile` lui
    appartient, et le lui remplacer en silence par son `chain_id` serait « faire
    taire la demande de l'operateur », ce que `slugify_label` ecarte deja mot
    pour mot.
    """
    assert scan_calibrate.etiquette_du_profil(
        "hp envy (bureau)", _pile("milieu"), CHAIN_ID) == "hp envy (bureau)"


# ---------------------------------------------------------------------------
# La confrontation au RASTER REEL -- « une mesure de synthese mesure la
# synthese » (`CLAUDE.md`)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not SCAN_REEL.is_file(),
                    reason=f"raster de terrain absent : {SCAN_REEL}")
def test_le_libelle_se_lit_sur_le_SCAN_REEL_d_Egan(tmp_path):
    """Le QR de terrain, ingere et detecte par le code du depot.

    C'est la seule mesure qui reponde a la phrase d'Egan : les doubles
    ci-dessus mesurent la lecture d'un payload, celle-ci mesure que le payload
    **arrive** -- decodage QR compris, a 300 dpi, sur un raster que personne
    n'a fabrique pour ce banc.

    Le raster EST au depot depuis le 2026-09-07 : ce banc joue. Le `skipif`
    reste, pour le seul regime ou il a encore un sens -- un clone sans
    `git-lfs`, ou le PDF vaut 133 octets.
    """
    from mixed_media_utility import scan_ingest
    from mixed_media_utility.io import project_layout

    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)
    rapport = scan_ingest.ingest_scan_lot(projet, SCAN_REEL, dpi=300)
    detection = scan_detection.detect_lot_pages(projet, rapport, dpi=300)

    assert scan_calibrate.libelle_de_chaine_du_scan(detection) == LIBELLE_ATTENDU
    # **Et c'est bien ce que la precedence retient**, saisie vide : le profil
    # portera le libelle lu sur la feuille et non le nom du fichier scanne.
    assert scan_calibrate.etiquette_du_profil(
        "", detection, CHAIN_ID) == LIBELLE_ATTENDU
    assert scan_calibrate.etiquette_du_profil(
        "", detection, CHAIN_ID) != SCAN_REEL.name


@pytest.mark.skipif(not SCAN_REEL.is_file(),
                    reason=f"raster de terrain absent : {SCAN_REEL}")
def test_le_profil_ecrit_du_SCAN_REEL_porte_le_nom_de_la_FEUILLE(tmp_path):
    """De bout en bout, sur la mire d'Egan : le fichier ecrit porte son libelle.

    C'est la mesure du **cablage**, celle qu'aucun des doubles ci-dessus ne
    donne : la precedence peut etre juste et n'etre appelee nulle part -- c'est
    le defaut « un mecanisme juste, cable nulle part » que ce depot a paye sept
    fois. Ici la passe entiere tourne, sans nom saisi, et le disque repond.

    Les deux assertions negatives sont les deux moities du grief d'Egan : le
    fichier ne porte NI le nom du scan, NI l'identite de chaine derivee.
    """
    from mixed_media_utility.io import project_layout

    projet = tmp_path / "projet"
    project_layout.ensure_project_layout(projet)
    consigne = scan_calibrate.calibrer_la_chaine(projet, SCAN_REEL, dpi=300)

    assert consigne.etiquette == LIBELLE_ATTENDU
    if LIBELLE_ATTENDU == LIBELLE_DU_SCAN_REEL:
        # Le litteral n'a de sens que pour LA planche mesuree ; sous
        # `MMU_SCAN_REEL`, les quatre assertions suivantes suffisent et
        # celle-ci n'aurait rien a comparer.
        assert Path(consigne.profile_path).name == PROFIL_DU_SCAN_REEL
    assert SCAN_REEL.stem not in Path(consigne.profile_path).name, (
        "le profil porte encore le nom du fichier scanne")
    assert Path(consigne.profile_path).stem != consigne.chain_id, (
        "le profil est retombe sur l'identite derivee alors que la feuille "
        "portait un nom")
    # **Et le document persiste le libelle**, pas seulement le nom du fichier :
    # c'est lui que `E3-5` et le pied du menu Scan relisent.
    assert consigne.document["label"] == LIBELLE_ATTENDU
