# -*- coding: utf-8 -*-
"""Story 11.9, lot C -- l'ECRAN du manuel des raccourcis (maquette `T1-2`).

Ce module **dessine**, il ne derive rien : tout ce qu'il affiche vient de
:mod:`.manuel`, livre au lot A (`EPIC11-ARB-196`). Le partage est net et il
n'est pas de confort -- une seconde derivation ecrite ici divergerait de la
premiere au premier ecran ajoute, ce que `CLAUDE.md` documente sous « une
valeur fausse dans un registre se recopie ».

**Ce que `F1` ouvre desormais.** `coque.action_aide` empilait `EcranPasEncore`
avec deux constantes qui nommaient cette story (`CE_QU_OUVRE_F1`,
`QUAND_ARRIVE_L_AIDE`). Il empile maintenant :class:`EcranManuel`. Trois
proprietes de l'ancien ecran sont **reprises**, pas heritees, parce qu'elles
sont ce qui rendait `F1` sortable :

* il est `TRANSITOIRE` (AC 2.5) -- un passage, pas une station. Le rendre non
  transitoire ferait compter `rang` un palier de plus, et
  `revenir_aux_ateliers()` / `RANG_DES_ATELIERS` derailleraient ;
* sa sortie `Échap` est traitee **localement** et depile sur
  `len(screen_stack) > 1`, **jamais** sur `rang > 0` (`EPIC11-ARB-140`, voir
  :meth:`EcranManuel.fermer`) ;
* `⏎` est **arrete** sans agir : il n'y a rien sous cet ecran, et la ligne de
  raccourcis ne l'annonce pas. Une touche non annoncee qui agit est aussi
  trompeuse qu'une touche annoncee qui n'agit pas.

**La ligne de raccourcis ne porte PAS `Q quitter`** (AC 5.7). La maquette
`T1-2` la dessine ; `EPIC11-ARB-140` la retire des passages, et
`tests/unit/tui/test_arb140_passages_sans_q_quitter.py:96` mesure un ensemble
**exact** de trois classes transitoires qui l'annoncent encore. Le manuel etant
transitoire, l'y faire entrer aurait fait rougir ce banc -- c'est l'un des six
ecarts bornes par l'AC 4.2.

**La ligne d'etat porte une MESURE** (`EPIC11-ARB-56`), la ou `T1-2` la laisse
vide. Une ligne d'etat vide n'est pas neutre : c'est une zone de la grille qui
ne dit rien alors que l'arbitrage lui donne un role.

**Le budget de largeur se LIT** (`jetons.largeur_utile()`), il ne se recopie
pas -- lecon de la 11.7, ou `CANONICAL_ID_MAX_LENGTH` a ete recopiee fausse
trois fois. Et le repli ASCII precede toujours la mesure : `⏎` y vaut **six**
colonnes (`Entree`), si bien qu'une colonne calee en UTF-8 se decale en repli
si l'on compte avant de replier.
"""
from __future__ import annotations

from dataclasses import dataclass

from textual.widget import Widget
from textual.widgets import Static

from . import jetons, manuel
from .atelier_extraction import _application_montee, ligne_de_titre
from .coque import ObjetTravaille, Palier

# ---------------------------------------------------------------------------
# Le dessin : les colonnes de `T1-2`, relevees sur la maquette approuvee
# ---------------------------------------------------------------------------

#: Le palier affiche dans le bandeau. C'est le mot de la maquette.
TITRE_DU_MANUEL = "Manuel"

#: Les deux titres de bloc de `T1-2`, dans son ecriture exacte.
TITRE_DU_BLOC_PARTOUT = "Raccourcis — partout"
TITRE_DU_BLOC_PROPRES = "Propres à un écran"

#: La ligne de raccourcis du manuel. **Sans `Q quitter`** (AC 5.7,
#: `EPIC11-ARB-140`), et **chaque fleche garde son sens nomme** -- `→ page
#: suivante`, jamais `←→ naviguer`, qui est exactement ce qu'`EPIC11-ARB-60`
#: refuse. Separateur a deux espaces (`EPIC11-ARB-122`), touches nommees dans
#: leur forme canonique : trois bancs d'epic enrolent cette ligne tout seuls.
RACCOURCIS_MANUEL = "→ page suivante  ← page précédente  Échap fermer"

