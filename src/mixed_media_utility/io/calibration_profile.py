"""Persistance du profil de calibration par chaine (story 5.22).

Module **pur**: aucun import numpy/OpenCV. Les coefficients y voyagent comme
des listes de nombres (jamais de tableaux); la reconstruction de l'objet
profil se fait cote couleur, dans `color_calibration.profile_from_document`.

Le fichier de profil vit **dans le projet**, sous
`versions/calibration/<chain_id>.json` (`EPIC5-ARB-81`, tranche le 2026-08-16):
un projet copie tel quel -- fichiers du projet seuls, sans bibliotheque
machine -- contient le profil et permet de le recharger a l'identique. Il est
**autoportant**: il porte son `chain_id`, sa `correction_form_id`, ses
coefficients, ses metadonnees **et la mesure brute de ses pastilles temoins**
(story 5.23), sans rien attendre du manifest ni d'une autre passe de scan.

La recette de persistance reprend celle de `io/extraction_manifest`
(`_serialize` canonique, `_atomic_write`: temporaire dans le dossier projet,
`fsync`, puis `os.replace` -- aucune trace si echec). La relecture est une
**fusion pure** avec defauts (pattern `REREAD_DEFAULTS`, `io/payload.py`): un
champ requis manquant ou de type invalide est un refus nomme, jamais un defaut
invente; un champ optionnel absent prend son defaut.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

from . import project_layout
from .naming import (BOUNDS_SUFFIX_LENGTH, CANONICAL_ID_MAX_LENGTH,
                     scan_chain_suffix)

#: Version de schema du fichier de profil. Un profil ecrit sous une version
#: differente est refuse a la relecture: inventer des champs manquants d'une
#: version plus recente produirait une correction que le fichier ne porte pas.
PROFILE_SCHEMA_VERSION = 1

#: Dossier `versions/` de l'arborescence projet et son sous-dossier des profils
#: de calibration. `versions/` est cree par `ensure_project_layout`
#: (`io/project_layout`); le sous-dossier `calibration/` est cree a l'ecriture.
#:
#: **La valeur est LUE de `project_layout`, elle n'est plus redeclaree ici**
#: (`EPIC11-ARB-225`). Ce module portait sa propre chaine `"versions"`, ce qui
#: est exactement le litteral double que `project_layout` existe pour fermer --
#: son commentaire d'`OUTPUTS_DIRNAME` l'enonce mot pour mot : « doubler la
#: chaine litterale est le defaut que ce module existe pour fermer ». Deux
#: declarations, c'est un renommage qui n'en deplace qu'une et rien qui
#: rougisse. Le nom reste exporte ici pour ses appelants.
VERSIONS_DIRNAME = project_layout.VERSIONS_DIRNAME
CALIBRATION_DIRNAME = "calibration"

#: Pattern impose au `chain_id` par le schema v2 (`project.schema.json`):
#: identique a celui du manifest, car le `chain_id` designe un nom de fichier.
#:
#: Il est confronte par `fullmatch`, jamais par `match`: en Python, `$` accepte
#: un saut de ligne **final**, donc `match` laissait passer `'x\n'`, et un
#: `chain_id` valant `'x\n'` ecrivait `versions/calibration/x\n.json`,
#: introuvable ensuite. Les ancres restent ecrites dans le pattern pour que sa
#: lecture soit sans ambiguite, mais c'est `fullmatch` qui porte la garantie.
#:
#: La garde reste indispensable apres le retrait du drapeau qui nommait la chaine a
#: la main (story 5.23, AC 13): le `chain_id` d'un **profil externe** est lu dans un
#: fichier JSON que le projet n'a pas produit, et c'est desormais le seul chemin par
#: lequel une valeur non derivee atteint un nom de fichier.
_CHAIN_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

#: Champs requis du document de profil, avec leur type attendu. Un champ
#: requis manquant ou mal type est un refus a la relecture et a l'ecriture.
_REQUIRED_FIELDS: dict[str, type] = {
    "schema_version": int,
    "chain_id": str,
    "correction_form_id": str,
    "coefficients": dict,
    "read_patch_count": int,
    "retained_patch_count": int,
    "ink_floor_excluded": bool,
    "source_page_id": str,
    "template_id": str,
}

#: Cle du bloc des mesures **brutes** des pastilles temoins de la page de
#: calibration (story 5.23, mesure du 2026-08-18). Nommee ici et pas recopiee en
#: litteral cote couleur: c'est le seul endroit ou la forme du document est decrite.
WITNESS_RAW_FIELD = "witness_raw_bgr"

#: Cle du **motif** qui dit pourquoi le bandeau de temoins n'a pas ete mesure
#: (story 5.23, `EPIC5-ARB-104`). Il vit a cote de `witness_raw_bgr` et suit
#: **exactement le meme patron**: champ **absent** = rien a signaler, valeur
#: presente = un motif nomme. Un second patron aurait diverge du premier des le
#: premier ajout.
#:
#: Il ferme le second etage du defaut trouve en revue: sans lui,
#: `profile_to_document` omet un bloc de temoins vide, la relecture rend `None`,
#: et la chaine ressort `raw_divergence_no_calibration_sheet` alors que sa page
#: **a bien ete lue** -- le profil persistait la faussete.
WITNESS_BAND_REASON_FIELD = "witness_band_reason"

# ---------------------------------------------------------------------------
# Story 5.23, AC 8quater : l'operateur nomme son profil, la machine le stocke
# ---------------------------------------------------------------------------
#
# Mandat d'Egan (`EPIC5-ARB-83`, geste 3): « le titre dans le qr a pu etre "hp envy 4520
# tiff 600 dpi auto corr off" mais l'utilisateur veut lire "scanner maison default tiff"
# comme nom de fichier. On peut egalement demander un commentaire (facultatif) qu'on
# verra par survol sur le fichier de calibration dans la GUI. **On stockera bien les
# infos officielles mais on laissera l'utilisateur nommer les choses.** »
#
# Les deux champs sont des **etiquettes, jamais des cles**, et c'est la seule chose que
# la relecture de ce module doit garantir. Le document garde intactes son identite
# (`chain_id`), sa forme de correction, ses coefficients, ses cardinaux, sa provenance
# et ses temoins bruts: l'etiquette s'ajoute, elle ne remplace rien. La resolution d'un
# profil reste ce qu'`EPIC5-ARB-83` en a fait -- **le chemin ecrit**, lu dans l'entree
# de manifest (`io/profile_designation.default_profile_path`) --, donc renommer un
# profil ne le rend pas introuvable, et l'etiquette ne peut pas redevenir un appariement
# automatique par la porte de derriere.
#
# L'etiquette a **un seul effet mecanique**: elle nomme le fichier, par un slug derive.
# Le commentaire n'en a aucun; il est stocke pour se lire au survol dans la GUI
# (Epic 7), et la CLI ne l'affiche nulle part ailleurs.

#: Nom du champ d'etiquette libre (le nom que l'operateur veut relire).
LABEL_FIELD = "label"

#: Nom du champ de commentaire libre (survol GUI, Epic 7).
COMMENT_FIELD = "comment"

#: Plafond du commentaire. Il n'est pas cosmetique: le commentaire est recopie dans
#: l'entree autoportante du manifest, et un manifest est relu a chaque commande.
COMMENT_MAX_LENGTH = 2000

#: Miroir de `io/manifest._ABSOLUTE_PATH_PATTERN`, recopie ici parce que ce module reste
#: pur (`io/manifest` importe `jsonschema`) et qu'un test epingle l'egalite des deux
#: patterns -- meme dispositif que la table des formes de correction ci-dessous.
#:
#: Pourquoi une etiquette est confrontee a la garde de **portabilite du manifest**: le
#: contrat v2 interdit toute chaine ressemblant a un chemin absolu **ou qu'elle se
#: trouve** dans le manifest (story 2.1, AC 2 et 3), et l'etiquette y est recopiee.
#: Sans ce refus a l'ecriture du profil, un commentaire commencant par `/home/...`
#: produirait un profil parfaitement valide dont l'entree de manifest serait ensuite
#: **refusee** -- et refusee sur un chemin qui, depuis la revue de 5.22 (bloquant `C2`),
#: se contente d'avertir. La trace du profil disparaitrait donc en silence.
_MANIFEST_ABSOLUTE_PATH_PATTERN = re.compile(r"^(?:/|[A-Za-z]:[\\/]|\\\\)")

#: Tout ce qui n'est **pas** retenu par le slug d'une etiquette. Le slug vise le meme
#: alphabet que `_CHAIN_ID_PATTERN`, en minuscules: c'est lui qui devient un nom de
#: fichier sous `versions/calibration/`.
_LABEL_SLUG_DROP_PATTERN = re.compile(r"[^a-z0-9]+")

#: Alphabet admis dans une etiquette, **apres depliage des accents** (`EPIC5-ARB-99`,
#: geste 1: « refus des caracteres speciaux »). Lettres ASCII, chiffres, espace, tiret
#: et souligne -- tout le reste est refuse, nomme, avant toute ecriture.
#:
#: Ce refus **ne ferme pas** la collision de noms, et le dire ici evite qu'on le croie:
#: `"HP Envy 4520"` et `"hp envy 4520"` sont tous deux dans cet alphabet et rendent le
#: meme slug. Il reduit la surprise -- une etiquette dont la moitie des caracteres
#: disparaissait silencieusement en tirets --, la collision etant fermee par
#: l'empreinte differenciante de `write_profile`.
#:
#: L'espace et le tiret y sont **parce qu'ils sont ce que l'operateur tape**: les
#: refuser rendrait le mandat d'Egan inapplicable (« scanner maison default tiff »).
_LABEL_ALLOWED_PATTERN = re.compile(r"^[A-Za-z0-9 _-]+$")


#: **Le dossier de scan dont ce profil est issu** (`EPIC11-ARB-262`, tranche par
#: Egan le 2026-09-07). Chemin **relatif POSIX au dossier projet**, jamais absolu:
#: c'est ce que `scan_ingest.ScanIngestReport.scans_dir` porte deja.
#:
#: **Ce qu'il ferme, et il vient d'un constat de terrain** -- Egan, verbatim: « Le
#: scan de la page de calibration apparait en non declare alors que je l'ai importe
#: au projet. » Avant lui, rien sur le disque ne reconnaissait un scan de mire: ni le
#: manifeste (que `calibrer_la_chaine` ne touche pas), ni le dossier de scan (qui ne
#: porte que la copie du raster), ni le profil -- dont ni `chain_id` (condensat de dpi
#: DECLARE, format et tags scanner) ni `source_page_id` (derive de la FEUILLE) ne
#: nomment un dossier. L'inventaire montrait donc, sur tout projet calibre, un faux
#: orphelin PERMANENT: une mire n'est jamais reconstruite en lot.
#:
#: **C'est de l'IDENTITE, pas de la ressemblance** (`CLAUDE.md`, regle 6). Les trois
#: heuristiques disponibles -- un fragment de nom, l'absence d'`ingest.json`, une page
#: unique -- ecarteraient un vrai lot de planches, c'est-a-dire rendraient invisibles
#: des images qui pesent sur le disque. Le profil, lui, NOMME son dossier.
#:
#: **Ce qu'il ne repare pas, dit plutot que tu**: les projets DEJA calibres. Le champ
#: s'ecrit a la calibration; rien ne relie retroactivement un dossier de scan a un
#: profil ecrit avant lui. Un projet existant garde son faux orphelin jusqu'a une
#: recalibration.
SCAN_DIR_FIELD = "scan_dir"

#: Champs optionnels, avec leur defaut de relecture (fusion pure). Un champ
#: absent complete son defaut; un champ present reste ce qu'il est.
#:
#: `witness_raw_bgr` n'y figure **pas**, et c'est delibere: son defaut est son
#: **absence**. Un profil ecrit avant la story 5.23, ou dont la page de calibration ne
#: porte pas de bandeau de temoins (`patches-14-v3`), n'a rien mesure -- et un champ
#: present-mais-vide dirait « mesure, aucun temoin trouve », qui est un autre fait, ecrit
#: sous un autre motif au manifeste (`raw_divergence_witness_band_not_printed` contre
#: `raw_divergence_no_calibration_sheet`). Le remplir d'un defaut vide a la relecture
#: ferait reecrire ce vide dans le fichier au premier aller-retour, et la distinction
#: serait perdue en silence. Les consommateurs passent donc par
#: `witness_raw_of_document`, qui rend une suite vide sans inventer de champ.
#: `label` et `comment` y figurent **avec la chaine vide pour defaut**, et c'est ce qui
#: rend la retrocompatibilite mecanique plutot que declarative: un profil ecrit avant
#: l'AC 8quater ne porte ni l'un ni l'autre, et la fusion pure les lui donne sans un
#: refus. Ils sont l'inverse exact de `witness_raw_bgr`: la ou l'absence d'une mesure
#: est un **fait distinct** d'une mesure vide, l'absence d'etiquette et une etiquette
#: vide disent la meme chose -- « l'operateur n'a rien nomme ».
_OPTIONAL_DEFAULTS: dict[str, Any] = {
    "acceptance": {},
    LABEL_FIELD: "",
    COMMENT_FIELD: "",
    SCAN_DIR_FIELD: "",
}


class ProfileReadError(Exception):
    """Base des erreurs de lecture/ecriture d'un profil de chaine."""


