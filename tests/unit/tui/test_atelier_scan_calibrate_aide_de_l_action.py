# -*- coding: utf-8 -*-
"""`F-C1-3` -- l'aide de la ligne d'ACTION de `E3-9`, confrontee a ce que `⏎` FAIT.

**Ce banc et lui seul mesure ce lot.** Aucun autre n'y ecrit, et il n'ecrit
dans aucun autre : la regle de decoupage du depot (« aucun lot ne partage un
fichier de banc avec un autre ») est ce qui rend `git commit -- <chemins>`
protecteur.

## Le defaut, et pourquoi il n'etait mesure nulle part

La ligne `Valider` de `E3-9` parle par **trois** canaux. Deux disaient vrai :

* la valeur de la ligne -- `ACTION_VALIDER`, « lancer la calibration » ;
* la ligne de pied -- `RACCOURCIS_SUR_VALIDER`, « ⏎ calibrer ».

Le troisieme mentait : `AIDE_PAR_CHAMP[CHAMP_VALIDER]` annoncait « **Écrit** le
profil de calibration ». Or `⏎` sur cette ligne appelle
`atelier_scan_parcours.consigner_le_profil`, qui **monte un point de jugement**
et n'ecrit rien -- son propre docstring le dit verbatim (« montrer ce qui va
etre fait, pas ecrire »), et seule l'issue `ISSUE_LANCER` mene a la passe.

L'aide se trompait donc **dans le sens dangereux** : elle niait le point
d'arret qu'`EPIC11-ARB-89` exige, celui-la meme que le cartouche de l'ecran
atteint promet dans son titre (« rien n'est encore écrit »).

**Rien ne confrontait une phrase d'aide a l'action de sa ligne.** Les
frontieres de `test_aide_de_champ.py` mesurent l'APPARIEMENT (chaque phrase a
son champ et a aucun autre) et le BUDGET (la ligne tient dans la fenetre) :
une phrase peut donc etre correctement appariee, tenir dans 76 colonnes, et
promettre l'inverse de ce que la touche fait. C'est le trou que ce banc ferme.

## La forme de la frontiere, et pourquoi elle n'est pas tautologique

Une frontiere qui recopierait la nouvelle phrase ne mesurerait qu'elle-meme --
c'est le banc tautologique que la politique de revue recense (5.9, « la
constante centrale de la calibration »). **Aucun des deux criteres de ce banc
n'est ecrit ici** : les deux sont LUS de l'ecran que `⏎` atteint, et cet ecran
est lui-meme DECOUVERT par une mesure plutot que nomme.

* **le mot interdit** est celui que le cartouche de l'ecran atteint **DEMENT**
  (« rien n'est encore *écrit* »). Une phrase d'aide qui l'affirme contredit,
  mot pour mot, la promesse de l'ecran ou la touche mene. Si ce titre change,
  la frontiere change avec lui ;
* **le mot exige** est un mot du NOM de la classe atteinte, prive de ceux que
  la ligne montre deja (sa valeur et son pied) : l'aide doit nommer le point
  d'arret avec un mot que l'operateur ne lit pas deja sur la ligne. C'est la
  forme mesurable de « l'aide dit ce que la ligne ne montre pas », que le
  docstring de `valeur_de_l_aide` pose comme regle de cet ecran.

**Et ce n'est pas un mot tabou, c'est une PLACE** : le meme radical se lit
legitimement ailleurs sur le meme ecran (`TITRE_DE_LA_SORTIE`, « Ce qui sera
écrit ») et dans la phrase d'aide de la reprise. Le banc le mesure, sans quoi
il interdirait un mot du produit au lieu de le remettre a sa place.

## Ce que ce banc NE mesure PAS, dit plutot que tu

* **il ne couvre qu'`E3-9`.** La regle vaut pour toute ligne d'action de tout
  porteur d'une table d'aide, et sa place naturelle serait
  `tests/unit/tui/test_aide_de_champ.py`, qui parcourt les quatre porteurs.
  Ce fichier appartient a un autre lot au moment ou celui-ci s'ecrit ; le
  raccord est a faire, et il est note dans le rapport du lot ;
* **il ne mesure pas la QUALITE de la phrase**, seulement sa compatibilite
  avec l'action. Une phrase juste mais creuse passerait ici ; c'est
  l'appariement par discriminant (`test_aide_de_champ.py`) qui la refuse ;
* **il ne connait qu'une forme de negation** -- « rien n'est … » --, celle que
  le cartouche emploie. Un titre qui dementirait autrement rendrait
  l'extraction vide, et le banc ROUGIT alors plutot que de mesurer le vide :
  c'est le mode de panne que la politique du depot nomme « une frontiere posee
  sur un ensemble vide ».
"""
from __future__ import annotations

