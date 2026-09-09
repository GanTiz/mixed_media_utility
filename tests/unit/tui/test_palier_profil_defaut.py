# -*- coding: utf-8 -*-
"""L'ecran « Profil de calibration par defaut » du palier Projet.

**Le manque que ce banc ferme, et c'est Egan qui l'a trouve** (recette du
2026-09-06, verbatim) : « # Profil de calibration par defaut (projet) -- Cet
ecran n'existe pas encore (mauvais cablage ?) ». Le coeur et les six fonctions
de `palier_projet.py` etaient livres depuis la story 11.3 ; l'entree du palier
menait a `EcranPasEncore`.

Ce fichier mesure **le dessin et le parcours**. L'ATTEIGNABILITE -- c'est-a-dire
la seule chose qui distingue un ecran livre d'un ecran que le produit a -- est
mesuree a part, dans `test_porte_du_profil_par_defaut.py`, et elle rougit tant
que les deux lignes de cablage ne sont pas posees dans `ChaineReelle`.

Les quatre points de la regle des fabriques
-------------------------------------------
* **trois profils DISTINGUABLES** au registre : trois `chain_id`, trois noms de
  fichier source, trois cardinaux de patchs et trois dates differents. Une
  fabrique uniforme rendrait invisible tout desappariement entre une ligne de
  la liste et le fichier qu'elle designe -- c'est le mutant `M33` de la 5.6 ;
* **la cible est jouee ailleurs qu'en premiere position** : le profil par
  defaut est le second des trois, et un `find` qui rendrait toujours le premier
  se demasque ;
* **la cible est jouee a CHAQUE BORD** : les trois rangs (0, 1, 2) sont joues
  pour le defaut comme pour la validation, tete et queue comprises. Un balayage
  tronque d'un bord est un **autre** mode de panne que l'aiguillage fautif, et
  c'est celui que ce depot paie le plus souvent en mutants survivants ;
* la variante multi-elements est ecrite **ici**, jamais renvoyee a la revue.

Les drapeaux qu'on fait VARIER, et pourquoi
-------------------------------------------
« Une garde qui ne fait varier aucun de ses drapeaux ne mesure qu'un seul
chemin » : le depot a paye une regression ou **11 des 14 ecrans montables**
amputaient leur bandeau en `--ascii` parce qu'aucun banc ne jouait le mode.
Sont donc joues dans les deux sens : `ascii_seul`, le profil par defaut
present / absent, le fichier valide / illisible, la zone liste / explorateur, et
le fichier d'un profil du registre present / disparu.

Tout se mesure au **plancher de 80x24** (`EPIC11-ARB-21`), jamais au-dessus :
un ecran qui tient a 100x30 et deborde a 80x24 est un defaut que seule cette
taille demasque.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_RACINE = Path(__file__).resolve().parents[3]
if str(_RACINE / "src") not in sys.path:
    sys.path.insert(0, str(_RACINE / "src"))

from mixed_media_utility.gui.depot_projets import creer_projet
from mixed_media_utility.io import (calibration_profile,
                                    profile_designation,
                                    project_layout)
from mixed_media_utility.tui import jetons, palier_profil_defaut as ppd
from mixed_media_utility.tui.coque import (Contexte, CoqueTui, EcranPasEncore,
                                           PalierTemoin)
from mixed_media_utility.tui.ecran_projet import CoutureExplorateur
from mixed_media_utility.tui.execution import EcranRefus
from mixed_media_utility.tui.explorateur import FAMILLE_PROFILS
from mixed_media_utility.tui.palier_projet import (CibleSansProjet,
                                                   apercu_de_profil)

#: Les TROIS profils du registre, **tous distinguables** : chaine, source,
#: cardinal de patchs et date different sur chacun. Le rang du defaut est
#: parametre par les tests qui en ont besoin, precisement pour que la cible
#: passe par les trois positions.
PROFILS = (
    {"chain_id": "chaine-alpha", "patchs": 21, "source": "profil-alpha.json",
     "date": "2026-08-01T10:00:00Z"},
    {"chain_id": "chaine-beta", "patchs": 33, "source": "profil-beta.json",
     "date": "2026-08-02T11:00:00Z"},
    {"chain_id": "chaine-gamma", "patchs": 47, "source": "profil-gamma.json",
     "date": "2026-08-03T12:00:00Z"},
)

#: Le rang de la cible **au milieu** : c'est celui qui demasque un `find`
#: fautif. Les deux bords sont joues par parametrage, jamais par cette
#: constante.
RANG_DU_MILIEU = 1

#: Les trois rangs, pour les tests qui balaient la liste entiere. La tete et la
#: queue y sont, et c'est le quatrieme point de la regle des fabriques.
TOUS_LES_RANGS = (0, 1, 2)


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _document(chain_id: str, *, patchs: int) -> dict:
    """Un document de profil **valide au sens du coeur**, jamais un mock.

    Il passe par `calibration_profile.validate_profile_document` a l'ecriture :
    un document fabrique a la main qui ne passerait pas cette porte mesurerait
    un ecran qui ne verra jamais ce document en production. C'est la lecon du
    2026-09-02 prise dans le bon sens -- une fixture de synthese qui fabrique
    une panne que le terrain n'a pas.
    """
    return {
        "schema_version": calibration_profile.PROFILE_SCHEMA_VERSION,
        "chain_id": chain_id,
        "correction_form_id": calibration_profile.CORRECTION_FORM_AFFINE_ID,
        "coefficients": {
            "stage_a": [[1.0, 0.0], [1.0, 0.0], [1.0, 0.0]],
            "stage_m": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        },
        "read_patch_count": patchs + 2,
        "retained_patch_count": patchs,
        "ink_floor_excluded": True,
        "source_page_id": f"page-{chain_id}",
        "template_id": "tpl-de-banc",
        "acceptance": {},
        calibration_profile.LABEL_FIELD: "",
        calibration_profile.COMMENT_FIELD: "",
    }


def _projet(tmp_path, *, profils=PROFILS, rang_du_defaut: int | None = None,
            nom="projet_demo") -> Path:
    """Un projet reel, ses profils ecrits **par le coeur** et inscrits.

    `write_profile` puis `record_designated_profile` plutot que
    `import_designated_profile` : le second n'accepte pas `designated_at`, et
    trois profils poses a la meme seconde ne seraient pas distinguables par
    leur date -- exactement le remplissage uniforme que la regle interdit.
    """
    chemin = creer_projet(tmp_path, nom).chemin
    for rang, profil in enumerate(profils):
        document = _document(profil["chain_id"], patchs=profil["patchs"])
        fichier = calibration_profile.write_profile(chemin, document)
        profile_designation.record_designated_profile(
            chemin, document, project_path=fichier, source=profil["source"],
            as_default=(rang == rang_du_defaut),
            designated_at=profil["date"])
    return chemin


def _fichier_de_profil(tmp_path, chain_id="chaine-designee", patchs=15) -> Path:
    """Un `.json` de profil **hors du projet**, tel qu'on en designe un.

    `EPIC5-ARB-82` : « le profil designe peut venir de n'importe ou ». Ce
    fichier vit donc deliberement hors de toute arborescence de projet.
    """
    cible = tmp_path / "valise" / f"{chain_id}.json"
    cible.parent.mkdir(parents=True, exist_ok=True)
    cible.write_text(json.dumps(_document(chain_id, patchs=patchs)),
                     encoding="utf-8")
    return cible


def _app(ecran, projet="projet_demo", **kwargs) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet=projet), **kwargs)


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def _ecran(dossier, confirmees=None, **kwargs):
    """Monter l'ecran de choix, et rendre `(ecran, prises)`.

    `confirmer` est **requis** : l'oubli du cablage est une erreur d'appel, pas
    un silence (finding `K3`). Le banc lui donne une liste qui collecte.
    """
    prises = [] if confirmees is None else confirmees
    return (ppd.EcranProfilParDefaut(dossier, confirmer=prises.append,
                                     **kwargs),
            prises)


def _texte(ecran) -> str:
    """Le texte **tel qu'il s'affiche**, balises de couleur retirees."""
    return jetons.texte_affiche(str(ecran._corps.content))


def _rendu(ecran, banc, app=None, **kwargs) -> str:
    async def scenario(_pilote):
        return _texte(ecran)

    return _monte(app or _app(ecran, **kwargs), scenario, banc)


# ===========================================================================
# La LISTE -- lue du registre, et jamais vide
# ===========================================================================

def test_la_liste_est_LUE_du_registre_dans_SON_ordre_et_porte_LA_PORTE(tmp_path):
    """L'ensemble des cles est mesure **exactement**, pas par `in`.

    « Une assertion positive laisse passer toute divergence supplementaire » :
    une quatrieme entree qui entrerait -- un profil balaye depuis
    `versions/calibration/`, par exemple -- ferait rougir ici.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)
    entrees = ppd.entrees_du_profil(projet)

    assert [e.cle for e in entrees] == [
        f"{ppd.PREFIXE_DE_PROFIL}0", f"{ppd.PREFIXE_DE_PROFIL}1",
        f"{ppd.PREFIXE_DE_PROFIL}2", ppd.CLE_AUTRE_FICHIER]
    # L'ordre est celui du registre, que `_upsert` trie par `chain_id` : on le
    # confronte au lecteur du coeur, jamais a une liste ecrite ici.
    lus = profile_designation.designated_profiles(projet)
    assert [e.entree["chain_id"] for e in entrees if e.est_un_profil] == [
        entree["chain_id"] for entree in lus]
    assert [e.nom for e in entrees] == [
        "profil-alpha.json", "profil-beta.json", "profil-gamma.json",
        ppd.LIBELLE_AUTRE_FICHIER]


