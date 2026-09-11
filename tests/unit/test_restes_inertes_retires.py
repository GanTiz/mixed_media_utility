"""Les deux restes inertes disparaissent. Story 5.23, AC 13 (`EPIC5-ARB-88`).

Deux retraits, et un seul motif commun: **une chose inerte laissee en place revient**.

1. **le drapeau qui nommait la chaine de scan a la main**. Depuis `EPIC5-ARB-83`,
   l'operateur designe le profil lui-meme; le `chain_id` a cesse d'etre une **cle
   d'appariement**, donc surcharger sa derivation ne rattrapait plus aucune panne.
   `EPIC5-ARB-83` l'ecrivait deja: « probablement a retirer -- a trancher au
   developpement, jamais en le laissant inerte ». Egan a tranche le 2026-08-18: « Ok ».
   Le `chain_id`, lui, **reste**: il est l'identite et la provenance du profil, ecrite au
   fichier et au manifest, et sa derivation automatique nomme toujours ce que
   `scan calibrate` produit. Ce fichier verifie donc les deux moities -- le drapeau parti,
   le concept intact;
2. **le cardinal des planches refusees** passe a `derive_lot_calibration_status`. Il
   valait structurellement zero depuis que l'AC 3 de cette meme story a supprime le refus
   pour divergence, et un compte toujours nul presente comme un compte est l'un des
   quatre pieges nommes du 2026-08-12. Sa nullite est **prouvee ici**, structurellement,
   et non affirmee: c'est le seul fait qui pouvait contredire l'arbitrage.

**Pourquoi ce lot est rapide** (AC 9): rien n'y scanne, n'y ecrit et n'y compose. Il lit
du texte source, construit un parseur d'arguments, appelle une fonction pure et copie
deux modules dans un `tmp_path` pour y injecter des mutants. Aucun raster, aucun PDF.

**Ce que ce fichier chasse, dans l'ordre des pieges deja payes.**

* le drapeau **reintroduit en silence** -- la frontiere est verifiee sur le texte source
  de *toute* la production, pas sur la seule absence d'une constante;
* le grep de frontiere qui **ne regarde qu'un fichier**: le balayage est exerce contre
  une copie mutee ou le motif a ete reintroduit **ailleurs que dans `cli.py`**, ce qui
  tue le mutant « lire seulement le module evident »;
* la garde de `color_pipeline` retiree **sans son parametre**, qui laisserait dans la
  signature exactement le reste inerte que l'AC supprime.
"""

from __future__ import annotations

import ast
import inspect
import shutil
import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from mixed_media_utility import cli  # noqa: E402
from mixed_media_utility import color_calibration as cc  # noqa: E402
from mixed_media_utility import color_pipeline  # noqa: E402
from mixed_media_utility import scan_chain  # noqa: E402

#: Le **texte** des deux motifs, jamais ecrit en clair dans les assertions qui suivent.
#: Une frontiere negative qui epelle son propre motif se trouve elle-meme: le balayage
#: exclut donc son propre fichier, et le motif est reconstitue pour que ce fichier de test
#: ne se cite pas lui-meme si un jour il finissait sous `src/`.
_MOTIF_DRAPEAU = "chain" + "-id"
_MOTIF_CARDINAL = "declined" + "_page_count"

#: Racine de la production balayee. Sous-repertoires compris (`io/`, ...): un motif
#: reintroduit dans `io/calibration_profile.py` n'est pas moins reintroduit.
_PRODUCTION = SRC / "mixed_media_utility"


def _fichiers_de_production(racine: Path) -> list[Path]:
    """Tous les modules Python de la production sous `racine`, tries.

    Rendus **tries** et non dans l'ordre du systeme de fichiers: un rapport d'echec
    reproductible vaut mieux qu'un rapport qui change de contenu entre deux machines.
    """
    return sorted(racine.rglob("*.py"))


def _citations(motif: str, racine: Path) -> list[str]:
    """Les lignes de la production qui citent `motif`, avec fichier et numero.

    Le **commentaire compte**. Un motif conserve en commentaire est une invitation a le
    reintroduire, et surtout: la sortie d'aide d'`argparse` etant construite a partir de
    litteraux, un drapeau « seulement documente » se rebranche en une ligne. La seule
    exemption prevue par l'AC est un message de **migration**, et l'AC 13 n'en porte
    aucun -- voir `test_aucun_message_de_migration_n_est_prevu_et_le_motif_est_ecrit`.
    """
    trouvees: list[str] = []
    for fichier in _fichiers_de_production(racine):
        for numero, ligne in enumerate(
                fichier.read_text(encoding="utf-8").splitlines(), start=1):
            if motif in ligne:
                trouvees.append(
                    f"{fichier.relative_to(racine)}:{numero}: {ligne.strip()}")
    return trouvees


# ---------------------------------------------------------------------------
# Frontiere negative -- le grep des deux motifs rend zero sur la production
# ---------------------------------------------------------------------------