import asyncio
import re
import sys
import unicodedata
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RACINE / "src"))

from mixed_media_utility import scan_calibrate  # noqa: E402
from mixed_media_utility.tui import atelier_scan_calibrate as calib  # noqa: E402
from mixed_media_utility.tui import atelier_scan_parcours  # noqa: E402
from mixed_media_utility.tui.coque import (Contexte, CoqueTui,  # noqa: E402
                                           PalierTemoin)


# ---------------------------------------------------------------------------
# Fabriques -- regle des fabriques du depot
# ---------------------------------------------------------------------------


class _Mesure:
    forme, cardinal, octets, dpi, fichiers = "pdf", 3, 1000, 300.0, 1


class _Source:
    """Une source de scan **a trois pages**, jamais a une seule.

    Regle des fabriques (`CLAUDE.md`) : une fabrique de collection produit au
    moins deux elements distinguables. Une source a une page ne distinguerait
    pas un jalon de son total, et ce banc fait tourner une passe entiere.
    """

    mesure = _Mesure()
    forme, cardinal, dpi, fichiers = "pdf", 3, 300.0, 1
    est_multiple = False

    def __init__(self, chemin: Path) -> None:
        self.chemin = chemin


class _CoeurFeint:
    """Un double au contrat du coeur, **sans `**kwargs`**.

    Le depot l'exige mot pour mot : « il porte la meme signature que le point
    d'entree du coeur, mots-cles compris et **sans `**kwargs`** -- un faux
    permissif laisserait passer un appel dont un mot-cle est mal nomme ». Ici
    ce n'est pas une precaution de style : ce double EST la mesure de « le
    coeur n'a pas ete appele », et un double permissif serait appele par un
    produit qui aurait change de contrat.
    """

    CHAINE = "900-png-cccccccccccc"

    def __init__(self, pages: int = 3) -> None:
        self.pages = pages
        self.appels: list[dict] = []

    def __call__(self, project_dir, scan_path, *, dpi, logger=None,
                 demander_le_nom_et_le_commentaire=None,
                 confirmer_l_ecrasement=None, rappel_progression=None):
        self.appels.append({"dpi": dpi, "scan": scan_path})
        for faites in range(1, self.pages + 1):
            if rappel_progression is not None:
                rappel_progression(faites, self.pages)
        if demander_le_nom_et_le_commentaire is not None:
            demander_le_nom_et_le_commentaire(self.CHAINE)
        chemin = Path(project_dir) / "versions" / "calibration" / "p.json"
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text("{}", encoding="utf-8")
        return scan_calibrate.ProfilDeChaineConsigne(
            profile_path=chemin, chain_id=self.CHAINE, etiquette="beta",
            commentaire="", lot_correction=None, document={})


def _coque(*ecrans, ascii_seul: bool = False) -> CoqueTui:
    return CoqueTui([PalierTemoin("Projet", "Q quitter"),
                     PalierTemoin("Ateliers", "Q quitter"), *ecrans],
                    Contexte(projet="projet_demo", palier="Scan"),
                    ascii_seul=ascii_seul)


def _parcours(app, tmp_path: Path, feinte):
    projet = tmp_path / "projet"
    projet.mkdir(parents=True, exist_ok=True)
    return atelier_scan_parcours.ParcoursScan(app, projet, calibration=feinte)


