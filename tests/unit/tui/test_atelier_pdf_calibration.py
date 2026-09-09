# -*- coding: utf-8 -*-
"""Story 11.7, lot H -- `E5-6` a `E5-6e`, la mire de calibration (AC 8).

**Ce banc et lui seul mesure le lot H.** La regle de decoupage de la fiche est
stricte et elle a ete payee trois fois sur ce depot : « aucun lot ne partage un
fichier de banc avec un autre ». `git add -N` et `git commit -- <chemins>`
protegent par FICHIER, jamais a l'interieur d'un fichier -- le commit `82e64de`
du 2026-08-30 a embarque ~200 lignes du lot voisin sous un message qui parlait
d'autre chose, alors que les deux agents appliquaient la regle a la lettre.

**Trois absences se mesurent ici comme des frontieres negatives**, et c'est ce
qui distingue une absence voulue d'un oubli :

1. **aucun rang de version** sur `E5-6d` (`EPIC5-ARB-82`) -- la mire ne declare
   ni rush, ni lot, ni cadence, donc elle n'a pas de lot dont numeroter les
   tirages. Ni l'ensemble des issues, ni le module, ne portent le vocabulaire
   des rangs ;
2. **aucune barre, aucun compte de pastilles** sur `E5-6c` (AC 8.6) -- le coeur
   ne peut pas l'alimenter, mesure a l'appui ;
3. **aucun poids de fichier, aucune duree** -- personne n'a pese ni chronometre
   une mire, et `EPIC7-ARB-67` interdit de rendre un temps sans mesure.

Chaque frontiere negative porte son **volet symetrique** : la mesure cherche
aussi la chose ailleurs, faute de quoi un grep sur un module vide serait vert
sans rien mesurer.

**Regle des fabriques** (`CLAUDE.md`), appliquee a ses quatre points. Deux
collections sont parcourues par le code de ce module, et pour chacune la cible
est **au milieu** :

* les **trois issues de `E5-6d`** -- `EcranMireExiste.rendu_des_issues` les
  balaie en `zip` avec leur mention, et l'issue destructive est la **deuxieme**
  des trois : ni la premiere, qu'un `issues[0]` rendrait, ni la derniere, qu'un
  `continue` -> `break` laisserait passer ;
* les **trois suites de `E5-6e`** -- la suite contextuelle qui revient a la mire
  est la deuxieme des trois, avant que `EcranResultat` n'ajoute son retour.

Les valeurs sont **distinguables** : trois libelles differents, trois mentions
differentes (dont une vide), et la position se verifie sur la liste que le
**CODE** parcourt (`choix.issues`), pas sur celle que la fabrique ecrit.

**Rien n'est tape a la main de ce que le produit sait construire** : le nom du
fichier sort de `io.naming.build_calibration_pdf_filename`, le cardinal de
pastilles de `patch_presets`, la liste des arguments de coeur de la
**signature reelle** de `makepdf.generer_la_page_de_calibration`. Une valeur
recopiee coinciderait le jour ou elle est ecrite et divergerait sans qu'aucune
etape n'echoue.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parents[3] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mixed_media_utility import makepdf, page_templates, patch_presets, pdf_composition
from mixed_media_utility.io import naming, project_layout
from mixed_media_utility.tui import atelier_pdf_calibration as mire
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.coque import (Contexte, CoqueTui, EcranPasEncore,
                                           PalierTemoin)
from mixed_media_utility.tui.execution import (EcranChiffre, EcranResultat,
                                               RACCOURCIS_RESULTAT,
                                               RACCOURCIS_RESULTAT_AVEC_JOURNAL)
from mixed_media_utility.tui.avancement import Journal
from mixed_media_utility.tui.panneau import RIEN_ECRIT, ChoixExclusif

from outils_frontiere import chaines_de_code, constantes_entieres, identifiants

#: Les deux regimes, portes par tout test qui touche au rendu. « Ne jamais
#: ajuster un test au code : tout test parametre porte les deux regimes. »
MODES = [pytest.param(False, id="utf8"), pytest.param(True, id="ascii")]

#: Le plancher d'`EPIC11-ARB-21`, et la zone ecrivable qui s'en deduit.
PLANCHER = (80, 24)
UTILE = jetons.largeur_utile(PLANCHER[0])

#: Le projet et la chaine des maquettes. Les employer permet de confronter le
#: rendu au dessin sans inventer d'identifiant.
PROJET = "projet_demo"
CHAINE = "hp-envy-4520-tiff-600-dpi-auto-corr-off"
COMMENTAIRE = "passe du 27/08, papier mat"

#: Le module sous mesure, pour les frontieres qui lisent du code.
MODULE = Path(mire.__file__)

#: L'horodatage pose sur la mire deja ecrite. Fixe, pour que la date rendue ne
#: depende ni de l'horloge ni du jour de la mesure ; lu par `datetime` local,
#: donc **jamais compare a un litteral** -- c'est le produit qui la formate.
QUAND_DE_LA_MIRE = 1_756_282_440.0


# ---------------------------------------------------------------------------
# Fabriques
# ---------------------------------------------------------------------------

def _formulaire(chaine: str = CHAINE,
                commentaire: str = COMMENTAIRE) -> mire.FormulaireDeLaMire:
    return mire.FormulaireDeLaMire(chaine=chaine, commentaire=commentaire)


def _presente(tmp_path: Path | None = None,
              quand: float | None = QUAND_DE_LA_MIRE) -> mire.MirePresente:
    """Une mire deja ecrite, **nommee par le coeur** et jamais tapee."""
    racine = Path("/projets") if tmp_path is None else tmp_path
    chemin = (racine / project_layout.PLANCHES_DIRNAME
              / naming.build_calibration_pdf_filename(PROJET, CHAINE))
    return mire.MirePresente(chemin, quand)


def _app(ecran, **reglages) -> CoqueTui:
    return CoqueTui(paliers=[PalierTemoin("Ateliers", "Q quitter"), ecran],
                    contexte=Contexte(projet=PROJET), **reglages)


def _monte(app, scenario, banc):
    async def tour(pilote):
        pilote.app.descendre()
        await pilote.pause()
        return await scenario(pilote)

    return banc(app, tour)


def _figer_le_rotor(ecran) -> None:
    """Arreter le minuteur du rotor et le ramener a son origine.

    **Ce banc ne mesure jamais une horloge**, et il l'a paye : `E5-6c` avance
    son rotor toutes les :data:`PERIODE_DU_ROTOR` secondes, y compris pendant
    les `await` d'un scenario. Deux tests d'ici se sont ainsi contredits -- l'un
    voulait `pas` immobile apres une frappe, l'autre le voulait mobile --, tous
    deux verts en isolation et rouges sous charge, **sans qu'aucun code ne
    change**. Un verdict qui depend du moment ou l'ordonnanceur rend la main
    n'est pas un verdict.

    La question a poser a chaque test de ce fichier est donc : « passerait-il si
    le temps ne s'ecoulait pas ? ». Ici la reponse est oui, parce que le
    mecanisme est **pilote** -- `avancer_le_rotor` est appelee explicitement --
    au lieu d'etre attendu.

    Sans effet sur les quatre autres ecrans, qui ne portent aucun minuteur.
    """
    minuteur = getattr(ecran, "minuteur", None)
    if minuteur is None:
        return
    minuteur.stop()
    ecran.minuteur = None
    # L'origine est **posee** et non supposee : entre le montage et l'arrivee du
    # scenario, l'horloge a deja pu faire tourner le rotor de quelques pas.
    ecran.pas = 0


def _lignes(ecran, banc, ascii_seul: bool = False,
            avant=None) -> list[str]:
    """Les lignes de la zone centrale, **telles qu'elles sont dessinees**.

    On lit le widget monte et non le modele : c'est la seule mesure qui voie ce
    que l'operateur voit, y compris le repli ASCII et l'ajustement de largeur.
    """
    async def scenario(pilote):
        _figer_le_rotor(pilote.app.screen)
        if avant is not None:
            avant(pilote.app.screen)
            pilote.app.screen.rafraichir()
            await pilote.pause()
        rendues: list[str] = []
        for widget in pilote.app.screen.query("Static"):
            rendues.extend(jetons.texte_affiche(
                str(widget.render())).split("\n"))
        return rendues

    return _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)


def _etat(ecran, banc, ascii_seul: bool = False) -> str:
    async def scenario(pilote):
        from textual.widgets import Static
        _figer_le_rotor(pilote.app.screen)
        return jetons.texte_affiche(
            str(pilote.app.screen.query_one("#etat", Static).content))

    return _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)


def _raccourcis(ecran, banc, ascii_seul: bool = False) -> str:
    async def scenario(pilote):
        from textual.widgets import Static
        _figer_le_rotor(pilote.app.screen)
        return jetons.texte_affiche(
            str(pilote.app.screen.query_one("#raccourcis", Static).content))

    return _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)


# ===========================================================================
# AC 8.2 -- les donnees imposees se DERIVENT, aucun nombre recopie
# ===========================================================================

def test_le_total_de_pastilles_est_la_SOMME_de_ses_deux_familles():
    """AC 8.2 : `164 = 130 + 34`, et les trois nombres viennent du coeur.

    Egan a corrige deux fois cette page -- « il y en a un sacre paquet » -- et
    la seconde fois **contre une premiere reponse qui disait 34**. Le treillis
    central porte les valeurs sous le seuil de saturation en double replicat ;
    le bandeau lateral porte celles du preset. L'ecran montre le **total**, avec
    sa decomposition, et aucun des trois n'est ecrit ici.
    """
    donnees = mire.donnees_imposees()
    assert donnees.pastilles == patch_presets.calibration_page_patch_count(
        donnees.preset)
    assert donnees.treillis == patch_presets.calibration_lattice_patch_count()
    assert donnees.temoins == donnees.pastilles - donnees.treillis
    # Le total est bien une somme de deux familles NON VIDES : une decomposition
    # dont l'une des parts vaudrait zero se lirait comme une soustraction juste
    # tout en decrivant une page qui n'existe pas.
    assert donnees.treillis > 0 and donnees.temoins > 0


def test_les_temoins_se_derivent_AUSSI_du_preset_par_une_AUTRE_route():
    """AC 8.2, seconde moitie : `34 = 17 x 2`.

    Deux routes vers le meme nombre -- la soustraction (`164 - 130`) et le
    produit (`len(value_ids) x repetition`) -- et le banc les confronte. Aucune
    des deux ne peut donc deriver seule sans que l'autre le dise : un treillis
    qui changerait de cardinal sans que le preset bouge ferait rougir ici, et
    c'est exactement la divergence qu'un `34` recopie ne montrerait jamais.
    """
    donnees = mire.donnees_imposees()
    preset = patch_presets.get_patch_preset(donnees.preset)
    assert mire.temoins_du_bandeau(donnees.preset) == donnees.temoins
    assert donnees.temoins == len(preset.value_ids) * preset.repetition


def test_le_preset_de_la_mire_est_celui_que_le_COEUR_prendra():
    """AC 8.2 : la TUI ne passe aucun `--nombre-patchs`, donc le defaut vaut.

    Et le preset retenu porte bien le **bandeau de temoins** : un preset qui
    n'en porterait pas rendrait la decomposition affichee fausse -- « 130
    treillis + 34 temoins » sur une page sans bandeau --, et rien a l'ecran ne
    le dirait.
    """
    donnees = mire.donnees_imposees()
    assert donnees.preset == pdf_composition.DEFAULT_PATCH_PRESET
    assert patch_presets.calibration_page_carries_witness_band(donnees.preset)
    assert donnees.preset in patch_presets.CALIBRATION_PAGE_BAND_PRESETS


def test_le_format_la_marge_le_dpi_et_le_cardinal_de_pages_viennent_du_COEUR():
    """AC 8.2 : quatre valeurs de plus, quatre lectures du registre.

    `pages` vaut le cardinal d'une mire tel que la composition le pose
    (`CALIBRATION_ONLY_PAGE_COUNT`) -- c'est lui qui fonde tout le reste de
    l'AC 8.6 : une page, donc un seul jalon, donc pas de barre.
    """
    donnees = mire.donnees_imposees()
    assert donnees.page_format == page_templates.DEFAULT_PAGE_FORMAT
    assert donnees.marge == page_templates.DEFAULT_MARGIN_PRESET
    assert donnees.dpi == pdf_composition.RENDER_DPI_DEFAULT
    assert donnees.pages == pdf_composition.CALIBRATION_ONLY_PAGE_COUNT


def test_AUCUN_nombre_de_la_calibration_n_est_un_LITTERAL_du_module():
    """AC 8.2, la frontiere negative : `164`, `130`, `34`, `17` et `600`.

    C'est la seule mesure qui attrape la regression que l'AC vise : un module
    qui **derive** ses nombres et un module qui les **recopie** rendent les
    memes lignes le jour ou on les ecrit. Seule l'absence du litteral distingue
    les deux, et elle se mesure sur l'AST -- un grep de texte mordrait dans les
    commentaires qui expliquent precisement pourquoi ces nombres n'y sont pas.
    """
    donnees = mire.donnees_imposees()
    preset = patch_presets.get_patch_preset(donnees.preset)
    # `preset.repetition` vaut deux et n'entre PAS dans la liste : `2` est un
    # entier de mise en page autant qu'un facteur de replicat, et l'interdire
    # rendrait le module inecrivable sans rien mesurer de plus -- c'est le
    # produit `17 x 2` qui est derive, et le test precedent le mesure.
    interdits = {donnees.pastilles, donnees.treillis, donnees.temoins,
                 donnees.dpi, len(preset.value_ids)}
    trouves = interdits & set(constantes_entieres(MODULE))
    assert not trouves, trouves


def test_la_frontiere_des_LITTERAUX_voit_vraiment_des_entiers():
    """Le volet symetrique : la mesure precedente n'est pas vide de sens.

    Un `constantes_entieres` qui rendrait une liste vide -- module illisible,
    outil casse -- ferait passer le test precedent sans rien mesurer. On exige
    donc que le module porte bien des entiers, et qu'ils soient ceux de la mise
    en page (les seuls qu'il ait le droit d'ecrire).
    """
    entiers = set(constantes_entieres(MODULE))
    assert entiers, "aucune constante entiere lue : la frontiere ne mesure rien"
    assert mire.LARGEUR_DE_LA_VALEUR in entiers


# ===========================================================================
# AC 8.1 -- DEUX champs exactement, chacun nommant son argument de coeur
# ===========================================================================

def test_le_formulaire_porte_EXACTEMENT_deux_champs():
    """AC 8.1, `EPIC11-ARB-36` : un ensemble **exact**, jamais une inclusion.

    « Ce formulaire porte un champ de chaine » resterait vrai avec cinq champs
    de plus. Ce qui se mesure est que l'ensemble des champs saisissables est
    **exactement** {chaine, commentaire} -- c'est-a-dire que les patchs, la
    geometrie et le dpi restent des donnees imposees.
    """
    assert set(mire.FormulaireDeLaMire().champs()) == {mire.CHAMP_CHAINE,
                                                       mire.CHAMP_COMMENTAIRE}
    assert len(mire.FormulaireDeLaMire().champs()) == 2
    assert set(mire.LIBELLES_DES_CHAMPS) == set(
        mire.FormulaireDeLaMire().champs())


def test_chaque_champ_NOMME_un_argument_REEL_du_coeur():
    """AC 8.1 : « un champ sans argument est un defaut, pas une amelioration ».

    La confrontation se fait a la **signature** de
    `makepdf.generer_la_page_de_calibration`, jamais a une liste recopiee : un
    argument renomme au coeur ferait rougir ici, ce qu'une seconde liste ne
    verrait pas.
    """
    parametres = inspect.signature(
        makepdf.generer_la_page_de_calibration).parameters
    assert set(mire.ARGUMENTS_DU_COEUR) == set(
        mire.FormulaireDeLaMire().champs())
    inconnus = set(mire.ARGUMENTS_DU_COEUR.values()) - set(parametres)
    assert not inconnus, inconnus


def test_les_arguments_rendus_par_le_formulaire_sont_LIABLES_a_la_signature():
    """AC 8.1, l'autre moitie : la table n'est pas declarative, elle est APPELEE.

    Une table exacte qui ne serait lue par personne serait de la documentation.
    On verifie donc que ce que le formulaire **rend** se lie a la signature du
    coeur : une cle inventee y leverait, au lieu d'etre ignoree en silence.
    """
    arguments = _formulaire().arguments_du_coeur()
    assert set(arguments) == set(mire.ARGUMENTS_DU_COEUR.values())
    inspect.signature(makepdf.generer_la_page_de_calibration).bind_partial(
        Path("/projet"), **arguments)
    assert arguments[mire.ARGUMENTS_DU_COEUR[mire.CHAMP_CHAINE]] == CHAINE
    assert arguments[mire.ARGUMENTS_DU_COEUR[mire.CHAMP_COMMENTAIRE]] == COMMENTAIRE


def test_un_commentaire_VIDE_part_a_None_et_non_a_la_chaine_vide():
    """Le coeur distingue les deux : `""` y serait un commentaire blanc."""
    arguments = _formulaire(commentaire="   ").arguments_du_coeur()
    assert arguments[mire.ARGUMENTS_DU_COEUR[mire.CHAMP_COMMENTAIRE]] is None


def test_les_blancs_de_bord_sont_retires_UNE_fois_pour_les_TROIS_surfaces():
    """La valeur affichee, le nom derive et ce qui part au coeur.

    Ne rogner que l'affichage laisserait partir `'   '` comme nom de chaine --
    defaut deja paye sur le formulaire de calibration du Scan, ou le document de
    profil a porte un libelle blanc.
    """
    formulaire = _formulaire(chaine=f"  {CHAINE}  ")
    assert formulaire.saisie(mire.CHAMP_CHAINE) == CHAINE
    assert formulaire.arguments_du_coeur()[
        mire.ARGUMENTS_DU_COEUR[mire.CHAMP_CHAINE]] == CHAINE
    assert not mire.FormulaireDeLaMire(chaine="   ").peut_continuer


@pytest.mark.parametrize("caractere", ["q", "e", "r", "t"])
def test_AUCUNE_lettre_n_est_un_raccourci_dans_un_champ(caractere):
    """`EPIC11-ARB-68` : « aucune lettre n'est un raccourci dans un champ ».

    Les quatre lettres choisies sont celles qui portent un raccourci ailleurs
    dans la TUI (`q` quitte, `e` editait, `r` remettait). Le defaut de cette
    famille est **silencieux** : il rend une valeur plausible.
    """
    formulaire = mire.FormulaireDeLaMire()
    assert formulaire.frapper(caractere)
    assert formulaire.chaine == caractere


def test_Tab_fait_le_TOUR_des_deux_champs_dans_les_deux_sens():
    formulaire = mire.FormulaireDeLaMire()
    vus = [formulaire.champ]
    for _ in range(len(formulaire.champs())):
        formulaire.avancer(1)
        vus.append(formulaire.champ)
    assert vus == [mire.CHAMP_CHAINE, mire.CHAMP_COMMENTAIRE,
                   mire.CHAMP_CHAINE]
    formulaire.avancer(-1)
    assert formulaire.champ == mire.CHAMP_COMMENTAIRE


def test_la_frappe_vise_le_champ_AU_FOCUS_et_pas_un_autre():
    """L'appariement a risque du formulaire : ce que la frappe ecrit."""
    formulaire = mire.FormulaireDeLaMire()
    formulaire.avancer(1)
    formulaire.frapper("z")
    assert formulaire.commentaire == "z"
    assert formulaire.chaine == ""
    assert formulaire.effacer()
    assert formulaire.commentaire == ""
    assert not formulaire.effacer()


