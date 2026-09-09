# -*- coding: utf-8 -*-
"""Story 11.4e -- les quatre etats de `E2-1e`, du modele pur a l'ecran monte.

**Ce que ce banc ferme, et ce que le banc voisin ne pouvait pas fermer.**
`test_ajout_de_rush_tui.py` dit de lui-meme : « Ce banc ne mesure aucun ecran,
et c'est le partage que le lot assume » -- `EPIC11-ARB-144` interdisait de
coder un ecran dont la maquette n'etait pas validee. `EPIC11-ARB-226`
(2026-09-05, verbatim d'Egan : « Je valide la v4 ») leve l'interdit pour
quatre maquettes. Celle du refus (`E2-1f`) est restee dehors le temps
qu'`EPIC11-ARB-231` lui donne sa troisieme sortie ; elle est validee depuis, et
son ecran vit dans `test_ecran_E2_1f_refus_de_conflit.py`. Ce banc-ci n'en
garde que le volet NEGATIF -- les quatre AUTRES motifs de refus gardent le
« pas encore ».

Trois familles de mesures, et elles ne se remplacent pas :

* **le modele contre la maquette**, ligne a ligne, avec un inventaire FERME
  des ecarts nommes. Un ecart tu est un ecran qui derive ; un inventaire qui
  garderait ses vieilles entrees se remplirait jusqu'a ne plus rien mesurer,
  donc le volet symetrique le mesure aussi ;
* **des frontieres NEGATIVES sur `EPIC11-ARB-227`** -- ni `0`, ni `--`, ni un
  libelle d'absence a la place du cardinal. Aucun test positif ne verrait la
  reintroduction, c'est la seule forme qui l'attrape ;
* **l'ecran monte**, et le disque mesure de part et d'autre de la validation :
  le temps 1 ne touche aucun octet, le temps 2 seul ecrit.

**Regle des fabriques (`CLAUDE.md`), les quatre points.** La collection de ce
banc est la **liste de lignes du cartouche**. Elle porte huit lignes toutes
distinguables (point 1) ; les tests d'omission visent une ligne du MILIEU
(`Codec · format de pixel`) et une ligne de QUEUE (`Timecode de départ`), et
les tests de contenu une ligne de TETE (`Nom du fichier`), une du milieu
(`Résolution`) et une de queue (`Espace couleur`) -- points 2 et 4. La
seconde collection est celle des rushes du projet, ou la cible est placee en
tete, au milieu et en queue par le banc voisin, reutilise et non recopie.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
# Les fabriques du banc voisin sont **reutilisees, jamais recopiees** : meme
# geste que `test_sobriete_et_grille_extraction`, et pour le meme motif -- deux
# projets de synthese qui divergeraient feraient mesurer deux produits.
sys.path.insert(0, str(Path(__file__).resolve().parent))
# La sonde de pointeur vit **une seule fois** pour tout le depot
# (`EPIC11-ARB-241`) : deux redactions de la meme garde, c'est deux regimes qui
# divergent -- exactement l'ecart que cet arbitrage ferme.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_ajout_de_rush_tui as voisin  # noqa: E402
import test_rang_de_desambiguisation as rangs  # noqa: E402

from mixed_media_utility.declaration_de_rush import (  # noqa: E402
    ISSUES_PAR_MOTIF,
    MOTIF_RUSH_DEJA_DECLARE,
    MOTIFS_DE_REFUS,
    DeclarationPreparee,
    RefusDeDeclaration,
    preparer_une_declaration,
)
from mixed_media_utility.io.extraction_manifest import (  # noqa: E402
    MANIFEST_FILENAME,
    RushRecord,
)
from mixed_media_utility import source_confirmation  # noqa: E402
from mixed_media_utility.tui import ajout_de_rush, jetons  # noqa: E402
from mixed_media_utility.tui import rushes  # noqa: E402
from mixed_media_utility.tui import atelier_extraction as amont  # noqa: E402
from mixed_media_utility.tui.coque import EcranPasEncore  # noqa: E402

MODES = voisin.MODES

_RACINE = Path(__file__).resolve().parents[3]
_MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
              / "ux-tui-2026-08-27" / "maquettes")

#: Le rush REEL du depot, et non une fixture de synthese. `CLAUDE.md` : « une
#: fixture de synthese peut fabriquer une panne que le terrain n'a PAS », et
#: le symetrique a coute davantage -- une mesure de synthese mesure la
#: synthese. Ce fichier-la passe par le vrai `ffprobe` et le vrai coeur.
RUSH_REEL = _RACINE / "tests" / "fixtures" / "rushes" / \
    "rush_test_16x9_1920x1080_25fps.mp4"

#: Le SECOND rush reel, celui du TERRAIN : 4K, sorti d'une vraie camera, la
#: ou `RUSH_REEL` est une fabrique `testsrc`. Il signale son triplet
#: (`bt709` sur les trois champs), et depuis `EPIC11-ARB-247` `RUSH_REEL` le
#: signale aussi -- ce n'est donc plus lui qui porte, seul, la mesure de la
#: VALEUR.
#:
#: **Corrige le 2026-09-06 (`EPIC11-ARB-247`).** Cette place disait « la ou
#: `RUSH_REEL` ne signale rien ». C'etait vrai jusqu'a la normalisation des
#: quatre rushes de synthese : leur triplet etait `unknown` sur les trois
#: champs, ce qui faisait refuser `extract` sans `--accept-unknown-color`.
#: L'ABSENCE ne se lit donc plus dans un fichier du depot ; elle se FABRIQUE,
#: par :func:`rush_du_terrain_sans_triplet`, a partir de ce meme rush --
#: c'est-a-dire que le drapeau VARIE au lieu d'etre subi.
#:
#: Il ne descend PAS tout seul (`.lfsconfig` exclut `tests/fixtures/rushes/
#: reels/**` : 64 Mo par conteneur, c'est ce qui a vide le quota de bande
#: passante le 2026-09-03). Le test qui s'en sert saute donc sur pointeur, et
#: le dit -- un saut silencieux serait un banc vert qui ne mesure rien.
RUSH_REEL_SIGNALE = _RACINE / "tests" / "fixtures" / "rushes" / "reels" / \
    "rush_bitch-4_chendj-mat.mp4"


# ===========================================================================
# La grille des maquettes, LUE plutot que recopiee
# ===========================================================================

#: Largeur ECRIVABLE du cartouche tel que les maquettes le dessinent :
#: `construire_maquette.cartouche` prend une boite de 72 colonnes et lui retire
#: son cadre et ses deux marges. Elle differe de
#: `jetons.largeur_de_cartouche(80)` -- 72 -- parce que le dessin indente le
#: cartouche de deux colonnes de plus que le produit ; c'est un ecart de
#: geometrie qui precede ce lot (il vaut deja pour `E2-3`) et que ce banc ne
#: pretend pas fermer. Ce qu'il mesure, c'est le CONTENU a largeur egale.
LARGEUR_DU_CARTOUCHE_DESSINE = 72 - 4

#: Le prefixe et le suffixe d'une ligne de corps de cartouche dans la grille.
_DEDANS = "│   │ "

#: Le rang de la ligne d'etat, compte depuis 1 -- l'avant-avant-derniere.
RANG_DE_L_ETAT = jetons.HAUTEUR_PLANCHER - 2


def grille(nom: str) -> list[str]:
    """Les 24 lignes de la maquette, sans les annotations manuscrites."""
    return (_MAQUETTES / nom).read_text(encoding="utf-8").rstrip(
        "\n").split("\n")[:jetons.HAUTEUR_PLANCHER]


def corps_du_cartouche(nom: str) -> list[str]:
    """Les lignes de l'INTERIEUR du cartouche, rembourrage compris.

    Le rembourrage est garde : une ligne calee a droite (`(exacte 25/1)`) ne se
    verifie pas autrement, et c'est precisement la ligne ou une mesure en
    `len()` plutot qu'en colonnes se verrait.
    """
    return [ligne[len(_DEDANS):len(_DEDANS) + LARGEUR_DU_CARTOUCHE_DESSINE]
            for ligne in grille(nom) if ligne.startswith(_DEDANS)]


def ligne_d_etat(nom: str) -> str:
    """La ligne d'etat de la maquette, sans son cadre ni son rembourrage."""
    return grille(nom)[RANG_DE_L_ETAT - 1][2:].rstrip("│ ").rstrip()


# ===========================================================================
# Les fabriques : une preparation de declaration, et ses quatre etats
# ===========================================================================

#: Le chemin de `E2-1e` -- il TIENT sur deux lignes de 43 colonnes.
CHEMIN_QUI_TIENT = ("D:\\HOKO\\Documents\\rushes\\2026\\03_tournage_mai\\hd\\"
                    "plan séquence 12.mov")
#: Celui de `E2-1h` -- 115 colonnes, il ne tient pas et se coupe.
CHEMIN_QUI_COUPE = ("D:\\HOKO\\Documents\\clients\\arte\\"
                    "documentaire-chendj\\tournage\\03_tournage_mai\\"
                    "camera_A\\hd\\prores\\plan séquence 12.mov")

NOM_DU_FICHIER = "plan séquence 12.mov"
#: L'identifiant DERIVE. Il ne doit apparaitre nulle part a l'ecran
#: (`EPIC11-ARB-228`, verbatim d'Egan : « Ok ainsi »).
IDENTIFIANT_DERIVE = "plan-sequence-12"


def champs_de_source(couleur: str | None = "bt709",
                     codec: str | None = "prores_ks",
                     pixels: str | None = "yuv422p10le") -> dict:
    """Les `source_fields` du coeur, avec le triplet colorimetrique pilotable.

    Les huit cles sont celles de `SOURCE_FIELD_SPECS` : une fabrique qui n'en
    poserait que trois laisserait le modele lire un `dict` plus pauvre que
    celui du produit, et l'ecart ne se verrait que sur un vrai probe.
    """
    return {"source_codec": codec, "source_pix_fmt": pixels,
            "source_bit_depth": 10, "source_sample_aspect_ratio": "1:1",
            "source_color_primaries": couleur, "source_color_trc": couleur,
            "source_colorspace": couleur, "source_color_range": None}


