# -*- coding: utf-8 -*-
"""Le palier Projet : trois commandes de cycle de vie (11.3 AC 5, 11.11 AC 2).

**TROIS depuis la story 11.11**, et la troisieme est la gestion des medias
(`EPIC11-ARB-155`). Le paragraphe qui suit garde son arbitrage d'origine parce
qu'il porte encore : il dit que le `relink` n'a pas d'ECRAN a lui ici, ce qui
reste vrai -- il est un geste de l'inventaire, atteint par `Ctrl+L` sur un
objet declare et absent, et non une quatrieme entree de menu.

`EPIC11-ARB-18` (`Q4-b`) : **deux commandes de cycle de vie, et non trois.**
`set-default-profile` et `reconstruct-project`. Le `relink` **n'a pas d'ecran
ici** -- sa porte est `E2-1`, l'ecran ou l'absence du rush se voit
(`EPIC11-ARB-23`, confirme par `32`). Une frontiere negative le mesure a zero.

**Ce module appelle `io/`, jamais `cli.py`.** Les fonctions de `cli.py`
impriment sur `stderr` et rendent un code retour : les appeler depuis une TUI
enverrait des lignes dans le terminal **sous** l'ecran dessine, et rendrait un
entier la ou l'interface a besoin d'un document ou d'un refus nomme.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from ..gui.depot_projets import NOM_FICHIER_PROJET
from ..io import calibration_profile, profile_designation, reconstruction
from ..io.extraction_manifest import MANIFEST_SCHEMA_VERSION, _atomic_write
from ..io.payload import parse_payload
from . import jetons
from .coque import Palier
from .panneau import ChoixExclusif, Issue, LigneChiffree, Panneau

#: Ligne de raccourcis du palier. Constante de module, comme celles des deux
#: autres ecrans : c'est ce qui la fait balayer par la garde d'epic.
#: **Majuscule d'affichage, touche NUE en minuscule** -- la regle des
#: majuscules de raccourci, ecrite en entier dans `coque.py`. La lettre
#: annoncee ici est en majuscule ; la touche cablee reste la minuscule.
RACCOURCIS_PROJET = ("⏎ choisir  ↑↓ naviguer  Échap ateliers  "
                     "F1 aide  Q quitter")

#: Les entrees du palier, et leurs cles nomment la commande de coeur qu'elles
#: servent : `EPIC11-ARB-36` veut que « tout champ de formulaire nomme
#: l'argument de coeur qu'il alimente », et la meme exigence vaut d'un cran
#: au-dessus pour une entree qui nomme une commande.
#:
#: **TROIS depuis la story 11.11** (`EPIC11-ARB-155`, Egan le 2026-09-01,
#: verbatim : « On doit y entrer par l'entree "Projet" qui existe deja sur la
#: page des ateliers »). La troisieme est en TETE, comme `E6-0` la dessine :
#: c'est celle qui sert le plus souvent, les deux autres etant des gestes de
#: configuration qu'on pose une fois.
#:
#: `ENTREE_MEDIAS` porte `"project"` et non un nom de commande complet : c'est
#: le sous-parseur de `cli.py`, « porte-nom naturel des gestes de maintenance
#: d'arborescence », et l'entree en sert **deux** -- l'inventaire
#: (`project_inventory.inventorier_le_projet`) et le retrait
#: (`project_maintenance.remove_project_element`, `mmu project remove`).
#: Nommer l'une des deux ferait mentir l'entree sur ce qu'elle ouvre.
ENTREE_MEDIAS = "project"
ENTREE_PROFIL = "set-default-profile"
ENTREE_RECONSTRUCTION = "reconstruct-project"

LIBELLES = {
    ENTREE_MEDIAS: "Gestion des médias",
    ENTREE_PROFIL: "Profil de calibration par defaut",
    ENTREE_RECONSTRUCTION: "Reconstruire le projet depuis des QR lus",
}

PHRASES = {
    ENTREE_MEDIAS: "Gérer les médias du projet : ajout, relink et suppression",
    ENTREE_PROFIL: "Poser le profil que les scans utiliseront sans le repeter",
    ENTREE_RECONSTRUCTION: "Rebatir un project.json depuis les payloads de page",
}


def entrees_du_palier() -> ChoixExclusif:
    """Les TROIS commandes, en point de decision (story 11.11, AC 2.1).

    `ChoixExclusif` refuse a la construction qu'une issue soit preselectionnee
    (`EPIC11-ARB-7`) et qu'aucune ne soit sans ecriture. Les trois entrees
    portent `ecrit=False` : **entrer** dans une commande n'ecrit rien -- c'est
    le panneau de confirmation, plus loin, qui engage. La gestion des medias ne
    fait pas exception, et c'est le point de la story 11.11 : son premier ecran
    est un INVENTAIRE, qui lit.
    """
    return ChoixExclusif([
        Issue(ENTREE_MEDIAS, LIBELLES[ENTREE_MEDIAS], ecrit=False),
        Issue(ENTREE_PROFIL, LIBELLES[ENTREE_PROFIL], ecrit=False),
        Issue(ENTREE_RECONSTRUCTION, LIBELLES[ENTREE_RECONSTRUCTION],
              ecrit=False),
    ])


class CibleSansProjet(ValueError):
    """La cible designee n'est pas un projet.

    **Ce refus n'existe pas dans `io/`, et il a fallu le mesurer pour s'en
    apercevoir** : `import_designated_profile` ecrit sans broncher dans
    n'importe quel dossier. La garde vit dans `cli.py`, **avant** l'appel --
    donc un appelant qui passe par `io/` directement, comme cette TUI le doit
    (voir le docstring du module), la saute entierement et poserait une
    arborescence `versions/calibration/` dans un dossier quelconque.

    Le refus est donc pose ici, sur la **meme** condition que `cli.py` et lue de
    la meme constante -- jamais sur un litteral. La duplication est reelle et
    assumee le temps que le coeur porte la garde ; elle est versee a
    `deferred-work.md` avec sa mesure.

    **Ce refus porte sur la CIBLE, jamais sur la provenance du profil**, et le
    distinguo n'est pas cosmetique : « un refus lie au projet du *profil* est
    precisement ce que l'AC interdit » (`EPIC5-ARB-82`).
    """


@dataclass(frozen=True)
class ProfilPose:
    """Ce qu'une pose de profil par defaut a produit, tel que le coeur le rend."""

    chaine: str
    forme: str
    chemin: Path