def _rendre_la_passe_possible(ecran, tmp_path: Path) -> None:
    """Ce qui fait passer la ligne d'action de « scan requis » a « pret »."""
    ecran.formulaire.poser_le_scan(_Source(tmp_path / "mire.pdf"))
    ecran.formulaire.dpi = "300"
    assert ecran.formulaire.peut_calibrer, "la ligne d'action doit pouvoir partir"


async def _tant_que(pilote, condition, tours: int = 600) -> bool:
    for _ in range(tours):
        if condition():
            return True
        await pilote.pause()
        await asyncio.sleep(0.005)
    return False


# ---------------------------------------------------------------------------
# Le vocabulaire, lu du produit et jamais recopie
# ---------------------------------------------------------------------------

#: La forme de negation que le cartouche d'un point de jugement emploie pour
#: promettre qu'il n'a rien fait -- « rien n'est encore écrit ».
#:
#: **Une seule forme, et le banc rougit si elle ne se lit pas** : mesurer sur
#: une extraction vide serait une frontiere posee sur un ensemble vide, et la
#: politique du depot en fait un mode de panne nomme.
NEGATION_DU_CARTOUCHE = re.compile(
    r"\brien\s+n['’]est\s+(?:encore\s+)?(\w+)", re.IGNORECASE)

#: Les mots du nom d'une classe d'ecran qui ne disent rien de CET ecran-la.
#: `Ecran` est le prefixe de toutes les classes du paquet : l'exiger dans une
#: phrase d'aide n'exigerait rien.
MOTS_SANS_PORTEE = frozenset({"ecran"})

#: Longueur minimale d'un mot retenu du nom d'une classe. Elle ecarte les
#: liaisons (`A`, `De`, `La`), qui ne portent pas de sens a citer.
LONGUEUR_D_UN_MOT_PORTEUR = 5


def sans_accents(texte: str) -> str:
    """Le texte replie, pour que « Écrit » et « écrire » se comparent.

    **Pas `jetons.replier_ascii`** : celui-la replie les GLYPHES pour un
    terminal pauvre, ce qui est un autre besoin et pourrait cesser de replier
    les accents sans que ce banc ait tort.
    """
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose
                   if not unicodedata.combining(c)).casefold()


def radical_dementi(titre: str) -> str:
    """Le radical du mot que ce cartouche DEMENT, ou `""` s'il n'en dement aucun.

    **Un radical et non un mot** : « écrit », « écrire », « écriture » et
    « écrits » sont la meme promesse, et une aide qui dirait « écrire » la ou
    le cartouche dit « écrit » echapperait a une comparaison mot a mot. La
    derniere lettre suffit a couvrir la famille sans mordre au-dela -- retirer
    deux lettres rendrait `ecr`, qui se lit dans « écran ».
    """
    trouve = NEGATION_DU_CARTOUCHE.search(titre)
    if trouve is None:
        return ""
    mot = sans_accents(trouve.group(1))
    return mot[:-1] if len(mot) >= 4 else mot


def mots_du_nom(nom_de_classe: str) -> set[str]:
    """Les mots porteurs du nom d'une classe d'ecran, replies.

    `EcranCalibrationAConfirmer` rend `{calibration, confirmer}` : le prefixe
    commun et les liaisons sont ecartes, parce qu'ils ne distinguent pas cet
    ecran d'un autre.
    """
    mots = re.findall(r"[A-Z][a-zÀ-ſ]+", nom_de_classe)
    replies = {sans_accents(mot) for mot in mots
               if len(mot) >= LONGUEUR_D_UN_MOT_PORTEUR}
    return replies - MOTS_SANS_PORTEE


def mots_de(texte: str) -> set[str]:
    """Les mots d'un texte de l'interface, replies -- glyphes et touches exclus."""
    return {sans_accents(mot) for mot in re.findall(r"\w+", texte)}


