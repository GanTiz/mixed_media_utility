"""La regle des rangs de version, ecrite UNE fois pour tous les objets versionnables.

`EPIC11-ARB-92` (Egan, 2026-08-31), etendu a tous les objets le meme jour :
« Il ne faut pas rendre le rang. La v2 a ete consommee par la v3 qui se trouve
apres. »

**Pourquoi un module et non une implementation par objet.** Le depot porte
CINQ objets versionnables -- les lots, les masters encodes, les planches
imprimees (tirages), les scans, et les frames rescannees d'un lot -- et chacun
a son resolveur, dans un module different. Autant de copies de cette regle
seraient autant de verites (`EPIC5-ARB-78`), donc autant d'occasions de
diverger au premier ajustement. Le calcul vit ici ; les appelants ne
fournissent que leurs donnees.

**Le module qui LIBERE les rangs en fait partie**, et c'est le seul a l'avoir
oublie : `project_maintenance` recopiait `ligne_d_eau`, `est_en_queue` et
`rangs_liberables` a la main, et les deux redactions avaient DEJA diverge
avant qu'une revue ne le mesure -- la copie lisait la ligne declaree telle
quelle la ou `ligne_d_eau` la borne, si bien qu'une ligne abimee desactivait le
refus hors queue. `EPIC11-ARB-108` ferme la question : il n'y a pas de
mecanisme different par objet, ni entre celui qui attribue et celui qui rend.

**Ce que la regle dit**, en trois temps :

1. **un rang se CONSOMME.** Retirer le tirage 2 alors que le 3 existe ne rend
   pas le 2 : le suivant sera le 4. Le motif est d'abord physique -- une
   planche part a l'imprimante, et deux feuilles portant « v2 » ne se
   distinguent plus une fois l'encre seche -- mais Egan l'a etendu aux lots et
   aux masters le meme jour : un master livre a quitte le disque lui aussi, et
   un rang qui ressort est un rang qui ment sur ce qu'il designe ;
2. **seule la QUEUE se rend**, c'est-a-dire les rangs qui suivent le plus haut
   rang encore declare. Et elle se rend d'un bloc : il n'y a pas de demi-mesure
   -- retirer le dernier tirage d'une famille `1, 5` propose de rendre `2, 3,
   4, 5`, jamais un sous-ensemble ;
3. **jamais par defaut.** Rendre un rang detruit de l'information (le fait
   qu'il a servi), donc cela se demande. Le defaut garde le rang consomme.

**La LIGNE D'EAU est la piece qui rend le point 2 possible**, et rien d'autre
ne pourrait la remplacer : apres le retrait du rang 2 d'une famille `1, 2, 3`,
plus aucune entree ne porte le rang 2 et il est pourtant consomme. Seule une
memoire distincte des entrees restantes le sait.
"""

from __future__ import annotations

from collections.abc import Iterable

from .naming import VERSION_RANK_MAX, VERSION_RANK_MIN

#: Rang de l'ORIGINE. Il ne porte aucun fragment de nom (`EPIC11-ARB-88`) et
#: ne s'ecrit jamais au manifeste : son absence le dit.
RANG_ORIGINE = 1


def ligne_d_eau(declaree: object, rangs_employes: Iterable[int]) -> int:
    """Le plus haut rang JAMAIS employe, lu au manifeste ou deduit.

    `declaree` est la valeur persistee, ou n'importe quoi d'autre quand elle
    est absente ou abimee -- un manifeste ecrit avant cet arbitrage n'en porte
    pas. Elle est alors DEDUITE du plus haut rang encore employe, ce qui est
    exact pour tout historique ou aucun rang de queue n'a ete retire, et
    prudent partout ailleurs : deduire ne peut que sous-estimer, jamais
    inventer un rang consomme qui ne l'aurait pas ete.
    """
    valeur = declaree if isinstance(declaree, int) and not isinstance(declaree, bool) else 0
    # **Bornee par le HAUT aussi** (trouve en revue, couche 2). Elle ne l'etait
    # que par le bas : un seul `version_rank` hors bornes dans un manifeste
    # abime -- rien ne le valide a la LECTURE -- faisait rendre a
    # `rangs_liberables` la queue entiere. Mesure : `9 999 999` produisait
    # 9 999 998 rangs, 400 Mo, que la CLI joignait ensuite pour les imprimer.
    # `VERSION_RANK_MAX` est la borne du domaine : au-dela, la valeur ne
    # designe aucun objet nommable.
    return min(max([valeur, *rangs_employes, RANG_ORIGINE]), VERSION_RANK_MAX)