def test_le_balayage_couvre_bien_toute_la_production_et_pas_un_seul_fichier():
    """Le mutant « le grep ne regarde qu'un fichier », tue avant que le grep ne serve.

    Sans ce test, un balayage reduit a `cli.py` rendrait zero sur les deux motifs et les
    deux frontieres ci-dessous seraient vertes en ne mesurant rien. Trois faits sont donc
    epingles: le cardinal est grand, la recursion descend dans `io/`, et les trois modules
    qui portaient effectivement les restes sont dedans.
    """
    fichiers = _fichiers_de_production(_PRODUCTION)
    relatifs = {chemin.relative_to(_PRODUCTION).as_posix() for chemin in fichiers}
    assert len(fichiers) > 20, sorted(relatifs)
    # La recursion: un balayage non recursif verrait `cli.py` et manquerait `io/`.
    assert any(chemin.startswith("io/") for chemin in relatifs), sorted(relatifs)
    # Les trois modules qui portaient un reste avant cette AC. Les nommer ici est ce qui
    # empeche un futur balayage de les exclure par un filtre trop large.
    assert {"cli.py", "color_pipeline.py", "scan_chain.py"} <= relatifs, sorted(relatifs)


def test_aucun_fichier_de_production_ne_cite_le_drapeau_de_nommage_de_chaine():
    """AC 13, frontiere negative, volet 1: le drapeau a disparu du texte source."""
    assert _citations(_MOTIF_DRAPEAU, _PRODUCTION) == []


def test_aucun_fichier_de_production_ne_cite_le_cardinal_des_planches_refusees():
    """AC 13, frontiere negative, volet 2: le cardinal a disparu du texte source."""
    assert _citations(_MOTIF_CARDINAL, _PRODUCTION) == []


def test_le_balayage_de_frontiere_mord_reellement(tmp_path):
    """Les deux mutants de reintroduction, **injectes** et non relus.

    C'est la forme exigee par la politique du depot: une frontiere negative verte peut
    l'etre parce que rien n'est reintroduit, ou parce qu'elle ne cherche pas. Seule
    l'injection separe les deux.

    Les deux motifs sont reintroduits **ailleurs que dans `cli.py`** -- dans `scan_chain`
    pour le drapeau, dans `io/calibration_profile` pour le cardinal --, precisement parce
    que `cli.py` est le fichier qu'un balayage paresseux regarderait en premier. Un grep
    mono-fichier survivrait a une reintroduction dans `cli.py`; il ne survit pas a
    celle-ci.
    """
    mute = tmp_path / "mixed_media_utility"
    shutil.copytree(_PRODUCTION, mute,
                    ignore=shutil.ignore_patterns("__pycache__"))

    # Mutant 1: le drapeau revient, en commentaire, dans un module qui n'est pas `cli.py`.
    cible_drapeau = mute / "scan_chain.py"
    cible_drapeau.write_text(
        cible_drapeau.read_text(encoding="utf-8")
        + f"\n# surcharge possible par --{_MOTIF_DRAPEAU[len('chain-'):]}\n"
        + f"# le drapeau est '--{_MOTIF_DRAPEAU}'\n",
        encoding="utf-8")
    citations = _citations(_MOTIF_DRAPEAU, mute)
    assert any(citation.startswith("scan_chain.py:") for citation in citations), (
        "le balayage ne voit pas le drapeau reintroduit hors de cli.py", citations)

    # Mutant 2: le cardinal revient, dans un sous-repertoire, ce qu'un balayage non
    # recursif manquerait.
    cible_cardinal = mute / "io" / "calibration_profile.py"
    cible_cardinal.write_text(
        cible_cardinal.read_text(encoding="utf-8")
        + f"\n{_MOTIF_CARDINAL} = 0\n",
        encoding="utf-8")
    citations = _citations(_MOTIF_CARDINAL, mute)
    assert any(citation.startswith("io/calibration_profile.py:")
               for citation in citations), (
        "le balayage ne descend pas dans les sous-repertoires", citations)

    # Et le contre-epreuve, sur le meme arbre mute: le motif *non* reintroduit reste
    # introuvable. Un balayage qui rendrait toutes les lignes passerait les deux
    # assertions ci-dessus.
    assert _citations("un_motif_qui_n_existe_nulle_part", mute) == []


# ---------------------------------------------------------------------------
# Volet 1 -- le drapeau n'existe plus, le `chain_id` reste
# ---------------------------------------------------------------------------


def _refus_de_ligne_de_commande(argv: list[str], monkeypatch) -> int:
    """Faire analyser `argv` par le **vrai** parseur, et rendre le code de sortie.

    Les deux handlers de `scan` sont substitues: un argv accepte ne doit pas partir
    scanner un projet inexistant, et surtout un test qui passerait par un vrai handler
    confondrait « refuse a l'analyse » et « echoue plus loin ».
    """
    monkeypatch.setattr(cli, "scan_command", lambda args: 0)
    monkeypatch.setattr(cli, "scan_calibrate_command", lambda args: 0)
    with pytest.raises(SystemExit) as sortie:
        cli.main(argv)
    return sortie.value.code


