# -*- coding: utf-8 -*-
"""L'explorateur de dossiers -- story 11.2b, `EPIC11-ARB-48` a `56`.

Tout se mesure sur le **modele pur** : il ne connait pas `textual`, donc aucun
de ces tests n'a besoin d'un terminal ni du banc. La couture avec l'ecran est
mesuree separement, dans `test_ecran_projet_tui.py`.

**La regle des fabriques est appliquee, pas citee.** Chaque fabrique de ce
fichier produit au moins deux entrees DISTINGUABLES -- des noms differents, des
cardinaux differents, des etats differents -- et les tests placent leur cible
ailleurs qu'en premiere position. Les trois appariements a risque de cette
story sont exactement du type qu'une fixture uniforme ne demasque pas.
"""
from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
if str(RACINE / "src") not in sys.path:  # pragma: no cover - amorce du banc
    sys.path.insert(0, str(RACINE / "src"))

import pytest

from mixed_media_utility.tui import explorateur, jetons

MAQUETTES = (RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")


# ---------------------------------------------------------------------------
# Fabriques. Deux entrees distinguables au MINIMUM, jamais un remplissage
# uniforme : une permutation ne se voit que si les elements different.
# ---------------------------------------------------------------------------

def arborescence(tmp_path, noms, sous_dossiers=None, fichiers=None):
    """Cree des dossiers portant des nombres de sous-dossiers DIFFERENTS.

    ``sous_dossiers`` associe un nom a son cardinal ; les absents en recoivent
    un derive de leur rang, donc jamais deux fois le meme. Une fabrique qui
    donnerait a tous le meme cardinal rendrait invisible une erreur
    d'appariement entre une ligne et sa colonne de droite.

    ``fichiers`` associe un nom de fichier a sa TAILLE, en octets, et pose les
    fichiers a cote des dossiers. Deux raisons de l'avoir ici plutot qu'ecrit a
    la main dans chaque test : la variante fichiers est la seule ou l'ordre
    « dossiers puis fichiers » existe -- une fabrique qui ne produirait que des
    dossiers ne le mettrait jamais en tension (finding `F21`) -- et des tailles
    distinctes rendent la colonne de droite des fichiers aussi distinguable que
    celle des dossiers.
    """
    sous_dossiers = sous_dossiers or {}
    base = tmp_path / "arbo"
    base.mkdir(parents=True, exist_ok=True)
    for rang, nom in enumerate(noms):
        dossier = base / nom
        dossier.mkdir()
        for n in range(sous_dossiers.get(nom, rang)):
            (dossier / f"sous_{n}").mkdir()
    for nom, taille in (fichiers or {}).items():
        (base / nom).write_bytes(b"x" * taille)
    return base


class DossierBloque:
    """Un chemin dont TOUTE question au systeme de fichiers echoue.

    **Pourquoi pas un vrai `chmod 000`** : le conteneur de session tourne en
    `root`, ou un `chmod 000` ne bloque rien. Un test qui compterait dessus
    serait vert pour la mauvaise raison -- et c'est exactement le genre de
    faux-vert que la campagne de mutation a trouve dans le test precedent.

    Le refus passe donc par le point d'injection prevu par le constructeur --
    `lister` --, avec un objet qui repond `name` et leve `OSError` sur tout le
    reste : c'est ce que rend un dossier dont le volume vient d'etre debranche,
    ou dont les droits de traversee sont retires sous un vrai compte.
    """

    def __init__(self, nom: str) -> None:
        self.name = nom

    def _refuse(self, *_):
        raise OSError(13, "Permission denied")

    is_dir = is_symlink = exists = _refuse

    def __repr__(self) -> str:            # pragma: no cover - confort de debug
        return f"DossierBloque({self.name!r})"


def arborescence_avec_un_bloque(tmp_path, nom_bloque="mm_interdit"):
    """Deux dossiers lisibles DISTINGUABLES, et un illisible AU MILIEU.

    Regle des fabriques : les deux dossiers lisibles portent des cardinaux
    differents, et la cible du test -- l'entree illisible -- n'est ni la
    premiere ni la derniere. Un `find` fautif qui rendrait toujours le premier
    element ne se demasque pas autrement.
    """
    base = arborescence(tmp_path, ["aa_lisible", "zz_lisible"],
                        {"aa_lisible": 2, "zz_lisible": 7})
    (base / ".cache").mkdir()

    def lister(_):
        return [base / "aa_lisible", DossierBloque(nom_bloque),
                base / "zz_lisible", base / ".cache"]

    return base, lister


#: Deux noms de dossier LONGS et distinguables, a la convention de nommage du
#: metier. La ligne de liste debordait des **54** caracteres de nom, l'etiquette
#: de validation des **60** en UTF-8 et des **55** en `--ascii` : une fabrique
#: qui s'arrete a 30 caracteres ne peut atteindre aucune des trois frontieres.
#: Les deux ne different que par leur QUEUE -- c'est ce qui mesure qu'un
#: abregement ne les rend pas identiques a l'ecran.
NOMS_LONGS = (
    "2026-08-29_tournage_exterieur_nuit_camera_A_prise_longue",
    "2026-08-29_tournage_exterieur_nuit_camera_B_prise_longue",
)

#: Vingt ideogrammes : **20 caracteres et 40 colonnes**. Une mesure faite en
#: `len()` le croit deux fois plus court qu'il n'est, et c'est la moitie de la
#: famille de debordement que la revue de la vague 1 avait deja payee sur un
#: nom de projet japonais.
NOM_DOUBLE_CHASSE = "\u6771\u4eac" * 20


def arborescence_aux_noms_LONGS(tmp_path):
    """Des noms qui ATTEIGNENT la frontiere, et un nom double chasse.

    Regle des fabriques : quatre entrees distinguables -- un nom court, les
    deux longs qui ne different que par leur queue, et le nom en ideogrammes --
    et les cibles du test ne sont **pas** en premiere position. Une fixture
    dont tous les noms sont courts ne mesure aucune largeur.
    """
    return arborescence(
        tmp_path,
        ["01_court", NOMS_LONGS[0], NOM_DOUBLE_CHASSE, NOMS_LONGS[1]],
        {"01_court": 0, NOMS_LONGS[0]: 3, NOM_DOUBLE_CHASSE: 11,
         NOMS_LONGS[1]: 27})


def arborescence_aux_ETATS_distincts(tmp_path):
    """Les colonnes de droite qui portent un GLYPHE, pas seulement un compte.

    C'est la fabrique qui manquait au test de repli ASCII : la sienne etait
    `arborescence(tmp_path, ["a", "b", "c"])`, dont les trois entrees rendent
    `0 sous-dossier`, `1 sous-dossier`, `2 sous-dossiers` -- **deja ASCII
    toutes les trois**. Le test faisait varier le mauvais axe et etait vert pour
    une raison sans rapport avec ce qu'il annonce (finding `F7`).

    Les cinq colonnes qui portent un glyphe sont donc toutes representees :
    `● projet`, `· sous-dossiers` (volume qui ne se compte pas), `✕ illisible`,
    `· pas une source` (fichier hors filtre) et `· taille inconnue` (fichier
    disparu entre le listage et le rendu). L'entree illisible est en
    **deuxieme** position, jamais en premiere.
    """
    base = arborescence(tmp_path, ["aa_compte", "mm_projet", "zz_lent"],
                        {"aa_compte": 2, "mm_projet": 5, "zz_lent": 9},
                        fichiers={"nn_note.txt": 12, "pp_prise.mp4": 4096})

    def lister(_):
        return [base / "aa_compte", DossierBloque("kk_interdit"),
                base / "mm_projet", base / "zz_lent", base / "nn_note.txt",
                base / "pp_prise.mp4", base / "qq_disparue.mp4"]

    exp = explorateur_sur(
        base, montrer_fichiers=True, lister=lister,
        accepte=lambda c: c.suffix == ".mp4",
        compter_sous_dossiers=lambda c: None if c.name == "zz_lent" else 1,
        porte_un_projet=lambda c: c.name == "mm_projet")
    return exp


def explorateur_sur(base, **kwargs):
    return explorateur.Explorateur(base, **kwargs)


def lignes_lues(exp, utile=76, ascii_seul=False):
    """Ce que la zone de liste RENVOIE, relu comme l'operateur le lit.

    Rend un triplet `(nom, droite, porte_le_curseur)` par ligne d'entree, dans
    l'ordre du rendu, les `…` et les lignes de remplissage exclus. C'est la
    seule facon de mesurer l'appariement `ligne rendue <-> entree` : tous les
    tests qui interrogent `exp.entrees` mesurent le MODELE, et une permutation
    posee dans le rendu leur echappe par construction (finding `E1`).
    """
    table = jetons.glyphes(ascii_seul)
    points = explorateur.symbole(explorateur.ELLIPSE, ascii_seul)
    lues = []
    for ligne in exp.lignes_de_liste(utile, ascii_seul):
        corps = ligne.strip()
        if not corps:
            continue
        curseur = corps.startswith(table["curseur"] + " ")
        if curseur:
            corps = corps[len(table["curseur"]):].strip()
        morceaux = re.split(r"\s{2,}", corps)
        nom = morceaux[0]
        if nom == points:
            continue                       # la ligne des `…` n'est pas une entree
        lues.append((nom, morceaux[1] if len(morceaux) > 1 else "", curseur))
    return lues


# ---------------------------------------------------------------------------
# AC 3.3 -- il n'y a JAMAIS deux curseurs
# ---------------------------------------------------------------------------

def test_le_curseur_ne_sort_JAMAIS_de_la_liste(tmp_path):
    """`EPIC11-ARB-50`, sur un constat d'Egan devant la maquette v1 : « il y a
    deux curseurs sur ton image. Impossible. » C'etait vrai, et c'etait la
    consequence d'avoir rendu les deux etiquettes focalisables.

    Le balayage va **au-dela** des bornes dans les deux sens : c'est la ou une
    borne mal ecrite laisserait le curseur s'echapper.
    """
    base = arborescence(tmp_path, [f"{n:02d}_dossier" for n in range(27)])
    exp = explorateur_sur(base)

    for _ in range(40):
        exp.deplacer(1)
        assert 0 <= exp.curseur < len(exp.entrees)
    for _ in range(40):
        exp.deplacer(-1)
        assert 0 <= exp.curseur < len(exp.entrees)


def test_un_seul_glyphe_de_curseur_dans_TOUT_le_balayage(tmp_path):
    """Volet symetrique du precedent, mesure sur le RENDU et non sur l'etat.

    Un modele juste dont le rendu poserait deux fleches serait un ecran faux :
    c'est exactement ce qu'Egan a vu, et le modele de la v1 etait « juste ».
    """
    base = arborescence(tmp_path, [f"{n:02d}_dossier" for n in range(27)])
    exp = explorateur_sur(base)
    marque = jetons.GLYPHES["curseur"]

    for _ in range(30):
        lignes = exp.lignes(80, titre="Ouvrir un projet")
        combien = sum(1 for ligne in lignes if marque in ligne)
        assert combien == 1, (combien, lignes)
        exp.deplacer(1)


def test_l_etiquette_du_bas_SUIT_le_curseur(tmp_path):
    """AC 3.4. Deux calculs separes -- l'entree courante et ce que l'etiquette
    annonce -- divergeraient au premier defilement. La cible est prise au
    DIXIEME rang, jamais au premier."""
    noms = [f"{n:02d}_dossier" for n in range(27)]
    exp = explorateur_sur(arborescence(tmp_path, noms))
    for _ in range(10):
        exp.deplacer(1)

    assert exp.entree_courante.chemin.name == "10_dossier"
    assert "10_dossier/" in exp.ligne_de_validation()
    assert exp.valider().name == "10_dossier"


# ---------------------------------------------------------------------------
# Appariement positionnel : ligne rendue <-> entree, glyphe <-> curseur, rang
# peint <-> ligne peinte. Famille CRITIQUE de la politique de revue (zero
# survivant), et le defaut que ce depot a deja paye trois fois -- 5.6/`M33`,
# 5.7/`M25`, 5.8. Il ne se voit QUE sur la sortie rendue : un test qui
# interroge `exp.entrees` mesure le modele, et le modele est juste.
# ---------------------------------------------------------------------------

def test_chaque_ligne_rendue_porte_l_entree_DE_SON_RANG(tmp_path):
    """Finding `E1`. Le mutant qui retourne la fenetre
    (`entrees[premier + dernier - rang]`) laissait 682 tests verts : tous
    portaient sur `exp.entrees` ou sur la presence des `…`, aucun ne comparait
    le TEXTE rendu, ligne a ligne, aux entrees de la fenetre.

    La mesure porte sur une fenetre DECALEE (`premier > 0`) : une permutation
    interne a la fenetre reste invisible tant qu'on ne regarde que la premiere.
    Consequence terrain de ce mutant : les bons noms dans le mauvais ordre, le
    curseur designe une ligne et `⏎` en valide une autre.
    """
    noms = [f"{n:02d}_dossier" for n in range(27)]
    exp = explorateur_sur(arborescence(tmp_path, noms))
    for _ in range(14):
        exp.deplacer(1)

    premier, dernier = exp.fenetre()
    assert premier > 0, "la fenetre doit avoir defile"
    attendu = [(exp.entrees[rang].nom, exp.entrees[rang].droite)
               for rang in range(premier, dernier + 1)]
    rendu = [(nom, droite) for nom, droite, _ in lignes_lues(exp)]
    assert rendu == attendu, (rendu, attendu)


def test_le_glyphe_de_curseur_est_sur_la_ligne_de_l_ENTREE_COURANTE(tmp_path):
    """Finding `E2`. `test_un_seul_glyphe_de_curseur_dans_TOUT_le_balayage`
    compte COMBIEN de glyphes sont rendus ; il ne dit jamais sur QUELLE ligne.
    Un glyphe pose un rang plus bas reste unique -- c'est le grief d'Egan
    (« il y a deux curseurs sur ton image ») dans sa variante silencieuse : un
    seul curseur, au mauvais endroit.

    Le balayage descend PUIS remonte. En descendant, le curseur colle au bas de
    la fenetre, ou un decalage de +1 est ecrete par la borne et ne se voit pas ;
    en remontant il colle au haut, et le decalage mord.
    """
    noms = [f"{n:02d}_dossier" for n in range(27)]
    exp = explorateur_sur(arborescence(tmp_path, noms))

    for pas in [1] * 26 + [-1] * 26:
        portees = [nom for nom, _, curseur in lignes_lues(exp) if curseur]
        assert portees == [exp.entree_courante.nom], (portees, exp.curseur)
        exp.deplacer(pas)


def test_le_rang_du_curseur_DESIGNE_la_ligne_qui_porte_le_glyphe(tmp_path):
    """Findings `F2` et `E3`, etat liste. `rang_du_curseur()` est la SEULE
    garde de la correction du defaut n. 3 : `jetons.peindre` auto-detectait la
    ligne a peindre par un `startswith` qui echoue en silence sur les lignes
    indentees, et la correction fut de passer le rang explicitement. Remplacer
    une detection silencieuse par un calcul non mesure ne ferme pas le trou :
    quatre mutations de ce rang -- constante decalee, decalage de defilement
    oublie, position dans la fenetre oubliee -- passaient inapercues.

    Le balayage complet couvre les DEUX regimes du decalage : `premier == 0`
    (aucune ligne `…` en tete) et `premier > 0` (elle en prend une).
    """
    noms = [f"{n:02d}_dossier" for n in range(27)]
    exp = explorateur_sur(arborescence(tmp_path, noms))
    marque = jetons.GLYPHES["curseur"]

    regimes = set()
    for pas in [1] * 26 + [-1] * 26:
        lignes = exp.lignes(80, titre="Ouvrir un projet")
        rang = exp.rang_du_curseur()
        portantes = [n for n, ligne in enumerate(lignes) if marque in ligne]
        assert portantes == [rang], (portantes, rang, exp.curseur)
        assert exp.entree_courante.nom in lignes[rang], lignes[rang]
        regimes.add(exp.fenetre()[0] > 0)
        exp.deplacer(pas)
    assert regimes == {False, True}, regimes


def test_dans_la_saisie_le_rang_du_curseur_DESIGNE_la_barre_d_adresse(tmp_path):
    """Findings `F2` et `E3`, etat saisie. Sous le mutant `return 3`, la
    surbrillance se pose sur l'etiquette `← …/Documents/` pendant que le caret
    clignote sur la barre d'adresse : ce sont les DEUX curseurs qu'
    `EPIC11-ARB-50` interdit, dans leur variante silencieuse.
    """
    exp = explorateur_sur(arborescence(tmp_path, ["cible", "voisin"]))
    exp.deplacer(1)                        # le curseur de liste n'est PAS en tete
    exp.basculer_la_saisie()

    lignes = exp.lignes(80, titre="Ouvrir un projet")
    rang = exp.rang_du_curseur()
    attendue = exp.ligne_d_adresse(jetons.largeur_utile(80), "Dossier", False)
    assert lignes[rang] == attendue, (rang, lignes[rang], attendue)
    porteuses = [n for n, ligne in enumerate(lignes)
                 if jetons.GLYPHES["caret"] in ligne]
    assert porteuses == [rang], (porteuses, rang)
    assert explorateur.PARENT not in lignes[rang], "ce n'est pas l'etiquette du haut"


def test_l_etiquette_du_haut_NOMME_le_dossier_parent(tmp_path):
    """Survivant trouve par l'orchestrateur de la revue : retirer
    `parent.name` de `nom_court_du_parent` laissait TOUTE la suite `tui` verte,
    et l'etiquette rendait `…/` -- une fleche et un separateur, sans
    destination.

    C'est exactement ce qu'Egan a demande, verbatim le 2026-08-29 : « mettre
    juste la fleche et "...\\Documents\\" au lieu du chemin complet ». Le nom
    du parent EST l'information de cette ligne, et `EPIC11-ARB-50` en fait une
    etiquette VIVE : « celle du haut dit ou `←` mene ». Les tests existants
    n'en mesuraient que la FORME -- calee a gauche, `←` en tete -- jamais le
    CONTENU.
    """
    base = arborescence(tmp_path, ["cible", "voisin"])
    sep = "/" if "/" in str(base) else "\\"
    exp = explorateur_sur(base / "cible")

    assert exp.nom_court_du_parent() == f"{explorateur.ELLIPSE}{sep}arbo{sep}"
    assert exp.nom_court_du_parent(True) == f"...{sep}arbo{sep}"

    etiquette = exp.lignes(80, titre="Ouvrir un projet")[3]
    assert etiquette.startswith(f"   {explorateur.PARENT}  "), etiquette
    assert etiquette.strip().endswith(f"{sep}arbo{sep}"), etiquette

    # A la racine d'un volume il n'y a pas de nom a dire : c'est le seul regime
    # ou l'etiquette n'en porte pas, et il ne doit pas masquer le precedent.
    racine = explorateur.Explorateur(Path(tmp_path.anchor), lister=lambda _: [])
    assert racine.nom_court_du_parent() == "Volumes"


# ---------------------------------------------------------------------------
# AC 4 -- la liste, sa fenetre, et sa colonne de droite
# ---------------------------------------------------------------------------

def test_la_zone_de_liste_garde_sa_hauteur_de_ZERO_a_DEUX_CENTS(tmp_path):
    """AC 4.1. Les deux etiquettes encadrantes ne bougent jamais d'une ligne :
    une cible qui se deplace quand la liste change de longueur est une cible
    qu'on rate."""
    hauteurs = set()
    for combien in (0, 1, 9, 27, 200):
        base = arborescence(tmp_path / f"n{combien}",
                            [f"{n:03d}_d" for n in range(combien)])
        lignes = explorateur_sur(base).lignes(80, titre="T")
        hauteurs.add(len(lignes))
    assert hauteurs == {17}, hauteurs


def test_les_points_de_suspension_disent_de_QUEL_cote_il_reste(tmp_path):
    """AC 4.2 et 4.3, dans les trois positions -- haut, milieu, bas."""
    noms = [f"{n:02d}_dossier" for n in range(27)]
    exp = explorateur_sur(arborescence(tmp_path, noms))
    points = explorateur.ELLIPSE

    def zone():
        return exp.lignes_de_liste(76, False)

    haut = zone()
    assert not haut[0].strip().startswith(points), "rien au-dessus, au depart"
    assert haut[-1].strip().startswith(points), "il reste du contenu en dessous"
    assert "sur 27" in haut[-1]

    for _ in range(13):
        exp.deplacer(1)
    milieu = zone()
    assert milieu[0].strip().startswith(points)
    assert milieu[-1].strip().startswith(points)

    for _ in range(26):
        exp.deplacer(1)
    bas = zone()
    assert bas[0].strip().startswith(points)
    assert not bas[-1].strip().startswith(points), "plus rien en dessous"


def test_la_position_annoncee_est_celle_qu_on_VOIT(tmp_path):
    """AC 4.3. Le compteur `11-17 sur 27` doit decrire la fenetre reelle : un
    decalage d'un rang ferait pointer le curseur sur le voisin."""
    noms = [f"{n:02d}_dossier" for n in range(27)]
    exp = explorateur_sur(arborescence(tmp_path, noms))
    for _ in range(20):
        exp.deplacer(1)

    premier, dernier = exp.fenetre()
    ligne = [l for l in exp.lignes_de_liste(76, False)
             if "sur 27" in l][0]
    assert f"{premier + 1}-{dernier + 1} sur 27" in ligne, ligne
    visibles = [exp.entrees[r].chemin.name for r in range(premier, dernier + 1)]
    assert exp.entree_courante.chemin.name in visibles


def test_la_colonne_de_droite_distingue_les_lignes(tmp_path):
    """AC 4.4. Trois dossiers a trois cardinaux differents : une fabrique qui
    leur donnerait le meme nombre laisserait passer une inversion."""
    base = arborescence(tmp_path, ["alpha", "beta", "gamma"],
                        {"alpha": 0, "beta": 3, "gamma": 12})
    exp = explorateur_sur(base)
    droites = {e.chemin.name: e.droite for e in exp.entrees}
    assert droites["alpha"] == "0 sous-dossier", droites
    assert droites["beta"] == "3 sous-dossiers", droites
    assert droites["gamma"] == "12 sous-dossiers", droites


def test_un_compte_INDISPONIBLE_rend_le_point_median_et_jamais_zero(tmp_path):
    """AC 4.5. `None` et `0` ne sont pas la meme information, et l'ecran ne doit
    pas les confondre : un volume lent n'est pas un dossier vide."""
    base = arborescence(tmp_path, ["lent", "vide"], {"vide": 0})
    exp = explorateur_sur(base, compter_sous_dossiers=lambda c:
                          None if c.name == "lent" else 0)
    droites = {e.chemin.name: e.droite for e in exp.entrees}
    assert droites["lent"].startswith(jetons.GLYPHES["neutre"]), droites
    assert droites["vide"] == "0 sous-dossier", droites


def test_le_comptage_ne_paie_QUE_les_lignes_VISIBLES(tmp_path):
    """AC 4.6, finding `F-1`. La mesure de la couche 3 : 27 dossiers, 8 lignes
    visibles, **27 appels** a `compter_sous_dossiers` -- donc 27 `iterdir()` a
    chaque `relire()`. `relire()` construisait une `Entree` complete pour chaque
    chemin avant tout decoupage de fenetre. Sur les 150 a 200 dossiers du cas
    nominal, et sur le volume reseau que l'AC 4.5 anticipe (« volume lent »),
    c'est la latence que l'AC existait pour empecher. Aucun test ne l'abordait.

    Ce test **compte les appels** ; ce n'est pas un test de duree, qui serait
    instable et ne dirait pas ou passe le temps.

    Regle des fabriques : 27 dossiers pour 8 lignes visibles -- bien plus que
    la fenetre --, des cardinaux tous differents, et la cible du second volet
    au rang 20, loin de la premiere position. Une fixture de la taille de la
    fenetre serait verte avec ou sans paresse.
    """
    noms = [f"{n:02d}_dossier" for n in range(27)]
    base = arborescence(tmp_path, noms, {nom: 0 for nom in noms})

    appels: list[str] = []

    def compter(chemin):
        appels.append(chemin.name)
        return int(chemin.name[:2])        # un cardinal DIFFERENT par dossier

    exp = explorateur_sur(base, compter_sous_dossiers=compter)
    assert appels == [], "construire la liste ne compte RIEN"

    lues = lignes_lues(exp)
    premier, dernier = exp.fenetre()
    visibles = [e.chemin.name for e in exp.entrees[premier:dernier + 1]]
    assert len(visibles) == 8, visibles
    assert appels == visibles, (appels, visibles)
    assert len(appels) < len(exp.entrees), "27 dossiers, 8 comptages"

    # Et le compte rendu est bien celui de SA ligne : une colonne paresseuse
    # qui se tromperait de chemin serait le meme defaut d'appariement que la
    # revue a trouve cinq fois dans ce lot.
    assert [(nom, droite) for nom, droite, _ in lues] == [
        (f"{n:02d}_dossier/",
         f"{n} sous-dossier" + ("s" if n > 1 else "")) for n in range(8)]

    # La cible est au rang 20 : elle n'est pas payee tant qu'elle n'est pas vue.
    assert "20_dossier" not in appels
    while exp.entree_courante.chemin.name != "20_dossier":
        assert exp.deplacer(1)
    assert "20_dossier" not in appels, "se deplacer ne compte pas, RENDRE compte"
    rendues = {nom: droite for nom, droite, _ in lignes_lues(exp)}
    assert rendues["20_dossier/"] == "20 sous-dossiers", rendues
    assert "20_dossier" in appels
    assert len(appels) == len(set(appels)), "un compte deja paye ne se repaie pas"


def test_un_dossier_qui_porte_un_projet_est_MARQUE(tmp_path):
    """AC 4.4. La fabrique en pose DEUX sur cinq, et pas le premier : un
    marquage qui suivrait le rang au lieu du contenu passerait autrement."""
    noms = ["aa", "bb_projet", "cc", "dd_projet", "ee"]
    base = arborescence(tmp_path, noms)
    exp = explorateur_sur(base,
                          porte_un_projet=lambda c: c.name.endswith("_projet"))
    marques = [e.chemin.name for e in exp.entrees if e.porte_un_projet]
    assert marques == ["bb_projet", "dd_projet"], marques
    assert all(jetons.GLYPHES["complete"] in e.droite
               for e in exp.entrees if e.porte_un_projet)
    assert "2 projets" in exp.etat(), exp.etat()


def test_zero_projet_est_une_MESURE_et_pas_un_silence(tmp_path):
    """Volet symetrique : la maquette `X1` affiche « aucun projet », et c'est
    l'information que l'operateur cherche en arrivant. La taire ferait croire
    que le compte n'a pas ete fait."""
    exp = explorateur_sur(arborescence(tmp_path, ["a", "b"]))
    assert "aucun projet" in exp.etat(), exp.etat()


# ---------------------------------------------------------------------------
# AC 2 -- le clavier
# ---------------------------------------------------------------------------

def test_le_saut_est_insensible_a_la_CASSE_et_aux_ACCENTS(tmp_path):
    """AC 2.4. Sans le repli, la moitie des dossiers d'un montage francais
    seraient inatteignables au saut.

    La fixture porte DEUX entrees en `e` -- une accentuee, une non -- et la
    cible du second saut est la SECONDE : une fixture a initiales toutes
    distinctes ne distingue pas « premiere correspondance » de « derniere »,
    et c'est ce qui laissait survivre le mutant qui inverse le sens de
    balayage (finding `E5` -- le `M25` de la story 5.7 a l'identique).
    """
    base = arborescence(tmp_path, ["Alpha", "Étalonnage", "Etendue", "zoulou"])
    exp = explorateur_sur(base)
    assert exp.sauter("e")
    assert exp.entree_courante.chemin.name == "Étalonnage"
    assert exp.sauter("e"), "la correspondance SUIVANTE, pas la premiere"
    assert exp.entree_courante.chemin.name == "Etendue"
    assert exp.sauter("a")
    assert exp.entree_courante.chemin.name == "Alpha"


def test_le_saut_CYCLE_sur_les_dossiers_NUMEROTES_du_metier(tmp_path):
    """Volet produit du finding `E5`. Avant correction, `sauter('0')` deux fois
    de suite laissait le curseur sur `01_reperages` : le saut etait inoperant
    au-dela de la premiere correspondance, c'est-a-dire sur les dossiers `01_`,
    `02_`, `03_` -- le cas nominal d'Egan, et l'exemple que le docstring de
    `sauter` cite lui-meme comme sa raison d'exister.

    Le curseur part du QUATRIEME rang : la premiere correspondance est donc
    derriere lui, et seul un balayage qui fait le tour la trouve.
    """
    base = arborescence(tmp_path, ["01_reperages", "02_tournage", "03_essais",
                                   "azalee", "zebre"])
    exp = explorateur_sur(base)
    exp.deplacer(3)
    assert exp.entree_courante.chemin.name == "azalee"

    vus = []
    for _ in range(4):
        assert exp.sauter("0")
        vus.append(exp.entree_courante.chemin.name)
    assert vus == ["01_reperages", "02_tournage", "03_essais",
                   "01_reperages"], vus

    # Frontiere negative : une initiale que personne ne porte ne bouge rien.
    assert exp.sauter("q") is False
    assert exp.entree_courante.chemin.name == "01_reperages"


def test_les_DOSSIERS_precedent_les_FICHIERS_dans_le_RENDU(tmp_path):
    """Finding `F21`. Le seul test de la variante fichiers comparait un
    ENSEMBLE -- aveugle a l'ordre par construction -- et le mutant qui
    concatene les fichiers AVANT les dossiers survivait. L'ordre est pourtant
    ce qui fixe le rang de chaque entree, donc la fenetre, le saut, l'etiquette
    du bas et le rang du curseur.

    Les noms sont choisis pour que les deux ordres DIFFERENT : tries ensemble,
    `alpha.tiff` passerait devant `bravo_dossier`. Et la colonne de droite est
    lue en meme temps que le nom -- c'est le meme appariement.
    """
    base = arborescence(tmp_path, ["bravo_dossier", "delta_dossier"],
                        {"bravo_dossier": 0, "delta_dossier": 4},
                        fichiers={"alpha.tiff": 1024, "charlie.tiff": 3072})
    # **Deux cardinaux de FICHIERS distincts, et il a fallu les poser.** Depuis
    # `EPIC11-ARB-121`, la colonne d'un dossier compte ce que le site cherche :
    # ici des fichiers. Les deux dossiers n'en portaient aucun, donc leurs
    # colonnes de droite devenaient IDENTIQUES -- et une fabrique dont deux
    # elements ne se distinguent plus ne demasque plus une erreur
    # d'appariement, ce que ce test existe justement pour mesurer.
    for n in range(1):
        (base / "bravo_dossier" / f"b{n}.tiff").write_bytes(b"b")
    for n in range(3):
        (base / "delta_dossier" / f"d{n}.tiff").write_bytes(b"d")
    exp = explorateur_sur(base, montrer_fichiers=True)

    assert [(nom, droite) for nom, droite, _ in lignes_lues(exp)] == [
        ("bravo_dossier/", "1 fichier"),
        ("delta_dossier/", "3 fichiers"),
        ("alpha.tiff", "1,0 ko"),
        ("charlie.tiff", "3,0 ko"),
    ]


def test_un_dossier_ILLISIBLE_se_voit_et_ne_s_entre_pas(tmp_path):
    """AC 6.3, mesuree ENTIEREMENT : la croix, le refus, le motif.

    La version precedente de ce test (findings `F12`, `E4`, `F-7` -- les TROIS
    couches l'ont trouvee) creait deux dossiers parfaitement lisibles, definis-
    sait une classe `Bloque` jamais utilisee, et n'assurait qu'une chose :
    `"interdit" in noms`, vraie pour un dossier ordinaire. Sa fixture rendait
    `None` sur `compter_sous_dossiers`, ce qui faisait passer
    `_entree_de_dossier` par la branche `compte is None` : l'entree produite
    etait `entrable=True`, avec `· sous-dossiers` et **sans `✕`**. La branche
    illisible n'etait jamais atteinte, et le mutant qui retire
    `entrable=False, validable=False` survivait.

    Ce qui se mesure ici, c'est la chaine complete du produit : l'entree reste
    LISTEE et a sa place dans l'ordre, elle porte `✕` **dans le rendu**, elle
    refuse l'entree, elle le DIT, et elle ne se valide pas.
    """
    base, lister = arborescence_avec_un_bloque(tmp_path)
    exp = explorateur_sur(base, lister=lister)

    par_nom = {e.chemin.name: e for e in exp.entrees}
    assert list(par_nom) == ["aa_lisible", "mm_interdit", "zz_lisible"], \
        "il reste LISTE, et a sa place dans l'ordre"

    bloque = par_nom["mm_interdit"]
    assert bloque.droite == jetons.marque("absent", "illisible"), bloque.droite
    assert jetons.GLYPHES["absent"] in bloque.droite
    assert bloque.entrable is False, "il ne s'entre pas"
    assert bloque.validable is False, "et il ne se valide pas davantage"
    assert bloque.illisible is True, "il se compte a part, pas en sous-dossier"

    # Le RENDU le porte aussi : une garde de modele que la ligne rendue perdrait
    # ne protegerait personne.
    rendu = {nom: droite for nom, droite, _ in lignes_lues(exp)}
    assert rendu["mm_interdit/"] == jetons.marque("absent", "illisible"), rendu

    # Le refus, et son MOTIF.
    assert exp.sauter("m")
    assert exp.entree_courante.chemin.name == "mm_interdit"
    assert exp.entrer() is False
    assert exp.dossier == base, "on n'y est pas descendu"
    assert exp.etat() == "mm_interdit ne se lit pas", exp.etat()
    assert exp.cible_de_validation() is None
    assert explorateur.RIEN_A_VALIDER in exp.ligne_de_validation()

    # Volet symetrique : le voisin lisible, lui, s'entre.
    assert exp.sauter("z")
    assert exp.entrer() is True
    assert exp.dossier == base / "zz_lisible"


def test_le_refus_d_entree_ne_SURVIT_pas_au_premier_geste(tmp_path):
    """Findings `F4`, `E7`, `E8` : le motif de refus etait COLLANT.

    `_refus` n'etait efface que par `entrer()` reussi, `remonter()` et
    `_suivre_la_saisie()` ; `etat()` le rend en priorite absolue. La ligne
    d'etat continuait donc de nommer une entree qui n'etait plus sous le
    curseur, et -- corollaire mesure par la couche 1 -- les cinq mesures
    (`sous-dossiers`, `illisibles`, `projets`, `caches`) restaient invisibles
    jusqu'a un changement de dossier.

    Le volet negatif compte autant : un geste qui n'aboutit pas n'efface rien,
    sans quoi il suffirait d'effacer `_refus` en tete d'`etat()` pour rendre ce
    test vert sans rien corriger.
    """
    base, lister = arborescence_avec_un_bloque(tmp_path)
    exp = explorateur_sur(base, lister=lister)
    mesure = "2 sous-dossiers · 1 illisible · aucun projet · 1 dossier cache"
    assert exp.etat() == mesure, exp.etat()

    assert exp.sauter("m")
    assert exp.entrer() is False
    assert exp.etat() == "mm_interdit ne se lit pas"

    # Le curseur bouge : la ligne d'etat cesse de nommer l'ancienne entree.
    assert exp.deplacer(1)
    assert exp.entree_courante.chemin.name == "zz_lisible"
    assert exp.etat() == mesure, exp.etat()

    # Meme chose pour le saut et pour la bascule des caches -- c'est par eux
    # que le compte masque redevenait annoncable.
    assert exp.sauter("m") and exp.entrer() is False
    assert exp.sauter("a")
    assert exp.etat() == mesure, exp.etat()
    assert exp.sauter("m") and exp.entrer() is False
    assert exp.basculer_les_caches()
    assert "cach" not in exp.etat(), exp.etat()
    assert exp.etat() == "3 sous-dossiers · 1 illisible · aucun projet"

    # Frontiere negative : un geste qui n'aboutit pas ne l'efface PAS.
    exp.basculer_les_caches()
    assert exp.sauter("m") and exp.entrer() is False
    assert exp.sauter("q") is False, "aucune initiale en q"
    assert exp.etat() == "mm_interdit ne se lit pas", exp.etat()


def test_le_message_du_DEPART_ILLISIBLE_ne_masque_pas_la_SESSION(tmp_path):
    """Finding `E8`. Le message dit un fait vrai **au montage** ; pose une fois
    pour toutes, il supprimait la ligne d'etat pour le reste de la session --
    `EPIC11-ARB-56` veut une MESURE en ligne d'etat.
    """
    repli = arborescence(tmp_path / "personnel", ["aa_replie", "zz_replie"],
                         {"aa_replie": 0, "zz_replie": 4})
    exp = explorateur.Explorateur(tmp_path / "volume_debranche",
                                  dossier_de_repli=repli)
    assert exp.dossier == repli
    assert "illisible" in exp.etat(), exp.etat()

    assert exp.deplacer(1)
    assert exp.etat() == "2 sous-dossiers · aucun projet", exp.etat()


def test_montrer_fichiers_FAUX_ne_liste_AUCUN_fichier(tmp_path):
    """Finding `E6`. C'est le reglage des **cinq sites** « choisir un dossier »,
    c'est-a-dire le regime nominal -- et aucune fixture contenant des fichiers
    ne l'exercait : la fabrique ne creait que des dossiers, et les trois tests
    qui creaient des fichiers passaient tous `montrer_fichiers=True`. Le mutant
    qui remplace `fichiers = []` par `pass` survivait donc, et sous lui un
    dossier de rushes listerait ses centaines de fichiers dans la zone de neuf
    lignes.

    Les noms sont choisis pour que les deux ordres DIFFERENT : tries ensemble,
    `bb_rush.mov` passerait devant `zz_dossier`. Un filtre absent ne se verrait
    pas sur une fixture ou fichiers et dossiers sont deja ordonnes pareil.
    """
    base = arborescence(tmp_path, ["aa_dossier", "zz_dossier"],
                        {"aa_dossier": 0, "zz_dossier": 5},
                        fichiers={"bb_rush.mov": 2048, "yy_notes.txt": 16})

    exp = explorateur_sur(base)                 # le reglage par DEFAUT
    assert [e.chemin.name for e in exp.entrees] == ["aa_dossier", "zz_dossier"]
    assert [nom for nom, _, _ in lignes_lues(exp)] == ["aa_dossier/",
                                                       "zz_dossier/"]
    assert exp.etat() == "2 sous-dossiers · aucun projet", exp.etat()
    assert "fichier" not in exp.etat(), exp.etat()

    # Volet symetrique : la variante fichiers les rend TOUS, dossiers d'abord.
    avec = explorateur.Explorateur(base, montrer_fichiers=True)
    assert [e.chemin.name for e in avec.entrees] == [
        "aa_dossier", "zz_dossier", "bb_rush.mov", "yy_notes.txt"]
    assert "2 fichiers" in avec.etat(), avec.etat()


def test_un_lien_symbolique_CASSE_ou_en_BOUCLE_reste_VISIBLE(tmp_path):
    """Finding `E16`. Il ne s'affichait meme pas comme illisible : il n'etait
    simplement **pas la**. `is_dir()` rend faux sur un lien casse ou en boucle,
    donc il tombait dans les fichiers -- et les fichiers sont supprimes quand
    `montrer_fichiers` est faux, c'est-a-dire dans le regime nominal.

    Un lien casse vers un rush deplace est **le** symptome que l'operateur
    cherche ; la regle du module -- « les masquer ferait croire qu'ils
    n'existent pas » -- vaut d'abord pour lui. Et il ne se compte pas en
    sous-dossier : rien n'a pu etre lu.
    """
    base = arborescence(tmp_path, ["aa_vrai", "zz_autre"],
                        {"aa_vrai": 0, "zz_autre": 6})
    (base / "mm_lien_valide").symlink_to(base / "aa_vrai")
    (base / "nn_lien_casse").symlink_to(base / "cible_deplacee")
    (base / "oo_boucle_a").symlink_to(base / "oo_boucle_b")
    (base / "oo_boucle_b").symlink_to(base / "oo_boucle_a")

    exp = explorateur_sur(base)                 # variante DOSSIERS
    par_nom = {e.chemin.name: e for e in exp.entrees}
    assert set(par_nom) == {"aa_vrai", "mm_lien_valide", "nn_lien_casse",
                            "oo_boucle_a", "oo_boucle_b", "zz_autre"}, par_nom

    for nom in ("nn_lien_casse", "oo_boucle_a", "oo_boucle_b"):
        entree = par_nom[nom]
        assert entree.illisible is True, nom
        assert entree.entrable is False and entree.validable is False, nom
        assert entree.droite == jetons.marque("absent", "illisible"), nom

    # Un lien VALIDE reste un dossier ordinaire : la question posee est « ce
    # lien mene-t-il quelque part », pas « est-ce un lien ».
    valide = par_nom["mm_lien_valide"]
    assert valide.illisible is False and valide.entrable is True
    assert valide.droite == "0 sous-dossier", valide.droite

    assert exp.etat() == "3 sous-dossiers · 3 illisibles · aucun projet", \
        exp.etat()
    assert exp.sauter("n")
    assert exp.entrer() is False
    assert exp.etat() == "nn_lien_casse ne se lit pas", exp.etat()


def test_un_lien_est_suivi_UNE_fois_et_le_chemin_reste_CELUI_qu_on_a_PRIS(
        tmp_path):
    """AC 6.8, finding `F-8`. `resolve()` **est** la resolution recursive : il
    reecrit chaque maillon du chemin jusqu'a la cible reelle. Il etait appele a
    deux endroits du chemin nominal -- au montage, et a **chaque frappe** via
    `projets.resoudre`.

    Consequence produit : naviguer dans un dossier atteint par un lien faisait
    remonter `←` vers le parent **reel**, pas vers celui d'ou l'on venait.
    L'operateur perdait sa route sans rien avoir demande.

    Le contre-sens a eviter est ecrit dans `normaliser` : suivre le lien
    nous-memes, une fois, donnerait le MEME chemin affiche que `resolve()` sur
    ce cas. « Suivi une fois » est ce que fait le systeme de fichiers a la
    lecture -- c'est le second assert ci-dessous.
    """
    reel = tmp_path / "volume_reel" / "montages"
    reel.mkdir(parents=True)
    (reel / "aa_dedans").mkdir()
    (reel / "zz_dedans").mkdir()
    atelier = tmp_path / "atelier"
    atelier.mkdir()
    (atelier / "voisin").mkdir()
    (atelier / "pont").symlink_to(reel)
    (atelier / "pont_du_pont").symlink_to(atelier / "pont")

    exp = explorateur_sur(atelier / "pont")
    assert exp.dossier == atelier / "pont", "le chemin PRIS, pas la cible reelle"
    assert [e.chemin.name for e in exp.entrees] == ["aa_dedans", "zz_dedans"], \
        "le lien EST suivi une fois -- par le systeme de fichiers, a la lecture"
    assert exp.remonter() is True
    assert exp.dossier == atelier, "`←` revient d'ou l'on vient"
    assert sorted(e.chemin.name for e in exp.entrees) == [
        "pont", "pont_du_pont", "voisin"]

    # Un lien qui pointe sur un lien : deux maillons, aucun reecrit.
    chaine = explorateur_sur(atelier / "pont_du_pont")
    assert chaine.dossier == atelier / "pont_du_pont"
    assert [e.chemin.name for e in chaine.entrees] == ["aa_dedans", "zz_dedans"]

    # Meme regle par la SAISIE, ou la resolution avait lieu a chaque frappe.
    saisi = explorateur_sur(atelier)
    saisi.basculer_la_saisie()
    saisi.saisie, saisi.caret = "", 0
    for caractere in str(atelier / "pont"):
        saisi.frapper(caractere)
    assert saisi.dossier == atelier / "pont", saisi.dossier
    assert saisi.cible_de_validation() == atelier / "pont"

    # Frontiere negative, celle dont le grep de la couche 3 rendait zero.
    # Mesuree sur l'AST et pas sur le texte : le module PARLE de `resolve()`
    # dans deux docstrings, pour dire pourquoi il ne l'appelle pas. Un grep de
    # chaine y trouverait la prose et rendrait le test faux dans les deux sens.
    arbre = ast.parse(Path(explorateur.__file__).read_text(encoding="utf-8"))
    appels = [f"{n.func.attr} (ligne {n.lineno})" for n in ast.walk(arbre)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr in ("resolve", "resoudre")]
    assert appels == [], appels


# ---------------------------------------------------------------------------
# La liste des VOLUMES (bloquant rapporte par Egan le 2026-09-07)
#
# **Ce que ces bancs remplacent, et pourquoi il faut le lire.** Il y avait ici
# `test_remonter_a_la_racine_ne_leve_pas_et_rend_faux`, qui verrouillait
# `remonter() is False` a la racine ET `nom_court_du_parent() == "Volumes"` --
# c'est-a-dire, dans le meme corps de test, une etiquette qui nomme une cible
# et une touche qui n'y mene pas. Le defaut etait donc MESURE et tenu vert
# pendant dix jours. Un banc peut verrouiller un bug : celui-la l'a fait, et
# c'est Egan qui l'a trouve, sous Windows, ou un `D:` de rushes devenait
# inatteignable autrement qu'en tapant son chemin.
#
# La regle des fabriques s'applique ici aux VOLUMES : `machine_a_volumes`
# produit toujours au moins trois racines DISTINGUABLES, et les tests placent
# leur cible en tete, au milieu ET en queue -- une cible au milieu demasque un
# `find` fautif, elle ne demasque pas un balayage tronque.
# ---------------------------------------------------------------------------

#: Trois racines Windows distinguables. Elles ne sont pas dans l'ordre des
#: lettres : c'est ce qui rend visible un tri parasite que l'ordre du systeme
#: ne doit PAS subir.
VOLUMES_WINDOWS = (Path("D:\\"), Path("C:\\"), Path("Z:\\"))


def machine_a_volumes(volumes=VOLUMES_WINDOWS, dedans=None):
    """Une machine de synthese : ses volumes, et ce que chacun contient.

    ``dedans`` associe une racine a la liste de ce qu'elle porte ; une racine
    absente de la table est **illisible** -- c'est un volume debranche ou un
    lecteur vide, et c'est le cas qui faisait disparaitre la ligne.

    Rend le couple `(lister_volumes, lister)` a passer au constructeur : les
    deux injections du module, et les seules dont ces bancs ont besoin.
    """
    dedans = dedans or {}

    def lister_volumes():
        return list(volumes)

    def lister(dossier):
        return dedans.get(Path(dossier))

    return lister_volumes, lister


def explorateur_aux_volumes(volumes=VOLUMES_WINDOWS, dedans=None, **kwargs):
    """Un explorateur DEJA remonte a la liste des volumes."""
    lister_volumes, lister = machine_a_volumes(volumes, dedans)
    exp = explorateur_sur(Path("/"), lister_volumes=lister_volumes,
                          lister=lister, **kwargs)
    assert exp.remonter() is True, "le montage du banc lui-meme a echoue"
    return exp


def test_remonter_depuis_une_racine_MENE_a_la_liste_des_volumes(tmp_path):
    """Le bloquant d'Egan, verbatim : « impossible d'atteindre les volumes par
    l'explorateur de fichiers. Rien ne se passe si j'essaie de remonter aux
    volumes. »

    L'etiquette du haut annoncait « Volumes » depuis la 11.2b et `remonter()`
    rendait faux : le parent d'une racine EST cette racine, donc la garde
    anti-boucle avalait le seul geste par lequel on change de volume.
    """
    exp = explorateur_sur(Path(tmp_path.anchor),
                          lister_volumes=lambda: list(VOLUMES_WINDOWS))
    assert exp.nom_court_du_parent() == "Volumes"
    assert exp.aux_volumes is False

    assert exp.remonter() is True, "l'etiquette promet une cible que `←` doit atteindre"
    assert exp.aux_volumes is True
    assert [e.chemin for e in exp.entrees] == list(VOLUMES_WINDOWS)


def test_l_ordre_des_volumes_est_celui_du_SYSTEME_et_n_est_pas_retrie():
    """Les racines n'ont pas de `name` : les trier dessus les rangerait toutes
    sur la meme cle vide. L'ordre rendu par le systeme -- les lettres
    croissantes sous Windows -- est le seul que l'operateur reconnaisse.

    La fabrique donne exprès `D:`, `C:`, `Z:` dans le desordre : un tri
    parasite se verrait, un tri correct aussi.
    """
    exp = explorateur_aux_volumes()
    assert [e.chemin for e in exp.entrees] == [Path("D:\\"), Path("C:\\"),
                                               Path("Z:\\")]


def test_une_racine_s_affiche_ENTIERE_et_jamais_par_son_name_VIDE():
    """`Path("C:\\").name` vaut la chaine VIDE, et `Path("/").name` aussi. La
    regle generale de `Entree.nom` -- « le nom, plus une barre » -- rendait donc
    `/` pour chacune : toutes les lignes de la liste portaient le meme nom, qui
    n'etait celui d'aucune.

    Et la barre ne se DOUBLE pas : une racine EST son separateur.
    """
    exp = explorateur_aux_volumes()
    assert [e.nom for e in exp.entrees] == ["D:\\", "C:\\", "Z:\\"]

    # La regle generale n'a pas bouge pour un dossier ordinaire.
    assert explorateur.Entree(Path("/a/rushes"), True).nom == "rushes/"
    assert explorateur.Entree(Path("/"), True).nom == "/"


def test_un_volume_qui_ne_se_lit_pas_reste_VISIBLE_dans_la_liste():
    """**Le defaut que la bifurcation de `relire` existe pour empecher.**

    Un lecteur de cartes vide ou un lecteur reseau deconnecte rend `False` a
    `is_dir()`. Passe par les trois filtres de `relire`, il tombait donc dans
    les FICHIERS, et les fichiers sont supprimes quand `montrer_fichiers` est
    faux : le volume qu'on cherche justement a voir pour savoir s'il est
    branche disparaissait de la liste.

    Sa lisibilite se dit par la colonne de droite, `·` et jamais `0` -- la
    regle du module partout ailleurs.
    """
    # `C:` seul est lisible ; `D:` (en TETE) et `Z:` (en QUEUE) ne le sont pas.
    # Les deux bords, parce qu'une cible au milieu ne demasque pas un balayage
    # tronque.
    lisible = {Path("C:\\"): [Path("C:\\rushes")]}
    exp = explorateur_aux_volumes(dedans=lisible)

    assert [e.chemin for e in exp.entrees] == list(VOLUMES_WINDOWS), \
        "un volume debranche a disparu de la liste des volumes"
    droites = {e.chemin: e.droite for e in exp.entrees}
    assert droites[Path("D:\\")].startswith(jetons.GLYPHES["neutre"]), droites
    assert droites[Path("Z:\\")].startswith(jetons.GLYPHES["neutre"]), droites
    assert "0 sous-dossier" not in droites[Path("D:\\")]


def test_entrer_sur_un_volume_SORT_du_mode_depuis_LES_TROIS_positions():
    """`→` sur un volume en fait le dossier courant. Mesure en TETE, au MILIEU
    et en QUEUE : un balayage tronque ne se demasque pas autrement.
    """
    for rang, attendu in enumerate(VOLUMES_WINDOWS):
        exp = explorateur_aux_volumes(dedans={v: [] for v in VOLUMES_WINDOWS})
        exp.deplacer(rang)
        assert exp.entree_courante.chemin == attendu, (rang, exp.entrees)

        assert exp.entrer() is True
        assert exp.aux_volumes is False, "le mode ne s'est pas referme"
        assert exp.dossier == attendu

    # **Le retour se mesure sur la racine NATIVE, et pas sur `D:\\`**, parce
    # qu'une fixture de synthese fabriquerait ici une panne que le terrain n'a
    # pas : sous POSIX, `Path("D:\\")` est un chemin RELATIF d'un seul segment
    # dont le parent vaut `.`, alors que sous Windows le parent d'une racine
    # est elle-meme. C'est cette egalite -- et elle seule -- que `remonter`
    # interroge pour savoir qu'on est sur une racine. La mesurer sur des
    # lettres de lecteur depuis Linux mesurerait `pathlib`, pas le produit.
    natif = explorateur_sur(Path(Path.cwd().anchor),
                            lister_volumes=lambda: list(VOLUMES_WINDOWS))
    assert natif.remonter() is True
    assert natif.aux_volumes is True


def test_au_dessus_des_VOLUMES_il_n_y_a_rien_et_l_ETIQUETTE_le_dit():
    """La ligne redevient inactive -- cette fois pour de bon.

    Et l'etiquette ne nomme AUCUNE cible : garder le `←` seul afficherait une
    touche annoncee qui n'agit pas, c'est-a-dire le defaut meme que ce lot
    ferme un cran plus bas. La ligne reste, VIDE : la grille est a hauteur
    fixe.
    """
    exp = explorateur_aux_volumes()
    assert exp.remonter() is False
    assert exp.nom_court_du_parent() == ""

    lignes = exp.lignes(76, "Titre", "Dossier")
    assert len(lignes) == 17, "la grille a hauteur fixe a bouge"
    assert lignes[3] == "", lignes[3]
    assert explorateur.symbole(explorateur.PARENT) not in lignes[3]


def test_la_liste_des_volumes_n_a_pas_d_ADRESSE_et_ne_montre_pas_la_racine_d_ou_l_on_vient():
    """Afficher `str(self.dossier)` en barre d'adresse y montrerait la racine
    d'ou l'on vient comme si c'etait ce que la liste porte : un chemin faux
    presente comme une position.
    """
    exp = explorateur_aux_volumes()
    adresse = exp.ligne_d_adresse(76, "Dossier", False)
    assert "Volumes" in adresse
    assert "/" not in adresse.split("Dossier")[-1], adresse


def test_l_etat_et_la_zone_VIDE_parlent_de_VOLUMES_et_non_de_sous_dossiers():
    """« 3 sous-dossiers » pour trois volumes serait une mesure juste sous un
    nom faux. Et les deux moities de `None` contre `[]` valent ici comme
    partout : `[]` dit « aucun volume », `None` dit « pas pu regarder ».
    """
    assert "3 volumes" in explorateur_aux_volumes().etat(76)

    vide = explorateur_aux_volumes(volumes=())
    assert "aucun volume" in " ".join(vide.lignes_de_liste(76, False))
    assert "0 volume" in vide.etat(76)

    lister_volumes, lister = machine_a_volumes()
    muet = explorateur_sur(Path("/"), lister=lister,
                           lister_volumes=lambda: None)
    muet.remonter()
    assert muet.dossier_lisible is False
    assert muet.etat(76) == f"{jetons.GLYPHES['neutre']} volumes"
    assert "volumes illisibles" in " ".join(muet.lignes_de_liste(76, False))


def test_la_liste_des_volumes_se_replie_en_ASCII_comme_le_reste():
    """La regle du depot : « une garde de repli, de mode ou de variante fait
    VARIER le drapeau dont elle depend ». Les deux ecrans neufs de ce lot --
    la zone vide et la ligne d'etat -- sont exactement les deux lignes ou un
    repli s'oublie.
    """
    for exp in (explorateur_aux_volumes(), explorateur_aux_volumes(volumes=())):
        for ascii_seul in (False, True):
            lignes = exp.lignes(76, "Titre", "Dossier", ascii_seul=ascii_seul)
            etat = exp.etat(76, ascii_seul)
            assert len(lignes) == 17
            assert max(len(l) for l in lignes) <= 76, lignes
            if ascii_seul:
                assert all(l.isascii() for l in lignes), lignes
                assert etat.isascii(), etat


def test_la_SAISIE_sort_de_la_liste_des_volumes(tmp_path):
    """Sans quoi `relire` rejouerait les volumes et la liste ne suivrait pas ce
    qu'on tape -- la barre d'adresse resterait donc le seul chemin vers un
    volume, alors que c'est elle que l'explorateur existe pour remplacer.
    """
    cible = tmp_path / "rushes"
    (cible / "aa_lot").mkdir(parents=True)
    (cible / "zz_lot").mkdir()

    exp = explorateur_sur(Path(tmp_path.anchor),
                          lister_volumes=lambda: list(VOLUMES_WINDOWS))
    exp.remonter()
    assert exp.aux_volumes is True

    exp.basculer_la_saisie()
    exp.saisie, exp.caret = "", 0
    for caractere in str(cible):
        exp.frapper(caractere)

    assert exp.aux_volumes is False, "la liste montrait encore les volumes"
    assert exp.dossier == cible
    assert [e.chemin.name for e in exp.entrees] == ["aa_lot", "zz_lot"]


def test_reprendre_la_memoire_RAMENE_du_mode_volumes_sur_le_dossier_retenu(tmp_path):
    """La memoire pointe peut-etre le dossier courant -- mais on est UN CRAN
    AU-DESSUS de lui. Sans cette moitie, revenir sur l'ecran laissait la liste
    des volumes affichee pour un souvenir qui designe un dossier.
    """
    retenu = tmp_path / "retenu"
    (retenu / "aa_dedans").mkdir(parents=True)
    (retenu / "zz_dedans").mkdir()

    exp = explorateur_sur(retenu, lister_volumes=lambda: list(VOLUMES_WINDOWS))
    assert exp.dossier == retenu
    while exp.remonter() and not exp.aux_volumes:
        pass
    assert exp.aux_volumes is True

    memoire = explorateur.MemoireDeSession(dernier_valide=retenu)
    assert exp.reprendre_la_memoire(memoire) is True
    assert exp.aux_volumes is False
    assert exp.dossier == retenu
    assert [e.chemin.name for e in exp.entrees] == ["aa_dedans", "zz_dedans"]


def test_les_DEUX_branches_de_volumes_du_systeme_se_mesurent_de_PARTOUT():
    """`windows` est injectable pour la meme raison que dans
    `projets.chemin_du_fichier_de_recents` : une branche qui ne se teste que
    sur la machine ou elle s'execute n'est testee qu'a moitie.
    """
    # POSIX : `/` d'abord et TOUJOURS -- le seul volume dont l'existence ne se
    # demande pas.
    posix = explorateur.volumes_du_systeme(windows=False)
    assert posix[0] == Path("/"), posix
    assert len(posix) == len(set(posix)), f"un volume compte deux fois : {posix}"

    # Le masque de `GetLogicalDrives`, mesure SANS `windll` : le bit 0 est `A`,
    # l'ordre est celui des lettres, et la borne tient a 26.
    assert explorateur.lettres_du_masque(0b1101) == [Path("A:\\"),
                                                     Path("C:\\"),
                                                     Path("D:\\")]
    assert explorateur.lettres_du_masque(1 << 25) == [Path("Z:\\")]
    assert explorateur.lettres_du_masque(1 << 26) == []
    assert explorateur.lettres_du_masque(0) == []

    # Frontiere NEGATIVE : la branche Windows ne sonde JAMAIS lettre par
    # lettre. Vingt-six `exists()` feraient tourner un lecteur de cartes vide,
    # reveilleraient chaque lecteur reseau deconnecte, et la console Windows y
    # ajouterait une boite modale par lettre absente. Mesuree sur l'AST : le
    # module PARLE de `exists()` dans sa prose, un grep de chaine rendrait le
    # test faux dans les deux sens.
    source = Path(explorateur.__file__).read_text(encoding="utf-8")
    corps = [n for n in ast.walk(ast.parse(source))
             if isinstance(n, ast.FunctionDef)
             and n.name in ("_volumes_windows", "lettres_du_masque")]
    assert len(corps) == 2, [n.name for n in corps]
    sondes = [n.func.attr for n in ast.walk(ast.Module(body=corps, type_ignores=[]))
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr in ("exists", "is_dir", "iterdir", "stat")]
    assert sondes == [], sondes


# ---------------------------------------------------------------------------
# AC 6 -- dossiers caches, depart, memoire
# ---------------------------------------------------------------------------

def test_un_dossier_DISPARU_rend_le_POINT_MEDIAN_et_jamais_zero(tmp_path):
    """Finding `E9`. Un dossier retire entre le listage et l'entree affichait
    `0 sous-dossier` en ligne d'etat et `aucun sous-dossier` dans la zone --
    deux mesures, pour un dossier que rien n'a pu lire.

    Le module ecrit pourtant noir sur blanc, pour la colonne de droite, que
    « rendre `0` pour un dossier illisible serait un chiffre faux presente
    comme une mesure ». La zone de liste et la ligne d'etat ne tenaient pas la
    meme regle : elles confondaient « vide » et « illisible ».

    Les deux volets sont mesures ensemble -- sans le dossier VRAIMENT vide, un
    correctif qui dirait « illisible » partout serait vert.
    """
    base = arborescence(tmp_path, ["aa_vide", "zz_cible"],
                        {"aa_vide": 0, "zz_cible": 3})
    exp = explorateur_sur(base)
    neutre = jetons.GLYPHES["neutre"]

    def zone():
        return [l for l in exp.lignes_de_liste(76, False) if l.strip()]

    # Volet « vide » : un vrai dossier vide dit `0`, et le dit dans la zone.
    assert exp.sauter("a") and exp.entrer() is True
    assert exp.etat() == "0 sous-dossier · aucun projet", exp.etat()
    assert "aucun sous-dossier" in zone()[0], zone()

    # Volet « illisible » : la cible disparait entre le listage et l'entree.
    assert exp.remonter() is True
    assert exp.sauter("z")
    assert exp.entree_courante.chemin.name == "zz_cible", "la cible n'est PAS en tete"
    shutil.rmtree(base / "zz_cible")
    assert exp.entrer() is True, "l'entree etait entrable au moment du listage"
    assert exp.dossier == base / "zz_cible"
    assert exp.dossier_lisible is False
    assert exp.etat() == f"{neutre} sous-dossiers", exp.etat()
    assert "0 sous-dossier" not in exp.etat()
    assert "aucun sous-dossier" not in "\n".join(zone()), zone()
    assert jetons.GLYPHES["absent"] in zone()[0], zone()
    assert "illisible" in zone()[0], zone()


def test_les_caches_sont_masques_et_leur_nombre_est_DIT(tmp_path):
    """AC 6.1 et 6.2. « Rien n'est invisible en silence » est la clause qui rend
    la decision tenable, et c'est elle qu'on mesure."""
    base = tmp_path / "arbo"
    base.mkdir()
    for nom in (".git", "$RECYCLE.BIN", "System Volume Information",
                "visible_a", "visible_b"):
        (base / nom).mkdir()
    exp = explorateur_sur(base)

    assert [e.chemin.name for e in exp.entrees] == ["visible_a", "visible_b"]
    assert exp.caches_masques == 3
    assert "3 dossiers caches" in exp.etat()

    exp.basculer_les_caches()
    assert len(exp.entrees) == 5
    assert exp.caches_masques == 0
    assert "caches" not in exp.etat(), "rien a signaler quand tout est montre"


def test_les_FICHIERS_caches_ne_se_comptent_pas_en_DOSSIERS_caches(tmp_path):
    """Findings `F9` et `E14`. La ligne d'etat annoncait « 2 dossiers caches »
    pour `.DS_Store` et `.gitignore`, et `Ctrl+H` n'en revelait aucun : les
    fichiers etaient de toute facon filtres. L'operateur avait la preuve qu'on
    lui cachait quelque chose et aucun moyen de le voir -- exactement le
    retournement de la clause qui rend `EPIC11-ARB-53` tenable, « rien n'est
    invisible en silence ».

    Le compte est desormais pris APRES le filtre `montrer_fichiers`, et le mot
    suit ce qui est reellement masque.
    """
    base = tmp_path / "arbo"
    base.mkdir()
    (base / ".git").mkdir()
    (base / "visible_a").mkdir()
    (base / "visible_b").mkdir()
    (base / ".DS_Store").write_bytes(b"x")
    (base / ".gitignore").write_bytes(b"y" * 10)

    # Variante DOSSIERS : les deux fichiers caches ne sont ni comptes ni
    # montrables, donc ils ne s'annoncent pas.
    exp = explorateur_sur(base)
    assert exp.caches_masques == 1, exp.caches_masques
    assert "1 dossier cache" in exp.etat(), exp.etat()
    exp.basculer_les_caches()
    assert [e.chemin.name for e in exp.entrees] == [".git", "visible_a",
                                                    "visible_b"]
    assert "cach" not in exp.etat(), exp.etat()

    # Variante FICHIERS : les trois se comptent, et `Ctrl+H` les REVELE tous.
    avec = explorateur.Explorateur(base, montrer_fichiers=True)
    assert avec.caches_masques == 3, avec.caches_masques
    assert "3 elements caches" in avec.etat(), avec.etat()
    avec.basculer_les_caches()
    assert sorted(e.chemin.name for e in avec.entrees) == [
        ".DS_Store", ".git", ".gitignore", "visible_a", "visible_b"]
    assert "cach" not in avec.etat(), avec.etat()


def test_aucun_cache_aucune_phrase(tmp_path):
    """Volet symetrique : la phrase ne s'affiche pas pour zero."""
    exp = explorateur_sur(arborescence(tmp_path, ["a", "b"]))
    assert "cach" not in exp.etat(), exp.etat()


def test_un_dossier_de_depart_ILLISIBLE_ouvre_sur_le_repli_et_le_DIT(tmp_path):
    """AC 6.7. Un explorateur qui leverait au montage rendrait l'ecran
    inatteignable -- le pire moment pour refuser de s'ouvrir."""
    repli = tmp_path / "personnel"
    repli.mkdir()
    exp = explorateur.Explorateur(tmp_path / "volume_debranche",
                                  dossier_de_repli=repli)
    assert exp.dossier == repli
    assert "illisible" in exp.etat()


def test_le_dernier_dossier_valide_sert_de_DEPART_au_suivant(tmp_path):
    """AC 6.5, `EPIC11-ARB-54`. Sur un parcours Scan puis Pdf, on ne retraverse
    pas trois fois la meme arborescence."""
    base = arborescence(tmp_path, ["cible", "autre"])
    memoire = explorateur.MemoireDeSession()

    premier = explorateur_sur(base, memoire=memoire)
    premier.deplacer(1)                       # « cible » n'est PAS en tete
    assert premier.entree_courante.chemin.name == "cible"
    premier.valider()

    second = explorateur.Explorateur(tmp_path, memoire=memoire)
    assert second.dossier == base / "cible"


def test_valider_une_adresse_INEXISTANTE_ne_MEMORISE_rien(tmp_path):
    """Finding `E12`. Une faute de frappe faisait ouvrir l'atelier suivant sur
    le dossier personnel avec « dossier de depart illisible » -- un **faux
    diagnostic de volume debranche**. Et, avant la correction de `F4`/`E8`, ce
    message ne s'effacait plus de la session.

    Ce qui n'est PAS reproche : la bifurcation « creer ici » sur un chemin
    absent est le comportement voulu, et `valider()` doit continuer de rendre
    le chemin saisi. Ce qui est corrige, c'est l'ecriture dans la memoire de
    session : elle ne retient que ce qui existe.
    """
    base = arborescence(tmp_path, ["aa_autre", "zz_cible"],
                        {"aa_autre": 2, "zz_cible": 9})
    memoire = explorateur.MemoireDeSession()

    exp = explorateur_sur(base, memoire=memoire)
    assert exp.sauter("z"), "la cible n'est PAS en premiere position"
    assert exp.valider() == base / "zz_cible"
    assert memoire.dernier_valide == base / "zz_cible", "ce qui existe est retenu"

    exp.basculer_la_saisie()
    exp.saisie, exp.caret = "", 0
    absent = base / "nexiste" / "pas_du_tout"
    for caractere in str(absent):
        exp.frapper(caractere)
    assert exp.etat() == explorateur.ADRESSE_INEXISTANTE

    assert exp.valider() == absent, "la bifurcation « creer ici » reste"
    assert memoire.dernier_valide == base / "zz_cible", "la memoire n'a pas bouge"

    suivant = explorateur.Explorateur(tmp_path, memoire=memoire)
    assert suivant.dossier == base / "zz_cible"
    assert "illisible" not in suivant.etat(), suivant.etat()


def test_la_memoire_de_session_n_ECRIT_rien_sur_le_disque(tmp_path):
    """AC 6.6, frontiere. `EPIC11-ARB-16` limite la persistance a la liste des
    recents ; ecrire ce dossier dans un fichier l'elargirait sans decision."""
    base = arborescence(tmp_path, ["a", "b"])
    avant = sorted(p.name for p in tmp_path.rglob("*"))
    exp = explorateur_sur(base)
    exp.deplacer(1)
    exp.valider()
    assert sorted(p.name for p in tmp_path.rglob("*")) == avant


# ---------------------------------------------------------------------------
# AC 1.3 et AC 5 -- la variante fichiers, et la saisie
# ---------------------------------------------------------------------------

def test_la_variante_FICHIERS_se_monte_hors_de_tout_ecran(tmp_path):
    """AC 1.3. Les trois autres sites n'existent pas encore ; ce qui se mesure
    aujourd'hui, c'est que le composant SAIT les servir."""
    base = tmp_path / "scans_du_prestataire"
    base.mkdir()
    (base / "precedents").mkdir()
    for nom in ("planche_01.tiff", "planche_02.tiff", "notes.txt"):
        (base / nom).write_bytes(b"x" * 2048)

    exp = explorateur.Explorateur(
        base, montrer_fichiers=True,
        accepte=lambda c: c.suffix in (".tiff", ".pdf"))
    par_nom = {e.chemin.name: e for e in exp.entrees}
    assert set(par_nom) == {"precedents", "planche_01.tiff",
                            "planche_02.tiff", "notes.txt"}
    assert par_nom["planche_01.tiff"].validable is True
    assert par_nom["notes.txt"].validable is False, "visible, mais pas validable"
    assert "2,0 ko" in par_nom["planche_02.tiff"].droite


def test_un_fichier_NON_ACCEPTE_ne_se_valide_pas_et_l_etiquette_le_dit(tmp_path):
    """Volet symetrique : la ligne du bas previent AVANT la frappe."""
    base = tmp_path / "src"
    base.mkdir()
    (base / "bon.tiff").write_bytes(b"x")
    (base / "mauvais.txt").write_bytes(b"x")
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  accepte=lambda c: c.suffix == ".tiff")
    exp.sauter("m")
    assert exp.entree_courante.chemin.name == "mauvais.txt"
    assert exp.cible_de_validation() is None
    assert explorateur.RIEN_A_VALIDER in exp.ligne_de_validation()


