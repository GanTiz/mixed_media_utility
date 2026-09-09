# -*- coding: utf-8 -*-
"""Story 11.1, AC 2 -- le MODELE d'edition d'un nom : refus, jamais troncature.

**Ce banc devait disparaitre avec la story 11.4e, lot G4** (`EPIC11-ARB-141` :
« On retire l'edition des noms PARTOUT ou elle ne peut pas etre effective »).
Il survit pour une raison mesuree et non par prudence : `NomEditable` et
`ModeleNoms` sont encore importes par `tui/execution.py`, l'ecran partage par
les quatre ateliers, qui porte le mode d'edition lui-meme. Ce fichier
appartenait a un autre lot ; la regle de decoupage interdit de l'ouvrir.

**Le modele est donc du code vivant que plus aucun ecran n'atteint** -- aucun
atelier ne lui donne de nom depuis le lot G, et `EcranChiffre` en pose un vide.
Retirer ses tests laisserait 319 lignes importables sans mesure : ils restent,
et l'ecart est verse a `deferred-work.md` (« Laisse ouvert par les lots G et H
de la 11.4e »), tenu par un ensemble EXACT d'importateurs dans
`test_aucun_nom_editable.py` qui rougira le jour du nettoyage.

**Ce qui a QUITTE ce fichier**, et c'etait le seul risque nomme du lot G : les
quatre tests d'AC 2.4 -- `tui.noms.LIMITE` **est**
`io.naming.CANONICAL_ID_MAX_LENGTH`, le litteral compte a zero ailleurs, et le
volet symetrique. Ils vivent desormais dans `test_aucun_nom_editable.py`, qui
survivra au retrait du modele. Les y laisser aussi aurait fait deux redactions
de la meme frontiere, c'est-a-dire deux qui divergeront.
"""

from pathlib import Path

import pytest

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.noms import (
    LIMITE,
    MOTIF_CARACTERES,
    MOTIF_VIDE,
    ModeleNoms,
    NomEditable,
    motif_de_longueur,
)


def fabrique_de_noms(combien: int = 2) -> ModeleNoms:
    """Au moins DEUX noms, tous differents (regle des fabriques).

    Un modele mono-nom rendrait `↑↓`, « tous valides » et « la cible n'est pas
    la premiere » inobservables -- ce sont precisement les trois defauts que la
    regle des fabriques du depot a payes trois fois.
    """
    return ModeleNoms([NomEditable(f"projet_demo_rush_0{rang}_25fps")
                       for rang in range(1, combien + 1)])


# --------------------------------------------------------------------------
# AC 2.3 -- refus, et JAMAIS troncature
# --------------------------------------------------------------------------

def test_une_saisie_de_cinquante_caracteres_en_rend_cinquante():
    """Le coeur de l'AC : la valeur n'est pas coupee, elle est refusee."""
    nom = NomEditable("court")
    nom.saisir("a" * 50)
    assert len(nom.valeur) == 50
    assert nom.valide is False
    assert nom.motif == motif_de_longueur(50)


def test_le_compteur_depasse_la_limite_au_lieu_de_s_y_coller():
    """AC 2.2 : afficher `48/48` sur 50 caracteres serait la troncature, en
    affichage. Le compteur dit ce qui est SAISI."""
    nom = NomEditable("court")
    nom.saisir("a" * 50)
    assert nom.compteur == "50/48"


@pytest.mark.parametrize("longueur,valide", [
    (47, True), (48, True), (49, False)])
def test_la_limite_est_inclusive(longueur, valide):
    """`>` et non `>=` : les trois longueurs encadrent la borne."""
    nom = NomEditable("court")
    nom.saisir("a" * longueur)
    assert nom.valide is valide


def test_le_motif_du_refus_MESURE_le_depassement_et_ne_justifie_PAS_la_regle():
    """**Ce test disait exactement l'inverse jusqu'au lot I**, et c'est la
    tension `EPIC11-ARB-25` / `EPIC11-ARB-56` tranchee.

    Il exigeait « meme prefixe » et « meme lot » dans le motif, c'est-a-dire la
    justification de la regle -- un **motif de conception**, que l'`ARB-56`
    interdit verbatim en ligne d'etat : elle « ne porte **aucune touche** [...]
    **aucun conseil d'usage** [...] **aucun motif de conception** ». Ce que
    l'`ARB-25` exige, lui, est autre chose : « le message nomme le motif au lieu
    de dire « invalide » ». Nommer le motif, c'est dire *trop long*, avec de
    combien -- pas expliquer pourquoi la regle existe.

    Egan l'avait deja tranche sur la maquette `E2-3c` : « On se contente de dire
    que le nom est trop long. Pas de justification. »
    """
    motif = motif_de_longueur(50)
    assert MOTIF_DESSINE_DU_REFUS in motif
    assert "invalide" not in motif.lower()
    # La MESURE, des deux cotes : ce qui est saisi, et ce qui est admis.
    assert "50" in motif and str(LIMITE) in motif
    # Et plus aucune justification de la regle.
    assert "prefixe" not in motif and "préfixe" not in motif