def prochain_rang(ligne: int) -> int:
    """Le rang du prochain objet de cette famille : la ligne d'eau plus un.

    **Ce n'est PAS le premier rang libre.** La redaction d'origine des trois
    resolveurs rendait le TROU dans la sequence -- `1, 2, 4` donnait `3` --, ce
    qu'Egan a corrige : le trou reste un trou, le suivant est le 5.
    """
    return ligne + 1


def rangs_liberables(ligne: int, rangs_restants: Iterable[int]) -> tuple[int, ...]:
    """Les rangs que le retrait en cours rendrait, dans l'ordre.

    La QUEUE, et elle entiere : du premier rang au-dessus du plus haut rang
    encore declare, jusqu'a la ligne d'eau. Sur une famille `1, 5` dont on
    retire le 5, cela rend `2, 3, 4, 5` -- les trois du milieu ayant ete
    retires plus tot sans etre liberes, ils redeviennent la queue au meme
    moment.

    Rend un tuple vide quand rien n'est liberable, ce qui est le cas des que
    l'objet retire n'est pas le dernier a date.
    """
    plancher = max([*rangs_restants, 0])
    # **L'ORIGINE n'est pas un rang de VERSION** et ne se « rend » donc pas :
    # `VERSION_RANK_MIN` vaut 2, et le rang 1 ne porte aucun fragment de nom
    # (`EPIC11-ARB-88`, omission stricte). Rendre une famille jusqu'a l'origine
    # ne libere aucun numero -- cela ramene simplement le prochain objet a
    # l'origine --, et l'annoncer comme « rang 1 rendu » disait a l'operateur
    # un numero qu'il ne verra jamais ecrit nulle part (trouve en revue).
    return tuple(
        r for r in range(plancher + 1, ligne + 1) if r >= VERSION_RANK_MIN
    )


def est_en_queue(rang: int, ligne: int) -> bool:
    """Le rang retire est-il le DERNIER a date ? Seul ce cas ouvre le choix."""
    return rang >= ligne


def refus_de_liberer_hors_queue(rang: int, ligne: int, objet: str) -> str:
    """Le texte du refus quand on demande de rendre un rang consomme.

    **Un refus, pas un silence.** L'operateur qui passe le drapeau en attend un
    effet ; l'ignorer lui ferait croire le rang disponible. Et le refus dit le
    geste qui debloque, conformement a `EPIC11-ARB-89` -- jamais un mur.
    """
    return (
        f"Le rang {rang} ne peut pas etre libere: il a ete CONSOMME par un "
        f"{objet} posterieur (le dernier a date est le rang {ligne}). Le liberer "
        f"ferait porter le meme numero a deux {objet}s differents. Retirer d'abord "
        "les rangs posterieurs; leur retrait liberera alors les rangs devenus "
        "libres, celui-ci compris."
    )


def cardinal_des_homonymes() -> int:
    """Combien d'objets peuvent porter le MEME nom, l'original compris.

    **Ce n'est pas le cardinal des rangs de version, et l'ecart est reel.**
    Les rangs vont de :data:`VERSION_RANK_MIN` a :data:`VERSION_RANK_MAX`,
    donc `MAX - MIN + 1` ; les homonymes comptent en plus l'original, qui n'en
    porte aucun -- `prise01`, puis `prise01-2` jusqu'a `prise01-<MAX>`. Les
    deux nombres disent vrai de deux choses differentes ; ne pas « corriger »
    l'un sur l'autre.

    **Pourquoi cette fonction existe plutot qu'un import de la borne.** La
    frontiere `test_AUCUN_module_de_la_TUI_ne_redige_une_regle_de_RANG`
    interdit au paquet `tui/` de nommer le vocabulaire des rangs, **prose
    comprise** : le paquet APPELLE la regle, il ne la reecrit pas
    (`EPIC11-ARB-108`). Un ecran qui importait la borne pour la formater dans
    une phrase la reecrivait -- c'est le defaut que le lot `E2-1j` a introduit
    le 2026-09-06 et que cette fonction ferme. Le cardinal se calcule ici, une
    fois, comme tout le reste de la regle des rangs.
    """
    return VERSION_RANK_MAX


def refus_de_rangs_epuises(objet: str, identifiant: object, issues: str) -> str:
    """Le texte du refus quand les 99 rangs sont consommes.

    Toujours au moins deux issues (`EPIC11-ARB-89`): sans elles, le rang 100
    partait vers `format_version_suffix` et en revenait sous un « rang hors
    bornes » qui ne dit rien de la situation et n'offre aucune sortie.
    """
    return (
        f"Les {VERSION_RANK_MAX - VERSION_RANK_MIN + 1} rangs de version "
        f"({objet}) de {identifiant!r} sont tous CONSOMMES (de {VERSION_RANK_MIN} "
        f"a {VERSION_RANK_MAX}). {issues}"
    )
