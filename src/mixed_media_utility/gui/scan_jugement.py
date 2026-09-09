# -*- coding: utf-8 -*-
"""Atelier Scan -- le jugement : mode PDF, galerie, vue vignette unique.

**Nom de module, et pourquoi celui-la.** Ce module s'est d'abord appele
``atelier_scan.py``, et la story 7.3 -- developpee EN PARALLELE sur la meme
branche -- a pose sous ce nom sa page du **premier temps** de l'atelier
(deposer, detecter). Les deux stories tiennent les deux temps du meme
atelier : « L'atelier Scan se deroule en deux temps, jamais en un »
(``EXPERIENCE.md``). Le nom de fichier suit donc le TEMPS, pas l'atelier --
``scan_jugement`` ici, ``atelier_scan`` la-bas -- plutot que de faire porter
a un seul fichier deux stories, deux agents et deux perimetres de revue.

Story 7.4. **Cette story LIT et ne modifie rien** : ni le document de
detection, ni le manifeste, ni un fichier du projet. Elle est le second point
de jugement du chemin du scan -- regarder la page, verifier que ce que l'outil
propose de decouper est bien ce qu'on veut, et le faire **avant qu'un seul
TIFF ne s'ecrive** (l'ecriture est 7.6, la correction manuelle 7.5).

Ce que ce module porte, AC par AC :

* **AC 1** -- :class:`VueModePdf` : la page rasterisee sous ses
  surimpressions, les marqueurs manquants NOMMES par identifiant, les
  ``foreign_markers`` LISTES (le document n'en porte aucune coordonnee, donc
  aucun n'est dessine), et ``refusal_reason`` affiche **verbatim**, a cote de
  son code enumere quand le document en porte un ;
* **AC 2** -- :class:`BandeauDeVerrous` : deux indicateurs distincts, chacun
  son libelle propre, chacun trois etats. « Fondre les deux familles dans un
  seul signe » est un Don't de ``DESIGN.md``, et l'esprit vaut ici mot pour
  mot ;
* **AC 3** -- :class:`LegendeDeZone` : taille en pixels et timecode, lus du
  document, rendus **hors du contenu d'image** (Don't « Incruster une valeur
  sur l'image ») **et hors du panneau lateral** (``EPIC7-ARB-22``), sur le
  modele de ``frame-thumb.caption-position`` : sous la vignette, hors de
  l'image ;
* **AC 4** -- :class:`VueGalerie` : les pages du lot par **numero de
  planche** (`EPIC7-ARB-76`, revue de vague 3 : l'ordre du document est celui
  du scanner, et poser les trous dedans les mettait a la mauvaise place),
  leurs trous a leur place, et **aucune image de frame fabriquee** ;
* **AC 6** -- :class:`VueVignetteUnique` et :class:`PanneauLateralDeVue` ;
* **AC 8** -- toutes les surfaces d'image LISENT une preference d'image
  unique, portee par la coquille. Aucun ecran ne tient sa propre bascule ni
  son propre etat de calibration (``EPIC7-ARB-69``).

**Ce que la story ne fait PAS**, et qui se mesure : aucune poignee, aucune
loupe, aucun formulaire de QR, aucune annulation (7.5) ; aucun mode lecteur,
aucun badge de cadence, aucun bus de transport (7.6). Un clic sur une zone
**designe** -- il n'ouvre rien. La prise de 7.5 existe pourtant deja :
l'adresse complete ``(read_rank, page_index, slot_index)`` est portee
**jusqu'au widget**.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import scan_detect as _scan_detect
from . import barre_de_vue as _barre
from . import chutier as _chutier
from . import jetons
from . import lecture_detection as _lecture
from . import modele_chutier as _modele
from . import raster_de_page as _raster
from . import surimpressions as _surimpressions

# ---------------------------------------------------------------------------
# Etats d'une case de galerie -- la FAMILLE 1 bis : « qu'y a-t-il ici ? »
# ---------------------------------------------------------------------------

CASE_PRESENTE = "presente"
CASE_ABSENTE = "absente"
CASE_MIRE = "mire"

#: NOM de jeton par etat de case. Une frame absente laisse sa case a sa place
#: en `state-absent` (« il n'y a rien ici ») ; une mire de remplacement est en
#: `state-substitute` (« il y a quelque chose ici, mais ce n'est pas ton
#: image »), **jamais confondue avec une frame complete**.
JETON_COULEUR_PAR_CASE = {
    CASE_PRESENTE: "border",
    CASE_ABSENTE: "state-absent",
    CASE_MIRE: "state-substitute",
}

#: Cle de catalogue de la legende d'etat d'une case.
CHAINE_PAR_CASE = {
    CASE_PRESENTE: None,
    CASE_ABSENTE: "scan-case-absente",
    CASE_MIRE: "scan-case-mire",
}


def etat_de_case(zone) -> str:
    """L'etat d'un emplacement, lu de deux champs fermes et de rien d'autre.

    L'invariant du coeur (``EPIC5-ARB-8``) est que ``synthetic`` accompagne
    ``frame_path_relative``, ``False`` compris : un drapeau omis se relit
    « vraie frame » et ferait passer une mire « FRAME MANQUANTE » pour un plan
    du film. On lit donc les deux, dans cet ordre.
    """
    if zone.frame_path_relative is None:
        return CASE_ABSENTE
    return CASE_MIRE if zone.synthetic else CASE_PRESENTE


def badge_de_completude_des_planches(document) -> str:
    """L'etat de completude **des planches du lot**, LU du coeur.

    **FAMILLE 1 des signes** : « que manque-t-il dans ce lot ? ». Elle est
    rendue par ``badge-state``, sous son propre nom, et **sans reference a
    ``EPIC7-ARB-5``**, qui porte le triplet de RATTACHEMENT (``state-glyph``).
    Les deux familles ne se fondent jamais dans un signe unique
    (correction de ``DESIGN.md`` du 2026-08-23, section 1.4).

    **Le nom dit ce qui est mesure** (`EPIC7-ARB-73`, cause 3) : a l'etape
    `detected` -- la seule que cette vague voit -- ce sont **les planches du
    lot**, jamais les frames. La version d'avant exigeait en plus qu'aucune
    zone ne soit sans ``frame_path_relative``, si bien que le badge valait
    ``incomplet`` sur **tout** document de detection : aucune zone n'en porte
    avant la story d'ecriture, et le seul test qui le voyait vert fabriquait
    un document `reconstructed`, etat que cette story ne produit pas.

    Le verdict lui-meme n'est plus calcule ici : il vient de
    :func:`scan_detect.completude_des_planches`, qui le rend aussi au chutier.
    Deux surfaces, un seul calcul.
    """
    etat, _manquantes = _scan_detect.completude_des_planches((document.previz,))
    # Sans document il n'y a pas de verdict ; ici il y en a toujours un --
    # la vue tient un document, sans quoi elle n'aurait rien a peindre.
    return etat if etat is not None else _modele.BADGE_INCOMPLET


def planches_manquantes(document) -> tuple[int, ...]:
    """Les ``page_index`` que le lot attend et que le document ne porte pas.

    LUS du coeur (`EPIC7-ARB-73`), jamais rederives ici. Ce qui vivait a cette
    place jusqu'au 2026-08-25 en etait la seconde redaction, et elle differait
    de la premiere sur deux points mesures : le cardinal attendu (elle prenait
    le ``max(page_count)`` sur **toutes** les pages, y compris une page de
    calibration) et l'origine des index, qu'elle **observait**
    (``0 if 0 in presents else 1``) au lieu de la tenir de la convention du
    depot. Sur un lot dont la planche ``0`` manque -- 0-based, comme tout ce
    que le depot produit --, cette observation nommait manquante la planche
    ``cardinal``, qui n'existe pas, et n'affichait **aucun** trou pour la
    planche ``0``, qui manque reellement.

    Le trou **garde sa place** dans la grille : c'est :func:`rangs_et_trous`
    qui l'y pose.
    """
    _etat, manquantes = _scan_detect.completude_des_planches((document.previz,))
    return manquantes


def _cle_de_planche(page):
    """La cle d'affichage d'une page : son **numero de planche**.

    Une page dont le QR n'a pas livre d'index n'a pas de numero de planche :
    elle ne peut pas se ranger entre deux planches numerotees, donc elle passe
    apres toutes celles qui le sont. Le tri est **stable**, donc deux scans de
    la MEME planche (story 5.14) et les pages sans index gardent entre eux
    l'ordre du document -- c'est-a-dire leur ordre de lecture.
    """
    index = page.page.page_index
    return (1, 0) if index is None else (0, index)


def rangs_et_trous(document):
    """La suite des cases de PAGE de la galerie : presentes et trous.

    Rend une liste de ``(page_lue, None)`` et de ``(None, page_index)``.

    **La galerie affiche par numero de planche** (`EPIC7-ARB-76`), pas par
    ordre de passage au scanner : l'operatrice raisonne en planches, et une
    galerie qui afficherait 3 puis 1 lui demanderait de faire dans sa tete le
    tri que la machine refuse de faire. Le ``read_rank`` reste porte par le
    document et par chaque case, pour qui en a besoin.

    C'est ce tri qui rend vraie la seconde promesse : chaque trou **garde sa
    place** -- il s'insere devant la premiere planche presente dont l'index
    est plus grand que le sien, ce qui ne decale aucune des suivantes. Cette
    regle n'a de sens que sur une liste qui MONTE par ``page_index``, et
    jusqu'au 2026-08-25 elle s'appliquait a l'ordre du document, trie par
    ``read_rank`` par le coeur (`scan_detect.pages_du_lot`). Mesure de la
    revue de vague 3, lot de 3 planches dont la 2 manque, scanne a l'envers :
    ``[p3, p1]`` rendait ``['[trou 2]', 'p3', 'p1']`` -- le trou de la
    planche 2 pose **en tete**, c'est-a-dire la promesse exactement inversee.

    **Depuis `EPIC7-ARB-77` (2026-08-26), le coeur trie deja par
    ``page_index``** : « on range les pages selon l'ordre indique dans le QR »,
    pour toutes les surfaces a la fois. Le tri local ci-dessous devient donc
    **redondant sur les documents du depot** -- et il est **garde**, deliberement.
    Motif : un tri est **idempotent**, retrier une liste deja triee ne rend
    jamais un ordre different, donc les deux ne peuvent pas se contredire. C'est
    ce qui le distingue de la double derivation de la completude
    (`EPIC7-ARB-73`), ou deux CALCULS rendaient deux verdicts opposes. La regle
    d'insertion des trous, elle, exige l'invariant croissant pour etre juste :
    le tenir localement rend cette fonction correcte sur n'importe quelle entree,
    y compris un document venu d'une version qui ne trierait pas.
    """
    suite: list[tuple[object, int | None]] = [
        (page, None) for page in sorted(document.pages, key=_cle_de_planche)
    ]
    # Les pages sans numero de planche forment la queue de la liste : un trou
    # se pose parmi les planches numerotees, jamais apres elles.
    numerotees = sum(
        1 for page, _trou in suite
        if page is not None and page.page.page_index is not None
    )
    for manquant in planches_manquantes(document):
        position = numerotees
        for indice, (page, _trou) in enumerate(suite):
            if page is not None and page.page.page_index is not None:
                if page.page.page_index > manquant:
                    position = indice
                    break
        suite.insert(position, (None, manquant))
        numerotees += 1
    return suite


# ---------------------------------------------------------------------------
# AC 2 -- deux verrous, deux indicateurs, jamais un signe unique
# ---------------------------------------------------------------------------

#: NOM de jeton par etat de verrou. Le troisieme n'est pas une fusion des
#: deux premiers : c'est « le document ne le dit pas », en neutre.
JETON_COULEUR_PAR_VERROU = {
    _lecture.VERROU_TENU: "state-complete-text",
    _lecture.VERROU_ROMPU: "state-absent-text",
    _lecture.VERROU_INDETERMINE: "text-secondary",
}

#: Redondance non chromatique EXIGEE (meme motif que `badge-state`) : rouge
#: et ambre sont la paire la plus confusable, et l'outil s'ouvrira a des
#: videastes dont on ne connait pas la vision des couleurs.
MARQUE_PAR_VERROU = {
    _lecture.VERROU_TENU: "●",
    _lecture.VERROU_ROMPU: "○",
    _lecture.VERROU_INDETERMINE: "—",
}


class IndicateurDeVerrou(QFrame):
    """UN verrou : son libelle propre, son detail, son etat parmi trois.

    Il n'existe pas d'indicateur « des deux verrous » : c'est la formulation
    qui manquait a la maquette et c'est le coeur de cette story.
    """

    def __init__(self, cle, chaines, parent=None):
        super().__init__(parent)
        self.cle = cle
        self._chaines = chaines
        self.setObjectName(f"verrou-{cle}")
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(jetons.ESPACEMENTS["1"])
        typo_label = jetons.TYPOGRAPHIE["label"]
        self.libelle = QLabel(chaines[f"scan-verrou-{cle}"], self)
        self.libelle.setStyleSheet(
            f"color: {jetons.COULEURS['text-secondary']};"
            f" font-size: {typo_label['taille']}px;"
        )
        self.detail = QLabel(chaines[f"scan-verrou-{cle}-detail"], self)
        self.detail.setStyleSheet(
            f"color: {jetons.COULEURS['text-disabled']};"
            f" font-size: {typo_label['taille']}px;"
        )
        self.valeur = QLabel(self)
        self.valeur.setObjectName(f"verrou-{cle}-valeur")
        colonne.addWidget(self.libelle)
        colonne.addWidget(self.valeur)
        colonne.addWidget(self.detail)
        self.etat = None
        self.couleurs_posees = ()
        self.poser_etat(_lecture.VERROU_INDETERMINE)

    def poser_etat(self, etat: str) -> None:
        if etat not in _lecture.ETATS_DE_VERROU:
            raise ValueError(f"etat de verrou inconnu : {etat!r}")
        self.etat = etat
        couleur = jetons.COULEURS[JETON_COULEUR_PAR_VERROU[etat]]
        self.couleurs_posees = (
            couleur,
            jetons.COULEURS["text-secondary"],
            jetons.COULEURS["text-disabled"],
        )
        libelle = self._chaines[f"scan-verrou-{etat}"]
        self.valeur.setText(f"{MARQUE_PAR_VERROU[etat]} {libelle}")
        self.valeur.setToolTip(libelle)
        typo = jetons.TYPOGRAPHIE["body"]
        self.valeur.setStyleSheet(
            f"color: {couleur}; font-size: {typo['taille']}px;"
        )


class BandeauDeVerrous(QFrame):
    """Les DEUX indicateurs cote a cote, plus le motif de non-proposition.

    « La proposition des zones exige les deux au vert » : quand les zones
    sont absentes du document, cette bande dit **lequel** des deux verrous
    manque -- et quand c'est le QR, elle le dit **avec ce motif-la**, pas
    avec « geometrie non resolue ».
    """

    def __init__(self, chaines, parent=None):
        super().__init__(parent)
        self.setObjectName("bandeau-verrous")
        self._chaines = chaines
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(jetons.ESPACEMENTS["3"])
        ligne = QHBoxLayout()
        ligne.setSpacing(jetons.ESPACEMENTS["7"])
        self.identite = IndicateurDeVerrou("identite", chaines, self)
        self.geometrie = IndicateurDeVerrou("geometrie", chaines, self)
        ligne.addWidget(self.identite)
        ligne.addWidget(self.geometrie)
        ligne.addStretch(1)
        colonne.addLayout(ligne)
        self.motif = QLabel(self)
        self.motif.setObjectName("motif-non-proposition")
        self.motif.setWordWrap(True)
        self.motif.setStyleSheet(
            f"color: {jetons.COULEURS['text-secondary']};"
            f" font-size: {jetons.TYPOGRAPHIE['body']['taille']}px;"
        )
        colonne.addWidget(self.motif)
        self.couleurs_posees = (jetons.COULEURS["text-secondary"],)

    def poser(self, page) -> None:
        """Poser les deux etats. **Chacun est calcule separement.**"""
        self.identite.poser_etat(_lecture.etat_verrou_identite(page))
        self.geometrie.poser_etat(_lecture.etat_verrou_geometrie(page))
        motif = _lecture.motif_de_non_proposition(page)
        self.motif.setText("" if motif is None else self._chaines[motif])
        self.motif.setVisible(motif is not None)
        self.cle_de_motif = motif


class BandeauDEtatDePage(QFrame):
    """L'etat de page : refus verbatim, code enumere, marqueurs.

    Trois faits, et chacun a sa regle :

    * ``refusal_reason`` est affiche **caractere pour caractere**, jamais
      reformule et jamais interprete. **Aucun ecran ne decide quoi que ce
      soit en lisant cette phrase** (``EPIC7-ARB-66``) ;
    * le **code de refus enumere** l'accompagne **quand le document en porte
      un**. Repli explicite et PERMANENT : un document ecrit par une version
      anterieure a la story de coeur 5.27 -- c'est-a-dire, au 2026-08-25,
      **tous** -- n'en porte pas, et la GUI affiche alors la phrase seule.
      Elle n'invente jamais de code et n'en deduit aucun de la phrase ;
    * les marqueurs de coin **manquants** sont nommes **par leur
      identifiant**, sans position dessinee ; les ``foreign_markers`` sont
      **listes** (identifiant + role), jamais dessines -- le document n'en
      porte aucune coordonnee.

    L'etat « marqueurs incomplets » de la correction ``A7`` **n'existe pas**
    ici : il est retire de la specification par ``EPIC7-ARB-66``, faute de
    producteur au coeur (``MIN_CORNER_MARKERS_REQUIRED`` vaut quatre et
    ``CORNER_MARKER_IDS`` en compte quatre : c'est tout ou rien).
    """

    def __init__(self, chaines, parent=None):
        super().__init__(parent)
        self.setObjectName("etat-de-page")
        self._chaines = chaines
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(jetons.ESPACEMENTS["2"])
        typo = jetons.TYPOGRAPHIE["body"]
        typo_data = jetons.TYPOGRAPHIE["data"]

        self.refus = QLabel(self)
        self.refus.setObjectName("refus-phrase")
        self.refus.setWordWrap(True)
        self.refus.setStyleSheet(
            f"color: {jetons.COULEURS['state-absent-text']};"
            f" font-size: {typo['taille']}px;"
        )
        #: Le CODE du coeur, en typographie `data` : il ne se traduit jamais
        #: et ne passe donc pas par le catalogue -- seule son etiquette y est.
        self.code = QLabel(self)
        self.code.setObjectName("refus-code")
        self.code.setStyleSheet(
            f"color: {jetons.COULEURS['text-primary']};"
            f" font-family: {typo_data['famille']};"
            f" font-size: {typo_data['taille']}px;"
        )
        self.marqueurs = QLabel(self)
        self.marqueurs.setObjectName("marqueurs-manquants")
        self.marqueurs.setWordWrap(True)
        self.marqueurs.setStyleSheet(
            f"color: {jetons.COULEURS['text-secondary']};"
            f" font-size: {typo['taille']}px;"
        )
        self.etrangers = QLabel(self)
        self.etrangers.setObjectName("marqueurs-etrangers")
        self.etrangers.setWordWrap(True)
        self.etrangers.setStyleSheet(
            f"color: {jetons.COULEURS['text-secondary']};"
            f" font-size: {typo['taille']}px;"
        )
        for widget in (self.refus, self.code, self.marqueurs, self.etrangers):
            colonne.addWidget(widget)
        self.couleurs_posees = (
            jetons.COULEURS["state-absent-text"],
            jetons.COULEURS["text-primary"],
            jetons.COULEURS["text-secondary"],
        )

    def poser(self, page) -> None:
        chaines = self._chaines
        phrase = page.page.refusal_reason
        if phrase:
            # VERBATIM : l'etiquette du catalogue, puis la phrase du coeur,
            # intacte. Aucune troncature, aucune reformulation.
            self.refus.setText(f"{chaines['scan-refus-motif']} {phrase}")
        else:
            self.refus.setText("")
        self.refus.setVisible(bool(phrase))

        code = page.code_de_refus
        self.code.setText("" if code is None else f"{chaines['scan-refus-code']} {code}")
        self.code.setVisible(code is not None)

        manquants = page.marqueurs_manquants
        if manquants:
            self.marqueurs.setText(
                chaines["scan-marqueurs-manquants"].format(
                    identifiants=", ".join(str(identifiant) for identifiant in manquants)
                )
            )
        else:
            self.marqueurs.setText(chaines["scan-marqueurs-tous-presents"])

        etrangers = page.page.foreign_markers
        if etrangers:
            lignes = [chaines["scan-marqueurs-etrangers"]]
            lignes += [
                chaines["scan-marqueur-etranger-ligne"].format(
                    identifiant=marqueur.marker_id, role=marqueur.role
                )
                for marqueur in etrangers
            ]
            self.etrangers.setText("\n".join(lignes))
        else:
            self.etrangers.setText("")
        self.etrangers.setVisible(bool(etrangers))


# ---------------------------------------------------------------------------
# AC 3 -- la legende d'une zone : hors de l'image, hors du panneau lateral
# ---------------------------------------------------------------------------


class LegendeDeZone(QFrame):
    """Taille en pixels et timecode d'une zone, **sous** la vignette.

    Deux interdits se croisent et ne laissent qu'un seul endroit : le Don't
    « Incruster une valeur sur l'image » et ``EPIC7-ARB-22`` (« un panneau
    lateral ne repete pas ce que l'image montre deja -- ni le timecode
    affiche dans la scene, ni le numero de frame, ni la position d'une
    poignee »). Le seul endroit ferme par aucun des deux est la legende hors
    image, sur le modele explicite de ``frame-thumb.caption-position``.

    Les deux valeurs sont LUES du document : la taille des ``crop_*_px``
    (``EPIC7-ARB-15`` : « seul le tc est deduit du qr pas la taille qui
    depend du dpi et de la geometrie »), le timecode de ``frame_timecode``.
    Une zone sans timecode affiche une **absence nommee**, jamais un zero ni
    un tiret muet : un ``--:--:--:--`` sans mot dirait « pas d'image », et ce
    n'est pas ce que le champ dit.
    """

    designee = Signal(tuple)

    def __init__(self, page, zone, chaines, parent=None):
        super().__init__(parent)
        self.setObjectName("legende-zone")
        #: L'adresse COMPLETE, portee jusqu'au widget : c'est la prise de 7.5.
        self.adresse = (page.page.read_rank, page.page.page_index, zone.slot_index)
        self.slot_index = zone.slot_index
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        typo = jetons.TYPOGRAPHIE["data-sm"]
        style = (
            f"color: {jetons.COULEURS['text-secondary']};"
            f" font-family: {typo['famille']};"
            f" font-size: {typo['taille']}px;"
        )
        self.rang = QLabel(
            chaines["scan-zone-legende"].format(slot=zone.slot_index), self
        )
        self.rang.setStyleSheet(style)
        #: `{typography.data}` a chiffres tabulaires : deux tailles de meme
        #: cardinal doivent s'aligner colonne par colonne.
        self.taille = QLabel(
            chaines["scan-zone-taille"].format(
                largeur=zone.crop_w_px, hauteur=zone.crop_h_px
            ),
            self,
        )
        self.taille.setObjectName("zone-taille")
        self.taille.setStyleSheet(style)
        self.timecode = QLabel(
            zone.frame_timecode
            if zone.frame_timecode
            else chaines["scan-zone-timecode-absent"],
            self,
        )
        self.timecode.setObjectName("zone-timecode")
        self.timecode.setStyleSheet(style)
        self.timecode_est_absent = not zone.frame_timecode
        for widget in (self.rang, self.taille, self.timecode):
            colonne.addWidget(widget)
        self.couleurs_posees = (jetons.COULEURS["text-secondary"],)

    def mousePressEvent(self, evenement):  # noqa: N802 -- nom impose par Qt
        """Un clic **designe** cette zone. Il n'ouvre aucune poignee (7.5)."""
        self.designee.emit(self.adresse)
        super().mousePressEvent(evenement)


