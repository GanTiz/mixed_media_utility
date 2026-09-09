# -*- coding: utf-8 -*-
"""La troncature d'un chemin se fait AU MILIEU (story 11.2, AC 3.4 et 8.3).

`DESIGN.md` section 9, do's and don'ts, derniere ligne : « pas de troncature
silencieuse d'un chemin : un chemin trop long se tronque **au milieu**, avec
`…`, en gardant le debut et le nom de fichier ».

**Pourquoi une fonction a part, et pas un reglage d'`ajuster`.** Les deux
abregements ne servent pas la meme chose et ne se choisissent pas au meme
endroit. `ajuster` abrege une **phrase** : on garde le debut parce qu'une phrase
se lit de gauche a droite et que sa fin est la moins couteuse a perdre. Un
**chemin** se lit par ses deux bouts -- la racine dit ou l'on est, le dernier
segment dit ce que c'est --, et c'est le MILIEU qui est le moins couteux. Un
chemin abrege par la fin perd le nom du dossier, c'est-a-dire la seule chose que
l'operateur cherchait.
"""
import sys
import threading
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.tui import jetons


#: Un chemin reel du depot, pris au poste d'Egan : c'est celui de la maquette
#: `E0-2`, allonge de ce qu'un projet reel porte vraiment. 79 colonnes pour une
#: zone qui en offre 76 au plancher -- le cas nominal, pas un cas limite.
CHEMIN_LONG = r"D:\HOKO-Admin\Documents\mixed_media_utility\projects\projet_demo"


def test_le_chemin_garde_son_debut_et_son_dernier_segment():
    """Le coeur de l'AC 3.4 : les deux bouts survivent, le milieu part."""
    rendu = jetons.abreger_chemin(CHEMIN_LONG, 40)
    assert rendu.startswith(r"D:\HOKO-Admin"), rendu
    assert rendu.endswith("projet_demo"), rendu
    assert "\u2026" in rendu, rendu


def test_le_chemin_abrege_tient_exactement_la_largeur_demandee():
    """En COLONNES, jamais en caracteres (`jetons.colonnes`)."""
    for largeur in range(20, 80):
        rendu = jetons.abreger_chemin(CHEMIN_LONG, largeur)
        assert jetons.colonnes(rendu) <= largeur, (largeur, rendu)


def test_un_chemin_qui_tient_n_est_pas_touche():
    """Volet symetrique : la mesure ne doit pas mordre quand rien ne deborde."""
    court = r"D:\projets\demo"
    assert jetons.abreger_chemin(court, 76) == court


def test_le_dernier_segment_prime_sur_le_debut_quand_la_place_manque():
    """A largeur serree, c'est le NOM qui reste -- c'est ce qu'on cherchait.

    Un abregement qui garderait la racine et perdrait le nom rendrait deux
    projets differents identiques a l'ecran, ce qui est exactement le mode de
    panne que la troncature au milieu existe pour empecher.
    """
    rendu = jetons.abreger_chemin(CHEMIN_LONG, 18)
    assert "projet_demo" in rendu, rendu
    assert jetons.colonnes(rendu) <= 18, rendu


def test_deux_chemins_qui_ne_different_que_par_la_fin_restent_distincts():
    r"""La regle des fabriques, portee ici : deux elements DISTINGUABLES.

    C'est la mesure qui condamne `ajuster` pour cet emploi -- abreges par la
    fin, `...projets\projet_demo` et `...projets\projet_hiver` rendent la
    MEME chaine, et l'operateur choisit a l'aveugle.
    """
    base = r"D:\HOKO-Admin\Documents\mixed_media_utility\projects"
    a = jetons.abreger_chemin(rf"{base}\projet_demo", 30)
    b = jetons.abreger_chemin(rf"{base}\projet_hiver", 30)
    assert a != b, (a, b)
    # Et la preuve que le mode de panne existe vraiment sur l'autre fonction :
    assert jetons.ajuster(rf"{base}\projet_demo", 30) == \
           jetons.ajuster(rf"{base}\projet_hiver", 30)


def test_le_repli_ascii_est_fait_AVANT_la_mesure():
    """Le piege paye le 2026-08-28 sur le bandeau, reintroduit ici sinon.

    `…` fait **une** colonne, `...` en fait **trois** : une chaine calee a la
    bonne largeur en UTF-8 la depasse de deux une fois repliee. Replier apres
    avoir mesure redonne exactement la regression que `BH-6` / `EC-10` avaient
    fermee.
    """
    for largeur in range(20, 60):
        rendu = jetons.abreger_chemin(CHEMIN_LONG, largeur, ascii_seul=True)
        assert rendu.isascii(), rendu
        assert jetons.colonnes(rendu) <= largeur, (largeur, rendu)
        assert "\u2026" not in rendu