class ProfileNotFoundError(ProfileReadError):
    """Aucun profil pour cette chaine dans le projet.

    Ce n'est pas une faute: c'est le cas d'`AC 3` -- projet recu sans son
    profil, machine nouvelle --, et l'appelant repond par l'invitation a
    regenerer ou a charger depuis le disque, jamais par un echec de commande.
    """


class ProfileValidationError(ProfileReadError):
    """Le document de profil ne satisfait pas le schema. Rien n'est ecrit."""


def slugify_label(label: str) -> str:
    """Le nom de fichier derive d'une etiquette libre. Leve si elle n'en nomme aucun.

    La recette, et chaque etape ferme une facon de perdre le nom de l'operateur:

    * les accents sont **deplies** (`NFKD`) puis leurs signes retires, donc « Ete » et
      « Ete » nomment le meme fichier au lieu d'en nommer deux dont un illisible;
    * tout caractere hors de :data:`_LABEL_ALLOWED_PATTERN` est **refuse** et non plus
      remplace par un tiret (`EPIC5-ARB-99`, geste 1). Le remplacement etait une
      politesse couteuse: `"HP ENVY /4520/"` devenait `hp-envy-4520` sans que rien ne
      le dise, et `../../evade` devenait `evade` -- neutralise, certes, mais l'operateur
      n'apprenait jamais que son etiquette n'etait pas celle qu'il avait tapee;
    * les espaces et tirets restants deviennent un tiret unique, les tirets de bord sont
      retires: c'est ce qui rend `"scanner maison default tiff"` lisible en
      `scanner-maison-default-tiff`;
    * une etiquette dont il ne reste rien (`'- _ -'`) est **refusee**, jamais remplacee
      en silence par le `chain_id`: l'operateur a demande un nom, il doit apprendre que
      celui-la n'en est pas un.

    **Elle reste non injective apres tout cela, et c'est assume**: `"HP Envy 4520"` et
    `"hp envy 4520"` rendent tous deux `hp-envy-4520`. Aucune recette de slug lisible ne
    ferme cette classe -- c'est `write_profile` qui la ferme, en refusant d'ecrire deux
    chaines de scan differentes dans un meme fichier (`EPIC5-ARB-99`, gestes 3 et 4).

    Elle est **refusee** plutot que **tronquee** au-dela de `CANONICAL_ID_MAX_LENGTH`.
    Tronquer ferait porter le meme nom de fichier a deux etiquettes distinctes qui
    partagent leur debut -- donc ecraser le premier profil par le second, en silence,
    sur exactement le geste que cette AC existe pour rendre fiable.
    """
    if not isinstance(label, str):
        raise ProfileValidationError(
            f"Etiquette de profil invalide: {type(label).__name__}, chaine attendue.")
    deplie = unicodedata.normalize("NFKD", label)
    sans_signes = "".join(
        caractere for caractere in deplie if not unicodedata.combining(caractere))
    # Une etiquette **vide** ne passe pas par ici mais par le refus 'nommable' plus
    # bas: elle ne porte aucun caractere refuse, elle ne porte rien.
    if sans_signes and not _LABEL_ALLOWED_PATTERN.fullmatch(sans_signes):
        refuses = sorted({caractere for caractere in sans_signes
                          if not _LABEL_ALLOWED_PATTERN.fullmatch(caractere)})
        raise ProfileValidationError(
            f"Etiquette de profil portant des caracteres refuses: {label!r} "
            f"({', '.join(repr(caractere) for caractere in refuses)}). Une etiquette "
            "nomme un fichier: lettres, chiffres, espace, tiret et souligne "
            "seulement. Les remplacer en silence par des tirets donnerait a "
            "l'operateur un nom de fichier qu'il n'a pas demande.")
    slug = _LABEL_SLUG_DROP_PATTERN.sub("-", sans_signes.lower()).strip("-")
    if not slug:
        raise ProfileValidationError(
            f"Etiquette de profil sans aucun caractere nommable: {label!r}. Un nom de "
            "fichier se derive de lettres et de chiffres; remplacer une etiquette vide "
            "par l'identite de chaine ferait taire la demande de l'operateur.")
    if len(slug) > CANONICAL_ID_MAX_LENGTH:
        raise ProfileValidationError(
            f"Etiquette de profil trop longue: son nom de fichier '{slug}' ferait "
            f"{len(slug)} caracteres, au plus {CANONICAL_ID_MAX_LENGTH} sont admis. "
            "Elle est refusee et non raccourcie: deux etiquettes distinctes partageant "
            "leur debut porteraient sinon le meme fichier, et la seconde ecraserait la "
            "premiere sans un mot.")
    return slug


