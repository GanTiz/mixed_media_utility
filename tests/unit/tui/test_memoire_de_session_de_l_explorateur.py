# -*- coding: utf-8 -*-
"""Retour terrain d'Egan du 2026-09-06 -- « l'explorateur de fichiers ne
retient pas le dernier chemin explore ».

**Ce n'etait pas un manque : c'etait un mecanisme mort.**
`explorateur.MemoireDeSession` (`EPIC11-ARB-54`) etait ecrite, ecrite au bon
moment, relue au bon endroit, corrigee d'un finding de finesse -- et
**injectee nulle part** dans `src/`. La recherche de `memoire=` sur tout le
depot rendait quatre occurrences, toutes dans `test_explorateur.py`. Les sept
sites de production construisaient chacun un explorateur sans memoire, donc
chacun s'en fabriquait une neuve et vide.

Ce banc mesure les trois choses que le defaut d'origine reunissait :

1. le **registre** et sa granularite par famille (`MemoiresDeSession`) ;
2. la **reprise** d'un explorateur deja monte (`reprendre_la_memoire`) -- ce
   que l'injection a la construction ne peut pas faire, les ecrans du produit
   etant montes une fois et revisites ;
3. le **cablage reel**, sous une application montee : c'est la seule couche qui
   aurait vu le defaut d'origine, et aucun test ne la traversait.

**Regle des fabriques.** Les arborescences portent au moins deux dossiers
distinguables, la cible est placee **ailleurs qu'en premiere position** et
**a chaque bord** (tete et queue), et les familles varient dans les deux sens
-- un banc qui ne jouerait qu'une famille ne verrait pas deux familles
partager la meme memoire par erreur, ce qui est exactement le defaut que la
granularite existe pour eviter.
"""
import sys
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from mixed_media_utility.tui import atelier_extraction, ecran_projet, explorateur
from mixed_media_utility.tui.coque import Contexte, CoqueTui, PalierTemoin
from mixed_media_utility.tui.explorateur import (
    FAMILLE_MATIERE,
    FAMILLE_PROFILS,
    FAMILLE_PROJETS,
    FAMILLES,
    Explorateur,
    MemoireDeSession,
    MemoiresDeSession,
)


# ---------------------------------------------------------------------------
# Fabriques -- QUATRE dossiers distinguables, jamais un remplissage uniforme
# ---------------------------------------------------------------------------

#: Les noms sont tries : `alpha` est en TETE de liste, `omega` en QUEUE. Les
#: deux du milieu existent pour que « ailleurs qu'en premiere position » et
#: « au bord » soient deux mesures distinctes et non la meme.
NOMS = ("alpha", "beta", "gamma", "omega")


def arborescence(racine: Path) -> dict[str, Path]:
    """Quatre dossiers distinguables, chacun avec un contenu DIFFERENT.

    Un remplissage uniforme rendrait une permutation invisible : c'est le
    defaut que la regle des fabriques de `CLAUDE.md` ferme, paye trois fois.
    """
    dossiers = {}
    for rang, nom in enumerate(NOMS):
        chemin = racine / nom
        chemin.mkdir()
        # Contenu distinguable : `alpha` a 0 sous-dossier, `omega` en a 3.
        for enfant in range(rang):
            (chemin / f"{nom}_{enfant}").mkdir()
        dossiers[nom] = chemin
    return dossiers


# ---------------------------------------------------------------------------
# 1 -- le registre, et sa granularite
# ---------------------------------------------------------------------------

def test_le_registre_rend_la_MEME_memoire_pour_la_meme_famille():
    registre = MemoiresDeSession()
    assert registre.pour(FAMILLE_MATIERE) is registre.pour(FAMILLE_MATIERE)


@pytest.mark.parametrize("une,autre", [
    (FAMILLE_PROJETS, FAMILLE_MATIERE),
    (FAMILLE_MATIERE, FAMILLE_PROFILS),
    (FAMILLE_PROJETS, FAMILLE_PROFILS),
])
def test_deux_familles_ne_partagent_PAS_leur_memoire(une, autre, tmp_path):
    """Volet symetrique du precedent, et il porte la decision de granularite.

    Sans lui, un registre qui rendrait une memoire unique pour tout l'outil
    passerait le test ci-dessus -- et menerait l'ecran des profils dans le
    dossier des rushes, ce qui est le contraire du benefice cherche.
    """
    registre = MemoiresDeSession()
    registre.pour(une).dernier_valide = tmp_path
    assert registre.pour(autre).dernier_valide is None


