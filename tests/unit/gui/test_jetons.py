# Story 7.0, AC 3 -- le module de jetons traduit DESIGN.md et les tests
# le MESURENT : neutralite R=G=B par iteration complete, contraste WCAG 2.1
# CALCULE ici (jamais recopie du module teste -- piege du test tautologique,
# 5.9), frontiere zero hexadecimal hors jetons.py.

import re
from pathlib import Path

from mixed_media_utility.gui import jetons

# ---------------------------------------------------------------------------
# Outils de calcul, ecrits DANS le test (WCAG 2.1, sRGB).
# ---------------------------------------------------------------------------


def _rgb(hexa):
    """'#RRGGBB' -> tuple d'entiers (r, g, b) sur 8 bits."""
    assert re.fullmatch(r"#[0-9A-Fa-f]{6}", hexa), hexa
    return tuple(int(hexa[i:i + 2], 16) for i in (1, 3, 5))


def _luminance_relative(rgb):
    """Luminance relative WCAG 2.1 d'un triplet sRGB 8 bits."""
    lineaires = []
    for canal in rgb:
        c = canal / 255.0
        lineaires.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = lineaires
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio_contraste(hexa_a, hexa_b):
    """Ratio de contraste WCAG 2.1 entre deux couleurs."""
    la = _luminance_relative(_rgb(hexa_a))
    lb = _luminance_relative(_rgb(hexa_b))
    clair, sombre = max(la, lb), min(la, lb)
    return (clair + 0.05) / (sombre + 0.05)


def _composite(hexa_dessus, opacite, hexa_dessous):
    """Compose ``dessus`` a ``opacite`` sur ``dessous`` (alpha sRGB 8 bits)."""
    dessus, dessous = _rgb(hexa_dessus), _rgb(hexa_dessous)
    canaux = tuple(
        round(opacite * haut + (1.0 - opacite) * bas)
        for haut, bas in zip(dessus, dessous)
    )
    return "#{:02X}{:02X}{:02X}".format(*canaux)


# Les cinq neutres PORTEURS d'un badge (DESIGN.md, Plancher de contraste :
# le pire fond est surface-hover, pas surface-raised -- d'ou l'iteration
# sur les cinq, jamais un echantillon).
_SURFACES_PORTEUSES = (
    "surface-sunken", "surface-canvas", "surface-panel",
    "surface-raised", "surface-hover",
)


# ---------------------------------------------------------------------------
# Neutralite : R = G = B sur TOUS les neutres.
# ---------------------------------------------------------------------------


def test_tous_les_neutres_sont_strictement_neutres():
    # Iteration sur le dictionnaire COMPLET, jamais un echantillon : une
    # coque teintee fausse le jugement colorimetrique (DESIGN.md).
    assert jetons.NEUTRES, "le dictionnaire des neutres ne doit pas etre vide"
    for nom, hexa in jetons.NEUTRES.items():
        r, g, b = _rgb(hexa)
        assert r == g == b, f"neutre teinte : {nom} = {hexa}"


def test_le_dictionnaire_des_neutres_couvre_toutes_les_familles():
    # Les familles exigees par l'AC 3 : surface-*, border*, text-*,
    # image-mat, paper, paper-ink, overlay-*. Un neutre retire du
    # dictionnaire pour passer le test R=G=B se verrait ici.
    noms = set(jetons.NEUTRES)
    attendus = {
        "surface-sunken", "surface-canvas", "surface-panel",
        "surface-raised", "surface-hover",
        "border", "border-strong",
        "text-primary", "text-secondary", "text-disabled",
        "image-mat", "paper", "paper-ink",
        "overlay-halo", "overlay-handle",
    }
    assert noms == attendus, f"ecart de familles : {noms ^ attendus}"


def test_les_chromies_ne_sont_pas_dans_les_neutres():
    # Accent et semantiques sont chromatiques par construction : aucune ne
    # doit verifier R=G=B (sinon c'est une erreur de transcription).
    for nom, hexa in {**jetons.ACCENT, **jetons.SEMANTIQUES}.items():
        if nom == "accent-on":
            continue  # accent-on est un blanc pur, legitime
        r, g, b = _rgb(hexa)
        assert not (r == g == b), f"chromie neutre par erreur : {nom} = {hexa}"


