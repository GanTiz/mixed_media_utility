# -*- coding: utf-8 -*-
"""Story 11.9, lot B -- l'etage 1 de l'aide, GENERALISE (AC 1).

Ce banc mesure `tui/aide_de_champ.py` -- le **mecanisme** -- et les **quatre**
ecrans qui le portent. Il ne mesure ni le manuel (lot C) ni la derivation du
paquet (lot A) : « aucun lot ne partage un fichier de banc avec un autre ».

**Ce que l'AC 1 demande, et ou chaque volet se lit ici :**

* **1.1** une phrase qui dit ce que le champ attend, les formes acceptees, et
  une **valeur du contexte courant** -- mesuree par « la phrase rendue porte
  une valeur qui n'est PAS dans le libelle du champ », et par le fait que cette
  valeur **change quand l'etat change** ;
* **1.2** l'aide **remplace** la tete : le cardinal de lignes du corps est
  identique aide ouverte et aide fermee, et **une seule** ligne diverge ;
* **1.3** l'aide **tombe** au changement de champ ;
* **1.4** `f1` est **consommee dans l'ecran** sur un champ, et **remonte** hors
  champ -- les deux volets, parce que l'un sans l'autre est la moitie d'une
  mesure ;
* **1.5** l'ensemble des ecrans porteurs est **EXACTEMENT** celui que
  `EPIC11-ARB-198` borne, `EcranCreation` **nomme** avec son motif.

**Les regles de forme du depot, et ou elles mordent ici :**

1. **toute fabrique de collection produit au moins trois elements
   distinguables**, avec la cible **au milieu** *et* **a chaque bord**
   (`fabrique-poser-aussi-aux-deux-bords`, 2026-09-03). Les collections de ce
   lot : les **champs** d'un formulaire (jusqu'a sept, cible au deuxieme, au
   premier et au dernier), les **ecrans** rendus par un balayage (temoin a cinq
   classes, cibles aux rangs 0, 2 et 4), et les **classes d'un meme module**
   -- `ecran_projet` en porte trois pour sept constantes `RACCOURCIS_*`, et
   c'est ce qui distingue un ecart pose par CLASSE d'un ecart pose par MODULE ;
2. **la position se verifie sur la liste que le CODE parcourt**, jamais sur
   celle que le test a ecrite ;
3. **les ensembles se comparent en egalite**, difference symetrique en message ;
4. **les frontieres negatives sont AST**, jamais un grep textuel, et chacune
   porte son volet de **morsure** : une frontiere sans contre-exemple est verte
   sur un module vide, un module renomme ou un balayage casse.
"""
from __future__ import annotations

import ast
import asyncio
import inspect
import sys
import textwrap
from dataclasses import dataclass
import os
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest

from outils_frontiere import chaines_de_code

from mixed_media_utility import scan_ingest
from mixed_media_utility.tui import aide_de_champ, jetons, manuel
from mixed_media_utility.tui import atelier_pdf_calibration as mire
from mixed_media_utility.tui import atelier_scan as depot
from mixed_media_utility.tui import atelier_scan_calibrate as calibrate
from mixed_media_utility.tui import atelier_scan_completion as completion
from mixed_media_utility.tui import ecran_projet
from mixed_media_utility.tui.atelier_scan_rapport import PageMuette
from mixed_media_utility.tui.coque import Contexte, CoqueTui, Palier, PalierTemoin

#: Les deux regimes, portes par tout test qui peint (AC 5.4).
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le module mesure, pour les frontieres negatives.
MECANISME = Path(_SRC) / "mixed_media_utility" / "tui" / "aide_de_champ.py"


# ===========================================================================
# Les fabriques -- un porteur, son module, ses champs, ses libelles
# ===========================================================================

def _manifeste_minimal() -> dict:
    """Un manifeste que `E3-4b` sait monter. Il ne sert qu'a ouvrir l'ecran :
    aucun test d'ici ne lit le modele de completion, qui est mesure par le banc
    de la 11.5."""
    return {"schema_version": "2.1", "project_id": "p",
            "created": "2026-09-03T00:00:00Z", "rushes": [], "lots": []}


def ecran_completion():
    return completion.EcranCompletionQr(
        PageMuette(read_rank=1, fichier="scans/scans-in/page_02.png",
                   code="QR_NON_DECODE", lot_id="rush-x_1"),
        _manifeste_minimal(), poser=lambda _identite: None)


def source_mesuree(chemin: str = "scans/planche-du-tournage-nocturne.png",
                   dpi: float | None = 300.0) -> depot.SourceDesignee:
    """Une source designee **avec sa mesure**, sans toucher au disque.

    Elle sert a deux choses : rendre la ligne de reprise atteignable -- elle
    n'existe que quand une mesure existe --, et donner a l'aide du champ de
    source une valeur de contexte qui **n'est pas** celle du champ vide.
    """
    return depot.SourceDesignee(
        chemin=Path(chemin),
        mesure=scan_ingest.SourceMesuree(
            forme=scan_ingest.FORME_IMAGE, cardinal=1, octets=4096,
            dpi=dpi, fichiers=1))


def ecran_depot():
    return depot.EcranScanDepot()


def ecran_calibrate():
    return calibrate.EcranCalibrerLaChaine(calibrer=lambda _formulaire: None)


def ecran_mire():
    return mire.EcranMireReglages("p", None)


@dataclass
class FormulaireTemoin:
    """Un formulaire de synthese, **suivi comme les quatre du produit**.

    Il sert aux tests du seul MECANISME, qui n'ont pas d'ecran a monter.
    :class:`~mixed_media_utility.tui.aide_de_champ.AideDeChamp` exige un
    formulaire suivi, et c'est deliberement une exigence de construction : un
    porteur qui n'en passerait pas ne construirait pas l'objet du tout.

    **Trois champs distinguables, jamais un seul**, et un `avancer` qui
    **boucle** comme les quatre : c'est la boucle qui a produit le defaut du
    2026-09-04, une fabrique bornee ne la reproduirait pas.
    """

    CHAMPS = ("tete", "milieu", "queue")

    champ: str = aide_de_champ.ChampSuivi(CHAMPS[0])

    def avancer(self, pas: int = 1) -> bool:
        rang = self.CHAMPS.index(self.champ)
        self.champ = self.CHAMPS[(rang + pas) % len(self.CHAMPS)]
        return True


#: **Les quatre porteurs, et ce que chacun declare.**
#:
#: `champs` est la liste que le CODE parcourt -- lue du module, jamais reecrite
#: ici : c'est sur elle que se verifient les positions de cible.
PORTEURS = {
    "mixed_media_utility.tui.atelier_pdf_calibration.EcranMireReglages": {
        "module": mire,
        "fabrique": ecran_mire,
        "champs": tuple(mire.LIBELLES_DES_CHAMPS),
        "libelles": mire.LIBELLES_DES_CHAMPS,
    },
    "mixed_media_utility.tui.atelier_scan.EcranScanDepot": {
        "module": depot,
        "fabrique": ecran_depot,
        # La ligne `Valider` est entree le 2026-09-06 (retour terrain d'Egan,
        # « il manque un bouton valider ») : elle est une LIGNE DU FORMULAIRE
        # et non une issue, donc elle se mesure comme les trois autres.
        "champs": (depot.CHAMP_SOURCE, depot.CHAMP_DPI, depot.CHAMP_REPRISE,
                   depot.CHAMP_VALIDER),
        "libelles": {depot.CHAMP_SOURCE: depot.LIBELLE_SOURCE,
                     depot.CHAMP_DPI: depot.LIBELLE_DPI,
                     depot.CHAMP_REPRISE: depot.LIBELLE_REPRISE,
                     depot.CHAMP_VALIDER: depot.LIBELLE_VALIDER},
    },
    "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrerLaChaine": {
        "module": calibrate,
        "fabrique": ecran_calibrate,
        "champs": tuple(calibrate.LIBELLES),
        "libelles": calibrate.LIBELLES,
    },
    "mixed_media_utility.tui.atelier_scan_completion.EcranCompletionQr": {
        "module": completion,
        "fabrique": ecran_completion,
        "champs": completion.LIGNES_DU_FORMULAIRE,
        "libelles": completion.LIBELLES,
    },
}

#: Les trois porteurs dont l'aide cite une **valeur du contexte courant**
#: (AC 1.1). Le quatrieme -- le modele de 11.5 -- en est absent, et c'est
#: mesure comme un ensemble EXACT plutot que tu : voir
#: :func:`test_l_ensemble_des_porteurs_qui_CITENT_une_valeur_de_contexte_est_EXACTEMENT_celui_la`.
PORTEURS_A_VALEUR = frozenset(PORTEURS) - {
    "mixed_media_utility.tui.atelier_scan_completion.EcranCompletionQr"}


#: Le pied du palier temoin. Il n'est pas invente : `E3-1` le dessine en fin
#: de ligne de raccourcis, et la confrontation en fin de fichier le verifie a
#: sa source.
PIED_DU_PALIER = "Q quitter"

#: La mention du champ `Valider` quand aucun scan n'est designe. Elle n'est
#: PAS recopiee d'un dessin -- `E3-9` ne dessine aucune ligne `Valider` -- et
#: la confrontation en fin de fichier nomme la coincidence qui le fait croire.
MENTION_DU_VALIDER_SANS_SCAN = "scan requis"


def monte(ecran, scenario, banc, ascii_seul=False):
    app = CoqueTui(paliers=[PalierTemoin("Ateliers", PIED_DU_PALIER), ecran],
                   contexte=Contexte(projet="p"), ascii_seul=ascii_seul)

    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def aide_de(ecran) -> aide_de_champ.AideDeChamp:
    """L'etat d'aide du porteur, ou qu'il vive.

    Le modele de 11.5 le porte sur son **formulaire** -- c'est la forme livree,
    et `EPIC11-ARB-198` interdit de la reecrire --, les trois autres sur
    l'ecran. Le mecanisme, lui, est le meme objet des quatre cotes, et c'est ce
    que ce banc mesure.
    """
    return getattr(ecran, "aide", None) or ecran.formulaire._aide


def champ_courant(ecran) -> str:
    return ecran.formulaire.champ


def poser_le_champ(ecran, cle: str) -> None:
    """Poser le curseur sur un champ, **et rien d'autre**.

    **Le `aide_de(ecran).fermer()` qui suivait a ete RETIRE le 2026-09-04**, et
    son retrait fait partie du correctif. Il etait la pour rendre l'etat de
    l'aide deterministe d'une iteration a l'autre -- c'est-a-dire pour
    **compenser** le fait que l'aide ne tombait pas au changement de champ mais
    se contentait de se cacher. C'etait l'aveu du defaut, ecrit dans
    l'outillage du banc ; le garder maintenant que le defaut est ferme
    masquerait la mesure, puisque toute reouverture au retour serait effacee
    avant d'etre lue.

    Ce que la pose fait desormais toute seule : l'affectation passe par
    `aide_de_champ.ChampSuivi`, donc elle compte, donc elle fait tomber l'aide.
    """
    ecran.formulaire.champ = cle


# ===========================================================================
# B1 -- l'ensemble BORNE des ecrans porteurs (AC 1.5, `EPIC11-ARB-198`)
# ===========================================================================

def test_l_ensemble_des_ecrans_PORTEURS_d_une_table_d_aide_est_EXACTEMENT_celui_la():
    """AC 1.5. **Egalite, jamais inclusion** : une assertion positive
    laisserait passer un ecran oublie exactement comme un ecran de trop, et
    c'est la phrase de l'AC.

    Le balayage est celui du depot (`manuel.classes_d_ecran`, remonte dans
    `src/` par le lot A) : un second balayage ecrit ici divergerait du premier.
    """
    derive = set(aide_de_champ.ecrans_porteurs_d_une_table_d_aide())
    declare = set(aide_de_champ.ECRANS_A_TABLE_D_AIDE)
    assert derive == declare, sorted(derive ^ declare)
    assert derive == set(PORTEURS), sorted(derive ^ set(PORTEURS))


def test_le_balayage_VOIT_vraiment_des_ecrans_et_pas_seulement_les_porteurs():
    """Volet sans lequel le precedent serait vert sur deux ensembles vides.

    Le paquet porte des dizaines de classes d'ecran ; les porteurs en sont une
    **petite minorite**, et c'est ce qui donne du sens a l'egalite ci-dessus.
    """
    toutes = manuel.classes_d_ecran()
    assert len(toutes) > 4 * len(aide_de_champ.ECRANS_A_TABLE_D_AIDE)
    assert set(aide_de_champ.ECRANS_A_TABLE_D_AIDE) <= set(toutes)


def test_les_ecrans_ECARTES_sont_nommes_avec_leur_motif_et_n_en_portent_AUCUNE():
    """Le silence sur un cas limite rend l'ensemble **indecidable** : « pourquoi
    celui-la n'y est pas » n'a pas de reponse mesurable si personne ne l'ecrit.

    Les deux ensembles sont **disjoints**, et chacun est une partie du paquet :
    un nom ecarte qui n'existerait plus serait un motif qui ne protege rien.
    """
    toutes = manuel.classes_d_ecran()
    ecartes = set(aide_de_champ.ECRANS_ECARTES)
    assert ecartes & set(aide_de_champ.ECRANS_A_TABLE_D_AIDE) == set()
    assert ecartes <= set(toutes), sorted(ecartes - set(toutes))
    for nom, motif in aide_de_champ.ECRANS_ECARTES.items():
        assert len(motif) > 60, nom
        assert aide_de_champ.NOM_DE_LA_TABLE not in vars(toutes[nom]), nom


def test_EcranCreation_est_ECARTE_et_ses_trois_motifs_se_MESURENT(banc):
    """**Le cas que l'AC 1.5 exige de trancher explicitement.**

    `ecran_projet.AIDE_PARENT` est bien une phrase d'aide de champ. Elle n'est
    ni une table ni un etage 1, et les trois motifs se mesurent plutot que de
    se declarer :

    1. c'est **une chaine**, pas une table -- une seule phrase, pour une seule
       des deux lignes ;
    2. elle est **TOUJOURS affichee** : elle est dans le corps avant comme
       apres `f1`, et le corps ne bouge pas d'une ligne ;
    3. elle n'est **liee a aucun `F1`** : la touche n'est pas consommee, donc
       elle remonte a la liaison applicative.
    """
    nom = "mixed_media_utility.tui.ecran_projet.EcranCreation"
    assert nom in aide_de_champ.ECRANS_ECARTES
    assert isinstance(ecran_projet.AIDE_PARENT, str)

    e = ecran_projet.EcranCreation(dossier_parent="/tmp", nom="essai")

    async def scenario(_pilote):
        avant = list(e.lignes())
        consommee = e.traiter("f1")
        return avant, consommee, list(e.lignes())

    avant, consommee, apres = monte(e, scenario, banc)
    assert consommee is False
    assert avant == apres
    assert any(ecran_projet.AIDE_PARENT in ligne for ligne in avant)


# ---------------------------------------------------------------------------
# Un dossier INTERDIT A LA LECTURE ne fait pas tomber l'explorateur -- 2026-09-08
# ---------------------------------------------------------------------------

def test_un_dossier_INTERDIT_n_est_pas_marque_et_ne_leve_PAS(monkeypatch):
    """Le plantage REEL de la CI publique, mesure sur ses trois jobs.

    `EcranCreation(dossier_parent="/tmp")` ouvre l'explorateur sur `/tmp`, ou
    le runner GitHub porte un `snap-private-tmp` appartenant a root :
    `PermissionError: '/tmp/snap-private-tmp/project.json'`, et l'ecran entier
    tombe. Le meme piege attend l'operateur qui ouvre un dossier parent
    quelconque contenant un sous-dossier qu'il ne peut pas lire.

    La panne est jouee par le DIAGNOSTIC plutot que par une permission de
    disque, pour une raison mesurable : la suite tourne en root dans les
    conteneurs de ce depot, et root traverse un `chmod 000`. Un banc pose sur
    les permissions y serait donc VERT sans rien mesurer -- c'est le volet
    reel ci-dessous qui le dit, et qui se saute en le NOMMANT.
    """
    def interdit(dossier, depuis_les_recents=False):
        raise PermissionError(13, "Permission denied", str(dossier))

    monkeypatch.setattr(ecran_projet.projets, "diagnostiquer", interdit)
    assert ecran_projet._porte_un_projet(Path("/nimporte/quoi")) is False


