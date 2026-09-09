# -*- coding: utf-8 -*-
"""Story 11.0, AC 2 et AC 3 -- jetons importes, glyphes, frontieres.

**Les frontieres negatives sont mesurees par l'arbre syntaxique, pas par un
grep de texte.** Motif mesure a l'ecriture : le docstring de
`tui/jetons.py` explique *pourquoi* il n'importe pas `SEMANTIQUES` -- il porte
donc le mot. Un grep de texte y mordrait et rendrait la garde inutilisable, ce
qui la ferait affaiblir ou supprimer. Lire les identifiants reellement
references par le code dit exactement ce que l'AC veut dire, et une prose
d'explication n'a plus a se censurer pour le confort de la garde.

Chaque frontiere porte son **volet symetrique** : la meme mesure appliquee a un
module fabrique qui viole la regle doit MORDRE. Sans lui, une garde qui ne
regarderait rien serait verte.
"""

import re
import unicodedata
from pathlib import Path

import pytest

from mixed_media_utility.gui import jetons as jetons_gui
from mixed_media_utility.tui import jetons

from outils_frontiere import chaines_de_code, identifiants

#: Ce que la GUI expose et que la TUI n'a **pas** le droit de toucher : ce sont
#: des chromies pleines, valeurs de trait et d'aplat. Dans un terminal tout est
#: glyphe, donc les importer serait un defaut de contraste, pas un style.
INTERDITS = ("SEMANTIQUES", "ACCENT")

#: Une couleur ecrite en dur, sous la forme ou elle apparaitrait vraiment.
MOTIF_HEXA = re.compile(r"#[0-9a-fA-F]{6}")


@pytest.fixture
def module_fabrique(tmp_path):
    """Ecrit un module qui VIOLE la regle, pour les volets symetriques."""
    def _ecrire(source: str) -> Path:
        chemin = tmp_path / "module_fautif.py"
        chemin.write_text(source, encoding="utf-8")
        return chemin
    return _ecrire


# --------------------------------------------------------------------------
# AC 2 -- les jetons sont importes, et seules les variantes de texte
# --------------------------------------------------------------------------

def test_les_six_jetons_valent_exactement_ceux_de_la_gui():
    """AC 2.1 et 2.3 : projection, pas recopie."""
    assert dict(jetons.COULEURS) == {
        "state-complete": jetons_gui.VARIANTES_TEXTE["state-complete-text"],
        "state-substitute": jetons_gui.VARIANTES_TEXTE["state-substitute-text"],
        "state-absent": jetons_gui.VARIANTES_TEXTE["state-absent-text"],
        "accent": jetons_gui.VARIANTES_TEXTE["accent-text"],
        "data": jetons_gui.NEUTRES["text-primary"],
        "muted": jetons_gui.NEUTRES["text-secondary"],
    }


def test_les_jetons_d_etat_ne_sont_pas_les_chromies_pleines():
    """AC 2.3 : la variante de texte differe de la chromie pleine, et c'est le
    point -- si les deux etaient egales, la frontiere sur `SEMANTIQUES` ne
    protegerait de rien."""
    assert jetons.COULEURS["state-complete"] != jetons_gui.SEMANTIQUES["state-complete"]
    assert jetons.COULEURS["accent"] != jetons_gui.ACCENT["accent"]


def test_aucune_couleur_litterale_dans_le_paquet_tui(sources_tui):
    """AC 2.2, frontiere : comptage a zero sur TOUT le paquet.

    L'AC tolerait des litteraux dans le module de jetons de la TUI ; il n'y en
    a aucun, la mesure est donc posee plus haut que l'AC ne l'exige.
    """
    coupables = {
        chemin.name: [c for c in chaines_de_code(chemin) if MOTIF_HEXA.search(c)]
        for chemin in sources_tui
    }
    assert not any(coupables.values()), coupables


def test_la_mesure_des_couleurs_litterales_mord_sur_un_module_fautif(module_fabrique):
    """AC 2.2, volet symetrique : sans lui la garde ci-dessus ne prouve rien."""
    chemin = module_fabrique(
        '"""Un docstring qui parle de #FFFFFF sans le poser."""\n'
        'TEINTE = "#4EC57A"\n'
    )
    trouves = [c for c in chaines_de_code(chemin) if MOTIF_HEXA.search(c)]
    assert trouves == ["#4EC57A"], (
        "la mesure doit voir la constante et ignorer le docstring")