def ecarts_de_l_aide(phrase: str, *, titre_atteint: str,
                     classe_atteinte: str, deja_sur_la_ligne: str) -> list:
    """Les ecarts entre une phrase d'aide de ligne d'ACTION et l'ecran atteint.

    Vide quand la phrase est compatible avec ce que `⏎` fait. **Factorise pour
    que la MORSURE joue exactement la meme mesure** : une frontiere dont le
    contre-exemple emprunte un autre chemin ne prouve rien de la frontiere --
    c'est la forme qu'`ecarts_d_appariement` a deja dans le banc voisin.
    """
    repliee = sans_accents(phrase)
    ecarts = []

    radical = radical_dementi(titre_atteint)
    if radical and radical in repliee:
        # L'aide AFFIRME ce que l'ecran atteint DEMENT : c'est le finding.
        ecarts.append(("dement", radical, phrase))

    candidats = mots_du_nom(classe_atteinte) - mots_de(deja_sur_la_ligne)
    if candidats and not any(mot in repliee for mot in candidats):
        # L'aide ne nomme pas le point d'arret ou la touche mene, avec aucun
        # des mots que la ligne ne montre pas deja.
        ecarts.append(("innomme", tuple(sorted(candidats)), phrase))
    return ecarts


# ---------------------------------------------------------------------------
# La mesure : ou `⏎` mene VRAIMENT, sur la ligne d'action
# ---------------------------------------------------------------------------


def lignes_qui_SORTENT_du_formulaire(tmp_path: Path, banc) -> set[str]:
    """Les lignes dont `⏎` appelle le rappel injecte -- **decouvertes**.

    Le banc ne NOMME pas la ligne d'action : il la trouve. Un mutant qui
    deplacerait l'action sur une autre ligne deplacerait la mesure avec lui,
    au lieu de la laisser pointer une ligne devenue inerte.
    """
    lances: list[str] = []
    ecran = calib.EcranCalibrerLaChaine(
        tmp_path, calibrer=lambda formulaire: lances.append(formulaire.champ))
    _rendre_la_passe_possible(ecran, tmp_path)

    async def scenario(_pilote):
        sortantes = set()
        for cle in ecran.formulaire.champs():
            # **La zone est REMISE a chaque tour** : `⏎` sur le champ du scan
            # ouvre l'explorateur, et toutes les touches suivantes partiraient
            # dans CETTE zone -- aucune n'atteindrait plus le formulaire.
            ecran.zone = calib.ZONE_FORMULAIRE
            ecran.formulaire.champ = cle
            avant = len(lances)
            ecran.traiter("enter")
            if len(lances) > avant:
                sortantes.add(cle)
        return sortantes

    return banc(_coque(ecran), scenario)


def ce_que_ENTREE_atteint(tmp_path: Path, banc, *, jusqu_au_lancement: bool):
    """Ce que `⏎` sur la ligne d'action atteint, **par le cablage de production**.

    L'ecran est monte par `ParcoursScan.calibrer_la_chaine`, c'est-a-dire par
    le chemin que le menu de l'atelier emprunte : rien n'est cable a la main
    ici, et un banc qui fournirait lui-meme le rappel qu'il pretend mesurer ne
    mesurerait que son propre cablage (defaut deja paye sur ce paquet).

    ``jusqu_au_lancement`` fait retenir l'issue `ISSUE_LANCER` sur l'ecran
    atteint. C'est le volet SYMETRIQUE, et il est ce qui rend la mesure
    honnete : sans lui, « le coeur n'est pas appele » serait vert sur un
    produit ou le coeur n'est jamais appele du tout.
    """
    feinte = _CoeurFeint()
    app = _coque()
    parcours = _parcours(app, tmp_path, feinte)
    action = None

    async def scenario(pilote):
        nonlocal action
        ecran = parcours.calibrer_la_chaine()
        await pilote.pause()
        _rendre_la_passe_possible(ecran, tmp_path)
        action = ecran.formulaire.champs()[-1]
        ecran.zone = calib.ZONE_FORMULAIRE
        ecran.formulaire.champ = action
        ecran.traiter("enter")
        await pilote.pause()

        atteint = pilote.app.screen
        vu = {
            "classe": type(atteint).__name__,
            "titre": getattr(getattr(atteint, "panneau", None), "titre", ""),
            "appels_avant_l_issue": len(feinte.appels),
            "ecrit_sur_le_disque": sorted(
                p.name for p in
                (parcours.dossier_projet / "versions" / "calibration").glob("*")
            ) if (parcours.dossier_projet / "versions"
                  / "calibration").exists() else [],
        }
        if jusqu_au_lancement:
            atteint.choix.viser(calib.ISSUE_LANCER)
            atteint.valider()
            await _tant_que(pilote, lambda: not pilote.app.tache_en_cours)
            await pilote.pause()
            vu["appels_apres_l_issue"] = len(feinte.appels)
        return vu

    mesure = banc(app, scenario)
    mesure["action"] = action
    return mesure