def test_un_chemin_qui_TIENT_est_replie_lui_aussi():
    """L'autre moitie de l'invariant : la branche « ca tient, je rends tel quel ».

    Le test ci-dessus ne parcourt que des largeurs ou le chemin deborde : il
    mesure le repli **sur la branche tronquee** seulement. Deplacer le repli
    apres le test `colonnes(chemin) <= largeur` laissait donc passer un chemin
    non-ASCII sur un ecran lance en `--ascii` -- c'est-a-dire des `?` a la place
    des accents, sur le seul mode ou l'on replie justement pour les eviter.
    """
    rendu = jetons.abreger_chemin("D:" + chr(92) + "rushes" + chr(92) + "ete\u0301",
                                  40, ascii_seul=True)
    assert rendu.isascii(), rendu
    assert rendu == "D:" + chr(92) + "rushes" + chr(92) + "ete", rendu


def test_un_chemin_CALE_JUSTE_deborde_s_il_est_replie_apres_la_mesure():
    """Le meme deplacement, pris par la largeur plutot que par les accents.

    `—` occupe une colonne et son repli `--` en occupe deux : un chemin cale
    **exactement** a la largeur en UTF-8 la depasse d'une colonne une fois
    replie. Mesurer avant de replier rend donc une ligne trop longue, que
    `textual` replie a son tour -- et la seconde ligne n'est jamais dessinee.
    C'est la regression payee sur le bandeau le 2026-08-28, par le seul chemin
    qui n'etait pas mesure.
    """
    chemin = "D:" + chr(92) + "rushes" + chr(92) + "jour\u20142"
    largeur = jetons.colonnes(chemin)  # cale JUSTE : la branche non tronquee
    rendu = jetons.abreger_chemin(chemin, largeur, ascii_seul=True)
    assert rendu.isascii(), rendu
    assert jetons.colonnes(rendu) <= largeur, (largeur, rendu, jetons.colonnes(rendu))


def test_le_repli_ascii_garde_les_deux_bouts_lui_aussi():
    rendu = jetons.abreger_chemin(CHEMIN_LONG, 40, ascii_seul=True)
    assert rendu.startswith(r"D:\HOKO-Admin"), rendu
    assert rendu.endswith("projet_demo"), rendu
    assert "..." in rendu, rendu


def test_un_chemin_sans_separateur_reste_abrege_sans_lever():
    """Un nom seul n'a pas de « dernier segment » distinct : on ne casse pas."""
    rendu = jetons.abreger_chemin("a" * 200, 20)
    assert jetons.colonnes(rendu) <= 20


@pytest.mark.parametrize("largeur", [0, -1, 1, 2, 3])
def test_les_largeurs_degenerees_ne_levent_pas(largeur):
    """Une zone de zero colonne est un etat d'ecran, pas une erreur."""
    rendu = jetons.abreger_chemin(CHEMIN_LONG, largeur)
    assert jetons.colonnes(rendu) <= max(largeur, 0)


def test_les_separateurs_posix_sont_traites_comme_ceux_de_windows():
    """Le depot tourne sur les deux ; un seul code, pas deux."""
    posix = "/home/egan/Documents/mixed_media_utility/projects/projet_demo"
    rendu = jetons.abreger_chemin(posix, 40)
    assert rendu.startswith("/home/egan"), rendu
    assert rendu.endswith("projet_demo"), rendu


# ---------------------------------------------------------------------------
# `envelopper` : la troisieme facon de faire tenir du texte, et la seule qui ne
# perd rien. Elle sert les motifs de refus rendus verbatim par le coeur.
# ---------------------------------------------------------------------------

#: Le motif reel que le coeur rend sur un `schema_version` inconnu. 101
#: colonnes pour une zone de 76 : c'est lui qui a rendu cette fonction
#: necessaire, mesure au developpement de la story 11.2.
MOTIF_DU_COEUR = ("Invalid manifest at 'schema_version': '9.9' is not a "
                  "supported manifest schema_version (known: 2.0, 2.1).")


def test_envelopper_ne_perd_AUCUN_mot():
    """C'est tout le point : `ajuster` coupe, celle-ci depense de la hauteur.

    Un motif tronque n'est plus le motif du coeur, c'est un resume -- ce que
    `EPIC11-ARB-30` refuse.
    """
    lignes = jetons.envelopper(MOTIF_DU_COEUR, 76)
    assert " ".join(lignes).split() == MOTIF_DU_COEUR.split()


