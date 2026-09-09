# -*- coding: utf-8 -*-
"""`E3-4b` -- completer ce que le QR aurait dit (story 11.5, lot E, AC 7).

L'ecran ou l'operateur **recopie** le bloc d'identite imprime en clair sur une
planche dont le QR n'a rien livre. Il n'y a rien a dechiffrer : la planche
imprime les identifiants canoniques **verbatim** et l'egalite a l'octet pres
avec le payload du QR *est* le mecanisme de secours de la story 4.6.

**Ce module n'ecrit aucune frame, et il n'ecrit qu'une chose** : la couche
`manual_corrections` du document de detection, par
:func:`scan_corrections.poser_les_identites`. Ni manifest, ni frame, ni second
document -- c'est l'invariant du temps 1 (`EPIC11-ARB-6`), et l'AC 7.5 le
mesure sur le disque et non sur le rapport.

**Trois points d'entree de coeur, et aucune regle reecrite ici** :

* :func:`scan_corrections.modele_depuis_le_manifeste` construit le modele de
  completion **depuis le manifeste**, jamais depuis les autres QR de la pile
  (`EPIC11-ARB-64`). C'est ce qui rend completable le cas qu'Egan a nomme --
  une pile d'**une seule** planche muette, sur un lot connu du projet : elle
  n'a aucune soeur a lire, donc aucune planche modele ;
* :func:`scan_corrections.payload_depuis_l_identite` valide la saisie.
  **Aucune seconde regle de validation de payload n'est ecrite ici**
  (`EPIC11-ARB-27`, verbatim d'`epics.md` sur cette story), et une frontiere
  negative de ce lot la compte a zero, volet symetrique compris. Le refus est
  rendu par `IdentiteIncompletable` **et son motif**, jamais par un message
  local -- un motif de coeur est deja une phrase pour l'operateur, et le
  resumer le detruirait (`EPIC11-ARB-30`) ;
* :func:`scan_corrections.poser_les_identites` pose la correction.

**Le mot « completer » est ici chez lui** (`EPIC11-ARB-127`, tranche par Egan
le 2026-08-31). La frontiere negative d'`EPIC11-ARB-48` vise la completion de
**CHEMIN** -- celle que `Tab` offrait et que l'explorateur a remplacee partout
--, pas la completion du QR, qui est le nom qu'`EPIC11-ARB-29` a choisi pour
cet ecran. La frontiere a donc ete resserree sur la chose plutot que la chose
renommee : voir `test_projets.py`.

**Rien n'est prerempli**, et c'est delibere : un champ devine faux n'appelle pas
la verification. C'est la regle du Flow 3 de la GUI, reprise sans amenagement,
et l'AC 7.3 la mesure **champ par champ**.

**Aucune lettre n'est un raccourci** (`EPIC11-ARB-68`, « sans exception et sans
ordre de priorite a maintenir »). L'ecran est un formulaire de saisie : les six
champs acceptent toutes les lettres. L'ouverture du scan est donc une **ligne du
formulaire**, atteinte par `Tab` et validee par `⏎` -- exactement le geste que
`EPIC11-ARB-101` (note 7) a retenu pour la reprise du dpi sur `E3-1`, et pour le
meme motif. `EPIC11-ARB-42` proposait la lettre `o` ; elle tombe sous l'interdit
d'`EPIC11-ARB-68`, plus recent, et la maquette regeneree ne la porte plus.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence

from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Static

from .. import page_templates, pdf_composition, scan_corrections
from ..io import payload as payload_io
from . import aide_de_champ, jetons
# `_cale_a_droite` est **importe** et non recopie : c'est la regle de calage des
# mentions de `E3-1`, et deux redactions donneraient deux formulaires du meme
# atelier qui ne se rendent pas pareil. Le trait de soulignement marque une
# fonction privee au PAQUET des ecrans du Scan, pas au module -- les deux
# formulaires sont un seul motif, livre en deux lots.
from .atelier_scan import (INDENT_DU_CURSEUR, INDENT_DU_TEXTE, _cale_a_droite,
                           filet)
from .atelier_scan_rapport import PageMuette
from .coque import Palier
from .execution import ouvrir_dans_la_visionneuse_du_systeme

# ---------------------------------------------------------------------------
# Les lignes du formulaire, et leur ordre de saisie
# ---------------------------------------------------------------------------
#
# **Les deux familles de champs sont celles du coeur, et elles ne se melangent
# pas** (`EPIC11-ARB-101`, note 12 d'Egan du 2026-08-31 -- « il y a plus de
# champs que cela a completer [...] si le lot est au manifeste on peut completer
# certaines infos automatiquement ») :
#
# * `scan_corrections.CHAMPS_D_IDENTITE` (6) -- ce que l'operateur LIT sur la
#   planche, et donc ce que ce formulaire demande ;
# * `scan_corrections.CHAMPS_NEUTRES_DU_LOT` (8) -- ce que
#   `modele_depuis_le_manifeste` apporte gratuitement, et donc ce que ce
#   formulaire **montre sans le demander**. Les demander serait faire retaper ce
#   que la machine sait deja, et un champ retape faux est pire qu'un champ vide.
#
# Les deux tuples sont **lus du coeur**, jamais recopies : une seconde redaction
# ferait demander demain un champ que le contrat aurait deplace d'une famille a
# l'autre, sans qu'aucune etape n'echoue.

#: Les six champs saisis, **dans l'ordre ou la planche les imprime, de haut en
#: bas** : l'en-tete (le nom de planche, puis la pagination), le pied technique
#: (le gabarit), puis les reperes sous les images (le cardinal, et les deux
#: timecodes). C'est la demande d'Egan -- « il faut que le formulaire soit DANS
#: LE MEME ORDRE que les infos du pied de page » -- appliquee a la feuille
#: entiere : un formulaire dont l'ordre suit l'oeil se remplit sans chercher.
CHAMP_LOT = "lot"
CHAMP_PAGE = "page"
CHAMP_GABARIT = "gabarit"
CHAMP_FRAMES = "frames"
CHAMP_TC_PREMIER = "tc-premier"
CHAMP_TC_DERNIER = "tc-dernier"

CHAMPS_SAISIS: tuple[str, ...] = (
    CHAMP_LOT,
    CHAMP_PAGE,
    CHAMP_GABARIT,
    CHAMP_FRAMES,
    CHAMP_TC_PREMIER,
    CHAMP_TC_DERNIER,
)

#: De quel champ du coeur chaque ligne porte la saisie. La table est **confrontee
#: a `CHAMPS_D_IDENTITE`** a l'import (voir plus bas) : un champ ajoute au
#: contrat de l'identite manuelle et absent d'ici ferait un formulaire
#: silencieusement incomplet, c'est-a-dire le faux succes que le coeur refuse
#: deja de son cote.
CHAMP_DU_COEUR: Mapping[str, str] = {
    CHAMP_LOT: "lot_id",
    CHAMP_PAGE: "page_index",
    CHAMP_GABARIT: "template_id",
    CHAMP_FRAMES: "frames_per_page",
    CHAMP_TC_PREMIER: "first_frame_timecode",
    CHAMP_TC_DERNIER: "last_frame_timecode",
}

#: La ligne qui n'est pas un champ : elle **agit**. Elle vit dans le meme
#: parcours de `Tab` que les six autres, parce qu'aucune lettre ne peut etre un
#: raccourci a cote d'un champ de saisie (`EPIC11-ARB-68`).
ACTION_OUVRIR = "ouvrir"

#: Toutes les lignes du formulaire, saisies et action, dans l'ordre du parcours.
LIGNES_DU_FORMULAIRE: tuple[str, ...] = CHAMPS_SAISIS + (ACTION_OUVRIR,)

#: Le libelle de chaque ligne. Une table et non une suite de `if` : les libelles
#: et l'ordre de parcours sont deux choses, et les melanger ferait d'une
#: permutation de l'un une permutation muette de l'autre.
LIBELLES: Mapping[str, str] = {
    CHAMP_LOT: "Lot",
    CHAMP_PAGE: "Page",
    CHAMP_GABARIT: "Gabarit",
    CHAMP_FRAMES: "Images sur la planche",
    CHAMP_TC_PREMIER: "Timecode première",
    CHAMP_TC_DERNIER: "Timecode dernière",
    ACTION_OUVRIR: "Ouvrir le scan",
}

#: **La cle imprimee de chaque champ, LUE de la table du depot** et jamais
#: recopiee (`EPIC11-ARB-101`, note 12 : « en precisant a chaque fois la cle
#: correspondant a chaque champ »).
#:
#: Trois des six champs d'identite n'en ont aucune, et l'omission est **mesuree**
#: plutot que comblee : `frames_per_page` et les deux timecodes ne sont pas des
#: scalaires du payload -- ils vivent dans ses `slots` --, donc le pied technique
#: ne les imprime pas. Leur inventer une cle enverrait l'operateur chercher au
#: pied une mention qui n'y est pas. Ils se lisent sous les images, et c'est ce
#: que `F1` dit.
CLE_IMPRIMEE: Mapping[str, str] = {
    cle: payload_io.PAYLOAD_SHORT_KEYS[CHAMP_DU_COEUR[cle]]
    for cle in CHAMPS_SAISIS
    if CHAMP_DU_COEUR[cle] in payload_io.PAYLOAD_SHORT_KEYS
}

#: L'ordre dans lequel la planche imprime les huit champs **neutres**, de haut en
#: bas : `project_id` et `rush_id` au bloc d'identite, `fps_target` a l'entete,
#: les cinq autres au pied technique -- dans l'ordre de
#: `pdf_composition.PIED_CHAMPS`, qui est l'ordre imprime (note 12, axe 3).
#:
#: **Il se DERIVE des deux tuples du coeur**, et un ecart entre les deux leve a
#: l'import : c'est la meme discipline que `scan_corrections._SOURCE_AU_MANIFESTE`,
#: qui confronte sa table au contrat plutot que de les supposer egaux.
ORDRE_DES_CHAMPS_NEUTRES: tuple[str, ...] = (
    ("project_id", "rush_id", "fps_target")
    + tuple(champ for champ in pdf_composition.PIED_CHAMPS
            if champ in scan_corrections.CHAMPS_NEUTRES_DU_LOT)
)

if set(ORDRE_DES_CHAMPS_NEUTRES) != set(scan_corrections.CHAMPS_NEUTRES_DU_LOT):
    raise RuntimeError(
        "l'ordre imprime des champs neutres ne couvre plus "
        f"{sorted(set(scan_corrections.CHAMPS_NEUTRES_DU_LOT) - set(ORDRE_DES_CHAMPS_NEUTRES))}: "
        "le contrat de completion a gagne un champ que cet ecran ne sait pas "
        "situer sur la planche")

if set(CHAMP_DU_COEUR.values()) != set(scan_corrections.CHAMPS_D_IDENTITE):
    raise RuntimeError(
        "le formulaire ne demande pas les memes champs que "
        "`scan_corrections.CHAMPS_D_IDENTITE`: "
        f"{sorted(set(scan_corrections.CHAMPS_D_IDENTITE) ^ set(CHAMP_DU_COEUR.values()))}")

#: Largeur de la colonne des libelles. Le plus long (`Images sur la planche`)
#: tient dedans, si bien que le glyphe de focus et les valeurs restent alignes
#: quel que soit le champ courant.
LARGEUR_DU_LIBELLE = 22

#: Le titre de l'ecran et le titre du filet de verification, verbatim de la
#: maquette `E3-4b`.
TITRE = "Compléter ce que le QR aurait dit"
TITRE_DE_LA_VERIFICATION = "Vérification"

#: La consigne generale, verbatim de la maquette. `F1` la **remplace** par
#: l'aide du champ courant : c'est le meme emplacement, donc l'ecran ne gagne
#: aucune ligne et la grille 80 x 24 ne bouge pas.
CONSIGNE = "Recopiez le bloc d'identité imprimé en clair sur la planche."

#: La ligne de raccourcis, verbatim de la maquette `E3-4b`. **Constante de
#: module**, comme celles des autres ecrans du Scan : c'est ce qui la fait
#: balayer par la garde d'epic du repli ASCII et par celle des majuscules.
RACCOURCIS_COMPLETION = ("⏎ valider  Tab champ  Échap abandonner  "
                         "F1 où lire ce champ")

#: Ce que la mention de droite dit d'un champ vide. Les six sont requis : un
#: payload ne se compose pas avec un trou (`payload_depuis_l_identite` refuse),
#: et laisser croire le contraire ferait valider pour rien.
MENTION_REQUIS = "requis"

#: Le separateur des parts d'une mention. Meme signe que `atelier_scan`
#: (« requis · dpi ») : deux mentions du meme atelier separees differemment se
#: liraient comme deux conventions.
SEPARATEUR_DE_MENTION = " · "

#: Ce que la ligne `Page` porte a droite quand le lot est connu : le cardinal de
#: planches, **lu du modele**. C'est le « sur 4 » de la maquette.
MENTION_SUR_LE_TOTAL = "sur {total}"

#: Ce que la ligne d'etat compte. **Une mesure de l'ecran courant**, sans
#: touche, sans conseil et sans motif de conception (`EPIC11-ARB-56`).
COMPTE_DES_CHAMPS = "{saisis} champs sur {total} saisis"

#: Ce que la ligne d'etat dit quand tout est saisi.  **Un fait**, pas une
#: invitation.
ETAT_PRET = "les {total} champs sont saisis"

#: La ligne qui montre ce que le manifeste apporte **sans qu'on le demande**
#: (note 12, axe 1). Elle porte les **cles imprimees**, dans l'ordre de la
#: planche : l'operateur peut donc les confronter d'un coup d'oeil au pied de sa
#: feuille, ce qui est exactement le geste que la note decrit.
LIGNE_DU_MANIFESTE = "Le manifeste donne  {cles}"

#: Ce qu'elle dit **avant** que le lot soit saisi. Le modele est celui d'un lot :
#: tant que le lot n'est pas declare, il n'y a pas de modele -- et dire « le
#: manifeste ne donne aucun champ » y serait faux, pas seulement imprecis.
#: Le cardinal est **lu** de `CHAMPS_NEUTRES_DU_LOT`, jamais ecrit : un champ
#: ajoute au contrat le fait bouger tout seul.
MANIFESTE_EN_ATTENTE = "Le manifeste donne {combien} champs une fois le lot déclaré"

#: Ce qu'elle dit quand le modele ne porte rien -- regime qui ne se produit que
#: sur un modele fabrique. **Jamais une ligne vide** : « rien » et « rien
#: affiché » ne portent pas la meme information.
MANIFESTE_SANS_CHAMP = "Le manifeste ne donne aucun champ"

#: Les phrases de la verification de coherence (AC 7.4).
#:
#: **Trois formes pour le constat favorable, et ce n'est pas de la cosmetique** :
#: zero page lue est le regime NOMINAL de la pile d'une seule planche muette
#: (AC 7.1), et « Cohérent avec les 0 pages déjà lues » y annoncerait une
#: verification qui n'a rien verifie. Le cas a un element est le seul ou la
#: faute d'accord se voie, et c'est celui qu'une fabrique porte -- meme geste
#: que `atelier_scan.mention_de_la_mesure`.
COHERENCE_SANS_PAGE_LUE = "Aucune autre page de ce lot n'a été lue"
COHERENCE_UNE_PAGE = "Cohérent avec la page déjà lue de ce lot"
COHERENCE_OK = "Cohérent avec les {pages} pages déjà lues de ce lot"
COHERENCE_TOTAL = ("Les {pages} pages déjà lues annoncent {annonce} planches, "
                   "la saisie {declare}")
COHERENCE_OCCUPEE = "La page {page} est déjà déclarée par {fichier}"
COHERENCE_HORS_LOT = "La page {page} sort d'un lot de {total} planches"

#: Ce que la verification dit tant que la pagination n'est pas saisie. Elle ne
#: peut rien mesurer avant, et **elle le dit** plutot que de rendre un `oui`
#: qui vaudrait acquittement.
COHERENCE_EN_ATTENTE = "En attente de la page à déclarer"

# ---------------------------------------------------------------------------
# `F1` -- ou chaque champ SE LIT sur la feuille (AC 7.6, `EPIC11-ARB-14`)
# ---------------------------------------------------------------------------
#
# « Une aide qui paraphrase le libelle est un defaut » : chacune de ces phrases
# nomme un **endroit de la planche imprimee**, pas ce que le champ veut dire.
#
# La mention du pied technique est **lue** de `CLE_IMPRIMEE`, donc de la table du
# depot, et jamais recopiee : c'est la table qui decide de la cle imprimee, et
# une seconde redaction enverrait l'operateur chercher `template=` le jour ou le
# pied imprime `tid=`. Le depot a deja paye cette famille de defaut
# (`pdf_composition.PIED_CLE_HORS_PAYLOAD` : « deux tables qui divergent
# produiraient un QR ecrit dans une forme et relu dans une autre »).

OU_LIRE_LE_CHAMP: Mapping[str, str] = {
    CHAMP_LOT: (
        "En-tête de la planche : le nom de planche, avant le _pNNN "
        f"({CLE_IMPRIMEE[CHAMP_LOT]})."),
    CHAMP_PAGE: (
        "En-tête de la planche : le premier nombre de « page N/M » "
        f"({CLE_IMPRIMEE[CHAMP_PAGE]})."),
    CHAMP_GABARIT: (
        "Pied technique de la planche, mention "
        f"{CLE_IMPRIMEE[CHAMP_GABARIT]}=."),
    CHAMP_FRAMES: "Sous les images : le dernier repère sNN de la planche.",
    CHAMP_TC_PREMIER: "Sous la première image : ce qui suit « tc ».",
    CHAMP_TC_DERNIER: "Sous la dernière image : ce qui suit « tc ».",
    ACTION_OUVRIR: "Le scan de cette planche, dans la visionneuse du système.",
}


def cles_du_manifeste(modele: Mapping) -> tuple[str, ...]:
    """Les cles imprimees des champs que le modele apporte, **dans l'ordre de la
    planche**.

    C'est ce que l'operateur n'a **pas** a retaper, dit dans le vocabulaire de sa
    feuille : il retrouve chaque cle au meme endroit, dans le meme ordre, et voit
    d'un coup d'oeil ce que la machine a deja.

    Un champ absent du modele n'y figure pas : `modele_depuis_le_manifeste`
    refuse plutot que de rendre un modele troue, mais un modele **fabrique** peut
    en manquer, et annoncer un champ qu'on n'a pas serait la seule chose que
    cette ligne ne doit jamais faire.
    """
    return tuple(payload_io.PAYLOAD_SHORT_KEYS[champ]
                 for champ in ORDRE_DES_CHAMPS_NEUTRES if champ in modele)


# ---------------------------------------------------------------------------
# Ce que l'ecran sait des pages DEJA LUES du meme lot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PageLue:
    """Une planche du meme lot dont le QR **a** parle.

    Elle sert a une seule chose : confronter la saisie a ce que la machine a
    deja lu (AC 7.4). Ce n'est pas une seconde source du modele de completion --
    `EPIC11-ARB-64` a tranche que le modele vient du **manifeste**, pas d'une
    planche lue.
    """

    read_rank: int
    page_index: int
    page_count: int | None
    fichier: str

    @property
    def page_imprimee(self) -> int:
        """Le numero **imprime** sur la planche, qui part de 1.

        `pdf_composition` imprime `page {page_index + 1}/{page_count}` et
        `{lot_id}_p{page_index + 1:03d}` : le document de detection, lui,
        numerote a partir de zero (`scan_detect.ORIGINE_DES_PAGE_INDEX`). Les
        deux se croisent **ici**, une seule fois, parce qu'une seconde
        conversion ailleurs decalerait un rang de planche sans un mot.
        """
        return self.page_index + 1

    @property
    def nom_court(self) -> str:
        """Le nom du fichier sans son dossier ni son extension."""
        return PurePosixPath(self.fichier).stem


def pages_lues_du_lot(documents: Sequence, lot_id: str) -> tuple[PageLue, ...]:
    """Les planches de `lot_id` que la detection a su identifier.

    **Dans l'ordre des documents recus**, qui est celui du tri du coeur : cette
    liste n'est jamais retriee ici, et c'est ce qui permet a un banc de verifier
    le rang d'une cible sur la liste que ce code parcourt plutot que sur celle
    que sa fabrique croit ecrire (CLAUDE.md, point 2 bis).

    Une page sans `page_index` n'y entre pas : elle n'a rien a dire sur la
    pagination, et l'y compter ferait annoncer une planche que personne n'a lue.
    """
    lues: list[PageLue] = []
    for document in documents:
        for page in document.pages:
            if page.page_index is None:
                continue
            if page.decoded_lot_id is not None and page.decoded_lot_id != lot_id:
                continue
            lues.append(PageLue(
                read_rank=page.read_rank,
                page_index=page.page_index,
                page_count=page.page_count,
                fichier=page.source_path_relative,
            ))
    return tuple(lues)


# ---------------------------------------------------------------------------
# La verification de coherence (AC 7.4)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Coherence:
    """Ce que la verification a trouve : un etat, et sa phrase.

    L'etat est une **cle** de la table des glyphes de `DESIGN.md` section 6,
    jamais son dessin : c'est ce qui rend le repli ASCII automatique et la
    couleur posee par `jetons.peindre`.
    """

    etat: str
    phrase: str

    @property
    def contredit(self) -> bool:
        return self.etat == "absent"

    def ligne(self, ascii_seul: bool = False) -> str:
        return jetons.marque(self.etat, self.phrase, ascii_seul)


def verifier_la_coherence(page_declaree: int | None, *,
                          pages_lues: Sequence[PageLue],
                          total_du_modele: int | None) -> Coherence:
    """Confronter la pagination saisie a ce que les pages deja lues annoncent.

    « Une "page 4 sur 4" declaree alors que trois pages annoncent un total de 6
    est une contradiction visible **sans aucune image** » (AC 7.4). Trois
    contradictions distinctes, et elles ne se confondent pas :

    1. **le total diverge** -- les pages deja lues annoncent un cardinal de
       planches que le modele ne porte pas. C'est le cas nomme par l'AC ;
    2. **la page est deja occupee** -- une autre feuille declare deja ce
       numero. « Deux pages 4 dans un lot sont une erreur de saisie, pas un
       second tirage » (`EXPERIENCE.md`), et le refus **nomme le fichier qui
       l'occupe** : sans lui, l'operateur ne sait pas laquelle des deux
       corriger ;
    3. **la page sort du lot** -- un numero au-dela du cardinal, ou en deca de
       1. La planche imprimee numerote a partir de 1, donc `0` n'est pas une
       page.

    L'ordre n'est pas indifferent : le total est verifie **avant** l'occupation,
    parce qu'un total faux rend l'occupation illisible -- on comparerait des
    rangs de deux paginations differentes.

    Rend un constat neutre tant que la page n'est pas saisie : la verification
    ne peut alors rien mesurer, et rendre `oui` vaudrait acquittement.
    """
    pages_lues = tuple(pages_lues)
    if page_declaree is None:
        return Coherence("neutre", COHERENCE_EN_ATTENTE)

    annonces = {page.page_count for page in pages_lues
                if page.page_count is not None}
    if total_du_modele is not None and annonces and annonces != {total_du_modele}:
        return Coherence("absent", COHERENCE_TOTAL.format(
            pages=len(pages_lues),
            annonce=" ou ".join(str(a) for a in sorted(annonces)),
            declare=total_du_modele))

    for lue in pages_lues:
        if lue.page_imprimee == page_declaree:
            return Coherence("absent", COHERENCE_OCCUPEE.format(
                page=page_declaree, fichier=lue.nom_court))

    if total_du_modele is not None and not 1 <= page_declaree <= total_du_modele:
        return Coherence("absent", COHERENCE_HORS_LOT.format(
            page=page_declaree, total=total_du_modele))

    if not pages_lues:
        # **Un constat, pas un acquittement** : rien ne contredit la saisie, et
        # rien ne la corrobore non plus. Le glyphe est celui de la substitution
        # -- « il manque quelque chose, et ce n'est pas une faute » --, jamais
        # celui du complet, qui ferait lire une verification comme faite.
        return Coherence("substitute", COHERENCE_SANS_PAGE_LUE)
    if len(pages_lues) == 1:
        return Coherence("complete", COHERENCE_UNE_PAGE)
    return Coherence("complete", COHERENCE_OK.format(pages=len(pages_lues)))


# ---------------------------------------------------------------------------
# Le formulaire -- modele PUR, aucune dependance a `textual`
# ---------------------------------------------------------------------------


@dataclass
class FormulaireDeCompletion:
    """Ce que l'operateur recopie, et ce que le coeur en fait.

    **Modele pur**, comme `panneau.py`, `explorateur.py` et
    `atelier_scan_rapport.py` : aucune dependance a `textual`, aucune lecture de
    disque, aucune ecriture. C'est ce qui rend mesurables sans terminal les deux
    appariements a risque de cet ecran -- champ au focus contre ligne rendue, et
    saisie contre identite composee.

    Les valeurs sont des **chaines** et non des entiers : c'est ce que
    l'operateur frappe, et un champ doit pouvoir etre vide, ce qu'aucun entier
    ne sait dire. Elles partent **toutes vides** (AC 7.3, `EPIC11-ARB-38` pour
    la meme regle sur le dpi) : « un champ devine faux n'appelle pas la
    verification ».
    """

    #: La planche fautive, telle que le rapport de detection la designe.
    page: PageMuette
    #: Le manifeste du projet, **tel quel**. Le modele de completion s'en
    #: deduit par le seul point d'entree du coeur, et seulement une fois le lot
    #: saisi -- voir :attr:`modele`.
    manifeste: Mapping
    #: Les planches du meme lot deja lues (AC 7.4). Vide est un regime nominal :
    #: c'est le cas de la pile d'une seule planche muette (AC 7.1).
    pages_lues: tuple[PageLue, ...] = ()
    valeurs: dict[str, str] = field(default_factory=dict)
    #: Le champ courant, **suivi** : `aide_de_champ.ChampSuivi` compte chaque
    #: deplacement du curseur, et c'est ce compte qui fait TOMBER l'aide de
    #: champ au lieu de la cacher (correctif du 2026-09-04). Le comptage se
    #: fait a l'AFFECTATION : aucun chemin de navigation -- ni ceux d'ici, ni
    #: un chemin ajoute plus tard -- n'a rien a appeler pour cela.
    champ: str = aide_de_champ.ChampSuivi(CHAMPS_SAISIS[0])

    def __post_init__(self) -> None:
        # **Les six champs existent des le montage, et ils sont vides.** Les
        # creer a la premiere frappe ferait de « champ absent » et « champ
        # vide » deux etats indistinguables, et l'AC 7.3 mesure champ par champ.
        self.valeurs = {cle: self.valeurs.get(cle, "") for cle in CHAMPS_SAISIS}
        self.pages_lues = tuple(self.pages_lues)
        #: `F1` : l'aide du champ courant remplace la consigne generale.
        #:
        #: **Le mecanisme est celui du paquet, la table reste la notre**
        #: (`EPIC11-ARB-198`, story 11.9 lot B) : ce formulaire a porte le
        #: premier etage 1 du produit, en 11.5 ; il en porte desormais la
        #: redaction PARTAGEE -- `aide_de_champ.AideDeChamp` --, sans que
        #: `OU_LIRE_LE_CHAMP` bouge d'un caractere. Ce qui a ete generalise est
        #: le mecanisme, jamais la donnee.
        self._aide = aide_de_champ.AideDeChamp(
            OU_LIRE_LE_CHAMP, CONSIGNE, formulaire=self)
        #: Memoire du dernier modele construit, **indexee par le lot saisi**.
        #: Le modele coute une lecture de gabarit et un recalcul de selection
        #: (`pdf_composition.page_count_du_lot`) ; le rebatir a chaque dessin
        #: le paierait a chaque frappe. La cle est la saisie elle-meme, si bien
        #: qu'une lettre de plus dans le champ invalide la memoire toute seule.
        self._modele_memorise: tuple[str, dict | None, str] = ("", None, "")

    # -- lecture ------------------------------------------------------------

    @property
    def aide(self) -> bool:
        """L'aide est-elle ouverte **sur le champ courant** ?

        Une propriete et non un drapeau : la chute au changement de ligne est
        desormais **structurelle** -- l'etat retient le champ sur lequel `F1` a
        ete frappee --, si bien qu'aucun chemin de navigation n'a a la poser.
        `avancer` le faisait a la main, et un second chemin ajoute plus tard
        l'aurait oublie sans que rien ne le dise.
        """
        return self._aide.ouverte(self.champ)

    @property
    def lot_saisi(self) -> str:
        return self.valeurs[CHAMP_LOT].strip()

    def _construire_le_modele(self) -> tuple[dict | None, str]:
        """Le modele du lot saisi, ou le **motif** qui empeche de le construire.

        **Le modele se construit DEPUIS LE MANIFESTE** (`EPIC11-ARB-64`), par
        `scan_corrections.modele_depuis_le_manifeste` et par rien d'autre --
        « pas d'une planche lue ». C'est ce qui rend completable la pile d'une
        seule planche muette sur un lot connu du projet (AC 7.1) : elle n'a
        aucune soeur a lire, donc aucune planche modele.

        **Il ne peut pas se construire avant que le lot soit saisi**, et ce
        n'est pas une contrainte d'implementation : le modele est celui d'un
        lot, et rien n'est prerempli (AC 7.3), donc le lot est ce que
        l'operateur tape en premier. Une planche du reliquat n'a d'ailleurs
        aucun lot connu -- c'est la definition du reliquat.

        Le refus du coeur est **transporte verbatim**, jamais reformule : il
        nomme le lot cherche ET les lots connus du projet, ce qui est
        exactement ce qu'il faut a un operateur qui s'est trompe de projet.
        """
        lot = self.lot_saisi
        if not lot:
            return None, ""
        try:
            return scan_corrections.modele_depuis_le_manifeste(
                self.manifeste, lot_id=lot), ""
        except (scan_corrections.IdentiteIncompletable,
                page_templates.UnknownTemplateError) as refus:
            # **`UnknownTemplateError` est attrapee ici, et ce n'est pas de la
            # prudence** : `modele_depuis_le_manifeste` lit
            # `lots[].template_id` du manifeste pour en deduire le cardinal de
            # planches, et `page_templates.get_template` leve son propre refus
            # quand ce gabarit est inconnu. Il ne descend PAS d'
            # `IdentiteIncompletable` : ne pas l'attraper ferait tomber la TUI
            # sur un manifeste dont le gabarit a ete retire du registre --
            # c'est-a-dire exactement le cas qu'un refus nomme existe pour
            # rendre lisible. Mesure faite sur `tpl-...` retire : trace nue.
            return None, str(refus)

    def _modele_et_refus(self) -> tuple[dict | None, str]:
        """Le couple (modele, motif de refus), memorise par lot saisi."""
        lot = self.lot_saisi
        if self._modele_memorise[0] != lot:
            modele, refus = self._construire_le_modele()
            self._modele_memorise = (lot, modele, refus)
        return self._modele_memorise[1], self._modele_memorise[2]

    @property
    def modele(self) -> dict | None:
        """Le modele de completion du lot saisi, ou `None`."""
        return self._modele_et_refus()[0]

    @property
    def refus_du_modele(self) -> str:
        """Le motif du coeur quand le lot saisi n'est pas au manifeste, ou ``""``."""
        return self._modele_et_refus()[1]

    @property
    def total_du_lot(self) -> int | None:
        """Le cardinal de planches du lot, **lu du modele** et jamais deduit.

        `modele_depuis_le_manifeste` le calcule par
        `pdf_composition.page_count_du_lot`, donc par la formule de pagination
        de l'impression elle-meme. Le recalculer ici en serait une seconde
        redaction, sur la valeur la plus facile a fausser de tout l'ecran.
        """
        modele = self.modele
        valeur = modele.get("page_count") if modele else None
        return valeur if isinstance(valeur, int) else None

    @property
    def page_declaree(self) -> int | None:
        """Le numero de page saisi, **tel qu'il est imprime** (a partir de 1)."""
        return self._entier(CHAMP_PAGE)

    def _entier(self, cle: str) -> int | None:
        """La valeur d'un champ lue en entier, ou `None` si elle n'en est pas un.

        `None` et pas un refus : le champ est en cours de frappe, et refuser a
        chaque caractere ferait clignoter un motif d'erreur sur une saisie qui
        va bien. Le refus vient du coeur, a la validation.
        """
        brut = self.valeurs.get(cle, "").strip()
        if not brut:
            return None
        try:
            return int(brut)
        except ValueError:
            return None

    def saisis(self) -> int:
        """Combien des six champs portent quelque chose."""
        return sum(1 for cle in CHAMPS_SAISIS if self.valeurs[cle].strip())

    @property
    def complet(self) -> bool:
        return self.saisis() == len(CHAMPS_SAISIS)

    def coherence(self) -> Coherence:
        return verifier_la_coherence(self.page_declaree,
                                     pages_lues=self.pages_lues,
                                     total_du_modele=self.total_du_lot)

    def identite(self) -> scan_corrections.IdentiteManuelle:
        """Composer l'identite saisie. **Leve les refus du coeur.**

        `read_rank` vient de la planche fautive et non de la saisie : c'est ce
        qui designe la page pour le coeur, et le faire recopier serait offrir a
        l'operateur l'occasion de poser sa correction sur une autre planche.

        `page_index` est le numero imprime **moins un** : la planche imprime
        `page N/M` a partir de 1, le document de detection numerote a partir de
        zero. La conversion est ecrite ici et dans `PageLue.page_imprimee`, aux
        deux seuls endroits ou les deux numerotations se croisent.
        """
        page = self.page_declaree
        return scan_corrections.IdentiteManuelle(
            read_rank=self.page.read_rank,
            lot_id=self.valeurs[CHAMP_LOT].strip(),
            template_id=self.valeurs[CHAMP_GABARIT].strip(),
            frames_per_page=self._entier(CHAMP_FRAMES) or 0,
            page_index=(page - 1) if page is not None else -1,
            first_frame_timecode=self.valeurs[CHAMP_TC_PREMIER].strip(),
            last_frame_timecode=self.valeurs[CHAMP_TC_DERNIER].strip(),
        )

    def payload(self) -> dict:
        """Le payload que la saisie devient, **par le point d'entree du coeur**.

        `scan_corrections.payload_depuis_l_identite`, et rien d'autre
        (`EPIC11-ARB-27`). Cette methode ne fait que composer l'identite et la
        lui passer : c'est deliberement une ligne, pour qu'il n'y ait nulle part
        ou glisser une regle.
        """
        modele, refus = self._modele_et_refus()
        if modele is None:
            # **Le refus du coeur, pas un message local** (AC 7.2). Quand aucun
            # lot n'est saisi, l'identite composee le dira elle-meme -- on la
            # laisse lever plutot que d'ecrire ici une seconde regle de
            # completude du formulaire.
            raise scan_corrections.IdentiteIncompletable(
                refus or "aucun lot n'est saisi : le modèle de complétion se "
                         "construit depuis le lot déclaré")
        return scan_corrections.payload_depuis_l_identite(
            self.identite(), modele=modele)

    # -- ecriture -----------------------------------------------------------

    def avancer(self, pas: int = 1) -> bool:
        """`Tab` : la ligne suivante, **en boucle**.

        En boucle et non bornee, comme le formulaire du depot : sept lignes, et
        une borne obligerait a une seconde touche pour revenir en arriere -- ce
        qui rendrait la ligne d'ouverture atteignable dans un sens seulement.

        **L'aide de champ tombe au changement de ligne** : elle porte sur le
        champ courant, et la laisser en place la ferait mentir des la ligne
        suivante. Elle tombe **toute seule** depuis la story 11.9 -- l'etat
        retient le champ sur lequel elle a ete ouverte --, et cette methode n'a
        donc plus rien a poser.
        """
        rang = LIGNES_DU_FORMULAIRE.index(self.champ)
        self.champ = LIGNES_DU_FORMULAIRE[
            (rang + pas) % len(LIGNES_DU_FORMULAIRE)]
        return True

    def frapper(self, caractere: str) -> bool:
        """Un caractere dans le champ courant. **Toute lettre s'y ecrit.**

        `EPIC11-ARB-68` : « aucune lettre n'est un raccourci dans un champ de
        saisie, sans exception et sans ordre de priorite a maintenir ». Filtrer
        les caracteres non numeriques des champs de pagination serait une facon
        detournee de rendre une lettre inerte ; ils les acceptent, et le coeur
        les refuse -- ce qui est visible.

        La ligne d'ouverture n'est pas un champ : elle n'absorbe rien.
        """
        if self.champ not in CHAMPS_SAISIS:
            return False
        self.valeurs[self.champ] += caractere
        return True

    def effacer(self) -> bool:
        if self.champ not in CHAMPS_SAISIS or not self.valeurs[self.champ]:
            return False
        self.valeurs[self.champ] = self.valeurs[self.champ][:-1]
        return True

    def basculer_l_aide(self) -> bool:
        """`F1` : dire ou le champ courant se lit sur la feuille, ou revenir.

        `EPIC11-ARB-14` : « `F1` sur un champ dit ce que ce champ attend ». Elle
        **remplace** la consigne generale au lieu de s'ajouter : l'ecran ne
        gagne aucune ligne, donc la grille 80 x 24 ne bouge pas.

        Rend `True` : les **sept** lignes du parcours portent une phrase, donc
        la touche est toujours consommee ici. Sur un formulaire dont une ligne
        n'en porterait pas, le mecanisme rendrait `False` et la touche
        remonterait au manuel (AC 1.4).
        """
        return self._aide.basculer(self.champ)

    def tete(self) -> str:
        """La ligne de tete : la consigne, ou l'aide du champ courant."""
        return self._aide.tete(self.champ)

    def ligne_du_manifeste(self) -> str:
        """Ce que le modele apporte, **en cles imprimees et dans l'ordre de la
        planche** (`EPIC11-ARB-101`, note 12 d'Egan).

        C'est la moitie du formulaire qu'on ne remplit pas, et la dire est ce qui
        distingue « la machine sait deja » de « personne ne le sait ». Sans elle,
        un operateur qui compte huit mentions au pied de sa feuille et six champs
        a l'ecran conclut qu'il en manque deux.
        """
        modele, refus = self._modele_et_refus()
        if not self.lot_saisi:
            return MANIFESTE_EN_ATTENTE.format(
                combien=len(scan_corrections.CHAMPS_NEUTRES_DU_LOT))
        if refus:
            # Le lot saisi n'est pas au manifeste. **Le motif du coeur passe
            # verbatim** : il nomme les lots connus du projet, donc il dit ou
            # l'operateur s'est trompe. C'est aussi, en l'etat de cette branche,
            # un refus SANS ISSUE -- voir la note de fin de module.
            return refus
        cles = cles_du_manifeste(modele or {})
        if not cles:
            return MANIFESTE_SANS_CHAMP
        return LIGNE_DU_MANIFESTE.format(cles=" ".join(cles))