def test_la_saisie_suit_la_frappe_et_un_chemin_inexistant_n_est_PAS_un_refus(
        tmp_path):
    """AC 5.3 et 5.4. La formulation de la ligne d'etat est celle d'Egan,
    verbatim : « aucun dossier n'existe a cette adresse »."""
    base = arborescence(tmp_path, ["a", "b"])
    exp = explorateur_sur(base)
    exp.basculer_la_saisie()
    exp.saisie, exp.caret = "", 0
    for caractere in str(base / "a"):
        exp.frapper(caractere)
    assert exp.dossier == base / "a"

    exp.frapper("z")
    assert exp.entrees == []
    assert exp.etat() == explorateur.ADRESSE_INEXISTANTE
    rendu = "\n".join(exp.lignes(80, titre="T"))
    assert jetons.GLYPHES["absent"] not in rendu, rendu


def test_sortir_de_la_SAISIE_sur_une_adresse_inexistante_REND_la_liste(tmp_path):
    """Finding `E7`. `Tab`, taper un chemin qui n'existe pas, `Tab` pour revenir
    a la liste : l'ecran devenait une **impasse**. La liste restait vide, le
    message d'erreur a demeure, `↑↓`, `→` et toutes les lettres inertes ; seul
    `←` (qui change de dossier) ou `Ctrl+H` en sortait -- et `Ctrl+H` repeuplait
    la liste en laissant le message qui la contredit.
    """
    base = arborescence(tmp_path, ["aa_reste", "zz_reste"],
                        {"aa_reste": 1, "zz_reste": 8})
    exp = explorateur_sur(base)
    exp.basculer_la_saisie()
    exp.saisie, exp.caret = "", 0
    for caractere in str(base / "nulle_part"):
        exp.frapper(caractere)
    assert exp.entrees == []
    assert exp.etat() == explorateur.ADRESSE_INEXISTANTE

    exp.basculer_la_saisie()               # `Tab` : retour a la liste
    assert exp.dans_la_saisie is False
    assert [e.chemin.name for e in exp.entrees] == ["aa_reste", "zz_reste"], \
        "la liste montre a nouveau le dossier courant, qui, lui, existe"
    assert exp.etat() == "2 sous-dossiers · aucun projet", exp.etat()
    assert exp.deplacer(1) is True
    assert exp.entrer() is True
    assert exp.dossier == base / "zz_reste"


