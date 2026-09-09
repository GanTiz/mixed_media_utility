# -*- coding: utf-8 -*-
"""Story 11.1, AC 3 -- la progression consomme le canal du coeur, sans mentir."""

import re

import pytest

from mixed_media_utility.progression import EmetteurProgression
from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.avancement import (
    LIGNES_DE_JOURNAL,
    Avancement,
    Journal,
    barre,
    duree_lisible,
    pourcentage,
)
from mixed_media_utility.tui.execution import SurfaceExecution

#: Toute forme sous laquelle une duree pourrait se glisser dans la ligne
#: d'etat. `EPIC7-ARB-67` en interdit **toutes** tant qu'aucune mesure
#: n'existe : `0:00` et `--:--` mentent autant que « il reste 0 seconde ».
FORMES_DE_DUREE = re.compile(r"\breste\b|\d+\s*(s|min|h)\b|\d+:\d\d|--:--")


class Horloge:
    """Une horloge qu'on avance a la main. Le temps ne passe pas en test."""

    def __init__(self) -> None:
        self.instant = 1000.0

    def __call__(self) -> float:
        return self.instant

    def avancer(self, secondes: float) -> None:
        self.instant += secondes


def tache_temoin(jalons=(), leve_au_jalon=None, leve_a_la_fin=None):
    """La fabrique unique de la fiche : quatre comportements, un parametre.

    * emettre des jalons ;
    * n'en emettre aucun (`jalons=()`), pour l'AC 3.2 ;
    * lever depuis le RAPPEL -- c'est `leve_au_jalon`, une defaillance du canal ;
    * lever depuis le TRAVAIL -- c'est `leve_a_la_fin`, l'interdit symetrique.

    Les deux derniers doivent etre distincts : les confondre ferait passer un
    faux succes pour une absorption reussie.
    """
    def tache(emetteur: EmetteurProgression):
        for rang, faites in enumerate(jalons):
            if leve_au_jalon is not None and rang == leve_au_jalon:
                emetteur._rappel = _rappel_qui_leve
            emetteur.emettre(faites)
        if leve_a_la_fin is not None:
            raise RuntimeError(leve_a_la_fin)
        return "termine"
    return tache


def _rappel_qui_leve(faites, total):
    raise RuntimeError("le canal a laché")


# --------------------------------------------------------------------------
# La barre et le pourcentage
# --------------------------------------------------------------------------

@pytest.mark.parametrize("faites,total,pleins", [
    (0, 100, 0), (50, 100, 18), (100, 100, 36), (25, 100, 9)])
def test_la_barre_remplit_a_proportion_sur_une_largeur_fixe(faites, total, pleins):
    dessin = barre(faites, total)
    assert len(dessin) == jetons.LARGEUR_BARRE == 36
    assert dessin.count(jetons.GLYPHES["barre-pleine"]) == pleins


def test_la_barre_ne_deborde_pas_sur_un_compte_aberrant():
    """Le coeur borne deja `faites` a `total` ; la barre ne s'en remet pas a
    cette garde -- une barre de 40 colonnes casserait la grille."""
    assert len(barre(500, 100)) == jetons.LARGEUR_BARRE
    assert barre(500, 100) == jetons.GLYPHES["barre-pleine"] * 36
    assert barre(-5, 100) == jetons.GLYPHES["barre-vide"] * 36


def test_un_total_nul_rend_une_barre_vide_et_pas_une_division():
    assert barre(0, 0) == jetons.GLYPHES["barre-vide"] * 36
    assert pourcentage(0, 0) == ""


def test_la_barre_suit_le_repli_ascii():
    dessin = barre(50, 100, ascii_seul=True)
    assert dessin.isascii()
    assert dessin.count("#") == 18


@pytest.mark.parametrize("secondes,attendu", [
    (0.4, "1 s"), (1, "1 s"), (8, "8 s"), (59, "59 s"),
    (59.5, "1 min 00"), (60, "1 min 00"), (70, "1 min 10"),
    (95, "1 min 35"), (3599, "59 min 59"), (3600, "1 h 00"), (5400, "1 h 30")])