def test_le_motif_du_refus_est_ACCENTUE_et_se_replie_en_ascii():
    """Finding `I6` : une chaine desaccentuee a la source rend le MEME texte
    dans les deux regimes, ce qui court-circuite `jetons.REPLIS_DE_TEXTE`.

    Les trois motifs sont mesures ensemble, et le volet symetrique est que le
    repli change quelque chose -- sans quoi le test serait vert sur une source
    restee sans accents.
    """
    for motif in (motif_de_longueur(50), MOTIF_CARACTERES, MOTIF_VIDE):
        replie = jetons.replier_ascii(motif)
        assert replie.isascii(), motif
        assert replie != motif, ("motif ecrit sans accents dans la source",
                                 motif)


@pytest.mark.parametrize("motif", [motif_de_longueur(50), MOTIF_CARACTERES,
                                   MOTIF_VIDE])
def test_chaque_motif_tient_dans_la_ligne_d_etat(motif):
    """**Le motif le plus long faisait 145 colonnes pour 76.**

    La zone est haute d'une ligne et `textual` ne tronque pas : il replie, et la
    seconde ligne n'est jamais dessinee. L'operateur lisait « Deux noms coupes
    au » -- la phrase s'arretait **juste avant sa consequence**, qui est la
    seule chose qu'elle existe pour dire. Le test qui la couvrait assertait une
    sous-chaine situee dans la partie invisible : il mesurait la chaine, pas la
    grille (revue de vague 1, couche 1).
    """
    assert jetons.colonnes(motif) <= jetons.largeur_utile(), (
        jetons.colonnes(motif), motif)


@pytest.mark.parametrize("saisie", [
    "avec espace", "accentue-é", "point.virgule", "slash/dedans", "*"])
def test_les_caracteres_hors_schema_sont_refuses(saisie):
    nom = NomEditable("court")
    nom.saisir(saisie)
    assert nom.motif == MOTIF_CARACTERES
    # Et la valeur n'a pas ete nettoyee : elle est rendue telle que tapee.
    assert nom.valeur == saisie


def test_un_nom_vide_est_refuse_par_son_propre_motif():
    nom = NomEditable("court")
    nom.saisir("")
    assert nom.motif == MOTIF_VIDE


def test_un_nom_trop_long_ET_mal_forme_est_d_abord_trop_long():
    """L'ordre des motifs suit ce qu'il faut corriger en premier : raccourcir
    peut suffire, l'inverse n'est pas vrai."""
    nom = NomEditable("court")
    nom.saisir("a b" * 20)
    assert nom.motif == motif_de_longueur(60)


@pytest.mark.parametrize("saisie", [
    "projet_demo_rush_01_25fps", "a", "A-B_c-9", "lot--double-tiret"])
def test_les_noms_conformes_passent(saisie):
    """Volet symetrique des refus : sans lui, un validateur qui refuserait
    TOUT serait vert sur tous les tests ci-dessus."""
    nom = NomEditable("court")
    nom.saisir(saisie)
    assert nom.motif is None


# --------------------------------------------------------------------------
# AC 2.1 -- le parcours d'edition
# --------------------------------------------------------------------------

def test_le_curseur_parcourt_les_noms_sans_boucler():
    modele = fabrique_de_noms(3)
    modele.descendre()
    modele.descendre()
    assert modele.curseur == 2
    modele.descendre()
    assert modele.curseur == 2, "le dernier nom reste le dernier"
    modele.monter()
    assert modele.curseur == 1


def test_la_cible_editee_n_est_pas_la_premiere():
    """Regle des fabriques : un modele qui editerait toujours le premier nom ne
    se demasque qu'en visant ailleurs."""
    modele = fabrique_de_noms(3)
    modele.descendre()
    modele.descendre()
    modele.saisir("nom_du_troisieme")
    assert modele.valeurs == ["projet_demo_rush_01_25fps",
                              "projet_demo_rush_02_25fps",
                              "nom_du_troisieme"]


