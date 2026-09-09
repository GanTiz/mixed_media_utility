# -*- coding: utf-8 -*-
"""Le parcours de l'atelier Scan, temps 1 -- l'ecran du rapport et le CABLAGE.

Story 11.5, **lot F** (AC 8 et AC 9). Ce module ne contient aucune regle
metier : il **assemble** ce que les lots B a E ont livre, et il ajoute le seul
ecran que le temps 1 n'avait pas.

**Pourquoi un ecran de rapport ici, et non dans `atelier_scan_rapport.py`.** Le
lot D a livre `E3-3` / `E3-4` en **modele pur** -- « aucun `textual`, aucune
lecture de disque, aucune ecriture », c'est la premiere ligne de son docstring
et c'est la propriete qui rend ses 61 tests mesurables sans monter
d'application. Y poser une sous-classe de `Screen` la detruirait. L'ecran vit
donc **ici**, ou il est ce qu'il est : le consommateur du modele, au meme titre
que le parcours.

**Ce que le cablage ferme, et il a un compte.** Sept fois dans cet epic un
composant a ete livre, teste, exporte -- et cable **nulle part** dans
l'application (`test_rappels_cables.py` les nomme un par un ; le plus gros,
`E9`, faisait ouvrir a `mmu-tui` trois ecrans TEMOINS alors que deux paliers
reels etaient livres). Le temps 1 du Scan etait dans cet etat exact avant ce
lot : cinq ecrans livres, `ChaineReelle.entrer` menant l'entree *Scan* a
`EcranPasEncore`.

**Ce que ce module ne fait pas, et c'est structurel :**

* il **n'importe jamais `cli`** (AC 8.1), ni `gui.chargeur_detections` : la
  relecture d'un document passe par `scan_previz.scan_previz_from_json_dict`,
  qui est le lecteur normatif du coeur, pas une seconde redaction ;
* il **ne redetecte rien au temps 2** (`EPIC11-ARB-6`) : l'ecriture part du
  **document deja pose**, et ce module n'appelle ni `run_scan_detect`, ni
  `detect_lot_pages`, ni `ingest_scan_lot` sur ce chemin -- mesure a l'AST.

**Ce que le lot H de la story 11.6 y ajoute : le CABLAGE DU TEMPS 2.** Ce
module portait deux `EcranPasEncore` -- « Ecrire les frames » et « Calibrer une
chaine » --, qui etaient la forme honnete d'une absence tant que les ecrans
n'existaient pas. Les six ecrans du temps 2 sont livres (lots C a G) ; les deux
promesses sont donc **tenues**, et les deux constantes d'echeance qui les
nommaient (`QUAND_LE_TEMPS_2` ici, `QUAND_LA_CALIBRATION` dans
`atelier_scan`) sont **retirees avec leur dernier usage** : « une constante
d'echeance qui survit a l'echeance est une promesse qui ment ».

Les deux chaines cablees, de bout en bout :

* `E3-3` / `E3-4` -> `E3-5` -> `E3-6` -> `E3-7` -> `E3-8`, l'ecriture ;
* `E3-0` -> `E3-9`, la calibration d'une chaine de scan.

**Le point dur du cablage, et il n'en existe qu'un** : `confirmer_l_ecrasement`
est appele **depuis l'interieur** de `write_profile`, et `executer_en_processus`
est un appel direct. La question de collision doit donc rendre sa reponse
**de facon synchrone** au coeur qui la pose, alors que la reponse vient d'un
ecran, donc de la boucle d'evenements. Rejouer la passe n'est pas une issue :
`ingest_scan_lot` a deja ecrit dans le projet quand la question arrive. La
passe part donc dans un **fil de travail** (`run_worker(thread=True)`), et la
question traverse par :class:`QuestionDeCollision` -- voir son docstring.
"""
from __future__ import annotations

import json
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

from textual.widgets import Static

from .. import scan_previz
from . import (
    atelier_scan_calibrate,
    atelier_scan_calibration,
    atelier_scan_confirmation,
    atelier_scan_ecriture,
    atelier_scan_resultat,
    jetons,
    projet_lecture,
)
from .atelier_extraction_ecriture import _lancer_apres_le_dessin
from .atelier_scan import (CLE_DE_LA_DETECTION, EcranScanDepot,
                          EcranScanMenu)
from .atelier_scan_completion import (
    EcranCompletionQr,
    ecrire_la_correction,
    page_suivante_a_completer,
    pages_lues_du_lot,
)
from .atelier_scan_detection import (
    DemandeDeDetection,
    EcranAdoptionDeLaPlanche,
    ISSUE_ADOPTER,
    executer_et_conclure,
    lancer_la_detection,
    journal_du_produit,
    ouvrir_la_detection,
    planches_etrangeres_de,
)
from .atelier_scan_rapport import (
    ISSUE_ANNULER,
    ISSUE_COMPLETER,
    ISSUE_ECRIRE,
    ISSUE_REPRENDRE,
    TITRE_LOTS_RECONNUS,
    PageMuette,
    RapportDeDetection,
    issues_du_rapport,
    projeter,
)
from .coque import EcranPasEncore, Palier
from .palier_projet import nom_du_profil
from .execution import (EcranChiffre, EcranExecution, bloc_peint,
                        ouvrir_dans_l_explorateur_du_systeme)
from .panneau import Panneau

# ---------------------------------------------------------------------------
# Textes d'ecran. En constantes, comme partout dans le paquet : un texte ecrit
# deux fois divergerait, et les frontieres negatives les balayent (la garde des
# majuscules lit les `RACCOURCIS_*`, celle de la sobriete les `PHRASE_*`).
# ---------------------------------------------------------------------------

#: La phrase d'ouverture de `E3-3` et de `E3-4`, verbatim des deux maquettes.
#: Elle dit l'invariant du temps 1 **dans le corps**, ou il est une mesure de
#: l'ecran, et non en ligne d'etat, ou `EPIC11-ARB-56` n'admet aucun motif de
#: conception (c'est l'ecart `G6` de cette story, corrige a la source).
TITRE_DU_RAPPORT = "Ce que la détection a trouvé — rien n'est encore écrit"

#: La ligne de raccourcis du rapport.
#:
#: **`Tab journal` des maquettes n'y est PAS, et c'est un ecart assume**
#: (remonte par le lot F) : aucun ecran de journal n'est monte par le temps 1,
#: et `CoqueTui.BINDINGS` n'a pas de liaison `tab`. L'annoncer ferait
#: exactement le defaut que le lot I a paye quarante fois -- « une touche
#: annoncee en ligne de raccourcis devenait inerte ». La maquette se corrige
#: avec la 11.6, qui monte le journal ; la ligne du produit, elle, ne promet
#: que ce qu'elle tient.
RACCOURCIS_RAPPORT = "⏎ choisir  ↑↓ naviguer  Échap ateliers  F1 aide"

#: Le titre de la file, suivi de son glyphe et de sa mesure. Le modele du lot D
#: rend les lignes ; ce qui est ecrit ici est leur en-tete.
LIBELLE_EN_ATTENTE = "En attente de lecture"

#: Ce que la ligne d'etat de `E3-3` porte : **le chemin du document ecrit**.
#: C'est ce qui permet de quitter ici et de reprendre plus tard sans redetecter
#: (`EPIC11-ARB-6`, AC 5.3) -- une mesure, donc, et pas un conseil.
PHRASE_DOCUMENT_ECRIT = "Document de détection écrit : {chemin}"

#: Ce que la ligne d'etat dit quand la passe a abouti **sans ecrire de
#: document** : c'est le regime des deux arrets non fautifs du coeur (aucun QR
#: decode, ou pile de calibration seule). Une ligne vide y laisserait croire a
#: un document dont on n'aurait pas su lire le chemin.
PHRASE_AUCUN_DOCUMENT = "Aucun document de détection n'a été écrit."

#: La ligne d'etat de `E3-4`, verbatim de la maquette moins le motif de
#: conception que l'ecart `G11` a retire (« aucune issue n'est
#: preselectionnee » : vrai, mais c'est une regle, pas une mesure).
PHRASE_LOTS_INCOMPLETS = "{lots} sur {total} {verbe} incomplet{s}"

#: Les deux mesures qui suivent, quand le rapport les porte. Elles sont
#: **omises** plutot que devinees quand l'attendu manque : jamais `0`, jamais
#: `--` (`DESIGN.md` section 3, meme regle que le dpi non mesure).
PHRASE_PAGES_DU_MANQUE = "{trouvees} pages sur {attendues}"
PHRASE_FRAMES_DU_MANQUE = "{trouvees} frames sur {attendues}"

#: Le separateur des mesures d'une ligne d'etat, verbatim des maquettes.
SEPARATEUR_DE_MESURE = " · "

#: Ce que le rapport dit quand la grille ne tient pas tout ce qu'il a a
#: montrer. **Couper en le disant, jamais en silence** : une ligne qui
#: disparait sans un mot est exactement le defaut que la 11.4b a paye trois
#: fois (trois mutants `continue` -> `break`, neuf planches evanouies, 288
#: tests verts).
PHRASE_RESTE_A_DIRE = "… et {reste}"

#: Par quel geste le profil de calibration a ete designe -- ce que le coeur
#: inscrit au **journal** de la passe (`scan_write.ecrire_le_lot_detecte`,
#: `origine=`).
#:
#: `scan_write.profil_designe_du_projet` en publie deux, et **aucune ne decrit
#: ce qui s'est passe ici** : « designe en ligne de commande » est faux (il n'y
#: a pas de ligne de commande) et « pris au defaut du projet » l'est aussi des
#: que l'operateur deplace le curseur. La troisieme forme est donc neuve, et
#: c'est pour cela qu'elle est ecrite plutot qu'importee : recycler l'une des
#: deux ferait mentir le journal sur le geste qui a designe le profil.
ORIGINE_DU_PROFIL = "retenu à l'écran de calibration du Scan"

#: Ce que l'ecran de completion dit quand la planche saisie designe un lot dont
#: la passe n'a ecrit **aucun** document. Rien n'est alors ecrit -- et c'est
#: dit, plutot que d'ecrire dans le document d'un autre lot.
PHRASE_SANS_DOCUMENT = "Aucun document de détection ne porte le lot {lot}."

#: Hauteur du chrome du rapport, **hors lignes de lot, hors file et hors
#: issues** : la phrase d'ouverture, sa respiration, les deux lignes de cadre du
#: cartouche, la respiration qui suit la file, et celle qui precede les issues.
#: Ce qui varie -- lots, fichiers en attente, issues -- est compte a part par
#: :meth:`EcranRapportDeDetection.hauteur_des_lots`, sans quoi une file de trois
#: fichiers pousserait les issues hors de la grille.
HAUTEUR_DU_CHROME = 6


def _accorder(valeur: int, singulier: str, pluriel: str) -> str:
    """« 1 lot », « 2 lots ». Le pluriel suit le compte, jamais un `+ "s"`."""
    return f"{valeur} {singulier if abs(valeur) <= 1 else pluriel}"


# ---------------------------------------------------------------------------
# `E3-3` et `E3-4` -- l'ecran du rapport
# ---------------------------------------------------------------------------


