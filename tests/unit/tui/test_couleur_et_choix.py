# -*- coding: utf-8 -*-
"""La couleur et le mecanisme de choix (`EPIC11-ARB-45` et `EPIC11-ARB-47`).

**Ce fichier existe parce que les AC de la vague etaient unilaterales.** Elles
verifiaient que l'information survit **sans** couleur, jamais qu'elle est
coloree **avec** -- si bien que les cinq ecrans rendaient du texte nu, que les
quatre jetons d'etat n'etaient jamais employes, et que le rendu monochrome
qu'Egan a vu au parcours manuel etait le rendu attendu du code.

Chaque propriete est donc mesuree **des deux cotes** : ce que le regime nominal
teinte, et ce que le repli garde lisible.
"""
import html
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.tui import jetons


def _styles_par_ligne(peint, lignes):
    """Le style de CHAQUE ligne, dans l'ordre -- `None` quand elle n'en a pas.

    Lire `peint.spans` a plat ne dit pas QUELLE ligne est teintee : une peinture
    qui teindrait toujours le rang 0 rendrait la meme liste de styles qu'une
    peinture juste. On rapporte donc chaque intervalle a son rang, en comptant
    les separateurs de ligne que :func:`jetons.peindre` intercale.
    """
    rang_du_debut = {}
    curseur = 0
    for rang, ligne in enumerate(lignes):
        rang_du_debut[curseur] = rang
        curseur += len(ligne) + 1  # + le saut de ligne
    styles = [None] * len(lignes)
    for span in peint.spans:
        if span.style:
            styles[rang_du_debut[span.start]] = str(span.style)
    return styles


# ---------------------------------------------------------------------------
# `EPIC11-ARB-47` -- la couleur, des deux cotes
# ---------------------------------------------------------------------------

def test_la_ligne_du_curseur_est_en_GRAS_et_en_ACCENTUATION():
    """La moitie du mecanisme de choix d'`EPIC11-ARB-45` : « le choix passe en
    surbrillance gras + couleur d'accentuation »."""
    peint = jetons.peindre(["  premiere", f"{jetons.GLYPHES['curseur']} visee",
                            "  troisieme"])
    styles = [(span.start, span.style) for span in peint.spans if span.style]
    assert styles == [(11, f"bold {jetons.couleur('accent')}")], styles


def test_un_glyphe_d_etat_TEINTE_sa_ligne():
    """Les quatre jetons d'etat existaient et n'etaient jamais employes."""
    for nom_etat in ("complete", "substitute", "absent"):
        ligne = jetons.marque(nom_etat, "un libelle")
        peint = jetons.peindre([ligne])
        attendu = jetons.couleur(f"state-{nom_etat}")
        assert [s.style for s in peint.spans if s.style] == [attendu], nom_etat


def test_SANS_COULEUR_le_texte_reste_identique():
    """Volet symetrique, et c'est la regle 1 non negociable de `DESIGN.md`
    section 5 : la couleur **double** un canal, elle ne le porte jamais seule.
    Un terminal monochrome doit lire exactement la meme chose."""
    lignes = [jetons.marque("absent", "ce dossier n'est pas un projet"),
              f"{jetons.GLYPHES['curseur']} Creer un projet ici"]
    peint = jetons.peindre(lignes, sans_couleur=True)
    assert jetons.texte_affiche(peint) == chr(10).join(lignes)
    assert [s for s in peint.spans if s.style] == [], "le repli teinte encore"
    # Et le regime nominal dit la MEME chose une fois les balises retirees.
    nominal = jetons.texte_affiche(jetons.peindre(lignes))
    assert nominal == jetons.texte_affiche(peint)


def test_la_LARGEUR_se_mesure_sur_le_texte_affiche_et_non_sur_les_balises():
    """L'ordre largeur-puis-couleur n'est pas negociable : peindre d'abord
    ferait compter les balises comme des colonnes, et **chaque ligne coloree
    deborderait** de la longueur de ses balises."""
    ligne = jetons.marque("absent", "x" * 60)
    peint = jetons.peindre([ligne])
    assert [s.style for s in peint.spans if s.style], "rien n'est teinte"
    assert jetons.colonnes(jetons.texte_affiche(peint)) == jetons.colonnes(ligne)


@pytest.mark.parametrize("texte", [
    r"D:\projets\[lot a]\rush.mov",
    "motif du coeur : [x] refuse",
    "chemin qui finit par une barre inverse " + chr(92),
])
def test_un_texte_a_CROCHETS_survit_intact(texte):
    """Un chemin ou un motif du coeur porte des crochets ; sans echappement,
    `[x]` serait lu comme une balise et **disparaitrait de l'ecran**."""
    assert jetons.texte_affiche(jetons.peindre([texte])) == texte


def test_le_repli_ASCII_teinte_AUSSI():
    """Le repli change le dessin du glyphe, jamais le canal de couleur : les
    deux tables d'etat sont branchees."""
    ligne = jetons.marque("absent", "refuse", ascii_seul=True)
    peint = jetons.peindre([ligne], ascii_seul=True)
    attendu = [jetons.couleur("state-absent")]
    assert [s.style for s in peint.spans if s.style] == attendu, peint


# ---------------------------------------------------------------------------
# Le defaut trouve par Egan le 2026-08-29 : la table des glyphes porte les DEUX
# modes, et la peinture y cherchait les six glyphes a la fois.
# ---------------------------------------------------------------------------

#: Les lignes de prose et de valeurs qu'aucun mode ne doit teindre. Elles
#: portent toutes un `x`, un `!` ou une `*` -- c'est-a-dire les trois glyphes
#: d'etat du repli ASCII -- et elles sont toutes atteignables : le journal
#: d'execution et l'ecran de refus rendent **verbatim** des messages venus du
#: coeur, et les deux dernieres sont des lignes de l'explorateur.
PROSE_QUI_RESSEMBLE_A_UN_ETAT = [
    "Extraction",                        # `x` colle a des lettres
    "deux lots",                         # idem, au milieu d'un mot
    "Rien n'a ete ecrit !",              # `!` borde de blancs, en fin de ligne
    "Attention ! le lot est incomplet",  # `!` borde de blancs, au milieu
    "resolution 3840 x 2160",            # `x` borde de blancs : une dimension
    "un budget de 3 * 4",                # `*` borde de blancs : un produit
    "planche 3 sur 4 * ok",              # `*` borde de blancs, suivi d'un mot
    "    x              2 o",            # un FICHIER nomme `x`, sa taille a droite
    "    x              3 sous-dossiers",  # un DOSSIER nomme `x`
]