def test_une_duree_se_lit_en_clair(secondes, attendu):
    """La grammaire est celle du `DESIGN.md` section 8, pas la mienne.

    `X s` sous la minute, `M min SS` au-dessus, `H h MM` au-dessus de l'heure.
    Ecrire `1 min 10 s` ajoutait deux colonnes que le DESIGN n'ecrit pas, et
    c'est de la que venait le debordement de la ligne d'etat.

    `59.5` est la borne que l'arrondi ratait : arrondir APRES avoir choisi
    l'unite rendait « 60 s » sur toute la bande ]59, 60[.
    """
    assert duree_lisible(secondes) == attendu


def test_une_duree_infime_ne_s_arrondit_pas_a_zero():
    """Annoncer « 0 s » rendrait le meme mensonge qu'`EPIC7-ARB-67` interdit."""
    assert duree_lisible(0.01) == "1 s"
    assert duree_lisible(0) == "1 s"


# --------------------------------------------------------------------------
# AC 3.2 -- aucun temps tant qu'aucune mesure
# --------------------------------------------------------------------------

def test_sans_mesure_la_ligne_d_etat_ne_porte_aucune_forme_de_duree():
    ligne = Avancement("frames", faites=3, total=124).ligne_d_etat()
    assert FORMES_DE_DUREE.search(ligne) is None, ligne
    assert "3/124 frames" in ligne


def test_avec_mesure_la_ligne_d_etat_porte_la_duree():
    """Volet symetrique : sans lui, une ligne qui n'afficherait JAMAIS de duree
    passerait le test precedent."""
    ligne = Avancement("frames", faites=60, total=124,
                       temps_restant=64.0).ligne_d_etat()
    assert FORMES_DE_DUREE.search(ligne) is not None
    assert "reste ~ 1 min 04" in ligne


def test_la_surface_ne_publie_un_temps_qu_une_fois_la_mesure_faite():
    """AC 3.2 de bout en bout : premier jalon sans duree, jalons suivants avec.

    L'estimateur du coeur rend `None` tant qu'il n'a pas deux jalons espaces ;
    la surface le **lit**, elle ne calcule pas -- et n'a donc rien a inventer.
    """
    horloge = Horloge()
    surface = SurfaceExecution("frames", horloge=horloge)
    emetteur = surface.emetteur(124)

    emetteur.emettre(1)
    premiere = surface.avancement.ligne_d_etat()
    assert surface.avancement.temps_restant is None
    assert FORMES_DE_DUREE.search(premiere) is None, premiere

    for faites in (2, 3, 4):
        horloge.avancer(1.0)
        emetteur.emettre(faites)
    suivante = surface.avancement.ligne_d_etat()
    assert surface.avancement.temps_restant is not None
    assert FORMES_DE_DUREE.search(suivante) is not None, suivante


def test_l_unite_est_la_seconde_par_frame_et_jamais_son_inverse():
    """AC 3.3, `EPIC7-ARB-80`. La cadence du rush (25 im/s) et le rythme
    d'ecriture (1 frame toutes les 2 s) different exprès : une surface qui
    afficherait l'inverse rendrait 0,5 au lieu de 2, et le temps restant serait
    quatre fois trop court.
    """
    horloge = Horloge()
    surface = SurfaceExecution("frames", horloge=horloge)
    emetteur = surface.emetteur(100)
    emetteur.emettre(1)
    horloge.avancer(2.0)
    emetteur.emettre(2)
    assert surface.estimateur.secondes_par_frame == pytest.approx(2.0)
    # 98 frames restantes a 2 s la frame = 196 s, et non 49.
    assert surface.avancement.temps_restant == pytest.approx(196.0)


# --------------------------------------------------------------------------
# AC 3.4 -- l'observation ne casse pas l'observe, et l'inverse traverse
# --------------------------------------------------------------------------