def preparee(chemin: str = CHEMIN_QUI_TIENT, cardinal: int | None = 6300,
             couleur: str | None = "bt709", codec: str | None = "prores_ks",
             pixels: str | None = "yuv422p10le",
             timecode: str | None = "00:00:04:12",
             rush_id: str = IDENTIFIANT_DERIVE,
             champs: dict | None = None,
             duree_secondes: float | None = 252.0) -> DeclarationPreparee:
    """Le temps 1 du coeur, tel que `preparer_une_declaration` le rend.

    Fabrique **de synthese**, et elle est doublee par le rush REEL du depot
    (:func:`preparee_du_terrain`) : les quatre maquettes dessinent un ProRes
    10 bits signale que le depot ne porte pas, et le rush reel ne porte aucune
    des valeurs qu'elles dessinent. Aucun des deux ne suffit seul.
    """
    fields = champs_de_source(couleur, codec, pixels) if champs is None \
        else champs
    record = RushRecord(
        rush_id=rush_id, source_name=NOM_DU_FICHIER, fps_source=25.0,
        source_width=1920, source_height=1080, source_fields=fields,
        source_start_timecode=timecode, source_parent="hd",
        source_path=chemin, source_frame_count=cardinal,
        source_frame_count_is_exact=None if cardinal is None else True)
    return DeclarationPreparee(
        project_dir=Path("projet_demo"),
        manifest_path=Path("projet_demo") / MANIFEST_FILENAME,
        project_id="projet_demo", rush_id=rush_id,
        rush_id_derive=IDENTIFIANT_DERIVE,
        homonymie_levee=rush_id != IDENTIFIANT_DERIVE,
        source_parent="hd", source_name=NOM_DU_FICHIER, source_path=chemin,
        fps_source=25.0, source_width=1920, source_height=1080,
        source_start_timecode=timecode, cardinal_de_frames=cardinal,
        # 6 300 frames a 25 im/s font 252 s, soit `4:12` -- la duree que les
        # QUATRE maquettes dessinent. Elle est posee independamment du
        # cardinal, et c'est tout le point : `E2-1i` la garde quand le cardinal
        # s'en va, parce que c'est elle qui a servi a tenter la corroboration.
        duree_source_secondes=duree_secondes,
        # `EPIC11-ARB-232` : la separation forcee est un cas de la CLI, jamais
        # de ces quatre etats -- un rush deja declare ne monte pas ce panneau.
        separation_forcee=False,
        record=record)


def preparee_du_terrain(tmp_path) -> DeclarationPreparee:
    """La MEME preparation, par le vrai coeur sur le rush reel du depot.

    `CLAUDE.md` : « interroger le raster reel du depot, pas seulement la
    fabrique ». Ici le fichier est un H.264 8 bits **sans timecode de depart**
    -- un etat que la fabrique de synthese ne prend qu'a la demande, et que ce
    fichier-la produit tout seul.

    **Depuis `EPIC11-ARB-247` il DECLARE son triplet** (`bt709` sur les trois
    champs). L'etat symetrique -- colorimetrie absente, `E2-1g` -- se lit sur
    :func:`preparee_du_terrain_sans_triplet`, qui le fabrique a partir du meme
    media.
    """
    dossier = voisin.creer_projet(tmp_path, "projet_reel").chemin
    return preparer_une_declaration(
        project_dir=dossier, video_path=RUSH_REEL,
        logger=logging.getLogger("banc.declaration"))


requiert_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg absent du PATH")


def rush_du_terrain_sans_triplet(tmp_path) -> Path:
    """Le MEME media, prive de sa declaration colorimetrique, sans reencodage.

    **Pourquoi une fabrique plutot qu'un cinquieme fichier de fixture.**
    `CLAUDE.md`, regle des drapeaux : « une garde de repli, de mode ou de
    variante fait VARIER le drapeau dont elle depend, dans les deux sens ».
    Jusqu'au 2026-09-06 ce banc mesurait l'absence de triplet parce que le
    fichier du depot n'en portait pas -- un drapeau SUBI, que la normalisation
    d'`EPIC11-ARB-247` a retourne d'un coup, sans que rien n'ait varie dans le
    banc. Ici l'absence est POSEE, donc les deux cotes tiennent quel que soit
    ce que la fixture declare demain.

    `-c copy` : le flux H.264 n'est pas reencode, seules la VUI du SPS
    (`h264_metadata`, `2` = *unspecified*) et l'atome `colr` du conteneur
    changent. Le condensat des pixels decodes est identique -- mesure le
    2026-09-06, `7be6dcd7…` des deux cotes.
    """
    sortie = tmp_path / "sans_triplet.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(RUSH_REEL), "-c", "copy",
         "-bsf:v", ("h264_metadata=colour_primaries=2"
                    ":transfer_characteristics=2:matrix_coefficients=2"),
         "-color_primaries", "unknown", "-color_trc", "unknown",
         "-colorspace", "unknown", str(sortie)],
        check=True, capture_output=True, timeout=120,
    )
    return sortie


def preparee_du_terrain_sans_triplet(tmp_path) -> DeclarationPreparee:
    """L'etat `E2-1g` sur le vrai coeur : un media reel, sans colorimetrie."""
    dossier = voisin.creer_projet(tmp_path, "projet_sans_triplet").chemin
    return preparer_une_declaration(
        project_dir=dossier, video_path=rush_du_terrain_sans_triplet(tmp_path),
        logger=logging.getLogger("banc.declaration"))


#: Les quatre etats valides par `EPIC11-ARB-226`, et ce qui les distingue.
ETATS = {
    "E2-1e-declaration-confirmation.txt": dict(),
    "E2-1h-declaration-chemin-coupe.txt": dict(chemin=CHEMIN_QUI_COUPE),
    "E2-1g-declaration-colorimetrie-inconnue.txt": dict(couleur=None),
    "E2-1i-declaration-cardinal-absent.txt": dict(cardinal=None),
}


def fiche_de(nom: str, rang: int | None = 4) -> ajout_de_rush.FicheDeDeclaration:
    return ajout_de_rush.FicheDeDeclaration(preparee(**ETATS[nom]), rang=rang)


# ===========================================================================
# L'inventaire FERME des ecarts avec les maquettes validees
# ===========================================================================

#: Ce que le produit rend AUTREMENT que la maquette validee, et **pourquoi**.
#: Une entree sans raison n'a pas sa place ici ; une entree qui cesse de
#: diverger fait rougir le volet symetrique, parce qu'un inventaire qui garde
#: ses vieilles entrees cesse de mesurer.
#:
#: Cle : `(maquette, rang de la ligne dans le corps du cartouche)`.
DIVERGENCES_NOMMEES = {
    # --- 1. la valeur colorimetrique : RETIREE le 2026-09-05, elle est fermee -
    # Cette place portait trois entrees, une par etat -- « bt 709 vs la valeur
    # mesuree ». `EPIC11-ARB-235` a tranche dans l'autre sens que ce que le
    # mot « divergence » laisse croire : ce n'est pas l'ecran qui avait derive
    # de la maquette, c'est la maquette qui avait derive de son PROPRE
    # generateur, dont le commentaire disait deja `bt709` trois lignes
    # au-dessus de la valeur qu'il dessinait. Les trois maquettes ont ete
    # corrigees a la source (`_gen_extraction.LIGNE_DE_COULEUR_SIGNALEE`), et
    # les trois entrees partent dans le meme mouvement parce que le volet
    # symetrique l'EXIGE -- il a d'ailleurs rougi trois fois avant ce retrait,
    # ce qui est la seule preuve que la fermeture a bien eu lieu.
    #
    # Ce que la fermeture laisse derriere elle, et qui n'est pas un
    # commentaire : `test_la_couleur_affichee_est_celle_du_PROBE` et son volet
    # negatif `test_aucune_maquette_du_panneau_ne_porte_la_forme_avec_espace`.
    # Une entree d'inventaire qui part sans laisser de frontiere rend le
    # dossier a la relecture.
    # --- 2. la duree de `E2-1i` : RETIREE le 2026-09-05, elle est fermee ---
    # Cette place portait « la duree n'atteint pas `DeclarationPreparee` ».
    # `duree_source_secondes` l'y porte desormais, et `texte_de_la_resolution`
    # s'en sert en repli du cardinal. L'entree est retiree parce que le volet
    # symetrique EXIGE qu'elle le soit : une divergence qui a cesse d'exister
    # fait rougir l'inventaire. C'est ce mecanisme, et non une relecture, qui
    # a rendu la fermeture verifiable -- garder la trace ici plutot que dans
    # l'historique de git, parce que c'est le seul endroit ou un lecteur de
    # `E2-1i` la cherchera.
}


@pytest.mark.parametrize("nom", sorted(ETATS))
def test_les_quatre_etats_rendent_leur_maquette_LIGNE_A_LIGNE(nom):
    """Le modele contre le dessin valide, a largeur egale et rang par rang.

    C'est la mesure qui attrape la DERIVE : une correction portee a `E2-1e` --
    un libelle, la colonne de valeur, l'ordre des lignes -- qui ne suivrait pas
    sur les trois autres etats ferait deux produits differents, et rien a la
    relecture ne le dirait. Le generateur des maquettes se protege du meme
    defaut par construction (`fiche_de_declaration` y est parametree, pas
    recopiee) ; ici c'est le PRODUIT qui est mesure.
    """
    attendu = corps_du_cartouche(nom)
    rendu = [ligne.ljust(LARGEUR_DU_CARTOUCHE_DESSINE)
             for ligne in fiche_de(nom).lignes(LARGEUR_DU_CARTOUCHE_DESSINE)]
    assert len(rendu) == len(attendu), (
        f"{len(rendu)} lignes rendues pour {len(attendu)} dessinees")
    for rang, (dessine, produit) in enumerate(zip(attendu, rendu)):
        if (nom, rang) in DIVERGENCES_NOMMEES:
            assert dessine != produit, (
                f"{nom} rang {rang} est declare divergent et ne l'est plus : "
                f"retirer l'entree de DIVERGENCES_NOMMEES "
                f"({DIVERGENCES_NOMMEES[(nom, rang)]})")
            continue
        assert produit == dessine, f"{nom}, rang {rang}"


def test_l_inventaire_des_DIVERGENCES_ne_porte_que_des_ecarts_REELS():
    """Volet symetrique : une entree qui ne correspond a rien rendrait muet.

    Deux facons de deriver, et les deux comptent : une cle qui ne designe
    aucune maquette (une maquette renommee, un rang qui n'existe plus) et une
    raison vide -- « un rappel legitimement optionnel entre dans l'inventaire
    **avec son motif ecrit**, jamais en silence » est l'interdit d'Egan sur la
    garde voisine, et il vaut ici mot pour mot.
    """
    for (nom, rang), raison in DIVERGENCES_NOMMEES.items():
        assert nom in ETATS, nom
        assert 0 <= rang < len(corps_du_cartouche(nom)), (nom, rang)
        assert raison and raison.strip(), (nom, rang)


@pytest.mark.parametrize("nom", sorted(ETATS))
def test_les_quatre_lignes_d_etat_sont_rendues_VERBATIM(nom):
    """`EPIC11-ARB-56` : la ligne d'etat porte une MESURE de l'ecran courant.

    Les quatre maquettes en dessinent trois formes -- le rang du rush, la
    coupe du chemin, l'absence de colorimetrie -- toutes prefixees du cardinal
    de frames source tant qu'il est corrobore. Aucune divergence n'est admise
    ici : c'est la seule ligne que les quatre etats font varier de bout en
    bout, donc la seule ou une recopie approximative se verrait tout de suite.
    """
    assert fiche_de(nom).etat(LARGEUR_DU_CARTOUCHE_DESSINE) == ligne_d_etat(nom)


# ===========================================================================
# `EPIC11-ARB-227` -- « On n'affiche rien si on ne corrobore pas »
# ===========================================================================

