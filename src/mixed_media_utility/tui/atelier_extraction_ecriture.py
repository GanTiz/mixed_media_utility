# -*- coding: utf-8 -*-
"""L'atelier Extraction, cote ECRITURE : juger, executer, conclure, et le cablage.

Story 11.4, lots `E6` a `E9`. Ce module ne porte **aucun ecran neuf** : les cinq
ecrans dont il a besoin existent depuis la story 11.1
(:class:`~mixed_media_utility.tui.execution.PanneauConfirmation`,
:class:`~mixed_media_utility.tui.execution.EcranEcrasement`,
:class:`~mixed_media_utility.tui.execution.EcranExecution`,
:class:`~mixed_media_utility.tui.execution.EcranRefus`,
:class:`~mixed_media_utility.tui.execution.EcranResultat`). Il les **alimente**,
et il assemble la chaine reelle des paliers du produit.

Quatre choses, et une seule d'entre elles est du dessin :

* `E6` -- le **plan** d'une extraction et le panneau chiffre qui le montre. Les
  noms proposes viennent de :func:`~mixed_media_utility.io.naming.build_lot_id`,
  jamais d'une recomposition locale, et ils ne sont **pas editables**
  (`EPIC11-ARB-141`) ;
* `E7` -- l'**execution** (une invocation de `run_extraction` par lot) et le
  **resultat**, dont les chiffres sont mesures et les suites menent quelque
  part ;
* `E8` -- le **branchement** dans `ecran_ateliers.EcranAteliers.entrer` ;
* `E9` -- la **chaine reelle** des paliers, montee par le point d'entree.

**`EPIC11-ARB-4`, verbatim** : le panneau chiffre « est **obligatoire pour toute
commande qui ecrit**, et il porte au minimum : ce qui sera produit (noms de
fichiers ou de lots), en quelle quantite (frames, pages), et ce que cela coute
(espace disque, majorant assume comme tel) ». Son corollaire, verbatim lui
aussi : « Une commande destructive (ecrasement d'un lot existant) porte une
confirmation **en propre**, distincte de celle-ci » -- d'ou
:func:`ouvrir_le_point_de_jugement`, qui choisit l'ecran d'ecrasement et jamais
le panneau nominal des qu'un lot du plan est deja sur le disque.

**`EPIC11-ARB-28`, verbatim** : « **Extraction et Exports n'en ont pas** : une
seule entree chacun, donc le menu serait un ecran a franchir pour rien. » Le
branchement du lot `E8` ouvre donc `E2-1` **directement**.

**`EPIC11-ARB-13`, verbatim** : « La fin d'une execution ramene au **menu des
ateliers du projet ouvert** [...], jamais a l'ecran projet. » C'est
`CoqueTui.revenir_aux_ateliers` qui le tient, et la suite « Retour aux
ateliers » de l'ecran de resultat qui l'appelle.

**Ce module n'importe JAMAIS `cli.py`** (`EPIC11-ARB-67`, et la meme regle que
`palier_projet.py:9-12`). Le code retour est **lu** de la table descendue dans
`extraction.py` par le lot B (`EPIC11-ARB-75`, verbatim : « La table descend
dans `extraction.py` et est **lue des deux cotes**. »), jamais redigee une
seconde fois.

Un defaut MESURE, et TRANCHE depuis (`EPIC11-ARB-141`)
------------------------------------------------------
`run_extraction` **n'a aucun argument de nom de lot** : il derive `lot_id` de
`build_lot_id(rush_id, fps_target, ...)` (`extraction.py`, etape 1). Un nom
edite dans le panneau n'atteignait donc pas le coeur, et deux regles du depot se
rencontraient la :

* `EPIC11-ARB-36`, verbatim : « **tout champ d'un formulaire TUI nomme
  l'argument de coeur qu'il alimente** -- un champ sans argument est un defaut,
  pas une amelioration. » ;
* `EPIC11-ARB-46`, verbatim : « l'apercu ne peut jamais mentir. Toute
  divergence entre ce qu'il annonce et ce que `creer_projet` ecrit est un
  defaut critique, pas un ecart d'affichage. »

**La conduite d'alors etait un verrou**, `noms_hors_convention` : garder
l'action principale inaccessible tant qu'un nom s'ecartait de la convention. Un
verrou pose faute de cablage, c'est-a-dire une surface qui promet ce que la
machine ne fait pas -- « un mensonge d'interface, et il coute plus cher qu'une
capacite absente, parce qu'il ne se voit pas ».

Egan a tranche le 2026-09-01, verbatim : « On retire l'edition des noms PARTOUT
ou elle ne peut pas etre effective. On la laisse uniquement la ou on sait la
cabler. » Le champ **et** son verrou sont donc partis (story 11.4e, lot G) ;
`EPIC11-ARB-8` (« pre-rempli, et toujours editable ») en est **borne** plutot
que contredit. Les noms **derives** restent montres : c'est ce qu'`EPIC11-ARB-4`
exige du panneau chiffre, et on retire a cet ecran un mode, pas sa raison
d'etre.

Le retrait ne se relit pas, il se mesure :
`tests/unit/tui/test_aucun_nom_editable.py` tient l'implication -- aucun mot-cle
de nom au point d'entree de coeur, donc aucun champ a l'ecran -- et **rougit le
jour ou le coeur gagnera le parametre**, ce qui force la reprise du champ plutot
que son oubli. La capacite de renommer est portee a `deferred-work.md`.
"""
from __future__ import annotations

import logging
import os

from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable

from .. import extraction
from ..io.extraction_manifest import (
    EXTRACTION_LOT_STATE,
    EXTRACTION_OUTPUT_BIT_DEPTH,
    MANIFEST_FILENAME,
    ExtractionPersistenceError,
    LotStateConflictError,
    resolve_version_rank,
)
from ..io.manifest import ValidationError, validate_lot_state_transition
from ..io.naming import NamingError, build_lot_id
from ..io.project_layout import EXTRACT_FRAMES_DIRNAME, extract_frames_dir
from ..source_confirmation import _OUTPUT_CHANNELS as _CANAUX_DU_COEUR
from . import jetons, projet_lecture
from .coque import Contexte, CoqueTui, EcranPasEncore
from .explorateur import taille_lisible as _taille_de_l_explorateur
from .execution import (
    EcranEcrasement,
    LigneDefilante,
    EcranExecution,
    EcranRefus,
    EcranResultat,
    PanneauConfirmation,
    SurfaceExecution,
    ouvrir_dans_l_explorateur_du_systeme,
)
from .panneau import ChoixExclusif, Issue, LigneChiffree, Panneau

if TYPE_CHECKING:   # pragma: no cover -- annotation seule
    # **Import de type, jamais d'execution.** `atelier_extraction`
    # tire `ecran_projet`, donc `gui.depot_projets` : le garder hors du
    # chargement de ce module laisse `--diagnostic-chemin` repondre sur
    # un environnement partiel, meme motif que `ChaineReelle.__init__`.
    from .atelier_extraction import SourceSondee

# ---------------------------------------------------------------------------
# Textes d'ecran. En constantes, pour la meme raison qu'au palier 0 : un texte
# ecrit deux fois divergerait, et les frontieres negatives les balayent.
# ---------------------------------------------------------------------------

#: Titre du cartouche de `E2-3`. Verbatim de la maquette.
TITRE_A_ECRIRE = "À écrire"

#: Titre du cartouche d'ecrasement (`E2-3` destructif). Il ne dit pas « À
#: écrire » : ce qui distingue cet ecran du nominal est qu'il y a **deja**
#: quelque chose, et le titre est le premier endroit ou ca se lit.
TITRE_ECRASEMENT = "Déjà présent"

#: Titre du cartouche de `E2-5`. Verbatim de la maquette.
TITRE_ECRIT = "Écrit"

#: Unite de la surface d'execution. Le coeur compte des **fichiers ecrits**
#: (`ffmpeg_utils`), donc des frames : le mot vient de ce qui est compte.
UNITE = "frames"

#: Le verbe de la passe, **verbatim de la maquette approuvee**
#: `E2-4-extraction-execution.txt` (l. 5 : `Extraction en cours — lot 2 sur 2`).
#: Il est declare a la surface avec les lots ; c'est l'ecran d'execution qui y
#: ajoute `— lot k sur n`, parce que lui seul sait ou en est la passe.
#:
#: Il ne remplace pas :func:`titre_de_la_tache`, qui garde ses autres usages :
#: les deux disent deux choses differentes, le rush et le nombre de lots pour
#: l'un, le verbe de la passe pour l'autre.
LIBELLE_DE_LA_PASSE = "Extraction en cours"

#: Les trois issues de `E2-3`, dans l'ordre de la maquette. `ChoixExclusif`
#: refuse a la construction qu'une issue soit preselectionnee (`EPIC11-ARB-7`)
#: et pose le curseur ailleurs que sur celle qui ecrit -- c'est ce qui tient
#: `EPIC11-ARB-45`, verbatim : « aucune issue **qui ecrit** n'est atteignable
#: par une seule frappe depuis le montage d'un ecran ».
ISSUE_EXTRAIRE = "extraire"
ISSUE_ECRASER = "ecraser"
ISSUE_NOUVELLE_VERSION = "nouvelle-version"
ISSUE_MODIFIER = "modifier-les-reglages"
ISSUE_ANNULER = "annuler"

LIBELLE_EXTRAIRE = "Extraire"
LIBELLE_ECRASER = "Écraser et réextraire"
LIBELLE_MODIFIER = "Modifier les réglages"
LIBELLE_ANNULER = "Annuler, ne rien écrire"

#: `Créer la v2` -- la SECONDE issue qui ecrit (`EPIC11-ARB-89`, story 11.4d
#: AC 1.4). Elle dit **ce qui sera cree**, la ou :data:`LIBELLE_ECRASER` nomme
#: la destruction : les deux libelles sont les deux moities de l'arbitrage,
#: verbatim d'Egan -- « toujours proposer un versionnage [...] Mais toujours
#: permettre une reecriture plutot qu'un blocage sec ».
#:
#: **Le meme libelle que les deux autres ateliers versionnables du produit**
#: (`atelier_pdf_versions.LIBELLE_CREER`,
#: `atelier_exports_versions.LIBELLE_CREER`), au caractere pres.
#: `EPIC11-ARB-108`, verbatim : « Le systeme de versionnage doit etre le meme
#: PARTOUT pour tous les objets ». Trois redactions differentes du meme geste
#: seraient trois vocabulaires pour un seul mecanisme.
#:
#: Le rang y est **affiche**, jamais derive ici : il vient de
#: `io.extraction_manifest.resolve_version_rank`, lu au manifeste.
LIBELLE_NOUVELLE_VERSION = "Créer la v{rang}"

#: Le libelle de la meme issue quand les lots du plan **ne partagent pas** le
#: meme rang, et il n'en nomme aucun.
#:
#: **Le defaut qu'il ferme, trouve en preparant le mutant de l'AC 2.** Les lots
#: d'un plan ont des cadences differentes, donc des `base_lot_id` differents,
#: donc des familles de versions **independantes** : un rush deja versionne a
#: 25 fps et vierge a 12,5 peut consommer le rang 5 pour l'un et le rang 2 pour
#: l'autre. `Créer la v5` aurait alors annonce un rang faux pour deux lots sur
#: trois -- `EPIC11-ARB-46`, verbatim : « l'apercu ne peut jamais mentir ».
#:
#: Le nom exact de chaque sortie reste lisible : le cartouche apparie chaque
#: lot avec le sien (:func:`noms_du_conflit`). L'issue dit ce qu'elle fait, le
#: cartouche dit a quoi ca aboutit -- c'est la repartition que la maquette
#: `T4-1` dessine deja.
LIBELLE_NOUVELLES_VERSIONS = "Créer une nouvelle version de chaque lot"

#: Ce que la version COUTE, symetrique de
#: `EcranEcrasement.ECRASER_DETRUIT` / `.NE_REGENERE_PAS` (story 11.4d,
#: AC 6.2, dedoublees par `EPIC11-ARB-245`). Les deux
#: phrases disent le prix de chacune des deux issues qui ecrivent : l'une ne
#: regenere pas ce qui derive, l'autre n'efface rien mais occupe le disque
#: **en plus**.
#:
#: **Le chiffre est celui que le plan a deja calcule** -- le majorant de
#: `_ligne_de_l_espace`, avec sa mention --, jamais un chiffre en dur :
#: `EPIC11-ARB-89` en donne un (« une version de lot 4K a 12 im/s pese plus de
#: 2 Go ») et l'ecran qui le recopierait mentirait sur toutes les autres
#: sources.
#:
#: **Aucune touche n'y est nommee** (AC 6.3) : la suppression d'un element de
#: projet est la story 11.11, et promettre `Suppr` avant qu'elle existe serait
#: annoncer une issue inerte. `EPIC11-ARB-56` : « une MESURE, jamais une touche
#: ni un conseil ».
CE_QUE_LA_VERSION_COUTE = (
    "Créer une version n'efface rien : ces {espace} s'ajoutent au disque."
)

#: Le volet de la meme phrase quand la resolution de la source est inconnue et
#: que le plan n'a donc **aucun** majorant a montrer. Sans lui, la phrase
#: sortait avec un trou -- « ces  s'ajoutent au disque » -- ou pire, avec un
#: chiffre invente. Un cout inconnu se dit ; il ne se chiffre pas.
CE_QUE_LA_VERSION_COUTE_SANS_CHIFFRE = (
    "Créer une version n'efface rien, et s'ajoute au disque."
)

#: Les trois conduites possibles apres le point de jugement d'un conflit, et
#: **une seule vit a la fois** : c'est un champ, pas deux drapeaux
#: (story 11.4d, AC 3.3). Le coeur leve un refus nomme quand
#: `nouvelle_version` et `ecrasement_conscient` partent ensemble
#: (`extraction.py`, « deux issues DISTINCTES du meme conflit d'ecriture et ne
#: se combinent pas ») ; deux booleens independants rendaient cet etat
#: representable et donc atteignable, un champ a trois valeurs le rend
#: **impossible a construire**. L'AC exige que l'exclusivite soit tenue
#: **avant** l'appel, « pas rattrapee par une exception ».
CONDUITE_NOMINALE = "nominale"
CONDUITE_NOUVELLE_VERSION = "nouvelle-version"
CONDUITE_ECRASEMENT_CONSCIENT = "ecrasement-conscient"

#: L'ensemble EXACT, lu par `PlanExtraction.__post_init__`. Une conduite mal
#: orthographiee vaudrait sinon `CONDUITE_NOMINALE` en silence -- c'est-a-dire
#: qu'un choix d'ecrasement conscient se degraderait en refus, et un choix de
#: version en ecrasement.
CONDUITES = (CONDUITE_NOMINALE, CONDUITE_NOUVELLE_VERSION,
             CONDUITE_ECRASEMENT_CONSCIENT)

#: Les trois suites de `E2-5` qui precedent le retour. `EcranResultat` ajoute
#: lui-meme « Retour aux ateliers » en dernier s'il manque : on ne l'ecrit donc
#: pas ici, sous peine de le voir deux fois.
SUITE_DOSSIER = "Ouvrir le dossier des lots"
SUITE_PDF = "Composer les planches de ces lots"
SUITE_AUTRE_RUSH = "Extraire un autre rush"

#: Ce que la ligne d'etat de `E2-5` dit quand « Ouvrir le dossier des lots »
#: est choisie sur un rapport qui n'en porte aucun. Il n'y a alors rien a
#: ouvrir, et ouvrir le dossier du projet serait repondre a une autre question.
#: `suites_du_resultat` ne propose pas la suite dans ce cas ; ce texte est le
#: volet symetrique, celui qui tient si un jour elle la proposait.
AUCUN_LOT_A_OUVRIR = "Aucun lot écrit : il n'y a aucun dossier à ouvrir."

#: Libelles des lignes du panneau chiffre. Ils nomment ce qu'ils comptent.
LIBELLE_LOTS = "Lots créés"
LIBELLE_FRAMES = "Frames écrites"
LIBELLE_BORNES = "Bornes"
LIBELLE_ESPACE = "Espace disque"
LIBELLE_DESTINATION = "Destination"
LIBELLE_COULEUR = "Espace colorimétrique"
LIBELLE_DEJA = "Déjà sur le disque"
#: La ligne du SECOND chemin de conflit : un lot deja passe a `pdf` ou au-dela.
#: Le mot d'etat affiche est celui du coeur (`io.manifest.LOT_STATES`), lu tel
#: quel dans `lots[].state` -- la TUI ne traduit pas le vocabulaire du coeur.
LIBELLE_ETAT_DEJA_AVANCE = "Déjà engagé plus loin"
#: Le separateur des noms apparies du cartouche d'ecrasement : a gauche ce
#: qu'« Écraser » reecrit, a droite ce que « Créer la vN » ecrirait.
#:
#: **De l'ASCII PUR, et ce n'est pas un choix de gout.** La fleche `→` serait
#: le signe juste -- la ligne des bornes l'emploie deja, et
#: `jetons.REPLIS_DE_TEXTE` en porte le repli --, mais `Panneau.rendu` **ne
#: replie PAS son bloc de noms** : il replie les lignes chiffrees et recopie
#: `noms` tel quel. Un panneau compose en UTF-8 puis rendu en `--ascii` --
#: exactement ce que mesure
#: `test_le_panneau_tient_la_grille_du_PLANCHER_dans_les_deux_regimes` --
#: sortait donc la fleche non repliee au milieu d'une ligne par ailleurs
#: entierement ASCII. Le defaut ne mordait pas avant, les `lot_id` etant de
#: l'ASCII par construction ; ce separateur est le premier texte de prose a
#: entrer dans ce bloc. Le non-repli de `Panneau.noms` est verse a
#: `deferred-work.md` -- le corriger ici casserait l'abregement, `…` valant une
#: colonne et `...` trois.
SEPARATEUR_DES_NOMS = " -> "
LIBELLE_MANIFESTE = "Manifest mis à jour"

#: Ce que la ligne des bornes dit quand il n'y en a pas. Un vide y serait
#: illisible : l'operateur ne saurait pas si la question a ete posee.
BORNES_ABSENTES = "rush entier"

#: `EPIC11-ARB-74` : le consentement `--accept-unknown-color` est **une ligne du
#: panneau chiffre**, pas un ecran. Les deux redactions disent un fait sur la
#: source, jamais un conseil.
COULEUR_INCONNUE_ACCEPTEE = "non déclaré par la source — accepté"
COULEUR_DECLAREE = "déclaré par la source"

#: Ce qu'ecraser ne fait pas -- porte par `EcranEcrasement` lui-meme
#: (`execution.EcranEcrasement.ECRASER_DETRUIT` et `.NE_REGENERE_PAS`). Rien
#: n'est redit ici.

#: L'indentation des noms de lots sous le cartouche, verbatim de la maquette
#: `E2-3`.
#:
#: **Elle remplace `MOTIF_NOM_HORS_CONVENTION`, et ce n'est pas un hasard de
#: place** : ce module portait un motif de refus parce qu'un nom EDITE ne
#: pouvait pas atteindre `run_extraction`. `EPIC11-ARB-141` retire l'edition
#: plutot que de garder le verrou ; il n'y a donc plus de refus a motiver, et
#: les noms redeviennent ce qu'ils sont -- des lignes de texte du cartouche.
INDENT_DES_NOMS = "  "

#: La ligne de raccourcis de `E2-3` et de son ecran d'ecrasement.
#:
#: **Elle n'est PAS `execution.RACCOURCIS_CONFIRMATION`** (`EPIC11-ARB-141`) : la
#: constante commune promet encore une touche d'edition de nom, et cet atelier
#: n'en a plus. L'annoncer promettrait une touche qui ne fait rien -- ce que
#: `coque.py:510` documente comme un defaut a part entiere. Les deux issues
#: etaient de poser une ligne propre ou de corriger la constante partagee ;
#: corriger la constante toucherait `execution.py`, que ce lot n'a pas le droit
#: d'ouvrir. C'est donc une ligne propre, sur le precedent deja livre par les
#: ateliers Pdf et Exports, et l'ecart sur la constante partagee reste ouvert.
#:
#: **Le repli ASCII l'ALLONGE de cinq colonnes** (`Entree` pour `⏎`), et c'est
#: le regime qui commande le budget : la zone utile est de 76 colonnes.
#: MESURE: 44/49
RACCOURCIS_EXTRACTION_CONFIRMATION = "⏎ valider  ↑↓ choisir  Échap retour  F1 aide"

#: Ce que la ligne de raccourcis de l'ecran d'ecrasement ajoute a celle de la
#: confirmation, et **rien d'autre** (`EPIC11-ARB-245`).
#:
#: **`Ctrl+↓` et non `↓`**, et c'est le point dur de l'arbitrage : `↑↓` choisit
#: une issue, `Ctrl+↓` lit le cartouche. Une meme touche qui ferait l'un ou
#: l'autre selon un focus invisible rendrait indistinguables deux effets dont
#: l'un engage une ecriture destructive -- l'operateur qui croit lire la suite
#: deplacerait son curseur sur `Écraser et réextraire`. La touche porte donc
#: elle-meme la separation : la fleche choisit, `Ctrl` + la fleche lit.
#:
#: **`Ctrl+↓` et non `PgSuiv`**, et ce n'est pas un gout. Le brief du lot
#: annoncait `PgSuiv` ; `test_majuscules_des_raccourcis.py` l'a refuse sur deux
#: frontieres, et un grep du depot ne rend AUCUNE touche de pagination -- ni
#: dans une maquette, ni dans un `on_key`. `PgSuiv` aurait ouvert une famille
#: de touches neuve dans tout le produit pour un seul ecran, la ou `Ctrl+↓`
#: suit `Ctrl+A`, `Ctrl+D` et `Ctrl+R` que le depot emploie deja.
JETON_DU_PLI = "Ctrl+↓ lire la suite"

#: La ligne de l'ecran d'ecrasement **quand son cartouche defile**, verbatim de
#: la maquette `T4-2` (`EPIC11-ARB-245`, corrigee le 2026-09-05).
#:
#: **Elle ne sort que quand il y a une suite a lire.** Un cartouche qui tient
#: entier reprend :data:`RACCOURCIS_EXTRACTION_CONFIRMATION` : annoncer une
#: touche qui ne fait rien est le defaut que `coque.py:510` documente, et c'est
#: deja le motif pour lequel cet atelier ne reprend pas
#: `execution.RACCOURCIS_CONFIRMATION`.
#:
#: Le repli ASCII l'ALLONGE de cinq colonnes (`Entree` pour `⏎`), et c'est le
#: regime qui commande le budget : la zone utile est de 76 colonnes.
RACCOURCIS_EXTRACTION_ECRASEMENT = (
    "⏎ valider  ↑↓ choisir  " + JETON_DU_PLI + "  Échap retour  F1 aide")