def test_une_defaillance_du_canal_ne_fait_pas_echouer_la_tache():
    surface = SurfaceExecution("frames", horloge=Horloge())
    tache = tache_temoin(jalons=(1, 2, 3, 4), leve_au_jalon=2)
    assert surface.executer(tache, 4) == "termine"


def test_une_erreur_du_travail_observe_traverse_intacte_texte_compris():
    """Volet symetrique OBLIGATOIRE : sans lui, on echangerait un mensonge
    d'affichage contre un faux succes (`EPIC7-ARB-79`)."""
    surface = SurfaceExecution("frames", horloge=Horloge())
    tache = tache_temoin(jalons=(1, 2), leve_a_la_fin="frame 42 illisible")
    with pytest.raises(RuntimeError, match="frame 42 illisible"):
        surface.executer(tache, 2)
    # Et les jalons deja recus restent lisibles : l'echec n'efface pas ce qui
    # a ete constate avant lui.
    assert surface.avancement.faites == 2


def test_une_tache_qui_n_emet_aucun_jalon_laisse_la_surface_muette():
    surface = SurfaceExecution("frames", horloge=Horloge())
    assert surface.executer(tache_temoin(jalons=()), 10) == "termine"
    assert surface.avancement.faites == 0
    assert surface.avancement.temps_restant is None
    assert len(surface.journal) == 0


# --------------------------------------------------------------------------
# AC 3.5 -- deux niveaux : le detail REMPLACE le compte
# --------------------------------------------------------------------------

def test_le_detail_remplace_le_compte_simple_au_lieu_de_s_y_ajouter():
    """Contrainte de grille (`DESIGN.md` 8) : les deux ensemble ne tiennent pas
    dans les 76 colonnes utiles."""
    simple = Avancement("pages", faites=3, total=8).ligne_d_etat()
    detaille = Avancement("pages", faites=3, total=8,
                          detail="lot 2 sur 5 · page 3/8").ligne_d_etat()
    assert "3/8 pages" in simple
    assert "3/8 pages" not in detaille
    assert "lot 2 sur 5" in detaille
    assert len(detaille) <= jetons.largeur_utile(), detaille


def test_la_ligne_d_etat_tient_dans_la_largeur_utile_avec_une_duree():
    """Le cas le plus long : barre, pourcentage, detail ET duree."""
    ligne = Avancement("frames", faites=1234, total=6300,
                       detail="lot 2 sur 5 · frame 1234/6300",
                       temps_restant=5400).ligne_d_etat()
    assert len(ligne) <= jetons.largeur_utile(), (len(ligne), ligne)


# --------------------------------------------------------------------------
# Le journal
# --------------------------------------------------------------------------

def test_le_journal_garde_les_dernieres_lignes_et_pas_les_premieres():
    journal = Journal(plafond=3)
    for rang in range(10):
        journal.inscrire(f"ligne {rang}")
    assert journal.lignes == ["ligne 7", "ligne 8", "ligne 9"]


def test_le_journal_se_lit_de_la_plus_ancienne_a_la_plus_recente():
    journal = Journal()
    journal.inscrire("premiere")
    journal.inscrire("seconde")
    assert journal.lignes == ["premiere", "seconde"]
    assert journal.dernieres(1) == ["seconde"]


def test_le_journal_replie_ne_demande_rien_quand_on_ne_lui_montre_rien():
    journal = Journal()
    journal.inscrire("une ligne")
    assert journal.dernieres(0) == []


def test_le_plafond_par_defaut_est_celui_du_module():
    journal = Journal()
    for rang in range(LIGNES_DE_JOURNAL + 50):
        journal.inscrire(str(rang))
    assert len(journal) == LIGNES_DE_JOURNAL


# --------------------------------------------------------------------------
# La ligne d'etat ne deborde jamais, et sacrifie dans l'ordre annonce
# --------------------------------------------------------------------------

