# -*- coding: utf-8 -*-
"""Story 11.4, AC 6.7 et 6.8 -- deux defauts du CODE LIVRE, trouves par Egan.

Les deux ont ete trouves en relisant des **maquettes**, pas du code, et aucun
des 845 tests de la TUI ne les voyait. Ils n'ont rien en commun sinon leur
forme : dans les deux cas, une regle **devine** ce que l'appelant savait deja.

* `EPIC11-ARB-68` -- une branche de clavier devine qu'une lettre est un
  raccourci, alors que le champ a le focus. Taper `r` dans un nom de lot
  **detruit la saisie** : champ vide, « rush_hiver » tape rend le nom d'origine.
  Nos lots s'appellent `projet_demo_rush_01_25fps` : la lettre y est
  structurelle ;
* `EPIC11-ARB-71` -- la peinture devine l'etat d'une ligne a partir de sa mise
  en page, alors que l'ecran qui l'a composee le connaissait. Dans un cartouche,
  le glyphe est precede de la bordure et d'UN blanc : aucun etat n'est trouve,
  donc **aucun glyphe d'etat pose dans un cartouche n'est colore** -- or le
  cartouche est la forme du panneau de confirmation, par lequel toute ecriture
  passe.

**Ce que ces tests mesurent, et pourquoi de cette facon.** Le test du clavier se
lit sur la **valeur du champ** apres frappe, jamais sur l'appel a `remettre` :
un test qui n'observe que le modele ne voit pas la collision, puisque `remettre`
fait exactement ce qu'on lui demande. Le test de la couleur exige le **volet
symetrique** : le cas documente de l'entree d'explorateur litteralement nommee
`x`, dont la taille est calee a droite, doit rester **non coloree** -- c'est lui
qui interdit de corriger le defaut en relachant les expressions regulieres, la
fausse piste evidente.
"""

import pytest

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.execution import EcranChiffre
from mixed_media_utility.tui.noms import ModeleNoms, NomEditable
from mixed_media_utility.tui.panneau import ChoixExclusif, Issue, Panneau

#: Les lettres de l'alphabet ASCII, minuscules et majuscules. Une regle qui
#: dit « aucune lettre » se mesure sur TOUTES, pas sur celle qui a mordu.
LETTRES = [chr(c) for c in range(ord("a"), ord("z") + 1)]
LETTRES += [c.upper() for c in LETTRES]


def ecran(en_edition: bool = True) -> EcranChiffre:
    """Un ecran chiffre a DEUX noms distinguables, cible en SECONDE position.

    Regle des fabriques : deux noms differents, jamais un remplissage uniforme,
    et la frappe portee sur le second. Un `remettre` fautif qui rendrait
    toujours le premier nom ne se demasque pas autrement.
    """
    e = EcranChiffre(
        Panneau("A ecrire", []),
        ChoixExclusif([Issue("annuler", "Annuler"),
                       Issue("ecrire", "Extraire", ecrit=True)]),
        ModeleNoms([NomEditable("lot_alpha"), NomEditable("lot_beta")]))
    if en_edition:
        e.noms.entrer_en_edition()
        e.noms.descendre()          # la cible est le SECOND nom
    return e


def vider(modele: ModeleNoms) -> None:
    for _ in range(len(modele.courant.valeur)):
        modele.effacer()


def taper(e: EcranChiffre, texte: str) -> None:
    """Rejoue le clavier de l'ecran, caractere par caractere."""
    for c in texte:
        e.traiter(c, c)


# ----------------------------------------------------------------------------
# `EPIC11-ARB-68` -- aucune LETTRE n'est un raccourci dans un champ de saisie
# ----------------------------------------------------------------------------

def test_taper_rush_hiver_dans_un_champ_vide_rend_rush_hiver():
    """LE defaut, dans la forme exacte ou Egan l'a trouve.

    Avant correctif, la valeur rendue etait `lot_beta` : le premier `r` remet le
    nom propose et efface la saisie, le second re-detruit ce que les huit
    lettres suivantes avaient reconstruit.
    """
    e = ecran()
    vider(e.noms)
    taper(e, "rush_hiver")
    assert e.noms.courant.valeur == "rush_hiver"