def test_le_collage_insere_au_CARET_et_nettoie_les_guillemets(tmp_path):
    """AC 5.7. Un chemin copie depuis l'explorateur de Windows arrive entoure de
    guillemets ; les garder ferait echouer la resolution en silence."""
    base = arborescence(tmp_path, ["a"])
    exp = explorateur_sur(base)
    exp.basculer_la_saisie()
    exp.saisie, exp.caret = "", 0
    assert exp.coller(f'  "{base}"  ')
    assert exp.dossier == base


def test_la_barre_d_adresse_a_UN_SEUL_comportement(tmp_path):
    """AC 5.1, sur la reserve d'Egan : « il va y avoir une saute c'est moyen ».

    Le meme chemin, dans les deux etats, doit rendre la meme forme abregee --
    c'est ce qui supprime la saute au moment ou l'on touche le clavier.
    """
    profond = tmp_path.joinpath(*[f"un_nom_bien_long_{n}" for n in range(6)])
    profond.mkdir(parents=True)
    exp = explorateur_sur(profond)

    hors = exp.ligne_d_adresse(76, "Dossier", False)
    exp.basculer_la_saisie()
    dedans = exp.ligne_d_adresse(76, "Dossier", False)

    # Le chemin abrege est le MEME dans les deux etats, au caret pres. Ce qui
    # change est le marqueur de focus, jamais la forme du texte : c'est
    # exactement ce qui supprime la saute au moment ou l'on touche le clavier.
    def chemin_seul(ligne):
        """Le chemin affiche, sans le libelle, sans le marqueur, sans le caret.

        Le caret RECOUVRE un caractere : on le remplace par ce qu'il masque --
        ici toujours la fin du chemin, donc un espace de garde -- au lieu de le
        retirer, sinon la comparaison mesurerait un decalage qui n'existe pas.
        """
        return (ligne.split(maxsplit=1)[1].lstrip("> ")
                .replace(jetons.GLYPHES["caret"], "").rstrip())

    assert chemin_seul(dedans) == chemin_seul(hors), (dedans, hors)
    assert explorateur.ELLIPSE in hors, "le DEBUT est ce qu'on perd"
    assert profond.name in hors, "la FIN survit"