def _cible_est_un_projet(dossier_projet) -> Path:
    """La garde de cible, **calculee une seule fois pour l'apercu et l'ecriture**.

    Elle vit ici et pas dans le coeur : `import_designated_profile` ecrit dans
    **n'importe quel** dossier, et le refus qui l'en empeche est pose dans
    `cli.py` *avant* l'appel -- donc tout appelant de `io/` le saute. Voir
    `V2-2` dans `deferred-work.md` ; le jour ou le coeur gagne la garde, un
    test symetrique passe au rouge et celle-ci se retire.
    """
    dossier_projet = Path(dossier_projet)
    if not (dossier_projet / NOM_FICHIER_PROJET).is_file():
        raise CibleSansProjet(
            f"Aucun {NOM_FICHIER_PROJET} dans {dossier_projet} : il n'y a pas "
            "de projet ou poser un profil par defaut. Ce refus porte sur la "
            "cible, pas sur le profil designe.")
    return dossier_projet


def apercu_de_profil(dossier_projet, source) -> ProfilPose:
    """Ce que `set-default-profile` ecrira -- **sans rien ecrire** (AC 5.5).

    `EPIC11-ARB-4` exige le panneau chiffre *avant* toute ecriture. Un panneau
    construit sur le resultat de la pose serait un panneau **de resultat**
    portant le titre « A ecrire » : il ne pourrait plus rien empecher.

    Les trois valeurs sont derivees par les memes fonctions que l'ecriture --
    `read_designated_document` valide et lit, `profile_path_for_document`
    calcule le radical du nom de fichier. Une seconde formule pour le chemin
    ferait mentir l'apercu, exactement comme du cote de `EcranCreation`.
    """
    dossier_projet = _cible_est_un_projet(dossier_projet)
    document = profile_designation.read_designated_document(source)
    return ProfilPose(
        chaine=document["chain_id"],
        forme=document["correction_form_id"],
        chemin=calibration_profile.profile_path_for_document(
            dossier_projet, document))