# ---------------------------------------------------------------------------
# AC 6 -- le panneau lateral d'une vue : retracte, memorise PAR VUE
# ---------------------------------------------------------------------------


class PanneauLateralDeVue(QFrame):
    """Un panneau lateral retractable, avec sa poignee de rappel.

    ``EPIC7-ARB-25`` : « tout panneau lateral d'atelier se retracte » ; « une
    vue qui n'a rien a mettre dans le panneau s'ouvre deja retractee » ;
    « l'etat retracte est memorise **par vue**, pas globalement ». D'ou un
    panneau par vue et jamais un panneau partage : partager l'objet
    partagerait l'etat, ce que l'arbitrage refuse explicitement.

    **Il ne porte ni taille, ni timecode, ni numero de frame**
    (``EPIC7-ARB-22``) : le banc le mesure sur l'arbre de widgets.
    """

    def __init__(self, chaines, retracte=False, parent=None):
        super().__init__(parent)
        self.setObjectName("panneau-lateral-de-vue")
        self._chaines = chaines
        self._retracte = bool(retracte)
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(0)
        self.poignee = QPushButton(self)
        self.poignee.setObjectName("poignee-panneau-lateral")
        self.poignee.setFixedWidth(jetons.ESPACEMENTS["hit-min"])
        self.poignee.clicked.connect(self.basculer_le_panneau)
        self.corps = QWidget(self)
        self.corps.setObjectName("corps-panneau-lateral")
        corps_v = QVBoxLayout(self.corps)
        corps_v.setContentsMargins(
            jetons.ESPACEMENTS["panel-pad"], jetons.ESPACEMENTS["panel-pad"],
            jetons.ESPACEMENTS["panel-pad"], jetons.ESPACEMENTS["panel-pad"],
        )
        corps_v.setSpacing(jetons.ESPACEMENTS["4"])
        ligne.addWidget(self.poignee)
        ligne.addWidget(self.corps, 1)
        self.couleurs_posees = (jetons.COULEURS["surface-panel"],)
        self.setStyleSheet(
            "#panneau-lateral-de-vue { background: "
            f"{jetons.COULEURS['surface-panel']}; }}"
        )
        self._appliquer()

    def ajouter(self, widget) -> None:
        self.corps.layout().addWidget(widget)

    @property
    def est_retracte(self) -> bool:
        return self._retracte

    def retracter(self) -> None:
        self._retracte = True
        self._appliquer()

    def deplier(self) -> None:
        self._retracte = False
        self._appliquer()

    def basculer_le_panneau(self) -> None:
        """Replier ou deplier CE panneau.

        Le nom porte son objet : `basculer` tout court serait confondu avec
        la bascule d'IMAGE de la coquille, que ce module n'a pas le droit de
        definir (`EPIC7-ARB-69`), et le grep qui le mesure perdrait son
        tranchant.
        """
        self._retracte = not self._retracte
        self._appliquer()

    def _appliquer(self) -> None:
        self.corps.setVisible(not self._retracte)
        cle = "scan-panneau-deplier" if self._retracte else "scan-panneau-replier"
        self.poignee.setToolTip(self._chaines[cle])
        self.poignee.setAccessibleName(self._chaines[cle])
        largeur = jetons.ESPACEMENTS["hit-min"] if self._retracte else (
            jetons.ESPACEMENTS["side-panel-width"]
        )
        self.setFixedWidth(largeur)


