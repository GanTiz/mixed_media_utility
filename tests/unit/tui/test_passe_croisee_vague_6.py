# -*- coding: utf-8 -*-
"""Passe croisee de la VAGUE 6 -- 11.8 (atelier Exports) contre 11.9 (manuel).

**Pourquoi ce banc existe, et pourquoi il ne pouvait pas exister avant.** Les
deux stories de la vague 6 ont ete developpees en parallele et revues
**separement** : la 11.8 le 2026-09-03 au matin, la 11.9 le soir. La politique
du depot fait pourtant de la VAGUE l'unite de revue sur l'Epic 11 (AC 6.2 de la
11.9). Ce qu'une revue par story ne peut pas voir est une **couture** : ce que
l'une livre et que l'autre contredit sans que ni `git` ni un banc de
comportement ne le voie.

Les deux revues etaient structurellement aveugles a ce qui suit, chacune pour
sa propre raison :

* **la 11.8 a ete revue avant que le manuel n'existe.** Ses quinze lignes de
  raccourcis neuves n'etaient lues par personne : un pied d'ecran ne se
  confronte a rien. Depuis la 11.9 elles sont **derivees** dans un manuel de
  reference, ou elles se retrouvent cote a cote avec celles des treize autres
  formulaires du paquet ;
* **la 11.9 a ete revue sur quatre modules produit et sept bancs**, dont aucun
  n'est un module `atelier_exports_*`. Ses trois couches ont mesure le
  MECANISME de la derivation ; aucune n'a lu ce que la story soeur y verse.

**Ce que ce banc mesure, et c'est une question de COUTURE, pas de contenu.**
Trois frontieres, toutes bornees **en egalite** plutot qu'en inclusion : un
ecart de plus fait rougir, et une unification faite sans mettre le registre a
jour aussi. Aucune ne corrige : le choix du mot appartient a Egan
(voir `deferred-work.md`).

**Ce que ce banc NE mesure PAS, dit plutot que tu.** Il ne rejoue ni les
couches 1 et 2 de la 11.8 -- elles sont payees -- ni celles de la 11.9. Il ne
mesure pas le coeur de la 11.8 (`encode.py`, `codec_profiles.py`), qui n'a
aucune surface commune avec la 11.9. Et il ne dit rien des pages 2 et 3 de la
maquette `T1-2`, qui ne sont pas dessinees.
"""
from __future__ import annotations

import ast
import dataclasses
import importlib
import inspect
import pkgutil
import types
from pathlib import Path

import pytest

from mixed_media_utility.tui import ecran_manuel, manuel

#: Les deux regimes. La derivation ne peint pas, mais le volet du manuel
#: ci-dessous rend des lignes : les deux y sont joues.
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

_RACINE = Path(__file__).resolve().parents[3]
_PAQUET = _RACINE / "src" / "mixed_media_utility" / "tui"


# ===========================================================================
# C1 -- le VOCABULAIRE d'une meme touche, releve des deux cotes de la vague
# ===========================================================================

def couples_divergents(lignes: dict[str, str]) -> dict[tuple[str, str, str],
                                                       tuple[frozenset,
                                                             frozenset]]:
    """Les couples de libelles d'un MEME ouvreur dont l'un prolonge l'autre.

    « Prolonge » et non « differe » : `Échap retour` et `Échap ateliers` sont
    deux actions differentes sur deux ecrans differents, et le manuel a raison
    de rendre les deux. `Tab champ` et `Tab champ suivant` sont **la meme
    action nommee deux fois** -- c'est ce que la relation de prefixe de MOTS
    attrape, et elle seule : elle ne se declenche pas sur deux libelles
    etrangers l'un a l'autre.

    Rend, pour chaque triplet `(ouvreur, court, long)`, les deux ensembles de
    cles qui les annoncent. La fonction prend son dictionnaire **en argument**
    plutot que d'appeler le balayage : c'est ce qui permet de la mesurer sur une
    fabrique, donc de tenir le volet de morsure et les cibles de bord.
    """
    par_ouvreur: dict[str, dict[str, set[str]]] = {}
    for cle, ligne in lignes.items():
        for ouvreur, libelle in manuel.items_d_une_ligne(ligne):
            par_ouvreur.setdefault(ouvreur, {}).setdefault(libelle,
                                                           set()).add(cle)
    divergents = {}
    for ouvreur, libelles in par_ouvreur.items():
        for court in libelles:
            for long in libelles:
                if long == court:
                    continue
                if long.split()[:len(court.split())] == court.split():
                    divergents[(ouvreur, court, long)] = (
                        frozenset(libelles[court]), frozenset(libelles[long]))
    return divergents


