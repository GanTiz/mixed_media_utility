# -*- coding: utf-8 -*-
"""L'atelier Pdf, la MIRE DE CALIBRATION : `E5-6` a `E5-6e` (story 11.7, AC 8).

**Cinq ecrans, pas un** -- regler, confirmer, generer, trancher un conflit,
conclure. Le parcours de la mire suit exactement celui des planches, et c'est
une demande d'Egan, verbatim : « conformement a la logique de tous les autres
ecrans qui ecrivent quelque chose ». `E5-6b` est donc **le meme ecran** que
`E5-3` -- meme `execution.EcranChiffre`, meme cadre `À écrire`, meme ordre (ce
qui sort, ou ca va, le nom en dernier), memes trois issues, meme fleche posee
sur celle qui n'ecrit pas -- et non une seconde redaction qui divergerait au
premier reglage.

**Ce module ne cable rien**, et c'est structurel : quatre lots de la meme story
travaillent en parallele sur `atelier_pdf.py`, qui porte le menu et la porte.
Les cinq ecrans sont livres ici avec leurs points d'entree (`ouvrir_*`), et le
parcours -- ce que `⏎` fait de chaque issue -- se pose **en un seul endroit et
plus tard**. Les rappels d'issue et de suite sont donc des mots-cles **requis**,
jamais `None` par defaut : c'est le finding `K3`, ou quatre suites d'un ecran de
resultat etaient navigables et decoratives parce qu'un point d'appel avait
oublie de les passer sans que rien ne le dise.

Ce que la mire N'A PAS, et qui se mesure comme une absence
----------------------------------------------------------

* **aucun rang de version** (`EPIC5-ARB-82`). La mire ne declare ni rush, ni
  lot, ni cadence -- elle sert **toute une chaine de scan** --, donc elle n'a
  pas de lot dont numeroter les tirages. `E5-6d` n'offre par consequent
  **aucune** issue « creer la version suivante » : sa sortie non destructive est
  le **changement de nom de chaine**, qui entre dans le nom du fichier et ecrit
  a cote. La ligne d'etat le dit -- `aucun rang pour cet objet` -- et une
  frontiere negative mesure que ce module ne porte aucun mot du vocabulaire des
  rangs ;
* **aucun poids de fichier annonce**. `E5-3` porte `~ 470 Mo (majorant)` parce
  qu'un majorant de planches se calcule ; personne n'a pese une mire, et
  l'inventer serait la valeur qui a l'air juste -- la pire des deux erreurs
  possibles (`DESIGN.md` section 3) ;
* **aucune duree, aucun « reste ~ 3 s »**. Personne n'a chronometre la
  composition, et `EPIC7-ARB-67` interdit de rendre un temps tant qu'aucune
  mesure n'existe.

`E5-6c` : le ROTOR, et pourquoi il n'y a plus ni barre ni journal
----------------------------------------------------------------

Egan a demande, puis valide (« **Bien** »), **un glyphe qui tourne** a la place
d'une barre chiffree. Son motif, verbatim : « **Car je crois qu'il n'y aura rien
a voir cote journal, non ?** »

Il avait raison, et c'est mesure sur le chemin de production : entre
`logger.info("Demarrage de la generation de page de calibration...")` et
`logger.info("Page de calibration ecrite: ...")`, **aucun appel de journalisation
n'existe** -- ni dans `pdf_render.render_lot_pdf`, ni dans son `_render_page`, ni
dans `pdf_composition.compose_calibration_page_plan`. Les quatre lignes que la
maquette v5 affichait etaient **dessinees** : rien ne les emet.

Trois consequences, et elles tiennent ensemble :

1. **la barre part**, parce que le coeur ne peut pas l'alimenter. Le canal livre
   par la tache B4 emet un jalon **par page** et `total = plan.page_count` ; une
   mire tient sur une page, donc la seule barre alimentable aurait deux etats,
   0 % puis 100 %. Le compte de pastilles (`130/164`) etait exactement le detail
   qu'Egan a exclu (« un jalon par page mais **pas le detail du QR et des
   pastilles** ») ;
2. **le journal part avec elle**, faute d'avoir quoi que ce soit a montrer ;
3. **et `Tab journal` part avec le journal.** Annoncer une touche inerte
   est un defaut que ce depot a paye quarante fois -- finding `I8` : `Tab
   journal` etait promis par les maquettes et traite par personne. La ligne de
   raccourcis de `E5-6c` ne porte donc que ce qui marche.

Le rotor est du **produit** : `jetons.ROTOR` et `jetons.rotor()`. Il vit **hors**
de `jetons.GLYPHES`, qui nomme des *etats* et rend un dessin par entree ; un
rotor est l'inverse -- un seul sens rendu par quatre dessins. `DESIGN.md` §9
interdit « une animation qui tourne **a la place d'un compte reel** » : l'interdit
tient, resserre a ce qu'il visait. Ici il n'y a **aucun compte a remplacer**, et
le rotor est le seul signe honnete que la machine travaille.

Les invariants que ce module ne casse pas
-----------------------------------------

* `EPIC11-ARB-36` : `E5-6` porte **deux champs exactement** -- la chaine et le
  commentaire -- et **affiche** le reste comme donnee imposee. « Tout champ d'un
  formulaire TUI nomme l'argument de coeur qu'il alimente -- un champ sans
  argument est un defaut » : c'est :data:`ARGUMENTS_DU_COEUR`, confronte par un
  banc a la **signature reelle** de `makepdf.generer_la_page_de_calibration` ;
* `EPIC11-ARB-89` : jamais une seule issue, jamais un blocage sec. `E5-6d` en
  porte trois, dont deux qui n'ecrivent pas ;
* `EPIC11-ARB-7` : le curseur au montage ne vise jamais une issue qui ecrit. Ce
  module **appelle** `panneau.ChoixExclusif`, il ne reecrit pas sa regle ;
* `EPIC11-ARB-56` : la ligne d'etat ne porte aucune touche, aucun conseil
  d'usage, aucun motif de conception -- seulement des constats chiffres ;
* `EPIC11-ARB-68` : aucune lettre n'est un raccourci dans un champ de saisie ;
* **aucun nombre de la fonction de calibration n'est recopie** : `164`, `130`,
  `34` et `17 x 2` se **derivent** du coeur (`patch_presets`), et une frontiere
  negative rougit si l'un d'eux devient un litteral de ce fichier ;
* la TUI **n'importe jamais `cli`**.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from textual.widget import Widget
from textual.widgets import Static

from ..io import naming, project_layout
from . import aide_de_champ, jetons
from .atelier_scan import (INDENT_DU_CURSEUR, INDENT_DU_TEXTE,
                           LARGEUR_DU_LIBELLE, MENTION_REQUIS, filet)
from .avancement import Journal
from .coque import EcranPasEncore, ObjetTravaille, Palier
from .execution import EcranChiffre, EcranResultat, bloc_peint
from .panneau import ChoixExclusif, Issue, LigneChiffree, Panneau

# ===========================================================================
# Le bandeau -- deux temps, et pas un mot de conception (AC 8.8)
# ===========================================================================

#: Le segment du milieu du bandeau, `mmu · projet_demo · **Pdf · Calibration**`.
#: Il nomme l'atelier et l'entree de son menu, ce qui suffit a dire ou l'on
#: entre : `EPIC11-ARB-28` interdit qu'un terme de nos documents de decision
#: -- « parcours a part », « palier », « feuille CLI », « point de jugement » --
#: s'affiche a l'ecran, et une frontiere negative le mesure sur ce fichier.
PALIER_DE_LA_MIRE = "Pdf · Calibration"

#: La droite du bandeau, aux deux temps du parcours. **Des mesures**, pas des
#: termes de conception : « 1 sur 2 » se compte, « regler » et « ecrire » sont
#: ce que l'operateur fait.
TEMPS_DE_REGLAGE = "temps 1 sur 2 · régler"
TEMPS_D_ECRITURE = "temps 2 sur 2 · écrire"

# ===========================================================================
# Les lignes de raccourcis
# ===========================================================================

#: `E5-6`, verbatim de la maquette (l. 23). `Tab` nomme sa **destination** --
#: l'autre champ --, convention d'`EPIC11-ARB-68` deja posee par le reste de la
#: TUI. `Échap` remonte au menu de l'atelier, ce que la coque traite.
#:
#: MESURE: 47/52
RACCOURCIS_MIRE_REGLAGES = "⏎ continuer  Tab champ  Échap menu Pdf  F1 aide"

#: `E5-6b` **et** `E5-6d`, verbatim de leurs maquettes (l. 23). Une seule
#: redaction pour les deux : ce sont deux points de jugement de la meme forme --
#: un cartouche, trois issues, aucun nom editable --, et deux constantes
#: identiques divergeraient au premier ajustement de libelle.
#:
#: **Elle ne porte pas `Tab`**, et c'est mesurable plutot que declaratif : ces
#: deux ecrans montent `EcranChiffre` **sans modele de noms**, et
#: `EcranChiffre.traiter` rend `False` sur `tab` des que `len(self.noms)` vaut
#: zero. La touche n'est donc ni annoncee ni active -- les deux moities de la
#: meme promesse (AC 6.3a, finding `I8`).
#:
#: MESURE: 44/49
RACCOURCIS_MIRE_JUGEMENT = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"

#: `E5-6c`, verbatim de la maquette (l. 23). **Deux touches, et pas une de
#: plus** : il n'y a ni barre a lire, ni journal a deplier -- voir le docstring
#: de module. `Échap` interrompt et **ne remonte pas** : il est arrete par
#: l'ecran, sans quoi l'application depilerait la generation en cours.
#:
#: MESURE: 26/26
RACCOURCIS_MIRE_EN_COURS = "Échap interrompre  F1 aide"

# ===========================================================================
# Les donnees IMPOSEES par la fonction de calibration (AC 8.1, AC 8.2)
# ===========================================================================

#: Les libelles de la colonne de gauche, verbatim des maquettes. Ils vivent en
#: constantes parce que **deux ecrans les portent** -- `E5-6` les affiche en
#: formulaire, `E5-6b` les reprend en cartouche -- et qu'une seconde redaction
#: ferait dire deux mots differents a la meme donnee.
LIBELLE_PASTILLES = "Pastilles"
LIBELLE_PATCHS = "Jeu de patchs"
LIBELLE_FORMAT_DPI = "Format · DPI"
LIBELLE_FORMAT_MARGE_DPI = "Format · marge · DPI"
LIBELLE_FICHIER = "Fichier"
LIBELLE_DESTINATION = "Destination"

#: La decomposition du cardinal de pastilles, dans ses deux redactions de
#: maquette : la longue sur `E5-6`, ou la colonne est large, la courte dans les
#: cartouches de `E5-6b` et `E5-6e`, ou elle ne l'est pas. **Les deux nombres
#: sont substitues, jamais ecrits** -- c'est ce que l'AC 8.2 mesure.
DECOMPOSITION_LONGUE = "{treillis} au treillis + {temoins} témoins"
DECOMPOSITION_COURTE = "{treillis} treillis + {temoins} témoins"

#: Ce que la colonne de droite du jeu de patchs dit, sur `E5-6`. Elle repond a
#: l'objection d'Egan mot pour mot : le bandeau de temoins est ce que cette page
#: a de **commun** avec une planche ordinaire, donc son cardinal ne la
#: caracterise pas -- c'est le total qui la caracterise.
MENTION_DU_BANDEAU = "les {temoins} témoins du bandeau"

#: L'unite de la marge, pour la ligne `Format · marge · DPI` de `E5-6b`. Le
#: preset de marge est un identifiant du registre (`"0"`), pas un nombre : c'est
#: lui qui est affiche, suivi de son unite.
UNITE_DE_LA_MARGE = "mm"

#: Le separateur des trois valeurs d'une meme ligne (`A4 · 600`). Celui des
#: maquettes, et le meme que le bandeau : un point median entoure d'espaces.
SEPARATEUR = " · "

#: Les mots de pluriel des deux unites de cet atelier. Le singulier vaut aussi
#: pour zero, comme partout dans `projet_lecture`.
PLURIEL_DES_PAGES = {False: "page", True: "pages"}
PLURIEL_DES_PASTILLES = {False: "pastille", True: "pastilles"}
UNITE_DES_PDF = "PDF"


@dataclass(frozen=True)
class DonneesImposees:
    """Ce que la fonction de calibration impose, et que l'operateur ne choisit pas.

    `EPIC11-ARB-36`, verbatim d'Egan : « le nombre de patches n'est pas un choix
    je crois. Il depend de la fonction de calibration non ? » -- il avait raison,
    `makepdf calibration-page` n'a que `--chaine` et `--commentaire` a offrir
    dans cette TUI. Le reste est **affiche** sous un filet nomme, jamais
    saisissable.

    **Aucun de ces champs n'est un litteral de ce module** : ils sont tous
    derives du coeur par :func:`donnees_imposees`. Un `164` ecrit ici serait
    juste le jour ou on l'ecrit et faux au premier reglage du treillis, sans
    qu'aucune etape n'echoue -- la classe de defaut la plus payee du depot.
    """

    #: Le total imprime sur la page : le treillis central **et** le bandeau.
    pastilles: int
    #: Le treillis central seul.
    treillis: int
    #: Le bandeau lateral de temoins, **derive par soustraction** du total.
    temoins: int
    #: L'identifiant du preset de patchs que le coeur retiendra.
    preset: str
    #: Le format de page, le preset de marge, le dpi de rendu, tous du registre.
    page_format: str
    marge: str
    dpi: int
    #: Le cardinal de pages d'une mire. C'est `1`, et il est **lu** du coeur.
    pages: int

    @property
    def decomposition(self) -> str:
        """`130 treillis + 34 témoins` -- la redaction des cartouches."""
        return DECOMPOSITION_COURTE.format(treillis=self.treillis,
                                           temoins=self.temoins)

    @property
    def decomposition_longue(self) -> str:
        """`130 au treillis + 34 témoins` -- la redaction de `E5-6`."""
        return DECOMPOSITION_LONGUE.format(treillis=self.treillis,
                                           temoins=self.temoins)

    @property
    def mention_du_bandeau(self) -> str:
        return MENTION_DU_BANDEAU.format(temoins=self.temoins)

    @property
    def format_et_dpi(self) -> str:
        """`A4 · 600` -- la ligne `Format · DPI` de `E5-6`."""
        return SEPARATEUR.join((self.page_format, str(self.dpi)))

    @property
    def format_marge_et_dpi(self) -> str:
        """`A4 · 0 mm · 600` -- la ligne du cartouche de `E5-6b`.

        Elle porte la marge en plus, parce qu'un cartouche de confirmation
        recapitule **ce qui sera ecrit** et que la marge en fait partie ; `E5-6`
        la tait, ayant deja trois lignes imposees et pas de decision a prendre
        dessus.
        """
        return SEPARATEUR.join((self.page_format,
                                f"{self.marge} {UNITE_DE_LA_MARGE}",
                                str(self.dpi)))

    @property
    def pages_lisibles(self) -> str:
        return f"{self.pages} {PLURIEL_DES_PAGES[self.pages > 1]}"

    @property
    def pastilles_lisibles(self) -> str:
        return (f"{self.pastilles} "
                f"{PLURIEL_DES_PASTILLES[self.pastilles > 1]}")


def temoins_du_bandeau(preset_id: str) -> int:
    """Le cardinal du bandeau de temoins, **derive du preset** : `17 x 2`.

    Seconde route vers le meme nombre que :func:`donnees_imposees` obtient par
    soustraction (`164 - 130`), et c'est deliberement une seconde route : un
    banc confronte les deux, si bien qu'aucune des deux ne peut deriver seule
    sans que l'autre le dise. L'AC 8.2 demande exactement cela -- que `34` soit
    `164 - 130` **et** `17 x 2`, jamais un litteral.
    """
    from .. import patch_presets

    preset = patch_presets.get_patch_preset(preset_id)
    return len(preset.value_ids) * preset.repetition


def donnees_imposees() -> DonneesImposees:
    """Tout ce que `E5-6` affiche sans le laisser choisir, **lu du coeur**.

    **Les imports sont differes**, comme partout ou ce paquet touche au coeur
    lourd : `pdf_composition` tire la chaine de composition entiere, et les
    ecrans de l'atelier doivent pouvoir se construire sur un environnement
    partiel -- c'est le meme geste qu'`atelier_pdf._pages_du_tirage`.

    Le preset retenu est celui que le coeur prendra pour de bon
    (`pdf_composition.DEFAULT_PATCH_PRESET`), la TUI ne passant aucun
    `--nombre-patchs`. Qu'il porte bien le bandeau de temoins est verifie par le
    coeur lui-meme (`calibration_page_carries_witness_band`) : un preset qui
    n'en porterait pas rendrait la decomposition affichee fausse, et c'est
    exactement le genre d'ecart qu'un chiffre recopie ne montre jamais.
    """
    from .. import page_templates, patch_presets, pdf_composition

    preset = pdf_composition.DEFAULT_PATCH_PRESET
    pastilles = patch_presets.calibration_page_patch_count(preset)
    treillis = patch_presets.calibration_lattice_patch_count()
    return DonneesImposees(
        pastilles=pastilles,
        treillis=treillis,
        temoins=pastilles - treillis,
        preset=preset,
        page_format=page_templates.DEFAULT_PAGE_FORMAT,
        marge=page_templates.DEFAULT_MARGIN_PRESET,
        dpi=pdf_composition.RENDER_DPI_DEFAULT,
        pages=pdf_composition.CALIBRATION_ONLY_PAGE_COUNT,
    )


# ===========================================================================
# Le nom du fichier -- derive, jamais editable, condensat JAMAIS elide (AC 8.3)
# ===========================================================================

#: Le dossier de sortie de la mire, **lu du plan de projet** et non recopie :
#: c'est celui que `makepdf.generer_la_page_de_calibration` compose
#: (`project_layout.chemin_de_planche(project_dir, plan.pdf_filename)`).
#:
#: C'est le nom NEUF (`EPIC11-ARB-225`), donc ce que l'ecran annonce d'un
#: projet neuf -- le seul cas qui existe chez Egan. Le dossier d'avant reste
#: RECONNU en lecture, et c'est `chemin_de_la_mire` ci-dessous qui le resout,
#: pas cette constante d'affichage.
DOSSIER_DE_LA_MIRE = project_layout.PLANCHES_DIRNAME


def nom_de_la_mire(project_id: str, chaine: str) -> str:
    """Le nom du PDF, **rendu par le coeur** (`build_calibration_pdf_filename`).

    Aucune recomposition ici : le nom entre dans le refus de conflit, dans le
    fichier ecrit et dans ce que `E5-6b` promet, et trois redactions du meme nom
    divergeraient sur celle qui compte -- la troncature du slug lisible.
    """
    return naming.build_calibration_pdf_filename(project_id, chaine)


def chaine_nommable(chaine: str) -> bool:
    """Vrai quand le coeur accepte de nommer un fichier avec ce libelle.

    **Rien n'est reecrit ici** : la regle -- « au moins un caractere
    alphanumerique ASCII » -- vit dans `io.naming.normalize_identifier`, et
    c'est elle qu'on interroge. La recopier ferait une seconde redaction qui
    divergerait de celle qui compte, c'est-a-dire de celle qui refuse au moment
    d'ecrire.

    Le libelle est passe **avec le nom d'argument du coeur** : la phrase du
    refus nomme alors le libelle et non un fichier source.

    **Elle ne leve jamais**, comme toutes les lectures de ce module : un ecran
    doit pouvoir se dessiner sur une saisie que le coeur refusera.
    """
    try:
        naming.normalize_identifier(chaine, label="scan_chain_label")
    except naming.NamingError:
        return False
    return True


def queue_du_nom(chaine: str) -> str:
    """La part du nom qui **porte l'identite** : `-<condensat>_calibration.pdf`.

    Elle est composee du condensat que le coeur derive du libelle **brut**
    (`naming.scan_chain_suffix`) et du suffixe fixe que
    `build_calibration_pdf_filename` pose. C'est elle qu'une ellipse ne doit
    **jamais** manger : `normalize_identifier` est non injective -- « hp envy »,
    « hp-envy » et « hp  envy » rendent le meme slug --, donc deux chaines
    distinctes ne se separent que par leur condensat. Un nom abrege qui le
    perdrait afficherait deux fichiers differents sous une meme ligne.
    """
    return f"-{naming.scan_chain_suffix(chaine)}{naming.CALIBRATION_PDF_SUFFIX}"


def abreger_la_mire(nom: str, chaine: str, largeur: int,
                    ascii_seul: bool = False) -> str:
    """Le nom tenu dans `largeur` colonnes, **l'ellipse dans le slug lisible**.

    Le nom se coupe en deux parts qui ne jouent pas le meme role : une **queue
    identifiante** -- le condensat et le suffixe `_calibration.pdf` -- qui passe
    entiere, et une **tete lisible** -- le projet et le slug de chaine -- qui
    est seule abregee. C'est exactement ce que la maquette dessine
    (`projet_demo_hp-envy-4520…-73881cda_calibration.pdf`).

    **Ni `abreger_nom`, ni `abreger_chemin`, et le motif est le condensat.**
    `abreger_nom` coupe **au milieu** parce qu'un nom de dossier de tournage
    porte son identite a ses deux bouts ; ici l'identite est deja mise a l'abri
    dans la queue, et couper au milieu de la tete y sacrifierait le debut du
    slug -- le nom de l'imprimante, c'est-a-dire ce qui se reconnait a l'oeil.
    `jetons.ajuster` garde le plus long prefixe et pose les points : c'est la
    coupe qui convient a une tete purement lisible.

    **Le repli quand la queue n'est pas reconnue n'est pas un detail** : un nom
    compose autrement, ou une chaine que le coeur refuse de condenser, retombent
    sur `abreger_nom`. Rendre la ligne telle quelle la ferait **replier** par
    `textual` -- et une ligne repliee dans un bloc decale tout ce qui suit.
    """
    if largeur <= 0:
        return ""
    if jetons.colonnes(nom) <= largeur:
        return nom
    try:
        queue = queue_du_nom(chaine)
    except naming.NamingError:
        return jetons.abreger_nom(nom, largeur, ascii_seul)
    if not nom.endswith(queue):
        return jetons.abreger_nom(nom, largeur, ascii_seul)
    place = largeur - jetons.colonnes(queue)
    if place <= 0:
        # Meme la queue seule ne tient pas. On la rend entiere et la ligne
        # deborde a la mesure de ce qu'il faudrait : un nom tronque dans son
        # condensat serait un nom **faux**, ce qui est pire qu'un nom trop long.
        return queue
    return jetons.ajuster(nom[:-len(queue)], place, ascii_seul) + queue


def destination_de_la_mire(project_id: str) -> str:
    """`projet_demo/planches/` -- ou le fichier va, verbatim des maquettes.

    Le dossier est celui du coeur, jamais la chaine `"planches"` ecrite ici : la
    ligne `Destination` existe parce qu'Egan a demande « on aimerait bien savoir
    ou va le fichier », et une seconde redaction du dossier repondrait a cote le
    jour ou le plan de projet change.
    """
    return f"{project_id}/{DOSSIER_DE_LA_MIRE}/"


def chemin_de_la_mire(dossier_projet, project_id: str, chaine: str) -> Path:
    """Le chemin **vise**, resolu comme le coeur le resout.

    **Les DEUX racines**, par `project_layout.chemin_de_planche`
    (`EPIC11-ARB-225`) et non par une composition locale sur
    `DOSSIER_DE_LA_MIRE`. C'est ce dont depend `mire_presente` : sous le nom
    neuf seul, une mire deja ecrite dans un projet ancien serait declaree
    ABSENTE, l'ecran de conflit `E5-6d` ne s'intercalerait pas, et le coeur --
    qui resout les deux, lui -- refuserait a l'ecriture. L'ecran promettrait
    donc une generation que le produit refuse.
    """
    return project_layout.chemin_de_planche(
        dossier_projet, nom_de_la_mire(project_id, chaine))


# ===========================================================================
# La mire deja presente -- ce que `E5-6` mesure et ce que `E5-6d` montre
# ===========================================================================

#: Les deux formats de date de cet atelier. `E5-6d` porte l'heure (`27/08 à
#: 09:14`) parce qu'un operateur qui hesite a ecraser a besoin de savoir si le
#: fichier date d'il y a cinq minutes ; la ligne d'etat n'en a pas la place.
#:
#: **La date vient du FICHIER, mesuree sur le disque.** Aucun document du depot
#: n'horodate une mire -- elle ne touche pas le manifeste, deliberement -- et
#: inventer un horodatage serait la valeur qui a l'air juste.
FORMAT_DE_L_HORODATAGE = "%d/%m à %H:%M"
FORMAT_DE_LA_DATE = "%d/%m"


@dataclass(frozen=True)
class MirePresente:
    """Une mire du meme nom deja ecrite, telle que le disque la donne.

    `quand` vaut `None` quand le fichier repond a `exists()` mais pas a `stat()`
    -- une course avec un autre processus, un montage qui disparait. Le segment
    de date **disparait** alors de la ligne plutot que de mentir, comme le pied
    du menu de l'atelier le fait deja.
    """

    chemin: Path
    quand: float | None = None

    @property
    def horodatage(self) -> str:
        """`27/08 à 09:14`, ou `""` quand le disque n'a rien dit."""
        return self._date(FORMAT_DE_L_HORODATAGE)

    @property
    def date(self) -> str:
        """`27/08`, ou `""`."""
        return self._date(FORMAT_DE_LA_DATE)

    def _date(self, forme: str) -> str:
        if self.quand is None:
            return ""
        try:
            return datetime.fromtimestamp(self.quand).strftime(forme)
        except (OSError, OverflowError, ValueError):
            return ""