#: Ou commence l'ouvreur d'un item, ou son libelle, ou son atelier. Les trois
#: sont **relevees sur `T1-2`** au caractere pres, cadre et marge retires.
COLONNE_DE_L_OUVREUR = 5
COLONNE_DU_LIBELLE = 18
COLONNE_DE_L_ATELIER = 47

#: La marge laissee a droite du texte, comme dans les blocs de l'Extraction.
MARGE_DROITE = 2

#: Ce qui separe deux libelles d'un meme ouvreur. `Échap` en porte quinze au
#: paquet : n'en garder qu'un ferait mentir le manuel sur quatorze ecrans, et
#: c'est ce que :class:`manuel.Entree` documente deja.
SEPARATEUR_DES_LIBELLES = " · "


def _replie(texte: str, ascii_seul: bool) -> str:
    return jetons.replier_ascii(texte) if ascii_seul else texte


def _a_la_colonne(gauche: str, colonne: int) -> str:
    """Completer `gauche` de blancs jusqu'a `colonne`, au moins un blanc.

    **La mesure est faite sur le texte DEJA replie**, et l'appelant s'en
    charge : `⏎` occupe une colonne en UTF-8 et six en repli (`Entree`).
    Caler la colonne avant de replier decalerait tout le bloc du repli, ce qui
    est la regression exacte payee sur le bandeau le 2026-08-28.
    """
    creux = colonne - jetons.colonnes(gauche)
    return gauche + " " * max(1, creux)


# ---------------------------------------------------------------------------
# Nommer l'atelier d'un raccourci propre -- derive, jamais recopie
# ---------------------------------------------------------------------------

#: Le domaine d'un module -- **re-exporte**, jamais reecrit.
#:
#: La redaction unique vit dans :mod:`manuel` depuis la fermeture du lot E2
#: (revue de la 11.9, couche 1 `F1` et couche 2 `F2`, mutant `M07`) : c'est le
#: critere `partout` qui la consomme le plus tot, et `manuel` ne peut pas
#: importer `ecran_manuel` sans boucler. Ce module en garda une **copie** le
#: temps de la fusion, epinglee a l'egalite par le banc
#: `test_manuel_derive.py::test_les_DEUX_redactions_du_DOMAINE_...`.
#:
#: **La copie disparait ici** (passe croisee de la vague 6, lot E3 du
#: 2026-09-05) : la fusion des trois lots de revue l'avait laissee vivre, ce
#: que le registre `11-9-registre-des-findings-manuel.md` (section 3, point 1)
#: lui demandait pourtant de faire. Deux redactions du meme calcul sont ce que
#: `CLAUDE.md` refuse partout ailleurs ; une egalite epinglee borne la
#: divergence, elle ne la supprime pas. Le banc d'egalite se **saute** de
#: lui-meme des que la copie est devenue une re-exportation -- c'est l'issue
#: qu'il annonce dans son propre message de saut.
noms_de_domaine = manuel.noms_de_domaine
atelier_lisible = manuel.atelier_lisible


def ateliers_d_une_entree(entree: manuel.Entree) -> str:
    """Ce que le manuel ecrit entre parentheses, a droite d'un raccourci propre."""
    lisibles = sorted({atelier_lisible(module) for module in entree.ateliers})
    return f"({SEPARATEUR_DES_LIBELLES.join(lisibles)})" if lisibles else ""


# ---------------------------------------------------------------------------
# Les lignes du manuel, puis leur PAGINATION
# ---------------------------------------------------------------------------

