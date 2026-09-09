# -*- coding: utf-8 -*-
"""La PORTE du profil par defaut : ce que le PRODUIT ouvre sur cette entree.

**Ce banc rougit tant que les deux lignes de cablage ne sont pas posees dans
`atelier_extraction_ecriture.ChaineReelle`, et c'est VOULU.** Le fichier est
tenu par un autre agent au 2026-09-06 ; les deux lignes sont ecrites verbatim
dans le rapport de ce lot, sous « CABLAGE A POSER ». Le coordinateur verra ce
banc passer au vert en les posant, et c'est le seul verdict qui dise que le
produit a l'ecran.

Le mode de panne, et le depot l'a paye QUATRE fois
---------------------------------------------------
`E9`, `I3`, puis `MQ-4`/`MQ-5` la meme nuit, puis `MQ-8` : **un composant
livre, teste, et cable nulle part dans l'application est un composant que le
produit n'a pas**. C'est litteralement ce qu'Egan a rencontre le 2026-09-06 --
« Cet ecran n'existe pas encore (mauvais cablage ?) » -- alors que les six
fonctions de `palier_projet.py` etaient ecrites, exportees et testees depuis la
story 11.3.

**Ce banc joue l'APPLICATION DU PRODUIT, jamais une fixture.** Il monte
`chaine_du_produit()` -- le point d'entree reel, celui qui injecte les
parcours -- et il frappe les touches du regime exact de la recette :

    `mmu-tui` -> `⏎` -> `↓↓↓↓` -> `⏎` -> `↓` -> `⏎`

Un banc qui assemblerait la chaine a la main est **precisement** ce qui a
masque `E9` pendant deux vagues : « c'est cette assemblee manuelle qui a masque
le manque -- la recette passait par la demo, jamais par le point d'entree du
produit » (`ChaineReelle`).

La mesure porte sur le **TYPE de l'ecran monte**, jamais sur son texte : un
ecran « pas encore » qui citerait le profil dans sa phrase passerait un grep, et
c'est exactement le texte qui a masque `MQ-4` et `MQ-5`.

Regle des fabriques
-------------------
Le projet de ce banc porte **trois profils distinguables** au registre -- trois
chaines, trois sources, trois cardinaux de patchs. Les **trois** entrees du
palier Projet sont frappees, la tete et la queue comprises : un aiguillage trop
large (« toute entree du palier ouvre le profil ») passerait le test de la
porte et emporterait les deux autres en silence.
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
from mixed_media_utility.io import calibration_profile, profile_designation
from mixed_media_utility.tui import palier_profil_defaut as ppd
from mixed_media_utility.tui import palier_projet, projets
from mixed_media_utility.tui.atelier_extraction_ecriture import (
    ChaineReelle, chaine_du_produit)
from mixed_media_utility.tui.coque import EcranPasEncore

#: Le regime de la recette, frappe par frappe. `⏎` ouvre le projet le plus
#: recent, `↓↓↓↓` descend jusqu'a l'entree *Projet* -- cinquieme et derniere du
#: menu des ateliers --, `⏎` y entre.
JUSQU_AU_PALIER_PROJET = ("enter", "down", "down", "down", "down", "enter")

#: Le rang de « Profil de calibration par defaut » dans le palier Projet : la
#: **deuxieme** des trois entrees. Elle n'est donc ni en tete ni en queue, ce
#: qui est exactement la position ou un aiguillage fautif se cache le mieux --
#: les deux bords sont couverts par le test des autres entrees.
DESCENTES_JUSQU_AU_PROFIL = 1

#: Les trois profils du registre, tous distinguables.
PROFILS = (
    {"chain_id": "chaine-alpha", "patchs": 21, "source": "profil-alpha.json"},
    {"chain_id": "chaine-beta", "patchs": 33, "source": "profil-beta.json"},
    {"chain_id": "chaine-gamma", "patchs": 47, "source": "profil-gamma.json"},
)


# ---------------------------------------------------------------------------
# Les fabriques -- TROIS profils DISTINGUABLES, le defaut au MILIEU
# ---------------------------------------------------------------------------

def _document(chain_id: str, *, patchs: int) -> dict:
    """Un profil **valide au sens du coeur**, jamais un mock."""
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


def _projet_a_trois_profils(tmp_path) -> Path:
    """Un projet reel, trois profils au registre, le defaut au **milieu**.

    Les trois cardinaux de patchs sont distincts (21, 33, 47) : une fabrique
    uniforme rendrait invisible tout desappariement entre une ligne de la liste
    et le fichier qu'elle designe. Le defaut est le second, jamais le premier :
    un aiguillage qui rendrait toujours la premiere entree se demasque.
    """
    chemin = creer_projet(tmp_path, "projet_demo").chemin
    for rang, profil in enumerate(PROFILS):
        document = _document(profil["chain_id"], patchs=profil["patchs"])
        fichier = calibration_profile.write_profile(chemin, document)
        profile_designation.record_designated_profile(
            chemin, document, project_path=fichier, source=profil["source"],
            as_default=(rang == 1))
    return chemin


def _chaine_sur(chemin: Path, tmp_path) -> ChaineReelle:
    """La chaine **du produit**, ouverte sur ce projet par ses recents.

    C'est `chaine_du_produit` et non `ChaineReelle(...)` : le premier injecte
    les parcours, le second est la version degradee que seuls les bancs
    montent. Mesurer le second serait mesurer un produit qui n'existe pas.
    """
    recents = projets.Recents(tmp_path / "reglages" / "recents-v1.json")
    recents.noter_ouverture(chemin)
    return chaine_du_produit(recents=recents)


def _jouer(chaine: ChaineReelle, touches, banc):
    """Frapper `touches` sur l'application montee, rendre l'ecran du dessus."""
    async def scenario(pilote):
        await pilote.press(*JUSQU_AU_PALIER_PROJET)
        await pilote.pause()
        await pilote.press(*touches)
        await pilote.pause()
        return pilote.app.screen

    return banc(chaine.app, scenario)


# ---------------------------------------------------------------------------
# La porte elle-meme
# ---------------------------------------------------------------------------

def test_le_PRODUIT_ouvre_l_ecran_du_PROFIL_PAR_DEFAUT(tmp_path, banc):
    """Huit frappes, et l'ecran de choix du profil s'ouvre.

    **Ce test rougit tant que le cablage n'est pas pose** : la huitieme frappe
    rend alors `EcranPasEncore`. C'est le verdict attendu du lot, et le seul
    qui distingue « l'ecran est ecrit » de « le produit a l'ecran ».

    La mesure porte sur le **type** de l'ecran monte et non sur son texte.
    """
    chemin = _projet_a_trois_profils(tmp_path)
    touches = tuple(["down"] * DESCENTES_JUSQU_AU_PROFIL + ["enter"])
    ecran = _jouer(_chaine_sur(chemin, tmp_path), touches, banc)

    assert not isinstance(ecran, EcranPasEncore), (
        "la porte du profil par defaut n'est pas posee : « Profil de "
        "calibration par defaut » tombe encore dans le filet de "
        "`ChaineReelle.entrer_commande`")
    assert isinstance(ecran, ppd.EcranProfilParDefaut), type(ecran).__name__


def test_l_ecran_OUVERT_PAR_LE_PRODUIT_porte_le_VRAI_projet(tmp_path, banc):
    """La liste est celle du disque, pas une liste vide montee pour la forme.

    Un cablage qui construirait `EcranProfilParDefaut(None, ...)` passerait le
    test ci-dessus : l'ecran existe, il est du bon type, et il n'affiche que la
    porte « autre fichier… » indefiniment. Les **trois** profils sont donc
    comptes, le premier et le dernier compris : une liste tronquee d'un bord
    rendrait les deux du milieu et tairait les autres.
    """
    chemin = _projet_a_trois_profils(tmp_path)
    touches = tuple(["down"] * DESCENTES_JUSQU_AU_PROFIL + ["enter"])
    ecran = _jouer(_chaine_sur(chemin, tmp_path), touches, banc)

    assert isinstance(ecran, ppd.EcranProfilParDefaut), type(ecran).__name__
    assert ecran.dossier == chemin, ecran.dossier
    noms = [e.nom for e in ecran.choix.entrees]
    assert noms == ["profil-alpha.json", "profil-beta.json",
                    "profil-gamma.json", ppd.LIBELLE_AUTRE_FICHIER], noms
    # Le defaut du projet est lu du manifeste, pas devine : il est au MILIEU.
    marques = [e.par_defaut for e in ecran.choix.entrees]
    assert marques == [False, True, False, False], marques


def test_le_parcours_COMPLET_depuis_le_produit_pose_le_profil(tmp_path, banc):
    """De la liste au compte rendu, sans quitter l'application du produit.

    C'est ce que la recette d'Egan fait a la main. Les trois temps
    d'`EPIC11-ARB-4` sont traverses : la liste, le point de jugement -- qui
    n'ecrit rien --, puis l'ecriture et son compte rendu.

    La cible est le profil **en queue** de registre, jamais celui sous le
    curseur au montage : un `⏎` qui poserait toujours la premiere entree
    resterait vert sur elle.
    """
    chemin = _projet_a_trois_profils(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)
    dernier = PROFILS[-1]

    async def scenario(pilote):
        await pilote.press(*JUSQU_AU_PALIER_PROJET)
        await pilote.pause()
        await pilote.press(*(["down"] * DESCENTES_JUSQU_AU_PROFIL), "enter")
        await pilote.pause()
        liste = pilote.app.screen
        if isinstance(liste, EcranPasEncore):
            pytest.fail("le cablage de la porte n'est pas pose")
        # Descendre jusqu'au troisieme profil : la QUEUE du registre.
        for _ in range(len(PROFILS) - 1):
            await pilote.press("down")
        await pilote.pause()
        vise = liste.choix.courante
        await pilote.press("enter")
        await pilote.pause()
        jugement = pilote.app.screen
        avant = profile_designation.default_profile_entry(chemin)
        # L'issue qui ecrit est en tete ; le curseur part sur celle qui n'ecrit
        # pas. On le remonte d'un cran, exactement comme l'operateur.
        await pilote.press("up", "enter")
        await pilote.pause()
        return vise, jugement, avant, pilote.app.screen

    vise, jugement, avant, ecran = banc(chaine.app, scenario)

    assert isinstance(jugement, ppd.EcranPoseDuProfil), type(jugement).__name__
    assert vise.entree["chain_id"] == dernier["chain_id"], vise.nom
    # Le point de jugement n'avait rien ecrit : le defaut etait encore l'ancien.
    assert avant is not None and avant["chain_id"] == PROFILS[1]["chain_id"]
    assert isinstance(ecran, ppd.EcranProfilPose), type(ecran).__name__
    apres = profile_designation.default_profile_entry(chemin)
    assert apres["chain_id"] == dernier["chain_id"], apres


# ---------------------------------------------------------------------------
# Les DEUX AUTRES entrees -- l'aiguillage ne doit pas etre trop large
# ---------------------------------------------------------------------------

def test_les_cles_qui_ouvrent_le_PROFIL_sont_un_ENSEMBLE_EXACT(tmp_path, banc):
    """`ENTREE_PROFIL` et **elle seule** ouvre cet ecran. Repli compris.

    La mesure est un **ensemble exact** et non trois assertions positives : une
    branche mal placee qui emporterait une entree cablee est invisible a toute
    assertion prise entree par entree. C'est le patron impose par le mutant
    `M23` de la campagne du 2026-09-06, sur la table de destinations de
    `ChaineReelle.entrer_commande`.

    Une quatrieme cle, **inconnue et posee en QUEUE**, mesure le repli de la
    table : c'est le rang ou un repli fautif se cache.
    """
    chemin = _projet_a_trois_profils(tmp_path)
    chaine = _chaine_sur(chemin, tmp_path)
    from mixed_media_utility.tui.panneau import Issue

    cles = [palier_projet.ENTREE_MEDIAS, palier_projet.ENTREE_PROFIL,
            palier_projet.ENTREE_RECONSTRUCTION, "entree-neuve-non-cablee"]

    async def scenario(pilote):
        await pilote.press(*JUSQU_AU_PALIER_PROJET)
        await pilote.pause()
        ouvrent = []
        for cle in cles:
            chaine.entrer_commande(Issue(cle, f"Libelle de {cle}"))
            await pilote.pause()
            if isinstance(pilote.app.screen, ppd.EcranProfilParDefaut):
                ouvrent.append(cle)
            pilote.app.action_remonter()
            await pilote.pause()
        return ouvrent

    ouvrent = banc(chaine.app, scenario)

    assert ouvrent == [palier_projet.ENTREE_PROFIL], ouvrent