class EcranRapportDeDetection(EcranChiffre):
    """`E3-3` et `E3-4` -- **deux rendus d'un seul ecran**, et rien n'est ecrit.

    Lequel des deux s'affiche se lit sur `RapportDeDetection.complet`, jamais
    sur un drapeau tenu a cote : « le rapport se recalcule, il ne se rapiece
    pas » (`EPIC11-ARB-101`, note 10). Une seconde classe pour le rapport
    complet ferait deux ecrans qui pourraient se contredire sur le meme scan.

    **Il herite d'`EcranChiffre` et n'ecrit pas un second point de jugement** :
    le cartouche, la navigation, le rendu peint des issues et le rang du
    curseur passe a `peindre` y sont deja, mesures par la story 11.1 et par le
    lot G de la 11.4. Ce que cette classe ajoute est ce qui lui est propre : la
    phrase d'ouverture, les lignes de lot, la file, et le a-cote de chaque
    issue.

    **Les issues viennent du modele du lot D** (`issues_du_rapport`), donc
    l'invariant d'`EPIC11-ARB-7` -- aucune preselectionnee, curseur sur une
    issue qui n'ecrit pas -- est leve par `ChoixExclusif.__post_init__` et non
    rejoue ici.
    """

    titre = "Scan"
    raccourcis = RACCOURCIS_RAPPORT

    #: **Une station, pas un passage.** On revient sur le rapport apres chaque
    #: planche completee, et il doit y etre au retour : le rendre transitoire
    #: le ferait sortir de la pile a la premiere descente vers `E3-4b`.
    TRANSITOIRE = False

    def __init__(self, rapport: RapportDeDetection, *,
                 sur_issue: Callable[[Any], None],
                 document: str | None = None) -> None:
        suites = issues_du_rapport(rapport)
        super().__init__(Panneau(TITRE_LOTS_RECONNUS), suites.choix,
                         sur_issue=sur_issue)
        self.rapport = rapport
        #: Les issues **et leur a-cote**, tels que le modele du lot D les rend.
        #: Le nom evite `self._issues`, qui est le WIDGET monte par la classe de
        #: base : deux noms voisins pour un modele et son rendu sont deux
        #: occasions de les confondre.
        self.suites = suites
        #: Le chemin du document de detection ecrit par la passe, **tel que le
        #: coeur l'a rendu**. Jamais reconstruit depuis un slug : les deux
        #: divergent des qu'un fichier deja sous `scans/` est ingere en place.
        self.document = document

    # -- lecture ------------------------------------------------------------

    def budget_du_corps(self) -> int:
        """Les lignes que la grille laisse aux lots ET a la file.

        Derivee de la geometrie et du nombre d'issues, jamais saisie : c'est la
        meme discipline que `jetons.HAUTEUR_CENTRE_AU_PLANCHER`, qui se deduit
        du plancher au lieu de valoir 17 en dur.

        **Mesure au plancher, jamais a la taille courante** : « au-dela de 80
        colonnes, la place gagnee allonge les lignes ; elle n'ajoute jamais une
        seconde colonne » (`EPIC11-ARB-21`). Un rapport qui remplirait une
        grande fenetre deborderait la petite, et c'est la petite qui fait foi.
        """
        return max(jetons.HAUTEUR_CENTRE_AU_PLANCHER - HAUTEUR_DU_CHROME
                   - len(self.choix.issues), 2)

    def hauteur_des_lots(self) -> int:
        """Ce qui revient aux lots. **Ils passent avant la file, et c'est un
        choix.**

        Les deux ne tiennent pas toujours ensemble : trois lots, leurs planches
        manquantes et un reliquat de trois fichiers font deja plus de lignes que
        la grille n'en a. Ce sont les lots qui gagnent -- ils sont l'objet du
        jugement que cet ecran demande -- et la file garde **au moins son
        en-tete chiffre**, qui est exactement ce que la maquette `E3-4` montre.
        """
        return max(self.budget_du_corps() - 1, 1)

    def lignes_des_lots(self) -> list[str]:
        """Une ligne par lot reconnu, **dans l'ordre que le modele parcourt**.

        Cet ordre est celui des documents recus, c'est-a-dire celui du tri du
        coeur : il n'est jamais retrie ici. C'est ce qui permet a un banc de
        verifier le rang d'une cible sur la liste que ce code parcourt, et non
        sur celle que sa fabrique croit ecrire (`CLAUDE.md`, point 2 bis).

        Les sous-lignes d'un lot incomplet -- planches manquantes, planches
        muettes -- sont rattachees par le glyphe `rattachement`, comme `E3-4`
        les montre.
        """
        table = self.app.glyphes
        largeur = jetons.largeur_de_cartouche(self.app.size.width)
        place = self.hauteur_des_lots()
        blocs = [[self._ligne_de_lot(lot, table, largeur)]
                 + self._sous_lignes(lot, table, largeur)
                 for lot in self.rapport.lots]
        lignes: list[str] = []
        dessines = 0
        for bloc in blocs:
            # **La ligne qui dira le reste se RESERVE d'avance**, tant qu'un lot
            # reste apres celui-ci. La reserver apres coup obligerait a retirer
            # une ligne deja posee, donc a defaire un lot deja compte : le
            # compte annonce serait alors faux d'une unite -- mesure faite, il
            # disait « 3 autres lots » pour 4.
            reserve = 1 if dessines + 1 < len(blocs) else 0
            if len(lignes) + len(bloc) + reserve > place:
                break
            lignes += bloc
            dessines += 1
        if dessines < len(blocs):
            # Couper est admis ; couper EN SILENCE ne l'est pas -- c'est le
            # defaut que la 11.4b a paye trois fois, neuf planches evanouies
            # et 288 tests verts.
            lignes.append(PHRASE_RESTE_A_DIRE.format(
                reste=_accorder(len(blocs) - dessines, "autre lot",
                                "autres lots")))
        return lignes

    def _ligne_de_lot(self, lot, table, largeur: int) -> str:
        """`● lot_25fps   8 pages / 8   124 frames / 124   complet`.

        Les deux cardinaux attendus valent `None` quand aucune source ne les
        porte, et la ligne ne montre alors **rien** a leur place : jamais `0`,
        jamais `/ --`, jamais une valeur devinee.
        """
        pages = self._sur(lot.pages_trouvees, lot.pages_attendues, "pages")
        frames = self._sur(lot.frames, lot.frames_attendues, "frames")
        gauche = f"{table[lot.glyphe]} {lot.lot_id}"
        colonnes = [f"{gauche:<22}", f"{pages:<16}", f"{frames:<20}",
                    lot.completude]
        return jetons.ajuster("".join(colonnes), largeur, self.app.ascii_seul)

    @staticmethod
    def _sur(trouve: int, attendu: int | None, unite: str) -> str:
        """« 8 pages / 8 », ou « 8 pages » quand l'attendu n'existe pas."""
        if attendu is None:
            return f"{trouve} {unite}"
        return f"{trouve} {unite} / {attendu}"

    def _sous_lignes(self, lot, table, largeur: int) -> list[str]:
        """Ce qui manque **sous** le lot : planches absentes, QR muets.

        Les deux manques ne sont pas le meme et n'ont pas la meme reparation
        (`EPIC11-ARB-29`, AC 6.7) : une planche absente n'a jamais ete scannee,
        une planche muette est sur la vitre et son identite est inconnue. Les
        rendre sur deux lignes distinctes est la moitie visible de cette
        distinction ; l'autre moitie est que seule la seconde ouvre `E3-4b`.
        """
        rattachement = table["rattachement"]
        lignes = []
        for page in lot.planches_manquantes:
            lignes.append(jetons.ajuster(
                f"  {rattachement} page {page} manquante", largeur,
                self.app.ascii_seul))
        for muette in lot.pages_muettes:
            motif = f"   {muette.code}" if muette.code else ""
            lignes.append(jetons.ajuster(
                f"  {rattachement} {muette.fichier}{motif}", largeur,
                self.app.ascii_seul))
        return lignes

    def lignes_du_panneau(self) -> list[str]:
        """Le contenu du cartouche : **les lots, et rien d'autre**.

        La classe de base rend ici un `Panneau` de `LigneChiffree` -- un
        libelle a gauche, un chiffre a droite. Une ligne de lot en porte
        **quatre** colonnes, ce que ce motif ne sait pas dire ; on redefinit
        donc la methode plutot que de deformer `LigneChiffree`.
        """
        return self.lignes_des_lots()

    def lignes_de_la_file(self) -> list[str]:
        """La file « en attente de lecture » : son en-tete, **puis ses fichiers**.

        `E3-4` ne montre que l'en-tete chiffre (« ✕  1 fichier non rattaché »),
        et l'AC 6.1 exige davantage : « la file en attente de lecture, **nommee
        fichier par fichier**, jamais reduite a un compte ». Les deux tiennent
        ensemble -- l'en-tete porte la mesure, les lignes suivantes portent les
        noms et le motif lu du vocabulaire ferme du coeur. Un ecart de plus
        entre la maquette et le produit, et il va dans le sens de l'AC.

        Le detail vient de `RapportDeDetection.lignes_en_attente`, du lot D : le
        recomposer ici en ferait une seconde redaction.
        """
        table = self.app.glyphes
        attente = self.rapport.en_attente
        if not attente:
            return [f"   {LIBELLE_EN_ATTENTE}   {table['complete']}  "
                    f"{self.rapport.lignes_en_attente()[0]}"]
        mesure = _accorder(len(attente), "fichier non rattaché",
                           "fichiers non rattachés")
        lignes = [f"   {LIBELLE_EN_ATTENTE}   {table['absent']}  {mesure}"]
        nommees = [f"      {ligne}"
                   for ligne in self.rapport.lignes_en_attente()]
        place = max(self.budget_du_corps() - len(self.lignes_des_lots()), 1)
        if len(nommees) + 1 <= place:
            return lignes + nommees
        if place <= 2:
            # **L'en-tete seul, et rien n'est tu pour autant** : il porte deja
            # le compte des fichiers en attente. Ajouter une ligne « … et N
            # autres » ici deborderait la grille d'une ligne -- mesure du
            # 2026-08-31 sur dix lots et un reliquat de trois : dix-huit lignes
            # pour dix-sept -- et elle ne dirait rien que l'en-tete ne dise.
            return lignes
        gardees = place - 2
        return lignes + nommees[:gardees] + [
            "      " + PHRASE_RESTE_A_DIRE.format(
                reste=_accorder(len(nommees) - gardees, "autre fichier",
                                "autres fichiers"))]

    def rendu_des_issues(self) -> list[str]:
        """Les issues **avec leur a-cote**, chacune portant son chiffre reel.

        Le rendu passe par `IssuesDuRapport.lignes`, donc par
        `ChoixExclusif.rendu` : le curseur y est pose une seule fois, et c'est
        lui que `bloc_peint` accentue au rang que la classe de base lui passe.
        """
        return self.suites.lignes(self.app.ascii_seul)

    def etat(self) -> str:
        """La ligne d'etat : **une mesure, jamais une touche** (`EPIC11-ARB-56`).

        Deux redactions, et laquelle s'affiche se lit sur le rapport :

        * rapport complet -- le **chemin du document de detection** ecrit. C'est
          la mesure qui compte ici : elle est ce qui rend le temps 1 reprenable
          sans redetecter (AC 5.3) ;
        * rapport incomplet -- **ce qui manque, chiffre** : combien de lots,
          puis les pages et les frames des lots incomplets. Les deux dernieres
          mesures sont omises quand l'attendu manque.
        """
        if self.rapport.complet:
            if not self.document:
                return jetons.marque("substitute", PHRASE_AUCUN_DOCUMENT,
                                     self.app.ascii_seul)
            return jetons.marque("complete", PHRASE_DOCUMENT_ECRIT.format(
                chemin=self.document), self.app.ascii_seul)
        return jetons.marque("substitute", self.mesure_du_manque(),
                             self.app.ascii_seul)

    def mesure_du_manque(self) -> str:
        """`1 lot sur 2 est incomplet · 3 pages sur 4 · 46 frames sur 62`.

        **Les trois mesures se somment sur les lots incomplets**, et c'est une
        boucle : un banc la mesure donc avec trois lots dont l'incomplet est au
        MILIEU (`CLAUDE.md`, point 2 bis).
        """
        incomplets = self.rapport.lots_incomplets
        parts = [PHRASE_LOTS_INCOMPLETS.format(
            lots=_accorder(len(incomplets), "lot", "lots"),
            total=len(self.rapport.lots),
            verbe="est" if len(incomplets) <= 1 else "sont",
            s="" if len(incomplets) <= 1 else "s")]
        pages = self._somme(incomplets, "pages_trouvees", "pages_attendues")
        if pages is not None:
            parts.append(PHRASE_PAGES_DU_MANQUE.format(
                trouvees=pages[0], attendues=pages[1]))
        frames = self._somme(incomplets, "frames", "frames_attendues")
        if frames is not None:
            parts.append(PHRASE_FRAMES_DU_MANQUE.format(
                trouvees=frames[0], attendues=frames[1]))
        return SEPARATEUR_DE_MESURE.join(parts)

    @staticmethod
    def _somme(lots, champ_trouve: str, champ_attendu: str):
        """Les deux totaux, ou `None` des qu'un seul attendu manque.

        **`None` des qu'UN seul manque**, et non « on somme ce qu'on a » : un
        total partiel se lirait comme un total, et c'est precisement la valeur
        devinee que `DESIGN.md` section 3 interdit.
        """
        attendus = [getattr(lot, champ_attendu) for lot in lots]
        if not attendus or any(valeur is None for valeur in attendus):
            return None
        return (sum(getattr(lot, champ_trouve) for lot in lots), sum(attendus))

    # -- rendu ---------------------------------------------------------------

    def contenu(self):
        """La composition de `E3-3` : phrase, cartouche, file, issues.

        Elle **etend** celle de la classe de base au lieu de la refaire : le
        cartouche, le bloc de refus et le bloc d'issues restent ceux qu'elle
        monte, et `rafraichir` continue donc de les alimenter.
        """
        from textual.widgets import Static

        herites = super().contenu()
        self._ouverture = Static("", id="ouverture-du-rapport")
        self._file = Static("", id="file-du-rapport")
        return ([self._ouverture, Static("")] + herites[:1]
                + [Static(""), self._file] + herites[1:])

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        utile = jetons.largeur_utile(self.app.size.width)
        self._ouverture.update(bloc_peint(
            ["   " + TITRE_DU_RAPPORT], utile, self.app))
        self._file.update(bloc_peint(self.lignes_de_la_file(), utile,
                                     self.app))
        super().rafraichir()


# ---------------------------------------------------------------------------
# Le parcours : ce qui mene d'un ecran au suivant
# ---------------------------------------------------------------------------


def documents_relus(chemins) -> tuple[tuple[Path, dict, Any], ...]:
    """Relire les documents ecrits par la passe : chemin, JSON brut, objet.

    **Le lecteur est celui du coeur** (`scan_previz.scan_previz_from_json_dict`)
    et non `gui.chargeur_detections` : le paquet `tui/` n'a pas le droit de
    l'importer (`test_frontiere_gui_tui.py` en fait une egalite sur deux modules
    nommes), et une seconde redaction du lecteur normatif divergerait de la
    premiere au premier champ ajoute.

    Le **JSON brut est garde a cote de l'objet**, et ce n'est pas une
    redondance : `poser_la_correction` prend le document sous sa forme
    normative -- un dictionnaire --, la projection prend l'objet. Reserialiser
    l'objet pour ecrire ferait passer le document par un aller-retour que
    personne n'a demande.

    Un document illisible est **saute**, pas fatal : les autres lots du meme
    vrac restent montrables, et l'ecran dira ce qui manque plutot que de
    tomber.
    """
    relus = []
    for chemin in chemins:
        chemin = Path(chemin)
        try:
            brut = json.loads(chemin.read_text(encoding="utf-8"))
            relus.append((chemin, brut,
                          scan_previz.scan_previz_from_json_dict(brut)))
        except (OSError, ValueError, scan_previz.ScanPrevizError):
            continue
    return tuple(relus)


# ---------------------------------------------------------------------------
# Le point dur du cablage : une question POSEE PAR LE COEUR, a laquelle un
# ecran repond -- et le coeur attend la reponse dans la meme pile d'appel.
# ---------------------------------------------------------------------------


class QuestionDeCollision:
    """Poser la collision de profil a l'operateur **sans rejouer la passe**.

    **Le probleme, tel que le lot G l'a mesure et laisse au cablage.**
    `io.calibration_profile.write_profile` appelle `confirm_overwrite` **depuis
    l'interieur** de l'ecriture, et `CoqueTui.executer_en_processus` est un
    appel direct (`EPIC11-ARB-1` : « le coeur est heberge, pas relance »). Le
    relais doit donc rendre un booleen **dans la meme pile d'appel** que la
    question, alors que la reponse vient d'un `ChoixExclusif`, c'est-a-dire de
    la boucle d'evenements de `textual`.

    **Les deux issues qui n'en sont pas**, dites pour qu'on ne les repaie pas :

    * *repondre a la place de l'operateur* -- c'est l'ecrasement silencieux
      qu'`EPIC11-ARB-89` interdit, et le relais du lot G existe justement pour
      ne pas trancher ;
    * *lever, poser la question, puis REJOUER la passe* -- `ingest_scan_lot` a
      **deja ecrit dans le projet** quand la question arrive (le scan est
      ingere avant que le profil ne soit ecrit). Rejouer ferait une seconde
      ingestion du meme scan ; ce n'est pas une question de cout, c'est une
      seconde ecriture que personne n'a demandee.

    **Le mecanisme retenu**, et il tient en deux objets : la passe part dans un
    **fil de travail** (`App.run_worker(thread=True)`), et cette classe fait le
    va-et-vient. :meth:`demander` est appelee **depuis le fil de travail** :
    elle fait monter l'ecran par la boucle (`App.call_from_thread`) puis
    **bloque** sur un :class:`threading.Event`. :meth:`repondre` est appelee
    **depuis la boucle**, quand l'operateur valide une issue : elle pose la
    reponse et libere le fil. La boucle n'est jamais bloquee -- c'est le fil de
    travail qui attend --, donc l'interface reste vivante et l'ecran de
    collision est navigable pendant ce temps.

    **La premiere reponse gagne, et c'est ce qui ferme l'interblocage.** `Échap`
    depile l'ecran de collision sans passer par une issue -- `EcranDeJugement`
    ne traite pas cette touche, l'application la traite pour lui. Sans reponse,
    le fil de travail attendrait indefiniment et la passe ne finirait jamais.
    L'ecran repond donc `annuler` a son demontage
    (:class:`EcranCollisionDuScan`), et l'idempotence fait que cette reponse-la
    n'ecrase jamais celle qu'une issue vient de poser.

    **Le defaut de depart n'ecrase rien** : c'est `annuler`, l'issue qui
    n'ecrit pas. Un defaut a « ecraser » ferait d'une panne de cablage une
    destruction.
    """

    def __init__(self,
                 poser: Callable[[Any, Callable[[str], None]], None]) -> None:
        self._poser = poser
        self._reponse = atelier_scan_calibrate.CLE_ANNULER
        self._repondu = threading.Event()

    @property
    def reponse(self) -> str:
        """La cle retenue. Mesurable de l'exterieur, comme tout le reste."""
        return self._reponse

    def demander(self, collision) -> str:
        """Appelee **depuis le fil de travail** : monte l'ecran, puis attend.

        Elle rend la cle d'issue que `RelaisDeCollision` traduit en booleen (ou
        en `CalibrationAnnulee`) par sa propre table -- la traduction n'est pas
        refaite ici, et c'est ce qui fait qu'aucune regle de collision ne vit de
        ce cote (AC 8.2).
        """
        self._reponse = atelier_scan_calibrate.CLE_ANNULER
        self._repondu.clear()
        self._poser(collision, self.repondre)
        self._repondu.wait()
        return self._reponse

    def repondre(self, cle: str) -> None:
        """Appelee **depuis la boucle** : pose la reponse et libere le fil.

        Idempotente : la premiere reponse gagne. Voir le docstring de classe --
        c'est ce qui rend le filet du demontage inoffensif quand une issue a
        deja tranche.
        """
        if self._repondu.is_set():
            return
        self._reponse = cle
        self._repondu.set()