# ---------------------------------------------------------------------------
# Plancher 4,5:1 -- texte d'etat sur fond de badge compose a 16 %.
# ---------------------------------------------------------------------------


def test_textes_etat_tiennent_4_5_sur_badge_16_pour_cent():
    # Pour chaque etat : fond = chromie PLEINE composee a 16 % sur CHACUN
    # des cinq neutres porteurs ; texte = variante -text. Plancher 4,5:1
    # (tout texte sous 18 px), calcule ici.
    paires = {
        "state-complete": "state-complete-text",
        "state-absent": "state-absent-text",
        "state-substitute": "state-substitute-text",
    }
    for pleine, texte in paires.items():
        for surface in _SURFACES_PORTEUSES:
            fond = _composite(
                jetons.SEMANTIQUES[pleine],
                jetons.BADGE_FOND_OPACITE,
                jetons.NEUTRES[surface],
            )
            ratio = _ratio_contraste(jetons.VARIANTES_TEXTE[texte], fond)
            assert ratio >= 4.5, (
                f"{texte} sur badge {pleine}@16% sur {surface} : "
                f"{ratio:.2f}:1 < 4,5:1"
            )


def test_composer_sur_rend_le_meme_melange_que_la_reference_du_banc():
    """`composer_sur` est mesuree, pas comparee a elle-meme.

    Trouve par la revue de vague 2 (couche 1, par injection): la SEULE
    assertion portant sur la sortie de `jetons.composer_sur` vivait dans
    `test_chutier_signes.py` et comparait `badge.couleur_fond` a un second
    appel de `composer_sur` avec les memes arguments -- les deux cotes de
    l'egalite passant par la meme implementation, un defaut DANS la
    fonction etait structurellement invisible. Deux mutants l'ont prouve en
    laissant les 231 tests du banc GUI verts: l'inversion des poids du
    melange, et un `return surface` qui rend un badge sans aucune teinte.

    Le test de contraste ci-dessous ne gardait rien non plus: les variantes
    `-text` tiennent 4,5:1 sur les cinq neutres porteurs NUS (c'est leur
    contrat), donc un badge qui aurait perdu sa chromie passait le plancher
    tout autant.

    La reference est `_composite`, la reimplementation independante que ce
    fichier porte deja pour ses mesures de contraste. C'est elle qui rend
    l'assertion non tautologique.
    """
    paires = {
        "state-complete": "surface-panel",
        "state-absent": "surface-hover",
        "state-substitute": "surface-raised",
    }
    for chromie, surface in paires.items():
        attendu = _composite(
            jetons.SEMANTIQUES[chromie],
            jetons.BADGE_FOND_OPACITE,
            jetons.NEUTRES[surface],
        )
        obtenu = jetons.composer_sur(
            jetons.SEMANTIQUES[chromie], jetons.NEUTRES[surface]
        )
        assert obtenu == attendu, (
            f"composer_sur({chromie} sur {surface}) rend {obtenu}, "
            f"reference {attendu}"
        )
        # Deux gardes qui nomment les deux mutants survivants: le melange
        # n'est ni la surface nue (chromie perdue) ni la chromie pleine
        # (opacite perdue).
        assert obtenu != jetons.NEUTRES[surface]
        assert obtenu != jetons.SEMANTIQUES[chromie]