# ---------------------------------------------------------------------------
# Socle commun aux trois surfaces d'image
# ---------------------------------------------------------------------------


class SurfaceDImage(QWidget):
    """Ce que les trois vues d'image ont en commun, et qui n'est ecrit qu'ici.

    Une barre de vue (LA meme classe, ``A10``), une preference d'image LUE
    d'un etat unique (``EPIC7-ARB-69`` : « aucun ecran ne porte sa propre
    bascule locale, ni un etat de calibration qui lui soit propre ») et un
    panneau lateral dont l'etat retracte est **le sien**.

    La preference est branchee, jamais recopiee : la surface n'en garde
    aucune copie et relit ``preference.variante`` a chaque rafraichissement.
    """

    def __init__(self, chaines, preference, fournisseur=None,
                 panneau_retracte=False, parent=None):
        super().__init__(parent)
        self._chaines = chaines
        self._preference = preference
        self._fournisseur = fournisseur
        self.barre_de_vue = _barre.BarreDeVue(chaines, self)
        self.panneau_lateral = PanneauLateralDeVue(
            chaines, retracte=panneau_retracte, parent=self
        )
        if preference is not None and hasattr(preference, "variante_changee"):
            preference.variante_changee.connect(self._sur_changement_de_variante)

    def brancher_la_barre_de_vue(self, scene) -> None:
        """Relier les cinq controles de vue a la scene qu'ils commandent.

        **Ils n'etaient relies a rien** jusqu'au 2026-08-26 : `BarreDeVue`
        emettait `zoom_change` et `controle_active`, et aucune des trois vues
        d'image ne s'y abonnait. Le curseur de zoom glissait, les quatre
        boutons s'enfoncaient, et l'image ne bougeait pas d'un pixel -- « le
        zoom sur la page pdf n'est absolument pas fonctionnel » (Egan, premier
        essai de terrain). Ce n'etait pas un reglage a corriger : il n'y avait
        aucun cablage du tout.

        Le branchement vit sur la classe de base et non sur chaque vue :
        c'etait precisement l'absence d'un lieu unique qui rendait l'oubli
        invisible -- trois vues construisent une `BarreDeVue`, aucune ne la
        branchait, et rien dans le code ne le disait.
        """
        self.barre_de_vue.zoom_change.connect(scene.definir_zoom_pourcent)
        self.barre_de_vue.controle_active.connect(
            lambda cle, scene=scene: self._sur_controle_de_vue(cle, scene)
        )

    def _sur_controle_de_vue(self, cle, scene) -> None:
        """Appliquer un bouton de vue, puis ACCORDER le curseur au resultat.

        L'accord compte autant que le geste : « pleine largeur » change le
        facteur reel, et un curseur reste a 100 % pendant que l'image en fait
        180 mentirait sur l'etat de la vue. Le curseur est donc repositionne
        sans reemettre -- sans quoi il redemanderait aussitot son propre
        facteur, arrondi au pourcent, et « taille reelle » ne serait jamais
        exacte.
        """
        gestes = {
            _barre.CONTROLE_AJUSTER: scene.ajuster,
            _barre.CONTROLE_PLEINE_LARGEUR: scene.cadrer_sur_la_largeur,
            _barre.CONTROLE_PLEINE_HAUTEUR: scene.cadrer_sur_la_hauteur,
            _barre.CONTROLE_TAILLE_REELLE: scene.taille_reelle,
        }
        geste = gestes.get(cle)
        if geste is None:
            return
        geste()
        self.barre_de_vue.accorder_le_zoom(round(scene.zoom * 100))

    @property
    def variante_dimage(self) -> str:
        """La variante courante, **lue** de la preference partagee."""
        if self._preference is None:
            return _raster.IMAGE_BRUTE
        return self._preference.variante

    def poser_fournisseur(self, fournisseur) -> None:
        self._fournisseur = fournisseur
        self.rafraichir()

    def image_de(self, page):
        """Le raster d'une page dans la variante COURANTE, ou ``None``."""
        if self._fournisseur is None or page is None:
            return None
        return self._fournisseur.image(page, self.variante_dimage)

    def _sur_changement_de_variante(self, _variante) -> None:
        self.rafraichir()

    def rafraichir(self) -> None:  # pragma: no cover -- surcharge par les vues
        """Redessiner ce que la surface montre. Surchargee par chaque vue."""