@pytest.mark.parametrize("interdit", INTERDITS)
def test_aucun_import_de_chromie_pleine_dans_le_paquet_tui(interdit, sources_tui):
    """AC 2.3, frontiere : comptage a zero, une mesure par nom interdit."""
    coupables = {chemin.name for chemin in sources_tui
                 if interdit in identifiants(chemin)}
    assert not coupables, f"{interdit} reference dans {sorted(coupables)}"


@pytest.mark.parametrize("interdit", INTERDITS)
def test_la_mesure_des_chromies_pleines_mord_sur_un_module_fautif(
        module_fabrique, interdit):
    """AC 2.3, volet symetrique, sur les DEUX noms -- pas seulement le premier."""
    chemin = module_fabrique(
        f'"""Docstring qui cite {interdit} en prose, et ne doit pas compter."""\n'
        f'from mixed_media_utility.gui.jetons import {interdit}\n'
        f'VALEUR = {interdit}\n'
    )
    assert interdit in identifiants(chemin)
    # Et le meme module, prose seule, ne mord pas : c'est ce qui rend la garde
    # utilisable par un docstring qui explique la regle.
    prose = module_fabrique(f'"""On n\'importe pas {interdit}, voici pourquoi."""\n')
    assert interdit not in identifiants(prose)


def test_le_module_de_jetons_importe_bien_la_gui():
    """AC 2.1 : l'import existe -- une projection sans import serait une copie."""
    chemin = Path(jetons.__file__)
    source = chemin.read_text(encoding="utf-8")
    assert "from ..gui import jetons" in source
    assert "VARIANTES_TEXTE" in identifiants(chemin)


# --------------------------------------------------------------------------
# AC 2.4 -- le contraste, CALCULE dans le test
# --------------------------------------------------------------------------

def _canal_lineaire(octet: int) -> float:
    canal = octet / 255
    return canal / 12.92 if canal <= 0.03928 else ((canal + 0.055) / 1.055) ** 2.4


def luminance(couleur: str) -> float:
    """Luminance relative WCAG 2.1, recalculee ici et jamais importee."""
    brut = couleur.lstrip("#")
    rouge, vert, bleu = (int(brut[i:i + 2], 16) for i in (0, 2, 4))
    return (0.2126 * _canal_lineaire(rouge)
            + 0.7152 * _canal_lineaire(vert)
            + 0.0722 * _canal_lineaire(bleu))


def contraste(avant: str, arriere: str) -> float:
    clair, sombre = sorted((luminance(avant), luminance(arriere)), reverse=True)
    return (clair + 0.05) / (sombre + 0.05)


def test_la_mesure_de_contraste_est_juste_sur_des_valeurs_connues():
    """Le calcul se verifie sur deux paires dont le ratio est connu d'avance.

    Sans ce test, une formule fausse rendrait TOUS les contrastes faux dans le
    meme sens et les assertions suivantes resteraient vertes.
    """
    assert contraste("#000000", "#FFFFFF") == pytest.approx(21.0, abs=1e-9)
    assert contraste("#777777", "#FFFFFF") == pytest.approx(4.48, abs=0.01)


@pytest.mark.parametrize("nom", sorted(jetons.COULEURS))
def test_chaque_jeton_tient_4_5_contre_le_fond_sombre(nom):
    """AC 2.4 : le contraste tient sur le fond pour lequel la GUI les a regles."""
    fond = jetons_gui.NEUTRES["surface-canvas"]
    mesure = contraste(jetons.COULEURS[nom], fond)
    assert mesure >= 4.5, f"{nom} ne tient que {mesure:.2f}:1 sur {fond}"