def test_la_liste_n_est_JAMAIS_VIDE_meme_sans_aucun_profil(tmp_path):
    """Le grief d'Egan du 2026-09-06 : « pas [...] d'ecran vide (listes) ».

    Un projet neuf n'a designe aucun profil. La porte « autre fichier… » y est
    quand meme, seule : un ecran sans aucune ligne serait un blocage sec
    deguise en liste -- il n'offrirait litteralement aucune issue.
    """
    projet = _projet(tmp_path, profils=(), nom="projet_neuf")
    entrees = ppd.entrees_du_profil(projet)

    assert [e.cle for e in entrees] == [ppd.CLE_AUTRE_FICHIER]
    assert entrees[0].mention == ppd.MENTION_AUTRE_FICHIER


@pytest.mark.parametrize("rang", TOUS_LES_RANGS)
def test_le_defaut_est_reconnu_par_son_CHEMIN_a_CHAQUE_RANG(tmp_path, rang):
    """Le defaut est reconnu par `ENTRY_PATH_KEY`, jamais par `chain_id`.

    C'est la propriete meme d'`EPIC5-ARB-83`. Les **trois** rangs sont joues :
    la tete et la queue demasquent un balayage tronque, le milieu demasque un
    aiguillage qui rendrait toujours le premier.
    """
    projet = _projet(tmp_path, rang_du_defaut=rang)
    entrees = ppd.entrees_du_profil(projet)
    marques = [e.par_defaut for e in entrees if e.est_un_profil]

    assert marques == [r == rang for r in TOUS_LES_RANGS], marques
    assert entrees[rang].mention == ppd.MENTION_PAR_DEFAUT
    # Volet symetrique : sans defaut au projet, AUCUNE entree n'est marquee.
    sans = ppd.entrees_du_profil(_projet(tmp_path, nom="sans_defaut"))
    assert not any(e.par_defaut for e in sans)


def test_un_profil_dont_le_FICHIER_A_DISPARU_reste_affiche_et_le_DIT(tmp_path):
    """Trois etats, pas deux : absent, present, et **pose puis disparu**.

    Le troisieme n'est pas le premier -- le projet a travaille avec ce profil,
    et le taire ferait croire qu'il n'y en a jamais eu. L'entree reste donc
    dans la liste, sans chemin, avec sa mention propre.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)
    entrees = ppd.entrees_du_profil(projet)
    cible = entrees[RANG_DU_MILIEU]
    assert cible.chemin is not None and cible.chemin.is_file()
    cible.chemin.unlink()

    apres = ppd.entrees_du_profil(projet)[RANG_DU_MILIEU]
    assert apres.chemin is None
    assert apres.mention == ppd.MENTION_FICHIER_DISPARU
    assert apres.est_un_profil, "l'entree du registre reste, elle ne s'efface pas"
    # **Le fichier disparu passe AVANT « profil par defaut actuel »** : c'est le
    # seul des trois etats sur lequel `⏎` ne peut rien, et le taire ferait
    # proposer une ligne inerte.
    assert apres.par_defaut, "l'entree est bien celle du defaut"


def test_les_mentions_des_profils_sont_DISTINCTES_les_unes_des_autres(tmp_path):
    """Une mention uniforme rendrait invisible tout desappariement.

    Les trois profils du registre portent trois mentions differentes -- leur
    `chain_id` --, sauf celui qui est le defaut. C'est la regle des fabriques
    appliquee au **produit** et non au banc : un rendu qui apparierait la ligne
    `n` a la mention `n+1` resterait vert sur un remplissage uniforme.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)
    mentions = [e.mention for e in ppd.entrees_du_profil(projet)
                if e.est_un_profil]

    assert len(set(mentions)) == 3, mentions
    assert mentions[0] == "chaine-alpha"
    assert mentions[-1] == "chaine-gamma"


# ===========================================================================
# LE CLAVIER -- chaque touche fait quelque chose, aucune n'est muette
# ===========================================================================