# ===========================================================================
# AC 8.4 -- aucun glyphe de focus hors des champs saisissables
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_UN_SEUL_glyphe_de_focus_est_dessine_sur_E5_6(ascii_seul, banc):
    """AC 8.4. Les lignes imposees ne sont pas atteignables : une invite posee
    sur l'une d'elles serait une cible qui ne fait rien.

    On compte les lignes de la zone centrale qui portent le glyphe d'invite
    **dans sa colonne**, celle ou une ligne de champ le pose. Un ensemble exact
    de un : ni zero -- le focus disparaitrait --, ni deux.
    """
    invite = jetons.glyphes(ascii_seul)["invite"]
    colonne = len(mire.INDENT_DU_CURSEUR) + mire.LARGEUR_DU_LIBELLE
    lignes = _lignes(mire.EcranMireReglages(PROJET, None,
                                            formulaire=_formulaire()),
                     banc, ascii_seul)
    portent = [ligne for ligne in lignes
               if len(ligne) > colonne and ligne[colonne] == invite]
    assert len(portent) == 1, portent
    libelle = mire.LIBELLES_DES_CHAMPS[mire.CHAMP_CHAINE]
    assert (jetons.replier_ascii(libelle) if ascii_seul
            else libelle) in portent[0]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_glyphe_de_focus_SUIT_le_champ_courant(ascii_seul, banc):
    """L'appariement a risque du rendu : le champ au focus contre la ligne.

    Deux champs, donc deux etats a mesurer -- et il faut les deux : un rendu qui
    poserait toujours l'invite sur la premiere ligne serait juste au montage.
    """
    invite = jetons.glyphes(ascii_seul)["invite"]
    colonne = len(mire.INDENT_DU_CURSEUR) + mire.LARGEUR_DU_LIBELLE

    def portant(lignes):
        return [ligne for ligne in lignes
                if len(ligne) > colonne and ligne[colonne] == invite]

    ecran = mire.EcranMireReglages(PROJET, None, formulaire=_formulaire())
    lignes = _lignes(ecran, banc, ascii_seul,
                     avant=lambda e: e.formulaire.avancer(1))
    marquees = portant(lignes)
    assert len(marquees) == 1, marquees
    plie = (jetons.replier_ascii if ascii_seul else (lambda texte: texte))
    assert plie(mire.LIBELLES_DES_CHAMPS[mire.CHAMP_COMMENTAIRE]) in marquees[0]
    assert plie(mire.LIBELLES_DES_CHAMPS[mire.CHAMP_CHAINE]) not in marquees[0]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_TROIS_lignes_imposees_sont_bien_AFFICHEES(ascii_seul, banc):
    """AC 8.2 : le volet positif de l'absence de focus.

    Sans lui, un ecran qui aurait **perdu** son bloc impose passerait la mesure
    du glyphe unique -- il n'y aurait plus rien pour en porter un.
    """
    donnees = mire.donnees_imposees()
    lignes = _lignes(mire.EcranMireReglages(PROJET, None,
                                            formulaire=_formulaire()),
                     banc, ascii_seul)
    texte = "\n".join(lignes)
    for libelle in (mire.LIBELLE_PASTILLES, mire.LIBELLE_PATCHS,
                    mire.LIBELLE_FORMAT_DPI):
        attendu = jetons.replier_ascii(libelle) if ascii_seul else libelle
        assert attendu in texte, libelle
    assert str(donnees.pastilles) in texte
    assert str(donnees.treillis) in texte
    assert donnees.preset in texte