def profile_file_stem(document) -> str:
    """Le nom de fichier d'un profil: son etiquette si elle existe, sinon son `chain_id`.

    C'est le **seul** endroit ou l'etiquette a un effet mecanique, et le repli sur le
    `chain_id` est ce qui garde un profil non etiquete identique a ce que la story 5.22
    ecrivait. Ce n'est pas une cle de resolution: personne ne retrouve un profil par ce
    nom -- il se designe par son chemin (`io/profile_designation`).
    """
    if not isinstance(document, dict):
        raise ProfileValidationError(
            f"Document de profil invalide: {type(document).__name__} attendu "
            "dictionnaire.")
    etiquette = document.get(LABEL_FIELD) or ""
    if isinstance(etiquette, str) and etiquette.strip():
        return slugify_label(etiquette)
    if "chain_id" not in document:
        raise ProfileValidationError(
            "Document de profil sans 'chain_id' ni etiquette: il ne peut nommer "
            "aucun fichier.")
    return document["chain_id"]


def profile_path_for_document(project_dir: str | Path, document) -> Path:
    """Le chemin qu'un document occupe dans un projet, **etiquette comprise**.

    A preferer partout a `profile_path(project_dir, document["chain_id"])`: depuis l'AC
    8quater les deux ne coincident plus des que l'operateur a nomme son profil, et
    recomposer le chemin depuis l'identite ferait pointer l'entree de manifest sur un
    fichier qui n'existe pas.
    """
    return profile_path(project_dir, profile_file_stem(document))


def _validate_label_and_comment(document: dict) -> None:
    """Refuser une etiquette ou un commentaire qui ne peut pas etre stocke tel quel.

    Quatre refus, chacun pour une perte silencieuse mesurable:

    * autre chose qu'une chaine -- un nombre ou une liste finirait recopie dans
      l'entree de manifest sous un champ dit textuel;
    * une etiquette portant un saut de ligne: elle est destinee a etre **lue** (nom de
      fichier, survol GUI), et un retour chariot y coupe l'affichage en deux;
    * une etiquette qui ne nomme aucun fichier, ou dont le nom serait tronque
      (`slugify_label` porte les deux motifs);
    * l'un ou l'autre ressemblant a un **chemin absolu**: la garde de portabilite du
      manifest v2 refuserait l'entree autoportante, et ce refus-la n'est qu'un
      avertissement depuis la revue de 5.22 -- la trace disparaitrait donc en silence.
    """
    etiquette = document.get(LABEL_FIELD, "")
    commentaire = document.get(COMMENT_FIELD, "")
    for champ, valeur in ((LABEL_FIELD, etiquette), (COMMENT_FIELD, commentaire)):
        if not isinstance(valeur, str):
            raise ProfileValidationError(
                f"Champ '{champ}' de type invalide dans le profil: "
                f"{type(valeur).__name__}, str attendu.")
        if _MANIFEST_ABSOLUTE_PATH_PATTERN.match(valeur):
            raise ProfileValidationError(
                f"Champ '{champ}' ressemblant a un chemin absolu: {valeur!r}. Le "
                "contrat v2 les interdit partout dans le manifest, ou ce champ est "
                "recopie; l'accepter ici ferait perdre l'entree autoportante du profil "
                "sans autre trace qu'un avertissement.")
    if "\n" in etiquette or "\r" in etiquette:
        raise ProfileValidationError(
            f"Etiquette de profil sur plusieurs lignes: {etiquette!r}. Elle nomme un "
            "fichier et se lit au survol: un saut de ligne y coupe l'affichage.")
    if etiquette.strip():
        slugify_label(etiquette)
    if len(commentaire) > COMMENT_MAX_LENGTH:
        raise ProfileValidationError(
            f"Commentaire de profil trop long: {len(commentaire)} caracteres, au plus "
            f"{COMMENT_MAX_LENGTH}. Il est recopie dans le manifest, relu a chaque "
            "commande.")


def normaliser_le_dossier_de_scan(valeur: Any) -> str:
    """La forme d'un `scan_dir` que l'inventaire peut APPARIER, ou `""` s'il n'y en a
    aucune.

    **C'est le manque que la revue du 2026-09-07 a mesure (finding `B1`), et c'etait
    une NORMALISATION qui manquait, pas un refus de plus.**
    :func:`dossiers_de_scan_declares` comparait des chaines BRUTES a
    `ObjetInventorie.chemin`, qui sort de `Path.relative_to(...).as_posix()` -- donc
    d'un cote normalise, et d'un seul. Cinq ecritures d'un meme dossier passaient la
    garde d'ecriture et ne s'appariaient a rien, si bien que le faux orphelin
    d'`EPIC11-ARB-262` revenait sans un mot **sur un profil que la garde venait de
    declarer valide**. Mesure du jour, sur le raster reel du depot et le parcours
    entier (`scan_calibrate.calibrer_la_chaine`), la barre oblique finale etant le seul
    caractere ajoute:

    ```
    'scans/<mire>'    -> orphelins=[]         calibrations=[la mire]
    'scans/<mire>/'   -> orphelins=[la mire]  calibrations=[]
    './scans/<mire>'  -> orphelins=[la mire]  calibrations=[]
    'scans//<mire>'   -> orphelins=[la mire]  calibrations=[]
    'scans/./<mire>'  -> orphelins=[la mire]  calibrations=[]
    ```

    **Pourquoi normaliser plutot que refuser davantage, et c'est mesure**:
    :func:`_validate_scan_dir` n'est appelee que par :func:`write_profile`. Le chemin de
    LECTURE ne la traverse jamais. Un refus de plus n'aurait donc rien ferme d'un profil
    deja ecrit -- edite a la main, produit par une version anterieure, recopie d'un
    autre projet --, la ou la normalisation apparie les cinq formes du meme dossier a
    l'unique noeud qui le porte.

    **Ce qu'elle ne fait PAS, dit plutot que tu**: elle ne RESOUT pas les remontees.
    `'scans/x/../mire'` rend `""` -- « ne declare rien » -- plutot que `'scans/mire'`.
    Une resolution lexicale mentirait des qu'un lien symbolique est en jeu, et `..` est
    de toute facon refuse a l'ecriture pour son propre motif: le champ designerait un
    dossier hors du projet, que l'inventaire ne balaie pas.

    Elle ne refuse pas non plus le **lecteur Windows** (`C:/scans`): sur un systeme de
    fichiers POSIX, `C:` est un nom de dossier legal, et l'apparier serait une identite
    et non une ressemblance. C'est la garde d'ecriture qui l'oppose, et pour un autre
    motif que l'appariement -- la portabilite du manifeste v2.
    """
    if not isinstance(valeur, str) or not valeur:
        return ""
    # L'antislash **avant** la decomposition, et c'est necessaire: `PurePosixPath` le
    # tient pour un caractere de nom ordinaire, donc `'scans\\mire'` lui parait un
    # segment unique parfaitement relatif.
    if "\\" in valeur:
        return ""
    chemin = PurePosixPath(valeur)
    if chemin.is_absolute():
        return ""
    segments = chemin.parts
    # `'.'`, `'./'` et `'.//.'` decomposent en RIEN: ils designent le dossier projet
    # lui-meme, qui n'est aucun des noeuds de l'inventaire. Ils ne declarent donc rien,
    # et c'est ce que la chaine vide dit.
    if not segments or ".." in segments:
        return ""
    return "/".join(segments)


