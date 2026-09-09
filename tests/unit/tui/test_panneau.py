# -*- coding: utf-8 -*-
"""Story 11.1, AC 1 et AC 7 -- le panneau chiffre et le choix exclusif."""

import pytest

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.panneau import (
    MENTION_MAJORANT,
    ChoixExclusif,
    Issue,
    LigneChiffree,
    Panneau,
    PanneauMalForme,
)


def fabrique_d_issues(combien: int = 3) -> list[Issue]:
    """Trois issues DISTINGUABLES, dont une seule ecrit.

    Un jeu uniforme -- trois issues qui ecrivent, ou trois libelles identiques
    -- rendrait invisible une liste indexee de travers, qui rendrait « annuler »
    a la place d'« ecraser ». C'est le defaut nomme dans les notes de la fiche.
    """
    toutes = [Issue("ecrire", "Ecrire les frames", ecrit=True),
              Issue("modifier", "Modifier les reglages"),
              Issue("annuler", "Annuler")]
    return toutes[:combien]


def fabrique_de_panneau() -> Panneau:
    """Un panneau qui porte a la fois une valeur MESUREE et une ESTIMEE.

    Les deux sont necessaires ensemble : c'est leur coexistence que l'AC 1.2
    demande de distinguer a l'affichage.
    """
    return Panneau("A ecrire", [
        LigneChiffree("Lots crees", 2, "lots"),
        LigneChiffree("Frames ecrites", 186, "frames"),
        LigneChiffree("Bornes", "00:00:04:12 -> 00:00:09:08"),
        LigneChiffree("Espace disque", "~ 3,1", "Go", majorant=True),
    ], noms=["projet_demo_rush_01_25fps", "projet_demo_rush_01_12p5"])


# --------------------------------------------------------------------------
# AC 1.2 -- toute unite, tout majorant
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valeur", [2, 186, 0, 3.1, -1])
def test_un_chiffre_sans_unite_est_refuse_a_la_construction(valeur):
    """Le refus a la construction rend le defaut IMPOSSIBLE, pas improbable.

    Signale en revue, il aurait a etre retrouve dans chacun des quatre
    ateliers ; refuse ici, il ne peut pas naitre.
    """
    with pytest.raises(PanneauMalForme, match="sans unite"):
        LigneChiffree("Lots crees", valeur)


@pytest.mark.parametrize("valeur", [
    "00:00:04:12 -> 00:00:09:08", "projet_demo/frames/", "16 bits"])
def test_une_valeur_TEXTE_n_exige_pas_d_unite(valeur):
    """Volet symetrique : un timecode ou un chemin n'a pas d'unite, et une
    garde qui l'exigerait rendrait le panneau inecrivable."""
    assert LigneChiffree("Bornes", valeur).unite is None


def test_le_majorant_porte_son_mot_et_le_mesure_ne_le_porte_pas():
    """AC 1.2 : les deux se distinguent a l'AFFICHAGE, pas dans le modele."""
    mesure = LigneChiffree("Frames ecrites", 186, "frames")
    estime = LigneChiffree("Espace disque", "~ 3,1", "Go", majorant=True)
    assert MENTION_MAJORANT not in mesure.rendu()
    assert MENTION_MAJORANT in estime.rendu()
    assert mesure.rendu().rstrip().endswith("186 frames")


def test_un_seul_mot_de_majorant_existe():
    """Deux formulations d'un ecran a l'autre rendraient la distinction
    illisible la ou elle compte."""
    panneau = fabrique_de_panneau()
    marques = [l for l in panneau.rendu() if MENTION_MAJORANT in l]
    assert len(marques) == 1
    assert panneau.porte_un_majorant is True


# --------------------------------------------------------------------------
# AC 1.1 -- la forme du panneau
# --------------------------------------------------------------------------

def test_le_libelle_est_a_gauche_et_le_chiffre_a_droite():
    ligne = LigneChiffree("Frames ecrites", 186, "frames").rendu(80)
    assert ligne.startswith("Frames ecrites")
    assert ligne.endswith("186 frames")
    # En COLONNES, jamais en caracteres : c'est l'unite du depot, et un
    # `len()` ici serait la mesure exacte que le defaut de ce module
    # exploitait. Le 72 est ecrit en clair EN PLUS de la deduction -- une
    # constante comparee a elle-meme ne mesurerait rien.
    assert jetons.colonnes(ligne) == jetons.largeur_de_cartouche(80) == 72