# ===========================================================================
# AC 8.3 -- le nom est derive, et son CONDENSAT n'est JAMAIS elide
# ===========================================================================

def test_le_nom_est_celui_que_le_COEUR_compose():
    assert mire.nom_de_la_mire(PROJET, CHAINE) == \
        naming.build_calibration_pdf_filename(PROJET, CHAINE)
    assert mire.DOSSIER_DE_LA_MIRE == project_layout.PLANCHES_DIRNAME
    assert mire.destination_de_la_mire(PROJET) == \
        f"{PROJET}/{project_layout.PLANCHES_DIRNAME}/"


@pytest.mark.parametrize("largeur", [30, 36, 42, 50, 60, 76])
@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_CONDENSAT_survit_a_toutes_les_largeurs(largeur, ascii_seul):
    """AC 8.3 : « le condensat n'est jamais elide ».

    C'est lui qui porte l'identite de la chaine : `normalize_identifier` est
    **non injective**, donc deux libelles distincts qui se normalisent en un
    meme slug ne se separent que par leur condensat. Un nom abrege qui le
    perdrait afficherait deux fichiers differents sous une meme ligne.

    Les largeurs balayees vont **sous** la longueur du nom complet (76) : c'est
    le seul regime ou l'abregement joue, et c'est donc le seul ou la mesure a un
    sens.
    """
    condensat = naming.scan_chain_suffix(CHAINE)
    nom = mire.nom_de_la_mire(PROJET, CHAINE)
    abrege = mire.abreger_la_mire(nom, CHAINE, largeur, ascii_seul)
    assert condensat in abrege, abrege
    assert abrege.endswith("_calibration.pdf"), abrege
    assert jetons.colonnes(abrege) <= largeur, (abrege, largeur)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_l_ELLIPSE_tombe_dans_le_slug_lisible_et_nulle_part_ailleurs(ascii_seul):
    """AC 8.3 : « l'ellipse se deplace dans le slug lisible ».

    Elle precede donc strictement le condensat. Un `abreger_nom` -- qui coupe au
    **milieu** -- poserait l'ellipse au milieu du nom entier, c'est-a-dire dans
    le condensat des que la tete est longue : c'est le mutant que ce test tue.
    """
    points = jetons.points_d_abregement(ascii_seul)
    nom = mire.nom_de_la_mire(PROJET, CHAINE)
    abrege = mire.abreger_la_mire(nom, CHAINE, 50, ascii_seul)
    assert points in abrege
    assert abrege.index(points) < abrege.index(naming.scan_chain_suffix(CHAINE))
    # Une seule ellipse : deux diraient qu'on a coupe des deux cotes, donc que
    # la queue identifiante a ete entamee.
    assert abrege.count(points) == 1, abrege


def test_deux_libelles_qui_se_normalisent_PAREIL_rendent_deux_noms_abreges_DIFFERENTS():
    """AC 8.3, et c'est la mesure qui donne son sens a tout le reste.

    « hp envy » et « hp-envy » rendent le **meme slug**. S'ils rendaient aussi
    le meme nom abrege, deux chaines de scan distinctes se liraient comme un
    seul fichier a l'ecran -- et l'operateur en ecraserait une pour l'autre.
    """
    largeur = 34
    premier = "hp envy 4520 tiff 600 dpi auto corr off"
    second = "hp-envy-4520-tiff-600-dpi-auto-corr-off"
    assert naming.normalize_identifier(premier) == \
        naming.normalize_identifier(second)
    abreges = {mire.abreger_la_mire(mire.nom_de_la_mire(PROJET, libelle),
                                    libelle, largeur)
               for libelle in (premier, second)}
    assert len(abreges) == 2, abreges


def test_un_nom_qui_TIENT_n_est_pas_touche():
    nom = mire.nom_de_la_mire(PROJET, "hp")
    assert mire.abreger_la_mire(nom, "hp", 76) == nom


def test_une_largeur_sous_la_QUEUE_rend_la_queue_ENTIERE():
    """Le volet symetrique de l'abregement : le refus de couper l'identite.

    Un nom tronque **dans** son condensat serait un nom FAUX, ce qui est pire
    qu'un nom trop long : le premier envoie chercher un fichier qui n'existe
    pas, le second deborde d'une colonne.
    """
    queue = mire.queue_du_nom(CHAINE)
    nom = mire.nom_de_la_mire(PROJET, CHAINE)
    assert mire.abreger_la_mire(nom, CHAINE, 5) == queue
    assert mire.abreger_la_mire(nom, CHAINE, 0) == ""


def test_un_libelle_que_le_coeur_REFUSE_de_nommer_ne_fait_pas_tomber_l_ecran():
    """Le repli : une chaine sans caractere alphanumerique ASCII.

    `build_calibration_pdf_filename` leve dessus, et il a raison. L'ecran de
    reglages doit s'ouvrir quand meme -- c'est le coeur qui refusera au moment
    d'ecrire, avec son message.
    """
    with pytest.raises(naming.NamingError):
        mire.nom_de_la_mire(PROJET, "---")
    ecran = mire.EcranMireReglages(PROJET, None, formulaire=_formulaire("---"))
    assert ecran.nom_du_fichier == ""
    assert mire.abreger_la_mire("n'importe quoi", "---", 8)


# ===========================================================================
# AC 8.8 -- le bandeau porte des MESURES, jamais un terme de conception
# ===========================================================================

@pytest.mark.parametrize("terme", ["parcours a part", "parcours à part",
                                   "palier", "feuille CLI",
                                   "point de jugement"])
def test_AUCUN_terme_de_nos_documents_de_decision_ne_s_affiche(terme):
    """`EPIC11-ARB-28`, AC 8.8. Mesure sur les chaines du **code**, docstrings
    exclus : les commentaires de ce module citent ces termes pour expliquer
    pourquoi ils n'y sont pas, et un grep de texte y mordrait."""
    exportes = set(mire.__all__)
    fautives = [chaine for chaine in chaines_de_code(MODULE)
                if terme.lower() in chaine.lower() and chaine not in exportes]
    assert not fautives, fautives
    # Le volet symetrique de l'exclusion : `__all__` porte bien des NOMS et non
    # du texte d'ecran, donc l'exclure ne blanchit rien d'affichable.
    assert all(hasattr(mire, nom) for nom in exportes)


def test_le_bandeau_porte_les_DEUX_temps_et_ils_se_comptent():
    """AC 8.8 : `temps 1 sur 2 · régler` puis `temps 2 sur 2 · écrire`.

    Deux mesures, et le cardinal des deux est le meme -- un « 1 sur 2 » suivi
    d'un « 2 sur 3 » dirait qu'un ecran a disparu en route.
    """
    assert mire.EcranMireReglages.objet == mire.TEMPS_DE_REGLAGE
    assert mire.EcranMireEnCours.objet == mire.TEMPS_D_ECRITURE
    assert mire.TEMPS_DE_REGLAGE.startswith("temps 1 sur 2")
    assert mire.TEMPS_D_ECRITURE.startswith("temps 2 sur 2")
    for ecran in (mire.EcranMireReglages, mire.EcranMireConfirmation,
                  mire.EcranMireEnCours, mire.EcranMireExiste,
                  mire.EcranMireEcrite):
        assert ecran.titre == mire.PALIER_DE_LA_MIRE, ecran.__name__


def test_la_confirmation_et_le_conflit_portent_le_temps_2(banc):
    """Les deux ecrans le recoivent a la construction, pas en attribut."""
    async def scenario(pilote):
        return pilote.app.screen.objet_du_bandeau()

    for ecran in (mire.EcranMireConfirmation(_formulaire(), PROJET),
                  mire.EcranMireExiste(_presente(), CHAINE)):
        assert _monte(_app(ecran), scenario, banc) == mire.TEMPS_D_ECRITURE


def test_le_RESULTAT_porte_un_bandeau_NU():
    """La maquette `E5-6e` n'a pas de segment droit : le travail est fini, il
    n'y a plus de temps a annoncer."""
    assert mire.EcranMireEcrite.objet == ""


# ===========================================================================
# AC 8.7 -- `E5-6b` est LE MEME ECRAN que `E5-3`
# ===========================================================================

def test_la_confirmation_EST_un_EcranChiffre_et_non_une_seconde_redaction():
    """AC 8.7 : « sans redaction neuve ».

    Egan l'a demande verbatim -- « conformement a la logique de tous les autres
    ecrans qui ecrivent quelque chose ». Une seconde redaction du point de
    jugement divergerait au premier reglage, et c'est la classe de defaut que la
    retrospective de l'Epic 7 instruit sous le nom de « defaut de couture ».
    """
    assert issubclass(mire.EcranMireConfirmation, EcranChiffre)
    assert issubclass(mire.EcranMireEcrite, EcranResultat)
    ecran = mire.EcranMireConfirmation(_formulaire(), PROJET)
    assert ecran.panneau.titre == mire.TITRE_A_ECRIRE
    assert isinstance(ecran.choix, ChoixExclusif)


def test_les_TROIS_issues_de_la_confirmation_sont_un_ensemble_EXACT():
    """AC 8.7. Un ensemble exact, jamais une inclusion : une quatrieme issue
    passerait inapercue a « `Générer` est proposee »."""
    choix = mire.choix_de_la_confirmation()
    assert [issue.cle for issue in choix.issues] == [
        mire.ISSUE_GENERER, mire.ISSUE_MODIFIER, mire.ISSUE_ANNULER]
    assert [issue.libelle for issue in choix.issues] == [
        mire.LIBELLE_GENERER, mire.LIBELLE_MODIFIER, mire.LIBELLE_ANNULER]
    ecrivent = {issue.cle for issue in choix.issues if issue.ecrit}
    assert ecrivent == {mire.ISSUE_GENERER}


def test_le_curseur_de_la_confirmation_ne_vise_JAMAIS_l_issue_qui_ecrit():
    """`EPIC11-ARB-7`, et il est **appele**, pas reecrit.

    La fleche de la maquette est sur `Modifier les réglages` : c'est ce que
    `ChoixExclusif.__post_init__` pose, sur la premiere issue qui n'ecrit pas.
    Poser le curseur ici en ferait une seconde redaction de l'invariant, qui
    pourrait diverger.
    """
    choix = mire.choix_de_la_confirmation()
    assert not choix.issues[choix.curseur].ecrit
    assert choix.issues[choix.curseur].cle == mire.ISSUE_MODIFIER
    assert choix.retenue is None
    # L'ordre de la LISTE ne bouge pas : c'est le curseur qui se place.
    assert choix.issues[0].cle == mire.ISSUE_GENERER


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_NOM_du_fichier_est_la_DERNIERE_chose_du_cartouche(ascii_seul, banc):
    """AC 8.7 : le meme ordre que `E5-3` -- ce qui sort, ou ca va, le nom.

    Et le nom y est abrege **par son slug** : un cartouche est plus etroit que
    la zone utile, donc c'est la que l'elision du condensat mordrait d'abord.
    """
    ecran = mire.EcranMireConfirmation(_formulaire(), PROJET)

    async def scenario(pilote):
        return pilote.app.screen.lignes_du_panneau()

    lignes = _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)
    libelle = (jetons.replier_ascii(mire.LIBELLE_NOM_DU_FICHIER)
               if ascii_seul else mire.LIBELLE_NOM_DU_FICHIER)
    assert lignes[-2] == libelle, lignes[-3:]
    assert naming.scan_chain_suffix(CHAINE) in lignes[-1]
    assert lignes[-1].endswith("_calibration.pdf")
    # La destination precede le nom, comme sur `E5-3`.
    rangs = [rang for rang, ligne in enumerate(lignes)
             if mire.LIBELLE_DESTINATION.split()[0][:6] in ligne]
    assert rangs and max(rangs) < len(lignes) - 2