def test_r_remet_le_nom_conventionnel_du_nom_courant_seulement():
    modele = fabrique_de_noms(2)
    modele.saisir("premier_modifie")
    modele.descendre()
    modele.saisir("second_modifie")
    modele.remettre()
    assert modele.valeurs == ["premier_modifie", "projet_demo_rush_02_25fps"]


def test_echap_rend_les_valeurs_qu_elles_avaient_a_l_entree_en_edition():
    """AC 2.1 : « sans modifier les valeurs » ne veut pas dire « sans avoir
    tape ». C'est la sauvegarde prise a l'entree qui rend l'abandon vrai."""
    modele = fabrique_de_noms(2)
    modele.saisir("valeur_gardee_avant_edition")
    modele.entrer_en_edition()
    modele.saisir("saisie_abandonnee")
    modele.descendre()
    modele.saisir("autre_saisie_abandonnee")
    modele.abandonner()
    assert modele.valeurs == ["valeur_gardee_avant_edition",
                              "projet_demo_rush_02_25fps"]
    assert modele.en_edition is False


def test_valider_l_edition_garde_ce_qui_a_ete_tape():
    """Volet symetrique de l'abandon : sans lui, une sauvegarde restauree a
    tort serait invisible."""
    modele = fabrique_de_noms(2)
    modele.entrer_en_edition()
    modele.saisir("nom_choisi_par_l_operateur")
    modele.confirmer()
    assert modele.valeurs[0] == "nom_choisi_par_l_operateur"
    assert modele.en_edition is False


def test_un_seul_nom_refuse_suffit_a_invalider_l_ensemble():
    """Un panneau qui n'examinerait que le nom sous le curseur laisserait
    passer un nom refuse edite plus tot."""
    modele = fabrique_de_noms(3)
    modele.descendre()
    modele.saisir("a" * 60)
    modele.monter()
    assert modele.courant.valide is True
    assert modele.valides is False
    assert set(modele.motifs) == {1}


def test_le_nom_modifie_se_distingue_du_nom_conventionnel():
    nom = NomEditable("projet_demo_rush_01_25fps")
    assert nom.modifie is False
    nom.saisir("autre_nom")
    assert nom.modifie is True
    nom.remettre()
    assert nom.modifie is False


# --------------------------------------------------------------------------
# Revue vague 2 bis -- la borne HAUTE de la ligne d'un nom
#
# `creux = largeur - _colonnes(gauche) - len(compteur)` puis `max(2, creux)` :
# la borne basse etait tenue, la haute manquait, et le compteur etait mesure en
# CARACTERES. Chiffres mesures sur le cartouche du plancher (72 colonnes) avant
# correction, dans les DEUX modes :
#
#     valeur = 61 colonnes             -> ligne = 72  ok
#     valeur = 62 colonnes             -> ligne = 73  DEBORDE (`...  62/…`)
#     valeur = 61 colonnes en EDITION  -> ligne = 73  DEBORDE (le caret coute 1)
#     valeur = 31 ideogrammes (62 col) -> ligne = 73  DEBORDE, compteur `31/48`
#     valeur = 33 ideogrammes (66 col) -> ligne = 77  DEBORDE
#
# Le garde-fou `jetons.ajuster` coupait par la FIN : le compteur `n/48` -- la
# seule chose qui dit POURQUOI le nom est refuse -- disparaissait exactement
# quand le nom devient trop long, c'est-a-dire au seul moment ou il sert.
#
# Le cas en double chasse est celui qui compte : 31 caracteres pour 62
# colonnes, alors que le compteur affiche `31/48`. Une borne posee sur `len()`
# le croirait a l'aise.
# --------------------------------------------------------------------------

#: La largeur ecrivable d'un cartouche au plancher. Ecrite en clair EN PLUS de
#: la deduction : une constante comparee a elle-meme ne mesurerait rien.
CARTOUCHE = jetons.largeur_de_cartouche(80)

#: Deux valeurs qui **debordent**, et une qui tient. La double chasse est la
#: seule des trois dont `len()` et `colonnes()` different.
VALEUR_COURTE = "ingest_hiver"
VALEUR_LONGUE = "ingest_hiver_2026_camera_B_prise_02_bis_v3_relecture_finale_ok"
VALEUR_IDEOGRAMMES = "日" * 31