@pytest.mark.parametrize("fenetre,utile", [(80, 72), (120, 112)])
def test_la_ligne_suit_la_largeur_de_la_fenetre(fenetre, utile):
    """Le cartouche porte SON cadre en plus de celui de l'ecran : ce sont
    quatre colonnes de plus qui partent, et les compter une seule fois ferait
    deborder chaque ligne de deux."""
    assert jetons.colonnes(
        LigneChiffree("Lots", 2, "lots").rendu(fenetre)) == utile


def test_une_ligne_trop_longue_garde_deux_espaces_de_creux():
    """Coller le chiffre au libelle rendrait la ligne illisible EN PLUS d'etre
    trop longue -- deux defauts au lieu d'un.

    **Le libelle ne finit PAS par une espace, et c'est tout le test.** La
    premiere redaction employait `"... long " * 3`, dont l'espace finale rendait
    l'assertion vraie avec ET sans le garde-fou : le test etait inerte, mesure
    par la revue de vague 1 (couche 2). Le libelle ci-dessous se termine sur une
    lettre, donc les deux espaces ne peuvent venir que du creux minimal.
    """
    libelle = "Un-libelle-deraisonnablement-long-qui-ne-finit-pas-par-une-espace"
    ligne = LigneChiffree(libelle, 1, "lot").rendu()
    assert ligne == libelle + "  1 lot"
    assert not libelle.endswith(" "), "sinon le test ne mesure rien"
    # **Et ce libelle ne deborde PAS** : 65 colonnes plus le creux plus
    # `1 lot` font exactement 72. Ce test mesure la borne BASSE du creux, et
    # elle seule -- il ne pouvait pas voir la borne haute manquante, qui est le
    # defaut trouve a la vague 2 bis. La distinction est ecrite ici pour que la
    # prochaine lecture ne le prenne pas pour une garde de debordement.
    assert jetons.colonnes(ligne) == jetons.largeur_de_cartouche(80)


def test_les_noms_viennent_en_dernier_apres_une_ligne_vide():
    """AC 1.1 : un bloc editable au milieu d'un tableau de chiffres se cherche."""
    rendu = fabrique_de_panneau().rendu()
    assert rendu[-2:] == ["projet_demo_rush_01_25fps", "projet_demo_rush_01_12p5"]
    assert rendu[-3] == ""
    assert all("projet_demo" not in ligne for ligne in rendu[:-2])


def test_un_panneau_sans_nom_ne_pose_pas_de_ligne_vide_orpheline():
    panneau = Panneau("A ecrire", [LigneChiffree("Lots", 2, "lots")])
    assert panneau.rendu() == [LigneChiffree("Lots", 2, "lots").rendu()]


# --------------------------------------------------------------------------
# AC 7 -- le choix exclusif
# --------------------------------------------------------------------------

def test_aucune_issue_n_est_retenue_au_depart():
    """`EPIC11-ARB-7`, dans sa forme d'apres `EPIC11-ARB-45`.

    Le modele ne porte **aucune retenue au montage** : c'est ce qui empeche un
    ecran de se dessiner avec une issue deja cochee. Ce qui change avec
    `ARB-45`, c'est que la validation retient au lieu d'exiger un geste de plus
    -- la protection contre l'accident est passee au panneau chiffre, et elle
    est mesuree la (voir `test_aucune_issue_qui_ECRIT_n_est_a_une_frappe`).
    """
    choix = ChoixExclusif(fabrique_d_issues())
    assert choix.retenue is None


def test_une_preselection_est_refusee_a_la_construction():
    with pytest.raises(PanneauMalForme, match="preselection"):
        ChoixExclusif(fabrique_d_issues(), retenue="ecrire")


@pytest.mark.parametrize("combien", [0, 1])
def test_un_point_de_decision_porte_au_moins_deux_issues(combien):
    """AC 7.2 : un cartouche sans issue est un defaut -- un point de decision
    sans decision possible est un constat, et un constat va en ligne d'etat."""
    with pytest.raises(PanneauMalForme, match="deux issues"):
        ChoixExclusif(fabrique_d_issues(combien))


def test_deux_issues_de_meme_cle_sont_refusees():
    doublon = [Issue("annuler", "Annuler"), Issue("annuler", "Abandonner")]
    with pytest.raises(PanneauMalForme, match="meme cle"):
        ChoixExclusif(doublon)