def test_le_nom_NON_VISE_n_est_pas_touche_par_la_frappe():
    """Volet de la regle des fabriques : la frappe porte sur UN seul nom."""
    e = ecran()
    vider(e.noms)
    taper(e, "rush_hiver")
    assert e.noms.valeurs == ["lot_alpha", "rush_hiver"]


@pytest.mark.parametrize("lettre", LETTRES)
def test_AUCUNE_lettre_n_est_un_raccourci_en_edition(lettre):
    """La regle est generale, pas ponctuelle : elle se mesure sur les 52."""
    e = ecran()
    vider(e.noms)
    e.traiter(lettre, lettre)
    assert e.noms.courant.valeur == lettre


def test_la_frappe_est_CONSOMMEE_par_l_ecran_en_edition():
    """Le mode d'edition capture le clavier, sinon ce n'en est pas un.

    Une touche non consommee remonterait a l'application, ou `q` quitte.
    """
    e = ecran()
    assert e.traiter("q", "q") is True


def test_Tab_ENTRE_dans_les_noms_depuis_les_choix():
    """`Tab` nomme sa destination -- la convention de toute la TUI."""
    e = ecran(en_edition=False)
    assert e.traiter("tab") is True
    assert e.noms.en_edition is True


def test_Tab_RESSORT_des_noms_vers_les_choix():
    """La reponse a « on passe des choix aux lots avec tab ? » : dans les DEUX
    sens. Mesure d'avant correctif : `traiter("tab")` rendait `False`."""
    e = ecran()
    assert e.traiter("tab") is True
    assert e.noms.en_edition is False


def test_Tab_qui_RESSORT_garde_la_saisie():
    """Sortir n'est pas abandonner : `Echap` abandonne, `Tab` deplace."""
    e = ecran()
    vider(e.noms)
    taper(e, "rush_hiver")
    e.traiter("tab")
    assert e.noms.valeurs == ["lot_alpha", "rush_hiver"]


def test_e_n_est_PLUS_un_raccourci_d_edition():
    """Frontiere negative : `e` etait la porte, `Tab` l'a remplacee.

    Deux portes pour le meme geste, c'est une porte que personne ne documente.
    """
    e = ecran(en_edition=False)
    assert e.traiter("e", "e") is False
    assert e.noms.en_edition is False


def test_ctrl_r_remet_le_nom_propose():
    """Une COMBINAISON, jamais une lettre nue : c'est la seule forme qui ne
    peut pas entrer en collision avec une saisie."""
    e = ecran()
    vider(e.noms)
    taper(e, "rush_hiver")
    assert e.traiter("ctrl+r") is True
    assert e.noms.courant.valeur == "lot_beta"


def test_ctrl_r_ne_remet_QUE_le_nom_courant():
    """Fabrique : la cible est le SECOND nom, et le premier ne bouge pas."""
    e = ecran()
    vider(e.noms)
    taper(e, "rush_hiver")
    e.traiter("ctrl+r")
    assert e.noms.valeurs == ["lot_alpha", "lot_beta"]


def test_ctrl_r_hors_edition_ne_fait_rien():
    """Le raccourci appartient au champ, pas a l'ecran."""
    e = ecran(en_edition=False)
    assert e.traiter("ctrl+r") is False


def test_echap_abandonne_et_rend_les_deux_noms_d_origine():
    """`Echap` est la sortie qui ANNULE -- l'autre moitie de la reponse a
    « comment on sort de l'edition des noms ? »."""
    e = ecran()
    vider(e.noms)
    taper(e, "rush_hiver")
    e.traiter("escape")
    assert e.noms.valeurs == ["lot_alpha", "lot_beta"]
    assert e.noms.en_edition is False


def test_entree_confirme_et_sort_de_l_edition():
    e = ecran()
    vider(e.noms)
    taper(e, "rush_hiver")
    e.traiter("enter")
    assert e.noms.valeurs == ["lot_alpha", "rush_hiver"]
    assert e.noms.en_edition is False


# ----------------------------------------------------------------------------
# `EPIC11-ARB-71` -- la couleur d'etat se DONNE, elle ne se devine plus
# ----------------------------------------------------------------------------