def _corps_de_l_adresse(ligne):
    """Le texte du champ d'adresse, sans le libelle ni le marqueur de focus.

    **On ne cherche jamais le caret par `find`** : en `--ascii` son glyphe est
    `_`, qui est aussi le separateur de mots des noms de dossier du metier. Un
    test qui le localiserait ainsi mesurerait un souligne du chemin et serait
    vert pour la mauvaise raison. On mesure donc les BORDS du corps, ou le
    caret est le seul candidat possible.
    """
    return ligne.split(maxsplit=1)[1].lstrip("> ")


def _chemin_long(tmp_path):
    """Un chemin qui deborde LARGEMENT la fenetre de la barre d'adresse.

    Six segments de 28 caracteres : la fenetre en montre 50 colonnes, donc
    quatre cinquiemes du chemin sont hors champ a tout instant. C'est le cas
    d'Egan : un chemin colle depuis l'Explorateur dont il veut corriger la
    lettre de volume, c'est-a-dire son tout DEBUT.
    """
    profond = tmp_path.joinpath(*[f"un_dossier_au_nom_assez_long_{n}"
                                  for n in range(6)])
    profond.mkdir(parents=True)
    return profond


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_le_caret_FRANCHIT_le_bord_GAUCHE_et_la_fenetre_le_suit(tmp_path,
                                                                ascii_seul):
    """Finding `E13`. Editer le DEBUT d'un chemin long etait AVEUGLE.

    La fenetre etait calee sur la fin et le rang du caret y etait simplement
    borne (`min(max(caret - perdu, 0), ...)`) : le caret recouvrait le `…` de
    tete et n'en bougeait plus. **Les positions 0 et 5 rendaient la meme
    ligne**, et le texte reellement edite n'etait jamais affiche. C'est le cas
    nominal d'Egan -- corriger la lettre de volume d'un chemin colle.

    Mesure prise dans les deux modes : `…` fait une colonne et `...` en fait
    trois, donc le repli change la place disponible des deux cotes.
    """
    profond = _chemin_long(tmp_path)
    exp = explorateur_sur(profond)
    exp.basculer_la_saisie()
    texte = exp.saisie
    assert len(texte) > 150, texte

    glyphe = jetons.glyphes(ascii_seul)["caret"]
    points = explorateur.symbole(explorateur.ELLIPSE, ascii_seul)
    corps = {}
    for caret in (0, 5, 20, 60, len(texte)):
        exp.caret = caret
        ligne = exp.ligne_d_adresse(76, "Dossier", ascii_seul)
        corps[caret] = _corps_de_l_adresse(ligne)
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne
        # **Ce qui SUIT le caret est visible** : c'est la seule chose qui rend
        # l'edition voyante. Le caractere sous le caret est recouvert, donc la
        # mesure commence a `caret + 1`.
        assert texte[caret + 1:caret + 9] in ligne, (caret, ligne)

    # Trois positions distinctes rendaient TOUTES la meme ligne, le caret colle
    # au `…` de tete. C'est le defaut, et il se mesure ici.
    assert len({corps[0], corps[5], corps[20], corps[60]}) == 4, corps

    # Au tout DEBUT, il n'y a rien a perdre a gauche : le caret est en tete,
    # sans `…`, et c'est la FIN qui sort du champ.
    assert corps[0].startswith(glyphe), corps[0]
    assert corps[0].endswith(points), corps[0]
    # Plus loin, le texte deborde des DEUX cotes : `…` de part et d'autre, et
    # le caret juste apres celui de tete.
    for caret in (5, 20, 60):
        assert corps[caret].startswith(points + glyphe), (caret, corps[caret])
        assert corps[caret].endswith(points), (caret, corps[caret])
    # A la FIN, la fenetre reste calee sur la fin : c'est le comportement par
    # defaut d'`EPIC11-ARB-52`, et il n'a pas bouge.
    assert corps[len(texte)].startswith(points), corps[len(texte)]
    assert corps[len(texte)].endswith(glyphe), corps[len(texte)]


