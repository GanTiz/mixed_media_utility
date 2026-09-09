# -*- coding: utf-8 -*-
"""Un champ cale a gauche se mesure en COLONNES, dans TOUT le paquet.

**Cinquieme, sixieme et septieme occurrence du meme defaut**, et c'est ce
cardinal qui justifie une frontiere plutot que trois corrections. `str.ljust`
-- ce que `f"{nom:<{LARGEUR}}"` est -- compte des caracteres ; un ideogramme en
occupe deux. Le champ sort donc trop large, la mention qui le suit part trop a
droite, et `jetons.ajuster` l'ampute : l'operateur perd la seule chose qui dise
ce que la ligne EST.

Le depot l'avait deja paye quatre fois -- `atelier_exports_lot._a_gauche`, son
jumeau d'`atelier_pdf_lots`, `cadences`, `projet_inventaire` -- **et il l'a
rouvert le 2026-09-06** dans l'ecran du profil par defaut, ecrit par un agent
qui ne pouvait pas voir quatre redactions privees. Ce qu'on ne trouve pas ne se
recopie pas ; ce qui se recopie diverge. Le calcul vit desormais **une fois**,
dans `jetons.caler_a_gauche`.

**Le mode `--ascii` PASSE sur ce defaut** (un ideogramme y vaut une colonne) :
c'est le mode NOMINAL qui casse. Une garde qui ne jouerait que l'ASCII ne
verrait rien -- c'est la regle des drapeaux du 2026-09-06, sur un drapeau que
personne n'avait recense : la chasse d'un caractere.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility.tui import jetons

PAQUET = RACINE / "src" / "mixed_media_utility" / "tui"

#: Le motif fautif : un champ de largeur variable cale par `str.__format__`.
#: Il ne cherche PAS `:<` seul -- un calage sur une largeur litterale de 1 ou 2
#: ne peut rien casser --, mais le calage sur une largeur NOMMEE, qui est la
#: forme que prennent les colonnes de nom du depot.
CALAGE_PAR_FORMAT = re.compile(r"\{[^{}]*:<\{[A-Za-z_]")


#: Les sites TOLERES, nommes plutot que tus, et **tous de la meme famille** :
#: ils calent un texte que le DEPOT ecrit -- un libelle de champ, un
#: identifiant de profil de codec --, jamais un nom que l'operateur choisit.
#:
#: **Pourquoi une tolerance et non dix corrections de plus.** Le defaut ne mord
#: que sur du texte a double chasse, et aucun de ces dix textes ne peut en
#: porter : ce sont des constantes de module en francais et des identifiants du
#: catalogue de codecs. Les convertir en bloc a 02:20, sans revue, ferait
#: passer dix rendus par `ajuster` -- qui ABREGE -- pour fermer un risque qui
#: n'existe pas sur eux. L'echange serait mauvais dans ce sens-la.
#:
#: **Ce que la tolerance ne dit PAS** : que ces lignes sont justes. Elles sont
#: SANS EFFET AUJOURD'HUI, ce qui n'est pas la meme chose -- le jour ou l'un de
#: ces libelles devient traduisible, ou ou un identifiant de codec vient d'un
#: fichier, le defaut y renait. La consolidation est en dette avec les quatre
#: `_a_gauche` prives.
CALAGES_TOLERES = (
    ("atelier_exports_reglages.py", "profil:<{_LARGEUR_DE_L_IDENTIFIANT}"),
    ("atelier_pdf.py", "LIBELLE_DU_PIED:<{LARGEUR_DU_LIBELLE_DU_PIED}"),
    ("atelier_pdf_calibration.py",
     "LIBELLES_DES_CHAMPS[cle]:<{LARGEUR_DU_LIBELLE}"),
    ("atelier_pdf_calibration.py", "libelle:<{LARGEUR_DU_LIBELLE}"),
    ("atelier_pdf_versions.py", "libelle:<{LARGEUR_DU_LIBELLE}"),
    ("atelier_scan.py", "libelle:<{LARGEUR_DU_LIBELLE}"),
    ("atelier_scan_calibrate.py", "LIBELLES[cle]:<{LARGEUR_DU_LIBELLE}"),
    ("atelier_scan_calibrate.py", "libelle:<{LARGEUR_DU_LIBELLE}"),
    ("atelier_scan_calibration.py", "libelle:<{LARGEUR_DU_LIBELLE}"),
    ("atelier_scan_completion.py", "LIBELLES[cle]:<{LARGEUR_DU_LIBELLE}"),
)


def _calages_du_paquet() -> list[tuple[str, str]]:
    """`(module, ligne)` pour chaque calage par format du paquet."""
    trouves = []
    for source in sorted(PAQUET.glob("*.py")):
        for ligne in source.read_text(encoding="utf-8").splitlines():
            if CALAGE_PAR_FORMAT.search(ligne):
                trouves.append((source.name, ligne.strip()))
    return trouves


def test_aucun_NOM_du_paquet_n_est_cale_par_str_ljust() -> None:
    """Frontiere negative -- elle attrape la HUITIEME occurrence, pas les sept
    premieres.

    Aucun test positif ne verrait revenir un `f"{nom:<{LARGEUR}}"` : il rend
    exactement la bonne chose sur tout nom en chasse simple, c'est-a-dire sur
    la totalite des fabriques du depot.
    """
    fautifs = [f"{module}: {ligne}"
               for module, ligne in _calages_du_paquet()
               if not any(module == m and motif in ligne
                          for m, motif in CALAGES_TOLERES)]
    assert not fautifs, (
        "ces lignes calent un champ en CARACTERES ; un ideogramme occupe deux "
        "colonnes et la mention qui suit se fait amputer. Le mecanisme est "
        f"`jetons.caler_a_gauche` : {fautifs}")


def test_la_TOLERANCE_des_calages_est_PORTANTE() -> None:
    """Le volet sans lequel la tolerance transformerait la frontiere en
    tautologie.

    Une entree qui ne correspond plus a rien laisserait le test ci-dessus vert
    en ne mesurant plus le motif qu'on croit tolerer -- et, pire ici, elle
    masquerait un site NEUF qui aurait repris le meme libelle. On mesure donc
    les deux sens : le cardinal exact, et le fait que chaque entree vive.
    """
    trouves = _calages_du_paquet()
    assert len(trouves) == len(CALAGES_TOLERES), (
        "le cardinal des calages du paquet a change : porter l'entree, ou "
        f"corriger le site -- {sorted(trouves)}")
    for module, motif in CALAGES_TOLERES:
        assert any(m == module and motif in ligne for m, ligne in trouves), (
            f"tolerance PERIMEE, a retirer : {module} / {motif}")


def test_la_frontiere_MORD_sur_le_motif_qu_elle_cherche() -> None:
    """Le volet symetrique : une frontiere qui ne sort jamais acquitte tout.

    Les quatre formes sont jouees -- la fautive, et trois voisines qui ne
    doivent PAS sortir. Sans elles, une expression reguliere trop large
    rougirait sur du code correct et se ferait desarmer.
    """
    assert CALAGE_PAR_FORMAT.search('f"{nom:<{LARGEUR_DU_NOM}}"')
    assert CALAGE_PAR_FORMAT.search('f"  {entree.nom:<{LARGEUR}}"')
    # Une largeur litterale ne cale rien de dangereux.
    assert not CALAGE_PAR_FORMAT.search('f"{rang:<2}"')
    # Un calage a DROITE n'est pas ce motif -- il a ses propres sites.
    assert not CALAGE_PAR_FORMAT.search('f"{nom:>{LARGEUR}}"')
    # Et le remede lui-meme ne doit pas se faire prendre pour la maladie.
    assert not CALAGE_PAR_FORMAT.search(
        "jetons.caler_a_gauche(nom, LARGEUR_DU_NOM, ascii_seul)")


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_caler_a_gauche_rend_la_LARGEUR_demandee_en_colonnes(ascii_seul):
    """Le mecanisme lui-meme, sur les DEUX chasses et les DEUX modes.

    Trois textes DISTINGUABLES et de chasses differentes : une mesure faite
    sur un seul texte ne verrait pas la difference entre compter des
    caracteres et compter des colonnes.
    """
    for texte in ("court", "日" * 5, "mixte 日日 ok"):
        cale = jetons.caler_a_gauche(texte, 20, ascii_seul)
        assert jetons.colonnes(cale) == 20, (texte, cale)
        # Et le contenu est devant, pas derriere : c'est un calage a GAUCHE.
        assert not cale.startswith(" ")


def test_caler_a_gauche_ABREGE_avant_de_caler() -> None:
    """L'ordre compte, et il n'est pas commutatif.

    Caler puis abreger rendrait un champ deja plein qu'on couperait ensuite --
    donc une largeur juste par accident et un contenu ampute sans que rien ne
    le dise. Le banc mesure les deux moities : la largeur tenue, et
    l'abregement ANNONCE.
    """
    long = "日" * 30          # 60 colonnes, pour une place de 20
    cale = jetons.caler_a_gauche(long, 20)
    assert jetons.colonnes(cale) == 20, cale
    assert jetons.points_d_abregement(False) in cale, cale
    # Le volet symetrique : ce qui TIENT n'est pas abrege.
    court = jetons.caler_a_gauche("日" * 5, 20)
    assert jetons.points_d_abregement(False) not in court, court
