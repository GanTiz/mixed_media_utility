# -*- coding: utf-8 -*-
"""Le modele de la liste : tri, recherche, epingle, dernier ouvert
(story 7.1, AC 2 et AC 3).

**Regle des fabriques, appliquee partout ici** -- cette story est
entierement une story de collections, et c'est le defaut que ce depot a
paye trois fois (5.6, 5.7, 5.8) :

* la fabrique produit QUATRE projets aux valeurs toutes differentes -- nom,
  chemin, date de creation et date de modification varient ensemble, aucun
  remplissage uniforme : une permutation ne se voit que si les elements
  different ;
* aucune assertion ne se contente d'un cardinal : le tri, la recherche et
  l'epingle sont mesures sur les valeurs NOMINATIVES des lignes ;
* la cible est systematiquement ailleurs qu'en premiere position, y compris
  pour l'ordre alphabetique ET pour la date de creation -- un tri accidentel
  qui rendrait le bon resultat par hasard se demasque alors.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mixed_media_utility.gui.modele_projets import (
    CLES_DE_TRI,
    LigneProjet,
    ModeleProjets,
)

#: Quatre projets distinguables sur les QUATRE axes a la fois. Les ordres
#: par nom, par creation et par modification sont volontairement TOUS
#: differents entre eux : un modele qui appliquerait toujours la meme cle
#: passerait un jeu ou les trois ordres coincident.
#:
#: nom croissant           : Aurore, Brume, Crepuscule, Delta
#: creation croissante     : Delta, Crepuscule, Aurore, Brume
#: modification croissante : Brume, Delta, Aurore, Crepuscule
_JEU = (
    ("Aurore", "2026-03-10T08:00:00Z", 3000.0),
    ("Brume", "2026-05-02T08:00:00Z", 1000.0),
    ("Crepuscule", "2026-02-01T08:00:00Z", 4000.0),
    ("Delta", "2026-01-15T08:00:00Z", 2000.0),
)


def fabriquer_lignes(racine: Path):
    """Quatre lignes, chacune dans son propre dossier, valeurs distinctes."""
    return [
        LigneProjet(
            nom=nom,
            chemin=racine / f"dossier-{nom.lower()}",
            date_creation=creation,
            date_modification=modification,
        )
        for nom, creation, modification in _JEU
    ]


@pytest.fixture
def lignes(tmp_path):
    return fabriquer_lignes(tmp_path)


def _noms(modele):
    return [ligne.nom for ligne in modele.lignes()]


def test_la_fabrique_produit_des_elements_reellement_distinguables(lignes):
    """Garde-fou de la fabrique elle-meme : si ce test tombe, tous les
    suivants mesurent un remplissage uniforme et sont vides de sens."""
    assert len({ligne.nom for ligne in lignes}) == 4
    assert len({str(ligne.chemin) for ligne in lignes}) == 4
    assert len({ligne.date_creation for ligne in lignes}) == 4
    assert len({ligne.date_modification for ligne in lignes}) == 4


# ---------------------------------------------------------------------------
# AC 2 -- tri par les trois cles
# ---------------------------------------------------------------------------


def test_les_trois_cles_de_tri_sont_offertes():
    assert CLES_DE_TRI == ("nom", "creation", "modification")


def test_tri_par_nom(lignes):
    modele = ModeleProjets(lignes)

    modele.definir_tri("nom")
    assert _noms(modele) == ["Aurore", "Brume", "Crepuscule", "Delta"]

    modele.definir_tri("nom", croissant=False)
    assert _noms(modele) == ["Delta", "Crepuscule", "Brume", "Aurore"]


def test_tri_par_date_de_creation(lignes):
    modele = ModeleProjets(lignes)

    modele.definir_tri("creation")
    assert _noms(modele) == ["Delta", "Crepuscule", "Aurore", "Brume"]

    modele.definir_tri("creation", croissant=False)
    assert _noms(modele) == ["Brume", "Aurore", "Crepuscule", "Delta"]


def test_tri_par_date_de_modification(lignes):
    """L'ordre par modification differe de celui par nom ET de celui par
    creation : un modele qui ignorerait la cle demandee ne peut pas passer
    les trois tests a la fois."""
    modele = ModeleProjets(lignes)

    modele.definir_tri("modification")
    assert _noms(modele) == ["Brume", "Delta", "Aurore", "Crepuscule"]

    modele.definir_tri("modification", croissant=False)
    assert _noms(modele) == ["Crepuscule", "Aurore", "Delta", "Brume"]


def test_une_cle_de_tri_inconnue_est_refusee(lignes):
    modele = ModeleProjets(lignes)
    with pytest.raises(ValueError, match="Cle de tri inconnue"):
        modele.definir_tri("nombre-de-planches")


def test_une_date_manquante_va_en_fin_quel_que_soit_le_sens(tmp_path, lignes):
    """Une valeur manquante n'est ni petite ni grande.

    La ligne muette est placee en TROISIEME position dans la fabrique --
    pas en tete, pas en queue : une implementation qui la laisserait ou
    elle est passerait un jeu ou elle est deja au bon endroit.
    """
    muette = LigneProjet(
        nom="Bfff-sans-dates",
        chemin=tmp_path / "dossier-muet",
        date_creation=None,
        date_modification=None,
        motif="illisible",
    )
    melange = lignes[:2] + [muette] + lignes[2:]
    modele = ModeleProjets(melange)

    modele.definir_tri("creation")
    assert _noms(modele)[-1] == "Bfff-sans-dates"

    modele.definir_tri("creation", croissant=False)
    assert _noms(modele)[-1] == "Bfff-sans-dates"


# ---------------------------------------------------------------------------
# AC 2 -- recherche
# ---------------------------------------------------------------------------


def test_la_recherche_rend_la_ligne_visee_nominativement(lignes):
    """Le terme cherche est celui d'un projet qui n'est PAS le premier de
    la liste par ordre alphabetique -- sans quoi un filtre fautif qui
    rendrait toujours la premiere ligne passerait."""
    modele = ModeleProjets(lignes)
    modele.definir_tri("nom")

    modele.definir_recherche("crep")

    assert _noms(modele) == ["Crepuscule"]


def test_la_recherche_porte_aussi_sur_le_chemin(lignes):
    modele = ModeleProjets(lignes)

    modele.definir_recherche("dossier-delta")

    assert _noms(modele) == ["Delta"]


def test_la_recherche_ignore_la_casse_et_les_espaces_de_bordure(lignes):
    modele = ModeleProjets(lignes)

    modele.definir_recherche("  BRUME ")

    assert _noms(modele) == ["Brume"]


def test_une_recherche_vide_rend_toute_la_liste(lignes):
    modele = ModeleProjets(lignes)
    modele.definir_recherche("brume")
    assert len(modele.lignes()) == 1

    modele.definir_recherche("")

    assert len(modele.lignes()) == 4


# ---------------------------------------------------------------------------
# AC 2 -- l'epingle resiste au tri par date
# ---------------------------------------------------------------------------


def test_un_projet_epingle_resiste_au_tri_par_date_et_reste_en_tete(lignes):
    """`EPIC7-ARB-37`. La cible est « Brume », que le tri par modification
    DESCENDANT place en dernier : c'est le cas ou l'epingle doit se voir."""
    modele = ModeleProjets(lignes)
    modele.definir_tri("modification", croissant=False)
    assert _noms(modele)[-1] == "Brume", "precondition de la fixture"

    modele.basculer_epingle(lignes[1].chemin)  # Brume

    assert _noms(modele)[0] == "Brume"
    assert _noms(modele)[1:] == ["Crepuscule", "Aurore", "Delta"]


def test_desepingler_rend_le_projet_au_tri(lignes):
    modele = ModeleProjets(lignes)
    modele.definir_tri("modification", croissant=False)
    modele.basculer_epingle(lignes[1].chemin)
    assert _noms(modele)[0] == "Brume"

    modele.basculer_epingle(lignes[1].chemin)

    assert _noms(modele)[-1] == "Brume"


def test_deux_projets_epingles_restent_ordonnes_entre_eux_par_la_cle(lignes):
    """Volet symetrique : l'epingle deplace en tete, elle ne desordonne pas
    -- deux epingles gardent entre elles l'ordre de la cle courante."""
    modele = ModeleProjets(lignes)
    modele.definir_tri("nom")
    modele.basculer_epingle(lignes[3].chemin)  # Delta
    modele.basculer_epingle(lignes[2].chemin)  # Crepuscule

    assert _noms(modele) == ["Crepuscule", "Delta", "Aurore", "Brume"]