def test_ENTRER_dans_la_saisie_ne_DECALE_toujours_rien(tmp_path):
    """Non-regression du defaut deja paye : « ca saute d'une colonne ».

    La fenetre qui suit le caret ne doit pas ressusciter la « saute »
    qu'`EPIC11-ARB-52` a supprimee : a l'entree dans la saisie le caret est
    pose en FIN de texte, donc la fenetre reste calee sur la fin et le rendu
    est le meme qu'hors saisie, **au caret pres**. Le caret RECOUVRE une
    colonne de garde, il ne s'insere pas.

    Mesure prise dans les deux modes et sur les deux etats, colonne par
    colonne : c'est le decalage d'UNE colonne qui avait ete paye.
    """
    profond = _chemin_long(tmp_path)
    exp = explorateur_sur(profond)
    for ascii_seul in (False, True):
        hors = exp.ligne_d_adresse(76, "Dossier", ascii_seul)
        exp.basculer_la_saisie()
        dedans = exp.ligne_d_adresse(76, "Dossier", ascii_seul)
        exp.basculer_la_saisie()

        glyphe = jetons.glyphes(ascii_seul)["caret"]
        # Le corps est le MEME, plus le caret pose sur la colonne de garde :
        # zero colonne de decalage, mesure a l'egalite de chaine et pas a
        # l'oeil. Ce qui change entre les deux etats est le marqueur de focus,
        # jamais la forme du texte.
        assert _corps_de_l_adresse(dedans) == _corps_de_l_adresse(hors) + glyphe, \
            (dedans, hors)


# ---------------------------------------------------------------------------
# AC 8 -- la grille, le repli, et la sobriete
# ---------------------------------------------------------------------------

def _debordements(exp, largeur=80):
    """Les lignes qui DEBORDENT la grille, dans les DEUX modes.

    La mesure est prise en **colonnes** et jamais en caracteres : un ideogramme
    en vaut deux, une marque combinante zero. Et elle est prise dans les deux
    modes parce que le repli en change la largeur des deux cotes -- `…` fait
    une colonne et `...` en fait trois, `⏎` en fait une et `Entree` six.
    """
    trouves = []
    for ascii_seul in (False, True):
        for rang, ligne in enumerate(exp.lignes(largeur, titre="Ouvrir un projet",
                                                ascii_seul=ascii_seul)):
            colonnes = jetons.colonnes(ligne)
            if colonnes > jetons.largeur_utile(largeur):
                trouves.append((ascii_seul, rang, colonnes, ligne))
    return trouves


def test_toutes_les_lignes_tiennent_dans_la_grille(tmp_path):
    """AC 8.1, findings `F8` et `E10`. En COLONNES, sur des noms qui ATTEIGNENT
    la frontiere, et dans les deux modes.

    **La fixture precedente ne pouvait pas voir le defaut** : elle employait
    `f"{n:02d}_un_dossier_au_nom_plutot_long"`, soit 30 caracteres, quand le
    debordement de la ligne de liste commence a 54. L'assertion etait verte sans
    avoir jamais approche la borne qu'elle pretendait tenir, et trois lignes
    debordaient dans son dos -- la ligne de liste, l'etiquette de validation et
    l'etiquette du parent, chacune sur un seuil different.

    Les trois axes qui manquaient sont ici, et chacun deborde seul :

    * un nom **long** ordinaire (56 caracteres, la convention de nommage du
      metier) ;
    * un nom en **double chasse** (20 ideogrammes, 40 colonnes) ;
    * le **repli ASCII**, ou `⏎` -> `Entree` coute cinq colonnes de plus a
      l'etiquette du bas.
    """
    exp = explorateur_sur(arborescence_aux_noms_LONGS(tmp_path))
    # Le curseur passe sur CHAQUE entree : l'etiquette du bas suit le curseur,
    # et c'est elle qui deborde sur le nom le plus long.
    for _ in range(len(exp.entrees)):
        assert not _debordements(exp), _debordements(exp)
        exp.deplacer(1)
    # Et dans la saisie, ou la barre d'adresse porte le chemin complet.
    exp.basculer_la_saisie()
    assert not _debordements(exp), _debordements(exp)


def test_l_etiquette_du_PARENT_tient_la_grille_sur_un_nom_LONG(tmp_path):
    """AC 8.1, finding `E10` cas N : l'etiquette du haut n'avait aucune borne.

    Elle rend `…\\<nom du parent>\\`, et un nom de parent n'a pas de borne cote
    systeme de fichiers. Le seuil mesure etait **78 colonnes en ASCII contre 76
    en UTF-8** -- le repli en change la largeur, donc la mesure se prend des
    deux cotes.
    """
    parent = tmp_path / NOMS_LONGS[1]
    (parent / "dedans").mkdir(parents=True)
    (parent / "dedans" / "aa").mkdir()
    (parent / "dedans" / "zz").mkdir()
    exp = explorateur_sur(parent / "dedans")

    assert not _debordements(exp), _debordements(exp)
    # La barre finale et le `…` de tete SURVIVENT a l'abregement : sans eux
    # l'etiquette se lirait comme un nom de fichier.
    for ascii_seul, points in ((False, explorateur.ELLIPSE), (True, "...")):
        etiquette = exp.nom_court_du_parent(ascii_seul, 40)
        assert etiquette.startswith(points), etiquette
        assert etiquette[-1] in "/\\", etiquette
        assert jetons.colonnes(etiquette) <= 40, etiquette


def test_un_nom_ABREGE_garde_ses_DEUX_bouts_et_reste_distinguable(tmp_path):
    """Findings `F8` / `E10`, le volet produit du garde-fou.

    Le garde-fou de l'ecran (`jetons.ajuster`) coupait **par la fin** : il
    supprimait la colonne de droite, puis, sur un nom seul, la queue qui
    distingue `_camera_A` de `_camera_B`. Deux lignes identiques a l'ecran pour
    deux dossiers differents, c'est le mode de panne que `abreger_chemin`
    existe deja pour empecher sur les chemins.
    """
    base = arborescence(tmp_path, ["01_court", *NOMS_LONGS],
                        {"01_court": 0, NOMS_LONGS[0]: 3, NOMS_LONGS[1]: 27})
    exp = explorateur_sur(base)
    lignes = [l for l in exp.lignes_de_liste(76, False) if "sous-dossier" in l]

    assert len(set(lignes)) == len(lignes), lignes
    for ligne, nom in zip(lignes[1:], NOMS_LONGS):
        assert nom[:12] in ligne, (ligne, nom)      # la TETE (la date)
        assert nom[-12:] in ligne, (ligne, nom)     # la QUEUE (la camera)
    # La colonne de droite -- ce qui distingue une ligne de sa voisine -- est
    # servie ENTIERE : c'est le nom qui paie l'abregement, jamais elle.
    assert "3 sous-dossiers" in lignes[1], lignes[1]
    assert "27 sous-dossiers" in lignes[2], lignes[2]


def test_le_repli_ASCII_ne_laisse_aucun_caractere_hors_ascii(tmp_path):
    """AC 8.2, finding `F7`. La mesure porte sur les deux etats de la saisie
    **et sur des entrees dont la colonne de droite porte un glyphe**.

    L'ancienne fixture etait `["a", "b", "c"]` : ses trois colonnes de droite
    rendaient `0 sous-dossier`, `1 sous-dossier`, `2 sous-dossiers`, deja ASCII
    toutes les trois. Le test faisait donc varier le mauvais axe, et restait
    vert pendant que `● projet`, `· sous-dossiers`, `✕ illisible` et
    `· pas une source` sortaient en UTF-8 sous `--ascii`.

    Le repli d'un texte d'ecran precede sa mesure : c'est pourquoi la largeur
    est verifiee dans la meme boucle.
    """
    exp = arborescence_aux_ETATS_distincts(tmp_path)
    for _ in range(2):
        for ligne in exp.lignes(80, titre="Ouvrir un projet", ascii_seul=True):
            assert ligne.isascii(), ligne
            assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne
        assert exp.etat(76, True).isascii(), exp.etat(76, True)
        exp.basculer_la_saisie()


def test_la_colonne_de_droite_de_CHAQUE_etat_se_replie(tmp_path):
    """Finding `F7`, entree par entree.

    Le test ci-dessus mesure une propriete de l'ecran entier ; celui-ci nomme
    les cinq colonnes qui portent un glyphe, et verifie que chacune rend son
    repli **et pas un autre** : un repli qui donnerait le meme caractere a deux
    etats detruirait le second canal de `DESIGN.md` section 6, celui qui existe
    pour les operateurs qui ne distinguent pas les couleurs.
    """
    exp = arborescence_aux_ETATS_distincts(tmp_path)
    lues = {nom: droite for nom, droite, _ in lignes_lues(exp, 76, True)}

    assert lues["mm_projet/"] == "* projet", lues
    # « fichiers » et non « sous-dossiers » : cette fabrique montre les
    # fichiers, donc la colonne d'un dossier compte ce que le SITE cherche
    # (`EPIC11-ARB-121`, 2026-08-31). Ce que ce test mesure n'a pas bouge --
    # c'est le REPLI du `·`, pas le nom de l'unite.
    assert lues["zz_lent/"] == ". fichiers", lues
    assert lues["kk_interdit/"] == "x illisible", lues
    assert lues["nn_note.txt"] == ". pas une source", lues
    assert lues["qq_disparue.mp4"] == ". taille inconnue", lues
    assert len({lues["mm_projet/"][0], lues["zz_lent/"][0],
                lues["kk_interdit/"][0]}) == 3, lues
    # Et en UTF-8, les memes entrees portent les glyphes de la table pleine.
    pleines = {nom: droite for nom, droite, _ in lignes_lues(exp, 76, False)}
    assert pleines["mm_projet/"] == "\u25cf projet", pleines
    assert pleines["kk_interdit/"] == "\u2715 illisible", pleines


#: Les noms de touche qui n'ont rien a faire en ligne d'etat (`EPIC11-ARB-56`).
NOMS_DE_TOUCHE = ("Tab", "Ctrl", "Echap", "\u23ce", "\u2190", "\u2192", "F1")


def _balayage_des_lignes_d_etat(exp):
    """Toutes les lignes d'etat qu'un balayage de l'ecran produit.

    Partage par la frontiere et par son volet symetrique : les deux doivent
    mesurer la MEME chose, sur le meme chemin de production, sinon le volet ne
    prouve rien de la frontiere.
    """
    # `entrer()` passe EN PREMIER : `basculer_les_caches()` relit le dossier et
    # remet le curseur a zero, ce qui deplacerait la cible du refus. L'ordre
    # d'un balayage n'est pas neutre des qu'un geste relit.
    etats = [exp.etat()]
    exp.entrer()
    etats.append(exp.etat())
    exp.basculer_les_caches()
    etats.append(exp.etat())
    exp.basculer_la_saisie()
    etats.append(exp.etat())
    exp.frapper("z")
    etats.append(exp.etat())
    return etats


@pytest.mark.parametrize("touche", NOMS_DE_TOUCHE)
def test_aucune_ligne_d_etat_ne_porte_un_NOM_DE_TOUCHE(tmp_path, touche):
    """AC 8.3, `EPIC11-ARB-56`, pose par Egan comme une regle generale : « pas
    une remarque d'aide ou, pire, de methode, a chaque fois. Sois sobre. »

    Une touche va a la ligne des raccourcis. La ligne d'etat porte une MESURE.
    """
    base = tmp_path / "arbo"
    base.mkdir()
    for nom in (".cache", "visible_a", "visible_b"):
        (base / nom).mkdir()
    exp = explorateur_sur(base)

    for etat in _balayage_des_lignes_d_etat(exp):
        assert touche not in etat, (touche, etat)


def test_la_frontiere_de_sobriete_MORD(tmp_path):
    """Volet symetrique, finding `F11`. **Il execute du code de production.**

    La version precedente etait une tautologie pure -- `bavarde = "27
    sous-dossiers -- Tab complete"` puis `assert "Tab" in bavarde` -- : elle
    verifiait qu'une chaine ecrite dans le test contient une sous-chaine ecrite
    dans le test, n'importait rien, n'appelait rien, et serait restee verte si
    `explorateur.py` etait vide. Elle faisait compter une couverture qui
    n'existait pas.

    Ici la ligne d'etat bavarde est **produite par `Explorateur.etat()`**, par
    le canal du refus d'entree : `entrer()` sur une entree non entrable pose
    `« <nom> ne se lit pas »`, et `etat()` le rend en priorite absolue. Un
    dossier nomme comme une touche suffit donc a faire sortir un nom de touche
    en ligne d'etat -- et c'est bien le balayage de la frontiere qui l'attrape.
    Si `etat()` cessait de rendre le refus, ou si le balayage cessait de
    passer par `entrer()`, ce test rougirait.
    """
    base, lister = arborescence_avec_un_bloque(tmp_path, "Tab_est_un_dossier")
    exp = explorateur_sur(base, lister=lister)
    exp.deplacer(1)                      # le curseur sur l'entree ILLISIBLE
    assert exp.entree_courante.chemin.name == "Tab_est_un_dossier"

    bavardes = [e for e in _balayage_des_lignes_d_etat(exp) if "Tab" in e]
    assert bavardes, "la mesure ne sort JAMAIS : elle ne mesure rien"
    assert "Tab_est_un_dossier ne se lit pas" in bavardes, bavardes


# ---------------------------------------------------------------------------
# AC 8.1 -- le rendu tient la MEME grille que les maquettes validees
# ---------------------------------------------------------------------------

def _colonnes_de_la_maquette(nom):
    """Les colonnes que la maquette fige, lues sur son fichier.

    On ne compare pas les chaines : les maquettes portent des chemins Windows
    qu'aucune machine de CI ne peut reproduire. Ce qui doit tenir, c'est la
    GRILLE -- ou commence le curseur, ou commence un nom, ou finit la colonne
    de droite. C'est cela qui derive quand on retouche la mise en page.
    """
    lignes = (MAQUETTES / nom).read_text(encoding="utf-8").split("\n")
    # **Seulement la zone centrale.** La ligne d'etat porte elle aussi le mot
    # « sous-dossiers », et la prendre pour une ligne de liste faussait la
    # colonne mesuree -- premiere version de ce test, et le piege qu'elle a
    # paye : une mesure prise sur la mauvaise zone est verte pour la mauvaise
    # raison.
    centre = lignes[3:20]
    interessantes = [l[2:-2] for l in centre
                     if l.startswith("│") and "sous-dossier" in l]
    assert interessantes, nom
    cur = min(l.index("▸") for l in interessantes if "▸" in l)
    nom_col = min(len(l) - len(l.lstrip()) for l in interessantes
                  if "▸" not in l)
    fin = max(len(l.rstrip()) for l in interessantes)
    return cur, nom_col, fin


@pytest.mark.skipif(not MAQUETTES.exists(), reason="maquettes hors du paquet")
def test_le_rendu_tient_la_grille_de_la_maquette_X1(tmp_path):
    """AC 8.1. Une maquette validee par Egan et un rendu qui derive d'une
    colonne : l'ecart est invisible a la relecture et saute aux yeux dans un
    terminal."""
    attendu = _colonnes_de_la_maquette("X1-explorateur-depart.txt")
    base = arborescence(tmp_path, ["archives", "projects", "rushes", "scans"],
                        {"archives": 0, "projects": 6, "rushes": 12,
                         "scans": 3})
    exp = explorateur_sur(base)
    exp.deplacer(1)                        # curseur sur la DEUXIEME entree
    lignes = [l for l in exp.lignes_de_liste(76, False) if "sous-dossier" in l]

    cur = min(l.index("▸") for l in lignes if "▸" in l)
    nom_col = min(len(l) - len(l.lstrip()) for l in lignes if "▸" not in l)
    fin = max(len(l.rstrip()) for l in lignes)
    assert (cur, nom_col, fin) == attendu, (cur, nom_col, fin, attendu)


# ---------------------------------------------------------------------------
# Story 11.2c -- le MODE SELECTION. `EPIC11-ARB-102` a `-106`.
#
# La regle des fabriques vaut ici deux fois plutot qu'une : `basculer_la_coche`
# et `valider` BOUCLENT tous les deux sur `self.entrees`. Une fabrique a deux
# elements dont la cible est en second la place aussi en DERNIER, et les deux
# formes y sont indiscernables -- c'est le mutant `continue` -> `break` qui a
# survecu a 288 tests sur la story 11.4b. Il faut TROIS elements et la cible AU
# MILIEU.
#
# Et le point se verifie sur la liste que le code PARCOURT : `self.entrees` est
# reconstruite ET TRIEE par `relire()`, donc une fixture qui croit placer sa
# cible au milieu peut la placer ailleurs. Chaque test qui en depend le
# **verifie** au lieu de le supposer.
# ---------------------------------------------------------------------------

def _selection_de_trois_fichiers(tmp_path):
    """Trois fichiers de TAILLES distinctes, plus un dossier, plus un refuse.

    Les tailles different pour que la colonne de droite soit distinguable ligne
    a ligne ; le dossier est la parce que `EPIC11-ARB-120` autorise a le cocher
    avec des fichiers ; le refuse mesure qu'une entree non validable ne se coche
    pas.
    """
    base = arborescence(
        tmp_path, ["dd_dossier"], {"dd_dossier": 3},
        {"aa_un.tiff": 11, "mm_deux.tiff": 22, "zz_trois.tiff": 33,
         "nn_refuse.txt": 44})
    return base