@pytest.mark.parametrize("rang", TOUS_LES_RANGS)
def test_ENTREE_sur_un_profil_confirme_CELUI_LA_a_chaque_rang(tmp_path, banc,
                                                              rang):
    """`⏎` rend **le chemin du profil sous le curseur**, pas le premier.

    Les trois rangs sont joues : un rappel qui confirmerait toujours la
    premiere entree resterait vert sur elle seule, et un balayage tronque d'un
    bord ne se verrait que sur la tete ou la queue.
    """
    projet = _projet(tmp_path)
    ecran, prises = _ecran(projet)

    async def scenario(pilote):
        for _ in range(rang):
            await pilote.press("down")
        await pilote.press("enter")
        await pilote.pause()

    _monte(_app(ecran), scenario, banc)

    assert len(prises) == 1, prises
    attendu = ppd.entrees_du_profil(projet)[rang].chemin
    assert prises[0] == attendu
    # La cible n'est pas devinee : c'est bien le fichier du profil de ce rang.
    document = json.loads(Path(prises[0]).read_text(encoding="utf-8"))
    assert document["chain_id"] == PROFILS[rang]["chain_id"]


def test_ENTREE_sur_autre_fichier_OUVRE_l_explorateur(tmp_path, banc):
    """La porte ouvre, elle ne confirme rien : il n'y a rien a confirmer.

    Consommer la touche sur rien serait indistinguable d'un clavier casse.
    """
    projet = _projet(tmp_path)
    ecran, prises = _ecran(projet)

    async def scenario(pilote):
        for _ in range(len(PROFILS)):
            await pilote.press("down")
        await pilote.press("enter")
        await pilote.pause()
        return ecran.zone, ecran.raccourcis

    zone, raccourcis = _monte(_app(ecran), scenario, banc)

    assert zone == ppd.ZONE_EXPLORATEUR
    assert prises == [], "ouvrir l'explorateur ne confirme aucun profil"
    # La ligne de raccourcis suit la zone : elle est **contextuelle**.
    assert raccourcis != ppd.RACCOURCIS_PROFIL


def test_ENTREE_sur_un_profil_SANS_FICHIER_ne_bloque_pas_et_le_DIT(tmp_path,
                                                                   banc):
    """`EPIC11-ARB-89` : jamais un blocage sec, jamais une touche muette.

    Le fichier du profil vise a disparu : `⏎` ne peut rien poser. Il ne ferme
    pas l'ecran et ne leve pas -- il **nomme** ce qui manque en ligne d'etat, et
    la porte « autre fichier… » reste a un rang de la.
    """
    projet = _projet(tmp_path)
    ppd.entrees_du_profil(projet)[RANG_DU_MILIEU].chemin.unlink()
    ecran, prises = _ecran(projet)

    async def scenario(pilote):
        for _ in range(RANG_DU_MILIEU):
            await pilote.press("down")
        await pilote.press("enter")
        await pilote.pause()
        return ecran.etat(), ecran.zone

    etat, zone = _monte(_app(ecran), scenario, banc)

    assert prises == [], "rien ne peut etre confirme sur un fichier absent"
    assert zone == ppd.ZONE_LISTE, "l'ecran ne se ferme pas"
    assert ppd.MENTION_FICHIER_DISPARU in etat, etat
    # L'issue reste offerte : la porte vers un fichier est toujours la.
    assert ppd.CLE_AUTRE_FICHIER in [e.cle for e in ecran.choix.entrees]


def test_une_LETTRE_est_consommee_et_ne_ferme_PAS_l_application(tmp_path):
    """La ligne de raccourcis n'annonce aucune sortie par lettre.

    Laisser remonter la frappe jusqu'au binding applicatif `q` fermerait
    l'application sur une touche que rien n'annonce -- le defaut mesure sur
    l'explorateur, paye une fois deja.
    """
    ecran, _ = _ecran(_projet(tmp_path))

    assert ecran.traiter("q", "q") is True
    assert ecran.traiter("z", "z") is True
    # Symetrique : une touche que l'ecran n'a **pas** a consommer traverse.
    assert ecran.traiter("escape") is False
    assert ecran.traiter("f1") is False


# ===========================================================================
# L'EXPLORATEUR -- le refus du coeur voyage VERBATIM, l'ecran ne se ferme pas
# ===========================================================================

def test_la_couture_clavier_est_le_MIXIN_du_depot_et_la_famille_est_POSEE():
    """`EPIC11-ARB-48` : un composant unique partout ou la TUI demande un chemin.

    Un site qui reimplementerait son routage clavier ne tiendrait que la moitie
    de la promesse -- le modele serait commun, le comportement non.
    """
    assert issubclass(ppd.EcranProfilParDefaut, CoutureExplorateur)
    bases = ppd.EcranProfilParDefaut.__mro__
    from mixed_media_utility.tui.coque import Palier
    assert bases.index(CoutureExplorateur) < bases.index(Palier), bases
    # La famille de memoire de session : les profils sont une famille A PART.
    assert ppd.EcranProfilParDefaut.FAMILLE_D_EXPLORATION == FAMILLE_PROFILS


def test_le_filtre_de_l_explorateur_retient_les_JSON_et_RIEN_d_autre(tmp_path):
    """Volet negatif compris : un `.tiff` et un `.JSON` majuscule.

    Le second est le piege : un filtre ecrit sans `lower()` refuserait un
    fichier parfaitement valide venu d'un autre systeme de fichiers.
    """
    assert ppd.profil_acceptable(Path("a/profil.json")) is True
    assert ppd.profil_acceptable(Path("a/PROFIL.JSON")) is True
    assert ppd.profil_acceptable(Path("a/page.tiff")) is False
    assert ppd.profil_acceptable(Path("a/sans-suffixe")) is False


def test_un_fichier_ILLISIBLE_laisse_sur_l_explorateur_avec_le_motif_VERBATIM(
        tmp_path, banc):
    """`EPIC11-ARB-30` : le motif vient du coeur et la TUI ne le resume pas.

    La cible est fautive, pas le geste : refermer l'explorateur ferait
    recommencer la navigation. Le choix precedent reste actif **sans qu'aucune
    restauration ait a etre ecrite** : rien n'a ete pose.
    """
    projet = _projet(tmp_path)
    faux = tmp_path / "valise" / "pas-un-profil.json"
    faux.parent.mkdir(parents=True, exist_ok=True)
    faux.write_text("{ ceci n'est pas un profil", encoding="utf-8")
    ecran, prises = _ecran(projet)

    async def scenario(pilote):
        ecran.zone = ppd.ZONE_EXPLORATEUR
        ecran.explorateur.dossier = faux.parent
        ecran.explorateur.relire()
        ecran._valider_l_explorateur()
        await pilote.pause()
        return ecran.zone, ecran.etat()

    zone, etat = _monte(_app(ecran), scenario, banc)

    # La phrase du coeur, mot pour mot : on la releve en la relevant.
    with pytest.raises(profile_designation.ProfileDesignationError) as leve:
        profile_designation.read_designated_document(faux)
    assert str(leve.value) in etat, (etat, str(leve.value))
    assert zone == ppd.ZONE_EXPLORATEUR, "l'ecran est reste sur l'explorateur"
    assert prises == [], "un fichier refuse ne confirme rien"
    assert ppd.CLE_FICHIER_DESIGNE not in [e.cle for e in ecran.choix.entrees]