@pytest.mark.parametrize("ligne", PROSE_QUI_RESSEMBLE_A_UN_ETAT)
@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_une_LETTRE_ordinaire_ne_teinte_RIEN_dans_AUCUN_mode(ligne, ascii_seul):
    """« Extraction » sortait en ROUGE au menu des ateliers, sur le rendu livre.

    La cause d'origine : une table qui portait les six glyphes -- les trois
    UTF-8 et leurs trois replis ASCII --, et une peinture qui les cherchait
    tous, dans un texte qui est en UTF-8.

    **La parametrisation est ici la mesure elle-meme.** La premiere correction
    a filtre les glyphes par mode et ajoute une frontiere de mot ; elle fermait
    l'UTF-8 et laissait l'ASCII ouvert, et le test ASCII avait ete restreint aux
    deux seuls cas qui passaient -- le code n'avait pas ete ajuste au test, le
    test l'avait ete au code. Les cas retires sont revenus, la liste est
    commune aux deux modes, et **aucun des deux ne peut plus etre ferme seul**.
    """
    peint = jetons.peindre([ligne], ascii_seul=ascii_seul)
    assert [s.style for s in peint.spans if s.style] == [], (ligne, ascii_seul)


#: **Des lignes ou un glyphe ASCII OUVRE UNE COLONNE** -- c'est-a-dire ou la
#: seconde condition de la peinture est satisfaite, et ou seul le FILTRE DE
#: MODE peut encore refuser de teindre. Le corpus ci-dessus n'en contenait
#: aucune : ses lignes a `*` et `!` les portent au milieu d'une prose, donc
#: `_OUVRE_UNE_COLONNE` les ecartait a lui seul, et le filtre de mode restait
#: sans mesure (revue de la vague 3, couche 1, finding `C1`).
GLYPHE_ASCII_QUI_OUVRE_UNE_COLONNE = [
    "  * Attention: la source est illisible",
    "  ! reserve sur le lot",
    "  x fichier absent",
]


@pytest.mark.parametrize("ligne", GLYPHE_ASCII_QUI_OUVRE_UNE_COLONNE)
def test_le_FILTRE_DE_MODE_est_ce_qui_ferme_l_UTF8_contre_un_GLYPHE_ASCII(ligne):
    """**La premiere des deux conditions, enfin mesuree seule** (finding `C1`).

    `etats_du_mode` dit d'elle-meme qu'elle est « la premiere des deux
    conditions qui rendent la peinture sure », et que « le filtre de mode seul
    ne tient pas ». La SECONDE condition (`_OUVRE_UNE_COLONNE`) etait mesuree ;
    la premiere ne l'etait pas, parce qu'aucune ligne du corpus de prose ne
    satisfaisait la seconde. Le mutant qui remet la table des DEUX modes --
    exactement la regression du 2026-08-29, celle qui faisait sortir
    « Extraction » en ROUGE -- survivait donc a 414 tests.

    Ici, `_OUVRE_UNE_COLONNE` est satisfaite par construction : deux blancs
    d'indentation, le glyphe, un blanc, le libelle. En UTF-8, les glyphes
    d'etat sont `●`, `▲`, `✕` -- `*`, `!` et `x` n'en sont pas, et c'est le
    filtre de mode, et lui seul, qui doit le dire.
    """
    peint = jetons.peindre([ligne], ascii_seul=False)
    assert [s.style for s in peint.spans if s.style] == [], (
        "en UTF-8, un glyphe du repli ASCII ne teint rien -- meme en tete de "
        f"colonne : {ligne!r}")


@pytest.mark.parametrize("ligne", GLYPHE_ASCII_QUI_OUVRE_UNE_COLONNE)
def test_en_ASCII_ces_MEMES_lignes_SONT_teintes__et_c_est_une_QUESTION_OUVERTE(
        ligne):
    """**Le volet symetrique, qui epingle le comportement d'AUJOURD'HUI.**

    Sans lui, le test precedent pourrait rester vert sur une peinture qui ne
    teint plus rien du tout : c'est la forme de garde d'absence que la
    politique refuse.

    Mais ce qu'il epingle **n'est pas forcement ce qu'on veut**, et il vaut
    mieux l'ecrire que de le taire. En repli ASCII, les glyphes d'etat SONT des
    lettres et des signes de ponctuation ordinaires, si bien qu'une ligne de
    journal venue du coeur -- « `  * Attention: la source est illisible` » --
    est teinte en VERT (`state-complete`) alors qu'elle porte un
    avertissement. La docstring de `jeton_d_etat` assume le cas du dossier
    litteralement nomme `x` ; elle n'assume ni la puce `*` ni le `!` en tete de
    colonne.

    Le vrai remede n'est pas de relacher `_OUVRE_UNE_COLONNE` -- ce serait
    rouvrir la regression de 2026-08-29 -- mais de poser `etats=` sur ces
    lignes-la : depuis `EPIC11-ARB-71`, la reconnaissance par motif n'est qu'un
    REPLI. C'est verse a `deferred-work.md` avec cette mesure, et ce banc
    rougira le jour ou quelqu'un s'en occupera -- ce qui est le but.
    """
    peint = jetons.peindre([ligne], ascii_seul=True)
    assert [s.style for s in peint.spans if s.style] != [], (
        "comportement d'aujourd'hui, epingle a dessein : en ASCII ces lignes "
        f"SONT teintes -- {ligne!r}")


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_dans_une_liste_la_seule_ligne_teintee_est_celle_qui_porte_l_etat(
        ascii_seul):
    """Volet d'appariement : trois entrees DISTINCTES, l'etat sur la DERNIERE.

    Une fabrique qui ne produirait qu'une entree -- ou trois entrees identiques
    -- laisserait passer une peinture qui teint toujours le rang 0, ou qui teint
    toute la liste des qu'une ligne porte un etat. L'entree visee est donc
    ailleurs qu'en premiere position, et ses voisines sont precisement les deux
    formes qui ressemblent le plus a un etat sans en etre un.
    """
    table = jetons.glyphes(ascii_seul)
    lignes = [
        "    x              2 o",              # un fichier nomme `x`
        "    notes.txt         14 ko",         # une entree ordinaire
        f"    demo           {table['complete']} projet",  # la seule teintee
    ]
    peint = jetons.peindre(lignes, ascii_seul=ascii_seul)
    styles = _styles_par_ligne(peint, lignes)
    assert styles == [None, None, jetons.couleur("state-complete")], (
        styles, lignes)