def test_le_volet_REEL_sur_un_dossier_chmod_000(tmp_path):
    """Le meme fait, sur une VRAIE permission -- et il se saute en le disant.

    Sans ce second volet, la garde ne serait mesuree que contre une exception
    fabriquee : rien ne dirait que `diagnostiquer` leve REELLEMENT sur un
    dossier interdit, et le jour ou elle cesserait de lever, le premier banc
    resterait vert en mesurant une panne qui n'existe plus.
    """
    if os.geteuid() == 0:
        pytest.skip("execute en root : `chmod 000` ne barre pas root, "
                    "le volet reel ne mesurerait rien")
    interdit = tmp_path / "interdit"
    interdit.mkdir()
    interdit.chmod(0o000)
    try:
        # L'anti-vacuite du volet : la lecture leve bien, donc il y a
        # quelque chose a garder.
        with pytest.raises(OSError):
            ecran_projet.projets.diagnostiquer(interdit)
        assert ecran_projet._porte_un_projet(interdit) is False
    finally:
        interdit.chmod(0o700)


def _classes_du_module(module) -> list[str]:
    """Les classes d'ecran d'un module, **dans l'ordre ou le balayage les
    rend** -- la liste que le code parcourt, jamais celle que le test ecrit."""
    prefixe = module.__name__ + "."
    return [nom for nom in sorted(manuel.classes_d_ecran())
            if nom.startswith(prefixe)]


def test_l_ecart_se_pose_par_CLASSE_et_jamais_par_MODULE():
    """`ecran_projet` porte **sept** constantes `RACCOURCIS_*` pour **deux**
    classes d'ecran : le cardinal des constantes ne dit rien de celui des
    ecrans, et un ecart pose par module emporterait les deux pour une.

    Une fabrique mono-constante rendrait cet appariement invisible -- c'est la
    famille du mutant `M25` de la 5.7, applique a « quelle classe cette
    constante decrit-elle ». La mesure : la classe ecartee est nommee, et sa
    voisine de module n'est **ni** porteuse **ni** ecartee.
    """
    constantes = [nom for nom in vars(ecran_projet)
                  if nom.startswith(manuel.PREFIXE_DES_CONSTANTES)]
    assert len(constantes) >= 7, sorted(constantes)

    du_module = _classes_du_module(ecran_projet)
    assert len(du_module) >= 2, du_module
    cible = "mixed_media_utility.tui.ecran_projet.EcranCreation"
    ecartes = set(aide_de_champ.ECRANS_ECARTES) & set(du_module)
    assert ecartes == {cible}, sorted(ecartes ^ {cible})
    voisines = set(du_module) - {cible}
    assert voisines & set(aide_de_champ.ECRANS_A_TABLE_D_AIDE) == set()
    assert voisines & set(aide_de_champ.ECRANS_ECARTES) == set()


def test_les_porteurs_sont_AU_MILIEU_et_AUX_DEUX_BORDS_de_leur_module():
    """La regle des fabriques, **sur des collections reelles du produit** et
    non sur une fixture : trois modules portent plusieurs classes d'ecran, et
    la cible y occupe les trois positions qui comptent.

    * `atelier_scan` -- la cible est la **premiere** de son module ;
    * `atelier_scan_calibrate` -- elle est **au milieu** de cinq ;
    * `atelier_pdf_calibration` -- elle est la **derniere** de cinq.

    « Au milieu » demasque un resolveur qui rendrait le premier ; les deux
    bords demasquent un balayage tronque en tete ou en queue, qui est un autre
    mode de panne (`fabrique-poser-aussi-aux-deux-bords`). La position se lit
    sur la liste que le CODE parcourt.
    """
    positions = {}
    for module, cible in ((depot, "EcranScanDepot"),
                          (calibrate, "EcranCalibrerLaChaine"),
                          (mire, "EcranMireReglages")):
        du_module = _classes_du_module(module)
        assert len(du_module) >= 2, module.__name__
        rang = du_module.index(f"{module.__name__}.{cible}")
        positions[module.__name__] = (rang, len(du_module))

    tete, milieu, queue = (positions["mixed_media_utility.tui.atelier_scan"],
                           positions["mixed_media_utility.tui."
                                     "atelier_scan_calibrate"],
                           positions["mixed_media_utility.tui."
                                     "atelier_pdf_calibration"])
    assert tete[0] == 0, tete
    assert 0 < milieu[0] < milieu[1] - 1, milieu
    assert queue[0] == queue[1] - 1, queue


def test_le_balayage_rend_TOUS_les_porteurs_AUX_DEUX_BORDS_et_au_milieu(monkeypatch):
    """La regle des fabriques, sur **la liste que le code parcourt**.

    Cinq classes temoins **distinguables**, trois porteuses aux rangs **0, 2 et
    4** : la cible du milieu demasque un resolveur qui rendrait le premier
    (`M25`), les deux cibles de bord demasquent un balayage **tronque** -- une
    tete ou une queue sautee --, qui est un autre mode de panne
    (`fabrique-poser-aussi-aux-deux-bords`, 2026-09-03).
    """
    temoins: dict[str, type] = {}
    for rang in range(5):
        corps = {"titre": f"temoin-{rang}", "raccourcis": f"T{rang} rien"}
        if rang % 2 == 0:
            corps[aide_de_champ.NOM_DE_LA_TABLE] = {f"champ-{rang}":
                                                    f"phrase {rang}"}
        temoins[f"temoin.Temoin{rang}"] = type(f"Temoin{rang}", (Palier,), corps)

    monkeypatch.setattr(manuel, "classes_d_ecran", lambda: temoins)
    rendus = set(aide_de_champ.ecrans_porteurs_d_une_table_d_aide())
    attendus = {"temoin.Temoin0", "temoin.Temoin2", "temoin.Temoin4"}
    assert rendus == attendus, sorted(rendus ^ attendus)


def test_un_attribut_HERITE_ne_fait_pas_entrer_une_sous_classe(monkeypatch):
    """Volet symetrique du precedent : l'ensemble est celui des **porteurs**,
    pas celui de leurs descendants. `vars` et non `getattr` -- une sous-classe
    qui n'a rien declare n'a rien a y faire."""
    porteur = type("Porteur", (Palier,),
                   {"titre": "p", "raccourcis": "P rien",
                    aide_de_champ.NOM_DE_LA_TABLE: {"a": "phrase a"}})
    heritiere = type("Heritiere", (porteur,), {"titre": "h"})
    monkeypatch.setattr(manuel, "classes_d_ecran",
                        lambda: {"t.Porteur": porteur, "t.Heritiere": heritiere})
    assert set(aide_de_champ.ecrans_porteurs_d_une_table_d_aide()) == {"t.Porteur"}


def test_chaque_porteur_ANNONCE_F1_dans_sa_ligne_de_raccourcis():
    """Le critere d'entree dans l'ensemble borne se **mesure** : un ecran qui
    porterait une table sans annoncer `F1` promettrait une aide que personne ne
    saurait ouvrir, et l'inverse est le finding `I8`."""
    classes = manuel.classes_d_ecran()
    lignes = manuel.lignes_de_raccourcis_du_paquet()
    for nom in aide_de_champ.ECRANS_A_TABLE_D_AIDE:
        annonces = [ligne for cle, ligne in lignes.items()
                    if cle.startswith(nom + ".")]
        annonces.append(classes[nom].raccourcis or "")
        assert any("F1" in ligne for ligne in annonces), nom


# ===========================================================================
# B2 -- le mecanisme est GENERALISE, jamais recopie (`EPIC11-ARB-198`)
# ===========================================================================

@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_les_quatre_porteurs_emploient_LE_MEME_mecanisme(nom):
    """Une seule redaction pour quatre ecrans : c'est tout l'objet du lot."""
    ecran = PORTEURS[nom]["fabrique"]()
    assert isinstance(aide_de(ecran), aide_de_champ.AideDeChamp)


@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_la_table_de_chaque_porteur_vit_dans_SON_module(nom):
    """« Ce que l'on extrait, c'est le MECANISME, pas la donnee. »

    La table declaree par la classe est **le meme objet** qu'une constante de
    son propre module -- pas une copie, pas une entree d'un registre central.
    Et aucune des phrases ne vit dans le module du mecanisme.
    """
    module = PORTEURS[nom]["module"]
    table = vars(manuel.classes_d_ecran()[nom])[aide_de_champ.NOM_DE_LA_TABLE]
    assert any(valeur is table for valeur in vars(module).values()), nom
    phrases = set(table.values())
    du_mecanisme = {valeur for valeur in vars(aide_de_champ).values()
                    if isinstance(valeur, str)}
    assert phrases & du_mecanisme == set(), sorted(phrases & du_mecanisme)


def test_aucun_des_TROIS_ecrans_enroles_ne_REDIGE_une_seconde_fois_le_mecanisme():
    """Frontiere **AST** : les trois modules enroles par cette story ne
    definissent ni `basculer_l_aide` ni `tete`. Une seconde redaction du
    mecanisme divergerait de la premiere sur la seule chose qui compte -- la
    chute au changement de champ, que le site ne pose plus."""
    for nom in sorted(PORTEURS_A_VALEUR):
        source = Path(inspect.getfile(PORTEURS[nom]["module"]))
        arbre = ast.parse(source.read_text(encoding="utf-8"))
        definies = {noeud.name for noeud in ast.walk(arbre)
                    if isinstance(noeud, ast.FunctionDef)}
        assert definies & {"basculer_l_aide", "tete"} == set(), nom


def test_le_modele_de_11_5_DELEGUE_au_mecanisme_au_lieu_de_le_redire():
    """`atelier_scan_completion` **garde** ses deux methodes -- c'est son
    contrat public depuis la 11.5, et deux tests de son banc les appellent --,
    mais leur corps est desormais une **delegation** : un `return` unique sur
    un appel de `self._aide`. C'est la lettre d'`EPIC11-ARB-198` : generaliser
    le livre, ne pas le reecrire."""
    arbre = ast.parse(Path(inspect.getfile(completion)).read_text(encoding="utf-8"))
    corps = {noeud.name: noeud for noeud in ast.walk(arbre)
             if isinstance(noeud, ast.FunctionDef)}
    for methode in ("basculer_l_aide", "tete"):
        instructions = [noeud for noeud in corps[methode].body
                        if not isinstance(noeud, ast.Expr)]
        assert len(instructions) == 1, methode
        rendu = instructions[0]
        assert isinstance(rendu, ast.Return), methode
        assert isinstance(rendu.value, ast.Call), methode
        appele = rendu.value.func
        assert isinstance(appele, ast.Attribute), methode
        assert isinstance(appele.value, ast.Attribute), methode
        assert appele.value.attr == "_aide", methode


def test_la_table_du_MODELE_n_a_pas_bouge():
    """`OU_LIRE_LE_CHAMP` couvre toujours les sept lignes du parcours, et
    aucune de ses phrases ne porte la marque de valeur : le modele predate
    l'AC 1.1, et cette story ne le reecrit pas."""
    assert set(completion.OU_LIRE_LE_CHAMP) == set(completion.LIGNES_DU_FORMULAIRE)
    assert not any(aide_de_champ.MARQUE_DE_LA_VALEUR in phrase
                   for phrase in completion.OU_LIRE_LE_CHAMP.values())


# ===========================================================================
# B3 -- la VALEUR DU CONTEXTE COURANT (AC 1.1)
# ===========================================================================

def test_l_ensemble_des_porteurs_qui_CITENT_une_valeur_de_contexte_est_EXACTEMENT_celui_la():
    """**Ecart nomme plutot que tu.** L'AC 1.1 veut une valeur du contexte
    courant dans la phrase rendue ; le modele de 11.5 n'en porte aucune -- ses
    phrases nomment un endroit de la planche IMPRIMEE et une cle lue du coeur
    --, et `EPIC11-ARB-198` interdit de le reecrire. L'ensemble est donc
    mesure en **egalite** : le jour ou un quatrieme porteur arrive sans valeur
    de contexte, ce test rougit au lieu de laisser filer.
    """
    citants = {nom for nom in PORTEURS
               if all(aide_de_champ.MARQUE_DE_LA_VALEUR in phrase
                      for phrase in vars(manuel.classes_d_ecran()[nom])[
                          aide_de_champ.NOM_DE_LA_TABLE].values())}
    assert citants == set(PORTEURS_A_VALEUR), sorted(citants ^ PORTEURS_A_VALEUR)


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", sorted(PORTEURS_A_VALEUR))
def test_la_phrase_rendue_porte_une_valeur_qui_n_est_PAS_dans_le_libelle(
        nom, ascii_seul, banc):
    """AC 1.1, dans la forme exacte que l'AC donne : « un test verifie que la
    phrase rendue porte une valeur qui n'est pas dans le libelle du champ ».

    Une aide qui paraphrase le libelle est un defaut (`EPIC11-ARB-14`), et la
    paraphrase se mesure des deux cotes : la **valeur** citee n'est pas dans le
    libelle, et la **phrase** ne le reprend pas non plus.
    """
    porteur = PORTEURS[nom]
    ecran = porteur["fabrique"]()

    async def scenario(_pilote):
        rendus = {}
        for cle in porteur["champs"]:
            poser_le_champ(ecran, cle)
            ecran.traiter("f1")
            # **La valeur se cherche dans le regime ou la ligne est LUE** : le
            # repli ASCII change les caracteres, et comparer une valeur UTF-8 a
            # une ligne repliee rendrait ce test vert par accident sur son
            # propre echec -- la ligne serait introuvable, donc vide.
            valeur = ecran.valeur_de_l_aide(cle)
            attendue = jetons.replier_ascii(valeur) if ascii_seul else valeur
            ligne = [l for l in ecran.lignes() if attendue in l]
            rendus[cle] = (ligne[0] if ligne else "", attendue)
        return rendus

    rendus = monte(ecran, scenario, banc, ascii_seul)
    for cle, (ligne, valeur) in rendus.items():
        libelle = porteur["libelles"][cle].casefold()
        assert valeur, cle
        assert ligne, cle
        assert valeur.casefold() not in libelle, (cle, valeur, libelle)
        assert libelle not in ligne.casefold(), (cle, ligne)


def _basculer_le_defaut(ecran) -> None:
    """`basculer_le_defaut` ne repond que **sur sa ligne** : elle rend `False`
    ailleurs. Poser le champ fait partie du geste, et l'oublier ferait croire a
    une valeur figee la ou c'est le formulaire qui refuse."""
    ecran.formulaire.champ = calibrate.CHAMP_DEFAUT
    assert ecran.formulaire.basculer_le_defaut() is True


def _rendre_la_passe_possible(ecran) -> None:
    """Ce qui fait passer la ligne d'action de « scan requis » a « pret »."""
    ecran.formulaire.scan = source_mesuree()
    ecran.formulaire.dpi = "600"


def _rendre_la_detection_possible(ecran) -> None:
    """Son jumeau sur `E3-1` : une source designee et une resolution saine."""
    ecran.formulaire.source = source_mesuree()
    ecran.formulaire.dpi = "600"


#: **Ce qui fait bouger la valeur de CHAQUE champ**, champ par champ.
#:
#: Une seule mutation par porteur ne suffirait pas : sur `E3-9`, changer
#: l'etiquette fait bouger UNE valeur sur sept, et un champ dont la valeur
#: serait figee resterait invisible derriere les six autres. C'est le mutant
#: `M10` de la reinjection de ce lot, et il a survecu a la premiere redaction.
MUTATIONS = {
    "mixed_media_utility.tui.atelier_pdf_calibration.EcranMireReglages": {
        mire.CHAMP_CHAINE:
            lambda e: setattr(e.formulaire, "chaine", "chaine-du-soir"),
        mire.CHAMP_COMMENTAIRE:
            lambda e: setattr(e.formulaire, "commentaire", "note du soir"),
    },
    "mixed_media_utility.tui.atelier_scan.EcranScanDepot": {
        depot.CHAMP_SOURCE:
            lambda e: e.formulaire.poser_la_source(source_mesuree()),
        depot.CHAMP_DPI: lambda e: setattr(e.formulaire, "dpi", "600"),
        depot.CHAMP_REPRISE:
            lambda e: e.formulaire.poser_la_source(source_mesuree()),
        # Ce qui fait passer la ligne d'action de « source requise » a « pret ».
        depot.CHAMP_VALIDER: _rendre_la_detection_possible,
    },
    "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrerLaChaine": {
        calibrate.CHAMP_SCAN:
            lambda e: setattr(e.formulaire, "scan", source_mesuree()),
        calibrate.CHAMP_DPI: lambda e: setattr(e.formulaire, "dpi", "600"),
        calibrate.CHAMP_REPRISE:
            lambda e: setattr(e.formulaire, "scan", source_mesuree()),
        calibrate.CHAMP_ETIQUETTE:
            lambda e: setattr(e.formulaire, "etiquette", "chaine-du-soir"),
        calibrate.CHAMP_COMMENTAIRE:
            lambda e: setattr(e.formulaire, "commentaire", "note du soir"),
        calibrate.CHAMP_DEFAUT: _basculer_le_defaut,
        calibrate.CHAMP_VALIDER: _rendre_la_passe_possible,
    },
}