def mire_presente(dossier_projet, project_id: str,
                  chaine: str) -> MirePresente | None:
    """La mire deja ecrite sous `planches/` -- ou sous le nom d'avant --, ou `None`.

    C'est la mesure dont depend tout le reste du parcours : la ligne d'etat de
    `E5-6` la dit **avant** de generer plutot qu'apres, et c'est elle qui decide
    si `E5-6d` s'intercale. Elle ne leve jamais -- un dossier de projet absent,
    un libelle de chaine que le coeur refuse de nommer, un droit de lecture
    manquant rendent tous `None` : l'ecran de reglages doit s'ouvrir dans tous
    les cas, et c'est le coeur qui refuse au moment d'ecrire.
    """
    try:
        chemin = chemin_de_la_mire(dossier_projet, project_id, chaine)
    except (naming.NamingError, TypeError, ValueError):
        return None
    try:
        if not chemin.is_file():
            return None
        return MirePresente(chemin, chemin.stat().st_mtime)
    except OSError:
        return None


# ===========================================================================
# `E5-6` -- le formulaire : DEUX champs exactement (AC 8.1)
# ===========================================================================

#: Les cles des deux champs, et **l'argument de coeur que chacun alimente**.
#:
#: `EPIC11-ARB-36`, verbatim : « tout champ d'un formulaire TUI nomme l'argument
#: de coeur qu'il alimente -- un champ sans argument est un defaut, pas une
#: amelioration ». Cette table n'est donc pas de la documentation : c'est ce que
#: :meth:`FormulaireDeLaMire.arguments_du_coeur` passe reellement, et un banc la
#: confronte a la **signature** de `makepdf.generer_la_page_de_calibration`. Un
#: troisieme champ ajoute a l'ecran sans argument correspondant fait rougir.
CHAMP_CHAINE = "chaine"
CHAMP_COMMENTAIRE = "commentaire"
ARGUMENTS_DU_COEUR: Mapping[str, str] = {
    CHAMP_CHAINE: "scan_chain_label",
    CHAMP_COMMENTAIRE: "comment",
}