def test_aucun_jeton_ne_tient_4_5_sur_un_fond_clair():
    """AC 2.4, seconde moitie : elle est **fausse**, et ce test l'epingle.

    Les six jetons sont ceux de la GUI, regles pour un fond sombre. Mesure :
    aucun des six n'atteint 4,5:1 sur du blanc (le meilleur, `muted`, plafonne
    a 2,81:1). L'AC 2.4 telle qu'ecrite exigeait les deux fonds a la fois ;
    c'etait inatteignable sans inventer des couleurs propres a la TUI, ce que
    l'AC 2.1 interdit dans la meme story.

    Le test **fige le fait** au lieu de le taire : si un jour un jeton tenait
    sur fond clair, ce test tomberait et forcerait a rouvrir la question. Elle
    est portee a Egan pour arbitrage (imposer le fond, ou s'en remettre au
    second canal des glyphes, qui est la regle 1 de `DESIGN.md` section 5).
    """
    tenants = {nom: contraste(valeur, "#FFFFFF")
               for nom, valeur in jetons.COULEURS.items()
               if contraste(valeur, "#FFFFFF") >= 4.5}
    assert tenants == {}
    assert max(contraste(v, "#FFFFFF")
               for v in jetons.COULEURS.values()) == pytest.approx(2.81, abs=0.01)


# --------------------------------------------------------------------------
# AC 3 -- un glyphe pour chaque etat, et le rendu sans couleur reste lisible
# --------------------------------------------------------------------------

#: La table de `DESIGN.md` section 6, recopiee ici depuis le DESIGN et non
#: depuis le module teste : comparer le module a lui-meme ne mesurerait rien.
TABLE_ATTENDUE = {
    "complete": "●", "substitute": "▲", "absent": "✕", "neutre": "·",
    "curseur": "▸", "coche": "[x]", "decoche": "[ ]",
    "exclusif-retenu": "(•)", "exclusif-libre": "( )",
    "barre-pleine": "▓", "barre-vide": "░",
    "invite": ">", "caret": "█", "rattachement": "└─",
}


def test_la_table_de_glyphes_est_complete_et_conforme_au_design():
    """AC 3.1."""
    assert dict(jetons.GLYPHES) == TABLE_ATTENDUE


@pytest.mark.parametrize("table", [jetons.GLYPHES, jetons.GLYPHES_ASCII])
def test_chaque_table_est_injective(table):
    """AC 3.2 et 3.3 : deux etats ne partagent jamais un dessin.

    Sauf `curseur`/`invite`, qui portent le meme `>` dans les deux tables :
    c'est une identite du DESIGN (le curseur de liste et l'invite de saisie
    disent la meme chose -- « c'est ici que vous etes »), pas une collision.
    """
    valeurs = [v for cle, v in table.items() if cle != "invite"]
    assert len(set(valeurs)) == len(valeurs), sorted(table.items())


def test_les_deux_tables_couvrent_les_memes_etats():
    """AC 3.3 : le repli ne perd aucun etat en route."""
    assert set(jetons.GLYPHES) == set(jetons.GLYPHES_ASCII)


@pytest.mark.parametrize("ascii_seul", [False, True])
def test_les_trois_etats_rendus_sans_couleur_restent_distincts(ascii_seul):
    """AC 3.2 : trois chaines differentes, sans aucune couleur en jeu."""
    rendus = [jetons.marque(etat, "lot_25fps", ascii_seul=ascii_seul)
              for etat in ("complete", "substitute", "absent")]
    assert len(set(rendus)) == 3, rendus
    # Le libelle est le meme pour les trois : ce qui les distingue est donc
    # bien le glyphe, et rien d'autre.
    assert all(r.endswith("lot_25fps") for r in rendus)


def test_le_repli_ascii_change_le_dessin_et_pas_le_sens():
    """AC 3.3 : meme etat, deux dessins ; et le repli reste en ASCII pur."""
    for etat in TABLE_ATTENDUE:
        repli = jetons.GLYPHES_ASCII[etat]
        assert repli.isascii(), f"{etat} rend {repli!r}, qui n'est pas ASCII"
    assert jetons.GLYPHES["complete"] != jetons.GLYPHES_ASCII["complete"]


def test_glyphes_rend_la_table_du_mode_demande():
    assert jetons.glyphes() is jetons.GLYPHES
    assert jetons.glyphes(ascii_seul=True) is jetons.GLYPHES_ASCII