def test_parcourir_n_ECRIT_toujours_rien_dans_le_modele():
    """Deplacer le curseur ne retient toujours rien : seule la validation le
    fait. Sans cette propriete, un simple parcours laisserait derriere lui une
    retenue qu'un autre chemin de code pourrait suivre."""
    choix = ChoixExclusif(fabrique_d_issues())
    choix.deplacer(1)
    choix.deplacer(1)
    assert choix.curseur == 2
    assert choix.retenue is None


def test_la_validation_RETIENT_et_suit_l_issue_sous_le_curseur():
    """`EPIC11-ARB-45`, en un seul geste. La cible est en **troisieme**
    position : une validation qui rendrait toujours la premiere issue -- le
    mutant `M25` de la 5.7 -- ne se demasque pas autrement."""
    choix = ChoixExclusif(fabrique_d_issues())
    choix.deplacer(2)
    suivie = choix.valider()
    assert suivie.cle == "annuler"
    assert choix.retenue == "annuler"


def test_aucune_issue_qui_ECRIT_n_est_a_une_frappe_du_montage():
    """Ce que `EPIC11-ARB-7` garde apres `ARB-45`, et c'est ce qui compte.

    La protection n'est plus le double geste, c'est le point de jugement : une
    issue qui ecrit n'est jamais la premiere d'une liste, donc jamais suivie par
    une validation a l'aveugle au montage.
    """
    choix = ChoixExclusif(fabrique_d_issues())
    assert choix.issues[choix.curseur].ecrit is False
    # Volet symetrique : la fabrique porte bien une issue qui ecrit, sinon la
    # mesure serait vraie par vacuite.
    assert any(issue.ecrit for issue in choix.issues)


def test_retenir_vise_l_issue_sous_le_curseur_et_pas_la_premiere():
    """Regle des fabriques : la cible est en troisieme position."""
    choix = ChoixExclusif(fabrique_d_issues())
    choix.deplacer(2)
    retenue = choix.retenir()
    assert retenue.cle == "annuler"
    assert choix.valider().cle == "annuler"


def test_retenir_par_cle_vise_la_cle_nommee():
    choix = ChoixExclusif(fabrique_d_issues())
    assert choix.retenir("modifier").libelle == "Modifier les reglages"


def test_retenir_une_cle_inconnue_est_refuse_en_nommant_les_connues():
    choix = ChoixExclusif(fabrique_d_issues())
    with pytest.raises(KeyError) as echec:
        choix.retenir("extraire")
    assert "annuler" in str(echec.value)


def test_le_curseur_ne_sort_pas_des_bornes():
    choix = ChoixExclusif(fabrique_d_issues())
    choix.deplacer(-5)
    assert choix.curseur == 0
    choix.deplacer(9)
    assert choix.curseur == 2


def test_un_panneau_offre_toujours_une_sortie_qui_n_ecrit_pas():
    """Sans elle, le point de jugement ne serait plus un jugement."""
    choix = ChoixExclusif(fabrique_d_issues())
    assert choix.sortie_sans_ecriture.cle == "modifier"


def test_le_rendu_ne_porte_PLUS_de_case_a_cocher():
    """`EPIC11-ARB-45` : « enlever l'espace pour cocher qui ne sert a rien dans
    ce cas. Juste la fleche sur le choix. »

    Frontiere negative, avec son volet symetrique juste apres : les deux
    glyphes de radio ne doivent apparaitre dans aucune ligne rendue.
    """
    table = jetons.GLYPHES
    choix = ChoixExclusif(fabrique_d_issues())
    choix.retenir("annuler")
    lignes = choix.rendu()
    radios = [l for l in lignes
              if table["exclusif-libre"] in l or table["exclusif-retenu"] in l]
    assert radios == [], radios
    # Exactement une ligne porte le curseur, et les autres n'ont aucun signe.
    portent = [l for l in lignes if l.startswith(table["curseur"])]
    assert len(portent) == 1, lignes


def test_le_curseur_est_le_SEUL_signe_et_il_se_deplace():
    """Volet symetrique du precedent : sans lui, un rendu qui ne poserait
    AUCUN signe passerait le comptage a zero ci-dessus."""
    table = jetons.GLYPHES
    choix = ChoixExclusif(fabrique_d_issues())
    choix.deplacer(2)
    lignes = choix.rendu()
    portent_le_curseur = [rang for rang, ligne in enumerate(lignes)
                          if ligne.startswith(table["curseur"])]
    assert portent_le_curseur == [2], lignes


