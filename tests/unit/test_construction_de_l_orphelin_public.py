# -*- coding: utf-8 -*-
"""Frontieres de `scripts/depot_public.py` -- le REGIME de publication.

CE QUE CE BANC FERME, ET IL A FAILLI SE PAYER
---------------------------------------------
`CLAUDE.md` porte depuis le 2026-09-08 la section « Le geste de publication
CHANGE a partir de la deuxieme version » : un orphelin pousse EN FORCE sur une
version deja taguee efface le commit que ce tag designe, et un tag qui pointe
dans le vide est pire qu'un historique absent. La section se terminait par
« le second reste a outiller ».

Ce n'etait pas une nuance de confort. Jusqu'au 2026-09-09, le recapitulatif de
`depot_public.py` ecrivait, quel que soit l'etat du depot public :

    git commit -q -m "mixed_media_utility 0.1.0"
    git remote add public https://github.com/GanTiz/mixed_media_utility.git
    git push public main

Trois defauts dans cinq lignes, et chacun mordait a une date differente :

* le SLUG en dur, alors que `scripts/public-repo.env` est la source unique de
  verite -- c'est-a-dire le defaut exact que ce fichier-la existe pour fermer ;
* la VERSION en dur (`0.1.0`), donc perimee des `v0.2.0`, et un recapitulatif
  perime DICTE UN TAG FAUX ;
* aucune lecture de l'etat du public. Un agent qui joue ce recapitulatif apres
  `v0.1.0` voit sa poussee refusee (non-avance-rapide) et ajoute `--force` --
  ce qui detruit le commit du tag.

La consigne existait, ecrite, et rien ne la mesurait : c'est litteralement le
motif de la section « Les politiques de ce fichier se MESURENT ».

CE QU'IL NE MESURE PAS, dit plutot que tu : il ne joue aucune poussee et ne
verifie donc pas que le geste de regime 2 aboutit sur GitHub. Il mesure ce que
le script DIT a l'operateur, qui est le seul endroit ou le defaut ci-dessus
s'introduisait.
"""

from __future__ import annotations

import io
import pathlib
import re
import subprocess
import sys
from contextlib import redirect_stdout

import pytest

RACINE = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "depot_public.py"

sys.path.insert(0, str(RACINE / "scripts"))
import depot_public as orphelin  # noqa: E402


# --------------------------------------------------------------------------
# Les trois regimes, et le fait que INJOIGNABLE n'est PAS zero
# --------------------------------------------------------------------------

def test_aucun_tag_publie_autorise_la_poussee_en_FORCE():
    assert orphelin.regime_de_publication(()) == orphelin.PREMIERE


@pytest.mark.parametrize("tags", [
    ("v0.1.0",),
    ("v0.1.0", "v0.2.0", "v0.10.0"),
    ("v9.9.9",),
])
def test_un_seul_tag_publie_SUFFIT_a_interdire_la_force(tags):
    assert orphelin.regime_de_publication(tags) == orphelin.SUIVANTE


def test_un_depot_INJOIGNABLE_n_est_pas_traite_comme_un_depot_SANS_TAG():
    """`None` et `()` sont deux verdicts differents, et c'est tout l'enjeu.

    Les confondre rendrait `premiere` -- donc `--force` -- au premier reseau
    coupe, c'est-a-dire exactement dans le conteneur neuf ou l'agent n'a aucun
    moyen de voir ce qu'il ecrase.
    """
    assert orphelin.regime_de_publication(None) == orphelin.INDETERMINE
    assert orphelin.regime_de_publication(None) != orphelin.PREMIERE


# --------------------------------------------------------------------------
# Ce que le script DIT, regime par regime
# --------------------------------------------------------------------------

def _dit(fonction, *args) -> str:
    tampon = io.StringIO()
    with redirect_stdout(tampon):
        fonction(*args)
    return tampon.getvalue()