def styles(peint) -> list[str]:
    """Le style pose sur chaque LIGNE, dans l'ordre.

    On lit les segments de l'objet stylise plutot que son texte : c'est la
    couleur qu'on mesure, et une chaine balisee ne la porte pas.
    """
    # `Text.split` conserve les styles : chaque ligne sort avec le sien, pose
    # en un seul segment par `peindre`.
    return [str(ligne.spans[0].style) if ligne.spans else ""
            for ligne in peint.split("\n")]


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_un_glyphe_d_etat_dans_un_CARTOUCHE_est_colore(ascii_seul):
    """Le defaut d'Egan sur `E2-5`, dans sa forme exacte.

    La ligne est celle d'un cartouche : bordure, UN blanc, puis le glyphe.
    `jeton_d_etat` n'y trouve rien -- le glyphe n'ouvre pas de colonne.
    """
    glyphe = jetons.glyphes(ascii_seul)["complete"]
    ligne = f"   │ {glyphe} projet_demo_rush_01_25fps     124 frames       │   "
    assert jetons.jeton_d_etat(ligne, ascii_seul) is None, (
        "prealable de la mesure : la reconnaissance par motif ne trouve rien")
    peint = jetons.peindre([ligne], ascii_seul=ascii_seul,
                           etats={0: "complete"})
    assert styles(peint)[0] == jetons.couleur("state-complete")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_un_glyphe_suivi_de_DEUX_blancs_est_colore(ascii_seul):
    """Le meme defaut sur la ligne d'etat : `_PORTE_UN_LIBELLE` exige UN blanc."""
    glyphe = jetons.glyphes(ascii_seul)["complete"]
    ligne = f"{glyphe}  2 lots ecrits, 166 frames, aucun refus"
    assert jetons.jeton_d_etat(ligne, ascii_seul) is None
    peint = jetons.peindre([ligne], ascii_seul=ascii_seul,
                           etats={0: "complete"})
    assert styles(peint)[0] == jetons.couleur("state-complete")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_un_message_de_refus_REPLIE_est_colore_sur_TOUTES_ses_lignes(ascii_seul):
    """Le troisieme symptome, signale par Egan le matin du 2026-08-29.

    « L'erreur est rouge uniquement sur la ligne 1. » Une ligne de continuation
    ne porte pas le glyphe : par construction, elle ne peut pas etre teintee
    par la reconnaissance par motif.
    """
    glyphe = jetons.glyphes(ascii_seul)["absent"]
    lignes = [f"{glyphe} Le nom est trop long : 50 caracteres pour 48 admis,",
              "  et les deux lots seraient alors le meme lot.",
              "  Retirez 2 caracteres."]
    peint = jetons.peindre(lignes, ascii_seul=ascii_seul,
                           etats={0: "absent", 1: "absent", 2: "absent"})
    assert styles(peint) == [jetons.couleur("state-absent")] * 3


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_l_etat_DONNE_l_emporte_sur_l_etat_DEVINE(ascii_seul):
    """L'appelant sait ; le motif ne fait que deviner. Le premier gagne."""
    absent = jetons.glyphes(ascii_seul)["absent"]
    ligne = f"  {absent} une ligne que le motif lit comme un refus"
    assert jetons.jeton_d_etat(ligne, ascii_seul) == "state-absent"
    peint = jetons.peindre([ligne], ascii_seul=ascii_seul,
                           etats={0: "complete"})
    assert styles(peint)[0] == jetons.couleur("state-complete")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_l_entree_nommee_x_calee_a_droite_reste_NON_coloree(ascii_seul):
    """**Volet symetrique, et c'est lui qui interdit la fausse piste.**

    Corriger le defaut en relachant `_PORTE_UN_LIBELLE` a « un ou plusieurs
    blancs » recolorerait cette entree d'explorateur -- un fichier litteralement
    nomme `x`, dont la taille est calee a droite (`jetons.py:557-562`). Le repli
    par motif n'est donc PAS touche : seul l'etat donne s'ajoute.
    """
    ligne = "     x              2 o"
    assert jetons.jeton_d_etat(ligne, ascii_seul) is None
    peint = jetons.peindre([ligne], ascii_seul=ascii_seul)
    assert styles(peint)[0] == ""


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_repli_par_MOTIF_reste_actif_pour_les_lignes_non_nommees(ascii_seul):
    """Les textes venus du coeur n'ont pas d'etat declare : le motif les sert."""
    glyphe = jetons.glyphes(ascii_seul)["substitute"]
    lignes = ["une ligne ordinaire", f"  {glyphe} un avertissement du coeur"]
    peint = jetons.peindre(lignes, ascii_seul=ascii_seul, etats={0: "complete"})
    assert styles(peint) == [jetons.couleur("state-complete"),
                             jetons.couleur("state-substitute")]


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_sans_couleur_ignore_AUSSI_les_etats_donnes(ascii_seul):
    """Le repli ne change pas ce qui est lisible, seulement ce qui est teinte."""
    glyphe = jetons.glyphes(ascii_seul)["complete"]
    ligne = f"   │ {glyphe} un lot ecrit    │   "
    peint = jetons.peindre([ligne], ascii_seul=ascii_seul,
                           sans_couleur=True, etats={0: "complete"})
    assert styles(peint)[0] == ""
    assert jetons.texte_affiche(peint) == ligne