def fabrique_de_noms_larges(cible: str) -> ModeleNoms:
    """Trois noms, la CIBLE en position 1 -- jamais la premiere.

    Regle des fabriques du depot : les trois valeurs sont deux a deux
    distinctes et de largeurs differentes, si bien qu'une ligne qui rendrait
    toujours celle du premier nom, ou qui abregerait tout le monde, se
    demasque. Le curseur est pose sur la cible : c'est le seul rang qui porte
    l'invite et, en edition, le caret.
    """
    modele = ModeleNoms([NomEditable(VALEUR_COURTE),
                         NomEditable(cible),
                         NomEditable("ingest_ete_2026")])
    modele.curseur = 1
    return modele


@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("en_edition", [False, True])
@pytest.mark.parametrize("valeur", [VALEUR_LONGUE, VALEUR_IDEOGRAMMES])
def test_une_valeur_trop_longue_cede_AVANT_le_compteur(valeur, en_edition,
                                                       ascii_seul):
    """La ligne tient le cartouche, et le compteur `n/48` reste ENTIER.

    Une assertion de simple largeur resterait verte sur une correction qui
    abregerait le compteur : c'est lui que le garde-fou mangeait, donc c'est
    sur lui que porte la seconde assertion.
    """
    assert CARTOUCHE == 72, CARTOUCHE
    modele = fabrique_de_noms_larges(valeur)
    modele.en_edition = en_edition
    ligne = modele.ligne(1, CARTOUCHE, ascii_seul=ascii_seul)

    assert jetons.colonnes(ligne) <= CARTOUCHE, (
        f"ascii={ascii_seul}, edition={en_edition} : "
        f"{jetons.colonnes(ligne)} colonnes pour {CARTOUCHE} -- {ligne!r}")
    assert ligne.endswith(f"{len(valeur)}/{LIMITE}"), (
        "le compteur est la seule chose qui dit POURQUOI le nom est refuse ; "
        f"il ne doit jamais etre mange -- {ligne!r}")
    # Volet symetrique : la fixture ATTEINT le defaut. Sans cette mesure, une
    # valeur courte rendrait les deux assertions ci-dessus vertes sans rien
    # mesurer.
    assert jetons.colonnes(valeur) > CARTOUCHE - 4 - 2 - len(f"{len(valeur)}/{LIMITE}"), (
        f"la fixture doit deborder -- {jetons.colonnes(valeur)} colonnes")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_ligne_d_un_nom_mesure_en_COLONNES_et_non_en_caracteres(ascii_seul):
    """Le mutant « mesurer en `len()` » meurt ici.

    31 ideogrammes : le compteur affiche `31/48`, donc la moitie de la limite,
    et la valeur occupe pourtant 62 colonnes. Une borne posee sur `len()` la
    croirait a l'aise et laisserait la ligne deborder de six colonnes -- le
    defaut ne se voit QUE sur de la double chasse.
    """
    assert jetons.colonnes(VALEUR_IDEOGRAMMES) == 2 * len(VALEUR_IDEOGRAMMES), (
        "la fixture doit porter de la double chasse, sans quoi `len()` et "
        f"`colonnes()` sont le meme test -- {VALEUR_IDEOGRAMMES!r}")
    assert len(VALEUR_IDEOGRAMMES) < LIMITE, (
        "et elle doit rester SOUS la limite du schema : le defaut mord sur un "
        "nom que le compteur presente comme acceptable")

    modele = fabrique_de_noms_larges(VALEUR_IDEOGRAMMES)
    ligne = modele.ligne(1, CARTOUCHE, ascii_seul=ascii_seul)
    assert jetons.colonnes(ligne) <= CARTOUCHE, (
        jetons.colonnes(ligne), len(ligne), ligne)
    assert ligne.endswith(f"{len(VALEUR_IDEOGRAMMES)}/{LIMITE}"), ligne


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_caret_survit_a_l_abregement_de_la_valeur(ascii_seul):
    """En edition, le caret dit OU l'on tape : il se reserve avant d'abreger.

    Sans cette reserve, la ligne d'un nom en cours de frappe tenait la largeur
    en perdant le caret -- l'operateur ne voyait plus le curseur au moment
    precis ou il depasse.
    """
    modele = fabrique_de_noms_larges(VALEUR_LONGUE)
    modele.en_edition = True
    ligne = modele.ligne(1, CARTOUCHE, ascii_seul=ascii_seul)
    caret = jetons.glyphes(ascii_seul)["caret"]
    gauche = ligne.rstrip().rsplit("  ", 1)[0]
    assert gauche.endswith(caret), (
        f"le caret doit rester le dernier signe de la valeur -- {ligne!r}")
    assert jetons.colonnes(ligne) <= CARTOUCHE, (jetons.colonnes(ligne), ligne)
    # Volet symetrique : hors edition la valeur ne se termine PAS par le
    # caret, sinon l'assertion ci-dessus serait vraie d'une ligne qui en
    # porterait toujours un. La comparaison porte sur la fin de la valeur et
    # non sur sa presence : en `--ascii` le caret est `_`, qui figure dans tout
    # nom de rush ordinaire.
    modele.en_edition = False
    hors_edition = modele.ligne(1, CARTOUCHE, ascii_seul=ascii_seul)
    assert not hors_edition.rstrip().rsplit("  ", 1)[0].endswith(caret), (
        hors_edition)
    assert hors_edition != ligne, (hors_edition, ligne)


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_un_nom_qui_tient_n_est_PAS_abrege(ascii_seul):
    """Volet symetrique de tout ce qui precede : la borne haute ne mord que
    quand elle doit. Une correction qui abregerait tous les noms passerait
    toutes les mesures de largeur ci-dessus."""
    modele = fabrique_de_noms_larges(VALEUR_LONGUE)
    points = "..." if ascii_seul else "…"
    # Le rang 0 porte la valeur courte ; le rang 1, la longue.
    courte = modele.ligne(0, CARTOUCHE, ascii_seul=ascii_seul)
    longue = modele.ligne(1, CARTOUCHE, ascii_seul=ascii_seul)
    assert VALEUR_COURTE in courte, courte
    assert points not in courte, courte
    assert points in longue, longue
    # Et le nom abrege garde ses DEUX bouts : `_camera_A` et `_camera_B`
    # coupes par la fin rendraient la meme ligne.
    assert VALEUR_LONGUE[:8] in longue, longue
    assert longue.split("  ")[0].endswith(VALEUR_LONGUE[-6:]), longue


