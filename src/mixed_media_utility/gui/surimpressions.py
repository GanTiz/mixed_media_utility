# -*- coding: utf-8 -*-
"""Surimpressions de scan et contenu d'image (story 7.4, AC 1 et AC 6).

Deux choses vivent ici, et la separation entre les deux est le coeur du
banc :

1. **le PLAN de surimpression** -- :func:`plan_de_surimpressions`, fonction
   PURE qui traduit une page du document en une liste de traits nommes. Il
   est mesurable sans peindre quoi que ce soit, ce qui compte sous
   ``offscreen`` ou certaines interactions Qt de haut niveau sont inertes ;
2. **le rendu** -- :class:`ContenuDImage`, qui peint le raster puis ce plan,
   et rien d'autre. La capture de reference (AC 7) est ce qui prouve que le
   plan est reellement peint et pas seulement calcule.

**Trois familles de traits, trois provenances distinctes, aucune calculee
ici** (``DESIGN.md``, « Surimpressions de scan (mode PDF) ») :

* les **zones proposees** (``frame_zones``), rectangle lu des ``crop_*_px``,
  en ``{colors.accent}`` ;
* les **marqueurs ArUco decodes** (``corner_markers``), a leur centre lu, en
  ``{colors.state-complete}`` ;
* la **zone du QR quand il n'est pas decode**, en
  ``{colors.state-substitute}``.

**Etat mesure du depot sur cette troisieme famille, et il est nomme parce
qu'il change ce que la story livre** : le document de detection ne porte
**aucun rectangle de QR**. ``scan_detection._page_geometry`` ne projette en
pixels que ``spec.frame_zones_mm`` -- les zones d'image --, et la zone de QR
du gabarit (``page_templates.TemplateGrid.qr_zone_mm``) ne descend jamais
jusqu'au document. En fabriquer un ici demanderait une conversion mm -> px et
une homographie, c'est-a-dire exactement les deux interdits mesures de l'AC 1
(« la GUI ne fabrique aucune position de zone ») et de l'AC 3 (« zero
arithmetique de conversion mm -> px, zero constante de dpi »).

La famille est donc implementee **et conditionnee au document** : elle rend
un trait si et seulement si le document porte une zone nommee
:data:`NOM_DE_ZONE_QR`, ce que le producteur d'aujourd'hui n'ecrit jamais.
La GUI n'invente pas ce rectangle ; elle sait l'honorer le jour ou le coeur
l'emettra. Quand le QR n'est pas decode et qu'aucun rectangle n'existe, le
fait est dit comme **etat de page** -- verrou d'identite et motif de
non-proposition (AC 2) --, jamais comme un dessin pose au hasard.

**Aucune valeur n'est incrustee sur l'image** (``EPIC7-ARB-68``, verbatim :
« Aucune valeur -- taille, timecode, rang -- n'est posee en surimpression
permanente sur une image de frame. ») : ce module peint des traits, jamais
du texte.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from . import jetons

#: Les trois familles de traits. Ce sont des noms, pas des couleurs : la
#: couleur se lit dans :data:`JETON_COULEUR_PAR_FAMILLE`, et jamais en dur.
FAMILLE_ZONE = "zone-proposee"
FAMILLE_MARQUEUR = "marqueur-decode"
FAMILLE_QR_NON_DECODE = "qr-non-decode"

FAMILLES: tuple[str, ...] = (FAMILLE_ZONE, FAMILLE_MARQUEUR, FAMILLE_QR_NON_DECODE)

#: NOM de jeton par famille -- jamais une valeur hexadecimale.
JETON_COULEUR_PAR_FAMILLE = {
    FAMILLE_ZONE: "accent",
    FAMILLE_MARQUEUR: "state-complete",
    FAMILLE_QR_NON_DECODE: "state-substitute",
}

#: Nom de zone sous lequel un rectangle de QR serait porte par le document.
#: C'est le nom que le coeur emploie deja pour cette zone dans ses gabarits
#: (``patch_presets``, entrees ``{"name": "qr_zone", ...}``) -- recopier un
#: autre nom ferait diverger la GUI du coeur sur un identifiant, defaut deja
#: paye dans ce depot (`LOT_INCOMPLET` cote maquette contre `LOT_INCOMPLETE`
#: cote coeur).
NOM_DE_ZONE_QR = "qr_zone"


@dataclass(frozen=True)
class Trait:
    """Un trait a poser sur l'image : sa famille, son identite, sa geometrie.

    ``rectangle_px`` et ``centre_px`` sont exclusifs : un rectangle pour une
    zone, un centre pour un marqueur. Les coordonnees sont celles du
    DOCUMENT, en pixels de page redressee, jamais retouchees ici.
    """

    famille: str
    identifiant: object
    jeton_couleur: str
    rectangle_px: tuple[int, int, int, int] | None = None
    centre_px: tuple[float, float] | None = None


def plan_de_surimpressions(page) -> tuple[Trait, ...]:
    """Traduire une page lue en liste de traits. **Fonction pure.**

    Rien n'est calcule : chaque coordonnee est recopiee d'un champ du
    document. Une page refusee -- sans zone, sans marqueur -- rend un plan
    **vide**, et c'est le resultat juste : il n'existe aucune position
    attendue sans homographie, et en dessiner une donnerait une geometrie
    fausse d'apparence valide.
    """
    traits: list[Trait] = []
    for zone in page.page.frame_zones:
        famille = (
            FAMILLE_QR_NON_DECODE
            if zone.zone_name == NOM_DE_ZONE_QR
            else FAMILLE_ZONE
        )
        if famille is FAMILLE_QR_NON_DECODE and not _qr_non_decode(page):
            # Un rectangle de QR sur une planche dont le QR a ete lu n'est pas
            # un etat a signaler : le State Pattern ne vise que le NON decode.
            continue
        traits.append(
            Trait(
                famille=famille,
                identifiant=zone.slot_index,
                jeton_couleur=JETON_COULEUR_PAR_FAMILLE[famille],
                rectangle_px=(
                    zone.crop_x_px, zone.crop_y_px, zone.crop_w_px, zone.crop_h_px
                ),
            )
        )
    for marqueur in page.page.corner_markers:
        traits.append(
            Trait(
                famille=FAMILLE_MARQUEUR,
                identifiant=marqueur.marker_id,
                jeton_couleur=JETON_COULEUR_PAR_FAMILLE[FAMILLE_MARQUEUR],
                centre_px=(marqueur.center_x_px, marqueur.center_y_px),
            )
        )
    return tuple(traits)


def _qr_non_decode(page) -> bool:
    """Le QR de cette page n'a-t-il rien livre ?

    Lu du champ ferme ``qr_status``, **jamais** de la phrase de refus. Import
    local : ce module de dessin n'a pas a dependre du module de lecture pour
    le reste de son travail.
    """
    from .. import qr_codes

    return page.page.qr_status != qr_codes.DECODE_OK


class ContenuDImage(QWidget):
    """Le contenu d'image : le raster, puis les traits. **Coins droits.**

    ``DESIGN.md``, Layout & Spacing : « L'exception : ``{rounded.none}`` sur
    tout contenu d'image. Le cadre autour de l'image peut etre arrondi ;
    l'image, jamais. » Ce widget n'a donc aucun rayon, et **aucun enfant** --
    ce qui rend structurellement impossible qu'un descendant en porte un, ou
    qu'une valeur vienne s'incruster dessus.

    **Repere de coordonnees, et c'est une decision a lire.** Les
    surimpressions sont en pixels de page REDRESSEE (``page_size_px``) tandis
    que le raster est la page SOURCE, non redressee. Redresser demanderait
    d'appliquer l'homographie, ce que cette story s'interdit formellement.
    Le raster est donc presente **dans le repere des surimpressions**, mis a
    l'echelle uniformement : c'est une mise en page, pas une rectification --
    aucune valeur du document n'est retouchee, et la capture de reference
    (AC 7) fige exactement ce que l'operateur voit.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("contenu-image")
        #: Rayon du contenu d'image : nul, toujours, lu du module de jetons.
        self.rayon = jetons.RAYON_CONTENU_IMAGE
        #: Couleurs REELLEMENT posees par ce widget, pour le banc (J) de la
        #: bande `mat-min`. Le contenu d'image porte des chromies -- c'est la
        #: seule exception admise --, et il les declare.
        self.couleurs_posees = tuple(
            jetons.COULEURS[nom]
            for nom in (
                *sorted(set(JETON_COULEUR_PAR_FAMILLE.values())),
                "overlay-halo",
            )
        )
        self.page = None
        self.image = None
        self.plan = ()
        self._repere_px = (1, 1)
        #: Facteur de zoom, 1.0 = « ajuste a la scene ». Jusqu'au 2026-08-26 il
        #: n'existait pas : `BarreDeVue.zoom_change` etait emis et **consomme
        #: par personne**, si bien que le curseur de zoom bougeait sans que
        #: rien ne change a l'ecran (« le zoom sur la page pdf n'est absolument
        #: pas fonctionnel », Egan).
        self._zoom = 1.0
        #: Deplacement de l'image dans la scene, en pixels du widget. Un zoom
        #: sans deplacement ne sert a rien : agrandir pour ne plus pouvoir
        #: atteindre le coin qu'on voulait regarder, c'est pire que ne pas
        #: agrandir.
        self._decalage = QPointF(0.0, 0.0)
        self._prise = None

    def poser(self, page, image: QImage | None = None) -> None:
        """Poser une page et son raster. Le plan en decoule, il n'est pas donne."""
        self.page = page
        self.image = image
        self.plan = plan_de_surimpressions(page) if page is not None else ()
        self._repere_px = self._repere_de_page(page, image)
        self.update()

    @staticmethod
    def _repere_de_page(page, image):
        """Le rectangle de reference, en pixels, dans lequel tout est place.

        ``page_size_px`` fait foi quand le document le porte : c'est le
        repere DES SURIMPRESSIONS, et les faire vivre dans un autre les
        decalerait. A defaut -- page refusee, geometrie non resolue -- on
        prend la taille de la source, qui est ce que le document dit de
        l'image elle-meme.
        """
        if page is None:
            return (1, 1)
        if page.page.page_size_px:
            largeur, hauteur = page.page.page_size_px[0], page.page.page_size_px[1]
        else:
            largeur, hauteur = page.page.width_px, page.page.height_px
        if image is not None and (largeur <= 0 or hauteur <= 0):
            largeur, hauteur = image.width(), image.height()
        return (max(int(largeur), 1), max(int(hauteur), 1))

    @property
    def repere_px(self) -> tuple[int, int]:
        """Le repere de coordonnees courant, en pixels de document."""
        return self._repere_px

    # --- zoom et deplacement ---------------------------------------------

    @property
    def zoom(self) -> float:
        """Le facteur courant. 1.0 = ajuste a la scene, 2.0 = deux fois plus."""
        return self._zoom

    def echelle_ajustee(self) -> float:
        """Le facteur qui fait tenir la page ENTIERE dans la scene.

        C'est la reference de tous les autres : « ajuster » y revient, et le
        zoom la multiplie. La calculer a part plutot que de l'enfouir dans
        `rectangle_de_reference` est ce qui permet a « taille reelle » de
        signifier *un pixel de document pour un pixel d'ecran* -- soit un zoom
        de `1 / echelle_ajustee`.
        """
        largeur_px, hauteur_px = self._repere_px
        disponible = self.rect()
        if disponible.width() <= 0 or disponible.height() <= 0:
            return 0.0
        return min(disponible.width() / largeur_px, disponible.height() / hauteur_px)

    def definir_zoom(self, facteur: float) -> None:
        """Poser le facteur de zoom. Un facteur nul ou negatif est ignore."""
        if facteur is None or facteur <= 0:
            return
        self._zoom = float(facteur)
        self._borner_le_decalage()
        self.update()

    def definir_zoom_pourcent(self, pourcent) -> None:
        """Poser le zoom depuis le curseur, qui parle en pourcents."""
        self.definir_zoom(float(pourcent) / 100.0)

    def ajuster(self) -> None:
        """Revenir a la page entiere, recentree."""
        self._zoom = 1.0
        self._decalage = QPointF(0.0, 0.0)
        self.update()

    def cadrer_sur_la_largeur(self) -> None:
        """Remplir la largeur de la scene, quitte a deborder en hauteur."""
        self._cadrer(horizontal=True)

    def cadrer_sur_la_hauteur(self) -> None:
        """Remplir la hauteur de la scene, quitte a deborder en largeur."""
        self._cadrer(horizontal=False)

    def _cadrer(self, *, horizontal: bool) -> None:
        largeur_px, hauteur_px = self._repere_px
        disponible = self.rect()
        ajustee = self.echelle_ajustee()
        if ajustee <= 0:
            return
        vise = (
            disponible.width() / largeur_px
            if horizontal
            else disponible.height() / hauteur_px
        )
        self._zoom = vise / ajustee
        self._decalage = QPointF(0.0, 0.0)
        self.update()

    def taille_reelle(self) -> None:
        """Un pixel de document pour un pixel d'ecran."""
        ajustee = self.echelle_ajustee()
        if ajustee <= 0:
            return
        self._zoom = 1.0 / ajustee
        self._decalage = QPointF(0.0, 0.0)
        self.update()

    def _borner_le_decalage(self) -> None:
        """Interdire de pousser l'image entierement hors de la scene.

        Sans cette borne, un deplacement continu finit sur un mat vide et
        l'operatrice n'a aucun moyen de savoir dans quelle direction ramener
        l'image. On garde donc toujours l'image accrochee a la scene : quand
        elle est plus petite que la scene elle reste centree (decalage nul),
        quand elle est plus grande elle ne peut pas se decoller d'un bord.
        """
        largeur_px, hauteur_px = self._repere_px
        disponible = self.rect()
        echelle = self.echelle_ajustee() * self._zoom
        debord_x = max(0.0, largeur_px * echelle - disponible.width()) / 2.0
        debord_y = max(0.0, hauteur_px * echelle - disponible.height()) / 2.0
        self._decalage = QPointF(
            max(-debord_x, min(debord_x, self._decalage.x())),
            max(-debord_y, min(debord_y, self._decalage.y())),
        )

    def rectangle_de_reference(self) -> QRectF:
        """Ou le repere de page atterrit dans ce widget, a l'echelle.

        Mise a l'echelle **uniforme et centree** : une echelle non uniforme
        deformerait les zones proposees, donc mentirait sur ce qui sera
        decoupe. Le zoom multiplie cette echelle et le deplacement translate
        le resultat -- les deux restent uniformes, donc les surimpressions
        suivent l'image exactement, ce que `rectangle_du_trait` obtient
        gratuitement en partant d'ici.
        """
        largeur_px, hauteur_px = self._repere_px
        disponible = self.rect()
        echelle = self.echelle_ajustee() * self._zoom
        if echelle <= 0:
            return QRectF(0.0, 0.0, 0.0, 0.0)
        largeur = largeur_px * echelle
        hauteur = hauteur_px * echelle
        return QRectF(
            disponible.x() + (disponible.width() - largeur) / 2.0 + self._decalage.x(),
            disponible.y() + (disponible.height() - hauteur) / 2.0 + self._decalage.y(),
            largeur,
            hauteur,
        )

    # --- deplacement a la souris ------------------------------------------

    def mousePressEvent(self, evenement):  # noqa: N802 -- nom impose par Qt
        # Seul le bouton GAUCHE saisit, et seulement quand il y a quelque
        # chose a atteindre : sur une page entierement visible, un cliquer
        # deplacer ne ferait que decentrer l'image sans rien reveler.
        if evenement.button() == Qt.MouseButton.LeftButton and self._depasse():
            self._prise = evenement.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(evenement)

    def mouseMoveEvent(self, evenement):  # noqa: N802 -- nom impose par Qt
        if self._prise is not None:
            position = evenement.position()
            self._decalage += position - self._prise
            self._prise = position
            self._borner_le_decalage()
            self.update()
        super().mouseMoveEvent(evenement)

    def mouseReleaseEvent(self, evenement):  # noqa: N802 -- nom impose par Qt
        if self._prise is not None:
            self._prise = None
            self.unsetCursor()
        super().mouseReleaseEvent(evenement)

    def _depasse(self) -> bool:
        """Vrai quand l'image deborde de la scene, donc qu'il y a a explorer."""
        reference = self.rectangle_de_reference()
        disponible = self.rect()
        return (
            reference.width() > disponible.width() + 1
            or reference.height() > disponible.height() + 1
        )

    def rectangle_du_trait(self, trait: Trait) -> QRectF:
        """La geometrie d'un trait, en coordonnees de ce widget.

        Publie pour le banc : c'est ce qui permet d'assert que la vue rend
        les rectangles de CETTE page et aucun de l'autre, nominativement.
        """
        reference = self.rectangle_de_reference()
        largeur_px, hauteur_px = self._repere_px
        facteur_x = reference.width() / largeur_px
        facteur_y = reference.height() / hauteur_px
        if trait.rectangle_px is not None:
            x, y, largeur, hauteur = trait.rectangle_px
            return QRectF(
                reference.x() + x * facteur_x,
                reference.y() + y * facteur_y,
                largeur * facteur_x,
                hauteur * facteur_y,
            )
        centre_x, centre_y = trait.centre_px
        # La marque d'un marqueur est un carre a la taille de boite d'un
        # pictogramme (`jetons.ICONOGRAPHIE`), centre sur le centre LU. Sa
        # taille est du chrome, pas de la geometrie de page : elle ne varie
        # donc pas avec le zoom du document.
        cote = jetons.ICONOGRAPHIE["boite-px"]
        return QRectF(
            reference.x() + centre_x * facteur_x - cote / 2.0,
            reference.y() + centre_y * facteur_y - cote / 2.0,
            cote,
            cote,
        )

    def paintEvent(self, evenement):  # noqa: N802 -- nom impose par Qt
        """Peindre le raster puis les traits a halo, sans remplissage."""
        peintre = QPainter(self)
        peintre.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        reference = self.rectangle_de_reference()
        if self.image is not None and not self.image.isNull():
            peintre.drawImage(reference, self.image)
        else:
            # Pas d'image : le fond du contenu est le PAPIER, neutre pur, et
            # rien qui ressemble a une image n'est fabrique.
            peintre.fillRect(reference, QColor(jetons.COULEURS["paper"]))
        halo = QColor(jetons.COULEURS["overlay-halo"])
        largeur_halo = jetons.SURIMPRESSIONS["halo-px"]
        largeur_trait = jetons.SURIMPRESSIONS["trait-px"]
        for trait in self.plan:
            rectangle = self.rectangle_du_trait(trait)
            # Le HALO passe dessous, le trait dessus : c'est ce qui rend la
            # surimpression lisible sur une marge blanche comme sur une zone
            # peinte a la gouache.
            peintre.setBrush(Qt.BrushStyle.NoBrush)   # `fill: none`, jamais un aplat
            peintre.setPen(QPen(halo, largeur_halo))
            peintre.drawRect(rectangle)
            peintre.setPen(
                QPen(QColor(jetons.COULEURS[trait.jeton_couleur]), largeur_trait)
            )
            peintre.drawRect(rectangle)
        peintre.end()