def test_le_glyphe_borde_par_des_blancs_teint_TOUJOURS():
    """Volet symetrique : la frontiere de mot ne doit pas eteindre le canal.

    Les trois etats, dans les deux modes, avec un libelle a droite -- c'est la
    forme que `marque()` produit et que les ecrans posent.
    """
    for ascii_seul in (False, True):
        for nom in jetons.NOMS_D_ETAT:
            ligne = "  " + jetons.marque(nom, "un libelle", ascii_seul)
            peint = jetons.peindre([ligne], ascii_seul=ascii_seul)
            attendu = [jetons.couleur(f"state-{nom}")]
            assert [s.style for s in peint.spans if s.style] == attendu, (
                nom, ascii_seul, ligne)


# ---------------------------------------------------------------------------
# `EPIC11-ARB-51` -- la TROISIEME regle de peinture : le champ qui a le focus
# ---------------------------------------------------------------------------

def _ecran_de_creation(ascii_seul: bool = False) -> list[str]:
    """Quatre lignes DISTINCTES d'un ecran de creation de projet.

    La fabrique produit **plusieurs lignes distinguables** et place la ligne
    visee -- le champ qui a le focus -- **en derniere position** : une peinture
    qui accentuerait toujours le rang 0, ou qui accentuerait tout ce qui porte
    un `>`, rendrait le meme resultat sur une fabrique mono-ligne.

    Le troisieme element est le second champ, **sans** focus : c'est lui qui
    prouve que ce n'est pas le libelle « champ » qui declenche l'accentuation.
    """
    table = jetons.glyphes(ascii_seul)
    return [
        "  Ce qui sera cree",
        "  " + jetons.marque("substitute", "ce dossier n'existe pas",
                             ascii_seul),
        "  Dossier parent      D:" + chr(92) + "projets",
        f"  Nom du projet     {table['invite']} mon_projet",
    ]


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_le_champ_qui_a_le_FOCUS_est_ACCENTUE_comme_la_ligne_du_curseur(
        ascii_seul):
    """La troisieme regle de `peindre`, mesuree du cote COLORE.

    Demande d'Egan, verbatim : « il faut que cet etat soit visible ». Quand la
    saisie a le focus, la liste ne l'a plus et **rien d'autre ne le montrerait**
    -- le champ EST le curseur a ce moment-la. Sans cette regle le champ sort
    en texte nu, indistinguable du champ voisin, et l'operateur ne sait plus ou
    il tape.

    L'AC 5.6 exige la mesure des deux cotes ; c'est ici le cote colore, le
    volet lisible-sans-couleur etant mesure juste apres.
    """
    lignes = _ecran_de_creation(ascii_seul)
    peint = jetons.peindre(lignes, ascii_seul=ascii_seul)
    accent = "bold " + jetons.couleur("accent")
    assert _styles_par_ligne(peint, lignes) == [
        None,
        jetons.couleur("state-substitute"),
        None,
        accent,
    ], (_styles_par_ligne(peint, lignes), lignes)


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_le_champ_qui_a_le_FOCUS_reste_LISIBLE_sans_couleur(ascii_seul):
    """Volet symetrique de l'AC 5.6, et regle 1 de `DESIGN.md` section 5.

    Le glyphe d'invite `>` reste la, au meme rang, avec exactement le meme
    texte : sur un terminal monochrome l'operateur voit toujours ou il tape.
    Une regle qui aurait remplace le glyphe par de la couleur echouerait ici.
    """
    lignes = _ecran_de_creation(ascii_seul)
    peint = jetons.peindre(lignes, ascii_seul=ascii_seul, sans_couleur=True)
    assert jetons.texte_affiche(peint) == chr(10).join(lignes)
    assert [s for s in peint.spans if s.style] == [], "le repli teinte encore"
    glyphe = jetons.glyphes(ascii_seul)["invite"]
    porteuses = [rang for rang, ligne in enumerate(lignes) if glyphe in ligne]
    assert porteuses == [3], (porteuses, lignes)


@pytest.mark.parametrize("ascii_seul", [False, True], ids=["utf8", "ascii"])
def test_l_invite_PASSE_DEVANT_le_glyphe_d_etat_de_la_meme_ligne(ascii_seul):
    """L'ORDRE des regles, et non leur seule existence.

    Une ligne peut porter les deux a la fois -- un champ en focus dont la
    valeur est refusee. La troisieme regle vient apres celle du curseur et
    **avant** celle de l'etat : c'est le focus qui gagne, parce que c'est lui
    qui dit ou va la frappe suivante. Sans la regle, la ligne sortirait en
    couleur d'etat, ce qui est precisement le rendu qu'on ne veut pas.
    """
    table = jetons.glyphes(ascii_seul)
    lignes = [
        "  Ce qui sera cree",
        f"  {jetons.marque('absent', 'introuvable', ascii_seul)}"
        f"   {table['invite']} D:" + chr(92) + "absent",
    ]
    peint = jetons.peindre(lignes, ascii_seul=ascii_seul)
    assert _styles_par_ligne(peint, lignes) == [
        None, "bold " + jetons.couleur("accent")], (
        _styles_par_ligne(peint, lignes), lignes)
    # Et la preuve que la ligne porte bien AUSSI un etat -- sans quoi le test
    # ci-dessus ne mesurerait pas une priorite mais une absence.
    assert jetons.jeton_d_etat(lignes[1], ascii_seul) == "state-absent"