@pytest.mark.parametrize("nom", sorted(PORTEURS_A_VALEUR))
def test_la_valeur_citee_CHANGE_avec_l_etat_CHAMP_PAR_CHAMP(nom):
    """**La mesure qui tue le mutant « valeur figee ».** Une phrase qui
    citerait une constante passerait les deux tests precedents.

    Et elle porte **sur chaque champ separement** : mesurer « au moins une
    valeur a bouge » laisserait un champ fige derriere ses voisins, ce qui est
    exactement l'erreur d'appariement que la regle des fabriques vise -- une
    seule cible, au milieu d'un groupe qui, lui, repond.
    """
    porteur = PORTEURS[nom]
    for cle, muter in MUTATIONS[nom].items():
        ecran = porteur["fabrique"]()
        avant = ecran.valeur_de_l_aide(cle)
        muter(ecran)
        assert ecran.valeur_de_l_aide(cle) != avant, (nom, cle, avant)
    assert set(MUTATIONS[nom]) == set(porteur["champs"]), nom


def test_le_dpi_REFUSE_par_le_coeur_se_lit_dans_l_aide():
    """La ligne du champ montre la frappe telle quelle ; l'aide dit ce que le
    coeur en fait. `dpi_valide` est la **seule autorite** -- l'aide ne redige
    pas une seconde regle."""
    ecran = ecran_depot()
    ecran.formulaire.dpi = str(scan_ingest.MAX_SCAN_DPI + 1)
    assert "hors bornes" in ecran.valeur_de_l_aide(depot.CHAMP_DPI)
    ecran.formulaire.dpi = "300"
    assert ecran.valeur_de_l_aide(depot.CHAMP_DPI) == "300"


def test_le_plafond_du_dpi_est_LU_du_coeur_et_JAMAIS_recopie():
    """Frontiere **AST** : la valeur du plafond n'apparait comme litteral dans
    aucun des deux modules qui l'annoncent. C'est la lecon de
    `CANONICAL_ID_MAX_LENGTH`, recopiee fausse trois fois dans ce depot."""
    plafond = str(scan_ingest.MAX_SCAN_DPI)
    for module in (depot, calibrate):
        table = vars(module)["AIDE_PAR_CHAMP"]
        assert any(plafond in phrase for phrase in table.values()), module
        arbre = ast.parse(
            Path(inspect.getfile(module)).read_text(encoding="utf-8"))
        litteraux = _litteraux_du_module(arbre)
        assert scan_ingest.MAX_SCAN_DPI not in litteraux["entiers"], module
        # **Et pas davantage dans une CHAINE.** Le mutant qui a survecu a la
        # premiere redaction remplacait la `f`-chaine par un litteral portant
        # les memes chiffres : la mesure des entiers ne le voyait pas, et la
        # phrase rendue restait identique au caractere pres. Une frontiere qui
        # ne regarde qu'une des deux formes d'ecriture est verte sur l'autre.
        recopies = [texte for texte in litteraux["chaines"]
                    if str(scan_ingest.MAX_SCAN_DPI) in texte]
        assert recopies == [], (module, recopies)


def _litteraux_du_module(arbre: ast.Module) -> dict[str, list]:
    """Les litteraux entiers et les litteraux de chaine d'un arbre.

    Les morceaux constants d'une `f`-chaine en font partie : c'est justement la
    ou une recopie se cacherait. Ce que la valeur INTERPOLEE rend, elle, n'est
    pas un litteral -- c'est un `FormattedValue`, et c'est la forme voulue.
    """
    entiers, chaines = [], []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, ast.Constant):
            continue
        if isinstance(noeud.value, bool):
            continue
        if isinstance(noeud.value, int):
            entiers.append(noeud.value)
        elif isinstance(noeud.value, str):
            chaines.append(noeud.value)
    return {"entiers": entiers, "chaines": chaines}


def test_la_mesure_du_plafond_MORD_sur_une_recopie_en_CHAINE():
    """Volet de morsure, et il est du au titre de l'AC 6.3 : « une fermeture ne
    vaut que si le mutant reinjecte fait rougir le test qui la porte »."""
    plafond = str(scan_ingest.MAX_SCAN_DPI)
    fautif = ast.parse(f'TABLE = {{"dpi": "Un entier jusqu\'a {plafond}."}}')
    chaines = _litteraux_du_module(fautif)["chaines"]
    assert [texte for texte in chaines if plafond in texte]

    sain = ast.parse(
        'TABLE = {"dpi": f"Un entier jusqu\'a {scan_ingest.MAX_SCAN_DPI}."}')
    chaines = _litteraux_du_module(sain)["chaines"]
    assert [texte for texte in chaines if plafond in texte] == []


# ---------------------------------------------------------------------------
# AC 1.1, le volet MANQUANT : chaque phrase est confrontee a SON champ
# ---------------------------------------------------------------------------
#
# **Ce que les trois couches de la revue du 2026-09-04 ont trouve
# independamment** -- couche 1 `F-C1-4`, couche 2 `F-C2-2`, couche 3 `F1` --,
# et c'est le signal le plus fort de ce depot : le MECANISME de l'aide etait
# mesure de partout, la DONNEE ne l'etait nulle part. Sept mutants de
# permutation survivaient, dont deux que l'operateur lirait comme un mensonge :
#
# * `M21` -- `E3-9`, phrases d'`etiquette` et de `commentaire` permutees : `F1`
#   sur `Nom de la chaine` repond « Texte libre garde dans le profil » ;
# * `M22` -- `E5-6`, memes permutations : `F1` sur `Nom de la chaine`, qui est
#   **requis** et sans lequel `entrer continuer` ne fait rien, repond
#   « **Facultatif**, un texte imprime sur la planche ».
#
# **Le trou etait trompeur, et il faut dire pourquoi.** Le mutant jumeau sur
# `E3-1` (`M20`) MOURAIT -- mais par accident : le banc de la paraphrase
# verifie `libelle not in ligne`, et la phrase de `reprise` contient le mot
# « source », qui se trouve etre le libelle du voisin. Sur `E3-9` et `E5-6`,
# aucun libelle n'apparait dans la phrase du voisin, donc rien ne rougissait.
# **Un mutant tue par coincidence de vocabulaire n'est pas une couverture.**
#
# C'est la quatrieme fois que ce depot paie un **appariement positionnel de
# collection** (`5.6 M33`, `5.7 M25`, `5.8`, et ici) : classe **critique**,
# zero survivant exige.

#: **Le discriminant de chaque champ : un fragment qui doit se lire dans SA
#: phrase et dans AUCUNE autre du meme porteur.**
#:
#: Il est redige **ici**, a la main, et jamais derive de la table mesuree : une
#: table qui se mesurerait elle-meme est le banc tautologique que la politique
#: de revue recense (`5.9`, la constante centrale de la calibration). Le prix a
#: payer est assume -- reformuler une phrase du produit fait rougir ce banc,
#: et c'est exactement ce qu'on veut d'une frontiere posee sur une donnee.
#:
#: **Les quatre porteurs y sont, pas seulement les trois enroles par la 11.9.**
#: Le modele de 11.5 predate l'AC 1.1 et ne cite aucune valeur, mais ses sept
#: phrases nomment sept endroits differents d'une planche imprimee : une
#: permutation y enverrait l'operateur lire le mauvais coin de sa feuille.
DISCRIMINANT_DU_CHAMP = {
    "mixed_media_utility.tui.atelier_pdf_calibration.EcranMireReglages": {
        mire.CHAMP_CHAINE: "Requis",
        mire.CHAMP_COMMENTAIRE: "Facultatif",
    },
    "mixed_media_utility.tui.atelier_scan.EcranScanDepot": {
        depot.CHAMP_SOURCE: "dossier",
        depot.CHAMP_DPI: "entier",
        depot.CHAMP_REPRISE: "Relit",
        # « temps 1 » : le mot que ni le libelle (`Valider`) ni le pied
        # (`⏎ détecter`) ne portent, et qu'aucune des trois autres phrases de
        # cet ecran n'emploie.
        depot.CHAMP_VALIDER: "temps 1",
    },
    "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrerLaChaine": {
        calibrate.CHAMP_SCAN: "mire",
        calibrate.CHAMP_DPI: "entier",
        calibrate.CHAMP_REPRISE: "Relit",
        calibrate.CHAMP_ETIQUETTE: "retrouvera",
        calibrate.CHAMP_COMMENTAIRE: "Texte libre",
        calibrate.CHAMP_DEFAUT: "Oui ou non",
        # Raccord du lot B (`F-C1-3`) : la phrase de `Valider` ne promet
        # plus une ecriture immediate mais nomme le point d'arret.
        calibrate.CHAMP_VALIDER: "confirmer",
    },
    "mixed_media_utility.tui.atelier_scan_completion.EcranCompletionQr": {
        completion.CHAMP_LOT: "nom de planche",
        completion.CHAMP_PAGE: "premier nombre",
        completion.CHAMP_GABARIT: "Pied technique",
        completion.CHAMP_FRAMES: "Sous les images",
        completion.CHAMP_TC_PREMIER: "Sous la première image",
        completion.CHAMP_TC_DERNIER: "Sous la dernière image",
        completion.ACTION_OUVRIR: "visionneuse",
    },
}

#: La largeur a laquelle ce banc lit la phrase. Elle est **volontairement plus
#: large que la fenetre** : ce volet mesure l'APPARIEMENT, pas le budget, et
#: une phrase tronquee par la fin perdrait son discriminant sans qu'aucun
#: appariement soit faux. Le budget reel a sa propre mesure (AC 5.5).
LARGEUR_SANS_TRONCATURE = 400


def tete_ouverte(ecran, cle: str, *, ascii_seul: bool = False) -> str:
    """La ligne de tete d'un champ, **aide ouverte sur lui**.

    Elle passe par le chemin que l'ecran emprunte vraiment -- poser le curseur,
    frapper `F1`, composer la ligne --, si bien qu'une permutation dans la
    TABLE et une erreur dans la LECTURE de la table sont attrapees toutes les
    deux. Mesurer la table seule ne verrait que la premiere.
    """
    poser_le_champ(ecran, cle)
    aide = aide_de(ecran)
    assert aide.basculer(cle) is True, cle
    valeur = (ecran.valeur_de_l_aide(cle)
              if hasattr(ecran, "valeur_de_l_aide") else "")
    return aide.ligne_de_tete(cle, utile=LARGEUR_SANS_TRONCATURE,
                              valeur=valeur, ascii_seul=ascii_seul)


#: **Ce qui porte chaque formulaire a son parcours MAXIMAL**, porteur par
#: porteur -- et sans lui la mesure serait aveugle a une cle sur sept.
#:
#: Sur `E3-1` et `E3-9`, la ligne de reprise **n'existe pas** tant qu'aucune
#: mesure n'a ete lue (`champs()` la retire) : un formulaire nu cache donc une
#: cle de la table, et comparer les deux ensembles rendrait un faux ecart.
#: `E5-6` et le modele de 11.5 n'ont qu'un seul parcours, et le disent en ne
#: faisant rien.
AU_PARCOURS_MAXIMAL = {
    "mixed_media_utility.tui.atelier_pdf_calibration.EcranMireReglages":
        lambda _ecran: None,
    "mixed_media_utility.tui.atelier_scan.EcranScanDepot":
        lambda ecran: setattr(ecran.formulaire, "source", source_mesuree()),
    "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrerLaChaine":
        _rendre_la_passe_possible,
    "mixed_media_utility.tui.atelier_scan_completion.EcranCompletionQr":
        lambda _ecran: None,
}


def au_parcours_maximal(nom: str):
    """Un ecran du porteur, porte a son parcours maximal, **et la liste que le
    CODE parcourt alors** -- jamais celle que le banc ecrirait.

    C'est le correctif de l'ecart que la couche 2 a nomme : `PORTEURS` affirme
    que `champs` est lue du module, et c'est **faux du quatrieme**
    (`EcranScanDepot` la porte a la main). Tout ce qui suit lit `champs()`.
    """
    porteur = PORTEURS[nom]
    ecran = porteur["fabrique"]()
    AU_PARCOURS_MAXIMAL[nom](ecran)
    return ecran, _parcours_du_code(ecran, porteur)


def table_du_porteur(nom: str):
    """La table d'aide telle que l'ECRAN la porte -- l'attribut de classe que
    `NOM_DE_LA_TABLE` declare, jamais une seconde lecture du module."""
    return PORTEURS[nom]["fabrique"]().TABLE_D_AIDE


@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_la_table_d_aide_couvre_EXACTEMENT_le_parcours_des_QUATRE(nom):
    """**Le second volet que la 11.9 avait laisse ouvert** (couche 2, `F-C2-2`).

    Le modele de 11.5 portait deja cette egalite ; les trois ecrans enroles
    n'avaient rien d'equivalent. Les deux sens mordent :

    * une cle **absente** de la table -- `basculer` rend `False`, `F1` remonte
      a la liaison applicative et **ouvre le manuel par-dessus le formulaire**,
      c'est-a-dire l'AC 1.4 a l'envers ;
    * une cle **de trop** -- une ligne du parcours a disparu. Sur `E3-9` c'est
      `Valider`, que `lignes_du_formulaire` **dessine** toujours : une ligne
      d'action visible que le curseur ne peut plus atteindre.

    Le mutant qui l'a rendue necessaire, mesure par la couche 2 : `champs()`
    ampute de sa derniere entree survivait aux 457 bancs du perimetre. Il
    survivait parce que les deux bancs de bord lisent leur reference **par
    `champs()`** : le bord qu'ils testent est le bord du mutant.
    """
    _ecran, champs = au_parcours_maximal(nom)
    table = table_du_porteur(nom)
    assert sorted(set(champs) ^ set(table)) == [], (nom, tuple(champs),
                                                    tuple(table))