def test_composer_sur_est_monotone_avec_l_opacite():
    """A opacite croissante, le melange s'ecarte de la surface vers la chromie.

    Garde d'ORIENTATION: elle tue l'inversion des poids, que l'egalite
    ci-dessus tue deja, mais sans dependre de la reference du banc -- si les
    deux implementations derivaient ensemble, celle-ci mordrait encore.
    """
    surface, chromie = "#000000", "#FFFFFF"
    valeurs = [
        int(jetons.composer_sur(chromie, surface, opacite)[1:3], 16)
        for opacite in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    assert valeurs == sorted(valeurs), valeurs
    assert valeurs[0] == 0x00 and valeurs[-1] == 0xFF, valeurs


def test_accent_text_tient_4_5_sur_surfaces_de_carte():
    # accent-text porte le nom de fonction d'une carte (label 11 px) sur
    # surface-raised, et la ligne survolee sur surface-hover.
    for surface in ("surface-raised", "surface-hover"):
        ratio = _ratio_contraste(
            jetons.VARIANTES_TEXTE["accent-text"], jetons.NEUTRES[surface]
        )
        assert ratio >= 4.5, f"accent-text sur {surface} : {ratio:.2f}:1 < 4,5:1"


# ---------------------------------------------------------------------------
# Plancher 3:1 -- chromies pleines en emploi non textuel.
# ---------------------------------------------------------------------------


def test_chromies_pleines_tiennent_3_1_en_non_textuel():
    # Bordure de vignette, barre de progression, trait de surimpression :
    # les valeurs de trait tiennent 3:1 sur les fonds d'atelier.
    chromies = dict(jetons.SEMANTIQUES)
    chromies["accent"] = jetons.ACCENT["accent"]
    for nom, hexa in chromies.items():
        for surface in ("surface-canvas", "surface-panel"):
            ratio = _ratio_contraste(hexa, jetons.NEUTRES[surface])
            assert ratio >= 3.0, (
                f"{nom} sur {surface} : {ratio:.2f}:1 < 3:1 (non textuel)"
            )


# ---------------------------------------------------------------------------
# Coherence structurelle des jetons de geometrie (valeurs relues par la
# coquille : defauts au-dessus des planchers, seuils ordonnes).
# ---------------------------------------------------------------------------


def test_defauts_au_dessus_des_planchers_et_seuils_ordonnes():
    e = jetons.ESPACEMENTS
    assert e["tree-panel-width"] >= e["tree-panel-min-width"]
    assert e["bin-width"] >= e["bin-min-width"]
    # Les trois seuils sont monotones (DESIGN.md, Taille minimale) :
    assert e["window-min-width"] < e["tree-collapse-threshold"] < e["queue-overlay-threshold"]
    # Et la fenetre minimale couvre le regime replie : rail + poignee +
    # chutier au plancher + scene au plancher (l'addition de la spine).
    assert (
        e["tree-panel-rail"] + e["splitter-width"]
        + e["bin-min-width"] + e["stage-min-width"]
        <= e["window-min-width"]
    )


# ---------------------------------------------------------------------------
# Frontiere negative : zero couleur hexadecimale dans gui/ hors jetons.py.
# ---------------------------------------------------------------------------


def test_aucun_hexadecimal_hors_du_module_de_jetons():
    # Toute couleur passe par le module de jetons. Le grep est scope au
    # paquet GUI : les modules de coeur portent legitimement des valeurs
    # colorimetriques metier.
    paquet_gui = Path(jetons.__file__).resolve().parent
    motif = re.compile(r"#[0-9a-fA-F]{6}")
    fautifs = []
    for source in sorted(paquet_gui.rglob("*.py")):
        if source.name == "jetons.py":
            continue
        if motif.search(source.read_text(encoding="utf-8")):
            fautifs.append(source.name)
    assert fautifs == [], f"couleurs en dur hors jetons.py : {fautifs}"


# ---------------------------------------------------------------------------
# Story 7.4, AC 6 / Task 1 -- geometrie des surimpressions de scan.
#
# Ces tests ne comparent PAS le module a lui-meme : ils relisent le
# frontmatter de `DESIGN.md`, qui est la source, et exigent l'egalite. Un
# jeton invente (une valeur qui n'existe pas dans la spine) ou derive (une
# valeur recopiee d'un autre jeton) tombe ici. Bloc ajoute en fin de fichier
# pour ne pas croiser les editions d'une autre story sur ce meme module.
# ---------------------------------------------------------------------------

import yaml  # noqa: E402  (import tardif, bloc de fin de fichier)

#: `DESIGN.md` a quitte `_bmad-output/planning-artifacts/ux-designs/` pour
#: `docs/guide-developpeur/` le 2026-09-07 : c'est une source de verite du
#: produit, pas un artefact de travail interne, et le depot public la livre.
#: Ses voisins de l'ancien dossier (EXPERIENCE.md, revues, maquettes) restent
#: ou ils sont -- eux relevent bien du travail interne.
_DESIGN_MD = (
    Path(jetons.__file__).resolve().parents[3]
    / "docs"
    / "guide-developpeur"
    / "DESIGN.md"
)


def _frontmatter_de_la_spine():
    """Le frontmatter YAML de `DESIGN.md`, la source des jetons.

    Echec **dur** si le fichier manque : un `skip` se lirait comme un vert
    alors que la transcription ne serait pas verifiee du tout.
    """
    assert _DESIGN_MD.is_file(), (
        f"spine introuvable a {_DESIGN_MD} : la transcription des jetons ne "
        "peut pas etre verifiee, et un skip se lirait comme un vert"
    )
    texte = _DESIGN_MD.read_text(encoding="utf-8")
    assert texte.startswith("---\n")
    _, brut, _ = texte.split("---\n", 2)
    return yaml.safe_load(brut)


def _px(valeur):
    """`1.5px` -> 1.5 ; `3px` -> 3. La spine ecrit ses longueurs en px."""
    texte = str(valeur).strip()
    assert texte.endswith("px"), f"longueur sans unite px : {valeur!r}"
    nombre = float(texte[:-2])
    return int(nombre) if nombre.is_integer() else nombre


def test_les_jetons_de_surimpression_sont_transcrits_de_la_spine():
    composants = _frontmatter_de_la_spine()["components"]
    zone = composants["overlay-zone"]
    poignee = composants["overlay-handle"]
    assert jetons.SURIMPRESSIONS["trait-px"] == _px(zone["stroke-width"])
    assert jetons.SURIMPRESSIONS["halo-px"] == _px(zone["halo-width"])
    assert jetons.SURIMPRESSIONS["poignee-px"] == _px(poignee["size"])
    # La spine dit "trait, jamais aplat" : `fill: none` est un invariant de
    # la famille, pas un defaut de rendu.
    assert zone["fill"] == "none"


def test_le_contenu_d_image_est_a_rayon_nul_et_le_cadre_ne_l_est_pas():
    # `DESIGN.md`, Layout & Spacing : « Le cadre autour de l'image peut etre
    # arrondi ; l'image, jamais. » Les deux moities sont mesurees, pas
    # seulement la premiere : un `content-radius` egal au rayon du cadre
    # passerait un test qui ne verifierait que le nul.
    scene = _frontmatter_de_la_spine()["components"]["viewer-stage"]
    assert scene["content-radius"] == "{rounded.none}"
    assert scene["radius"] == "{rounded.lg}"
    assert jetons.RAYON_CONTENU_IMAGE == jetons.RAYONS["none"] == 0
    assert jetons.RAYON_CADRE_SCENE == jetons.RAYONS["lg"]
    assert jetons.RAYON_CONTENU_IMAGE != jetons.RAYON_CADRE_SCENE


def test_l_opacite_de_vignette_non_designee_est_celle_de_la_spine():
    vignette = _frontmatter_de_la_spine()["components"]["frame-thumb"]
    assert jetons.OPACITE_VIGNETTE_NON_DESIGNEE == float(
        vignette["opacity-deselected"]
    )
    # Une vignette non designee s'EFFACE, elle ne disparait pas.
    assert 0.0 < jetons.OPACITE_VIGNETTE_NON_DESIGNEE < 1.0
    # La vignette est un contenu d'image : coins droits, comme la scene.
    assert vignette["radius"] == "{rounded.none}"


def test_la_bande_mat_min_de_la_spine_est_celle_du_module():
    espacements = _frontmatter_de_la_spine()["spacing"]
    scene = _frontmatter_de_la_spine()["components"]["viewer-stage"]
    # Le `padding` de la scene EST la bande de mat : le jeton n'a pas deux
    # valeurs concurrentes.
    assert scene["padding"] == "{spacing.mat-min}"
    assert jetons.ESPACEMENTS["mat-min"] == _px(espacements["mat-min"])