# ---------------------------------------------------------------------------
# AC 1, 2, 3 -- le mode PDF
# ---------------------------------------------------------------------------


class VueModePdf(SurfaceDImage):
    """La page rasterisee sous ses surimpressions, et ce que la page dit.

    Ordre de haut en bas : controles de vue (**au-dessus** de la scene), la
    scene (``viewer-stage``, et **rien d'autre n'entre dans son cadre**),
    puis, HORS de l'image, les legendes de zones et l'etat de page.
    """

    zone_designee = Signal(tuple)

    def __init__(self, chaines, preference=None, fournisseur=None, parent=None):
        super().__init__(chaines, preference, fournisseur, parent=parent)
        self.setObjectName("vue-mode-pdf")
        self.page = None
        self.designation = None
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(0)
        colonne = QVBoxLayout()
        colonne.setContentsMargins(
            jetons.ESPACEMENTS["gutter"], jetons.ESPACEMENTS["gutter"],
            jetons.ESPACEMENTS["gutter"], jetons.ESPACEMENTS["gutter"],
        )
        colonne.setSpacing(jetons.ESPACEMENTS["5"])
        colonne.addWidget(self.barre_de_vue)
        self.scene = _surimpressions.ScenePlanche(self)
        self.brancher_la_barre_de_vue(self.scene)
        self.scene.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        colonne.addWidget(self.scene, 1)

        #: Les legendes de zones : **hors** du contenu d'image.
        self.legendes = QWidget(self)
        self.legendes.setObjectName("legendes-de-zones")
        self._legendes_ligne = QHBoxLayout(self.legendes)
        self._legendes_ligne.setContentsMargins(0, 0, 0, 0)
        self._legendes_ligne.setSpacing(jetons.ESPACEMENTS["gutter"])
        colonne.addWidget(self.legendes)

        self.verrous = BandeauDeVerrous(chaines, self)
        colonne.addWidget(self.verrous)
        self.etat_de_page = BandeauDEtatDePage(chaines, self)
        colonne.addWidget(self.etat_de_page)
        ligne.addLayout(colonne, 1)
        ligne.addWidget(self.panneau_lateral)
        self._apercu_indisponible = QLabel(chaines["scan-apercu-page-indisponible"], self)
        self._apercu_indisponible.setObjectName("apercu-indisponible")
        self._apercu_indisponible.setStyleSheet(
            f"color: {jetons.COULEURS['text-secondary']};"
        )
        colonne.addWidget(self._apercu_indisponible)
        self._apercu_indisponible.setVisible(False)

    def poser(self, page) -> None:
        """Poser la page a juger. **Aucune ecriture, aucune derivation.**"""
        self.page = page
        self.designation = None
        self.verrous.poser(page)
        self.etat_de_page.poser(page)
        self._poser_les_legendes(page)
        self.rafraichir()

    def rafraichir(self) -> None:
        if self.page is None:
            return
        image = self.image_de(self.page)
        self.scene.poser(self.page, image)
        self._apercu_indisponible.setVisible(image is None)

    @property
    def plan_de_surimpressions(self):
        """Le plan reellement pose sur l'image de cette vue."""
        return self.scene.contenu.plan

    def _poser_les_legendes(self, page) -> None:
        while self._legendes_ligne.count():
            element = self._legendes_ligne.takeAt(0)
            widget = element.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for zone in page.page.frame_zones:
            legende = LegendeDeZone(page, zone, self._chaines, self.legendes)
            legende.designee.connect(self.designer)
            self._legendes_ligne.addWidget(legende)
        self._legendes_ligne.addStretch(1)

    def designer(self, adresse) -> None:
        """Designer une zone. **Aucune poignee n'est instanciee** (7.5)."""
        self.designation = tuple(adresse)
        self.zone_designee.emit(self.designation)