def test_une_famille_inconnue_LEVE_plutot_que_de_rendre_une_memoire_neuve():
    """Frontiere : un nom mal orthographie doit se payer au banc.

    Une quatrieme memoire silencieuse ferait retenir l'ecran pour lui seul,
    et le defaut se lirait exactement comme celui qu'on repare -- « ca ne
    retient pas » -- sans qu'aucune etape n'echoue.
    """
    with pytest.raises(ValueError, match="famille d'exploration inconnue"):
        MemoiresDeSession().pour("matiere ")   # une espace de trop


def test_le_registre_ne_cree_une_memoire_qu_A_LA_DEMANDE():
    registre = MemoiresDeSession()
    assert registre.familles_ouvertes == ()
    registre.pour(FAMILLE_PROFILS)
    assert registre.familles_ouvertes == (FAMILLE_PROFILS,)


# ---------------------------------------------------------------------------
# 2 -- la reprise d'un explorateur DEJA monte
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cible", ["alpha", "omega", "gamma"])
def test_la_reprise_replace_l_explorateur_sur_le_dossier_memorise(tmp_path, cible):
    """Trois positions, dont les DEUX BORDS de la liste triee.

    La cible au milieu (`gamma`) demasque un `find` fautif ; elle ne demasque
    pas un balayage tronque. `alpha` est en tete, `omega` en queue -- point 4
    de la regle des fabriques, pose le 2026-09-03.
    """
    dossiers = arborescence(tmp_path)
    exp = Explorateur(tmp_path)
    assert exp.dossier == tmp_path

    memoire = MemoireDeSession(dernier_valide=dossiers[cible])
    assert exp.reprendre_la_memoire(memoire) is True
    assert exp.dossier == dossiers[cible]
    # Et la liste a bien ete relue : le contenu est celui de la CIBLE, pas
    # celui de la racine. Sans cette moitie, un `self.dossier = ...` sans
    # `relire()` passerait.
    assert [e.chemin.name for e in exp.entrees] == sorted(
        c.name for c in dossiers[cible].iterdir())


def test_la_reprise_rebranche_l_explorateur_meme_quand_elle_ne_deplace_rien(tmp_path):
    """Volet symetrique : rien a rejouer, mais la memoire doit etre PARTAGEE.

    C'est le cas du tout premier passage -- la memoire est vide. Si la reprise
    se contentait de deplacer, l'explorateur garderait la memoire neuve de sa
    construction et sa validation n'ecrirait nulle part : le defaut d'origine,
    exactement.
    """
    dossiers = arborescence(tmp_path)
    exp = Explorateur(tmp_path)
    memoire = MemoireDeSession()

    assert exp.reprendre_la_memoire(memoire) is False
    assert exp.memoire is memoire
    exp.deplacer(len(NOMS) - 1)          # jusqu'a `omega`, en QUEUE de liste
    assert exp.valider() == dossiers["omega"]
    assert memoire.dernier_valide == dossiers["omega"]


def test_la_validation_MULTIPLE_ecrit_aussi_dans_la_memoire(tmp_path):
    """La branche que le mode selection prenait sans rien memoriser.

    Le seul site du produit qui coche plusieurs sources est le depot du Scan
    (`E3-1`), c'est-a-dire justement le premier temps du parcours que
    `EPIC11-ARB-54` nomme. Il aurait LU la memoire de sa famille sans jamais
    l'ecrire -- un explorateur qui lit sans ecrire est le meme mecanisme mort
    que ce lot repare, en plus discret.

    On coche **deux** entrees, dont celle de QUEUE : une seule coche ne
    distinguerait pas ce mode du mode simple.
    """
    dossiers = arborescence(tmp_path)
    exp = Explorateur(dossiers["gamma"], selection_multiple=True)
    memoire = MemoireDeSession()
    exp.reprendre_la_memoire(memoire)

    exp.basculer_la_coche()
    exp.deplacer(len(exp.entrees) - 1)
    exp.basculer_la_coche()
    retour = exp.valider()

    assert isinstance(retour, list) and len(retour) == 2
    assert memoire.dernier_valide == dossiers["gamma"]


def test_la_validation_multiple_SANS_coche_retombe_sur_le_mode_simple(tmp_path):
    """Volet symetrique : sans coche, c'est la cible sous le curseur qui vaut,
    et c'est ELLE qui se memorise -- pas le dossier parcouru."""
    dossiers = arborescence(tmp_path)
    exp = Explorateur(tmp_path, selection_multiple=True)
    memoire = MemoireDeSession()
    exp.reprendre_la_memoire(memoire)

    exp.deplacer(len(NOMS) - 1)          # `omega`, en QUEUE
    assert exp.valider() == dossiers["omega"]
    assert memoire.dernier_valide == dossiers["omega"]