@pytest.mark.parametrize("nom", sorted(jetons.COULEURS))
def test_couleur_rend_chaque_jeton_par_son_nom(nom):
    """La cible n'est pas toujours en premiere position : la table est
    parcourue en entier, ordre alphabetique compris."""
    assert jetons.couleur(nom) == jetons.COULEURS[nom]


def test_un_jeton_inconnu_est_refuse_et_le_refus_nomme_les_jetons_connus():
    with pytest.raises(KeyError) as echec:
        jetons.couleur("state-complete-text")
    message = str(echec.value)
    assert "state-complete-text" in message and "muted" in message


def test_un_glyphe_inconnu_est_refuse():
    with pytest.raises(KeyError) as echec:
        jetons.marque("termine")
    assert "termine" in str(echec.value)


def test_les_tables_sont_figees():
    """Une table modifiable laisserait un atelier « corriger » un glyphe chez lui."""
    for table in (jetons.COULEURS, jetons.GLYPHES, jetons.GLYPHES_ASCII):
        with pytest.raises(TypeError):
            table["complete"] = "X"


#: Le repli ASCII de `DESIGN.md` section 6, recopie **du DESIGN** et non du
#: module. Il n'en avait aucun : la table de repli n'etait comparee a rien, et
#: deux mutants y survivaient (revue de vague 1, couche 2).
#:
#: Le DESIGN nomme neuf substitutions ; les cinq autres cles de la table sont
#: deja en ASCII pur cote UTF-8 (`[x]`, `[ ]`, `>`) ou n'ont pas d'equivalent
#: nomme (`(•)`, `( )`). Le test les traite separement plutot que d'inventer
#: une regle que le DESIGN n'ecrit pas.
REPLIS_DU_DESIGN = {
    "complete": "*", "substitute": "!", "absent": "x", "neutre": ".",
    "curseur": ">", "barre-pleine": "#", "barre-vide": "-",
    "rattachement": "\\_", "caret": "_",
}


@pytest.mark.parametrize("etat,repli", sorted(REPLIS_DU_DESIGN.items()))
def test_le_repli_ascii_est_celui_que_le_design_ecrit(etat, repli):
    """Le repli est confronte au DESIGN, pas au module qu'il teste."""
    assert jetons.GLYPHES_ASCII[etat] == repli


def test_les_cles_sans_repli_nomme_restent_lisibles_en_ascii():
    """Les cinq cles que le DESIGN ne substitue pas nommement doivent tout de
    meme etre ASCII -- sans quoi `--ascii` ne tiendrait pas sa promesse."""
    sans_repli_nomme = set(jetons.GLYPHES_ASCII) - set(REPLIS_DU_DESIGN)
    assert sans_repli_nomme == {"coche", "decoche", "exclusif-retenu",
                                "exclusif-libre", "invite"}
    for cle in sans_repli_nomme:
        assert jetons.GLYPHES_ASCII[cle].isascii()


def test_une_marque_sans_libelle_ne_traine_pas_d_espace():
    """Branche non mesuree : un mutant qui supprimait la condition ajoutait une
    espace parasite en fin de marque, ce qui casse tout calage a droite du
    glyphe seul (revue de vague 1, couche 2, mutant M18).
    """
    assert jetons.marque("complete") == jetons.GLYPHES["complete"]
    assert jetons.marque("complete", "") == jetons.GLYPHES["complete"]
    assert not jetons.marque("complete").endswith(" ")
    # Volet symetrique : avec un libelle, l'espace de separation EST attendue.
    assert jetons.marque("complete", "lot") == f"{jetons.GLYPHES['complete']} lot"


# --------------------------------------------------------------------------
# La primitive de mesure vit dans le module de MESURE, et une seule fois
# --------------------------------------------------------------------------

#: Les deux noms sous lesquels le creux minimal a ete ecrit. La garde compte
#: les DEUX : une copie reintroduite sous son ancien nom prive passerait au
#: travers d'une garde qui ne connaitrait que le nom public.
NOMS_DU_CREUX = ("CREUX_MINIMAL", "_CREUX_MINIMAL")