class EcranCollisionDuScan(atelier_scan_calibrate.EcranCollisionDeProfil):
    """L'ecran de collision du lot G, **plus le filet de son demontage**.

    Une sous-classe et rien d'autre : les trois issues, leur rendu, leur ligne
    d'etat et l'invariant « aucune preselectionnee » sont ceux du lot G, et
    `atelier_scan_calibrate.py` n'est pas modifie.

    Ce qu'elle ajoute est le **seul chemin de sortie que le clavier offre sans
    passer par une issue** : `Échap`. `EcranDeJugement.traiter` ne le traite
    pas, donc `CoqueTui.action_remonter` depile l'ecran -- et le fil de travail
    qui attend la reponse attendrait alors pour toujours. Le demontage repond
    donc `annuler`, l'issue qui n'ecrase rien : sortir sans choisir ne peut
    signifier que « n'ecris pas ».
    """

    def __init__(self, collision, *, retenir: Callable[[Any], None],
                 abandonner: Callable[[], None]) -> None:
        super().__init__(collision, retenir=retenir)
        self._abandonner = abandonner

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """`Échap` **se depile lui-meme**, au lieu de le demander a la coque.

        Rien ne change pour l'operateur : l'ecran disparait, `on_unmount`
        repond `annuler`, et le fil de travail repart -- exactement ce que
        mesure `test_ECHAP_sur_la_collision_repond_ANNULER_et_ne_BLOQUE_personne`.

        Ce qui change est **d'ou vient le depilement**. Depuis la fermeture du
        finding `Echap pendant la calibration`, la passe pose
        `app.tache_en_cours`, et `CoqueTui.action_remonter` cesse alors de
        depiler : elle pose `interruption_demandee` et rend. Le filet du
        demontage ne se serait donc plus jamais declenche, et le fil de travail
        aurait attendu pour toujours -- la panne exacte que ce filet existe pour
        ecarter. Le depilement est pose **ici**, ou la reponse `annuler` a un
        sens, plutot que retire au drapeau qui protege le reste de la passe.
        """
        if touche == "escape":
            self.app.pop_screen()
            return True
        return super().traiter(touche, caractere)

    def on_unmount(self) -> None:
        self._abandonner()


class EcranChaineDejaCalibreeDuScan(
        atelier_scan_calibrate.EcranChaineDejaCalibree):
    """L'ecran d'`EPIC11-ARB-261`, **plus la sortie par `Échap`**.

    Une sous-classe et rien d'autre, exactement comme
    :class:`EcranCollisionDuScan` : les deux issues, leur rendu, leur ligne
    d'etat et l'invariant « aucune preselectionnee » sont ceux du lot de
    vocabulaire, et `atelier_scan_calibrate.py` porte la regle une seule fois.

    Ce qu'elle ajoute est la continuation : `Échap` depile cet ecran, et rien
    ne monterait derriere -- l'operateur retomberait sur `E3-9` sans jamais
    voir le resultat de la passe qu'il vient de lancer, c'est-a-dire le
    court-circuit exact que l'ecran de resultat a ete ecrit pour fermer.
    `on_unmount` declenche donc la meme continuation que les deux issues, et
    elle est gardee de son cote pour ne pas monter deux fois.

    **Pas de filet de reponse a un fil**, a la difference de la collision : la
    passe est finie quand cet ecran monte. Il n'y a personne a debloquer, il y
    a un ecran a montrer.
    """

    def __init__(self, passe, autres, *, retenir: Callable[[Any], None],
                 poursuivre: Callable[..., None]) -> None:
        super().__init__(passe, autres, retenir=retenir)
        self._poursuivre = poursuivre

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """`Échap` se depile **lui-meme**, comme sur la collision.

        `CoqueTui.action_remonter` est gardee par `tache_en_cours` ; le drapeau
        est tombe ici, donc elle depilerait -- mais le geste appartient au
        parcours, et le poser ici garde les deux ecrans de jugement de cet
        atelier sur la meme regle.
        """
        if touche == "escape":
            self.app.pop_screen()
            return True
        return super().traiter(touche, caractere)

    def on_unmount(self) -> None:
        self._poursuivre()


def _payload_du_lot(brut: Any, lot_id: str):
    """Le payload d'une page **de ce lot-la**, ou `None`.

    L'appariement se fait **par `lot_id`**, jamais par rang : « le premier
    payload du document » designerait le mauvais lot des qu'un vrac en porte
    deux, ce qui est litteralement le risque `R12` et le mutant `M25` de la
    story 5.7.

    `None` est un regime nominal et non un manque : une pile de calibration
    seule ne porte aucun payload de lot, et
    `atelier_scan_ecriture.LotAEcrire.dossier` accepte `None` pour dire « je ne
    sais pas ou ce lot ecrit ».
    """
    for page in (brut or {}).get("pages", ()) or ():
        payload = page.get("payload") or {}
        if payload.get("lot_id") == lot_id:
            return payload
    return None


def nom_de_la_calibration(retenue) -> str | None:
    """Sous quel nom `E3-6` annonce la calibration retenue en `E3-5`.

    `None` veut dire « aucune » : la ligne du cartouche dit alors « lot livre
    brut » (`atelier_scan_confirmation.CALIBRATION_AUCUNE`), et c'est un fait
    sur ce qui sera ecrit, jamais un manque.

    Le nom d'une entree du registre est celui de `palier_projet.nom_du_profil`
    -- **la redaction unique** de « sous quel nom un profil s'affiche », deja
    employee par le pied du palier Projet, par celui du menu du Scan et par
    `E3-5`. Une quatrieme divergerait, et l'ecart ne se verrait que sur un
    profil ayant perdu sa provenance.

    Un fichier designe a l'explorateur n'a **pas** d'entree de registre : il
    s'annonce par son nom de fichier, qui est ce que l'operateur vient de
    choisir a l'ecran.
    """
    if retenue is None or retenue.livrer_brut:
        return None
    if retenue.entree:
        return nom_du_profil(retenue.entree)
    if retenue.profil_designe is not None:
        return Path(retenue.profil_designe).name
    return None