# ===========================================================================
# Volet A -- ce que `⏎` FAIT, mesure
# ===========================================================================


def test_UNE_SEULE_ligne_du_formulaire_SORT_vers_l_action(tmp_path, banc):
    """L'ensemble des lignes qui sortent du formulaire est mesure **exactement**.

    « La ligne d'action est celle-ci » serait vert sur un formulaire ou toutes
    les lignes lanceraient -- c'est-a-dire sur le defaut qu'`EPIC11-ARB-158`
    a fait fermer (« ⏎ lancait la calibration depuis n'importe quel champ »).
    Et c'est cet ensemble-la, decouvert, que les volets suivants confrontent.
    """
    sortantes = lignes_qui_SORTENT_du_formulaire(tmp_path, banc)
    assert sortantes == {calib.CHAMP_VALIDER}, sortantes


def test_ENTREE_sur_la_ligne_d_action_MONTE_un_point_de_jugement_SANS_ecrire(
        tmp_path, banc):
    """Le fait dont toute la suite depend : `⏎` **montre**, il n'ecrit pas.

    Trois mesures, et aucune n'est redondante :

    * l'ecran atteint est le point de jugement, par IDENTITE de classe ;
    * le coeur n'a **pas** ete appele -- c'est le double qui le dit, pas une
      lecture d'attribut prive ;
    * **rien n'est sur le disque** : un produit qui ecrirait sans passer par le
      point d'entree du coeur passerait les deux premieres.
    """
    vu = ce_que_ENTREE_atteint(tmp_path, banc, jusqu_au_lancement=False)
    assert vu["action"] == calib.CHAMP_VALIDER, vu
    assert vu["classe"] == calib.EcranCalibrationAConfirmer.__name__, vu
    assert vu["appels_avant_l_issue"] == 0, vu
    assert vu["ecrit_sur_le_disque"] == [], vu


def test_le_coeur_n_est_atteint_qu_APRES_l_issue_de_la_confirmation(
        tmp_path, banc):
    """**Le volet symetrique, et il est ce qui rend le precedent honnete.**

    « Le coeur n'est pas appele » serait vert sur un produit ou il ne l'est
    jamais. Ici il l'est -- une fois, et seulement apres `ISSUE_LANCER`. C'est
    aussi ce qui etablit que l'ancienne phrase ne se trompait pas de VERBE mais
    de MOMENT : l'ecriture existe, elle arrive plus loin, apres un point
    d'arret volontaire (`EPIC11-ARB-89`).
    """
    vu = ce_que_ENTREE_atteint(tmp_path, banc, jusqu_au_lancement=True)
    assert vu["appels_avant_l_issue"] == 0, vu
    assert vu["appels_apres_l_issue"] == 1, vu


# ===========================================================================
# Volet B -- la phrase d'aide, confrontee a cet ecran-la
# ===========================================================================