def _definitions(fichiers, noms_de_fonction, noms_de_constante):
    """Ou chaque fonction et chaque constante nommees sont **definies**.

    A l'AST, comme les autres frontieres de ce fichier : un grep compterait le
    nom vu dans un commentaire ou dans un appel. Un `from … import X as Y` n'est
    pas une definition et n'est donc **pas** compte -- c'est exactement la
    distinction qui separe « quatre modules lisent la primitive » de « quatre
    modules l'ecrivent ».
    """
    import ast

    trouvees = []
    for fichier in fichiers:
        arbre = ast.parse(Path(fichier).read_text(encoding="utf-8"))
        for noeud in ast.walk(arbre):
            if (isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and noeud.name in noms_de_fonction):
                trouvees.append(f"{Path(fichier).name}:{noeud.name}")
            elif isinstance(noeud, ast.Assign):
                for cible in noeud.targets:
                    if (isinstance(cible, ast.Name)
                            and cible.id in noms_de_constante):
                        trouvees.append(f"{Path(fichier).name}:{cible.id}")
            elif (isinstance(noeud, ast.AnnAssign)
                  and isinstance(noeud.target, ast.Name)
                  and noeud.target.id in noms_de_constante):
                trouvees.append(f"{Path(fichier).name}:{noeud.target.id}")
    return sorted(trouvees)


def test_l_abregement_de_nom_et_son_creux_n_ont_qu_UNE_ecriture(sources_tui):
    """Ils en avaient une et QUATRE (revue de vague 2 bis, dette laissee ouverte).

    `abreger_nom` vivait dans `explorateur.py` -- l'ecran qui en avait besoin le
    premier --, donc les trois autres lignes de la TUI qui bornent un nom
    l'importaient depuis un ecran. Le creux minimal, lui, n'etait pas
    importable du tout : il etait **reecrit dans quatre modules**
    (`explorateur`, `ecran_projet`, `noms`, `panneau`), chacun avec un
    commentaire renvoyant a l'original. Quatre ecritures de la meme valeur
    divergent au premier ajustement -- c'est le motif que
    `projets.LEGENDE_DES_CARDINAUX` documente pour justifier de ne pas recopier.

    Mesure a l'identite d'objet **et** a la structure : un jour ou l'autre
    quelqu'un reecrira une fonction plutot que de lire celle qui existe.
    """
    from mixed_media_utility.tui import explorateur, noms, panneau

    assert noms._abreger is jetons.abreger_nom
    assert noms._CREUX_MINIMAL is jetons.CREUX_MINIMAL
    # L'explorateur ne l'expose plus : deux noms publics pour une meme fonction
    # laisseraient les appelants se repartir entre les deux, et la prochaine
    # correction n'en toucherait qu'un.
    assert not hasattr(explorateur, "abreger_nom")
    assert "abreger_nom" not in explorateur.__all__
    assert not hasattr(panneau, "_CREUX_MINIMAL")

    assert _definitions(sources_tui, {"abreger_nom"}, set(NOMS_DU_CREUX)) == [
        "jetons.py:CREUX_MINIMAL", "jetons.py:abreger_nom"]


def test_la_mesure_d_unicite_MORD_sur_un_module_qui_recopie(module_fabrique):
    """Volet symetrique, sans lequel la garde ci-dessus pourrait ne rien voir.

    Elle lit un AST : une lecture qui raterait les `FunctionDef` ou les `Assign`
    rendrait la liste vide, donc verte, sur un paquet entierement fautif.
    """
    fautif = module_fabrique(
        "_CREUX_MINIMAL = 2\n\n\n"
        "def abreger_nom(nom, largeur, ascii_seul=False):\n"
        "    return nom[:largeur]\n")
    assert _definitions([fautif], {"abreger_nom"}, set(NOMS_DU_CREUX)) == [
        "module_fautif.py:_CREUX_MINIMAL", "module_fautif.py:abreger_nom"]

    # Et un module qui se contente de LIRE la primitive n'est pas compte.
    sage = module_fabrique(
        "from .jetons import CREUX_MINIMAL as _CREUX_MINIMAL\n"
        "from .jetons import abreger_nom\n\n\n"
        "def ligne(nom):\n"
        "    return abreger_nom(nom, 10 - _CREUX_MINIMAL)\n")
    assert _definitions([sage], {"abreger_nom"}, set(NOMS_DU_CREUX)) == []