def test_le_drapeau_de_nommage_de_chaine_est_refuse_par_la_ligne_de_commande(monkeypatch):
    """AC 13: `scan ... --chain-id C calibrate` n'est plus une commande valide.

    Le refus est celui d'`argparse` (`unrecognized arguments`, sortie 2) et non un message
    ecrit a la main: voir le test du choix ci-dessous, qui porte le motif.
    """
    assert _refus_de_ligne_de_commande([
        "scan", "--project", "p", "--scan", "s", "--dpi", "600",
        f"--{_MOTIF_DRAPEAU}", "chaine-nommee", "calibrate",
    ], monkeypatch) == 2


def test_le_drapeau_est_refuse_aussi_pose_sur_la_sous_commande(monkeypatch):
    """Les deux positions, parce que 5.22 avait paye la difference entre les deux.

    Le defaut mesure le 2026-08-17 etait exactement positionnel: declare des deux cotes,
    le drapeau etait analyse par le parent puis **ecrase** par le defaut du sous-parseur.
    Une suppression qui n'aurait retire que la declaration du parent laisserait la seconde
    position acceptee -- donc un drapeau toujours vivant, et silencieusement sans effet.
    """
    assert _refus_de_ligne_de_commande([
        "scan", "--project", "p", "--scan", "s", "--dpi", "600", "calibrate",
        f"--{_MOTIF_DRAPEAU}", "chaine-nommee",
    ], monkeypatch) == 2
    # Et sans la sous-commande: le drapeau vivait aussi au temps de la relecture.
    assert _refus_de_ligne_de_commande([
        "scan", "--project", "p", "--scan", "s", "--dpi", "600",
        f"--{_MOTIF_DRAPEAU}", "chaine-nommee",
    ], monkeypatch) == 2


def test_la_commande_scan_reste_analysable_sans_le_drapeau(monkeypatch):
    """Le pendant vivant: le retrait n'a pas casse le geste nominal.

    Sans ce test, les deux refus ci-dessus passeraient aussi bien si `scan` avait cesse
    d'exister -- un code 2 ne dit pas **pourquoi** il refuse.
    """
    vus: list = []
    monkeypatch.setattr(cli, "scan_calibrate_command", lambda args: vus.append(args) or 0)
    assert cli.main([
        "scan", "--project", "p", "--scan", "s", "--dpi", "600", "calibrate"]) == 0
    (args,) = vus
    assert not hasattr(args, "chain_id"), sorted(vars(args))


def _aides_de_la_commande_scan(capsys) -> list[str]:
    """Le texte d'aide de `scan` et de sa sous-commande, tel que l'operateur le lit."""
    aides = []
    for argv in (["scan", "--help"], ["scan", "calibrate", "--help"]):
        with pytest.raises(SystemExit):
            cli.main(argv)
        aides.append(capsys.readouterr().out)
    return aides


def test_aucune_aide_de_la_commande_scan_ne_cite_le_drapeau(capsys):
    """La frontiere porte aussi sur **le texte que l'operateur lit**.

    Meme regle que la frontiere du mot « seuil » de 5.16: une aide qui nomme une option
    inexistante la fait chercher.
    """
    aides = _aides_de_la_commande_scan(capsys)
    # L'aide est bien celle de `scan`, et non une page vide: sans ce temoin, la frontiere
    # serait verte sur une capture ratee.
    assert all(aide.strip() for aide in aides), aides
    # Le temoin de capture est desormais `--profil` (story 5.23, AC 12): l'option de
    # chargement de 5.22 a ete remplacee par elle, avec sa semantique d'appariement.
    assert any(cli.PROFILE_FLAG in aide for aide in aides), aides
    fautives = [aide for aide in aides if _MOTIF_DRAPEAU in aide]
    assert fautives == [], fautives


def test_la_derivation_de_l_identite_de_chaine_n_a_plus_de_surcharge():
    """Le **parametre** de surcharge est parti avec le drapeau.

    Le retirer de la ligne de commande en laissant `override=` dans la signature serait
    la forme exacte du reste inerte: le rebrancher tiendrait alors en une ligne
    d'`add_argument`, ce que `EPIC5-ARB-83` refuse mot pour mot.
    """
    parametres = inspect.signature(cli._derive_chain_id).parameters
    assert "override" not in parametres, sorted(parametres)
    assert list(parametres) == ["report", "scan_locator", "logger"], sorted(parametres)