#: Ce qui n'a PAS le droit de prendre la place du cardinal. Les trois issues
#: qu'Egan a ecartees, plus les substituts que `DESIGN.md` §3 interdit depuis
#: `EPIC7-ARB-67` (« jamais `0:00`, jamais `--:--` presente comme une duree »).
#:
#: **`--` nu n'y figure PAS, et c'est mesure** : le repli ASCII rend le tiret
#: cadratin de `4e rush du projet — rien n'a encore été écrit` par `--`, donc
#: un interdit sur `--` rougirait sur la ponctuation nominale au lieu du
#: substitut. La forme `--:--` reste interdite, elle, et la ligne
#: `Résolution` est mesuree a part -- sans cardinal elle ne porte plus **aucun
#: tiret**, ce qui est la borne la plus serree qu'on puisse poser.
SUBSTITUTS_INTERDITS = ("0 frames", "-- frames", "--:--", "non corrobor",
                        "inconnu", "indetermin", "estim", "? frames")


def tout_ce_que_l_ecran_montre(fiche, largeur=LARGEUR_DU_CARTOUCHE_DESSINE,
                               ascii_seul=False) -> str:
    """Le corps, la ligne d'etat, le bandeau et l'assertion, d'un seul tenant.

    Une frontiere negative posee sur le seul corps du cartouche laisserait
    revenir le substitut par la ligne d'etat ou par le bandeau -- et c'est
    exactement ou `EPIC11-ARB-227` a du etre DEDUIT plutot que lu.
    """
    morceaux = list(fiche.lignes(largeur, ascii_seul))
    morceaux.append(fiche.etat(largeur, ascii_seul))
    morceaux.append(fiche.bandeau(ascii_seul))
    assertion = fiche.assertion(ascii_seul)
    if assertion is not None:
        morceaux.append(assertion)
    return "\n".join(morceaux)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_cardinal_NON_CORROBORE_ne_laisse_AUCUN_substitut(ascii_seul):
    """La frontiere negative de `EPIC11-ARB-227`, sur TOUT ce que l'ecran rend.

    Egan avait trois issues devant lui -- disparition muette, absence nommee
    (`nombre d'images non corrobore`), ligne d'avertissement sous le cadre --
    et il prend la premiere. La recommandation portee a la planche etait la
    DEUXIEME ; elle est ecartee, et ce test existe pour qu'elle ne revienne pas
    comme neuve. Aucun test positif ne verrait sa reintroduction.
    """
    montre = tout_ce_que_l_ecran_montre(
        ajout_de_rush.FicheDeDeclaration(preparee(cardinal=None), rang=4),
        ascii_seul=ascii_seul)
    for interdit in SUBSTITUTS_INTERDITS:
        assert interdit not in montre.lower(), (interdit, montre)
    assert "frames" not in montre, (
        "le mot `frames` ne survit pas au retrait du cardinal : c'est la seule "
        "chose qu'il qualifiait")
    # La borne la plus serree : la ligne `Résolution` ne porte plus AUCUN
    # tiret, donc ni `--`, ni `-`, ni un libelle qui en contiendrait un.
    resolution = [ligne for ligne in montre.split("\n")
                  if ligne.startswith(jetons.replier_ascii(
                      ajout_de_rush.LIBELLE_RESOLUTION) if ascii_seul
                      else ajout_de_rush.LIBELLE_RESOLUTION)]
    assert len(resolution) == 1, resolution
    assert "-" not in resolution[0], resolution[0]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_cardinal_CORROBORE_est_bien_affiche(ascii_seul):
    """Volet symetrique, sans lequel le precedent serait vert sur un ecran vide.

    Une frontiere negative seule est satisfaite par un modele qui n'afficherait
    JAMAIS le cardinal -- c'est-a-dire par la panne opposee. Les deux moities
    se posent ensemble.
    """
    montre = tout_ce_que_l_ecran_montre(
        ajout_de_rush.FicheDeDeclaration(preparee(), rang=4),
        ascii_seul=ascii_seul)
    assert "6 300 frames" in montre, montre
    assert "6 300 frames source" in montre, (
        "la ligne d'etat perd le cardinal alors qu'il est corrobore")


def test_le_cardinal_est_SEPARE_par_une_espace_ORDINAIRE():
    """`6 300` et non `6300` ni `6\u202f300`.

    Mesure sur les maquettes plutot que sur une conviction : elles portent
    `0x20`. Une espace insecable rendrait un point d'interrogation sur les
    consoles que le repli ASCII existe pour servir, et la mesure en colonnes ne
    la distinguerait pas de l'ordinaire.
    """
    assert ajout_de_rush.cardinal_lisible(6300) == "6 300"
    assert ajout_de_rush.cardinal_lisible(1234567) == "1 234 567"
    assert ajout_de_rush.cardinal_lisible(125) == "125"
    assert "\u00a0" not in ajout_de_rush.cardinal_lisible(6300)
    assert "\u202f" not in ajout_de_rush.cardinal_lisible(6300)


# ===========================================================================
# La DUREE ne suit PAS le sort du cardinal (fermeture du 2026-09-05)
# ===========================================================================
#
# Ces quatre mesures ferment la divergence que `DIVERGENCES_NOMMEES` portait.
# Elles ne se contentent pas de constater `4:12` a l'ecran : la ligne
# `Résolution` de `E2-1i` est deja comparee a sa maquette, caractere par
# caractere, par `test_les_quatre_etats_rendent_leur_maquette_LIGNE_A_LIGNE`.
# Ce que ces mesures ajoutent est ce qu'une comparaison de rendu ne peut pas
# voir : **quel chemin** a produit la duree, et ce qui arrive quand les deux
# manquent.


def test_la_duree_SURVIT_a_l_absence_du_cardinal():
    """`E2-1i` : le cardinal s'en va, la duree reste.

    C'est l'etat que la maquette dessine et que l'ecran ne rendait pas : la
    duree du flux est la grandeur qui sert a TENTER la corroboration du
    cardinal, donc elle existe par construction quand celui-ci manque.
    """
    ligne = ajout_de_rush.texte_de_la_resolution(1920, 1080, None, 25.0, 252.0)
    assert ligne == "1920 × 1080 · 4:12"


def test_la_duree_EXACTE_prime_sur_celle_du_CONTENEUR():
    """Les deux chemins sont distinguables, et c'est le bon qui gagne.

    **La fabrique fait diverger les deux sources sur l'axe mesure** : 6 300
    frames a 25 im/s font `4:12`, la duree du conteneur dit `9:59`. Un test qui
    poserait les deux a la meme valeur serait vert quel que soit l'ordre des
    deux termes -- c'est-a-dire vert pour un `or` inverse, qui rendrait
    l'ecran dependant d'une duree moins precise sans qu'aucun rendu ne change
    sur les maquettes.

    `cardinal / fps` est la grandeur EXACTE : le conteneur, lui, declare une
    duree qui inclut souvent une queue de flux audio ou un arrondi de
    remultiplexage.
    """
    ligne = ajout_de_rush.texte_de_la_resolution(1920, 1080, 6300, 25.0, 599.0)
    assert "4:12" in ligne
    assert "9:59" not in ligne


def test_les_DEUX_absentes_ne_laissent_AUCUNE_duree():
    """Le volet negatif : pas de repli sur un repli.

    `EPIC7-ARB-67` interdit `0:00` a la place d'une duree, et `EPIC11-ARB-227`
    interdit tout substitut a la place du cardinal. Quand ni le cardinal ni la
    duree du conteneur ne sont connus, la ligne se reduit a la resolution --
    elle ne fabrique pas une duree nulle, et elle ne dit pas non plus son
    absence.
    """
    ligne = ajout_de_rush.texte_de_la_resolution(1920, 1080, None, 25.0, None)
    assert ligne == "1920 × 1080"
    for interdit in SUBSTITUTS_INTERDITS:
        assert interdit not in ligne
    assert "0:00" not in ligne


def test_la_duree_du_CONTENEUR_atteint_reellement_le_CARTOUCHE():
    """Le raccord, pas seulement la fonction de mise en forme.

    Une fonction juste dont l'appelant ne passe pas le nouvel argument est
    exactement le defaut que la dette decrivait -- la duree existait au coeur
    et n'atteignait pas l'ecran. La mesure porte donc sur la ligne rendue par
    :class:`FicheDeDeclaration`, avec son VOLET SYMETRIQUE : la meme fiche
    privee de duree perd son `4:12`, ce qui prouve que le `4:12` du premier
    cas vient bien du champ et non d'ailleurs.
    """
    def ligne_resolution(fiche):
        return next(l for l in fiche.lignes(LARGEUR_DU_CARTOUCHE_DESSINE)
                    if ajout_de_rush.LIBELLE_RESOLUTION in l)

    avec = ligne_resolution(ajout_de_rush.FicheDeDeclaration(
        preparee(cardinal=None, duree_secondes=252.0), rang=4))
    sans = ligne_resolution(ajout_de_rush.FicheDeDeclaration(
        preparee(cardinal=None, duree_secondes=None), rang=4))
    assert "4:12" in avec
    assert "4:12" not in sans


# ===========================================================================
# `EPIC11-ARB-228` -- aucune ligne « nom sur le disque »
# ===========================================================================

@pytest.mark.parametrize("rush_id", (IDENTIFIANT_DERIVE,
                                     f"{IDENTIFIANT_DERIVE}_2"))
@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ecran_ne_montre_JAMAIS_l_identifiant_derive(rush_id, ascii_seul):
    """`EPIC11-ARB-228` (« Ok ainsi ») et `EPIC11-ARB-153`, ensemble.

    Le `rush_id` « ne sert qu'aux chemins, aux noms de frames et au payload QR
    -- **jamais a l'affichage** », et une ligne « nom sur le disque » a ete
    refusee nommement. Le second parametre est le cas d'homonymie levee
    (`EPIC11-ARB-9`) : c'est celui ou un identifiant suffixe existe, donc celui
    ou l'afficher serait le plus tentant et le plus faux.
    """
    fiche = ajout_de_rush.FicheDeDeclaration(preparee(rush_id=rush_id), rang=4)
    montre = tout_ce_que_l_ecran_montre(fiche, ascii_seul=ascii_seul)
    assert rush_id not in montre, montre
    attendu = (jetons.replier_ascii(NOM_DU_FICHIER) if ascii_seul
               else NOM_DU_FICHIER)
    assert attendu in montre, (
        "le VRAI nom du fichier a disparu avec l'identifiant : AC 3.4")