#: Les libelles des deux champs, verbatim de la maquette `E5-6` (l. 7-8).
LIBELLES_DES_CHAMPS: Mapping[str, str] = {
    CHAMP_CHAINE: "Nom de la chaîne",
    CHAMP_COMMENTAIRE: "Commentaire",
}

#: **`F1` sur un champ : ce que ce champ attend** (`EPIC11-ARB-14`, story 11.9
#: lot B). Le mecanisme vient du paquet (`aide_de_champ`) ; ces deux phrases
#: sont la **donnee de cet ecran**, et elles restent ici.
#:
#: Chacune dit ce que le champ attend, sa forme -- requis ou non, ce que
#: `peut_continuer` tranche -- et une **valeur du contexte courant**
#: (`{valeur}`, remplie par :meth:`EcranMireReglages.valeur_de_l_aide`). Aucune
#: ne redit `Nom de la chaîne` ni `Commentaire` : « une aide qui paraphrase le
#: libelle est un defaut ».
AIDE_PAR_CHAMP = {
    CHAMP_CHAINE: "Requis, le nom qui nommera le fichier ; ici : {valeur}.",
    CHAMP_COMMENTAIRE: ("Facultatif, un texte imprimé sur la planche ; "
                        "ici : {valeur}."),
}

#: Le titre de l'ecran, verbatim (l. 5).
TITRE_DES_REGLAGES = "Générer une planche de calibration"

#: Les deux filets nommes de `E5-6` (l. 10 et l. 16).
FILET_IMPOSE = "Imposé par la fonction de calibration"
FILET_A_ECRIRE = "Ce qui sera écrit"

#: Largeur de la colonne des valeurs, avant la colonne de mention. Elle est
#: **derivee de la maquette** : `164` et `patches-17-v4` s'y calent, et la
#: mention commence apres un creux d'au moins deux colonnes. La maquette
#: dessine sa propre mention a deux colonnes differentes (41 et 45) selon la
#: ligne ; le produit en tient **une**, ce qui est ce qu'une colonne doit etre.
LARGEUR_DE_LA_VALEUR = 13


def avec_la_mention(gauche: str, valeur: str, mention: str) -> str:
    """`gauche` puis `mention`, calee sur LA colonne de mention de `E5-6`.

    **Une seule redaction pour les deux sortes de lignes** : les lignes
    imposees la portaient depuis la livraison, les lignes de champ la
    gagnent avec `MQ-6`. Deux calculs de la meme colonne divergeraient au
    premier ajustement -- c'est ce que `jetons.CREUX_MINIMAL` documente deja
    pour les quatre copies qu'il a remplacees.

    Le creux se prend sur la LARGEUR DE LA VALEUR et non sur celle de la
    ligne : la mention doit tomber au meme endroit que la valeur soit `164`
    ou le glyphe neutre d'un champ vide, sans quoi elle danserait a chaque
    frappe.
    """
    if not mention:
        return gauche
    creux = max(LARGEUR_DE_LA_VALEUR - jetons.colonnes(valeur), 0)
    return gauche + " " * (creux + jetons.CREUX_MINIMAL) + mention


#: Ce que la ligne d'etat DIT quand `⏎ continuer` refuse (manque `MQ-6`).
#:
#: **Le defaut qu'elle ferme est mesure** : `⏎ continuer` est annonce au pied,
#: `peut_continuer` le refuse a juste titre tant que la chaine n'est pas
#: nommable -- le coeur refuse une page anonyme --, et l'ecran ne disait
#: **rien**. La ligne d'etat continuait d'afficher sa mesure du fichier, exacte
#: mais sans rapport avec la question que l'operateur venait de poser ; il n'y
#: avait aucun moyen, sans presser `F1`, de savoir pourquoi la touche ne
#: continuait pas.
#:
#: La redaction suit `atelier_scan.PHRASE_DPI_REQUIS`, l'ecran jumeau : ce qui
#: manque, puis ce que son absence empeche. **Aucune touche, aucun conseil
#: d'usage** (`EPIC11-ARB-56`).
#:
#: **Elle ne couvre QUE le champ vide.** Le second regime de refus -- un
#: libelle saisi mais innommable (`---`) -- porte `ETAT_CHAINE_INUTILISABLE`
#: depuis le finding `C2-2`, et la poser par-dessus mentirait : un nom est
#: bien saisi.
ETAT_CHAINE_REQUISE = ("nom de chaîne requis — la planche ne peut pas être "
                       "nommée")


@dataclass
class FormulaireDeLaMire:
    """Le modele de `E5-6` : deux champs, et rien d'autre.

    **Modele pur**, comme `panneau.py` : aucune dependance a `textual`, aucune
    ecriture. C'est ce qui rend mesurable sans terminal le seul appariement a
    risque de cet ecran -- le champ au focus contre la ligne rendue, et ce que
    la frappe ecrit contre le champ qu'elle vise.

    Les deux champs partent **vides**. La chaine est requise (`E5-6` ne continue
    pas sans elle, exactement comme le coeur refuse une page anonyme) ; le
    commentaire ne l'est pas, et son absence n'est pas un manque -- le coeur
    l'accepte a `None`.
    """

    chaine: str = ""
    commentaire: str = ""
    #: Le champ courant, **suivi** : `aide_de_champ.ChampSuivi` compte chaque
    #: deplacement du curseur, et c'est ce compte qui fait TOMBER l'aide de
    #: champ au lieu de la cacher (correctif du 2026-09-04). Le comptage se
    #: fait a l'AFFECTATION : aucun chemin de navigation -- ni ceux d'ici, ni
    #: un chemin ajoute plus tard -- n'a rien a appeler pour cela.
    champ: str = aide_de_champ.ChampSuivi(CHAMP_CHAINE)

    # -- lecture -----------------------------------------------------------

    def champs(self) -> tuple[str, ...]:
        """L'ensemble **EXACT** des champs que `Tab` parcourt : deux.

        Ce n'est pas une liste ouverte : `EPIC11-ARB-36` a tranche que les
        patchs, la geometrie et le dpi sont des **donnees imposees**, et un
        troisieme champ ici serait un reglage que le coeur ne recevrait pas.
        """
        return (CHAMP_CHAINE, CHAMP_COMMENTAIRE)

    def saisie(self, cle: str) -> str:
        """Ce qu'un champ porte vraiment, blancs de bord retires.

        **Une seule redaction pour trois surfaces** : la valeur dessinee, le nom
        de fichier derive, et ce qui part au coeur. Ne strip que la valeur
        affichee laisserait partir `'   '` comme nom de chaine -- defaut deja
        paye sur le formulaire de calibration du Scan, ou le document de profil
        a porte un libelle blanc.
        """
        valeur = getattr(self, cle, "")
        return valeur.strip() if isinstance(valeur, str) else valeur

    @property
    def peut_continuer(self) -> bool:
        """`⏎ continuer` n'est accessible qu'avec une chaine **nommable**.

        Le coeur refuse une page anonyme -- « une page de calibration anonyme ne
        se distinguerait pas d'une autre » -- et laisser continuer ici ferait
        decouvrir le refus deux ecrans plus loin, apres une confirmation.

        **Deux conditions, et la seconde manquait** (finding `C2-2`). Un libelle
        non vide mais sans un seul caractere alphanumerique ASCII -- `---`,
        `!!!`, `..` -- passait cette garde, et le refus du coeur n'etait pas
        decouvert deux ecrans plus loin : il **traversait la boucle `textual`**
        au moment de generer et emportait l'application. Le promettre dans un
        docstring sans le mesurer etait la forme exacte du blocage sec
        qu'`EPIC11-ARB-89` proscrit -- sauf qu'ici il n'y avait meme pas de
        blocage, il y avait une chute.

        La seconde condition n'est pas ecrite ici : elle interroge le coeur
        (:func:`chaine_nommable`), qui est le seul a savoir ce qu'il refusera.
        """
        chaine = self.saisie(CHAMP_CHAINE)
        return bool(chaine) and chaine_nommable(chaine)

    def arguments_du_coeur(self) -> dict[str, Any]:
        """Ce que les deux champs alimentent, **nomme comme le coeur le nomme**.

        C'est le point d'appel qui rend `ARGUMENTS_DU_COEUR` mesurable au lieu
        de declaratif : le cablage passe ce dictionnaire en `**kwargs` a
        `makepdf.generer_la_page_de_calibration`, donc une cle qui n'existe pas
        dans sa signature leve a l'appel au lieu d'etre ignoree.

        Le commentaire vide part a `None` et non a `""` : le coeur distingue les
        deux, et une chaine vide y serait un commentaire present et blanc.
        """
        commentaire = self.saisie(CHAMP_COMMENTAIRE)
        return {ARGUMENTS_DU_COEUR[CHAMP_CHAINE]: self.saisie(CHAMP_CHAINE),
                ARGUMENTS_DU_COEUR[CHAMP_COMMENTAIRE]: commentaire or None}

    # -- ecriture ----------------------------------------------------------

    def avancer(self, pas: int = 1) -> bool:
        """`Tab` (et `↑↓` en synonyme non annonce) : l'autre champ, en boucle.

        En boucle et non borne : le formulaire tient sur deux lignes, et une
        borne obligerait a une seconde touche pour revenir en arriere.
        """
        champs = self.champs()
        if self.champ not in champs:
            self.champ = champs[0]
            return True
        self.champ = champs[(champs.index(self.champ) + pas) % len(champs)]
        return True

    def frapper(self, caractere: str) -> bool:
        """Un caractere dans le champ au focus.

        **Toute lettre s'y ecrit** (`EPIC11-ARB-68`) : « aucune lettre n'est un
        raccourci dans un champ de saisie, sans exception et sans ordre de
        priorite a maintenir ». Aucun filtrage : un caractere que le coeur
        refusera doit pouvoir etre tape **puis** vu refuse.
        """
        if self.champ not in self.champs():
            return False
        setattr(self, self.champ, getattr(self, self.champ) + caractere)
        return True

    def effacer(self) -> bool:
        if self.champ not in self.champs() or not getattr(self, self.champ):
            return False
        setattr(self, self.champ, getattr(self, self.champ)[:-1])
        return True