def test_le_cartouche_de_confirmation_ne_porte_AUCUN_majorant():
    """Les trois absences : ni poids, ni duree, donc aucun majorant.

    `E5-3` porte `~ 470 Mo (majorant)` parce qu'un majorant de planches se
    calcule. Personne n'a pese une mire, et l'inventer serait « la valeur qui a
    l'air juste » -- la pire des deux erreurs possibles.
    """
    panneau = mire.panneau_de_la_confirmation(_formulaire(), PROJET)
    assert not panneau.porte_un_majorant
    from mixed_media_utility.tui.panneau import MENTION_MAJORANT
    assert MENTION_MAJORANT not in "\n".join(panneau.rendu())
    assert MENTION_MAJORANT not in "".join(chaines_de_code(MODULE))


def test_la_ligne_de_COMMENTAIRE_disparait_quand_le_champ_est_vide():
    """Les deux regimes : un `Commentaire` suivi de rien se lit comme une donnee
    perdue, alors que son absence est un cas nominal."""
    avec = mire.panneau_de_la_confirmation(_formulaire(), PROJET)
    sans = mire.panneau_de_la_confirmation(_formulaire(commentaire=""), PROJET)
    libelles = lambda p: [ligne.libelle for ligne in p.lignes]
    assert mire.LIBELLE_COMMENTAIRE in libelles(avec)
    assert mire.LIBELLE_COMMENTAIRE not in libelles(sans)
    assert len(sans.lignes) == len(avec.lignes) - 1


def test_Tab_n_est_ni_ANNONCE_ni_ACTIF_sur_la_confirmation(banc):
    """AC 6.3a : « une ligne de raccourcis propre, sans `Tab` ».

    Les deux moities de la meme promesse. `EcranChiffre` traite `tab` en entree
    d'edition des noms ; cet ecran n'en a **aucun** (le nom est derive, AC 8.3),
    donc la touche rend faux -- et la ligne ne l'annonce pas.
    """
    assert "Tab" not in mire.RACCOURCIS_MIRE_JUGEMENT
    ecran = mire.EcranMireConfirmation(_formulaire(), PROJET)

    async def scenario(pilote):
        return (pilote.app.screen.traiter("tab"),
                len(pilote.app.screen.noms))

    assert _monte(_app(ecran), scenario, banc) == (False, 0)


def test_la_ligne_d_etat_de_E5_6b_est_celle_du_MOTIF_PARTAGE(banc):
    """**Un ecart maquette / produit, epingle plutot que corrige.**

    La maquette porte `1 PDF · 1 page · 164 pastilles — rien n'a encore été
    écrit` ; `EcranChiffre.etat()` rend `panneau.RIEN_ECRIT` seul. `E5-3` porte
    le **meme** ecart, et le corriger d'un seul cote ferait diverger deux ecrans
    qu'Egan a demandes identiques. La correction appartient a `execution.py`,
    partage par les quatre ateliers, que ce lot n'a pas le droit de toucher.

    Ce test tient donc l'ecart **visible** : le jour ou la liaison de la vague
    corrige le motif partage, il rougit et le dit.
    """
    ecran = mire.EcranMireConfirmation(_formulaire(), PROJET)
    assert _etat(ecran, banc) == RIEN_ECRIT


# ===========================================================================
# AC 8.6 -- `E5-6c` : un ROTOR, aucune barre, aucun journal
# ===========================================================================

@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_ROTOR_tourne_et_rend_QUATRE_dessins_DISTINCTS(ascii_seul):
    """AC 8.6, la demande d'Egan validee : « **Bien** ».

    C'est le mutant central de ce lot -- un rotor qui cesse de tourner rend
    quatre fois le meme dessin, et **rien d'autre a l'ecran ne change**. Sans
    cette mesure, l'ecran serait indistinguable d'une TUI figee : c'est
    precisement le doute que le glyphe existe pour lever.

    Le repli ASCII rend lui aussi **quatre dessins distincts** : un repli qui en
    rendrait deux identiques detruirait le mouvement, qui est toute
    l'information que ce signe porte.
    """
    table = jetons.ROTOR_ASCII if ascii_seul else jetons.ROTOR
    ecran = mire.EcranMireEnCours("mire.pdf", CHAINE)
    vus = [ecran.glyphe_du_rotor(ascii_seul)]
    for _ in range(len(table) - 1):
        ecran.avancer_le_rotor()
        vus.append(ecran.glyphe_du_rotor(ascii_seul))
    assert vus == list(table)
    assert len(set(vus)) == len(table)


def test_le_rotor_ne_LEVE_jamais_au_quatrieme_tour():
    """Le modulo est fait par `jetons.rotor`, jamais par l'ecran.

    Un ecran qui compterait ses propres pas et oublierait le reste rendrait un
    `IndexError` apres quelques secondes d'execution reelle -- c'est-a-dire
    jamais dans un banc qui ne fait que quatre pas.
    """
    ecran = mire.EcranMireEnCours("mire.pdf", CHAINE)
    for _ in range(4 * len(jetons.ROTOR) + 3):
        ecran.avancer_le_rotor()
    assert ecran.pas == 4 * len(jetons.ROTOR) + 3
    assert ecran.glyphe_du_rotor(False) in jetons.ROTOR


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_rotor_est_DESSINE_et_change_a_l_ecran(ascii_seul, banc):
    """L'autre moitie : le glyphe calcule doit atteindre le widget.

    Un rotor qui tournerait dans le modele sans que l'ecran se redessine est le
    meme defaut, vu de l'autre bout -- et c'est exactement le mode de panne du
    finding `E9` : « un composant que rien ne cable est un composant que le
    produit n'a pas ».

    **Le minuteur est fige et le pas est PILOTE** (:func:`_figer_le_rotor`).
    C'est la difference entre mesurer le mecanisme et mesurer l'horloge : la
    premiere redaction de ce test laissait le minuteur tourner pendant les
    `await` du scenario, si bien que le glyphe dessine valait
    `rotor(pas + un nombre de tics inconnu)`. Il etait vert en isolation et
    rouge sous charge, sans qu'aucun code ne change -- et il se contredisait
    avec son voisin, qui exigeait l'immobilite du meme compteur.
    """
    table = jetons.ROTOR_ASCII if ascii_seul else jetons.ROTOR
    nom = mire.nom_de_la_mire(PROJET, CHAINE)

    def dessine(pas: int) -> str:
        ecran = mire.EcranMireEnCours(nom, CHAINE)
        lignes = _lignes(ecran, banc, ascii_seul,
                         avant=lambda e: [e.avancer_le_rotor()
                                          for _ in range(pas)])
        portantes = [ligne for ligne in lignes if "_calibration.pdf" in ligne]
        assert len(portantes) == 1, portantes
        return portantes[0].strip()[0]

    assert [dessine(pas) for pas in range(len(table))] == list(table)


def test_le_minuteur_du_rotor_est_TENU_et_s_arrete_au_demontage(banc):
    """La poignee sur le minuteur, mesuree des deux cotes.

    Un minuteur qu'on ne tient pas ne s'arrete pas : il continue d'appeler
    `avancer_le_rotor` sur un ecran demonte, donc de redessiner un arbre de
    widgets detruit. C'est le geste qu'`EcranExecution.on_unmount` fait deja en
    se desabonnant.

    Et c'est cette meme poignee qui rend le banc **independant de l'horloge** :
    sans elle, la seule facon de mesurer le rotor serait d'attendre.
    """
    ecran = mire.EcranMireEnCours("mire.pdf", CHAINE)
    assert ecran.minuteur is None, "aucun minuteur avant le montage"

    async def scenario(pilote):
        monte = pilote.app.screen.minuteur
        pilote.app.screen.on_unmount()
        return monte, pilote.app.screen.minuteur

    monte, apres = _monte(_app(ecran), scenario, banc)
    assert monte is not None, "le minuteur doit etre RETENU au montage"
    assert apres is None, "le minuteur doit etre arrete au demontage"


def test_l_ecran_de_generation_ne_porte_AUCUNE_barre_de_progression():
    """AC 8.6b, frontiere negative sur le **code** du module.

    Le motif n'est pas un gout : le canal de progression du coeur emet un jalon
    **par page** et une mire fait une page, donc la seule barre alimentable
    aurait deux etats. Le compte `130/164` de la v5 etait exactement le detail
    qu'Egan a exclu -- « un jalon par page mais **pas le detail du QR et des
    pastilles** ».

    La frontiere porte sur **ce fichier seul** et non sur `tui/atelier_pdf*.py` :
    le lot I de la meme story livre `E5-4`, dont la barre agregee est demandee
    par l'AC 9.1. Une frontiere posee sur le glob rougirait chez le voisin.
    """
    interdits = {"LARGEUR_BARRE", "Avancement", "SurfaceExecution",
                 "EcranExecution", "EmetteurProgression",
                 "EstimateurTempsRestant", "ligne_d_etat", "barre"}
    trouves = interdits & identifiants(MODULE)
    assert not trouves, trouves
    glyphes = {"barre-pleine", "barre-vide"}
    assert not glyphes & set(chaines_de_code(MODULE))


def test_la_frontiere_de_la_BARRE_mord_dans_l_autre_sens():
    """Le volet symetrique : ces noms existent, et ils sont a cote.

    Sans lui, une faute de frappe dans la liste des interdits rendrait le test
    precedent vert sur un module qui porterait une barre.
    """
    voisin = sys.modules["mixed_media_utility.tui.execution"]
    for nom in ("Avancement", "SurfaceExecution", "EcranExecution"):
        assert hasattr(voisin, nom), nom
    assert "LARGEUR_BARRE" in jetons.__dict__
    assert {"barre-pleine", "barre-vide"} <= set(jetons.GLYPHES)


@pytest.mark.parametrize("ascii_seul", MODES)
def test_AUCUN_compte_de_pastilles_n_est_DESSINE_pendant_la_generation(
        ascii_seul, banc):
    """AC 8.6b, le volet du rendu : le `130/164` de la v5 a disparu.

    On cherche la **forme** du compte -- deux cardinaux separes d'une barre --
    et non la chaine litterale : une barre reecrite `130 sur 164` serait le meme
    detail exclu.
    """
    donnees = mire.donnees_imposees()
    lignes = _lignes(mire.EcranMireEnCours(mire.nom_de_la_mire(PROJET, CHAINE),
                                           CHAINE), banc, ascii_seul)
    texte = "\n".join(lignes) + "\n" + _etat(
        mire.EcranMireEnCours("m.pdf", CHAINE), banc, ascii_seul)
    for forme in (f"{donnees.treillis}/{donnees.pastilles}",
                  f"{donnees.treillis} sur {donnees.pastilles}",
                  f"{donnees.treillis}/"):
        assert forme not in texte, forme
    # Le total, lui, reste : c'est une mesure de ce que la page CONTIENT, pas
    # un avancement. L'ecran serait muet sans elle.
    assert str(donnees.pastilles) in texte