def _rangs(exp):
    """Les noms de la liste que le code PARCOURT, dans son ordre reel."""
    return [e.chemin.name for e in exp.entrees]


def test_le_mode_selection_est_FAUX_par_defaut():
    """`EPIC11-ARB-102` : le troisieme reglage ne change rien tant qu'on ne le
    demande pas. Les quatre sites livres n'en veulent pas."""
    exp = explorateur.Explorateur(Path.cwd())
    assert exp.selection_multiple is False
    assert exp.selection == ()


def test_le_compte_de_reglages_annonce_par_le_docstring_est_le_compte_REEL(
):
    """`EPIC11-ARB-102`, la moitie qui compte : le nombre cesse d'etre une
    phrase pour devenir une mesure.

    Le docstring d'`Explorateur` annonce un nombre de reglages ; ce test lit la
    SIGNATURE et compare. Un quatrieme reglage ajoute en silence fait rougir --
    ce que « et pas davantage », ecrit en prose, ne faisait pas.
    """
    import inspect
    doc = inspect.getdoc(explorateur.Explorateur) or ""
    mots = {"deux": 2, "trois": 3, "quatre": 4, "cinq": 5}
    annonces = sorted({n for mot, n in mots.items()
                       if f"{mot} reglages" in doc.lower()})
    assert len(annonces) == 1, (
        "le docstring d'`Explorateur` doit annoncer UN nombre de reglages et un "
        f"seul ; il en annonce {annonces or 'aucun'}. Prendre le premier match "
        "d'un dictionnaire, comme le faisait la premiere version de ce test, "
        "rendait la mesure dependante d'un saut de ligne du docstring")
    reels = len(explorateur.Explorateur.REGLAGES)
    assert annonces[0] == reels, (
        f"le docstring annonce {annonces[0]} reglages, la classe en declare "
        f"{reels} ({explorateur.Explorateur.REGLAGES})")


def test_un_reglage_ajoute_a_la_SIGNATURE_sans_passer_par_la_table_fait_ROUGIR():
    """Finding `R8` de la revue : la frontiere mesurait le mauvais sens.

    L'ancienne version verifiait `REGLAGES` inclus dans la signature. Or un
    reglage s'ajoute **par la signature** : un `trier_a_l_envers: bool = False`
    pose dans `__init__` sans toucher a la table passait la suite TUI entiere --
    mutant injecte, 2245 passed. Le docstring promettait pourtant qu'« un
    quatrieme reglage ne peut plus entrer sans faire rougir un banc ».

    La mesure porte donc sur l'ensemble **EXACT** : signature moins outillage
    **egale** `REGLAGES`. Une assertion d'inclusion laisse passer toute entree
    supplementaire -- c'est le piege que `CLAUDE.md` nomme, et il etait ici.
    """
    import inspect
    signature = set(
        inspect.signature(explorateur.Explorateur.__init__).parameters)
    outillage = set(explorateur.Explorateur.OUTILLAGE)
    inconnus = outillage - signature
    assert inconnus == set(), (
        f"`OUTILLAGE` nomme des parametres qui n'existent plus : {inconnus}")
    assert signature - outillage == set(explorateur.Explorateur.REGLAGES), (
        "tout parametre d'`__init__` est soit un REGLAGE, soit de l'OUTILLAGE "
        "explicitement nomme. Un parametre qui n'est ni l'un ni l'autre est un "
        "reglage entre en silence, exactement ce que cette frontiere existe "
        f"pour empecher.\nsignature : {sorted(signature)}\n"
        f"reglages  : {sorted(explorateur.Explorateur.REGLAGES)}\n"
        f"outillage : {sorted(outillage)}")


def test_cocher_prend_l_entree_sous_le_curseur_placee_AU_MILIEU(tmp_path):
    """`EPIC11-ARB-103`. La cible est au milieu de la liste PARCOURUE, et le
    test le verifie plutot que de l'esperer."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    noms = _rangs(exp)
    assert len(noms) >= 5, noms
    cible = "mm_deux.tiff"
    rang = noms.index(cible)
    assert 0 < rang < len(noms) - 1, (
        f"la cible doit etre au MILIEU de la liste parcourue, elle est au rang "
        f"{rang} sur {len(noms)} : {noms}")
    exp.curseur = rang
    assert exp.basculer_la_coche() is None
    assert [c.name for c in exp.selection] == [cible]
    assert exp.basculer_la_coche() is None
    assert exp.selection == ()


def test_valider_rend_la_liste_dans_l_ordre_D_AFFICHAGE(tmp_path):
    """AC 4.1. Coche dans le DESORDRE, rend dans l'ordre de la liste.

    L'ordre de cochage n'est reproductible pour personne ; celui de la liste
    l'est. Un test qui cocherait dans l'ordre d'affichage serait vert quelle que
    soit l'implementation.
    """
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    noms = _rangs(exp)
    voulus = ["zz_trois.tiff", "aa_un.tiff", "mm_deux.tiff"]
    for nom in voulus:                       # cochage DESORDONNE
        exp.curseur = noms.index(nom)
        exp.basculer_la_coche()
    attendu = [n for n in noms if n in set(voulus)]
    assert [c.name for c in exp.selection] == attendu
    assert attendu != voulus, ("la fabrique doit rendre les deux ordres "
                               "DIFFERENTS, sinon le test ne mesure rien")
    rendu = exp.valider()
    assert isinstance(rendu, list)
    assert [c.name for c in rendu] == attendu


def test_selection_VIDE_valide_l_entree_sous_le_curseur(tmp_path):
    """AC 4.2. Un mode qui refuserait de valider tant que rien n'est coche
    ferait d'un explorateur un formulaire."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    exp.curseur = _rangs(exp).index("mm_deux.tiff")
    rendu = exp.valider()
    assert isinstance(rendu, Path)
    assert rendu.name == "mm_deux.tiff"


def test_le_TYPE_rendu_par_valider_ne_change_pas_en_mode_simple(tmp_path):
    """AC 4.1 bis. Trois sites du produit lisent `valider()` et font `.name`
    dessus : `ecran_projet` 700 et 1021, `atelier_extraction` 623. Une liste a
    un element les casserait sans que rien ne le dise."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True)
    exp.curseur = _rangs(exp).index("mm_deux.tiff")
    rendu = exp.valider()
    assert isinstance(rendu, Path) and not isinstance(rendu, list)


def test_une_entree_non_validable_ne_se_coche_pas_et_le_DIT(tmp_path):
    """AC 2.4. Comme une cadence refusee : un motif, jamais une frappe ignoree."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(
        base, montrer_fichiers=True, selection_multiple=True,
        accepte=lambda c: c.suffix == ".tiff")
    noms = _rangs(exp)
    rang = noms.index("nn_refuse.txt")
    assert 0 < rang < len(noms) - 1, noms
    exp.curseur = rang
    motif = exp.basculer_la_coche()
    assert motif, "un refus se NOMME"
    assert exp.selection == ()


def test_la_selection_survit_a_un_changement_de_dossier(tmp_path):
    """AC 4.3. Cocher ici, descendre, cocher la, remonter : les quatre tiennent."""
    base = _selection_de_trois_fichiers(tmp_path)
    (base / "dd_dossier" / "profond.tiff").write_bytes(b"y" * 55)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    exp.curseur = _rangs(exp).index("mm_deux.tiff")
    exp.basculer_la_coche()
    exp.curseur = _rangs(exp).index("dd_dossier")
    assert exp.entrer()
    exp.curseur = _rangs(exp).index("profond.tiff")
    exp.basculer_la_coche()
    assert {c.name for c in exp.selection} == {"mm_deux.tiff", "profond.tiff"}
    assert exp.remonter()
    assert {c.name for c in exp.selection} == {"mm_deux.tiff", "profond.tiff"}
    coches = {e.chemin.name for e in exp.entrees if exp.est_cochee(e.chemin)}
    assert coches == {"mm_deux.tiff"}, "l'ecran ne coche que ce qu'il montre"


def test_un_chemin_devenu_illisible_sort_de_la_selection(tmp_path):
    """AC 4.4. Un compte qui inclurait un fichier disparu serait un chiffre faux."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    for nom in ("aa_un.tiff", "mm_deux.tiff"):
        exp.curseur = _rangs(exp).index(nom)
        exp.basculer_la_coche()
    (base / "mm_deux.tiff").unlink()
    exp.relire()
    assert [c.name for c in exp.selection] == ["aa_un.tiff"]


# ---------------------------------------------------------------------------
# T3 -- le RENDU du mode selection, et la colonne du dossier (`EPIC11-ARB-121`).
# ---------------------------------------------------------------------------

def test_la_case_prend_QUATRE_colonnes_et_seulement_en_mode_selection(tmp_path):
    """AC 2.1 et 2.2. Le mode simple rend caractere pour caractere ce qu'il
    rendait : c'est la moitie de la story qui ne doit RIEN changer."""
    base = _selection_de_trois_fichiers(tmp_path)
    simple = explorateur.Explorateur(base, montrer_fichiers=True)
    choisi = explorateur.Explorateur(base, montrer_fichiers=True,
                                     selection_multiple=True)
    utile = jetons.largeur_utile()
    lignes_simples = simple.lignes_de_liste(utile, False)
    lignes_cochables = choisi.lignes_de_liste(utile, False)
    assert lignes_simples[0] != lignes_cochables[0]
    assert jetons.GLYPHES["decoche"] in lignes_cochables[0]
    assert jetons.GLYPHES["decoche"] not in lignes_simples[0]

    # **La case coute quatre colonnes AU NOM, pas a la ligne.** La ligne fait la
    # meme largeur dans les deux modes -- le creux l'absorbe --, et une premiere
    # redaction de ce test comparait justement les deux lignes nues : elle
    # mesurait donc zero et aurait ete verte sans aucune case. Ce qui se mesure
    # est la colonne ou le NOM commence.
    def _colonne_du_nom(ligne, nom):
        return jetons.colonnes(ligne[:ligne.index(nom)])

    nom = "dd_dossier/"
    assert (_colonne_du_nom(lignes_cochables[0], nom)
            - _colonne_du_nom(lignes_simples[0], nom)) == 4
    assert jetons.colonnes(lignes_cochables[0]) <= utile


def test_la_case_est_IDENTIQUE_dans_les_deux_rendus(tmp_path):
    """AC 2.3. `[x]` et `[ ]` valent pareil en UTF-8 et en ASCII -- le test
    mesure les deux rendus ET leur egalite, sans quoi une divergence future
    passerait sans que rien ne rougisse."""
    assert jetons.GLYPHES["coche"] == jetons.GLYPHES_ASCII["coche"] == "[x]"
    assert jetons.GLYPHES["decoche"] == jetons.GLYPHES_ASCII["decoche"] == "[ ]"
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    exp.curseur = _rangs(exp).index("mm_deux.tiff")
    exp.basculer_la_coche()
    for ascii_seul in (False, True):
        ligne = [l for l in exp.lignes_de_liste(jetons.largeur_utile(),
                                                ascii_seul)
                 if "mm_deux" in l][0]
        assert jetons.GLYPHES["coche"] in ligne


def test_une_entree_refusee_porte_le_glyphe_ABSENT_dans_sa_case(tmp_path):
    """AC 2.4, rendu. Comme une cadence refusee (`cadences.py:731`)."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(
        base, montrer_fichiers=True, selection_multiple=True,
        accepte=lambda c: c.suffix == ".tiff")
    ligne = [l for l in exp.lignes_de_liste(jetons.largeur_utile(), False)
             if "nn_refuse" in l][0]
    assert jetons.GLYPHES["absent"] in ligne
    assert jetons.GLYPHES["decoche"] not in ligne


def test_le_compte_rejoint_les_mesures_en_LIGNE_D_ETAT(tmp_path):
    """AC 5.1 et 5.2. `EPIC11-ARB-56` : la ligne d'etat est une MESURE."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    assert "selectionn" not in exp.etat(), "une mesure a zero ne se dit pas (AC 5.4)"
    for nom in ("aa_un.tiff", "mm_deux.tiff"):
        exp.curseur = _rangs(exp).index(nom)
        exp.basculer_la_coche()
    etat = exp.etat()
    assert "2 selectionnes" in _sans_accents_du_test(etat), etat
    assert "fichier" in etat, "les mesures existantes restent"


def _sans_accents_du_test(texte):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texte)
                   if not unicodedata.combining(c))


def test_la_ligne_du_bas_dit_la_SELECTION_et_son_poids(tmp_path):
    """AC 5.3. Egan, sur les deux redactions montrees cote a cote : « Je prefere
    le poids total ». Des qu'une coche existe, `⏎` valide la selection, donc la
    ligne l'annonce -- sinon elle ment sur ce que la touche fait."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    exp.curseur = _rangs(exp).index("mm_deux.tiff")
    avant = exp.ligne_de_validation()
    assert "mm_deux.tiff" in avant, "selection vide : le nom, comme avant"
    exp.basculer_la_coche()
    exp.curseur = _rangs(exp).index("zz_trois.tiff")
    exp.basculer_la_coche()
    apres = exp.ligne_de_validation()
    assert "2 fichiers" in _sans_accents_du_test(apres), apres
    # Finding `R21` : `"55 o" in apres or "55" in apres` acceptait n'importe
    # quel « 55 » de la ligne -- la seconde branche rendait la premiere inutile.
    # Le poids se lit ici a sa forme rendue, et une seule.
    assert "55 o" in apres, f"le poids total (22+33) : {apres}"


def test_la_ligne_du_bas_tient_la_grille_a_trois_chiffres(tmp_path):
    """AC 5.5. Le repli ASCII ALLONGE : `⏎` y vaut six colonnes.

    **Cette mesure ne pouvait pas rougir jusqu'au 2026-08-31** (finding `R20`).
    Elle posait 123 chemins **inexistants**, donc le poids valait `·` -- une
    colonne au lieu des sept de son pire cas --, et surtout
    `ligne_de_validation` passe par `jetons.abreger_nom`, qui **garantit** la
    tenue par construction : le test mesurait une propriete d'`abreger_nom`, pas
    de la ligne.

    Ce qui se mesure vraiment, c'est la ligne **avant** l'abregement : si elle
    tient deja, aucun nom n'est jamais coupe. C'est la propriete utile, et elle
    peut, elle, cesser d'etre vraie -- un libelle plus long, une unite de poids
    plus large. Les chemins sont donc REELS, avec un poids qui se mesure.
    """
    base = _selection_de_trois_fichiers(tmp_path)
    gros = base / "gros"
    gros.mkdir()
    for n in range(123):
        (gros / f"p{n:03}.tiff").write_bytes(b"x" * 9)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    exp.curseur = _rangs(exp).index("gros")
    assert exp.basculer_la_coche() is None
    assert exp._cardinal_de_la_selection() == 123, "la mesure est REELLE"

    utile = jetons.largeur_utile()
    for ascii_seul in (False, True):
        ligne = exp.ligne_de_validation(ascii_seul, utile)
        assert jetons.colonnes(ligne) <= utile, (
            f"{jetons.colonnes(ligne)} colonnes pour {utile} "
            f"({'ASCII' if ascii_seul else 'UTF-8'}) : {ligne}")
        # **Le volet qui MESURE** : la ligne tient SANS que l'abregement ait eu
        # a mordre. Le point d'abregement, present, dirait qu'un nom a ete
        # coupe -- ce qui, sur une phrase, coupe au MILIEU d'un mot puisque
        # `abreger_nom` est ecrite pour des noms de fichier.
        assert jetons.points_d_abregement(ascii_seul) not in ligne, (
            "la ligne du bas a du etre abregee : elle ne tient plus seule, et "
            f"l'abregement d'un NOM applique a une phrase coupe au milieu d'un "
            f"mot. {ligne!r}")


def test_un_dossier_compte_ses_FICHIERS_quand_le_site_cherche_des_fichiers(
        tmp_path):
    """AC 4 bis, `EPIC11-ARB-121`. Egan : « c'est une bonne feature ».

    Le dossier porte TROIS sous-dossiers et DEUX fichiers : les deux nombres
    different, sans quoi le test serait vert quelle que soit la branche prise.
    """
    base = arborescence(tmp_path, ["dd_dossier"], {"dd_dossier": 3})
    (base / "dd_dossier" / "a.tiff").write_bytes(b"x")
    (base / "dd_dossier" / "b.tiff").write_bytes(b"y")
    dossiers_seuls = explorateur.Explorateur(base)
    avec_fichiers = explorateur.Explorateur(base, montrer_fichiers=True)
    gauche = dossiers_seuls.entrees[0].droite
    droite = avec_fichiers.entrees[0].droite
    assert "3 sous-dossiers" == gauche, gauche
    assert "2 fichiers" == droite, droite


def test_la_colonne_du_dossier_reste_PARESSEUSE(tmp_path):
    """AC 4 bis.2. La paresse existe apres mesure : 27 `iterdir()` par relecture
    sur un volume lent (AC 4.6 de la 11.2b). La changer de filtre ne doit pas la
    changer de moment."""
    base = arborescence(tmp_path, ["aa", "mm", "zz"], {"aa": 1, "mm": 2, "zz": 3})
    lectures = []
    exp = explorateur.Explorateur(
        base, montrer_fichiers=True,
        compter_sous_dossiers=lambda c: lectures.append(c) or 0)
    assert lectures == [], "aucun comptage a la relecture"
    _ = exp.entrees[1].droite
    assert len(lectures) == 1, lectures


# ---------------------------------------------------------------------------
# T4 -- la TOUCHE. `EPIC11-ARB-103` : `Espace` sort de l'attrape-tout des
# caracteres imprimables, et l'exception est BORNEE au mode selection.
# ---------------------------------------------------------------------------

def test_Espace_est_bien_un_caractere_IMPRIMABLE(tmp_path):
    """Le fait qui fonde `EPIC11-ARB-103`, mesure plutot que suppose.

    `" ".isprintable()` vaut `True` en Python : `Espace` partait donc a
    `sauter()` par l'attrape-tout de l'ecran. La premiere lecture de cette story
    annoncait « la touche est libre » -- c'etait vrai du composant et faux de
    l'ecran. Si ce test devenait faux, tout le raisonnement de l'arbitrage
    tomberait, et il vaut mieux qu'un banc le dise.
    """
    assert " ".isprintable() is True
    assert "\t".isprintable() is False


def test_le_saut_alphabetique_ne_trouve_JAMAIS_rien_sur_un_espace(tmp_path):
    """Ce que l'exception coute vraiment : rien.

    Aucun nom de la fabrique ne commence par un espace -- comme aucun nom de
    dossier reel. Le saut sur `Espace` etait donc deja inoperant ; ce que
    l'arbitrage retire n'est pas un geste utile, c'est un geste mort qui
    occupait une touche.
    """
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True)
    assert exp.sauter(" ") is False


def test_basculer_la_coche_est_INERTE_en_mode_simple(tmp_path):
    """AC 3.2, la borne de l'exception. Les quatre sites livres ne voient rien."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True)
    exp.curseur = _rangs(exp).index("mm_deux.tiff")
    assert exp.basculer_la_coche() is None
    assert exp.selection == ()


