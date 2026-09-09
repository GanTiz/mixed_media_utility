"""Vocabulaire ferme des **roles de page** d'un lot (story 5.16, AC 3).

Ce que ce module resout, et pourquoi il est a part
-------------------------------------------------
Depuis `EPIC5-ARB-54` un lot ne porte plus un seul type de page: sa **premiere
page est une page de calibration dediee**, qui porte le treillis de mesure et
aucune frame, et ses pages suivantes sont les **planches d'images**. Le role
d'une page doit donc etre declare, et il doit l'etre par un champ de payload
**de niveau page**.

Le vocabulaire vit dans un module a lui, minuscule et sans aucun import du
depot, pour une raison de couches: il est lu a la fois par `io/payload.py` (le
contrat du QR, qui ne connait rien de la geometrie) et par `page_templates` /
`patch_presets` (la geometrie, qui ne connait rien du QR). Le declarer dans
l'un des deux aurait force l'autre a l'importer, donc a importer un paquet
entier pour deux chaines -- ou, pire, a recopier les deux valeurs. Une seconde
liste de roles est exactement la seconde table que la story 5.17 a interdite
pour les cles du payload, et elle divergerait de la meme facon: en silence a
l'ecriture, fatalement a la relecture.

Pourquoi des codes d'**un** caractere
-------------------------------------
Le role voyage dans le payload QR, donc chaque caractere se paie en octets sur
du papier. Mesure du 2026-08-12, reproduite sur les six cardinaux et sur le
pire regime d'identifiants: le fragment ``,"pr":"i"`` coute **9 octets**, et le
pire cas atteignable -- trois identifiants a `naming.CANONICAL_ID_MAX_LENGTH`
et 8 emplacements -- pese **542 octets** pour la version de symbole **19**,
contre un plafond `io.payload.ALERT_BUDGET_BYTES` de 768 et une seule version
bannie, 22. Le champ est donc sans risque, et il l'est **parce que** sa valeur
fait un caractere: la meme information portee par un mot en couterait onze.

Le chiffre est **borne des deux cotes**, sur le balayage des **252** couples
(gabarit x preset) livres a ce regime: minimum **537**, maximum **542**, et la
version **19** sur les 252 sans exception -- soit **226 octets** de marge sous le
plafond. Il annoncait **534**, corrige au 2026-08-12 (mineur m2 de la couche 1 de
la revue de 5.16): 534 n'etait atteint par aucun couple, il etait **sous le
minimum du domaine qu'il bornait**, donc faux dans le sens qui **sous-estime** le
pire cas. La conclusion (« sans risque ») ne bouge pas; c'est la raison pour
laquelle un pire cas s'ecrit avec son regime **et** son balayage, jamais comme un
nombre seul.

Deux pieges que la mesure a nommes, et qu'il ne faut pas re-decouvrir:

* la **version du symbole n'est pas monotone en octets**. A 18 emplacements, un
  payload *sans* ce champ tombe sur la version bannie 22 et le meme payload
  *avec* le champ en sort. Ajouter un champ peut donc **debloquer** une page:
  aucun raisonnement « plus leger donc plus sur » n'est valide ici, il faut
  mesurer;
* un champ nouveau **s'ajoute a la table** `io.payload.PAYLOAD_SHORT_KEYS`, il
  ne se glisse pas dans un payload -- une cle inconnue de la table leve
  `PayloadValidationError`, et c'est exactement la garde voulue.

Vocabulaire interdit, verifie
-----------------------------
Le mot ``mire`` est **deja pris** dans ce depot, et il designe autre chose: les
frames de remplacement de synthese (`lots[].synthetic_frames`,
`EPIC5-ARB-33`). Aucun identifiant de ce module ni des mecanismes qu'il
commande ne porte ``mire`` ni le prefixe ``synthetic_``: les confondre rendrait
les deux registres indiscernables a la lecture.

Ce que le role change au reste du depot
---------------------------------------
Consequence semantique a assumer, et elle est ecrite ici parce qu'elle est le
prix du mecanisme: **`template_id` cesse d'etre une description complete de ce
qui est imprime sur une page donnee.** Il decrit la geometrie des pages
d'**images** du lot; la mise en page effective d'une page se derive du couple
``(template_id, role de page)`` -- voir `patch_presets.resolve_page_layout`.

Cette forme est **forcee** et non choisie: `template_id` et `patch_preset_id`
sont tous deux dans `io.reconstruction._LOT_LEVEL_FIELDS`, et une page qui
declarerait les siens serait refusee par l'invariant d'identite de lot, pas par
une garde qu'on pourrait assouplir. `page_count` y est **aussi**, ce qui force
la deuxieme moitie du contrat: la page de calibration porte
``page_index = 0`` et le **meme** `page_count` que les planches d'images,
lequel la compte.
"""