def test_un_fichier_VALIDE_prend_SA_PROPRE_LIGNE_avant_la_porte(tmp_path, banc):
    """Le cul-de-sac evite, mesure en marchant le parcours.

    Si « autre fichier… » devenait elle-meme le choix retenu, il n'y aurait
    plus aucune touche pour en designer un autre. Le fichier prend donc sa
    ligne **juste avant** la porte, le curseur s'y pose, et la porte reste.
    """
    projet = _projet(tmp_path)
    cible = _fichier_de_profil(tmp_path)
    ecran, _ = _ecran(projet)

    async def scenario(pilote):
        ecran.zone = ppd.ZONE_EXPLORATEUR
        ecran.explorateur.dossier = cible.parent
        ecran.explorateur.relire()
        ecran._valider_l_explorateur()
        await pilote.pause()
        return [e.cle for e in ecran.choix.entrees], ecran.choix.curseur, ecran.zone

    cles, curseur, zone = _monte(_app(ecran), scenario, banc)

    assert cles == [f"{ppd.PREFIXE_DE_PROFIL}0", f"{ppd.PREFIXE_DE_PROFIL}1",
                    f"{ppd.PREFIXE_DE_PROFIL}2", ppd.CLE_FICHIER_DESIGNE,
                    ppd.CLE_AUTRE_FICHIER]
    assert cles[curseur] == ppd.CLE_FICHIER_DESIGNE
    assert zone == ppd.ZONE_LISTE
    assert ecran.choix.courante.chemin == cible


def test_designer_un_SECOND_fichier_REMPLACE_la_ligne_au_lieu_d_en_ajouter(
        tmp_path, banc):
    """Deux lignes pour un choix unique laisseraient retenir un fichier remplace."""
    projet = _projet(tmp_path)
    premier = _fichier_de_profil(tmp_path, "chaine-un")
    second = _fichier_de_profil(tmp_path, "chaine-deux")
    ecran, _ = _ecran(projet)

    async def scenario(pilote):
        for cible in (premier, second):
            ecran.zone = ppd.ZONE_EXPLORATEUR
            ecran.explorateur.dossier = cible.parent
            ecran.explorateur.relire()
            ecran.choix.poser_le_fichier(cible)
        await pilote.pause()
        return [e.cle for e in ecran.choix.entrees]

    cles = _monte(_app(ecran), scenario, banc)

    assert cles.count(ppd.CLE_FICHIER_DESIGNE) == 1, cles
    assert ecran.choix.fichier == second


def test_ECHAP_sort_de_l_explorateur_et_ne_remonte_JAMAIS_d_un_dossier(tmp_path):
    """`EPIC11-ARB-2` : `Échap` sort, `←` remonte. Deux touches, deux sens."""
    ecran, _ = _ecran(_projet(tmp_path))
    ecran.zone = ppd.ZONE_EXPLORATEUR
    depart = ecran.explorateur.dossier

    assert ecran._sortir_de_l_explorateur() is True
    assert ecran.zone == ppd.ZONE_LISTE
    assert ecran.explorateur.dossier == depart, "Échap n'a pas navigue"


# ===========================================================================
# `EPIC11-ARB-4` -- l'APERCU precede l'ecriture, et il n'ecrit RIEN
# ===========================================================================

def _empreinte(dossier: Path) -> set[tuple[str, int]]:
    """Ce que le disque du projet porte, taille comprise.

    C'est la seule facon de mesurer qu'un apercu **n'ecrit rien** : compter les
    fichiers laisserait passer une reecriture en place.
    """
    return {(str(f.relative_to(dossier)), f.stat().st_size)
            for f in sorted(dossier.rglob("*")) if f.is_file()}


def test_l_APERCU_ne_touche_pas_au_disque_du_projet(tmp_path):
    """`EPIC11-ARB-4` : le panneau chiffre precede toute ecriture.

    Un apercu construit sur le resultat de la pose serait un panneau **de
    resultat** portant le titre « A ecrire » : il ne pourrait plus rien
    empecher.
    """
    projet = _projet(tmp_path)
    cible = _fichier_de_profil(tmp_path)
    avant = _empreinte(projet)

    apercu = apercu_de_profil(projet, cible)
    panneau = ppd.panneau_de_la_pose(apercu)

    assert _empreinte(projet) == avant, "l'apercu a ecrit sur le disque"
    assert panneau.titre == "A ecrire"
    rendu = "\n".join(panneau.rendu(80))
    assert "chaine-designee" in rendu
    assert apercu.chemin.name in rendu


def test_le_point_de_jugement_offre_DEUX_issues_dont_une_qui_N_ECRIT_PAS(
        tmp_path):
    """`EPIC11-ARB-89` et `EPIC11-ARB-7`, mesures ensemble.

    Deux issues, une seule ecrit, et le curseur **ne part pas** sur celle-la :
    l'ecriture n'est jamais atteignable en une frappe.
    """
    choix = ppd.issues_de_la_pose(remplace=False)

    assert [i.cle for i in choix.issues] == [ppd.CLE_POSER, ppd.CLE_ANNULER]
    assert [i.ecrit for i in choix.issues] == [True, False]
    assert choix.issues[choix.curseur].ecrit is False
    assert choix.retenue is None, "aucune issue n'est preselectionnee"


@pytest.mark.parametrize("remplace,libelle", [
    (False, ppd.LIBELLE_POSER),
    (True, ppd.LIBELLE_REMPLACER),
])
def test_l_issue_qui_ecrit_CHANGE_DE_MOT_quand_un_defaut_existe_deja(remplace,
                                                                    libelle):
    """Le mot n'est pas cosmetique : c'est l'avertissement d'`EPIC11-ARB-89`.

    Les deux sens sont joues -- « une garde qui ne fait varier aucun de ses
    drapeaux ne mesure qu'un seul chemin ». Un libelle fige ferait remplacer un
    defaut sans le dire, c'est-a-dire une ecriture non avertie.
    """
    choix = ppd.issues_de_la_pose(remplace)
    action = next(i for i in choix.issues if i.ecrit)

    assert action.libelle.startswith(libelle), action.libelle
    autre = ppd.LIBELLE_REMPLACER if not remplace else ppd.LIBELLE_POSER
    assert autre not in action.libelle