def test_le_MODELE_du_panneau_n_importe_aucun_ECRAN():
    """`panneau.py` se presente comme un modele pur : il doit le rester.

    Il importait `explorateur.py` -- un ecran -- pour la seule raison que la
    primitive d'abregement y vivait. Il n'y avait pas de cycle, mais la
    dependance etait a l'envers : un modele qui depend d'un ecran ne se mesure
    plus sans lui, et c'est la porte d'entree du cycle suivant. Elle disparait
    en meme temps que la primitive descend dans le module de mesure.
    """
    import ast

    from mixed_media_utility.tui import panneau

    arbre = ast.parse(Path(panneau.__file__).read_text(encoding="utf-8"))
    racines = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            racines.update(a.name.split(".")[0] for a in noeud.names)
        elif isinstance(noeud, ast.ImportFrom):
            # `from . import explorateur` porte un module VIDE : le module vise
            # est dans les alias. Ne lire que `noeud.module` laisserait passer
            # la forme exacte que `panneau.py` employait pour ses voisins --
            # c'est le volet symetrique ci-dessous qui l'a fait voir.
            if noeud.module:
                racines.add(noeud.module.split(".")[0])
            else:
                racines.update(alias.name.split(".")[0]
                               for alias in noeud.names)
    interdits = {"textual", "coque", "explorateur", "ecran_projet",
                 "ecran_ateliers", "execution"}
    assert not racines & interdits, racines
    # Volet symetrique : la lecture voit bien les imports qui SONT la.
    assert "jetons" in racines


# --------------------------------------------------------------------------
# Revue de la vague 3, couche 1 -- l'abregement : la classe `F` et la colonne
# impaire
# --------------------------------------------------------------------------

def test_l_abregement_compte_la_PLEINE_CHASSE_comme_deux_colonnes():
    """**Le second site de la table `("W", "F")`, et il survivait** (finding
    `C2`, volet `C2b`).

    `colonnes()` et `_cout()` portent la MEME table, et la fermer sur l'une ne
    ferme rien sur l'autre : `_cout` est ce dont `_tete` et `_fin` se servent,
    donc le chemin d'ABREGEMENT. Un nom en latin pleine chasse -- la saisie par
    defaut d'un IME japonais ou chinois sous Windows -- y serait compte a la
    moitie de sa largeur, et l'abrege deborderait le budget qu'on vient de lui
    donner.

    La mesure porte sur la SORTIE, en colonnes, jamais sur `len()` : c'est la
    seule facon de distinguer les deux.
    """
    # 12 caracteres pleine chasse (2 colonnes chacun) + 2 soulignes ASCII.
    nom = "ＴＥＳＴ_ＦＩＬＥ_ＲＵＳＨ"      # 14 caracteres, 26 colonnes
    assert jetons.colonnes(nom) == 26, jetons.colonnes(nom)
    assert len(nom) == 14
    for largeur in range(4, 27):
        abrege = jetons.abreger_nom(nom, largeur)
        assert jetons.colonnes(abrege) <= largeur, (
            f"largeur {largeur} : l'abrege occupe "
            f"{jetons.colonnes(abrege)} colonnes -- {abrege!r}")


def test_a_budget_IMPAIR_c_est_la_TETE_qui_gagne_la_colonne():
    """**La decision est argumentee dans le code et mesuree par rien** (finding
    `T1`).

    `abreger_nom` fait `queue = budget // 2`, avec son motif ecrit sur place :
    « la tete porte la date, et deux dossiers d'un meme tournage ne se
    distinguent qu'a partir d'elle ». Le mutant symetrique
    (`queue = budget - budget // 2`, la queue gagne la colonne) survivait a 414
    tests.

    Le nom est choisi pour que les deux repartitions soient DISCERNABLES : une
    tete et une queue de contenus differents, et un budget impair.
    """
    nom = "2026-08-29_camera_B_v3"
    abrege = jetons.abreger_nom(nom, 12)          # 12 - 1 point = 11, impair
    assert jetons.colonnes(abrege) <= 12, abrege
    tete, _, queue = abrege.partition(jetons.points_d_abregement(False))
    assert jetons.colonnes(tete) == 6, (
        f"a budget impair la TETE prend la colonne en trop : {abrege!r}")
    assert jetons.colonnes(queue) == 5, abrege
    # Et le volet qui dit POURQUOI : la date reste lisible, ce que la
    # repartition inverse perdrait.
    assert abrege.startswith("2026-0"), abrege


