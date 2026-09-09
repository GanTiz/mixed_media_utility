# -*- coding: utf-8 -*-
"""Story 11.0, AC 3.2 et 3.3 -- les deux replis, et par quoi on les demande.

Reponse a la question 2 restee ouverte dans la fiche : **la convention plutot
que l'invention**. `NO_COLOR` existe et se respecte ; il n'existe aucune
convention d'environnement pour un repli ASCII, il n'en recoit donc pas une
inventee.
"""

import pytest

from mixed_media_utility.tui import jetons
from mixed_media_utility.tui.__main__ import analyser, diagnostic, main
from mixed_media_utility.tui.coque import CoqueTui, feuille


@pytest.fixture(autouse=True)
def sans_no_color(monkeypatch):
    """Chaque test part d'un environnement ou `NO_COLOR` n'est pas pose."""
    monkeypatch.delenv("NO_COLOR", raising=False)


def test_par_defaut_la_couleur_et_l_utf8_sont_actifs():
    options = analyser([])
    assert options.sans_couleur is False
    assert options.ascii_seul is False


def test_l_option_explicite_eteint_la_couleur():
    assert analyser(["--sans-couleur"]).sans_couleur is True


@pytest.mark.parametrize("valeur", ["", "1", "0", "false"])
def test_no_color_eteint_la_couleur_quelle_que_soit_sa_valeur(monkeypatch, valeur):
    """La convention veut que la SEULE presence de la variable compte.

    Les quatre valeurs comptent : un code qui lirait `NO_COLOR` comme un
    booleen laisserait la couleur allumee sur `0` et sur la chaine vide, qui
    sont justement les deux formes qu'on rencontre.
    """
    monkeypatch.setenv("NO_COLOR", valeur)
    assert analyser([]).sans_couleur is True


def test_no_color_ne_touche_pas_au_repli_ascii(monkeypatch):
    """Les deux replis sont independants : eteindre la couleur ne change pas
    les glyphes, et c'est le point de l'AC 3.2 (le glyphe reste le canal)."""
    monkeypatch.setenv("NO_COLOR", "1")
    options = analyser([])
    assert options.sans_couleur is True
    assert options.ascii_seul is False


def test_le_repli_ascii_n_a_pas_de_variable_d_environnement(monkeypatch):
    """Frontiere : aucune variable inventee ne l'active."""
    for invente in ("NO_UNICODE", "MMU_ASCII", "ASCII", "TERM_ASCII"):
        monkeypatch.setenv(invente, "1")
    assert analyser([]).ascii_seul is False
    assert analyser(["--ascii"]).ascii_seul is True


# --------------------------------------------------------------------------
# Ce que les deux modes changent reellement
# --------------------------------------------------------------------------

def test_la_feuille_sans_couleur_ne_declare_aucune_couleur():
    """AC 3.2 : plus une seule teinte, et la mise en page ne bouge pas."""
    eteinte = feuille(sans_couleur=True)
    assert "color:" not in eteinte
    for valeur in jetons.COULEURS.values():
        assert valeur not in eteinte
    # La structure survit : hauteurs, marges et cadre sont toujours la.
    for morceau in ("height:", "padding:", "border:", "border-bottom:",
                    "border-top:", "box-sizing:"):
        assert morceau in eteinte


def test_la_feuille_en_couleur_porte_les_jetons_et_seulement_eux():
    """Volet symetrique : sans lui, une feuille vide passerait le test ci-dessus."""
    allumee = feuille(sans_couleur=False)
    assert "color:" in allumee
    employes = {valeur for valeur in jetons.COULEURS.values() if valeur in allumee}
    # Le chrome emploie quatre des six jetons -- `accent` depuis que le nom
    # courant du cartouche le porte. Ce qui compte est qu'aucune AUTRE couleur
    # n'y soit, et qu'elles viennent toutes de la table.
    assert employes == {jetons.couleur("data"), jetons.couleur("muted"),
                        jetons.couleur("state-absent"), jetons.couleur("accent")}
    assert employes <= set(jetons.COULEURS.values())