#: Ce que la ligne d'etat de `E5-6` dit du fichier vise. **Un constat**
#: (`EPIC11-ARB-56`), et le seul fait que l'ecran ne dit nulle part ailleurs :
#: Egan a demande que le bandeau du bas cesse de repeter `A4 · 600`, deja trois
#: lignes plus haut. C'est aussi la mesure dont depend le refus de conflit,
#: apprise **avant** de generer plutot qu'apres.
ETAT_AUCUN_FICHIER = "aucun fichier de ce nom sous {dossier}/"
ETAT_FICHIER_PRESENT = "un fichier de ce nom existe déjà sous {dossier}/"

#: Ce que la ligne d'etat dit d'un libelle que le coeur refuse de nommer
#: (finding `C2-2`). **Un constat** (`EPIC11-ARB-56`), et le seul endroit ou le
#: refus se lit avant qu'il ne soit trop tard : sans lui, le nom de fichier
#: s'affichait sous le glyphe neutre -- « non renseigne » --, ce qui ne dit rien
#: d'un refus. La regle qu'il nomme est celle du coeur, pas une seconde.
ETAT_CHAINE_INUTILISABLE = "aucune lettre ni chiffre dans ce nom de chaîne"


def ligne_d_etat_des_reglages(donnees: DonneesImposees,
                              presente: MirePresente | None,
                              nommable: bool = True) -> str:
    """`1 page · 164 pastilles · aucun fichier de ce nom sous planches/`.

    Les deux regimes du fichier sont rendus, et c'est volontaire : dire
    seulement l'absence laisserait la presence muette, c'est-a-dire
    indistinguable d'un ecran qui n'a pas encore mesure.

    **Un troisieme regime dit le refus** (finding `C2-2`) : un libelle sans un
    seul caractere alphanumerique ASCII ne nomme aucun fichier, donc la question
    « ce fichier existe-t-il ? » n'a pas de reponse, et y repondre « aucun
    fichier de ce nom » serait un mensonge tranquille. `nommable` vaut vrai par
    defaut : le regime neuf est celui qu'on ajoute, pas celui qu'on impose aux
    appelants qui ne mesurent que le fichier.
    """
    if not nommable:
        return SEPARATEUR.join((donnees.pages_lisibles,
                                donnees.pastilles_lisibles,
                                ETAT_CHAINE_INUTILISABLE))
    forme = (ETAT_FICHIER_PRESENT if presente is not None
             else ETAT_AUCUN_FICHIER)
    return SEPARATEUR.join((donnees.pages_lisibles,
                            donnees.pastilles_lisibles,
                            forme.format(dossier=DOSSIER_DE_LA_MIRE)))


