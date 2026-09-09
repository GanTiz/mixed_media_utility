"""Confrontation des ecrans PROFONDS du parcours Scan a leurs maquettes validees.

**L'audit qui manquait, et ce que la mesure a montre.** Quatre maquettes du
parcours Scan -- `E3-2` (detection en cours), `E3-7` (ecriture en cours),
`E3-8` (resultat), `E3-9` (calibrer) -- sont citees NOMMEMENT, et parfois
jusqu'au numero de ligne, dans les commentaires de leurs bancs :

    test_atelier_scan_detection_tui.py   cite `E3-2`, `E3-3`
    test_atelier_scan_ecriture.py        cite `E3-7`, `E3-8`
    test_atelier_scan_resultat.py        cite `E3-0`, `E3-1`, `E3-3`, `E3-5`, `E3-8`
    test_atelier_scan_calibrate_tui.py   cite `E3-1`, `E3-9`

et **aucun des quatre n'OUVRE le fichier de maquette** -- compte pris a la
commande le 2026-09-06, `grep -c "maquettes" -> 0` sur les quatre. Chaque
valeur y a donc ete recopiee a la main. Le depot connait pourtant le geste
juste et le pratique ailleurs : `test_atelier_scan_rapport.py` lit `E3-3` et
`E3-4` a leur source, `test_atelier_scan_sources_multiples.py` lit `E3-1` et
`E3-1b`. Le commentaire de ce dernier le dit mieux que ce paragraphe : « un
texte recopie a la main derive ; celui-ci est confronte a sa source ».

**Ce que ce banc mesure.** Les constantes de chaine que ces quatre ecrans
exposent et qui sont censees venir de la maquette y sont **verbatim**, la
maquette etant lue a sa source a chaque tour. Ce n'est pas une ressemblance :
c'est une appartenance.

**Ce qu'il NE mesure pas, dit plutot que tu.** La ligne de raccourcis de
`E3-2`, `E3-7` et `E3-8` n'est ecrite par aucun de ces trois modules -- aucun
d'eux ne porte la moindre constante de raccourci, verifie a la commande. Elle
vient de la coque d'execution partagee, qui est **hors du perimetre de ce
lot**. Sa confrontation reste donc a poser, et elle est nommee comme telle
dans `deferred-work.md` plutot qu'enterree ici.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.tui import atelier_scan_calibrate as calibrate  # noqa: E402
from mixed_media_utility.tui import atelier_scan_detection as detection  # noqa: E402
from mixed_media_utility.tui import atelier_scan_ecriture as ecriture  # noqa: E402
from mixed_media_utility.tui import atelier_scan_resultat as resultat  # noqa: E402

#: Les maquettes, lues a leur source -- jamais recopiees ici.
MAQUETTES = (_RACINE / "_bmad-output" / "planning-artifacts" / "ux-designs"
             / "ux-tui-2026-08-27" / "maquettes")

#: La NOTE en pied de maquette est une CONVERSATION avec Egan et l'arbitrage
#: qui en sort ; ce n'est pas de l'ecran. La confondre avec le dessin ferait
#: passer pour « conforme » un libelle qui ne vit que dans une note.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin(nom: str) -> str:
    """Rend le DESSIN d'une maquette, sa note de relecture retiree."""
    chemin = MAQUETTES / nom
    assert chemin.exists(), f"maquette absente: {chemin}"
    return chemin.read_text(encoding="utf-8").split(SEPARATEUR_DE_NOTE)[0]