def lignes_d_une_entree(entree: manuel.Entree,
                        largeur: int = jetons.LARGEUR_PLANCHER,
                        ascii_seul: bool = False) -> list[str]:
    """Les lignes que le manuel consacre a UN ouvreur.

    Le bloc « partout » rend l'ouvreur puis **tous** ses libelles, enveloppes
    sur la largeur restante : la hauteur se depense, l'information ne se perd
    pas (`jetons.envelopper`). Le bloc « propre » rend le libelle puis
    l'atelier a sa colonne, comme `T1-2` l'annote.
    """
    utile = jetons.largeur_utile(largeur)
    ouvreur = _replie(entree.ouvreur, ascii_seul)
    tete = _a_la_colonne(" " * COLONNE_DE_L_OUVREUR + ouvreur,
                         COLONNE_DU_LIBELLE)
    creux = " " * COLONNE_DU_LIBELLE
    texte = SEPARATEUR_DES_LIBELLES.join(entree.libelles)

    if entree.partout:
        place = utile - COLONNE_DU_LIBELLE - MARGE_DROITE
        morceaux = jetons.envelopper(texte, place, ascii_seul) or [""]
        return [(tete if rang == 0 else creux) + morceau
                for rang, morceau in enumerate(morceaux)]

    place = COLONNE_DE_L_ATELIER - COLONNE_DU_LIBELLE - 1
    morceaux = jetons.envelopper(texte, place, ascii_seul) or [""]
    lignes = [(tete if rang == 0 else creux) + morceau
              for rang, morceau in enumerate(morceaux)]
    atelier = _replie(ateliers_d_une_entree(entree), ascii_seul)
    if atelier:
        lignes[-1] = _a_la_colonne(lignes[-1], COLONNE_DE_L_ATELIER) + atelier
    return lignes


@dataclass(frozen=True)
class _Unite:
    """Ce que la pagination deplace d'un seul tenant, **avec son titre**.

    Une unite est **un** ouvreur et toutes ses lignes ; celle qui ouvre un bloc
    y porte en plus le groupe de titre, **soude** a elle. Les deux moities de
    la soudure sont ce qui ferme le defaut `F3` de la revue du 2026-09-03, et
    elles ferment deux regimes distincts :

    * ``titre`` voyage avec chaque unite pour qu'une page qui **continue** un
      bloc puisse en reposer le titre en tete (regime `(a)` : la page 2 du
      manuel reel s'ouvrait au milieu du bloc « partout » et la page 3
      entierement dans le bloc « propres », sans titre ni l'une ni l'autre) ;
    * ``ouvre_son_bloc`` dit que le titre est **deja dans** ``lignes`` : la
      coupure ne peut donc pas passer entre un titre et son premier raccourci
      (regime `(b)` : le titre restait seul en bas de page, et le paquet reel
      etait a une ligne de ce cas).
    """

    lignes: tuple[str, ...]
    ouvreurs: tuple[str, ...]
    #: Le groupe de titre du bloc courant, **verbatim** -- respirations
    #: comprises. Aucun suffixe n'est invente : « (suite) » serait une decision
    #: de libelle, et une decision de libelle ne se prend pas dans un
    #: correctif de pagination.
    titre: tuple[str, ...]
    ouvre_son_bloc: bool


def _unites_du_manuel(entrees: tuple[manuel.Entree, ...] | None = None,
                      largeur: int = jetons.LARGEUR_PLANCHER,
                      ascii_seul: bool = False) -> list[_Unite]:
    """Les unites insecables du manuel, dans l'ordre de la derivation.

    ``entrees`` est injectable pour que le banc fabrique ses propres corpus --
    la derivation reelle est appelee a defaut, et **jamais au niveau module**
    (AC 3.5 : 25 modules importent `coque`, un balayage a l'import rend le
    cycle).
    """
    if entrees is None:
        entrees = manuel.entrees_du_manuel()
    unites: list[_Unite] = []
    titre_courant: tuple[str, ...] = ()
    bloc_ouvert: bool | None = None
    for entree in entrees:
        lignes = tuple(lignes_d_une_entree(entree, largeur, ascii_seul))
        if entree.partout != bloc_ouvert:
            titre = (TITRE_DU_BLOC_PARTOUT if entree.partout
                     else TITRE_DU_BLOC_PROPRES)
            titre_courant = ("", ligne_de_titre(titre, ascii_seul), "")
            bloc_ouvert = entree.partout
            unites.append(_Unite(titre_courant + lignes, (entree.ouvreur,),
                                 titre_courant, True))
            continue
        unites.append(_Unite(lignes, (entree.ouvreur,), titre_courant, False))
    return unites