class ScenePlanche(QFrame):
    """Le ``viewer-stage`` : le mat, la bande, le cadre -- et l'image dedans.

    ``DESIGN.md``, ``components.viewer-stage`` : fond ``{colors.image-mat}``,
    ``padding`` ``{spacing.mat-min}``, ``radius`` ``{rounded.lg}``,
    ``content-radius`` ``{rounded.none}``.

    La bande de ``mat-min`` autour du contenu est du **neutre pur** : aucune
    couleur chromatique -- accent, semantique, badge, bordure -- n'y entre.
    C'est pour cela que cette scene n'accueille QUE le contenu d'image :
    rien d'autre n'entre dans le cadre (``EXPERIENCE.md``), et les controles
    de vue vivent **au-dessus** d'elle.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("viewer-stage")
        marge = jetons.ESPACEMENTS["mat-min"]
        self.rayon = jetons.RAYON_CADRE_SCENE
        #: Couleurs posees par la scene elle-meme : le mat et sa bordure,
        #: tous deux strictement neutres (R = G = B).
        self.couleurs_posees = (
            jetons.COULEURS["image-mat"],
            jetons.COULEURS["border"],
        )
        self.setStyleSheet(
            f"#viewer-stage {{ background: {jetons.COULEURS['image-mat']};"
            f" border: 1px solid {jetons.COULEURS['border']};"
            f" border-radius: {self.rayon}px; }}"
        )
        colonne = QVBoxLayout(self)
        colonne.setContentsMargins(marge, marge, marge, marge)
        colonne.setSpacing(0)
        self.contenu = ContenuDImage(self)
        colonne.addWidget(self.contenu)

    def poser(self, page, image: QImage | None = None) -> None:
        self.contenu.poser(page, image)

    # La scene RELAIE les gestes de vue vers son contenu : les vues
    # connaissent la scene (c'est elle qu'elles posent dans leur colonne) et
    # n'ont pas a savoir qu'un `ContenuDImage` vit dedans.
    def definir_zoom_pourcent(self, pourcent) -> None:
        self.contenu.definir_zoom_pourcent(pourcent)

    def ajuster(self) -> None:
        self.contenu.ajuster()

    def cadrer_sur_la_largeur(self) -> None:
        self.contenu.cadrer_sur_la_largeur()

    def cadrer_sur_la_hauteur(self) -> None:
        self.contenu.cadrer_sur_la_hauteur()

    def taille_reelle(self) -> None:
        self.contenu.taille_reelle()

    @property
    def zoom(self) -> float:
        return self.contenu.zoom


__all__ = [
    "ContenuDImage",
    "FAMILLES",
    "FAMILLE_MARQUEUR",
    "FAMILLE_QR_NON_DECODE",
    "FAMILLE_ZONE",
    "JETON_COULEUR_PAR_FAMILLE",
    "NOM_DE_ZONE_QR",
    "ScenePlanche",
    "Trait",
    "plan_de_surimpressions",
]