@pytest.mark.parametrize("detail,reste", [
    ("lot 2 sur 5 · frame 1234/6300", 5400),
    ("x" * 200, 5400),
    ("x" * 200, None),
    ("lot 2/2 · page 3/5", 8),
    (None, 70),
])
def test_la_ligne_d_etat_tient_toujours_dans_la_largeur_utile(detail, reste):
    """Cinq regimes, dont deux deraisonnables. `textual` ne tronque pas une
    ligne trop longue : il la REPLIE, et sur une zone de hauteur 1 la fin
    disparait sans bruit -- un temps restant perdu ainsi serait indistinguable
    d'un temps restant absent."""
    ligne = Avancement("frames", 1234, 6300, detail=detail,
                       temps_restant=reste).ligne_d_etat()
    assert len(ligne) <= jetons.largeur_utile(), (len(ligne), ligne)


def test_le_pourcentage_part_avant_le_detail():
    """Premier sacrifice : la barre dit deja le pourcentage, en dessin."""
    serre = Avancement("frames", 1234, 6300,
                       detail="lot 2 sur 5 · frame 1234/6300",
                       temps_restant=5400).ligne_d_etat()
    assert "%" not in serre
    assert "lot 2 sur 5" in serre


def test_le_temps_restant_survit_a_l_abregement_du_detail():
    """Troisieme regle : il est la seule information qu'on ne peut pas relire
    ailleurs, donc il n'est jamais sacrifie."""
    ligne = Avancement("frames", 1, 2, detail="y" * 200,
                       temps_restant=5400).ligne_d_etat()
    assert ligne.endswith("reste ~ 1 h 30")
    assert "…" in ligne


def test_la_barre_garde_sa_largeur_meme_quand_tout_deborde():
    ligne = Avancement("frames", 1, 2, detail="y" * 500,
                       temps_restant=5400).ligne_d_etat()
    dessin = ligne.split("  ")[0]
    assert len(dessin) == jetons.LARGEUR_BARRE


def test_l_abregement_reste_ascii_en_mode_ascii():
    ligne = Avancement("frames", 1, 2, detail="y" * 200,
                       temps_restant=5400).ligne_d_etat(ascii_seul=True)
    assert ligne.isascii(), ligne
    assert "..." in ligne


def test_une_ligne_courte_n_est_pas_touchee():
    """Volet symetrique : sans lui, un abregement applique toujours passerait
    tous les tests de largeur ci-dessus."""
    ligne = Avancement("frames", 84, 124, temps_restant=26).ligne_d_etat()
    assert "…" not in ligne
    assert "68 %" in ligne
    assert "84/124 frames" in ligne
    assert "reste ~ 26 s" in ligne


@pytest.mark.parametrize("avancement,attendue", [
    (Avancement("frames", 84, 124, temps_restant=70),
     "▓" * 24 + "░" * 12 + "  68 %  84/124 frames  reste ~ 1 min 10"),
    (Avancement("pages", 3, 8, detail="lot 2/2 · page 3/5", temps_restant=8),
     "▓" * 14 + "░" * 22 + "  38 %  lot 2/2 · page 3/5  reste ~ 8 s"),
])
def test_les_deux_exemples_du_design_sont_rendus_au_caractere_pres(
        avancement, attendue):
    """`DESIGN.md` section 8 est **la loi** : « une maquette qui la contredit
    est fausse, pas l'inverse ». Ses deux exemples sont recopies ici depuis le
    DESIGN, pas depuis le code, et font tous deux 75 colonnes sur 76 -- le
    DESIGN calcule lui-meme ce 75.

    **Correction d'une erreur que j'avais ecrite dans une fiche.** J'avais
    affirme que la maquette `E2-4` debordait et avait perdu le `s` de sa duree.
    C'etait faux, mesure par la couche 3 de la revue : la maquette est juste, et
    le debordement venait de `duree_lisible` qui ecrivait `1 min 10 s` la ou la
    grammaire du DESIGN ecrit `1 min 10`. Le pourcentage n'a jamais eu a etre
    sacrifie dans le regime nominal.
    """
    rendue = avancement.ligne_d_etat()
    assert rendue == attendue
    assert jetons.colonnes(rendue) == 75