#: **Le registre des divergences de vocabulaire, borne en EGALITE.**
#:
#: Chaque entree est un ouvreur que le paquet annonce avec deux mots dont l'un
#: prolonge l'autre, avec l'origine mesuree de la divergence. Ajouter un
#: quinzieme formulaire qui dirait `Tab champ suivant` fait rougir ; unifier le
#: vocabulaire sans retirer la ligne d'ici fait rougir aussi.
#:
#: Les trois dernieres sont **anterieures a la vague 6** et sont ici pour la
#: meme raison qu'un ensemble se borne en egalite : les taire ferait de la
#: mesure une inclusion, qui est verte le jour ou elle ne voit plus rien.
DIVERGENCES_CONNUES = {
    # Vague 6, cote 11.8 : le quatorzieme formulaire du paquet est le seul a
    # dire `champ suivant`. Les treize autres -- dont les TROIS que la 11.9
    # enrole dans son aide de champ le meme jour -- disent `champ`.
    ("Tab", "champ", "champ suivant"),
    # Anterieures a la vague 6, mesurees ici pour borner l'ensemble.
    #
    # **`("Tab", "journal", "journal complet")` est TOMBEE le 2026-09-06**
    # (`EPIC11-ARB-246`, Egan par invite : « Tab journal partout »). Elle est
    # retiree de ce registre parce qu'il est borne en EGALITE : une divergence
    # fermee qui y resterait ferait rougir, et c'est exactement ce qu'on
    # attend d'un registre borne ainsi. Le jeton unique n'est pas tenu ici --
    # il l'est par la frontiere negative de `test_vocabulaire_de_la_tui.py`,
    # qui, elle, attrape la REINTRODUCTION de la forme longue.
    ("Échap", "reprendre", "reprendre les cadences"),
    ("⏎", "choisir", "choisir quoi extraire"),
    ("⏎", "ouvrir", "ouvrir la fenêtre"),
}


def test_l_ensemble_des_DIVERGENCES_de_vocabulaire_du_paquet_est_EXACTEMENT_celui_la():
    """La frontiere d'identite : ni une de plus, ni une de moins.

    **Une assertion positive ne suffirait pas** : « le paquet dit bien
    `Tab champ suivant` quelque part » resterait vraie le jour ou un quinzieme
    ecran l'ecrirait aussi, et c'est exactement la dispersion qu'on cherche a
    empecher. C'est la meme forme que
    `test_arb140_passages_sans_q_quitter.py::test_l_ensemble_des_PASSAGES_...`,
    livre par la 11.8.
    """
    mesure = set(couples_divergents(manuel.lignes_de_raccourcis_du_paquet()))
    assert mesure == DIVERGENCES_CONNUES, sorted(mesure ^ DIVERGENCES_CONNUES)


def test_les_TROIS_sites_de_Tab_champ_suivant_sont_TOUS_du_module_de_la_11_8():
    """L'origine de la divergence de la vague 6, mesuree et non supposee.

    `atelier_exports_reglages` est livre par la story 11.8 le 2026-09-03 ; les
    treize sites de `Tab champ` couvrent cinq modules livres avant elle, dont
    **les trois formulaires que la 11.9 enrole dans son aide de champ le meme
    jour** (`atelier_scan`, `atelier_pdf_calibration`,
    `atelier_scan_completion`). La divergence est donc bien une couture de
    vague : un mot neuf pose d'un cote pendant que l'autre cote generalisait le
    mecanisme qui le rendrait visible.
    """
    lignes = manuel.lignes_de_raccourcis_du_paquet()
    courts, longs = couples_divergents(lignes)[("Tab", "champ",
                                                "champ suivant")]
    prefixe = "mixed_media_utility.tui."
    modules_longs = {cle[len(prefixe):].split(".")[0] for cle in longs}
    modules_courts = {cle[len(prefixe):].split(".")[0] for cle in courts}
    assert modules_longs == {"atelier_exports_reglages"}, sorted(modules_longs)
    assert len(longs) == 3, sorted(longs)
    # Le volet symetrique : le mot court n'est pas une curiosite d'un module,
    # c'est la convention du paquet. Sans lui, la mesure ci-dessus serait vraie
    # meme si `champ` n'existait qu'une fois.
    assert len(modules_courts) >= 5, sorted(modules_courts)
    assert {"atelier_scan", "atelier_pdf_calibration",
            "atelier_scan_completion"} <= modules_courts, sorted(modules_courts)