@pytest.mark.parametrize("ascii_seul,table", [
    (False, jetons.GLYPHES), (True, jetons.GLYPHES_ASCII)])
def test_la_coque_sert_la_table_de_glyphes_du_mode_demande(ascii_seul, table):
    assert CoqueTui(ascii_seul=ascii_seul).glyphes is table


def test_les_deux_modes_se_combinent(banc):
    """Un terminal monochrome sans UTF-8 est un cas reel, pas une combinaison
    theorique : c'est la console d'une session SSH sur materiel ancien."""
    async def scenario(pilote):
        app = pilote.app
        return app.glyphes is jetons.GLYPHES_ASCII, "color:" not in app.CSS

    assert banc(CoqueTui(sans_couleur=True, ascii_seul=True), scenario) == (
        True, True)


def test_deux_coques_de_modes_differents_coexistent(banc):
    """La feuille est posee sur l'INSTANCE : deux applications montees dans le
    meme processus -- ce que fait la suite de tests -- ne se marchent pas
    dessus."""
    async def rendre_la_feuille(pilote):
        return pilote.app.CSS

    en_couleur = banc(CoqueTui(), rendre_la_feuille)
    eteinte = banc(CoqueTui(sans_couleur=True), rendre_la_feuille)
    assert "color:" in en_couleur
    assert "color:" not in eteinte


# --------------------------------------------------------------------------
# Le diagnostic de chemin, qui est la mesure du lanceur
# --------------------------------------------------------------------------

def test_le_diagnostic_dit_le_pythonpath_puis_les_chemins_vus(monkeypatch):
    """Le diagnostic rend TROIS rubriques, dans un ordre qui compte.

    `PYTHONPATH` d'abord, les chemins vus par l'interpreteur ensuite, et
    **`ESCDELAY` en dernier** (ajoute par la vague 1 bis). Ce dernier n'est
    pas decoratif : il est a la fois la latence de `Echap` et la fenetre
    pendant laquelle la touche suivante lui est collee, et il ne se mesure
    qu'en executant le lanceur -- pas en relisant son texte.

    L'ordre est assert parce que `test_lanceur.py` lit ces lignes par
    prefixe : une rubrique glissee au milieu des chemins passerait ici et
    ferait echouer la-bas pour une raison illisible.
    """
    monkeypatch.setenv("PYTHONPATH", "un/chemin/temoin")
    monkeypatch.setenv("ESCDELAY", "25")
    lignes = diagnostic().splitlines()
    assert lignes[0] == "PYTHONPATH=un/chemin/temoin"
    assert lignes[-1] == "ESCDELAY=25"
    assert len(lignes) > 2
    assert all(l.startswith("sys.path=") for l in lignes[1:-1])


def test_le_diagnostic_rend_un_escdelay_vide_plutot_que_de_mentir(monkeypatch):
    """Volet symetrique : sans reglage, la rubrique existe et elle est VIDE.

    Elle ne doit ni disparaitre -- `test_lanceur.py` leverait alors une
    erreur de rubrique manquante au lieu de dire ce qui ne va pas -- ni
    afficher le defaut de `textual`, que le diagnostic ne connait pas : il
    rend ce que l'ENVIRONNEMENT porte, et rien d'autre.
    """
    monkeypatch.delenv("ESCDELAY", raising=False)
    assert diagnostic().splitlines()[-1] == "ESCDELAY="


def test_le_diagnostic_sort_sans_monter_l_application(capsys):
    """Il rend 0 et n'ouvre aucun ecran : c'est ce qui le rend utilisable dans
    un test de lanceur, ou une application qui tourne bloquerait."""
    assert main(["--diagnostic-chemin"]) == 0
    assert capsys.readouterr().out.startswith("PYTHONPATH=")