@pytest.mark.parametrize("remplace", [False, True])
@pytest.mark.parametrize("ascii_seul", [False, True])
def test_aucune_ISSUE_n_est_ABREGEE_au_plancher(remplace, ascii_seul):
    """Une issue dont le COUT est coupe est une ecriture non avertie.

    Mesure faite en marchant le parcours : la premiere redaction de
    `MENTION_REMPLACE` sortait a 88 colonnes au plancher et se faisait couper
    **a la mention** -- l'operateur lisait « Remplacer le profil par défaut —
    l'ancien reste sur le disque, il cesse d… ». C'est le seul endroit de
    l'ecran qui dise ce que l'issue coute, et `EPIC11-ARB-89` exige
    l'avertissement avant une ecriture consciente.

    Les DEUX drapeaux varient : le mode de repli -- `—` vaut une colonne, `--`
    en vaut deux, donc l'ASCII est le pire des deux cas -- et l'existence d'un
    defaut a remplacer, dont depend le libelle le plus long.
    """
    choix = ppd.issues_de_la_pose(remplace)
    points = jetons.points_d_abregement(ascii_seul)
    utile = jetons.largeur_utile(80)

    for ligne in choix.rendu(ascii_seul=ascii_seul):
        pose = jetons.ajuster(ligne, utile, ascii_seul)
        assert not pose.rstrip().endswith(points), pose
        assert jetons.colonnes(pose.rstrip()) <= utile, pose