# ===========================================================================
# `EPIC11-ARB-151` et la note 6 -- le chemin, entier ou coupe SUR UN SEPARATEUR
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_chemin_qui_TIENT_n_est_pas_coupe(ascii_seul):
    """`EPIC11-ARB-151` : le chemin est COMPLET tant qu'il tient.

    L'oracle est le recollement, jamais la presence du glyphe d'abregement :
    un dossier qui porterait un `…` dans son nom ferait mentir un test de
    glyphe, et `segments_de_chemin` promet justement que recoller rend le
    chemin caractere pour caractere.
    """
    fiche = ajout_de_rush.FicheDeDeclaration(preparee(), rang=4)
    assert fiche.chemin_coupe(LARGEUR_DU_CARTOUCHE_DESSINE, ascii_seul) is False
    recolle = "".join(fiche.chemin_replie(LARGEUR_DU_CARTOUCHE_DESSINE,
                                          ascii_seul))
    attendu = (jetons.replier_ascii(CHEMIN_QUI_TIENT) if ascii_seul
               else CHEMIN_QUI_TIENT)
    assert recolle == attendu


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_chemin_qui_NE_TIENT_PAS_est_coupe_et_MESURE(ascii_seul):
    """`E2-1h` : la coupe se dit, et la ligne d'etat en donne la MESURE.

    Une ligne qui dirait seulement « chemin abrege » n'apprendrait rien
    (`EPIC11-ARB-56`). Le nombre de colonnes du chemin ENTIER est ce qui rend
    la coupe verifiable, et c'est ce que la maquette porte : 115.
    """
    fiche = ajout_de_rush.FicheDeDeclaration(preparee(chemin=CHEMIN_QUI_COUPE),
                                             rang=4)
    assert fiche.chemin_coupe(LARGEUR_DU_CARTOUCHE_DESSINE, ascii_seul) is True
    assert fiche.colonnes_du_chemin(ascii_seul) == 115
    assert "115 colonnes" in fiche.etat(LARGEUR_DU_CARTOUCHE_DESSINE,
                                        ascii_seul)
    # La coupe tombe sur une FRONTIERE DE SEPARATEUR (note 9 d'Egan) : aucun
    # nom de dossier n'est entame.
    for ligne in fiche.chemin_replie(LARGEUR_DU_CARTOUCHE_DESSINE, ascii_seul):
        assert ligne in (jetons.replier_ascii(CHEMIN_QUI_COUPE) if ascii_seul
                         else CHEMIN_QUI_COUPE) or "…" in ligne or "..." in ligne


# ===========================================================================
# `EPIC11-ARB-149` / `-150` -- l'espace couleur, UNE ligne et TROIS etats
# ===========================================================================

@pytest.mark.parametrize("champs,signale,attendu", (
    # complet, les trois EGALES -> une seule valeur (`EPIC11-ARB-150`)
    (champs_de_source("bt709"), True, "bt709"),
    # complet, les trois DIFFERENTES -> les trois, cote a cote : les fondre
    # serait un mensonge
    ({**champs_de_source(), "source_color_primaries": "bt2020",
      "source_color_trc": "smpte2084", "source_colorspace": "bt2020nc"},
     True, "bt2020 · smpte2084 · bt2020nc"),
    # absent -> l'avertissement de `E2-1g`
    (champs_de_source(None), False, ajout_de_rush.COULEUR_NON_SIGNALEE),
    # PARTIEL -- la cible n'est ni la premiere ni la derniere cle du triplet :
    # un balayage qui s'arreterait a la premiere ne le verrait pas
    ({**champs_de_source(), "source_color_trc": None}, False,
     ajout_de_rush.COULEUR_NON_SIGNALEE),
    # partiel, cible en TETE du triplet
    ({**champs_de_source(), "source_color_primaries": None}, False,
     ajout_de_rush.COULEUR_NON_SIGNALEE),
    # partiel, cible en QUEUE du triplet
    ({**champs_de_source(), "source_colorspace": None}, False,
     ajout_de_rush.COULEUR_NON_SIGNALEE),
))
def test_les_TROIS_etats_du_triplet_colorimetrique(champs, signale, attendu):
    """`COLOR_TRIPLET_REPORT_KEYS` a trois cles, et une seule absente suffit.

    Les trois cibles de bord sont posees exprès (regle des fabriques, point 4)
    : un balayage qui sauterait la premiere ou la derniere cle du triplet
    resterait vert sur la cible du milieu seule.

    `color_range` **ne compte pas** : le coeur n'escalade que sur le triplet
    (« ProRes n'emet aucune signalisation de plage alors que DNxHR / H264 /
    HEVC emettent `tv` »), et la fabrique le laisse a `None` de bout en bout --
    ce qui rend le volet symetrique gratuit et reel.
    """
    texte, mesure = ajout_de_rush.texte_de_l_espace_couleur(champs)
    assert mesure is signale
    assert attendu in texte


# ===========================================================================
# `EPIC11-ARB-235` -- la valeur affichee est celle du PROBE
# ===========================================================================

def valeur_de_la_couleur(fiche, ascii_seul: bool = False) -> str:
    """La colonne de VALEUR de la ligne « Espace couleur », telle que rendue.

    Le libelle et la colonne sont LUS du produit (`LIBELLE_COULEUR`,
    `COLONNE_DE_VALEUR`) : recopier `25` ici ferait un banc qui mesure sa
    propre constante le jour ou le panneau deplacerait sa colonne.
    """
    libelle = ajout_de_rush.LIBELLE_COULEUR
    if ascii_seul:
        libelle = jetons.replier_ascii(libelle)
    for ligne in fiche.lignes(LARGEUR_DU_CARTOUCHE_DESSINE, ascii_seul):
        if ligne.startswith(libelle):
            return ligne[ajout_de_rush.COLONNE_DE_VALEUR:].rstrip()
    raise AssertionError(
        f"aucune ligne « {libelle} » dans le cartouche rendu")


@pytest.mark.skipif(not RUSH_REEL_SIGNALE.exists(),
                    reason="le rush reel signale est absent du clone")
def test_la_couleur_affichee_est_celle_du_PROBE(tmp_path):
    """Le panneau rend ce que `ffprobe` a MESURE, caractere pour caractere.

    **Ce que cette frontiere ferme, et ce que la fermeture d'`EPIC11-ARB-235`
    aurait laisse ouvert sans elle.** L'arbitrage a corrige trois maquettes qui
    ecrivaient `bt 709` ; le retrait des trois entrees de `DIVERGENCES_NOMMEES`
    fait passer le banc du rouge au vert, et un test qui passe au vert parce
    qu'une DONNEE a change ne prouve rien du chemin qui la porte. Ce qui se
    mesure ici est le chemin : `ffprobe` -> `source_fields` du coeur -> la
    ligne du cartouche.

    **Et il faut un rush du TERRAIN pour la mesurer.** Les quatre maquettes
    dessinent une source signalee ; `rush_bitch-4_chendj-mat.mp4` est le seul
    media de ce depot qui la porte parce qu'une VRAIE camera l'y a mise --
    `RUSH_REEL` signale aussi son triplet depuis `EPIC11-ARB-247`, mais il le
    tient d'un remux du depot, pas d'un tournage. `CLAUDE.md` : « une
    mesure de synthese mesure la synthese ; elle ne devient une mesure du
    produit que confrontee a un artefact de terrain ».

    **L'attendu est LU du probe, jamais ecrit ici.** Poser `"bt709"` en
    litteral ferait le test tautologique que la politique du depot nomme --
    il resterait vert si le panneau ecrivait sa propre chaine au lieu de lire
    la mesure. Le volet qui tue ce mutant-la est
    :func:`test_la_couleur_affichee_SUIT_le_probe_meme_sur_une_valeur_inedite`.
    """
    rangs.exiger_le_media(RUSH_REEL_SIGNALE)
    dossier = voisin.creer_projet(tmp_path, "projet_signale").chemin
    preparation = preparer_une_declaration(
        project_dir=dossier, video_path=RUSH_REEL_SIGNALE,
        logger=logging.getLogger("banc.declaration"))
    mesure = [preparation.record.source_fields[cle]
              for cle in source_confirmation.COLOR_TRIPLET_REPORT_KEYS]
    assert all(valeur is not None for valeur in mesure), (
        "ce rush est cense SIGNALER son triplet : sans cela le test mesure "
        f"l'absence et non la valeur ({mesure})")
    distinctes: list[str] = []
    for valeur in mesure:
        if str(valeur) not in distinctes:
            distinctes.append(str(valeur))
    attendu = rushes.SEPARATEUR.join(distinctes)

    fiche = ajout_de_rush.FicheDeDeclaration(preparation, rang=1)
    assert valeur_de_la_couleur(fiche) == attendu

    # Le volet de FORME, et c'est celui qu'`EPIC11-ARB-235` a paye : une valeur
    # de probe ne porte pas d'espace au milieu. Le separateur d'`ARB-150` en
    # porte, lui -- on mesure donc morceau par morceau, pas sur la chaine.
    for morceau in valeur_de_la_couleur(fiche).split(rushes.SEPARATEUR):
        assert " " not in morceau, (
            f"« {morceau} » porte une espace : une valeur de probe rendue "
            "ainsi est incomparable a ce que l'operateur lit dans `ffprobe` "
            "et a ce que le manifeste garde (`EPIC11-ARB-235`)")


@pytest.mark.parametrize("mesure,attendu", (
    # La valeur du terrain, celle des trois maquettes.
    ("bt709", "bt709"),
    # Une valeur INEDITE : elle n'est ecrite dans aucune maquette, aucun
    # generateur et aucune constante du depot. Un panneau qui recopierait une
    # chaine plutot que de lire la mesure ne peut pas la rendre.
    ("smpte240m", "smpte240m"),
    # Et une seconde, pour qu'un mutant ne puisse pas se sauver en apprenant
    # la premiere : le point 1 de la regle des fabriques vaut aussi pour les
    # valeurs d'un parametrage.
    ("bt470bg", "bt470bg"),
))
def test_la_couleur_affichee_SUIT_le_probe_meme_sur_une_valeur_inedite(
        mesure, attendu):
    """Le volet qui MORD : la ligne suit la mesure, elle ne la recopie pas.

    **Pourquoi il ne fait pas double emploi avec
    :func:`test_les_TROIS_etats_du_triplet_colorimetrique`.** Celui-la appelle
    `texte_de_l_espace_couleur` directement ; celui-ci passe par
    `FicheDeDeclaration.lignes`, c'est-a-dire par le CABLAGE. Un litteral pose
    dans le constructeur du cartouche -- exactement la faute que les maquettes
    ont commise pendant trois etats -- survivrait au premier et meurt ici.
    C'est le finding `R10` de la revue du 2026-08-31, applique a une autre
    ligne : « deux mutants du CABLAGE survivaient a un test qui appelait la
    peinture directement ».
    """
    fiche = ajout_de_rush.FicheDeDeclaration(preparee(couleur=mesure), rang=4)
    assert valeur_de_la_couleur(fiche) == attendu