#: Ce que la ligne d'etat de l'ecran d'execution ne dit pas : la surface la
#: remplit avec sa mesure. Ce module n'y ecrit rien.

# ---------------------------------------------------------------------------
# Le majorant d'espace disque. Il n'a AUCUN producteur dans le coeur (fait 5 de
# la fiche 11.4) : il vit donc ici, en constantes nommees, et il est marque
# comme majorant partout ou il apparait.
# ---------------------------------------------------------------------------

#: Les canaux d'un TIFF ecrit par `extract`, **lus du coeur** et jamais
#: redigees ici. `source_confirmation` porte deja la borne haute d'occupation
#: disque et l'ecrit dans son rapport de confirmation :
#: `largeur x hauteur x 3 canaux x 2 octets x nombre de frames, TIFF 16 bits
#: non compresse`.
#:
#: **Le fait F5 de la fiche 11.4 est faux, et c'est mesure** : il pose que « le
#: majorant d'espace disque de `E2-3` n'a aucun producteur dans le coeur ». Il
#: n'en a aucun dans `extraction.py` -- ou la fiche a cherche --, mais
#: `source_confirmation.build_source_report` le calcule et
#: `SourceReport.disk_upper_bound_bytes` le porte. Le rapport de confirmation
#: de la CLI l'imprime a chaque extraction. Ce module ne peut pas appeler cette
#: fonction au moment du plan -- elle exige un probe et une selection, que le
#: temps 1 a deja payes ailleurs --, mais il n'a aucune raison d'en recopier
#: les deux constantes : deux redactions de la meme formule divergeraient, et
#: le panneau chiffre annoncerait alors un cout different de celui du coeur.
CANAUX_ECRITS = _CANAUX_DU_COEUR

#: Octets par canal, **derives** de la profondeur du coeur et jamais recopies :
#: `EXTRACTION_OUTPUT_BIT_DEPTH` vaut 16 et « la valeur ne varie jamais »
#: (fiche 11.4, Q3).
OCTETS_PAR_CANAL = EXTRACTION_OUTPUT_BIT_DEPTH // 8

#: Le prefixe qui dit « ceci est approche ». La mention `(majorant)` que
#: `LigneChiffree` ajoute dit la meme chose d'une autre facon ; les deux
#: cohabitent dans la maquette `E2-3`, et c'est voulu -- le tilde se lit dans le
#: chiffre, la mention se lit dans la colonne.
PREFIXE_APPROCHE = "~ "


def octets_par_frame(largeur: int | None, hauteur: int | None) -> int | None:
    """Le poids **majorant** d'une frame ecrite, ou ``None`` si on ne sait pas.

    Majorant et non estimation : c'est la taille d'un TIFF **non compresse** a
    la resolution de la source, et l'ecriture reelle ne peut pas depasser ce
    chiffre. C'est la formule de `source_confirmation`, aux memes constantes,
    divisee par le nombre de frames.

    Un `None` se propage jusqu'a la ligne du panneau, qui dit alors qu'elle ne
    sait pas plutot que d'inventer -- une ligne d'espace disque fausse est pire
    qu'une ligne d'espace disque absente.
    """
    if not largeur or not hauteur or largeur < 0 or hauteur < 0:
        return None
    return largeur * hauteur * CANAUX_ECRITS * OCTETS_PAR_CANAL


def taille_lisible(octets: int | None) -> str | None:
    """Une taille de fichier, **par la fonction que l'explorateur porte deja**.

    Aucune seconde redaction : `explorateur.taille_lisible` est deja le rendu
    de taille de cette TUI, avec sa virgule decimale et sa decimale supprimee
    au-dela de dix. En reecrire une ici ferait deux formats du meme chiffre
    dans la meme interface, et ils divergeraient au premier ajustement.

    Ce module n'ajoute qu'une chose : `None` traverse. Une taille inconnue est
    un resultat, pas un zero, et c'est l'appelant qui decide de ce qu'il en
    dit.
    """
    if octets is None:
        return None
    return _taille_de_l_explorateur(octets)


def texte_des_bornes(source_in_timecode: str | None,
                     source_out_timecode: str | None) -> str:
    """Les deux bornes retenues, ou le fait qu'il n'y en a pas.

    Une seule borne est une fenetre valide du coeur (`bounds_suffix` distingue
    `("15:34:30:00", None)` de `(None, "15:34:30:00")`) : elle se rend donc
    telle quelle, avec la fleche qui montre de quel cote elle mord.
    """
    if source_in_timecode is None and source_out_timecode is None:
        return BORNES_ABSENTES
    return f"{source_in_timecode or ''} → {source_out_timecode or ''}".strip()


# ---------------------------------------------------------------------------
# Le plan : ce qui SERA ecrit, avant que quoi que ce soit le soit
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LotPrevu:
    """Un lot que l'extraction produira, avec son nom et son dossier du coeur.

    `lot_id` et `dossier` viennent tous deux du coeur -- `build_lot_id` et
    `project_layout.extract_frames_dir` --, et ce sont les **memes** fonctions que
    `run_extraction` appellera. C'est ce qui rend l'apercu incapable de diverger
    de l'ecriture (`EPIC11-ARB-46`).
    """

    fps_target: float
    frames: int
    lot_id: str
    dossier: Path
    deja_present: bool = False
    #: L'etat du lot **deja declare au manifeste**, ou ``None`` quand le lot
    #: n'existe pas encore. Il vient du vocabulaire du coeur
    #: (`io.manifest.LOT_STATES`), lu tel quel dans `lots[].state`.
    etat: str | None = None
    #: Le rang que « Creer la vN » consommerait pour ce lot, ou ``None`` quand
    #: le coeur refuse d'en proposer un. Il vient de
    #: `io.extraction_manifest.resolve_version_rank` -- **aucune arithmetique de
    #: rang dans `tui/`** (`EPIC11-ARB-108` : le calcul vit dans
    #: `io/version_ranks.py`, ecrit une fois pour tous les objets versionnables).
    rang_de_version: int | None = None
    #: Le `lot_id` que « Creer la vN » ecrirait, rendu par
    #: `build_lot_id(..., version_rank=rang)` -- **jamais compose ici**
    #: (`EPIC11-ARB-46`, « l'apercu ne peut jamais mentir » : il ne le peut que
    #: s'il appelle la meme fonction que l'ecriture). ``None`` quand le coeur
    #: refuse le rang ou le nom.
    lot_id_versionne: str | None = None
    #: Le refus du coeur, **verbatim**, quand aucune version n'est proposable :
    #: rangs epuises (`resolve_version_rank`) ou nom versionne trop long
    #: (`build_lot_id`). La TUI le RELAIE, elle ne le devine pas et ne le
    #: reformule pas (AC 8.2). ``None`` en regime nominal.
    refus_de_version: str | None = None

    @property
    def texte_de_cadence(self) -> str:
        """`25 fps`, comme la colonne de droite de `E2-5`."""
        entier = int(self.fps_target)
        valeur = entier if self.fps_target == entier else self.fps_target
        return f"{valeur} fps"


@dataclass(frozen=True)
class PlanExtraction:
    """Tout ce que le point de jugement doit montrer, et rien de plus.

    **Deux lots au moins des que deux cadences sont cochees** : la regle des
    fabriques de `CLAUDE.md` porte ici sur les lots produits, dont les comptes
    de frames doivent differer pour qu'une inversion se voie.
    """

    dossier_projet: Path
    rush_id: str
    video_path: Path
    lots: tuple[LotPrevu, ...]
    source_in_timecode: str | None = None
    source_out_timecode: str | None = None
    octets_par_frame: int | None = None
    couleur_inconnue_acceptee: bool = False
    #: Ce que l'operateur a retenu au point de jugement. Une des trois valeurs
    #: de :data:`CONDUITES`, et **une seule a la fois** -- c'est ce qui rend
    #: l'exclusivite des deux drapeaux du coeur structurelle plutot que
    #: verifiee (AC 3.3). Le plan qui sort de :func:`preparer_le_plan` est
    #: toujours `CONDUITE_NOMINALE` : la conduite se pose au jugement, par
    #: `dataclasses.replace`, jamais a la preparation.
    conduite: str = CONDUITE_NOMINALE

    def __post_init__(self) -> None:
        if not self.lots:
            raise ValueError(
                "Un plan d'extraction sans lot n'a rien a montrer : une "
                "validation a zero cadence cochee est refusee en amont "
                "(cadences.MOTIF_AUCUNE_COCHEE, AC 3.6).")
        if self.conduite not in CONDUITES:
            # Un `in` plutot qu'un defaut silencieux : une conduite inconnue
            # vaudrait sinon « nominale », c'est-a-dire qu'un choix
            # d'ecrasement conscient se degraderait en refus d'etat et un choix
            # de version en ecrasement -- deux pannes muettes, chacune du cote
            # destructif.
            raise ValueError(
                f"Conduite d'ecriture inconnue : {self.conduite!r}. "
                f"Connues : {list(CONDUITES)}.")

    # -- ce que le plan dit de lui-meme -------------------------------------

    @property
    def frames_total(self) -> int:
        """La **somme** des comptes, jamais un produit duree x cadence.

        `EPIC11-ARB-30`, verbatim : « le noyau ne derive **jamais** le cardinal
        d'une duree, il l'exige ».
        """
        return sum(lot.frames for lot in self.lots)

    @property
    def ecrase(self) -> bool:
        """Vrai des qu'**un** lot du plan est deja sur le disque.

        Un seul suffit : l'ecriture de ce lot-la detruirait des frames
        existantes, et `EPIC11-ARB-4` veut alors une confirmation en propre.
        """
        return any(lot.deja_present for lot in self.lots)

    @property
    def lots_deja_presents(self) -> tuple[LotPrevu, ...]:
        return tuple(lot for lot in self.lots if lot.deja_present)

    # -- le conflit, ses DEUX formes et ses DEUX issues ----------------------

    @property
    def lots_en_conflit_d_etat(self) -> tuple[LotPrevu, ...]:
        """Les lots deja passes a `pdf` ou au-dela, juges par le coeur.

        Le jugement est celui de :func:`refus_d_etat_de_lot`, donc celui de
        `io.manifest.validate_lot_state_transition` : aucune machine a etats
        n'est relue ici, et le vocabulaire du coeur n'est pas recopie.
        """
        return tuple(lot for lot in self.lots
                     if refus_d_etat_de_lot(lot) is not None)

    @property
    def conflit_d_etat(self) -> bool:
        """Vrai des qu'**un** lot du plan est deja passe a `pdf` ou au-dela.

        **C'est le SECOND chemin de conflit de l'atelier**, et il etait le seul
        a n'avoir aucune issue (story 11.4d, AC 4.1) : `executer_le_plan` le
        rencontrait au milieu de sa serie et montait un `EcranRefus` sans une
        seule suite -- le blocage sec qu'`EPIC11-ARB-89` interdit verbatim
        (« Un refus qui n'offre aucune issue est aussi fautif qu'une
        destruction silencieuse »).

        Le lire **au plan** plutot qu'a l'execution est ce qui permet de le
        montrer avant d'engager quoi que ce soit : `LotPrevu.etat` est
        renseigne des :func:`preparer_le_plan` (AC 4.3).
        """
        return bool(self.lots_en_conflit_d_etat)

    @property
    def en_conflit(self) -> bool:
        """Vrai des qu'un des **deux** chemins de conflit est ouvert.

        Le dossier de frames deja peuple (:attr:`ecrase`) et le lot deja passe
        a `pdf` (:attr:`conflit_d_etat`) sont deux conflits differents ; ils
        appellent le **meme** point de jugement, parce qu'ils ont les memes deux
        issues qui ecrivent. C'est ce qui evite un troisieme ecran pour un
        troisieme mot.
        """
        return self.ecrase or self.conflit_d_etat

    @property
    def version_proposable(self) -> bool:
        """Vrai quand **tous** les lots du plan ont un rang de version.

        `Tous` et non `au moins un` : l'issue est posee sur le PLAN, et le coeur
        recevra `nouvelle_version=True` pour chacun de ses lots. Proposer
        l'issue alors qu'un seul lot n'a pas de rang la ferait echouer au
        milieu de la serie -- c'est-a-dire apres avoir ecrit les autres.
        """
        return all(lot.rang_de_version is not None for lot in self.lots)

    @property
    def refus_de_version(self) -> str | None:
        """Le refus du coeur qui empeche la version, **verbatim**, ou ``None``.

        Celui du **premier** lot qui en porte un, dans l'ordre du plan. Un seul
        est montre : les autres diraient la meme chose du meme rush, et le
        cartouche a une hauteur.
        """
        for lot in self.lots:
            if lot.refus_de_version is not None:
                return lot.refus_de_version
        return None

    @property
    def rang_de_version(self) -> int | None:
        """Le rang **COMMUN** aux lots du plan, ou ``None`` s'ils divergent.

        Deux motifs de rendre ``None``, et le second a ete trouve en preparant
        le mutant de l'AC 2 :

        * un lot au moins n'a pas de rang -- la version n'est pas proposable, et
          annoncer un rang serait promettre une issue qui ne peut pas aboutir ;
        * les lots **n'ont pas le meme rang**. Chaque cadence est une famille de
          versions distincte (le `base_lot_id` porte la cadence), et un rush
          deja versionne a 25 fps mais vierge a 12,5 consomme le rang 5 pour
          l'un et le rang 2 pour l'autre. Rendre celui du premier ferait dire
          `Créer la v5` a une issue qui ecrit deux `_v2` -- exactement l'apercu
          qui ment qu'`EPIC11-ARB-46` interdit.

        L'issue existe quand meme dans ce second cas : c'est son **libelle** qui
        cesse de nommer un rang (:data:`LIBELLE_NOUVELLES_VERSIONS`), pas
        l'issue qui disparait. Le nom exact de chaque sortie reste lisible au
        cartouche, apparie lot par lot.
        """
        if not self.version_proposable:
            return None
        rangs = {lot.rang_de_version for lot in self.lots}
        return rangs.pop() if len(rangs) == len({None}) else None

    # -- ce que la conduite retenue dit au coeur -----------------------------

    @property
    def nouvelle_version(self) -> bool:
        """Le drapeau `nouvelle_version=` de `run_extraction`, **derive**.

        Derive et non stocke : c'est ce qui rend impossible qu'il parte en meme
        temps que :attr:`ecrasement_conscient` (AC 3.3).
        """
        return self.conduite == CONDUITE_NOUVELLE_VERSION

    @property
    def ecrasement_conscient(self) -> bool:
        """Le drapeau `ecrasement_conscient=` de `run_extraction`, **derive**."""
        return self.conduite == CONDUITE_ECRASEMENT_CONSCIENT

    @property
    def octets_majorants(self) -> int | None:
        if self.octets_par_frame is None:
            return None
        return self.octets_par_frame * self.frames_total

    @property
    def destination(self) -> str:
        """Le dossier des lots, relatif au projet --
        `projet_demo/extract-frames/`.

        **Le nom vient de la constante du coeur, jamais d'un litteral** : la
        story 11.14 a renomme ce dossier (`EPIC11-ARB-220`), et la seule
        raison pour laquelle cet ecran n'a pas menti pendant le renommage est
        que la valeur y a toujours ete LUE. Le nom d'avant ne s'ecrit qu'a un
        seul endroit du depot, `project_layout.LEGACY_FRAMES_DIRNAME`, qui le
        RECONNAIT sans jamais l'ecrire.
        La constante lue est desormais celle qui porte le mot d'Egan --
        `EXTRACT_FRAMES_DIRNAME` -- et non l'alias transitoire
        `FRAMES_DIRNAME`, qui porte la meme valeur sous le mot ambigu que la
        story existe pour retirer.
        """
        return f"{self.dossier_projet.name}/{EXTRACT_FRAMES_DIRNAME}/"

    @property
    def noms_conventionnels(self) -> tuple[str, ...]:
        return tuple(lot.lot_id for lot in self.lots)


def preparer_le_plan(dossier_projet: Path | str, *, rush_id: str,
                     video_path: Path | str,
                     cadences: Iterable[Any],
                     source_in_timecode: str | None = None,
                     source_out_timecode: str | None = None,
                     largeur: int | None = None,
                     hauteur: int | None = None,
                     couleur_inconnue_acceptee: bool = False
                     ) -> PlanExtraction:
    """Assembler le plan depuis les cadences **cochees** de `E2-2`.

    `cadences` est une suite de :class:`~mixed_media_utility.tui.cadences.Cadence`
    -- on n'en lit que `valeur` et `compte`, ce qui permet aussi d'y passer un
    couple `(valeur, compte)` en test sans fabriquer le modele entier.

    **Le nom et le dossier ne sont pas recomposes ici** : `build_lot_id` et
    `project_layout.extract_frames_dir` sont appeles avec les memes arguments que
    `run_extraction` leur passera. Une cadence que le coeur refuserait de
    nommer -- la fractionnaire d'`EPIC11-ARB-72` -- leve donc **ici**, avant
    tout ecran, avec le message du coeur.
    """
    dossier_projet = Path(dossier_projet)
    video_path = Path(video_path)
    bornes = {"source_in_timecode": source_in_timecode,
              "source_out_timecode": source_out_timecode}
    # **Une seule lecture de manifeste pour tous les lots**, et par
    # `projet_lecture` : c'est le module qui fait foi (AC 2.5), et relire une
    # fois par lot donnerait N etats potentiellement differents d'un document
    # qu'un autre processus peut ecrire pendant ce temps.
    etats = _etats_des_lots(dossier_projet)
    # Le manifeste ENTIER, et une seule fois : `resolve_version_rank` lit
    # `lots[]` et la ligne d'eau, ce que `_etats_des_lots` reduit deja a un
    # dictionnaire d'etats. Deux lectures donneraient deux etats d'un document
    # qu'un autre processus peut ecrire entre les deux.
    manifeste = projet_lecture.lire_manifeste(dossier_projet) or {}

    lots = []
    for cadence in cadences:
        valeur, compte = _valeur_et_compte(cadence)
        fps_target = float(valeur)
        dossier = extract_frames_dir(dossier_projet, rush_id, fps_target, **bornes)
        lot_id = build_lot_id(rush_id, fps_target, **bornes)
        rang, lot_id_versionne, refus = _version_proposee(
            manifeste, rush_id, fps_target, **bornes)
        lots.append(LotPrevu(
            fps_target=fps_target,
            frames=compte,
            lot_id=lot_id,
            dossier=dossier,
            deja_present=_porte_des_fichiers(dossier),
            etat=etats.get(lot_id),
            rang_de_version=rang,
            lot_id_versionne=lot_id_versionne,
            refus_de_version=refus,
        ))
    return PlanExtraction(
        dossier_projet=dossier_projet, rush_id=rush_id, video_path=video_path,
        lots=tuple(lots), octets_par_frame=octets_par_frame(largeur, hauteur),
        couleur_inconnue_acceptee=couleur_inconnue_acceptee, **bornes)


def _version_proposee(manifeste: dict, rush_id: str, fps_target: float,
                      **bornes: Any) -> tuple[int | None, str | None,
                                              str | None]:
    """`(rang, lot_id versionne, refus)` -- **tout vient du coeur**.

    Deux appels et rien d'autre : `resolve_version_rank` donne le rang,
    `build_lot_id(version_rank=)` donne le nom. Aucune arithmetique de rang,
    aucune composition de suffixe, aucun litteral de longueur -- le calcul du
    rang vit dans `io/version_ranks.py` et la convention de suffixe dans
    `io/naming.py`, chacune ecrite **une** fois pour les cinq objets
    versionnables du depot (`EPIC11-ARB-108`). Aucune des deux n'est nommee par
    sa fonction ici : une frontiere du depot compte a **zero** le vocabulaire
    des rangs dans tout `tui/`, prose comprise, et la citer suffirait a la faire
    rougir.

    **Les deux refus du coeur sont RELAYES, jamais devines** (AC 8.2) :

    * `ExtractionPersistenceError` -- tous les rangs de la famille sont
      consommes ;
    * `NamingError` -- le nom versionne depasserait la borne canonique. Le
      fragment `_v<N>` allonge l'identifiant, si bien que ce refus est
      atteignable par la version alors qu'il ne l'etait pas par le lot
      d'origine. Le message du coeur porte le chiffre ; le recalculer ici
      poserait une **seconde** redaction de la borne, ce que
      `tui/noms.LIMITE` existe justement pour empecher.

    Les deux messages nomment eux-memes deux issues -- « supprimer une version,
    ou ecraser sciemment » pour l'un, « renommer le fichier source plus court,
    ou ecraser sciemment » pour l'autre. Un refus de version ne ferme donc pas
    le point de jugement : `Écraser et réextraire` y reste, et c'est ce qui
    empeche ce regime d'etre le blocage sec qu'`EPIC11-ARB-89` interdit.

    **Aucune autre exception n'est attrapee.** Une panne hors de ces deux
    familles remonte, comme partout ailleurs dans ce module : la deguiser en
    « pas de version proposable » ferait disparaitre une panne reelle derriere
    une issue en moins.
    """
    try:
        rang = resolve_version_rank(manifeste, rush_id, fps_target, **bornes)
        return rang, build_lot_id(rush_id, fps_target, version_rank=rang,
                                  **bornes), None
    except (ExtractionPersistenceError, NamingError) as refus:
        return None, None, str(refus)


def _valeur_et_compte(cadence: Any) -> tuple[Fraction | float, int]:
    """Lire `(valeur, compte)` d'une `Cadence` ou d'un couple nu."""
    valeur = getattr(cadence, "valeur", None)
    if valeur is None:
        valeur, compte = cadence
        return valeur, int(compte)
    compte = getattr(cadence, "compte", None)
    if compte is None:
        raise ValueError(
            f"La cadence {getattr(cadence, 'libelle', cadence)!r} n'a pas de "
            "compte : le coeur la refuse, elle n'est donc pas cochable "
            "(AC 3.5) et n'entre pas dans un plan.")
    return valeur, int(compte)