def test_les_MARQUES_COMBINANTES_ne_comptent_AUCUNE_colonne():
    """**La branche des marques combinantes, mesuree par rien** (revue de la
    vague 3, couche 2, finding `C2`).

    `colonnes` et `_cout` ecartent tous deux les marques combinantes
    (`unicodedata.combining`), et retirer l'une ou l'autre de ces gardes
    survivait aux **2 179** tests de `tests/unit/tui`. Le volet « double
    chasse » du meme `if`, lui, etait tue -- donc c'est bien la moitie
    combinante, et elle seule, qui n'etait pas tenue.

    **Le regime qui la declenche n'a rien d'exotique : c'est macOS.** Un volume
    HFS+/APFS range ses noms en forme **NFD**, ou `e` est suivi de son accent
    combinant U+0301. Un dossier nomme `rushes_prepares_camera_A` avec accents
    y arrive donc en NFD, et une mesure qui compte l'accent croit la ligne plus
    large qu'elle n'est.

    La mesure porte sur l'EGALITE des deux formes : c'est ce qui distingue
    « compte les colonnes » de « compte les caracteres », et aucune assertion
    sur une seule forme ne le ferait.
    """
    nfc = unicodedata.normalize("NFC", "rushes_préparés_caméra_A")
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfd != nfc, "la fixture doit vraiment porter deux formes distinctes"
    assert len(nfd) > len(nfc), (len(nfd), len(nfc))

    assert jetons.colonnes(nfd) == jetons.colonnes(nfc), (
        "une marque combinante n'occupe AUCUNE colonne : les deux formes du "
        f"meme nom mesurent pareil -- NFD={jetons.colonnes(nfd)}, "
        f"NFC={jetons.colonnes(nfc)}")
    assert jetons.colonnes(nfd) == len(nfc)


def test_l_abregement_d_un_nom_NFD_tient_sa_largeur_et_ne_COUPE_pas_un_accent():
    """Le volet d'`abreger_nom` : `_cout` porte la meme garde, et le meme trou.

    Sous le mutant, `abreger_nom(NFD("rushes_préparés_caméra_A"), 20)` rend
    `'rushes_pre…caméra_A'` la ou le sain rend `'rushes_pré…_caméra_A'` : la
    ligne est crue 27 colonnes au lieu de 24, le nom est coupe trois colonnes
    trop tot, et un `e` se retrouve separe de son accent.
    """
    nfc = unicodedata.normalize("NFC", "rushes_préparés_caméra_A")
    nfd = unicodedata.normalize("NFD", nfc)
    for largeur in range(4, 26):
        abrege = jetons.abreger_nom(nfd, largeur)
        assert jetons.colonnes(abrege) <= largeur, (largeur, abrege)

        # **L'EGALITE des deux formes, et c'est elle qui mesure `_cout`.**
        # Une garde manquante y fait SUR-compter la marque combinante, ce qui
        # rend l'abrege plus COURT -- jamais plus large. « Il tient dans sa
        # largeur » reste donc vrai des deux cotes et ne mesure rien. Ce qui
        # mesure, c'est que le meme nom, dans ses deux formes, s'abrege au
        # meme endroit.
        assert unicodedata.normalize("NFC", abrege) == \
            jetons.abreger_nom(nfc, largeur), (
                f"largeur {largeur} : les deux formes du meme nom s'abregent "
                f"differemment -- NFD={abrege!r}, "
                f"NFC={jetons.abreger_nom(nfc, largeur)!r}")
        # Aucun accent orphelin : une marque combinante n'ouvre jamais l'abrege
        # ni ne suit immediatement le symbole d'abregement.
        assert not unicodedata.combining(abrege[0]), abrege
        points = jetons.points_d_abregement(False)
        if points in abrege:
            apres = abrege.split(points, 1)[1]
            assert not apres or not unicodedata.combining(apres[0]), abrege