#: Les quatre ecrans profonds, du plus tot au plus tard dans le parcours.
#: Quatre elements DISTINGUABLES -- module, maquette et cardinal de constantes
#: differents --, et la cible du balayage n'est ni toujours en tete ni toujours
#: en queue : `test_les_deux_BORDS_du_parcours_sont_couverts` place
#: explicitement une mesure a chaque bord.
ECRANS_PROFONDS = [
    ("E3-2", detection, "E3-2-scan-detection-en-cours.txt", [
        "PALIER_DE_L_ATELIER", "OBJET_DU_BANDEAU", "TITRE_DE_LA_TACHE",
        "INTERROMPRE", "UNITE",
    ]),
    ("E3-7", ecriture, "E3-7-scan-ecriture-en-cours.txt", [
        "PALIER_DE_L_ATELIER", "OBJET_DU_BANDEAU", "TITRE_DE_LA_TACHE",
        "LIBELLE_DE_LA_PASSE", "UNITE",
    ]),
    ("E3-8", resultat, "E3-8-scan-resultat.txt", [
        "PALIER_DE_L_ATELIER", "TITRE_ECRIT", "LIBELLE_CALIBRATION",
        "LIBELLE_MANIFESTE", "LIBELLE_DUREE", "SUITE_AUTRES_SCANS",
        "AUCUN_REFUS", "UNITE", "UNITE_DE_PROFONDEUR",
    ]),
    ("E3-9", calibrate, "E3-9-scan-calibrate.txt", [
        "PALIER_DE_L_ECRAN", "TITRE", "TITRE_DE_LA_SORTIE", "LIBELLE_SCAN",
        "LIBELLE_DPI", "LIBELLE_REPRISE", "LIBELLE_ETIQUETTE",
        "LIBELLE_COMMENTAIRE", "LIBELLE_PROFIL", "LIBELLE_REMPLACE",
        "LIBELLE_DEFAUT", "MENTION_REQUIS", "MENTION_REQUIS_DPI",
        "MENTION_VALIDER_SANS_SCAN", "PHRASE_DPI_REQUIS", "CHOIX_OUI",
        "CHOIX_NON", "UNITE_DPI",
    ]),
]


@pytest.mark.parametrize(
    "code, module, maquette, constantes",
    ECRANS_PROFONDS,
    ids=[code for code, _, _, _ in ECRANS_PROFONDS],
)
def test_les_libelles_de_l_ecran_sont_VERBATIM_de_sa_maquette(
    code: str, module, maquette: str, constantes: list[str]
) -> None:
    """Chaque libelle nomme est un fragment EXACT du dessin, pas un voisin."""
    texte = dessin(maquette)
    for nom in constantes:
        assert hasattr(module, nom), (
            f"{code}: {module.__name__} n'expose plus {nom} -- une constante "
            "confrontee a sa maquette ne se supprime pas en silence")
        valeur = getattr(module, nom)
        assert isinstance(valeur, str) and valeur, f"{code}.{nom}"
        assert valeur in texte, (
            f"{code}: {nom} = {valeur!r} ne figure pas dans {maquette}. "
            "Soit l'ecran a derive, soit la maquette a bouge sans que "
            "l'ecart soit nomme -- dans les deux cas ca ne se corrige pas ici.")


def test_la_table_de_confrontation_n_est_pas_VIDE_par_ecran() -> None:
    """Le volet sans lequel le precedent serait vert en ne mesurant rien.

    Une table videe ferait passer les quatre cas parametres sans une seule
    assertion executee -- c'est le mode de panne exact que le `conftest.py` du
    dossier nomme deja pour `sources_tui` (« une frontiere posee sur un paquet
    quasi vide ne mesure rien »).
    """
    assert len(ECRANS_PROFONDS) == 4, ECRANS_PROFONDS
    for code, module, maquette, constantes in ECRANS_PROFONDS:
        # Le cardinal n'est PAS un seuil choisi a la main : c'est celui que le
        # module et le dessin rendent. Un seuil arbitraire (« au moins cinq »)
        # a ete mesure SURVIVANT le 2026-09-06 -- mutant N2, desserre a zero,
        # treize cas toujours verts -- parce que rien ne le reliait a une
        # grandeur reelle.
        assert len(constantes) == len(constantes_verbatim(module, maquette)), code
    # Et `EXCLUSIONS` reste une liste courte et justifiee : elle est la seule
    # facon de sortir un libelle de la mesure, donc elle ne grossit pas sans
    # qu'on le voie.
    assert len(EXCLUSIONS) <= 6, sorted(EXCLUSIONS)


