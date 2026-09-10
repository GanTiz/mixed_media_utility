# -*- coding: utf-8 -*-
"""L'explorateur de dossiers (story 11.2b, `EPIC11-ARB-48` a `56`).

Il remplace le champ-chemin partout ou la TUI demande un chemin. Trois defauts
**mesures** de la completion qu'il remplace, et qui expliquent sa forme :

* elle ne proposait **rien** sur un champ vide -- un raccourci pour qui connait
  deja le chemin, pas un outil pour le trouver ;
* sa zone de propositions tenait sur **une ligne**, sans defilement ni compteur ;
* elle s'arretait au plus long prefixe commun, donc sur `01_reperages`,
  `02_tournage`, `03_essais` elle ne completait **rien**.

**Ce module ne connait pas `textual`.** Le modele et le rendu en lignes vivent
ici et se mesurent sans terminal, comme `projets.py` ; l'ecran ne fait que
poser les lignes et router les touches. C'est ce qui rend testables les trois
appariements a risque de cette story : entree visible contre ligne rendue,
entree sous le curseur contre etiquette du bas, et lot contre etat compte.

**Les deux etiquettes sont VIVES, jamais des cibles** (`EPIC11-ARB-50`). Celle
du haut dit ou `←` mene, celle du bas dit ce que `⏎` validerait, et elle suit le
curseur. Le curseur n'y va jamais : c'est ce qui empeche a la fois les deux
curseurs simultanes qu'Egan a trouves sur la maquette v1 (« il y a deux curseurs
sur ton image. Impossible. ») et les vingt-sept frappes qu'il fallait pour
atteindre « Valider ».
"""
from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

from . import jetons

#: Hauteur FIXE de la zone de liste, `…` compris. Elle ne bouge jamais : les
#: deux etiquettes encadrantes occupent toujours les memes lignes de la grille,
#: que le dossier courant porte zero ou deux cents entrees. Une cible qui se
#: deplace quand la liste change de longueur est une cible qu'on rate.
HAUTEUR_LISTE = 9

#: Ce que la ligne du bas annonce quand il n'y a rien a valider.
RIEN_A_VALIDER = "--"

#: Les prefixes qui font qu'un dossier est « cache » (`EPIC11-ARB-53`). Ecrits
#: ici et pas devines : `$RECYCLE.BIN` est a la racine de chaque volume Windows,
#: et `System Volume Information` ne porte pas de point.
PREFIXES_CACHES = (".", "$")
NOMS_CACHES = frozenset({"System Volume Information"})

#: Ou les systemes de bureau montent les supports amovibles. Ecrits ici et pas
#: devines : c'est une convention par systeme, pas une regle deductible.
PARENTS_DE_MONTAGE = ("/Volumes", "/media", "/mnt", "/run/media")

#: Ceux de ces parents qui interposent un palier par COMPTE
#: (`/media/<utilisateur>/<disque>`, la disposition d'udisks2).
PARENTS_PAR_COMPTE = ("/media", "/run/media")

#: Ce que la ligne du haut et la barre d'adresse nomment quand on est dans la
#: liste des volumes. Un seul endroit : les deux doivent dire le meme mot.
LISTE_DES_VOLUMES = "Volumes"

#: Ce que dit la ligne d'etat quand le chemin saisi ne designe rien. Et ce
#: **n'est pas un refus** : rien ne passe en `state-absent`, une frappe en cours
#: n'est pas une erreur.
#:
#: **La phrase ne parle plus de « dossier »** (story 11.15, `EPIC11-ARB-283`).
#: La formulation d'origine etait celle d'Egan, verbatim -- « le bandeau du bas
#: doit juste dire "aucun dossier n'existe a cette adresse" » --, et elle etait
#: juste tant que la barre d'adresse ne savait suivre qu'un dossier. Elle a
#: cesse de l'etre le jour ou coller un chemin de FICHIER est devenu un geste
#: servi : la phrase annoncait alors l'absence d'un fichier qui existe. Le NOM
#: de la constante ne bouge pas -- quatre bancs la lisent --, seul son texte.
ADRESSE_INEXISTANTE = "rien n'existe a cette adresse"

#: Les trois raisons pour lesquelles un fichier qui EXISTE peut ne pas figurer
#: dans la liste de son propre dossier. L'ecran va au dossier parent et NOMME
#: celle qui s'applique, plutot que de rendre une liste ou le fichier manque
#: sans explication (`EPIC11-ARB-89` : « jamais un blocage sec » ;
#: `EPIC11-ARB-56` : une mesure, jamais une touche ni un conseil -- aucune de
#: ces trois phrases ne nomme `Ctrl+H`).
#:
#: **Elles sont en ASCII pur, comme `ADRESSE_INEXISTANTE`**, et ce n'est pas un
#: hasard : `etat()` rend `self._refus` **avant** de construire sa table de
#: glyphes et sans passer par `_replie`, si bien qu'un accent pose ici fuirait
#: tel quel en `--ascii`. Une frontiere le mesure.
FICHIERS_NON_MONTRES = "cet ecran ne montre pas les fichiers"
FICHIER_CACHE = "ce fichier est cache"
FICHIER_ABSENT_DE_LA_LISTE = "ce fichier ne figure pas dans la liste"


def symbole(nom: str, ascii_seul: bool = False) -> str:
    """Un symbole de TEXTE (`…`, `←`, `⏎`), replie pour le mode demande.

    Ces trois-la ne sont pas dans la table des glyphes du `DESIGN.md` : ils
    vivent dans `jetons.REPLIS_DE_TEXTE`, qui est la table des symboles que les
    textes d'ecran portent en plus des glyphes d'etat.

    **Le repli se fait ICI, avant toute mesure de largeur.** `…` occupe une
    colonne et `...` en occupe trois ; replier apres avoir mesure ferait
    deborder de deux colonnes chaque ligne calee juste -- c'est la regression
    payee sur le bandeau le 2026-08-28, et le motif est ecrit noir sur blanc
    dans `jetons.abreger_chemin`.
    """
    return jetons.REPLIS_DE_TEXTE[nom] if ascii_seul else nom


#: Les trois symboles de texte que l'explorateur nomme. `ELLIPSE` est LUE dans
#: le module de mesure : c'est lui qui abrege, et deux ecritures du meme
#: caractere divergeraient sur le repli.
ELLIPSE = jetons.ELLIPSE
PARENT = "\u2190"
ENTREE = "\u23ce"


