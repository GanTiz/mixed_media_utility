"""Completion manuelle d'un lot absent du manifeste -- `EPIC11-ARB-106`.

Egan, 2026-08-31, en relisant la planche du Scan : « si le lot n'est pas au
manifeste il faut rentrer tous les champs manuellement ».

**Le trou que cela ferme.** `payload_depuis_l_identite` exige un modele -- les
huit champs neutres du lot --, et le depot n'avait que DEUX sources : une autre
planche lue de la meme pile, ou le manifeste du projet. Quand les deux
manquent (manifeste perdu, projet reconstruit, pile d'une seule planche
muette), le refus etait juste mais n'offrait RIEN. Un blocage sec, d'autant
plus dur que la feuille, elle, PORTE l'information.

**Ce que ce mecanisme ne fait pas, et c'est l'essentiel** : il ne devine rien.
Deviner une cadence est l'interdit central d'`EPIC6-ARB-6`, et le tort qu'il
decrit -- « des TIFF d'apparence valide au mauvais timecode » -- ne devient pas
acceptable parce que c'est un humain qui a laisse le champ vide.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mixed_media_utility import scan_corrections, scan_write


def _saisie_complete(**ecrase):
    valeurs = {
        "project_id": "demo",
        "rush_id": "rush-001",
        "fps_target": 24.0,
        "timecode_base_fps": "25/1",
        "patch_preset_id": "patches-17-v4",
        "target_colorspace": "bt709",
        "gamut_map_id": "gamut-map-none-1",
        "page_count": 5,
    }
    valeurs.update(ecrase)
    return valeurs


def test_une_saisie_COMPLETE_produit_un_modele():
    modele = scan_corrections.modele_saisi(_saisie_complete(lot_id="rush-001_24"))
    for champ in scan_corrections.CHAMPS_NEUTRES_DU_LOT:
        assert champ in modele, f"le modele saisi ne porte pas {champ}"
    assert modele["lot_id"] == "rush-001_24"


@pytest.mark.parametrize("manquant", scan_corrections.CHAMPS_NEUTRES_DU_LOT)
def test_CHAQUE_champ_manquant_est_refuse_NOMMEMENT(manquant):
    """Les huit, un par un. Un seul champ non teste laisserait passer le
    defaut exact que ce refus existe pour empecher -- et c'est
    `fps_target` qui le porte le plus lourdement (`EPIC6-ARB-6`)."""
    valeurs = _saisie_complete()
    del valeurs[manquant]
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.modele_saisi(valeurs)
    assert manquant in str(refus.value), (
        "le refus ne NOMME pas le champ manquant: l'operateur ne sait pas quoi "
        "corriger"
    )


@pytest.mark.parametrize("valeur_vide", ["", None, 0])
def test_un_champ_VIDE_vaut_un_champ_manquant(valeur_vide):
    """Une chaine vide n'est pas une saisie : c'est un formulaire non rempli.
    L'accepter ferait construire un payload d'apparence valide."""
    with pytest.raises(scan_corrections.IdentiteIncompletable):
        scan_corrections.modele_saisi(_saisie_complete(fps_target=valeur_vide))


def test_le_refus_DIT_ou_lire_les_valeurs_sur_la_planche():
    """Un refus qui n'aide pas est un refus a moitie. Les huit champs sont
    atteignables a l'oeil : le pied technique en porte cinq, le bloc
    d'identite le projet et le rush, l'en-tete la cadence."""
    valeurs = _saisie_complete()
    del valeurs["fps_target"]
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_corrections.modele_saisi(valeurs)
    texte = str(refus.value)
    assert "pied technique" in texte and "en-tete" in texte


def test_le_modele_saisi_ne_laisse_passer_AUCUN_champ_de_plus():
    """Y laisser entrer un champ arbitraire ferait passer par cette porte une
    valeur qui ne vient d'aucune planche."""
    modele = scan_corrections.modele_saisi(
        _saisie_complete(lot_id="L", CHAMP_PIRATE="x", page_index=99))
    assert "CHAMP_PIRATE" not in modele and "page_index" not in modele


@pytest.mark.parametrize("pas_un_dict", [None, "texte", 42, []])
def test_une_saisie_qui_n_est_pas_un_dictionnaire_est_refusee(pas_un_dict):
    with pytest.raises(scan_corrections.IdentiteIncompletable):
        scan_corrections.modele_saisi(pas_un_dict)


# ---------------------------------------------------------------------------
# L'ORDRE DES SOURCES, et il compte.
# ---------------------------------------------------------------------------