def test_la_ligne_du_curseur_l_emporte_sur_l_etat_donne():
    """L'ordre des regles ne bouge pas : le curseur reste au-dessus.

    Deux lignes, la seconde sous le curseur : un ordre inverse ne se verrait
    pas sur une seule.
    """
    glyphe = jetons.glyphes(False)["complete"]
    lignes = [f"   │ {glyphe} lot_alpha │", f"   │ {glyphe} lot_beta  │"]
    peint = jetons.peindre(lignes, etats={0: "complete", 1: "complete"},
                           ligne_du_curseur=1)
    assert styles(peint) == [jetons.couleur("state-complete"),
                             "bold " + jetons.couleur("accent")]


def test_un_etat_donne_INCONNU_est_refuse():
    """Le refus est dur, comme celui de `couleur` : un jeton mal orthographie
    qui rendrait une couleur par defaut produirait une surface silencieusement
    hors charte."""
    with pytest.raises((KeyError, ValueError)):
        jetons.peindre(["une ligne"], etats={0: "compleet"})


def test_un_rang_d_etat_HORS_BORNES_est_refuse():
    """Un rang qui ne designe aucune ligne est une erreur d'appariement -- la
    famille de defauts que la regle des fabriques existe pour attraper."""
    with pytest.raises((IndexError, ValueError)):
        jetons.peindre(["une ligne"], etats={7: "complete"})


# ----------------------------------------------------------------------------
# Le signe multiplier, trouve au developpement du lot D
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("texte,attendu", [
    ("1920×1080", "1920x1080"),
    ("4096×2160", "4096x2160"),
    ("3 rushes · 1920×1080 · 4:12", "3 rushes . 1920x1080 . 4:12"),
])
def test_le_signe_MULTIPLIER_se_replie_en_x_et_pas_en_point_d_interrogation(
        texte, attendu):
    """Une resolution repliee doit rester une resolution.

    Sans cette entree de table, la decomposition Unicode ne connaissait pas
    `×` et le repli terminal rendait `1920?1080`. Cinq maquettes de TROIS
    ateliers portent ce signe : le defaut aurait morde trois fois.
    """
    assert jetons.replier_ascii(texte) == attendu


@pytest.mark.parametrize("ligne", [
    "1920x1080", "      rush_01     25 fps . 1920x1080 . 4:12", "4096x2160",
])
def test_une_resolution_repliee_n_est_JAMAIS_lue_comme_un_REFUS(ligne):
    """**Volet symetrique du choix de `x`.**

    `x` est aussi le glyphe ASCII de l'etat « absent ». La collision est
    impossible parce que `jeton_d_etat` exige que le glyphe OUVRE UNE COLONNE,
    et une resolution le colle entre deux chiffres -- mais ce test est ce qui
    le PROUVE, plutot que de le supposer.
    """
    assert jetons.jeton_d_etat(ligne, ascii_seul=True) is None