def test_le_rendu_suit_le_repli_ascii():
    lignes = ChoixExclusif(fabrique_d_issues()).rendu(ascii_seul=True)
    assert all(ligne.isascii() for ligne in lignes), lignes


def test_un_choix_dont_toutes_les_issues_ecrivent_est_refuse():
    """Le docstring de `sortie_sans_ecriture` promettait cette verification et
    personne ne la posait : les trois autres invariants etaient rendus
    impossibles plutot qu'improbables, celui-la restait une declaration (revue
    de vague 1, couche 2).

    Un point de jugement dont toutes les issues ecrivent n'est plus un jugement.
    """
    with pytest.raises(PanneauMalForme, match="n'ecrit"):
        ChoixExclusif([Issue("ecraser", "Ecraser", ecrit=True),
                       Issue("renommer", "Ecrire sous un autre nom", ecrit=True)])


def test_le_meme_choix_passe_des_qu_une_issue_n_ecrit_pas():
    """Volet symetrique : la garde ne doit pas refuser les cas legitimes."""
    choix = ChoixExclusif([Issue("ecraser", "Ecraser", ecrit=True),
                           Issue("renommer", "Ecrire sous un autre nom",
                                 ecrit=True),
                           Issue("annuler", "Annuler")])
    assert choix.sortie_sans_ecriture.cle == "annuler"


# --------------------------------------------------------------------------
# Revue vague 2 bis -- la borne HAUTE de la ligne chiffree
#
# `creux = largeur_de_cartouche(largeur) - len(libelle) - len(chiffre)` puis
# `max(2, creux)` : la borne basse etait tenue, la haute manquait, et la mesure
# se faisait en CARACTERES. Chiffres mesures au plancher (cartouche de 72
# colonnes) avant correction, sur les deux lignes chiffrees du depot qui
# portent un nom de FICHIER et non un nombre (`palier_projet` : `Fichier de
# projet`, `Fichier du profil`) :
#
#   valeur 11 caracteres / 11 colonnes  -> ligne = 72 colonnes  ok
#   valeur 57 caracteres / 57 colonnes  -> ligne = 76 colonnes  DEBORDE
#   valeur 61 caracteres / 61 colonnes  -> ligne = 80 colonnes  DEBORDE
#   valeur 34 caracteres / 56 colonnes  -> len(ligne) = 72, soit une ligne que
#                                          le code croyait calee juste, pour
#                                          **94 colonnes** reelles
#   valeur 46 caracteres / 80 colonnes  -> len(ligne) = 72, pour 106 colonnes
#
# Le second cas est celui qui compte : la mesure en `len()` ne voit RIEN. Et le
# garde-fou `jetons.ajuster` coupait par la fin, c'est-a-dire qu'il mangeait le
# chiffre -- la seule chose que le panneau existe pour montrer.
#
# La fixture d'avant cette revue ne pouvait pas le voir :
# `test_une_ligne_trop_longue_garde_deux_espaces_de_creux` porte un libelle de
# 65 colonnes, qui fait une ligne de 72 exactement -- elle TIENT.
# --------------------------------------------------------------------------

#: Deux valeurs de ligne chiffree qui debordent, et une qui tient. La seconde
#: est en ideogrammes : `len()` et `colonnes()` n'y disent pas la meme chose,
#: et c'est la seule des trois ou le mutant « mesurer en caracteres » meurt.
FICHIER_COURT = "projet.json"
FICHIER_LONG = "2026-08-29_tournage_exterieur_nuit_camera_B_prise_02_bis.json"
FICHIER_IDEOGRAMMES = "profil_" + "日" * 22 + ".json"   # 34 car., 56 col.