def poser_le_profil_par_defaut(dossier_projet, source) -> ProfilPose:
    """`set-default-profile`, servi par le **coeur** (AC 5.2).

    Appelle `profile_designation.import_designated_profile(..., as_default=True)`,
    qui valide le profil, l'ecrit sous `versions/calibration/<radical>.json` et
    l'inscrit au manifest. **Ce module n'ecrit ni le fichier ni l'entree** : il
    n'a aucun chemin vers le disque, et l'artefact produit est donc identique a
    celui de `mmu set-default-profile` par construction plutot que par
    verification.

    **Aucun refus lie a la provenance** (`EPIC5-ARB-82`) : « le profil designe
    peut venir de n'importe ou ». Rien ici ne teste d'ou vient le fichier, et
    une frontiere negative le mesure.

    Le refus qui existe porte sur **la cible** -- un dossier qui n'est pas un
    projet --, et le distinguo compte : « un refus lie au projet du *profil* est
    precisement ce que l'AC interdit ».
    """
    dossier_projet = _cible_est_un_projet(dossier_projet)
    document, chemin = profile_designation.import_designated_profile(
        dossier_projet, Path(source), as_default=True)
    return ProfilPose(chaine=document["chain_id"],
                      forme=document["correction_form_id"],
                      chemin=chemin)


def nom_du_profil(entree) -> str:
    """Sous quel nom un profil designe s'affiche. **Une seule redaction.**

    Le nom du fichier designe (`designated_from`) d'abord, son `chain_id`
    ensuite : c'est la provenance que l'operateur reconnait -- il a designe un
    fichier --, et l'identite de chaine ne sert que si l'entree a ete ecrite
    avant que la provenance ne soit consignee.

    Elle vit ici, en fonction de module, parce que **deux ecrans l'affichent** :
    le pied du palier Projet et le pied du menu du Scan (story 11.5, AC 2.2).
    Deux redactions divergeraient au premier ajustement, et l'ecart ne se
    verrait que sur un projet dont le profil a perdu sa provenance -- soit
    jamais, en fabrique.
    """
    if not entree:
        return ""
    return (entree.get(profile_designation.ENTRY_SOURCE_KEY)
            or entree.get("chain_id") or "?")


def profil_par_defaut(dossier_projet):
    """Ce que l'atelier Scan proposera -- **l'entree et le chemin, distincts**.

    Rend `(entree, chemin)`. Les deux ne disent pas la meme chose et l'ecran ne
    doit pas les confondre : `default_profile_path` rend `None` quand le
    **fichier** a disparu, tandis que l'entree de manifest « reste vraie de ce
    que le projet a utilise ». Un projet peut donc declarer un profil dont le
    fichier n'est plus la, et c'est une information -- pas une absence.
    """
    dossier_projet = Path(dossier_projet)
    return (profile_designation.default_profile_entry(dossier_projet),
            profile_designation.default_profile_path(dossier_projet))


# ---------------------------------------------------------------------------
# `reconstruct-project` (AC 5.4).
# ---------------------------------------------------------------------------

class PayloadIntrouvable(ValueError):
    """Un fichier de payload designe n'existe pas. Refus AVANT toute lecture."""


@dataclass(frozen=True)
class ProjetReconstruit:
    """Ce qu'une reconstruction a produit : de quoi remplir un panneau chiffre."""

    pages: int
    rushes: int
    lots: int
    chemin: Path