#: Constantes verbatim de leur maquette qu'on EXCLUT deliberement de la table,
#: avec le motif. Sans cette liste nommee, la garde d'exhaustivite ci-dessous
#: obligerait a declarer des valeurs qui ne sont pas des libelles d'ecran.
EXCLUSIONS = {
    # Un gabarit d'indentation, pas un libelle : trois espaces se retrouvent
    # dans n'importe quel dessin et ne discriminent rien.
    "INDENT_DU_CURSEUR",
    "INDENT_DU_TEXTE",
    # Cles techniques de champ (`scan`, `dpi`) : elles se retrouvent dans le
    # dessin par HASARD, comme fragments de mots, pas comme libelles.
    "CHAMP_SCAN",
    "CHAMP_DPI",
    # Un SEPARATEUR, pas un libelle -- et il n'appartient meme pas au module
    # ou il apparait : `atelier_scan_calibrate` l'IMPORTE d'
    # `atelier_scan_calibration` (2026-09-06, pour couper la part non mesuree
    # de la ligne d'etat). Il est verbatim de tous les dessins qui portent une
    # carte, donc il ne discrimine rien -- le declarer a la table de `E3-9`
    # affirmerait que cette maquette-la le possede, ce qui est faux.
    "SEPARATEUR_DE_CARTE",
}

#: Longueur en deca de laquelle une chaine se retrouve dans n'importe quel
#: dessin sans rien mesurer. **Trois et non quatre**, mesure : a quatre, les
#: trois libelles `oui`, `non` et `dpi` de `E3-9` sortaient du calcul alors
#: qu'ils sont bel et bien au dessin (`( ) oui    (•) non`, `requis · dpi`).
#: Ce qui separe le bruit du libelle n'est donc pas la longueur seule mais la
#: liste nommee `EXCLUSIONS` ci-dessus, qui porte son motif entree par entree.
LONGUEUR_UTILE = 3


def constantes_verbatim(module, maquette: str) -> set[str]:
    """Les constantes du module qui figurent MOT POUR MOT dans le dessin."""
    texte = dessin(maquette)
    trouvees = set()
    for nom in dir(module):
        if not nom.isupper() or nom in EXCLUSIONS:
            continue
        valeur = getattr(module, nom)
        if (isinstance(valeur, str) and len(valeur) >= LONGUEUR_UTILE
                and valeur.strip() and valeur in texte):
            trouvees.add(nom)
    return trouvees


@pytest.mark.parametrize(
    "code, module, maquette, constantes",
    ECRANS_PROFONDS,
    ids=[code for code, _, _, _ in ECRANS_PROFONDS],
)
def test_la_table_est_EXHAUSTIVE_et_pas_seulement_correcte(
    code: str, module, maquette: str, constantes: list[str]
) -> None:
    """Toute constante verbatim du dessin est DECLAREE, ou explicitement exclue.

    Une table simplement *correcte* se vide une entree a la fois sans jamais
    rougir : retirer un libelle de la liste enleve une mesure, et les gardes de
    cardinal ne voient rien tant qu'il en reste assez. Ici la table est
    recalculee depuis le module et le dessin, donc elle ne peut plus retrecir
    en silence -- et une constante NEUVE qui atterrit dans le dessin doit etre
    declaree ou nommee dans `EXCLUSIONS`, jamais oubliee.
    """
    attendues = constantes_verbatim(module, maquette)
    # Le volet sans lequel tout le reste est vide : un calcul qui ne trouve
    # RIEN rendrait l'inclusion ci-dessous vraie par vacuite. Mutant N10,
    # mesure survivant le 2026-09-06 -- neutraliser le filtre de
    # `constantes_verbatim` laissait les treize cas verts.
    assert attendues, (
        f"{code}: aucune constante verbatim trouvee dans {maquette}. "
        "Le calcul de confrontation ne mesure plus rien.")
    manquantes = attendues - set(constantes)
    assert not manquantes, (
        f"{code}: ces constantes sont verbatim de {maquette} mais absentes de "
        f"la table de confrontation: {sorted(manquantes)}")
    # Egalite, pas inclusion : une table qui declarerait des noms que le calcul
    # ne retrouve plus signalerait un libelle sorti du dessin.
    assert set(constantes) == attendues, (
        f"{code}: declarees mais plus verbatim: {sorted(set(constantes) - attendues)}")


def test_les_deux_BORDS_du_parcours_sont_couverts() -> None:
    """Une cible en TETE et une en QUEUE, pas seulement au milieu.

    Un balayage tronque d'un cote laisse tomber un ecran entier sans qu'aucun
    cas ne rougisse : la table etant parcourue dans l'ordre du parcours, ce
    sont `E3-2` et `E3-9` qui disparaitraient les premiers. Ils sont donc
    nommes ici, en propre.
    """
    codes = [code for code, _, _, _ in ECRANS_PROFONDS]
    assert codes[0] == "E3-2", codes
    assert codes[-1] == "E3-9", codes
    # Et les deux bords doivent porter des ecrans DIFFERENTS : une table qui
    # repeterait le meme module aux deux bouts ne mesurerait qu'un ecran.
    assert ECRANS_PROFONDS[0][1] is not ECRANS_PROFONDS[-1][1]
    cardinaux = [len(c) for _, _, _, c in ECRANS_PROFONDS]
    assert len(set(cardinaux)) >= 2, cardinaux