def test_l_aide_de_la_ligne_d_action_NE_PROMET_PAS_ce_que_l_ecran_atteint_DEMENT(
        tmp_path, banc):
    """La frontiere, et ses deux gardes d'anti-vacuite.

    Le mot interdit n'est pas ecrit ici : il est **lu du cartouche** de l'ecran
    que `⏎` atteint, qui promet « rien n'est encore … ». Les deux gardes :

    * l'extraction rend quelque chose -- sinon la frontiere mesurerait le vide
      et serait verte sur n'importe quelle phrase ;
    * le meme radical se lit **ailleurs** sur cet ecran (`TITRE_DE_LA_SORTIE`,
      « Ce qui sera écrit »). Ce n'est donc pas un mot tabou du produit, c'est
      une place : l'ecriture se dit la ou elle a lieu.
    """
    vu = ce_que_ENTREE_atteint(tmp_path, banc, jusqu_au_lancement=False)
    radical = radical_dementi(vu["titre"])
    assert radical, (
        "le cartouche de l'ecran atteint ne dement plus rien : la frontiere "
        f"mesurerait le vide (titre lu : {vu['titre']!r})")
    assert radical in sans_accents(calib.TITRE_DE_LA_SORTIE), (
        radical, calib.TITRE_DE_LA_SORTIE)

    phrase = calib.AIDE_PAR_CHAMP[vu["action"]]
    assert radical not in sans_accents(phrase), (radical, phrase)


def test_l_aide_de_la_ligne_d_action_NOMME_l_ecran_ou_la_touche_mene(
        tmp_path, banc):
    """Le volet positif : ne pas mentir ne suffit pas, il faut dire ou l'on va.

    Le mot exige est lu du **nom de la classe atteinte**, prive des mots que la
    ligne montre deja (sa valeur et son pied) : l'aide doit apporter ce que
    l'operateur ne lit pas encore, ce qui est la regle de cet ecran -- le
    docstring de `valeur_de_l_aide` : « elle dit ce que la ligne du champ ne
    montre pas ».

    Sans ce volet, une aide muette (« Cette ligne. ») passerait la frontiere
    negative sans rien dire du point d'arret.
    """
    vu = ce_que_ENTREE_atteint(tmp_path, banc, jusqu_au_lancement=False)
    deja = f"{calib.ACTION_VALIDER} {calib.RACCOURCIS_SUR_VALIDER}"
    candidats = mots_du_nom(vu["classe"]) - mots_de(deja)
    assert candidats, (
        "le nom de l'ecran atteint n'apporte aucun mot que la ligne ne montre "
        f"deja : la frontiere mesurerait le vide ({vu['classe']!r})")

    phrase = sans_accents(calib.AIDE_PAR_CHAMP[vu["action"]])
    assert [mot for mot in candidats if mot in phrase], (candidats, phrase)


def test_la_phrase_LIVREE_ne_porte_AUCUN_ecart(tmp_path, banc):
    """Les deux volets rejoues par la **fonction que la morsure emploie**.

    Deux mesures pour un seul interdit divergeraient, et c'est le volet non
    couvert par le plus strict des deux qui passerait. La morsure ci-dessous
    joue donc exactement cette fonction-la.
    """
    vu = ce_que_ENTREE_atteint(tmp_path, banc, jusqu_au_lancement=False)
    deja = f"{calib.ACTION_VALIDER} {calib.RACCOURCIS_SUR_VALIDER}"
    assert ecarts_de_l_aide(
        calib.AIDE_PAR_CHAMP[vu["action"]], titre_atteint=vu["titre"],
        classe_atteinte=vu["classe"], deja_sur_la_ligne=deja) == []


# ===========================================================================
# Volet C -- la MORSURE : les phrases qui doivent faire rougir
# ===========================================================================

#: **Les phrases fautives, et la premiere est l'ancienne, verbatim.**
#: « Une fermeture ne vaut que si le mutant reinjecte fait rougir le test qui
#: la porte » : elle est donc rejouee ici, en plus de l'avoir ete a la main
#: dans le module de produit.
#:
#: Les quatre couvrent les deux modes de panne et leurs bords :
#: l'ecriture affirmee au present, a l'infinitif et au substantif (le radical
#: doit couvrir la famille), et la phrase creuse qui ne ment pas mais ne dit
#: rien du point d'arret.
PHRASES_FAUTIVES = [
    pytest.param("Écrit le profil de calibration ; ici : {valeur}.",
                 ["dement", "innomme"], id="ancienne-phrase"),
    pytest.param("Va écrire le profil, à confirmer ; ici : {valeur}.",
                 ["dement"], id="infinitif"),
    pytest.param("Lance l'écriture, à confirmer ; ici : {valeur}.",
                 ["dement"], id="substantif"),
    pytest.param("Lance la calibration ; ici : {valeur}.",
                 ["innomme"], id="creuse-mais-vraie"),
]