def test_un_dossier_memorise_devenu_illisible_ne_deplace_RIEN(tmp_path):
    """Le volume debranche entre deux visites est le cas nominal de la famille
    « matiere ». Passer alors au dossier personnel ferait perdre la position
    courante EN PLUS du souvenir."""
    dossiers = arborescence(tmp_path)
    exp = Explorateur(dossiers["beta"])
    disparu = tmp_path / "volume_debranche"

    assert exp.reprendre_la_memoire(
        MemoireDeSession(dernier_valide=disparu)) is False
    assert exp.dossier == dossiers["beta"]
    assert "illisible" not in exp.etat()


def test_la_reprise_referme_la_BARRE_D_ADRESSE_quand_elle_deplace(tmp_path):
    """La barre porte le chemin de l'ANCIEN dossier, pose a la visite
    precedente. La laisser ouverte afficherait une adresse qui n'est plus
    celle de la liste en dessous.

    Volet symetrique juste apres : une reprise qui ne deplace pas ne doit rien
    refermer -- sans quoi elle detruirait une saisie en cours.
    """
    dossiers = arborescence(tmp_path)
    exp = Explorateur(tmp_path)
    exp.basculer_la_saisie()
    assert exp.dans_la_saisie

    assert exp.reprendre_la_memoire(
        MemoireDeSession(dernier_valide=dossiers["omega"])) is True
    assert exp.dans_la_saisie is False
    assert exp.dossier == dossiers["omega"]


def test_la_reprise_qui_ne_deplace_pas_LAISSE_la_barre_d_adresse(tmp_path):
    arborescence(tmp_path)
    exp = Explorateur(tmp_path)
    exp.basculer_la_saisie()
    exp.frapper("z")
    avant = exp.saisie

    assert exp.reprendre_la_memoire(MemoireDeSession()) is False
    assert exp.dans_la_saisie and exp.saisie == avant


def test_la_reprise_sur_le_dossier_deja_courant_ne_relit_pas(tmp_path):
    arborescence(tmp_path)
    exp = Explorateur(tmp_path)
    exp.deplacer(2)
    assert exp.curseur == 2
    assert exp.reprendre_la_memoire(
        MemoireDeSession(dernier_valide=tmp_path)) is False
    # `relire()` remet le curseur a zero : s'il a bouge, il y a eu relecture.
    assert exp.curseur == 2


# ---------------------------------------------------------------------------
# 3 -- le CABLAGE REEL, sous une application montee
# ---------------------------------------------------------------------------

def coque_avec(*ecrans):
    return CoqueTui(paliers=[PalierTemoin("Projet", "q quitter"),
                             PalierTemoin("Ateliers", "q quitter"), *ecrans],
                    contexte=Contexte("projet_demo"))


def test_la_coque_porte_un_registre_de_memoires():
    assert isinstance(CoqueTui().memoires, MemoiresDeSession)


def test_deux_coques_ont_des_memoires_DISTINCTES(tmp_path):
    """Meme motif que la feuille CSS posee sur l'instance : le banc monte une
    application par fichier, et une memoire de module fuirait de l'une a
    l'autre."""
    une, autre = CoqueTui(), CoqueTui()
    une.memoires.pour(FAMILLE_MATIERE).dernier_valide = tmp_path
    assert autre.memoires.pour(FAMILLE_MATIERE).dernier_valide is None


def test_l_ecran_projet_LIT_la_memoire_de_sa_famille_a_l_ouverture(tmp_path, banc):
    """**Le test qui aurait vu le defaut d'origine.**

    L'operateur a valide `omega` ailleurs dans la session ; il revient au
    palier 0, presse `Tab`, et l'explorateur doit s'ouvrir sur `omega` -- pas
    sur `Path.cwd()`.
    """
    dossiers = arborescence(tmp_path)
    ecran = ecran_projet.EcranProjet()
    app = coque_avec(ecran)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        # **La memoire est posee APRES le montage, et c'est tout le point** :
        # ce palier est monte une fois pour la session, l'operateur valide
        # `omega` dans un AUTRE ecran, puis revient ici. Poser la memoire
        # avant le montage laisserait passer un cablage qui ne lirait qu'a la
        # construction -- c'est-a-dire le defaut d'origine, deguise.
        app.memoires.pour(FAMILLE_PROJETS).dernier_valide = dossiers["omega"]
        ecran.zone = ecran_projet.ZONE_RECENTS
        ecran.traiter("tab")
        return ecran.explorateur.dossier

    assert banc(app, scenario) == dossiers["omega"]