def test_Tab_journal_n_est_NI_annonce_NI_actif_sur_E5_6c(banc):
    """Le retour d'Egan, mesure : « il n'y aura rien a voir cote journal ».

    Verifie sur le chemin de production : entre les deux `logger.info` de
    `makepdf_calibration_page_command`, **aucun** appel de journalisation
    n'existe. Le journal part donc, et `Tab journal` part avec lui --
    annoncer une touche inerte est le defaut du finding `I8`, paye quarante fois
    par ce depot.

    **Les trois moities de l'absence, et aucune ne regarde une horloge.**

    1. la touche n'est **pas annoncee** : la ligne de raccourcis ne la nomme
       pas ;
    2. le mecanisme n'existe **pas** : cet ecran ne porte ni journal, ni bascule
       de journal -- volet symetrique, `EcranResultat` et `EcranExecution` les
       portent tous les deux, donc la mesure cherche bien quelque chose qui
       existe ailleurs ;
    3. la touche n'est **pas liee** : la presser ne change ni l'ecran au sommet
       de la pile, ni le pas du rotor.

    Le point 3 mesurait auparavant le pas du rotor **sans figer le minuteur** :
    il prouvait donc « `Tab` n'agit pas » par un compteur qui bouge tout seul,
    et il contredisait le test du rotor a chaque fois que l'ordonnanceur leur
    donnait raison a tous les deux. Le minuteur est desormais arrete avant la
    frappe : ce qui reste mesure est bien la touche.
    """
    assert "Tab" not in mire.RACCOURCIS_MIRE_EN_COURS
    assert "journal" not in mire.RACCOURCIS_MIRE_EN_COURS.lower()
    for absent in ("basculer_le_journal", "journal", "journal_deplie",
                   "lignes_du_journal"):
        assert not hasattr(mire.EcranMireEnCours, absent), absent
    # Volet symetrique : le mecanisme cherche existe bel et bien a cote.
    assert hasattr(EcranResultat, "basculer_le_journal")
    ecran = mire.EcranMireEnCours("mire.pdf", CHAINE)

    async def scenario(pilote):
        _figer_le_rotor(pilote.app.screen)
        avant = pilote.app.screen.pas
        await pilote.press("tab")
        return (avant, pilote.app.screen.pas,
                type(pilote.app.screen).__name__)

    avant, apres, nom = _monte(_app(ecran), scenario, banc)
    assert nom == mire.EcranMireEnCours.__name__
    assert apres == avant


def test_le_MOT_journal_n_est_ecrit_NULLE_PART_dans_le_module():
    """La frontiere negative du journal, sur les chaines du **code**.

    Le docstring du module explique longuement pourquoi il n'y a pas de journal
    ici : un grep de texte y mordrait, l'AST non.
    """
    fautives = [chaine for chaine in chaines_de_code(MODULE)
                if "journal" in chaine.lower()]
    assert not fautives, fautives


@pytest.mark.parametrize("cable", [True, False])
def test_Echap_interrompre_n_est_JAMAIS_inerte(cable, banc):
    """Les **deux** regimes de la touche annoncee. Aucun n'est muet.

    Cable, elle appelle le rappel de l'atelier ; non cable, elle nomme ce qui
    manque et quand il arrive -- ce qui distingue « pas encore construit » de
    « casse ». C'est la seule facon de tenir la promesse de la ligne de
    raccourcis tant que `T6-1` n'est pas livre.
    """
    appels: list[int] = []
    ecran = mire.EcranMireEnCours(
        "mire.pdf", CHAINE,
        sur_interruption=(lambda: appels.append(1)) if cable else None)

    async def scenario(pilote):
        _figer_le_rotor(pilote.app.screen)
        await pilote.press("escape")
        await pilote.pause()
        return pilote.app.screen

    sommet = _monte(_app(ecran), scenario, banc)
    if cable:
        assert appels == [1]
        assert sommet is ecran
    else:
        assert isinstance(sommet, EcranPasEncore)
        assert appels == []


def test_Echap_ne_DEPILE_pas_l_ecran_de_generation(banc):
    """AC 4.1 du motif partage : pendant une execution, `Echap` cesse d'etre une
    remontee. Laisser l'application le voir ferait disparaitre la tache de la
    vue au lieu de demander quoi en faire."""
    ecran = mire.EcranMireEnCours("mire.pdf", CHAINE,
                                  sur_interruption=lambda: None)

    async def scenario(pilote):
        _figer_le_rotor(pilote.app.screen)
        avant = len(pilote.app.screen_stack)
        await pilote.press("escape")
        await pilote.pause()
        return avant, len(pilote.app.screen_stack)

    avant, apres = _monte(_app(ecran), scenario, banc)
    assert apres == avant


def test_la_ligne_d_etat_de_la_generation_ne_dit_QUE_ce_qui_est_su(banc):
    """AC 8.6c, `EPIC11-ARB-56` : un constat, aucune touche, aucun conseil."""
    donnees = mire.donnees_imposees()
    etat = _etat(mire.EcranMireEnCours("m.pdf", CHAINE), banc)
    assert etat == (f"{donnees.pages_lisibles} · {donnees.pastilles_lisibles}"
                    f" — {mire.ETAT_PAS_ENCORE_ECRITE}")
    for touche in ("Tab", "Échap", "F1", "⏎", "Entrée"):
        assert touche not in etat


def test_le_rotor_vit_HORS_de_la_table_des_glyphes_et_c_est_voulu():
    """`jetons.GLYPHES` nomme des ETATS et rend UN dessin par entree ; un rotor
    est un seul sens rendu par quatre. L'y verser casserait les deux proprietes
    que la table tient -- l'injectivite de son repli et l'egalite des deux
    tables."""
    assert set(jetons.GLYPHES) == set(jetons.GLYPHES_ASCII)
    assert not set(jetons.ROTOR) & set(jetons.GLYPHES.values())
    assert len(jetons.ROTOR) == len(jetons.ROTOR_ASCII)


# ===========================================================================
# AC 8.5 -- `E5-6d` : TROIS issues, et AUCUN rang
# ===========================================================================

def test_les_TROIS_issues_du_conflit_sont_un_ensemble_EXACT():
    """AC 8.5c, `EPIC11-ARB-89` : « jamais une, toujours au moins deux ».

    L'ordre compte autant que l'ensemble : la non destructive vient **en
    premier**, parce que c'est celle que l'arbitrage demande d'offrir d'abord.
    """
    choix = mire.choix_du_conflit()
    assert [issue.cle for issue in choix.issues] == [
        mire.ISSUE_AUTRE_CHAINE, mire.ISSUE_REMPLACER, mire.ISSUE_ANNULER]
    assert {issue.cle for issue in choix.issues if issue.ecrit} == {
        mire.ISSUE_REMPLACER}
    assert {issue.cle for issue in choix.issues if not issue.ecrit} == {
        mire.ISSUE_AUTRE_CHAINE, mire.ISSUE_ANNULER}


def test_le_curseur_du_conflit_part_sur_la_sortie_NON_DESTRUCTIVE():
    """AC 8.5b, `EPIC11-ARB-7` -- pose par `ChoixExclusif`, jamais reecrit ici.

    Et la cible est **au milieu** de la liste que le code parcourt : l'issue qui
    ecrit est la **deuxieme** des trois. Un curseur qui viserait `issues[0]`
    serait juste par accident si elle etait en tete, et un mutant qui prendrait
    la derniere le serait aussi si elle etait en queue.
    """
    choix = mire.choix_du_conflit()
    assert choix.issues[choix.curseur].cle == mire.ISSUE_AUTRE_CHAINE
    assert not choix.issues[choix.curseur].ecrit
    assert choix.retenue is None
    rang = [issue.cle for issue in choix.issues].index(mire.ISSUE_REMPLACER)
    assert rang == 1, "l'issue destructive doit rester AU MILIEU des trois"


def test_AUCUNE_issue_du_conflit_ne_propose_de_creer_une_VERSION():
    """AC 8.5a, la frontiere negative qui donne son sens a l'ecran.

    La mire ne declare ni rush, ni lot, ni cadence (`EPIC5-ARB-82`) : elle sert
    **toute une chaine de scan**, donc elle n'a pas de lot dont numeroter les
    tirages. Une issue « creer la version suivante » y promettrait un `_v2` que
    le coeur ne sait pas ecrire pour cet objet.

    La sortie non destructive est donc le **changement de nom de chaine** -- le
    libelle entre dans le nom, donc ca ecrit un fichier voisin et laisse
    l'existant intact.
    """
    choix = mire.choix_du_conflit()
    mots = ("version", "rang", "tirage", "_v", "suivante")
    for issue in choix.issues:
        minuscule = issue.libelle.lower()
        for mot in mots:
            assert mot not in minuscule, (issue.libelle, mot)
    # Et la sortie non destructive existe, nommee : sans ce volet, un ecran a
    # deux issues destructrices passerait la mesure ci-dessus.
    sortie = choix.sortie_sans_ecriture
    assert sortie is not None and sortie.cle == mire.ISSUE_AUTRE_CHAINE
    assert "chaîne" in sortie.libelle


def test_le_MODULE_ne_porte_AUCUN_mot_du_vocabulaire_des_RANGS():
    """AC 8.5a, la meme absence mesuree sur le code entier.

    Une issue propre ne suffirait pas : un rang calcule ailleurs dans le module
    et affiche dans un cartouche serait le meme defaut. Ni les identifiants ni
    les chaines du code ne portent le vocabulaire des rangs.
    """
    interdits = {"version_ranks", "version_rank", "RANG_ORIGINE",
                 "consommer_un_rang", "resolve_sheets_version_rank"}
    assert not interdits & identifiants(MODULE)
    for chaine in chaines_de_code(MODULE):
        assert "version_rank" not in chaine
        assert "_v2" not in chaine


def test_la_frontiere_du_VOCABULAIRE_des_rangs_mord_dans_l_autre_sens():
    """Le volet symetrique : ces noms existent bel et bien au coeur.

    `io/version_ranks.py` porte la regle des rangs, ecrite une fois pour les
    cinq objets versionnables (`EPIC11-ARB-108`). La mire n'en est pas un, et
    c'est ce que la frontiere precedente mesure -- encore faut-il que la chose
    cherchee existe.
    """
    from mixed_media_utility.io import version_ranks

    assert hasattr(version_ranks, "RANG_ORIGINE")
    voisins = identifiants(Path(version_ranks.__file__))
    assert "RANG_ORIGINE" in voisins


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_d_etat_du_conflit_DIT_l_absence_de_rang(ascii_seul, banc):
    """AC 8.5a : « la ligne d'etat le dit : `aucun rang pour cet objet` ».

    Une absence tue laisserait chercher le `_vN` que les tirages de planches
    portent -- et l'operateur conclurait que l'ecran a oublie de l'afficher.
    """
    presente = _presente()
    donnees = mire.donnees_imposees()
    etat = _etat(mire.EcranMireExiste(presente, CHAINE), banc, ascii_seul)
    assert mire.AUCUN_RANG in etat
    assert etat.startswith(jetons.glyphes(ascii_seul)["substitute"])
    assert str(donnees.pastilles) in etat
    assert presente.date in etat