class EcranMireReglages(ObjetTravaille, Palier):
    """`E5-6` -- deux champs saisissables, le reste **affiche**.

    L'ecran ne connait ni le nom du projet ni le disque : il les recoit. C'est
    ce qui permet de le monter dans un banc sans fabriquer un projet complet, et
    c'est aussi ce qui garde le cablage hors de ce module.

    **`⏎` ne fait rien ici** au-dela d'appeler le rappel de suite : c'est le
    parcours qui decide si l'on va vers `E5-6d` (une mire du meme nom existe) ou
    vers `E5-6b`. L'ecran fournit la mesure -- :meth:`presente` -- il ne
    l'interprete pas.
    """

    titre = PALIER_DE_LA_MIRE
    raccourcis = RACCOURCIS_MIRE_REGLAGES
    objet = TEMPS_DE_REGLAGE
    #: **La declaration qui fait entrer cet ecran dans l'ensemble borne** de
    #: `aide_de_champ.ECRANS_A_TABLE_D_AIDE` (AC 1.5, `EPIC11-ARB-198`).
    TABLE_D_AIDE = AIDE_PAR_CHAMP

    #: Un passage : un formulaire n'est pas une station.
    TRANSITOIRE = True

    def __init__(self, project_id: str = "", dossier=None,
                 formulaire: FormulaireDeLaMire | None = None,
                 sur_continuer: Callable[[FormulaireDeLaMire], None] | None = None
                 ) -> None:
        super().__init__()
        self.project_id = project_id
        self.dossier = Path(dossier) if dossier is not None else None
        self.formulaire = formulaire or FormulaireDeLaMire()
        self._sur_continuer = sur_continuer
        self.donnees = donnees_imposees()
        #: `F1` : l'aide du champ courant (story 11.9, AC 1). Elle **remplace**
        #: la ligne blanche qui suit le titre : le cardinal de lignes du corps
        #: ne bouge pas, et `E5-6` reste au caractere pres ce qu'il etait tant
        #: que l'aide est fermee -- l'ecran ne dessine aucune consigne, et lui
        #: en inventer une changerait la maquette sans arbitrage.
        self.aide = aide_de_champ.AideDeChamp(
            AIDE_PAR_CHAMP, formulaire=self.formulaire)
        #: Ce que la ligne d'etat dit **a la place de sa mesure**, le temps
        #: d'une frappe (manque `MQ-6`). Meme mecanisme que `EcranRushes` et
        #: `EcranLotsAPlanches` : il est remis a vide en tete de
        #: :meth:`traiter`, donc un refus ne survit jamais au geste qui le
        #: corrige.
        self._etat_a_dire = ""

    # -- lecture ------------------------------------------------------------

    @property
    def presente(self) -> MirePresente | None:
        """La mire deja ecrite sous ce nom, **relue a chaque dessin**.

        Relue et non memorisee : le nom depend du champ `chaine`, donc il change
        a chaque frappe. Une mesure prise au montage repondrait pour un nom que
        l'operateur vient de quitter.
        """
        if self.dossier is None or not self.formulaire.peut_continuer:
            return None
        return mire_presente(self.dossier, self.project_id,
                             self.formulaire.saisie(CHAMP_CHAINE))

    @property
    def nom_du_fichier(self) -> str:
        """Le nom derive, ou `""` tant qu'aucune chaine n'est nommee."""
        if not self.formulaire.peut_continuer:
            return ""
        try:
            return nom_de_la_mire(self.project_id,
                                  self.formulaire.saisie(CHAMP_CHAINE))
        except naming.NamingError:
            # Un libelle sans un seul caractere alphanumerique ASCII : le coeur
            # refuse de le nommer, et il a raison. On rend une chaine vide,
            # rendue par le glyphe neutre -- « non renseigne », ce qui est
            # exact -- plutot qu'un nom invente.
            return ""

    # -- rendu ---------------------------------------------------------------

    def mention_du_champ(self, cle: str) -> str:
        """La colonne de droite d'un champ : ce qui manque, ou rien.

        **La forme des deux ecrans jumeaux du Scan, portee ici** (manque
        `MQ-6`, audit du 2026-09-06). `EcranScanDepot` rend
        `Source  > ·   requis` et `EcranCalibrerLaChaine` rend
        `Scan de la page  > ·  requis` ; `E5-6` ne rendait rien, si bien que
        **rien a l'ecran ne disait que le premier champ etait obligatoire** --
        le texte existait, mais seulement derriere `F1`
        (`AIDE_PAR_CHAMP[CHAMP_CHAINE]`, « Requis, le nom qui nommera le
        fichier »).

        Le mot est **lu** d'`atelier_scan`, jamais redit ici : trois ecrans du
        depot marquent un champ requis, et une seconde redaction divergerait
        de la premiere au premier ajustement.

        Elle s'efface des que le champ porte quelque chose, comme chez le
        jumeau -- une mention `requis` qui survivrait a la saisie dirait le
        contraire de ce que l'ecran mesure. La lecture passe par `saisie()`,
        strippee, parce que c'est ce que le coeur lira : un champ de blancs
        est vide pour lui, et afficher la mention disparue sur `'   '` serait
        le meme defaut que le jumeau du dpi a deja paye.
        """
        if cle != CHAMP_CHAINE:
            return ""
        return "" if self.formulaire.saisie(cle) else MENTION_REQUIS

    def ligne_de_champ(self, cle: str) -> str:
        """Une ligne saisissable : libelle, glyphe de focus, valeur, mention.

        Le glyphe `>` marque le champ **au focus** et lui seul ; les autres
        champs portent un blanc a sa place, pour que les valeurs restent
        alignees quand le focus se deplace. **Les lignes imposees n'en portent
        jamais** (AC 8.4) : elles ne sont pas atteignables, et un glyphe de
        focus sur une ligne qu'on ne peut pas viser serait une invite morte.

        La mention passe par :func:`avec_la_mention`, la meme que les lignes
        imposees : une seconde colonne de mention sur le meme ecran serait
        exactement ce que le commentaire de `LARGEUR_DE_LA_VALEUR` refuse.
        """
        table = self.app.glyphes
        valeur = self.formulaire.saisie(cle) or table["neutre"]
        focus = table["invite"] if self.formulaire.champ == cle else " "
        return avec_la_mention(
            f"{INDENT_DU_CURSEUR}"
            f"{LIBELLES_DES_CHAMPS[cle]:<{LARGEUR_DU_LIBELLE}}"
            f"{focus} {valeur}",
            valeur, self.mention_du_champ(cle))

    def valeur_de_l_aide(self, cle: str) -> str:
        """La **valeur du contexte courant** que l'aide de ce champ cite (AC 1.1).

        La saisie **strippee** -- `saisie()`, la seule redaction du depot sur ce
        que ces champs portent vraiment : lire l'attribut brut ferait dire
        « `   ` » a l'aide la ou le coeur lit une chaine vide.

        **Aucune lecture de `self.app`** : mesurable sans terminal.
        """
        # Le mot est **lu** de `aide_de_champ`, jamais redit ici : trois
        # ecrans disent « ce champ n'a rien », et l'ecrire trois fois l'a
        # deja fait diverger (defaut `F4` de la revue du 2026-09-03).
        return self.formulaire.saisie(cle) or aide_de_champ.VALEUR_ABSENTE

    def ligne_imposee(self, libelle: str, valeur: str,
                      mention: str = "") -> str:
        """Une ligne **affichee** : libelle, valeur, mention. Aucun focus.

        Deux espaces la ou une ligne de champ porte son glyphe : c'est ce qui
        garde les valeurs des deux blocs sur la meme colonne.

        Le calage vit dans :func:`avec_la_mention`, partage avec
        :meth:`EcranMireReglages.ligne_de_champ` depuis `MQ-6`.
        """
        return avec_la_mention(
            f"{INDENT_DU_CURSEUR}{libelle:<{LARGEUR_DU_LIBELLE}}  {valeur}",
            valeur, mention)

    def lignes(self) -> list[str]:
        utile = jetons.largeur_utile(self.app.size.width)
        ascii_seul = self.app.ascii_seul
        neutre = self.app.glyphes["neutre"]
        donnees = self.donnees
        corps = [INDENT_DU_TEXTE + TITRE_DES_REGLAGES,
                 aide_de_champ.ligne_de_tete_de(
                     self, self.formulaire.champ, utile=utile,
                     indent=INDENT_DU_TEXTE, ascii_seul=ascii_seul)]
        corps += [self.ligne_de_champ(cle)
                  for cle in self.formulaire.champs()]
        corps += ["", filet(utile, FILET_IMPOSE, ascii_seul), ""]
        corps.append(self.ligne_imposee(
            LIBELLE_PASTILLES, str(donnees.pastilles),
            donnees.decomposition_longue))
        corps.append(self.ligne_imposee(
            LIBELLE_PATCHS, donnees.preset, donnees.mention_du_bandeau))
        corps.append(self.ligne_imposee(LIBELLE_FORMAT_DPI,
                                        donnees.format_et_dpi))
        corps += ["", filet(utile, FILET_A_ECRIRE, ascii_seul), ""]
        nom = self.nom_du_fichier
        colonne = len(INDENT_DU_CURSEUR) + LARGEUR_DU_LIBELLE + 2
        corps.append(self.ligne_imposee(
            LIBELLE_FICHIER,
            abreger_la_mire(nom, self.formulaire.saisie(CHAMP_CHAINE),
                            max(utile - colonne, 0), ascii_seul)
            if nom else neutre))
        corps.append(self.ligne_imposee(
            LIBELLE_DESTINATION, destination_de_la_mire(self.project_id)))
        return corps

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-mire-reglages")
        return [self._corps]

    def on_mount(self) -> None:
        self.rafraichir()

    def etat(self) -> str:
        """La phrase du refus si elle est posee, la mesure sinon.

        **La mesure reste le regime nominal** : `EPIC11-ARB-56` veut une
        ligne d'etat qui mesure, et `1 page · 164 pastilles · aucun fichier de
        ce nom sous planches/` est cette mesure. Ce que `MQ-6` ajoute est un
        regime transitoire -- la reponse a une touche qui vient d'etre
        pressee --, pas un second decor permanent.
        """
        if self._etat_a_dire:
            return self._etat_a_dire
        return ligne_d_etat_des_reglages(
            self.donnees, self.presente,
            nommable=chaine_nommable(self.formulaire.saisie(CHAMP_CHAINE))
            or not self.formulaire.saisie(CHAMP_CHAINE))

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        self._corps.update(bloc_peint(
            self.lignes(), jetons.largeur_utile(self.app.size.width), self.app))
        self.poser_etat(self.etat())
        super().rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot.

        **La branche du texte passe EN PREMIER** (`EPIC11-ARB-68`) : une lettre
        testee apres un raccourci nomme cesserait d'entrer dans le champ le jour
        ou un raccourci porte cette lettre, et l'echec serait silencieux -- il
        rendrait une valeur plausible. En sortant le texte avant toute touche
        nommee, la regle devient structurelle.
        """
        self._etat_a_dire = ""
        if caractere is not None and len(caractere) == 1 and caractere.isprintable():
            return self.formulaire.frapper(caractere)
        if touche == "backspace":
            return self.formulaire.effacer()
        if touche in ("tab", "down"):
            return self.formulaire.avancer(1)
        if touche in ("shift+tab", "up"):
            return self.formulaire.avancer(-1)
        if touche == "enter":
            return self.continuer()
        if touche == "f1":
            # **`F1` est consommee ICI quand le focus est sur un champ**
            # (AC 1.4, story 11.9) : les deux lignes de ce formulaire en sont,
            # donc elle l'est toujours, et le manuel des raccourcis ne s'ouvre
            # pas par-dessus la saisie. Le volet symetrique -- la touche qui
            # remonte hors champ -- se lit sur les ecrans qui ont une zone hors
            # formulaire ; celui-ci n'en a aucune.
            return self.aide.basculer(self.formulaire.champ)
        # `escape` et `q` ne sont pas notre affaire : la coque remonte ou
        # quitte.
        return False

    def continuer(self) -> bool:
        """`⏎` : passer au temps 2. **Jamais muette, et ce n'etait pas vrai.**

        Sans chaine nommee, la touche est consommee, le champ reste sous le
        focus, et la ligne d'etat **dit le refus** -- elle disait sa mesure du
        fichier, ce qui etait exact et ne repondait pas a la question posee.
        C'est le manque `MQ-6` de l'audit du 2026-09-06 : la garde est juste
        et documentee, c'est de la **dire** qui manquait.

        **Deux regimes de refus, deux phrases**, et une seule est posee ici :
        le champ vide rend `ETAT_CHAINE_REQUISE` en transitoire ; le champ
        rempli d'un libelle innommable garde `ETAT_CHAINE_INUTILISABLE`, que
        la mesure permanente rend deja depuis le finding `C2-2`.

        Sans rappel cable, on nomme ce qui manque plutot que de consommer la
        touche sur rien -- la difference entre « pas encore construit » et
        « casse ».
        """
        if not self.formulaire.peut_continuer:
            # **Le refus se DIT** (manque `MQ-6`). La ligne d'etat continuait
            # d'afficher sa mesure du fichier -- exacte, mais sans rapport
            # avec la question que l'operateur venait de poser --, et rien
            # hors de `F1` ne disait pourquoi `⏎ continuer` ne continuait pas.
            # Le premier jet de ce docstring appelait ce silence « jamais
            # muette » : il l'etait.
            #
            # **Mais `peut_continuer` est faux dans DEUX regimes, et un seul
            # etait muet.** Le champ vide, oui ; le champ rempli d'un libelle
            # que le coeur refuse de nommer (`---`), non -- celui-la portait
            # deja sa phrase depuis le finding `C2-2`, rendue en permanence
            # par `ligne_d_etat_des_reglages(nommable=False)`. Poser la phrase
            # generique sur les deux la **masquait**, et mentait par-dessus :
            # un nom EST saisi, il est seulement inutilisable. La mesure de
            # non-regression du 2026-09-06 l'a rendu, un vert devenu rouge sur
            # `test_C2_2_un_libelle_INNOMMABLE_ne_fait_PAS_tomber_la_TUI`.
            #
            # Le transitoire ne se pose donc que la ou le permanent se tait.
            if not self.formulaire.saisie(CHAMP_CHAINE):
                self._etat_a_dire = ETAT_CHAINE_REQUISE
            return True
        if self._sur_continuer is None:
            self.app.descendre(EcranPasEncore(TITRE_DES_REGLAGES,
                                              QUAND_LA_SUITE_DE_LA_MIRE))
            return True
        self._sur_continuer(self.formulaire)
        return True


#: L'echeance annoncee tant que le parcours de la mire n'est pas cable. Elle est
#: **propre a ce module** et non importee d'`atelier_pdf` : le cablage fera
#: importer ce module-ci par celui-la, et l'import inverse fermerait la boucle.
#: « Sans la date, on ne distingue pas "pas encore fait" de "abandonne". »
QUAND_LA_SUITE_DE_LA_MIRE = "la suite de l'atelier Pdf"


def ouvrir_les_reglages(app, project_id: str, dossier, *,
                        sur_continuer: Callable[[FormulaireDeLaMire], None],
                        formulaire: FormulaireDeLaMire | None = None
                        ) -> EcranMireReglages:
    """Monter `E5-6`. `sur_continuer` est **requis**, et c'est structurel.

    Un `Callable | None = None` assorti d'un `if ... is not None` transforme
    l'oubli du cablage en **silence** (findings `K3` et `I8`). Le rendre requis
    fait de l'oubli une erreur d'appel ; passer explicitement l'ecran « pas
    encore » reste possible et **dit** ce qui manque.
    """
    ecran = EcranMireReglages(project_id, dossier, formulaire=formulaire,
                              sur_continuer=sur_continuer)
    app.descendre(ecran)
    return ecran


# ===========================================================================
# `E5-6b` -- la confirmation. LE MEME ECRAN QUE `E5-3` (AC 8.7)
# ===========================================================================

#: Le titre du cadre, verbatim de `E5-3` **et** de `E5-6b`. Les deux ecrans
#: portent le meme parce que ce sont le meme point de jugement.
TITRE_A_ECRIRE = "À écrire"

#: Les libelles du cartouche de `E5-6b`, verbatim (l. 6-13).
LIBELLE_PLANCHE = "Planche de calibration"
LIBELLE_CHAINE = "Chaîne"
LIBELLE_COMMENTAIRE = "Commentaire"
LIBELLE_NOM_DU_FICHIER = "Nom du fichier"

#: Les trois issues, **dans l'ordre de la maquette**, et leurs cles. `Générer`
#: est la seule qui ecrit ; `ChoixExclusif` pose donc le curseur au montage sur
#: `Modifier les réglages`, qui est ce que la maquette dessine (`▸` l. 19).
#: L'ordre de la liste ne bouge pas pour autant -- c'est le curseur qui se
#: place, pas la liste qui se reordonne (`EPIC11-ARB-7`, `EPIC11-ARB-45`).
ISSUE_GENERER = "generer"
ISSUE_MODIFIER = "modifier"
ISSUE_ANNULER = "annuler"
LIBELLE_GENERER = "Générer"
LIBELLE_MODIFIER = "Modifier les réglages"
LIBELLE_ANNULER = "Annuler"


def choix_de_la_confirmation() -> ChoixExclusif:
    """Les trois issues de `E5-6b`. **Ensemble exact, et une seule ecrit.**"""
    return ChoixExclusif([
        Issue(ISSUE_GENERER, LIBELLE_GENERER, ecrit=True),
        Issue(ISSUE_MODIFIER, LIBELLE_MODIFIER),
        Issue(ISSUE_ANNULER, LIBELLE_ANNULER),
    ])


def panneau_de_la_confirmation(formulaire: FormulaireDeLaMire,
                               project_id: str,
                               donnees: DonneesImposees | None = None
                               ) -> Panneau:
    """Le cartouche chiffre de `E5-6b`, **dans l'ordre de `E5-3`**.

    Ce qui sort, puis ou ca va. Le **nom vient apres**, et il n'est pas ici :
    `EcranChiffre.lignes_du_panneau` ne rend que les lignes chiffrees -- les
    noms y sont des widgets a part, pour qu'un nom refuse puisse porter sa
    propre couleur. `EcranMireConfirmation` le compose donc a la largeur
    courante, ou l'abregement du slug peut se calculer.

    **Aucune ligne de taille** : personne n'a pese une mire, et `E5-3` porte
    `~ 470 Mo (majorant)` parce qu'un majorant de planches se calcule. **Aucun
    majorant** par consequent, et c'est mesurable : `Panneau.porte_un_majorant`
    rend faux.
    """
    donnees = donnees_imposees() if donnees is None else donnees
    lignes = [
        LigneChiffree(LIBELLE_PLANCHE,
                      f"{donnees.pages} {UNITE_DES_PDF}"
                      f"{SEPARATEUR}{donnees.pages_lisibles}"),
        LigneChiffree(LIBELLE_CHAINE, formulaire.saisie(CHAMP_CHAINE)),
    ]
    commentaire = formulaire.saisie(CHAMP_COMMENTAIRE)
    if commentaire:
        # La ligne disparait quand le champ est vide : un `Commentaire` suivi de
        # rien se lit comme une donnee perdue, alors que l'absence de
        # commentaire est un cas nominal -- le coeur l'accepte a `None`.
        lignes.append(LigneChiffree(LIBELLE_COMMENTAIRE, commentaire))
    lignes += [
        LigneChiffree(LIBELLE_PASTILLES,
                      f"{donnees.pastilles}    {donnees.decomposition}"),
        LigneChiffree(LIBELLE_PATCHS, donnees.preset),
        LigneChiffree(LIBELLE_FORMAT_MARGE_DPI, donnees.format_marge_et_dpi),
        LigneChiffree(LIBELLE_DESTINATION, destination_de_la_mire(project_id)),
    ]
    return Panneau(TITRE_A_ECRIRE, lignes)


class EcranMireConfirmation(EcranChiffre):
    """`E5-6b` -- l'`EcranChiffre` livre, avec le bandeau et le nom de la mire.

    Une sous-classe et **presque rien d'autre**, comme `EcranResultatDuScan` :
    le cartouche, les trois issues, le curseur pose au montage sur celle qui
    n'ecrit pas et la navigation sont ceux de `execution.EcranChiffre`, mesures
    par la story 11.1. `execution.py` n'est **pas modifie** -- c'est le module
    partage par les quatre ateliers, et le toucher serait la contention que la
    regle de decoupage interdit.

    Ce qu'elle redonne tient en trois choses : le **titre**, segment du milieu
    du bandeau ; la **ligne de raccourcis**, qui ne porte pas `Tab` -- cet ecran
    n'a aucun nom editable (AC 6.3a, `EPIC11-ARB-141`) ; et le **bloc du nom**,
    compose a la largeur courante pour que le condensat ne soit jamais elide.

    **Un ecart maquette / produit, dit plutot que tu.** La maquette porte en
    ligne d'etat `1 PDF · 1 page · 164 pastilles — rien n'a encore été écrit`,
    la ou `EcranChiffre.etat()` rend `panneau.RIEN_ECRIT` seul. `E5-3` porte le
    **meme** ecart, dans les memes termes. Il n'est pas corrige ici : le
    corriger d'un seul cote ferait diverger deux ecrans qu'Egan a demandes
    identiques, et le corriger des deux se fait dans `execution.py`, que ce lot
    n'a pas le droit de toucher. Un banc epingle l'etat courant, si bien que la
    liaison de la vague le verra plutot que de le decouvrir.
    """

    titre = PALIER_DE_LA_MIRE
    raccourcis = RACCOURCIS_MIRE_JUGEMENT

    def __init__(self, formulaire: FormulaireDeLaMire, project_id: str = "",
                 donnees: DonneesImposees | None = None,
                 sur_issue: Callable[[Issue], None] | None = None) -> None:
        donnees = donnees_imposees() if donnees is None else donnees
        super().__init__(
            panneau_de_la_confirmation(formulaire, project_id, donnees),
            choix_de_la_confirmation(), sur_issue=sur_issue,
            objet=TEMPS_D_ECRITURE)
        self.formulaire = formulaire
        self.project_id = project_id
        self.donnees = donnees

    def lignes_du_panneau(self) -> list[str]:
        """Les chiffres, puis le nom du fichier -- **en dernier**.

        `panneau.Panneau` explique l'ordre : les noms sont en dernier « parce
        qu'ils sont ce que l'operateur edite, et qu'un bloc editable au milieu
        d'un tableau de chiffres se cherche ». Ici il n'est **pas** editable
        (AC 8.3), et il reste quand meme en dernier : deux confirmations qui
        rangeraient leurs lignes differemment seraient deux ecrans a apprendre.

        **Le nom est abrege par son slug** (:func:`abreger_la_mire`), jamais au
        milieu : le condensat porte l'identite de la chaine, et deux libelles
        qui se normalisent en un meme slug ne se separent que par lui.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        largeur = jetons.largeur_de_cartouche(self.app.size.width)
        chaine = self.formulaire.saisie(CHAMP_CHAINE)
        nom = abreger_la_mire(
            nom_de_la_mire(self.project_id, chaine), chaine,
            max(largeur - len(INDENT_DU_TEXTE), 0), ascii_seul)
        libelle = (jetons.replier_ascii(LIBELLE_NOM_DU_FICHIER) if ascii_seul
                   else LIBELLE_NOM_DU_FICHIER)
        return super().lignes_du_panneau() + [
            "", libelle, INDENT_DU_TEXTE + nom]


def ouvrir_la_confirmation(app, formulaire: FormulaireDeLaMire,
                           project_id: str, *,
                           sur_issue: Callable[[Issue], None],
                           donnees: DonneesImposees | None = None
                           ) -> EcranMireConfirmation:
    """Monter `E5-6b`. `sur_issue` est **requis** -- voir :func:`ouvrir_les_reglages`."""
    ecran = EcranMireConfirmation(formulaire, project_id, donnees,
                                  sur_issue=sur_issue)
    app.descendre(ecran)
    return ecran


# ===========================================================================
# `E5-6c` -- la generation : UN ROTOR, aucune barre, aucun journal (AC 8.6)
# ===========================================================================

#: Le titre de l'ecran, verbatim de la maquette (l. 5).
TITRE_DE_LA_GENERATION = "Génération en cours — planche de calibration"

#: Ce que la colonne de droite de la ligne du fichier dit. **Un etat, pas un
#: temps** : personne n'a chronometre la composition d'une mire, et
#: `EPIC7-ARB-67` interdit de rendre une duree tant qu'aucune mesure n'existe.
MENTION_EN_COURS = "en cours"

#: Ce que la ligne d'etat dit pendant la generation. **Ce que l'ecran sait**, et
#: rien de plus : une page, son cardinal de pastilles, et le fait qu'elle n'est
#: pas encore ecrite (`EPIC11-ARB-56`, un constat).
ETAT_PAS_ENCORE_ECRITE = "la page n'est pas encore écrite"

#: Le separateur qui detache le constat des deux mesures qui le precedent,
#: verbatim des maquettes (`1 page · 164 pastilles — la page ...`).
TIRET_DE_L_ETAT = " — "

#: La periode du rotor, en secondes. Quatre dessins : le cycle complet dure
#: quatre fois cette valeur. Assez lent pour qu'un terminal lent suive, assez
#: rapide pour qu'on voie que ca bouge.
PERIODE_DU_ROTOR = 0.25

#: Ce que l'interruption ouvre tant que `T6-1` n'est pas livre (lot I de la
#: meme story). `Échap interrompre` est **annonce** par la ligne de raccourcis :
#: le laisser sans destination en ferait une touche inerte, exactement le
#: defaut que ce module documente en tete.
NOM_DE_L_INTERRUPTION = "Interrompre la génération"


class EcranMireEnCours(ObjetTravaille, Palier):
    """`E5-6c` -- une ligne, un rotor, et rien qui pretende compter.

    **Ce n'est pas `execution.EcranExecution`**, et ce n'est pas un oubli : cet
    ecran-la porte une barre, un journal et `Tab journal`, c'est-a-dire les
    trois choses que la mesure du chemin de production a retirees d'ici. Le
    sous-classer pour en desactiver les trois quarts aurait laisse ses promesses
    dans la ligne de raccourcis.

    **Le rotor ne remplace aucun compte** : il n'y a rien a compter. Le canal de
    progression du coeur emet un jalon par page, une mire fait une page, et une
    barre a deux etats n'informe pas -- elle occupe.
    """

    titre = PALIER_DE_LA_MIRE
    raccourcis = RACCOURCIS_MIRE_EN_COURS
    objet = TEMPS_D_ECRITURE

    #: Un passage : la duree d'une tache, pas une station.
    TRANSITOIRE = True

    def __init__(self, nom: str = "", chaine: str = "",
                 donnees: DonneesImposees | None = None,
                 sur_interruption: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.nom = nom
        self.chaine = chaine
        self.donnees = donnees_imposees() if donnees is None else donnees
        self._sur_interruption = sur_interruption
        #: Le pas du rotor. Il ne se remet **jamais** a zero : le modulo est
        #: fait par `jetons.rotor`, precisement pour qu'un ecran qui compte ses
        #: propres pas ne rende pas un `IndexError` au quatrieme tour.
        self.pas = 0
        #: Le minuteur qui fait tourner le rotor, **retenu** et non oublie.
        #:
        #: Deux motifs, et le second a ete paye. **Le premier** : un minuteur
        #: qu'on ne tient pas ne s'arrete pas -- il continue d'appeler
        #: :meth:`avancer_le_rotor` sur un ecran demonte, donc de redessiner un
        #: arbre de widgets detruit. C'est le meme geste que
        #: `EcranExecution.on_unmount`, qui se desabonne.
        #:
        #: **Le second, et c'est une lecon de banc.** Sans cette poignee, la
        #: seule facon de mesurer le rotor etait d'attendre que l'horloge le
        #: fasse tourner -- et un banc qui attend mesure l'attente. Deux tests
        #: du lot H se sont ainsi contredits : l'un voulait `pas` immobile
        #: apres une frappe, l'autre le voulait mobile, et **les deux
        #: dependaient du meme minuteur** qui tourne pendant les `await`. Les
        #: deux etaient verts en isolation et rouges sous charge, sans qu'aucun
        #: code ne change. La poignee permet de **figer** le mecanisme et de
        #: mesurer ce qui le fait avancer, plutot que le temps qui passe.
        self.minuteur = None

    # -- le rotor ------------------------------------------------------------

    def glyphe_du_rotor(self, ascii_seul: bool | None = None) -> str:
        """Le dessin courant, **lu de `jetons`** et jamais recompose ici."""
        if ascii_seul is None:
            ascii_seul = getattr(self.app, "ascii_seul", False)
        return jetons.rotor(self.pas, ascii_seul)

    def avancer_le_rotor(self) -> None:
        """Un pas de plus, et on redessine. C'est **tout** ce qui bouge ici.

        Appelee par un intervalle `textual` monte dans :meth:`on_mount`, et
        appelable a la main : c'est ce qui rend le mouvement mesurable sans
        terminal et sans horloge.
        """
        self.pas += 1
        self.rafraichir()

    # -- rendu ---------------------------------------------------------------

    def ligne_du_fichier(self, utile: int) -> str:
        """`◐ projet_demo_…_calibration.pdf  1 page   en cours`.

        Le nom est abrege **par le slug** (:func:`abreger_la_mire`) : le
        condensat porte l'identite de la chaine, et une ligne d'execution qui le
        mangerait montrerait un fichier qu'on ne peut plus reconnaitre sur le
        disque.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        droite = f"{self.donnees.pages_lisibles}   {MENTION_EN_COURS}"
        tete = f"{INDENT_DU_CURSEUR}{self.glyphe_du_rotor(ascii_seul)} "
        place = max(utile - jetons.colonnes(tete)
                    - jetons.colonnes(droite) - jetons.CREUX_MINIMAL, 0)
        nom = abreger_la_mire(self.nom, self.chaine, place, ascii_seul)
        gauche = tete + nom
        creux = utile - jetons.colonnes(gauche) - jetons.colonnes(droite)
        return gauche + " " * max(creux, jetons.CREUX_MINIMAL) + droite

    def lignes(self) -> list[str]:
        utile = jetons.largeur_utile(self.app.size.width)
        return [INDENT_DU_TEXTE + TITRE_DE_LA_GENERATION, "",
                self.ligne_du_fichier(utile)]

    def etat(self) -> str:
        """`1 page · 164 pastilles — la page n'est pas encore écrite`."""
        return (SEPARATEUR.join((self.donnees.pages_lisibles,
                                 self.donnees.pastilles_lisibles))
                + TIRET_DE_L_ETAT + ETAT_PAS_ENCORE_ECRITE)

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-mire-en-cours")
        return [self._corps]

    def on_mount(self) -> None:
        self.minuteur = self.set_interval(PERIODE_DU_ROTOR,
                                          self.avancer_le_rotor)
        self.rafraichir()

    def on_unmount(self) -> None:
        """Arreter le minuteur. Un ecran demonte n'a plus rien a faire tourner.

        Symetrique de :meth:`on_mount`, et meme motif qu'`EcranExecution` qui se
        desabonne : un rappel qui survit a son ecran ecrit dans un arbre de
        widgets detruit.
        """
        if self.minuteur is not None:
            self.minuteur.stop()
            self.minuteur = None

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        self._corps.update(bloc_peint(
            self.lignes(), jetons.largeur_utile(self.app.size.width), self.app))
        self.poser_etat(self.etat())
        super().rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if evenement.key == "escape":
            # **Arrete ici**, comme sur `EcranExecution` : laisser l'application
            # voir la touche depilerait la generation en cours, c'est-a-dire
            # ferait disparaitre la tache de la vue au lieu de demander quoi en
            # faire.
            evenement.stop()
            self.interrompre()

    def interrompre(self) -> None:
        """`Échap` : demander quoi faire de la generation. **Jamais muette.**"""
        if self._sur_interruption is None:
            self.app.descendre(EcranPasEncore(NOM_DE_L_INTERRUPTION,
                                              QUAND_LA_SUITE_DE_LA_MIRE))
            return
        self._sur_interruption()


