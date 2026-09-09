# -*- coding: utf-8 -*-
"""Story 11.9, lot B -- l'etage 1 de l'aide, GENERALISE (`EPIC11-ARB-198`).

`F1` sur un champ dit **ce que ce champ attend** (`EPIC11-ARB-14`). Ce
mecanisme a ete livre **une fois**, en 11.5, sur `atelier_scan_completion`
(`OU_LIRE_LE_CHAMP`, `basculer_l_aide`, `tete`, chute au changement de ligne).
`EPIC11-ARB-198` tranche : on **generalise le livre, on ne le reecrit pas**.

**Ce module porte le MECANISME, jamais la DONNEE.** Chaque ecran reste le
porteur de sa propre table de phrases -- `atelier_scan_completion` garde
`OU_LIRE_LE_CHAMP`, et les trois ecrans enroles par cette story ecrivent la
leur dans leur propre module. Une table centrale ici aurait fait de ce fichier
un second lieu ou lire ce qu'un champ attend, c'est-a-dire exactement la
« seconde redaction » que le depot paie a chaque fois qu'il en tolere une.

Ce que le mecanisme garantit, et qui etait auparavant a la charge de chaque
site :

* **l'aide REMPLACE la consigne** (AC 1.2). Elle occupe un emplacement de tete
  qui existe dans les deux etats, si bien que le cardinal de lignes du corps
  est identique aide ouverte et aide fermee -- la grille 80 x 24 ne bouge pas ;
* **l'aide TOMBE au changement de champ** (AC 1.3), et elle tombe
  **structurellement** : :class:`ChampSuivi` compte les deplacements du
  curseur, l'etat retient ce compte au moment de `F1`, et se lit ferme des que
  le compte a bouge. Le site n'a aucun `self.aide = False` a poser dans chaque
  chemin de navigation -- c'est la forme qu'avait
  `atelier_scan_completion.avancer`, et un chemin de navigation ajoute plus
  tard l'aurait oublie sans que rien ne le dise.

  **La premiere redaction comparait le champ RETENU au champ COURANT, et elle
  ne TOMBAIT pas : elle se CACHAIT** (defaut `F1` de la revue du 2026-09-04,
  « Corrige » d'Egan). Une comparaison de valeurs ne distingue pas « on n'a pas
  bouge » de « on est revenu » : sur `E3-1`, ou `Tab` boucle entre deux lignes,
  `F1` puis deux `Tab` **rouvraient** l'aide sans que personne ne la redemande.
  Ce qui distingue les deux regimes est le **deplacement**, pas la valeur ;
* **`f1` est consommee dans l'ecran quand le focus est sur un champ, et
  seulement alors** (AC 1.4). :meth:`AideDeChamp.basculer` rend `False` sur une
  ligne que la table ne porte pas : la touche remonte alors a la liaison
  applicative, qui ouvre le manuel. Sans ce volet, le manuel s'ouvrirait
  par-dessus le formulaire -- ou, symetriquement, ne s'ouvrirait jamais.

**Le module n'importe aucun ecran au niveau module.** Les ecrans l'importent ;
un import en retour rendrait le cycle. :func:`ecrans_porteurs_d_une_table_d_aide`
balaie le paquet, et son import est donc **dans le corps de la fonction** --
meme contrainte d'architecture que `manuel.py` (AC 3.5), pour le meme motif :
vingt-cinq modules du paquet importent `coque`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from . import jetons

#: La marque qu'une phrase d'aide porte la ou la **valeur du contexte courant**
#: s'ecrit (AC 1.1 : « ce que le champ attend, les formes acceptees, et une
#: valeur du contexte courant »).
#:
#: **Une marque et non `str.format`** : une phrase d'aide est du texte pour
#: l'operateur, et `format` y interpreterait toute accolade -- un jour ou
#: l'autre, une phrase citera un gabarit `{lot}` et levera. Le remplacement est
#: litteral, donc sans surprise.
MARQUE_DE_LA_VALEUR = "{valeur}"

#: Ce qu'une valeur de contexte vaut quand le champ est **vide**.
#:
#: **C'est du VOCABULAIRE, pas de la donnee** -- la distinction que le
#: docstring du module tient. Une phrase d'aide appartient a son ecran ; le mot
#: par lequel trois ecrans disent « ce champ n'a rien » est le meme mot, et
#: l'ecrire trois fois le ferait diverger au premier ajustement -- c'est
#: exactement le motif de `jetons.CREUX_MINIMAL`, qui vit dans le module de
#: mesure apres avoir ete recopie quatre fois.
#:
#: Il ne se substitue a rien de ce que l'ecran affiche deja : le glyphe
#: `neutre` reste le second canal de « rien ici » sur la LIGNE du champ
#: (`DESIGN.md` section 6). Celui-ci se lit dans une phrase, ou un glyphe ne
#: dirait rien.
#:
#: **La phrase ci-dessus a ete DEMENTIE par la livraison qui l'ecrit**, et
#: c'est pourquoi elle est desormais **mesuree** plutot que rappelee.
#: `atelier_scan_calibrate` et `atelier_pdf_calibration` portaient chacun un
#: `AIDE_CHAMP_VIDE = "vide"` : sur le meme formulaire `E3-9`, `dpi` rendait
#: « rien de saisi » quand `etiquette` et `commentaire` rendaient « vide »
#: (defaut `F4` de la revue du 2026-09-03). Les trois frontieres qui ferment
#: les trois ecritures du defaut vivent dans
#: `tests/unit/tui/test_aide_de_champ.py`, section B4 : par la **valeur** (le
#: mot recopie), par le **role** (le repli d'un `saisie(…) or …`) et par le
#: **litteral rendu** depuis un `valeur_de_l_aide`.
#:
#: **Ce que ce mot ne couvre PAS, ecrit plutot que tu.** « Rien de saisi » dit
#: qu'une SAISIE est vide. Un objet qu'on n'a pas encore **designe** est autre
#: chose, et garde son propre mot -- `AIDE_SANS_SOURCE` (`atelier_scan`) et
#: `AIDE_SANS_SCAN` (`atelier_scan_calibrate`), tous deux « rien de designe ».
#: Les fondre ferait dire a l'aide d'un champ de fichier qu'on n'y a « rien
#: saisi », alors qu'on n'y saisit jamais rien. La distinction est deliberee ;
#: elle est ecrite ici pour que le prochain lecteur ne refasse pas le raccourci
#: en sens inverse.
VALEUR_ABSENTE = "rien de saisi"

#: Le nom de l'attribut de classe par lequel un ecran **declare** qu'il porte
#: une table d'aide de champ. C'est ce que
#: :func:`ecrans_porteurs_d_une_table_d_aide` cherche, et c'est ce qui rend
#: l'ensemble mesurable plutot que declaratif.
NOM_DE_LA_TABLE = "TABLE_D_AIDE"


# ---------------------------------------------------------------------------
# La liste BORNEE des ecrans porteurs (AC 1.5, `EPIC11-ARB-198`)
# ---------------------------------------------------------------------------

#: **L'ensemble EXACT des ecrans porteurs d'une table d'aide de champ.**
#:
#: `EPIC11-ARB-198` borne la liste, et un banc la mesure en **egalite** contre
#: le balayage du paquet : une assertion positive laisserait passer un ecran
#: oublie comme un ecran de trop.
#:
#: Le critere d'entree, et il se mesure : l'ecran porte un **formulaire** dont
#: le curseur designe une ligne a la fois (un modele `Formulaire*`), et sa
#: ligne de raccourcis annonce `F1`. Les quatre du depot au 2026-09-03 :
#:
#: * `atelier_scan_completion.EcranCompletionQr` -- le **modele**, livre en 11.5
#:   sous `EPIC11-ARB-14`. Il entre dans l'ensemble parce qu'il **porte** une
#:   table, pas parce que cette story lui en donne une : sa table reste la
#:   sienne, et cette story ne la reecrit pas ;
#: * `atelier_scan.EcranScanDepot` (`E3-1`), `atelier_scan_calibrate.EcranCalibrerLaChaine`
#:   (`E3-9`) et `atelier_pdf_calibration.EcranMireReglages` (`E5-6`) -- les
#:   trois qui **gagnent** une table ici.
ECRANS_A_TABLE_D_AIDE: frozenset[str] = frozenset({
    "mixed_media_utility.tui.atelier_pdf_calibration.EcranMireReglages",
    "mixed_media_utility.tui.atelier_scan.EcranScanDepot",
    "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrerLaChaine",
    "mixed_media_utility.tui.atelier_scan_completion.EcranCompletionQr",
})

#: **Les ecrans ECARTES, nommes avec leur motif.** Le silence sur un cas
#: limite rendrait l'ensemble indecidable : « pourquoi celui-la n'y est pas »
#: n'a pas de reponse mesurable si personne ne l'ecrit.
#:
#: Les trois motifs ci-dessous sont chacun **verifiables par un banc**, et le
#: sont : ce ne sont pas des opinions.
ECRANS_ECARTES: Mapping[str, str] = {
    "mixed_media_utility.tui.ecran_projet.EcranCreation": (
        "`AIDE_PARENT` (`ecran_projet.py:65`, rendue a `:938`) est bien une "
        "phrase d'aide de champ, mais elle est TOUJOURS affichee et n'est liee "
        "a aucun `F1` : ce n'est ni une table -- une seule phrase, pour une "
        "seule des deux lignes -- ni un etage 1 -- rien ne la bascule. L'ecran "
        "n'a d'ailleurs pas de modele `Formulaire*` : ses deux valeurs vivent "
        "sur lui, et `Tab` y change de ZONE et non de champ."),
    "mixed_media_utility.tui.atelier_pdf_calibration.EcranMireConfirmation": (
        "il RECOIT un formulaire pour en afficher les valeurs ; il n'a aucun "
        "curseur de champ, donc aucun champ sous lequel `F1` puisse dire quoi "
        "que ce soit."),
    "mixed_media_utility.tui.atelier_scan_calibrate.EcranCalibrationAConfirmer": (
        "meme motif que `EcranMireConfirmation` -- et sa ligne de raccourcis "
        "n'annonce meme pas `F1`."),
}


def ecrans_porteurs_d_une_table_d_aide() -> dict[str, type]:
    """Les ecrans du paquet qui **portent** une table d'aide de champ.

    Balaye le paquet par :func:`~mixed_media_utility.tui.manuel.classes_d_ecran`
    -- le balayage du depot, remonte dans `src/` par le lot A -- et retient les
    classes qui **declarent** :data:`NOM_DE_LA_TABLE` dans leur propre corps.

    **`vars(classe)` et non `getattr`** : un attribut herite ferait entrer une
    sous-classe qui n'a rien declare, et l'ensemble cesserait d'etre celui des
    porteurs pour devenir celui de leurs descendants.

    **L'import est dans le corps** (AC 3.5) : `manuel` balaie le paquet, donc
    il importe `coque`, que vingt-cinq modules importent deja. Un import au
    niveau de ce module-ci rendrait le cycle des le premier ecran qui l'appelle.
    """
    from .manuel import classes_d_ecran

    return {nom: classe for nom, classe in classes_d_ecran().items()
            if vars(classe).get(NOM_DE_LA_TABLE)}


# ---------------------------------------------------------------------------
# Le champ courant, et le COMPTE de ses deplacements
# ---------------------------------------------------------------------------

#: Le nom de l'attribut d'instance ou :class:`ChampSuivi` tient son compte.
#: **Un seul nom pour les quatre formulaires** : le compte est lu par
#: :func:`deplacements_du_champ` et par rien d'autre.
COMPTE_DES_DEPLACEMENTS = "_deplacements_du_champ"

#: Le nom de l'attribut par lequel un formulaire designe son champ courant.
#: Les quatre porteurs l'ecrivent `champ` ; c'est ce nom que
#: :class:`AideDeChamp` cherche pour verifier qu'on lui a bien passe un
#: formulaire SUIVI.
NOM_DU_CHAMP_COURANT = "champ"


class ChampSuivi:
    """Le champ courant d'un formulaire, qui **COMPTE ses deplacements**.

    **Pourquoi un descripteur, et pas un appel de plus.** L'aide devait tomber
    au changement de champ ; elle se contentait de retenir le champ sur lequel
    `F1` avait ete frappee et de le comparer au champ courant. Une comparaison
    de VALEURS ne distingue pas « on n'a pas bouge » de « on est revenu » :
    `Tab` bouclant sur un formulaire a deux lignes, deux frappes suffisaient a
    faire **reapparaitre** l'aide sans que personne ne l'ait redemandee. Elle
    se cachait, elle ne tombait pas (defaut `F1` de la revue du 2026-09-04,
    « Corrige » d'Egan, qui leve `EPIC11-ARB-198` sur ce point).

    Ce qui distingue les deux regimes n'est pas la valeur du champ mais le
    **deplacement** : `source -> dpi -> source` en fait deux, et l'aide doit
    donc etre tombee. Le compte est ce que ce descripteur tient.

    **Pourquoi le compter ICI plutot que dans chaque chemin de navigation.**
    Le docstring du module refuse depuis la 11.9 le `self.aide.fermer()` pose
    dans chaque `avancer`, `poser_la_source`, `poser_le_scan` -- « un chemin de
    navigation ajoute plus tard l'aurait oublie sans que rien ne le dise ». Un
    descripteur est le seul point de passage OBLIGE de toute ecriture du champ,
    d'ou qu'elle vienne : un chemin neuf est compte sans avoir rien a appeler,
    et un banc qui pose `formulaire.champ = ...` a la main l'est aussi.

    **Seules les affectations qui CHANGENT la valeur comptent.** Reposer le
    champ ou l'on est deja n'est pas un deplacement -- c'est ce que fait
    `poser_la_source` quand le curseur est deja sur le dpi --, et le compter
    ferait tomber une aide que rien n'a quittee.

    **Le defaut se lit par `getattr(cls, nom)`**, donc `__get__(None, cls)`
    rend la valeur de depart : c'est ce qu'un `@dataclass` appelle pour
    composer la signature de son `__init__` quand le defaut d'un champ est un
    descripteur (comportement documente depuis Python 3.10). Les quatre
    formulaires restent donc des dataclasses ordinaires, `champ` compris.
    """

    def __init__(self, defaut: str) -> None:
        self.defaut = defaut

    def __set_name__(self, proprietaire: type, nom: str) -> None:
        # La valeur vit sous un nom PRIVE dans le `__dict__` de l'instance.
        # Sous `nom`, elle marcherait encore aujourd'hui -- un descripteur de
        # DONNEE, c'est-a-dire celui qui a un `__set__`, prime sur le `__dict__`
        # de l'instance --, mais elle cesserait de marcher le jour ou `__set__`
        # disparaitrait : l'entree du `__dict__` prendrait alors la main en
        # silence, et le compte ne bougerait plus.
        self._prive = f"_{nom}_courant"

    def __get__(self, instance, proprietaire: type | None = None):
        if instance is None:
            return self.defaut
        return instance.__dict__.get(self._prive, self.defaut)

    def __set__(self, instance, valeur: str) -> None:
        if instance.__dict__.get(self._prive, self.defaut) != valeur:
            instance.__dict__[COMPTE_DES_DEPLACEMENTS] = (
                deplacements_du_champ(instance) + 1)
        instance.__dict__[self._prive] = valeur


def descripteur_du_champ(formulaire) -> ChampSuivi | None:
    """Le :class:`ChampSuivi` d'un formulaire, ou `None` s'il n'en a pas.

    Le balayage remonte la MRO : une sous-classe de formulaire herite du champ
    suivi de sa base, et refuser ce cas ferait de l'heritage une regression
    silencieuse.
    """
    for classe in type(formulaire).__mro__:
        candidat = vars(classe).get(NOM_DU_CHAMP_COURANT)
        if isinstance(candidat, ChampSuivi):
            return candidat
    return None


def deplacements_du_champ(formulaire) -> int:
    """Combien de fois le champ courant de ce formulaire a **change**.

    Un compte, jamais un booleen : deux deplacements qui ramenent au point de
    depart doivent se distinguer de zero deplacement, et c'est tout l'objet du
    correctif.
    """
    return getattr(formulaire, COMPTE_DES_DEPLACEMENTS, 0)


# ---------------------------------------------------------------------------
# Le mecanisme
# ---------------------------------------------------------------------------

@dataclass
class AideDeChamp:
    """L'etat de l'aide de champ d'un formulaire, et rien de plus.

    **Modele pur** : aucune dependance a `textual`, aucune lecture de disque.
    C'est ce qui rend les trois volets de l'AC 1 mesurables sans terminal.

    :param phrases: la table du porteur -- champ -> phrase. Elle **reste chez
        lui** : ce module ne connait aucune phrase.
    :param consigne: ce que l'emplacement de tete dit **aide fermee**. Vide est
        un regime nominal : sur les trois ecrans enroles par la story 11.9,
        l'emplacement est une ligne blanche du corps, si bien que l'aide
        remplace un blanc et que le dessin approuve ne bouge pas d'un caractere
        tant qu'elle est fermee.
    :param formulaire: le formulaire dont l'aide suit le curseur. **Obligatoire
        et sans defaut**, et c'est le point du correctif du 2026-09-04 : un
        porteur qui n'en passerait pas retomberait sur une aide qui se CACHE au
        lieu de tomber, sans que rien ne rougisse. Ici, il ne construit pas
        l'objet du tout. Son champ courant doit etre un :class:`ChampSuivi` --
        verifie a la construction, pour la meme raison : un formulaire non
        suivi rendrait un compte de deplacements eternellement nul, c'est-a-dire
        exactement le defaut, en silence.
    """

    phrases: Mapping[str, str]
    consigne: str = ""
    formulaire: object = field(kw_only=True)
    #: Le champ sur lequel `F1` a ete frappee, ou `None`.
    _champ_ouvert: str | None = field(default=None, init=False, repr=False)
    #: Le compte de deplacements **au moment ou `F1` a ete frappee**. C'est lui
    #: qui fait TOMBER l'aide (AC 1.3) plutot que la cacher : la comparaison de
    #: valeurs qu'il remplace ne distinguait pas « on n'a pas bouge » de « on
    #: est revenu », si bien que `Tab` bouclant rouvrait l'aide sans `F1`.
    _jalon: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if descripteur_du_champ(self.formulaire) is None:
            raise TypeError(
                f"{type(self.formulaire).__name__}.{NOM_DU_CHAMP_COURANT} "
                f"n'est pas un {ChampSuivi.__name__} : l'aide ne saurait pas "
                "que le curseur a bouge, et se rouvrirait toute seule au "
                "retour sur le champ. Declarer "
                f"`{NOM_DU_CHAMP_COURANT}: str = "
                f"aide_de_champ.{ChampSuivi.__name__}(<defaut>)`.")

    # -- lecture ------------------------------------------------------------

    def porte(self, champ: str) -> bool:
        """La table dit-elle quelque chose de ce champ ?"""
        return champ in self.phrases

    def ouverte(self, champ: str) -> bool:
        """L'aide est-elle ouverte **sur ce champ-la, et sans qu'on ait bouge** ?

        **Deux conditions, et chacune ferme un mode de panne distinct** :

        * le champ, sans quoi l'aide d'une ligne s'afficherait sur une autre ;
        * le **jalon**, sans quoi elle se contenterait de se CACHER. Revenir sur
          le champ la rouvrirait, alors que personne n'a refrappe `F1` -- le
          defaut mesure le 2026-09-04 sur `E3-1`, ou `Tab` boucle entre deux
          lignes et ou deux frappes suffisaient.

        Une lecture PURE : le compte est tenu par :class:`ChampSuivi`, du cote
        du formulaire. Le faire consommer ici -- une ecriture dans une lecture
        -- ne repondrait d'ailleurs pas : sans lecture intercalee entre les deux
        deplacements, rien ne consommerait le jeton.
        """
        return (self._champ_ouvert == champ
                and self._jalon == deplacements_du_champ(self.formulaire))

    def phrase(self, champ: str, valeur: str = "") -> str:
        """La phrase du champ, sa **valeur de contexte** posee.

        Le remplacement est litteral (voir :data:`MARQUE_DE_LA_VALEUR`), et une
        phrase sans marque rend la phrase telle quelle : c'est le regime du
        modele de 11.5, dont les phrases nomment un endroit de la planche
        imprimee et ne portent aucune valeur d'execution.
        """
        return self.phrases[champ].replace(MARQUE_DE_LA_VALEUR, valeur)

    def tete(self, champ: str, valeur: str = "") -> str:
        """L'emplacement de tete : la consigne, ou l'aide du champ courant.

        C'est `atelier_scan_completion.FormulaireDeCompletion.tete`, generalise
        -- meme forme, meme contrat, une seule redaction.
        """
        if not self.ouverte(champ):
            return self.consigne
        return self.phrase(champ, valeur)

    def ligne_de_tete(self, champ: str, *, utile: int, valeur: str = "",
                      indent: str = "", ascii_seul: bool = False) -> str:
        """La **ligne** de tete, tenue dans `utile` colonnes (AC 5.5).

        Le budget se **lit** de l'appelant, qui le tient de
        `jetons.largeur_utile()` : il ne se recopie nulle part, et surtout pas
        ici -- le depot a paye trois fois la recopie d'une borne
        (`CANONICAL_ID_MAX_LENGTH`).

        **C'est la VALEUR qui est abregee, jamais la phrase.** Une phrase
        tronquee par la fin perd ce que le champ attend, c'est-a-dire tout son
        objet ; une valeur abregee au milieu garde ses deux bouts, qui sont ce
        qui l'identifie (`jetons.abreger_nom`). `jetons.ajuster` reste en
        dernier recours, pour la meme raison qu'ailleurs dans le depot : sans
        lui, `textual` replierait la ligne sur une hauteur qui ne la dessine
        pas.

        Aide fermee, la ligne est la consigne -- **sans indentation quand la
        consigne est vide**, si bien qu'une ligne blanche reste blanche et non
        une ligne de blancs.
        """
        texte = self.tete(champ)
        if self.ouverte(champ) and valeur:
            # Le cout de la partie FIXE se mesure dans le regime ou la ligne
            # sera lue : le repli ASCII fait grossir les glyphes, et mesurer
            # avant lui rendrait la borne fausse d'exactement ce qu'ils
            # coutent -- le piege que `jetons.points_d_abregement` documente.
            fixe = indent + self.phrase(champ, "")
            if ascii_seul:
                fixe = jetons.replier_ascii(fixe)
                # **La VALEUR se replie AVANT d'etre mesuree, elle aussi.** La
                # premiere redaction ne repliait que la partie fixe :
                # `abreger_nom` comptait alors les colonnes de la valeur BRUTE,
                # si bien qu'un glyphe qui GROSSIT au repli (`…` -> `...`, une
                # colonne contre trois) faisait deborder la ligne, et
                # `jetons.ajuster` rattrapait la borne **en tronquant par la
                # fin** -- c'est-a-dire en sacrifiant la phrase, l'inverse exact
                # de ce que le docstring ci-dessus promet. Le glyphe est dans la
                # donnee livree, pas seulement dans une saisie :
                # `atelier_scan.AIDE_DPI_REFUSE` porte un tiret cadratin et
                # mesure 20 colonnes brutes contre 21 repliees (defaut `F-C2-1`
                # de la revue du 2026-09-04). Troisieme occurrence dans ce depot
                # de la famille « mesurer avant le repli ».
                valeur = jetons.replier_ascii(valeur)
            texte = self.phrase(
                champ, jetons.abreger_nom(
                    valeur, max(utile - jetons.colonnes(fixe), 1), ascii_seul))
        if not texte:
            return ""
        return jetons.ajuster(indent + texte, utile, ascii_seul)

    # -- ecriture -----------------------------------------------------------

    def basculer(self, champ: str) -> bool:
        """`F1` : ouvrir l'aide de ce champ, ou la refermer.

        **Rend `True` quand la touche est CONSOMMEE, `False` sinon** (AC 1.4).
        Sur une ligne que la table ne porte pas -- c'est-a-dire hors champ --
        elle n'est pas consommee, et la liaison applicative ouvre le manuel.
        C'est le volet symetrique, et il compte autant que l'autre : sans lui,
        `F1` n'ouvrirait jamais le manuel depuis un ecran a formulaire.
        """
        if not self.porte(champ):
            return False
        if self.ouverte(champ):
            self._champ_ouvert = None
        else:
            self._champ_ouvert = champ
            # Le jalon se pose ICI et nulle part ailleurs : c'est la frappe de
            # `F1` qui date l'ouverture, et tout deplacement posterieur du
            # curseur la perime.
            self._jalon = deplacements_du_champ(self.formulaire)
        return True

    def fermer(self) -> None:
        """Refermer l'aide sans consommer de touche -- un changement de zone,
        une validation. La chute au changement de CHAMP, elle, n'a besoin de
        personne."""
        self._champ_ouvert = None


def ligne_de_tete_de(ecran, champ: str, *, utile: int, indent: str = "",
                     ascii_seul: bool = False) -> str:
    """La ligne de tete d'un ecran **porteur**, en une seule redaction.

    Le contrat d'un porteur tient en trois points, et ce sont eux que
    :data:`ECRANS_A_TABLE_D_AIDE` borne :

    * l'attribut de classe :data:`NOM_DE_LA_TABLE`, qui le declare ;
    * `ecran.aide`, son :class:`AideDeChamp` ;
    * `ecran.valeur_de_l_aide(champ)`, la **valeur du contexte courant** du
      champ vise (AC 1.1) -- vide quand l'ecran n'en porte aucune, ce qui est le
      regime du modele de 11.5.

    Cette fonction existe pour que les quatre porteurs n'en ecrivent pas quatre
    versions : c'est la meme phrase de composition partout, et une seconde
    redaction divergerait sur la seule chose qui compte -- le budget de
    largeur.
    """
    return ecran.aide.ligne_de_tete(
        champ, utile=utile, valeur=ecran.valeur_de_l_aide(champ),
        indent=indent, ascii_seul=ascii_seul)


__all__ = [
    "AideDeChamp",
    "COMPTE_DES_DEPLACEMENTS",
    "ChampSuivi",
    "NOM_DU_CHAMP_COURANT",
    "ECRANS_A_TABLE_D_AIDE",
    "ECRANS_ECARTES",
    "MARQUE_DE_LA_VALEUR",
    "NOM_DE_LA_TABLE",
    "VALEUR_ABSENTE",
    "deplacements_du_champ",
    "descripteur_du_champ",
    "ecrans_porteurs_d_une_table_d_aide",
    "ligne_de_tete_de",
]
