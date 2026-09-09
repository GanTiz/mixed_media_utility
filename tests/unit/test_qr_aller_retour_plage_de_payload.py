"""Aller-retour `encode -> render -> decode` sur TOUTE la plage qu'`io.payload` autorise.

**La frontiere qui manquait, et ce qu'elle a coute de ne pas exister.** Le depot
mesurait l'aller-retour QR sur une poignee de charges utiles, et aucune ne
montait au-dela de la version 7 de symbole autrement qu'incidemment. Or
`io.payload` autorise `NOMINAL_BUDGET_BYTES = 512` et `ALERT_BUDGET_BYTES = 768`,
c'est-a-dire les versions 19 et 23 au niveau ECC de production. Toute la plage
haute etait donc **produite sans jamais etre relue**.

**Ce que ce banc mesure, en trois volets qui ne valent que reunis.**

1. *Synthese* -- chaque taille de la plage, a la geometrie de production, doit
   revenir a l'identique. Une taille qui tombe sur une version bannie par le
   module (`QR_BANNED_SYMBOL_VERSIONS`) n'est pas exemptee : elle doit etre
   **refusee par la garde de geometrie**, sinon la garde ment.
2. *Terrain* -- les quatre recadrages reels de `tests/fixtures/qr_300dpi/`
   portent v11 a v16, c'est-a-dire **tous au-dessus de la version 7**, et ils se
   decodent. CLAUDE.md (2026-09-02) : « une fixture de synthese peut fabriquer
   une panne que le terrain n'a PAS ». Le volet 2 est ce qui empeche de lire le
   volet 1 comme une propriete du papier ; sans lui, un rouge de synthese
   ferait a nouveau conclure a un defaut produit -- ce qui a deja ete publie
   puis retracte deux fois dans ce depot.
3. *Frontiere negative* -- aucun saut conditionne a la version d'OpenCV ne peut
   apparaitre ici. Un banc qui se saute sous une version cassee laisserait
   revenir exactement le defaut qu'il est cense tenir.

**Pourquoi le verdict NOMME la version d'OpenCV.** Le defaut mesure le
2026-09-06 est entierement porte par le decodeur : meme arbre, meme commit, meme
script, meme graine, deux interpreteurs --

    opencv-contrib-python 4.10.0.84 : 10/96 cas decodent (plafond v7)
    opencv-contrib-python 5.0.0.93  : 93/96 cas decodent (seuls les 3 v22 echouent)

Un echec ici qui ne nommerait pas `cv2.__version__` renverrait le lecteur vers le
code de rendu, ou il ne trouverait rien -- c'est le detour qui a coute une nuit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

RACINE_DEPOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE_DEPOT / "src"))

from mixed_media_utility import qr_codes
from mixed_media_utility.io import payload as payload_io

#: Le fichier se relit lui-meme pour tenir sa frontiere negative.
CE_FICHIER = Path(__file__).resolve()

#: Alphabet de remplissage **deterministe** : ni aleatoire ni horodate, pour que
#: deux conteneurs produisent le meme symbole a taille egale. Il est volontairement
#: ASCII pur, donc un octet par caractere : la taille demandee EST la taille
#: obtenue, et le banc mesure la plage qu'il annonce.
ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-_"

#: Pas de balayage de la plage. 32 octets donnent 24 points de mesure de la borne
#: basse au plafond dur, soit **toutes** les versions de symbole de v4 a v23 sans
#: trou -- verifie par `test_la_plage_couvre_bien_les_versions_hautes`.
PAS_DE_PLAGE = 32

#: Geometrie de production, lue du module plutot que recopiee : si la cible
#: bougeait, ce banc suivrait au lieu de mesurer une geometrie perimee.
TAILLE_MM = qr_codes.QR_PRINT_SIZE_TARGET_MM
DPI = qr_codes.QR_MIN_SCAN_DPI


def charge_utile(taille: int) -> str:
    """Rend une charge de `taille` octets exactement, sans etat ni horloge."""
    return "".join(ALPHABET[i % len(ALPHABET)] for i in range(taille))


def _tailles_de_la_plage() -> list[int]:
    return list(range(PAS_DE_PLAGE, payload_io.ALERT_BUDGET_BYTES + 1, PAS_DE_PLAGE))


def _diagnostic(taille: int, version: int, ppm: float, statut: str) -> str:
    """Message d'echec qui NOMME la version d'OpenCV.

    Il ne dit pas seulement « ca n'a pas decode » : il donne les trois grandeurs
    qui separent un defaut de rendu d'un defaut de decodeur (version de symbole,
    pixels par module, statut), et la version du decodeur qui a rendu ce verdict.
    """
    return (
        f"charge de {taille} octets -> symbole v{version} a {ppm:.2f} px/module, "
        f"statut={statut}. Decodeur: opencv-contrib-python {cv2.__version__}. "
        "Si cette version est < 5.0, le defaut est le DECODEUR et non le rendu: "
        "mesure du 2026-09-06, 4.10.0.84 plafonne a la version 7 sur un rendu de "
        "synthese la ou 5.0.0.93 decode jusqu'a v23, et les rasters REELS de "
        "tests/fixtures/qr_300dpi/ (v11 a v16) decodent sous les DEUX."
    )


@pytest.mark.parametrize("taille", _tailles_de_la_plage())
def test_toute_la_plage_de_payload_fait_l_aller_retour(taille: int) -> None:
    """Chaque taille autorisee par `io.payload` revient a l'identique -- ou est refusee.

    Les deux issues sont mesurees, jamais confondues : une version bannie doit
    **etre nommee par la garde de geometrie**, pas silencieusement toleree ici.
    """
    texte = charge_utile(taille)
    assert qr_codes.payload_size_bytes(texte) == taille

    natif = qr_codes.encode_qr_image(texte)
    cote = int(natif.shape[0])
    version = qr_codes.symbol_version(cote)
    ppm = qr_codes.pixels_per_module(cote, TAILLE_MM, DPI)
    verdict_geometrie = qr_codes.check_print_geometry(cote, TAILLE_MM, DPI)

    if version in qr_codes.QR_BANNED_SYMBOL_VERSIONS:
        # Le seul cas ou l'aller-retour n'est pas exige, et il ne s'exempte pas
        # tout seul : la garde doit refuser d'imprimer, sinon la planche partirait
        # avec un QR que rien ne relira.
        assert verdict_geometrie == qr_codes.GEOMETRY_UNUSABLE, (
            f"v{version} est bannie mais check_print_geometry rend "
            f"{verdict_geometrie!r}: la planche s'imprimerait sans un mot."
        )
        return

    rendu = qr_codes.render_for_print(natif, TAILLE_MM, DPI)
    resultat = qr_codes.decode_qr_image(rendu)

    assert resultat.ok, _diagnostic(taille, version, ppm, resultat.status)
    assert resultat.text == texte, _diagnostic(
        taille, version, ppm, "decode mais INFIDELE"
    )


def test_la_plage_couvre_bien_les_versions_hautes() -> None:
    """Le banc mesure ce qu'il annonce, et le pas ne laisse pas de trou.

    Sans cette garde, faire passer `PAS_DE_PLAGE` de 32 a 256 laisserait le banc
    vert en ne mesurant plus que quatre points -- une regression invisible, du
    genre exact que la campagne de mutation cherche.
    """
    versions = sorted(
        {
            qr_codes.symbol_version(int(qr_codes.encode_qr_image(charge_utile(t)).shape[0]))
            for t in _tailles_de_la_plage()
        }
    )
    assert versions[0] <= 4, versions
    # Le plafond dur d'`io.payload` doit etre atteint, pas approche.
    assert versions[-1] >= 23, versions
    # Et la plage haute -- celle que le depot ne relisait jamais -- est bien
    # representee : au moins dix versions strictement au-dessus de v7.
    assert len([v for v in versions if v > 7]) >= 10, versions


def test_le_plafond_dur_est_le_dernier_point_mesure() -> None:
    """La derniere taille du balayage EST `ALERT_BUDGET_BYTES`, pas la valeur d'avant.

    Un pas qui ne divise pas le plafond ferait manquer le plafond lui-meme, et
    c'est precisement la borne au-dela de laquelle `encode_qr_image` refuse.
    """
    assert _tailles_de_la_plage()[-1] == payload_io.ALERT_BUDGET_BYTES
    assert payload_io.NOMINAL_BUDGET_BYTES in _tailles_de_la_plage()
    au_dela = charge_utile(payload_io.ALERT_BUDGET_BYTES + 1)
    with pytest.raises(qr_codes.QRPayloadTooLarge):
        qr_codes.encode_qr_image(au_dela)


# --- Volet 2 : le terrain, qui dit que le volet 1 n'est pas une loi du papier ---

FIXTURES_300DPI = RACINE_DEPOT / "tests" / "fixtures" / "qr_300dpi"

#: Les quatre recadrages reels, **avec des valeurs distinguables** (version de
#: symbole et cardinal d'octets differents), et non un remplissage uniforme.
#: L'ordre place volontairement une cible a CHAQUE BORD : `calibration` en tete
#: est la plus legere (v11), `main` en queue est celle qui exige le repli. Un
#: balayage tronque d'un cote ou de l'autre laisse donc tomber une cible qui
#: porte une propriete que les autres n'ont pas.
RASTERS_REELS = [
    ("calibration", 11, 181, qr_codes.DECODE_OK),
    ("heteroclite", 15, 338, qr_codes.DECODE_OK),
    ("chendj", 16, 380, qr_codes.DECODE_OK),
    ("main", 16, 368, qr_codes.DECODE_UNREADABLE),
]


def _lire_raster_reel(nom: str) -> np.ndarray:
    """Relit un recadrage 300 dpi et refuse d'avancer sur un pointeur Git LFS.

    Ces PNG ne sont volontairement pas sous LFS, mais la garde reste : un
    pointeur de 133 octets ne leve **aucune** erreur et ferait echouer le banc
    sur un message de decodage incomprehensible au lieu de nommer la cause.
    """
    chemin = FIXTURES_300DPI / f"{nom}-qr-300dpi.png"
    assert chemin.exists(), f"fixture absente: {chemin}"
    taille = chemin.stat().st_size
    assert taille >= 500, (
        f"{chemin} pese {taille} octets: pointeur Git LFS non materialise. "
        "Reparer par `git lfs checkout` (cout reseau nul)."
    )
    image = cv2.imread(str(chemin), cv2.IMREAD_UNCHANGED)
    assert image is not None, f"{chemin} n'est pas une image decodable"
    return image


@pytest.mark.parametrize("nom, version_attendue, octets, statut_sans_repli", RASTERS_REELS)
def test_le_terrain_decode_AU_DESSUS_de_la_version_7(
    nom: str, version_attendue: int, octets: int, statut_sans_repli: str
) -> None:
    """Le symetrique du volet 1, et la seule chose qui l'empeche d'etre mal lu.

    Ces quatre symboles ont ete **imprimes puis scannes** (HP Envy, 300 dpi,
    2026-08-17). Ils portent v11 a v16 -- tous au-dessus du plafond v7 mesure sur
    la synthese sous OpenCV 4.10 -- et ils decodent sous les DEUX versions
    d'OpenCV, verdict pour verdict. La conclusion « notre chaine ne sait pas
    relire au-dela de v7 » est donc fausse du produit, et ce test est ce qui
    l'ecrit plutot que de le laisser reconclure.
    """
    image = _lire_raster_reel(nom)

    assert qr_codes.decode_qr_image(image).status == statut_sans_repli, (
        f"{nom}: verdict sans repli inattendu sous opencv {cv2.__version__}"
    )

    resultat = qr_codes.decode_qr_image_resilient(image)
    assert resultat.ok, f"{nom}: {resultat.status} sous opencv {cv2.__version__}"
    assert len(resultat.text.encode("utf-8")) == octets, nom

    # La version du symbole, relue en le reencodant : c'est le chiffre qui rend
    # ce test comparable au volet 1.
    version = qr_codes.symbol_version(
        int(qr_codes.encode_qr_image(resultat.text).shape[0])
    )
    assert version == version_attendue, f"{nom}: v{version} au lieu de v{version_attendue}"
    # Le « au-dessus de v7 » qui donne son sens a ce volet n'est PAS assert ici :
    # l'egalite ci-dessus le rend deja vrai par construction, donc un
    # `assert version > 7` y serait tautologique -- mutant M12, mesure survivant
    # le 2026-09-06. Il vit au niveau de la TABLE, ou il discrimine vraiment
    # (`test_les_versions_attendues_sont_TOUTES_au_dessus_de_la_v7`).


def test_les_versions_attendues_sont_TOUTES_au_dessus_de_la_v7() -> None:
    """Ce qui donne son sens au volet terrain, pose la ou il discrimine.

    Le volet 2 ne dit quelque chose du plafond v7 mesure sur la synthese que si
    les quatre rasters portent des versions strictement superieures. Abaisser
    une valeur attendue de la table viderait le volet de son propos sans faire
    rougir un seul cas -- c'est ce que cette frontiere ferme.
    """
    versions = [version for _, version, _, _ in RASTERS_REELS]
    assert min(versions) > 7, versions
    # Et la table doit couvrir plus d'une version, sinon les quatre cas
    # mesureraient le meme point (regle des fabriques, point 1).
    assert len(set(versions)) >= 2, versions


def test_les_quatre_rasters_reels_sont_DISTINGUABLES() -> None:
    """La regle des fabriques, appliquee a une fixture de terrain.

    Quatre rasters qui porteraient la meme version et le meme cardinal ne
    demasqueraient aucun appariement inverse : le test ci-dessus passerait en
    lisant n'importe lequel des quatre a la place de n'importe quel autre.
    """
    cardinaux = [octets for _, _, octets, _ in RASTERS_REELS]
    assert len(set(cardinaux)) == len(cardinaux), cardinaux
    # Et les deux bords different aussi entre eux, sur les deux grandeurs.
    tete, queue = RASTERS_REELS[0], RASTERS_REELS[-1]
    assert tete[1] != queue[1] and tete[2] != queue[2]
    assert tete[3] != queue[3], "les deux bords doivent porter des verdicts distincts"


def test_le_lecteur_de_raster_NOMME_un_pointeur_LFS_au_lieu_de_le_decoder(tmp_path) -> None:
    """La garde de pointeur se mesure, elle ne se relit pas.

    Sans ce test, retirer la garde laisserait le banc entierement vert : les
    quatre PNG sont materialises ici. C'est exactement le mode de panne que
    CLAUDE.md decrit -- un pointeur de 133 octets ne leve AUCUNE erreur, et le
    banc echouerait plus loin sur un message de decodage incomprehensible.

    On fabrique le pointeur plutot que d'attendre un conteneur casse : c'est la
    seule facon d'avoir la mesure dans un conteneur sain.
    """
    global FIXTURES_300DPI
    faux = tmp_path / "calibration-qr-300dpi.png"
    faux.write_text(
        "version https://git-lfs.github.com/spec/v1\n"
        "oid sha256:0000000000000000000000000000000000000000000000000000000000000000\n"
        "size 199319\n",
        encoding="utf-8",
    )
    assert faux.stat().st_size < 500

    ancien = FIXTURES_300DPI
    FIXTURES_300DPI = tmp_path
    try:
        with pytest.raises(AssertionError) as refus:
            _lire_raster_reel("calibration")
    finally:
        FIXTURES_300DPI = ancien

    # Le refus doit NOMMER la cause et le geste, pas seulement echouer.
    assert "pointeur Git LFS" in str(refus.value)
    assert "git lfs checkout" in str(refus.value)


def test_le_payload_de_terrain_est_du_JSON_lisible_et_pas_un_texte_quelconque() -> None:
    """Le volet terrain porte sur le vrai schema, pas sur un remplissage.

    Sans cette garde, `decode_qr_image_resilient` pourrait rendre n'importe quel
    texte du bon cardinal et les quatre cas resteraient verts.
    """
    for nom, _, octets, _ in RASTERS_REELS:
        texte = qr_codes.decode_qr_image_resilient(_lire_raster_reel(nom)).text
        brut = json.loads(texte)
        assert isinstance(brut, dict) and brut, nom
        assert len(texte.encode("utf-8")) == octets, nom


# --- Volet 3 : la frontiere negative, sans laquelle les deux autres se perdent ---

#: Marqueurs qui, dans CE fichier, feraient de la frontiere une promesse vide.
#: `skipif` conditionne a la version est le cas exact contre lequel elle est
#: posee ; `xfail` fait la meme chose en plus discret, en rendant un rouge
#: attendu et donc muet.
MARQUEURS_DE_SAUT = ("skipif", "importorskip", "xfail", "skip(")


def test_ce_banc_NE_PEUT_PAS_se_sauter_sous_une_version_cassee() -> None:
    """Frontiere negative : aucun saut ne peut entrer ici.

    Un test positif ne verrait jamais revenir un saut conditionne a la version
    du decodeur. Or c'est le geste le plus tentant devant un rouge
    d'environnement, et c'est celui qui laisserait le defaut revenir sans un
    mot -- exactement ce que la revue a demande d'empecher.

    La lecture passe par `tokenize` et non par une recherche de sous-chaine :
    une recherche naive attrape ses propres commentaires et sa propre
    docstring, ce qui rend la frontiere ROUGE en permanence et donc inutile.
    Seuls les jetons de CODE sont regardes -- les chaines et les commentaires
    sont ecartes, c'est-a-dire exactement la ou ces mots ont le droit d'etre.
    """
    import io
    import tokenize

    source = CE_FICHIER.read_text(encoding="utf-8")
    jetons_de_code = [
        jeton.string
        for jeton in tokenize.generate_tokens(io.StringIO(source).readline)
        if jeton.type not in (tokenize.STRING, tokenize.COMMENT)
    ]
    # `MARQUEURS_DE_SAUT` lui-meme est du code : on retire son unique mention
    # d'identifiant plutot que de se laisser attraper par sa propre definition.
    code = " ".join(j for j in jetons_de_code if j != "MARQUEURS_DE_SAUT")

    suspectes = [marqueur for marqueur in MARQUEURS_DE_SAUT if marqueur in code]
    assert not suspectes, (
        "un saut conditionnel est apparu dans ce banc: "
        f"{suspectes}. Ce banc doit ECHOUER en nommant opencv, jamais se sauter."
    )


def test_la_frontiere_negative_ATTRAPE_reellement_un_saut_reinjecte() -> None:
    """La moitie sans laquelle la precedente ne prouve rien.

    Une frontiere negative qui ne rougit sur rien est indistinguable d'une
    frontiere cassee. On lui donne donc une source ou un saut a ete REINJECTE
    et on verifie qu'elle le voit -- et qu'elle ne le voit pas quand il est
    seulement cite dans un commentaire ou une chaine.
    """
    import io
    import tokenize

    def marqueurs_vus(source: str) -> list[str]:
        jetons = [
            jeton.string
            for jeton in tokenize.generate_tokens(io.StringIO(source).readline)
            if jeton.type not in (tokenize.STRING, tokenize.COMMENT)
        ]
        code = " ".join(jetons)
        return [marqueur for marqueur in MARQUEURS_DE_SAUT if marqueur in code]

    saut_reel = (
        "import pytest\n"
        "@pytest.mark.skipif(True, reason='opencv trop vieux')\n"
        "def test_x():\n    pass\n"
    )
    assert marqueurs_vus(saut_reel) == ["skipif"], marqueurs_vus(saut_reel)

    saut_cite = (
        "# on n'ecrit jamais skipif ici\n"
        "def test_x():\n"
        "    \"\"\"pas de xfail non plus\"\"\"\n"
        "    pass\n"
    )
    assert marqueurs_vus(saut_cite) == [], marqueurs_vus(saut_cite)


def test_le_message_d_echec_nomme_bien_la_version_d_opencv() -> None:
    """La promesse « le verdict nomme la version » se mesure, elle ne se relit pas.

    Le diagnostic est une fonction : si quelqu'un la simplifiait en « decode
    KO », ce test rougirait au lieu de laisser le banc rendre un echec muet.
    """
    message = _diagnostic(512, 19, 8.89, qr_codes.DECODE_UNREADABLE)
    assert cv2.__version__ in message
    assert "opencv-contrib-python" in message
    assert "512" in message and "v19" in message and "8.89" in message
    assert qr_codes.DECODE_UNREADABLE in message