def test_une_planche_LUE_du_meme_lot_PRIME_sur_la_saisie():
    """La saisie vient en DERNIER. Une planche lue de la meme pile est
    toujours plus sure qu'une retranscription a la main, et lui preferer la
    saisie ferait entrer une faute de frappe la ou la machine avait la valeur
    exacte."""
    lu = {"lot_id": "L_24", "fps_target": 24.0, "rush_id": "LU"}
    modele = scan_write._modele_de_completion(
        [lu], "L_24", saisie=_saisie_complete(rush_id="SAISI"))
    assert modele["rush_id"] == "LU", "la saisie a pris le pas sur une planche lue"


def test_la_saisie_sert_quand_AUCUNE_planche_du_lot_n_est_lue():
    """Regle des fabriques : la pile porte deux payloads d'AUTRES lots,
    distinguables -- un appariement fautif qui rendrait le premier venu
    completerait la planche avec la cadence d'un autre lot, sans un mot."""
    autres = [{"lot_id": "AUTRE_12", "rush_id": "A"},
              {"lot_id": "ENCORE_5", "rush_id": "B"}]
    modele = scan_write._modele_de_completion(
        autres, "L_24", saisie=_saisie_complete(rush_id="SAISI"))
    assert modele["rush_id"] == "SAISI"
    assert modele["lot_id"] == "L_24"


def test_sans_planche_lue_NI_saisie_le_refus_offre_DEUX_issues():
    """`EPIC11-ARB-89`. Le refus d'origine n'en offrait qu'une -- rescanner
    avec une planche lisible -- et restait muet sur la saisie, qui est
    pourtant possible puisque la feuille porte tout."""
    with pytest.raises(scan_corrections.IdentiteIncompletable) as refus:
        scan_write._modele_de_completion([], "L_24")
    texte = str(refus.value)
    assert "DEUX issues" in texte
    assert "a la main" in texte
    # Et le refus de deviner est REAFFIRME, pour qu'une saisie partielle ne
    # paraisse pas une porte de sortie.
    assert "incomplete est refusee" in texte


# ---------------------------------------------------------------------------
# `EPIC11-ARB-106` -- la troisieme source est JOIGNABLE depuis un appelant reel.
#
# Trouve en revue (couches 2 et 3) : `_modele_de_completion` acceptait `saisie`
# depuis son ecriture, mais son unique appelant de production ne la passait pas
# et aucun parametre ne la transportait. Le refus annoncait « ou fournir ces
# valeurs a la main », une issue qu'aucun chemin ne savait executer -- le code
# neuf etait atteint a 100 % et utilise a 0 %.
#
# Ces tests-ci portent sur la SIGNATURE publique du coeur, la ou les autres
# appellent le helper prive : c'est le seul niveau ou le defaut se voyait.
# ---------------------------------------------------------------------------


def test_le_coeur_EXPOSE_un_canal_pour_la_saisie():
    """Sans ce parametre, la seconde issue du refus reste inatteignable."""
    import inspect

    from mixed_media_utility import scan_write

    for fonction in (scan_write.ecrire_le_lot_detecte,
                     scan_write.consommer_les_corrections_manuelles):
        parametres = inspect.signature(fonction).parameters
        assert "saisie_du_lot" in parametres, (
            f"{fonction.__name__} ne peut pas transporter la saisie: la "
            "deuxieme issue annoncee par le refus de `_modele_de_completion` "
            "n'est joignable par aucun appelant."
        )
        assert parametres["saisie_du_lot"].default is None, (
            "la saisie doit etre facultative: `None` ne change rien, qui est "
            "le regime de tous les appelants d'aujourd'hui."
        )


def test_la_saisie_TRAVERSE_reellement_jusqu_au_modele():
    """Un parametre qui existe mais n'arrive pas serait la meme fuite.

    Le test precedent verifie la SIGNATURE ; celui-ci verifie le TRANSPORT --
    sans quoi ajouter le parametre et oublier de le passer donnerait un banc
    vert pour un canal toujours coupe. C'est exactement la forme du defaut
    trouve en revue : le helper acceptait `saisie` depuis son ecriture, et
    personne ne la lui passait.

    La mesure est STRUCTURELLE (AST) et non comportementale : construire un
    document de detection complet demanderait un scan reel, et un test qui
    ferait semblant mesurerait la fixture plutot que le transport. Le depot
    tient deja une frontiere de cette forme pour les bornes du payload.
    """
    import ast

    source = (Path(__file__).resolve().parents[2] / "src" / "mixed_media_utility"
              / "scan_write.py").read_text(encoding="utf-8")
    appels = [
        noeud for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Name)
        and noeud.func.id == "_modele_de_completion"
    ]
    assert appels, "aucun appel a `_modele_de_completion` : la frontiere ne lit rien."
    for appel in appels:
        noms = {mot.arg for mot in appel.keywords}
        assert "saisie" in noms, (
            "un appel a `_modele_de_completion` ne passe pas `saisie=`: la "
            "troisieme source reste inatteignable depuis la production, et le "
            "refus continue de nommer une issue qui n'existe pas."
        )
        # Et la valeur passee vient bien du parametre de bout de chaine, pas
        # d'un litteral qui neutraliserait le canal.
        valeur = next(m.value for m in appel.keywords if m.arg == "saisie")
        assert isinstance(valeur, ast.Name) and valeur.id == "saisie_du_lot", (
            "`saisie=` doit recevoir le parametre `saisie_du_lot`, pas une "
            "constante -- sinon le canal est declare mais mort."
        )