def _sans_accent(texte: str) -> str:
    """Le texte replie pour la comparaison du saut alphabetique.

    Le saut est insensible a la casse **et** aux accents : taper `e` doit
    trouver `Etalonnage`. Sans ce repli, la moitie des dossiers d'un montage
    francais seraient inatteignables au saut.
    """
    decompose = unicodedata.normalize("NFD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c)).lower()


def taille_lisible(octets: int) -> str:
    """Une taille de fichier, en une unite et sans decimale inutile.

    Le mot « fichier » ne precede pas la taille : « Enlever "fichier" laisser
    juste la taille » (Egan, 2026-08-29). La colonne de droite dit **ce qui
    distingue** une entree de sa voisine, pas ce qu'elles ont en commun.
    """
    for unite, seuil in (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("ko", 1024)):
        if octets >= seuil:
            valeur = octets / seuil
            entier = f"{valeur:.0f}" if valeur >= 10 else f"{valeur:.1f}"
            return f"{entier.replace('.', ',')} {unite}"
    return f"{octets} o"


@dataclass(frozen=True)
class Entree:
    """Une ligne de la liste : ce qu'elle est, et ce qu'elle autorise.

    ``entrable`` et ``validable`` sont **distincts** : un dossier illisible se
    voit et ne s'entre pas ; un fichier hors filtre se voit et ne se valide pas.
    Les masquer ferait croire qu'ils n'existent pas -- c'est la meme regle que
    pour les entrees de menu non disponibles du palier 1.

    ``illisible`` DOUBLE ce couple au lieu de s'en deduire : un fichier hors
    filtre porte lui aussi ``entrable=False, validable=False``, et la ligne
    d'etat doit pouvoir compter les entrees **non mesurees** sans compter les
    fichiers refuses par le filtre.

    **La colonne de droite est PARESSEUSE** (AC 4.6, finding `F-1`). Le champ
    accepte soit le texte, soit un appelable qui le calcule ; l'appelable n'est
    invoque qu'a la premiere lecture de ``droite``, c'est-a-dire au rendu d'une
    ligne **visible**. Avant, `relire()` construisait une entree complete pour
    chaque chemin : 27 dossiers pour 8 lignes visibles faisaient 27 `iterdir()`
    a chaque relecture -- exactement la latence que l'AC 4.6 existe pour
    empecher sur un volume lent.
    """

    chemin: Path
    est_dossier: bool
    _droite: "str | Callable[[], str]" = ""
    entrable: bool = True
    validable: bool = True
    porte_un_projet: bool = False
    illisible: bool = False

    @property
    def droite(self) -> str:
        """Le texte de la colonne de droite, calcule au plus tard et UNE fois."""
        valeur = self._droite
        if callable(valeur):
            valeur = valeur()
            # Le resultat remplace l'appelable : defiler de haut en bas puis
            # revenir ne doit pas repayer le comptage de chaque ligne.
            object.__setattr__(self, "_droite", valeur)
        return valeur

    @property
    def nom(self) -> str:
        """Le nom affiche. Un dossier porte sa barre finale, un fichier non.

        **Une racine de volume n'a pas de `name`** : `Path("C:\\\\").name` vaut la
        chaine VIDE, et `Path("/").name` aussi. La regle generale rendait donc
        `/` pour `C:\\` comme pour `D:\\` -- toutes les lignes de la liste des
        volumes portant le meme nom, qui n'est celui d'aucune. Une racine
        s'affiche entiere, separateur compris, parce que c'est tout ce
        qu'elle est.
        """
        if not self.est_dossier:
            return self.chemin.name
        # `name` d'abord, le chemin ENTIER quand il est vide. La barre finale
        # ne s'ajoute que si le nom n'en porte pas deja une : une racine EST
        # son separateur, et `C:\\/` ou `//` ne nomment rien.
        nom = self.chemin.name or str(self.chemin)
        return nom if nom.endswith(("\\", "/")) else f"{nom}/"


@dataclass
class MemoireDeSession:
    """Le dernier dossier valide de la session (`EPIC11-ARB-54`).

    **Elle vit en memoire et nulle part ailleurs.** `EPIC11-ARB-16` limite la
    persistance a la liste des recents ; ecrire ce dossier dans un fichier
    l'elargirait sans decision. La question inter-session est consignee dans
    `deferred-work.md` (retour d'Egan du 2026-09-06) plutot que tranchee ici.
    """

    dernier_valide: Path | None = None


# ---------------------------------------------------------------------------
# Les FAMILLES d'usage, et le registre qui les tient.
# ---------------------------------------------------------------------------

#: **Une memoire par famille d'usage, jamais une seule pour tout l'outil**
#: (2026-09-06, retour d'Egan « l'explorateur de fichiers ne retient pas le
#: dernier chemin explore »).
#:
#: Le mecanisme d'`EPIC11-ARB-54` etait ecrit, teste, et **cable nulle part** :
#: les sept sites de production construisaient chacun un `Explorateur` sans
#: memoire, donc chacun s'en fabriquait une neuve et vide. La recherche de
#: `memoire=` sur tout le depot rendait quatre occurrences, **toutes dans le
#: banc**. C'est la meme classe de defaut que `__main__` documente pour les
#: paliers temoins : un composant livre, mesure, et que rien n'appelle.
#:
#: **Pourquoi trois cles et non une.** Les sept sites ne cherchent pas la meme
#: chose, et leurs filtres le disent :
#:
#: * :data:`FAMILLE_PROJETS` -- on cherche un DOSSIER DE PROJET
#:   (`montrer_fichiers=False`, filtre `porte_un_projet`). Cette famille vit au
#:   palier 0, **avant qu'un projet soit ouvert** : elle ne peut donc pas etre
#:   rangee « par projet » ;
#: * :data:`FAMILLE_MATIERE` -- rushes, planches, scans. Souvent un volume
#:   externe, et c'est le parcours que l'arbitrage nomme explicitement : « sur
#:   un parcours Scan puis Pdf, on ne retraverse pas trois fois la meme
#:   arborescence ». Les ateliers la PARTAGENT, c'est tout son objet ;
#: * :data:`FAMILLE_PROFILS` -- les fichiers de profil de calibration
#:   (filtre `profil_acceptable`), qui vivent dans un dossier d'outillage.
#:
#: Une memoire unique menerait l'ecran de profils dans le dossier de rushes et
#: ferait perdre le benefice a chacun des trois. Une memoire par SITE, elle,
#: perdrait le partage que l'arbitrage demande. La cle est donc la famille.
FAMILLE_PROJETS = "projets"
FAMILLE_MATIERE = "matiere"
FAMILLE_PROFILS = "profils"

#: L'ensemble EXACT des familles. Une cle hors de cette table est un defaut de
#: cablage -- pas une quatrieme memoire silencieuse : voir
#: :meth:`MemoiresDeSession.pour`.
FAMILLES = (FAMILLE_PROJETS, FAMILLE_MATIERE, FAMILLE_PROFILS)


class MemoiresDeSession:
    """Le registre des memoires de session, **une par famille**.

    Il est porte par l'application (`coque.CoqueTui.memoires`) et non par un
    module : deux coques d'un meme processus -- ce que le banc monte a chaque
    fichier -- doivent avoir des memoires distinctes, ce qu'un singleton de
    module rendrait impossible. C'est la meme raison qui fait vivre la memoire
    de regime d'`ecran_manuel` sur l'instance.

    Les memoires sont creees **a la demande** : un parcours qui n'ouvre jamais
    l'ecran des profils n'a pas de memoire de profils, et
    :attr:`familles_ouvertes` le dit -- ce qui rend le cablage mesurable
    autrement que par ses effets.
    """

    def __init__(self, par_famille: dict[str, MemoireDeSession] | None = None
                 ) -> None:
        self._par_famille: dict[str, MemoireDeSession] = dict(par_famille or {})

    def pour(self, famille: str) -> MemoireDeSession:
        """La memoire de `famille`, creee au premier appel.

        **Une famille inconnue LEVE**, plutot que de rendre une memoire neuve.
        Un nom mal orthographie sur un site rendrait sinon une quatrieme
        memoire que personne ne partage : l'ecran retiendrait son dossier pour
        lui seul et le defaut se lirait exactement comme celui qu'on repare --
        « ca ne retient pas », sans qu'aucune etape n'echoue. Une frontiere
        balaye les ecrans et confronte leurs familles a :data:`FAMILLES`, si
        bien que la levee se paie au banc et jamais chez l'operateur.
        """
        if famille not in FAMILLES:
            raise ValueError(
                f"famille d'exploration inconnue : {famille!r} "
                f"(attendu l'une de {FAMILLES})")
        return self._par_famille.setdefault(famille, MemoireDeSession())

    @property
    def familles_ouvertes(self) -> tuple[str, ...]:
        """Les familles pour lesquelles une memoire a ete demandee."""
        return tuple(f for f in FAMILLES if f in self._par_famille)


def _lister_le_disque(dossier: Path) -> list[Path] | None:
    """Le contenu d'un dossier, ou `None` s'il ne se lit pas.

    **`None` et `[]` ne sont pas la meme information** (finding `E9`) : `[]`
    dit « ce dossier est vide », `None` dit « je n'ai pas pu regarder ». Rendre
    `[]` pour un dossier disparu entre le listage et l'entree faisait afficher
    `0 sous-dossier` et `aucun sous-dossier` -- le chiffre faux presente comme
    une mesure que le module s'interdit deux lignes plus bas, dans
    `_compter_par_defaut`, et que `projets.Compteurs` s'interdit aussi.

    Injectable a la construction : c'est ce qui rend le modele mesurable sans
    disque, et ce qui permet de rejouer la liste des volumes Windows sur une
    machine qui n'en a pas. Un injecteur qui rend `[]` dit donc « vide », et
    reste lu comme avant.
    """
    try:
        return list(dossier.iterdir())
    except OSError:
        return None


def volumes_du_systeme(windows: bool | None = None) -> list[Path] | None:
    """Les racines de volume de la machine, ou `None` si elles ne se listent pas.

    **C'est la moitie manquante de `←`.** L'etiquette du haut annonce
    « Volumes » des qu'on est sur une racine depuis la 11.2b -- et jusqu'au
    2026-09-07 la touche n'y menait nulle part : `remonter()` constatait que le
    parent d'une racine est elle-meme et rendait faux. Egan, qui travaille sous
    Windows, l'a nomme comme un bloquant : « impossible d'atteindre les volumes
    par l'explorateur de fichiers. Rien ne se passe si j'essaie de remonter aux
    volumes. » Un `D:` de rushes etait donc inatteignable autrement qu'en
    tapant son chemin.

    ``windows`` est **injectable** pour que les deux branches se mesurent
    depuis n'importe quelle plateforme -- meme geste et meme motif que
    `projets.chemin_du_fichier_de_recents` : une branche qui ne se teste que
    sur la machine ou elle s'execute n'est testee qu'a moitie.

    **`None` et `[]` ne sont pas la meme information**, comme partout dans ce
    module : `[]` dit « aucun volume », `None` dit « je n'ai pas pu regarder ».
    """
    if windows is None:
        windows = os.name == "nt"
    return _volumes_windows() if windows else _volumes_posix()


def _volumes_windows() -> list[Path] | None:
    """Les lettres de lecteur, par le MASQUE, jamais par 26 `exists()`.

    `GetLogicalDrives` rend un entier dont le bit `n` dit que la lettre `n`
    existe. Il ne touche AUCUN volume : c'est ce qui compte ici. Sonder
    `A:\\`..`Z:\\` par `Path.exists()` ferait tourner un lecteur de cartes
    vide, reveillerait chaque lecteur reseau deconnecte, et la console Windows
    y ajoute la boite « Il n'y a pas de disque dans le lecteur » -- une boite
    modale par lettre absente, sur un ecran qui promet une liste.

    La lecture reelle de chaque volume reste **paresseuse**, comme le reste du
    module (AC 4.6) : la colonne de droite ne compte que les lignes visibles,
    et un volume debranche y rend `·` plutot qu'un zero faux.
    """
    try:
        import ctypes
        masque = ctypes.windll.kernel32.GetLogicalDrives()   # type: ignore[attr-defined]
    except (ImportError, AttributeError, OSError):
        # Pas de `windll` : ce n'est pas « aucun volume », c'est « pas pu
        # regarder ». La distinction est celle de `_lister_le_disque`.
        return None
    return lettres_du_masque(masque)


def lettres_du_masque(masque: int) -> list[Path]:
    """Le masque de `GetLogicalDrives` en racines, `A:\\` au bit 0.

    **Separee de son appel systeme pour etre MESURABLE depuis Linux.** C'est la
    seule moitie de la branche Windows qui porte une regle -- l'autre est un
    appel a `windll` --, et une regle qui ne se teste que sur la machine ou
    elle s'execute n'est testee qu'a moitie. Le decalage d'un bit, l'ordre des
    lettres et la borne a 26 se mesurent donc partout.
    """
    return [Path(f"{chr(ord('A') + rang)}:\\")
            for rang in range(26) if masque >> rang & 1]


def _volumes_posix() -> list[Path]:
    """`/`, puis les points de montage des supports amovibles.

    `/` d'abord et **toujours** : c'est le seul volume dont l'existence ne se
    demande pas. Les autres se lisent aux quatre emplacements que les systemes
    de bureau utilisent -- `/Volumes` sous macOS, `/media`, `/mnt` et
    `/run/media` sous Linux.

    `/media` et `/run/media` portent une couche de plus chez udisks2 :
    `/media/<utilisateur>/<disque>`. On y descend d'un cran quand le nom du
    palier est celui d'un compte, et pas autrement -- descendre partout
    remonterait le contenu de `/mnt/sauvegardes` comme s'il etait une liste de
    volumes.

    **Ce que ca ne couvre pas, dit plutot que tu** : un montage pose ailleurs
    (`/srv`, un `fstab` maison) n'apparait pas. La barre d'adresse reste la
    voie pour ceux-la, et elle marche deja. Lire `/proc/mounts` les attraperait
    sous Linux et rendrait en meme temps les dizaines de montages systeme
    (`/proc`, `/sys`, `/run/lock`) qui ne sont pas des volumes pour qui cherche
    ses rushes -- le tri qu'il faudrait alors ecrire serait plus devinatoire
    que cette liste-ci.
    """
    volumes = [Path("/")]
    for parent in PARENTS_DE_MONTAGE:
        for enfant in sorted(_lister_le_disque(Path(parent)) or []):
            if not enfant.is_dir():
                continue
            if parent in PARENTS_PAR_COMPTE and enfant.name == _nom_de_compte():
                volumes += [p for p in sorted(_lister_le_disque(enfant) or [])
                            if p.is_dir()]
                continue
            volumes.append(enfant)
    # Un meme volume atteint par deux chemins ne se compte qu'une fois, et
    # l'ordre de decouverte est celui qu'on garde : `dict` plutot que `set`.
    return list(dict.fromkeys(volumes))


def _nom_de_compte() -> str:
    """Le nom du compte courant, ou la chaine vide s'il ne se lit pas.

    `getpass.getuser()` LEVE quand aucune des variables d'environnement n'est
    posee et que le compte n'a pas d'entree `passwd` -- ce qui est le cas
    nominal d'un conteneur. Une exception ici ferait disparaitre la liste des
    volumes entiere pour une question accessoire.
    """
    try:
        import getpass
        return getpass.getuser()
    except (ImportError, KeyError, OSError):
        # Les TROIS levees reelles, et rien de plus : `ImportError` quand
        # `pwd` manque (Windows), `KeyError` quand l'uid n'a pas d'entree
        # `passwd` -- mesure le 2026-09-07, c'est ce que rend un conteneur --,
        # `OSError` sur les plateformes qui le documentent. Un `except
        # Exception` avalait en plus tout defaut de programmation de cette
        # ligne, sur un chemin de PRODUCTION et non de diagnostic.
        return ""


def _fichiers_du_dossier(dossier: Path,
                         retenu: Callable[[Path], bool]):
    """Les fichiers d'un dossier, recursivement, et il LEVE si le dossier a
    disparu.

    **`rglob` ne leve pas** : sur un dossier absent ou illisible il rend une
    suite VIDE, et un total qui l'additionne vaut zero sans que rien ne le dise.
    C'est le defaut trouve le 2026-08-31 en fermant le survivant `S9` de la
    campagne : le test ecrit pour verifier qu'un poids non mesurable rend `None`
    a montre qu'il rendait un TOTAL AMPUTE -- exactement le chiffre faux
    presente comme une mesure que ce module s'interdit partout ailleurs.

    `os.walk` avec `onerror` qui releve fait la difference : la premiere lecture
    impossible remonte au lieu d'etre avalee.

    **`retenu` decide de ce qui compte** (`EPIC11-ARB-123`, Egan le 2026-08-31).
    Sans lui, la resolution comptait TOUT : le filtre `accepte` du site et la
    regle des fichiers caches ne s'appliquaient qu'en surface. Mesure des deux
    couches de revue qui l'ont trouve independamment -- un dossier de 8 planches,
    un `notes.txt` de 6 ko et un `.DS_Store` de 6 ko annoncait « 10 fichiers
    selectionnes   12 ko » pour **8 planches et 800 octets**. L'ecran refusait un
    `.txt` coche seul et en avalait huit par son dossier.

    Les dossiers caches sont **elagues** plutot que filtres a la sortie : un
    `.git/` de vingt mille objets se parcourait entierement pour etre jete.

    `retenu` est **obligatoire** et non optionnel a `None` : un predicat qu'on
    peut oublier de passer est exactement la forme du defaut qu'on vient de
    fermer. La frontiere `test_rappels_cables.py` l'a d'ailleurs attrape a la
    seconde ou il etait optionnel -- elle mesure qu'un rappel accepte est
    injecte ou declare, et un filtre par defaut inerte ne l'est ni l'un ni
    l'autre.
    """
    def _relever(erreur: OSError) -> None:
        raise erreur

    for base, dossiers, fichiers in os.walk(dossier, onerror=_relever):
        dossiers[:] = [d for d in dossiers if not _est_cache(d)]
        racine = Path(base)
        for nom in fichiers:
            if _est_cache(nom):
                continue
            chemin = racine / nom
            if retenu(chemin):
                yield chemin


def _replie(texte: str, ascii_seul: bool) -> str:
    """Le texte tel quel, ou replie en ASCII pur.

    Exister comme fonction plutot que comme ternaire recopie a chaque site est
    le point : la revue du 2026-08-31 a trouve DEUX lignes neuves qui avaient
    oublie le repli, au moment meme ou le module ecrivait son premier texte
    accentue. Un seul endroit ou l'oublier.
    """
    return jetons.replier_ascii(texte) if ascii_seul else texte


def _est_cache(nom: str) -> bool:
    return nom.startswith(PREFIXES_CACHES) or nom in NOMS_CACHES


def _lien_illisible(chemin: Path) -> bool:
    """Vrai pour un lien symbolique casse ou en boucle (finding `E16`).

    Sans cette question, un tel lien **disparaissait entierement** de la
    variante « dossiers seuls » : `is_dir()` rend faux, donc il tombait dans
    les fichiers, et les fichiers sont supprimes quand `montrer_fichiers` est
    faux. Un lien casse vers un rush deplace est pourtant **le** symptome que
    l'operateur cherche ; la regle du module -- « les masquer ferait croire
    qu'ils n'existent pas » -- vaut d'abord pour lui.

    La question posee est bien « ce lien mene-t-il quelque part », pas « est-ce
    un lien » : un lien valide vers un fichier reste un fichier.
    """
    try:
        if not chemin.is_symlink():
            return False
        return not chemin.exists()
    except OSError:
        # Meme savoir si c'est un lien a echoue : cela ne se lit pas.
        return True


def normaliser(chemin: Path | str, depuis: Path | None = None) -> Path:
    """Le chemin ABSOLU, **sans reecrire un seul maillon symbolique**.

    AC 6.8 : « un lien symbolique est suivi **une fois**, jamais resolu
    recursivement ». Les deux moities se tiennent, et c'est ce qui rend
    l'implementation contre-intuitive :

    * **suivi une fois**, c'est le systeme de fichiers qui le fait, a la
      lecture : `iterdir()` sur `atelier/pont` traverse le lien. Le modele n'a
      rien a faire pour cela, et surtout rien a reecrire ;
    * **jamais resolu recursivement**, c'est ce que `Path.resolve()` violait :
      il reecrit **chaque** maillon du chemin jusqu'a la cible reelle. Le
      chemin affiche cessait alors d'etre celui qu'on avait pris. Consequence
      produit mesuree par la revue (finding `F-8`) : sur un dossier atteint par
      un lien, `←` remontait vers le parent **reel** et l'operateur perdait sa
      route. Suivre le lien nous-memes, une fois, donnerait exactement le meme
      chemin affiche que `resolve()` sur ce cas : la correction est de **ne pas
      suivre du tout**.

    `..` est en revanche resolu **lexicalement** (`normpath`), c'est-a-dire
    « reviens d'ou tu viens » -- la meme regle que `←`, et le seul sens qui
    tienne quand un maillon est un lien.

    **Un chemin qui n'existe pas encore se resout quand meme** : c'est le cas
    nominal de la creation (`EPIC11-ARB-40`), et `normpath` est purement
    lexical -- il ne demande rien au systeme de fichiers. C'est ce que
    `resolve(strict=False)` apportait, et la seule moitie de son contrat qu'il
    fallait garder.

    **C'est l'implementation UNIQUE de la resolution de chemin de la TUI** :
    `projets.resoudre` est cette fonction, sous son autre nom. Il y en a eu
    deux -- `projets.resoudre` avec `resolve(strict=False)`, et une copie
    locale `resoudre_sans_recursion` ecrite pour la contourner --, et les deux
    ne faisaient pas la meme chose : `ecran_projet` affichait donc la cible
    REELLE d'un parent saisi par un lien, avant validation, pendant que
    l'explorateur affichait le chemin pris.
    """
    chemin = Path(chemin).expanduser()
    if not chemin.is_absolute():
        chemin = Path(depuis or Path.cwd()) / chemin
    return Path(os.path.normpath(str(chemin)))


def _mesure_des_caches(dossiers: int, fichiers: int) -> str:
    """La phrase du compte masque, **nommee par ce qu'elle compte**.

    Finding `E14`/`F9` : la phrase disait « dossiers caches » pour un compte
    qui incluait `.DS_Store` et `.gitignore`, et `Ctrl+H` ne les revelait
    jamais puisque les fichiers etaient de toute facon filtres. L'operateur
    avait la preuve qu'on lui cachait quelque chose et aucun moyen de le voir.
    Le compte est desormais pris **apres** le filtre `montrer_fichiers`, et le
    mot suit ce qui est reellement masque.
    """
    total = dossiers + fichiers
    if not total:
        return ""
    if dossiers and fichiers:
        return f"{total} elements caches"
    mot = "fichier" if fichiers else "dossier"
    return f"{total} {mot}{'s' if total > 1 else ''} cache{'s' if total > 1 else ''}"


class Explorateur:
    """Le modele pur : ou l'on est, ce qu'on voit, ce que chaque touche fait.

    **Trois reglages** (`EPIC11-ARB-48`, amende par `EPIC11-ARB-102`) :

    * ``montrer_fichiers`` -- ce que la liste porte ;
    * ``accepte`` -- ce qu'une validation rend, pour la variante fichiers ;
    * ``selection_multiple`` -- une coche par entree, plusieurs retenues.

    Ecrire cinq explorateurs pour cinq ecrans serait la faute que la story
    existe pour eviter : un defaut se paierait cinq fois.

    **Le compte est une MESURE, pas une phrase.** `EPIC11-ARB-48` disait « deux
    reglages, et pas davantage » ; cette phrase etait vraie jusqu'a ce qu'elle
    cesse de l'etre, et rien ne l'aurait dit. :data:`REGLAGES` porte desormais
    la liste, un test compare ce docstring a sa longueur, et un quatrieme
    reglage ne peut plus entrer sans faire rougir un banc. C'est la doctrine du
    depot appliquee a une regle du depot.
    """

    #: Les reglages, nommes ici pour etre COMPTES. Toute entree ajoutee doit
    #: exister dans la signature de `__init__`, et le nombre annonce au
    #: docstring ci-dessus doit suivre : les deux sont mesures.
    REGLAGES = ("montrer_fichiers", "accepte", "selection_multiple")

    #: Le reste de la signature : de l'**outillage**, pas des reglages. Ce sont
    #: les points d'injection des bancs et le contexte de session -- ils ne
    #: changent pas ce que l'ecran fait, ils disent d'ou il tire ce qu'il
    #: montre.
    #:
    #: **Cette table existe parce que la frontiere mesurait le mauvais sens**
    #: (finding `R8` de la revue du 2026-08-31). Elle verifiait que chaque nom
    #: de :data:`REGLAGES` figure dans la signature -- or un reglage s'ajoute
    #: PAR la signature, pas par la table : un `trier_a_l_envers` ajoute a
    #: `__init__` sans toucher a rien d'autre passait la suite TUI entiere,
    #: mutant injecte et verifie. Les deux tables ensemble permettent la mesure
    #: a l'ensemble EXACT, qui est la seule qui ferme les deux sens.
    #:
    #: Ce qu'elle ne peut pas empecher, et il vaut mieux l'ecrire : on peut
    #: toujours ranger un vrai reglage ici. Mais c'est alors un geste explicite
    #: qui le NOMME outillage, pas un ajout silencieux -- et c'est tout ce
    #: qu'une frontiere de ce genre sait acheter.
    OUTILLAGE = ("self", "depart", "lister", "lister_volumes",
                 "compter_sous_dossiers", "porte_un_projet", "memoire",
                 "dossier_de_repli")

    def __init__(self, depart: Path | str | None = None, *,
                 montrer_fichiers: bool = False,
                 accepte: Callable[[Path], bool] | None = None,
                 selection_multiple: bool = False,
                 lister: Callable[[Path], Sequence[Path]] | None = None,
                 lister_volumes: Callable[[], Sequence[Path] | None] | None = None,
                 compter_sous_dossiers: Callable[[Path], int | None] | None = None,
                 porte_un_projet: Callable[[Path], bool] | None = None,
                 memoire: MemoireDeSession | None = None,
                 dossier_de_repli: Path | None = None) -> None:
        self.montrer_fichiers = montrer_fichiers
        self.selection_multiple = selection_multiple
        #: Les chemins coches, associes a leur nature (dossier ou non). La
        #: nature est retenue AU COCHAGE plutot que redemandee au tri : un
        #: volume debranche entre les deux rendrait l'ordre instable, et un
        #: `is_dir()` par comparaison ferait payer le tri en appels systeme.
        self._selection: dict[Path, bool] = {}
        #: **La resolution d'une coche, payee AU COCHAGE** (AC 4.7,
        #: `EPIC11-ARB-120`). Chemin coche -> `{fichier: octets}`, ou ``None``
        #: quand la mesure n'a pas pu se faire.
        #:
        #: La revue du 2026-08-31 a mesure ce que coutait de ne pas l'avoir :
        #: **trois parcours recursifs complets plus un `stat()` par fichier a
        #: chaque rendu de trame** -- soit a chaque frappe de fleche. C'est
        #: exactement la latence que l'AC 4.6 de la 11.2b avait fait fermer, et
        #: l'AC 4.7 disait mot pour mot l'inverse de ce qui etait livre.
        #:
        #: Le memo porte les OCTETS par fichier, et pas seulement un total :
        #: c'est ce qui permet de dedoublonner deux coches qui se recouvrent --
        #: un dossier et un fichier qu'il contient se comptaient DEUX fois.
        self._resolu: dict[Path, dict[Path, int] | None] = {}
        self._accepte = accepte or (lambda _: True)
        self._lister = lister or _lister_le_disque
        #: Injectable pour la meme raison que `lister` : c'est ce qui permet de
        #: rejouer la liste des volumes Windows sur une machine qui n'en a pas.
        self._lister_les_volumes = lister_volumes or volumes_du_systeme
        self._compter = compter_sous_dossiers or self._compter_par_defaut
        self._porte_un_projet = porte_un_projet or (lambda _: False)
        self.memoire = memoire if memoire is not None else MemoireDeSession()
        self._repli = Path(dossier_de_repli) if dossier_de_repli else Path.home()

        # `EPIC11-ARB-54` : le dernier dossier valide de la session prime sur le
        # dossier de lancement. Sur un parcours Scan puis Pdf, on ne retraverse
        # pas trois fois la meme arborescence.
        candidat = Path(depart) if depart is not None else Path.cwd()
        if self.memoire.dernier_valide is not None:
            candidat = self.memoire.dernier_valide

        self.montrer_caches = False
        self.saisie: str | None = None      # `None` : la liste a le focus
        self.caret = 0                      # position d'insertion dans la saisie
        #: Le FICHIER que la saisie designe, quand elle en designe un (story
        #: 11.15). Il survit juste ce qu'il faut : le temps que `Tab` rende la
        #: main a la liste, dont `relire()` remet le curseur a zero. Sans lui,
        #: la story livrerait un curseur pose qui s'evapore a la frappe
        #: suivante -- une fonction a moitie, ce qu'elle existe pour fermer.
        self._pointe: Path | None = None
        self.curseur = 0
        self.premier_visible = 0
        self.caches_masques = 0
        #: Vrai tant que le dossier courant s'est LU. Faux ne veut pas dire
        #: « vide » : voir `_lister_le_disque`.
        self.dossier_lisible = True
        #: Vrai quand la liste montre les VOLUMES et non un dossier. C'est un
        #: etat de la LISTE, pas un dossier courant : `self.dossier` continue
        #: de porter la derniere racine visitee, parce que c'est de la que la
        #: saisie doit resoudre un chemin relatif et c'est la qu'on revient.
        self.aux_volumes = False
        self._mesure_caches = ""
        self.entrees: list[Entree] = []
        self._refus = ""
        self.dossier = self._premier_lisible(candidat)
        self.relire()

    # -- lecture -------------------------------------------------------------

    def _premier_lisible(self, candidat: Path) -> Path:
        """Le dossier de depart, ou le repli s'il n'est plus lisible.

        `EPIC11-ARB-54` : « si le dossier de depart n'est plus lisible (volume
        debranche en cours de session), l'explorateur ouvre sur le dossier
        personnel et **le dit**. Il ne refuse pas de s'ouvrir. » Un explorateur
        qui leve au montage rendrait l'ecran inatteignable.
        """
        try:
            # `resolve(strict=False)` reecrivait ICI tout le chemin : le
            # dossier de depart atteint par un lien s'ouvrait sur sa cible
            # reelle, et `←` remontait ailleurs que d'ou l'on venait (AC 6.8).
            candidat = normaliser(candidat)
            if candidat.is_dir():
                return candidat
        except OSError:
            pass
        self._refus = "dossier de depart illisible -- ouvert sur le dossier personnel"
        return self._repli

    def reprendre_la_memoire(self, memoire: MemoireDeSession) -> bool:
        """Rebrancher cet explorateur sur `memoire`, et s'y replacer. Rend vrai
        si le dossier courant a change.

        **Pourquoi ce n'est pas suffisant d'injecter la memoire a la
        construction**, ce que le constructeur sait deja faire : les
        explorateurs du produit sont montes **une fois**, avec leur ecran, et
        cet ecran est reutilise a chaque visite. `EcranProjet` est meme
        construit AVANT l'application, dans `ChaineReelle` -- il n'a donc
        aucune application a interroger a ce moment. Un explorateur qui ne
        lirait la memoire qu'a sa construction retiendrait le dossier de la
        toute premiere visite et rien d'autre, ce qui se lit exactement comme
        le defaut d'origine.

        **Un dossier memorise devenu illisible ne deplace RIEN.** Le volume
        debranche entre deux visites est le cas nominal de cette famille (les
        rushes vivent souvent sur un disque externe) : passer alors au dossier
        personnel ferait perdre la position courante en plus du souvenir. La
        cascade de `_premier_lisible` reste celle du DEPART, ou elle a un sens
        -- il n'y a pas d'autre position a garder.
        """
        self.memoire = memoire
        cible = memoire.dernier_valide
        if cible is None:
            return False
        try:
            cible = normaliser(cible)
            if not cible.is_dir():
                return False
        except OSError:
            return False
        if cible == self.dossier and not self.aux_volumes:
            # `and not self.aux_volumes` : la memoire pointe peut-etre le
            # dossier courant, mais on est UN CRAN AU-DESSUS de lui. Sans cette
            # moitie, revenir sur l'ecran laissait la liste des volumes
            # affichee pour un souvenir qui designe un dossier.
            return False
        self.aux_volumes = False
        self.dossier = cible
        self._refus = ""
        if self.dans_la_saisie:
            # **La barre d'adresse ne survit pas au deplacement.** Elle porte
            # le chemin de l'ANCIEN dossier -- pose par `basculer_la_saisie` a
            # la visite precedente -- et la laisser afficherait une adresse qui
            # n'est plus celle de la liste en dessous. `entrer` et `remonter`
            # ne rencontrent pas ce cas : le routeur ne les atteint jamais
            # depuis la saisie. La reprise, elle, arrive de l'exterieur.
            self.saisie = None
            self.caret = 0
        # **La pointe non plus** (finding de la couche 3 de la revue de 11.15).
        # `_pointe` est le chemin de FICHIER que la saisie a designe ; il est
        # consomme par `basculer_la_saisie`, qui est la sortie NORMALE de la
        # saisie. Celle-ci en est une TROISIEME, et elle arrive de l'exterieur.
        # Sans cette ligne, le curseur se reposait sur un fichier designe deux
        # changements de dossier plus tot.
        self._pointe = None
        # `relire` remet curseur et fenetre a zero : arriver au milieu d'une
        # liste qu'on n'a pas parcourue n'aurait aucun sens.
        self.relire()
        return True

    def _compter_par_defaut(self, dossier: Path) -> int | None:
        """Le compte du dossier, ou `None` si le dossier ne se lit pas.

        **Ce qu'on compte suit ce que le SITE cherche** (`EPIC11-ARB-121`, Egan
        le 2026-08-31 : « c'est une bonne feature, j'aimerais bien la
        conserver »). Sur un ecran qui cherche des projets, « combien de
        sous-dossiers » repond a « y a-t-il des candidats la-dedans » ; sur un
        ecran qui cherche des planches a scanner, il ne repond a rien, et ce
        qu'on veut savoir est combien de fichiers on trouverait en entrant.

        Le compte se derive donc de `montrer_fichiers`, **sans ajouter un
        quatrieme reglage** : `EPIC11-ARB-102` n'en ouvre qu'un seul.

        `None` et `0` ne sont **pas** la meme information : `None` se rend `·`,
        `0` se rend `0`. Rendre `0` pour un dossier illisible serait un chiffre
        faux presente comme une mesure -- meme regle que `projets.Compteurs`.
        """
        try:
            if self.montrer_fichiers:
                return sum(1 for e in dossier.iterdir() if not e.is_dir())
            return sum(1 for e in dossier.iterdir() if e.is_dir())
        except OSError:
            return None

    def relire(self) -> None:
        """Recharger la liste du dossier courant, curseur et fenetre remis a zero.

        **L'ordre des trois filtres porte deux corrections.** Le compte des
        caches se prend APRES le filtre `montrer_fichiers` (finding `E14`) :
        pris avant, il annoncait des « dossiers caches » qui etaient des
        fichiers, et que `Ctrl+H` ne pouvait pas montrer. Et un lien symbolique
        casse rejoint les dossiers plutot que les fichiers (finding `E16`),
        faute de quoi il disparaissait de la variante « dossiers seuls ».

        Aucune colonne de droite n'est calculee ici : elles le sont au rendu,
        pour les lignes visibles seulement (AC 4.6).
        """
        if self.aux_volumes:
            self._relire_les_volumes()
            return
        brut = self._lister(self.dossier)
        self.dossier_lisible = brut is not None

        # `(chemin, lisible)` : la nature de chaque entree est etablie UNE
        # fois, ici, et voyage jusqu'a `_entree_de_dossier` -- deux `is_dir()`
        # par ligne sur un volume reseau, c'est deux fois trop.
        dossiers: list[tuple[Path, bool]] = []
        fichiers: list[Path] = []
        for chemin in (brut or []):
            if self._est_dossier(chemin):
                dossiers.append((chemin, True))
            elif _lien_illisible(chemin):
                dossiers.append((chemin, False))
            else:
                fichiers.append(chemin)
        if not self.montrer_fichiers:
            fichiers = []

        caches_dossiers = sum(1 for c, _ in dossiers if _est_cache(c.name))
        caches_fichiers = sum(1 for c in fichiers if _est_cache(c.name))
        self.caches_masques = (0 if self.montrer_caches
                               else caches_dossiers + caches_fichiers)
        self._mesure_caches = ("" if self.montrer_caches else
                               _mesure_des_caches(caches_dossiers,
                                                  caches_fichiers))
        if not self.montrer_caches:
            dossiers = [(c, l) for c, l in dossiers if not _est_cache(c.name)]
            fichiers = [c for c in fichiers if not _est_cache(c.name)]

        dossiers.sort(key=lambda paire: _sans_accent(paire[0].name))
        fichiers.sort(key=lambda c: _sans_accent(c.name))

        self.entrees = ([self._entree_de_dossier(c, lisible)
                         for c, lisible in dossiers]
                        + [self._entree_de_fichier(c) for c in fichiers])
        if self.selection_multiple and brut is not None:
            # **Le BRUT, jamais `self.entrees`** (`EPIC11-ARB-124`). Les entrees
            # ont deja subi `montrer_fichiers` et le filtre des caches : purger
            # contre elles faisait tomber une coche parce qu'on avait cesse de
            # la VOIR. Et `brut is not None` est l'autre moitie : sur un volume
            # debranche, `_lister_le_disque` rend `None`, la liste est vide, et
            # purger contre elle vidait TOUTE la selection.
            self._oublier_ce_qui_a_disparu(set(brut))
        self.curseur = 0
        self.premier_visible = 0

    def _relire_les_volumes(self) -> None:
        """La liste des volumes. **Elle ne passe par AUCUN des trois filtres.**

        Et c'est le point, plutot qu'une simplification : les trois filtres de
        `relire` mangeraient la liste, chacun a sa facon.

        * `_est_dossier` d'abord. Un lecteur de cartes vide ou un lecteur
          reseau deconnecte rend `False` a `is_dir()`, donc le volume tombait
          dans les fichiers -- et les fichiers sont supprimes quand
          `montrer_fichiers` est faux. Le volume qu'on cherche justement a
          voir pour savoir s'il est branche DISPARAISSAIT de la liste ;
        * le filtre des caches ensuite. `_est_cache` lit `chemin.name`, qui
          vaut la chaine vide pour une racine -- inoffensif aujourd'hui, faux
          des que `PREFIXES_CACHES` accueillerait la chaine vide ;
        * le tri enfin. Trier sur `name` trierait vingt-six racines sur la
          meme cle vide. L'ordre des volumes est celui que le systeme rend --
          les lettres croissantes sous Windows, `/` en tete ailleurs -- et
          c'est le seul ordre que l'operateur reconnaisse.

        Un volume est donc TOUJOURS un dossier de la liste, et sa lisibilite
        se dit **paresseusement**, par la colonne de droite : `·` quand il ne
        s'est pas lu, jamais `0` (`_colonne_de_compte`). Sonder les vingt-six
        lettres a la construction est exactement la latence qu'AC 4.6 existe
        pour empecher.
        """
        brut = self._lister_les_volumes()
        # `None` : la liste ne s'est pas faite. `[]` : il n'y a aucun volume.
        # La ligne d'etat et la liste vide disent l'une et l'autre.
        self.dossier_lisible = brut is not None
        volumes = list(brut or [])
        self.caches_masques = 0
        self._mesure_caches = ""
        self.entrees = [self._entree_de_dossier(chemin) for chemin in volumes]
        if self.selection_multiple and brut is not None:
            self._oublier_ce_qui_a_disparu(set(volumes))
        self.curseur = 0
        self.premier_visible = 0

    def _est_dossier(self, chemin: Path) -> bool:
        try:
            return chemin.is_dir()
        except OSError:
            return False

    def _entree_de_dossier(self, chemin: Path, lisible: bool = True) -> Entree:
        """L'entree d'un dossier. **Le comptage n'a pas lieu ici** (AC 4.6).

        ``lisible`` vient de `relire`, qui l'a etabli en classant l'entree. La
        branche illisible est la SEULE productrice d'une entree non entrable
        pour un dossier : elle porte `✕`, refuse l'entree, et se compte a part
        en ligne d'etat.
        """
        if not lisible:
            return Entree(chemin, True, jetons.marque("absent", "illisible"),
                          entrable=False, validable=False, illisible=True)
        if self._porte_un_projet(chemin):
            return Entree(chemin, True, jetons.marque("complete", "projet"),
                          porte_un_projet=True)
        # Un appelable, pas un nombre : `iterdir()` ne sera paye que si cette
        # ligne devient visible.
        return Entree(chemin, True, lambda c=chemin: self._colonne_de_compte(c))

    def _colonne_de_compte(self, chemin: Path) -> str:
        """Le texte de la colonne de droite d'un dossier, compte a l'appui."""
        compte = self._compter(chemin)
        nom = "fichier" if self.montrer_fichiers else "sous-dossier"
        if compte is None:
            # `·`, jamais `0` : un volume lent ou debranche n'est pas un dossier
            # vide, et l'ecran ne doit pas les confondre.
            return f"{jetons.GLYPHES['neutre']} {nom}s"
        return f"{compte} {nom}{'s' if compte > 1 else ''}"

    def _entree_de_fichier(self, chemin: Path) -> Entree:
        if not self._accepte(chemin):
            # Visible mais non validable : un fichier absent de la liste ferait
            # croire qu'il n'est pas la. La couleur `muted` DOUBLE le `·`, elle
            # ne le remplace pas (`DESIGN.md` section 5, regle 1).
            return Entree(chemin, False,
                          f"{jetons.GLYPHES['neutre']} pas une source",
                          entrable=False, validable=False)
        try:
            taille = taille_lisible(chemin.stat().st_size)
        except OSError:
            taille = f"{jetons.GLYPHES['neutre']} taille inconnue"
        return Entree(chemin, False, taille, entrable=False)

    # -- ce que la fenetre montre -------------------------------------------

    @property
    def hauteur_de_liste(self) -> int:
        """Les lignes disponibles pour les entrees, `…` compris."""
        return HAUTEUR_LISTE

    def fenetre(self) -> tuple[int, int]:
        """`(premier, dernier)` rangs visibles, bornes incluses.

        **Le calcul vit dans `jetons`, pas ici** : `cadences` en portait deja
        une copie, et la liste des rushes en aurait fait une troisieme. Le
        motif reste le sien -- une ligne est reservee a chaque `…` **avant**
        le decoupage, sans quoi la derniere entree se cacherait derriere le
        `…` qui annonce qu'elle existe.
        """
        return jetons.fenetre_de_liste(len(self.entrees),
                                       self.premier_visible, HAUTEUR_LISTE)

    def _recadrer(self) -> None:
        """Faire suivre la fenetre au curseur, d'un rang a la fois."""
        self.premier_visible = jetons.recadrer_la_fenetre(
            self.premier_visible, self.curseur, len(self.entrees),
            HAUTEUR_LISTE)

    @property
    def entree_courante(self) -> Entree | None:
        if not self.entrees or not 0 <= self.curseur < len(self.entrees):
            return None
        return self.entrees[self.curseur]

    # -- navigation ----------------------------------------------------------

    def deplacer(self, pas: int) -> bool:
        """`↑↓` : le curseur reste **dans la liste**, il n'en sort jamais.

        C'est la moitie de `EPIC11-ARB-50`. L'autre moitie est que les deux
        etiquettes ne sont pas des cibles : les deux ensemble garantissent qu'il
        n'y a jamais deux glyphes de curseur a l'ecran.
        """
        if not self.entrees:
            return False
        self.curseur = min(max(self.curseur + pas, 0), len(self.entrees) - 1)
        self._recadrer()
        self._oublier_le_refus()
        return True

    def _oublier_le_refus(self) -> None:
        """Le refus MEURT au premier geste qui change ce que l'ecran montre.

        Findings `F4`, `E7`, `E8` -- trois symptomes d'un seul defaut : `_refus`
        n'etait efface que par `entrer()` reussi, `remonter()` et
        `_suivre_la_saisie()`, et `etat()` le rend en priorite absolue. Trois
        consequences mesurees :

        * apres un refus d'entree, la ligne d'etat continuait de nommer une
          entree qui n'etait plus sous le curseur ;
        * pose au montage, « dossier de depart illisible » masquait **toutes**
          les mesures pour le reste de la session -- `EPIC11-ARB-56` veut une
          mesure en ligne d'etat, et un message d'accueil qui ne s'efface pas
          la supprime definitivement ;
        * sortir de la saisie sur une adresse inexistante laissait la liste
          vide **et** le message a demeure : l'ecran devenait une impasse.

        Le cycle est donc : le refus **nait** d'un geste refuse (`entrer` sur
        une entree non entrable), d'un depart illisible au montage, ou d'une
        adresse saisie qui ne designe rien ; il **meurt** au premier geste qui
        aboutit -- un deplacement, un saut trouve, une bascule des caches, un
        changement de dossier, une sortie de saisie. Un geste qui n'aboutit pas
        ne l'efface pas : il n'a rien change a ce que l'ecran montre.
        """
        self._refus = ""

    def entrer(self) -> bool:
        """`→` : descendre dans le dossier sous le curseur.

        Depuis la liste des volumes, c'est la sortie du mode : le volume choisi
        DEVIENT le dossier courant.
        """
        entree = self.entree_courante
        if entree is None or not entree.entrable:
            if entree is not None and not entree.entrable:
                # **Le nom NU, sans la barre finale.** `Entree.nom` est fait
                # pour la colonne de gauche, ou la barre dit « dossier » ; en
                # prose elle se lit comme une faute de frappe. Et le repli sur
                # le chemin entier est la pour la racine, dont le `name` est
                # vide -- « ne se lit pas » tout court ne dirait pas de quoi.
                nom = entree.chemin.name or str(entree.chemin)
                self._refus = f"{nom} ne se lit pas"
            return False
        self.aux_volumes = False
        self.dossier = entree.chemin
        self._refus = ""
        self.relire()
        return True

    def remonter(self) -> bool:
        """`←` : le dossier parent -- et, depuis une racine, LES VOLUMES.

        **La ligne du haut annoncait « Volumes » et la touche ne menait nulle
        part** (bloquant rapporte par Egan le 2026-09-07, sous Windows :
        « impossible d'atteindre les volumes par l'explorateur de fichiers.
        Rien ne se passe si j'essaie de remonter aux volumes »). Le parent
        d'une racine EST cette racine -- `Path("C:\\\\").parent` vaut `C:\\` --,
        donc la garde qui empeche la boucle infinie avalait aussi le seul geste
        par lequel on change de volume. Un `D:` de rushes n'etait atteignable
        qu'en tapant son chemin, ce que l'explorateur existe pour eviter.

        Le mode est un **cran de plus au-dessus des racines**, pas un dossier :
        `self.dossier` ne bouge pas. C'est ce qui laisse la saisie resoudre
        depuis la derniere racine visitee, et ce qui fait qu'annuler ne perd
        pas la position.

        Au-dessus des volumes il n'y a rien, et la ligne redevient inactive --
        cette fois pour de bon, et l'etiquette le dit (`nom_court_du_parent`
        rend alors la chaine vide).
        """
        if self.aux_volumes:
            return False
        parent = self.dossier.parent
        if parent == self.dossier:
            self.aux_volumes = True
            self._refus = ""
            self.relire()
            return True
        self.dossier = parent
        self._refus = ""
        self.relire()
        return True

    def sauter(self, caractere: str) -> bool:
        """Un caractere imprimable saute au nom SUIVANT qui commence par lui.

        **C'est ce qui rend une liste de deux cents dossiers praticable**, et
        c'est pourquoi aucune lettre n'est un raccourci d'action
        (`EPIC11-ARB-49`). Chiffres compris : les dossiers d'Egan s'appellent
        `01_reperages`, et sans les chiffres le saut ne servirait a rien.

        **Le balayage part de l'entree suivante et fait le tour complet**, la
        courante testee en dernier. Sans le tour, le saut s'arretait a la
        premiere correspondance et redevenait inoperant la ou il sert le plus :
        sur `01_`, `02_`, `03_` -- l'exemple ci-dessus, le cas nominal d'Egan --
        `0` appuye trois fois ne quittait jamais `01_reperages` (finding `E5`
        de la revue de la vague 2 bis). Le tour complet garantit qu'aucune
        correspondance n'est inatteignable, y compris quand la seule est celle
        que le curseur occupe deja.
        """
        if not caractere or not caractere.isprintable() or not self.entrees:
            return False
        cible = _sans_accent(caractere)
        total = len(self.entrees)
        for decalage in range(1, total + 1):
            rang = (self.curseur + decalage) % total
            if _sans_accent(self.entrees[rang].chemin.name).startswith(cible):
                self.curseur = rang
                self._recadrer()
                self._oublier_le_refus()
                return True
        return False

    def basculer_les_caches(self) -> bool:
        """`Ctrl+H`. Le compte masque est **toujours dit** en ligne d'etat."""
        self.montrer_caches = not self.montrer_caches
        self.relire()
        self._oublier_le_refus()
        return True

    # -- la saisie du chemin -------------------------------------------------

    @property
    def dans_la_saisie(self) -> bool:
        return self.saisie is not None

    def basculer_la_saisie(self) -> bool:
        """`Tab` entre dans la saisie et en sort. **Et rien d'autre.**

        `EPIC11-ARB-51`, sur une contradiction relevee par Egan : « Le curseur
        est toujours dans la liste. D'ou la proposition : tab entre et sort de
        la saisie. » Donner a `Tab` un second role -- entrer dans un dossier --
        rendait la saisie inatteignable au clavier.
        """
        if self.dans_la_saisie:
            self.saisie = None
            # Finding `E7` : sans cette relecture, sortir de la saisie sur une
            # adresse inexistante rendait la main a une liste VIDE, sur un
            # dossier qui, lui, existe -- `↑↓`, `→` et toutes les lettres
            # inertes, et le message d'erreur toujours affiche.
            self._oublier_le_refus()
            self.relire()
            # **Et le curseur pose par un chemin de FICHIER survit a ce
            # `Tab`** (story 11.15). La relecture ci-dessus est la frontiere
            # `E7` et elle ne bouge pas ; ce qui s'ajoute est de reposer
            # ensuite le curseur la ou la saisie l'avait mis. Sans cela, le
            # geste qu'Egan demande -- coller le chemin, revenir a la liste --
            # ramenerait a la premiere des cent cinquante lignes qu'il cherche
            # justement a ne plus defiler.
            pointe, self._pointe = self._pointe, None
            if pointe is not None and not self._poser_le_curseur_sur(pointe):
                # **Le retour de la pose se LIT** (finding `C2-1` de la couche 2
                # de la revue). Il etait ignore ici alors que
                # `_suivre_la_saisie` le garde : `_oublier_le_refus()` venait
                # d'effacer la phrase, le curseur restait au rang 0, et le
                # geste d'Egan -- coller le chemin, `Tab`, `Entree` -- rendait
                # **un autre fichier**, sans un mot. Mesure sur les deux
                # regimes nominaux : un ecran qui ne montre pas les fichiers,
                # et un fichier cache.
                self._refus = self._pourquoi_hors_liste(pointe)
            return True
        # Depuis la liste des volumes, la saisie part de la derniere racine
        # visitee : c'est le seul chemin reel que l'ecran ait sous la main, et
        # `LISTE_DES_VOLUMES` n'est pas une adresse qu'on puisse editer.
        self.saisie = str(self.dossier)
        self.caret = len(self.saisie)
        return True

    def frapper(self, caractere: str) -> bool:
        """Un caractere dans la saisie. La liste suit, en direct."""
        if not self.dans_la_saisie or not caractere.isprintable():
            return False
        self.saisie = (self.saisie[:self.caret] + caractere
                       + self.saisie[self.caret:])
        self.caret += len(caractere)
        self._suivre_la_saisie()
        return True

    def coller(self, texte: str) -> bool:
        """`Ctrl+V`, ou l'evenement de collage du terminal.

        Les deux sont branches par l'ecran : la console Windows historique livre
        la touche sans l'evenement.
        """
        if not self.dans_la_saisie or not texte:
            return False
        propre = texte.strip().strip('"').replace("\n", "")
        self.saisie = self.saisie[:self.caret] + propre + self.saisie[self.caret:]
        self.caret += len(propre)
        self._suivre_la_saisie()
        return True

    def effacer(self) -> bool:
        if not self.dans_la_saisie or self.caret == 0:
            return False
        self.saisie = self.saisie[:self.caret - 1] + self.saisie[self.caret:]
        self.caret -= 1
        self._suivre_la_saisie()
        return True

    def deplacer_le_caret(self, pas: int) -> bool:
        """Dans la saisie, `←→` deplacent le POINT D'INSERTION, pas le dossier."""
        if not self.dans_la_saisie:
            return False
        self.caret = min(max(self.caret + pas, 0), len(self.saisie))
        return True

    def _suivre_la_saisie(self) -> None:
        """La liste suit le chemin saisi. **TROIS natures, jamais deux.**

        Un dossier fait afficher son contenu ; un FICHIER fait afficher son
        dossier, curseur pose sur lui (story 11.15, `EPIC11-ARB-283`) ; un
        chemin qui n'existe vraiment pas vide la liste et le dit -- et ce
        dernier cas **n'est pas un refus** : rien ne passe en `state-absent`,
        une frappe en cours n'est pas une erreur.

        **Ce que la deuxieme branche repare, mesure avant d'etre ecrite** :
        `cible_de_validation()` rendait deja le fichier -- donc `⏎` le
        validait -- pendant que la liste se vidait et que la ligne d'etat
        annoncait « aucun dossier n'existe a cette adresse ». L'ecran
        DECOURAGEAIT un geste qu'il savait executer, ce qui est pire qu'une
        fonction absente. Coller le chemin d'un fichier depuis le Finder ou
        l'Explorateur est exactement ce que produit un copier/coller, et c'est
        le geste qu'Egan a demande.

        **L'ordre des trois gestes de la branche fichier est porteur** :
        `relire()` remet `curseur` et `premier_visible` a zero, donc le curseur
        se pose APRES, jamais avant. C'est la meme famille que le finding `E7`
        que ce module porte deja -- un etat pose puis ecrase par une relecture,
        sans erreur et sans trace.

        **Le cout en appels systeme est borne a un de plus, et seulement quand
        `is_dir()` a dit non.** Cette methode tourne sur CHAQUE caractere tape :
        `lexists` n'est donc pas ajoute a `normaliser` (qui reste purement
        lexicale, cf. son docstring) mais ici, dans la seule branche ou il
        change quelque chose.

        **`lexists` et non `exists`** : un lien symbolique casse EXISTE comme
        entree de son dossier, `relire()` le montre (finding `E16` : « un lien
        casse vers un rush deplace est LE symptome que l'operateur cherche »),
        et lui repondre « rien n'existe a cette adresse » serait le meme
        mensonge que celui que cette story ferme.
        """
        # `projets.resoudre` EST `normaliser` (une seule implementation dans
        # toute la TUI). Elle etait appelee ici a chaque frappe quand elle
        # resolvait encore recursivement : la contradiction avec l'AC 6.8 etait
        # sur le chemin nominal de la saisie, pas dans un cas limite.
        cible = normaliser(self.saisie) if self.saisie else self.dossier
        if cible.is_dir():
            # **La saisie sort de la liste des volumes**, sans quoi `relire`
            # rejouerait les volumes et la liste ne suivrait pas ce qu'on tape.
            self.aux_volumes = False
            self.dossier = cible
            self._pointe = None
            self._refus = ""
            self.relire()
            return
        if os.path.lexists(cible):
            self.aux_volumes = False
            self.dossier = cible.parent
            self.relire()              # <- remet curseur et premier_visible a 0
            self._pointe = cible
            if self._poser_le_curseur_sur(cible):
                self._refus = ""
            else:
                # AC 6 : la liste ne PEUT PAS le montrer, elle le DIT. Un
                # curseur laisse a zero en silence ferait croire que le fichier
                # est la premiere entree du dossier.
                self._refus = self._pourquoi_hors_liste(cible)
            return
        self._pointe = None
        self.entrees = []
        self.curseur = 0
        self.premier_visible = 0
        self._refus = ADRESSE_INEXISTANTE

    def _poser_le_curseur_sur(self, chemin: Path) -> bool:
        """Poser le curseur sur `chemin` dans la liste courante, et recadrer.

        **L'appariement se fait par identite de `Path`, jamais par nom** : deux
        dossiers peuvent porter le meme nom de fichier, et `normaliser` a deja
        resolu la forme du chemin saisi -- comparer les noms rendrait vrai pour
        un homonyme d'un autre dossier.

        Le recadrage passe par :meth:`_recadrer`, jamais par une arithmetique
        recopiee : la borne haute de la fenetre depend de la presence du `…` de
        tete, qui depend elle-meme de `premier_visible` (cf.
        `jetons.recadrer_la_fenetre`).
        """
        for rang, entree in enumerate(self.entrees):
            if entree.chemin == chemin:
                self.curseur = rang
                self._recadrer()
                return True
        return False

    def _pourquoi_hors_liste(self, cible: Path) -> str:
        """Laquelle des trois raisons empeche `cible` de figurer dans la liste.

        **Les FAITS d'abord, le reglage du site ensuite** (finding `C2-2` de la
        couche 2 de la revue). La premiere redaction repondait
        `montrer_fichiers` avant d'avoir etabli quoi que ce soit, et se
        trompait donc dans trois regimes mesures : un dossier parent
        **illisible** (rien n'a ete lu, le reglage n'y est pour rien, et la
        phrase masquait le compte de sous-dossiers) ; un fichier **disparu**
        entre le `lexists` et la relecture ; et surtout un **lien symbolique
        casse**, que :meth:`relire` range parmi les DOSSIERS -- il figure donc
        dans la liste meme quand les fichiers n'y sont pas, et nommer
        `montrer_fichiers` designait un obstacle qui n'existait pas.

        Une fois les faits etablis, l'ordre des deux reglages se justifie par
        ce que l'operateur peut CHANGER. `montrer_caches` est a portee d'une
        touche ; `montrer_fichiers` est un reglage du SITE, hors de sa main.
        Sur un fichier cache d'un ecran qui ne montre aucun fichier, les deux
        s'appliquent -- nommer le masquage suggererait un geste qui, la, ne
        ferait rien apparaitre. On nomme celle qui BORNE l'autre.
        """
        if not self.dossier_lisible or not os.path.lexists(cible):
            # Rien n'a ete lu, ou il n'y a plus rien a lire : aucun reglage
            # n'est en cause.
            return FICHIER_ABSENT_DE_LA_LISTE
        # Ce que la liste porte de toute facon : les dossiers, et les liens
        # casses que `relire` range avec eux.
        porte_par_la_liste = (self._est_dossier(cible)
                              or _lien_illisible(cible)
                              or self.montrer_fichiers)
        if not porte_par_la_liste:
            return FICHIERS_NON_MONTRES
        # **`and not self.montrer_caches` est INATTEIGNABLE dans un sens depuis
        # la reordonnance ci-dessus, et il reste.** Mesure : le retirer ne
        # change aucun verdict, parce qu'une cible cachee ET montree figure
        # forcement dans la liste -- donc `_pourquoi_hors_liste` n'est pas
        # appelee. La clause n'est donc porteuse que dans l'autre sens (cachee
        # et masquee), ou elle l'est bel et bien.
        #
        # Elle est gardee plutot que simplifiee, et c'est un choix : cette nuit
        # meme, une couche de revue a declare une garde inatteignable qu'une
        # autre a mesuree atteignable ET porteuse -- sans elle, un lot entier
        # etait perdu. Une clause juste qui ne coute rien vaut mieux qu'une
        # simplification qui repose sur l'exhaustivite d'un raisonnement.
        if _est_cache(cible.name) and not self.montrer_caches:
            return FICHIER_CACHE
        return FICHIER_ABSENT_DE_LA_LISTE

    # -- validation ----------------------------------------------------------

    # -- la selection multiple (`EPIC11-ARB-102` a `-104`) --------------------

    @staticmethod
    def _cle_d_affichage(chemin: Path, est_dossier: bool) -> tuple:
        """L'ordre de la LISTE, reproduit hors d'elle.

        `relire()` pose les dossiers d'abord, puis les fichiers, chacun trie
        sans accent. La selection peut couvrir plusieurs dossiers : le parent
        entre donc en tete de cle, sans quoi deux entrees de meme nom dans deux
        dossiers se rangeraient l'une dans l'autre.
        """
        return (str(chemin.parent), not est_dossier, _sans_accent(chemin.name))

    @property
    def selection(self) -> tuple[Path, ...]:
        """Les chemins coches, dans l'ordre d'AFFICHAGE (AC 4.1).

        Jamais dans l'ordre de cochage : celui-la n'est reproductible pour
        personne, et deux operateurs cochant les memes fichiers dans un ordre
        different obtiendraient deux lots differents.
        """
        return tuple(sorted(
            self._selection,
            key=lambda c: self._cle_d_affichage(c, self._selection[c])))

    def est_cochee(self, chemin: Path) -> bool:
        return chemin in self._selection

    def basculer_la_coche(self) -> str | None:
        """`Espace` coche et decoche l'entree sous le curseur (`EPIC11-ARB-103`).

        Le geste n'est pas neuf dans le produit : `cadences.ListeDeCadences`
        le porte deja, et son docstring nomme la meme frontiere avec
        `EPIC11-ARB-45` -- « cette liste-ci n'est pas un ecran a issue unique,
        donc `Espace` garde son role, et la case avec ».

        Rend le motif du refus quand l'entree ne se coche pas, et ``None``
        quand la bascule a eu lieu. Une frappe ignoree en silence laisserait
        croire a une touche morte.
        """
        if not self.selection_multiple:
            return None
        entree = self.entree_courante
        if entree is None:
            return None
        if not entree.validable:
            return (f"{entree.nom} ne peut pas etre retenu"
                    if not entree.illisible
                    else f"{entree.nom} ne se lit pas")
        if entree.chemin in self._selection:
            del self._selection[entree.chemin]
            self._resolu.pop(entree.chemin, None)
        else:
            self._selection[entree.chemin] = entree.est_dossier
            self._resolu[entree.chemin] = self._resoudre(entree.chemin,
                                                         entree.est_dossier)
        self._oublier_le_refus()
        return None

    def _resoudre(self, chemin: Path,
                  est_dossier: bool) -> dict[Path, int] | None:
        """Ce qu'une coche apporte VRAIMENT au site : `{fichier: octets}`.

        Rend ``None`` quand la mesure n'a pas pu se faire -- jamais un total
        ampute, qui passerait pour un total.

        Un dossier est resolu **a travers le filtre du site**
        (`EPIC11-ARB-123`) : ce que le compte annonce est ce que le scan
        prendra, pas ce que le dossier contient.
        """
        try:
            if est_dossier:
                return {f: f.stat().st_size
                        for f in _fichiers_du_dossier(chemin,
                                                     retenu=self._retenu)}
            return {chemin: chemin.stat().st_size}
        except OSError:
            return None

    def _retenu(self, chemin: Path) -> bool:
        """Ce que le site accepte -- le MEME predicat qu'en surface.

        C'est le point du finding `R3` : `accepte` posait le `✕` sur
        `nn_refuse.txt` ligne a ligne, et ne s'appliquait pas a l'interieur
        d'un dossier coche. Un seul predicat, deux usages.
        """
        return self._accepte(chemin)

    def _oublier_ce_qui_a_disparu(self, presents: set[Path]) -> None:
        """Un chemin coche que le dossier courant ne porte plus sort (AC 4.4).

        **Borne au dossier COURANT**, et c'est la premiere moitie : une
        selection couvre plusieurs dossiers, et retirer ce qu'on ne voit pas
        viderait la selection a chaque pas de navigation. On ne retire que ce
        qui a disparu **la ou on regarde**.

        **Et une coche ne tombe que sur une disparition REELLE ET CONSTATEE**
        (`EPIC11-ARB-124`, Egan le 2026-08-31), ce qui est la seconde moitie et
        vit chez l'appelant : `presents` est le listing BRUT du disque, jamais
        la liste filtree, et l'appel ne se fait pas du tout quand le dossier ne
        s'est pas lu. Deux defauts de la revue tenaient a cette confusion --
        `Ctrl+H` decochait les caches retenus, et un volume debranche purgeait
        toute la selection. *Masque n'est pas absent, et un volume debranche
        n'est pas un dossier vide* : c'est la regle du `·` que ce module tient
        partout ailleurs, appliquee a l'objet le plus couteux a reconstruire.
        """
        perdus = [c for c in self._selection
                  if c.parent == self.dossier and c not in presents]
        for chemin in perdus:
            del self._selection[chemin]
            self._resolu.pop(chemin, None)

    def cible_de_validation(self) -> Path | None:
        """Ce que `⏎` validerait **maintenant**.

        La ligne du bas affiche exactement cela : elle suit le curseur, et c'est
        ce qui supprime toute ambiguite sur ce que la touche va faire.
        """
        if self.dans_la_saisie:
            return normaliser(self.saisie) if self.saisie else None
        entree = self.entree_courante
        if entree is None or not entree.validable:
            return None
        return entree.chemin

    def valider(self) -> "Path | list[Path] | None":
        """`⏎`. Une frappe, quelle que soit la position dans la liste.

        `EPIC11-ARB-49`, apres le grief d'Egan -- « long de scroller 150 dossiers
        ou fichiers pour valider ! ». La regle rejoint `EPIC11-ARB-45` a la
        lettre : la validation retient et suit ce qui est sous le curseur.
        """
        if self.selection_multiple and self._selection:
            # **La memoire s'ecrit AUSSI ici** (2026-09-06). Cette branche
            # rendait la selection sans rien memoriser, si bien que le seul
            # site du produit qui coche plusieurs sources -- le depot du Scan
            # -- aurait LU la memoire de sa famille sans jamais l'ecrire. Un
            # explorateur qui lit sans ecrire est exactement le mecanisme mort
            # que ce lot repare, en plus discret.
            #
            # **Le dossier PARCOURU, pas un parent commun des coches.** Deux
            # coches prises dans deux dossiers differents n'ont pas de parent
            # utile -- leur ancetre commun peut etre la racine du volume --,
            # alors que le dossier ou l'on etait au moment de valider est
            # precisement l'endroit ou l'on voudra revenir.
            self.memoire.dernier_valide = self.dossier
            # **Le type s'ELARGIT, il ne change pas** (AC 4.1 bis). Trois sites
            # du produit lisent ce retour et font `.name` dessus ; ils sont tous
            # en mode simple, ou la branche ci-dessous les sert comme avant.
            # Rendre une liste a un element en mode simple les casserait sans
            # qu'aucune etape n'echoue.
            return list(self.selection)
        cible = self.cible_de_validation()
        if cible is None:
            return None
        # Finding `E12` : valider une adresse inexistante memorisait son parent
        # inexistant, et l'explorateur SUIVANT s'ouvrait alors sur le dossier
        # personnel avec « dossier de depart illisible » -- un faux diagnostic
        # de volume debranche, pour une faute de frappe. La bifurcation « creer
        # ici » sur un chemin absent reste, elle, le comportement voulu : ce
        # qui est corrige est l'ecriture dans la memoire de session, pas le
        # retour de la fonction.
        try:
            dossier = cible if cible.is_dir() else cible.parent
            if dossier.is_dir():
                self.memoire.dernier_valide = dossier
        except OSError:
            pass
        return cible

    # -- rendu ---------------------------------------------------------------

    def nom_court_du_parent(self, ascii_seul: bool = False,
                            place: int | None = None) -> str:
        """Ce que la ligne du haut affiche, **tenu dans `place` colonnes**.

        « mettre juste la fleche et "...\\Documents\\" au lieu du chemin
        complet » (Egan, 2026-08-29). Le chemin complet du parent n'apprend
        rien : il ne differe de la barre d'adresse que par son dernier segment.

        `place` est ce qui reste au texte de l'etiquette une fois la fleche et
        la marge droite deduites. Un nom de dossier n'a **aucune borne** cote
        systeme de fichiers : sans elle, l'etiquette debordait a 78 colonnes en
        `--ascii` contre 76 en UTF-8 (finding `E10`, cas N).
        """
        if place is None:
            place = _place_d_etiquette(symbole(PARENT, ascii_seul),
                                       jetons.largeur_utile())
        if self.aux_volumes:
            # Au-dessus des volumes il n'y a rien. L'etiquette VIVE ne nomme
            # donc aucune cible -- une etiquette qui nomme ce que la touche
            # n'atteint pas est exactement le defaut que ce lot ferme.
            return ""
        parent = self.dossier.parent
        if parent == self.dossier:
            return jetons.abreger_nom(LISTE_DES_VOLUMES, place, ascii_seul)
        if parent.parent == parent:
            return jetons.abreger_nom(str(parent), place, ascii_seul)
        sep = _separateur(parent)
        tete = f"{symbole(ELLIPSE, ascii_seul)}{sep}"
        # Seul le NOM du parent s'abrege : `…\\` et la barre finale disent que
        # c'est un dossier et qu'il y a une racine au-dessus. Les perdre ferait
        # lire l'etiquette comme un nom de fichier.
        reste = place - jetons.colonnes(tete) - jetons.colonnes(sep)
        court = jetons.abreger_nom(parent.name, reste, ascii_seul)
        return f"{tete}{court}{sep}"

    def lignes(self, largeur: int = jetons.LARGEUR_PLANCHER,
               titre: str = "", libelle: str = "Dossier",
               ascii_seul: bool = False) -> list[str]:
        """Les 17 lignes de la zone centrale, dans l'ordre des maquettes."""
        utile = jetons.largeur_utile(largeur)
        corps = ["", "  " + titre, ""]
        touche = symbole(PARENT, ascii_seul)
        cible_du_haut = self.nom_court_du_parent(
            ascii_seul, _place_d_etiquette(touche, utile))
        # **Pas de touche quand elle ne mene nulle part.** Au-dessus des
        # volumes il n'y a rien : garder le `←` seul, sans cible, afficherait
        # une touche annoncee qui n'agit pas -- le mode de panne que la coque
        # nomme, et celui-la meme que ce lot ferme un cran plus bas. La ligne
        # reste, VIDE : la grille est a hauteur fixe et les deux etiquettes
        # encadrantes occupent toujours les memes lignes.
        corps.append(_etiquette(touche, cible_du_haut) if cible_du_haut else "")
        corps.append(self.ligne_d_adresse(utile, libelle, ascii_seul))
        corps.append(_filet(utile, ascii_seul))
        corps += self.lignes_de_liste(utile, ascii_seul)
        corps.append(_filet(utile, ascii_seul))
        corps.append(self.ligne_de_validation(ascii_seul, utile))
        return corps

    def ligne_d_adresse(self, utile: int, libelle: str,
                        ascii_seul: bool) -> str:
        """La barre d'adresse : **un seul** comportement d'abregement.

        `EPIC11-ARB-52`, sur la reserve d'Egan (« il va y avoir une saute c'est
        moyen »). Une fenetre glissante calee sur la FIN, avec `…` en tete quand
        le debut sort du champ -- que l'on tape ou non. Deux comportements
        feraient sauter le texte au moment ou l'on touche le clavier, c'est-a-
        dire exactement quand on le regarde.

        **`abreger_chemin` ne convient pas ici** : il coupe au milieu, ce qui
        est bon pour un chemin qu'on lit et faux pour un chemin qu'on tape.
        """
        table = jetons.glyphes(ascii_seul)
        marqueur = table["invite"] if self.dans_la_saisie else " "
        # La liste des volumes n'a pas d'adresse : afficher `str(self.dossier)`
        # y montrerait la racine d'ou l'on vient comme si c'etait ce que la
        # liste porte, c'est-a-dire un chemin faux presente comme une position.
        courant = (LISTE_DES_VOLUMES if self.aux_volumes
                   else str(self.dossier))
        texte = self.saisie if self.dans_la_saisie else courant
        place = utile - _COLONNE_VALEUR

        # **Le caret RECOUVRE un caractere, il ne s'insere pas**, et la fenetre
        # se calcule sur le texte NU. Insérer le caret avant de decouper
        # decalerait la troncature d'une colonne des qu'on entre dans la
        # saisie : le chemin sauterait d'un caractere au moment precis ou l'on
        # touche le clavier -- la « saute » qu'`EPIC11-ARB-52` existe pour
        # supprimer, en plus petit. La colonne du caret est reservee dans les
        # DEUX etats, par l'espace ajoute ici, pour que rien ne bouge non plus
        # quand on en sort.
        points = symbole(ELLIPSE, ascii_seul)
        if self.dans_la_saisie:
            corps, rang = _fenetre_de_saisie(texte, self.caret, place, points)
            corps = corps[:rang] + table["caret"] + corps[rang + 1:]
        else:
            corps = _queue(texte + " ", place, points).rstrip()
        tete = " " * _INDENT + libelle
        tete += " " * max(1, _COLONNE_VALEUR - 2 - jetons.colonnes(tete))
        return f"{tete}{marqueur} {corps}"

    def lignes_de_liste(self, utile: int, ascii_seul: bool) -> list[str]:
        """La zone de liste, a hauteur FIXE, `…` compris.

        **`utile` et `ascii_seul` descendent jusqu'a chaque ligne**, y compris
        celles qui n'ont pas de colonne de droite : sans `utile`, elles se
        mesuraient sur la largeur par defaut et non sur celle demandee ; sans
        `ascii_seul`, le repli n'atteignait pas la colonne de droite
        (findings `F7`, `F8`, `E10`).
        """
        table = jetons.glyphes(ascii_seul)
        total = len(self.entrees)
        rendues: list[str] = []
        if total == 0:
            # « vide » et « illisible » ne sont pas la meme information
            # (finding `E9`) : un dossier disparu entre le listage et l'entree
            # annoncait « aucun sous-dossier », c'est-a-dire une mesure, la ou
            # rien n'a pu etre mesure.
            if self.aux_volumes:
                vide = ("aucun volume" if self.dossier_lisible else
                        f"{table['absent']} volumes illisibles")
            else:
                vide = "aucun sous-dossier" if self.dossier_lisible else \
                    f"{table['absent']} dossier illisible"
            rendues.append(_ligne(vide, "", False, utile, ascii_seul))
            return rendues + [""] * (HAUTEUR_LISTE - len(rendues))

        premier, dernier = self.fenetre()
        points = symbole(ELLIPSE, ascii_seul)
        if premier > 0:
            rendues.append(_ligne(points, "", False, utile, ascii_seul))
        for rang in range(premier, dernier + 1):
            entree = self.entrees[rang]
            rendues.append(_ligne(entree.nom, entree.droite,
                                  rang == self.curseur, utile, ascii_seul,
                                  self._case(entree, table)))
        if dernier < total - 1:
            position = f"{premier + 1}-{dernier + 1} sur {total}"
            rendues.append(_ligne(points, position, False, utile, ascii_seul))
        return rendues + [""] * (HAUTEUR_LISTE - len(rendues))

    def _resume_de_la_selection(self, ascii_seul: bool = False) -> str:
        """« 3 fichiers selectionnes   471 Mo », ou ce qui n'a pas pu se mesurer.

        Le cardinal parle en FICHIERS, dossiers coches resolus
        (`EPIC11-ARB-120`) ; le poids qui manque se dit `·` plutot que de
        s'omettre, sinon un total ampute passerait pour un total.
        """
        cardinal = self._cardinal_de_la_selection()
        poids = self._poids_de_la_selection()
        table = jetons.glyphes(ascii_seul)
        tete = (f"{table['neutre']} fichiers"
                if cardinal is None
                else f"{cardinal} fichier{'s' if cardinal > 1 else ''}")
        queue = table['neutre'] if poids is None else taille_lisible(poids)
        # **L'accent est ECRIT, et il se REPLIE** -- deux findings de la revue
        # au meme endroit. Il perforait le repli ASCII (le premier texte
        # accentue jamais rendu par ce module, sous la frontiere `F7` que le
        # depot avait deja payee) ; le retirer partout aurait fait diverger le
        # produit des maquettes `X11`/`X11b` qu'Egan a validees, qui ecrivent
        # bien « selectionnes » avec ses accents. `replier_ascii` decompose et
        # retire les accents -- c'est exactement le geste que le separateur fait
        # six lignes plus bas.
        #
        # Et le pluriel suit la TETE : la branche non mesurable disait
        # « fichiers selectionne », tete plurielle et participe singulier.
        pluriel = "s" if (cardinal is None or cardinal > 1) else ""
        mot = _replie(f"s\u00e9lectionn\u00e9{pluriel}", ascii_seul)
        return f"{tete} {mot}   {queue}"

    def _case(self, entree: "Entree", table) -> str:
        """Les trois etats d'une case, tous de MEME largeur.

        Une entree non validable porte le glyphe d'absence au lieu d'une case,
        exactement comme une cadence refusee (`cadences.py:731`) : elle reste
        VISIBLE -- la masquer ferait croire qu'elle n'est pas la -- et la frappe
        n'est pas ignoree en silence, `basculer_la_coche` rend son motif.
        """
        if not self.selection_multiple:
            return ""
        if not entree.validable:
            return f" {table['absent']} "
        return table["coche" if entree.chemin in self._selection else "decoche"]

    def _fichiers_retenus(self) -> dict[Path, int] | None:
        """L'UNION des fichiers que la selection apporte, dedoublonnee.

        **Deux coches peuvent se recouvrir**, et c'est le cas nominal, pas une
        curiosite : l'AC 4.3 fait survivre la selection au changement de
        dossier, donc cocher `rushes/`, entrer, puis cocher `rushes/a.tiff`
        demande trois touches. Le total comptait alors ce fichier **deux fois**,
        en cardinal comme en poids -- un chiffre faux presente comme une mesure,
        exactement ce que `EPIC11-ARB-120` existe pour empecher. Un dictionnaire
        indexe par CHEMIN dedoublonne par construction.

        Rend ``None`` des qu'une coche n'a pas pu se mesurer : un total qui
        aurait silencieusement oublie un dossier debranche passerait pour
        complet.

        **Ce que cette fonction relit, et ce qu'elle ne relit pas.** Le contenu
        vient du memo pose au cochage : aucun parcours recursif, aucun `stat()`
        par fichier (AC 4.7). Mais elle verifie que chaque RACINE cochee est
        toujours la -- un `stat()` par coche, pas par fichier.

        Cette verification n'est pas un reste de l'ancienne version, c'est ce
        qui rend les deux AC compatibles. L'AC 4.8 veut qu'un dossier coche
        devenu illisible rende une mesure ABSENTE ; l'AC 4.7 interdit de le
        reparcourir a chaque trame. Un memo seul rendrait un total PERIME avec
        l'aplomb d'une mesure -- precisement le defaut que ce module refuse
        partout ailleurs. Le compromis est de bon rapport : le cout suit le
        nombre de coches, jamais le nombre de fichiers, la ou l'ancienne version
        faisait 1200 visites par frappe de fleche pour un seul dossier de 400
        fichiers.

        Et cela ne contredit pas `EPIC11-ARB-124` : la coche est **retenue** --
        rien n'est retire ici --, c'est la MESURE qui se dit absente.
        """
        union: dict[Path, int] = {}
        for chemin in self._selection:
            fichiers = self._resolu.get(chemin)
            if fichiers is None or not self._encore_mesurable(chemin):
                return None
            union.update(fichiers)
        return union

    @staticmethod
    def _encore_mesurable(chemin: Path) -> bool:
        """La racine cochee est-elle toujours lisible ? Un `stat()`, pas plus."""
        try:
            if not chemin.exists():
                return False
            return not chemin.is_dir() or os.access(chemin, os.R_OK)
        except OSError:
            return False

    def _poids_de_la_selection(self) -> int | None:
        """Le poids total des chemins coches, ou ``None`` si une mesure manque.

        `EPIC11-ARB-120` : un dossier coche est RESOLU -- son poids entre dans le
        total, parce que « a la fin ce sont bien les fichiers qui sont scannes »
        (Egan). La resolution se paie ICI, sur les seuls chemins coches, jamais
        sur chaque ligne de la liste : la colonne de droite reste paresseuse.

        ``None`` plutot qu'un total partiel quand un chemin ne se lit plus : un
        poids qui aurait silencieusement oublie un dossier debranche serait un
        chiffre faux presente comme une mesure.
        """
        fichiers = self._fichiers_retenus()
        return None if fichiers is None else sum(fichiers.values())

    def _cardinal_de_la_selection(self) -> int | None:
        """Le nombre de FICHIERS retenus, dossiers coches resolus.

        Le compte parle en fichiers et jamais en « 1 dossier et 3 fichiers » :
        deux unites melangees ne diraient pas ce qui va etre lu.
        """
        fichiers = self._fichiers_retenus()
        return None if fichiers is None else len(fichiers)

    def ligne_de_validation(self, ascii_seul: bool = False,
                            utile: int = jetons.largeur_utile()) -> str:
        """L'etiquette du bas : elle **suit le curseur**, et tient la grille.

        Elle dit ce que `⏎` validerait maintenant. C'est ce qui remplace le
        bouton qu'Egan devait atteindre : il n'y a plus rien a atteindre, et
        l'ecran dit d'avance ce que la touche fera.

        Le nom s'abrege ICI, a la source. Il debordait des **60** caracteres en
        UTF-8 et des **55** en `--ascii` -- le repli `⏎` -> `Entree` coute cinq
        colonnes --, et le garde-fou de l'ecran coupait alors le nom par la
        fin, c'est-a-dire par ce qui distingue deux prises (finding `E10`).
        """
        if self.selection_multiple and self._selection:
            # **Des qu'une coche existe, `⏎` valide la SELECTION** : la ligne
            # doit le dire, sinon elle ment sur ce que la touche fait. Egan, sur
            # les deux redactions montrees cote a cote le 2026-08-31 : « Je
            # prefere le poids total » -- c'est ce qu'on cherche avant de lancer
            # un scan, et le nom se lit deja sur sa ligne, en surbrillance.
            return _etiquette(symbole(ENTREE, ascii_seul),
                              jetons.abreger_nom(
                                  "Valider   "
                                  + self._resume_de_la_selection(ascii_seul),
                                  _place_d_etiquette(
                                      symbole(ENTREE, ascii_seul), utile),
                                  ascii_seul))
        cible = self.cible_de_validation()
        if cible is None:
            nom = RIEN_A_VALIDER
        elif self.dans_la_saisie:
            nom = cible.name or str(cible)
        else:
            entree = self.entree_courante
            nom = entree.nom if entree is not None else RIEN_A_VALIDER
        touche = symbole(ENTREE, ascii_seul)
        libelle = "Valider   "
        nom = jetons.abreger_nom(
            nom, _place_d_etiquette(touche, utile) - len(libelle), ascii_seul)
        return _etiquette(touche, f"{libelle}{nom}")

    def rang_du_curseur(self) -> int | None:
        """Le rang, dans `lignes()`, de la ligne a peindre en accentuation.

        **Passe explicitement a `peindre`, jamais devine.** L'auto-detection de
        `jetons.peindre` teste `startswith` sur le glyphe de curseur ; les
        lignes de cet ecran sont indentees, donc elle ne les trouverait pas et
        ne colorerait rien -- en silence. Le meme piege dort dans
        `execution.py`, qui rend `f"  {curseur} {suite}"`.
        """
        if self.dans_la_saisie:
            return 4                       # la barre d'adresse EST le curseur
        if not self.entrees:
            return None
        premier, dernier = self.fenetre()
        if not premier <= self.curseur <= dernier:
            return None
        decalage = 1 if premier > 0 else 0
        return 6 + decalage + (self.curseur - premier)

    def etat(self, utile: int = jetons.largeur_utile(),
             ascii_seul: bool = False) -> str:
        """La ligne d'etat : une MESURE, jamais une touche ni un conseil.

        `EPIC11-ARB-56`, pose par Egan comme une regle generale : « tu es trop
        bavard dans les bandeaux en bas. Contente toi de mettre les raccourcis
        et les infos pertinentes mais pas une remarque d'aide ou, pire, de
        methode, a chaque fois. Sois sobre. » `Ctrl+H` a donc quitte cette ligne
        pour celle des raccourcis, ou est sa place.
        """
        if self._refus:
            return self._refus
        if self.dans_la_saisie:
            return _tete(str(self.dossier), utile,
                         symbole(ELLIPSE, ascii_seul))
        table = jetons.glyphes(ascii_seul)
        nom_du_compte = "volume" if self.aux_volumes else "sous-dossier"
        if not self.dossier_lisible:
            # Aucun chiffre : le dossier ne s'est pas lu, donc rien n'a ete
            # mesure. `0 sous-dossier` serait le chiffre faux que ce module
            # s'interdit une ligne sur deux.
            return f"{table['neutre']} {nom_du_compte}s"
        mesures = []
        dossiers = sum(1 for e in self.entrees
                       if e.est_dossier and not e.illisible)
        mesures.append(
            f"{dossiers} {nom_du_compte}{'s' if dossiers > 1 else ''}")
        fichiers = sum(1 for e in self.entrees if not e.est_dossier)
        if fichiers:
            mesures.append(f"{fichiers} fichier{'s' if fichiers > 1 else ''}")
        # Une entree illisible -- dossier refuse, lien casse ou en boucle -- se
        # compte a PART : la mettre dans les sous-dossiers annoncerait comme
        # mesure un dossier que rien n'a pu lire (finding `E16`).
        illisibles = sum(1 for e in self.entrees if e.illisible)
        if illisibles:
            mesures.append(f"{illisibles} illisible{'s' if illisibles > 1 else ''}")
        # **Zero projet est une mesure, pas un silence** -- c'est ce que la
        # maquette `X1` affiche, et c'est l'information que l'operateur cherche
        # en arrivant. La taire ferait croire que le compte n'a pas ete fait.
        projets_vus = sum(1 for e in self.entrees if e.porte_un_projet)
        if not self.montrer_fichiers:
            mesures.append(f"{projets_vus} projets" if projets_vus > 1
                           else "1 projet" if projets_vus else "aucun projet")
        if self._mesure_caches:
            mesures.append(self._mesure_caches)
        # Le compte de selection est une MESURE, donc sa place est ici et non
        # dans la ligne du bas (`EPIC11-ARB-56` : « une MESURE, jamais une
        # touche ni un conseil » ; `EPIC11-ARB-103` pour l'emplacement). A zero
        # il ne se dit pas : une mesure nulle n'occupe la ligne que si elle
        # repond a une question qu'on se pose.
        if self.selection_multiple and self._selection:
            cardinal = self._cardinal_de_la_selection()
            # Meme correction qu'a `_resume_de_la_selection` : le glyphe passe
            # par la TABLE du mode et le participe s'ecrit sans accent. Ces deux
            # lignes etaient les seules du module a rendre un caractere hors
            # ASCII en repli, et la frontiere qui l'interdit ne les voyait pas
            # parce que sa fabrique n'entrait jamais en mode selection.
            tete = (table['neutre'] if cardinal is None else str(cardinal))
            pluriel = "s" if (cardinal is None or cardinal > 1) else ""
            mesures.append(
                f"{tete} " + _replie(f"s\u00e9lectionn\u00e9{pluriel}",
                                     ascii_seul))
        # Le SEPARATEUR se replie aussi. `·` n'est pas ASCII, et il restait le
        # dernier caractere hors ASCII d'une ligne d'etat par ailleurs saine :
        # `etat(76, True)` rendait `3 sous-dossiers · 1 fichier`. Le repli se
        # fait ici, avant la mesure, comme `coque.py` le fait deja sur sa
        # propre ligne de raccourcis (finding `F7`, meme famille).
        separateur = jetons.replier_ascii(" · ") if ascii_seul else " · "
        return separateur.join(mesures)


# ---------------------------------------------------------------------------
# Mise en page. Les constantes vivent ici parce que les maquettes les figent, et
# qu'un test les compare ligne par ligne.
# ---------------------------------------------------------------------------

#: Colonne ou commence un nom d'entree, dans la zone centrale.
_INDENT = 5
#: Colonne ou commence la valeur d'un champ de formulaire (`DESIGN.md` 7.3).
_COLONNE_VALEUR = 26
#: Deux colonnes de respiration au bord droit.
_MARGE_DROITE = 2


def _separateur(chemin: Path) -> str:
    """Le separateur du chemin, tel qu'il s'ecrit sur cette plateforme."""
    texte = str(chemin)
    return "\\" if "\\" in texte and "/" not in texte else "/"


def _filet(utile: int, ascii_seul: bool = False) -> str:
    """Le filet de separation. **Il se replie aussi.**

    Trouve par le test de repli ASCII : `─` n'est pas ASCII, et un terminal qui
    ne rend pas `▓` ne rend pas davantage un filet Unicode. Le repli garde la
    MEME largeur -- les deux caracteres occupent une colonne.
    """
    return "  " + ("-" if ascii_seul else "\u2500") * (utile - 4)


def _etiquette(touche: str, texte: str) -> str:
    """Une ETIQUETTE VIVE : la touche, puis ce sur quoi elle agit.

    Calee a gauche, jamais a droite (« Justifie a gauche et non a droite »,
    Egan). Le curseur n'y va jamais.
    """
    return f"   {touche}  {texte}"


def _ligne(nom: str, droite: str, curseur: bool,
           utile: int = jetons.largeur_utile(),
           ascii_seul: bool = False, case: str = "") -> str:
    """Une ligne de liste, **tenue dans la grille** et repliee AVANT la mesure.

    Deux defauts mesures par la revue de la vague 2 bis, et qui expliquent la
    forme de cette fonction.

    * `max(2, creux)` n'avait **aucune borne haute** : des 54 caracteres de nom
      -- un nom de rush ordinaire, `2026-08-29_tournage_exterieur_nuit_camera_B`
      -- la ligne debordait des 76 colonnes ecrivables, et de 26 colonnes sur un
      nom en ideogrammes, ou chaque caractere en vaut **deux**. Le garde-fou de
      l'ecran (`jetons.ajuster`) rattrapait le debordement en coupant **par la
      fin**, c'est-a-dire en supprimant la colonne de droite : la seule chose
      qui distingue une ligne de sa voisine. C'est donc le NOM qui s'abrege ici,
      a la source, et la colonne de droite qui est servie en premier
      (findings `F8`, `E10`).
    * `droite` est construite a `relire()`, **avant** de savoir dans quel mode
      on rendra, et toujours en UTF-8 : `● projet`, `· sous-dossiers`,
      `✕ illisible`, `· pas une source` sortaient tels quels en `--ascii`. Le
      repli se fait donc ici, et **avant** toute mesure de largeur : `…` fait
      une colonne, `...` en fait trois, et replier apres avoir mesure ferait
      deborder de deux colonnes une ligne calee juste (finding `F7`).

    Le nom, lui, n'est **pas** replie : c'est une donnee du systeme de
    fichiers, pas un texte d'ecran. Le rendre en `????` ferait perdre a
    l'operateur le seul moyen de reconnaitre son dossier ; sa largeur, elle,
    est mesuree en colonnes dans les deux modes.
    """
    table = jetons.glyphes(ascii_seul)
    if droite and ascii_seul:
        droite = jetons.replier_ascii(droite)
    entete = " " * (_INDENT - 2) + (f"{table['curseur']} " if curseur else "  ")
    # La case, quand il y en a une, s'intercale entre le curseur et le nom --
    # disposition de `cadences.py:735`, copiee et non reinventee
    # (`EPIC11-ARB-103`). Elle coute QUATRE colonnes au nom : trois de case, une
    # de blanc. Ses trois etats font la meme largeur, donc la colonne du nom ne
    # bouge jamais selon ce qu'une ligne porte.
    if case:
        entete += f"{case} "
    place = utile - _MARGE_DROITE - jetons.colonnes(entete)
    if not droite:
        return entete + jetons.abreger_nom(nom, place, ascii_seul)
    # La colonne de droite passe en premier sur le budget -- mais elle reste
    # bornee, sans quoi un nom pourrait n'avoir plus aucune place et le creux
    # minimal ferait deborder la ligne malgre tout.
    droite = jetons.abreger_nom(
        droite, max(place - jetons.CREUX_MINIMAL, 0), ascii_seul)
    tete = entete + jetons.abreger_nom(
        nom, place - jetons.colonnes(droite) - jetons.CREUX_MINIMAL,
        ascii_seul)
    creux = utile - _MARGE_DROITE - jetons.colonnes(tete) - jetons.colonnes(droite)
    return tete + " " * max(jetons.CREUX_MINIMAL, creux) + droite


def _prefixe(texte: str, largeur: int) -> str:
    """Le plus long DEBUT de `texte` tenant dans `largeur` colonnes.

    En colonnes et non en caracteres : un ideogramme en vaut deux, une marque
    combinante zero. Un `texte[:largeur]` rendrait 40 colonnes pour 20
    caracteres japonais, et c'est exactement le debordement mesure.
    """
    reste, garde = largeur, []
    for caractere in texte:
        cout = jetons.colonnes(caractere)
        if cout > reste:
            break
        garde.append(caractere)
        reste -= cout
    return "".join(garde)


def _place_d_etiquette(touche: str, utile: int) -> int:
    """Les colonnes qui restent au TEXTE d'une etiquette, marge deduite.

    `_etiquette` pose trois espaces, la touche, puis deux espaces. En
    `--ascii`, `⏎` devient `Entree` et coute **cinq colonnes de plus** : la
    place se calcule donc sur la touche deja repliee, jamais sur son ecriture
    UTF-8 (finding `E10`, ou l'etiquette de validation debordait a 55
    caracteres de nom en ASCII contre 60 en UTF-8).
    """
    return utile - _MARGE_DROITE - (3 + jetons.colonnes(touche) + 2)


def _fenetre_de_saisie(texte: str, caret: int, place: int,
                       points: str) -> tuple[str, int]:
    """La tranche visible du texte saisi, et le rang du caret DEDANS.

    **Le caret RECOUVRE un caractere**, il ne s'insere pas, et la fenetre se
    calcule sur le texte NU augmente d'une colonne de garde en fin : sans elle
    le caret n'aurait pas de place quand il est apres le dernier caractere, et
    entrer dans la saisie decalerait le chemin d'une colonne -- la « saute »
    qu'`EPIC11-ARB-52` existe pour supprimer, en plus petit.

    **La fenetre est calee sur la FIN par defaut** (`EPIC11-ARB-52` : c'est la
    fin qu'on vient de taper), et elle **suit le caret quand il sort par la
    gauche** (finding `E13`). Sans ce second temps, editer le DEBUT d'un chemin
    long etait aveugle : le caret butait sur le `…` de tete et n'en bougeait
    plus, les positions 0 et 5 rendaient la meme ligne, et corriger la lettre
    de volume d'un chemin colle -- le cas nominal -- se faisait sans rien voir.
    """
    plein = texte + " "
    if place <= 0:
        return "", 0
    if jetons.colonnes(plein) <= place:
        return plein, min(max(caret, 0), len(plein) - 1)
    corps = _queue(plein, place, points)
    # `_queue` rend `points + garde` : le debut de la garde dans `plein` est
    # donc a `len(plein) - len(garde)`, et le rang du caret s'en deduit.
    perdu = len(plein) - len(corps)
    rang = caret - perdu
    if rang >= len(points):
        return corps, min(rang, len(corps) - 1)
    # Sorti par la GAUCHE : la fenetre se recale SUR le caret. `…` en tete des
    # qu'il reste du texte avant, `…` en queue toujours -- par construction il
    # reste du texte apres, puisque la fenetre calee sur la fin commencait plus
    # loin que le caret.
    debut = min(max(caret, 0), len(plein) - 1)
    tete = points if debut > 0 else ""
    budget = place - jetons.colonnes(tete) - jetons.colonnes(points)
    visible = _prefixe(plein[debut:], max(budget, 0))
    return tete + visible + points, len(tete)


def _queue(texte: str, largeur: int, points: str) -> str:
    """Le texte cale sur sa FIN, avec `points` en tete s'il deborde."""
    if largeur <= 0:
        return ""
    if jetons.colonnes(texte) <= largeur:
        return texte
    budget = largeur - jetons.colonnes(points)
    if budget <= 0:
        return points[:largeur]
    garde = texte
    while jetons.colonnes(garde) > budget:
        garde = garde[1:]
    return points + garde


def _tete(texte: str, largeur: int, points: str) -> str:
    """Le chemin complet de la ligne d'etat, tronque **par le DEBUT**.

    Demande d'Egan : « s'il est trop long meme pour le bas on tronque le debut
    avec `…` ». C'est le seul endroit de la TUI ou l'abregement se fait par le
    debut : ici la fin est ce que l'operateur vient de taper, et la racine est
    ce qu'il coute le moins cher de perdre.
    """
    return _queue(texte, largeur, points)


__all__ = [
    "ADRESSE_INEXISTANTE",
    "FICHIERS_NON_MONTRES",
    "FICHIER_ABSENT_DE_LA_LISTE",
    "FICHIER_CACHE",
    "HAUTEUR_LISTE",
    "Entree",
    "Explorateur",
    "FAMILLES",
    "FAMILLE_MATIERE",
    "FAMILLE_PROFILS",
    "FAMILLE_PROJETS",
    "MemoireDeSession",
    "MemoiresDeSession",
    "normaliser",
    "taille_lisible",
]