# ---------------------------------------------------------------------------
# Story 11.2c, AC 6 -- la peinture teinte l'ENTREE du curseur, pas seulement la
# ligne qui porte son glyphe. Note 1 d'Egan du 2026-08-31, sur `E3-0` :
# « Detecter les planches et la premiere ligne de description sont en bleu. Pas
# la seconde ligne de description. »
#
# C'est le SYMETRIQUE d'un defaut deja ferme : `EPIC11-ARB-71` a ajoute le
# parametre `etats` parce qu'« une ligne de continuation d'un message replie ne
# porte, par construction, aucun glyphe ». Le raisonnement n'avait jamais ete
# applique au curseur.
# ---------------------------------------------------------------------------

def _entree_sur_trois_lignes():
    """Une entree de menu qui tient sur TROIS lignes, entouree de voisines.

    Trois et non deux : avec deux, « teinter la premiere et la suivante » et
    « teinter toute l'entree » sont indiscernables. Et l'entree est au MILIEU --
    ni premiere, ni derniere -- pour qu'un debordement d'un rang de trop se
    voie des deux cotes.
    """
    return [
        "  Atelier Scan",
        "",
        "  Calibrer une chaine        Depuis le scan d'une page,",
        "                             produire le profil couleur.",
        "\u25b8 Detecter des planches    Deposer des scans, lire les QR,",
        "                             ecrire les TIFF. Le parcours",
        "                             principal, celui de tous les jours.",
        "",
        "  Autre chose                une derniere entree",
    ]


def test_l_entree_du_curseur_est_teintee_EN_ENTIER(tmp_path=None):
    """AC 6.1 et 6.2. Les trois lignes de l'entree, pas la premiere seule."""
    lignes = _entree_sur_trois_lignes()
    peint = jetons.peindre(lignes, lignes_du_curseur=range(4, 7))
    styles = _styles_par_ligne(peint, lignes)
    accent = "bold " + jetons.couleur("accent")
    assert styles[4] == accent, styles[4]
    assert styles[5] == accent, ("la premiere ligne de continuation, "
                                 "c'est exactement ce qu'Egan a vu blanc")
    assert styles[6] == accent, "et la seconde aussi"
    assert styles[3] != accent, "l'entree du dessus n'est pas teintee"
    assert styles[7] != accent, "ni la ligne du dessous"


def test_le_parametre_d_ORIGINE_survit(tmp_path=None):
    """AC 6.1. Huit appelants passent `ligne_du_curseur=<rang>` : aucun n'est
    modifie par cette story, et un test le mesure plutot qu'une promesse."""
    lignes = _entree_sur_trois_lignes()
    peint = jetons.peindre(lignes, ligne_du_curseur=4)
    styles = _styles_par_ligne(peint, lignes)
    accent = "bold " + jetons.couleur("accent")
    assert styles[4] == accent
    assert styles[5] != accent, ("un rang unique reste un rang unique : "
                                 "elargir en douce changerait huit ecrans")


def test_l_auto_detection_teinte_toujours_UN_seul_rang(tmp_path=None):
    """Le repli par motif ne peut pas deviner ou une entree finit -- une ligne
    de continuation ne porte, par construction, aucun glyphe. Il teinte donc un
    rang, et c'est pourquoi les ecrans a entrees multi-lignes DOIVENT donner
    leurs rangs."""
    lignes = _entree_sur_trois_lignes()
    styles = _styles_par_ligne(jetons.peindre(lignes), lignes)
    accent = "bold " + jetons.couleur("accent")
    assert styles[4] == accent
    assert styles[5] != accent


def test_l_auto_detection_exige_le_glyphe_EN_TETE_de_ligne(tmp_path=None):
    """Une propriete du repli qu'il vaut mieux epingler que decouvrir.

    `peindre` cherche `ligne.startswith(glyphe)` : une ligne de curseur
    INDENTEE n'est donc pas detectee du tout. Les ecrans du produit posent leur
    glyphe en premiere colonne (`ecran_ateliers.ligne_d_entree` :
    `f"{marque} {nom:<12}{droite}"`), donc aucun n'est concerne aujourd'hui --
    mais une maquette indentee, elle, l'est, et le colorisateur de maquettes
    `strip()` avant de tester la ou `peindre` ne le fait pas. Les deux ne
    peuvent pas rendre la meme chose sur la meme ligne, et c'est ce que ce test
    rend visible.
    """
    lignes = _entree_sur_trois_lignes()
    indentees = ["  " + l for l in lignes]
    styles = _styles_par_ligne(jetons.peindre(indentees), indentees)
    accent = "bold " + jetons.couleur("accent")
    assert styles[4] != accent, (
        "indentee, la ligne du curseur n'est pas detectee -- c'est le REPLI qui "
        "a cette limite, et c'est pourquoi un ecran DONNE ses rangs")


# --------------------------------------------------------------------------
# AC 6.4 -- le colorisateur de maquettes recoit les rangs, comme un ecran.
#
# Il vit hors du paquet (`_bmad-output/planning-artifacts/ux-designs/`), et il
# est charge par chemin plutot que recopie : un second colorisateur dans le
# banc divergerait du premier au premier ajustement, et le banc validerait
# alors une peinture que personne ne rend.
# --------------------------------------------------------------------------

