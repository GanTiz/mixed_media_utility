"""L'encodeur QR est `segno`, et OpenCV n'est plus que detecteur (`EPIC11-ARB-250`/`-251`).

**Ce que ce banc tient, et pourquoi aucun autre ne le tenait.**

La ligne 4.10/4.11 d'`opencv-contrib-python` encode un symbole MALFORME au-dela
de la version 7 -- illisible par tout lecteur, y compris `zxing-cpp` et les
versions ulterieures d'OpenCV. Le papier est perdu au moment de l'impression,
pas au moment du scan (`mesure-2026-09-06-plancher-opencv-et-rendu-qr.md`). La
sortie retenue n'est pas un plancher de version -- `4.10.0.84` est la derniere
roue `macosx_12_0_x86_64`, donc tout plancher sortait la machine de reference --
mais un changement d'ENCODEUR : `segno`, roue `py3-none-any`.

Trois choses se mesurent ici, et elles ne valent que reunies :

1. **la geometrie ne bouge pas d'un module.** C'est la condition de surete de
   la bascule. Le cote du raster natif gouverne `pixels_per_module`, donc
   `required_print_size_mm`, donc l'emprise du QR sur la planche, donc les
   gabarits et les seuils de calibration. `segno` rend sa matrice NUE ; le
   raster d'OpenCV portait une marge de 2 modules. Le nappage de
   `MARGE_NATIVE_MODULES` est ce qui rend les deux interchangeables, et ce banc
   le mesure **cote a cote contre l'encodeur d'OpenCV**, jamais contre une
   table de nombres recopiee ;
2. **la table de correspondance ECC ne s'inverse pas.** Le vocabulaire du depot
   est l'entier d'OpenCV (0=L, 1=M, 2=Q, 3=H), celui de `segno` est une lettre.
   Une conversion de quatre entrees est exactement le genre d'endroit ou une
   permutation L/H passe des mois : elle ne change ni la signature, ni le
   cardinal, ni le fait que « ca decode ». Elle est donc mesuree dans QUATRE
   sens, dont un qui interroge le symbole PRODUIT plutot que la table ;
3. **la garde d'aller-retour part vraiment** (`EPIC11-ARB-251`). Un banc qui se
   contenterait de constater l'absence d'avertissement sur le chemin nominal ne
   mesurerait rien du tout : il resterait vert avec la garde entierement
   desarmee. La garde se mesure donc par un encodeur GREFFE qui rend un raster
   faux -- greffe en memoire, jamais une mutation sur disque.

**Ce que ce banc NE mesure pas, dit plutot que tu.** Il ne mesure pas le defaut
de la ligne 4.10 lui-meme : ce conteneur porte OpenCV 5.0.0, ou l'encodeur
d'OpenCV est sain. La comparaison de cote ci-dessous tient sous les deux lignes
(les DIMENSIONS de 4.10 sont justes, c'est le CONTENU des modules qui ne l'est
pas -- 1 761 modules sur 4 761 different d'un symbole conforme). Le
contre-controle sous 4.10 se fait hors banc, en venv dedie ; son verdict est au
compte rendu du lot.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest import mock

import cv2
import numpy as np
import pytest
import segno

RACINE_DEPOT = Path(__file__).resolve().parents[2]
if str(RACINE_DEPOT / "src") not in sys.path:
    sys.path.insert(0, str(RACINE_DEPOT / "src"))

from mixed_media_utility import qr_codes
from mixed_media_utility.io import payload as payload_io

SOURCES = RACINE_DEPOT / "src" / "mixed_media_utility"
RECHERCHE = RACINE_DEPOT / "scripts" / "research"

#: Le nom du journal du module, pour que `caplog` ecoute CELUI-LA et pas la
#: racine : un banc qui ecoute la racine se croit vert le jour ou
#: l'avertissement part d'ailleurs.
JOURNAL = "mixed_media_utility.qr_codes"

#: Les huit tailles de reference de la mesure du 2026-09-06, avec le cote
#: attendu au niveau ECC M. **Les cotes sont ecrits ici pour que le banc dise ce
#: qu'il attend**, mais ils ne sont pas la seule reference : chaque cas est aussi
#: compare a l'encodeur d'OpenCV, mesure a l'execution. Un lecteur voit donc a la
#: fois la valeur attendue et la source qui la valide.
TAILLES_DE_REFERENCE = {
    150: 53,
    170: 57,
    181: 61,
    256: 69,
    320: 73,
    380: 81,
    452: 89,
    560: 93,
}

#: Les quatre niveaux, du plus faible au plus fort. Les DEUX bords comptent
#: (regle des fabriques, point 4) : une permutation qui echangerait L et H est
#: le mode de panne le plus probable de la table, et il ne se voit qu'en jouant
#: la tete ET la queue.
NIVEAUX = (
    qr_codes.CORRECTION_LEVEL_L,
    qr_codes.CORRECTION_LEVEL_M,
    qr_codes.CORRECTION_LEVEL_Q,
    qr_codes.CORRECTION_LEVEL_H,
)

#: Correspondance de REFERENCE, ecrite a la main depuis la documentation
#: d'OpenCV, et confrontee aux constantes reelles par le premier test. Elle est
#: volontairement un second exemplaire de la table du module : deux exemplaires
#: qui se contredisent font rougir, un exemplaire unique ne se mesure pas.
LETTRES_ATTENDUES = {0: "l", 1: "m", 2: "q", 3: "h"}


def charge_utile(taille: int) -> str:
    """Rend une charge de `taille` octets exactement, sans etat ni horloge.

    Volontairement en MINUSCULES et ponctuee : le mode alphanumerique du QR ne
    couvre que `0-9 A-Z $%*+-./:` et l'espace, donc une charge en majuscules
    s'encoderait dans un mode plus dense et changerait le cote. Les charges
    reelles du produit sont du JSON, donc toujours en mode octet.
    """
    motif = "mmu:v1;lot=m-milieu_25;page=i;slot=%04d;gamut=gamut-map-none-1;"
    return "".join(motif % i for i in range(1, 60))[:taille]


def cote_par_opencv(texte: str, niveau: int) -> int:
    """Cote du raster que l'encodeur d'OpenCV rendait, mesure a l'execution.

    C'est la reference contre laquelle la bascule doit etre neutre. Elle est
    appelee ICI, dans un banc, et nulle part dans `src/` -- voir la frontiere
    negative en fin de fichier.
    """
    parametres = cv2.QRCodeEncoder_Params()
    parametres.correction_level = niveau
    return int(cv2.QRCodeEncoder_create(parametres).encode(texte).shape[0])


#: Emplacement des 15 bits de l'information de format, copie du coin superieur
#: gauche, dans l'ordre du plus significatif au moins significatif (ISO/IEC
#: 18004, 8.9). La colonne 6 et la ligne 6 -- les motifs de synchronisation --
#: sont sautees, ce qui est la seule subtilite de ce releve.
_POSITIONS_DU_FORMAT = (
    (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
    (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8),
)

#: Masque applique aux 15 bits de format par la norme, pour qu'un symbole ne
#: puisse jamais porter un format tout blanc ou tout noir.
_MASQUE_DU_FORMAT = 0x5412

#: Les deux bits de tete, une fois le masque retire, donnent le niveau ECC.
#: L'ordre n'est PAS L/M/Q/H : c'est 01/00/11/10, et le recopier de memoire est
#: le genre d'erreur que ce releve existe pour attraper.
_INDICATEUR_ECC = {0b01: "L", 0b00: "M", 0b11: "Q", 0b10: "H"}


def niveau_ecc_du_raster(natif: np.ndarray) -> str:
    """Lire le niveau ECC **dans le symbole lui-meme**, et non dans la table.

    C'est la mesure la plus forte du lot sur la correspondance ECC : elle
    n'interroge ni `segno`, ni la table du module, ni l'argument passe -- elle
    lit les bits que le symbole IMPRIME porte. Une table inversee, un
    `boost_error` reste arme, ou un appel qui contourne la table s'y voient
    tous les trois.

    Le releve est valide contre un encodeur INDEPENDANT (celui d'OpenCV) par
    `test_le_releve_du_format_est_valide_contre_un_encodeur_INDEPENDANT` : sans
    ce controle, un extracteur faux rendrait un banc faux et rassurant.
    """
    marge = qr_codes.MARGE_NATIVE_MODULES
    symbole = natif[marge:natif.shape[0] - marge, marge:natif.shape[1] - marge]
    sombre = (symbole == 0).astype(int)
    valeur = 0
    for ligne, colonne in _POSITIONS_DU_FORMAT:
        valeur = (valeur << 1) | int(sombre[ligne, colonne])
    return _INDICATEUR_ECC[((valeur ^ _MASQUE_DU_FORMAT) >> 13) & 0b11]


# --- 1. La geometrie ne bouge pas ------------------------------------------


@pytest.mark.parametrize("octets,cote_attendu", sorted(TAILLES_DE_REFERENCE.items()))
def test_le_cote_est_IDENTIQUE_a_celui_d_OpenCV_aux_huit_tailles(
    octets: int, cote_attendu: int
) -> None:
    """**La condition de surete du lot** : un module d'ecart casse tout le produit.

    Le cote gouverne `pixels_per_module`, donc `required_print_size_mm`, donc
    l'emprise sur la planche, donc les gabarits et les seuils de calibration.
    Retirer le nappage de `MARGE_NATIVE_MODULES` fait perdre 4 modules et rend
    ce test rouge aux huit tailles -- verifie par greffe avant de le declarer
    vert.
    """
    texte = charge_utile(octets)
    assert qr_codes.payload_size_bytes(texte) == octets

    natif = qr_codes.encode_qr_image(texte)
    assert natif.shape == (cote_attendu, cote_attendu), (
        f"{octets} octets: cote {natif.shape[0]} au lieu de {cote_attendu}. "
        "La geometrie d'impression du produit entier depend de ce nombre."
    )
    assert int(natif.shape[0]) == cote_par_opencv(texte, qr_codes.DEFAULT_CORRECTION_LEVEL), (
        "segno et l'encodeur d'OpenCV ne rendent plus le meme cote: la bascule "
        "d'encodeur cesse d'etre neutre sur la geometrie d'impression."
    )


@pytest.mark.parametrize(
    "octets",
    [
        pytest.param(1, id="borne-basse-un-octet"),
        pytest.param(2, id="deux-octets"),
        pytest.param(payload_io.NOMINAL_BUDGET_BYTES, id="budget-nominal"),
        pytest.param(payload_io.ALERT_BUDGET_BYTES, id="borne-haute-plafond-dur"),
    ],
)
def test_le_cote_est_IDENTIQUE_a_celui_d_OpenCV_AUX_DEUX_BORDS(octets: int) -> None:
    """Les bords de la plage, la ou la table de reference ne va pas.

    **La borne basse n'est pas decorative** : sans `micro=False`, `segno` rend
    un Micro QR pour 1 ou 2 octets -- `M2`/`M3`, cote 17 ou 19 -- la ou
    l'encodeur d'OpenCV rendait un symbole de version 1 (cote 25). C'est une
    rupture de geometrie que le seul balayage des tailles de production, toutes
    au-dessus de 150 octets, ne verrait jamais.
    """
    texte = charge_utile(octets) if octets > 2 else "ab"[:octets]
    natif = qr_codes.encode_qr_image(texte)
    assert int(natif.shape[0]) == cote_par_opencv(texte, qr_codes.DEFAULT_CORRECTION_LEVEL)


def test_l_egalite_des_cotes_tient_sur_TOUTE_la_plage_et_aux_QUATRE_niveaux() -> None:
    """Le balayage, parce que huit points ne sont pas une plage.

    Il fait varier les DEUX axes -- taille et niveau ECC -- plutot qu'un seul :
    une garde qui ne ferait varier aucun de ses drapeaux ne mesurerait qu'un
    chemin, et le niveau ECC est precisement le drapeau que la bascule traduit.
    """
    ecarts = []
    for niveau in NIVEAUX:
        for octets in range(8, payload_io.ALERT_BUDGET_BYTES + 1, 40):
            texte = charge_utile(octets)
            obtenu = int(qr_codes.encode_qr_image(texte, correction_level=niveau).shape[0])
            attendu = cote_par_opencv(texte, niveau)
            if obtenu != attendu:
                ecarts.append((niveau, octets, obtenu, attendu))
    assert not ecarts, (
        f"{len(ecarts)} ecarts de cote entre segno et l'encodeur d'OpenCV: "
        f"{ecarts[:5]}. La bascule cesse d'etre neutre sur la geometrie."
    )


@pytest.mark.parametrize(
    "bord,decoupe",
    [
        pytest.param("haut", lambda a, n: a[:n, :], id="bord-haut"),
        pytest.param("bas", lambda a, n: a[-n:, :], id="bord-bas"),
        pytest.param("gauche", lambda a, n: a[:, :n], id="bord-gauche"),
        pytest.param("droite", lambda a, n: a[:, -n:], id="bord-droite"),
    ],
)
def test_la_marge_native_vaut_DEUX_modules_sur_CHACUN_des_quatre_bords(
    bord: str, decoupe
) -> None:
    """La marge se mesure bord par bord, jamais globalement.

    Un nappage asymetrique -- `np.pad` mal parametre, un `((2, 0), (2, 0))` au
    lieu d'un `2` -- rendrait un raster NON CARRE ou decale, et un test qui ne
    regarderait que le cote total ou qu'un seul bord le laisserait passer. Les
    quatre bords sont donc quatre cibles, tete et queue comprises sur les deux
    axes.
    """
    natif = qr_codes.encode_qr_image(charge_utile(256))
    marge = qr_codes.MARGE_NATIVE_MODULES

    assert (decoupe(natif, marge) == 255).all(), (
        f"bord {bord}: les {marge} premiers modules ne sont pas tous blancs"
    )
    # Et la bande immediatement suivante n'est PAS blanche : sinon un nappage de
    # 4 modules -- ou de 8 -- passerait ce test aussi bien qu'un nappage de 2.
    assert not (decoupe(natif, marge + 1) == 255).all(), (
        f"bord {bord}: la marge depasse {marge} modules. Le cote du raster ne "
        "serait plus celui qu'attend toute la geometrie d'impression."
    )


def test_le_raster_natif_est_un_uint8_carre_en_0_255_comme_avant() -> None:
    """Le contrat de FORME du raster, que tous les appelants supposent.

    `render_for_print` refuse un raster non carre, `pdf_render` compare
    `shape[0]` au plan, et les detecteurs veulent du `uint8` monocanal. Une
    conversion 0/255 inversee rendrait une video inverse que rien ne lit.
    """
    natif = qr_codes.encode_qr_image(charge_utile(256))
    assert natif.dtype == np.uint8
    assert natif.ndim == 2 and natif.shape[0] == natif.shape[1]
    assert set(np.unique(natif).tolist()) == {0, 255}
    # Le sens de la conversion : les coins du raster sont dans la marge, donc
    # BLANCS. Une inversion 0/255 les rendrait noirs, et le symbole illisible.
    assert natif[0, 0] == 255 and natif[-1, -1] == 255
    # Et il reste du noir : un raster entierement blanc passerait la ligne
    # ci-dessus sans porter le moindre module.
    assert (natif == 0).any()


# --- 2. La table de correspondance ECC, dans quatre sens --------------------


def test_les_entiers_du_depot_sont_bien_ceux_d_OpenCV() -> None:
    """Sens 1 : la constante du module contre la constante reelle d'OpenCV.

    `DEFAULT_CORRECTION_LEVEL` etait lu de `cv2.QRCodeEncoder_CORRECT_LEVEL_M`.
    Il est desormais ecrit en clair -- l'encodeur d'OpenCV ne doit plus etre
    nomme dans `src/` -- donc ce qui etait une DEPENDANCE devient une MESURE,
    et c'est ce test qui la porte.
    """
    assert qr_codes.CORRECTION_LEVEL_L == cv2.QRCodeEncoder_CORRECT_LEVEL_L == 0
    assert qr_codes.CORRECTION_LEVEL_M == cv2.QRCodeEncoder_CORRECT_LEVEL_M == 1
    assert qr_codes.CORRECTION_LEVEL_Q == cv2.QRCodeEncoder_CORRECT_LEVEL_Q == 2
    assert qr_codes.CORRECTION_LEVEL_H == cv2.QRCodeEncoder_CORRECT_LEVEL_H == 3
    assert qr_codes.DEFAULT_CORRECTION_LEVEL == cv2.QRCodeEncoder_CORRECT_LEVEL_M
    assert qr_codes.CORRECTION_LEVEL_MIN == 0 and qr_codes.CORRECTION_LEVEL_MAX == 3


def test_la_table_ECC_est_EXHAUSTIVE_et_sans_doublon() -> None:
    """Sens 2 : la table couvre exactement la plage, une lettre par niveau.

    Une table a trois entrees leverait un `KeyError` sur le quatrieme niveau,
    et une table dont deux niveaux partagent la meme lettre encoderait deux
    niveaux differents a l'identique -- sans qu'aucun test de decodage ne s'en
    apercoive, puisque les deux se relisent.
    """
    table = qr_codes._NIVEAU_ECC_VERS_SEGNO
    assert set(table) == set(range(qr_codes.CORRECTION_LEVEL_MIN,
                                   qr_codes.CORRECTION_LEVEL_MAX + 1))
    assert len(set(table.values())) == len(table) == 4
    assert table == LETTRES_ATTENDUES


@pytest.mark.parametrize("niveau", NIVEAUX)
def test_le_symbole_PRODUIT_porte_le_niveau_demande(niveau: int) -> None:
    """Sens 3, le plus fort : on interroge le SYMBOLE, pas la table.

    C'est le seul sens qui attrape une table juste employee a l'envers, ou un
    `boost_error` reste a `True`. `segno` PUBLIE le niveau du symbole qu'il a
    produit ; on le compare a celui qui a ete demande, plutot que de deduire.

    La garde fait varier son drapeau sur les QUATRE valeurs -- tete et queue
    comprises --, parce qu'une permutation L/H ne se voit pas au milieu.
    """
    texte = charge_utile(256)
    attendue = LETTRES_ATTENDUES[niveau].upper()

    with mock.patch.object(segno, "make", wraps=segno.make) as espion:
        qr_codes.encode_qr_image(texte, correction_level=niveau)

    assert espion.call_count == 1
    _, nommes = espion.call_args
    assert nommes["error"] == LETTRES_ATTENDUES[niveau], (
        f"niveau {niveau} traduit en {nommes['error']!r} au lieu de "
        f"{LETTRES_ATTENDUES[niveau]!r}"
    )
    # Et le symbole reellement produit le porte : la table peut etre juste et
    # l'appel la contourner.
    symbole = segno.make(texte, error=nommes["error"], boost_error=False, micro=False)
    assert symbole.error == attendue


@pytest.mark.parametrize("niveau", NIVEAUX)
def test_le_releve_du_format_est_valide_contre_un_encodeur_INDEPENDANT(
    niveau: int,
) -> None:
    """Le releve se mesure avant de servir, sinon il mesure n'importe quoi.

    L'encodeur d'OpenCV est ici un TEMOIN independant : il n'a rien de commun
    avec `segno` sauf la norme. Si les deux rasters rendent le meme niveau au
    meme rang, le releve lit bien ce qu'il pretend lire -- et le controle est
    non circulaire, ce qu'une comparaison de `segno` a lui-meme ne serait pas.
    """
    texte = charge_utile(256)
    parametres = cv2.QRCodeEncoder_Params()
    parametres.correction_level = niveau
    temoin = cv2.QRCodeEncoder_create(parametres).encode(texte)

    attendu = LETTRES_ATTENDUES[niveau].upper()
    assert niveau_ecc_du_raster(temoin) == attendu
    assert niveau_ecc_du_raster(qr_codes.encode_qr_image(texte, correction_level=niveau)) \
        == attendu


@pytest.mark.parametrize("niveau", NIVEAUX)
def test_le_RASTER_PRODUIT_porte_le_niveau_demande_dans_ses_bits_de_format(
    niveau: int,
) -> None:
    """Le sens qui ne se contourne pas : on lit le symbole, pas l'appel.

    Un espion sur `segno.make` mesure ce qu'on DEMANDE ; ce test mesure ce
    qu'on OBTIENT. La difference n'est pas theorique : une greffe qui force
    `boost_error=True` dans `segno.make` survit a l'espion -- il la remplace --
    et meurt ici, parce que le symbole produit ne porte alors plus le niveau
    demande.

    Les quatre niveaux sont joues, tete et queue comprises : c'est le seul
    balayage qui distingue une table juste d'une table permutee.
    """
    natif = qr_codes.encode_qr_image(charge_utile(256), correction_level=niveau)
    assert niveau_ecc_du_raster(natif) == LETTRES_ATTENDUES[niveau].upper()


def test_le_MODE_reste_automatique_comme_chez_l_encodeur_d_OpenCV() -> None:
    """Forcer le mode octet gonflerait le symbole, mesure.

    L'encodeur d'OpenCV choisit le mode le plus dense que la charge permet ;
    `segno` aussi, tant qu'on ne lui impose rien. Une charge NUMERIQUE est le
    seul cas ou les deux comportements se separent visiblement -- et les
    charges de production etant du JSON, donc toujours en mode octet, aucun
    autre test du depot ne verrait la difference.

    Mesure : 120 chiffres rendent 37 modules de cote en mode automatique et 49
    en mode octet force, soit trois versions de symbole d'ecart.
    """
    for texte in ("1234567890" * 12, "ABCDEF1234 $%*+-./:" * 6):
        natif = qr_codes.encode_qr_image(texte)
        assert int(natif.shape[0]) == cote_par_opencv(
            texte, qr_codes.DEFAULT_CORRECTION_LEVEL
        ), (
            f"charge {texte[:12]!r}...: le mode d'encodage a cesse de suivre "
            "celui de l'encodeur d'OpenCV, donc le cote du symbole a bouge"
        )


def test_boost_error_reste_DESARME_la_ou_segno_remonterait_le_niveau() -> None:
    """Sens 4 : le reglage qui changerait le symbole sans qu'on le demande.

    `segno` remonte le niveau ECC de lui-meme quand la place restante le
    permet. Le niveau demande vient d'un `patch_preset_id` versionne : le
    remonter en silence, c'est produire un symbole que le plan ne decrit pas.

    Le cas est choisi pour que le boost ait LIEU s'il n'est pas desarme -- une
    charge courte au niveau L, ou il reste beaucoup de place. Un cas ou le
    boost n'aurait rien a faire mesurerait le neant.
    """
    texte = charge_utile(8)
    boostee = segno.make(texte, error="l", boost_error=True, micro=False)
    assert boostee.error != "L", (
        "le cas choisi ne declenche aucun boost: il ne mesure donc rien. En "
        "choisir un plus court, ou a niveau plus bas."
    )

    with mock.patch.object(segno, "make", wraps=segno.make) as espion:
        natif = qr_codes.encode_qr_image(texte, correction_level=qr_codes.CORRECTION_LEVEL_L)
    _, nommes = espion.call_args
    assert nommes["boost_error"] is False
    assert nommes["micro"] is False
    # Et la consequence observable, LUE DANS LE SYMBOLE : c'est elle qui compte,
    # parce que l'espion ci-dessus se laisse contourner par une greffe posee sur
    # `segno.make` -- mesure, mutant `M10`, SURVIVANT tant que cette ligne
    # n'existait pas.
    assert niveau_ecc_du_raster(natif) == "L", (
        "le symbole produit ne porte plus le niveau demande: boost_error est "
        "arme quelque part"
    )
    assert niveau_ecc_du_raster(qr_codes._raster_natif(boostee)) == boostee.error, (
        "le releve du format ne lit pas le symbole boste: le temoin de ce test "
        "ne temoigne de rien"
    )
    # Et le cote reste celui de l'encodeur d'OpenCV, qui ne boostait pas non plus.
    assert int(natif.shape[0]) == cote_par_opencv(texte, qr_codes.CORRECTION_LEVEL_L)


@pytest.mark.parametrize("niveau", NIVEAUX)
def test_chaque_niveau_fait_son_ALLER_RETOUR_a_la_geometrie_de_production(
    niveau: int,
) -> None:
    """Les quatre niveaux se relisent vraiment, pas seulement le defaut.

    Une garde qui ne joue qu'`ECC M` mesure un quart du produit et l'annonce
    verte.
    """
    texte = charge_utile(256)
    natif = qr_codes.encode_qr_image(texte, correction_level=niveau)
    rendu = qr_codes.render_for_print(
        natif, qr_codes.QR_PRINT_SIZE_TARGET_MM, qr_codes.QR_MIN_SCAN_DPI
    )
    resultat = qr_codes.decode_qr_image_resilient(rendu)
    assert resultat.text == texte, (
        f"niveau ECC {niveau}: statut={resultat.status}. "
        f"Encodeur segno {segno.__version__}, decodeur OpenCV {cv2.__version__}."
    )


def test_un_payload_trop_gros_pour_son_niveau_reste_un_QRPayloadTooLarge() -> None:
    """Le contrat d'erreur ne change pas d'exception avec l'encodeur.

    `segno` leve `segno.DataOverflowError` la ou l'encodeur d'OpenCV levait
    `cv2.error`. Les appelants sont ecrits contre `QRPayloadTooLarge`, et le
    message doit continuer de nommer les octets ET le niveau -- ce sont les
    deux seules grandeurs sur lesquelles un operateur peut agir.

    Le plafond dur d'`io.payload` interceptant tout ce que `segno` refuserait
    reellement, la conversion se mesure par une greffe : sans elle, ce chemin
    serait du code que rien ne joue.
    """
    texte = charge_utile(256)
    with mock.patch.object(
        segno, "make", side_effect=segno.DataOverflowError("capacite depassee")
    ):
        with pytest.raises(qr_codes.QRPayloadTooLarge) as leve:
            qr_codes.encode_qr_image(texte, correction_level=qr_codes.CORRECTION_LEVEL_H)
    message = str(leve.value)
    assert "256" in message and str(qr_codes.CORRECTION_LEVEL_H) in message


# --- 3. La garde d'aller-retour (`EPIC11-ARB-251`) --------------------------


def test_le_chemin_NOMINAL_n_avertit_pas(caplog) -> None:
    """Prealable, et rien de plus : une garde qui crie au loup est desarmee vite.

    Ce test seul ne mesure RIEN de la garde -- il reste vert avec la garde
    entierement retiree. C'est le test suivant qui la mesure ; celui-ci
    n'existe que pour tenir l'absence de fausse alerte, mesuree nulle sur 120
    symboles (quatre niveaux x 30 tailles).
    """
    with caplog.at_level(logging.WARNING, logger=JOURNAL):
        for niveau in NIVEAUX:
            qr_codes.encode_qr_image(charge_utile(452), correction_level=niveau)
    assert [e for e in caplog.records if e.name == JOURNAL] == []


def test_la_garde_AVERTIT_quand_le_symbole_ne_se_relit_pas(caplog) -> None:
    """**Le mutant vivant qui mesure la garde**, greffe en memoire.

    On greffe un encodeur qui rend un raster FAUX -- du bruit deterministe a la
    bonne forme -- et on verifie que l'avertissement part. Sans cette greffe, la
    garde pourrait etre entierement absente sans qu'un seul banc rougisse.

    Le raster greffe garde la forme d'un vrai raster (carre, uint8, 0/255,
    marge blanche) : c'est le CONTENU qui est faux, exactement comme le symbole
    malforme de la ligne 4.10 -- memes dimensions, 37 % des modules differents.
    """
    texte = charge_utile(256)
    cote = int(qr_codes.encode_qr_image(texte).shape[0])

    generateur = np.random.default_rng(20260906)
    damier = np.where(
        generateur.random((cote - 4, cote - 4)) < 0.5, 0, 255
    ).astype(np.uint8)
    faux = np.pad(damier, qr_codes.MARGE_NATIVE_MODULES, constant_values=255)

    with mock.patch.object(qr_codes, "_raster_natif", return_value=faux):
        with caplog.at_level(logging.WARNING, logger=JOURNAL):
            rendu = qr_codes.encode_qr_image(texte)

    # 1. Elle n'a pas bloque : la sortie est rendue quand meme (EPIC11-ARB-89).
    assert rendu is faux

    # 2. Elle a averti, une fois, au bon niveau.
    avertissements = [e for e in caplog.records if e.name == JOURNAL]
    assert len(avertissements) == 1, (
        "la garde d'aller-retour n'a pas averti sur un symbole illisible: elle "
        "est desarmee (EPIC11-ARB-251)"
    )
    assert avertissements[0].levelno == logging.WARNING

    # 3. Le message porte ce qui rend le defaut diagnosticable EN UNE LECTURE:
    #    la version d'OpenCV -- le decodeur -- et le fait que l'encodeur, lui,
    #    est segno. Sans les deux noms, un futur lecteur cherche le defaut dans
    #    le mauvais des deux roles, ce qui a deja coute une nuit a ce depot.
    message = avertissements[0].getMessage()
    assert cv2.__version__ in message, "l'avertissement ne nomme pas la version d'OpenCV"
    assert "segno" in message and segno.__version__ in message, (
        "l'avertissement ne nomme pas l'encodeur"
    )


def test_la_garde_avertit_AUSSI_quand_la_relecture_elle_meme_echoue(caplog) -> None:
    """L'autre chemin de la garde, et il est symetrique du precedent.

    Un raster mal FORME -- pas seulement mal rempli -- fait lever le
    redimensionnement ou la normalisation du decodeur. Une garde qui laisserait
    filer cette exception ferait echouer `encode_qr_image` la ou la bascule
    promet de ne rien casser : elle transformerait un avertissement en panne.
    """
    faux = np.zeros((0, 0), dtype=np.uint8)
    with mock.patch.object(qr_codes, "_raster_natif", return_value=faux):
        with caplog.at_level(logging.WARNING, logger=JOURNAL):
            rendu = qr_codes.encode_qr_image(charge_utile(256))

    assert rendu is faux, "la garde a fait echouer son appelant au lieu d'avertir"
    avertissements = [e for e in caplog.records if e.name == JOURNAL]
    assert len(avertissements) == 1
    assert cv2.__version__ in avertissements[0].getMessage()


def test_la_garde_REND_son_verdict_en_plus_de_le_journaliser() -> None:
    """Le verdict est une valeur, pas seulement une ligne de journal.

    `encode_qr_image` ne s'en sert pas aujourd'hui -- elle n'a rien a en faire,
    la garde ne bloque pas --, mais un appelant futur (une commande qui
    voudrait compter les planches douteuses, une TUI qui voudrait les
    signaler) en aura besoin, et un booleen qui rend toujours `True` est un
    contrat muet. Mutant `M17`, SURVIVANT tant que ce test n'existait pas :
    la garde avertissait correctement ET rendait `True`, sans qu'un seul banc
    ne s'en apercoive.
    """
    texte = charge_utile(256)
    natif = qr_codes.encode_qr_image(texte)
    assert qr_codes._avertir_si_le_symbole_ne_se_relit_pas(
        natif, texte, qr_codes.DEFAULT_CORRECTION_LEVEL
    ) is True

    faux = np.full(natif.shape, 255, dtype=np.uint8)
    faux[10:20, 10:20] = 0
    assert qr_codes._avertir_si_le_symbole_ne_se_relit_pas(
        faux, texte, qr_codes.DEFAULT_CORRECTION_LEVEL
    ) is False
    # Et le troisieme chemin, celui ou la relecture leve : il rend `False` lui
    # aussi, jamais une exception.
    assert qr_codes._avertir_si_le_symbole_ne_se_relit_pas(
        np.zeros((0, 0), dtype=np.uint8), texte, qr_codes.DEFAULT_CORRECTION_LEVEL
    ) is False


def test_la_garde_passe_par_le_chemin_de_lecture_de_la_PRODUCTION() -> None:
    """Elle pose la bonne question, et ce n'est pas « un detecteur y arrive-t-il ».

    La relecture passe par `decode_qr_image_resilient` -- detecteur par defaut
    ET ses replis --, c'est-a-dire par ce que le produit fait vraiment au scan.
    Une relecture par un appel nu au detecteur mesurerait un chemin que la
    production n'emprunte pas, et rendrait des fausses alertes : mesure, la
    lecture directe en rend 1 sur 120 la ou le chemin resilient en rend 0.
    """
    with mock.patch.object(
        qr_codes, "decode_qr_image_resilient", wraps=qr_codes.decode_qr_image_resilient
    ) as espion:
        qr_codes.encode_qr_image(charge_utile(256))
    assert espion.call_count == 1, (
        "la relecture de controle n'emprunte pas le chemin de lecture de la "
        "production"
    )
    (image,), _ = espion.call_args
    # Le regime MESURE, ecrit en clair : zone de silence de 4 modules,
    # agrandissement entier x4. Les constantes du module ne sont deliberement
    # PAS relues ici -- une assertion qui les relit est tautologique et reste
    # verte quoi qu'on leur fasse (mutant `M19`, SURVIVANT tant qu'elle
    # l'etait). Ces deux nombres viennent de la mesure du lot : 0 fausse alerte
    # sur 120 symboles a x4, contre 1 pour la lecture directe.
    cote_natif = int(qr_codes.encode_qr_image(charge_utile(256)).shape[0])
    attendu = (cote_natif + 2 * 4) * 4
    assert image.shape == (attendu, attendu), (
        f"regime de relecture change: {image.shape} au lieu de "
        f"{(attendu, attendu)} (cote natif {cote_natif}, silence 4, facteur 4)"
    )


# --- 4. La frontiere negative -----------------------------------------------


def test_AUCUN_chemin_de_production_n_appelle_plus_l_encodeur_d_OpenCV() -> None:
    """**Le seul type de banc qui verrait revenir l'encodeur d'OpenCV dans `src/`.**

    Aucun test positif ne l'attraperait : un `QRCodeEncoder_create` reintroduit
    a cote de `segno` produirait des symboles parfaitement decodables sur ce
    conteneur (OpenCV 5.0), et casserait silencieusement toute machine en
    4.10/4.11 -- c'est-a-dire exactement le defaut qu'`EPIC11-ARB-250` ferme.

    La frontiere porte sur le jeton `QRCodeEncoder` **ou qu'il soit** dans
    `src/`, y compris en commentaire : une prose qui le nomme est un appel en
    puissance, et une frontiere qui distingue les deux se contourne par
    accident. Le module dit « l'encodeur d'OpenCV » en toutes lettres a la
    place.

    Elle ne porte PAS sur `scripts/research/`, et ce n'est pas un oubli : ces
    deux bancs de recherche COMPARENT les encodeurs, donc ils doivent appeler
    celui d'OpenCV. C'est mesure ci-dessous plutot que suppose -- une exemption
    dont on ne verifie pas qu'elle sert encore devient un trou.
    """
    fautifs = []
    for chemin in sorted(SOURCES.rglob("*.py")):
        if "QRCodeEncoder" in chemin.read_text(encoding="utf-8"):
            fautifs.append(str(chemin.relative_to(RACINE_DEPOT)))
    assert not fautifs, (
        f"l'encodeur d'OpenCV est de retour dans src/: {fautifs}. Sa ligne "
        "4.10/4.11 rend un symbole malforme au-dela de la version 7, et le "
        "papier est perdu a l'impression (EPIC11-ARB-250)."
    )


def test_l_exemption_des_bancs_de_recherche_SERT_encore() -> None:
    """L'exemption se mesure, sinon elle se perime en trou.

    Les deux scripts nommes comparent les encodeurs entre eux : leur retirer
    l'appel a celui d'OpenCV les viderait de leur objet. S'ils cessaient un jour
    de l'appeler, l'exemption n'aurait plus de raison d'etre et devrait
    disparaitre de la prose ci-dessus -- ce test est ce qui le dira.
    """
    attendus = {
        "qr_encoder_conformance_bench.py",
        "qr_feasibility_experiment.py",
    }
    trouves = {
        chemin.name
        for chemin in RECHERCHE.glob("*.py")
        if "QRCodeEncoder" in chemin.read_text(encoding="utf-8")
    }
    assert trouves == attendus, (
        f"les bancs de recherche qui appellent l'encodeur d'OpenCV ont change: "
        f"{sorted(trouves)} au lieu de {sorted(attendus)}. L'exemption de la "
        "frontiere negative est a relire."
    )


def test_segno_est_le_SEUL_encodeur_de_src() -> None:
    """Le versant positif de la frontiere : quelqu'un encode encore.

    Une frontiere purement negative reste verte si plus rien n'encode du tout
    -- par exemple si `encode_qr_image` etait vide de son corps. Le versant
    positif est donc mesure, et il l'est sur le SEUL fichier qui a le droit
    d'importer l'encodeur.
    """
    importateurs = {
        chemin.name
        for chemin in SOURCES.rglob("*.py")
        if "import segno" in chemin.read_text(encoding="utf-8")
    }
    assert importateurs == {"qr_codes.py"}, (
        f"l'encodage QR doit rester dans qr_codes.py, trouve: {sorted(importateurs)}"
    )


# --- 5. Le terrain, confronte a la synthese ---------------------------------


def test_les_RASTERS_REELS_ne_passent_pas_par_l_encodeur_et_gardent_leur_verdict() -> None:
    """« Une fixture de synthese peut fabriquer une panne que le terrain n'a PAS ».

    Les quatre captures de `tests/fixtures/qr_300dpi/` sont des planches
    imprimees puis scannees : elles n'ont **jamais** traverse `encode_qr_image`.
    Leurs verdicts doivent donc etre rigoureusement INCHANGES par la bascule
    d'encodeur, et un ecart signalerait que le lot a touche au decodage --
    c'est-a-dire deborde de son perimetre.

    **Les verdicts sont mesures ici, sur les images ENTIERES et par les deux
    chemins de lecture du produit** -- pas recopies d'un compte rendu. Ceux de
    `mesure-2026-09-06-plancher-opencv-et-rendu-qr.md` (« heteroclite : rien,
    main : rien ») ont ete pris sur un chemin plus etroit : sur l'image entiere,
    le detecteur par defaut lit deja `heteroclite`, et le chemin resilient lit
    les QUATRE. C'est la lecon de `decode_qr_image_resilient` elle-meme -- le
    verdict d'une capture depend de la marge de contexte gardee autour du
    symbole --, et c'est pourquoi la reference vit ici, dans un banc rejoue, et
    non dans une prose.

    `main` est gardee alors qu'elle echoue au detecteur par defaut : c'est elle
    qui rend ce banc capable de voir une AMELIORATION inattendue du decodage
    autant qu'une regression.
    """
    dossier = RACINE_DEPOT / "tests" / "fixtures" / "qr_300dpi"
    #: nom -> (octets lus par le detecteur par defaut, octets lus par le chemin
    #: resilient). `None` = non decode. Les deux colonnes ne disent pas la meme
    #: chose : la premiere mesure le detecteur, la seconde ce que le produit
    #: obtient reellement au scan.
    attendus = {
        "calibration-qr-300dpi.png": (181, 181),
        "chendj-qr-300dpi.png": (380, 380),
        "heteroclite-qr-300dpi.png": (338, 338),
        "main-qr-300dpi.png": (None, 368),
    }
    mesures = {}
    for nom in sorted(attendus):
        image = cv2.imread(str(dossier / nom), cv2.IMREAD_GRAYSCALE)
        assert image is not None, f"{nom} illisible: pointeur LFS non materialise ?"
        direct = qr_codes.decode_qr_image(image)
        resilient = qr_codes.decode_qr_image_resilient(image)
        mesures[nom] = (
            len(direct.text.encode("utf-8")) if direct.ok else None,
            len(resilient.text.encode("utf-8")) if resilient.ok else None,
        )

    assert mesures == attendus, (
        f"les verdicts du TERRAIN ont change: {mesures} au lieu de {attendus}. "
        "Ces captures ne passent pas par l'encodeur, donc un ecart signale que "
        f"le decodage a bouge. Decodeur: OpenCV {cv2.__version__}."
    )