# --------------------------------------------------------------------------
# Ce qui n'est pas fini ne s'affiche pas comme fini
# --------------------------------------------------------------------------

@pytest.mark.parametrize("faites,total", [(6299, 6300), (123, 124), (99, 100)])
def test_ni_la_barre_ni_le_pourcentage_n_annoncent_la_fin_avant_la_fin(faites, total):
    """**Deux champs disaient « termine » pendant que le troisieme disait le
    contraire.**

    `round` remplissait les 36 colonnes des 98,6 %, et `:.0f` ecrivait « 100 % »
    des 99,5 % -- donc sur les trente dernieres frames d'une extraction de
    6 300. C'est la contradiction que `EmetteurProgression` prend soin d'eviter
    cote coeur : « il n'est jamais force a `total` en fin de course [...]
    completer artificiellement a 100 % masquerait dans l'affichage exactement le
    defaut que cette garde existe pour lever » (risque R12, revue de vague 1,
    couche 2).
    """
    assert pourcentage(faites, total) != "100 %"
    assert jetons.GLYPHES["barre-vide"] in barre(faites, total)


@pytest.mark.parametrize("total", [1, 100, 6300])
def test_la_fin_s_affiche_bien_comme_la_fin(total):
    """Volet symetrique : une garde qui n'afficherait JAMAIS 100 % serait verte
    sur le test precedent et mentirait dans l'autre sens."""
    assert pourcentage(total, total) == "100 %"
    assert barre(total, total) == jetons.GLYPHES["barre-pleine"] * 36


def test_le_pourcentage_reste_celui_du_design_dans_le_regime_courant():
    """Le plafonnement ne doit pas deplacer l'arrondi : les deux exemples du
    DESIGN ecrivent 68 % et 38 %, pas 67 % et 37 %."""
    assert pourcentage(84, 124) == "68 %"
    assert pourcentage(3, 8) == "38 %"


def test_un_detail_vide_retombe_sur_le_compte_au_lieu_de_l_effacer():
    """Le contrat du champ est « il remplace le compte », pas « il peut le
    supprimer » : un detail vide laissait une ligne d'etat sans aucun compte."""
    vide = Avancement("frames", 84, 124, detail="").ligne_d_etat()
    absent = Avancement("frames", 84, 124, detail=None).ligne_d_etat()
    assert "84/124 frames" in vide
    assert vide == absent


def test_le_journal_deplie_suit_la_hauteur_reelle_de_la_fenetre(banc):
    """`DESIGN.md` section 1 : au-dela du plancher, la place gagnee va
    entierement a la zone centrale. Le compte de lignes etait calcule sur la
    constante du plancher : sur un terminal de 40 lignes, le journal deplie
    montrait 14 lignes dans une zone qui en offrait 33."""
    from mixed_media_utility.tui.coque import CoqueTui, PalierTemoin
    from mixed_media_utility.tui.execution import EcranExecution, SurfaceExecution

    surface = SurfaceExecution("frames")
    emetteur = surface.emetteur(500)
    for faites in range(1, 60):
        emetteur.emettre(faites)
    ecran = EcranExecution(surface, "Extraction")

    async def scenario(pilote):
        app = pilote.app
        app.descendre(ecran)
        await pilote.pause()
        replie = ecran.lignes_de_journal_visibles()
        await pilote.press("tab")
        await pilote.pause()
        return replie, ecran.lignes_de_journal_visibles()

    coque = CoqueTui(paliers=[PalierTemoin("Projet", "q"),
                              PalierTemoin("Ateliers", "q")])
    replie, deplie = banc(coque, scenario, taille=(80, 40))
    assert replie == 2
    assert deplie > jetons.HAUTEUR_CENTRE_AU_PLANCHER, (
        "au-dela du plancher, le journal deplie doit gagner des lignes")
    assert deplie == 40 - 2 - 2 - 3 - 3