def test_F1_est_annonce_avec_DEUX_mots_et_l_ensemble_de_chacun_est_BORNE():
    """`F1` : la 11.9 lui donne un second SENS sans unifier son MOT.

    Avant la 11.9, `F1 aide` etait une promesse non tenue (finding `I8` de la
    11.8 : « promis par trente-neuf maquettes [...] et implemente NULLE PART »).
    La 11.9 la tient, et lui donne deux etages : l'aide de CHAMP sur les quatre
    ecrans porteurs d'une table, le MANUEL partout ailleurs. Le paquet continue
    pourtant de nommer la touche de deux facons, et la 11.8 a estampille
    `F1 aide` sur quatorze sites neufs pendant la meme vague.

    L'ecart est **borne en egalite**, comme le reste de ce fichier : il ne se
    tranche pas ici. Ce que la mesure etablit, c'est que les deux mots ne se
    repartissent PAS selon les deux etages -- trois des quatre ecrans porteurs
    d'une table d'aide disent `aide` comme les quatre-vingt-quatre autres.
    """
    from mixed_media_utility.tui import aide_de_champ

    lignes = manuel.lignes_de_raccourcis_du_paquet()
    mots: dict[str, set[str]] = {}
    for cle, ligne in lignes.items():
        for ouvreur, libelle in manuel.items_d_une_ligne(ligne):
            if ouvreur == "F1":
                mots.setdefault(libelle, set()).add(cle)
    assert set(mots) == {"aide", "où lire ce champ"}, sorted(mots)

    prefixe = "mixed_media_utility.tui."
    disant_le_second = {cle[len(prefixe):].split(".")[0]
                        for cle in mots["où lire ce champ"]}
    assert disant_le_second == {"atelier_scan_completion"}, sorted(
        disant_le_second)

    # Le point qui fait de ceci une couture et non une coquetterie : le mot ne
    # suit pas l'etage. Trois des quatre porteurs d'une table d'aide annoncent
    # le mot generique.
    porteurs = {nom.rsplit(".", 1)[0][len(prefixe):]
                for nom in aide_de_champ.ecrans_porteurs_d_une_table_d_aide()}
    assert len(porteurs) == 4, sorted(porteurs)
    assert len(porteurs - disant_le_second) == 3, sorted(porteurs)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_MANUEL_rend_les_DEUX_mots_sur_UNE_SEULE_ligne(ascii_seul):
    """La consequence visible par l'operateur, dans les deux regimes.

    C'est ce qui fait de la divergence un defaut de produit et non une affaire
    de style : le manuel de la 11.9 range les deux mots sous **un seul**
    ouvreur, separes par le meme point median que deux actions distinctes. Un
    operateur y lit `Tab   ... champ · champ suivant ...` sans qu'aucune
    surface ne lui dise que ce sont deux noms d'un seul geste.
    """
    from mixed_media_utility.tui import jetons

    def attendu(texte: str) -> str:
        """Le mot tel que le regime le rend -- replie en `--ascii`.

        Recopier `ou lire ce champ` pour le regime de repli serait une seconde
        redaction, qui divergerait au premier accent change : on interroge le
        replieur, comme le fait `test_repli_ascii.py`.
        """
        return jetons.replier_ascii(texte) if ascii_seul else texte

    rendu = "\n".join(ligne
                      for page in ecran_manuel.pages_du_manuel(None, 80,
                                                               ascii_seul)
                      for ligne in page.lignes)
    for ouvreur, court, long in (("Tab", "champ", "champ suivant"),
                                 ("F1", "aide", "où lire ce champ")):
        assert attendu(court) in rendu, (ouvreur, court)
        assert attendu(long) in rendu, (ouvreur, long)
    # Le volet qui empeche la mesure d'etre vraie par hasard : les deux mots de
    # `F1` sont sur la MEME ligne, celle de l'ouvreur.
    lignes_de_f1 = [ligne for ligne in rendu.splitlines()
                    if ligne.strip().startswith("F1")]
    assert len(lignes_de_f1) == 1, lignes_de_f1
    assert "aide" in lignes_de_f1[0]
    assert attendu("où lire ce champ") in lignes_de_f1[0], lignes_de_f1[0]


# --- les volets de morsure et les cibles de bord de C1 ---------------------

#: Une fabrique a TROIS lignes distinguables, pour poser la cible ailleurs
#: qu'en premiere position. Les valeurs different -- un remplissage uniforme
#: rendrait toute permutation invisible (`CLAUDE.md`, regle des fabriques).
def _fabrique(place_de_la_cible: int) -> dict[str, str]:
    """Trois lignes temoins, la divergente posee au rang demande.

    Rang 0 = en tete, 1 = au milieu, 2 = en queue -- les trois positions que
    la regle des fabriques exige depuis le 2026-09-03.
    """
    ordinaires = ["Zz premier  Ww un mot",
                  "Yy second  Vv deux mots"]
    cible = "Tt champ suivant  Ss cible"
    lignes = list(ordinaires)
    lignes.insert(place_de_la_cible, cible)
    lignes.append("Tt champ  Rr le mot court")
    return {f"module_temoin_{rang}.RACCOURCIS_TEMOIN": ligne
            for rang, ligne in enumerate(lignes)}


@pytest.mark.parametrize("place", [0, 1, 2], ids=["tete", "milieu", "queue"])
def test_la_mesure_des_DIVERGENCES_MORD_ou_que_soit_la_cible(place):
    """Le volet de morsure, cible au milieu ET AUX DEUX BORDS.

    Une mesure qui ne verrait la divergence qu'en premiere position serait
    verte sur un paquet ou elle arrive en queue -- et le paquet reel range
    `atelier_exports_reglages` au milieu de ses quarante-cinq modules. C'est le
    mutant de bord paye par le lot A de la 11.11 (`CLAUDE.md`, point 4 de la
    regle des fabriques).
    """
    mesure = couples_divergents(_fabrique(place))
    assert ("Tt", "champ", "champ suivant") in mesure, sorted(mesure)