def test_le_cartouche_NOMME_le_defaut_remplace_et_SEULEMENT_alors(tmp_path):
    """Les deux sens du drapeau, sur le cartouche cette fois.

    Sans defaut pose, la quatrieme ligne n'existe pas : l'ecrire a vide ferait
    annoncer un remplacement qui n'a pas lieu.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)
    apercu = apercu_de_profil(projet, _fichier_de_profil(tmp_path))

    avec = ppd.panneau_de_la_pose(apercu, "profil-beta.json")
    sans = ppd.panneau_de_la_pose(apercu, "")

    assert len(avec.lignes) == len(sans.lignes) + 1
    assert ppd.LIBELLE_DEFAUT_ACTUEL in "\n".join(avec.rendu(80))
    assert ppd.LIBELLE_DEFAUT_ACTUEL not in "\n".join(sans.rendu(80))
    assert "profil-beta.json" in "\n".join(avec.rendu(80))


def test_les_TROIS_valeurs_du_cartouche_viennent_de_palier_projet(tmp_path):
    """Une seule redaction de « ce qu'une pose de profil ecrit ».

    Les recopier ici en ferait une seconde, qui divergerait au premier
    ajustement -- et l'ecart ne se verrait que sur l'ecran, jamais dans le
    coeur. La mesure porte donc sur l'**egalite** des deux rendus.
    """
    from mixed_media_utility.tui.palier_projet import panneau_de_profil

    projet = _projet(tmp_path)
    apercu = apercu_de_profil(projet, _fichier_de_profil(tmp_path))

    assert ppd.panneau_de_la_pose(apercu).lignes == panneau_de_profil(
        apercu).lignes
    # Le compte rendu porte les MEMES trois lignes, plus l'emplacement.
    pose = ppd.panneau_du_profil_pose(apercu)
    assert pose.lignes[:3] == panneau_de_profil(apercu).lignes
    assert pose.titre == ppd.TITRE_ECRIT != panneau_de_profil(apercu).titre


# ===========================================================================
# LA POSE -- elle passe par le coeur, et elle DIT ce qu'elle a fait
# ===========================================================================

def test_la_POSE_ecrit_par_le_COEUR_et_inscrit_le_defaut(tmp_path):
    """`poser_le_profil_par_defaut` et rien d'autre.

    Ce parcours n'ecrit ni le fichier ni l'entree de manifest : l'artefact
    produit est identique a celui de `mmu set-default-profile` **par
    construction** plutot que par verification. La mesure porte donc sur le
    disque, pas sur un appel espionne.
    """
    from mixed_media_utility.tui.palier_projet import poser_le_profil_par_defaut

    projet = _projet(tmp_path, profils=(), nom="projet_neuf")
    cible = _fichier_de_profil(tmp_path)
    assert profile_designation.default_profile_entry(projet) is None

    pose = poser_le_profil_par_defaut(projet, cible)

    entree = profile_designation.default_profile_entry(projet)
    assert entree is not None
    assert entree["chain_id"] == "chaine-designee"
    assert profile_designation.default_profile_path(projet) == pose.chemin
    assert pose.chemin.is_file()


def test_l_ecran_de_SUCCES_nomme_le_fichier_ecrit_et_la_chaine(tmp_path, banc):
    """Le grief separe d'Egan : « pas d'ecran de succes [...] incoherent ».

    Un geste qui ecrit et rend la main sans compte rendu est indistinguable
    d'un geste qui n'a rien fait.
    """
    from mixed_media_utility.tui.palier_projet import poser_le_profil_par_defaut

    projet = _projet(tmp_path, profils=(), nom="projet_neuf")
    pose = poser_le_profil_par_defaut(projet, _fichier_de_profil(tmp_path))
    ecran = ppd.EcranProfilPose(ppd.panneau_du_profil_pose(pose),
                                objet=ppd.OBJET_DU_BANDEAU)

    async def scenario(_pilote):
        return jetons.texte_affiche(str(ecran._corps.content))

    rendu = _monte(_app(ecran), scenario, banc)

    assert ppd.TITRE_ECRIT == ecran.panneau.titre
    assert pose.chemin.name in rendu, rendu
    assert "chaine-designee" in rendu, rendu
    # **« Retour aux ateliers » n'est ecrit qu'UNE fois** : `EcranResultat`
    # l'ajoute d'office, et l'ecrire ici en ferait deux lignes pour une sortie.
    assert ecran.suites.count(ppd.EcranProfilPose.RETOUR) == 1, ecran.suites
    assert ppd.ETAT_POSE in ppd.ligne_d_etat_de_la_pose(pose)
    assert pose.chaine in ppd.ligne_d_etat_de_la_pose(pose)


def test_le_parcours_COMPLET_apercu_puis_pose_puis_compte_rendu(tmp_path, banc):
    """Les trois temps, enchaines par le cablage reel, sur le disque reel.

    C'est ce qu'`EPIC11-ARB-4` exige, mesure de bout en bout : la confirmation
    monte **avant** que quoi que ce soit ne soit ecrit, et le fichier
    n'apparait qu'apres l'issue retenue.
    """
    projet = _projet(tmp_path, profils=(), nom="projet_neuf")
    cible = _fichier_de_profil(tmp_path)
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter")],
                   contexte=Contexte(projet="projet_neuf"))

    async def scenario(pilote):
        assert ppd.ouvrir_le_profil_par_defaut(pilote.app, projet) is True
        await pilote.pause()
        choix = pilote.app.screen
        assert isinstance(choix, ppd.EcranProfilParDefaut), type(choix).__name__
        # On designe le fichier comme l'explorateur le ferait, puis on valide.
        choix.choix.poser_le_fichier(cible)
        await pilote.press("enter")
        await pilote.pause()
        jugement = pilote.app.screen
        assert isinstance(jugement, ppd.EcranPoseDuProfil), type(jugement).__name__
        avant = profile_designation.default_profile_entry(projet)
        # L'issue qui ecrit est en tete ; le curseur part sur celle qui n'ecrit
        # pas. On le remonte d'un cran, exactement comme l'operateur.
        await pilote.press("up")
        await pilote.press("enter")
        await pilote.pause()
        return avant, pilote.app.screen

    avant, ecran = banc(app, scenario)

    assert avant is None, "le point de jugement avait deja ecrit"
    assert isinstance(ecran, ppd.EcranProfilPose), type(ecran).__name__
    apres = profile_designation.default_profile_entry(projet)
    assert apres is not None and apres["chain_id"] == "chaine-designee"


def test_ANNULER_ne_touche_a_RIEN_et_DEPILE(tmp_path, banc):
    """Volet symetrique de la pose : l'autre issue existe et elle marche.

    Une annulation qui ne rendrait pas la main serait un blocage sec
    (`EPIC11-ARB-89`). Elle **depile**, ce qui est ce que `Échap` fait deja sur
    cet ecran -- et elle n'est volontairement pas un rappel injecte : un
    `annuler: Callable | None = None` assorti d'un `if ... is not None` serait
    un point d'injection que personne n'injecte, donc une branche morte
    qu'aucune garde ne distingue d'un oubli. `test_rappels_cables.py` l'a
    mesuree comme telle, et c'est ce qui a fait retirer le parametre.

    Le curseur part sur « Annuler » -- `ChoixExclusif` le pose sur la premiere
    issue qui n'ecrit pas --, donc `⏎` seul suffit : c'est le geste de
    l'operateur qui valide par reflexe, et il ne doit rien ecrire.
    """
    projet = _projet(tmp_path, profils=(), nom="projet_neuf")
    cible = _fichier_de_profil(tmp_path)
    poses = []
    apercu = apercu_de_profil(projet, cible)
    ecran = ppd.EcranPoseDuProfil(apercu, cible, poser=poses.append)
    # **DEUX paliers sous le jugement, et ce n'est pas du decor** :
    # `CoqueTui.rang` ne compte que les paliers NON transitoires, et
    # `action_remonter` refuse de depiler au rang zero. Un banc qui poserait le
    # jugement sur un palier unique mesurerait cette garde-la, pas
    # l'annulation -- et conclurait a un blocage sec qui n'existe pas. La pile
    # reelle du produit en porte quatre : projet, ateliers, palier Projet,
    # ecran de choix.
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"),
                            PalierTemoin("Projet", "Q quitter")],
                   contexte=Contexte(projet="projet_neuf"))

    async def scenario(pilote):
        # Le jugement est **empile par-dessus** son palier, comme le parcours
        # le monte.
        pilote.app.descendre()
        await pilote.pause()
        pilote.app.descendre(ecran)
        await pilote.pause()
        assert pilote.app.screen is ecran, type(pilote.app.screen).__name__
        await pilote.press("enter")
        await pilote.pause()
        return pilote.app.screen

    dessus = banc(app, scenario)

    assert poses == [], "l'annulation a declenche l'ecriture"
    assert dessus is not ecran, "l'ecran de jugement est reste : blocage sec"
    assert profile_designation.default_profile_entry(projet) is None


# ===========================================================================
# LES REFUS -- un ECRAN, jamais une trace de pile
# ===========================================================================

def test_une_CIBLE_QUI_N_EST_PAS_UN_PROJET_rend_un_ECRAN_de_refus(tmp_path,
                                                                  banc):
    """`CibleSansProjet` : la garde que le coeur n'a pas, et qui vit dans la TUI.

    `import_designated_profile` ecrit dans **n'importe quel** dossier ; le refus
    est pose dans `cli.py` avant l'appel, donc tout appelant de `io/` le saute.
    Sans cet ecran, un dossier quelconque recevrait une arborescence
    `versions/calibration/`.
    """
    pas_un_projet = tmp_path / "dossier_quelconque"
    pas_un_projet.mkdir()
    cible = _fichier_de_profil(tmp_path)
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter")],
                   contexte=Contexte(projet="-"))

    async def scenario(pilote):
        assert ppd.ouvrir_le_profil_par_defaut(pilote.app, pas_un_projet)
        await pilote.pause()
        pilote.app.screen.choix.poser_le_fichier(cible)
        await pilote.press("enter")
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)

    assert isinstance(ecran, EcranRefus), type(ecran).__name__
    with pytest.raises(CibleSansProjet) as leve:
        apercu_de_profil(pas_un_projet, cible)
    assert ecran.message == str(leve.value)
    assert ecran.code == "CIBLE_SANS_PROJET"
    assert not (pas_un_projet
                / project_layout.VERSIONS_DIRNAME).exists(), (
        "le refus a quand meme ecrit")


def test_le_code_du_refus_DISTINGUE_les_deux_familles_et_tient_aux_BORDS():
    """Une derivation, pas une table : elle nomme un refus qu'elle n'a jamais vu.

    Une table serait une seconde redaction qui perimerait **en silence** le jour
    ou un refus de plus serait publie. Un refus de synthese, inconnu du module,
    le mesure.
    """
    class RefusInedit(ValueError):
        """Un refus publie demain."""

    codes = [ppd.code_du_refus(CibleSansProjet("x")),
             ppd.code_du_refus(profile_designation.ProfileDesignationError("y")),
             ppd.code_du_refus(RefusInedit("z"))]

    assert len(set(codes)) == 3, codes
    assert codes[0] == "CIBLE_SANS_PROJET"
    assert codes[-1] == "REFUS_INEDIT"
    assert all(c.isupper() and " " not in c for c in codes), codes


def test_SANS_PROJET_OUVERT_on_nomme_ce_qui_manque_ET_son_echeance(banc):
    """`MQ-8` pris a l'avance : un `EcranPasEncore` sans echeance est un abandon.

    « comme ca on sait que c'est temporaire et que ce n'est pas un bug »
    (Egan, 2026-08-28).
    """
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter")],
                   contexte=Contexte(projet="-"))

    async def scenario(pilote):
        assert ppd.ouvrir_le_profil_par_defaut(pilote.app, None) is True
        await pilote.pause()
        return pilote.app.screen

    ecran = banc(app, scenario)

    assert isinstance(ecran, EcranPasEncore), type(ecran).__name__
    assert str(ecran.ce_qui_manque) == ppd.CE_QUI_MANQUE_SANS_PROJET
    assert str(ecran.quand) == ppd.QUAND_LE_PROFIL_PAR_DEFAUT


def test_sans_application_montee_l_ouverture_rend_FAUX_et_ne_bouge_RIEN(tmp_path):
    """La troisieme sortie, et l'appelant sait que rien n'a bouge.

    Le regime est celui d'un ecran **construit a nu**, comme les bancs en
    montent : `textual` fait de `Screen.app` une propriete qui **leve** hors
    montage, et `_application_montee` est ce qui transforme cette levee en
    reponse. Un objet quelconque ne mesurerait pas ce regime -- il rendrait un
    `AttributeError`, qui n'est pas ce que le produit rencontre.
    """
    projet = _projet(tmp_path)
    avant = _empreinte(projet)

    assert ppd.ouvrir_le_profil_par_defaut(
        PalierTemoin("Ateliers", "Q quitter"), projet) is False
    assert _empreinte(projet) == avant


def test_le_rappel_de_confirmation_est_REQUIS_sans_defaut(tmp_path):
    """Finding `K3`, paye quatre fois dans cet epic.

    « Un `Callable | None = None` assorti d'un `if ... is not None` fait de
    l'oubli de cablage un silence. » L'ecran ne sait pas ce qui suit le choix :
    il ne peut simplement pas etre monte sans savoir a qui le rendre.
    """
    with pytest.raises(TypeError):
        ppd.EcranProfilParDefaut(_projet(tmp_path))
    with pytest.raises(TypeError):
        ppd.EcranPoseDuProfil(object(), Path("x.json"))


# ===========================================================================
# LE REPLI ASCII et le PLANCHER 80x24 -- le drapeau varie dans les DEUX sens
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", [False, True])
@pytest.mark.parametrize("zone", [ppd.ZONE_LISTE, ppd.ZONE_EXPLORATEUR])
def test_aucune_ligne_ne_DEBORDE_au_plancher_dans_les_DEUX_modes(
        tmp_path, banc, ascii_seul, zone):
    """Le plancher est 80x24, et le mode se joue **dans les deux sens**.

    Le depot a paye une regression ou 11 des 14 ecrans montables amputaient
    leur bandeau en `--ascii` : le bandeau etait calibre en geometrie UTF-8
    puis replie, donc coupe a droite. La mesure porte donc sur le bandeau
    **et** sur la zone centrale, dans les deux modes.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)
    ecran, _ = _ecran(projet)
    ecran.zone = zone
    utile = jetons.largeur_utile(80)

    async def scenario(_pilote):
        return ecran.lignes(), ecran.bandeau(80), ecran.etat(), ecran.raccourcis

    lignes, bandeau, etat, raccourcis = _monte(
        _app(ecran, ascii_seul=ascii_seul), scenario, banc)

    for ligne in lignes + [bandeau, etat, raccourcis]:
        assert jetons.colonnes(ligne) <= utile, (jetons.colonnes(ligne), ligne)
    # La zone centrale porte dix-sept lignes au plancher : un ecran qui en rend
    # davantage se fait couper par le bas, sans un mot.
    assert len(lignes) <= jetons.hauteur_centrale(24), len(lignes)