def test_le_chain_id_lui_meme_reste_et_se_derive_toujours():
    """La moitie qu'il ne fallait **pas** retirer (`EPIC5-ARB-83` decision 3).

    Sans ce test, la frontiere negative ci-dessus serait passee aussi bien par un retrait
    du concept entier -- qui casserait le nommage des profils produits par
    `scan calibrate` -- que par le retrait du seul drapeau. Deux derivations distinguables
    plutot qu'une seule valeur temoin: une derivation devenue constante rendrait le meme
    identifiant pour deux chaines differentes, et un seul appel ne le verrait pas.
    """
    premier = scan_chain.derive_chain_id(
        declared_dpi=600, scan_input_format="tiff",
        make=None, model=None, software=None)
    second = scan_chain.derive_chain_id(
        declared_dpi=300, scan_input_format="tiff",
        make="EPSON", model="V850", software=None)
    assert premier != second
    assert premier.startswith("600-tiff-")
    assert second.startswith("300-tiff-")
    # Deterministe: rejoue, la meme entree rend la meme sortie.
    assert premier == scan_chain.derive_chain_id(
        declared_dpi=600, scan_input_format="tiff",
        make=None, model=None, software=None)


def test_aucun_message_de_migration_n_est_prevu_et_le_motif_est_ecrit():
    """**Le choix tranche au developpement**, epingle plutot que laisse a la relecture.

    L'AC 13 autorise un message de migration (« hors messages de migration »); elle ne
    l'exige pas. Le choix retenu est de **ne pas en ecrire**, pour trois raisons mesurees:

    1. le seul moyen d'emettre un message de retrait serait de **redeclarer l'option**
       avec une action qui echoue -- c'est-a-dire garder dans le parseur exactement le
       reste inerte que cette AC supprime, et faire echouer sa propre frontiere;
    2. `argparse` refuse deja bruyamment: `unrecognized arguments`, code de sortie **2**.
       Le regime qui justifierait un message sur mesure est le changement **silencieux**
       de comportement, et il n'a pas lieu ici -- c'est ce que le test du code 2
       ci-dessus verifie;
    3. l'option a vecu **une journee** (introduite le 2026-08-17 par 5.22, retiree le
       2026-08-18), sur une branche de developpement, sans version publiee et sans une
       seule mention dans `docs/` -- ce que la derniere assertion de ce test verifie,
       parce que c'est le fait qui pourrait changer et invalider le choix.

    Si un jour `docs/` documente le drapeau, cette assertion rougit et le choix se
    rediscute: c'est la forme la plus utile qu'un arbitrage puisse prendre dans un test.
    """
    # Aucun sur-mesure: rien de la production ne parle du retrait a l'operateur.
    assert _citations(_MOTIF_DRAPEAU, _PRODUCTION) == []
    docs = SRC.parent / "docs"
    # Le dossier existe et porte des documents: sans ce temoin, le balayage ci-dessous
    # serait vert sur un `docs/` absent ou renomme, c'est-a-dire vert en ne lisant rien.
    assert docs.is_dir(), docs
    # `rglob` et non `glob` depuis le lot 4C du 2026-09-10 : les protocoles de
    # test manuel sont descendus dans `docs/protocoles/`, et un balayage de la
    # seule RACINE de `docs/` ne les lisait plus. Il ne restait alors que deux
    # documents a la racine -- le temoin de vivacite ci-dessous l'a dit en
    # rougissant, ce pour quoi il existe. Balayer tout `docs/` mesure ce que ce
    # test a toujours voulu mesurer : que le drapeau retire n'est documente
    # NULLE PART, pas seulement a la racine.
    assert len(list(docs.rglob("*.md"))) > 3, sorted(
        chemin.name for chemin in docs.rglob("*"))
    fautifs = [
        f"{chemin.relative_to(docs)}:{numero}"
        for chemin in sorted(docs.rglob("*.md"))
        for numero, ligne in enumerate(
            chemin.read_text(encoding="utf-8").splitlines(), start=1)
        if _MOTIF_DRAPEAU in ligne
    ]
    assert fautifs == [], fautifs


# ---------------------------------------------------------------------------
# Volet 2 -- le cardinal des planches refusees, et la preuve qu'il valait zero
# ---------------------------------------------------------------------------


def test_la_derivation_du_statut_de_lot_n_accepte_plus_le_cardinal_des_refus():
    """Le mutant « garde retiree, parametre conserve », tue par la signature.

    C'est le mutant le plus probable de ce retrait: supprimer la branche morte est le
    geste visible, laisser le parametre est l'oubli naturel. Un parametre conserve reste
    passable par un appelant, donc reste une porte -- et une porte ouverte sur une
    decision de statut est precisement ce que `EPIC5-ARB-88` ferme.
    """
    parametres = inspect.signature(color_pipeline.derive_lot_calibration_status).parameters
    assert _MOTIF_CARDINAL not in parametres, sorted(parametres)
    assert sorted(parametres) == [
        "calibration_page_present",
        "correctable_page_count",
        "corrected_page_count",
        "correction_requested",
        "lot_correction_available",
    ], sorted(parametres)
    with pytest.raises(TypeError):
        color_pipeline.derive_lot_calibration_status(
            calibration_page_present=True,
            lot_correction_available=True,
            correctable_page_count=2,
            corrected_page_count=0,
            **{_MOTIF_CARDINAL: 2},
        )