@pytest.mark.parametrize("ascii_seul", MODES)
def test_les_DEUX_premieres_issues_du_conflit_portent_DEUX_mentions_distinctes(
        ascii_seul, banc):
    """AC 8.5 : la colonne de droite est ce qui les separe au moment du choix.

    **C'est la mesure d'appariement de ce lot** : `rendu_des_issues` balaie
    `choix.issues` en `zip` avec leur mention, et une permutation y rendrait
    « ecrit a cote, sans rien effacer » en face de `Remplacer cette mire`. Trois
    valeurs distinguables -- deux mentions differentes et une absente -- et la
    cible **au milieu** de la liste que le code parcourt.
    """
    ecran = mire.EcranMireExiste(_presente(), CHAINE)

    async def scenario(pilote):
        return pilote.app.screen.rendu_des_issues()

    lignes = _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)
    assert len(lignes) == 3
    attendu = (jetons.replier_ascii(mire.MENTION_AUTRE_CHAINE)
               if ascii_seul else mire.MENTION_AUTRE_CHAINE)
    assert attendu in lignes[0]
    assert attendu not in lignes[1]
    assert _presente().date in lignes[1]
    assert jetons.glyphes(ascii_seul)["substitute"] in lignes[1]
    # `Annuler` n'a pas de mention : une troisieme phrase y serait du bruit sur
    # la seule issue dont personne ne se demande ce qu'elle fait.
    assert lignes[2].strip() == (jetons.replier_ascii(mire.LIBELLE_ANNULER)
                                 if ascii_seul else mire.LIBELLE_ANNULER)


def test_les_mentions_sont_appariees_par_CLE_et_non_par_RANG(banc):
    """Le volet qui tue la permutation : la table est indexee par cle.

    Un appariement positionnel serait juste tant que l'ordre ne bouge pas, et
    faux au premier reordonnancement -- la classe de defaut `M33` / `M25`,
    trouvee trois fois par mutation et jamais par relecture.
    """
    ecran = mire.EcranMireExiste(_presente(), CHAINE)

    async def scenario(pilote):
        return pilote.app.screen.mentions_des_issues(False)

    mentions = _monte(_app(ecran), scenario, banc)
    assert set(mentions) == {mire.ISSUE_AUTRE_CHAINE, mire.ISSUE_REMPLACER}
    assert mentions[mire.ISSUE_AUTRE_CHAINE] == mire.MENTION_AUTRE_CHAINE
    assert _presente().date in mentions[mire.ISSUE_REMPLACER]
    assert mire.ISSUE_ANNULER not in mentions


def test_une_DATE_absente_fait_disparaitre_le_segment_au_lieu_de_l_inventer(banc):
    """Les deux volets. La date vient du **fichier**, mesuree sur le disque :
    aucun document du depot n'horodate une mire, et inventer un horodatage
    serait « la valeur qui a l'air juste »."""
    sans = _presente(quand=None)
    assert sans.horodatage == "" and sans.date == ""
    panneau = mire.panneau_du_conflit(sans)
    assert mire.LIBELLE_ECRIT_LE not in [ligne.libelle
                                         for ligne in panneau.lignes]
    etat = _etat(mire.EcranMireExiste(sans, CHAINE), banc)
    assert mire.AUCUN_RANG in etat
    assert " le " not in etat

    async def scenario(pilote):
        return pilote.app.screen.mentions_des_issues(False)

    mentions = _monte(_app(mire.EcranMireExiste(sans, CHAINE)), scenario, banc)
    assert mentions[mire.ISSUE_REMPLACER].endswith(
        mire.MENTION_REMPLACER_SANS_DATE)
    # Volet symetrique : avec une date, le segment revient.
    assert mire.LIBELLE_ECRIT_LE in [
        ligne.libelle for ligne in mire.panneau_du_conflit(_presente()).lignes]


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_cartouche_du_conflit_ouvre_sur_le_NOM_et_ferme_sur_le_PARAGRAPHE(
        ascii_seul, banc):
    """AC 8.5 : le nom est le sujet, le paragraphe dit ce qu'il ne porte pas.

    Le nom est abrege **par son slug** : c'est le fichier qu'on va peut-etre
    effacer, et un condensat mange le rendrait impossible a reconnaitre sur le
    disque -- au moment precis ou il faut etre sur de viser le bon.
    """
    ecran = mire.EcranMireExiste(_presente(), CHAINE)

    async def scenario(pilote):
        return pilote.app.screen.lignes_du_panneau()

    lignes = _monte(_app(ecran, ascii_seul=ascii_seul), scenario, banc)
    assert lignes[0].startswith(jetons.glyphes(ascii_seul)["substitute"])
    assert naming.scan_chain_suffix(CHAINE) in lignes[0]
    attendu = [jetons.replier_ascii(ligne) if ascii_seul else ligne
               for ligne in mire.PARAGRAPHE_DU_NOM]
    assert lignes[-len(attendu):] == attendu


def test_la_mire_PRESENTE_se_mesure_sur_le_DISQUE(tmp_path):
    """La mesure dont depend tout le parcours, dans ses deux regimes.

    Elle ne leve **jamais** : un dossier absent, un libelle irrecevable, un
    droit manquant rendent `None`. L'ecran de reglages doit s'ouvrir dans tous
    les cas -- c'est le coeur qui refuse au moment d'ecrire.
    """
    assert mire.mire_presente(tmp_path, PROJET, CHAINE) is None
    assert mire.mire_presente(tmp_path, PROJET, "---") is None
    assert mire.mire_presente(tmp_path / "absent", PROJET, CHAINE) is None
    chemin = mire.chemin_de_la_mire(tmp_path, PROJET, CHAINE)
    chemin.parent.mkdir(parents=True)
    chemin.write_bytes(b"%PDF-1.4\n")
    import os
    os.utime(chemin, (QUAND_DE_LA_MIRE, QUAND_DE_LA_MIRE))
    presente = mire.mire_presente(tmp_path, PROJET, CHAINE)
    assert presente is not None
    assert presente.chemin == chemin
    assert presente.date and presente.horodatage.startswith(presente.date)
    # Un DOSSIER du meme nom n'est pas une mire : `is_file` et non `exists`.
    autre = mire.chemin_de_la_mire(tmp_path, PROJET, "autre-chaine")
    autre.mkdir()
    assert mire.mire_presente(tmp_path, PROJET, "autre-chaine") is None


def test_la_ligne_d_etat_des_REGLAGES_dit_les_DEUX_regimes(tmp_path, banc):
    """La mesure apprise **avant** de generer plutot qu'apres.

    Dire seulement l'absence laisserait la presence muette, c'est-a-dire
    indistinguable d'un ecran qui n'a pas encore mesure.
    """
    donnees = mire.donnees_imposees()
    ecran = mire.EcranMireReglages(PROJET, tmp_path, formulaire=_formulaire())
    avant = _etat(ecran, banc)
    assert mire.ETAT_AUCUN_FICHIER.format(
        dossier=mire.DOSSIER_DE_LA_MIRE) in avant
    assert donnees.pages_lisibles in avant and donnees.pastilles_lisibles in avant
    chemin = mire.chemin_de_la_mire(tmp_path, PROJET, CHAINE)
    chemin.parent.mkdir(parents=True)
    chemin.write_bytes(b"%PDF-1.4\n")
    apres = _etat(mire.EcranMireReglages(PROJET, tmp_path,
                                         formulaire=_formulaire()), banc)
    assert mire.ETAT_FICHIER_PRESENT.format(
        dossier=mire.DOSSIER_DE_LA_MIRE) in apres
    assert avant != apres


# ===========================================================================
# AC 8.7 -- `E5-6e`, le resultat et ses suites CONTEXTUELLES
# ===========================================================================

def test_les_suites_du_resultat_sont_un_ensemble_EXACT():
    """AC 8.7 : trois suites contextuelles, plus le retour ajoute par la base.

    `EcranResultat` ajoute `Retour aux ateliers` en dernier de lui-meme
    (`EPIC11-ARB-13`) : l'ecrire ici le ferait voir deux fois. La cible
    contextuelle -- `Générer une autre mire` -- est **la deuxieme des trois**,
    ni la premiere ni la derniere de la liste que le code parcourt.
    """
    suites = mire.suites_du_resultat()
    assert suites == [mire.SUITE_DOSSIER, mire.SUITE_AUTRE_MIRE,
                      mire.SUITE_PLANCHES]
    assert mire.SUITE_AUTRE_MIRE == suites[1]
    assert EcranResultat.RETOUR not in suites
    ecran = mire.EcranMireEcrite(
        mire.panneau_du_resultat("m.pdf", CHAINE, PROJET), suites,
        sur_suite=lambda _: None)
    assert ecran.suites == suites + [EcranResultat.RETOUR]
    assert len(ecran.suites) == len(set(ecran.suites))


def test_le_cartouche_du_resultat_porte_les_chiffres_REELS_sans_majorant():
    """AC 8.7 : « le travail est fait, les chiffres sont mesures ».

    `EcranResultat` **leve** sur un panneau qui porterait un majorant : c'est
    l'invariant de la story 11.1, et il vaut ici comme ailleurs.
    """
    donnees = mire.donnees_imposees()
    panneau = mire.panneau_du_resultat("m.pdf", CHAINE, PROJET)
    assert not panneau.porte_un_majorant
    rendu = "\n".join(panneau.rendu())
    assert str(donnees.pastilles) in rendu
    assert str(donnees.treillis) in rendu
    assert CHAINE in rendu
    assert mire.destination_de_la_mire(PROJET) in rendu
    for ligne in mire.PROSE_DE_LA_MIRE:
        assert ligne in rendu


@pytest.mark.parametrize("ascii_seul", MODES)
def test_le_CONDENSAT_survit_aussi_au_cartouche_du_RESULTAT(ascii_seul):
    """AC 8.3, la ou l'elision mordrait d'abord.

    `LigneChiffree.rendu` abrege le libelle **au milieu** quand il deborde : sur
    un cartouche de 72 colonnes, un nom de 76 y perdrait son condensat. Le nom
    est donc pre-abrege par son slug, avec le budget que la ligne chiffree
    laissera au libelle.
    """
    longue = CHAINE + "-et-un-suffixe-qui-rallonge-encore-le-libelle"
    panneau = mire.panneau_du_resultat(
        naming.build_calibration_pdf_filename(PROJET, longue), longue, PROJET,
        ascii_seul=ascii_seul)
    rendu = panneau.rendu(jetons.LARGEUR_PLANCHER, ascii_seul)
    assert naming.scan_chain_suffix(longue) in rendu[0], rendu[0]
    assert "_calibration.pdf" in rendu[0]
    for ligne in rendu:
        assert jetons.colonnes(ligne) <= jetons.largeur_de_cartouche(
            jetons.LARGEUR_PLANCHER), ligne