def test_l_etat_d_epingle_est_porte_par_la_ligne_et_persistable(lignes):
    modele = ModeleProjets(lignes)

    modele.basculer_epingle(lignes[2].chemin)

    vise = next(ligne for ligne in modele.lignes() if ligne.nom == "Crepuscule")
    assert vise.epingle is True
    assert all(
        ligne.epingle is False for ligne in modele.lignes() if ligne.nom != "Crepuscule"
    )
    assert modele.epingles() == (
        str(Path(lignes[2].chemin).expanduser().resolve()),
    )


# ---------------------------------------------------------------------------
# AC 3 -- dernier projet en tete
# ---------------------------------------------------------------------------


def test_le_dernier_ouvert_est_en_tete_sans_etre_premier_par_accident(lignes):
    """La cible est « Crepuscule » : ni premiere par ordre alphabetique
    (Aurore l'est), ni premiere par date de creation (Delta l'est). Un tri
    accidentel qui donnerait le bon resultat par hasard se demasque donc.
    """
    modele = ModeleProjets(lignes, dernier_ouvert=lignes[2].chemin)

    modele.definir_tri("nom")
    assert _noms(modele) == ["Crepuscule", "Aurore", "Brume", "Delta"]

    modele.definir_tri("creation")
    assert _noms(modele) == ["Crepuscule", "Delta", "Aurore", "Brume"]