@pytest.mark.parametrize("zone", [ppd.ZONE_LISTE, ppd.ZONE_EXPLORATEUR])
def test_le_mode_ASCII_change_REELLEMENT_le_rendu(tmp_path, banc, zone):
    """Volet symetrique : sans lui, la garde ci-dessus passerait sur un ecran
    qui ignorerait `ascii_seul` de bout en bout.

    Un banc qui ne joue qu'un mode « mesure la moitie du produit et l'annonce
    verte ».
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)

    rendus = {}
    for ascii_seul in (False, True):
        ecran, _ = _ecran(projet)
        ecran.zone = zone
        rendus[ascii_seul] = _rendu(ecran, banc, _app(ecran,
                                                      ascii_seul=ascii_seul))

    assert rendus[True] != rendus[False], "le repli n'a rien change"
    assert rendus[True].isascii(), rendus[True]
    assert not rendus[False].isascii(), "le mode nominal a perdu ses glyphes"


def test_la_COLONNE_des_mentions_est_la_MEME_dans_les_deux_modes(tmp_path,
                                                                 banc):
    """Le defaut que le repli tardif produit, et il a ete mesure ici.

    `jetons.abreger_nom` ne replie **que** ce qu'il abrege : un nom qui tient
    en ressort intact, et `jetons.ajuster` le replie ensuite -- une fois la
    colonne posee. La porte s'appelle `autre fichier…` ; `…` vaut une colonne,
    `...` en vaut trois. Sa mention partait donc DEUX colonnes plus a droite
    que les trois autres en `--ascii`, et l'oeil perdait la colonne que ce
    calage existe pour tenir.

    La mesure porte sur l'**ensemble des colonnes d'ouverture**, pas sur une
    ligne : une seule ligne decalee est invisible a une assertion prise ligne
    par ligne, et c'est exactement ce regime-la -- trois lignes justes, une
    fausse. **Le meme defaut vit dans `E3-5`**, d'ou cet ecran est decline ; il
    est remonte plutot que corrige ici.
    """
    projet = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)
    colonnes = {}
    for ascii_seul in (False, True):
        ecran, _ = _ecran(projet)
        utile = jetons.largeur_utile(80)

        async def scenario(_pilote, e=ecran, u=utile, a=ascii_seul):
            # La colonne d'OUVERTURE de la mention, mesuree en colonnes de
            # terminal et non en caracteres : `len()` mentirait sur un nom en
            # double chasse, et c'est le defaut jumeau de celui-ci.
            ouvertures = set()
            for rang, entree in enumerate(e.choix.entrees):
                ligne = e.ligne_d_entree(rang, u)
                mention = jetons.replier_ascii(entree.mention) if a \
                    else entree.mention
                ouvertures.add(jetons.colonnes(ligne[:ligne.index(mention)]))
            return ouvertures

        colonnes[ascii_seul] = _monte(_app(ecran, ascii_seul=ascii_seul),
                                      scenario, banc)

    assert len(colonnes[False]) == 1, colonnes[False]
    assert colonnes[True] == colonnes[False], colonnes


def test_le_pied_dit_les_TROIS_etats_du_defaut(tmp_path, banc):
    """Aucun defaut, un defaut present, un defaut dont le fichier a disparu.

    Le troisieme n'est pas le premier, et c'est la distinction que le palier
    Projet tient deja un cran au-dessus.
    """
    sans = _projet(tmp_path, profils=(), nom="projet_neuf")
    avec = _projet(tmp_path, rang_du_defaut=RANG_DU_MILIEU)

    ecran_sans, _ = _ecran(sans)
    ecran_avec, _ = _ecran(avec)
    pied_sans = _monte(_app(ecran_sans),
                       lambda _p: _renvoyer(ecran_sans.lignes_du_pied()), banc)
    pied_avec = _monte(_app(ecran_avec),
                       lambda _p: _renvoyer(ecran_avec.lignes_du_pied()), banc)

    assert ppd.ETAT_SANS_DEFAUT in "".join(pied_sans)
    assert "profil-beta.json" in "".join(pied_avec)
    assert ppd.MENTION_FICHIER_DISPARU not in "".join(pied_avec)

    # Troisieme etat : le fichier du defaut disparait sous les pieds.
    ppd.entrees_du_profil(avec)[RANG_DU_MILIEU].chemin.unlink()
    ecran_perdu, _ = _ecran(avec)
    pied_perdu = _monte(_app(ecran_perdu),
                        lambda _p: _renvoyer(ecran_perdu.lignes_du_pied()),
                        banc)
    assert "profil-beta.json" in "".join(pied_perdu)
    assert ppd.MENTION_FICHIER_DISPARU in "".join(pied_perdu)


async def _renvoyer(valeur):
    """Rendre une valeur deja calculee depuis un scenario de banc."""
    return valeur


def test_la_ligne_d_etat_est_une_MESURE_et_compte_les_trois_formes(tmp_path,
                                                                   banc):
    """`EPIC11-ARB-56` : une mesure, jamais une touche ni un conseil.

    Les trois formes du cardinal sont jouees -- zero, un, plusieurs. Le cas a
    un est le seul ou la faute d'accord se voie, et c'est celui qu'une fabrique
    porte.
    """
    cardinaux = {
        0: ppd.ETAT_SANS_PROFIL,
        1: ppd.ETAT_UN_PROFIL,
        3: ppd.ETAT_DES_PROFILS.format(profils=3),
    }
    for combien, attendu in cardinaux.items():
        projet = _projet(tmp_path, profils=PROFILS[:combien],
                         nom=f"projet_{combien}")
        ecran, _ = _ecran(projet)
        etat = _monte(_app(ecran), lambda _p: _renvoyer(ecran.etat()), banc)
        assert attendu in etat, (combien, etat)
        # Aucune touche dans la ligne d'etat : c'est l'arbitrage, a la lettre.
        assert "⏎" not in etat and "Échap" not in etat, etat


def test_la_ligne_de_raccourcis_de_la_LISTE_n_annonce_aucune_LETTRE():
    """`EPIC11-ARB-68` : une lettre annoncee ici serait une lettre consommee
    ailleurs. La frappe imprimable est prise par l'ecran ; l'annoncer ferait
    croire a une sortie qui n'existe pas."""
    mots = ppd.RACCOURCIS_PROFIL.split()
    lettres = [m for m in mots if len(m) == 1 and m.isalpha()]

    assert lettres == [], ppd.RACCOURCIS_PROFIL
    assert "Q quitter" not in ppd.RACCOURCIS_PROFIL
    # Elle tient la grille du plancher, replis compris.
    for ligne in (ppd.RACCOURCIS_PROFIL, ppd.RACCOURCIS_POSE):
        assert jetons.colonnes(ligne) <= jetons.largeur_utile(80), ligne
        assert jetons.replier_ascii(ligne).isascii(), ligne


