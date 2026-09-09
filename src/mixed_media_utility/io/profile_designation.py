"""Designation de profil de calibration par l'operateur (story 5.23, AC 12).

**L'operateur designe le profil; la machine ne le devine plus** (`EPIC5-ARB-83`,
tranche par Egan le 2026-08-17).

Ce que ce module remplace, et pourquoi il ne s'agit pas d'un raffinement. Jusqu'ici
le profil applique a un lot etait retrouve en **derivant** l'identite de la chaine de
scan puis en lisant `versions/calibration/<chain_id>.json`. Cette derivation est
**mesuree defaillante sur le materiel d'Egan**: les tags scanner y sont absents, si
bien que deux scanners physiquement differents rendaient tous les deux
`600-tiff-e2168f9b2b81` -- et le mauvais profil s'appliquait en silence. Aucun
raffinement de la derivation ne ferme ce trou: les tags **n'existent pas**. Quand
l'operateur designe le profil, le defaut ne se corrige pas, **il cesse d'etre
possible**.

Les trois proprietes que ce module tient, et qu'aucune ligne ne doit reintroduire:

1. **Aucun appariement par `chain_id`.** Le `chain_id` reste ecrit au fichier et au
   manifest -- il est l'identite et la provenance du profil --, mais il n'est
   **compare a rien** pour choisir un profil. Le seul chemin par lequel un profil est
   choisi est un **chemin de fichier** designe par l'operateur.
2. **Aucun repli automatique.** Sans profil designe, le lot est livre **brut**, avec
   un avertissement. Choisir a la place de l'operateur -- « il n'y a qu'un profil
   dans le projet, ce doit etre celui-la » -- reintroduirait exactement le defaut que
   `EPIC5-ARB-83` supprime, et le reintroduirait sous une forme plus difficile a voir.
3. **Aucun refus lie au projet.** Une page et un profil appartiennent a une **chaine
   de scan**, jamais a un projet (`EPIC5-ARB-82`, confirme par Egan: « on peut
   utiliser la page d'un autre projet dans un projet donne. Cela ne doit pas donner
   lieu a un refus de calibration »). Un profil designe hors du projet courant y est
   **verse**, sans un mot sur sa provenance.

**Un profil = un fichier autoportant + une entree autoportante au manifest** (Egan,
note 1 de sa relecture du 2026-08-18). Les deux se suffisent, et c'est deliberement
redondant: le **fichier** voyage seul (il porte ses coefficients, son identite, ses
mesures), et le **manifest** dit ce que le projet a reellement utilise **sans avoir a
ouvrir le fichier**. Un manifest qui ne porterait qu'un chemin obligerait a relire le
profil pour savoir ce qui a corrige un lot -- donc a l'avoir encore.

Module **pur** au sens de `io/`: json, chemins, et rien d'autre. Aucun import de
numpy, d'OpenCV ni de `color_calibration`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from . import calibration_profile

#: Section du `project.json` ou vivent les deux cles ci-dessous. Le schema v2 la
#: declare `additionalProperties: true`, donc ces champs s'y ajoutent sans revision
#: de version -- exactement comme `calibration_chain_ids` de la story 5.22.
COLOR_SECTION_KEY = "color"

#: Registre des profils que ce projet a reellement utilises, **liste triee** d'entrees
#: autoportantes. Liste et non valeur unique, pour le meme motif que
#: `calibration_chain_ids`: un projet peut porter des lots numerises sur plusieurs
#: chaines, et un champ scalaire aurait fait ecrire la derniere par-dessus les
#: precedentes.
DESIGNATED_PROFILES_KEY = "calibration_profiles"

#: Le profil par defaut du projet, pose par une commande **dediee et separee** --
#: jamais par un effet de bord d'un scan (`EPIC5-ARB-83`, decision 2). C'est une
#: entree de la meme forme que celles du registre: elle se suffit, donc lire le
#: defaut ne demande ni d'ouvrir le fichier de profil, ni de parcourir le registre.
DEFAULT_PROFILE_KEY = "default_calibration_profile"

#: Cle de l'entree qui porte le chemin **dans le projet** du fichier de profil,
#: relatif au dossier projet et en separateurs POSIX (meme convention que le reste du
#: manifest). C'est par lui que le defaut se resout -- **jamais** en recomposant
#: `versions/calibration/<chain_id>.json` a partir du `chain_id`: recomposer ferait de
#: l'identite une cle de resolution, ce que `EPIC5-ARB-83` supprime.
ENTRY_PATH_KEY = "path"

#: Cle de l'entree qui porte le **nom du fichier** designe par l'operateur -- son nom
#: de base, jamais son chemin. C'est de la provenance, jamais une cle: le fichier peut
#: avoir disparu de la ou il venait, l'entree reste vraie de ce qui s'est passe.
#:
#: Le nom de base et non le chemin, et ce n'est pas une approximation: le contrat v2
#: interdit **toute** chaine ressemblant a un chemin absolu, ou qu'elle se trouve dans
#: le manifest (`io/manifest._check_no_absolute_paths`, story 2.1, AC 2 et 3). L'invariant
#: est celui de la portabilite -- un projet se copie d'une machine a l'autre --, et un
#: profil designe vit precisement **hors** du projet, donc son chemin n'est relatif a
#: rien de copiable. Le nom de base, lui, reste vrai partout et suffit a la question que
#: l'operateur pose (« lequel de mes fichiers ai-je designe »).
ENTRY_SOURCE_KEY = "designated_from"

#: Cle de l'entree qui porte la **date et l'heure** de la designation, en RFC 3339 UTC
#: (`EPIC5-ARB-99`, geste 2: « date et heure au manifeste »).
#:
#: Elle ne resout rien et n'entre dans aucune comparaison: elle existe pour que **deux
#: entrees se distinguent a la lecture**. Le defaut ferme par cette decision se lisait
#: precisement ainsi -- deux entrees de deux chaines, un seul chemin, et rien dans le
#: manifest ne disait laquelle avait ete ecrite en dernier.
#:
#: Meme recette que `extraction_manifest._utc_now_rfc3339`, reprise et non reecrite:
#: une seconde serialisation d'horodate divergerait a la premiere evolution du format.
ENTRY_DESIGNATED_AT_KEY = "designated_at"

#: Champs du document de profil recopies dans l'entree de manifest. C'est ce qui la
#: rend **autoportante**: repondre a « qu'est-ce qui a corrige ce projet » sans ouvrir
#: le fichier. Enumere ici et derive du document, jamais recompose champ par champ a
#: l'appel: une seconde redaction divergerait a la premiere evolution du profil.
ENTRY_DOCUMENT_FIELDS = (
    "schema_version",
    "chain_id",
    "correction_form_id",
    "source_page_id",
    "template_id",
    "read_patch_count",
    "retained_patch_count",
    "ink_floor_excluded",
)


#: Champs **optionnels** du document recopies dans l'entree, avec leur defaut. Separes
#: des precedents parce qu'ils sont lus par `.get`: un profil ecrit avant l'AC 8quater
#: ne les porte pas, et une entree de manifest impossible a construire pour un vieux
#: profil serait exactement la retrocompatibilite cassee que cette AC doit tenir.
#:
#: Ils y sont **parce que l'entree est autoportante**: la GUI d'Epic 7 liste les profils
#: d'un projet depuis le manifest et affiche le commentaire au survol. Sans eux, il
#: faudrait ouvrir chaque fichier de profil pour afficher autre chose que des identites
#: de chaine -- c'est-a-dire precisement ce qu'Egan ne veut pas lire.
ENTRY_OPTIONAL_DOCUMENT_FIELDS = (
    calibration_profile.LABEL_FIELD,
    calibration_profile.COMMENT_FIELD,
)


class ProfileDesignationError(Exception):
    """Le profil designe n'est pas exploitable. Rien n'a ete ecrit.

    Distincte de `calibration_profile.ProfileReadError`: celle-ci parle du **geste de
    designation** (le chemin donne par l'operateur), celle-la du **contenu** d'un
    document. Les confondre ferait dire « profil invalide » a un chemin mal tape.
    """


def read_designated_document(source: str | Path) -> dict:
    """Relire et valider le profil designe, **ou** lever un refus nomme.

    Aucune tolerance de relecture: un document dont le contenu ne peut pas etre
    garanti ne doit pas etre applique -- ce sont des pixels qu'on ne saurait plus
    interpreter. Le refus nomme le **chemin**, parce que c'est ce que l'operateur a
    tape et la seule chose qu'il puisse corriger.
    """
    chemin = Path(source)
    try:
        brut = chemin.read_text(encoding="utf-8")
    except OSError as exc:
        raise ProfileDesignationError(
            f"Profil designe '{chemin}' illisible: {exc}.") from exc
    except UnicodeDecodeError as exc:
        # **Le refus nomme, la ou passait un `UnicodeDecodeError` nu.** Il derive de
        # `ValueError` et non d'`OSError`: il traversait donc le garde-fou ci-dessus,
        # et `--profil <fichier binaire>` tuait le scan en traceback **avant
        # l'ecriture des frames**. C'est la famille du bloquant `C2` de la revue de
        # 5.22 -- un chemin de trace qui fait perdre un lot deja extractible --, et le
        # seul chemin par lequel un fichier que le projet n'a pas produit entre ici.
        raise ProfileDesignationError(
            f"Profil designe '{chemin}' n'est pas du texte UTF-8 ({exc}). Un fichier "
            "de profil est du JSON en UTF-8; verifiez que le chemin designe est bien "
            "un profil et non une image ou une archive.") from exc
    try:
        document = json.loads(brut)
    except json.JSONDecodeError as exc:
        raise ProfileDesignationError(
            f"Profil designe '{chemin}' n'est pas un JSON valide: {exc}.") from exc
    try:
        return calibration_profile.validate_profile_document(document)
    except calibration_profile.ProfileValidationError as exc:
        raise ProfileDesignationError(
            f"Profil designe '{chemin}' refuse: {exc}.") from exc


def manifest_entry(document: Mapping[str, Any], *, project_path: Path,
                   project_dir: str | Path,
                   source: str | Path,
                   designated_at: str | None = None) -> dict:
    """L'entree **autoportante** d'un profil, telle qu'elle vit au manifest.

    Autoportante veut dire: elle repond seule a « quel profil, de quelle chaine, sous
    quelle forme de correction, ajuste sur quelle page, sur combien de pastilles, d'ou
    il venait **et quand** » -- sans ouvrir le fichier de profil, et sans le supposer
    encore present. C'est la moitie manifest du couple d'Egan (« un profil = un fichier
    autonome + une entree autoportante au manifeste »).

    `designated_at` est un parametre plutot qu'un appel direct a l'horloge, pour une
    raison de mesure: une entree qu'on ne peut pas construire deux fois a l'identique
    ne peut pas etre comparee par un test. Le defaut reste l'heure courante, qui est le
    regime de production.
    """
    from .extraction_manifest import _utc_now_rfc3339

    entree = {champ: document[champ] for champ in ENTRY_DOCUMENT_FIELDS}
    entree.update({champ: document.get(champ, "")
                   for champ in ENTRY_OPTIONAL_DOCUMENT_FIELDS})
    entree[ENTRY_PATH_KEY] = project_path.relative_to(Path(project_dir)).as_posix()
    entree[ENTRY_SOURCE_KEY] = Path(source).name
    entree[ENTRY_DESIGNATED_AT_KEY] = designated_at or _utc_now_rfc3339()
    return entree


def _upsert(entries, entree: Mapping[str, Any]) -> list:
    """Le registre, l'entree posee, **trie par chaine** et sans doublon.

    * **trie**, pour que deux projets ayant vu les memes profils dans un ordre
      different rendent le meme document: l'ordre des scans n'est pas une donnee;
    * **sans doublon**, parce qu'une chaine recalibree remplace son entree -- deux
      entrees pour une chaine feraient deux verites, dont une perimee.

    C'est le **seul** endroit du module qui compare un `chain_id`, et le distinguo est
    ce qui le rend legitime: il ne **choisit** pas un profil, il dedoublonne un
    registre deja constitue de designations passees. Un `find_registered_profile` lui
    doublait ce role jusqu'au 2026-08-19, sans aucun appelant de production, et son
    docstring lui pretait un role que celui-ci tient seul (`EPIC5-ARB-101`): un
    comparateur de `chain_id` inerte dans ce module precis est exactement le reste
    qu'une story suivante reutiliserait pour apparier.

    Ecarter la mauvaise entree -- la premiere plutot que celle qui porte la chaine
    visee -- est la classe du mutant `M25` (`_find_lot`, story 5.7): le registre serait
    ecrase de travers des le deuxieme profil, et un projet declarerait avoir utilise un
    profil qu'il n'a jamais applique.
    """
    connues = [dict(valeur) for valeur in entries
               if isinstance(valeur, Mapping)] if isinstance(entries, list) else []
    restantes = [valeur for valeur in connues
                 if valeur.get("chain_id") != entree["chain_id"]]
    restantes.append(dict(entree))
    return sorted(restantes, key=lambda valeur: str(valeur.get("chain_id", "")))


def _manifest_path(project_dir: str | Path) -> Path:
    from . import extraction_manifest

    return Path(project_dir) / extraction_manifest.MANIFEST_FILENAME


def _rewrite_color_section(project_dir: str | Path, mutation) -> bool:
    """Appliquer `mutation` a la section `color` du `project.json`, atomiquement.

    Rend `False` quand il n'y a **aucun** manifest a modifier -- un dossier projet qui
    n'a pas encore ete persiste. Ce n'est pas une faute: l'appelant reessaie apres la
    persistance, et le profil, lui, est deja sur le disque.

    Reprend `_load_existing_manifest` / `_atomic_write` d'`extraction_manifest` plutot
    que d'en ecrire une seconde version (meme principe que `io/pdf_manifest.py`:
    « Reprendre, ne pas copier »). L'import est **local**, comme partout dans `io/`,
    pour ne pas creer de cycle a l'import du paquet.
    """
    from .extraction_manifest import _atomic_write, _load_existing_manifest

    chemin = _manifest_path(project_dir)
    existant = _load_existing_manifest(chemin)
    if existant is None:
        return False
    manifest = json.loads(json.dumps(existant))
    section = dict(manifest.get(COLOR_SECTION_KEY) or {})
    mutation(section)
    manifest[COLOR_SECTION_KEY] = section
    _atomic_write(chemin, manifest)
    return True


def record_designated_profile(project_dir: str | Path, document: Mapping[str, Any],
                              *, project_path: Path, source: str | Path,
                              as_default: bool = False,
                              designated_at: str | None = None) -> dict:
    """Verser au manifest du **projet courant** l'entree autoportante du profil.

    « L'import verse au projet courant » (`EPIC5-ARB-83`, decision 6): un profil
    designe hors du projet y entre, **sans aucun refus lie au projet**. Rien ici
    n'examine d'ou vient le fichier: la provenance est ecrite, elle ne decide de rien.

    Rend l'entree ecrite (ou celle qui aurait ete ecrite, si le projet n'a pas encore
    de manifest -- l'appelant la reposera apres la persistance).
    """
    entree = manifest_entry(document, project_path=project_path,
                            project_dir=project_dir, source=source,
                            designated_at=designated_at)

    def mutation(section: dict) -> None:
        section[DESIGNATED_PROFILES_KEY] = _upsert(
            section.get(DESIGNATED_PROFILES_KEY), entree)
        if as_default:
            section[DEFAULT_PROFILE_KEY] = dict(entree)

    _rewrite_color_section(project_dir, mutation)
    return entree


def import_designated_profile(project_dir: str | Path, source: str | Path, *,
                              record: bool = True,
                              as_default: bool = False,
                              confirm_overwrite=None) -> tuple[dict, Path]:
    """Valider le profil designe, l'ecrire **dans** le projet, l'inscrire au manifest.

    Rend le couple `(document, chemin dans le projet)`.

    Le fichier est ecrit sous `versions/calibration/<radical>.json`, ou le radical est
    l'etiquette du document quand il en porte une (AC 8quater) et le `chain_id` qu'il
    porte sinon -- jamais une identite derivee du scan en cours. C'est un **nom**, pas une cle: deux profils de deux chaines cohabitent, et
    un profil venu d'ailleurs garde son identite d'origine au lieu d'etre reecrit sous
    celle du projet d'accueil. Le reecrire serait la faute inverse de celle que la
    story supprime -- un profil retrouve plus tard sous une identite qui n'est pas la
    sienne.

    Un profil deja present sous **cette identite de chaine** est remplace: c'est le
    geste de l'operateur qui redesigne, et refuser l'obligerait a effacer un fichier a
    la main. Un profil deja present sous ce **nom** mais portant une **autre** chaine
    est une collision, jamais un remplacement: `confirm_overwrite` est le seul chemin
    par lequel il peut etre ecrase, et hors terminal le profil entrant prend une
    empreinte differenciante (`EPIC5-ARB-99`, detail dans
    `calibration_profile.write_profile`).

    `record=False` **n'ecrit que le fichier** et laisse l'entree de manifest a
    l'appelant. C'est ce dont le chemin de scan a besoin, et pour deux raisons qui vont
    dans le meme sens: un projet neuf n'a pas encore de `project.json` au moment ou la
    correction doit etre calculee, et surtout un echec d'ecriture du manifest ne doit
    **pas** remonter par ici. C'est la famille du bloquant `C2` de la revue de 5.22:
    un scan entier mourait en traceback parce que la consignation d'un profil n'avait
    pas pu ecrire, alors que les frames etaient parfaitement extractibles. La **trace**
    d'un profil n'est pas de la meme urgence que le profil lui-meme.
    """
    document = read_designated_document(source)
    try:
        chemin = calibration_profile.write_profile(
            project_dir, document,
            confirm_overwrite=confirm_overwrite)
    except (calibration_profile.ProfileReadError, OSError) as exc:
        raise ProfileDesignationError(
            f"Profil designe '{source}' valide mais non consigne dans "
            f"{project_dir}: {exc}.") from exc
    if record:
        record_designated_profile(project_dir, document, project_path=chemin,
                                  source=source, as_default=as_default)
    return document, chemin


def _color_section(project_dir: str | Path) -> dict:
    """La section `color` du manifest, ou un dictionnaire **vide**.

    Point unique de lecture de cette section, partage par le lecteur du defaut
    et par celui du registre (story 11.4b, lot S5) : deux relectures du meme
    endroit divergeraient au premier changement de forme du manifest, et
    l'ecart ne se verrait que sur un projet dont le defaut et le registre ne
    diraient plus la meme chose.

    **Aucun echec ne remonte** : un projet sans manifest, un manifest illisible
    ou une section absente rendent la meme chose -- rien de designe. Un
    manifest illisible n'est pas un defaut de designation, et faire lever la
    lecture du registre transformerait un projet a demi ecrit en refus
    d'ouverture d'ecran.
    """
    from .extraction_manifest import _load_existing_manifest

    try:
        existant = _load_existing_manifest(_manifest_path(project_dir))
    except Exception:  # noqa: BLE001 -- un manifest illisible n'est pas un defaut
        return {}
    if not isinstance(existant, Mapping):
        return {}
    section = existant.get(COLOR_SECTION_KEY)
    return dict(section) if isinstance(section, Mapping) else {}


def designated_profiles(project_dir: str | Path) -> list[dict]:
    """**La liste** des profils que ce projet a designes, dans l'ordre du registre.

    Story 11.4b, lot S5 (AC 8). Symetrique de l'ecrivain `_upsert` /
    :func:`record_designated_profile`, qui manquait : fait F8 de la 11.4b,
    mesure et non suppose -- `DESIGNATED_PROFILES_KEY` n'apparaissait qu'a sa
    definition et a son ecriture. **Un ecrivain, zero lecteur.** Un ecran qui
    doit proposer un profil parmi ceux du projet n'avait aucun moyen de les
    enumerer, et les seules lectures publiques du module
    (:func:`read_designated_document`, :func:`default_profile_entry`,
    :func:`default_profile_path`) repondent a d'autres questions.

    Rend des entrees **autoportantes**, telles qu'elles ont ete ecrites : elles
    repondent seules a « quel profil, de quelle chaine, sous quelle forme de
    correction, ajuste sur quelle page, d'ou il venait et quand », sans ouvrir
    un seul fichier de profil -- donc sans les supposer encore presents. C'est
    exactement ce dont une liste a l'ecran a besoin, et c'est la moitie
    manifest du couple d'Egan (« un profil = un fichier autoportant + une
    entree autoportante au manifest »).

    **L'ordre est celui du registre**, jamais un ordre recalcule ici : le
    registre est deja trie par `chain_id` a l'ecriture, pour que deux projets
    ayant vu les memes profils dans un ordre different rendent le meme
    document. Le retrier ici serait une seconde redaction de cette regle.

    **Aucun repli, aucune invention** (`EPIC5-ARB-83`, propriete 2) : un projet
    sans aucun profil designe rend une liste **vide** (AC 8.3), jamais une
    erreur et jamais un profil balaye depuis `versions/calibration/`. Balayer
    le dossier, ou rendre « le seul profil du projet, ce doit etre celui-la »,
    reintroduirait le choix automatique que cette story a supprime -- sous une
    forme plus difficile a voir. Cette fonction **enumere**, elle ne choisit
    pas.

    **Rien n'est compare a un `chain_id`** ici : le module n'a qu'un seul
    endroit qui le fasse (`_upsert`, qui dedoublonne un registre deja
    constitue), et un second comparateur serait exactement le reste qu'une
    story suivante reutiliserait pour apparier (`EPIC5-ARB-101`).
    """
    entrees = _color_section(project_dir).get(DESIGNATED_PROFILES_KEY)
    if not isinstance(entrees, list):
        return []
    # Une entree qui n'est pas un mapping est **ecartee**, jamais rendue telle
    # quelle : le registre est ecrit par ce module, mais le `project.json` d'un
    # operateur s'edite a la main, et une chaine nue rendue ici deviendrait un
    # `entree["path"]` en `TypeError` chez l'appelant, plusieurs etages plus
    # loin. Meme geste que `_upsert`, qui filtre deja a l'ecriture.
    return [dict(entree) for entree in entrees if isinstance(entree, Mapping)]


def designated_profile_path(project_dir: str | Path,
                            entry: Mapping[str, Any]) -> Path | None:
    """Le fichier d'une entree du registre, resolu **par le chemin ecrit**.

    Corps commun avec :func:`default_profile_path`, et c'est tout son objet :
    sans lui, l'ecran qui choisit un profil dans la liste de
    :func:`designated_profiles` devrait recomposer le chemin lui-meme. Une
    seconde redaction de cette resolution est precisement la porte par laquelle
    `versions/calibration/<chain_id>.json` reviendrait -- c'est-a-dire
    l'identite redevenue cle de resolution, ce que `EPIC5-ARB-83` supprime, et
    de la seule facon qui passe inapercue : en marchant, tant que les deux
    coincident.

    Rend `None` quand l'entree ne porte pas de chemin exploitable ou quand le
    fichier a disparu : l'entree reste vraie de ce que le projet a utilise,
    mais elle ne fabrique pas un profil absent.
    """
    if not isinstance(entry, Mapping):
        return None
    relatif = entry.get(ENTRY_PATH_KEY)
    if not isinstance(relatif, str) or not relatif:
        return None
    chemin = Path(project_dir) / relatif
    return chemin if chemin.is_file() else None


def default_profile_entry(project_dir: str | Path) -> dict | None:
    """L'entree du profil par defaut du projet, ou `None` s'il n'y en a pas.

    Aucun repli: pas d'entree, pas de defaut. Parcourir le registre pour y prendre le
    premier profil, ou balayer `versions/calibration/`, serait le choix automatique
    que `EPIC5-ARB-83` interdit -- et ce serait la meme faute que la derivation
    automatique, sous un autre nom.
    """
    # La lecture de la section passe par `_color_section` (story 11.4b, lot
    # S5), point unique partage avec le lecteur du registre. Le corps est
    # **deplace**, jamais reecrit : memes replis, meme absorption d'un manifest
    # illisible, meme reponse « rien de designe ».
    entree = _color_section(project_dir).get(DEFAULT_PROFILE_KEY)
    if not isinstance(entree, Mapping):
        return None
    return dict(entree)


def default_profile_path(project_dir: str | Path) -> Path | None:
    """Le chemin du profil par defaut du projet, resolu **par le chemin ecrit**.

    Jamais recompose depuis le `chain_id`: recomposer ferait de l'identite une cle de
    resolution, ce que `EPIC5-ARB-83` supprime, et le ferait de la seule facon qui
    passe inapercue -- en marchant, tant que les deux coincident.

    Rend `None` quand le fichier a disparu: l'entree de manifest reste vraie de ce que
    le projet a utilise, mais elle ne fabrique pas un profil absent. L'appelant
    avertit, et le lot sort brut.
    """
    # Corps **deplace** dans `designated_profile_path` (story 11.4b, lot S5) et
    # jamais recopie : le defaut est une entree de la meme forme que celles du
    # registre, donc sa resolution est la meme resolution. Deux redactions
    # divergeraient, et l'ecart ne se verrait que sur un projet ou le defaut et
    # un profil du registre ne pointeraient plus au meme endroit.
    return designated_profile_path(project_dir, default_profile_entry(project_dir) or {})