def test_les_epingles_precedent_le_dernier_ouvert(lignes):
    """`EPIC7-ARB-61` : l'epingle passe devant le dernier ouvert.

    Les deux exigences disent « en tete » -- « dernier projet en tete »
    (`EXPERIENCE.md`) et « un projet epingle resiste au tri par date et
    reste en tete » (`EPIC7-ARB-37`) -- et **aucune source ne tranchait**
    laquelle prime : la revue de vague 2 a instruit les quatre (spine,
    `DESIGN.md`, ARB-37, `epics.md`) sans en trouver une seule qui le dise.
    Egan arbitre le 2026-08-25 : l'epingle d'abord, parce qu'epingler est un
    geste delibere quand « dernier ouvert » est un effet de bord du travail.

    Le test nomme les QUATRE positions, pas seulement la premiere : c'est ce
    qui le rend sensible a l'inversion des deux rangs -- une assertion sur
    la seule tete passerait encore si les epingles et le dernier ouvert
    echangeaient leurs places derriere elle.
    """
    modele = ModeleProjets(lignes, dernier_ouvert=lignes[2].chemin)  # Crepuscule
    modele.definir_tri("nom")
    modele.basculer_epingle(lignes[3].chemin)  # Delta

    assert _noms(modele) == ["Delta", "Crepuscule", "Aurore", "Brume"]


def test_un_projet_a_la_fois_epingle_et_dernier_ouvert_ne_parait_qu_une_fois(lignes):
    modele = ModeleProjets(lignes, dernier_ouvert=lignes[1].chemin)  # Brume
    modele.basculer_epingle(lignes[1].chemin)

    noms = _noms(modele)

    assert noms[0] == "Brume"
    assert noms.count("Brume") == 1


def test_est_dernier_ouvert_repond_sur_le_chemin_pas_sur_le_nom(lignes):
    modele = ModeleProjets(lignes, dernier_ouvert=lignes[2].chemin)

    assert modele.est_dernier_ouvert(lignes[2].chemin)
    assert not modele.est_dernier_ouvert(lignes[0].chemin)


# ---------------------------------------------------------------------------
# Alimentation : un dossier designe deux fois reste une seule ligne
# ---------------------------------------------------------------------------


def test_ajouter_le_meme_dossier_deux_fois_ne_fabrique_pas_de_doublon(lignes):
    """Le cas nominal de l'AC 5 : « ouvrir un dossier » puis « importer » le
    meme dossier. La cible est en SECONDE position -- une implementation qui
    ne comparerait qu'a la premiere ligne empilerait un doublon."""
    modele = ModeleProjets(lignes)
    remise = LigneProjet(
        nom="Brume",
        chemin=lignes[1].chemin,
        date_creation="2026-05-02T08:00:00Z",
        date_modification=9999.0,
    )

    modele.ajouter(remise)

    assert len(modele.lignes()) == 4
    vise = next(ligne for ligne in modele.lignes() if ligne.nom == "Brume")
    assert vise.date_modification == 9999.0