# ---------------------------------------------------------------------------
# Ce qui SUIT une correction posee -- note 10 d'Egan, portee par aucune AC
# ---------------------------------------------------------------------------
#
# `EPIC11-ARB-101`, note 10 (2026-08-31), verbatim de la disposition : « le
# formulaire `E3-4b` s'ouvre pour la page non rattachee, **une page a la fois**,
# puis on **revient au rapport** (`E3-4`), qui se **recalcule**. Si la page
# rattachee etait la derniere manquante, le rapport devient complet (`E3-3`) et
# l'ecriture s'ouvre. Sinon la page suivante est proposee. »
#
# **Le rapport se RECALCULE, il ne se rapièce pas.** `E3-3` et `E3-4` sont deux
# rendus du meme `atelier_scan_rapport.RapportDeDetection`, et lequel des deux
# s'affiche se lit sur `RapportDeDetection.complet`. Retrancher ici une page de
# la liste des completables ecrirait une seconde regle de completude a cote de
# `scan_detect.completude_des_planches`, qui est sa seule derivation du depot
# (`EPIC7-ARB-73`) -- et les deux divergeraient au premier lot dont il manque
# une planche JAMAIS SCANNEE, qu'aucune saisie ne rattrape.
#
# Cette fonction ne repond donc qu'a la question que l'ecran pose : **y a-t-il
# une page suivante a proposer ?**