def test_le_statut_de_lot_garde_exactement_le_comportement_qu_il_avait():
    """Le retrait est **sans effet sur les valeurs rendues**, et c'est verifie cas par cas.

    Les cinq regimes du contrat, dont celui que la garde retiree gouvernait: aucune
    planche corrigee alors qu'au moins une etait corrigeable rend `failed`, exactement
    comme avant -- puisque le cardinal des refus valait zero, la comparaison etait
    invariablement fausse et la branche `not_applied` invariablement morte.
    """
    commun = {"calibration_page_present": True, "lot_correction_available": True}
    # Le regime que la garde gouvernait, aux deux cardinaux qui l'encadraient.
    assert color_pipeline.derive_lot_calibration_status(
        **commun, correctable_page_count=1,
        corrected_page_count=0) == color_pipeline.FAILED_STATUS
    assert color_pipeline.derive_lot_calibration_status(
        **commun, correctable_page_count=3,
        corrected_page_count=0) == color_pipeline.FAILED_STATUS
    # Les quatre autres, inchanges.
    assert color_pipeline.derive_lot_calibration_status(
        **commun, correctable_page_count=3,
        corrected_page_count=1) == color_pipeline.APPLIED_STATUS
    assert color_pipeline.derive_lot_calibration_status(
        **commun, correctable_page_count=0,
        corrected_page_count=0) == color_pipeline.NOT_APPLIED_STATUS
    assert color_pipeline.derive_lot_calibration_status(
        calibration_page_present=True, lot_correction_available=False,
        correctable_page_count=3,
        corrected_page_count=0) == color_pipeline.FAILED_STATUS
    assert color_pipeline.derive_lot_calibration_status(
        **commun, correctable_page_count=3, corrected_page_count=0,
        correction_requested=False) == color_pipeline.NOT_APPLIED_STATUS
    assert color_pipeline.derive_lot_calibration_status(
        calibration_page_present=False, lot_correction_available=False,
        correctable_page_count=3,
        corrected_page_count=0) == color_pipeline.NOT_APPLIED_STATUS


def _fonction(arbre: ast.Module, nom: str) -> ast.FunctionDef:
    """La definition de `nom` dans `arbre`, ou une erreur nommee."""
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.FunctionDef) and noeud.name == nom:
            return noeud
    raise AssertionError(f"fonction absente du module: {nom}")


def _sorties_hors_fonctions_imbriquees(fonction: ast.FunctionDef) -> list[ast.Return]:
    """Les `return` du corps de `fonction`, fermetures internes exclues.

    Les fermetures internes (`_fail`) ont leurs propres `return`, et les compter comme
    sorties de la fonction fausserait le denombrement dans les deux sens.
    """
    imbriquees = {
        interne for enfant in ast.iter_child_nodes(fonction)
        if isinstance(enfant, ast.FunctionDef)
        for interne in ast.walk(enfant)
    }
    return [noeud for noeud in ast.walk(fonction)
            if isinstance(noeud, ast.Return) and noeud not in imbriquees]


def _verifier_la_nullite_du_cardinal(arbre: ast.Module) -> None:
    """**La** preuve, ecrite une seule fois et exercee dans les deux sens.

    Elle vit dans une fonction plutot que dans le corps d'un test parce que le test qui
    l'exerce a l'envers -- sur un arbre ou la sortie retiree a ete reinjectee -- doit
    appeler **exactement** ce code. Une seconde redaction du denombrement dans le test du
    mutant rendrait la preuve tautologique: c'est le defaut mesure sur 5.9, et il a
    effectivement survecu a une premiere redaction de ce fichier (relacher `== 1` en
    `>= 1` ici laissait le test du mutant vert).

    Leve `AssertionError` des qu'une sortie de `calibrate_page` peut combiner l'absence de
    `profile` et l'absence de `failure_reason` -- c'est-a-dire des que le cardinal retire
    par l'AC 13 pourrait redevenir non nul.
    """
    sorties = _sorties_hors_fonctions_imbriquees(_fonction(arbre, "calibrate_page"))
    assert len(sorties) > 5, len(sorties)
    autres = []
    for retour in sorties:
        valeur = retour.value
        if (isinstance(valeur, ast.Call) and isinstance(valeur.func, ast.Name)
                and valeur.func.id in {"_fail", "_failed"}):
            # Le motif est le premier argument **positionnel**: un `_fail()` sans motif
            # rendrait un echec sans `failure_reason`, donc un troisieme regime.
            assert valeur.args, ast.dump(valeur)
            continue
        autres.append(valeur)
    assert len(autres) == 1, [ast.unparse(valeur) for valeur in autres]
    terminale = autres[0]
    assert isinstance(terminale, ast.Call)
    assert isinstance(terminale.func, ast.Name) and terminale.func.id == "PageCalibration"
    nommes = {mot.arg: ast.unparse(mot.value) for mot in terminale.keywords}
    assert nommes["status"] == "acceptance.status"
    assert nommes["failure_reason"] == "acceptance.failure_reason"
    assert nommes["profile"] == "profile if acceptance.status == 'applied' else None"

    # Et le fait de production qui rend ces deux expressions constantes: le statut du
    # verdict est un **litteral** depuis `EPIC5-ARB-78`, donc invariablement `"applied"`,
    # donc le `profile` est invariablement conserve et le `failure_reason` invariablement
    # celui d'`evaluate_page_acceptance` -- lui-meme litteral `None`.
    verdict = next(
        noeud for noeud in ast.walk(_fonction(arbre, "evaluate_acceptance"))
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
        and noeud.func.id == "AcceptanceVerdict")
    statut = {mot.arg: mot.value for mot in verdict.keywords}["status"]
    assert isinstance(statut, ast.Constant) and statut.value == "applied", ast.dump(statut)