# ---------------------------------------------------------------------------
# AC 4 -- la galerie
# ---------------------------------------------------------------------------


class CaseDEmplacement(QFrame):
    """Un emplacement de la grille : son etat, sa legende. **Aucune image.**

    « Aucune image de frame n'est fabriquee » : les images legeres de la
    detection sont une dependance nommee **non livree**, et recadrer le
    raster de page pour simuler une vignette creerait une **seconde source**
    pour la meme frame -- ce que le produit a refuse le 2026-08-17. Une case
    dont l'image n'existe pas affiche donc son etat et sa legende, et **rien
    qui ressemble a une image**.

    La case est ecrite pour accueillir cette image sans changer de forme le
    jour ou elle arrivera : la legende est deja **sous** la vignette, hors de
    l'image (``frame-thumb.caption-position``), et les bordures d'etat sont
    deja celles de ``frame-thumb``.
    """

    ouverte = Signal(tuple)

    def __init__(self, page, zone, chaines, parent=None):
        super().__init__(parent)
        self.setObjectName("case-emplacement")
        self.adresse = (page.page.read_rank, page.page.page_index, zone.slot_index)
        self.slot_index = zone.slot_index
        self.etat = etat_de_case(zone)
        self.jeton_bordure = JETON_COULEUR_PAR_CASE[self.etat]
        self.designee = False
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(jetons.ESPACEMENTS["2"])
        #: La vignette : un cadre a coins DROITS (`frame-thumb.radius` vaut
        #: `{rounded.none}`), vide tant que les images legeres n'existent pas.
        self.vignette = QFrame(self)
        self.vignette.setObjectName("vignette-emplacement")
        self.vignette.setMinimumSize(jetons.ESPACEMENTS["8"], jetons.ESPACEMENTS["8"])
        self.vignette.setStyleSheet(
            "#vignette-emplacement { border: 1px solid "
            f"{jetons.COULEURS[self.jeton_bordure]};"
            f" border-radius: {jetons.RAYON_CONTENU_IMAGE}px; }}"
        )
        colonne.addWidget(self.vignette, 1)
        cle_etat = CHAINE_PAR_CASE[self.etat]
        typo = jetons.TYPOGRAPHIE["data-sm"]
        self.legende = LegendeDeZone(page, zone, chaines, self)
        colonne.addWidget(self.legende)
        self.etat_libelle = QLabel(
            "" if cle_etat is None else chaines[cle_etat], self
        )
        self.etat_libelle.setObjectName("case-etat")
        # Le libelle d'etat porte la variante `-text` de la chromie de la
        # case quand elle en a une (plancher 4,5:1 en 11 px), le neutre
        # secondaire sinon : `border` n'est pas une chromie et n'a pas de
        # variante de texte.
        jeton_texte = (
            f"{self.jeton_bordure}-text"
            if f"{self.jeton_bordure}-text" in jetons.COULEURS
            else "text-secondary"
        )
        self.couleur_du_libelle = jetons.COULEURS[jeton_texte]
        self.etat_libelle.setStyleSheet(
            f"color: {self.couleur_du_libelle};"
            f" font-size: {typo['taille']}px;"
        )
        self.etat_libelle.setVisible(cle_etat is not None)
        colonne.addWidget(self.etat_libelle)
        self.couleurs_posees = (
            jetons.COULEURS[self.jeton_bordure],
            self.couleur_du_libelle,
        )
        self._effet_opacite = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effet_opacite)
        self._appliquer_l_opacite()

    def _appliquer_l_opacite(self) -> None:
        """`frame-thumb.opacity-deselected` : une case non designee s'efface.

        Elle s'EFFACE, elle ne disparait pas : 0,32 est lu du module de
        jetons, jamais ecrit ici.
        """
        self.opacite = (
            1.0 if self.designee else jetons.OPACITE_VIGNETTE_NON_DESIGNEE
        )
        self._effet_opacite.setOpacity(self.opacite)

    def designer(self, designee=True) -> None:
        self.designee = bool(designee)
        self._appliquer_l_opacite()

    def mousePressEvent(self, evenement):  # noqa: N802 -- nom impose par Qt
        """Un clic ouvre la vue vignette unique sur CETTE frame."""
        self.ouverte.emit(self.adresse)
        super().mousePressEvent(evenement)