def page_suivante_a_completer(pages_completables, posees=()) -> PageMuette | None:
    """La prochaine planche muette a completer, ou `None` s'il n'en reste aucune.

    :param pages_completables: les planches muettes du rapport, **dans l'ordre
        ou le rapport les parcourt** (`RapportDeDetection.pages_completables`).
        Cet ordre n'est jamais retrie ici : le refaire donnerait a l'operateur un
        enchainement different de celui que le rapport lui a montre.
    :param posees: les `read_rank` deja corriges pendant cette passe.

    `None` veut dire « reviens au rapport », et le rapport dira lui-meme s'il est
    devenu complet -- ce n'est pas a cette fonction de le decider.
    """
    posees = set(posees)
    for page in pages_completables:
        if page.read_rank not in posees:
            return page
    return None


# ---------------------------------------------------------------------------
# Poser la correction -- et RIEN D'AUTRE n'est ecrit (AC 7.5)
# ---------------------------------------------------------------------------


def poser_la_correction(document: dict,
                        identite: scan_corrections.IdentiteManuelle) -> dict:
    """Un document neuf portant cette identite saisie **de plus**.

    **Les identites deja posees sont relues et rendues**, et ce n'est pas une
    precaution de style : `scan_corrections.poser_les_identites` prend la liste
    **entiere** et remplace celle du document. Lui passer la seule identite
    qu'on vient de saisir effacerait celles des planches corrigees avant, sans
    un mot -- et un lot de trois planches muettes se corrige en trois passages
    sur cet ecran.

    Poser deux fois la meme planche **remplace** sa correction plutot que de
    lever : c'est une reprise de saisie, cas nominal de cet ecran, et
    `poser_les_identites` refuse deux entrees du meme `read_rank`.
    """
    posees = dict(scan_corrections.lire_les_identites(document))
    posees[identite.read_rank] = identite
    return scan_corrections.poser_les_identites(
        document, [posees[rang] for rang in sorted(posees)])