def fabrique_de_lignes_larges() -> Panneau:
    """Un panneau de trois lignes chiffrees **de largeurs differentes**, la
    cible en position 1.

    Regle des fabriques du depot : un remplissage uniforme rendrait invisible
    une correction qui n'abregerait que la premiere ligne, et une fixture dont
    toutes les lignes tiennent ne mesurerait pas la borne haute du tout. La
    ligne 0 tient, la 1 deborde en simple chasse, la 2 en double.
    """
    return Panneau("Projet lu", [
        LigneChiffree("Fichier de projet", FICHIER_COURT),
        LigneChiffree("Fichier de projet", FICHIER_LONG),
        LigneChiffree("Fichier du profil", FICHIER_IDEOGRAMMES),
    ])


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_une_ligne_chiffree_trop_longue_tient_le_cartouche(ascii_seul):
    """La borne haute, dans les DEUX modes.

    Le repli ASCII precede la mesure : `…` vaut une colonne, `...` en vaut
    trois. Une correction qui abregerait puis replierait ferait deborder de
    deux colonnes toute ligne calee juste -- c'est le finding `F7` de
    l'explorateur, et il vaut ici mot pour mot.
    """
    utile = jetons.largeur_de_cartouche(80)
    assert utile == 72, utile
    for rang, ligne in enumerate(fabrique_de_lignes_larges().rendu(80, ascii_seul)):
        assert jetons.colonnes(ligne) <= utile, (
            f"rang {rang}, ascii={ascii_seul} : {jetons.colonnes(ligne)} "
            f"colonnes pour {utile} -- {ligne!r}")
    # Volet symetrique : la fixture ATTEINT le defaut. Deux des trois valeurs
    # debordent a elles seules le cartouche une fois le libelle pose.
    debordent = [valeur for valeur in (FICHIER_COURT, FICHIER_LONG,
                                       FICHIER_IDEOGRAMMES)
                 if jetons.colonnes("Fichier de projet") + 2
                 + jetons.colonnes(valeur) > utile]
    assert len(debordent) == 2, [(v, jetons.colonnes(v)) for v in debordent]


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_la_ligne_chiffree_mesure_en_COLONNES_et_non_en_caracteres(ascii_seul):
    """Le mutant « mesurer en `len()` » meurt ici, et seulement ici.

    Un nom de fichier de 34 caracteres pour 56 colonnes rendait une ligne dont
    `len()` valait exactement 72 -- le code la croyait calee juste -- pour 94
    colonnes reelles. La mesure porte donc sur les colonnes, et le volet
    symetrique verifie que les deux comptes different bien sur cette fixture.
    """
    assert jetons.colonnes(FICHIER_IDEOGRAMMES) > len(FICHIER_IDEOGRAMMES), (
        "la fixture doit porter de la double chasse, sans quoi `len()` et "
        f"`colonnes()` sont le meme test -- {FICHIER_IDEOGRAMMES!r}")
    ligne = LigneChiffree("Fichier du profil", FICHIER_IDEOGRAMMES).rendu(
        80, ascii_seul)
    assert jetons.colonnes(ligne) <= jetons.largeur_de_cartouche(80), (
        len(ligne), jetons.colonnes(ligne), ligne)


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_libelle_cede_mais_le_CHIFFRE_ne_disparait_pas(ascii_seul):
    """Ce qui doit survivre, et ce qui peut ceder.

    Le chiffre passe en premier sur le budget -- c'est la mesure, et un panneau
    qui l'ampute ment sur ce qu'il annonce --, mais le libelle garde au moins
    la moitie de la place : un chiffre sans son libelle ne designe plus rien,
    et le panneau est un point de jugement.
    """
    utile = jetons.largeur_de_cartouche(80)
    ligne = LigneChiffree("Fichier de projet", FICHIER_LONG).rendu(80, ascii_seul)
    assert ligne.startswith("Fichier de projet"), (
        f"le libelle tient dans la moitie basse et ne doit PAS ceder -- {ligne!r}")
    points = "..." if ascii_seul else "…"
    assert points in ligne, (
        f"le nom de fichier, lui, doit s'abreger -- {ligne!r}")
    # Abrege AU MILIEU : la tete (la date) et la queue (l'extension) portent
    # l'identite, et deux fichiers d'un meme tournage ne se distinguent qu'a
    # partir d'elles.
    assert ligne.rstrip().endswith(".json"), ligne
    assert FICHIER_LONG[:11] in ligne, ligne
    assert jetons.colonnes(ligne) <= utile, (jetons.colonnes(ligne), ligne)


def test_une_ligne_chiffree_qui_tient_n_est_PAS_abregee():
    """Volet symetrique de tout ce qui precede : la borne haute ne mord que
    quand elle doit. Une correction qui abregerait toutes les lignes passerait
    chaque mesure de largeur ci-dessus."""
    ligne = LigneChiffree("Frames ecrites", 186, "frames").rendu(80)
    assert ligne.startswith("Frames ecrites")
    assert ligne.rstrip().endswith("186 frames")
    assert "…" not in ligne and "..." not in ligne, ligne