def ouvrir_la_generation(app, nom: str, chaine: str, *,
                         sur_interruption: Callable[[], None],
                         donnees: DonneesImposees | None = None
                         ) -> EcranMireEnCours:
    """Monter `E5-6c`. `sur_interruption` est **requis**."""
    ecran = EcranMireEnCours(nom, chaine, donnees,
                             sur_interruption=sur_interruption)
    app.descendre(ecran)
    return ecran


# ===========================================================================
# `E5-6d` -- une mire du meme nom existe deja (AC 8.5)
# ===========================================================================

#: Le titre du cadre, verbatim de la maquette (l. 6).
TITRE_MIRE_EXISTE = "Cette mire existe déjà"

#: Les deux libelles chiffres du cartouche (l. 9-10).
LIBELLE_ECRIT_LE = "Écrit le"
LIBELLE_CONTIENT = "Contient"

#: Le paragraphe du cartouche, **verbatim** de la maquette (l. 12-14), replie a
#: la main sur trois lignes comme elle le dessine.
#:
#: Il dit ce que le nom ne porte pas, et c'est la mesure qui fonde les trois
#: issues : `build_calibration_pdf_filename` ne prend que le projet et le
#: libelle de chaine, alors que **huit** parametres de geometrie plus le
#: commentaire font varier la page sans entrer dans son nom. « Deux tirages de
#: la meme chaine sont le meme document » est donc **faux**, et c'est ce qui
#: rend la premiere issue possible.
PARAGRAPHE_DU_NOM = (
    "Le nom ne porte que le projet et la chaîne. La géométrie, le",
    "jeu de patchs et le commentaire n'y entrent pas : deux mires",
    "de la même chaîne réglées autrement se disputent ce fichier.",
)