def test_l_ecran_projet_ECRIT_dans_la_memoire_de_sa_famille(tmp_path, banc):
    """Volet symetrique : sans lui, un ecran qui lirait la memoire de l'app
    mais garderait la sienne pour ecrire passerait le test precedent."""
    dossiers = arborescence(tmp_path)
    ecran = ecran_projet.EcranProjet()
    app = coque_avec(ecran)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        app.memoires.pour(FAMILLE_PROJETS).dernier_valide = tmp_path
        ecran.zone = ecran_projet.ZONE_RECENTS
        ecran.traiter("tab")
        # `beta` est en SECONDE position : un `valider` qui prendrait le
        # premier element rendrait `alpha` et ce test le verrait.
        ecran.traiter("down")
        ecran.traiter("enter")

    banc(app, scenario)
    assert app.memoires.pour(FAMILLE_PROJETS).dernier_valide == dossiers["beta"]


def test_les_DEUX_ecrans_du_palier_0_partagent_la_memoire_projets(tmp_path, banc):
    """`E0-2` et `E0-4` : on cree un projet la ou l'on vient d'en chercher."""
    dossiers = arborescence(tmp_path)
    liste = ecran_projet.EcranProjet()
    creation = ecran_projet.EcranCreation()
    app = coque_avec(liste, creation)

    async def scenario(pilote):
        # L'operateur cherche d'abord un projet, valide `alpha`, puis bascule
        # sur la creation : c'est le PARCOURS, pas un etat pose a la main.
        pilote.app.descendre(liste)
        await pilote.pause()
        app.memoires.pour(FAMILLE_PROJETS).dernier_valide = tmp_path
        liste.zone = ecran_projet.ZONE_RECENTS
        liste.traiter("tab")
        # `omega` est en QUEUE de liste : un balayage tronque d'un cran ne
        # l'atteindrait pas, et c'est l'autre bord que le point 4 de la regle
        # des fabriques exige.
        for _ in range(len(NOMS) - 1):
            liste.traiter("down")
        liste.traiter("enter")
        pilote.app.descendre(creation)
        await pilote.pause()
        creation.traiter("tab")
        return creation.explorateur.dossier

    assert banc(app, scenario) == dossiers["omega"]


def test_un_depart_IMPOSE_prime_sur_la_memoire_de_session(tmp_path, banc):
    """Volet symetrique du precedent, et il borne la reprise.

    `E0-4` construit avec un `dossier_parent` valide s'ouvre la, pas ailleurs :
    le champ pointe deja, le deplacer d'office obligerait a revenir a la main.
    """
    dossiers = arborescence(tmp_path)
    creation = ecran_projet.EcranCreation(
        dossier_parent=str(dossiers["gamma"]))
    app = coque_avec(creation)

    async def scenario(pilote):
        pilote.app.descendre(creation)
        await pilote.pause()
        app.memoires.pour(FAMILLE_PROJETS).dernier_valide = dossiers["alpha"]
        creation.traiter("tab")
        return creation.explorateur.dossier

    assert banc(app, scenario) == dossiers["gamma"]


# ---------------------------------------------------------------------------
# 3 bis -- la famille MATIERE, et le fait qu'elle ne se melange pas
# ---------------------------------------------------------------------------

MANIFESTE_VIDE = {"schema_version": "2.1", "project_id": "projet_demo",
                  "rushes": [], "lots": [], "artifacts": {}, "color": {},
                  "video": {}, "reconstruction": {}}


def projet_vide(tmp_path: Path) -> Path:
    import json
    dossier = tmp_path / "projet"
    dossier.mkdir()
    (dossier / "extraction_manifest.json").write_text(
        json.dumps(MANIFESTE_VIDE), encoding="utf-8")
    return dossier