def test_cocher_ne_bouge_ni_le_curseur_ni_la_fenetre(tmp_path):
    """Cocher est un geste de RETENUE, pas de navigation.

    Un cochage qui avancerait le curseur ferait deux gestes pour un, et
    interdirait de decocher ce qu'on vient de cocher sans remonter.
    """
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    rang = _rangs(exp).index("mm_deux.tiff")
    exp.curseur = rang
    premier = exp.premier_visible
    exp.basculer_la_coche()
    assert exp.curseur == rang
    assert exp.premier_visible == premier


class _HoteMinimal:
    """Le strict necessaire pour exercer `CoutureExplorateur` SANS terminal.

    La couture est un mixin : elle attend de son ecran `self.explorateur`,
    `self._etat_a_dire`, et deux gestes qui appartiennent a l'ecran. Un stub
    suffit donc a mesurer le ROUTAGE, qui est ce que la story change -- et ca
    garde ce test hors de `test_ecran_projet_tui.py`, que d'autres lots
    touchent.
    """

    def __init__(self, exp):
        self.explorateur = exp
        self._etat_a_dire = ""
        self.sorti = False
        self.valide = None

    def _sortir_de_l_explorateur(self):
        self.sorti = True
        return True

    def _valider_l_explorateur(self):
        self.valide = self.explorateur.valider()


def _couture(exp):
    from mixed_media_utility.tui.ecran_projet import CoutureExplorateur

    class _Hote(_HoteMinimal, CoutureExplorateur):
        pass

    return _Hote(exp)


def test_Espace_COCHE_en_mode_selection_et_SAUTE_en_mode_simple(tmp_path):
    """AC 3.1 et 3.2 -- c'est CE test qui borne l'exception d'`EPIC11-ARB-103`,
    pas la phrase qui l'accompagne."""
    base = _selection_de_trois_fichiers(tmp_path)

    choisi = explorateur.Explorateur(base, montrer_fichiers=True,
                                     selection_multiple=True)
    choisi.curseur = _rangs(choisi).index("mm_deux.tiff")
    hote = _couture(choisi)
    assert hote._traiter_l_explorateur("space", " ") is True
    assert [c.name for c in choisi.selection] == ["mm_deux.tiff"]

    simple = explorateur.Explorateur(base, montrer_fichiers=True)
    rang = _rangs(simple).index("mm_deux.tiff")
    simple.curseur = rang
    hote_simple = _couture(simple)
    assert hote_simple._traiter_l_explorateur("space", " ") is True
    assert simple.selection == (), "le mode simple ne coche rien"
    assert simple.curseur == rang, (
        "aucun nom ne commence par un espace : le saut ne trouve rien et ne "
        "deplace donc pas le curseur")


def test_l_evenement_est_CONSOMME_dans_les_deux_modes(tmp_path):
    """AC 3.4, et c'est une perte de travail deja payee.

    `sauter` rend faux quand rien ne correspond ; si l'ecran laissait alors
    l'evenement remonter, il atteindrait le binding applicatif `q` et
    **fermerait l'application**. La meme touche quitterait donc ou sauterait
    selon le contenu du dossier.
    """
    base = _selection_de_trois_fichiers(tmp_path)
    for multiple in (False, True):
        exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                      selection_multiple=multiple)
        hote = _couture(exp)
        assert hote._traiter_l_explorateur("space", " ") is True
        assert hote._traiter_l_explorateur("q", "q") is True, (
            "une lettre sans correspondance est consommee elle aussi")


def test_dans_la_SAISIE_Espace_ecrit_un_espace_quel_que_soit_le_mode(tmp_path):
    """AC 3.3. La selection n'a pas le focus quand la barre d'adresse l'a."""
    base = _selection_de_trois_fichiers(tmp_path)
    for multiple in (False, True):
        exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                      selection_multiple=multiple)
        exp.basculer_la_saisie()
        assert exp.dans_la_saisie
        avant = exp.saisie or ""
        hote = _couture(exp)
        assert hote._traiter_l_explorateur("space", " ") is True
        assert (exp.saisie or "") == avant + " ", (exp.saisie, multiple)
        assert exp.selection == ()


def test_une_entree_refusee_fait_DIRE_son_motif_a_l_ecran(tmp_path):
    """AC 2.4, cote couture : le motif remonte a la ligne d'etat, il ne se perd
    pas entre le modele et l'ecran."""
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(
        base, montrer_fichiers=True, selection_multiple=True,
        accepte=lambda c: c.suffix == ".tiff")
    exp.curseur = _rangs(exp).index("nn_refuse.txt")
    hote = _couture(exp)
    assert hote._traiter_l_explorateur("space", " ") is True
    assert hote._etat_a_dire, "le refus se DIT"
    assert "nn_refuse" in hote._etat_a_dire


# ---------------------------------------------------------------------------
# Fermeture des cinq survivants de la campagne du 2026-08-31.
#
# Aucun des cinq n'etait une equivalence : ils nommaient tous un trou du banc,
# et le plus instructif est `S3` -- l'exception d'`Espace` que je croyais bornee
# par un test qui ne mesurait rien.
# ---------------------------------------------------------------------------

def test_la_selection_multi_dossiers_se_range_par_DOSSIER_puis_par_nom(tmp_path):
    """Ferme `S2`. La cle d'affichage porte le parent, et c'est mesurable.

    Deux fichiers de MEME NOM dans deux dossiers differents : sans le parent
    dans la cle, ils se rangent l'un dans l'autre et l'ordre rendu n'est celui
    d'aucun ecran. Aucun test ne le voyait -- tous cochaient dans un seul
    dossier.
    """
    base = arborescence(tmp_path, ["aa_avant", "zz_apres"],
                        {"aa_avant": 1, "zz_apres": 2})
    for dossier in ("aa_avant", "zz_apres"):
        (base / dossier / "planche.tiff").write_bytes(b"x")
        (base / dossier / "zzz_autre.tiff").write_bytes(b"y")
    exp = explorateur.Explorateur(base / "zz_apres", montrer_fichiers=True,
                                  selection_multiple=True)
    for nom in ("zzz_autre.tiff", "planche.tiff"):
        exp.curseur = _rangs(exp).index(nom)
        exp.basculer_la_coche()
    # Finding `R21` : la ligne d'ici etait
    # `assert exp.remonter() and exp.entrer() is not None or True`, qui est
    # **toujours vraie** (`X and Y or True`). Elle ne mesurait rien et masquait
    # que le deplacement reel se fait par affectation, deux lignes plus bas. On
    # remonte donc pour de vrai, et on le mesure.
    depart = exp.dossier
    assert exp.remonter() is True
    assert exp.dossier == depart.parent
    exp.dossier = base / "aa_avant"
    exp.relire()
    exp.curseur = _rangs(exp).index("planche.tiff")
    exp.basculer_la_coche()

    rendu = [(c.parent.name, c.name) for c in exp.selection]
    assert rendu == [
        ("aa_avant", "planche.tiff"),
        ("zz_apres", "planche.tiff"),
        ("zz_apres", "zzz_autre.tiff"),
    ], rendu


def test_Espace_en_mode_simple_SAUTE_VRAIMENT(tmp_path):
    """Ferme `S3`, et c'est celui qui m'a le plus appris.

    Le test qui pretendait borner l'exception verifiait que le curseur ne
    bougeait pas apres un `Espace` en mode simple. Or il ne bouge pas non plus
    quand la touche coche -- les deux branches sont indiscernables tant
    qu'AUCUN nom ne commence par un espace, et j'avais moi-meme ecrit que c'est
    le cas ordinaire.

    Le voici, le cas qui les separe : un nom qui commence par un espace. Il est
    pathologique, il est legal sur les trois systemes, et il est le SEUL a
    mesurer que `Espace` part bien au saut en mode simple.
    """
    base = arborescence(tmp_path, ["aa_dossier"], {"aa_dossier": 1},
                        {" espace_en_tete.tiff": 5, "mm_normal.tiff": 6})
    exp = explorateur.Explorateur(base, montrer_fichiers=True)
    noms = _rangs(exp)
    depart = noms.index("mm_normal.tiff")
    vise = noms.index(" espace_en_tete.tiff")
    assert depart != vise, noms
    exp.curseur = depart
    hote = _couture(exp)
    assert hote._traiter_l_explorateur("space", " ") is True
    assert exp.curseur == vise, (
        "en mode simple, `Espace` doit partir au saut alphabetique et trouver "
        f"le nom qui commence par un espace : {noms}")


def test_cocher_un_DOSSIER_le_resout_en_fichiers_et_en_poids(tmp_path):
    """Ferme `S6` et `S7`. `EPIC11-ARB-120`, verbatim d'Egan : « a la fin ce
    sont bien les fichiers qui sont scannes ».

    Aucun test ne cochait un DOSSIER -- tous cochaient des fichiers. Le compte
    pouvait donc annoncer « 1 » pour un dossier de huit planches, et le poids
    l'oublier entierement, sans qu'aucun banc ne bronche.
    """
    base = arborescence(tmp_path, ["dd_dossier"], {"dd_dossier": 1},
                        {"mm_seul.tiff": 7})
    for n, taille in enumerate((10, 20, 30)):
        (base / "dd_dossier" / f"p{n}.tiff").write_bytes(b"x" * taille)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    exp.curseur = _rangs(exp).index("dd_dossier")
    exp.basculer_la_coche()
    exp.curseur = _rangs(exp).index("mm_seul.tiff")
    exp.basculer_la_coche()

    # QUATRE fichiers : trois dans le dossier, un a cote. Un compte qui dirait
    # « 2 » compterait des ENTREES cochees, pas des fichiers a scanner.
    assert exp._cardinal_de_la_selection() == 4
    assert exp._poids_de_la_selection() == 10 + 20 + 30 + 7
    assert "4 selectionnes" in _sans_accents_du_test(exp.etat()), exp.etat()
    assert "4 fichiers" in _sans_accents_du_test(exp.ligne_de_validation())


def test_un_dossier_coche_ILLISIBLE_rend_une_mesure_ABSENTE_pas_un_total(
        tmp_path):
    """Ferme `S9`. Un total ampute passerait pour un total.

    C'est la doctrine du `·` de `_colonne_de_compte`, appliquee au compte de
    selection : `None` et un chiffre partiel ne sont pas la meme information,
    et c'est le chiffre partiel qui est dangereux -- il a l'air d'une mesure.

    **Trois coches, la cible AU MILIEU de la liste que les COMPTEURS parcourent**
    (finding `R23`). La premiere redaction n'en cochait que deux, et l'illisible
    y etait donc aussi le DERNIER : un compteur qui n'examinerait que la premiere
    entree de `self._selection`, ou qui s'arreterait a la premiere, y survivait.
    La regle des fabriques vaut sur la liste PARCOURUE -- ici `self._selection`,
    dont l'ordre est celui du cochage -- et pas seulement sur `exp.entrees`.
    """
    base = arborescence(tmp_path, ["aa_lisible"], {"aa_lisible": 1},
                        {"mm_fichier.tiff": 9, "zz_dernier.tiff": 7})
    (base / "aa_lisible" / "p.tiff").write_bytes(b"x" * 4)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    # L'ordre de cochage EST l'ordre du dict : la cible est cochee en second
    # sur trois, donc ni premiere ni derniere.
    for nom in ("mm_fichier.tiff", "aa_lisible", "zz_dernier.tiff"):
        exp.curseur = _rangs(exp).index(nom)
        assert exp.basculer_la_coche() is None, nom
    parcourus = list(exp._selection)
    rang = [c.name for c in parcourus].index("aa_lisible")
    assert 0 < rang < len(parcourus) - 1, (
        f"la cible doit etre au MILIEU de la liste PARCOURUE : rang {rang} sur "
        f"{len(parcourus)} ({[c.name for c in parcourus]})")
    assert exp._cardinal_de_la_selection() == 3

    # Le dossier devient illisible APRES le cochage -- c'est le volume
    # debranche en cours de session, pas un dossier refuse des le depart.
    shutil.rmtree(base / "aa_lisible")
    assert exp._poids_de_la_selection() is None
    assert exp._cardinal_de_la_selection() is None
    etat = _sans_accents_du_test(exp.etat())
    assert "selectionnes" in etat and "3 selectionnes" not in etat, etat


# ---------------------------------------------------------------------------
# Fermeture des findings de la revue en trois couches du 2026-08-31.
# Rapports complets et mesures dans `review-11-2c-triage.md`.
# ---------------------------------------------------------------------------

def _selection_avec_dossier_et_bruit(tmp_path):
    """Un dossier de planches, un fichier refuse dedans, un cache dedans.

    C'est la fabrique des findings `R3` et `R4` : ce que le site accepte et ce
    que le dossier contient ne sont pas la meme chose, et les deux tailles sont
    choisies pour que la confusion se VOIE -- un `.txt` de 6000 octets contre
    des planches de 10.
    """
    base = tmp_path / "base"
    rush = base / "rush"
    rush.mkdir(parents=True)
    for n in range(2):
        (rush / f"planche_{n}.tiff").write_bytes(b"x" * 10)
    (rush / "notes.txt").write_bytes(b"n" * 6000)
    (rush / ".DS_Store").write_bytes(b"d" * 6000)
    profond = rush / "sous"
    profond.mkdir()
    (profond / "planche_9.tiff").write_bytes(b"x" * 10)
    cache = rush / ".cache"
    cache.mkdir()
    (cache / "vignette.tiff").write_bytes(b"v" * 9999)
    (base / "zz_ailleurs.tiff").write_bytes(b"a" * 5)
    return base


def _explorateur_de_planches(base):
    return explorateur.Explorateur(
        base, montrer_fichiers=True, selection_multiple=True,
        accepte=lambda c: c.suffix == ".tiff")


def _cocher(exp, nom):
    exp.curseur = _rangs(exp).index(nom)
    assert exp.basculer_la_coche() is None, nom


def test_R3_le_compte_d_un_dossier_coche_est_CE_QUE_LE_SITE_PRENDRA(tmp_path):
    """`EPIC11-ARB-123`. Le filtre `accepte` et les caches s'appliquent DEDANS.

    Mesure de la revue avant correction : « 10 fichiers selectionnes   12 ko »
    pour 8 planches et 800 octets. Le meme `accepte` qui pose le `✕` sur un
    `.txt` en surface l'avalait par son dossier.
    """
    exp = _explorateur_de_planches(_selection_avec_dossier_et_bruit(tmp_path))
    _cocher(exp, "rush")
    assert exp._cardinal_de_la_selection() == 3, (
        "deux planches a la racine du dossier plus une dans le sous-dossier : "
        "ni le .txt, ni le .DS_Store, ni la vignette du dossier cache")
    assert exp._poids_de_la_selection() == 30, (
        "les 6000 octets du .txt et les 9999 de la vignette cachee ne sont pas "
        "du poids a scanner")


def test_R3bis_un_dossier_CACHE_est_ELAGUE_et_non_parcouru_pour_rien(tmp_path):
    """Le volet de cout : `.git/` ne se parcourt pas pour etre jete."""
    base = _selection_avec_dossier_et_bruit(tmp_path)
    vus = []
    vrai = explorateur.os.walk

    def walk_espion(dossier, **kwargs):
        for base_, dossiers, fichiers in vrai(dossier, **kwargs):
            vus.append(Path(base_).name)
            yield base_, dossiers, fichiers

    explorateur.os.walk = walk_espion
    try:
        exp = _explorateur_de_planches(base)
        _cocher(exp, "rush")
        exp._cardinal_de_la_selection()
    finally:
        explorateur.os.walk = vrai
    assert ".cache" not in vus, (
        f"le dossier cache a ete PARCOURU avant d'etre jete : {vus}")
    assert "sous" in vus, f"le sous-dossier visible doit l'etre : {vus}"


def test_R2_un_dossier_et_un_fichier_QU_IL_CONTIENT_ne_comptent_qu_une_fois(
        tmp_path):
    """Finding `R2`, trouve par deux couches. Trois touches suffisent.

    L'AC 4.3 fait survivre la selection au changement de dossier : cocher
    `rush/`, entrer, cocher `rush/planche_0.tiff` est le parcours nominal, et
    la planche se comptait DEUX fois, en cardinal comme en poids.
    """
    base = _selection_avec_dossier_et_bruit(tmp_path)
    exp = _explorateur_de_planches(base)
    _cocher(exp, "rush")
    exp.curseur = _rangs(exp).index("rush")
    exp.entrer()
    _cocher(exp, "planche_0.tiff")
    assert exp._cardinal_de_la_selection() == 3, (
        "la planche cochee deux fois -- par son dossier et pour elle-meme -- "
        "ne fait pas quatre fichiers")
    assert exp._poids_de_la_selection() == 30


def test_R9_le_rendu_d_une_trame_ne_PARCOURT_RIEN(tmp_path):
    """AC 4.7, VIOLEE avant cette correction (les trois couches l'ont trouve).

    Mesure de la revue : trois parcours recursifs complets plus un `stat()` par
    fichier a CHAQUE rendu de trame, c'est-a-dire a chaque frappe de fleche.
    Ici on compte les `os.walk` : la resolution se paie au cochage, une fois.
    """
    base = _selection_avec_dossier_et_bruit(tmp_path)
    exp = _explorateur_de_planches(base)

    parcours = []
    vrai = explorateur.os.walk

    def walk_espion(dossier, **kwargs):
        parcours.append(Path(dossier))
        yield from vrai(dossier, **kwargs)

    explorateur.os.walk = walk_espion
    try:
        _cocher(exp, "rush")
        au_cochage = len(parcours)
        parcours.clear()
        for _ in range(3):
            exp.lignes(80, titre="Choisir", ascii_seul=False)
            exp.etat(76, False)
            exp.ligne_de_validation(False)
    finally:
        explorateur.os.walk = vrai

    assert au_cochage == 1, (
        f"la resolution se paie UNE fois, au cochage : {au_cochage} parcours")
    assert parcours == [], (
        f"trois rendus de trame ont declenche {len(parcours)} parcours "
        f"recursifs : {parcours}. C'est la latence que l'AC 4.6 de la 11.2b "
        "avait fait fermer")


def test_R1_le_repli_ASCII_tient_AUSSI_en_mode_SELECTION(tmp_path):
    """Findings `R1` / `A2` / `E1`, trouves par deux couches.

    Deux defauts au meme endroit : `selectionné` portait un ACCENT -- le premier
    texte accentue jamais rendu par ce module --, et le glyphe `·` etait lu dans
    `jetons.GLYPHES` en dur alors que la table du mode etait dans la portee.

    **La frontiere existait deja** (`test_le_repli_ASCII_ne_laisse_aucun_...`,
    finding `F7`, deja paye par ce depot) : elle rougissait des qu'on activait
    le mode selection. Sa fabrique n'y etait jamais entree. Ce test est cette
    frontiere, sur le mode neuf, et il porte les DEUX etats de la mesure --
    mesurable et absente --, parce que c'est la branche absente qui portait le
    glyphe en dur.
    """
    base = _selection_avec_dossier_et_bruit(tmp_path)
    exp = _explorateur_de_planches(base)
    _cocher(exp, "rush")
    _cocher(exp, "zz_ailleurs.tiff")

    def tout_le_rendu():
        return (list(exp.lignes(80, titre="Choisir", ascii_seul=True))
                + [exp.etat(76, True), exp.ligne_de_validation(True)])

    for ligne in tout_le_rendu():
        assert ligne.isascii(), f"hors ASCII en repli : {ligne!r}"
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne
    assert "selectionnes" in exp.etat(76, True)
    # Le volet symetrique : en UTF-8 l'accent est bien la, comme les maquettes
    # `X11` et `X11b` qu'Egan a validees l'ecrivent. Retirer l'accent partout
    # aurait ferme le finding en faisant diverger le produit d'une maquette
    # approuvee -- exactement le defaut voisin (`R11`) que la meme revue a
    # trouve ailleurs.
    assert "s\u00e9lectionn\u00e9s" in exp.etat(76, False), exp.etat(76, False)
    assert "s\u00e9lectionn\u00e9s" in exp.ligne_de_validation(False)

    # La branche NON MESURABLE : c'est elle qui portait le glyphe en dur.
    shutil.rmtree(base / "rush")
    for ligne in tout_le_rendu():
        assert ligne.isascii(), f"hors ASCII en repli, mesure absente : {ligne!r}"
    assert exp._cardinal_de_la_selection() is None