def test_Tab_journal_n_est_annonce_QUE_lorsqu_un_journal_EXISTE(banc):
    """AC 8.7 : la ligne de raccourcis est **contextuelle**.

    Les deux regimes, et il faut les deux : sans journal, `Tab journal` serait
    une touche annoncee qui ne fait rien -- le finding `I8` ; avec journal, une
    absence d'annonce cacherait le seul endroit ou il se relit.

    **L'ecart que ce docstring epinglait est FERME** (`EPIC11-ARB-140`,
    2026-09-02) : la maquette annoncait `F1 aide` la ou
    `execution.RACCOURCIS_RESULTAT_AVEC_JOURNAL` annoncait `Q quitter`. Ce banc
    n'a pas bouge d'une ligne pour autant, et c'est voulu : il asserte **par
    reference** (`== RACCOURCIS_RESULTAT`), donc il SUIT la constante. Un banc
    qui aurait recopie la chaine aurait rougi ; c'est l'argument entier de la
    regle « on epingle par reference, on ne recopie pas ».
    """
    def ligne(journal):
        ecran = mire.EcranMireEcrite(
            mire.panneau_du_resultat("m.pdf", CHAINE, PROJET),
            mire.suites_du_resultat(), sur_suite=lambda _: None,
            journal=journal)
        return _raccourcis(ecran, banc)

    assert ligne(None) == RACCOURCIS_RESULTAT
    assert "Tab" not in RACCOURCIS_RESULTAT
    journal = Journal()
    journal.inscrire("Page de calibration ecrite")
    assert ligne(journal) == RACCOURCIS_RESULTAT_AVEC_JOURNAL
    assert "Tab" in RACCOURCIS_RESULTAT_AVEC_JOURNAL


@pytest.mark.parametrize("ascii_seul", MODES)
def test_la_ligne_d_etat_du_resultat_est_un_CONSTAT_chiffre(ascii_seul):
    donnees = mire.donnees_imposees()
    etat = mire.ligne_d_etat_du_resultat(donnees, ascii_seul)
    assert etat.startswith(jetons.glyphes(ascii_seul)["complete"])
    assert mire.AUCUN_REFUS in etat
    assert str(donnees.pastilles) in etat
    for touche in ("Tab", "Échap", "F1"):
        assert touche not in etat


# ===========================================================================
# Les points d'entree -- aucun rappel FACULTATIF (findings `K3` et `I8`)
# ===========================================================================

@pytest.mark.parametrize("ouvreur, requis", [
    (mire.ouvrir_les_reglages, "sur_continuer"),
    (mire.ouvrir_la_confirmation, "sur_issue"),
    (mire.ouvrir_la_generation, "sur_interruption"),
    (mire.ouvrir_le_conflit, "sur_issue"),
    (mire.ouvrir_le_resultat, "sur_suite"),
])
def test_le_rappel_de_chaque_point_d_entree_est_REQUIS(ouvreur, requis):
    """Findings `K3` et `I8`, en une mesure.

    Un `Callable | None = None` assorti d'un `if ... is not None` transforme
    l'oubli du cablage en **silence** : quatre suites navigables et decoratives
    d'un cote, `Tab journal` annonce et traite par personne de l'autre. Le
    rendre requis fait de l'oubli une **erreur d'appel**.
    """
    parametre = inspect.signature(ouvreur).parameters[requis]
    assert parametre.default is inspect.Parameter.empty, requis
    assert parametre.kind is inspect.Parameter.KEYWORD_ONLY, requis


def test_les_cinq_ecrans_sont_des_PASSAGES_et_non_des_stations():
    """`DESIGN.md` distingue les deux : un formulaire, une confirmation, une
    execution, un conflit et un resultat occupent la pile **sans etre des
    paliers** -- ils ne comptent pas dans le rang et ne restent pas sur le
    chemin du retour (`V2-M1`)."""
    for ecran in (mire.EcranMireReglages, mire.EcranMireConfirmation,
                  mire.EcranMireEnCours, mire.EcranMireExiste,
                  mire.EcranMireEcrite):
        assert ecran.TRANSITOIRE is True, ecran.__name__


def test_les_reglages_ne_CONTINUENT_pas_sans_chaine_et_ne_sont_pas_MUETS(banc):
    """`⏎` dans ses trois regimes : sans chaine, sans cablage, cable.

    Aucun n'est muet. Sans chaine, la touche est consommee et l'ecran se
    redessine -- le coeur refuse une page anonyme, et decouvrir ce refus deux
    ecrans plus loin serait pire.
    """
    appels: list[str] = []

    def ouvre(chaine, sur_continuer):
        ecran = mire.EcranMireReglages(PROJET, None,
                                       formulaire=_formulaire(chaine=chaine),
                                       sur_continuer=sur_continuer)

        async def scenario(pilote):
            await pilote.press("enter")
            await pilote.pause()
            return pilote.app.screen

        return ecran, _monte(_app(ecran), scenario, banc)

    ecran, sommet = ouvre("", lambda f: appels.append("x"))
    assert sommet is ecran and appels == []
    ecran, sommet = ouvre(CHAINE, None)
    assert isinstance(sommet, EcranPasEncore) and appels == []
    ecran, sommet = ouvre(CHAINE, lambda f: appels.append(f.saisie(
        mire.CHAMP_CHAINE)))
    assert sommet is ecran and appels == [CHAINE]


# ===========================================================================
# La grille et le repli -- 80x24, et rien qui deborde (AC 11, AC 12)
# ===========================================================================

def _tous_les_ecrans():
    """Les cinq ecrans, montables tels quels. Les rappels sont **cables** : un
    ecran monte sans cablage n'est pas celui que l'operateur verra."""
    return [
        mire.EcranMireReglages(PROJET, None, formulaire=_formulaire(),
                               sur_continuer=lambda _: None),
        mire.EcranMireConfirmation(_formulaire(), PROJET,
                                   sur_issue=lambda _: None),
        mire.EcranMireEnCours(mire.nom_de_la_mire(PROJET, CHAINE), CHAINE,
                              sur_interruption=lambda: None),
        mire.EcranMireExiste(_presente(), CHAINE, sur_issue=lambda _: None),
        mire.EcranMireEcrite(
            mire.panneau_du_resultat(mire.nom_de_la_mire(PROJET, CHAINE),
                                     CHAINE, PROJET),
            mire.suites_du_resultat(), sur_suite=lambda _: None),
    ]


@pytest.mark.parametrize("ascii_seul", MODES)
@pytest.mark.parametrize("rang", range(5))
def test_AUCUNE_ligne_ne_deborde_de_la_zone_utile_au_PLANCHER(rang, ascii_seul,
                                                              banc):
    """`EPIC11-ARB-21` : mesurer au plancher et non au-dessus est delibere.

    `textual` ne tronque pas une ligne trop longue, il la **replie** : une ligne
    de trop decale tout le bloc qui la suit, et sur une zone de hauteur 1 la fin
    part sur une ligne jamais dessinee.
    """
    lignes = _lignes(_tous_les_ecrans()[rang], banc, ascii_seul)
    trop_longues = [ligne for ligne in lignes
                    if jetons.colonnes(ligne) > UTILE]
    assert not trop_longues, trop_longues


@pytest.mark.parametrize("rang", range(5))
def test_le_repli_ASCII_ne_laisse_AUCUN_caractere_non_rendu(rang, banc):
    """Le repli doit rester **injectif de sens** : un `?` a l'ecran est un
    caractere que le terminal ne sait pas dessiner, donc une information
    perdue."""
    lignes = _lignes(_tous_les_ecrans()[rang], banc, True)
    texte = "\n".join(lignes)
    assert "?" not in texte, [l for l in lignes if "?" in l]
    assert texte.isascii(), [l for l in lignes if not l.isascii()]


@pytest.mark.parametrize("nom", ["RACCOURCIS_MIRE_REGLAGES",
                                 "RACCOURCIS_MIRE_JUGEMENT",
                                 "RACCOURCIS_MIRE_EN_COURS"])
@pytest.mark.parametrize("ascii_seul", MODES)
def test_chaque_ligne_de_RACCOURCIS_tient_dans_les_DEUX_regimes(nom, ascii_seul):
    """Le budget de colonnes, **mesure dans les deux regimes** : un repli ASCII
    peut ALLONGER une ligne (`⏎` rend `Entree`, cinq colonnes de plus)."""
    ligne = getattr(mire, nom)
    if ascii_seul:
        ligne = jetons.replier_ascii(ligne)
    assert jetons.colonnes(ligne) <= UTILE, (nom, jetons.colonnes(ligne))
    assert ligne.strip() == ligne


def test_le_module_n_importe_JAMAIS_cli():
    """La frontiere de la story 11.4b : la TUI n'invoque pas la ligne de
    commande, elle appelle le coeur."""
    noms = identifiants(MODULE)
    assert "cli" not in noms
    assert "mixed_media_utility.cli" not in noms
    for interdit in ("subprocess", "Popen", "os.system"):
        assert interdit not in noms


# ===========================================================================
# Finding `C2-2` (revue du 2026-09-02, couche 2) -- le libelle innommable
# ===========================================================================

#: Trois libelles que le coeur refuse de nommer, **distinguables** : des tirets,
#: de la ponctuation, un separateur de chemin. Un seul cas laisserait passer une
#: garde qui ne reconnaitrait que lui.
INNOMMABLES = ["---", "!!!", "/"]

#: Le volet symetrique : trois libelles que le coeur accepte, dont un qui ne
#: porte **qu'un seul** caractere alphanumerique -- c'est la frontiere exacte,
#: et une garde trop large le refuserait avec les autres.
NOMMABLES = [CHAINE, "a", "-x-"]


@pytest.mark.parametrize("libelle", INNOMMABLES)
def test_C2_2_un_libelle_que_le_COEUR_refuse_ne_passe_PAS_peut_continuer(
        libelle):
    """Finding `C2-2` -- `peut_continuer` ne mesurait que `bool(saisie)`.

    Un libelle non vide mais sans un seul caractere alphanumerique ASCII
    passait la garde, et le refus du coeur n'etait pas decouvert « deux ecrans
    plus loin » comme le docstring le promettait : il **traversait la boucle
    `textual`** au moment de generer, et l'application tombait.

    La garde interroge le coeur (`naming.normalize_identifier`) plutot que de
    reecrire sa regle : la recopier ferait une seconde redaction qui divergerait
    de celle qui refuse au moment d'ecrire.
    """
    formulaire = mire.FormulaireDeLaMire(chaine=libelle)
    assert formulaire.saisie(mire.CHAMP_CHAINE)      # non vide : c'est le piege
    assert mire.chaine_nommable(libelle) is False
    assert formulaire.peut_continuer is False
    # Et le coeur refuse bien ce libelle : la garde ne mesure pas autre chose
    # que ce que l'ecriture refusera.
    with pytest.raises(naming.NamingError):
        naming.build_calibration_pdf_filename(PROJET, libelle)


@pytest.mark.parametrize("libelle", NOMMABLES)
def test_C2_2_un_libelle_que_le_COEUR_accepte_passe_TOUJOURS(libelle):
    """Volet symetrique -- une garde qui refuserait tout serait verte ci-dessus.

    Le cas frontiere est `-x-` : un seul caractere alphanumerique, et le coeur
    l'accepte. Une garde ecrite « au jugé » (« pas que de la ponctuation »)
    aurait refuse un libelle que l'ecriture accepte, c'est-a-dire un blocage sec
    sur un objet innocent.
    """
    formulaire = mire.FormulaireDeLaMire(chaine=libelle)
    assert mire.chaine_nommable(libelle) is True
    assert formulaire.peut_continuer is True
    assert naming.build_calibration_pdf_filename(PROJET, libelle)