def _colorisateur():
    import importlib.util

    chemin = (Path(__file__).resolve().parents[3] / "_bmad-output"
              / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
              / "coloriser_maquette.py")
    spec = importlib.util.spec_from_file_location("coloriser_maquette", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _grille_avec_entree_sur_trois_lignes():
    """Une grille 80x24 minimale : un cadre, et l'entree du curseur INDENTEE.

    Indentee volontairement : c'est la forme que prennent les maquettes, et
    c'est exactement celle sur laquelle le repli et `jetons.peindre` divergent
    (test ci-dessus). Ce qui est mesure ici, c'est que la forme DONNEE, elle,
    ne depend d'aucune des deux.
    """
    def contenu(texte=""):
        return "│" + texte.ljust(78) + "│"

    lignes = ["┌" + "─" * 78 + "┐",
              contenu(" Atelier Scan"),
              "├" + "─" * 78 + "┤"]
    lignes += [contenu(" ")] * 4
    lignes += [contenu("  ▸ Detecter des planches   Deposer des scans,"),
               contenu("                            lire les QR, ecrire les"),
               contenu("                            TIFF.")]
    lignes += [contenu(" ")] * (24 - len(lignes) - 4)
    lignes += ["├" + "─" * 78 + "┤",
               contenu(" pret"),
               contenu(" Entree ouvrir"),
               "└" + "─" * 78 + "┘"]
    assert len(lignes) == 24, len(lignes)
    return "\n".join(lignes)


def _rangs_en_accent_de_la_maquette(module, texte, lignes_du_curseur=None):
    """Les rangs que le colorisateur rend en `accent` gras."""
    accent = jetons.couleur("accent")
    rangs = set()
    for rang, segments in enumerate(module.peindre_maquette(
            texte, lignes_du_curseur)):
        if any(gras and couleur == accent and morceau.strip()
               for morceau, couleur, gras in segments):
            rangs.add(rang)
    return rangs


def test_le_colorisateur_de_maquettes_RECOIT_les_rangs_du_curseur():
    """AC 6.4. Les trois lignes de l'entree, y compris les continuations qui ne
    portent aucun glyphe -- ce qu'aucun repis par motif ne peut deviner."""
    module = _colorisateur()
    texte = _grille_avec_entree_sur_trois_lignes()
    assert _rangs_en_accent_de_la_maquette(module, texte, range(7, 10)) == {
        7, 8, 9}


def test_le_repli_du_colorisateur_ne_trouve_QU_UN_rang():
    """Le volet symetrique, et le motif de l'AC : sans les rangs, la maquette
    laisse blanches les deux lignes de continuation. C'est le rendu qu'Egan a
    juge incorrect le 2026-08-31 sur la planche de selection."""
    module = _colorisateur()
    texte = _grille_avec_entree_sur_trois_lignes()
    assert _rangs_en_accent_de_la_maquette(module, texte) == {7}


def test_le_colorisateur_teint_une_continuation_VIDE_quand_elle_est_donnee():
    """Une entree peut porter une ligne de continuation blanche. Donnee, elle
    est teintee : sinon la teinte se troue AU MILIEU de l'entree, ce qui est
    pire que de ne pas teindre du tout."""
    module = _colorisateur()
    lignes = _grille_avec_entree_sur_trois_lignes().split("\n")
    lignes[8] = "│" + " " * 78 + "│"
    peint = module.peindre_maquette("\n".join(lignes), range(7, 10))
    accent = jetons.couleur("accent")
    corps = [(m, c, g) for m, c, g in peint[8] if m.strip("│")]
    assert corps and all(c == accent and g for _, c, g in corps), corps


def test_les_rangs_donnes_ne_debordent_PAS_sur_les_voisins():
    """La mesure d'exception se fait a l'ensemble EXACT : « ces rangs sont en
    accent » laisserait passer une peinture qui teint toute la grille."""
    module = _colorisateur()
    texte = _grille_avec_entree_sur_trois_lignes()
    rangs = _rangs_en_accent_de_la_maquette(module, texte, [8])
    assert rangs == {8}, ("un rang donne teint SA ligne et rien d'autre, "
                          "meme quand la ligne 7 porte le glyphe du curseur")


# --------------------------------------------------------------------------
# `EPIC11-ARB-125` -- les rangs sont DECLARES par le generateur, et le
# colorisateur les LIT. Finding `R10` de la revue du 2026-08-31 : la story
# 11.2c avait livre la capacite sans son appelant, si bien que regenerer les
# maquettes reproduisait a l'identique le rendu qu'Egan avait refuse.
# --------------------------------------------------------------------------

def _dossier_des_maquettes():
    return (Path(__file__).resolve().parents[3] / "_bmad-output"
            / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
            / "maquettes")


def test_les_rangs_declares_sont_LUS_par_le_chemin_de_PRODUCTION(tmp_path):
    """Le bout de chaine qui manquait, mesure **sur le SVG que `main()` ecrit**.

    **Premiere redaction de ce test : deux mutants survivants.** Elle appelait
    `peindre_maquette` avec les rangs declares -- ce que quatre tests font deja
    plus haut -- et ne touchait jamais `main()`, qui EST le finding. Retirer les
    rangs de l'appel de `main()`, ou tronquer la hauteur declaree a 1, la
    laissait verte. C'est la tautologie que la politique du depot nomme, dans un
    test ecrit expres pour la fermer.

    La mesure porte donc sur le SVG **produit**, dans un dossier jetable : la
    ligne de continuation de l'entree du curseur doit y sortir en accent gras.
    """
    module = _colorisateur()
    source = _dossier_des_maquettes()
    declares = module.rangs_declares(source)
    assert declares, (
        "aucune maquette ne declare ses rangs : la capacite de recevoir des "
        "rangs redeviendrait sans appelant, ce qui EST le finding `R10`")

    module.main(source=source, cible=tmp_path)
    accent = jetons.couleur("accent")
    for stem, rangs in sorted(declares.items()):
        svg = (tmp_path / f"{stem}.svg").read_text(encoding="utf-8")
        lignes = (source / f"{stem}.txt").read_text(encoding="utf-8").split("\n")
        # Chaque rang declare doit se retrouver PEINT dans le SVG : on cherche
        # le texte de la ligne, et l'on exige qu'il soit servi en accent gras.
        for rang in rangs:
            corps = lignes[rang][1:-1].strip()
            if not corps:
                continue
            morceau = html.escape(corps[:24])
            porteuses = [l for l in svg.split("\n") if morceau in l]
            assert porteuses, (stem, rang, morceau)
            assert all(accent in l and "font-weight:700" in l or
                       accent in l and 'font-weight="700"' in l
                       for l in porteuses), (
                f"{stem} rang {rang} n'est pas peint en accent : {porteuses}")


def test_une_declaration_de_rangs_DECRIT_la_maquette_qu_elle_nomme():
    """Une declaration perimee est pire qu'aucune : elle teint a cote.

    Trois proprietes, sur chaque entree : la maquette existe, le premier rang
    declare porte bien le glyphe de curseur, et les rangs sont contigus et dans
    la grille. Le generateur ecrit une HAUTEUR et ne compte aucun rang -- c'est
    ici qu'on verifie que le rang retrouve est le bon.
    """
    module = _colorisateur()
    source = _dossier_des_maquettes()
    for stem, rangs in sorted(module.rangs_declares(source).items()):
        chemin = source / f"{stem}.txt"
        assert chemin.exists(), f"declaration orpheline : {stem}"
        lignes = chemin.read_text(encoding="utf-8").split("\n")
        assert rangs == list(range(rangs[0], rangs[0] + len(rangs))), (
            stem, rangs)
        assert rangs[-1] < module.HAUTEUR_GRILLE, (stem, rangs)
        tete = lignes[rangs[0]][1:-1].strip()
        assert tete.startswith(jetons.GLYPHES["curseur"]), (
            f"{stem} : le premier rang declare ({rangs[0]}) ne porte pas le "
            f"glyphe de curseur : {tete!r}")
        for rang in rangs[1:]:
            suite = lignes[rang][1:-1].strip()
            assert not suite.startswith(jetons.GLYPHES["curseur"]), (
                f"{stem} : le rang {rang} porte un glyphe de curseur, ce n'est "
                "donc pas une continuation mais une AUTRE entree")


def test_la_HAUTEUR_declaree_par_le_generateur_devient_les_bons_rangs(tmp_path):
    """L'autre bout de la chaine : `ecrire(..., hauteur_du_curseur=N)`.

    Le generateur declare une HAUTEUR et ne compte aucun rang -- il se
    tromperait au premier filet deplace. C'est `ecrire` qui retrouve le rang du
    glyphe dans la grille rendue. Ce test mesure la traduction, sur une maquette
    fabriquee pour lui : un mutant qui tronquerait la hauteur a 1 -- et il a
    SURVECU a la premiere redaction du test voisin -- fait rougir ici.
    """
    import importlib.util
    import json

    chemin = (Path(__file__).resolve().parents[3] / "_bmad-output"
              / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
              / "construire_maquette.py")
    spec = importlib.util.spec_from_file_location("construire_maquette", chemin)
    bati = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bati)

    grille = bati.maquette(
        bandeau_gauche="mmu · essai", bandeau_droite="",
        centre=["", "  Titre", "",
                f"   {jetons.GLYPHES['curseur']} Une entree      sa description",
                "                     sa suite, sans glyphe",
                "", "     Une autre        et sa description"],
        etat="", raccourcis="⏎ entrer  Q quitter")
    bati.ecrire("Z9-essai.txt", grille, dossier=tmp_path,
                hauteur_du_curseur=2)

    registre = json.loads(
        (tmp_path / bati.DECLARATIONS).read_text(encoding="utf-8"))
    assert list(registre) == ["Z9-essai"], registre
    rangs = registre["Z9-essai"]
    assert len(rangs) == 2, (
        f"la hauteur declaree vaut 2, les rangs ecrits sont {rangs}")
    lignes = (tmp_path / "Z9-essai.txt").read_text(encoding="utf-8").split("\n")
    assert lignes[rangs[0]][1:-1].strip().startswith(jetons.GLYPHES["curseur"])
    assert "sa suite" in lignes[rangs[1]], lignes[rangs[1]]