def test_le_RETOUR_sur_l_ecran_relit_le_registre(tmp_path, banc):
    """`Palier.reprendre` : un menu qui ne relit pas garde l'etat d'avant.

    C'est le defaut `V2-M2` -- « un menu gardait les compteurs du projet
    precedent ». Ici, un profil pose entre-temps doit apparaitre.
    """
    from mixed_media_utility.tui.palier_projet import poser_le_profil_par_defaut

    projet = _projet(tmp_path, profils=(), nom="projet_neuf")
    ecran, _ = _ecran(projet)

    async def scenario(pilote):
        avant = [e.cle for e in ecran.choix.entrees]
        poser_le_profil_par_defaut(projet, _fichier_de_profil(tmp_path))
        ecran.reprendre()
        await pilote.pause()
        return avant, [e.cle for e in ecran.choix.entrees]

    avant, apres = _monte(_app(ecran), scenario, banc)

    assert avant == [ppd.CLE_AUTRE_FICHIER]
    assert apres == [f"{ppd.PREFIXE_DE_PROFIL}0", ppd.CLE_AUTRE_FICHIER]


def test_le_MOTIF_d_un_refus_ne_SURVIT_pas_a_la_frappe_suivante(tmp_path, banc):
    """Un refus s'efface a la frappe d'apres, **dans les deux zones**.

    Le motif ne l'etait que dans la liste : `traiter` posait
    `self._etat_a_dire = ""` **apres** l'aiguillage vers l'explorateur, si bien
    qu'un refus pose par `_valider_l_explorateur` survivait a tout ce qui
    suivait.

    Les deux regimes ou ca mord, et le second est le pire :

    * on bouge le curseur dans l'explorateur -- la ligne d'etat continue
      d'accuser le fichier **precedent**, celui qui n'est plus sous le
      curseur ;
    * on designe ensuite un fichier **valide** -- il est accepte, sa ligne est
      posee, on revient a la liste, et la ligne d'etat porte encore le refus
      du fichier d'avant. Une ligne d'etat qui accuse un fichier accepte est
      un chemin d'erreur qui **ment**, et c'est ce que `EPIC11-ARB-56` -- « la
      ligne d'etat porte une mesure » -- interdit litteralement.

    Le drapeau qu'on fait varier ici est la ZONE, dans les deux sens : c'est
    la garde de mode dont l'absence a laisse le defaut vivre.
    """
    projet = _projet(tmp_path)
    faux = tmp_path / "valise" / "a-pas-un-profil.json"
    faux.parent.mkdir(parents=True, exist_ok=True)
    faux.write_text("{ ceci n'est pas un profil", encoding="utf-8")
    bon = _fichier_de_profil(tmp_path, "chaine-designee")
    assert bon.parent == faux.parent, "les deux vivent dans le meme dossier"
    ecran, _ = _ecran(projet)

    async def scenario(pilote):
        ecran.zone = ppd.ZONE_EXPLORATEUR
        ecran.explorateur.dossier = faux.parent
        ecran.explorateur.relire()
        noms = [e.chemin.name for e in ecran.explorateur.entrees]
        ecran.explorateur.curseur = noms.index(faux.name)
        ecran.traiter("enter")
        refuse = ecran.etat()
        # 1. un simple deplacement dans l'explorateur efface deja le motif.
        ecran.traiter("down")
        apres_le_pas = ecran.etat()
        # 2. et une designation REUSSIE ne rend jamais la main avec lui.
        ecran.explorateur.curseur = noms.index(bon.name)
        ecran.traiter("enter")
        await pilote.pause()
        return refuse, apres_le_pas, ecran.etat(), ecran.zone, [
            e.cle for e in ecran.choix.entrees]

    refuse, apres_le_pas, apres, zone, cles = _monte(_app(ecran), scenario,
                                                     banc)

    # Le refus a bien ete dit une fois, verbatim du coeur.
    with pytest.raises(profile_designation.ProfileDesignationError) as leve:
        profile_designation.read_designated_document(faux)
    assert str(leve.value) in refuse, refuse
    # Puis il a disparu, aux deux frappes suivantes.
    assert str(leve.value) not in apres_le_pas, apres_le_pas
    assert str(leve.value) not in apres, apres
    # Et la designation valide a bien abouti : le motif n'a pas disparu parce
    # que rien ne s'est passe.
    assert zone == ppd.ZONE_LISTE
    assert ppd.CLE_FICHIER_DESIGNE in cles, cles