def ecrire_la_correction(chemin, document: dict,
                         identite: scan_corrections.IdentiteManuelle) -> dict:
    """Poser la correction et **ecrire le seul document de detection**.

    Un seul fichier est touche, et c'est celui-la : ni frame, ni manifest, ni
    second document (AC 7.5). L'ecriture passe par `scan_corrections.ecrire`,
    donc par le serialiseur canonique et l'ecrivain atomique du depot -- « c'est
    le seul fichier qui porte le travail de jugement de l'operatrice : une
    interruption ne doit jamais le laisser tronque ».
    """
    corrige = poser_la_correction(document, identite)
    scan_corrections.ecrire(Path(chemin), corrige)
    return corrige


# ---------------------------------------------------------------------------
# `E3-4b` -- l'ecran
# ---------------------------------------------------------------------------


class EcranCompletionQr(Palier):
    """`E3-4b` -- le formulaire de completion du QR.

    **Un formulaire, pas une liste d'issues** : `EPIC11-ARB-126` distingue les
    deux, et c'est pourquoi aucune ligne d'ici ne porte de case a cocher -- le
    glyphe de focus `>` marque le champ courant, comme sur `E3-1`.

    `poser` est **injecte et REQUIS**, comme `sur_rapport` l'est sur l'ecran de
    detection depuis le finding `K3` : « un `Callable | None = None` fait de
    l'oubli de cablage un silence ». L'ecran ne decide pas ou le document vit, il
    rend l'identite validee a qui l'a ouvert -- mais il ne peut pas etre monte
    sans savoir a qui la rendre.

    `ouvrir` a pour defaut le **vrai chemin de production**, et n'est remplace
    que par les bancs : le produit passe par
    :func:`~mixed_media_utility.tui.execution.ouvrir_dans_la_visionneuse_du_systeme`,
    l'unique point d'appel systeme du paquet (`EPIC11-ARB-85`, AC 7.7).
    """

    titre = "Scan"
    raccourcis = RACCOURCIS_COMPLETION
    #: Un **passage**, pas une station : on entre ici depuis le rapport, on en
    #: repart aussitot l'identite posee ou abandonnee.
    TRANSITOIRE = True
    #: **La declaration qui fait entrer cet ecran dans l'ensemble borne** de
    #: `aide_de_champ.ECRANS_A_TABLE_D_AIDE` (AC 1.5, `EPIC11-ARB-198`). Il y
    #: entre parce qu'il PORTE une table depuis la 11.5, non parce que la story
    #: 11.9 lui en donnerait une.
    TABLE_D_AIDE = OU_LIRE_LE_CHAMP

    def __init__(self, page: PageMuette, manifeste: Mapping, *,
                 poser: Callable[[scan_corrections.IdentiteManuelle], None],
                 pages_lues: Sequence[PageLue] = (),
                 chemin_du_scan=None,
                 ouvrir: Callable[[object], str] =
                 ouvrir_dans_la_visionneuse_du_systeme) -> None:
        super().__init__()
        self.formulaire = FormulaireDeCompletion(
            page=page, manifeste=manifeste, pages_lues=tuple(pages_lues))
        #: Le chemin **absolu** du scan de la planche, quand l'appelant le
        #: connait. `PageMuette.fichier` est relatif au projet : l'ouvrir tel
        #: quel remettrait au bureau un chemin qui ne designe rien depuis le
        #: dossier courant.
        self.chemin_du_scan = Path(chemin_du_scan) if chemin_du_scan else None
        self._poser = poser
        self._ouvrir = ouvrir
        self._etat_a_dire = ""

    # -- lecture ------------------------------------------------------------

    def bandeau(self, largeur: int | None = None) -> str:
        """Le bandeau, avec le **nom du fichier fautif** a droite.

        C'est ce que la maquette porte (`planche_03.tiff`) : l'ecran ne dit pas
        seulement qu'on complete un QR, il dit **lequel**. Un formulaire qui ne
        nomme pas sa planche est un formulaire qu'on remplit a l'aveugle des
        qu'un lot en porte deux.
        """
        from .coque import Contexte

        session = getattr(self.app, "contexte", Contexte())
        contexte = Contexte(session.projet, self.titre,
                            PurePosixPath(self.formulaire.page.fichier).name)
        return contexte.rendu(self.app.size.width if largeur is None else largeur,
                              getattr(self.app, "ascii_seul", False))

    def valeur_du_champ(self, cle: str) -> str:
        """Ce que la ligne affiche a droite de son libelle.

        Le glyphe `neutre` -- et jamais une chaine vide -- marque un champ non
        renseigne : `DESIGN.md` section 6 en fait le second canal de « rien
        ici », et une case vide se lit comme un defaut de rendu.
        """
        neutre = self.app.glyphes["neutre"]
        if cle == ACTION_OUVRIR:
            if self.chemin_du_scan is None:
                return self.formulaire.page.fichier
            utile = jetons.largeur_utile(self.app.size.width)
            place = utile - len(INDENT_DU_CURSEUR) - LARGEUR_DU_LIBELLE - 2
            return jetons.abreger_chemin(str(self.chemin_du_scan),
                                         max(place, 1), self.app.ascii_seul)
        return self.formulaire.valeurs[cle] or neutre

    def mention_du_champ(self, cle: str) -> str:
        """La colonne de droite : ce qui manque, le total du lot, et **la cle**.

        Trois parts, cumulables et separees comme `atelier_scan` les separe :

        * `requis` tant que le champ est vide (`DESIGN.md` section 7.3) ;
        * `sur N` sur la ligne `Page` -- le cardinal du lot, **lu du modele**.
          Absent quand le modele ne le donne pas : jamais `0`, jamais `--`,
          jamais une valeur devinee (`DESIGN.md` section 3) ;
        * la **cle imprimee** du champ, quand la planche en imprime une. C'est la
          demande d'Egan (note 12) : l'operateur voit, sur la meme ligne, le mot
          qu'il doit chercher sur sa feuille.

        La ligne d'ouverture n'en porte aucune : elle ne se recopie pas.
        """
        if cle == ACTION_OUVRIR:
            return ""
        parts = []
        if not self.formulaire.valeurs[cle].strip():
            parts.append(MENTION_REQUIS)
        elif cle == CHAMP_PAGE and self.formulaire.total_du_lot is not None:
            parts.append(MENTION_SUR_LE_TOTAL.format(
                total=self.formulaire.total_du_lot))
        if cle in CLE_IMPRIMEE:
            parts.append(CLE_IMPRIMEE[cle])
        return SEPARATEUR_DE_MENTION.join(parts)

    def ligne_de_champ(self, cle: str, utile: int) -> str:
        """Une ligne de formulaire : libelle, glyphe de focus, valeur, mention.

        Le glyphe `>` marque la ligne **au focus** (`DESIGN.md` section 7.3), et
        il ouvre sa colonne : les autres lignes portent un blanc a sa place,
        pour que les valeurs restent alignees quand le focus se deplace. C'est
        la meme forme que `E3-1`, et c'est voulu -- deux formulaires du meme
        atelier qui ne se rendraient pas pareil se liraient comme deux ecrans.
        """
        table = self.app.glyphes
        focus = table["invite"] if self.formulaire.champ == cle else " "
        gauche = (f"{INDENT_DU_CURSEUR}{LIBELLES[cle]:<{LARGEUR_DU_LIBELLE}}"
                  f"{focus} {self.valeur_du_champ(cle)}")
        return _cale_a_droite(gauche, self.mention_du_champ(cle), utile)

    def lignes(self) -> list[str]:
        """Le corps de l'ecran, **dix-sept lignes** -- la hauteur de la grille.

        Le compte n'est pas indicatif : `DESIGN.md` pose 80 x 24 ligne d'etat
        comprise, et la zone centrale en recoit dix-sept. Une ligne de plus
        pousserait la verification hors de l'ecran, ce qui est precisement le
        renseignement que ce formulaire existe pour rendre. C'est pour cela que
        `F1` **remplace** la consigne au lieu de s'ajouter.
        """
        utile = jetons.largeur_utile(self.app.size.width)
        ascii_seul = self.app.ascii_seul
        corps = ["", INDENT_DU_TEXTE + TITRE, "",
                 INDENT_DU_CURSEUR + "  " + self.formulaire.tete(), ""]
        corps += [self.ligne_de_champ(cle, utile) for cle in CHAMPS_SAISIS]
        corps += ["", self.ligne_de_champ(ACTION_OUVRIR, utile)]
        corps += [filet(utile, TITRE_DE_LA_VERIFICATION, ascii_seul), ""]
        corps.append(INDENT_DU_CURSEUR + "  "
                     + self.formulaire.coherence().ligne(ascii_seul))
        corps.append(INDENT_DU_CURSEUR + "  " + self.formulaire.ligne_du_manifeste())
        return corps

    def valeur_de_l_aide(self, cle: str) -> str:
        """La **valeur du contexte courant** de l'aide de ce champ -- **aucune**.

        Troisieme point du contrat des porteurs (`aide_de_champ`), rendu ici
        pour que les quatre s'interrogent de la meme facon. Et il rend le vide,
        ce qui est un **ecart nomme plutot que tu** : les phrases de
        `OU_LIRE_LE_CHAMP` nomment un endroit de la planche IMPRIMEE et une cle
        lue du coeur (`CLE_IMPRIMEE`), jamais une valeur de l'etat courant de
        l'ecran. C'est le dessin livre en 11.5 sous `EPIC11-ARB-14`, et
        `EPIC11-ARB-198` interdit de le reecrire ici : « generaliser le livre,
        ne pas le reecrire ». L'ensemble des porteurs qui citent une valeur du
        contexte est donc mesure EXACTEMENT, et celui-ci en est absent.
        """
        return ""

    def rang_du_lien(self) -> int | None:
        """Le rang de la ligne qui porte le lien cliquable, ou `None`.

        **Un supplement, jamais le chemin principal** (`EPIC11-ARB-42`) : le
        lien est pose sur la ligne d'ouverture, dont le libelle et le chemin
        restent lisibles sans lui. Le rang est **derive** de la position de la
        ligne dans le parcours, jamais ecrit en dur -- deux comptes de lignes
        divergeraient a la premiere ligne ajoutee, et le lien se poserait alors
        sur une autre ligne sans que rien ne le dise.
        """
        if self.chemin_du_scan is None:
            return None
        prefixe = INDENT_DU_CURSEUR + LIBELLES[ACTION_OUVRIR]
        for rang, ligne in enumerate(self.lignes()):
            if ligne.startswith(prefixe):
                return rang
        return None

    def cible_du_lien(self) -> str | None:
        """L'URL `file://` du scan, ou `None` quand aucun chemin n'est connu."""
        if self.chemin_du_scan is None:
            return None
        return self.chemin_du_scan.absolute().as_uri()

    def annoncer(self, motif: str) -> None:
        """Poser un motif en ligne d'etat, **et l'y laisser** (story 11.5, lot F).

        `poser_etat` seul ne suffit pas : le dessin suivant rappelle
        :meth:`etat`, qui repartirait du compte des champs et effacerait le
        motif dans le meme souffle. C'est donc le canal d'etat de l'ecran que
        l'on alimente, celui-la meme que ses refus internes emploient.

        Il existe pour l'appelant -- le parcours du Scan, quand la planche
        saisie designe un lot dont la passe n'a ecrit aucun document : rien
        n'est alors ecrit, et une touche qui ne fait rien et ne dit rien est
        indistinguable d'un clavier casse.
        """
        self._etat_a_dire = jetons.marque("absent", motif,
                                          self.app.ascii_seul)
        self.rafraichir()

    def etat(self) -> str:
        """La ligne d'etat : une **mesure** de l'ecran courant.

        Le compte des champs saisis, ou le motif que le coeur a rendu au dernier
        refus -- **verbatim** (`DESIGN.md` section 9). Aucune touche, aucun
        conseil, aucun motif de conception (`EPIC11-ARB-56`).
        """
        if self._etat_a_dire:
            return self._etat_a_dire
        total = len(CHAMPS_SAISIS)
        if self.formulaire.complet:
            return jetons.marque("complete", ETAT_PRET.format(total=total),
                                 self.app.ascii_seul)
        return jetons.marque(
            "absent",
            COMPTE_DES_CHAMPS.format(saisis=self.formulaire.saisis(),
                                     total=total),
            self.app.ascii_seul)

    # -- rendu ---------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id="corps-scan-completion")
        return [Vertical(self._corps, id="centre-scan-completion")]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        utile = jetons.largeur_utile(self.app.size.width)
        rang, cible = self.rang_du_lien(), self.cible_du_lien()
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, self.app.ascii_seul)
             for ligne in self.lignes()],
            ascii_seul=self.app.ascii_seul, sans_couleur=self.app.sans_couleur,
            liens={rang: cible} if rang is not None and cible else None))
        self.poser_etat(self.etat())
        super().rafraichir()

    def on_mount(self) -> None:
        self.rafraichir()

    # -- navigation ----------------------------------------------------------

    def on_key(self, evenement) -> None:
        if self.traiter(evenement.key, getattr(evenement, "character", None)):
            evenement.stop()
            self.rafraichir()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot."""
        if touche == "tab":
            self._etat_a_dire = ""
            return self.formulaire.avancer()
        if touche == "f1":
            # **`F1` est consommee ici**, sinon la liaison applicative ouvrirait
            # le manuel des raccourcis par-dessus le formulaire : l'aide a deux
            # etages d'`EPIC11-ARB-14` veut l'aide DU CHAMP quand un champ a la
            # main, et le manuel seulement hors champ.
            self._etat_a_dire = ""
            return self.formulaire.basculer_l_aide()
        if touche == "enter":
            return self._valider()
        if touche == "backspace":
            self._etat_a_dire = ""
            return self.formulaire.effacer()
        if caractere and caractere.isprintable():
            self._etat_a_dire = ""
            # Hors champ, la frappe est **consommee** plutot que de remonter au
            # binding applicatif `q` : une meme touche qui quitterait ou
            # saisirait selon la ligne serait pire qu'inerte.
            self.formulaire.frapper(caractere)
            return True
        return False

    def _valider(self) -> bool:
        """Ce que `⏎` fait, ligne par ligne."""
        self._etat_a_dire = ""
        if self.formulaire.champ == ACTION_OUVRIR:
            return self._ouvrir_le_scan()
        if not self.formulaire.complet:
            # L'action principale reste **inaccessible** tant qu'un champ est
            # vide, et elle DIT pourquoi : une touche annoncee qui ne fait rien
            # et ne dit rien est indistinguable d'un clavier casse.
            self._etat_a_dire = self.etat()
            return True
        return self._poser_la_correction()

    def _poser_la_correction(self) -> bool:
        """Valider la saisie **par le coeur**, puis la rendre a l'appelant.

        Le payload est compose avant de rendre l'identite, et c'est le seul
        moment ou cet ecran appelle le coeur : un refus se voit **ici**, pas
        trois ecrans plus loin. Son motif est rendu verbatim -- « le refus est
        rendu par `IdentiteIncompletable` et son motif, jamais par un message
        local » (AC 7.2).
        """
        try:
            self.formulaire.payload()
        except (scan_corrections.CorrectionInvalide,
                page_templates.UnknownTemplateError) as refus:
            self._etat_a_dire = jetons.marque("absent", str(refus),
                                              self.app.ascii_seul)
            return True
        self._poser(self.formulaire.identite())
        return True

    def _ouvrir_le_scan(self) -> bool:
        """Remettre le scan de la planche a la visionneuse du systeme.

        **Le retour est toujours une phrase**, jamais une trace
        (`EPIC11-ARB-42`) : l'ouvreur du paquet ne leve pas, et ce qu'il rend --
        le chemin ouvert, ou le motif qui a empeche de l'ouvrir -- va en ligne
        d'etat. Un conteneur sans bureau est le regime nominal des bancs.
        """
        cible = self.chemin_du_scan or Path(self.formulaire.page.fichier)
        self._etat_a_dire = jetons.marque("substitute", self._ouvrir(cible),
                                          self.app.ascii_seul)
        return True


__all__ = [
    "ACTION_OUVRIR",
    "CHAMPS_SAISIS",
    "CHAMP_FRAMES",
    "CHAMP_GABARIT",
    "CHAMP_LOT",
    "CHAMP_PAGE",
    "CHAMP_TC_DERNIER",
    "CHAMP_TC_PREMIER",
    "COHERENCE_EN_ATTENTE",
    "COHERENCE_HORS_LOT",
    "COHERENCE_OCCUPEE",
    "COHERENCE_OK",
    "COHERENCE_SANS_PAGE_LUE",
    "COHERENCE_UNE_PAGE",
    "COHERENCE_TOTAL",
    "COMPTE_DES_CHAMPS",
    "CONSIGNE",
    "Coherence",
    "EcranCompletionQr",
    "ETAT_PRET",
    "FormulaireDeCompletion",
    "LIBELLES",
    "LIGNES_DU_FORMULAIRE",
    "LIGNE_DU_MANIFESTE",
    "MANIFESTE_EN_ATTENTE",
    "MANIFESTE_SANS_CHAMP",
    "MENTION_SUR_LE_TOTAL",
    "ORDRE_DES_CHAMPS_NEUTRES",
    "CLE_IMPRIMEE",
    "CHAMP_DU_COEUR",
    "cles_du_manifeste",
    "page_suivante_a_completer",
    "MENTION_REQUIS",
    "OU_LIRE_LE_CHAMP",
    "PageLue",
    "RACCOURCIS_COMPLETION",
    "TITRE",
    "TITRE_DE_LA_VERIFICATION",
    "ecrire_la_correction",
    "pages_lues_du_lot",
    "poser_la_correction",
    "verifier_la_coherence",
]