def test_une_hauteur_de_UN_n_ecrit_AUCUNE_declaration(tmp_path):
    """Le volet symetrique. Toutes les listes sont dans ce cas -- les lignes qui
    suivent le curseur y sont d'AUTRES entrees --, et le repli par motif y rend
    deja le bon resultat. Declarer partout ferait un registre que personne ne
    relit ; ne rien ecrire garde le fichier lisible d'un coup d'oeil."""
    import importlib.util

    chemin = (Path(__file__).resolve().parents[3] / "_bmad-output"
              / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
              / "construire_maquette.py")
    spec = importlib.util.spec_from_file_location("construire_maquette", chemin)
    bati = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bati)

    grille = bati.maquette(
        bandeau_gauche="mmu · essai", bandeau_droite="",
        centre=["", "  Titre", "",
                f"   {jetons.GLYPHES['curseur']} Premiere",
                "     Deuxieme", "     Troisieme"],
        etat="", raccourcis="⏎ entrer  Q quitter")
    bati.ecrire("Z8-liste.txt", grille, dossier=tmp_path)
    assert not (tmp_path / bati.DECLARATIONS).exists()


def test_R16_le_colorisateur_BORNE_ses_rangs_comme_le_produit():
    """Finding `R16`. Un rang hors grille etait avale cote maquette et levait
    cote produit : une maquette validee sur de mauvais rangs passait pour
    validee, ce qui est la seule chose que ce module existe pour empecher.

    La mesure est faite **des deux cotes**, sur la meme entree fautive : c'est
    la divergence qui est le defaut, pas l'une ou l'autre des deux reactions.
    """
    module = _colorisateur()
    texte = _grille_avec_entree_sur_trois_lignes()
    lignes = texte.split("\n")
    for mauvais in ([1, 99], [-1], [len(lignes)]):
        with pytest.raises(IndexError):
            module.peindre_maquette(texte, mauvais)
        with pytest.raises(IndexError):
            jetons.peindre(lignes, lignes_du_curseur=mauvais)