def _etats_des_lots(dossier_projet: Path) -> dict[str, str]:
    """`lot_id -> state`, lu par `projet_lecture` et **apparie par lot_id**.

    Jamais par position : `lots[]` porte l'ordre de premiere creation, et un
    appariement positionnel ecrirait l'etat d'un lot sur un autre -- c'est le
    mutant `M25` de la story 5.7, ou 257 tests restaient verts.
    """
    manifeste = projet_lecture.lire_manifeste(dossier_projet) or {}
    lots = manifeste.get("lots")
    if not isinstance(lots, list):
        return {}
    etats = {}
    for lot in lots:
        if not isinstance(lot, dict):
            continue
        lot_id, etat = lot.get("lot_id"), lot.get("state")
        if isinstance(lot_id, str) and isinstance(etat, str):
            etats[lot_id] = etat
    return etats


def _porte_des_fichiers(dossier: Path) -> bool:
    """Vrai si le dossier de lot existe **et contient un fichier**.

    La meme mesure que `run_extraction` (« un lot deja present dans ... et ne
    sera pas efface implicitement ») : un dossier vide n'est pas un lot, et
    ouvrir l'ecran d'ecrasement pour lui serait une alarme sur rien.

    **Une panne de lecture rend faux** (revue de la vague 3, couche 2, `T2`) :
    `is_dir()` repond vrai sur un volume devenu illisible et `iterdir()` leve.
    Rendre faux revient a ne pas proposer l'ecrasement -- c'est le cote sur.
    """
    try:
        return dossier.is_dir() and any(e.is_file() for e in dossier.iterdir())
    except OSError:
        return False


# ---------------------------------------------------------------------------
# `E6` -- le panneau chiffre, ses noms, ses issues
# ---------------------------------------------------------------------------

def panneau_de_l_extraction(plan: PlanExtraction,
                            largeur: int = jetons.LARGEUR_PLANCHER,
                            ascii_seul: bool = False) -> Panneau:
    """Le cartouche de `E2-3`. Cinq lignes, et chacune est exigee par ARB-4.

    Ce qui sera produit (la destination et, sous le cartouche, les noms), en
    quelle quantite (les lots, les frames **par lot et au total**), ce que cela
    coute (l'espace disque, en majorant explicite). Les bornes s'y ajoutent
    parce qu'Egan les nomme dans sa formulation d'origine (« Apercu disque
    (majorant) + nombre de frames extraites et bornes timecode »).

    **Les noms vivent desormais DANS le panneau** (`EPIC11-ARB-141`). Ils y
    etaient des widgets a part, un par nom, pour qu'un nom refuse puisse porter
    sa propre couleur ; aucun n'etant plus editable, aucun ne peut plus etre
    refuse, et la liste redevient du texte de cartouche.
    """
    return Panneau(TITRE_A_ECRIRE, _lignes_communes(plan),
                   noms=noms_des_lots(plan, largeur, ascii_seul))


def panneau_de_l_ecrasement(plan: PlanExtraction,
                            largeur: int = jetons.LARGEUR_PLANCHER,
                            ascii_seul: bool = False) -> Panneau:
    """Le cartouche de la confirmation **en propre** d'un ecrasement.

    Il dit d'abord **ce qui existe deja** -- combien de lots, lesquels, combien
    de fichiers -- puis ce que l'ecriture produira. `EcranEcrasement` ajoute de
    son cote la phrase sur ce qu'ecraser ne regenere pas ; elle n'est pas redite
    ici.
    """
    lignes: list[LigneChiffree] = []
    deja = plan.lots_deja_presents
    if deja:
        # **Le bloc ne s'ouvre que s'il compte quelque chose.** Un conflit
        # d'ETAT seul -- le lot est passe a `pdf`, ses frames peuvent avoir ete
        # supprimees -- montait « Déjà sur le disque   0 lots », une ligne qui
        # ne dit rien et qui coute une ligne de grille sur l'ecran le plus
        # charge de l'atelier. Le bloc d'etat, lui, a toujours ete conditionnel.
        lignes.append(LigneChiffree(LIBELLE_DEJA, len(deja), "lots"))
        for lot in deja:
            lignes.append(LigneChiffree(f"  {lot.lot_id}",
                                        _compte_de_fichiers(lot.dossier),
                                        "fichiers"))
    etat = plan.lots_en_conflit_d_etat
    if etat:
        # **Le second chemin de conflit se dit dans le MEME cartouche.** Un lot
        # deja passe a `pdf` n'est pas « deja sur le disque » -- ses frames
        # peuvent avoir ete supprimees --, c'est un conflit d'ETAT, et le
        # confondre avec l'autre ferait un cartouche qui compte deux fois les
        # lots qui sont dans les deux cas.
        lignes.append(LigneChiffree(LIBELLE_ETAT_DEJA_AVANCE, len(etat), "lots"))
        for lot in etat:
            lignes.append(LigneChiffree(f"  {lot.lot_id}", lot.etat or ""))
    return Panneau(TITRE_ECRASEMENT, lignes + _lignes_communes(plan),
                   noms=noms_du_conflit(plan, largeur, ascii_seul))


def _lignes_communes(plan: PlanExtraction) -> list[LigneChiffree]:
    """Les lignes que les deux points de jugement partagent."""
    lignes = [
        LigneChiffree(LIBELLE_LOTS, len(plan.lots), "lots"),
        _ligne_des_frames(plan),
        LigneChiffree(LIBELLE_BORNES, texte_des_bornes(
            plan.source_in_timecode, plan.source_out_timecode)),
        _ligne_de_l_espace(plan),
        LigneChiffree(LIBELLE_DESTINATION, plan.destination),
    ]
    if plan.couleur_inconnue_acceptee:
        # `EPIC11-ARB-74` : une ligne du panneau, pas un ecran de plus.
        lignes.append(LigneChiffree(LIBELLE_COULEUR, COULEUR_INCONNUE_ACCEPTEE))
    return lignes


def _ligne_des_frames(plan: PlanExtraction) -> LigneChiffree:
    """« Frames écrites » : **par lot ET total** (AC 6.1).

    Un seul lot n'a pas de total a montrer -- `124 = 124` serait du bruit --,
    donc la forme somme n'apparait qu'a partir de deux, exactement comme la
    maquette `E2-3` la montre pour deux lots.
    """
    if len(plan.lots) == 1:
        return LigneChiffree(LIBELLE_FRAMES, plan.lots[0].frames, UNITE)
    somme = " + ".join(str(lot.frames) for lot in plan.lots)
    return LigneChiffree(LIBELLE_FRAMES,
                         f"{somme} = {plan.frames_total} {UNITE}")


def _ligne_de_l_espace(plan: PlanExtraction) -> LigneChiffree:
    """« Espace disque », **toujours** marquee majorant quand elle chiffre.

    Quand la resolution de la source n'est pas connue, la ligne dit qu'elle ne
    sait pas et ne porte **pas** la mention : `(majorant)` sur « inconnu »
    laisserait croire qu'un chiffre a ete calcule.
    """
    lisible = taille_lisible(plan.octets_majorants)
    if lisible is None:
        return LigneChiffree(LIBELLE_ESPACE,
                             "inconnu — résolution source non déclarée")
    valeur, _, unite = lisible.partition(" ")
    return LigneChiffree(LIBELLE_ESPACE, PREFIXE_APPROCHE + valeur, unite,
                         majorant=True)


def phrase_du_cout_de_la_version(plan: PlanExtraction) -> str:
    """`Créer une version n'efface rien : ces ~ 1,9 Go s'ajoutent au disque.`

    Le chiffre est **celui du plan**, compose par la meme fonction que la ligne
    « Espace disque » du cartouche : `taille_lisible(plan.octets_majorants)`,
    precede de la marque d'approche. Un chiffre en dur -- meme celui
    qu'`EPIC11-ARB-89` cite (« une version de lot 4K a 12 im/s pese plus de
    2 Go ») -- mentirait sur toutes les autres sources, et ce panneau est
    justement celui ou l'operateur decide de doubler son occupation disque.

    Sans majorant -- resolution de la source non declaree --, la phrase dit le
    fait **sans le chiffrer** : « n'efface rien, et s'ajoute au disque ». Un
    trou dans la phrase, ou pire un zero, serait annoncer que la version ne
    coute rien.

    **Aucune touche n'y est nommee** (AC 6.3, `EPIC11-ARB-56`) : la suppression
    d'un element de projet est la story 11.11, et `Suppr` n'existe pas encore.
    """
    lisible = taille_lisible(plan.octets_majorants)
    if lisible is None:
        return CE_QUE_LA_VERSION_COUTE_SANS_CHIFFRE
    return CE_QUE_LA_VERSION_COUTE.format(espace=PREFIXE_APPROCHE + lisible)


def _compte_de_fichiers(dossier: Path) -> int:
    """Le cardinal des fichiers d'un lot, **zero quand il ne se lit pas**.

    **Le seul des trois freres a n'avoir eu AUCUNE garde** (revue de la
    vague 3, couche 2, `T2`) : ni `is_dir()`, ni `except OSError`. Un
    `FileNotFoundError` en sortait, au point de JUGEMENT -- l'ecran qui compte
    ce qu'un ecrasement va detruire. Le declencheur mesure est etroit (une
    course entre la pose de `deja_present` et le comptage, dans la meme
    frappe), mais il n'a pas besoin d'etre large : un partage reseau demonte
    entre les deux suffit, et c'est exactement le mode de panne que la revue du
    2026-08-05 a fait disparaitre cote CLI.
    """
    try:
        return sum(1 for entree in dossier.iterdir() if entree.is_file())
    except OSError:
        return 0


def noms_des_lots(plan: PlanExtraction,
                  largeur: int = jetons.LARGEUR_PLANCHER,
                  ascii_seul: bool = False) -> list[str]:
    """Les noms produits, **derives par la convention du coeur**, un par ligne.

    Ils viennent de `build_lot_id`, deja calcule au plan : les recomposer ici
    ferait deux redactions de la meme convention.

    **Aucun n'est editable** (`EPIC11-ARB-141`, verbatim d'Egan : « On retire
    l'edition des noms PARTOUT ou elle ne peut pas etre effective »). Ce sont
    des lignes de texte, pas des champs -- c'est pour cela qu'ils vivent dans
    `Panneau.noms` et non dans un `ModeleNoms`, qui est le modele de l'edition.
    L'ecran, lui, n'en recoit aucun.

    Les montrer reste **obligatoire** : `EPIC11-ARB-4` exige du panneau chiffre
    qu'il porte « ce qui sera produit (noms de fichiers ou de lots) ». On retire
    a cet ecran un mode, pas sa raison d'etre.

    L'abregement passe par `jetons.abreger_nom`, qui coupe **au milieu** : un
    nom coupe par la fin perdrait sa queue, c'est-a-dire exactement la cadence
    qui distingue deux lots du meme rush.
    """
    budget = jetons.largeur_de_cartouche(largeur) - len(INDENT_DES_NOMS)
    return [INDENT_DES_NOMS + jetons.abreger_nom(lot.lot_id, budget, ascii_seul)
            for lot in plan.lots]