# ===========================================================================
# La maquette que ce banc citait sans la LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E2-3c` en verbatim
# d'Egan -- « On se contente de dire que le nom est trop long » -- et
# n'ouvrait pas le dessin. C'est le cas ou la recopie trompe le plus : la
# citation a l'air d'une source.

#: Le motif que `E2-3c` dessine (l. 14 : « ✕ Le nom est trop long : 50
#: caractères pour 48 admis. »). Confronte a sa source ci-dessous.
MOTIF_DESSINE_DU_REFUS = "trop long"

#: Les dessins repris ici, a leur source.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕▓▒░█"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_le_MOTIF_du_refus_est_celui_que_E2_3c_dessine_avec_SES_DEUX_nombres():
    """Le motif ET la borne, a leur source -- et la borne se lit dans le CODE.

    `CLAUDE.md` porte trois fois la trace d'une borne citee de memoire et
    fausse (64 puis 48). Elle n'est donc ecrite ni ici ni dans le brief : le
    test lit `LIMITE`, le dessin porte le meme nombre, et l'egalite est la
    mesure. Le jour ou la borne bouge, c'est le DESSIN qui rougit -- ce qui
    est exactement ce qu'on veut d'une maquette approuvee.
    """
    dessin = dessin_de_la_maquette("E2-3c-extraction-nom-refuse.txt")
    assert MOTIF_DESSINE_DU_REFUS in dessin
    assert f"{LIMITE} admis" in dessin

    # Le nombre saisi, l'autre cote de la mesure : le dessin montre un
    # depassement, pas un cas limite.
    assert "50 caractères" in dessin
    assert 50 > LIMITE


def test_le_dessin_NE_JUSTIFIE_PAS_la_regle_et_c_est_l_arbitrage_mesure():
    """`EPIC11-ARB-56` en frontiere negative, sur le dessin plutot que sur le
    rendu.

    Le test ci-dessus mesure que le motif est NOMME ; celui-ci mesure que le
    dessin ne porte aucune des justifications que l'`ARB-56` interdit. Les
    deux ensemble disent « ce qui est dit » et « ce qui ne l'est pas », et
    l'un sans l'autre laisse passer une ligne d'etat bavarde.
    """
    dessin = dessin_de_la_maquette("E2-3c-extraction-nom-refuse.txt")
    for justification in ("meme prefixe", "même préfixe", "parce que",
                          "invalide", "conception"):
        assert justification not in dessin.lower(), justification


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    dessin = dessin_de_la_maquette("E2-3c-extraction-nom-refuse.txt")
    assert "trop courte" not in dessin
    assert "64 admis" not in dessin