def test_ajouter_conserve_l_epingle_deja_posee_sur_ce_chemin(lignes):
    modele = ModeleProjets(lignes)
    modele.basculer_epingle(lignes[1].chemin)

    modele.ajouter(
        LigneProjet(nom="Brume", chemin=lignes[1].chemin, date_modification=42.0)
    )

    vise = next(ligne for ligne in modele.lignes() if ligne.nom == "Brume")
    assert vise.epingle is True


def test_les_chemins_connus_suivent_l_ordre_d_ajout_pas_le_tri(lignes):
    """La liste PERSISTEE est la liste connue, pas la vue du moment : elle
    ne doit pas se reordonner a chaque changement de tri."""
    modele = ModeleProjets(lignes)
    avant = modele.chemins()

    modele.definir_tri("modification", croissant=False)
    modele.definir_recherche("brume")

    assert modele.chemins() == avant
    assert len(avant) == 4


# ---------------------------------------------------------------------------
# Retirer de la liste (correctif du 2026-08-26)
# ---------------------------------------------------------------------------


def test_retirer_ote_LA_ligne_visee_et_pas_une_autre(lignes):
    """La cible est en TROISIEME position, et les trois autres restent.

    Un `retirer` qui oterait la premiere ligne, ou qui viderait la liste,
    passerait un test qui se contenterait d'un cardinal ou d'une cible en
    tete. Les noms sont donc mesures nommement.
    """
    modele = ModeleProjets(lignes)
    vise = next(ligne for ligne in lignes if ligne.nom == "Crepuscule")

    assert modele.retirer(vise.chemin) is True

    assert _noms(modele) == ["Aurore", "Brume", "Delta"]
    assert str(vise.chemin) not in modele.chemins()


def test_retirer_un_chemin_inconnu_ne_touche_a_rien_et_le_dit(lignes, tmp_path):
    modele = ModeleProjets(lignes)

    assert modele.retirer(tmp_path / "jamais-vu") is False
    assert len(modele.chemins()) == 4


def test_retirer_emporte_l_epingle_du_meme_chemin(lignes):
    """Sinon le projet revient EPINGLE au prochain import du meme dossier,
    et l'epingle resterait persistee sans qu'aucune ligne ne la montre."""
    modele = ModeleProjets(lignes)
    vise = next(ligne for ligne in lignes if ligne.nom == "Brume")
    # Deux epingles, pour que le retrait d'une seule se distingue d'un vidage.
    autre = next(ligne for ligne in lignes if ligne.nom == "Delta")
    modele.basculer_epingle(vise.chemin)
    modele.basculer_epingle(autre.chemin)

    modele.retirer(vise.chemin)

    assert modele.est_epingle(vise.chemin) is False
    assert modele.est_epingle(autre.chemin) is True
    assert modele.epingles() == (str(Path(autre.chemin).resolve()),)


def test_retirer_le_dernier_ouvert_libere_le_rang_de_tete(lignes):
    """Le rang de « dernier ouvert » se libere, il ne se transfere pas."""
    modele = ModeleProjets(lignes)
    vise = next(ligne for ligne in lignes if ligne.nom == "Crepuscule")
    modele.definir_dernier_ouvert(vise.chemin)

    modele.retirer(vise.chemin)

    assert modele.dernier_ouvert is None
    # Personne n'a herite du lisere.
    for ligne in modele.lignes():
        assert modele.est_dernier_ouvert(ligne.chemin) is False


def test_retirer_le_dernier_ouvert_ne_libere_PAS_le_rang_d_un_autre(lignes):
    """Volet symetrique : retirer une ligne quelconque laisse intact le rang
    de tete du dernier ouvert, qui n'est pas celle-la."""
    modele = ModeleProjets(lignes)
    dernier = next(ligne for ligne in lignes if ligne.nom == "Crepuscule")
    modele.definir_dernier_ouvert(dernier.chemin)

    modele.retirer(next(l for l in lignes if l.nom == "Aurore").chemin)

    assert modele.est_dernier_ouvert(dernier.chemin) is True
    assert _noms(modele)[0] == "Crepuscule"


def test_retirer_reconnait_le_meme_dossier_designe_autrement(lignes):
    """Meme normalisation que le reste du modele : une barre finale ou un
    detour par `..` designent la meme ligne."""
    modele = ModeleProjets(lignes)
    vise = next(ligne for ligne in lignes if ligne.nom == "Delta")
    detour = Path(vise.chemin).parent / "." / Path(vise.chemin).name

    assert modele.retirer(detour) is True
    assert "Delta" not in _noms(modele)