from __future__ import annotations

#: Une planche d'images: des zones de dessin, des frames, un jeu de pastilles
#: temoins aux cotes. C'est le role **par defaut** partout ou un appelant n'en
#: nomme pas -- et ce defaut est le regime **strict**: un payload de planche
#: d'images sans emplacements reste refuse, ce qui est un mode d'echec reel du
#: chemin de scan (un QR dont les emplacements ont ete perdus).
PAGE_ROLE_IMAGES = "i"

#: La page de calibration dediee du lot, premiere page (`page_index = 0`). Elle
#: porte le treillis de mesure et ses quatre coins, **aucune frame**, donc
#: aucun emplacement.
PAGE_ROLE_CALIBRATION = "c"

#: Vocabulaire ferme, dans l'ordre ou il se lit: le regime courant d'abord.
PAGE_ROLES: tuple[str, ...] = (PAGE_ROLE_IMAGES, PAGE_ROLE_CALIBRATION)

#: Index de la **page de calibration** dans l'espace d'index du lot (story 5.16,
#: `EPIC5-ARB-54`). Zero, et ce n'est pas un choix: `page_count` est de niveau lot, donc
#: une page de calibration hors de cet espace d'index serait refusee a la reconstruction
#: par l'invariant d'identite de lot -- mesure a l'execution, pas suppose. Consequence
#: assumee et honnete: la pagination de pied se decale d'une page, les planches d'images
#: d'un lot de douze devenant `2/13` a `13/13`.
#:
#: **Elle vit ici depuis la passe de correction de 5.16** (finding F1 de la couche 2), et
#: le motif est le meme que celui du vocabulaire lui-meme: la relecture doit pouvoir
#: refuser une page de calibration posee ailleurs qu'a cet index, et `io/reconstruction`
#: n'a pas a importer `pdf_composition` -- donc la composition PDF entiere, donc les
#: gabarits et les presets -- pour lire un entier. `pdf_composition` la **relit** ici.
CALIBRATION_PAGE_INDEX = 0

#: Combien de pages de role calibration un lot porte **au plus**. Un, et le refus qui le
#: tient est a la relecture: deux pages de calibration font perdre en silence les
#: emplacements de la seconde, et un lot **entierement** en role calibration se
#: reconstruisait `status = complete` avec zero emplacement et sans `missing_pages` --
#: mesure de la couche 2, pas une precaution. Le producteur n'en insere qu'une; le
#: lecteur est une implementation independante et doit le verifier lui-meme.
MAX_CALIBRATION_PAGES_PER_LOT = 1

#: Libelles lisibles, pour les **messages de refus** seulement. Ils ne voyagent
#: jamais dans un payload: c'est le code d'un caractere qui est imprime. Un
#: operateur qui lit un refus doit lire « planche d'images », pas ``'i'``.
PAGE_ROLE_LABELS: dict[str, str] = {
    PAGE_ROLE_IMAGES: "planche d'images",
    PAGE_ROLE_CALIBRATION: "page de calibration",
}


class UnknownPageRoleError(ValueError):
    """Role de page hors vocabulaire.

    Refus explicite et jamais de repli sur le role courant: un repli ferait
    composer une planche d'images la ou une page de calibration etait demandee,
    donc imprimerait des pastilles de 6 mm sur la page dont depend toute la
    correction du lot -- sans qu'aucune etape n'echoue.
    """


def validate_page_role(value: object) -> str:
    """Rendre ``value`` si c'est un role du vocabulaire, lever sinon."""
    if value in PAGE_ROLES:
        return str(value)
    raise UnknownPageRoleError(
        f"Role de page inconnu: {value!r}. Vocabulaire ferme: "
        + ", ".join(f"{role!r} ({PAGE_ROLE_LABELS[role]})" for role in PAGE_ROLES)
        + ". Un role inconnu ne se resout jamais en role devine (contrat 4.5)."
    )


def page_role_label(role: str) -> str:
    """Libelle lisible d'un role, pour un message destine a un operateur."""
    return PAGE_ROLE_LABELS[validate_page_role(role)]
