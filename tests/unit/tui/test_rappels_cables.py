# -*- coding: utf-8 -*-
"""La garde STRUCTURELLE des rappels -- lot `N2`, story 11.4 (2026-08-30).

**Le mode de panne que ce banc ferme, et son compte.** Sept fois dans l'epic 11,
un ecran a recu son action sous forme de **parametre optionnel de type
`Callable`** que le produit n'injectait nulle part, avec un `if ... is not None`
qui transformait le manque en **silence** :

1. lot `E9` -- `ChaineReelle` etait assemblee a la main dans `demo_vague_2.py`
   et nulle part dans l'application : `mmu-tui` ouvrait trois ecrans TEMOINS ;
2. `I0` -- le journal du produit : `run_extraction` exige un `logger`, la TUI
   n'en passait aucun, et **toute** extraction lancee depuis `mmu-tui` tombait ;
3. `I3` -- `rushes.bandeau_de_relink`, livre, teste, exporte, appele par aucun
   ecran : la droite du bandeau etait vide sur les DOUZE ecrans ;
4. `I2` -- `rushes.lignes_des_modes` et `PHRASE_AJOUTER_UN_RUSH`, meme famille ;
5. `K1.1a` -- `ajouter un rush` : l'explorateur s'ouvrait, on designait une
   vraie video, et **rien** ne se passait -- ni ajout, ni message, ni refus ;
6. `K3.1a` -- les quatre suites de `E2-5` : `ouvrir_le_resultat` acceptait
   `sur_suite`, son unique point d'appel ne le passait pas, et les quatre
   suites etaient navigables au clavier et **decoratives** ;
7. `N3` -- les trois issues de `E2-1d`. Famille voisine et distincte : rien ne
   manquait a l'injection, c'est la **valeur de retour** de `choix.valider()`
   qui etait lue puis jetee. Voir la section « ce que cette garde n'attrape
   pas » en bas de ce fichier.

**Chaque fois, TOUS les bancs etaient verts** -- parce qu'un banc injecte le
rappel lui-meme. C'est la raison d'etre de cette garde : elle ne mesure pas un
comportement, elle mesure un **cablage**, et le cablage est precisement ce
qu'aucun banc unitaire ne peut voir.

**Le patron est celui de la garde du lot `J`**
(`test_atelier_extraction_rushes.py::test_TOUTE_surface_publique_de_rushes_est_CABLEE_ou_DECLAREE`)
: une **egalite** contre un inventaire ferme, donc une garde qui mord des DEUX
cotes. Un rappel nouveau qu'aucun appel n'injecte doit entrer dans
:data:`OPTIONNELS_ASSUMES` **avec sa raison** ; un rappel qu'on decablerait
sortirait de l'inventaire et ferait rougir le banc.

**La mesure est faite sur l'ARBRE SYNTAXIQUE, jamais par un grep** : c'est la
lecon du finding `I3`, ou le nom etait partout dans les commentaires et nulle
part dans le code. Un docstring qui cite `sur_suite` ne cable rien.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[3]
_SRC = str(_RACINE / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import pytest


# ---------------------------------------------------------------------------
# L'inventaire ferme : les rappels optionnels que le produit N'INJECTE PAS,
# et **pourquoi**. Une entree sans raison fait rougir le volet symetrique.
# ---------------------------------------------------------------------------

#: Deux familles seulement y ont leur place, et elles se distinguent par une
#: question : **est-ce que l'absence se voit ?**
#:
#: * un POINT D'INJECTION DE BANC -- le rappel a un defaut qui est le vrai
#:   chemin de production (le disque, le coeur, `ffprobe`), et l'omettre ne
#:   degrade rien : c'est le double qui est l'exception, pas le defaut ;
#: * un MANQUE QUI SE DIT -- le rappel n'existe pas encore, et l'ecran NOMME ce
#:   qui manque au lieu de ne rien faire. C'est ce que `K1.1` a paye.
#:
#: Ce qui n'y a **pas** sa place : un rappel dont l'absence est un no-op muet.
#: C'est exactement le defaut, et le declarer ici reviendrait a le classer.
OPTIONNELS_ASSUMES = {
    ("EcranRushes", "ajouter"):
        # **Motif CORRIGE le 2026-09-06** (recensement des filets « pas
        # encore »). Il portait : « K1.1d ouvert : le point d'entree de coeur
        # "declarer un rush sans l'extraire" n'existe pas. » C'est faux depuis
        # que la declaration en deux temps est livree, et le depot se
        # contredisait a deux endroits -- `ChaineReelle.atelier_extraction`
        # ecrit dans son propre docstring que c'est « ce qui ferme K1.1d ».
        # Un justificatif qu'on ne rouvre pas se perime en silence : c'est le
        # defaut exact que `MQ-4` et `MQ-5` ont paye, ici dans l'inventaire
        # d'une frontiere plutot que dans un filet.
        "voie a UN TEMPS, SUPPLANTEE par le couple `preparer`/`ecrire` "
        "qu'exige `EPIC11-ARB-4` -- le panneau chiffre se peint ENTRE les "
        "deux. Le point d'entree de coeur EXISTE "
        "(`declaration_de_rush.preparer_une_declaration` et "
        "`ecrire_la_declaration`), et `ChaineReelle.atelier_extraction` "
        "injecte les deux temps. Le produit n'atteint donc plus ce rappel : "
        "`_valider_l_explorateur` passe par `_declarer` avant de le lire. Il "
        "reste accepte parce qu'un banc s'en sert, et son absence NE SE TAIT "
        "PAS -- `ce_qui_manque_pour_ajouter` la nomme sur un ecran « pas "
        "encore »",
    ("EcranRushes", "existe"):
        "oracle de presence de banc ; sans lui `rushes.lister` interroge le "
        "vrai disque, qui est le chemin de production",
    ("Explorateur", "lister"):
        "double de disque de banc ; le defaut est `_lister_le_disque`",
    ("Explorateur", "compter_sous_dossiers"):
        "double de disque de banc ; le defaut est `_compter_par_defaut`",
    ("Explorateur", "lister_volumes"):
        "double de MACHINE de banc ; le defaut est `volumes_du_systeme`. "
        "Meme motif que `lister` un cran plus haut, et une raison de plus : "
        "c'est ce qui permet de rejouer la liste des volumes WINDOWS -- des "
        "lettres de lecteur, un lecteur debranche -- sur une machine qui n'en "
        "a aucun. Sans lui, la moitie du produit qu'Egan utilise ne se "
        "mesurerait que chez Egan",
    ("ParcoursExtraction", "sonder"):
        "double de banc ; le defaut est `sonder_la_source`, qui paie ffprobe",
    ("ParcoursExtraction", "preparer_la_previz"):
        "double de banc ; le defaut est `cadence_previz.prepare_previz`",
    ("ParcoursExtraction", "jouer"):
        "double de banc ; le defaut est `jouer_les_cadences`, qui ouvre la "
        "vraie fenetre OpenCV",
    ("ParcoursExtraction", "extraire"):
        "double de banc ; `None` traverse jusqu'a `executer_le_plan`, dont le "
        "defaut est `extraction.run_extraction`",
    ("ParcoursExtraction", "composer_les_planches"):
        "double de banc ; le defaut est le VRAI point d'entree, "
        "`atelier_pdf.ouvrir_la_composition_des_planches`, resolu a l'appel "
        "dans `_composer_les_planches_de_ces_lots`. Il est resolu la et non "
        "injecte par `ChaineReelle` parce que la signature de "
        "`ouvrir_les_cadences` est celle que `ChaineReelle.extraire` appelle : "
        "y faire traverser un second rappel Pdf ferait diverger les deux "
        "cablages de l'atelier Pdf (`MQ-4`, 2026-09-06)",
    ("ParcoursExtraction", "verifier_l_affichage"):
        "double de banc ; absent, `_affichage()` rend un dictionnaire VIDE et "
        "les deux ecrans appellent la garde reelle du coeur eux-memes",
    # `("EcranScanMenu", "entrer")` et `("EcranScanDepot", "detecter")` SONT
    # SORTIS DE CET INVENTAIRE le 2026-08-31, avec le lot F de la story 11.5 :
    # `ParcoursScan` les injecte tous les deux, et `chaine_du_produit` injecte
    # le parcours. **C'est le volet « declares mais desormais cables » qui l'a
    # dit**, pas une relecture -- la garde a rougi dans le sens de la
    # reparation, ce qu'une assertion positive n'aurait pas fait.
    # `("EcranPdfMenu", "entrer")`, `("EcranLotsAPlanches", "continuer")`,
    # `("EcranReglagesDesPlanches", "continuer")` et
    # `("EcranPdfConfirmation", "sur_issue")` SONT SORTIS DE CET INVENTAIRE le
    # 2026-09-02, avec le lot de cablage de la story 11.7 : `ParcoursPdf` les
    # injecte tous les quatre, et `atelier_pdf.ouvrir_l_atelier_pdf` -- que
    # `chaine_du_produit` injecte deja -- monte le parcours. **Les quatre
    # entrees annoncaient leur propre sortie** (« elle SORT de l'inventaire le
    # jour ou un parcours Pdf injecte le rappel »), et c'est le volet
    # « declares mais desormais cables » qui l'a dit, pas une relecture :
    # quatrieme fois que cette garde rougit dans le sens de la reparation.
    ("suivre", "encoder_un_master"):
        "double de banc de `atelier_scan_resultat.suivre` ; le defaut est le "
        "VRAI point d'entree, `atelier_exports_parcours.ouvrir_l_atelier_"
        "exports`, resolu a l'appel dans `encoder_un_master_depuis_ces_lots`. "
        "`suivre` est une FONCTION de module, pas une methode de parcours : "
        "elle n'a pas de constructeur ou l'injecter, et son appelant "
        "(`conclure`) ne connait rien de l'atelier Exports (`MQ-5`, "
        "2026-09-06)",
    ("ParcoursScan", "detection"):
        "double de banc ; le defaut est `scan_detect.run_scan_detect`, le vrai "
        "point d'entree du coeur. `None` traverse jusqu'a `executer_et_conclure`, "
        "qui exige `detection` sans defaut de son cote -- c'est le double qui "
        "est l'exception, pas le defaut",
    ("ParcoursScan", "mesurer"):
        "double de banc ; le defaut est `scan_ingest.mesurer_le_dpi`, que "
        "`atelier_scan.designer` appelle quand personne n'en donne d'autre. "
        "Absent, le depot mesure le VRAI fichier designe",
    # `("EcranScanConfirmation", "sur_issue")` et `("consigner", "hote")` SONT
    # SORTIS DE CET INVENTAIRE le 2026-09-01, avec le lot H de la story 11.6 :
    # `ParcoursScan.confirmer` injecte le premier, `ParcoursScan.consigner_le_profil`
    # le second (`hote=self.app.executer_en_processus`). Les deux entrees
    # annoncaient leur propre sortie -- « elle SORT de cet inventaire au lot H,
    # et c'est le volet "declares mais desormais cables" qui le dira » --, et
    # c'est **ce volet-la** qui l'a dit, pas une relecture. Troisieme fois que
    # cette garde rougit dans le sens de la reparation.
    ("ParcoursScan", "ecriture"):
        "double de banc ; le defaut est "
        "`scan_write.ecrire_depuis_le_document`, le point d'entree de coeur du "
        "temps 2 livre par le lot B. `None` traverse jusqu'a "
        "`executer_et_conclure`, qui exige `ecrire` sans defaut de son cote -- "
        "c'est le double qui est l'exception, pas le defaut",
    ("ParcoursScan", "calibration"):
        "double de banc ; le defaut est `scan_calibrate.calibrer_la_chaine`, "
        "le point d'entree de coeur de `scan ... calibrate` livre par le lot "
        "B. `None` traverse jusqu'a `consigner`, qui porte le vrai point "
        "d'entree en defaut -- une passe reelle ingere un scan et ecrit un "
        "profil, ce qu'un banc ne demande qu'en le disant",
    ("ParcoursPdf", "generer"):
        "double de banc ; le defaut est "
        "`makepdf.generer_les_planches_du_lot`, le vrai point d'entree de "
        "coeur de l'atelier Pdf. `None` traverse jusqu'a `executer_les_lots`, "
        "qui retombe elle aussi sur ce point d'entree -- c'est le double qui "
        "est l'exception, pas le defaut",
    ("ParcoursPdf", "calibrer"):
        "double de banc ; le defaut est "
        "`makepdf.generer_la_page_de_calibration`, le point d'entree de coeur "
        "de la mire. Absent, une passe reelle compose et ecrit la planche de "
        "calibration, ce qu'un banc ne demande qu'en le disant",
    ("ParcoursPdf", "horloge"):
        "double de banc ; le defaut est `datetime.now`, pose par "
        "`executer_les_lots`. Il horodate les lignes de journal de `E5-4` : "
        "une horloge lue au fond d'une fonction rendrait le journal "
        "immesurable, et c'est pourquoi l'instant est DONNE",
    # `("EcranDesLotsAEncoder", "continuer")`,
    # `("EcranReglagesDeL_encodage", "continuer")` et
    # `("EcranEncodageEnCours", "sur_issue")` SONT SORTIS DE CET INVENTAIRE
    # le 2026-09-03, avec le lot B5 de la story 11.8 : `ParcoursExports` les
    # injecte tous les trois, et `chaine_du_produit` injecte
    # `ouvrir_l_atelier_exports`. **Les trois entrees annoncaient leur propre
    # sortie** (« elle SORT de cet inventaire le jour ou un parcours Exports
    # injecte le rappel »), et c'est le volet « declares mais desormais
    # cables » qui l'a dit, pas une relecture : cinquieme fois que cette garde
    # rougit dans le sens de la reparation.
    # `("EcranInventaireDuProjet", "supprimer")` EST SORTI DE CET INVENTAIRE le
    # 2026-09-06, avec le lot « la porte de l'inventaire » (`MQ-8`) :
    # `palier_projet_parcours.ParcoursDuPalierProjet.ouvrir` monte
    # `EcranInventaireDuProjet(arbre, supprimer=self.supprimer)`, et
    # `chaine_du_produit` injecte `ouvrir_la_gestion_des_medias`. **L'entree
    # annoncait sa propre sortie** (« elle SORT de cet inventaire le jour ou
    # l'entree `project` du palier Projet monte l'inventaire avec
    # `supprimer=cabler_la_suppression(...)` »), et c'est le volet « declares
    # mais desormais cables » qui l'a dit, pas une relecture : sixieme fois que
    # cette garde rougit dans le sens de la reparation.
    #
    # **Le mot-cle est passe A LA CONSTRUCTION, et ce n'est pas du style** : le
    # banc de la story 11.11 pose `ecran._supprimer` apres coup, ce que cette
    # garde ne verrait pas -- elle lit les mots-cles des appels sur l'arbre
    # syntaxique, jamais les affectations d'attributs. Le cycle « le rappel
    # veut l'ecran, l'ecran veut le rappel » est donc rompu par une METHODE
    # LIEE du parcours, qui est le geste que `ChaineReelle` documente deja
    # pour elle-meme.
    # **Le motif de ces deux entrees a ete REECRIT le 2026-09-06**, et pas
    # allege : il disait « aucun chemin de produit », ce qui est devenu FAUX le
    # jour ou le lot des suites de la suppression a cable les quatre. Une
    # entree d'inventaire dont le motif ment est pire qu'une entree absente --
    # elle classe le defaut au lieu de le nommer. Ce qui les garde ici est
    # desormais une propriete de la MESURE, pas une absence du produit.
    ("EcranResultatDeSuppression", "sur_suite"):
        "CABLE, mais par AFFECTATION D'ATTRIBUT, que cette garde ne voit pas "
        "-- elle lit les mots-cles des appels sur l'arbre syntaxique. "
        "`monter_le_compte_rendu` pose `ecran._sur_suite` APRES construction, "
        "parce que le rappel a besoin de l'ecran lui-meme pour retrouver "
        "l'application montee : un ecran ne peut pas se citer dans son propre "
        "appel de construction. Meme idiome, meme cycle rompu et meme angle "
        "mort que `ecran._supprimer` ci-dessus. Les quatre suites sont "
        "mesurees au clavier par "
        "`tests/unit/tui/test_suites_de_la_suppression.py`, et leur nommage "
        "par `test_couverture_des_suites.py`",
    ("EcranReussiteDeSuppression", "sur_suite"):
        "CABLE, meme regime et meme angle mort que son jumeau ci-dessus : "
        "`monter_le_compte_rendu` construit l'un ou l'autre selon "
        "`fichiers_non_supprimes` et pose `_sur_suite` apres coup, sur les "
        "deux. Elle SORT de cet inventaire le jour ou cette garde saura lire "
        "une affectation d'attribut -- ce qui la rendrait plus forte, et pas "
        "seulement plus bavarde",
    ("le_coeur_sait_compter", "point_d_entree"):
        "POINT D'INJECTION DE BANC ; le defaut est "
        "`encode_master.encoder_le_master_du_lot`, c'est-a-dire le vrai point "
        "d'entree de coeur de l'atelier Exports. Le double sert a poser la "
        "question aux DEUX etats -- un coeur qui accepte `rappel_progression` "
        "et un qui ne l'accepte pas --, sans quoi la frontiere de la jonction "
        "d'`EPIC11-ARB-184` serait verte sans rien prouver",
    ("raccord_de_progression", "point_d_entree"):
        "POINT D'INJECTION DE BANC, meme double et meme defaut que "
        "`le_coeur_sait_compter` ci-dessus : il le lui transmet tel quel, "
        "positionnellement, parce que le cabler par mot-cle ferait taire cette "
        "garde sans que le produit injecte quoi que ce soit",
    ("ParcoursExports", "encoder"):
        "POINT D'INJECTION DE BANC ; le defaut est "
        "`encode_master.encoder_le_master_du_lot`, le vrai point d'entree de "
        "coeur de l'atelier Exports -- il est rendu par la propriete "
        "`point_d_entree`, que le raccord de progression interroge. Absent, "
        "une passe reelle encode le master ; c'est le double qui est "
        "l'exception, pas le defaut",
    ("ParcoursExports", "planifier"):
        "POINT D'INJECTION DE BANC ; le defaut est `encode.plan_encode`, la "
        "seule redaction de la decision (destination libre, rang, completude). "
        "Elle sonde chaque frame par `ffprobe` : un banc qui n'a ni frames ni "
        "`ffprobe` passe le sien, le produit paie la vraie sonde",
    ("ParcoursExports", "horloge"):
        "POINT D'INJECTION DE BANC ; le defaut est celui de `chronometre()`, "
        "c'est-a-dire l'horloge reelle. Elle mesure la duree d'encodage que "
        "`E4-5` affiche : un banc qui ne veut pas attendre passe la sienne, "
        "et l'absence ne degrade rien",
    # **Ces deux entrees sont NEES le 2026-09-06**, avec le passage de la passe
    # d'extraction au fil de travail. `ParcoursExtraction._ecrire` appelle
    # desormais `lancer_l_extraction` -- qui recoit bien `extraire` et
    # `sur_suite`, et que cette garde voit --, si bien que le chemin SYNCHRONE
    # n'a plus aucun appelant de produit. Elles disent donc exactement ce
    # qu'elles sont : les mots-cles d'une fonction que seuls les bancs
    # empruntent.
    ("executer_et_conclure", "extraire"):
        "CHEMIN SYNCHRONE de l'extraction, plus emprunte par le produit depuis "
        "le passage au fil (2026-09-06) : `_ecrire` injecte `extraire` dans "
        "`lancer_l_extraction`. Le defaut reste `extraction.run_extraction`, "
        "atteint par `executer_le_plan`. Elle SORT de cet inventaire le jour "
        "ou un chemin de produit rappelle la forme synchrone",
    ("executer_et_conclure", "sur_suite"):
        "CHEMIN SYNCHRONE de l'extraction, meme regime que son jumeau "
        "ci-dessus : le produit passe `sur_suite` a `lancer_l_extraction`, qui "
        "le transporte jusqu'a `conclure_l_extraction` -- c'est ce que "
        "`test_suites_du_resultat.py` mesure, maillon par maillon. Absent, "
        "`E2-5` se replie sur l'ecran « pas encore », ce qui n'est pas un "
        "no-op",
    ("SurfaceExecution", "sur_jalon"):
        "commodite de construction ; le cablage reel du produit passe par "
        "`abonner()`, appele au montage de l'ecran d'execution",
    ("ouvrir_le_point_de_jugement", "sur_modification"):
        "l'absence N'EST PAS un no-op : « Modifier les reglages » remonte d'un "
        "palier (`app.action_remonter()`), ce que la branche `else` ecrit noir "
        "sur blanc",
}


# ---------------------------------------------------------------------------
# La mesure
# ---------------------------------------------------------------------------

def _paquet() -> Path:
    return Path(_SRC) / "mixed_media_utility" / "tui"


def _modules() -> list[tuple[str, ast.Module]]:
    fichiers = sorted(_paquet().glob("*.py"))
    assert len(fichiers) >= 2, (
        "une garde posee sur un paquet quasi vide serait verte sans rien "
        f"mesurer (trouve {fichiers!r})")
    return [(f.name, ast.parse(f.read_text(encoding="utf-8")))
            for f in fichiers]


def _nom_appele(noeud: ast.expr) -> str:
    """Le dernier segment du nom appele : `a.b.C(...)` -> `C`."""
    return ast.unparse(noeud).split(".")[-1]


def rappels_acceptes() -> dict[tuple[str, str], str]:
    """`(porteur, nom du rappel) -> module`, pour TOUT le paquet `tui/`.

    Un rappel « accepte » est un parametre dont l'annotation nomme `Callable`
    **et** `None`, et dont le defaut est le litteral `None` : c'est la forme
    exacte des sept occurrences historiques. Le porteur est la CLASSE quand le
    parametre est celui d'un `__init__`, la fonction sinon -- `K3.1a` portait
    sur `ouvrir_le_resultat`, une fonction, et une garde qui ne regarderait que
    les classes l'aurait manque.
    """
    acceptes: dict[tuple[str, str], str] = {}

    def parcourir(noeud, classe: str | None, module: str) -> None:
        for enfant in ast.iter_child_nodes(noeud):
            if isinstance(enfant, ast.ClassDef):
                parcourir(enfant, enfant.name, module)
            elif isinstance(enfant, (ast.FunctionDef, ast.AsyncFunctionDef)):
                porteur = (classe if (classe and enfant.name == "__init__")
                           else enfant.name)
                args = enfant.args
                paires = list(zip(args.args[len(args.args) - len(args.defaults):],
                                  args.defaults))
                paires += list(zip(args.kwonlyargs, args.kw_defaults))
                for arg, defaut in paires:
                    if arg.annotation is None:
                        continue
                    annotation = ast.unparse(arg.annotation)
                    if ("Callable" in annotation and "None" in annotation
                            and isinstance(defaut, ast.Constant)
                            and defaut.value is None):
                        acceptes[(porteur, arg.arg)] = module
                parcourir(enfant, classe, module)
            else:
                parcourir(enfant, classe, module)

    for module, arbre in _modules():
        parcourir(arbre, None, module)
    return acceptes


def _heritages() -> dict[str, list[str]]:
    """`classe -> bases`, pour propager une injection aux SOUS-CLASSES.

    `ouvrir_le_point_de_jugement` monte `PanneauConfirmation` ou
    `EcranEcrasement` et leur passe `sur_issue=` ; le parametre, lui, est
    declare sur leur base commune `EcranChiffre`. Sans cette propagation, la
    base passerait pour orpheline alors qu'elle est cablee deux fois.
    """
    table: dict[str, list[str]] = {}
    for _module, arbre in _modules():
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.ClassDef):
                table[noeud.name] = [_nom_appele(base) for base in noeud.bases]
    return table


def _fonctions_du_paquet() -> dict[str, ast.FunctionDef]:
    table: dict[str, ast.FunctionDef] = {}
    for _module, arbre in _modules():
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
                table[noeud.name] = noeud
    return table


def _cles_etalees(expression: ast.expr,
                  fonctions: dict[str, ast.FunctionDef]) -> set[str]:
    """Les cles litterales qu'un `**expression` etale sur l'appelé.

    Deux formes seulement, et c'est **volontairement etroit** : un
    dictionnaire ecrit sur place, et un appel de fonction du paquet dont les
    `return` rendent des dictionnaires litteraux -- ce qui est la forme de
    `ParcoursExtraction._affichage()`. Tout le reste (`**reglages`, un
    dictionnaire construit a la volee) ne credite **rien** : dans le doute, le
    rappel reste orphelin, ce qui fait rougir plutot que taire.
    """
    if isinstance(expression, ast.Dict):
        dictionnaires = [expression]
    elif isinstance(expression, ast.Call):
        fonction = fonctions.get(_nom_appele(expression.func))
        if fonction is None:
            return set()
        dictionnaires = [noeud.value for noeud in ast.walk(fonction)
                         if isinstance(noeud, ast.Return)
                         and isinstance(noeud.value, ast.Dict)]
    else:
        return set()
    return {cle.value for d in dictionnaires for cle in d.keys
            if isinstance(cle, ast.Constant) and isinstance(cle.value, str)}


def _alias_de_classes(portee) -> dict[str, set[str]]:
    """`classe = A if condition else B` -- le nom local et ce qu'il peut valoir.

    `ouvrir_le_point_de_jugement` choisit sa classe d'ecran a la volee ; sans
    cette resolution, l'appel `classe(...)` ne se rattacherait a aucun ecran.
    """
    table: dict[str, set[str]] = {}
    for noeud in ast.walk(portee):
        if isinstance(noeud, ast.Assign):
            for cible in noeud.targets:
                if isinstance(cible, ast.Name):
                    table.setdefault(cible.id, set()).update(
                        n.id for n in ast.walk(noeud.value)
                        if isinstance(n, ast.Name))
    return table


def rappels_injectes() -> set[tuple[str, str]]:
    """`(appelé, mot-cle)` pour tout appel du paquet qui passe un mot-cle."""
    fonctions = _fonctions_du_paquet()
    injectes: set[tuple[str, str]] = set()
    for _module, arbre in _modules():
        portees = [arbre] + [n for n in ast.walk(arbre)
                             if isinstance(n, (ast.FunctionDef,
                                               ast.AsyncFunctionDef))]
        for portee in portees:
            alias = _alias_de_classes(portee)
            for noeud in ast.walk(portee):
                if not isinstance(noeud, ast.Call):
                    continue
                appeles = {_nom_appele(noeud.func)}
                appeles |= alias.get(ast.unparse(noeud.func), set())
                for mot_cle in noeud.keywords:
                    noms = ({mot_cle.arg} if mot_cle.arg is not None
                            else _cles_etalees(mot_cle.value, fonctions))
                    for appele in appeles:
                        for nom in noms:
                            injectes.add((appele, nom))
    return injectes


def _ancetres(classe: str, heritages: dict[str, list[str]],
              vus: set[str] | None = None):
    vus = set() if vus is None else vus
    for base in heritages.get(classe, ()):
        if base in vus:
            continue
        vus.add(base)
        yield base
        yield from _ancetres(base, heritages, vus)


def rappels_orphelins() -> set[tuple[str, str]]:
    """Les rappels acceptes qu'AUCUN appel du paquet n'injecte."""
    acceptes = rappels_acceptes()
    injectes = rappels_injectes()
    heritages = _heritages()

    def cable(porteur: str, rappel: str) -> bool:
        if (porteur, rappel) in injectes:
            return True
        return any((sous, rappel) in injectes for sous in heritages
                   if porteur in set(_ancetres(sous, heritages)))

    return {cle for cle in acceptes if not cable(*cle)}


# ---------------------------------------------------------------------------
# Les deux volets de la garde
# ---------------------------------------------------------------------------

def test_les_RAPPELS_acceptes_par_les_ecrans_sont_INJECTES_ou_DECLARES():
    """L'egalite, et elle mord des DEUX cotes.

    A gauche : un rappel accepte que le produit n'injecte nulle part et que
    l'inventaire ne declare pas -- c'est la panne, sept fois payee.

    A droite : un rappel declare dans l'inventaire alors qu'il est desormais
    cable. Ce volet-la compte autant : un inventaire qui garderait ses vieilles
    entrees se remplirait jusqu'a ne plus rien mesurer.
    """
    orphelins = rappels_orphelins()
    assert orphelins == set(OPTIONNELS_ASSUMES), (
        "rappels optionnels qu'aucun appel du paquet TUI n'injecte et que "
        "l'inventaire ne declare pas : "
        f"{sorted(orphelins - set(OPTIONNELS_ASSUMES))} ; "
        "declares mais desormais cables : "
        f"{sorted(set(OPTIONNELS_ASSUMES) - orphelins)}")


def test_l_inventaire_des_OPTIONNELS_ne_declare_que_des_rappels_REELS():
    """Volet symetrique : un inventaire qui deriverait rendrait la garde muette.

    Une entree qui ne correspond a aucun parametre accepte ferait, a elle
    seule, tomber l'egalite ci-dessus dans le mauvais sens -- et on serait
    tente de la relacher. Elle est donc mesuree ici, separement.

    **Et chaque raison doit etre ECRITE** : l'interdit d'Egan est verbatim --
    « un rappel legitimement optionnel entre dans l'inventaire **avec son
    motif ecrit**, jamais en silence ». Une chaine vide vaut un silence.
    """
    acceptes = rappels_acceptes()
    inconnus = set(OPTIONNELS_ASSUMES) - set(acceptes)
    assert inconnus == set(), inconnus
    muettes = [cle for cle, raison in OPTIONNELS_ASSUMES.items()
               if not raison or not raison.strip()]
    assert muettes == [], muettes


def test_la_mesure_porte_sur_TOUT_le_paquet_tui_et_pas_sur_un_module():
    """Exigence d'Egan, verbatim : « elle porte sur **tout**
    `src/mixed_media_utility/tui/`, pas sur un module ».

    Mesure et non declaration : les rappels acceptes viennent d'au moins
    quatre modules differents, et les six modules d'ecran du paquet sont
    balayes. Une garde qui aurait glisse vers un seul fichier -- par un
    `glob` mal ecrit, par une liste en dur -- resterait verte sur les cinq
    autres.
    """
    modules = {module for module in rappels_acceptes().values()}
    assert len(modules) >= 4, modules
    balayes = {nom for nom, _arbre in _modules()}
    for attendu in ("atelier_extraction.py", "atelier_extraction_ecriture.py",
                    "ecran_projet.py", "ecran_ateliers.py", "execution.py",
                    "explorateur.py", "palier_projet.py", "rushes.py"):
        assert attendu in balayes, (attendu, sorted(balayes))


def test_la_mesure_est_SYNTAXIQUE_et_pas_un_grep_de_docstring():
    """La lecon du finding `I3`, mesuree.

    Le nom `sur_suite` etait cite partout dans les commentaires de `K3.1a` et
    injecte nulle part. Un banc qui grepperait le paquet aurait donc ete vert
    pendant tout le temps ou la panne durait.

    On le mesure en fabriquant les deux textes : le meme nom de rappel, une
    fois en docstring, une fois en mot-cle d'appel. Seul le second compte.
    """
    def injectes_de(source: str) -> set[tuple[str, str]]:
        arbre = ast.parse(source)
        fonctions: dict[str, ast.FunctionDef] = {}
        trouves = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Call):
                for mot_cle in noeud.keywords:
                    noms = ({mot_cle.arg} if mot_cle.arg is not None
                            else _cles_etalees(mot_cle.value, fonctions))
                    for nom in noms:
                        trouves.add((_nom_appele(noeud.func), nom))
        return trouves

    prose = '"""On injecte bien Ecran(sur_suite=...) quelque part."""\nEcran()\n'
    code = "Ecran(sur_suite=suivre)\n"
    assert injectes_de(prose) == set()
    assert injectes_de(code) == {("Ecran", "sur_suite")}


# ---------------------------------------------------------------------------
# Ce que cette garde N'ATTRAPE PAS, et il faut que ce soit ecrit quelque part
#
# * **`I0`, le journal du produit.** `logger` est annote `Any`, pas `Callable` :
#   ce n'est pas un rappel mais un objet, et l'elargissement a « tout parametre
#   optionnel » ferait entrer dans l'inventaire des dizaines de reglages sans
#   rapport (`objet`, `memoire`, `dossier_de_repli`, `horloge`, `probe`...).
#   Une garde bruyante finit relachee ;
# * **`I3` et `I2`, les surfaces publiques jamais appelees.** Ce ne sont pas des
#   parametres du tout : `bandeau_de_relink` est une FONCTION exportee que
#   personne n'appelle. C'est l'autre garde qui les tient, celle du lot `J`
#   (`test_TOUTE_surface_publique_de_rushes_est_CABLEE_ou_DECLAREE`), et les
#   deux sont complementaires -- l'une regarde ce qu'un module OFFRE, l'autre
#   ce qu'un ecran DEMANDE ;
# * **`E9` dans sa forme d'origine.** `CoqueTui(paliers=...)` prend une LISTE de
#   paliers, pas un rappel. Sa forme d'un cran plus loin, en revanche --
#   `ChaineReelle(ouvrir_les_cadences=...)`, injecte par `chaine_du_produit` --
#   est bien un rappel, et elle est couverte ;
# * **`N3`, l'issue lue puis jetee.** Le rappel `reprendre` est injecte, donc la
#   garde est verte -- mais elle l'etait aussi AVANT le correctif, quand
#   `traiter` lisait `choix.valider()` pour la seule comparaison a `None`. Le
#   silence y venait d'une VALEUR DE RETOUR ignoree, pas d'un rappel absent, et
#   aucune mesure syntaxique raisonnable ne distingue « lue puis jetee » de
#   « lue puis utilisee » sans devenir un analyseur de flot. Ce que le depot
#   oppose a cette famille-la est ailleurs : un banc par issue, qui mesure que
#   les trois menent a trois etats DIFFERENTS
#   (`test_lots_m_n_previz_et_refus.py`). Trois issues qui font la meme chose
#   ne se voient que la.
# ---------------------------------------------------------------------------

def test_les_QUATRE_cas_historiques_de_la_FAMILLE_sont_bien_dans_le_domaine():
    """Les quatre occurrences que cette garde-ci peut voir sont **acceptees**.

    Une garde dont le domaine ne contient pas les cas qu'elle est censee
    fermer serait verte pour la mauvaise raison. On mesure donc que les quatre
    rappels concernes sont bien vus comme « acceptes » : `ChaineReelle`
    (`E9`, un cran plus loin), `EcranRushes.ajouter` (`K1.1a`),
    `ouvrir_le_resultat.sur_suite` (`K3.1a`) et `EcranRefusRelink.reprendre`
    (`N3`).
    """
    acceptes = set(rappels_acceptes())
    for cle in (("ChaineReelle", "ouvrir_les_cadences"),
                ("EcranRushes", "ajouter"),
                ("ouvrir_le_resultat", "sur_suite"),
                ("EcranRefusRelink", "reprendre")):
        assert cle in acceptes, (cle, sorted(acceptes))


@pytest.mark.parametrize("cle", [
    ("ChaineReelle", "ouvrir_les_cadences"),
    ("ouvrir_le_resultat", "sur_suite"),
    ("EcranRefusRelink", "reprendre"),
])
def test_les_rappels_HISTORIQUEMENT_decables_sont_aujourd_hui_INJECTES(cle):
    """Volet positif, un cas par ligne : ces trois-la sont **cables**.

    C'est ce que la campagne d'injection remesure en les decablant un par un ;
    ce banc-ci est ce qui rougit alors. `EcranRushes.ajouter` n'y figure pas :
    il est le quatrieme cas, et il est encore ouvert (`K1.1d`) -- il vit dans
    :data:`OPTIONNELS_ASSUMES` avec sa raison.
    """
    assert cle not in rappels_orphelins()