class CaseDePageManquante(QFrame):
    """Le trou d'une planche absente : il **garde sa place** dans la grille."""

    def __init__(self, page_index, chaines, parent=None):
        super().__init__(parent)
        self.setObjectName("case-page-manquante")
        self.page_index = page_index
        self.etat = CASE_ABSENTE
        self.jeton_bordure = JETON_COULEUR_PAR_CASE[CASE_ABSENTE]
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        libelle = QLabel(
            chaines["scan-galerie-page-manquante"].format(planche=page_index), self
        )
        libelle.setWordWrap(True)
        libelle.setStyleSheet(
            f"color: {jetons.COULEURS['state-absent-text']};"
            f" font-size: {jetons.TYPOGRAPHIE['data-sm']['taille']}px;"
        )
        colonne.addWidget(libelle)
        self.setStyleSheet(
            "#case-page-manquante { border: 1px solid "
            f"{jetons.COULEURS[self.jeton_bordure]};"
            f" border-radius: {jetons.RAYON_CONTENU_IMAGE}px; }}"
        )
        self.couleurs_posees = (
            jetons.COULEURS[self.jeton_bordure],
            jetons.COULEURS["state-absent-text"],
        )


class LigneDePageDeGalerie(QFrame):
    """Une planche de la galerie : son apercu de PAGE, puis ses emplacements.

    L'apercu est celui de la **page entiere**, tel que le scan l'a lue -- ce
    n'est ni une image de frame fabriquee, ni un recadrage du raster : c'est
    la page, en entier, la seule image que le document designe. C'est par lui
    que la galerie respecte la bascule brut / corrige (AC 8), et c'est ce qui
    permet de mesurer que cette bascule est **globale** sur deux surfaces.
    """

    case_ouverte = Signal(tuple)

    def __init__(self, page, chaines, parent=None):
        super().__init__(parent)
        self.setObjectName("ligne-page-galerie")
        self.page = page
        self._chaines = chaines
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(jetons.ESPACEMENTS["3"])
        entete = QHBoxLayout()
        entete.setSpacing(jetons.ESPACEMENTS["5"])
        index = page.page.page_index
        titre = (
            chaines["scan-galerie-planche"].format(planche=index)
            if index is not None
            else chaines["scan-galerie-planche-inconnue"].format(
                rang=page.page.read_rank
            )
        )
        self.titre = QLabel(titre, self)
        self.titre.setStyleSheet(
            f"color: {jetons.COULEURS['text-primary']};"
            f" font-size: {jetons.TYPOGRAPHIE['label']['taille']}px;"
        )
        entete.addWidget(self.titre)
        #: FAMILLE 2 -- le rattachement. Une planche dont le QR n'a pas livre
        #: son index n'est rattachee a rien : elle porte le GLYPHE, jamais un
        #: badge de completude, qui repond a une autre question.
        self.glyphe = None
        if index is None:
            self.glyphe = _chutier.GlypheDeRattachement(
                _modele.GLYPHE_NON_RATTACHE, chaines, self
            )
            entete.addWidget(self.glyphe)
        entete.addStretch(1)
        colonne.addLayout(entete)

        self.apercu = _surimpressions.ScenePlanche(self)
        #: Hauteur d'apercu a 100 %. Gardee nommee parce que le zoom de
        #: vignettes la MULTIPLIE : sans reference conservee, un zoom applique
        #: deux fois de suite composerait au lieu de remplacer, et redescendre
        #: a 100 % ne rendrait plus la taille de depart.
        # Six fois `8` et non deux (correctif du 2026-08-26) : a 64 px de
        # haut, l'apercu d'une planche A4 faisait 45 px de large -- on n'y
        # distinguait ni les zones proposees ni les marqueurs, c'est-a-dire
        # rien de ce que la galerie existe pour montrer. Mesure sur capture.
        self.hauteur_apercu_de_reference = jetons.ESPACEMENTS["8"] * 6
        self.apercu.setMinimumHeight(self.hauteur_apercu_de_reference)
        colonne.addWidget(self.apercu)

        self.cases: list[CaseDEmplacement] = []
        grille_widget = QWidget(self)
        grille_widget.setObjectName("grille-emplacements")
        self.grille = QGridLayout(grille_widget)
        self.grille.setContentsMargins(0, 0, 0, 0)
        self.grille.setSpacing(jetons.ESPACEMENTS["gutter"])
        for colonne_indice, zone in enumerate(page.page.frame_zones):
            case = CaseDEmplacement(page, zone, chaines, grille_widget)
            case.ouverte.connect(self.case_ouverte.emit)
            self.grille.addWidget(case, 0, colonne_indice)
            self.cases.append(case)
        colonne.addWidget(grille_widget)
        self.couleurs_posees = (jetons.COULEURS["text-primary"],)

    def poser_image(self, image) -> None:
        self.apercu.poser(self.page, image)