def _arbre_de_la_couche_couleur() -> ast.Module:
    return ast.parse((_PRODUCTION / "color_calibration.py").read_text(encoding="utf-8"))


def test_le_cardinal_retire_valait_structurellement_zero():
    """**La preuve, pas l'affirmation.** C'est le seul fait qui pouvait bloquer l'AC.

    Le cardinal comptait, dans `page_calibrations`, les resultats sans `profile` **et**
    sans `failure_reason`. `page_calibrations` ne porte que des sorties de
    `calibrate_page` -- la page de calibration elle-meme n'y entre pas, elle est traitee
    par la branche `PAGE_ROLE_CALIBRATION` de `_scanned_pages_for_output`, qui n'ajoute
    aucune calibration. Il suffit donc de montrer qu'aucune sortie de `calibrate_page` ne
    combine les deux absences, ce que fait `_verifier_la_nullite_du_cardinal`.

    Si un jour une sortie sortait de ces formes, ce test rougit -- et c'est exactement le
    moment ou l'arbitrage `EPIC5-ARB-88` devrait etre rouvert plutot que contourne.
    """
    _verifier_la_nullite_du_cardinal(_arbre_de_la_couche_couleur())


def test_la_preuve_de_nullite_mord_sur_une_sortie_qui_la_contredirait():
    """Le mutant de la preuve elle-meme: une sortie `not_applied` reintroduite.

    Une preuve structurelle qui ne rougit sur rien est une tautologie -- le defaut trouve
    sur 5.9. On reintroduit ici, dans une copie de l'arbre, exactement la sortie que
    `EPIC5-ARB-82` a supprimee (`return _not_applied_page(...)`, sans motif d'echec), et
    on verifie que **la meme** fonction de preuve la refuse. Appeler la meme fonction est
    le point: une seconde redaction du denombrement rendrait ce test complaisant.
    """
    arbre = _arbre_de_la_couche_couleur()
    fonction = _fonction(arbre, "calibrate_page")
    mutant = ast.parse(
        "if divergence is not None:\n"
        "    return _not_applied_page(reason=NOT_APPLIED_PAGE_DIVERGES,\n"
        "                             preset_id=patch_preset_id, values_version=version)\n"
    ).body[0]
    fonction.body.insert(len(fonction.body) - 1, mutant)
    ast.fix_missing_locations(arbre)
    with pytest.raises(AssertionError):
        _verifier_la_nullite_du_cardinal(arbre)


def test_la_preuve_de_nullite_accepte_l_arbre_intact_apres_une_copie():
    """Contre-epreuve du precedent: la preuve n'echoue pas sur *tout* arbre.

    Sans elle, `_verifier_la_nullite_du_cardinal` pourrait lever inconditionnellement et
    le test du mutant serait vert pour la mauvaise raison.
    """
    _verifier_la_nullite_du_cardinal(_arbre_de_la_couche_couleur())


def test_la_fermeture_de_refus_n_a_pas_de_domaine_de_retour():
    """Le pendant vivant du precedent: rien, en production, ne construit un refus de page.

    `_not_applied_page` reste **definie** -- son commentaire de 5.23 dit pourquoi -- mais
    aucune ligne ne l'appelle plus, et c'est ce fait-la qui rend le cardinal nul. Le
    verifier separement de la preuve structurelle ci-dessus evite qu'un futur appel
    reintroduit ailleurs (hors de `calibrate_page`) passe entre les deux tests.
    """
    appelants = []
    for fichier in _fichiers_de_production(_PRODUCTION):
        arbre = ast.parse(fichier.read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Name)
                    and noeud.func.id == "_not_applied_page"):
                appelants.append(f"{fichier.name}:{noeud.lineno}")
    assert appelants == [], appelants
    # Le motif, lui, reste **enregistre**: les manifests deja ecrits chez Egan le portent.
    assert cc.NOT_APPLIED_PAGE_DIVERGES == "page_diverges_without_explicit_apply"