@pytest.mark.parametrize("mode", ["retrouver", "designer"])
def test_les_DEUX_explorateurs_de_l_ecran_rushes_suivent_la_famille_matiere(
        tmp_path, banc, mode):
    """Les deux variantes du MEME ecran cherchent le meme dossier.

    L'une montre les fichiers, l'autre non ; c'est la facon de regarder qui
    differe, pas l'endroit. Deux souvenirs feraient retraverser l'arborescence
    en changeant simplement de facon de chercher.
    """
    from mixed_media_utility.tui import rushes as modele_rushes

    dossiers = arborescence(tmp_path)
    ecran = atelier_extraction.EcranRushes(projet_vide(tmp_path))
    app = coque_avec(ecran)

    async def scenario(pilote):
        pilote.app.descendre(ecran)
        await pilote.pause()
        app.memoires.pour(FAMILLE_MATIERE).dernier_valide = dossiers["omega"]
        ecran._ouvrir_l_explorateur(atelier_extraction.BUT_AJOUTER, mode)
        return ecran.explorateur.dossier

    assert modele_rushes.MONTRER_FICHIERS[mode] in (True, False)
    assert banc(app, scenario) == dossiers["omega"]


def test_la_matiere_et_les_projets_ne_se_MELANGENT_pas(tmp_path, banc):
    """**La mesure de la granularite, cablage compris.**

    Deux familles, deux ecrans reels, une seule application. Un registre a
    memoire unique -- ou deux ecrans ayant recopie la meme cle -- ferait
    partir l'atelier des rushes dans le dossier de projets.
    """
    dossiers = arborescence(tmp_path)
    liste = ecran_projet.EcranProjet()
    rushes_ = atelier_extraction.EcranRushes(projet_vide(tmp_path))
    app = coque_avec(liste, rushes_)

    async def scenario(pilote):
        pilote.app.descendre(liste)
        await pilote.pause()
        app.memoires.pour(FAMILLE_PROJETS).dernier_valide = dossiers["alpha"]
        app.memoires.pour(FAMILLE_MATIERE).dernier_valide = dossiers["omega"]
        liste.zone = ecran_projet.ZONE_RECENTS
        liste.traiter("tab")
        vu_projets = liste.explorateur.dossier
        pilote.app.descendre(rushes_)
        await pilote.pause()
        rushes_._ouvrir_l_explorateur(atelier_extraction.BUT_AJOUTER, "designer")
        return vu_projets, rushes_.explorateur.dossier

    assert banc(app, scenario) == (dossiers["alpha"], dossiers["omega"])


def test_un_ecran_sans_application_montee_s_ouvre_QUAND_MEME(tmp_path):
    """Frontiere : la memoire est un confort, jamais une condition.

    La plupart des bancs d'ecran instancient l'ecran nu. Un explorateur qui
    refuserait de s'ouvrir hors application serait un defaut bien pire que
    l'absence de memoire.
    """
    ecran = ecran_projet.EcranProjet()
    assert ecran.memoire_de_session() is None
    assert ecran.reprendre_la_memoire_de_session() is False


# ---------------------------------------------------------------------------
# 4 -- la frontiere de cablage : plus aucun site muet
# ---------------------------------------------------------------------------

def _classes_a_explorateur():
    """Les classes du paquet TUI qui portent un explorateur.

    Le balayage se fait sur le TEXTE des modules plutot que par import : trois
    des sept sites vivent dans des modules que d'autres agents editent, et un
    import de l'atelier Scan tirerait le coeur avec lui.
    """
    import re

    paquet = Path(_SRC) / "mixed_media_utility" / "tui"
    sites = {}
    for source in sorted(paquet.glob("*.py")):
        texte = source.read_text(encoding="utf-8")
        classe = None
        for ligne in texte.splitlines():
            trouve = re.match(r"class (\w+)\(", ligne)
            if trouve:
                classe = trouve.group(1)
            if re.search(r"(?<![\w.])(explorateur\.)?Explorateur\(", ligne) and classe:
                sites.setdefault(f"{source.name}:{classe}", []).append(ligne)
    return sites


def test_le_balayage_voit_bien_les_sept_sites():
    """Volet symetrique : une frontiere posee sur un balayage vide serait
    verte sans rien mesurer."""
    sites = _classes_a_explorateur()
    assert len(sites) >= 6, sorted(sites)
    # Le compte EXACT vit dans `test_explorateur.py::test_R11...`, qui est le
    # banc de l'AC 1.2 ; le dupliquer ici ferait deux verites du meme fait.
    assert any("ecran_projet.py" in nom for nom in sites), sorted(sites)
    assert any("atelier_scan.py" in nom for nom in sites), sorted(sites)
    assert any("atelier_extraction.py" in nom for nom in sites), sorted(sites)