def test_les_quatre_maquettes_EXISTENT_et_portent_bien_un_dessin() -> None:
    """Une maquette absente ou vide rendrait `in texte` faux pour tout.

    Sans cette garde, renommer un fichier de maquette ferait rougir les quatre
    cas sur un message d'appartenance, la ou la cause est un chemin.
    """
    for code, _, maquette, _ in ECRANS_PROFONDS:
        texte = dessin(maquette)
        assert len(texte.splitlines()) >= 20, f"{code}: dessin trop court"
        # Le cadre de la coque : sans lui, ce n'est pas une maquette d'ecran.
        assert "┌" in texte and "└" in texte, code


def test_la_NOTE_de_relecture_est_bien_RETIREE_du_dessin() -> None:
    """La conversation avec Egan n'est pas de l'ecran, et ca se mesure.

    `E3-9` porte en note « Enlever "parcours a part" » et l'arbitrage
    `EPIC11-ARB-28` qui l'a retire. Confondre note et dessin ferait passer
    « parcours a part » pour un libelle CONFORME, alors qu'il est exactement ce
    que l'arbitrage a sorti de l'interface.
    """
    brut = (MAQUETTES / "E3-9-scan-calibrate.txt").read_text(encoding="utf-8")
    assert "EPIC11-ARB-28" in brut, "la note d'arbitrage a disparu de E3-9"
    assert "parcours" in brut
    assert "EPIC11-ARB-28" not in dessin("E3-9-scan-calibrate.txt")
    assert "parcours" not in dessin("E3-9-scan-calibrate.txt"), (
        "« parcours a part » est revenu DANS le dessin: EPIC11-ARB-28 l'a retire")


def test_les_ECARTS_arbitres_restent_des_ecarts() -> None:
    """Le volet symetrique, et il compte autant que la conformite.

    Deux libelles de `E3-9` ne sont PAS ceux du dessin, et c'est voulu :
    `EPIC11-ARB-68` a tranche que « `Tab` nomme sa DESTINATION », donc la
    maquette dit `Tab champ` la ou l'ecran dit `↑↓ champ` (ecart 25 de la
    11.8). Sans cette mesure, un retour silencieux vers le dessin passerait
    pour une correction alors qu'il retournerait l'arbitrage.
    """
    texte = dessin("E3-9-scan-calibrate.txt")
    assert "Tab champ" in texte, "le dessin de E3-9 a change sous l'arbitrage"
    for nom in ("RACCOURCIS_CALIBRATE", "RACCOURCIS_SUR_VALIDER"):
        ligne = getattr(calibrate, nom)
        assert "Tab champ" not in ligne, (
            f"{nom} est revenu a `Tab champ`, ce que EPIC11-ARB-68 a refuse")
        assert "↑↓ champ" in ligne, nom


# ---------------------------------------------------------------------------
# `E3-0`, l'entree du parcours : le seul dessin du Scan qu'aucun banc ne citait
# ---------------------------------------------------------------------------
#
# Les quatre precedents sont confrontes VERBATIM. `E3-0` ne peut pas l'etre au
# meme instrument, et le dire vaut mieux que de l'assouplir en silence : ses
# deux descriptions d'entree sont **repliees sur deux lignes** dans le dessin,
# avec le cadre de la coque au milieu. Une comparaison stricte y rougirait sur
# une mise en forme correcte -- or ce qui doit etre mesure est que rien n'a ete
# REFORMULE, pas que rien n'a ete replie : le repli est le travail de l'ecran.
# C'est le meme raisonnement que `_normalise` de `test_atelier_scan_calibrate_tui`.

from mixed_media_utility.tui import atelier_scan as menu_scan  # noqa: E402

#: Le trait de cadre de la coque, retire avant de replier -- sans quoi une
#: phrase coupee se recolle autour d'un `│` et ne se retrouve jamais.
CADRE = "─│┌┐└┘├┤┬┴┼━┃▏▕"