def _geste_de_premiere() -> str:
    return _dit(orphelin._dit_le_geste_de_premiere,
                pathlib.Path("/tmp/orphelin"), "Proprio/depot", "1.2.3")


def _geste_de_suivante(tags=("v0.1.0",)) -> str:
    return _dit(orphelin._dit_le_geste_de_suivante,
                pathlib.Path("/tmp/orphelin"), "Proprio/depot", "1.2.3", tags)


def test_le_geste_de_PREMIERE_dit_bien_la_force():
    """Frontiere POSITIVE, et elle n'est pas decorative.

    Sans elle, la frontiere negative ci-dessous serait vraie d'un script qui
    ne proposerait JAMAIS de poussee en force -- y compris quand elle est
    l'unique geste correct. Une frontiere negative seule ne distingue pas
    « le defaut est ferme » de « la fonctionnalite a disparu ».
    """
    geste = _geste_de_premiere()
    assert "--force" in geste, geste


@pytest.mark.parametrize("forme", [r"--force", r"push\s+-f\b", r"\+refs/",
                                   r"--mirror"])
def test_le_geste_de_SUIVANTE_ne_propose_JAMAIS_d_ecraser(forme):
    """La frontiere qui protege le commit d'un tag deja publie."""
    geste = _geste_de_suivante()
    assert not re.search(forme, geste), (
        f"le geste de la deuxieme version propose `{forme}` :\n{geste}")


def test_le_geste_de_SUIVANTE_RETIRE_avant_de_recopier():
    """Un recouvrement laisserait les fichiers SUPPRIMES entre deux versions.

    C'est la classe de defaut qu'un historique neuf par version existe pour
    eviter, et elle ne se voit pas : le fichier mort reste servi par la
    distribution sans qu'aucune commande ne le dise.
    """
    geste = _geste_de_suivante()
    rang_du_retrait = geste.find("git rm")
    rang_de_la_recopie = geste.find("tar ")
    assert rang_du_retrait != -1, geste
    assert rang_de_la_recopie != -1, geste
    assert rang_du_retrait < rang_de_la_recopie, geste


def test_le_geste_de_SUIVANTE_ne_recopie_PAS_le_git_de_l_orphelin():
    geste = _geste_de_suivante()
    assert "--exclude=./.git" in geste, geste


@pytest.mark.parametrize("geste", ["premiere", "suivante"])
def test_CHAQUE_geste_tague_la_version_LUE_et_jamais_une_autre(geste):
    rendu = _geste_de_premiere() if geste == "premiere" else _geste_de_suivante()
    assert "git tag v1.2.3" in rendu, rendu
    assert "v0.1.0 &&" not in rendu, rendu


@pytest.mark.parametrize("geste", ["premiere", "suivante"])
def test_CHAQUE_geste_vise_le_SLUG_LU_et_jamais_un_autre(geste):
    rendu = _geste_de_premiere() if geste == "premiere" else _geste_de_suivante()
    assert "Proprio/depot" in rendu, rendu
    assert "GanTiz/" not in rendu, rendu


def test_un_depot_INJOIGNABLE_nomme_les_DEUX_gestes_et_ne_bloque_pas(monkeypatch,
                                                                     tmp_path):
    """« Jamais un blocage sec » vaut aussi pour l'outillage de publication."""
    monkeypatch.setattr(orphelin, "tags_du_public", lambda slug: None)
    monkeypatch.setattr(sys, "argv", ["depot_public.py", "--garder",
                                      str(tmp_path / "orphelin")])
    tampon = io.StringIO()
    with redirect_stdout(tampon):
        code = orphelin.principal()
    rendu = tampon.getvalue()
    assert code == 0
    assert "INJOIGNABLE" in rendu, rendu
    assert "REGIME 1" in rendu and "REGIME 2" in rendu, rendu


# --------------------------------------------------------------------------
# La lecture des tags : ce qu'elle retient et ce qu'elle jette
# --------------------------------------------------------------------------