@pytest.mark.parametrize("phrase,attendus", PHRASES_FAUTIVES)
def test_la_frontiere_MORD_sur_une_aide_qui_annonce_une_ecriture(
        tmp_path, banc, phrase, attendus):
    """La morsure, sur la mesure REELLE de l'ecran atteint.

    Le contre-exemple n'est pas confronte a un titre ecrit dans le banc : il
    passe par la meme mesure montee que la phrase livree. Une morsure jouee
    sur une constante recopiee prouverait la constante, pas la frontiere.
    """
    vu = ce_que_ENTREE_atteint(tmp_path, banc, jusqu_au_lancement=False)
    deja = f"{calib.ACTION_VALIDER} {calib.RACCOURCIS_SUR_VALIDER}"
    ecarts = ecarts_de_l_aide(phrase, titre_atteint=vu["titre"],
                              classe_atteinte=vu["classe"],
                              deja_sur_la_ligne=deja)
    assert sorted(nom for nom, _, _ in ecarts) == sorted(attendus), ecarts


def test_la_morsure_passe_par_la_TABLE_du_produit_et_pas_par_un_argument(
        tmp_path, banc, monkeypatch):
    """Et la meme morsure **dans la table**, la ou le defaut a vecu.

    Une frontiere qui ne saurait juger qu'un argument passe a la main ne
    verrait jamais revenir la phrase dans `AIDE_PAR_CHAMP` -- c'est-a-dire le
    seul endroit ou le defaut peut renaitre. Le mutant est donc pose dans la
    table du module, et la mesure relue depuis elle.
    """
    vu = ce_que_ENTREE_atteint(tmp_path, banc, jusqu_au_lancement=False)
    monkeypatch.setitem(calib.AIDE_PAR_CHAMP, vu["action"],
                        "Écrit le profil de calibration ; ici : {valeur}.")
    deja = f"{calib.ACTION_VALIDER} {calib.RACCOURCIS_SUR_VALIDER}"
    assert ecarts_de_l_aide(
        calib.AIDE_PAR_CHAMP[vu["action"]], titre_atteint=vu["titre"],
        classe_atteinte=vu["classe"], deja_sur_la_ligne=deja) != []


def test_le_radical_couvre_la_FAMILLE_du_mot_et_pas_ses_HOMONYMES(tmp_path,
                                                                  banc):
    """La borne du radical, mesuree des deux cotes.

    Retirer une lettre couvre « écrit », « écrire », « écriture » ; en retirer
    deux rendrait `ecr`, qui se lit dans « écran » et ferait rougir une aide
    parfaitement honnete. La borne est donc un choix, et un choix mesure.
    """
    vu = ce_que_ENTREE_atteint(tmp_path, banc, jusqu_au_lancement=False)
    radical = radical_dementi(vu["titre"])
    for mot in ("Écrit", "écrire", "écriture", "écrits"):
        assert radical in sans_accents(mot), (radical, mot)
    for etranger in ("écran", "écarte", "échap"):
        assert radical not in sans_accents(etranger), (radical, etranger)


def test_l_extraction_de_la_NEGATION_ne_rend_rien_sur_un_titre_qui_n_en_porte_pas():
    """Le volet qui rend la garde d'anti-vacuite credible.

    Si `radical_dementi` rendait toujours quelque chose, l'assertion « le
    cartouche dement encore quelque chose » serait decorative.
    """
    assert radical_dementi("Ce qui va être fait") == ""
    assert radical_dementi("") == ""
    assert radical_dementi("Ce qui va être fait — rien n'est encore écrit")