def test_le_parametre_de_saisie_atteint_le_consommateur():
    """La chaine complete : `ecrire_le_lot_detecte` -> `consommer_...`."""
    import ast

    source = (Path(__file__).resolve().parents[2] / "src" / "mixed_media_utility"
              / "scan_write.py").read_text(encoding="utf-8")
    appels = [
        noeud for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Name)
        and noeud.func.id == "consommer_les_corrections_manuelles"
    ]
    assert appels, "aucun appel au consommateur : la frontiere ne lit rien."
    assert any("saisie_du_lot" in {m.arg for m in appel.keywords} for appel in appels), (
        "`ecrire_le_lot_detecte` ne transmet pas `saisie_du_lot` au "
        "consommateur : le maillon du milieu est coupe."
    )


# ---------------------------------------------------------------------------
# `EPIC11-ARB-106`, vague 3 : la saisie voyage dans le DOCUMENT.
#
# La correction precedente avait cable un parametre `saisie_du_lot` de bout en
# bout du coeur -- et aucun appelant de production ne le remplissait. L'auditeur
# de la vague 3 l'a mesure : `grep -rn saisie_du_lot src/` ne trouvait rien hors
# de `scan_write.py`, donc le refus continuait de promettre « ou fournir ces
# valeurs a la main », issue qu'aucune interface n'offrait. Le canal existait,
# il ne partait de nulle part.
# ---------------------------------------------------------------------------


def test_la_saisie_se_LIT_dans_la_couche_de_corrections():
    """Le meme chemin que les coins corriges : pose par l'interface, consomme
    par le coeur. Un second canal pour un meme geste serait une seconde verite."""
    document = {
        scan_corrections.CLE_DOCUMENT: {
            "schema": scan_corrections.SCHEMA_DE_CORRECTION,
            scan_corrections.CLE_SAISIE_DU_LOT: _saisie_complete(),
        }
    }
    assert scan_corrections.lire_la_saisie_du_lot(document) == _saisie_complete()


@pytest.mark.parametrize("document", [
    {},                                                    # aucune couche
    {scan_corrections.CLE_DOCUMENT: {
        "schema": scan_corrections.SCHEMA_DE_CORRECTION}},  # couche sans saisie
])
def test_l_ABSENCE_de_saisie_n_est_pas_une_anomalie(document):
    """La couche est additive : son absence ne se signale pas."""
    assert scan_corrections.lire_la_saisie_du_lot(document) is None


@pytest.mark.parametrize("saisie", [[], "x", 3, True])
def test_une_saisie_qui_n_est_pas_un_OBJET_est_refusee(saisie):
    document = {
        scan_corrections.CLE_DOCUMENT: {
            "schema": scan_corrections.SCHEMA_DE_CORRECTION,
            scan_corrections.CLE_SAISIE_DU_LOT: saisie,
        }
    }
    with pytest.raises(scan_corrections.CorrectionInvalide):
        scan_corrections.lire_la_saisie_du_lot(document)


def test_le_coeur_LIT_la_saisie_du_document_quand_l_appelant_n_en_passe_pas():
    """La chaine complete, mesuree structurellement.

    Sans ce maillon, le parametre `saisie_du_lot` reste un canal qui ne part de
    nulle part -- le defaut exact que la vague 3 a trouve.
    """
    import ast
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "src" / "mixed_media_utility"
              / "scan_write.py").read_text(encoding="utf-8")
    appels = [
        noeud for noeud in ast.walk(ast.parse(source))
        if isinstance(noeud, ast.Call)
        and isinstance(noeud.func, ast.Attribute)
        and noeud.func.attr == "lire_la_saisie_du_lot"
    ]
    assert appels, (
        "`scan_write` ne lit jamais la saisie du document de corrections : le "
        "canal `saisie_du_lot` ne part de nulle part, et le refus promet une "
        "issue qu'aucune interface ne peut executer."
    )