class VueGalerie(SurfaceDImage):
    """Les pages du lot et leurs trous. **Aucune image de frame fabriquee.**"""

    case_ouverte = Signal(tuple)

    def __init__(self, chaines, preference=None, fournisseur=None, parent=None):
        super().__init__(chaines, preference, fournisseur, parent=parent)
        self.setObjectName("vue-galerie")
        self.document = None
        self.lignes: list[LigneDePageDeGalerie] = []
        self.trous: list[CaseDePageManquante] = []
        ligne_h = QHBoxLayout(self)
        ligne_h.setContentsMargins(0, 0, 0, 0)
        ligne_h.setSpacing(0)
        colonne = QVBoxLayout()
        colonne.setContentsMargins(
            jetons.ESPACEMENTS["gutter"], jetons.ESPACEMENTS["gutter"],
            jetons.ESPACEMENTS["gutter"], jetons.ESPACEMENTS["gutter"],
        )
        colonne.setSpacing(jetons.ESPACEMENTS["5"])
        entete = QHBoxLayout()
        entete.setSpacing(jetons.ESPACEMENTS["5"])
        entete.addWidget(self.barre_de_vue, 1)
        #: Le zoom de VIGNETTES, continu et sans paliers, **au-dessus** de la
        #: scene (`EXPERIENCE.md`, Interaction Primitives).
        self.zoom_vignettes = QSlider(Qt.Orientation.Horizontal, self)
        self.zoom_vignettes.setObjectName("zoom-vignettes")
        self.zoom_vignettes.setRange(
            _barre.ZOOM_MIN_POURCENT, _barre.ZOOM_MAX_POURCENT
        )
        self.zoom_vignettes.setValue(_barre.ZOOM_DEFAUT_POURCENT)
        self.zoom_vignettes.setSingleStep(1)
        self.zoom_vignettes.setPageStep(1)
        self.zoom_vignettes.setTickPosition(QSlider.TickPosition.NoTicks)
        self.zoom_vignettes.setToolTip(chaines["scan-galerie-zoom"])
        self.zoom_vignettes.setAccessibleName(chaines["scan-galerie-zoom"])
        # **Il n'etait relie a rien** jusqu'au 2026-08-26 : le curseur glissait
        # et aucune vignette ne changeait de taille. Meme defaut, meme jour,
        # que le zoom de la vue page -- un signal emis que personne n'ecoute.
        self.zoom_vignettes.valueChanged.connect(self.definir_zoom_vignettes)
        entete.addWidget(self.zoom_vignettes)
        self.badge = None
        self._entete = entete
        colonne.addLayout(entete)

        self.defilement = QScrollArea(self)
        self.defilement.setWidgetResizable(True)
        self.contenu_defilant = QWidget()
        self.colonne_pages = QVBoxLayout(self.contenu_defilant)
        self.colonne_pages.setContentsMargins(0, 0, 0, 0)
        self.colonne_pages.setSpacing(jetons.ESPACEMENTS["7"])
        self.defilement.setWidget(self.contenu_defilant)
        colonne.addWidget(self.defilement, 1)
        ligne_h.addLayout(colonne, 1)
        ligne_h.addWidget(self.panneau_lateral)

    def definir_zoom_vignettes(self, pourcent) -> None:
        """Mettre les apercus de planche a l'echelle demandee.

        La galerie montre des PAGES entieres, pas des frames recadrees (aucune
        vignette de frame n'existe avant la story 7.6) : ce zoom-ci agit donc
        sur la hauteur des apercus, et c'est bien « la taille des vignettes »
        au sens ou l'operatrice le demande -- voir plus grand ce qu'elle juge.

        Chaque hauteur est recalculee depuis sa REFERENCE et non depuis sa
        valeur courante : multiplier la valeur courante composerait les zooms
        successifs, et redescendre a 100 % ne rendrait pas la taille de depart.
        """
        facteur = max(1, int(pourcent)) / 100.0
        for ligne in self.lignes:
            ligne.apercu.setMinimumHeight(
                int(ligne.hauteur_apercu_de_reference * facteur)
            )

    def poser(self, document) -> None:
        """Poser le document. **L'ordre rendu est celui du document.**"""
        self.document = document
        for ancien in self.lignes + self.trous:
            ancien.setParent(None)
            ancien.deleteLater()
        self.lignes = []
        self.trous = []
        while self.colonne_pages.count():
            element = self.colonne_pages.takeAt(0)
            widget = element.widget()
            if widget is not None:
                widget.setParent(None)
        if self.badge is not None:
            self.badge.setParent(None)
            self.badge.deleteLater()
        self.badge = _chutier.BadgeDeCompletude(
            badge_de_completude_des_planches(document), self._chaines,
            parent=self
        )
        self._entete.insertWidget(0, self.badge)
        for page, trou in rangs_et_trous(document):
            if page is not None:
                ligne = LigneDePageDeGalerie(page, self._chaines, self.contenu_defilant)
                ligne.case_ouverte.connect(self.case_ouverte.emit)
                self.colonne_pages.addWidget(ligne)
                self.lignes.append(ligne)
            else:
                case = CaseDePageManquante(trou, self._chaines, self.contenu_defilant)
                self.colonne_pages.addWidget(case)
                self.trous.append(case)
        self.colonne_pages.addStretch(1)
        # Le zoom courant s'applique aux lignes qui viennent d'etre posees :
        # changer de lot ne doit pas ramener sournoisement les apercus a 100 %
        # pendant que le curseur, lui, reste ou l'operatrice l'a laisse.
        self.definir_zoom_vignettes(self.zoom_vignettes.value())
        self.rafraichir()

    def rafraichir(self) -> None:
        for ligne in self.lignes:
            ligne.poser_image(self.image_de(ligne.page))

    @property
    def suite_rendue(self) -> tuple:
        """Ce que la galerie rend, dans l'ordre : pages presentes et trous.

        Publie pour le banc : c'est ce qui permet de mesurer que le trou est
        **a sa place** et que les suivantes ne sont pas decalees.
        """
        rendus = []
        for indice in range(self.colonne_pages.count()):
            widget = self.colonne_pages.itemAt(indice).widget()
            if isinstance(widget, LigneDePageDeGalerie):
                rendus.append(("page", widget.page.adresse))
            elif isinstance(widget, CaseDePageManquante):
                rendus.append(("trou", widget.page_index))
        return tuple(rendus)


# ---------------------------------------------------------------------------
# AC 6 -- la vue vignette unique
# ---------------------------------------------------------------------------