def test_la_mesure_des_DIVERGENCES_NE_MORD_PAS_sur_deux_libelles_ETRANGERS():
    """Le volet symetrique : sans lui, la mesure serait vraie de tout.

    Deux actions differentes sur deux ecrans differents ne sont pas une
    divergence de vocabulaire, et une mesure qui les confondrait rendrait le
    registre ci-dessus ininterpretable -- le paquet annonce quinze libelles
    pour `Échap`.
    """
    mesure = couples_divergents({
        "a.RACCOURCIS_A": "Échap retour  Tt cible",
        "b.RACCOURCIS_B": "Échap ateliers  Tt cible",
    })
    assert mesure == {}, sorted(mesure)


# ===========================================================================
# C2 -- une constante IMPORTEE est attribuee au module IMPORTATEUR
# ===========================================================================

def constantes_definies_par_module() -> dict[str, set[str]]:
    """Les `RACCOURCIS_*` que chaque module du paquet DEFINIT, lues a l'AST.

    A l'AST et non a l'execution : `inspect.getmembers` est precisement ce qui
    ne sait pas distinguer une definition d'un import, et c'est l'ecart entre
    les deux lectures que la mesure ci-dessous porte.
    """
    definies: dict[str, set[str]] = {}
    for fichier in sorted(_PAQUET.glob("*.py")):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        noms = set()
        for noeud in arbre.body:
            if isinstance(noeud, ast.Assign):
                for cible in noeud.targets:
                    if (isinstance(cible, ast.Name)
                            and cible.id.startswith(
                                manuel.PREFIXE_DES_CONSTANTES)):
                        noms.add(cible.id)
        definies[fichier.stem] = noms
    return definies


def emprunts_d_un_module(module: types.ModuleType,
                         definies: set[str]) -> set[str]:
    """Les `RACCOURCIS_*` que ce module EXPOSE sans les DEFINIR.

    **Extraite du balayage le 2026-09-05, lot E3, et c'est un correctif de
    mesure.** La fabrique ci-dessous reecrivait cette comprehension au lieu de
    l'appeler : elle mesurait donc une COPIE du mecanisme, et serait restee
    verte sur toute mutation du vrai. C'est la famille exacte du « banc
    tautologique » que la politique de revue nomme endemique ici -- avec la
    circonstance aggravante que le test s'appelait
    `..._le_MECANISME_..._MORD_...`.
    """
    return {nom for nom, valeur in inspect.getmembers(module)
            if nom.startswith(manuel.PREFIXE_DES_CONSTANTES)
            and isinstance(valeur, str)
            and nom not in definies}


def emprunts_du_paquet() -> set[tuple[str, str]]:
    """Les couples `(module, constante)` que le module ne definit pas.

    C'est le troisieme chemin vers le faux « partout », et il est distinct des
    deux que les couches 1 et 2 de la 11.9 ont nommes : celles-ci portent sur
    deux modules **du meme atelier** ; celui-ci fait porter une ligne par un
    module qui n'a fait que l'**importer**, y compris depuis un autre atelier.
    """
    import mixed_media_utility.tui as paquet

    definies = constantes_definies_par_module()
    trouves = set()
    for info in pkgutil.iter_modules(paquet.__path__):
        module = importlib.import_module(f"{paquet.__name__}.{info.name}")
        trouves |= {(info.name, nom)
                    for nom in emprunts_d_un_module(
                        module, definies.get(info.name, set()))}
    return trouves


#: Les DEUX emprunts du paquet, avec le module qui definit vraiment la
#: constante. Les deux sont deliberes cote produit -- « une reference plutot
#: qu'une seconde redaction » -- et c'est la DERIVATION qui n'en sait rien.
EMPRUNTS_CONNUS = {
    ("atelier_pdf_resultat", "RACCOURCIS_RAPPORT"),        # atelier_scan_parcours
    # `("atelier_scan_confirmation", "RACCOURCIS_CONFIRMATION")` EST SORTI DE
    # CET ENSEMBLE le 2026-09-05, avec le lot G de la story 11.4e. `E3-6`
    # reprenait la constante de l'ecran partage `execution.py` -- juste tant
    # qu'il avait un mode d'edition, faux des que `EPIC11-ARB-141` le lui a
    # retire : la constante commune promet `Tab éditer les noms`. Il porte
    # desormais sa propre ligne, comme les ateliers Pdf et Exports.
    #
    # **La frontiere a fait exactement ce qu'elle promet** : elle a rougi dans
    # le sens de l'AMELIORATION, ce qu'une assertion positive n'aurait pas
    # fait. Le second emprunt disparait donc, et l'ensemble n'en garde qu'un --
    # ce qui rend le prochain d'autant plus visible.
}


def test_l_ensemble_des_CONSTANTES_EMPRUNTEES_est_EXACTEMENT_celui_la():
    """La frontiere qui empeche le troisieme chemin de s'etendre en silence.

    **Ce que la mesure etablit aujourd'hui**, et il faut le dire avec elle :
    aucun des deux emprunts ne change quoi que ce soit au manuel livre -- les
    ouvreurs concernes ont deja des porteurs dans plusieurs ateliers, et
    `test_les_DEUX_emprunts_sont_SANS_EFFET_aujourd_hui` le mesure. Le defaut
    est **latent**, exactement comme le sont les findings `F1` de la couche 1
    et `F2` de la couche 2. Il cesse de l'etre au premier emprunt d'une ligne
    dont l'ouvreur n'a qu'un seul porteur reel.

    Un troisieme emprunt fait rougir ici, ce qui est le seul moyen de le voir
    arriver : `git` ne montre qu'un `from . import`, qui est ordinaire.
    """
    mesure = emprunts_du_paquet()
    assert mesure == EMPRUNTS_CONNUS, sorted(mesure ^ EMPRUNTS_CONNUS)