def test_envelopper_tient_la_largeur_en_COLONNES():
    for largeur in range(12, 80):
        for ligne in jetons.envelopper(MOTIF_DU_COEUR, largeur):
            assert jetons.colonnes(ligne) <= largeur, (largeur, ligne)


def test_ajuster_PERD_la_partie_actionnable_du_meme_motif():
    """La mesure qui justifie l'existence de la fonction, figee des deux cotes.

    Sans ce test, un futur developpeur pourrait remplacer `envelopper` par
    `ajuster` en trouvant que « ca revient au meme » -- et l'operateur
    relirait qu'il y a un probleme de `schema_version` sans jamais savoir
    quelles versions sont acceptees.
    """
    abrege = jetons.ajuster(MOTIF_DU_COEUR, 76)
    assert "known: 2.0, 2.1" not in abrege
    assert "known: 2.0, 2.1" in " ".join(jetons.envelopper(MOTIF_DU_COEUR, 76))


def test_un_mot_plus_long_que_la_zone_est_coupe_net():
    """Sinon `textual` le replierait lui-meme et decalerait tout le bloc."""
    lignes = jetons.envelopper("a" * 200, 20)
    assert all(jetons.colonnes(l) <= 20 for l in lignes)
    assert "".join(lignes) == "a" * 200


def test_envelopper_replie_en_ascii_AVANT_de_mesurer():
    lignes = jetons.envelopper("un motif avec des « guillemets » et un …", 20,
                               ascii_seul=True)
    for ligne in lignes:
        assert ligne.isascii(), ligne
        assert jetons.colonnes(ligne) <= 20, ligne


@pytest.mark.parametrize("largeur", [0, -1])
def test_envelopper_sur_une_zone_nulle_ne_leve_pas(largeur):
    assert jetons.envelopper(MOTIF_DU_COEUR, largeur) == []


def _sous_garde_de_temps(fonction, *args, secondes: float = 5.0):
    """Appeler `fonction` en la faisant ECHOUER si elle ne rend pas la main.

    **Un test qui se contenterait d'appeler `envelopper` ne rougirait pas : il
    se bloquerait**, et une suite bloquee ne dit rien -- elle est tuee par le
    tour de garde de l'integration, sans nommer ce qui l'a tuee. Le fil est
    `daemon` pour que l'interpreteur puisse quand meme se fermer si la fonction
    ne termine jamais.
    """
    resultat = {}

    def cible():
        resultat["valeur"] = fonction(*args)

    fil = threading.Thread(target=cible, daemon=True)
    fil.start()
    fil.join(secondes)
    assert not fil.is_alive(), (
        f"{fonction.__name__}{args} n'a pas rendu la main en {secondes} s : "
        "la boucle de decoupe ne progresse pas")
    return resultat["valeur"]


@pytest.mark.parametrize("texte, largeur", [
    ("\u6771\u4eac", 1),        # deux ideogrammes, deux colonnes chacun
    ("\u6771a\u4eac", 1),       # un caractere fin AU MILIEU de deux larges
    ("\u6771\u4eac\u90fd", 2),  # la largeur egale le cout d'UN caractere
    ("\U0001f4c1", 1),           # un emoji : meme famille, autre plan Unicode
])
def test_envelopper_PROGRESSE_meme_sur_un_caractere_plus_large_que_la_zone(
        texte, largeur):
    """`envelopper` ne rendait jamais la main sur une largeur de 1.

    `_tete(mot, 1)` rend `""` des que le premier caractere en coute deux :
    la boucle apposait une ligne vide, ne consommait aucun caractere, et
    tournait sans fin. Le processus etait bloque, **sans exception ni
    message** -- une TUI qui ne repond plus, sans trace.

    La fonction est publique et le module est declare fragile : la garde ne
    porte pas sur l'ecran d'aujourd'hui, elle porte sur la fonction.

    Deux bornes plutot qu'une : le TEMPS (la fonction rend la main) et le
    NOMBRE de lignes (elle consomme au moins un caractere par tour). La seconde
    tomberait aussi sur une boucle qui progresserait « parfois ».
    """
    lignes = _sous_garde_de_temps(jetons.envelopper, texte, largeur)
    assert len(lignes) <= len(texte), (lignes, texte)
    assert all(lignes), ("une ligne vide a ete apposee sans rien consommer",
                         lignes)
    assert "".join(lignes) == texte, (lignes, texte)