#: Les **TROIS** issues, ensemble exact (`EPIC11-ARB-89` : « jamais une, toujours
#: au moins deux, et jamais zero »). Le coeur les porte deja, verbatim de son
#: refus : donner un autre `--chaine`, relancer avec `--overwrite`, ou supprimer
#: le fichier -- la TUI rend les deux premieres et laisse la suppression a la
#: story 11.11, qui la livre proprement.
#:
#: **Il n'y a PAS de « créer la version suivante »**, et c'est une absence
#: mesuree : la mire ne declare ni rush, ni lot, ni cadence (`EPIC5-ARB-82`),
#: donc elle n'a **pas de lot dont numeroter les tirages**. La sortie non
#: destructive est le changement de nom de chaine, qui entre dans le nom et
#: ecrit a cote.
ISSUE_AUTRE_CHAINE = "changer-la-chaine"
ISSUE_REMPLACER = "remplacer"
LIBELLE_AUTRE_CHAINE = "Changer le nom de la chaîne"
LIBELLE_REMPLACER = "Remplacer cette mire"

#: Les mentions de la colonne de droite des issues (l. 17-18). Celle de
#: l'ecrasement porte le glyphe d'avertissement **et** la date de ce qui
#: disparait : c'est l'avertissement qu'`EPIC11-ARB-89` exige avant une ecriture
#: destructive consciente.
MENTION_AUTRE_CHAINE = "écrit à côté, sans rien effacer"
MENTION_REMPLACER = "efface celle du {date}"
MENTION_REMPLACER_SANS_DATE = "efface la mire déjà écrite"

#: Ce que la ligne d'etat de `E5-6d` dit du rang. **Une absence, dite.** Un
#: ecran de conflit qui la tairait laisserait chercher le `_v2` que les tirages
#: de planches portent.
AUCUN_RANG = "aucun rang pour cet objet"

#: Le participe accorde des pastilles ecrites, pour la ligne d'etat.
PARTICIPE_DES_PASTILLES = {False: "écrite", True: "écrites"}


def choix_du_conflit() -> ChoixExclusif:
    """Les trois issues de `E5-6d`. **Ensemble exact, une seule ecrit.**

    Le curseur part sur `Changer le nom de la chaîne`, qui n'ecrit pas : c'est
    `ChoixExclusif` qui le pose, jamais ce module -- `EPIC11-ARB-7` est un
    invariant de construction, et le reecrire ici en ferait une seconde
    redaction qui pourrait diverger.
    """
    return ChoixExclusif([
        Issue(ISSUE_AUTRE_CHAINE, LIBELLE_AUTRE_CHAINE),
        Issue(ISSUE_REMPLACER, LIBELLE_REMPLACER, ecrit=True),
        Issue(ISSUE_ANNULER, LIBELLE_ANNULER),
    ])


def panneau_du_conflit(presente: MirePresente,
                       donnees: DonneesImposees | None = None) -> Panneau:
    """Le cartouche chiffre de `E5-6d` : ce qui est deja la.

    **Aucun rang, aucune taille, aucune duree** -- les trois absences de cet
    atelier. `Écrit le` disparait quand le disque n'a rien dit, plutot que
    d'afficher une date inventee : c'est le meme geste que le pied du menu de
    l'atelier, ou un segment qu'on ne sait pas remplir disparait.

    Le nom du fichier et le paragraphe qui explique le conflit ne sont pas ici :
    `EcranMireExiste` les compose a la largeur courante, le premier parce que
    son abregement en depend, le second parce qu'il encadre les chiffres au lieu
    de les suivre.
    """
    donnees = donnees_imposees() if donnees is None else donnees
    lignes = []
    if presente.horodatage:
        lignes.append(LigneChiffree(LIBELLE_ECRIT_LE, presente.horodatage))
    lignes.append(LigneChiffree(
        LIBELLE_CONTIENT,
        SEPARATEUR.join((donnees.pages_lisibles,
                         donnees.pastilles_lisibles))))
    return Panneau(TITRE_MIRE_EXISTE, lignes)


def ligne_d_etat_du_conflit(presente: MirePresente,
                            donnees: DonneesImposees,
                            ascii_seul: bool = False) -> str:
    """`▲  1 page · 164 pastilles écrites le 27/08 · aucun rang pour cet objet`.

    Le glyphe **ouvre la ligne**, comme sur toutes les lignes d'etat qui portent
    un etat : `jetons.jeton_d_etat` exige qu'il ouvre une colonne pour teinter la
    ligne, et `DESIGN.md` section 5 veut les deux canaux, jamais la couleur
    seule. Le segment de date disparait quand le disque n'a rien dit.
    """
    glyphe = jetons.glyphes(ascii_seul)["substitute"]
    ecrites = (f"{donnees.pastilles} "
               f"{PLURIEL_DES_PASTILLES[donnees.pastilles > 1]} "
               f"{PARTICIPE_DES_PASTILLES[donnees.pastilles > 1]}")
    if presente.date:
        ecrites += f" le {presente.date}"
    return (f"{glyphe}  "
            + SEPARATEUR.join((donnees.pages_lisibles, ecrites, AUCUN_RANG)))


class EcranMireExiste(EcranChiffre):
    """`E5-6d` -- le conflit de la mire, sur le patron du point de jugement.

    Elle redonne trois choses a `EcranChiffre`, et pas une de plus :

    * le **nom du fichier en tete du cartouche**, marque du glyphe
      d'avertissement, et le **paragraphe** qui dit ce que ce nom ne porte pas.
      Le nom ouvre le cartouche parce qu'il en est le sujet -- un cartouche qui
      commencerait par une date ferait chercher de quoi elle parle ;
    * la **colonne de mention** des issues : « ecrit a cote, sans rien effacer »
      contre « ▲ efface celle du 27/08 ». Sans elle, les deux premieres issues
      se distingueraient par leur seul libelle, au moment ou la distinction
      coute le plus cher ;
    * la **ligne d'etat**, qui porte l'absence de rang.
    """

    titre = PALIER_DE_LA_MIRE
    raccourcis = RACCOURCIS_MIRE_JUGEMENT

    def __init__(self, presente: MirePresente, chaine: str = "",
                 donnees: DonneesImposees | None = None,
                 sur_issue: Callable[[Issue], None] | None = None) -> None:
        donnees = donnees_imposees() if donnees is None else donnees
        super().__init__(panneau_du_conflit(presente, donnees),
                         choix_du_conflit(), sur_issue=sur_issue,
                         objet=TEMPS_D_ECRITURE)
        self.presente = presente
        self.chaine = chaine
        self.donnees = donnees

    def lignes_du_panneau(self) -> list[str]:
        """Le nom, les chiffres, le paragraphe -- dans cet ordre.

        Le nom est abrege **par son slug** (:func:`abreger_la_mire`) : c'est le
        fichier qu'on va peut-etre effacer, et un condensat mange le rendrait
        impossible a reconnaitre sur le disque -- exactement au moment ou il
        faut etre sur de viser le bon.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        table = jetons.glyphes(ascii_seul)
        largeur = jetons.largeur_de_cartouche(self.app.size.width)
        tete = f"{table['substitute']} "
        nom = abreger_la_mire(self.presente.chemin.name, self.chaine,
                              max(largeur - jetons.colonnes(tete), 0),
                              ascii_seul)
        paragraphe = [jetons.replier_ascii(ligne) if ascii_seul else ligne
                      for ligne in PARAGRAPHE_DU_NOM]
        return ([tete + nom, ""] + super().lignes_du_panneau()
                + [""] + paragraphe)

    def mentions_des_issues(self, ascii_seul: bool = False) -> dict[str, str]:
        """Ce que chaque issue fait au fichier deja la. `Annuler` n'en a pas.

        La mention de l'ecrasement porte le glyphe d'avertissement **et** la
        date de ce qui disparait. Sans date mesurable, elle garde le glyphe et
        prend sa redaction sans date : une mention qui annoncerait « efface
        celle du » suivi de rien serait pire qu'une phrase plus courte.
        """
        glyphe = jetons.glyphes(ascii_seul)["substitute"]
        efface = (MENTION_REMPLACER.format(date=self.presente.date)
                  if self.presente.date else MENTION_REMPLACER_SANS_DATE)
        mentions = {ISSUE_AUTRE_CHAINE: MENTION_AUTRE_CHAINE,
                    ISSUE_REMPLACER: f"{glyphe} {efface}"}
        if not ascii_seul:
            return mentions
        # **Le repli precede la mesure**, comme partout ou une largeur se
        # calcule : `jetons.ajuster` replierait au dessin, donc apres que le
        # creux a ete compte, et une mention dont le repli ALLONGE le texte
        # deborderait de la difference.
        return {cle: jetons.replier_ascii(texte)
                for cle, texte in mentions.items()}

    def rendu_des_issues(self) -> list[str]:
        """Les trois issues, chacune avec sa mention calee a droite.

        Le rendu des issues lui-meme vient de `ChoixExclusif` -- le glyphe de
        curseur, sa position, l'ordre -- et n'est pas recompose : seule la
        colonne de droite est ajoutee.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        utile = jetons.largeur_utile(self.app.size.width)
        mentions = self.mentions_des_issues(ascii_seul)
        rendues = []
        for issue, ligne in zip(self.choix.issues,
                                self.choix.rendu(ascii_seul=ascii_seul)):
            if ascii_seul:
                ligne = jetons.replier_ascii(ligne)
            mention = mentions.get(issue.cle, "")
            if not mention:
                rendues.append(ligne)
                continue
            creux = utile - jetons.colonnes(ligne) - jetons.colonnes(mention)
            rendues.append(ligne + " " * max(creux, jetons.CREUX_MINIMAL)
                           + mention)
        return rendues

    def etat(self) -> str:
        """La ligne d'etat du conflit, **sauf** quand une validation est refusee.

        Le refus prime : c'est la seule chose qui vient de se passer, et le
        constat permanent redevient lisible au dessin suivant. C'est l'ordre que
        `EcranChiffre.etat` pose deja pour les quatre ateliers.
        """
        if self._refus_annonce is not None:
            return self._refus_annonce
        return ligne_d_etat_du_conflit(
            self.presente, self.donnees,
            getattr(self.app, "ascii_seul", False))

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """La frappe imprimable est **consommee** (`EPIC11-ARB-45` / `-126`).

        Mesure du 2026-09-06, sur le parcours reel : depuis `E5-6d`, un `q`
        **fermait l'application** (`app.is_running` passe a faux) alors que la
        ligne de raccourcis de cet ecran n'annonce que
        `⏎ valider  ↑↓ choisir  Échap retour  F1 aide` -- aucune sortie par
        lettre. Le conflit n'etait pas tranche, la mire d'origine restait sur
        le disque, et le formulaire de `E5-6` disparaissait avec l'application :
        « laisser remonter `q` fermerait l'application sur une touche que rien
        n'annonce », ce que les cinq autres ecrans de conflit du depot
        empechent deja, chacun dans son `traiter`.

        **Le correctif est ici et non dans `EcranChiffre`**, dont le clavier
        est partage par les confirmations et les formulaires des quatre
        ateliers : leur docstring assume que `q` remonte a l'application, et le
        changer les emporterait tous. Un ecran de conflit, lui, est un point de
        jugement dont on ne sort que par une issue ou par `Échap`.

        On **delegue d'abord** : la classe mere garde son mode d'edition des
        noms, ou la lettre entre dans le champ au lieu d'etre jetee. Ce n'est
        que la frappe qu'elle laisse passer qui est consommee ici.
        """
        if super().traiter(touche, caractere):
            return True
        if caractere and caractere.isprintable():
            return True
        return False