def test_aucune_maquette_du_panneau_ne_porte_la_forme_avec_espace():
    """Le volet NEGATIF d'`EPIC11-ARB-235`, sur les maquettes elles-memes.

    **Aucun test positif ne verrait la reintroduction.** Les trois maquettes
    corrigees rendent aujourd'hui la meme chose que le produit, donc
    `test_les_quatre_etats_rendent_leur_maquette_LIGNE_A_LIGNE` est vert -- et
    il le resterait si quelqu'un remettait `bt 709` **des deux cotes**, ce qui
    est precisement ce qu'une correction portee au `.txt` plutot qu'au
    generateur produirait a la premiere regeneration suivante.

    La mesure est STRUCTURELLE et non litterale : elle n'attrape pas seulement
    `bt 709` mais toute valeur de probe respacee -- `bt 2020`, `smpte 2084`.
    Un banc qui grepperait la chaine exacte serait muet sur la suivante.

    L'etat `E2-1g` est le contre-exemple qui rend la mesure honnete : sa ligne
    de couleur porte une PHRASE (`COULEUR_NON_SIGNALEE`), pleine d'espaces et
    legitimement. Elle est reconnue par la constante du produit, jamais par sa
    place dans la liste.
    """
    vus = 0
    for nom in sorted(ETATS):
        for ligne in corps_du_cartouche(nom):
            if not ligne.startswith(ajout_de_rush.LIBELLE_COULEUR):
                continue
            vus += 1
            valeur = ligne[ajout_de_rush.COLONNE_DE_VALEUR:].rstrip()
            if ajout_de_rush.COULEUR_NON_SIGNALEE in valeur:
                continue
            for morceau in valeur.split(rushes.SEPARATEUR):
                assert " " not in morceau, (
                    f"{nom} dessine « {morceau} » : une valeur de probe ne "
                    "porte pas d'espace au milieu (`EPIC11-ARB-235`). Une "
                    "maquette se corrige dans son GENERATEUR "
                    "(`_gen_extraction.LIGNE_DE_COULEUR_SIGNALEE`), jamais "
                    "dans le `.txt` rendu.")
    assert vus == len(ETATS), (
        f"{vus} lignes d'espace couleur pour {len(ETATS)} maquettes : une "
        "maquette sans ligne de couleur rendrait ce banc vert sans rien "
        "mesurer")


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_assertion_REC709_n_apparait_QUE_sur_la_colorimetrie_inconnue(
        ascii_seul):
    """`EPIC11-ARB-149`, note 1 : une ANNONCE a la place d'un choix unique.

    Et elle est **hors du cartouche**, ce que mesure le test de composition
    plus bas : le cadre s'appelle « À déclarer », or `bt709` n'est jamais
    ecrit au manifeste. Ici on mesure les deux bouts -- elle est la quand le
    triplet manque, absente quand il est signale.
    """
    signalee = ajout_de_rush.FicheDeDeclaration(preparee(), rang=4)
    absente = ajout_de_rush.FicheDeDeclaration(preparee(couleur=None), rang=4)
    assert signalee.assertion(ascii_seul) is None
    ligne = absente.assertion(ascii_seul)
    assert ligne is not None
    assert jetons.glyphes(ascii_seul)["substitute"] in ligne
    assert "Rec. 709" in ligne or "Rec. 709" in jetons.replier_ascii(ligne)
    # Elle n'est PAS dans le cartouche : c'est la moitie de l'arbitrage.
    corps = "\n".join(absente.lignes(LARGEUR_DU_CARTOUCHE_DESSINE, ascii_seul))
    assert "Rec. 709" not in corps
    assert ajout_de_rush.ASSERTION_REC709 not in corps


# ===========================================================================
# L'OMISSION d'un champ non mesure (`DESIGN.md` §3), au MILIEU et en QUEUE
# ===========================================================================

def libelles(fiche) -> list[str]:
    """Les libelles des lignes du cartouche, dans l'ordre rendu."""
    rendus = []
    for ligne in fiche.lignes(LARGEUR_DU_CARTOUCHE_DESSINE):
        tete = ligne[:ajout_de_rush.COLONNE_DE_VALEUR].strip()
        if tete:
            rendus.append(tete)
    return rendus


def test_les_lignes_du_cartouche_sont_dans_l_ORDRE_de_la_maquette():
    """La collection de ce banc, nommee : huit libelles DISTINGUABLES.

    Sans cette mesure, les tests d'omission ci-dessous pourraient etre verts
    sur une liste reordonnee -- « au milieu » et « en queue » ne veulent plus
    rien dire si l'ordre n'est pas tenu.
    """
    assert libelles(ajout_de_rush.FicheDeDeclaration(preparee())) == [
        ajout_de_rush.LIBELLE_NOM, ajout_de_rush.LIBELLE_CHEMIN,
        ajout_de_rush.LIBELLE_CODEC, ajout_de_rush.LIBELLE_CADENCE,
        ajout_de_rush.LIBELLE_RESOLUTION, ajout_de_rush.LIBELLE_TIMECODE,
        ajout_de_rush.LIBELLE_COULEUR]


def test_le_CODEC_absent_retire_sa_ligne_du_MILIEU():
    """`DESIGN.md` §3 : un champ non mesure s'OMET, il ne rend pas `unknown`.

    La cible est au MILIEU de la liste (rang 2 sur 7) : une omission qui
    laisserait une ligne vide, ou qui retirerait la mauvaise, se verrait sur
    l'ordre des libelles restants -- pas sur un cardinal.
    """
    fiche = ajout_de_rush.FicheDeDeclaration(preparee(codec=None, pixels=None))
    restants = libelles(fiche)
    assert ajout_de_rush.LIBELLE_CODEC not in restants
    assert restants == [ajout_de_rush.LIBELLE_NOM,
                        ajout_de_rush.LIBELLE_CHEMIN,
                        ajout_de_rush.LIBELLE_CADENCE,
                        ajout_de_rush.LIBELLE_RESOLUTION,
                        ajout_de_rush.LIBELLE_TIMECODE,
                        ajout_de_rush.LIBELLE_COULEUR]


def test_un_SEUL_des_deux_champs_du_codec_garde_la_ligne():
    """Le cas intermediaire, qu'aucune maquette ne dessine et que le terrain
    produit : `pix_fmt` sans `codec_name` ou l'inverse.

    Retirer la ligne entiere pour un champ manquant perdrait une valeur
    mesuree ; la garder avec un `unknown` en inventerait une.
    """
    fiche = ajout_de_rush.FicheDeDeclaration(preparee(pixels=None))
    ligne = [l for l in fiche.lignes(LARGEUR_DU_CARTOUCHE_DESSINE)
             if l.startswith(ajout_de_rush.LIBELLE_CODEC)]
    assert len(ligne) == 1
    assert "prores_ks" in ligne[0]
    assert "unknown" not in ligne[0]
    assert "None" not in ligne[0]


def test_le_TIMECODE_absent_retire_sa_ligne_de_QUEUE():
    """Meme regle, cible en QUEUE -- le point 4 des fabriques.

    Une cible au milieu demasque un `find` fautif ; elle ne demasque pas un
    balayage tronque. Le timecode est l'avant-derniere ligne, et il est
    reellement absent sur le rush REEL du depot : ce n'est pas un cas de
    synthese.
    """
    fiche = ajout_de_rush.FicheDeDeclaration(preparee(timecode=None))
    restants = libelles(fiche)
    assert ajout_de_rush.LIBELLE_TIMECODE not in restants
    assert restants[-1] == ajout_de_rush.LIBELLE_COULEUR, (
        "la ligne de queue a saute avec celle qu'on retirait")
    assert restants[0] == ajout_de_rush.LIBELLE_NOM, (
        "la ligne de tete a saute avec celle qu'on retirait")


# ===========================================================================
# Les TROIS issues (`EPIC11-ARB-7`, `-45`, `-126`)
# ===========================================================================

def test_les_TROIS_issues_et_leur_ORDRE():
    """L'ordre compte autant que l'ensemble : la maquette porte l'action
    principale en premier, ce qui rend visible le deplacement du curseur."""
    choix = ajout_de_rush.issues_de_la_declaration()
    assert [issue.cle for issue in choix.issues] == [
        ajout_de_rush.CLE_DECLARER, ajout_de_rush.CLE_DESIGNER,
        ajout_de_rush.CLE_ANNULER]
    assert [issue.ecrit for issue in choix.issues] == [True, False, False]


def test_le_curseur_ne_vise_JAMAIS_l_issue_qui_ECRIT():
    """`EPIC11-ARB-7` tenu par `EPIC11-ARB-45`, et mesure sur `ecrit`.

    Mesurer l'invariant plutot que la cle est delibere : il survivrait a un
    renommage. Le rang de l'issue principale ne bouge pas pour autant -- c'est
    le curseur qui se place, pas la liste qui se reordonne.
    """
    choix = ajout_de_rush.issues_de_la_declaration()
    assert choix.issues[choix.curseur].ecrit is False
    assert choix.issues[choix.curseur].cle == ajout_de_rush.CLE_DESIGNER
    assert choix.action_qui_ecrit.cle == ajout_de_rush.CLE_DECLARER
    assert choix.retenue is None


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_trois_issues_sont_reellement_ATTEIGNABLES(ascii_seul):
    """Une issue nommee au modele et absente du rendu est intypable."""
    choix = ajout_de_rush.issues_de_la_declaration()
    # **Le repli passe par `jetons.ajuster`, comme dans le produit.**
    # `ChoixExclusif.rendu` ne replie que le GLYPHE de curseur ; les libelles
    # sont replies au dessin, par `execution.bloc_peint`. Un banc qui lirait
    # `rendu()` seul mesurerait un chemin que l'ecran ne prend pas -- le piege
    # exact que `test_journal_du_produit` raconte.
    rendu = "\n".join(jetons.ajuster(ligne, 72, ascii_seul)
                      for ligne in choix.rendu(ascii_seul))
    for issue in choix.issues:
        libelle = (jetons.replier_ascii(issue.libelle) if ascii_seul
                   else issue.libelle)
        assert libelle in rendu, issue.cle


# ===========================================================================
# Le rang du rush dans le projet, a CHAQUE BORD de la liste
# ===========================================================================

@pytest.mark.parametrize("rang,attendu", ((1, "1er"), (2, "2e"), (4, "4e"),
                                          (11, "11e"), (21, "21e")))
def test_l_ordinal_du_rang(rang, attendu):
    """`1er` et non `1e` -- la seule irregularite du francais, et elle tombe
    sur le PREMIER rush d'un projet, c'est-a-dire sur le cas nominal d'un
    projet neuf."""
    assert ajout_de_rush.rang_ordinal(rang) == attendu


def test_sans_rang_la_ligne_d_etat_ne_l_INVENTE_pas():
    """Un rang absent retire sa moitie de phrase plutot que d'ecrire `0e`."""
    etat = ajout_de_rush.FicheDeDeclaration(preparee(), rang=None).etat(
        LARGEUR_DU_CARTOUCHE_DESSINE)
    assert "rush du projet" not in etat
    assert ajout_de_rush.RIEN_ECRIT_ENCORE in etat
    assert "0e" not in etat and "None" not in etat


# ===========================================================================
# Le repli ASCII et la largeur -- les deux regimes, sur plusieurs largeurs
# ===========================================================================

@pytest.mark.parametrize("largeur", (40, 52, 68, 72, 120))
@pytest.mark.parametrize("nom", sorted(ETATS))
def test_aucune_ligne_du_cartouche_ne_DEBORDE(largeur, nom):
    """Une ligne plus large que le cartouche est coupee EN SILENCE par
    `textual`, et c'est le finding `I1` pris par la largeur plutot que par la
    hauteur. La ligne de cadence est la plus exposee : elle porte une mention
    calee a droite, donc elle est la seule dont la largeur depend de deux
    textes a la fois."""
    for ligne in fiche_de(nom).lignes(largeur):
        assert jetons.colonnes(ligne) <= largeur, (
            f"{jetons.colonnes(ligne)} colonnes pour {largeur} : {ligne!r}")