def _validate_scan_dir(document: dict) -> None:
    """Refuser un `scan_dir` qui ne serait pas un chemin relatif POSIX au projet.

    Cinq refus, et chacun ferme une perte mesurable:

    * autre chose qu'une chaine -- le champ est relu par `project_inventory` et
      compare a un chemin relatif; un nombre ou une liste y ferait une comparaison
      toujours fausse, donc un faux orphelin qui revient sans un mot;
    * un chemin **absolu**: c'est l'invariant de portabilite v2, et le profil est
      recopie dans l'entree autoportante du manifeste. Un projet copie sur une autre
      machine porterait un `scan_dir` qui ne designe rien;
    * un chemin qui **remonte** (`..`): il designerait un dossier hors du projet, que
      l'inventaire ne balaie pas -- et l'ecrire donnerait a croire qu'il le fait;
    * un **antislash** : le champ est declare POSIX. Un separateur Windows ne
      s'apparierait jamais au chemin en barres obliques que `_relatif` rend, et le
      faux orphelin reviendrait exactement sur les machines ou personne ne le mesure;
    * une valeur non vide qui **ne nomme aucun dossier** une fois normalisee -- `'.'`,
      `'./'`, `'.//.'`. C'est le residu que :func:`normaliser_le_dossier_de_scan` ne
      peut pas reparer, et il est du meme genre que le champ vide a une difference
      pres, qui est tout: un champ **absent ou vide** dit « aucune declaration n'a ete
      faite » et c'est un fait legitime (tout profil ecrit avant le 2026-09-07);
      `'.'` dit « je declare le dossier projet », qui n'est aucun noeud de
      l'inventaire. Le premier est accepte, le second refuse.

    **Cette garde ne suffit pas a elle seule, et il faut le savoir en la lisant**: elle
    n'est appelee que par :func:`write_profile`. Un profil deja sur le disque ne la
    traverse jamais. C'est :func:`normaliser_le_dossier_de_scan`, du cote LECTURE, qui
    tient l'appariement -- la garde ne fait que refuser d'ecrire ce qu'aucune
    normalisation ne rattraperait.
    """
    valeur = document.get(SCAN_DIR_FIELD, "")
    if not isinstance(valeur, str):
        raise ProfileValidationError(
            f"Champ '{SCAN_DIR_FIELD}' de type invalide dans le profil: "
            f"{type(valeur).__name__}, str attendu.")
    if not valeur:
        return
    if _MANIFEST_ABSOLUTE_PATH_PATTERN.match(valeur):
        raise ProfileValidationError(
            f"Champ '{SCAN_DIR_FIELD}' absolu: {valeur!r}. Il designe un dossier DANS "
            "le projet, relativement a lui: un chemin absolu rendrait le profil "
            "inutilisable des que le projet change de machine.")
    if "\\" in valeur:
        raise ProfileValidationError(
            f"Champ '{SCAN_DIR_FIELD}' portant un antislash: {valeur!r}. Le champ est "
            "declare relatif POSIX; un separateur Windows ne s'apparierait a aucun "
            "chemin de l'inventaire.")
    if any(segment == ".." for segment in valeur.split("/")):
        raise ProfileValidationError(
            f"Champ '{SCAN_DIR_FIELD}' remontant hors du projet: {valeur!r}. "
            "L'inventaire ne balaie que le dossier projet: un chemin qui en sort "
            "designerait un dossier que rien ne lira jamais.")
    if not normaliser_le_dossier_de_scan(valeur):
        raise ProfileValidationError(
            f"Champ '{SCAN_DIR_FIELD}' ne nommant aucun dossier: {valeur!r}. Une fois "
            "normalise il ne reste aucun segment, c'est-a-dire le dossier projet "
            "lui-meme, qui n'est aucun objet de l'inventaire. Un champ ABSENT ou VIDE "
            "dit « aucune declaration », et il est accepte; celui-ci dit « je declare » "
            "et ne declare rien -- c'est le faux orphelin qui revient sans un mot.")