def ouvrir_le_conflit(app, presente: MirePresente, chaine: str, *,
                      sur_issue: Callable[[Issue], None],
                      donnees: DonneesImposees | None = None
                      ) -> EcranMireExiste:
    """Monter `E5-6d`. `sur_issue` est **requis**."""
    ecran = EcranMireExiste(presente, chaine, donnees, sur_issue=sur_issue)
    app.descendre(ecran)
    return ecran


# ===========================================================================
# `E5-6e` -- le resultat (AC 8.7)
# ===========================================================================

#: Le titre du cadre, verbatim de la maquette (l. 6).
TITRE_ECRIT = "Écrit"

#: Les libelles du cartouche (l. 9-11).
LIBELLE_EMPLACEMENT = "Emplacement"

#: Ce que la mire sert, verbatim de la maquette (l. 13-14). **Ce n'est pas un
#: conseil d'usage en ligne d'etat** -- `EPIC11-ARB-56` l'y interdirait -- c'est
#: le corps du compte rendu, ou il a sa place : une mire seule ne sert a rien,
#: et le seul moment ou l'operateur peut l'apprendre est celui ou il vient d'en
#: produire une.
PROSE_DE_LA_MIRE = (
    "À imprimer AVEC les planches, puis à scanner UNE fois : c'est",
    "l'atelier Scan qui en tire le profil de cette chaîne.",
)

#: Les trois suites, **dans l'ordre de la maquette** (l. 16-18).
#: `EcranResultat` ajoute lui-meme `Retour aux ateliers` en dernier s'il
#: manque (`EPIC11-ARB-13`) : on ne l'ecrit donc pas ici, sous peine de le voir
#: deux fois.
SUITE_DOSSIER = "Ouvrir le dossier"
SUITE_AUTRE_MIRE = "Générer une autre mire"
SUITE_PLANCHES = "Mettre des lots en planches"

#: Ce que la ligne d'etat du resultat dit. **Des chiffres mesures**, plus
#: aucun majorant : le travail est fait (story 11.1, AC 8.2).
AUCUN_REFUS = "aucun refus"
PARTICIPE_DES_PAGES = {False: "écrite", True: "écrites"}


def suites_du_resultat() -> list[str]:
    """Les trois suites de `E5-6e`. **Ensemble exact**, et chacune mene ailleurs.

    `Générer une autre mire` revient au temps 1 de ce parcours ; `Mettre des
    lots en planches` passe a l'autre entree du menu de l'atelier. Les deux sont
    contextuelles au sens de l'AC 8.7 : elles nomment ce que l'operateur peut
    faire **de cette mire-la**, et pas un menu generique.
    """
    return [SUITE_DOSSIER, SUITE_AUTRE_MIRE, SUITE_PLANCHES]


def panneau_du_resultat(chemin, chaine: str, project_id: str,
                        donnees: DonneesImposees | None = None,
                        largeur: int = jetons.LARGEUR_PLANCHER,
                        ascii_seul: bool = False) -> Panneau:
    """Le cartouche de `E5-6e` : les chiffres **reels**, et aucun majorant.

    La premiere ligne est le fichier ecrit, ouverte par le glyphe de l'etat
    `complete` -- c'est le sujet du compte rendu, et le glyphe le double comme
    `DESIGN.md` section 5 l'exige. La ligne vide qui la suit est une
    `LigneChiffree` sans libelle ni valeur : `Panneau` ne sait pas espacer ses
    lignes, et c'est la forme la moins couteuse pour lui faire rendre la
    respiration que la maquette dessine.

    **Le nom est abrege ICI, a la construction**, et c'est un ecart assume avec
    les quatre autres ecrans de ce module. `EcranResultat` consomme
    `Panneau.rendu` en trois endroits -- le corps, la hauteur de journal
    disponible, le rang du curseur --, et surcharger le premier seul ferait
    diverger les deux autres : le curseur designerait une ligne et la validation
    en ouvrirait une autre. On paie donc un panneau compose a la largeur du
    montage, comme `atelier_scan_resultat.panneau_du_resultat` le fait deja avec
    son mode d'affichage.

    Le budget est **derive** de ce que `LigneChiffree.rendu` laissera au
    libelle : la largeur du cartouche, moins le creux minimal, moins le chiffre,
    moins le glyphe et son espace. Sans ce calcul, `abreger_nom` couperait le
    nom **au milieu** -- c'est-a-dire dans le condensat.
    """
    donnees = donnees_imposees() if donnees is None else donnees
    unite = PLURIEL_DES_PAGES[donnees.pages > 1]
    tete = f"{jetons.glyphes(ascii_seul)['complete']} "
    budget = (jetons.largeur_de_cartouche(largeur) - jetons.CREUX_MINIMAL
              - jetons.colonnes(f"{donnees.pages} {unite}")
              - jetons.colonnes(tete))
    nom = abreger_la_mire(Path(chemin).name, chaine, max(budget, 0), ascii_seul)
    return Panneau(TITRE_ECRIT, [
        LigneChiffree(tete + nom, donnees.pages, unite=unite),
        LigneChiffree("", ""),
        LigneChiffree(LIBELLE_CHAINE, chaine),
        LigneChiffree(LIBELLE_PASTILLES,
                      f"{donnees.pastilles}      {donnees.decomposition}"),
        LigneChiffree(LIBELLE_EMPLACEMENT, destination_de_la_mire(project_id)),
    ], noms=list(PROSE_DE_LA_MIRE))


def ligne_d_etat_du_resultat(donnees: DonneesImposees,
                             ascii_seul: bool = False) -> str:
    """`●  1 page écrite · 164 pastilles · aucun refus`."""
    glyphe = jetons.glyphes(ascii_seul)["complete"]
    pages = (f"{donnees.pages} {PLURIEL_DES_PAGES[donnees.pages > 1]} "
             f"{PARTICIPE_DES_PAGES[donnees.pages > 1]}")
    return (f"{glyphe}  "
            + SEPARATEUR.join((pages, donnees.pastilles_lisibles,
                               AUCUN_REFUS)))


class EcranMireEcrite(EcranResultat):
    """`E5-6e` -- l'`EcranResultat` livre, avec le bandeau de la mire.

    Une sous-classe et **rien d'autre**, exactement comme `EcranResultatDuScan`.
    Elle ne redonne que le **titre**, segment du milieu du bandeau ; la droite
    reste vide, la maquette portant un bandeau nu -- le travail est fini, il n'y
    a plus de temps a annoncer.

    **La ligne de raccourcis est contextuelle, et la base la tient deja** : sans
    journal passe, `Tab journal` n'est ni annonce ni traite. C'est la moitie de
    la promesse que le finding `I8` avait trouvee cassee dans l'autre sens.

    **L'ecart maquette / produit que ce docstring epinglait est FERME**
    (`EPIC11-ARB-140`, 2026-09-02). Il disait : « la maquette annonce `F1 aide`
    la ou `execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL` annonce `Q quitter` », et
    concluait que le corriger ici seul ferait diverger les quatre ecrans de
    resultat du depot. C'etait juste : la correction a donc ete faite **dans
    `execution.py`**, d'ou les quatre l'heritent d'un coup. Cet ecran n'a rien
    eu a changer, ce qui est la preuve que le diagnostic tenait.
    """

    titre = PALIER_DE_LA_MIRE


def ouvrir_le_resultat(app, chemin, chaine: str, project_id: str, *,
                       sur_suite: Callable[[str], None],
                       journal: Journal | None = None,
                       donnees: DonneesImposees | None = None
                       ) -> EcranMireEcrite:
    """Monter `E5-6e`. `sur_suite` est **requis**.

    `journal` est celui de la generation qui vient de finir. Il est **facultatif
    et il le reste** : le chemin de production n'emet que deux lignes -- le
    demarrage et l'ecriture --, et un journal absent est un cas nominal. Sans
    lui, la ligne de raccourcis n'annonce pas `Tab journal`, et c'est ce qui
    empeche d'annoncer une touche inerte.
    """
    donnees = donnees_imposees() if donnees is None else donnees
    ascii_seul = getattr(app, "ascii_seul", False)
    ecran = EcranMireEcrite(
        panneau_du_resultat(chemin, chaine, project_id, donnees,
                            app.size.width, ascii_seul),
        suites_du_resultat(), sur_suite=sur_suite, journal=journal)
    app.descendre(ecran)
    # **`poser_etat` APRES le montage**, jamais avant : la ligne d'etat est
    # posee sur l'ecran monte, et un ecran pas encore empile la perdrait au
    # premier dessin.
    ecran.poser_etat(ligne_d_etat_du_resultat(donnees, ascii_seul))
    return ecran


__all__ = [
    "AIDE_PAR_CHAMP",
    "avec_la_mention",
    "ARGUMENTS_DU_COEUR",
    "AUCUN_RANG",
    "AUCUN_REFUS",
    "CHAMP_CHAINE",
    "CHAMP_COMMENTAIRE",
    "DECOMPOSITION_COURTE",
    "DECOMPOSITION_LONGUE",
    "DOSSIER_DE_LA_MIRE",
    "ETAT_AUCUN_FICHIER",
    "ETAT_CHAINE_INUTILISABLE",
    "ETAT_CHAINE_REQUISE",
    "ETAT_FICHIER_PRESENT",
    "ETAT_PAS_ENCORE_ECRITE",
    "FILET_A_ECRIRE",
    "FILET_IMPOSE",
    "ISSUE_ANNULER",
    "ISSUE_AUTRE_CHAINE",
    "ISSUE_GENERER",
    "ISSUE_MODIFIER",
    "ISSUE_REMPLACER",
    "LIBELLES_DES_CHAMPS",
    "LIBELLE_AUTRE_CHAINE",
    "LIBELLE_CHAINE",
    "LIBELLE_CONTIENT",
    "LIBELLE_DESTINATION",
    "LIBELLE_ECRIT_LE",
    "LIBELLE_EMPLACEMENT",
    "LIBELLE_FICHIER",
    "LIBELLE_FORMAT_DPI",
    "LIBELLE_FORMAT_MARGE_DPI",
    "LIBELLE_GENERER",
    "LIBELLE_MODIFIER",
    "LIBELLE_NOM_DU_FICHIER",
    "LIBELLE_PASTILLES",
    "LIBELLE_PATCHS",
    "LIBELLE_PLANCHE",
    "LIBELLE_REMPLACER",
    "MENTION_AUTRE_CHAINE",
    "MENTION_DU_BANDEAU",
    "MENTION_EN_COURS",
    "MENTION_REMPLACER",
    "MENTION_REMPLACER_SANS_DATE",
    "NOM_DE_L_INTERRUPTION",
    "PALIER_DE_LA_MIRE",
    "PARAGRAPHE_DU_NOM",
    "PERIODE_DU_ROTOR",
    "PROSE_DE_LA_MIRE",
    "QUAND_LA_SUITE_DE_LA_MIRE",
    "RACCOURCIS_MIRE_EN_COURS",
    "RACCOURCIS_MIRE_JUGEMENT",
    "RACCOURCIS_MIRE_REGLAGES",
    "SUITE_AUTRE_MIRE",
    "SUITE_DOSSIER",
    "SUITE_PLANCHES",
    "TEMPS_DE_REGLAGE",
    "TEMPS_D_ECRITURE",
    "TITRE_A_ECRIRE",
    "TITRE_DES_REGLAGES",
    "TITRE_DE_LA_GENERATION",
    "TITRE_ECRIT",
    "TITRE_MIRE_EXISTE",
    "UNITE_DES_PDF",
    "DonneesImposees",
    "EcranMireConfirmation",
    "EcranMireEcrite",
    "EcranMireEnCours",
    "EcranMireExiste",
    "EcranMireReglages",
    "FormulaireDeLaMire",
    "MirePresente",
    "abreger_la_mire",
    "chaine_nommable",
    "chemin_de_la_mire",
    "choix_de_la_confirmation",
    "choix_du_conflit",
    "destination_de_la_mire",
    "donnees_imposees",
    "ligne_d_etat_des_reglages",
    "ligne_d_etat_du_conflit",
    "ligne_d_etat_du_resultat",
    "mire_presente",
    "nom_de_la_mire",
    "ouvrir_la_confirmation",
    "ouvrir_la_generation",
    "ouvrir_le_conflit",
    "ouvrir_le_resultat",
    "ouvrir_les_reglages",
    "panneau_de_la_confirmation",
    "panneau_du_conflit",
    "panneau_du_resultat",
    "queue_du_nom",
    "suites_du_resultat",
    "temoins_du_bandeau",
]