@pytest.mark.parametrize("nom", sorted(ETATS))
def test_le_repli_ASCII_ne_laisse_AUCUN_caractere_hors_ASCII(nom):
    """`--ascii` sert des consoles qui ne rendent pas l'UTF-8 : un seul
    caractere oublie y devient un point d'interrogation, au milieu d'un panneau
    de decision."""
    fiche = fiche_de(nom)
    montre = tout_ce_que_l_ecran_montre(fiche, LARGEUR_DU_CARTOUCHE_DESSINE,
                                        ascii_seul=True)
    fautifs = sorted({c for c in montre if ord(c) > 127})
    assert fautifs == [], fautifs


def test_le_repli_ASCII_change_REELLEMENT_quelque_chose():
    """Volet symetrique : un repli qui ne replierait rien passerait le test
    ci-dessus sur un texte deja ASCII. Les quatre etats portent tous des
    accents, un `·` et un `×` ; le repli doit donc differer du nominal."""
    fiche = fiche_de("E2-1e-declaration-confirmation.txt")
    assert (tout_ce_que_l_ecran_montre(fiche, ascii_seul=True)
            != tout_ce_que_l_ecran_montre(fiche, ascii_seul=False))


# ===========================================================================
# L'ECRAN MONTE -- les deux temps, et le disque mesure entre les deux
# ===========================================================================

def empreinte_du_manifeste(dossier: Path) -> tuple:
    """Inode, taille et `st_mtime_ns` du `project.json`, plus son contenu.

    C'est la mesure de l'AC 1.8, rejouee **cote ecran** : le coeur a sa propre
    frontiere (`C1_preparer_ne_touche_AUCUN_octet`) et elle ne dit rien du
    chemin que l'ecran emprunte pour l'atteindre. Un ecran qui appellerait
    `declarer_un_rush` -- la composition des deux temps -- ecrirait avant de
    montrer, et la frontiere du coeur resterait verte.
    """
    manifeste = dossier / MANIFEST_FILENAME
    etat = manifeste.stat()
    return (etat.st_ino, etat.st_size, etat.st_mtime_ns,
            manifeste.read_text(encoding="utf-8"))


def double_de_preparation(cible_attendue=None, refus: str | None = None):
    """Un temps 1 de banc : il rend une preparation, ou il REFUSE.

    Le vrai temps 1 paie un `ffprobe` et exige un fichier lisible ; le doubler
    permet de mesurer ce que l'ECRAN fait de la preparation, y compris dans
    l'etat de refus dont l'ecran (`E2-1f`) n'existe pas encore. Le chemin reel
    est mesure a part, sur le rush du depot.
    """
    vues = []

    def preparer(cible: Path):
        vues.append(Path(cible))
        if refus is not None:
            raise RefusDeDeclaration(
                "deja declare", motif=refus,
                # Les issues sont LUES dans la table publiee du coeur, jamais
                # recopiees : c'est le motif exact qui l'a fait publier.
                issues=ISSUES_PAR_MOTIF[refus],
                source_name=Path(cible).name)
        return preparee(chemin=str(cible))

    preparer.vues = vues
    return preparer


def double_d_ecriture(dossier: Path, rush_id: str, rang: int):
    """Un temps 2 de banc qui ecrit VRAIMENT, au rang demande.

    Il **rend** le `rush_id` -- c'est ce que `_viser_le_rush_declare` attend, et
    c'est ce que `DeclarationDeRush.rush_id` rend dans le produit.
    """
    ecrites = []

    def ecrire(preparation) -> str:
        ecrites.append(preparation)
        voisin.ecrire_le_rush(dossier, rush_id, rang)(
            Path(preparation.source_path))
        return rush_id

    ecrire.ecrites = ecrites
    return ecrire


def au_panneau(banc, monkeypatch, tmp_path, dossier, preparer, ecrire=None,
               depart: str = voisin.RUSHES[0], suite=None,
               sur_les_videos=None):
    """Monter `E2-1`, designer la video du milieu, jouer `suite` sur le panneau.

    Le parcours est celui du CLAVIER, jamais un appel direct : c'est le piege
    que `test_journal_du_produit.py` raconte -- « le banc mesurait un parcours
    qui n'est pas celui du produit, sur le seul point ou les deux different ».

    **Tout se joue dans UNE seule session `run_test`**, et ce n'est pas un
    detail de confort : remonter le meme ecran dans une seconde boucle
    `asyncio` casse les verrous que `textual` lui a attaches, et l'erreur
    remonte en « bound to a different event loop » -- c'est-a-dire loin de la
    ligne fautive. `suite` recoit `(pilote, panneau)` et rend ce que le test
    veut asserter.
    """
    videos = voisin.dossier_des_videos(tmp_path)
    if sur_les_videos is not None:
        # **Apres la fabrique, jamais avant** : elle reecrit ses trois fichiers,
        # donc une vraie video posee en amont serait remplacee par ses vingt
        # octets de synthese -- et le test mesurerait le refus au lieu du
        # chemin nominal. Paye une fois, ici.
        sur_les_videos(videos)
    monkeypatch.chdir(videos)
    ecran = amont.EcranRushes(dossier, preparer=preparer, ecrire=ecrire)
    boite: dict = {}

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        ecran.liste.viser(depart)
        assert ecran.liste.courant.rush_id == depart
        boite["avant"] = empreinte_du_manifeste(dossier)
        await voisin.designer_la_video(pilote, ecran)
        boite["apres_le_temps_1"] = empreinte_du_manifeste(dossier)
        boite["dessus"] = pilote.app.screen
        if suite is not None:
            boite["suite"] = await suite(pilote, boite["dessus"])
        return boite

    boite = banc(voisin.coque(ecran), scenario)
    return ecran, boite


def test_designer_un_fichier_monte_le_PANNEAU_et_n_ecrit_RIEN(
        tmp_path, banc, monkeypatch):
    """AC 3.3 et `EPIC11-ARB-4` : « obligatoire pour toute commande qui ecrit ».

    Le defaut que ce test ferme est celui que le lot precedent avait laisse
    ouvert des deux cotes : `Ajouter un rush` menait a un ecran « pas encore »,
    et un cablage naif du rappel aurait ecrit **sans rien montrer**. La mesure
    porte sur l'inode, la taille, `st_mtime_ns` **et** le contenu : un
    remplacement atomique change l'inode sans changer la taille, et une
    reecriture identique change `mtime` sans changer le contenu.
    """
    dossier = voisin.projet(tmp_path)
    ecran, boite = au_panneau(banc, monkeypatch, tmp_path, dossier,
                              double_de_preparation())
    assert isinstance(boite["dessus"], amont.EcranDeclaration)
    assert boite["apres_le_temps_1"] == boite["avant"], (
        "le temps 1 a touche le manifeste : le panneau chiffre n'a plus rien "
        "a proposer de renoncer")


def test_le_panneau_est_monte_sur_la_CIBLE_designee(tmp_path, banc,
                                                    monkeypatch):
    """La preparation porte le fichier du MILIEU, pas le premier du dossier.

    C'est le mode de panne de `_find_lot` en 5.7, rejoue ici : un ecran qui
    prendrait la premiere entree de l'explorateur montrerait un panneau
    plausible sur le mauvais fichier.
    """
    dossier = voisin.projet(tmp_path)
    preparer = double_de_preparation()
    ecran, boite = au_panneau(banc, monkeypatch, tmp_path, dossier, preparer)
    assert [chemin.name for chemin in preparer.vues] == [voisin.VIDEO_CIBLE]
    assert boite["dessus"].fiche.preparee.source_path.endswith(
        voisin.VIDEO_CIBLE)


@pytest.mark.parametrize("rang,depart", (
    (0, voisin.RUSHES[0]),                  # en TETE : la liste se decale
    (2, voisin.RUSHES[1]),                  # au MILIEU
    (len(voisin.RUSHES), voisin.RUSHES[-1]),  # en QUEUE : rien ne se decale
))
def test_VALIDER_ecrit_puis_pose_le_curseur_sur_le_rush_neuf(
        tmp_path, banc, monkeypatch, rang, depart):
    """Le temps 2, et l'AC 3.7 -- a CHAQUE BORD (regle des fabriques, point 4).

    Un rush insere AVANT le curseur decale toute la liste d'un cran ; un rush
    insere en queue ne decale rien, et c'est le cas ou l'oubli du `viser` est
    INVISIBLE. Les trois sont mesures, sur la liste que le code parcourt.
    """
    dossier = voisin.projet(tmp_path)
    ecrire = double_d_ecriture(dossier, "rush_zz_neuf", rang)

    async def valider(pilote, panneau_):
        panneau_.choix.viser(ajout_de_rush.CLE_DECLARER)
        panneau_.traiter("enter")
        await pilote.pause()
        return empreinte_du_manifeste(dossier)

    ecran, boite = au_panneau(banc, monkeypatch, tmp_path, dossier,
                              double_de_preparation(), ecrire, depart=depart,
                              suite=valider)
    apres = boite["suite"]
    assert len(ecrire.ecrites) == 1, "une validation, une ecriture"
    assert apres != boite["apres_le_temps_1"], "rien n'a ete ecrit"
    assert ecran.liste.courant.rush_id == "rush_zz_neuf", (
        f"curseur sur {ecran.liste.courant.rush_id} apres une insertion au "
        f"rang {rang}")


@pytest.mark.parametrize("cle", (ajout_de_rush.CLE_ANNULER,
                                 ajout_de_rush.CLE_DESIGNER))
def test_les_DEUX_issues_qui_n_ecrivent_pas_n_ecrivent_RIEN(
        tmp_path, banc, monkeypatch, cle):
    """Le volet symetrique du test precedent, et il porte sur le DISQUE.

    `Annuler` sort, `Désigner un autre fichier` rouvre l'explorateur : les deux
    sont des suites, aucune n'est une ecriture. Le mesurer sur l'empreinte du
    manifeste plutot que sur un compteur d'appels est delibere -- un rappel
    d'ecriture contourne ne se verrait pas sur un compteur.
    """
    dossier = voisin.projet(tmp_path)
    ecrire = double_d_ecriture(dossier, "rush_zz_neuf", 0)

    async def choisir(pilote, panneau_):
        panneau_.choix.viser(cle)
        panneau_.traiter("enter")
        await pilote.pause()
        return empreinte_du_manifeste(dossier)

    ecran, boite = au_panneau(banc, monkeypatch, tmp_path, dossier,
                              double_de_preparation(), ecrire, suite=choisir)
    apres = boite["suite"]
    assert ecrire.ecrites == [], f"{cle} a ecrit"
    assert apres == boite["apres_le_temps_1"]
    if cle == ajout_de_rush.CLE_DESIGNER:
        assert ecran.zone == amont.ZONE_EXPLORATEUR, (
            "« Désigner un autre fichier » ne mene nulle part : c'est le "
            "defaut du lot N3, une issue lue puis jetee")
        assert ecran.mode == voisin.amont.rushes.MODE_DESIGNER
    else:
        assert ecran.zone == amont.ZONE_LISTE