def test_R19_la_mesure_absente_ne_melange_pas_pluriel_et_singulier(tmp_path):
    """Finding `R19`. « · fichiers selectionne » : tete plurielle, participe
    singulier. Les deux couches l'ont note, et il se voit a l'oeil nu."""
    base = _selection_avec_dossier_et_bruit(tmp_path)
    exp = _explorateur_de_planches(base)
    _cocher(exp, "rush")
    shutil.rmtree(base / "rush")
    resume = exp._resume_de_la_selection()
    assert "fichiers s\u00e9lectionn\u00e9s" in resume, resume
    assert "fichiers s\u00e9lectionn\u00e9 " not in resume, resume
    replie = exp._resume_de_la_selection(True)
    assert "fichiers selectionnes" in replie, replie


def test_R6_Ctrl_H_NE_DECOCHE_PAS_ce_qu_il_masque(tmp_path):
    """`EPIC11-ARB-124`. Masque n'est pas absent.

    Mesure de la revue : cocher un fichier cache et un fichier visible, puis
    `Ctrl+H` -- la selection tombait au seul fichier visible, sans un mot, alors
    que la ligne d'etat venait d'annoncer qu'elle masquait quelque chose.
    """
    base = tmp_path / "base"
    base.mkdir()
    for nom, taille in ((".cache_planche.tiff", 3), ("mm.tiff", 5),
                        ("zz.tiff", 7)):
        (base / nom).write_bytes(b"x" * taille)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    exp.basculer_les_caches()
    _cocher(exp, ".cache_planche.tiff")
    _cocher(exp, "mm.tiff")
    assert len(exp.selection) == 2

    exp.basculer_les_caches()
    assert exp.caches_masques == 1, "l'ecran dit bien qu'il masque quelque chose"
    assert len(exp.selection) == 2, (
        f"une coche est tombee parce qu'on a cesse de la voir : {exp.selection}")
    assert exp._cardinal_de_la_selection() == 2
    assert exp._poids_de_la_selection() == 8


def test_R7_un_dossier_courant_ILLISIBLE_ne_purge_PAS_la_selection(tmp_path):
    """`EPIC11-ARB-124`, second volet -- trouve par la couche 2 seule.

    `relire()` passait l'ensemble des entrees SANS regarder `dossier_lisible` :
    sur un volume debranche, la liste est vide et la purge concluait que tout
    avait disparu. Le module distingue partout `None` de `[]` ; ce chemin-la les
    confondait.
    """
    base = tmp_path / "base"
    base.mkdir()
    for nom in ("aa.tiff", "mm.tiff", "zz.tiff"):
        (base / nom).write_bytes(b"x" * 4)
    lisible = {"oui": True}
    exp = explorateur.Explorateur(
        base, montrer_fichiers=True, selection_multiple=True,
        lister=lambda d: (list(d.iterdir()) if lisible["oui"] else None))
    _cocher(exp, "mm.tiff")
    _cocher(exp, "zz.tiff")

    lisible["oui"] = False
    exp.relire()
    assert exp.dossier_lisible is False
    assert len(exp.selection) == 2, (
        f"un volume debranche n'est pas un dossier vide : {exp.selection}")

    lisible["oui"] = True
    exp.relire()
    assert len(exp.selection) == 2, "et la selection revient avec le volume"


def test_R7bis_une_disparition_REELLE_retire_bien_la_coche(tmp_path):
    """Le volet symetrique, sans lequel le precedent ne mesure rien : la purge
    doit toujours fonctionner quand la disparition est reelle et constatee."""
    base = tmp_path / "base"
    base.mkdir()
    for nom in ("aa.tiff", "mm.tiff", "zz.tiff"):
        (base / nom).write_bytes(b"x" * 4)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    _cocher(exp, "mm.tiff")
    _cocher(exp, "zz.tiff")
    (base / "mm.tiff").unlink()
    exp.relire()
    assert [c.name for c in exp.selection] == ["zz.tiff"]


def test_R17_N2_la_purge_retire_TOUS_les_chemins_disparus_pas_le_premier(
        tmp_path):
    """Mutant `N2` de la couche 2, SURVIVANT : `for chemin in perdus[:1]`.

    Aucun test ne faisait disparaitre DEUX chemins coches entre deux relectures.
    Trois coches, les deux du MILIEU disparaissent -- regle des fabriques,
    point 2 bis, applique a la liste que la purge PARCOURT.
    """
    base = tmp_path / "base"
    base.mkdir()
    for nom in ("aa.tiff", "mm.tiff", "nn.tiff", "zz.tiff"):
        (base / nom).write_bytes(b"x" * 4)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    for nom in ("aa.tiff", "mm.tiff", "nn.tiff", "zz.tiff"):
        _cocher(exp, nom)
    (base / "mm.tiff").unlink()
    (base / "nn.tiff").unlink()
    exp.relire()
    assert [c.name for c in exp.selection] == ["aa.tiff", "zz.tiff"]


def test_R11_les_QUATRE_sites_montent_l_explorateur_avec_les_reglages_ATTENDUS():
    """AC 1.2, qui n'avait AUCUN test (findings `R11` et `A4`).

    L'AC exigeait « site par site et non en bloc [...] l'egalite du rendu » ; la
    tache y repondait « mesure par la suite TUI entiere », c'est-a-dire
    precisement la mesure en bloc que l'AC interdit. Et c'est ce trou qui a
    laisse passer la divergence de `E2-1c` : le site du relink « designer »
    montre des FICHIERS, sa colonne de droite a donc change d'unite
    (`EPIC11-ARB-121`), et la maquette validee ne l'avait pas suivi.

    La mesure lit les sites **par le source**, sans monter d'application : elle
    tient donc dans un banc unitaire, et elle nomme chaque site plutot que de
    compter.

    **La moitie qui portait sur `selection_multiple` a change de sens le
    2026-08-31, et c'est une mesure qui l'a rendue fausse** : elle disait
    « aucun site ne le demande », ce qui etait vrai tant qu'aucun ecran ne
    consommait la capacite livree par la 11.2c. Le lot E bis de la story 11.5
    monte `E3-1` en mode selection -- c'est la quatrieme forme de source
    d'`EPIC7-ARB-88`, une sequence de chemins qui fait un lot, et elle etait
    injoignable depuis la TUI.

    **SIX sites depuis la story 11.6, lot C** (2026-09-01), et cette frontiere a
    rougi **dans le sens de l'amelioration** : `E3-5` -- le choix du profil de
    calibration -- ouvre l'explorateur sur un `.json`, et c'est le quatrieme des
    cinq sites qu'`EPIC11-ARB-48` nomme (« Scan, "autre fichier..." : un fichier
    `.json` »), livre par la 11.2b et cable seulement maintenant. L'AC 3.5 de la
    11.6 nommait cette mise a jour d'avance, pour qu'elle ne soit pas prise pour
    une regression et qu'elle ne soit pas non plus contournee en relachant
    l'egalite en inclusion.

    **SEPT sites depuis le lot G de la meme story**, et celui-la n'etait dans
    la table d'AUCUN des cinq : `E3-9` -- calibrer une chaine -- **demande un
    chemin** (« Scan de la page »), et l'arbitrage dit « partout ou la TUI
    demande un chemin ». Il a donc ete **oublie**, pas excepte : c'est l'ecart
    `H11` de la fiche de la 11.6, et l'AC 8.4 en fait le **sixieme** site que
    l'arbitrage aurait du nommer. Le compte de ce banc, lui, en est le
    septieme -- il compte les MONTAGES et non les entrees de la table, et deux
    d'entre eux vivent dans `ecran_projet`.

    **HUIT sites depuis le 2026-09-07**, et le huitieme est
    `palier_profil_defaut` -- l'ecran du profil de calibration par defaut,
    ecrit dans la nuit du 2026-09-06. Il **demande un fichier** (« autre
    fichier… », un `.json` de profil), donc il releve de la meme phrase
    d'`EPIC11-ARB-48` que `E3-5` : « partout ou la TUI demande un chemin ».
    Ce n'est ni une exception ni une regression -- c'est un montage de plus,
    et cette frontiere a fait exactement son travail en le voyant arriver.
    Son entree se pose ici plutot que de relacher l'egalite en inclusion.

    L'assertion reste donc **une egalite et jamais une inclusion** : les sites
    qui demandent le mode sont **exactement** celui du depot du Scan. « Le site
    du Scan le demande » laisserait un neuvieme site l'activer en silence, ce
    qui est precisement ce que ce banc existe pour empecher.
    """
    import ast

    racine = Path(__file__).resolve().parents[3] / "src/mixed_media_utility/tui"
    sites = {}
    for chemin in sorted(racine.glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if not isinstance(noeud, ast.Call):
                continue
            cible = noeud.func
            nom = (cible.attr if isinstance(cible, ast.Attribute)
                   else getattr(cible, "id", None))
            if nom != "Explorateur":
                continue
            reglages = {mc.arg for mc in noeud.keywords}
            sites[f"{chemin.stem}:{noeud.lineno}"] = reglages

    # **HUIT sites** : `E3-5` (lot C de la 11.6) est le dernier des cinq
    # qu'`EPIC11-ARB-48` nomme ; `E3-9` (lot G) est le **sixieme** que
    # l'arbitrage a oublie de nommer alors qu'il demande un chemin ; et
    # `palier_profil_defaut` (2026-09-07) est le septieme de la table, huitieme
    # montage. La mesure NOMME les modules plutot que de compter seule : un
    # site qui changerait de fichier sans que personne l'ait dit ferait
    # toujours rougir.
    assert len(sites) == 8, (
        "HUIT instanciations depuis le 2026-09-07 ; un neuvieme site entre "
        f"dans le produit sans que personne l'ait dit : {sorted(sites)}")
    assert {site.split(":")[0] for site in sites} == {
        "atelier_extraction", "atelier_scan", "atelier_scan_calibrate",
        "atelier_scan_calibration", "ecran_projet",
        "palier_profil_defaut"}, sorted(sites)
    # **L'ensemble EXACT des demandeurs**, nomme par son module : le rang de
    # ligne entrerait dans la mesure sans rien y ajouter, et ferait rougir ce
    # banc a chaque ligne inseree au-dessus du montage.
    demandeurs = {site for site, reglages in sites.items()
                  if "selection_multiple" in reglages}
    assert {site.split(":")[0] for site in demandeurs} == {"atelier_scan"}, (
        "les sites qui demandent le mode selection sont EXACTEMENT celui du "
        f"depot du Scan (`E3-1`) : {sorted(demandeurs)}")
    assert len(demandeurs) == 1, (
        "et il n'y en a qu'UN dans ce module : un second montage en mode "
        f"selection entrerait sans que personne l'ait dit : {sorted(demandeurs)}")
    for site, reglages in sites.items():
        assert "montrer_fichiers" in reglages, (
            f"{site} ne DIT pas ce qu'il montre. `EPIC11-ARB-121` fait suivre "
            "l'unite de la colonne de droite a ce reglage : un site qui le "
            "laisse par defaut choisit son unite sans le savoir")


def test_R11bis_la_colonne_d_un_site_qui_cherche_des_FICHIERS_compte_des_fichiers(
        tmp_path):
    """Le volet comportemental de `R11`, sur la fabrique du site reel.

    `EPIC11-ARB-121` : « la colonne d'un dossier compte ce que le SITE
    cherche ». Le site du relink « designer » monte l'explorateur avec
    `montrer_fichiers=True`, donc sa colonne compte des fichiers -- et c'est ce
    qui a rendu la maquette `E2-1c` perimee.

    Trois elements, la cible AU MILIEU, et des cardinaux DISTINCTS : deux
    dossiers a meme contenu rendraient la permutation invisible.
    """
    base = tmp_path / "hd"
    base.mkdir()
    for nom, fichiers in (("aa_avant", 1), ("proxy", 3), ("zz_apres", 2)):
        d = base / nom
        d.mkdir()
        for n in range(fichiers):
            (d / f"f{n}.mov").write_bytes(b"x")

    montrant = explorateur.Explorateur(base, montrer_fichiers=True)
    cachant = explorateur.Explorateur(base, montrer_fichiers=False)
    rangs = _rangs(montrant)
    rang = rangs.index("proxy")
    assert 0 < rang < len(rangs) - 1, (rangs,)

    droite = {e.chemin.name: e.droite for e in montrant.entrees}
    assert droite["proxy"] == "3 fichiers", droite
    assert droite["aa_avant"] == "1 fichier", droite
    assert droite["zz_apres"] == "2 fichiers", droite
    autre = {e.chemin.name: e.droite for e in cachant.entrees}
    assert autre["proxy"] == "0 sous-dossier", autre


# ---------------------------------------------------------------------------
# `R17` -- les six mutants de disposition et d'ordre restes vivants apres la
# campagne de story. Aucun ne portait sur un calcul : tous sur ce que l'oeil
# voit, ou sur l'ordre d'un parcours. C'est la famille que la relecture rate.
# ---------------------------------------------------------------------------

def test_R17_N5_la_case_vient_APRES_le_glyphe_de_curseur(tmp_path):
    """Mutant `N5` : la case passe AVANT le curseur, et les bancs restaient
    verts. Le seul test de disposition mesurait le DELTA de la colonne du nom
    (quatre), que les deux dispositions satisfont.

    La disposition est copiee de `cadences.py:735` (`EPIC11-ARB-103`) et elle se
    voit sur `X10` : « curseur, puis case, puis nom ». Inversee, la colonne du
    curseur bouge de quatre et se desaligne des lignes `…`, qui ne portent pas
    de case.
    """
    base = _selection_de_trois_fichiers(tmp_path)
    exp = _explorateur_de_planches(base) if False else explorateur.Explorateur(
        base, montrer_fichiers=True, selection_multiple=True)
    exp.curseur = _rangs(exp).index("mm_deux.tiff")
    ligne = [l for l in exp.lignes_de_liste(76, False)
             if "mm_deux.tiff" in l][0]
    curseur = ligne.index(jetons.GLYPHES["curseur"])
    case = ligne.index("[")
    assert curseur < case, (
        "le glyphe de curseur ouvre la ligne, la case s'intercale ENTRE lui et "
        f"le nom : {ligne!r}")
    # Et le volet qui rend la mesure non contournable : sur une ligne SANS
    # curseur, la case occupe exactement la meme colonne.
    exp.curseur = _rangs(exp).index("aa_un.tiff")
    autre = [l for l in exp.lignes_de_liste(76, False)
             if "mm_deux.tiff" in l][0]
    assert autre.index("[") == case, (ligne, autre)


def test_R17_N3_le_compte_de_selection_vient_EN_DERNIER_dans_la_ligne_d_etat(
        tmp_path):
    """Mutant `N3` : `mesures.append` -> `insert(0, ...)`, le compte passe en
    tete. Le banc ne testait qu'une sous-chaine, donc la place n'etait mesuree
    par rien -- alors qu'`EPIC11-ARB-103` la tranche.
    """
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    exp.curseur = _rangs(exp).index("mm_deux.tiff")
    exp.basculer_la_coche()
    mesures = [m.strip() for m in exp.etat(76, False).split("·")]
    assert len(mesures) >= 2, mesures
    assert "lectionn" in mesures[-1], (
        f"le compte de selection est la DERNIERE mesure : {mesures}")
    assert not any("lectionn" in m for m in mesures[:-1]), mesures


def test_R17_M6_les_DOSSIERS_precedent_les_fichiers_dans_la_SELECTION_rendue(
        tmp_path):
    """Mutant `M6` : `_cle_d_affichage` inverse `not est_dossier`.

    Le comportement etait juste, mais la seule fabrique qui mesurait l'ordre ne
    contenait **que des fichiers** -- une permutation dossier/fichier y est
    invisible. C'est `S2` a un axe pres, et l'axe manquait.

    Trois entrees, la cible au milieu de l'ordre attendu.
    """
    base = _selection_de_trois_fichiers(tmp_path)
    exp = explorateur.Explorateur(base, montrer_fichiers=True,
                                  selection_multiple=True)
    for nom in ("zz_trois.tiff", "dd_dossier", "aa_un.tiff"):
        exp.curseur = _rangs(exp).index(nom)
        assert exp.basculer_la_coche() is None, nom
    assert [c.name for c in exp.selection] == [
        "dd_dossier", "aa_un.tiff", "zz_trois.tiff"], (
        "le dossier passe devant les fichiers, puis l'ordre alphabetique : "
        f"{[c.name for c in exp.selection]}")


def test_R17_N6_les_deux_motifs_de_refus_ne_disent_PAS_la_meme_chose(tmp_path):
    """Mutant `N6` : les deux motifs sont interchangeables, et la branche
    « illisible » n'etait exercee par aucun test -- seule la VERITE du motif
    l'etait, jamais son texte.

    Un motif qui dirait « ne se lit pas » d'un fichier parfaitement lisible mais
    refuse par le site enverrait l'operateur verifier son disque.
    """
    base = _selection_de_trois_fichiers(tmp_path)
    illisible = base / "kk_illisible"
    illisible.mkdir()
    exp = explorateur.Explorateur(
        base, montrer_fichiers=True, selection_multiple=True,
        accepte=lambda c: c.suffix == ".tiff",
        lister=lambda d: list(d.iterdir()))
    # Un fichier REFUSE par le site : il se lit tres bien.
    exp.curseur = _rangs(exp).index("nn_refuse.txt")
    refus = exp.basculer_la_coche()
    assert refus is not None and "ne peut pas etre retenu" in refus, refus
    assert "ne se lit pas" not in refus, (
        "un fichier refuse par le site se LIT : dire le contraire enverrait "
        f"verifier le disque. {refus!r}")

    # Et le volet symetrique, sur une entree illisible. `Entree` est gelee --
    # c'est voulu --, donc on la remplace plutot que de la muter.
    import dataclasses

    rang = _rangs(exp).index("kk_illisible")
    exp.entrees[rang] = dataclasses.replace(
        exp.entrees[rang], illisible=True, validable=False)
    exp.curseur = rang
    illisible_motif = exp.basculer_la_coche()
    assert illisible_motif is not None, illisible_motif
    assert "ne se lit pas" in illisible_motif, illisible_motif
    assert illisible_motif != refus, (
        "les deux motifs doivent differer, sinon ils sont interchangeables et "
        "aucun ne dit ce qui s'est passe")