def noms_du_conflit(plan: PlanExtraction,
                    largeur: int = jetons.LARGEUR_PLANCHER,
                    ascii_seul: bool = False) -> list[str]:
    """Les noms du cartouche d'ecrasement : **une paire par lot**.

    `rush_01_25 → rush_01_25_v2` -- a gauche ce qu'« Écraser et réextraire »
    reecrit, a droite ce que « Créer la vN » ecrirait. Les deux issues qui
    ecrivent nomment donc chacune sa sortie **avant** que l'operateur valide
    (AC 2.3), et les deux noms viennent de `build_lot_id`, le second avec
    `version_rank=` (AC 2.2) : ni l'un ni l'autre n'est compose ici.

    **Une paire par ligne plutot qu'un bloc de plus**, et c'est une contrainte
    de grille mesuree : le cartouche d'ecrasement porte deja son compte de
    lots, une ligne par lot deja present, les cinq lignes communes et la
    phrase de ce qu'ecraser ne regenere pas. Un second bloc de noms lui
    couterait `1 + N` lignes de plus ; l'appariement n'en coute **aucune**.

    Le budget est **partage en deux moities**, chacune abregee par
    `jetons.abreger_nom`, qui coupe au milieu : un nom coupe par la fin
    perdrait sa cadence, et un nom versionne coupe par la fin perdrait son
    rang -- c'est-a-dire exactement ce qui le distingue de l'autre.

    Quand aucune version n'est proposable -- rangs epuises, ou nom versionne
    trop long --, la ligne **retombe sur le nom seul**. Montrer une fleche vers
    rien serait annoncer une issue que le panneau ne porte pas.
    """
    budget = jetons.largeur_de_cartouche(largeur) - len(INDENT_DES_NOMS)
    if not plan.version_proposable:
        return noms_des_lots(plan, largeur, ascii_seul)
    separateur = SEPARATEUR_DES_NOMS
    lignes = []
    for lot in plan.lots:
        # **Le budget se partage par le CARDINAL des noms de la ligne**, jamais
        # par un `2` litteral : la frontiere `test_la_TUI_ne_RECOPIE_aucun_code
        # _retour` interdit tout entier en clair dans ce module -- `2` y est le
        # code de refus du coeur --, et un partage ecrit `// len(parts)` dit en
        # plus ce qu'il partage.
        parts = (lot.lot_id, lot.lot_id_versionne or "")
        part = max((budget - jetons.colonnes(separateur)) // len(parts), 0)
        lignes.append(INDENT_DES_NOMS + separateur.join(
            jetons.abreger_nom(nom, part, ascii_seul) for nom in parts))
    return lignes


def issues_de_l_extraction() -> ChoixExclusif:
    """Les trois issues de `E2-3`. Une seule ecrit, et le curseur ne la vise pas."""
    return ChoixExclusif([
        Issue(ISSUE_EXTRAIRE, LIBELLE_EXTRAIRE, ecrit=True),
        Issue(ISSUE_MODIFIER, LIBELLE_MODIFIER),
        Issue(ISSUE_ANNULER, LIBELLE_ANNULER),
    ])


def libelle_de_la_version(rang: int | None) -> str:
    """`Créer la v2` quand les lots partagent un rang, sinon le libelle pluriel.

    Meme geste et meme redaction que `atelier_pdf_versions.libelle_de_la_creation`
    et `atelier_exports_versions.libelle_de_la_creation` : `EPIC11-ARB-108`
    veut un seul mecanisme de versionnage pour tous les objets, donc un seul
    vocabulaire a l'ecran. Le rang est **affiche**, jamais derive ici.

    ``None`` -- les lots du plan ne consomment pas le meme rang -- rend
    :data:`LIBELLE_NOUVELLES_VERSIONS`, qui n'en nomme aucun plutot que d'en
    nommer un faux.
    """
    if rang is None:
        return LIBELLE_NOUVELLES_VERSIONS
    return LIBELLE_NOUVELLE_VERSION.format(rang=rang)


def issues_de_l_ecrasement(plan: PlanExtraction) -> ChoixExclusif:
    """Les issues d'un conflit d'ecriture -- **DEUX d'entre elles ecrivent**.

    `EPIC11-ARB-89`, verbatim d'Egan : « au lieu d'un overwrite destructif,
    toujours proposer un versionnage avec un suffixe [...] Mais toujours
    permettre une reecriture plutot qu'un blocage sec. » Les deux moities de
    cette phrase sont les deux issues qui portent ``ecrit=True`` :

    * `Écraser et réextraire` -- la reecriture **consciente**, dont le libelle
      nomme la destruction ;
    * `Créer la vN` -- la version a cote, qui n'efface rien.

    Ce panneau n'en portait qu'**une**, et c'etait la destructrice : le chemin
    le plus destructif du produit etait aussi le seul a n'offrir aucune autre
    ecriture. C'est le defaut que la story 11.4d ferme (AC 1.1).

    **L'ordre suit la maquette approuvee `T4-1`** -- ecraser, puis la version,
    puis les sorties -- et il n'a aucune consequence sur la surete : c'est
    `ChoixExclusif.__post_init__` qui pose le curseur sur la premiere issue qui
    n'ecrit pas, donc jamais sur l'une des deux premieres (`EPIC11-ARB-7`,
    `EPIC11-ARB-45`). Le rang de l'issue principale ne bouge pas, c'est le
    curseur qui se place.

    **La version disparait quand le coeur la refuse**, et alors seulement :
    rangs epuises, ou nom versionne au-dela de la borne canonique. Le panneau
    garde ses trois issues d'origine, `Écraser et réextraire` comprise --
    c'est-a-dire qu'il ne devient jamais un blocage sec --, et le refus du
    coeur est relaye **verbatim** dans le cartouche par
    :meth:`EcranExtractionEcrasement.lignes_du_panneau`. Les deux messages du
    coeur nomment eux-memes l'ecrasement conscient comme seconde issue : la
    surface dit donc la meme chose que le noyau, sans la reecrire.
    """
    issues = [Issue(ISSUE_ECRASER, LIBELLE_ECRASER, ecrit=True)]
    if plan.version_proposable:
        issues.append(Issue(ISSUE_NOUVELLE_VERSION,
                            libelle_de_la_version(plan.rang_de_version),
                            ecrit=True))
    issues.extend([Issue(ISSUE_MODIFIER, LIBELLE_MODIFIER),
                   Issue(ISSUE_ANNULER, LIBELLE_ANNULER)])
    return ChoixExclusif(issues)


#: La conduite que chaque issue ecrivante retient. **Une table et non deux
#: `if`** : c'est le seul endroit du module qui traduit un choix d'ecran en
#: drapeau de coeur, et deux redactions divergeraient au premier ecran ajoute.
#: Une issue absente de cette table n'ecrit pas.
CONDUITE_DES_ISSUES: dict[str, str] = {
    ISSUE_ECRASER: CONDUITE_ECRASEMENT_CONSCIENT,
    ISSUE_NOUVELLE_VERSION: CONDUITE_NOUVELLE_VERSION,
}


# ---------------------------------------------------------------------------
# `E2-3` et son ecran d'ecrasement -- **les deux ecrans de cet atelier**
#
# **Pourquoi deux sous-classes, et non les deux classes partagees telles
# quelles** (`EPIC11-ARB-141`). `PanneauConfirmation` et `EcranEcrasement`
# portent `execution.RACCOURCIS_CONFIRMATION`, qui promet encore une touche
# d'edition de nom. Cet atelier n'en a plus : l'annoncer promettrait une touche
# qui ne fait rien. Une constante posee sur l'INSTANCE ne tiendrait pas --
# `EcranChiffre._appliquer_les_raccourcis` relit `type(self).raccourcis` a
# chaque rafraichissement --, donc la ligne se pose au niveau de la CLASSE,
# comme la garde de paquet de `test_repli_ascii.py` la lit.
#
# `noms_hors_convention` a disparu avec elles : ce module portait un verrou qui
# gardait l'action principale inaccessible tant qu'un nom s'ecartait de la
# convention, faute de pouvoir faire atteindre le coeur a un nom edite. Il n'y
# a plus de nom edite ; le verrou n'a plus d'objet, et il **cesse d'exister**
# plutot que de cesser de verrouiller -- une garde desarmee se rearme, une
# fonction absente ne revient pas toute seule.
# ---------------------------------------------------------------------------


class _SansEditionDeNom:
    """Ce que les deux ecrans de cet atelier ajoutent, et rien d'autre.

    Un mixin plutot qu'une duplication : les deux ecrans n'ont **pas** la meme
    classe de base -- l'un est le panneau nominal, l'autre l'ecran d'ecrasement
    qui porte sa propre phrase sur ce qu'ecraser ne regenere pas -- et ce qu'ils
    partagent est exactement ce que `EPIC11-ARB-141` leur fait.
    """

    #: **Un ATTRIBUT de classe, jamais une `@property`.** La garde de paquet de
    #: `test_repli_ascii.py` balaye les sous-classes de `Palier` et lit
    #: `classe.raccourcis` **au niveau de la classe** : une propriete y rendrait
    #: l'objet `property` et ferait echapper l'ecran a la mesure.
    raccourcis = RACCOURCIS_EXTRACTION_CONFIRMATION

    def lignes_du_panneau(self) -> list[str]:
        """Le cartouche **avec sa liste de noms**, a la largeur courante.

        `EcranChiffre` rend un panneau **sans** ses noms -- chez lui les noms
        sont des widgets a part, pour qu'un nom refuse puisse porter sa propre
        couleur. Ici aucun n'est editable, donc aucun ne peut etre refuse : la
        liste redevient du texte de cartouche, et c'est `Panneau.rendu` qui la
        pose apres une ligne vide, comme la maquette la dessine.

        Le panneau est recompose a la largeur courante plutot que garde tel
        quel : c'est cette largeur qui borne l'abregement des noms, et
        `ascii_seul` **precede la mesure** -- `…` vaut une colonne, `...` en
        vaut trois.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        largeur = self.app.size.width
        panneau = self._panneau_a_la_largeur(largeur, ascii_seul)
        return panneau.rendu(largeur, ascii_seul)


class EcranExtractionConfirmation(_SansEditionDeNom, PanneauConfirmation):
    """`E2-3` -- le point de jugement de l'Extraction. **Rien n'est ecrit.**"""

    def __init__(self, panneau: Panneau, choix: ChoixExclusif, *,
                 sur_issue: Callable[[Issue], None] | None = None,
                 plan: PlanExtraction | None = None,
                 objet: str = "") -> None:
        # **Aucun `noms=`**, et c'est le sujet d'`EPIC11-ARB-141` : le modele
        # d'edition n'est meme plus importe par ce module. `EcranChiffre` en
        # pose un vide de lui-meme, si bien que `Tab` n'a aucune destination et
        # que `traiter` le rend inerte -- ce n'est pas une garde ajoutee ici,
        # c'est la consequence de ne pas donner de noms editables.
        super().__init__(panneau, choix, sur_issue=sur_issue, objet=objet)
        #: Le plan montre, ou `None` quand l'appelant n'en a pas donne. Il ne
        #: sert qu'a **recomposer** le cartouche a la largeur courante ; sans
        #: lui, le panneau recu a la construction sert tel quel.
        self.plan = plan

    def _panneau_a_la_largeur(self, largeur: int, ascii_seul: bool) -> Panneau:
        if self.plan is None:
            return self.panneau
        return panneau_de_l_extraction(self.plan, largeur, ascii_seul)


class EcranExtractionEcrasement(_SansEditionDeNom, EcranEcrasement):
    """La confirmation **en propre** d'un ecrasement (`EPIC11-ARB-4`).

    Son cartouche **defile** depuis `EPIC11-ARB-245` : il porte trois phrases
    de consequence et jusqu'a treize lignes de detail, la ou la grille lui en
    laisse dix.
    """

    #: **Un ATTRIBUT de classe**, comme celui du mixin et pour le meme motif :
    #: la garde de paquet de `test_repli_ascii.py` lit `classe.raccourcis`.
    #: C'est la ligne du cartouche qui DEFILE ; celle du cartouche qui tient
    #: est posee a chaque rafraichissement par :meth:`_appliquer_les_raccourcis`.
    raccourcis = RACCOURCIS_EXTRACTION_ECRASEMENT

    def __init__(self, panneau: Panneau, choix: ChoixExclusif, *,
                 sur_issue: Callable[[Issue], None] | None = None,
                 plan: PlanExtraction | None = None,
                 objet: str = "") -> None:
        super().__init__(panneau, choix, sur_issue=sur_issue, objet=objet)
        self.plan = plan

    def _panneau_a_la_largeur(self, largeur: int, ascii_seul: bool) -> Panneau:
        if self.plan is None:
            return self.panneau
        return panneau_de_l_ecrasement(self.plan, largeur, ascii_seul)

    #: Le nom sous lequel la ligne de pli annonce un nom apparie cache, et sa
    #: forme collective. `EPIC11-ARB-245` : la ligne de pli NOMME ce qu'elle
    #: cache -- « la suite : bornes, destination, 3 noms appariés » --, jamais
    #: un nombre de lignes muet.
    NOM_APPARIE = "nom apparié"
    NOMS_APPARIES = "{compte} noms appariés"

    def lignes_defilantes(self) -> list[LigneDefilante]:
        """Le detail reperable du cartouche, **chaque ligne avec son NOM**.

        C'est ce qui passe sous le pli quand la grille manque : les lignes
        chiffrees, la respiration, les noms apparies. Les phrases de
        consequence, elles, n'en sont pas -- elles restent au-dessus
        (`EcranEcrasement.phrases_de_consequence`).

        **Le nom vient de `Panneau.rendu_nomme`, jamais d'une seconde liste.**
        Le panneau apparie lui-meme chaque ligne rendue au libelle qui l'a
        produite ; recomposer ce lien ici, par position, serait le mutant `M33`
        de la story 5.6 -- une permutation y reste verte.

        Le libelle est mis en bas de casse parce qu'une ligne de pli est une
        phrase (« la suite : bornes, destination ») et non un tableau : `Bornes`
        au milieu d'une phrase se lirait comme un nom propre.
        """
        ascii_seul = getattr(self.app, "ascii_seul", False)
        largeur = self.app.size.width
        panneau = self._panneau_a_la_largeur(largeur, ascii_seul)
        lignes: list[LigneDefilante] = []
        for texte, libelle in panneau.rendu_nomme(largeur, ascii_seul):
            if libelle is None:
                lignes.append(LigneDefilante(texte))
            elif libelle == Panneau.LIBELLE_DES_NOMS:
                lignes.append(LigneDefilante(texte, self.NOM_APPARIE,
                                             self.NOMS_APPARIES))
            else:
                lignes.append(LigneDefilante(texte, libelle.strip().lower()))
        return lignes

    def phrases_de_consequence(self, ascii_seul: bool = False) -> list[str]:
        """Les DEUX phrases de l'ecrasement, **et celle de la version**.

        `EcranEcrasement` pose ce qu'ecraser detruit et ce qu'il ne regenere
        pas ; la story 11.4d (AC 6.2) lui ajoute le **symetrique** de l'autre
        issue qui ecrit. Sans lui, le panneau chiffrait le prix d'une seule des
        deux : l'operateur savait ce qu'ecraser detruit et ignorait ce que la
        version coute.

        La troisieme phrase a **deux redactions, et une seule sort a la fois** :

        * la version est proposable -- son cout, lu du **majorant deja calcule
          par le plan** (`_ligne_de_l_espace`, mention comprise), jamais un
          chiffre en dur ;
        * elle ne l'est pas -- le refus du coeur, **verbatim**, avec son propre
          chiffre. Il nomme lui-meme sa seconde issue (« ecraser sciemment »),
          qui est precisement celle que le panneau garde : le refus ne ferme
          donc rien.

        Le refus prend la place du cout plutot que de s'ajouter, et c'est la
        grille qui l'exige : ce cartouche est le plus charge de l'atelier.

        **Les trois sont AU-DESSUS DU PLI** (`EPIC11-ARB-245`). Elles etaient
        en QUEUE de cartouche, c'est-a-dire exactement la ou un pli les aurait
        cachees les premieres -- et l'avertissement qu'`EPIC11-ARB-89` exige
        avant une ecriture destructive consciente avec elles.
        """
        return super().phrases_de_consequence(ascii_seul) + [
            self.RETRAIT_DES_CONSEQUENCES + self.phrase_de_la_version()]

    def lignes_du_panneau(self) -> list[str]:
        """Le cartouche entier, **par `EcranEcrasement` et non par le mixin**.

        L'ordre de resolution est `_SansEditionDeNom` puis `EcranEcrasement` :
        sans cette delegation explicite, le mixin gagne, rend le panneau nu et
        n'appelle pas `super()`. C'est exactement le defaut que le lot F avait
        trouve ici -- `EcranEcrasement.lignes_du_panneau` n'etait jamais
        atteinte, et l'ecran ne disait plus ce qu'ecraser ne regenere pas --,
        et il reviendrait a l'identique si cette methode disparaissait. Le
        contenu recompose a la largeur courante, lui, arrive par
        :meth:`lignes_defilantes`, qui appelle `_panneau_a_la_largeur` comme le
        mixin le faisait.
        """
        return EcranEcrasement.lignes_du_panneau(self)

    def _appliquer_les_raccourcis(self) -> None:
        """`Ctrl+↓` n'est annonce que s'il y a une suite a lire.

        Meme geste que `EcranChiffre._appliquer_les_raccourcis`, dont c'est la
        specialisation : une constante de module posee sur l'instance, jamais
        une propriete -- les deux lignes restent ainsi balayees une par une par
        la garde d'epic, qui lit la CLASSE.
        """
        self.raccourcis = (RACCOURCIS_EXTRACTION_ECRASEMENT if self.pli().replie
                           else RACCOURCIS_EXTRACTION_CONFIRMATION)

    def phrase_de_la_version(self) -> str:
        """Le cout de la version, ou le refus du coeur qui l'empeche."""
        if self.plan is None:
            return CE_QUE_LA_VERSION_COUTE_SANS_CHIFFRE
        refus = self.plan.refus_de_version
        if refus is not None:
            return refus
        return phrase_du_cout_de_la_version(self.plan)


def ouvrir_le_point_de_jugement(app, plan: PlanExtraction, *,
                                sur_ecriture: Callable[[PlanExtraction], None],
                                sur_modification: Callable[[], None] | None = None,
                                objet: str = ""):
    """Monter `E2-3` -- **ou l'ecran d'ecrasement**, jamais le nominal des deux.

    `EPIC11-ARB-4`, corollaire verbatim : « Une commande destructive
    (ecrasement d'un lot existant) porte une confirmation **en propre**,
    distincte de celle-ci ». Le choix se fait sur `plan.en_conflit`,
    c'est-a-dire sur le disque et sur le manifeste, jamais sur une intention :
    ce sont les memes mesures que `run_extraction` fait avant de refuser.

    **DEUX chemins de conflit y menent, et le second n'y menait pas**
    (story 11.4d, AC 4.1) :

    * le dossier de frames deja peuple (`plan.ecrase`) -- il ouvrait deja cet
      ecran ;
    * le lot deja passe a `pdf` ou au-dela (`plan.conflit_d_etat`) -- il
      n'ouvrait **rien**. Le refus tombait au milieu de
      :func:`executer_le_plan`, apres que la passe s'etait declaree, et
      :func:`ouvrir_le_refus` montait un `EcranRefus` sans une seule suite :
      le blocage sec qu'`EPIC11-ARB-89` interdit. Le conflit d'etat etant connu
      **au plan** (`LotPrevu.etat`, renseigne par :func:`preparer_le_plan`), il
      se juge desormais avant d'engager quoi que ce soit (AC 4.3).

    La garde :func:`refus_d_etat_de_lot` **reste** et refuse toujours
    (`EPIC11-ARB-83`, AC 4.2) : ce qui change est ce qui **suit** le refus,
    jamais le refus.

    Rien n'est ecrit par cette fonction ni par l'ecran qu'elle monte. L'ecriture
    n'a lieu que dans `sur_ecriture`, appele sur la seule issue qui porte
    `ecrit=True`.

    **Le parametre `modele` a disparu** (`EPIC11-ARB-141`) : il servait a
    injecter un jeu de noms editables, et il n'y en a plus. Le seul appelant qui
    s'en servait etait un banc.
    """
    ecrasement = plan.en_conflit

    def sur_issue(issue: Issue) -> None:
        if issue.cle == ISSUE_MODIFIER:
            if sur_modification is not None:
                sur_modification()
            else:
                app.action_remonter()
            return
        if issue.cle == ISSUE_ANNULER:
            # « Annuler, ne rien ecrire » : on remonte d'UN palier, et rien
            # d'autre. `EPIC11-ARB-2`, verbatim : « Un formulaire abandonne en
            # cours ne produit aucun ecrit. »
            app.action_remonter()
            return
        # **La conduite retenue voyage AVEC le plan**, et c'est ce qui la rend
        # exclusive sans qu'aucune garde ait a la verifier : un plan porte UNE
        # conduite, `run_extraction` en derive ses deux drapeaux, et l'etat
        # « les deux a la fois » que le coeur refuse nommement n'est pas
        # representable (AC 3.3). Rien d'autre ne change de la signature de
        # `sur_ecriture`, qui recoit toujours un plan et rien qu'un plan.
        sur_ecriture(replace(plan, conduite=CONDUITE_DES_ISSUES.get(
            issue.cle, CONDUITE_NOMINALE)))

    classe = (EcranExtractionEcrasement if ecrasement
              else EcranExtractionConfirmation)
    panneau = (panneau_de_l_ecrasement(plan) if ecrasement
               else panneau_de_l_extraction(plan))
    choix = (issues_de_l_ecrasement(plan) if ecrasement
             else issues_de_l_extraction())
    # **L'objet est DONNE, il n'est pas devine** (`J3`) : `execution.py` porte
    # les cinq ecrans partages par les quatre ateliers, et le mot « rush » est
    # du vocabulaire de celui-ci. C'est l'atelier qui sait sur quoi on
    # travaille, et le mixin `coque.ObjetTravaille` le fait rendre AU DESSIN --
    # jamais ecrire dans le `Contexte` de session, qui traverse les etages et
    # poserait le rush sur le bandeau du voisin.
    ecran = classe(panneau, choix, sur_issue=sur_issue, plan=plan, objet=objet)
    app.descendre(ecran)
    return ecran


# ---------------------------------------------------------------------------
# `E7` -- l'execution : une invocation de `run_extraction` par lot
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LotEcrit:
    """Un lot **reellement** ecrit : ses chiffres sont mesures, pas estimes."""

    lot_id: str
    frames: int
    fps_target: float
    octets: int
    dossier: Path

    @property
    def texte_de_cadence(self) -> str:
        entier = int(self.fps_target)
        valeur = entier if self.fps_target == entier else self.fps_target
        return f"{valeur} fps"


@dataclass(frozen=True)
class RefusDExtraction:
    """Un refus rendu **tel quel** : le code du coeur, sa phrase, son code retour.

    `EPIC11-ARB-30` : « le code **et** la phrase viennent du coeur. La TUI met
    en forme -- elle n'interprete pas, elle ne resume pas, elle ne requalifie
    pas. » Le `code` nomme la classe d'exception du coeur et le code de sortie
    que la table d'`extraction.py` lui associe ; le `message` est la chaine
    levee, non retouchee.
    """

    code: str
    message: str
    code_retour: int


@dataclass(frozen=True)
class RapportExtraction:
    """Ce que l'execution a produit, et ce qu'elle a refuse.

    Les deux cohabitent : une serie de trois lots dont le deuxieme echoue a
    ecrit un lot, et l'ecran de resultat doit le dire plutot que de tout
    presenter comme perdu.
    """

    lots_ecrits: tuple[LotEcrit, ...] = ()
    refus: RefusDExtraction | None = None
    interrompu: bool = False
    manifeste: Path | None = None

    @property
    def code_retour(self) -> int:
        """Le code retour de la serie. **Lu** de la table du coeur.

        `EPIC11-ARB-75` : la table est descendue dans `extraction.py` et « est
        **lue des deux cotes** ». Aucun entier de code retour n'est ecrit dans
        ce module ; les deux valeurs citees ici sont les constantes du coeur.
        """
        if self.refus is not None:
            return self.refus.code_retour
        if self.interrompu:
            return extraction.CODE_INTERRUPTION
        return extraction.CODE_SUCCES

    @property
    def frames_ecrites(self) -> int:
        return sum(lot.frames for lot in self.lots_ecrits)


#: L'en-tete qu'`executer_le_plan` inscrit au journal au debut de CHAQUE lot.
#:
#: Elle existe pour une raison precise et non pour decorer : depuis
#: `EPIC11-ARB-93`, le journal n'est plus remis a zero entre deux lots -- c'est
#: ce qui rend enfin lisibles les lignes que le coeur emet, et qui etaient
#: injoignables des le second lot. Mais le meme changement fait cohabiter les
#: jalons de plusieurs lots, et `26/26 frames` suivi de `1/13 frames` se lirait
#: comme un compte qui recule. C'est l'objection que la revue de la vague 1
#: avait opposee, et elle etait juste : cette ligne est ce qui la ferme.
#:
#: Le rang est **1-indexe** et porte son total (`lot 2/3`) : un operateur qui
#: relit un journal veut savoir ou il en etait, pas seulement quel lot il
#: regarde.
EN_TETE_DE_LOT = "-- lot {rang}/{total} : {lot_id}"


def nom_prevu(plan: PlanExtraction, lot: LotPrevu) -> str:
    """Le `lot_id` que **cette conduite-ci** ecrira pour ce lot.

    Le nom versionne quand l'operateur a retenu « Creer la vN », le nom
    d'origine sinon. `EPIC11-ARB-46`, verbatim : « l'apercu ne peut jamais
    mentir » -- et la declaration de passe comme l'en-tete du journal sont des
    apercus : annoncer `rush_01_25` pendant qu'on ecrit `rush_01_25_v2` ferait
    chercher un dossier qui n'existe pas.

    **Ce n'est pas le nom du RAPPORT.** Celui-la vient du coeur
    (`issue.lot_id`) et de lui seul, parce que c'est le seul qui soit mesure
    plutot que prevu (AC 3.4).
    """
    if plan.nouvelle_version and lot.lot_id_versionne is not None:
        return lot.lot_id_versionne
    return lot.lot_id


def en_tete_de_lot(index: int, total: int, lot_id: str) -> str:
    """L'en-tete du lot d'`index` (0-indexe), rendu 1-indexe pour l'operateur.

    **Cette fonction existe pour une raison de FRONTIERE, et le dire evite de
    la reinliner.** La conversion `index + 1` vivait d'abord dans
    :func:`executer_le_plan`, sous la forme `enumerate(plan.lots, start=1)`.
    `test_la_TUI_ne_RECOPIE_aucun_code_retour` l'a refusee, et elle a eu
    raison : cette frontiere interdit **tout** entier litteral dans les quatre
    fonctions qui decident d'un code retour, precisement parce que « lit la
    table » n'est pas mesurable autrement. Son docstring nomme d'avance la
    facon dont elle se casse -- « une frontiere qui les interdirait [partout]
    serait affaiblie a la premiere relecture ».

    Relacher la frontiere pour y laisser passer un rang de liste aurait donc
    ete l'exemple meme de ce qu'elle previent. Le rang demenage ; la garde
    reste entiere.
    """
    return EN_TETE_DE_LOT.format(rang=index + 1, total=total, lot_id=lot_id)


def canal_de_progression(surface: SurfaceExecution, total: int):
    """Le **seul** canal de progression (AC 7.4), et son adaptation d'arite.

    Deux faits mesures, qui expliquent pourquoi cette fonction existe :

    * `SurfaceExecution.emetteur(total)` est le seul appel qui **remet a zero**
      l'avancement, le journal et l'estimateur. Le sauter ferait afficher au lot
      suivant les jalons du precedent, donc un compte qui recule ;
    * `run_extraction` attend un **appelable a deux arguments** `(faites,
      total)` : `ffmpeg_utils` le remet dans un `EmetteurProgression` a lui
      (`ffmpeg_utils.py:584`). Or l'objet rendu par `emetteur()` **n'est pas
      appelable** -- `EmetteurProgression` n'expose que `emettre(faites)` --,
      donc le passer tel quel eteindrait le canal EN SILENCE : `callable(...)`
      y rend faux et l'emetteur du coeur se declare inactif sans rien lever.

    Aucun second canal n'existe : cette fonction est le seul chemin par lequel
    un jalon du coeur atteint l'ecran.
    """
    emetteur = surface.emetteur(total)
    return lambda faites, _total: emetteur.emettre(faites)


def executer_le_plan(plan: PlanExtraction, surface: SurfaceExecution, *,
                     logger, hote: Callable[..., Any] | None = None,
                     interrompu: Callable[[], bool] | None = None,
                     extraire: Callable[..., Any] | None = None
                     ) -> RapportExtraction:
    """Extraire les lots du plan, un appel de `run_extraction` par lot.

    `hote` est `CoqueTui.executer_en_processus` : le coeur est **heberge**, pas
    relance (`EPIC11-ARB-1`). Il vaut l'appel direct par defaut, pour que le
    modele se mesure sans monter d'application.

    **L'ordre des lots est celui du plan**, et un echec n'annule pas ce qui
    precede : les lots deja ecrits le restent, et le rapport les porte. C'est la
    propriete de cette boucle que la fiche 11.4 demande de mesurer avec un echec
    **ailleurs qu'en premiere position**.

    `interrompu` est consulte **entre deux lots**. La granularite est celle-la
    et pas une autre : a l'interieur d'un lot, l'appel a ffmpeg est synchrone et
    le coeur n'offre aucun point d'arret -- le dire est plus honnete que de
    faire croire a une interruption immediate.
    """
    hote = hote or (lambda fonction, *args, **kwargs: fonction(*args, **kwargs))
    extraire = extraire or extraction.run_extraction
    ecrits: list[LotEcrit] = []
    manifeste = plan.dossier_projet / MANIFEST_FILENAME
    # **La passe se declare AVANT son premier lot** (11.4e, AC 8.1). Sans elle
    # la surface ne connait qu'un cardinal a la fois : le total ne pourrait que
    # grossir de lot en lot, et « 26/26, 100 % » a la fin du premier lot d'une
    # passe qui en compte trois est une ligne fausse. La declaration est aussi
    # ce qui donne a `E2-4` sa liste des lots et son rang -- le champ existe
    # dans la surface, ce chemin est ce qui l'ECRIT.
    if plan.lots:
        surface.declarer_la_passe(
            LIBELLE_DE_LA_PASSE,
            [(nom_prevu(plan, lot), lot.frames) for lot in plan.lots])

    for rang, lot in enumerate(plan.lots):
        if interrompu is not None and interrompu():
            return RapportExtraction(tuple(ecrits), None, True, manifeste)
        # **La garde d'etat ne juge que la conduite NOMINALE**, et c'est ce que
        # les deux issues ecrivantes du point de jugement veulent dire
        # (`EPIC11-ARB-89`, story 11.4d AC 4) :
        #
        # * `nouvelle_version` vise un `lot_id` NEUF -- `current_state` y vaut
        #   `None`, il n'y a aucune transition a juger, et juger celle du lot
        #   d'origine refuserait une ecriture qui ne le touche pas ;
        # * `ecrasement_conscient` est la reecriture **consciente** qu'Egan
        #   exige de toujours permettre : « la rigueur de l'outil ne doit pas
        #   empecher une ecriture destructive CONSCIENTE (apres avertissement) ».
        #   Le coeur contourne alors son propre refus pour cet appel seul, et
        #   journalise l'avertissement (`message_avertissement_ecrasement`) ;
        #   garder la garde ici la rendrait inerte, c'est-a-dire un blocage sec
        #   deguise en issue.
        #
        # La garde **reste** pour la conduite nominale, et c'est la que
        # `EPIC11-ARB-83` la veut : elle nomme le refus avant d'engager quoi que
        # ce soit, au lieu de relayer une exception. Le point de jugement la
        # consulte desormais AVANT la serie (`plan.conflit_d_etat`) ; ce
        # passage-ci reste le filet du cas ou l'etat change entre le plan et
        # l'execution (AC 4.4).
        refus = (refus_d_etat_de_lot(lot)
                 if plan.conduite == CONDUITE_NOMINALE else None)
        if refus is not None:
            return RapportExtraction(tuple(ecrits), refus, False, manifeste)
        # **La ligne qui NOMME le lot, et c'est elle qui rend `EPIC11-ARB-93`
        # tenable.** Le journal n'est plus remis a zero entre deux lots, donc
        # les jalons du precedent restent visibles ; sans en-tete, `26/26` puis
        # `1/13` se lirait comme « un compte qui recule », l'objection exacte
        # que la revue de la vague 1 avait opposee. Nommee, la rupture se lit
        # pour ce qu'elle est : un changement de lot.
        surface.journal.inscrire(
            en_tete_de_lot(rang, len(plan.lots), nom_prevu(plan, lot)))
        rappel = canal_de_progression(surface, lot.frames)
        try:
            issue = hote(
                extraire,
                project_dir=plan.dossier_projet,
                video_path=plan.video_path,
                fps_target=lot.fps_target,
                source_in_timecode=plan.source_in_timecode,
                source_out_timecode=plan.source_out_timecode,
                # **`overwrite` tombe des que la version est retenue**
                # (AC 3.1) : « Creer la version » vise un dossier neuf, et
                # `lot.deja_present` parle de celui du lot d'ORIGINE. Le passer
                # ferait ecraser un dossier que cette issue existe pour ne pas
                # toucher.
                overwrite=lot.deja_present and not plan.nouvelle_version,
                nouvelle_version=plan.nouvelle_version,
                ecrasement_conscient=plan.ecrasement_conscient,
                consent_granted=True,
                unknown_color_accepted=plan.couleur_inconnue_acceptee,
                logger=logger,
                rappel_progression=rappel,
            )
        except BaseException as exception:  # noqa: BLE001 -- voir refus_de
            refus = refus_de(exception)
            if refus is None:
                # Hors table : on **relaie**. Deguiser une panne inconnue en
                # refus metier est exactement ce que `correspondance_de_sortie`
                # existe pour empecher (« l'appelant relaie alors l'exception
                # au lieu de la deguiser en refus metier »).
                raise
            return RapportExtraction(tuple(ecrits), refus, False, manifeste)

        if not issue.granted:
            # Refus de confirmation du coeur (story 3.3) : rien n'est ecrit,
            # aucun dossier de lot n'est cree, et le code retour est celui du
            # refus -- pas celui d'une erreur.
            return RapportExtraction(
                tuple(ecrits),
                RefusDExtraction(code=_CODE_REFUS_DE_CONFIRMATION,
                                 message=issue.message,
                                 code_retour=extraction.CODE_REFUS),
                False, manifeste)

        ecrits.append(LotEcrit(
            lot_id=issue.lot_id or lot.lot_id,
            frames=issue.written_frame_count,
            fps_target=lot.fps_target,
            octets=_octets_du_dossier(issue.frames_dir or lot.dossier),
            dossier=issue.frames_dir or lot.dossier))
    return RapportExtraction(tuple(ecrits), None, False, manifeste)


#: Le « code » d'un refus de confirmation. Ce n'est pas une exception : le coeur
#: rend `granted=False` avec sa phrase, et `ExtractionOutcome` documente que
#: « l'appelant renvoie le code de sortie `3` sans passer par le chemin
#: d'erreur ». Le mot nomme donc l'etat du coeur, pas une invention d'ecran.
_CODE_REFUS_DE_CONFIRMATION = "confirmation-refusee"


def refus_d_etat_de_lot(lot: LotPrevu) -> RefusDExtraction | None:
    """AC 7.5 -- un lot passe a `pdf` ou au-dela est refuse **avant** d'ecrire.

    **Le refus vient du coeur** : la transition est jugee par
    `io.manifest.validate_lot_state_transition`, la meme fonction que
    `persist_extraction` appelle, et le message affiche est celui qu'elle leve.
    Rien n'est reimplemente ici -- ni la machine a etats, ni son vocabulaire.

    **Cette garde DOUBLE le refus du coeur ; elle ne le remplace plus.**
    C'est vrai depuis le lot `V1` de la story 11.4c (commit `8894f52`, le
    2026-08-30), et la phrase precedente disait exactement le contraire -- d'ou
    cette reecriture, faite au lot `O` par l'agent qui tenait `tui/` a ce
    moment-la.

    **Ce qu'elle tenait, et pourquoi elle etait load-bearing.**
    `EPIC11-ARB-83`, verbatim : « La garde `refus_d_etat_de_lot` de la TUI
    (lot E) est **load-bearing** : elle est ce qui tient l'AC 7.5, pas une
    ceinture par-dessus une bretelle du coeur. La retirer au motif que "le
    coeur refuse de toute facon" detruirait des frames livrees. » Le motif
    etait une mesure : `run_extraction` ne jugeait la transition qu'a son
    **etape 6**, la persistance, c'est-a-dire **apres** avoir ecrit les TIFF
    (etape 5) et, quand `overwrite` etait vrai, **apres** avoir efface le lot
    precedent (`_clear_existing_lot`). Confirmer un ecrasement sur un lot deja
    passe a `pdf` detruisait donc les frames qu'une planche imprimee reference,
    puis refusait -- alors que le message du coeur affirme « Aucune ecriture
    n'a eu lieu », ce qui n'etait vrai que du **manifeste**.

    **Ce qui a change.** Le lot `V1` de 11.4c a remonte ce jugement **en
    amont** dans `run_extraction` : la transition est desormais validee a
    l'etape 1, avant ffmpeg et avant tout effacement, par
    `validate_extraction_state_transition`. Le coeur refuse donc de lui-meme
    sans rien detruire, y compris pour un `mmu extract` lance hors de toute
    TUI -- ce que cette garde-ci n'a jamais pu couvrir.

    **Elle est gardee quand meme, et ce n'est pas une redondance a nettoyer.**
    Deux refus a deux etages, chacun a sa place : celui du coeur protege
    n'importe quel appelant, celui-ci permet a l'ecran de **nommer** le refus
    avant d'engager quoi que ce soit, donc de le dire a l'operateur au lieu de
    relayer une exception. Un futur relecteur qui la croirait morte parce que
    « le coeur refuse de toute facon » referait exactement le raisonnement
    qu'`EPIC11-ARB-83` a interdit -- a la difference pres que, cette fois, le
    coeur tient. C'est la ceinture ; la bretelle est en amont ; on garde les
    deux.
    """
    if lot.etat is None:
        return None
    try:
        validate_lot_state_transition(lot.etat, EXTRACTION_LOT_STATE)
    except ValidationError as erreur:
        return refus_de(LotStateConflictError(erreur.message))
    return None


def refus_de(exception: BaseException) -> RefusDExtraction | None:
    """Traduire une exception du coeur en refus nomme, **par la table du coeur**.

    Rend ``None`` quand la table ne nomme pas l'exception : l'appelant relaie
    alors, il ne fabrique pas un refus. C'est le contrat de
    `extraction.correspondance_de_sortie`, repris tel quel.
    """
    correspondance = extraction.correspondance_de_sortie(exception)
    if correspondance is None:
        return None
    _classe_de_la_table, code_retour = correspondance
    # **Le code nomme la classe LEVEE, pas l'entree de la table qui a repondu.**
    # Les deux different des qu'une exception herite d'une autre --
    # `LotStateConflictError` est attrapee par l'entree
    # `ExtractionPersistenceError` --, et c'est la classe levee qui designe la
    # panne. Le code de sortie, lui, vient de la table et d'elle seule.
    return RefusDExtraction(code=type(exception).__name__,
                            message=str(exception), code_retour=code_retour)


def _octets_du_dossier(dossier: Path) -> int:
    """Le poids **mesure** d'un lot ecrit. Aucun majorant sur l'ecran de resultat.

    **Toute panne de lecture rend zero plutot que de lever** (revue de la
    vague 3, couche 2, `T2`). `is_dir()` repond vrai sur un partage reseau
    demonte ou un volume ejecte, et `iterdir()` leve alors -- une trace Python
    nue devant l'operateur, au moment ou l'ecriture vient de REUSSIR. Le poids
    est un renseignement ; il ne vaut pas de faire tomber l'ecran de resultat.
    L'explorateur porte cette meme garde a ses onze appels systeme.
    """
    try:
        if not dossier.is_dir():
            return 0
        return sum(entree.stat().st_size for entree in dossier.iterdir()
                   if entree.is_file())
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# `E7` (suite) -- l'ecran de resultat et ses suites
# ---------------------------------------------------------------------------

def panneau_du_resultat(rapport: RapportExtraction,
                        ascii_seul: bool = False) -> Panneau:
    """Le cartouche de `E2-5` : un lot par ligne, puis le manifest.

    **Aucun majorant** : `EcranResultat` leve a la construction sur un panneau
    qui en porte un (story 11.1, AC 8.2), et c'est juste -- le travail est fait,
    les chiffres sont mesures.
    """
    complet = jetons.glyphes(ascii_seul)["complete"]
    lignes = [
        LigneChiffree(
            f"{complet} {lot.lot_id}",
            f"{lot.frames} {UNITE} · {lot.texte_de_cadence} · "
            f"{taille_lisible(lot.octets)}")
        for lot in rapport.lots_ecrits
    ]
    if rapport.manifeste is not None and rapport.lots_ecrits:
        lignes.append(LigneChiffree(
            LIBELLE_MANIFESTE,
            f"{rapport.manifeste.parent.name}/{rapport.manifeste.name}"))
    return Panneau(TITRE_ECRIT, lignes)


def suites_du_resultat(rapport: RapportExtraction) -> list[str]:
    """Les suites de `E2-5`, et **chacune mene quelque part**.

    « Composer les planches de ces lots » n'est offerte que si un lot a ete
    ecrit : proposer l'atelier Pdf sur zero lot serait une invite vers un ecran
    qui n'aurait rien a lister. `EcranResultat` ajoute « Retour aux ateliers »
    en dernier de lui-meme (`EPIC11-ARB-13`).

    **La promesse de la premiere ligne a ete FAUSSE du 2026-09-02 au
    2026-09-06**, et il faut le savoir pour ne pas la reintroduire : l'atelier
    Pdf a ete livre (story 11.7) sans que le filet pose en son absence soit
    retire, si bien que la deuxieme des trois suites menait a
    `EcranPasEncore`. Rien ne rougissait -- le filet *fonctionne*, c'est
    l'absence qu'il nomme qui avait cesse d'exister. C'est
    `tests/unit/tui/test_couverture_des_suites.py` qui mesure desormais que
    chaque suite declaree porte une branche nommee.
    """
    suites = [SUITE_DOSSIER, SUITE_PDF] if rapport.lots_ecrits else []
    suites.append(SUITE_AUTRE_RUSH)
    return suites


def dossier_a_ouvrir(rapport: RapportExtraction) -> Path | None:
    """Le dossier que « Ouvrir le dossier des lots » designe, ou ``None``.

    C'est le **parent commun** des dossiers reellement ecrits : donc le dossier
    du lot quand il n'y en a qu'un, et le dossier qui les contient tous des
    qu'il y en a plusieurs. Il n'y a pas de raison d'elire un lot parmi
    plusieurs, et en ouvrir un seul cacherait les autres derriere un libelle qui
    les annonce au pluriel.

    **Les chemins sont ceux que le COEUR a rendus** -- `ExtractionOutcome.
    frames_dir`, recopie tel quel dans `LotEcrit.dossier` par
    :func:`executer_le_plan`. Aucune recomposition : `project_layout.extract_frames_dir`
    rappele ici ouvrirait un dossier que l'extraction n'a peut-etre pas ecrit
    la, et c'est exactement la divergence qu'`EPIC11-ARB-46` interdit -- « l'apercu
    ne peut jamais mentir ».

    ``None`` quand rien n'a ete ecrit.
    """
    dossiers = [str(lot.dossier) for lot in rapport.lots_ecrits]
    if not dossiers:
        return None
    try:
        commun = os.path.commonpath(dossiers)
    except ValueError:
        # Des chemins sans racine commune -- deux volumes sous Windows, un
        # relatif et un absolu. Aucun dossier ne les contient tous ; on ouvre
        # celui du premier lot ecrit, et le fait affiche NOMME le chemin
        # ouvert, si bien que l'operateur voit lequel.
        commun = dossiers[0]
    return Path(commun)


def remonter_a_l_ouverture_de_l_atelier(app) -> None:
    """Depiler jusqu'a la **page d'ouverture** de l'atelier courant.

    Egan, 2026-08-30, sur « Extraire un autre rush » : « ca doit mener a la page
    d'ouverture de l'atelier, c'est-a-dire la liste des rushes ».

    On depile les **passages**, et rien d'autre : `E2-2`, `E2-2b`, `E2-2c`,
    `E2-3`, `E2-4` et `E2-5` portent tous `TRANSITOIRE = True`, tandis que
    `EcranRushes` porte `TRANSITOIRE = False` -- il est le seul ecran de
    l'atelier a n'etre pas un passage. Le premier palier non transitoire
    rencontre est donc `E2-1`, sans que cette fonction ait a connaitre sa
    classe : elle ne l'importe pas, et un atelier futur dont l'ouverture est un
    autre ecran y arrivera par la meme regle.

    **On ne remonte pas plus haut.** `EPIC11-ARB-13`, verbatim : « La fin d'une
    execution ramene au **menu des ateliers du projet ouvert** [...], jamais a
    l'ecran projet. » Cette suite-ci s'arrete un cran EN DESSOUS du menu, dans
    l'atelier ou l'operateur travaille -- c'est le retour, et lui seul, qui
    remonte au menu.

    `EcranRushes.reprendre` relit le manifeste quand il redevient le sommet :
    le lot qui vient d'etre ecrit est donc dans la liste retrouvee, jamais
    l'etat d'avant l'ecriture.
    """
    while app.passages_empiles and len(app.screen_stack) > 1:
        app.pop_screen()


def ligne_d_etat_du_resultat(rapport: RapportExtraction,
                             ascii_seul: bool = False) -> str:
    """Une **mesure**, jamais un nom de touche ni un conseil (`EPIC11-ARB-56`)."""
    lots = len(rapport.lots_ecrits)
    mot = "lot écrit" if lots == 1 else "lots écrits"
    refus = "aucun refus" if rapport.refus is None else rapport.refus.code
    # **Le repli ASCII precede la mesure**, et il porte sur le libelle autant
    # que sur le glyphe : `jetons.marque` ne replie que le second, et « lots
    # écrits » sortait donc accentue en `--ascii`.
    libelle = f"{lots} {mot}, {rapport.frames_ecrites} {UNITE}, {refus}"
    if ascii_seul:
        libelle = jetons.replier_ascii(libelle)
    return jetons.marque("complete" if rapport.refus is None else "absent",
                         libelle, ascii_seul)


def ouvrir_le_resultat(app, rapport: RapportExtraction, *,
                       sur_suite: Callable[[str], None] | None = None,
                       journal=None, objet: str = "") -> EcranResultat:
    """Monter `E2-5` sur les chiffres mesures, avec ses suites navigables.

    **`sur_suite` est ce qui rend les suites autre chose qu'un decor.** Sans
    lui, `EcranResultat.choisir` mene TOUTE suite autre que le retour a l'ecran
    « pas encore » : c'est l'etat qu'Egan a rencontre le 2026-08-30 -- « quatre
    suites sont proposees, une seule marche » --, et il ne venait pas de
    l'ecran mais du POINT D'APPEL, qui ne passait pas le rappel. Le mot-cle
    garde son defaut pour les bancs d'ecran ; c'est
    :func:`executer_et_conclure`, seul chemin du produit vers cet ecran, qui le
    passe, et le banc `test_suites_du_resultat.py` mesure qu'il le passe.

    ``journal`` est celui de l'execution qui vient de finir. Sans lui, `E2-5`
    n'annonce pas `Tab journal` et ne le traite pas : sa ligne de raccourcis est
    contextuelle (finding `I8` du lot I -- la maquette annoncait cette touche
    depuis toujours et l'ecran ne la traitait pas, si bien que le journal d'une
    extraction terminee n'etait relisible de nulle part).
    """
    ecran = EcranResultat(
        panneau_du_resultat(rapport, getattr(app, "ascii_seul", False)),
        suites_du_resultat(rapport), sur_suite=sur_suite, journal=journal,
        objet=objet)
    app.descendre(ecran)
    ecran.poser_etat(ligne_d_etat_du_resultat(
        rapport, getattr(app, "ascii_seul", False)))
    return ecran


def ouvrir_le_refus(app, refus: RefusDExtraction, rapport: RapportExtraction
                    ) -> EcranRefus:
    """Monter l'ecran de refus. Le message du coeur y voyage **verbatim**.

    Ce que le refus a **conserve** et ce qu'il n'a **pas ecrit** sont dits
    separement, parce que c'est la premiere question devant un refus au milieu
    d'une serie : ce qui precede est-il perdu ?
    """
    ecran = EcranRefus(
        code=f"{refus.code} (code de sortie {refus.code_retour})",
        message=refus.message,
        conserve=[lot.lot_id for lot in rapport.lots_ecrits],
        non_ecrit=[])
    app.descendre(ecran)
    return ecran


# ---------------------------------------------------------------------------
# `E7` (suite) -- l'ecran d'execution, et l'enchainement complet
# ---------------------------------------------------------------------------

def titre_de_la_tache(plan: PlanExtraction) -> str:
    """L'entete de `E2-4` : ce qui tourne, et combien il y en a."""
    if len(plan.lots) == 1:
        return f"Extraction de {plan.rush_id}"
    return f"Extraction de {plan.rush_id} — {len(plan.lots)} lots"


#: Le nom du journal du produit. Un nom PROPRE, jamais le racine: un handler
#: pose sur le racine capterait aussi les lignes des bibliotheques tierces, et
#: le journal de `E2-4` montrerait du bruit que l'operateur ne peut pas lire.
NOM_DU_JOURNAL = "mixed_media_utility.tui.extraction"


class RelaisDeJournal(logging.Handler):
    """Ce qui fait arriver les lignes du coeur dans le journal de `E2-4`.

    **Deux pannes en une, trouvees le 2026-08-30 en CAPTURANT les douze ecrans
    de l'atelier, et par aucun banc** (lot `H1`) :

    1. `extraction.run_extraction` declare `logger` en mot-cle **sans defaut**
       et le dereference sans garde des sa premiere ligne utile
       (`extraction.py:853`, `logger.info(...)`). Or le rappel que le produit
       injecte -- `ChaineReelle.extraire`, qui appelle
       `self._ouvrir_les_cadences(self.app, self.menu.dossier, rush_id)` --
       n'en passe aucun, et `ParcoursExtraction` le laissait a `None`. **Toute**
       extraction lancee depuis `mmu-tui` tombait donc sur
       `AttributeError: 'NoneType' object has no attribute 'info'`. Aucun banc
       ne pouvait le voir : ils passent tous un logger, parce que c'est ce
       qu'on fait quand on ecrit un banc.
    2. Meme sans le plantage, **le journal de `E2-4` n'etait alimente par
       rien** : `SurfaceExecution.noter` n'y inscrit que l'avancement chiffre.
       Les lignes que la maquette y montre -- la qualification de la source, le
       compte de frames retenues, le manifest mis a jour -- sont des `logger.info`
       du coeur, et elles n'avaient nulle part ou aller.

    Le correctif est **structurel**, comme celui du lot `A` sur les raccourcis
    de saisie : le journal ne se construit pas au point d'appel, il se
    construit dans :class:`ParcoursExtraction` **des que l'appelant n'en donne
    pas**. Un futur appelant ne peut donc pas rouvrir le trou en oubliant un
    mot-cle -- ce qui est exactement ce qui vient d'arriver.

    Le relais vise `None` tant que `E2-4` n'est pas monte : le plan est prepare
    et juge avant que l'ecran d'execution n'existe, et les lignes de cette
    phase-la n'ont pas de journal ou aller. Elles sont **jetees**, pas mises en
    attente : un journal qui deverserait d'un coup la phase precedente au
    montage de l'ecran montrerait a l'operateur un passe qu'il n'a pas demande.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.setFormatter(logging.Formatter("%(message)s"))
        self._journal = None

    def viser(self, journal) -> None:
        """Brancher le relais sur le journal de l'ecran qui vient d'etre monte."""
        self._journal = journal

    def emit(self, record: logging.LogRecord) -> None:
        journal = self._journal
        if journal is None:
            return
        # `logging` veut qu'un handler n'explose jamais: une ligne de journal
        # ratee ne doit pas faire tomber l'extraction qu'elle raconte.
        try:
            journal.inscrire(self.format(record))
        except Exception:   # noqa: BLE001 -- contrat de `logging.Handler`
            self.handleError(record)


def journal_du_produit() -> tuple[logging.Logger, RelaisDeJournal]:
    """Le logger que le produit passe au coeur, et son relais vers `E2-4`.

    `propagate` est coupe : sous une TUI, tout handler herite du racine ecrit
    sur `stdout` **par-dessus l'interface**, qui est un plein ecran.
    """
    logger = logging.getLogger(NOM_DU_JOURNAL)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    relais = RelaisDeJournal()
    # Le logger est un singleton par nom: deux parcours successifs dans la meme
    # session reutiliseraient le meme objet, et les relais s'empileraient --
    # chaque ligne serait inscrite autant de fois qu'il y a eu d'extractions.
    for ancien in list(logger.handlers):
        if isinstance(ancien, RelaisDeJournal):
            logger.removeHandler(ancien)
    logger.addHandler(relais)
    return logger, relais


def ouvrir_l_execution(app, plan: PlanExtraction, *,
                       objet: str = "") -> EcranExecution:
    """Monter `E2-4` **avant** d'appeler le coeur.

    L'ordre n'est pas cosmetique : `EcranExecution.on_mount` est ce qui abonne
    l'ecran aux jalons de la surface. Appeler le coeur d'abord ferait ecrire les
    jalons dans une surface que personne n'ecoute encore, et la barre partirait
    de la fin.
    """
    surface = SurfaceExecution(unite=UNITE)
    ecran = EcranExecution(surface, titre_tache=titre_de_la_tache(plan),
                           sur_issue=lambda issue: _interrompre(app, issue),
                           objet=objet)
    app.descendre(ecran)
    return ecran


def _interrompre(app, issue: Issue) -> None:
    """Les deux issues qui arretent la tache. « Reprendre » ne vient jamais ici.

    L'interruption est **demandee** ; elle est constatee entre deux lots par
    :func:`executer_le_plan`. Voir son docstring : le coeur n'offre aucun point
    d'arret a l'interieur d'un lot.
    """
    app.interruption_demandee = True


def executer_et_conclure(app, ecran: EcranExecution, plan: PlanExtraction, *,
                         logger, extraire: Callable[..., Any] | None = None,
                         sur_suite: Callable[[str], None] | None = None
                         ) -> RapportExtraction:
    """Lancer la serie, puis monter le resultat ou le refus. **Synchrone.**

    Un seul chemin pour les deux issues : c'est ce qui garantit que
    `oublier_la_tache` est appele dans tous les cas -- un drapeau
    `tache_en_cours` reste a vrai ferait de `Echap` une interruption bien apres
    la fin (defaut de couture ferme par la revue de vague 1, couche 2).

    **Elle reste synchrone, et le produit ne passe plus par elle.** Depuis le
    2026-09-06, `ParcoursExtraction._ecrire` appelle :func:`lancer_l_extraction`,
    qui fait le meme travail **au fil**. Celle-ci demeure pour les appelants qui
    veulent le rapport tout de suite -- les bancs, au premier chef --, et parce
    qu'elle est le seul endroit ou l'ordre « coeur puis conclusion » se lit
    d'une traite.
    """
    rapport = executer_le_plan(
        plan, ecran.surface, logger=logger,
        hote=app.executer_en_processus,
        interrompu=lambda: bool(app.interruption_demandee),
        extraire=extraire)
    return conclure_l_extraction(app, ecran, rapport, sur_suite=sur_suite)


def conclure_l_extraction(app, ecran: EcranExecution,
                          rapport: RapportExtraction, *,
                          sur_suite: Callable[[str], None] | None = None
                          ) -> RapportExtraction:
    """Les deux conclusions, **et rien d'autre**. Appelee DEPUIS LA BOUCLE.

    Extraite d':func:`executer_et_conclure` sans changer une ligne de son
    corps, pour une seule raison -- la meme que
    `atelier_scan_detection.conclure_la_detection` : elle **touche l'arbre de
    widgets**. Elle eteint le drapeau de tache, elle empile `E2-5` ou l'ecran
    de refus. Muter l'arbre depuis un fil de travail est un defaut plus grave
    que le gel qu'on repare : `textual` ne le signale pas, l'ecran se met a
    jour la plupart du temps, et ce qui casse casse au hasard.

    :func:`lancer_l_extraction` la rappelle donc par `call_from_thread` ;
    :func:`executer_et_conclure`, qui reste synchrone, l'appelle directement.

    **`E2-4` est RETIRE ici, et il ne l'etait pas** (corrige le 2026-09-07, sur
    finding `C2` de la couche 2 de la revue du lot des ecrans vivants). Le
    commentaire de la branche nominale, quelques lignes plus bas, affirmait
    depuis le debut qu'« `E2-4` est depile au moment ou le resultat monte » --
    et personne ne le depilait. Pile mesuree ::

        [..., EcranExecution, EcranResultat]

    `Echap` depuis `E2-5` retombait donc sur l'ecran d'execution d'une tache
    finie, dont l'`on_key` intercepte l'echappement : c'est le jumeau exact du
    cul-de-sac d'encode qu'Egan a rencontre cote exports.

    **Ce lot rend le trou ATTEIGNABLE alors qu'il preexistait.** L'empilement
    sous `E2-5` datait d'avant ; ce qui est neuf, c'est que la boucle
    d'evenements vit desormais pendant la passe, donc `Echap` et `F1` sont
    atteignables et peuvent poser un ecran tiers par-dessus `E2-4`. C'est
    pourquoi le retrait passe par `CoqueTui.retirer_l_ecran`, qui retire par
    identite **ou que soit** l'ecran, et non par un depilement conditionne sur
    le sommet -- la premiere version du correctif d'exports avait fait ce
    choix-la, et la revue a mesure qu'elle ne fermait rien.
    """
    app.oublier_la_tache()
    retirer = getattr(app, "retirer_l_ecran", None)
    if retirer is not None:
        retirer(ecran)
    if rapport.refus is not None:
        ouvrir_le_refus(app, rapport.refus, rapport)
    else:
        # **Le journal traverse jusqu'a `E2-5`.** C'est le seul endroit du
        # produit ou les deux se touchent : `E2-4` est depile au moment ou le
        # resultat monte, et son journal disparaitrait avec lui.
        # **L'objet traverse jusqu'a `E2-5`**, comme le journal, et il est
        # LU SUR L'ECRAN D'EXECUTION plutot que repasse en argument : c'est le
        # meme rush qu'on vient d'extraire, l'ecran qui l'a affiche pendant
        # toute la tache le porte deja, et un second argument qui dirait la
        # meme chose pourrait dire autre chose.
        # **Le rappel des suites traverse aussi**, et c'est le defaut que le
        # lot `K3` ferme : ce point d'appel etait le SEUL du produit vers
        # `E2-5`, et il ne passait pas `sur_suite`. Les quatre suites etaient
        # donc navigables au clavier et ne menaient nulle part -- meme mode de
        # panne que le lot `E9` et que le finding `I3` : un composant livre,
        # teste, et cable nulle part. Le `| None = None` de la signature le
        # rendait SILENCIEUX.
        ouvrir_le_resultat(app, rapport, sur_suite=sur_suite,
                           journal=ecran.surface.journal,
                           objet=ecran.objet)
    return rapport


# ---------------------------------------------------------------------------
# Le PARCOURS reel : de « quel rush » a « ecrit »
#
# Les deux moities de l'atelier existaient et ne se touchaient pas. Les ecrans
# amont vivent dans `atelier_extraction.py` (`E2-1`, `E2-2`, `E2-2b`, `E2-2c`),
# le jugement, l'execution et le resultat vivent ici (`E2-3`, `E2-4`, `E2-5`).
# Ce qui suit est le **raccord**, et rien d'autre : aucun ecran neuf, aucun
# modele neuf, aucune seconde redaction d'une convention du coeur.
# ---------------------------------------------------------------------------

#: Ce que le refus d'un rush delinke NOMME comme demandeur du fichier source.
#: `relink.refus_necessite_le_rush` compose son message avec ce mot, et le mot
#: designe ici l'**atelier**, pas une commande de terminal : une TUI qui dirait
#: le nom d'une sous-commande enverrait l'operateur vers une ligne de commande
#: qu'il n'a pas ouverte. Le message du coeur, lui, voyage verbatim (AC 4.3) --
#: seul le sujet de sa phrase est nomme par l'appelant, comme la signature du
#: coeur le prevoit.
DEMANDEUR_DU_FICHIER_SOURCE = "L'atelier Extraction"


@dataclass(frozen=True)
class SourceProbee:
    """Ce qu'UN sondage rend, et qui suffit a tout le reste du parcours.

    Trois choses, payees ensemble et jamais deux fois :

    * `source` -- la :class:`~mixed_media_utility.tui.atelier_extraction.SourceSondee`
      que le modele des cadences consomme. `EPIC11-ARB-79` : le compte de
      frames vient de `frame_selection.select_source_frames`, appele avec la
      `Fraction` exacte et ce cardinal-la, **jamais** par `prepare_previz` --
      dont le filtre d'entrees refuse une `Fraction`, et dont la conversion en
      flottant reintroduirait l'approximation que le modele garde exacte ;
    * `probe` -- le dictionnaire ffprobe **brut**. C'est lui qu'on repasse a
      `prepare_previz`, qui ne resonde alors pas : « Le probe reste paye une
      seule fois : c'est son resultat qu'on repasse » ;
    * la resolution, lue du meme probe, d'ou sort le majorant d'espace disque.
    """

    source: "SourceSondee"
    probe: dict[str, Any]
    largeur: int | None = None
    hauteur: int | None = None

    @property
    def octets_par_frame(self) -> int | None:
        """Le poids majorant d'une frame ecrite, **par la formule du coeur**.

        Elle passe par :func:`octets_par_frame`, qui lit les canaux et la
        profondeur de `source_confirmation` et d'`extraction_manifest`. Aucune
        seconde formule : le majorant annonce par `E2-2c` et celui que le
        rapport de confirmation du coeur imprime sont le meme chiffre.
        """
        return octets_par_frame(self.largeur, self.hauteur)


def chemin_du_rush(dossier_projet: Path | str, rush_id: str) -> Path | None:
    """Le fichier source du rush vise, **apparie par `rush_id`**, ou ``None``.

    Jamais par position : `rushes[]` porte l'ordre de premiere extraction, et
    un appariement positionnel sonderait le fichier d'un **autre** rush -- le
    mutant `M25` de la story 5.7, dont la consequence reelle etait d'ecrire les
    cardinaux sur le mauvais lot.

    **Le diagnostic de liaison est celui du coeur** (`relink.statut_de_liaison`,
    la meme fonction que la liste `E2-1` consulte, AC 2.2) : deux diagnostics
    divergeraient, et l'ecran proposerait alors d'extraire un rush que le
    sondage refuse. La lecture du document passe par `projet_lecture`, qui fait
    foi (AC 2.5) et ne leve jamais.
    """
    from .. import relink

    manifeste = projet_lecture.lire_manifeste(Path(dossier_projet)) or {}
    entrees = manifeste.get("rushes")
    if not isinstance(entrees, list):
        return None
    for entree in entrees:
        if not isinstance(entree, dict) or entree.get("rush_id") != rush_id:
            continue
        if relink.statut_de_liaison(entree) != relink.LIE:
            return None
        return Path(entree["source_path"])
    return None


def sonder_la_source(video_path: Path | str, *, ffprobe_binaire: str = "ffprobe",
                     logger: Any = None) -> SourceProbee:
    """Sonder le rush UNE FOIS, par le chemin de probe du depot et lui seul.

    L'ordre est celui de `relink.probe_reel` et d'`extract`, repris tel quel :
    `video_metadata.probe_media` -> `extraction.qualify_source` ->
    `extraction.resolve_source_frame_count`. Aucun second chemin de sondage
    n'est ecrit ici -- `extraction.py` l'interdit deja explicitement (« Il ne
    derive jamais le cardinal source d'une duree: il l'exige »), et une seconde
    porte divergerait de la premiere sur ce qu'elle sait refuser.

    **Ce que cette fonction ajoute a `relink.probe_reel`**, et qui est sa
    seule raison d'exister : elle **garde le probe brut** et la resolution.
    `ProbeCandidat` ne porte ni l'un ni l'autre -- il n'en a pas besoin pour
    juger une identite --, or le parcours en a besoin des deux : le probe pour
    que `prepare_previz` ne resonde pas, la resolution pour le majorant.

    La resolution se lit par l'accesseur **du coeur**
    (`video_metadata._video_stream`), celui-la meme que `source_confirmation`
    emploie pour le majorant : un second choix de flux video pourrait designer
    un autre flux que celui que le coeur mesure.
    """
    from .. import video_metadata
    from ..source_confirmation import _coerce_positive_int as _entier_du_coeur
    from .atelier_extraction import SourceSondee

    chemin = Path(video_path)
    probe = video_metadata.probe_media(str(chemin), ffprobe_bin=ffprobe_binaire)
    qualification = extraction.qualify_source(probe)
    cardinal, exact = extraction.resolve_source_frame_count(
        chemin, qualification, ffprobe_bin=ffprobe_binaire, logger=logger)
    flux = video_metadata._video_stream(probe)
    return SourceProbee(
        source=SourceSondee(
            video_path=chemin,
            fps_source=qualification.fps_source,
            source_frame_count=cardinal,
            source_frame_count_is_exact=exact,
            source_start_timecode=qualification.start_timecode),
        probe=probe,
        largeur=_entier_du_coeur(flux.get("width")),
        hauteur=_entier_du_coeur(flux.get("height")))


def jouer_les_cadences(session, *, logger: Any = None):
    """La lecture comparee, sur la **fenetre reelle** et sur elle seule.

    `EPIC11-ARB-41`, verbatim : « L'absence d'affichage doit etre **detectee
    avant** de lancer quoi que ce soit [...] Un refus qui arrive apres coup
    vaut un plantage. » La detection est faite par les ecrans, au montage
    (`EcranCadences.demarrer` et `EcranPreviz.demarrer`) ; cette fonction n'est
    donc atteinte que sur un affichage disponible, et elle n'a aucune variante
    degradee a proposer -- « on ne degrade pas une promesse, on la retire
    quand elle ne peut pas etre tenue ».
    """
    from .. import cadence_previz

    return cadence_previz.play_cadences(
        session, sink=cadence_previz.CvWindowSink(), logger=logger)


def _lancer_apres_le_dessin(app, action: Callable[[], None]) -> None:
    """Laisser l'ecran d'execution se MONTER avant d'appeler le coeur.

    **Mesure du 2026-08-30, dans le banc** : `app.descendre(ecran)` empile
    l'ecran, mais son `on_mount` n'a pas encore tourne a l'instruction
    suivante -- `len(surface._observateurs)` vaut alors `0` et
    `app.tache_en_cours` vaut `False`. Appeler le coeur dans la foulee ferait
    donc deux choses fausses a la fois : les jalons tomberaient dans une
    surface que **personne n'ecoute** -- la barre resterait figee du debut a la
    fin de l'extraction, exactement le defaut que `SurfaceExecution.abonner`
    existe pour fermer --, et `Echap` depilerait l'ecran d'une tache qui tourne
    au lieu d'ouvrir l'interruption.

    `call_after_refresh` est le rendez-vous que `textual` offre pour cela : la
    meme mesure rend alors un observateur et `tache_en_cours` a vrai. Le repli
    direct existe pour les appelants qui ne montent aucune application -- ils
    n'ont pas d'ecran a laisser se monter.
    """
    differer = getattr(app, "call_after_refresh", None)
    if differer is None:
        action()
        return
    differer(action)


#: Le nom de l'ouvrier `textual` de la passe d'extraction. Nomme plutot
#: qu'anonyme : c'est ce qui distingue cette course des autres dans la liste
#: des `workers` de l'application -- et c'est par ce nom qu'un banc verifie
#: qu'elle est bien partie, sans avoir a deviner laquelle.
OUVRIER_DE_L_EXTRACTION = "extraction-ecrire"


def lancer_l_extraction(app, ecran: EcranExecution, plan: PlanExtraction, *,
                        logger, extraire: Callable[..., Any] | None = None,
                        sur_suite: Callable[[str], None] | None = None,
                        sur_rapport: Callable[["RapportExtraction"], None]
                        | None = None) -> None:
    """La passe **dans un fil de travail**, pour que `E2-4` vive pendant.

    **Ce que cette fonction ferme, et Egan l'a constate en utilisant le
    produit** (2026-09-06) : « La barre de progression saute de 0 a 100. Pas eu
    l'impression de voir les frames progresser. Je ne suis pas sur que le coeur
    sache le faire ? » Le coeur sait, et tres finement :
    `ffmpeg_utils.run_with_written_file_progress` scrute le repertoire
    temporaire toutes les 0,25 s et emet un jalon a chaque passage. Sur 6 300
    frames, ce sont des centaines de jalons -- tous emis, tous recus par la
    surface, et **aucun peint**.

    **Le rendez-vous de dessin ne suffisait pas, et c'est la mesure du jour.**
    `call_after_refresh` differe d'une image : il fait apparaitre `E2-4` **une
    fois**, puis rend la boucle a un appel synchrone qui la garde jusqu'a la
    derniere frame. `textual` peignant depuis cette boucle, l'ecran affiche
    `0 %  0/6300` et ne bouge plus -- ce qui, vu de l'operateur, est
    indiscernable d'un coeur muet. Le fil est la seule forme qui garde la
    boucle vivante **pendant** la passe.

    **Le drapeau se pose ICI, avant le fil, et pas dans le fil.** Entre le
    `run_worker` et la premiere ligne du fil, la boucle tourne : un `Echap` qui
    y tomberait depilerait `E2-4` sous la passe. Meme geste, meme motif que
    `atelier_scan_detection.lancer_la_detection`.

    **Le fil ne part qu'APRES le dessin**, et le rendez-vous ne le remplace
    pas : `EcranExecution.on_mount` est ce qui abonne l'ecran aux jalons de la
    surface **et** rallume `tache_en_cours`. Un fil parti avant ce montage
    ecrirait ses premiers jalons dans une surface que personne n'ecoute, et
    pourrait eteindre le drapeau avant qu'`on_mount` le rallume -- l'atelier
    reste alors mort pour la session sur une panne.

    Ne rend **rien** : le rapport n'existe pas encore quand cette fonction rend
    la main, et c'est exactement ce qui change. Il arrive par `sur_rapport`,
    appele sur la boucle.
    """
    app.tache_en_cours = True

    def conclure(rapport: RapportExtraction) -> RapportExtraction:
        # **Un seul passage par la boucle pour les deux gestes.** Retenir le
        # rapport puis conclure dans deux `call_from_thread` distincts
        # laisserait la boucle libre entre les deux, avec `tache_en_cours`
        # deja eteint par la conclusion et le rapport pas encore pose.
        if sur_rapport is not None:
            sur_rapport(rapport)
        return conclure_l_extraction(app, ecran, rapport, sur_suite=sur_suite)

    def passe() -> None:
        try:
            rapport = executer_le_plan(
                plan, ecran.surface, logger=logger,
                hote=app.executer_en_processus,
                interrompu=lambda: bool(app.interruption_demandee),
                extraire=extraire)
        except BaseException:
            # Le coeur a leve : le drapeau tombe **ici**, puisque
            # `conclure_l_extraction` ne sera pas atteinte. C'est la moitie du
            # `finally` d'origine qui reste necessaire, et l'exception
            # continue son chemin -- elle n'est pas avalee.
            app.call_from_thread(app.oublier_la_tache)
            raise
        app.call_from_thread(conclure, rapport)

    _lancer_apres_le_dessin(app, lambda: app.run_worker(
        passe, thread=True, name=OUVRIER_DE_L_EXTRACTION,
        description="extraire les lots d'un rush"))


class ParcoursExtraction:
    """Les cinq paliers de l'atelier, cables les uns aux autres.

    `EPIC11-ARB-28`, verbatim : « **Extraction et Exports n'en ont pas** : une
    seule entree chacun, donc le menu serait un ecran a franchir pour rien. »
    Aucun ecran ne s'intercale entre le menu des ateliers et `E2-1`, et aucun
    entre les paliers de ce parcours : chaque etape en ouvre exactement une
    autre.

    Le cablage vit dans une **classe** et non dans une fonction a fermetures
    pour la meme raison que :class:`ChaineReelle` : chaque rappel a besoin de
    ce que le precedent a produit -- la source sondee, les cadences regardees,
    le resultat de la previz --, et les methodes liees le portent sans rendre
    l'etat implicite.

    **Ce que ce parcours ne fait jamais**, et qui est la moitie de son contrat :

    * il ne recalcule aucun compte de frames (`EPIC11-ARB-79`) ;
    * il ne recompose aucun nom de lot -- `build_lot_id` est appele des deux
      cotes, au temps 2 pour montrer et au plan pour ecrire, si bien que
      l'apercu ne peut pas mentir (`EPIC11-ARB-46`) ;
    * il ne resonde jamais la source ;
    * il ne fait rien ecrire avant le point de jugement.
    """

    def __init__(self, app, dossier_projet: Path | str, rush_id: str, *,
                 borne_d_entree: str | None = None,
                 borne_de_sortie: str | None = None,
                 sonder: Callable[..., SourceProbee] | None = None,
                 preparer_la_previz: Callable[..., Any] | None = None,
                 jouer: Callable[..., Any] | None = None,
                 extraire: Callable[..., Any] | None = None,
                 verifier_l_affichage: Callable[[], None] | None = None,
                 composer_les_planches: Callable[..., Any] | None = None,
                 logger: Any = None) -> None:
        from .. import cadence_previz

        self.app = app
        self.dossier_projet = Path(dossier_projet)
        self.rush_id = rush_id
        self.borne_d_entree = borne_d_entree
        self.borne_de_sortie = borne_de_sortie
        self._sonder = sonder or sonder_la_source
        self._preparer_la_previz = (preparer_la_previz
                                    or cadence_previz.prepare_previz)
        self._jouer = jouer or jouer_les_cadences
        self._extraire = extraire
        self._verifier_l_affichage = verifier_l_affichage
        #: L'ouverture de l'atelier Pdf sur sa liste de lots, pour la suite
        #: « Composer les planches de ces lots ». **Le defaut est le VRAI point
        #: d'entree** (`atelier_pdf.ouvrir_la_composition_des_planches`),
        #: resolu a l'appel : c'est le double qui est l'exception, jamais le
        #: defaut. Le resoudre ici plutot que dans `ChaineReelle` evite de
        #: faire traverser un second rappel Pdf a `ouvrir_les_cadences`, dont
        #: la signature est celle que `ChaineReelle.extraire` appelle.
        self._composer_les_planches = composer_les_planches
        # **Jamais `None`** : voir `RelaisDeJournal`. Le coeur declare `logger`
        # obligatoire et le dereference sans garde ; c'est ici, et pas au point
        # d'appel, que le produit s'en dote -- sinon un appelant qui oublie le
        # mot-cle fait tomber toute extraction.
        if logger is None:
            self._logger, self._relais_de_journal = journal_du_produit()
        else:
            self._logger, self._relais_de_journal = logger, None
        #: Ce que le sondage a rendu. Pose une fois, relu partout.
        self.sondee: SourceProbee | None = None
        #: Les cadences que le temps 1 a envoyees regarder.
        self.regardees: tuple = ()
        #: Ce que la derniere execution a produit. Pose par :meth:`_conclure`,
        #: relu par :meth:`suivre` -- les suites de `E2-5` sont choisies APRES
        #: que l'execution a rendu son rapport, jamais pendant.
        self.rapport: RapportExtraction | None = None

    # -- les deux bornes, passees a l'IDENTIQUE aux quatre appels du coeur ----

    @property
    def _bornes(self) -> dict[str, str | None]:
        """La fenetre, sous la forme que le coeur nomme.

        Un seul dictionnaire pour `select_source_frames`, `prepare_previz`,
        `build_lot_id` et `preparer_le_plan` : ecrire les deux bornes quatre
        fois ferait diverger le nom du lot de la selection qu'il contient au
        premier oubli, et le suffixe de bornes est justement ce qui distingue
        deux extraits du meme rush a la meme cadence.
        """
        return {"source_in_timecode": self.borne_d_entree,
                "source_out_timecode": self.borne_de_sortie}

    # -- etape 1 : le rush choisi -> `E2-2` ----------------------------------

    def ouvrir(self):
        """Sonder la source **une fois**, puis monter `E2-2`.

        Le sondage est long -- il paie `ffprobe`, et parfois un decodage
        complet. Il passe donc par `CoqueTui.executer_en_processus`, la
        frontiere qui **nomme** l'appel du coeur (`EPIC11-ARB-1` : « le coeur
        est heberge, pas relance »), jamais dans la boucle d'evenements sans
        le dire.

        Un rush delinke n'est pas sonde du tout : le refus vient du coeur, avec
        son code, et l'ecran de refus du relink porte les trois suites qui
        menent a la reparation.
        """
        from .atelier_extraction import EcranCadences

        chemin = chemin_du_rush(self.dossier_projet, self.rush_id)
        if chemin is None:
            return self._refuser_le_rush_delinke()
        try:
            self.sondee = self.app.executer_en_processus(
                self._sonder, chemin, logger=self._logger)
        except BaseException as exception:   # noqa: BLE001 -- voir _refuser
            return self._refuser(exception)
        ecran = EcranCadences(
            self.sondee.source,
            borne_d_entree=self.borne_d_entree,
            borne_de_sortie=self.borne_de_sortie,
            previsualiser=self.previsualiser,
            extraire=self.extraire_sans_voir,
            **self._affichage())
        self.app.descendre(ecran)
        return ecran

    def _affichage(self) -> dict[str, Any]:
        """La garde d'affichage, laissee au coeur sauf si l'appelant en donne une.

        Absente, `EcranCadences` et `EcranPreviz` appellent tous deux
        `cadence_previz.ensure_display_available` : c'est la garde reelle, et
        la remplacer par un defaut local en ferait une seconde.
        """
        if self._verifier_l_affichage is None:
            return {}
        return {"verifier_l_affichage": self._verifier_l_affichage}

    # -- etape 2 : `⏎` -> `E2-2b` --------------------------------------------

    def previsualiser(self, validation):
        """La lecture comparee des cadences cochees, **sur le probe deja paye**.

        `prepare_previz` accepte le probe en argument et ne resonde alors pas.
        Le lui cacher couterait un second `ffprobe` -- « le poste le plus cher
        de la preparation sur un rush long » -- pour un resultat identique.

        Ce que la previz produit n'autorise rien : voir :meth:`confirmer`.
        """
        from .atelier_extraction import EcranPreviz

        self.regardees = tuple(validation.cochees)
        try:
            session = self.app.executer_en_processus(
                self._preparer_la_previz,
                video_path=self.sondee.source.video_path,
                fps_targets=[float(cadence.valeur)
                             for cadence in self.regardees],
                probe=self.sondee.probe,
                logger=self._logger,
                **self._bornes)
        except BaseException as exception:   # noqa: BLE001 -- voir _refuser
            return self._refuser(exception)
        ecran = EcranPreviz(self.regardees, session, jouer=self._jouer,
                            choisir=self.choisir, **self._affichage())
        self.app.descendre(ecran)
        return ecran

    # -- etape 3 : `x` -> DROIT au point de jugement -------------------------

    def extraire_sans_voir(self, validation):
        """AC 5.1 : « `x` extrait sans previz. »

        Aucun ecran de lecture comparee ne s'intercale -- « Un operateur qui
        refait tous les jours la meme cadence n'a rien a regarder, et lui
        imposer une lecture serait remplacer une syntaxe obscure par une
        ceremonie » (`EPIC11-ARB-24`). Le point de jugement, lui, n'est pas
        saute : c'est le seul ecran que rien ne contourne.
        """
        return self._juger([(cadence.valeur, cadence.compte)
                            for cadence in validation.cochees])

    # -- etape 4 : `⏎` sur `E2-2b` -> `E2-2c` --------------------------------

    def choisir(self, resultat):
        """Le temps 2 : lesquelles extraire, parmi celles qu'on a regardees.

        `EPIC11-ARB-24`, verbatim : « une previz n'autorise rien » -- « elle ne
        cree ni lot, ni entree de manifest, ni consentement reutilisable ». La
        liste arrive donc entierement decochee, et c'est `EcranChoixDesCadences`
        qui le garantit.

        Le majorant d'espace disque est **donne** ici : l'ecran ne l'affiche
        pas autrement, et la maquette `E2-2c` le porte.
        """
        from .atelier_extraction import EcranChoixDesCadences

        ecran = EcranChoixDesCadences(
            self.regardees, resultat,
            nommer=self.nommer,
            confirmer=self.confirmer,
            rejouer=self._jouer,
            octets_par_frame=self.sondee.octets_par_frame)
        self.app.descendre(ecran)
        return ecran

    def nommer(self, cadence) -> str:
        """Le nom du lot que cette cadence produira, **par `build_lot_id`**.

        La meme fonction, avec les memes arguments, que celle que
        :func:`preparer_le_plan` appellera pour le plan et que
        `run_extraction` appellera pour ecrire. C'est ce qui rend impossible
        qu'`E2-2c` annonce un nom et que le disque en porte un autre
        (`EPIC11-ARB-46`, verbatim : « l'apercu ne peut jamais mentir »).
        """
        return build_lot_id(self.rush_id, float(cadence.valeur), **self._bornes)

    # -- etape 5 : `⏎` sur `E2-2c` -> `E2-3`, puis `E2-4` et `E2-5` ----------

    def confirmer(self, lots) -> Any:
        """`EPIC11-ARB-24`, verbatim : « **Le temps 2 repasse donc par le
        panneau de confirmation** ; il ne herite d'aucun consentement du temps
        1. »

        Rien n'est ecrit ici, et rien ne peut l'etre : cette methode monte le
        point de jugement, dont la seule issue qui porte `ecrit=True` appelle
        :meth:`_ecrire`.
        """
        # **Chaque lot porte SA cadence et SON compte**, lus sur le meme objet.
        # Un appariement decale d'un rang inverserait deux lots aux comptes
        # differents, et rien ne le dirait avant les TIFF.
        return self._juger([(lot.cadence, lot.compte) for lot in lots])

    @property
    def objet_du_bandeau(self) -> str:
        """`rush_01 · 25 fps · 4:12` -- la droite du bandeau des cinq ecrans
        aval (`E2-3`, `E2-3b`, `E2-3c`, `E2-4`, `E2-5`).

        **Le defaut qu'elle ferme** (`J3`, 2026-08-30, vu sur les captures
        `20-` a `24-`) : les cinq maquettes portent cet objet, et les cinq
        ecrans rendaient un bandeau nu. Les sept autres ecrans de l'atelier
        l'avaient recu au lot `I` ; ces cinq-la vivent dans `execution.py`,
        partage par les quatre ateliers, donc hors du perimetre de ce lot-la.

        **Rien n'est resonde et rien n'est recalcule.** Les deux mesures
        viennent de `self.sondee`, paye une seule fois a l'ouverture, et leur
        mise en forme est celle de `rushes.bandeau_du_rush` -- donc les memes
        fonctions que la colonne technique de `E2-1`. Deux redactions du meme
        rendu feraient lire `25 fps` sur un ecran et `25.0 fps` sur le suivant
        pour le meme rush.

        Rend la chaine vide tant que rien n'est sonde : un bandeau nu est ce
        que la maquette `E2-1` porte, et c'est un etat legitime -- jamais une
        moitie de mesure.
        """
        from . import rushes

        if self.sondee is None:
            return ""
        source = self.sondee.source
        return rushes.bandeau_du_rush(
            self.rush_id, float(source.fps_source),
            source.source_frame_count,
            getattr(self.app, "ascii_seul", False))

    def _juger(self, cadences_cochees):
        """Monter `E2-3` -- ou l'ecran d'ecrasement -- sur le plan des cochees."""
        try:
            plan = preparer_le_plan(
                self.dossier_projet, rush_id=self.rush_id,
                video_path=self.sondee.source.video_path,
                cadences=cadences_cochees,
                largeur=self.sondee.largeur, hauteur=self.sondee.hauteur,
                **self._bornes)
        except BaseException as exception:   # noqa: BLE001 -- voir _refuser
            return self._refuser(exception)
        return ouvrir_le_point_de_jugement(self.app, plan,
                                           sur_ecriture=self._ecrire,
                                           objet=self.objet_du_bandeau)

    def _ecrire(self, plan: PlanExtraction) -> None:
        """L'ecriture, et elle seule : `E2-4` monte d'abord, le coeur ensuite.

        L'ordre est tenu par :func:`lancer_l_extraction`, qui prend le
        rendez-vous de dessin **et** part au fil -- voir son docstring pour ce
        que chacun des deux tient, et pour ce que le rendez-vous seul ne
        tenait pas.

        `EPIC11-ARB-13`, verbatim : « La fin d'une execution ramene au **menu
        des ateliers du projet ouvert** [...], jamais a l'ecran projet. » C'est
        `EcranResultat` qui porte cette suite, et `CoqueTui.revenir_aux_ateliers`
        qui la tient ; rien n'est a rajouter ici.
        """
        ecran = ouvrir_l_execution(self.app, plan,
                                   objet=self.objet_du_bandeau)
        # Le journal de `E2-4` n'existe qu'une fois l'ecran monte : c'est ici,
        # et pas a la construction du parcours, que le relais trouve sa cible.
        if self._relais_de_journal is not None:
            self._relais_de_journal.viser(ecran.surface.journal)
        lancer_l_extraction(self.app, ecran, plan, logger=self._logger,
                            extraire=self._extraire, sur_suite=self.suivre,
                            sur_rapport=self._retenir_le_rapport)

    def _retenir_le_rapport(self, rapport: RapportExtraction) -> None:
        """Garder ce que la passe a produit. **Appele DEPUIS LA BOUCLE.**

        Le rapport est retenu parce que :meth:`suivre` en a besoin plus tard --
        « Ouvrir le dossier des lots » ouvre les dossiers que le coeur a
        RENDUS, et personne d'autre ne les connait.

        Il est pose **avant** que `E2-5` monte, et non apres : l'ecran de
        resultat porte les suites, donc une frappe arrivee dans la meme image
        que son montage trouverait sinon un `rapport` a `None` et une suite
        qui ne mene nulle part.

        C'etait le corps de l'ancienne `_conclure`, que le passage au fil a
        scindee : `executer_et_conclure` melait le travail de coeur et le
        toucher de l'arbre de widgets, ce qui n'est plus tenable des lors que
        le coeur tourne ailleurs que sur la boucle.
        """
        self.rapport = rapport

    # -- ce que `E2-5` fait d'une suite choisie ------------------------------

    def suivre(self, suite: str) -> None:
        """Le rappel des suites de `E2-5`. **Aucune n'est muette.**

        Trois destinations, et la troisieme est le filet :

        * `SUITE_DOSSIER` remet le dossier des lots ecrits a l'explorateur du
          bureau, et **dit** ce qui s'est passe -- y compris qu'aucun bureau
          n'est joignable ici, ce qui est le cas d'un conteneur sans affichage.
          Tolerance nommee d'`EPIC11-ARB-85` ;
        * `SUITE_AUTRE_RUSH` remonte a la page d'ouverture de l'atelier, la
          liste des rushes (Egan, 2026-08-30 : « ca doit mener a la page
          d'ouverture de l'atelier, c'est-a-dire la liste des rushes ») ;
        * `SUITE_PDF` ouvre l'atelier Pdf sur la liste des lots -- voir
          :meth:`_composer_les_planches_de_ces_lots` ;
        * **tout libelle inconnu** mene a l'ecran qui **NOMME** l'absence.
          C'est la cinquieme consigne du lot `K3` : « une suite sans
          destination doit le DIRE, pas ne rien faire », et le filet est ce qui
          empeche qu'une suite ajoutee demain redevienne decorative en silence.

        **Le docstring de cette methode a ete FAUX pendant quatre jours**, et
        c'est ce qui a rendu le manque invisible en relecture : il ecrivait
        « `SUITE_PDF`, dont l'atelier n'existe pas » alors que la story 11.7
        l'avait livre et que `ChaineReelle.atelier_pdf` le cablait. Un
        justificatif qu'on ne rouvre pas se perime en silence ; la frontiere de
        `test_couverture_des_suites.py` ne se perime pas, elle.

        **Ce que cette methode ne fait jamais** : rien ecrire, rien effacer,
        rien relancer. Une suite est une navigation ; l'ecriture est finie
        quand `E2-5` monte.
        """
        if suite == SUITE_DOSSIER:
            self._ouvrir_le_dossier_des_lots()
            return
        if suite == SUITE_AUTRE_RUSH:
            remonter_a_l_ouverture_de_l_atelier(self.app)
            return
        if suite == SUITE_PDF:
            self._composer_les_planches_de_ces_lots()
            return
        self.app.descendre(EcranPasEncore(
            suite, self.app.QUAND_ARRIVENT_LES_ATELIERS))

    def _composer_les_planches_de_ces_lots(self) -> None:
        """`MQ-4` : l'atelier Pdf, ouvert sur les lots qui viennent d'etre ecrits.

        **On REMONTE AU MENU DES ATELIERS d'abord, et c'est la moitie du
        geste.** Cette suite change d'atelier : sans depilement, tout le
        parcours d'extraction -- cadences, jugement, execution, resultat --
        resterait sous la liste des lots, et `Echap` ramenerait l'operateur sur
        le compte rendu d'une extraction finie au lieu du menu. C'est le
        finding `F3`, un atelier plus loin, et le geste est celui que les
        suites de `E5-5` emploient deja pour la meme raison. On remonte au menu
        et **pas plus haut** : `EPIC11-ARB-13`, verbatim, « la fin d'une
        execution ramene au menu des ateliers du projet ouvert [...], jamais a
        l'ecran projet ».

        **Aucun lot n'est passe a l'atelier Pdf, et c'est voulu** : il relit le
        manifeste, ou l'extraction vient d'inscrire ce qu'elle a ecrit. Lui
        remettre une liste calculee ici la ferait diverger de celle du disque
        au premier ecart -- « l'apercu ne peut jamais mentir »
        (`EPIC11-ARB-46`). La suite n'est de toute facon offerte que si un lot
        a ete ecrit (:func:`suites_du_resultat`).
        """
        from .atelier_pdf import ouvrir_la_composition_des_planches

        composer = (self._composer_les_planches
                    or ouvrir_la_composition_des_planches)
        self.app.revenir_aux_ateliers()
        composer(self.app, self.dossier_projet)

    def _ouvrir_le_dossier_des_lots(self) -> None:
        """Remettre le dossier des lots ecrits a l'explorateur du systeme.

        **Le resultat est DIT, dans les deux cas**, et c'est la moitie du
        correctif : un echec silencieux serait indistinguable de la suite
        decorative qu'on vient de corriger. C'est pour cela que
        :func:`~mixed_media_utility.tui.execution.ouvrir_dans_l_explorateur_du_systeme`
        rend une phrase plutot qu'un booleen. La phrase est **une mesure** -- un
        chemin, ou un motif nomme -- et jamais une touche ni un conseil
        (`EPIC11-ARB-56`).

        **L'ecran ne change pas** : on reste sur `E2-5`, dont les chiffres
        restent lisibles. Descendre d'un palier pour annoncer qu'un dossier a
        ete ouvert ferait perdre le compte rendu au moment meme ou l'operateur
        va le comparer au contenu du dossier.
        """
        dossier = dossier_a_ouvrir(self.rapport or RapportExtraction())
        if dossier is None:
            fait = AUCUN_LOT_A_OUVRIR
        else:
            fait = ouvrir_dans_l_explorateur_du_systeme(dossier)
        if getattr(self.app, "ascii_seul", False):
            fait = jetons.replier_ascii(fait)
        self.app.palier_courant.poser_etat(fait)

    # -- les deux refus, tous deux rendus PAR LE CODE DU COEUR ---------------

    def _refuser_le_rush_delinke(self):
        """Un rush sans fichier source ne se sonde pas : il se relinke.

        Le refus est celui du coeur (`relink.refus_necessite_le_rush`), avec
        son code et son message verbatim, et l'ecran est celui que la story a
        deja livre pour les refus de relink -- ses trois suites menent a la
        reparation. Un ecran « pas encore » serait faux ici : rien ne manque au
        produit, c'est le fichier qui manque.
        """
        from .. import relink
        from . import rushes
        from .atelier_extraction import EcranRefusRelink

        erreur = relink.refus_necessite_le_rush(DEMANDEUR_DU_FICHIER_SOURCE,
                                                self.rush_id)
        # **Le code se lit sur `.reason`, jamais dans la phrase** : « le motif
        # voyage sur `.reason` [...], jamais dans le texte du message: un
        # appelant qui veut distinguer les refus n'a pas a analyser une phrase
        # francaise » (`relink.RelinkError`).
        ecran = EcranRefusRelink(rushes.Refus(erreur.reason, str(erreur)))
        self.app.descendre(ecran)
        return ecran

    def _refuser(self, exception: BaseException):
        """Rendre un refus du coeur par son code, ou **relayer** l'inconnu.

        Meme contrat que :func:`executer_le_plan` : ce que la table du coeur ne
        nomme pas n'est pas deguise en refus metier, il remonte. Un sondage qui
        echoue sur une panne non nommee est un defaut, pas un refus, et le
        cacher derriere un ecran de refus le rendrait indistinguable.
        """
        refus = refus_de(exception)
        if refus is None:
            raise exception
        return ouvrir_le_refus(self.app, refus, RapportExtraction())


def ouvrir_les_cadences(app, dossier_projet: Path | str, rush_id: str, **reglages):
    """Ce que « choisir un rush » ouvre, cable jusqu'a « ecrit ».

    C'est le rappel que :class:`ChaineReelle` injecte : sa signature est celle
    que `ChaineReelle.extraire` appelle, `(app, dossier, rush_id)`, et tout le
    reste est du reglage que seuls les bancs fournissent.
    """
    return ParcoursExtraction(app, dossier_projet, rush_id, **reglages).ouvrir()


# ---------------------------------------------------------------------------
# `E8` et `E9` -- le branchement, et la chaine reelle des paliers
# ---------------------------------------------------------------------------

class ChaineReelle:
    """Les trois paliers du produit, cables les uns aux autres.

    **Le defaut que cette classe ferme est mesure** (2026-08-29) :
    `python -m mixed_media_utility.tui` construisait `CoqueTui()` **sans
    paliers**, donc `coque.paliers_temoins()` -- trois `PalierTemoin`. `E0-1`
    (story 11.2) et `E1-1` (story 11.3) etaient livres, testes, et cables
    **nulle part** dans l'application : ils ne vivaient que dans les bancs et
    dans `demo_vague_2.py`, qui assemble la chaine a la main. C'est cette
    assemblee manuelle qui a masque le manque pendant deux vagues -- la recette
    passait par la demo, jamais par le point d'entree du produit.

    Le cablage vit dans une **classe** et non dans une fonction a fermetures
    parce que chaque rappel a besoin de l'application, qui a besoin des paliers,
    qui ont besoin des rappels : les methodes liees rompent le cycle sans
    toucher aux attributs prives des ecrans.
    """

    #: Ce que les deux commandes du palier Projet attendent, et **rien de
    #: plus** : l'ecran qui leur donnerait un fichier a designer. Le coeur des
    #: six fonctions de `palier_projet.py` est ecrit, teste et exporte ; ce qui
    #: manque tient en un ecran par commande.
    #:
    #: **Ce n'est volontairement ni une date ni une vague** : aucune story du
    #: depot ne porte ces deux commandes au 2026-09-06, et une echeance de
    #: calendrier inventee serait pire que le silence -- elle mentirait la ou
    #: le silence se contentait de ne rien dire. Celle-ci se verifie a l'oeil.
    QUAND_LA_PORTE_VERS_UN_FICHIER = (
        "l'écran de désignation de fichier de ce palier")

    def __init__(self, recents=None, *, sans_couleur: bool = False,
                 ascii_seul: bool = False,
                 ouvrir_les_cadences: Callable[..., Any] | None = None,
                 ouvrir_l_atelier_scan: Callable[..., Any] | None = None,
                 ouvrir_l_atelier_pdf: Callable[..., Any] | None = None,
                 ouvrir_l_atelier_exports: Callable[..., Any] | None = None,
                 ouvrir_la_gestion_des_medias: Callable[..., Any] | None = None,
                 ouvrir_le_profil_par_defaut: Callable[..., Any] | None = None
                 ) -> None:
        # Imports locaux : `ecran_projet` tire `gui.depot_projets`, et le garder
        # hors du chargement du module laisse `--diagnostic-chemin` repondre sur
        # un environnement partiel.
        from .ecran_ateliers import EcranAteliers
        from .ecran_projet import EcranProjet
        from .palier_projet import EcranPalierProjet

        #: Ce que faire d'un rush choisi. Injecte : l'ecran des cadences
        #: (`E2-2`, lot `E3`) est le seul appelant naturel de
        #: :func:`preparer_le_plan`, et il n'est pas dans ce module. Sans lui,
        #: choisir un rush mene a l'ecran « pas encore », qui nomme ce qui
        #: manque -- jamais a une touche muette.
        self._ouvrir_les_cadences = ouvrir_les_cadences

        #: Ce que faire de l'entree *Scan*. Injecte pour le meme motif exactement
        #: que les cadences : le parcours du Scan (story 11.5) vit dans son
        #: propre module, et le garder hors d'ici est ce qui rend cette chaine
        #: mesurable sans disque et sans coeur. **Le produit, lui, n'a pas de
        #: version degradee** : `chaine_du_produit` l'injecte toujours.
        self._ouvrir_l_atelier_scan = ouvrir_l_atelier_scan

        #: Ce que faire de l'entree *Pdf*. Meme forme et meme motif que les deux
        #: precedents (story 11.7, lot C) : l'atelier Pdf vit dans son propre
        #: module, et le garder hors d'ici est ce qui rend cette chaine mesurable
        #: sans disque et sans coeur. **Le produit n'a pas de version degradee** :
        #: `chaine_du_produit` l'injecte toujours.
        self._ouvrir_l_atelier_pdf = ouvrir_l_atelier_pdf

        #: Ce que faire de l'entree *Exports*. Meme forme et meme motif que les
        #: trois precedents (story 11.8, lot B5) : le parcours de l'atelier
        #: Exports vit dans son propre module, et le garder hors d'ici est ce
        #: qui rend cette chaine mesurable sans disque et sans coeur. **Le
        #: produit n'a pas de version degradee** : `chaine_du_produit`
        #: l'injecte toujours.
        self._ouvrir_l_atelier_exports = ouvrir_l_atelier_exports

        #: Ce que faire de l'entree *Gestion des medias* du palier Projet.
        #: Meme forme et meme motif que les quatre precedents (story 11.11,
        #: lot « la porte de l'inventaire ») : le parcours vit dans son propre
        #: module, et le garder hors d'ici est ce qui rend cette chaine
        #: mesurable sans disque et sans coeur. **Le produit n'a pas de
        #: version degradee** : `chaine_du_produit` l'injecte toujours.
        self._ouvrir_la_gestion_des_medias = ouvrir_la_gestion_des_medias

        #: Ce que faire de l'entree *Profil de calibration par defaut* du
        #: palier Projet. Meme forme et meme motif que les cinq precedents :
        #: le parcours vit dans son propre module (`palier_profil_defaut`), et
        #: le garder hors d'ici est ce qui rend cette chaine mesurable sans
        #: disque et sans coeur. **Le produit n'a pas de version degradee** :
        #: `chaine_du_produit` l'injecte toujours.
        self._ouvrir_le_profil_par_defaut = ouvrir_le_profil_par_defaut

        self.ecran_projet = EcranProjet(recents=recents, ouvrir=self.ouvrir,
                                        creer=self.creer)
        self.menu = EcranAteliers(entrer=self.entrer)
        self.palier_projet = EcranPalierProjet(entrer=self.entrer_commande)
        self.app = CoqueTui(
            paliers=[self.ecran_projet, self.menu, self.palier_projet],
            contexte=Contexte(projet="-"),
            sans_couleur=sans_couleur, ascii_seul=ascii_seul)

    # -- palier 0 -> palier 1 -----------------------------------------------

    def ouvrir(self, dossier) -> None:
        """Nommer le projet, le poser sur les paliers du bas, relire, descendre.

        **Dans cet ordre** : le menu lit son manifeste avant d'etre monte, faute
        de quoi il se dessinerait vide une premiere fois puis se corrigerait.
        """
        dossier = Path(dossier)
        self.app.contexte = Contexte(projet=dossier.name)
        self.menu.dossier = self.palier_projet.dossier = dossier
        self.menu.charger()
        self.app.descendre()

    def creer(self, cible) -> None:
        """`E0-4`, monte par-dessus le palier 0, et qui ouvre ce qu'il a cree.

        **`apres_creation` vise `EcranProjet.ouvrir`, pas le `ouvrir` d'ici**, et
        l'ecart entre les deux est tout le defaut du terrain (retour d'Egan du
        2026-09-06 : « Echap fais un retour a l'ecran precedent au lieu d'ouvrir
        la liste des projets avec ce projet present »). La pile de navigation
        etait saine -- un seul Echap ramenait bien au palier 0, ce que
        `test_paliers_et_passages` mesurait deja. Ce qui manquait est ailleurs :
        `recents.noter_ouverture` n'est appele QUE par `EcranProjet.ouvrir`, et
        viser `self.ouvrir` court-circuitait cette methode. Le projet fraichement
        cree n'entrait donc jamais dans les recents, et l'operateur retombait sur
        une liste inchangee -- ce qu'il a lu, legitimement, comme un mauvais
        retour de pile.

        Rien n'est appele deux fois : `EcranProjet.ouvrir` note, recharge sa
        liste, puis delegue a son propre `_ouvrir`, qui **est** le `ouvrir`
        ci-dessus (injecte a la construction). La chaine se referme d'elle-meme.
        """
        from .ecran_projet import EcranCreation

        self.app.descendre(EcranCreation(
            dossier_parent=str(Path(cible).parent) if cible else "",
            nom=Path(cible).name if cible else "",
            apres_creation=self.ecran_projet.ouvrir))

    # -- palier 1 -> palier 2 (`E8`) ----------------------------------------

    def entrer(self, entree) -> None:
        """`⏎` sur une entree du menu des ateliers.

        `EPIC11-ARB-28`, verbatim : « **Extraction et Exports n'en ont pas** :
        une seule entree chacun, donc le menu serait un ecran a franchir pour
        rien. » L'entree Extraction monte donc `E2-1` **directement** ; aucun
        ecran ne s'intercale.

        Les entrees Scan et Pdf, elles, **commencent par leur menu** (`E3-0`,
        `E5-0`) : le meme arbitrage tranche atelier par atelier, et ces deux-la
        ont deux entrees chacun.

        **Plus AUCUN atelier ne tombe dans la branche par defaut** depuis le
        lot B5 de la story 11.8 : Exports etait le dernier, et il monte
        desormais `E4-1` directement -- lui non plus n'a pas de menu
        d'atelier. Le repli reste, et il n'est pas mort : il attrape une
        entree que `projet_lecture` ajouterait demain sans cablage, et il la
        NOMME. Le banc `test_atelier_pdf_menu.py` mesure cette branche en
        **ensemble exact**, desormais vide : une branche mal placee qui y
        renverrait un atelier cable serait invisible a toute assertion
        positive prise atelier par atelier.
        """
        if entree.nom == projet_lecture.PROJET:
            self.app.descendre()
            return
        if entree.nom == projet_lecture.EXTRACTION:
            self.app.descendre(self.atelier_extraction())
            return
        if entree.nom == projet_lecture.SCAN:
            self.atelier_scan()
            return
        if entree.nom == projet_lecture.PDF:
            self.atelier_pdf()
            return
        if entree.nom == projet_lecture.EXPORTS:
            self.atelier_exports()
            return
        self.app.descendre(EcranPasEncore(
            f"L'atelier {entree.nom}", self.app.QUAND_ARRIVENT_LES_ATELIERS))

    def atelier_extraction(self):
        """`E2-1`, sur le projet courant. Aucun menu intermediaire.

        **Les DEUX TEMPS de la declaration y sont injectes** (AC 3.1,
        `EPIC11-ARB-4`), et c'est ce qui ferme `K1.1d` : le rappel etait
        accepte par l'ecran et passe nulle part, si bien que « Ajouter un
        rush » menait a un ecran « pas encore » alors que le coeur savait
        declarer. Ils sont **deux** parce que le panneau chiffre se peint entre
        eux -- `preparer_une_declaration` ne touche aucun octet, une frontiere
        du coeur le mesure, et `ecrire_la_declaration` n'est atteint qu'apres
        la validation de l'operateur.
        """
        from .atelier_extraction import EcranRushes

        return EcranRushes(self.menu.dossier, extraire=self.extraire,
                           preparer=self.preparer_la_declaration,
                           ecrire=self.ecrire_la_declaration)

    def preparer_la_declaration(self, cible: Path, *,
                                force_distinct: bool = False):
        """Temps 1 : ce que la declaration ECRIRA, sans rien avoir ecrit.

        Le journal est celui du produit, comme pour l'extraction : le coeur y
        inscrit la qualification de la source, et un `getLogger` racine
        ecrirait par-dessus l'interface plein ecran.

        **`force_distinct` est la deuxieme issue de `E2-1f` portee jusqu'au
        coeur** (`EPIC11-ARB-231` pour la sortie, `EPIC11-ARB-232` pour le
        drapeau, qui est `--force-distinct` en ligne de commande). Il est
        **transporte** et jamais interprete ici : la separation se decide au
        coeur, ou elle est journalisee et ou le suffixe d'`EPIC11-ARB-9` la
        rend. Le poser par defaut a `False` garde intact le contrat du rappel
        pour tout appelant qui l'ignore -- les bancs qui doublent le temps 1,
        et le chemin nominal de la declaration.
        """
        from ..declaration_de_rush import preparer_une_declaration

        logger, _relais = journal_du_produit()
        return preparer_une_declaration(
            project_dir=self.menu.dossier, video_path=cible, logger=logger,
            force_distinct=force_distinct)

    def ecrire_la_declaration(self, preparee) -> str:
        """Temps 2 : l'ecriture, et elle rend le `rush_id` REELLEMENT ecrit.

        C'est ce que `EcranRushes._viser_le_rush_declare` attend, et pas un
        identifiant redérivé du nom de fichier : le coeur a pu lever une
        homonymie (`EPIC11-ARB-9`) et ecrire un `rush_id` suffixe. Le deriver
        une seconde fois viserait un rush qui n'existe pas, ou pire, son
        homonyme -- `EPIC11-ARB-146` pris a l'endroit.
        """
        from ..declaration_de_rush import ecrire_la_declaration

        logger, _relais = journal_du_produit()
        return ecrire_la_declaration(preparee, logger=logger).rush_id

    def atelier_scan(self) -> None:
        """`E3-0`, le menu de l'atelier Scan -- et il en a un.

        `EPIC11-ARB-28`, verbatim : « **Tout atelier qui a plus d'une entree
        commence par un menu d'atelier** [...] la regle est "plus d'une
        entree", pas "un menu partout" ». Le Scan en a deux (detecter,
        calibrer), l'Extraction une seule : c'est pourquoi l'une passe par son
        menu et l'autre monte son premier ecran directement.

        Le parcours est **injecte**, et son absence n'est pas silencieuse : sans
        lui on nomme ce qui manque plutot que de laisser la touche muette --
        c'est la forme exacte du finding `K3`, et c'est ce que la garde des
        rappels cables mesure.
        """
        if self._ouvrir_l_atelier_scan is not None:
            self._ouvrir_l_atelier_scan(self.app, self.menu.dossier)
            return
        self.app.descendre(EcranPasEncore(
            f"L'atelier {projet_lecture.SCAN}",
            self.app.QUAND_ARRIVENT_LES_ATELIERS))

    def atelier_pdf(self) -> None:
        """`E5-0`, le menu de l'atelier Pdf -- et il en a un.

        `EPIC11-ARB-28`, verbatim : « **Tout atelier qui a plus d'une entree
        commence par un menu d'atelier** ». Le Pdf en a deux -- composer des
        planches, generer la mire de calibration --, exactement comme le Scan.

        L'atelier est **injecte**, et son absence n'est pas silencieuse : sans
        lui on nomme ce qui manque plutot que de laisser la touche muette. Meme
        forme que :meth:`atelier_scan`, et pour le meme motif.
        """
        if self._ouvrir_l_atelier_pdf is not None:
            self._ouvrir_l_atelier_pdf(self.app, self.menu.dossier)
            return
        self.app.descendre(EcranPasEncore(
            f"L'atelier {projet_lecture.PDF}",
            self.app.QUAND_ARRIVENT_LES_ATELIERS))

    def atelier_exports(self) -> None:
        """`E4-1`, la designation du lot -- et **aucun menu ne s'intercale**.

        `EPIC11-ARB-28`, verbatim : « **Extraction et Exports n'en ont pas** :
        une seule entree chacun, donc le menu serait un ecran a franchir pour
        rien. » C'est donc la forme de :meth:`atelier_extraction`, pas celle du
        Scan ni du Pdf.

        Le parcours est **injecte**, et son absence n'est pas silencieuse :
        sans lui on nomme ce qui manque plutot que de laisser la touche muette.
        Meme forme que :meth:`atelier_scan` et :meth:`atelier_pdf`, et pour le
        meme motif.
        """
        if self._ouvrir_l_atelier_exports is not None:
            self._ouvrir_l_atelier_exports(self.app, self.menu.dossier)
            return
        self.app.descendre(EcranPasEncore(
            f"L'atelier {projet_lecture.EXPORTS}",
            self.app.QUAND_ARRIVENT_LES_ATELIERS))

    def extraire(self, rush_id: str) -> None:
        """Ce que « choisir un rush » ouvre : les cadences (`E2-2`).

        L'ecran des cadences appartient au lot `E3` et n'est pas monte ici : le
        rappel est **injecte**. Absent, on nomme ce qui manque plutot que de
        laisser la touche muette.
        """
        if self._ouvrir_les_cadences is not None:
            self._ouvrir_les_cadences(self.app, self.menu.dossier, rush_id)
            return
        self.app.descendre(EcranPasEncore(
            f"Les cadences de {rush_id}",
            self.app.QUAND_ARRIVENT_LES_ATELIERS))

    def gestion_des_medias(self, issue: Issue | None = None) -> None:
        """`E6-1`, l'inventaire du projet -- la PREMIERE entree du palier.

        **C'est `MQ-8`, et c'etait le dernier grand manque du parcours**
        (audit du 2026-09-06). `EcranInventaireDuProjet` est livre depuis la
        story 11.11 et n'etait construit par **rien** : les trois entrees de ce
        palier tombaient dans le filet, y compris celle que la maquette validee
        `E6-0-projet-palier` dessine en tete.

        Le dossier se lit sur le palier, ou `ouvrir` l'a pose en meme temps que
        celui du menu : le redeviner ailleurs ferait diverger les deux.

        `issue` est recue et **non lue** : c'est le prix d'une table de
        destinations dont toutes les valeurs ont la meme signature. L'inventaire
        n'a besoin que du dossier du palier, qu'il ne tient pas de l'issue.

        Le parcours est **injecte**, et son absence n'est pas silencieuse :
        sans lui on nomme ce qui manque plutot que de laisser la touche muette
        -- meme forme que les quatre ateliers, et c'est ce que la garde des
        rappels cables mesure.
        """
        from . import palier_projet

        if self._ouvrir_la_gestion_des_medias is not None:
            self._ouvrir_la_gestion_des_medias(self.app,
                                               self.palier_projet.dossier)
            return
        self.app.descendre(EcranPasEncore(
            palier_projet.LIBELLES[palier_projet.ENTREE_MEDIAS],
            self.QUAND_LA_PORTE_VERS_UN_FICHIER))

    def profil_par_defaut(self, issue: Issue | None = None) -> None:
        """« Profil de calibration par defaut » -- la DEUXIEME entree du palier.

        **C'est le manque qu'Egan a trouve sur le terrain le 2026-09-06**
        (« Cet ecran n'existe pas encore (mauvais cablage ?) ») : les six
        fonctions de `palier_projet.py` etaient ecrites, exportees et testees,
        et cette entree tombait dans le filet.

        Le dossier se lit sur le palier, ou `ouvrir` l'a pose en meme temps que
        celui du menu : le redeviner ailleurs ferait diverger les deux.

        `issue` est recue et **non lue** : c'est le prix d'une table de
        destinations dont toutes les valeurs ont la meme signature.

        Le parcours est **injecte**, et son absence n'est pas silencieuse :
        sans lui on nomme ce qui manque plutot que de laisser la touche muette
        -- meme forme que les cinq precedents.
        """
        from . import palier_projet

        if self._ouvrir_le_profil_par_defaut is not None:
            self._ouvrir_le_profil_par_defaut(self.app,
                                              self.palier_projet.dossier)
            return
        self.app.descendre(EcranPasEncore(
            palier_projet.LIBELLES[palier_projet.ENTREE_PROFIL],
            self.QUAND_LA_PORTE_VERS_UN_FICHIER))

    def entrer_commande(self, issue: Issue) -> None:
        """Les trois entrees du palier Projet, **toutes les trois nommees**.

        `ENTREE_MEDIAS` ouvre l'inventaire depuis le lot « la porte de
        l'inventaire ». `ENTREE_PROFIL` ouvre, depuis le retour terrain d'Egan
        du 2026-09-06, l'ecran « Profil de calibration par defaut » de
        `palier_profil_defaut` -- qui porte, lui, la designation de fichier qui
        manquait. **`ENTREE_RECONSTRUCTION` est la seule qui reste au filet** :
        `apercu_de_reconstruction` exige des chemins que seule
        `demo_vague_2.py` fournit, depuis son bac. On le dit donc, plutot que
        de laisser `⏎` inerte.

        **Les trois destinations sont ecrites dans une table, et c'est mesure**
        (`test_couverture_des_suites.py`). Une entree qui tomberait dans le
        filet par un `else` muet serait indistinguable d'une entree qui n'a
        legitimement pas de destination -- c'est exactement le defaut que
        `MQ-4` et `MQ-5` ont paye la meme nuit sur les suites. Nommer les trois
        fait rougir la frontiere le jour ou `palier_projet` en declarera une
        quatrieme sans la cabler.

        **L'echeance manquait, et c'etait `MQ-8`** (audit du 2026-09-06). Ces
        commandes montaient `EcranPasEncore` **sans `quand`**, si bien que les
        seules entrees du palier etaient indistinguables d'un abandon
        -- exactement ce que la ligne demandee par Egan le 2026-08-28 existe
        pour eviter : « comme ca on sait que c'est temporaire et que ce n'est
        pas un bug ».

        Ce que la ligne annonce est :data:`QUAND_LA_PORTE_VERS_UN_FICHIER`, et
        le choix de sa forme est le sujet : **aucune story du depot ne porte
        la reconstruction**, donc promettre une vague ou une date serait
        inventer. Ce qui est nomme est ce qui manque **reellement** et qui se
        verifie a l'oeil -- l'ecran de designation de fichier --, et c'est une
        echeance vraie plutot qu'un calendrier faux. La position d'origine
        (« sans annoncer d'echeance, faute d'en connaitre une : une date
        inventee vaudrait moins que pas de date ») avait raison sur la date et
        tort sur le silence : le silence, lui aussi, dit quelque chose de faux.
        """
        # Import local : `palier_projet` tire `gui.depot_projets`, et le garder
        # hors du chargement du module laisse `--diagnostic-chemin` repondre
        # sur un environnement partiel. Meme motif que `__init__`.
        from . import palier_projet

        filet = self._pas_de_porte_vers_un_fichier
        # Toutes les destinations recoivent l'issue frappee, y compris celle
        # qui n'en a pas besoin : une table dont les valeurs n'ont pas la meme
        # signature n'est plus une table, c'est un aiguillage deguise.
        destinations = {
            palier_projet.ENTREE_MEDIAS: self.gestion_des_medias,
            palier_projet.ENTREE_PROFIL: self.profil_par_defaut,
            palier_projet.ENTREE_RECONSTRUCTION: filet,
        }
        # Une entree inconnue tombe dans le meme filet que celle qui n'a pas
        # encore d'ecran : jamais une touche muette.
        destinations.get(issue.cle, filet)(issue)

    def _pas_de_porte_vers_un_fichier(self, issue: Issue) -> None:
        """Le filet des entrees qui attendent leur ecran de designation."""
        self.app.descendre(EcranPasEncore(
            issue.libelle, self.QUAND_LA_PORTE_VERS_UN_FICHIER))


def chaine_du_produit(*, sans_couleur: bool = False,
                      ascii_seul: bool = False, recents=None) -> ChaineReelle:
    """La chaine du produit : trois paliers reels **et le parcours reel**.

    C'est ici, et nulle part ailleurs, que :func:`ouvrir_les_cadences`,
    :func:`~mixed_media_utility.tui.atelier_scan_parcours.ouvrir_l_atelier_scan`,
    :func:`~mixed_media_utility.tui.atelier_pdf.ouvrir_l_atelier_pdf` et
    :func:`~mixed_media_utility.tui.atelier_exports_parcours.ouvrir_l_atelier_exports`
    sont injectes. Les rappels restent des arguments de :class:`ChaineReelle` parce que
    c'est ce qui rend la chaine mesurable sans disque, sans `ffprobe` et sans
    projet -- mais **le produit, lui, n'a pas de version degradee** : sans
    cette injection, choisir un rush menerait a l'ecran « pas encore » alors
    que l'atelier existe. C'est exactement la panne du lot `E9`, d'un cran plus
    loin : un composant livre, teste, et cable nulle part dans l'application
    est un composant que le produit n'a pas.
    """
    from .atelier_exports_parcours import ouvrir_l_atelier_exports
    from .atelier_pdf import ouvrir_l_atelier_pdf
    from .atelier_scan_parcours import ouvrir_l_atelier_scan
    from .palier_profil_defaut import ouvrir_le_profil_par_defaut
    from .projet_inventaire import ouvrir_l_inventaire_du_projet

    return ChaineReelle(recents=recents, sans_couleur=sans_couleur,
                        ascii_seul=ascii_seul,
                        ouvrir_les_cadences=ouvrir_les_cadences,
                        ouvrir_l_atelier_scan=ouvrir_l_atelier_scan,
                        ouvrir_l_atelier_pdf=ouvrir_l_atelier_pdf,
                        ouvrir_l_atelier_exports=ouvrir_l_atelier_exports,
                        ouvrir_la_gestion_des_medias=ouvrir_l_inventaire_du_projet,
                        ouvrir_le_profil_par_defaut=ouvrir_le_profil_par_defaut)


def construire_l_application(*, sans_couleur: bool = False,
                             ascii_seul: bool = False,
                             recents=None) -> CoqueTui:
    """L'application du produit : trois paliers **reels**, zero palier temoin."""
    return chaine_du_produit(sans_couleur=sans_couleur, ascii_seul=ascii_seul,
                             recents=recents).app


__all__ = [
    "BORNES_ABSENTES",
    "INDENT_DES_NOMS",
    "RACCOURCIS_EXTRACTION_CONFIRMATION",
    "EcranExtractionConfirmation",
    "EcranExtractionEcrasement",
    "DEMANDEUR_DU_FICHIER_SOURCE",
    "CANAUX_ECRITS",
    "ChaineReelle",
    "ISSUE_ANNULER",
    "CONDUITES",
    "CONDUITE_NOMINALE",
    "CONDUITE_NOUVELLE_VERSION",
    "CONDUITE_ECRASEMENT_CONSCIENT",
    "CONDUITE_DES_ISSUES",
    "LIBELLE_NOUVELLE_VERSION",
    "LIBELLE_NOUVELLES_VERSIONS",
    "LIBELLE_ETAT_DEJA_AVANCE",
    "CE_QUE_LA_VERSION_COUTE",
    "CE_QUE_LA_VERSION_COUTE_SANS_CHIFFRE",
    "SEPARATEUR_DES_NOMS",
    "ISSUE_ECRASER",
    "ISSUE_NOUVELLE_VERSION",
    "ISSUE_EXTRAIRE",
    "ISSUE_MODIFIER",
    "LotEcrit",
    "LotPrevu",
    "OCTETS_PAR_CANAL",
    "ParcoursExtraction",
    "PlanExtraction",
    "RapportExtraction",
    "RefusDExtraction",
    "SUITE_AUTRE_RUSH",
    "SourceProbee",
    "AUCUN_LOT_A_OUVRIR",
    "SUITE_DOSSIER",
    "SUITE_PDF",
    "TITRE_A_ECRIRE",
    "TITRE_ECRASEMENT",
    "RACCOURCIS_EXTRACTION_ECRASEMENT",
    "JETON_DU_PLI",
    "TITRE_ECRIT",
    "canal_de_progression",
    "chaine_du_produit",
    "journal_du_produit",
    "chemin_du_rush",
    "construire_l_application",
    "dossier_a_ouvrir",
    "conclure_l_extraction",
    "executer_et_conclure",
    "executer_le_plan",
    "lancer_l_extraction",
    "OUVRIER_DE_L_EXTRACTION",
    "issues_de_l_ecrasement",
    "libelle_de_la_version",
    "jouer_les_cadences",
    "issues_de_l_extraction",
    "ligne_d_etat_du_resultat",
    "noms_des_lots",
    "noms_du_conflit",
    "nom_prevu",
    "octets_par_frame",
    "ouvrir_le_point_de_jugement",
    "ouvrir_les_cadences",
    "RelaisDeJournal",
    "ouvrir_le_refus",
    "ouvrir_le_resultat",
    "ouvrir_l_execution",
    "panneau_de_l_ecrasement",
    "panneau_de_l_extraction",
    "panneau_du_resultat",
    "phrase_du_cout_de_la_version",
    "preparer_le_plan",
    "refus_d_etat_de_lot",
    "refus_de",
    "remonter_a_l_ouverture_de_l_atelier",
    "sonder_la_source",
    "suites_du_resultat",
    "taille_lisible",
    "texte_des_bornes",
    "titre_de_la_tache",
]