class VueVignetteUnique(SurfaceDImage):
    """La frame seule, plein panneau, zoom dedans (``EPIC7-ARB-18``).

    « C'est une vue a part entiere, la troisieme apres la galerie et le
    lecteur, et non un agrandissement de la grille. » Son panneau lateral
    **s'ouvre deja retracte** : cette vue n'a rien a y mettre
    (``EPIC7-ARB-25``), et l'etat retracte lui appartient -- revenir a la
    galerie puis rouvrir une autre frame ne change pas l'etat de la galerie.
    """

    def __init__(self, chaines, preference=None, fournisseur=None, parent=None):
        # Le panneau s'ouvre RETRACTE : c'est le defaut de cette vue-la.
        super().__init__(
            chaines, preference, fournisseur, panneau_retracte=True, parent=parent
        )
        self.setObjectName("vue-vignette-unique")
        self.adresse = None
        self.page = None
        self.zone = None
        ligne = QHBoxLayout(self)
        ligne.setContentsMargins(0, 0, 0, 0)
        ligne.setSpacing(0)
        colonne = QVBoxLayout()
        colonne.setContentsMargins(
            jetons.ESPACEMENTS["gutter"], jetons.ESPACEMENTS["gutter"],
            jetons.ESPACEMENTS["gutter"], jetons.ESPACEMENTS["gutter"],
        )
        colonne.setSpacing(jetons.ESPACEMENTS["5"])
        self.titre = QLabel(self)
        self.titre.setObjectName("titre-vignette-unique")
        self.titre.setStyleSheet(
            f"color: {jetons.COULEURS['text-primary']};"
            f" font-size: {jetons.TYPOGRAPHIE['title']['taille']}px;"
        )
        colonne.addWidget(self.titre)
        colonne.addWidget(self.barre_de_vue)
        self.scene = _surimpressions.ScenePlanche(self)
        self.brancher_la_barre_de_vue(self.scene)
        self.scene.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        colonne.addWidget(self.scene, 1)
        self.legende = None
        self._colonne = colonne
        ligne.addLayout(colonne, 1)
        ligne.addWidget(self.panneau_lateral)
        self.couleurs_posees = (jetons.COULEURS["text-primary"],)

    def poser(self, page, zone) -> None:
        self.page = page
        self.zone = zone
        self.adresse = (page.page.read_rank, page.page.page_index, zone.slot_index)
        self.titre.setText(
            self._chaines["scan-frame-titre"].format(
                slot=zone.slot_index,
                planche=page.page.page_index
                if page.page.page_index is not None
                else page.page.read_rank,
            )
        )
        if self.legende is not None:
            self.legende.setParent(None)
            self.legende.deleteLater()
        # La legende reste SOUS l'image, hors du contenu, et **hors du
        # panneau lateral** : les deux interdits d'EPIC7-ARB-22 et du Don't
        # « Incruster une valeur sur l'image » se croisent ici aussi.
        self.legende = LegendeDeZone(page, zone, self._chaines, self)
        self._colonne.addWidget(self.legende)
        self.rafraichir()

    def rafraichir(self) -> None:
        if self.page is None:
            return
        self.scene.poser(self.page, self.image_de(self.page))


# ---------------------------------------------------------------------------
# L'atelier : les trois vues, les onglets, un document
# ---------------------------------------------------------------------------


class AtelierScanJugement(QWidget):
    """Le second point de jugement du chemin du scan, en trois vues.

    Onglets de cette story : ``page`` et ``galerie``, plus ``frame`` **la ou
    la vue vignette unique a un objet**. L'onglet ``lecteur`` n'existe pas
    ici : c'est 7.6. Un onglet sans objet est ABSENT, un controle
    temporairement indisponible est GRISE (``EPIC7-ARB-24``).
    """

    def __init__(self, chaines, preference=None, fournisseur=None, parent=None):
        super().__init__(parent)
        self.setObjectName("atelier-scan-jugement")
        self._chaines = chaines
        self.document = None
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(0, 0, 0, 0)
        colonne.setSpacing(0)
        self.onglets = _barre.OngletsDeVue(chaines, self)
        # Cette barre porte deux ou trois onglets, jamais plus : elle ne
        # defile pas. Qt lui pose pourtant deux boutons de defilement dont il
        # nomme l'accessibilite en ANGLAIS (« Scroll Left », « Scroll
        # Right ») -- des chaines qui n'existent dans aucun catalogue et que
        # l'anglais hors v1 (`EPIC7-ARB-52`) interdit dans la fenetre. On les
        # eteint et on efface leur nom : un controle masque et sans fonction
        # n'a rien a nommer, et la coquille cesse de porter du texte qu'aucune
        # substitution de catalogue n'atteint.
        self.onglets.setUsesScrollButtons(False)
        for bouton in self.onglets.findChildren(QToolButton):
            bouton.setAccessibleName("")
            bouton.setToolTip("")
        colonne.addWidget(self.onglets)
        self.pile = QStackedWidget(self)
        self.vue_page = VueModePdf(chaines, preference, fournisseur, self)
        self.vue_galerie = VueGalerie(chaines, preference, fournisseur, self)
        self.vue_frame = VueVignetteUnique(chaines, preference, fournisseur, self)
        for vue in (self.vue_page, self.vue_galerie, self.vue_frame):
            self.pile.addWidget(vue)
        colonne.addWidget(self.pile, 1)
        self.onglets.vue_changee.connect(self._activer)
        self.vue_galerie.case_ouverte.connect(self.ouvrir_la_frame)

    @property
    def vues(self) -> dict:
        return {
            _barre.ONGLET_PAGE: self.vue_page,
            _barre.ONGLET_GALERIE: self.vue_galerie,
            _barre.ONGLET_FRAME: self.vue_frame,
        }

    def poser_document(self, document, page_visee=None) -> None:
        """Poser un document de detection. **Rien n'est ecrit nulle part.**"""
        self.document = document
        self.vue_galerie.poser(document)
        page = page_visee if page_visee is not None else document.pages[0]
        self.vue_page.poser(page)
        # Changer de lot referme la vue vignette unique : son objet a disparu,
        # donc son onglet aussi -- absent, jamais grise.
        self.vue_frame.adresse = None
        self.onglets.poser_onglets((_barre.ONGLET_PAGE, _barre.ONGLET_GALERIE))
        self._activer(self.onglets.vue_courante())

    def poser_fournisseur(self, fournisseur) -> None:
        for vue in self.vues.values():
            vue.poser_fournisseur(fournisseur)

    def ouvrir_la_frame(self, adresse) -> None:
        """Ouvrir la vue vignette unique sur cette frame, et lui donner son onglet."""
        read_rank, page_index, slot_index = adresse
        page = self.document.page_par_adresse(read_rank, page_index)
        self.vue_frame.poser(page, page.zone(slot_index))
        self.onglets.poser_onglets(
            (_barre.ONGLET_PAGE, _barre.ONGLET_GALERIE, _barre.ONGLET_FRAME)
        )
        self.onglets.activer(_barre.ONGLET_FRAME)

    def _activer(self, cle) -> None:
        if cle is None:
            return
        self.pile.setCurrentWidget(self.vues[cle])


__all__ = [
    "AtelierScanJugement",
    "BandeauDEtatDePage",
    "BandeauDeVerrous",
    "CASE_ABSENTE",
    "CASE_MIRE",
    "CASE_PRESENTE",
    "CaseDEmplacement",
    "CaseDePageManquante",
    "IndicateurDeVerrou",
    "JETON_COULEUR_PAR_CASE",
    "JETON_COULEUR_PAR_VERROU",
    "LegendeDeZone",
    "LigneDePageDeGalerie",
    "PanneauLateralDeVue",
    "SurfaceDImage",
    "VueGalerie",
    "VueModePdf",
    "VueVignetteUnique",
    "badge_de_completude_des_planches",
    "etat_de_case",
    "planches_manquantes",
    "rangs_et_trous",
]