def test_C2_2_le_champ_VIDE_reste_refuse_pour_SON_motif_a_lui():
    """Les deux conditions se cassent separement, et la premiere existait deja.

    Sans cette mesure, une garde qui n'aurait garde que la seconde condition
    serait verte partout ailleurs : `chaine_nommable("")` est faux aussi, mais
    pour une autre raison, et la fermer par accident serait un vert qui ne
    mesure rien.
    """
    assert mire.FormulaireDeLaMire(chaine="").peut_continuer is False
    assert mire.FormulaireDeLaMire(chaine="   ").peut_continuer is False


def test_C2_2_la_ligne_d_etat_DIT_le_refus_au_lieu_de_mentir():
    """`EPIC11-ARB-89` : un refus **dit ce qui ne va pas**, il ne se tait pas.

    Avant, l'ecran affichait un nom de fichier vide (glyphe neutre, « non
    renseigne ») et une ligne d'etat qui repondait `aucun fichier de ce nom` --
    une reponse a une question qui n'a pas de sens, puisqu'aucun nom n'existe.
    Les trois regimes sont mesures : le refus **remplace** les deux autres, il
    ne s'y ajoute pas.
    """
    donnees = mire.donnees_imposees()
    refus = mire.ligne_d_etat_des_reglages(donnees, None, nommable=False)
    assert mire.ETAT_CHAINE_INUTILISABLE in refus
    assert mire.ETAT_AUCUN_FICHIER.format(
        dossier=mire.DOSSIER_DE_LA_MIRE) not in refus
    # Les deux regimes du fichier restent intacts.
    nominal = mire.ligne_d_etat_des_reglages(donnees, None)
    assert mire.ETAT_CHAINE_INUTILISABLE not in nominal
    assert mire.ETAT_AUCUN_FICHIER.format(
        dossier=mire.DOSSIER_DE_LA_MIRE) in nominal


@pytest.mark.parametrize("ascii_seul", MODES)
def test_C2_2_la_ligne_d_etat_du_refus_TIENT_le_budget_de_colonnes(ascii_seul):
    """Une ligne d'etat qui deborde se replie et decale tout ce qui suit.

    Mesuree dans les **deux** regimes : le repli ASCII peut allonger une ligne.
    """
    ligne = mire.ligne_d_etat_des_reglages(mire.donnees_imposees(), None,
                                           nommable=False)
    if ascii_seul:
        ligne = jetons.replier_ascii(ligne)
        assert ligne.isascii(), ligne
    assert jetons.colonnes(ligne) <= UTILE, jetons.colonnes(ligne)


# ===========================================================================
# Les quatre maquettes de la mire, LUES a leur source plutot que recopiees
# ===========================================================================
#
# **Le defaut que cette section ferme, et il etait mesure.** Ce banc citait
# `E5-6` a `E5-6e` par leur code, et n'ouvrait aucun des dessins : six de ses
# valeurs en etaient donc RECOPIEES. Un texte recopie a la main derive -- il
# coincide le jour ou il est ecrit et diverge sans qu'aucune etape n'echoue.
# Le geste juste se pratiquait deja dans le depot
# (`test_atelier_scan_rapport.py`), il ne se pratiquait pas ici.
#
# Ce qui est confronte n'est PAS un litteral de ce banc mais, quand il existe,
# la constante du MODULE : `mire.TEMPS_DE_REGLAGE` et `mire.TEMPS_D_ECRITURE`
# sont ce que l'ecran rend, et c'est cela qui doit etre dans le dessin.

#: Les maquettes, a leur source.
MAQUETTES = (Path(_SRC).parents[0] / "_bmad-output" / "planning-artifacts"
             / "ux-designs" / "ux-tui-2026-08-27" / "maquettes")

#: Le cadre d'un dessin separe des colonnes ; il ne fait pas partie du texte.
CADRE_DU_DESSIN = "─│┌┐└┘├┤┬┴┼━┃▏▕"

#: Ce qui suit est la prose de relecture, pas le dessin.
SEPARATEUR_DE_NOTE = "\nNOTE"


def dessin_de_la_maquette(nom: str) -> str:
    """Le corps du dessin, cadre retire et notes coupees, espaces replies."""
    brut = (MAQUETTES / nom).read_text(encoding="utf-8")
    brut = brut.split(SEPARATEUR_DE_NOTE)[0]
    return " ".join(
        "".join(" " if c in CADRE_DU_DESSIN else c for c in brut).split())


#: Les quatre dessins que ce banc citait sans les lire, et ce que chacun doit
#: porter. Des valeurs DISTINGUABLES d'un dessin a l'autre : `E5-6` est le
#: seul en temps 1, les trois autres en temps 2, et les deux premiers seuls
#: portent la chaine et le commentaire.
DESSINS_DE_LA_MIRE = [
    ("E5-6", "E5-6-pdf-calibration-page.txt",
     (PROJET, CHAINE, COMMENTAIRE, mire.TEMPS_DE_REGLAGE)),
    ("E5-6b", "E5-6b-pdf-calibration-confirmation.txt",
     (PROJET, CHAINE, COMMENTAIRE, mire.TEMPS_D_ECRITURE)),
    ("E5-6c", "E5-6c-pdf-calibration-execution.txt",
     (PROJET, mire.TEMPS_D_ECRITURE)),
    ("E5-6d", "E5-6d-pdf-calibration-existe.txt",
     (PROJET, mire.TEMPS_D_ECRITURE)),
]


@pytest.mark.parametrize(("code", "fichier", "attendus"), DESSINS_DE_LA_MIRE,
                         ids=[c for c, _, _ in DESSINS_DE_LA_MIRE])
def test_les_valeurs_de_la_mire_sont_VERBATIM_de_leur_maquette(
        code, fichier, attendus):
    """Chaque valeur est DANS le dessin, lu sur disque a ce tour-ci.

    Ce n'est pas une ressemblance, c'est une appartenance : le jour ou une
    maquette change, ce test rouge NOMME l'ecart (`EPIC11-ARB-144`) plutot
    que de le laisser filer.
    """
    dessin = dessin_de_la_maquette(fichier)
    for attendu in attendus:
        assert attendu in dessin, (code, attendu)


def test_le_TEMPS_distingue_bien_les_deux_dessins_et_ne_les_confond_pas():
    """Le volet symetrique, sans quoi la confrontation serait complaisante.

    Les deux temps sont des chaines proches (`temps 1 sur 2` / `temps 2 sur
    2`) : si l'un etait dans les quatre dessins, la table ci-dessus passerait
    en ne mesurant rien. Le seul dessin en temps 1 est `E5-6`, et il est le
    seul a ne PAS porter le temps 2.
    """
    en_temps_1 = {code for code, fichier, _ in DESSINS_DE_LA_MIRE
                  if mire.TEMPS_DE_REGLAGE in dessin_de_la_maquette(fichier)}
    en_temps_2 = {code for code, fichier, _ in DESSINS_DE_LA_MIRE
                  if mire.TEMPS_D_ECRITURE in dessin_de_la_maquette(fichier)}
    assert en_temps_1 == {"E5-6"}
    assert en_temps_2 == {"E5-6b", "E5-6c", "E5-6d"}
    assert en_temps_1 & en_temps_2 == set()


def test_la_confrontation_REFUSE_une_valeur_absente_du_dessin():
    """Et elle refuse ce qui n'y est pas -- une frontiere negative.

    Sans elle, une comparaison qui rendrait toujours vrai passerait les deux
    tests ci-dessus sans que personne ne le voie.
    """
    dessin = dessin_de_la_maquette("E5-6-pdf-calibration-page.txt")
    assert COMMENTAIRE in dessin
    assert "passe du 27/08, papier glace" not in dessin
    assert mire.TEMPS_D_ECRITURE not in dessin
    assert "projet_demonstration" not in dessin


# ===========================================================================
# `EPIC11-ARB-225` -- la mire se cherche dans LES DEUX racines
#
# « Une garde de repli fait VARIER le drapeau dont elle depend » (`CLAUDE.md`,
# 2026-09-06). Les bancs ci-dessus ne jouent que l'arborescence NEUVE, parce
# qu'ils composent leur chemin par `chemin_de_la_mire` -- ils suivraient donc
# n'importe quel repli, y compris un repli absent. Les trois etats sont joues
# ici, en ECRIVANT le nom du dossier plutot qu'en le derivant : une cible
# derivee du module mesure serait tautologique.
#
# Le mode de panne : une mire deja ecrite dans un projet ancien est declaree
# ABSENTE, l'ecran de conflit `E5-6d` ne s'intercale pas, l'ecran promet une
# generation -- et le coeur, qui resout les deux racines, refuse a l'ecriture.
# ===========================================================================

@pytest.mark.parametrize("dossiers,ou,etat", (
    (("patches",), "patches", "projet ANCIEN"),
    (("planches",), "planches", "projet NEUF"),
    (("planches", "patches"), "patches", "projet MIXTE, la mire sous l'ancien"),
    (("planches", "patches"), "planches", "projet MIXTE, la mire sous le neuf"),
))
def test_la_mire_est_RETROUVEE_dans_les_deux_racines(
        tmp_path, dossiers, ou, etat):
    """`mire_presente` voit la mire la ou elle est, dans les trois etats."""
    nom = mire.nom_de_la_mire(PROJET, CHAINE)
    for dossier in dossiers:
        (tmp_path / dossier).mkdir()
    (tmp_path / ou / nom).write_bytes(b"%PDF-1.4\n")

    presente = mire.mire_presente(tmp_path, PROJET, CHAINE)

    assert presente is not None, etat
    assert presente.chemin == tmp_path / ou / nom, etat
    assert mire.chemin_de_la_mire(tmp_path, PROJET, CHAINE) == (
        tmp_path / ou / nom), etat


def test_une_mire_ANCIENNE_n_est_pas_declaree_ABSENTE(tmp_path):
    """Le volet qui chiffre ce que la racine unique COUTAIT.

    Sans le repli, l'ecran de reglages d'un projet ancien annonce
    `ETAT_AUCUN_FICHIER` sur un projet qui porte deja sa mire : l'operateur
    croit generer un fichier neuf, et c'est le coeur qui l'arretera.
    """
    nom = mire.nom_de_la_mire(PROJET, CHAINE)
    (tmp_path / project_layout.LEGACY_PATCHES_DIRNAME).mkdir()
    (tmp_path / project_layout.LEGACY_PATCHES_DIRNAME / nom).write_bytes(b"%PDF-1.4\n")
    assert not (tmp_path / "planches").exists()

    assert mire.mire_presente(tmp_path, PROJET, CHAINE) is not None


def test_une_mire_d_un_AUTRE_nom_ne_repond_PAS_pour_celle_ci(tmp_path):
    """Volet symetrique : le repli resout un FICHIER, pas un dossier.

    Sans lui, les bancs ci-dessus seraient tenus par une resolution qui
    rendrait le dossier d'avant des qu'il existe -- et une mire NEUVE
    s'ecrirait eternellement sous le nom retire dans tout projet ancien.
    """
    (tmp_path / project_layout.LEGACY_PATCHES_DIRNAME).mkdir()
    (tmp_path / project_layout.LEGACY_PATCHES_DIRNAME
     / mire.nom_de_la_mire(PROJET, "autre-chaine")
     ).write_bytes(b"%PDF-1.4\n")

    assert mire.mire_presente(tmp_path, PROJET, CHAINE) is None
    assert mire.chemin_de_la_mire(tmp_path, PROJET, CHAINE) == (
        tmp_path / "planches" / mire.nom_de_la_mire(PROJET, CHAINE))