class ParcoursScan:
    """Les cinq ecrans de l'atelier Scan, temps 1, cables les uns aux autres.

    Meme forme que `ParcoursExtraction`, et pour le meme motif : chaque rappel
    a besoin de ce que le precedent a produit -- la source designee, le rapport
    de la passe, les corrections deja posees --, et les methodes liees le
    portent sans rendre l'etat implicite.

    **Ce parcours n'ecrit aucune frame** : c'est l'invariant qui rend la story
    ouvrable, et il se lit ici a ce qu'aucune methode n'appelle `scan_write`.
    La seule ecriture est celle du document de detection corrige.
    """

    def __init__(self, app, dossier_projet, *,
                 detection: Callable[..., Any] | None = None,
                 ecriture: Callable[..., Any] | None = None,
                 calibration: Callable[..., Any] | None = None,
                 mesurer: Callable[..., Any] | None = None,
                 logger: Any = None) -> None:
        self.app = app
        self.dossier_projet = Path(dossier_projet)
        self._mesurer = mesurer
        # **Jamais `None`** : le coeur declare `logger` obligatoire et le
        # dereference sans garde. C'est ici, et pas au point d'appel, que le
        # produit s'en dote -- c'est le finding `I0`, et il faisait tomber
        # TOUTE extraction lancee depuis `mmu-tui`.
        if logger is None:
            self._logger, self._relais = journal_du_produit()
        else:
            self._logger, self._relais = logger, None
        #: Le logger que l'appelant a impose, ou `None`. Retenu tel quel : le
        #: temps 2 a **son** journal (un nom de logger par passe, sans quoi les
        #: lignes d'une detection tombent dans le journal d'une ecriture), et il
        #: ne se construit que si personne n'en a donne.
        self._logger_injecte = logger
        #: Le couple `(logger, relais)` de la passe d'ecriture, construit au
        #: premier besoin. Une seule construction par parcours : `getLogger` est
        #: un singleton par nom, et deux relais empiles inscriraient chaque
        #: ligne du coeur deux fois.
        self._journal_ecriture: tuple | None = None
        #: Le double de banc de `run_scan_detect`, quand un banc en pose un.
        #: `None` veut dire « le vrai point d'entree du coeur », et c'est le
        #: regime du produit.
        self._detection = detection
        #: Ce que la derniere passe a rendu. Pose par :meth:`conclure`.
        self.rapport: RapportDeDetection | None = None
        #: Les documents relus de la passe : chemin, JSON brut, objet.
        self.documents: tuple = ()
        #: Le chemin du document a montrer en ligne d'etat de `E3-3`.
        self.document: str | None = None
        #: La partition du tri de la derniere passe, ou `None` en regime
        #: `--lot-slug`, ou il n'y a pas de tri et donc pas de reliquat.
        self.partition: Any = None
        #: La derniere demande transmise au coeur. Retenue parce que l'adoption
        #: RELANCE la passe (`EPIC11-ARB-267`) et qu'une relance a besoin de la
        #: source, du dpi et du slug d'origine -- les recomposer ici ferait une
        #: seconde construction de la demande, qui divergerait de la premiere.
        self._demande: DemandeDeDetection | None = None
        #: Les `read_rank` deja completes pendant cette passe. Ils ne sortent
        #: pas du rapport -- le rapport se **recalcule**, il ne se rapiece pas
        #: (`EPIC11-ARB-101`, note 10) -- mais ils disent quelle planche
        #: proposer ensuite.
        self.posees: list[int] = []

        # -- l'etat du TEMPS 2 (story 11.6, lot H) --------------------------
        #: Les doubles de banc des deux autres points d'entree du coeur. Meme
        #: forme et meme motif que `detection` : leur defaut est le **vrai**
        #: point d'entree (`scan_write.ecrire_depuis_le_document`,
        #: `scan_calibrate.calibrer_la_chaine`), c'est le double qui est
        #: l'exception.
        self._ecriture = ecriture
        self._calibration = calibration
        #: Le dpi **declare au depot** (`E3-1`), tel quel. `E3-5` le confronte
        #: a celui du profil retenu et le **dit** quand les deux divergent ; il
        #: n'est jamais substitue (`EPIC11-ARB-38`).
        self.dpi: int | None = None
        #: Ce que `E3-5` a retenu -- une `CalibrationRetenue`, ou `None` tant
        #: que l'ecran n'a pas ete franchi.
        self.calibration_retenue: Any = None
        #: L'ecran de confirmation monte, dont `ecrire` lit les noms.
        self.confirmation: Any = None
        #: L'ecran de calibration de chaine monte, a qui la passe s'annonce.
        self.ecran_de_calibration: Any = None
        #: L'ecran d'execution de la passe **en cours**, ou `None` hors
        #: passe -- `consigner_le_profil` le pose avant de lancer le fil et
        #: `conclure_la_passe` le remet a `None` apres l'avoir depile.
        #:
        #: **Corrige le 2026-09-05 : ce commentaire disait l'inverse du code.**
        #: Il annoncait « `None` tant qu'aucun jalon n'est arrive. C'est ce
        #: `None` qui tient l'AC 9.6 ». C'etait vrai du montage TARDIF, que
        #: `EPIC11-ARB-160` a retire le 2026-09-02 au profit d'un montage
        #: **avant le fil** ; le commentaire n'a pas suivi. Ce que l'AC 9.6
        #: tient reellement est son MOTIF, et il est tenu ailleurs : aucun
        #: chiffre n'est invente (`test_un_refus_avant_la_detection_ne_PROMET_
        #: aucun_chiffre`) et l'ecran est depile avant le refus
        #: (`test_un_refus_avant_la_detection_mene_DIRECTEMENT_au_refus`). Sa
        #: lettre n'est pas tenue, et c'est au registre.
        self.ecran_de_passe: Any = None
        #: La `SurfaceExecution` de la derniere passe de calibration, ou
        #: `None`. **Retenue a part de l'ecran**, qui est demonte et oublie par
        #: `conclure_la_passe` : l'objet `Journal` qu'elle porte, lui, survit a
        #: son ecran et c'est ce que l'ecran de resultat annonce sous
        #: `Tab journal`. Sans cette reference, la seule facon de le retrouver
        #: serait de garder l'ecran monte -- c'est-a-dire de ne pas conclure.
        self._surface_de_la_passe: Any = None

    # -- etape 1 : le menu des ateliers -> `E3-0` -----------------------------

    def ouvrir(self) -> EcranScanMenu:
        """`E3-0`, le menu de l'atelier. **Il y en a un, et c'est une regle.**

        `EPIC11-ARB-28`, verbatim : « **Tout atelier qui a plus d'une entree
        commence par un menu d'atelier** ». Le Scan en a deux, l'Extraction une
        seule -- c'est pourquoi l'Extraction monte `E2-1` directement et le
        Scan passe par ici.
        """
        ecran = EcranScanMenu(self.dossier_projet, entrer=self.entrer)
        self.app.descendre(ecran)
        return ecran

    def entrer(self, entree) -> None:
        """`⏎` sur une entree **construite** du menu. **Les deux menent.**

        Depuis le lot H de la story 11.6, les deux entrees du menu sont
        construites : « Detecter des planches » ouvre le depot, « Calibrer une
        chaine » ouvre `E3-9`. La seconde menait jusqu'ici a `EcranPasEncore`,
        ce qui etait la forme honnete d'une absence -- et ne l'est plus, l'ecran
        etant livre.

        Une entree inconnue reste une **erreur de cablage** plutot qu'un etat du
        produit, et elle mene quand meme quelque part : l'ecran qui nomme
        l'absence, avec l'echeance que l'entree porte (`EntreeDeMenu.quand`).
        """
        if entree.cle == CLE_DE_LA_DETECTION:
            self.deposer()
            return
        if entree.cle == atelier_scan_calibration.CLE_DE_LA_CALIBRATION:
            self.calibrer_la_chaine()
            return
        self.app.descendre(EcranPasEncore(entree.nom,
                                          getattr(entree, "quand", "")))

    # -- etape 2 : `E3-1` -> la passe ----------------------------------------

    def deposer(self) -> EcranScanDepot:
        """`E3-1` / `E3-1b`, le depot. Le champ part **vide** a chaque montage.

        C'est ce que « Reprendre avec d'autres fichiers » promet -- « retour au
        depot, le champ vide » -- et c'est obtenu en montant un ecran neuf
        plutot qu'en vidant l'ancien : un formulaire remis a zero garde son
        explorateur ouvert la ou l'operateur l'avait laisse.
        """
        ecran = EcranScanDepot(self.dossier_projet, detecter=self.detecter,
                               mesurer=self._mesurer)
        self.app.descendre(ecran)
        return ecran

    def detecter(self, source, dpi: int):
        """`E3-2` : monter l'ecran d'execution, **puis** appeler le coeur.

        L'ordre n'est pas cosmetique -- `ouvrir_la_detection` le documente :
        appeler le coeur d'abord ferait ecrire les jalons dans une surface que
        personne n'ecoute encore.

        `source` est passee **telle quelle** (`EPIC7-ARB-88`) : c'est
        l'ingestion qui distingue les quatre formes, et elle seule.

        Le dpi **declare** est retenu ici, et pour un seul usage : `E3-5` le
        confronte a celui du profil retenu et **dit** quand les deux divergent
        (AC 3.7). Il n'est jamais substitue a une mesure (`EPIC11-ARB-38`), et
        il n'entre dans aucun calcul du temps 2 -- les deux dpi de l'ecriture
        sont lus **dans le document** par le coeur.
        """
        self.dpi = dpi
        ecran = ouvrir_la_detection(self.app)
        # Meme branchement, meme relais, meme motif : les deux passes qui
        # recoivent `self._logger` sont la detection et la calibration, et
        # aucune des deux ne le visait. `E3-2` montrait donc une barre qui
        # avance au-dessus d'un journal vide, alors que le coeur y raconte la
        # qualification de la source et le compte de pages lues.
        if self._relais is not None:
            self._relais.viser(ecran.surface.journal)
        demande = DemandeDeDetection(dossier_projet=self.dossier_projet,
                                     source=source, dpi=dpi)
        self._demande = demande
        reglages = {} if self._detection is None else {
            "detection": self._detection}
        # **Au FIL, et non plus synchroniquement** (2026-09-06). L'ordre que le
        # docstring ci-dessus defend -- monter d'abord, appeler ensuite -- etait
        # respecte a la lettre et ne suffisait pas : `descendre` EMPILE, il ne
        # dessine pas. Le dessin est un evenement de la boucle, et l'appel
        # synchrone qui suivait la gardait du premier au dernier jalon. Mesure :
        # zero image ecrite au pilote, `on_mount` jamais joue, et les touches
        # frappees pendant la passe delivrees a l'ecran SUIVANT.
        #
        # `lancer_la_detection` ne rend PAS de rapport : il n'existe pas encore
        # quand cette methode rend la main -- il arrivera par `sur_rapport`.
        # C'est ce qui change pour un appelant, et c'est le prix de l'ecran
        # vivant. (Elle rendait un `Worker` entre le matin et le soir du
        # 2026-09-06 ; depuis que le fil part APRES le dessin, le worker
        # n'existe pas non plus a cet instant.)
        return lancer_la_detection(self.app, ecran, demande,
                                   logger=self._logger,
                                   sur_rapport=self.conclure, **reglages)

    # -- etape 3 : le rapport ------------------------------------------------

    def conclure(self, passe) -> None:
        """Relire ce que la passe a ecrit, puis montrer `E3-3` ou `E3-4`.

        **La partition est reposee a chaque passe, y compris quand elle est
        absente** : la garder d'une passe sur l'autre ferait montrer le reliquat
        du scan precedent a cote des lots du scan courant, et les deux regimes
        du coeur -- vrac trie, `--lot-slug` sans tri -- alternent librement dans
        une meme session.
        """
        self.documents = documents_relus(passe.documents)
        self.document = str(passe.documents[0]) if passe.documents else None
        self.posees = []
        self.partition = getattr(passe.issue, "partition", None)
        if self.proposer_l_adoption() is not None:
            return
        self.montrer_le_rapport()

    # -- etape 3 bis : `EPIC11-ARB-267`, l'adoption se DEMANDE ---------------

    def proposer_l_adoption(self) -> "EcranAdoptionDeLaPlanche | None":
        """Monter le point de jugement de l'adoption, ou `None` s'il n'y a rien
        a demander.

        **Ici et pas dans `montrer_le_rapport`**, et c'est ce qui donne la
        regle « une seule question » d'`EPIC7-ARB-106` sans compteur ni
        drapeau : `conclure` joue UNE fois par passe, la ou
        `montrer_le_rapport` se rejoue a chaque retour de `E3-4b`. Poser la
        question la-bas la reposerait a chaque aller-retour de completion.

        **La seconde borne est explicite plutot que deduite** : une demande qui
        porte deja `adopter=True` ne redemande rien. Le coeur ayant substitue
        l'identite, la passe relancee ne rend en principe plus aucune page hors
        perimetre -- mais « en principe » n'est pas une borne, et une adoption
        partielle rouvrirait l'ecran sur lui-meme. Une boucle de points de
        jugement est exactement ce qu'un operateur ne peut pas quitter.
        """
        if self._demande is None or self._demande.adopter:
            return None
        etrangeres = planches_etrangeres_de(self.partition)
        if etrangeres is None:
            return None
        ecran = EcranAdoptionDeLaPlanche(etrangeres, retenir=self.adopter)
        self.app.descendre(ecran)
        return ecran

    def adopter(self, issue) -> None:
        """Les deux issues de l'adoption. **Les deux menent quelque part.**

        L'adoption **relance la passe entiere** avec le drapeau pose : ecran
        d'execution neuf, meme source, meme dpi, meme journal. C'est ce
        qu'`EPIC7-ARB-106` demande -- « un Oui relance la detection tout
        seul » -- et c'est aussi ce qui fait de l'issue une ecriture reelle
        plutot qu'une decoration ; le finding `K3`, paye quatre fois dans cet
        epic, est exactement l'issue navigable qui n'appelle personne.

        L'issue qui n'adopte pas montre le rapport -- elle ne revient pas au
        menu : la passe a REUSSI, et les lots que la meme pile a produits
        existent. Les perdre pour une question a laquelle on repond « non »
        serait le refus d'aujourd'hui sous un autre nom.

        **La relance vit ICI et non dans le module de l'ecran**, et ce n'est
        pas un rangement : la frontiere `C3` de
        `test_journal_du_scan_atteint_la_tui.py` exige que la methode qui
        donne `self._logger` au coeur soit AUSSI celle qui rebranche le
        relais. L'ecran d'execution neuf porte une surface neuve ; un relais
        reste vise sur l'ancienne ecrirait les jalons de la relance dans un
        journal que plus personne n'affiche -- le motif `K3` exactement, sous
        sa forme « barre qui avance au-dessus d'un journal vide ». Ecrire la
        relance dans `atelier_scan_detection.py`, comme le fait
        `trancher_le_conflit`, mettrait le `viser` hors de portee de cette
        mesure.

        **La reprise est bornee, et ce n'est pas une esperance** : la demande
        relancee porte `adopter=True`, le coeur substitue alors l'identite du
        projet courant, et `planches_etrangeres_de` ne trouve plus rien a la
        passe suivante. `proposer_l_adoption` relit ce champ, si bien que
        l'ecran ne peut pas se remonter lui-meme meme sur une adoption
        partielle.
        """
        if issue.cle != ISSUE_ADOPTER:
            self.montrer_le_rapport()
            return
        # Le `replace` vit ICI et nulle part ailleurs : le recomposer ferait
        # une seconde construction de la meme demande, qui divergerait de la
        # premiere au premier champ ajoute. Et retenir la demande adoptee est
        # ce qui BORNE la reprise -- sans cette ligne, `proposer_l_adoption`
        # relirait la demande d'ORIGINE, qui porte `adopter=False`, et l'ecran
        # se remonterait sur lui-meme.
        demande = replace(self._demande, adopter=True)
        self._demande = demande
        ecran = ouvrir_la_detection(self.app)
        if self._relais is not None:
            self._relais.viser(ecran.surface.journal)
        reglages = {} if self._detection is None else {
            "detection": self._detection}
        # **Au FIL, comme la passe d'origine** : relancer synchroniquement
        # rejouerait le gel, et sur le chemin dont l'ecran d'arrivee porte
        # l'issue qui ecrit.
        lancer_la_detection(self.app, ecran, demande, logger=self._logger,
                            sur_rapport=self.conclure, **reglages)

    def montrer_le_rapport(self) -> EcranRapportDeDetection:
        """Projeter les documents **relus** puis monter l'ecran du rapport.

        La projection se refait a chaque retour de `E3-4b` : « le rapport se
        recalcule, il ne se rapiece pas » (`EPIC11-ARB-101`, note 10).
        Retrancher une page de la liste des completables ecrirait une seconde
        regle de completude a cote de `scan_detect.completude_des_planches`, et
        les deux divergeraient au premier lot dont il manque une planche jamais
        scannee -- qu'aucune saisie ne rattrape.
        """
        self.rapport = projeter(
            [objet for _chemin, _brut, objet in self.documents],
            partition=self.partition,
            manifeste=projet_lecture.lire_manifeste(self.dossier_projet))
        ecran = EcranRapportDeDetection(self.rapport, sur_issue=self.juger,
                                        document=self.document)
        self.app.descendre(ecran)
        return ecran

    def juger(self, issue) -> None:
        """Les quatre issues du rapport, **et chacune mene quelque part**.

        « Ecrire les frames » ouvre le temps 2 par son premier ecran, `E3-5` :
        elle menait a `EcranPasEncore` tant que le temps 2 n'existait pas, et
        c'est le lot H de la story 11.6 qui tient la promesse. **Elle n'ecrit
        toujours rien ici** : `E3-5` puis `E3-6` sont deux ecrans de jugement,
        et rien n'est ecrit avant que la seule issue qui ecrit de `E3-6` n'ait
        ete validee.
        """
        if issue.cle == ISSUE_ECRIRE:
            self.choisir_la_calibration()
            return
        if issue.cle == ISSUE_COMPLETER:
            self.completer()
            return
        if issue.cle == ISSUE_REPRENDRE:
            self.deposer()
            return
        if issue.cle == ISSUE_ANNULER:
            self.app.revenir_aux_ateliers()

    # -- etape 4 : `E3-4b`, une planche a la fois ----------------------------

    def completer(self) -> Palier | None:
        """Ouvrir `E3-4b` sur la **prochaine** planche muette, ou revenir.

        `page_suivante_a_completer` ne repond qu'a une question -- « y a-t-il
        une page suivante ? » --, et l'ordre qu'elle suit est celui du rapport :
        le refaire ici donnerait a l'operateur un enchainement different de
        celui que le rapport lui a montre.
        """
        page = page_suivante_a_completer(self.rapport.pages_completables,
                                         self.posees)
        if page is None:
            return self.montrer_le_rapport()
        ecran = EcranCompletionQr(
            page, projet_lecture.lire_manifeste(self.dossier_projet) or {},
            poser=self.poser,
            pages_lues=self._pages_lues(page),
            chemin_du_scan=self.dossier_projet / page.fichier)
        self.app.descendre(ecran)
        return ecran

    def _pages_lues(self, page: PageMuette):
        """Les planches deja lues du **meme lot**, pour la coherence (AC 7.4).

        Vide quand la planche est au reliquat : personne ne la reclame, donc il
        n'y a aucune soeur a confronter. C'est un regime nominal -- la pile
        d'une seule planche muette --, pas un manque.
        """
        if page.lot_id is None:
            return ()
        return pages_lues_du_lot(
            [objet for _chemin, _brut, objet in self.documents], page.lot_id)

    def poser(self, identite) -> None:
        """Ecrire la correction dans **le seul** document du lot saisi.

        Le document est choisi par le `lot_id` que l'operateur vient de saisir,
        et par rien d'autre : ecrire dans « le premier document de la passe »
        poserait l'identite sur le mauvais lot des qu'un vrac en porte deux --
        c'est litteralement le risque `R12`, et le mutant `M25` de la story 5.7
        est la meme faute au meme endroit.

        Aucun document ne portant ce lot, **rien n'est ecrit** et l'ecran le
        dit : la passe n'a pas produit de document pour ce lot-la, et en
        fabriquer un ici serait ecrire ce que la detection n'a pas trouve.
        """
        cible = self._document_du_lot(identite.lot_id)
        if cible is None:
            # **Rien n'est ecrit, et l'ecran le dit.** Ecrire dans « le premier
            # document de la passe » poserait l'identite sur le mauvais lot, et
            # fabriquer un document ici ecrirait ce que la detection n'a pas
            # trouve. L'annonce passe par le canal d'etat de l'ecran lui-meme :
            # sa ligne d'etat est reecrite au dessin suivant, donc y poser
            # directement le texte le ferait disparaitre aussitot.
            ecran = self.app.screen
            if isinstance(ecran, EcranCompletionQr):
                ecran.annoncer(PHRASE_SANS_DOCUMENT.format(lot=identite.lot_id))
            return
        chemin, brut, _objet = cible
        corrige = ecrire_la_correction(chemin, brut, identite)
        # Le triplet du lot corrige est **remplace**, pas ajoute : la projection
        # suivante doit lire le document tel qu'il vient d'etre ecrit, sans quoi
        # le rapport recalcule montrerait encore la planche qu'on vient de
        # completer.
        self.documents = tuple(
            (chemin, corrige, scan_previz.scan_previz_from_json_dict(corrige))
            if autre[0] == chemin else autre
            for autre in self.documents)
        self.posees.append(identite.read_rank)
        self.completer()

    # -- etape 5 : `E3-5`, quelle calibration appliquer -----------------------

    def choisir_la_calibration(self):
        """`E3-5` -- le profil est **propose**, jamais impose.

        `retenir` est passe sans defaut de l'autre cote (finding `K3`) : cet
        ecran ne peut pas etre monte sans savoir a qui rendre son choix, et
        c'est ce qui rend impossible la panne qui a coute sept composants a cet
        epic -- un ecran livre, teste, et cable nulle part.

        `lots` et `dpi_du_scan` sont deux **mesures de la passe en cours**, pas
        des reglages : le premier dit a quoi le profil retenu s'appliquera, le
        second est le dpi declare au depot, que la carte confronte a celui du
        profil. `None` sur l'un ou l'autre fait **omettre** la ligne concernee,
        jamais afficher `0` ni `--`.
        """
        lots = None if self.rapport is None else len(self.rapport.lots)
        ecran = atelier_scan_calibration.EcranChoixDeCalibration(
            self.dossier_projet, retenir=self.confirmer, lots=lots,
            dpi_du_scan=self.dpi)
        self.app.descendre(ecran)
        return ecran

    # -- etape 6 : `E3-6`, ce qui sera ecrit ---------------------------------

    def confirmer(self, retenue):
        """`E3-6` -- le point de jugement du temps 2. **Rien n'est encore ecrit.**

        Les deux cardinaux de frames viennent du **rapport**, tels quels : les
        rederiver ici ferait deux comptes du meme lot, et l'ecran de
        confirmation contredirait le rapport qui vient de les montrer (AC 4.2).

        La calibration est **donnee** au plan, pas retrouvee : la relire du
        projet serait une seconde lecture de la designation (AC 3.1), et elle
        pourrait rendre autre chose que ce que l'operateur vient de retenir.

        Le comptage du disque l'est aussi (`EPIC11-ARB-133`) : c'est lui qui
        fait apparaitre la quatrieme issue de `E3-6` sur un lot deja ecrit, et
        `E3-6` n'ouvre aucun dossier -- voir :meth:`frames_deja_ecrites`.
        """
        self.calibration_retenue = retenue
        plan = atelier_scan_confirmation.preparer_le_plan(
            self.rapport, [objet for _chemin, _brut, objet in self.documents],
            calibration=nom_de_la_calibration(retenue),
            frames_deja_ecrites=self.frames_deja_ecrites())
        ecran = atelier_scan_confirmation.EcranScanConfirmation(
            plan, sur_issue=self.trancher)
        self.confirmation = ecran
        self.app.descendre(ecran)
        return ecran

    def trancher(self, issue) -> None:
        """Les issues de `E3-6`, **et aucune n'est muette**.

        « Modifier » remonte d'un palier, donc revient sur `E3-5` avec le choix
        de calibration la ou l'operateur l'avait laisse -- c'est la meme forme
        que `ouvrir_le_point_de_jugement(sur_modification=...)` cote Extraction,
        et le comportement qu'un point de jugement doit avoir : on ne refait pas
        le chemin, on revient d'un cran.

        « Annuler » ramene au **menu des ateliers du projet ouvert**
        (`EPIC11-ARB-13`), jamais a l'ecran projet.
        """
        if issue.cle == atelier_scan_confirmation.ISSUE_ECRIRE:
            self.ecrire()
            return
        # **La seconde issue d'`EPIC11-ARB-89`, et son unique point de pose**
        # (`EPIC11-ARB-133`). Elle ne change qu'une chose au chemin nominal :
        # le drapeau que le coeur recevra. Aucun rang n'est resolu ici, aucun
        # `_vN` n'est compose ici -- c'est `io.version_ranks` qui porte la
        # regle, une fois, pour les cinq objets versionnables.
        if issue.cle == atelier_scan_confirmation.ISSUE_NOUVELLE_VERSION:
            self.ecrire(nouvelle_version=True)
            return
        if issue.cle == atelier_scan_confirmation.ISSUE_MODIFIER:
            self.app.action_remonter()
            return
        if issue.cle == atelier_scan_confirmation.ISSUE_ANNULER:
            self.app.revenir_aux_ateliers()

    # -- etape 7 : `E3-7` puis `E3-8` -----------------------------------------

    def frames_deja_ecrites(self) -> dict:
        """`lot_id -> frames deja sur le disque`, pour les lots du rapport.

        **Aucune regle neuve, et c'est le point** (`EPIC11-ARB-133`) : le
        dossier de chaque lot est derive par les deux fonctions du coeur (via
        :meth:`_dossier_du_lot`) et son contenu compte par
        `atelier_scan_ecriture.frames_du_dossier`, qui est deja le comptage de
        disque de `T6-1`. Ce parcours n'ouvre pas un second chemin, ne resout
        aucun rang de version et n'ecrit aucun `_vN`.

        **Toute panne rend zero**, comme `frames_du_dossier` : un lot dont on
        ne sait pas ou il ecrit -- payload absent, page de calibration seule --
        vaut zero, et zero se lit « rien de deja ecrit ». C'est un
        renseignement, il ne vaut pas de faire tomber `E3-6` ; le pire qu'un
        zero de trop puisse faire est de ne pas offrir une issue que le coeur
        offrira de toute facon dans son message de refus.
        """
        comptes: dict = {}
        for lot in self.rapport.lots:
            entree = self._document_du_lot(lot.lot_id)
            if entree is None:
                continue
            _chemin, brut, _objet = entree
            dossier = self._dossier_du_lot(_payload_du_lot(brut, lot.lot_id))
            comptes[lot.lot_id] = atelier_scan_ecriture.frames_du_dossier(
                dossier)
        return comptes

    def plan_d_ecriture(self, confirme, *, nouvelle_version: bool = False):
        """Le plan que `E3-7` execute, derive de celui que `E3-6` a montre.

        **Aucune seconde derivation de chiffre** : `frames` est le cardinal que
        le rapport a projete pour ce lot, c'est-a-dire ce que le **document**
        porte, et c'est exactement le total que le coeur emettra
        (`write_lot_output_frames` : « `total` valant `len(planned)` »).

        > **Ecart assume avec le docstring de `LotAEcrire`**, qui annonce
        > `PanneauDeLot.frames_attendues`. L'attendu vient du **manifest**, pas
        > du document : il vaut `None` des que le manifest ne declare pas le
        > lot, et il diverge du reel sur un lot incomplet -- c'est meme la
        > definition de « incomplet ». Une barre calee dessus n'atteindrait
        > jamais son terme sur le seul regime ou l'operateur la regarde. C'est
        > la meme lecture que l'AC 4.3, qui fait dire a la premiere issue
        > « Ecrire les N frames **obtenues** » : le compte reel, jamais le
        > compte attendu.

        Le dossier de sortie est **derive par les deux fonctions du coeur** (via
        `atelier_scan_ecriture.dossier_de_sortie`), et il ne sert qu'au comptage
        du disque de `T6-1` : l'ecriture, elle, resout le sien au coeur.

        Un lot du rapport dont aucun document ne porte le `lot_id` est **saute**
        et n'arrete pas les suivants : c'est un `continue`, jamais un `break`.
        Le cas ne se rencontre pas en regime nominal -- le rapport est projete
        des memes documents --, et il est mesure pour qu'il ne devienne pas,
        d'un mutant, la disparition silencieuse des lots suivants.
        """
        lots = []
        for lot in confirme.lots:
            entree = self._document_du_lot(lot.lot_id)
            if entree is None:
                continue
            chemin, brut, _objet = entree
            payload = _payload_du_lot(brut, lot.lot_id)
            lots.append(atelier_scan_ecriture.LotAEcrire(
                document=Path(chemin), lot_id=lot.lot_id, frames=lot.frames,
                dossier=self._dossier_du_lot(payload),
                nouvelle_version=nouvelle_version,
                **self._reglages_de_calibration()))
        return atelier_scan_ecriture.PlanDEcriture(
            dossier_projet=self.dossier_projet, lots=tuple(lots),
            # **La ligne d'eau des rangs**, et elle part TOUJOURS -- pas
            # seulement quand `nouvelle_version` est pose. Le coeur la lit pour
            # savoir quels rangs ont deja ete consommes puis retires
            # (`EPIC11-ARB-92`, point 3 : un rang retire ne se rend qu'en
            # queue et sur demande) ; la passer conditionnellement ferait deux
            # regimes de resolution du meme rang selon le chemin d'appel.
            # `lire_manifeste` ne leve jamais et rend `None` sur un projet dont
            # le `project.json` manque -- ce qui vaut « aucune version
            # employee », jamais « projet invalide ».
            manifest_du_projet=projet_lecture.lire_manifeste(
                self.dossier_projet))

    def _dossier_du_lot(self, payload) -> Path | None:
        """Ou ce lot ecrira, ou `None` -- **et un `None` n'arrete jamais rien**.

        Le dossier ne sert qu'au **comptage du disque** de `T6-1` : l'ecriture,
        elle, resout le sien au coeur. C'est un renseignement, et il ne vaut pas
        de faire tomber une passe -- meme raisonnement, meme mot, que
        `atelier_scan_ecriture.frames_du_dossier` (« toute panne de lecture rend
        zero plutot que de lever [...] le compte est un renseignement »).

        `dossier_de_sortie` **refuse nommement** un payload qui ne designe aucun
        lot (`rush_id`, `fps_target` ou `lot_id` absent) : c'est le cas d'une
        page de calibration par contrat, et le refus est ce qui l'empeche
        d'etre une `KeyError` nue. Ici, ou l'on n'attend qu'un renseignement, ce
        refus se lit « je ne sais pas ou ce lot ecrit » -- ce que `None` dit
        deja, et ce que `T6-1` sait rendre (zero frame comptee pour ce lot,
        jamais un chemin invente).
        """
        if payload is None:
            return None
        try:
            return atelier_scan_ecriture.dossier_de_sortie(
                self.dossier_projet, payload)
        except (ValueError, RuntimeError):
            # **`RuntimeError` et pas seulement `ValueError`**, corrige le
            # 2026-09-01 avec `EPIC11-ARB-133`. `derive_lot_dir_slug` refuse
            # aussi un `lot_id` qui ne se recompose pas de son rush et de sa
            # cadence -- `scan_output_frames.LotInconsistencyError`, qui herite
            # de `RuntimeError` --, et cette valeur-la est **lue sur du papier
            # scanne** : elle arrive de l'exterieur. Le refus traversait donc
            # jusqu'a l'ecran en trace Python nue, ce qui est le pire des
            # blocages secs. Il vaut ici ce que `None` dit deja : « je ne sais
            # pas ou ce lot ecrit ». Le coeur, lui, refusera nommement a
            # l'ecriture, et la table des refus de `E3-7` le nommera.
            return None

    def _reglages_de_calibration(self) -> dict:
        """Ce que `E3-5` a retenu, **porte tel quel** au coeur.

        Les deux champs de `CalibrationRetenue` sont exclusifs par construction
        -- la classe leve si on les porte ensemble --, et ils partent chacun a
        son mot-cle : `profil_designe=` et `livrer_brut=`. Un profil vide serait
        une correction identite, c'est-a-dire une correction *appliquee*, et le
        manifeste la declarerait comme telle.

        Sans passage par `E3-5` -- ce qui n'arrive pas dans le parcours, mais
        arrive a un banc qui monte `E3-7` seul --, rien n'est designe et le
        coeur applique sa propre precedence (`profil_designe_du_projet`).
        """
        retenue = self.calibration_retenue
        if retenue is None:
            return {}
        return {
            "profil_designe": retenue.profil_designe,
            "livrer_brut": retenue.livrer_brut,
            "origine_du_profil": (None if retenue.profil_designe is None
                                  else ORIGINE_DU_PROFIL),
        }

    def ecrire(self, *, nouvelle_version: bool = False):
        """`E3-7` puis `E3-8` : monter l'ecran, appeler le coeur, conclure.

        `nouvelle_version` est le drapeau d'`EPIC11-ARB-89` / `-133`, pose par
        la seule issue de `E3-6` qui le demande. Il **traverse** jusqu'au coeur
        sans etre interprete : voir :meth:`plan_d_ecriture`.

        **Trois ordres, et aucun n'est cosmetique :**

        1. `ouvrir_l_ecriture` monte `E3-7` **avant** l'appel au coeur : c'est
           `on_mount` qui abonne l'ecran aux jalons de la surface, et appeler le
           coeur d'abord laisserait la barre figee du debut a la fin ;
        2. le relais du journal **vise** la surface de l'ecran monte, et pas
           avant : le journal de `E3-7` n'existe qu'une fois l'ecran monte, et
           les lignes de la phase precedente n'ont nulle part ou aller ;
        3. `lancer_l_ecriture` met le coeur **au fil**, derriere un rendez-vous
           de dessin. Il en faut DEUX, et ce point n'en portait qu'un jusqu'au
           2026-09-06 : le rendez-vous fait apparaitre `E3-7` une fois, le fil
           est ce qui garde la boucle vivante **pendant** la passe. Sans lui,
           l'ecran affichait `0 %  0/6300` et ne bougeait plus jusqu'a la fin
           de l'ecriture -- ce que l'operateur lit comme un coeur en panne.
           C'etait la derniere ligne du registre d'exceptions de
           `tests/unit/tui/test_frontiere_du_dessin_avant_le_coeur.py`, et les
           deux motifs du rendez-vous tiennent toujours : a l'instruction qui
           suit `descendre`, `on_mount` n'a pas encore tourne -- la surface n'a
           **aucun** observateur et `tache_en_cours` vaut faux, si bien que
           `Echap` depilerait l'ecran d'une passe qui tourne au lieu d'ouvrir
           `T6-1`, et qu'un fil parti avant ce montage pourrait eteindre le
           drapeau que `on_mount` rallume ensuite.

        Le **chronometre part avant l'appel au coeur**, pas apres : une duree
        mesuree apres coup ne compterait pas l'ecriture.

        `conclure` cable deja le rappel des suites de `E3-8` : le recomposer ici
        serait exactement le point ou le finding `K3` a mordu -- l'ecran savait
        s'en servir, la fonction savait le transmettre, et le point d'appel ne
        le passait pas.

        Rend l'ecran monte, **jamais le rapport** : il n'existe pas encore
        quand cette methode rend la main, et c'est exactement ce que le
        passage au fil change. Il arrive par `sur_rapport`, sur la boucle.
        """
        confirme = self.confirmation.plan
        # **Aucun nom ne sort plus de `E3-6`** (`EPIC11-ARB-141`) : l'ecran n'en
        # edite plus, donc il n'y a plus rien a retenir entre lui et le coeur.
        # `ecrire_depuis_le_document` n'a de toute facon aucun parametre ou le
        # poser, et c'est cette mesure-la qui a fait retirer le champ.
        plan = self.plan_d_ecriture(confirme,
                                    nouvelle_version=nouvelle_version)
        ecoule = atelier_scan_resultat.chronometre()
        logger, relais = self._journal_de_l_ecriture()
        ecran = atelier_scan_ecriture.ouvrir_l_ecriture(self.app, plan)
        if relais is not None:
            relais.viser(ecran.surface.journal)
        reglages = ({} if self._ecriture is None
                    else {"ecrire": self._ecriture})
        atelier_scan_ecriture.lancer_l_ecriture(
            self.app, ecran, plan, logger=logger,
            sur_rapport=lambda rapport: atelier_scan_resultat.conclure(
                self.app, rapport, journal=ecran.surface.journal,
                duree=ecoule(), attendues=plan.frames),
            **reglages)
        return ecran

    def _journal_de_l_ecriture(self):
        """Le logger de la passe d'ecriture, et son relais vers `E3-7`.

        **Jamais celui de la detection** : deux passes qui partageraient un nom
        de logger verraient leurs lignes tomber dans le journal de l'autre. Un
        logger injecte par un banc l'emporte sur les deux, et n'a alors aucun
        relais -- c'est le banc qui observe, pas l'ecran.
        """
        if self._logger_injecte is not None:
            return self._logger_injecte, None
        if self._journal_ecriture is None:
            self._journal_ecriture = atelier_scan_ecriture.journal_du_produit()
        return self._journal_ecriture

    # -- `E3-9` : calibrer une chaine de scan ---------------------------------

    def calibrer_la_chaine(self):
        """`E3-9`, depuis le menu de l'atelier (`EPIC11-ARB-28`).

        L'entree « Calibrer une chaine » menait a `EcranPasEncore` jusqu'au lot
        H de la story 11.6 ; l'ecran est livre, la promesse est tenue.

        `mesurer` est le double de banc du dpi ; son absence fait mesurer le
        **vrai** fichier designe, ce qui est le chemin de production.
        """
        ecran = atelier_scan_calibrate.EcranCalibrerLaChaine(
            self.dossier_projet, calibrer=self.consigner_le_profil,
            mesurer=self._mesurer)
        self.ecran_de_calibration = ecran
        self.app.descendre(ecran)
        return ecran

    def consigner_le_profil(self, formulaire):
        """Ce que `Valider` fait : **montrer ce qui va etre fait**, pas ecrire.

        Egan, 2026-09-01 : « Pas de page de validation avant, ce n'est pas
        conforme au reste des parcours. » Il avait raison sur les deux moities
        -- le temps 2 pose un `EcranChiffre` avant toute ecriture (`E3-6`), et
        la calibration partait sans.

        **La confirmation n'est pas sautable**, et c'est ce qui en fait une :
        ce point d'entree ne lance plus rien lui-meme ; seule l'issue
        `ISSUE_LANCER` mene a :meth:`lancer_la_passe_de_calibration`.

        La garde de re-entrance reste **ici**, avant la confirmation : montrer
        « ce qui va etre fait » pendant qu'une passe tourne deja promettrait un
        travail que la garde refusera ensuite.
        """
        if self.app.tache_en_cours:
            ecran_du_formulaire = self.ecran_de_calibration
            if ecran_du_formulaire is not None:
                ecran_du_formulaire._etat_a_dire = jetons.marque(
                    "substitute",
                    atelier_scan_calibrate.PHRASE_PASSE_EN_COURS,
                    getattr(self.app, "ascii_seul", False))
            return None
        ecran = atelier_scan_calibrate.EcranCalibrationAConfirmer(
            formulaire,
            sur_issue=lambda issue: self.trancher_la_confirmation(
                issue, formulaire))
        self.app.descendre(ecran)
        return ecran

    def trancher_la_confirmation(self, issue, formulaire):
        """Les deux issues du point de jugement, **et chacune mene quelque part**.

        « Revenir au formulaire » depile : le formulaire est intact dessous,
        avec ce que l'operateur y a saisi. Le remonter neuf lui ferait ressaisir
        ce qu'il vient de relire.
        """
        if issue.cle == atelier_scan_calibrate.ISSUE_LANCER:
            # **La confirmation se CONSOMME**, comme tout point de jugement :
            # l'operateur a tranche, la question n'a plus lieu d'etre posee.
            # La laisser sur la pile mettrait l'ecran d'execution PAR-DESSUS
            # elle, et le depilement de fin de passe rendrait alors la
            # confirmation plutot que le formulaire annote -- l'operateur
            # relirait la question a laquelle il vient de repondre.
            if (self.app.screen_stack and isinstance(
                    self.app.screen,
                    atelier_scan_calibrate.EcranCalibrationAConfirmer)):
                self.app.pop_screen()
            return self.lancer_la_passe_de_calibration(formulaire)
        # **`pop_screen` et non `action_remonter`**, exactement comme
        # `sortir_du_refus` huit methodes plus bas -- et le meme commit avait
        # ecrit le motif la sans l'appliquer ici. `action_remonter` est la
        # touche `Échap` de l'operateur et elle est **gardee par
        # `tache_en_cours`** : drapeau pose, « Revenir au formulaire » ne
        # depilait RIEN et armait au passage `interruption_demandee`, que rien
        # sur ce chemin ne lit. Une issue annoncee, choisie, inerte.
        # Mesure (revue de vague B, couches 1 et 2, independamment) : pile
        # `[..., EcranCalibrerLaChaine, EcranCalibrationAConfirmer]` inchangee
        # apres le choix, et `interruption_demandee` passe a vrai.
        # **Garde par IDENTITE, comme la branche `LANCER` huit lignes plus
        # haut.** Un cardinal ne dit pas QUOI on depile : avec un ecran
        # intercale au-dessus, « Revenir au formulaire » depilait l'intrus et
        # laissait la confirmation ; deux `valider()` sur la meme instance
        # depilaient DEUX ecrans et emportaient `E3-9` (revue de reprise,
        # couche 2). Au clavier la fenetre ne s'ouvre pas, mais deux gardes
        # differentes pour une meme intention divergeront.
        if (self.app.screen_stack and isinstance(
                self.app.screen,
                atelier_scan_calibrate.EcranCalibrationAConfirmer)):
            self.app.pop_screen()
        return None

    def lancer_la_passe_de_calibration(self, formulaire):
        """Lancer la passe de calibration **dans un fil de travail**.

        C'est le seul endroit du paquet ou une passe ne tourne pas sur la
        boucle, et le motif est mesure plutot que prudentiel : le coeur pose sa
        question de collision **depuis l'interieur** de l'ecriture du profil, et
        il attend la reponse dans la meme pile d'appel. Une question posee sur
        la boucle depuis la boucle ne peut pas etre repondue -- c'est le
        docstring de :class:`QuestionDeCollision`, avec les deux fausses issues
        qu'il ecarte.

        Le fil de travail n'appelle **jamais** un ecran directement : il repasse
        par la boucle (`call_from_thread`) pour monter la collision et pour
        annoncer la passe. C'est la seule discipline que `textual` impose, et
        c'est aussi ce qui garde l'interface vivante pendant l'ingestion du
        scan.

        **Le cycle de vie de la tache est pose ici, et il ne l'etait pas.**
        `E3-9` est un `Palier` et non un `EcranExecution` : personne n'ecrivait
        `app.tache_en_cours` sur ce chemin, seul `execution.py` le fait. `Échap`
        depilait donc `E3-9` pendant que le fil tournait, et l'annonce de fin
        de passe levait `NoMatches('#etat')` dans `call_from_thread` -- une application
        qui tombe sur une passe qui avait **reussi**, le profil ecrit et
        l'operateur n'en sachant rien. Le drapeau est pose avant le fil, oublie
        dans un `finally`, et il sert **aussi** de garde de re-entrance : les
        deux defauts sont le meme cycle de vie, ils se ferment ensemble.
        """
        # **Le formulaire de la passe est retenu ICI**, et pas ailleurs
        # (`EPIC11-ARB-266`). `PasseDeCalibration` ne porte pas la source : elle
        # porte ce que la passe a **produit**, jamais ce qu'on lui a donne. Or
        # l'issue « trier cette pile par QR » a besoin de la meme source et du
        # meme dpi -- rendre la pile au parcours de scan sans les avoir serait
        # redemander a l'operateur ce qu'il vient de saisir. Retenu avant le
        # fil, comme le drapeau de tache : les deux appartiennent au meme cycle
        # de vie.
        self._formulaire_de_la_passe = formulaire
        if self.app.tache_en_cours:
            # **Et elle le DIT** (finding `F3` de la couche de reprise de la
            # vague 4). Elle etait muette, huit lignes sous un commentaire qui
            # rappelle qu'« une touche annoncee qui ne fait rien et ne dit rien
            # est indistinguable d'un clavier casse ». `⏎` ne faisait rien et
            # ne disait rien.
            #
            # J2 rend ce regime beaucoup plus rare -- l'ecran d'execution est
            # monte PAR-DESSUS le formulaire, donc on ne peut plus y appuyer --
            # mais « plus rare » n'est pas « impossible », et une garde muette
            # reste muette le jour ou elle mord.
            ecran_du_formulaire = self.ecran_de_calibration
            if ecran_du_formulaire is not None:
                # `_etat_a_dire` est la surface d'etat de cet ecran, et la
                # meme que ses propres refus emploient : lui en ajouter une
                # seconde ferait deux facons de dire la meme chose.
                ecran_du_formulaire._etat_a_dire = jetons.marque(
                    "substitute",
                    atelier_scan_calibrate.PHRASE_PASSE_EN_COURS,
                    getattr(self.app, "ascii_seul", False))
            # **Garde de re-entrance**, et elle porte le meme drapeau que la
            # garde d'`Echap` ci-dessous : c'est le meme cycle de vie. Sans
            # elle, deux `⏎` lancaient DEUX passes concurrentes sur le meme
            # scan -- deux ingestions, deux ecritures de profil, et la seconde
            # est litteralement « la seconde ecriture que personne n'a
            # demandee » que le docstring de `QuestionDeCollision` ecarte.
            #
            # **`exclusive=True` n'est PAS le remede**, et c'est pourquoi il
            # n'est pas employe : un worker de fil ne s'annule pas. `textual`
            # marquerait le premier « annule » pendant que son fil continue
            # d'ingerer et d'ecrire -- deux passes concurrentes quand meme,
            # avec en plus une interface qui croit le contraire.
            return None
        ecran = self.ecran_de_calibration
        # **L'ecran d'execution est monte AVANT le fil**, et ce choix a ete
        # renverse puis retabli : `EPIC11-ARB-160` le tranche, avec sa mesure.
        #
        # Le montage TARDIF -- au premier jalon -- a ete essaye pour tenir
        # l'AC 9.6 (« une passe qui echoue avant la detection ne monte pas
        # l'ecran d'execution »). Il la tient. Il coute trois choses, les trois
        # mesurees et les trois trouvees independamment par les trois couches
        # de la revue de reprise :
        #
        # * le premier jalon n'arrive qu'apres la premiere page **produite**
        #   par l'ingestion, c'est-a-dire apres sa rasterisation -- et sur un
        #   scan entierement illisible il n'arrive pas du tout (AC 9.3,
        #   `EPIC7-ARB-79` : « un refus d'ingestion ne produit aucune
        #   progression »). Un montage tardif laisserait donc l'operateur
        #   devant le formulaire fige pendant toute la rasterisation de la
        #   premiere page, et devant **rien du tout** pendant une tentative
        #   d'ingestion entierement refusee -- litteralement le grief d'Egan
        #   que ce lot existe pour fermer, « RIEN n'indique qu'on a lance le
        #   processus » ;
        #
        #   > **Corrige le 2026-09-07, et ce paragraphe declarait l'inverse du
        #   > code de son propre commit.** Il disait « le premier jalon est
        #   > emis apres la detection de la page 1, apres le chemin le plus
        #   > lent du depot (decodage QR) ». C'etait vrai jusqu'a `f41a22a79`,
        #   > qui a dote `scan_ingest.ingest_scan_lot` de son canal de
        #   > progression -- le commit qui a AJOUTE le relais des phases vingt
        #   > lignes plus bas est celui-la meme qui a rendu ce texte faux. Le
        #   > cout du montage tardif est donc plus petit qu'ecrit ici, il n'est
        #   > pas nul, et les deux points suivants ne bougent pas.
        # * `E3-9` reste au SOMMET, donc **vivant et editable**, pendant que la
        #   passe tourne. Or `consigner` ne lit l'etiquette et le commentaire
        #   qu'a la fin. Mesure : etiquette `alpha` a la validation, trois
        #   frappes pendant l'ingestion, et le coeur recoit `alphazzz`. Le
        #   profil est nomme par ce que l'operateur a tape APRES avoir valide ;
        # * `Échap` y est inerte ET muet (garde par `tache_en_cours`, sans
        #   ecran d'execution pour l'accueillir), donc l'AC 9.5 n'est tenue
        #   qu'a partir du premier jalon.
        #
        # L'AC 9.4 et l'AC 9.6 sont inconciliables **a la lettre** sur un coeur
        # synchrone : on ne peut pas savoir qu'une passe sera refusee avant de
        # l'avoir lancee. Ce qui est retenu tient l'AC 9.6 dans son MOTIF --
        # « un ecran de progression qui PARAITRAIT sur un refus serait la meme
        # faute qu'un jalon avant l'ecriture » : aucun chiffre n'est invente
        # (le total part a zero, aucun jalon n'est emis avant la premiere page
        # PRODUITE, donc un refus d'ingestion n'en emet aucun et la passe n'est
        # jamais declaree), et `conclure_la_passe` depile cet ecran **avant** de
        # montrer le refus, si bien que l'operateur « va directement au refus ».
        # Ce qui n'est pas tenu est sa lettre -- « ne monte pas » --, et c'est
        # dit plutot que tu.
        #
        # **Cet argument n'est pas gratuit : il REPOSE sur une garantie du
        # coeur, et elle se nomme.** « Aucun jalon avant la premiere page
        # produite » est l'AC 9.3 (`EPIC7-ARB-79`), tenue par `_ingest_files`
        # -- ses deux branches de saut passent par `_le_saut_peut_emettre`, qui
        # differe leur jalon tant qu'aucune page n'existe -- et mesuree dans
        # `tests/unit/test_progression_de_l_ingestion_du_scan.py`. Le jour ou
        # cette garantie tombe, c'est CE paragraphe qui devient faux, et le
        # symptome se lit ici : `RelaisDesPhasesDeLaCalibration` declare les
        # deux lots au **premier** jalon, donc un jalon emis sur un refus fait
        # paraitre un lot « Detection » a N pages avant que la detection n'ait
        # rien dit -- un chiffre invente presente comme une mesure.
        #
        # **La garantie a UNE exception, et la taire ici serait refaire la
        # faute que ce commentaire corrige.** Les jalons emis depuis
        # `_ingest_pdf` pour des pages reellement rasterisees partent avant que
        # l'exception ne soit connue : un dossier ne portant qu'un PDF
        # partiellement rasterisable emet donc encore de la progression avant
        # son refus -- mesure du coeur, `(1, 3)` puis `(2, 3)`, soit une barre
        # a 67 % puis `EmptyScanLotError`. C'est une tolerance documentee la-bas
        # (`test_un_PDF_partiellement_rasterisable_SEUL_emet_encore_avant_son_`
        # `refus`), et la fermer demanderait de rendre muette la phase la plus
        # longue de la calibration. Ce que l'AC 9.6 tient dans son motif est
        # donc : aucun chiffre INVENTE, et aucune barre COMPLETEE sur un refus.
        # Pas : « aucun jalon, jamais ». La premiere redaction de ce paragraphe
        # ecrivait la seconde, ce qui aurait fait lire une garantie plus forte
        # que celle que le coeur tient.
        #
        # > **Corrige le 2026-09-07.** Entre `f41a22a79` (l'ingestion se met a
        # > emettre) et la fermeture de l'AC 9.3, ce texte a ete litteralement
        # > faux : un refus d'ingestion portait `2/4` a l'ecran, dont un lot
        # > « Detection » annonce a 2 pages. La phrase n'a pas ete relachee
        # > pour coller au regime fautif -- elle est reecrite pour le regime
        # > corrige, et la garantie dont elle depend est nommee au lieu d'etre
        # > supposee.
        from .execution import SurfaceExecution
        surface = SurfaceExecution(
            unite=atelier_scan_calibrate.UNITE_DE_LA_PASSE)
        self._surface_de_la_passe = surface
        # **Le relais du produit se branche ICI, et il ne l'etait NULLE PART**
        # (findings `C3` et `C2-4`, trouves independamment par deux couches de
        # la revue du 2026-09-06). `self._relais` naît a la meme ligne que
        # `self._logger` -- celle qui dote le parcours d'un journal quand
        # l'appelant n'en impose pas --, et le seul `viser` du fichier porte sur
        # un AUTRE relais, celui de la passe d'ecriture (`_journal_de_l_ecriture`).
        # Celui-ci visait donc `None` pour la vie du parcours ; or
        # `RelaisDeJournal.emit` **jette** ce qui arrive avant un `viser`, par
        # construction et pour une bonne raison (ne pas deverser un passe que
        # l'operateur n'a pas demande). Tout ce que le coeur dit pendant la
        # calibration tombait dans le vide.
        #
        # Le regime mesure, et c'est le grief d'origine d'Egan sous une autre
        # forme : un operateur qui ne saisit rien, sur une feuille dont le
        # libelle porte une parenthese -- « hp envy 4520 (bureau) », « Été
        # chaine n°2 », un libelle de 49 caracteres --, obtient un profil nomme
        # par son `chain_id`. Le coeur l'AVERTIT
        # (`scan_calibrate.py`, repli de nommage) et cet avertissement n'avait
        # aucun journal ou aller : aucun mot nulle part.
        if self._relais is not None:
            self._relais.viser(surface.journal)
        question = QuestionDeCollision(self._poser_la_collision)
        reglages = ({} if self._calibration is None
                    else {"calibrer": self._calibration})
        # **Le drapeau se pose AVANT le fil**, jamais dans le fil : entre le
        # `run_worker` et la premiere ligne du fil, la boucle tourne, et un
        # `Echap` qui y tomberait depilerait `E3-9` sous la passe.
        self.app.tache_en_cours = True
        # **Un ecran par passe**, monte ici et jamais reutilise : l'ecran de la
        # passe precedente est demonte, et le garder ne montrerait plus rien a
        # partir de la deuxieme calibration de la session.
        self.ecran_de_passe = (
            atelier_scan_calibrate.ouvrir_la_calibration_en_cours(
                self.app, surface=surface))

        # **Le routeur des DEUX phases** (dette `CALIB-N1`, fermee le
        # 2026-09-07). Depuis que `scan_ingest.ingest_scan_lot` emet lui aussi,
        # le coeur envoie deux suites de jalons par le meme rappel ; sans ce
        # relais, la seconde suite ferait RECULER la barre au lieu de la faire
        # avancer -- 1/1 puis 1/1 sur une mire, ce qui est le grief d'origine
        # avec un pas de plus. Il vit dans `atelier_scan_calibrate` avec le
        # reste du vocabulaire de la passe ; ici on ne fait que le brancher.
        relais_des_phases = (
            atelier_scan_calibrate.RelaisDesPhasesDeLaCalibration(surface))

        def noter_le_jalon(faites: int, total: int) -> None:
            """Un jalon du coeur, **repasse par la boucle**.

            Le rappel est appele depuis le fil de travail, et `sur_jalon` puis
            `EcranExecution.rafraichir` mutaient donc l'arbre de widgets hors
            de la boucle -- mesure a l'instrumentation : `asyncio_0`, une fois
            par page. Le docstring de cette methode dit pourtant, deux ecrans
            plus haut, que « le fil de travail n'appelle **jamais** un ecran
            directement ». Les trois autres ateliers repassent par la boucle.

            **Ce qui repasse par la boucle est le RELAIS, pas la surface** : il
            declare la passe et fait avancer le lot, donc il mute lui aussi
            l'etat que l'ecran dessine.
            """
            self.app.call_from_thread(relais_des_phases.noter, faites, total)

        def passe() -> None:
            try:
                resultat = atelier_scan_calibrate.consigner(
                    self.dossier_projet, formulaire,
                    poser_la_collision=question.demander,
                    hote=self.app.executer_en_processus,
                    logger=self._logger,
                    rappel_progression=noter_le_jalon, **reglages)
            except BaseException:
                # Le coeur a leve : le drapeau tombe **ici**, puisque
                # `conclure_la_passe` ne sera pas atteint. C'est la moitie du
                # `finally` d'origine qui reste necessaire.
                self.app.call_from_thread(self.app.oublier_la_tache)
                raise
            # **UN SEUL passage par la boucle pour conclure** (finding `F1`).
            # L'annonce etait hors du `try` et le drapeau tombait AVANT elle :
            # entre les deux `call_from_thread`, la boucle etait libre avec
            # `tache_en_cours` a faux, et un `Echap` y depilait `E3-9` sous une
            # annonce qui arrivait alors sur un ecran demonte. Mesure de bout en
            # bout par la couche de reprise : le profil ETAIT ecrit, et
            # l'operateur n'en savait rien.
            self.app.call_from_thread(self.conclure_la_passe, ecran, resultat)

        # **Le fil ne part qu'APRES le dessin** (mesure de la session voisine,
        # 2026-09-06, `rapport-2026-09-06-a-l-agent-epic-11-gel-des-ecrans-de-`
        # `progression.md` section 10). `EcranCalibrationEnCours` est un
        # `EcranExecution`, dont l'`on_mount` RALLUME `tache_en_cours` ; or
        # `Mount` est distribue par la boucle. Sans rendez-vous, une passe
        # courte -- un refus d'ingestion, une mire deja calibree -- pouvait
        # eteindre le drapeau AVANT ce montage, qui le rallumait ensuite :
        # drapeau final a vrai sur une passe morte, et l'atelier reste bloque
        # pour la session. Les deux regimes ont ete mesures a la sonde :
        #
        #     sans rendez-vous : descendre -> fil -> on_mount -> tache=True
        #     avec rendez-vous : descendre -> on_mount -> fil -> tache=False
        #
        # **Cette methode ne rend donc plus le `Worker`** : il n'existe pas
        # encore quand elle rend la main. Aucun appelant ne le lisait.
        _lancer_apres_le_dessin(self.app, lambda: self.app.run_worker(
            passe, thread=True, name="scan-calibrate",
            description="calibrer une chaine de scan"))

    def _poser_la_collision(self, collision, repondre) -> None:
        """Faire monter l'ecran de collision **par la boucle**, depuis le fil.

        `call_from_thread` rend la main des que l'ecran est empile ; la reponse,
        elle, arrive plus tard par `repondre`. C'est exactement la coupure que
        :class:`QuestionDeCollision` gere : monter est synchrone, repondre ne
        l'est pas.
        """
        self.app.call_from_thread(self.montrer_la_collision, collision,
                                  repondre)

    def montrer_la_collision(self, collision, repondre):
        """Les **trois** issues d'`EPIC11-ARB-89`, dont une seule ecrase.

        La reponse est posee **avant** le depilement, et l'ordre compte : le
        demontage repond `annuler` par filet (voir
        :class:`EcranCollisionDuScan`), et une reponse posee apres lui serait
        ignoree -- la premiere gagne. L'operateur qui a choisi « ecraser »
        verrait alors son choix silencieusement retourne en « annuler », ce qui
        est le pire des deux mondes : ni la destruction consciente qu'il a
        demandee, ni un refus qui se nomme.
        """
        def retenir(issue) -> None:
            repondre(issue.cle)
            self.app.pop_screen()

        ecran = EcranCollisionDuScan(
            collision, retenir=retenir,
            abandonner=lambda: repondre(
                atelier_scan_calibrate.CLE_ANNULER))
        self.app.descendre(ecran)
        return ecran

    def conclure_la_passe(self, ecran, passe):
        """Annoncer la passe, PUIS oublier la tache. L'ordre est le correctif.

        Findings `F1` et `F2` de la couche de reprise de la vague 4, fermes
        ensemble parce qu'ils sont le meme cycle de vie :

        * **l'annonce d'abord** (`F1`). Tant que le drapeau est a vrai,
          `action_remonter` ne depile pas : l'ecran que l'annonce va toucher
          est encore monte. Un `Echap` arrive pendant l'annonce est mis en file
          et traite apres, ce qui est le comportement voulu ;
        * **l'oubli quoi qu'il arrive** (`F2`). Sans le `finally`,
          `tache_en_cours` resterait a vrai pour la session si l'annonce levait
          : `Echap` ne depilerait plus, `q` ne quitterait plus, et la garde de
          re-entrance interdirait toute passe suivante -- le fil attend pour
          toujours, c'est-a-dire la panne exacte que le filet existe pour
          ecarter.

        **Les deux gestes sont dans la MEME fonction, et c'est ce qui ferme la
        fenetre.** Deux `call_from_thread` successifs laissent la boucle libre
        entre eux ; un seul ne la laisse pas.
        """
        try:
            # **L'ecran d'execution se DEPILE avant l'annonce** (lot J2). Il est
            # monte par-dessus `E3-9` pendant la passe ; le laisser en place a
            # la fin laisserait l'operateur devant une barre pleine, avec le
            # formulaire ANNOTE cache dessous -- c'est-a-dire avec le resultat
            # de sa passe invisible. Defaut introduit par J2 et trouve par les
            # bancs du temps 2, qui mesuraient deja que l'ecran final est
            # `E3-9` ; c'est la promesse d'`annoter_la_passe` (« pose sur
            # `E3-9` et pas seulement dit ») qui la porte.
            #
            # **`pop_screen` et non `action_remonter`** : la seconde est gardee
            # par `tache_en_cours`, qui est encore a vrai ici -- et il doit
            # l'etre, c'est tout le correctif de `F1`. Le depilement est un
            # geste du parcours, pas une remontee de l'operateur.
            #
            # **On depile JUSQU'A `E3-9`, pas d'un etage.** Un seul `pop` a
            # suffi tant que l'ecran d'execution etait le sommet ; il ne l'est
            # plus des que l'operateur a appuye sur `Échap` pendant la passe --
            # ce que l'AC 9.5 vient precisement de rendre possible --, et
            # l'ecran d'interruption se retrouve alors au-dessus. La boucle est
            # BORNEE par la taille de la pile : une condition d'arret qui
            # dependrait de ce qu'on depile pourrait ne jamais tomber.
            # **On ne depile QUE si la cible est effectivement dans la pile.**
            # Le repli `len(stack) <= 1` etait la condition d'arret de dernier
            # recours ; quand `ecran` n'y est pas -- `None` compris, et cet
            # attribut est garde contre `None` deux fois dans cette meme classe
            # --, c'est lui qui prenait la main et **demontait toute la
            # navigation** avant qu'`annoter_la_passe` ne leve un
            # `AttributeError` dans le fil (revue de vague B, couche 2).
            # **UNE seule regle de depilement, et elle nomme ce qu'elle
            # depile.** Il y en avait deux : une boucle qui remontait « jusqu'a
            # `E3-9` » et un depilement de l'ecran de passe par identite. La
            # reinjection l'a montre redondant -- reduire la premiere a un seul
            # `pop` ne faisait rougir personne, parce que la seconde finissait
            # le travail. Deux gardes pour une intention divergent au premier
            # ajustement (revue de reprise, couche 2), donc il n'en reste
            # qu'une.
            #
            # Elle vise **l'ecran de la passe**, pas un rang de pile : c'est lui
            # que le parcours a monte, et tout ce que l'operateur a pu empiler
            # pendant la passe -- l'ecran d'interruption ouvert par `Échap`, une
            # aide -- est necessairement AU-DESSUS de lui. Depiler jusqu'a l'en
            # sortir les emporte tous. La boucle est **bornee** par la taille de
            # la pile : une condition d'arret qui depend de ce qu'on depile
            # pourrait ne jamais tomber.
            #
            # Viser `E3-9` etait le pari que l'ecran de passe soit entre les
            # deux ; quand il ne l'etait pas, rien n'etait depile, l'ecran
            # d'execution restait monte et `tache_en_cours` restait vrai POUR
            # LA SESSION.
            if (self.ecran_de_passe is not None
                    and self.ecran_de_passe in self.app.screen_stack):
                for _ in range(len(self.app.screen_stack)):
                    if (self.ecran_de_passe not in self.app.screen_stack
                            or len(self.app.screen_stack) <= 1):
                        break
                    self.app.pop_screen()
            self.ecran_de_passe = None
            if ecran is not None:
                # **Le depilement se garde, l'annotation se garde a part.** Les
                # deux gestes n'ont pas la meme condition : on ne depile que
                # vers un ecran qui est dans la pile, mais on annote un ecran
                # des lors qu'il existe -- un `E3-9` hors pile est le cas des
                # bancs, et y annoter reste sans effet plutot que sans mesure.
                self.annoter_la_passe(ecran, passe)
        finally:
            self.app.oublier_la_tache()
        # **La NAVIGATION se fait drapeau tombe**, et la separation d'avec
        # l'annotation n'est pas cosmetique -- elle ferme une fenetre mesuree.
        #
        # L'annonce de fin de passe faisait les deux d'un bloc : elle annotait
        # `E3-9`
        # PUIS poussait l'ecran de refus. Or `descendre` rend la main a la
        # boucle au montage, si bien que l'ecran de refus etait vivant et
        # `tache_en_cours` encore a vrai. `sortir_du_refus` passe par
        # `action_remonter`, qui est **gardee par ce drapeau** : « Renommer
        # l'etiquette et reprendre » ne depilait rien. Sonde posee au moment du
        # choix : `tache=True`, pile
        # `[..., EcranCalibrerLaChaine, EcranRefusDeCalibration]`, et l'ecran
        # apres le choix inchange.
        #
        # C'est le correctif de `F1` qui avait ouvert cette fenetre en
        # inversant l'ordre, et la refermer ne le defait pas : ce que `F1`
        # protege est l'ANNOTATION de `E3-9` -- que `Echap` ne doit pas pouvoir
        # depiler sous elle --, pas la navigation qui suit.
        return self.ouvrir_ce_que_la_passe_demande(passe)

    def ouvrir_ce_que_la_passe_demande(self, passe):
        """L'aiguillage de fin de passe : le refus, ou **le resultat**.

        **Le court-circuit que cette methode ferme** (retour terrain d'Egan,
        2026-09-06 : « pas d'ecran de succes et on revient directement a la
        page pour lancer une calibration. Incoherent avec le reste »). La
        conclusion d'une passe n'avait qu'une branche de navigation, et elle
        etait reservee au REFUS : :meth:`ouvrir_ce_que_le_refus_demande`
        commence par `if passe.refus is None: return None`. Un profil ecrit ne
        montait donc rien, et l'operateur retombait sur son propre formulaire.

        C'est le geste **symetrique** qui donne la mesure : produire la mire
        (`E5-6e`, `atelier_pdf_calibration`) a un ecran de resultat depuis la
        story 11.1 ; la consommer n'en avait pas.

        **Trois issues et non deux**, parce que l'annulation devant la
        collision n'est ni un succes ni un refus a remontrer : l'operateur
        vient de dire « n'ecris rien », le formulaire reste sous ses yeux avec
        le motif du coeur en ligne d'etat, et **c'est** une issue. C'est ce que
        :meth:`ouvrir_ce_que_le_refus_demande` tranche deja ; on ne le redit pas
        ici, on l'appelle.
        """
        if passe.refus is not None:
            return self.ouvrir_ce_que_le_refus_demande(passe)
        if not passe.a_ecrit:
            # Ni refus, ni profil : rien a montrer et rien a taire. Le cas
            # n'existe pas au produit -- `consigner` rend l'un ou l'autre --,
            # et un ecran de succes monte sur une passe vide serait le
            # « champ non mesure rendu faux » que `DESIGN.md` section 3
            # interdit.
            return None
        # **`EPIC11-ARB-261` s'intercale ICI**, entre l'ecriture et le
        # resultat. Le balayage inverse du coeur
        # (`calibration_profile.profils_de_la_chaine`) etait ecrit, juste, et
        # cable NULLE PART -- les trois couches de la revue du 2026-09-07 l'ont
        # trouve independamment, et son propre docstring nommait l'appelant
        # manquant (« elle ne decide rien : elle rend, l'appelant avertit et
        # propose les deux issues »).
        autres = atelier_scan_calibrate.profils_a_remplacer(
            self.dossier_projet, passe)
        if autres:
            return self.montrer_la_chaine_deja_calibree(passe, autres)
        return self.ouvrir_le_resultat_de_la_calibration(passe)

    def montrer_la_chaine_deja_calibree(self, passe, autres):
        """Les DEUX issues d'`EPIC11-ARB-261`, puis le resultat **dans tous les cas**.

        Egan, tranche par invite le 2026-09-07 : « avertir et proposer les deux
        issues » -- remplacer le profil existant, ou garder les deux.

        **Le resultat suit quoi qu'il arrive, et par un seul chemin.** Trois
        sorties menent ici : retenir « garder », retenir « remplacer », et
        `Échap`. Les trois doivent finir sur l'ecran de resultat -- sortir sans
        rien montrer rejouerait le court-circuit que
        :meth:`ouvrir_ce_que_la_passe_demande` vient de fermer (retour terrain
        d'Egan : « pas d'ecran de succes et on revient directement a la page
        pour lancer une calibration »). La continuation est donc **une**, et
        gardee : `on_unmount` la declenche aussi, et le drapeau empeche le
        double montage quand une issue a deja depile.

        **`Échap` vaut « garder les deux », jamais « remplacer ».** Sortir sans
        choisir ne peut pas signifier detruire : c'est le meme principe que le
        filet de :class:`EcranCollisionDuScan`, ou le demontage repond
        `annuler`. Ici il n'y a rien a annuler -- le profil est ecrit --, donc
        le repli est l'issue qui ne retire rien.

        **Aucun fil n'attend**, a la difference de la collision : `conclure_la_passe`
        a rendu la main et `tache_en_cours` est tombe. C'est pourquoi cet ecran
        n'a pas besoin du filet de re-entrance de la collision, et pourquoi
        `Échap` peut simplement depiler.
        """
        fait = {"suivi": False}

        def poursuivre(etat: str = "") -> None:
            if fait["suivi"]:
                return
            fait["suivi"] = True
            ecran_du_resultat = self.ouvrir_le_resultat_de_la_calibration(passe)
            if etat and ecran_du_resultat is not None:
                # **La ligne d'etat porte le REMPLACEMENT, pas la mesure de la
                # passe**, et rien n'est perdu : le fichier ecrit, la chaine,
                # l'etiquette, les pastilles et la divergence sont tous dans le
                # cartouche de ce meme ecran (`panneau_du_resultat`). Ce qui
                # n'existe qu'ici est ce que le retrait a fait -- et une
                # destruction consciente qui ne se dirait nulle part serait la
                # moitie muette d'`EPIC11-ARB-89`.
                ecran_du_resultat.poser_etat(etat)

        def retenir(issue) -> None:
            etat = ""
            if issue.cle == atelier_scan_calibrate.CLE_REMPLACER_LE_PROFIL:
                remplacement = (
                    atelier_scan_calibrate.remplacer_les_profils_de_la_chaine(
                        self.dossier_projet, passe, autres))
                etat = atelier_scan_calibrate.etat_du_remplacement(
                    remplacement)
                # Le journal de la passe est encore vise par le relais : le
                # compte rendu du retrait y rejoint les jalons du coeur, et
                # `Tab journal` le montre sur l'ecran de resultat.
                self._logger.info("%s", etat)
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            poursuivre(etat)

        ecran = EcranChaineDejaCalibreeDuScan(
            passe, autres, retenir=retenir, poursuivre=poursuivre)
        self.app.descendre(ecran)
        return ecran

    def ouvrir_le_resultat_de_la_calibration(self, passe):
        """Monter l'ecran de succes de `E3-9`, ses suites deja cablees.

        Le rappel des suites est compose **ici** et pas au point de montage :
        c'est exactement la ou le finding `K3` a mordu -- l'ecran savait s'en
        servir, la fonction savait le transmettre, et le point d'appel ne le
        passait pas.

        Le journal est celui de l'ecran de passe **s'il en reste un** :
        `conclure_la_passe` vient de le depiler, mais l'objet `Journal` lui
        survit et porte les jalons de la passe. Sans lui, `Tab journal` n'est ni
        annonce ni traite, ce qui est la seule facon de ne pas annoncer une
        touche inerte.
        """
        return atelier_scan_calibrate.ouvrir_le_resultat(
            self.app, passe, self.dossier_projet,
            journal=getattr(self._surface_de_la_passe, "journal", None),
            sur_suite=lambda suite: self.suivre_le_resultat_de_la_calibration(
                passe, suite))

    def suivre_le_resultat_de_la_calibration(self, passe, suite: str) -> None:
        """Les trois suites de l'ecran de succes, **et chacune mene ailleurs**.

        * « Ouvrir le dossier » remet `versions/calibration/` a l'explorateur du
          systeme -- `execution.ouvrir_dans_l_explorateur_du_systeme` est
          l'**unique** lanceur du paquet (`EPIC11-ARB-85`), et le dossier est
          celui que le coeur compose (`dossier_des_profils`), jamais un chemin
          recompose ici ;
        * « Calibrer une autre chaine » depile le resultat : `E3-9` est dessous,
          avec son formulaire tel qu'il etait et son annonce de la passe qui
          vient de finir ;
        * « Detecter des planches » remonte a la page d'ouverture de l'atelier,
          `E3-0`, d'ou part la detection -- et pas plus haut (`EPIC11-ARB-13`).

        **`Retour aux ateliers` n'est PAS traite ici** : `EcranResultat`
        l'ajoute lui-meme et le traite lui-meme. Le doubler ferait deux
        redactions d'un retour, et l'ecrire dans la liste des suites le ferait
        voir deux fois.
        """
        if suite == atelier_scan_calibrate.SUITE_DOSSIER_DES_PROFILS:
            ouvrir_dans_l_explorateur_du_systeme(
                atelier_scan_calibrate.dossier_des_profils(
                    self.dossier_projet))
            return
        if suite == atelier_scan_calibrate.SUITE_AUTRE_CHAINE:
            # **`pop_screen` et non `action_remonter`**, meme motif que
            # `sortir_du_refus` : `action_remonter` est la touche `Échap` de
            # l'operateur et elle est **gardee par `tache_en_cours`**. Retenir
            # une issue est un geste du PARCOURS, pas une remontee.
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            return
        if suite == atelier_scan_calibrate.SUITE_DETECTER:
            atelier_scan_resultat.remonter_a_l_ouverture_de_l_atelier(self.app)

    def annoter_la_passe(self, ecran, passe) -> None:
        """Poser sur `E3-9` ce que la passe a produit. **Aucune navigation.**

        La moitie que le drapeau de tache protege : `annoncer` fait vivre la
        mesure sur l'ecran plutot que dans la ligne d'etat (« `poser_etat` seul
        se fait effacer par le dessin suivant »), et il faut donc que l'ecran
        soit encore monte quand elle s'ecrit.
        """
        ecran.annoncer(passe)
        ecran.rafraichir()

    def ouvrir_ce_que_le_refus_demande(self, passe):
        """L'ecran de refus, s'il y a lieu. **Aucune annotation.**

        Le refus ouvre le point de jugement de `E3-9` -- **jamais un ecran sans
        issue** (AC 8.3) : le coeur porte un chemin qui ne propose rien
        (« l'empreinte differenciante n'a pas separe les deux »), et
        `EcranRefusDeCalibration` en offre deux.

        **Une annulation devant la collision n'ouvre pas ce refus**, et c'est
        delibere : l'operateur vient de dire « n'ecris rien ». Lui reposer la
        question serait l'invite qui apprend a repondre sans lire, exactement ce
        qu'`EPIC5-ARB-99` ecarte. Le formulaire reste sous ses yeux, intact,
        avec le motif du coeur en ligne d'etat -- ce qui **est** une issue.
        """
        if passe.refus is None:
            return None
        if isinstance(passe.refus, atelier_scan_calibrate.CalibrationAnnulee):
            return None
        refus = atelier_scan_calibrate.EcranRefusDeCalibration(
            passe, retenir=self.sortir_du_refus)
        self.app.descendre(refus)
        return refus

    def sortir_du_refus(self, issue) -> None:
        """Les deux issues de l'impasse, **et aucune n'ecrit**.

        « Renommer l'etiquette et reprendre » remonte d'un cran : `E3-9` est
        dessous, avec son formulaire tel qu'il etait -- changer l'etiquette
        change le radical vise, donc sort de l'impasse. « Revenir au menu Scan »
        remonte jusqu'a la page d'ouverture de l'atelier, `E3-0`, et pas plus
        haut (`EPIC11-ARB-13`).
        """
        if issue.cle == atelier_scan_calibrate.CLE_RENOMMER:
            # **`pop_screen` et non `action_remonter`**, et le motif est le
            # meme que dans `conclure_la_passe` : `action_remonter` est la
            # touche `Échap` de l'operateur, et elle est **gardee par
            # `tache_en_cours`** -- elle pose `interruption_demandee` et rend.
            # Retenir une issue est un geste du PARCOURS, pas une remontee :
            # l'operateur vient de choisir explicitement, et son choix ne doit
            # pas dependre de l'etat d'une tache.
            #
            # Mesure qui l'impose (2026-09-01, sous `-n 4`) : le drapeau peut
            # etre encore a vrai au moment du choix, parce que les passes de
            # deux tests voisins se chevauchent dans un meme worker. « Renommer
            # l'etiquette et reprendre » ne depilait alors RIEN -- une issue
            # annoncee qui ne fait rien et ne dit rien, exactement ce que le
            # depot sanctionne ailleurs. Le defaut etait deja possible dans le
            # produit : il suffit que le choix arrive avant la fin de la passe.
            if len(self.app.screen_stack) > 1:
                self.app.pop_screen()
            return
        if issue.cle == atelier_scan_calibrate.CLE_TRIER_EN_VRAC:
            return self._trier_la_pile_refusee_en_vrac()
        atelier_scan_resultat.remonter_a_l_ouverture_de_l_atelier(self.app)

    def _trier_la_pile_refusee_en_vrac(self) -> None:
        """La troisieme issue du refus de pile mixte. `EPIC11-ARB-266`.

        **Aucun parcours neuf n'est ecrit, et c'est ce qui rend l'issue bon
        marche.** Le tri en vrac de la story 5.24 est deja le regime PAR DEFAUT
        de :meth:`detecter` -- `DemandeDeDetection` laisse `ingest_slug` a
        `None`, ce qui declenche le tri par QR (`EPIC5-ARB-106`). Cette methode
        ne fait donc que rendre au scan la pile que la calibration vient de
        refuser, avec la source et le dpi que l'operateur a deja saisis.

        **Elle depile le refus avant de relancer**, pour la meme raison que
        « renommer » : l'ecran de refus ne doit pas rester sous la passe qui le
        remplace, sans quoi `Echap` y retomberait apres coup -- sur un refus qui
        ne decrit plus rien.

        **La source et le dpi se lisent du FORMULAIRE, par ses deux proprietes,
        et jamais recomposes ici.** `chemin_du_scan` et `dpi_valide` portent
        deja les deux regles -- la quatrieme forme d'`EPIC7-ARB-88` pour l'une,
        la validation d'`EPIC7-ARB-44` pour l'autre --, et une seconde redaction
        divergerait. `self.dpi` ne conviendrait pas : il est pose par
        :meth:`detecter`, donc par le parcours de SCAN, et il vaut `None` chez
        l'operateur qui entre directement en calibration -- l'issue remonterait
        au menu en silence, c'est-a-dire une issue annoncee qui ne fait pas ce
        qu'elle dit.

        **Elle se garde de l'absence de formulaire** plutot que de la supposer.
        Un refus atteint sans passe -- il n'y en a pas aujourd'hui, mais rien ne
        l'interdit demain -- ferait tomber l'issue en `AttributeError` sur un
        ecran, c'est-a-dire une application qui meurt sur le geste de sortie
        d'une impasse. Elle remonte alors au menu, ce qui est l'autre issue.
        """
        formulaire = getattr(self, "_formulaire_de_la_passe", None)
        chemin = None if formulaire is None else formulaire.chemin_du_scan
        dpi = None if formulaire is None else formulaire.dpi_valide
        if chemin is None or dpi is None:
            atelier_scan_resultat.remonter_a_l_ouverture_de_l_atelier(self.app)
            return
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        self.detecter(chemin, dpi)

    def _document_du_lot(self, lot_id: str):
        """Le triplet du lot nomme, ou `None`.

        **Une egalite sur le `lot_id`, jamais un rang** : la liste des
        documents est celle du tri du coeur, et « le premier » n'y designe rien
        de stable.
        """
        for entree in self.documents:
            if entree[2].subject.lot_id == lot_id:
                return entree
        return None