def test_R15_une_liste_VIDE_de_rangs_eteint_le_repli_des_DEUX_cotes():
    """Finding `R15`. `[]` dit « aucun rang », `None` dit « je ne declare rien ».

    Le cas se produit : une entree hors de la fenetre de defilement, un menu
    vide. Les deux comportements etaient plausibles et aucun n'etait mesure ;
    celui-ci est celui de `jetons.peindre`, dont le `is not None` fait la meme
    distinction. Le volet `None` est teste dans la foulee, sans quoi on
    mesurerait « rien n'est peint » sans savoir pourquoi.
    """
    module = _colorisateur()
    texte = _grille_avec_entree_sur_trois_lignes()
    assert _rangs_en_accent_de_la_maquette(module, texte, []) == set()
    assert _rangs_en_accent_de_la_maquette(module, texte) == {7}

    lignes = _entree_sur_trois_lignes()
    accent = "bold " + jetons.couleur("accent")
    vides = _styles_par_ligne(
        jetons.peindre(lignes, lignes_du_curseur=[]), lignes)
    assert accent not in vides
    sans = _styles_par_ligne(jetons.peindre(lignes), lignes)
    assert sans[4] == accent, "et le repli, lui, trouve toujours son rang"


def test_R17_les_DEUX_parametres_de_curseur_FUSIONNENT(tmp_path=None):
    """Mutant de la couche 2 sur `jetons.py:803`, SURVIVANT.

    `peindre` reunit deliberement `ligne_du_curseur` (un rang) et
    `lignes_du_curseur` (une suite) : le code le fait, aucun banc ne le passait.
    Un appelant qui migrerait vers la forme neuve en gardant l'ancienne pour un
    site perdrait silencieusement l'un des deux, et c'est un ecran a moitie
    teint -- le defaut meme que l'AC 6 existe pour fermer.

    On mesure l'ensemble EXACT : l'union des deux, ni plus ni moins.
    """
    lignes = _entree_sur_trois_lignes()
    peint = jetons.peindre(lignes, ligne_du_curseur=3,
                           lignes_du_curseur=range(4, 7))
    styles = _styles_par_ligne(peint, lignes)
    accent = "bold " + jetons.couleur("accent")
    teints = {rang for rang, style in enumerate(styles) if style == accent}
    assert teints == {3, 4, 5, 6}, (
        f"l'union des deux parametres, exactement : {sorted(teints)}")


# ---------------------------------------------------------------------------
# La REGLE DE COLORISATION du 2026-09-02 -- Egan, sur trois ecrans a la fois
# ---------------------------------------------------------------------------
#
# « la deuxieme ligne de ton avertissement n'est pas colorisee » (ecran 3),
# « l'avertissement n'est pas colorise [...] colorise en bleu au lieu du
# orange » (ecran 5), « cela devrait donc etre un avertissement orange plutot
# qu'une validation verte » (ecran 6). Ce n'etaient pas trois retouches mais
# UNE regle absente :
#
#   1. un avertissement se colorise ENTIEREMENT, jamais une ligne sur deux ;
#   2. la teinte suit ce que le message FAIT -- jamais bleu sur un
#      avertissement, jamais vert sur un interdit.
#
# Les bancs ci-dessous mesurent le mecanisme ; les frontieres qui mesurent les
# 80 maquettes vivent dans `verifier_maquettes.py`, que `regenerer.py` lance a
# chaque campagne.

def _batisseur():
    """`construire_maquette`, charge par son chemin comme les bancs voisins."""
    import importlib.util

    chemin = (Path(__file__).resolve().parents[3] / "_bmad-output"
              / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
              / "construire_maquette.py")
    spec = importlib.util.spec_from_file_location("construire_maquette", chemin)
    bati = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bati)
    return bati


def _verificateur():
    """`verifier_maquettes`, charge de meme."""
    import importlib.util

    chemin = (Path(__file__).resolve().parents[3] / "_bmad-output"
              / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
              / "verifier_maquettes.py")
    spec = importlib.util.spec_from_file_location("verifier_maquettes", chemin)
    verif = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verif)
    return verif


def _grille_de_cartouche(bati, motif="▲", suite="  la suite du message"):
    """Une grille dont le cartouche porte un message d'etat sur DEUX lignes."""
    return bati.maquette(
        bandeau_gauche="mmu · essai", bandeau_droite="",
        centre=["", *bati.cartouche("Un panneau", [
            "Fait                une valeur",
            "",
            f"{motif} un message qui deborde de la largeur du",
            suite,
        ]), "", "     Une issue"],
        etat="", raccourcis="⏎ entrer  Q quitter")


def test_un_glyphe_dans_un_CARTOUCHE_reste_BLANC_sans_declaration():
    """Le defaut qu'Egan a nomme sur l'ecran 5, mesure a sa racine.

    Dans un cartouche le glyphe est precede de la bordure et d'UN blanc : il
    n'ouvre pas de colonne, donc `jetons.jeton_d_etat` ne le voit pas et le
    repli par motif laisse l'avertissement en blanc. Ce banc fige l'etat SANS
    declaration -- c'est le volet symetrique de celui qui suit, et sans lui la
    correction pourrait etre verte sans avoir rien ferme.
    """
    module = _colorisateur()
    bati = _batisseur()
    grille = _grille_de_cartouche(bati)
    peint = module.peindre_maquette(grille)
    lignes = grille.rstrip("\n").split("\n")
    rang = next(r for r, l in enumerate(lignes) if "un message qui deborde" in l)
    couleurs = {c for m, c, _ in peint[rang] if m.strip("│ ")}
    assert jetons.couleur("state-substitute") not in couleurs, (
        "sans declaration, le repli par motif ne peut PAS voir ce glyphe")