# ---------------------------------------------------------------------------
# `EPIC5-ARB-101` -- extension de la frontiere: l'aide ne promet plus le fichier
# nomme par la chaine
# ---------------------------------------------------------------------------
#
# Troisieme reste de la liste de `EPIC5-ARB-101`: « aide du sous-parseur `calibrate`,
# promet encore un fichier `<chain_id>.json` ». Depuis l'AC 8quater,
# `io.calibration_profile.write_profile` nomme le fichier par le **slug de l'etiquette**
# donnee par l'operateur, et le `chain_id` seulement a defaut.
#
# **La frontiere porte sur le texte que l'operateur lit, pas sur le source.** C'est
# delibere et mesure: le motif survit legitimement dans les commentaires de production
# qui racontent le regime d'avant (`cli.py`, la derivation de 5.22 qui « lisait
# versions/calibration/<chain_id>.json »), et un balayage du source les compterait pour
# des reintroductions. Ce que l'AC 13 interdit est qu'une aide **promette** une chose
# inexistante -- meme regle que la frontiere du mot « seuil » de 5.16: une aide qui
# nomme une chose inexistante la fait chercher, et l'operateur qui ne trouve pas le
# fichier conclut que la commande n'a rien ecrit.

#: Le motif, reconstitue et jamais ecrit en clair, pour la meme raison que les deux
#: motifs du haut de ce fichier: une frontiere negative qui epelle son propre motif se
#: trouverait elle-meme si ce fichier passait un jour sous un balayage de source.
_MOTIF_FICHIER_DE_CHAINE = "<chain" + "_id>.json"

#: Les commandes dont l'aide est relue. La liste est **nommee** plutot que deduite du
#: parseur: une deduction qui se tromperait rendrait une liste vide, et la frontiere
#: serait verte en ne lisant rien. Le temoin de non-vacuite ci-dessous ferme l'autre
#: moitie du meme piege.
_COMMANDES_AIDEES = (
    ("scan",),
    ("scan", "calibrate"),
    ("set-default-profile",),
    ("makepdf",),
)


def _aide_de(argv: tuple[str, ...], capsys) -> str:
    """Le texte d'aide de cette commande, tel que l'operateur le lit."""
    with pytest.raises(SystemExit):
        cli.main([*argv, "--help"])
    return capsys.readouterr().out


def test_aucune_aide_de_commande_ne_promet_le_fichier_nomme_par_la_chaine(capsys):
    """AC 13, frontiere negative, volet 3 (`EPIC5-ARB-101`).

    Toutes les aides sont relues, pas seulement celle de `calibrate`: le motif s'est
    deja glisse dans deux redactions (l'aide du sous-parseur **et** le docstring du
    handler), et rien n'empeche une troisieme de reapparaitre sur `scan` ou sur la
    commande de profil par defaut.
    """
    aides = {argv: _aide_de(argv, capsys) for argv in _COMMANDES_AIDEES}
    # Temoin de capture: sans lui, la frontiere serait verte sur des pages vides.
    assert all(aide.strip() for aide in aides.values()), aides
    # Et les aides sont bien celles qu'on croit: `--profil` est declare sur `scan` et
    # sur `set-default-profile`, `calibrate` se nomme dans l'aide de `scan`.
    assert cli.PROFILE_FLAG in aides[("scan",)], aides[("scan",)]
    assert cli.PROFILE_FLAG in aides[("set-default-profile",)]
    assert cli.SCAN_CALIBRATE_SUBCOMMAND in aides[("scan",)], aides[("scan",)]
    fautives = {argv: aide for argv, aide in aides.items()
                if _MOTIF_FICHIER_DE_CHAINE in aide}
    assert fautives == {}, sorted(fautives)


def _promet_le_fichier_de_chaine(aide: str) -> bool:
    """Le predicat de la frontiere, isole pour etre injectable.

    Isole pour la meme raison que `_citations` plus haut: c'est lui qu'on met a
    l'epreuve d'une reintroduction, et un predicat ecrit en ligne dans l'assertion ne
    se met a l'epreuve de rien.
    """
    return _MOTIF_FICHIER_DE_CHAINE in aide