#: **Les trois sites voisins, avec la famille que chacun doit prendre.** Ils
#: vivent dans des modules qu'un autre agent editait en parallele le
#: 2026-09-06, et le coordinateur les posera. Cette liste doit **retrecir**,
#: jamais grandir : le volet symetrique ci-dessous rougit des qu'une de ses
#: entrees devient perimee.
#:
#: **Un huitieme montage est apparu pendant ce lot** -- `palier_profil_defaut`,
#: ecrit par un agent voisin le meme jour -- et il a declare sa famille de
#: lui-meme : il n'a donc jamais eu besoin d'entrer ici. C'est la preuve que la
#: frontiere sert : elle a vu le site arriver.
#:
#: **VIDE depuis le 2026-09-07**, et c'est le volet symetrique
#: `..._n_est_PERIMEE` qui l'a demande : ses deux dernieres entrees --
#: `EcranCalibrerLaChaine` et `EcranChoixDeCalibration` -- declarent desormais
#: leur famille, et une tolerance qui survit a sa raison d'etre est exactement
#: le mode de panne que ce volet existe pour attraper.
#:
#: Un registre vide n'est pas un banc mort : c'est l'etat ou la frontiere
#: mesure ce qu'elle annonce sans exception. Une entree qui y reapparaitrait
#: **hors reparation en cours** serait une regression, et non plus une dette
#: connue.
A_POSER: dict[str, str] = {}


def _famille_declaree(nom: str) -> "str | None":
    """La famille que le module declare pour cette classe, ou `None`.

    Lue dans le TEXTE du module : trois des sept sites vivent dans des modules
    qui tirent le coeur a l'import, et un banc de la TUI n'a pas a payer ca.
    """
    import re

    fichier, _, classe = nom.partition(":")
    texte = (Path(_SRC) / "mixed_media_utility" / "tui" / fichier
             ).read_text(encoding="utf-8")
    corps = texte.split(f"class {classe}(")[1]
    # **Les DEUX formes d'ecriture, et c'est ce qui rend la frontiere sure.**
    # Un site peut nommer la constante (`FAMILLE_MATIERE`, la forme voulue) ou
    # ecrire la chaine en dur (`"matiere"`). Ne lire que la premiere laisserait
    # la seconde invisible -- donc une tolerance perimee dormirait, ce qui est
    # exactement ce que le volet symetrique existe pour empecher.
    trouve = re.search(r"FAMILLE_D_EXPLORATION[^=\n]*=\s*"
                       r"(?:(?:explorateur\.)?(FAMILLE_\w+)"
                       r"|[\"']([^\"'\n]*)[\"'])", corps)
    if trouve is None:
        return None
    if trouve.group(1):
        # Le module ecrit le NOM de la constante ; on rend sa VALEUR, qui est
        # ce que le registre indexe. Lire l'un pour l'autre ferait passer une
        # frontiere qui ne compare rien.
        return getattr(explorateur, trouve.group(1))
    return trouve.group(2)


def test_la_liste_de_tolerance_ne_porte_que_des_sites_ENCORE_muets():
    """Volet symetrique de la frontiere ci-dessous : une tolerance perimee ne
    dort pas.

    Sans lui, un site cable resterait tolere pour toujours, et la liste
    cesserait de dire ce qu'il reste a faire -- exactement le mode de panne
    d'une exception qui survit a sa raison d'etre.
    """
    perimees = {nom: _famille_declaree(nom) for nom in A_POSER
                if _famille_declaree(nom) is not None}
    assert not perimees, (
        "ces sites declarent desormais leur famille : retirer leur entree de "
        f"A_POSER dans ce fichier -- {perimees}")


@pytest.mark.parametrize("nom", sorted(_classes_a_explorateur()))
def test_toute_classe_a_explorateur_declare_une_famille_CONNUE(nom):
    """La frontiere qui empeche une cle mal orthographiee d'atteindre le
    produit -- `MemoiresDeSession.pour` leve, et on veut que la levee se paie
    ici plutot que chez l'operateur.

    Les trois sites voisins de :data:`A_POSER` sont tolerés **nommement**, avec
    la famille attendue -- pas par un silence.
    """
    declaree = _famille_declaree(nom)
    if nom in A_POSER and declaree is None:
        pytest.xfail(f"site voisin, famille a poser : {A_POSER[nom]}")
    assert declaree in FAMILLES, (
        f"{nom} porte un explorateur sans declarer de famille connue "
        f"(vu {declaree!r}) : son dossier ne sera retenu par personne")
    if nom in A_POSER:
        assert declaree == A_POSER[nom], (nom, declaree, A_POSER[nom])