@pytest.mark.parametrize("motif", [m for m in MOTIFS_DE_REFUS
                                   if m != MOTIF_RUSH_DEJA_DECLARE])
def test_le_REFUS_du_coeur_ne_se_TAIT_pas(motif, tmp_path, banc, monkeypatch):
    """Le refus se DIT, et c'est le defaut `K1.1` pris par son autre bout.

    L'operateur designe une vraie video, le coeur la refuse pour un motif
    nomme, et l'ecran ne dirait rien. Le motif du coeur voyage donc verbatim
    jusqu'a l'ecran qui nomme le manque -- et **aucun octet n'est ecrit** au
    passage.

    **Il porte desormais les QUATRE motifs, et plus celui du conflit.**
    Jusqu'au 2026-09-05 ce test jouait `MOTIF_RUSH_DEJA_DECLARE`, faute d'ecran
    a lui opposer : `E2-1f` n'etait pas construit (`EPIC11-ARB-231`,
    `EPIC11-ARB-144`). Il l'est, et ce motif-la monte maintenant
    `atelier_extraction.EcranRefusDeConflit` -- mesure par
    `test_ecran_E2_1f_refus_de_conflit.py`, avec le volet negatif symetrique de
    celui-ci (« les quatre autres ne montent PAS cet ecran »).

    Le passer en `parametrize` sur les quatre plutot que d'en choisir un est le
    point 4 de la regle des fabriques : la cible est en TETE de
    `MOTIFS_DE_REFUS` comme au milieu, et un motif ajoute demain entre dans la
    mesure tout seul.
    """
    dossier = voisin.projet(tmp_path)
    ecrire = double_d_ecriture(dossier, "rush_zz_neuf", 0)
    ecran, boite = au_panneau(
        banc, monkeypatch, tmp_path, dossier,
        double_de_preparation(refus=motif), ecrire)
    dessus = boite["dessus"]
    assert isinstance(dessus, EcranPasEncore), type(dessus)
    dit = "\n".join(dessus.lignes())
    assert motif in dit, dit
    assert voisin.VIDEO_CIBLE in dit, dit
    assert ecrire.ecrites == []
    assert boite["apres_le_temps_1"] == boite["avant"]


def test_sans_rappel_de_PREPARATION_l_ecran_NOMME_ce_qui_manque(
        tmp_path, banc, monkeypatch):
    """AC 3.2 : `ce_qui_manque_pour_ajouter` reste ATTEIGNABLE sans rappel.

    Le retirer rouvrirait le silence du 2026-08-30. Ce test est le volet
    symetrique du cablage : le produit injecte les deux temps, donc plus
    personne ne passe par ce chemin -- et c'est precisement quand un chemin
    cesse d'etre parcouru qu'il faut le mesurer.
    """
    dossier = voisin.projet(tmp_path)
    monkeypatch.chdir(voisin.dossier_des_videos(tmp_path))
    ecran = amont.EcranRushes(dossier)
    boite: dict = {}

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        await voisin.designer_la_video(pilote, ecran)
        boite["dessus"] = pilote.app.screen

    banc(voisin.coque(ecran), scenario)
    assert isinstance(boite["dessus"], EcranPasEncore)
    assert voisin.VIDEO_CIBLE in "\n".join(boite["dessus"].lignes())


def test_le_rang_annonce_est_celui_de_la_LISTE_plus_un(tmp_path, banc,
                                                       monkeypatch):
    """`4e rush du projet` -- un cardinal, pas une constante.

    La fabrique du banc voisin porte CINQ rushes ; le rush declare sera donc le
    sixieme. Un rang ecrit en dur passerait sur la maquette et mentirait sur
    tout autre projet.
    """
    dossier = voisin.projet(tmp_path)
    _ecran, boite = au_panneau(banc, monkeypatch, tmp_path, dossier,
                               double_de_preparation())
    fiche = boite["dessus"].fiche
    assert fiche.rang == len(voisin.RUSHES) + 1
    # La ligne d'etat est lue sur un cartouche assez LARGE pour que le chemin
    # temporaire du banc tienne : sinon c'est la coupe du chemin qui prend la
    # place du rang, ce qui est le comportement voulu et pas ce qu'on mesure
    # ici. La priorite entre les trois mesures est testee a part.
    assert "6e rush du projet" in fiche.etat(400)


def test_AUCUN_nom_n_est_editable_sur_le_panneau(tmp_path, banc, monkeypatch):
    """AC 3.4 et `EPIC11-ARB-141` : `Tab` n'a plus de destination.

    Mesure sur les deux bouts -- la touche ne consomme rien, et **aucun widget
    de nom n'est monte**. Le second volet compte : un modele de noms vide qui
    monterait quand meme sa ligne laisserait un champ ouvert sur un ecran ou
    l'AC dit qu'il n'y en a pas.
    """
    dossier = voisin.projet(tmp_path)

    async def taper(pilote, panneau_):
        avant = panneau_.etat()
        assert panneau_.traiter("tab") is False
        panneau_.rafraichir()
        return (avant, panneau_.etat(), len(panneau_.noms),
                list(panneau_._lignes_de_noms))

    _ecran, boite = au_panneau(banc, monkeypatch, tmp_path, dossier,
                               double_de_preparation(), suite=taper)
    avant, apres, combien, widgets = boite["suite"]
    assert avant == apres
    assert combien == 0
    assert widgets == []


def test_l_assertion_REC709_n_occupe_AUCUNE_ligne_hors_de_son_etat(
        tmp_path, banc, monkeypatch):
    """Un `Static` vide garde sa ligne : la geometrie nominale y passerait.

    C'est le geste de `_refus_du_nom` sur `EcranChiffre`, repris ici, et il se
    mesure sur `display` -- l'attribut que `textual` lit -- plutot que sur le
    texte du widget.
    """
    dossier = voisin.projet(tmp_path)

    def monter(preparation):
        ecran = amont.EcranDeclaration(preparation, rang=4)

        async def scenario(pilote):
            pilote.app.descendre(ecran)
            await pilote.pause()
            ecran.rafraichir()
            await pilote.pause()
            return ecran._assertion.display, ecran._blanc_d_assertion.display

        return banc(voisin.coque(ecran), scenario)

    assert monter(preparee()) == (False, False)
    assert monter(preparee(couleur=None)) == (True, True)


# ===========================================================================
# Le rush REEL du depot -- le vrai coeur, le vrai ffprobe
# ===========================================================================

@pytest.mark.skipif(not RUSH_REEL.exists(),
                    reason="le rush reel du depot est absent du clone")
def test_le_TEMPS_1_du_VRAI_coeur_alimente_le_panneau(tmp_path, banc):
    """Le banc de synthese mesure la synthese ; celui-ci mesure le produit.

    `CLAUDE.md` : « une fixture de synthese peut fabriquer une panne que le
    terrain n'a PAS », et son symetrique a coute davantage. Le rush du depot
    est un H.264 **sans timecode de depart** : il exerce donc, tout seul,
    l'omission de la ligne de queue -- un chemin que la fabrique ne prend que
    sur commande.

    **Le drapeau colorimetrique VARIE ici, dans les deux sens** (regle des
    drapeaux de `CLAUDE.md`, et c'est `EPIC11-ARB-247` qui l'a rendue
    necessaire). Avant la normalisation, ce test n'avait que le volet
    « absente », et il le tenait d'un fichier qui se trouvait n'etre pas
    tague : un drapeau qu'on subit ne mesure qu'un chemin, et celui-la a
    bascule sans qu'une ligne du banc ait bouge. Les deux etats se lisent
    desormais sur le MEME media reel -- declare tel qu'il est au depot,
    puis prive de sa declaration.
    """
    rangs.exiger_le_media(RUSH_REEL)
    preparation = preparee_du_terrain(tmp_path)
    fiche = ajout_de_rush.FicheDeDeclaration(preparation, rang=1)
    lignes = fiche.lignes(LARGEUR_DU_CARTOUCHE_DESSINE)
    rendus = libelles(fiche)
    assert ajout_de_rush.LIBELLE_TIMECODE not in rendus, (
        "le rush reel ne declare aucun timecode de depart : la ligne s'omet")
    # Volet SIGNALE : le rush du depot declare son triplet depuis
    # `EPIC11-ARB-247`. L'attendu est LU du probe, jamais ecrit ici -- un
    # litteral `bt709` rendrait le test tautologique.
    mesure = {preparation.record.source_fields[cle]
              for cle in source_confirmation.COLOR_TRIPLET_REPORT_KEYS}
    assert None not in mesure, (
        "le rush du depot est cense DECLARER son triplet depuis "
        f"`EPIC11-ARB-247` : {sorted(map(str, mesure))}")
    assert ajout_de_rush.COULEUR_NON_SIGNALEE not in "\n".join(lignes)
    for valeur in mesure:
        assert str(valeur) in "\n".join(lignes)
    # Le cardinal, lui, EST corrobore sur ce fichier : le panneau le porte.
    assert preparation.cardinal_de_frames is not None
    assert ajout_de_rush.cardinal_lisible(
        preparation.cardinal_de_frames) in "\n".join(lignes)


@requiert_ffmpeg
@pytest.mark.skipif(not RUSH_REEL.exists(),
                    reason="le rush reel du depot est absent du clone")
def test_le_TEMPS_1_du_VRAI_coeur_sur_une_source_SANS_colorimetrie(
        tmp_path, banc):
    """Volet symetrique du precedent : l'etat `E2-1g`, sur un media REEL.

    C'est l'autre sens du drapeau. Le media est le meme -- meme flux H.264,
    memes pixels --, seule sa declaration a ete retiree : ce que le panneau
    change ici ne peut donc venir que d'elle.
    """
    rangs.exiger_le_media(RUSH_REEL)
    preparation = preparee_du_terrain_sans_triplet(tmp_path)
    fiche = ajout_de_rush.FicheDeDeclaration(preparation, rang=1)
    lignes = fiche.lignes(LARGEUR_DU_CARTOUCHE_DESSINE)
    assert all(preparation.record.source_fields[cle] is None
               for cle in source_confirmation.COLOR_TRIPLET_REPORT_KEYS), (
        "la fabrique est censee avoir RETIRE le triplet")
    assert ajout_de_rush.COULEUR_NON_SIGNALEE in "\n".join(lignes), (
        "sans triplet, le cartouche porte l'etat E2-1g")
    assert fiche.assertion() is not None
    # La ligne d'etat porte la mesure de la COLORIMETRIE, pas le rang : sur ce
    # fichier-la c'est elle qui prime, et c'est l'ordre que `etat` documente.
    assert (ajout_de_rush.ETAT_COULEUR_ABSENTE
            in fiche.etat(LARGEUR_DU_CARTOUCHE_DESSINE))
    assert "rush du projet" not in fiche.etat(LARGEUR_DU_CARTOUCHE_DESSINE)