def test_l_emprunt_RESTANT_est_SANS_EFFET_aujourd_hui():
    """La reserve, MESUREE plutot que supposee.

    **Ils etaient deux jusqu'au 2026-09-05** ; le lot G de la 11.4e a ferme
    celui de `atelier_scan_confirmation`, voir le commentaire d'`EMPRUNTS_CONNUS`.

    On rejoue la derivation en retirant les cles d'emprunt et on compare
    les entrees rendues. Si le manuel livre etait deja fausse par un emprunt,
    cette mesure le dirait -- et elle rougirait le jour ou un emprunt commence
    a mordre, ce qui est le vrai signal.
    """
    vrai = manuel.lignes_de_raccourcis_du_paquet
    prefixe = "mixed_media_utility.tui."
    exclues = {f"{prefixe}{module}.{constante}"
               for module, constante in EMPRUNTS_CONNUS}
    livre = manuel.entrees_du_manuel()
    try:
        manuel.lignes_de_raccourcis_du_paquet = lambda: {
            cle: ligne for cle, ligne in vrai().items() if cle not in exclues}
        sans_emprunts = manuel.entrees_du_manuel()
    finally:
        manuel.lignes_de_raccourcis_du_paquet = vrai
    assert livre == sans_emprunts, (
        "un emprunt MORD desormais sur la derivation : voir la dette "
        "« la constante importee est attribuee au module importateur »")


#: Les trois rangs d'une collection triee : `inspect.getmembers` rend ses
#: membres par ordre alphabetique, donc le SUFFIXE decide de la place.
_RANGS_DE_L_EMPRUNT = [pytest.param("AAA", id="tete"),
                       pytest.param("MMM", id="milieu"),
                       pytest.param("ZZZ", id="queue")]


@pytest.mark.parametrize("suffixe_emprunte", _RANGS_DE_L_EMPRUNT)
def test_le_MECANISME_de_l_emprunt_MORD_sur_un_module_FABRIQUE(
        suffixe_emprunte):
    """Le volet de morsure : la mesure voit-elle vraiment un emprunt ?

    Sans lui, `emprunts_du_paquet` pourrait ne plus rien regarder et son
    egalite ci-dessus resterait verte contre un ensemble vide -- le mode de
    panne que `test_manuel_derive.py` nomme pour les deux volets de l'AC 3.3.

    Le module fabrique porte TROIS constantes distinguables -- des valeurs
    differentes, jamais un remplissage uniforme -- et l'empruntee est posee
    successivement en TETE, au MILIEU et en QUEUE.

    **La cible de bord a ete ajoutee le 2026-09-05, lot E3**, et le motif est
    celui du point 4 de la regle des fabriques : la version d'origine ne
    plagait la cible qu'au milieu. « Au milieu » demasque un `find` fautif --
    une mesure qui ne verrait que le premier membre --, il ne demasque **pas**
    un balayage tronque, qui est l'autre mode de panne d'une boucle qui
    accumule et le plus naturel ici, `inspect.getmembers` rendant une liste.
    """
    valeurs = {"AAA": "Tt propre  Uu un",
               "MMM": "Tt empruntee  Uu deux",
               "ZZZ": "Tt propre aussi  Uu trois"}
    faux = types.ModuleType("module_fabrique")
    for suffixe, valeur in valeurs.items():
        setattr(faux, f"{manuel.PREFIXE_DES_CONSTANTES}{suffixe}", valeur)
    empruntee = f"{manuel.PREFIXE_DES_CONSTANTES}{suffixe_emprunte}"
    definies = {f"{manuel.PREFIXE_DES_CONSTANTES}{suffixe}"
                for suffixe in valeurs} - {empruntee}
    # On appelle le mecanisme, on ne le reecrit pas : une comprehension
    # recopiee ici serait verte sur toute mutation de `emprunts_d_un_module`.
    assert emprunts_d_un_module(faux, definies) == {empruntee}


# ===========================================================================
# C3 -- ce que la passe croisee a cherche et N'A PAS trouve
# ===========================================================================

#: L'intervalle de commits de la 11.8. Il est **clos** -- la story est livree
#: --, donc stable et rejouable ; c'est ce qui permet de mesurer la moitie
#: 11.8 de la surface plutot que de la recopier.
INTERVALLE_DE_LA_11_8 = ("b90ed2cd", "ef3d6746f")