class _RenduDeGit:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = ""


#: Regle des fabriques : plusieurs elements DISTINGUABLES, et une cible a
#: CHAQUE BORD -- le premier `v*` est en tete de listing, le dernier en queue.
#: Une cible au milieu demasque un tri fautif ; elle ne demasque pas un
#: balayage tronque, qui est un autre mode de panne.
_LISTING = "\n".join([
    "aaa1\trefs/tags/v0.1.0",
    "bbb2\trefs/tags/v0.1.0^{}",
    "ccc3\trefs/tags/jalon-interne",
    "ddd4\trefs/tags/v0.2.0",
    "eee5\trefs/tags/brouillon",
    "fff6\trefs/tags/v0.10.0",
])


def test_les_tags_de_VERSION_sont_retenus_aux_DEUX_BORDS_du_listing(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _RenduDeGit(_LISTING))
    tags = orphelin.tags_du_public("Proprio/depot")
    assert "v0.1.0" in tags, tags     # en TETE du listing
    assert "v0.10.0" in tags, tags    # en QUEUE du listing
    assert "v0.2.0" in tags, tags     # et au milieu


def test_les_references_PELEES_ne_comptent_pas_deux_fois(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _RenduDeGit(_LISTING))
    tags = orphelin.tags_du_public("Proprio/depot")
    assert sorted(tags) == ["v0.1.0", "v0.10.0", "v0.2.0"], tags


def test_un_tag_qui_n_est_pas_une_VERSION_ne_verrouille_pas_la_publication(
        monkeypatch):
    """Un jalon interne ne doit pas faire croire qu'une version est publiee."""
    listing = "aaa1\trefs/tags/jalon-interne\nbbb2\trefs/tags/brouillon"
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _RenduDeGit(listing))
    assert orphelin.tags_du_public("Proprio/depot") == ()
    assert orphelin.regime_de_publication(()) == orphelin.PREMIERE


def test_un_git_qui_ECHOUE_rend_INJOIGNABLE_et_pas_une_liste_vide(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: _RenduDeGit("", returncode=128))
    assert orphelin.tags_du_public("Proprio/depot") is None


# --------------------------------------------------------------------------
# Les deux sources uniques de verite, mesurees NEGATIVEMENT
# --------------------------------------------------------------------------

def test_le_SLUG_du_public_n_est_ecrit_NULLE_PART_dans_le_script():
    """Il se lit dans `scripts/public-repo.env`, comme le fait `ci.yml`.

    Frontiere negative : aucun test positif ne verrait revenir une seconde
    ecriture du slug, puisque le script continuerait de rendre la bonne valeur
    tant que les deux coincident -- c'est-a-dire jusqu'au prochain renommage,
    qui est exactement le moment ou la mesure servirait.
    """
    texte = SCRIPT.read_text(encoding="utf-8")
    slug = orphelin.slug_public()
    assert slug not in texte, (
        f"le slug `{slug}` est ecrit en dur dans {SCRIPT.name} ; il doit se "
        f"lire dans {orphelin.ENV_DU_DEPOT_PUBLIC}")


def test_la_VERSION_n_est_ecrite_NULLE_PART_dans_le_script():
    texte = SCRIPT.read_text(encoding="utf-8")
    version = orphelin.version_du_produit()
    lignes_fautives = [
        ligne for ligne in texte.splitlines()
        if version in ligne and "MODULE_DE_VERSION" not in ligne
        and not ligne.lstrip().startswith("#")
    ]
    assert not lignes_fautives, (
        f"la version `{version}` est ecrite en dur : {lignes_fautives}")


def test_les_deux_lecteurs_visent_des_fichiers_QUI_EXISTENT():
    assert (RACINE / orphelin.ENV_DU_DEPOT_PUBLIC).is_file()
    assert (RACINE / orphelin.MODULE_DE_VERSION).is_file()