def test_l_ordre_des_TROIS_mesures_de_la_ligne_d_etat():
    """Aucune maquette ne tranche le cas ou DEUX mesures s'appliquent.

    Le choix est ecrit dans `FicheDeDeclaration.etat` -- la colorimetrie passe
    devant la coupe du chemin, parce qu'elle porte sur ce que le manifeste
    ECRIT tandis que la coupe ne porte que sur le rendu de cet ecran-ci. Il est
    mesure ici pour qu'il ne se perde pas : un ordre implicite se re-casse au
    prochain etat ajoute, et personne ne le verrait.
    """
    court = LARGEUR_DU_CARTOUCHE_DESSINE
    les_deux = ajout_de_rush.FicheDeDeclaration(
        preparee(chemin=CHEMIN_QUI_COUPE, couleur=None), rang=4)
    assert les_deux.chemin_coupe(court) is True, "le cas mixte n'est pas monte"
    assert les_deux.colorimetrie_signalee() is False
    assert ajout_de_rush.ETAT_COULEUR_ABSENTE in les_deux.etat(court)
    assert "colonnes" not in les_deux.etat(court)
    # Et le rang cede aux deux autres, dans les deux sens.
    assert "rush du projet" not in les_deux.etat(court)
    coupe_seule = ajout_de_rush.FicheDeDeclaration(
        preparee(chemin=CHEMIN_QUI_COUPE), rang=4)
    assert "115 colonnes" in coupe_seule.etat(court)
    assert "rush du projet" not in coupe_seule.etat(court)


def test_la_ligne_d_etat_et_le_CORPS_mesurent_la_MEME_largeur(tmp_path, banc,
                                                              monkeypatch):
    """Le couplage que `EcranDeclaration._cartouche` existe pour tenir.

    Deux largeurs differentes feraient annoncer une coupe que le corps n'a pas
    faite -- ou l'inverse, un corps coupe sous une ligne d'etat muette. C'est
    la meme famille que le finding `I1` : un ecart de geometrie qui ne leve
    rien et ne se voit qu'a l'oeil, sur un terminal.
    """
    dossier = voisin.projet(tmp_path)

    async def relever(pilote, panneau_):
        panneau_.rafraichir()
        await pilote.pause()
        return (panneau_._cartouche(), panneau_.etat(),
                panneau_.lignes_du_panneau())

    _ecran, boite = au_panneau(banc, monkeypatch, tmp_path, dossier,
                               double_de_preparation(), suite=relever)
    largeur, etat, lignes = boite["suite"]
    assert largeur == jetons.largeur_de_cartouche(80)
    fiche = boite["dessus"].fiche
    assert etat == fiche.etat(largeur)
    assert lignes == fiche.lignes(largeur)
    annonce_une_coupe = "colonnes, coup" in etat
    assert annonce_une_coupe == fiche.chemin_coupe(largeur), (
        "la ligne d'etat et le corps ne s'accordent pas sur la coupe")


@pytest.mark.skipif(not RUSH_REEL.exists(),
                    reason="le rush reel du depot est absent du clone")
def test_les_DEUX_TEMPS_sur_le_VRAI_coeur_du_bout_en_bout(tmp_path, banc,
                                                          monkeypatch):
    """L'integration : vrai `ffprobe`, vrai coeur, vrai manifeste.

    **Un test d'integration contre le vrai producteur ne suffit pas s'il
    n'asserte pas** (`EPIC5-ARB-39`, story 5.8 : les deux tests ecrits
    survivaient aux trois mutations qu'ils devaient attraper). Celui-ci asserte
    sur les trois familles que le decoupage engage :

    * le manifeste est INTACT apres le temps 1 -- inode, taille, `mtime_ns`,
      contenu ;
    * il porte le rush apres le temps 2, sous l'identifiant que le coeur a
      derive -- jamais un identifiant recalcule ici ;
    * le curseur de la liste s'y pose (AC 3.7).
    """
    rangs.exiger_le_media(RUSH_REEL)
    dossier = voisin.projet(tmp_path)

    def poser_le_vrai_rush(videos: Path) -> None:
        """La cible du MILIEU devient le vrai rush du depot.

        Le parcours clavier du banc voisin la vise deja ; c'est lui qu'on veut
        jouer, et non un parcours ecrit pour ce test-ci.
        """
        (videos / voisin.VIDEO_CIBLE).write_bytes(RUSH_REEL.read_bytes())

    journal = logging.getLogger("banc.declaration.integration")

    def preparer(cible: Path):
        return preparer_une_declaration(project_dir=dossier, video_path=cible,
                                        logger=journal)

    def ecrire(preparation) -> str:
        from mixed_media_utility.declaration_de_rush import (
            ecrire_la_declaration)
        return ecrire_la_declaration(preparation, logger=journal).rush_id

    async def valider(pilote, panneau_):
        vu = panneau_.fiche.preparee.rush_id
        panneau_.choix.viser(ajout_de_rush.CLE_DECLARER)
        panneau_.traiter("enter")
        await pilote.pause()
        return vu, empreinte_du_manifeste(dossier)

    ecran, boite = au_panneau(banc, monkeypatch, tmp_path, dossier, preparer,
                              ecrire, suite=valider,
                              sur_les_videos=poser_le_vrai_rush)
    assert boite["apres_le_temps_1"] == boite["avant"], (
        "le vrai temps 1 a touche le manifeste")
    derive, apres = boite["suite"]
    assert apres != boite["avant"], "le temps 2 n'a rien ecrit"
    document = json.loads((dossier / MANIFEST_FILENAME).read_text(
        encoding="utf-8"))
    ecrits = [entree["rush_id"] for entree in document["rushes"]]
    assert derive in ecrits, ecrits
    assert len(ecrits) == len(voisin.RUSHES) + 1
    assert ecran.liste.courant.rush_id == derive, (
        f"curseur sur {ecran.liste.courant.rush_id}, pas sur le rush declare")


# ===========================================================================
# Les TROIS survivants de la campagne, et ce qu'ils disaient du banc
#
# 30 mutants sur 33 tues du premier coup ; les trois qui ont survecu ne
# disaient rien du code et tout du CORPUS -- « une fixture de synthese peut
# fabriquer une panne que le terrain n'a PAS », pris a l'envers : un corpus qui
# n'exerce pas un chemin ne le mesure pas. Les trois tests ci-dessous portent
# donc sur le CONTRAT de la fonction, jamais sur les quatre maquettes.
# ===========================================================================

def test_un_LIBELLE_plus_long_que_la_colonne_garde_son_CREUX():
    """Mutant `M02` : retirer `max(..., CREUX_MINIMAL)` SURVIVAIT.

    Il survivait honnetement : les sept libelles du panneau tiennent tous sous
    la colonne de valeur -- le plus long, `Codec · format de pixel`, en fait 23
    pour 25 --, donc le `max` n'est jamais atteint par le corpus. Le jour ou un
    libelle grandit, sans cette borne la valeur se **colle** a lui et la fiche
    devient illisible sur la seule ligne qui a change.

    `jetons.CREUX_MINIMAL` est lu et non recopie : il vit a un seul endroit
    depuis qu'il y etait ecrit quatre fois.
    """
    long = "Un libelle beaucoup trop long pour la colonne de valeur"
    assert jetons.colonnes(long) > ajout_de_rush.COLONNE_DE_VALEUR
    ligne = ajout_de_rush.ligne_de_fiche(long, "valeur", 200)
    assert ligne.startswith(long)
    creux = len(ligne) - len(long) - len("valeur")
    assert creux >= jetons.CREUX_MINIMAL, repr(ligne)
    # Volet symetrique : un libelle COURT garde, lui, sa colonne exacte.
    court = ajout_de_rush.ligne_de_fiche("Nom", "valeur", 200)
    assert court.index("valeur") == ajout_de_rush.COLONNE_DE_VALEUR


def test_la_VALEUR_est_rendue_TELLE_QUELLE_espaces_compris():
    """Mutant `M04` : un `.strip()` sur la valeur SURVIVAIT.

    Il survivait parce qu'aucune valeur du corpus ne porte d'espace en tete ni
    en queue -- et le terrain, lui, en porte : un nom de fichier peut finir par
    une espace (macOS et Windows les acceptent tous les deux), et c'est
    precisement le genre de nom qu'un operateur ne voit pas et qu'un outil doit
    rendre **verbatim**. Rogner la valeur ferait lire a l'ecran un nom qui n'est
    pas celui du disque, c'est-a-dire exactement ce qu'`EPIC11-ARB-153`
    interdit par l'autre bout.

    La cible est posee aux DEUX BORDS de la valeur -- en tete et en queue --,
    parce qu'un `.lstrip()` et un `.rstrip()` sont deux mutants differents.
    """
    espace_en_queue = "plan sequence 12 .mov"
    ligne = ajout_de_rush.ligne_de_fiche("Nom du fichier",
                                         f" {espace_en_queue} ", 200)
    assert f" {espace_en_queue} " in ligne, repr(ligne)
    assert ligne[ajout_de_rush.COLONNE_DE_VALEUR] == " "
    assert ligne.endswith(" "), (
        "l'espace de queue de la valeur a ete rognee : le nom rendu n'est plus "
        "celui du disque")


def test_la_mesure_du_chemin_compte_des_COLONNES_et_non_des_points_de_code():
    """Mutant `M21` : `len()` a la place de `jetons.colonnes()` SURVIVAIT.

    Meme mode de panne que le mutant `M25` de
    `test_maquette_E2_1i_cardinal_absent`, et la meme lecon : aucun chemin du
    corpus ne porte de caractere large, donc `len()` y rend le bon chiffre
    **par accident**. La mesure porte donc sur le CONTRAT -- un ideogramme
    occupe deux colonnes de terminal --, et le jour ou un dossier japonais
    entrera dans un projet, la ligne d'etat dira la vraie largeur.

    Ce n'est pas theorique pour cette ligne-la : elle annonce « chemin de N
    colonnes, coupé au milieu », c'est-a-dire la MESURE qui justifie la coupe
    (`EPIC11-ARB-56`). Un chiffre compte en points de code sous-estimerait la
    largeur de moitie sur un chemin en ideogrammes -- il annoncerait une coupe
    plus petite que celle qui a eu lieu.
    """
    ideogrammes = "D:\\\u6f22\u5b57\\\u6f22\u5b57\\plan.mov"
    fiche = ajout_de_rush.FicheDeDeclaration(preparee(chemin=ideogrammes))
    assert fiche.colonnes_du_chemin() == jetons.colonnes(ideogrammes)
    assert fiche.colonnes_du_chemin() == len(ideogrammes) + 4, (
        "quatre ideogrammes occupent quatre colonnes de PLUS que de "
        "caracteres : c'est tout ce que le mutant effacait")
    # Volet symetrique : sur un chemin sans caractere large les deux mesures
    # coincident, et c'est bien pour cela que le corpus ne voyait rien.
    latin = ajout_de_rush.FicheDeDeclaration(preparee(chemin=CHEMIN_QUI_TIENT))
    assert latin.colonnes_du_chemin() == len(CHEMIN_QUI_TIENT)