@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_la_couverture_du_parcours_MORD_dans_les_DEUX_sens(nom, monkeypatch):
    """Volet de morsure du test precedent, et il joue les **deux** amputations
    -- la table qui perd une cle, le parcours qui perd un champ -- **a chaque
    bord et au milieu**.

    Une frontiere qui ne mordrait que dans un sens serait verte sur l'autre, et
    c'est precisement l'asymetrie qui a laisse passer `M28`.
    """
    _ecran, champs = au_parcours_maximal(nom)
    champs = tuple(champs)
    assert len(champs) >= 2, nom

    for rang in {0, len(champs) // 2, len(champs) - 1}:
        cible = champs[rang]

        # Sens 1 : la TABLE perd une cle que le parcours porte toujours.
        table = table_du_porteur(nom)
        ampute = {cle: phrase for cle, phrase in table.items() if cle != cible}
        assert sorted(set(champs) ^ set(ampute)) == [cible], (nom, cible)

        # Sens 2 : le PARCOURS perd un champ que la table porte toujours.
        prive = tuple(cle for cle in champs if cle != cible)
        assert sorted(set(prive) ^ set(table_du_porteur(nom))) == [cible], (
            nom, cible)


def ecarts_d_appariement(nom: str, *, ascii_seul: bool = False) -> list:
    """Les couples (champ vise, champ fautif) ou un discriminant se lit ailleurs
    qu'a sa place -- vide quand l'appariement est juste.

    Factorise pour que la MORSURE joue exactement la meme mesure : une
    frontiere dont le contre-exemple emprunte un autre chemin ne prouve rien de
    la frontiere.
    """
    ecran, champs = au_parcours_maximal(nom)
    attendus = DISCRIMINANT_DU_CHAMP[nom]
    lignes = {cle: tete_ouverte(ecran, cle, ascii_seul=ascii_seul)
              for cle in champs}

    ecarts = []
    for vise, fragment in attendus.items():
        marque = jetons.replier_ascii(fragment) if ascii_seul else fragment
        # Un champ que le PARCOURS ne porte plus rend un ecart nomme, jamais
        # une `KeyError` : la morsure joue des parcours amputes, et une
        # frontiere dont le contre-exemple casse au lieu de rougir ne dit pas
        # ce qui a change.
        if vise not in lignes:
            ecarts.append((vise, vise, "hors parcours", ""))
            continue
        if marque not in lignes[vise]:
            ecarts.append((vise, vise, "absent", lignes[vise]))
        for autre, ligne in lignes.items():
            if autre != vise and marque in ligne:
                ecarts.append((vise, autre, "ailleurs", ligne))
    return ecarts


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_chaque_phrase_d_aide_est_appariee_a_SON_champ_et_a_AUCUN_autre(
        nom, ascii_seul):
    """**Le volet que la 11.9 avait laisse ouvert.** Chaque champ a un fragment
    qui le distingue ; il se lit dans sa phrase, et dans aucune autre du meme
    porteur. Toute permutation de deux phrases fait donc rougir deux fois.

    La mesure porte sur **tous** les champs du porteur -- donc au milieu *et*
    aux deux bords, ce que la regle des fabriques exige depuis le 2026-09-03 --
    et l'ensemble des champs mesures est compare en EGALITE a celui que le code
    parcourt : un champ ajoute a la table sans discriminant fait rougir plutot
    que de passer inapercu.
    """
    _ecran, champs = au_parcours_maximal(nom)
    attendus = DISCRIMINANT_DU_CHAMP[nom]
    assert set(attendus) == set(champs), (nom, set(attendus) ^ set(champs))
    assert len(set(attendus.values())) == len(attendus), nom

    ecarts = ecarts_d_appariement(nom, ascii_seul=ascii_seul)
    assert ecarts == [], (nom, ecarts)


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_la_mesure_de_l_appariement_MORD_sur_une_PERMUTATION(
        nom, ascii_seul, monkeypatch):
    """Volet de morsure, et il n'est pas facultatif : « une fermeture ne vaut
    que si le mutant reinjecte fait rougir le test qui la porte ».

    Il rejoue `M21` et `M22` -- deux phrases echangees dans la table -- sur
    **chaque** porteur et sur **chaque** couple de champs voisins, bords
    compris. Sans ce volet, un discriminant mal choisi (un fragment present
    partout, ou absent partout) rendrait le test precedent vert sur une table
    permutee.
    """
    table = table_du_porteur(nom)
    champs = list(au_parcours_maximal(nom)[1])

    for rang in range(len(champs) - 1):
        gauche, droite = champs[rang], champs[rang + 1]
        with monkeypatch.context() as permutation:
            permutation.setitem(table, gauche, table[droite])
            permutation.setitem(table, droite, table[gauche])
            ecarts = ecarts_d_appariement(nom, ascii_seul=ascii_seul)
        assert ecarts, (nom, gauche, droite)


# ===========================================================================
# AC 1.2 et AC 1.3 -- l'aide REMPLACE, et elle TOMBE
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_l_aide_REMPLACE_la_tete_et_UNE_SEULE_ligne_du_corps_change(
        nom, ascii_seul, banc):
    """AC 1.2. Le cardinal de lignes du corps est **identique** aide ouverte et
    aide fermee -- la grille 80 x 24 ne bouge pas --, et **exactement une**
    ligne diverge : si l'aide s'ajoutait au lieu de remplacer, le cardinal
    bougerait ; si elle remplacait la mauvaise ligne, le compte de divergentes
    aussi.

    Le parcours est celui que le CODE rend (`champs()` quand le formulaire en
    a un), et non une liste ecrite ici.
    """
    porteur = PORTEURS[nom]
    ecran = porteur["fabrique"]()

    async def scenario(_pilote):
        mesures = {}
        parcours = (tuple(ecran.formulaire.champs())
                    if hasattr(ecran.formulaire, "champs")
                    else porteur["champs"])
        for cle in parcours:
            poser_le_champ(ecran, cle)
            avant = list(ecran.lignes())
            consommee = ecran.traiter("f1")
            apres = list(ecran.lignes())
            mesures[cle] = (consommee, len(avant), len(apres),
                            [rang for rang, (a, b) in enumerate(zip(avant, apres))
                             if a != b])
        return mesures

    for cle, (consommee, avant, apres, divergentes) in monte(
            ecran, scenario, banc, ascii_seul).items():
        assert consommee is True, cle
        assert avant == apres, (cle, avant, apres)
        assert len(divergentes) == 1, (cle, divergentes)


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_l_emplacement_de_tete_est_UNIQUE_et_ne_S_AJOUTE_a_rien(
        nom, ascii_seul, banc):
    """AC 1.2, second volet -- **celui que « meme cardinal » ne mesure pas.**

    Un emplacement de tete ajoute **en plus** de la ligne blanche qu'il devait
    remplacer garde le cardinal identique entre les deux etats : les deux
    lignes sont la dans les deux cas. Le corps a pourtant gagne une ligne, et
    la grille 80 x 24 a bouge -- ce que l'AC interdit.

    Ce qui le demasque : **aucun corps de porteur ne porte deux lignes blanches
    consecutives**, aide fermee comme aide ouverte. Les quatre le tiennent
    aujourd'hui, dans chaque etat de champ ; un emplacement en double le
    romprait aussitot. Mutant `M7` de la reinjection de ce lot, qui a survecu a
    la premiere redaction de ce banc.
    """
    porteur = PORTEURS[nom]
    ecran = porteur["fabrique"]()

    async def scenario(_pilote):
        doubles = {}
        parcours = (tuple(ecran.formulaire.champs())
                    if hasattr(ecran.formulaire, "champs")
                    else porteur["champs"])
        for cle in parcours:
            for ouverte in (False, True):
                poser_le_champ(ecran, cle)
                if ouverte:
                    ecran.traiter("f1")
                corps = ecran.lignes()
                doubles[(cle, ouverte)] = [
                    rang for rang in range(len(corps) - 1)
                    if not corps[rang].strip() and not corps[rang + 1].strip()]
        return doubles

    for etat, rangs in monte(ecran, scenario, banc, ascii_seul).items():
        assert rangs == [], (etat, rangs)


@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_l_aide_TOMBE_au_changement_de_champ_AU_MILIEU_ET_AUX_DEUX_BORDS(nom):
    """AC 1.3, sur la liste que le code parcourt, avec la cible **au milieu**
    puis **a chaque bord**.

    La cible au milieu demasque une chute qui ne regarderait que le premier ou
    le dernier champ ; les deux cibles de bord demasquent une chute **tronquee**
    -- un balayage qui saute une extremite --, qui est un autre mode de panne.
    """
    porteur = PORTEURS[nom]
    champs = porteur["champs"]
    assert len(champs) >= 2, nom
    milieu = len(champs) // 2
    for rang in {0, milieu, len(champs) - 1}:
        ecran = porteur["fabrique"]()
        aide = aide_de(ecran)
        poser_le_champ(ecran, champs[rang])
        assert aide.basculer(champs[rang]) is True
        assert aide.ouverte(champs[rang])
        voisin = champs[(rang + 1) % len(champs)]
        ecran.formulaire.champ = voisin
        assert not aide.ouverte(voisin), (nom, champs[rang], voisin)
        assert aide.tete(voisin) == aide.consigne


# ---------------------------------------------------------------------------
# B3 bis -- l'aide TOMBE, elle ne se CACHE pas (correctif du 2026-09-04)
#
# Le test ci-dessus s'arrete au VOISIN, et c'est ce qui a laisse passer le
# defaut : `_champ_ouvert` retenait le champ de la frappe et le comparait au
# champ courant, si bien que REVENIR sur le champ rouvrait l'aide sans que
# personne n'ait frappe `F1`. Sur `E3-1`, ou `Tab` boucle entre deux lignes,
# deux frappes suffisaient. Le troisieme pas -- revenir -- est ce que cette
# section mesure, et la navigation y passe par `avancer`, c'est-a-dire par le
# chemin que l'operateur emprunte.
# ---------------------------------------------------------------------------

def _parcours_du_code(ecran, porteur) -> tuple[str, ...]:
    """La liste que le CODE parcourt, jamais celle que le banc ecrirait."""
    return (tuple(ecran.formulaire.champs())
            if hasattr(ecran.formulaire, "champs") else porteur["champs"])


@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_l_aide_ne_SE_ROUVRE_PAS_en_REVENANT_sur_le_champ_AU_MILIEU_ET_AUX_DEUX_BORDS(
        nom):
    """**Le banc que la dette exige** : `F1` sur le champ i, aller a i+1,
    **revenir** a i, et l'aide doit etre tombee.

    La cible est prise **au milieu** puis **a chaque bord**
    (`fabrique-poser-aussi-aux-deux-bords`) : au milieu, elle demasque une
    chute qui ne regarderait qu'une extremite ; aux bords, elle demasque une
    boucle tronquee -- et c'est justement la boucle de `Tab` qui a produit le
    defaut.

    Le retour se fait par `avancer(-1)`, donc par le chemin du produit : poser
    `formulaire.champ` a la main mesurerait le descripteur, pas la navigation.
    """
    porteur = PORTEURS[nom]
    reference = _parcours_du_code(porteur["fabrique"](), porteur)
    assert len(reference) >= 2, nom
    for rang in {0, len(reference) // 2, len(reference) - 1}:
        ecran = porteur["fabrique"]()
        aide = aide_de(ecran)
        cible = _parcours_du_code(ecran, porteur)[rang]
        ecran.formulaire.champ = cible

        assert aide.basculer(cible) is True, (nom, cible)
        assert aide.ouverte(cible) is True, (nom, cible)

        assert ecran.formulaire.avancer(1) is True
        voisin = ecran.formulaire.champ
        assert voisin != cible, (nom, cible)
        assert aide.ouverte(voisin) is False, (nom, cible, voisin)

        assert ecran.formulaire.avancer(-1) is True
        assert ecran.formulaire.champ == cible, (nom, cible)
        # Le pas que le banc precedent n'avait pas : on est REVENU, et
        # personne n'a refrappe `F1`.
        assert aide.ouverte(cible) is False, (nom, cible, voisin)
        assert aide.tete(cible) == aide.consigne, (nom, cible)


@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_l_aide_ne_SE_ROUVRE_PAS_quand_la_navigation_BOUCLE_AU_MILIEU_ET_AUX_DEUX_BORDS(
        nom):
    """Le regime **exact** de la dette : `Tab` boucle, donc il ramene sur le
    champ sans jamais reculer.

    Aller-retour et tour complet sont deux chemins differents vers le meme
    retour, et un correctif qui ne fermerait que le premier -- par exemple en
    retenant le champ **precedent** -- resterait vert sur l'autre. La cible est
    au milieu et aux deux bords, et l'aide doit etre fermee a **chaque** pas du
    tour, y compris le dernier.
    """
    porteur = PORTEURS[nom]
    reference = _parcours_du_code(porteur["fabrique"](), porteur)
    for rang in {0, len(reference) // 2, len(reference) - 1}:
        ecran = porteur["fabrique"]()
        aide = aide_de(ecran)
        parcours = _parcours_du_code(ecran, porteur)
        cible = parcours[rang]
        ecran.formulaire.champ = cible
        assert aide.basculer(cible) is True
        assert aide.ouverte(cible) is True

        vus = []
        for _ in range(len(parcours)):
            ecran.formulaire.avancer(1)
            vus.append(ecran.formulaire.champ)
            assert aide.ouverte(ecran.formulaire.champ) is False, (
                nom, cible, vus)
        assert vus[-1] == cible, (nom, cible, vus)
        assert set(vus) == set(parcours), (nom, sorted(set(vus) ^ set(parcours)))


def test_l_aide_ouverte_ne_vaut_QUE_pour_le_champ_VISE():
    """Le **second** volet de `ouverte`, et il se mesure sans bouger.

    Le jalon seul rendrait `ouverte` vraie pour n'importe quel champ tant que
    le curseur n'a pas bouge : l'aide d'une ligne s'afficherait alors sur une
    autre. Trois champs distinguables, la cible successivement en tete, au
    milieu et en queue.
    """
    forme = FormulaireTemoin()
    aide = aide_de_champ.AideDeChamp(
        {cle: f"phrase de {cle}." for cle in forme.CHAMPS},
        consigne="la consigne", formulaire=forme)
    for cible in forme.CHAMPS:
        forme.champ = cible
        assert aide.basculer(cible) is True, cible
        assert aide.ouverte(cible) is True, cible
        assert aide.tete(cible) == f"phrase de {cible}."
        for autre in forme.CHAMPS:
            if autre == cible:
                continue
            assert aide.ouverte(autre) is False, (cible, autre)
            assert aide.tete(autre) == "la consigne", (cible, autre)


# -- le descripteur lui-meme -------------------------------------------------

def test_ChampSuivi_compte_les_DEPLACEMENTS_et_non_les_REECRITURES():
    """Ce que le compte doit distinguer, et que la comparaison de valeurs ne
    distinguait pas : « on n'a pas bouge » et « on est revenu ».

    Reposer le champ ou l'on est deja n'est pas un deplacement -- c'est ce que
    fait `poser_la_source` quand le curseur est deja sur le dpi --, et le
    compter ferait tomber une aide que rien n'a quittee.
    """
    forme = FormulaireTemoin()
    tete, milieu, queue = forme.CHAMPS
    assert aide_de_champ.deplacements_du_champ(forme) == 0

    forme.champ = tete
    assert aide_de_champ.deplacements_du_champ(forme) == 0, "reecriture"

    forme.champ = milieu
    assert aide_de_champ.deplacements_du_champ(forme) == 1
    forme.champ = milieu
    assert aide_de_champ.deplacements_du_champ(forme) == 1, "reecriture"

    forme.champ = queue
    assert aide_de_champ.deplacements_du_champ(forme) == 2
    forme.champ = tete
    # Le RETOUR au point de depart : la valeur est celle du debut, le compte
    # ne l'est pas -- c'est tout l'objet du correctif.
    assert forme.champ == tete
    assert aide_de_champ.deplacements_du_champ(forme) == 3


def test_ChampSuivi_rend_son_DEFAUT_et_ne_PARTAGE_rien_entre_instances():
    """Deux pieges de descripteur, chacun avec son temoin.

    Le defaut se lit `getattr(cls, nom)` -- c'est ainsi qu'un `@dataclass`
    compose la signature de son `__init__` --, et l'etat vit sur l'INSTANCE :
    un descripteur qui rangerait sa valeur sur lui-meme ferait de deux
    formulaires un seul curseur, ce qu'aucun test de champ pris isolement ne
    verrait.
    """
    tete, milieu, queue = FormulaireTemoin.CHAMPS
    assert FormulaireTemoin.champ == tete
    assert FormulaireTemoin().champ == tete
    assert FormulaireTemoin(champ=queue).champ == queue

    une, autre = FormulaireTemoin(), FormulaireTemoin()
    une.champ = milieu
    assert autre.champ == tete
    assert aide_de_champ.deplacements_du_champ(une) == 1
    assert aide_de_champ.deplacements_du_champ(autre) == 0


# -- le CABLAGE, mesure en egalite -------------------------------------------

def test_les_QUATRE_porteurs_CABLENT_leur_aide_a_LEUR_PROPRE_formulaire():
    """**Egalite contre l'ensemble borne, jamais assertion positive.**

    Un porteur qui ne cablerait rien retomberait sur le comportement fautif --
    une aide qui se cache -- sans que rien ne rougisse. La construction le
    refuse deja (`formulaire` est obligatoire, et son champ doit etre suivi) ;
    ce banc mesure le pas que la construction ne peut pas voir : que le
    formulaire cable est bien **celui de l'ecran**, et non un autre.
    """
    cables = set()
    for nom, porteur in PORTEURS.items():
        ecran = porteur["fabrique"]()
        if aide_de(ecran).formulaire is ecran.formulaire:
            cables.add(nom)
    attendu = set(aide_de_champ.ECRANS_A_TABLE_D_AIDE)
    assert cables == attendu, sorted(cables ^ attendu)


def test_les_QUATRE_formulaires_declarent_un_champ_SUIVI():
    """Meme egalite, sur l'autre moitie du cablage : un formulaire dont le
    champ n'est pas un `ChampSuivi` rendrait un compte eternellement nul,
    c'est-a-dire exactement le defaut, en silence."""
    suivis = set()
    for nom, porteur in PORTEURS.items():
        formulaire = porteur["fabrique"]().formulaire
        if aide_de_champ.descripteur_du_champ(formulaire) is not None:
            suivis.add(nom)
    attendu = set(aide_de_champ.ECRANS_A_TABLE_D_AIDE)
    assert suivis == attendu, sorted(suivis ^ attendu)


def test_une_aide_SANS_formulaire_ou_sur_un_formulaire_NON_suivi_est_REFUSEE():
    """Le volet de **morsure** des deux egalites ci-dessus.

    Sans lui, « les quatre sont cables » serait vrai d'un mecanisme qui
    accepterait n'importe quoi : la mesure ne dirait pas que le cablage est
    exige, seulement qu'il a ete fait ce jour-la.
    """
    @dataclass
    class FormulaireNu:
        champ: str = "tete"

    with pytest.raises(TypeError):
        aide_de_champ.AideDeChamp({"tete": "phrase."})

    with pytest.raises(TypeError) as refus:
        aide_de_champ.AideDeChamp({"tete": "phrase."},
                                  formulaire=FormulaireNu())
    assert aide_de_champ.NOM_DU_CHAMP_COURANT in str(refus.value)
    assert aide_de_champ.ChampSuivi.__name__ in str(refus.value)

    # Morsure : le meme appel, avec un formulaire suivi, passe.
    assert aide_de_champ.AideDeChamp(
        {"tete": "phrase."}, formulaire=FormulaireTemoin()) is not None


def test_un_formulaire_qui_HERITE_de_son_champ_suivi_est_accepte():
    """La recherche du descripteur remonte la MRO : un formulaire derive
    herite du champ suivi de sa base, et le refuser ferait de l'heritage une
    regression silencieuse -- l'ecran ne se construirait plus du tout."""
    class FormulaireHeritier(FormulaireTemoin):
        pass

    forme = FormulaireHeritier()
    aide = aide_de_champ.AideDeChamp({cle: f"phrase {cle}." for cle
                                      in forme.CHAMPS}, formulaire=forme)
    tete, milieu, _queue = forme.CHAMPS
    assert aide.basculer(tete) is True and aide.ouverte(tete) is True
    forme.champ = milieu
    forme.champ = tete
    assert aide.ouverte(tete) is False


def test_l_aide_tombe_aussi_en_QUITTANT_le_formulaire(banc):
    """Elle tombe toute seule au changement de CHAMP ; entrer dans
    l'explorateur n'en change aucun. Sans le geste de `_appliquer_la_zone`,
    elle reapparaitrait au retour sans que personne ne l'ait redemandee."""
    ecran = ecran_depot()

    async def scenario(_pilote):
        ecran.traiter("f1")
        ouverte = aide_de(ecran).ouverte(champ_courant(ecran))
        ecran.zone = depot.ZONE_EXPLORATEUR
        ecran.traiter("down")
        return ouverte, aide_de(ecran).ouverte(champ_courant(ecran))

    ouverte, apres = monte(ecran, scenario, banc)
    assert ouverte is True
    assert apres is False


# ===========================================================================
# B4 -- le dispatch des DEUX etages (AC 1.4), et son volet symetrique
# ===========================================================================

@pytest.mark.parametrize("nom", sorted(PORTEURS))
def test_f1_est_CONSOMMEE_quand_le_focus_est_sur_un_champ(nom, banc):
    """AC 1.4, premier volet. Consommee dans l'ecran, sinon la liaison
    applicative ouvrirait le manuel **par-dessus** le formulaire."""
    porteur = PORTEURS[nom]
    ecran = porteur["fabrique"]()

    async def scenario(_pilote):
        verdicts = {}
        for cle in porteur["champs"]:
            poser_le_champ(ecran, cle)
            verdicts[cle] = ecran.traiter("f1")
        return verdicts

    for cle, verdict in monte(ecran, scenario, banc).items():
        assert verdict is True, cle


@pytest.mark.parametrize("fabrique,zone", [
    pytest.param(ecran_depot, depot.ZONE_EXPLORATEUR, id="E3-1"),
    pytest.param(ecran_calibrate, calibrate.ZONE_EXPLORATEUR, id="E3-9"),
])
def test_f1_n_est_PAS_consommee_hors_champ_et_REMONTE(fabrique, zone, banc):
    """AC 1.4, **volet symetrique**, et il compte autant que l'autre : sans
    lui, `F1` n'ouvrirait jamais le manuel depuis un ecran a formulaire.

    La mesure porte sur ce que l'ecran **rend** (`traiter` -> `False`), et non
    sur l'ouverture du manuel : celui-ci est ecrit par un autre lot, et
    l'importer ici ferait dependre cette mesure d'un fichier qui n'existe pas
    encore.
    """
    ecran = fabrique()

    async def scenario(_pilote):
        ecran.zone = zone
        return ecran.traiter("f1")

    assert monte(ecran, scenario, banc) is False


def test_le_mecanisme_rend_FAUX_sur_une_ligne_que_la_TABLE_NE_PORTE_PAS():
    """Le volet symetrique, au niveau du mecanisme -- **trois** champs
    distinguables, la ligne muette **au milieu**, puis a chaque bord.

    Une fabrique a un seul champ rendrait invisible tout appariement inverse :
    `basculer` doit consulter la table **du champ vise**, et non la premiere
    entree venue.
    """
    for muet in ("tete", "milieu", "queue"):
        phrases = {cle: f"phrase de {cle} ; ici : {{valeur}}."
                   for cle in ("tete", "milieu", "queue") if cle != muet}
        aide = aide_de_champ.AideDeChamp(phrases, consigne="la consigne",
                                         formulaire=FormulaireTemoin())
        assert aide.basculer(muet) is False, muet
        assert aide.tete(muet) == "la consigne"
        for present in phrases:
            assert aide.basculer(present) is True, (muet, present)
            assert aide.tete(present) == phrases[present].replace(
                aide_de_champ.MARQUE_DE_LA_VALEUR, "")
            aide.fermer()


def test_basculer_REFERME_sur_le_meme_champ_et_pas_ailleurs():
    """Deux frappes sur le meme champ referment ; une frappe sur un autre champ
    **ouvre** celui-la plutot que de refermer le premier."""
    phrases = {"a": "phrase a.", "b": "phrase b.", "c": "phrase c."}
    aide = aide_de_champ.AideDeChamp(phrases, consigne="consigne",
                                     formulaire=FormulaireTemoin())
    assert aide.basculer("b") is True and aide.ouverte("b")
    assert aide.basculer("b") is True and not aide.ouverte("b")
    aide.basculer("b")
    aide.basculer("c")
    assert aide.ouverte("c") and not aide.ouverte("b")


# ===========================================================================
# AC 5.5 -- le budget de largeur, LU de `jetons` et jamais recopie
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("nom", sorted(PORTEURS_A_VALEUR))
def test_toute_ligne_de_tete_tient_dans_le_budget_LU_de_jetons(
        nom, ascii_seul, banc):
    """AC 5.5, dans les **deux** regimes. Le budget se lit de
    `jetons.largeur_utile()`, jamais recopie : c'est la lecon de la 11.7."""
    porteur = PORTEURS[nom]
    ecran = porteur["fabrique"]()

    async def scenario(pilote):
        utile = jetons.largeur_utile(pilote.app.size.width)
        mesures = {}
        for cle in porteur["champs"]:
            poser_le_champ(ecran, cle)
            ecran.traiter("f1")
            ligne = aide_de_champ.ligne_de_tete_de(
                ecran, cle, utile=utile, indent=depot.INDENT_DU_TEXTE,
                ascii_seul=ascii_seul)
            mesures[cle] = (jetons.colonnes(ligne), utile)
        return mesures

    for cle, (cols, utile) in monte(ecran, scenario, banc, ascii_seul).items():
        assert cols <= utile, (cle, cols, utile)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_une_valeur_DEMESUREE_est_abregee_et_la_PHRASE_survit(ascii_seul):
    """C'est la **valeur** qui est abregee, jamais la phrase : une phrase
    tronquee par la fin perd ce que le champ attend, c'est-a-dire tout son
    objet."""
    utile = jetons.largeur_utile()
    aide = aide_de_champ.AideDeChamp(
        {"a": "Ce que le champ attend ; ici : {valeur}."},
        formulaire=FormulaireTemoin())
    aide.basculer("a")
    ligne = aide.ligne_de_tete("a", utile=utile, valeur="x" * 400,
                               indent="  ", ascii_seul=ascii_seul)
    assert jetons.colonnes(
        jetons.replier_ascii(ligne) if ascii_seul else ligne) <= utile
    assert "Ce que le champ attend" in ligne


def test_une_consigne_VIDE_rend_une_ligne_VIDE_et_pas_une_ligne_de_blancs():
    """Trois des quatre porteurs n'ont aucune consigne a dessiner : leur
    emplacement de tete est une ligne blanche, et elle doit rester **vide** --
    une ligne de blancs se lit comme du remplissage et deborde la colonne."""
    aide = aide_de_champ.AideDeChamp({"a": "phrase a."},
                                     formulaire=FormulaireTemoin())
    assert aide.ligne_de_tete("a", utile=76, indent="    ") == ""


# ===========================================================================
# Frontiere negative AST -- le mecanisme n'importe AUCUN ecran
# ===========================================================================

def _imports_de_niveau_module(source: str) -> set[str]:
    """Les modules importes **au niveau du module**, par AST.

    Un `grep` compterait les imports ecrits dans le corps d'une fonction, qui
    sont precisement la forme voulue ici, et ceux cites dans un docstring.
    """
    arbre = ast.parse(source)
    trouves: set[str] = set()
    for noeud in arbre.body:
        if isinstance(noeud, ast.Import):
            trouves.update(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            # `from . import jetons` rend `.jetons` ; `from .coque import
            # Palier` rend `.coque.Palier`. Les points de tete disent le
            # niveau relatif, et c'est eux qui distinguent un module du paquet
            # d'un module du coeur.
            prefixe = "." * noeud.level + (noeud.module or "")
            separateur = "." if noeud.module else ""
            trouves.update(prefixe + separateur + alias.name
                           for alias in noeud.names)
    return trouves


def test_le_mecanisme_n_importe_AUCUN_ecran_au_niveau_module():
    """AC 3.5, meme contrainte que `manuel.py` et pour le meme motif : vingt-cinq
    modules du paquet importent `coque`, et les ecrans importent celui-ci. Un
    import d'ecran au niveau module rendrait le cycle.

    Seul `jetons` est admis : c'est le module de MESURE, une feuille du paquet
    que tous les ecrans importent deja.
    """
    trouves = _imports_de_niveau_module(MECANISME.read_text(encoding="utf-8"))
    ecrans = {nom for nom in trouves
              if nom.startswith(".") and not nom.endswith("jetons")}
    assert ecrans == set(), sorted(ecrans)


def test_la_mesure_des_imports_a_bien_VU_quelque_chose():
    """Premier volet symetrique : une frontiere posee sur un balayage casse est
    verte sur tout. Le module importe bien des choses, et `jetons` en est."""
    trouves = _imports_de_niveau_module(MECANISME.read_text(encoding="utf-8"))
    assert len(trouves) >= 3, sorted(trouves)
    assert any(nom.endswith("jetons") for nom in trouves), sorted(trouves)


def test_la_mesure_des_imports_MORD_sur_un_module_fautif():
    """Second volet symetrique, et c'est celui qui a manque deux fois sur la
    11.8 : une garde peut etre ecrite, relue, plausible **et ne rien mesurer**.

    Le module fautif porte l'import interdit au niveau module ET la forme
    correcte dans le corps d'une fonction : la mesure doit distinguer les deux.
    """
    fautif = textwrap.dedent('''
        """Un module temoin. Il parle de `from .coque import Palier` en prose."""
        from . import jetons
        from .coque import Palier

        def tardif():
            from .manuel import classes_d_ecran
            return classes_d_ecran
    ''')
    trouves = _imports_de_niveau_module(fautif)
    ecrans = {nom for nom in trouves
              if nom.startswith(".") and not nom.endswith("jetons")}
    assert ecrans == {".coque.Palier"}, sorted(ecrans)

    sain = textwrap.dedent('''
        from . import jetons

        def tardif():
            from .coque import Palier
            return Palier
    ''')
    trouves = _imports_de_niveau_module(sain)
    assert {nom for nom in trouves
            if nom.startswith(".") and not nom.endswith("jetons")} == set()


def test_le_mecanisme_reste_montable_APRES_la_coque(banc):
    """La forme qui aurait attrape le cycle : monter la coque **puis**
    demander le balayage des porteurs, dans cet ordre."""
    ecran = ecran_depot()

    async def scenario(_pilote):
        return set(aide_de_champ.ecrans_porteurs_d_une_table_d_aide())

    assert monte(ecran, scenario, banc) == set(aide_de_champ.ECRANS_A_TABLE_D_AIDE)


# ===========================================================================
# B4 -- le VOCABULAIRE de l'absence de saisie : UN SEUL mot, UNE SEULE
#       definition (defaut `F4` de la couche 1, 2026-09-03)
# ===========================================================================
#
# **Le defaut que cette section ferme, et il etait LIVRE.** Le docstring de
# `aide_de_champ.VALEUR_ABSENTE` dit, mot pour mot, que « le mot par lequel
# trois ecrans disent "ce champ n'a rien" est le meme mot, et l'ecrire trois
# fois le ferait diverger au premier ajustement ». Il a diverge **dans la
# livraison qui ecrit cette phrase** : `AIDE_CHAMP_VIDE = "vide"` etait
# redefini dans `atelier_scan_calibrate.py` **et** dans
# `atelier_pdf_calibration.py`, si bien que sur le meme formulaire `E3-9`,
# `dpi` rendait « rien de saisi » quand `etiquette` et `commentaire` rendaient
# « vide ».
#
# Retirer les deux redefinitions ne suffit pas : rien n'empecherait de les
# reecrire demain, sous un autre nom ou en ligne. C'est la lecon de
# `test_frontiere_vocabulaire_d_etat.py` -- « une consigne ne se mesure pas ».

#: Le paquet mesure par les frontieres de cette section.
PAQUET_TUI = Path(_SRC) / "mixed_media_utility" / "tui"


def _modules_du_paquet_tui() -> list[Path]:
    """Tous les modules du paquet `tui/`, dans l'ordre que le CODE parcourt."""
    return sorted(PAQUET_TUI.glob("*.py"))


def _chaines_rendues(noeud: ast.AST) -> list[str]:
    """Les chaines litterales qu'un corps **REND**, f-chaines exclues.

    Trois exclusions, chacune payee :

    * la mesure part des seuls `return` -- un `cle == "dpi"` est une
      **comparaison**, pas un mot rendu a l'operateur, et une frontiere qui les
      confondrait interdirait une ecriture qui n'a jamais rien casse ;
    * une `f`-chaine (`f"{saisi} — hors bornes"`) est une **composition** de la
      valeur du contexte, pas un mot de vocabulaire ;
    * la chaine **vide**, qui est un ecart nomme -- voir le test qui s'en sert.

    Le docstring, lui, sort de lui-meme : il n'est jamais dans un `return`.
    C'est ce qui empeche la mesure de se faire affaiblir a la premiere prose --
    le defaut mesure a l'ecriture de la 11.0 sur `tui/jetons.py`.
    """
    trouvees: list[str] = []

    def descendre(n: ast.AST) -> None:
        if isinstance(n, ast.JoinedStr):
            return
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            trouvees.append(n.value)
            return
        for enfant in ast.iter_child_nodes(n):
            descendre(enfant)

    for instruction in ast.walk(noeud):
        if isinstance(instruction, ast.Return) and instruction.value is not None:
            descendre(instruction.value)
    return [texte for texte in trouvees if texte]


def _aides_de_valeur(source: str) -> list[ast.FunctionDef]:
    """Les methodes `valeur_de_l_aide` d'un module, par AST."""
    return [n for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.FunctionDef) and n.name == "valeur_de_l_aide"]


def _replis_de_saisie(source: str) -> list[str]:
    """Le repli de chaque `… .saisie(…) or X` ecrit dans un `valeur_de_l_aide`.

    C'est la **forme exacte** du defaut : `return self.formulaire.saisie(cle)
    or AIDE_CHAMP_VIDE`. La mesure porte sur le ROLE -- « ce qu'on dit quand la
    saisie est vide » --, pas sur un nom ni sur un mot, parce que le defaut a
    porte les deux fois un nom different de la constante partagee.

    Elle est bornee aux corps de `valeur_de_l_aide` a dessein : le meme
    `saisie(cle) or …` sert ailleurs a poser le **glyphe neutre** de la LIGNE
    du champ (`atelier_pdf_calibration:815`), qui est un autre canal et un
    autre vocabulaire (`DESIGN.md` section 6).
    """
    replis: list[str] = []
    for aide in _aides_de_valeur(source):
        for noeud in ast.walk(aide):
            if not (isinstance(noeud, ast.BoolOp)
                    and isinstance(noeud.op, ast.Or)):
                continue
            gauche = noeud.values[0]
            if not (isinstance(gauche, ast.Call)
                    and isinstance(gauche.func, ast.Attribute)
                    and gauche.func.attr == "saisie"):
                continue
            replis.extend(ast.unparse(autre) for autre in noeud.values[1:])
    return replis


#: L'ecriture EXACTE qu'un repli de saisie vide doit porter. L'acces qualifie,
#: jamais un import de la valeur : `from .aide_de_champ import VALEUR_ABSENTE`
#: rendrait le module porteur d'un second nom pour le meme mot, ce qui est la
#: moitie du defaut.
REPLI_ATTENDU = "aide_de_champ.VALEUR_ABSENTE"


# -- volet PRODUIT : les porteurs disent le meme mot -------------------------

#: **Ce qu'on frappe dans un champ de TEXTE, porteur par porteur et champ par
#: champ.** Le couple est `(attribut du formulaire, texte frappe)`.
#:
#: Regle des fabriques : deux champs distinguables au moins par porteur, des
#: textes **differents** -- un remplissage uniforme rendrait invisible une
#: inversion d'appariement --, et les cibles se verifient sur la liste que le
#: CODE parcourt (`PORTEURS[nom]["champs"]`, lue des modules) : `E5-6` en pose
#: une **en tete** et une **en queue** de ses deux champs, `E3-1` une **au
#: milieu** de ses trois, `E3-9` trois **au milieu** de ses sept.
SAISIES_DE_TEXTE = {
    "mixed_media_utility.tui.atelier_pdf_calibration.EcranMireReglages": {
        mire.CHAMP_CHAINE: ("chaine", "chaine-du-soir"),
        mire.CHAMP_COMMENTAIRE: ("commentaire", "note du soir"),
    },
    "mixed_media_utility.tui.atelier_scan.EcranScanDepot": {
        depot.CHAMP_DPI: ("dpi", "600"),
    },
    "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrerLaChaine": {
        calibrate.CHAMP_DPI: ("dpi", "600"),
        calibrate.CHAMP_ETIQUETTE: ("etiquette", "chaine-du-soir"),
        calibrate.CHAMP_COMMENTAIRE: ("commentaire", "note du soir"),
    },
}


def test_les_champs_de_TEXTE_sont_bien_ceux_la_et_leur_aide_CITE_la_saisie():
    """Anti-vacuite du volet suivant, et il est indispensable.

    Sans lui, une table `SAISIES_DE_TEXTE` qui aurait cesse de designer des
    champs de saisie -- une cle renommee, un champ devenu liste -- rendrait le
    test du vocabulaire vert sans rien mesurer. On verifie donc d'abord que
    **rempli**, chacun de ces champs fait citer a l'aide la frappe elle-meme.

    Et les positions se lisent sur la liste que le CODE parcourt : une cible
    en **tete** (`E5-6`), une en **queue** (`E5-6`), trois au **milieu**
    (`E3-1`, `E3-9`).
    """
    assert set(SAISIES_DE_TEXTE) == set(PORTEURS_A_VALEUR), sorted(
        set(SAISIES_DE_TEXTE) ^ set(PORTEURS_A_VALEUR))
    positions: set[str] = set()
    for nom, champs in sorted(SAISIES_DE_TEXTE.items()):
        parcourus = list(PORTEURS[nom]["champs"])
        assert len(champs) >= 1, nom
        for cle, (attribut, frappe) in champs.items():
            assert cle in parcourus, (nom, cle, parcourus)
            rang = parcourus.index(cle)
            positions.add("tete" if rang == 0
                          else "queue" if rang == len(parcourus) - 1
                          else "milieu")
            ecran = PORTEURS[nom]["fabrique"]()
            setattr(ecran.formulaire, attribut, frappe)
            assert ecran.valeur_de_l_aide(cle) == frappe, (nom, cle)
    assert positions == {"tete", "milieu", "queue"}, sorted(positions)
    # Les textes frappes sont **distinguables** : deux champs remplis du meme
    # mot rendraient invisible une inversion d'appariement (mutant `M33`).
    frappes = [frappe for champs in SAISIES_DE_TEXTE.values()
               for _attribut, frappe in champs.values()]
    assert len(set(frappes)) >= 3, frappes


def test_tout_champ_de_TEXTE_VIDE_dit_le_MEME_mot_sur_les_TROIS_porteurs():
    """**Le defaut `F4`, mesure sur le PRODUIT et non sur le code.**

    Quatre champs du meme formulaire `E3-9` rendaient trois mots : `dpi`
    disait « rien de saisi », `etiquette` et `commentaire` disaient « vide ».
    L'ensemble des mots rendus est mesure en **egalite** avec le singleton
    `{VALEUR_ABSENTE}` : une assertion positive (« `dpi` dit bien le mot
    partage ») serait restee verte pendant que ses deux voisins divergeaient.
    """
    mots: dict[str, set[str]] = {}
    for nom, champs in sorted(SAISIES_DE_TEXTE.items()):
        for cle, (attribut, _frappe) in champs.items():
            ecran = PORTEURS[nom]["fabrique"]()
            setattr(ecran.formulaire, attribut, "")
            mots.setdefault(nom, set()).add(ecran.valeur_de_l_aide(cle))
    rendus = {mot for par_porteur in mots.values() for mot in par_porteur}
    assert rendus == {aide_de_champ.VALEUR_ABSENTE}, (
        {nom: sorted(vus) for nom, vus in mots.items()})


# -- volet AST A : le mot n'est RECOPIE nulle part ---------------------------

def test_le_mot_de_l_absence_de_saisie_n_est_RECOPIE_par_AUCUN_module():
    """Frontiere negative **par la VALEUR**, mesuree a l'AST.

    Le mot est **lu** de `aide_de_champ.VALEUR_ABSENTE`, jamais recopie ici :
    c'est la lecon de `CANONICAL_ID_MAX_LENGTH`, recopiee fausse trois fois
    dans ce depot. Un module qui porterait « rien de saisi » en litteral aurait
    une seconde definition du meme mot, sous n'importe quel nom.
    """
    modules = _modules_du_paquet_tui()
    assert len(modules) >= 30, len(modules)
    recopies = {chemin.name: [texte for texte in chaines_de_code(chemin)
                              if aide_de_champ.VALEUR_ABSENTE in texte]
                for chemin in modules if chemin.name != "aide_de_champ.py"}
    fautifs = {nom: textes for nom, textes in recopies.items() if textes}
    assert fautifs == {}, fautifs


# -- volet AST B : le ROLE, dans les corps de `valeur_de_l_aide` -------------

def test_le_repli_d_une_SAISIE_VIDE_est_TOUJOURS_la_constante_partagee():
    """Frontiere negative **par le ROLE** -- la forme exacte du defaut `F4`.

    `return self.formulaire.saisie(cle) or AIDE_CHAMP_VIDE` : le repli d'une
    saisie vide **est** `aide_de_champ.VALEUR_ABSENTE`, l'acces qualifie, et
    rien d'autre. La mesure ne regarde ni un nom ni un mot -- le defaut a porte
    les deux fois un nom different --, elle regarde la place.
    """
    replis = {chemin.name: _replis_de_saisie(chemin.read_text(encoding="utf-8"))
              for chemin in _modules_du_paquet_tui()}
    trouves = [(nom, repli) for nom, liste in sorted(replis.items())
               for repli in liste]
    # Anti-vacuite : la mesure a bien VU des replis, sur au moins deux modules.
    assert len(trouves) >= 2, trouves
    assert len({nom for nom, _ in trouves}) >= 2, trouves
    fautifs = [(nom, repli) for nom, repli in trouves
               if repli != REPLI_ATTENDU]
    assert fautifs == [], fautifs


def test_aucun_MOT_en_litteral_ne_sort_d_un_valeur_de_l_aide():
    """Frontiere negative **par le LITTERAL** -- l'autre ecriture du meme
    defaut.

    Le volet par le role attrape `saisie(…) or "vide"` ; il n'attrape pas
    `if not saisi: return "vide"`, qui dit exactement la meme chose par une
    autre porte. Aucun mot de vocabulaire ne se rend donc en litteral depuis
    ces corps : ils rendent des constantes nommees ou des `f`-chaines de
    composition.

    La chaine **vide** est admise, et c'est un ecart nomme : le modele de 11.5
    (`atelier_scan_completion`) rend `""` parce que ses phrases ne citent
    aucune valeur de contexte, ce qu'`EPIC11-ARB-198` interdit de reecrire.
    """
    vus = 0
    fautifs: list[tuple[str, str]] = []
    for chemin in _modules_du_paquet_tui():
        for aide in _aides_de_valeur(chemin.read_text(encoding="utf-8")):
            vus += 1
            fautifs.extend((chemin.name, texte)
                           for texte in _chaines_rendues(aide))
    assert vus >= 4, vus  # anti-vacuite : les quatre porteurs sont vus
    assert fautifs == [], fautifs


# -- volet symetrique : les trois mesures MORDENT ----------------------------

def test_les_frontieres_du_VOCABULAIRE_MORDENT_sur_un_module_fautif():
    """**Le volet sans lequel les trois precedents seraient verts sur rien.**

    C'est le mode de panne paye deux fois sur la 11.8 (`M2`, `M4`) : une garde
    « ecrite, relue, plausible, et ne mesurant rien ». Le module temoin porte
    les **trois** formes fautives -- la recopie du mot, le repli par un nom
    local, le litteral rendu --, la premiere **en tete** et la derniere **en
    queue** de sa methode, avec la forme SAINE au milieu : un balayage tronque
    par l'un ou l'autre bout se demasque alors, ce qu'une cible unique au
    milieu ne ferait pas (`fabrique-poser-aussi-aux-deux-bords`, 2026-09-03).
    """
    fautif = textwrap.dedent(f'''
        """Un module temoin. Il parle de {REPLI_ATTENDU} en prose."""
        from . import aide_de_champ

        AIDE_CHAMP_VIDE = "vide"
        MOT_RECOPIE = "{aide_de_champ.VALEUR_ABSENTE}"

        class EcranTemoin:
            def valeur_de_l_aide(self, cle: str) -> str:
                """Docstring qui cite « vide » sans que ce soit du code."""
                if cle == "tete":
                    return self.formulaire.saisie(cle) or AIDE_CHAMP_VIDE
                if cle == "milieu":
                    return (self.formulaire.saisie(cle)
                            or aide_de_champ.VALEUR_ABSENTE)
                if cle == "queue":
                    return "vide"
                return f"{{cle}} — hors bornes"
    ''')
    # 1. le repli par un nom local est vu, et le repli SAIN ne l'est pas.
    replis = _replis_de_saisie(fautif)
    assert replis == ["AIDE_CHAMP_VIDE", REPLI_ATTENDU], replis
    # 2. le litteral rendu est vu -- et ni le docstring, ni la `f`-chaine.
    aides = _aides_de_valeur(fautif)
    assert len(aides) == 1, len(aides)
    assert _chaines_rendues(aides[0]) == ["vide"], _chaines_rendues(aides[0])

    sain = textwrap.dedent('''
        from . import aide_de_champ

        class EcranSain:
            def valeur_de_l_aide(self, cle: str) -> str:
                """Il cite « vide » et « rien de saisi » en prose, sans plus."""
                return self.formulaire.saisie(cle) or aide_de_champ.VALEUR_ABSENTE
    ''')
    assert _replis_de_saisie(sain) == [REPLI_ATTENDU]
    assert _chaines_rendues(_aides_de_valeur(sain)[0]) == []


def test_la_recopie_du_MOT_est_vue_par_la_mesure_des_CHAINES_de_code(tmp_path):
    """Troisieme morsure : `chaines_de_code` lit bien le code et non la prose.

    Le module temoin porte le mot **en litteral** et **en docstring** ; seul le
    premier doit etre vu. Sans ce volet, une frontiere par la valeur posee sur
    un lecteur casse resterait verte sur une recopie.
    """
    temoin = tmp_path / "temoin.py"
    temoin.write_text(
        f'"""Ce docstring cite {aide_de_champ.VALEUR_ABSENTE}."""\n'
        f'MOT = "{aide_de_champ.VALEUR_ABSENTE}"\n', encoding="utf-8")
    vues = [texte for texte in chaines_de_code(temoin)
            if aide_de_champ.VALEUR_ABSENTE in texte]
    assert vues == [aide_de_champ.VALEUR_ABSENTE], vues


# ===========================================================================
# T2 -- « mesurer que ca a BOUGE ne mesure jamais que ca dit VRAI »
# ===========================================================================
#
# Le triage du 2026-09-04 range six findings critiques dans **une seule
# famille**, et c'est ce qui rend leur regroupement legitime : le banc epinglait
# des CHANGEMENTS, presque jamais des VALEURS attendues. Ce que chaque section
# ci-dessous ferme :
#
# * `F-C1-1` -- `E3-1` : une espace dans le `dpi` eteignait les TROIS canaux de
#   « rien ici » pendant que `peut_detecter` restait faux ;
# * `F-C1-5` -- le budget de largeur n'etait tenu que par le garde-fou de
#   dernier recours (`M9`, `M10`, `M11` survivants) ;
# * `F-C1-6` -- la branche « designation multiple » de `valeur_de_l_aide`
#   n'etait jamais jouee, faute d'une fabrique multi-etat (`M23`, `M25`) ;
# * `F-C1-7` et `F2` (couche 3) -- l'appariement champ -> VALEUR de contexte
#   n'etait mesure hors des champs de TEXTE (`M27`, `M01`, `M02`, `M24`) ;
# * `F-C2-1` -- la valeur etait mesuree AVANT son repli ASCII, et la PHRASE en
#   mourait.


# ---------------------------------------------------------------------------
# T2-A -- la fabrique MULTI-ETAT (`F-C1-6`), et les valeurs ATTENDUES
# ---------------------------------------------------------------------------

def sources_mesurees(dpi: float | None = None) -> depot.SourceDesignee:
    """Une designation **MULTIPLE**, la branche qu'aucune fabrique ne produisait.

    **Regle des fabriques, point 1** : trois sources, et **distinguables** --
    trois noms differents, trois poids differents. Un remplissage uniforme
    rendrait invisible toute erreur d'appariement ou de cardinal, et c'est
    exactement ce qui a laisse survivre `M23` (`len(source.sources) - 1`, un
    cardinal FAUX montre a l'operateur) et `M25` (le chemin entier la ou l'aide
    doit dire le seul nom).

    **La forme est celle du COEUR** (`FORME_SELECTION`) et jamais un test sur
    la longueur de la sequence : `SourceDesignee.est_multiple` la lit du coeur,
    et une fabrique qui deciderait autrement mesurerait sa propre regle.
    ``chemin`` vaut donc `None`, comme le coeur le rend -- une designation
    multiple n'a pas un chemin, elle en a une sequence.
    """
    return depot.SourceDesignee(
        chemin=None,
        mesure=scan_ingest.SourceMesuree(
            forme=scan_ingest.FORME_SELECTION, cardinal=3, octets=3072,
            dpi=dpi, fichiers=3),
        sources=((Path("scans/planche-A_prise-01.png"), 1024),
                 (Path("scans/planche-B_prise-02.png"), 2048),
                 (Path("scans/planche-C_prise-03.png"), 512)))


def _depot_a_source_unique(ecran) -> None:
    ecran.formulaire.source = source_mesuree()
    ecran.formulaire.dpi = "600"


def _depot_a_designation_multiple(ecran) -> None:
    """Trois planches designees, **sans mesure** et un dpi que le coeur refuse.

    Deux branches d'un coup, et c'est delibere : le cardinal de la designation
    multiple, et le constat « hors bornes » que la ligne du champ ne dit pas.
    """
    ecran.formulaire.source = sources_mesurees()
    ecran.formulaire.dpi = str(scan_ingest.MAX_SCAN_DPI + 1)


def _calibrate_saisi_sans_mesure(ecran) -> None:
    """Les trois saisies remplies, mais un scan qui n'a livre AUCUNE mesure.

    **Cet etat n'est pas un doublon du suivant**, et il est ce qui rend
    mesurable l'echange `dpi` <-> `etiquette` : la ligne de reprise n'existe
    que quand une mesure existe, si bien que ces deux champs ne sont VOISINS
    que dans ce regime-la. Sur un formulaire vierge ils disent tous deux
    « rien de saisi », et l'echange y est invisible faute de quoi que ce soit
    a echanger.
    """
    ecran.formulaire.scan = source_mesuree("scans/mire-sans-mesure.png",
                                           dpi=None)
    ecran.formulaire.dpi = "600"
    ecran.formulaire.etiquette = "chaine-du-soir"
    ecran.formulaire.commentaire = "note du soir"


def _calibrate_rempli(ecran) -> None:
    ecran.formulaire.scan = source_mesuree("scans/mire-du-soir.png", dpi=300.0)
    ecran.formulaire.dpi = "600"
    ecran.formulaire.etiquette = "chaine-du-soir"
    ecran.formulaire.commentaire = "note du soir"
    ecran.formulaire.champ = calibrate.CHAMP_DEFAUT
    assert ecran.formulaire.basculer_le_defaut() is True


def _mire_remplie(ecran) -> None:
    ecran.formulaire.chaine = "chaine-du-soir"
    ecran.formulaire.commentaire = "note du soir"


#: **Ce que l'aide de CHAQUE champ doit citer, mot pour mot, dans un etat
#: nomme.**
#:
#: Chaque entree est `(libelle de l'etat, ce qui le pose, la valeur attendue
#: champ par champ)`. Les valeurs sont **ecrites a la main ici**, jamais lues
#: du module mesure : une table qui se mesurerait elle-meme est le banc
#: tautologique que la politique de revue recense, et c'est le prix assume de
#: toute frontiere posee sur une donnee -- reformuler un mot du produit fait
#: rougir ce banc.
#:
#: **Pourquoi une VALEUR et pas un changement.** Les deux bancs qui touchaient
#: ces champs mesuraient l'un une inegalite (`… != avant`), l'autre la valeur
#: rendue par l'ecran lui-meme : quatre mutants d'appariement y survivaient --
#: `M01` (`E3-1`, `source` repond `reprise`), `M02` (`E3-9`, `scan` repond
#: `reprise`), `M24` et `M27` (le choix `Devient le défaut` rend l'INVERSE de
#: l'etat). Un echange de deux branches laisse une inegalite vraie ; il ne
#: laisse pas une egalite vraie.
#:
#: **Chaque porteur porte au moins deux etats distinguables**, et l'un d'eux
#: est l'etat VIERGE : les branches « rien ici » sont autant de familles
#: d'etat, et n'en fabriquer qu'une revient a la fabrique mono-etat que la
#: regle des fabriques interdit.
VALEUR_ATTENDUE_DU_CHAMP = {
    "mixed_media_utility.tui.atelier_pdf_calibration.EcranMireReglages": (
        ("vierge", lambda _ecran: None, {
            mire.CHAMP_CHAINE: "rien de saisi",
            mire.CHAMP_COMMENTAIRE: "rien de saisi",
        }),
        ("rempli", _mire_remplie, {
            mire.CHAMP_CHAINE: "chaine-du-soir",
            mire.CHAMP_COMMENTAIRE: "note du soir",
        }),
    ),
    "mixed_media_utility.tui.atelier_scan.EcranScanDepot": (
        ("vierge", lambda _ecran: None, {
            depot.CHAMP_SOURCE: "rien de désigné",
            depot.CHAMP_DPI: "rien de saisi",
            # **Le premier manque nomme, et c'est la SOURCE** : dire
            # « résolution requise » sur un ecran vierge enverrait l'operateur
            # remplir un champ qui n'est pas en cause.
            depot.CHAMP_VALIDER: depot.MENTION_VALIDER_SANS_SOURCE,
        }),
        ("source unique mesuree", _depot_a_source_unique, {
            # Le NOM, jamais le chemin : la ligne du champ montre deja un
            # chemin abrege, et l'aide dit ce que la ligne ne montre pas
            # (mutant `M25`).
            depot.CHAMP_SOURCE: "planche-du-tournage-nocturne.png",
            depot.CHAMP_DPI: "600",
            depot.CHAMP_REPRISE: "300 dpi",
            depot.CHAMP_VALIDER: depot.AIDE_PRET_A_PARTIR,
        }),
        ("designation multiple sans mesure", _depot_a_designation_multiple, {
            # TROIS planches designees : le cardinal est montre a l'operateur,
            # et un cardinal faux ne se voit pas autrement (mutant `M23`).
            depot.CHAMP_SOURCE: "3 fichiers",
            depot.CHAMP_DPI: "20001 — hors bornes",
            # Le TROISIEME regime du refus : la resolution est saisie, et le
            # coeur la refuse. « requise » y serait faux.
            depot.CHAMP_VALIDER: depot.MENTION_VALIDER_DPI_REFUSE,
        }),
    ),
    "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrerLaChaine": (
        ("vierge", lambda _ecran: None, {
            calibrate.CHAMP_SCAN: "rien de désigné",
            calibrate.CHAMP_DPI: "rien de saisi",
            calibrate.CHAMP_ETIQUETTE: "rien de saisi",
            calibrate.CHAMP_COMMENTAIRE: "rien de saisi",
            calibrate.CHAMP_DEFAUT: "non",
            calibrate.CHAMP_VALIDER: MENTION_DU_VALIDER_SANS_SCAN,
        }),
        ("saisi sans mesure", _calibrate_saisi_sans_mesure, {
            calibrate.CHAMP_SCAN: "mire-sans-mesure.png",
            calibrate.CHAMP_DPI: "600",
            calibrate.CHAMP_ETIQUETTE: "chaine-du-soir",
            calibrate.CHAMP_COMMENTAIRE: "note du soir",
            calibrate.CHAMP_DEFAUT: "non",
            calibrate.CHAMP_VALIDER: "prêt à partir",
        }),
        ("rempli", _calibrate_rempli, {
            calibrate.CHAMP_SCAN: "mire-du-soir.png",
            calibrate.CHAMP_DPI: "600",
            calibrate.CHAMP_REPRISE: "300 dpi",
            calibrate.CHAMP_ETIQUETTE: "chaine-du-soir",
            calibrate.CHAMP_COMMENTAIRE: "note du soir",
            # L'INVERSE de l'etat serait « non » : c'est tout ce que `M24` et
            # `M27` changent, et une inegalite ne l'aurait jamais vu.
            calibrate.CHAMP_DEFAUT: "oui",
            calibrate.CHAMP_VALIDER: "prêt à partir",
        }),
    ),
}


def _valeurs_de_l_etat(nom: str, poser, resolveur=None):
    """L'ecran porte a un etat, et la valeur de contexte de **chaque** champ que
    le CODE parcourt alors.

    `resolveur` remplace `valeur_de_l_aide` pour le seul volet de morsure : une
    frontiere dont le contre-exemple emprunte un autre chemin ne prouve rien de
    la frontiere.
    """
    porteur = PORTEURS[nom]
    ecran = porteur["fabrique"]()
    poser(ecran)
    champs = _parcours_du_code(ecran, porteur)
    lire = resolveur or (lambda cle: ecran.valeur_de_l_aide(cle))
    return champs, {cle: lire(cle) for cle in champs}


@pytest.mark.parametrize("nom", sorted(VALEUR_ATTENDUE_DU_CHAMP))
def test_la_valeur_de_contexte_de_CHAQUE_champ_est_EXACTEMENT_celle_la(nom):
    """**Le volet que le triage du 2026-09-04 nomme `F2`.** Chaque champ du
    parcours porte une valeur attendue, ecrite a la main, dans **chaque** etat
    nomme -- et l'ensemble des champs mesures est compare en EGALITE a celui
    que le code parcourt : un champ ajoute au parcours sans valeur attendue
    fait rougir plutot que de passer inapercu.

    Les cibles sont donc au **milieu** et **aux deux bords** de la liste que le
    code parcourt, ce que la regle des fabriques exige depuis le 2026-09-03 :
    l'egalite d'ensembles le garantit par construction, et l'assertion de
    positions ci-dessous le **mesure** plutot que de le supposer.
    """
    positions: set[str] = set()
    parcourus: list[int] = []
    for libelle, poser, attendues in VALEUR_ATTENDUE_DU_CHAMP[nom]:
        champs, rendues = _valeurs_de_l_etat(nom, poser)
        assert set(attendues) == set(champs), (
            nom, libelle, sorted(set(attendues) ^ set(champs)))
        parcourus.append(len(champs))
        for cle, attendue in attendues.items():
            assert rendues[cle] == attendue, (nom, libelle, cle, rendues[cle])
            rang = list(champs).index(cle)
            positions.add("tete" if rang == 0
                          else "queue" if rang == len(champs) - 1
                          else "milieu")
    # **Le milieu n'existe que sur un parcours d'au moins trois lignes**, et
    # `E5-6` n'en a que deux : l'exiger de lui rendrait la frontiere fausse
    # plutot que stricte. Il est exige de tout porteur qui en a un, et
    # l'ensemble est compare en EGALITE -- un parcours qui s'allongerait sans
    # que la table gagne sa cible du milieu fait rougir.
    attendues_positions = {"tete", "queue"}
    if max(parcourus) >= 3:
        attendues_positions.add("milieu")
    assert positions == attendues_positions, (nom, sorted(positions),
                                              parcourus)
    # Deux etats au moins, et **distinguables** : un porteur dont tous les
    # etats rendraient les memes valeurs serait la fabrique mono-etat que
    # `F-C1-6` a payee.
    etats = VALEUR_ATTENDUE_DU_CHAMP[nom]
    assert len(etats) >= 2, nom
    rendus = [tuple(sorted(attendues.items())) for _l, _p, attendues in etats]
    assert len(set(rendus)) == len(rendus), nom


@pytest.mark.parametrize("nom", sorted(VALEUR_ATTENDUE_DU_CHAMP))
def test_la_mesure_de_la_VALEUR_de_contexte_MORD_sur_un_ECHANGE(nom):
    """Volet de morsure, et il n'est pas facultatif : « une fermeture ne vaut
    que si le mutant reinjecte fait rougir le test qui la porte ».

    Il rejoue `M01` et `M02` -- deux champs voisins dont les valeurs
    s'echangent -- sur **chaque** couple de voisins, bords compris, et dans
    **chaque** etat nomme. Sans ce volet, une valeur attendue mal choisie (deux
    champs qui rendraient le meme mot) laisserait le test precedent vert sur un
    resolveur permute.
    """
    mordu: dict[tuple[str, str], bool] = {}
    for libelle, poser, _attendues in VALEUR_ATTENDUE_DU_CHAMP[nom]:
        champs, saines = _valeurs_de_l_etat(nom, poser)
        champs = list(champs)
        assert len(champs) >= 2, (nom, libelle)
        for rang in range(len(champs) - 1):
            couple = (champs[rang], champs[rang + 1])
            echange = {couple[0]: couple[1], couple[1]: couple[0]}
            _c, permutees = _valeurs_de_l_etat(
                nom, poser,
                resolveur=lambda cle, s=saines, e=echange: s[e.get(cle, cle)])
            mordu[couple] = mordu.get(couple, False) or permutees != saines
    # **Dans AU MOINS un etat, et c'est la bonne exigence.** Sur un formulaire
    # vierge, quatre champs disent le meme mot -- « rien de saisi » --, et un
    # echange y est invisible parce qu'il n'y a rien a echanger. Exiger la
    # morsure dans CHAQUE etat ferait rougir la frontiere sur un produit juste ;
    # ne l'exiger nulle part la laisserait verte sur un discriminant mal choisi.
    assert mordu, nom
    sourds = sorted(couple for couple, mord in mordu.items() if not mord)
    assert sourds == [], (nom, sourds)


def test_l_aide_du_CHOIX_dit_l_etat_et_JAMAIS_son_inverse():
    """`E3-9`, ligne `Devient le défaut` -- le mutant `M27`, nomme.

    Le seul banc qui touchait ce champ assertait une **inegalite** : echanger
    les deux branches la laisse vraie. Ici les deux moities du choix sont
    epinglees a la main, dans les deux sens, et un echange fait rougir deux
    fois.
    """
    ecran = ecran_calibrate()
    assert ecran.formulaire.devient_le_defaut is False
    assert ecran.valeur_de_l_aide(calibrate.CHAMP_DEFAUT) == "non"
    _basculer_le_defaut(ecran)
    assert ecran.formulaire.devient_le_defaut is True
    assert ecran.valeur_de_l_aide(calibrate.CHAMP_DEFAUT) == "oui"


def test_la_DESIGNATION_MULTIPLE_compte_ses_fichiers_et_ne_les_NOMME_pas():
    """`E3-1`, la branche que la fabrique mono-etat cachait (`F-C1-6`).

    Deux mesures, et il faut les deux : le **cardinal** est celui de la
    sequence designee (`M23` en rendait un de moins), et la designation
    multiple ne cite **aucun** des trois chemins -- c'est la liste, en dessous,
    qui les dit.
    """
    ecran = ecran_depot()
    ecran.formulaire.source = sources_mesurees()
    sources = ecran.formulaire.source.sources
    # **Anti-vacuite de la fabrique** : trois elements, et distinguables. Une
    # fabrique redevenue mono-element rendrait ce banc vert sans rien mesurer,
    # ce qui est le defaut meme que `F-C1-6` a paye.
    assert len(sources) == 3, sources
    assert len({chemin.name for chemin, _o in sources}) == 3, sources
    assert ecran.formulaire.source.est_multiple is True
    assert ecran.valeur_de_l_aide(depot.CHAMP_SOURCE) == "3 fichiers"
    # Aucun des trois chemins n'est cite -- **ni celui de tete, ni celui du
    # milieu, ni celui de queue** : c'est la liste, en dessous, qui les dit.
    for chemin, _octets in sources:
        assert chemin.name not in ecran.valeur_de_l_aide(depot.CHAMP_SOURCE)

    # La MESURE d'une designation multiple se lit sur la ligne de reprise, et
    # la source continue de ne dire qu'un cardinal.
    mesure = ecran_depot()
    mesure.formulaire.source = sources_mesurees(dpi=300.0)
    assert mesure.valeur_de_l_aide(depot.CHAMP_SOURCE) == "3 fichiers"
    assert mesure.valeur_de_l_aide(depot.CHAMP_REPRISE) == "300 dpi"


def test_l_aide_d_une_source_UNIQUE_dit_le_NOM_et_jamais_le_CHEMIN():
    """`M25`, nomme : l'aide rendait le chemin entier la ou son contrat declare
    est de dire « ce que la ligne ne montre pas » -- la ligne montrant deja un
    chemin abrege. La cible est ecrite a la main, et le chemin dont elle sort
    porte **deux** segments, sans quoi nom et chemin se confondraient."""
    ecran = ecran_depot()
    ecran.formulaire.source = source_mesuree("scans/planche-du-soir.png")
    assert ecran.valeur_de_l_aide(depot.CHAMP_SOURCE) == "planche-du-soir.png"


# ---------------------------------------------------------------------------
# T2-B -- le budget de largeur (`F-C1-5`) et le repli de la VALEUR (`F-C2-1`)
# ---------------------------------------------------------------------------
#
# Les deux bancs de l'AC 5.5 etaient **tautologiques tous les deux** : la
# largeur est garantie par construction, puisque `jetons.ajuster` est appele en
# dernier ; et `"Ce que le champ attend" in ligne` est un PREFIXE, alors
# qu'`ajuster` tronque par la FIN. Aucun des deux ne pouvait rougir, et trois
# mutants du calcul de budget y survivaient.

#: La phrase du banc de budget. **Son glyphe `…` est dans la partie FIXE**, et
#: il y est pour une raison : c'est lui qui rend `M11` mesurable -- le repli
#: ASCII fait grossir le glyphe d'une colonne a trois, et mesurer le cout fixe
#: avant le repli rend la borne fausse d'exactement ce qu'il coute.
PHRASE_DU_BUDGET = ("Ce que le champ attend… en toutes lettres ; "
                    "ici : {valeur} (fin).")

#: La QUEUE de la phrase. Une phrase tronquee par la fin perd ce que le champ
#: attend, c'est-a-dire tout son objet : c'est la seule assertion qui
#: distingue un budget juste d'un budget rattrape par le garde-fou.
QUEUE_DE_LA_PHRASE = "(fin)."

#: Une valeur DEMESUREE, et ses deux bouts, ecrits a la main. `abreger_nom`
#: abrege **au milieu** parce qu'un nom porte son identite a ses deux bouts :
#: sous `M9`, la queue disparait et `…_camera_A` et `…_camera_B` rendent la
#: meme ligne -- litteralement le mode de panne que la fonction existe pour
#: empecher.
VALEUR_DEMESUREE = "planche-du-tournage-nocturne-BIS_camera_A-prise-07.png"
TETE_DE_LA_VALEUR = "planch"
QUEUE_DE_LA_VALEUR = "07.png"


def _tete_du_temoin(valeur: str, ascii_seul: bool) -> str:
    """La ligne de tete d'une aide de synthese, au budget REEL de la fenetre."""
    aide = aide_de_champ.AideDeChamp({"a": PHRASE_DU_BUDGET},
                                     formulaire=FormulaireTemoin())
    aide.basculer("a")
    return aide.ligne_de_tete("a", utile=jetons.largeur_utile(), valeur=valeur,
                              indent="  ", ascii_seul=ascii_seul)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_QUEUE_de_la_phrase_et_les_DEUX_BOUTS_de_la_valeur_survivent(
        ascii_seul):
    """AC 5.5, mesuree pour de bon (`F-C1-5`, mutants `M9`, `M10`, `M11`).

    Quatre assertions, et chacune ferme un mode de panne distinct :

    * la largeur tient -- elle tenait deja, `ajuster` la garantit ;
    * la phrase se **termine** par sa queue : c'est ce qui rougit des que le
      budget est trop large et que le garde-fou tronque par la fin. `M9` (le
      cout fixe n'est plus soustrait), `M10` (l'indentation sort du budget) et
      `M11` (le repli ne precede plus la mesure) y meurent tous les trois ;
    * les **deux bouts** de la valeur se lisent : c'est le contrat de
      `jetons.abreger_nom`, et c'est ce que `M9` detruit en particulier.
    """
    ligne = _tete_du_temoin(VALEUR_DEMESUREE, ascii_seul)
    assert jetons.colonnes(ligne) <= jetons.largeur_utile(), ligne
    assert ligne.endswith(QUEUE_DE_LA_PHRASE), ligne
    assert TETE_DE_LA_VALEUR in ligne, ligne
    assert QUEUE_DE_LA_VALEUR in ligne, ligne


#: Une valeur qui **GROSSIT au repli** -- quatre `…` a une colonne qui en
#: prennent trois --, et son TEMOIN de meme longueur sans le glyphe. Le temoin
#: isole la cause : sans lui, un banc rouge ne dirait pas si c'est le repli ou
#: la longueur qui coupe.
#:
#: Le geste est **garanti** par `EPIC11-ARB-68` (« toute lettre imprimable est
#: du texte a cote d'un champ de saisie »), et le glyphe est aussi dans la
#: donnee LIVREE : `atelier_scan.AIDE_DPI_REFUSE` porte un tiret cadratin et
#: mesure 20 colonnes brutes contre 21 repliees.
#:
#: **Les glyphes sont AUX DEUX BOUTS, et c'est la seule place qui mesure.**
#: `abreger_nom` abrege au milieu : un glyphe pose au centre de la valeur est
#: jete avec le milieu, et le mutant survit. Trouve en le mesurant -- une
#: premiere redaction portait ses quatre `…` au milieu et laissait `F-C2-1`
#: vivant.
VALEUR_QUI_GROSSIT = "pla…che-du-tournage nocturne camera A prise 07.p…g"
VALEUR_TEMOIN = "pla-che-du-tournage nocturne camera A prise 07.p-g"


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("valeur,nomme", [(VALEUR_TEMOIN, "temoin"),
                                          (VALEUR_QUI_GROSSIT, "glyphe")])
def test_la_QUEUE_de_la_phrase_survit_a_une_valeur_qui_GROSSIT_au_repli(
        valeur, nomme, ascii_seul):
    """`F-C2-1` : la valeur etait mesuree AVANT son repli ASCII.

    `abreger_nom` comptait les colonnes de la valeur **brute** alors que la
    partie fixe, elle, etait repliee avant mesure. Le budget etait donc calcule
    dans le mauvais regime pour la moitie que la methode abrege, et `ajuster`
    rattrapait la borne en tronquant par la fin -- exactement ce que le
    docstring de la methode interdit.

    Trois des quatre parametrisations passaient deja : c'est le temoin, et
    c'est ce qui prouve que seul le repli est en jeu.
    """
    ligne = _tete_du_temoin(valeur, ascii_seul)
    assert jetons.colonnes(ligne) <= jetons.largeur_utile(), (nomme, ligne)
    assert ligne.endswith(QUEUE_DE_LA_PHRASE), (nomme, ascii_seul, ligne)


def test_le_GLYPHE_qui_grossit_est_bien_DANS_la_donnee_livree():
    """Anti-vacuite du banc precedent, et il n'est pas decoratif : sans lui, on
    pourrait croire que le cas ne se rencontre que sur une saisie. Le constat
    « hors bornes » de `E3-1` **grossit** au repli, et une colonne de plus
    suffit a decaler la coupe."""
    brut = depot.AIDE_DPI_REFUSE
    assert jetons.colonnes(jetons.replier_ascii(brut)) > jetons.colonnes(brut)


# ---------------------------------------------------------------------------
# T2-C -- une saisie de BLANCS se lit VIDE, sur les trois porteurs (`F-C1-1`)
# ---------------------------------------------------------------------------

#: Le champ de saisie de chaque porteur sur lequel une **espace** se frappe par
#: reflexe -- `Espace` est un geste annonce sur une ligne voisine --, et ce que
#: la colonne de droite doit alors continuer de dire.
#:
#: Les trois porteurs y sont : le mot de l'absence doit etre le **meme**
#: partout, et `E3-1` etait le seul des trois a lire l'attribut brut au lieu
#: d'une methode `saisie()` (defaut `F-C1-1`, qui ferme aussi `F-C1-9` -- la
#: divergence vivante entre `E3-1` et `E3-9` sur la meme question de dpi).
#:
#: La troisieme moitie du couple est la mention attendue, ou `None` quand
#: l'ecran **n'a pas** de colonne de mention. Le nommer le rend mesurable ; le
#: taire rendrait la frontiere verte le jour ou un porteur perdrait sa mention.
#:
#: **`E5-6` y est entre le 2026-09-06** (manque `MQ-6` de l'audit du parcours).
#: Il portait `None` -- ecart nomme du lot `A` du 2026-09-04 : « `E5-6` n'a pas
#: de `mention_du_champ` » --, et l'audit a mesure ce que cet ecart coutait au
#: clavier : rien a l'ecran ne disait que le premier champ etait obligatoire,
#: alors que ses deux ecrans jumeaux le disent. Les trois porteurs portent
#: desormais la meme colonne, et c'est l'egalite ci-dessous qui le tient.
CHAMP_A_BLANCS = {
    "mixed_media_utility.tui.atelier_pdf_calibration.EcranMireReglages":
        (mire.CHAMP_CHAINE, "chaine", depot.MENTION_REQUIS),
    "mixed_media_utility.tui.atelier_scan.EcranScanDepot":
        (depot.CHAMP_DPI, "dpi", depot.MENTION_REQUIS_DPI),
    "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrerLaChaine":
        (calibrate.CHAMP_DPI, "dpi", calibrate.MENTION_REQUIS_DPI),
}


@pytest.mark.parametrize("nom", sorted(CHAMP_A_BLANCS))
def test_une_saisie_de_BLANCS_se_lit_VIDE_sur_les_TROIS_porteurs(nom):
    """**Le defaut deja paye sur `E3-9`, encore ouvert sur `E3-1`.**

    Une espace frappee dans le champ requis eteignait les canaux qui disent
    « rien ici » pendant que l'action principale restait inaccessible : un
    champ requis qui se lit comme rempli et ne l'est pas.

    Les trois canaux purs sont mesures ensemble, et le **temoin** rempli l'est
    aussi : un banc qui n'assertait que le cas des blancs serait vert sur un
    formulaire qui dirait « rien ici » de tout, y compris d'une saisie reelle.
    """
    cle, attribut, mention = CHAMP_A_BLANCS[nom]
    for blancs in (" ", "   ", "\t", " \n "):
        ecran = PORTEURS[nom]["fabrique"]()
        setattr(ecran.formulaire, attribut, blancs)
        assert ecran.formulaire.saisie(cle) == "", (nom, repr(blancs))
        assert ecran.valeur_de_l_aide(cle) == aide_de_champ.VALEUR_ABSENTE, (
            nom, repr(blancs))
        # L'ecart de `E5-6` est mesure en EGALITE, dans les deux sens : un
        # porteur qui gagnerait une mention sans entrer dans cette table, ou
        # qui en perdrait une, fait rougir ici.
        assert hasattr(ecran, "mention_du_champ") is (mention is not None), nom
        if mention is not None:
            assert ecran.mention_du_champ(cle) == mention, (nom, repr(blancs))

    # Le temoin : la meme frappe, entouree de blancs, se lit **remplie**.
    ecran = PORTEURS[nom]["fabrique"]()
    setattr(ecran.formulaire, attribut, "  600  ")
    assert ecran.formulaire.saisie(cle) == "600", nom
    assert ecran.valeur_de_l_aide(cle) == "600", nom
    if mention is not None:
        assert ecran.mention_du_champ(cle) == "", nom


def test_un_dpi_de_BLANCS_eteint_le_GLYPHE_et_la_LIGNE_D_ETAT_de_E3_1(banc):
    """Les deux canaux qui n'etaient pas mesurables sans terminal, sur le vrai
    chemin produit -- la colonne de valeur et la ligne d'etat.

    `peut_detecter` reste faux dans les deux cas : c'est ce qui fait de l'ecart
    un mensonge et non une divergence de style.
    """
    ecran = ecran_depot()

    async def scenario(_pilote):
        ecran.formulaire.source = source_mesuree()
        ecran.formulaire.dpi = "  "
        neutre = ecran.app.glyphes["neutre"]
        return (ecran.valeur_du_champ(depot.CHAMP_DPI), neutre, ecran.etat(),
                ecran.formulaire.peut_detecter)

    valeur, neutre, etat, peut = monte(ecran, scenario, banc)
    assert valeur == neutre, valeur
    assert depot.PHRASE_DPI_REQUIS in etat, etat
    assert peut is False


# ===========================================================================
# Les maquettes que ce banc citait sans les LIRE
# ===========================================================================
#
# **Le defaut, mesure le 2026-09-06.** Ce banc cite `E3-1`, `E3-9` et `E5-6`
# jusqu'au nom de leurs champs, et n'ouvrait aucun dessin. Deux de ses
# litteraux appartenaient a un dessin cite -- et ils n'y appartiennent PAS de
# la meme facon, ce que la section ci-dessous mesure plutot que d'aplatir :
# l'un est une recopie, l'autre une coincidence de sous-chaine.

#: Les dessins repris ici, a leur source.
MAQUETTES = (Path(__file__).resolve().parents[3] / "_bmad-output"
             / "planning-artifacts" / "ux-designs" / "ux-tui-2026-08-27"
             / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il n'est pas du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


def test_le_PIED_du_palier_temoin_est_celui_du_menu_des_ATELIERS():
    """`Q quitter` vient de `E1-1`, le palier que le temoin DOUBLE.

    Trois dessins, trois reponses distinctes, et c'est ce qui fait la mesure :

    * `E1-1` -- le menu des ateliers -- le dessine : c'est la SOURCE du pied
      que `PalierTemoin("Ateliers", ...)` rejoue ;
    * `E3-1` le dessine aussi, et c'est pour ca qu'une confrontation
      automatique l'y trouve d'abord. Le trouver la ne dit rien de la
      filiation : c'est un autre ecran qui porte le meme pied ;
    * `E3-9` ne le dessine PAS -- son pied est `Échap menu Scan`, sans sortie
      directe. Un ecran monte au-dessus du palier n'herite pas de son pied,
      et si les trois repondaient pareil la mesure serait muette.
    """
    ateliers = dessin_de_la_maquette("E1-1-menu-ateliers.txt")
    depot_dessine = dessin_de_la_maquette("E3-1-scan-depot.txt")
    calibrate_dessine = dessin_de_la_maquette("E3-9-scan-calibrate.txt")
    assert PIED_DU_PALIER in ateliers
    assert PIED_DU_PALIER in depot_dessine
    assert PIED_DU_PALIER not in calibrate_dessine


def test_scan_requis_n_est_PAS_une_recopie_mais_une_COINCIDENCE_de_sous_chaine():
    """La mention du `Valider` se TROUVE dans `E3-9` sans en etre recopiee.

    Une confrontation par sous-chaine dit « ce litteral est dans le dessin »
    et s'arrete la. Ici la reponse est vraie et la conclusion serait fausse :
    `E3-9` ne dessine aucune ligne `Valider`. Ce qu'il dessine, c'est la ligne
    d'etat `résolution de scan requise — …`, dont `scan requis` est un
    prefixe de `scan requise`. La mesure qui tranche : retirer la ligne d'etat
    du dessin fait DISPARAITRE le litteral. S'il en avait ete recopie, il
    survivrait ailleurs dans le dessin.
    """
    dessin = dessin_de_la_maquette("E3-9-scan-calibrate.txt")
    assert MENTION_DU_VALIDER_SANS_SCAN in dessin

    ligne_d_etat = " ".join(calibrate.PHRASE_DPI_REQUIS.split())
    assert ligne_d_etat in dessin
    assert MENTION_DU_VALIDER_SANS_SCAN in ligne_d_etat

    sans_l_etat = dessin.replace(ligne_d_etat, "")
    assert MENTION_DU_VALIDER_SANS_SCAN not in sans_l_etat

    # Le temoin qui rend la mesure non tautologique : le pied, lui, SURVIT au
    # retrait de la ligne d'etat, parce qu'il est dessine ailleurs.
    assert "Tab champ" in sans_l_etat

    # Et le dessin ne porte nulle part la ligne `Valider` que le banc mesure :
    # la mention vit dans le module, pas dans la maquette.
    assert calibrate.CHAMP_VALIDER not in dessin
    assert MENTION_DU_VALIDER_SANS_SCAN == calibrate.MENTION_VALIDER_SANS_SCAN


def test_la_ligne_d_etat_est_la_MEME_phrase_sur_les_DEUX_ecrans_a_leur_verbe_pres():
    """`E3-1` et `E3-9` partagent la tete de la phrase et divergent en queue.

    C'est le volet symetrique de la coincidence ci-dessus : si les deux
    dessins portaient exactement la meme ligne, on ne saurait pas dire que
    chaque module tient la SIENNE.
    """
    tete = "résolution de scan requise"
    depot_dessine = dessin_de_la_maquette("E3-1-scan-depot.txt")
    calibrate_dessine = dessin_de_la_maquette("E3-9-scan-calibrate.txt")

    assert " ".join(depot.PHRASE_DPI_REQUIS.split()) in depot_dessine
    assert " ".join(calibrate.PHRASE_DPI_REQUIS.split()) in calibrate_dessine
    assert depot.PHRASE_DPI_REQUIS.startswith(tete)
    assert calibrate.PHRASE_DPI_REQUIS.startswith(tete)
    assert depot.PHRASE_DPI_REQUIS != calibrate.PHRASE_DPI_REQUIS


def test_la_confrontation_REFUSE_ce_qui_n_est_PAS_dessine():
    """Frontiere negative : sans elle, une comparaison toujours vraie passe."""
    ateliers = dessin_de_la_maquette("E1-1-menu-ateliers.txt")
    calibrate_dessine = dessin_de_la_maquette("E3-9-scan-calibrate.txt")
    assert PIED_DU_PALIER + " et revenir" not in ateliers
    assert "Q fermer" not in ateliers
    assert calibrate.PHRASE_SCAN_REQUIS not in calibrate_dessine