def dessin_replie(nom: str) -> str:
    """Le dessin, cadre retire et blancs replies -- pour une phrase COUPEE."""
    brut = "".join(" " if c in CADRE else c for c in dessin(nom))
    return " ".join(brut.split())


def replie(texte: str) -> str:
    """Le pendant, cote code : meme normalisation des deux cotes."""
    return " ".join(texte.split())


def test_les_deux_ENTREES_du_menu_Scan_sont_celles_de_E3_0() -> None:
    """`E3-0` n'etait cite par AUCUN banc -- ni verbatim, ni replie.

    Les deux entrees portent chacune un libelle et une description, et la
    description est ce qui dit a l'operateur laquelle des deux prendre. Elle
    derive donc exactement comme un titre, et rien ne le voyait.
    """
    plan = dessin_replie("E3-0-scan-menu.txt")
    entrees = menu_scan.ENTREES_DU_MENU
    assert len(entrees) == 2, entrees
    # Deux entrees DISTINGUABLES, et la cible n'est pas toujours la premiere :
    # les deux sont mesurees, en tete comme en queue.
    assert entrees[0].nom != entrees[-1].nom
    for entree in entrees:
        assert replie(entree.nom) in plan, entree.nom
        assert replie(entree.phrase) in plan, entree.phrase


def test_le_titre_et_le_PIED_de_E3_0_sont_ceux_du_dessin() -> None:
    """Le cartouche et la ligne de raccourcis, que `E3-0` ecrit lui-meme.

    C'est la difference avec `E3-2`, `E3-7` et `E3-8`, dont la ligne de
    raccourcis vient de la coque d'execution partagee et reste donc hors de
    portee de ce banc (entree deposee au `deferred-work.md` plutot
    qu'enterree).
    """
    plan = dessin_replie("E3-0-scan-menu.txt")
    assert replie(menu_scan.TITRE_DU_MENU) in plan
    assert replie(menu_scan.RACCOURCIS_SCAN_MENU) in plan
    assert replie(menu_scan.LIBELLE_DU_PROFIL) in plan


def test_le_repli_ne_rend_pas_la_confrontation_COMPLAISANTE() -> None:
    """Le volet sans lequel le repli serait un assouplissement.

    Replier les blancs fait disparaitre une difference d'indentation, ce qui
    est voulu ; il ne doit PAS faire disparaitre un mot change, un accent perdu
    ou une phrase reformulee. Trois contre-exemples le mesurent.
    """
    plan = dessin_replie("E3-0-scan-menu.txt")
    for faux in ("Detecter des planches",          # accents perdus
                 "Détecter les planches",          # un mot change
                 "Le parcours principal du Scan",  # une phrase rallongee
                 "Déposer des scans et lire les QR"):  # une phrase reformulee
        assert faux not in plan, faux
    # Et le vrai, lui, passe : sans ce volet le test ci-dessus serait vert sur
    # un dessin vide.
    assert "Détecter des planches" in plan


# ---------------------------------------------------------------------------
# La ligne de RACCOURCIS, confrontee SANS ouvrir la coque partagee
# ---------------------------------------------------------------------------
#
# Les trois ecrans profonds n'ecrivent pas leur pied : il vient de la coque
# d'execution partagee, qui est hors du perimetre de ce lot. Ce banc ne l'ouvre
# donc pas -- il en lit la VALEUR, ce qui suffit a confronter et ne demande de
# lire aucune ligne de son source. Une propriete d'ecran se mesure a ce que
# l'ecran rend, pas a la facon dont il l'a compose.

from mixed_media_utility.tui import atelier_pdf_execution as pdf_execution  # noqa: E402
from mixed_media_utility.tui import execution  # noqa: E402


def pied_du_dessin(nom: str) -> str:
    """La ligne de raccourcis d'une maquette : la derniere qui porte `F1 aide`.

    Prise par sa MARQUE et non par son rang : compter les lignes depuis le bas
    casserait au premier dessin qui gagne ou perd une ligne de cadre, et un
    banc qui casse sur une mise en page cesse d'etre lu.
    """
    lignes = [ligne.strip("│ ") for ligne in dessin(nom).splitlines()
              if "F1 aide" in ligne]
    assert len(lignes) == 1, f"{nom}: {len(lignes)} lignes de raccourcis"
    return lignes[0]