def documents_de_calibration(project_dir: str | Path) -> list[tuple[Path, dict]]:
    """Les profils ecrits sous `versions/calibration/`, lus et **jamais devines**.

    Le **balayage inverse** que `EPIC11-ARB-261` et `EPIC11-ARB-262` demandent tous
    les deux, ecrit **une seule fois** ici plutot que deux fois chez ses appelants:
    l'un cherche les profils d'une meme chaine, l'autre les dossiers de scan
    declares, et les deux partent du meme parcours.

    Un fichier illisible, non-JSON ou qui n'est pas un objet est **saute** en silence,
    exactement comme :func:`_chain_id_du_fichier` le fait pour la meme raison: on ne
    peut rien prouver de lui, donc on n'en conclut rien. Un dossier absent rend une
    liste vide -- un projet non calibre n'est pas une panne.

    L'ordre est celui du tri des noms de fichiers: il est **stable** entre deux
    lectures, ce qu'`iterdir` seul ne garantit pas, et un appelant qui montre « cette
    chaine porte deja le profil X » ne doit pas nommer un profil different a chaque
    passage.
    """
    dossier = Path(project_dir) / VERSIONS_DIRNAME / CALIBRATION_DIRNAME
    if not dossier.is_dir():
        return []
    trouves: list[tuple[Path, dict]] = []
    for chemin in sorted(dossier.glob("*.json")):
        try:
            document = json.loads(chemin.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(document, dict):
            trouves.append((chemin, document))
    return trouves


def profils_de_la_chaine(project_dir: str | Path, chain_id: str) -> list[Path]:
    """Les fichiers de profil du projet dont le `chain_id` vaut celui-ci.

    C'est le **balayage inverse** d'`EPIC11-ARB-261`, et il ne demande aucune donnee
    neuve: le document PORTE son `chain_id` depuis la story 5.22, et
    :func:`_chain_id_du_fichier` le relit deja -- c'est ce que `write_profile` emploie
    pour refuser d'ecraser le fichier d'une AUTRE chaine. Il manquait seulement le
    sens inverse: quels fichiers portent CETTE chaine.

    Ce que le regime ferme, et c'est le constat de la revue: depuis que le nom d'un
    profil suit la precedence *saisie -> libelle du QR -> identite de chaine*, la
    collision se juge sur le **chemin** vise et plus sur la **chaine**. Recalibrer une
    chaine deja calibree sous un libelle different ecrivait donc un second fichier,
    l'ancien devenait orphelin sans un mot, et l'ecran annoncait « nouveau profil » sur
    ce qui est une recalibration.

    **Ce n'est pas un doublon**: deux dpi ou deux scanners rendent deux `chain_id`
    reellement differents, et deux fichiers y sont corrects
    (`scan_chain.derive_chain_id`). Cette fonction ne rend donc jamais que ce qui est
    LITTERALEMENT la meme chaine.

    Elle ne decide rien: elle **rend**, l'appelant avertit et propose les deux issues
    (`EPIC11-ARB-89`: jamais un blocage sec, jamais un ecrasement silencieux).
    """
    if not isinstance(chain_id, str) or not chain_id:
        return []
    return [chemin for chemin, document in documents_de_calibration(project_dir)
            if document.get("chain_id") == chain_id]


def dossiers_de_scan_declares(project_dir: str | Path) -> set[str]:
    """Les `scan_dir` que les profils de ce projet declarent, en relatif POSIX.

    C'est la moitie LECTURE d'`EPIC11-ARB-262`. Elle vit ici et non dans
    `project_inventory` parce que la forme du document de profil appartient a ce
    module: l'inventaire lit une declaration, il n'ouvre pas un schema.

    Les valeurs vides et non textuelles sont ecartees: un champ absent -- c'est-a-dire
    tout profil ecrit avant le 2026-09-07 -- ne declare rien, et ne doit surtout pas
    ecarter un dossier au hasard.

    **Chaque valeur est NORMALISEE avant d'entrer** (`normaliser_le_dossier_de_scan`),
    et c'est ce qui manquait au 2026-09-07: cette fonction comparait des chaines brutes
    a `ObjetInventorie.chemin`, qui sort d'un `as_posix()` -- normalise d'un seul cote.
    Cinq ecritures du meme dossier ne s'appariaient alors a rien. Ce qui sort d'ici est
    donc la forme que l'inventaire porte, jamais celle que l'operateur a tapee.

    **Ce que la normalisation ne fait pas, et il faut le lire ici**: elle ne rend pas
    l'appariement TOLERANT. Il reste une **identite** -- un dossier declare qui n'est
    pas exactement un objet de l'inventaire ne s'apparie a rien, y compris quand il est
    un descendant de l'un d'eux (`scans/2026/janvier` face au noeud `scans/2026`).
    C'est mesure, nomme et laisse ouvert: `deferred-work.md`, entree `ARB262-N1`.
    """
    declares: set[str] = set()
    for _chemin, document in documents_de_calibration(project_dir):
        normalise = normaliser_le_dossier_de_scan(document.get(SCAN_DIR_FIELD))
        if normalise:
            declares.add(normalise)
    return declares


def profile_path(project_dir: str | Path, chain_id: str) -> Path:
    """Le chemin canonique `versions/calibration/<radical>.json` d'un projet.

    `chain_id` y est un **radical de nom de fichier**, pas une cle: depuis l'AC 8quater
    c'est le slug de l'etiquette de l'operateur quand il en a donne une, et son identite
    de chaine sinon. `profile_path_for_document` fait ce choix; cette fonction ne fait
    que concatener.

    Ne cree rien: la distinction "le dossier n'existe pas encore" et "le
    fichier est absent" appartient a l'appelant.
    """
    return Path(project_dir) / VERSIONS_DIRNAME / CALIBRATION_DIRNAME / f"{chain_id}.json"


def _validate_chain_id(chain_id: str) -> None:
    """Refuser un `chain_id` hors du pattern schema et du budget de longueur.

    Le `chain_id` designe un nom de fichier sous `versions/`; le laisser porter
    un separateur ou une remontee de chemin ferait ecrire le profil hors du
    projet. C'est la garde avant la concatenation, pas une politesse de schema.
    """
    if (not isinstance(chain_id, str) or not chain_id
            or len(chain_id) > CANONICAL_ID_MAX_LENGTH
            or not _CHAIN_ID_PATTERN.fullmatch(chain_id)):
        raise ProfileValidationError(
            f"chain_id invalide: {chain_id!r}. Un identifiant de chaine "
            f"satisfait '{_CHAIN_ID_PATTERN.pattern}' et fait au plus "
            f"{CANONICAL_ID_MAX_LENGTH} caracteres: il designe un nom de "
            "fichier sous versions/.")


def _is_number(value: object) -> bool:
    """Est-ce un nombre JSON (int/float, jamais un booleen) ?"""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _nested_numbers(value: object) -> bool:
    """Une valeur de coefficient: un nombre, ou une liste (imbriquee) de nombres.

    Recursif par profondeur deux: chaque forme stocke soit un scalaire (les
    parametres de la forme Lab), soit une liste plate (les sorties d'ancrage),
    soit une liste de listes (matrices et entrees d'ancrage). La garde reste
    generique pour ne pas coupler `io/` a la liste des formes.
    """
    if isinstance(value, list):
        if not value:
            return False
        return all(
            _nested_numbers(item) if isinstance(item, list) else _is_number(item)
            for item in value)
    return _is_number(value)


def _coefficients_are_lists_of_numbers(value: object) -> bool:
    """Le bloc `coefficients` est un dictionnaire non vide de valeurs numeriques.

    Les cles dependent de la forme (`tone_anchors_in`, `chroma_matrix`, ...):
    c'est la partie qui vit cote couleur. Ici on garantit ce que `io/` peut
    garantir sans connaitre les formes: des nombres, jamais de dictionnaires,
    de booleens ou de chaines.
    """
    if not isinstance(value, dict) or not value:
        return False
    return all(_nested_numbers(item) for item in value.values())


# ---------------------------------------------------------------------------
# Forme du bloc `coefficients`, par forme de correction (correctif du 2026-08-17)
# ---------------------------------------------------------------------------
#
# Ce que `_coefficients_are_lists_of_numbers` garantit -- « des nombres, jamais
# de dictionnaires ni de booleens » -- ne dit **rien** des cles attendues ni des
# dimensions, et la couche 2 de la revue de 5.22 a mesure les deux consequences:
#
# * un profil externe ampute d'une cle etait **ecrit dans le projet** puis
#   levait un `KeyError` nu a la reconstruction; tout `scan` ulterieur de la
#   meme chaine replantait a l'identique -- le projet restait empoisonne, le
#   journal annoncant « profil reutilise » juste avant;
# * une `chroma_matrix` de dimension 1x2 au lieu de 2x2 passait la validation
#   **sans aucune erreur**, la commande rendait 0, et les pixels ecrits
#   s'ecartaient de 1,83 (sur `[0, 1]`) de ceux du profil sain. Un refus
#   nomme n'est pas un luxe ici: c'est la seule difference entre « rien n'a ete
#   ecrit » et « des frames fausses ont ete ecrites sans un mot ».
#
# La table vit **ici** et non cote couleur parce que `io/` reste pur (aucun
# import numpy/OpenCV, et `color_calibration` importe deja ce module: l'importer
# en retour serait un cycle). Le partage est celui du depot: `io/` porte la
# *forme* du document -- presence des cles, type, cardinal, rectangularite --,
# `color_calibration` porte le *sens* des nombres et reconstruit les tableaux.
# La derive entre les deux tables est epinglee par un test qui exige que les
# identifiants de forme d'ici soient exactement ceux de
# `color_calibration.CORRECTION_FORMS`.

#: Cardinaux de forme, lus au registre plutot qu'ecrits en litteral dans la
#: table: trois canaux BGR, deux parametres d'affine par canal (gain, decalage),
#: deux axes de chroma (a*, b*).
CHANNEL_COUNT = 3
STAGE_A_PARAMETER_COUNT = 2
CHROMA_AXIS_COUNT = 2

#: Nombre minimal d'ancrages de la courbe de tonalite. Miroir de
#: `color_calibration.MIN_NEUTRAL_TONE_ANCHORS` (epingle par test): sur un
#: ancrage unique `np.interp` rend une **constante**, donc toute la page ecrasee
#: sur une clarte -- un resultat plausible, et donc non detecte.
MIN_TONE_ANCHOR_COUNT = 2

#: Identifiants des formes de correction, miroir de `color_calibration`. Ce
#: module ne peut pas les importer (cycle), et un test epingle l'egalite des
#: deux jeux de cles: une forme ajoutee cote couleur sans sa forme de document
#: ici doit rougir, jamais passer en silence.
CORRECTION_FORM_AFFINE_ID = "color-correction-affine-matrix-1"
CORRECTION_FORM_LAB_ID = "color-correction-lab-lightness-chroma-1"
CORRECTION_FORM_TONE_CHROMA_ID = "color-correction-tone-curve-chroma-1"


class _Shape:
    """Forme attendue d'une valeur de coefficient, sans aucun numpy.

    `kind` vaut `"scalar"` (un nombre), `"vector"` (une liste plate de nombres)
    ou `"matrix"` (une liste de lignes de meme largeur). `length` est le cardinal
    **exact** attendu, ou `None` quand il est libre -- auquel cas `min_length`
    porte le minimum. `width` est la largeur des lignes d'une matrice.
    """

    __slots__ = ("kind", "length", "width", "min_length")

    def __init__(self, kind: str, *, length: int | None = None,
                 width: int | None = None, min_length: int = 1) -> None:
        self.kind = kind
        self.length = length
        self.width = width
        self.min_length = min_length

    def describe(self) -> str:
        """Le libelle de la forme attendue, pour le message de refus."""
        if self.kind == "scalar":
            return "un nombre"
        cardinal = (str(self.length) if self.length is not None
                    else f"au moins {self.min_length}")
        if self.kind == "vector":
            return f"une liste plate de {cardinal} nombre(s)"
        return f"une liste de {cardinal} ligne(s) de {self.width} nombre(s)"


#: Cles attendues et forme de chacune, par `correction_form_id`. Les cles sont
#: exigees **exactement**: une manquante est le `KeyError` nu mesure, une en
#: trop est le signe d'un document d'une autre forme ou d'une autre version.
_COEFFICIENT_SHAPES: dict[str, dict[str, _Shape]] = {
    CORRECTION_FORM_AFFINE_ID: {
        "stage_a": _Shape("matrix", length=CHANNEL_COUNT,
                          width=STAGE_A_PARAMETER_COUNT),
        "stage_m": _Shape("matrix", length=CHANNEL_COUNT, width=CHANNEL_COUNT),
    },
    CORRECTION_FORM_LAB_ID: {
        "lightness_slope": _Shape("scalar"),
        "lightness_offset": _Shape("scalar"),
        "chroma_matrix": _Shape("matrix", length=CHROMA_AXIS_COUNT,
                                width=CHROMA_AXIS_COUNT),
        "chroma_offset": _Shape("vector", length=CHROMA_AXIS_COUNT),
    },
    CORRECTION_FORM_TONE_CHROMA_ID: {
        "tone_anchors_in": _Shape("matrix", width=CHANNEL_COUNT,
                                  min_length=MIN_TONE_ANCHOR_COUNT),
        "tone_anchors_out": _Shape("vector", min_length=MIN_TONE_ANCHOR_COUNT),
        "chroma_matrix": _Shape("matrix", length=CHROMA_AXIS_COUNT,
                                width=CHROMA_AXIS_COUNT),
    },
}

#: Cles dont les cardinaux sont **lies** au sein d'une forme. La courbe de
#: tonalite interpole `tone_anchors_out` sur `tone_anchors_in`: deux cardinaux
#: differents ne decrivent aucune courbe, et le laisser passer rendrait un
#: `ValueError` numpy nu au lieu d'un refus nomme avant toute ecriture.
_COEFFICIENT_LINKED_LENGTHS: dict[str, tuple[tuple[str, str], ...]] = {
    CORRECTION_FORM_TONE_CHROMA_ID: (("tone_anchors_in", "tone_anchors_out"),),
}


def _matches_shape(value: object, shape: _Shape) -> bool:
    """La valeur satisfait-elle la forme attendue ? Presence, type, cardinal."""
    if shape.kind == "scalar":
        return _is_number(value)
    if not isinstance(value, list):
        return False
    if shape.length is not None:
        if len(value) != shape.length:
            return False
    elif len(value) < shape.min_length:
        return False
    if shape.kind == "vector":
        return all(_is_number(item) for item in value)
    # Matrice: rectangulaire, chaque ligne de la largeur declaree. Une matrice
    # dentelee (`[[1, 0, 0], [0, 1]]`) est refusee ici plutot que de faire
    # lever un `inhomogeneous shape` a numpy, hors de toute garde.
    return all(
        isinstance(row, list) and len(row) == shape.width
        and all(_is_number(item) for item in row)
        for row in value)


def _validate_coefficients_shape(correction_form_id: str,
                                 coefficients: dict) -> None:
    """Refuser un bloc `coefficients` qui ne colle pas a sa forme declaree.

    Verifie l'identifiant de forme, l'egalite **exacte** des cles, la forme de
    chaque valeur et les cardinaux lies. Ne reconstruit aucun objet: `io/` ne
    connait ni numpy ni le sens des nombres, seulement la forme du document.
    """
    expected = _COEFFICIENT_SHAPES.get(correction_form_id)
    if expected is None:
        raise ProfileValidationError(
            f"Forme de correction inconnue dans le profil: "
            f"{correction_form_id!r}. Formes connues: "
            f"{', '.join(sorted(_COEFFICIENT_SHAPES))}. Un profil dont la forme "
            "est devinee serait applique avec des coefficients mal interpretes.")
    missing = sorted(set(expected) - set(coefficients))
    if missing:
        raise ProfileValidationError(
            f"Coefficients incomplets pour la forme '{correction_form_id}': "
            f"cle(s) manquante(s) {', '.join(missing)}. Sans ce refus, la cle "
            "absente sort en KeyError nue a la reconstruction, apres que le "
            "profil a ete ecrit dans le projet.")
    extra = sorted(set(coefficients) - set(expected))
    if extra:
        raise ProfileValidationError(
            f"Coefficients etrangers a la forme '{correction_form_id}': "
            f"{', '.join(extra)}. Des coefficients d'une autre forme dans un "
            "document declarant celle-ci seraient silencieusement ignores.")
    for key, shape in expected.items():
        if not _matches_shape(coefficients[key], shape):
            raise ProfileValidationError(
                f"Coefficient '{key}' de forme invalide pour "
                f"'{correction_form_id}': {shape.describe()} attendu(e). Une "
                "dimension fausse ne leve pas toujours a l'application -- une "
                "chroma 1x2 au lieu de 2x2 ecrit des pixels ecartes de 1,83 "
                "sans le moindre message.")
    for first, second in _COEFFICIENT_LINKED_LENGTHS.get(correction_form_id, ()):
        if len(coefficients[first]) != len(coefficients[second]):
            raise ProfileValidationError(
                f"Cardinaux lies incoherents pour '{correction_form_id}': "
                f"'{first}' porte {len(coefficients[first])} element(s) et "
                f"'{second}' {len(coefficients[second])}. Les deux decrivent la "
                "meme courbe, point par point.")


# ---------------------------------------------------------------------------
# Story 5.23 (mesure du 2026-08-18) : le profil porte les mesures BRUTES de ses
# temoins, donc il redevient autoportant pour la divergence brute a brute
# ---------------------------------------------------------------------------
#
# Ce que la chaine complete a mesure sur les vrais scans d'Egan le 2026-08-18: page de
# calibration lue (130 pastilles de treillis), profil ecrit, planches corrigees -- et le
# manifeste rendant `raw_divergence = {"reason": "raw_divergence_no_calibration_sheet",
# "mean_raw_de76": null, "paired_value_ids": []}`. La mesure centrale d'`EPIC5-ARB-82`
# n'avait pas lieu.
#
# La cause tient en une phrase: le fichier de profil portait ses coefficients et sa
# provenance, **pas la mesure de ses pastilles temoins**. La comparaison brute a brute ne
# fonctionnait donc que si les deux feuilles etaient dans la **meme passe de scan**, ce
# qui est exactement le regime que la calibration par chaine (`EPIC5-ARB-80`) existe pour
# supprimer -- une page de calibration se scanne une fois, les planches ensuite.
#
# Le champ est **optionnel** et sa forme est fixee ici:
#
#     "witness_raw_bgr": [["neutral-065", [0.245, 0.248, 0.251]], ...]
#
# * une **liste de couples** `[value_id, [b, g, r]]` et non un objet: l'appariement se
#   fait par identifiant de valeur, jamais par position (famille `M33` / `M25`, sept
#   occurrences payees), et la liste triee par identifiant rend l'ordre du document
#   independant de la graine de hachage du processus qui l'ecrit;
# * ordre des canaux **BGR**, comme partout dans la chaine couleur du depot
#   (`measured_raw` d'`evaluate_page_acceptance`, `witness_raw_mapping`);
# * echelle **sRGB encode normalise `[0, 1]`**, la meme que `sample_patches` -- jamais
#   des entiers 8 bits: quantifier a 1/255 ici perdrait la moyenne des repliques;
# * precision de serialisation **fixee** a `WITNESS_RAW_DECIMALS` decimales, ce qui rend
#   l'ecriture idempotente octet pour octet (arrondir un nombre deja arrondi ne le
#   deplace pas) et laisse 2,6e-4 pas de quantification 8 bits de marge -- trois ordres
#   de grandeur sous le bruit de mesure d'un scanner a plat.

#: Decimales conservees par la serialisation des mesures de temoins.
WITNESS_RAW_DECIMALS = 6

#: Composantes d'une mesure de temoin: **B, G, R**, dans cet ordre.
WITNESS_RAW_COMPONENT_COUNT = CHANNEL_COUNT

#: Bornes de l'echelle des mesures (sRGB encode normalise). Une mesure hors de ces
#: bornes n'est pas une mesure de pastille: c'est un tableau reste en 8 bits, ou une
#: valeur inventee. La refuser a l'ecriture evite d'ecrire dans le projet un profil dont
#: la divergence brute serait chiffree en dE76 de nulle part.
WITNESS_RAW_MIN = 0.0
WITNESS_RAW_MAX = 1.0


def _finite_number(value: object) -> bool:
    """Un nombre JSON fini (`nan` et `inf` exclus, booleens exclus)."""
    return _is_number(value) and math.isfinite(float(value))


def _validate_witness_band_reason(value: object) -> None:
    """Refuser un motif de bandeau mal forme. Rien n'est ecrit.

    Le champ est **absent** quand il n'y a rien a signaler -- c'est deja la reponse.
    Une chaine **vide** dirait « un motif, mais lequel »: elle est refusee, comme la
    liste vide de `witness_raw_bgr` l'est pour la meme raison.
    """
    if not isinstance(value, str) or not value:
        raise ProfileValidationError(
            f"Champ '{WITNESS_BAND_REASON_FIELD}' invalide: chaine non vide attendue. "
            "L'absence du champ dit deja « rien a signaler »; une chaine vide dirait "
            "« un motif, mais lequel ».")


def witness_band_reason_of_document(document: Mapping[str, Any]) -> str:
    """Le motif consigne, ou la chaine vide. **Point de lecture unique.**

    Rend `""` quand le champ est absent: un profil ecrit avant `EPIC5-ARB-104` se
    relit sans refus, et dire « rien a signaler » de lui est vrai de lui.
    """
    return str(document.get(WITNESS_BAND_REASON_FIELD, "") or "")


def _validate_witness_raw(entries: object) -> None:
    """Refuser un bloc `witness_raw_bgr` mal forme. Rien n'est ecrit.

    Cinq refus, chacun pour une faussete qui se lirait sinon comme une mesure:

    * autre chose qu'une liste -- un objet `{value_id: triplet}` serait accepte par
      `json` et perdrait l'ordre documente;
    * liste **vide** presente: le document dirait « mesure, rien trouve » la ou l'absence
      du champ dit « pas mesure ». Les deux se distinguent au manifeste (motifs
      `raw_divergence_no_calibration_sheet` et `raw_divergence_witness_band_not_printed`)
      et cette distinction ne tient que si le document ne peut pas les confondre;
    * couple mal forme, identifiant vide ou triplet d'un autre cardinal;
    * composante non finie ou hors de `[0, 1]`;
    * identifiants non **strictement croissants** -- un doublon ferait dependre le
      resultat de la derniere occurrence lue, et un ordre libre ferait dependre le
      fichier de la graine de hachage.
    """
    if not isinstance(entries, list):
        raise ProfileValidationError(
            f"Champ '{WITNESS_RAW_FIELD}' invalide: liste de couples "
            f"[value_id, [b, g, r]] attendue, recu {type(entries).__name__}.")
    if not entries:
        raise ProfileValidationError(
            f"Champ '{WITNESS_RAW_FIELD}' present mais vide. L'absence du champ dit "
            "« ces temoins n'ont pas ete mesures », une liste vide dirait « mesures, "
            "aucun temoin trouve »: les deux s'ecrivent differemment au manifeste, "
            "donc le document ne doit pas pouvoir les confondre.")
    precedent: str | None = None
    for entry in entries:
        if (not isinstance(entry, (list, tuple)) or len(entry) != 2
                or not isinstance(entry[0], str) or not entry[0]):
            raise ProfileValidationError(
                f"Entree de '{WITNESS_RAW_FIELD}' invalide: un couple "
                f"[value_id, [b, g, r]] est attendu, recu {entry!r}.")
        value_id, triplet = entry
        if (not isinstance(triplet, (list, tuple))
                or len(triplet) != WITNESS_RAW_COMPONENT_COUNT
                or not all(_finite_number(item) for item in triplet)):
            raise ProfileValidationError(
                f"Mesure du temoin '{value_id}' invalide: "
                f"{WITNESS_RAW_COMPONENT_COUNT} nombres finis (ordre BGR) attendus, "
                f"recu {triplet!r}.")
        if any(not (WITNESS_RAW_MIN <= float(item) <= WITNESS_RAW_MAX)
               for item in triplet):
            raise ProfileValidationError(
                f"Mesure du temoin '{value_id}' hors echelle: "
                f"{list(triplet)!r}, attendu dans [{WITNESS_RAW_MIN}, "
                f"{WITNESS_RAW_MAX}] (sRGB encode normalise, ordre BGR). Une mesure "
                "restee en 8 bits chiffrerait une divergence de nulle part.")
        if precedent is not None and value_id <= precedent:
            raise ProfileValidationError(
                f"Temoins de '{WITNESS_RAW_FIELD}' non tries strictement: "
                f"'{value_id}' apres '{precedent}'. Un doublon ferait dependre la "
                "mesure de la derniere occurrence lue, et un ordre libre ferait "
                "dependre le fichier de la graine de hachage du processus.")
        precedent = value_id


def witness_raw_to_document(
        witnesses) -> list:
    """Forme document des mesures de temoins: liste triee, arrondie, ordre BGR.

    Prend une suite de couples `(value_id, (b, g, r))` ou un mapping equivalent, et rend
    la **seule** forme que ce module ecrit. La recette de tri et d'arrondi vit ici et pas
    cote couleur: deux redactions de la meme recette divergeraient, et le symptome serait
    un fichier qui cesse d'etre reproductible octet pour octet sans que rien ne le dise.

    Une entree vide rend une liste vide, que l'appelant **n'ecrit pas** dans le document
    (`_validate_witness_raw` la refuserait): rendre `[]` plutot que lever laisse
    l'appelant traiter « pas de bandeau » comme le non-evenement qu'il est.
    """
    couples = (list(witnesses.items()) if isinstance(witnesses, dict)
               else [tuple(item) for item in witnesses])
    return [
        [value_id, [round(float(component), WITNESS_RAW_DECIMALS)
                    for component in triplet]]
        for value_id, triplet in sorted(couples, key=lambda item: item[0])
    ]


def witness_raw_of_document(document) -> tuple:
    """Les mesures de temoins d'un document de profil, ou une suite vide.

    Le point de lecture unique: il vaut pour un profil qui porte le champ comme pour un
    profil ecrit avant qu'il existe, **sans** que la relecture ait a inventer un champ
    absent -- c'est ce qui garde « pas mesure » distinct de « mesure, rien trouve ».
    """
    if not isinstance(document, dict):
        raise ProfileValidationError(
            f"Document de profil invalide: {type(document).__name__} attendu "
            "dictionnaire.")
    return witness_raw_from_document(document.get(WITNESS_RAW_FIELD, ()))


def witness_raw_from_document(entries) -> tuple:
    """Relire les mesures de temoins d'un document: suite de couples immuables.

    Rend une **suite triee de couples** et non un dictionnaire: l'objet qui la porte cote
    couleur (`LotCorrection`) est `frozen`, et l'ordre d'iteration ne doit dependre de
    rien d'autre que des identifiants.
    """
    return tuple(
        (value_id, tuple(float(component) for component in triplet))
        for value_id, triplet in sorted(
            ((entry[0], entry[1]) for entry in entries or ()),
            key=lambda item: item[0]))


def validate_profile_document(document: dict) -> dict:
    """Valider et normaliser un document de profil. Rend une copie complete.

    Verifie les champs requis (presence + type), le pattern du `chain_id`, la
    version de schema, la forme generique des coefficients **et** leur forme
    propre a `correction_form_id` (cles exactes, cardinaux, rectangularite).
    Remplit les champs optionnels absents par leur defaut et rend une copie,
    sans jamais modifier l'entree.

    C'est la seule porte avant l'ecriture (`write_profile` valide puis ecrit):
    un profil externe mal forme est donc refuse **avant** d'entrer dans le
    projet, et non consigne puis rejoue en panne a chaque scan suivant.
    """
    if not isinstance(document, dict):
        raise ProfileValidationError(
            f"Document de profil invalide: {type(document).__name__} attendu "
            "dictionnaire.")
    for field, expected in _REQUIRED_FIELDS.items():
        if field not in document:
            raise ProfileValidationError(
                f"Champ requis manquant dans le profil: '{field}'.")
        if not isinstance(document[field], expected):
            raise ProfileValidationError(
                f"Champ '{field}' de type invalide dans le profil: "
                f"{type(document[field]).__name__}, {expected.__name__} attendu.")
    if document["schema_version"] != PROFILE_SCHEMA_VERSION:
        raise ProfileValidationError(
            f"Version de schema de profil inconnue: "
            f"{document['schema_version']}, attendue {PROFILE_SCHEMA_VERSION}. "
            "Inventer des champs d'une version plus recente produirait une "
            "correction que le fichier ne porte pas.")
    _validate_chain_id(document["chain_id"])
    if not _coefficients_are_lists_of_numbers(document["coefficients"]):
        raise ProfileValidationError(
            "Champ 'coefficients' invalide: des listes de nombres non vides "
            "sont attendues, jamais de dictionnaires ni de booleens.")
    _validate_coefficients_shape(
        document["correction_form_id"], document["coefficients"])
    if document["read_patch_count"] < 0 or document["retained_patch_count"] < 0:
        raise ProfileValidationError(
            "Cardinaux negatifs: read_patch_count et retained_patch_count sont "
            "des comptages, jamais negatifs.")
    if WITNESS_RAW_FIELD in document:
        _validate_witness_raw(document[WITNESS_RAW_FIELD])
    if WITNESS_BAND_REASON_FIELD in document:
        _validate_witness_band_reason(document[WITNESS_BAND_REASON_FIELD])
    _validate_label_and_comment(document)
    _validate_scan_dir(document)
    merged = dict(_OPTIONAL_DEFAULTS)
    merged.update(document)
    return merged


def serialize_profile(document: dict) -> str:
    """Serialisation JSON deterministe, octet pour octet (AC 1).

    Meme recette que `io/extraction_manifest._serialize`: `sort_keys=True`
    rend l'idempotence verifiable byte a byte, et la fin de ligne finale
    identifie un fichier ecrit par ce module.
    """
    return json.dumps(document, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _atomic_write_profile(path: Path, payload: str) -> None:
    """Temporaire dans le dossier projet, puis `os.replace`.

    La validation a deja eu lieu en memoire (`validate_profile_document`),
    donc aucun ecart JSON-schema n'est possible a l'ecriture; l'atomicite
    reste celle du pattern de `extraction_manifest` -- un echec ne laisse ni
    fichier tronque ni temporaire.
    """
    project_dir = path.parent
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=project_dir,
        prefix=f".{path.name}.", suffix=".tmp", delete=False)
    temp_path = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as error:
        temp_path.unlink(missing_ok=True)
        raise ProfileReadError(
            f"Ecriture du profil impossible: {error}. Le profil precedent est "
            "intact.") from error
    try:
        os.replace(temp_path, path)
    except OSError as error:
        temp_path.unlink(missing_ok=True)
        raise ProfileReadError(
            f"Remplacement atomique du profil impossible: {error}.") from error


#: La question posee a l'operateur quand deux chaines de scan veulent le meme fichier.
#: Le texte est celui d'Egan, mot pour mot (`EPIC5-ARB-99`, geste 3).
#:
#: Elle vit **ici** et pas dans la CLI pour une raison mesurable: ce module est le seul
#: a savoir qu'il y a collision, et la CLI est la seule a savoir s'il y a quelqu'un pour
#: repondre. Le texte descend, la reponse remonte.
COLLISION_PROMPT = ("Un profil porte deja ce nom ('{stem}', chaine de scan '{chaine}'). "
                    "Voulez-vous l'ecraser ?")


def profile_collision_suffix(document) -> str:
    """L'**empreinte differenciante** ajoutee au nom quand deux chaines le revendiquent.

    `EPIC5-ARB-99`, geste 4. C'est la recette d'empreinte du depot, reprise et non
    reecrite: :func:`naming.scan_chain_suffix`, c'est-a-dire un `sha256` tronque a
    :data:`naming.BOUNDS_SUFFIX_LENGTH`. Deterministe et inter-machine -- jamais le
    `hash()` randomise de Python, jamais une horodate, sans quoi deux passes du meme
    profil ecriraient deux fichiers.

    Le materiau est le couple **identite + etiquette brute**, jointes par un octet nul
    qui ne peut apparaitre dans aucune des deux: c'est exactement ce qui distingue les
    deux profils que le slug avait confondus. L'etiquette y entre **brute**, avant
    normalisation, pour la meme raison que `scan_chain_suffix` le fait: condenser un
    slug deja non injectif rendrait le meme condensat aux deux.
    """
    chaine = document.get("chain_id", "")
    etiquette = document.get(LABEL_FIELD, "") or ""
    return scan_chain_suffix(f"{chaine}\x00{etiquette}")


def _chain_id_du_fichier(path: Path) -> str | None:
    """L'identite de chaine deja ecrite a ce chemin, ou `None` si on ne peut pas la lire.

    `None` couvre trois cas volontairement confondus -- fichier absent, illisible, JSON
    invalide -- parce que l'appelant en fait la meme chose: il ne peut pas prouver que
    le fichier est **le sien**, donc il ne l'ecrase pas.
    """
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(document, dict):
        return None
    identite = document.get("chain_id")
    return identite if isinstance(identite, str) else None


def _stem_avec_empreinte(stem: str, document: dict) -> str:
    """Le radical, tronque si besoin, suivi de son empreinte differenciante.

    Ici la troncature est **sure**, la ou `slugify_label` la refuse: c'est l'empreinte
    qui porte l'identite, donc deux etiquettes partageant leurs 39 premiers caracteres
    rendent deux noms differents. Sans empreinte, tronquer aurait confondu les deux --
    c'est le motif du refus de `slugify_label`, et il ne s'applique pas ici.

    Meme forme que `naming.build_calibration_pdf_filename`: un fragment lisible pour
    reconnaitre le fichier a l'oeil, un condensat pour porter l'identite.
    """
    empreinte = profile_collision_suffix(document)
    budget = CANONICAL_ID_MAX_LENGTH - 1 - len(empreinte)
    lisible = stem[:budget].rstrip("-_") or "profil"
    return f"{lisible}-{empreinte}"


def write_profile(project_dir: str | Path, document: dict, *,
                  confirm_overwrite=None) -> Path:
    """Ecrire (atomiquement) le profil d'une chaine dans le projet.

    Valide d'abord en memoire, cree le dossier `versions/calibration/`, puis
    ecrit par temporaire + `os.replace`. Rend le chemin ecrit.

    Le nom du fichier est celui de l'**etiquette** du document quand il en porte une
    (AC 8quater), et le `chain_id` du document sinon: deux etiquettes distinctes font
    donc deux fichiers, et un profil non etiquete reste exactement la ou 5.22
    l'ecrivait.

    **Il n'y a plus d'argument `chain_id`** (`EPIC5-ARB-101`, retire le 2026-08-19).
    Il ne decidait plus de l'emplacement depuis l'AC 8quater, et sa seule action
    restante -- `_validate_chain_id(chain_id)` -- etait deja faite, sur la meme valeur,
    par `validate_profile_document` appelee deux lignes plus bas: mesure sur les cinq
    formes fautives que ses tests exercent (`'../escape'`, `'avec espace'`, `'x\n'`,
    un identifiant trop long, la chaine vide), **toutes refusees par le document
    seul**. Un parametre accepte puis sans effet est la definition litterale du reste
    inerte que cette story retire ailleurs; pire ici, il pouvait diverger du document
    et faire croire qu'on validait l'identite ecrite alors qu'on en validait une autre.
    La garde, elle, ne bouge pas: elle reste le seul chemin par lequel une valeur non
    derivee -- le `chain_id` d'un profil externe -- atteint un nom de fichier.

    **La collision de noms, et ce qu'elle est exactement** (`EPIC5-ARB-99`). Le slug
    d'une etiquette n'est pas injectif: `"HP Envy 4520"` et `"hp envy 4520"` le
    revendiquent tous deux. Mesuree de bout en bout par la revue de 5.23, la
    consequence n'etait pas cosmetique -- deux profils de **deux chaines differentes**
    faisaient un seul fichier, le second ecrasait le premier, le manifest declarait
    deux entrees sur un seul chemin, et le defaut du projet rendait ensuite les
    coefficients de l'autre chaine. Sans un mot.

    Il y a donc collision quand le fichier vise porte deja **une autre identite de
    chaine** (ou une identite qu'on ne peut pas lire: fichier tronque, non-UTF-8). Et
    il n'y en a **pas** quand la chaine est la meme: c'est la recalibration, ou la
    redesignation, que le module documente depuis 5.22 comme un remplacement voulu --
    poser la question a chaque recalibration serait une invite qui apprend a repondre
    « oui » sans lire, donc l'inverse de ce que cette decision cherche.

    `confirm_overwrite` est le seul chemin vers l'ecrasement. C'est un appelable
    `(document_existant, radical) -> bool`, que **la CLI** fournit quand -- et seulement
    quand -- elle a un terminal (`cli._stdin_is_interactive`, la seule machinerie
    d'interactivite du depot, qui n'est pas dupliquee ici). Le texte de la question est
    :data:`COLLISION_PROMPT`.

    **Hors terminal, le defaut est l'empreinte, jamais l'ecrasement** (`EPIC5-ARB-99`,
    tranche pour le regime que la note d'Egan ne couvre pas: script, CI, ces 4900
    tests). Un ecrasement silencieux serait exactement le defaut que cette decision
    supprime; un echec, lui, ferait perdre un profil parfaitement mesure. On fait donc
    la chose sure: le profil s'ecrit, sous un nom que rien ne confond.
    """
    normalized = validate_profile_document(document)
    # **Le fichier porte le nom que l'operateur a donne** (AC 8quater), et le
    # `chain_id` sinon. Le radical repasse par `_validate_chain_id` avant d'etre
    # concatene: c'est la meme garde qu'une identite de chaine subit, appliquee au seul
    # autre chemin par lequel une valeur libre atteint desormais un nom de fichier.
    stem = profile_file_stem(normalized)
    _validate_chain_id(stem)
    path = profile_path(project_dir, stem)
    occupant = _chain_id_du_fichier(path) if path.is_file() else normalized["chain_id"]
    if occupant != normalized["chain_id"]:
        ecraser = False
        if confirm_overwrite is not None:
            ecraser = bool(confirm_overwrite(occupant, stem))
        if not ecraser:
            stem = _stem_avec_empreinte(stem, normalized)
            _validate_chain_id(stem)
            path = profile_path(project_dir, stem)
            # Frontiere: l'empreinte est calculee sur ce qui distingue les deux profils,
            # donc ce second chemin ne peut etre occupe que par **ce** profil-ci. S'il
            # l'est par un autre, l'hypothese est fausse et on refuse plutot que
            # d'ecraser sur une supposition.
            occupant = (_chain_id_du_fichier(path) if path.is_file()
                        else normalized["chain_id"])
            if occupant != normalized["chain_id"]:
                raise ProfileValidationError(
                    f"Profil non ecrit: '{stem}.json' porte deja la chaine "
                    f"{occupant!r} et non {normalized['chain_id']!r}. L'empreinte "
                    "differenciante n'a pas separe les deux; ecraser ferait perdre "
                    "un profil qu'aucune autre trace ne porte.")
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_profile(path, serialize_profile(normalized))
    return path


def read_profile(project_dir: str | Path, chain_id: str) -> dict:
    """Relire le profil range sous ce **radical de nom de fichier**, avec defauts.

    `chain_id` y designe le radical du fichier, pas une cle d'appariement, et le nom du
    parametre est le dernier reste de l'epoque ou les deux coincidaient. Depuis
    l'AC 8quater un profil etiquete est range sous le slug de son etiquette: appeler
    cette fonction avec une identite de chaine ne le trouve **pas**, et ce n'est pas un
    defaut -- un profil se resout par le chemin ecrit au manifest
    (`io/profile_designation.default_profile_path`), jamais par recomposition depuis
    une identite (`EPIC5-ARB-83`).

    Leve `ProfileNotFoundError` quand le fichier est absent (le cas d'`AC 3`,
    distinct d'une faute) et `ProfileValidationError` quand il est present mais
    invalide (champ requis manquant, type faux, schema inconnu, chain_id hors
    pattern, octets non-UTF-8). Un fichier tronque ou mal forme est refuse par la meme
    voie: un profil dont on ne peut pas garantir le contenu ne doit pas etre applique.
    """
    _validate_chain_id(chain_id)
    path = profile_path(project_dir, chain_id)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ProfileNotFoundError(
            f"Profil absent du projet pour la chaine '{chain_id}': {error}. "
            "Regenerer-le avec `scan calibrate`, ou charger un profil depuis "
            "le disque (`AC 3`).") from error
    except UnicodeDecodeError as error:
        # **Un refus nomme, et non un `UnicodeDecodeError` nu.** Il n'est pas une
        # `OSError` -- c'est un `ValueError` --, donc il passait **hors** du garde-fou
        # ci-dessus et tuait la commande en traceback. C'est la famille du bloquant
        # `C2` de la revue de 5.22, que ce module cite lui-meme comme motif de son
        # propre `record=False`: un scan entier mourait avant l'ecriture des frames
        # parce qu'un fichier de profil n'etait pas du texte.
        raise ProfileValidationError(
            f"Profil '{chain_id}' illisible: ce ne sont pas des octets UTF-8 "
            f"({error}). Un fichier de profil est du JSON en UTF-8; celui-ci est "
            "binaire ou dans un autre encodage, et un profil dont on ne peut pas "
            "garantir le contenu ne doit pas etre applique.") from error
    try:
        document = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ProfileValidationError(
            f"Profil '{chain_id}' illisible: {error}. Un fichier tronque ne "
            "doit pas etre applique.") from error
    return validate_profile_document(document)


def profile_exists(project_dir: str | Path, chain_id: str) -> bool:
    """Le projet porte-t-il un fichier de profil sous **ce radical** ?

    Meme avertissement que `read_profile`, et il est la moitie qui coute: depuis
    l'AC 8quater ce n'est **pas** la question « ce projet a-t-il un profil pour cette
    chaine ». Un profil etiquete est range sous le slug de son etiquette, donc cette
    fonction rend `False` sur son identite de chaine alors que le profil est bien la.
    Elle repond a une question de systeme de fichiers, pas d'appariement -- s'en servir
    comme d'un test d'appartenance reintroduirait la resolution par identite que
    `EPIC5-ARB-83` supprime.
    """
    return profile_path(project_dir, chain_id).is_file()