def lire_les_payloads(fichiers) -> list[dict]:
    """Lire les textes de QR, **par le meme chemin que le scan**.

    `parse_payload`, jamais un `json.loads` nu -- et ce n'est pas une preference
    de style : la commande `reconstruct-project` lisait autrefois un `json.loads`
    nu, donc exigeait un document a cles **longues** portant `2.0`, c'est-a-dire
    exactement celui que `parse_payload` refuse comme perime. **Aucune entree ne
    satisfaisait les deux cotes a la fois**, et le texte reel d'une planche
    ressortait en echec avec « les douze champs annonces manquants » alors
    qu'aucun ne manquait. Le defaut est deja paye ; on ne le repaie pas.

    Le motif d'un payload refuse est celui du coeur, **verbatim** : c'est deja
    une phrase pour l'operateur (« planche perimee, a reimprimer », « QR
    etranger, aucun tirage en cause »), et la resumer la detruirait.
    """
    documents = []
    for fichier in fichiers:
        chemin = Path(fichier)
        if not chemin.is_file():
            raise PayloadIntrouvable(f"Fichier payload introuvable : {chemin}")
        documents.append(parse_payload(chemin.read_text(encoding="utf-8")))
    return documents


def apercu_de_reconstruction(dossier_projet, fichiers,
                             manifeste_partiel=None) -> ProjetReconstruit:
    """Ce que la reconstruction produirait -- **sans rien ecrire**.

    C'est ce qui alimente le panneau chiffre de la story 11.1 : `EPIC11-ARB-4`
    exige un point de jugement avant toute ecriture, et un apercu qui
    ecrirait pour se calculer ne serait plus un apercu.

    `reconstruct_project_manifest` est une **couche pure** : elle ne touche pas
    au disque, donc l'apercu et l'ecriture partagent litteralement le meme
    calcul. Deux calculs distincts pourraient diverger, et c'est le panneau qui
    mentirait.
    """
    documents = lire_les_payloads(fichiers)
    manifeste = reconstruction.reconstruct_project_manifest(
        documents, manifeste_partiel)
    return ProjetReconstruit(
        pages=len(documents),
        rushes=len(manifeste.get("rushes") or []),
        lots=len(manifeste.get("lots") or []),
        chemin=Path(dossier_projet) / NOM_FICHIER_PROJET,
    )


def reconstruire_le_projet(dossier_projet, fichiers,
                           manifeste_partiel=None) -> ProjetReconstruit:
    """Ecrire le `project.json` reconstruit, par l'ecriture atomique du coeur.

    `_atomic_write` valide un temporaire **avant** de le mettre en place : un
    document que le coeur refuserait ne peut donc pas atterrir sur le disque, et
    un echec laisse le `project.json` precedent strictement intact. C'est la
    meme porte que la creation de projet emprunte.
    """
    dossier_projet = Path(dossier_projet)
    documents = lire_les_payloads(fichiers)
    manifeste = reconstruction.reconstruct_project_manifest(
        documents, manifeste_partiel)
    dossier_projet.mkdir(parents=True, exist_ok=True)
    chemin = dossier_projet / NOM_FICHIER_PROJET
    _atomic_write(chemin, manifeste)
    return ProjetReconstruit(
        pages=len(documents),
        rushes=len(manifeste.get("rushes") or []),
        lots=len(manifeste.get("lots") or []),
        chemin=chemin,
    )


def panneau_de_reconstruction(apercu: ProjetReconstruit) -> Panneau:
    """Le panneau chiffre qui precede l'ecriture (`EPIC11-ARB-4`, AC 5.5).

    **Tout chiffre porte son unite** -- `LigneChiffree` le refuse a la
    construction, pas en revue. Aucun majorant ici : les trois comptes sont
    **mesures** sur le manifest deja calcule, pas estimes.
    """
    return Panneau("A ecrire", [
        LigneChiffree("Pages lues", apercu.pages, "pages"),
        LigneChiffree("Rushes reconstruits", apercu.rushes, "rushes"),
        LigneChiffree("Lots reconstruits", apercu.lots, "lots"),
        LigneChiffree("Fichier de projet", apercu.chemin.name),
    ])


def panneau_de_profil(apercu: ProfilPose) -> Panneau:
    """Le panneau chiffre qui precede la pose (`EPIC11-ARB-4`, AC 5.5).

    Il se construit sur l'**apercu**, jamais sur la pose : voir
    `apercu_de_profil`. Le parametre garde le type `ProfilPose` parce que les
    deux portent litteralement les memes trois valeurs -- c'est ce qu'un test
    exige.
    """
    return Panneau("A ecrire", [
        LigneChiffree("Chaine de scan", apercu.chaine),
        LigneChiffree("Forme de correction", apercu.forme),
        LigneChiffree("Fichier du profil", apercu.chemin.name),
    ])