def test_la_frontiere_des_aides_mord_reellement(capsys):
    """Le mutant de reintroduction, **injecte dans un vrai parseur** et non concatene.

    Meme forme que `test_le_balayage_de_frontiere_mord_reellement` plus haut: une
    frontiere verte peut l'etre parce que rien n'est reintroduit, ou parce qu'elle ne
    cherche pas. Seule l'injection separe les deux.

    Le mutant passe par le **chemin realiste** de reintroduction: un litteral d'aide
    d'`add_parser`, rendu par le formateur d'`argparse` lui-meme. Le detour n'est pas
    cosmetique -- `argparse` **replie** les aides longues sur plusieurs lignes, et une
    frontiere qui chercherait un motif contenant une espace y deviendrait aveugle. Le
    motif vise n'en contient aucune, ce qui est mesure ici plutot que suppose.
    """
    import argparse
    import contextlib
    import io as _io

    parseur = argparse.ArgumentParser(prog="mutant")
    sous = parseur.add_subparsers()
    sous.add_parser(
        SCAN_CALIBRATE_LITTERAL,
        help="Calibrer la chaine de scan d'une page de calibration: ajuster la "
             "correction et la consigner sous versions/calibration/"
             f"{_MOTIF_FICHIER_DE_CHAINE}, pour que tous les lots de la chaine la "
             "reutilisent")
    tampon = _io.StringIO()
    with contextlib.redirect_stdout(tampon):
        parseur.print_help()
    aide_mutee = tampon.getvalue()

    # L'aide mutee est bien repliee sur plusieurs lignes -- sans quoi l'injection ne
    # mesurerait pas le regime qu'elle pretend mesurer.
    assert len(aide_mutee.splitlines()) > 6, aide_mutee
    assert _promet_le_fichier_de_chaine(aide_mutee), aide_mutee
    # Contre-epreuve sur le meme texte: un predicat qui rendrait toujours `True`
    # passerait l'assertion ci-dessus.
    assert "un_motif_qui_n_existe_nulle_part" not in aide_mutee
    # Et les aides reelles, elles, restent propres: c'est ce que l'injection valide.
    for argv in _COMMANDES_AIDEES:
        assert not _promet_le_fichier_de_chaine(_aide_de(argv, capsys)), argv


#: Le nom de la sous-commande, ecrit **en litteral** et non lu sur `cli`: l'injection
#: ci-dessus doit construire son parseur mutant sans dependre du module qu'elle teste.
SCAN_CALIBRATE_LITTERAL = "calibrate"


def test_le_nom_de_la_sous_commande_est_bien_celui_du_litteral():
    """Le litteral de l'injection et la constante du code disent la meme chose.

    Sans lui, un renommage de la sous-commande laisserait l'injection construire un
    parseur qui ne ressemble plus a celui de la production, et la frontiere mesurerait
    une commande qui n'existe pas.
    """
    assert cli.SCAN_CALIBRATE_SUBCOMMAND == SCAN_CALIBRATE_LITTERAL


# ---------------------------------------------------------------------------
# `EPIC5-ARB-101` -- le parametre `chain_id` de `write_profile` a disparu
# ---------------------------------------------------------------------------
#
# Quatrieme reste de la liste, retire le 2026-08-19. Il ne decidait plus de
# l'emplacement du fichier depuis l'AC 8quater (c'est le slug de l'etiquette qui le
# fait), et sa seule action restante -- `_validate_chain_id(chain_id)` -- etait deja
# faite sur la **meme** valeur par `validate_profile_document`, appelee deux lignes plus
# bas. Un parametre accepte puis sans effet est la definition litterale du reste inerte.


def test_write_profile_n_accepte_plus_de_parametre_de_chaine():
    """Le parametre est parti de la **signature**, pas seulement des appels.

    Le laisser dans la signature en cessant de le lire serait la forme exacte du reste
    inerte que l'AC 13 retire ailleurs: le rebrancher tiendrait en une ligne, et
    entre-temps chaque appelant croirait valider une identite.
    """
    from mixed_media_utility.io import calibration_profile

    parametres = inspect.signature(calibration_profile.write_profile).parameters
    assert "chain_id" not in parametres, sorted(parametres)
    # Temoin positif: la fonction existe toujours et garde ses trois autres parametres.
    assert list(parametres) == ["project_dir", "document", "confirm_overwrite"], \
        sorted(parametres)


def test_la_garde_d_identite_de_chaine_survit_au_retrait_du_parametre(tmp_path):
    """Ce que le parametre semblait tenir, et qui est tenu ailleurs -- mesure.

    C'est le geste 2 de la section 7 de la politique de revue: **avant de retirer une
    garde, mesurer ce qu'elle couvrait par accident**. Les cinq formes fautives que les
    tests du parametre exercaient sont confrontees ici au document seul; si l'une
    passait, le retrait aurait ouvert un trou par lequel une valeur non derivee
    atteindrait un nom de fichier.

    Les cinq formes sont ecrites **en litteral**, jamais derivees d'une constante du
    module: une liste construite depuis le pattern du code mesurerait le pattern contre
    lui-meme.
    """
    from mixed_media_utility.io import calibration_profile
    import test_calibration_profile as profil

    for mauvais in ("../escape", "avec espace", "chemin/relatif", "", "x\n"):
        with pytest.raises(calibration_profile.ProfileValidationError):
            calibration_profile.write_profile(
                tmp_path, profil._document_complet(chain_id=mauvais))
    # Temoin positif: un identifiant livre passe, donc les cinq refus ci-dessus ne sont
    # pas ceux d'une fonction qui refuserait tout.
    assert calibration_profile.write_profile(
        tmp_path, profil._document_complet()).is_file()