def test_le_pied_de_E3_8_est_EXACTEMENT_celui_de_la_maquette() -> None:
    """`E3-8` est conforme, et c'est mesure plutot que suppose.

    Sa relecture porte « NOTE : parfait. -> approbation, rien change », donc
    son pied est liant. Il l'est : la valeur rendue est le dessin, caractere
    pour caractere.
    """
    assert (execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL
            == pied_du_dessin("E3-8-scan-resultat.txt"))
    # Le volet symetrique : la ligne SANS journal doit differer, sans quoi rien
    # n'est contextuel et l'egalite ci-dessus ne dirait rien du bon regime.
    assert execution.RACCOURCIS_RESULTAT != execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL


#: **Ecart FERME le 2026-09-06 par `EPIC11-ARB-246`** (Egan, par invite,
#: verbatim : « Tab journal partout »). Cette place portait un ecart epingle :
#: les deux ecrans « en cours » du Scan rendaient `Tab journal` la ou leurs
#: maquettes -- toutes deux approuvees SANS CHANGEMENT -- portaient
#: `Tab journal complet`, et l'ecran « en cours » de l'atelier PDF rendait,
#: lui, la forme longue. Trois formulations pour un meme geste ; l'arbitrage
#: en garde **une**.
#:
#: **L'epingle est RETOURNEE, pas retiree.** Une frontiere supprimee ne rougit
#: plus jamais, et c'est precisement la reintroduction qu'il faut attraper.
#: Elle mesurait « le dessin porte un mot que le rendu n'a pas » ; elle mesure
#: desormais l'egalite, dans les deux sens, et le jeton unique du produit est
#: tenu par une frontiere negative dans `test_vocabulaire_de_la_tui.py`.
JETON_UNIQUE_DU_JOURNAL = "Tab journal"


@pytest.mark.parametrize("maquette", [
    "E3-2-scan-detection-en-cours.txt",
    "E3-7-scan-ecriture-en-cours.txt",
])
def test_le_pied_des_ecrans_EN_COURS_est_EXACTEMENT_celui_du_dessin(
    maquette: str,
) -> None:
    """L'ecart est ferme, et il ne peut plus se rouvrir sans rougir.

    Les deux maquettes ont ete corrigees **a la source** -- dans leur
    generateur (`EPIC11-ARB-142`), jamais dans le rendu -- et l'egalite
    ci-dessous est ce qui empeche l'une des deux de repartir seule.
    """
    du_dessin = pied_du_dessin(maquette)
    rendu = execution.EcranExecution.raccourcis

    assert du_dessin == rendu, (
        f"{maquette}: le dessin et l'ecran ont redivergé\n"
        f"  dessin: {du_dessin!r}\n  ecran : {rendu!r}")
    # Le volet symetrique, sans lequel l'egalite ci-dessus serait verte le jour
    # ou les DEUX cotes perdraient le jeton : il est bien la, des deux cotes.
    assert JETON_UNIQUE_DU_JOURNAL in du_dessin
    assert JETON_UNIQUE_DU_JOURNAL in rendu
    # Et c'est le jeton COURT : la forme longue est retiree du produit entier.
    assert f"{JETON_UNIQUE_DU_JOURNAL} complet" not in du_dessin
    assert f"{JETON_UNIQUE_DU_JOURNAL} complet" not in rendu


def test_le_MEME_geste_est_libelle_d_UNE_SEULE_facon_dans_le_produit() -> None:
    """Ce qui etait la question produit, et ce qu'`EPIC11-ARB-246` en fait.

    L'ecran « en cours » de l'atelier PDF portait sa propre formulation --
    seul site du code a le faire. Elle vivait, pour le meme geste, a cote de
    celle des quatre autres ecrans « en cours » : « l'une des deux est de
    trop », disait l'epingle. C'est la longue qui part.
    """
    du_pdf = pdf_execution.RACCOURCIS_GENERATION
    du_scan = execution.EcranExecution.raccourcis
    assert du_pdf == du_scan
    assert JETON_UNIQUE_DU_JOURNAL in du_pdf
    assert du_pdf == pied_du_dessin("E3-7-scan-ecriture-en-cours.txt"), (
        "l'ecran PDF rend le pied que la maquette du Scan demande")