def groupes_du_manuel(entrees: tuple[manuel.Entree, ...] | None = None,
                      largeur: int = jetons.LARGEUR_PLANCHER,
                      ascii_seul: bool = False
                      ) -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    """Le manuel en GROUPES : `(lignes, ouvreurs portes)`.

    Un groupe est soit un titre de bloc avec ses respirations, soit **un**
    ouvreur avec toutes ses lignes. C'est la **lecture** du manuel, celle qui
    dit ce qu'il ecrit et dans quel ordre.

    **Ce n'est plus l'unite de coupure**, et la distinction est ce qui ferme le
    regime `(b)` du defaut `F3` : la pagination travaille sur
    :func:`_unites_du_manuel`, ou le titre est **soude** a son premier
    raccourci. Couper entre les groupes laissait un titre finir seul en bas de
    page, son bloc commencant sur la suivante.
    """
    groupes: list[tuple[tuple[str, ...], tuple[str, ...]]] = []
    for unite in _unites_du_manuel(entrees, largeur, ascii_seul):
        if unite.ouvre_son_bloc:
            groupes.append((unite.titre, ()))
            groupes.append((unite.lignes[len(unite.titre):], unite.ouvreurs))
        else:
            groupes.append((unite.lignes, unite.ouvreurs))
    return groupes


@dataclass(frozen=True)
class Page:
    """Une page du manuel : ses lignes, et les ouvreurs qu'elle porte.

    Les ouvreurs voyagent avec les lignes parce que la ligne d'etat en tire sa
    **mesure** (`EPIC11-ARB-56`). Les recompter en relisant les lignes rendues
    serait une seconde lecture, qui divergerait du dessin.
    """

    lignes: tuple[str, ...]
    ouvreurs: tuple[str, ...]


def pages_du_manuel(entrees: tuple[manuel.Entree, ...] | None = None,
                    largeur: int = jetons.LARGEUR_PLANCHER,
                    ascii_seul: bool = False,
                    hauteur: int = jetons.HAUTEUR_CENTRE_AU_PLANCHER
                    ) -> tuple[Page, ...]:
    """Le manuel decoupe en pages qui tiennent dans la zone centrale.

    ``hauteur`` est **derivee** de la grille (`HAUTEUR_CENTRE_AU_PLANCHER`) et
    jamais saisie : `textual` coupe par le bas **en silence**, si bien qu'une
    page trop haute perdrait ses derniers raccourcis sans rien dire -- c'est le
    defaut `I1` que `Composition` a paye sur `E2-2`.

    Le rang de page qu'affiche le bandeau est donc **une consequence** du
    cardinal derive : le manuel dit `page 1 sur 1` s'il tient en une page,
    plutot que de mentir a `3` comme la maquette l'annonce.

    **Toute page porte le titre du bloc qu'elle montre** (defaut `F3` de la
    revue du 2026-09-03). Une page qui **continue** un bloc en repose le titre
    en tete, verbatim, comme un en-tete de tableau qui se repete : sans lui,
    la page 3 du manuel reel portait deux raccourcis que l'operateur arrive
    par `→` ne pouvait rattacher a rien. Et le titre ne peut plus rester seul
    en bas d'une page, puisqu'il voyage **soude** a son premier raccourci
    (:func:`_unites_du_manuel`).

    **Ce que le rappel ne couvre pas, dit plutot que tu** : une unite plus
    haute que la zone centrale deborde deja sans lui -- `textual` coupe alors
    par le bas en silence (defaut `I1`) --, et le rappel aggrave ce cas de
    trois lignes au lieu de le creer. Aucune entree du paquet n'en approche :
    la plus haute vaut six lignes sur dix-sept, et
    `test_C2_aucune_page_ne_DEPASSE_la_hauteur_derivee_de_la_grille` le mesure
    a chaque course.
    """
    pages: list[Page] = []
    lignes: list[str] = []
    ouvreurs: list[str] = []
    for unite in _unites_du_manuel(entrees, largeur, ascii_seul):
        if lignes and len(lignes) + len(unite.lignes) > hauteur:
            pages.append(Page(tuple(lignes), tuple(ouvreurs)))
            # La page neuve REPREND le titre du bloc qu'elle continue ; celle
            # qui ouvre un bloc le porte deja dans ses lignes, et le reposer
            # l'ecrirait deux fois.
            lignes = [] if unite.ouvre_son_bloc else list(unite.titre)
            ouvreurs = []
        lignes.extend(unite.lignes)
        ouvreurs.extend(unite.ouvreurs)
    if lignes or not pages:
        pages.append(Page(tuple(lignes), tuple(ouvreurs)))
    return tuple(pages)