class EcranPalierProjet(Palier):
    """Le menu du palier Projet : deux entrees, et l'etat du profil courant."""

    titre = "Projet"
    raccourcis = RACCOURCIS_PROJET

    def __init__(self, dossier=None,
                 entrer: Callable[[Issue], None] | None = None) -> None:
        super().__init__()
        self.dossier = dossier
        self.choix = entrees_du_palier()
        self._entrer = entrer
        self._etat_a_dire = ""

    def lignes(self) -> list[str]:
        largeur = jetons.largeur_utile(self.app.size.width)
        # **ECART NOMME plutot que corrige** : `E6-0` ecrit « Que faire sur
        # projet_demo lui-même ? », c'est-a-dire le NOM du projet, comme
        # `ecran_ateliers` le fait deja de son cote. Le corriger ici depasse
        # l'AC 2.1, qui ne porte que sur la troisieme entree ; l'ecart est
        # verse au registre de la story 11.11.
        corps = ["Que faire sur ce projet ?", ""]
        # **Par `ChoixExclusif.rendu()`, pas par une boucle reecrite ici.** La
        # couche 3 de la revue a releve les deux rendus divergents comme une
        # incoherence entre stories ; c'est aussi ce qui aurait fait rater
        # `EPIC11-ARB-45` a cet ecran.
        for ligne, issue in zip(self.choix.rendu(self.app.ascii_seul),
                                self.choix.issues):
            corps.append(ligne)
            corps.append(f"    {PHRASES[issue.cle]}")
        corps += ["", "-" * largeur, ""]
        corps += [f"  {ligne}" for ligne in self.lignes_du_profil()]
        return corps

    def lignes_du_profil(self) -> list[str]:
        """L'etat du profil par defaut. **Trois etats, pas deux.**

        Aucun profil pose ; un profil pose et present ; un profil pose dont le
        fichier a disparu. Le troisieme n'est pas le premier : le projet a
        travaille avec ce profil, et le taire ferait croire qu'il n'y en a
        jamais eu.
        """
        if self.dossier is None:
            return ["aucun profil de calibration par defaut"]
        entree, chemin = profil_par_defaut(self.dossier)
        if entree is None:
            return ["aucun profil de calibration par defaut"]
        chaine = nom_du_profil(entree)
        if chemin is None:
            return ["Profil par defaut", "  " + jetons.marque(
                "substitute", f"{chaine} -- son fichier a disparu",
                self.app.ascii_seul)]
        return ["Profil par defaut", "  " + jetons.marque(
            "complete", f"{chaine}", self.app.ascii_seul)]

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-palier-projet")
        return [Vertical(self._corps, id="centre-palier-projet")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur = jetons.largeur_utile(self.app.size.width)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, largeur, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur))
        self.poser_etat(self.etat())
        super().rafraichir()

    def etat(self) -> str:
        return self._etat_a_dire

    def on_mount(self) -> None:
        self.rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        self._etat_a_dire = ""
        if touche in ("up", "down"):
            self.choix.deplacer(-1 if touche == "up" else 1)
            return True
        if touche == "enter":
            issue = self.choix.valider()
            if issue is None:
                return True
            if self._entrer is not None:
                self._entrer(issue)
            return True
        return False


__all__ = [
    "ENTREE_MEDIAS",
    "apercu_de_profil",
    "reconstruire_le_projet",
    "panneau_de_reconstruction",
    "panneau_de_profil",
    "lire_les_payloads",
    "apercu_de_reconstruction",
    "ProjetReconstruit",
    "PayloadIntrouvable",
    "CibleSansProjet",
    "ENTREE_PROFIL",
    "ENTREE_RECONSTRUCTION",
    "LIBELLES",
    "PHRASES",
    "RACCOURCIS_PROJET",
    "EcranPalierProjet",
    "ProfilPose",
    "entrees_du_palier",
    "nom_du_profil",
    "poser_le_profil_par_defaut",
    "profil_par_defaut",
]