def ouvrir_l_atelier_scan(app, dossier_projet, **reglages) -> EcranScanMenu:
    """Ce que l'entree *Scan* du menu des ateliers ouvre.

    C'est le rappel que `ChaineReelle` injecte, et sa signature est celle que
    `ChaineReelle.atelier_scan` appelle : `(app, dossier)`. Tout le reste est du
    reglage que seuls les bancs fournissent -- meme forme que
    `atelier_extraction_ecriture.ouvrir_les_cadences`.
    """
    return ParcoursScan(app, dossier_projet, **reglages).ouvrir()


__all__ = [
    "ORIGINE_DU_PROFIL",
    "EcranCollisionDuScan",
    "QuestionDeCollision",
    "nom_de_la_calibration",
    "HAUTEUR_DU_CHROME",
    "LIBELLE_EN_ATTENTE",
    "PHRASE_AUCUN_DOCUMENT",
    "PHRASE_DOCUMENT_ECRIT",
    "PHRASE_FRAMES_DU_MANQUE",
    "PHRASE_LOTS_INCOMPLETS",
    "PHRASE_RESTE_A_DIRE",
    "PHRASE_PAGES_DU_MANQUE",
    "PHRASE_SANS_DOCUMENT",
    "RACCOURCIS_RAPPORT",
    "SEPARATEUR_DE_MESURE",
    "TITRE_DU_RAPPORT",
    "EcranRapportDeDetection",
    "ParcoursScan",
    "documents_relus",
    "ouvrir_l_atelier_scan",
]