def libelle_de_page(rang: int, total: int) -> str:
    """`page 2 sur 3`, l'ecriture exacte de `T1-2`. Rang compte depuis 1."""
    return f"page {rang + 1} sur {total}"


def mesure_de_la_page(page: Page, total: int) -> str:
    """La ligne d'etat : **une mesure de l'ecran courant** (`EPIC11-ARB-56`).

    Elle ne porte aucune touche, aucun conseil d'usage, aucun motif de
    conception -- ce sont les trois interdits de l'arbitrage. Elle porte ce que
    la page montre, rapporte a ce que le paquet annonce.
    """
    return f"{len(page.ouvreurs)} raccourcis sur {total}"


# ---------------------------------------------------------------------------
# L'ecran
# ---------------------------------------------------------------------------

class EcranManuel(ObjetTravaille, Palier):
    """`T1-2` -- le manuel pagine de tous les raccourcis du produit.

    **Un passage, jamais une station** (AC 2.5) : il s'ouvre par `F1` par-dessus
    n'importe quoi, y compris une tache en cours, et il se ferme sans rien
    decider du travail en cours.
    """

    titre = TITRE_DU_MANUEL
    raccourcis = RACCOURCIS_MANUEL
    TRANSITOIRE = True
    ID_DU_CORPS = "corps-manuel"

    def __init__(self, entrees: tuple[manuel.Entree, ...] | None = None) -> None:
        super().__init__()
        #: Les entrees a dessiner. `None` = la derivation reelle, appelee au
        #: dessin et **jamais a l'import** (AC 3.5).
        self._entrees = entrees
        #: La pagination deja calculee, par regime de rendu. Voir :meth:`pages`.
        self._pages_par_regime: dict[tuple[int, int, bool],
                                     tuple[Page, ...]] = {}
        self.rang_de_page = 0

    # -- lecture --------------------------------------------------------------

    def _regime(self) -> tuple[int, int, bool]:
        """La largeur, la HAUTEUR et le mode de rendu -- ou ceux du plancher.

        **Les deux moities du regime se lisent au meme endroit** (arbitrage
        d'Egan du 2026-09-04, verbatim : « Remplir la fenetre » -- il n'a pas
        encore de numero, et un numero non reserve se paie en renumerotation).
        Jusqu'au 2026-09-04 cette
        methode rendait la largeur **reelle** de la fenetre et laissait la
        hauteur a `jetons.HAUTEUR_CENTRE_AU_PLANCHER` : le manuel s'elargissait
        avec le terminal mais restait pagine pour 17 lignes. A 120 x 50, ses 28
        lignes tenaient en **une** page ; le produit en annonçait deux, laissait
        28 lignes de la zone centrale vides et imposait un `→` qui n'avait
        aucune raison d'exister. C'etait une asymetrie, pas un choix.

        La hauteur se derive de la fenetre par `jetons.hauteur_centrale`, la
        seule ecriture de cette soustraction dans le depot.

        **Le repli hors montage reste, et il reste au PLANCHER.** `textual` fait
        de `Screen.app` une propriete qui **leve** hors montage, y compris a
        travers `getattr(..., None)`. Les bancs construisent les ecrans a nu ;
        sans ce repli, `traiter()` ne serait pas mesurable sans terminal, ce
        qu'`EPIC11-ARB-11` exige pourtant. Hors montage il n'y a pas de fenetre
        a suivre : le plancher est la seule taille que le depot connaisse.
        """
        application = _application_montee(self)
        if application is None:
            return (jetons.LARGEUR_PLANCHER, jetons.HAUTEUR_CENTRE_AU_PLANCHER,
                    False)
        return (application.size.width,
                jetons.hauteur_centrale(application.size.height),
                getattr(application, "ascii_seul", False))

    def pages(self, largeur: int | None = None,
              ascii_seul: bool | None = None,
              hauteur: int | None = None) -> tuple[Page, ...]:
        """Les pages du manuel dans le regime demande, ou dans le regime courant.

        **La memoire est portee par l'INSTANCE et CLEE PAR LE REGIME**, jamais
        par le module. Les deux moities comptent :

        * cle par `(largeur, hauteur, repli)`, parce qu'un redimensionnement
          change la mise en page : une pagination cachee sans sa cle peindrait
          celle de l'ancienne fenetre. **La hauteur est dans la cle depuis le
          2026-09-04** ; sans elle, agrandir la fenetre en hauteur seule aurait
          rendu la pagination de l'ancienne, ce qui est le defaut que le
          correctif venait de fermer, deplace d'un cran ;
        * sur l'instance, parce que `action_aide` construit un ecran **neuf** a
          chaque `F1` : la derivation est donc rejouee a chaque ouverture de
          l'aide, et un ecran ajoute au paquet entre au manuel sans que
          personne y pense (AC 3.1). Une memoire de module, elle, mentirait des
          qu'un banc ajoute une classe temoin -- c'est ce que le lot A refuse.

        Sans elle, une seule frappe coutait **quatre** derivations : le corps,
        la ligne d'etat et le bandeau la demandent chacun (262 ms mesures au
        lot A, soit une seconde par touche).
        """
        courante, haute, replie = self._regime()
        regime = (largeur if largeur is not None else courante,
                  haute if hauteur is None else hauteur,
                  replie if ascii_seul is None else ascii_seul)
        if regime not in self._pages_par_regime:
            self._pages_par_regime[regime] = pages_du_manuel(
                self._entrees, regime[0], regime[2], regime[1])
        pages = self._pages_par_regime[regime]
        # La largeur peut avoir retreci depuis la derniere touche : le rang
        # survivrait a la page qu'il designait.
        self.rang_de_page = max(0, min(self.rang_de_page, len(pages) - 1))
        return pages

    def composer(self, largeur: int | None = None,
                 ascii_seul: bool | None = None,
                 hauteur: int | None = None) -> list[str]:
        """Les lignes de la page courante -- ce que le banc confronte a `T1-2`."""
        return list(
            self.pages(largeur, ascii_seul, hauteur)[self.rang_de_page].lignes)

    def objet_du_bandeau(self) -> str:
        """La DROITE du bandeau : `page 2 sur 3`, comme la maquette le dessine."""
        pages = self.pages()
        return libelle_de_page(self.rang_de_page, len(pages))

    def ligne_d_etat(self, ascii_seul: bool = False) -> str:
        pages = self.pages()
        total = sum(len(page.ouvreurs) for page in pages)
        return _replie(mesure_de_la_page(pages[self.rang_de_page], total),
                       ascii_seul)

    # -- rendu ----------------------------------------------------------------

    def contenu(self) -> list[Widget]:
        self._corps = Static("", id=self.ID_DU_CORPS)
        return [self._corps]

    def rafraichir(self) -> None:
        if not self._assez_grand_au_dernier_dessin:
            return
        largeur, hauteur, ascii_seul = self._regime()
        utile = jetons.largeur_utile(largeur)
        self._corps.update(jetons.peindre(
            [jetons.ajuster(ligne, utile, ascii_seul)
             for ligne in self.composer(largeur, ascii_seul, hauteur)],
            ascii_seul=ascii_seul,
            sans_couleur=getattr(self.app, "sans_couleur", False)))
        self.poser_etat(self.ligne_d_etat(ascii_seul))
        super().rafraichir()

    def on_mount(self) -> None:
        self.rafraichir()

    # -- clavier --------------------------------------------------------------

    def fermer(self) -> None:
        """`Échap` DEPILE, d'ou qu'on soit venu. `EPIC11-ARB-140`, geste 2.

        **Reprise de `coque.EcranPasEncore.on_key`, et la condition est la
        sienne** : on depile sur `len(screen_stack) > 1`, **pas** sur
        `rang > 0`. Les deux culs-de-sac que cette condition ferme :

        * **pendant une tache** -- `CoqueTui.action_remonter` voit
          `tache_en_cours`, arme `interruption_demandee` et rend la main **sans
          depiler**. L'operateur qui a demande l'aide devrait declencher une
          interruption pour en sortir ;
        * **a la racine** -- `rang` compte les PALIERS, et le manuel est un
          passage. Un `F1` presse sur l'ecran projet laisse `rang == 0`, et
          `if self.rang > 0` ne depile pas davantage.

        La tache n'est **pas** touchee : ni `tache_en_cours` ni
        `interruption_demandee` ne bougent. Fermer l'aide n'est pas une
        decision sur le travail en cours.
        """
        application = _application_montee(self)
        if application is None:
            return
        if len(application.screen_stack) > 1:
            application.pop_screen()

    def traiter(self, touche: str, caractere: str | None = None) -> bool:
        """Mesurable sans clavier, comme tous les ecrans du depot.

        `EPIC11-ARB-11` : « aucun geste n'est atteignable seulement a la
        souris ». Les trois gestes du manuel -- page suivante, page precedente,
        sortie -- passent donc tous par ici, et le banc les joue par
        `traiter()` seul, sans `Pilot` ni souris.

        **Seules les touches ANNONCEES agissent** : une touche non annoncee qui
        agit est aussi trompeuse qu'une touche annoncee qui n'agit pas
        (finding `I8`).
        """
        if touche == "right":
            self.rang_de_page = min(self.rang_de_page + 1,
                                    len(self.pages()) - 1)
            return True
        if touche == "left":
            self.rang_de_page = max(self.rang_de_page - 1, 0)
            return True
        if touche == "escape":
            self.fermer()
            return True
        return False

    def on_key(self, evenement) -> None:
        """`⏎` est ARRETE sans agir ; le reste passe par :meth:`traiter`.

        `⏎` n'est pas annonce par la ligne de raccourcis du manuel : il ne doit
        donc rien faire, et `evenement.stop()` **coupe sa remontee vers
        l'application**.

        **Le motif ecrit ici jusqu'au 2026-09-04 etait FAUX, et il est garde en
        memoire plutot qu'efface** (revue de la story 11.9, couche 1 `F9`,
        mutant `M39`). Il disait : « le laisser monter jusqu'a `descendre()`
        empilerait un second ecran sur le premier ». Ce mecanisme n'existe pas :
        `textual` route une touche vers l'ecran **actif** puis vers l'`App`,
        **jamais** vers les ecrans *sous* la pile -- le `on_key` du palier
        recouvert n'est pas atteint. Le defaut du 2026-08-28 dont ce motif etait
        herite etait un defaut **d'API** (`descendre()` appele cinq fois en
        Python), pas un defaut de clavier.

        **Ce que `stop()` fait reellement, et c'est ce qui se mesure** : il
        empeche la touche d'atteindre `CoqueTui`. Aujourd'hui `BINDINGS` n'y lie
        pas `enter`, donc la garde est **preventive** -- une liaison globale
        `enter` posee demain agirait par-dessus le manuel sans elle.
        `tests/unit/tui/test_revue_11_9_lot_e5.py` la mesure par une coque
        temoin qui **journalise** ce qui lui remonte, avec son volet de morsure
        (`z`, que le manuel n'arrete pas, doit remonter). Le meme motif faux
        reste a relire sur `coque.EcranPasEncore.on_key`, qui le porte depuis
        avant cette story.
        """
        if evenement.key == "enter":
            evenement.stop()
            return
        if not self.traiter(evenement.key,
                            getattr(evenement, "character", None)):
            return
        evenement.stop()
        if evenement.key != "escape":
            # `Échap` a depile : l'ecran n'est plus monte, et le redessiner
            # viserait un arbre de widgets detruit.
            self.rafraichir()


__all__ = [
    "COLONNE_DE_L_ATELIER",
    "COLONNE_DE_L_OUVREUR",
    "COLONNE_DU_LIBELLE",
    "MARGE_DROITE",
    "RACCOURCIS_MANUEL",
    "SEPARATEUR_DES_LIBELLES",
    "TITRE_DU_BLOC_PARTOUT",
    "TITRE_DU_BLOC_PROPRES",
    "TITRE_DU_MANUEL",
    "EcranManuel",
    "Page",
    "atelier_lisible",
    "ateliers_d_une_entree",
    "groupes_du_manuel",
    "libelle_de_page",
    "lignes_d_une_entree",
    "mesure_de_la_page",
    "noms_de_domaine",
    "pages_du_manuel",
]