def test_un_avertissement_de_CARTOUCHE_est_colorise_EN_ENTIER_quand_il_est_declare():
    """La regle, point 1. Les DEUX lignes prennent l'orange, la continuation
    comprise -- elle ne porte par construction aucun glyphe."""
    module = _colorisateur()
    bati = _batisseur()
    grille = _grille_de_cartouche(bati)
    lignes = grille.rstrip("\n").split("\n")
    tete = next(r for r, l in enumerate(lignes) if "un message qui deborde" in l)
    peint = module.peindre_maquette(
        grille, etats={tete: "substitute", tete + 1: "substitute"})
    orange = jetons.couleur("state-substitute")
    for rang in (tete, tete + 1):
        couleurs = {c for m, c, _ in peint[rang] if m.strip("│ ")}
        assert couleurs == {orange}, (rang, couleurs)


def test_la_HAUTEUR_d_un_message_declaree_par_le_generateur_devient_les_bons_rangs(tmp_path):
    """L'autre bout de la chaine : `ecrire(..., hauteurs_de_message=...)`.

    Meme geste que `hauteur_du_curseur` -- le generateur declare une HAUTEUR et
    ne compte aucun rang. Un mutant qui tronquerait la hauteur a 1 rend ici le
    message colorise une ligne sur deux, c'est-a-dire le defaut d'origine.
    """
    import json

    bati = _batisseur()
    bati.ecrire("Z7-message.txt", _grille_de_cartouche(bati), dossier=tmp_path,
                hauteurs_de_message={"un message qui deborde": 2})
    registre = json.loads(
        (tmp_path / bati.ETATS_DECLARES).read_text(encoding="utf-8"))
    rangs = registre["Z7-message"]
    lignes = (tmp_path / "Z7-message.txt").read_text(
        encoding="utf-8").split("\n")
    tete = next(r for r, l in enumerate(lignes) if "un message qui deborde" in l)
    assert rangs[str(tete)] == "substitute"
    assert rangs[str(tete + 1)] == "substitute", (
        "la continuation n'est pas declaree : le message serait colorise une "
        "ligne sur deux, ce qu'Egan a refuse sur trois ecrans")


def test_un_fragment_de_message_INTROUVABLE_leve(tmp_path):
    """Une declaration qui ne designe rien est une erreur d'appariement -- la
    famille que la regle des fabriques existe pour attraper, et qui ne se voit
    jamais a l'oeil. Le refus est donc dur, comme celui de `jetons.peindre`."""
    bati = _batisseur()
    with pytest.raises(ValueError):
        bati.ecrire("Z6-absent.txt", _grille_de_cartouche(bati),
                    dossier=tmp_path,
                    hauteurs_de_message={"un texte qui n'y est pas": 2})


def test_l_etat_DONNE_ne_passe_PAS_devant_le_curseur():
    """Le meme ORDRE que `jetons.peindre`, et il n'est pas negociable.

    Cote produit, la ligne du curseur passe avant l'etat donne. Une maquette qui
    inverserait les deux ferait valider un rendu que le produit ne saura pas
    poser -- et c'est ce qui a fait descendre l'avertissement de l'ecran 5 sur sa
    PROPRE ligne plutot que de le laisser sur la ligne du choix.
    """
    module = _colorisateur()
    bati = _batisseur()
    grille = bati.maquette(
        bandeau_gauche="mmu · essai", bandeau_droite="",
        centre=["", "  Titre", "",
                f"   {jetons.GLYPHES['curseur']} Remplacer      ▲ efface tout"],
        etat="", raccourcis="⏎ entrer  Q quitter")
    lignes = grille.rstrip("\n").split("\n")
    rang = next(r for r, l in enumerate(lignes) if "Remplacer" in l)
    peint = module.peindre_maquette(grille, lignes_du_curseur=[rang],
                                    etats={rang: "substitute"})
    couleurs = {c for m, c, _ in peint[rang] if m.strip("│ ")}
    assert couleurs == {jetons.couleur("accent")}, couleurs


def test_la_frontiere_rougit_sur_une_VALIDATION_VERTE_dans_un_ecran_qui_REFUSE():
    """La regle, point 2 : « jamais vert sur un interdit ».

    C'est cette frontiere qui a TROUVE l'ecran 6 -- elle a rougi sur
    `E5-3c` avant qu'on ait relu la note d'Egan, et sur lui seul.
    """
    bati, verif = _batisseur(), _verificateur()
    grille = bati.maquette(
        bandeau_gauche="mmu · essai", bandeau_droite="",
        centre=["", *bati.cartouche("Un panneau", [
            "Scanné              ● oui            hier",
        ]), "", "     Annuler"],
        etat="✕  Remplacer n'est pas offert — ce tirage a été scanné",
        raccourcis="⏎ entrer  Q quitter")
    defauts = verif.verifier_la_colorisation(
        grille.rstrip("\n").split("\n")[:verif.HAUTEUR], {})
    assert any("VERTE" in d for d in defauts), defauts

    # Volet symetrique : la MEME grille en orange ne rougit plus. Sans lui, une
    # frontiere qui rougirait toujours passerait pour juste.
    saine = grille.replace("● oui", "▲ oui")
    assert not [d for d in verif.verifier_la_colorisation(
        saine.rstrip("\n").split("\n")[:verif.HAUTEUR], {}) if "VERTE" in d]


def test_la_frontiere_rougit_sur_un_AVERTISSEMENT_de_cartouche_NON_declare():
    """La regle, point 1, mesuree sur la maquette et non sur son rendu : un
    glyphe qu'aucun repli ne peut voir et qu'aucune declaration ne porte
    resterait sans couleur. C'est le defaut de l'ecran 5, et il valait pour 27
    lignes de 17 maquettes le jour ou la frontiere a ete ecrite."""
    bati, verif = _batisseur(), _verificateur()
    grille = _grille_de_cartouche(bati)
    lignes = grille.rstrip("\n").split("\n")[:verif.HAUTEUR]
    tete = next(r for r, l in enumerate(lignes) if "un message qui deborde" in l)
    assert any("AUCUN repli" in d
               for d in verif.verifier_la_colorisation(lignes, {}))
    # Declare, il ne rougit plus -- volet symetrique.
    assert not verif.verifier_la_colorisation(
        lignes, {str(tete): "substitute", str(tete + 1): "substitute"})