def _fichiers_de_l_intervalle(depuis: str, jusqu_a: str) -> set[str] | None:
    """Les chemins ecrits entre deux commits, ou `None` si l'un est hors
    d'atteinte.

    Le saut est **structurel** et jamais un drapeau qu'on oublie de rallumer :
    un clone superficiel n'a pas ces commits, et il n'y a alors rien a
    comparer. Meme forme que `test_politiques_du_depot` face a `origin/main`.
    """
    import subprocess

    try:
        sortie = subprocess.run(
            ["git", "diff", "--name-only", f"{depuis}..{jusqu_a}"],
            cwd=_RACINE, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if sortie.returncode != 0:
        return None
    return {ligne for ligne in sortie.stdout.splitlines() if ligne}


def test_les_HUIT_fichiers_ecrits_par_les_DEUX_stories_sont_EXACTEMENT_ceux_la():
    """La surface de collision directe de la vague.

    C'est le point de depart de la passe : les fichiers que les deux stories
    ont ecrits, mesures a l'intersection de leurs deux intervalles
    (`b90ed2cd..ef3d6746f` pour la 11.8, `a95d137a8..HEAD` pour la 11.9).

    > **Rectifie le 2026-09-05, lot E3, et c'est une AUTOCRITIQUE de la
    > premiere passe croisee.** Ce test annoncait borner la surface « pour
    > qu'une reprise ulterieure de l'une des deux ne l'elargisse pas sans
    > qu'on le voie », et il ne le faisait pas : ses deux seules assertions
    > portaient sur un ensemble **litteral** -- que ses huit fichiers existent
    > encore, et que ce litteral en compte huit. `len({...}) == 8` sur un
    > litteral est vrai par construction. Un neuvieme fichier ecrit des deux
    > cotes n'aurait fait rougir personne.
    >
    > **Et l'intervalle de la 11.9 ne peut PLUS etre rejoue tel quel** :
    > `a95d137a8..HEAD` rend aujourd'hui **33** fichiers communs, parce que
    > `HEAD` a depuis absorbe les stories 11.4e, 11.13 et 11.14. Le recalculer
    > des deux cotes produirait un faux rouge, pas une mesure.
    >
    > Ce qui reste mesurable, et qui l'est desormais : la moitie **11.8** de
    > la surface, dont l'intervalle est **clos**. Chacun des huit fichiers doit
    > y figurer -- un fichier renomme ou sorti de la story fait rougir --, et
    > le volet symetrique verifie que la mesure voit vraiment quelque chose.
    > Ce que ce test ne peut toujours pas voir est **dit** plutot que promis :
    > l'elargissement du cote 11.9. Il est en dette.
    """
    surface = {
        "src/mixed_media_utility/cli.py",
        "src/mixed_media_utility/project_maintenance.py",
        "src/mixed_media_utility/tui/atelier_pdf_calibration.py",
        "src/mixed_media_utility/tui/coque.py",
        "tests/unit/test_liaison_coeur_vague_3.py",
        "tests/unit/tui/test_arb140_sortie_de_l_ecran_d_aide.py",
        "tests/unit/tui/test_coeur_en_processus.py",
        "tests/unit/tui/test_frontiere_cli.py",
    }
    manquants = [chemin for chemin in surface if not (_RACINE / chemin).exists()]
    assert manquants == [], manquants

    ecrits_par_la_11_8 = _fichiers_de_l_intervalle(*INTERVALLE_DE_LA_11_8)
    if ecrits_par_la_11_8 is None:
        pytest.skip("l'intervalle de la 11.8 est hors d'atteinte (clone "
                    "superficiel) : il n'y a rien a comparer")
    # Le volet de morsure : sans lui, un `git diff` qui ne rendrait plus rien
    # laisserait l'inclusion ci-dessous verte contre un ensemble vide.
    assert len(ecrits_par_la_11_8) > len(surface), len(ecrits_par_la_11_8)
    hors_11_8 = sorted(surface - ecrits_par_la_11_8)
    assert hors_11_8 == [], hors_11_8


def test_le_registre_ARB_140_a_bien_ete_ELARGI_et_non_DEPLACE():
    """La couture que la 11.9 a fermee, epinglee pour qu'elle le reste.

    La 11.8 a livre la sortie `Echap` d'un ecran de passage en le nommant :
    « cet ecran est celui que `F1` empile de n'importe ou ». La 11.9 a change
    ce que `F1` empile. Deplacer la mesure sur le nouvel ecran aurait laisse
    l'ancien sans temoin -- « une mesure portee sans son module », le defaut
    symetrique que `CLAUDE.md` nomme a la liaison. Le lot D a elargi le
    registre au lieu de le deplacer ; ce test mesure que les deux passages y
    sont, plutot que de faire confiance au rapport qui le dit.
    """
    banc = importlib.import_module("test_arb140_sortie_de_l_ecran_d_aide")
    identifiants = {parametre.id for parametre in banc.PASSAGES}
    assert identifiants == {"manuel-par-F1", "pas-encore-par-la-suite-de-X"}, (
        sorted(identifiants))


# ===========================================================================
# C4 -- l'AIDE DE CHAMP de la 11.9 et le FORMULAIRE que la 11.8 livre
#       (passe croisee du 2026-09-05, lot E3)
# ===========================================================================
#
# La premiere passe croisee (2026-09-03) a mesure le VOCABULAIRE des touches et
# les EMPRUNTS de constantes. Elle n'a pas regarde la surface que la 11.9 a
# reellement ouverte : l'aide de CHAMP, c'est-a-dire un second sens de `F1` sur
# les ecrans qui portent un formulaire. Or la 11.8 livre, le meme jour et dans
# la meme vague, un formulaire de plus.
#
# Ce que la mesure ci-dessous etablit -- et elle ne tranche rien :
#
#   * six modules du paquet definissent un modele de formulaire (une classe a
#     champ courant) ;
#   * quatre d'entre eux portent une `TABLE_D_AIDE`, ce sont les quatre de
#     l'AC 1.5 de la 11.9 ;
#   * les deux autres n'en portent pas et ne sont **pas non plus** nommes dans
#     `aide_de_champ.ECRANS_ECARTES`, dont le docstring dit pourtant que « le
#     silence sur un cas limite rendrait l'ensemble indecidable ». L'un des
#     deux est `atelier_exports_reglages`, livre par la 11.8 le 2026-09-03 --
#     c'est-a-dire dans la vague meme ou la 11.9 generalisait le mecanisme.
#
# La consequence est visible par l'operateur : sur les quatre porteurs, `F1`
# ouvre l'aide du champ sous le curseur ; sur le formulaire de la 11.8, la meme
# touche annoncee par le meme mot (`F1 aide`) ouvre le MANUEL. Le choix
# appartient a Egan (`deferred-work.md`, « ce qui attend un ARBITRAGE »).


def modules_portant_un_formulaire(
        classes_par_module: dict[str, tuple[type, ...]]) -> set[str]:
    """Les modules qui DEFINISSENT un modele de formulaire.

    « Modele de formulaire » se mesure et ne se declare pas : une classe de
    donnees qui porte un **champ courant**, c'est-a-dire l'attribut sur lequel
    `aide_de_champ.ChampSuivi` se pose chez les quatre porteurs. C'est le
    critere que `ECRANS_ECARTES` invoque deja en creux pour ecarter
    `EcranCreation` (« l'ecran n'a d'ailleurs pas de modele `Formulaire*` »).

    La fonction prend ses classes **en argument** plutot que de balayer le
    paquet : c'est ce qui permet de la mesurer sur une fabrique, donc de tenir
    le volet de morsure et les cibles de bord (regle des fabriques, point 4).
    """
    from mixed_media_utility.tui import aide_de_champ

    porteurs = set()
    for module, classes in classes_par_module.items():
        for classe in classes:
            if not dataclasses.is_dataclass(classe):
                continue
            noms = {champ.name for champ in dataclasses.fields(classe)}
            if aide_de_champ.NOM_DU_CHAMP_COURANT in noms:
                porteurs.add(module)
    return porteurs


def classes_par_module_du_paquet() -> dict[str, tuple[type, ...]]:
    """Les classes que chaque module du paquet DEFINIT lui-meme.

    `obj.__module__ == module.__name__` : sans ce filtre, une classe importee
    ferait porter le formulaire au module importateur -- exactement le
    troisieme chemin vers le faux « partout » que la section C2 mesure.
    """
    import mixed_media_utility.tui as paquet

    rendu: dict[str, tuple[type, ...]] = {}
    for info in pkgutil.iter_modules(paquet.__path__):
        module = importlib.import_module(f"{paquet.__name__}.{info.name}")
        rendu[info.name] = tuple(
            objet for objet in vars(module).values()
            if inspect.isclass(objet) and objet.__module__ == module.__name__)
    return rendu


#: **Les formulaires du paquet que l'aide de champ ne couvre pas, bornes en
#: EGALITE.** Un septieme formulaire qui arriverait sans table et sans motif
#: fait rougir ; donner une table a l'un des deux, ou l'inscrire a
#: `ECRANS_ECARTES` avec son motif, fait rougir aussi -- et c'est voulu : la
#: sortie de cet ensemble se constate, elle ne se devine pas.
#:
#: * `atelier_exports_reglages` -- **vague 6, story 11.8, 2026-09-03**. Trois
#:   champs (`CHAMPS`), deux de saisie, et ses deux lignes de raccourcis
#:   annoncent `F1 aide` ;
#: * `atelier_pdf_reglages` -- anterieur a la vague (2026-09-02), meme silence.
#:   Il est ici pour la meme raison qu'un ensemble se borne en egalite : le
#:   taire ferait de la mesure une inclusion, verte le jour ou elle ne voit
#:   plus rien.
FORMULAIRES_HORS_AIDE_DE_CHAMP = {"atelier_exports_reglages",
                                  "atelier_pdf_reglages"}


def test_l_ensemble_des_FORMULAIRES_SANS_aide_de_champ_est_EXACTEMENT_celui_la():
    """La couture de la vague 6, bornee en egalite plutot que tranchee.

    **Ni porteur, ni ecarte.** `aide_de_champ` tient deux registres -- les
    ecrans qui portent une table, et ceux qu'on ecarte avec leur motif -- et
    son docstring dit que le silence sur un cas limite rend l'ensemble
    indecidable. Ces deux modules sont ce silence.
    """
    from mixed_media_utility.tui import aide_de_champ

    formulaires = modules_portant_un_formulaire(classes_par_module_du_paquet())
    assert len(formulaires) == 6, sorted(formulaires)

    prefixe = "mixed_media_utility.tui."
    couverts = {nom[len(prefixe):].rsplit(".", 1)[0]
                for nom in (set(aide_de_champ.ECRANS_A_TABLE_D_AIDE)
                            | set(aide_de_champ.ECRANS_ECARTES))}
    muets = formulaires - couverts
    assert muets == FORMULAIRES_HORS_AIDE_DE_CHAMP, sorted(
        muets ^ FORMULAIRES_HORS_AIDE_DE_CHAMP)

    # Le volet symetrique : sans lui, la mesure ci-dessus serait verte le jour
    # ou plus AUCUN module ne serait couvert.
    assert len(formulaires & couverts) == 4, sorted(formulaires & couverts)


def test_le_formulaire_de_la_11_8_annonce_F1_aide_et_n_a_AUCUNE_table():
    """Le mot est le meme des deux cotes de la vague ; le geste ne l'est pas.

    Ce que la mesure etablit, et c'est ce qui en fait une couture de produit
    plutot qu'une affaire de registre : le formulaire de la 11.8 annonce
    `F1 aide` -- le mot des quatre-vingt-quatre autres sites -- alors que `F1`
    y ouvre le manuel et non l'aide de son champ. Rien, sur l'ecran, ne dit a
    l'operateur laquelle des deux aides il va obtenir.
    """
    from mixed_media_utility.tui import aide_de_champ, atelier_exports_reglages

    assert aide_de_champ.NOM_DE_LA_TABLE not in vars(atelier_exports_reglages)
    for classe in vars(atelier_exports_reglages).values():
        if inspect.isclass(classe):
            assert aide_de_champ.NOM_DE_LA_TABLE not in vars(classe), classe

    prefixe = "mixed_media_utility.tui.atelier_exports_reglages."
    lignes = {cle: ligne
              for cle, ligne in manuel.lignes_de_raccourcis_du_paquet().items()
              if cle.startswith(prefixe)}
    assert len(lignes) >= 2, sorted(lignes)
    mots = {libelle
            for ligne in lignes.values()
            for ouvreur, libelle in manuel.items_d_une_ligne(ligne)
            if ouvreur == "F1"}
    assert mots == {"aide"}, sorted(mots)


#: Trois modules temoins DISTINGUABLES -- deux sans formulaire, un avec. Un
#: remplissage uniforme rendrait toute permutation invisible.
def _fabrique_de_modules(place_de_la_cible: int) -> dict[str,
                                                         tuple[type, ...]]:
    """La cible posee au rang demande : 0 en tete, 1 au milieu, 2 en queue.

    Le point 4 de la regle des fabriques mord ici pour de bon : un balayage
    tronque -- `for module in list(modules)[:-1]` -- ne se voit **que** sur une
    cible de queue, et il est le mode de panne naturel d'une boucle qui
    accumule.
    """
    from mixed_media_utility.tui import aide_de_champ

    # Le nom du champ courant est LU du module, jamais recopie : le recopier
    # ferait une seconde redaction, qui divergerait au premier renommage.
    cible = dataclasses.dataclass(
        type("_AvecChampCourant", (),
             {"__annotations__": {aide_de_champ.NOM_DU_CHAMP_COURANT: str},
              aide_de_champ.NOM_DU_CHAMP_COURANT: ""}))

    @dataclasses.dataclass
    class _SansChampCourant:
        autre_chose: str = ""

    @dataclasses.dataclass
    class _SansChampCourantNonPlus:
        troisieme: int = 0

    ordinaires = [("module_zzz", (_SansChampCourant,)),
                  ("module_yyy", (_SansChampCourantNonPlus,))]
    ordinaires.insert(place_de_la_cible, ("module_cible", (cible,)))
    return dict(ordinaires)


@pytest.mark.parametrize("place", [0, 1, 2], ids=["tete", "milieu", "queue"])
def test_la_mesure_des_FORMULAIRES_MORD_ou_que_soit_la_cible(place):
    """Le volet de morsure, cible en TETE, au MILIEU et en QUEUE.

    Sans lui, `modules_portant_un_formulaire` pourrait ne plus rien voir et
    l'egalite ci-dessus resterait verte contre un ensemble vide -- le mode de
    panne que la politique de revue nomme « une garde ecrite, relue, plausible,
    et ne mesurant rien ».
    """
    mesure = modules_portant_un_formulaire(_fabrique_de_modules(place))
    assert mesure == {"module_cible"}, sorted(mesure)


def test_la_mesure_des_FORMULAIRES_NE_MORD_PAS_sur_une_classe_IMPORTEE():
    """Le volet symetrique : un formulaire importe n'est pas un formulaire
    defini.

    Sans ce filtre, les quatre porteurs de l'aide de champ feraient porter un
    formulaire a `aide_de_champ` lui-meme, qui n'en definit aucun -- et
    l'ensemble ci-dessus en compterait sept au lieu de six.
    """
    classes = classes_par_module_du_paquet()
    assert "aide_de_champ" in classes
    assert "aide_de_champ" not in modules_portant_un_formulaire(classes)
